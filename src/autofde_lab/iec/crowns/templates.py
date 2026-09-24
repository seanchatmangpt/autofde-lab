"""Static anatomy of declared generator templates -- parsed, never evaluated.

IEC must compare a committed output against the generator that claims to have
produced it without running that generator (ARD section 22: no arbitrary build or
test execution during passive discovery). This module therefore only *tokenizes*:

* `split_frontmatter` mirrors `GgenIgniter.Frontmatter.split_template/1`
  (ggen_igniter `lib/ggen_igniter/frontmatter.ex:260-275`): a first line of `---`,
  then everything up to the first `\\n---\\n`. The header is read as flat
  `key: value` pairs only; any nested or multi-line key is recorded as
  unsupported rather than guessed.
* `eex_chunks` splits an EEx body into literal text and tags (`<%= %>` output,
  `<% %>` code, `<%# %>` comment, `<%%` escaped literal), with no trimming --
  Elixir `EEx.eval_string/2`'s default, which is what ggen_igniter calls
  (`lib/ggen_igniter/render.ex:10`).

`literal_containment` is the static reflexion check: every literal chunk the
template would emit must occur in the output, in template order, anchored at the
start/end where the template itself begins/ends with literal text. It is a
necessary condition for "this output is an instance of this template", not a
sufficient one, and is reported that way.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .model import IECRefusal

__all__ = [
    "Chunk",
    "Containment",
    "chunk_depths",
    "eex_chunks",
    "literal_containment",
    "split_frontmatter",
    "tera_chunks",
]

_FLAT_KEY = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def _scalar(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return json.loads(raw)
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1].replace("''", "'")
    return raw


def split_frontmatter(template: str) -> tuple[dict[str, str] | None, list[str], str]:
    """`(flat header, unsupported keys, body)`; header is None when absent."""
    first, newline, rest = template.partition("\n")
    if first != "---" or not newline:
        return None, [], template
    header_text, fence, body = rest.partition("\n---\n")
    if not fence:
        raise IECRefusal(
            "UNSUPPORTED_GENERATOR_CAPABILITY", "frontmatter has no closing fence"
        )
    header: dict[str, str] = {}
    unsupported: list[str] = []
    current: str | None = None
    for line in header_text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):
            if current is not None and current not in unsupported:
                unsupported.append(current)
                header.pop(current, None)
            continue
        match = _FLAT_KEY.match(line)
        if not match:
            unsupported.append(line.strip())
            current = None
            continue
        current, value = match.group(1), match.group(2)
        if value.strip() in ("", "|", ">"):
            unsupported.append(current)
            continue
        header[current] = _scalar(value)
    return header, unsupported, body


@dataclass(frozen=True)
class Chunk:
    kind: str  # "literal" | "output" | "code" | "comment"
    text: str
    line: int  # 1-based line in the template body where the chunk starts
    block: str = ""  # "open" | "middle" | "close" | "" -- block structure of a tag

    def to_json(self) -> dict[str, Any]:
        record = {"kind": self.kind, "text": self.text, "line": self.line}
        if self.block:
            record["block"] = self.block
        return record


_OPENS = re.compile(r"(\bdo|->)\s*$")
_CLOSES = re.compile(r"^\s*end\b")
_MIDDLE = re.compile(r"^\s*(else|after|catch|rescue)\b")


def _eex_block(text: str) -> str:
    if _MIDDLE.match(text):
        return "middle"
    if _CLOSES.match(text):
        return "close"
    if _OPENS.search(text):
        return "open"
    return ""


def eex_chunks(body: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    literal: list[str] = []
    literal_line = 1
    index = 0
    line = 1

    def flush() -> None:
        nonlocal literal
        if literal:
            chunks.append(Chunk("literal", "".join(literal), literal_line))
            literal = []

    while index < len(body):
        start = body.find("<%", index)
        if start < 0:
            if not literal:
                literal_line = line
            literal.append(body[index:])
            break
        if start > index:
            if not literal:
                literal_line = line
            literal.append(body[index:start])
            line += body.count("\n", index, start)
        if body.startswith("<%%", start):
            if not literal:
                literal_line = line
            literal.append("<%")
            index = start + 3
            continue
        end = body.find("%>", start + 2)
        if end < 0:
            raise IECRefusal(
                "UNSUPPORTED_GENERATOR_CAPABILITY",
                f"unterminated EEx tag at line {line}",
            )
        flush()
        marker = body[start + 2 : start + 3]
        kind, offset = {"=": ("output", 3), "#": ("comment", 3)}.get(
            marker, ("code", 2)
        )
        text = body[start + offset : end].strip()
        chunks.append(
            Chunk(kind, text, line, _eex_block(text) if kind != "comment" else "")
        )
        line += body.count("\n", start, end + 2)
        index = end + 2
        literal_line = line
    flush()
    return chunks


_TERA_OPEN = re.compile(r"^(for|if|macro|block|filter)\b")
_TERA_MIDDLE = re.compile(r"^(else|elif)\b")
_TERA_CLOSE = re.compile(r"^end(for|if|macro|block|filter)\b")
_TERA_TAGS = {"{{": ("}}", "output"), "{%": ("%}", "code"), "{#": ("#}", "comment")}


def tera_chunks(body: str) -> list[Chunk]:
    """Tokenize a Tera body, applying `{%-`/`-%}` whitespace control to literals.

    `{% raw %}...{% endraw %}` content is literal. Whitespace control is applied at
    tokenization time -- it changes which bytes a literal emits, so a containment
    check against untrimmed literals would report differences Tera never makes.
    """
    chunks: list[Chunk] = []
    literal: list[str] = []
    literal_line = 1
    line = 1
    index = 0
    trim_next = False

    def add_literal(text: str) -> None:
        nonlocal trim_next, literal_line
        if trim_next:
            text = text.lstrip()
            trim_next = False
        if text:
            if not literal:
                literal_line = line
            literal.append(text)

    def flush(trim_left: bool) -> None:
        nonlocal literal
        text = "".join(literal)
        if trim_left:
            text = text.rstrip()
        if text:
            chunks.append(Chunk("literal", text, literal_line))
        literal = []

    while index < len(body):
        starts = [(body.find(opener, index), opener) for opener in _TERA_TAGS]
        starts = [(pos, opener) for pos, opener in starts if pos >= 0]
        if not starts:
            add_literal(body[index:])
            break
        start, opener = min(starts)
        if start > index:
            add_literal(body[index:start])
        line += body.count("\n", index, start)
        closer, kind = _TERA_TAGS[opener]
        end = body.find(closer, start + 2)
        if end < 0:
            raise IECRefusal(
                "UNSUPPORTED_GENERATOR_CAPABILITY",
                f"unterminated Tera tag at line {line}",
            )
        inner = body[start + 2 : end]
        trim_left = inner.startswith("-")
        trim_right = inner.endswith("-")
        text = inner.strip("-").strip()
        is_raw = kind == "code" and re.match(r"^raw\b", text) is not None
        if is_raw:
            # A raw block emits its body verbatim and nothing else, so it
            # continues the surrounding literal instead of splitting it.
            if trim_left and literal:
                joined = "".join(literal).rstrip()
                literal[:] = [joined] if joined else []
        else:
            flush(trim_left)
        line += body.count("\n", start, end + 2)
        index = end + 2
        if is_raw:
            close = re.compile(r"\{%-?\s*endraw\s*-?%\}").search(body, index)
            if close is None:
                raise IECRefusal(
                    "UNSUPPORTED_GENERATOR_CAPABILITY",
                    f"unterminated raw block at line {line}",
                )
            raw = body[index : close.start()]
            if trim_right:
                raw = raw.lstrip()
            if close.group(0).startswith("{%-"):
                raw = raw.rstrip()
            trim_next = False
            add_literal(raw)
            line += body.count("\n", index, close.end())
            index = close.end()
            trim_next = close.group(0).endswith("-%}")
            continue
        block = ""
        if kind == "code":
            if _TERA_CLOSE.match(text):
                block = "close"
            elif _TERA_MIDDLE.match(text):
                block = "middle"
            elif _TERA_OPEN.match(text):
                block = "open"
        chunks.append(Chunk(kind, text, line, block))
        trim_next = trim_right
    flush(False)
    return chunks


def chunk_depths(chunks: list[Chunk]) -> list[int]:
    """Block nesting depth of each chunk, from each tag's `block` structure.

    A literal at depth 0 is emitted on every render; a literal inside a `for` or
    `if` block may be emitted zero times, so only depth-0 literals are necessary
    conditions on an output.
    """
    depths: list[int] = []
    depth = 0
    for chunk in chunks:
        if chunk.block in ("close", "middle"):
            depth -= 1
        if depth < 0:
            raise IECRefusal(
                "UNSUPPORTED_GENERATOR_CAPABILITY",
                f"unbalanced block at line {chunk.line}",
            )
        depths.append(depth)
        if chunk.block in ("open", "middle"):
            depth += 1
    if depth != 0:
        raise IECRefusal(
            "UNSUPPORTED_GENERATOR_CAPABILITY", f"{depth} unclosed template block(s)"
        )
    return depths


@dataclass(frozen=True)
class Containment:
    holds: bool
    detail: str
    literal_spans: tuple[tuple[int, int], ...]
    missing: dict[str, Any] | None

    def to_json(self) -> dict[str, Any]:
        return {
            "holds": self.holds,
            "detail": self.detail,
            "literal_span_count": len(self.literal_spans),
            "literal_bytes": sum(end - start for start, end in self.literal_spans),
            "missing": self.missing,
        }


def literal_containment(chunks: list[Chunk], output: str) -> Containment:
    """Greedy earliest-match embedding of the template's *mandatory* literals.

    Mandatory means depth 0 (`chunk_depths`): emitted on every render. Literals
    inside a block are skipped, because a block may run zero times. Greedy
    earliest match is complete for ordered, non-overlapping substring embedding:
    if any embedding exists, this finds one.
    """
    depths = chunk_depths(chunks)
    mandatory = [
        position
        for position, chunk in enumerate(chunks)
        if chunk.kind == "literal" and depths[position] == 0
    ]
    spans: list[tuple[int, int]] = []
    cursor = 0
    for rank, position in enumerate(mandatory):
        chunk = chunks[position]
        emits_before = any(
            item.kind == "output" or depths[index] > 0
            for index, item in enumerate(chunks[:position])
        )
        emits_after = any(
            item.kind == "output" or depths[position + 1 + index] > 0
            for index, item in enumerate(chunks[position + 1 :])
        )
        anchored_start = rank == 0 and not emits_before
        anchored_end = rank == len(mandatory) - 1 and not emits_after
        if anchored_end:
            found = len(output) - len(chunk.text)
            if found < cursor or not output.endswith(chunk.text):
                found = -1
        else:
            found = output.find(chunk.text, cursor)
        if found < 0 or (anchored_start and found != 0):
            return Containment(
                False,
                f"mandatory template literal at body line {chunk.line} not found in order",
                tuple(spans),
                {
                    "chunk_index": position,
                    "line": chunk.line,
                    "text": chunk.text[:400],
                    "search_from": cursor,
                    "anchored_start": anchored_start,
                    "anchored_end": anchored_end,
                },
            )
        spans.append((found, found + len(chunk.text)))
        cursor = found + len(chunk.text)
    optional = sum(
        1 for p, c in enumerate(chunks) if c.kind == "literal" and depths[p] > 0
    )
    return Containment(
        True,
        f"{len(spans)} mandatory literal chunks embedded in order ({optional} in blocks not required)",
        tuple(spans),
        None,
    )
