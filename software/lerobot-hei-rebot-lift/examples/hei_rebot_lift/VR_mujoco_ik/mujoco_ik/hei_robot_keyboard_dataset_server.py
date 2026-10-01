#!/usr/bin/env python
"""Publish keyboard-controlled HEI MuJoCo demonstrations through ZMQ."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import mujoco.viewer
import numpy as np
import zmq

from hei_robot_keyboard_mujoco_sim import HEIRobotKeyboardSimulator
from hei_robot_mujoco_dataset_adapter import HEIMujocoDatasetAdapter
from hei_robot_mujoco_observation_publisher import AsyncObservationPublisher
from hei_robot_mujoco_zmq_protocol import (
    DEFAULT_COMMAND_PORT,
    DEFAULT_OBSERVATION_PORT,
    OBSERVATION_TOPIC,
    tcp_endpoint,
)
from hei_robot_vr_mujoco_sim import (
    CHASSIS_MAX_LINEAR_M_S,
    CHASSIS_MAX_YAW_RAD_S,
    DEFAULT_URDF,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run keyboard-controlled HEI MuJoCo and publish demonstrations over ZMQ."
    )
    parser.add_argument("--bind-ip", default="0.0.0.0")
    parser.add_argument("--observation-port", type=int, default=DEFAULT_OBSERVATION_PORT)
    parser.add_argument("--command-port", type=int, default=DEFAULT_COMMAND_PORT)
    parser.add_argument("--publish-fps", type=float, default=30.0)
    parser.add_argument("--jpeg-quality", type=int, default=85)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
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
    parser.add_argument("--plain-scene", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    positive_values = {
        "--publish-fps": args.publish_fps,
        "--arm-linear-speed-m-s": args.arm_linear_speed_m_s,
        "--arm-angular-speed-deg-s": args.arm_angular_speed_deg_s,
        "--lift-speed-m-s": args.lift_speed_m_s,
        "--chassis-linear-speed-m-s": args.chassis_linear_speed_m_s,
        "--chassis-yaw-speed-deg-s": args.chassis_yaw_speed_deg_s,
    }
    for option, value in positive_values.items():
        if value <= 0.0:
            parser.error(f"{option} must be positive")
    if not 0.0 < args.fine_scale <= 1.0:
        parser.error("--fine-scale must be in (0, 1]")

    # Keyboard simulation does not open the inherited VR receiver.
    args.vr_endpoint = ""
    args.vr_pos_scale = 1.0
    args.vr_timeout_s = 1.0
    return args


class HEIRobotKeyboardDatasetServer(HEIRobotKeyboardSimulator):
    """Own keyboard/MuJoCo control in hei-rebot-vr and publish dataset samples."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.server_args = args
        self.adapter: HEIMujocoDatasetAdapter | None = None
        self.publisher: AsyncObservationPublisher | None = None
        self.context: zmq.Context | None = None
        self.command_socket: zmq.Socket | None = None
        super().__init__(args)
        try:
            self.adapter = HEIMujocoDatasetAdapter(
                self,
                width=args.width,
                height=args.height,
                create_renderer=False,
            )
            self.context = zmq.Context()
            self.command_socket = self.context.socket(zmq.PULL)
            self.command_socket.setsockopt(zmq.RCVHWM, 4)
            self.command_socket.bind(tcp_endpoint(args.bind_ip, args.command_port))
            self.publisher = AsyncObservationPublisher(
                self,
                endpoint=tcp_endpoint(args.bind_ip, args.observation_port),
                topic=OBSERVATION_TOPIC,
                source_mode="keyboard",
                publish_fps=args.publish_fps,
                jpeg_quality=args.jpeg_quality,
                width=args.width,
                height=args.height,
            )
            self.publisher.start()
        except Exception:
            self.close()
            raise

    def _reset_for_recording(self) -> None:
        # 清除仍处于按下状态的运动键，避免 episode 复位后立即继续运动。
        with self.key_lock:
            self.pressed_keys.clear()
            self.control_mode = "chassis"
            self.mode_changed = False
            self.reset_requested = False
            self.arm_reset_requests.clear()
        self._reset_keyboard_pose()

    def _process_commands(self) -> None:
        while True:
            try:
                command = self.command_socket.recv_json(flags=zmq.NOBLOCK)
            except zmq.Again:
                return
            command_type = command.get("type")
            if command_type == "reset":
                self._reset_for_recording()
            elif command_type == "stop":
                with self.key_lock:
                    self.pressed_keys.clear()
            else:
                print(f"[HEI Keyboard Dataset] ignored command: {command_type!r}", flush=True)

    def run(self) -> None:
        observation_endpoint = tcp_endpoint(
            self.server_args.bind_ip,
            self.server_args.observation_port,
        )
        command_endpoint = tcp_endpoint(
            self.server_args.bind_ip,
            self.server_args.command_port,
        )
        print(
            f"[HEI Keyboard Dataset] observations={observation_endpoint}, "
            f"commands={command_endpoint}, publish_fps={self.server_args.publish_fps}",
            flush=True,
        )
        print(
            "[HEI Keyboard Dataset] modes: 1 chassis, 2 lift, 3 left arm, "
            "4 right arm; 5/6 reset arms",
            flush=True,
        )
        print("[HEI Keyboard Dataset] chassis: W/S, A/D, Q/E; lift: I/K", flush=True)
        print(
            "[HEI Keyboard Dataset] arm: W/S X, A/D Y, R/F Z; "
            "U/J Rx, I/K Ry, O/L Rz; Z/X gripper",
            flush=True,
        )
        print(
            "[HEI Keyboard Dataset] Shift fine; Space stop; V frames; "
            "Backspace reset; Esc quit",
            flush=True,
        )

        self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
        self._start_keyboard_listener()
        self.viewer.cam.lookat[:] = (0.0, 0.0, 0.75)
        self.viewer.cam.distance = 2.8
        self.viewer.cam.azimuth = 135
        self.viewer.cam.elevation = -20

        previous_s = time.monotonic()
        next_publish_s = previous_s
        publish_period_s = 1.0 / self.server_args.publish_fps
        try:
            while self.viewer.is_running() and not self.exit_requested:
                now_s = time.monotonic()
                dt = min(max(now_s - previous_s, 0.0), 0.05)
                previous_s = now_s
                self._process_commands()
                self.publisher.raise_if_failed()

                sample_due = now_s >= next_publish_s
                snapshot = self.adapter.capture_snapshot() if sample_due else None
                mode = self._step_keyboard_control(dt)
                if sample_due:
                    # 与真机采集顺序一致：先观察，再记录本次控制产生的动作。
                    self.publisher.submit(snapshot, self.adapter.read_action(), time.time())
                    next_publish_s = max(next_publish_s + publish_period_s, now_s + publish_period_s)

                self.viewer.sync()
                self._print_keyboard_status(mode)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def close(self) -> None:
        if self.publisher is not None:
            self.publisher.close()
            self.publisher = None
        if self.adapter is not None:
            self.adapter.close()
            self.adapter = None
        if self.command_socket is not None:
            self.command_socket.close(0)
            self.command_socket = None
        if self.context is not None:
            self.context.term()
            self.context = None
        super().close()


def main() -> None:
    server = HEIRobotKeyboardDatasetServer(parse_args())
    server.run()


if __name__ == "__main__":
    main()
