#!/bin/bash
# Build the worked example end to end: extract -> build -> A4 page check.
#
#   bash example/run.sh          HTML, then measure every page against A4
#   bash example/run.sh --png    ... and render every page as a PNG to look at
#   bash example/run.sh --pdf    ... and convert to a PDF at 192 dpi
#
# Everything lands in example/out/. The RTL in example/rtl/ is a set of stubs:
# real interfaces, empty bodies, enough for the whole flow to run.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
SCRIPTS=$(cd "$HERE/../scripts" && pwd)
PY=${PY:-python3}
OUT=$HERE/out
mkdir -p "$OUT"
cd "$OUT"

# An explicit file list, never a glob - see "do not glob" in SKILL.md.
FILES=$(sed -e '/^\s*$/d' -e "s|^|$HERE/rtl/|" "$HERE/rtl/files.f")
# shellcheck disable=SC2086
"$PY" "$SCRIPTS/extract.py" $FILES > modules.json
PYTHONPATH="$SCRIPTS" "$PY" "$HERE/build.py"
"$PY" "$SCRIPTS/topdf.py" example_datasheet_manual.html --check

case "${1:-}" in
    --png) "$PY" "$SCRIPTS/topdf.py" example_datasheet_manual.html --png ;;
    --pdf) "$PY" "$SCRIPTS/topdf.py" example_datasheet_manual.html --scale 2 ;;
    "")    ;;
    *)     echo "unknown option: $1" >&2; exit 2 ;;
esac
