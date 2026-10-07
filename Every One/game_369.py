import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import pygame

# --- 레트로 픽셀 감성 팔레트 ---
COLOR_OUTSIDE = (165, 200, 220)
COLOR_TREE = (120, 160, 100)
COLOR_WALL = (240, 230, 210)
COLOR_WINDOW_FRAME = (90, 60, 40)
COLOR_FLOOR_1 = (180, 140, 100)
COLOR_FLOOR_2 = (160, 120, 80)
COLOR_TABLE = (130, 85, 45)
COLOR_TABLE_SIDE = (90, 55, 25)
COLOR_CHAIR = (110, 70, 35)

COLOR_MY_HAIR = (50, 40, 30)
COLOR_MY_CLOTHES = (60, 130, 80)
COLOR_BOT_HAIR = (40, 40, 50)
COLOR_BOT_SKIN = (240, 200, 170)
COLOR_BOT_CLOTHES = (40, 60, 110)

PANEL_BG = (250, 245, 235)
PANEL_BORDER = (100, 70, 45)
WHITE = (255, 255, 255)
BLACK = (30, 30, 30)
RED = (220, 50, 50)
GREEN = (40, 160, 80)

MAX_NUM = 500
LIMIT_TIME = 5.0  # 제한시간 5초


# --- 숫자를 한글 읽기 발음으로 변환하는 헬퍼 함수 ---
UNITS_TEXT = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]
TENS_TEXT = ["", "십", "이십", "삼십", "사십", "오십", "육십", "칠십", "팔십", "구십"]
HUNDREDS_TEXT = ["", "백", "이백", "삼백", "사백", "오백"]

def get_korean_number_words(num):
    if num == 500:
        return ["오백"]
    
    h = num // 100
    t = (num % 100) // 10
    u = num % 10
    
    word = f"{HUNDREDS_TEXT[h]}{TENS_TEXT[t]}{UNITS_TEXT[u]}"
    return [word, str(num)]


# --- 한글 음성을 아라비아 숫자로 변환하는 파서 ---
KOREAN_NUM_MAP = {
    "영": 0, "공": 0,
    "일": 1, "하나": 1,
    "이": 2, "둘": 2,
    "삼": 3, "셋": 3,
    "사": 4, "넷": 4,
    "오": 5, "다섯": 5,
    "육": 6, "여섯": 6,
    "칠": 7, "일곱": 7,
    "팔": 8, "여덟": 8,
    "구": 9, "아홉": 9,
    "십": 10, "열": 10,
    "스물": 20, "서른": 30, "마흔": 40, "쉰": 50,
    "예순": 60, "일흔": 70, "여든": 80, "아흔": 90,
    "백": 100
}


def parse_korean_number(text):
    digits = re.findall(r'\d+', text)
    if digits:
        return int(digits[0])

    text = text.replace(" ", "")
    if not text:
        return None

    if text in KOREAN_NUM_MAP:
        return KOREAN_NUM_MAP[text]

    total = 0
    current = 0
    found = False

    i = 0
    while i < len(text):
        two_char = text[i:i+2]
        if two_char in KOREAN_NUM_MAP:
            found = True
            val = KOREAN_NUM_MAP[two_char]
            total += val
            i += 2
            continue

        one_char = text[i]
        if one_char in KOREAN_NUM_MAP:
            found = True
            val = KOREAN_NUM_MAP[one_char]
            if val == 100:
                current = (current if current != 0 else 1) * 100
                total += current
                current = 0
            elif val == 10:
                current = (current if current != 0 else 1) * 10
                total += current
                current = 0
            else:
                current += val
            i += 1
        else:
            i += 1

    total += current
    return total if found else None


