"""외부 게임(DOOM, SuperTuxKart 등)을 손동작으로 조작하기 위한 공통 모듈.

  - 가상 키보드/마우스 출력
      * 리눅스(라즈베리파이): uinput (evdev 패키지)
      * 윈도우: SendInput (ctypes, 추가 설치 없음)
  - HandMapper: 손 상태 -> 눌러야 할 키 목록 (게임마다 상속해서 규칙만 정의)
  - run_external_game: 게임 실행, 손 입력 전달, V 1초 종료, 정리까지 처리

주의: 설치 스크립트(install_*.py)도 이 파일의 windows_game_home()을 쓴다.
설치 스크립트는 pygame이 없는 파이썬으로 실행될 수 있으므로
pygame 은 함수 안에서만 import 한다.
"""

import os
import subprocess
import sys
import time

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

START_GRACE_SEC = 2.0   # 메뉴에서 고른 손동작이 바로 게임에 들어가지 않도록 대기
LOOP_FPS = 60


def windows_game_home(name):
    """윈도우에서 외부 게임을 설치할 영문 경로.

    프로젝트 경로에 한글이 있어 외부 게임 엔진이 파일을 못 여는 경우가 있으므로
    %LOCALAPPDATA%\\EveryOne\\<name> 을 쓰고, 그 경로에도 한글(사용자 이름)이
    있으면 C:\\EveryOne\\<name> 을 쓴다.
    """
    override = os.environ.get("EVERYONE_GAMES_HOME")
    if override:
        return os.path.join(override, name)
    base = os.environ.get("LOCALAPPDATA", "")
    candidate = os.path.join(base, "EveryOne", name) if base else ""
    if candidate and candidate.isascii():
        return candidate
    return os.path.join("C:\\", "EveryOne", name)


# ══════════════════════════════════════════════════════════
#  키 정의: 이름 -> (리눅스 evdev 키 이름, 윈도우 스캔코드, 확장 키 여부)
#  SDL 게임은 스캔코드를 읽으므로 윈도우에서는 스캔코드로 보낸다.
# ══════════════════════════════════════════════════════════
KEYS = {
    "up":        ("KEY_UP", 0x48, True),
    "down":      ("KEY_DOWN", 0x50, True),
    "left":      ("KEY_LEFT", 0x4B, True),
    "right":     ("KEY_RIGHT", 0x4D, True),
    "ctrl":      ("KEY_LEFTCTRL", 0x1D, False),
    "shift":     ("KEY_LEFTSHIFT", 0x2A, False),
    "space":     ("KEY_SPACE", 0x39, False),
    "enter":     ("KEY_ENTER", 0x1C, False),
    "esc":       ("KEY_ESC", 0x01, False),
    "backspace": ("KEY_BACKSPACE", 0x0E, False),
    "n":         ("KEY_N", 0x31, False),
    "v":         ("KEY_V", 0x2F, False),
    "b":         ("KEY_B", 0x30, False),
}


class LinuxVirtualInput:
    """리눅스 uinput 으로 가상 키보드/마우스를 만든다."""

    def __init__(self, key_names, use_mouse):
        from evdev import UInput, ecodes as e

        self.e = e
        self.codes = {name: getattr(e, KEYS[name][0]) for name in key_names}
        self.keyboard = UInput({e.EV_KEY: list(self.codes.values())},
                               name="everyone-hand-keyboard")
        self.mouse = None
        if use_mouse:
            # 마우스로 인식되려면 버튼도 있어야 한다
            self.mouse = UInput({e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT],
                                 e.EV_REL: [e.REL_X, e.REL_Y]},
                                name="everyone-hand-mouse")

    def set_key(self, name, down):
        self.keyboard.write(self.e.EV_KEY, self.codes[name], 1 if down else 0)

    def flush_keys(self):
        self.keyboard.syn()

    def move_mouse(self, dx):
        if self.mouse is not None:
            self.mouse.write(self.e.EV_REL, self.e.REL_X, dx)
            self.mouse.syn()

    def close(self):
        self.keyboard.close()
        if self.mouse is not None:
            self.mouse.close()


