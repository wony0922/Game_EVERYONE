"""MarioPygame 을 Every One 창 안에서 손동작으로 플레이한다.  (Raspberry Pi OS / Windows)

원본: https://github.com/Winter091/MarioPygame (코드 MIT 라이선스)
설치: 프로젝트 루트에서  python3 install_mario.py  (윈도우: py -3.14 install_mario.py)
      -> Every One/mario_pygame/ 에 원본 게임 파일이 설치된다.

원본 코드는 고치지 않고 이 파일에서 감싸서 실행한다.
  - 원본이 새 창을 만들지 않도록 800x448 그림판(Surface)에 그리게 하고,
    그걸 Every One 창 크기에 맞게 확대해서 보여 준다.
  - 원본의 키보드 입력 대신 손동작(+키보드)으로 마리오를 움직인다.
  - 원본에는 리눅스에서 깨지는 이미지 경로가 있어(폴더 대소문자, 역슬래시) 자동 보정한다.

손동작 조작
  손 좌우            -> 걷기 (끝까지 치우치면 달리기)
  주먹               -> 점프 (오래 쥐면 더 높이)
  가리키기           -> 달리기 / 파이어볼
  V 1초 유지         -> 메뉴로 돌아가기
키보드: 방향키 이동, ↑ 점프, 왼쪽 Shift 달리기, ESC 종료
"""

import os
import sys

import pygame

from external_game import axis_strength, show_error
from hand_exit import VictoryExit

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
MARIO_DIR = os.path.join(GAME_DIR, "mario_pygame")

if sys.platform == "win32":
    INSTALL_HINT = "프로젝트 폴더에서  py -3.14 install_mario.py  를 실행해 주세요."
else:
    INSTALL_HINT = "프로젝트 폴더에서  python3 install_mario.py  를 실행해 주세요."

# 손 위치 판정 (화면 좌표 0~1, 가운데 0.5)
WALK_DEADZONE = 0.08
WALK_FULL_AT = 0.30
RUN_AT_STRENGTH = 0.8     # 이 이상 치우치면 자동으로 달리기

HINT_COLOR = (255, 255, 255)


# ══════════════════════════════════════════════════════════
#  손 상태 -> 마리오 키
# ══════════════════════════════════════════════════════════
def hand_to_keys(detected, hand_x, gesture):
    """(오른쪽, 왼쪽, 점프, 달리기) 를 돌려준다."""
    if not detected or gesture == "Victory":
        return False, False, False, False
    dx = hand_x - 0.5
    strength = axis_strength(dx, WALK_DEADZONE, WALK_FULL_AT)
    right = strength > 0 and dx > 0
    left = strength > 0 and dx < 0
    jump = gesture == "Fist"
    run = gesture == "Point" or strength >= RUN_AT_STRENGTH
    return right, left, jump, run


# ══════════════════════════════════════════════════════════
#  원본 코드 감싸기
# ══════════════════════════════════════════════════════════
def _resolve_path(path):
    """역슬래시와 폴더/파일 이름 대소문자 차이를 실제 파일에 맞게 고친다."""
    if not isinstance(path, str):
        return path
    fixed = path.replace("\\", "/")
    if os.path.exists(fixed):
        return fixed
    current = "/" if fixed.startswith("/") else "."
    for part in [p for p in fixed.split("/") if p]:
        candidate = os.path.join(current, part)
        if not os.path.exists(candidate):
            try:
                matches = [n for n in os.listdir(current) if n.lower() == part.lower()]
            except OSError:
                return fixed
            if not matches:
                return fixed
            candidate = os.path.join(current, matches[0])
        current = candidate
    return current


class _Patches:
    """원본 실행 중에만 pygame 함수 몇 개를 바꿔 끼우고, 끝나면 되돌린다."""

    def __init__(self, offscreen):
        self.offscreen = offscreen
        self.saved = {}

    def __enter__(self):
        self.saved = {
            "image.load": pygame.image.load,
            "display.set_mode": pygame.display.set_mode,
            "display.update": pygame.display.update,
            "display.set_caption": pygame.display.set_caption,
            "caption": pygame.display.get_caption(),
        }
        original_load = self.saved["image.load"]

        def load(file, *args, **kwargs):
            return original_load(_resolve_path(file), *args, **kwargs)

        pygame.image.load = load
        pygame.display.set_mode = lambda *a, **k: self.offscreen   # 새 창 대신 그림판
        pygame.display.update = lambda *a, **k: None                # 화면 출력은 여기서 직접
        pygame.display.set_caption = lambda *a, **k: None
        return self

    def __exit__(self, *exc):
        pygame.image.load = self.saved["image.load"]
        pygame.display.set_mode = self.saved["display.set_mode"]
        pygame.display.update = self.saved["display.update"]
        pygame.display.set_caption = self.saved["display.set_caption"]
        caption = self.saved["caption"]
        if caption and caption[0]:
            pygame.display.set_caption(caption[0])
        return False