def _find_model_path():
    configured_path = os.environ.get("VOSK_MODEL_PATH")
    if configured_path:
        if os.path.isdir(configured_path):
            return configured_path
        raise RuntimeError(f"VOSK_MODEL_PATH 경로가 존재하지 않습니다:\n{configured_path}")

    game_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(game_dir, "vosk-model-small-ko-0.22")
    if os.path.isdir(model_path):
        return model_path

    legacy_model_path = os.path.join(game_dir, "model")
    if os.path.isdir(legacy_model_path):
        return legacy_model_path

    raise RuntimeError(
        "한국어 Vosk 모델을 찾을 수 없습니다.\n"
        f"다음 폴더에 한국어 Vosk 모델을 압축 해제해 주세요:\n{model_path}\n"
        "또는 VOSK_MODEL_PATH 환경 변수에 모델 폴더를 지정해 주세요."
    )


def _create_vosk_model_access_path(model_path):
    if os.name != "nt" or model_path.isascii():
        return model_path, None

    temp_root = tempfile.gettempdir()
    if not temp_root.isascii():
        raise RuntimeError(
            "Vosk가 한글 경로를 처리하지 못합니다. 모델을 C:\\vosk-model-small-ko-0.22 "
            "같은 영문 경로로 옮기고 VOSK_MODEL_PATH에 해당 경로를 지정해 주세요."
        )

    temp_dir = tempfile.mkdtemp(prefix="vosk-", dir=temp_root)
    junction_path = os.path.join(temp_dir, "model")
    environment = os.environ.copy()
    environment["VOSK_MODEL_TARGET"] = model_path
    environment["VOSK_MODEL_JUNCTION"] = junction_path
    command = (
        "New-Item -ItemType Junction -Path $env:VOSK_MODEL_JUNCTION "
        "-Target $env:VOSK_MODEL_TARGET -ErrorAction Stop | Out-Null"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            env=environment,
            text=True,
        )
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(details or "임시 모델 경로를 만들 수 없습니다.")
    except (OSError, RuntimeError) as error:
        os.rmdir(temp_dir)
        raise RuntimeError(f"한글 경로에서 Vosk 모델을 열기 위한 임시 경로를 만들지 못했습니다.\n{error}") from error

    return junction_path, temp_dir


class VoiceRecognizer:
    def __init__(self):
        try:
            import sounddevice
            from vosk import KaldiRecognizer, Model
        except ImportError as error:
            raise RuntimeError(
                "음성인식 패키지가 없습니다. 다음 명령으로 설치해 주세요:\n"
                "py -3.14 -m pip install vosk sounddevice"
            ) from error

        model_path = _find_model_path()
        self._sounddevice = sounddevice
        self._model_temp_dir = None
        try:
            model_access_path, self._model_temp_dir = _create_vosk_model_access_path(model_path)
            self._model = Model(model_access_path)
        except Exception as error:
            self._cleanup_model_access_path()
            raise RuntimeError(
                f"Vosk 모델을 불러오지 못했습니다. 모델 폴더가 올바른지 확인해 주세요:\n{model_path}\n{error}"
            ) from error

        device_info = self._sounddevice.query_devices(kind="input")
        self.native_rate = int(device_info["default_samplerate"])
        
        initial_grammar = ["짝", "착", "[unk]"]
        self._recognizer = KaldiRecognizer(
            self._model,
            self.native_rate,
            json.dumps(initial_grammar, ensure_ascii=False)
        )

        self._audio_queue = queue.Queue(maxsize=100)
        self.results = queue.Queue()
        self.errors = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def update_grammar(self, current_num):
        if self._recognizer is None:
            return
        
        target_clap = check_369(current_num)
        if target_clap > 0:
            grammar = ["짝", "착", "짹", "[unk]"]
        else:
            grammar = get_korean_number_words(current_num) + ["짝", "[unk]"]
            
        try:
            self._recognizer.SetGrammar(json.dumps(grammar, ensure_ascii=False))
        except Exception:
            pass

    def clear_results(self):
        while not self.results.empty():
            try:
                self.results.get_nowait()
            except queue.Empty:
                break

    def _audio_callback(self, indata, frames, time_info, status):
        try:
            self._audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            pass

    def _listen(self):
        try:
            with self._sounddevice.RawInputStream(
                samplerate=self.native_rate,
                blocksize=16000,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            ):
                while not self._stop_event.is_set():
                    try:
                        audio = self._audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if self._recognizer.AcceptWaveform(audio):
                        transcript = json.loads(self._recognizer.Result()).get("text", "")
                        if transcript:
                            self.results.put(transcript)
                    else:
                        partial = json.loads(self._recognizer.PartialResult()).get("partial", "")
                        if partial:
                            self.results.put(f"PARTIAL:{partial}")
        except Exception as error:
            self.errors.put(f"마이크 오류: {error}")

    def close(self):
        self._stop_event.set()
        self._thread.join(timeout=1.5)
        self._recognizer = None
        self._model = None
        self._cleanup_model_access_path()

    def _cleanup_model_access_path(self):
        if self._model_temp_dir is None:
            return

        junction_path = os.path.join(self._model_temp_dir, "model")
        try:
            if os.path.lexists(junction_path):
                os.rmdir(junction_path)
            os.rmdir(self._model_temp_dir)
        except OSError:
            pass
        finally:
            self._model_temp_dir = None


