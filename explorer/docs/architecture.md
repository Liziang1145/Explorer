# System architecture and data flow

## 1. Layering

```text
+------------------------------------------------------------------+
|  AIPC (Ryzen AI Max+ 395, ROCm 7.14)                              |
|    - VR session service, arm console, VLA task bridge            |
|    - YOLO26m-seg on GPU, Qwen local task parsing                  |
|    - analytic layered IK, RRT-Connect, TOPP-RA, FCL collision    |
|    - FAST-LIO2 mapping, navigation supervisor, point-cloud post  |
+---------------------------+--------------------------------------+
                            | UDP v2 (seq / enable / epoch / ts)
+---------------------------v--------------------------------------+
|  KR260  PS (Ubuntu 24.04)          |  KR260  PL                   |
|    - target validation and limits  |    - dual Ethernet datapath  |
|    - 0.8 rad/s per-cycle slew      |      (DMA -> FIFO -> MAC)    |
|    - SocketCAN bridge              |    - PS CAN via EMIO x2      |
|    - feedback polling at 20 ms     |    - CTU CAN (APB) x1        |
|                                    |    - 8x AXI GPIO + IOBUF     |
|                                    |    - eth_recovery_watchdog_v2|
|                                    |    - can_io_observer (ILA)   |
+------------------------------------+------------------------------+
                            | CAN / Ethernet
+---------------------------v--------------------------------------+
|  Physical: 2x PIPER 6-axis arms, 4WID-4WIS chassis,              |
|            Orbbec Gemini 335, fisheye, LiDAR + IMU               |
+------------------------------------------------------------------+
```

## 2. Control plane

- **Target message**: six joint targets per arm, carrying sequence number,
  enable bits, reference version and the sampling/receive timestamps.
- **Execution gate**: KR260 validates mode and numeric range, applies joint
  limits, then limits each target increment to `kMaxJointVel * dt_plan`
  (0.8 rad/s) before writing SocketCAN.
- **Feedback**: polled at 20 ms, tagged with the target sequence and task state.
- **Chassis**: a separate UDP relay converts mode and velocity into CAN frames.
- **Stops**: software stop and enable-bit withdrawal are separate paths.
  A standalone hardware e-stop is **not** wired.

## 3. Media plane

VR and the base station subscribe to six HEVC/fMP4 camera streams, telemetry,
the geometry map and point-cloud products. Media never carries control
authority; control and feedback keep their own sequence and timestamps so that
media processing cannot occupy control semantics.

## 4. Chain 1 — VR teleoperation

```text
Quest (OpenXR, 50 Hz default, 10-90 Hz configurable)
  -> TLZ2 / OPERATOR_STATE, CBOR or opbin1
  -> AIPC: authorisation, clutch-incremental mapping, One Euro filter,
           analytic layered IK, joint limiting, execution permit
  -> UDP v2 -> KR260 -> CAN -> arms
  -> encoder feedback -> telemetry -> VR
```

Clutch-incremental mapping plus One Euro filtering keeps hand tremor out of the
target while allowing large workspace coverage without re-anchoring.

## 5. Chain 2 — language task planning and VLA pre-check

```text
Chinese request
  -> Qwen local call + strict JSON schema (action / target / executor / arm)
  -> whitelist and parameter validation (unknown action or extra field rejected)
  -> YOLO26m-seg on ROCm GPU -> 3D localisation
  -> camera optical -> body -> arm-base frame -> J5 target
  -> analytic layered IK -> joint limits, FK residual, FCL mesh collision,
     trajectory speed and duration limits
  -> preview -> human confirmation ("confirm execute", TTL 60 s)
  -> execution bridge -> UDP / KR260 / CAN
```

A SmolVLA branch produces 50x7 action chunks and passes the same discrete grid
pre-check; it is **not** wired to physical execution.

## 6. Chain 3 — mapping and navigation

```text
LiDAR + IMU -> FAST-LIO2 -> registered cloud, odometry, incremental map
  -> navigation geometry (10 cm voxel, <=5 Hz)
  -> semantic pass (2 Hz, same online trajectory)
  -> colored product (offline replay), light product at 5 cm
  -> route: rectangular-footprint continuous sweep + unknown-cell restriction
  -> supervised Pure Pursuit -> AIPC -> KR260 -> chassis CAN
```

Geometry, semantic and colored products are scheduled asynchronously: navigation
never waits for the dense coloring pass.

## 7. Why the split is where it is

- The **PL** owns the deterministic, high-rate work: dual Ethernet datapath,
  CAN/GPIO exposure, port-local recovery and in-fabric observation. These cannot
  be reduced to a USB/serial adapter because the data path is timed and the
  recovery/watchdog logic runs independently of the PS scheduler.
- The **PS** owns protocol handling, limits, interpolation and SocketCAN, where
  Linux drivers and the CAN stack are required.
- The **AIPC** owns inference, planning and UI, where the GPU and the Python
  ecosystem are required.

## 8. Measurement boundaries

Each chain reports its own endpoint definitions. Software timestamps are used for
the reported latency; the in-fabric 32-bit counter exists but is **not** yet used
to recompute physical end-to-end latency. See `metrics/metrics.csv` for the
per-row condition column.
