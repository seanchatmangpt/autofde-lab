from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from urllib.request import urlopen

import dspy

from autofde_lab.powl.runner import PowlV2Runner, RunnerConfig, RunStatus

from . import SIGNATURE_REVISION
from .epistemic import (
    EpistemicRoute,
    compute_hypothesis_records,
    discrimination_frontier,
    route_epistemic_state,
)
from .facts import FactStore
from .mcp import McpBroker
from .models import DiagnosisCandidate, HypothesisProposal, HypothesisRecord, MitigationProcessProposal
from .powl_process import (
    McpActivityDriver,
    ProcessAdmissionError,
    compile_mitigation_process,
    compile_observation_process,
)
from .signatures import (
    ChallengeDiagnosis,
    CommitDiagnosis,
    ConstructDiscriminationProcess,
    ConstructMitigationProcesses,
    GenerateHypotheses,
    OrientIncident,
    RelateEvidence,
)


def _json(value) -> str:
    if isinstance(value, list):
        payload = [v.model_dump() if hasattr(v, "model_dump") else v for v in value]
    elif hasattr(value, "model_dump"):
        payload = value.model_dump()
    else:
        payload = value
    return json.dumps(payload, sort_keys=True, default=str)


class SignatureProgram:
    """No optimizer or compiler: source signatures are the experimental variable."""

    def __init__(self) -> None:
        self.orient = dspy.Predict(OrientIncident)
        self.hypothesize = dspy.Predict(GenerateHypotheses)
        self.relate = dspy.Predict(RelateEvidence)
        self.discriminate = dspy.Predict(ConstructDiscriminationProcess)
        self.commit = dspy.Predict(CommitDiagnosis)
        self.challenge = dspy.Predict(ChallengeDiagnosis)
        self.mitigate = dspy.Predict(ConstructMitigationProcesses)


async def _wait_for_stage(target: set[str], *, timeout_s: int = 300) -> str:
    host = os.getenv("API_HOSTNAME", "localhost")
    port = os.getenv("API_PORT", "8000")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://{host}:{port}/status", timeout=5) as response:
                stage = json.loads(response.read().decode()).get("stage", "error")
        except Exception:
            stage = "error"
        if stage in target:
            return stage
        await asyncio.sleep(1)
    raise TimeoutError(f"benchmark stage did not enter {sorted(target)}")


async def _seed_observations(broker: McpBroker, facts: FactStore, capabilities) -> None:
    available = {(c.surface, c.tool) for c in capabilities}
    if ("kubectl", "exec_kubectl_cmd_safely") not in available:
        return
    # Kubernetes adapter bootstrap only. Core epistemic routing never branches
    # on object kinds; subsequent reads are signature-manufactured from the live
    # capability catalog.
    for cmd in (
        "kubectl api-resources -o wide",
        "kubectl get events -A --sort-by=.lastTimestamp",
        "kubectl get pods -A -o wide",
    ):
        raw = await broker.call("kubectl", "exec_kubectl_cmd_safely", {"cmd": cmd})
        facts.ingest(f"mcp:kubectl:{cmd}", raw)


def _process_observations(evidence, store: FactStore) -> int:
    count = 0
    for record in evidence.activity_records:
        observation = record.metadata.get("observation") if record.success else None
        if observation:
            count += len(
                store.ingest(
                    f"mcp:{record.metadata.get('surface')}:{record.metadata.get('tool')}",
                    str(observation),
                )
            )
    return count


def _activity_records(evidence) -> list[dict]:
    return [
        {
            "label": record.label,
            "path": list(record.path),
            "attempt": record.attempt,
            "success": record.success,
            "committed": record.committed,
            "metadata": dict(record.metadata),
            "error_type": record.error_type,
            "error_message": record.error_message,
        }
        for record in evidence.activity_records
    ]


def _mitigation_rank(process: MitigationProcessProposal) -> tuple:
    return (
        process.risk,
        sum(step.consequence == "DO" for step in process.steps),
        len(process.steps),
        process.id,
    )


