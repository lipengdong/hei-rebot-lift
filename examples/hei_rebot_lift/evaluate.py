#!/usr/bin/env python

import argparse
import logging
import time

import torch

from lerobot.common.control_utils import init_keyboard_listener, predict_action
from lerobot.datasets import LeRobotDataset
from lerobot.policies import make_pre_post_processors
from lerobot.policies.act import ACTPolicy
from lerobot.policies.utils import make_robot_action
from lerobot.processor import make_default_processors
from lerobot.robots.hei_rebot_lift import HeiRebotLiftClient, HeiRebotLiftClientConfig
from lerobot.utils.constants import ACTION, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, hw_to_dataset_features
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import log_say
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data

NUM_EPISODES = 2
FPS = 30
EPISODE_TIME_SEC = 60
TASK_DESCRIPTION = "My task description"
HF_MODEL_ID = "<hf_username>/<model_repo_id>"
HF_DATASET_ID = "<hf_username>/<eval_dataset_repo_id>"
REMOTE_IP = "192.168.31.127"
ROBOT_ID = "hei_rebot_lift"


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate an ACT policy on HEI ReBot Lift and record data.")
    parser.add_argument("--model-id", type=str, default=HF_MODEL_ID, help="Pretrained policy repo id/path.")
    parser.add_argument("--dataset-id", type=str, default=HF_DATASET_ID, help="Eval dataset repo id.")
    parser.add_argument("--root", type=str, default=None, help="Local dataset root.")
    parser.add_argument("--num-episodes", type=int, default=NUM_EPISODES)
    parser.add_argument("--episode-time-sec", type=float, default=EPISODE_TIME_SEC)
    parser.add_argument("--task-description", type=str, default=TASK_DESCRIPTION)
    parser.add_argument("--remote-ip", type=str, default=REMOTE_IP)
    parser.add_argument("--robot-id", type=str, default=ROBOT_ID)
    # 默认只保存到本地，需要同步到 Hugging Face 时再显式加 --push-to-hub。
    parser.add_argument("--push-to-hub", dest="push_to_hub", action="store_true", default=False)
    parser.add_argument("--no-push-to-hub", dest="push_to_hub", action="store_false")
    parser.add_argument("--private", action="store_true", help="Push eval dataset as private.")
    return parser.parse_args()


def main():
    args = parse_args()

    robot_config = HeiRebotLiftClientConfig(remote_ip=args.remote_ip, id=args.robot_id)
    robot = HeiRebotLiftClient(robot_config)

    policy = ACTPolicy.from_pretrained(args.model_id)
    device = torch.device(policy.config.device)

    action_features = hw_to_dataset_features(robot.action_features, ACTION)
    obs_features = hw_to_dataset_features(robot.observation_features, OBS_STR)
    dataset_features = {**action_features, **obs_features}

    dataset = LeRobotDataset.create(
        repo_id=args.dataset_id,
        fps=FPS,
        root=args.root,
        features=dataset_features,
        robot_type=robot.name,
        use_videos=True,
        image_writer_threads=4 * len(robot.config.cameras),
    )

    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy,
        pretrained_path=args.model_id,
        dataset_stats=dataset.meta.stats,
        preprocessor_overrides={"device_processor": {"device": str(policy.config.device)}},
    )

    robot.connect()
    _, robot_action_processor, robot_observation_processor = make_default_processors()

    listener, events = init_keyboard_listener()
    init_rerun(session_name="hei_rebot_lift_evaluate")

    try:
        if not robot.is_connected:
            raise ValueError("Robot is not connected!")

        print("Starting HEI ReBot Lift evaluate loop...")
        control_interval = 1 / FPS
        recorded_episodes = 0
        while recorded_episodes < args.num_episodes and not events["stop_recording"]:
            log_say(f"Running inference, recording eval episode {recorded_episodes} of {args.num_episodes}")

            timestamp = 0
            start_episode_t = time.perf_counter()
            while timestamp < args.episode_time_sec:
                start_loop_t = time.perf_counter()

                if events["exit_early"]:
                    events["exit_early"] = False
                    break

                obs = robot.get_observation()
                obs_processed = robot_observation_processor(obs)
                observation_frame = build_dataset_frame(dataset.features, obs_processed, prefix=OBS_STR)

                action_tensor = predict_action(
                    observation=observation_frame,
                    policy=policy,
                    device=device,
                    preprocessor=preprocessor,
                    postprocessor=postprocessor,
                    use_amp=device.type == "cuda" and policy.config.use_amp,
                    task=args.task_description,
                    robot_type=robot.name,
                )

                action_values = make_robot_action(action_tensor, dataset.features)
                # 策略输出已经是目标动作，这里只做默认处理器转换，再发给机器人端。
                robot_action_to_send = robot_action_processor((action_values, obs))
                robot.send_action(robot_action_to_send)

                action_frame = build_dataset_frame(dataset.features, action_values, prefix=ACTION)
                frame = {**observation_frame, **action_frame, "task": args.task_description}
                dataset.add_frame(frame)

                log_rerun_data(observation=obs_processed, action=action_values)

                dt_s = time.perf_counter() - start_loop_t
                sleep_time_s = control_interval - dt_s
                if sleep_time_s < 0:
                    logging.warning(
                        f"Evaluate loop is running slower ({1 / dt_s:.1f} Hz) than the target FPS ({FPS} Hz)."
                    )
                precise_sleep(max(sleep_time_s, 0.0))
                timestamp = time.perf_counter() - start_episode_t

            if not events["stop_recording"] and (
                (recorded_episodes < args.num_episodes - 1) or events["rerecord_episode"]
            ):
                log_say("Reset the environment")
                log_say("Waiting for environment reset, press right arrow key when ready...")

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
        if robot.is_connected:
            robot.disconnect()
        listener.stop()

        dataset.finalize()
        if args.push_to_hub:
            dataset.push_to_hub(private=args.private)


if __name__ == "__main__":
    main()
