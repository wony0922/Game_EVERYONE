import pygame
import os
import sys
import time

# 상위 경로 모듈 검색 추가
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from pong import run_game
from doom_wave import run_game as run_doom_wave
from Stroop_Game import run_game as run_stroop_game

try:
    from hand_controller import HandController
except ImportError:
    HandController = None

try:
    from hand_controller import HandController
except ImportError:
    HandController = None


# ==========================================
# 기본 설정
# ==========================================

WIDTH = 800
HEIGHT = 600
FPS = 60

BACKGROUND_COLOR = (20, 20, 30)
WHITE = (255, 255, 255)
BLUE = (80, 180, 255)
GREEN = (80, 255, 120)
RED = (255, 80, 80)
GRAY = (130, 130, 140)


# ==========================================
# 메인 메뉴
# ==========================================

def main():

    # Pygame 초기화
    pygame.init()

    # 게임 창 생성
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Every One")

    clock = pygame.time.Clock()

    # 폰트
    title_font = pygame.font.Font(None, 70)
    menu_font = pygame.font.Font(None, 50)
    info_font = pygame.font.Font(None, 30)
    small_font = pygame.font.Font(None, 24)

    # HandController 생성 (카메라 & 손 동작 인식)
    hand_controller = None
    if HandController is not None:
        try:
            hand_controller = HandController(cam_index=0)
            hand_controller.start()
            print("[메인 메뉴] HandController 시작됨")
        except Exception as e:
            print(f"[메인 메뉴] HandController 생성 실패: {e}")

    # 현재 선택된 게임
    selected_game = 0

    # 현재 게임 목록
    games = [
        ("PONG", run_game),
        ("DOOM WAVE", run_doom_wave),
        ("STROOP COLOR", run_stroop_game),
    ]

    hand_input_block_until = 0
    HAND_GAME_RETURN_COOLDOWN_MS = 2500

    def launch_selected_game():
        nonlocal hand_input_block_until
        try:
            games[selected_game][1](hand_controller)
        finally:
            hand_input_block_until = (
                pygame.time.get_ticks() + HAND_GAME_RETURN_COOLDOWN_MS
            )

    running = True

    # 손 동작 메뉴 조작 쿨다운 (연속 입력 방지)
    last_gesture_nav_time = 0
    GESTURE_NAV_COOLDOWN = 1  # 초

    # ======================================
    # 메인 메뉴 루프
    # ======================================

    while running:

        # ----------------------------------
        # 이벤트 처리
        # ----------------------------------

        for event in pygame.event.get():

            # 창 닫기
            if event.type == pygame.QUIT:

                running = False

            # 키보드 입력
            elif event.type == pygame.KEYDOWN:

                # 왼쪽
                if event.key == pygame.K_LEFT:

                    selected_game -= 1

                    if selected_game < 0:
                        selected_game = len(games) - 1

                # 오른쪽
                elif event.key == pygame.K_RIGHT:

                    selected_game += 1

                    if selected_game >= len(games):
                        selected_game = 0

                # Enter
                elif event.key == pygame.K_RETURN:

                    # 선택된 게임 실행
                    launch_selected_game()

        # ----------------------------------
        # 화면 그리기
        # ----------------------------------

        screen.fill(BACKGROUND_COLOR)

        # 제목
        title = title_font.render(
            "Every One",
            True,
            WHITE
        )

        screen.blit(
            title,
            (
                WIDTH // 2 - title.get_width() // 2,
                100
            )
        )

        # 선택된 게임 이름
        game_name = games[selected_game][0]

        game_text = menu_font.render(
            "<  " + game_name + "  >",
            True,
            BLUE
        )

        screen.blit(
            game_text,
            (
                WIDTH // 2 - game_text.get_width() // 2,
                280
            )
        )

        # 조작법
        if hand_controller is not None:
            ctrl_label = "HAND POINT : SELECT    FIST : START    (KB OK)"
        else:
            ctrl_label = "LEFT / RIGHT : SELECT    ENTER : START"

        info = info_font.render(
            ctrl_label,
            True,
            GRAY
        )

        screen.blit(
            info,
            (
                WIDTH // 2 - info.get_width() // 2,
                400
            )
        )

        # ----------------------------------
        # 손 동작 메뉴 조작
        # ----------------------------------

        if hand_controller is not None:
            is_detected, hand_x, hand_y, gesture = hand_controller.get_state()
            now = time.time()
            hand_input_blocked = (
                pygame.time.get_ticks() < hand_input_block_until
            )
            if hand_input_blocked:
                is_detected = False

            if (
                not hand_input_blocked
                and is_detected
                and now - last_gesture_nav_time > GESTURE_NAV_COOLDOWN
            ):

                # Point 제스처 + 손 위치로 좌/우 선택
                if gesture == "Point":
                    if hand_x < 0.35:
                        selected_game -= 1
                        if selected_game < 0:
                            selected_game = len(games) - 1
                        last_gesture_nav_time = now
                    elif hand_x > 0.65:
                        selected_game += 1
                        if selected_game >= len(games):
                            selected_game = 0
                        last_gesture_nav_time = now

                # Fist(주먹) → 선택 (Enter 대체)
                elif gesture == "Fist":
                    last_gesture_nav_time = now
                    launch_selected_game()

            # 웹캠 미니 미리보기 (PIP)
            preview = hand_controller.get_preview_surface()
            if preview is not None:
                pip_x = WIDTH - 170
                pip_y = HEIGHT - 130
                pygame.draw.rect(
                    screen,
                    BLUE,
                    (pip_x - 2, pip_y - 2, 164, 124),
                    2
                )
                screen.blit(preview, (pip_x, pip_y))

            # 손 인식 상태 표시
            if is_detected:
                status_text = small_font.render(
                    f"Hand: {gesture}",
                    True, GREEN
                )
            else:
                status_text = small_font.render(
                    "Hand: Not Detected",
                    True, RED
                )
            screen.blit(status_text, (10, HEIGHT - 30))

        # 화면 업데이트
        pygame.display.flip()

        clock.tick(FPS)

    # ======================================
    # 프로그램 종료
    # ======================================

    if hand_controller is not None:
        hand_controller.stop()

    pygame.quit()


# ==========================================
# 프로그램 시작
# ==========================================

if __name__ == "__main__":

    main()
