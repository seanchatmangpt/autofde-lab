"""File-based extractors: each yields CandidateCapability records from one
source file. Pure reads; no subprocess except `cli_help` (opt-in, PATH-only).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from typing import Iterator

from classify import classify_command, RULES
from model import CandidateCapability, make_id

SKIP_DIRS = {".git", "node_modules", "target", "_build", "deps", ".venv", "venv", "vendor",
             "tmp", "tmp_probe", ".terraform", "__pycache__", ".tox", "dist", "build",
             ".ggen-verify-tmp", ".tmp-jira-plan", ".ws2work", "scratch", "TEMP_RLlib"}


def _cap(repo: str, kind: str, name: str, command: str, cwd: str, ev: str, **kw) -> CandidateCapability:
    c = classify_command(command)
    cap = CandidateCapability(
        id=make_id(repo, kind, name, command),
        name=name,
        source_kind=kind,
        command=command,
        cwd=cwd,
        evidence_source=ev,
        authority_class=c["authority_class"],
        reversibility=c["reversibility"],
        effects=c["effects"],
        qualification_strategy=c["qualification_strategy"],
    )
    for k, v in kw.items():
        setattr(cap, k, v)
    return cap


def _rel(root: str, path: str) -> str:
    return os.path.relpath(path, root)


def _read(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


# --------------------------------------------------------------------- justfile
_JUST_RECIPE = re.compile(r"^(?:@)?([A-Za-z_][A-Za-z0-9_-]*)((?:\s+[A-Za-z_][A-Za-z0-9_]*(?:=\S+|=\"[^\"]*\")?|\s+\+[A-Za-z_]\w*|\s+\*[A-Za-z_]\w*)*)\s*:(?!=)\s*(.*)$")
_JUST_SETTING = re.compile(r"^(set |export |alias |import |mod |\[)")
_JUST_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*\s*:=")


def _just_deps(deps_text: str) -> list[str]:
    """`a b (c arg) && d` -> [a, b, c, d]; `{{...}}` / `&&` markers stripped."""
    txt = deps_text.replace("&&", " ")
    out: list[str] = []
    for grp in re.findall(r"\(([^)]*)\)", txt):
        tok = grp.split()
        if tok:
            out.append(tok[0])
    txt = re.sub(r"\([^)]*\)", " ", txt)
    for tok in txt.split():
        if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*$", tok):
            out.append(tok)
    return out


def extract_justfile(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    lines = _read(path)
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(path)) or "."
    i = 0
    attrs: list[str] = []
    while i < len(lines):
        line = lines[i]
        if line.startswith("[") and line.rstrip().endswith("]"):
            attrs.append(line.strip())
            i += 1
            continue
        if not line or line.lstrip().startswith("#") or line[0] in " \t" or _JUST_SETTING.match(line) or _JUST_ASSIGN.match(line):
            if line.strip() and not line[0] in " \t":
                attrs = []
            i += 1
            continue
        m = _JUST_RECIPE.match(line)
        if not m:
            i += 1
            continue
        name, params, deps_text = m.group(1), m.group(2).strip(), m.group(3).strip()
        start = i + 1
        body: list[str] = []
        j = start
        while j < len(lines) and (lines[j].startswith((" ", "\t")) or not lines[j].strip()):
            if lines[j].strip():
                body.append(lines[j].strip())
            j += 1
        deps = _just_deps(deps_text)
        pre = [f"just recipe params: {params}"] if params else []
        if attrs:
            pre.append("justfile attributes: " + " ".join(attrs))
        body_text = "\n".join(body) if body else ""
        cmd = body_text or f"just {name}"
        cap = _cap(repo, "justfile", name, cmd, cwd, f"{rel}:{i + 1}",
                   preconditions=["`just` on PATH"] + pre, depends_on=deps)
        cap.notes.append(f"invoke: just --justfile {rel} {name}")
        yield cap
        attrs = []
        i = j if j > i else i + 1


# --------------------------------------------------------------------- Makefile
_MAKE_TARGET = re.compile(r"^([A-Za-z_][A-Za-z0-9_./-]*(?:\s+[A-Za-z_][A-Za-z0-9_./-]*)*)\s*::?(?!=)\s*(.*)$")


def extract_makefile(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    lines = _read(path)
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(path)) or "."
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line or line[0] in " \t#" or line.startswith(".") or "=" in line.split(":")[0] or "%" in line:
            i += 1
            continue
        m = _MAKE_TARGET.match(line)
        if not m:
            i += 1
            continue
        targets, deps_text = m.group(1).split(), m.group(2).strip()
        j = i + 1
        body: list[str] = []
        while j < len(lines) and (lines[j].startswith("\t") or not lines[j].strip()):
            if lines[j].strip():
                body.append(lines[j].strip())
            j += 1
        deps = [d for d in deps_text.split() if not d.startswith("$")]
        for t in targets:
            cmd = "\n".join(body) if body else f"make {t}"
            cap = _cap(repo, "makefile", t, cmd, cwd, f"{rel}:{i + 1}", preconditions=["`make` on PATH"], depends_on=deps)
            cap.notes.append(f"invoke: make -f {rel} {t}")
            yield cap
        i = j


# --------------------------------------------------------------------- minimal YAML walker
def _yaml_block(lines: list[str], start: int, key: str) -> list[tuple[int, str]]:
    """Return (lineno, text) of lines belonging to a `key:` mapping at line start's indent."""
    indent = len(lines[start]) - len(lines[start].lstrip())
    out = []
    for k in range(start + 1, len(lines)):
        ln = lines[k]
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        ind = len(ln) - len(ln.lstrip())
        if ind <= indent:
            break
        out.append((k, ln))
    return out