def _check_ready():
    if not os.path.isfile(os.path.join(MARIO_DIR, "Core.py")):
        return ["마리오 게임 파일이 설치되어 있지 않습니다.", INSTALL_HINT]
    try:
        import pytmx  # noqa: F401
    except ImportError:
        return ["pytmx 패키지가 없습니다.", INSTALL_HINT]
    return None


def _fit_rect(src_size, dst_size):
    sw, sh = src_size
    dw, dh = dst_size
    scale = min(dw / sw, dh / sh)
    w, h = int(sw * scale), int(sh * scale)
    return pygame.Rect((dw - w) // 2, (dh - h) // 2, w, h)


# ══════════════════════════════════════════════════════════
#  메뉴에서 호출하는 진입점
# ══════════════════════════════════════════════════════════
def run_game(hand_controller=None):
    screen = pygame.display.get_surface()
    problem = _check_ready()
    if problem:
        show_error(screen, "MARIO", problem)
        return

    old_cwd = os.getcwd()
    sys.path.insert(0, MARIO_DIR)
    os.chdir(MARIO_DIR)   # 원본은 'images/...' 같은 상대 경로로 파일을 읽는다
    try:
        from Const import FPS, WINDOW_H, WINDOW_W
        offscreen = pygame.Surface((WINDOW_W, WINDOW_H)).convert()
        with _Patches(offscreen):
            try:
                from Core import Core
                core = Core()
            except Exception as error:
                print(f"[MARIO] 시작 실패: {error}")
                show_error(screen, "MARIO", ["게임을 시작하지 못했습니다.", str(error)[:60]])
                return
            core.screen = offscreen
            _play(core, screen, offscreen, FPS, hand_controller)
    finally:
        pygame.mixer.stop()
        os.chdir(old_cwd)
        if MARIO_DIR in sys.path:
            sys.path.remove(MARIO_DIR)
        pygame.event.clear()


def _play(core, screen, offscreen, fps, hand_controller):
    from font_utils import get_font

    clock = pygame.time.Clock()
    victory_exit = VictoryExit(hold_time_ms=1000)
    target = _fit_rect(offscreen.get_size(), screen.get_size())
    hint = get_font(18).render("V 1초 유지 / ESC : 메뉴로", True, HINT_COLOR)
    started = pygame.time.get_ticks()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return

        # 시작 화면/게임오버 뒤에는 자동으로 다시 시작 (손으로 엔터를 누를 수 없으므로)
        if core.get_mm().currentGameState == "MainMenu":
            core.get_mm().start_loading()

        # ── 입력: 키보드 + 손동작 ──
        keys = pygame.key.get_pressed()
        kb_right, kb_left = keys[pygame.K_RIGHT], keys[pygame.K_LEFT]
        kb_jump, kb_run = keys[pygame.K_UP], keys[pygame.K_LSHIFT]
        kb_down = keys[pygame.K_DOWN]

        h_right = h_left = h_jump = h_run = False
        if hand_controller is not None:
            detected, hand_x, _hand_y, gesture = hand_controller.get_state()
            if pygame.time.get_ticks() - started < 2000:
                detected = False   # 메뉴에서 고른 손동작이 바로 들어가지 않도록
            h_right, h_left, h_jump, h_run = hand_to_keys(detected, hand_x, gesture)
            if victory_exit.update(detected, gesture, pygame.time.get_ticks()):
                return

        core.keyR = bool(kb_right or h_right)
        core.keyL = bool(kb_left or h_left)
        core.keyU = bool(kb_jump or h_jump)
        core.keyD = bool(kb_down)
        core.keyShift = bool(kb_run or h_run)

        # ── 원본 게임 한 프레임 ──
        core.update()
        core.render()

        # ── Every One 창에 확대해서 출력 ──
        screen.fill((0, 0, 0))
        pygame.transform.scale(offscreen, target.size, screen.subsurface(target))
        screen.blit(hint, (target.right - hint.get_width() - 8, target.bottom - hint.get_height() - 6))
        pygame.display.flip()
        clock.tick(fps)
