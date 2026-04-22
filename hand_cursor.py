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

prev_x, prev_y = 0, 0
last_click_time = 0


def normalize_to_screen(norm_x, norm_y):
    x_min, x_max = config.MAP_X
    y_min, y_max = config.MAP_Y
    x = (norm_x - x_min) / (x_max - x_min)
    y = (norm_y - y_min) / (y_max - y_min)
    x = np.clip(x, 0.0, 1.0)
    y = np.clip(y, 0.0, 1.0)
    return int(x * screen_w), int(y * screen_h)


def main():
    global prev_x, prev_y, last_click_time

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
                gesture = GestureDetector(lm)

                norm_x, norm_y = gesture.cursor_position()
                raw_x, raw_y = normalize_to_screen(norm_x, norm_y)

                curr_x = int(prev_x + (raw_x - prev_x) * config.SMOOTH_FACTOR)
                curr_y = int(prev_y + (raw_y - prev_y) * config.SMOOTH_FACTOR)
                prev_x, prev_y = curr_x, curr_y

                pyautogui.moveTo(curr_x, curr_y)

                now = time.time()
                if gesture.is_left_click() and (now - last_click_time) > config.CLICK_COOLDOWN:
                    pyautogui.click()
                    last_click_time = now
                elif gesture.is_right_click() and (now - last_click_time) > config.CLICK_COOLDOWN:
                    pyautogui.rightClick()
                    last_click_time = now

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
