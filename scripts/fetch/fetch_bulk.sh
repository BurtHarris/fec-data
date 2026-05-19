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
    if [[ -f "${ZIP}" ]]; then
        echo "[SKIP]  ${NAME}.zip already exists"
    else
        echo "[GET]   ${NAME}.zip"
        curl -L --progress-bar -o "${ZIP}" "${BASE_URL}/${NAME}.zip"
    fi
    echo "[UNZIP] ${NAME}.zip"
    unzip -o -q -d "${DEST}" "${ZIP}"
    echo "[OK]    ${NAME} done"
    echo ""

    # Optional: Remove ZIP file after extraction
    # rm -f "${ZIP}"
done

echo "All files ready in ${DEST}/"
ls -lh "${DEST}/"