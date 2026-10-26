"""Install optional speech-recognition packages and models automatically."""

import importlib
import os
import subprocess
import sys
import urllib.request
import zipfile


MODULE_PACKAGES = {
    "sounddevice": "sounddevice==0.5.6",
    "vosk": "vosk==0.3.45",
}

VOSK_MODEL_NAME = "vosk-model-small-ko-0.22"
VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"


def ensure_voice_dependencies(with_model=False):
    """sounddevice 및 vosk 파이썬 패키지를 검사하고 누락 시 자동 설치한다."""
    missing = []
    for module_name, package_name in MODULE_PACKAGES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)

    if missing:
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

    if with_model:
        ensure_vosk_model()


def find_vosk_model(candidate_dirs=None):
    """환경 변수 및 후보 디렉토리들에서 Vosk 모델 폴더를 탐색한다."""
    configured_path = os.environ.get("VOSK_MODEL_PATH")
    if configured_path and os.path.isdir(configured_path):
        return os.path.abspath(configured_path)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    game_dir = os.path.join(base_dir, "Every One")

    search_roots = []
    if candidate_dirs:
        if isinstance(candidate_dirs, (list, tuple)):
            search_roots.extend(candidate_dirs)
def is_valid_vosk_model(model_dir):
    """모델 폴더 내 대용량 FST 파일이 Git LFS 포인터 텍스트가 아닌 실제 바이너리인지 검사"""
    if not model_dir or not os.path.isdir(model_dir):
        return False
    fst_file = os.path.join(model_dir, "graph", "HCLr.fst")
    if not os.path.isfile(fst_file):
        return False
    try:
        # 정상 HCLr.fst 파일은 약 180MB. 10MB 미만이거나 헤더가 'vers'면 Git LFS 텍스트 포인터
        if os.path.getsize(fst_file) < 10 * 1024 * 1024:
            return False
        with open(fst_file, "rb") as f:
            if f.read(4) == b"vers":
                return False
    except Exception:
        return False
    return True


def find_vosk_model(candidate_dirs=None):
    """환경 변수, 인자, 기본 경로에서 유효한 한국어 Vosk 모델 폴더를 탐색한다."""
    search_roots = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    game_dir = os.path.join(base_dir, "Every One")

    env_path = os.environ.get("VOSK_MODEL_PATH")
    if env_path:
        search_roots.append(env_path)

    if candidate_dirs:
        if isinstance(candidate_dirs, (list, tuple)):
            search_roots.extend(candidate_dirs)
        else:
            search_roots.append(candidate_dirs)
    search_roots.extend([game_dir, base_dir])

    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        model_candidate = os.path.join(root, VOSK_MODEL_NAME)
        if is_valid_vosk_model(model_candidate):
            return os.path.abspath(model_candidate)
        legacy_candidate = os.path.join(root, "model")
        if is_valid_vosk_model(legacy_candidate):
            return os.path.abspath(legacy_candidate)

    return None


