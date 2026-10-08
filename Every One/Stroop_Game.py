import json
import os
import queue
import random
import subprocess
import tempfile
import threading

import pygame
from font_utils import get_font

from game_tutorial import show_tutorial
from hand_exit import VictoryExit


WIDTH = 800
HEIGHT = 600
CAMERA_PANEL_WIDTH = 240
WINDOW_WIDTH = WIDTH + CAMERA_PANEL_WIDTH
CAMERA_PREVIEW_SIZE = (160, 120)
CAMERA_PREVIEW_X = WIDTH + (CAMERA_PANEL_WIDTH - CAMERA_PREVIEW_SIZE[0]) // 2
CAMERA_PREVIEW_Y = 230
FPS = 60
MAX_LIVES = 5
ROUND_TIME = 1.5
FEEDBACK_TIME = 0.8

BACKGROUND_COLOR = (20, 20, 30)
WHITE = (245, 245, 245)
GRAY = (150, 150, 160)
GREEN = (80, 230, 120)
RED = (255, 90, 90)
YELLOW = (255, 220, 90)

COLORS = {
    "빨강": (245, 75, 75),
    "파랑": (80, 150, 255),
    "노랑": (255, 220, 65),
    "초록": (70, 215, 125),
    "보라": (185, 110, 245),
    "주황": (255, 145, 55),
}

COLOR_ALIASES = {
    "빨강": ("빨강", "빨간색", "빨강색"),
    "파랑": ("파랑", "파란색", "파랑색"),
    "노랑": ("노랑", "노란색", "노랑색"),
    "초록": ("초록", "초록색", "녹색"),
    "보라": ("보라", "보라색"),
    "주황": ("주황", "주황색"),
}


