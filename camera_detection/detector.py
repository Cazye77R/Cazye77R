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

# Drawing specs are immutable config objects. Built once on first use rather than
# per-landmark-per-person-per-frame, which would allocate thousands of objects a second.
_pose_landmark_spec = None
_pose_connection_spec = None


# ---------------------------------------------------------------------------
# Colors (BGR)
# ---------------------------------------------------------------------------
COLOR_PERSON = (238, 211, 34)   # cyan  #22d3ee  → BGR
COLOR_OBJECT = (21, 204, 250)   # yellow #facc15 → BGR
COLOR_POSE   = (94, 197, 34)    # green  #22c55e → BGR
COLOR_TEXT_BG = (15, 18, 11)    # near-black

PERSON_CLASS_ID = 0             # COCO class index for "person"
NUM_COCO_CLASSES = 80

# Smoothing factor for the FPS readout. Raw 1/delta is far too noisy to read.
FPS_SMOOTHING = 0.2


def _load_yolo(model_size: str):
    if model_size not in _yolo_model_cache:
        from ultralytics import YOLO
        _yolo_model_cache[model_size] = YOLO(f"{model_size}.pt")
    return _yolo_model_cache[model_size]


def _get_mp_pose():
    global _mp_pose, _mp_drawing, _pose_landmark_spec, _pose_connection_spec
    if _mp_pose is None:
        import mediapipe as mp
        _mp_pose = mp.solutions.pose
        _mp_drawing = mp.solutions.drawing_utils
        _pose_landmark_spec = _mp_drawing.DrawingSpec(
            color=COLOR_POSE, thickness=2, circle_radius=3
        )
        _pose_connection_spec = _mp_drawing.DrawingSpec(color=COLOR_POSE, thickness=2)
    return _mp_pose, _mp_drawing


@dataclass
class Detection:
    x1: int
    y1: int
    x2: int
    y2: int
    class_id: int
    label: str
    confidence: float

    @property
    def area(self) -> int:
        return max(0, self.x2 - self.x1) * max(0, self.y2 - self.y1)


def _resolve_class_filter(
    mode: str, selected_classes: Optional[list[int]]
) -> Optional[list[int]]:
    """
    Build the class-id list handed to YOLO so filtering happens during inference
    (NMS then runs over fewer boxes) instead of afterwards in Python.

    Returns None when every class is allowed — YOLO treats that as "no filter".
    """
    if mode == "persons":
        allowed = [PERSON_CLASS_ID]
    elif mode == "objects":
        allowed = [c for c in range(NUM_COCO_CLASSES) if c != PERSON_CLASS_ID]
    else:  # "both"
        allowed = None

    if not selected_classes:
        return allowed

    if allowed is None:
        return sorted(set(selected_classes))

    narrowed = sorted(set(selected_classes) & set(allowed))
    # An empty intersection would read as "no filter" to YOLO, the opposite of
    # what the user asked for — fall back to the mode's own restriction.
    return narrowed or allowed


