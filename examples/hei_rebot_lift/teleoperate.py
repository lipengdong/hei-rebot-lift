#!/usr/bin/env python

import time

from lerobot.robots.hei_rebot_lift import HeiRebotLiftClient, HeiRebotLiftClientConfig
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data

from vr_control import VRActionReceiver

FPS = 30
REMOTE_IP = "192.168.31.127"
ROBOT_ID = "hei_rebot_lift"


def main():
    robot_config = HeiRebotLiftClientConfig(remote_ip=REMOTE_IP, id=ROBOT_ID)
    robot = HeiRebotLiftClient(robot_config)
    vr_receiver = VRActionReceiver()
    vr_receiver.start()

    robot.connect()
    init_rerun(session_name="hei_rebot_lift_teleop")

    try:
        if not robot.is_connected:
            raise ValueError("Robot is not connected!")

        observation = robot.get_observation()
        vr_receiver.set_height_from_observation(observation)

        print("Starting HEI ReBot Lift VR teleop loop...")
        vr_receiver.wait_for_arm_action()
        while True:
            t0 = time.perf_counter()

            observation = robot.get_observation()
            action = vr_receiver.get_action(observation)

            if action:
                action_sent = robot.send_action(action)
                log_rerun_data(observation=observation, action=action_sent)

            precise_sleep(max(1.0 / FPS - (time.perf_counter() - t0), 0.0))
    finally:
        vr_receiver.stop()
        if robot.is_connected:
            robot.disconnect()


if __name__ == "__main__":
    main()
