# SOP OPS-02 — Machine Setup & Changeover

_Sample data for the Factory Knowledge startup kit. Fictional — replace with your real changeover SOP._

**SOP ID:** OPS-02 · **Owner:** Operations · **Rev:** 1.3

## 1. Purpose

Standardize how operators change the VMX-500 (and similar machines) from one part
to another quickly, safely, and with a guaranteed quality start.

## 2. Before you start (preparation / external setup)

Do as much as possible **while the previous job is still running** to minimize
downtime (SMED principle):
- Stage the new program, fixtures, tooling, and material at the machine.
- Pull the new part's drawing and the inspection checklist.
- Confirm all required gauges are present and **in calibration**.

## 3. Changeover steps (internal setup — machine stopped)

1. Complete the current lot and record final inspection results.
2. **Lockout/tagout** before reaching into the enclosure to change fixtures
   (Safety SOP LOTO-01).
3. Remove old fixture/tooling; clean the table and locating surfaces.
4. Install and secure the new fixture; torque clamps to the spec on the setup sheet.
5. Load the new tooling; set tool offsets and tool length.
6. Load the new NC program and verify the program number matches the drawing.
7. Set the work offset (G54) using an edge finder or probe.
8. Remove locks, reinstall guards, and clear the area.

## 4. Dry run & first article

1. Run the program in **single-block / reduced rapid** for the first cycle, hand on
   the feed-hold, watching for collisions.
2. Produce the **first article** and inspect it against the drawing (see QC-01 and
   `inspection_checklist.pdf`).
3. Only release the batch **after the first article passes** and is signed off.

## 5. Record the changeover

Log the changeover time, program number, and first-article result. Tracking
changeover time reveals where setup can be shortened.

## 6. Common changeover mistakes

| Mistake | Consequence | Prevention |
|---------|-------------|------------|
| Wrong work offset | Crash or scrap | Verify G54 with a probe/edge finder |
| Old program left loaded | Wrong features | Confirm program number vs drawing |
| Under-torqued clamp | Part shifts, scrap | Torque to setup-sheet spec |
| Skipping first article | Whole batch suspect | Never skip FAI |

## 7. Escalation

If the first article fails repeatedly or the setup sheet is missing/unclear, **hold
the job** and contact the **Quality Engineer** (ext. 4700) or your supervisor —
don't guess a setting.
