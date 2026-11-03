# Host and execution-side applications

| Directory | Language | Role |
|---|---|---|
| `aipc_console/` | Python | AIPC console backend: sessions, arm control, tasks, telemetry |
| `aipc_simulator/` | Python + HTML/JS | web console UI and its HTTP routes |
| `offline_planning/` | Python | RRT-Connect, FCL collision, TOPP-RA, dual-arm coupling |
| `kr260_executor/` | C++ / Python | KR260 PS execution side: target validation, slew limit, SocketCAN |
| `kr260_side/` | C++ | `arm_planner`, `arm_hardware_interface`, `teleop_task_runner` |
| `kr260_console/` | Python | KR260-side console and diagnostics |
| `vr_client/` | Java / Kotlin | OpenXR + OpenGL ES client |
| `vr_release/` | APK | delivered VR build 2.14.1 |
| `base_station/` | Python | independent display station |
| `ros_ws/` | C++ / Python | vehicle ROS workspace and FAST-LIO integration |
| `mapping/` | Python | mapping and navigation release and validation |

## Control entry points

| Entry | Module | Notes |
|---|---|---|
| Coordinate task execution | `aipc_simulator/vla_motion_execute.py` | forces exact mesh pre-check, 5x time scale, 30 s / 0.50 rad/s gate |
| One-shot test motion | `aipc_simulator/vla_test_motion.py` | requires a fixed confirm string, 15 s / 0.15 rad/s gate |
| Preview only | `aipc_simulator/vla_plan_preview.py` | no execution call |
| VR follow | `aipc_console/arm_console.py` — `solve_layered_j5_pose_user` | direct IK at input rate, no RRT/TOPP-RA |

## Note on collision scope

The general coordinate-execution path sets `check_gripper=False`. This is
deliberate: the capsule gripper model produces false collisions because its
orientation does not match the physical gripper. **The gripper's real collision
risk is therefore not eliminated by the algorithm** and is covered by low-speed
operation and an observer.

## Supplementary source folders

| Path | Content |
|---|---|
| `vr_client/shaders/` | GLSL shaders for the VR renderer (vertex / fragment / compressed-vertex) |
| `kr260_executor/piper_dual_arm_teleop/matlab/` | MATLAB verification of the inverse-dynamics terms: mass matrix, Coriolis, gravity compensation, link Jacobians, SE(3) helpers |

The MATLAB files are analysis and verification scripts, not part of the runtime
path; the runtime uses the C++ implementation.
