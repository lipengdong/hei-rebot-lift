#!/usr/bin/env python
"""Keyboard control for the complete HEI ReBot Lift MuJoCo simulation.

This entry point is simulation-only. It reuses the complete-model IK, chassis,
lift, gripper, and stable-grasp implementation from the VR simulator, but never
opens a VR receiver or a real-robot command publisher.
"""

from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np
import pinocchio as pin

from hei_robot_vr_mujoco_sim import (
    ARM_JOINTS,
    CHASSIS_MAX_LINEAR_M_S,
    CHASSIS_MAX_YAW_RAD_S,
    DEFAULT_ARM_Q,
    DEFAULT_URDF,
    GRIPPER_CLOSED_M,
    GRIPPER_OPEN_M,
    IK_SETTLE_MAX_STEPS,
    LIFT_JOINT,
    STATUS_INTERVAL_S,
    TCP_FRAMES,
    WHEEL_JOINTS,
    HEIRobotVRSimulator,
)


CONTROL_MODES = {
    "1": "chassis",
    "2": "lift",
    "3": "left_arm",
    "4": "right_arm",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Control the complete HEI robot MuJoCo simulation with a keyboard."
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_URDF, help="Complete HEI robot URDF path.")
    parser.add_argument(
        "--arm-linear-speed-m-s",
        type=float,
        default=0.12,
        help="TCP translation speed while a position key is held.",
    )
    parser.add_argument(
        "--arm-angular-speed-deg-s",
        type=float,
        default=35.0,
        help="TCP rotation speed while an orientation key is held.",
    )
    parser.add_argument("--lift-speed-m-s", type=float, default=0.20, help="Simulated lift speed.")
    parser.add_argument(
        "--chassis-linear-speed-m-s",
        type=float,
        default=CHASSIS_MAX_LINEAR_M_S,
        help=f"Chassis translation speed, capped at {CHASSIS_MAX_LINEAR_M_S:.2f} m/s.",
    )
    parser.add_argument(
        "--chassis-yaw-speed-deg-s",
        type=float,
        default=float(np.degrees(CHASSIS_MAX_YAW_RAD_S)),
        help=f"Chassis yaw speed, capped at {np.degrees(CHASSIS_MAX_YAW_RAD_S):.1f} deg/s.",
    )
    parser.add_argument(
        "--fine-scale",
        type=float,
        default=0.25,
        help="Speed multiplier while Shift is held.",
    )
    parser.add_argument("--plain-scene", action="store_true", help="Disable the environment and show only the robot.")
    parser.add_argument("--headless-check", action="store_true", help="Build and validate without opening a viewer.")
    parser.add_argument("--verbose", action="store_true", help="Print additional IK diagnostics.")

    args = parser.parse_args()
    if args.arm_linear_speed_m_s <= 0.0:
        parser.error("--arm-linear-speed-m-s must be positive")
    if args.arm_angular_speed_deg_s <= 0.0:
        parser.error("--arm-angular-speed-deg-s must be positive")
    if args.lift_speed_m_s <= 0.0:
        parser.error("--lift-speed-m-s must be positive")
    if args.chassis_linear_speed_m_s <= 0.0:
        parser.error("--chassis-linear-speed-m-s must be positive")
    if args.chassis_yaw_speed_deg_s <= 0.0:
        parser.error("--chassis-yaw-speed-deg-s must be positive")
    if not 0.0 < args.fine_scale <= 1.0:
        parser.error("--fine-scale must be in (0, 1]")

    # HEIRobotVRSimulator expects these attributes. The keyboard subclass does
    # not open the VR receiver, so the endpoint and timeout are placeholders.
    args.vr_endpoint = ""
    args.vr_pos_scale = 1.0
    args.vr_timeout_s = 1.0
    return args


