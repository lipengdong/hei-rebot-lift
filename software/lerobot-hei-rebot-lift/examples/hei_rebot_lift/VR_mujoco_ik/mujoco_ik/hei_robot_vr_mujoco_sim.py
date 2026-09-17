#!/usr/bin/env python
"""VR kinematic simulation for the complete HEI ReBot Lift model.

This program receives Telegrip controller poses and drives only the MuJoCo
simulation. It never opens the real-robot command publisher.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

# 在创建 IK solver 前设置连续性约束，抑制快速运动时的跳解。
os.environ.setdefault("IK_SMOOTH_WEIGHT_FIRST_TWO", "2.0")
os.environ.setdefault("IK_SMOOTH_WEIGHT_OTHER", "1.0")
os.environ.setdefault("IK_SMOOTH_COST_WEIGHT", "0.0015")
os.environ.setdefault("IK_MAX_STEP_FIRST_TWO", "0.16")
os.environ.setdefault("IK_MAX_STEP_OTHER", "0.22")
os.environ.setdefault("SAM101_IPOPT_MAX_ITER", "50")
os.environ.setdefault("SAM101_IPOPT_ACCEPTABLE_TOL", "1e-3")

import mujoco
import mujoco.viewer
import numpy as np
import pinocchio as pin
import zmq


BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "model" / "HEI_robot_urdf"
DEFAULT_URDF = MODEL_DIR / "urdf" / "HEI_robot_urdf.urdf"
DEFAULT_VR_ENDPOINT = "tcp://localhost:5567"

# 加载当前 mujoco_ik 目录内已经验证过的 Pinocchio/CasADi IK 实现。
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
from hei_robot_mujoco_scene import (  # noqa: E402
    GRASPABLE_OBJECTS,
    SCENE_GEOMS,
    TABLE_CENTER_X_M,
    TABLE_CENTER_Y_M,
    TABLE_HALF_LENGTH_X_M,
    TABLE_HALF_WIDTH_Y_M,
    TABLE_TOP_Z_M,
    GraspableObjectSpec,
    build_mujoco_model,
)
from src import pinocchio_kinematic  # noqa: E402
from src import utils  # noqa: E402


RIGHT_ARM_JOINTS = tuple(f"a_right_joint{i}" for i in range(1, 7))
LEFT_ARM_JOINTS = tuple(f"b_left_joint{i}" for i in range(1, 7))
ARM_JOINTS = {"right": RIGHT_ARM_JOINTS, "left": LEFT_ARM_JOINTS}
TCP_FRAMES = {"right": "a_right_tcp", "left": "b_left_tcp"}
GRIPPER_JOINTS = {
    "right": ("a_right_end_joint_L_finger", "a_right_end_joint_R_finger"),
    "left": ("b_left_end_joint_L_finger", "b_left_end_joint_R_finger"),
}
LIFT_JOINT = "lift_joint"
WHEEL_JOINTS = (
    "front_left_wheel_joint",
    "front_right_wheel_joint",
    "rear_left_wheel_joint",
    "rear_right_wheel_joint",
)
BASE_FRAME = "base_footprint"

DEFAULT_ARM_Q = np.array([0.0, -0.5, -0.5, 0.0, 0.0, 0.0], dtype=float)
GRIPPER_OPEN_M = 0.05
GRIPPER_CLOSED_M = 0.0

# WebXR: X 向右、Y 向上、Z 向后；机器人: X 向前、Y 向左、Z 向上。
VR_TO_ROBOT_ROT = np.array(
    [
        [0.0, 0.0, -1.0],
        [-1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ],
    dtype=float,
)

TARGET_POS_EPS_M = 0.0012
TARGET_ROT_EPS_RAD = np.deg2rad(0.35)
MAX_MUJOCO_JOINT_STEP_RAD = 0.08
# 只判断候选目标是否连续可达，不改变原有速度、加速度和电机参数。
IK_TARGET_MAX_JOINT_DELTA_RAD = np.deg2rad([20.0, 20.0, 20.0, 25.0, 25.0, 25.0])
IK_TARGET_MAX_POSITION_ERROR_M = 0.100
# 只有完整 VR 目标不可达时才执行边界投影。5 次二分最多额外调用 5 次 IK，
# 可将“最后可达位姿 -> 手柄请求位姿”的线段细分到 1/32。
IK_BOUNDARY_PROJECTION_ITERATIONS = 5
IK_BOUNDARY_MIN_TRANSLATION_M = 0.0005
IK_BOUNDARY_MIN_ROTATION_RAD = np.deg2rad(0.20)
# 每个新 VR 目标最多允许若干次 IK 收敛，之后锁住关节，避免静止时反复寻解。
IK_SETTLE_MAX_STEPS = 8
IK_SETTLE_MAX_RECOVERY_STEPS = 100
IK_JOINT_HOLD_EPS_RAD = 0.001
LIFT_DEADZONE = 0.15
CHASSIS_DEADZONE = 0.15
CHASSIS_MAX_LINEAR_M_S = 0.30
CHASSIS_MAX_YAW_RAD_S = np.deg2rad(30.0)
CHASSIS_SMOOTH_ALPHA = 0.35
# 与 HeiRebotLiftConfig 和 _ChassisRuntime._body_to_wheel_speeds 保持一致。
CHASSIS_X_SIGN = -1.0
CHASSIS_Y_SIGN = -1.0
CHASSIS_THETA_SIGN = 1.0
CHASSIS_LINEAR_SPEED_SCALE = 9.0
CHASSIS_YAW_SPEED_SCALE = 2.0
CHASSIS_MAX_WHEEL_SPEED_RAD_S = 9.0
CHASSIS_WHEEL_SIGN = np.ones(4, dtype=float)
# 真机驱动顺序是 [RF, RR, LR, LF]。
O_TYPE_KINEMATICS = np.array(
    [
        [-1.0, -1.0, -1.0],
        [-1.0, 1.0, -1.0],
        [1.0, 1.0, -1.0],
        [1.0, -1.0, -1.0],
    ],
    dtype=float,
)
# 将真机电机顺序重排成模型关节顺序 [FL, FR, RL, RR]。
MODEL_WHEEL_FROM_MOTOR_ORDER = np.array([3, 0, 2, 1], dtype=int)
RESET_MAX_STEP_RAD = 0.015
VR_STALE_TIMEOUT_S = 1.0
STATUS_INTERVAL_S = 1.0
GRIPPER_CLOSED_THRESHOLD_M = 0.01


@dataclass
class ArmRuntime:
    side: str
    solver: pinocchio_kinematic.Kinematics
    pin_q_indices: np.ndarray
    target_tf: np.ndarray
    controller_origin_pos: dict[str, float] | None = None
    controller_origin_quat: dict[str, float] | None = None
    robot_origin_tf: np.ndarray | None = None
    controller_origin_q: np.ndarray | None = None
    last_solved_target_tf: np.ndarray | None = None
    settle_steps_remaining: int = 0
    reset_requested: bool = False
    last_failure_log_s: float = 0.0
    last_accepted_ik_q: np.ndarray | None = None
    last_accepted_target_tf: np.ndarray | None = None


@dataclass
class GraspableObjectRuntime:
    spec: GraspableObjectSpec
    body_id: int
    initial_pos: np.ndarray
    initial_quat: np.ndarray
    held_by: str | None = None
    tcp_relative_pos: np.ndarray | None = None
    tcp_relative_rot: np.ndarray | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Control the complete HEI robot MuJoCo simulation using Telegrip VR data."
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_URDF, help="Complete HEI robot URDF path.")
    parser.add_argument("--vr-endpoint", default=DEFAULT_VR_ENDPOINT, help="Telegrip ZMQ SUB endpoint.")
    parser.add_argument("--vr-pos-scale", type=float, default=1.0, help="VR translation to robot TCP scale.")
    parser.add_argument("--lift-speed-m-s", type=float, default=0.20, help="Maximum simulated lift speed.")
    parser.add_argument("--vr-timeout-s", type=float, default=VR_STALE_TIMEOUT_S, help="VR packet stale timeout.")
    parser.add_argument("--plain-scene", action="store_true", help="Disable floor, lights, markings, and axes.")
    parser.add_argument("--headless-check", action="store_true", help="Build models and run checks without a viewer.")
    parser.add_argument("--verbose", action="store_true", help="Print additional VR and IK diagnostics.")
    return parser.parse_args()


def empty_controller(side: str) -> dict:
    buttons = {"xButton": 0, "yButton": 0} if side == "left" else {"aButton": 0, "bButton": 0}
    return {
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "quaternion": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        "poseValid": False,
        "gripActive": False,
        "trigger": False,
        "thumbstick": {"x": 0.0, "y": 0.0, "pressed": 0},
        **buttons,
    }


class HEIRobotVRSimulator:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.model_path = args.model.expanduser().resolve()
        if not self.model_path.is_file():
            raise FileNotFoundError(f"URDF not found: {self.model_path}")

        print(f"[HEI VR Sim] loading MuJoCo model: {self.model_path}", flush=True)
        self.scene_enabled = not bool(getattr(args, "plain_scene", False))
        self.model = build_mujoco_model(self.model_path, add_environment=self.scene_enabled)
        self.data = mujoco.MjData(self.model)
        self.data_lock = threading.Lock()
        self.vr_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.viewer = None
        self.show_frames = False
        self.real_command_enabled = bool(getattr(self, "real_command_enabled", False))

        self.mj_qpos = {name: self._mujoco_qpos_address(name) for name in self._required_movable_joints()}
        self.vr_data = {"left": empty_controller("left"), "right": empty_controller("right")}
        self.last_vr_packet_s = 0.0
        self.received_packet_count = 0
        self.previous_buttons = {"right_a": False, "left_x": False}
        self.gripper_target = {"right": GRIPPER_CLOSED_M, "left": GRIPPER_CLOSED_M}
        self.sim_chassis_velocity = np.zeros(3, dtype=float)
        self.base_pose = np.zeros(3, dtype=float)
        self.base_body_id = self._mujoco_body_id(BASE_FRAME)
        self.base_initial_pos = self.model.body_pos[self.base_body_id].copy()
        self.base_initial_quat = self.model.body_quat[self.base_body_id].copy()
        self.graspable_objects: dict[str, GraspableObjectRuntime] = {}
        self.previous_gripper_closed = {"right": True, "left": True}
        self._initialize_graspable_objects()
        self.last_status_s = 0.0

        self._reset_full_pose()
        self.arms = self._build_arm_solvers()
        self._validate_frames_and_axes()

        self.listener_thread = threading.Thread(target=self._vr_listener, name="hei-vr-zmq", daemon=True)
        self.listener_thread.start()

    def _required_movable_joints(self) -> tuple[str, ...]:
        return (
            *WHEEL_JOINTS,
            LIFT_JOINT,
            *RIGHT_ARM_JOINTS,
            *GRIPPER_JOINTS["right"],
            *LEFT_ARM_JOINTS,
            *GRIPPER_JOINTS["left"],
        )

    def _mujoco_joint_id(self, name: str) -> int:
        value = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if value < 0:
            raise ValueError(f"MuJoCo model is missing joint: {name}")
        return value

    def _mujoco_qpos_address(self, name: str) -> int:
        return int(self.model.jnt_qposadr[self._mujoco_joint_id(name)])

    def _mujoco_body_id(self, name: str) -> int:
        value = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, name)
        if value < 0:
            raise ValueError(f"MuJoCo model is missing frame/body: {name}")
        return value

    def _initialize_graspable_objects(self) -> None:
        if not self.scene_enabled:
            return
        for object_spec in GRASPABLE_OBJECTS:
            body_id = self._mujoco_body_id(object_spec.body_name)
            self.graspable_objects[object_spec.body_name] = GraspableObjectRuntime(
                spec=object_spec,
                body_id=body_id,
                initial_pos=self.model.body_pos[body_id].copy(),
                initial_quat=self.model.body_quat[body_id].copy(),
            )

    def _get_joint_q(self, names: tuple[str, ...]) -> np.ndarray:
        return np.array([self.data.qpos[self.mj_qpos[name]] for name in names], dtype=float)

    def _set_joint_q(self, names: tuple[str, ...], values: np.ndarray) -> None:
        for name, value in zip(names, values, strict=True):
            joint_id = self._mujoco_joint_id(name)
            if bool(self.model.jnt_limited[joint_id]):
                low, high = self.model.jnt_range[joint_id]
                value = float(np.clip(value, low, high))
            self.data.qpos[self.mj_qpos[name]] = value

    def _set_gripper(self, side: str, opening_m: float) -> None:
        opening_m = float(np.clip(opening_m, GRIPPER_CLOSED_M, GRIPPER_OPEN_M))
        primary, follower = GRIPPER_JOINTS[side]
        self.data.qpos[self.mj_qpos[primary]] = opening_m
        # MuJoCo 不执行 URDF mimic，右手指必须显式写成左手指的反向位移。
        self.data.qpos[self.mj_qpos[follower]] = -opening_m
        self.gripper_target[side] = opening_m

    def _reset_full_pose(self) -> None:
        with self.data_lock:
            self.data.qpos[:] = 0.0
            self.data.qvel[:] = 0.0
            self.base_pose[:] = 0.0
            self.sim_chassis_velocity[:] = 0.0
            self.model.body_pos[self.base_body_id] = self.base_initial_pos
            self.model.body_quat[self.base_body_id] = self.base_initial_quat
            self._set_joint_q(RIGHT_ARM_JOINTS, DEFAULT_ARM_Q)
            self._set_joint_q(LEFT_ARM_JOINTS, DEFAULT_ARM_Q)
            self._set_gripper("right", GRIPPER_CLOSED_M)
            self._set_gripper("left", GRIPPER_CLOSED_M)
            self._reset_scene_objects()
            self.data.qpos[self.mj_qpos[LIFT_JOINT]] = 0.0
            mujoco.mj_forward(self.model, self.data)

    def _reset_scene_objects(self) -> None:
        for runtime in self.graspable_objects.values():
            self.model.body_pos[runtime.body_id] = runtime.initial_pos
            self.model.body_quat[runtime.body_id] = runtime.initial_quat
            runtime.held_by = None
            runtime.tcp_relative_pos = None
            runtime.tcp_relative_rot = None
        # 复位后夹爪已经闭合，标记为稳定闭合状态，避免下一帧误触发抓取边沿。
        self.previous_gripper_closed = {"right": True, "left": True}

    def _pin_joint_q_indices(self, pin_model: pin.Model, names: tuple[str, ...]) -> np.ndarray:
        indices = []
        for name in names:
            joint_id = pin_model.getJointId(name)
            if joint_id == 0 or pin_model.names[joint_id] != name:
                raise ValueError(f"Pinocchio model is missing joint: {name}")
            if pin_model.nqs[joint_id] != 1:
                raise ValueError(f"Arm joint {name} must have exactly one Pinocchio q value")
            indices.append(pin_model.idx_qs[joint_id])
        return np.asarray(indices, dtype=int)

    def _build_arm_solvers(self) -> dict[str, ArmRuntime]:
        # Pinocchio 中 continuous 轮子各占两个 q，因此不能复用 MuJoCo qpos 下标。
        full_pin_model = pin.buildModelFromUrdf(str(self.model_path))
        reference_q = pin.neutral(full_pin_model)
        for side in ("right", "left"):
            indices = self._pin_joint_q_indices(full_pin_model, ARM_JOINTS[side])
            reference_q[indices] = DEFAULT_ARM_Q

        runtimes = {}
        for side in ("right", "left"):
            indices = self._pin_joint_q_indices(full_pin_model, ARM_JOINTS[side])
            solver = pinocchio_kinematic.Kinematics(TCP_FRAMES[side])
            solver.buildFromURDF(
                str(self.model_path),
                active_q_indices=indices,
                reference_q=reference_q,
            )
            zero_tf = solver.fk(DEFAULT_ARM_Q)
            runtimes[side] = ArmRuntime(
                side=side,
                solver=solver,
                pin_q_indices=indices,
                target_tf=zero_tf.copy(),
            )
            xyz = zero_tf[:3, 3]
            print(
                f"[HEI VR Sim] {side} IK ready: frame={TCP_FRAMES[side]}, "
                f"zero_tcp=({xyz[0]:.4f}, {xyz[1]:.4f}, {xyz[2]:.4f})",
                flush=True,
            )
        return runtimes

    def _validate_frames_and_axes(self) -> None:
        for frame in (BASE_FRAME, *TCP_FRAMES.values()):
            self._mujoco_body_id(frame)
        for joint in WHEEL_JOINTS:
            self._mujoco_joint_id(joint)
        if self.scene_enabled:
            for geom in SCENE_GEOMS:
                if mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, geom) < 0:
                    raise ValueError(f"MuJoCo debug scene is missing geom: {geom}")
        mujoco.mj_forward(self.model, self.data)
        lift_axis = self.data.xaxis[self._mujoco_joint_id(LIFT_JOINT)]
        if float(np.dot(lift_axis, np.array([0.0, 0.0, 1.0]))) < 0.999:
            raise ValueError(f"Lift axis must point to world +Z, got {lift_axis}")
        print(
            f"[HEI VR Sim] model ready: nbody={self.model.nbody}, njnt={self.model.njnt}, "
            f"nq={self.model.nq}; real-robot publishing="
            f"{'enabled' if self.real_command_enabled else 'disabled'}; "
            f"debug-scene={'enabled' if self.scene_enabled else 'disabled'}",
            flush=True,
        )

    @staticmethod
    def _parse_controller(side: str, controller: dict | None) -> dict:
        result = empty_controller(side)
        controller = controller if isinstance(controller, dict) else {}
        position = controller.get("position")
        quaternion = controller.get("quaternion")
        pose_valid = isinstance(position, dict) and isinstance(quaternion, dict)
        if pose_valid:
            try:
                result["position"] = {axis: float(position[axis]) for axis in "xyz"}
                result["quaternion"] = {axis: float(quaternion[axis]) for axis in "xyzw"}
            except (KeyError, TypeError, ValueError):
                pose_valid = False
        result["poseValid"] = pose_valid
        result["gripActive"] = bool(controller.get("gripActive", False)) and pose_valid
        result["trigger"] = bool(controller.get("trigger", False))
        thumbstick = controller.get("thumbstick")
        if isinstance(thumbstick, dict):
            result["thumbstick"] = {
                "x": float(thumbstick.get("x", 0.0)),
                "y": float(thumbstick.get("y", 0.0)),
                "pressed": int(bool(thumbstick.get("pressed", 0))),
            }
        if side == "left":
            result["xButton"] = int(bool(controller.get("xButton", 0)))
            result["yButton"] = int(bool(controller.get("yButton", 0)))
        else:
            result["aButton"] = int(bool(controller.get("aButton", 0)))
            result["bButton"] = int(bool(controller.get("bButton", 0)))
        return result

    def _vr_listener(self) -> None:
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        socket.setsockopt(zmq.RCVHWM, 2)
        socket.connect(self.args.vr_endpoint)
        poller = zmq.Poller()
        poller.register(socket, zmq.POLLIN)
        print(f"[HEI VR Sim] waiting for Telegrip: {self.args.vr_endpoint}", flush=True)
        try:
            while not self.stop_event.is_set():
                if socket not in dict(poller.poll(100)):
                    continue
                # 只保留队列中的最新帧，避免网络恢复后回放过期 VR 动作。
                message = socket.recv_string()
                while True:
                    try:
                        message = socket.recv_string(zmq.NOBLOCK)
                    except zmq.Again:
                        break
                # Telegrip normally sends "topic {json}", but accepting raw JSON makes
                # local diagnostics and alternative publishers compatible as well.
                stripped = message.lstrip()
                payload = stripped if stripped.startswith("{") else message.split(" ", 1)[-1]
                try:
                    packet = json.loads(payload)
                except json.JSONDecodeError:
                    if self.args.verbose:
                        print("[HEI VR Sim] ignored invalid VR JSON", flush=True)
                    continue
                with self.vr_lock:
                    if "leftController" in packet:
                        self.vr_data["left"] = self._parse_controller("left", packet["leftController"])
                    if "rightController" in packet:
                        self.vr_data["right"] = self._parse_controller("right", packet["rightController"])
                    self.last_vr_packet_s = time.monotonic()
                    self.received_packet_count += 1
        except zmq.ZMQError as exc:
            if not self.stop_event.is_set():
                print(f"[HEI VR Sim] VR receiver stopped unexpectedly: {exc}", flush=True)
        finally:
            socket.close(0)
            context.term()

    @staticmethod
    def _quat_to_rotation(quaternion: dict[str, float]) -> np.ndarray:
        return utils.quat2rotmat(
            [quaternion["w"], quaternion["x"], quaternion["y"], quaternion["z"]]
        )

    @classmethod
    def _relative_controller_rotation(
        cls,
        initial_quat: dict[str, float],
        current_quat: dict[str, float],
    ) -> np.ndarray:
        initial = cls._quat_to_rotation(initial_quat)
        current = cls._quat_to_rotation(current_quat)
        relative_vr = current @ initial.T
        return VR_TO_ROBOT_ROT @ relative_vr @ VR_TO_ROBOT_ROT.T

    @staticmethod
    def _controller_delta(
        origin: dict[str, float],
        current: dict[str, float],
    ) -> np.ndarray:
        delta_vr = np.array([current[axis] - origin[axis] for axis in "xyz"], dtype=float)
        return VR_TO_ROBOT_ROT @ delta_vr

    @staticmethod
    def _rotation_delta_angle(first: np.ndarray, second: np.ndarray) -> float:
        delta = first[:3, :3].T @ second[:3, :3]
        cosine = np.clip((np.trace(delta) - 1.0) * 0.5, -1.0, 1.0)
        return float(np.arccos(cosine))

    def _target_changed(self, arm: ArmRuntime, target: np.ndarray) -> bool:
        previous = arm.last_solved_target_tf
        if previous is None:
            return True
        translation = np.linalg.norm(target[:3, 3] - previous[:3, 3])
        rotation = self._rotation_delta_angle(previous, target)
        return translation >= TARGET_POS_EPS_M or rotation >= TARGET_ROT_EPS_RAD

    def _capture_controller_origin(self, arm: ArmRuntime, controller: dict) -> None:
        current_q = self._get_joint_q(ARM_JOINTS[arm.side])
        current_tf = arm.solver.fk(current_q)
        arm.controller_origin_pos = controller["position"].copy()
        arm.controller_origin_quat = controller["quaternion"].copy()
        arm.robot_origin_tf = current_tf.copy()
        arm.controller_origin_q = current_q.copy()
        arm.target_tf = current_tf.copy()
        # 抓取原点时 TCP 已经在当前位置，不应仅因 grip 按下就再求解一次。
        arm.last_solved_target_tf = current_tf.copy()
        arm.last_accepted_ik_q = current_q.copy()
        arm.last_accepted_target_tf = current_tf.copy()
        arm.settle_steps_remaining = 0
        arm.reset_requested = False
        print(f"[HEI VR Sim] {arm.side} controller origin captured", flush=True)

    @staticmethod
    def _release_controller_origin(arm: ArmRuntime) -> None:
        arm.controller_origin_pos = None
        arm.controller_origin_quat = None
        arm.robot_origin_tf = None
        arm.controller_origin_q = None
        arm.last_solved_target_tf = None
        arm.last_accepted_ik_q = None
        arm.last_accepted_target_tf = None
        arm.settle_steps_remaining = 0

    def _update_arm_target(self, arm: ArmRuntime, controller: dict) -> None:
        if arm.controller_origin_pos is None:
            self._capture_controller_origin(arm, controller)
        delta = self._controller_delta(arm.controller_origin_pos, controller["position"])
        relative_rotation = self._relative_controller_rotation(
            arm.controller_origin_quat,
            controller["quaternion"],
        )
        target = arm.robot_origin_tf.copy()
        target[:3, 3] = arm.robot_origin_tf[:3, 3] + delta * self.args.vr_pos_scale
        target[:3, :3] = relative_rotation @ arm.robot_origin_tf[:3, :3]
        # 以“上一个已接受的 VR 目标”为基准做死区判断。小于阈值的手柄噪声不进入 IK；
        # 微小位移会继续累积，总变化超过阈值后仍会被接受，不会丢失慢速跟随。
        if self._target_changed(arm, target):
            arm.target_tf = target
            arm.last_solved_target_tf = target.copy()
            arm.settle_steps_remaining = IK_SETTLE_MAX_STEPS

    def _candidate_rejection_reason(
        self,
        arm: ArmRuntime,
        current_q: np.ndarray,
        raw_q: np.ndarray,
        target_tf: np.ndarray | None = None,
    ) -> str | None:
        if target_tf is None:
            target_tf = arm.target_tf
        if raw_q.shape != current_q.shape or not np.all(np.isfinite(raw_q)):
            return "invalid raw IK solution"
        # 与上一帧已经接受的完整 IK 解比较，而不是和仍在追赶目标的当前关节角比较。
        # 这样正常快速运动不会因关节暂时落后而被误判为换解。
        reference_q = arm.last_accepted_ik_q
        if reference_q is None:
            reference_q = current_q
        returning_to_origin = False
        if (
            arm.robot_origin_tf is not None
            and arm.controller_origin_q is not None
            and arm.last_accepted_target_tf is not None
        ):
            requested_distance = np.linalg.norm(
                target_tf[:3, 3] - arm.robot_origin_tf[:3, 3]
            )
            accepted_distance = np.linalg.norm(
                arm.last_accepted_target_tf[:3, 3] - arm.robot_origin_tf[:3, 3]
            )
            requested_joint_distance = np.linalg.norm(raw_q - arm.controller_origin_q)
            accepted_joint_distance = np.linalg.norm(reference_q - arm.controller_origin_q)
            returning_to_origin = (
                requested_distance < accepted_distance - TARGET_POS_EPS_M
                and requested_joint_distance < accepted_joint_distance
            )
        changed = np.flatnonzero(np.abs(raw_q - reference_q) > IK_TARGET_MAX_JOINT_DELTA_RAD)
        if returning_to_origin:
            changed = np.empty(0, dtype=int)
        if changed.size:
            joints = ", ".join(str(index + 1) for index in changed)
            return f"IK branch jump at joint {joints}"
        raw_tf = arm.solver.fk(raw_q)
        position_error = float(np.linalg.norm(target_tf[:3, 3] - raw_tf[:3, 3]))
        if not np.isfinite(position_error) or position_error > IK_TARGET_MAX_POSITION_ERROR_M:
            return f"unreachable target (position error={position_error * 1000.0:.1f} mm)"
        return None

    @staticmethod
    def _interpolate_target(start_tf: np.ndarray, end_tf: np.ndarray, alpha: float) -> np.ndarray:
        """在 SE(3) 中插值 TCP 目标：位置线性插值，姿态沿最短旋转路径插值。"""
        alpha = float(np.clip(alpha, 0.0, 1.0))
        interpolated = np.eye(4)
        interpolated[:3, 3] = (
            start_tf[:3, 3] + alpha * (end_tf[:3, 3] - start_tf[:3, 3])
        )
        relative_rotation = start_tf[:3, :3].T @ end_tf[:3, :3]
        interpolated[:3, :3] = (
            start_tf[:3, :3] @ pin.exp3(alpha * pin.log3(relative_rotation))
        )
        return interpolated

    def _solve_ik_candidate(
        self,
        arm: ArmRuntime,
        current_q: np.ndarray,
        target_tf: np.ndarray,
    ) -> tuple[np.ndarray | None, np.ndarray | None, str | None]:
        """求解并检查一个 TCP 候选目标，但不将结果写入 MuJoCo。"""
        full_solution, info = arm.solver.ik(target_tf, current_q)
        if not info.get("success", False):
            return None, None, "IK solve failed"
        raw_solution = info.get("raw_solution")
        if raw_solution is None:
            return None, None, "raw IK diagnostics unavailable"
        raw_q = np.asarray(raw_solution, dtype=float)[arm.pin_q_indices]
        reason = self._candidate_rejection_reason(arm, current_q, raw_q, target_tf)
        if reason is not None:
            return None, raw_q, reason
        return np.asarray(full_solution, dtype=float), raw_q, None

    def _project_target_to_workspace(
        self,
        arm: ArmRuntime,
        current_q: np.ndarray,
        requested_tf: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, float] | None:
        """从最后可达位姿向 VR 请求位姿二分搜索最远可执行目标。"""
        safe_tf = arm.last_accepted_target_tf
        if safe_tf is None:
            safe_tf = arm.solver.fk(current_q)
        safe_tf = safe_tf.copy()

        low = 0.0
        high = 1.0
        best: tuple[np.ndarray, np.ndarray, np.ndarray, float] | None = None
        for _ in range(IK_BOUNDARY_PROJECTION_ITERATIONS):
            alpha = 0.5 * (low + high)
            candidate_tf = self._interpolate_target(safe_tf, requested_tf, alpha)
            full_solution, raw_q, reason = self._solve_ik_candidate(
                arm, current_q, candidate_tf
            )
            if reason is None and full_solution is not None and raw_q is not None:
                best = (candidate_tf, full_solution, raw_q, alpha)
                low = alpha
            else:
                high = alpha

        if best is None:
            return None
        projected_tf = best[0]
        translation = np.linalg.norm(projected_tf[:3, 3] - safe_tf[:3, 3])
        rotation = self._rotation_delta_angle(safe_tf, projected_tf)
        if (
            translation < IK_BOUNDARY_MIN_TRANSLATION_M
            and rotation < IK_BOUNDARY_MIN_ROTATION_RAD
        ):
            return None
        return best

    def _accept_arm_candidate(
        self,
        arm: ArmRuntime,
        current_q: np.ndarray,
        target_tf: np.ndarray,
        full_solution: np.ndarray,
        raw_q: np.ndarray,
    ) -> None:
        arm.target_tf = target_tf.copy()
        arm.last_accepted_ik_q = raw_q.copy()
        arm.last_accepted_target_tf = target_tf.copy()
        # 快速回程可能远大于 8 * 0.08 rad。只延长收敛周期，不改变原来的
        # 单步幅度；接近目标后仍由下方 TCP 误差条件提前停止。
        required_steps = int(
            np.ceil(np.max(np.abs(raw_q - current_q)) / MAX_MUJOCO_JOINT_STEP_RAD)
        ) + 2
        arm.settle_steps_remaining = max(
            arm.settle_steps_remaining,
            min(required_steps, IK_SETTLE_MAX_RECOVERY_STEPS),
        )
        target_q = full_solution[arm.pin_q_indices]
        step = np.clip(target_q - current_q, -MAX_MUJOCO_JOINT_STEP_RAD, MAX_MUJOCO_JOINT_STEP_RAD)
        if np.max(np.abs(step)) < IK_JOINT_HOLD_EPS_RAD:
            arm.settle_steps_remaining = 0
            return
        applied_q = current_q + step
        self._set_joint_q(ARM_JOINTS[arm.side], applied_q)
        achieved_tf = arm.solver.fk(applied_q)
        position_error = np.linalg.norm(target_tf[:3, 3] - achieved_tf[:3, 3])
        rotation_error = self._rotation_delta_angle(achieved_tf, target_tf)
        if position_error < TARGET_POS_EPS_M and rotation_error < TARGET_ROT_EPS_RAD:
            arm.settle_steps_remaining = 0

    def _reject_arm_target(self, arm: ArmRuntime, current_q: np.ndarray, reason: str) -> None:
        # 拒绝危险目标后仍继续靠近最后安全目标，不会在正常追赶过程中突然冻结。
        # last_solved_target_tf 回退到安全目标，使下一帧立即重试最新手柄目标；快速回程
        # 因此无需松开 grip，也不会被先前的边界目标缓存卡住。
        safe_q = arm.last_accepted_ik_q
        safe_tf = arm.last_accepted_target_tf
        if safe_q is None:
            safe_q = current_q
        if safe_tf is None:
            safe_tf = arm.solver.fk(current_q)
        arm.target_tf = safe_tf.copy()
        arm.last_solved_target_tf = safe_tf.copy()
        arm.settle_steps_remaining = 0
        arm.solver.init_data = current_q.copy()
        safe_step = np.clip(
            safe_q - current_q,
            -MAX_MUJOCO_JOINT_STEP_RAD,
            MAX_MUJOCO_JOINT_STEP_RAD,
        )
        if np.max(np.abs(safe_step)) >= IK_JOINT_HOLD_EPS_RAD:
            self._set_joint_q(ARM_JOINTS[arm.side], current_q + safe_step)
        now = time.monotonic()
        if now - arm.last_failure_log_s >= 1.0:
            print(f"[HEI VR Boundary] {arm.side}: {reason}; keeping current pose", flush=True)
            arm.last_failure_log_s = now

    def _solve_arm(self, arm: ArmRuntime) -> None:
        if arm.settle_steps_remaining <= 0:
            return
        current_q = self._get_joint_q(ARM_JOINTS[arm.side])
        requested_tf = arm.target_tf.copy()
        full_solution, raw_q, reason = self._solve_ik_candidate(
            arm, current_q, requested_tf
        )
        arm.settle_steps_remaining -= 1
        if reason is not None:
            projection = self._project_target_to_workspace(arm, current_q, requested_tf)
            if projection is None:
                self._reject_arm_target(arm, current_q, reason)
                return
            projected_tf, full_solution, raw_q, alpha = projection
            # last_solved_target_tf 保留投影后的安全目标。下一帧若手柄仍在
            # 边界外，_update_arm_target 会继续重试原始请求，因此可沿边界滑动。
            arm.last_solved_target_tf = projected_tf.copy()
            now = time.monotonic()
            if now - arm.last_failure_log_s >= 1.0:
                print(
                    f"[HEI VR Boundary] {arm.side}: projected {alpha * 100.0:.1f}% "
                    f"toward requested target ({reason})",
                    flush=True,
                )
                arm.last_failure_log_s = now
            target_tf = projected_tf
        else:
            target_tf = requested_tf
        self._accept_arm_candidate(arm, current_q, target_tf, full_solution, raw_q)

    def _step_reset(self, arm: ArmRuntime) -> None:
        if not arm.reset_requested:
            return
        current = self._get_joint_q(ARM_JOINTS[arm.side])
        delta = DEFAULT_ARM_Q - current
        self._set_joint_q(
            ARM_JOINTS[arm.side],
            current + np.clip(delta, -RESET_MAX_STEP_RAD, RESET_MAX_STEP_RAD),
        )
        if np.all(np.abs(delta) <= RESET_MAX_STEP_RAD):
            arm.reset_requested = False
            arm.target_tf = arm.solver.fk(DEFAULT_ARM_Q)
            arm.last_solved_target_tf = None
            arm.settle_steps_remaining = 0
            print(f"[HEI VR Sim] {arm.side} arm reset complete", flush=True)

    @staticmethod
    def _deadzone(value: float, deadzone: float) -> float:
        value = float(np.clip(value, -1.0, 1.0))
        magnitude = abs(value)
        if magnitude <= deadzone:
            return 0.0
        return float(np.sign(value) * (magnitude - deadzone) / (1.0 - deadzone))

    @staticmethod
    def _smooth(current: float, target: float) -> float:
        return float(current + CHASSIS_SMOOTH_ALPHA * (target - current))

    @staticmethod
    def _quat_multiply(first: np.ndarray, second: np.ndarray) -> np.ndarray:
        """Multiply MuJoCo quaternions stored as [w, x, y, z]."""
        w1, x1, y1, z1 = first
        w2, x2, y2, z2 = second
        return np.array(
            [
                w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
                w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            ],
            dtype=float,
        )

    @staticmethod
    def _rotation_to_quat(rotation: np.ndarray) -> np.ndarray:
        quat = np.empty(4, dtype=float)
        mujoco.mju_mat2Quat(quat, np.asarray(rotation, dtype=float).reshape(9))
        quat /= np.linalg.norm(quat)
        return quat

    def _held_object(self, side: str) -> GraspableObjectRuntime | None:
        return next(
            (runtime for runtime in self.graspable_objects.values() if runtime.held_by == side),
            None,
        )

    def _try_stable_grasp(self, side: str) -> bool:
        if self._held_object(side) is not None:
            return False

        tcp_id = self._mujoco_body_id(TCP_FRAMES[side])
        tcp_pos = self.data.xpos[tcp_id].copy()
        tcp_rot = self.data.xmat[tcp_id].reshape(3, 3).copy()
        candidates: list[tuple[float, GraspableObjectRuntime]] = []
        for runtime in self.graspable_objects.values():
            if runtime.held_by is not None:
                continue
            distance = float(np.linalg.norm(self.data.xpos[runtime.body_id] - tcp_pos))
            if distance <= runtime.spec.grasp_radius_m:
                candidates.append((distance, runtime))
        if not candidates:
            return False

        distance, runtime = min(candidates, key=lambda item: item[0])
        object_pos = self.data.xpos[runtime.body_id].copy()
        object_rot = self.data.xmat[runtime.body_id].reshape(3, 3).copy()
        # 保存物体相对 TCP 的位姿，抓起时不会突然吸附到夹爪中心或改变朝向。
        runtime.tcp_relative_pos = tcp_rot.T @ (object_pos - tcp_pos)
        runtime.tcp_relative_rot = tcp_rot.T @ object_rot
        runtime.held_by = side
        print(
            f"[HEI VR Sim] {side} grasped {runtime.spec.body_name} at {distance:.3f}m",
            flush=True,
        )
        return True

    def _update_held_objects(self) -> bool:
        changed = False
        for runtime in self.graspable_objects.values():
            if runtime.held_by is None:
                continue
            tcp_id = self._mujoco_body_id(TCP_FRAMES[runtime.held_by])
            tcp_pos = self.data.xpos[tcp_id]
            tcp_rot = self.data.xmat[tcp_id].reshape(3, 3)
            world_pos = tcp_pos + tcp_rot @ runtime.tcp_relative_pos
            world_rot = tcp_rot @ runtime.tcp_relative_rot
            self.model.body_pos[runtime.body_id] = world_pos
            self.model.body_quat[runtime.body_id] = self._rotation_to_quat(world_rot)
            changed = True
        return changed

    def _release_stable_grasp(self, side: str) -> bool:
        runtime = self._held_object(side)
        if runtime is None:
            return False

        world_pos = self.model.body_pos[runtime.body_id].copy()
        world_rot = self.data.xmat[runtime.body_id].reshape(3, 3)
        on_table = (
            abs(world_pos[0] - TABLE_CENTER_X_M)
            <= TABLE_HALF_LENGTH_X_M - runtime.spec.support_height_m
            and abs(world_pos[1] - TABLE_CENTER_Y_M)
            <= TABLE_HALF_WIDTH_Y_M - runtime.spec.support_height_m
        )
        support_z = TABLE_TOP_Z_M if on_table else 0.0
        world_pos[2] = support_z + runtime.spec.support_height_m

        # 稳定模式释放后只保留平面朝向，避免物体倾斜后穿进桌面或地面。
        yaw = float(np.arctan2(world_rot[1, 0], world_rot[0, 0]))
        yaw_quat = np.array([np.cos(yaw * 0.5), 0.0, 0.0, np.sin(yaw * 0.5)], dtype=float)
        self.model.body_pos[runtime.body_id] = world_pos
        self.model.body_quat[runtime.body_id] = yaw_quat
        runtime.held_by = None
        runtime.tcp_relative_pos = None
        runtime.tcp_relative_rot = None
        surface = "table" if on_table else "floor"
        print(f"[HEI VR Sim] {side} released {runtime.spec.body_name} on {surface}", flush=True)
        return True

    def _step_stable_grasp(self) -> None:
        if not self.graspable_objects:
            return

        # 先让已经抓住的物体跟到当前 TCP，再判断松爪，避免释放位置落后一帧。
        if self._update_held_objects():
            mujoco.mj_forward(self.model, self.data)

        changed = False
        for side in ("right", "left"):
            closed = self.gripper_target[side] <= GRIPPER_CLOSED_THRESHOLD_M
            if not closed:
                changed = self._release_stable_grasp(side) or changed
            elif not self.previous_gripper_closed[side]:
                changed = self._try_stable_grasp(side) or changed
            self.previous_gripper_closed[side] = closed
        if changed:
            mujoco.mj_forward(self.model, self.data)

    def _set_sim_chassis_command(self, controllers: dict[str, dict], fresh: bool) -> None:
        right = controllers["right"]
        right_grip = fresh and bool(right["gripActive"])
        if not right_grip:
            # 与真机安全逻辑一致：松开握把或 VR 断流后立即停止，不保留平滑拖尾。
            self.sim_chassis_velocity[:] = 0.0
            return

        target_x = self._deadzone(right["thumbstick"]["y"], CHASSIS_DEADZONE)
        target_y = self._deadzone(right["thumbstick"]["x"], CHASSIS_DEADZONE)
        target_yaw = 0.0
        if right["bButton"]:
            target_yaw = -CHASSIS_MAX_YAW_RAD_S
        elif controllers["left"]["yButton"]:
            target_yaw = CHASSIS_MAX_YAW_RAD_S

        targets = np.array(
            [
                target_x * CHASSIS_MAX_LINEAR_M_S,
                target_y * CHASSIS_MAX_LINEAR_M_S,
                target_yaw,
            ],
            dtype=float,
        )
        for index, target in enumerate(targets):
            self.sim_chassis_velocity[index] = self._smooth(
                self.sim_chassis_velocity[index], float(target)
            )

    def _step_sim_chassis(self, controllers: dict[str, dict], fresh: bool, dt: float) -> None:
        self._set_sim_chassis_command(controllers, fresh)
        command_x, command_y, command_yaw_rate = self.sim_chassis_velocity
        # 真机安装方向中 X/Y 都需要反向，旋转方向不反。MuJoCo 位姿也必须应用相同
        # 方向参数，否则轮速动画正确，但整机前后和左右移动会与真机相反。
        vx = command_x * CHASSIS_X_SIGN
        vy = command_y * CHASSIS_Y_SIGN
        yaw_rate = command_yaw_rate * CHASSIS_THETA_SIGN
        yaw = float(self.base_pose[2])

        # VR 指令定义在机器人本体坐标系，先旋转到世界坐标后再积分底盘位姿。
        cos_yaw = np.cos(yaw)
        sin_yaw = np.sin(yaw)
        self.base_pose[0] += (cos_yaw * vx - sin_yaw * vy) * dt
        self.base_pose[1] += (sin_yaw * vx + cos_yaw * vy) * dt
        self.base_pose[2] = float(np.arctan2(np.sin(yaw + yaw_rate * dt), np.cos(yaw + yaw_rate * dt)))

        self.model.body_pos[self.base_body_id] = self.base_initial_pos + np.array(
            [self.base_pose[0], self.base_pose[1], 0.0], dtype=float
        )
        half_yaw = 0.5 * self.base_pose[2]
        yaw_quat = np.array([np.cos(half_yaw), 0.0, 0.0, np.sin(half_yaw)], dtype=float)
        self.model.body_quat[self.base_body_id] = self._quat_multiply(yaw_quat, self.base_initial_quat)

        # 完全复用真机 _ChassisRuntime 的方向、缩放和限速，再重排到 URDF 轮子顺序。
        scaled_command = np.array(
            [
                command_x * CHASSIS_X_SIGN * CHASSIS_LINEAR_SPEED_SCALE,
                command_y * CHASSIS_Y_SIGN * CHASSIS_LINEAR_SPEED_SCALE,
                (command_yaw_rate / CHASSIS_MAX_YAW_RAD_S)
                * CHASSIS_THETA_SIGN
                * CHASSIS_YAW_SPEED_SCALE,
            ],
            dtype=float,
        )
        motor_speeds = O_TYPE_KINEMATICS @ scaled_command
        max_abs_speed = float(np.max(np.abs(motor_speeds)))
        if max_abs_speed > CHASSIS_MAX_WHEEL_SPEED_RAD_S:
            motor_speeds *= CHASSIS_MAX_WHEEL_SPEED_RAD_S / max_abs_speed
        motor_speeds *= CHASSIS_WHEEL_SIGN
        wheel_speeds = motor_speeds[MODEL_WHEEL_FROM_MOTOR_ORDER]
        for joint, speed in zip(WHEEL_JOINTS, wheel_speeds, strict=True):
            address = self.mj_qpos[joint]
            angle = float(self.data.qpos[address] + speed * dt)
            self.data.qpos[address] = np.arctan2(np.sin(angle), np.cos(angle))

    def _snapshot_vr(self) -> tuple[dict[str, dict], bool, int]:
        with self.vr_lock:
            controllers = {
                side: {
                    **self.vr_data[side],
                    "position": self.vr_data[side]["position"].copy(),
                    "quaternion": self.vr_data[side]["quaternion"].copy(),
                    "thumbstick": self.vr_data[side]["thumbstick"].copy(),
                }
                for side in ("left", "right")
            }
            fresh = (
                self.last_vr_packet_s > 0.0
                and time.monotonic() - self.last_vr_packet_s <= max(0.1, self.args.vr_timeout_s)
            )
            packet_count = self.received_packet_count
        if not fresh:
            for controller in controllers.values():
                controller["gripActive"] = False
        return controllers, fresh, packet_count

    def _handle_buttons(self, controllers: dict[str, dict]) -> None:
        right_a = bool(controllers["right"]["aButton"])
        left_x = bool(controllers["left"]["xButton"])
        if not controllers["right"]["gripActive"] and right_a and not self.previous_buttons["right_a"]:
            self.arms["right"].reset_requested = True
            self._release_controller_origin(self.arms["right"])
        if not controllers["left"]["gripActive"] and left_x and not self.previous_buttons["left_x"]:
            self.arms["left"].reset_requested = True
            self._release_controller_origin(self.arms["left"])
        self.previous_buttons["right_a"] = right_a
        self.previous_buttons["left_x"] = left_x

    def _step_control(self, dt: float) -> tuple[bool, int]:
        controllers, fresh, packet_count = self._snapshot_vr()
        with self.data_lock:
            self._handle_buttons(controllers)
            self._step_sim_chassis(controllers, fresh, dt)
            for side in ("right", "left"):
                arm = self.arms[side]
                controller = controllers[side]
                if controller["gripActive"]:
                    self._update_arm_target(arm, controller)
                    # 默认闭合，trigger 按下张开；松开 grip 后保留最后夹爪状态。
                    target = GRIPPER_OPEN_M if controller["trigger"] else GRIPPER_CLOSED_M
                    self._set_gripper(side, target)
                    self._solve_arm(arm)
                else:
                    self._release_controller_origin(arm)
                    self._step_reset(arm)

            left = controllers["left"]
            lift_axis = self._deadzone(left["thumbstick"]["y"], LIFT_DEADZONE)
            if not left["gripActive"]:
                lift_axis = 0.0
            lift_id = self._mujoco_joint_id(LIFT_JOINT)
            low, high = self.model.jnt_range[lift_id]
            current_lift = float(self.data.qpos[self.mj_qpos[LIFT_JOINT]])
            # WebXR 摇杆向上通常为负；与现有 height_axis 链路一致，负值使升降上升到 0。
            self.data.qpos[self.mj_qpos[LIFT_JOINT]] = np.clip(
                current_lift - lift_axis * self.args.lift_speed_m_s * dt,
                low,
                high,
            )
            self.data.qvel[:] = 0.0
            mujoco.mj_forward(self.model, self.data)
            self._step_stable_grasp()
        return fresh, packet_count

    def _print_status(self, fresh: bool, packet_count: int) -> None:
        now = time.monotonic()
        if now - self.last_status_s < STATUS_INTERVAL_S:
            return
        self.last_status_s = now
        with self.data_lock:
            lift = float(self.data.qpos[self.mj_qpos[LIFT_JOINT]])
            base_pose = self.base_pose.copy()
            chassis_command = self.sim_chassis_velocity.copy()
            chassis_velocity = chassis_command * np.array(
                [CHASSIS_X_SIGN, CHASSIS_Y_SIGN, CHASSIS_THETA_SIGN], dtype=float
            )
            wheel_q = self._get_joint_q(WHEEL_JOINTS)
            right_q = self._get_joint_q(RIGHT_ARM_JOINTS)
            left_q = self._get_joint_q(LEFT_ARM_JOINTS)
            held = ",".join(
                f"{runtime.held_by}:{runtime.spec.body_name.removeprefix('hei_object_')}"
                for runtime in self.graspable_objects.values()
                if runtime.held_by is not None
            ) or "none"
        print(
            f"[HEI VR Sim] VR={'online' if fresh else 'waiting'} packets={packet_count} "
            f"base=({base_pose[0]:+.2f}m, {base_pose[1]:+.2f}m, "
            f"{np.degrees(base_pose[2]):+.1f}deg) "
            f"vel=({chassis_velocity[0]:+.2f}, {chassis_velocity[1]:+.2f}, "
            f"{np.degrees(chassis_velocity[2]):+.1f}deg/s) wheels={np.round(wheel_q, 2)} "
            f"lift={lift:.3f}m held={held} right={np.round(right_q, 2)} left={np.round(left_q, 2)}",
            flush=True,
        )

    def _keyboard_callback(self, keycode: int) -> None:
        key = chr(keycode).upper() if 0 <= keycode < 256 else ""
        if key == "F" and self.viewer is not None:
            self.show_frames = not self.show_frames
            self.viewer.opt.frame = (
                mujoco.mjtFrame.mjFRAME_BODY if self.show_frames else mujoco.mjtFrame.mjFRAME_NONE
            )
            print(f"[HEI VR Sim] body frames {'shown' if self.show_frames else 'hidden'}", flush=True)
        elif key == "R":
            self._reset_full_pose()
            for arm in self.arms.values():
                arm.target_tf = arm.solver.fk(DEFAULT_ARM_Q)
                arm.last_solved_target_tf = None
                arm.settle_steps_remaining = 0
                arm.reset_requested = False
                self._release_controller_origin(arm)
            print("[HEI VR Sim] full pose reset", flush=True)

    def run(self) -> None:
        print("[HEI VR Sim] pure simulation mode; no command will be sent to the robot", flush=True)
        print(
            "[HEI VR Sim] right grip + stick moves chassis; right B / left Y rotates; "
            "hold grip to move an arm; trigger opens, release trigger closes/grabs; F frames; R reset",
            flush=True,
        )
        self.viewer = mujoco.viewer.launch_passive(
            self.model,
            self.data,
            key_callback=self._keyboard_callback,
        )
        self.viewer.cam.lookat[:] = (0.0, 0.0, 0.75)
        self.viewer.cam.distance = 2.8
        self.viewer.cam.azimuth = 135
        self.viewer.cam.elevation = -20
        previous_s = time.monotonic()
        try:
            while self.viewer.is_running() and not self.stop_event.is_set():
                now_s = time.monotonic()
                dt = min(max(now_s - previous_s, 0.0), 0.05)
                previous_s = now_s
                fresh, packet_count = self._step_control(dt)
                self.viewer.sync()
                self._print_status(fresh, packet_count)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def headless_check(self) -> None:
        # 用零位 FK 及同目标 IK 验证两套 reduced model 可正常求解。
        for side, arm in self.arms.items():
            current_q = self._get_joint_q(ARM_JOINTS[side])
            target = arm.solver.fk(current_q)
            solution, info = arm.solver.ik(target, current_q)
            if not info["success"] or not np.all(np.isfinite(solution)):
                raise RuntimeError(f"{side} IK self-check failed")
            print(f"[HEI VR Sim] {side} FK/IK self-check passed", flush=True)
        controllers = {"left": empty_controller("left"), "right": empty_controller("right")}
        controllers["right"]["poseValid"] = True
        controllers["right"]["gripActive"] = True
        # WebXR 摇杆向前为负值；经过 X 方向配置后，机器人应沿自身 +X 前进。
        controllers["right"]["thumbstick"]["y"] = -1.0
        initial_x = float(self.base_pose[0])
        self._step_sim_chassis(controllers, True, 0.1)
        if self.base_pose[0] <= initial_x or np.allclose(self._get_joint_q(WHEEL_JOINTS), 0.0):
            raise RuntimeError("Chassis/wheel kinematics self-check failed")
        print("[HEI VR Sim] chassis translation and wheel animation self-check passed", flush=True)
        self._reset_full_pose()
        if self.graspable_objects:
            right_tcp_id = self._mujoco_body_id(TCP_FRAMES["right"])
            runtime = next(iter(self.graspable_objects.values()))
            self.model.body_pos[runtime.body_id] = self.data.xpos[right_tcp_id] + np.array(
                [0.02, 0.0, 0.0], dtype=float
            )
            mujoco.mj_forward(self.model, self.data)
            # 默认闭合夹爪先张开再闭合，验证真正的闭合边沿会触发稳定抓取。
            self._set_gripper("right", GRIPPER_OPEN_M)
            self._step_stable_grasp()
            self._set_gripper("right", GRIPPER_CLOSED_M)
            self._step_stable_grasp()
            if runtime.held_by != "right":
                raise RuntimeError("Stable grasp self-check failed to attach object")

            previous_object_pos = self.model.body_pos[runtime.body_id].copy()
            self.model.body_pos[self.base_body_id, 0] += 0.05
            mujoco.mj_forward(self.model, self.data)
            self._step_stable_grasp()
            if np.allclose(self.model.body_pos[runtime.body_id], previous_object_pos):
                raise RuntimeError("Stable grasp self-check failed to follow TCP")

            self._set_gripper("right", GRIPPER_OPEN_M)
            self._step_stable_grasp()
            if runtime.held_by is not None:
                raise RuntimeError("Stable grasp self-check failed to release object")
            print("[HEI VR Sim] stable grasp/release self-check passed", flush=True)
            self._reset_full_pose()
        self.close()

    def close(self) -> None:
        if self.stop_event.is_set():
            return
        self.stop_event.set()
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None
        if self.listener_thread.is_alive():
            self.listener_thread.join(timeout=1.0)
        print("[HEI VR Sim] stopped", flush=True)


def main() -> None:
    args = parse_args()
    simulator = HEIRobotVRSimulator(args)
    if args.headless_check:
        simulator.headless_check()
    else:
        simulator.run()


if __name__ == "__main__":
    main()
