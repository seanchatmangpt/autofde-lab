"""AFDE-2612: real-execution falsifier for the WASM hook-registration gap.

Scope: this file tests exactly one thing the AFDE-2612 closure note named as a
deferred gap -- "a synthesized hook's real ``graphlaw_rule_ttl``/``kh:Hook``
definition is never admitted into the real Praxis GraphLaw WASM engine, so the
WASM verdict branch (``KnowledgeHookEngine.evaluate``'s ``if v_data:`` arm,
``hooks/engine.py``) is never actually hit for any hook this repo synthesizes."

This session investigated whether that gap is closeable from the Python side
(merge the hook's own Turtle into ``base_ttl`` before calling
``GraphLawBridge.run_hooks``) and found, by REAL execution against the real
pinned ``praxis-graphlaw-wasm`` artifact (this repo's
``admission/graphlaw_bridge.py:EXPECTED_ARTIFACT_SHA256`` ==
``187688d9e7e33a575713d6911d75687adb38713ed37412e211af263dfcbe0c28``), that it
is NOT closeable from this repo alone:

1. Even the upstream WASM crate's OWN reference fixture for a firing hook
   (``crates/praxis-graphlaw-wasm/tests/core.rs::test_run_hooks_core_fires_expected_hook``
   in ``~/praxis``) produces an EMPTY ``schedule``/``verdicts`` when actually run
   through the real pinned ``run_hooks`` WASM export -- confirmed by real
   execution this session via this repo's own ``GraphLawBridge.run_hooks``
   (real Node.js subprocess, real wasm bytes, zero mocks). That upstream test's
   own assertion is deliberately weakened to tolerate this
   (``assert!(hook_result.verdicts.is_empty() || !hook_result.schedule.is_empty(), ...)``,
   with the comment "schedule may be empty depending on hook parsing/loading")
   -- this is a known, pre-existing gap in the vendored engine itself, not
   something introduced or fixable by this repo's Python wiring.
2. Root cause, isolated this session via a real, temporary ``cargo test`` probe
   run directly against ``~/praxis`` (added, run, and deleted this session --
   no tracked change was left in that repo; ``git status`` there is clean):
   ``TripleStore::from`` (the parse entry point both ``run_hooks_core_impl``
   and ``validate_all_core_impl`` use, per
   ``crates/praxis-graphlaw-wasm/src/core.rs``) decodes every plain string
   literal WITH its RDF 1.1 datatype suffix baked into the decoded text, e.g.
   ``"assert"^^<http://www.w3.org/2001/XMLSchema#string>`` instead of bare
   ``assert``. ``hooks::parsing::clean_term``
   (``crates/praxis-graphlaw/src/hooks/parsing.rs:16-24``) only strips a
   surrounding bare ``<...>`` or bare ``"..."`` wrapper -- it has no case for
   the compound ``"value"^^<datatype>`` form, so ``HookProps::one_str``
   (``parsing.rs:88-94``) returns the literal WITH its datatype suffix still
   attached. ``validate_and_extract_hooks``'s own exact-string match on
   ``kh:on`` (``parsing.rs:279``, ``"assert" | "retract" | "any"``) and
   ``kh:kind`` (``parsing.rs:286``, the ``match kind.as_str() { "delta" => ...
   }``) can never match, so extraction fails with a typed ``Err`` for every
   real hook -- silently swallowed by ``TripleStore::from``'s
   ``.unwrap_or_default()`` (``crates/praxis-graphlaw/src/lib.rs:257-259``),
   which is exactly why ``run_hooks`` returns ``ADMITTED`` with an empty
   ``schedule`` instead of a visible error.

   Real probed output, this session, against the exact upstream reference TTL::

       PROBE hooks.len() = 0
       PROBE validate_and_extract_hooks ERR: hook:on must be assert, retract, or any, got: "assert"^^<http://www.w3.org/2001/XMLSchema#string>

Conclusion: no TTL serialization this repo could construct or merge into
``base_ttl`` -- whether from ``HookSynthesizer``, hand-built, or copied
verbatim from the upstream engine's own passing fixture -- can make
``KnowledgeHookEngine.evaluate``'s WASM verdict branch fire, because the
defect lives in the vendored, pinned, content-addressed
``praxis-graphlaw``/``praxis-graphlaw-wasm`` engine itself (``~/praxis``), a
different repository this project must not modify (see
``admission/graphlaw_bridge.py``'s own artifact-identity-discipline docstring
and ``.claude/rules/ecosystem-boundary.md``). Per this repo's
``.claude/rules/absence-is-not-evidence.md`` ("an unexecuted counter-example
is not the same claim as an executed one"), this file converts that finding
into two permanent, real-execution falsifiers rather than leaving it as prose
in a ticket doc.

Zero ``unittest.mock``/``Mock``/``MagicMock``/``patch``/``monkeypatch``: both
tests drive the real ``GraphLawBridge`` (real Node.js subprocess against the
real pinned ``.wasm`` bytes) and the real ``KnowledgeHookEngine`` /
``HookSynthesizer``.
"""

