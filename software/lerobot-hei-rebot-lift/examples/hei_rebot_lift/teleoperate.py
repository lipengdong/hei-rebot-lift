#!/usr/bin/env python

import argparse
import time

from lerobot.robots.hei_rebot_lift import HeiRebotLiftClient, HeiRebotLiftClientConfig
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data

from vr_control import VRActionReceiver

FPS = 30
REMOTE_IP = "192.168.31.130"
ROBOT_ID = "hei_rebot_lift"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Teleoperate HEI ReBot Lift with VR controllers.")
    parser.add_argument("--remote-ip", type=str, default=REMOTE_IP, help="HEI ReBot Lift host IP address.")
    parser.add_argument("--robot-id", type=str, default=ROBOT_ID, help="Robot identifier.")
    parser.add_argument("--fps", type=int, default=FPS, help="Teleoperation control frequency.")
    return parser.parse_args()


def main():
    args = parse_args()
    robot_config = HeiRebotLiftClientConfig(remote_ip=args.remote_ip, id=args.robot_id)
    robot = HeiRebotLiftClient(robot_config)
    vr_receiver = VRActionReceiver()
    vr_receiver.start()

    print(f"[HEI Teleoperate] Connecting to robot host={args.remote_ip}, robot_id={args.robot_id}")
    robot.connect()
    init_rerun(session_name="hei_rebot_lift_teleop")

    try:
        if not robot.is_connected:
            raise ValueError("Robot is not connected!")

        observation = robot.get_observation()
        vr_receiver.set_height_from_observation(observation)

        print(f"Starting HEI ReBot Lift VR teleop loop at {args.fps} fps")
        vr_receiver.wait_for_arm_action()
        while True:
            t0 = time.perf_counter()

            observation = robot.get_observation()
            action = vr_receiver.get_action(observation)

            if action:
                action_sent = robot.send_action(action)
                log_rerun_data(observation=observation, action=action_sent)

            precise_sleep(max(1.0 / args.fps - (time.perf_counter() - t0), 0.0))
    finally:
        vr_receiver.stop()
        if robot.is_connected:
            robot.disconnect()


if __name__ == "__main__":
    main()