def _scalar_or_block(lines: list[str], idx: int) -> str:
    """Value of `key: v` at lines[idx]; supports `|`/`>` block scalars and quoted scalars."""
    ln = lines[idx]
    v = ln.split(":", 1)[1].strip()
    if v in ("|", "|-", ">", ">-", "|+"):
        indent = len(ln) - len(ln.lstrip())
        body = []
        for k in range(idx + 1, len(lines)):
            b = lines[k]
            if not b.strip():
                body.append("")
                continue
            if len(b) - len(b.lstrip()) <= indent:
                break
            body.append(b.strip())
        return "\n".join(body).strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v


# --------------------------------------------------------------------- Taskfile
def extract_taskfile(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    lines = _read(path)
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(path)) or "."
    for i, ln in enumerate(lines):
        if re.match(r"^tasks:\s*$", ln):
            for k, tl in _yaml_block(lines, i, "tasks"):
                m = re.match(r"^\s{2}([A-Za-z_][\w:-]*):\s*$", tl)
                if not m:
                    continue
                name = m.group(1)
                cmds: list[str] = []
                deps: list[str] = []
                for kk, sub in _yaml_block(lines, k, name):
                    s = sub.strip()
                    if s.startswith("- ") and not s.startswith("- task:"):
                        cmds.append(s[2:].strip().strip('"'))
                    elif s.startswith("- task:"):
                        deps.append(s.split(":", 1)[1].strip())
                    elif s.startswith("deps:") and "[" in s:
                        deps += [d.strip() for d in s.split("[", 1)[1].rstrip("]").split(",") if d.strip()]
                yield _cap(repo, "taskfile", name, "\n".join(cmds) or f"task {name}", cwd, f"{rel}:{k + 1}",
                           preconditions=["`task` on PATH"], depends_on=deps)


# --------------------------------------------------------------------- package.json
def extract_package_json(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(path)) or "."
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    lines = _read(path)
    for name, cmd in (data.get("scripts") or {}).items():
        if not isinstance(cmd, str):
            continue
        ln = next((i + 1 for i, l in enumerate(lines) if f'"{name}"' in l), 1)
        pre = ["node + package manager on PATH", "node_modules/ installed (npm install / yarn)"]
        cap = _cap(repo, "package_json", name, cmd, cwd, f"{rel}:{ln}", preconditions=pre)
        cap.notes.append(f"invoke: npm run {name}")
        yield cap


