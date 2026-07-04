# Telegrip

This is the WebXR/HTTPS/WebSocket/ZMQ submodule in the HEI ReBot Lift VR teleoperation pipeline.

For unified deployment, dependency installation, VR headset URL, and port descriptions, see the parent document:

```text
../README.md
```

Common startup command:

```bash
cd ..
bash run_telegrip.sh
```

The main configuration file is still `config.yaml` in this directory. To display the robot's three camera streams in VR, set `vr_images.enabled` to `true` and update `vr_images.endpoint` to the robot's real IP address.

## Chinese Version

- [README_zh.md](README_zh.md)