def _diagnosis_identity_is_admitted(
    diagnosis: DiagnosisCandidate,
    records: list[HypothesisRecord],
    admitted_fact_ids: set[str],
) -> bool:
    if not diagnosis.root_causes:
        return False
    supported_ids = {record.id for record in records if record.state == "SUPPORTED"}
    if len(supported_ids) != 1:
        return False
    for root_cause in diagnosis.root_causes:
        if not root_cause.hypothesis_ids:
            return False
        if not set(root_cause.hypothesis_ids) <= supported_ids:
            return False
        if not root_cause.evidence_fact_ids:
            return False
        if not set(root_cause.evidence_fact_ids) <= admitted_fact_ids:
            return False
    return True


def _subject_metadata(model: str) -> dict[str, str]:
    return {
        "autofde_head": os.getenv("GITHUB_SHA", "UNKNOWN"),
        "sregym_head": os.getenv("SREGYM_SHA", "UNKNOWN"),
        "problem_id": os.getenv("PROBLEM_ID", "UNKNOWN"),
        "model_id": model,
        "signature_revision": SIGNATURE_REVISION,
    }


def _write_receipt(payload: dict) -> None:
    root = Path(os.getenv("AGENT_LOGS_DIR", "."))
    root.mkdir(parents=True, exist_ok=True)
    path = root / "autofde-sota-receipt.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


async def _refuse_diagnosis(
    broker: McpBroker,
    *,
    subject: dict[str, str],
    standing: str,
    facts: FactStore,
    trajectory: list[dict],
    detail: object | None = None,
) -> dict:
    result = {
        "subject": subject,
        "signature_revision": SIGNATURE_REVISION,
        "standing": standing,
        "facts": len(facts.facts),
        "trajectory": trajectory,
        "detail": detail,
    }
    _write_receipt(result)
    await broker.call("submit", "submit", {"ans": standing})
    return result


