# Shortcuts for the KiCad fab export (hardware/kicad/tools/export_fab.py).
# Run `make` or `make help` for the list. Override the board with BOARD=path.

TOOLS := hardware/kicad/tools
BOARD ?= hardware/kicad/cryocooler.kicad_pcb
BOARD_ABS := $(abspath $(BOARD))
EXPORT_FAB = cd $(TOOLS) && python3 -c "from pathlib import Path; import export_fab as f; b = Path('$(BOARD_ABS)');

.DEFAULT_GOAL := help
.PHONY: help fab gerbers renders fab-imu

help:
	@echo "make fab       Gerbers, drills, JLCPCB zip and renders (about 30 s)"
	@echo "make gerbers   Gerbers, drills and JLCPCB zip only, no renders"
	@echo "make renders   board renders only"
	@echo "make fab-imu   full export of the IMU board"
	@echo "BOARD=path.kicad_pcb picks another board (default $(BOARD))"

fab:
	python3 $(TOOLS)/export_fab.py $(BOARD_ABS)

gerbers:
	$(EXPORT_FAB) f.export_gerbers(b); f.build_zip(b); print('gerbers and zip written to', f.fab_dir(b))"

renders:
	$(EXPORT_FAB) f.render_board(b); print('renders written to', f.fab_dir(b))"

fab-imu:
	$(MAKE) fab BOARD=hardware/kicad/imu/imu.kicad_pcb
