#!/bin/sh
# Build (all specs, or the named ones) into OUT, then ERC + netlist check + PDF.
# Usage: tools/check.sh OUT_DIR [spec ...]
set -e
OUT=${1:?output dir}; shift
cd "$(dirname "$0")/.."
mkdir -p "$OUT"
OEM_KICAD_OUT="$OUT" python3 -I tools/gen_oem_schematic.py "$@"
kicad-cli sch erc --severity-all --format json -o "$OUT/erc.json" "$OUT/oem-controller.kicad_sch" >/dev/null
python3 -I tools/erc_summary.py "$OUT/erc.json"
kicad-cli sch export netlist --format kicadsexpr -o "$OUT/net.net" "$OUT/oem-controller.kicad_sch" >/dev/null
OEM_ONLY="$*" python3 -I tools/verify_netlist.py "$OUT/net.net"
kicad-cli sch export pdf -o "$OUT/schematic.pdf" "$OUT/oem-controller.kicad_sch" >/dev/null
echo "pdf: $OUT/schematic.pdf (page 1 root, 2 patent sheet, 3+ figures in order)"
