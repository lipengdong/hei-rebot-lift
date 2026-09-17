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

以下以 `cd examples/...` 开头的命令块，均在新终端的
`software/lerobot-hei-rebot-lift/` 目录执行。不带 `cd` 的命令默认已进入
`VR_mujoco_ik/`。启动脚本自动激活 `hei-rebot-vr`；直接运行 Python 检查命令时
需要手动激活。LeRobot 客户端仍使用独立的 `lerobot5` 环境。

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
conda activate hei-rebot-vr
env -u LD_LIBRARY_PATH python -c "import pinocchio as pin; from pinocchio import casadi as cpin; print(pin.__version__); print('casadi binding ok')"
```

看到 `casadi binding ok` 就说明正逆解库链路正常。

## 启动流程

纯仿真通常两个终端；真机还需机器人 host 和一个电脑客户端，共四个终端。

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

#### VR 手柄使用教程

程序使用相对位姿控制。每次按下某侧 `grip` 时，程序会把当时的手柄位姿和对应
机械臂 TCP 位姿记为控制原点；之后手柄的 XYZ 位移与旋转以 1:1 比例映射到 TCP。
松开 `grip` 后机械臂保持最后目标，再次按下时会重新建立原点，因此不会要求手柄
回到固定的绝对位置。

| 手柄输入 | 生效条件 | 功能 |
| --- | --- | --- |
| 左侧 `grip` | 按住 | 启用左臂相对位姿控制，同时允许左摇杆控制升降 |
| 右侧 `grip` | 按住 | 启用右臂相对位姿控制，同时允许右摇杆和旋转按键控制底盘 |
| 左/右 `trigger` | 对应侧 `grip` 按住 | 按下张开对应夹爪，松开闭合夹爪 |
| 左摇杆上下 | 左侧 `grip` 按住 | 向前推使升降上升，向后拉使升降下降 |
| 右摇杆上下 | 右侧 `grip` 按住 | 控制底盘前进和后退 |
| 右摇杆左右 | 右侧 `grip` 按住 | 控制 O 型全向底盘向左和向右横移 |
| 右手 `B` | 右侧 `grip` 按住 | 底盘顺时针旋转 |
| 左手 `Y` | 右侧 `grip` 按住 | 底盘逆时针旋转 |
| 右手 `A` | 右侧 `grip` 松开 | 右臂缓慢回到默认姿态 |
| 左手 `X` | 左侧 `grip` 松开 | 左臂缓慢回到默认姿态 |

机械臂与夹爪操作步骤：

1. 把手柄放在舒适位置，确认目标机械臂周围没有障碍物。
2. 按住对应侧 `grip`，以当前位姿建立控制原点，然后平移或旋转手柄控制末端。
3. 夹爪启动默认为闭合。保持 `grip` 时按下 `trigger` 张开夹爪，将夹爪移动到物体两侧。
4. 松开 `trigger` 使夹爪闭合并抓取。松开 `grip` 只会停止机械臂跟随，夹爪仍保持最后状态。
5. 需要释放物体时，再次按住对应侧 `grip` 并按下 `trigger`。

底盘与升降操作步骤：

1. 右侧 `grip` 是底盘使能键。保持右侧 `grip`，使用右摇杆控制前后与横移；使用
   右手 `B` 或左手 `Y` 控制旋转。松开右侧 `grip` 立即清除运动请求；实机减速
   仍受 host 加减速限制和硬件响应影响，不代表瞬间机械停止。
2. 左侧 `grip` 是升降使能键。保持左侧 `grip`，前后推动左摇杆控制上升和下降；
   松开左侧 `grip` 后停止升降请求；真机客户端以最新反馈高度作为保持目标。
3. 控制机械臂但不希望底盘或升降运动时，保持相应摇杆处于中心位置。

真机首次使用与恢复：

1. 启动真机桥后先松开左右两个 `grip`，等待终端显示 `command bridge ARMED`。
2. 首次测试每次只操作一条机械臂，采用小幅、缓慢的手柄动作，并确保急停可随时按下。
3. VR 数据或实机反馈超时后，底盘和升降会停止，桥接进入锁定状态；连接恢复后，
   再次松开左右两个 `grip` 完成同步和解锁。
4. MuJoCo 仿真窗口中，`F` 显示或隐藏 body 坐标系，`R` 同时复位机器人和场景物体。
   真机模式禁用键盘 `R` 全复位，请使用右手 `A` 和左手 `X` 分别缓慢复位机械臂。

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
对应的是**满摇杆时的理论最高速**，不是全过程实测同步。硬件参数变化后可用
`--lift-speed-m-s VALUE` 覆盖显示速度；这个参数不会改变电机转速。
单独仿真仍保留原来的 `0.20 m/s` 默认值。

真机桥接发布的是 `height_axis`，不是仿真高度。LeRobot 客户端结合机器人反馈
高度生成毫米单位的 `action["height.pos"]`，host 再根据高度误差控制电机速度。
解锁后，viewer 主要按摇杆积分显示，不会持续用实测高度校正，因此半摇杆响应、
加减速、网络延迟和负载都会造成显示与实机不一致。它是控制可视化，不是全过程
同步的数字孪生。单位和丝杆换算详见
[机器人驱动说明](../../../src/lerobot/robots/hei_rebot_lift/README_zh.md)。

程序同时收到新鲜的实机反馈，以及一帧“两个 grip 都已松开”的新鲜 Telegrip
数据后，才会解锁真机发布。解锁前，MuJoCo 会先同步实测的双臂、夹爪和升降位置，
再通过 `6558` 发布 14 个双臂/夹爪关节、底盘和升降命令。平行夹爪的 URDF
米制开度会转换为达妙夹爪的 `-4.5` rad 张开和 `0` rad 闭合。

VR 数据或实机反馈任意一路超时，程序都会先发送底盘/升降停止包，再退回锁定状态。
连接恢复后，必须重新松开左右两个 grip，完成同步后才能再次解锁。终端日志中的
`feedback=<延迟>` 和 `bridge=locked/armed` 可用于判断当前阶段。

`--allow-no-feedback` 只用于兼容旧流程，它会跳过实机姿态同步和反馈新鲜度检查，解锁后机械臂可能
直接追向仿真启动姿态，因此不建议在真实硬件上使用。

首次实机测试建议架起底盘轮子，让升降远离上下限位，每次只测一条手臂且减小动作幅度。
按 grip 前先确认日志已显示新鲜反馈和 `command bridge ARMED`。关闭 viewer，或 VR/
实机反馈超时时，底盘和升降会停止，机械臂保持最后关节目标。

### 2C. 启动原有双臂实机 MuJoCo IK 链路

此入口与完整模型真机桥接**二选一**，不能同时发布到 `6558`。
`teleoperate.py` 与 `record.py` 也只能运行一个，因为它们都在 `6559` 发布反馈。
录制前停止遥操作；反馈恢复后松开两侧 grip 重新解锁。回放或策略推理前，应停止
VR 真机发布及其他电脑端机器人控制程序。

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
6555  LeRobot 客户端向 host 发送机器人控制命令
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

LeRobot 脚本的 `--remote-ip` 不会自动更新此 YAML 地址，机器人换 IP 时两处都要
检查。`6556` 是 host 的观测/图像通道，不是 Telegrip 的 `5567` VR 位姿通道。

真机桥接默认 VR 超时和反馈超时均为 `1.0 s`；host 另有 `1000 ms` 命令看门狗。
它们保护不同链路，不能代替急停。IK 工作空间投影与关节限位也不等于碰撞检测或
过载保护。

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
conda activate hei-rebot-vr
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
ss -ltnp | rg ':(8443|8442|5567|6555|6556|6558|6559)\b'
```

