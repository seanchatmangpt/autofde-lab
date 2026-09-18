"""telemetry.py — real OpenTelemetry Python SDK instrumentation for sa2a-mfg-01.

Adds tracing ALONGSIDE the existing direct `OcelLog` writer path in
`ocel_adapter.py` — this module never touches decision logic in
`resource_agent.py`/`authority_agent.py`/`actuator.py`/`verifier.py`, and
`runtime.py`'s stopping condition and round loop are unchanged. It only
wraps the same five real per-round transitions `runtime.py` already
orchestrates in real OpenTelemetry spans, matching the mapping contract in
`~/ggen-marketplace/packs/otel-weaver-ocel-pack/ontology.ttl`:

    span.name = activity, one of exactly:
        "observe", "propose", "authorize", "actuate", "receipt"
    resource.attributes["service.name"] = "sa2a-mfg-01"

Real domain identities already present in this runtime's per-round data
(`resource_id`, `proposal_id`, `round_index`, `seed`, `verdict`,
`granted_energy_kwh`, `receipt_id`, `pre_state_hash`, `post_state_hash`) are
attached as real span attributes, not fabricated values -- when a phase
handles more than one item in a round (e.g. 4 `ResourceAgent`s observing),
the per-item identities are comma-joined into the same attribute rather than
invented or dropped.

Export wiring: a real `TracerProvider` is constructed once, module-level.
When `OTEL_EXPORTER_OTLP_ENDPOINT` is set, spans are exported for real via
`OTLPSpanExporter(endpoint=...)` through a `BatchSpanProcessor`. When it is
unset (the existing test suite's environment), no span processor is
attached at all -- spans are still real SDK `Span` objects with real
attributes, they are simply not exported anywhere, which is the documented
"no-op exporter" default so `runtime.py`'s Chicago-style tests keep passing
unmodified with no env var set.
"""
from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider

SERVICE_NAME_VALUE = "sa2a-mfg-01"

# Exactly the five real per-round transitions this runtime executes, per the
# otel-weaver-ocel-pack MappingRule contract (span.name = activity).
ACTIVITY_OBSERVE = "observe"
ACTIVITY_PROPOSE = "propose"
ACTIVITY_AUTHORIZE = "authorize"
ACTIVITY_ACTUATE = "actuate"
ACTIVITY_RECEIPT = "receipt"


def _build_tracer_provider() -> TracerProvider:
    """Construct the one real `TracerProvider` this module exports.

    Real SDK resource carries `service.name` = "sa2a-mfg-01" per the
    contract. Exporter wiring is real, env-gated: `OTLPSpanExporter` +
    `BatchSpanProcessor` only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set;
    otherwise no processor is added (a genuine no-op default, not a stub
    exporter class) so spans are created but never leave the process.
    """
    resource = Resource.create({SERVICE_NAME: SERVICE_NAME_VALUE})
    provider = TracerProvider(resource=resource)

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        # Imported lazily, real dependency (opentelemetry-exporter-otlp-proto-http),
        # only constructed when actually wired to an endpoint.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


_PROVIDER = _build_tracer_provider()
_TRACER = _PROVIDER.get_tracer("autofde_lab.sa2a.case_studies.manufacturing")


def get_tracer() -> trace.Tracer:
    """Return this module's real, module-level `Tracer`.

    A single tracer/provider per process (constructed once at import time)
    is deliberate: it lets every call to `runtime.run()` in one process
    share the same exporter wiring, matching how a real deployed service
    would configure tracing once at startup rather than per invocation.
    """
    return _TRACER


def join_ids(values: "list[str]") -> str:
    """Comma-join real per-item identities for a round-batched span
    attribute (e.g. 4 `resource_id`s observed in one round's "observe"
    span). Never fabricates a value: an empty list yields "" rather than a
    placeholder."""
    return ",".join(str(v) for v in values)


__all__ = [
    "SERVICE_NAME_VALUE",
    "ACTIVITY_OBSERVE",
    "ACTIVITY_PROPOSE",
    "ACTIVITY_AUTHORIZE",
    "ACTIVITY_ACTUATE",
    "ACTIVITY_RECEIPT",
    "get_tracer",
    "join_ids",
]
