#!/usr/bin/env python

import contextlib
import logging
import threading
import time

import numpy as np
import zmq

VR_ZMQ_ADDRESS = "tcp://localhost:6558"

RIGHT_QPOS_START = 0
LEFT_QPOS_START = 7
ARM_QPOS_COUNT = 7
ARM_JOINT_COUNT = 6
ARM_JOINTS = ("joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6", "gripper")

RIGHT_MIN_RAD = np.array([-0.3, -3.14, -3.14, -1.4, -1.57, -3.14, -4.5])
RIGHT_MAX_RAD = np.array([1.5, 0.0, 0.0, 1.57, 1.57, 3.14, 0.0])
LEFT_MIN_RAD = np.array([-1.5, -3.14, -3.14, -1.4, -1.57, -3.14, -4.5])
LEFT_MAX_RAD = np.array([0.3, 0.0, 0.0, 1.57, 1.57, 3.14, 0.0])
RIGHT_DIRECTION = np.ones(ARM_QPOS_COUNT, dtype=float)
LEFT_DIRECTION = np.ones(ARM_QPOS_COUNT, dtype=float)
RIGHT_TRIM_RAD = np.zeros(ARM_QPOS_COUNT, dtype=float)
LEFT_TRIM_RAD = np.zeros(ARM_QPOS_COUNT, dtype=float)

HEIGHT_MIN_MM = -800.0
HEIGHT_MAX_MM = 0.0
HEIGHT_TARGET_STEP_MM = 80.0
THETA_INPUT_SCALE = 30.0


def map_arm_qpos(packet_qpos, start, lower_rad, upper_rad, direction, trim_rad):
    raw = np.asarray(packet_qpos[start : start + ARM_QPOS_COUNT], dtype=float)
    command = np.zeros(ARM_QPOS_COUNT, dtype=float)
    command[:ARM_JOINT_COUNT] = np.radians(raw[:ARM_JOINT_COUNT])
    command[6] = raw[6]
    command = command * direction + trim_rad
    return np.clip(command, lower_rad, upper_rad)


def arm_action(side, command):
    return {f"{side}_{joint}.pos": float(command[i]) for i, joint in enumerate(ARM_JOINTS)}


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
        self._height_axis = 0.0

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def set_height_from_observation(self, observation):
        with self._lock:
            self._height_axis = 0.0

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
            height_axis = None
            if "qpos" in message:
                qpos = message["qpos"]
                if isinstance(qpos, list) and len(qpos) >= LEFT_QPOS_START + ARM_QPOS_COUNT:
                    right_command = map_arm_qpos(
                        qpos, RIGHT_QPOS_START, RIGHT_MIN_RAD, RIGHT_MAX_RAD, RIGHT_DIRECTION, RIGHT_TRIM_RAD
                    )
                    left_command = map_arm_qpos(
                        qpos, LEFT_QPOS_START, LEFT_MIN_RAD, LEFT_MAX_RAD, LEFT_DIRECTION, LEFT_TRIM_RAD
                    )
                    right_arm_action = arm_action("right", right_command)
                    left_arm_action = arm_action("left", left_command)

            if "x_val" in message:
                theta_input = float(message.get("theta_vel", 0.0))
                base_action = {
                    "x.vel": float(message.get("x_val", 0.0)),
                    "y.vel": float(message.get("y_val", 0.0)),
                    "theta.vel": float(np.clip(theta_input / THETA_INPUT_SCALE, -1.0, 1.0)),
                }

            if "height_axis" in message:
                height_axis = float(np.clip(message["height_axis"], -1.0, 1.0))

            with self._lock:
                if left_arm_action is not None:
                    self._left_arm_action = left_arm_action
                if right_arm_action is not None:
                    self._right_arm_action = right_arm_action
                if base_action is not None:
                    self._base_action = base_action
                if height_axis is not None:
                    self._height_axis = height_axis

        self._close_socket()

    def get_action(self, observation=None):
        with self._lock:
            height_axis = self._height_axis
            action = {**self._right_arm_action, **self._left_arm_action, **self._base_action}

        current_height = 0.0
        if observation is not None:
            current_height = float(observation.get("height.pos", 0.0))
        height_target = np.clip(current_height - height_axis * HEIGHT_TARGET_STEP_MM, HEIGHT_MIN_MM, HEIGHT_MAX_MM)
        action["height.pos"] = float(height_target)
        return action

    def has_arm_action(self):
        with self._lock:
            return bool(self._left_arm_action and self._right_arm_action)

    def wait_for_arm_action(self, poll_s: float = 1.0):
        while not self.has_arm_action():
            print(f"Waiting for VR arm qpos messages on {self.address}...")
            time.sleep(poll_s)

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            # ZMQ socket 由接收线程创建，优先让接收线程自己退出并关闭资源；
            # 主线程直接关闭正在 recv 的 socket，偶发会导致程序退出不干净。
            self._thread.join(timeout=1.5)
            if self._thread.is_alive():
                logging.warning("VR ZMQ receiver did not stop cleanly; forcing context shutdown.")
                if self._context is not None:
                    with contextlib.suppress(Exception):
                        self._context.destroy(linger=0)
                self._thread.join(timeout=0.5)
            if self._thread.is_alive():
                logging.warning("VR ZMQ receiver thread is still alive after forced shutdown.")
                return
            self._thread = None
        self._close_socket()

    def _close_socket(self):
        if self._socket is not None:
            with contextlib.suppress(Exception):
                self._socket.close(0)
            self._socket = None
        if self._context is not None:
            with contextlib.suppress(Exception):
                self._context.term()
            self._context = None
