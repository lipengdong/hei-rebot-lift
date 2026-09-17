# Telegrip

[English](README.md) | [中文](README_zh.md)

This is the WebXR/HTTPS/WebSocket/ZMQ submodule in the HEI ReBot Lift VR teleoperation pipeline.

For unified deployment, dependency installation, VR headset URL, and port descriptions, see the parent document:

[VR + MuJoCo IK guide](../README.md)

Common startup command, starting in this **telegrip directory**:

```bash
cd ..
bash run_telegrip.sh
```

The main configuration is [config.yaml](config.yaml). VR controller data is
published on `5567`; the headset opens `https://COMPUTER_IP:8443` (for example,
`https://192.168.31.245:8443`). The robot is a different machine.

Camera display is currently **disabled** (`vr_images.enabled: false`), without
disabling VR poses or the host's recording cameras. To enable it, set
`vr_images.enabled: true` and `vr_images.endpoint: tcp://ROBOT_IP:6556`, then
restart Telegrip and reload the headset page. The client's `--remote-ip` does
not modify this setting.

Before control, hold the right controller's **Meta Quest button about 3 seconds**
to recenter; repeat after changing position/heading or a direction mismatch.
Release both grips and center sticks first. See the parent controller tutorial
for diagrams and the safe sequence. This does not write motor zeros.

## Chinese Version

- [README_zh.md](README_zh.md)