# --------------------------------------------------------------------- mix.exs
def extract_mix_exs(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    lines = _read(path)
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(path)) or "."
    text = "\n".join(lines)
    deps_ln = next((i + 1 for i, l in enumerate(lines) if re.search(r"defp?\s+deps\b", l)), 1)
    dep_names = re.findall(r"\{:([a-z_0-9]+)\s*,", text)
    pre = ["elixir + mix on PATH", "hex + rebar archives installed (mix local.hex / local.rebar)"]
    if "rustler" in text or "ggen_igniter" in dep_names:
        pre.append("rust/cargo toolchain (NIF dependency compiles at deps.compile)")
    yield _cap(repo, "mix_exs", "deps.get", "mix deps.get", cwd, f"{rel}:{deps_ln}",
               preconditions=pre, notes=[f"declared deps: {', '.join(dep_names)}"])
    yield _cap(repo, "mix_exs", "compile", "mix compile", cwd, f"{rel}:{deps_ln}", preconditions=pre + ["deps fetched"])
    yield _cap(repo, "mix_exs", "test", "mix test", cwd, f"{rel}:{deps_ln}", preconditions=pre + ["deps fetched"])
    for i, l in enumerate(lines):
        if re.search(r"defp?\s+aliases\b", l) or re.search(r"\baliases:\s*\[", l):
            block = _read_until_balanced(lines, i)
            for m in re.finditer(r"\"?([a-z_][\w.]*)\"?:\s*(\[[^\]]*\]|\"[^\"]*\"|&\S+)", block):
                yield _cap(repo, "mix_exs", f"alias:{m.group(1)}", f"mix {m.group(1)}", cwd, f"{rel}:{i + 1}",
                           preconditions=pre, notes=[f"alias body: {m.group(2)}"])
            break


def _read_until_balanced(lines: list[str], start: int, max_lines: int = 60) -> str:
    return "\n".join(lines[start:start + max_lines])


# --------------------------------------------------------------------- Cargo
def extract_cargo_toml(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(path)) or "."
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            yield _cap(repo, "cargo_toml", "unparseable", f"cargo metadata --manifest-path {rel}", cwd, f"{rel}:1",
                       notes=[f"TOML parse error: {e}"])
            return
    lines = _read(path)
    pkg = data.get("package", {})
    ws = data.get("workspace")
    name = pkg.get("name", os.path.basename(os.path.dirname(path)))
    pre = ["cargo + rustc on PATH"]
    rtc = os.path.join(os.path.dirname(path), "rust-toolchain.toml")
    if os.path.exists(rtc):
        pre.append(f"rust-toolchain pinned: {_rel(root, rtc)}")
    if ws and not pkg:
        members = ws.get("members", [])
        ln = next((i + 1 for i, l in enumerate(lines) if l.strip().startswith("[workspace]")), 1)
        yield _cap(repo, "cargo_toml", f"{name}:build-workspace", "cargo build --workspace", cwd, f"{rel}:{ln}",
                   preconditions=pre, notes=[f"members: {', '.join(members)}", f"exclude: {', '.join(ws.get('exclude', []))}"])
        yield _cap(repo, "cargo_toml", f"{name}:test-workspace", "cargo test --workspace", cwd, f"{rel}:{ln}", preconditions=pre)
        for mem in members:
            mp = os.path.join(os.path.dirname(path), mem, "Cargo.toml")
            if os.path.exists(mp):
                yield from extract_cargo_toml(repo, root, mp)
        return
    ln = next((i + 1 for i, l in enumerate(lines) if l.strip().startswith("[package]")), 1)
    yield _cap(repo, "cargo_toml", f"{name}:build", "cargo build", cwd, f"{rel}:{ln}", preconditions=pre)
    yield _cap(repo, "cargo_toml", f"{name}:test", "cargo test", cwd, f"{rel}:{ln}", preconditions=pre)
    bins = data.get("bin", [])
    has_release = "release" in (data.get("profile") or {})
    if bins or has_release:
        bln = next((i + 1 for i, l in enumerate(lines) if l.strip().startswith("[[bin]]") or l.strip().startswith("[profile.release]")), ln)
        yield _cap(repo, "cargo_toml", f"{name}:build-release", "cargo build --release", cwd, f"{rel}:{bln}", preconditions=pre,
                   notes=[f"bins: {', '.join(b.get('name', '?') for b in bins)}" if bins else "profile.release declared"])
    lib = data.get("lib", {})
    if "cdylib" in lib.get("crate-type", []):
        yield _cap(repo, "cargo_toml", f"{name}:build-wasm", "cargo build --release --target wasm32-wasip1", cwd, f"{rel}:{ln}",
                   preconditions=pre + ["rustup target wasm32-wasip1 installed"], notes=["cdylib crate-type (wasm/NIF candidate)"])


