# Simulation models

- `ad633_behavioral.lib` - hand-written AD633 stand-in (W = X*Y/10, rail-limited). Not an Analog Devices model.
- `ti_original/OPA1656.LIB`, `ti_original/OPAx188.LIB` - Texas Instruments SPICE models. Not committed:
  download them from the OPA1656 and OPA188 product pages on ti.com (Design tools & simulation,
  SPICE model) and put the `.LIB` files in `ti_original/`. `cryocooler_sim.kicad_sch` references them
  through its Sim.Library fields.
- `opa1656.lib`, `opax188.lib` - ngspice-converted copies made by `../prep_models.py`. They did not converge
  in the headless runner; KiCad's own simulator runs the originals.
