"""Executable Chatman ecosystem WebAssembly federation for scikit-decide."""

from ._abi import ABI_NAME, ABI_VERSION, ADAPTER_OPERATIONS, CORE_ABI, WIT
from ._model import ComponentDescriptor, Invocation, InvocationResult
from ._registry import ComponentRegistry
from ._runtime import (
    AbiViolation,
    ArtifactImage,
    ArtifactIntegrityError,
    AutoBackend,
    ChatmanEcosystem,
    ComponentBinding,
    DirectoryArtifactStore,
    EmbeddedArtifactStore,
    NodeBackend,
    RuntimeDependencyUnavailable,
    WasmBindingError,
    WasmtimeBackend,
)

__all__ = [
    "ABI_NAME", "ABI_VERSION", "ADAPTER_OPERATIONS", "CORE_ABI", "WIT",
    "AbiViolation", "ArtifactImage", "ArtifactIntegrityError", "AutoBackend",
    "ChatmanEcosystem", "ComponentBinding", "ComponentDescriptor",
    "ComponentRegistry", "DirectoryArtifactStore", "EmbeddedArtifactStore",
    "Invocation", "InvocationResult", "NodeBackend",
    "RuntimeDependencyUnavailable", "WasmBindingError", "WasmtimeBackend",
]