async def run() -> dict:
    model = os.getenv("AGENT_MODEL_ID", os.getenv("MODEL_ID", "groq/openai/gpt-oss-120b"))
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is required")
    dspy.configure(lm=dspy.LM(model, api_key=key, max_tokens=8000, cache=False))

    subject = _subject_metadata(model)
    broker = McpBroker()
    capabilities = await broker.discover()
    store = FactStore()
    await _seed_observations(broker, store, capabilities)

    program = SignatureProgram()
    goal = (
        "restore the benchmarked system to verified healthy operation by "
        "identifying and repairing the causal mechanism"
    )
    orient = program.orient(
        goal=goal,
        facts_json=_json(store.facts),
        capabilities_json=_json(capabilities),
    )

    hypotheses: list[HypothesisProposal] = []
    records: list[HypothesisRecord] = []
    trajectory: list[dict] = [
        {
            "stage": "orient",
            "focus": orient.focus,
            "capability_ids": [capability.id for capability in capabilities],
        }
    ]
    max_rounds = int(os.getenv("AUTOFDE_MAX_DISCRIMINATION_ROUNDS", "6"))
    max_process_attempts = int(os.getenv("AUTOFDE_MAX_PROCESS_CANDIDATE_ATTEMPTS", "3"))
    diagnosis: DiagnosisCandidate | None = None
    stagnant_rounds = 0

    for round_index in range(max_rounds):
        if not hypotheses:
            predicted = program.hypothesize(
                goal=goal,
                facts_json=_json(store.facts),
                prior_hypotheses_json="[]",
                max_hypotheses=6,
            )
            hypotheses = list(predicted.hypotheses)
            ids = [hypothesis.id for hypothesis in hypotheses]
            if not ids or len(ids) != len(set(ids)):
                return await _refuse_diagnosis(
                    broker,
                    subject=subject,
                    standing="REFUSED:HYPOTHESIS_IDENTITY_INVALID",
                    facts=store,
                    trajectory=trajectory,
                    detail={"ids": ids},
                )

        related = program.relate(
            facts_json=_json(store.facts),
            hypotheses_json=_json(hypotheses),
        )
        links = list(related.links)
        admitted_fact_ids = {fact.id for fact in store.facts}
        known_hypothesis_ids = {hypothesis.id for hypothesis in hypotheses}
        rejected_links = sum(
            link.hypothesis_id not in known_hypothesis_ids
            or link.fact_id not in admitted_fact_ids
            for link in links
        )
        records = compute_hypothesis_records(hypotheses, links, admitted_fact_ids)
        route = route_epistemic_state(records)
        trajectory.append(
            {
                "stage": "epistemic",
                "round": round_index,
                "route": route.value,
                "states": {h.id: h.state for h in records},
                "fact_count": len(store.facts),
                "rejected_evidence_links": rejected_links,
            }
        )

        if route is EpistemicRoute.REHYPOTHESIZE:
            hypotheses = []
            continue

        if route is EpistemicRoute.DIAGNOSIS_READY:
            candidate = program.commit(
                facts_json=_json(store.facts),
                hypotheses_json=_json(records),
            ).diagnosis
            if not _diagnosis_identity_is_admitted(candidate, records, admitted_fact_ids):
                return await _refuse_diagnosis(
                    broker,
                    subject=subject,
                    standing="REFUSED:DIAGNOSIS_IDENTITY_NOT_ADMITTED",
                    facts=store,
                    trajectory=trajectory,
                    detail=candidate.model_dump(),
                )
            challenged = program.challenge(
                diagnosis_json=_json(candidate),
                facts_json=_json(store.facts),
                hypotheses_json=_json(records),
            )
            if not challenged.obligations:
                diagnosis = candidate
                break
            obligations = list(challenged.obligations)
        else:
            obligations = list(related.obligations)

        frontier = discrimination_frontier(records)
        rejections: list[dict] = []
        evidence = None
        for candidate_attempt in range(max_process_attempts):
            proposed = program.discriminate(
                facts_json=_json(store.facts),
                hypotheses_json=_json(frontier),
                obligations_json=_json(obligations),
                capabilities_json=_json(capabilities),
                rejections_json=_json(rejections),
                max_steps=4,
            ).process
            try:
                model_powl = compile_observation_process(proposed, capabilities)
            except ProcessAdmissionError as exc:
                rejection = {
                    "candidate_attempt": candidate_attempt,
                    "kind": "PROCESS_ADMISSION",
                    "refusal": str(exc),
                    "process": proposed.model_dump(),
                }
                rejections.append(rejection)
                trajectory.append(
                    {
                        "stage": "discrimination_candidate_refused",
                        "round": round_index,
                        **rejection,
                    }
                )
                continue

            with PowlV2Runner(RunnerConfig(max_workers=4, max_attempts=1)) as runner:
                evidence = await asyncio.to_thread(
                    runner.run,
                    model_powl,
                    McpActivityDriver(broker, capabilities, allow_do=False),
                )
            if evidence.status is RunStatus.COMPLETED:
                break
            rejection = {
                "candidate_attempt": candidate_attempt,
                "kind": "PROCESS_EXECUTION",
                "status": evidence.status.value,
                "detail": evidence.detail,
                "activities": _activity_records(evidence),
                "process": proposed.model_dump(),
            }
            rejections.append(rejection)
            trajectory.append(
                {
                    "stage": "discrimination_candidate_refused",
                    "round": round_index,
                    **rejection,
                }
            )
            evidence = None

        if evidence is None:
            return await _refuse_diagnosis(
                broker,
                subject=subject,
                standing="REFUSED:DISCRIMINATION_PROCESS_NOT_ADMITTED",
                facts=store,
                trajectory=trajectory,
                detail={"rejections": rejections},
            )

        new_facts = _process_observations(evidence, store)
        trajectory.append(
            {
                "stage": "discriminate",
                "round": round_index,
                "new_facts": new_facts,
                "powl_sha256": evidence.model_sha256,
                "peak_concurrency": evidence.peak_concurrency,
                "activities": _activity_records(evidence),
            }
        )
        if new_facts == 0:
            stagnant_rounds += 1
            hypotheses = []
            trajectory.append(
                {
                    "stage": "stagnation",
                    "round": round_index,
                    "count": stagnant_rounds,
                    "action": "rehypothesize" if stagnant_rounds < 2 else "refuse",
                }
            )
            if stagnant_rounds >= 2:
                break
        else:
            stagnant_rounds = 0

    if diagnosis is None:
        return await _refuse_diagnosis(
            broker,
            subject=subject,
            standing="REFUSED:CAUSAL_CLOSURE_NOT_REACHED",
            facts=store,
            trajectory=trajectory,
        )

    await broker.call("submit", "submit", {"ans": diagnosis.explanation})
    post_diagnosis_stage = await _wait_for_stage({"mitigation", "done"})
    if post_diagnosis_stage == "done":
        result = {
            "subject": subject,
            "signature_revision": SIGNATURE_REVISION,
            "standing": "BENCHMARK_DONE_AFTER_DIAGNOSIS",
            "diagnosis": diagnosis.model_dump(),
            "facts": len(store.facts),
            "trajectory": trajectory,
        }
        _write_receipt(result)
        return result

    processes = list(
        program.mitigate(
            diagnosis_json=_json(diagnosis),
            facts_json=_json(store.facts),
            capabilities_json=_json(capabilities),
            max_processes=4,
        ).processes
    )
    ids = [process.id for process in processes]
    if not ids or len(ids) != len(set(ids)):
        mitigation_rejections = [{"refusal": "MITIGATION_PROCESS_IDENTITY_INVALID", "ids": ids}]
        admitted_mitigations = []
    else:
        mitigation_rejections: list[dict] = []
        admitted_mitigations: list[tuple[MitigationProcessProposal, object]] = []
        for process in processes:
            try:
                powl = compile_mitigation_process(process, capabilities)
            except ProcessAdmissionError as exc:
                mitigation_rejections.append(
                    {
                        "process_id": process.id,
                        "refusal": str(exc),
                        "process": process.model_dump(),
                    }
                )
            else:
                admitted_mitigations.append((process, powl))

    trajectory.append(
        {
            "stage": "mitigation_admission",
            "admitted": [process.id for process, _ in admitted_mitigations],
            "rejections": mitigation_rejections,
        }
    )
    if not admitted_mitigations:
        result = {
            "subject": subject,
            "signature_revision": SIGNATURE_REVISION,
            "standing": "REFUSED:MITIGATION_PROCESS_NOT_ADMITTED",
            "diagnosis": diagnosis.model_dump(),
            "facts": len(store.facts),
            "trajectory": trajectory,
        }
        _write_receipt(result)
        await broker.call("submit", "submit", {"ans": ""})
        return result

    selected, mitigation_powl = min(
        admitted_mitigations, key=lambda pair: _mitigation_rank(pair[0])
    )
    with PowlV2Runner(RunnerConfig(max_workers=4, max_attempts=1)) as runner:
        mitigation_evidence = await asyncio.to_thread(
            runner.run,
            mitigation_powl,
            McpActivityDriver(broker, capabilities, allow_do=True),
        )
    if mitigation_evidence.status is not RunStatus.COMPLETED:
        result = {
            "subject": subject,
            "signature_revision": SIGNATURE_REVISION,
            "standing": "REFUSED:MITIGATION_PROCESS_EXECUTION_FAILED",
            "diagnosis": diagnosis.model_dump(),
            "mitigation_process": selected.model_dump(),
            "mitigation_powl_sha256": mitigation_evidence.model_sha256,
            "facts": len(store.facts),
            "trajectory": trajectory,
            "activities": _activity_records(mitigation_evidence),
        }
        _write_receipt(result)
        await broker.call("submit", "submit", {"ans": ""})
        return result

    _process_observations(mitigation_evidence, store)
    await broker.call("submit", "submit", {"ans": ""})
    result = {
        "subject": subject,
        "signature_revision": SIGNATURE_REVISION,
        "standing": "CANDIDATE_EXECUTED",
        "diagnosis": diagnosis.model_dump(),
        "mitigation_process": selected.model_dump(),
        "mitigation_powl_sha256": mitigation_evidence.model_sha256,
        "facts": len(store.facts),
        "trajectory": trajectory,
        "mitigation_activities": _activity_records(mitigation_evidence),
    }
    _write_receipt(result)
    return result


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
