"""WebRTC camera streaming helpers for the VR headset view."""

from __future__ import annotations

import asyncio
import logging
from fractions import Fraction
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.mediastreams import VideoStreamTrack
    from av import VideoFrame
except ImportError:  # pragma: no cover - optional runtime dependency
    RTCPeerConnection = None
    RTCSessionDescription = None
    VideoStreamTrack = object
    VideoFrame = None


class CameraVideoTrack(VideoStreamTrack):
    """Video track backed by the newest frame in a ZMQ camera manager."""

    def __init__(self, camera_manager, fps: int = 30):
        super().__init__()
        self.camera_manager = camera_manager
        self._last_version: Optional[int] = None
        self._fps = max(1, int(fps))
        self._time_base = Fraction(1, 90000)
        self._pts = 0
        self._frame_duration = int(90000 / self._fps)

    async def recv(self):
        if VideoFrame is None:
            raise RuntimeError("PyAV is not installed")

        frame_array, version = await asyncio.to_thread(
            self.camera_manager.get_latest_frame_array,
            self._last_version,
            1.0,
        )
        self._last_version = version

        if frame_array is None:
            frame_array = self.camera_manager.get_error_frame_array()

        frame = VideoFrame.from_ndarray(frame_array, format="bgr24")
        frame.pts = self._pts
        frame.time_base = self._time_base
        self._pts += self._frame_duration
        return frame


class WebRTCCameraServer:
    """Small one-way WebRTC offer/answer server for camera panels."""

    def __init__(self, camera_managers: Dict[str, Any]):
        self.camera_managers = camera_managers
        self.peer_connections: Set[Any] = set()

    @property
    def available(self) -> bool:
        return RTCPeerConnection is not None and RTCSessionDescription is not None and VideoFrame is not None

    async def handle_offer(self, offer: Dict[str, Any], camera_id: str) -> Dict[str, Any]:
        if not self.available:
            raise RuntimeError("WebRTC dependencies are not installed. Install aiortc and av.")
        if camera_id not in self.camera_managers:
            raise RuntimeError(f"Unknown camera id: {camera_id}")

        pc = RTCPeerConnection()
        self.peer_connections.add(pc)
        connection_id = f"pc-{id(pc)}"
        logger.info("Creating WebRTC camera peer %s for %s", connection_id, camera_id)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info("WebRTC peer %s state=%s", connection_id, pc.connectionState)
            if pc.connectionState in {"failed", "closed", "disconnected"}:
                await self._close_pc(pc)

        camera_manager = self.camera_managers[camera_id]
        fps = max(1, int(camera_manager.get_status().get("fps", 30)))
        pc.addTrack(CameraVideoTrack(camera_manager, fps=fps))

        remote_description = RTCSessionDescription(sdp=offer["sdp"], type=offer["type"])
        await pc.setRemoteDescription(remote_description)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

    async def _close_pc(self, pc) -> None:
        if pc in self.peer_connections:
            self.peer_connections.discard(pc)
        await pc.close()

    async def stop(self) -> None:
        await asyncio.gather(*(self._close_pc(pc) for pc in list(self.peer_connections)), return_exceptions=True)
        self.peer_connections.clear()
