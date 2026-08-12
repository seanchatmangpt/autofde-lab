#!/usr/bin/env bash
set -euo pipefail

readonly GGEN_VERSION="v26.8.8"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_root="${repo_root}/ggen/fortune5"

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
    echo "REFUSED:UNSUPPORTED_GGEN_VERIFIER_PLATFORM:$(uname -s)/$(uname -m)" >&2
    exit 2
    ;;
esac

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
archive="${workdir}/${asset}"
project="${workdir}/project"
mkdir -p "${project}"
cp "${source_root}/ggen.toml" "${project}/ggen.toml"
cp -R "${source_root}/ontology" "${project}/ontology"
cp -R "${source_root}/templates" "${project}/templates"

curl --fail --location --retry 3 --silent --show-error \
  "https://github.com/seanchatmangpt/ggen/releases/download/${GGEN_VERSION}/${asset}" \
  --output "${archive}"
actual_sha256="$(python - "${archive}" <<'PY'
import hashlib
from pathlib import Path
import sys

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"
if [[ "${actual_sha256}" != "${sha256}" ]]; then
  echo "REFUSED:GGEN_ASSET_DIGEST_DRIFT:${actual_sha256}!=${sha256}" >&2
  exit 3
fi

tar -xzf "${archive}" -C "${workdir}"
ggen_bin="$(find "${workdir}" -type f -name ggen -print -quit)"
if [[ -z "${ggen_bin}" ]]; then
  echo "REFUSED:GGEN_BINARY_NOT_FOUND" >&2
  exit 4
fi
chmod +x "${ggen_bin}"

run_ggen() {
  python - "${ggen_bin}" "${project}" <<'PY'
from pathlib import Path
import subprocess
import sys

binary, project = sys.argv[1:]
try:
    completed = subprocess.run(
        [binary, "sync", "run"],
        cwd=Path(project),
        check=False,
        timeout=5,
    )
except subprocess.TimeoutExpired as exc:
    raise SystemExit("REFUSED:GGEN_FIVE_SECOND_BUDGET_EXCEEDED") from exc
if completed.returncode != 0:
    raise SystemExit(completed.returncode)
PY
}

manifest() {
  python - "${project}" <<'PY'
import hashlib
from pathlib import Path
import sys

root = Path(sys.argv[1])
for name in ("catalog.py", "test_fortune5_laws.py"):
    path = root / name
    if not path.is_file():
        raise SystemExit(f"REFUSED:GGEN_OUTPUT_MISSING:{name}")
    print(f"{name}:{hashlib.sha256(path.read_bytes()).hexdigest()}")
PY
}

run_ggen
first_manifest="$(manifest)"
run_ggen
second_manifest="$(manifest)"
if [[ "${first_manifest}" != "${second_manifest}" ]]; then
  echo "REFUSED:GGEN_NONDETERMINISTIC_FORTUNE5_MANUFACTURE" >&2
  printf 'first:\n%s\nsecond:\n%s\n' "${first_manifest}" "${second_manifest}" >&2
  exit 5
fi

python - \
  "${repo_root}/src/autofde_lab/fortune5/catalog.py" \
  "${project}/catalog.py" <<'PY'
import ast
from pathlib import Path
import sys


def rows(path: str):
    tree = ast.parse(Path(path).read_text(), filename=path)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "CATALOG_ROWS":
                return ast.literal_eval(node.value)
    raise SystemExit(f"REFUSED:CATALOG_ROWS_MISSING:{path}")

committed, manufactured = map(rows, sys.argv[1:])
if committed != manufactured:
    raise SystemExit("REFUSED:GGEN_FORTUNE5_PROJECTION_DRIFT")
print(f"fortune5_catalog_rows={len(committed)}")
PY

PYTHONPATH="${repo_root}/src" python -m pytest -q \
  "${project}/test_fortune5_laws.py" \
  "${repo_root}/tests/fortune5/test_space.py"

printf 'FORTUNE5_GGEN_ALIVE version=%s\n%s\n' "${GGEN_VERSION}" "${second_manifest}"
