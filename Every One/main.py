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
CAMERA_PANEL_WIDTH = 240
WINDOW_WIDTH = WIDTH + CAMERA_PANEL_WIDTH
CAMERA_PREVIEW_SIZE = (160, 120)
CAMERA_PREVIEW_X = WIDTH + (CAMERA_PANEL_WIDTH - CAMERA_PREVIEW_SIZE[0]) // 2
CAMERA_PREVIEW_Y = 230
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
    screen = pygame.display.set_mode((WINDOW_WIDTH, HEIGHT))
    pygame.display.set_caption("Every One")

    clock = pygame.time.Clock()

    # 폰트
    title_font = pygame.font.Font(None, 70)
    info_font = pygame.font.Font(None, 30)
    small_font = pygame.font.Font(None, 24)
    card_title_font = pygame.font.Font(None, 38)
    card_info_font = pygame.font.Font(None, 23)

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
        ("PONG", "손으로 패들을 움직여\n공을 받아내세요.", run_game),
        ("DOOM WAVE", "시점을 돌리고 주먹을 쥐어\n적을 처치하세요.", run_doom_wave),
        ("STROOP COLOR", "글자가 아닌 글자의 색을\n맞히는 게임입니다.", run_stroop_game),
    ]
    card_width = 220
    card_height = 210
    card_gap = 20
    card_start_x = (WIDTH - (card_width * len(games) + card_gap * (len(games) - 1))) // 2
    card_y = 220
    game_cards = [
        pygame.Rect(
            card_start_x + index * (card_width + card_gap),
            card_y,
            card_width,
            card_height,
        )
        for index in range(len(games))
    ]

    hand_input_block_until = 0
    HAND_GAME_RETURN_COOLDOWN_MS = 2500

    def launch_selected_game():
        nonlocal hand_input_block_until
        try:
            games[selected_game][2](hand_controller)
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
                    selected_game = (selected_game - 1) % len(games)

                # 오른쪽
                elif event.key == pygame.K_RIGHT:
                    selected_game = (selected_game + 1) % len(games)

                # Enter
                elif event.key == pygame.K_RETURN:

                    # 선택된 게임 실행
                    launch_selected_game()

            elif event.type == pygame.MOUSEMOTION:
                for index, card in enumerate(game_cards):
                    if card.collidepoint(event.pos):
                        selected_game = index
                        break

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for index, card in enumerate(game_cards):
                    if card.collidepoint(event.pos):
                        selected_game = index
                        launch_selected_game()
                        break

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

        # 게임 목록 카드
        for index, (game_name, description, _run_game) in enumerate(games):
            card = game_cards[index]
            selected = index == selected_game
            card_color = (42, 62, 86) if selected else (32, 36, 48)
            border_color = BLUE if selected else (75, 80, 95)
            pygame.draw.rect(screen, card_color, card, border_radius=12)
            pygame.draw.rect(screen, border_color, card, 3 if selected else 1, border_radius=12)

            title_color = BLUE if selected else WHITE
            game_text = card_title_font.render(game_name, True, title_color)
            screen.blit(
                game_text,
                (card.centerx - game_text.get_width() // 2, card.y + 36),
            )

            for line_index, line in enumerate(description.splitlines()):
                description_text = card_info_font.render(line, True, GRAY)
                screen.blit(
                    description_text,
                    (
                        card.centerx - description_text.get_width() // 2,
                        card.y + 92 + line_index * 30,
                    ),
                )

            if selected:
                select_text = small_font.render("ENTER / CLICK / FIST", True, GREEN)
                screen.blit(
                    select_text,
                    (
                        card.centerx - select_text.get_width() // 2,
                        card.bottom - 42,
                    ),
                )

        # 조작법
        if hand_controller is not None:
            ctrl_label = "POINT : SELECT    FIST : START    (ARROWS / CLICK OK)"
        else:
            ctrl_label = "LEFT / RIGHT : SELECT    ENTER / CLICK : START"

        info = info_font.render(
            ctrl_label,
            True,
            GRAY
        )

        screen.blit(
            info,
            (
                WIDTH // 2 - info.get_width() // 2,
                470
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
                    target_game = min(int(hand_x * len(games)), len(games) - 1)
                    if target_game != selected_game:
                        selected_game = target_game
                        last_gesture_nav_time = now

                # Fist(주먹) → 선택 (Enter 대체)
                elif gesture == "Fist":
                    last_gesture_nav_time = now
                    launch_selected_game()

            # 웹캠 미니 미리보기 (PIP)
            panel_title = small_font.render("WEBCAM", True, BLUE)
            screen.blit(
                panel_title,
                (
                    WIDTH + (CAMERA_PANEL_WIDTH - panel_title.get_width()) // 2,
                    CAMERA_PREVIEW_Y - 32,
                ),
            )
            preview = hand_controller.get_preview_surface()
            if preview is not None:
                pygame.draw.rect(
                    screen,
                    BLUE,
                    (
                        CAMERA_PREVIEW_X - 2,
                        CAMERA_PREVIEW_Y - 2,
                        CAMERA_PREVIEW_SIZE[0] + 4,
                        CAMERA_PREVIEW_SIZE[1] + 4,
                    ),
                    2,
                )
                preview = pygame.transform.smoothscale(
                    preview, CAMERA_PREVIEW_SIZE
                )
                screen.blit(preview, (CAMERA_PREVIEW_X, CAMERA_PREVIEW_Y))

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
            screen.blit(
                status_text,
                (
                    WIDTH + (CAMERA_PANEL_WIDTH - status_text.get_width()) // 2,
                    CAMERA_PREVIEW_Y + CAMERA_PREVIEW_SIZE[1] + 14,
                ),
            )

        pygame.draw.line(screen, WHITE, (WIDTH, 0), (WIDTH, HEIGHT), 2)

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
