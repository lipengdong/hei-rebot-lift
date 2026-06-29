#!/usr/bin/env python

import base64
import json
import logging
import time
from dataclasses import dataclass, field

import cv2
import draccus
import zmq

from .config_hei_rebot_lift import HeiRebotLiftConfig, HeiRebotLiftHostConfig
from .hei_rebot_lift import HeiRebotLift


@dataclass
class HeiRebotLiftServerConfig:
    robot: HeiRebotLiftConfig = field(default_factory=HeiRebotLiftConfig)
    host: HeiRebotLiftHostConfig = field(default_factory=HeiRebotLiftHostConfig)


class HeiRebotLiftHost:
    def __init__(self, config: HeiRebotLiftHostConfig):
        self.zmq_context = zmq.Context()
        self.zmq_cmd_socket = self.zmq_context.socket(zmq.PULL)
        self.zmq_cmd_socket.setsockopt(zmq.CONFLATE, 1)
        self.zmq_cmd_socket.bind(f"tcp://*:{config.port_zmq_cmd}")

        self.zmq_observation_socket = self.zmq_context.socket(zmq.PUSH)
        self.zmq_observation_socket.setsockopt(zmq.CONFLATE, 1)
        self.zmq_observation_socket.bind(f"tcp://*:{config.port_zmq_observations}")

        self.connection_time_s = config.connection_time_s
        self.watchdog_timeout_ms = config.watchdog_timeout_ms
        self.max_loop_freq_hz = config.max_loop_freq_hz

    def disconnect(self):
        self.zmq_observation_socket.close()
        self.zmq_cmd_socket.close()
        self.zmq_context.term()


@draccus.wrap()
def main(cfg: HeiRebotLiftServerConfig):
    logging.info("Configuring HEI ReBot Lift")
    robot = HeiRebotLift(cfg.robot)

    logging.info("Connecting HEI ReBot Lift")
    robot.connect()

    logging.info("Starting HEI ReBot Lift host")
    host = HeiRebotLiftHost(cfg.host)

    last_cmd_time = time.time()
    last_no_cmd_log_time = 0.0
    watchdog_active = False
    try:
        start = time.perf_counter()
        duration = 0.0
        while duration < host.connection_time_s:
            loop_start_time = time.time()
            try:
                msg = host.zmq_cmd_socket.recv_string(zmq.NOBLOCK)
                data = dict(json.loads(msg))
                robot.send_action(data)
                last_cmd_time = time.time()
                watchdog_active = False
            except zmq.Again:
                now = time.time()
                if not watchdog_active and now - last_no_cmd_log_time > 2.0:
                    logging.warning("No command available")
                    last_no_cmd_log_time = now
            except Exception as exc:
                logging.error("Message fetching failed: %s", exc)

            now = time.time()
            if (now - last_cmd_time > host.watchdog_timeout_ms / 1000) and not watchdog_active:
                logging.warning(
                    "Command not received for more than %s milliseconds. Stopping chassis and lift.",
                    host.watchdog_timeout_ms,
                )
                watchdog_active = True
                robot.stop_motion()

            last_observation = robot.get_observation()
            for cam_key in robot.cameras:
                ret, buffer = cv2.imencode(
                    ".jpg", last_observation[cam_key], [int(cv2.IMWRITE_JPEG_QUALITY), 90]
                )
                last_observation[cam_key] = base64.b64encode(buffer).decode("utf-8") if ret else ""

            try:
                host.zmq_observation_socket.send_string(json.dumps(last_observation), flags=zmq.NOBLOCK)
            except zmq.Again:
                logging.info("Dropping observation, no client connected")

            elapsed = time.time() - loop_start_time
            time.sleep(max(1 / host.max_loop_freq_hz - elapsed, 0.0))
            duration = time.perf_counter() - start
        print("Cycle time reached.")
    except KeyboardInterrupt:
        print("Keyboard interrupt received. Exiting...")
    finally:
        print("Shutting down HEI ReBot Lift host.")
        robot.disconnect()
        host.disconnect()


if __name__ == "__main__":
    main()
