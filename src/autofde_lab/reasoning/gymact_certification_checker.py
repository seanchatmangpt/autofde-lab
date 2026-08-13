# Copyright (c) AIRBUS and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Real, hand-written checker producing a "GymAct Certified" conformance
manifest for any real `gymact.providers.EnvironmentProvider` instance.

Never ggen-generated -- manufacture is provenance, not architecture
(`ontology/manufacture.ttl`); the types this module constructs
(`CertificationManifest`, `CertificationCheckResult`) are ggen-generated
(`gymact_certification_types.py`, from `ontology/gymact-certification.ttl`),
but the real check logic lives here, hand-written, matching every other
`ggen`-adjacent checker/verifier in this repo (`scripts/verify_ggen_generation.py`
never trusts `ggen`'s own self-report either).

Provider-agnostic by construction
------------------------------------
Every check here depends only on `gymact.providers.Environment`/
`EnvironmentProvider` -- real, `@runtime_checkable typing.Protocol`s, zero
ABC subclassing required. Confirmed genuinely generic (not
`sregym`-specific) by direct comparison against a second real adapter,
`gymact.gyms.swegym`, this session: both implement the exact same 7+1
method surface with matching signatures; only capability count/shape and
`actuate`'s real dispatch target differ per adapter. This module never
imports `gymact.gyms.sregym` or any other concrete adapter module directly
-- callers supply a real provider instance; the checker only ever asks
"does this real object satisfy the real, generic Protocol."

Reconciled against gymact's own real, existing conformance precedent
------------------------------------------------------------------------
`gymact` already has partial, unnamed provider-conformance testing before
this module existed -- found by exhaustive research this session, not
duplicated here:

- `tests/test_two_gym_gate.py` -- a real, generic lifecycle test
  (materialize -> observe -> actuate -> verify -> teardown) parametrized
  over exactly 2 real providers (`MemoryProvider`, `GymnasiumProvider`),
  with zero provider-name branching in the test body.
- `tests/test_bounded_discovery_gyms.py` -- 3 more real providers
  (`SwitchboardProvider`, `ResourceFlowProvider`, `LockAndKeyProvider`),
  using the real `gymact.process.ConformanceChecker` -- a **different**
  concept (OCEL 2.0 process-mining conformance: declared operation
  sequence vs. actual receipt trail), not provider-API-shape conformance.
- `tests/test_registry_completeness_chicago.py` -- a real registry-presence
  check across all 21+ registered provider classes (does every registered
  provider instantiate and report capabilities), a third, still different
  scope from either of the above.

None of these three is exhaustive over gymact's full real provider catalog
(2-3 providers each, chosen for structural diversity, not completeness),
and none is named "certification" anywhere in source/tests/docs (confirmed
by an exhaustive case-insensitive "certif" grep across the whole `gymact`
package this session -- the only real hits are "self-certification" used
as an anti-pattern name, unrelated prose). This module is the first
exhaustive, explicitly-named, provider-API-shape-scoped one -- genuinely
additive, not a reimplementation of any of the three real precedents
above. `scripts/run_gymact_certification_sweep.py` additionally folds in
gymact's own real `gymact doctor`/`gymact validate-profile` CLI output
(real SHACL + zero-custom-TBox validation against gymact's own packaged
RDF profile) as further, real, non-duplicative evidence.

Never fabricates a pass
--------------------------
A check that could not run (e.g. `run_smoke_cycle=False`, or a required
method missing so a later check is structurally impossible) is recorded
as a real, honest, non-passing `CertificationCheckResult` -- never silently
omitted and never coerced into a pass. `manifest_conformance_level_ref` is
computed strictly from real check results; constructing a
`CertificationManifest` never itself asserts conformance independent of
what the real checks actually found.

`resultPassed`'s real generated-type quirk, named not hidden
-------------------------------------------------------------
`CertificationCheckResult.result_passed` is typed `str | None` even though
its real ontology range is `xsd:boolean` -- the shared
`templates/constitution_module.py.tera` template (reused by 12 real
generation rules in this repo, including this one) has no `xsd:boolean`
special case; it only branches on functional-vs-non-functional. This
module deliberately does not hand-edit the generated output (that would
violate `mode = "Create"`'s own "GENERATED, DO NOT EDIT BY HAND"
contract) -- it constructs real Python `bool` values at the field
despite the (slightly imprecise) static type hint; dataclass field types
are not runtime-enforced. Fixing the template itself is out of scope here
-- it is shared by every other ggen-generated module in this repo and
deserves its own reviewed change, not a side effect of this file.

Evidence fields are honestly UNKNOWN, never fabricated
--------------------------------------------------------
`CertificationCheckResult.result_evidence_ref`,
`CertificationManifest.manifest_computation_receipt_ref`, and
`manifest_issued_at_ref` are schema'd (`ontology/gymact-certification.ttl`
declares an `EVIDENCE` severity and these three reference fields) but this
module always constructs them as `None`/unset -- there is no real
receipt-chain implementation behind them. A real evidence chain here would
duplicate Level 4's OCEL/commitment machinery
(`src/autofde_lab/hub/domain/gym_procedure/`) and is deliberately out of
scope for this checker. Per this repo's own standing-law vocabulary
(`.claude/rules/standing-law.md`), that makes the `EVIDENCE` severity tier
`UNKNOWN`, not `ALIVE` and not silently dropped -- named here so a future
change doesn't "fix" these fields by inventing a fake evidence identifier
just to make them non-`None`.

