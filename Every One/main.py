import os
import sys
import time
import pygame

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from pong import run_game
from doom_wave import run_game as run_doom_wave
from Stroop_Game import run_game as run_stroop_game
from game_369 import run_game as run_369_game

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
    menu_font = pygame.font.Font(None, 50)
    info_font = pygame.font.Font(None, 30)
    small_font = pygame.font.Font(None, 24)

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
        ("PONG", run_game),
        ("DOOM WAVE", run_doom_wave),
        ("STROOP COLOR", run_stroop_game),
        ("369 GAME", run_369_game),
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
    last_gesture_nav_time = 0
    GESTURE_NAV_COOLDOWN = 1

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    selected_game -= 1
                    if selected_game < 0:
                        selected_game = len(games) - 1

                elif event.key == pygame.K_RIGHT:
                    selected_game += 1
                    if selected_game >= len(games):
                        selected_game = 0

                elif event.key == pygame.K_RETURN:
                    launch_selected_game()

        screen.fill(BACKGROUND_COLOR)

        title = title_font.render("Every One", True, WHITE)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 100))

        game_name = games[selected_game][0]
        game_text = menu_font.render("<  " + game_name + "  >", True, BLUE)
        screen.blit(game_text, (WIDTH // 2 - game_text.get_width() // 2, 280))

        if hand_controller is not None:
            ctrl_label = "HAND POINT : SELECT    FIST : START    (KB OK)"
        else:
            ctrl_label = "LEFT / RIGHT : SELECT    ENTER : START"

        info = info_font.render(ctrl_label, True, GRAY)
        screen.blit(info, (WIDTH // 2 - info.get_width() // 2, 400))

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

                elif gesture == "Fist":
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
