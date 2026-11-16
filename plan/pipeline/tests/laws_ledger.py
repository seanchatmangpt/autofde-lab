"""Pure parsers for LAWS.md (laws-v1) and OPEN.md (open-v1). Fail loudly on schema mismatch."""
from dataclasses import dataclass

LAWS_MARK = "<!-- schema: laws-v1 -->"
LAWS_COLS = ("id", "law", "quote", "line", "check", "pddl", "test", "scenario", "expect", "status")
OPEN_MARK = "<!-- schema: open-v1 -->"
OPEN_COLS = ("id", "question", "option_a", "option_b", "default", "owner", "switch",
             "transcript_line")


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class Law:
    id: str
    law: str
    quote: str
    line: str
    check: str
    pddl: str
    test: str
    scenario: str
    expect: str
    status: str


@dataclass(frozen=True)
class OpenQ:
    id: str
    question: str
    option_a: str
    option_b: str
    default: str
    owner: str
    switch: str
    transcript_line: str


def split_row(line):
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        raise SchemaError(f"not a table row: {line!r}")
    cells, cur, i, body = [], [], 0, s[1:-1]
    while i < len(body):
        if body[i] == "\\" and body[i + 1:i + 2] == "|":
            cur.append("|")
            i += 2
            continue
        if body[i] == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(body[i])
        i += 1
    cells.append("".join(cur).strip())
    return cells


def parse_table(text, mark, cols):
    lines = text.splitlines()
    idx = [i for i, ln in enumerate(lines) if ln.strip() == mark]
    if len(idx) != 1:
        raise SchemaError(f"expected exactly one {mark!r}, found {len(idx)}")
    i = idx[0] + 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        raise SchemaError("no table after schema marker")
    head = tuple(split_row(lines[i]))
    if head != cols:
        raise SchemaError(f"header mismatch: {head} != {cols}")
    i += 1
    if i >= len(lines) or set(lines[i].replace("|", "").replace(":", "").strip()) - {"-", " "}:
        raise SchemaError("missing header separator row")
    i += 1
    rows = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = split_row(lines[i])
        if len(cells) != len(cols):
            raise SchemaError(f"row {len(rows) + 1}: {len(cells)} cells, want {len(cols)}")
        rows.append(cells)
        i += 1
    if not rows:
        raise SchemaError("table has no rows")
    ids = [r[0] for r in rows]
    if len(set(ids)) != len(ids):
        raise SchemaError("duplicate ids")
    return rows


def parse_laws(text):
    return [Law(*r) for r in parse_table(text, LAWS_MARK, LAWS_COLS)]


def parse_open(text):
    return [OpenQ(*r) for r in parse_table(text, OPEN_MARK, OPEN_COLS)]
