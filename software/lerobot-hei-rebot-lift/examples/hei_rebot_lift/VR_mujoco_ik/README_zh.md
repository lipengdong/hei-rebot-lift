# HEI ReBot Lift VR + MuJoCo IK

这个目录是一套完整的 VR 遥操作链路：

- `telegrip/`：启动 HTTPS/WebXR 页面，接收 VR 头显和手柄数据，并通过 ZMQ 发布到 `tcp://*:5567`。
- `mujoco_ik/`：接收 Telegrip 的 VR 数据，用 MuJoCo 显示双臂模型，用 Pinocchio + CasADi 做正逆解，并通过 ZMQ 发布 LeRobot 可用的动作命令到 `tcp://*:6558`。
- `examples/hei_rebot_lift/vr_control.py`：接收动作，同时在 `tcp://*:6559` 发布轻量实机关节/升降反馈，用于真机启动前安全同步。
- `mujoco_ik/hei_robot_vr_mujoco_sim.py`：使用完整机器人模型进行纯仿真 VR 控制，不会向真实机器人发送命令。
- LeRobot 录制端 `examples/hei_rebot_lift/record.py` 订阅 `tcp://localhost:6558`，把动作和机器人观测保存成数据集。

## 目录结构

```text
VR_mujoco_ik/
  environment.yml          # 统一 conda 环境，Telegrip + MuJoCo IK 共用
  run_telegrip.sh          # 启动 VR Web 页面和 VR 数据发布
  run_mujoco_ik.sh         # 原双臂实机动作链路
  run_hei_robot_vr_sim.sh  # 完整机器人 VR 纯仿真
  run_hei_robot_vr_real.sh # 完整模型 + 真实机器人命令桥接
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

根据需要打开两到三个终端。

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

### 2A. 先用完整模型测试 VR 仿真

先启动 Telegrip，然后在另一个终端执行：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_sim.sh
```

这是完整 URDF 的推荐首次测试入口。VR 可控制 O 型全向底盘、四个轮子的旋转动画、
左右机械臂、两个平行夹爪和升降平台。程序不发布 `6558` 端口的动作，也不会连接实机。
默认调试场景包含浅灰方格地面、渐变天空、柔和的顶部/前侧灯光、橙色 `4 x 4 m`
安全区域、青色启动区域，以及位于启动原点的世界坐标轴（X 红、Y 绿、Z 蓝）。
场景还加入了操作桌、三个彩色方块和一个保存于项目本地的 YCB 纹理香蕉，可用于
抓取和放置练习。

场景采用适合运动学 VR 调试的“稳定抓取模式”：夹爪在物体附近由张开变为闭合时，
程序会把最近的物体绑定到对应 TCP，并保留抓取瞬间的相对位置和朝向。松开 grip
不会掉落物体；再次张开夹爪才会释放。物体位于桌面范围上方时会稳定放到桌面，
否则放到地面。每条机械臂同时最多抓取一个物体。

控制方式：

- 按住左或右手柄 grip 控制对应机械臂，手柄的位移和旋转以 1:1 比例映射到 TCP。
- 夹爪启动默认为闭合。按住 grip 时，trigger 按下为夹爪张开；trigger 松开为闭合，并尝试抓住附近物体。松开 grip 后保持夹爪及已抓物体的最后状态。
- 按住右手 grip，右摇杆上下控制底盘前后，左右控制横移。
- 按住右手 grip 时，右手 `B` 控制顺时针旋转，左手 `Y` 控制逆时针旋转；松开右手 grip 或 VR 断流后底盘立即停止。
- 按住左手 grip，上下推左摇杆控制升降。
- 未按 grip 时，右手 `A` 键复位右臂，左手 `X` 键复位左臂。
- MuJoCo 窗口中，`F` 显示/隐藏 body 坐标系，`R` 同时复位机器人和全部场景物体。

不打开图形窗口，只检查模型编译和两臂 FK/IK：

```bash
./run_hei_robot_vr_sim.sh --headless-check
```

如需关闭全部环境元素，只显示机器人：

```bash
./run_hei_robot_vr_sim.sh --plain-scene
```

香蕉模型保存在
`mujoco_ik/model/HEI_robot_urdf/scene_assets/ycb_011_banana/`，其 YCB 来源、
引用方式和 CC BY 4.0 许可证说明见该目录的 `SOURCE.md`。

### 2B. 用完整模型控制真实机器人

解锁真机命令前，请清空机器人工作区并确保急停可随时按下。按 HEI ReBot Lift
文档先启动机器人 host 和 `teleoperate.py`。`teleoperate.py` 会在 `6559` 端口以
10 Hz 回传实机当前双臂、夹爪和升降位置，然后执行：

```bash
cd examples/hei_rebot_lift/VR_mujoco_ik
./run_hei_robot_vr_real.sh --enable-real-publish
```

真机模式只加载完整机器人 URDF，用于逆解计算和实机状态显示；不会加载仿真地面、
桌子、可抓取物体及其他调试场景元素。真机模式的升降显示速度默认为约
`0.0286 m/s`，对应当前 `18 rad/s` 电机限速和 `10 mm/rev` 丝杆导程；硬件参数
变化后可用 `--lift-speed-m-s VALUE` 覆盖。单独仿真仍保留原来的 `0.20 m/s` 默认值。

程序同时收到新鲜的实机反馈，以及一帧“两个 grip 都已松开”的新鲜 Telegrip
数据后，才会解锁真机发布。解锁前，MuJoCo 会先同步实测的双臂、夹爪和升降位置，
再通过 `6558` 发布 14 个双臂/夹爪关节、底盘和升降命令。平行夹爪的 URDF
米制开度会转换为达妙夹爪的 `-4.5` rad 张开和 `0` rad 闭合。

VR 数据或实机反馈任意一路超时，程序都会先发送底盘/升降停止包，再退回锁定状态。
连接恢复后，必须重新松开左右两个 grip，完成同步后才能再次解锁。终端日志中的
`feedback=<延迟>` 和 `bridge=locked/armed` 可用于判断当前阶段。

`--allow-no-feedback` 只用于兼容旧流程，它会跳过实机姿态同步，解锁后机械臂可能
直接追向仿真启动姿态，因此不建议在真实硬件上使用。

首次实机测试建议架起底盘轮子，让升降远离上下限位，每次只测一条手臂且减小动作幅度。
按 grip 前先确认日志已显示新鲜反馈和 `command bridge ARMED`。关闭 viewer，或 VR/
实机反馈超时时，底盘和升降会停止，机械臂保持最后关节目标。

### 2C. 启动原有双臂实机 MuJoCo IK 链路

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
6559  teleoperate.py/record.py 发布实机状态，供启动姿态同步
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
