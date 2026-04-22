import queue
import threading
import time
import datetime

import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import streamlit as st

import config
import profile_manager
from gestures import GestureDetector

_PROFILE_KEYS = (
    "smooth_factor", "pinch_threshold", "click_cooldown",
    "scroll_sensitivity", "drag_threshold", "double_click_window",
)


def _apply_profile(rt: dict, profile: dict) -> None:
    for k in _PROFILE_KEYS:
        if k in profile:
            rt[k] = profile[k]

pyautogui.FAILSAFE = False
_mp_hands = mp.solutions.hands
_mp_draw = mp.solutions.drawing_utils
_screen_w, _screen_h = pyautogui.size()


# ── Rendering helpers ─────────────────────────────────────────────────────────

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


# ── Coordinate helper ─────────────────────────────────────────────────────────

def _to_screen(nx: float, ny: float) -> tuple[int, int]:
    x_min, x_max = config.MAP_X
    y_min, y_max = config.MAP_Y
    x = float(np.clip((nx - x_min) / (x_max - x_min), 0.0, 1.0))
    y = float(np.clip((ny - y_min) / (y_max - y_min), 0.0, 1.0))
    return int(x * _screen_w), int(y * _screen_h)


# ── Camera thread ─────────────────────────────────────────────────────────────

