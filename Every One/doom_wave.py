import pygame
import random
import math
import os
import sys

# 상위 폴더(hand_controller.py 위치)를 모듈 검색 경로에 추가 (pong.py 와 동일)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

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

WHITE = (255, 255, 255)
RED = (230, 60, 60)
DARK_RED = (110, 25, 25)
GREEN = (70, 220, 110)
GRAY = (120, 120, 130)
YELLOW = (255, 220, 70)
ORANGE = (255, 150, 50)

# ------------------------------------------
# 시점 (플레이어는 움직일 수 없고 회전만 가능)
# ------------------------------------------

FOV = 70                 # 화면에 보이는 시야각(도)
MAX_TURN = 90            # 정면 기준 좌우 최대 회전각 → 총 180도
TURN_SPEED = 95.0        # 초당 회전 속도(도)

# ------------------------------------------
# 손동작 조작 (hand_controller)
# ------------------------------------------
# 손의 좌우 위치(0.0~1.0)를 시점 각도(-MAX_TURN~+MAX_TURN)에 그대로 대응시킨다.
# 카메라 가장자리까지 손을 뻗지 않아도 끝까지 돌 수 있도록 가운데 구간만 사용한다.
HAND_X_MIN = 0.15        # 이 위치 이하 → 왼쪽 끝
HAND_X_MAX = 0.85        # 이 위치 이상 → 오른쪽 끝
HAND_SMOOTH = 14.0       # 클수록 손을 빨리 따라감 (흔들림 ↔ 반응속도)
FIST_REARM_TIME = 0.12   # 주먹을 편 상태가 이 시간 이상 유지돼야 다음 발사 가능
GAME_OVER_HAND_COOLDOWN = 2.5

# ------------------------------------------
# 총
# ------------------------------------------

SHOT_COOLDOWN = 150      # ms
SHOT_DAMAGE = 1

# ------------------------------------------
# 적
# ------------------------------------------

MAX_ENEMIES = 10         # 동시에 존재할 수 있는 최대 적 수
ENEMY_TIME_LIMIT = 5.0   # 스폰 후 이 시간 안에 못 잡으면 라이프 감소
ENEMY_MIN_GAP = 1.1      # 적끼리 최소 간격(맵 칸 단위)
SPAWN_INTERVAL_START = 1.5   # 시작: 1.5초에 1마리
SPAWN_INTERVAL_END = 0.5     # 60초 직전: 1초에 2마리

# ------------------------------------------
# 게임
# ------------------------------------------

GAME_TIME = 60.0
START_LIVES = 5

# ------------------------------------------
# 렌더링
# ------------------------------------------

COLUMN_WIDTH = 2         # 레이 1개가 그리는 화면 픽셀 폭 (작을수록 선명, 느림)
TEX_SIZE = 64
SHADE_LEVELS = 12
MAX_SHADE_DIST = 14.0


# ==========================================
# 맵 : T자 복도
# ==========================================
#
#  '#' = 벽,  '.' = 바닥,  'P' = 플레이어 위치
#
#  가로 복도(위)가 좌우로 뻗어 있고,
#  세로 복도(아래)가 플레이어 정면으로 길게 이어진다.
#  플레이어는 교차점 뒤쪽 벽에 등을 대고 남쪽(아래)을 바라본다.

MAP_LAYOUT = [
    "#####################",
    "#.........P.........#",
    "#...................#",
    "#...................#",
    "#########...#########",
    "#########...#########",
    "#########...#########",
    "#########...#########",
    "#########...#########",
    "#########...#########",
    "#########...#########",
    "#########...#########",
    "#########...#########",
    "#########...#########",
    "#####################",
]

MAP_W = len(MAP_LAYOUT[0])
MAP_H = len(MAP_LAYOUT)


def _parse_map():
    grid = []
    start = (1.5, 1.5)

    for y, row in enumerate(MAP_LAYOUT):
        line = []
        for x, ch in enumerate(row):
            if ch == "P":
                start = (x + 0.5, y + 0.5)
            line.append(1 if ch == "#" else 0)
        grid.append(line)

    return grid, start


GRID, PLAYER_POS = _parse_map()

# 정면 = 남쪽(+y 방향). 각도는 라디안이 아닌 '도' 로 관리
BASE_ANGLE = 90.0


def is_wall(x, y):
    ix = int(x)
    iy = int(y)
    if ix < 0 or iy < 0 or ix >= MAP_W or iy >= MAP_H:
        return True
    return GRID[iy][ix] == 1


# ==========================================
# 레이캐스팅 수학 (pygame 과 무관)
# ==========================================

def camera_vectors(angle_deg):
    """시선 방향 벡터와 카메라 평면 벡터.
    평면은 화면 오른쪽 방향을 가리킨다."""
    a = math.radians(angle_deg)
    dir_x = math.cos(a)
    dir_y = math.sin(a)
    k = math.tan(math.radians(FOV / 2))
    plane_x = -dir_y * k
    plane_y = dir_x * k
    return dir_x, dir_y, plane_x, plane_y


def cast_ray(px, py, ray_x, ray_y):
    """DDA 레이캐스팅.
    반환: (수직거리, 벽 맞은 면(0=x면,1=y면), 텍스처 x좌표 0~1)"""
    map_x = int(px)
    map_y = int(py)

    delta_x = abs(1 / ray_x) if ray_x != 0 else 1e30
    delta_y = abs(1 / ray_y) if ray_y != 0 else 1e30

    if ray_x < 0:
        step_x = -1
        side_x = (px - map_x) * delta_x
    else:
        step_x = 1
        side_x = (map_x + 1.0 - px) * delta_x

    if ray_y < 0:
        step_y = -1
        side_y = (py - map_y) * delta_y
    else:
        step_y = 1
        side_y = (map_y + 1.0 - py) * delta_y

    side = 0

    for _ in range(64):
        if side_x < side_y:
            side_x += delta_x
            map_x += step_x
            side = 0
        else:
            side_y += delta_y
            map_y += step_y
            side = 1

        if (
            map_x < 0 or map_y < 0
            or map_x >= MAP_W or map_y >= MAP_H
            or GRID[map_y][map_x] == 1
        ):
            break

    if side == 0:
        dist = side_x - delta_x
        wall_x = py + dist * ray_y
    else:
        dist = side_y - delta_y
        wall_x = px + dist * ray_x

    wall_x -= math.floor(wall_x)

    # 텍스처가 좌우 반전되지 않도록
    if side == 0 and ray_x > 0:
        wall_x = 1 - wall_x
    if side == 1 and ray_y < 0:
        wall_x = 1 - wall_x

    return max(dist, 0.0001), side, wall_x


