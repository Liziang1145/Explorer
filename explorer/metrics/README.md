# metrics/

`metrics.csv` columns follow section 3.2.5.2. **All `evidence_file` values are
relative to the package root**, e.g. `metrics/logs/vr_latency/vla-215-reference.json`.

## Measurement conditions

Section 3.2.5.2 also requires the `measurement_condition` column to carry the
hardware model, model and numeric precision, input spec, software version, FPGA
clock frequency and power mode. Rather than repeat those constants in all 57
rows, every row ends with `env=E1` or `env=E2`; both tag sets are defined in
[`ENVIRONMENT.md`](ENVIRONMENT.md). `E1` = AI PC only, `E2` = KR260 PS/PL in the
loop. Fields that are still unrecorded (power mode, per-op numeric precision)
are marked as such there instead of being guessed.

## Layout

| Path | Content |
|---|---|
| `metrics.csv` | one row per metric: name, category, value, unit, condition, trials, evidence |
| `ENVIRONMENT.md` | `env=E1` / `env=E2` measurement conditions (six required fields) |
| `logs/vr_latency/` | VR latency清洗 records, VLA 215-request reference |
| `logs/latency/` | CPU baseline latency, `final_100/metrics.csv` with p50/p95/p99/max |
| `logs/planning_perf/` | collision parallelisation and dual-arm retiming |
| `logs/camera_calibration/` | camera extrinsic calibration record and matrix |
| `logs/handoff_records/` | experiment records carried over from the handoff package |
| `scripts/` | re-runnable measurement scripts |
| `evidence/` | handoff checks and supplementary material |

## Verification

Every evidence path in `metrics.csv` resolves inside this package. Re-check with:

```bash
python metrics/scripts/check_aipc_latency.py
```
