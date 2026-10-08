import math
import os
import random
import sys
import pygame
from hand_input import scale_hand_x

# 상위 경로 모듈 검색 추가 (hand_controller 불러오기용)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

try:
    from hand_controller import HandController
except ImportError:
    HandController = None

# --- 레트로 픽셀 아트 팔레트 ---
COLOR_BG = (15, 20, 35)

COLOR_P_BODY = (200, 210, 225)
COLOR_P_WING = (80, 130, 200)
COLOR_P_COCKPIT = (100, 230, 255)
COLOR_P_DARK = (100, 110, 130)
COLOR_P_ENGINE = (255, 120, 30)

COLOR_DRONE = (100, 240, 120)
COLOR_SHIELD = (80, 180, 255)

COLOR_E1_BODY = (210, 50, 50)
COLOR_E1_WING = (140, 30, 30)

COLOR_E2_BODY = (240, 160, 30)
COLOR_E2_WING = (180, 100, 10)

COLOR_BOSS_BODY = (160, 40, 180)
COLOR_BOSS_WING = (100, 20, 120)
COLOR_BOSS_DARK = (60, 10, 80)

COLOR_BULLET = (255, 240, 100)
COLOR_E_BULLET = (255, 80, 80)
COLOR_EXPLOSION = (255, 140, 40)

COLOR_BOMB_ITEM = (255, 100, 30)
COLOR_SHIELD_ITEM = (50, 150, 255)
COLOR_DRONE_ITEM = (80, 220, 100)

WHITE = (255, 255, 255)
BLACK = (20, 20, 20)
GRAY = (140, 140, 150)
RED = (240, 70, 70)
GREEN = (70, 230, 120)
ORANGE = (255, 140, 0)
BLUE = (80, 180, 255)

WIDTH = 800
HEIGHT = 600
CAMERA_PANEL_WIDTH = 240
WINDOW_WIDTH = WIDTH + CAMERA_PANEL_WIDTH
CAMERA_PREVIEW_SIZE = (160, 120)
CAMERA_PREVIEW_X = WIDTH + (CAMERA_PANEL_WIDTH - CAMERA_PREVIEW_SIZE[0]) // 2
CAMERA_PREVIEW_Y = 230
FPS = 60
BOSS_TIME_LIMIT = 300  # 5분(300초) 버티면 보스 등장


