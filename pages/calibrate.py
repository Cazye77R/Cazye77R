import queue
import threading
import time

import cv2
import mediapipe as mp
import numpy as np
import streamlit as st

import config
import profile_manager

_mp_hands = mp.solutions.hands
_mp_draw  = mp.solutions.drawing_utils
_STEPS    = 3


# ── Camera thread ─────────────────────────────────────────────────────────────

def _calib_thread(frame_q: queue.Queue, stop_evt: threading.Event, cs: dict) -> None:
    smooth_cx = smooth_cy = 0.5

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

            frame  = cv2.flip(frame, 1)
            rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            step       = cs.get("step", 1)
            collecting = cs.get("collecting", False)
            has_hand   = bool(result.multi_hand_landmarks)
            pinch_dist = None
            fh, fw     = frame.shape[:2]

            if has_hand:
                lm  = result.multi_hand_landmarks[0].landmark
                tip = np.array([lm[8].x, lm[8].y])
                thmb = np.array([lm[4].x, lm[4].y])
                pinch_dist = float(np.linalg.norm(tip - thmb))

                # ── Step 1: collect pinch distances ──────────────────────────
                if step == 1 and collecting:
                    cs["step1_distances"].append(pinch_dist)
                    if len(cs["step1_distances"]) >= 30:
                        cs["collecting"]  = False
                        cs["step1_done"]  = True

                # ── Step 2: track bounding box of index fingertip ─────────────
                elif step == 2 and collecting:
                    cs["x_min"] = min(cs["x_min"], lm[8].x)
                    cs["x_max"] = max(cs["x_max"], lm[8].x)
                    cs["y_min"] = min(cs["y_min"], lm[8].y)
                    cs["y_max"] = max(cs["y_max"], lm[8].y)

                # ── Step 3: animated smooth cursor preview ────────────────────
                elif step == 3:
                    s = cs.get("smooth_factor", 0.3)
                    smooth_cx += (lm[8].x - smooth_cx) * s
                    smooth_cy += (lm[8].y - smooth_cy) * s
                    cv2.circle(frame,
                               (int(smooth_cx * fw), int(smooth_cy * fh)),
                               22, (255, 100, 0), -1)
                    cv2.circle(frame,
                               (int(lm[8].x * fw), int(lm[8].y * fh)),
                               7, (0, 255, 0), -1)

                # ── Overlays for steps 1 & 2 ─────────────────────────────────
                if step in (1, 2):
                    cv2.circle(frame,
                               (int(lm[8].x * fw), int(lm[8].y * fh)),
                               9, (0, 255, 0), -1)

                if step == 1:
                    cv2.putText(frame, f"Pinch: {pinch_dist:.3f}", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)
                    if collecting:
                        n = len(cs["step1_distances"])
                        cv2.putText(frame, f"Frame {n}/30", (10, 75),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

                if step == 2 and cs["x_max"] > cs["x_min"]:
                    pt1 = (int(cs["x_min"] * fw), int(cs["y_min"] * fh))
                    pt2 = (int(cs["x_max"] * fw), int(cs["y_max"] * fh))
                    cv2.rectangle(frame, pt1, pt2, (0, 255, 100), 2)
                    cv2.putText(frame, "Erfasster Bereich", (pt1[0], max(pt1[1] - 8, 12)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 1)

                _mp_draw.draw_landmarks(
                    frame, result.multi_hand_landmarks[0], _mp_hands.HAND_CONNECTIONS,
                )

            payload = {
                "frame":      cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                "has_hand":   has_hand,
                "pinch_dist": pinch_dist,
            }
            if frame_q.full():
                try:    frame_q.get_nowait()
                except: pass
            try:    frame_q.put_nowait(payload)
            except: pass

    cap.release()


# ── State helpers ─────────────────────────────────────────────────────────────

def _fresh_cs() -> dict:
    return {
        "step":            1,
        "collecting":      False,
        # step 1
        "step1_distances": [],
        "step1_done":      False,
        # step 2
        "x_min": 1.0, "x_max": 0.0,
        "y_min": 1.0, "y_max": 0.0,
        # step 3
        "smooth_factor":   config.SMOOTH_FACTOR,
        # results
        "result_threshold": None,
        "result_map_x":     None,
        "result_map_y":     None,
        "result_smooth":    None,
    }


def _reset(cs: dict) -> None:
    cs.clear()
    cs.update(_fresh_cs())
    for flag in ("_s1_notified",):
        st.session_state.pop(flag, None)


# ── App ───────────────────────────────────────────────────────────────────────

st.set_page_config(layout="wide", page_title="HandCursor – Kalibrierung")
st.title("Kalibrierungs-Wizard")

# Session state
if "calib_fq" not in st.session_state:
    st.session_state.calib_fq = queue.Queue(maxsize=2)
if "calib_stop" not in st.session_state:
    st.session_state.calib_stop = threading.Event()
if "cs" not in st.session_state:
    st.session_state.cs = _fresh_cs()

# Camera thread
if "calib_thread" not in st.session_state or not st.session_state.calib_thread.is_alive():
    st.session_state.calib_stop.clear()
    _t = threading.Thread(
        target=_calib_thread,
        args=(st.session_state.calib_fq, st.session_state.calib_stop, st.session_state.cs),
        daemon=True,
    )
    _t.start()
    st.session_state.calib_thread = _t

cs = st.session_state.cs
fq = st.session_state.calib_fq
step = cs.get("step", 1)

# ── Layout ────────────────────────────────────────────────────────────────────
col_left, col_right = st.columns([2, 1])

with col_left:
    frame_ph  = st.empty()
    status_ph = st.empty()

# Collect dynamic placeholders in a dict so the while loop can reference them
phs: dict = {}

with col_right:
    _step_labels = {1: "Pinch-Kalibrierung", 2: "Mapping-Bereich",
                    3: "Smooth-Faktor", 4: "Ergebnisse"}
    st.progress(
        min(step, _STEPS) / _STEPS,
        text=f"Schritt {min(step, _STEPS)} von {_STEPS}: {_step_labels.get(step, 'Ergebnisse')}",
    )
    st.divider()

    # ── Step 1 ────────────────────────────────────────────────────────────────
    if step == 1:
        st.subheader("Schritt 1 – Pinch-Kalibrierung")
        st.info(
            "Mach einen Pinch (Daumen + Zeigefinger) **so eng wie möglich** "
            "und halte ihn, dann starte die Messung."
        )
        phs["s1_prog"]   = st.empty()
        phs["s1_result"] = st.empty()

        if not cs["collecting"] and not cs["step1_done"]:
            if st.button("Messung starten", use_container_width=True, key="s1_start"):
                cs["step1_distances"] = []
                cs["collecting"]      = True

        if cs["step1_done"]:
            min_d   = min(cs["step1_distances"])
            new_thr = round(min_d * 0.8, 4)
            phs["s1_result"].success(
                f"Minimale Distanz: **{min_d:.4f}**  \n"
                f"Neuer Pinch Threshold: **{new_thr:.4f}**"
            )
            if st.button("Weiter →", use_container_width=True, key="s1_next"):
                cs["result_threshold"] = new_thr
                cs["step"]            = 2
                cs["step1_done"]      = False
                st.rerun()

    # ── Step 2 ────────────────────────────────────────────────────────────────
    elif step == 2:
        st.subheader("Schritt 2 – Mapping-Bereich")
        st.info(
            "Starte die Aufzeichnung, bewege dann den **Zeigefinger langsam "
            "in alle vier Ecken** und Kanten des Bildschirms. Das grüne Rechteck "
            "zeigt den erfassten Bereich."
        )
        phs["s2_bounds"] = st.empty()

        has_data = cs["x_max"] > cs["x_min"] and cs["y_max"] > cs["y_min"]
        c1, c2   = st.columns(2)

        with c1:
            lbl = "Stopp" if cs["collecting"] else "Start"
            if st.button(lbl, use_container_width=True, key="s2_toggle"):
                if cs["collecting"]:
                    cs["collecting"] = False
                else:
                    cs.update({"x_min": 1.0, "x_max": 0.0, "y_min": 1.0, "y_max": 0.0})
                    cs["collecting"] = True

        with c2:
            if st.button("Weiter →", use_container_width=True, key="s2_next",
                         disabled=not has_data):
                margin = 0.02
                cs["result_map_x"] = (max(0.0, cs["x_min"] - margin),
                                      min(1.0, cs["x_max"] + margin))
                cs["result_map_y"] = (max(0.0, cs["y_min"] - margin),
                                      min(1.0, cs["y_max"] + margin))
                cs["collecting"]   = False
                cs["step"]         = 3
                st.rerun()

    # ── Step 3 ────────────────────────────────────────────────────────────────
    elif step == 3:
        st.subheader("Schritt 3 – Smooth-Faktor")
        st.info(
            "Bewege die Hand. **Blau** = geglätteter Cursor, **Grün** = Rohposition. "
            "Passe den Regler an, bis der Cursor sich natürlich anfühlt."
        )

        smooth = st.slider(
            "Smooth Factor",
            min_value=0.05, max_value=1.0,
            value=float(cs["smooth_factor"]),
            step=0.05, key="s3_smooth",
        )
        cs["smooth_factor"] = smooth

        c1, c2 = st.columns(2)
        c1.caption("← träge / geglättet")
        c2.caption("schnell / zittrig →")

        if st.button("Übernehmen & Weiter →", use_container_width=True, key="s3_next"):
            cs["result_smooth"] = smooth
            cs["step"]          = 4
            st.rerun()

    # ── Step 4: Results ───────────────────────────────────────────────────────
    elif step >= 4:
        st.subheader("Kalibrierung abgeschlossen")

        thr = cs.get("result_threshold") or config.PINCH_THRESHOLD
        mx  = cs.get("result_map_x")     or list(config.MAP_X)
        my  = cs.get("result_map_y")     or list(config.MAP_Y)
        sm  = cs.get("result_smooth")    or cs.get("smooth_factor", config.SMOOTH_FACTOR)

        st.markdown(f"""
| Einstellung     | Wert |
|-----------------|------|
| Pinch Threshold | `{thr:.4f}` |
| MAP_X           | `[{float(mx[0]):.3f}, {float(mx[1]):.3f}]` |
| MAP_Y           | `[{float(my[0]):.3f}, {float(my[1]):.3f}]` |
| Smooth Factor   | `{sm:.2f}` |
""")

        save_name = st.text_input("Als Profil speichern:", value="calibrated", key="s4_name")
        c1, c2 = st.columns(2)

        with c1:
            if st.button("Profil speichern", use_container_width=True, key="s4_save"):
                profile_manager.save_profile(save_name, {
                    "name":                save_name,
                    "smooth_factor":       sm,
                    "pinch_threshold":     thr,
                    "click_cooldown":      config.CLICK_COOLDOWN,
                    "scroll_sensitivity":  config.SCROLL_SENSITIVITY,
                    "drag_threshold":      config.DRAG_THRESHOLD_SEC,
                    "double_click_window": config.DOUBLE_CLICK_WINDOW,
                    "map_x":               [float(mx[0]), float(mx[1])],
                    "map_y":               [float(my[0]), float(my[1])],
                })
                # Apply immediately to this session's config
                config.MAP_X           = tuple(mx)
                config.MAP_Y           = tuple(my)
                config.PINCH_THRESHOLD = thr
                config.SMOOTH_FACTOR   = sm
                st.success(f"Profil **'{save_name}'** gespeichert.")

        with c2:
            if st.button("Neu kalibrieren", use_container_width=True, key="s4_restart"):
                _reset(cs)
                st.rerun()


# ── Streaming loop ────────────────────────────────────────────────────────────
while True:
    try:
        d = fq.get(timeout=0.08)
        frame_ph.image(d["frame"], channels="RGB", use_container_width=True)
        if d["has_hand"]:
            extra = f"  |  Pinch: **{d['pinch_dist']:.3f}**" if d["pinch_dist"] is not None else ""
            status_ph.caption(f"Hand erkannt{extra}")
        else:
            status_ph.warning("Keine Hand im Bild – Kamera und Beleuchtung prüfen.")
    except queue.Empty:
        pass

    cur_step = cs.get("step", 1)

    # Step 1: update progress bar; trigger a rerun when collection finishes
    if cur_step == 1 and "s1_prog" in phs:
        n = len(cs["step1_distances"])
        phs["s1_prog"].progress(min(n / 30, 1.0), text=f"{n} / 30 Frames gesammelt")

        if cs.get("step1_done") and not st.session_state.get("_s1_notified"):
            st.session_state._s1_notified = True
            st.rerun()
        elif not cs.get("step1_done"):
            st.session_state._s1_notified = False

    # Step 2: update bounds display
    elif cur_step == 2 and "s2_bounds" in phs:
        x_min, x_max = cs["x_min"], cs["x_max"]
        y_min, y_max = cs["y_min"], cs["y_max"]
        if x_max > x_min:
            phs["s2_bounds"].caption(
                f"Erfasster Bereich:  "
                f"X [{x_min:.2f} – {x_max:.2f}]  ·  Y [{y_min:.2f} – {y_max:.2f}]"
            )
        else:
            phs["s2_bounds"].caption("Noch kein Bereich erfasst – starte die Aufzeichnung.")

    time.sleep(0.033)
