"""
Core detection logic: YOLOv8 object/person detection + MediaPipe full-body pose tracking.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Lock, RLock
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports — loaded on first use so the module can be imported without GPU/model weights
_yolo_model_cache: dict[str, object] = {}
_mp_pose = None
_mp_drawing = None
_mp_drawing_styles = None


def _load_yolo(model_size: str):
    if model_size not in _yolo_model_cache:
        from ultralytics import YOLO
        _yolo_model_cache[model_size] = YOLO(f"{model_size}.pt")
    return _yolo_model_cache[model_size]


def _get_mp_pose():
    global _mp_pose, _mp_drawing, _mp_drawing_styles
    if _mp_pose is None:
        import mediapipe as mp
        _mp_pose = mp.solutions.pose
        _mp_drawing = mp.solutions.drawing_utils
        _mp_drawing_styles = mp.solutions.drawing_styles
    return _mp_pose, _mp_drawing, _mp_drawing_styles


# ---------------------------------------------------------------------------
# Colors (BGR)
# ---------------------------------------------------------------------------
COLOR_PERSON = (238, 211, 34)   # cyan  #22d3ee  → BGR
COLOR_OBJECT = (21, 204, 250)   # yellow #facc15 → BGR
COLOR_POSE   = (94, 197, 34)    # green  #22c55e → BGR
COLOR_TEXT_BG = (15, 18, 11)    # near-black


@dataclass
class Detection:
    x1: int
    y1: int
    x2: int
    y2: int
    class_id: int
    label: str
    confidence: float


class CameraDetector:
    """
    Wraps YOLOv8 detection + MediaPipe Pose tracking.

    Thread-safe settings updates via update_settings().
    """

    PERSON_CLASS_ID = 0  # COCO class index for "person"

    def __init__(
        self,
        model_size: str = "yolov8n",
        mode: str = "both",
        show_boxes: bool = True,
        show_labels: bool = True,
        show_pose: bool = True,
        confidence: float = 0.5,
    ):
        self._lock = Lock()
        self._model_lock = RLock()
        self.model_size = model_size
        self.mode = mode
        self.show_boxes = show_boxes
        self.show_labels = show_labels
        self.show_pose = show_pose
        self.confidence = confidence

        # Lazy-load models
        self._yolo = None
        self._pose_solution = None

        # FPS tracking
        self._prev_time: float = 0.0

        # Probe required packages at construction time so failures surface early
        try:
            from ultralytics import YOLO  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                f"Paket 'ultralytics' nicht gefunden – bitte installieren: "
                f"pip install ultralytics  ({exc})"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Fehler beim Laden von YOLO (ultralytics): {exc}") from exc

        try:
            import mediapipe  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                f"Paket 'mediapipe' nicht gefunden – bitte installieren: "
                f"pip install mediapipe  ({exc})"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Fehler beim Laden von MediaPipe (mediapipe): {exc}") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_settings(
        self,
        model_size: Optional[str] = None,
        mode: Optional[str] = None,
        show_boxes: Optional[bool] = None,
        show_labels: Optional[bool] = None,
        show_pose: Optional[bool] = None,
        confidence: Optional[float] = None,
    ) -> None:
        with self._lock:
            if model_size is not None and model_size != self.model_size:
                logger.info(
                    "Modellgröße geändert: %s -> %s", self.model_size, model_size
                )
                self.model_size = model_size
                with self._model_lock:
                    self._yolo = None  # force reload
            if mode is not None:
                self.mode = mode
            if show_boxes is not None:
                self.show_boxes = show_boxes
            if show_labels is not None:
                self.show_labels = show_labels
            if show_pose is not None:
                self.show_pose = show_pose
            if confidence is not None:
                self.confidence = confidence

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, dict]:
        """
        Run detection on a BGR frame.
        Returns (annotated_frame, stats_dict).
        stats_dict keys: fps, object_count, person_count
        """
        with self._lock:
            mode = self.mode
            show_boxes = self.show_boxes
            show_labels = self.show_labels
            show_pose = self.show_pose
            confidence = self.confidence
            model_size = self.model_size

        # Load YOLO lazily and run inference — held together under _model_lock
        # so a concurrent update_settings() cannot null out self._yolo mid-inference.
        with self._model_lock:
            if self._yolo is None:
                self._yolo = _load_yolo(model_size)
            detections = self._run_yolo(frame, mode, confidence)

        annotated = frame.copy()

        person_detections = [d for d in detections if d.class_id == self.PERSON_CLASS_ID]
        object_detections = [d for d in detections if d.class_id != self.PERSON_CLASS_ID]

        # Draw pose skeleton first (behind boxes)
        if show_pose and person_detections:
            annotated = self._run_pose(annotated, person_detections)

        # Draw bounding boxes
        if show_boxes:
            for det in person_detections:
                self._draw_box(annotated, det, COLOR_PERSON, show_labels)
            for det in object_detections:
                self._draw_box(annotated, det, COLOR_OBJECT, show_labels)

        # Compute FPS
        now = time.time()
        fps = 1.0 / (now - self._prev_time) if self._prev_time else 0.0
        self._prev_time = now

        # Overlay FPS
        cv2.putText(
            annotated,
            f"FPS: {fps:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            COLOR_POSE,
            2,
            cv2.LINE_AA,
        )

        stats = {
            "fps": round(fps, 1),
            "person_count": len(person_detections),
            "object_count": len(object_detections),
        }
        return annotated, stats

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_yolo(self, frame: np.ndarray, mode: str, confidence: float) -> list[Detection]:
        results = self._yolo(frame, conf=confidence, verbose=False)[0]
        detections: list[Detection] = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            label = results.names[cls_id]
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            is_person = cls_id == self.PERSON_CLASS_ID

            if mode == "persons" and not is_person:
                continue
            if mode == "objects" and is_person:
                continue

            detections.append(
                Detection(x1=x1, y1=y1, x2=x2, y2=y2, class_id=cls_id, label=label, confidence=conf)
            )

        return detections

    def _draw_box(
        self,
        frame: np.ndarray,
        det: Detection,
        color: tuple[int, int, int],
        show_label: bool,
    ) -> None:
        cv2.rectangle(frame, (det.x1, det.y1), (det.x2, det.y2), color, 2)

        if show_label:
            label_text = f"{det.label} {det.confidence:.0%}"
            (tw, th), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            ty = max(det.y1 - 4, th + 4)
            cv2.rectangle(
                frame,
                (det.x1, ty - th - baseline - 4),
                (det.x1 + tw + 4, ty),
                color,
                -1,
            )
            cv2.putText(
                frame,
                label_text,
                (det.x1 + 2, ty - baseline - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                COLOR_TEXT_BG,
                1,
                cv2.LINE_AA,
            )

    def _run_pose(self, frame: np.ndarray, person_detections: list[Detection]) -> np.ndarray:
        mp_pose, mp_drawing, mp_drawing_styles = _get_mp_pose()

        if self._pose_solution is None:
            self._pose_solution = mp_pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                enable_segmentation=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        for det in person_detections:
            # Crop person ROI with a small margin
            margin = 10
            x1 = max(0, det.x1 - margin)
            y1 = max(0, det.y1 - margin)
            x2 = min(w, det.x2 + margin)
            y2 = min(h, det.y2 + margin)

            roi = rgb[y1:y2, x1:x2]
            if roi.size == 0:
                continue

            results = self._pose_solution.process(roi)

            if results.pose_landmarks:
                # Draw landmarks on the ROI in BGR, then paste back
                roi_bgr = cv2.cvtColor(roi, cv2.COLOR_RGB2BGR)
                mp_drawing.draw_landmarks(
                    roi_bgr,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(
                        color=COLOR_POSE, thickness=2, circle_radius=3
                    ),
                    connection_drawing_spec=mp_drawing.DrawingSpec(
                        color=COLOR_POSE, thickness=2
                    ),
                )
                frame[y1:y2, x1:x2] = roi_bgr

        return frame
