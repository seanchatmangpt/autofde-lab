"""Chatman ecosystem WebAssembly federation for scikit-decide."""

from ._abi import ABI_NAME, ABI_VERSION, CORE_ABI, WIT
from ._model import ComponentDescriptor, Invocation, InvocationResult
from ._registry import ComponentRegistry
from ._runtime import (
    AbiViolation,
    ArtifactUnavailable,
    ChatmanEcosystem,
    ComponentBinding,
    RuntimeDependencyUnavailable,
    WasmBindingError,
    WasmtimeBackend,
)

__all__ = [
    "ABI_NAME",
    "ABI_VERSION",
    "CORE_ABI",
    "WIT",
    "AbiViolation",
    "ArtifactUnavailable",
    "ChatmanEcosystem",
    "ComponentBinding",
    "ComponentDescriptor",
    "ComponentRegistry",
    "Invocation",
    "InvocationResult",
    "RuntimeDependencyUnavailable",
    "WasmBindingError",
    "WasmtimeBackend",
]
