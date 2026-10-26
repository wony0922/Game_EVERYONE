"""
voice_dependencies.py
─────────────────────
음성인식 의존성(Vosk, sounddevice) 및 모델 자동 다운로드 모듈.
"""

import os
import sys
import zipfile
import tempfile
import urllib.request
import urllib.error

GITHUB_REPO      = "wony0922/Game_EVERYONE"
MODEL_ASSET_NAME = "vosk-model-small-ko-0.22.zip"
MODEL_DIR_NAME   = "vosk-model-small-ko-0.22"

_RELEASE_URL = (
    f"https://github.com/{GITHUB_REPO}/releases/latest/download/{MODEL_ASSET_NAME}"
)


def _print(msg, end="\n"):
    """표준 출력과 flush를 함께 처리하며 cp949 인코딩 오류를 방지한다."""
    try:
        print(msg, end=end, flush=True)
    except UnicodeEncodeError:
        try:
            print(msg.encode("ascii", "replace").decode("ascii"), end=end, flush=True)
        except Exception:
            pass


def _download_with_progress(url, dest):
    def _reporthook(block_num, block_size, total_size):
        if total_size <= 0:
            _print(f"\r  다운로드 중... {block_num * block_size // 1024} KB", end="")
            return
        downloaded = min(block_num * block_size, total_size)
        pct = downloaded / total_size * 100
        bar_len = 30
        filled = int(bar_len * pct / 100)
        bar = "=" * filled + "-" * (bar_len - filled)
        mb_done = downloaded / 1_048_576
        mb_total = total_size / 1_048_576
        print(
            f"\r  [{bar}] {pct:5.1f}%  {mb_done:.1f}/{mb_total:.1f} MB",
            end="",
            flush=True,
        )

    urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
    print()


def ensure_vosk_model(target_dir=None):
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
                "다운로드된 파일이 올바른 ZIP이 아닙니다. Release 첨부 파일을 확인하세요."
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
                f"압축 해제 후 모델 폴더를 찾을 수 없습니다: {model_path}"
            )

    _print(f"  [OK] 모델 준비 완료: {model_path}")
    _print("=" * 60)
    return model_path


def ensure_voice_dependencies():
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
        _print(f"  [OK] 설치 완료: {pkg}")
    _print("=" * 60)


def get_valid_input_device(sounddevice):
    """
    사용 가능한 마이크 입력 장치 인덱스를 반환한다.
    - Windows(노트북/PC): OS 기본 마이크가 유효하면 None을 반환하여
      sounddevice가 기본 장치로 안전하게 열리도록 한다.
    - Linux(라즈베리파이): 외장 USB 마이크를 우선 탐색하고, 없으면 기본/대체 장치로 fallback한다.
    """
    if sounddevice is None:
        return None

    # Windows 환경: 기본 입력 장치가 정상이면 None 반환 (OS 기본 마이크 즉시 사용)
    if sys.platform == "win32":
        try:
            default_in = sounddevice.default.device[0]
            if default_in is not None and default_in >= 0:
                dev = sounddevice.query_devices(default_in)
                channels = dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0)
                if channels > 0:
                    _print("  [오디오] Windows 기본 마이크를 사용합니다.")
                    return None
        except Exception:
            pass

    try:
        devices = sounddevice.query_devices()
    except Exception as exc:
        _print(f"  [오디오] 장치 목록 조회 실패: {exc}")
        return None

    input_devices = []
    for idx, dev in enumerate(devices):
        channels = dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0)
        if channels > 0:
            input_devices.append((idx, dev))

    if not input_devices:
        _print("  [오디오 경고] 사용 가능한 마이크 입력 장치를 찾을 수 없습니다!")
        return None

    # 1순위: 외장 USB 마이크 (라즈베리파이 등에서 꽂은 USB 마이크/웹캠 마이크)
    usb_keywords = ["usb", "microphone", "mic", "headset"]
    for idx, dev in input_devices:
        name = dev.get("name", "") if isinstance(dev, dict) else getattr(dev, "name", "")
        name_lower = name.lower()
        if any(bad in name_lower for bad in ["dmix", "loopback", "null", "mapper"]):
            continue
        if any(kw in name_lower for kw in usb_keywords):
            _print(f"  [오디오] 외장/우선 마이크 선택됨: [{idx}]")
            return idx

    # 2순위: 시스템 기본 입력 장치 fallback
    try:
        default_idx = sounddevice.default.device[0]
        if default_idx is not None and default_idx >= 0:
            dev = devices[default_idx]
            channels = dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0)
            if channels > 0:
                _print(f"  [오디오] 기본 입력 장치 fallback: [{default_idx}]")
                return default_idx
    except Exception:
        pass

    # 3순위: 입력 가능한 첫 번째 장치
    chosen_idx, chosen_dev = input_devices[0]
    _print(f"  [오디오] 대체 입력 장치 fallback: [{chosen_idx}]")
    return chosen_idx


PREFERRED_SAMPLE_RATE = 16000
BLOCK_SECONDS = 0.1


def pick_input_samplerate(sounddevice, preferred=PREFERRED_SAMPLE_RATE):
    """마이크가 16kHz 입력을 지원하면 16kHz, 아니면 장치 기본값을 쓴다."""
    try:
        sounddevice.check_input_settings(
            samplerate=preferred, channels=1, dtype="int16"
        )
        return preferred
    except Exception:
        try:
            device_info = sounddevice.query_devices(kind="input")
            return int(device_info["default_samplerate"])
        except Exception:
            return 16000


def block_size_for(samplerate):
    return max(160, int(samplerate * BLOCK_SECONDS))
