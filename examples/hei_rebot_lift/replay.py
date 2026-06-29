#!/usr/bin/env python

import argparse
import time

from lerobot.datasets import LeRobotDataset
from lerobot.processor import make_default_processors
from lerobot.robots.hei_rebot_lift import HeiRebotLiftClient, HeiRebotLiftClientConfig
from lerobot.utils.constants import ACTION
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import log_say
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data

EPISODE_IDX = 0
HF_REPO_ID = "HGM/hei_rebot_lift"
REMOTE_IP = "192.168.31.127"
ROBOT_ID = "hei_rebot_lift"


def parse_args():
    parser = argparse.ArgumentParser(description="Replay one recorded HEI ReBot Lift dataset episode.")
    parser.add_argument("--repo-id", type=str, default=HF_REPO_ID, help="Hugging Face dataset repo id.")
    parser.add_argument("--episode-index", type=int, default=EPISODE_IDX, help="Episode index to replay.")
    parser.add_argument("--root", type=str, default=None, help="Local dataset root.")
    parser.add_argument("--remote-ip", type=str, default=REMOTE_IP, help="HEI ReBot Lift host IP address.")
    parser.add_argument("--robot-id", type=str, default=ROBOT_ID, help="HEI ReBot Lift robot id.")
    parser.add_argument("--fps", type=float, default=None, help="Replay FPS. Defaults to dataset FPS.")
    parser.add_argument("--display-data", action="store_true", help="Visualize with Rerun while replaying.")
    return parser.parse_args()


def main():
    args = parse_args()

    robot_config = HeiRebotLiftClientConfig(remote_ip=args.remote_ip, id=args.robot_id)
    robot = HeiRebotLiftClient(robot_config)
    _, robot_action_processor, robot_observation_processor = make_default_processors()

    dataset = LeRobotDataset(args.repo_id, root=args.root, episodes=[args.episode_index])
    episode_frames = dataset.hf_dataset.filter(lambda x: x["episode_index"] == args.episode_index)
    actions = episode_frames.select_columns(ACTION)
    replay_fps = args.fps if args.fps is not None else dataset.fps

    robot.connect()
    if args.display_data:
        init_rerun(session_name="hei_rebot_lift_replay")

    try:
        if not robot.is_connected:
            raise ValueError("Robot is not connected!")

        print("Starting HEI ReBot Lift replay loop...")
        log_say(f"Replaying episode {args.episode_index}")
        for idx in range(len(episode_frames)):
            t0 = time.perf_counter()

            action = {
                name: float(actions[idx][ACTION][i])
                for i, name in enumerate(dataset.features[ACTION]["names"])
            }

            observation = robot.get_observation()
            observation = robot_observation_processor(observation)
            action = robot_action_processor((action, observation))

            _ = robot.send_action(action)

            if args.display_data:
                log_rerun_data(observation=observation, action=action)

            precise_sleep(max(1.0 / replay_fps - (time.perf_counter() - t0), 0.0))
    finally:
        if robot.is_connected:
            robot.disconnect()


if __name__ == "__main__":
    main()
