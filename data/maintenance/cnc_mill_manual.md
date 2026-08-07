# CNC Vertical Mill VMX-500 — Operation & Maintenance Manual

_Sample data for the Factory Knowledge startup kit. Fictional equipment — replace with your real manuals._

**Asset ID:** VMX-500 · **Manufacturer:** ACME Machine Tools · **Doc rev:** 3.2

## 1. Machine specifications

| Parameter | Value |
|-----------|-------|
| Spindle speed | 100–12,000 RPM |
| Spindle motor | 11 kW |
| Max feed rate | 15 m/min |
| Coolant tank | 120 L |
| Control system | ACME-NC v4 |
| Air supply | 6 bar, clean dry air |

## 2. Daily startup checklist

1. Confirm the work area is clear and guards are in place.
2. Check coolant level is above the MIN line on the sight glass.
3. Check air pressure reads 6 bar on the panel gauge.
4. Power on, then run the spindle warm-up program (W-WARMUP) for 8 minutes.
5. Verify no active alarms on the control screen before loading a job.

> **Warning:** Never bypass the door interlock. The spindle must not run with the
> enclosure open. See the Safety SOPs for lockout/tagout before any maintenance.

## 3. Lubrication

The way-lube system is automatic. Check the lubricant reservoir weekly and top up
with **ISO VG 68 way oil** to the MAX line. Low lubricant triggers alarm **E-110**
(see the Error Code Reference). Grease the X/Y/Z ballscrew bearings every **500
operating hours** with 2 pumps of **NLGI 2 lithium grease** — do not over-grease.

## 4. Coolant

Maintain coolant concentration between **6% and 8%** (check with a refractometer
weekly). Replace coolant every **3 months** or when pH falls below 8.5. Clean the
chip tray and coolant filter weekly to prevent pump cavitation.

## 5. Common faults (quick guide)

| Symptom | Likely cause | First action |
|---------|--------------|--------------|
| Spindle won't start | Door interlock open; alarm E-204 | Close enclosure, clear alarm |
| Poor surface finish | Worn tool; low coolant | Replace tool, check coolant |
| Axis drifts / chatter | Loose gib; worn ballscrew | Inspect gibs, log vibration |
| Coolant pump noisy | Low coolant; clogged filter | Top up, clean filter |
| Overheating spindle | Blocked cooling; over-speed | Stop, let cool, check fan |

Full alarm/error meanings are in `error_code_reference.md`. Repair history for this
asset is in `maintenance_log.md`.

## 6. Spindle overload (E-204) procedure

1. **Stop the cycle** and ensure the spindle has come to a complete halt.
2. Apply **lockout/tagout** before opening the enclosure (Safety SOP LOTO-01).
3. Check for a jammed tool or excessive cutting load; reduce feed/speed.
4. Inspect the spindle drive belt tension and the cooling fan.
5. Clear alarm E-204 on the panel and run the warm-up program before resuming.
6. If E-204 recurs within one shift, **escalate to the maintenance supervisor** and
   tag the machine out of service.

## 7. Recommended spare parts

| Part | Part number | Reorder level |
|------|-------------|---------------|
| Spindle drive belt | VMX-BELT-11 | 2 |
| Way oil ISO VG 68 (5 L) | LUB-VG68-5 | 4 |
| Coolant filter | VMX-FLT-120 | 6 |
| Door interlock switch | VMX-INT-02 | 1 |

## 8. Contact

For issues beyond this manual, contact the **maintenance supervisor** (ext. 4500)
or log a work order using the `work_order_template.docx` form.
