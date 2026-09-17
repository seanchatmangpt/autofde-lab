"""Tests for Knowledge Hook Synthesizer."""

from __future__ import annotations

from autofde_lab.sa2a.hooks.synthesis import HookSynthesizer, SynthesizedHookArtifact


def test_hook_synthesis_from_resolution():
    synthesizer = HookSynthesizer()
    artifact = synthesizer.synthesize_from_resolution(
        hook_name="crash_loop_pod_hook",
        trigger_predicate="ex:podState",
        trigger_value="CrashLoopBackOff",
        action_iri="urn:action:restart_pod",
        target_capability_iri="urn:cap:cluster:pods",
        goal_iri="urn:goal:cluster_healthy",
        reason="Restart pod upon repeated CrashLoopBackOff",
        authorized_actor="urn:agent:autonomic-controller",
    )

    assert isinstance(artifact, SynthesizedHookArtifact)
    assert artifact.hook.name == "crash_loop_pod_hook"
    assert artifact.hook.action_iri == "urn:action:restart_pod"
    assert artifact.suggested_grant.subject_id == "urn:agent:autonomic-controller"
    assert artifact.suggested_grant.action_iri == "urn:action:restart_pod"
    assert "ex:podState 'CrashLoopBackOff'" in artifact.graphlaw_rule_ttl
    assert len(artifact.artifact_digest) == 64