def project_point(px, py, angle_deg, wx, wy):
    """월드 좌표를 카메라 좌표로 변환.
    반환: (화면 x, 깊이). 깊이 <= 0 이면 뒤쪽."""
    dir_x, dir_y, plane_x, plane_y = camera_vectors(angle_deg)
    rx = wx - px
    ry = wy - py

    inv_det = 1.0 / (plane_x * dir_y - dir_x * plane_y)
    tx = inv_det * (dir_y * rx - dir_x * ry)
    ty = inv_det * (-plane_y * rx + plane_x * ry)

    if ty <= 0.0001:
        return None, ty

    screen_x = (WIDTH / 2) * (1 + tx / ty)
    return screen_x, ty


def has_line_of_sight(x0, y0, x1, y1):
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = max(2, int(dist * 20))
    for i in range(1, steps):
        t = i / steps
        if is_wall(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t):
            return False
    return True


def angle_diff(a, b):
    """a - b 를 -180~180 으로"""
    return (a - b + 180) % 360 - 180


def build_spawn_points():
    """플레이어가 (회전해서) 볼 수 있고, 벽에 가려지지 않는 바닥 위치들"""
    px, py = PLAYER_POS
    limit = MAX_TURN + FOV / 2 - 6
    points = []

    for y in range(MAP_H):
        for x in range(MAP_W):
            if GRID[y][x] == 1:
                continue

            for ox, oy in ((0.5, 0.5), (0.25, 0.5), (0.75, 0.5)):
                wx = x + ox
                wy = y + oy
                dist = math.hypot(wx - px, wy - py)

                if dist < 2.8 or dist > 12.5:
                    continue

                ang = math.degrees(math.atan2(wy - py, wx - px))
                if abs(angle_diff(ang, BASE_ANGLE)) > limit:
                    continue

                if not has_line_of_sight(px, py, wx, wy):
                    continue

                points.append((wx, wy))

    return points


SPAWN_POINTS = build_spawn_points()


# ==========================================
# 그래픽 리소스 (절차적으로 생성)
# ==========================================

