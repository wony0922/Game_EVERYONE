import os
import sys
import time
import pygame
from hand_input import scale_hand_x

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from pong import run_game
from doom_wave import run_game as run_doom_wave
from Stroop_Game import run_game as run_stroop_game
from game_1945 import run_game as run_1945_game
from game_369 import run_game as run_369_game
from game_one_card import run_game as run_one_card_game

try:
    from hand_controller import HandController
except ImportError:
    HandController = None

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


def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, HEIGHT))
    pygame.display.set_caption("Every One")
    clock = pygame.time.Clock()

    title_font = pygame.font.Font(None, 70)
    info_font = pygame.font.Font(None, 30)
    small_font = pygame.font.Font(None, 24)
    card_title_fonts = {
        "large": pygame.font.Font(None, 36),
        "small": pygame.font.Font(None, 25),
    }
    card_info_fonts = {
        "large": pygame.font.Font(None, 19),
        "small": pygame.font.Font(None, 15),
    }

    hand_controller = None
    if HandController is not None:
        try:
            hand_controller = HandController(cam_index=0)
            hand_controller.start()
            print("[메인 메뉴] HandController 시작됨")
        except Exception as e:
            print(f"[메인 메뉴] HandController 생성 실패: {e}")

    selected_game = 0

    games = [
        ("PONG", "손으로 패들을 움직여\n공을 받아내세요.", run_game),
        ("DOOM WAVE", "시점을 돌리고 주먹을 쥐어\n적을 처치하세요.", run_doom_wave),
        ("1945 AIR COMBAT", "비행기를 조종해 적을\n물리치세요.", run_1945_game),
        ("STROOP COLOR", "글자가 아닌 글자의 색을\n맞히는 게임입니다.", run_stroop_game),
        ("369 GAME", "숫자 대신 박수로\n369를 플레이하세요.", run_369_game),
        ("ONE CARD", "카드를 내고 먼저\n손패를 비우세요.", run_one_card_game),
    ]
    carousel_position = 0.0
    carousel_target = 0.0
    visible_cards = []

    hand_input_block_until = 0
    HAND_GAME_RETURN_COOLDOWN_MS = 2500

    def move_selection(direction):
        nonlocal selected_game, carousel_target
        selected_game = (selected_game + direction) % len(games)
        carousel_target += direction

    def select_game(index):
        nonlocal selected_game, carousel_target
        forward = (index - selected_game) % len(games)
        backward = forward - len(games)
        direction = forward if forward <= len(games) // 2 else backward
        selected_game = index
        carousel_target += direction

    def launch_selected_game():
        nonlocal hand_input_block_until
        try:
            games[selected_game][2](hand_controller)
        finally:
            hand_input_block_until = (
                pygame.time.get_ticks() + HAND_GAME_RETURN_COOLDOWN_MS
            )

    running = True
    last_gesture_nav_time = 0
    GESTURE_NAV_COOLDOWN = 1
    HAND_SCROLL_LEFT = 0.35
    HAND_SCROLL_RIGHT = 0.65

    while running:
        dt = clock.tick(FPS) / 1000.0
        carousel_position += (carousel_target - carousel_position) * (
            1 - pow(0.001, dt)
        )
        if abs(carousel_target - carousel_position) < 0.005:
            carousel_position = carousel_target

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    move_selection(-1)

                elif event.key == pygame.K_RIGHT:
                    move_selection(1)

                elif event.key == pygame.K_RETURN:
                    launch_selected_game()

            elif event.type == pygame.MOUSEMOTION:
                for index, card in visible_cards:
                    if card.collidepoint(event.pos):
                        select_game(index)
                        break

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for index, card in visible_cards:
                    if card.collidepoint(event.pos):
                        select_game(index)
                        launch_selected_game()
                        break

        # ----------------------------------
        # 화면 그리기
        # ----------------------------------

        screen.fill(BACKGROUND_COLOR)

        title = title_font.render("Every One", True, WHITE)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 100))

        screen.set_clip(pygame.Rect(0, 0, WIDTH, HEIGHT))
        carousel_slots = []
        for index in range(len(games)):
            offset = (index - carousel_position + len(games) / 2) % len(games) - len(games) / 2
            carousel_slots.append((abs(offset), offset, index))

        visible_slots = sorted(carousel_slots)[:3]
        visible_cards = []
        for _, offset, index in sorted(
            visible_slots, key=lambda slot: slot[0], reverse=True
        ):
            selected = index == selected_game
            scale = 1.0 - min(1.0, abs(offset)) * 0.32
            card_width = int(360 * scale)
            card_height = int(250 * scale)
            card = pygame.Rect(0, 0, card_width, card_height)
            card.center = (
                int(WIDTH // 2 + offset * 290),
                315,
            )
            visible_cards.append((index, card))

            card_color = (42, 62, 86) if selected else (32, 36, 48)
            border_color = BLUE if selected else (75, 80, 95)
            pygame.draw.rect(screen, card_color, card, border_radius=16)
            pygame.draw.rect(
                screen,
                border_color,
                card,
                4 if selected else 2,
                border_radius=16,
            )

            title_color = BLUE if selected else WHITE
            game_name, description, _run_game = games[index]
            font_size = "large" if scale > 0.84 else "small"
            card_title_font = card_title_fonts[font_size]
            card_info_font = card_info_fonts[font_size]
            game_text = card_title_font.render(game_name, True, title_color)
            screen.blit(
                game_text,
                (card.centerx - game_text.get_width() // 2, card.y + int(card_height * 0.2)),
            )

            for line_index, line in enumerate(description.splitlines()):
                description_text = card_info_font.render(line, True, GRAY)
                screen.blit(
                    description_text,
                    (
                        card.centerx - description_text.get_width() // 2,
                        card.y + int(card_height * 0.48) + line_index * 22,
                    ),
                )

            if selected:
                select_text = small_font.render("ENTER / CLICK / FIST", True, GREEN)
                screen.blit(
                    select_text,
                    (
                        card.centerx - select_text.get_width() // 2,
                        card.bottom - 38,
                    ),
                )

        visible_cards.reverse()
        screen.set_clip(None)

        # 조작법
        if hand_controller is not None:
            ctrl_label = "POINT: HOLD LEFT/RIGHT (1s/STEP)  |  FIST: START"
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
                500
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

            if not hand_input_blocked and is_detected:
                if gesture == "Point":
                    scaled_hand_x = scale_hand_x(hand_x)
                    direction = (
                        -1 if scaled_hand_x < HAND_SCROLL_LEFT
                        else 1 if scaled_hand_x > HAND_SCROLL_RIGHT
                        else 0
                    )
                    if (
                        direction
                        and now - last_gesture_nav_time >= GESTURE_NAV_COOLDOWN
                    ):
                        move_selection(direction)
                        last_gesture_nav_time = now

                elif (
                    gesture == "Fist"
                    and now - last_gesture_nav_time > GESTURE_NAV_COOLDOWN
                ):
                    last_gesture_nav_time = now
                    launch_selected_game()

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

            if is_detected:
                status_text = small_font.render(f"Hand: {gesture}", True, GREEN)
            else:
                status_text = small_font.render("Hand: Not Detected", True, RED)
            screen.blit(
                status_text,
                (
                    WIDTH + (CAMERA_PANEL_WIDTH - status_text.get_width()) // 2,
                    CAMERA_PREVIEW_Y + CAMERA_PREVIEW_SIZE[1] + 14,
                ),
            )

        pygame.draw.line(screen, WHITE, (WIDTH, 0), (WIDTH, HEIGHT), 2)
        pygame.display.flip()
        clock.tick(FPS)

    if hand_controller is not None:
        hand_controller.stop()

    pygame.quit()


if __name__ == "__main__":
    main()
