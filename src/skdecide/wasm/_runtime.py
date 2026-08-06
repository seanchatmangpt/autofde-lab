"""Python bindings for receipt-bound Chatman WebAssembly components."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from ._abi import ALLOC_EXPORT, DEALLOC_EXPORT, INVOKE_EXPORT, MEMORY_EXPORT
from ._model import ComponentDescriptor, Invocation, InvocationResult
from ._registry import ComponentRegistry


class WasmBindingError(RuntimeError):
    """Base class for bounded component binding failures."""


class ArtifactUnavailable(WasmBindingError):
    """The exact component artifact has not been manufactured yet."""


class RuntimeDependencyUnavailable(WasmBindingError):
    """The selected host runtime is not installed."""


class AbiViolation(WasmBindingError):
    """The guest does not implement the admitted ABI or returned invalid data."""


class Backend(Protocol):
    def invoke(self, artifact: Path, request: bytes) -> bytes:
        """Invoke one exact artifact with a canonical request envelope."""


class WasmtimeBackend:
    """No-import core-Wasm backend implemented with the optional wasmtime package."""

    def __init__(self, *, fuel: int = 10_000_000) -> None:
        if fuel <= 0:
            raise ValueError("fuel must be positive")
        self._fuel = fuel

    def invoke(self, artifact: Path, request: bytes) -> bytes:
        try:
            import wasmtime
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeDependencyUnavailable(
                "wasmtime is required to execute Chatman components; install wasmtime"
            ) from exc

        config = wasmtime.Config()
        config.consume_fuel = True
        engine = wasmtime.Engine(config)
        store = wasmtime.Store(engine)
        store.set_fuel(self._fuel)
        store.set_limits(memory_size=64 * 1024 * 1024, instances=1, memories=1)
        module = wasmtime.Module.from_file(engine, str(artifact))
        if tuple(module.imports):
            raise AbiViolation(
                "component imports ambient host capabilities; the default binding admits none"
            )
        try:
            instance = wasmtime.Instance(store, module, [])
            exports = instance.exports(store)
            memory = exports[MEMORY_EXPORT]
            allocate = exports[ALLOC_EXPORT]
            invoke = exports[INVOKE_EXPORT]
            try:
                deallocate = exports[DEALLOC_EXPORT]
            except KeyError:
                deallocate = None
        except (KeyError, TypeError) as exc:
            raise AbiViolation("component is missing a required Chatman ABI export") from exc

        request_ptr = int(allocate(store, len(request)))
        memory.write(store, request, request_ptr)
        packed = int(invoke(store, request_ptr, len(request)))
        response_ptr = (packed >> 32) & 0xFFFFFFFF
        response_len = packed & 0xFFFFFFFF
        if response_len == 0:
            raise AbiViolation("component returned an empty response")
        response = bytes(memory.read(store, response_ptr, response_ptr + response_len))
        if deallocate is not None:
            deallocate(store, request_ptr, len(request))
            deallocate(store, response_ptr, response_len)
        return response


class ComponentBinding:
    """A Python object bound to one exact source-pinned Wasm component."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        artifact_root: Path,
        backend: Backend,
    ) -> None:
        self.descriptor = descriptor
        self.artifact_root = artifact_root
        self.backend = backend

    @property
    def artifact(self) -> Path:
        return self.artifact_root / self.descriptor.artifact

    @property
    def available(self) -> bool:
        return self.artifact.is_file()

    def invoke(
        self,
        operation: str,
        payload: Mapping[str, Any] | None = None,
        *,
        authority: Mapping[str, Any] | None = None,
    ) -> InvocationResult:
        if not self.available:
            raise ArtifactUnavailable(
                f"{self.descriptor.name} is pinned at {self.descriptor.revision} but "
                f"{self.artifact} has not been manufactured"
            )
        invocation = Invocation(
            component=self.descriptor,
            operation=operation,
            payload=payload or {},
            authority=authority or {},
        )
        try:
            raw = self.backend.invoke(self.artifact, invocation.to_bytes())
            return InvocationResult.from_bytes(
                self.descriptor,
                operation,
                raw,
            )
        except WasmBindingError:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise AbiViolation(
                f"{self.descriptor.name} failed the receipt-bound ABI"
            ) from exc


class ChatmanEcosystem:
    """Alias-aware Python façade over the complete admitted component registry."""

    def __init__(
        self,
        artifact_root: str | Path,
        *,
        registry: ComponentRegistry | None = None,
        backend: Backend | None = None,
    ) -> None:
        self.registry = registry or ComponentRegistry.default()
        self.artifact_root = Path(artifact_root)
        self.backend = backend or WasmtimeBackend()
        self._bindings: dict[str, ComponentBinding] = {}

    def __iter__(self):
        for component in self.registry:
            yield self.bind(component.name)

    def __getattr__(self, name: str) -> ComponentBinding:
        descriptor = self.registry.by_python_name(name)
        return self.bind(descriptor.name)

    def bind(self, name: str) -> ComponentBinding:
        descriptor = self.registry.by_name(name)
        binding = self._bindings.get(descriptor.name)
        if binding is None:
            binding = ComponentBinding(descriptor, self.artifact_root, self.backend)
            self._bindings[descriptor.name] = binding
        return binding

    def inventory(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                **component.as_dict(),
                "available": (self.artifact_root / component.artifact).is_file(),
            }
            for component in self.registry
        )

    def missing_artifacts(self) -> tuple[str, ...]:
        return tuple(
            component.name
            for component in self.registry
            if not (self.artifact_root / component.artifact).is_file()
        )
