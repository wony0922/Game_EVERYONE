"""Install optional speech-recognition packages into the running interpreter."""

import importlib
import subprocess
import sys


MODULE_PACKAGES = {
    "sounddevice": "sounddevice==0.5.6",
    "vosk": "vosk==0.3.45",
}


def ensure_voice_dependencies():
    missing = []
    for module_name, package_name in MODULE_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)

    if not missing:
        return

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        *missing,
    ]
    print(
        "[음성인식] 누락된 패키지를 현재 Python 환경에 설치합니다: "
        + ", ".join(missing),
        flush=True,
    )
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError(
            "음성인식 패키지를 자동 설치하지 못했습니다. "
            "인터넷 연결과 가상환경의 쓰기 권한을 확인해 주세요. "
            "실행 명령: {}".format(" ".join(command))
        ) from error

    importlib.invalidate_caches()
    for module_name in MODULE_PACKAGES:
        try:
            importlib.import_module(module_name)
        except ImportError as error:
            raise RuntimeError(
                "자동 설치 후에도 {} 패키지를 불러올 수 없습니다.".format(
                    module_name
                )
            ) from error


# Vosk 한국어 소형 모델은 16kHz로 학습되어 있다. 16kHz로 바로 받으면
# 48kHz로 받을 때보다 인식 연산량이 1/3 수준이라 라즈베리파이에서 특히 빠르다.
PREFERRED_SAMPLE_RATE = 16000
# 오디오를 0.1초 단위로 잘라 인식기에 넘긴다. (기존 0.5초 → 대기 시간 단축)
BLOCK_SECONDS = 0.1


def pick_input_samplerate(sounddevice, preferred=PREFERRED_SAMPLE_RATE):
    """마이크가 16kHz 입력을 지원하면 16kHz, 아니면 장치 기본값을 쓴다."""
    try:
        sounddevice.check_input_settings(
            samplerate=preferred, channels=1, dtype="int16"
        )
        return preferred
    except Exception:
        device_info = sounddevice.query_devices(kind="input")
        return int(device_info["default_samplerate"])


def block_size_for(samplerate):
    return max(160, int(samplerate * BLOCK_SECONDS))
