"""Detector and multi-object tracking boundary for CCTV integrations.

`MotionDetector` is the dependency-free fixed-camera fallback. Deployments can inject a
model-backed detector (for example a validated YOLO/ByteTrack provider) without changing
camera streaming, twin synchronisation, or the API contract.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

import cv2
import numpy as np


@dataclass
class Detection:
    bbox: tuple[int, int, int, int]
    object_class: str = "vehicle"
    confidence: float = .70
    lane_number: int = 1
    external_track_id: str | None = None


@dataclass
class Track:
    track_id: str
    bbox: tuple[int, int, int, int]
    object_class: str
    confidence: float
    lane_number: int
    path: list[tuple[int, int]] = field(default_factory=list)
    missing_frames: int = 0


class Detector(Protocol):
    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class MotionDetector:
    """Fixed-camera motion segmentation with contour filtering.

    Use this only where a model provider is unavailable. It identifies moving
    vehicle-sized objects, but cannot safely distinguish car/truck/bus classes.
    """
    def __init__(self) -> None:
        self.subtractor = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=True)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        mask = self.subtractor.apply(frame)
        _, mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        mask = cv2.dilate(mask, np.ones((7, 7), np.uint8), iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        output: list[Detection] = []
        for contour in contours:
            if cv2.contourArea(contour) < 1000:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            if w < 22 or h < 18:
                continue
            # Lanes are derived from image thirds and must be calibrated per camera.
            lane = min(3, x * 3 // max(frame.shape[1], 1) + 1)
            output.append(Detection((x, y, w, h), lane_number=int(lane)))
        return output


class UltralyticsByteTrackDetector:
    """GPU-capable YOLO + ByteTrack adapter for production deployments.

    Configure `FLOWMIRROR_YOLO_MODEL` with a vetted model path. COCO models provide
    person, bicycle, car, motorcycle, bus, and truck. Emergency-vehicle recognition
    requires a locally validated custom model trained for the deployment city.
    """
    _classes = {0: "pedestrian", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

    def __init__(self, model_path: str, tracker_config: str = "bytetrack.yaml") -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Install ultralytics and GPU runtime to enable YOLO/ByteTrack detection.") from exc
        self.model = YOLO(model_path)
        self.tracker_config = tracker_config

    def detect(self, frame: np.ndarray) -> list[Detection]:
        result = self.model.track(frame, persist=True, tracker=self.tracker_config, classes=list(self._classes), verbose=False)[0]
        if result.boxes is None:
            return []
        detections: list[Detection] = []
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            if class_id not in self._classes:
                continue
            x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
            track_id = str(int(box.id[0].item())) if box.id is not None else None
            detections.append(Detection((x1, y1, x2 - x1, y2 - y1), object_class=self._classes[class_id], confidence=round(float(box.conf[0].item()), 3), lane_number=max(1, min(3, x1 * 3 // max(frame.shape[1], 1) + 1)), external_track_id=track_id))
        return detections


def detector_from_environment() -> Detector:
    model_path = os.getenv("FLOWMIRROR_YOLO_MODEL")
    if model_path:
        return UltralyticsByteTrackDetector(model_path, os.getenv("FLOWMIRROR_TRACKER_CONFIG", "bytetrack.yaml"))
    return MotionDetector()


class MultiObjectTracker:
    """Persistent IoU tracker for real-time UI continuity.

    A production adapter may substitute ByteTrack or DeepSORT while preserving the
    same `Track` result. This tracker keeps IDs and paths across typical CCTV frames.
    """
    def __init__(self, iou_threshold: float = .22, max_missing_frames: int = 18) -> None:
        self.iou_threshold = iou_threshold
        self.max_missing_frames = max_missing_frames
        self._tracks: dict[str, Track] = {}
        self._next_id = 1001

    @staticmethod
    def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax, ay, aw, ah = a; bx, by, bw, bh = b
        x1, y1 = max(ax, bx), max(ay, by); x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        union = aw * ah + bw * bh - intersection
        return intersection / union if union else 0.0

    @staticmethod
    def _centre(box: tuple[int, int, int, int]) -> tuple[int, int]:
        x, y, w, h = box
        return x + w // 2, y + h // 2

    def update(self, detections: list[Detection]) -> list[Track]:
        unmatched = set(range(len(detections)))
        # ByteTrack/DeepSORT IDs are authoritative. Honour them before doing IoU
        # association so two close vehicles cannot accidentally exchange identities.
        for index, detection in enumerate(detections):
            if detection.external_track_id is None:
                continue
            track_id = f"OBJ-{detection.external_track_id}"
            existing = self._tracks.get(track_id)
            if existing:
                existing.bbox = detection.bbox
                existing.object_class = detection.object_class
                existing.confidence = detection.confidence
                existing.lane_number = detection.lane_number
                existing.path = (existing.path + [self._centre(detection.bbox)])[-24:]
                existing.missing_frames = 0
            else:
                self._tracks[track_id] = Track(
                    track_id=track_id,
                    bbox=detection.bbox,
                    object_class=detection.object_class,
                    confidence=detection.confidence,
                    lane_number=detection.lane_number,
                    path=[self._centre(detection.bbox)],
                )
            unmatched.remove(index)
        for track in self._tracks.values():
            # This track has already been updated through an external tracker ID.
            if any(detection.external_track_id and f"OBJ-{detection.external_track_id}" == track.track_id for detection in detections):
                continue
            candidates = [(self._iou(track.bbox, detection.bbox), index) for index, detection in enumerate(detections) if index in unmatched]
            score, index = max(candidates, default=(0.0, -1))
            if index >= 0 and score >= self.iou_threshold:
                detection = detections[index]
                track.bbox, track.object_class, track.confidence, track.lane_number = detection.bbox, detection.object_class, detection.confidence, detection.lane_number
                track.path = (track.path + [self._centre(detection.bbox)])[-24:]
                track.missing_frames = 0
                unmatched.remove(index)
            else:
                track.missing_frames += 1
        self._tracks = {key: track for key, track in self._tracks.items() if track.missing_frames <= self.max_missing_frames}
        for index in unmatched:
            detection = detections[index]
            track_id = f"OBJ-{detection.external_track_id}" if detection.external_track_id else f"VEH-{self._next_id}"
            if not detection.external_track_id:
                self._next_id += 1
            self._tracks[track_id] = Track(track_id=track_id, bbox=detection.bbox, object_class=detection.object_class, confidence=detection.confidence, lane_number=detection.lane_number, path=[self._centre(detection.bbox)])
        return list(self._tracks.values())
