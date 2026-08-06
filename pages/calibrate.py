"""Three-step calibration wizard.

Shares the process-wide camera hub with the main page, so opening this page
takes the camera over rather than fighting the main page for it. Results are
written into :mod:`runtime`, which is what the main page reads — so a
calibration takes effect immediately instead of being overwritten.
"""

import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import camera          # noqa: E402
import config          # noqa: E402
import profile_manager  # noqa: E402
import runtime         # noqa: E402

_OWNER = "calibrate"
_STEPS = 3
_PINCH_FRAMES = 30
# Abort the pinch measurement if no hand shows up for this long.
_NO_HAND_TIMEOUT = 15.0


def _fresh() -> dict:
    return {
        "step": 1,
        "collecting": False,
        "distances": [],
        "step1_done": False,
        "started_at": 0.0,
        "last_hand_at": 0.0,
        "x_min": 1.0, "x_max": 0.0,
        "y_min": 1.0, "y_max": 0.0,
        "smooth_factor": runtime.get("smooth_factor"),
        "result_threshold": None,
        "result_map_x": None,
        "result_map_y": None,
        "result_smooth": None,
        "has_hand": False,
        "pinch_dist": None,
    }


# Process-global, same scope as the camera hub that reads it.
_CS: dict = _fresh()


def _reset() -> None:
    """Reset in place. Never cs.clear() — the worker thread reads this dict
    concurrently and would hit a KeyError in the gap before update()."""
    _CS.update(_fresh())


def _smooth_state() -> dict:
    if "_sm" not in _CS:
        _CS["_sm"] = {"x": 0.5, "y": 0.5}
    return _CS["_sm"]


# ── Frame processor (runs on the camera worker thread) ────────────────────

