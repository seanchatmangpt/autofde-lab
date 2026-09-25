# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Statistical reporting for ALOOP benchmark results (lane 6).

Laws enforced here, not elsewhere:

* **Never a single-episode claim.** Every reported number is either pooled
  over a portfolio of logs, or a distribution over repeated trials with an
  explicit dispersion summary and, for ratio metrics, a Wilson 95% interval.
* **Deterministic trials.** A trial is derived from a seed by a stated
  formula (``iterations = BASE + seed % SPREAD``); no wall clock, no RNG, so
  every scoreboard is byte-replayable.
* **Negative controls are part of the report**, not an appendix: an episode
  with a planted post-epoch human edge must classify ASSISTED and a loop
  with severed recurrence must fail ALOOP-001, or the whole scoreboard is
  BLOCKED regardless of how good the positive numbers look.
"""

from __future__ import annotations

import json
import statistics
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from autofde_lab.aloop.metrics import (
    scoreboard,
    score_corpus,
    score_log,
    semantic_divergence,
    semantic_signature,
    wilson,
)
from autofde_lab.aloop.synth import build_positive, write_all

BASE_ITERATIONS = 101
SPREAD = 3  # iterations = BASE + seed % SPREAD per trial


# ── distributions ───────────────────────────────────────────────────────────


def summarize(values: Sequence[float | int | None]) -> dict[str, Any]:
    """Dispersion summary over repeated trials (never a single value)."""
    xs = [float(v) for v in values if v is not None]
    if not xs:
        return {"n": 0, "values": []}
    qs = statistics.quantiles(xs, n=20) if len(xs) >= 2 else [xs[0], xs[0]]
    return {
        "n": len(xs),
        "mean": statistics.fmean(xs),
        "stdev": statistics.stdev(xs) if len(xs) > 1 else 0.0,
        "min": min(xs),
        "p50": statistics.median(xs),
        "p95": qs[18],
        "max": max(xs),
        "values": xs,
    }


def summarize_ratio(k: int, n: int) -> dict[str, Any]:
    """Pooled ratio with its Wilson 95% interval."""
    interval = wilson(k, n)
    return {
        "k": k,
        "n": n,
        "value": (k / n) if n else None,
        "wilson95": list(interval) if interval else None,
    }


# ── trials ──────────────────────────────────────────────────────────────────


def trial_iterations(seed: int) -> int:
    """Deterministic loop depth for a trial seed (documented, replayable)."""
    return BASE_ITERATIONS + (seed % SPREAD)


def run_trials(seeds: Iterable[int], *, with_corpus: bool = True) -> dict[str, Any]:
    """Score one positive trial per seed + (once) the full mutant battery.

    Each trial regenerates ``build_positive(iterations=trial_iterations(seed))``
    into a private temp file and scores it cold -- real bytes on disk, real
    court verdicts, no reuse across trials. The mutant battery runs once:
    its expectations are iteration-independent, so repeating it per seed
    would buy no information.
    """
    log_scores: list[dict[str, Any]] = []
    trial_meta: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="aloop-trials-") as td:
        root = Path(td)
        for seed in seeds:
            path = root / f"trial-{seed}.ocel.json"
            from autofde_lab.aloop.ocel_builder import dump

            dump(build_positive(iterations=trial_iterations(seed)), path)
            score = score_log(path)
            score["trial"] = {"seed": seed, "iterations": trial_iterations(seed)}
            log_scores.append(score)
            trial_meta.append(
                {"seed": seed, "iterations": trial_iterations(seed),
                 "exit": score["exit"], "class": score["verdict"]}
            )
    corpus = score_corpus() if with_corpus else None
    with tempfile.TemporaryDirectory(prefix="aloop-pdr-") as pd:
        # PDR sensitivity control: the signature MUST detect a real semantic
        # change (planted post-epoch human edge) or it is insensitive. This
        # is reported as a control, never pooled into the PDR invariant
        # (which only pools provider-varied pairs of the *same* scenario).
        from autofde_lab.aloop.ocel_builder import dump
        from autofde_lab.aloop import synth as _synth

        doc = build_positive(iterations=BASE_ITERATIONS)
        _synth.m_human_after_epoch(doc)
        human_path = Path(pd) / "human-mutant.ocel.json"
        dump(doc, human_path)
        human_score = score_log(human_path)
    pdr_sensitivity = None
    sensitivity_ok = False
    if log_scores:
        d = semantic_divergence(semantic_signature(log_scores[0]), semantic_signature(human_score))
        pdr_sensitivity = {"pair": "positive-vs-human_after_epoch", "PDR": d}
        sensitivity_ok = (d or 0.0) > 0.0
    result = scoreboard(
        log_scores,
        corpus=corpus,
        pdr_pairs=[],
        provenance={
            "trials": trial_meta,
            "trial_iterations_formula": f"BASE({BASE_ITERATIONS}) + seed % {SPREAD}",
            "generator": "autofde_lab.aloop.stats.run_trials",
        },
    )
    result["pdr_sensitivity"] = pdr_sensitivity
    if result.get("negative_controls") is not None:
        result["negative_controls"]["pdr_signature_sensitivity"] = sensitivity_ok
        if sensitivity_ok and all(result["invariants"].values()) and all(result["negative_controls"].values()):
            result["standing"] = "ALIVE"
    return result


def add_stats(score: Mapping[str, Any]) -> dict[str, Any]:
    """Attach distribution/interval summaries to a scoreboard (report form)."""
    out = json.loads(json.dumps(score))  # deep copy, plain JSON
    per_log: list[dict[str, Any]] = out.get("log_results", [])
    stats: dict[str, Any] = {}
    for name in ("HIR", "ALD", "LCR", "RR", "UAR", "PSR", "CRR", "OCR", "DCR", "RPR"):
        stats[name] = {
            "pooled": out["metrics"].get(name),
            "wilson95": out["metrics"].get(f"{name}_wilson95"),
            "across_logs": summarize([s["metrics"].get(name) for s in per_log]),
        }
    mkr = out["metrics"].get("MKR")
    stats["MKR"] = {
        "pooled": mkr,
        "wilson95": out["metrics"].get("MKR_wilson95"),
        "across_logs": None,
    }
    out["statistics"] = stats
    out["reporting_law"] = (
        "no single-episode claims: pooled ratios carry Wilson 95% intervals; "
        "ALD is reported as a distribution over seed-varied trials"
    )
    return out
