"""Compile historical engineering events into replayable software-manufacturing plans.

The compiler treats GitHub/software-delivery history as observation evidence, not as
authority. It preserves the reported August 2026 commit total separately from the
number of commit events actually present in an export so an incomplete export can
never silently masquerade as the historical corpus.

Replay is simulation-only. A replay world exposes admissible plan steps, records
agent selections, and emits a deterministic simulation receipt. It cannot push,
merge, deploy, apply infrastructure, send messages, or acquire external authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

PLAN_SCHEMA = "urn:autofde-lab:software-manufacturing-plan:1"
CORPUS_SCHEMA = "urn:autofde-lab:software-manufacturing-corpus:1"
REPLAY_SCHEMA = "urn:autofde-lab:software-manufacturing-replay:1"

_GITHUB_KINDS = {
    "branch",
    "branch_created",
    "commit",
    "default_branch_containment",
    "issue",
    "merge",
    "pull_request",
    "release",
    "review",
    "workflow_run",
}
_CLOSURE_KINDS = {"merge", "release", "default_branch_containment"}
_PATH_SURFACE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("tests", re.compile(r"(^|/)(tests?|specs?)(/|$)|(^|/)test_[^/]+\.py$")),
    (
        "ci_cd",
        re.compile(
            r"(^|/)\.github/workflows/|jenkins|circleci|buildkite|"
            r"gitlab-ci|(^|/)ci(/|$)"
        ),
    ),
    (
        "iac",
        re.compile(
            r"\.tf$|terraform|cloudformation|crossplane|pulumi|"
            r"(^|/)iac(/|$)|(^|/)infra(structure)?(/|$)"
        ),
    ),
    (
        "container",
        re.compile(
            r"(^|/)dockerfile$|docker-compose|compose\.ya?ml$|"
            r"(^|/)helm(/|$)|(^|/)k8s(/|$)|(^|/)kubernetes(/|$)"
        ),
    ),
    (
        "docs",
        re.compile(r"(^|/)docs?(/|$)|readme|agents\.md$|(^|/)book(/|$)|mdbook"),
    ),
    (
        "security",
        re.compile(
            r"security|iam|rbac|policy|policies|guardrail|opa|shacl|"
            r"provenance|supply-chain|sbom"
        ),
    ),
    (
        "observability",
        re.compile(
            r"otel|opentelemetry|observability|telemetry|metrics|tracing|"
            r"logging|prometheus|grafana"
        ),
    ),
    (
        "cloud",
        re.compile(r"aws|azure|gcp|google-cloud|cloudrun|sagemaker|vertex"),
    ),
    (
        "release",
        re.compile(
            r"release|publish|package|packaging|pypi|crates\.io|npm|ghcr|artifact"
        ),
    ),
)
_SOURCE_PATH = re.compile(
    r"(^|/)(src|app|apps|lib|libs|crates|packages|services|cmd|internal)(/|$)"
)


def canonical_digest(value: object) -> str:
    """Return a deterministic SHA-256 over canonical JSON."""

    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text[:64] or "step"


@dataclass(frozen=True, slots=True)
class HistoricalEvent:
    """One normalized observation from GitHub or an adjacent delivery surface."""

    event_id: str
    timestamp: str
    repository: str
    kind: str
    ref: str = ""
    sha: str = ""
    parent_ids: tuple[str, ...] = ()
    changed_paths: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "HistoricalEvent":
        required = ("event_id", "timestamp", "repository", "kind")
        missing = [key for key in required if not value.get(key)]
        if missing:
            raise ValueError(f"historical event missing required fields: {missing}")
        metadata = value.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("historical event metadata must be an object")
        return cls(
            event_id=str(value["event_id"]),
            timestamp=str(value["timestamp"]),
            repository=str(value["repository"]),
            kind=str(value["kind"]),
            ref=str(value.get("ref", "")),
            sha=str(value.get("sha", "")),
            parent_ids=tuple(str(item) for item in value.get("parent_ids", ())),
            changed_paths=tuple(str(item) for item in value.get("changed_paths", ())),
            labels=tuple(str(item) for item in value.get("labels", ())),
            metadata=dict(metadata),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "repository": self.repository,
            "kind": self.kind,
            "ref": self.ref,
            "sha": self.sha,
            "parent_ids": list(self.parent_ids),
            "changed_paths": list(self.changed_paths),
            "labels": list(self.labels),
            "metadata": dict(self.metadata),
        }


def infer_surfaces(event: HistoricalEvent) -> tuple[str, ...]:
    """Infer engineering surfaces without making them authority claims."""

    surfaces: set[str] = set()
    explicit = event.metadata.get("surfaces", ())
    if isinstance(explicit, Sequence) and not isinstance(explicit, (str, bytes)):
        surfaces.update(str(item) for item in explicit)

    if event.kind in _GITHUB_KINDS:
        surfaces.add("github")
    if event.kind == "release":
        surfaces.add("release")

    message = str(event.metadata.get("message", ""))
    ambient_text = " ".join(
        (event.kind, event.ref, message, " ".join(event.labels))
    ).lower()
    paths = tuple(path.lower() for path in event.changed_paths)
    for surface, pattern in _PATH_SURFACE_PATTERNS:
        if pattern.search(ambient_text) or any(pattern.search(path) for path in paths):
            surfaces.add(surface)

    if event.kind == "commit" and any(
        _SOURCE_PATH.search(path.lower()) for path in event.changed_paths
    ):
        surfaces.add("source")
    if not surfaces:
        surfaces.add("other")
    return tuple(sorted(surfaces))


def infer_intent(event: HistoricalEvent) -> str:
    """Infer a compact plan-step intent from normalized history."""

    explicit = event.metadata.get("intent")
    if explicit:
        return str(explicit)
    message = str(event.metadata.get("message", "")).strip()
    if message:
        head = message.splitlines()[0]
        conventional = re.match(
            r"^(feat|fix|test|docs|ci|build|refactor|perf|chore)"
            r"(?:\([^)]+\))?!?:\s*(.+)$",
            head,
            flags=re.IGNORECASE,
        )
        if conventional:
            return f"{conventional.group(1).lower()}:{conventional.group(2)}"
        return head
    return event.kind.replace("_", "-")


def _episode_key(event: HistoricalEvent) -> str:
    explicit = event.metadata.get("episode") or event.metadata.get("workstream")
    if explicit:
        return str(explicit)
    pr_number = event.metadata.get("pull_request")
    if pr_number:
        return f"{event.repository}:pr-{pr_number}"
    if event.ref:
        return f"{event.repository}:{event.ref}"
    return f"{event.repository}:default"


@dataclass(slots=True)
class _MutableStep:
    step_id: str
    kind: str
    intent: str
    surfaces: tuple[str, ...]
    event_ids: list[str]
    commit_shas: list[str]
    required_authority_classes: set[str]
    dependencies: set[str] = field(default_factory=set)

    @property
    def signature(self) -> tuple[str, str, tuple[str, ...]]:
        return self.kind, self.intent, self.surfaces

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.step_id,
            "kind": self.kind,
            "intent": self.intent,
            "surfaces": list(self.surfaces),
            "count": len(self.event_ids),
            "source_event_ids": list(self.event_ids),
            "commit_shas": list(self.commit_shas),
            "depends_on": sorted(self.dependencies),
            "required_authority_classes": sorted(self.required_authority_classes),
        }


def _authority_classes(event: HistoricalEvent) -> set[str]:
    explicit = event.metadata.get("required_authority_classes", ())
    if isinstance(explicit, Sequence) and not isinstance(explicit, (str, bytes)):
        return {str(item) for item in explicit}
    if event.kind in {"merge", "pull_request", "review", "branch"}:
        return {"github:write"}
    if event.kind == "release":
        return {"release:publish"}
    if event.kind == "deployment":
        return {"deployment:write"}
    if "iac" in infer_surfaces(event):
        return {"infrastructure:write"}
    return set()


def _build_plan(
    episode_id: str,
    events: Sequence[HistoricalEvent],
    *,
    period: str,
    compact: bool,
) -> dict[str, object]:
    ordered = sorted(events, key=lambda item: (item.timestamp, item.event_id))
    steps: list[_MutableStep] = []
    event_to_step: dict[str, str] = {}

    for event in ordered:
        surfaces = infer_surfaces(event)
        intent = infer_intent(event)
        signature = (event.kind, intent, surfaces)
        if compact and steps and steps[-1].signature == signature:
            step = steps[-1]
            step.event_ids.append(event.event_id)
            if event.sha and event.kind == "commit":
                step.commit_shas.append(event.sha)
            step.required_authority_classes.update(_authority_classes(event))
        else:
            step = _MutableStep(
                step_id=f"s{len(steps):05d}-{_slug(intent)}",
                kind=event.kind,
                intent=intent,
                surfaces=surfaces,
                event_ids=[event.event_id],
                commit_shas=(
                    [event.sha] if event.sha and event.kind == "commit" else []
                ),
                required_authority_classes=_authority_classes(event),
            )
            steps.append(step)
        event_to_step[event.event_id] = step.step_id

    step_by_id = {step.step_id: step for step in steps}
    for index, event in enumerate(ordered):
        step_id = event_to_step[event.event_id]
        step = step_by_id[step_id]
        causal_ids = tuple(event.parent_ids)
        metadata_depends = event.metadata.get("depends_on", ())
        if isinstance(metadata_depends, Sequence) and not isinstance(
            metadata_depends, (str, bytes)
        ):
            causal_ids += tuple(str(item) for item in metadata_depends)

        causal_steps = {
            event_to_step[item]
            for item in causal_ids
            if item in event_to_step and event_to_step[item] != step_id
        }
        if causal_steps:
            step.dependencies.update(causal_steps)
        elif index:
            previous = event_to_step[ordered[index - 1].event_id]
            if previous != step_id:
                step.dependencies.add(previous)

    surface_counts: Counter[str] = Counter()
    for event in ordered:
        surface_counts.update(infer_surfaces(event))

    commit_shas = [
        event.sha for event in ordered if event.kind == "commit" and event.sha
    ]
    event_payload = [event.as_dict() for event in ordered]
    objective = next(
        (
            str(event.metadata["objective"])
            for event in ordered
            if event.metadata.get("objective")
        ),
        f"replay:{episode_id}",
    )
    repositories = sorted({event.repository for event in ordered})
    closure_expected = any(event.kind in _CLOSURE_KINDS for event in ordered)

    payload: dict[str, object] = {
        "schema": PLAN_SCHEMA,
        "episode": {
            "id": episode_id,
            "objective": objective,
            "period": period,
            "repositories": repositories,
        },
        "world": {
            "source_event_count": len(ordered),
            "observed_commit_count": sum(event.kind == "commit" for event in ordered),
            "closure_expected": closure_expected,
        },
        "roles": [
            "planner",
            "implementer",
            "verifier",
            "ci-repair",
            "github-controller",
            "iac-operator",
            "release-controller",
        ],
        "surfaces": dict(sorted(surface_counts.items())),
        "plan": {
            "type": "partial-order",
            "steps": [step.as_dict() for step in steps],
            "edges": sorted(
                [dependency, step.step_id]
                for step in steps
                for dependency in step.dependencies
            ),
        },
        "historical_trace": {
            "event_ids": [event.event_id for event in ordered],
            "commit_shas": commit_shas,
            "event_digest": canonical_digest(event_payload),
        },
        "authority": {
            "mode": "SIMULATION_ONLY",
            "do_authority": False,
            "required_classes_are_descriptive": True,
        },
    }
    payload["plan_digest"] = canonical_digest(payload)
    return payload


def compile_history(
    events: Iterable[HistoricalEvent],
    *,
    period: str,
    reported_commit_count: int | None = None,
    compact: bool = True,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    """Compile normalized observations into a deterministic planning corpus."""

    event_tuple = tuple(events)
    grouped: dict[str, list[HistoricalEvent]] = defaultdict(list)
    for event in event_tuple:
        grouped[_episode_key(event)].append(event)

    plans = tuple(
        _build_plan(
            episode_id,
            grouped[episode_id],
            period=period,
            compact=compact,
        )
        for episode_id in sorted(grouped)
    )
    observed_commit_count = sum(event.kind == "commit" for event in event_tuple)
    surface_counts: Counter[str] = Counter()
    for event in event_tuple:
        surface_counts.update(infer_surfaces(event))

    manifest: dict[str, object] = {
        "schema": CORPUS_SCHEMA,
        "period": period,
        "reported_commit_count": reported_commit_count,
        "observed_commit_count": observed_commit_count,
        "complete_history_observed": (
            reported_commit_count is not None
            and reported_commit_count == observed_commit_count
        ),
        "source_event_count": len(event_tuple),
        "episode_count": len(plans),
        "repositories": sorted({event.repository for event in event_tuple}),
        "surfaces": dict(sorted(surface_counts.items())),
        "source_digest": canonical_digest(
            [
                event.as_dict()
                for event in sorted(
                    event_tuple,
                    key=lambda item: (
                        item.repository,
                        item.timestamp,
                        item.event_id,
                    ),
                )
            ]
        ),
        "plan_digests": [plan["plan_digest"] for plan in plans],
        "authority": {
            "mode": "SIMULATION_ONLY",
            "do_authority": False,
        },
    }
    manifest["corpus_digest"] = canonical_digest(manifest)
    return manifest, plans


@dataclass(slots=True)
class ReplayWorld:
    """Powerless execution gym over one software-manufacturing planning file."""

    plan: Mapping[str, object]
    completed: list[str] = field(default_factory=list)
    transitions: list[dict[str, object]] = field(default_factory=list)

    def _steps(self) -> tuple[Mapping[str, object], ...]:
        plan_section = self.plan.get("plan")
        if not isinstance(plan_section, Mapping):
            raise ValueError("planning file missing plan object")
        raw_steps = plan_section.get("steps")
        if not isinstance(raw_steps, list):
            raise ValueError("planning file missing plan.steps array")
        return tuple(step for step in raw_steps if isinstance(step, Mapping))

    def admissible_actions(self) -> tuple[str, ...]:
        """Return plan-step ids whose declared dependencies are satisfied."""

        completed = set(self.completed)
        ready: list[str] = []
        for step in self._steps():
            step_id = str(step["id"])
            dependencies = {str(item) for item in step.get("depends_on", ())}
            if step_id not in completed and dependencies.issubset(completed):
                ready.append(step_id)
        return tuple(sorted(ready))

    def apply(self, step_id: str, *, agent: str = "reference-agent") -> None:
        """Apply one simulated action; no external side effect is possible."""

        ready = set(self.admissible_actions())
        if step_id not in ready:
            raise ValueError(
                f"step is not admissible in the current replay state: {step_id}"
            )
        self.completed.append(step_id)
        self.transitions.append(
            {
                "index": len(self.transitions),
                "agent": agent,
                "step_id": step_id,
            }
        )

    def run_reference(self) -> dict[str, object]:
        """Deterministically execute the first admissible action until closure."""

        step_count = len(self._steps())
        while len(self.completed) < step_count:
            ready = self.admissible_actions()
            if not ready:
                raise RuntimeError("planning file contains a dependency deadlock")
            self.apply(ready[0])
        return self.receipt()

    def receipt(self) -> dict[str, object]:
        """Return deterministic replay evidence for the simulated trajectory."""

        step_ids = {str(step["id"]) for step in self._steps()}
        state = "ALIVE" if set(self.completed) == step_ids else "PARTIAL_ALIVE"
        payload: dict[str, object] = {
            "schema": REPLAY_SCHEMA,
            "plan_digest": self.plan.get("plan_digest", ""),
            "state": state,
            "completed_steps": list(self.completed),
            "transitions": list(self.transitions),
            "authority": "NONE",
            "do_authority": False,
            "evidence_kind": "SIMULATION_RECEIPT",
        }
        payload["receipt_sha256"] = canonical_digest(payload)
        return payload


def load_events(path: Path) -> tuple[HistoricalEvent, ...]:
    """Load either a JSON array or an object containing an ``events`` array."""

    raw = json.loads(path.read_text())
    if isinstance(raw, Mapping):
        raw = raw.get("events")
    if not isinstance(raw, list):
        raise ValueError("history export must be a JSON array or {events: [...]}")
    return tuple(
        HistoricalEvent.from_mapping(item) for item in raw if isinstance(item, Mapping)
    )


def write_corpus(
    output_dir: Path,
    manifest: Mapping[str, object],
    plans: Sequence[Mapping[str, object]],
) -> tuple[Path, ...]:
    """Write deterministic planning files and return all created paths."""

    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    created.append(manifest_path)

    for plan in plans:
        episode = plan.get("episode")
        if not isinstance(episode, Mapping):
            raise ValueError("planning file missing episode")
        episode_id = _slug(str(episode.get("id", "episode")))
        path = output_dir / f"{episode_id}.plan.json"
        path.write_text(json.dumps(plan, sort_keys=True, indent=2) + "\n")
        created.append(path)
    return tuple(created)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile and replay software-manufacturing history."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("history", type=Path)
    compile_parser.add_argument("output", type=Path)
    compile_parser.add_argument("--period", required=True)
    compile_parser.add_argument("--reported-commit-count", type=int)
    compile_parser.add_argument("--no-compact", action="store_true")

    replay_parser = subparsers.add_parser("replay")
    replay_parser.add_argument("plan", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if args.command == "compile":
        events = load_events(args.history)
        manifest, plans = compile_history(
            events,
            period=args.period,
            reported_commit_count=args.reported_commit_count,
            compact=not args.no_compact,
        )
        created = write_corpus(args.output, manifest, plans)
        print(
            json.dumps(
                {
                    "corpus_digest": manifest["corpus_digest"],
                    "created": [str(path) for path in created],
                    "observed_commit_count": manifest["observed_commit_count"],
                    "reported_commit_count": manifest["reported_commit_count"],
                },
                sort_keys=True,
                indent=2,
            )
        )
        return

    plan = json.loads(args.plan.read_text())
    receipt = ReplayWorld(plan).run_reference()
    print(json.dumps(receipt, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
