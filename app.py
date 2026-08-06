"""HandCursor — Streamlit UI with live camera feed, profiles and settings.

Start via the launcher (``./start.sh ui``) or ``streamlit run app.py``.

The camera is owned by :mod:`camera`, not by this page, so navigating to the
calibration page hands the device over cleanly instead of opening it twice.
"""

import datetime
import time

import streamlit as st

import camera
import config
import profile_manager
import runtime
from gestures import GestureDetector

_OWNER = "main"

# Worker-thread state. Process-global to match the camera hub's scope: the
# processor closure is rebuilt on every Streamlit rerun, but this must not be.
_STATE: dict = {
    "detector":    None,
    "prev_x":      0,
    "prev_y":      0,
    "last_rc":     0.0,
    "scroll_prev": None,
    "prev_label":  "none",
    "log":         [],
    "dc_until":    0.0,
}

_BADGES: dict[str, tuple[str, str, str]] = {
    "idle":        ("Bereit",       "#27ae60", "#fff"),
    "pinch":       ("PINCH",        "#f39c12", "#000"),
    "right_click": ("RECHTSKLICK",  "#d35400", "#fff"),
    "scroll":      ("SCROLL",       "#2980b9", "#fff"),
    "drag":        ("DRAG",         "#c0392b", "#fff"),
    "double":      ("DOPPELKLICK",  "#8e44ad", "#fff"),
    "click":       ("KLICK",        "#16a085", "#fff"),
    "none":        ("Keine Hand",   "#7f8c8d", "#fff"),
}

_screen_cache: list = []


def _screen_size():
    """Screen size, resolved lazily so importing this module stays headless-safe."""
    if not _screen_cache:
        import pyautogui
        _screen_cache.append(pyautogui.size())
    return _screen_cache[0]


def _badge(label: str) -> str:
    text, bg, fg = _BADGES.get(label, _BADGES["none"])
    return (
        f'<span style="background:{bg};color:{fg};padding:5px 16px;'
        f'border-radius:10px;font-weight:bold;font-size:1.1rem">{text}</span>'
    )


def _log_table(entries: list) -> str:
    if not entries:
        return "<i style='color:#999'>Noch keine Gesten erkannt.</i>"
    rows = "".join(
        f'<tr>'
        f'<td style="color:#888;font-size:0.78rem;white-space:nowrap;padding:3px 0">{e["ts"]}</td>'
        f'<td style="padding-left:10px">{_badge(e["gesture"])}</td>'
        f'</tr>'
        for e in entries
    )
    return f'<table style="border-collapse:collapse;width:100%">{rows}</table>'


def _to_screen(nx: float, ny: float, settings: dict) -> tuple[int, int]:
    screen_w, screen_h = _screen_size()
    x_min, x_max = settings["map_x"]
    y_min, y_max = settings["map_y"]
    x = min(max((nx - x_min) / (x_max - x_min), 0.0), 1.0)
    y = min(max((ny - y_min) / (y_max - y_min), 0.0), 1.0)
    return int(x * screen_w), int(y * screen_h)


# ── Frame processor (runs on the camera worker thread) ────────────────────

