import mujoco
import mujoco.viewer
import argparse
import json
import os
import numpy as np
import time
import zmq
from threading import Thread, Lock
from pynput import keyboard

import src.pinocchio_kinematic as pinocchio_kinematic
import src.utils as utils

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCENE_XML_PATH = os.path.join(
    BASE_DIR,
    "model/reBot_description/urdf/reBot_dual_with_gripper_scene.xml",
)
ARM_XML_PATH = os.path.join(
    BASE_DIR,
    "model/reBot_description/urdf/reBot_dual_with_gripper.urdf",
)
DEFAULT_VR_ENDPOINT = "tcp://localhost:5567"
DEFAULT_COMMAND_ENDPOINT = "tcp://*:6558"
RIGHT_EE_FRAME = "a_right_end_link"
LEFT_EE_FRAME = "b_left_end_link"

RIGHT_QPOS = slice(0, 7)
LEFT_QPOS = slice(7, 14)
RIGHT_IK_QPOS = np.arange(0, 6)
LEFT_IK_QPOS = np.arange(7, 13)
RIGHT_GRIP_INDEX = 6
LEFT_GRIP_INDEX = 13
ROBOT_QPOS_COUNT = 14
GRIPPER_CLOSED_QPOS = 0.0
GRIPPER_OPEN_QPOS = -4.5
DEFAULT_RIGHT_QPOS = np.array([0.0, -0.5, -0.5, 0.0, 0.0, 0.0, GRIPPER_CLOSED_QPOS])
DEFAULT_LEFT_QPOS = np.array([0.0, -0.5, -0.5, 0.0, 0.0, 0.0, GRIPPER_CLOSED_QPOS])
# IK 限频，默认 60Hz
IK_MAX_RATE_HZ = 60.0
IK_MIN_INTERVAL = 1.0 / IK_MAX_RATE_HZ
IK_TARGET_POS_EPS = 0.001
IK_TARGET_ROT_EPS = np.deg2rad(0.5)
IK_FAIL_LOG_INTERVAL = 1.0
#VR 目标低通滤波：TARGET_FILTER_ALPHA = 0.45，会减少手抖导致的 IK 抖动，
#可以把 TARGET_FILTER_ALPHA 从 0.45 调到 0.6-0.75，会更灵敏但抖动也会多一点
TARGET_FILTER_ALPHA = 0.45
# VR 控制器位移到机械臂末端目标位移的比例。
# 调小会让机械臂移动幅度更小、更稳；调大会让机械臂移动幅度更大、更灵敏。
VR_POS_SCALE = 0.95
# 胸部/身体防碰撞总开关；False 时完全关闭下面的胸部禁入区和夹爪工具点检查。
CHEST_COLLISION_AVOIDANCE_ENABLED = True
# 胸部/身体末端禁入区开关。方案一只限制末端目标点，不检查整条手臂连杆。
CHEST_WORKSPACE_LIMIT_ENABLED = True
# 胸部禁入盒，单位 m，基于 reBot 双臂模型的 base_link 包围盒和默认双臂末端位置估计。
# 默认末端约在 x=+/-0.20, y=-0.175, z=0.83；禁区只覆盖身体中心，避免挡住初始姿态。
# x: -0.16 ~ 0.16   左右宽度 0.32m
# y: -0.30 ~ 0.08   前后深度 0.38m
# z:  0.45 ~ 1.05   高度
CHEST_FORBIDDEN_MIN = np.array([-0.12, -0.24, 0.45])
CHEST_FORBIDDEN_MAX = np.array([0.12, 0.02, 1.05])
# 目标点进入禁入盒时，会被投影到最近盒面外侧并额外留出这个安全边距。
CHEST_FORBIDDEN_MARGIN = 0.03
# 夹爪/末端工具相对 link7 目标坐标系的采样点，单位 m。
# URDF 中 link7->link8 约为 [0.0195, 0.017, 0.0497]，这里额外取一个更靠前的工具点。
CHEST_TOOL_POINTS_LOCAL = np.array([
    [0.0, 0.0, 0.0],
    [0.0195, 0.0173, 0.0497],
    [0.02, -0.02, 0.09],
])
# MuJoCo viewer 每隔多少次主循环刷新一次；3 表示每 3 轮主循环刷新 1 次画面。
# 数值越大越省 CPU/GPU，但仿真窗口视觉刷新会更低；控制和 IK 仍按主循环运行。
VIEWER_SYNC_EVERY = 2
# 主循环 sleep 时间，0.01 约 100Hz，0.016 约 60Hz。
MAIN_LOOP_SLEEP = 0.01
# 发送给 LeRobot 录制端的命令心跳频率。
# 之前只有 IK/复位产生新关节目标时才发布，手柄静止或只等待时可能长时间没有 ZMQ 新包；
# 录制端需要稳定拿到当前 qpos/base/height_axis，所以这里固定频率广播当前命令。
COMMAND_PUBLISH_RATE_HZ = 30.0
COMMAND_PUBLISH_INTERVAL = 1.0 / COMMAND_PUBLISH_RATE_HZ
# A/X 复位时每轮主循环最大关节变化量，单位 rad。
# 只影响“恢复到预设默认姿态”的动作；调小更柔和但回位更慢，调大回位更快但可能更冲。
RESET_MAX_STEP = 0.015
# VR IK 正常控制时每轮主循环最大关节变化量，单位 rad。
# IK 求解后先对关节目标做限速，再写入 MuJoCo qpos，避免末端快速移动时关节目标一帧跳太多。
# 如果实机末端仍抖，优先调小到 0.015；如果感觉跟手太慢，可调大到 0.035 左右。
IK_MAX_JOINT_STEP = 0.025
# 性能统计开关。打开后每秒打印主循环、VR、IK、MuJoCo forward、viewer sync 等耗时。
PERF_DEBUG = False
PERF_PRINT_INTERVAL = 1.0

