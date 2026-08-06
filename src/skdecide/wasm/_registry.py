"""Exact-SHA registry for the reusable Chatman ecosystem layer."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from types import MappingProxyType
from typing import Mapping

from ._model import ComponentDescriptor

_COMPONENTS = (
    ComponentDescriptor(
        name="ggen",
        python_name="ggen",
        repository="https://github.com/seanchatmangpt/ggen",
        branch="main",
        revision="c36d72161b847b13555c24132819281f17e40e40",
        artifact="ggen.wasm",
        capability_class="graph-manufacture",
    ),
    ComponentDescriptor(
        name="ggen-legacy",
        python_name="ggen_legacy",
        repository="https://github.com/seanchatmangpt/ggen-legacy",
        branch="main",
        revision="9118fe4569df0e1f98bdae279d01a66b6c177781",
        artifact="ggen-legacy.wasm",
        capability_class="compatibility",
    ),
    ComponentDescriptor(
        name="ggen-create",
        python_name="ggen_create",
        repository="https://github.com/seanchatmangpt/ggen-create",
        branch="main",
        revision="f5a0dc1ad7a3c981240231616efdff18eb3990a9",
        artifact="ggen-create.wasm",
        capability_class="graph-manufacture",
    ),
    ComponentDescriptor(
        name="wasm4pm",
        python_name="wasm4pm",
        repository="https://github.com/seanchatmangpt/wasm4pm",
        branch="main",
        revision="44f1bca8ff8cb05b1d8f5561c20c827e33d2b5fd",
        artifact="wasm4pm.wasm",
        capability_class="process-evidence",
    ),
    ComponentDescriptor(
        name="wasm4pm-compat",
        python_name="wasm4pm_compat",
        repository="https://github.com/seanchatmangpt/wasm4pm-compat",
        branch="main",
        revision="fbc080dc39300dac9dbd1d46edf47caa9916c610",
        artifact="wasm4pm-compat.wasm",
        capability_class="compatibility",
    ),
    ComponentDescriptor(
        name="lsp-max",
        python_name="lsp_max",
        repository="https://github.com/seanchatmangpt/lsp-max",
        branch="master",
        revision="2bc341561312b81c3b6d1b4585e82e0cd524b839",
        artifact="lsp-max.wasm",
        capability_class="language-protocol",
    ),
    ComponentDescriptor(
        name="star-toml",
        python_name="star_toml",
        repository="https://github.com/seanchatmangpt/star-toml",
        branch="main",
        revision="8395515cf8e68bfdc9edff49fb358c4f1da7c795",
        artifact="star-toml.wasm",
        capability_class="admitted-observation",
    ),
    ComponentDescriptor(
        name="mfact",
        python_name="mfact",
        repository="https://github.com/seanchatmangpt/mfact",
        branch="main",
        revision="308384002a15b9946acbcd6f560c5819723d79dc",
        artifact="mfact.wasm",
        capability_class="formal-admission",
    ),
    ComponentDescriptor(
        name="powl",
        python_name="powl",
        repository="https://github.com/seanchatmangpt/POWL",
        branch="main",
        revision="d2bae89b4f3a6375b56225ecfaf5eac3797900dc",
        artifact="powl.wasm",
        capability_class="process-planning",
        aliases=("POWL",),
    ),
    ComponentDescriptor(
        name="fgn",
        python_name="fgn",
        repository="https://github.com/seanchatmangpt/fgn",
        branch="main",
        revision="ae4156ddb0a1e4a6db0ef36f8675df903dedd718",
        artifact="fgn.wasm",
        capability_class="agent-runtime",
    ),
    ComponentDescriptor(
        name="mfw",
        python_name="mfw",
        repository="https://github.com/seanchatmangpt/mfw",
        branch="main",
        revision="e4fbda46f13d8213b86aa4f981d2387638983066",
        artifact="mfw.wasm",
        capability_class="manufacture-framework",
        visibility="private",
    ),
    ComponentDescriptor(
        name="mmdio",
        python_name="mmdio",
        repository="https://github.com/seanchatmangpt/mmdio",
        branch="main",
        revision="77c80ca2b1a944ecec8e28faa8c1762278f91e2b",
        artifact="mmdio.wasm",
        capability_class="diagram-io",
    ),
    ComponentDescriptor(
        name="mu-mcpp",
        python_name="mu_mcpp",
        repository="https://github.com/seanchatmangpt/mcpp",
        branch="master",
        revision="9995559a9042806ba18cd8177b1f5dd4c064008b",
        artifact="mu-mcpp.wasm",
        capability_class="lawful-manufacture",
        visibility="private",
        aliases=("mcpp",),
    ),
    ComponentDescriptor(
        name="mu-truex",
        python_name="mu_truex",
        repository="https://github.com/seanchatmangpt/truex",
        branch="main",
        revision="7da0500926ddd0374e91f6ab8d58244f6611fe4a",
        artifact="mu-truex.wasm",
        capability_class="lawful-manufacture",
        aliases=("truex",),
    ),
    ComponentDescriptor(
        name="cargo-cicd",
        python_name="cargo_cicd",
        repository="https://github.com/seanchatmangpt/cargo-cicd",
        branch="main",
        revision="e64f8224c23771e8c4e5d1d22fb939f812b04e1b",
        artifact="cargo-cicd.wasm",
        capability_class="release-law",
    ),
    ComponentDescriptor(
        name="ferroplan",
        python_name="ferroplan",
        repository="https://github.com/seanchatmangpt/ferroplan",
        branch="main",
        revision="282fae46a7cf4f71ab473e33b5f3fdb4d73433c9",
        artifact="ferroplan.wasm",
        capability_class="planning-runtime",
    ),
)


class ComponentRegistry:
    """Immutable, alias-aware registry with collision checks."""

    def __init__(self, components: Iterable[ComponentDescriptor]) -> None:
        ordered = tuple(components)
        by_name: dict[str, ComponentDescriptor] = {}
        by_python_name: dict[str, ComponentDescriptor] = {}
        for component in ordered:
            if component.name in by_name:
                raise ValueError(f"duplicate component name: {component.name}")
            by_name[component.name] = component
            for key in (component.python_name, *component.aliases):
                if key in by_python_name:
                    raise ValueError(f"duplicate Python binding or alias: {key}")
                by_python_name[key] = component
        self._components = ordered
        self._by_name: Mapping[str, ComponentDescriptor] = MappingProxyType(by_name)
        self._by_python_name: Mapping[str, ComponentDescriptor] = MappingProxyType(
            by_python_name
        )

    @classmethod
    def default(cls) -> "ComponentRegistry":
        return cls(_COMPONENTS)

    def __iter__(self) -> Iterator[ComponentDescriptor]:
        return iter(self._components)

    def __len__(self) -> int:
        return len(self._components)

    def by_name(self, name: str) -> ComponentDescriptor:
        try:
            return self._by_name[name]
        except KeyError as exc:
            raise KeyError(f"unknown Chatman component: {name}") from exc

    def by_python_name(self, name: str) -> ComponentDescriptor:
        try:
            return self._by_python_name[name]
        except KeyError as exc:
            raise AttributeError(f"unknown Chatman Python binding: {name}") from exc

    def as_manifest(self) -> dict[str, object]:
        return {
            "schema": "chatman.ecosystem.registry.v1",
            "component_count": len(self),
            "components": [component.as_dict() for component in self],
        }
