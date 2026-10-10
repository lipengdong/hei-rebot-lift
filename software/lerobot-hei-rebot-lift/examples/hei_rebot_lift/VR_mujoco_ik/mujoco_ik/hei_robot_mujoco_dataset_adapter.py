#!/usr/bin/env python
"""Bridge the HEI MuJoCo simulator and the real-robot LeRobot schema."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import mujoco
import numpy as np

from hei_robot_mujoco_scene import build_mujoco_model

from hei_robot_mujoco_zmq_protocol import (
    CAMERA_HEIGHT,
    CAMERA_NAMES,
    CAMERA_WIDTH,
    ROBOT_TYPE,
    observation_feature_types,
    state_feature_types,
)
from hei_robot_vr_mujoco_sim import (
    ARM_JOINTS,
    CHASSIS_MAX_LINEAR_M_S,
    CHASSIS_MAX_YAW_RAD_S,
    GRIPPER_CLOSED_M,
    GRIPPER_JOINTS,
    GRIPPER_OPEN_M,
    LIFT_JOINT,
    MAX_MUJOCO_JOINT_STEP_RAD,
)


DATASET_ARM_JOINTS = (
    "joint_1",
    "joint_2",
    "joint_3",
    "joint_4",
    "joint_5",
    "joint_6",
    "gripper",
)
REAL_GRIPPER_CLOSED_RAD = 0.0
REAL_GRIPPER_OPEN_RAD = -4.5
HEIGHT_MIN_MM = -700.0
HEIGHT_MAX_MM = 0.0
HEIGHT_TARGET_STEP_MM = 80.0
ARM_MAX_SPEED_RAD_S = np.array([8.0, 8.0, 8.0, 1.8, 2.5, 2.5], dtype=float)


@dataclass(frozen=True)
class SimulationSnapshot:
    """Small immutable copy of one simulation instant for asynchronous rendering."""

    state: dict[str, float]
    qpos: np.ndarray
    body_pos: np.ndarray
    body_quat: np.ndarray


class HEIMujocoSnapshotRenderer:
    """Render snapshots with a private model/data pair owned by one worker thread."""

    def __init__(
        self,
        model_path,
        *,
        add_environment: bool,
        width: int,
        height: int,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self.model = build_mujoco_model(model_path, add_environment=add_environment)
        self.model.vis.global_.offwidth = max(self.model.vis.global_.offwidth, self.width)
        self.model.vis.global_.offheight = max(self.model.vis.global_.offheight, self.height)
        self.data = mujoco.MjData(self.model)
        self.renderer = mujoco.Renderer(self.model, height=self.height, width=self.width)
        self._closed = False
        self._validate_cameras()

    def _validate_cameras(self) -> None:
        missing = [
            name
            for name in CAMERA_NAMES
            if mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_CAMERA, name) < 0
        ]
        if missing:
            raise ValueError(f"MuJoCo model is missing named cameras: {missing}")

    def render(self, snapshot: SimulationSnapshot) -> dict[str, float | np.ndarray]:
        if snapshot.qpos.shape != self.data.qpos.shape:
            raise ValueError(
                f"Snapshot qpos shape {snapshot.qpos.shape} does not match renderer {self.data.qpos.shape}"
            )
        if snapshot.body_pos.shape != self.model.body_pos.shape:
            raise ValueError("Snapshot body_pos shape does not match renderer model")
        if snapshot.body_quat.shape != self.model.body_quat.shape:
            raise ValueError("Snapshot body_quat shape does not match renderer model")

        self.data.qpos[:] = snapshot.qpos
        self.data.qvel[:] = 0.0
        self.model.body_pos[:] = snapshot.body_pos
        self.model.body_quat[:] = snapshot.body_quat
        mujoco.mj_forward(self.model, self.data)

        observation: dict[str, float | np.ndarray] = dict(snapshot.state)
        for camera_name in CAMERA_NAMES:
            self.renderer.update_scene(self.data, camera=camera_name)
            observation[camera_name] = self.renderer.render().copy()
        return observation

    def close(self) -> None:
        if self._closed:
            return
        self.renderer.close()
        self._closed = True


def finite_or(value: float, fallback: float) -> float:
    value = float(value)
    return value if np.isfinite(value) else float(fallback)


def simulated_gripper_to_dataset(opening_m: float) -> float:
    """Convert the MuJoCo finger opening in metres to the real motor position."""
    ratio = float(np.clip(opening_m, GRIPPER_CLOSED_M, GRIPPER_OPEN_M)) / GRIPPER_OPEN_M
    return REAL_GRIPPER_CLOSED_RAD + ratio * (REAL_GRIPPER_OPEN_RAD - REAL_GRIPPER_CLOSED_RAD)


def dataset_gripper_to_simulated(position_rad: float) -> float:
    """Convert the real gripper motor position to MuJoCo finger opening."""
    ratio = (float(position_rad) - REAL_GRIPPER_CLOSED_RAD) / (
        REAL_GRIPPER_OPEN_RAD - REAL_GRIPPER_CLOSED_RAD
    )
    return float(np.clip(ratio, 0.0, 1.0) * GRIPPER_OPEN_M)


class HEIMujocoDatasetAdapter:
    """Expose simulation observations/actions using the real robot's 18-D schema."""

    # 与 HeiRebotLiftClient.name 一致，避免 VLA 预处理看到不同的 robot_type。
    robot_type = ROBOT_TYPE

    def __init__(
        self,
        simulator,
        *,
        width: int | None = None,
        height: int | None = None,
        create_renderer: bool = True,
    ) -> None:
        self.simulator = simulator
        self.width = int(width or CAMERA_WIDTH)
        self.height = int(height or CAMERA_HEIGHT)
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Camera width and height must be positive")

        self.renderer = None
        if create_renderer:
            simulator.model.vis.global_.offwidth = max(simulator.model.vis.global_.offwidth, self.width)
            simulator.model.vis.global_.offheight = max(simulator.model.vis.global_.offheight, self.height)
            self.renderer = mujoco.Renderer(simulator.model, height=self.height, width=self.width)
        self._closed = False
        self._validate_cameras()

    @property
    def state_features(self) -> dict[str, type]:
        return state_feature_types()

    @property
    def action_features(self) -> dict[str, type]:
        return self.state_features

    @property
    def observation_features(self) -> dict[str, type | tuple[int, int, int]]:
        return observation_feature_types(width=self.width, height=self.height)

    def _validate_cameras(self) -> None:
        missing = [
            name
            for name in CAMERA_NAMES
            if mujoco.mj_name2id(self.simulator.model, mujoco.mjtObj.mjOBJ_CAMERA, name) < 0
        ]
        if missing:
            raise ValueError(f"MuJoCo model is missing named cameras: {missing}")

    def _read_state_unlocked(self) -> dict[str, float]:
        state: dict[str, float] = {}
        for side in ("right", "left"):
            arm_q = self.simulator._get_joint_q(ARM_JOINTS[side])
            for index, joint in enumerate(DATASET_ARM_JOINTS[:6]):
                state[f"{side}_{joint}.pos"] = float(arm_q[index])
            primary_gripper = GRIPPER_JOINTS[side][0]
            opening_m = float(self.simulator.data.qpos[self.simulator.mj_qpos[primary_gripper]])
            state[f"{side}_gripper.pos"] = simulated_gripper_to_dataset(opening_m)

        # 底盘字段保留真机接口的命令语义；theta.vel 在数据集中是 [-1, 1] 归一化值。
        chassis = self.simulator.sim_chassis_velocity
        state["x.vel"] = float(chassis[0])
        state["y.vel"] = float(chassis[1])
        state["theta.vel"] = float(
            np.clip(chassis[2] / CHASSIS_MAX_YAW_RAD_S, -1.0, 1.0)
        )
        lift_m = float(self.simulator.data.qpos[self.simulator.mj_qpos[LIFT_JOINT]])
        state["height.pos"] = float(np.clip(lift_m * 1000.0, HEIGHT_MIN_MM, HEIGHT_MAX_MM))
        return state

    def read_state(self) -> dict[str, float]:
        with self.simulator.data_lock:
            return self._read_state_unlocked()

    def read_action(self) -> dict[str, float]:
        # 仿真控制器直接写位置目标；当前 qpos 就是发送给真机时对应的关节目标。
        return self.read_state()

    def capture_snapshot(self) -> SimulationSnapshot:
        """Copy state needed by the render worker without holding the control lock."""
        with self.simulator.data_lock:
            return SimulationSnapshot(
                state=self._read_state_unlocked(),
                qpos=self.simulator.data.qpos.copy(),
                body_pos=self.simulator.model.body_pos.copy(),
                body_quat=self.simulator.model.body_quat.copy(),
            )

    def read_observation(self) -> dict[str, float | np.ndarray]:
        if self.renderer is None:
            raise RuntimeError("This adapter was created without an inline renderer")
        with self.simulator.data_lock:
            observation: dict[str, float | np.ndarray] = self._read_state_unlocked()
            for camera_name in CAMERA_NAMES:
                self.renderer.update_scene(self.simulator.data, camera=camera_name)
                observation[camera_name] = self.renderer.render().copy()
        return observation

    def apply_action(self, action: Mapping[str, float], dt: float) -> dict[str, float]:
        """Apply one policy action with joint/lift rate limiting and hard range clipping."""
        dt = float(np.clip(dt, 0.0, 0.1))
        sim = self.simulator
        with sim.data_lock:
            for side in ("right", "left"):
                current = sim._get_joint_q(ARM_JOINTS[side])
                requested = np.array(
                    [
                        float(action.get(f"{side}_{joint}.pos", current[i]))
                        for i, joint in enumerate(DATASET_ARM_JOINTS[:6])
                    ],
                    dtype=float,
                )
                requested = np.where(np.isfinite(requested), requested, current)
                # 策略进程与仿真循环已经解耦，按 dt 限速可避免
                # 仿真帧率变化导致机械臂速度漂移。
                max_step = np.minimum(MAX_MUJOCO_JOINT_STEP_RAD, ARM_MAX_SPEED_RAD_S * dt)
                sim._set_joint_q(
                    ARM_JOINTS[side],
                    current + np.clip(requested - current, -max_step, max_step),
                )
                gripper_key = f"{side}_gripper.pos"
                current_gripper = simulated_gripper_to_dataset(sim.gripper_target[side])
                sim._set_gripper(
                    side,
                    dataset_gripper_to_simulated(
                        finite_or(action.get(gripper_key, current_gripper), current_gripper)
                    ),
                )

            x_command = finite_or(action.get("x.vel", 0.0), 0.0)
            y_command = finite_or(action.get("y.vel", 0.0), 0.0)
            theta_command = finite_or(action.get("theta.vel", 0.0), 0.0)
            sim.sim_chassis_velocity[:] = (
                float(np.clip(x_command, -CHASSIS_MAX_LINEAR_M_S, CHASSIS_MAX_LINEAR_M_S)),
                float(np.clip(y_command, -CHASSIS_MAX_LINEAR_M_S, CHASSIS_MAX_LINEAR_M_S)),
                float(np.clip(theta_command, -1.0, 1.0)) * CHASSIS_MAX_YAW_RAD_S,
            )
            sim._integrate_sim_chassis(dt)

            lift_id = sim._mujoco_joint_id(LIFT_JOINT)
            low, high = sim.model.jnt_range[lift_id]
            current_lift = float(sim.data.qpos[sim.mj_qpos[LIFT_JOINT]])
            requested_height_mm = finite_or(action.get("height.pos", current_lift * 1000.0), current_lift * 1000.0)
            requested_lift = requested_height_mm / 1000.0
            max_lift_step = max(float(getattr(sim.args, "lift_speed_m_s", 0.20)), 0.0) * dt
            requested_lift = current_lift + float(
                np.clip(requested_lift - current_lift, -max_lift_step, max_lift_step)
            )
            sim.data.qpos[sim.mj_qpos[LIFT_JOINT]] = np.clip(requested_lift, low, high)
            sim.data.qvel[:] = 0.0
            mujoco.mj_forward(sim.model, sim.data)
            sim._step_stable_grasp()
            return self._read_state_unlocked()

    def close(self) -> None:
        if self._closed:
            return
        if self.renderer is not None:
            self.renderer.close()
            self.renderer = None
        self._closed = True
