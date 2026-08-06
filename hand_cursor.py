"""HandCursor — mouse control from webcam hand gestures (OpenCV window).

Run via the launcher (``./start.sh app``) or directly:

    python hand_cursor.py                 # active profile
    python hand_cursor.py --profile gaming
    python hand_cursor.py --camera 1
    python hand_cursor.py --no-control    # detect and draw, don't touch the mouse
    python hand_cursor.py --list-profiles

Heavy imports (cv2, mediapipe, pyautogui) happen inside :func:`main` on
purpose: ``--help`` and ``--list-profiles`` must work on a machine with no
display, where importing pyautogui raises.
"""

import argparse
import sys
import time

import camera
import config
import profile_manager
import runtime
from gestures import GestureDetector
from version import APP_NAME, VERSION

QUIT_KEYS = {ord("q"), 27}  # q or Esc


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hand_cursor.py",
        description=f"{APP_NAME} — Maussteuerung per Handgesten.",
    )
    parser.add_argument("--profile", metavar="NAME",
                        help="Profil, mit dem gestartet wird (Standard: zuletzt aktives)")
    parser.add_argument("--list-profiles", action="store_true",
                        help="Verfügbare Profile auflisten und beenden")
    parser.add_argument("--camera", type=int, metavar="N",
                        help=f"Kamera-Index (Standard: {config.CAM_INDEX})")
    parser.add_argument("--no-control", action="store_true",
                        help="Gesten nur erkennen und anzeigen, Maus nicht steuern")
    parser.add_argument("--no-failsafe", action="store_true",
                        help="PyAutoGUI-Notaus (Maus in eine Bildschirmecke) deaktivieren")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    return parser.parse_args(argv)


def normalize_to_screen(norm_x, norm_y, settings, screen_w, screen_h):
    x_min, x_max = settings["map_x"]
    y_min, y_max = settings["map_y"]
    x = min(max((norm_x - x_min) / (x_max - x_min), 0.0), 1.0)
    y = min(max((norm_y - y_min) / (y_max - y_min), 0.0), 1.0)
    return int(x * screen_w), int(y * screen_h)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.list_profiles:
        names = profile_manager.list_profiles()
        if not names:
            print("Keine Profile gefunden.")
            return 0
        active = profile_manager.get_active_profile_name()
        for name in names:
            print(f"{'*' if name == active else ' '} {name}")
        return 0

    applied = runtime.load_startup_profile(args.profile)
    if args.profile and applied != args.profile:
        print(f"Profil '{args.profile}' nicht gefunden.", file=sys.stderr)
        print(f"Verfügbar: {', '.join(profile_manager.list_profiles()) or '(keine)'}",
              file=sys.stderr)
        return 1
    print(f"{APP_NAME} {VERSION} — Profil: {applied or 'Standardwerte'}")

    cam_index = config.CAM_INDEX if args.camera is None else args.camera

    # Heavy imports deferred: they fail hard on a headless machine.
    try:
        import cv2
        import mediapipe as mp
        import pyautogui
    except Exception as exc:
        print(f"Abhängigkeit konnte nicht geladen werden: {exc}", file=sys.stderr)
        print("Diagnose:  python run.py doctor", file=sys.stderr)
        return 3

    pyautogui.FAILSAFE = not args.no_failsafe
    control = not args.no_control

    try:
        cap = camera.open_capture(cam_index)
    except camera.CameraError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    screen_w, screen_h = pyautogui.size()

    detector = GestureDetector(settings=runtime.snapshot())
    prev_x = prev_y = 0
    last_rc_time = 0.0
    double_click_until = 0.0
    scroll_prev_y: float | None = None

    print("Beenden mit 'q' oder Esc." + ("" if control else "  [Steuerung AUS]"))

    try:
        with mp_hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        ) as hands:
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("Kamera liefert keine Bilder mehr — beende.", file=sys.stderr)
                    break

                frame = cv2.flip(frame, 1)
                result = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                now = time.time()

                settings = runtime.snapshot()
                detector.set_settings(settings)

                landmarks = (result.multi_hand_landmarks[0].landmark
                             if result.multi_hand_landmarks else None)
                detector.update(landmarks)

                # Polled every frame, including when no hand is visible: a
                # queued click must settle on time, not fire minutes later at
                # wherever the cursor happens to be.
                action = detector.get_click_action()

                frame_h, frame_w = frame.shape[:2]

                if landmarks is None:
                    scroll_prev_y = None
                elif detector.is_scroll_mode():
                    if scroll_prev_y is not None:
                        delta = detector.get_scroll_delta(scroll_prev_y)
                        amount = -int(delta * settings["scroll_sensitivity"] * 100)
                        if amount and control:
                            pyautogui.scroll(amount)
                    scroll_prev_y = landmarks[8].y
                    cv2.putText(frame, "SCROLL", (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 80, 0), 2)
                else:
                    scroll_prev_y = None
                    norm_x, norm_y = detector.cursor_position()
                    raw_x, raw_y = normalize_to_screen(
                        norm_x, norm_y, settings, screen_w, screen_h)

                    smooth = settings["smooth_factor"]
                    curr_x = int(prev_x + (raw_x - prev_x) * smooth)
                    curr_y = int(prev_y + (raw_y - prev_y) * smooth)
                    prev_x, prev_y = curr_x, curr_y
                    if control:
                        pyautogui.moveTo(curr_x, curr_y)

                    tip = (int(norm_x * frame_w), int(norm_y * frame_h))
                    if detector.is_dragging():
                        cv2.circle(frame, tip, 16, (0, 0, 255), -1)
                        cv2.putText(frame, "DRAG", (10, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2)
                    else:
                        cv2.circle(frame, tip, 8, (0, 255, 0), -1)

                # ── Dispatch (identical to the Streamlit page) ────────────
                if detector.drag_just_started():
                    if control:
                        pyautogui.mouseDown()
                elif detector.drag_just_ended():
                    if control:
                        pyautogui.mouseUp()

                if action == "click":
                    if control:
                        pyautogui.click()
                elif action == "double_click":
                    if control:
                        pyautogui.doubleClick()
                    double_click_until = now + 0.5

                if (detector.right_click_just_fired()
                        and now - last_rc_time > settings["click_cooldown"]):
                    if control:
                        pyautogui.rightClick()
                    last_rc_time = now

                if result.multi_hand_landmarks:
                    mp_draw.draw_landmarks(frame, result.multi_hand_landmarks[0],
                                           mp_hands.HAND_CONNECTIONS)

                if now < double_click_until:
                    cv2.putText(frame, "DOUBLE CLICK", (10, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 2)
                if not control:
                    cv2.putText(frame, "STEUERUNG AUS", (10, frame_h - 15),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

                cv2.imshow(APP_NAME, frame)
                if (cv2.waitKey(1) & 0xFF) in QUIT_KEYS:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        # Never leave the mouse button stuck down.
        if control and detector.is_dragging():
            try:
                pyautogui.mouseUp()
            except Exception:
                pass
        cap.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
