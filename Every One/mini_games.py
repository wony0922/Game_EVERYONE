import math
import os
import random

import pygame

from display_utils import set_game_display
from font_utils import get_font
from game_tutorial import show_tutorial
from hand_exit import VictoryExit
from hand_input import scale_hand_x


WIDTH = 800
HEIGHT = 600
WINDOW_WIDTH = WIDTH + 240
FPS = 60
WHITE = (245, 245, 235)
MUTED = (165, 180, 185)
GOLD = (255, 220, 110)
GREEN = (100, 220, 140)
RED = (245, 100, 100)
CURSOR_GAIN_X = 3.2
CURSOR_GAIN_Y = 2.8
PICKUP_RADIUS = 64
_BACKGROUND_CACHE = {}


def _start_game(title, tutorial, hand_controller):
    pygame.init()
    screen = set_game_display((WINDOW_WIDTH, HEIGHT), title)
    if not show_tutorial(screen, title, tutorial, hand_controller):
        return None
    return screen


def _countdown(screen, hand_controller, scene_drawer=None):
    clock = pygame.time.Clock()
    exit_gesture = VictoryExit()
    started_at = pygame.time.get_ticks()
    countdown_font = get_font(112, bold=True)
    label_font = get_font(28, bold=True)

    while True:
        clock.tick(FPS)
        now = pygame.time.get_ticks()
        detected, _hand_x, _hand_y, gesture = _read_hand(hand_controller)
        if exit_gesture.update(detected, gesture, now):
            return False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False

        elapsed = (now - started_at) / 1000.0
        if elapsed >= 3:
            return True

        if scene_drawer:
            scene_drawer()
        else:
            screen.fill((11, 20, 32))
            for index in range(8):
                x = (index * 127 + 43) % WINDOW_WIDTH
                y = (index * 83 + 29) % HEIGHT
                pygame.draw.circle(screen, (46, 77, 96), (x, y), 3 + index % 3)
        label = label_font.render("준비하세요", True, WHITE)
        screen.blit(label, label.get_rect(center=(WIDTH // 2, 175)))
        count = 3 - int(elapsed)
        number = countdown_font.render(str(count), True, GOLD)
        screen.blit(number, number.get_rect(center=(WIDTH // 2, 285)))
        pygame.draw.circle(screen, (74, 118, 140), (WIDTH // 2, 285), 92, 3)
        _draw_camera_panel(screen, hand_controller, gesture)
        pygame.display.flip()


def _read_hand(hand_controller):
    if hand_controller is None:
        return False, 0.5, 0.5, "None"
    return hand_controller.get_state()


def _cursor_position(hand_x, hand_y):
    x = 0.5 + (hand_x - 0.5) * CURSOR_GAIN_X
    y = 0.5 + (hand_y - 0.5) * CURSOR_GAIN_Y
    return (
        round(max(0.02, min(0.98, x)) * WIDTH),
        round(max(0.04, min(0.96, y)) * HEIGHT),
    )


def _scene_background(top_color, bottom_color, accent_color):
    key = (top_color, bottom_color, accent_color)
    if key not in _BACKGROUND_CACHE:
        background = pygame.Surface((WIDTH, HEIGHT))
        for y in range(HEIGHT):
            blend = y / (HEIGHT - 1)
            color = tuple(
                round(top + (bottom - top) * blend)
                for top, bottom in zip(top_color, bottom_color)
            )
            pygame.draw.line(background, color, (0, y), (WIDTH, y))

        decoration = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for index in range(9):
            x = (index * 127 + 43) % WIDTH
            y = 90 + (index * 83) % (HEIGHT - 110)
            pygame.draw.circle(decoration, (*accent_color, 18), (x, y), 36 + index % 3 * 14)
        background.blit(decoration, (0, 0))
        _BACKGROUND_CACHE[key] = background
    return _BACKGROUND_CACHE[key]


def _cursor_near_rect(position, rect, radius=PICKUP_RADIUS):
    nearest_x = max(rect.left, min(position[0], rect.right))
    nearest_y = max(rect.top, min(position[1], rect.bottom))
    return (position[0] - nearest_x) ** 2 + (position[1] - nearest_y) ** 2 <= radius ** 2


def _ellipse_touches_rect(ellipse_rect, rect):
    nearest_x = max(rect.left, min(ellipse_rect.centerx, rect.right))
    nearest_y = max(rect.top, min(ellipse_rect.centery, rect.bottom))
    radius_x = ellipse_rect.width / 2
    radius_y = ellipse_rect.height / 2
    dx = (nearest_x - ellipse_rect.centerx) / radius_x
    dy = (nearest_y - ellipse_rect.centery) / radius_y
    return dx * dx + dy * dy <= 1


def _draw_cursor(screen, position, color=GOLD, radius=18):
    glow = pygame.Surface((radius * 2 + 12, radius * 2 + 12), pygame.SRCALPHA)
    center = (radius + 6, radius + 6)
    pygame.draw.circle(glow, (*color, 38), center, radius + 5)
    pygame.draw.circle(glow, (*color, 115), center, radius, 2)
    screen.blit(glow, (position[0] - center[0], position[1] - center[1]))
    pygame.draw.circle(screen, color, position, max(3, radius // 5), 2)
    pygame.draw.circle(screen, color, position, 4)


def _draw_header(screen, title, score, font):
    pygame.draw.rect(screen, (12, 22, 34), (0, 0, WIDTH, 60))
    pygame.draw.line(screen, (75, 105, 125), (0, 59), (WIDTH, 59), 2)
    pygame.draw.rect(screen, (84, 198, 205), (0, 0, 6, 60))
    title_surface = font.render(title, True, WHITE)
    screen.blit(title_surface, (24, (60 - title_surface.get_height()) // 2))
    score_surface = font.render("점수  {}".format(score), True, GOLD)
    badge = pygame.Rect(WIDTH - score_surface.get_width() - 42, 8, score_surface.get_width() + 24, 44)
    pygame.draw.rect(screen, (31, 47, 60), badge, border_radius=14)
    pygame.draw.rect(screen, (86, 112, 126), badge, 1, border_radius=14)
    screen.blit(score_surface, score_surface.get_rect(center=badge.center))


def _draw_game_over(
    screen,
    score,
    font,
    detail=None,
    restart_prompt="ENTER / FIST  다시 시작",
):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((5, 12, 22, 205))
    screen.blit(overlay, (0, 0))

    panel = pygame.Rect(92, 156, WIDTH - 184, 292)
    pygame.draw.rect(screen, (20, 34, 48), panel, border_radius=24)
    pygame.draw.rect(screen, (101, 141, 158), panel, 2, border_radius=24)
    title = get_font(44, bold=True).render("GAME OVER", True, RED)
    screen.blit(title, title.get_rect(center=(WIDTH // 2, 218)))
    score_text = font.render("최종 점수  {}".format(score), True, GOLD)
    screen.blit(score_text, score_text.get_rect(center=(WIDTH // 2, 276)))
    if detail:
        detail_text = font.render(detail, True, WHITE)
        screen.blit(detail_text, detail_text.get_rect(center=(WIDTH // 2, 318)))

    restart_text = font.render(restart_prompt, True, WHITE)
    menu_text = font.render("ESC / V  메뉴로 나가기", True, MUTED)
    screen.blit(restart_text, restart_text.get_rect(center=(WIDTH // 2, 365)))
    screen.blit(menu_text, menu_text.get_rect(center=(WIDTH // 2, 405)))


def _draw_camera_panel(screen, hand_controller, gesture):
    pygame.draw.rect(screen, (13, 23, 35), (WIDTH, 0, WINDOW_WIDTH - WIDTH, HEIGHT))
    pygame.draw.line(screen, (60, 91, 111), (WIDTH, 0), (WIDTH, HEIGHT), 2)
    label_font = get_font(20, bold=True)
    title = label_font.render("손 동작", True, WHITE)
    screen.blit(title, title.get_rect(center=(WIDTH + 120, 145)))
    if hand_controller is None:
        status = label_font.render("카메라 없음", True, MUTED)
        screen.blit(status, status.get_rect(center=(WIDTH + 120, 240)))
        return
    preview = hand_controller.get_preview_surface()
    if preview is not None:
        preview = pygame.transform.smoothscale(preview, (160, 120))
        frame = pygame.Rect(WIDTH + 34, 174, 172, 132)
        pygame.draw.rect(screen, (31, 46, 58), frame, border_radius=14)
        screen.blit(preview, (WIDTH + 40, 180))
        pygame.draw.rect(screen, (107, 142, 157), (WIDTH + 40, 180, 160, 120), 2, border_radius=8)
    status = label_font.render(str(gesture), True, GREEN)
    status_box = pygame.Rect(WIDTH + 30, 322, 180, 48)
    pygame.draw.rect(screen, (31, 55, 54), status_box, border_radius=14)
    screen.blit(status, status.get_rect(center=status_box.center))
    exit_text = label_font.render("V: 메뉴", True, MUTED)
    screen.blit(exit_text, exit_text.get_rect(center=(WIDTH + 120, 410)))


class _CursorSmoother:
    def __init__(self, initial_position=None):
        self.position = initial_position

    def update(self, hand_x, hand_y, dt):
        target = _cursor_position(hand_x, hand_y)
        if self.position is None:
            self.position = target
            return self.position

        distance = math.dist(self.position, target)
        time_constant = max(0.035, 0.09 - distance / 2200)
        alpha = 1 - math.exp(-min(dt, 0.05) / time_constant)
        self.position = (
            round(self.position[0] + (target[0] - self.position[0]) * alpha),
            round(self.position[1] + (target[1] - self.position[1]) * alpha),
        )
        return self.position


class _GestureHold:
    def __init__(self, gesture, duration_ms):
        self.gesture = gesture
        self.duration_ms = duration_ms
        self.started_at = None
        self.fired = False

    def update(self, gesture, now):
        if gesture != self.gesture:
            self.started_at = None
            self.fired = False
            return False
        if self.started_at is None:
            self.started_at = now
        if not self.fired and now - self.started_at >= self.duration_ms:
            self.fired = True
            return True
        return False


def _ski_speed(elapsed):
    if elapsed <= 10:
        return 110 + elapsed * 39
    return 500 + min(elapsed - 10, 60) * 37.5


def run_burger_tower(hand_controller=None):
    screen = _start_game(
        "버거 탑 쌓기",
        [
            ("목표", ["재료를 접시 중앙에 타이밍 맞춰 쌓기"]),
            ("조작", [
                "FIST|재료통 위에서 Fist: 재료 만들기",
                "OPEN_PALM|Open Palm: 재료 떨어뜨리기",
                "V|V: 메뉴로 나가기",
            ]),
        ],
        hand_controller,
    )
    if screen is None:
        return

    clock = pygame.time.Clock()
    font = get_font(26, bold=True)
    body_font = get_font(22, bold=True)
    exit_gesture = VictoryExit()
    fist_hold = _GestureHold("Fist", 350)
    palm_hold = _GestureHold("Open Palm", 350)
    asset_dir = os.path.join(os.path.dirname(__file__), "assets")
    background = pygame.transform.scale(
        pygame.image.load(os.path.join(asset_dir, "burger_station.png")).convert(),
        (WIDTH, HEIGHT),
    )
    ingredient_data = {
        "bun_bottom": ("아래 빵", "burger_bun_bottom.png", (112, 62)),
        "bun_top": ("깨 빵", "burger_bun_top.png", (112, 66)),
        "patty": ("패티", "burger_patty.png", (112, 52)),
        "lettuce": ("양상추", "burger_lettuce.png", (120, 52)),
        "cheese": ("치즈", "burger_cheese.png", (94, 60)),
        "tomato": ("토마토", "burger_tomato.png", (106, 58)),
    }
    middle_ingredients = ["patty", "lettuce", "cheese", "tomato"]
    recipe = ["bun_bottom"] + random.sample(middle_ingredients, len(middle_ingredients)) + ["bun_top"]
    ingredient_images = {
        key: pygame.transform.scale(
            pygame.image.load(os.path.join(asset_dir, filename)).convert_alpha(),
            size,
        )
        for key, (_name, filename, size) in ingredient_data.items()
    }
    complete_burger = pygame.transform.scale(
        pygame.image.load(os.path.join(asset_dir, "burger_complete.png")).convert_alpha(),
        (150, 140),
    )
    ingredient_zones = [
        (pygame.Rect(40, 44, 240, 184), "bun_top"),
        (pygame.Rect(512, 42, 246, 185), "bun_bottom"),
        (pygame.Rect(10, 224, 230, 190), "patty"),
        (pygame.Rect(575, 224, 215, 190), "cheese"),
        (pygame.Rect(18, 395, 235, 185), "lettuce"),
        (pygame.Rect(555, 395, 235, 185), "tomato"),
    ]
    time_limits = (60, 50, 42, 35, 30)
    score = 0
    stack_layers = []
    used_ingredients = set()
    ingredient_key = None
    burgers_completed = 0
    result_until = 0
    last_result_points = 0
    last_result_correct = False
    restart_fist = _GestureHold("Fist", 500)
    held = False
    game_over = False
    deadline = pygame.time.get_ticks() + time_limits[0] * 1000
    cursor = (WIDTH // 2, HEIGHT // 2)
    cursor_smoother = _CursorSmoother(cursor)
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        now = pygame.time.get_ticks()
        detected, hand_x, hand_y, gesture = _read_hand(hand_controller)
        if exit_gesture.update(detected, gesture, now):
            break
        if detected:
            cursor = cursor_smoother.update(hand_x, hand_y, dt)

        restart_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif game_over and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    restart_requested = True

        if game_over and restart_fist.update(gesture if detected else "None", now):
            restart_requested = True
        elif not game_over:
            restart_fist.update("None", now)

        if restart_requested:
            score = 0
            stack_layers = []
            used_ingredients = set()
            ingredient_key = None
            burgers_completed = 0
            result_until = 0
            held = game_over = False
            deadline = now + time_limits[0] * 1000
            fist_hold = _GestureHold("Fist", 350)
            palm_hold = _GestureHold("Open Palm", 350)
            restart_fist = _GestureHold("Fist", 500)

        selected_zone = next(
            (key for zone, key in ingredient_zones if zone.collidepoint(cursor)),
            None,
        )
        if (
            detected and gesture == "Fist" and not held and not game_over
            and now >= result_until and selected_zone
            and selected_zone not in used_ingredients
        ):
            if fist_hold.update(gesture, now):
                ingredient_key = selected_zone
                held = True
        else:
            fist_hold.update("None", now)

        plate_ellipse = pygame.Rect(275, 205, 250, 220)
        image = ingredient_images[ingredient_key] if ingredient_key else None
        ingredient_rect = image.get_rect(center=cursor) if held and image else None
        if (
            detected and held and gesture == "Open Palm" and not game_over
            and now >= result_until
        ):
            if palm_hold.update(gesture, now):
                touched_bowl = _ellipse_touches_rect(plate_ellipse, ingredient_rect)
                stack_area = pygame.Rect(325, 318 - len(stack_layers) * 24, 150, 70)
                touched_stack = bool(stack_layers) and ingredient_rect.colliderect(stack_area)
                if touched_bowl or touched_stack:
                    stack_layers.append(ingredient_key)
                    used_ingredients.add(ingredient_key)
                    if len(stack_layers) == len(recipe):
                        last_result_correct = stack_layers == recipe
                        last_result_points = 3 if last_result_correct else 1
                        score += last_result_points
                        burgers_completed += 1
                        result_until = now + 1600
                        stack_layers = []
                        used_ingredients = set()
                        time_limit = time_limits[min(burgers_completed, len(time_limits) - 1)]
                        deadline = now + time_limit * 1000
                        recipe = (
                            ["bun_bottom"]
                            + random.sample(middle_ingredients, len(middle_ingredients))
                            + ["bun_top"]
                        )
                held = False
                ingredient_key = None
        else:
            palm_hold.update(gesture, now)
        if not game_over and now >= deadline:
            game_over = True
            held = False

        screen.blit(background, (0, 0))
        _draw_header(screen, "버거 탑 쌓기", score, font)
        for index, layer_key in enumerate(stack_layers):
            layer_image = ingredient_images[layer_key]
            screen.blit(
                layer_image,
                layer_image.get_rect(midbottom=(WIDTH // 2, 390 - index * 25)),
            )
        recipe_panel = pygame.Surface((WIDTH, 74), pygame.SRCALPHA)
        recipe_panel.fill((244, 246, 249, 225))
        screen.blit(recipe_panel, (0, HEIGHT - 74))
        recipe_title = body_font.render("만들 순서", True, (38, 50, 59))
        screen.blit(recipe_title, (18, HEIGHT - 51))
        recipe_x_positions = (190, 290, 390, 490, 590, 690)
        for index, key in enumerate(recipe):
            slot = pygame.Rect(recipe_x_positions[index] - 34, HEIGHT - 65, 68, 56)
            pygame.draw.rect(screen, (255, 255, 255, 220), slot, border_radius=10)
            pygame.draw.rect(screen, (111, 137, 149), slot, 1, border_radius=10)
            guide_image = pygame.transform.smoothscale(ingredient_images[key], (54, 34))
            screen.blit(guide_image, guide_image.get_rect(center=(slot.centerx, slot.centery + 4)))
            number = get_font(16, bold=True).render(str(index + 1), True, (45, 58, 66))
            screen.blit(number, number.get_rect(center=(slot.centerx, slot.top + 8)))
        if held and image:
            screen.blit(image, ingredient_rect)
            name = ingredient_data[ingredient_key][0]
            label = body_font.render(name, True, (40, 45, 50))
            screen.blit(label, label.get_rect(center=(cursor[0], cursor[1] + 46)))
        seconds_left = max(0, (deadline - now + 999) // 1000)
        timer = body_font.render(
            "제한시간 {}초".format(seconds_left), True, RED if seconds_left <= 10 else GOLD
        )
        screen.blit(timer, (24, 68))
        if result_until and now < result_until:
            screen.blit(complete_burger, complete_burger.get_rect(center=(WIDTH // 2, 305)))
            result_message = body_font.render(
                ("순서 완성! " if last_result_correct else "순서 오류! ")
                + "점수 +{}".format(last_result_points),
                True,
                (35, 74, 48) if last_result_correct else (142, 54, 44),
            )
            screen.blit(result_message, result_message.get_rect(center=(WIDTH // 2, 397)))
        if detected:
            _draw_cursor(screen, cursor, radius=PICKUP_RADIUS)
        status_text = body_font.render(
            "남은 재료 {}개".format(len(recipe) - len(used_ingredients)),
            True,
            (42, 58, 63),
        )
        screen.blit(status_text, (24, 104))
        if game_over:
            _draw_game_over(
                screen, score, font, "시간 초과",
                restart_prompt="ENTER / FIST (0.5초) 다시 시작",
            )
        _draw_camera_panel(screen, hand_controller, gesture)
        pygame.display.flip()


def run_fly_swatter(hand_controller=None):
    screen = _start_game(
        "모기 잡기",
        [
            ("목표", ["날아다니는 모기를 조준해 잡기"]),
            ("조작", [
                "OPEN_PALM|Open Palm: 잡을 범위 지정",
                "FIST|Fist: 범위 안의 모기 잡기 (0.5초 대기)",
                "V|V: 메뉴로 나가기",
            ]),
        ],
        hand_controller,
    )
    if screen is None:
        return

    clock = pygame.time.Clock()
    font = get_font(26, bold=True)
    exit_gesture = VictoryExit()
    score = 0
    started_at = pygame.time.get_ticks()
    initial_count = 5
    max_mosquitoes = initial_count * 2
    cursor = (WIDTH // 2, HEIGHT // 2)
    cursor_smoother = _CursorSmoother(cursor)
    restart_fist = _GestureHold("Fist", 500)
    range_radius = 112
    spawn_interval = 2400
    next_spawn = started_at + spawn_interval
    last_swatter = started_at - 500
    next_bomb_at = started_at + random.randint(9000, 16000)
    bombs = []
    stunned_until = 0
    explosion = None
    next_blackout_at = started_at + random.randint(30000, 60000)
    blackout_until = 0
    game_over = False
    mosquito_images = [
        pygame.transform.smoothscale(
            pygame.image.load(
                os.path.join(os.path.dirname(__file__), "assets", filename)
            ).convert_alpha(),
            (76, 50),
        )
        for filename in ("mosquito_1.png", "mosquito_2.png")
    ]
    dark_mosquito_images = []
    for image in mosquito_images:
        dark_image = image.copy()
        dark_image.fill((34, 34, 38, 255), special_flags=pygame.BLEND_RGBA_MULT)
        dark_mosquito_images.append(dark_image)
    yellow_mosquito_images = []
    for image in mosquito_images:
        yellow_image = image.copy()
        yellow_image.fill((255, 245, 70, 255), special_flags=pygame.BLEND_RGBA_MULT)
        yellow_mosquito_images.append(yellow_image)
    bomb_image = pygame.transform.smoothscale(
        pygame.image.load(
            os.path.join(os.path.dirname(__file__), "assets", "mosquito_bomb.png")
        ).convert_alpha(),
        (42, 52),
    )
    room_background = pygame.transform.smoothscale(
        pygame.image.load(
            os.path.join(os.path.dirname(__file__), "assets", "mosquito_room_bg.png")
        ).convert(),
        (WIDTH, HEIGHT),
    )

    def make_mosquito(now, speed_multiplier=1.0):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(145, 245) * speed_multiplier
        kind = "yellow" if random.random() < 0.2 else "normal"
        return [
            random.randint(45, WIDTH - 45),
            random.randint(85, HEIGHT - 45),
            math.cos(angle) * speed,
            math.sin(angle) * speed,
            now + random.randint(450, 1100),
            random.randrange(len(mosquito_images)),
            kind,
            now,
            now,
        ]

    mosquitoes = [make_mosquito(started_at) for _ in range(initial_count)]
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        now = pygame.time.get_ticks()
        detected, hand_x, hand_y, gesture = _read_hand(hand_controller)
        if exit_gesture.update(detected, gesture, now):
            break
        if detected and gesture == "Open Palm" and not game_over and now >= stunned_until:
            cursor = cursor_smoother.update(hand_x, hand_y, dt)

        restart_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif game_over and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    restart_requested = True

        if game_over and restart_fist.update(gesture if detected else "None", now):
            restart_requested = True
        elif not game_over:
            restart_fist.update("None", now)

        if restart_requested:
            score = 0
            started_at = now
            cursor = (WIDTH // 2, HEIGHT // 2)
            cursor_smoother = _CursorSmoother(cursor)
            mosquitoes = [make_mosquito(started_at) for _ in range(initial_count)]
            bombs = []
            spawn_interval = 2400
            next_spawn = started_at + spawn_interval
            last_swatter = started_at - 500
            next_bomb_at = started_at + random.randint(9000, 16000)
            next_blackout_at = started_at + random.randint(30000, 60000)
            blackout_until = 0
            stunned_until = 0
            explosion = None
            game_over = False
            restart_fist = _GestureHold("Fist", 500)

        elapsed_seconds = (now - started_at) / 1000
        speed_multiplier = 1.0 + min(1.0, elapsed_seconds / 60.0)
        if elapsed_seconds <= 10:
            range_radius = round(112 - elapsed_seconds * 4.2)
        else:
            range_radius = max(52, round(70 - (elapsed_seconds - 10) * 0.3))
        if not blackout_until and now >= next_blackout_at:
            blackout_until = now + random.randint(5000, 10000)
            next_blackout_at = blackout_until + random.randint(30000, 60000)
        elif blackout_until and now >= blackout_until:
            blackout_until = 0

        if not game_over:
            for mosquito in mosquitoes:
                if mosquito[6] == "yellow":
                    desired_angle = math.atan2(mosquito[3], mosquito[2])
                    if now >= mosquito[4]:
                        desired_angle += random.uniform(-0.75, 0.75)
                        mosquito[4] = now + random.randint(600, 1200)

                    edge_x = 70 if mosquito[0] < 70 else WIDTH - 70 if mosquito[0] > WIDTH - 70 else None
                    edge_y = 100 if mosquito[1] < 100 else HEIGHT - 60 if mosquito[1] > HEIGHT - 60 else None
                    if edge_x is not None or edge_y is not None:
                        inward_x = (WIDTH / 2 - mosquito[0]) if edge_x is not None else 0
                        inward_y = (HEIGHT / 2 - mosquito[1]) if edge_y is not None else 0
                        desired_angle = math.atan2(inward_y, inward_x)

                    cursor_distance = math.dist((mosquito[0], mosquito[1]), cursor)
                    if detected and cursor_distance < range_radius + 90:
                        away_angle = math.atan2(mosquito[1] - cursor[1], mosquito[0] - cursor[0])
                        urgency = max(0.0, min(1.0, (range_radius + 90 - cursor_distance) / 90))
                        desired_angle += math.atan2(
                            math.sin(away_angle - desired_angle) * urgency,
                            math.cos(away_angle - desired_angle) * urgency,
                        )
                        if cursor_distance < range_radius + 20 and now - mosquito[7] >= 3000:
                            desired_angle = away_angle + random.uniform(-0.3, 0.3)
                            mosquito[7] = now
                            panic_speed = random.uniform(330, 390) * speed_multiplier
                            mosquito[2] = math.cos(desired_angle) * panic_speed
                            mosquito[3] = math.sin(desired_angle) * panic_speed
                            mosquito[8] = now + 600

                    current_angle = math.atan2(mosquito[3], mosquito[2])
                    angle_delta = math.atan2(
                        math.sin(desired_angle - current_angle),
                        math.cos(desired_angle - current_angle),
                    )
                    turn = max(-2.4 * dt, min(2.4 * dt, angle_delta))
                    current_angle += turn
                    speed = (370 if now < mosquito[8] else 205) * speed_multiplier
                    mosquito[2] = math.cos(current_angle) * speed
                    mosquito[3] = math.sin(current_angle) * speed
                    mosquito[0] += mosquito[2] * dt
                    mosquito[1] += mosquito[3] * dt
                    mosquito[0] = max(28, min(WIDTH - 28, mosquito[0]))
                    mosquito[1] = max(78, min(HEIGHT - 28, mosquito[1]))
                    continue

                if now >= mosquito[4]:
                    angle = math.atan2(mosquito[3], mosquito[2])
                    angle += random.uniform(-0.9, 0.9)
                    speed = random.uniform(145, 245) * speed_multiplier
                    mosquito[2] = math.cos(angle) * speed
                    mosquito[3] = math.sin(angle) * speed
                    mosquito[4] = now + random.randint(450, 1100)
                mosquito[0] += mosquito[2] * dt
                mosquito[1] += mosquito[3] * dt
                if mosquito[0] < 25 or mosquito[0] > WIDTH - 25:
                    mosquito[2] *= -1
                    mosquito[0] = max(25, min(WIDTH - 25, mosquito[0]))
                if mosquito[1] < 75 or mosquito[1] > HEIGHT - 25:
                    mosquito[3] *= -1
                    mosquito[1] = max(75, min(HEIGHT - 25, mosquito[1]))

            if now >= next_spawn:
                mosquitoes.append(make_mosquito(now, speed_multiplier))
                spawn_interval = max(1200, spawn_interval - 40)
                next_spawn = now + spawn_interval
                if len(mosquitoes) >= max_mosquitoes:
                    game_over = True

            if now >= next_bomb_at:
                bomb_angle = random.uniform(0, math.tau)
                bomb_speed = random.uniform(65, 105)
                bombs.append([
                    random.randint(55, WIDTH - 55),
                    random.randint(100, HEIGHT - 55),
                    math.cos(bomb_angle) * bomb_speed,
                    math.sin(bomb_angle) * bomb_speed,
                ])
                next_bomb_at = now + random.randint(18000, 30000)
            for bomb in bombs:
                bomb[0] += bomb[2] * dt
                bomb[1] += bomb[3] * dt
                if bomb[0] < 24 or bomb[0] > WIDTH - 24:
                    bomb[2] *= -1
                if bomb[1] < 78 or bomb[1] > HEIGHT - 24:
                    bomb[3] *= -1

            if (
                not game_over
                and detected
                and gesture == "Fist"
                and now >= stunned_until
                and now - last_swatter >= 500
            ):
                hit_bomb_index = next(
                    (
                        index for index, bomb in enumerate(bombs)
                        if (cursor[0] - bomb[0]) ** 2 + (cursor[1] - bomb[1]) ** 2
                        <= range_radius ** 2
                    ),
                    None,
                )
                if hit_bomb_index is not None:
                    hit_bomb = bombs.pop(hit_bomb_index)
                    stunned_until = now + 3000
                    explosion = (hit_bomb[0], hit_bomb[1], now)
                    last_swatter = now
                else:
                    hit_bomb_index = None
                if hit_bomb_index is None:
                    before = len(mosquitoes)
                    mosquitoes = [
                        mosquito for mosquito in mosquitoes
                        if (cursor[0] - mosquito[0]) ** 2
                        + (cursor[1] - mosquito[1]) ** 2
                        > range_radius ** 2
                    ]
                    score += before - len(mosquitoes)
                    last_swatter = now

        lights_out = bool(blackout_until)
        if lights_out:
            screen.fill((4, 5, 9))
        else:
            screen.blit(room_background, (0, 0))
        _draw_header(screen, "모기 잡기", score, font)
        for mosquito in mosquitoes:
            x, y = int(mosquito[0]), int(mosquito[1])
            if mosquito[6] == "yellow":
                image_set = dark_mosquito_images if lights_out else yellow_mosquito_images
            else:
                image_set = dark_mosquito_images if lights_out else mosquito_images
            image = image_set[mosquito[5]]
            screen.blit(image, image.get_rect(center=(x, y)))
        for bomb in bombs:
            screen.blit(bomb_image, bomb_image.get_rect(center=(round(bomb[0]), round(bomb[1]))))
        if explosion:
            explosion_age = now - explosion[2]
            if explosion_age < 650:
                center = (round(explosion[0]), round(explosion[1]))
                progress = explosion_age / 650
                blast_radius = round(12 + progress * 74)
                pygame.draw.circle(screen, (255, 221, 91), center, blast_radius, max(2, 8 - round(progress * 6)))
                pygame.draw.circle(screen, (255, 132, 45), center, round(blast_radius * 0.62), 3)
                for ray_index in range(10):
                    angle = math.tau * ray_index / 10
                    inner = blast_radius * 0.75
                    outer = blast_radius + 14
                    pygame.draw.line(
                        screen,
                        (255, 239, 155),
                        (round(center[0] + math.cos(angle) * inner), round(center[1] + math.sin(angle) * inner)),
                        (round(center[0] + math.cos(angle) * outer), round(center[1] + math.sin(angle) * outer)),
                        3,
                    )
            else:
                explosion = None
        timer_color = (150, 152, 158) if lights_out else (38, 55, 65)
        timer = font.render("경과 {}초".format(int(elapsed_seconds)), True, timer_color)
        screen.blit(timer, (WIDTH - timer.get_width() - 24, 70))
        if detected and gesture in ("Open Palm", "Fist"):
            ring_color = (78, 81, 91) if lights_out else (73, 142, 187)
            pygame.draw.circle(screen, ring_color, cursor, range_radius, 1)
            pygame.draw.circle(screen, ring_color, cursor, range_radius - 5, 1)
            pygame.draw.circle(screen, RED if gesture == "Fist" else GOLD, cursor, 8)
        if lights_out:
            blackout_label = get_font(20, bold=True).render("불이 꺼졌습니다", True, (115, 117, 125))
            screen.blit(blackout_label, (24, HEIGHT - 38))
        if now < stunned_until:
            stun_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            stun_overlay.fill((255, 236, 135, 58))
            screen.blit(stun_overlay, (0, 0))
            stun_text = get_font(32, bold=True).render(
                "기절! {:.1f}초".format((stunned_until - now) / 1000),
                True,
                (255, 226, 117),
            )
            screen.blit(stun_text, stun_text.get_rect(center=(WIDTH // 2, 130)))
        if game_over:
            _draw_game_over(
                screen, score, font,
                "생존 {}초  ·  모기 {}마리".format(int(elapsed_seconds), len(mosquitoes)),
                restart_prompt="ENTER / FIST (0.5초) 다시 시작",
            )
        _draw_camera_panel(screen, hand_controller, gesture)
        pygame.display.flip()


def run_pattern_line(hand_controller=None):
    screen = _start_game(
        "비밀번호 궤적 잇기",
        [
            ("목표", ["제한시간 안에 1 → 2 → 3 순서로 잇기"]),
            ("조작", [
                "POINT|Point: 손가락으로 숫자 이어 그리기",
                "V|V: 메뉴로 나가기",
            ]),
        ],
        hand_controller,
    )
    if screen is None:
        return

    clock = pygame.time.Clock()
    font = get_font(30, bold=True)
    body_font = get_font(24, bold=True)
    exit_gesture = VictoryExit()
    def make_nodes(count):
        nodes = []
        attempts = 0
        while len(nodes) < count and attempts < count * 100:
            attempts += 1
            candidate = (random.randint(65, WIDTH - 65), random.randint(115, HEIGHT - 65))
            if all(
                (candidate[0] - x) ** 2 + (candidate[1] - y) ** 2 >= 115 ** 2
                for x, y in nodes
            ):
                nodes.append(candidate)
        return nodes

    nodes = make_nodes(3)
    progress = 0
    score = 0
    round_started = pygame.time.get_ticks()
    round_duration = 7000
    cursor = None
    cursor_smoother = _CursorSmoother()
    restart_fist = _GestureHold("Fist", 500)
    game_over = False
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        now = pygame.time.get_ticks()
        detected, hand_x, hand_y, gesture = _read_hand(hand_controller)
        if exit_gesture.update(detected, gesture, now):
            break
        cursor = cursor_smoother.update(hand_x, hand_y, dt) if detected else None

        restart_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif game_over and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    restart_requested = True

        if game_over and restart_fist.update(gesture if detected else "None", now):
            restart_requested = True
        elif not game_over:
            restart_fist.update("None", now)

        if restart_requested:
            score = 0
            nodes = make_nodes(3)
            progress = 0
            round_started = now
            cursor_smoother = _CursorSmoother()
            game_over = False
            restart_fist = _GestureHold("Fist", 500)

        if now - round_started >= round_duration:
            game_over = True
        if not game_over and detected and gesture == "Point" and progress < len(nodes):
            target = nodes[progress]
            if (cursor[0] - target[0]) ** 2 + (cursor[1] - target[1]) ** 2 <= 46 ** 2:
                progress += 1
                if progress == len(nodes):
                    score += 1
                    nodes = make_nodes(len(nodes) + 1)
                    progress = 0
                    round_started = now

        remaining = max(0, round_duration - (now - round_started))
        screen.blit(_scene_background((20, 33, 61), (16, 26, 48), (66, 150, 208)), (0, 0))
        _draw_header(screen, "비밀번호 궤적 잇기", score, font)
        for x in range(40, WIDTH, 40):
            pygame.draw.line(screen, (30, 54, 78), (x, 72), (x, HEIGHT), 1)
        for y in range(100, HEIGHT, 40):
            pygame.draw.line(screen, (30, 54, 78), (0, y), (WIDTH, y), 1)
        timer_track = pygame.Rect(24, 72, WIDTH - 48, 8)
        pygame.draw.rect(screen, (33, 47, 65), timer_track, border_radius=4)
        timer_width = round(timer_track.width * remaining / round_duration)
        if timer_width:
            pygame.draw.rect(screen, (83, 208, 195), (timer_track.x, timer_track.y, timer_width, timer_track.height), border_radius=4)
        for index, node in enumerate(nodes):
            if index + 1 < progress:
                pygame.draw.line(screen, (31, 91, 110), node, nodes[index + 1], 14)
                pygame.draw.line(screen, GREEN, node, nodes[index + 1], 6)
            pygame.draw.circle(screen, (8, 17, 35), (node[0], node[1] + 5), 47)
            pygame.draw.circle(screen, (49, 194, 204) if index == progress else (54, 83, 111), node, 43)
            pygame.draw.circle(screen, (163, 239, 225) if index == progress else (131, 163, 182), node, 43, 2)
            number = body_font.render(str(index + 1), True, WHITE)
            screen.blit(number, number.get_rect(center=node))
        timer = body_font.render("{:.1f}초".format(remaining / 1000), True, GOLD)
        screen.blit(timer, (WIDTH - timer.get_width() - 24, 75))
        if cursor and gesture == "Point" and not game_over:
            _draw_cursor(screen, cursor)
            if progress:
                pygame.draw.line(screen, GOLD, nodes[progress - 1], cursor, 4)
        if game_over:
            _draw_game_over(
                screen, score, font, "시간 초과",
                restart_prompt="ENTER / FIST (0.5초) 다시 시작",
            )
        _draw_camera_panel(screen, hand_controller, gesture)
        pygame.display.flip()


def _make_maze():
    columns, rows = 15, 9
    cells = [[{"N": True, "S": True, "E": True, "W": True}
              for _ in range(columns)] for _ in range(rows)]
    visited = set()
    stack = [(columns // 2, rows // 2)]
    visited.add(stack[0])
    while stack:
        x, y = stack[-1]
        neighbors = [
            (x, y - 1, "N", "S"),
            (x + 1, y, "E", "W"),
            (x, y + 1, "S", "N"),
            (x - 1, y, "W", "E"),
        ]
        choices = [
            (nx, ny, wall, opposite)
            for nx, ny, wall, opposite in neighbors
            if 0 <= nx < columns and 0 <= ny < rows and (nx, ny) not in visited
        ]
        if not choices:
            stack.pop()
            continue
        nx, ny, wall, opposite = random.choice(choices)
        cells[y][x][wall] = False
        cells[ny][nx][opposite] = False
        visited.add((nx, ny))
        stack.append((nx, ny))
    return cells


def _maze_wall_rects(maze, origin_x, origin_y, cell_size):
    walls = []
    thickness = 8
    for row in range(len(maze)):
        for col in range(len(maze[row])):
            x = origin_x + col * cell_size
            y = origin_y + row * cell_size
            cell = maze[row][col]
            if cell["N"]:
                walls.append(pygame.Rect(x, y - thickness // 2, cell_size, thickness))
            if cell["W"]:
                walls.append(pygame.Rect(x - thickness // 2, y, thickness, cell_size))
            if row == len(maze) - 1 and cell["S"]:
                walls.append(pygame.Rect(x, y + cell_size - thickness // 2, cell_size, thickness))
            if col == len(maze[row]) - 1 and cell["E"]:
                walls.append(pygame.Rect(x + cell_size - thickness // 2, y, thickness, cell_size))
    return walls


def run_maze_escape(hand_controller=None):
    screen = _start_game(
        "미로 탈출",
        [
            ("목표", ["벽에 닿지 않고 출발점에서 도착점까지 이동"]),
            ("조작", [
                "POINT|Point: 손가락 커서로 통로 이동",
                "V|V: 메뉴로 나가기",
            ]),
        ],
        hand_controller,
    )
    if screen is None:
        return

    clock = pygame.time.Clock()
    font = get_font(24, bold=True)
    exit_gesture = VictoryExit()
    maze = _make_maze()
    cell_size = 48
    origin_x = 40
    origin_y = 80
    walls = _maze_wall_rects(maze, origin_x, origin_y, cell_size)
    board = pygame.Rect(origin_x, origin_y, cell_size * 15, cell_size * 9)
    start_cell = (7, 4)
    end_cell = (14, 8)
    player = [origin_x + (start_cell[0] + 0.5) * cell_size,
              origin_y + (start_cell[1] + 0.5) * cell_size]
    cursor = (0.5, 0.5)
    previous_hand = None
    level = 1
    won_until = 0
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        now = pygame.time.get_ticks()
        detected, hand_x, hand_y, gesture = _read_hand(hand_controller)
        if exit_gesture.update(detected, gesture, now):
            break
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        if detected and gesture == "Point":
            scaled_x = scale_hand_x(hand_x)
            if previous_hand is None:
                previous_hand = (scaled_x, hand_y)
            dx = (scaled_x - previous_hand[0]) * WIDTH
            dy = (hand_y - previous_hand[1]) * HEIGHT
            previous_hand = (scaled_x, hand_y)
            distance = max(abs(dx), abs(dy))
            steps = max(1, int(distance / 4))
            hit_wall = False
            for step in range(1, steps + 1):
                candidate = (
                    player[0] + dx * step / steps,
                    player[1] + dy * step / steps,
                )
                candidate_rect = pygame.Rect(
                    int(candidate[0]) - 7, int(candidate[1]) - 7, 14, 14
                )
                if not board.inflate(-8, -8).contains(candidate_rect):
                    hit_wall = True
                    break
                if any(candidate_rect.colliderect(wall) for wall in walls):
                    hit_wall = True
                    break
            if hit_wall:
                player = [
                    origin_x + (start_cell[0] + 0.5) * cell_size,
                    origin_y + (start_cell[1] + 0.5) * cell_size,
                ]
                previous_hand = None
            else:
                player[0] += dx
                player[1] += dy
            cursor = (int(player[0]), int(player[1]))
        else:
            previous_hand = None

        goal_center = (
            origin_x + (end_cell[0] + 0.5) * cell_size,
            origin_y + (end_cell[1] + 0.5) * cell_size,
        )
        if (player[0] - goal_center[0]) ** 2 + (player[1] - goal_center[1]) ** 2 < 24 ** 2:
            won_until = now + 1800
            level += 1
            maze = _make_maze()
            walls = _maze_wall_rects(maze, origin_x, origin_y, cell_size)
            player = [
                origin_x + (start_cell[0] + 0.5) * cell_size,
                origin_y + (start_cell[1] + 0.5) * cell_size,
            ]
            previous_hand = None

        screen.fill((30, 42, 48))
        _draw_header(screen, "미로 탈출  |  단계 {}".format(level), level - 1, font)
        for row in range(len(maze)):
            for col in range(len(maze[row])):
                x = origin_x + col * cell_size
                y = origin_y + row * cell_size
                cell = maze[row][col]
                if cell["N"]:
                    pygame.draw.line(screen, WHITE, (x, y), (x + cell_size, y), 5)
                if cell["W"]:
                    pygame.draw.line(screen, WHITE, (x, y), (x, y + cell_size), 5)
                if row == len(maze) - 1 and cell["S"]:
                    pygame.draw.line(screen, WHITE, (x, y + cell_size), (x + cell_size, y + cell_size), 5)
                if col == len(maze[row]) - 1 and cell["E"]:
                    pygame.draw.line(screen, WHITE, (x + cell_size, y), (x + cell_size, y + cell_size), 5)
        pygame.draw.circle(screen, GREEN, (int(origin_x + (start_cell[0] + .5) * cell_size),
                                          int(origin_y + (start_cell[1] + .5) * cell_size)), 10)
        pygame.draw.circle(screen, GOLD, (int(goal_center[0]), int(goal_center[1])), 13)
        pygame.draw.circle(screen, RED, (int(player[0]), int(player[1])), 11)
        pygame.draw.circle(screen, WHITE, (int(player[0]), int(player[1])), 11, 2)
        if now < won_until:
            text = font.render("탈출 성공!", True, GOLD)
            screen.blit(text, text.get_rect(center=(WIDTH // 2, 65)))
        _draw_camera_panel(screen, hand_controller, gesture)
        pygame.display.flip()


def run_ski_game(hand_controller=None):
    screen = _start_game(
        "스키 게임",
        [
            ("목표", ["S자 코스를 따라 내려오기"]),
            ("조작", [
                "POINT|Point: 손을 좌우로 움직여 방향 조절",
                "V|V: 메뉴로 나가기",
            ]),
        ],
        hand_controller,
    )
    if screen is None:
        return
    ski_background = pygame.transform.smoothscale(
        pygame.image.load(
            os.path.join(os.path.dirname(__file__), "assets", "ski_forest_bg.png")
        ).convert(),
        (WIDTH, HEIGHT),
    )
    skier_y = 465
    course_half_width = 290

    def course_center(y, distance):
        phase = (y - distance * 0.28) * 0.009
        start_phase = skier_y * 0.009
        return WIDTH / 2 + (math.sin(phase) - math.sin(start_phase)) * 155 + (
            math.sin(phase * 0.5) - math.sin(start_phase * 0.5)
        ) * 22

    def draw_countdown_scene():
        screen.blit(ski_background, (0, 0))
        centers = [
            course_center(y, 0)
            for y in range(0, HEIGHT + 8, 8)
        ]
        left = [(int(center - course_half_width), y) for center, y in zip(centers, range(0, HEIGHT + 8, 8))]
        right = [(int(center + course_half_width), y) for center, y in zip(centers, range(0, HEIGHT + 8, 8))]
        pygame.draw.polygon(screen, (250, 250, 245), left + list(reversed(right)))
        guides = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.lines(guides, (80, 155, 190, 80), False, left, 6)
        pygame.draw.lines(guides, (80, 155, 190, 80), False, right, 6)
        screen.blit(guides, (0, 0))
        center_x = round(course_center(skier_y, 0))
        pygame.draw.ellipse(screen, (40, 95, 140), (center_x - 20, skier_y - 25, 40, 58))
        pygame.draw.circle(screen, (245, 195, 155), (center_x, skier_y - 15), 13)
        pygame.draw.line(screen, (110, 75, 45), (center_x - 24, skier_y + 24),
                         (center_x + 24, skier_y + 24), 5)

    if not _countdown(screen, hand_controller, draw_countdown_scene):
        return

    clock = pygame.time.Clock()
    font = get_font(25, bold=True)
    exit_gesture = VictoryExit()
    restart_fist = _GestureHold("Fist", 500)
    travel = 0.0
    elapsed = 0.0
    player_x = WIDTH / 2
    cursor_smoother = _CursorSmoother((round(player_x), HEIGHT // 2))
    hand_anchor_x = None
    obstacles = []
    next_obstacle_distance = None
    game_over = False
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        now = pygame.time.get_ticks()
        detected, hand_x, _hand_y, gesture = _read_hand(hand_controller)
        if exit_gesture.update(detected, gesture, now):
            break
        restart_requested = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif game_over and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    restart_requested = True

        if game_over and restart_fist.update(
            gesture if detected else "None", now
        ):
            restart_requested = True
        elif not game_over:
            restart_fist.update("None", now)

        if restart_requested:
            travel = elapsed = 0.0
            course_half_width = 290
            player_x = WIDTH / 2
            cursor_smoother = _CursorSmoother((round(player_x), HEIGHT // 2))
            hand_anchor_x = None
            obstacles = []
            next_obstacle_distance = None
            game_over = False
            restart_fist = _GestureHold("Fist", 500)

        if not game_over:
            if detected and gesture == "Point":
                smoothed_hand_x = cursor_smoother.update(hand_x, 0.5, dt)[0]
                if hand_anchor_x is None:
                    hand_anchor_x = smoothed_hand_x
                hand_offset = smoothed_hand_x - hand_anchor_x
                dead_zone = 30
                if abs(hand_offset) > dead_zone:
                    steering = max(-1.0, min(1.0, hand_offset / 120))
                    player_x += steering * 300 * dt
                    player_x = max(24, min(WIDTH - 24, player_x))
            else:
                hand_anchor_x = None
            speed = _ski_speed(elapsed)
            travel += speed * dt
            elapsed += dt
            course_half_width = max(185, 290 - elapsed * 3.5)
            road_center = course_center(skier_y, travel)
            if abs(player_x - road_center) + 16 >= course_half_width:
                game_over = True
            if elapsed >= 60:
                if next_obstacle_distance is None:
                    next_obstacle_distance = travel + random.randint(700, 1000)
                if travel >= next_obstacle_distance:
                    obstacles.append((
                        next_obstacle_distance,
                        random.uniform(-course_half_width + 55, course_half_width - 55),
                        random.choice(("rock", "tree")),
                    ))
                    next_obstacle_distance += random.randint(700, 1100)

            visible_obstacles = []
            for obstacle_distance, obstacle_offset, obstacle_kind in obstacles:
                obstacle_y = skier_y - (obstacle_distance - travel) * 0.28
                if obstacle_y < HEIGHT + 40:
                    if abs(obstacle_y - skier_y) < 30:
                        obstacle_x = course_center(obstacle_y, travel) + obstacle_offset
                        if abs(player_x - obstacle_x) < 34:
                            game_over = True
                    if obstacle_y >= 60:
                        visible_obstacles.append((obstacle_distance, obstacle_offset, obstacle_kind))
            obstacles = visible_obstacles

        background_height = HEIGHT
        background_offset = round(travel * 0.45) % background_height
        for tile_y in (-background_offset, background_height - background_offset):
            screen.blit(ski_background, (0, tile_y))
        boundary_points_left = []
        boundary_points_right = []
        for y in range(0, HEIGHT + 8, 8):
            center = course_center(y, travel)
            boundary_points_left.append((int(center - course_half_width), y))
            boundary_points_right.append((int(center + course_half_width), y))
        pygame.draw.polygon(
            screen,
            (250, 250, 245),
            boundary_points_left + list(reversed(boundary_points_right)),
        )
        map_guides = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.lines(map_guides, (80, 155, 190, 80), False, boundary_points_left, 6)
        pygame.draw.lines(map_guides, (80, 155, 190, 80), False, boundary_points_right, 6)
        road_center = course_center(skier_y, travel)
        pygame.draw.line(
            map_guides,
            (170, 185, 185, 65),
            (int(road_center), 0),
            (int(road_center), HEIGHT),
            2,
        )
        screen.blit(map_guides, (0, 0))
        for obstacle_distance, obstacle_offset, obstacle_kind in obstacles:
            obstacle_y = round(skier_y - (obstacle_distance - travel) * 0.28)
            obstacle_x = round(course_center(obstacle_y, travel) + obstacle_offset)
            if obstacle_kind == "rock":
                pygame.draw.circle(screen, (81, 92, 101), (obstacle_x + 2, obstacle_y + 4), 20)
                pygame.draw.circle(screen, (126, 143, 151), (obstacle_x, obstacle_y), 18)
                pygame.draw.circle(screen, (173, 185, 186), (obstacle_x - 6, obstacle_y - 6), 6)
            else:
                pygame.draw.polygon(screen, (24, 86, 79), [
                    (obstacle_x, obstacle_y - 25),
                    (obstacle_x - 20, obstacle_y + 15),
                    (obstacle_x + 20, obstacle_y + 15),
                ])
                pygame.draw.polygon(screen, (39, 123, 103), [
                    (obstacle_x, obstacle_y - 13),
                    (obstacle_x - 23, obstacle_y + 25),
                    (obstacle_x + 23, obstacle_y + 25),
                ])
        pygame.draw.ellipse(
            screen,
            (40, 95, 140),
            (int(player_x) - 20, skier_y - 25, 40, 58),
        )
        pygame.draw.circle(screen, (245, 195, 155), (int(player_x), skier_y - 15), 13)
        pygame.draw.line(
            screen, (110, 75, 45), (int(player_x) - 24, skier_y + 24),
            (int(player_x) + 24, skier_y + 24), 5
        )
        speed_label = font.render(
            "속도 {:.1f}".format(_ski_speed(elapsed)), True, (30, 55, 75)
        )
        distance_label = font.render(
            "거리 {}m".format(int(travel)), True, (30, 55, 75)
        )
        screen.blit(speed_label, (24, 70))
        screen.blit(distance_label, (24, 105))
        if detected and gesture == "Point" and not game_over:
            cursor_x = player_x
            _draw_cursor(screen, (cursor_x, skier_y), (35, 105, 160), radius=30)
        if game_over:
            _draw_game_over(
                screen,
                int(travel),
                font,
                "코스를 벗어났습니다  ·  거리 점수",
                restart_prompt="ENTER / FIST (0.5초) 다시 시작",
            )
        _draw_camera_panel(screen, hand_controller, gesture)
        pygame.display.flip()