关掉旧进程后重新启动。

### 真机发布锁定

`Real command publishing is locked` 表示缺少明确的安全确认参数。检查工作区与
急停后，用 `./run_hei_robot_vr_real.sh --enable-real-publish` 启动。
如果窗口已打开但显示 `bridge=locked`，检查 Telegrip、host，以及一个已运行的
客户端（`teleoperate.py` 或 `record.py`），再同时松开两侧 grip。不要通过跳过
反馈检查解决网络连接问题。

### 自检与参数位置

在 `VR_mujoco_ik/` 目录执行，以下检查不发布真机命令：

```bash
./run_hei_robot_vr_sim.sh --headless-check
./run_hei_robot_vr_real.sh --headless-check
conda run --no-capture-output -n hei-rebot-vr python -m unittest discover -s mujoco_ik/tests -p 'test_*.py' -v
```

| 参数 | 所在文件 | 生效范围 |
| --- | --- | --- |
| 电机增益/限速、丝杆导程/加速度、相机 | 软件根目录下 `src/lerobot/robots/hei_rebot_lift/config_hei_rebot_lift.py` | 机器人 host；修改后重启 host |
| 完整模型 IK 判断与工作空间投影 | `mujoco_ik/hei_robot_vr_mujoco_sim.py` | 完整模型仿真与真机桥接共用 |
| 实机反馈/VR 超时、升降显示速度 | `mujoco_ik/hei_robot_vr_mujoco_real.py` 及命令行选项 | 电脑端真机桥接 |
| VR 相机地址与图像显示 | `telegrip/config.yaml` | Telegrip；与机器人相机采集配置分开 |

`IK_TARGET_MAX_POSITION_ERROR_M` 当前为 `0.100 m`，是接受 IK 解的误差阈值，
不表示末端控制精度能达到该值；调大后，请求目标与实际执行目标可能相差更多。

### LeRobot 录制没有动作

检查链路顺序：

1. Telegrip 页面已经启动并进入 VR。
2. MuJoCo IK 窗口已经启动，并能收到 VR 控制器数据。
3. MuJoCo IK 正在向 `tcp://*:6558` 发布动作。
4. `record.py` 已启动并能看到 saved_frames 增长。