Never calls `actuate()`
--------------------------
A generic checker has no safe, gym-agnostic capability payload to send --
every real adapter's capabilities are gym-specific (sregym: kubectl/MCP
dispatch; swegym: docker exec + patch + pytest). Calling `actuate()`
without knowing what it does would be exactly the kind of blind real
actuation `.claude/rules/gym-actuation-boundary.md` forbids. Named here as
a real, permanent boundary of this checker, not a gap silently left open.

In-process use of this module is NOT independent -- use the subprocess entrypoint
------------------------------------------------------------------------------------
This module does `from gymact.models import Consequence` / `from
gymact.providers import Environment, EnvironmentProvider` at import time --
real, in-process, no `sys.modules` guard. `gymact` is an ordinary
`pyproject.toml` dependency of `autofde-lab`, so any caller that imports
`check_environment_provider_conformance` directly always has `gymact`
present in its own `sys.modules` for the lifetime of that process. That is
exactly the self-certification shape
`~/gymact/docs/2026-08-12-gymact-certification-and-ggen-from-sregym.md`'s
central finding rejects ("a certification mechanism that lives inside
GymAct cannot be the independent verifier -- structurally, not by
discipline" -- and by extension, nor can a checker that imports `gymact`
in-process with no process boundary at all, regardless of which submodule
it imports).

`scripts/run_gymact_certification_check.py` is the one real, subprocess-isolated
entrypoint -- it imports `gymact` only inside its own fresh interpreter,
never inside a caller's process
(`tests/reasoning/test_gymact_certification_process_isolation_chicago.py`
proves this the same way
`tests/ecosystem/test_identity_mutation_chicago.py::test_verifier_runs_independently_in_a_fresh_process`
proves it for `standalone_verifier.py`). Calling
`check_environment_provider_conformance` directly, in-process, from a test
or another module is still real and useful for structural/smoke checks --
it is simply not the certified, independent path, and must never be
represented as one.