from __future__ import annotations

import hashlib

from autofde_lab.sa2a.admission.graphlaw_bridge import GraphLawBridge
from autofde_lab.sa2a.hooks.engine import KnowledgeHookEngine
from autofde_lab.sa2a.hooks.model import HookVerdict
from autofde_lab.sa2a.hooks.synthesis import HookSynthesizer

# sha256("") -- the constant KnowledgeHookEngine's LOCAL fallback branch hashes
# into HookExecutionRecord.condition_hash whenever the WASM verdict lookup misses
# a hook's IRI (engine.py: `condition_hash = hashlib.sha256(hook.condition_query
# .encode("utf-8")).hexdigest()`, and every synthesized hook's condition_query is
# always ""). A record carrying exactly this digest is real, observable proof the
# LOCAL path -- not WASM -- produced that verdict, without needing to inspect
# engine internals or mock anything.
_LOCAL_FALLBACK_EMPTY_CONDITION_HASH = hashlib.sha256(b"").hexdigest()


def _wasm_admissible_hook_ttl(hook_iri: str, hook_name: str, trigger_predicate: str) -> str:
    """Hand-build the most charitable possible ``kh:Hook`` Turtle for this hook --
    deliberately NOT ``KnowledgeHookDefinition.to_turtle()`` (which has its own,
    separate serialization gaps out of this ticket's scope: it never emits
    ``kh:var`` at all, and its ``kh:effect`` value ("GroundAction") doesn't match
    the Rust engine's expected kebab-case vocabulary ("ground-action") either).

    This helper produces exactly the shape the upstream WASM crate's own
    reference fixture uses (see module docstring), isolating the ONE remaining,
    decisive blocker (the literal-datatype-suffix bug) from every other,
    independently-fixable gap.
    """
    return (
        "@prefix kh: <http://seanchatmangpt.github.io/praxis/kh#> .\n"
        f"<{hook_iri}> a kh:Hook ;\n"
        f'    kh:name "{hook_name}" ;\n'
        '    kh:on "assert" ;\n'
        '    kh:kind "delta" ;\n'
        f'    kh:var "{trigger_predicate}" ;\n'
        '    kh:effect "emit-delta" .\n'
    )


