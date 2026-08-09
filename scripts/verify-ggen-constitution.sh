#!/usr/bin/env bash
set -euo pipefail

readonly GGEN_VERSION="v26.8.8"
readonly ASSET_FETCH_TIMEOUT_SECONDS="30"
readonly ASSET_EXTRACT_TIMEOUT_SECONDS="10"
readonly GGEN_SYNC_TIMEOUT_SECONDS="20"
readonly COMPILE_TIMEOUT_SECONDS="10"
readonly TEST_TIMEOUT_SECONDS="30"

annotate() {
  local level="$1"
  local title="$2"
  local message="$3"
  printf '%s\n' "${title}: ${message}" >&2
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    message="${message//'%'/'%25'}"
    message="${message//$'\r'/'%0D'}"
    message="${message//$'\n'/'%0A'}"
    printf '::%s title=%s::%s\n' "${level}" "${title}" "${message}" >&2
  fi
}

bounded_exec() {
  local stage="$1"
  local timeout_seconds="$2"
  shift 2
  python - "${stage}" "${timeout_seconds}" "$@" <<'PY'
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

stage = sys.argv[1]
timeout = float(sys.argv[2])
command = sys.argv[3:]


def emit(title: str, message: str) -> None:
    print(f"{title}: {message}", file=sys.stderr)
    if os.environ.get("GITHUB_ACTIONS"):
        safe = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title={title}::{safe}", file=sys.stderr)


def descendants(root_pid: int) -> list[int]:
    completed = subprocess.run(
        ["ps", "-axo", "pid=,ppid="],
        check=False,
        capture_output=True,
        text=True,
    )
    children: dict[int, list[int]] = {}
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        pid, ppid = map(int, parts)
        children.setdefault(ppid, []).append(pid)
    found: list[int] = []
    stack = list(children.get(root_pid, ()))
    while stack:
        pid = stack.pop()
        found.append(pid)
        stack.extend(children.get(pid, ()))
    return found


def signal_pid(pid: int, sig: signal.Signals) -> None:
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        pass


def terminate_tree(root_pid: int) -> None:
    # Discover before terminating the root so children that created their own
    # sessions/process groups cannot escape by being re-parented first.
    targets = descendants(root_pid)
    for pid in reversed(targets):
        signal_pid(pid, signal.SIGTERM)
    signal_pid(root_pid, signal.SIGTERM)
    try:
        os.killpg(root_pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        alive = []
        for pid in [root_pid, *targets]:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            alive.append(pid)
        if not alive:
            return
        time.sleep(0.05)

    for pid in reversed(targets):
        signal_pid(pid, signal.SIGKILL)
    signal_pid(root_pid, signal.SIGKILL)
    try:
        os.killpg(root_pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


proc = subprocess.Popen(command, start_new_session=True)
try:
    returncode = proc.wait(timeout=timeout)
except subprocess.TimeoutExpired:
    terminate_tree(proc.pid)
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        pass
    title = f"REFUSED:{stage}_TIMEOUT"
    emit(title, f"timeout_seconds={timeout:g}")
    raise SystemExit(124)

if returncode != 0:
    title = f"REFUSED:{stage}_FAILED"
    emit(title, f"exit={returncode}")
    raise SystemExit(returncode or 126)
PY
}

case "$(uname -s)/$(uname -m)" in
  Linux/x86_64)
    asset="ggen-x86_64-unknown-linux-gnu.tar.gz"
    sha256="c651d873c2aeb6bd71c3d5356634f0b3f4adafd2454ee354c817a7079c2ea802"
    ;;
  Linux/aarch64|Linux/arm64)
    asset="ggen-aarch64-unknown-linux-gnu.tar.gz"
    sha256="c39d883b43aa6c635f5a490b7c203a1aaa6499e0df14b5d82d9dc4a26b8d22f6"
    ;;
  Darwin/arm64|Darwin/aarch64)
    asset="ggen-aarch64-apple-darwin.tar.gz"
    sha256="673c1b5e1aecc13fd848141e62ef6b2bb5b54f0eb653866826caa01e80aea3df"
    ;;
  Darwin/x86_64)
    asset="ggen-x86_64-apple-darwin.tar.gz"
    sha256="a4304371ce787e7bfe479fdba050960cdb8761fc9ca3d272da6bd7e64af08570"
    ;;
  *)
    annotate error "REFUSED:UNSUPPORTED_GGEN_VERIFIER_PLATFORM" "$(uname -s)/$(uname -m)"
    exit 2
    ;;
esac

