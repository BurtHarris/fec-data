#!/usr/bin/env bash
# =============================================================================
# fec_bulk_download.sh
#
# Downloads FEC bulk data files for a given election cycle.
#
# Usage:
#   ./fec_bulk_download.sh <cycle>
#
#   <cycle>  Required. Four-digit election year, e.g. 2026 or 2020.
#
# Examples:
#   ./fec_bulk_download.sh 2026
#     → stores files in data/raw/2026/
#
# Requires: curl, unzip
# =============================================================================

set -euo pipefail

get_remote_signature() {
    local url="$1"
    local headers

    # Follow redirects and collect the final response headers.
    headers="$(curl -fsSLI "$url" | tr -d '\r')"

    local etag
    local last_modified
    local content_length

    etag="$(printf '%s\n' "$headers" | awk -F': ' 'tolower($1)=="etag" {print $2}' | tail -n1)"
    last_modified="$(printf '%s\n' "$headers" | awk -F': ' 'tolower($1)=="last-modified" {print $2}' | tail -n1)"
    content_length="$(printf '%s\n' "$headers" | awk -F': ' 'tolower($1)=="content-length" {print $2}' | tail -n1)"

    printf '%s|%s|%s\n' "$etag" "$last_modified" "$content_length"
}

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <cycle>"
    echo "  e.g. $0 2026"
    exit 1
fi

CYCLE="$1"
YY="${CYCLE:2}"
BASE_URL="https://www.fec.gov/files/bulk-downloads/${CYCLE}"
DEST="data/raw/${CYCLE}"

mkdir -p "${DEST}"

FILES=(
    "weball${YY}"   # Candidate summary totals
    "indiv${YY}"    # Individual contributions (Schedule A)
    "oppexp${YY}"   # Operating expenditures (Schedule B)
    "pas2${YY}"     # Committee-to-committee contributions
    "oth${YY}"      # Inter-committee transfers
    "cm${YY}"       # Committee master
    "cn${YY}"       # Candidate master
)

echo "Downloading FEC bulk data — cycle ${CYCLE}"
echo "Destination: ${DEST}"
echo ""

for NAME in "${FILES[@]}"; do
    ZIP="${DEST}/${NAME}.zip"
    URL="${BASE_URL}/${NAME}.zip"
    META="${DEST}/.${NAME}.meta"

    REMOTE_SIG="$(get_remote_signature "${URL}")"
    PREV_SIG=""

    if [[ -f "${META}" ]]; then
        PREV_SIG="$(<"${META}")"
    fi

    if [[ -f "${ZIP}" && -n "${PREV_SIG}" && "${REMOTE_SIG}" == "${PREV_SIG}" ]]; then
        echo "[SKIP]  ${NAME}.zip unchanged on server"
        echo "[SKIP]  ${NAME} extract unchanged"
        echo ""
        continue
    fi

    echo "[GET]   ${NAME}.zip"
    curl -fL --progress-bar -o "${ZIP}" "${URL}"

    echo "[UNZIP] ${NAME}.zip"
    unzip -o -q -d "${DEST}" "${ZIP}"

    printf '%s\n' "${REMOTE_SIG}" > "${META}"

    echo "[OK]    ${NAME} done"
    echo ""

    # Optional: Remove ZIP file after extraction
    # rm -f "${ZIP}"
done

echo "All files ready in ${DEST}/"
ls -lh "${DEST}/"