#!/usr/bin/env python
"""Run MuJoCo independently and exchange observations/actions through ZMQ."""

from __future__ import annotations

import argparse
import time
from collections.abc import Mapping
from pathlib import Path

import mujoco.viewer
import numpy as np
import zmq

from hei_robot_mujoco_dataset_adapter import (
    HEIGHT_MAX_MM,
    HEIGHT_MIN_MM,
    HEIGHT_TARGET_STEP_MM,
    HEIMujocoDatasetAdapter,
)
from hei_robot_mujoco_zmq_protocol import (
    DEFAULT_COMMAND_PORT,
    DEFAULT_OBSERVATION_PORT,
    OBSERVATION_TOPIC,
    STATE_NAMES,
    encode_observation_packet,
    safe_hold_action,
    tcp_endpoint,
)
from hei_robot_vr_mujoco_sim import (
    ARM_JOINTS,
    DEFAULT_URDF,
    DEFAULT_VR_ENDPOINT,
    HEIRobotVRSimulator,
    LIFT_DEADZONE,
    VR_STALE_TIMEOUT_S,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run HEI MuJoCo as an independent VR demonstration or policy simulation server."
    )
    parser.add_argument("--control-source", choices=("vr", "policy"), required=True)
    parser.add_argument("--bind-ip", default="0.0.0.0", help="ZMQ bind address.")
    parser.add_argument("--observation-port", type=int, default=DEFAULT_OBSERVATION_PORT)
    parser.add_argument("--command-port", type=int, default=DEFAULT_COMMAND_PORT)
    parser.add_argument("--publish-fps", type=float, default=30.0)
    parser.add_argument("--jpeg-quality", type=int, default=85)
    parser.add_argument("--policy-timeout-s", type=float, default=1.0)
    parser.add_argument("--model", type=Path, default=DEFAULT_URDF)
    parser.add_argument("--vr-endpoint", default=DEFAULT_VR_ENDPOINT)
    parser.add_argument("--vr-pos-scale", type=float, default=1.0)
    parser.add_argument("--lift-speed-m-s", type=float, default=0.20)
    parser.add_argument("--vr-timeout-s", type=float, default=VR_STALE_TIMEOUT_S)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--plain-scene", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.publish_fps <= 0.0:
        parser.error("--publish-fps must be positive")
    if args.policy_timeout_s <= 0.0:
        parser.error("--policy-timeout-s must be positive")
    return args


