#!/usr/bin/env python
"""VR control for the complete HEI ReBot Lift MuJoCo model and real robot.

The program receives Telegrip data, solves both arm targets against the complete
URDF, updates the MuJoCo viewer, and publishes the existing 6558 bridge protocol
consumed by examples/hei_rebot_lift/teleoperate.py or record.py.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np
import zmq

from hei_robot_vr_mujoco_sim import (
    ARM_JOINTS,
    DEFAULT_URDF,
    DEFAULT_VR_ENDPOINT,
    GRIPPER_CLOSED_M,
    GRIPPER_OPEN_M,
    HEIRobotVRSimulator,
    LIFT_DEADZONE,
    LIFT_JOINT,
)


DEFAULT_COMMAND_ENDPOINT = "tcp://*:6558"
DEFAULT_FEEDBACK_ENDPOINT = "tcp://localhost:6559"
REAL_GRIPPER_OPEN_RAD = -4.5
REAL_GRIPPER_CLOSED_RAD = 0.0
CHASSIS_DEADZONE = 0.15
CHASSIS_MAX_LINEAR_COMMAND = 0.3
CHASSIS_MAX_THETA_COMMAND = 30.0
MOBILE_COMMAND_TIME_CONSTANT_S = 0.08
DEFAULT_PUBLISH_HZ = 30.0
DEFAULT_FEEDBACK_TIMEOUT_S = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Control the complete HEI robot MuJoCo model and publish real-robot actions."
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_URDF, help="Complete HEI robot URDF path.")
    parser.add_argument("--vr-endpoint", default=DEFAULT_VR_ENDPOINT, help="Telegrip ZMQ SUB endpoint.")
    parser.add_argument("--command-endpoint", default=DEFAULT_COMMAND_ENDPOINT, help="ZMQ action PUB bind endpoint.")
    parser.add_argument(
        "--feedback-endpoint",
        default=DEFAULT_FEEDBACK_ENDPOINT,
        help="Robot-state feedback SUB endpoint published by teleoperate.py/record.py.",
    )
    parser.add_argument("--vr-pos-scale", type=float, default=1.0, help="VR translation to robot TCP scale.")
    parser.add_argument("--lift-speed-m-s", type=float, default=0.20, help="Simulated lift display speed.")
    parser.add_argument("--vr-timeout-s", type=float, default=0.5, help="Stop chassis/lift after stale VR data.")
    parser.add_argument(
        "--feedback-timeout-s",
        type=float,
        default=DEFAULT_FEEDBACK_TIMEOUT_S,
        help="Lock real commands when robot-state feedback is stale.",
    )
    parser.add_argument(
        "--publish-hz",
        type=float,
        default=DEFAULT_PUBLISH_HZ,
        help="Action bridge publish rate; 30 Hz matches teleoperate.py and the robot host.",
    )
    parser.add_argument(
        "--enable-real-publish",
        action="store_true",
        help="Required safety acknowledgement before publishing real-robot commands.",
    )
    parser.add_argument(
        "--allow-no-feedback",
        action="store_true",
        help="Unsafe legacy mode: permit arming without first synchronizing the real robot state.",
    )
    parser.add_argument("--plain-scene", action="store_true", help="Disable the environment and show only the robot.")
    parser.add_argument("--headless-check", action="store_true", help="Run model/FK/IK/protocol checks without publishing.")
    parser.add_argument("--verbose", action="store_true", help="Print additional VR and IK diagnostics.")
    return parser.parse_args()


def simulated_gripper_to_real(opening_m: float) -> float:
    opening = float(np.clip(opening_m, GRIPPER_CLOSED_M, GRIPPER_OPEN_M))
    ratio = opening / GRIPPER_OPEN_M
    return REAL_GRIPPER_CLOSED_RAD + ratio * (REAL_GRIPPER_OPEN_RAD - REAL_GRIPPER_CLOSED_RAD)


def real_gripper_to_simulated(position_rad: float) -> float:
    denominator = REAL_GRIPPER_OPEN_RAD - REAL_GRIPPER_CLOSED_RAD
    ratio = (float(position_rad) - REAL_GRIPPER_CLOSED_RAD) / denominator
    return float(np.clip(ratio, 0.0, 1.0) * GRIPPER_OPEN_M)


class HEIRobotVRRealController(HEIRobotVRSimulator):
    def __init__(self, args: argparse.Namespace) -> None:
        if not args.enable_real_publish:
            raise RuntimeError(
                "Real command publishing is locked. Re-run with --enable-real-publish after checking "
                "the robot workspace and emergency stop."
            )
        if args.publish_hz <= 0.0:
            raise ValueError("--publish-hz must be greater than zero for real-robot control")

        self.command_context = zmq.Context()
        self.command_socket = self.command_context.socket(zmq.PUB)
        self.command_socket.setsockopt(zmq.SNDHWM, 2)
        self.command_socket.setsockopt(zmq.LINGER, 0)
        self.command_socket.bind(args.command_endpoint)
        self.command_closed = False

        self.feedback_context = zmq.Context()
        self.feedback_socket = self.feedback_context.socket(zmq.SUB)
        self.feedback_socket.setsockopt(zmq.SUBSCRIBE, b"")
        self.feedback_socket.setsockopt(zmq.RCVHWM, 2)
        self.feedback_socket.setsockopt(zmq.LINGER, 0)
        self.feedback_socket.connect(args.feedback_endpoint)
        self.feedback_closed = False

        self.last_publish_s = 0.0
        self.last_bridge_status_s = 0.0
        self.bridge_armed = False
        self.previous_fresh = False
        self.previous_right_grip = False
        self.previous_left_grip = False
        self.chassis_command = np.zeros(3, dtype=float)
        self.height_axis = 0.0
        self.command_sequence = 0
        self.robot_feedback = None
        self.last_feedback_s = 0.0
        self.feedback_count = 0
        self.last_synced_feedback_sequence = None
        self.real_command_enabled = True

        try:
            super().__init__(args)
        except Exception:
            self._close_command_socket()
            self._close_feedback_socket()
            raise

        print(f"[HEI VR Real] command bridge bound: {args.command_endpoint}", flush=True)
        print(f"[HEI VR Real] robot-state feedback: {args.feedback_endpoint}", flush=True)
        if args.allow_no_feedback:
            print(
                "[HEI VR Real] WARNING: --allow-no-feedback disables startup pose synchronization",
                flush=True,
            )
        print(
            "[HEI VR Real] SAFETY: commands stay locked until robot feedback is synchronized "
            "and a fresh VR frame arrives with both grip buttons released.",
            flush=True,
        )

    @staticmethod
    def _smooth_mobile_command(current: float, target: float, dt: float) -> float:
        alpha = 1.0 - np.exp(-max(float(dt), 0.0) / MOBILE_COMMAND_TIME_CONSTANT_S)
        return float(current + alpha * (target - current))

    def _update_mobile_commands(self, controllers: dict[str, dict], fresh: bool, dt: float) -> None:
        right = controllers["right"]
        left = controllers["left"]
        right_grip = fresh and bool(right["gripActive"])
        left_grip = fresh and bool(left["gripActive"])

        if right_grip:
            target_x = self._deadzone(right["thumbstick"]["y"], CHASSIS_DEADZONE)
            target_y = self._deadzone(right["thumbstick"]["x"], CHASSIS_DEADZONE)
            target_theta = 0.0
            if right["bButton"]:
                target_theta = -CHASSIS_MAX_THETA_COMMAND
            elif left["yButton"]:
                target_theta = CHASSIS_MAX_THETA_COMMAND
            self.chassis_command[0] = self._smooth_mobile_command(
                self.chassis_command[0], target_x * CHASSIS_MAX_LINEAR_COMMAND, dt
            )
            self.chassis_command[1] = self._smooth_mobile_command(
                self.chassis_command[1], target_y * CHASSIS_MAX_LINEAR_COMMAND, dt
            )
            self.chassis_command[2] = self._smooth_mobile_command(
                self.chassis_command[2], target_theta, dt
            )
        else:
            # 握把松开或 VR 断流时必须立即归零，不保留平滑拖尾。
            self.chassis_command[:] = 0.0

        self.height_axis = self._deadzone(left["thumbstick"]["y"], LIFT_DEADZONE) if left_grip else 0.0

    def _real_gripper_position(self, side: str) -> float:
        return simulated_gripper_to_real(self.gripper_target[side])

    @staticmethod
    def _validate_feedback_packet(message: dict) -> dict | None:
        if message.get("type") != "hei_rebot_lift_state":
            return None
        try:
            right = np.asarray(message["right_arm_rad"], dtype=float)
            left = np.asarray(message["left_arm_rad"], dtype=float)
            height_mm = float(message["height_mm"])
            sequence = int(message.get("sequence", -1))
        except (KeyError, TypeError, ValueError):
            return None
        if right.shape != (7,) or left.shape != (7,):
            return None
        if not np.all(np.isfinite(right)) or not np.all(np.isfinite(left)) or not np.isfinite(height_mm):
            return None
        return {
            "right_arm_rad": right,
            "left_arm_rad": left,
            "height_mm": height_mm,
            "sequence": sequence,
        }

    def _poll_robot_feedback(self) -> None:
        latest = None
        while True:
            try:
                message = self.feedback_socket.recv_json(flags=zmq.NOBLOCK)
            except zmq.Again:
                break
            except zmq.ZMQError as exc:
                if not self.feedback_closed:
                    print(f"[HEI VR Real] robot feedback receive failed: {exc}", flush=True)
                break
            validated = self._validate_feedback_packet(message)
            if validated is not None:
                latest = validated
        if latest is None:
            return
        self.robot_feedback = latest
        self.last_feedback_s = time.monotonic()
        self.feedback_count += 1

    def _feedback_is_fresh(self) -> bool:
        if self.args.allow_no_feedback:
            return True
        return (
            self.robot_feedback is not None
            and self.last_feedback_s > 0.0
            and time.monotonic() - self.last_feedback_s <= max(0.1, self.args.feedback_timeout_s)
        )

    def _sync_model_from_robot_feedback(self) -> bool:
        feedback = self.robot_feedback
        if feedback is None:
            return False
        sequence = feedback["sequence"]
        if sequence == self.last_synced_feedback_sequence:
            return True

        with self.data_lock:
            for side in ("right", "left"):
                arm_state = feedback[f"{side}_arm_rad"]
                self._set_joint_q(ARM_JOINTS[side], arm_state[:6])
                self._set_gripper(side, real_gripper_to_simulated(arm_state[6]))
            lift_id = self._mujoco_joint_id(LIFT_JOINT)
            lift_low, lift_high = self.model.jnt_range[lift_id]
            self.data.qpos[self.mj_qpos[LIFT_JOINT]] = np.clip(
                feedback["height_mm"] / 1000.0,
                lift_low,
                lift_high,
            )
            self.data.qvel[:] = 0.0
            mujoco.mj_forward(self.model, self.data)
            for side, arm in self.arms.items():
                current_q = self._get_joint_q(ARM_JOINTS[side])
                arm.target_tf = arm.solver.fk(current_q)
                arm.last_solved_target_tf = arm.target_tf.copy()
                arm.settle_steps_remaining = 0
                arm.reset_requested = False
                self._release_controller_origin(arm)
        self.last_synced_feedback_sequence = sequence
        return True

    def _lock_bridge(self, reason: str) -> None:
        if not self.bridge_armed:
            return
        self.chassis_command[:] = 0.0
        self.height_axis = 0.0
        self._publish_bridge_packet()
        self.bridge_armed = False
        print(f"[HEI VR Real] command bridge LOCKED: {reason}", flush=True)

    def _bridge_packet(self) -> dict:
        with self.data_lock:
            right_q = self._get_joint_q(ARM_JOINTS["right"])
            left_q = self._get_joint_q(ARM_JOINTS["left"])
            qpos = [
                *np.degrees(right_q).tolist(),
                self._real_gripper_position("right"),
                *np.degrees(left_q).tolist(),
                self._real_gripper_position("left"),
            ]
        packet = {
            "protocol_version": 2,
            "sequence": self.command_sequence,
            "timestamp_s": time.time(),
            "qpos": qpos,
            "x_val": float(self.chassis_command[0]),
            "y_val": float(self.chassis_command[1]),
            "theta_vel": float(self.chassis_command[2]),
            "height_axis": float(self.height_axis),
        }
        self.command_sequence += 1
        return packet

    def _publish_bridge_packet(self) -> None:
        try:
            self.command_socket.send_json(self._bridge_packet(), flags=zmq.NOBLOCK)
        except zmq.Again:
            if self.args.verbose:
                print("[HEI VR Real] dropped action packet because the ZMQ queue is full", flush=True)
        self.last_publish_s = time.monotonic()

    def _step_real_control(self, dt: float) -> tuple[bool, int]:
        fresh, packet_count = super()._step_control(dt)
        self._poll_robot_feedback()
        controllers, fresh, packet_count = self._snapshot_vr()
        right_grip = fresh and bool(controllers["right"]["gripActive"])
        left_grip = fresh and bool(controllers["left"]["gripActive"])
        feedback_fresh = self._feedback_is_fresh()

        if not self.bridge_armed and feedback_fresh and not self.args.allow_no_feedback:
            self._sync_model_from_robot_feedback()

        if self.bridge_armed and not fresh:
            self._lock_bridge("VR stream timed out")
        elif self.bridge_armed and not feedback_fresh:
            self._lock_bridge("robot-state feedback timed out")

        can_arm = feedback_fresh and (self.args.allow_no_feedback or self.robot_feedback is not None)
        if fresh and can_arm and not right_grip and not left_grip and not self.bridge_armed:
            self.bridge_armed = True
            arm_message = (
                "legacy mode without feedback"
                if self.args.allow_no_feedback and self.robot_feedback is None
                else "real pose synchronized"
            )
            print(f"[HEI VR Real] command bridge ARMED; {arm_message}", flush=True)

        stop_transition = (
            (self.previous_right_grip and not right_grip)
            or (self.previous_left_grip and not left_grip)
        )
        self.previous_fresh = fresh
        self.previous_right_grip = right_grip
        self.previous_left_grip = left_grip

        if not self.bridge_armed:
            return fresh, packet_count

        now_s = time.monotonic()
        publish_due = now_s - self.last_publish_s >= 1.0 / self.args.publish_hz
        if publish_due or stop_transition:
            command_dt = (
                now_s - self.last_publish_s if self.last_publish_s > 0.0 else 1.0 / self.args.publish_hz
            )
            self._update_mobile_commands(controllers, fresh, command_dt)
            self._publish_bridge_packet()
        return fresh, packet_count

    def _print_real_status(self, fresh: bool, packet_count: int) -> None:
        now_s = time.monotonic()
        if now_s - self.last_bridge_status_s < 1.0:
            return
        self.last_bridge_status_s = now_s
        feedback_age = (
            time.monotonic() - self.last_feedback_s if self.last_feedback_s > 0.0 else float("inf")
        )
        feedback_status = f"{feedback_age:.2f}s" if np.isfinite(feedback_age) else "waiting"
        print(
            f"[HEI VR Real] VR={'online' if fresh else 'waiting'} packets={packet_count} "
            f"bridge={'armed' if self.bridge_armed else 'locked'} "
            f"feedback={feedback_status} count={self.feedback_count} "
            f"base=({self.chassis_command[0]:+.3f}, {self.chassis_command[1]:+.3f}, "
            f"{self.chassis_command[2]:+.1f}) height_axis={self.height_axis:+.2f}",
            flush=True,
        )

    def _keyboard_callback(self, keycode: int) -> None:
        key = chr(keycode).upper() if 0 <= keycode < 256 else ""
        if key == "R":
            print(
                "[HEI VR Real] R reset is disabled in real mode; use right A / left X for gradual arm reset",
                flush=True,
            )
            return
        super()._keyboard_callback(keycode)

    def run_real(self) -> None:
        print("[HEI VR Real] REAL ROBOT COMMAND MODE", flush=True)
        print("[HEI VR Real] waiting for teleoperate.py/record.py feedback before arming", flush=True)
        print("[HEI VR Real] hold grip to move; release grip to stop chassis/lift immediately", flush=True)
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
                fresh, packet_count = self._step_real_control(dt)
                self.viewer.sync()
                self._print_real_status(fresh, packet_count)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def _send_final_stop(self) -> None:
        if not self.bridge_armed or self.command_closed:
            return
        self.chassis_command[:] = 0.0
        self.height_axis = 0.0
        # 重复数次发送停车包，给 SUB 桥接留出接收时间。
        for _ in range(3):
            try:
                self.command_socket.send_json(self._bridge_packet())
            except zmq.ZMQError:
                break
            time.sleep(0.02)

    def _close_command_socket(self) -> None:
        if self.command_closed:
            return
        self.command_closed = True
        self.command_socket.close(0)
        self.command_context.term()

    def _close_feedback_socket(self) -> None:
        if self.feedback_closed:
            return
        self.feedback_closed = True
        self.feedback_socket.close(0)
        self.feedback_context.term()

    def close(self) -> None:
        if self.command_closed and self.feedback_closed and self.stop_event.is_set():
            return
        self._send_final_stop()
        self._close_command_socket()
        self._close_feedback_socket()
        super().close()


def run_protocol_self_check() -> None:
    for opening in (GRIPPER_CLOSED_M, GRIPPER_OPEN_M * 0.5, GRIPPER_OPEN_M):
        restored = real_gripper_to_simulated(simulated_gripper_to_real(opening))
        if not np.isclose(restored, opening):
            raise RuntimeError("Parallel-gripper conversion self-check failed")
    valid_feedback = {
        "type": "hei_rebot_lift_state",
        "right_arm_rad": [0.0] * 7,
        "left_arm_rad": [0.0] * 7,
        "height_mm": -400.0,
        "sequence": 1,
    }
    if HEIRobotVRRealController._validate_feedback_packet(valid_feedback) is None:
        raise RuntimeError("Robot-state feedback protocol self-check failed")
    print("[HEI VR Real] bridge/feedback protocol self-check passed", flush=True)


def main() -> None:
    args = parse_args()
    if args.headless_check:
        simulator = HEIRobotVRSimulator(args)
        simulator.headless_check()
        run_protocol_self_check()
        return
    controller = HEIRobotVRRealController(args)
    controller.run_real()


if __name__ == "__main__":
    main()
