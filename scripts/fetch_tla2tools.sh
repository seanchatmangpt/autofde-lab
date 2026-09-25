#!/usr/bin/env bash
# Fetch the pinned tla2tools.jar (v1.7.4) into the user cache and verify it.
# Exits non-zero on any size or sha256 mismatch; the jar is never committed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="1.7.4"
url="https://github.com/tlaplus/tlaplus/releases/download/v${version}/tla2tools.jar"
expected_size=2274532
expected_sha="$(awk '{print $1}' "${here}/tools/tla/tla2tools-${version}.sha256")"
dest_dir="${AUTOFDE_TLA2TOOLS_CACHE:-${HOME}/.cache/autofde-lab/tla2tools/${version}}"
dest="${dest_dir}/tla2tools.jar"
mkdir -p "${dest_dir}"
if [[ ! -f "${dest}" ]]; then
  tmp="$(mktemp "${dest_dir}/tla2tools.jar.XXXXXX")"
  trap 'rm -f "${tmp}"' EXIT
  curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 --retry 3 \
    -o "${tmp}" "${url}"
  mv "${tmp}" "${dest}"
  trap - EXIT
fi
size="$(wc -c < "${dest}" | tr -d ' ')"
if [[ "${size}" != "${expected_size}" ]]; then
  echo "REFUSED: ${dest} size ${size} != ${expected_size}" >&2
  exit 2
fi
if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "${dest}" | awk '{print $1}')"
else
  actual="$(shasum -a 256 "${dest}" | awk '{print $1}')"
fi
if [[ "${actual}" != "${expected_sha}" ]]; then
  echo "REFUSED: ${dest} sha256 ${actual} != pinned ${expected_sha}" >&2
  exit 3
fi
echo "${dest}"
