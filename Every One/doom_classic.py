"""DOOM (chocolate-doom + Freedoom) 을 손동작으로 조작한다.  (Raspberry Pi OS / Windows)

chocolate-doom 을 별도 프로세스(전체화면)로 실행하고, 손 상태를 가상 키보드/마우스
입력으로 바꿔 보낸다. 실행/종료/가상 입력 처리는 external_game.py 공통 모듈이 한다.

손동작 조작
  손 좌우       -> 회전 (가운데서 멀수록 빠르게)
  손 위 / 아래  -> 전진 / 후진 (많이 올리면 달리기)
  주먹          -> 발사
  가리키기      -> 문 열기 / 스위치 / 죽은 뒤 다시 시작
  V 1초 유지    -> 종료

설치: 프로젝트 루트에서
  라즈베리파이: python3 install_doom.py
  윈도우:       py -3.14 install_doom.py
"""

import os
import shutil

from external_game import (
    IS_LINUX, IS_WINDOWS, RED, HandMapper, axis_strength,
    check_virtual_input_ready, run_external_game, show_error, windows_game_home,
)

# ══════════════════════════════════════════════════════════
#  설정
# ══════════════════════════════════════════════════════════
SKILL = "3"  # 1(아주 쉬움) ~ 5(악몽)

# 회전 방식: True = 가상 마우스(손을 많이 치우칠수록 빠르게 회전, 부드러움)
#            False = 방향키 (마우스 회전이 안 먹히는 환경일 때 사용)
TURN_WITH_MOUSE = True

# 손 위치 판정 (화면 좌표 0~1, 가운데 0.5)
TURN_DEADZONE = 0.07      # 이 범위 안에서는 회전하지 않음
TURN_FULL_AT = 0.32       # 가운데서 이만큼 떨어지면 최대 속도
MOVE_DEADZONE = 0.08      # 위아래 데드존
RUN_THRESHOLD = 0.22      # 이보다 많이 올리면 달리기

# 최대 회전 속도: 가상 마우스 이동량(초당). 5600 이면 둠의 '빠른 회전'과 비슷.
MAX_TURN_COUNTS_PER_SEC = 5600

GAME_DIR = os.path.dirname(os.path.abspath(__file__))

if IS_WINDOWS:
    DOOM_HOME = windows_game_home("doom")
    DATA_DIR = os.path.join(DOOM_HOME, "config")
    WAD_CANDIDATES = [
        (os.path.join(DOOM_HOME, "freedoom1.wad"), ["1", "1"]),
        (os.path.join(DOOM_HOME, "freedoom2.wad"), ["1"]),
    ]
    INSTALL_HINT = "프로젝트 폴더에서  py -3.14 install_doom.py  를 실행해 주세요."
else:
    DOOM_HOME = None
    DATA_DIR = os.path.join(GAME_DIR, "doom_data")
    WAD_CANDIDATES = [
        # (WAD 경로, 바로 시작할 맵을 지정하는 -warp 인자)
        ("/usr/share/games/doom/freedoom1.wad", ["1", "1"]),  # 에피소드형 (E1M1)
        ("/usr/share/games/doom/freedoom2.wad", ["1"]),       # MAP01
    ]
    INSTALL_HINT = "프로젝트 폴더에서  python3 install_doom.py  를 실행해 주세요."

# 둠 설정 파일 (실행할 때마다 덮어써서 항상 같은 상태로 시작)
DEFAULT_CFG = """use_mouse 1
mouse_sensitivity 5
"""
CHOCOLATE_CFG = """fullscreen 1
show_endoom 0
grabmouse 1
novert 1
mouse_acceleration 1.000000
mouse_threshold 0
"""

GUIDE_LINES = [
    "손 좌우 : 회전        손 위/아래 : 전진/후진",
    "주먹 : 발사        가리키기 : 문 열기 / 다시 시작",
    "V 손동작 1초 유지 : 메뉴로 돌아가기",
]


