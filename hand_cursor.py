import time
import cv2
import mediapipe as mp
import pyautogui
import numpy as np

import config
from gestures import GestureDetector

pyautogui.FAILSAFE = False

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

screen_w, screen_h = pyautogui.size()


def normalize_to_screen(norm_x, norm_y):
    x_min, x_max = config.MAP_X
    y_min, y_max = config.MAP_Y
    x = (norm_x - x_min) / (x_max - x_min)
    y = (norm_y - y_min) / (y_max - y_min)
    x = np.clip(x, 0.0, 1.0)
    y = np.clip(y, 0.0, 1.0)
    return int(x * screen_w), int(y * screen_h)


def main():
    prev_x, prev_y = 0, 0
    last_right_click_time = 0
    scroll_prev_y: float | None = None
    gesture = GestureDetector()

    cap = cv2.VideoCapture(config.CAM_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAM_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAM_H)

    with mp_hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.7,
    ) as hands:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = hands.process(rgb)

            if result.multi_hand_landmarks:
                lm = result.multi_hand_landmarks[0].landmark
                gesture.update(lm)

                frame_h, frame_w = frame.shape[:2]

                if gesture.is_scroll_mode():
                    if scroll_prev_y is not None:
                        delta = gesture.get_scroll_delta(scroll_prev_y)
                        scroll_amount = -int(delta * config.SCROLL_SENSITIVITY * 100)
                        if scroll_amount != 0:
                            pyautogui.scroll(scroll_amount)
                    scroll_prev_y = lm[8].y

                    cv2.putText(
                        frame, "SCROLL", (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 80, 0), 2,
                    )
                else:
                    scroll_prev_y = None

                    norm_x, norm_y = gesture.cursor_position()
                    raw_x, raw_y = normalize_to_screen(norm_x, norm_y)

                    curr_x = int(prev_x + (raw_x - prev_x) * config.SMOOTH_FACTOR)
                    curr_y = int(prev_y + (raw_y - prev_y) * config.SMOOTH_FACTOR)
                    prev_x, prev_y = curr_x, curr_y

                    pyautogui.moveTo(curr_x, curr_y)

                    if gesture.drag_just_started():
                        pyautogui.mouseDown()
                    elif gesture.drag_just_ended():
                        pyautogui.mouseUp()
                    elif gesture.click_just_fired():
                        pyautogui.click()

                    now = time.time()
                    if gesture.is_right_click() and (now - last_right_click_time) > config.CLICK_COOLDOWN:
                        pyautogui.rightClick()
                        last_right_click_time = now

                    if gesture.is_dragging():
                        tip_px = (int(norm_x * frame_w), int(norm_y * frame_h))
                        cv2.circle(frame, tip_px, 16, (0, 0, 255), -1)
                        cv2.putText(
                            frame, "DRAG", (10, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 2,
                        )
                    else:
                        tip_px = (int(norm_x * frame_w), int(norm_y * frame_h))
                        cv2.circle(frame, tip_px, 8, (0, 255, 0), -1)

                mp_draw.draw_landmarks(
                    frame,
                    result.multi_hand_landmarks[0],
                    mp_hands.HAND_CONNECTIONS,
                )

            cv2.imshow("HandCursor", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
