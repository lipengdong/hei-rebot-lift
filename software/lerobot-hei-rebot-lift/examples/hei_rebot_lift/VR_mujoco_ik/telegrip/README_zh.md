# Telegrip

[English](README.md) | [中文](README_zh.md)

这是 HEI ReBot Lift VR 遥操作链路里的 WebXR/HTTPS/WebSocket/ZMQ 子模块。

统一部署、依赖安装、VR 头显访问地址和端口说明请看上一级文档：

[VR + MuJoCo IK 教程](../README_zh.md)

常用启动方式，从**本 telegrip 目录**开始：

```bash
cd ..
bash run_telegrip.sh
```

主要配置是 [config.yaml](config.yaml)，VR 手柄位姿发布在 `5567`。
头显访问 `https://电脑IP:8443`，例如 `https://192.168.31.245:8443`；机器人
是另一台机器，不要混用 IP。

当前相机显示**已关闭**（`vr_images.enabled: false`），不影响 VR 位姿和 host
录制相机。需要时设置 `vr_images.enabled: true`、
`vr_images.endpoint: tcp://机器人IP:6556`，重启 Telegrip 并刷新头显页面。
客户端 `--remote-ip` 不会修改此项。

操作前长按右手柄 **Meta Quest 按钮约 3 秒**重新居中；换位置、朝向或运动
方向不一致时重新校准。先松开两侧 grip、摇杆回中，示意图与安全步骤见上级
手柄教程。此操作不会写电机零位。

[English](README.md)
