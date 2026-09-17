# MuJoCo IK

这是 HEI ReBot Lift VR 遥操作链路里的 MuJoCo + Pinocchio IK 子模块。

统一部署、手柄操作、网络配置和真机安全启动请看 [VR 使用教程](../README_zh.md)。

## 选择启动入口

以下脚本在上一级 `VR_mujoco_ik/` 目录执行，会自动激活 `hei-rebot-vr` 环境。
`6558` 端口同一时间只能保留一个动作发布程序。

| 入口 | 模型 | 用途 |
| --- | --- | --- |
| `./run_hei_robot_vr_sim.sh` | `model/HEI_robot_urdf/` | 完整机器人、场景、VR、稳定抓取演示；不发布真机命令 |
| `./run_hei_robot_vr_real.sh --enable-real-publish` | `model/HEI_robot_urdf/` | 仅机器人显示与真机桥接；需要实机反馈及松开握把解锁 |
| `./run_mujoco_ik.sh` | `model/reBot_description/` | 旧双臂 realtime 控制程序，不是完整机器人入口 |

真机模式还需要机器人 host，以及 `teleoperate.py` 或 `record.py` 中的一个。
启用真机命令前请先阅读上级教程。

## 无界面自检

以下命令不发布真机命令，也不需要 VR 头显：

```bash
./run_hei_robot_vr_sim.sh --headless-check
./run_hei_robot_vr_real.sh --headless-check
conda run --no-capture-output -n hei-rebot-vr python -m unittest discover -s mujoco_ik/tests -p 'test_*.py' -v
```

模型与协议自检通过，不代表实机零位、方向、限位开关和负载能力已经验证；
这些仍需单独进行硬件调试。

注意：`pinocchio`、`casadi`、`eigenpy`、`coal-python` 请使用上级 `environment.yml` 里的 conda-forge 版本安装，不要在这里单独 `pip install pin`。
