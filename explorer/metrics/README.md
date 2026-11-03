# metrics/

`metrics.csv` columns follow section 3.2.5.2. **All `evidence_file` values are
relative to the package root**, e.g. `metrics/logs/vr_latency/vla-215-reference.json`.

## Layout

| Path | Content |
|---|---|
| `metrics.csv` | one row per metric: name, category, value, unit, condition, trials, evidence |
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