def extract_cargo_config(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(os.path.dirname(path))) or "."
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            return
    lines = _read(path)
    for alias, expansion in (data.get("alias") or {}).items():
        exp = " ".join(expansion) if isinstance(expansion, list) else str(expansion)
        ln = next((i + 1 for i, l in enumerate(lines) if l.strip().startswith(alias)), 1)
        yield _cap(repo, "cargo_config", f"alias:{alias}", f"cargo {exp}", cwd, f"{rel}:{ln}",
                   preconditions=["cargo on PATH"], notes=[f"invoke: cargo {alias}"])


# --------------------------------------------------------------------- pyproject
def extract_pyproject(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(path)) or "."
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            yield _cap(repo, "pyproject", "unparseable", "python3 -c 'import tomllib'", cwd, f"{rel}:1", notes=[str(e)])
            return
    lines = _read(path)
    proj = data.get("project", {})
    pre = ["python >= " + str(proj.get("requires-python", "3")).lstrip(">= "), "project installed in env (uv sync / pip install -e .)"]
    for name, target in (proj.get("scripts") or {}).items():
        ln = next((i + 1 for i, l in enumerate(lines) if l.strip().startswith(name)), 1)
        yield _cap(repo, "pyproject", f"script:{name}", f"{name} --help", cwd, f"{rel}:{ln}", preconditions=pre,
                   notes=[f"entry: {target}"])
    for group, eps in (proj.get("entry-points") or {}).items():
        ln = next((i + 1 for i, l in enumerate(lines) if group in l and "entry-points" in l), 1)
        yield _cap(repo, "pyproject", f"entry-points:{group}",
                   f"python3 -c \"from importlib.metadata import entry_points; print(sorted(e.name for e in entry_points(group='{group}')))\"",
                   cwd, f"{rel}:{ln}", preconditions=pre, notes=[f"{len(eps)} entry points: {', '.join(list(eps)[:12])}"])
    tool = data.get("tool", {})
    if "pytest" in tool or any("pytest" in str(v) for v in (data.get("dependency-groups") or {}).values()):
        ln = next((i + 1 for i, l in enumerate(lines) if "pytest" in l), 1)
        yield _cap(repo, "pyproject", "pytest", "python3 -m pytest", cwd, f"{rel}:{ln}", preconditions=pre)
    if "poe" in tool:
        for name, task in (tool["poe"].get("tasks") or {}).items():
            cmd = task if isinstance(task, str) else str(task.get("cmd") or task.get("shell") or task.get("script") or name)
            ln = next((i + 1 for i, l in enumerate(lines) if l.strip().startswith(name)), 1)
            yield _cap(repo, "pyproject", f"poe:{name}", cmd, cwd, f"{rel}:{ln}", preconditions=pre)


