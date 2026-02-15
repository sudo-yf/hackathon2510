import base64
import logging
import threading
import time
from typing import Any, Dict, Optional

import cv2
import mediapipe as mp
import numpy as np

from .config import AppConfig

logger = logging.getLogger(__name__)


class _NoopMouseBackend:
    def size(self):
        return (1920, 1080)

    def move_to(self, x: int, y: int):
        return None

    def click(self):
        return None

    def right_click(self):
        return None


class _PyAutoGuiBackend:
    def __init__(self):
        import pyautogui

        pyautogui.FAILSAFE = False
        self._pyautogui = pyautogui

    def size(self):
        return self._pyautogui.size()

    def move_to(self, x: int, y: int):
        self._pyautogui.moveTo(x, y, duration=0)

    def click(self):
        self._pyautogui.click()

    def right_click(self):
        self._pyautogui.rightClick()


class GestureControlService:
    """Core stateful service for camera processing and gesture-to-mouse control."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.hands = mp.solutions.hands.Hands(
            model_complexity=1,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.cap = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.state_lock = threading.Lock()

        self.mouse = self._build_mouse_backend()
        self.screen_w, self.screen_h = self.mouse.size()

        self.mouse_enabled = False
        self.flip_horizontal = True

        self.power_factor = 2.0
        self.edge_boost = 1.5
        self.dead_zone = 0.05

        self.cursor_x = None
        self.cursor_y = None
        self.smoothing_alpha = 0.3

        self.last_gesture = None
        self.gesture_cooldown = 0.3
        self.last_gesture_time = 0

        self.calibration_data = {
            "left_threshold": 0.05,
            "right_threshold": 0.05,
        }

        self.fps = 0
        self.frame_count = 0
        self.last_fps_time = time.time()

    def get_runtime_settings(self) -> Dict[str, float]:
        return {
            "smoothing": self.smoothing_alpha,
            "power_factor": self.power_factor,
            "edge_boost": self.edge_boost,
        }

    def apply_settings(self, smoothing: float | None = None, power_factor: float | None = None, edge_boost: float | None = None):
        with self.state_lock:
            if smoothing is not None:
                self.smoothing_alpha = max(0.1, min(0.9, float(smoothing)))
            if power_factor is not None:
                self.power_factor = max(1.0, min(3.0, float(power_factor)))
            if edge_boost is not None:
                self.edge_boost = max(1.0, min(3.0, float(edge_boost)))

    def _build_mouse_backend(self):
        if self.config.disable_mouse:
            logger.info("Mouse backend disabled by DISABLE_MOUSE")
            return _NoopMouseBackend()
        try:
            return _PyAutoGuiBackend()
        except Exception as exc:
            logger.warning("Failed to initialize pyautogui backend, fallback to noop: %s", exc)
            return _NoopMouseBackend()

    def start(self) -> Dict[str, Any]:
        with self.state_lock:
            if self.running:
                return {"success": False, "message": "已在运行中"}

        try:
            self.cap = cv2.VideoCapture(self.config.camera_index)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.frame_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.config.frame_fps)

            if not self.cap.isOpened():
                self.cap.release()
                self.cap = None
                return {"success": False, "message": "无法打开摄像头"}

            with self.state_lock:
                self.running = True
            self.thread = threading.Thread(target=self.process_loop, daemon=True, name="gesture-camera-loop")
            self.thread.start()
            return {"success": True, "message": "摄像头已启动"}
        except Exception as exc:
            logger.exception("启动摄像头失败")
            return {"success": False, "message": f"启动失败: {exc}"}

    def stop(self) -> Dict[str, Any]:
        with self.state_lock:
            self.running = False
            self.mouse_enabled = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        if self.cap:
            self.cap.release()
            self.cap = None

        self.cursor_x = None
        self.cursor_y = None
        return {"success": True, "message": "摄像头已停止"}

    def process_loop(self):
        while True:
            with self.state_lock:
                if not self.running:
                    break

            if not self.cap:
                time.sleep(0.05)
                continue

            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.05)
                continue

            if self.flip_horizontal:
                frame = cv2.flip(frame, 1)

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)

            annotated_frame = frame.copy()
            gesture_info = None

            if results.multi_hand_landmarks:
                for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    self.draw_hand_skeleton(annotated_frame, hand_landmarks)
                    if idx == 0:
                        gesture_info = self.process_hand_gesture(hand_landmarks)

            self.draw_overlay_info(annotated_frame, gesture_info)

            encoded, buffer = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not encoded:
                continue

            frame_base64 = base64.b64encode(buffer).decode("utf-8")
            self.on_frame(
                {
                    "image": frame_base64,
                    "gesture": gesture_info,
                    "fps": self.fps,
                }
            )

            self.frame_count += 1
            now = time.time()
            if now - self.last_fps_time >= 1.0:
                self.fps = self.frame_count
                self.frame_count = 0
                self.last_fps_time = now

            time.sleep(0.01)

    def on_frame(self, payload: Dict[str, Any]):
        """Override in web layer."""

    def process_hand_gesture(self, landmarks) -> Dict[str, Any]:
        thumb_tip = landmarks.landmark[4]
        index_tip = landmarks.landmark[8]
        middle_tip = landmarks.landmark[12]
        middle_mid = landmarks.landmark[10]

        gesture_info = {"type": None, "mouse_pos": None, "click": None}

        if self.mouse_enabled:
            self.update_mouse_position_advanced(index_tip)
            gesture_info["mouse_pos"] = (self.cursor_x, self.cursor_y)

        current_time = time.time()
        dist_to_tip = self.calculate_distance(thumb_tip, middle_tip)
        dist_to_mid = self.calculate_distance(thumb_tip, middle_mid)

        if dist_to_tip < self.calibration_data["left_threshold"]:
            if current_time - self.last_gesture_time > self.gesture_cooldown and self.last_gesture != "left_click":
                gesture_info["type"] = "left_click"
                gesture_info["click"] = "left"
                if self.mouse_enabled:
                    self.mouse.click()
                self.last_gesture = "left_click"
                self.last_gesture_time = current_time
        elif dist_to_mid < self.calibration_data["right_threshold"]:
            if current_time - self.last_gesture_time > self.gesture_cooldown and self.last_gesture != "right_click":
                gesture_info["type"] = "right_click"
                gesture_info["click"] = "right"
                if self.mouse_enabled:
                    self.mouse.right_click()
                self.last_gesture = "right_click"
                self.last_gesture_time = current_time
        else:
            self.last_gesture = None

        return gesture_info

    @staticmethod
    def calculate_distance(point1, point2):
        return np.sqrt((point1.x - point2.x) ** 2 + (point1.y - point2.y) ** 2)

    def update_mouse_position_advanced(self, finger_tip):
        centered_x = finger_tip.x - 0.5
        centered_y = finger_tip.y - 0.5
        distance = np.sqrt(centered_x ** 2 + centered_y ** 2)

        if distance < self.dead_zone:
            return

        if distance < 0.3:
            factor = np.power(distance / 0.3, self.power_factor)
        else:
            factor = 1.0 + (distance - 0.3) * self.edge_boost

        mapped_x = max(0, min(1, 0.5 + centered_x * factor))
        mapped_y = max(0, min(1, 0.5 + centered_y * factor))

        target_x = int(mapped_x * self.screen_w)
        target_y = int(mapped_y * self.screen_h)

        if self.cursor_x is None:
            self.cursor_x, self.cursor_y = target_x, target_y
        else:
            self.cursor_x = int(self.cursor_x + self.smoothing_alpha * (target_x - self.cursor_x))
            self.cursor_y = int(self.cursor_y + self.smoothing_alpha * (target_y - self.cursor_y))

        try:
            self.mouse.move_to(self.cursor_x, self.cursor_y)
        except Exception as exc:
            logger.warning("鼠标移动失败: %s", exc)

    @staticmethod
    def draw_hand_skeleton(frame, landmarks):
        h, w, _ = frame.shape
        connections = [
            [0, 1], [1, 2], [2, 3], [3, 4],
            [0, 5], [5, 6], [6, 7], [7, 8],
            [0, 9], [9, 10], [10, 11], [11, 12],
            [0, 13], [13, 14], [14, 15], [15, 16],
            [0, 17], [17, 18], [18, 19], [19, 20],
            [5, 9], [9, 13], [13, 17],
        ]

        for start_idx, end_idx in connections:
            start = landmarks.landmark[start_idx]
            end = landmarks.landmark[end_idx]
            start_point = (int(start.x * w), int(start.y * h))
            end_point = (int(end.x * w), int(end.y * h))
            cv2.line(frame, start_point, end_point, (220, 100, 50), 3, cv2.LINE_AA)

        for idx, landmark in enumerate(landmarks.landmark):
            x, y = int(landmark.x * w), int(landmark.y * h)
            if idx == 0:
                cv2.circle(frame, (x, y), 8, (50, 50, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, (x, y), 8, (220, 100, 50), 2, cv2.LINE_AA)
            else:
                cv2.circle(frame, (x, y), 5, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(frame, (x, y), 5, (220, 100, 50), 2, cv2.LINE_AA)

    def draw_overlay_info(self, frame, gesture_info: Optional[Dict[str, Any]]):
        cv2.putText(frame, f"FPS: {self.fps}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        mouse_status = "ON" if self.mouse_enabled else "OFF"
        color = (0, 255, 0) if self.mouse_enabled else (128, 128, 128)
        cv2.putText(frame, f"Mouse: {mouse_status}", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

        if gesture_info and gesture_info["type"]:
            self.draw_glass_card(frame, gesture_info)

    @staticmethod
    def draw_glass_card(frame, gesture_info):
        h, w, _ = frame.shape
        card_w, card_h = 200, 80
        card_x = w - card_w - 20
        card_y = 100

        overlay = frame.copy()
        cv2.rectangle(overlay, (card_x, card_y), (card_x + card_w, card_y + card_h), (255, 255, 255), -1)
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
        cv2.rectangle(frame, (card_x, card_y), (card_x + card_w, card_y + card_h), (200, 200, 200), 2, cv2.LINE_AA)

        gesture_text = "左键" if gesture_info["click"] == "left" else "右键"
        text_color = (255, 100, 50) if gesture_info["click"] == "left" else (220, 100, 220)
        cv2.putText(frame, gesture_text, (card_x + 60, card_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, text_color, 3, cv2.LINE_AA)
