# HEI ReBot Lift VR + MuJoCo IK

这个目录是一套完整的 VR 遥操作链路：

- `telegrip/`：启动 HTTPS/WebXR 页面，接收 VR 头显和手柄数据，并通过 ZMQ 发布到 `tcp://*:5567`。
- `mujoco_ik/`：接收 Telegrip 的 VR 数据，用 MuJoCo 显示双臂模型，用 Pinocchio + CasADi 做正逆解，并通过 ZMQ 发布 LeRobot 可用的动作命令到 `tcp://*:6558`。
- LeRobot 录制端 `examples/hei_rebot_lift/record.py` 订阅 `tcp://localhost:6558`，把动作和机器人观测保存成数据集。

## 目录结构

```text
VR_mujoco_ik/
  environment.yml          # 统一 conda 环境，Telegrip + MuJoCo IK 共用
  run_telegrip.sh          # 启动 VR Web 页面和 VR 数据发布
  run_mujoco_ik.sh         # 启动 MuJoCo viewer + Pinocchio IK
  telegrip/                # WebXR/HTTPS/WebSocket/ZMQ VR 桥
  mujoco_ik/               # MuJoCo 模型、IK 主程序、Pinocchio 工具
```

## 一体化环境部署

建议只保留一个 conda 环境，不再分 `VR_Telegrip` 和 `mujoco_vr` 两套。

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
conda env create -f environment.yml
```

如果环境已经存在，更新即可：

```bash
conda env update -n hei-rebot-vr -f environment.yml --prune
```


验证：

```bash
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__); print('casadi binding ok')"
```

看到 `casadi binding ok` 就说明正逆解库链路正常。

## 启动流程

推荐开三个终端。

### 1. 启动 Telegrip

电脑端：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_telegrip.sh
```

VR 头显浏览器访问：

```text
https://电脑IP:8443
```

第一次访问自签名 HTTPS 页面时，需要在浏览器里手动继续访问。

### 2. 启动 MuJoCo IK

同一台电脑另一个终端：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_mujoco_ik.sh
```


## 网络和端口

```text
8443  Telegrip HTTPS VR 页面
8442  Telegrip WebSocket
5567  Telegrip 发布 VR 数据，MuJoCo IK 订阅
6558  MuJoCo IK 发布动作，LeRobot record 订阅
6556  机器人图像流，Telegrip 可选订阅显示
```

`telegrip/config.yaml` 里主要看两个地方：

```yaml
vr:
  zmq_publish_endpoint: tcp://*:5567
  zmq_topic: vr_data
```

如果要在 VR 里显示机器人三路相机，打开：

```yaml
vr_images:
  enabled: true
  endpoint: tcp://机器人IP:6556
```

三路图像 key 默认是：

```text
front
left_wrist
right_wrist
```

## 常见问题

### MuJoCo/Pinocchio 导入失败

优先用下面命令验证：

```bash
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__)"
```

如果不用 `env -u LD_LIBRARY_PATH` 才失败，说明当前 shell 的 `LD_LIBRARY_PATH` 污染了 conda-forge 的动态库搜索路径。启动 MuJoCo IK 时继续用 `run_mujoco_ik.sh`，脚本里已经处理。

### VR 页面打不开

检查电脑和 VR 头显是否在同一局域网，访问地址必须是：

```text
https://电脑IP:8443
```

不是 `http`。

### 端口被占用

常见是旧的 Telegrip 或 MuJoCo IK 没关。查端口：

```bash
ss -ltnp | grep -E '8443|8442|5567|6558'
```

关掉旧进程后重新启动。

### LeRobot 录制没有动作

检查链路顺序：

1. Telegrip 页面已经启动并进入 VR。
2. MuJoCo IK 窗口已经启动，并能收到 VR 控制器数据。
3. MuJoCo IK 正在向 `tcp://*:6558` 发布动作。
4. `record.py` 已启动并能看到 saved_frames 增长。