def check_369(num):
    num_str = str(num)
    return num_str.count("3") + num_str.count("6") + num_str.count("9")


def draw_pixel_speech_bubble(screen, font_speech, text, pos, is_left_tail=True, is_editing=False):
    display_text = text if text else ("..." if not is_editing else "")
    if is_editing and text:
        display_text = text + "_"

    text_surface = font_speech.render(display_text, True, BLACK)
    padding_x, padding_y = 16, 10
    width = max(text_surface.get_width() + padding_x * 2, 70)
    height = text_surface.get_height() + padding_y * 2

    x, y = pos
    rect = pygame.Rect(x, y, width, height)

    pygame.draw.rect(screen, WHITE, rect)
    pygame.draw.rect(screen, PANEL_BORDER, rect, width=3)

    if is_left_tail:
        pygame.draw.rect(screen, WHITE, (x + 15, y + height, 12, 12))
        pygame.draw.rect(screen, PANEL_BORDER, (x + 15, y + height, 12, 12), 2)
    else:
        pygame.draw.rect(screen, WHITE, (x + width - 25, y + height, 12, 12))
        pygame.draw.rect(screen, PANEL_BORDER, (x + width - 25, y + height, 12, 12), 2)

    txt_x = x + (width - text_surface.get_width()) // 2
    txt_y = y + padding_y
    screen.blit(text_surface, (txt_x, txt_y))


