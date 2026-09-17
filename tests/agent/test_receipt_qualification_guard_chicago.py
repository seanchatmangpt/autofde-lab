# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Chicago suite closing AFDE-2603 (docs/jira/v26.9.15): a receipt's
qualification expires whenever the subject head moves.

Falsifier from the ticket: commit any change on top of a qualified receipt
without re-qualifying it -- the receipt's current-standing claim must be
refused/downgraded automatically by the guard, with the mismatch surfaced
(not silently retained as green).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autofde_lab.agent.receipt_qualification import (
    VERDICT_EXPIRED_POINT_IN_TIME,
    VERDICT_QUALIFIED,
    VERDICT_REFUSED_STALE,
    VERDICT_REFUSED_UNANCHORED,
    evaluate_receipt_document,
    resolve_current_head,
    verify_repo_receipts,
)
from autofde_lab.agent.receipt_qualification import (
    main as guard_main,
)

_CURRENT = "a" * 40
_OTHER = "b" * 40


def _write(tmp_path: Path, body: str) -> Path:
    doc = tmp_path / "receipt-test.md"
    doc.write_text(body, encoding="utf-8")
    return doc


class TestAFDE2603QualificationExpiry:
    def test_fresh_receipt_with_current_head_qualifies(self, tmp_path):
        doc = _write(
            tmp_path,
            "# Receipt\n\n- **Exact Head Commit**: `" + _CURRENT + "`\n"
            "- **Final Standing**: `ALIVE`\n",
        )
        verdict = evaluate_receipt_document(doc, _CURRENT)
        assert verdict.verdict == VERDICT_QUALIFIED

    def test_stale_receipt_claiming_current_standing_is_refused(self, tmp_path):
        """The ticket's falsifier: head moved, receipt still says ALIVE."""
        doc = _write(
            tmp_path,
            "# Receipt\n\n- **Exact Head Commit**: `" + _OTHER + "`\n"
            "- **Final Standing**: `ALIVE`\n",
        )
        verdict = evaluate_receipt_document(doc, _CURRENT)
        assert verdict.verdict == VERDICT_REFUSED_STALE
        assert _OTHER[:12] in verdict.detail
        assert _CURRENT[:12] in verdict.detail

    def test_stale_receipt_with_green_prose_claim_is_refused(self, tmp_path):
        """The episode's actual phrasing: 'pushed, verified, green'."""
        doc = _write(
            tmp_path,
            "# Receipt\n\n- **Exact Head Commit**: `" + _OTHER + "`\n"
            "- **Publication State**: PR is pushed, verified, green.\n",
        )
        verdict = evaluate_receipt_document(doc, _CURRENT)
        assert verdict.verdict == VERDICT_REFUSED_STALE

    def test_stale_receipt_with_head_bound_standing_is_expired_not_refused(
        self, tmp_path
    ):
        """Point-in-time records are lawful: standing bound to the head it
        was earned on is EXPIRED (historical), not refused."""
        doc = _write(
            tmp_path,
            "# Receipt\n\n- **Exact Head Commit**: `" + _OTHER + "`\n"
            "- **Standing at qualified head `" + _OTHER + "`**: ALIVE\n",
        )
        verdict = evaluate_receipt_document(doc, _CURRENT)
        assert verdict.verdict == VERDICT_EXPIRED_POINT_IN_TIME

    def test_scope_qualifier_on_anchor_is_tolerated(self, tmp_path):
        doc = _write(
            tmp_path,
            "# Receipt\n\n- **Exact Head Commit (capstone scope)**: `" + _OTHER + "`\n",
        )
        verdict = evaluate_receipt_document(doc, _CURRENT)
        assert verdict.qualified_head == _OTHER
        assert verdict.verdict == VERDICT_EXPIRED_POINT_IN_TIME

    def test_malformed_current_head_refused_by_contract(self, tmp_path):
        doc = _write(tmp_path, "# Receipt\n")
        with pytest.raises(ValueError, match="full 40-char SHA"):
            evaluate_receipt_document(doc, "deadbeef")


