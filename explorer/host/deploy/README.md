# Deployment and dependency list

## 1. AIPC

```bash
python3 -m venv ~/apex_env && source ~/apex_env/bin/activate
pip install -r requirements.txt
python host/app/aipc_console/arm_console.py        # console service
```

`requirements.txt` lists the Python side. System packages: ROCm 7.14 or newer,
the Orbbec SDK, and the CAN userspace tools.

## 2. KR260 PS

```bash
sudo apt install can-utils
sudo patch -p1 -d /lib/modules/$(uname -r)/build < fpga/linux/can-driver-v203-identity.patch
sudo ip link set can0 type can bitrate 1000000 && sudo ip link set can0 up
```

## 3. FPGA

```bash
cd fpga/build && vivado -mode batch -source rebuild.tcl
# then load the resulting bitstream and the .hwh handoff for the PS
```

## 4. VR

Install the APK under `host/app/vr_release/content/` on the Quest (package
`com.tanluzhe.controlterminal.vr`, version 2.14.1, versionCode 25).

## 5. Startup order

1. KR260 PS services and CAN interfaces.
2. AIPC console; confirm feedback is received.
3. VR client; confirm the session heartbeat.
4. Base station; confirm layout revision matches.

## 6. Environment record

| Component | Version |
|---|---|
| Ubuntu (PS) | 24.04 |
| Vivado | 2026.1 (win64 build) |
| ROCm | 7.14.0 or newer |
| Device | xck26-sfvc784, speed file -2LV |
