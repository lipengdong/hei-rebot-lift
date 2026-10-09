#!/usr/bin/env python
"""Keyboard-controlled HEI simulation with physical grasp contacts."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

from hei_robot_keyboard_mujoco_sim import (
    ARM_JOINTS,
    CHASSIS_MAX_LINEAR_M_S,
    CHASSIS_MAX_YAW_RAD_S,
    DEFAULT_ARM_Q,
    DEFAULT_URDF,
    GRIPPER_OPEN_M,
    LIFT_JOINT,
    HEIRobotKeyboardSimulator,
)
from hei_robot_vr_mujoco_physics import HEIRobotVRPhysicsSimulator


class HEIRobotKeyboardPhysicsSimulator(
    HEIRobotKeyboardSimulator,
    HEIRobotVRPhysicsSimulator,
):
    """Keep the keyboard/IK mapping while using actuator and contact physics."""

    def _hold_arm_at_current_pose(self, side: str) -> None:
        super()._hold_arm_at_current_pose(side)
        if not getattr(self, "_physics_ready", False):
            return
        joint_names = ARM_JOINTS[side]
        current_q = self._get_joint_q(joint_names)
        self._set_joint_q(joint_names, current_q)

    def _viewer_key_callback(self, keycode: int) -> None:
        key = chr(keycode).upper() if 0 <= keycode < 256 else ""
        if key == "C":
            HEIRobotVRPhysicsSimulator._keyboard_callback(self, keycode)

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
                mujoco.mjtFrame.mjFRAME_BODY
                if self.show_frames
                else mujoco.mjtFrame.mjFRAME_NONE
            )
            print(
                f"[HEI Keyboard Physics] body frames "
                f"{'shown' if self.show_frames else 'hidden'}",
                flush=True,
            )

        fine_scale = self.args.fine_scale if "shift" in keys else 1.0
        with self.data_lock:
            if "space" in keys:
                self._hold_arms_at_current_pose()
            elif mode_changed:
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

            lift_id = self._mujoco_joint_id(LIFT_JOINT)
            self.data.qvel[int(self.model.jnt_dofadr[lift_id])] = 0.0
            self._sync_robot_controls(include_arms=False)
            mujoco.mj_forward(self.model, self.data)
            self._advance_physics(dt)
            self._update_physical_grasp_events()
        return mode

    def _print_keyboard_status(self, mode: str) -> None:
        previous_status_s = self.last_status_s
        super()._print_keyboard_status(mode)
        if self.last_status_s == previous_status_s:
            return
        with self.data_lock:
            contacts = self._finger_contacts()
            contact_text = ",".join(
                f"{side}:{name.removeprefix('hei_object_')}"
                f"[{'+'.join(sorted(fingers))}]"
                for (side, name), fingers in contacts.items()
            ) or "none"
        print(
            f"[HEI Keyboard Physics] contacts={contact_text} "
            f"confirmed_grasps={len(self._physical_grasps)}",
            flush=True,
        )

    def run(self) -> None:
        print(
            "[HEI Keyboard Physics] physical simulation only; no real command publishing",
            flush=True,
        )
        print(
            "[HEI Keyboard Physics] modes: 1 chassis, 2 lift, 3 left arm, "
            "4 right arm; 5/6 reset arms",
            flush=True,
        )
        print("[HEI Keyboard Physics] chassis: W/S, A/D, Q/E; lift: I/K", flush=True)
        print(
            "[HEI Keyboard Physics] arm: W/S X, A/D Y, R/F Z; "
            "U/J Rx, I/K Ry, O/L Rz",
            flush=True,
        )
        print(
            "[HEI Keyboard Physics] gripper: Z open, X close; Shift fine; "
            "Space stop; C contacts; V frames; Backspace reset; Esc quit",
            flush=True,
        )
        self.viewer = mujoco.viewer.launch_passive(
            self.model,
            self.data,
            key_callback=self._viewer_key_callback,
        )
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
        """Validate held-key mappings using actuator-driven motion."""
        initial_base_x = float(self.base_pose[0])
        with self.key_lock:
            self.control_mode = "chassis"
            self.pressed_keys = {"w"}
        self._step_keyboard_control(0.1)
        if self.base_pose[0] <= initial_base_x:
            raise RuntimeError("Keyboard physics check failed: W must move chassis toward +X")

        self._reset_keyboard_pose()
        initial_lift = float(self.data.qpos[self.mj_qpos[LIFT_JOINT]])
        with self.key_lock:
            self.control_mode = "lift"
            self.pressed_keys = {"k"}
        self._step_keyboard_control(0.1)
        if float(self.data.qpos[self.mj_qpos[LIFT_JOINT]]) >= initial_lift:
            raise RuntimeError("Keyboard physics check failed: K must lower the lift")

        self._reset_keyboard_pose()
        right_arm = self.arms["right"]
        initial_target_x = float(right_arm.target_tf[0, 3])
        with self.key_lock:
            self.control_mode = "right_arm"
            self.pressed_keys = {"w", "z"}
        for _ in range(20):
            self._step_keyboard_control(0.02)
        if float(right_arm.target_tf[0, 3]) <= initial_target_x:
            raise RuntimeError("Keyboard physics check failed: W must increase TCP X")
        if self.gripper_target["right"] != GRIPPER_OPEN_M:
            raise RuntimeError("Keyboard physics check failed: Z must open the gripper")

        distance_before_reset = np.linalg.norm(
            self._get_joint_q(ARM_JOINTS["right"]) - DEFAULT_ARM_Q
        )
        with self.key_lock:
            self.pressed_keys = {"6"}
            self.arm_reset_requests.add("right")
        self._step_keyboard_control(0.02)
        with self.key_lock:
            self.pressed_keys.clear()
        for _ in range(100):
            self._step_keyboard_control(0.02)
        distance_after_reset = np.linalg.norm(
            self._get_joint_q(ARM_JOINTS["right"]) - DEFAULT_ARM_Q
        )
        if distance_after_reset >= distance_before_reset:
            raise RuntimeError("Keyboard physics check failed: 6 must reset the right arm")
        print("[HEI Keyboard Physics] actuator keyboard mapping check passed", flush=True)

        with self.key_lock:
            self.pressed_keys.clear()
            self.control_mode = "chassis"
        self._reset_keyboard_pose()
        HEIRobotVRPhysicsSimulator.headless_check(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Control HEI physical grasp simulation with a keyboard."
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_URDF)
    parser.add_argument("--arm-linear-speed-m-s", type=float, default=0.12)
    parser.add_argument("--arm-angular-speed-deg-s", type=float, default=35.0)
    parser.add_argument("--lift-speed-m-s", type=float, default=0.20)
    parser.add_argument(
        "--chassis-linear-speed-m-s",
        type=float,
        default=CHASSIS_MAX_LINEAR_M_S,
    )
    parser.add_argument(
        "--chassis-yaw-speed-deg-s",
        type=float,
        default=float(np.degrees(CHASSIS_MAX_YAW_RAD_S)),
    )
    parser.add_argument("--fine-scale", type=float, default=0.25)
    parser.add_argument("--physics-timestep-s", type=float, default=0.002)
    parser.add_argument("--object-friction", type=float, default=1.0)
    parser.add_argument("--gripper-force-n", type=float, default=18.0)
    parser.add_argument(
        "--grasp-assist",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable contact-triggered force-limited adsorption; use --no-grasp-assist for pure contacts.",
    )
    parser.add_argument("--robot-gravity-scale", type=float, default=0.0)
    parser.add_argument("--headless-check", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    positive_values = {
        "--arm-linear-speed-m-s": args.arm_linear_speed_m_s,
        "--arm-angular-speed-deg-s": args.arm_angular_speed_deg_s,
        "--lift-speed-m-s": args.lift_speed_m_s,
        "--chassis-linear-speed-m-s": args.chassis_linear_speed_m_s,
        "--chassis-yaw-speed-deg-s": args.chassis_yaw_speed_deg_s,
        "--physics-timestep-s": args.physics_timestep_s,
        "--object-friction": args.object_friction,
        "--gripper-force-n": args.gripper_force_n,
    }
    for option, value in positive_values.items():
        if value <= 0.0:
            parser.error(f"{option} must be positive")
    if not 0.0 < args.fine_scale <= 1.0:
        parser.error("--fine-scale must be in (0, 1]")
    if not 0.0 <= args.robot_gravity_scale <= 1.0:
        parser.error("--robot-gravity-scale must be between 0 and 1")

    args.plain_scene = False
    args.vr_endpoint = ""
    args.vr_pos_scale = 1.0
    args.vr_timeout_s = 1.0
    return args


def main() -> None:
    simulator = HEIRobotKeyboardPhysicsSimulator(parse_args())
    if simulator.args.headless_check:
        simulator.headless_check()
    else:
        simulator.run()


if __name__ == "__main__":
    main()
