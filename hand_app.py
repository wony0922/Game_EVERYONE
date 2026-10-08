"""
hand_app.py – 오프라인 손 동작 인식 + 학습 모드
MediaPipe 1.0 (Tasks API) + OpenCV + Tkinter (WiFi 불필요)

사용법:
  python hand_app.py

조작:
  - 'L' 키: 학습 모드 (5초 카운트다운 → 캡처 → 동작 확인 모달)
  - 'C' 키: 카메라 전환
  - 'Q' 키: 종료
"""

import cv2
import mediapipe as mp
import numpy as np
import os
import json
import time
import math
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from datetime import datetime

# ══════════════════════════════════════════════════════════
#  경로 설정
# ══════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(BASE_DIR, "Photo_Learning")
CUSTOM_GESTURES_FILE = os.path.join(BASE_DIR, "custom_gestures.json")
ACCURACY_FILE = os.path.join(BASE_DIR, "accuracy_score.json")
MODEL_PATH = os.path.join(BASE_DIR, "hand_landmarker.task")
os.makedirs(PHOTO_DIR, exist_ok=True)

def load_accuracy():
    if os.path.exists(ACCURACY_FILE):
        try:
            with open(ACCURACY_FILE, "r", encoding="utf-8") as f:
                return float(json.load(f).get("accuracy", 0.800))
        except Exception:
            return 0.800
    return 0.800

# ══════════════════════════════════════════════════════════
#  MediaPipe 1.0 Tasks API
# ══════════════════════════════════════════════════════════
BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode
HandConnections = mp.tasks.vision.HandLandmarksConnections
draw_landmarks = mp.tasks.vision.drawing_utils.draw_landmarks
DrawingSpec = mp.tasks.vision.drawing_utils.DrawingSpec

# 연결선 리스트 → frozenset 변환 (draw_landmarks용)
HAND_CONNECTIONS_SET = frozenset(
    (c.start, c.end) for c in HandConnections.HAND_CONNECTIONS
)

# ══════════════════════════════════════════════════════════
#  기본 동작 정의 (5종)
# ══════════════════════════════════════════════════════════

def _dy(a, b):
    return abs(a.y - b.y)

def _dx(a, b):
    return abs(a.x - b.x)


def detect_open_palm(lm):
    """펴진 손 (Open Palm)"""
    index, middle, ring, pinky, wrist = lm[8], lm[12], lm[16], lm[20], lm[0]
    return all(_dy(p, wrist) > 0.04 and _dx(p, wrist) > 0.015
               for p in [index, middle, ring, pinky])


def detect_fist(lm):
    """주먹 (Fist)"""
    index, middle, ring, pinky, wrist = lm[8], lm[12], lm[16], lm[20], lm[0]
    return all(_dy(p, wrist) < 0.18 and _dx(p, wrist) < 0.12
               for p in [index, middle, ring, pinky])


def detect_point(lm):
    """가리키기 (Point)"""
    index, middle, ring, pinky, wrist = lm[8], lm[12], lm[16], lm[20], lm[0]
    return (_dy(index, wrist) > 0.04 and
            all(_dy(p, wrist) < 0.18 and _dx(p, wrist) < 0.15
                for p in [middle, ring, pinky]))


def detect_victory(lm):
    """승리 V (Victory)"""
    index, middle, ring, pinky, wrist = lm[8], lm[12], lm[16], lm[20], lm[0]
    return (_dy(index, wrist) > 0.1 and _dy(middle, wrist) > 0.1 and
            all(_dy(p, wrist) < 0.09 and _dx(p, wrist) < 0.06
                for p in [ring, pinky]))

GESTURE_DEFINITIONS = [
    ("펴진 손 (Open Palm)", detect_open_palm),
    ("주먹 (Fist)", detect_fist),
    ("가리키기 (Point)", detect_point),
    ("승리 V (Victory)", detect_victory),
]

# ══════════════════════════════════════════════════════════
#  커스텀 동작 관리
# ══════════════════════════════════════════════════════════

