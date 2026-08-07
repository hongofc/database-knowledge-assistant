# SOP QC-01 — In-Process Quality Control

_Sample data for the Factory Knowledge startup kit. Fictional — replace with your real quality SOP._

**SOP ID:** QC-01 · **Owner:** Quality Engineering · **Rev:** 3.0

## 1. Purpose

Ensure parts produced on Line 2 meet specification before they move downstream,
catching defects early to reduce scrap and rework.

## 2. First-article inspection (FAI)

After any setup or changeover, the operator produces **one first article** and has
it inspected **before running the batch**. The part is checked against the drawing
for all critical dimensions. Production does not start until the FAI passes and is
signed off. See `inspection_checklist.pdf` for the checklist.

## 3. In-process sampling plan

Use the sampling plan below (based on AQL 1.0, normal inspection):

| Lot size | Sample size | Accept | Reject |
|----------|-------------|--------|--------|
| 2–25 | 3 | 0 | 1 |
| 26–150 | 8 | 0 | 1 |
| 151–500 | 13 | 1 | 2 |
| 501–1,200 | 20 | 1 | 2 |

Take samples at the **start, middle, and end** of each lot, plus after any tool
change. Record measurements on the inspection record.

## 4. Critical dimensions & tolerances (example part P-Bracket)

| Feature | Nominal | Tolerance | Gauge |
|---------|---------|-----------|-------|
| Overall length | 120.0 mm | ±0.10 mm | Caliper (cal. ID CAL-07) |
| Bore diameter | 25.00 mm | +0.02 / −0.00 mm | Bore gauge (CAL-12) |
| Surface finish | Ra 1.6 | max | Profilometer |
| Hole position | — | ⌖0.1 mm | CMM |

> Quote tolerances **exactly** from the controlled drawing. If a feature's tolerance
> is not on the drawing or in this SOP, **do not assume a value** — check with the
> quality engineer.

## 5. Control charts

For the bore diameter (a key characteristic), plot **X-bar and R** charts with a
subgroup of 5 every hour. Stop and investigate if you see:
- any point outside the control limits, or
- **7 consecutive points** trending or on one side of the center line.

## 6. Handling a defect

1. **Quarantine** the suspect parts in the red NCR bin.
2. Raise a nonconformance report (`nonconformance_report.docx`).
3. Notify the quality engineer; do not continue running known-bad output.
4. Disposition (rework / scrap / use-as-is) is decided by Quality, not the operator.

## 7. Gauges

Only use gauges that are **in calibration** (check the cal sticker date). A gauge
past its calibration date must not be used — see `calibration_procedure.md`.

## 8. Escalation

Out-of-control process, missing tolerance, or repeated defects: **hold the lot** and
contact the **Quality Engineer** (ext. 4700).
