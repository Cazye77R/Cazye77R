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
}
for _key, _val in _DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ---------------------------------------------------------------------------
# Shared detector instance (created once per session)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_detector() -> CameraDetector:
    return CameraDetector()


try:
    detector = get_detector()
    logger.info("CameraDetector initialisiert (Modell: %s)", detector.model_size)
except ImportError as exc:
    st.error(
        f"**Fehlende Abhängigkeit:** {exc}\n\n"
        "Bitte alle Pakete installieren:\n"
        "```\npip install opencv-python-headless ultralytics mediapipe "
        "streamlit-webrtc av\n```"
    )
    st.stop()
except Exception as exc:
    st.error(
        f"**Die App konnte nicht gestartet werden.**\n\n{exc}\n\n"
        "Stelle sicher, dass folgende Pakete korrekt installiert sind: "
        "`opencv-python-headless`, `ultralytics`, `mediapipe`, `streamlit-webrtc`, `av`."
    )
    st.stop()

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

    st.markdown("---")
    st.subheader("Modell")
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

# Stats placeholder — updated by VideoProcessor via session state
stats_placeholder = st.empty()

# ---------------------------------------------------------------------------
# WebRTC Video Processor
# ---------------------------------------------------------------------------

class VideoProcessor(VideoProcessorBase):
    """Processes each video frame through the shared CameraDetector."""

    def __init__(self) -> None:
        self._stats_lock = threading.Lock()
        self.latest_stats: dict = {"fps": 0.0, "person_count": 0, "object_count": 0}

    def get_stats(self) -> dict:
        with self._stats_lock:
            return dict(self.latest_stats)

    def recv_queued(self, frames: list[av.VideoFrame]) -> list[av.VideoFrame]:
        # Discard all but the newest frame to avoid queue buildup when
        # YOLO inference is slower than the incoming camera framerate.
        frame = frames[-1]
        try:
            img = frame.to_ndarray(format="bgr24")
            annotated, stats = detector.detect(img)

            with self._stats_lock:
                self.latest_stats = stats

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
    video_processor_factory=VideoProcessor,
    media_stream_constraints={"video": True, "audio": False},
    async_processing=True,
    rtc_configuration={
        "iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]
    },
)

# ---------------------------------------------------------------------------
# Live stats display
# ---------------------------------------------------------------------------
if ctx.state.playing and ctx.video_processor:
    stats = ctx.video_processor.get_stats()

    with stats_placeholder.container():
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("FPS", stats.get("fps", 0))
        with col2:
            st.metric("Personen", stats.get("person_count", 0))
        with col3:
            st.metric("Objekte", stats.get("object_count", 0))
else:
    with stats_placeholder.container():
        st.info("Kamera starten, um die Erkennung zu aktivieren.")

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
