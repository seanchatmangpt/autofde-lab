"""Ephemeral software lifecycle and projection wrapper for Semantic A2A (§27).

Lifecycle:
    O* \to G \to C_t \to Verify \to Run \to Discard

Fundamental Theorem of Semantic Manufacture:
    GeneratedCode != SemanticTruth
    Changes to projection cannot mutate O*.
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from .constructor import (
    AdmittedSemantics,
    ArtifactManufacturer,
    ConstructionReceipt,
    ExecutableArtifact,
    TargetProfile,
    compute_digest,
)


class EphemeralState(str, Enum):
    """Lifecycle stages for ephemeral software compilation and execution."""

    ADMITTED = "ADMITTED"  # O*
    GENERATED = "GENERATED"  # G = \mu(O*)
    COMPILED = "COMPILED"  # C_t
    VERIFIED = "VERIFIED"  # Verify(C_t, Receipt)
    EXECUTED = "EXECUTED"  # Run(C_t)
    DISCARDED = "DISCARDED"  # Discard(C_t)
    TAMPERED = "TAMPERED"  # Tamper detected


class ProjectionMutationForbiddenError(Exception):
    """Raised when an attempt is made to mutate canonical semantics O* via a projection."""


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Outcome of ephemeral projection execution."""

    output: Any
    admitted_digest: str
    artifact_digest: str
    verified: bool
    state: EphemeralState


class EphemeralProjectionWrapper:
    """Projection wrapper guaranteeing that code retains no independent semantic authority.

    Principles:
    1. Canonical authority resides strictly in O*.
    2. Changes to projected code or execution environment cannot mutate O*.
    3. Ephemeral software is disposable: verify -> run -> discard.
    """

    def __init__(
        self,
        canonical_semantics: AdmittedSemantics,
        artifact: ExecutableArtifact,
    ) -> None:
        self._canonical_semantics = canonical_semantics
        self._initial_canonical_digest = canonical_semantics.canonical_digest()
        self._artifact = artifact
        self._state = EphemeralState.GENERATED
        self._compiled_callable: Callable[..., Any] | None = None

    @property
    def canonical_semantics(self) -> AdmittedSemantics:
        """Access canonical semantics (immutable view)."""
        return self._canonical_semantics

    @property
    def artifact(self) -> ExecutableArtifact:
        """Access the generated artifact."""
        return self._artifact

    @property
    def state(self) -> EphemeralState:
        """Current lifecycle state."""
        return self._state

    def compile(self) -> None:
        """Compile ephemeral projection into runnable form C_t."""
        if self._state == EphemeralState.DISCARDED:
            raise RuntimeError("Cannot compile discarded projection.")

        # For PYTHON_EPHEMERAL target, compile in isolated namespace
        if self._artifact.target_profile == TargetProfile.PYTHON_EPHEMERAL:
            ns: dict[str, Any] = {}
            exec(compile(self._artifact.source_code, "<ephemeral_projection>", "exec"), ns)
            fn = ns.get(self._artifact.entrypoint)
            if fn is None or not callable(fn):
                raise ValueError(
                    f"Entrypoint '{self._artifact.entrypoint}' not found or not callable in projection."
                )
            self._compiled_callable = fn
        else:
            # Simulated compilation for other profiles
            self._compiled_callable = lambda *args, **kwargs: {
                "profile": self._artifact.target_profile.value,
                "digest": self._artifact.artifact_digest,
            }

        self._state = EphemeralState.COMPILED

    def verify(self) -> bool:
        """Verify C_t against ConstructionReceipt and canonical O*."""
        if self._state not in (EphemeralState.COMPILED, EphemeralState.GENERATED, EphemeralState.TAMPERED):
            raise RuntimeError(f"Cannot verify from state {self._state}")

        # Check integrity of source code against receipt
        current_digest = compute_digest(self._artifact.source_code)
        if current_digest != self._artifact.receipt.output_artifact_digest:
            self._state = EphemeralState.TAMPERED
            return False

        # Verify receipt binds O*
        is_valid = self._artifact.receipt.verify(self._canonical_semantics, self._artifact)
        if not is_valid:
            self._state = EphemeralState.TAMPERED
            return False

        self._state = EphemeralState.VERIFIED
        return True

    def execute(self, *args: Any, **kwargs: Any) -> ExecutionResult:
        """Run verified ephemeral code."""
        if self._state == EphemeralState.TAMPERED:
            raise RuntimeError("Integrity verification failed: projection was tampered.")

        if self._state != EphemeralState.VERIFIED:
            # Auto-verify if compiled, or compile & verify
            if self._state == EphemeralState.GENERATED:
                self.compile()
            if not self.verify():
                raise RuntimeError("Integrity verification failed; execution forbidden.")

        assert self._compiled_callable is not None
        output = self._compiled_callable(*args, **kwargs)
        self._state = EphemeralState.EXECUTED

        # Assert canonical semantics were not mutated
        if self._canonical_semantics.canonical_digest() != self._initial_canonical_digest:
            raise ProjectionMutationForbiddenError(
                "Violation of §27: Projection execution attempted to mutate canonical O*!"
            )

        return ExecutionResult(
            output=output,
            admitted_digest=self._initial_canonical_digest,
            artifact_digest=self._artifact.artifact_digest,
            verified=True,
            state=self._state,
        )

    def discard(self) -> None:
        r"""Discard projection C_t; release resources ($O* \to \dots \to Discard$)."""
        self._compiled_callable = None
        self._state = EphemeralState.DISCARDED

    def mutate_code_attempt(self, tampered_code: str) -> ExecutableArtifact:
        """Simulate an external attempt to tamper with the generated artifact.

        Demonstrates that modifying the projection produces a tampered artifact whose
        receipt fails verification, while canonical semantics O* remains strictly untouched.
        """
        # Create a tampered artifact with same receipt
        tampered_artifact = ExecutableArtifact(
            target_profile=self._artifact.target_profile,
            source_code=tampered_code,
            entrypoint=self._artifact.entrypoint,
            artifact_digest=compute_digest(tampered_code),
            receipt=self._artifact.receipt,
            metadata=self._artifact.metadata,
        )

        # Check that O* is unchanged
        assert self._canonical_semantics.canonical_digest() == self._initial_canonical_digest
        return tampered_artifact


class EphemeralLifecycleRunner:
    """Executes the full ephemeral software lifecycle (§27):

    O* \to G \to C_t \to Verify \to Run \to Discard
    """

    def __init__(self, manufacturer: ArtifactManufacturer | None = None) -> None:
        self.manufacturer = manufacturer or ArtifactManufacturer()

    def run_lifecycle(
        self,
        admitted: AdmittedSemantics,
        target_profile: TargetProfile = TargetProfile.PYTHON_EPHEMERAL,
        *args: Any,
        **kwargs: Any,
    ) -> ExecutionResult:
        """Run entire lifecycle from admitted semantics to discard."""
        # 1. O* -> G = \mu(O*)
        artifact = self.manufacturer.manufacture(admitted, target_profile)

        # 2. Wrapper around G
        wrapper = EphemeralProjectionWrapper(admitted, artifact)

        # 3. G -> C_t
        wrapper.compile()

        # 4. Verify C_t
        if not wrapper.verify():
            raise RuntimeError("Ephemeral verification failed.")

        # 5. Run C_t
        try:
            result = wrapper.execute(*args, **kwargs)
        finally:
            # 6. Discard
            wrapper.discard()

        return result
