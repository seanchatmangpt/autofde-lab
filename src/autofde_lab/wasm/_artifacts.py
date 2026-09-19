"""Metadata and verified loading for packaged Chatman Wasm archives."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from io import BytesIO
from types import MappingProxyType
from typing import Mapping
from zipfile import BadZipFile, ZipFile

_BASE_ARCHIVE = "chatman-ecosystem-wasm.zip"
_INTEROP_ARCHIVE = "chatman-interop-wasm.zip"
_INTEROP_ENTRIES = frozenset({"mfw.wasm", "wasm4pm.wasm"})


@lru_cache(maxsize=2)
def _archive_bytes(name: str) -> bytes:
    return files("autofde_lab.wasm.artifacts").joinpath(name).read_bytes()


def _read_archive(name: str) -> dict[str, bytes]:
    try:
        with ZipFile(BytesIO(_archive_bytes(name))) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError(f"packaged Wasm archive has duplicates: {name}")
            return {entry: archive.read(entry) for entry in names}
    except BadZipFile as exc:
        raise ValueError(f"packaged Chatman Wasm archive is invalid: {name}") from exc


@lru_cache(maxsize=1)
def _archive_entries() -> Mapping[str, bytes]:
    entries = _read_archive(_BASE_ARCHIVE)
    interop = _read_archive(_INTEROP_ARCHIVE)
    if frozenset(interop) != _INTEROP_ENTRIES:
        raise ValueError("interop Wasm archive must contain exactly MFW and wasm4pm")
    entries.update(interop)
    return MappingProxyType(entries)


@dataclass(frozen=True, slots=True)
class PackagedArtifact:
    component: str
    filename: str
    sha256: str
    size: int

    def bytes(self) -> bytes:
        try:
            value = _archive_entries()[self.filename]
        except KeyError as exc:
            raise ValueError(f"packaged artifact is missing: {self.filename}") from exc
        if len(value) != self.size:
            raise ValueError(f"packaged artifact size drift for {self.filename}")
        if hashlib.sha256(value).hexdigest() != self.sha256:
            raise ValueError(f"packaged artifact digest drift for {self.filename}")
        if not value.startswith(b"\x00asm\x01\x00\x00\x00"):
            raise ValueError(f"packaged artifact is not Wasm v1: {self.filename}")
        return value


_ARTIFACTS = {
    "cargo-cicd": PackagedArtifact(
        component="cargo-cicd",
        filename="cargo-cicd.wasm",
        sha256="25017f7be19fa7fd7c1b5213c06c134cae8f0787ec819a95483aaf3fbc9f9894",
        size=5430,
    ),
    "ferroplan": PackagedArtifact(
        component="ferroplan",
        filename="ferroplan.wasm",
        sha256="c94569b5227e2674ab2b2db45f798627404b27431880a7c1b73a30b5db91aa16",
        size=5601,
    ),
    "fgn": PackagedArtifact(
        component="fgn",
        filename="fgn.wasm",
        sha256="ff7e746a60607fbcc67e63c8ce9f1b1f9006cc88003ab0da8edd6a5d7bb64ef2",
        size=5180,
    ),
    "ggen": PackagedArtifact(
        component="ggen",
        filename="ggen.wasm",
        sha256="682915fa6b438aae45343b53b43ec7792f666adf632ec256c491fb0b0a99d216",
        size=5051,
    ),
    "ggen-create": PackagedArtifact(
        component="ggen-create",
        filename="ggen-create.wasm",
        sha256="366d43d0e3969a9b355a5f5610d72c94c2569b35a0579752e1dba826d34441a3",
        size=5343,
    ),
    "ggen-legacy": PackagedArtifact(
        component="ggen-legacy",
        filename="ggen-legacy.wasm",
        sha256="3d7eea15677cde78e4859d0ebf9597a32bff0ba388c86a5dab4c086547cbd279",
        size=5514,
    ),
    "lsp-max": PackagedArtifact(
        component="lsp-max",
        filename="lsp-max.wasm",
        sha256="0b4d5f5683e6b333e763456952589f0cbb9aa84c251a81b7d3035e50ef713a92",
        size=5174,
    ),
    "mfact": PackagedArtifact(
        component="mfact",
        filename="mfact.wasm",
        sha256="698e4df2daa9c19bf1e8940b7a7d61a147575d6eedfcf1da157c2dcc1145e912",
        size=5432,
    ),
    "mfw": PackagedArtifact(
        component="mfw",
        filename="mfw.wasm",
        sha256="a4e0a2d4ea0173b32023f5bf925cee2b12e9452cd39e0136ec9fcb94ed5e3e57",
        size=5047,
    ),
    "mmdio": PackagedArtifact(
        component="mmdio",
        filename="mmdio.wasm",
        sha256="aa06f3665e54c43038dda962778052cc2b2fbcf33ac4b8609c5e5b8a6b7b8dee",
        size=5200,
    ),
    "mu-mcpp": PackagedArtifact(
        component="mu-mcpp",
        filename="mu-mcpp.wasm",
        sha256="4760b0818ffa65dc92e6bc42396f26b4ab9443511edf2db3166bac1e5f483779",
        size=5209,
    ),
    "mu-truex": PackagedArtifact(
        component="mu-truex",
        filename="mu-truex.wasm",
        sha256="c4b9c2d27ebb7333bbb891306fa307dfcd2d8a2531323c57524a53930d12216d",
        size=5251,
    ),
    "powl": PackagedArtifact(
        component="powl",
        filename="powl.wasm",
        sha256="40e2576d74c5c3343bff1a41f60d943043f5d5e1c565e64f628e9ab34778ccbe",
        size=5391,
    ),
    "star-toml": PackagedArtifact(
        component="star-toml",
        filename="star-toml.wasm",
        sha256="32fb4526512435e1d77cdc9456ac8dbdc8385e149f710435041dc869df471499",
        size=5260,
    ),
    "wasm4pm": PackagedArtifact(
        component="wasm4pm",
        filename="wasm4pm.wasm",
        sha256="2902d59cfce55ea592645855d5d4f9f19019bac36b14dda9d694d0d9b8d5bf1f",
        size=5514,
    ),
    "wasm4pm-compat": PackagedArtifact(
        component="wasm4pm-compat",
        filename="wasm4pm-compat.wasm",
        sha256="5383c57430b47647ce9598aded302c9503919d72b8a520784c4ba25c98224102",
        size=5639,
    ),
}
ARTIFACTS: Mapping[str, PackagedArtifact] = MappingProxyType(_ARTIFACTS)


def artifact_for(name: str) -> PackagedArtifact:
    try:
        return ARTIFACTS[name]
    except KeyError as exc:
        raise KeyError(f"unknown packaged Chatman artifact: {name}") from exc
