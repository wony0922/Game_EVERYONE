import pygame
from hand_exit import VictoryExit


TRANSITION_COOLDOWN_MS = 3000


def show_tutorial(
    screen, title, sections, hand_controller=None, require_fist=False
):
    width, height = screen.get_size()
    clock = pygame.time.Clock()

    try:
        title_font = pygame.font.SysFont("malgungothic", 40, bold=True)
        heading_font = pygame.font.SysFont("malgungothic", 25, bold=True)
        body_font = pygame.font.SysFont("malgungothic", 21)
        prompt_font = pygame.font.SysFont("malgungothic", 20, bold=True)
    except pygame.error:
        title_font = pygame.font.Font(None, 42)
        heading_font = pygame.font.Font(None, 28)
        body_font = pygame.font.Font(None, 24)
        prompt_font = pygame.font.Font(None, 22)

    board = pygame.Rect(32, 28, width - 64, height - 56)
    running = True
    entry_ready_at = pygame.time.get_ticks() + TRANSITION_COOLDOWN_MS
    fist_armed = hand_controller is None
    transition_until = None
    victory_exit = VictoryExit()
    while running:
        clock.tick(30)
        now = pygame.time.get_ticks()
        is_detected = False
        gesture = "None"
        if hand_controller is not None:
            is_detected, _hand_x, _hand_y, gesture = hand_controller.get_state()
            if victory_exit.update(is_detected, gesture, now):
                return False
            if now >= entry_ready_at and (
                not is_detected or gesture != "Fist"
            ):
                fist_armed = True
        else:
            victory_exit.update(False, "None", now)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if (
                    transition_until is None
                    and not require_fist
                    and now >= entry_ready_at
                    and event.key in (pygame.K_SPACE, pygame.K_RETURN)
                ):
                    transition_until = now + TRANSITION_COOLDOWN_MS
                    fist_armed = False

        if (
            transition_until is None
            and hand_controller is not None
            and now >= entry_ready_at
            and fist_armed
            and is_detected
            and gesture == "Fist"
        ):
            transition_until = now + TRANSITION_COOLDOWN_MS
            fist_armed = False

        if transition_until is not None and now >= transition_until:
            return True

        screen.fill((20, 28, 34))
        pygame.draw.rect(screen, (31, 57, 47), board, border_radius=12)
        pygame.draw.rect(screen, (145, 111, 70), board, 7, border_radius=12)

        title_surface = title_font.render(title, True, (255, 224, 117))
        screen.blit(
            title_surface,
            (width // 2 - title_surface.get_width() // 2, board.y + 30),
        )
        pygame.draw.line(
            screen,
            (145, 111, 70),
            (board.x + 35, board.y + 95),
            (board.right - 35, board.y + 95),
            2,
        )

        y = board.y + 120
        for heading, instructions in sections:
            heading_surface = heading_font.render(heading, True, (255, 224, 117))
            screen.blit(heading_surface, (board.x + 48, y))
            y += 35
            for instruction in instructions:
                line_surface = body_font.render(instruction, True, (245, 245, 235))
                screen.blit(line_surface, (board.x + 58, y))
                y += 31
            y += 12

        if transition_until is not None:
            prompt_text = "잠시 후 게임이 시작됩니다..."
        elif now < entry_ready_at:
            prompt_text = "안내를 읽어 주세요. 잠시 후 시작 입력이 활성화됩니다."
        elif require_fist:
            prompt_text = "주먹(Fist): 게임 시작    |    ESC / V 모양 1초: 메뉴"
        else:
            prompt_text = "SPACE / ENTER / 주먹: 시작    |    ESC / V 모양 1초: 메뉴"
        prompt = prompt_font.render(
            prompt_text,
            True,
            (150, 255, 170),
        )
        screen.blit(
            prompt,
            (width // 2 - prompt.get_width() // 2, board.bottom - 48),
        )
        if hand_controller is not None:
            exit_hint = prompt_font.render(
                "ESC / V 모양 1초: 메뉴로 돌아가기",
                True,
                (210, 220, 210),
            )
            screen.blit(
                exit_hint,
                (width // 2 - exit_hint.get_width() // 2, board.bottom - 80),
            )
        pygame.display.flip()

    return True
