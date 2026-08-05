#!/usr/bin/env bash
set -euo pipefail

STOCKFISH_VERSION="sf_18"
ARCHIVE_NAME="stockfish-ubuntu-x86-64.tar"
ARCHIVE_SHA256="5c6f38b02a4da5f3ffe763f27da6c3e743eebefd92b50cb3661623b96696adff"
DOWNLOAD_URL="https://github.com/official-stockfish/Stockfish/releases/download/${STOCKFISH_VERSION}/${ARCHIVE_NAME}"
INSTALL_DIR="${1:-.stockfish}"
TARGET_PATH="${INSTALL_DIR}/stockfish"
TEMP_DIR="$(mktemp -d)"

cleanup() {
    rm -rf -- "${TEMP_DIR}"
}
trap cleanup EXIT

mkdir -p -- "${INSTALL_DIR}" "${TEMP_DIR}/extracted"
curl --fail --location --retry 3 --output "${TEMP_DIR}/${ARCHIVE_NAME}" "${DOWNLOAD_URL}"
printf '%s  %s\n' "${ARCHIVE_SHA256}" "${TEMP_DIR}/${ARCHIVE_NAME}" | sha256sum --check --status
tar -xf "${TEMP_DIR}/${ARCHIVE_NAME}" -C "${TEMP_DIR}/extracted"

BINARY_PATH="$(find "${TEMP_DIR}/extracted" -type f -name 'stockfish-ubuntu-x86-64' -print -quit)"
if [[ -z "${BINARY_PATH}" ]]; then
    echo "Stockfish executable was not found in ${ARCHIVE_NAME}." >&2
    exit 1
fi

install -m 0755 "${BINARY_PATH}" "${TARGET_PATH}"
UCI_OUTPUT="$(printf 'uci\nquit\n' | "${TARGET_PATH}")"
if ! grep -q '^uciok$' <<<"${UCI_OUTPUT}"; then
    echo "Installed Stockfish executable did not complete the UCI handshake." >&2
    exit 1
fi

echo "Installed Stockfish ${STOCKFISH_VERSION} at ${TARGET_PATH}."
