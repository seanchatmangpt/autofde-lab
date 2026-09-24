"""Deterministic structural parsing before semantic/LLM interpretation."""

from __future__ import annotations

import ast
import json
import tomllib
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Protocol

from .model import digest


class ParseStanding(str, Enum):
    OBSERVED = "OBSERVED"
    UNSUPPORTED = "UNSUPPORTED"
    BUILD_BROKEN = "BUILD_BROKEN"


@dataclass(frozen=True, slots=True)
class StructuralDocument:
    parser_id: str
    parser_version: str
    language: str
    source_digest: str
    standing: ParseStanding
    structure: Any | None
    diagnostic: str | None = None

    @property
    def document_id(self) -> str:
        return digest(self)

    @property
    def structure_digest(self) -> str | None:
        if self.structure is None:
            return None
        return digest(self.structure)


class StructuralParser(Protocol):
    parser_id: str
    parser_version: str
    language: str

    def parse(self, text: str, source_digest: str) -> StructuralDocument: ...


def _ast_value(value: Any) -> Any:
    if isinstance(value, ast.AST):
        fields = {
            name: _ast_value(child)
            for name, child in ast.iter_fields(value)
        }
        return {"_type": value.__class__.__name__, **fields}
    if isinstance(value, list):
        return [_ast_value(item) for item in value]
    return value


class PythonAstParser:
    parser_id = "python.ast"
    parser_version = "stdlib"
    language = "python"

    def parse(self, text: str, source_digest: str) -> StructuralDocument:
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            return StructuralDocument(
                parser_id=self.parser_id,
                parser_version=self.parser_version,
                language=self.language,
                source_digest=source_digest,
                standing=ParseStanding.BUILD_BROKEN,
                structure=None,
                diagnostic=f"{exc.msg}:{exc.lineno}:{exc.offset}",
            )
        return StructuralDocument(
            parser_id=self.parser_id,
            parser_version=self.parser_version,
            language=self.language,
            source_digest=source_digest,
            standing=ParseStanding.OBSERVED,
            structure=_ast_value(tree),
        )


class JsonParser:
    parser_id = "python.json"
    parser_version = "stdlib"
    language = "json"

    def parse(self, text: str, source_digest: str) -> StructuralDocument:
        try:
            structure = json.loads(text)
        except json.JSONDecodeError as exc:
            return StructuralDocument(
                self.parser_id,
                self.parser_version,
                self.language,
                source_digest,
                ParseStanding.BUILD_BROKEN,
                None,
                f"{exc.msg}:{exc.lineno}:{exc.colno}",
            )
        return StructuralDocument(
            self.parser_id,
            self.parser_version,
            self.language,
            source_digest,
            ParseStanding.OBSERVED,
            structure,
        )


class TomlParser:
    parser_id = "python.tomllib"
    parser_version = "stdlib"
    language = "toml"

    def parse(self, text: str, source_digest: str) -> StructuralDocument:
        try:
            structure = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            return StructuralDocument(
                self.parser_id,
                self.parser_version,
                self.language,
                source_digest,
                ParseStanding.BUILD_BROKEN,
                None,
                str(exc),
            )
        return StructuralDocument(
            self.parser_id,
            self.parser_version,
            self.language,
            source_digest,
            ParseStanding.OBSERVED,
            structure,
        )


class StructuralParserRegistry:
    """Route known syntax to deterministic parsers; preserve unsupported types."""

    def __init__(self) -> None:
        self._by_suffix: dict[str, StructuralParser] = {
            ".py": PythonAstParser(),
            ".json": JsonParser(),
            ".toml": TomlParser(),
        }

    def register(self, suffix: str, parser: StructuralParser) -> None:
        suffix = suffix.lower()
        if not suffix.startswith("."):
            raise ValueError("parser suffix must start with '.'")
        if suffix in self._by_suffix:
            raise ValueError(f"parser already registered for {suffix}")
        self._by_suffix[suffix] = parser

    def parse(
        self,
        *,
        path: str,
        content: bytes,
        source_digest: str,
    ) -> StructuralDocument:
        suffix = PurePosixPath(path).suffix.lower()
        parser = self._by_suffix.get(suffix)
        if parser is None:
            return StructuralDocument(
                parser_id="none",
                parser_version="none",
                language=suffix.removeprefix(".") or "unknown",
                source_digest=source_digest,
                standing=ParseStanding.UNSUPPORTED,
                structure=None,
                diagnostic=f"UNSUPPORTED_LANGUAGE:{suffix or '<none>'}",
            )
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return StructuralDocument(
                parser_id=parser.parser_id,
                parser_version=parser.parser_version,
                language=parser.language,
                source_digest=source_digest,
                standing=ParseStanding.UNSUPPORTED,
                structure=None,
                diagnostic="UNSUPPORTED_LANGUAGE:non-utf8",
            )
        return parser.parse(text, source_digest)