def load_custom_gestures():
    """custom_gestures.json에서 사용자 추가 동작을 불러옴."""
    if os.path.exists(CUSTOM_GESTURES_FILE):
        try:
            with open(CUSTOM_GESTURES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_custom_gestures(gestures):
    """custom_gestures.json에 사용자 추가 동작을 저장."""
    with open(CUSTOM_GESTURES_FILE, "w", encoding="utf-8") as f:
        json.dump(gestures, f, ensure_ascii=False, indent=2)


custom_gestures = load_custom_gestures()


def landmark_distance(lm_a, lm_b):
    """두 랜드마크 dict 리스트 사이의 정규화된 유클리드 거리."""
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
    """MediaPipe NormalizedLandmark 리스트 → dict 리스트."""
    return [{"x": l.x, "y": l.y, "z": l.z} for l in lm_list]


# ══════════════════════════════════════════════════════════
#  동작 인식
# ══════════════════════════════════════════════════════════

def recognize_gesture(lm_list):
    """NormalizedLandmark 리스트로부터 동작을 인식하여 이름 문자열 반환."""
    # 1) 기본 동작
    for name, detect_fn in GESTURE_DEFINITIONS:
        if detect_fn(lm_list):
            return name

    # 2) 커스텀 동작 (랜드마크 패턴 매칭)
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

    return "알 수 없음"


# ══════════════════════════════════════════════════════════
#  카메라 열거 및 백엔드 오픈 (USB 카메라 지원 개선)
# ══════════════════════════════════════════════════════════

def open_camera(index=0):
    """사용 가능한 카메라를 다양한 백엔드로 열어 깨끗한 스트림을 반환합니다."""
    # 1. DirectShow 시도
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    # 2. Media Foundation 시도 (USB 외장 웹캠 인식 지원)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index, cv2.CAP_MSMF)
    # 3. 기본 백엔드 시도
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
    
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        for _ in range(5):
            cap.read()
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[카메라 {index}] 연결 완료 (해상도: {w}x{h})")
    return cap


def enumerate_cameras(max_check=6):
    """사용 가능한 카메라 목록 반환 (외장 카메라 탐색 범위 확대)."""
    available = []
    for i in range(max_check):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(i, cv2.CAP_MSMF)

        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available.append(i)
            cap.release()
    return available if available else [0]


# ══════════════════════════════════════════════════════════
#  랜드마크 직접 그리기 (OpenCV)
# ══════════════════════════════════════════════════════════

def draw_hand_landmarks(image, lm_list, connections=HAND_CONNECTIONS_SET,
                        landmark_color=(0, 0, 255), connection_color=(0, 255, 0),
                        thickness=2, circle_radius=3):
    """NormalizedLandmark 리스트를 이미지에 그림."""
    h, w, _ = image.shape
    px = [(int(l.x * w), int(l.y * h)) for l in lm_list]

    # 연결선
    for start, end in connections:
        if start < len(px) and end < len(px):
            cv2.line(image, px[start], px[end], connection_color, thickness, cv2.LINE_AA)

    # 포인트
    for pt in px:
        cv2.circle(image, pt, circle_radius, landmark_color, -1, cv2.LINE_AA)


# ══════════════════════════════════════════════════════════
#  학습 모드 – Tkinter 모달
# ══════════════════════════════════════════════════════════

class LearningModal:
    """학습 모드에서 캡처된 이미지와 동작 선택을 보여주는 Tkinter 창."""

    def __init__(self, captured_frame, detected_gesture, lm_list):
        self.captured_frame = captured_frame
        self.detected_gesture = detected_gesture
        self.lm_list = lm_list
        self.result = None

    def show(self):
        """모달을 표시하고 사용자 입력을 기다림."""
        self.root = tk.Tk()
        self.root.title("학습 모드 – 동작 확인")
        self.root.configure(bg="#1a1a2e")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        # ── 제목 ──
        title = tk.Label(self.root, text="이 동작은 무엇인가요?",
                         font=("맑은 고딕", 16, "bold"), fg="#e0e0e0", bg="#1a1a2e")
        title.pack(pady=(16, 8))

        # ── 캡처된 이미지 ──
        img_rgb = cv2.cvtColor(self.captured_frame, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_pil = img_pil.resize((400, 300), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img_pil)
        img_label = tk.Label(self.root, image=self._photo, bg="#1a1a2e",
                             bd=2, relief="groove")
        img_label.pack(pady=8)

        # ── AI 인식 결과 ──
        det_label = tk.Label(self.root,
                             text=f"AI 인식 결과: {self.detected_gesture}",
                             font=("맑은 고딕", 11), fg="#90caf9", bg="#1a1a2e")
        det_label.pack(pady=(0, 12))

        # ── 동작 선택 버튼 프레임 ──
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(pady=4, padx=16, fill="x")

        all_names = [name for name, _ in GESTURE_DEFINITIONS]
        all_names += [cg["name"] for cg in custom_gestures]

        col, row = 0, 0
        for name in all_names:
            btn = tk.Button(btn_frame, text=name, width=20,
                            font=("맑은 고딕", 10),
                            fg="#e0e0e0", bg="#2a2a4a", activebackground="#4a4a7a",
                            relief="flat", bd=0, cursor="hand2",
                            command=lambda n=name: self._select(n))
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="ew")
            col += 1
            if col >= 2:
                col = 0
                row += 1

        next_row = row + 1 if col == 0 else row + 2

        # 기타 버튼
        btn_other = tk.Button(btn_frame, text="✏️ 기타 (새 동작)", width=20,
                              font=("맑은 고딕", 10),
                              fg="#a5d6a7", bg="#1b3a1b", activebackground="#2d5a2d",
                              relief="flat", bd=0, cursor="hand2",
                              command=self._on_other)
        btn_other.grid(row=next_row, column=0, padx=4, pady=4, sticky="ew")

        # 재시도 버튼
        btn_retry = tk.Button(btn_frame, text="🔄 재시도", width=20,
                              font=("맑은 고딕", 10),
                              fg="#ffd54f", bg="#3a3000", activebackground="#5a4a00",
                              relief="flat", bd=0, cursor="hand2",
                              command=self._on_retry)
        btn_retry.grid(row=next_row, column=1, padx=4, pady=4, sticky="ew")

        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        # ── 기타 입력 영역 (숨김) ──
        self.custom_frame = tk.Frame(self.root, bg="#1a1a2e")

        self.custom_entry = tk.Entry(self.custom_frame, font=("맑은 고딕", 11),
                                     bg="#2a2a4a", fg="#e0e0e0",
                                     insertbackground="#e0e0e0",
                                     relief="flat", bd=2)
        self.custom_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.custom_entry.bind("<Return>", lambda e: self._confirm_custom())

        btn_confirm = tk.Button(self.custom_frame, text="확인",
                                font=("맑은 고딕", 10, "bold"),
                                fg="#fff", bg="#6c63ff", activebackground="#8a7fff",
                                relief="flat", bd=0, cursor="hand2",
                                command=self._confirm_custom)
        btn_confirm.pack(side="right")

        # 창 닫기 처리
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 창 중앙 배치
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

        self.root.mainloop()
        return self.result

    def _select(self, name):
        self.result = name
        self.root.destroy()

    def _on_retry(self):
        self.result = "__RETRY__"
        self.root.destroy()

    def _on_other(self):
        self.custom_frame.pack(pady=8, padx=16, fill="x")
        self.custom_entry.focus_set()

    def _confirm_custom(self):
        name = self.custom_entry.get().strip()
        if not name:
            self.custom_entry.configure(bg="#4a2020")
            self.root.after(500, lambda: self.custom_entry.configure(bg="#2a2a4a"))
            return

        # 중복 검사
        existing = [n for n, _ in GESTURE_DEFINITIONS] + [cg["name"] for cg in custom_gestures]
        if name in existing:
            messagebox.showwarning("중복", f'"{name}" 동작은 이미 존재합니다.',
                                   parent=self.root)
            return

        # 커스텀 동작 등록
        if self.lm_list:
            lm_data = landmarks_to_dicts(self.lm_list)
        else:
            lm_data = []

        custom_gestures.append({"name": name, "landmarks": lm_data})
        save_custom_gestures(custom_gestures)
        print(f'[학습 모드] 새 동작 추가: "{name}" (랜드마크 {len(lm_data)}개 저장)')

        self.result = name
        self.root.destroy()

    def _on_close(self):
        self.result = None
        self.root.destroy()


# ══════════════════════════════════════════════════════════
#  Photo_Learning 저장
# ══════════════════════════════════════════════════════════

def save_photo(frame, gesture_name):
    """캡처 이미지를 Photo_Learning 폴더에 저장."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("_", "-", " ") else "_"
                        for c in gesture_name)
    filename = f"{safe_name}_{timestamp}.png"
    filepath = os.path.join(PHOTO_DIR, filename)
    cv2.imwrite(filepath, frame)
    print(f"[Photo_Learning] 저장됨: {filepath}")


# ══════════════════════════════════════════════════════════
#  메인 루프
# ══════════════════════════════════════════════════════════

def main():
    if not os.path.exists(MODEL_PATH):
        print(f"[오류] 모델 파일이 없습니다: {MODEL_PATH}")
        return

    cameras = enumerate_cameras()
    cam_idx = 0
    print(f"[카메라] 사용 가능 탐색 결과: {cameras}")

    cap = open_camera(cameras[cam_idx])

    if not cap.isOpened():
        print("카메라를 열 수 없습니다.")
        return

    with open(MODEL_PATH, "rb") as f:
        model_data = f.read()
    base_options = BaseOptions(model_asset_buffer=model_data)
    options = HandLandmarkerOptions(
        base_options=base_options,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.7,
        min_tracking_confidence=0.7,
        running_mode=RunningMode.IMAGE,
    )

    landmarker = HandLandmarker.create_from_options(options)

    learning_active = False
    countdown_start = 0.0
    countdown_seconds = 3
    current_gesture = "대기 중..."
    latest_landmarks = None

    window_name = "Hand Gesture Recognition"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 800, 600)

    print("\n[조작법]")
    print("  L : 학습 모드 시작")
    print("  C : 카메라 전환")
    print("  Q : 종료\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("프레임을 읽을 수 없습니다.")
            break

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        display = frame.copy()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_image)

        if result.hand_landmarks:
            lm_list = result.hand_landmarks[0]
            draw_hand_landmarks(display, lm_list)
            current_gesture = recognize_gesture(lm_list)
            latest_landmarks = lm_list
        else:
            current_gesture = "-"
            latest_landmarks = None

        if learning_active:
            elapsed = time.time() - countdown_start
            remaining = countdown_seconds - int(elapsed)

            if remaining > 0:
                overlay = display.copy()
                cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.45, display, 0.55, 0, display)

                text = str(remaining)
                font = cv2.FONT_HERSHEY_SIMPLEX
                scale = 6.0
                thickness = 12
                (tw, th_text), _ = cv2.getTextSize(text, font, scale, thickness)
                tx = (w - tw) // 2
                ty = (h + th_text) // 2

                cv2.putText(display, text, (tx, ty), font, scale,
                            (255, 200, 0), thickness + 8, cv2.LINE_AA)
                cv2.putText(display, text, (tx, ty), font, scale,
                            (255, 255, 255), thickness, cv2.LINE_AA)
            else:
                learning_active = False
                captured = display.copy()

                modal = LearningModal(captured, current_gesture, latest_landmarks)
                choice = modal.show()

                if choice == "__RETRY__":
                    learning_active = True
                    countdown_start = time.time()
                elif choice is not None:
                    save_photo(captured, choice)
                    print(f'[학습 모드] 확인된 동작: "{choice}"')

        cv2.rectangle(display, (0, h - 50), (w, h), (0, 0, 0), -1)

        gesture_text = f"Gesture: {current_gesture}"
        cv2.putText(display, gesture_text, (10, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (160, 255, 160), 2, cv2.LINE_AA)

        cam_text = f"Cam: {cameras[cam_idx]}  |  L:Learn  C:Switch  Q:Quit"
        cv2.putText(display, cam_text, (w - 420, h - 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1, cv2.LINE_AA)

        if not learning_active:
            cv2.rectangle(display, (10, 10), (170, 50), (108, 99, 255), -1)
            cv2.putText(display, "L: Learn Mode", (18, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

            acc_val = load_accuracy()
            acc_txt = f"Accuracy: {acc_val:.3f}"
            cv2.rectangle(display, (w - 200, 10), (w - 10, 50), (30, 30, 60), -1)
            cv2.putText(display, acc_txt, (w - 188, 38),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 220, 100), 2, cv2.LINE_AA)

        cv2.imshow(window_name, display)

        if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
            break

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q') or key == ord('Q') or key == 27:
            break
        elif (key == ord('l') or key == ord('L')) and not learning_active:
            learning_active = True
            countdown_start = time.time()
            print("[학습 모드] 카운트다운 시작")
        elif key == ord('c') or key == ord('C'):
            cam_idx = (cam_idx + 1) % len(cameras)
            cap.release()
            cap = open_camera(cameras[cam_idx])
            print(f"[카메라] 전환 → {cameras[cam_idx]}")

    if 'landmarker' in locals():
        landmarker.close()
    if 'cap' in locals() and cap is not None:
        cap.release()
    cv2.destroyAllWindows()
    print("[시스템] 카메라 및 프로그램이 정상 종료되었습니다.")


if __name__ == "__main__":
    main()