class CameraDetector:
    """
    Wraps YOLOv8 detection + MediaPipe Pose tracking.

    Thread-safe settings updates via update_settings().
    """

    PERSON_CLASS_ID = PERSON_CLASS_ID

    def __init__(
        self,
        model_size: str = "yolov8n",
        mode: str = "both",
        show_boxes: bool = True,
        show_labels: bool = True,
        show_pose: bool = True,
        confidence: float = 0.5,
        selected_classes: Optional[list[int]] = None,
        max_pose_persons: int = 4,
    ):
        self._lock = Lock()
        self._model_lock = RLock()
        self.model_size = model_size
        self.mode = mode
        self.show_boxes = show_boxes
        self.show_labels = show_labels
        self.show_pose = show_pose
        self.confidence = confidence
        self.selected_classes = selected_classes
        self.max_pose_persons = max_pose_persons

        # Lazy-load models
        self._yolo = None
        self._loaded_model_size: str = ""
        self._pose_solution = None

        # FPS tracking (only ever touched from the single video worker thread)
        self._prev_time: float = 0.0
        self._fps_ema: float = 0.0

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
        selected_classes: Optional[list[int]] = None,
        max_pose_persons: Optional[int] = None,
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
            if selected_classes is not None:
                self.selected_classes = selected_classes
            if max_pose_persons is not None:
                self.max_pose_persons = max_pose_persons

    def ensure_model_loaded(self) -> None:
        """
        Load the configured YOLO weights if they are not resident yet.

        Call this from the Streamlit main thread (wrapped in st.spinner) so the
        first-run download does not stall the WebRTC video worker, which would
        show up to the user as a frozen picture.
        """
        with self._lock:
            model_size = self.model_size

        with self._model_lock:
            if self._yolo is None or self._loaded_model_size != model_size:
                logger.info("Lade YOLO-Modell: %s", model_size)
                self._yolo = _load_yolo(model_size)
                self._loaded_model_size = model_size

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, dict]:
        """
        Run detection on a BGR frame.

        The frame is annotated IN PLACE and returned; callers must pass an array
        they own (av's ``to_ndarray()`` always hands out a fresh one).

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
            selected_classes = self.selected_classes
            max_pose_persons = self.max_pose_persons

        class_filter = _resolve_class_filter(mode, selected_classes)

        # Load YOLO lazily and run inference — held together under _model_lock
        # so a concurrent update_settings() cannot null out self._yolo mid-inference.
        # _loaded_model_size guards against a TOCTOU window where update_settings()
        # clears _yolo after model_size was snapshotted above, causing detect() to
        # reload the old model into _yolo (which would then persist indefinitely).
        with self._model_lock:
            if self._yolo is None or self._loaded_model_size != model_size:
                self._yolo = _load_yolo(model_size)
                self._loaded_model_size = model_size
            detections = self._run_yolo(frame, confidence, class_filter)

        person_detections = [d for d in detections if d.class_id == PERSON_CLASS_ID]
        object_detections = [d for d in detections if d.class_id != PERSON_CLASS_ID]

        # Draw pose skeleton first (behind boxes)
        if show_pose and person_detections:
            self._run_pose(frame, person_detections, max_pose_persons)

        # Draw bounding boxes
        if show_boxes:
            for det in person_detections:
                self._draw_box(frame, det, COLOR_PERSON, show_labels)
            for det in object_detections:
                self._draw_box(frame, det, COLOR_OBJECT, show_labels)

        # FPS as an exponential moving average — the instantaneous 1/delta value
        # swings too wildly to be readable.
        now = time.time()
        if self._prev_time:
            instant = 1.0 / max(now - self._prev_time, 1e-6)
            self._fps_ema = (
                instant
                if self._fps_ema == 0.0
                else FPS_SMOOTHING * instant + (1.0 - FPS_SMOOTHING) * self._fps_ema
            )
        self._prev_time = now

        # Overlay FPS
        cv2.putText(
            frame,
            f"FPS: {self._fps_ema:.1f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            COLOR_POSE,
            2,
            cv2.LINE_AA,
        )

        stats = {
            "fps": round(self._fps_ema, 1),
            "person_count": len(person_detections),
            "object_count": len(object_detections),
        }
        return frame, stats

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_yolo(
        self,
        frame: np.ndarray,
        confidence: float,
        class_filter: Optional[list[int]],
    ) -> list[Detection]:
        # Passing `classes` lets YOLO drop unwanted classes before NMS instead of
        # us discarding them afterwards in Python.
        results = self._yolo(
            frame, conf=confidence, classes=class_filter, verbose=False
        )[0]
        detections: list[Detection] = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            label = results.names[cls_id]
            x1, y1, x2, y2 = map(int, box.xyxy[0])

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

    def _get_pose_solution(self):
        mp_pose, _ = _get_mp_pose()
        with self._model_lock:
            if self._pose_solution is None:
                # static_image_mode=True is deliberate: with False, Pose is a
                # stateful single-person tracker that carries landmark history
                # between calls. Feeding it alternating person ROIs within one
                # frame corrupts that state. YOLO already does the person
                # detection that the stateful mode would otherwise save us.
                self._pose_solution = mp_pose.Pose(
                    static_image_mode=True,
                    model_complexity=1,
                    enable_segmentation=False,
                    min_detection_confidence=0.5,
                )
            return self._pose_solution

    def _run_pose(
        self,
        frame: np.ndarray,
        person_detections: list[Detection],
        max_persons: int,
    ) -> None:
        """Draw pose skeletons onto ``frame`` in place for the largest persons."""
        mp_pose, mp_drawing = _get_mp_pose()
        pose_solution = self._get_pose_solution()

        h, w = frame.shape[:2]

        # Cap the work: each person costs a full MediaPipe pass, so a crowd would
        # otherwise stall the stream. Largest boxes are the most useful ones.
        targets = sorted(person_detections, key=lambda d: d.area, reverse=True)
        targets = targets[:max_persons]

        for det in targets:
            # Crop person ROI with a small margin
            margin = 10
            x1 = max(0, det.x1 - margin)
            y1 = max(0, det.y1 - margin)
            x2 = min(w, det.x2 + margin)
            y2 = min(h, det.y2 + margin)

            if x2 <= x1 or y2 <= y1:
                continue

            # A column slice of an (H, W, 3) array is not C-contiguous, and
            # MediaPipe's process() rejects non-contiguous input outright.
            # ascontiguousarray also gives us the BGR buffer we draw into, so
            # no full-frame colour conversion is needed.
            roi_bgr = np.ascontiguousarray(frame[y1:y2, x1:x2])
            if roi_bgr.size == 0:
                continue

            roi_rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
            results = pose_solution.process(roi_rgb)

            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    roi_bgr,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=_pose_landmark_spec,
                    connection_drawing_spec=_pose_connection_spec,
                )
                frame[y1:y2, x1:x2] = roi_bgr