def _process(frame, result) -> dict:
    import cv2
    import mediapipe as mp

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    step = _CS.get("step", 1)
    collecting = _CS.get("collecting", False)
    landmarks = (result.multi_hand_landmarks[0].landmark
                 if result.multi_hand_landmarks else None)
    frame_h, frame_w = frame.shape[:2]
    now = time.time()

    _CS["has_hand"] = landmarks is not None
    pinch_dist = None

    if landmarks is not None:
        _CS["last_hand_at"] = now
        thumb, index = landmarks[4], landmarks[8]
        pinch_dist = float(((thumb.x - index.x) ** 2 + (thumb.y - index.y) ** 2) ** 0.5)
        _CS["pinch_dist"] = pinch_dist

        if step == 1 and collecting:
            _CS["distances"].append(pinch_dist)
            if len(_CS["distances"]) >= _PINCH_FRAMES:
                _CS["collecting"] = False
                _CS["step1_done"] = True

        elif step == 2 and collecting:
            _CS["x_min"] = min(_CS["x_min"], index.x)
            _CS["x_max"] = max(_CS["x_max"], index.x)
            _CS["y_min"] = min(_CS["y_min"], index.y)
            _CS["y_max"] = max(_CS["y_max"], index.y)

        elif step == 3:
            sm = _smooth_state()
            factor = _CS.get("smooth_factor", 0.3)
            sm["x"] += (index.x - sm["x"]) * factor
            sm["y"] += (index.y - sm["y"]) * factor
            cv2.circle(frame, (int(sm["x"] * frame_w), int(sm["y"] * frame_h)),
                       22, (255, 100, 0), -1)
            cv2.circle(frame, (int(index.x * frame_w), int(index.y * frame_h)),
                       7, (0, 255, 0), -1)

        if step in (1, 2):
            cv2.circle(frame, (int(index.x * frame_w), int(index.y * frame_h)),
                       9, (0, 255, 0), -1)

        if step == 1:
            cv2.putText(frame, f"Pinch: {pinch_dist:.3f}", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 255), 2)
            if collecting:
                cv2.putText(frame, f"Frame {len(_CS['distances'])}/{_PINCH_FRAMES}",
                            (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        mp_draw.draw_landmarks(frame, result.multi_hand_landmarks[0],
                               mp_hands.HAND_CONNECTIONS)

    # Time out a measurement that will never finish (no hand in frame).
    if (step == 1 and collecting and _CS["started_at"]
            and now - _CS["last_hand_at"] > _NO_HAND_TIMEOUT):
        _CS["collecting"] = False
        _CS["timed_out"] = True

    if step == 2 and _CS["x_max"] > _CS["x_min"]:
        pt1 = (int(_CS["x_min"] * frame_w), int(_CS["y_min"] * frame_h))
        pt2 = (int(_CS["x_max"] * frame_w), int(_CS["y_max"] * frame_h))
        cv2.rectangle(frame, pt1, pt2, (0, 255, 100), 2)
        cv2.putText(frame, "Erfasster Bereich", (pt1[0], max(pt1[1] - 8, 12)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 100), 1)

    return {
        "frame": cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
        "has_hand": landmarks is not None,
        "pinch_dist": pinch_dist,
    }


# ── Page ──────────────────────────────────────────────────────────────────

st.set_page_config(layout="wide", page_title="HandCursor – Kalibrierung")
st.title("Kalibrierungs-Wizard")

camera.acquire(_OWNER, _process)

step = _CS.get("step", 1)
col_left, col_right = st.columns([2, 1])

with col_left:
    frame_ph = st.empty()
    status_ph = st.empty()
    error_ph = st.empty()

phs: dict = {}

with col_right:
    labels = {1: "Pinch-Kalibrierung", 2: "Mapping-Bereich",
              3: "Smooth-Faktor", 4: "Ergebnisse"}
    st.progress(min(step, _STEPS) / _STEPS,
                text=f"Schritt {min(step, _STEPS)} von {_STEPS}: {labels.get(step, 'Ergebnisse')}")
    st.divider()

    # ── Step 1 ────────────────────────────────────────────────────────────
    if step == 1:
        st.subheader("Schritt 1 – Pinch-Kalibrierung")
        st.info("Mach einen Pinch (Daumen + Zeigefinger) **so eng wie möglich** "
                "und halte ihn, dann starte die Messung.")
        phs["prog"] = st.empty()

        if _CS.pop("timed_out", False):
            st.warning(f"Abgebrochen – {int(_NO_HAND_TIMEOUT)} s keine Hand erkannt. "
                       "Beleuchtung und Kameraabstand prüfen (40–70 cm).")

        if _CS["collecting"]:
            # Always reachable: without this the wizard is a dead end whenever
            # the hand is not detected.
            if st.button("Abbrechen", use_container_width=True, key="s1_cancel"):
                _CS["collecting"] = False
                _CS["distances"] = []
                st.rerun()
        elif not _CS["step1_done"]:
            if st.button("Messung starten", use_container_width=True, key="s1_start"):
                _CS["distances"] = []
                _CS["collecting"] = True
                _CS["started_at"] = time.time()
                _CS["last_hand_at"] = time.time()
                st.rerun()

        if _CS["step1_done"] and _CS["distances"]:
            min_d = min(_CS["distances"])
            new_thr = round(min_d * 0.8, 4)
            st.success(f"Minimale Distanz: **{min_d:.4f}**  \n"
                       f"Neuer Pinch Threshold: **{new_thr:.4f}**")
            c1, c2 = st.columns(2)
            if c1.button("Weiter →", use_container_width=True, key="s1_next"):
                _CS["result_threshold"] = new_thr
                _CS["step"] = 2
                _CS["step1_done"] = False
                st.rerun()
            if c2.button("Nochmal", use_container_width=True, key="s1_again"):
                _CS["step1_done"] = False
                _CS["distances"] = []
                st.rerun()

    # ── Step 2 ────────────────────────────────────────────────────────────
    elif step == 2:
        st.subheader("Schritt 2 – Mapping-Bereich")
        st.info("Starte die Aufzeichnung, bewege dann den **Zeigefinger langsam "
                "in alle vier Ecken** und Kanten. Das grüne Rechteck zeigt den "
                "erfassten Bereich.")
        phs["bounds"] = st.empty()

        c1, c2 = st.columns(2)
        with c1:
            label = "Stopp" if _CS["collecting"] else "Start"
            if st.button(label, use_container_width=True, key="s2_toggle"):
                if _CS["collecting"]:
                    _CS["collecting"] = False
                else:
                    _CS.update({"x_min": 1.0, "x_max": 0.0,
                                "y_min": 1.0, "y_max": 0.0, "collecting": True})
                st.rerun()
        with c2:
            # Deliberately not disabled= : that value is computed once at render
            # time and would stay stale while the user records. Validate instead.
            if st.button("Weiter →", use_container_width=True, key="s2_next"):
                if _CS["x_max"] > _CS["x_min"] and _CS["y_max"] > _CS["y_min"]:
                    margin = 0.02
                    _CS["result_map_x"] = (max(0.0, _CS["x_min"] - margin),
                                           min(1.0, _CS["x_max"] + margin))
                    _CS["result_map_y"] = (max(0.0, _CS["y_min"] - margin),
                                           min(1.0, _CS["y_max"] + margin))
                    _CS["collecting"] = False
                    _CS["step"] = 3
                    st.rerun()
                else:
                    st.warning("Noch kein Bereich erfasst – erst „Start“ drücken "
                               "und den Zeigefinger bewegen.")

    # ── Step 3 ────────────────────────────────────────────────────────────
    elif step == 3:
        st.subheader("Schritt 3 – Smooth-Faktor")
        st.info("Bewege die Hand. **Blau** = geglätteter Cursor, **Grün** = "
                "Rohposition. Passe den Regler an, bis es sich natürlich anfühlt.")
        _CS["smooth_factor"] = st.slider(
            "Smooth Factor", 0.05, 1.0, float(_CS["smooth_factor"]), 0.05,
            key="s3_smooth")
        c1, c2 = st.columns(2)
        c1.caption("← träge / geglättet")
        c2.caption("schnell / zittrig →")
        if st.button("Übernehmen & Weiter →", use_container_width=True, key="s3_next"):
            _CS["result_smooth"] = _CS["smooth_factor"]
            _CS["step"] = 4
            st.rerun()

    # ── Step 4 ────────────────────────────────────────────────────────────
    else:
        st.subheader("Kalibrierung abgeschlossen")
        thr = _CS["result_threshold"]
        thr = runtime.get("pinch_threshold") if thr is None else thr
        mx = _CS["result_map_x"] or runtime.get("map_x")
        my = _CS["result_map_y"] or runtime.get("map_y")
        sm = _CS["result_smooth"]
        sm = runtime.get("smooth_factor") if sm is None else sm

        st.markdown(f"""
| Einstellung     | Wert |
|-----------------|------|
| Pinch Threshold | `{thr:.4f}` |
| MAP_X           | `[{float(mx[0]):.3f}, {float(mx[1]):.3f}]` |
| MAP_Y           | `[{float(my[0]):.3f}, {float(my[1]):.3f}]` |
| Smooth Factor   | `{sm:.2f}` |
""")

        save_name = st.text_input("Als Profil speichern:", value="calibrated",
                                  key="s4_name")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Profil speichern", use_container_width=True, key="s4_save"):
                try:
                    # Write into the shared runtime first, so the main page
                    # picks the values up instead of overwriting them.
                    runtime.update(pinch_threshold=thr, smooth_factor=sm,
                                   map_x=tuple(mx), map_y=tuple(my))
                    profile_manager.save_profile(save_name,
                                                 runtime.as_profile(save_name))
                    runtime.apply_profile(save_name)
                    st.success(f"Profil **'{save_name}'** gespeichert und aktiviert.")
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
        with c2:
            if st.button("Neu kalibrieren", use_container_width=True, key="s4_restart"):
                _reset()
                st.rerun()

# ── Streaming loop ────────────────────────────────────────────────────────
while True:
    payload = camera.latest(_OWNER)
    state = camera.status()

    if state.error:
        error_ph.error(state.error)
    elif not state.running:
        error_ph.info("Kamera gestoppt. Seite neu laden, um sie erneut zu starten.")
    else:
        error_ph.empty()

    if payload is not None:
        frame_ph.image(payload["frame"], channels="RGB", use_container_width=True)
        if payload["has_hand"]:
            dist = payload["pinch_dist"]
            status_ph.caption(
                f"Hand erkannt  |  Pinch: **{dist:.3f}**" if dist is not None
                else "Hand erkannt")
        else:
            status_ph.warning("Keine Hand im Bild – Kamera und Beleuchtung prüfen.")

    cur = _CS.get("step", 1)
    if cur == 1 and "prog" in phs:
        n = len(_CS["distances"])
        phs["prog"].progress(min(n / _PINCH_FRAMES, 1.0),
                             text=f"{n} / {_PINCH_FRAMES} Frames gesammelt")
    elif cur == 2 and "bounds" in phs:
        if _CS["x_max"] > _CS["x_min"]:
            phs["bounds"].caption(
                f"Erfasster Bereich:  X [{_CS['x_min']:.2f} – {_CS['x_max']:.2f}]"
                f"  ·  Y [{_CS['y_min']:.2f} – {_CS['y_max']:.2f}]")
        else:
            phs["bounds"].caption("Noch kein Bereich erfasst – „Start“ drücken.")

    # Rerun whenever anything the widgets depend on changed. This replaces the
    # old one-shot _s1_notified flag and is what makes step 2's button react.
    sig = (_CS["step"], _CS["collecting"], _CS["step1_done"],
           _CS["x_max"] > _CS["x_min"], _CS.get("timed_out", False))
    if sig != st.session_state.get("_calib_sig"):
        st.session_state._calib_sig = sig
        st.rerun()

    time.sleep(0.033)