class HEIMujocoZmqServer(HEIRobotVRSimulator):
    """Own MuJoCo in hei-rebot-vr; never imports LeRobot."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.server_args = args
        self.control_source = args.control_source
        super().__init__(args)
        self.adapter: HEIMujocoDatasetAdapter | None = None
        self.context: zmq.Context | None = None
        self.observation_socket: zmq.Socket | None = None
        self.command_socket: zmq.Socket | None = None
        try:
            self.adapter = HEIMujocoDatasetAdapter(self, width=args.width, height=args.height)
            self.context = zmq.Context()
            self.observation_socket = self.context.socket(zmq.PUB)
            self.observation_socket.setsockopt(zmq.SNDHWM, 2)
            self.observation_socket.bind(tcp_endpoint(args.bind_ip, args.observation_port))
            self.command_socket = self.context.socket(zmq.PULL)
            self.command_socket.setsockopt(zmq.RCVHWM, 4)
            self.command_socket.bind(tcp_endpoint(args.bind_ip, args.command_port))
        except Exception:
            self.close()
            raise

        self.sequence = 0
        self.last_command_s = 0.0
        self.last_policy_action = safe_hold_action(self.adapter.read_state())
        self.dropped_packets = 0
        self.last_network_status_s = 0.0

    def _vr_listener(self) -> None:
        if self.control_source == "vr":
            super()._vr_listener()

    @staticmethod
    def _validate_action(values: Mapping[str, object]) -> dict[str, float]:
        missing = [name for name in STATE_NAMES if name not in values]
        if missing:
            raise ValueError(f"policy action is missing fields: {missing}")
        action = {name: float(values[name]) for name in STATE_NAMES}
        if not np.all(np.isfinite(tuple(action.values()))):
            raise ValueError("policy action contains non-finite values")
        return action

    def _reset_simulation(self) -> None:
        self._reset_full_pose()
        with self.data_lock:
            for arm in self.arms.values():
                self._release_controller_origin(arm)
                current_q = self._get_joint_q(ARM_JOINTS[arm.side])
                arm.target_tf = arm.solver.fk(current_q)
                arm.last_solved_target_tf = None
                arm.last_accepted_ik_q = current_q.copy()
                arm.last_accepted_target_tf = arm.target_tf.copy()
                arm.settle_steps_remaining = 0
                arm.reset_requested = False
        self.last_policy_action = safe_hold_action(self.adapter.read_state())
        self.last_command_s = 0.0
        print("[HEI Sim Server] simulation reset", flush=True)

    def _process_commands(self) -> None:
        while True:
            try:
                command = self.command_socket.recv_json(flags=zmq.NOBLOCK)
            except zmq.Again:
                return
            command_type = command.get("type")
            if command_type == "reset":
                self._reset_simulation()
            elif command_type == "policy_action":
                if self.control_source != "policy":
                    print("[HEI Sim Server] ignored policy action while control-source=vr", flush=True)
                    continue
                try:
                    self.last_policy_action = self._validate_action(command.get("action", {}))
                except (TypeError, ValueError) as exc:
                    print(f"[HEI Sim Server] ignored invalid policy action: {exc}", flush=True)
                    continue
                self.last_command_s = time.monotonic()
            elif command_type == "stop":
                self.last_policy_action = safe_hold_action(self.adapter.read_state())
                self.last_command_s = 0.0
            else:
                print(f"[HEI Sim Server] ignored unknown command: {command_type!r}", flush=True)

    def _step_policy(self, dt: float, now_s: float) -> None:
        if self.last_command_s <= 0.0 or now_s - self.last_command_s > self.server_args.policy_timeout_s:
            action = safe_hold_action(self.adapter.read_state())
        else:
            action = self.last_policy_action
        self.adapter.apply_action(action, dt)

    def _publish(self, observation: dict, action: dict, timestamp_s: float) -> None:
        packet = encode_observation_packet(
            topic=OBSERVATION_TOPIC,
            sequence=self.sequence,
            timestamp_s=timestamp_s,
            source_mode=self.control_source,
            publish_fps=self.server_args.publish_fps,
            observation=observation,
            action=action,
            jpeg_quality=self.server_args.jpeg_quality,
        )
        try:
            self.observation_socket.send_multipart(packet, flags=zmq.NOBLOCK, copy=False)
            self.sequence += 1
        except zmq.Again:
            self.dropped_packets += 1

    def _keyboard_callback(self, keycode: int) -> None:
        key = chr(keycode).upper() if 0 <= keycode < 256 else ""
        if key == "R":
            self._reset_simulation()
        else:
            super()._keyboard_callback(keycode)

    def run(self) -> None:
        observation_endpoint = tcp_endpoint(self.server_args.bind_ip, self.server_args.observation_port)
        command_endpoint = tcp_endpoint(self.server_args.bind_ip, self.server_args.command_port)
        print(
            f"[HEI Sim Server] mode={self.control_source}, observations={observation_endpoint}, "
            f"commands={command_endpoint}, publish_fps={self.server_args.publish_fps}",
            flush=True,
        )
        if self.control_source == "vr":
            print("[HEI Sim Server] VR controls simulation; start record_mujoco.py in lerobot5", flush=True)
        else:
            print("[HEI Sim Server] waiting for rollout_mujoco.py actions from lerobot5", flush=True)

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
        next_publish_s = previous_s
        publish_period_s = 1.0 / self.server_args.publish_fps
        try:
            while self.viewer.is_running() and not self.stop_event.is_set():
                now_s = time.monotonic()
                dt = min(max(now_s - previous_s, 0.0), 0.05)
                previous_s = now_s
                self._process_commands()

                sample_due = now_s >= next_publish_s
                observation = self.adapter.read_observation() if sample_due else None
                if self.control_source == "vr":
                    fresh, packet_count = self._step_control(dt)
                    if sample_due:
                        action = self.adapter.read_action()
                        controllers, action_fresh, _ = self._snapshot_vr()
                        left = controllers["left"]
                        lift_axis = (
                            self._deadzone(left["thumbstick"]["y"], LIFT_DEADZONE)
                            if action_fresh and left["gripActive"]
                            else 0.0
                        )
                        # 真机链路记录的是下一目标高度，而不是升降瞬时速度。
                        action["height.pos"] = float(
                            np.clip(
                                observation["height.pos"] - lift_axis * HEIGHT_TARGET_STEP_MM,
                                HEIGHT_MIN_MM,
                                HEIGHT_MAX_MM,
                            )
                        )
                else:
                    self._step_policy(dt, now_s)
                    fresh = self.last_command_s > 0.0 and (
                        now_s - self.last_command_s <= self.server_args.policy_timeout_s
                    )
                    packet_count = self.sequence
                    if sample_due:
                        action = self.last_policy_action.copy()

                if sample_due:
                    self._publish(observation, action, time.time())
                    next_publish_s = max(next_publish_s + publish_period_s, now_s + publish_period_s)

                self.viewer.sync()
                if self.control_source == "vr":
                    self._print_status(fresh, packet_count)
                elif now_s - self.last_network_status_s >= 1.0:
                    age = (
                        max(0.0, now_s - self.last_command_s)
                        if self.last_command_s > 0.0
                        else float("inf")
                    )
                    print(
                        f"[HEI Sim Server] policy={'online' if fresh else 'waiting'} "
                        f"published={self.sequence} command_age={age:.2f}s dropped={self.dropped_packets}",
                        flush=True,
                    )
                    self.last_network_status_s = now_s
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def close(self) -> None:
        if self.adapter is not None:
            self.adapter.close()
            self.adapter = None
        if self.observation_socket is not None:
            self.observation_socket.close(0)
            self.observation_socket = None
        if self.command_socket is not None:
            self.command_socket.close(0)
            self.command_socket = None
        if self.context is not None:
            self.context.term()
            self.context = None
        super().close()


def main() -> None:
    server = HEIMujocoZmqServer(parse_args())
    server.run()


if __name__ == "__main__":
    main()