def ensure_vosk_model(target_dir=None):
    """Vosk 한국어 모델이 없거나 손상되었으면 자동으로 다운로드하고 압축을 푼다."""
    existing_path = find_vosk_model(candidate_dirs=[target_dir] if target_dir else None)
    if existing_path:
        return existing_path

    if target_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.join(base_dir, "Every One")
    os.makedirs(target_dir, exist_ok=True)

    dest_model_path = os.path.join(target_dir, VOSK_MODEL_NAME)
    zip_dest_path = os.path.join(target_dir, f"{VOSK_MODEL_NAME}.zip")

    # 기존에 깨진(Git LFS 포인터) 폴더가 있다면 삭제 후 정상 재다운로드
    if os.path.isdir(dest_model_path) and not is_valid_vosk_model(dest_model_path):
        print(f"[음성인식] 기존 모델 파일이 손상되었거나 Git LFS 포인터입니다. 재다운로드를 위해 정리합니다...", flush=True)
        import shutil
        try:
            shutil.rmtree(dest_model_path)
        except Exception:
            pass

    print(
        f"[음성인식] 한국어 Vosk 모델이 없습니다. 자동 다운로드를 시작합니다...\n"
        f"  URL: {VOSK_MODEL_URL}\n"
        f"  저장 위치: {dest_model_path}",
        flush=True,
    )

    try:
        def _report_progress(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100.0, (block_num * block_size / total_size) * 100.0)
                sys.stdout.write(f"\r[음성 모델 다운로드 중] {percent:5.1f}% 완료...")
                sys.stdout.flush()

        urllib.request.urlretrieve(VOSK_MODEL_URL, zip_dest_path, reporthook=_report_progress)
        print("\n[음성인식] 다운로드 완료. 압축을 해제합니다...", flush=True)

        with zipfile.ZipFile(zip_dest_path, "r") as zip_ref:
            zip_ref.extractall(target_dir)

        if os.path.exists(zip_dest_path):
            os.remove(zip_dest_path)

        if os.path.isdir(dest_model_path):
            print(f"[음성인식] 모델 준비 완료: {dest_model_path}", flush=True)
            return os.path.abspath(dest_model_path)

    except Exception as error:
        if os.path.exists(zip_dest_path):
            try:
                os.remove(zip_dest_path)
            except OSError:
                pass
        raise RuntimeError(
            "한국어 Vosk 모델을 자동으로 내려받지 못했습니다.\n"
            f"오류: {error}\n"
            f"수동 다운로드: {VOSK_MODEL_URL} 을 받아서\n"
            f"다음 경로에 압축 해제해 주세요: {dest_model_path}"
        ) from error

    return os.path.abspath(dest_model_path)


def get_valid_input_device(sd):
    """
    사용 가능한 마이크 입력 장치 인덱스를 반환한다.
    - Windows(노트북/PC): OS 기본 마이크(내장 마이크 포함)가 유효하면 None을 반환하여
      sounddevice가 기본 장치로 안전하게 열리도록 한다.
    - Linux(라즈베리파이): 외장 USB 마이크를 우선 탐색하고, 없으면 기본/대체 장치로 fallback한다.
    """
    if sd is None:
        return None

    # Windows 환경: 기본 입력 장치가 정상이면 None 반환 (OS 기본 마이크 즉시 사용)
    if sys.platform == "win32":
        try:
            default_in = sd.default.device[0]
            if default_in is not None and default_in >= 0:
                dev = sd.query_devices(default_in)
                channels = dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0)
                if channels > 0:
                    print(f"[음성인식] Windows 기본 마이크를 사용합니다: [{default_in}]")
                    return None
        except Exception:
            pass

    try:
        devices = sd.query_devices()
    except Exception as exc:
        print(f"[음성인식] 장치 목록 조회 실패: {exc}")
        return None

    input_devices = []
    for idx, dev in enumerate(devices):
        channels = dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0)
        if channels > 0:
            input_devices.append((idx, dev))

    if not input_devices:
        print("[음성인식 경고] 사용 가능한 마이크 입력 장치를 찾을 수 없습니다!")
        return None

    # 1순위: 외장 USB 마이크 (라즈베리파이 등에서 꽂은 USB 마이크/웹캠 마이크)
    usb_keywords = ["usb", "microphone", "mic", "headset"]
    for idx, dev in input_devices:
        name = dev.get("name", "") if isinstance(dev, dict) else getattr(dev, "name", "")
        name_lower = name.lower()
        if any(bad in name_lower for bad in ["dmix", "loopback", "null", "mapper"]):
            continue
        if any(kw in name_lower for kw in usb_keywords):
            print(f"[음성인식] 외장/우선 마이크 선택됨: [{idx}]")
            return idx

    # 2순위: 시스템 기본 입력 장치 fallback
    try:
        default_idx = sd.default.device[0]
        if default_idx is not None and default_idx >= 0:
            dev = devices[default_idx]
            channels = dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0)
            if channels > 0:
                print(f"[음성인식] 기본 입력 장치 fallback: [{default_idx}]")
                return default_idx
    except Exception:
        pass

    # 3순위: 입력 가능한 첫 번째 장치
    chosen_idx, chosen_dev = input_devices[0]
    print(f"[음성인식] 대체 입력 장치 fallback: [{chosen_idx}] {chosen_dev.get('name')}")
    return chosen_idx


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

