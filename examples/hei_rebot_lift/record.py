#!/usr/bin/env python

import argparse
import time

from lerobot.common.control_utils import init_keyboard_listener, sanity_check_dataset_robot_compatibility
from lerobot.datasets import LeRobotDataset
from lerobot.processor import make_default_processors
from lerobot.robots.hei_rebot_lift import HeiRebotLiftClient, HeiRebotLiftClientConfig
from lerobot.utils.constants import ACTION, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, hw_to_dataset_features
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import log_say
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data

from vr_control import VRActionReceiver

NUM_EPISODES = 5
FPS = 30
EPISODE_TIME_SEC = 120
RESET_TIME_SEC = 30
TASK_DESCRIPTION = "Pick up the yellow block from the floor and put it on the table in front"
# TASK_DESCRIPTION = "My task description"
HF_REPO_ID = "HGM/hei_rebot_lift"
REMOTE_IP = "192.168.31.127"
ROBOT_ID = "hei_rebot_lift"
PROGRESS_INTERVAL_SEC = 5.0


def print_status(message: str) -> None:
    print(f"[HEI Record] {message}", flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Record a HEI ReBot Lift dataset from VR actions.")
    parser.add_argument("--num-episodes", type=int, default=NUM_EPISODES, help="Number of new episodes.")
    parser.add_argument("--episode-time-sec", type=float, default=EPISODE_TIME_SEC, help="Seconds per episode.")
    parser.add_argument("--reset-time-sec", type=float, default=RESET_TIME_SEC, help="Seconds between episodes.")
    parser.add_argument("--task-description", type=str, default=TASK_DESCRIPTION, help="Task text per frame.")
    parser.add_argument("--repo-id", type=str, default=HF_REPO_ID, help="Hugging Face dataset repo id.")
    parser.add_argument("--root", type=str, default=None, help="Local dataset root.")
    parser.add_argument("--resume", action="store_true", help="Continue recording into an existing dataset.")
    parser.add_argument("--remote-ip", type=str, default=REMOTE_IP, help="HEI ReBot Lift host IP address.")
    parser.add_argument("--robot-id", type=str, default=ROBOT_ID, help="HEI ReBot Lift robot id.")
    parser.add_argument("--image-writer-threads", type=int, default=4, help="Image writer threads per camera.")
    parser.add_argument(
        "--progress-interval-sec",
        type=float,
        default=PROGRESS_INTERVAL_SEC,
        help="Seconds between recording progress logs.",
    )
    # 默认只保存到本地，避免实机录制结束后因为网络/代理问题影响数据落盘。
    parser.add_argument("--push-to-hub", dest="push_to_hub", action="store_true", default=False)
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
    phase_name="record",
    progress_interval_s=PROGRESS_INTERVAL_SEC,
):
    if dataset is not None and dataset.fps != fps:
        raise ValueError(f"The dataset fps should be equal to requested fps ({dataset.fps} != {fps}).")

    timestamp = 0
    saved_frames = 0
    start_episode_t = time.perf_counter()
    last_progress_t = start_episode_t
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

        # 升降目标需要基于机器人真实 height.pos 计算，所以这里必须把 obs 传给 VRActionReceiver。
        action = vr_receiver.get_action(obs)
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
            saved_frames += 1

        if display_data:
            log_rerun_data(observation=obs_processed, action=action_values)

        now = time.perf_counter()
        if progress_interval_s > 0 and now - last_progress_t >= progress_interval_s:
            # 实机录制时最怕“不知道程序在干嘛”，这里定期打印本阶段进度。
            print_status(
                f"{phase_name}: {timestamp:.1f}/{control_time_s:.1f}s, "
                f"saved_frames={saved_frames if dataset is not None else 0}"
            )
            last_progress_t = now

        precise_sleep(max(1.0 / fps - (time.perf_counter() - start_loop_t), 0.0))
        timestamp = time.perf_counter() - start_episode_t

    print_status(
        f"{phase_name} finished: {min(timestamp, control_time_s):.1f}/{control_time_s:.1f}s, "
        f"saved_frames={saved_frames if dataset is not None else 0}"
    )
    return saved_frames


