#!/usr/bin/env bash
set -euo pipefail

readonly GGEN_VERSION="v26.8.8"

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
    echo "REFUSED:UNSUPPORTED_GGEN_VERIFIER_PLATFORM $(uname -s)/$(uname -m)" >&2
    exit 2
    ;;
esac

readonly asset sha256
readonly url="https://github.com/seanchatmangpt/ggen/releases/download/${GGEN_VERSION}/${asset}"
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT
archive="${workdir}/${asset}"

curl --fail --location --retry 3 --silent --show-error \
  "${url}" \
  --output "${archive}"
printf '%s  %s\n' "${sha256}" "${archive}" | sha256sum --check --strict

tar -xzf "${archive}" -C "${workdir}"
ggen_bin="$(find "${workdir}" -type f -name ggen -print -quit)"
if [[ -z "${ggen_bin}" ]]; then
  echo "REFUSED:GGEN_BINARY_NOT_FOUND" >&2
  exit 3
fi
chmod +x "${ggen_bin}"

"${ggen_bin}" sync run

git diff --exit-code -- \
  src/autofde_lab/constitution \
  tests/constitution/test_semantic_constitution.py

python -m compileall -q \
  src/autofde_lab/constitution \
  tests/constitution/test_semantic_constitution.py
PYTHONPATH=src python -m pytest -q tests/constitution/test_semantic_constitution.py