def _find_model_path():
    configured_path = os.environ.get("VOSK_MODEL_PATH")
    if configured_path:
        if os.path.isdir(configured_path):
            return configured_path
        raise RuntimeError(
            "VOSK_MODEL_PATH 경로가 존재하지 않습니다:\n{}".format(configured_path)
        )

    game_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(game_dir, "vosk-model-small-ko-0.22")
    if os.path.isdir(model_path):
        return model_path

    legacy_model_path = os.path.join(game_dir, "model")
    if os.path.isdir(legacy_model_path):
        return legacy_model_path

    raise RuntimeError(
        "한국어 Vosk 모델을 찾을 수 없습니다.\n"
        "다음 폴더에 한국어 Vosk 모델을 압축 해제해 주세요:\n"
        "{}\n".format(model_path)
        + "또는 VOSK_MODEL_PATH 환경 변수에 모델 폴더를 지정해 주세요."
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
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
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
        raise RuntimeError(
            "한글 경로에서 Vosk 모델을 열기 위한 임시 경로를 만들지 못했습니다.\n"
            "{}".format(error)
        ) from error

    return junction_path, temp_dir


class VoiceRecognizer:
    def __init__(self):
        try:
            from voice_dependencies import ensure_voice_dependencies

            ensure_voice_dependencies()
            import sounddevice
            from vosk import KaldiRecognizer, Model
        except (ImportError, RuntimeError) as error:
            raise RuntimeError(
                "음성인식 패키지 준비에 실패했습니다:\n{}".format(error)
            ) from error

        model_path = _find_model_path()
        self._sounddevice = sounddevice
        self._model_temp_dir = None
        try:
            model_access_path, self._model_temp_dir = (
                _create_vosk_model_access_path(model_path)
            )
            self._model = Model(model_access_path)
        except Exception as error:
            self._cleanup_model_access_path()
            raise RuntimeError(
                "Vosk 모델을 불러오지 못했습니다. 모델 폴더가 올바른지 확인해 주세요:\n"
                "{}\n{}".format(model_path, error)
            ) from error
        grammar = [
            alias
            for aliases in COLOR_ALIASES.values()
            for alias in aliases
        ]
        self._recognizer_type = KaldiRecognizer
        self._grammar = json.dumps(grammar + ["[unk]"], ensure_ascii=False)
        self._recognizer = KaldiRecognizer(self._model, 16000, self._grammar)
        self._audio_queue = queue.Queue(maxsize=100)
        self.results = queue.Queue()
        self.errors = queue.Queue()
        self._stop_event = threading.Event()
        self._audio_lock = threading.Lock()
        self._accepting_audio = threading.Event()
        self._finish_round = threading.Event()
        self.round_finished = threading.Event()
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.errors.put("마이크 입력 상태: {}".format(status))
        with self._audio_lock:
            if not self._accepting_audio.is_set():
                return
            try:
                self._audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                self.errors.put("음성 입력 처리가 지연되고 있습니다.")

    def start_round(self):
        self.round_finished.clear()
        with self._audio_lock:
            self._accepting_audio.set()

    def end_round(self):
        with self._audio_lock:
            self._accepting_audio.clear()
        self.round_finished.clear()
        self._finish_round.set()

    def _consume_audio(self, audio):
        if self._recognizer.AcceptWaveform(audio):
            transcript = json.loads(self._recognizer.Result()).get("text", "")
            if transcript:
                self.results.put(transcript)

    def _listen(self):
        try:
            with self._sounddevice.RawInputStream(
                samplerate=16000,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            ):
                while not self._stop_event.is_set():
                    if self._finish_round.is_set():
                        while True:
                            try:
                                audio = self._audio_queue.get_nowait()
                            except queue.Empty:
                                break
                            self._consume_audio(audio)

                        transcript = json.loads(
                            self._recognizer.FinalResult()
                        ).get("text", "")
                        if transcript:
                            self.results.put(transcript)
                        self._recognizer = self._recognizer_type(
                            self._model, 16000, self._grammar
                        )
                        self._finish_round.clear()
                        self.round_finished.set()
                        continue

                    try:
                        audio = self._audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    self._consume_audio(audio)
        except Exception as error:
            self.errors.put(
                "마이크를 시작할 수 없습니다: {}\n"
                "입력 장치와 마이크 권한을 확인해 주세요.".format(error)
            )

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
        except OSError as error:
            print(
                "[Stroop] 임시 모델 경로를 정리하지 못했습니다: {}".format(error)
            )
        finally:
            self._model_temp_dir = None


def _font(size, bold=False):
    return get_font(size, bold=bold)


def _draw_centered(screen, font, text, color, y):
    rendered = font.render(text, True, color)
    screen.blit(rendered, (WIDTH // 2 - rendered.get_width() // 2, y))


def run_game(hand_controller=None):
    screen = pygame.display.set_mode((WINDOW_WIDTH, HEIGHT))
    pygame.display.set_caption("Every One - Stroop Color Game")
    clock = pygame.time.Clock()
    title_font = _font(38, True)
    word_font = _font(100, True)
    body_font = _font(30)
    small_font = _font(22)

    if not show_tutorial(
        screen,
        "STROOP COLOR - 규칙 및 조작법",
        [
            ("게임 목표", [
                "화면에 적힌 글자가 아니라 글자의 실제 색깔을 맞히세요.",
                "제한 시간 안에 정답을 맞히고, 목숨 5개를 지키세요.",
            ]),
            ("조작 방법", [
                "마이크에 색깔 이름을 말하거나 해당 숫자 키를 누르세요.",
                "1 빨강   2 파랑   3 노랑   4 초록   5 보라   6 주황",
                "음성 또는 키 입력 제한 시간: 1.5초 | ESC: 메뉴",
            ]),
        ],
        hand_controller,
    ):
        return

    recognizer = None
    setup_error = None
    try:
        recognizer = VoiceRecognizer()
    except (RuntimeError, OSError) as error:
        setup_error = str(error)
        print("[Stroop] 음성인식 초기화 실패: {}".format(error))

    color_names = list(COLORS)
    score = 0
    lives = MAX_LIVES
    game_over = False
    feedback = ""
    feedback_color = WHITE
    feedback_until = 0
    round_expired = False
    timeout_pending = False
    round_started = pygame.time.get_ticks()
    word = ""
    ink_color = ""

    def next_round():
        nonlocal word, ink_color, round_started, feedback, round_expired
        nonlocal timeout_pending
        word = random.choice(color_names)
        ink_color = random.choice([name for name in color_names if name != word])
        round_started = pygame.time.get_ticks()
        feedback = ""
        round_expired = False
        timeout_pending = False
        if recognizer is not None:
            recognizer.start_round()

    def answer(spoken_color):
        nonlocal score, lives, game_over, feedback, feedback_color, feedback_until
        if game_over or feedback or (round_expired and not timeout_pending):
            return
        if spoken_color == ink_color:
            score += 1
            feedback = "정답!"
            feedback_color = GREEN
        else:
            lives -= 1
            feedback = "오답! 정답은 {}!".format(ink_color)
            feedback_color = RED
        feedback_until = pygame.time.get_ticks() + int(FEEDBACK_TIME * 1000)
        if lives <= 0:
            lives = 0
            game_over = True

    next_round()
    running = True
    victory_exit = VictoryExit()
    try:
        while running:
            now = pygame.time.get_ticks()
            if hand_controller is not None:
                is_detected, _hand_x, _hand_y, gesture = (
                    hand_controller.get_state()
                )
                if victory_exit.update(is_detected, gesture, now):
                    break
            else:
                victory_exit.update(False, "None", now)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif game_over and event.key == pygame.K_RETURN:
                        score = 0
                        lives = MAX_LIVES
                        game_over = False
                        next_round()
                    elif (
                        not setup_error
                        and not game_over
                        and not feedback
                        and not round_expired
                    ):
                        if pygame.K_1 <= event.key <= pygame.K_6:
                            answer(color_names[event.key - pygame.K_1])

            if recognizer is not None and not game_over and not feedback:
                while True:
                    try:
                        message = recognizer.errors.get_nowait()
                    except queue.Empty:
                        break
                    setup_error = message
                    print("[Stroop] {}".format(message))
                    recognizer.close()
                    recognizer = None
                    break

                if recognizer is not None:
                    while True:
                        try:
                            transcript = recognizer.results.get_nowait()
                        except queue.Empty:
                            break
                        normalized = transcript.replace(" ", "")
                        for color_name, aliases in COLOR_ALIASES.items():
                            if any(alias in normalized for alias in aliases):
                                answer(color_name)
                                break
                        if feedback or game_over:
                            break

            if not setup_error and not game_over:
                if feedback and now >= feedback_until:
                    next_round()
                elif (
                    not feedback
                    and not round_expired
                    and now - round_started >= ROUND_TIME * 1000
                ):
                    round_expired = True
                    timeout_pending = True
                    if recognizer is not None:
                        recognizer.end_round()

                if (
                    round_expired
                    and timeout_pending
                    and (
                        recognizer is None
                        or recognizer.round_finished.is_set()
                    )
                ):
                    timeout_pending = False
                    if not feedback and not game_over:
                        lives -= 1
                        if lives <= 0:
                            lives = 0
                            game_over = True
                        else:
                            feedback = "시간 초과!"
                            feedback_color = YELLOW
                            feedback_until = now + int(FEEDBACK_TIME * 1000)

            screen.fill(BACKGROUND_COLOR)
            _draw_centered(screen, title_font, "색깔 맞추기", WHITE, 42)
            screen.blit(body_font.render("점수: {}".format(score), True, WHITE), (28, 24))
            screen.blit(body_font.render("목숨: {}".format(lives), True, RED), (WIDTH - 140, 24))

            if setup_error:
                _draw_centered(screen, body_font, "음성인식을 시작할 수 없습니다.", RED, 165)
                for index, line in enumerate(setup_error.splitlines()):
                    _draw_centered(screen, small_font, line, WHITE, 225 + index * 34)
                _draw_centered(screen, small_font, "설정을 마친 뒤 다시 실행해 주세요.  ESC: 나가기", GRAY, 500)
            elif game_over:
                _draw_centered(screen, title_font, "게임 종료", RED, 200)
                _draw_centered(screen, body_font, "최종 점수: {}".format(score), WHITE, 275)
                _draw_centered(screen, small_font, "Enter: 다시 시작    ESC: 나가기", GRAY, 350)
            else:
                _draw_centered(screen, body_font, "글자가 아니라 글자의 실제 색깔을 말하세요!", GRAY, 125)
                word_surface = word_font.render(word, True, COLORS[ink_color])
                screen.blit(
                    word_surface,
                    (WIDTH // 2 - word_surface.get_width() // 2, 220),
                )
                if feedback:
                    _draw_centered(screen, body_font, feedback, feedback_color, 365)
                elif round_expired:
                    _draw_centered(screen, body_font, "분석중...", WHITE, 365)
                else:
                    remaining = max(
                        0.0,
                        ROUND_TIME - (now - round_started) / 1000.0,
                    )
                    _draw_centered(
                        screen,
                        body_font,
                        "정답을 말하세요!    남은 시간: {:.1f}초".format(remaining),
                        WHITE,
                        365,
                    )
                if recognizer is not None:
                    _draw_centered(screen, small_font, "마이크 듣는 중", GREEN, 435)
                _draw_centered(
                    screen,
                    small_font,
                    "1 빨강   2 파랑   3 노랑   4 초록   5 보라   6 주황",
                    GRAY,
                    478,
                )
                _draw_centered(screen, small_font, "ESC: 나가기", GRAY, 520)

            pygame.draw.line(screen, WHITE, (WIDTH, 0), (WIDTH, HEIGHT), 2)

            if hand_controller is not None:
                panel_title = small_font.render("WEBCAM", True, GREEN)
                screen.blit(
                    panel_title,
                    (
                        WIDTH
                        + (CAMERA_PANEL_WIDTH - panel_title.get_width()) // 2,
                        CAMERA_PREVIEW_Y - 32,
                    ),
                )
                preview = hand_controller.get_preview_surface()
                if preview is not None:
                    pygame.draw.rect(
                        screen,
                        GREEN,
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

            pygame.display.flip()
            clock.tick(FPS)
    finally:
        if recognizer is not None:
            recognizer.close()


if __name__ == "__main__":
    pygame.init()
    try:
        run_game()
    finally:
        pygame.quit()
