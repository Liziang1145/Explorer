# Interface definition

## 1. AIPC → KR260 target message (UDP v2)

| Field | Type | Meaning |
|---|---|---|
| `seq` | uint32 | monotonically increasing target sequence |
| `enable` | bitfield | per-arm enable and per-axis validity |
| `ref_version` | uint32 | reference-version stamp; mismatch is logged then accepted |
| `q[6]` | float32 x6 | joint targets, radians |
| `ts_send` | uint64 | AIPC send timestamp (monotonic, us) |
| `epoch` | uint32 | session epoch; stale epochs are dropped |

Behaviour on anomalies:

- **Reference-version mismatch** — logged as a warning, then accepted.
- **Stream gap > 100 ms** — a throttled warning is logged and interpolation
  continues toward the last target.
- **Software stop / enable withdrawal** — handled on separate paths.

## 2. KR260 → AIPC feedback

| Field | Type | Meaning |
|---|---|---|
| `seq` | uint32 | echoes the target sequence being reported |
| `q[6]` | float32 x6 | measured joint positions, radians |
| `state` | enum | idle / running / done / failed / stopped |
| `ts_recv` | uint64 | receive timestamp (monotonic, us) |

Polled at a 20 ms period.

## 3. PL register map (AXI-Lite)

| Module | Base address | Notes |
|---|---|---|
| Ethernet channel 2 CSR/MDIO | `0x80180000` | UP, 100 Mbit/s negotiated in snapshot |
| Ethernet channel 3 CSR/MDIO | `0x801c0000` | UP, 1000 Mbit/s negotiated in snapshot |
| `eth_recovery_watchdog_v2` | per port | protection, local reset, settle wait, cooldown, quota |
| `can_io_observer` | bypass tap | CAN TX/RX, GPIO I/O/T, reset, tick, 32-bit counter |

- `CAN0`/`CAN1` are PS CAN routed through **EMIO**.
- `CAN2` is the **CTU CAN** IP bridged on APB, used as classic CAN 2.0.
- Eight AXI GPIO channels drive eight IOBUF groups (input / output / tri-state).
- `CAN`/`GPIO` use J20/J19, bank 43, LVCMOS33; external transceivers are still
  required for a physical bus.

## 4. Coordinate frames

| Frame | Definition |
|---|---|
| Body (project) | origin at the centre of the deck top surface, X right, Y forward, Z up |
| Navigation base | X forward, Y left, Z up; same origin, `(x, y) = (Y_B, -X_B)` |
| Arm base | per-arm local frame; the left/right base positions in body are (-152.55, +183.75, +5.00) and (+152.55, +183.75, +5.00) mm, centre distance 305.1 mm |
| Camera optical | X right, Y down, Z along the optical axis |

Units: metres and radians internally; centimetres and degrees on the VLA HTTP
interface. `J5→J7` is 152.5 mm, `J5→flange` 91 mm, `flange→J7` 61.5 mm.

## 5. VR protocol

| Item | Value |
|---|---|
| Transport | TLZ2 / OPERATOR_STATE |
| Serialisation | CBOR or opbin1, negotiated |
| Default input rate | 50 Hz, configurable 10-90 Hz |
| Video | six independent HEVC/fMP4 subscriptions, hardware decode |
| Side buttons | local UI only — **not** a robot e-stop |

## 6. Timing conventions

- Control and feedback carry monotonic timestamps plus a session epoch.
- Sensor data carries device timestamp, host offset and stream epoch.
- Reported latency uses software timestamps at explicitly stated endpoints; see
  the condition column in `metrics/metrics.csv`.
