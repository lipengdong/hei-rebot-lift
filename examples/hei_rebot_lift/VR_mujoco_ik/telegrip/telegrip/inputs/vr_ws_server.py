"""WebSocket receiver that republishes VR browser data over ZeroMQ."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from pathlib import Path
from typing import Optional, Set

import websockets
import zmq

from ..config import TelegripConfig, get_config_data

logger = logging.getLogger(__name__)
HEAD_POSE_LOG = Path("/tmp/telegrip_head_pose.log")


class VRWebSocketServer:
    """Receive WebXR head/controller packets and publish them to ZMQ."""

    def __init__(self, command_queue: asyncio.Queue, config: TelegripConfig):
        self.command_queue = command_queue
        self.config = config
        self.clients: Set = set()
        self.server = None
        self.is_running = False
        self.last_head_log_time = 0.0
        self.last_control_state: dict[str, object] = {}

        runtime_config = get_config_data()
        vr_config = runtime_config.get("vr", {})
        self.enabled = bool(vr_config.get("enabled", True))
        self.zmq_topic = str(vr_config.get("zmq_topic", "vr_data"))
        self.zmq_endpoint = str(vr_config.get("zmq_publish_endpoint", "tcp://*:5567"))

        try:
            HEAD_POSE_LOG.write_text("", encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not initialize head pose log %s: %s", HEAD_POSE_LOG, exc)

        self.zmq_context = zmq.Context()
        self.zmq_socket = None
        try:
            self.zmq_socket = self.zmq_context.socket(zmq.PUB)
            self.zmq_socket.bind(self.zmq_endpoint)
            logger.info("ZeroMQ publisher started on %s topic=%s", self.zmq_endpoint, self.zmq_topic)
        except Exception as exc:
            if self.zmq_socket is not None:
                self.zmq_socket.close(0)
            self.zmq_socket = None
            self.zmq_context.term()
            raise RuntimeError(f"ZeroMQ publisher bind failed on {self.zmq_endpoint}: {exc}") from exc

    def _get_local_ip(self) -> str:
        import socket

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "localhost"

    def setup_ssl(self) -> Optional[ssl.SSLContext]:
        if not self.config.ssl_files_exist and not self.config.ensure_ssl_certificates():
            logger.error("Failed to generate SSL certificates for WebSocket server")
            return None

        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        try:
            cert_path, key_path = self.config.get_absolute_ssl_paths()
            ssl_context.load_cert_chain(certfile=cert_path, keyfile=key_path)
            return ssl_context
        except ssl.SSLError as exc:
            logger.error("Error loading SSL cert/key: %s", exc)
            return None

    async def start(self):
        if not self.enabled:
            logger.info("VR WebSocket server disabled in configuration")
            return

        ssl_context = self.setup_ssl()
        if ssl_context is None:
            return

        self.server = await websockets.serve(
            self.websocket_handler,
            self.config.host_ip,
            self.config.websocket_port,
            ssl=ssl_context,
            process_request=self._process_request,
        )
        self.is_running = True
        host_display = self._get_local_ip() if self.config.host_ip == "0.0.0.0" else self.config.host_ip
        logger.info("VR WebSocket server running on wss://%s:%s", host_display, self.config.websocket_port)

    async def _process_request(self, connection, request):
        headers = request.headers
        connection_header = headers.get("Connection", "")
        upgrade_header = headers.get("Upgrade", "")
        is_websocket_request = "upgrade" in connection_header.lower() and "websocket" in upgrade_header.lower()
        if not is_websocket_request:
            host_display = self._get_local_ip() if self.config.host_ip == "0.0.0.0" else self.config.host_ip
            logger.info(
                "Port %s is for WebSocket only. Open https://%s:%s for the VR page.",
                self.config.websocket_port,
                host_display,
                self.config.https_port,
            )
        return None

    async def stop(self):
        self.is_running = False
        for client in list(self.clients):
            try:
                await client.close()
            except Exception:
                pass

        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

        if self.zmq_socket is not None:
            self.zmq_socket.close(0)
            self.zmq_socket = None
        self.zmq_context.term()

    async def websocket_handler(self, websocket, path=None):
        client_address = websocket.remote_address
        logger.info("VR client connected: %s", client_address)
        self.clients.add(websocket)

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning("Received non-JSON message from %s", client_address)
                    continue

                self._log_head_pose(data)
                self._log_control_state(data)
                if self.zmq_socket is not None:
                    self.zmq_socket.send_string(f"{self.zmq_topic} {json.dumps(data)}")
        except websockets.exceptions.ConnectionClosedOK:
            logger.info("VR client %s disconnected normally", client_address)
        except websockets.exceptions.ConnectionClosedError as exc:
            logger.warning("VR client %s disconnected with error: %s", client_address, exc)
        finally:
            self.clients.discard(websocket)

    def _log_head_pose(self, data: dict) -> None:
        head = data.get("head")
        now = time.time()
        if not isinstance(head, dict) or now - self.last_head_log_time < 0.2:
            return

        position = head.get("position") or {}
        rotation = head.get("rotation") or {}
        line = (
            "Head "
            f"pos=({position.get('x', 0):.2f}, {position.get('y', 0):.2f}, {position.get('z', 0):.2f}) "
            f"rot=({rotation.get('x', 0):.0f}, {rotation.get('y', 0):.0f}, {rotation.get('z', 0):.0f})"
        )
        try:
            with HEAD_POSE_LOG.open("a", encoding="utf-8") as log_file:
                log_file.write(line + "\n")
        except Exception as exc:
            logger.warning("Could not write head pose log %s: %s", HEAD_POSE_LOG, exc)
        self.last_head_log_time = now

    def _log_control_state(self, data: dict) -> None:
        event_type = data.get("type")
        if event_type in {"button_press", "button_release"}:
            hand = data.get("hand", "unknown")
            button = data.get("button", "unknown")
            action = "pressed" if event_type == "button_press" else "released"
            logger.info("VR button %s %s %s", hand, button, action)
            state_field = {
                "X": "xButton",
                "Y": "yButton",
                "A": "aButton",
                "B": "bButton",
            }.get(str(button).upper())
            if state_field:
                self.last_control_state[f"{hand}.{state_field}"] = event_type == "button_press"
            return

        hand = data.get("hand")
        if hand and data.get("gripReleased"):
            self.last_control_state[f"{hand}.gripActive"] = False
            logger.info("VR button %s grip released", hand)
            return
        if hand and data.get("triggerReleased"):
            self.last_control_state[f"{hand}.trigger"] = False
            logger.info("VR button %s trigger released", hand)
            return

        self._log_controller_state("left", data.get("leftController"))
        self._log_controller_state("right", data.get("rightController"))

    def _log_controller_state(self, hand: str, controller) -> None:
        if not isinstance(controller, dict):
            return

        if hand == "left":
            button_fields = [("grip", "gripActive"), ("trigger", "trigger"), ("X", "xButton"), ("Y", "yButton")]
        else:
            button_fields = [("grip", "gripActive"), ("trigger", "trigger"), ("A", "aButton"), ("B", "bButton")]

        for label, field in button_fields:
            value = bool(controller.get(field, 0))
            state_key = f"{hand}.{field}"
            if self.last_control_state.get(state_key) != value:
                self.last_control_state[state_key] = value
                logger.info("VR button %s %s %s", hand, label, "pressed" if value else "released")

        thumbstick = controller.get("thumbstick")
        if not isinstance(thumbstick, dict):
            return

        x = round(float(thumbstick.get("x", 0.0)), 2)
        y = round(float(thumbstick.get("y", 0.0)), 2)
        pressed = int(bool(thumbstick.get("pressed", 0)))
        compact = (x, y, pressed)
        state_key = f"{hand}.thumbstick"
        if self.last_control_state.get(state_key) != compact:
            self.last_control_state[state_key] = compact
            if pressed or abs(x) >= 0.05 or abs(y) >= 0.05:
                logger.info("VR joystick %s x=%.2f y=%.2f pressed=%s", hand, x, y, pressed)
            else:
                logger.info("VR joystick %s released", hand)
