# fpga/build — build scripts and delivered artifacts

Section 3.2.5.1(2) asks for reproducible build scripts **and the produced
`.bit` / `.xsa` / `.hwh`**. This directory holds the scripts, the Vivado project
and the `.hwh` handoff files; the routed binaries are listed below with their
checksums.

## What is in this directory

| Item | Content |
|---|---|
| `*.tcl` | rebuild, integration and verification scripts for `KR260_PL_CAN_SWITCH.xpr` |
| `KR260_PL_CAN_SWITCH.xpr` | Vivado 2026.1 project (xck26-sfvc784) |
| `hw_handoff/*.hwh` | four hardware handoff files for the PS-side device tree / driver work |

Rebuild entry point:

```bash
vivado -mode batch -source fpga/build/rebuild.tcl
```

Verification entry points: `verify_final_routed.tcl` (routed checks),
`verify_can_switch_cdc.tcl` and `verify_shadow_cdc.tcl` (clock-domain checks),
`verify_routed_probes.tcl` / `verify_lifecycle_ila.tcl` (probe and ILA readback).

## Routed binaries (delivered separately)

The routed bitstream, XSA and probes file are **not stored in this repository**;
they ship as `KR260_PL_CAN_SWITCH_DELIVERY_20261103.zip` per the FPGA owner's
packaging convention. The expected names, sizes and SHA-256 come from
`fpga/evidence/artifact_consistency.json`, which also records that the `.bit`
payload matches the `.bit.bin` and that the XSA embeds the same bitstream:

| File | Bytes | SHA-256 |
|---|---|---|
| `kr260_pl_can_fix.bit` | 7797904 | `f6599719ef8cbca1ba35dd908fb5233882be9b39f7145f23cfac4f64d4915afe` |
| `kr260_pl_can_fix.bit.bin` | 7797692 | `88d72ec35d084acaecfd5ad562f3004b15767273dad42d48de6fbd9452f3cb00` |
| `kr260_pl_can_fix.xsa` | 3683183 | `ec3d2d589cdf325e1f01cb48d2d035f405f2f9bc785540e84a1c99e75cf2afb9` |
| `kr260_pl_can_fix.ltx` | 250856 | `e60bff81976c6fe088ac67fc199fa777a56d6e06b5b1757e40d0ef1dec688cb0` |

Verify a candidate delivery against the manifest before using it:

```bash
sha256sum kr260_pl_can_fix.bit   # must equal the value above
```

> **Do not substitute an earlier build.** A 2026-10-30 `kr260_j20_j19.bit`
> exists in the handoff archives; it has the same byte length but a different
> hash, so it is a different implementation and does not match the timing,
> utilisation and ILA evidence recorded in `fpga/report/` and `fpga/evidence/`.

## Board-level evidence

The bitstream corresponds to the build referenced by `fpga/report/final_*.rpt`
and summarised in `fpga/evidence/final_gate.json` (45 ports, 27 bus-skew checks,
DRC 0) and `fpga/evidence/release_signoff.json`.