# ══════════════════════════════════════════════════════════
#  손 상태 -> 둠 조작
#  둠 기본 키: 방향키 이동/회전, Ctrl 발사, Space 사용, Shift 달리기
# ══════════════════════════════════════════════════════════
class DoomHandMapper(HandMapper):
    KEYS = ("up", "down", "left", "right", "ctrl", "space", "shift")
    USES_MOUSE = TURN_WITH_MOUSE

    def __init__(self, output=None):
        super().__init__(output)
        self.turn_remainder = 0.0

    def reset(self):
        self.turn_remainder = 0.0

    def compute(self, hand_x, hand_y, gesture, dt):
        wanted = set()

        # ── 회전 (손 좌우) ──
        dx = hand_x - 0.5
        strength = axis_strength(dx, TURN_DEADZONE, TURN_FULL_AT)
        if strength > 0:
            direction = 1 if dx > 0 else -1
            if TURN_WITH_MOUSE:
                # 살짝 치우치면 정밀하게, 많이 치우치면 빠르게 (곡선)
                amount = direction * (strength ** 1.5) * MAX_TURN_COUNTS_PER_SEC * dt
                amount += self.turn_remainder
                whole = int(amount)
                self.turn_remainder = amount - whole
                if whole:
                    self.out.move_mouse(whole)
            else:
                wanted.add("right" if direction > 0 else "left")
        else:
            self.turn_remainder = 0.0

        # ── 전진/후진 (손 위아래: 위 = 전진) ──
        dy = 0.5 - hand_y
        if dy > MOVE_DEADZONE:
            wanted.add("up")
            if dy > RUN_THRESHOLD:
                wanted.add("shift")
        elif dy < -MOVE_DEADZONE:
            wanted.add("down")

        # ── 제스처 ──
        if gesture == "Fist":
            wanted.add("ctrl")     # 발사
        elif gesture == "Point":
            wanted.add("space")    # 사용(문 열기)
        return wanted


# ══════════════════════════════════════════════════════════
#  준비 확인
# ══════════════════════════════════════════════════════════
def _find_engine():
    if IS_WINDOWS:
        path = os.path.join(DOOM_HOME, "chocolate-doom.exe")
        return path if os.path.isfile(path) else None
    path = shutil.which("chocolate-doom")
    if path:
        return path
    if os.path.exists("/usr/games/chocolate-doom"):
        return "/usr/games/chocolate-doom"
    return None


def _find_wad():
    for wad, warp in WAD_CANDIDATES:
        if os.path.isfile(wad):
            return wad, warp
    return None, None


def _check_ready():
    if not (IS_WINDOWS or IS_LINUX):
        return ["DOOM은 Windows와 라즈베리파이에서만 실행됩니다."]
    if _find_engine() is None:
        return ["chocolate-doom이 설치되어 있지 않습니다.", INSTALL_HINT]
    if _find_wad()[0] is None:
        return ["Freedoom 게임 데이터가 없습니다.", INSTALL_HINT]
    return check_virtual_input_ready(INSTALL_HINT)


def _write_configs():
    os.makedirs(DATA_DIR, exist_ok=True)
    default_cfg = os.path.join(DATA_DIR, "default.cfg")
    extra_cfg = os.path.join(DATA_DIR, "chocolate-doom.cfg")
    with open(default_cfg, "w", encoding="utf-8") as f:
        f.write(DEFAULT_CFG)
    with open(extra_cfg, "w", encoding="utf-8") as f:
        f.write(CHOCOLATE_CFG)
    return default_cfg, extra_cfg


# ══════════════════════════════════════════════════════════
#  메뉴에서 호출하는 진입점
# ══════════════════════════════════════════════════════════
def run_game(hand_controller=None):
    import pygame

    problem = _check_ready()
    if problem:
        show_error(pygame.display.get_surface(), "DOOM", problem)
        return

    wad, warp = _find_wad()
    default_cfg, extra_cfg = _write_configs()
    command = [
        _find_engine(),
        "-iwad", wad,
        "-config", default_cfg,
        "-extraconfig", extra_cfg,
        "-skill", SKILL,
        "-warp", *warp,
    ]
    run_external_game("DOOM", RED, command, DATA_DIR, DoomHandMapper,
                      hand_controller, GUIDE_LINES)