def draw_pixel_cafe_scene(screen):
    screen.fill(COLOR_WALL)

    tile_size = 40
    for y in range(320, 490, tile_size):
        for x in range(0, 800, tile_size):
            color = (
                COLOR_FLOOR_1
                if ((x // tile_size) + (y // tile_size)) % 2 == 0
                else COLOR_FLOOR_2
            )
            pygame.draw.rect(screen, color, (x, y, tile_size, tile_size))

    pygame.draw.rect(screen, COLOR_OUTSIDE, (80, 40, 640, 180))
    pygame.draw.rect(screen, COLOR_TREE, (120, 100, 90, 120))
    pygame.draw.rect(screen, COLOR_TREE, (550, 80, 110, 140))
    pygame.draw.rect(screen, COLOR_WINDOW_FRAME, (80, 40, 640, 180), width=6)
    pygame.draw.line(screen, COLOR_WINDOW_FRAME, (400, 40), (400, 220), 6)

    pygame.draw.rect(screen, COLOR_CHAIR, (510, 200, 90, 110))
    pygame.draw.rect(screen, COLOR_BOT_HAIR, (530, 205, 50, 45))
    pygame.draw.rect(screen, COLOR_BOT_SKIN, (535, 220, 40, 35))
    pygame.draw.rect(screen, BLACK, (543, 230, 6, 6))
    pygame.draw.rect(screen, BLACK, (561, 230, 6, 6))
    pygame.draw.rect(screen, COLOR_BOT_CLOTHES, (515, 255, 80, 65))

    pygame.draw.polygon(screen, COLOR_TABLE, [(40, 320), (760, 320), (800, 440), (0, 440)])
    pygame.draw.polygon(screen, COLOR_TABLE_SIDE, [(0, 440), (800, 440), (800, 455), (0, 455)])

    pygame.draw.rect(screen, WHITE, (260, 345, 18, 22))
    pygame.draw.rect(screen, (200, 50, 50), (510, 335, 16, 20))

    pygame.draw.rect(screen, COLOR_CHAIR, (140, 360, 130, 90))
    pygame.draw.rect(screen, COLOR_MY_CLOTHES, (120, 380, 170, 90))
    pygame.draw.rect(screen, COLOR_MY_HAIR, (165, 310, 80, 75))


def run_tutorial(screen, font_large, font_medium, font_small):
    """게임 시작 전 규칙과 조작법을 알려주는 블랙보드 스타일 튜토리얼 화면"""
    clock = pygame.time.Clock()
    running = True

    while running:
        clock.tick(30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                    return True

        # 블랙보드 배경 렌더링
        screen.fill((30, 50, 40))
        
        # 테두리 칠판 느낌
        pygame.draw.rect(screen, (70, 50, 30), (30, 30, 980, 540), 12)

        title_surf = font_large.render("★ 369 게임 규칙 및 조작법 ★", True, (255, 230, 100))
        screen.blit(title_surf, (1040 // 2 - title_surf.get_width() // 2, 70))

        rules = [
            "1. 턴이 돌아올 때마다 차례대로 숫자를 말하거나 입력하세요.",
            "2. 숫자에 3, 6, 9가 포함되어 있다면 숫자가 아닌 '짝'을 외쳐야 합니다!",
            "3. 제한 시간(5초) 내에 올바른 대답을 하지 못하면 게임이 종료됩니다.",
            "",
            "[조작 방법]",
            "· 음성 조작: 마이크를 통해 숫자를 발음하거나 '짝'이라고 말하기",
            "· 키보드 조작: 숫자 입력 후 [Enter], '짝'일 경우 [Space] 2번 연타"
        ]

        y_offset = 150
        for rule in rules:
            color = (255, 215, 0) if "조작 방법" in rule or "1." in rule or "2." in rule or "3." in rule else WHITE
            rule_surf = font_medium.render(rule, True, color)
            screen.blit(rule_surf, (80, y_offset))
            y_offset += 40

        prompt_surf = font_medium.render("▶ [SPACE] 또는 [ENTER]를 누르면 게임이 시작됩니다! (ESC: 메뉴)", True, (150, 255, 150))
        screen.blit(prompt_surf, (1040 // 2 - prompt_surf.get_width() // 2, 500))

        pygame.display.flip()

    return True


def run_game(hand_controller=None):
    SCREEN_WIDTH = 800
    SCREEN_HEIGHT = 600

    screen = pygame.display.set_mode((1040, 600))
    pygame.display.set_caption("Every One - 369 Mini Game")
    clock = pygame.time.Clock()

    try:
        font_large = pygame.font.SysFont("malgungothic", 42, bold=True)
        font_timer = pygame.font.SysFont("malgungothic", 50, bold=True)
        font_medium = pygame.font.SysFont("malgungothic", 20, bold=True)
        font_small = pygame.font.SysFont("malgungothic", 17, bold=True)
        font_speech = pygame.font.SysFont("malgungothic", 28, bold=True)
    except:
        font_large = pygame.font.Font(None, 48)
        font_timer = pygame.font.Font(None, 56)
        font_medium = pygame.font.Font(None, 24)
        font_small = pygame.font.Font(None, 20)
        font_speech = pygame.font.Font(None, 32)

    # 게임 시작 전 튜토리얼 먼저 실행
    if not run_tutorial(screen, font_large, font_medium, font_small):
        return

    recognizer = None
    setup_error = None
    try:
        recognizer = VoiceRecognizer()
    except (RuntimeError, OSError) as error:
        setup_error = str(error)

    current_num = 1
    is_player_turn = True
    game_over = False
    game_clear = False
    message = "게임을 진행하세요!"
    player_speech = ""
    bot_speech = ""
    bot_timer = 0
    input_buffer = ""
    space_press_count = 0
    turn_start_time = pygame.time.get_ticks()
    turn_unlocked_time = pygame.time.get_ticks()

    if recognizer:
        recognizer.update_grammar(current_num)

    def reset_game():
        nonlocal current_num, is_player_turn, game_over, game_clear, message
        nonlocal player_speech, bot_speech, bot_timer, input_buffer, space_press_count, turn_start_time, turn_unlocked_time
        current_num = 1
        is_player_turn = True
        game_over = False
        game_clear = False
        message = "게임을 진행하세요!"
        player_speech = ""
        bot_speech = ""
        bot_timer = 0
        input_buffer = ""
        space_press_count = 0
        turn_start_time = pygame.time.get_ticks()
        turn_unlocked_time = pygame.time.get_ticks() + 300
        if recognizer:
            recognizer.update_grammar(current_num)
            recognizer.clear_results()

    def pass_player_turn(speech_text):
        nonlocal current_num, is_player_turn, game_clear, message, player_speech, bot_timer, input_buffer, space_press_count
        player_speech = speech_text
        input_buffer = ""
        space_press_count = 0

        if current_num >= MAX_NUM:
            game_clear = True
            message = "🎉 GAME CLEAR! (Space: 재시작 | ESC: 메뉴)"
        else:
            current_num += 1
            is_player_turn = False
            bot_timer = pygame.time.get_ticks()

    def fail_player_turn(speech_text, err_msg):
        nonlocal game_over, message, player_speech, input_buffer, space_press_count
        player_speech = speech_text
        input_buffer = ""
        space_press_count = 0
        game_over = True
        message = f"{err_msg} [Space: 재시작 | ESC: 메뉴]"

    running = True
    try:
        while running:
            clock.tick(30)
            current_time = pygame.time.get_ticks()

            if not game_over and not game_clear and is_player_turn:
                elapsed_sec = (current_time - turn_start_time) / 1000.0
                remaining_time = max(0, int(LIMIT_TIME - elapsed_sec + 0.99))

                if elapsed_sec >= LIMIT_TIME:
                    fail_player_turn("...", "시간 초과! (5초 이내에 입력해야 합니다)")

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        break

                    if game_over or game_clear:
                        if event.key == pygame.K_SPACE:
                            reset_game()
                        continue

                    if is_player_turn:
                        target_clap = check_369(current_num)

                        if event.key == pygame.K_SPACE:
                            if target_clap == 0:
                                fail_player_turn("짝!", f"틀렸습니다! ({current_num}은/는 숫자를 쳐야 합니다)")
                            else:
                                space_press_count += 1
                                input_buffer = ""
                                if space_press_count == 2:
                                    pass_player_turn("짝!")

                        elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                            if target_clap > 0:
                                fail_player_turn(input_buffer if input_buffer else "X", f"틀렸습니다! ({current_num}은/는 스페이스 2번 연타 = 짝)")
                            else:
                                if input_buffer == str(current_num):
                                    pass_player_turn(input_buffer)
                                else:
                                    fail_player_turn(input_buffer if input_buffer else "X", f"틀렸습니다! (정답: {current_num})")

                        elif event.key == pygame.K_BACKSPACE:
                            if space_press_count > 0:
                                space_press_count -= 1
                            else:
                                input_buffer = input_buffer[:-1]

                        elif event.unicode.isdigit():
                            space_press_count = 0
                            input_buffer += event.unicode

            if recognizer is not None and not game_over and not game_clear:
                if not is_player_turn:
                    recognizer.clear_results()
                elif current_time >= turn_unlocked_time:
                    while True:
                        try:
                            err_msg = recognizer.errors.get_nowait()
                        except queue.Empty:
                            break
                        setup_error = err_msg
                        recognizer.close()
                        recognizer = None
                        break

                    if recognizer is not None:
                        while True:
                            try:
                                transcript = recognizer.results.get_nowait()
                            except queue.Empty:
                                break

                            raw_text = transcript.replace("PARTIAL:", "").replace(" ", "").strip()
                            if not raw_text:
                                continue

                            target_clap = check_369(current_num)

                            if "짝" in raw_text or "착" in raw_text or "짹" in raw_text:
                                if target_clap == 0:
                                    fail_player_turn("짝!", f"틀렸습니다! ({current_num}은/는 숫자를 말해야 합니다)")
                                else:
                                    pass_player_turn("짝!")
                                break

                            parsed_val = parse_korean_number(raw_text)
                            if parsed_val is not None:
                                if target_clap > 0:
                                    fail_player_turn(str(parsed_val), f"틀렸습니다! ({current_num}은/는 짝을 외쳐야 합니다)")
                                    break
                                elif parsed_val == current_num:
                                    pass_player_turn(str(parsed_val))
                                    break

            if not game_over and not game_clear and not is_player_turn:
                if current_time - bot_timer > 700:
                    clap_count = check_369(current_num)
                    bot_speech = "짝!" if clap_count > 0 else str(current_num)

                    if current_num >= MAX_NUM:
                        game_clear = True
                        message = "🎉 GAME CLEAR! (Space: 재시작 | ESC: 메뉴)"
                    else:
                        current_num += 1
                        is_player_turn = True
                        turn_start_time = pygame.time.get_ticks()
                        turn_unlocked_time = pygame.time.get_ticks() + 300
                        if recognizer:
                            recognizer.update_grammar(current_num)
                            recognizer.clear_results()

            screen.fill((20, 20, 30))
            draw_pixel_cafe_scene(screen)

            if not game_over and not game_clear and is_player_turn:
                timer_color = RED if remaining_time <= 2 else BLACK
                timer_txt = font_timer.render(str(remaining_time), True, timer_color)
                screen.blit(timer_txt, (25, 15))

            if space_press_count > 0:
                draw_pixel_speech_bubble(screen, font_speech, "짝!", (270, 230), is_left_tail=True, is_editing=True)
            elif is_player_turn:
                draw_pixel_speech_bubble(screen, font_speech, input_buffer, (270, 230), is_left_tail=True, is_editing=True)
            else:
                draw_pixel_speech_bubble(screen, font_speech, player_speech, (270, 230), is_left_tail=True)

            draw_pixel_speech_bubble(screen, font_speech, bot_speech, (420, 120), is_left_tail=False)

            panel_rect = pygame.Rect(20, 485, 760, 100)
            pygame.draw.rect(screen, PANEL_BG, panel_rect)
            pygame.draw.rect(screen, PANEL_BORDER, panel_rect, width=4)

            status_str = f"☕ 369 게임 | 목표: {MAX_NUM} | 현재 숫자: {current_num}"
            if not game_over and not game_clear:
                status_str += "  ▶ [내 차례]" if is_player_turn else "  ▶ [상대 생각 중...]"

            hdr_txt = font_medium.render(status_str, True, BLACK)
            screen.blit(hdr_txt, (35, 502))

            msg_color = RED if game_over else (GREEN if game_clear else BLACK)
            msg_txt = font_small.render(message, True, msg_color)
            screen.blit(msg_txt, (35, 542))

            if recognizer is not None:
                mic_txt = font_small.render("🎤 마이크 듣는 중", True, GREEN)
                screen.blit(mic_txt, (650, 15))

            if game_over or game_clear:
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                screen.blit(overlay, (0, 0))

                main_title = font_large.render("GAME OVER" if game_over else "★ GAME CLEAR ★", True, RED if game_over else (255, 215, 0))
                sub_title = font_medium.render("Press SPACE to Restart | ESC to Menu", True, WHITE)

                screen.blit(main_title, (SCREEN_WIDTH // 2 - main_title.get_width() // 2, SCREEN_HEIGHT // 2 - 40))
                screen.blit(sub_title, (SCREEN_WIDTH // 2 - sub_title.get_width() // 2, SCREEN_HEIGHT // 2 + 20))

            pygame.display.flip()
    finally:
        if recognizer is not None:
            recognizer.close()


if __name__ == "__main__":
    pygame.init()
    try:
        run_game()
    finally:
        pygame.quit()
