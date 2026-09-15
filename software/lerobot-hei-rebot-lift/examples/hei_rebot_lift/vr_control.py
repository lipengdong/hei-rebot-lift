#!/usr/bin/env python

import contextlib
import logging
import threading
import time

import numpy as np
import zmq

VR_ZMQ_ADDRESS = "tcp://localhost:6558"
ROBOT_STATE_ZMQ_BIND_ADDRESS = "tcp://*:6559"

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
COMMAND_STALE_TIMEOUT_S = 0.5
ROBOT_STATE_PUBLISH_HZ = 10.0


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
    def __init__(
        self,
        address: str = VR_ZMQ_ADDRESS,
        stale_timeout_s: float = COMMAND_STALE_TIMEOUT_S,
        feedback_bind_address: str | None = ROBOT_STATE_ZMQ_BIND_ADDRESS,
    ):
        self.address = address
        self.stale_timeout_s = float(stale_timeout_s)
        self.feedback_bind_address = feedback_bind_address
        self._lock = threading.Lock()
        self._context = None
        self._socket = None
        self._thread = None
        self._feedback_thread = None
        self._feedback_ready = threading.Event()
        self._feedback_error = None
        self._stop_event = threading.Event()
        self._left_arm_action = {}
        self._right_arm_action = {}
        self._base_action = {}
        self._height_axis = 0.0
        self._last_message_s = 0.0
        self._last_stale_log_s = 0.0
        self._robot_state = None
        self._feedback_sequence = 0

    def start(self):
        if self._thread is not None:
            return
        self._stop_event.clear()
        if self.feedback_bind_address is not None:
            self._feedback_ready.clear()
            self._feedback_error = None
            self._feedback_thread = threading.Thread(
                target=self._feedback_loop,
                name="hei-robot-state-feedback",
                daemon=True,
            )
            self._feedback_thread.start()
            if not self._feedback_ready.wait(timeout=2.0):
                raise RuntimeError("Timed out while starting the robot-state feedback publisher")
            if self._feedback_error is not None:
                raise RuntimeError(
                    f"Failed to bind robot-state feedback at {self.feedback_bind_address}: "
                    f"{self._feedback_error}"
                )
        self._thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thread.start()

    def set_height_from_observation(self, observation):
        self.set_robot_observation(observation)
        with self._lock:
            self._height_axis = 0.0

    @staticmethod
    def _robot_state_from_observation(observation):
        if observation is None:
            return None
        joint_keys = [f"{side}_{joint}.pos" for side in ("right", "left") for joint in ARM_JOINTS]
        if any(key not in observation for key in joint_keys):
            return None
        values = np.asarray([observation[key] for key in joint_keys], dtype=float)
        height_mm = float(observation.get("height.pos", 0.0))
        if not np.all(np.isfinite(values)) or not np.isfinite(height_mm):
            return None
        return {
            "type": "hei_rebot_lift_state",
            "right_arm_rad": values[:ARM_QPOS_COUNT].tolist(),
            "left_arm_rad": values[ARM_QPOS_COUNT:].tolist(),
            "height_mm": height_mm,
        }

    def set_robot_observation(self, observation) -> None:
        state = self._robot_state_from_observation(observation)
        if state is None:
            return
        with self._lock:
            self._robot_state = state

    def _feedback_loop(self) -> None:
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        socket.setsockopt(zmq.SNDHWM, 2)
        socket.setsockopt(zmq.LINGER, 0)
        try:
            socket.bind(self.feedback_bind_address)
        except zmq.ZMQError as exc:
            self._feedback_error = exc
            self._feedback_ready.set()
            socket.close(0)
            context.term()
            return
        self._feedback_ready.set()
        print(f"[HEI VR] robot-state feedback publishing on {self.feedback_bind_address}", flush=True)
        period_s = 1.0 / ROBOT_STATE_PUBLISH_HZ
        try:
            while not self._stop_event.is_set():
                with self._lock:
                    state = self._robot_state.copy() if self._robot_state is not None else None
                    sequence = self._feedback_sequence
                    if state is not None:
                        self._feedback_sequence += 1
                if state is not None:
                    state["sequence"] = sequence
                    state["timestamp_s"] = time.time()
                    try:
                        socket.send_json(state, flags=zmq.NOBLOCK)
                    except zmq.Again:
                        pass
                self._stop_event.wait(period_s)
        finally:
            socket.close(0)
            context.term()

    def _receive_loop(self):
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.SUB)
        self._socket.setsockopt_string(zmq.SUBSCRIBE, "")
        # 限制队列并每次只消费最新包，避免网络恢复后回放过期动作。
        self._socket.setsockopt(zmq.RCVHWM, 2)
        self._socket.setsockopt(zmq.RCVTIMEO, 250)
        self._socket.connect(self.address)

        while not self._stop_event.is_set():
            try:
                message = self._socket.recv_json()
                while True:
                    try:
                        message = self._socket.recv_json(flags=zmq.NOBLOCK)
                    except zmq.Again:
                        break
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
                self._last_message_s = time.monotonic()

        self._close_socket()

    def get_action(self, observation=None):
        # 控制循环每次读取实机观测后都更新轻量反馈，供 MuJoCo 真机入口安全同步。
        self.set_robot_observation(observation)
        with self._lock:
            height_axis = self._height_axis
            action = {**self._right_arm_action, **self._left_arm_action, **self._base_action}
            last_message_s = self._last_message_s

        stale = (
            last_message_s <= 0.0
            or time.monotonic() - last_message_s > max(self.stale_timeout_s, 0.1)
        )
        if stale:
            # 保留最后关节位置让机械臂原地保持，只立即撤销底盘和升降运动。
            action.update({"x.vel": 0.0, "y.vel": 0.0, "theta.vel": 0.0})
            height_axis = 0.0
            now_s = time.monotonic()
            if last_message_s > 0.0 and now_s - self._last_stale_log_s >= 2.0:
                logging.warning(
                    "VR action stream is stale for %.3fs; stopping chassis and lift.",
                    now_s - last_message_s,
                )
                self._last_stale_log_s = now_s

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
        if self._feedback_thread is not None:
            self._feedback_thread.join(timeout=1.5)
            if self._feedback_thread.is_alive():
                logging.warning("Robot-state feedback thread did not stop cleanly.")
            else:
                self._feedback_thread = None
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