class WindowsVirtualInput:
    """윈도우 SendInput 으로 키보드/마우스 입력을 만든다."""

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MOUSEEVENTF_MOVE = 0x0001

    def __init__(self, key_names=None, use_mouse=True):
        import ctypes
        from ctypes import wintypes

        ULONG_PTR = wintypes.WPARAM

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ULONG_PTR)]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                        ("wParamH", wintypes.WORD)]

        class _INPUTUNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

        self.ctypes = ctypes
        self.INPUT = INPUT
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self.user32.SendInput.restype = wintypes.UINT
        self._pending = []

    def _send(self, inputs):
        if not inputs:
            return
        array = (self.INPUT * len(inputs))(*inputs)
        self.user32.SendInput(len(inputs), array, self.ctypes.sizeof(self.INPUT))

    def set_key(self, name, down):
        _, scan, extended = KEYS[name]
        flags = self.KEYEVENTF_SCANCODE
        if extended:
            flags |= self.KEYEVENTF_EXTENDEDKEY
        if not down:
            flags |= self.KEYEVENTF_KEYUP
        item = self.INPUT(type=self.INPUT_KEYBOARD)
        item.ki.wScan = scan
        item.ki.dwFlags = flags
        self._pending.append(item)

    def flush_keys(self):
        self._send(self._pending)
        self._pending = []

    def move_mouse(self, dx):
        item = self.INPUT(type=self.INPUT_MOUSE)
        item.mi.dx = dx
        item.mi.dwFlags = self.MOUSEEVENTF_MOVE
        self._send([item])

    def close(self):
        self._pending = []


def create_virtual_input(key_names, use_mouse):
    if IS_WINDOWS:
        return WindowsVirtualInput(key_names, use_mouse)
    return LinuxVirtualInput(key_names, use_mouse)


def check_virtual_input_ready(install_hint):
    """가상 입력을 쓸 수 없으면 오류 메시지 줄 목록, 쓸 수 있으면 None."""
    if IS_WINDOWS:
        return None
    if not IS_LINUX:
        return ["Windows와 라즈베리파이에서만 실행됩니다."]
    try:
        import evdev  # noqa: F401
    except ImportError:
        return ["evdev 패키지가 없습니다.", install_hint]
    if not os.access("/dev/uinput", os.R_OK | os.W_OK):
        return ["가상 입력 장치(/dev/uinput) 권한이 없습니다.",
                "설치 스크립트 실행 후 재부팅했는지 확인해 주세요."]
    return None


# ══════════════════════════════════════════════════════════
#  손 상태 -> 키 (게임별로 상속)
# ══════════════════════════════════════════════════════════
class HandMapper:
    """게임별 조작 규칙의 부모 클래스.

    자식 클래스는 KEYS(사용할 키 이름), USES_MOUSE 를 정하고
    compute() 에서 '지금 눌려 있어야 할 키 이름 집합'을 돌려주면 된다.
    키를 누르고 떼는 처리는 여기서 알아서 한다.
    """

    KEYS = ()
    USES_MOUSE = False

    def __init__(self, output=None):
        self.out = output if output is not None else create_virtual_input(
            self.KEYS, self.USES_MOUSE)
        self.pressed = set()

    def compute(self, hand_x, hand_y, gesture, dt):
        raise NotImplementedError

    def reset(self):
        """손이 사라지거나 종료 동작 중일 때 호출된다 (필요하면 재정의)."""

    def update(self, detected, hand_x, hand_y, gesture, dt):
        # 손이 안 보이거나 종료 동작(V) 중에는 모든 키를 뗀다
        if not detected or gesture == "Victory":
            self.reset()
            wanted = set()
        else:
            wanted = set(self.compute(hand_x, hand_y, gesture, dt))
        self._set_keys(wanted)

    def _set_keys(self, wanted):
        changed = False
        for name in self.pressed - wanted:
            self.out.set_key(name, False)
            changed = True
        for name in wanted - self.pressed:
            self.out.set_key(name, True)
            changed = True
        if changed:
            self.out.flush_keys()
        self.pressed = set(wanted)

    def close(self):
        try:
            self._set_keys(set())  # 눌린 키가 남지 않도록 모두 뗀다
        finally:
            self.out.close()


def axis_strength(offset, deadzone, full_at):
    """가운데서 떨어진 정도(offset)를 0~1 세기로 바꾼다 (데드존 적용)."""
    value = (abs(offset) - deadzone) / (full_at - deadzone)
    return max(0.0, min(1.0, value))


