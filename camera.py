from __future__ import annotations

import math
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .twin import TrafficTwin
from .surveillance import MultiObjectTracker, detector_from_environment


class TrafficCameraService:
    """Processes a fixed CCTV/video feed using OpenCV motion segmentation.

    It is deliberately self-contained: no cloud service or pre-trained weight file is
    required for the first deployment. For a fixed, elevated traffic camera, moving
    vehicle-sized contours supply a useful real-time density and movement estimate.
    """

    def __init__(self, twin: TrafficTwin) -> None:
        self.twin = twin
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._running = False
        self._source: str | int | None = None
        self._latest_jpeg: bytes | None = None
        self._previous_centres: list[tuple[int, int]] = []
        self._detector = detector_from_environment()
        self._tracker = MultiObjectTracker()
        self._status: dict[str, Any] = {
            "state": "idle", "source": None, "vehicle_count": 0,
            "average_speed_kmph": 0.0, "congestion": "unknown",
            "stopped_vehicle_risk": False, "message": "Upload a fixed-camera CCTV video or start a webcam.",
            "detections": [], "fps": 0.0,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def start(self, source: str | int) -> None:
        self.stop()
        self._source = source
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="traffic-camera")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        with self._lock:
            if self._status["state"] != "error":
                self._status["state"] = "idle"
                self._status["message"] = "Camera analysis stopped."

    def _run(self) -> None:
        capture = cv2.VideoCapture(self._source)
        if not capture.isOpened():
            with self._lock:
                self._status.update(state="error", message="Unable to open the selected camera or video source.")
            return
        previous_time = time.monotonic()
        try:
            while self._running:
                ok, frame = capture.read()
                if not ok:
                    # Recorded videos loop; a disconnected webcam reports an error.
                    if isinstance(self._source, str):
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        self._previous_centres = []
                        continue
                    with self._lock:
                        self._status.update(state="error", message="Camera stream ended or disconnected.")
                    break
                frame = cv2.resize(frame, (960, 540))
                annotated, metrics = self._analyse_frame(frame, max(time.monotonic() - previous_time, .05))
                previous_time = time.monotonic()
                encoded, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 84])
                if encoded:
                    with self._lock:
                        self._latest_jpeg = jpeg.tobytes()
                        self._status.update(state="running", source=str(self._source), **metrics)
                self.twin.apply_camera_observation(metrics["vehicle_count"], metrics["average_speed_kmph"], metrics["congestion"], metrics["stopped_vehicle_risk"])
                time.sleep(.03)
        finally:
            capture.release()

    def _analyse_frame(self, frame: np.ndarray, delta_seconds: float) -> tuple[np.ndarray, dict[str, Any]]:
        tracks = self._tracker.update(self._detector.detect(frame))
        centres = [track.path[-1] for track in tracks if track.path]

        movements: list[float] = []
        for cx, cy in centres:
            nearest = min((math.dist((cx, cy), point) for point in self._previous_centres), default=None)
            if nearest is not None and nearest < 100:
                movements.append(nearest)
        self._previous_centres = centres
        # A camera must be calibrated for legal real-world speed measurement. This
        # display estimate is used only for traffic-state classification in the demo.
        average_speed = min(60.0, round((sum(movements) / len(movements) / delta_seconds * .12) if movements else 0.0, 1))
        count = len(tracks)
        congestion = "high" if count >= 10 or (count >= 5 and average_speed < 8) else "medium" if count >= 4 else "low"
        stopped_risk = count >= 5 and average_speed < 3
        for track in tracks:
            x, y, w, h = track.bbox
            colour = (72, 84, 237) if congestion == "high" else (58, 172, 255) if congestion == "medium" else (105, 210, 122)
            cv2.rectangle(frame, (x, y), (x + w, y + h), colour, 2)
            cv2.putText(frame, f"{track.track_id} {track.object_class} L{track.lane_number}", (x, max(18, y - 7)), cv2.FONT_HERSHEY_SIMPLEX, .48, colour, 1, cv2.LINE_AA)
            if len(track.path) > 1:
                cv2.polylines(frame, [np.array(track.path, np.int32)], False, colour, 1)
        banner = f"FLOWMIRROR CCTV | VEHICLES: {count} | TRAFFIC: {congestion.upper()}"
        cv2.rectangle(frame, (0, 0), (960, 43), (11, 23, 37), -1)
        cv2.putText(frame, banner, (16, 28), cv2.FONT_HERSHEY_SIMPLEX, .62, (233, 244, 255), 2, cv2.LINE_AA)
        return frame, {
            "vehicle_count": count, "average_speed_kmph": average_speed,
            "congestion": congestion, "stopped_vehicle_risk": stopped_risk,
            "message": "CCTV analysis running. Detector/tracker output is live.",
            "detections": [{"id": track.track_id, "class": track.object_class, "confidence": track.confidence, "lane": track.lane_number, "bbox": track.bbox, "path": track.path[-12:]} for track in tracks],
            "fps": round(1 / delta_seconds, 1),
        }

    def mjpeg_frames(self):
        while True:
            with self._lock:
                frame = self._latest_jpeg
                running = self._running
            if frame:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            elif not running:
                return
            time.sleep(.08)
