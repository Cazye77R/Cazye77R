"""
Live Camera Detection & Body Tracking — Streamlit App

Modes:
  - Objekterkennung  : Alle COCO-Objekte (kein Person-Filter)
  - Personenerkennung: Nur Personen + Körper-Skeleton
  - Beides           : Objekte + Personen + optional Skeleton

Start: streamlit run camera_detection/app.py
"""
from __future__ import annotations

import logging
import threading

import av
import streamlit as st
from streamlit_webrtc import VideoProcessorBase, webrtc_streamer, WebRtcMode

from camera_detection.detector import CameraDetector

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
MODE_MAP: dict[str, str] = {
    "Objekterkennung": "objects",
    "Personenerkennung": "persons",
    "Beides": "both",
}

RESOLUTIONS: dict[str, tuple[int, int]] = {
    "640 × 480 — schnell": (640, 480),
    "1280 × 720 — ausgewogen": (1280, 720),
    "1920 × 1080 — hohe Details": (1920, 1080),
}

# COCO class names in class-id order; the index IS the id YOLO reports.
COCO_CLASSES: list[str] = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Kamera-Erkennung",
    page_icon="🎥",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS tweaks (matches existing dark theme)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; }
    .stats-box {
        background: #0f172a;
        border: 1px solid #22d3ee44;
        border-radius: 8px;
        padding: 0.6rem 1rem;
        margin-top: 0.5rem;
        font-size: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state defaults — initialised once per session so sidebar values
# survive Streamlit reruns triggered by widget interaction.
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, object] = {
    "mode_label": "Beides",
    "show_boxes": True,
    "show_labels": True,
    "show_pose": True,
    "model_size": "yolov8n",
    "confidence": 0.50,
    "class_names": [],
    "resolution_label": "1280 × 720 — ausgewogen",
    "max_pose_persons": 4,
}
for _key, _val in _DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ---------------------------------------------------------------------------
# Per-session detector.
#
# NOT st.cache_resource: that cache is process-global, so every browser tab
# would share one detector and fight over its settings. The YOLO *weights* are
# still shared process-wide via detector._yolo_model_cache, which is safe
# because the weights themselves are stateless.
# ---------------------------------------------------------------------------
if "detector" not in st.session_state:
    try:
        st.session_state.detector = CameraDetector()
        logger.info("CameraDetector initialisiert")
    except ImportError as exc:
        st.error(
            f"**Fehlende Abhängigkeit:** {exc}\n\n"
            "Bitte alle Pakete installieren:\n"
            "```\n./start.sh --setup\n```"
        )
        st.stop()
    except Exception as exc:
        st.error(
            f"**Die App konnte nicht gestartet werden.**\n\n{exc}\n\n"
            "Stelle sicher, dass alle Pakete installiert sind:\n"
            "```\n./start.sh --setup\n```"
        )
        st.stop()

detector: CameraDetector = st.session_state.detector

# ---------------------------------------------------------------------------
# Sidebar — settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Einstellungen")
    st.markdown("---")

    mode_label = st.radio(
        "Erkennungsmodus",
        options=list(MODE_MAP.keys()),
        key="mode_label",
    )
    mode = MODE_MAP[mode_label]

    class_names = st.multiselect(
        "Klassenfilter",
        options=COCO_CLASSES,
        key="class_names",
        help="Leer = alle Klassen des gewählten Modus.",
    )
    selected_classes = [COCO_CLASSES.index(name) for name in class_names]

    st.markdown("---")
    st.subheader("Anzeige")
    show_boxes = st.toggle("Rahmen anzeigen", key="show_boxes")
    show_labels = st.toggle("Beschriftung anzeigen", key="show_labels")

    pose_disabled = mode == "objects"
    show_pose = st.toggle(
        "Körper-Tracking (Skeleton)",
        key="show_pose",
        disabled=pose_disabled,
        help="Nur verfügbar bei Personenerkennung oder 'Beides'",
    )
    if pose_disabled:
        show_pose = False

    max_pose_persons = st.slider(
        "Max. Personen für Skeleton",
        min_value=1,
        max_value=10,
        key="max_pose_persons",
        disabled=pose_disabled or not show_pose,
        help="Jede Person kostet einen eigenen MediaPipe-Durchlauf pro Frame.",
    )

    st.markdown("---")
    st.subheader("Modell & Kamera")
    model_size = st.selectbox(
        "Modellgröße",
        options=["yolov8n", "yolov8s", "yolov8m"],
        key="model_size",
        format_func=lambda x: {
            "yolov8n": "YOLOv8n — schnell",
            "yolov8s": "YOLOv8s — ausgewogen",
            "yolov8m": "YOLOv8m — genau",
        }[x],
    )
    resolution_label = st.selectbox(
        "Kamera-Auflösung",
        options=list(RESOLUTIONS.keys()),
        key="resolution_label",
        help="Wird beim nächsten Kamerastart angewendet.",
    )
    cam_width, cam_height = RESOLUTIONS[resolution_label]

    confidence = st.slider(
        "Konfidenzschwelle",
        min_value=0.1,
        max_value=0.95,
        key="confidence",
        step=0.05,
        format="%.2f",
    )

    # Push settings to detector
    detector.update_settings(
        model_size=model_size,
        mode=mode,
        show_boxes=show_boxes,
        show_labels=show_labels,
        show_pose=show_pose,
        confidence=confidence,
        selected_classes=selected_classes,
        max_pose_persons=max_pose_persons,
    )

    st.markdown("---")
    st.caption(
        "Erkannte Klassen: COCO (80 Kategorien).\n\n"
        "Skeleton: MediaPipe Pose (33 Landmarken)."
    )

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("Live Kamera-Erkennung & Körper-Tracking")
st.caption(
    "Wähle links den Modus, schalte Rahmen/Beschriftung ein oder aus und starte die Kamera."
)

