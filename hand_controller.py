"""
hand_controller.py – Pygame 연동용 백그라운드 손 동작 인식 모듈
MediaPipe 1.0 (Tasks API) + OpenCV + Pygame 스레드 처리 (제스처 인식률 개선 버전)
"""

import cv2
import mediapipe as mp
import numpy as np
import os
import json
import time
import math
import threading
import pygame

# ══════════════════════════════════════════════════════════
#  경로 및 기본 설정
# ══════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CUSTOM_GESTURES_FILE = os.path.join(BASE_DIR, "custom_gestures.json")
MODEL_PATH = os.path.join(BASE_DIR, "hand_landmarker.task")

# MediaPipe 1.0 Tasks API
BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode
HandConnections = mp.tasks.vision.HandLandmarksConnections

HAND_CONNECTIONS_SET = frozenset(
    (c.start, c.end) for c in HandConnections.HAND_CONNECTIONS
)

# ══════════════════════════════════════════════════════════
#  동작 인식 함수 정의 (개선된 관절 높이 비교 방식)
# ══════════════════════════════════════════════════════════
def _dy(a, b):
    return abs(a.y - b.y)

def _dx(a, b):
    return abs(a.x - b.x)

def detect_point(lm):
    """가리키기 (Point): 검지만 펴지고 나머지 손가락은 접힘"""
    wrist = lm[0]
    # 검지 끝(8)이 PIP(6)보다 위(y가 작음)에 있고, 나머지(중지, 약지, 새끼)는 접혀 있음
    index_extended = lm[8].y < lm[6].y and _dy(lm[8], wrist) > 0.12
    others_curled = all(lm[tip].y > lm[pip].y for tip, pip in [(12, 10), (16, 14), (20, 18)])
    return index_extended and others_curled

def detect_victory(lm):
    """승리 V (Victory): 검지와 중지만 펴지고 나머지 손가락은 접힘"""
    index_mid_extended = lm[8].y < lm[6].y and lm[12].y < lm[10].y
    ring_pinky_curled = all(lm[tip].y > lm[pip].y for tip, pip in [(16, 14), (20, 18)])
    return index_mid_extended and ring_pinky_curled

def detect_fist(lm):
    """주먹 (Fist): 네 손가락 모두 접혀 있음"""
    wrist = lm[0]
    return all(lm[tip].y > lm[pip].y or _dy(lm[tip], wrist) < 0.13
               for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)])

def detect_open_palm(lm):
    """펴진 손 (Open Palm): 네 손가락 모두 확실히 펴져 있음"""
    wrist = lm[0]
    return all(lm[tip].y < lm[pip].y and _dy(lm[tip], wrist) > 0.12
               for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)])

# 구별이 명확한 제스처를 먼저 검사하도록 순서 배치
GESTURE_DEFINITIONS = [
    ("Point", detect_point),
    ("Victory", detect_victory),
    ("Fist", detect_fist),
    ("Open Palm", detect_open_palm),
]

