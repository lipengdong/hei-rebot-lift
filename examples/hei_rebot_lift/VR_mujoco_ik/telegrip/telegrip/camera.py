"""ZMQ-backed MJPEG camera streams for the VR view."""

from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Union

import numpy as np
import zmq

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None


@dataclass
class ZmqObservationCameraRuntimeConfig:
    id: str
    name: str
    endpoint: str
    image_key: str
    color_order: str = "rgb"
    socket_type: str = "pull"
    topic: str = ""
    width: int = 640
    height: int = 480
    fps: int = 30
    jpeg_quality: int = 95
    enabled: bool = True


class _CameraSlot:
    def __init__(self, config: ZmqObservationCameraRuntimeConfig):
        self.config = config
        self.latest_jpeg: Optional[bytes] = None
        self.latest_frame_shape: Optional[tuple[int, int]] = None
        self.frame_version = 0
        self.clients = 0
        self.last_error: Optional[str] = None
        self.jpeg_quality = max(60, min(100, int(config.jpeg_quality)))


class ZmqObservationCameraHub:
    """Receive one ZMQ observation stream and expose several image keys."""

    def __init__(self, configs: List[ZmqObservationCameraRuntimeConfig]):
        if not configs:
            raise ValueError("At least one camera config is required")
        self._configs = configs
        self._transport = configs[0]
        self._slots = {config.id: _CameraSlot(config) for config in configs}
        self._lock = threading.Lock()
        self._stream_condition = threading.Condition(self._lock)
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self.start()

    def start(self) -> None:
        if self._capture_thread and self._capture_thread.is_alive():
            return
        self._stop_event.clear()
        self._capture_thread = threading.Thread(target=self._receive_loop, name="zmq-camera-hub", daemon=True)
        self._capture_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
        self._capture_thread = None

    def manager(self, camera_id: str) -> "ZmqObservationCameraManager":
        if camera_id not in self._slots:
            raise KeyError(f"Unknown camera id: {camera_id}")
        return ZmqObservationCameraManager(self, camera_id)

    def _make_socket(self, context: zmq.Context):
        socket_type = self._transport.socket_type.lower()
        if socket_type == "sub":
            socket = context.socket(zmq.SUB)
            socket.setsockopt_string(zmq.SUBSCRIBE, self._transport.topic)
        else:
            socket = context.socket(zmq.PULL)
        socket.setsockopt(zmq.CONFLATE, 1)
        socket.setsockopt(zmq.RCVHWM, 1)
        socket.setsockopt(zmq.RCVTIMEO, 200)
        socket.connect(self._transport.endpoint)
        return socket

    def _receive_loop(self) -> None:
        context = zmq.Context()
        socket = None
        try:
            socket = self._make_socket(context)
            while not self._stop_event.is_set():
                if not any(slot.config.enabled for slot in self._slots.values()):
                    time.sleep(0.2)
                    continue

                try:
                    message = socket.recv_string()
                except zmq.Again:
                    continue
                except Exception as exc:
                    self._set_all_errors(f"ZMQ receive failed: {exc}")
                    time.sleep(0.2)
                    continue

                try:
                    observation = json.loads(self._extract_payload(message))
                except json.JSONDecodeError as exc:
                    self._set_all_errors(f"Invalid observation JSON: {exc}")
                    continue

                for camera_id, slot in self._slots.items():
                    if not slot.config.enabled:
                        continue
                    frame = self._extract_frame(observation, slot.config)
                    if frame is None:
                        self._set_error(camera_id, f"Image key not found or could not decode: {slot.config.image_key}")
                    else:
                        self._store_frame(camera_id, frame)
        finally:
            if socket is not None:
                socket.close(0)
            context.term()

    def _extract_payload(self, message: str) -> str:
        config = self._transport
        if config.socket_type.lower() == "sub" and config.topic and message.startswith(config.topic + " "):
            return message.split(" ", 1)[1]
        return message

    def _extract_frame(self, observation: dict, config: ZmqObservationCameraRuntimeConfig) -> Optional[np.ndarray]:
        image_value = self._find_image_value(observation, config.image_key)
        if image_value is None:
            return None

        frame = self._decode_image_value(image_value)
        if frame is None:
            return None

        if frame.ndim == 2:
            frame = np.repeat(frame[:, :, None], 3, axis=2)
        if frame.ndim != 3 or frame.shape[2] not in {3, 4}:
            return None
        if frame.shape[2] == 4 and cv2 is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        if config.color_order.lower() == "rgb" and cv2 is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return frame

    def _find_image_value(self, observation: dict, image_key: str):
        preferred_keys = [
            image_key,
            f"observation.images.{image_key}",
            f"observation.image.{image_key}",
            "observation.image",
        ]

        nested_observation = observation.get("observation")
        if isinstance(nested_observation, dict):
            nested_images = nested_observation.get("images") or nested_observation.get("image")
            if isinstance(nested_images, dict) and image_key in nested_images:
                return nested_images[image_key]
            for key in preferred_keys:
                if key in nested_observation:
                    return nested_observation[key]

        images = observation.get("images") or observation.get("image")
        if isinstance(images, dict) and image_key in images:
            return images[image_key]

        for key in preferred_keys:
            if key in observation:
                return observation[key]
        for key, value in observation.items():
            if image_key in str(key).lower():
                return value
        return None

    def _decode_image_value(self, image_value) -> Optional[np.ndarray]:
        if isinstance(image_value, str):
            if cv2 is None:
                return None
            image_text = image_value.split(",", 1)[1] if image_value.startswith("data:image") else image_value
            try:
                image_bytes = base64.b64decode(image_text)
            except (TypeError, ValueError):
                return None
            np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
            return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if isinstance(image_value, dict) and "data" in image_value and "shape" in image_value:
            array = np.asarray(image_value["data"], dtype=np.uint8)
            return array.reshape(tuple(image_value["shape"]))

        if isinstance(image_value, list):
            return np.asarray(image_value, dtype=np.uint8)

        if isinstance(image_value, np.ndarray):
            return image_value
        return None

    def _store_frame(self, camera_id: str, frame: np.ndarray) -> None:
        if cv2 is None:
            self._set_error(camera_id, "opencv-python-headless is not installed")
            return

        with self._lock:
            slot = self._slots[camera_id]
            jpeg_quality = slot.jpeg_quality

        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
        if not ok:
            self._set_error(camera_id, "Failed to encode ZMQ image frame")
            return

        with self._lock:
            slot = self._slots[camera_id]
            slot.last_error = None
            slot.latest_jpeg = encoded.tobytes()
            slot.latest_frame_shape = (frame.shape[1], frame.shape[0])
            slot.frame_version += 1
            self._stream_condition.notify_all()

    def _set_all_errors(self, message: str) -> None:
        with self._lock:
            for slot in self._slots.values():
                slot.last_error = message
            self._stream_condition.notify_all()

    def _set_error(self, camera_id: str, message: str) -> None:
        with self._lock:
            self._slots[camera_id].last_error = message
            self._stream_condition.notify_all()

    def list_devices(self, camera_id: str) -> List[Dict[str, str]]:
        slot = self._slots[camera_id]
        return [{"path": slot.config.endpoint, "name": f"ZMQ {slot.config.image_key}", "exists": True}]

    def get_status(self, camera_id: str) -> Dict[str, Union[bool, int, str, List[Dict[str, str]], None]]:
        with self._lock:
            slot = self._slots[camera_id]
            latest_shape = slot.latest_frame_shape
            return {
                "id": camera_id,
                "enabled": slot.config.enabled,
                "opencv_available": cv2 is not None,
                "name": slot.config.name,
                "device": slot.config.endpoint,
                "image_key": slot.config.image_key,
                "width": latest_shape[0] if latest_shape else slot.config.width,
                "height": latest_shape[1] if latest_shape else slot.config.height,
                "fps": slot.config.fps,
                "jpeg_quality": slot.jpeg_quality,
                "device_exists": True,
                "devices": self.list_devices(camera_id),
                "last_error": slot.last_error,
                "stream_ready": slot.latest_jpeg is not None,
                "clients": slot.clients,
            }

    def _wait_for_frame(
        self, camera_id: str, last_version: Optional[int] = None, timeout: float = 1.0
    ) -> tuple[Optional[bytes], int]:
        deadline = time.time() + timeout
        with self._lock:
            slot = self._slots[camera_id]
            while not self._stop_event.is_set():
                has_new_frame = slot.latest_jpeg is not None and (
                    last_version is None or slot.frame_version != last_version
                )
                if has_new_frame:
                    return slot.latest_jpeg, slot.frame_version
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._stream_condition.wait(timeout=remaining)

            if slot.latest_jpeg is not None:
                return slot.latest_jpeg, slot.frame_version
        return None, last_version or 0

    def stream_mjpeg(self, camera_id: str) -> Iterable[bytes]:
        last_version = None
        with self._lock:
            self._slots[camera_id].clients += 1
        try:
            while True:
                frame_bytes, last_version = self._wait_for_frame(camera_id, last_version, timeout=1.0)
                if frame_bytes is None:
                    error = self._slots[camera_id].last_error or "ZMQ camera frame not available"
                    yield self._error_frame(error)
                    continue
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Cache-Control: no-cache\r\n\r\n" + frame_bytes + b"\r\n"
                )
        finally:
            with self._lock:
                slot = self._slots[camera_id]
                slot.clients = max(0, slot.clients - 1)

    def get_jpeg_frame(self, camera_id: str) -> bytes:
        frame_bytes, _ = self._wait_for_frame(camera_id, timeout=1.0)
        if frame_bytes is None:
            error = self._slots[camera_id].last_error or "ZMQ camera frame not available"
            return self._error_jpeg(error)
        return frame_bytes

    def _error_frame(self, text: str) -> bytes:
        return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + self._error_jpeg(text) + b"\r\n"

    def _error_jpeg(self, text: str) -> bytes:
        if cv2 is None:
            return f"ZMQ camera error: {text}".encode("utf-8")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (24, 24, 24)
        lines = ["ZMQ camera stream unavailable", text]
        y = 160
        for line in lines:
            cv2.putText(frame, line, (32, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            y += 44
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            return f"ZMQ camera error: {text}".encode("utf-8")
        return encoded.tobytes()


class ZmqObservationCameraManager:
    """Per-camera facade backed by a shared observation hub."""

    def __init__(self, hub: ZmqObservationCameraHub, camera_id: str):
        self._hub = hub
        self.camera_id = camera_id

    def list_devices(self) -> List[Dict[str, str]]:
        return self._hub.list_devices(self.camera_id)

    def get_status(self) -> Dict[str, Union[bool, int, str, List[Dict[str, str]], None]]:
        return self._hub.get_status(self.camera_id)

    def stream_mjpeg(self) -> Iterable[bytes]:
        return self._hub.stream_mjpeg(self.camera_id)

    def get_jpeg_frame(self) -> bytes:
        return self._hub.get_jpeg_frame(self.camera_id)
