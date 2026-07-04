# Telegrip

这是 HEI ReBot Lift VR 遥操作链路里的 WebXR/HTTPS/WebSocket/ZMQ 子模块。

统一部署、依赖安装、VR 头显访问地址和端口说明请看上一级文档：

```text
../README.md
```

常用启动方式：

```bash
cd ..
bash run_telegrip.sh
```

主要配置仍在本目录的 `config.yaml`。如果要在 VR 里显示机器人三路相机，把 `vr_images.enabled` 改成 `true`，并把 `vr_images.endpoint` 改成机器人真实 IP。