def main():
    args = parse_args()
    print_status(
        f"Starting with repo_id={args.repo_id}, episodes={args.num_episodes}, "
        f"episode_time={args.episode_time_sec}s, reset_time={args.reset_time_sec}s, "
        f"push_to_hub={args.push_to_hub}"
    )

    robot_config = HeiRebotLiftClientConfig(remote_ip=args.remote_ip, id=args.robot_id)
    robot = HeiRebotLiftClient(robot_config)
    vr_receiver = VRActionReceiver()

    teleop_action_processor, robot_action_processor, robot_observation_processor = make_default_processors()

    action_features = hw_to_dataset_features(robot.action_features, ACTION)
    obs_features = hw_to_dataset_features(robot.observation_features, OBS_STR)
    dataset_features = {**action_features, **obs_features}

    if args.resume:
        if args.root is None:
            raise ValueError("--resume requires --root with the latest LeRobot dataset writer.")
        print_status(f"Resuming local dataset at root={args.root}")
        dataset = LeRobotDataset.resume(
            args.repo_id,
            root=args.root,
            image_writer_threads=args.image_writer_threads * len(robot.config.cameras),
        )
        sanity_check_dataset_robot_compatibility(dataset, robot, FPS, dataset_features)
    else:
        print_status(f"Creating local dataset; root={args.root or 'default HF_LEROBOT_HOME/repo_id'}")
        dataset = LeRobotDataset.create(
            repo_id=args.repo_id,
            fps=FPS,
            root=args.root,
            features=dataset_features,
            robot_type=robot.name,
            use_videos=True,
            image_writer_threads=args.image_writer_threads * len(robot.config.cameras),
        )
    print_status(f"Dataset ready at {dataset.root}")

    print_status("Starting VR ZMQ receiver")
    vr_receiver.start()
    print_status(f"Connecting robot client to {args.remote_ip}")
    robot.connect()
    print_status("Robot connected")

    listener, events = init_keyboard_listener()
    init_rerun(session_name="hei_rebot_lift_record")

    try:
        if not robot.is_connected:
            raise ValueError("Robot is not connected!")

        first_obs = robot.get_observation()
        vr_receiver.set_height_from_observation(first_obs)
        print_status(f"Initial lift height: {float(first_obs.get('height.pos', 0.0)):.1f} mm")

        print_status("Waiting for first VR arm action from MuJoCo/VR")
        vr_receiver.wait_for_arm_action()
        print_status("VR arm action received, recording loop starts")
        recorded_episodes = 0
        while recorded_episodes < args.num_episodes and not events["stop_recording"]:
            episode_index = dataset.num_episodes
            log_say(f"Recording episode {episode_index}")
            print_status(f"Episode {recorded_episodes + 1}/{args.num_episodes} started (dataset episode {episode_index})")

            saved_frames = record_vr_loop(
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
                phase_name=f"episode {recorded_episodes + 1}/{args.num_episodes}",
                progress_interval_s=args.progress_interval_sec,
            )
            print_status(f"Episode {recorded_episodes + 1}/{args.num_episodes} control loop done, frames={saved_frames}")

            if not events["stop_recording"] and (
                (recorded_episodes < args.num_episodes - 1) or events["rerecord_episode"]
            ):
                log_say("Reset the environment")
                print_status(f"Reset phase started for {args.reset_time_sec:.1f}s")
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
                    phase_name="reset",
                    progress_interval_s=args.progress_interval_sec,
                )
                print_status("Reset phase finished")

            if events["rerecord_episode"]:
                log_say("Re-record episode")
                print_status(f"Discarding episode buffer for dataset episode {episode_index}")
                events["rerecord_episode"] = False
                events["exit_early"] = False
                dataset.clear_episode_buffer()
                continue

            if saved_frames <= 0:
                # 没有收到可保存的 VR action 时，LeRobot 不允许保存空 episode。
                # 这里跳过本集，避免整次录制因为一次空包/误触提前退出而中断。
                print_status(
                    f"Episode {episode_index} has no saved frames; skipped. "
                    "Check MuJoCo/VR ZMQ if this happens repeatedly."
                )
                events["exit_early"] = False
                dataset.clear_episode_buffer()
                continue

            print_status(f"Saving episode {episode_index} to disk (images/video/data)")
            dataset.save_episode()
            print_status(f"Episode {episode_index} saved")
            recorded_episodes += 1
    finally:
        log_say("Stop recording")
        print_status("Stopping VR receiver")
        vr_receiver.stop()
        if robot.is_connected:
            print_status("Disconnecting robot")
            robot.disconnect()
            print_status("Robot disconnected")
        print_status("Stopping keyboard listener")
        listener.stop()

        print_status("Finalizing dataset (waiting image writer/video encoder/metadata)")
        dataset.finalize()
        print_status(f"Dataset finalized at {dataset.root}")
        if args.push_to_hub:
            print_status("Pushing dataset to Hugging Face Hub")
            dataset.push_to_hub(private=args.private)
            print_status("Push to Hub finished")
        else:
            print_status("Push to Hub skipped")


if __name__ == "__main__":
    main()