class TestAFDE2603RepoReceipts:
    def test_repo_head_resolves(self):
        head = resolve_current_head()
        assert len(head) == 40

    def test_no_repo_receipt_claims_stale_current_standing(self):
        """Permanent machinery: every receipt document in this repo must
        comply -- none may claim current standing from a moved head."""
        import autofde_lab

        repo_root = Path(autofde_lab.__file__).resolve().parents[2]
        current = resolve_current_head(repo_root)
        verdicts = verify_repo_receipts(repo_root / "docs", current)
        refused = [v for v in verdicts if v.verdict == VERDICT_REFUSED_STALE]
        assert not refused, (
            "receipts claiming current standing from a moved head: "
            + "; ".join(f"{v.document}: {v.detail}" for v in refused)
        )


class TestHardenedGuardSemantics:
    """Second-pass falsifiers: the audit showed the first guard was
    fail-open -- omitting the anchor escaped, only two claim phrasings
    were detected, and abbreviated anchors were falsely refused."""

    def test_unanchored_standing_claim_is_refused_not_qualified(self, tmp_path):
        """The live blind spot: '**Standing:** `ALIVE`' with no anchor."""
        doc = _write(
            tmp_path,
            "# Receipt\n\n**Standing:** `ALIVE` -- observed this session.\n",
        )
        verdict = evaluate_receipt_document(doc, _CURRENT)
        assert verdict.verdict == VERDICT_REFUSED_UNANCHORED

    def test_bound_form_is_not_detected_as_unbound(self, tmp_path):
        doc = _write(
            tmp_path,
            "# Receipt\n\n**Standing at qualified head `" + _OTHER + "`**: ALIVE\n",
        )
        verdict = evaluate_receipt_document(doc, _CURRENT)
        assert verdict.verdict == VERDICT_EXPIRED_POINT_IN_TIME

    def test_abbreviated_anchor_prefix_of_current_head_qualifies(self, tmp_path):
        """A 12-char abbreviation that IS the head must not be refused."""
        doc = _write(
            tmp_path,
            "# Receipt\n\n- **Exact Head Commit**: `" + _CURRENT[:12] + "`\n"
            "- **Final Standing**: `ALIVE`\n",
        )
        verdict = evaluate_receipt_document(doc, _CURRENT)
        assert verdict.verdict == VERDICT_QUALIFIED

    def test_historical_ci_green_narration_is_not_a_current_claim(self, tmp_path):
        """Past-tense narration ('re-pushed, CI green on retry') is lawful
        history; only present-tense claims need anchors."""
        doc = _write(
            tmp_path,
            "# Log\n\nRe-pushed, CI green on retry.\n",
        )
        verdict = evaluate_receipt_document(doc, "e" * 40)
        assert verdict.verdict == VERDICT_QUALIFIED

    def test_present_tense_ci_is_green_is_a_current_claim(self, tmp_path):
        doc = _write(tmp_path, "# Doc\n\nCI is green.\n")
        verdict = evaluate_receipt_document(doc, "c" * 40)
        assert verdict.verdict == VERDICT_REFUSED_UNANCHORED

    def test_cli_exits_nonzero_on_refusal(self, tmp_path, monkeypatch, capsys):
        bad = tmp_path / "docs"
        bad.mkdir()
        (bad / "receipt-bad.md").write_text("**Standing:** `ALIVE`\n", encoding="utf-8")
        monkeypatch.setattr(
            "autofde_lab.agent.receipt_qualification.resolve_current_head",
            lambda *a, **k: "d" * 40,
        )
        rc = guard_main(["--docs-root", str(bad)])
        assert rc == 1
        assert "REFUSED" in capsys.readouterr().out

    def test_repo_wide_scan_covers_all_docs_not_receipt_names_only(self):
        """Content-based: every docs/*.md is evaluated."""
        import autofde_lab

        repo_root = Path(autofde_lab.__file__).resolve().parents[2]
        current = resolve_current_head(repo_root)
        verdicts = verify_repo_receipts(repo_root / "docs", current)
        total_md = sum(1 for _ in (repo_root / "docs").rglob("*.md"))
        assert len(verdicts) == total_md
        assert total_md > 100  # far more than receipt-named files
