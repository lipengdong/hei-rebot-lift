# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

import logging
import threading
import time

import numpy as np
import zmq


VR_ZMQ_ADDRESS = "tcp://localhost:6558"

# Keep this in sync with the MuJoCo controller:
# RIGHT_QPOS = slice(0, 8), LEFT_QPOS = slice(8, 16).
RIGHT_QPOS_START = 0
LEFT_QPOS_START = 8

ARM_JOINTS = (
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "wrist_x",
    "wrist_y",
    "gripper",
)

# Joint limits from the Xinma MuJoCo URDF, in degrees.
RIGHT_LOWER_DEG = np.array([-89.954, -89.954, -89.954, -89.954, -171.887, -45.837, -89.954, -8.995])
RIGHT_UPPER_DEG = np.array([89.954, 8.995, 89.954, 70.161, 171.887, 45.837, 89.954, 89.954])
LEFT_LOWER_DEG = np.array([-89.954, -8.995, -89.954, -89.954, -171.887, -45.837, -89.954, -8.995])
LEFT_UPPER_DEG = np.array([89.954, 89.954, 89.954, 70.161, 171.887, 45.837, 89.954, 89.954])

# Direction correction from MuJoCo joint coordinates to real LeKiwi motor coordinates.
RIGHT_DIRECTION = np.array([-1, -1, -1, -1, -1, 1, 1, 1], dtype=float)
LEFT_DIRECTION = np.array([1, -1, -1, -1, -1, 1, 1, 1], dtype=float)

# Fine trim after normalization, in LeKiwi command units.
RIGHT_TRIM = np.zeros(8, dtype=float)
LEFT_TRIM = np.zeros(8, dtype=float)


def map_arm_qpos(joint_angles, start, lower_deg, upper_deg, direction, trim):
    sim_degrees = np.asarray(joint_angles[start : start + 8], dtype=float)
    sim_degrees = np.clip(sim_degrees, lower_deg, upper_deg)
    command = ((sim_degrees - lower_deg) / (upper_deg - lower_deg)) * 200.0 - 100.0
    command[-1] = ((sim_degrees[-1] - lower_deg[-1]) / (upper_deg[-1] - lower_deg[-1])) * 100.0
    command = command * direction + trim
    command[:-1] = np.clip(command[:-1], -100.0, 100.0)
    command[-1] = np.clip(command[-1], 0.0, 100.0)
    return np.round(command, 1)


def arm_action(side, command):
    return {f"{side}_arm_{joint}.pos": float(command[i]) for i, joint in enumerate(ARM_JOINTS)}


class VRActionReceiver:
    def __init__(self, address: str = VR_ZMQ_ADDRESS):
        self.address = address
        self._lock = threading.Lock()
        self._context = None
        self._socket = None
        self._thread = None
        self._stop_event = threading.Event()
        self._left_arm_action = {}
        self._right_arm_action = {}
        self._base_action = {}

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def _receive_loop(self):
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.connect(self.address)
        self._socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self._socket.setsockopt(zmq.RCVTIMEO, 250)

        while not self._stop_event.is_set():
            try:
                message = self._socket.recv_json()
            except zmq.Again:
                continue
            except zmq.ZMQError as exc:
                if not self._stop_event.is_set():
                    logging.warning("VR ZMQ receive failed: %s", exc)
                break

            left_arm_action = right_arm_action = base_action = None
            if "qpos" in message:
                joint_angles = message["qpos"]
                right_command = map_arm_qpos(
                    joint_angles, RIGHT_QPOS_START, RIGHT_LOWER_DEG, RIGHT_UPPER_DEG, RIGHT_DIRECTION, RIGHT_TRIM
                )
                left_command = map_arm_qpos(
                    joint_angles, LEFT_QPOS_START, LEFT_LOWER_DEG, LEFT_UPPER_DEG, LEFT_DIRECTION, LEFT_TRIM
                )
                right_arm_action = arm_action("right", right_command)
                left_arm_action = arm_action("left", left_command)

            if "x_val" in message:
                base_action = {
                    "x.vel": float(message["x_val"]),
                    "y.vel": float(message["y_val"]),
                    "theta.vel": float(message["theta_vel"]),
                    "height.vel": float(message["height_val"]),
                    "yao.vel": float(message["yao_val"]),
                }

            with self._lock:
                if left_arm_action is not None:
                    self._left_arm_action = left_arm_action
                if right_arm_action is not None:
                    self._right_arm_action = right_arm_action
                if base_action is not None:
                    self._base_action = base_action

        self._close_socket()

    def get_action(self):
        with self._lock:
            return {**self._left_arm_action, **self._right_arm_action, **self._base_action}

    def has_arm_action(self):
        with self._lock:
            return bool(self._left_arm_action and self._right_arm_action)

    def wait_for_arm_action(self, poll_s: float = 1.0):
        while not self.has_arm_action():
            print(f"Waiting for VR arm qpos messages on {self.address}...")
            time.sleep(poll_s)

    def stop(self):
        self._stop_event.set()
        self._close_socket()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _close_socket(self):
        if self._socket is not None:
            self._socket.close(0)
            self._socket = None
        if self._context is not None:
            self._context.term()
            self._context = None
