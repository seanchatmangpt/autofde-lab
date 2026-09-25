"""Deterministic Python public-API extraction for interface equivalence."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from .model import digest


@dataclass(frozen=True, slots=True)
class PublicSymbol:
    kind: str
    name: str
    signature: str
    decorators: tuple[str, ...] = ()

    @property
    def symbol_id(self) -> str:
        return digest(self)


@dataclass(frozen=True, slots=True)
class PythonApiSurface:
    module_name: str
    symbols: tuple[PublicSymbol, ...]

    @property
    def surface_id(self) -> str:
        return digest(self)


def _name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _name(node.value) + "." + node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    return ast.dump(node, include_attributes=False)


def _arg(arg: ast.arg, default: ast.expr | None = None) -> str:
    rendered = arg.arg
    if arg.annotation is not None:
        rendered += ":" + ast.unparse(arg.annotation)
    if default is not None:
        rendered += "=" + ast.unparse(default)
    return rendered


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    parts: list[str] = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults: list[ast.expr | None] = [None] * (
        len(positional) - len(args.defaults)
    ) + list(args.defaults)
    posonly_count = len(args.posonlyargs)
    for index, (arg, default) in enumerate(zip(positional, defaults)):
        parts.append(_arg(arg, default))
        if posonly_count and index + 1 == posonly_count:
            parts.append("/")
    if args.vararg:
        parts.append("*" + _arg(args.vararg))
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        parts.append(_arg(arg, default))
    if args.kwarg:
        parts.append("**" + _arg(args.kwarg))
    result = f"({','.join(parts)})"
    if node.returns is not None:
        result += "->" + ast.unparse(node.returns)
    return result


def extract_python_api(source: str, *, module_name: str) -> PythonApiSurface:
    tree = ast.parse(source)
    symbols: list[PublicSymbol] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            symbols.append(
                PublicSymbol(
                    kind="async-function"
                    if isinstance(node, ast.AsyncFunctionDef)
                    else "function",
                    name=node.name,
                    signature=_signature(node),
                    decorators=tuple(_name(d) for d in node.decorator_list),
                )
            )
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            public_methods = [
                child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not child.name.startswith("_")
            ]
            method_sig = ";".join(
                f"{child.name}{_signature(child)}" for child in public_methods
            )
            symbols.append(
                PublicSymbol(
                    kind="class",
                    name=node.name,
                    signature=method_sig,
                    decorators=tuple(_name(d) for d in node.decorator_list),
                )
            )
    return PythonApiSurface(
        module_name=module_name,
        symbols=tuple(sorted(symbols, key=lambda symbol: (symbol.kind, symbol.name))),
    )


def python_api_verifier(
    original: PythonApiSurface,
    generated: PythonApiSurface,
) -> tuple[bool, object, object, str]:
    left = tuple((s.kind, s.name, s.signature, s.decorators) for s in original.symbols)
    right = tuple(
        (s.kind, s.name, s.signature, s.decorators) for s in generated.symbols
    )
    return left == right, left, right, "deterministic Python public API surface"
