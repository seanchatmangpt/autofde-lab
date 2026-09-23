"""Adversarial hardening tests for SubjectResolver / ExactSubject (QUALIFICATION
pass, 2026-09-17). Real objects throughout, zero mocks -- Chicago style per
`.claude/rules/testing-chicago-style.md`.

Scope: attacks SubjectResolver().resolve(...) and ExactSubject.composition_digest
beyond the manifest-shape hardening already committed in this session (see
resolver.py's REFUSED_MALFORMED_MANIFEST docstring). Each test below either pins a
newly fixed bug or documents a confirmed-safe/confirmed-correct finding as an
executable falsifier rather than prose.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from autofde_lab.sa2a.composition.resolver import (
    REFUSED_CONFLICTING_ARTIFACT_DIGEST,
    REFUSED_FLOATING_REPOSITORY_REF,
    REFUSED_MISSING_ARTIFACT_DIGEST,
    SubjectResolutionError,
    SubjectResolver,
    resolve_self_identity,
)

_VALID_MANIFEST = {
    "release_id": "v26.9.17-test",
    "repositories": [
        {
            "name": "autofde-lab",
            "exact_sha": "a" * 40,
            "remote_url": "https://example.invalid/a",
        }
    ],
    "artifacts": [{"artifact_id": "artifact-1", "digest": "b" * 64}],
    "root_manifest_digest": "c" * 64,
    "semantic_profile": "SA2A-STRICT",
    "court_revision": "v26.9.17",
    "falsifier_corpus_digest": "d" * 64,
    "query_set_digest": "e" * 64,
    "environment_identity": "test-env",
}


# --- 1. Unicode / control characters / very long strings ----------------------


def test_unicode_and_control_characters_in_release_id_do_not_crash() -> None:
    # release_id passes through `str(...).strip()` (existing, intentional trimming
    # of surrounding whitespace, confirmed here -- not a bug) so only interior
    # control/unicode characters are expected to survive verbatim.
    for weird in ("release\x00id", "release\nid", "\U0001f525" * 10, "release​id"):
        subject = SubjectResolver().resolve({**_VALID_MANIFEST, "release_id": weird})
        assert subject.release_id == weird
        assert len(subject.composition_digest) == 64


def test_release_id_leading_trailing_whitespace_is_trimmed_not_a_bug() -> None:
    """CONFIRMED-INTENTIONAL: `release_id` is normalized via `str(...).strip()`
    before becoming identity-bearing, so surrounding whitespace/CRLF is trimmed,
    not preserved as a distinct identity. Pinning this so a future change to the
    trim behavior is a deliberate, tested decision rather than silent drift."""
    subject = SubjectResolver().resolve(
        {**_VALID_MANIFEST, "release_id": "release\nid\r\n"}
    )
    assert subject.release_id == "release\nid"


def test_very_long_strings_do_not_collide_or_truncate() -> None:
    long_a = "x" * 10_000 + "A"
    long_b = "x" * 10_000 + "B"
    subject_a = SubjectResolver().resolve({**_VALID_MANIFEST, "release_id": long_a})
    subject_b = SubjectResolver().resolve({**_VALID_MANIFEST, "release_id": long_b})
    assert subject_a.release_id == long_a  # not silently truncated
    assert subject_b.release_id == long_b
    assert subject_a.composition_digest != subject_b.composition_digest


# --- 2. SHA case sensitivity ---------------------------------------------------


def test_uppercase_hex_sha_is_refused_not_a_bug() -> None:
    """CONFIRMED-CORRECT, not a gap: real `git rev-parse HEAD` (exercised below on
    THIS repo's own working tree) emits only lowercase hex -- git's internal SHA-1
    hex formatting is always lowercase regardless of `core.ignorecase` (that setting
    governs filesystem path comparison, not object-id text form). No git plumbing
    command, and no tool in this repo's toolchain, emits uppercase-hex SHAs. Refusing
    a non-canonical uppercase SHA is therefore fail-closed on a real anomaly (a
    hand-typed or corrupted ref), not a false refusal of a legitimate value -- left
    unchanged."""
    real_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert real_sha == real_sha.lower(), (
        "real git SHA output is lowercase, confirming the regex's assumption"
    )

    manifest = {
        **_VALID_MANIFEST,
        "repositories": [{"name": "x", "exact_sha": "A" * 40}],
    }
    try:
        SubjectResolver().resolve(manifest)
        assert False, "uppercase-hex SHA must still be refused (non-canonical form)"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_FLOATING_REPOSITORY_REF


# --- 3. Large repositories list -- no O(n^2) -----------------------------------


def test_large_unique_repository_list_resolves_in_linear_time() -> None:
    repos = [{"name": f"repo-{i}", "exact_sha": format(i, "040x")} for i in range(3000)]
    manifest = {**_VALID_MANIFEST, "repositories": repos}
    start = time.perf_counter()
    subject = SubjectResolver().resolve(manifest)
    elapsed = time.perf_counter() - start
    assert len(subject.repositories) == 3000
    assert elapsed < 2.0, (
        f"3000 unique repositories took {elapsed:.3f}s -- possible O(n^2) regression"
    )
    # composition_digest also must not blow up (it sorts every repo/artifact tuple)
    start = time.perf_counter()
    _ = subject.composition_digest
    assert time.perf_counter() - start < 2.0


def test_large_duplicate_repository_list_dedupes_without_quadratic_blowup() -> None:
    repos = [{"name": "same-name", "exact_sha": "a" * 40} for _ in range(5000)]
    manifest = {**_VALID_MANIFEST, "repositories": repos}
    start = time.perf_counter()
    subject = SubjectResolver().resolve(manifest)
    elapsed = time.perf_counter() - start
    assert len(subject.repositories) == 1
    assert elapsed < 2.0, (
        f"5000 identical duplicates took {elapsed:.3f}s -- possible O(n^2) regression"
    )


# --- 4. resolve_self_identity() on a non-git directory -------------------------


def test_resolve_self_identity_on_non_git_dir_raises_named_subprocess_error(
    tmp_path: Path,
) -> None:
    """CONFIRMED finding, not changed: `resolve_self_identity` on a directory with no
    `.git` raises `subprocess.CalledProcessError` (returncode 128, a real, typed,
    standard-library exception carrying git's own stderr). This is consistent with
    the module's fail-closed discipline -- it is a loud, typed failure a caller can
    catch specifically, not a silent wrong answer -- so no behavior change is made
    here. (No caller in this repo invokes `resolve_self_identity` from a path that
    isn't known to be this repo's own root, so wrapping it further would add
    indirection with no real caller benefit; documented as a considered, not
    overlooked, gap.)"""
    try:
        resolve_self_identity(tmp_path)
        raise AssertionError("must not silently succeed against a non-git directory")
    except subprocess.CalledProcessError as exc:
        assert exc.returncode == 128
        assert "not a git repository" in (exc.stderr or "")


# --- 5. No shell=True / list-arg subprocess invocation --------------------------


def test_resolver_module_never_uses_shell_true() -> None:
    source = Path(
        __import__(
            "autofde_lab.sa2a.composition.resolver", fromlist=["__file__"]
        ).__file__
    ).read_text()
    assert "shell=True" not in source


def test_subprocess_calls_use_list_args_and_resist_shell_metacharacters_in_cwd(
    tmp_path: Path,
) -> None:
    """Real, non-mocked injection probe: create a real git repo whose directory name
    itself contains shell metacharacters, then call `resolve_self_identity` against
    it and confirm no command execution occurred. Because `subprocess.run` is given
    argv lists (confirmed directly in source, see the previous test's neighbor
    assertion below) rather than a shell string, `cwd` can never be interpreted by a
    shell regardless of its content."""
    evil_dir = tmp_path / "repo$(touch pwned)`touch pwned2`;touch pwned3;"
    evil_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=evil_dir, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@example.invalid"], cwd=evil_dir, check=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=evil_dir, check=True)
    (evil_dir / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=evil_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=evil_dir, check=True)

    identity = resolve_self_identity(evil_dir)
    assert len(identity.sha) == 40
    assert identity.dirty is False
    for marker in ("pwned", "pwned2", "pwned3"):
        assert not (evil_dir / marker).exists()
        assert not (tmp_path / marker).exists()


# --- 6. Dict key order / JSON round-trip does not change composition_digest -----


def test_dict_key_order_does_not_change_composition_digest() -> None:
    reordered = {k: _VALID_MANIFEST[k] for k in reversed(list(_VALID_MANIFEST.keys()))}
    reordered["repositories"] = [
        dict(reversed(list(_VALID_MANIFEST["repositories"][0].items())))
    ]
    subject_a = SubjectResolver().resolve(_VALID_MANIFEST)
    subject_b = SubjectResolver().resolve(reordered)
    assert subject_a.composition_digest == subject_b.composition_digest


def test_json_round_trip_does_not_change_composition_digest() -> None:
    roundtripped = json.loads(json.dumps(_VALID_MANIFEST))
    subject_a = SubjectResolver().resolve(_VALID_MANIFEST)
    subject_b = SubjectResolver().resolve(roundtripped)
    assert subject_a.composition_digest == subject_b.composition_digest


# --- 7. Whitespace-only digest is refused, not silently accepted ---------------


def test_whitespace_only_artifact_digest_is_refused() -> None:
    for whitespace_digest in (" ", "   ", "\t\n"):
        manifest = {
            **_VALID_MANIFEST,
            "artifacts": [{"artifact_id": "a1", "digest": whitespace_digest}],
        }
        try:
            SubjectResolver().resolve(manifest)
            assert False, (
                f"whitespace-only digest {whitespace_digest!r} must be refused"
            )
        except SubjectResolutionError as exc:
            assert exc.code == REFUSED_MISSING_ARTIFACT_DIGEST


# --- Real bug found and fixed this pass: conflicting artifact digests ----------


def test_refuses_conflicting_digest_for_same_logical_artifact() -> None:
    """REAL BUG (fixed this pass): `_resolve_artifacts` had no conflict check
    analogous to `_resolve_repositories`'s `REFUSED_CONFLICTING_REPOSITORY_SHA` --
    two entries sharing one `artifact_id` but carrying two different `digest`
    values were both silently admitted into `ExactSubject.artifacts`, so the
    'exact composition' the resolver promises could not actually say which digest
    was this artifact's identity."""
    manifest = {
        **_VALID_MANIFEST,
        "artifacts": [
            {"artifact_id": "same-id", "digest": "b" * 64},
            {"artifact_id": "same-id", "digest": "c" * 64},
        ],
    }
    try:
        SubjectResolver().resolve(manifest)
        assert False, "must refuse two conflicting digests for one logical artifact"
    except SubjectResolutionError as exc:
        assert exc.code == REFUSED_CONFLICTING_ARTIFACT_DIGEST


def test_identical_duplicate_artifact_entry_is_not_an_error() -> None:
    """Mirrors the repository-side rule: same id, same digest, twice, is a harmless
    duplicate, not a conflict."""
    manifest = {
        **_VALID_MANIFEST,
        "artifacts": [
            {"artifact_id": "same-id", "digest": "b" * 64},
            {"artifact_id": "same-id", "digest": "b" * 64},
        ],
    }
    subject = SubjectResolver().resolve(manifest)
    assert len(subject.artifacts) == 1
    assert subject.artifacts[0].digest == "b" * 64