# ══════════════════════════════════════════════════════════
#  Every One 창 안내 화면
# ══════════════════════════════════════════════════════════
BG = (12, 12, 18)
WHITE = (240, 240, 240)
GRAY = (150, 150, 160)
RED = (255, 90, 80)
GREEN = (90, 230, 120)


def draw_info(screen, title, title_color, lines, colors):
    import pygame
    from font_utils import get_font

    screen.fill(BG)
    w, _ = screen.get_size()
    title_surf = get_font(52).render(title, True, title_color)
    screen.blit(title_surf, title_surf.get_rect(center=(w // 2, 110)))
    font = get_font(26)
    y = 200
    for line, color in zip(lines, colors):
        surf = font.render(line, True, color)
        screen.blit(surf, surf.get_rect(center=(w // 2, y)))
        y += 42
    pygame.display.flip()


def show_error(screen, title, lines, seconds=6):
    import pygame

    draw_info(screen, title, RED, lines + ["", "아무 키나 누르면 메뉴로 돌아갑니다."],
              [RED] + [WHITE] * len(lines))
    end = time.time() + seconds
    while time.time() < end:
        for event in pygame.event.get():
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.QUIT):
                return
        time.sleep(0.05)


# ══════════════════════════════════════════════════════════
#  외부 게임 실행 루프
# ══════════════════════════════════════════════════════════
def run_external_game(title, title_color, command, cwd, mapper_class,
                      hand_controller, guide_lines, env=None):
    """외부 게임을 실행하고 끝날 때까지 손 입력을 전달한다.

    V 손동작 1초 유지 또는 게임 자체 종료 시 돌아온다.
    """
    import pygame
    from hand_exit import VictoryExit

    screen = pygame.display.get_surface()
    draw_info(screen, title, title_color, [f"{title} 실행 중..."] + [""] + guide_lines,
              [GREEN, WHITE] + [GRAY] * len(guide_lines))

    mapper = None
    proc = None
    try:
        if hand_controller is not None:
            try:
                mapper = mapper_class()
            except Exception as error:
                print(f"[{title}] 가상 입력 장치를 만들지 못했습니다: {error}")
                show_error(screen, title, ["가상 입력 장치를 만들지 못했습니다.",
                                           str(error)[:60]])
                return

        try:
            proc = subprocess.Popen(command, cwd=cwd, env=env)
        except OSError as error:
            show_error(screen, title, ["게임을 실행하지 못했습니다.", str(error)[:60]])
            return
        print(f"[{title}] 실행: {' '.join(command)}")

        victory_exit = VictoryExit(hold_time_ms=1000)
        clock = pygame.time.Clock()
        started = time.monotonic()
        last_draw = 0.0

        while proc.poll() is None:
            dt = clock.tick(LOOP_FPS) / 1000.0

            # Every One 창이 '응답 없음'이 되지 않도록 이벤트를 비워 준다
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

            if mapper is not None:
                detected, hand_x, hand_y, gesture = hand_controller.get_state()
                if time.monotonic() - started < START_GRACE_SEC:
                    detected = False
                mapper.update(detected, hand_x, hand_y, gesture, dt)
                if victory_exit.update(detected, gesture, pygame.time.get_ticks()):
                    print(f"[{title}] V 손동작으로 종료")
                    return

            # 게임 창 뒤에 가려져 있으므로 가끔만 다시 그린다
            now = time.monotonic()
            if now - last_draw > 1.0:
                last_draw = now
                draw_info(screen, title, title_color,
                          [f"{title} 실행 중"] + [""] + guide_lines,
                          [GREEN, WHITE] + [GRAY] * len(guide_lines))

        print(f"[{title}] 게임이 종료되었습니다 (코드 {proc.returncode})")
    finally:
        if mapper is not None:
            mapper.close()
        if proc is not None and proc.poll() is None:
            # 외부 게임은 일반 종료 신호에 "정말 종료?" 창을 띄우기도 하므로 바로 끈다
            proc.kill()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        # 돌아온 직후 쌓인 입력이 메뉴를 조작하지 않도록 비운다
        pygame.event.clear()