def make_brick_texture():
    tex = pygame.Surface((TEX_SIZE, TEX_SIZE))
    tex.fill((70, 62, 56))

    rnd = random.Random(7)
    brick_h = 16
    brick_w = 32

    for row in range(TEX_SIZE // brick_h):
        offset = 0 if row % 2 == 0 else brick_w // 2
        for col in range(-1, TEX_SIZE // brick_w + 1):
            bx = col * brick_w + offset
            by = row * brick_h
            shade = rnd.randint(-14, 14)
            color = (
                max(0, min(255, 118 + shade)),
                max(0, min(255, 72 + shade // 2)),
                max(0, min(255, 56 + shade // 2)),
            )
            pygame.draw.rect(
                tex, color,
                (bx + 1, by + 1, brick_w - 2, brick_h - 2)
            )
            # 윗면 하이라이트
            pygame.draw.line(
                tex,
                (min(255, color[0] + 25),
                 min(255, color[1] + 18),
                 min(255, color[2] + 15)),
                (bx + 1, by + 1),
                (bx + brick_w - 2, by + 1)
            )

    # 얼룩
    for _ in range(120):
        x = rnd.randrange(TEX_SIZE)
        y = rnd.randrange(TEX_SIZE)
        c = tex.get_at((x, y))
        tex.set_at((x, y), (max(0, c.r - 30), max(0, c.g - 25), max(0, c.b - 20)))

    return tex


def make_shaded_textures(base):
    """[면][거리단계] → 어둡게 처리된 텍스처"""
    result = []
    for side in range(2):
        levels = []
        for lv in range(SHADE_LEVELS):
            t = base.copy()
            bright = 1.0 - lv / SHADE_LEVELS * 0.82
            if side == 1:
                bright *= 0.72
            v = int(255 * bright)
            t.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
            levels.append(t)
        result.append(levels)
    return result


def make_enemy_sprite(hit=False):
    s = pygame.Surface((TEX_SIZE, TEX_SIZE), pygame.SRCALPHA)

    body = (255, 255, 255) if hit else (175, 40, 35)
    dark = (255, 255, 255) if hit else (110, 22, 20)
    horn = (255, 255, 255) if hit else (225, 210, 170)

    # 다리
    pygame.draw.rect(s, dark, (20, 46, 9, 17))
    pygame.draw.rect(s, dark, (35, 46, 9, 17))
    # 몸통
    pygame.draw.ellipse(s, body, (12, 22, 40, 32))
    # 팔
    pygame.draw.ellipse(s, dark, (4, 26, 12, 22))
    pygame.draw.ellipse(s, dark, (48, 26, 12, 22))
    # 머리
    pygame.draw.ellipse(s, body, (19, 6, 26, 24))
    # 뿔
    pygame.draw.polygon(s, horn, [(21, 12), (14, 0), (26, 9)])
    pygame.draw.polygon(s, horn, [(43, 12), (50, 0), (38, 9)])

    if not hit:
        # 눈
        pygame.draw.rect(s, (255, 230, 60), (24, 14, 6, 4))
        pygame.draw.rect(s, (255, 230, 60), (34, 14, 6, 4))
        # 입
        pygame.draw.rect(s, (40, 5, 5), (26, 22, 12, 4))
        for i in range(3):
            pygame.draw.rect(s, (240, 240, 240), (27 + i * 4, 22, 2, 2))

    return s


def make_gradient(top, bottom, height):
    surf = pygame.Surface((WIDTH, height))
    for y in range(height):
        t = y / max(1, height - 1)
        c = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        pygame.draw.line(surf, c, (0, y), (WIDTH, y))
    return surf


# ==========================================
# 적
# ==========================================

class Enemy:

    def __init__(self, x, y, hp=1):
        self.x = x
        self.y = y
        self.hp = hp
        self.max_hp = hp
        self.alive = True
        self.hit_flash = 0.0
        self.age = 0.0           # 스폰 후 경과 시간
        self.time_left = ENEMY_TIME_LIMIT

    def update(self, dt):
        # 적은 절대 움직이지 않는다. 시간만 흐른다.
        self.age += dt
        self.time_left -= dt
        if self.hit_flash > 0:
            self.hit_flash -= dt


# ==========================================
# 렌더러
# ==========================================

class Renderer:

    def __init__(self):
        base = make_brick_texture()
        self.wall_tex = make_shaded_textures(base)
        self.enemy_img = make_enemy_sprite(False)
        self.enemy_hit_img = make_enemy_sprite(True)

        self.ceiling = make_gradient((26, 24, 30), (6, 6, 8), HEIGHT // 2)
        self.floor = make_gradient((8, 7, 7), (58, 50, 44), HEIGHT // 2)

        self.num_cols = WIDTH // COLUMN_WIDTH
        self.zbuffer = [0.0] * self.num_cols

        # 플레이어가 움직이지 않으므로 같은 각도면 벽 화면을 재사용
        self.cached_angle = None
        self.wall_layer = pygame.Surface((WIDTH, HEIGHT))

    # ---------------- 벽 ----------------

    def render_walls(self, angle):
        if self.cached_angle is not None and abs(self.cached_angle - angle) < 1e-6:
            return

        self.cached_angle = angle
        surf = self.wall_layer
        surf.blit(self.ceiling, (0, 0))
        surf.blit(self.floor, (0, HEIGHT // 2))

        px, py = PLAYER_POS
        dir_x, dir_y, plane_x, plane_y = camera_vectors(angle)
        half_h = HEIGHT / 2

        for i in range(self.num_cols):
            sx = i * COLUMN_WIDTH
            cam_x = 2 * (sx + COLUMN_WIDTH / 2) / WIDTH - 1
            ray_x = dir_x + plane_x * cam_x
            ray_y = dir_y + plane_y * cam_x

            dist, side, wall_x = cast_ray(px, py, ray_x, ray_y)
            self.zbuffer[i] = dist

            line_h = HEIGHT / dist
            shade = min(SHADE_LEVELS - 1, int(dist / MAX_SHADE_DIST * SHADE_LEVELS))
            tex = self.wall_tex[side][shade]
            tex_x = min(TEX_SIZE - 1, int(wall_x * TEX_SIZE))

            if line_h <= HEIGHT:
                h = max(1, int(line_h))
                column = tex.subsurface((tex_x, 0, 1, TEX_SIZE))
                column = pygame.transform.scale(column, (COLUMN_WIDTH, h))
                surf.blit(column, (sx, int(half_h - h / 2)))
            else:
                # 화면보다 큰 벽은 보이는 부분만 잘라서 확대
                visible = HEIGHT / line_h
                src_h = max(1, int(TEX_SIZE * visible))
                src_y = (TEX_SIZE - src_h) // 2
                column = tex.subsurface((tex_x, src_y, 1, src_h))
                column = pygame.transform.scale(column, (COLUMN_WIDTH, HEIGHT))
                surf.blit(column, (sx, 0))

    # ---------------- 적 ----------------

    def enemy_screen_info(self, enemy, angle):
        px, py = PLAYER_POS
        screen_x, depth = project_point(px, py, angle, enemy.x, enemy.y)
        if screen_x is None:
            return None

        size = int(HEIGHT / depth * 0.82)

        # 스폰 연출: 0.25초 동안 커지며 등장
        if enemy.age < 0.25:
            size = max(1, int(size * (0.3 + 0.7 * enemy.age / 0.25)))

        # 바닥에 발을 붙인다 (벽의 아래쪽과 같은 높이)
        floor_y = HEIGHT / 2 + (HEIGHT / depth) / 2
        top = int(floor_y - size)
        left = int(screen_x - size / 2)
        return screen_x, depth, size, left, top

    def render_enemies(self, target, enemies, angle, small_font):
        infos = []
        for e in enemies:
            if not e.alive:
                continue
            info = self.enemy_screen_info(e, angle)
            if info is not None:
                infos.append((e, info))

        # 먼 적부터 그린다
        infos.sort(key=lambda item: item[1][1], reverse=True)

        for enemy, (screen_x, depth, size, left, top) in infos:
            if left > WIDTH or left + size < 0:
                continue

            img = self.enemy_hit_img if enemy.hit_flash > 0 else self.enemy_img
            scaled = pygame.transform.scale(img, (size, size))

            # z-buffer 로 벽에 가려진 부분은 그리지 않음
            col_start = max(0, left // COLUMN_WIDTH)
            col_end = min(self.num_cols - 1, (left + size) // COLUMN_WIDTH)

            run_start = None
            for c in range(col_start, col_end + 2):
                visible = c <= col_end and depth < self.zbuffer[c]
                if visible and run_start is None:
                    run_start = c
                elif not visible and run_start is not None:
                    x0 = max(run_start * COLUMN_WIDTH, left)
                    x1 = min(c * COLUMN_WIDTH, left + size)
                    if x1 > x0:
                        target.blit(
                            scaled,
                            (x0, top),
                            (x0 - left, 0, x1 - x0, size)
                        )
                    run_start = None

            # 머리 위 타이머/체력 (몸 중앙이 보일 때만)
            center_col = int(screen_x) // COLUMN_WIDTH
            if 0 <= center_col < self.num_cols and depth < self.zbuffer[center_col]:
                self.draw_enemy_hud(target, enemy, screen_x, top, size, small_font)

    def draw_enemy_hud(self, target, enemy, screen_x, top, size, small_font):
        ratio = max(0.0, enemy.time_left / ENEMY_TIME_LIMIT)
        bar_w = max(30, int(size * 0.8))
        bar_h = 6
        bx = int(screen_x - bar_w / 2)
        by = top - 14

        if ratio > 0.6:
            color = GREEN
        elif ratio > 0.3:
            color = YELLOW
        else:
            color = RED

        pygame.draw.rect(target, (20, 20, 20), (bx - 1, by - 1, bar_w + 2, bar_h + 2))
        pygame.draw.rect(target, color, (bx, by, int(bar_w * ratio), bar_h))

        label = small_font.render("{:.1f}".format(max(0.0, enemy.time_left)), True, color)
        target.blit(label, (int(screen_x - label.get_width() / 2), by - 20))

        if enemy.max_hp > 1:
            hp_w = int(bar_w * enemy.hp / enemy.max_hp)
            pygame.draw.rect(target, DARK_RED, (bx, by + bar_h + 3, bar_w, 4))
            pygame.draw.rect(target, (90, 160, 255), (bx, by + bar_h + 3, hp_w, 4))


# ==========================================
# 리볼버 (뒤에서 본 1인칭 조준 구도)
# ==========================================
#
#  총구가 화면 중앙(조준점) 쪽을 정면으로 향하고,
#  총열 위의 가늠쇠와 프레임 위의 가늠자가 보이는 구도.
#  화면 아래쪽 영역(GUN_AREA)을 2배 해상도로 그린 뒤 축소한다.

GUN_AREA = (200, 300, 400, 300)      # 화면에서 총이 그려지는 영역 (x, y, w, h)
_GS = 2                              # 내부 그리기 배율
_VP = (200 * _GS, 0)                 # 소실점(=조준점 바로 아래), 로컬 좌표

STEEL = (58, 62, 74)
STEEL_DARK = (26, 28, 35)
STEEL_MID = (86, 92, 108)
STEEL_HI = (150, 158, 178)
STEEL_SHINE = (210, 216, 232)
WOOD = (122, 64, 32)
WOOD_DARK = (78, 38, 18)
SKIN = (196, 142, 108)
SKIN_DARK = (146, 98, 72)
SKIN_HI = (224, 176, 142)
SLEEVE = (46, 50, 40)
SLEEVE_DARK = (28, 31, 24)


def _persp(half_ratio, y, dx=0.0):
    """소실점에서 뻗어 나온 직선 위의 점 (원근감)"""
    return (_VP[0] + dx + half_ratio * (y - _VP[1]), y)


def _band(half_ratio_l, half_ratio_r, y0, y1):
    """소실점으로 모이는 띠(사다리꼴)"""
    return [_persp(half_ratio_l, y0), _persp(half_ratio_r, y0),
            _persp(half_ratio_r, y1), _persp(half_ratio_l, y1)]


def _capsule(s, color, a, b, width):
    pygame.draw.line(s, color, a, b, width)
    pygame.draw.circle(s, color, (int(a[0]), int(a[1])), width // 2)
    pygame.draw.circle(s, color, (int(b[0]), int(b[1])), width // 2)


def _draw_revolver_rear(hammer_cocked=True, cylinder_phase=0):
    w = GUN_AREA[2] * _GS
    h = GUN_AREA[3] * _GS
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    d = pygame.draw
    cx = _VP[0]

    # ---------- 실린더 (뒤에서 본 둥근 드럼) ----------
    far_c, far_rx, far_ry = 322, 112, 34      # 실린더 앞쪽 끝(먼 쪽)
    near_c, near_rx, near_ry = 432, 152, 84   # 실린더 뒤쪽 끝(가까운 쪽)

    def ring(t, scale=1.0):
        """t: 각도(도). 먼 원과 가까운 원 위의 대응점"""
        r = math.radians(t)
        fa = (cx + far_rx * scale * math.cos(r), far_c + far_ry * scale * math.sin(r))
        na = (cx + near_rx * scale * math.cos(r), near_c + near_ry * scale * math.sin(r))
        return fa, na

    # 외곽(어두운 테두리) : 두 타원 + 옆면을 잇는 다각형
    d.ellipse(s, STEEL_DARK, (cx - far_rx - 4, far_c - far_ry - 4, 2 * far_rx + 8, 2 * far_ry + 8))
    d.ellipse(s, STEEL_DARK, (cx - near_rx - 4, near_c - near_ry - 4, 2 * near_rx + 8, 2 * near_ry + 8))
    d.polygon(s, STEEL_DARK, [(cx - far_rx - 4, far_c), (cx + far_rx + 4, far_c),
                              (cx + near_rx + 4, near_c), (cx - near_rx - 4, near_c)])
    # 둥근 면의 음영 : 바깥 → 안쪽으로 밝아지는 층
    for scale, color, lift in ((1.0, STEEL, 0), (0.80, STEEL_MID, 6), (0.52, STEEL_HI, 12)):
        d.ellipse(s, color, (cx - far_rx * scale, far_c - far_ry * scale - lift,
                             2 * far_rx * scale, 2 * far_ry * scale))
        d.ellipse(s, color, (cx - near_rx * scale, near_c - near_ry * scale - lift,
                             2 * near_rx * scale, 2 * near_ry * scale))
        d.polygon(s, color, [(cx - far_rx * scale, far_c - lift), (cx + far_rx * scale, far_c - lift),
                             (cx + near_rx * scale, near_c - lift), (cx - near_rx * scale, near_c - lift)])
    # 플루트(홈) : 드럼 윗면을 따라 앞뒤로 길게 파인 홈
    shift = (cylinder_phase % 2) * 15
    for t in range(150, 400, 30):
        ang = t + shift
        if not (188 < ang % 360 < 352) and not (ang % 360 < 8):
            pass
        sn = math.sin(math.radians(ang))
        if sn > 0.15:          # 드럼 아래쪽(안 보이는 면)은 생략
            continue
        fa, na = ring(ang, 0.9)
        _capsule(s, STEEL_DARK, fa, na, 14)
        fb, nb = ring(ang - 5, 0.9)
        d.line(s, STEEL_SHINE if sn < -0.6 else STEEL_HI, fb, nb, 2)
    # 실린더 앞쪽 틈 (총열과의 경계)
    d.ellipse(s, STEEL_DARK, (cx - far_rx, far_c - far_ry, 2 * far_rx, 2 * far_ry), 3)

    # ---------- 총열 ----------
    bar_far, bar_near = 96, 330
    # 아래쪽 이젝터 러그 (양옆으로 살짝 보임)
    d.polygon(s, STEEL_DARK, _band(-0.21, 0.21, bar_far + 10, bar_near))
    # 총열 몸체
    d.polygon(s, STEEL, _band(-0.18, 0.18, bar_far, bar_near))
    # 옆면 그림자
    d.polygon(s, STEEL_DARK, _band(-0.18, -0.13, bar_far, bar_near))
    d.polygon(s, STEEL_DARK, _band(0.13, 0.18, bar_far, bar_near))
    # 윗면 통풍 리브
    d.polygon(s, STEEL_MID, _band(-0.085, 0.085, bar_far, bar_near))
    d.polygon(s, STEEL_HI, _band(-0.03, 0.03, bar_far, bar_near))
    # 리브의 미끄럼 방지 홈 (멀수록 촘촘)
    y = bar_far + 8
    gap = 6.0
    while y < bar_near - 6:
        d.line(s, STEEL_DARK, _persp(-0.08, y), _persp(0.08, y), 2)
        y += gap
        gap *= 1.16
    # 총구 끝면
    d.polygon(s, STEEL_HI, _band(-0.20, 0.20, bar_far - 4, bar_far + 4))

    # ---------- 가늠쇠 (총열 끝, 조준점 바로 아래) ----------
    fs_top = 54
    d.polygon(s, STEEL_DARK, [(cx - 9, bar_far + 2), (cx - 7, fs_top),
                              (cx + 7, fs_top), (cx + 9, bar_far + 2)])
    d.rect(s, (255, 90, 40), (cx - 5, fs_top + 2, 10, 10), border_radius=3)
    d.rect(s, (255, 190, 120), (cx - 2, fs_top + 4, 4, 4))

    # ---------- 프레임 / 톱스트랩 ----------
    top_far, top_near = 318, 470
    d.polygon(s, STEEL_DARK, _band(-0.19, 0.19, top_far, top_near))
    d.polygon(s, STEEL, _band(-0.15, 0.15, top_far + 2, top_near))
    d.polygon(s, STEEL_MID, _band(-0.06, 0.06, top_far + 2, top_near - 40))
    d.line(s, STEEL_SHINE, _persp(-0.02, top_far + 6), _persp(-0.02, top_near - 50), 3)

    # ---------- 가늠자 (U자 홈) ----------
    rs_y = 400
    rs_h = 26
    left_ear = [_persp(-0.17, rs_y), _persp(-0.03, rs_y),
                _persp(-0.03, rs_y + rs_h), _persp(-0.17, rs_y + rs_h)]
    right_ear = [_persp(0.03, rs_y), _persp(0.17, rs_y),
                 _persp(0.17, rs_y + rs_h), _persp(0.03, rs_y + rs_h)]
    left_ear[0] = (left_ear[0][0], left_ear[0][1] - 10)
    left_ear[1] = (left_ear[1][0], left_ear[1][1] - 10)
    right_ear[0] = (right_ear[0][0], right_ear[0][1] - 10)
    right_ear[1] = (right_ear[1][0], right_ear[1][1] - 10)
    d.polygon(s, STEEL_DARK, left_ear)
    d.polygon(s, STEEL_DARK, right_ear)
    d.line(s, STEEL_HI, left_ear[0], left_ear[1], 2)
    d.line(s, STEEL_HI, right_ear[0], right_ear[1], 2)
    # 가늠자 흰 점
    d.circle(s, (235, 235, 235), (int(cx - 0.10 * rs_y), rs_y + 4), 4)
    d.circle(s, (235, 235, 235), (int(cx + 0.10 * rs_y), rs_y + 4), 4)

    # ---------- 손 (오른손으로 손잡이를 감싼 모습) ----------
    # 소매
    d.polygon(s, SLEEVE_DARK, [(cx - 170, h), (cx - 126, 566), (cx + 136, 566), (cx + 190, h)])
    d.polygon(s, SLEEVE, [(cx - 160, h), (cx - 118, 574), (cx + 128, 574), (cx + 178, h)])
    # 손잡이 윗부분 (해머 바로 아래)
    d.polygon(s, WOOD_DARK, [(cx - 34, 462), (cx + 34, 462), (cx + 40, 500), (cx - 40, 500)])
    d.polygon(s, WOOD, [(cx - 28, 466), (cx + 28, 466), (cx + 32, 496), (cx - 32, 496)])
    # 손등 (손잡이 오른쪽을 감싸며 아래로)
    back = [(cx - 104, 596), (cx - 92, 520), (cx - 44, 488), (cx + 40, 488),
            (cx + 104, 500), (cx + 142, 534), (cx + 146, 584), (cx + 120, 600)]
    d.polygon(s, SKIN_DARK, back)
    d.polygon(s, SKIN, [(cx - 96, 594), (cx - 86, 524), (cx - 42, 496), (cx + 38, 496),
                        (cx + 100, 507), (cx + 134, 538), (cx + 138, 582), (cx + 116, 594)])
    # 손등 음영과 관절 라인 (오른쪽 가장자리에서 손가락이 앞으로 감겨 들어감)
    d.polygon(s, SKIN_DARK, [(cx + 100, 507), (cx + 134, 538), (cx + 138, 582),
                             (cx + 120, 588), (cx + 116, 546)])
    for i in range(3):
        ky = 528 + i * 18
        d.arc(s, SKIN_DARK, (cx + 108, ky - 10, 36, 26), math.radians(-80), math.radians(80), 3)
    d.line(s, SKIN_HI, (cx - 60, 520), (cx + 60, 508), 5)
    d.line(s, SKIN_HI, (cx + 70, 512), (cx + 104, 522), 3)
    # 엄지 : 프레임 왼쪽 옆을 따라 앞(조준 방향)으로 뻗음
    _capsule(s, SKIN_DARK, (cx - 112, 572), (cx - 78, 470), 42)
    _capsule(s, SKIN, (cx - 110, 570), (cx - 79, 472), 34)
    d.line(s, SKIN_HI, (cx - 112, 548), (cx - 90, 482), 3)
    # 엄지손톱
    d.ellipse(s, SKIN_DARK, (cx - 92, 456, 26, 24))
    d.ellipse(s, (232, 196, 170), (cx - 89, 458, 20, 18))
    # 엄지 마디 주름
    d.arc(s, SKIN_DARK, (cx - 112, 512, 30, 16), math.radians(200), math.radians(340), 2)

    # ---------- 공이치기(해머) ----------
    if hammer_cocked:
        # 젖혀져서 카메라 쪽으로 튀어나온 스퍼
        d.polygon(s, STEEL_DARK, [(cx - 22, 440), (cx + 22, 440),
                                  (cx + 40, 520), (cx - 40, 520)])
        d.rect(s, STEEL_DARK, (cx - 46, 506, 92, 42), border_radius=12)
        d.rect(s, STEEL_MID, (cx - 40, 510, 80, 32), border_radius=10)
        for i in range(6):
            x = cx - 32 + i * 13
            d.line(s, STEEL_DARK, (x, 512), (x + 6, 540), 2)
        d.line(s, STEEL_HI, (cx - 34, 512), (cx + 34, 512), 2)
    else:
        # 내려간 해머: 프레임 안으로 들어가 작게 보임
        d.polygon(s, STEEL_DARK, [(cx - 18, 440), (cx + 18, 440),
                                  (cx + 24, 478), (cx - 24, 478)])
        d.rect(s, STEEL_MID, (cx - 22, 466, 44, 16), border_radius=6)

    return s


def _make_flash(size):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    rnd = random.Random(3)
    layers = [((255, 140, 30, 150), 1.0), ((255, 210, 80, 220), 0.7),
              ((255, 250, 210, 255), 0.38)]
    for color, k in layers:
        pts = []
        spikes = 9
        for i in range(spikes * 2):
            ang = math.pi * i / spikes
            r = (c * k) if i % 2 == 0 else (c * k * rnd.uniform(0.35, 0.5))
            pts.append((c + math.cos(ang) * r, c + math.sin(ang) * r))
        pygame.draw.polygon(s, color, pts)
    pygame.draw.circle(s, (255, 255, 255, 255), (c, c), max(2, size // 10))
    return s


class Revolver:

    def __init__(self):
        size = (GUN_AREA[2], GUN_AREA[3])
        self.frames = {}
        for cocked in (True, False):
            for phase in (0, 1):
                big = _draw_revolver_rear(cocked, phase)
                self.frames[(cocked, phase)] = pygame.transform.smoothscale(big, size)

        # 총구 위치 (화면 좌표) : 총열 끝, 가늠쇠 바로 아래
        self.muzzle = (GUN_AREA[0] + _VP[0] / _GS, GUN_AREA[1] + 100 / _GS)

        self.flash_base = _make_flash(150)
        self.shots = 0
        self.kick = 0.0          # 반동 (1 → 0 으로 감소)
        self.flash_time = 0.0
        self.flash_angle = 0
        self.sway_t = 0.0

    def fire(self):
        self.shots += 1
        self.kick = 1.0
        self.flash_time = 0.07
        self.flash_angle = random.randint(0, 359)

    def update(self, dt, turning):
        self.kick = max(0.0, self.kick - dt * 6.5)
        self.flash_time = max(0.0, self.flash_time - dt)
        self.sway_t += dt * (6.0 if turning else 1.6)

    def draw(self, surf):
        k = self.kick
        kick_curve = math.sin(min(1.0, k) * math.pi / 2)
        sway_x = math.sin(self.sway_t) * 4
        sway_y = abs(math.cos(self.sway_t)) * 3

        # 총구 화염은 총보다 멀리 있으므로 먼저 그린다 (총에 일부 가려짐)
        if self.flash_time > 0:
            scale = 0.9 + self.flash_time / 0.07 * 0.5
            flash = pygame.transform.rotozoom(self.flash_base, self.flash_angle, scale)
            fx = self.muzzle[0] + sway_x
            fy = self.muzzle[1] + sway_y - 6
            surf.blit(flash, (int(fx - flash.get_width() / 2),
                              int(fy - flash.get_height() / 2)))

        cocked = self.kick < 0.55
        img = self.frames[(cocked, self.shots % 2)]

        # 반동: 총이 몸 쪽으로 밀려와 커지고, 총구가 살짝 들린 뒤 내려온다
        x = GUN_AREA[0] + sway_x
        y = GUN_AREA[1] + sway_y
        if k > 0:
            zoom = 1.0 + kick_curve * 0.07
            img = pygame.transform.rotozoom(img, kick_curve * 2.5, zoom)
            x -= (img.get_width() - GUN_AREA[2]) / 2
            y -= (img.get_height() - GUN_AREA[3]) / 2 - kick_curve * 22
        surf.blit(img, (int(x), int(y)))


# ==========================================
# 게임
# ==========================================

def run_game(hand_controller=None):

    # 메뉴에서 컨트롤러를 받지 못했으면 직접 만든다 (pong.py 와 동일)
    own_controller = False
    if hand_controller is None and HandController is not None:
        try:
            hand_controller = HandController(cam_index=0)
            hand_controller.start()
            own_controller = True
        except Exception as e:
            print(f"[Doom Wave] HandController 생성 실패: {e}")

    screen = pygame.display.set_mode((WINDOW_WIDTH, HEIGHT))
    pygame.display.set_caption("DOOM WAVE - T CORRIDOR")

    clock = pygame.time.Clock()

    font = pygame.font.Font(None, 34)
    big_font = pygame.font.Font(None, 72)
    small_font = pygame.font.Font(None, 25)

    renderer = Renderer()
    gun = Revolver()
    fire_light = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    fire_light.fill((255, 190, 90, 28))
    frame = pygame.Surface((WIDTH, HEIGHT))

    state = {}

    def reset():
        state["turn"] = 0.0                 # 정면 기준 회전 (-MAX_TURN ~ MAX_TURN)
        state["score"] = 0
        state["kills"] = 0
        state["lives"] = START_LIVES
        state["time"] = GAME_TIME
        state["enemies"] = []
        state["spawn_timer"] = SPAWN_INTERVAL_START
        state["last_shot"] = -SHOT_COOLDOWN
        state["muzzle"] = 0.0
        state["damage_flash"] = 0.0
        state["shake"] = 0.0
        state["over"] = False
        state["result"] = ""
        state["over_time"] = 0.0

    reset()

    # 손동작 상태
    hand = {
        "detected": False,
        "gesture": "None",
        "fist_armed": False,     # 시작할 때 쥐고 있던 주먹으로는 바로 쏘지 않음
        "open_time": 0.0,        # 주먹을 편 상태로 지난 시간
    }

    def hand_fist_pressed(dt):
        """주먹을 '새로 쥔 순간'에만 True (계속 쥐고 있으면 연사되지 않음)"""
        if hand_controller is None or not hand["detected"]:
            return False
        if hand["gesture"] == "Fist":
            if hand["fist_armed"]:
                hand["fist_armed"] = False
                hand["open_time"] = 0.0
                return True
            return False
        hand["open_time"] += dt
        if hand["open_time"] >= FIST_REARM_TIME:
            hand["fist_armed"] = True
        return False

    def current_angle():
        return BASE_ANGLE + state["turn"]

    # --------------------------------------
    # 적 생성
    # --------------------------------------

    def spawn_enemy():
        alive = [e for e in state["enemies"] if e.alive]
        if len(alive) >= MAX_ENEMIES:
            return

        candidates = [
            p for p in SPAWN_POINTS
            if all(math.hypot(p[0] - e.x, p[1] - e.y) >= ENEMY_MIN_GAP for e in alive)
        ]
        if not candidates:
            return

        x, y = random.choice(candidates)

        # 시간이 지날수록 단단한 적 등장
        elapsed = GAME_TIME - state["time"]
        hp = 1
        if elapsed >= 20 and random.random() < 0.18:
            hp = 2
        if elapsed >= 40 and random.random() < 0.15:
            hp = 3

        state["enemies"].append(Enemy(x, y, hp))

    # --------------------------------------
    # 총 발사 (화면 중앙 조준점 히트스캔)
    # --------------------------------------

    def shoot():
        now = pygame.time.get_ticks()
        if now - state["last_shot"] < SHOT_COOLDOWN:
            return

        state["last_shot"] = now
        state["muzzle"] = 0.08
        gun.fire()

        angle = current_angle()
        center_col = (WIDTH // 2) // COLUMN_WIDTH
        wall_depth = renderer.zbuffer[center_col]

        target = None
        best = float("inf")

        for e in state["enemies"]:
            if not e.alive:
                continue
            info = renderer.enemy_screen_info(e, angle)
            if info is None:
                continue
            screen_x, depth, size, left, top = info

            if depth >= wall_depth:
                continue     # 벽 뒤
            if abs(screen_x - WIDTH / 2) > size * 0.32:
                continue     # 조준점에서 벗어남

            if depth < best:
                best = depth
                target = e

        if target is not None:
            target.hp -= SHOT_DAMAGE
            target.hit_flash = 0.1
            if target.hp <= 0:
                target.alive = False
                state["kills"] += 1
                # 빨리 잡을수록 보너스
                state["score"] += 100 + int(target.time_left * 20)

    # ======================================
    # 게임 루프
    # ======================================

    running = True

    while running:

        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)

        # ----------------------------------
        # 이벤트
        # ----------------------------------

        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if state["over"]:
                        if event.key == pygame.K_RETURN:
                            reset()
                    else:
                        shoot()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and not state["over"]:
                    shoot()

        # ----------------------------------
        # 손동작 읽기
        # ----------------------------------

        hand_x = 0.5
        hand_input_allowed = (
            not state["over"]
            or state["over_time"] >= GAME_OVER_HAND_COOLDOWN
        )
        if hand_controller is not None and hand_input_allowed:
            detected, hand_x, _hand_y, gesture = hand_controller.get_state()
            hand["detected"] = detected
            hand["gesture"] = gesture if detected else "None"
        elif state["over"]:
            hand["detected"] = False
            hand["gesture"] = "None"
            hand["fist_armed"] = False
            hand["open_time"] = 0.0

        fist_now = hand_fist_pressed(dt)

        # ----------------------------------
        # 진행
        # ----------------------------------

        prev_turn = state["turn"]

        if not state["over"]:

            state["time"] -= dt

            keys = pygame.key.get_pressed()
            key_turning = keys[pygame.K_LEFT] or keys[pygame.K_RIGHT]
            if keys[pygame.K_LEFT]:
                state["turn"] -= TURN_SPEED * dt
            if keys[pygame.K_RIGHT]:
                state["turn"] += TURN_SPEED * dt

            # 손 위치로 시점 회전 (키보드를 누르는 동안은 키보드 우선)
            # 주먹을 쥔 동안에는 조준을 고정 → 쥐는 동작 때문에 조준이 흔들리지 않음
            if (
                hand_controller is not None
                and hand["detected"]
                and not key_turning
                and hand["gesture"] != "Fist"
            ):
                t = (hand_x - HAND_X_MIN) / (HAND_X_MAX - HAND_X_MIN)
                t = max(0.0, min(1.0, t))
                target_turn = (t * 2 - 1) * MAX_TURN
                follow = 1 - math.exp(-HAND_SMOOTH * dt)
                state["turn"] += (target_turn - state["turn"]) * follow

            # 주먹 쥐기 → 발사
            if fist_now:
                shoot()

            # 시야 회전 제한 (MAX_TURN * 2 도)
            state["turn"] = max(-MAX_TURN, min(MAX_TURN, state["turn"]))

            # 스폰: 1.5초에 1마리 → 60초 직전 1초에 2마리 (경과 시간에 비례해 빨라짐)
            state["spawn_timer"] -= dt
            while state["spawn_timer"] <= 0:
                spawn_enemy()
                progress = min(1.0, (GAME_TIME - max(0.0, state["time"])) / GAME_TIME)
                interval = SPAWN_INTERVAL_START + (
                    SPAWN_INTERVAL_END - SPAWN_INTERVAL_START
                ) * progress
                state["spawn_timer"] += interval

            # 적 타이머
            for e in state["enemies"]:
                if not e.alive:
                    continue
                e.update(dt)
                if e.time_left <= 0:
                    # 시간 안에 못 잡음 → 적의 공격, 라이프 감소
                    e.alive = False
                    state["lives"] -= 1
                    state["damage_flash"] = 0.35
                    state["shake"] = 0.25

            state["enemies"] = [e for e in state["enemies"] if e.alive]

            if state["lives"] <= 0:
                state["lives"] = 0
                state["over"] = True
                state["result"] = "GAME OVER"
            elif state["time"] <= 0:
                state["time"] = 0
                state["over"] = True
                state["result"] = "SURVIVED!"

        else:
            # 게임 종료 후 2.5초간 손 입력을 막고, 이후 주먹으로 다시 시작
            state["over_time"] += dt
            if fist_now and state["over_time"] >= GAME_OVER_HAND_COOLDOWN:
                reset()

        if state["muzzle"] > 0:
            state["muzzle"] -= dt

        # 시점이 움직이는 중이면 총이 조금 더 흔들린다
        turning = abs(state["turn"] - prev_turn) > 0.05
        gun.update(dt, turning)
        if state["damage_flash"] > 0:
            state["damage_flash"] -= dt
        if state["shake"] > 0:
            state["shake"] -= dt

        # ==================================
        # 화면
        # ==================================

        angle = current_angle()

        renderer.render_walls(angle)
        frame.blit(renderer.wall_layer, (0, 0))
        renderer.render_enemies(frame, state["enemies"], angle, small_font)

        draw_offscreen_indicators(frame, state["enemies"], angle)
        draw_crosshair(frame)
        if gun.flash_time > 0:
            frame.blit(fire_light, (0, 0))
        gun.draw(frame)
        draw_turn_meter(frame, state["turn"], small_font)
        draw_hud(frame, state, font, small_font, hand_controller is not None)
        if state["damage_flash"] > 0:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = int(150 * state["damage_flash"] / 0.35)
            overlay.fill((200, 0, 0, max(0, alpha)))
            frame.blit(overlay, (0, 0))

        if state["over"]:
            draw_game_over(frame, state, font, big_font, small_font)

        # 피격 시 화면 흔들림
        ox = oy = 0
        if state["shake"] > 0:
            ox = random.randint(-8, 8)
            oy = random.randint(-8, 8)
        screen.fill((0, 0, 0))
        screen.blit(frame, (ox, oy))
        pygame.draw.line(screen, WHITE, (WIDTH, 0), (WIDTH, HEIGHT), 2)
        if hand_controller is not None:
            draw_hand_preview(screen, hand_controller, hand, small_font)

        pygame.display.flip()

    # 메인 메뉴로 돌아갈 때 제목 복구
    pygame.display.set_caption("Every One")

    # 직접 만든 컨트롤러만 정리 (메뉴에서 받은 것은 메뉴가 계속 사용)
    if own_controller and hand_controller is not None:
        hand_controller.stop()


# ==========================================
# HUD 그리기
# ==========================================

def draw_crosshair(surf):
    cx = WIDTH // 2
    cy = HEIGHT // 2
    pygame.draw.line(surf, WHITE, (cx - 12, cy), (cx - 4, cy), 2)
    pygame.draw.line(surf, WHITE, (cx + 4, cy), (cx + 12, cy), 2)
    pygame.draw.line(surf, WHITE, (cx, cy - 12), (cx, cy - 4), 2)
    pygame.draw.line(surf, WHITE, (cx, cy + 4), (cx, cy + 12), 2)


def draw_turn_meter(surf, turn, small_font):
    """화면 위쪽: 120도 회전 범위 중 현재 위치"""
    w = 240
    x0 = WIDTH // 2 - w // 2
    y0 = 18
    pygame.draw.rect(surf, (30, 30, 36), (x0, y0, w, 8))
    pygame.draw.rect(surf, GRAY, (x0, y0, w, 8), 1)
    pygame.draw.line(surf, GRAY, (WIDTH // 2, y0 - 3), (WIDTH // 2, y0 + 10), 1)

    pos = x0 + int((turn + MAX_TURN) / (2 * MAX_TURN) * w)
    pygame.draw.rect(surf, WHITE, (pos - 3, y0 - 3, 6, 14))

    lbl = small_font.render("{:+.0f}".format(turn), True, GRAY)
    surf.blit(lbl, (WIDTH // 2 - lbl.get_width() // 2, y0 + 14))


def draw_offscreen_indicators(surf, enemies, angle):
    """시야 밖 적이 있는 방향을 화면 가장자리 화살표로 표시"""
    px, py = PLAYER_POS
    left_y = HEIGHT // 2 - 60
    right_y = HEIGHT // 2 - 60

    for e in sorted(enemies, key=lambda en: en.time_left):
        if not e.alive:
            continue
        ang = math.degrees(math.atan2(e.y - py, e.x - px))
        rel = angle_diff(ang, angle)
        if abs(rel) <= FOV / 2:
            continue

        ratio = max(0.0, e.time_left / ENEMY_TIME_LIMIT)
        color = GREEN if ratio > 0.6 else YELLOW if ratio > 0.3 else RED

        if rel < 0:
            y = left_y
            pygame.draw.polygon(surf, color, [(10, y), (30, y - 12), (30, y + 12)])
            left_y += 30
        else:
            y = right_y
            pygame.draw.polygon(
                surf, color,
                [(WIDTH - 10, y), (WIDTH - 30, y - 12), (WIDTH - 30, y + 12)]
            )
            right_y += 30


def draw_hand_preview(surf, hand_controller, hand, small_font):
    """게임 영역 바깥 오른쪽 패널에 웹캠 미리보기와 인식 상태 표시."""
    panel_title = small_font.render("WEBCAM", True, (80, 180, 255))
    surf.blit(
        panel_title,
        (
            WIDTH + (CAMERA_PANEL_WIDTH - panel_title.get_width()) // 2,
            CAMERA_PREVIEW_Y - 32,
        ),
    )
    preview = hand_controller.get_preview_surface()
    if preview is not None:
        pygame.draw.rect(
            surf,
            (80, 180, 255),
            (
                CAMERA_PREVIEW_X - 2,
                CAMERA_PREVIEW_Y - 2,
                CAMERA_PREVIEW_SIZE[0] + 4,
                CAMERA_PREVIEW_SIZE[1] + 4,
            ),
            2,
        )
        preview = pygame.transform.smoothscale(preview, CAMERA_PREVIEW_SIZE)
        surf.blit(preview, (CAMERA_PREVIEW_X, CAMERA_PREVIEW_Y))

    if hand["detected"]:
        color = YELLOW if hand["gesture"] == "Fist" else GREEN
        label = "Hand: " + hand["gesture"]
        if hand["gesture"] == "Fist":
            label += " (AIM LOCK)"
    else:
        color = RED
        label = "Hand: Not Detected"
    text = small_font.render(label, True, color)
    surf.blit(
        text,
        (
            WIDTH + (CAMERA_PANEL_WIDTH - text.get_width()) // 2,
            CAMERA_PREVIEW_Y + CAMERA_PREVIEW_SIZE[1] + 14,
        ),
    )


def draw_hud(surf, state, font, small_font, hand_mode=False):
    t = state["time"]
    time_text = font.render(
        "TIME : {:05.1f}".format(max(0.0, t)), True, RED if t <= 10 else WHITE
    )
    score_text = font.render("SCORE : " + str(state["score"]), True, WHITE)
    kills_text = font.render("KILLS : " + str(state["kills"]), True, GREEN)

    surf.blit(time_text, (20, 20))
    surf.blit(score_text, (20, 55))
    surf.blit(kills_text, (20, 90))

    # 라이프 (하트 대신 사각형)
    lives_label = font.render("LIFE", True, WHITE)
    lx = WIDTH - 20 - START_LIVES * 26 - lives_label.get_width() - 10
    surf.blit(lives_label, (lx, 20))
    for i in range(START_LIVES):
        x = WIDTH - 20 - (START_LIVES - i) * 26
        color = RED if i < state["lives"] else (60, 30, 30)
        pygame.draw.rect(surf, color, (x, 22, 20, 20))
        pygame.draw.rect(surf, WHITE, (x, 22, 20, 20), 1)

    alive = len([e for e in state["enemies"] if e.alive])
    enemy_text = small_font.render(
        "ENEMIES : {}/{}".format(alive, MAX_ENEMIES), True, ORANGE
    )
    surf.blit(enemy_text, (WIDTH - 20 - enemy_text.get_width(), 55))

    if hand_mode:
        label = "HAND : TURN    FIST : FIRE    (KB OK)    ESC : MENU"
    else:
        label = "LEFT / RIGHT : TURN    CLICK / SPACE / ENTER : FIRE    ESC : MENU"
    controls = small_font.render(label, True, GRAY)
    surf.blit(controls, (WIDTH // 2 - controls.get_width() // 2, HEIGHT - 20))


def draw_game_over(surf, state, font, big_font, small_font):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 175))
    surf.blit(overlay, (0, 0))

    color = RED if state["result"] == "GAME OVER" else GREEN
    result_text = big_font.render(state["result"], True, color)
    surf.blit(result_text, (WIDTH // 2 - result_text.get_width() // 2, HEIGHT // 2 - 120))

    final_text = font.render(
        "KILLS : {}    SCORE : {}".format(state["kills"], state["score"]), True, WHITE
    )
    surf.blit(final_text, (WIDTH // 2 - final_text.get_width() // 2, HEIGHT // 2 - 20))

    restart_text = font.render("ENTER / FIST : RESTART", True, GREEN)
    surf.blit(restart_text, (WIDTH // 2 - restart_text.get_width() // 2, HEIGHT // 2 + 50))

    menu_text = small_font.render("ESC : MAIN MENU", True, GRAY)
    surf.blit(menu_text, (WIDTH // 2 - menu_text.get_width() // 2, HEIGHT // 2 + 95))


if __name__ == "__main__":
    pygame.init()
    run_game()
    pygame.quit()