def _process(frame, result) -> dict:
    """Annotate the frame and drive the mouse. Never calls st.*."""
    import cv2
    import mediapipe as mp
    import pyautogui

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    settings = runtime.snapshot()
    control = bool(runtime.flag("control_active", False))

    detector = _STATE["detector"]
    if detector is None:
        detector = _STATE["detector"] = GestureDetector()
    detector.set_settings(settings)

    landmarks = (result.multi_hand_landmarks[0].landmark
                 if result.multi_hand_landmarks else None)
    detector.update(landmarks)
    action = detector.get_click_action()   # every frame, see gestures.py

    now = time.time()
    frame_h, frame_w = frame.shape[:2]
    label = "none"

    if landmarks is None:
        _STATE["scroll_prev"] = None
    elif detector.is_scroll_mode():
        label = "scroll"
        prev = _STATE["scroll_prev"]
        if prev is not None:
            amount = -int(detector.get_scroll_delta(prev) * settings["scroll_sensitivity"] * 100)
            if amount and control:
                pyautogui.scroll(amount)
        _STATE["scroll_prev"] = landmarks[8].y
        cv2.putText(frame, "SCROLL", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 80, 0), 2)
    else:
        _STATE["scroll_prev"] = None
        nx, ny = detector.cursor_position()
        sx, sy = _to_screen(nx, ny, settings)
        smooth = settings["smooth_factor"]
        cx = int(_STATE["prev_x"] + (sx - _STATE["prev_x"]) * smooth)
        cy = int(_STATE["prev_y"] + (sy - _STATE["prev_y"]) * smooth)
        _STATE["prev_x"], _STATE["prev_y"] = cx, cy
        if control:
            pyautogui.moveTo(cx, cy)

        tip = (int(nx * frame_w), int(ny * frame_h))
        if detector.is_dragging():
            label = "drag"
            cv2.circle(frame, tip, 16, (0, 0, 255), -1)
            cv2.putText(frame, "DRAG", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
        else:
            cv2.circle(frame, tip, 8, (0, 255, 0), -1)
            if detector.is_left_click():
                label = "pinch"
            elif detector.is_right_click():
                label = "right_click"
            else:
                label = "idle"

    # ── Dispatch (identical to hand_cursor.py) ───────────────────────────
    if detector.drag_just_started():
        label = "drag"
        if control:
            pyautogui.mouseDown()
    elif detector.drag_just_ended():
        label = "drag"
        if control:
            pyautogui.mouseUp()

    if action == "click":
        label = "click"
        if control:
            pyautogui.click()
    elif action == "double_click":
        label = "double"
        if control:
            pyautogui.doubleClick()
        _STATE["dc_until"] = now + 0.5

    if (detector.right_click_just_fired()
            and now - _STATE["last_rc"] > settings["click_cooldown"]):
        label = "right_click"
        if control:
            pyautogui.rightClick()
        _STATE["last_rc"] = now

    if result.multi_hand_landmarks:
        mp_draw.draw_landmarks(frame, result.multi_hand_landmarks[0],
                               mp_hands.HAND_CONNECTIONS)

    if now < _STATE["dc_until"]:
        cv2.putText(frame, "DOUBLE CLICK", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 2)
    if not control:
        cv2.putText(frame, "STEUERUNG AUS", (10, frame_h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

    if label != _STATE["prev_label"] and label not in ("none", "idle"):
        _STATE["log"].insert(0, {
            "ts": datetime.datetime.now().strftime("%H:%M:%S"), "gesture": label})
        del _STATE["log"][10:]
    _STATE["prev_label"] = label

    return {
        "frame":   cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
        "gesture": label,
        "log":     list(_STATE["log"]),
    }


# ── Page ──────────────────────────────────────────────────────────────────

st.set_page_config(layout="wide", page_title="HandCursor")
st.title("HandCursor – Live Gestensteuerung")

if "profile_loaded" not in st.session_state:
    runtime.load_startup_profile()
    st.session_state.profile_loaded = True

camera.acquire(_OWNER, _process)

settings = runtime.snapshot()
col_left, col_right = st.columns([2, 1])

with col_right:
    # ── Profiles ──────────────────────────────────────────────────────────
    st.subheader("Profil")
    profiles = profile_manager.list_profiles()
    active = runtime.active_profile()

    if not profiles:
        st.info("Keine Profile gefunden.")
        if st.button("Standardprofil anlegen", use_container_width=True):
            profile_manager.save_profile("default", runtime.as_profile("default"))
            st.rerun()
    else:
        index = profiles.index(active) if active in profiles else 0
        selected = st.selectbox("Profil wählen", profiles, index=index)
        st.caption(f"Aktiv: **{active or 'Standardwerte'}**")
        if st.button("Laden", use_container_width=True):
            runtime.apply_profile(selected)
            st.rerun()

    with st.expander("Profil speichern"):
        save_name = st.text_input("Name:", value=active or "mein-profil",
                                  key="save_name_input")
        if st.button("Speichern", key="btn_save_profile"):
            try:
                # runtime.as_profile carries *every* setting including
                # map_x/map_y, so a calibrated mapping cannot be lost here.
                profile_manager.save_profile(save_name, runtime.as_profile(save_name))
                runtime.apply_profile(save_name)
                st.session_state.flash = f"Profil '{save_name}' gespeichert."
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))

    if flash := st.session_state.pop("flash", None):
        st.success(flash)

    st.divider()

    # ── Settings ──────────────────────────────────────────────────────────
    st.subheader("Einstellungen")
    with st.form("cfg_form"):
        smooth = st.slider("Smooth Factor", 0.05, 1.0,
                           float(settings["smooth_factor"]), 0.05)
        pinch = st.slider("Pinch Threshold", 0.01, 0.15,
                          float(settings["pinch_threshold"]), 0.005, format="%.3f")
        cooldown = st.slider("Click Cooldown (s)", 0.1, 1.0,
                             float(settings["click_cooldown"]), 0.05)
        scroll_s = st.slider("Scroll Sensitivity", 1, 30,
                             int(settings["scroll_sensitivity"]), 1)
        drag_thr = st.slider("Drag Threshold (s)", 0.1, 1.0,
                             float(settings["drag_threshold"]), 0.05)
        dc_win = st.slider("Double-Click Fenster (s)", 0.1, 0.8,
                           float(settings["double_click_window"]), 0.05)
        if st.form_submit_button("Übernehmen"):
            runtime.update(smooth_factor=smooth, pinch_threshold=pinch,
                           click_cooldown=cooldown, scroll_sensitivity=scroll_s,
                           drag_threshold=drag_thr, double_click_window=dc_win)
            st.rerun()

    runtime.set_flag("control_active", st.checkbox(
        "Steuerung aktiv",
        value=bool(runtime.flag("control_active", False)),
        help="Wenn deaktiviert: Gesten werden erkannt, aber die Maus wird nicht bewegt.",
    ))

    if st.button("Kamera freigeben", use_container_width=True,
                 help="Stoppt den Kamera-Thread und gibt das Gerät frei."):
        camera.stop()
        st.rerun()

    st.divider()
    st.subheader("Gesten-Log")
    log_ph = st.empty()

with col_left:
    frame_ph = st.empty()
    badge_ph = st.empty()
    fps_ph = st.empty()
    error_ph = st.empty()

# ── Streaming loop ────────────────────────────────────────────────────────
_last_log: list = []

while True:
    payload = camera.latest(_OWNER)
    state = camera.status()

    if state.error:
        error_ph.error(state.error)
    elif not state.running:
        error_ph.info("Kamera gestoppt. Seite neu laden, um sie erneut zu starten.")
    elif not camera.HUB.owns(_OWNER):
        error_ph.info("Die Kamera wird gerade von der Kalibrierung verwendet.")
    else:
        error_ph.empty()

    if payload is not None:
        frame_ph.image(payload["frame"], channels="RGB", use_container_width=True)
        badge_ph.markdown(_badge(payload["gesture"]), unsafe_allow_html=True)
        fps_ph.caption(f"FPS: {state.fps}")
        if payload["log"] != _last_log:
            _last_log = payload["log"]
            log_ph.markdown(_log_table(_last_log), unsafe_allow_html=True)

    time.sleep(0.033)
