"""
voice_dependencies.py
─────────────────────
게임 실행 시 vosk/sounddevice 패키지와 한국어 모델이 없으면
자동으로 설치·다운로드한다.
"""

import os
import sys
import zipfile
import tempfile
import urllib.request
import urllib.error

# ── 설정 ──────────────────────────────────────────────────────────────────────
GITHUB_REPO      = "wony0922/Game_EVERYONE"
MODEL_ASSET_NAME = "vosk-model-small-ko-0.22.zip"   # Release 첨부 파일 이름
MODEL_DIR_NAME   = "vosk-model-small-ko-0.22"        # 압축 해제 후 폴더 이름

# GitHub Releases latest 다운로드 URL
_RELEASE_URL = (
    f"https://github.com/{GITHUB_REPO}/releases/latest/download/{MODEL_ASSET_NAME}"
)
# ──────────────────────────────────────────────────────────────────────────────


def _print(msg, end="\n"):
    """표준 출력과 flush를 함께 처리한다."""
    print(msg, end=end, flush=True)


def _download_with_progress(url, dest):
    """URL을 dest 경로로 다운로드하며 진행률을 출력한다."""

    def _reporthook(block_num, block_size, total_size):
        if total_size <= 0:
            _print(f"\r  다운로드 중... {block_num * block_size // 1024} KB", end="")
            return
        downloaded = min(block_num * block_size, total_size)
        pct = downloaded / total_size * 100
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)
        mb_done = downloaded / 1_048_576
        mb_total = total_size / 1_048_576
        print(
            f"\r  [{bar}] {pct:5.1f}%  {mb_done:.1f}/{mb_total:.1f} MB",
            end="",
            flush=True,
        )

    urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
    print()  # 줄바꿈


def ensure_vosk_model(target_dir=None):
    """
    vosk 모델 폴더 경로를 반환한다.
    모델이 없으면 GitHub Releases에서 자동 다운로드한다.
    """
    if target_dir is None:
        target_dir = os.path.dirname(os.path.abspath(__file__))

    model_path = os.path.join(target_dir, MODEL_DIR_NAME)

    if os.path.isdir(model_path):
        return model_path

    _print("=" * 60)
    _print("  한국어 Vosk 음성 모델이 없습니다.")
    _print("  GitHub Releases에서 자동으로 다운로드합니다.")
    _print(f"  URL: {_RELEASE_URL}")
    _print("=" * 60)

    zip_fd, zip_path = tempfile.mkstemp(suffix=".zip", prefix="vosk-model-")
    os.close(zip_fd)

    try:
        try:
            _download_with_progress(_RELEASE_URL, zip_path)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"모델 다운로드 실패 (HTTP {exc.code}): {_RELEASE_URL}\n"
                "GitHub Release에 모델 파일이 첨부되어 있는지 확인하세요."
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"네트워크 오류로 모델을 받지 못했습니다: {exc.reason}"
            ) from exc

        _print("  압축을 해제하는 중...")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_dir)
        except zipfile.BadZipFile as exc:
            raise RuntimeError(
                "다운로드된 파일이 올바른 ZIP이 아닙니다. "
                "Release 첨부 파일을 확인하세요."
            ) from exc
    finally:
        try:
            os.remove(zip_path)
        except OSError:
            pass

    if not os.path.isdir(model_path):
        candidates = [
            os.path.join(target_dir, d)
            for d in os.listdir(target_dir)
            if d.startswith("vosk-model") and os.path.isdir(os.path.join(target_dir, d))
        ]
        if candidates:
            model_path = candidates[0]
        else:
            raise RuntimeError(
                f"압축 해제 후 모델 폴더를 찾을 수 없습니다.\n"
                f"ZIP 내부 폴더 이름이 '{MODEL_DIR_NAME}'인지 확인하세요."
            )

    _print(f"  ✓ 모델 준비 완료: {model_path}")
    _print("=" * 60)
    return model_path


def ensure_voice_dependencies():
    """
    vosk 와 sounddevice 패키지가 설치돼 있는지 확인하고,
    없으면 pip으로 자동 설치한다.
    """
    _REQUIRED = {
        "vosk": "vosk",
        "sounddevice": "sounddevice",
    }

    missing = []
    for module_name, pip_name in _REQUIRED.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append(pip_name)

    if not missing:
        return

    _print("=" * 60)
    _print(f"  음성인식 패키지가 없습니다: {', '.join(missing)}")
    _print("  pip으로 자동 설치합니다...")
    _print("=" * 60)

    import subprocess

    for pkg in missing:
        _print(f"  설치 중: {pkg}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"패키지 설치 실패: {pkg}\n{result.stderr.strip()}"
            )
        _print(f"  ✓ 설치 완료: {pkg}")

    _print("=" * 60)


def get_valid_input_device(sounddevice):
    """
    사용 가능한 마이크 입력 장치 인덱스를 반환한다.
    기본 장치가 없거나 오류 시 입력 채널이 있는 첫 번째 장치를 반환한다.
    아무것도 없으면 None 반환.
    """
    try:
        default = sounddevice.default.device[0]
        if default is not None and default >= 0:
            devices = sounddevice.query_devices()
            if devices[default]["max_input_channels"] > 0:
                return None
    except Exception:
        pass

    try:
        devices = sounddevice.query_devices()
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                return idx
    except Exception:
        pass

    return None
