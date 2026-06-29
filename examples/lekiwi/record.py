# !/usr/bin/env python

# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

import argparse
import time

from lerobot.common.control_utils import init_keyboard_listener, sanity_check_dataset_robot_compatibility
from lerobot.datasets import LeRobotDataset
from lerobot.processor import make_default_processors
from lerobot.robots.lekiwi import LeKiwiClient, LeKiwiClientConfig
from lerobot.utils.constants import ACTION, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, hw_to_dataset_features
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import log_say
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data

from vr_control import VRActionReceiver

NUM_EPISODES = 50
FPS = 30
EPISODE_TIME_SEC = 30
RESET_TIME_SEC = 10
TASK_DESCRIPTION = "My task description"
HF_REPO_ID = "HGM/act_lekiwi"
REMOTE_IP = "192.168.31.28"
ROBOT_ID = "my_lekiwi"


def parse_args():
    parser = argparse.ArgumentParser(description="Record a LeKiwi dataset from VR actions over ZMQ.")
    parser.add_argument("--num-episodes", type=int, default=NUM_EPISODES, help="Number of new episodes.")
    parser.add_argument("--episode-time-sec", type=float, default=EPISODE_TIME_SEC, help="Seconds per episode.")
    parser.add_argument("--reset-time-sec", type=float, default=RESET_TIME_SEC, help="Seconds between episodes.")
    parser.add_argument("--task-description", type=str, default=TASK_DESCRIPTION, help="Task text per frame.")
    parser.add_argument("--repo-id", type=str, default=HF_REPO_ID, help="Hugging Face dataset repo id.")
    parser.add_argument("--root", type=str, default=None, help="Local dataset root.")
    parser.add_argument("--resume", action="store_true", help="Continue recording into an existing dataset.")
    parser.add_argument("--remote-ip", type=str, default=REMOTE_IP, help="LeKiwi host IP address.")
    parser.add_argument("--robot-id", type=str, default=ROBOT_ID, help="LeKiwi robot id.")
    parser.add_argument("--image-writer-threads", type=int, default=4, help="Image writer threads.")
    parser.add_argument("--push-to-hub", dest="push_to_hub", action="store_true", default=True)
    parser.add_argument("--no-push-to-hub", dest="push_to_hub", action="store_false")
    parser.add_argument("--private", action="store_true", help="Push dataset as private.")
    return parser.parse_args()


def complete_action_for_dataset(action, dataset):
    action_names = dataset.features[ACTION]["names"]
    return {name: float(action.get(name, 0.0)) for name in action_names}


def record_vr_loop(
    robot,
    events,
    fps,
    teleop_action_processor,
    robot_action_processor,
    robot_observation_processor,
    vr_receiver,
    dataset=None,
    control_time_s=None,
    single_task=None,
    display_data=False,
):
    if dataset is not None and dataset.fps != fps:
        raise ValueError(f"The dataset fps should be equal to requested fps ({dataset.fps} != {fps}).")

    timestamp = 0
    start_episode_t = time.perf_counter()
    while timestamp < control_time_s:
        start_loop_t = time.perf_counter()

        if events["exit_early"]:
            events["exit_early"] = False
            break

        obs = robot.get_observation()
        obs_processed = robot_observation_processor(obs)
        observation_frame = (
            build_dataset_frame(dataset.features, obs_processed, prefix=OBS_STR) if dataset is not None else None
        )

        action = vr_receiver.get_action()
        if not action:
            precise_sleep(max(1.0 / fps - (time.perf_counter() - start_loop_t), 0.0))
            timestamp = time.perf_counter() - start_episode_t
            continue

        action_values = teleop_action_processor((action, obs))
        robot_action_to_send = robot_action_processor((action_values, obs))
        _ = robot.send_action(robot_action_to_send)

        if dataset is not None:
            dataset_action = complete_action_for_dataset(action_values, dataset)
            action_frame = build_dataset_frame(dataset.features, dataset_action, prefix=ACTION)
            frame = {**observation_frame, **action_frame, "task": single_task}
            dataset.add_frame(frame)

        if display_data:
            log_rerun_data(observation=obs_processed, action=action_values)

        precise_sleep(max(1.0 / fps - (time.perf_counter() - start_loop_t), 0.0))
        timestamp = time.perf_counter() - start_episode_t


def main():
    args = parse_args()

    robot_config = LeKiwiClientConfig(remote_ip=args.remote_ip, id=args.robot_id)
    robot = LeKiwiClient(robot_config)
    vr_receiver = VRActionReceiver()

    teleop_action_processor, robot_action_processor, robot_observation_processor = make_default_processors()

    action_features = hw_to_dataset_features(robot.action_features, ACTION)
    obs_features = hw_to_dataset_features(robot.observation_features, OBS_STR)
    dataset_features = {**action_features, **obs_features}

    if args.resume:
        if args.root is None:
            raise ValueError("--resume requires --root with the latest LeRobot dataset writer.")
        dataset = LeRobotDataset.resume(
            args.repo_id,
            root=args.root,
            image_writer_threads=args.image_writer_threads * len(robot.config.cameras),
        )
        sanity_check_dataset_robot_compatibility(dataset, robot, FPS, dataset_features)
    else:
        dataset = LeRobotDataset.create(
            repo_id=args.repo_id,
            fps=FPS,
            root=args.root,
            features=dataset_features,
            robot_type=robot.name,
            use_videos=True,
            image_writer_threads=args.image_writer_threads * len(robot.config.cameras),
        )

    vr_receiver.start()
    robot.connect()

    listener, events = init_keyboard_listener()
    init_rerun(session_name="lekiwi_record")

    try:
        if not robot.is_connected:
            raise ValueError("Robot is not connected!")

        print("Starting VR record loop...")
        vr_receiver.wait_for_arm_action()
        recorded_episodes = 0
        while recorded_episodes < args.num_episodes and not events["stop_recording"]:
            log_say(f"Recording episode {dataset.num_episodes}")

            record_vr_loop(
                robot=robot,
                events=events,
                fps=FPS,
                dataset=dataset,
                vr_receiver=vr_receiver,
                control_time_s=args.episode_time_sec,
                single_task=args.task_description,
                display_data=True,
                teleop_action_processor=teleop_action_processor,
                robot_action_processor=robot_action_processor,
                robot_observation_processor=robot_observation_processor,
            )

            if not events["stop_recording"] and (
                (recorded_episodes < args.num_episodes - 1) or events["rerecord_episode"]
            ):
                log_say("Reset the environment")
                record_vr_loop(
                    robot=robot,
                    events=events,
                    fps=FPS,
                    vr_receiver=vr_receiver,
                    control_time_s=args.reset_time_sec,
                    single_task=args.task_description,
                    display_data=True,
                    teleop_action_processor=teleop_action_processor,
                    robot_action_processor=robot_action_processor,
                    robot_observation_processor=robot_observation_processor,
                )

            if events["rerecord_episode"]:
                log_say("Re-record episode")
                events["rerecord_episode"] = False
                events["exit_early"] = False
                dataset.clear_episode_buffer()
                continue

            dataset.save_episode()
            recorded_episodes += 1
    finally:
        log_say("Stop recording")
        vr_receiver.stop()
        if robot.is_connected:
            robot.disconnect()
        listener.stop()

        dataset.finalize()
        if args.push_to_hub:
            dataset.push_to_hub(private=args.private)


if __name__ == "__main__":
    main()
