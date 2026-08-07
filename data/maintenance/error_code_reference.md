# Error & Alarm Code Reference

_Sample data for the Factory Knowledge startup kit. Fictional — replace with your real code reference._

This reference covers the ACME-NC v4 control used on the VMX-500 CNC mill and the
BX-200 belt conveyor. Always follow lockout/tagout before clearing any alarm that
requires opening a guard or enclosure.

## CNC mill (VMX-500) codes

### E-110 — Low lubricant level
**Cause:** Way-lube reservoir below minimum.
**Action:** Top up with ISO VG 68 way oil to the MAX line, then clear the alarm. If
it returns immediately, check the lube pump and lines for a leak.
**Severity:** Warning — machine may run briefly but stop scheduling new jobs.

### E-204 — Spindle overload
**Cause:** Spindle drew excess current — jammed tool, excessive cutting load, belt
slip, or cooling-fan failure.
**Action:** Stop the cycle, apply lockout/tagout, inspect for a jam, reduce feed and
speed, check the drive belt and cooling fan, then clear and warm up. Recurrence in
one shift = tag out and escalate to the maintenance supervisor.
**Severity:** Critical — cycle halts.

### E-220 — Spindle over-temperature
**Cause:** Blocked spindle cooling, prolonged over-speed, or ambient heat.
**Action:** Stop and allow the spindle to cool. Check the cooling fan and air filter.
Do not resume until temperature is normal.
**Severity:** Critical.

### E-305 — Axis following error
**Cause:** Servo could not keep up — mechanical bind, loose gib, or worn ballscrew.
**Action:** Check axis for obstruction, inspect gibs and ballscrew, log any vibration.
**Severity:** Critical.

### E-410 — Door interlock open
**Cause:** Enclosure door opened during a cycle, or a faulty interlock switch.
**Action:** Close the door fully. If the alarm persists with the door closed, the
interlock switch (VMX-INT-02) may be faulty — tag out and replace.
**Severity:** Safety stop.

## Conveyor (BX-200) codes

### C-101 — Belt drift / mistracking
**Cause:** Belt running off-center due to tension imbalance or worn roller.
**Action:** Adjust take-up tension evenly both sides; inspect rollers. See
`conveyor_troubleshooting.md`.
**Severity:** Warning.

### C-205 — Motor overcurrent
**Cause:** Jam, overload, or seized roller bearing.
**Action:** Stop, lockout/tagout, clear any jam, check bearings for free rotation.
**Severity:** Critical — conveyor stops.

### C-301 — E-stop activated
**Cause:** An emergency-stop button was pressed.
**Action:** Clear the hazard, confirm the line is safe, twist-release the pressed
E-stop, then reset at the panel. Never reset an E-stop without verifying why it was
pressed.
**Severity:** Safety stop.

## Quick lookup table

| Code | Equipment | Meaning | Severity |
|------|-----------|---------|----------|
| E-110 | VMX-500 | Low lubricant | Warning |
| E-204 | VMX-500 | Spindle overload | Critical |
| E-220 | VMX-500 | Spindle over-temp | Critical |
| E-305 | VMX-500 | Axis following error | Critical |
| E-410 | VMX-500 | Door interlock open | Safety stop |
| C-101 | BX-200 | Belt drift | Warning |
| C-205 | BX-200 | Motor overcurrent | Critical |
| C-301 | BX-200 | E-stop pressed | Safety stop |
