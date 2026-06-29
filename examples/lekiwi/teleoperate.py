# !/usr/bin/env python

# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time

from lerobot.robots.lekiwi import LeKiwiClient, LeKiwiClientConfig
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data

from vr_control import VRActionReceiver

FPS = 30
REMOTE_IP = "192.168.31.28"
ROBOT_ID = "my_lekiwi"


def main():
    robot_config = LeKiwiClientConfig(remote_ip=REMOTE_IP, id=ROBOT_ID)

    robot = LeKiwiClient(robot_config)
    vr_receiver = VRActionReceiver()
    vr_receiver.start()

    # To connect you already should have this script running on LeKiwi: `python -m lerobot.robots.lekiwi.lekiwi_host --robot.id=my_awesome_kiwi`
    robot.connect()

    init_rerun(session_name="lekiwi_teleop")

    try:
        if not robot.is_connected:
            raise ValueError("Robot is not connected!")

        print("Starting VR teleop loop...")
        vr_receiver.wait_for_arm_action()
        while True:
            t0 = time.perf_counter()

            observation = robot.get_observation()
            action = vr_receiver.get_action()

            if action:
                _ = robot.send_action(action)
                log_rerun_data(observation=observation, action=action)

            precise_sleep(max(1.0 / FPS - (time.perf_counter() - t0), 0.0))
    finally:
        vr_receiver.stop()
        if robot.is_connected:
            robot.disconnect()


if __name__ == "__main__":
    main()