class HEIRobotKeyboardSimulator(HEIRobotVRSimulator):
    """Complete-model simulator driven by held keyboard keys."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.key_lock = threading.Lock()
        self.pressed_keys: set[str] = set()
        self.control_mode = "chassis"
        self.mode_changed = False
        self.reset_requested = False
        self.arm_reset_requests: set[str] = set()
        self.toggle_frames_requested = False
        self.exit_requested = False
        self.keyboard_listener = None
        super().__init__(args)
        self._hold_arms_at_current_pose()

    def _vr_listener(self) -> None:
        """Disable the VR socket for this simulation-only keyboard entry point."""

    @staticmethod
    def _axis(keys: set[str], positive: str, negative: str) -> float:
        return float((positive in keys) - (negative in keys))

    def _hold_arm_at_current_pose(self, side: str) -> None:
        arm = self.arms[side]
        current_q = self._get_joint_q(ARM_JOINTS[side])
        current_tf = arm.solver.fk(current_q)
        arm.target_tf = current_tf.copy()
        arm.last_solved_target_tf = current_tf.copy()
        arm.last_accepted_ik_q = current_q.copy()
        arm.last_accepted_target_tf = current_tf.copy()
        arm.filtered_target_tf = current_tf.copy()
        arm.joint_target_q = current_q.copy()
        arm.settle_steps_remaining = 0
        arm.reset_requested = False
        arm.solver.init_data = current_q.copy()

    def _hold_arms_at_current_pose(self) -> None:
        """Make the measured arm poses the new IK targets without moving them."""
        for side in self.arms:
            self._hold_arm_at_current_pose(side)

    def _reset_keyboard_pose(self) -> None:
        self._reset_full_pose()
        with self.data_lock:
            self._hold_arms_at_current_pose()
        print("[HEI Keyboard Sim] full pose reset", flush=True)

    def _start_keyboard_listener(self) -> None:
        try:
            from pynput import keyboard
        except ImportError as exc:
            raise RuntimeError("Keyboard control requires pynput: pip install pynput") from exc

        def key_name(key) -> str | None:
            char = getattr(key, "char", None)
            if char:
                return char.lower()
            if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
                return "shift"
            if key == keyboard.Key.space:
                return "space"
            if key == keyboard.Key.backspace:
                return "backspace"
            if key == keyboard.Key.esc:
                return "esc"
            return None

        def on_press(key):
            name = key_name(key)
            if name is None:
                return None
            with self.key_lock:
                first_press = name not in self.pressed_keys
                self.pressed_keys.add(name)
                if not first_press:
                    return None
                if name in CONTROL_MODES:
                    self.control_mode = CONTROL_MODES[name]
                    # 切换模式时清除旧运动键，防止按键跨模式造成意外运动。
                    self.pressed_keys = {name}
                    self.mode_changed = True
                    print(f"[HEI Keyboard Sim] mode -> {self.control_mode}", flush=True)
                elif name in ("5", "6"):
                    side = "left" if name == "5" else "right"
                    self.pressed_keys = {name}
                    self.arm_reset_requests.add(side)
                    print(f"[HEI Keyboard Sim] {side} arm reset requested", flush=True)
                elif name == "backspace":
                    self.pressed_keys = {name}
                    self.control_mode = "chassis"
                    self.mode_changed = True
                    self.reset_requested = True
                elif name == "v":
                    self.toggle_frames_requested = True
                elif name == "esc":
                    self.exit_requested = True
                    return False
            return None

        def on_release(key):
            name = key_name(key)
            if name is not None:
                with self.key_lock:
                    self.pressed_keys.discard(name)
            return None

        self.keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.keyboard_listener.start()

    def _snapshot_keyboard(self) -> tuple[set[str], str, bool, bool, set[str], bool]:
        with self.key_lock:
            keys = self.pressed_keys.copy()
            mode = self.control_mode
            mode_changed = self.mode_changed
            reset_requested = self.reset_requested
            arm_reset_requests = self.arm_reset_requests.copy()
            toggle_frames = self.toggle_frames_requested
            self.mode_changed = False
            self.reset_requested = False
            self.arm_reset_requests.clear()
            self.toggle_frames_requested = False
        return keys, mode, mode_changed, reset_requested, arm_reset_requests, toggle_frames

    def _step_keyboard_chassis(self, keys: set[str], mode: str, dt: float, fine_scale: float) -> None:
        if mode != "chassis" or "space" in keys:
            self.sim_chassis_velocity[:] = 0.0
            self._integrate_sim_chassis(dt)
            return

        forward = self._axis(keys, "w", "s")
        lateral = self._axis(keys, "a", "d")
        yaw = self._axis(keys, "q", "e")
        if forward == lateral == yaw == 0.0:
            self.sim_chassis_velocity[:] = 0.0
            self._integrate_sim_chassis(dt)
            return

        linear_speed = min(self.args.chassis_linear_speed_m_s, CHASSIS_MAX_LINEAR_M_S)
        yaw_speed = min(
            np.deg2rad(self.args.chassis_yaw_speed_deg_s),
            CHASSIS_MAX_YAW_RAD_S,
        )
        # 复用 VR/真机底盘方向配置：链路内部会再次应用 X/Y 安装方向符号，
        # 因此这里用负值表示机器人自身坐标系的 +X 前进和 +Y 左移。
        self.sim_chassis_velocity[:] = (
            -forward * linear_speed * fine_scale,
            -lateral * linear_speed * fine_scale,
            yaw * yaw_speed * fine_scale,
        )
        self._integrate_sim_chassis(dt)

    def _step_keyboard_arm(self, keys: set[str], mode: str, dt: float, fine_scale: float) -> None:
        if mode not in ("left_arm", "right_arm") or "space" in keys:
            return
        side = "left" if mode == "left_arm" else "right"
        arm = self.arms[side]

        linear_axis = np.array(
            [
                self._axis(keys, "w", "s"),
                self._axis(keys, "a", "d"),
                self._axis(keys, "r", "f"),
            ],
            dtype=float,
        )
        angular_axis = np.array(
            [
                self._axis(keys, "u", "j"),
                self._axis(keys, "i", "k"),
                self._axis(keys, "o", "l"),
            ],
            dtype=float,
        )
        if not np.any(linear_axis) and not np.any(angular_axis):
            return

        # 操作者重新给出末端运动时，立即取消这条臂尚未完成的自动复位。
        if arm.reset_requested:
            self._hold_arm_at_current_pose(side)

        # 对角组合按键归一化，保证单轴和多轴运动的总速度一致。
        linear_norm = np.linalg.norm(linear_axis)
        if linear_norm > 1.0:
            linear_axis /= linear_norm
        angular_norm = np.linalg.norm(angular_axis)
        if angular_norm > 1.0:
            angular_axis /= angular_norm

        target = arm.target_tf.copy()
        target[:3, 3] += linear_axis * self.args.arm_linear_speed_m_s * fine_scale * dt
        rotation_step = (
            angular_axis
            * np.deg2rad(self.args.arm_angular_speed_deg_s)
            * fine_scale
            * dt
        )
        # 左乘增量旋转：Rx/Ry/Rz 始终对应机器人固定坐标轴。
        target[:3, :3] = pin.exp3(rotation_step) @ target[:3, :3]
        arm.target_tf = target
        arm.last_solved_target_tf = target.copy()
        arm.settle_steps_remaining = IK_SETTLE_MAX_STEPS

    def _step_keyboard_lift(self, keys: set[str], mode: str, dt: float, fine_scale: float) -> None:
        if mode != "lift" or "space" in keys:
            return
        direction = self._axis(keys, "i", "k")
        if direction == 0.0:
            return
        lift_id = self._mujoco_joint_id(LIFT_JOINT)
        low, high = self.model.jnt_range[lift_id]
        address = self.mj_qpos[LIFT_JOINT]
        self.data.qpos[address] = np.clip(
            float(self.data.qpos[address])
            + direction * self.args.lift_speed_m_s * fine_scale * dt,
            low,
            high,
        )

    def _step_keyboard_gripper(self, keys: set[str], mode: str) -> None:
        if mode not in ("left_arm", "right_arm") or "space" in keys:
            return
        side = "left" if mode == "left_arm" else "right"
        if "z" in keys:
            self._set_gripper(side, GRIPPER_OPEN_M)
        elif "x" in keys:
            self._set_gripper(side, GRIPPER_CLOSED_M)

    def _step_keyboard_control(self, dt: float) -> str:
        (
            keys,
            mode,
            mode_changed,
            reset_requested,
            arm_reset_requests,
            toggle_frames,
        ) = self._snapshot_keyboard()
        if reset_requested:
            self._reset_keyboard_pose()
        if toggle_frames and self.viewer is not None:
            self.show_frames = not self.show_frames
            self.viewer.opt.frame = (
                mujoco.mjtFrame.mjFRAME_BODY if self.show_frames else mujoco.mjtFrame.mjFRAME_NONE
            )
            print(f"[HEI Keyboard Sim] body frames {'shown' if self.show_frames else 'hidden'}", flush=True)

        fine_scale = self.args.fine_scale if "shift" in keys else 1.0
        with self.data_lock:
            if "space" in keys:
                self._hold_arms_at_current_pose()
            elif mode_changed:
                # 切换底盘/升降/手臂模式时保持普通手臂目标，但不打断另一条臂
                # 已经开始的渐进复位。
                for side, arm in self.arms.items():
                    if not arm.reset_requested:
                        self._hold_arm_at_current_pose(side)
            for side in arm_reset_requests:
                arm = self.arms[side]
                self._release_controller_origin(arm)
                arm.reset_requested = True
            self._step_keyboard_chassis(keys, mode, dt, fine_scale)
            self._step_keyboard_lift(keys, mode, dt, fine_scale)
            self._step_keyboard_arm(keys, mode, dt, fine_scale)
            self._step_keyboard_gripper(keys, mode)
            for arm in self.arms.values():
                if arm.reset_requested:
                    self._step_reset(arm)
                else:
                    self._solve_arm(arm, dt)
            self.data.qvel[:] = 0.0
            mujoco.mj_forward(self.model, self.data)
            self._step_stable_grasp()
        return mode

    def _print_keyboard_status(self, mode: str) -> None:
        now = time.monotonic()
        if now - self.last_status_s < STATUS_INTERVAL_S:
            return
        self.last_status_s = now
        with self.data_lock:
            lift = float(self.data.qpos[self.mj_qpos[LIFT_JOINT]])
            base_pose = self.base_pose.copy()
            side = "left" if mode == "left_arm" else "right"
            tcp_id = self._mujoco_body_id(TCP_FRAMES[side])
            tcp = self.data.xpos[tcp_id].copy()
            grippers = self.gripper_target.copy()
            wheel_q = self._get_joint_q(WHEEL_JOINTS)
        print(
            f"[HEI Keyboard Sim] mode={mode} "
            f"base=({base_pose[0]:+.2f}, {base_pose[1]:+.2f}, {np.degrees(base_pose[2]):+.1f}deg) "
            f"lift={lift:+.3f}m {side}_tcp={np.round(tcp, 3)} "
            f"gripper(L/R)=({grippers['left']:.3f}/{grippers['right']:.3f})m "
            f"wheels={np.round(wheel_q, 2)}",
            flush=True,
        )

    def run(self) -> None:
        print("[HEI Keyboard Sim] simulation only; no command will be sent to the robot", flush=True)
        print(
            "[HEI Keyboard Sim] modes: 1 chassis, 2 lift, 3 left arm, 4 right arm; "
            "5 reset left arm, 6 reset right arm",
            flush=True,
        )
        print("[HEI Keyboard Sim] chassis: W/S forward/back, A/D strafe, Q/E rotate", flush=True)
        print("[HEI Keyboard Sim] lift: I/K up/down", flush=True)
        print("[HEI Keyboard Sim] arm: W/S X, A/D Y, R/F Z; U/J Rx, I/K Ry, O/L Rz", flush=True)
        print(
            "[HEI Keyboard Sim] gripper: Z open, X close; Shift fine; "
            "Space stop; V frames; Backspace reset; Esc quit",
            flush=True,
        )
        self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
        try:
            self._start_keyboard_listener()
            self.viewer.cam.lookat[:] = (0.0, 0.0, 0.75)
            self.viewer.cam.distance = 2.8
            self.viewer.cam.azimuth = 135
            self.viewer.cam.elevation = -20
            previous_s = time.monotonic()
            while self.viewer.is_running() and not self.exit_requested:
                now_s = time.monotonic()
                dt = min(max(now_s - previous_s, 0.0), 0.05)
                previous_s = now_s
                mode = self._step_keyboard_control(dt)
                self.viewer.sync()
                self._print_keyboard_status(mode)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def headless_check(self) -> None:
        """Validate keyboard mappings before running the shared model checks."""
        initial_base_x = float(self.base_pose[0])
        with self.key_lock:
            self.control_mode = "chassis"
            self.pressed_keys = {"w"}
        self._step_keyboard_control(0.1)
        if self.base_pose[0] <= initial_base_x:
            raise RuntimeError("Keyboard chassis mapping self-check failed: W must move toward +X")

        self._reset_keyboard_pose()
        initial_lift = float(self.data.qpos[self.mj_qpos[LIFT_JOINT]])
        with self.key_lock:
            self.control_mode = "lift"
            self.pressed_keys = {"k"}
        self._step_keyboard_control(0.1)
        if float(self.data.qpos[self.mj_qpos[LIFT_JOINT]]) >= initial_lift:
            raise RuntimeError("Keyboard lift mapping self-check failed: K must lower the lift")

        self._reset_keyboard_pose()
        right_arm = self.arms["right"]
        initial_target_x = float(right_arm.target_tf[0, 3])
        with self.key_lock:
            self.control_mode = "right_arm"
            self.pressed_keys = {"w", "z"}
        self._step_keyboard_control(0.02)
        if float(right_arm.target_tf[0, 3]) <= initial_target_x:
            raise RuntimeError("Keyboard arm mapping self-check failed: W must increase TCP X")
        if self.gripper_target["right"] != GRIPPER_OPEN_M:
            raise RuntimeError("Keyboard gripper mapping self-check failed: Z must open the gripper")

        distance_before_reset = np.linalg.norm(
            self._get_joint_q(ARM_JOINTS["right"]) - DEFAULT_ARM_Q
        )
        with self.key_lock:
            self.pressed_keys = {"6"}
            self.arm_reset_requests.add("right")
        self._step_keyboard_control(0.02)
        distance_after_reset = np.linalg.norm(
            self._get_joint_q(ARM_JOINTS["right"]) - DEFAULT_ARM_Q
        )
        if distance_after_reset >= distance_before_reset:
            raise RuntimeError("Keyboard arm reset self-check failed: 6 must reset the right arm")
        print("[HEI Keyboard Sim] keyboard mapping self-check passed", flush=True)

        with self.key_lock:
            self.pressed_keys.clear()
            self.control_mode = "chassis"
        self._reset_keyboard_pose()
        super().headless_check()

    def close(self) -> None:
        if self.keyboard_listener is not None:
            self.keyboard_listener.stop()
            self.keyboard_listener.join(timeout=1.0)
            self.keyboard_listener = None
        super().close()


def main() -> None:
    args = parse_args()
    simulator = HEIRobotKeyboardSimulator(args)
    if args.headless_check:
        simulator.headless_check()
    else:
        simulator.run()


if __name__ == "__main__":
    main()
