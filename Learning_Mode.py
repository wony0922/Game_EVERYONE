"""
Learning_Mode.py – 손 동작 5회 학습 및 테스트 모드 + 최종 반영 시스템
MediaPipe 1.0 (Tasks API) + OpenCV + Tkinter (WiFi 불필요, 100% 오프라인)
"""

import cv2
import mediapipe as mp
import os
import json
import time
import math
import tkinter as tk
from PIL import Image, ImageTk
from datetime import datetime
from camera_utils import open_camera as open_platform_camera
from ui_font import get_tk_font_family


# ══════════════════════════════════════════════════════════
#  경로 및 파일 설정
# ══════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(BASE_DIR, "Photo_Learning")
CUSTOM_GESTURES_FILE = os.path.join(BASE_DIR, "custom_gestures.json")
ACCURACY_FILE = os.path.join(BASE_DIR, "accuracy_score.json")
MODEL_PATH = os.path.join(BASE_DIR, "hand_landmarker.task")

os.makedirs(PHOTO_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════
#  정확도(Accuracy) 관리 (범위: 0.0 ~ 1.0)
# ══════════════════════════════════════════════════════════
DEFAULT_ACCURACY = 0.800


def load_accuracy():
    if os.path.exists(ACCURACY_FILE):
        try:
            with open(ACCURACY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return float(data.get("accuracy", DEFAULT_ACCURACY))
        except Exception:
            return DEFAULT_ACCURACY
    return DEFAULT_ACCURACY


def save_accuracy(acc, reason=""):
    acc = max(0.0, min(1.0, round(acc, 3)))
    history = []
    if os.path.exists(ACCURACY_FILE):
        try:
            with open(ACCURACY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                history = data.get("history", [])
        except Exception:
            history = []

    history.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "accuracy": acc,
        "reason": reason
    })

    history = history[-50:]

    with open(ACCURACY_FILE, "w", encoding="utf-8") as f:
        json.dump({"accuracy": acc, "history": history}, f, ensure_ascii=False, indent=2)

    return acc


def calculate_accuracy_on_yes(current_acc):
    improvement = (1.0 - current_acc) * 0.20 + 0.025
    return min(1.0, round(current_acc + improvement, 3))


def calculate_accuracy_on_no(current_acc):
    penalty = current_acc * 0.15 + 0.030
    return max(0.0, round(current_acc - penalty, 3))


# ══════════════════════════════════════════════════════════
#  기본 제스처 정의 (4종)
# ══════════════════════════════════════════════════════════
def _dy(a, b):
    return abs(a.y - b.y)


def _dx(a, b):
    return abs(a.x - b.x)


def detect_open_palm(lm):
    index, middle, ring, pinky, wrist = lm[8], lm[12], lm[16], lm[20], lm[0]
    return all(_dy(p, wrist) > 0.04 and _dx(p, wrist) > 0.015
               for p in [index, middle, ring, pinky])


def detect_fist(lm):
    index, middle, ring, pinky, wrist = lm[8], lm[12], lm[16], lm[20], lm[0]
    return all(_dy(p, wrist) < 0.18 and _dx(p, wrist) < 0.12
               for p in [index, middle, ring, pinky])


def detect_point(lm):
    index, middle, ring, pinky, wrist = lm[8], lm[12], lm[16], lm[20], lm[0]
    return (_dy(index, wrist) > 0.04 and
            all(_dy(p, wrist) < 0.18 and _dx(p, wrist) < 0.15
                for p in [middle, ring, pinky]))


def detect_victory(lm):
    index, middle, ring, pinky, wrist = lm[8], lm[12], lm[16], lm[20], lm[0]
    return (_dy(index, wrist) > 0.1 and _dy(middle, wrist) > 0.1 and
            all(_dy(p, wrist) < 0.09 and _dx(p, wrist) < 0.06
                for p in [ring, pinky]))


BASE_GESTURES = [
    ("펴진 손 (Open Palm)", detect_open_palm),
    ("주먹 (Fist)", detect_fist),
    ("가리키기 (Point)", detect_point),
    ("승리 V (Victory)", detect_victory),
]


# ══════════════════════════════════════════════════════════
#  커스텀 제스처 관리
# ══════════════════════════════════════════════════════════
def load_custom_gestures():
    if os.path.exists(CUSTOM_GESTURES_FILE):
        try:
            with open(CUSTOM_GESTURES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_custom_gestures(gestures):
    with open(CUSTOM_GESTURES_FILE, "w", encoding="utf-8") as f:
        json.dump(gestures, f, ensure_ascii=False, indent=2)


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
    return [{"x": float(l.x), "y": float(l.y), "z": float(l.z)} for l in lm_list]


def recognize_gesture(lm_list, custom_list, session_samples=None):
    for name, detect_fn in BASE_GESTURES:
        if detect_fn(lm_list):
            return name

    candidates = list(custom_list)
    if session_samples:
        candidates.extend(session_samples)

    lm_dicts = landmarks_to_dicts(lm_list)
    best_name = None
    best_dist = float("inf")

    for cg in candidates:
        stored = cg.get("landmarks", [])
        if not stored:
            continue
        dist = landmark_distance(lm_dicts, stored)
        if dist < best_dist:
            best_dist = dist
            best_name = cg["name"]

    if best_name and best_dist < 0.38:
        return best_name

    return "알 수 없음"


# ══════════════════════════════════════════════════════════
#  Photo_Learning 사진 저장
# ══════════════════════════════════════════════════════════
def save_photo(frame, gesture_name, prefix="Train"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("_", "-", " ") else "_" for c in gesture_name)
    filename = f"{prefix}_{safe_name}_{timestamp}.png"
    filepath = os.path.join(PHOTO_DIR, filename)
    cv2.imwrite(filepath, frame)
    print(f"[Photo_Learning] 캡처 저장 완료: {filepath}")
    return filepath


# ══════════════════════════════════════════════════════════
#  Tkinter 모달: 학습 데이터 라벨링 확인
# ══════════════════════════════════════════════════════════
class LearningModal:
    def __init__(self, frame, detected_gesture, lm_list, existing_customs, session_samples, sample_index):
        self.captured_frame = frame
        self.detected_gesture = detected_gesture
        self.lm_list = lm_list
        self.existing_customs = existing_customs
        self.session_samples = session_samples
        self.sample_index = sample_index
        self.result_name = None
        self.root = None

    def show(self):
        self.root = tk.Tk()
        self.font_family = get_tk_font_family(self.root)
        self.root.title(f"학습 모드 – 데이터 수집 ({self.sample_index}/5)")
        self.root.configure(bg="#13141f")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        header = tk.Label(self.root, text=f"🎯 학습 데이터 등록 ({self.sample_index} / 5번째)",
                          font=(self.font_family, 15, "bold"), fg="#ffd54f", bg="#13141f")
        header.pack(pady=(16, 6))

        sub = tk.Label(self.root, text="캡처된 손 동작이 무엇인지 선택하거나 새로 입력해 주세요.",
                       font=(self.font_family, 10), fg="#a0a0b0", bg="#13141f")
        sub.pack(pady=(0, 10))

        img_rgb = cv2.cvtColor(self.captured_frame, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb).resize((380, 280), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img_pil)
        img_label = tk.Label(self.root, image=self._photo, bg="#13141f", bd=2, relief="groove")
        img_label.pack(pady=4)

        ai_box = tk.Label(self.root, text=f"현재 감지된 동작: {self.detected_gesture}",
                          font=(self.font_family, 11, "bold"), fg="#82b1ff", bg="#1c1e2f",
                          padx=12, pady=6, relief="ridge")
        ai_box.pack(pady=10)

        btn_frame = tk.Frame(self.root, bg="#13141f")
        btn_frame.pack(pady=6, padx=20, fill="x")

        all_names = [n for n, _ in BASE_GESTURES]
        all_names += [cg["name"] for cg in self.existing_customs]
        all_names += [s["name"] for s in self.session_samples if s["name"] not in all_names]

        col, row = 0, 0
        for name in all_names:
            btn = tk.Button(btn_frame, text=name, font=(self.font_family, 10),
                            fg="#ffffff", bg="#252840", activebackground="#3d426b",
                            relief="flat", cursor="hand2",
                            command=lambda n=name: self._choose(n))
            btn.grid(row=row, column=col, padx=4, pady=4, sticky="ew")
            col += 1
            if col >= 2:
                col = 0
                row += 1

        next_row = row + 1 if col == 0 else row + 2

        btn_other = tk.Button(btn_frame, text="✏️ 직접 새 동작 입력", font=(self.font_family, 10, "bold"),
                              fg="#69f0ae", bg="#1b3d2b", activebackground="#2a5d42",
                              relief="flat", cursor="hand2", command=self._show_input)
        btn_other.grid(row=next_row, column=0, padx=4, pady=4, sticky="ew")

        btn_retry = tk.Button(btn_frame, text="🔄 다시 캡처 (재시도)", font=(self.font_family, 10),
                              fg="#ffab91", bg="#3e231e", activebackground="#5e342d",
                              relief="flat", cursor="hand2", command=self._retry)
        btn_retry.grid(row=next_row, column=1, padx=4, pady=4, sticky="ew")

        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        self.entry_frame = tk.Frame(self.root, bg="#13141f")
        self.entry = tk.Entry(self.entry_frame, font=(self.font_family, 11),
                              bg="#202336", fg="#ffffff", insertbackground="#ffffff",
                              relief="flat", bd=4)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._confirm_entry())

        btn_ok = tk.Button(self.entry_frame, text="등록", font=(self.font_family, 10, "bold"),
                           fg="#ffffff", bg="#6c5ce7", activebackground="#8375f0",
                           relief="flat", cursor="hand2", command=self._confirm_entry)
        btn_ok.pack(side="right")

        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

        self.root.mainloop()
        return self.result_name

    def _choose(self, name):
        self.result_name = name
        self.root.destroy()

    def _retry(self):
        self.result_name = "__RETRY__"
        self.root.destroy()

    def _show_input(self):
        self.entry_frame.pack(pady=8, padx=20, fill="x")
        self.entry.focus_set()

    def _confirm_entry(self):
        name = self.entry.get().strip()
        if not name:
            return
        self.result_name = name
        self.root.destroy()


# ══════════════════════════════════════════════════════════
#  Tkinter 모달: 테스트 후 최종 반영 (YES / NO) 확인
# ══════════════════════════════════════════════════════════
class FinalConfirmationModal:
    def __init__(self, current_accuracy, session_samples):
        self.current_accuracy = current_accuracy
        self.session_samples = session_samples
        self.expected_yes_acc = calculate_accuracy_on_yes(current_accuracy)
        self.expected_no_acc = calculate_accuracy_on_no(current_accuracy)
        self.decision = None
        self.root = None

    def show(self):
        self.root = tk.Tk()
        self.font_family = get_tk_font_family(self.root)
        self.root.title("학습 결과 최종 반영 여부 확인")
        self.root.configure(bg="#11131e")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        title = tk.Label(self.root, text="📢 테스트 완료: 기본 모드에 최종 반영할까요?",
                         font=(self.font_family, 15, "bold"), fg="#ffffff", bg="#11131e")
        title.pack(pady=(20, 8), padx=20)

        desc = tk.Label(self.root, text="테스트 모드에서 확인한 신규 5개 동작을 기본 모드(메인 데이터베이스)에 저장할지 결정하세요.",
                        font=(self.font_family, 10), fg="#a4b0be", bg="#11131e")
        desc.pack(pady=(0, 16), padx=20)

        list_box = tk.LabelFrame(self.root, text=" 5개 학습 완료 항목 ",
                                 font=(self.font_family, 10, "bold"), fg="#ffd32a", bg="#1e2235", padx=12, pady=8)
        list_box.pack(fill="x", padx=24, pady=6)

        for i, s in enumerate(self.session_samples, start=1):
            lbl = tk.Label(list_box, text=f"• [{i}/5] 동작명: {s['name']}",
                           font=(self.font_family, 10), fg="#f1f2f6", bg="#1e2235", anchor="w")
            lbl.pack(fill="x", pady=2)

        acc_frame = tk.Frame(self.root, bg="#181a29", bd=1, relief="solid", padx=16, pady=12)
        acc_frame.pack(fill="x", padx=24, pady=16)

        curr_lbl = tk.Label(acc_frame, text=f"현재 모델 정확도: {self.current_accuracy:.3f}",
                            font=(self.font_family, 11, "bold"), fg="#70a1ff", bg="#181a29")
        curr_lbl.pack(pady=2)

        yes_info = tk.Label(acc_frame, text=f"▶ YES 선택 시: {self.current_accuracy:.3f} ➔ {self.expected_yes_acc:.3f} (정확도 상승 📈)",
                            font=(self.font_family, 10, "bold"), fg="#2ed573", bg="#181a29")
        yes_info.pack(pady=3)

        no_info = tk.Label(acc_frame, text=f"▶ NO  선택 시: {self.current_accuracy:.3f} ➔ {self.expected_no_acc:.3f} (반영 취소 및 감점 📉)",
                           font=(self.font_family, 10), fg="#ff4757", bg="#181a29")
        no_info.pack(pady=3)

        btn_box = tk.Frame(self.root, bg="#11131e")
        btn_box.pack(pady=(8, 20), padx=24, fill="x")

        btn_yes = tk.Button(btn_box, text="✔ YES (기본 모드에 최종 반영)",
                            font=(self.font_family, 11, "bold"), fg="#ffffff", bg="#20bf6b",
                            activebackground="#26de81", height=2, relief="flat", cursor="hand2",
                            command=self._on_yes)
        btn_yes.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_no = tk.Button(btn_box, text="✖ NO (반영 취소 및 폐기)",
                           font=(self.font_family, 11, "bold"), fg="#ffffff", bg="#eb3b5a",
                           activebackground="#fc5c65", height=2, relief="flat", cursor="hand2",
                           command=self._on_no)
        btn_no.pack(side="right", fill="x", expand=True, padx=(8, 0))

        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

        self.root.mainloop()
        return self.decision

    def _on_yes(self):
        self.decision = True
        self.root.destroy()

    def _on_no(self):
        self.decision = False
        self.root.destroy()


# ══════════════════════════════════════════════════════════
#  카메라 및 MediaPipe 유틸 (USB 카메라 다중 지원 추가)
# ══════════════════════════════════════════════════════════
def open_camera(index=0):
    return open_platform_camera(index)


HAND_CONNECTIONS = mp.tasks.vision.HandLandmarksConnections.HAND_CONNECTIONS
HAND_CONN_SET = frozenset((c.start, c.end) for c in HAND_CONNECTIONS)


def draw_landmarks_cv(image, lm_list):
    h, w, _ = image.shape
    pts = [(int(l.x * w), int(l.y * h)) for l in lm_list]
    for s, e in HAND_CONN_SET:
        if s < len(pts) and e < len(pts):
            cv2.line(image, pts[s], pts[e], (0, 255, 128), 2, cv2.LINE_AA)
    for p in pts:
        cv2.circle(image, p, 5, (0, 165, 255), -1, cv2.LINE_AA)
        cv2.circle(image, p, 2, (255, 255, 255), -1, cv2.LINE_AA)


# ══════════════════════════════════════════════════════════
#  메인 실행 루틴
# ══════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print(" [Learning_Mode] 5회 학습 ➔ 테스트 모드 ➔ 최종 반영 시스템 ")
    print("=" * 60)

    if not os.path.exists(MODEL_PATH):
        print(f"[오류] MediaPipe 모델 파일이 없습니다: {MODEL_PATH}")
        return

    with open(MODEL_PATH, "rb") as f:
        model_bytes = f.read()

    base_opts = mp.tasks.BaseOptions(model_asset_buffer=model_bytes)
    opts = mp.tasks.vision.HandLandmarkerOptions(
        base_options=base_opts,
        num_hands=1,
        min_hand_detection_confidence=0.7,
        min_hand_presence_confidence=0.7,
        min_tracking_confidence=0.7,
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
    )
    landmarker = mp.tasks.vision.HandLandmarker.create_from_options(opts)

    cap = open_camera(0)
    if not cap.isOpened():
        print("[오류] 카메라를 열 수 없습니다.")
        return

    existing_customs = load_custom_gestures()
    current_accuracy = load_accuracy()
    session_samples = []

    app_mode = "COLLECT"
    countdown_active = False
    countdown_start = 0.0
    countdown_secs = 5
    current_detected = "-"
    latest_lm = None

    window_name = "Learning & Test Mode"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1000, 700)

    print("\n[안내]")
    print("  1. 'L' 키를 눌러 5초 카운트다운 후 손 동작을 캡처하세요 (총 5개).")
    print("  2. 5개가 모두 채워지면 신규 학습이 반영된 [테스트 모드]로 자동 진입합니다.")
    print("  3. 테스트 후 [Space] 또는 [Enter]를 눌러 기본 모드 최종 반영(YES/NO)을 결정합니다.")
    print("  4. 'Q' 또는 'ESC'로 종료합니다.\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape
            display = frame.copy()

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = landmarker.detect(mp_img)

            if res.hand_landmarks:
                latest_lm = res.hand_landmarks[0]
                draw_landmarks_cv(display, latest_lm)

                if app_mode == "COLLECT":
                    current_detected = recognize_gesture(latest_lm, existing_customs)
                else:
                    current_detected = recognize_gesture(latest_lm, existing_customs, session_samples)
            else:
                current_detected = "-"
                latest_lm = None

            if app_mode == "COLLECT" and countdown_active:
                elapsed = time.time() - countdown_start
                remaining = countdown_secs - int(elapsed)

                if remaining > 0:
                    overlay = display.copy()
                    cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.4, display, 0.6, 0, display)

                    txt = str(remaining)
                    (tw, th_txt), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 6.0, 12)
                    tx = (w - tw) // 2
                    ty = (h + th_txt) // 2
                    cv2.putText(display, txt, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 6.0, (255, 200, 0), 16, cv2.LINE_AA)
                    cv2.putText(display, txt, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 6.0, (255, 255, 255), 10, cv2.LINE_AA)
                else:
                    countdown_active = False
                    captured = display.copy()
                    sample_idx = len(session_samples) + 1

                    modal = LearningModal(captured, current_detected, latest_lm,
                                          existing_customs, session_samples, sample_idx)
                    chosen_name = modal.show()

                    if chosen_name == "__RETRY__":
                        countdown_active = True
                        countdown_start = time.time()
                    elif chosen_name is not None:
                        save_photo(captured, chosen_name, prefix=f"Train_{sample_idx}")

                        lm_data = landmarks_to_dicts(latest_lm) if latest_lm else []
                        session_samples.append({
                            "name": chosen_name,
                            "landmarks": lm_data
                        })
                        print(f"[학습 진행] ({len(session_samples)}/5) '{chosen_name}' 등록 완료")

                        if len(session_samples) >= 5:
                            app_mode = "TEST"
                            print("\n" + "★" * 60)
                            print(" [알림] 5개 학습 완료! 신규 학습이 반영된 [테스트 모드]로 전환되었습니다.")
                            print(" 화면에서 손을 움직여 인식 결과를 테스트해 보세요.")
                            print(" 테스트가 끝나면 [Space] 키를 눌러 최종 반영 여부를 선택하세요.")
                            print("★" * 60 + "\n")

            top_bar_color = (40, 40, 80) if app_mode == "COLLECT" else (20, 80, 40)
            cv2.rectangle(display, (0, 0), (w, 55), top_bar_color, -1)

            if app_mode == "COLLECT":
                mode_str = f"MODE: DATA COLLECTION ({len(session_samples)}/5)  |  Press 'L' to Capture"
                cv2.putText(display, mode_str, (15, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
            else:
                mode_str = "TEST MODE (5 New Samples Applied)  |  [Space]: Final Decision (YES/NO)"
                cv2.putText(display, mode_str, (15, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 255, 150), 2, cv2.LINE_AA)

            acc_str = f"Accuracy: {current_accuracy:.3f}"
            (aw, _), _ = cv2.getTextSize(acc_str, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            cv2.putText(display, acc_str, (w - aw - 20, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 220, 100), 2, cv2.LINE_AA)

            cv2.rectangle(display, (0, h - 50), (w, h), (15, 15, 25), -1)
            rec_text = f"Recognized: {current_detected}"
            cv2.putText(display, rec_text, (15, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (160, 255, 160), 2, cv2.LINE_AA)

            if app_mode == "COLLECT" and not countdown_active:
                hint = "Press 'L': Learn (5s)  |  'Q': Quit"
            elif app_mode == "TEST":
                hint = "Press [Space]: Final Confirmation  |  'Q': Quit"
            else:
                hint = "Capturing in progress..."
            cv2.putText(display, hint, (w - 480, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)

            cv2.imshow(window_name, display)

            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break

            key = cv2.waitKey(1) & 0xFF

            if key == ord('q') or key == ord('Q') or key == 27:
                break

            elif (key == ord('l') or key == ord('L')) and app_mode == "COLLECT" and not countdown_active:
                if len(session_samples) < 5:
                    countdown_active = True
                    countdown_start = time.time()
                    print(f"\n[학습 시작] {len(session_samples) + 1}번째 동작 캡처 5초 카운트다운 시작...")

            elif (key == 32 or key == 13) and app_mode == "TEST":
                confirm_modal = FinalConfirmationModal(current_accuracy, session_samples)
                decision = confirm_modal.show()

                if decision is True:
                    for s in session_samples:
                        existing_customs.append(s)
                    save_custom_gestures(existing_customs)

                    new_acc = calculate_accuracy_on_yes(current_accuracy)
                    current_accuracy = save_accuracy(new_acc, reason="YES: 5개 신규 학습 최종 반영 승인")

                    print("\n" + "★" * 60)
                    print(f" [반영 완료] 5개 학습 데이터가 기본 모드에 최종 반영되었습니다!")
                    print(f" 정확도 수치 상승: ➔ {current_accuracy:.3f}")
                    print("★" * 60 + "\n")

                    session_samples = []
                    app_mode = "COLLECT"

                elif decision is False:
                    new_acc = calculate_accuracy_on_no(current_accuracy)
                    current_accuracy = save_accuracy(new_acc, reason="NO: 신규 학습 데이터 반영 거부")

                    print("\n" + "▼" * 60)
                    print(" [반영 취소] 신규 학습 데이터 5개가 폐기되었습니다.")
                    print(f" 정확도 수치 하락: ➔ {current_accuracy:.3f}")
                    print("▼" * 60 + "\n")

                    session_samples = []
                    app_mode = "COLLECT"

    finally:
        if 'landmarker' in locals():
            landmarker.close()
        if 'cap' in locals() and cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        print("[시스템] 카메라 자원이 안전하게 해제되었습니다.")


if __name__ == "__main__":
    main()
