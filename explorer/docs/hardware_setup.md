# Hardware, wiring, power and mechanical parts

## 1. Bill of materials

| Role | Model | Notes |
|---|---|---|
| Host | AMD Ryzen AI Max+ 395 (Radeon 8060S iGPU) | ROCm 7.14, local inference |
| FPGA / MPSoC | AMD Kria KR260, xck26-sfvc784 (-2LV) | Ubuntu 24.04 PS + PL |
| Arms | 2x PIPER six-axis | left on FPGA_CAN0, right on FPGA_CAN1 |
| Chassis | 4-wheel independent drive, independent steering | mode and velocity via dedicated UDP relay |
| RGB-D | Orbbec Gemini 335 | color 1280x720 MJPG, depth 848x480 Y16, not hardware D2C |
| Fisheye | onboard fisheye | supplementary scene view |
| LiDAR + IMU | Mid-360 class unit + IMU | FAST-LIO2 input |
| VR | Meta Quest | OpenXR, 50 Hz default |
| Display station | independent PC | receives media and layout from AIPC |
| Switch | Mercury MWB505G | KR260 LAN |

## 2. Power

Single 48 V / 20 Ah ternary lithium pack.

| Branch | Conversion | Loads |
|---|---|---|
| A | 48 -> 24 V -> 19 V | AIPC |
| A (Type-C) | direct | Gemini 335, fisheye |
| B | 48 -> 12 V | KR260, MWB505G switch, LiDAR |

> Final connector, fuse and harness specifications are to be confirmed against
> the delivered build; the diagram is in `report/design_report.pdf` figure 2.3.

## 3. Mechanical interface

- Deck top surface is the body-frame origin; arms sit at
  (-152.55, +183.75, +5.00) and (+152.55, +183.75, +5.00) mm, both forward and
  level, relative yaw 0 degrees, centre distance 305.1 mm.
- Bracket rods measure 30 mm x 4 mm; the collision model uses a 15.13 mm
  circumscribed radius as a conservative bound.
- The vehicle model splits into moving arm, other arm and fixed body, each with
  convex hulls plus the original mesh.

## 4. Printed parts (`cad/`)

| Part | Purpose | File |
|---|---|---|
| `shell_10x20x80` | rear housing, lower 30 mm of front/back faces removed | `cad/shell_20261101/shell_10x20x80_notch_front_back_30.stl` |
| `tray_32x32x50` | open-top tray, 5 mm wall outward | `cad/tray_3.2x3.2_20261101/tray_32x32x50_wall5_open_top.stl` |
| `pillar_3x6x34` | base plate 3x6x34 with a 3x3x25 post | `cad/pillar_3x6x34_20261101/base_plate3x6x34_post3x3x25.stl` |
| -- | socket for the white part | not included in this package |
| `arc_shell_v5` | 60-degree arc shell | `cad/08_printed_arc_shell_20261030/arc_shell_v5.stl` |

Dimension check sheets (`*_check_sheet.png`) and STEP exports sit beside each STL.

## 5. Sensor mounting

- Camera mount, optical origin and LiDAR origin are defined separately; extrinsics
  are managed per use (calibration vs mapping).
- Camera-to-body extrinsic: reprojection RMS 0.309 px (54 corners), depth plane
  deviation -0.2 mm (79,197 points) — see `metrics/logs/camera_calibration/`.
- In-plane XY accuracy of the current planar method is about +-30 to 70 mm; it is
  used for coarse approach only, not for direct grasping.
