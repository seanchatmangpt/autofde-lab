#!/usr/bin/env python3
"""Build the Crown-2 durable evidence bundle and gate it.

Source (integration worktree, never mutated):
    /Users/sac/crown-2-integration/{CompositionReceipt.json,*.log}
    /Users/sac/crown-2-integration/autofde-lab/tools/crown2/{run,native,falsify}
Destination (canonical autofde-lab checkout, docs only, written not committed):
    /Users/sac/autofde-lab/docs/evidence/crown2/attempt1/
    /Users/sac/autofde-lab/docs/evidence/crown2/crown_manifest.json
    /Users/sac/autofde-lab/docs/evidence/crown2/crown_run.json

Every artifact is a NEW file. Digests are recomputed from the durable copy and
the whole bundle is run through evidence_gate.gate_bundle; standing is issued
only if every artifact resolves.

Run: python3 tools/crown2/durability/build_bundle.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import evidence_gate as eg  # noqa: E402

INTEG = "/Users/sac/crown-2-integration"
LAB = os.path.join(INTEG, "autofde-lab")
C2 = os.path.join(LAB, "tools", "crown2")
DEST_ROOT = "/Users/sac/autofde-lab/docs/evidence/crown2"
ATTEMPT = os.path.join(DEST_ROOT, "attempt1")
COMPOSED_PRS = [
    {"repo": "beam4pm", "pr": 47, "head": "baf4a73a56e42e29defac247147a4f45bf4677e8", "title": "fix(submodules): register native/ferroplan in .gitmodules"},
    {"repo": "autofde-lab", "pr": 103, "head": "add8fba6d9cbb567c3bdf4953ddfb42774d5ca58", "title": "fix: auto-init cpp/sdk/* git submodules during CMake configure"},
    {"repo": "autofde-lab", "pr": None, "head": "4278b151", "title": "fix(cpp): drop unused pybind11 include from skdecide_pddl (Task B fix commit, local branch only)"},
]


def _load(p: str):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _dump(p: str, obj) -> None:
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


def _copy(src: str, name: str) -> str:
    dst = os.path.join(ATTEMPT, name)
    shutil.copyfile(src, dst)
    return dst


def _receipt_with_digest(src: str, dst: str) -> dict:
    receipt = _load(src)
    receipt.pop("receipt_sha256", None)
    digest = eg.sha256_bytes(eg.canonical_json(receipt))
    receipt["receipt_sha256"] = digest
    _dump(dst, receipt)
    reread = _load(dst)
    claimed = reread.pop("receipt_sha256")
    recomputed = eg.sha256_bytes(eg.canonical_json(reread))
    return {"written": digest, "reread_claimed": claimed, "recomputed": recomputed,
            "match": claimed == recomputed == digest}


def _mix_summary(log: str) -> str | None:
    last = None
    with open(log, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if " tests, " in ln and " failures" in ln:
                last = ln.strip()
    return last


def _report(ctx: dict) -> str:
    f = ctx["falsifier"]
    t = ctx["timing"]
    v = ctx["validation"]
    lines = [
        "# Crown-2 Report (attempt1)",
        "",
        f"Generated {ctx['generated_utc']} by tools/crown2/durability/build_bundle.py. Facts only; status",
        "vocabulary ALIVE/PARTIAL/BLOCKED/REFUSED/UNVERIFIED. Every path cited is inside this bundle",
        "and passed the evidence durability gate (evidence-gate-result.json).",
        "",
        "## Composition",
        "",
        f"- CompositionReceipt receipt_sha256 = `{ctx['receipt_digest']['written']}` "
        f"(reread+recomputed MATCH={ctx['receipt_digest']['match']})",
        "- beam4pm: canonical 6fb0992d -> PR #47 head baf4a73a -> composed d21838c0 (local branch, never pushed)",
        "- autofde-lab: canonical e5c4aef7 -> PR #103 head add8fba6 -> composed 1d11067a -> "
        "4278b151 (Task B pybind11 fix) -> e950e155 (native bootstrap reprove)",
        "",
        "## Run facts (crown-run-v3.ocel.json)",
        "",
        f"- events={t['events']} objects={t['objects']} elapsed_monotonic_s={t['elapsed_monotonic_seconds']:.3f} "
        f"floor_s={t['floor_seconds']}",
        f"- validate (durable copy): crown-run-v3={json.dumps(v['crown-run-v3.ocel.json'], sort_keys=True)}",
        f"- validate (durable copy): native-bootstrap={json.dumps(v['native-bootstrap.ocel.json'], sort_keys=True)}",
        f"- counts: {json.dumps(t['counts'], sort_keys=True)}",
        f"- native planner: {json.dumps(t['native_planner'], sort_keys=True)}",
        "",
        "## Falsifier verdict (falsifier-result.json)",
        "",
        f"- global_status: `{f['global_status']}`  failed_gates={f['failed_gates']}",
    ]
    for k, c in sorted(f["closures"].items()):
        lines.append(f"- {k}: `{c['status']}`")
        for n in c.get("notes", [])[:4]:
            lines.append(f"    - {n[:160]}")
    lines += [
        "",
        "## Staged transitions closed by the composed PRs (from receipts only)",
        "",
        "| Transition | Closed by | Evidence |",
        "| --- | --- | --- |",
        "| SUBMODULES_READY (beam4pm native/ferroplan registered) | PR #47 | CompositionReceipt.components[0] |",
        "| SUBMODULES_READY (autofde cpp/sdk/* auto-init at configure) | PR #103 | autofde-cmake-configure.log |",
        "| NATIVE_SOLVER_BUILDABLE (pybind11 include wiring) | commit 4278b151 (Task B, local) | autofde-cmake-build.log:2178 was the failure; native-bootstrap.ocel.json ev:bootstrap-completed ok=True after fix |",
        "| ELIXIR_DEPS_READY false->true | mix deps.get (pre-fleet) | beam4pm-mixdeps.log EXIT:0 |",
        "| NATIVE_ORACLES_BUILT false->true | action:001:01 cargo build --release | run-logs/action-001-01-cargo.log, ev:action-completed:00011 |",
        "| ORACLE_ENV_SET false->true | action:001:02 set oracle env | run-logs/action-001-02-set.log, ev:action-completed:00021 |",
        f"| MIX_TEST_GREEN false->true | action:001:03 mix test | run-logs/beam4pm-verify2.log: `{ctx['mix_run']}` (ev:observed:00032) |",
        "",
        "Pre-fleet baseline for the same suite (before oracles were built/bound): "
        f"beam4pm-verify2.log: `{ctx['mix_prefleet']}`. The 18 failures were RF3_ORACLE_BIN-unset and "
        "rf1-dfg-oracle-binary-missing; both predicates were closed by actions 001:01/001:02 above, and "
        "prediction_matches=3/3 (PredictionCompared delta={} on every action).",
        "",
        "## PR merge-order recommendation (derived only from receipts)",
        "",
        "1. beam4pm PR #47 — exercised; closes ferroplan submodule registration; no conflicts recorded "
        "(merge --no-ff clean). Standing: PARTIAL (LAB_PROVEN on local compose branch, not on default branch).",
        "2. autofde-lab PR #103 — exercised; closes cpp/sdk/* auto-init; configure completed in 409s. "
        "Standing: PARTIAL (LAB_PROVEN). Must land BEFORE the Task B fix commit, which builds on it.",
        "3. autofde-lab commit 4278b151 (Task B) — not a PR yet; needed for native solver build "
        "(skdecide_pddl pybind11 include). Standing: PARTIAL; open a PR on top of #103.",
        "",
        "Of the 7 backlog PRs named in CompositionReceipt.backlog_status, only #47 and #103 were composed and "
        "exercised. The other 5 were NOT exercised and have NO standing from this crown (UNVERIFIED).",
        "",
        "## Staged transitions still open / gates still failing",
        "",
        f"- control_invariant: heartbeat span {f['closures']['control_invariant']['notes'][1]} — "
        "BLOCKED[HEARTBEAT_SPAN_LT_300S] (elapsed 299.977s < 300s floor by 0.023s; runner's first/last "
        "heartbeat timestamps, not wall clock, define the span).",
        "- planner_loop: BLOCKED[NO_TYPED_REFUSAL_PATH] — 0 PlanRefused/GapDiagnosed/AuthorityRefused events; "
        "the run only exercised the happy path, so refusal typing is UNVERIFIED.",
        "- native_bootstrap: BLOCKED[SOLVER_IMPLEMENTATION_ATTR_MISSING] — solver object carries "
        "kind=cpp:_AStarSolver_ but implementation=None; the falsifier requires implementation=native.",
        "- MIX_TEST_GREEN: closed in-run (0 failures) but only under the run's env (RF*_ORACLE_BIN set); "
        "92 tests still skipped; not green from a clean shell.",
        "- Nothing in this crown is merged to any default branch (backlog_status).",
        "",
        "## Lawful next actions discovered",
        "",
        "- Raise runner heartbeat floor so heartbeat_span >= 300s (emit final heartbeat after the floor).",
        "- Add a deliberate refused-plan probe (an action lacking authority) so PlanRefused/AuthorityRefused "
        "events exist and the typed refusal path can be falsified.",
        "- Emit `implementation=native` on solver objects in native/bootstrap.py (emitter attribute), re-run.",
        "- Persist oracle env into beam4pm's mix config or a checked-in .env so MIX_TEST_GREEN holds from a clean shell.",
        "- Open a PR for 4278b151 against autofde-lab, stacked on #103.",
        "",
        "## Evidence gate",
        "",
        f"- standing: `{ctx['gate_standing']}` ({ctx['gate_resolved']}/{ctx['gate_total']} artifacts resolved)",
        "- rule: identity + durable path + sha256 match + parser success, else "
        "REFUSED[EVIDENCE_ARTIFACT_UNRESOLVABLE:<check>] (tools/crown2/durability/evidence_gate.py)",
        "- the never-located crown-run-v2.ocel.json resolves to REFUSED[...:identity]; it is cited nowhere as evidence.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    if os.path.isdir(ATTEMPT) and os.listdir(ATTEMPT):
        print(f"REFUSED[BUNDLE_EXISTS]: {ATTEMPT} is non-empty; attempts are immutable", file=sys.stderr)
        return 3
    os.makedirs(ATTEMPT, exist_ok=True)
    os.makedirs(os.path.join(ATTEMPT, "run-logs"), exist_ok=True)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    files: dict[str, tuple[str, str]] = {}  # name -> (durable path, parser)

    receipt_dst = os.path.join(ATTEMPT, "composition-receipt.json")
    receipt_digest = _receipt_with_digest(os.path.join(INTEG, "CompositionReceipt.json"), receipt_dst)
    files["composition-receipt.json"] = (receipt_dst, "json")

    run_dst = _copy(os.path.join(C2, "run", "crown-run-v3.ocel.json"), "crown-run-v3.ocel.json")
    files["crown-run-v3.ocel.json"] = (run_dst, "ocel")
    run_sha = eg.sha256_file(run_dst)
    sha_dst = os.path.join(ATTEMPT, "crown-run-v3.sha256")
    with open(sha_dst, "w", encoding="utf-8") as fh:
        fh.write(f"{run_sha}  crown-run-v3.ocel.json\n")
    files["crown-run-v3.sha256"] = (sha_dst, "sha256")

    nb_dst = _copy(os.path.join(C2, "native", "native-bootstrap.ocel.json"), "native-bootstrap.ocel.json")
    files["native-bootstrap.ocel.json"] = (nb_dst, "ocel")

    sys.path.insert(0, os.path.join(LAB, "tools", "ocel_v2"))
    import validate as ocel_validate  # noqa: E402

    validation = {
        "crown-run-v3.ocel.json": ocel_validate.validate(_load(run_dst)),
        "native-bootstrap.ocel.json": ocel_validate.validate(_load(nb_dst)),
        "validator": "tools/ocel_v2/validate.py",
        "validated_from": "durable copies in attempt1/",
        "generated_utc": generated,
    }
    val_dst = os.path.join(ATTEMPT, "crown-validation.json")
    _dump(val_dst, validation)
    files["crown-validation.json"] = (val_dst, "json")

    for name in ("timing-receipt.json",):
        files[name] = (_copy(os.path.join(C2, "run", name), name), "json")
    files["falsifier-result.json"] = (_copy(os.path.join(C2, "falsify", "falsifier-result.json"), "falsifier-result.json"), "json")

    for name in sorted(os.listdir(INTEG)):
        if name.endswith(".log") and (name.startswith("beam4pm-") or name.startswith("autofde-cmake-")):
            files[name] = (_copy(os.path.join(INTEG, name), name), "text")
    for name in sorted(os.listdir(os.path.join(C2, "run", "logs"))):
        dst = os.path.join(ATTEMPT, "run-logs", name)
        shutil.copyfile(os.path.join(C2, "run", "logs", name), dst)
        files["run-logs/" + name] = (dst, "text")

    timing = _load(os.path.join(C2, "run", "timing-receipt.json"))
    falsifier = _load(os.path.join(C2, "falsify", "falsifier-result.json"))

    # Gate everything so far; the report cites the gate result, then the report
    # itself is gated in a second pass so the receipt covers it too.
    refs = [{"name": n, "path": p, "sha256": eg.sha256_file(p), "parser": parser} for n, (p, parser) in files.items()]
    pre = eg.gate_bundle(refs)

    ctx = {
        "generated_utc": generated,
        "receipt_digest": receipt_digest,
        "timing": timing,
        "falsifier": falsifier,
        "validation": validation,
        "mix_run": _mix_summary(files["run-logs/beam4pm-verify2.log"][0]),
        "mix_prefleet": _mix_summary(files["beam4pm-verify2.log"][0]),
        "gate_standing": pre["standing"],
        "gate_resolved": pre["resolved"],
        "gate_total": pre["artifacts"],
    }
    rep_dst = os.path.join(ATTEMPT, "crown-report.md")
    with open(rep_dst, "w", encoding="utf-8") as fh:
        fh.write(_report(ctx))
    files["crown-report.md"] = (rep_dst, "markdown")

    refs = [{"name": n, "path": p, "sha256": eg.sha256_file(p), "parser": parser} for n, (p, parser) in files.items()]
    gate = eg.gate_bundle(refs)
    gate["generated_utc"] = generated
    gate["receipt_sha256_proof"] = receipt_digest
    gate_dst = os.path.join(ATTEMPT, "evidence-gate-result.json")
    _dump(gate_dst, gate)
    _dump(os.path.join(_HERE, "evidence-gate-result.json"), gate)

    artifacts = [{"name": n, "bytes": os.path.getsize(p), "sha256": eg.sha256_file(p), "parser": parser}
                 for n, (p, parser) in sorted(files.items())]
    artifacts.append({"name": "evidence-gate-result.json", "bytes": os.path.getsize(gate_dst),
                      "sha256": eg.sha256_file(gate_dst), "parser": "json"})
    manifest = {
        "crown_id": "crown-2",
        "components": [{k: c[k] for k in ("repo", "pr_number", "pr_head_sha", "canonical_base_sha", "composed_head_sha")}
                       for c in _load(receipt_dst)["components"]],
        "composed_prs": COMPOSED_PRS,
        "actions": [a["name"] for a in [
            {"name": "cargo build --release (oracles)"}, {"name": "set oracle env"}, {"name": "mix test"}]],
        "gates": [g["gate"] for g in falsifier["global_gates"]],
        "artifacts": artifacts,
        "attempt_dirs": ["attempt1"],
    }
    manifest["manifest_digest"] = eg.sha256_bytes(eg.canonical_json(manifest))
    _dump(os.path.join(DEST_ROOT, "crown_manifest.json"), manifest)

    gates = falsifier["global_gates"]
    crown_run = {
        "manifest_digest": manifest["manifest_digest"],
        "denominator": len(gates),
        "attempts": [{
            "attempt_index": 1,
            "repair_note": "",
            "alive": sum(1 for g in gates if g["passed"]),
            "results": [{"gate": g["gate"], "passed": g["passed"],
                         "status": "ALIVE" if g["passed"] else falsifier["closures"].get(g["gate"], {}).get("status", "BLOCKED")}
                        for g in gates],
            "evidence_dir": ATTEMPT,
            "evidence_gate_standing": gate["standing"],
            "global_status": falsifier["global_status"],
        }],
        "history": [f"attempt 1: {sum(1 for g in gates if g['passed'])}/{len(gates)} gates passed; evidence gate {gate['standing']}"],
        "complete": False,
    }
    _dump(os.path.join(DEST_ROOT, "crown_run.json"), crown_run)

    print(json.dumps({"receipt_sha256_proof": receipt_digest, "gate_standing": gate["standing"],
                      "resolved": gate["resolved"], "artifacts": gate["artifacts"],
                      "unresolved": gate["unresolved"], "manifest_digest": manifest["manifest_digest"]}, indent=2))
    return 0 if not gate["unresolved"] else 1


if __name__ == "__main__":
    sys.exit(main())
