#!/usr/bin/env python
"""Record HEI MuJoCo ZMQ observations as a LeRobotDataset.

Run this client in the lerobot5 environment. MuJoCo runs independently in the
hei-rebot-vr environment and this file deliberately imports no MuJoCo modules.
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import zmq

from lerobot.common.control_utils import init_keyboard_listener
from lerobot.datasets import LeRobotDataset
from lerobot.utils.constants import ACTION, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, hw_to_dataset_features
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data, shutdown_rerun

from hei_robot_mujoco_zmq_protocol import (
    CAMERA_NAMES,
    DEFAULT_COMMAND_PORT,
    DEFAULT_OBSERVATION_PORT,
    OBSERVATION_TOPIC,
    ROBOT_TYPE,
    decode_observation_packet,
    observation_feature_types,
    state_feature_types,
    tcp_endpoint,
)


DEFAULT_REPO_ID = "HGM/hei_rebot_lift_mujoco"
DEFAULT_TASK = "Pick up the red cube with the right gripper and place it in the center of the table."


def print_status(message: str) -> None:
    print(f"[HEI Sim Record] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record HEI MuJoCo data received over ZMQ.")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--num-episodes", type=int, default=10)
    parser.add_argument("--episode-time-sec", type=float, default=30.0)
    parser.add_argument("--reset-time-sec", type=float, default=2.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument(
        "--source-mode",
        choices=("vr", "keyboard"),
        default="vr",
        help="Expected simulation demonstration source.",
    )
    parser.add_argument("--sim-ip", default="127.0.0.1", help="Computer running MuJoCo.")
    parser.add_argument("--observation-port", type=int, default=DEFAULT_OBSERVATION_PORT)
    parser.add_argument("--command-port", type=int, default=DEFAULT_COMMAND_PORT)
    parser.add_argument("--image-writer-threads", type=int, default=4)
    parser.add_argument("--progress-interval-sec", type=float, default=5.0)
    parser.add_argument(
        "--rerun",
        dest="rerun",
        action="store_true",
        default=True,
        help="Show recorded cameras, observations, and actions in Rerun (default: enabled).",
    )
    parser.add_argument(
        "--no-rerun",
        dest="rerun",
        action="store_false",
        help="Disable the live Rerun viewer for headless recording.",
    )
    parser.add_argument(
        "--rerun-compress-images",
        action="store_true",
        help="JPEG-compress images sent to Rerun to reduce viewer memory and bandwidth.",
    )
    parser.add_argument("--push-to-hub", action="store_true")
    parser.add_argument("--private", action="store_true")
    args = parser.parse_args()
    if args.num_episodes <= 0:
        parser.error("--num-episodes must be positive")
    if args.episode_time_sec <= 0.0:
        parser.error("--episode-time-sec must be positive")
    if args.reset_time_sec < 0.0:
        parser.error("--reset-time-sec must be non-negative")
    if args.fps <= 0:
        parser.error("--fps must be positive")
    if args.resume and args.root is None:
        parser.error("--resume requires an explicit --root")
    return args


def dataset_features() -> dict:
    return {
        **hw_to_dataset_features(state_feature_types(), ACTION),
        **hw_to_dataset_features(observation_feature_types(), OBS_STR),
    }


def make_dataset(args: argparse.Namespace) -> LeRobotDataset:
    features = dataset_features()
    writer_threads = args.image_writer_threads * len(CAMERA_NAMES)
    if args.resume:
        dataset = LeRobotDataset.resume(
            args.repo_id,
            root=args.root,
            image_writer_threads=writer_threads,
        )
        if dataset.fps != args.fps:
            raise ValueError(f"Existing dataset FPS is {dataset.fps}, requested {args.fps}")
        for key, expected in features.items():
            actual = dataset.features.get(key)
            compatible = actual is not None and actual.get("dtype") == expected.get("dtype")
            compatible = compatible and tuple(actual.get("shape", ())) == tuple(expected.get("shape", ()))
            compatible = compatible and actual.get("names") == expected.get("names")
            if not compatible:
                raise ValueError(f"Existing dataset feature mismatch at {key}: {actual} != {expected}")
        return dataset
    return LeRobotDataset.create(
        repo_id=args.repo_id,
        fps=args.fps,
        root=args.root,
        features=features,
        robot_type=ROBOT_TYPE,
        use_videos=True,
        image_writer_threads=writer_threads,
    )


class SimulationClient:
    def __init__(self, args: argparse.Namespace) -> None:
        self.context = zmq.Context()
        self.observation_socket = self.context.socket(zmq.SUB)
        self.observation_socket.setsockopt(zmq.SUBSCRIBE, OBSERVATION_TOPIC.encode("utf-8"))
        self.observation_socket.setsockopt(zmq.RCVHWM, 2)
        self.observation_socket.connect(tcp_endpoint(args.sim_ip, args.observation_port))
        self.command_socket = self.context.socket(zmq.PUSH)
        self.command_socket.setsockopt(zmq.SNDHWM, 4)
        self.command_socket.connect(tcp_endpoint(args.sim_ip, args.command_port))
        self.poller = zmq.Poller()
        self.poller.register(self.observation_socket, zmq.POLLIN)

    def receive(self, timeout_ms: int = 1000):
        if self.observation_socket not in dict(self.poller.poll(timeout_ms)):
            return None
        parts = self.observation_socket.recv_multipart()
        # 采集只使用最新同步帧，网络短暂拥塞后不回放过期动作。
        while self.observation_socket in dict(self.poller.poll(0)):
            parts = self.observation_socket.recv_multipart()
        return decode_observation_packet(parts)

    def send(self, command_type: str, **payload) -> None:
        self.command_socket.send_json({"type": command_type, **payload})

    def close(self) -> None:
        self.observation_socket.close(0)
        self.command_socket.close(0)
        self.context.term()


def wait_for_server(client: SimulationClient, source_mode: str):
    print_status(f"Waiting for MuJoCo {source_mode} simulation stream")
    while True:
        packet = client.receive()
        if packet is None:
            print_status(
                f"No simulation frame received yet; check the {source_mode} simulation process and ports"
            )
            continue
        metadata, observation, action = packet
        actual_source = metadata.get("source_mode")
        if actual_source != source_mode:
            expected_script = (
                "run_hei_robot_vr_dataset_sim.sh"
                if source_mode == "vr"
                else "run_hei_robot_keyboard_dataset_sim.sh"
            )
            raise RuntimeError(
                f"Expected source_mode={source_mode!r}, received {actual_source!r}. "
                f"Start {expected_script}."
            )
        print_status(
            f"Connected: sequence={metadata['sequence']}, publish_fps={metadata['publish_fps']}, "
            f"cameras={','.join(CAMERA_NAMES)}"
        )
        return metadata, observation, action


def reset_simulation(client: SimulationClient, reset_time_s: float) -> None:
    client.send("reset")
    print_status(f"Reset requested; waiting {reset_time_s:.1f}s")
    deadline = time.monotonic() + reset_time_s
    while time.monotonic() < deadline:
        client.receive(timeout_ms=min(250, max(1, int((deadline - time.monotonic()) * 1000))))


def record_episode(
    client: SimulationClient,
    dataset: LeRobotDataset,
    events: dict,
    args: argparse.Namespace,
    episode_number: int,
) -> int:
    started_s = time.monotonic()
    last_progress_s = started_s
    last_pause_status_s = 0.0
    last_sequence = None
    saved_frames = 0
    target_frames = max(1, math.ceil(args.episode_time_sec * args.fps))
    warned_fps = False
    stream_paused = False
    while saved_frames < target_frames:
        if events["exit_early"]:
            events["exit_early"] = False
            break
        packet = client.receive()
        if packet is None:
            now_s = time.monotonic()
            pause_log_period_s = max(args.progress_interval_sec, 1.0)
            if not stream_paused or now_s - last_pause_status_s >= pause_log_period_s:
                recorded_s = saved_frames / args.fps
                print_status(
                    "Waiting for simulation frames; recording timer is paused at "
                    f"{recorded_s:.1f}/{args.episode_time_sec:.1f}s, frames={saved_frames}/{target_frames}"
                )
                last_pause_status_s = now_s
            stream_paused = True
            continue
        if stream_paused:
            print_status("Simulation stream resumed; recording timer continues")
            stream_paused = False
        metadata, observation, action = packet
        if metadata.get("source_mode") != args.source_mode:
            raise RuntimeError(
                f"Simulation source changed from {args.source_mode!r} "
                f"to {metadata.get('source_mode')!r} during recording"
            )

        sequence = int(metadata["sequence"])
        if last_sequence is not None and sequence > last_sequence + 1:
            print_status(f"WARNING: dropped {sequence - last_sequence - 1} simulation frames")
        last_sequence = sequence
        source_fps = float(metadata.get("publish_fps", 0.0))
        if not warned_fps and abs(source_fps - args.fps) > 0.1:
            print_status(
                f"WARNING: simulation publishes {source_fps:g} Hz but dataset is {args.fps} Hz; "
                "start both sides with the same FPS"
            )
            warned_fps = True

        observation_frame = build_dataset_frame(dataset.features, observation, prefix=OBS_STR)
        action_frame = build_dataset_frame(dataset.features, action, prefix=ACTION)
        dataset.add_frame({**observation_frame, **action_frame, "task": args.task})
        saved_frames += 1
        if args.rerun:
            # 只显示真正写入数据集的同步样本，确保 Rerun 与落盘内容完全一致。
            log_rerun_data(
                observation=observation,
                action=action,
                compress_images=args.rerun_compress_images,
            )

        now_s = time.monotonic()
        if args.progress_interval_sec > 0.0 and now_s - last_progress_s >= args.progress_interval_sec:
            recorded_s = min(saved_frames / args.fps, args.episode_time_sec)
            wall_elapsed_s = now_s - started_s
            print_status(
                f"episode {episode_number}/{args.num_episodes}: "
                f"{recorded_s:.1f}/{args.episode_time_sec:.1f}s, "
                f"frames={saved_frames}/{target_frames}, "
                f"wall_average={saved_frames / max(wall_elapsed_s, 1e-6):.1f} Hz"
            )
            last_progress_s = now_s
    return saved_frames


def main() -> None:
    args = parse_args()
    dataset = make_dataset(args)
    client = SimulationClient(args)
    listener, events = init_keyboard_listener()
    rerun_initialized = False
    print_status(f"Dataset ready at {dataset.root}")
    print_status("Right arrow: finish episode; left arrow: discard/re-record; Esc: stop")
    try:
        if args.rerun:
            print_status("Starting Rerun live visualization")
            init_rerun(session_name=f"hei_rebot_lift_{args.source_mode}_mujoco_record")
            rerun_initialized = True
        wait_for_server(client, args.source_mode)
        recorded_episodes = 0
        while recorded_episodes < args.num_episodes and not events["stop_recording"]:
            reset_simulation(client, args.reset_time_sec)
            episode_index = dataset.num_episodes
            print_status(
                f"Episode {recorded_episodes + 1}/{args.num_episodes} started "
                f"(dataset episode {episode_index})"
            )
            saved_frames = record_episode(
                client,
                dataset,
                events,
                args,
                recorded_episodes + 1,
            )

            if events["rerecord_episode"]:
                events["rerecord_episode"] = False
                events["exit_early"] = False
                dataset.clear_episode_buffer()
                print_status(f"Episode {episode_index} discarded; recording it again")
                continue
            if saved_frames <= 0:
                dataset.clear_episode_buffer()
                print_status(f"Episode {episode_index} contained no frames and was skipped")
                continue

            print_status(f"Saving episode {episode_index}, frames={saved_frames}")
            dataset.save_episode()
            recorded_episodes += 1
            print_status(f"Episode {episode_index} saved")
    except KeyboardInterrupt:
        print_status("Interrupted by user")
    finally:
        if getattr(dataset, "episode_buffer", None):
            dataset.clear_episode_buffer()
        if listener is not None:
            listener.stop()
        client.close()
        if rerun_initialized:
            print_status("Stopping Rerun visualization")
            shutdown_rerun()
        print_status("Finalizing dataset")
        dataset.finalize()
        print_status(f"Dataset finalized at {dataset.root}")
        if args.push_to_hub:
            dataset.push_to_hub(private=args.private)
            print_status("Hub upload finished")
        else:
            print_status("Push to Hub skipped")


if __name__ == "__main__":
    main()
