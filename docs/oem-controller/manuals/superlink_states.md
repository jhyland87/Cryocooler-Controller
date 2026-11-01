# SuperLink Rx: internal states and status

Source: *SuperLink Rx Operation and Installation Manual* (STI 830-0013E), copied here as
[SuperLink_Rx_Operation_and_Installation_Manual.pdf](SuperLink_Rx_Operation_and_Installation_Manual.pdf).
Page numbers are PDF pages; the printed page number is the PDF page minus 5.
Diagram: [diagrams/superlink_state_machine.drawio](diagrams/superlink_state_machine.drawio).

## Table 7. SuperLink Rx Internal States and Status (PDF p39), verbatim

| Mode | State Name | Bypass Relay State | BYPASS (RED) | STATUS (GREEN) | Description |
|---|---|---|---|---|---|
| Bypass | 0. Initial | Bypass | On | On | Initializes the system and powers up the cooler motor to minimum power setting. Transitions to the Cooldown state. |
| Bypass | 1. Cooldown | Bypass | On | On | Cools down the CoRE. The Cooldown state runs the cooler motor at the maximum motor drive power, based on the cooldown profile of the cooler. The LNAs turn on in the Cooldown state when the cold stage narrow range temperature is within operating bounds. Transitions to Regulate state when the narrow range temperature is within its operating tolerance for 300 seconds (LNA on). |
| SuperLink | 2. Regulate | Normal | Off | On | Regulates the cold stage temperature indefinitely. |
| Bypass | 3. Bypass (Fault) | Bypass | On | Off | Continues to regulate the cooler temperature. This Fault state occurs when the Input Voltage is out of bounds. When the Input Voltage fault has cleared, the system transitions back to the Regulate state (Automatic mode). |
| Bypass | 4. Shutdown (Fault) | Bypass | On | Off | The cooler motor drive reduces to zero and is turned off. Transitions back to Initial state in Automatic mode when cold stage narrow range temperature has warmed sufficiently to be out of its valid range and the faults are cleared. |
| Bypass | 5. Forced Bypass | Bypass | Flash if On | Flash if On | Forces the system into Bypass mode regardless of any other conditions. At least one LED should always flash on if in Forced Bypass mode. |

Footer: "Regulate state = SuperLink mode. In all other states, the SL Rx is in Bypass mode."

## Related statements elsewhere in the manual

- **p13:** if the motor driver current moves to an unacceptable level, the DSP switches the unit into Shutdown mode and activates the alarm relay. An input voltage out of bounds gives Fault Bypass mode (state 3). An out-of-range temperature or LNA current gives Bypass mode. "Each time the SL Rx is switched to Bypass mode, the alarm relay is activated."
- **p12:** the unit powers up in Bypass mode. In Bypass mode both bypass relays switch together and route the input to the output through a stripline that skips the filter and LNA.
- **p38:** both LEDs stay on and steady during cooldown. At ~78 K the STATUS LED goes steady green and the BYPASS LED goes off. If the unit is not in Regulate within 5 hours, call the hotline.
- **p42:** the FORCED BYPASS button makes the STATUS LED slow-flash green and puts the alarm relay in the alarm condition. Pressing it again returns to Regulate (steady green STATUS).
- **p57:** if the LEDs show red and green, the unit may be recovering from a power drop-out. Wait three hours for it to recool.
- **p69 (State tab):** "In Automatic mode, the system will automatically sequence through the states. In Manual mode, the operator manually changes states by selecting the state."
- **p37, Figure 13 (alarm relay):** in normal operation NO is open and NC is closed. During a fault NO is closed and NC is open. Dry contacts, rated 2 A. See [diagrams/superlink_fig13_alarm_relay_states.drawio](diagrams/superlink_fig13_alarm_relay_states.drawio).
- **p67 (System tab):** status flags include *Power Drive Limit Foldback* ("Power maximum drive level is folding back on a limit." / "...is off the cooldown table."), *Power Duty Limit Exceeded*, *Power/Current Loop Regulating*, *Power Loop Active*, *Auto Frequency Adjust*, *Temperature Loop Regulating*, and out-of-bounds flags for Cold Stage NR, Cold Stage WR, Cooler Rejection and Ambient. See [../analysis/OVERSTROKE.md](../analysis/OVERSTROKE.md).
- **p70-73 (fault records):** PM, Tcsw, Trej, Tcsn, Ilna, Vin and Duty, each with a First and a Last record.
