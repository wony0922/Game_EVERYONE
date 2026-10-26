"""SuperTuxKart 를 손동작으로 조작한다.  (Raspberry Pi OS / Windows)

SuperTuxKart(오픈소스 GPL 카트 레이싱)를 메뉴 없이 바로 경주가 시작되도록 실행하고,
손 상태를 가상 키보드 입력으로 바꿔 보낸다.
실행/종료/가상 입력 처리는 external_game.py 공통 모듈이 한다.

손동작 조작
  손 좌우            -> 핸들 (가운데서 멀수록 크게 꺾임)
  손바닥 / 그 외     -> 가속 (손이 보이면 기본으로 달린다)
  주먹               -> 브레이크 / 후진
  가리키기           -> 아이템 사용 (가속은 유지)
  손을 높이 들기     -> 니트로
  손을 아래로 내리기 -> 가속 멈춤
  V 1초 유지         -> 종료

설치: 프로젝트 루트에서
  라즈베리파이: python3 install_supertuxkart.py
  윈도우:       py -3.14 install_supertuxkart.py
"""

import os
import shutil

from external_game import (
    IS_LINUX, IS_WINDOWS, HandMapper, axis_strength,
    check_virtual_input_ready, run_external_game, show_error, windows_game_home,
)

# ══════════════════════════════════════════════════════════
#  경주 설정
# ══════════════════════════════════════════════════════════
TRACK = "lighthouse"   # 가볍고 짧은 트랙. 다른 예: zengarden, sandtrack, cornfield_crossing
KART = "tux"
LAPS = "2"
DIFFICULTY = "0"       # 0 초보, 1 중급, 2 전문가, 3 슈퍼턱스

if IS_WINDOWS:
    NUM_KARTS = "6"
    DISPLAY_ARGS = ["--fullscreen"]
else:
    # 라즈베리파이 4: 상대 카트 수와 해상도를 줄여야 부드럽게 돈다
    NUM_KARTS = "4"
    DISPLAY_ARGS = ["--windowed", "--screensize=960x540"]

# 손 위치 판정 (화면 좌표 0~1, 가운데 0.5)
STEER_DEADZONE = 0.06
STEER_FULL_AT = 0.28        # 이만큼 치우치면 핸들을 끝까지 꺾은 상태
STEER_PERIOD_SEC = 0.12     # 살짝 꺾을 때 방향키를 짧게 끊어 누르는 주기
NITRO_THRESHOLD = 0.22      # 손을 이만큼 올리면 니트로
COAST_THRESHOLD = 0.18      # 손을 이만큼 내리면 가속 멈춤

if IS_WINDOWS:
    STK_HOME = windows_game_home("supertuxkart")
    STK_EXE = os.path.join(STK_HOME, "stk-code", "build-x86_64", "bin", "supertuxkart.exe")
    INSTALL_HINT = "프로젝트 폴더에서  py -3.14 install_supertuxkart.py  를 실행해 주세요."
else:
    STK_HOME = None
    STK_EXE = None
    INSTALL_HINT = "프로젝트 폴더에서  python3 install_supertuxkart.py  를 실행해 주세요."

TITLE = "SUPERTUXKART"
TITLE_COLOR = (255, 200, 60)
GUIDE_LINES = [
    "손 좌우 : 핸들        손이 보이면 자동 가속",
    "주먹 : 브레이크        가리키기 : 아이템",
    "손 높이 들기 : 니트로        V 1초 유지 : 메뉴로",
]


# ══════════════════════════════════════════════════════════
#  손 상태 -> 카트 조작
#  SuperTuxKart 기본 키: ↑ 가속, ↓ 브레이크, ←→ 핸들, Space 아이템, N 니트로
# ══════════════════════════════════════════════════════════
class KartHandMapper(HandMapper):
    KEYS = ("up", "down", "left", "right", "space", "n")
    USES_MOUSE = False

    def __init__(self, output=None):
        super().__init__(output)
        self.steer_phase = 0.0

    def reset(self):
        self.steer_phase = 0.0

    def compute(self, hand_x, hand_y, gesture, dt):
        wanted = set()

        # ── 핸들 (손 좌우) ──
        # 방향키는 켜짐/꺼짐뿐이라, 살짝 꺾을 때는 짧게 끊어 눌러서
        # 꺾는 정도를 흉내 낸다 (세기 0.4 = 주기의 40% 동안 누름).
        dx = hand_x - 0.5
        strength = axis_strength(dx, STEER_DEADZONE, STEER_FULL_AT)
        self.steer_phase = (self.steer_phase + dt / STEER_PERIOD_SEC) % 1.0
        if strength >= 0.999 or (strength > 0 and self.steer_phase < strength):
            wanted.add("right" if dx > 0 else "left")

        # ── 가속 / 브레이크 / 아이템 / 니트로 ──
        dy = 0.5 - hand_y          # 위로 갈수록 +
        if gesture == "Fist":
            wanted.add("down")     # 브레이크 / 후진
        elif dy > -COAST_THRESHOLD:
            wanted.add("up")       # 가속 (손바닥, 가리키기, 인식 애매할 때 모두)
            if gesture == "Point":
                wanted.add("space")   # 아이템
            if dy > NITRO_THRESHOLD:
                wanted.add("n")       # 니트로
        return wanted


# ══════════════════════════════════════════════════════════
#  준비 확인
# ══════════════════════════════════════════════════════════
def _find_engine():
    if IS_WINDOWS:
        return STK_EXE if os.path.isfile(STK_EXE) else None
    path = shutil.which("supertuxkart")
    if path:
        return path
    if os.path.exists("/usr/games/supertuxkart"):
        return "/usr/games/supertuxkart"
    return None


def _check_ready():
    if not (IS_WINDOWS or IS_LINUX):
        return ["SuperTuxKart는 Windows와 라즈베리파이에서만 실행됩니다."]
    if _find_engine() is None:
        return ["SuperTuxKart가 설치되어 있지 않습니다.", INSTALL_HINT]
    return check_virtual_input_ready(INSTALL_HINT)


# ══════════════════════════════════════════════════════════
#  메뉴에서 호출하는 진입점
# ══════════════════════════════════════════════════════════
def run_game(hand_controller=None):
    import pygame

    problem = _check_ready()
    if problem:
        show_error(pygame.display.get_surface(), TITLE, problem)
        return

    engine = _find_engine()
    command = [
        engine,
        "--no-start-screen",      # 메뉴 없이 바로 경주 시작
        "--use-keyboard=0",
        f"--track={TRACK}",
        f"--kart={KART}",
        f"--numkarts={NUM_KARTS}",
        f"--laps={LAPS}",
        f"--difficulty={DIFFICULTY}",
        *DISPLAY_ARGS,
    ]
    # 윈도우판은 실행 파일 폴더에서 실행해야 ../../data 를 찾는다
    cwd = os.path.dirname(engine) if IS_WINDOWS else None
    run_external_game(TITLE, TITLE_COLOR, command, cwd, KartHandMapper,
                      hand_controller, GUIDE_LINES)
