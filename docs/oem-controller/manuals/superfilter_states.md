# SuperFilter: cool-down state table

Source: *SuperFilter Operation/Install Guide* (STI 830-0010A, 9/21/00), copied here as
[SuperFilter_Operation_Install_Guide.pdf](SuperFilter_Operation_Install_Guide.pdf). It is a scanned document.
Page numbers are PDF pages. Diagram: [diagrams/superfilter_state_machine.drawio](diagrams/superfilter_state_machine.drawio).

## Table 9. Cool-Down State Table (PDF p33), transcribed from the image

| State No. | State Name | Bypass Relay State | FAULT | READY | Description |
|---|---|---|---|---|---|
| 0 | Initialize | Bypass | On ** | Off ** | Initial Power Up State |
| 1 | Idle | Bypass | On RED | Off | Cold stage is warm, Dewar is not cooling |
| 2 | Coarse Cool-down | Bypass | Flash Fast * RED | Off | Cooling, cold stage is above 85 K |
| 3 | Fine Cool-down | Bypass | Flash Fast * RED | Flash Slow * GREEN | Cooling, cold stage is below 85 K |
| 4 | Over shoot | Bypass | Flash Fast * RED | Flash Fast * GREEN | Cold stage is cooler than set point (nominally 78 K) and the control algorithm integrator is settling |
| 5 | Settle | Normal | Flash Fast * RED | Flash Fast * GREEN | Cold stage temperature is settling, circuits are switched to Normal |
| 6 | Baseline | Normal | Off | On GREEN | Cold stage temperature has settled and baseline data is being collected |
| 7 | Operating | Normal | Off | On GREEN | System is operating normally and being checked for deviations from the baseline |
| 8 | Fault | Bypass | On RED | Off | Alarm relay is switched on |

Note: \* = Fast Flash is twice per second, Slow Flash is once per second.
\*\* = On power up, both FAULT and READY Indicators will momentarily illuminate AMBER during System State zero (0).
(State 8 is printed as a separate box below states 0-7.) Table 14, "System State Machine", on p62 repeats this table.

## Related statements elsewhere in the guide

- **p14:** the unit is in Bypass on power-up and switches to Normal only when the CoRE reaches operating temperature. A problem such as losing temperature or power switches it back to Bypass automatically. `SET FORCED BYPASS ON` holds Bypass until `SET FORCED BYPASS OFF`.
- **p15:** input power, LNA voltage, driver current or CoRE temperature at an unacceptable level switches the unit to Bypass and activates the alarm relay.
- **p16, Figure 3:** the block diagram includes an **Overstroke Detector** under the cooler feeding the control electronics. See [diagrams/superfilter_fig3_functional_block.drawio](diagrams/superfilter_fig3_functional_block.drawio) and [../analysis/OVERSTROKE.md](../analysis/OVERSTROKE.md).
- **p32:** the cool-down "progresses through eight stages ... The system state machine controls the cooling for the superconductor circuits and the bypass relay switching." It takes 3-5 h, with ~78 K as the operating temperature. If the unit is not in Normal within 5 h, call STI.
- **p61-62 (STATE screen):** `System SM State` shows the current state with the previous one in parentheses. The LNA and RF Bypass relay are normally controlled by the state machine. Forced Bypass makes the READY LED slow-flash amber in all states.
- **p63:** the WR sensor is used down to about 85 K, then the NR cold-finger and cold-stage sensors. This is the boundary between states 2 and 3.
- **p65 (LOOP screen):** *Back-off Count* is "the amount the maximum cooler drive is 'Backed off' due to the cooler over-stroke detector" (0 = none). *DAC Back Off* is "a factory set value". A ±20 % change in LNA current from its initial value declares a fault, which means System State 8, the alarm relay and Bypass.
