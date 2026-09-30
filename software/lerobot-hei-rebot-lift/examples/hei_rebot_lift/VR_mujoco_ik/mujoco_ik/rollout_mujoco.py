#!/usr/bin/env python
"""Run a LeRobot policy against an independently running HEI MuJoCo server.

Run this client in lerobot5. The process imports no MuJoCo modules.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch
import zmq

from lerobot.common.control_utils import predict_action
from lerobot.configs import PreTrainedConfig
from lerobot.policies import get_policy_class, make_pre_post_processors
from lerobot.policies.utils import make_robot_action
from lerobot.utils.constants import ACTION, OBS_STR
from lerobot.utils.feature_utils import build_dataset_frame, hw_to_dataset_features

from hei_robot_mujoco_zmq_protocol import (
    DEFAULT_COMMAND_PORT,
    DEFAULT_OBSERVATION_PORT,
    OBSERVATION_TOPIC,
    ROBOT_TYPE,
    STATE_NAMES,
    decode_observation_packet,
    observation_feature_types,
    safe_hold_action,
    state_feature_types,
    tcp_endpoint,
)


DEFAULT_TASK = "Pick up the red cube with the right gripper and place it in the center of the table."


def resolve_model_id(model_id: str) -> str:
    path = Path(model_id).expanduser()
    if path.is_dir() and (path / "config.json").is_file():
        return str(path.resolve())
    checkpoints = path / "checkpoints"
    if checkpoints.is_dir():
        candidates = sorted(
            candidate / "pretrained_model"
            for candidate in checkpoints.iterdir()
            if candidate.is_dir() and (candidate / "pretrained_model" / "config.json").is_file()
        )
        if candidates:
            return str(candidates[-1].resolve())
    return model_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a LeRobot policy through the HEI MuJoCo ZMQ server.")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--duration-sec", type=float, default=30.0)
    parser.add_argument("--fps", type=float, default=30.0, help="Expected simulation observation rate.")
    parser.add_argument("--device", default=None)
    parser.add_argument("--sim-ip", default="127.0.0.1", help="Computer running MuJoCo.")
    parser.add_argument("--observation-port", type=int, default=DEFAULT_OBSERVATION_PORT)
    parser.add_argument("--command-port", type=int, default=DEFAULT_COMMAND_PORT)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.duration_sec < 0.0:
        parser.error("--duration-sec must be non-negative")
    if args.fps <= 0.0:
        parser.error("--fps must be positive")
    return args


def dataset_features() -> dict:
    return {
        **hw_to_dataset_features(state_feature_types(), ACTION),
        **hw_to_dataset_features(observation_feature_types(), OBS_STR),
    }


def load_policy(model_id: str, device_override: str | None):
    resolved_id = resolve_model_id(model_id)
    config = PreTrainedConfig.from_pretrained(resolved_id)
    device = torch.device(device_override or config.device)
    config.device = str(device)
    config.pretrained_path = resolved_id
    policy_class = get_policy_class(config.type)
    policy = policy_class.from_pretrained(resolved_id, config=config).to(device)
    policy.eval()
    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=config,
        pretrained_path=resolved_id,
        preprocessor_overrides={"device_processor": {"device": str(device)}},
    )
    return policy, config, device, preprocessor, postprocessor, resolved_id


class SimulationClient:
    def __init__(self, args: argparse.Namespace) -> None:
        self.context = zmq.Context()
        self.observation_socket = self.context.socket(zmq.SUB)
        self.observation_socket.setsockopt(zmq.SUBSCRIBE, OBSERVATION_TOPIC.encode("utf-8"))
        self.observation_socket.setsockopt(zmq.RCVHWM, 1)
        self.observation_socket.connect(tcp_endpoint(args.sim_ip, args.observation_port))
        self.command_socket = self.context.socket(zmq.PUSH)
        self.command_socket.setsockopt(zmq.SNDHWM, 2)
        self.command_socket.connect(tcp_endpoint(args.sim_ip, args.command_port))
        self.poller = zmq.Poller()
        self.poller.register(self.observation_socket, zmq.POLLIN)

    def receive_latest(self, timeout_ms: int = 1000):
        if self.observation_socket not in dict(self.poller.poll(timeout_ms)):
            return None
        parts = self.observation_socket.recv_multipart()
        while self.observation_socket in dict(self.poller.poll(0)):
            parts = self.observation_socket.recv_multipart()
        return decode_observation_packet(parts)

    def send(self, command_type: str, **payload) -> None:
        self.command_socket.send_json({"type": command_type, **payload})

    def close(self) -> None:
        self.observation_socket.close(0)
        self.command_socket.close(0)
        self.context.term()


def serializable_action(action: dict) -> dict[str, float]:
    missing = [name for name in STATE_NAMES if name not in action]
    if missing:
        raise ValueError(f"Policy output is missing action fields: {missing}")
    return {name: float(action[name]) for name in STATE_NAMES}


def requested_action_fields(action: dict[str, float], observation: dict) -> list[str]:
    """Return fields that currently request visible motion instead of a hold."""
    requested = []
    for name in STATE_NAMES:
        if name in ("x.vel", "y.vel", "theta.vel"):
            magnitude = abs(action[name])
            threshold = 1e-3
        else:
            magnitude = abs(action[name] - float(observation[name]))
            threshold = 0.5 if name == "height.pos" else 1e-3
        if magnitude > threshold:
            requested.append(name)
    return requested


def main() -> None:
    args = parse_args()
    policy, policy_config, device, preprocessor, postprocessor, resolved_id = load_policy(
        args.model_id,
        args.device,
    )
    features = dataset_features()
    client = SimulationClient(args)
    last_observation = None
    last_sequence = None
    warned_fps = False
    started_s = None
    inference_count = 0
    hold_action_started_s = None
    warned_hold_action = False
    policy_ever_requested_motion = False
    last_requested_fields: list[str] = []
    policy.reset()
    print(
        f"[HEI Sim Rollout] policy={resolved_id}, type={policy_config.type}, device={device}",
        flush=True,
    )
    print("[HEI Sim Rollout] waiting for the independent policy simulation server", flush=True)
    try:
        while True:
            packet = client.receive_latest()
            if packet is None:
                print(
                    "[HEI Sim Rollout] no simulation frame; "
                    "check the policy simulation process and ports",
                    flush=True,
                )
                continue
            metadata, observation, _ = packet
            if metadata.get("source_mode") != "policy":
                raise RuntimeError(
                    "The simulation server is in VR mode. Start run_hei_robot_policy_sim.sh for rollout."
                )
            source_fps = float(metadata.get("publish_fps", 0.0))
            if not warned_fps and abs(source_fps - args.fps) > 0.1:
                print(
                    f"[HEI Sim Rollout] WARNING: server publishes {source_fps:g} Hz, expected {args.fps:g} Hz",
                    flush=True,
                )
                warned_fps = True
            client.send("reset")
            print(
                f"[HEI Sim Rollout] connected, sequence={metadata['sequence']}, "
                f"publish_fps={source_fps:g}",
                flush=True,
            )
            break

        started_s = time.monotonic()
        while args.duration_sec == 0.0 or time.monotonic() - started_s < args.duration_sec:
            packet = client.receive_latest()
            if packet is None:
                print("[HEI Sim Rollout] waiting for simulation frames", flush=True)
                continue
            metadata, observation, _ = packet
            if metadata.get("source_mode") != "policy":
                raise RuntimeError("Simulation source changed from policy to VR during rollout")
            sequence = int(metadata["sequence"])
            if last_sequence is not None and sequence > last_sequence + 1 and args.verbose:
                print(
                    f"[HEI Sim Rollout] skipped {sequence - last_sequence - 1} stale observation frames",
                    flush=True,
                )
            last_sequence = sequence
            last_observation = observation

            observation_frame = build_dataset_frame(features, observation, prefix=OBS_STR)
            action_tensor = predict_action(
                observation=observation_frame,
                policy=policy,
                device=device,
                preprocessor=preprocessor,
                postprocessor=postprocessor,
                use_amp=device.type == "cuda" and bool(getattr(policy_config, "use_amp", False)),
                task=args.task,
                robot_type=ROBOT_TYPE,
            )
            action = serializable_action(make_robot_action(action_tensor, features))
            last_requested_fields = requested_action_fields(action, observation)
            now_s = time.monotonic()
            if last_requested_fields:
                policy_ever_requested_motion = True
                hold_action_started_s = None
            elif hold_action_started_s is None:
                hold_action_started_s = now_s
            elif (
                not policy_ever_requested_motion
                and not warned_hold_action
                and now_s - hold_action_started_s >= 3.0
            ):
                print(
                    "[HEI Sim Rollout] WARNING: the policy has requested only hold actions "
                    "for 3 seconds. Check dataset action ranges and confirm the recorded "
                    "arm/task match the rollout instruction.",
                    flush=True,
                )
                warned_hold_action = True
            client.send("policy_action", sequence=sequence, action=action)
            inference_count += 1
            if args.verbose:
                print(f"[HEI Sim Rollout] sequence={sequence}, action={action}", flush=True)
            elif inference_count % max(1, int(args.fps * 5)) == 0:
                elapsed_s = time.monotonic() - started_s
                print(
                    f"[HEI Sim Rollout] actions={inference_count}, "
                    f"average={inference_count / max(elapsed_s, 1e-6):.1f} Hz, "
                    f"requested={','.join(last_requested_fields) if last_requested_fields else 'hold'}",
                    flush=True,
                )
    except KeyboardInterrupt:
        print("[HEI Sim Rollout] interrupted by user", flush=True)
    finally:
        if last_observation is not None:
            client.send("policy_action", action=safe_hold_action(last_observation))
        client.send("stop")
        client.close()
        print("[HEI Sim Rollout] stopped", flush=True)


if __name__ == "__main__":
    main()