# Lift platform command axis. The robot side converts this axis to a short
# position target using the measured lift height.
LIFT_THUMBSTICK_DEADZONE = 0.15

# VR position axes -> robot/world axes for reBot:
#   robot_x = -vr_z  (VR forward/back -> robot forward/back)
#   robot_y = -vr_x  (VR left/right -> robot left/right)
#   robot_z =  vr_y  (VR up/down -> robot up/down)
VR_TO_ROBOT_ROT = np.array([
    [0.0, 0.0, -1.0],
    [-1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
])

class CustomViewer:
    def __init__(self, model, data, command_endpoint, vr_endpoint):
        self.model = model
        self.data = data
        self.command_endpoint = command_endpoint
        self.vr_endpoint = vr_endpoint
        self.handle = mujoco.viewer.launch_passive(self.model, self.data)

        # 添加ZMQ初始化代码
        self.zmq_context = zmq.Context()
        self.zmq_pub = self.zmq_context.socket(zmq.PUB)
        # 绑定端口，可根据需要修改端口号
        self.zmq_pub.bind(self.command_endpoint)

        self.keyboard_controller = keyboard.Controller()
        self.prev_right_b_button = 0
        self.prev_left_y_button = 0
        self.prev_right_a_button = 0
        self.prev_left_x_button = 0
        
        self.vr_run = False
        # 线程锁
        self.data_lock = Lock()
        self.vr_lock = Lock()

        self.default_q = np.zeros(self.model.nq)
        self.default_q[RIGHT_QPOS] = DEFAULT_RIGHT_QPOS
        self.default_q[LEFT_QPOS] = DEFAULT_LEFT_QPOS

        self.right_grip_num = 0.0
        self.right_arm = pinocchio_kinematic.Kinematics(RIGHT_EE_FRAME)
        self.right_arm.buildFromMJCF(
            ARM_XML_PATH,
            active_q_indices=RIGHT_IK_QPOS,
            reference_q=self.default_q,
        )

        self.left_grip_num = 0.0
        self.left_arm = pinocchio_kinematic.Kinematics(LEFT_EE_FRAME)
        self.left_arm.buildFromMJCF(
            ARM_XML_PATH,
            active_q_indices=LEFT_IK_QPOS,
            reference_q=self.default_q,
        )
        self.right_zero_tf = self.right_arm.fk(self.default_q)
        self.left_zero_tf = self.left_arm.fk(self.default_q)
        self.right_target_tf = self.right_zero_tf.copy()
        self.left_target_tf = self.left_zero_tf.copy()
        self._sync_target_scalars_from_tf("right")
        self._sync_target_scalars_from_tf("left")
        self._apply_zero_qpos()
        

        # VR控制器数据
        self.vr_data = {
            'left': {
                'position': {'x': 0.0, 'y': 0.0, 'z': 0.0},
                'quaternion': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0},
                'gripActive': False,
                'gripReleased': True,
                'trigger': False,
                'xButton': 0,
                'yButton': 0,
                'thumbstick': {'x': 0.0, 'y': 0.0, 'pressed': 0},
            },
            'right': {
                'position': {'x': 0.0, 'y': 0.0, 'z': 0.0},
                'quaternion': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0},
                'gripActive': False,
                'gripReleased': True,
                'trigger': False,
                'aButton': 0,
                'bButton': 0,
                'thumbstick': {'x': 0.0, 'y': 0.0, 'pressed': 0},
            }
        }
        
        # VR控制器原点位置和姿态
        self.vr_origin = {
            'left': None,
            'right': None
        }
        
        # VR控制器初始姿态（用于计算相对旋转）
        self.vr_initial_rot = {
            'left': None,
            'right': None
        }
        
        # 机器人初始旋转角度（用于校准）
        self.robot_initial_rot = {
            'left': self.left_target_tf[:3, :3].copy(),
            'right': self.right_target_tf[:3, :3].copy(),
        }
        
        # 旋转校准矩阵（用于修正VR控制器和机器人之间的旋转偏差）
        self.rot_calibration = np.eye(3)
        self.last_ik_target_tf = {
            'left': None,
            'right': None,
        }
        self.last_ik_solve_time = {
            'left': 0.0,
            'right': 0.0,
        }
        self.last_ik_fail_log_time = {
            'left': 0.0,
            'right': 0.0,
        }
        self.last_vr_pose_warning_time = {
            'left': 0.0,
            'right': 0.0,
        }
        self.chest_limit_face = {
            'left': None,
            'right': None,
        }
        self.reset_target_q = {
            'left': None,
            'right': None,
        }
        self.perf_stats = {}
        self.perf_last_print = time.perf_counter()
        self.perf_loop_count = 0
        self.last_command_publish_time = 0.0
        self.prev_right_motion_grip = False
        self.prev_left_lift_grip = False
        self.height_axis = 0.0
        
        # 启动ZeroMQ接收线程
        self.right_zmq_thread = Thread(target=self._start_zmq_listener, daemon=True)
        self.right_zmq_thread.start()
        
        # 打印控制说明
        self.show_help()

    def _sync_target_scalars_from_tf(self, side):
        target = self.right_target_tf if side == "right" else self.left_target_tf
        x, y, z, rx, ry, rz = utils.mat2transform(target)
        setattr(self, f"{side}_x", float(x))
        setattr(self, f"{side}_y", float(y))
        setattr(self, f"{side}_z", float(z))
        setattr(self, f"{side}_rx", float(rx))
        setattr(self, f"{side}_ry", float(ry))
        setattr(self, f"{side}_rz", float(rz))

    def _sync_target_tf_from_scalars(self, side):
        target = utils.transform2mat(
            getattr(self, f"{side}_x"),
            getattr(self, f"{side}_y"),
            getattr(self, f"{side}_z"),
            getattr(self, f"{side}_rx"),
            getattr(self, f"{side}_ry"),
            getattr(self, f"{side}_rz"),
        )
        if side == "right":
            self.right_target_tf = target
        else:
            self.left_target_tf = target

    def _set_target_tf(self, side, target):
        target = target.copy()
        if side == "right":
            self.right_target_tf = target.copy()
        else:
            self.left_target_tf = target.copy()
        self._sync_target_scalars_from_tf(side)

    def _set_filtered_target_tf(self, side, target):
        previous = self.right_target_tf if side == "right" else self.left_target_tf
        target = target.copy()
        self._apply_chest_workspace_limit(side, target, previous)
        filtered = target.copy()
        alpha = TARGET_FILTER_ALPHA
        filtered[:3, 3] = (1.0 - alpha) * previous[:3, 3] + alpha * target[:3, 3]
        rot_blend = (1.0 - alpha) * previous[:3, :3] + alpha * target[:3, :3]
        u, _, vt = np.linalg.svd(rot_blend)
        filtered[:3, :3] = u @ vt
        if np.linalg.det(filtered[:3, :3]) < 0.0:
            u[:, -1] *= -1.0
            filtered[:3, :3] = u @ vt
        self._apply_chest_workspace_limit(side, filtered, previous)
        self._set_target_tf(side, filtered)

    def _apply_chest_workspace_limit(self, side, target, previous_target=None):
        if not CHEST_COLLISION_AVOIDANCE_ENABLED or not CHEST_WORKSPACE_LIMIT_ENABLED:
            return False

        total_shift = np.zeros(3)
        limited = False
        for local_point in CHEST_TOOL_POINTS_LOCAL:
            world_point = target[:3, 3] + target[:3, :3] @ local_point + total_shift
            if not self._point_inside_chest_box(world_point):
                continue

            face_axis, face_sign = self._select_chest_limit_face(
                side,
                world_point,
                local_point,
                target,
                previous_target,
            )
            boundary = (
                CHEST_FORBIDDEN_MIN[face_axis] - CHEST_FORBIDDEN_MARGIN
                if face_sign < 0
                else CHEST_FORBIDDEN_MAX[face_axis] + CHEST_FORBIDDEN_MARGIN
            )
            shift = np.zeros(3)
            shift[face_axis] = boundary - world_point[face_axis]
            total_shift += shift
            limited = True

        if limited:
            target[:3, 3] += total_shift
        return limited

    def _point_inside_chest_box(self, point):
        return np.all(point >= CHEST_FORBIDDEN_MIN) and np.all(point <= CHEST_FORBIDDEN_MAX)

    def _select_chest_limit_face(self, side, world_point, local_point, target, previous_target):
        if previous_target is not None:
            previous_point = previous_target[:3, 3] + previous_target[:3, :3] @ local_point
            outside_low = previous_point < CHEST_FORBIDDEN_MIN
            outside_high = previous_point > CHEST_FORBIDDEN_MAX
            if np.any(outside_low) or np.any(outside_high):
                distances = np.full(6, np.inf)
                distances[:3] = np.where(outside_low, CHEST_FORBIDDEN_MIN - previous_point, np.inf)
                distances[3:] = np.where(outside_high, previous_point - CHEST_FORBIDDEN_MAX, np.inf)
                selected = int(np.argmin(distances))
                axis = selected % 3
                sign = -1 if selected < 3 else 1
                self.chest_limit_face[side] = (axis, sign)
                return axis, sign

        if self.chest_limit_face[side] is not None:
            return self.chest_limit_face[side]

        lower_dist = world_point - CHEST_FORBIDDEN_MIN
        upper_dist = CHEST_FORBIDDEN_MAX - world_point
        axis_distances = np.concatenate([lower_dist, upper_dist])
        nearest = int(np.argmin(axis_distances))
        axis = nearest % 3
        sign = -1 if nearest < 3 else 1
        self.chest_limit_face[side] = (axis, sign)
        return axis, sign

    def _rotation_angle_between(self, a, b):
        rot_delta = a[:3, :3].T @ b[:3, :3]
        cos_angle = (np.trace(rot_delta) - 1.0) * 0.5
        return float(np.arccos(np.clip(cos_angle, -1.0, 1.0)))

    def _target_changed_enough(self, side, target):
        previous = self.last_ik_target_tf[side]
        if previous is None:
            return True
        pos_delta = np.linalg.norm(target[:3, 3] - previous[:3, 3])
        rot_delta = self._rotation_angle_between(previous, target)
        return pos_delta >= IK_TARGET_POS_EPS or rot_delta >= IK_TARGET_ROT_EPS

    def _log_ik_failure(self, side, message):
        now = time.time()
        if now - self.last_ik_fail_log_time[side] >= IK_FAIL_LOG_INTERVAL:
            print(message)
            self.last_ik_fail_log_time[side] = now

    def _perf_add(self, name, elapsed):
        if not PERF_DEBUG:
            return
        total, count = self.perf_stats.get(name, (0.0, 0))
        self.perf_stats[name] = (total + elapsed, count + 1)

    def _perf_report_if_due(self, loop_elapsed):
        if not PERF_DEBUG:
            return
        self._perf_add("loop", loop_elapsed)
        self.perf_loop_count += 1
        now = time.perf_counter()
        if now - self.perf_last_print < PERF_PRINT_INTERVAL:
            return

        hz = self.perf_loop_count / max(now - self.perf_last_print, 1e-9)
        parts = [f"loop_hz={hz:.1f}"]
        for name in sorted(self.perf_stats):
            total, count = self.perf_stats[name]
            parts.append(f"{name}={total / max(count, 1) * 1000:.2f}ms")
        print("[PERF] " + " | ".join(parts))
        self.perf_stats.clear()
        self.perf_loop_count = 0
        self.perf_last_print = now

    def _apply_zero_qpos(self):
        with self.data_lock:
            self.data.qpos[:] = self.default_q
            self.data.qvel[:] = 0.0
            mujoco.mj_forward(self.model, self.data)

    def _kinematic_forward(self):
        """Refresh MuJoCo state without allowing dynamics to integrate joint positions."""
        self.data.qvel[:] = 0.0
        self.data.qacc[:] = 0.0
        if self.model.nu:
            self.data.ctrl[:] = 0.0
        mujoco.mj_forward(self.model, self.data)

    def _clear_vr_origin(self):
        with self.vr_lock:
            self.vr_origin['left'] = None
            self.vr_origin['right'] = None
            self.vr_initial_rot['left'] = None
            self.vr_initial_rot['right'] = None

    def _vr_quat_to_rot(self, quat):
        return utils.quat2rotmat([quat['w'], quat['x'], quat['y'], quat['z']])

    def _map_vr_relative_rot_to_robot(self, initial_quat, current_quat):
        initial_rot = self._vr_quat_to_rot(initial_quat)
        current_rot = self._vr_quat_to_rot(current_quat)
        relative_rot = current_rot @ initial_rot.T
        return self.rot_calibration @ (VR_TO_ROBOT_ROT @ relative_rot @ VR_TO_ROBOT_ROT.T)

    def _map_vr_relative_pos_to_robot(self, origin_pos, current_pos):
        vr_delta = np.array([
            current_pos['x'] - origin_pos['x'],
            current_pos['y'] - origin_pos['y'],
            current_pos['z'] - origin_pos['z'],
        ], dtype=float)
        return VR_TO_ROBOT_ROT @ vr_delta

    def _warn_missing_vr_pose(self, side, missing_fields):
        now = time.time()
        if now - self.last_vr_pose_warning_time[side] < 1.0:
            return
        label = "左" if side == "left" else "右"
        fields = ", ".join(missing_fields)
        print(f"\n⚠️ {label}控制器 VR 数据缺少 {fields}，本帧按未激活处理")
        self.last_vr_pose_warning_time[side] = now

    def _controller_from_vr_packet(self, side, controller):
        current = self.vr_data[side]
        controller = controller or {}
        missing_fields = [
            field
            for field in ("position", "quaternion")
            if not isinstance(controller.get(field), dict)
        ]
        pose_valid = not missing_fields
        if not pose_valid:
            self._warn_missing_vr_pose(side, missing_fields)

        data = current.copy()
        data['position'] = controller.get('position') if pose_valid else current['position']
        data['quaternion'] = controller.get('quaternion') if pose_valid else current['quaternion']
        data['gripActive'] = bool(controller.get('gripActive', False)) and pose_valid
        data['gripReleased'] = controller.get('gripReleased', not data['gripActive'])
        data['trigger'] = controller.get('trigger', 0)
        data['thumbstick'] = controller.get('thumbstick') or current['thumbstick']

        if side == "left":
            data['xButton'] = controller.get('xButton', 0)
            data['yButton'] = controller.get('yButton', 0)
        else:
            data['aButton'] = controller.get('aButton', 0)
            data['bButton'] = controller.get('bButton', 0)
        return data

    def _fk_status_text(self):
        q = self.data.qpos.copy()
        right_tf = self.right_arm.fk(q)
        left_tf = self.left_arm.fk(q)
        right_pose = utils.mat2transform(right_tf)
        left_pose = utils.mat2transform(left_tf)
        right_deg = np.degrees(right_pose[3:])
        left_deg = np.degrees(left_pose[3:])
        return (
            f"右臂FK xyz=({right_pose[0]:.3f}, {right_pose[1]:.3f}, {right_pose[2]:.3f}) "
            f"rpy=({right_deg[0]:.1f}, {right_deg[1]:.1f}, {right_deg[2]:.1f})deg | "
            f"左臂FK xyz=({left_pose[0]:.3f}, {left_pose[1]:.3f}, {left_pose[2]:.3f}) "
            f"rpy=({left_deg[0]:.1f}, {left_deg[1]:.1f}, {left_deg[2]:.1f})deg"
        )

    def _start_zmq_listener(self):
        """启动ZeroMQ数据接收线程"""
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")  # 订阅所有主题
        socket.connect(self.vr_endpoint)
        
        print(f"\n👂 ZeroMQ 接收端已启动，等待 VR 数据: {self.vr_endpoint}")
        
        try:
            while True:
                # 接收完整的消息
                message = socket.recv_string()
                
                # 解析主题和数据
                if " " in message:
                    topic, payload = message.split(" ", 1)
                    try:
                        vr_data = json.loads(payload)
                        
                        with self.vr_lock:
                            if "leftController" in vr_data:
                                self.vr_data['left'] = self._controller_from_vr_packet(
                                    'left',
                                    vr_data["leftController"],
                                )
                            if "rightController" in vr_data:
                                self.vr_data['right'] = self._controller_from_vr_packet(
                                    'right',
                                    vr_data["rightController"],
                                )
                                
                    except json.JSONDecodeError:
                        print(f"\n⚠️ 无法解析 JSON 数据: {payload}")
                    except Exception as e:
                        print(f"\n⚠️ 跳过异常 VR 数据帧: {e}")
                else:
                    print(f"\n📥 收到无主题数据: {message}")
                    
        except Exception as e:
            print(f"\n❌ ZeroMQ 接收线程出错: {e}")
        finally:
            socket.close()

    def is_running(self):
        return self.handle.is_running()

    def sync(self):
        self.handle.sync()

    @property
    def cam(self):
        return self.handle.cam

    @property
    def viewport(self):
        return self.handle.viewport
    
    def reset_to_default(self):
        """恢复到预设默认姿态。"""
        print("\n=== 恢复到预设默认姿态 ===")
        self.right_grip_num = 0.0
        self.left_grip_num = 0.0
        self._set_target_tf("right", self.right_zero_tf)
        self._set_target_tf("left", self.left_zero_tf)
        self.robot_initial_rot['right'] = self.right_target_tf[:3, :3].copy()
        self.robot_initial_rot['left'] = self.left_target_tf[:3, :3].copy()
        self.last_ik_target_tf['right'] = None
        self.last_ik_target_tf['left'] = None
        self.chest_limit_face['right'] = None
        self.chest_limit_face['left'] = None
        self.reset_target_q['right'] = None
        self.reset_target_q['left'] = None
        self._clear_vr_origin()
        self._apply_zero_qpos()
        print(f"右臂默认目标: xyz=({self.right_x:.3f}, {self.right_y:.3f}, {self.right_z:.3f}), "
              f"rpy=({np.degrees(self.right_rx):.1f}, {np.degrees(self.right_ry):.1f}, {np.degrees(self.right_rz):.1f})deg")
        print(f"左臂默认目标: xyz=({self.left_x:.3f}, {self.left_y:.3f}, {self.left_z:.3f}), "
              f"rpy=({np.degrees(self.left_rx):.1f}, {np.degrees(self.left_ry):.1f}, {np.degrees(self.left_rz):.1f})deg")
        
    
    def show_help(self):
        """显示帮助信息"""
        print("\n" + "="*60)
        print("机器人VR控制说明:")
        print("="*60)
        print("VR控制器控制:")
        print("  - 右手控制器: 控制机器人右臂末端执行器")
        print("  - 左手控制器: 控制机器人左臂末端执行器")
        print("  - 按下握把键: 设置控制器原点位置和姿态")
        print("  - 移动控制器: 机器人末端执行器跟随移动")
        print("  - 旋转控制器: 机器人末端执行器跟随旋转（已校准）")
        print("")
        print("特殊功能:")
        print("  - 右手 A 键: 右臂恢复到预设默认姿态")
        print("  - 左手 X 键: 左臂恢复到预设默认姿态")
        print("  - 左手 X 键 + 右手 A 键: 头部复位")
        print("")
        print("当前状态:")
        print(f"  右臂目标: xyz=({self.right_x:.3f}, {self.right_y:.3f}, {self.right_z:.3f}), "
              f"rpy=({np.degrees(self.right_rx):.1f}, {np.degrees(self.right_ry):.1f}, {np.degrees(self.right_rz):.1f})deg")
        print(f"  左臂目标: xyz=({self.left_x:.3f}, {self.left_y:.3f}, {self.left_z:.3f}), "
              f"rpy=({np.degrees(self.left_rx):.1f}, {np.degrees(self.left_ry):.1f}, {np.degrees(self.left_rz):.1f})deg")
        print("="*60)
    
    def handle_vr_input(self):
        """处理VR控制器输入"""
        with self.vr_lock:
            right_controller = self.vr_data['right'].copy()
            left_controller = self.vr_data['left'].copy()

        self.vr_run = right_controller['gripActive'] or left_controller['gripActive']

        # 处理右手控制器
        right_grip = right_controller['gripActive']
        right_trigger = right_controller['trigger']
        right_pos = right_controller['position']
        right_quat = right_controller['quaternion']

        if right_trigger and right_grip:
            self.right_grip_num = GRIPPER_OPEN_QPOS
        else:
            self.right_grip_num = GRIPPER_CLOSED_QPOS
        # 设置右手控制器原点
        if right_grip and self.vr_origin['right'] is None:
            self.reset_target_q['right'] = None
            self.vr_origin['right'] = right_pos.copy()
            # 记录初始位置
            self.right_x_origin = self.right_x
            self.right_y_origin = self.right_y
            self.right_z_origin = self.right_z
            # 记录初始姿态（四元数）
            self.vr_initial_rot['right'] = right_quat.copy()
            # 记录机器人当前旋转角度作为初始旋转
            self.robot_initial_rot['right'] = self.right_target_tf[:3, :3].copy()
            print(f"🎯 右手控制器原点已设置: {self.vr_origin['right']}")
            print(f"🎯 右手控制器初始姿态已记录: {self.vr_initial_rot['right']}")
            print("🎯 机器人右臂初始末端姿态矩阵已记录")
        elif not right_grip:
            self.vr_origin['right'] = None
            self.vr_initial_rot['right'] = None
            self.last_ik_target_tf['right'] = None
            self.chest_limit_face['right'] = None

        # 使用右手控制器控制机器人右臂
        if self.vr_origin['right'] and self.vr_initial_rot['right']:
            robot_delta = self._map_vr_relative_pos_to_robot(self.vr_origin['right'], right_pos)
            self.right_x = self.right_x_origin + robot_delta[0] * VR_POS_SCALE
            self.right_y = self.right_y_origin + robot_delta[1] * VR_POS_SCALE
            self.right_z = self.right_z_origin + robot_delta[2] * VR_POS_SCALE
            robot_relative_rot = self._map_vr_relative_rot_to_robot(self.vr_initial_rot['right'], right_quat)
            right_target = np.eye(4)
            right_target[:3, :3] = robot_relative_rot @ self.robot_initial_rot['right']
            right_target[:3, 3] = [self.right_x, self.right_y, self.right_z]
            self._set_filtered_target_tf("right", right_target)

        # 处理左手控制器
        left_grip = left_controller['gripActive']
        left_trigger = left_controller['trigger']
        left_pos = left_controller['position']
        left_quat = left_controller['quaternion']

        if left_trigger and left_grip:
            self.left_grip_num = GRIPPER_OPEN_QPOS
        else:
            self.left_grip_num = GRIPPER_CLOSED_QPOS
        # 设置左手控制器原点
        if left_grip and self.vr_origin['left'] is None:
            self.reset_target_q['left'] = None
            self.vr_origin['left'] = left_pos.copy()
            # 记录初始位置
            self.left_x_origin = self.left_x
            self.left_y_origin = self.left_y
            self.left_z_origin = self.left_z
            # 记录初始姿态（四元数）
            self.vr_initial_rot['left'] = left_quat.copy()
            # 记录机器人当前旋转角度作为初始旋转
            self.robot_initial_rot['left'] = self.left_target_tf[:3, :3].copy()
            print(f"🎯 左手控制器原点已设置: {self.vr_origin['left']}")
            print(f"🎯 左手控制器初始姿态已记录: {self.vr_initial_rot['left']}")
            print("🎯 机器人左臂初始末端姿态矩阵已记录")
        elif not left_grip:
            self.vr_origin['left'] = None
            self.vr_initial_rot['left'] = None
            self.last_ik_target_tf['left'] = None
            self.chest_limit_face['left'] = None

        # 使用左手控制器控制机器人左臂
        if self.vr_origin['left'] and self.vr_initial_rot['left']:
            robot_delta = self._map_vr_relative_pos_to_robot(self.vr_origin['left'], left_pos)
            self.left_x = self.left_x_origin + robot_delta[0] * VR_POS_SCALE
            self.left_y = self.left_y_origin + robot_delta[1] * VR_POS_SCALE
            self.left_z = self.left_z_origin + robot_delta[2] * VR_POS_SCALE
            robot_relative_rot = self._map_vr_relative_rot_to_robot(self.vr_initial_rot['left'], left_quat)
            left_target = np.eye(4)
            left_target[:3, :3] = robot_relative_rot @ self.robot_initial_rot['left']
            left_target[:3, 3] = [self.left_x, self.left_y, self.left_z]
            self._set_filtered_target_tf("left", left_target)

    def _solve_side_ik(self, side, current_time):
        if side == "right":
            target = self.right_target_tf.copy()
            arm = self.right_arm
            qpos_slice = RIGHT_QPOS
            grip_index = RIGHT_GRIP_INDEX
            grip_num = self.right_grip_num
            label = "右臂"
        else:
            target = self.left_target_tf.copy()
            arm = self.left_arm
            qpos_slice = LEFT_QPOS
            grip_index = LEFT_GRIP_INDEX
            grip_num = self.left_grip_num
            label = "左臂"

        command_updated = False
        with self.data_lock:
            current_q = self.data.qpos[:ROBOT_QPOS_COUNT].copy()
            if abs(self.data.qpos[grip_index] - grip_num) > 1e-6:
                self.data.qpos[grip_index] = grip_num
                command_updated = True

        if not np.all(np.isfinite(target)):
            self._log_ik_failure(side, f"[警告] {label}目标位姿包含无效值，跳过{label}IK求解")
            return command_updated

        if current_time - self.last_ik_solve_time[side] < IK_MIN_INTERVAL:
            return command_updated

        if not self._target_changed_enough(side, target):
            return command_updated

        dof, info = arm.ik(target, current_q)
        self.last_ik_solve_time[side] = current_time
        if info["success"]:
            with self.data_lock:
                current_arm_q = self.data.qpos[qpos_slice].copy()
                target_arm_q = dof[qpos_slice]
                step = np.clip(target_arm_q - current_arm_q, -IK_MAX_JOINT_STEP, IK_MAX_JOINT_STEP)
                self.data.qpos[qpos_slice] = current_arm_q + step
                self.data.qpos[grip_index] = grip_num
            if not info.get("clamped", False):
                self.last_ik_target_tf[side] = target
            return True

        self._log_ik_failure(side, f"[警告] {label}IK求解失败!")
        return command_updated

    def _handle_active_ik_control(self, current_time):
        with self.vr_lock:
            right_active = self.vr_data['right']['gripActive']
            left_active = self.vr_data['left']['gripActive']

        command_updated = False
        if right_active:
            start = time.perf_counter()
            command_updated = self._solve_side_ik("right", current_time) or command_updated
            self._perf_add("ik_right", time.perf_counter() - start)
        if left_active:
            start = time.perf_counter()
            command_updated = self._solve_side_ik("left", current_time) or command_updated
            self._perf_add("ik_left", time.perf_counter() - start)
        if command_updated:
            start = time.perf_counter()
            with self.data_lock:
                self._publish_robot_command()
            self._perf_add("publish", time.perf_counter() - start)

    def _request_reset(self, side):
        if side == "right":
            self._set_target_tf("right", self.right_zero_tf)
            self.reset_target_q["right"] = DEFAULT_RIGHT_QPOS.copy()
        else:
            self._set_target_tf("left", self.left_zero_tf)
            self.reset_target_q["left"] = DEFAULT_LEFT_QPOS.copy()

        self.last_ik_target_tf[side] = None
        self.chest_limit_face[side] = None
        self.vr_origin[side] = None
        self.vr_initial_rot[side] = None

    def _step_reset(self, side):
        target_q = self.reset_target_q[side]
        if target_q is None:
            return False

        qpos_slice = RIGHT_QPOS if side == "right" else LEFT_QPOS
        with self.data_lock:
            current = self.data.qpos[qpos_slice].copy()
            delta = target_q - current
            step = np.clip(delta, -RESET_MAX_STEP, RESET_MAX_STEP)
            self.data.qpos[qpos_slice] = current + step
            self.data.qvel[qpos_slice] = 0.0
            done = np.all(np.abs(delta) <= RESET_MAX_STEP)

        if done:
            self.reset_target_q[side] = None
        return True

    def _handle_idle_controls(self):
        with self.vr_lock:
            right_grip = self.vr_data['right']['gripActive']
            right_a_button = self.vr_data['right']['aButton']
            left_grip = self.vr_data['left']['gripActive']
            left_x_button = self.vr_data['left']['xButton']

        if not right_grip and right_a_button and not left_x_button and not self.prev_right_a_button:
            self._request_reset("right")
        elif not left_grip and left_x_button and not right_a_button and not self.prev_left_x_button:
            self._request_reset("left")

        self.prev_right_a_button = right_a_button
        self.prev_left_x_button = left_x_button

        command_updated = False
        if self._step_reset("right"):
            command_updated = True
        if self._step_reset("left"):
            command_updated = True
        if command_updated:
            with self.data_lock:
                self._publish_robot_command()

    def close(self):
        send_data = {
            "x_val": 0,
            "y_val": 0,
            "theta_vel": 0,
            "height_axis": 0.0,
        }
        try:
            self.zmq_pub.send_json(send_data)
        except zmq.ZMQError:
            pass
        """关闭ZMQ套接字和上下文"""
        self.zmq_pub.close(linger=0)
        self.zmq_context.term()

    def _tap_key(self, key):
        self.keyboard_controller.press(key)
        self.keyboard_controller.release(key)

    def _handle_vr_button_keypress(self):
        with self.vr_lock:
            right = self.vr_data['right'].copy()
            left = self.vr_data['left'].copy()

        no_grip_pressed = not right['gripActive'] and not left['gripActive']
        right_a_button = right['aButton']
        right_b_button = right['bButton']
        left_x_button = left['xButton']
        left_y_button = left['yButton']
        head_reset_combo = right_a_button and left_x_button

        if no_grip_pressed and right_b_button and not self.prev_right_b_button:
            print("触发一次右方向键")
            self._tap_key(keyboard.Key.right)
        if no_grip_pressed and left_y_button and not self.prev_left_y_button:
            print("触发一次左方向键")
            self._tap_key(keyboard.Key.left)


        self.prev_right_b_button = right_b_button
        self.prev_left_y_button = left_y_button

    def _publish_robot_command(self):
        qpos_rad = self.data.qpos[:ROBOT_QPOS_COUNT]
        qpos_command = np.round(np.degrees(qpos_rad), 1)
        qpos_command[RIGHT_GRIP_INDEX] = round(qpos_rad[RIGHT_GRIP_INDEX], 1)
        qpos_command[LEFT_GRIP_INDEX] = round(qpos_rad[LEFT_GRIP_INDEX], 1)
        with self.vr_lock:
            right = self.vr_data['right'].copy()
            left = self.vr_data['left'].copy()

        theta_vel = 0
        right_grip = right['gripActive']
        if right_grip and right['bButton']:
            theta_vel = -30
        elif right_grip and left['yButton']:
            theta_vel = 30

        right_thumbstick_y = right['thumbstick']['y']
        x_val = (right_thumbstick_y * 0.3) if right_grip and abs(right_thumbstick_y) > 0.5 else 0.0
        right_thumbstick_x = right['thumbstick']['x']
        y_val = (right_thumbstick_x * 0.3) if right_grip and abs(right_thumbstick_x) > 0.5 else 0.0
        left_thumbstick_y = left['thumbstick']['y']
        left_grip = left['gripActive']
        if left_grip and abs(left_thumbstick_y) > LIFT_THUMBSTICK_DEADZONE:
            self.height_axis = float(np.clip(left_thumbstick_y, -1.0, 1.0))
        else:
            self.height_axis = 0.0
        send_data = {
            "qpos": qpos_command.tolist(),
            "x_val": x_val,
            "y_val": y_val,
            "theta_vel": theta_vel,
            "height_axis": self.height_axis,
        }
        self.zmq_pub.send_json(send_data)
        self.last_command_publish_time = time.perf_counter()

    def _publish_stop_on_grip_release(self):
        with self.vr_lock:
            right_grip = self.vr_data['right']['gripActive']
            left_grip = self.vr_data['left']['gripActive']

        right_released = self.prev_right_motion_grip and not right_grip
        left_released = self.prev_left_lift_grip and not left_grip
        self.prev_right_motion_grip = right_grip
        self.prev_left_lift_grip = left_grip

        if right_released or left_released:
            # 安全停机：握把一松开，底盘和升降必须立即发 0，而不是等摇杆回中。
            with self.data_lock:
                self._publish_robot_command()

    def run_loop(self):
        """主循环"""
        iteration = 0
        last_print_time = time.time()
        
        while self.is_running():
            loop_start = time.perf_counter()
            # 处理VR控制器输入
            start = time.perf_counter()
            self.handle_vr_input()
            self._perf_add("vr_input", time.perf_counter() - start)
            start = time.perf_counter()
            self._publish_stop_on_grip_release()
            self._perf_add("grip_release_stop", time.perf_counter() - start)
            start = time.perf_counter()
            self._handle_vr_button_keypress()
            self._perf_add("buttons", time.perf_counter() - start)

            # # 每0.5秒打印一次状态
            current_time = time.time()
            if current_time - last_print_time > 0.5:
                start = time.perf_counter()
                with self.data_lock:
                    print("\n" + self._fk_status_text())
                self._perf_add("fk_print", time.perf_counter() - start)
                last_print_time = current_time

            if self.vr_run:
                self._handle_active_ik_control(current_time)
            else:
                self._handle_idle_controls()

            # 稳定心跳发布当前机器人命令，避免 LeRobot 录制端因为长时间没有新 ZMQ 包而录到空 episode。
            publish_time = time.perf_counter()
            if publish_time - self.last_command_publish_time >= COMMAND_PUBLISH_INTERVAL:
                start = time.perf_counter()
                with self.data_lock:
                    self._publish_robot_command()
                self._perf_add("publish_heartbeat", time.perf_counter() - start)
            
            # 只做运动学刷新，不进行动力学积分，避免无控制时关节漂移。
            start = time.perf_counter()
            with self.data_lock:
                self._kinematic_forward()
            self._perf_add("mj_forward", time.perf_counter() - start)
            if iteration % VIEWER_SYNC_EVERY == 0:
                start = time.perf_counter()
                self.sync()
                self._perf_add("viewer_sync", time.perf_counter() - start)
            time.sleep(MAIN_LOOP_SLEEP)
            self._perf_report_if_due(time.perf_counter() - loop_start)
            iteration += 1

def parse_args():
    parser = argparse.ArgumentParser(
        description="Receive VR data and run MuJoCo + Pinocchio FK/IK for hei reBot lift teleoperation."
    )
    parser.add_argument(
        "--vr-endpoint",
        default=DEFAULT_VR_ENDPOINT,
        help="VR data ZMQ SUB endpoint, default: tcp://localhost:5567",
    )
    parser.add_argument(
        "--command-endpoint",
        default=DEFAULT_COMMAND_ENDPOINT,
        help="robot command ZMQ PUB bind endpoint, default: tcp://*:6558",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    model = mujoco.MjModel.from_xml_path(SCENE_XML_PATH)
    data = mujoco.MjData(model)

    viewer = CustomViewer(
        model,
        data,
        command_endpoint=args.command_endpoint,
        vr_endpoint=args.vr_endpoint,
    )
    viewer.cam.distance = 3
    viewer.cam.azimuth = 0
    viewer.cam.elevation = -30

    try:
        viewer.run_loop()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n程序出错: {e}")
    finally:
        viewer.close()


if __name__ == "__main__":
    main()