def load_custom_gestures():
    if os.path.exists(CUSTOM_GESTURES_FILE):
        try:
            with open(CUSTOM_GESTURES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def landmark_distance(lm_a, lm_b):
    if not lm_a or not lm_b or len(lm_a) != len(lm_b):
        return float("inf")
    total = 0.0
    for a, b in zip(lm_a, lm_b):
        dx = a.get("x", 0) - b.get("x", 0)
        dy = a.get("y", 0) - b.get("y", 0)
        dz = a.get("z", 0) - b.get("z", 0)
        total += dx * dx + dy * dy + dz * dz
    return math.sqrt(total / len(lm_a))

def landmarks_to_dicts(lm_list):
    return [{"x": l.x, "y": l.y, "z": l.z} for l in lm_list]

def recognize_gesture(lm_list, custom_gestures):
    for name, detect_fn in GESTURE_DEFINITIONS:
        if detect_fn(lm_list):
            return name

    lm_dicts = landmarks_to_dicts(lm_list)
    best_name = None
    best_dist = float("inf")
    for cg in custom_gestures:
        stored = cg.get("landmarks", [])
        if not stored:
            continue
        dist = landmark_distance(lm_dicts, stored)
        if dist < best_dist:
            best_dist = dist
            best_name = cg["name"]

    if best_name and best_dist < 0.35:
        return best_name

    return "Unknown"

def draw_hand_landmarks(image, lm_list, connections=HAND_CONNECTIONS_SET,
                        landmark_color=(0, 0, 255), connection_color=(0, 255, 0),
                        thickness=2, circle_radius=3):
    h, w, _ = image.shape
    px = [(int(l.x * w), int(l.y * h)) for l in lm_list]

    for start, end in connections:
        if start < len(px) and end < len(px):
            cv2.line(image, px[start], px[end], connection_color, thickness, cv2.LINE_AA)

    for pt in px:
        cv2.circle(image, pt, circle_radius, landmark_color, -1, cv2.LINE_AA)

# ══════════════════════════════════════════════════════════
#  HandController 클래스 (스레드 기반)
# ══════════════════════════════════════════════════════════
class HandController:
    def __init__(self, cam_index=0):
        self.cam_index = cam_index
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        self.is_detected = False
        self.hand_x = 0.5
        self.hand_y = 0.5
        self.gesture = "None"
        self.frame_rgb = None
        self.preview_surface = None

        self.custom_gestures = load_custom_gestures()

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._camera_loop, daemon=True)
        self.thread.start()
        print("[HandController] 백그라운드 손 동작 인식 스레드 시작됨")

    def _camera_loop(self):
        if not os.path.exists(MODEL_PATH):
            print(f"[HandController 에러] 모델 파일을 찾을 수 없습니다: {MODEL_PATH}")
            self.running = False
            return

        import shutil
        import tempfile
        try:
            model_path_to_use = MODEL_PATH
            if not MODEL_PATH.isascii():
                temp_dir = os.path.join(tempfile.gettempdir(), "everyone_mp")
                os.makedirs(temp_dir, exist_ok=True)
                temp_model = os.path.join(temp_dir, "hand_landmarker.task")
                if not os.path.exists(temp_model):
                    shutil.copy2(MODEL_PATH, temp_model)
                model_path_to_use = temp_model
        except Exception as e:
            model_path_to_use = MODEL_PATH

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path_to_use),
            running_mode=RunningMode.IMAGE,
            num_hands=1
        )

        try:
            landmarker = HandLandmarker.create_from_options(options)
        except Exception as e:
            print(f"[HandController 에러] MediaPipe 초기화 실패: {e}")
            self.running = False
            return

        cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.cam_index, cv2.CAP_MSMF)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.cam_index)

        if not cap.isOpened():
            print(f"[HandController 에러] 카메라를 열 수 없습니다 (index={self.cam_index})")
            landmarker.close()
            self.running = False
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self.running:
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            try:
                result = landmarker.detect(mp_image)
            except Exception:
                result = None

            detected = False
            hand_x_val = 0.5
            hand_y_val = 0.5
            gesture_val = "None"

            if result and result.hand_landmarks:
                lm_list = result.hand_landmarks[0]
                detected = True
                hand_x_val = max(0.0, min(1.0, lm_list[9].x))
                hand_y_val = max(0.0, min(1.0, lm_list[9].y))

                gesture_val = recognize_gesture(lm_list, self.custom_gestures)
                draw_hand_landmarks(frame, lm_list)

            cv2.putText(frame, f"Gesture: {gesture_val}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            small_frame = cv2.resize(frame_rgb, (160, 120))

            with self.lock:
                self.is_detected = detected
                self.hand_x = hand_x_val
                self.hand_y = hand_y_val
                self.gesture = gesture_val
                self.frame_rgb = small_frame

            time.sleep(0.01)

        cap.release()
        landmarker.close()
        print("[HandController] 스레드 정상 종료됨")

    def get_state(self):
        with self.lock:
            return self.is_detected, self.hand_x, self.hand_y, self.gesture

    def get_preview_surface(self):
        with self.lock:
            if self.frame_rgb is None:
                return None
            h, w, _ = self.frame_rgb.shape
            return pygame.image.frombuffer(self.frame_rgb.tobytes(), (w, h), "RGB")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
