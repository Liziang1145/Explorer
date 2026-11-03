# Reusable skills

Each skill is a self-contained procedure with a stated scope, usage and failure
condition. They were extracted from this project; they are not tied to this
specific robot.

## 1. `kr260-pl-bringup`

**Scope** — bring a KR260 PL design from Tcl scripts to a verified routed build.

**Procedure**
1. `vivado -mode batch -source fpga/build/open_source.tcl`
2. `vivado -mode batch -source fpga/build/rebuild.tcl`
3. `vivado -mode batch -source fpga/build/verify_final_routed.tcl`
4. Check `fpga/report/timing_gate.txt` for `min slack > 0`, then read
   `final_utilization.rpt` and `final_drc.rpt`.

**Failure conditions** — negative WNS/WHS, non-zero DRC errors, or a
resource-utilisation jump above 90 % on BRAM.

**Verified reuse** — used to deliver the 2026-11-04 CAN-switch build
(WNS +0.082 ns, DRC 0).

## 2. `aipc-kr260-latency-harness`

**Scope** — measure per-segment software latency for a distributed control chain
without touching the actuators.

**Procedure**
1. Freeze the robot; run only the read-only path.
2. `python metrics/scripts/measure_latency.py` — writes a metrics-style CSV with
   `p50/p95/p99/max/mean/min` per stage.
3. `python metrics/scripts/check_aipc_latency.py` to validate the archive.

**Failure conditions** — motion commands issued during measurement, or stages
whose start/end points are not explicitly defined in the report.

**Verified reuse** — produced the N=215 and N=54 distributions in
`metrics/logs/`.

## 3. `analytic-layered-ik`

**Scope** — six-axis IK with a guaranteed geometric branch: J1-J3 position the
wrist centre by planar 2R, J4-J6 solve orientation by ZYZ, with the position
joints frozen during orientation solving.

**Procedure** — call `solve_layered_j5_pose_user(position, rotation, seed, side)`;
reject any solution whose native-FK residual exceeds 1e-7.

**Failure conditions** — a solution that only exists by letting J1-J3 compensate
for wrist limits; such solutions are rejected by design.

**Verified reuse** — the same entry serves the web console, VR and VLA.

## 4. `evidence-graded-reporting`

**Scope** — keep every reported number traceable to an artefact, with an explicit
evidence level and data-status column.

**Procedure** — one row per metric: name, category, value, unit, condition,
trials/duration, evidence path. States are limited to *tool-verified*,
*software-regression*, *read-only interface*, *field snapshot* and *pending*.

**Failure conditions** — a number whose evidence path does not resolve, or a
claim whose scope is not stated in the condition column.

**Verified reuse** — this package: `metrics/metrics.csv` has 50 rows, all with
resolvable evidence paths.
