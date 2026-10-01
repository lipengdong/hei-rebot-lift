#!/usr/bin/env python
"""Asynchronously render and publish HEI MuJoCo observation snapshots."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

import zmq

from hei_robot_mujoco_dataset_adapter import HEIMujocoSnapshotRenderer, SimulationSnapshot
from hei_robot_mujoco_zmq_protocol import encode_observation_packet


@dataclass(frozen=True)
class ObservationSample:
    snapshot: SimulationSnapshot
    action: dict[str, float]
    timestamp_s: float


class AsyncObservationPublisher:
    """Keep camera rendering/JPEG/ZMQ work out of the robot control loop."""

    def __init__(
        self,
        simulator,
        *,
        endpoint: str,
        topic: str,
        source_mode: str,
        publish_fps: float,
        jpeg_quality: int,
        width: int,
        height: int,
    ) -> None:
        self.simulator = simulator
        self.endpoint = endpoint
        self.topic = topic
        self.source_mode = source_mode
        self.publish_fps = float(publish_fps)
        self.jpeg_quality = int(jpeg_quality)
        self.width = int(width)
        self.height = int(height)

        # 只保留最新快照。渲染落后时宁可丢帧，也不回放过期的机器人状态。
        self._samples: queue.Queue[ObservationSample] = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._stats_lock = threading.Lock()
        self._sequence = 0
        self._dropped_snapshots = 0
        self._dropped_network_packets = 0
        self._error: BaseException | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="hei-mujoco-observation-publisher",
            daemon=True,
        )

    def start(self, timeout_s: float = 30.0) -> None:
        self._thread.start()
        if not self._ready_event.wait(timeout=max(float(timeout_s), 0.1)):
            raise RuntimeError("Timed out while starting the MuJoCo observation publisher")
        self.raise_if_failed()

    def submit(
        self,
        snapshot: SimulationSnapshot,
        action: dict[str, float],
        timestamp_s: float,
    ) -> None:
        self.raise_if_failed()
        sample = ObservationSample(
            snapshot=snapshot,
            action=dict(action),
            timestamp_s=float(timestamp_s),
        )
        try:
            self._samples.put_nowait(sample)
            return
        except queue.Full:
            pass

        try:
            self._samples.get_nowait()
        except queue.Empty:
            pass
        with self._stats_lock:
            self._dropped_snapshots += 1
        try:
            self._samples.put_nowait(sample)
        except queue.Full:
            # 极小概率下工作线程刚好与本线程竞争队列；下一采样周期会继续提交。
            with self._stats_lock:
                self._dropped_snapshots += 1

    def stats(self) -> tuple[int, int, int]:
        with self._stats_lock:
            return (
                self._sequence,
                self._dropped_snapshots,
                self._dropped_network_packets,
            )

    def raise_if_failed(self) -> None:
        if self._error is not None:
            raise RuntimeError("MuJoCo observation publisher stopped unexpectedly") from self._error

    def _run(self) -> None:
        context = None
        socket = None
        renderer = None
        try:
            # Renderer 在此线程中创建并始终由此线程使用，避免 OpenGL 上下文跨线程。
            renderer = HEIMujocoSnapshotRenderer(
                self.simulator.model_path,
                add_environment=self.simulator.scene_enabled,
                width=self.width,
                height=self.height,
            )
            context = zmq.Context()
            socket = context.socket(zmq.PUB)
            socket.setsockopt(zmq.SNDHWM, 2)
            socket.bind(self.endpoint)
            self._ready_event.set()

            while not self._stop_event.is_set():
                try:
                    sample = self._samples.get(timeout=0.1)
                except queue.Empty:
                    continue

                # submit() 已经限制队列长度，这里再次清空可覆盖刚到达的新快照。
                while True:
                    try:
                        sample = self._samples.get_nowait()
                        with self._stats_lock:
                            self._dropped_snapshots += 1
                    except queue.Empty:
                        break

                observation = renderer.render(sample.snapshot)
                with self._stats_lock:
                    sequence = self._sequence
                packet = encode_observation_packet(
                    topic=self.topic,
                    sequence=sequence,
                    timestamp_s=sample.timestamp_s,
                    source_mode=self.source_mode,
                    publish_fps=self.publish_fps,
                    observation=observation,
                    action=sample.action,
                    jpeg_quality=self.jpeg_quality,
                )
                try:
                    socket.send_multipart(packet, flags=zmq.NOBLOCK, copy=False)
                except zmq.Again:
                    with self._stats_lock:
                        self._dropped_network_packets += 1
                else:
                    with self._stats_lock:
                        self._sequence += 1
        except BaseException as exc:
            self._error = exc
            self._ready_event.set()
        finally:
            if renderer is not None:
                try:
                    renderer.close()
                except Exception:
                    pass
            if socket is not None:
                try:
                    socket.close(0)
                except Exception:
                    pass
            if context is not None:
                try:
                    context.term()
                except Exception:
                    pass

    def close(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)
        if self._thread.is_alive():
            raise RuntimeError("MuJoCo observation publisher did not stop within 5 seconds")