def test_real_wasm_engine_never_schedules_a_wellformed_matching_hook():
    """Black-box falsifier: even a WASM-format-correct ``kh:Hook`` definition,
    evaluated against a genuinely matching event delta through the REAL pinned
    ``praxis-graphlaw-wasm`` engine, produces zero schedule and zero verdicts.

    This is the decisive, repo-external blocker: it holds regardless of what
    autofde-lab's ``HookSynthesizer``/``KnowledgeHookEngine`` do, because the
    defect is in hook *extraction* inside the vendored WASM artifact itself,
    upstream of any Python-side wiring.
    """
    bridge = GraphLawBridge()  # real artifact-integrity-checked WASM bridge

    hook_iri = "http://example.org/hook/afde_2612_wasm_probe"
    hook_ttl = _wasm_admissible_hook_ttl(
        hook_iri=hook_iri, hook_name="afde_2612_wasm_probe", trigger_predicate="ex:status"
    )
    # Genuinely matching event: asserts the exact predicate the hook's kh:var names.
    matching_event_ttl = "@prefix ex: <http://example.org/> . ex:pod ex:status 'CRASH_LOOP' ."

    result = bridge.run_hooks(hook_ttl, matching_event_ttl)

    assert result["status"] == "ADMITTED"
    # Real observed evidence of the blocker (not a description of it): the hook
    # was never extracted into the engine's hook registry at all, so there is
    # nothing to schedule or produce a verdict for -- even though the event
    # genuinely matches the hook's own trigger predicate.
    assert result["schedule"] == [], (
        "If this now shows the hook_iri, the upstream praxis-graphlaw-wasm "
        "literal-decoding bug this test documents has been fixed and repinned -- "
        "revisit AFDE-2612's WASM-registration wiring, it may now be feasible."
    )
    assert result["verdicts"] == []


def test_engine_evaluate_uses_local_fallback_not_wasm_even_when_hook_ttl_is_merged_into_base():
    """Integration-level falsifier: simulate the exact wiring this ticket asked
    for (merge a real, synthesized hook's WASM-admissible Turtle into
    ``base_ttl`` before calling ``KnowledgeHookEngine.evaluate``) and prove the
    verdict that fires still comes from the LOCAL fallback branch, not the WASM
    branch -- for both a matching and a non-matching event.

    Uses the real ``HookSynthesizer`` (so the hook under test is genuinely this
    repo's synthesized artifact, not a hand-built stand-in) and the real
    ``KnowledgeHookEngine`` (real ``GraphLawBridge`` inside, real subprocess call
    per ``evaluate()``).
    """
    synthesizer = HookSynthesizer()
    artifact = synthesizer.synthesize_from_resolution(
        hook_name="afde_2612_wasm_probe_merged",
        trigger_predicate="ex:status",
        trigger_value="CRASH_LOOP",
        action_iri="http://example.org/action/restart_afde_2612",
        target_capability_iri="http://example.org/capability/restart_afde_2612",
    )

    engine = KnowledgeHookEngine()
    engine.register_hook(artifact.hook)

    # Deliberately merge a WASM-admissible Turtle for this exact hook into
    # base_ttl -- the change this ticket asked whether autofde-lab could make.
    merged_base_ttl = _wasm_admissible_hook_ttl(
        hook_iri=artifact.hook.iri,
        hook_name=artifact.hook.name,
        trigger_predicate="ex:status",
    )

    matching_event_ttl = "@prefix ex: <http://example.org/> . ex:pod ex:status 'CRASH_LOOP' ."
    matching_records = engine.evaluate(base_ttl=merged_base_ttl, event_ttl=matching_event_ttl)

    assert len(matching_records) == 1
    matching_record = matching_records[0]
    assert matching_record.hook_iri == artifact.hook.iri
    # The hook still fires correctly (AFDE-2612's prior content-matching fix to
    # the local fallback) -- but real, observable proof it fired via the LOCAL
    # path, not WASM: the WASM branch would set condition_hash from the WASM
    # engine's own v_data["condition_hash"], never the constant sha256("").
    assert matching_record.verdict == HookVerdict.FIRED
    assert matching_record.condition_hash == _LOCAL_FALLBACK_EMPTY_CONDITION_HASH

    unrelated_event_ttl = (
        "@prefix ex: <http://example.org/> . ex:pod ex:otherthing 'UNRELATED_SIGNAL' ."
    )
    nonmatching_records = engine.evaluate(base_ttl=merged_base_ttl, event_ttl=unrelated_event_ttl)
    assert len(nonmatching_records) == 1
    nonmatching_record = nonmatching_records[0]
    assert nonmatching_record.verdict == HookVerdict.NOT_FIRED
    assert nonmatching_record.condition_hash == _LOCAL_FALLBACK_EMPTY_CONDITION_HASH
