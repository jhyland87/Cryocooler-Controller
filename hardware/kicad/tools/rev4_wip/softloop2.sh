#!/bin/bash
# softloop2.sh 'NET|NET' : rip-up route the nets, then re-route only what that displaced
S=${SCRATCH:?set SCRATCH to the work directory, see hardware/HANDOFF_ucs125_rev4.md}
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
W=$S/kicad; B=$W/cryocooler.kicad_pcb; D=$S/out/drc.json
F='swig/python|wxApp|Debug:|^$'
drc() { $KC pcb drc --schematic-parity --severity-all --format json -o $D $B >/dev/null 2>&1; }
cd $W/tools
drc
MAX_EXPAND=${MAX_EXPAND:-20000000} PYTHONPATH=$W/tools $KPY $S/soft8.py $B $D "$1" > $S/out/soft.log 2>&1
grep -Ev "$F" $S/out/soft.log
DISPLACED=$(grep "^displaced:" $S/out/soft.log | sed 's/^displaced: *//')
if [ -n "$DISPLACED" ]; then
  drc
  ONLY=1 BRIDGE=0 MAX_EXPAND=20000000 PYTHONPATH=$W/tools $KPY $S/route_loop.py $B $D "$DISPLACED" > $S/out/reroute.log 2>&1
  grep -Ev "$F" $S/out/reroute.log | grep -v "^group"
fi
$KPY $S/prune_all.py $B 2>&1 | grep -Ev "$F" | tail -1
drc
python3 $S/drcsum.py $D | grep -v "silk\|lib_footprint"
