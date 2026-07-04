# HEI ReBot Lift VR + MuJoCo IK

This directory contains the complete VR teleoperation pipeline:

- `telegrip/`: starts the HTTPS/WebXR page, receives VR headset/controller data, and publishes it through ZMQ at `tcp://*:5567`.
- `mujoco_ik/`: receives Telegrip VR data, visualizes the dual-arm model in MuJoCo, solves FK/IK with Pinocchio + CasADi, and publishes LeRobot-compatible actions to `tcp://*:6558`.
- `examples/hei_rebot_lift/record.py`: subscribes to `tcp://localhost:6558` and saves robot actions/observations into a LeRobotDataset.

## Layout

```text
VR_mujoco_ik/
  environment.yml          # Unified conda environment for Telegrip + MuJoCo IK
  run_telegrip.sh          # Start the VR Web page and VR data publisher
  run_mujoco_ik.sh         # Start MuJoCo viewer + Pinocchio IK
  telegrip/                # WebXR/HTTPS/WebSocket/ZMQ VR bridge
  mujoco_ik/               # MuJoCo model, IK main program, Pinocchio tools
```

## Environment Setup

Use one shared conda environment instead of separate `VR_Telegrip` and `mujoco_vr` environments.

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
```

Update an existing environment:

```bash
conda env update -n hei-rebot-vr -f environment.yml --prune
```

Verify Pinocchio + CasADi:

```bash
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__); print('casadi binding ok')"
```

## Startup Flow

### 1. Start Telegrip

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

Open in the VR headset browser:

```text
https://COMPUTER_IP:8443
```

For the first visit to the self-signed HTTPS page, manually continue in the browser.

### 2. Start MuJoCo IK

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_mujoco_ik.sh
```

## Network and Ports

```text
8443  Telegrip HTTPS VR page
8442  Telegrip WebSocket
5567  Telegrip publishes VR data, MuJoCo IK subscribes
6558  MuJoCo IK publishes actions, LeRobot record subscribes
6556  Robot image stream, optionally displayed in Telegrip
```

Key settings in `telegrip/config.yaml`:

```yaml
vr:
  zmq_publish_endpoint: tcp://*:5567
  zmq_topic: vr_data
```

To display robot cameras in VR:

```yaml
vr_images:
  enabled: true
  endpoint: tcp://ROBOT_IP:6556
```

Default image keys:

```text
front
left_wrist
right_wrist
```

## Troubleshooting

### MuJoCo/Pinocchio Import Failure

```bash
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__)"
```

If imports only work after clearing `LD_LIBRARY_PATH`, keep using `run_mujoco_ik.sh`, which handles this case.

### VR Page Cannot Open

Make sure the computer and VR headset are on the same LAN and use:

```text
https://COMPUTER_IP:8443
```

Do not use `http`.

### Port Already in Use

```bash
ss -ltnp | grep -E '8443|8442|5567|6558'
```

Stop old Telegrip/MuJoCo IK processes and restart.

### LeRobot Recording Has No Actions

Check that Telegrip is in VR, MuJoCo IK receives controller data, MuJoCo IK publishes to `tcp://*:6558`, and `record.py` shows increasing `saved_frames`.

## Chinese Version

- [README_zh.md](README_zh.md)