# Preload weights on the main thread. Doing this lazily inside the video worker
# would stall the stream — the first run has to download the weights file.
try:
    with st.spinner(f"Lade Modell {model_size} …"):
        detector.ensure_model_loaded()
except Exception as exc:
    st.error(f"**Modell konnte nicht geladen werden.**\n\n{exc}")
    st.stop()

# ---------------------------------------------------------------------------
# WebRTC Video Processor
# ---------------------------------------------------------------------------

class VideoProcessor(VideoProcessorBase):
    """Processes each video frame through the session's CameraDetector."""

    def __init__(self, detector: CameraDetector) -> None:
        self._detector = detector
        self._stats_lock = threading.Lock()
        self.latest_stats: dict = {
            "fps": 0.0,
            "person_count": 0,
            "object_count": 0,
            "dropped": 0,
        }
        self._dropped = 0

    def get_stats(self) -> dict:
        with self._stats_lock:
            return dict(self.latest_stats)

    def recv_queued(self, frames: list[av.VideoFrame]) -> list[av.VideoFrame]:
        # Discard all but the newest frame to avoid queue buildup when
        # YOLO inference is slower than the incoming camera framerate.
        self._dropped += len(frames) - 1
        frame = frames[-1]
        try:
            img = frame.to_ndarray(format="bgr24")
            annotated, stats = self._detector.detect(img)

            with self._stats_lock:
                self.latest_stats = {**stats, "dropped": self._dropped}

            return [av.VideoFrame.from_ndarray(annotated, format="bgr24")]
        except Exception:
            logger.exception("Fehler bei der Frame-Verarbeitung in recv_queued")
            return [frame]


# ---------------------------------------------------------------------------
# Stream widget
# ---------------------------------------------------------------------------
ctx = webrtc_streamer(
    key="camera-detection",
    mode=WebRtcMode.SENDRECV,
    video_processor_factory=lambda: VideoProcessor(detector),
    media_stream_constraints={
        "video": {
            "width": {"ideal": cam_width},
            "height": {"ideal": cam_height},
            "frameRate": {"ideal": 30},
        },
        "audio": False,
    },
    async_processing=True,
    rtc_configuration={
        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
    },
)


# ---------------------------------------------------------------------------
# Live stats display
#
# Rendered inside a fragment so it refreshes on its own timer. A plain block
# would only repaint on a full script rerun, i.e. when the user touches a
# widget — leaving the numbers frozen while the stream runs.
# ---------------------------------------------------------------------------
@st.fragment(run_every=1.0)
def render_stats() -> None:
    if ctx.state.playing and ctx.video_processor:
        stats = ctx.video_processor.get_stats()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("FPS", stats.get("fps", 0))
        with col2:
            st.metric("Personen", stats.get("person_count", 0))
        with col3:
            st.metric("Objekte", stats.get("object_count", 0))
        with col4:
            st.metric(
                "Verworfene Frames",
                stats.get("dropped", 0),
                help="Übersprungene Kamerabilder, wenn die Erkennung nicht hinterherkommt.",
            )
    else:
        st.info("Kamera starten, um die Erkennung zu aktivieren.")


render_stats()

# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    """
    **Legende:**
    - 🟡 Gelber Rahmen → Objekte (Nicht-Personen)
    - 🔵 Cyan-Rahmen → Personen
    - 🟢 Grünes Skeleton → Körper-Tracking (MediaPipe Pose)
    """
)