class Player:
    def __init__(self):
        self.x = WIDTH // 2
        self.y = HEIGHT - 80
        self.speed = 7.5
        self.lives = 3
        self.bombs = 1
        self.shield_until = 0
        self.drone_until = 0

    def move(self, keys):
        if (keys[pygame.K_LEFT] or keys[pygame.K_a]) and self.x > 25:
            self.x -= self.speed
        if (keys[pygame.K_RIGHT] or keys[pygame.K_d]) and self.x < WIDTH - 25:
            self.x += self.speed

    def draw(self, screen, current_time):
        px, py = int(self.x), int(self.y)

        # 방어막
        if current_time < self.shield_until:
            pygame.draw.circle(screen, COLOR_SHIELD, (px, py), 34, 3)
            if (current_time // 80) % 2 == 0:
                pygame.draw.circle(screen, WHITE, (px, py), 36, 1)

        # 미니드론 2대
        if current_time < self.drone_until:
            for offset in [-38, 38]:
                dx, dy = px + offset, py + 10
                pygame.draw.circle(screen, COLOR_DRONE, (dx, dy), 8)
                pygame.draw.circle(screen, WHITE, (dx, dy), 4)

        # 엔진 부스터
        flame_len = random.randint(8, 14)
        pygame.draw.polygon(screen, COLOR_P_ENGINE, [(px - 4, py + 16), (px + 4, py + 16), (px, py + 16 + flame_len)])
        pygame.draw.polygon(screen, COLOR_BULLET, [(px - 2, py + 16), (px + 2, py + 16), (px, py + 14 + flame_len // 2)])

        # 메인 기체
        pygame.draw.polygon(screen, COLOR_P_WING, [(px, py - 10), (px - 24, py + 10), (px - 24, py + 16), (px, py + 8), (px + 24, py + 16), (px + 24, py + 10)])
        pygame.draw.polygon(screen, COLOR_P_DARK, [(px - 24, py + 14), (px - 24, py + 16), (px, py + 10), (px + 24, py + 16), (px + 24, py + 14), (px, py + 8)])
        pygame.draw.polygon(screen, COLOR_P_BODY, [(px, py - 24), (px - 6, py - 6), (px - 7, py + 16), (px + 7, py + 16), (px + 6, py - 6)])
        pygame.draw.polygon(screen, COLOR_P_DARK, [(px - 12, py + 12), (px + 12, py + 12), (px, py + 18)])
        pygame.draw.ellipse(screen, COLOR_P_COCKPIT, (px - 3, py - 14, 6, 12))

    def get_rect(self):
        return pygame.Rect(self.x - 20, self.y - 20, 40, 40)


class Bullet:
    def __init__(self, x, y, vx=0, vy=-12, is_enemy=False):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.is_enemy = is_enemy

    def update(self):
        self.x += self.vx
        self.y += self.vy

    def draw(self, screen):
        color = COLOR_E_BULLET if self.is_enemy else COLOR_BULLET
        if self.is_enemy:
            pygame.draw.rect(screen, color, (self.x - 3, self.y - 6, 6, 12))
        else:
            pygame.draw.rect(screen, COLOR_BULLET, (self.x - 4, self.y - 9, 8, 18))
            pygame.draw.rect(screen, WHITE, (self.x - 2, self.y - 7, 4, 14))

    def get_rect(self):
        if self.is_enemy:
            return pygame.Rect(self.x - 3, self.y - 6, 6, 12)
        return pygame.Rect(self.x - 4, self.y - 9, 8, 18)


class Enemy:
    def __init__(self, target_x=None, target_y=None, speed_bonus=0.0):
        self.is_diagonal = random.random() < 0.3 and target_x is not None

        if self.is_diagonal:
            spawn_side = random.choice(["top", "left", "right"])
            if spawn_side == "top":
                self.x = random.randint(40, WIDTH - 40)
                self.y = -30
            elif spawn_side == "left":
                self.x = -30
                self.y = random.randint(20, 200)
            else:
                self.x = WIDTH + 30
                self.y = random.randint(20, 200)

            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.hypot(dx, dy) or 1
            speed = random.uniform(4.5, 6.0) + speed_bonus
            self.vx = (dx / dist) * speed
            self.vy = (dy / dist) * speed
        else:
            self.x = random.randint(40, WIDTH - 40)
            self.y = random.randint(-100, -30)
            self.vx = 0
            self.vy = random.randint(3, 5) + speed_bonus

    def update(self):
        self.x += self.vx
        self.y += self.vy

    def draw(self, screen):
        ex, ey = int(self.x), int(self.y)
        if self.is_diagonal:
            pygame.draw.polygon(screen, COLOR_E2_WING, [(ex, ey + 18), (ex - 18, ey - 6), (ex + 18, ey - 6)])
            pygame.draw.polygon(screen, COLOR_E2_BODY, [(ex, ey + 22), (ex - 5, ey - 14), (ex + 5, ey - 14)])
        else:
            pygame.draw.polygon(screen, COLOR_E1_WING, [(ex, ey - 8), (ex - 20, ey - 12), (ex - 18, ey + 2), (ex, ey + 10), (ex + 18, ey + 2), (ex + 20, ey - 12)])
            pygame.draw.polygon(screen, COLOR_E1_BODY, [(ex, ey + 18), (ex - 6, ey - 16), (ex + 6, ey - 16)])

    def get_rect(self):
        return pygame.Rect(self.x - 18, self.y - 18, 36, 36)


class Boss:
    def __init__(self):
        self.x = WIDTH // 2
        self.y = -100
        self.target_y = 100
        self.max_hp = 250
        self.hp = 250
        self.dir = 1
        self.speed = 2.5
        self.pattern_timer = 0
        self.pattern_type = 0

    def update(self, current_time, enemy_bullets, player_x, player_y):
        if self.y < self.target_y:
            self.y += 2
            return

        self.x += self.speed * self.dir
        if self.x < 120 or self.x > WIDTH - 120:
            self.dir *= -1

        if current_time - self.pattern_timer > 1500:
            self.pattern_timer = current_time
            self.pattern_type = (self.pattern_type + 1) % 3

            if self.pattern_type == 0:
                dx = player_x - self.x
                dy = player_y - self.y
                dist = math.hypot(dx, dy) or 1
                base_vx, base_vy = (dx / dist) * 5.5, (dy / dist) * 5.5
                enemy_bullets.append(Bullet(self.x, self.y + 40, base_vx, base_vy, True))
                enemy_bullets.append(Bullet(self.x - 30, self.y + 30, base_vx - 1.2, base_vy, True))
                enemy_bullets.append(Bullet(self.x + 30, self.y + 30, base_vx + 1.2, base_vy, True))

            elif self.pattern_type == 1:
                for angle in range(-40, 41, 20):
                    rad = math.radians(angle + 90)
                    vx = math.cos(rad) * 5
                    vy = math.sin(rad) * 5
                    enemy_bullets.append(Bullet(self.x, self.y + 40, vx, vy, True))

            elif self.pattern_type == 2:
                for vx in [-4, -2, 0, 2, 4]:
                    enemy_bullets.append(Bullet(self.x, self.y + 40, vx, 5.5, True))

    def draw(self, screen):
        bx, by = int(self.x), int(self.y)
        pygame.draw.polygon(screen, COLOR_BOSS_WING, [(bx, by - 20), (bx - 90, by - 40), (bx - 80, by + 20), (bx, by + 40), (bx + 80, by + 20), (bx + 90, by - 40)])
        pygame.draw.polygon(screen, COLOR_BOSS_BODY, [(bx, by + 60), (bx - 30, by - 50), (bx + 30, by - 50)])
        pygame.draw.polygon(screen, COLOR_BOSS_DARK, [(bx - 15, by - 20), (bx + 15, by - 20), (bx, by + 30)])
        pygame.draw.ellipse(screen, RED, (bx - 12, by - 10, 24, 24))

    def get_rect(self):
        return pygame.Rect(self.x - 80, self.y - 40, 160, 90)


class Item:
    def __init__(self, x, y, item_type="BOMB"):
        self.x = x
        self.y = y
        self.speed = 2.0
        self.size = 32
        self.item_type = item_type

    def update(self):
        self.y += self.speed

    def draw(self, screen, font):
        rect = pygame.Rect(self.x - self.size // 2, self.y - self.size // 2, self.size, self.size)
        if self.item_type == "BOMB":
            color = COLOR_BOMB_ITEM
            label = "B"
        elif self.item_type == "SHIELD":
            color = COLOR_SHIELD_ITEM
            label = "S"
        else:
            color = COLOR_DRONE_ITEM
            label = "D"

        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, WHITE, rect, 2)
        txt = font.render(label, True, WHITE)
        screen.blit(txt, (self.x - txt.get_width() // 2, self.y - txt.get_height() // 2))

    def get_rect(self):
        return pygame.Rect(self.x - 20, self.y - 20, 40, 40)


class Particle:
    def __init__(self, x, y, is_bomb=False):
        self.x = x
        self.y = y
        speed_mult = 8 if is_bomb else 4
        self.vx = random.uniform(-speed_mult, speed_mult)
        self.vy = random.uniform(-speed_mult, speed_mult)
        self.life = random.randint(15, 30) if is_bomb else random.randint(10, 20)
        self.size = random.randint(4, 10) if is_bomb else random.randint(3, 6)
        self.color = ORANGE if is_bomb else COLOR_EXPLOSION

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, screen):
        if self.life > 0:
            pygame.draw.rect(screen, self.color, (self.x, self.y, self.size, self.size))


def run_game(hand_controller=None):
    own_controller = False
    if hand_controller is None and HandController is not None:
        try:
            hand_controller = HandController(cam_index=0)
            hand_controller.start()
            own_controller = True
        except Exception as e:
            print(f"[1945] HandController 생성 실패: {e}")

    screen = pygame.display.set_mode((WINDOW_WIDTH, HEIGHT))
    pygame.display.set_caption("Every One - 1945 Air Combat")
    clock = pygame.time.Clock()

    font_large = pygame.font.SysFont("malgungothic", 42, bold=True)
    font_medium = pygame.font.SysFont("malgungothic", 22, bold=True)
    font_small = pygame.font.SysFont("malgungothic", 16, bold=True)
    font_item = pygame.font.SysFont("malgungothic", 18, bold=True)

    player = Player()
    bullets = []
    enemy_bullets = []
    enemies = []
    particles = []
    items = []
    boss = None

    score = 0
    game_over = False
    game_clear = False
    last_shot_time = 0
    shot_delay = 200  # 자동 발사 간격
    bomb_flash_until = 0
    game_start_time = pygame.time.get_ticks()

    # 주먹 쿨다운 제어
    fist_armed = True
    fist_rearm_time = 0.5
    last_fist_time = 0

    def trigger_bomb():
        nonlocal bomb_flash_until, score, game_clear
        if player.bombs > 0:
            player.bombs -= 1
            bomb_flash_until = pygame.time.get_ticks() + 200

            for enemy in enemies:
                score += 100
                for _ in range(12):
                    particles.append(Particle(enemy.x, enemy.y, is_bomb=True))
            enemies.clear()
            enemy_bullets.clear()

            if boss:
                boss.hp -= 35
                if boss.hp <= 0:
                    game_clear = True

            for _ in range(50):
                particles.append(Particle(random.randint(0, WIDTH), random.randint(0, HEIGHT), is_bomb=True))

    running = True
    while running:
        clock.tick(FPS)
        current_time = pygame.time.get_ticks()

        elapsed_sec = (current_time - game_start_time) // 1000
        remaining_boss_time = max(0, BOSS_TIME_LIMIT - elapsed_sec)
        difficulty_level = 1 + (elapsed_sec // 20)
        spawn_rate = min(0.04 + (difficulty_level * 0.006), 0.12)
        speed_bonus = min((difficulty_level - 1) * 0.3, 3.0)

        if elapsed_sec >= BOSS_TIME_LIMIT and boss is None and not game_clear:
            boss = Boss()
            enemies.clear()

        # --- 모션 인식 연동 ---
        if hand_controller is not None:
            is_detected, hand_x, hand_y, gesture = hand_controller.get_state()
            if is_detected and not game_over and not game_clear:
                # 1) 손 위치에 따라 플레이어 X 위치 부드럽게 이동
                target_x = int(scale_hand_x(hand_x) * WIDTH)
                diff = target_x - player.x
                player.x += diff * 0.3
                player.x = max(25, min(WIDTH - 25, player.x))

                # 2) 주먹(Fist) 제스처로 폭탄 발사
                if gesture == "Fist" and fist_armed:
                    trigger_bomb()
                    fist_armed = False
                    last_fist_time = current_time
                elif gesture != "Fist" and (current_time - last_fist_time) > (fist_rearm_time * 1000):
                    fist_armed = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif (game_over or game_clear) and event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    player = Player()
                    bullets.clear()
                    enemy_bullets.clear()
                    enemies.clear()
                    particles.clear()
                    items.clear()
                    boss = None
                    score = 0
                    game_over = False
                    game_clear = False
                    game_start_time = pygame.time.get_ticks()
                elif not game_over and not game_clear and event.key == pygame.K_SPACE:
                    trigger_bomb()

        if not game_over and not game_clear:
            keys = pygame.key.get_pressed()
            player.move(keys)

            # 총알 자동 연사
            if current_time - last_shot_time > shot_delay:
                bullets.append(Bullet(player.x, player.y - 20))
                if current_time < player.drone_until:
                    bullets.append(Bullet(player.x - 38, player.y + 10))
                    bullets.append(Bullet(player.x + 38, player.y + 10))
                last_shot_time = current_time

            if boss is None:
                if random.random() < spawn_rate and len(enemies) < (8 + difficulty_level * 2):
                    enemies.append(Enemy(player.x, player.y, speed_bonus=speed_bonus))
            else:
                boss.update(current_time, enemy_bullets, player.x, player.y)

            for bullet in bullets[:]:
                bullet.update()
                if bullet.y < -20:
                    bullets.remove(bullet)

            player_rect = player.get_rect()
            for e_bullet in enemy_bullets[:]:
                e_bullet.update()
                if e_bullet.y > HEIGHT + 10 or e_bullet.x < -10 or e_bullet.x > WIDTH + 10:
                    enemy_bullets.remove(e_bullet)
                    continue

                if player_rect.colliderect(e_bullet.get_rect()):
                    enemy_bullets.remove(e_bullet)
                    if current_time >= player.shield_until:
                        player.lives -= 1
                        if player.lives <= 0:
                            game_over = True

            for item in items[:]:
                item.update()
                if item.y > HEIGHT + 30:
                    items.remove(item)
                    continue

                if player_rect.colliderect(item.get_rect()):
                    if item.item_type == "BOMB":
                        player.bombs = min(2, player.bombs + 1)
                    elif item.item_type == "SHIELD":
                        player.shield_until = current_time + 5000
                    elif item.item_type == "DRONE":
                        player.drone_until = current_time + 3000
                    items.remove(item)

            for enemy in enemies[:]:
                enemy.update()
                if enemy.y > HEIGHT + 40 or enemy.x < -50 or enemy.x > WIDTH + 50:
                    enemies.remove(enemy)
                    continue

                if player_rect.colliderect(enemy.get_rect()):
                    enemies.remove(enemy)
                    for _ in range(15):
                        particles.append(Particle(enemy.x, enemy.y))

                    if current_time >= player.shield_until:
                        player.lives -= 1
                        if player.lives <= 0:
                            game_over = True
                    else:
                        score += 100
                    continue

                for bullet in bullets[:]:
                    if bullet.get_rect().colliderect(enemy.get_rect()):
                        if bullet in bullets:
                            bullets.remove(bullet)
                        if enemy in enemies:
                            rand_val = random.random()
                            if rand_val < 0.12:
                                items.append(Item(enemy.x, enemy.y, "BOMB"))
                            elif rand_val < 0.24:
                                items.append(Item(enemy.x, enemy.y, "SHIELD"))
                            elif rand_val < 0.35:
                                items.append(Item(enemy.x, enemy.y, "DRONE"))

                            enemies.remove(enemy)
                        score += 100
                        for _ in range(10):
                            particles.append(Particle(enemy.x, enemy.y))
                        break

            if boss:
                boss_rect = boss.get_rect()
                for bullet in bullets[:]:
                    if bullet.get_rect().colliderect(boss_rect):
                        if bullet in bullets:
                            bullets.remove(bullet)
                        boss.hp -= 1
                        particles.append(Particle(bullet.x, bullet.y))
                        if boss.hp <= 0:
                            game_clear = True
                            score += 10000
                            for _ in range(60):
                                particles.append(Particle(boss.x + random.randint(-60, 60), boss.y + random.randint(-30, 30), is_bomb=True))

            for particle in particles[:]:
                particle.update()
                if particle.life <= 0:
                    particles.remove(particle)

        # --- 화면 그리기 ---
        screen.fill(COLOR_BG)

        for i in range(15):
            sx = (i * 57 + current_time // 10) % WIDTH
            sy = (i * 97 + current_time // 2) % HEIGHT
            pygame.draw.rect(screen, GRAY, (sx, sy, 2, 2))

        for item in items:
            item.draw(screen, font_item)

        for bullet in bullets:
            bullet.draw(screen)

        for e_bullet in enemy_bullets:
            e_bullet.draw(screen)

        for enemy in enemies:
            enemy.draw(screen)

        if boss:
            boss.draw(screen)

        for particle in particles:
            particle.draw(screen)

        if not game_over and not game_clear:
            player.draw(screen, current_time)

        if current_time < bomb_flash_until:
            flash_overlay = pygame.Surface((WIDTH, HEIGHT))
            flash_overlay.fill((255, 200, 100))
            flash_overlay.set_alpha(128)
            screen.blit(flash_overlay, (0, 0))

        # UI 표시
        score_txt = font_medium.render(f"SCORE: {score}", True, WHITE)
        lives_txt = font_medium.render(f"LIVES: {'★ ' * player.lives}", True, RED)
        bombs_txt = font_medium.render(f"BOMBS: {'💣 ' * player.bombs} (MAX 2)", True, ORANGE)

        if boss is None:
            timer_txt = font_medium.render(f"BOSS IN: {remaining_boss_time // 60:02d}:{remaining_boss_time % 60:02d}", True, GREEN)
            screen.blit(timer_txt, (20, 50))
        else:
            pygame.draw.rect(screen, RED, (WIDTH // 2 - 150, 15, 300, 16))
            pygame.draw.rect(screen, GREEN, (WIDTH // 2 - 150, 15, int(300 * (boss.hp / boss.max_hp)), 16))
            pygame.draw.rect(screen, WHITE, (WIDTH // 2 - 150, 15, 300, 16), 2)
            boss_lbl = font_small.render("BOSS HP", True, WHITE)
            screen.blit(boss_lbl, (WIDTH // 2 - boss_lbl.get_width() // 2, 34))

        screen.blit(score_txt, (20, 20))
        screen.blit(lives_txt, (WIDTH - 180, 20))
        screen.blit(bombs_txt, (WIDTH - 180, 50))

        if game_over or game_clear:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))
            screen.blit(overlay, (0, 0))

            main_msg = "★ VICTORY! ★" if game_clear else "GAME OVER"
            main_color = GREEN if game_clear else RED

            over_txt = font_large.render(main_msg, True, main_color)
            score_res = font_medium.render(f"FINAL SCORE: {score}", True, WHITE)
            restart_txt = font_small.render("ENTER / FIST : Restart | ESC : Menu", True, GRAY)

            screen.blit(over_txt, (WIDTH // 2 - over_txt.get_width() // 2, HEIGHT // 2 - 50))
            screen.blit(score_res, (WIDTH // 2 - score_res.get_width() // 2, HEIGHT // 2 + 10))
            screen.blit(restart_txt, (WIDTH // 2 - restart_txt.get_width() // 2, HEIGHT // 2 + 60))

        # PIP 웹캠 미리보기
        if hand_controller is not None:
            panel_title = font_small.render("WEBCAM", True, BLUE)
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
                preview = pygame.transform.smoothscale(preview, CAMERA_PREVIEW_SIZE)
                screen.blit(preview, (CAMERA_PREVIEW_X, CAMERA_PREVIEW_Y))

        pygame.draw.line(screen, WHITE, (WIDTH, 0), (WIDTH, HEIGHT), 2)
        pygame.display.flip()

    if own_controller and hand_controller is not None:
        hand_controller.stop()


if __name__ == "__main__":
    pygame.init()
    try:
        run_game()
    finally:
        pygame.quit()