readonly asset sha256
readonly url="https://github.com/seanchatmangpt/ggen/releases/download/${GGEN_VERSION}/${asset}"
readonly -a GENERATED_ROOTS=(
  "src/autofde_lab/constitution"
  "tests/constitution/test_semantic_constitution.py"
)

if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
  printf '::notice title=GGEN_CONSTITUTION_VERIFIER::started version=%s asset=%s\n' \
    "${GGEN_VERSION}" "${asset}"
fi

for forbidden in generated src/autofde_lab/generated; do
  if [[ -e "${forbidden}" ]]; then
    annotate error "REFUSED:GENERATED_NAMESPACE_FORBIDDEN" "${forbidden}"
    exit 3
  fi
done

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
archive="${workdir}/${asset}"

bounded_exec ASSET_FETCH "${ASSET_FETCH_TIMEOUT_SECONDS}" \
  curl --fail --location --retry 1 --silent --show-error \
  --connect-timeout 10 --max-time 25 \
  "${url}" \
  --output "${archive}"

actual_sha256="$(python - "${archive}" <<'PY'
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

path = Path(sys.argv[1])
h = hashlib.sha256()
with path.open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(chunk)
print(h.hexdigest())
PY
)"
if [[ "${actual_sha256}" != "${sha256}" ]]; then
  annotate error \
    "REFUSED:GGEN_ASSET_DIGEST_DRIFT" \
    "actual=${actual_sha256} expected=${sha256}"
  exit 5
fi

bounded_exec ASSET_EXTRACT "${ASSET_EXTRACT_TIMEOUT_SECONDS}" \
  tar -xzf "${archive}" -C "${workdir}"
ggen_bin="$(find "${workdir}" -type f -name ggen -print -quit)"
if [[ -z "${ggen_bin}" ]]; then
  annotate error "REFUSED:GGEN_BINARY_NOT_FOUND" "asset=${asset}"
  exit 6
fi
chmod +x "${ggen_bin}"

projection_manifest() {
  python - "${GENERATED_ROOTS[@]}" <<'PY'
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

paths: list[Path] = []
for raw in sys.argv[1:]:
    root = Path(raw)
    if root.is_dir():
        paths.extend(path for path in root.rglob("*") if path.is_file())
    elif root.is_file():
        paths.append(root)
    else:
        raise SystemExit(f"REFUSED:GENERATED_PROJECTION_MISSING:{root}")

for path in sorted(paths, key=lambda item: item.as_posix()):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"{digest}  {path.as_posix()}")
PY
}

verify_clean_projection() {
  local changed
  changed="$(git diff --name-only -- "${GENERATED_ROOTS[@]}")"
  if [[ -n "${changed}" ]]; then
    local compact
    compact="$(printf '%s\n' "${changed}" | paste -sd, -)"
    annotate error "REFUSED:GGEN_PROJECTION_DRIFT" "changed=${compact}"
    git diff --stat -- "${GENERATED_ROOTS[@]}" >&2 || true
    return 7
  fi
}

# Pass 1 proves committed projection correspondence.
bounded_exec GGEN_SYNC "${GGEN_SYNC_TIMEOUT_SECONDS}" "${ggen_bin}" sync run
verify_clean_projection
projection_manifest > "${workdir}/manifest-1.sha256"

# Pass 2 proves the manufacturer is idempotent at the exact same subject.
bounded_exec GGEN_SYNC "${GGEN_SYNC_TIMEOUT_SECONDS}" "${ggen_bin}" sync run
verify_clean_projection
projection_manifest > "${workdir}/manifest-2.sha256"
if ! cmp -s "${workdir}/manifest-1.sha256" "${workdir}/manifest-2.sha256"; then
  annotate error \
    "REFUSED:GGEN_NONDETERMINISTIC_PROJECTION" \
    "pass-1 and pass-2 projection manifests differ"
  diff -u "${workdir}/manifest-1.sha256" "${workdir}/manifest-2.sha256" >&2 || true
  exit 10
fi

bounded_exec COMPILE "${COMPILE_TIMEOUT_SECONDS}" \
  python -m compileall -q \
  src/autofde_lab/constitution \
  tests/constitution/test_semantic_constitution.py
bounded_exec CONSTITUTION_TEST "${TEST_TIMEOUT_SECONDS}" \
  env PYTHONPATH=src python -m pytest -q tests/constitution/test_semantic_constitution.py

if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
  printf '::notice title=GGEN_CONSTITUTION_VERIFIER::passed two-pass byte-identical manufacture\n'
fi