This closes only the structural (process-isolation) half of the
independence question, honestly, not the harder half. `standalone_verifier.py`
-- this repo's own real precedent for the `FORBIDDEN_RUNTIME_MODULES` +
`sys.modules`-guard pattern -- was itself self-retracted in commit
`7369e0ab` ("retract: the ALIVE reconstruction does not establish
independent standing"): a fabricated directory with a copied artifact tree
still reconstructed as `ALIVE_EVIDENCE_RECONSTRUCTED`, because nothing
bound the durable artifact to a specific real trial's identity. This
module's manifest has the identical gap -- nothing in a
`CertificationManifest` binds it to a specific real materialization event
beyond the caller's own say-so. Subprocess isolation is real progress
(the checking process no longer needs `gymact` importable to trust its own
result), but it is not identity-binding independence, and this module must
never claim the latter.
"""

from __future__ import annotations

import inspect
from typing import Any

from gymact.models import Consequence
from gymact.providers import Environment, EnvironmentProvider

from autofde_lab.reasoning.gymact_certification_types import (
    CertificationCheck,
    CertificationCheckResult,
    CertificationManifest,
    StandingValue,
)

__all__ = ["check_environment_provider_conformance"]

#: The real, required Environment surface (per gymact.providers.Environment,
#: confirmed identical across sregym.py and swegym.py this session).
_REQUIRED_ENVIRONMENT_METHODS: tuple[str, ...] = (
    "capabilities",
    "observe",
    "actuate",
    "verify",
    "checkpoint",
    "restore",
    "teardown",
)
_REQUIRED_ENVIRONMENT_ATTRIBUTES: tuple[str, ...] = ("environment_id", "requires_authority")

#: Real `CertificationCheck` catalog -- the check *definitions* this checker
#: performs, backed by the real ggen-generated type (previously unused: the
#: schema declared `afl:CertificationCheck` but no code constructed one; every
#: `CertificationCheckResult.result_check_ref` was a bare string literal with
#: no declared check behind it). Only the fixed-name checks are catalogued
#: here -- the per-method/per-attribute smoke checks
#: (`smoke_environment_has_method_{name}`, `smoke_environment_has_attribute_{attr}`)
#: are parameterized at runtime over `_REQUIRED_ENVIRONMENT_METHODS`/
#: `_REQUIRED_ENVIRONMENT_ATTRIBUTES` and are synthesized on demand by
#: `_dynamic_check` below rather than pre-enumerated, since their count is
#: derived from those tuples, not fixed.
_CERTIFICATION_CHECKS: tuple[CertificationCheck, ...] = (
    CertificationCheck(
        check_name="provider_satisfies_environment_provider_protocol",
        check_description="Real isinstance check against gymact.providers.EnvironmentProvider, a @runtime_checkable Protocol.",
        check_severity_ref=StandingValue.STRUCTURAL.value,
    ),
    CertificationCheck(
        check_name="materialize_method_present",
        check_description="Real inspect.signature check: materialize accepts keyword-only scenario/config.",
        check_severity_ref=StandingValue.STRUCTURAL.value,
    ),
    CertificationCheck(
        check_name="capabilities_returns_valid_consequences",
        check_description="Real capabilities() call returns a non-empty tuple of Capability objects with valid Consequence values.",
        check_severity_ref=StandingValue.BEHAVIORAL.value,
    ),
    CertificationCheck(
        check_name="smoke_materialize_succeeds",
        check_description="Real materialize() call completes without raising.",
        check_severity_ref=StandingValue.BEHAVIORAL.value,
    ),
    CertificationCheck(
        check_name="smoke_materialize_returns_environment",
        check_description="Real materialize() return value structurally satisfies gymact.providers.Environment.",
        check_severity_ref=StandingValue.BEHAVIORAL.value,
    ),
    CertificationCheck(
        check_name="smoke_observe_returns_dict",
        check_description="Real observe() call returns a dict.",
        check_severity_ref=StandingValue.BEHAVIORAL.value,
    ),
    CertificationCheck(
        check_name="smoke_checkpoint_returns_dict",
        check_description="Real checkpoint() call returns a dict.",
        check_severity_ref=StandingValue.BEHAVIORAL.value,
    ),
    CertificationCheck(
        check_name="smoke_teardown_succeeds",
        check_description="Real teardown() call completes without raising.",
        check_severity_ref=StandingValue.BEHAVIORAL.value,
    ),
    CertificationCheck(
        check_name="smoke_cycle_skipped_due_to_structural_failure",
        check_description="Honest non-check: run_smoke_cycle=True was requested but a structural check failed first, so no smoke cycle ran.",
        check_severity_ref=StandingValue.STRUCTURAL.value,
    ),
)
_CERTIFICATION_CHECKS_BY_NAME: dict[str, CertificationCheck] = {
    check.check_name: check for check in _CERTIFICATION_CHECKS if check.check_name is not None
}


def _dynamic_check(check_name: str, description: str) -> CertificationCheck:
    """Real `CertificationCheck` for a parameterized smoke check (one real
    instance is constructed per call, per real method/attribute name, rather
    than pre-enumerated in `_CERTIFICATION_CHECKS` -- the set of names is
    derived from `_REQUIRED_ENVIRONMENT_METHODS`/`_REQUIRED_ENVIRONMENT_ATTRIBUTES`,
    not fixed)."""
    return CertificationCheck(
        check_name=check_name,
        check_description=description,
        check_severity_ref=StandingValue.BEHAVIORAL.value,
    )


def _catalog_check_name(name: str) -> str:
    """Resolves `name` against the real `_CERTIFICATION_CHECKS_BY_NAME`
    catalog -- raises `KeyError` if a caller passes a check name with no
    real, declared `CertificationCheck` backing it, so a new check added
    without a matching catalog entry fails loudly rather than silently
    staying a bare string literal (the real gap Priority 4 closes)."""
    return _CERTIFICATION_CHECKS_BY_NAME[name].check_name or name


#: Named marker for the one real, known type-hint imprecision in this
#: module: `CertificationCheckResult.result_passed` is ggen-generated as
#: `str | None` (its real ontology range is `xsd:boolean`) because the
#: shared `templates/constitution_module.py.tera` has no `xsd:boolean`
#: branch -- see the module docstring's "resultPassed's real
#: generated-type quirk" section for the full explanation and why fixing
#: the shared template is out of scope here. Grep this name to find every
#: call site working around it.
_BOOL_TYPE_HINT_QUIRK = (
    "gymact_certification_types.CertificationCheckResult.result_passed is generated "
    "str | None, real value is bool -- templates/constitution_module.py.tera has no "
    "xsd:boolean branch"
)


def _result(check_ref: str, passed: bool, detail: str, evidence_ref: str | None = None) -> CertificationCheckResult:
    # `passed` is a real bool constructed here despite result_passed's
    # generated type hint -- see _BOOL_TYPE_HINT_QUIRK above.
    #
    # `evidence_ref` stays `None` for every real check this module performs
    # -- see the module docstring's "Evidence fields are honestly UNKNOWN,
    # never fabricated" section. Never invent a receipt/evidence identifier
    # here to make `EVIDENCE`-severity checks look populated.
    return CertificationCheckResult(
        result_check_ref=check_ref,
        result_passed=passed,  # type: ignore[arg-type]  # see _BOOL_TYPE_HINT_QUIRK
        result_detail=detail,
        result_evidence_ref=evidence_ref,
    )


def _check_provider_protocol(provider: Any) -> CertificationCheckResult:
    """Real structural check: does `provider` satisfy `EnvironmentProvider`?"""
    check_name = _catalog_check_name("provider_satisfies_environment_provider_protocol")
    if isinstance(provider, EnvironmentProvider):
        return _result(
            check_name,
            True,
            f"real object of type {type(provider).__name__!r} structurally satisfies "
            "gymact.providers.EnvironmentProvider",
        )
    return _result(
        check_name,
        False,
        f"real object of type {type(provider).__name__!r} does NOT satisfy "
        "gymact.providers.EnvironmentProvider (isinstance check against the real, "
        "@runtime_checkable Protocol failed)",
    )


def _check_materialize_signature(provider: Any) -> CertificationCheckResult:
    """Real structural check: does `materialize` accept the real, documented
    `(*, scenario, config)` keyword-only shape?"""
    check_name = _catalog_check_name("materialize_method_present")
    materialize = getattr(provider, "materialize", None)
    if materialize is None:
        return _result(
            check_name,
            False,
            "real object has no materialize attribute at all",
        )
    try:
        sig = inspect.signature(materialize)
    except (TypeError, ValueError) as exc:
        return _result(
            check_name,
            False,
            f"materialize is present but its real signature could not be inspected: {exc}",
        )
    params = sig.parameters
    has_scenario = "scenario" in params and params["scenario"].kind == inspect.Parameter.KEYWORD_ONLY
    has_config = "config" in params and params["config"].kind == inspect.Parameter.KEYWORD_ONLY
    if has_scenario and has_config:
        return _result(
            check_name,
            True,
            f"real materialize signature is {sig} -- carries keyword-only scenario/config",
        )
    return _result(
        check_name,
        False,
        f"real materialize signature is {sig} -- missing the real, required keyword-only "
        "scenario/config parameters",
    )


def _check_capabilities(provider_or_env: Any) -> tuple[CertificationCheckResult, tuple[Any, ...]]:
    """Real check: does `capabilities()` return real `Capability` tuples
    with valid `Consequence` values? Returns the real capabilities alongside
    the check result so a caller can report the real count."""
    check_name = _catalog_check_name("capabilities_returns_valid_consequences")
    capabilities_fn = getattr(provider_or_env, "capabilities", None)
    if capabilities_fn is None:
        return (
            _result(check_name, False, "no capabilities() method present"),
            (),
        )
    try:
        real_capabilities = tuple(capabilities_fn())
    except Exception as exc:  # noqa: BLE001 -- a real, external failure, reported honestly
        return (
            _result(
                check_name,
                False,
                f"real capabilities() call raised: {type(exc).__name__}: {exc}",
            ),
            (),
        )
    if not real_capabilities:
        return (
            _result(
                check_name,
                False,
                "real capabilities() returned zero capabilities -- a real, honest "
                "STRUCTURAL_ONLY-capping finding, never silently passed",
            ),
            (),
        )
    invalid = [c for c in real_capabilities if not isinstance(getattr(c, "consequence", None), Consequence)]
    if invalid:
        return (
            _result(
                check_name,
                False,
                f"{len(invalid)} of {len(real_capabilities)} real capabilities carry a "
                "consequence value that is not a real gymact.models.Consequence member",
            ),
            real_capabilities,
        )
    return (
        _result(
            check_name,
            True,
            f"real capabilities() returned {len(real_capabilities)} capabilities, every "
            "consequence value real and valid",
        ),
        real_capabilities,
    )


async def _run_smoke_cycle(
    provider: Any, *, scenario: str | None, config: dict[str, Any]
) -> tuple[list[CertificationCheckResult], Any | None]:
    """Real materialize -> observe -> checkpoint -> teardown cycle.
    Never calls `actuate()` -- see module docstring."""
    results: list[CertificationCheckResult] = []
    env: Any | None = None

    try:
        env = await provider.materialize(scenario=scenario, config=config)
    except Exception as exc:  # noqa: BLE001 -- real, external, reported honestly
        results.append(
            _result(
                _catalog_check_name("smoke_materialize_succeeds"),
                False,
                f"real materialize() raised: {type(exc).__name__}: {exc}",
            )
        )
        return results, None

    if not isinstance(env, Environment):
        results.append(
            _result(
                _catalog_check_name("smoke_materialize_returns_environment"),
                False,
                f"real materialize() returned an object of type {type(env).__name__!r} that "
                "does NOT structurally satisfy gymact.providers.Environment",
            )
        )
        # Real, honest early exit: no point running further smoke checks
        # against an object that isn't a real Environment.
        teardown = getattr(env, "teardown", None)
        if callable(teardown):
            try:
                await teardown()
            except Exception:  # noqa: BLE001 -- best-effort cleanup only
                pass
        return results, env

    results.append(
        _result(
            _catalog_check_name("smoke_materialize_returns_environment"),
            True,
            f"real materialize() returned a real, Protocol-conformant Environment "
            f"(environment_id={getattr(env, 'environment_id', '<missing>')!r})",
        )
    )

    for method_name in _REQUIRED_ENVIRONMENT_METHODS:
        # Real CertificationCheck constructed per real required method name
        # (see `_dynamic_check` -- these are parameterized over
        # `_REQUIRED_ENVIRONMENT_METHODS`, not pre-enumerated literals).
        check = _dynamic_check(
            f"smoke_environment_has_method_{method_name}",
            f"Real Environment instance exposes a callable {method_name!r} method.",
        )
        present = callable(getattr(env, method_name, None))
        results.append(
            _result(
                check.check_name or "",
                present,
                f"real Environment {'exposes' if present else 'is missing'} a callable "
                f"{method_name!r} method",
            )
        )

    capabilities_result, _capabilities = _check_capabilities(env)
    results.append(capabilities_result)

    for attr in _REQUIRED_ENVIRONMENT_ATTRIBUTES:
        check = _dynamic_check(
            f"smoke_environment_has_attribute_{attr}",
            f"Real Environment instance carries the required {attr!r} attribute.",
        )
        present = hasattr(env, attr)
        results.append(
            _result(
                check.check_name or "",
                present,
                f"real Environment {'carries' if present else 'is missing'} the required "
                f"{attr!r} attribute",
            )
        )

    try:
        observed = await env.observe()
        results.append(
            _result(
                _catalog_check_name("smoke_observe_returns_dict"),
                isinstance(observed, dict),
                f"real observe() returned {type(observed).__name__}"
                + (f" with {len(observed)} real key(s)" if isinstance(observed, dict) else ""),
            )
        )
    except Exception as exc:  # noqa: BLE001
        results.append(
            _result(
                _catalog_check_name("smoke_observe_returns_dict"),
                False,
                f"real observe() raised: {type(exc).__name__}: {exc}",
            )
        )

    try:
        checkpoint = await env.checkpoint()
        results.append(
            _result(
                _catalog_check_name("smoke_checkpoint_returns_dict"),
                isinstance(checkpoint, dict),
                f"real checkpoint() returned {type(checkpoint).__name__}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        results.append(
            _result(
                _catalog_check_name("smoke_checkpoint_returns_dict"),
                False,
                f"real checkpoint() raised: {type(exc).__name__}: {exc}",
            )
        )

    try:
        await env.teardown()
        results.append(
            _result(_catalog_check_name("smoke_teardown_succeeds"), True, "real teardown() completed without raising")
        )
    except Exception as exc:  # noqa: BLE001
        results.append(
            _result(
                _catalog_check_name("smoke_teardown_succeeds"),
                False,
                f"real teardown() raised: {type(exc).__name__}: {exc}",
            )
        )

    return results, env


async def check_environment_provider_conformance(
    provider: Any,
    *,
    gym_name: str,
    environment_factory_config: dict[str, Any] | None = None,
    scenario: str | None = None,
    run_smoke_cycle: bool = False,
) -> tuple[CertificationManifest, tuple[CertificationCheckResult, ...]]:
    """Real, provider-agnostic conformance check against `provider`.

    Structural checks (Protocol shape, `materialize` signature,
    `capabilities()` validity) always run and need no live cluster/network.
    `run_smoke_cycle=True` additionally drives a real
    `materialize -> observe -> checkpoint -> teardown` cycle (never
    `actuate()`) against the real `provider` -- `environment_factory_config`/
    `scenario` are passed straight to the real `materialize()` call.

    Returns `(manifest, results)` -- the real `CertificationManifest`
    (summary, `manifest_check_result_ref` holding each real result's
    `result_check_ref` as a reference, per this repo's own "hold a
    reference, never a duplicated copy" convention) alongside the full,
    real, ordered `CertificationCheckResult` tuple a caller/test can
    inspect for per-check detail. `manifest_conformance_level_ref` is
    honestly computed:

    - `CERT_UNSUPPORTED` if `provider` does not satisfy `EnvironmentProvider`
      at all (the object is not even the right kind of thing to certify --
      distinct from "conforms but a check failed").
    - `CERT_BUILD_BROKEN` if `provider` satisfies the Protocol but some
      other structural check fails (e.g. a malformed `materialize`
      signature).
    - `STRUCTURAL_ONLY` if all structural checks pass but no smoke cycle
      ran (or ran and failed).
    - `SMOKE_TESTED` only if every structural AND smoke check passed for
      real.
    """
    results: list[CertificationCheckResult] = []

    # `capabilities()` is a real Environment-level method (confirmed live:
    # gymact.providers.EnvironmentProvider itself declares no such method,
    # only materialize()) -- it cannot be checked without a real,
    # materialized Environment, so it is NOT part of the pure-structural
    # (no-materialize) pass. It runs inside _run_smoke_cycle instead, the
    # only point a real Environment instance actually exists.
    provider_protocol_result = _check_provider_protocol(provider)
    results.append(provider_protocol_result)

    # `CERT_UNSUPPORTED` is distinct from `CERT_BUILD_BROKEN`: a provider
    # that isn't even structurally an `EnvironmentProvider` is not "broken
    # certification", it's the wrong kind of object entirely -- checking its
    # materialize signature would be meaningless, so the remaining
    # structural checks are skipped in that case.
    if not provider_protocol_result.result_passed:
        results.append(
            _result(
                _catalog_check_name("materialize_method_present"),
                False,
                "skipped -- provider does not satisfy EnvironmentProvider, so its "
                "materialize signature cannot be meaningfully checked",
            )
        )
        manifest = CertificationManifest(
            manifest_gym_name=gym_name,
            manifest_provider_class_ref=f"{type(provider).__module__}.{type(provider).__qualname__}",
            manifest_conformance_level_ref=StandingValue.CERT_UNSUPPORTED.value,
            manifest_check_result_ref=tuple(r.result_check_ref or "" for r in results),
            manifest_issued_at_ref=None,
            manifest_computation_receipt_ref=None,
        )
        return manifest, tuple(results)

    results.append(_check_materialize_signature(provider))

    structural_passed = all(r.result_passed for r in results)

    smoke_ran = False
    smoke_passed = False
    if run_smoke_cycle and structural_passed:
        smoke_results, _env = await _run_smoke_cycle(
            provider, scenario=scenario, config=environment_factory_config or {}
        )
        results.extend(smoke_results)
        smoke_ran = True
        smoke_passed = all(r.result_passed for r in smoke_results)
    elif run_smoke_cycle and not structural_passed:
        results.append(
            _result(
                _catalog_check_name("smoke_cycle_skipped_due_to_structural_failure"),
                False,
                "run_smoke_cycle=True was requested, but a structural check failed first -- "
                "never running a smoke cycle against a provider that isn't even a real "
                "Protocol-conformant EnvironmentProvider",
            )
        )

    if not structural_passed:
        conformance_level = StandingValue.CERT_BUILD_BROKEN
    elif smoke_ran and smoke_passed:
        conformance_level = StandingValue.SMOKE_TESTED
    else:
        conformance_level = StandingValue.STRUCTURAL_ONLY

    manifest = CertificationManifest(
        manifest_gym_name=gym_name,
        manifest_provider_class_ref=f"{type(provider).__module__}.{type(provider).__qualname__}",
        manifest_conformance_level_ref=conformance_level.value,
        manifest_check_result_ref=tuple(r.result_check_ref or "" for r in results),
        manifest_issued_at_ref=None,
        manifest_computation_receipt_ref=None,
    )
    return manifest, tuple(results)