def _camera_loop(
    frame_q: queue.Queue,
    event_q: queue.Queue,
    stop_evt: threading.Event,
    rt: dict,
) -> None:
    gesture    = GestureDetector()
    prev_x     = prev_y = 0
    last_rc_t  = 0.0
    scroll_y   = None
    fps_times: list[float] = []
    prev_label = "none"

    cap = cv2.VideoCapture(config.CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAM_H)

    with _mp_hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    ) as hands:
        while not stop_evt.is_set():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            now = time.time()
            fps_times = [t for t in fps_times if now - t < 1.0]
            fps_times.append(now)
            fps = len(fps_times)

            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            # Read runtime config (GIL-safe dict reads)
            ctrl     = rt.get("control_active",    False)
            smooth   = rt.get("smooth_factor",     config.SMOOTH_FACTOR)
            click_cd = rt.get("click_cooldown",    config.CLICK_COOLDOWN)
            scroll_s = rt.get("scroll_sensitivity", config.SCROLL_SENSITIVITY)

            # Patch module-level thresholds so GestureDetector uses updated values
            config.PINCH_THRESHOLD      = rt.get("pinch_threshold",    config.PINCH_THRESHOLD)
            config.DRAG_THRESHOLD_SEC   = rt.get("drag_threshold",     config.DRAG_THRESHOLD_SEC)
            config.DOUBLE_CLICK_WINDOW  = rt.get("double_click_window", config.DOUBLE_CLICK_WINDOW)

            label  = "none"
            fh, fw = frame.shape[:2]

            if result.multi_hand_landmarks:
                lm = result.multi_hand_landmarks[0].landmark
                gesture.update(lm)

                if gesture.is_scroll_mode():
                    label = "scroll"
                    if scroll_y is not None:
                        delta = gesture.get_scroll_delta(scroll_y)
                        amt   = -int(delta * scroll_s * 100)
                        if amt and ctrl:
                            pyautogui.scroll(amt)
                    scroll_y = lm[8].y
                    cv2.putText(frame, "SCROLL", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 80, 0), 2)

                else:
                    scroll_y = None
                    nx, ny   = gesture.cursor_position()
                    sx, sy   = _to_screen(nx, ny)
                    cx = int(prev_x + (sx - prev_x) * smooth)
                    cy = int(prev_y + (sy - prev_y) * smooth)
                    prev_x, prev_y = cx, cy

                    if ctrl:
                        pyautogui.moveTo(cx, cy)

                    if gesture.drag_just_started():
                        label = "drag"
                        if ctrl:
                            pyautogui.mouseDown()
                    elif gesture.drag_just_ended():
                        label = "drag"
                        if ctrl:
                            pyautogui.mouseUp()
                    elif gesture.is_dragging():
                        label = "drag"
                    else:
                        action = gesture.get_click_action()
                        if action == "click":
                            label = "click"
                            if ctrl:
                                pyautogui.click()
                        elif action == "double_click":
                            label = "double"
                            if ctrl:
                                pyautogui.doubleClick()
                            cv2.putText(frame, "DOUBLE CLICK", (10, 80),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 2)
                        elif gesture.is_left_click():
                            label = "pinch"
                        elif gesture.is_right_click():
                            label = "right_click"
                        else:
                            label = "idle"

                    if gesture.is_right_click() and (now - last_rc_t) > click_cd:
                        label = "right_click"
                        if ctrl:
                            pyautogui.rightClick()
                        last_rc_t = now

                    tip = (int(nx * fw), int(ny * fh))
                    if gesture.is_dragging():
                        cv2.circle(frame, tip, 16, (0, 0, 255), -1)
                        cv2.putText(frame, "DRAG", (10, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
                    else:
                        cv2.circle(frame, tip, 8, (0, 255, 0), -1)

                _mp_draw.draw_landmarks(
                    frame, result.multi_hand_landmarks[0], _mp_hands.HAND_CONNECTIONS,
                )

            # Log gesture transitions (skip idle/none)
            if label != prev_label and label not in ("none", "idle"):
                ts = datetime.datetime.now().strftime("%H:%M:%S")
                try:
                    event_q.put_nowait({"ts": ts, "gesture": label})
                except queue.Full:
                    pass
            prev_label = label

            # Push frame; drop stale entry if queue is full
            payload = {
                "frame":   cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                "fps":     fps,
                "gesture": label,
            }
            if frame_q.full():
                try:
                    frame_q.get_nowait()
                except queue.Empty:
                    pass
            try:
                frame_q.put_nowait(payload)
            except queue.Full:
                pass

    cap.release()


# ── Streamlit app ─────────────────────────────────────────────────────────────

st.set_page_config(layout="wide", page_title="HandCursor")
st.title("HandCursor – Live Gestensteuerung")


def _init_state() -> None:
    if "frame_q" not in st.session_state:
        st.session_state.frame_q = queue.Queue(maxsize=2)
    if "event_q" not in st.session_state:
        st.session_state.event_q = queue.Queue(maxsize=20)
    if "stop_evt" not in st.session_state:
        st.session_state.stop_evt = threading.Event()
    if "rt" not in st.session_state:
        st.session_state.rt = {
            "control_active":      False,
            "smooth_factor":       config.SMOOTH_FACTOR,
            "pinch_threshold":     config.PINCH_THRESHOLD,
            "click_cooldown":      config.CLICK_COOLDOWN,
            "scroll_sensitivity":  config.SCROLL_SENSITIVITY,
            "drag_threshold":      config.DRAG_THRESHOLD_SEC,
            "double_click_window": config.DOUBLE_CLICK_WINDOW,
        }
        try:
            _apply_profile(st.session_state.rt, profile_manager.load_profile("default"))
        except FileNotFoundError:
            pass
    if "active_profile" not in st.session_state:
        st.session_state.active_profile = "default"
    if "gesture_log" not in st.session_state:
        st.session_state.gesture_log = []


_init_state()

# Start camera thread on first load or after crash
if "cam_thread" not in st.session_state or not st.session_state.cam_thread.is_alive():
    st.session_state.stop_evt.clear()
    _t = threading.Thread(
        target=_camera_loop,
        args=(
            st.session_state.frame_q,
            st.session_state.event_q,
            st.session_state.stop_evt,
            st.session_state.rt,
        ),
        daemon=True,
    )
    _t.start()
    st.session_state.cam_thread = _t

rt   = st.session_state.rt
glog = st.session_state.gesture_log

# ── Two-column layout ─────────────────────────────────────────────────────────
col_left, col_right = st.columns([2, 1])

with col_right:
    # ── Profile section ───────────────────────────────────────────────────────
    st.subheader("Profil")
    profiles = profile_manager.list_profiles()
    active   = st.session_state.active_profile
    sel_idx  = profiles.index(active) if active in profiles else 0
    selected = st.selectbox("Profil wählen", profiles, index=sel_idx)
    st.caption(f"Aktiv: **{active}**")

    if st.button("Laden", use_container_width=True):
        _apply_profile(rt, profile_manager.load_profile(selected))
        st.session_state.active_profile = selected
        st.rerun()

    with st.expander("Profil speichern"):
        save_name = st.text_input("Name:", value=active, key="save_name_input")
        if st.button("Speichern", key="btn_save_profile"):
            settings = {"name": save_name, **{k: rt[k] for k in _PROFILE_KEYS}}
            profile_manager.save_profile(save_name, settings)
            st.session_state.active_profile = save_name
            st.success(f"Profil '{save_name}' gespeichert.")

    st.divider()

    # ── Settings form ─────────────────────────────────────────────────────────
    st.subheader("Einstellungen")
    with st.form("cfg_form"):
        smooth   = st.slider("Smooth Factor",          0.05, 1.0,  float(rt["smooth_factor"]),       0.05)
        pinch    = st.slider("Pinch Threshold",         0.01, 0.15, float(rt["pinch_threshold"]),     0.005, format="%.3f")
        cooldown = st.slider("Click Cooldown (s)",      0.1,  1.0,  float(rt["click_cooldown"]),      0.05)
        scroll_s = st.slider("Scroll Sensitivity",      1,    30,   int(rt["scroll_sensitivity"]),    1)
        drag_thr = st.slider("Drag Threshold (s)",      0.1,  1.0,  float(rt["drag_threshold"]),      0.05)
        dc_win   = st.slider("Double-Click Fenster (s)", 0.1, 0.8,  float(rt["double_click_window"]), 0.05)
        apply    = st.form_submit_button("Übernehmen")
        if apply:
            rt["smooth_factor"]       = smooth
            rt["pinch_threshold"]     = pinch
            rt["click_cooldown"]      = cooldown
            rt["scroll_sensitivity"]  = scroll_s
            rt["drag_threshold"]      = drag_thr
            rt["double_click_window"] = dc_win

    ctrl = st.checkbox(
        "Steuerung aktiv",
        value=rt.get("control_active", False),
        help="Wenn deaktiviert: Gesten werden erkannt, aber Maus wird nicht bewegt.",
    )
    rt["control_active"] = ctrl

    st.divider()
    st.subheader("Gesten-Log")
    log_ph = st.empty()
    log_ph.markdown(_log_table(glog), unsafe_allow_html=True)

with col_left:
    frame_ph = st.empty()
    badge_ph = st.empty()
    fps_ph   = st.empty()

# ── Streaming loop ────────────────────────────────────────────────────────────
fq = st.session_state.frame_q
eq = st.session_state.event_q

while True:
    try:
        d = fq.get(timeout=0.08)
        frame_ph.image(d["frame"], channels="RGB", use_container_width=True)
        badge_ph.markdown(_badge(d["gesture"]), unsafe_allow_html=True)
        fps_ph.caption(f"FPS: {d['fps']}")
    except queue.Empty:
        pass

    changed = False
    while not eq.empty():
        try:
            glog.insert(0, eq.get_nowait())
            changed = True
        except queue.Empty:
            break

    if len(glog) > 10:
        del glog[10:]

    if changed:
        log_ph.markdown(_log_table(glog), unsafe_allow_html=True)

    time.sleep(0.033)
