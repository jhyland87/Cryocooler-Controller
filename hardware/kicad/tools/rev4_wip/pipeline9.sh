#!/bin/bash
# rev 3 copy -> place -> link -> plane ties -> prune the bottom wall -> route (bridges, net groups)
# -> prune -> leftovers -> prune -> rip-up routing of what is left -> DRC
S=${SCRATCH:?set SCRATCH to the work directory, see hardware/HANDOFF_ucs125_rev4.md}
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
W=$S/kicad; B=$W/cryocooler.kicad_pcb; D=$S/out/drc.json
F='swig/python|wxApp|Debug:|^$'
drc() { $KC pcb drc --schematic-parity --severity-all --format json -o $D $B >/dev/null 2>&1; }
cd $W
cp $S/rev3_board_backup.kicad_pcb $B
echo "== place"; $KPY tools/ucs125_rev4.py place $B 2>&1 | grep -Ev "$F" | grep -E "CONFLICT|problems|no free|incomplete|Trace|Error"
echo "== link"; SKIP_FAB_EXPORT=1 $KPY tools/gen_pcb.py link 2>&1 | grep -Ev "$F" | tail -2
drc
echo "== ties"; $KPY tools/plane_ties.py $B $D GND,+3V3 2>&1 | grep -Ev "$F" | grep -c "via"
echo "== prune bottom wall"; $KPY $S/prune_all.py $B 50,40,97,62 2>&1 | grep -Ev "$F" | tail -1
drc; python3 $S/drcsum.py $D | tail -2 | cut -c1-300
cp $B $S/pre_route9.kicad_pcb
echo "== route"
cd $W/tools
PYTHONPATH=$W/tools $KPY $S/route_loop.py $B $D "/Cold Head Temp/RTD_2,/Cold Head Temp/RTD_3,Net-(J1-*,USB_VBUS" "Net-(D8?-G?),Net-(U4??--),+5V_OR,/General Purpose IO/IO*_HDR" "/General Purpose IO/*,AUX_IO*,/Power Button/PWR_BTN" "ACS_*,SPI_*" > $S/out/route9.log 2>&1
grep -Ev "$F" $S/out/route9.log | grep "FAILED\|^group\|^saved"
cd $W
cp $B $S/routed9a.kicad_pcb
echo "== prune"; $KPY $S/prune_all.py $B 2>&1 | grep -Ev "$F" | tail -1
drc; python3 $S/drcsum.py $D | tail -2 | cut -c1-900
echo "== route leftovers (wider search)"
cd $W/tools
BRIDGE=0 MAX_EXPAND=30000000 PYTHONPATH=$W/tools $KPY $S/route_loop.py $B $D > $S/out/route9b.log 2>&1
grep -Ev "$F" $S/out/route9b.log | grep -v "^group"
cd $W
echo "== prune"; $KPY $S/prune_all.py $B 2>&1 | grep -Ev "$F" | tail -1
drc
python3 $S/drcsum.py $D | cut -c1-1200
cp $B $S/routed9.kicad_pcb
echo PIPELINE_DONE