# --------------------------------------------------------------------- GitHub Actions
def extract_github_workflow(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    lines = _read(path)
    rel = _rel(root, path)
    wf = os.path.basename(path)
    triggers = []
    for i, ln in enumerate(lines[:80]):
        if re.match(r"^on:\s*$", ln):
            triggers = [re.match(r"^\s+([a-z_]+):", t).group(1) for _, t in _yaml_block(lines, i, "on") if re.match(r"^\s{2}[a-z_]+:", t)]
        elif re.match(r"^on:\s*\[", ln):
            triggers = [t.strip() for t in ln.split("[", 1)[1].rstrip("] ").split(",")]
    if "workflow_dispatch" in triggers:
        yield _cap(repo, "github_workflow", f"{wf}:dispatch", f"gh workflow run {wf}", ".", f"{rel}:1",
                   preconditions=["gh authenticated", "workflow_dispatch trigger declared"], notes=[f"triggers: {', '.join(triggers)}"])
    jobs_idx = next((i for i, l in enumerate(lines) if re.match(r"^jobs:\s*$", l)), None)
    if jobs_idx is None:
        return
    for jl, jline in _yaml_block(lines, jobs_idx, "jobs"):
        jm = re.match(r"^\s{2}([A-Za-z_][\w-]*):\s*$", jline)
        if not jm:
            continue
        job = jm.group(1)
        job_lines = _yaml_block(lines, jl, job)
        runs_on = next((_scalar_or_block(lines, k) for k, t in job_lines if re.match(r"^\s{4}runs-on:", t)), "?")
        step_no = 0
        step_name = ""
        uses: list[str] = []
        in_steps = False
        for k, t in job_lines:
            if re.match(r"^\s{4}steps:\s*$", t):
                in_steps = True
                continue
            if re.match(r"^\s{4}\S", t):
                in_steps = False
            if not in_steps:
                continue
            if re.match(r"^\s{6}- ", t):
                step_no += 1
                step_name = ""
            if re.match(r"^\s{6,8}(- )?name:", t):
                step_name = _scalar_or_block(lines, k)
            if re.match(r"^\s{6,8}(- )?uses:", t):
                uses.append(_scalar_or_block(lines, k).split("#")[0].strip())
            if re.match(r"^\s{6,8}(- )?run:", t):
                cmd = _scalar_or_block(lines, k)
                wd = next((_scalar_or_block(lines, kk) for kk, tt in job_lines if kk > k and kk < k + 12 and re.match(r"^\s{8}working-directory:", tt)), ".")
                nm = step_name or f"step{step_no}"
                cap = _cap(repo, "github_workflow", f"{wf}:{job}:{nm}", cmd, wd, f"{rel}:{k + 1}",
                           preconditions=[f"CI runner: {runs_on}", "prior steps of job '%s' completed" % job] + [f"uses: {u}" for u in uses[-3:]],
                           notes=[f"job={job} step={step_no}"])
                yield cap


# --------------------------------------------------------------------- Docker
def extract_dockerfile(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    lines = _read(path)
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(path)) or "."
    stages = []
    for i, ln in enumerate(lines):
        m = re.match(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", ln, re.IGNORECASE)
        if m:
            stages.append((i + 1, m.group(1), m.group(2)))
    fname = os.path.basename(path)
    for ln, base, stage in stages:
        target = f" --target {stage}" if stage else ""
        yield _cap(repo, "dockerfile", f"{fname}:build{(':' + stage) if stage else ''}",
                   f"docker build -f {fname}{target} .", cwd, f"{rel}:{ln}",
                   preconditions=["docker daemon running", f"base image pullable: {base}"], notes=[f"stage={stage or 'final'}"])
    cmd_ln = next((i + 1 for i, l in enumerate(lines) if re.match(r"^(CMD|ENTRYPOINT)\b", l)), None)
    if cmd_ln:
        yield _cap(repo, "dockerfile", f"{fname}:run", f"docker run --rm $(docker build -q -f {fname} .)", cwd, f"{rel}:{cmd_ln}",
                   preconditions=["image built"], notes=[lines[cmd_ln - 1].strip()])


def extract_compose(repo: str, root: str, path: str) -> Iterator[CandidateCapability]:
    lines = _read(path)
    rel = _rel(root, path)
    cwd = _rel(root, os.path.dirname(path)) or "."
    fname = os.path.basename(path)
    for i, ln in enumerate(lines):
        if re.match(r"^services:\s*$", ln):
            for k, t in _yaml_block(lines, i, "services"):
                m = re.match(r"^\s{2}([A-Za-z_][\w.-]*):\s*$", t)
                if m:
                    svc = m.group(1)
                    yield _cap(repo, "compose", f"{fname}:{svc}", f"docker compose -f {fname} up -d {svc}", cwd, f"{rel}:{k + 1}",
                               preconditions=["docker daemon running", "docker compose plugin"])
            break


# --------------------------------------------------------------------- Terraform
def extract_terraform_dir(repo: str, root: str, dirpath: str, tf_files: list[str]) -> Iterator[CandidateCapability]:
    cwd = _rel(root, dirpath) or "."
    main = sorted(tf_files)[0]
    rel = _rel(root, os.path.join(dirpath, main))
    providers = []
    for f in tf_files:
        for ln in _read(os.path.join(dirpath, f)):
            m = re.match(r"^\s*(google|aws|azurerm|kubernetes|helm|github|random|null|local)\s*=\s*\{", ln)
            if m:
                providers.append(m.group(1))
    pre = ["terraform on PATH"] + ([f"providers: {', '.join(sorted(set(providers)))}"] if providers else [])
    for verb in ("init", "validate", "plan", "apply", "destroy"):
        p = list(pre)
        if verb in ("plan", "apply", "destroy"):
            p.append("cloud credentials in env")
        if verb != "init":
            p.append(".terraform/ initialized")
        yield _cap(repo, "terraform", f"{cwd}:{verb}", f"terraform {verb}" + (" -auto-approve" if verb in ("apply", "destroy") else ""),
                   cwd, f"{rel}:1", preconditions=p)


# --------------------------------------------------------------------- CLI --help (opt-in, PATH only)
_CLI_HEAD = re.compile(r"^(?:cd\s+\S+\s*(?:&&)?\s*)?([A-Za-z][\w.+-]*)")
_CLI_DENY = {"cd", "echo", "export", "set", "if", "then", "else", "fi", "for", "while", "do", "done", "true", "false", "test",
             "python", "python3", "bash", "sh", "zsh", "touch", "printf", "mkdir", "cat", "mv", "cp", "rm", "grep", "find",
             "env", "tar", "command", "import", "prune", "route", "profiles", "patch", "bundle", "cpp", "sha256sum",
             "sudo", "chmod", "chown", "tree", "sleep", "exit", "source", "read", "wc", "head", "tail", "sort", "sed", "awk",
             "ls", "date", "which", "xargs", "tee", "cut", "tr", "basename", "dirname", "ln", "ps", "kill", "uname"}
_CLI_SYSTEM_DIRS = ("/bin/", "/usr/bin/", "/sbin/", "/usr/sbin/")


def declared_cli_binaries(caps: list[CandidateCapability]) -> list[str]:
    seen: list[str] = []
    for c in caps:
        for ln in c.command.splitlines():
            for part in re.split(r"\s*(?:&&|\|\||;)\s*", ln.strip().lstrip("@-+ ")):
                m = _CLI_HEAD.match(part)
                if not m:
                    continue
                b = m.group(1)
                if b in _CLI_DENY or b.startswith("$") or b.startswith("{{"):
                    continue
                if b not in seen:
                    seen.append(b)
        if c.source_kind == "pyproject" and c.name.startswith("script:"):
            b = c.name.split(":", 1)[1]
            if b not in seen:
                seen.append(b)
    return seen


def extract_cli_help(repo: str, binaries: list[str], scratch_cwd: str, timeout: float = 10.0) -> Iterator[CandidateCapability]:
    for b in binaries:
        exe = shutil.which(b)
        if not exe or exe.startswith(_CLI_SYSTEM_DIRS) and b != "curl":
            continue
        try:
            r = subprocess.run([exe, "--help"], cwd=scratch_cwd, capture_output=True, text=True, timeout=timeout, env={**os.environ, "NO_COLOR": "1"})
            out = (r.stdout or r.stderr).strip()
            excerpt = "\n".join(out.splitlines()[:12])
            status = f"exit={r.returncode}"
        except subprocess.TimeoutExpired:
            excerpt, status = "", f"timeout>{timeout}s"
        except OSError as e:
            excerpt, status = "", f"oserror:{e}"
        cap = _cap(repo, "cli_help", b, f"{b} --help", ".", f"PATH:{exe}", preconditions=[f"binary on PATH: {exe}"],
                   help_excerpt=excerpt, notes=[status])
        # `--help` itself is always a read; the binary's other verbs are classified where they are invoked.
        cap.authority_class, cap.reversibility, cap.effects = "READ", "IDEMPOTENT", []
        cap.qualification_strategy = RULES["qualification_by_class"]["READ"]
        yield cap
