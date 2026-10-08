import pygame
from font_utils import get_font
import random
import os
import sys
from hand_input import scale_hand_x
from hand_exit import VictoryExit

# 상위 경로 모듈 검색 추가
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

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

# 색상 팔레트
BG_COLOR = (30, 60, 40)
PANEL_BG = (20, 40, 25)
BLACKBOARD_BG = (35, 55, 45)
BLACKBOARD_BORDER = (90, 130, 100)
WHITE = (255, 255, 255)
BLACK = (30, 30, 30)
RED = (220, 50, 50)
BLUE = (50, 120, 220)
YELLOW = (240, 190, 40)
GREEN = (50, 180, 90)
GRAY = (140, 140, 150)
DARK_GRAY = (60, 60, 70)
PURPLE = (150, 50, 200)
CARD_BACK_COLOR = (40, 80, 140)

SUITS = ['♠', '◆', '♥', '♣']
SUIT_COLORS = {'♠': BLACK, '◆': RED, '♥': RED, '♣': BLACK, 'JOKER': PURPLE}
RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def __str__(self):
        if self.suit == 'JOKER':
            return f"[{self.rank} JOKER]"
        return f"{self.suit}{self.rank}"

def run_game(hand_controller=None):
    own_controller = False
    if hand_controller is None and HandController is not None:
        try:
            hand_controller = HandController(cam_index=0)
            hand_controller.start()
            own_controller = True
        except Exception as e:
            print(f"[OneCard] HandController 생성 실패: {e}")

    screen = pygame.display.set_mode((WINDOW_WIDTH, HEIGHT))
    pygame.display.set_caption("Every One - One Card Deluxe")
    clock = pygame.time.Clock()

    font_title = get_font(26, bold=True)
    font_main = get_font(18, bold=True)
    font_card_num = get_font(24, bold=True)
    font_card_suit = get_font(32, bold=True)
    font_small = get_font(15, bold=True)
    font_board = get_font(18, bold=True)
    font_board_title = get_font(26, bold=True)

    game_state = "INSTRUCTION_1"

    def create_deck():
        deck = [Card(s, r) for s in SUITS for r in RANKS]
        deck.append(Card('JOKER', 'Black'))
        deck.append(Card('JOKER', 'Color'))
        random.shuffle(deck)
        return deck

    deck = create_deck()
    player_hand = [deck.pop() for _ in range(5)]
    ai_hand = [deck.pop() for _ in range(5)]
    discard_pile = [deck.pop()]

    while discard_pile[-1].rank in ['2', 'A', 'K', 'J', 'Black', 'Color']:
        deck.append(discard_pile.pop())
        random.shuffle(deck)
        discard_pile.append(deck.pop())

    turn = "PLAYER"
    selected_index = 0
    message = "내 차례: Point로 카드 선택 후 [주먹/Enter]로 내세요."
    game_over = False
    winner = ""

    attack_stack = 0
    current_suit = discard_pile[-1].suit
    suit_select_index = 0

    turn_start_time = 0
    gesture_locked = False
    lock_timer = 0
    instruction_transition_ready_at = (
        pygame.time.get_ticks() + 1500
    )
    instruction_fist_armed = hand_controller is None
    instruction_back_armed = True
    ai_think_end_time = 0
    victory_exit = VictoryExit(hold_time_ms=1200)
    instruction_back_gesture = VictoryExit(hold_time_ms=1200)

    # 카드 날아가는 애니메이션 관리 리스트 ([x, y, target_x, target_y, progress, total_frames])
    flying_cards = []

    def trigger_fly_animation(target_type="PLAYER"):
        # 덱 위치에서 시작
        start_x, start_y = WIDTH // 2 - 120, HEIGHT // 2 - 85
        # 목표 위치 (플레이어 핸드 중앙 혹은 AI 위치)
        if target_type == "PLAYER":
            target_x, target_y = WIDTH // 2, HEIGHT - 165
        else:
            target_x, target_y = WIDTH // 2, 80

        flying_cards.append({
            'x': float(start_x), 'y': float(start_y),
            'tx': float(target_x), 'ty': float(target_y),
            'progress': 0, 'total': 15
        })

    def draw_cards(target_hand, count, target_type="PLAYER"):
        nonlocal deck
        for _ in range(count):
            if not deck:
                deck = create_deck()
            target_hand.append(deck.pop())
            trigger_fly_animation(target_type)

    def is_playable(card, top_card, cur_suit, stack):
        if stack > 0:
            if stack in [2, 4, 6, 8, 9, 10, 12, 14, 16]:
                return card.rank == '2' or card.suit == 'JOKER'
            elif stack in [3, 6, 9, 12, 15]:
                return card.rank == 'A' or card.suit == 'JOKER'
            elif stack >= 5:
                return card.suit == 'JOKER' or card.rank in ['2', 'A']
            return False

        if card.suit == 'JOKER':
            return True
        return card.suit == cur_suit or card.rank == top_card.rank or card.suit == top_card.suit

    def apply_card_effect(card):
        nonlocal attack_stack, current_suit, turn, message, game_state
        if card.suit == 'JOKER':
            if card.rank == 'Color':
                attack_stack += 7
                message = f"컬러 조커! 공격력 +7 (누적: {attack_stack})"
            else:
                attack_stack += 5
                message = f"흑백 조커! 공격력 +5 (누적: {attack_stack})"
            current_suit = '♠'
        elif card.rank == '2':
            attack_stack += 2
            message = f"공격 카드 '2'! 공격력 +2 (누적: {attack_stack})"
            current_suit = card.suit
        elif card.rank == 'A':
            attack_stack += 3
            message = f"공격 카드 'A'! 공격력 +3 (누적: {attack_stack})"
            current_suit = card.suit
        elif card.rank in ['J', 'K']:
            message = f"기능 카드 '{card.rank}'! 턴이 한 번 더 주어집니다."
            current_suit = card.suit
            return True
        elif card.rank == '7':
            game_state = "SELECTING_SUIT"
            message = "숫자 7 발동! 변경할 문양을 선택하세요."
            return True
        else:
            current_suit = card.suit
        return False

    running = True
    while running:
        clock.tick(FPS)
        current_time = pygame.time.get_ticks()

        is_detected = False
        gesture = "None"
        if hand_controller is not None:
            is_detected, hand_x, hand_y, gesture = hand_controller.get_state()
            if game_state in ("INSTRUCTION_1", "INSTRUCTION_2"):
                instruction_back = False
                if not is_detected or gesture != "Victory":
                    instruction_back_gesture.update(
                        False, "None", current_time
                    )
                    instruction_back_armed = True
                elif instruction_back_armed:
                    instruction_back = instruction_back_gesture.update(
                        is_detected, gesture, current_time
                    )
                else:
                    instruction_back_gesture.update(
                        False, "None", current_time
                    )
                    instruction_back = False
                victory_exit.update(False, "None", current_time)
                if instruction_back:
                    instruction_back_armed = False
                    if game_state == "INSTRUCTION_2":
                        game_state = "INSTRUCTION_1"
                        instruction_transition_ready_at = current_time + 1500
                        instruction_fist_armed = False
                        gesture_locked = True
                        lock_timer = current_time
                    else:
                        running = False
            else:
                instruction_back_gesture.update(
                    False, "None", current_time
                )
                if victory_exit.update(
                    is_detected, gesture, current_time
                ):
                    break
            if (
                game_state in ("INSTRUCTION_1", "INSTRUCTION_2")
                and current_time >= instruction_transition_ready_at
                and (not is_detected or gesture != "Fist")
            ):
                instruction_fist_armed = True
            if gesture in ["None", "Unknown"]:
                gesture_locked = False
            elif gesture_locked and current_time - lock_timer > 1200:
                gesture_locked = False
        else:
            instruction_back_gesture.update(False, "None", current_time)
            victory_exit.update(False, "None", current_time)

        # ==========================================
        # 1. 칠판 안내 1페이지 (게임 규칙)
        # ==========================================
        if game_state == "INSTRUCTION_1":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif (
                        event.key in (pygame.K_SPACE, pygame.K_RETURN)
                        and current_time >= instruction_transition_ready_at
                    ):
                        game_state = "INSTRUCTION_2"
                        instruction_transition_ready_at = current_time + 1500
                        instruction_fist_armed = hand_controller is None

            if (
                hand_controller is not None
                and is_detected
                and gesture == "Fist"
                and instruction_fist_armed
                and not gesture_locked
                and current_time >= instruction_transition_ready_at
            ):
                gesture_locked = True
                instruction_fist_armed = False
                lock_timer = current_time
                game_state = "INSTRUCTION_2"
                instruction_transition_ready_at = current_time + 1500

            screen.fill(BG_COLOR)
            board_rect = pygame.Rect(40, 20, WIDTH - 80, HEIGHT - 40)
            pygame.draw.rect(screen, BLACKBOARD_BG, board_rect, border_radius=12)
            pygame.draw.rect(screen, BLACKBOARD_BORDER, board_rect, 6, border_radius=12)

            title_surf = font_board_title.render("♠ 원카드 게임 규칙 안내 (1 / 2) ♠", True, YELLOW)
            screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 45))
            pygame.draw.line(screen, BLACKBOARD_BORDER, (70, 90), (WIDTH - 70, 90), 2)

            rules = [
                ("🎯 게임 목표 및 기본 룰", GREEN),
                ("• 내 손에 있는 모든 카드를 먼저 다 내면 승리합니다!", WHITE),
                ("• 바닥의 카드와 [무늬] 또는 [숫자]가 같은 카드를 낼 수 있습니다.", WHITE),
                ("", WHITE),
                ("⚡ 특수 카드 및 공격 규칙", YELLOW),
                ("• [2] 카드: 공격력 +2 / [A] 카드: 공격력 +3 (중첩 가능)", WHITE),
                ("  - 공격받았을 때 방어 카드를 못 내면 누적된 카드 더미를 다 가져가야 합니다!", WHITE),
                ("• [흑백 조커 (+5)] / [컬러 조커 (+7)]: 언제든 내며 강력한 공격!", WHITE),
                ("• [J, K]: 턴을 건너뛰고 내 턴이 한 번 더 주어집니다.", WHITE),
                ("• [7]: 원하는 문양(♠, ◆, ♥, ♣)으로 변경할 수 있습니다.", WHITE),
            ]

            start_y = 105
            for text, color in rules:
                if text == "":
                    start_y += 6
                    continue
                txt_surf = font_board.render(text, True, color)
                screen.blit(txt_surf, (65, start_y))
                start_y += 28

            prompt_text = (
                "잠시 기다려 주세요..."
                if current_time < instruction_transition_ready_at
                else "Space / 주먹: 다음 안내    |    ESC / V 모양 1.2초: 메뉴"
            )
            prompt_surf = font_main.render(prompt_text, True, YELLOW)
            if (current_time // 400) % 2 == 0:
                screen.blit(prompt_surf, (WIDTH // 2 - prompt_surf.get_width() // 2, HEIGHT - 65))

            if hand_controller is not None:
                panel_title = font_small.render("WEBCAM", True, BLUE)
                screen.blit(panel_title, (WIDTH + (CAMERA_PANEL_WIDTH - panel_title.get_width()) // 2, CAMERA_PREVIEW_Y - 32))
                preview = hand_controller.get_preview_surface()
                if preview is not None:
                    pygame.draw.rect(screen, BLUE, (CAMERA_PREVIEW_X - 2, CAMERA_PREVIEW_Y - 2, CAMERA_PREVIEW_SIZE[0] + 4, CAMERA_PREVIEW_SIZE[1] + 4), 2)
                    preview = pygame.transform.smoothscale(preview, CAMERA_PREVIEW_SIZE)
                    screen.blit(preview, (CAMERA_PREVIEW_X, CAMERA_PREVIEW_Y))

                st_text = font_small.render(f"Gesture: {gesture}", True, GREEN if is_detected else RED)
                screen.blit(st_text, (WIDTH + (CAMERA_PANEL_WIDTH - st_text.get_width()) // 2, CAMERA_PREVIEW_Y + CAMERA_PREVIEW_SIZE[1] + 14))

            pygame.draw.line(screen, WHITE, (WIDTH, 0), (WIDTH, HEIGHT), 2)
            pygame.display.flip()
            continue

        # ==========================================
        # 2. 칠판 안내 2페이지 (조작법 안내)
        # ==========================================
        if game_state == "INSTRUCTION_2":
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        game_state = "INSTRUCTION_1"
                        instruction_transition_ready_at = current_time + 1500
                        instruction_fist_armed = False
                        gesture_locked = True
                        lock_timer = current_time
                    elif (
                        event.key in (pygame.K_SPACE, pygame.K_RETURN)
                        and current_time >= instruction_transition_ready_at
                    ):
                        game_state = "PLAYING"
                        turn_start_time = pygame.time.get_ticks()
                        instruction_transition_ready_at = current_time + 1500
                        instruction_fist_armed = hand_controller is None

            if (
                hand_controller is not None
                and is_detected
                and gesture == "Fist"
                and instruction_fist_armed
                and not gesture_locked
                and current_time >= instruction_transition_ready_at
            ):
                gesture_locked = True
                instruction_fist_armed = False
                lock_timer = current_time
                game_state = "PLAYING"
                turn_start_time = pygame.time.get_ticks()
                instruction_transition_ready_at = current_time + 1500

            screen.fill(BG_COLOR)
            board_rect = pygame.Rect(40, 20, WIDTH - 80, HEIGHT - 40)
            pygame.draw.rect(screen, BLACKBOARD_BG, board_rect, border_radius=12)
            pygame.draw.rect(screen, BLACKBOARD_BORDER, board_rect, 6, border_radius=12)

            title_surf = font_board_title.render("🖐️ 모션 및 키보드 조작법 안내 (2 / 2) ♠", True, YELLOW)
            screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 45))
            pygame.draw.line(screen, BLACKBOARD_BORDER, (70, 90), (WIDTH - 70, 90), 2)

            instructions = [
                ("🖐️ 모션 인식 조작법 (오류 방지 안내)", GREEN),
                ("• [Point (가리키기)] 상태에서 손을 좌우로 이동: 내 패 카드 선택", WHITE),
                ("  ※ 주먹이나 손바닥을 핀 채로 움직이면 인식이 꼬일 수 있으니 주의하세요!", YELLOW),
                ("• [주먹 (Fist)]: 선택한 카드 내기 / 메뉴 진행", WHITE),
                ("• [승리 V (Victory)]: 카드 한 장 뽑기", WHITE),
                ("• [펴진 손 (Palm)]: 카드 1장 뽑고 턴 넘기기", WHITE),
                ("", WHITE),
                ("⌨️ 키보드 조작법", BLUE),
                ("• ← / → 방향키: 카드 선택  |  ENTER / SPACE: 카드 내기", WHITE),
                ("• D 키: 카드 뽑기  |  P 키: 카드 1장 뽑고 턴 넘기기", WHITE),
                ("• 20초 제한 시간 초과 시 자동으로 카드를 먹고 턴이 넘어갑니다.", WHITE),
            ]

            start_y = 105
            for text, color in instructions:
                if text == "":
                    start_y += 6
                    continue
                txt_surf = font_board.render(text, True, color)
                screen.blit(txt_surf, (65, start_y))
                start_y += 28

            prompt_text = (
                "잠시 기다려 주세요..."
                if current_time < instruction_transition_ready_at
                else "Space / 주먹: 게임 시작    |    ESC / V 모양 1.2초: 이전 안내"
            )
            prompt_surf = font_main.render(prompt_text, True, YELLOW)
            if (current_time // 400) % 2 == 0:
                screen.blit(prompt_surf, (WIDTH // 2 - prompt_surf.get_width() // 2, HEIGHT - 65))

            if hand_controller is not None:
                panel_title = font_small.render("WEBCAM", True, BLUE)
                screen.blit(panel_title, (WIDTH + (CAMERA_PANEL_WIDTH - panel_title.get_width()) // 2, CAMERA_PREVIEW_Y - 32))
                preview = hand_controller.get_preview_surface()
                if preview is not None:
                    pygame.draw.rect(screen, BLUE, (CAMERA_PREVIEW_X - 2, CAMERA_PREVIEW_Y - 2, CAMERA_PREVIEW_SIZE[0] + 4, CAMERA_PREVIEW_SIZE[1] + 4), 2)
                    preview = pygame.transform.smoothscale(preview, CAMERA_PREVIEW_SIZE)
                    screen.blit(preview, (CAMERA_PREVIEW_X, CAMERA_PREVIEW_Y))

                st_text = font_small.render(f"Gesture: {gesture}", True, GREEN if is_detected else RED)
                screen.blit(st_text, (WIDTH + (CAMERA_PANEL_WIDTH - st_text.get_width()) // 2, CAMERA_PREVIEW_Y + CAMERA_PREVIEW_SIZE[1] + 14))

            pygame.draw.line(screen, WHITE, (WIDTH, 0), (WIDTH, HEIGHT), 2)
            pygame.display.flip()
            continue

        # ==========================================
        # 3. 7을 냈을 때 문양 선택 화면
        # ==========================================
        if game_state == "SELECTING_SUIT":
            if hand_controller is not None and is_detected:
                if gesture == "Point":
                    suit_select_index = int(scale_hand_x(hand_x) * len(SUITS))
                    suit_select_index = max(0, min(len(SUITS) - 1, suit_select_index))
                elif gesture == "Fist" and not gesture_locked:
                    gesture_locked = True
                    lock_timer = current_time
                    current_suit = SUITS[suit_select_index]
                    message = f"문양이 [{current_suit}](으)로 변경되었습니다. AI 턴으로 넘어갑니다."
                    game_state = "PLAYING"
                    turn = "AI"
                    ai_think_end_time = current_time + random.randint(3000, 6000)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_LEFT:
                        suit_select_index = (suit_select_index - 1) % len(SUITS)
                    elif event.key == pygame.K_RIGHT:
                        suit_select_index = (suit_select_index + 1) % len(SUITS)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        current_suit = SUITS[suit_select_index]
                        message = f"문양이 [{current_suit}](으)로 변경되었습니다. AI 턴으로 넘어갑니다."
                        game_state = "PLAYING"
                        turn = "AI"
                        ai_think_end_time = current_time + random.randint(3000, 6000)

            screen.fill(BG_COLOR)
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))

            title_s = font_board_title.render("♠ 숫자 7 발동! 변경할 문양을 선택하세요 ♠", True, YELLOW)
            screen.blit(title_s, (WIDTH // 2 - title_s.get_width() // 2, HEIGHT // 2 - 120))

            card_w, card_h = 100, 140
            start_x = WIDTH // 2 - (len(SUITS) * 115) // 2
            for i, s in enumerate(SUITS):
                cx = start_x + i * 115
                cy = HEIGHT // 2 - 50
                is_sel = (i == suit_select_index)
                crect = pygame.Rect(cx, cy, card_w, card_h)

                pygame.draw.rect(screen, (255, 255, 240) if is_sel else WHITE, crect, border_radius=10)
                pygame.draw.rect(screen, YELLOW if is_sel else DARK_GRAY, crect, 4 if is_sel else 2, border_radius=10)

                col = SUIT_COLORS[s]
                st_surf = font_card_suit.render(s, True, col)
                screen.blit(st_surf, (cx + card_w // 2 - st_surf.get_width() // 2, cy + 45))

            guide_s = font_main.render("Point로 좌우 이동 후 [주먹/Enter]로 선택", True, WHITE)
            screen.blit(guide_s, (WIDTH // 2 - guide_s.get_width() // 2, HEIGHT // 2 + 120))

            pygame.display.flip()
            continue

        # ==========================================
        # 4. 본 게임 플레이 루프
        # ==========================================
        if turn == "PLAYER" and not game_over:
            elapsed_sec = (current_time - turn_start_time) / 1000.0
            if elapsed_sec >= 20.0:
                draw_count = attack_stack if attack_stack > 0 else 1
                draw_cards(player_hand, draw_count, "PLAYER")
                message = f"20초 초과! 카드를 {draw_count}장 강제로 먹고 AI 턴으로 넘어갑니다."
                attack_stack = 0
                turn = "AI"
                ai_think_end_time = current_time + random.randint(3000, 6000)

        if hand_controller is not None:
            if is_detected and not game_over and turn == "PLAYER":
                if gesture == "Point" and player_hand:
                    selected_index = int(scale_hand_x(hand_x) * len(player_hand))
                    selected_index = max(0, min(len(player_hand) - 1, selected_index))

                if gesture == "Fist" and not gesture_locked:
                    gesture_locked = True
                    lock_timer = current_time
                    if player_hand:
                        card = player_hand[selected_index]
                        top_card = discard_pile[-1]
                        if is_playable(card, top_card, current_suit, attack_stack):
                            discard_pile.append(player_hand.pop(selected_index))
                            selected_index = max(0, selected_index - 1)
                            if not player_hand:
                                game_over = True
                                winner = "PLAYER"
                            else:
                                keep_turn = apply_card_effect(card)
                                if game_state != "SELECTING_SUIT" and not keep_turn:
                                    turn = "AI"
                                    ai_think_end_time = current_time + random.randint(3000, 6000)
                                    turn_start_time = pygame.time.get_ticks()
                        else:
                            message = "이 카드는 낼 수 없습니다!"

                elif gesture == "Victory" and not gesture_locked:
                    gesture_locked = True
                    lock_timer = current_time
                    draw_count = attack_stack if attack_stack > 0 else 1
                    draw_cards(player_hand, draw_count, "PLAYER")
                    message = f"카드를 {draw_count}장 뽑았습니다. AI 차례로 넘어갑니다."
                    attack_stack = 0
                    turn = "AI"
                    ai_think_end_time = current_time + random.randint(3000, 6000)

                elif gesture == "Open Palm" and not gesture_locked:
                    gesture_locked = True
                    lock_timer = current_time
                    draw_count = attack_stack if attack_stack > 0 else 1
                    draw_cards(player_hand, draw_count, "PLAYER")
                    if attack_stack > 0:
                        message = f"공격 방어 실패! 카드 {draw_count}장을 먹고 턴을 넘깁니다."
                        attack_stack = 0
                    else:
                        message = "카드 1장을 뽑고 턴을 넘깁니다."
                    turn = "AI"
                    ai_think_end_time = current_time + random.randint(3000, 6000)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif game_over and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    deck = create_deck()
                    player_hand = [deck.pop() for _ in range(5)]
                    ai_hand = [deck.pop() for _ in range(5)]
                    discard_pile = [deck.pop()]
                    while discard_pile[-1].rank in ['2', 'A', 'K', 'J', 'Black', 'Color']:
                        deck.append(discard_pile.pop())
                        random.shuffle(deck)
                        discard_pile.append(deck.pop())
                    turn = "PLAYER"
                    game_over = False
                    winner = ""
                    attack_stack = 0
                    current_suit = discard_pile[-1].suit
                    message = "새 게임이 시작되었습니다."
                    turn_start_time = pygame.time.get_ticks()
                elif not game_over and turn == "PLAYER":
                    if event.key == pygame.K_LEFT:
                        selected_index = (selected_index - 1) % max(1, len(player_hand))
                    elif event.key == pygame.K_RIGHT:
                        selected_index = (selected_index + 1) % max(1, len(player_hand))
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if player_hand:
                            card = player_hand[selected_index]
                            top_card = discard_pile[-1]
                            if is_playable(card, top_card, current_suit, attack_stack):
                                discard_pile.append(player_hand.pop(selected_index))
                                selected_index = max(0, selected_index - 1)
                                if not player_hand:
                                    game_over = True
                                    winner = "PLAYER"
                                else:
                                    keep_turn = apply_card_effect(card)
                                    if game_state != "SELECTING_SUIT" and not keep_turn:
                                        turn = "AI"
                                        ai_think_end_time = current_time + random.randint(3000, 6000)
                                        turn_start_time = pygame.time.get_ticks()
                            else:
                                message = "이 카드는 낼 수 없습니다!"
                    elif event.key == pygame.K_d:
                        draw_count = attack_stack if attack_stack > 0 else 1
                        draw_cards(player_hand, draw_count, "PLAYER")
                        message = f"카드를 {draw_count}장 뽑았습니다."
                        attack_stack = 0
                        turn = "AI"
                        ai_think_end_time = current_time + random.randint(3000, 6000)
                    elif event.key == pygame.K_p:
                        draw_count = attack_stack if attack_stack > 0 else 1
                        draw_cards(player_hand, draw_count, "PLAYER")
                        if attack_stack > 0:
                            message = f"공격 방어 실패! 카드 {draw_count}장을 먹고 턴을 넘깁니다."
                            attack_stack = 0
                        else:
                            message = "카드 1장을 뽑고 턴을 넘깁니다."
                        turn = "AI"
                        ai_think_end_time = current_time + random.randint(3000, 6000)

        # --- AI 턴 (3~6초 고민 후 행동) ---
        if not game_over and turn == "AI":
            if current_time >= ai_think_end_time:
                top_card = discard_pile[-1]
                playable_cards = [c for c in ai_hand if is_playable(c, top_card, current_suit, attack_stack)]

                if playable_cards:
                    chosen = playable_cards[0]
                    ai_hand.remove(chosen)
                    discard_pile.append(chosen)
                    message = f"AI가 [{chosen}] 카드를 냈습니다."
                    if not ai_hand:
                        game_over = True
                        winner = "AI"
                    else:
                        if chosen.suit == 'JOKER':
                            if chosen.rank == 'Color':
                                attack_stack += 7
                            else:
                                attack_stack += 5
                            current_suit = '♠'
                            turn = "PLAYER"
                            turn_start_time = pygame.time.get_ticks()
                        elif chosen.rank == '2':
                            attack_stack += 2
                            current_suit = chosen.suit
                            turn = "PLAYER"
                            turn_start_time = pygame.time.get_ticks()
                        elif chosen.rank == 'A':
                            attack_stack += 3
                            current_suit = chosen.suit
                            turn = "PLAYER"
                            turn_start_time = pygame.time.get_ticks()
                        elif chosen.rank in ['J', 'K']:
                            ai_think_end_time = current_time + random.randint(2000, 4000)
                        elif chosen.rank == '7':
                            suits_count = {s: sum(1 for c in ai_hand if c.suit == s) for s in SUITS}
                            current_suit = max(suits_count, key=suits_count.get)
                            message = f"AI가 7을 내고 문양을 [{current_suit}](으)로 바꿨습니다."
                            turn = "PLAYER"
                            turn_start_time = pygame.time.get_ticks()
                        else:
                            current_suit = chosen.suit
                            turn = "PLAYER"
                            turn_start_time = pygame.time.get_ticks()
                else:
                    draw_count = attack_stack if attack_stack > 0 else 1
                    draw_cards(ai_hand, draw_count, "AI")
                    message = f"AI가 카드를 {draw_count}장 먹었습니다."
                    attack_stack = 0
                    turn = "PLAYER"
                    turn_start_time = pygame.time.get_ticks()

        # --- 화면 렌더링 ---
        screen.fill(BG_COLOR)

        top_bar = pygame.Rect(20, 20, WIDTH - 40, 50)
        pygame.draw.rect(screen, PANEL_BG, top_bar, border_radius=8)
        pygame.draw.rect(screen, GRAY, top_bar, 2, border_radius=8)

        ai_txt = font_main.render(f"🤖 상대(AI) 남은 카드: {len(ai_hand)}장", True, WHITE)
        screen.blit(ai_txt, (35, 32))

        if turn == "PLAYER":
            remaining_time = max(0, int(20.0 - (current_time - turn_start_time) / 1000.0))
            turn_indicator = f"🔥 내 턴! ({remaining_time}초)" + (f" [공격중:{attack_stack}]" if attack_stack > 0 else "")
            t_color = YELLOW if remaining_time > 5 else RED
        else:
            turn_indicator = "🤔 AI가 고민 중..." + (f" [공격중:{attack_stack}]" if attack_stack > 0 else "")
            t_color = YELLOW

        turn_txt = font_main.render(turn_indicator, True, t_color)
        screen.blit(turn_txt, (WIDTH - turn_txt.get_width() - 35, 32))

        # 1. 뒤집힌 카드 덱 (Draw Pile) 그리기 (버린 카드 더미 왼쪽)
        draw_pile_rect = pygame.Rect(WIDTH // 2 - 160, HEIGHT // 2 - 85, 100, 140)
        pygame.draw.rect(screen, CARD_BACK_COLOR, draw_pile_rect, border_radius=10)
        pygame.draw.rect(screen, DARK_GRAY, draw_pile_rect, 3, border_radius=10)
        # 덱 카드 뒷면 패턴 (십자가나 무늬 느낌)
        inner_rect = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 - 75, 80, 120)
        pygame.draw.rect(screen, (50, 100, 170), inner_rect, border_radius=6)
        deck_label = font_small.render("DECK", True, WHITE)
        screen.blit(deck_label, (WIDTH // 2 - 110 - deck_label.get_width() // 2, HEIGHT // 2 - 25))

        # 2. 버린 카드 더미 (Discard Pile) 그리기
        top_card = discard_pile[-1]
        pile_rect = pygame.Rect(WIDTH // 2 - 40, HEIGHT // 2 - 85, 100, 140)
        pygame.draw.rect(screen, WHITE, pile_rect, border_radius=10)
        pygame.draw.rect(screen, DARK_GRAY, pile_rect, 3, border_radius=10)

        c_color = SUIT_COLORS.get(top_card.suit, BLACK)
        if top_card.suit == 'JOKER':
            suit_surf = font_small.render("JOKER", True, PURPLE)
            rank_surf = font_card_num.render(top_card.rank, True, PURPLE)
            screen.blit(suit_surf, (WIDTH // 2 + 10 - suit_surf.get_width() // 2, HEIGHT // 2 - 40))
            screen.blit(rank_surf, (WIDTH // 2 + 10 - rank_surf.get_width() // 2, HEIGHT // 2 - 10))
        else:
            suit_surf = font_card_suit.render(top_card.suit, True, c_color)
            rank_surf = font_card_num.render(top_card.rank, True, c_color)
            screen.blit(suit_surf, (WIDTH // 2 + 10 - suit_surf.get_width() // 2, HEIGHT // 2 - 50))
            screen.blit(rank_surf, (WIDTH // 2 + 10 - rank_surf.get_width() // 2, HEIGHT // 2 + 10))

        suit_indicator = font_small.render(f"현재 문양: [{current_suit}] | 누적 공격: {attack_stack}", True, YELLOW)
        screen.blit(suit_indicator, (WIDTH // 2 - suit_indicator.get_width() // 2, HEIGHT // 2 + 62))

        pile_label = font_small.render("[ 버린 카드 ]", True, GRAY)
        screen.blit(pile_label, (WIDTH // 2 + 10 - pile_label.get_width() // 2, HEIGHT // 2 - 112))

        # 3. 날아가는 카드 애니메이션 업데이트 및 렌더링
        for fc in flying_cards[:]:
            fc['progress'] += 1
            t = fc['progress'] / fc['total']
            # 부드러운 이동 (Lerp)
            current_x = fc['x'] + (fc['tx'] - fc['x']) * t
            current_y = fc['y'] + (fc['ty'] - fc['y']) * t

            # 날아가는 카드(뒷면) 렌더링
            fly_rect = pygame.Rect(int(current_x - 30), int(current_y - 45), 60, 90)
            pygame.draw.rect(screen, CARD_BACK_COLOR, fly_rect, border_radius=6)
            pygame.draw.rect(screen, WHITE, fly_rect, 2, border_radius=6)

            if fc['progress'] >= fc['total']:
                flying_cards.remove(fc)

        # 하단 플레이어 패 그리기
        card_w, card_h = 80, 115
        total_w = len(player_hand) * 90
        start_x = WIDTH // 2 - total_w // 2

        for i, card in enumerate(player_hand):
            cx = start_x + i * 90
            cy = HEIGHT - 165
            is_selected = (i == selected_index)

            if is_selected:
                cy -= 15

            crect = pygame.Rect(cx, cy, card_w, card_h)
            bg_col = (255, 255, 240) if is_selected else WHITE
            border_col = YELLOW if is_selected else DARK_GRAY

            pygame.draw.rect(screen, bg_col, crect, border_radius=8)
            pygame.draw.rect(screen, border_col, crect, 3 if is_selected else 2, border_radius=8)

            col = SUIT_COLORS.get(card.suit, BLACK)
            if card.suit == 'JOKER':
                st = font_small.render("JOKER", True, PURPLE)
                rt = font_small.render(card.rank, True, PURPLE)
                screen.blit(st, (cx + 12, cy + 20))
                screen.blit(rt, (cx + card_w // 2 - rt.get_width() // 2, cy + 50))
            else:
                st = font_small.render(card.suit, True, col)
                rt = font_card_num.render(card.rank, True, col)
                screen.blit(st, (cx + 8, cy + 8))
                screen.blit(rt, (cx + card_w // 2 - rt.get_width() // 2, cy + 42))

        msg_bar = pygame.Rect(20, HEIGHT - 220, WIDTH - 40, 40)
        pygame.draw.rect(screen, PANEL_BG, msg_bar, border_radius=6)
        pygame.draw.rect(screen, GRAY, msg_bar, 1, border_radius=6)
        msg_surf = font_main.render(message, True, YELLOW if turn == "PLAYER" else GREEN)
        screen.blit(msg_surf, (35, HEIGHT - 212))

        if hand_controller is not None:
            guide = "Point: 선택 | Fist: 내기 | Victory: 뽑기/메뉴(1.2초 유지) | Palm: 1장 뽑고 넘기기"
        else:
            guide = "←/→: 카드 선택 | ENTER: 카드 내기 | D: 뽑기 | P: 1장 뽑고 넘기기"
        g_surf = font_small.render(guide, True, GRAY)
        screen.blit(g_surf, (WIDTH // 2 - g_surf.get_width() // 2, HEIGHT - 30))

        if game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))

            res_msg = "★ VICTORY! ★" if winner == "PLAYER" else "DEFEAT..."
            res_col = GREEN if winner == "PLAYER" else RED
            res_surf = font_card_suit.render(res_msg, True, res_col)
            sub_surf = font_main.render("SPACE / ENTER : 다시 시작    |    ESC : 메인 메뉴", True, WHITE)

            screen.blit(res_surf, (WIDTH // 2 - res_surf.get_width() // 2, HEIGHT // 2 - 60))
            screen.blit(sub_surf, (WIDTH // 2 - sub_surf.get_width() // 2, HEIGHT // 2 + 10))

        if hand_controller is not None:
            panel_title = font_small.render("WEBCAM", True, BLUE)
            screen.blit(panel_title, (WIDTH + (CAMERA_PANEL_WIDTH - panel_title.get_width()) // 2, CAMERA_PREVIEW_Y - 32))
            preview = hand_controller.get_preview_surface()
            if preview is not None:
                pygame.draw.rect(screen, BLUE, (CAMERA_PREVIEW_X - 2, CAMERA_PREVIEW_Y - 2, CAMERA_PREVIEW_SIZE[0] + 4, CAMERA_PREVIEW_SIZE[1] + 4), 2)
                preview = pygame.transform.smoothscale(preview, CAMERA_PREVIEW_SIZE)
                screen.blit(preview, (CAMERA_PREVIEW_X, CAMERA_PREVIEW_Y))

            st_text = font_small.render(f"Gesture: {gesture}", True, GREEN if is_detected else RED)
            screen.blit(st_text, (WIDTH + (CAMERA_PANEL_WIDTH - st_text.get_width()) // 2, CAMERA_PREVIEW_Y + CAMERA_PREVIEW_SIZE[1] + 14))

        pygame.draw.line(screen, WHITE, (WIDTH, 0), (WIDTH, HEIGHT), 2)
        pygame.display.flip()

    if own_controller and hand_controller is not None:
        hand_controller.stop()

if __name__ == "__main__":
    pygame.init()
    run_game()
    pygame.quit()
