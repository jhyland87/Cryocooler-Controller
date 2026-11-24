# Shortcuts for the KiCad fab export (hardware/kicad/tools/export_fab.py) and the
# hardware checks. Run `make` or `make help` for the list. Override the board with
# BOARD=path, the KiCad binaries with KICAD_CLI= and KICAD_PYTHON= (a Python with pcbnew).

TOOLS := hardware/kicad/tools
BOARD ?= hardware/kicad/cryocooler.kicad_pcb
BOARD_ABS := $(abspath $(BOARD))
KICAD_CLI ?= /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
KICAD_PYTHON ?= /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
SCH_DIR := hardware/kicad
SCH := cryocooler.kicad_sch
OUT ?= build/hardware-checks
OUT_ABS := $(abspath $(OUT))
EXPORT_FAB = cd $(TOOLS) && python3 -c "from pathlib import Path; import export_fab as f; b = Path('$(BOARD_ABS)');

.DEFAULT_GOAL := help
.PHONY: help fab gerbers renders fab-imu sch-checks drc checks

help:
	@echo "make fab       Gerbers, drills, JLCPCB zip and renders (about 30 s)"
	@echo "make gerbers   Gerbers, drills and JLCPCB zip only, no renders"
	@echo "make renders   board renders only"
	@echo "make fab-imu   full export of the IMU board"
	@echo "make sch-checks  ERC, netlist, datasheet rules, netlist and symbol checks"
	@echo "make drc         DRC with schematic parity and a tally"
	@echo "make checks      sch-checks, drc and board_checks.py (when present)"
	@echo "OUT=dir sets where check output goes (default $(OUT))"
	@echo "BOARD=path.kicad_pcb picks another board (default $(BOARD))"

fab:
	python3 $(TOOLS)/export_fab.py $(BOARD_ABS)

gerbers:
	$(EXPORT_FAB) f.export_gerbers(b); f.build_zip(b); print('gerbers and zip written to', f.fab_dir(b))"

renders:
	$(EXPORT_FAB) f.render_board(b); print('renders written to', f.fab_dir(b))"

fab-imu:
	$(MAKE) fab BOARD=hardware/kicad/imu/imu.kicad_pcb

sch-checks:
	mkdir -p $(OUT_ABS)
	cd $(SCH_DIR) && $(KICAD_CLI) sch erc --severity-all --exit-code-violations --format json -o $(OUT_ABS)/erc.json $(SCH)
	cd $(SCH_DIR) && $(KICAD_CLI) sch export netlist --format kicadsexpr -o $(OUT_ABS)/new.net $(SCH)
	cd $(SCH_DIR) && python3 tools/datasheet_rules.py $(OUT_ABS)/new.net
	cd $(SCH_DIR) && python3 tools/verify_netlist.py $(OUT_ABS)/new.net
	cd $(SCH_DIR) && python3 tools/check_symbols.py $(SCH)
	cd $(SCH_DIR) && python3 tools/check_sheet_structure.py

# Fails on any error, unconnected item or parity item; warnings are only counted.
drc:
	mkdir -p $(OUT_ABS)
	$(KICAD_CLI) pcb drc --schematic-parity --severity-all --format json -o $(OUT_ABS)/drc.json $(BOARD_ABS)
	python3 -c "import json,collections,sys; d=json.load(open(sys.argv[1])); u=len(d['unconnected_items']); p=len(d.get('schematic_parity', [])); c=collections.Counter((v['severity'], v['type']) for v in d['violations']); print('unconnected', u, 'parity', p); print(c); sys.exit(1 if u or p or any(k[0]=='error' for k in c) else 0)" $(OUT_ABS)/drc.json

checks: sch-checks drc
	@if [ -f $(TOOLS)/board_checks.py ] && grep -q '(segment' $(BOARD_ABS); then \
		$(KICAD_PYTHON) $(TOOLS)/board_checks.py $(BOARD_ABS); \
	else echo "board_checks.py skipped: script missing or board has no tracks"; fi
