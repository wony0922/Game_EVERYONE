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
        else:
            search_roots.append(candidate_dirs)
    search_roots.extend([game_dir, base_dir])

    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        model_candidate = os.path.join(root, VOSK_MODEL_NAME)
        if os.path.isdir(model_candidate):
            return os.path.abspath(model_candidate)
        legacy_candidate = os.path.join(root, "model")
        if os.path.isdir(legacy_candidate):
            return os.path.abspath(legacy_candidate)

    return None


def ensure_vosk_model(target_dir=None):
    """Vosk 한국어 모델이 없으면 자동으로 다운로드하고 압축을 푼다."""
    existing_path = find_vosk_model(candidate_dirs=[target_dir] if target_dir else None)
    if existing_path:
        return existing_path

    if target_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.join(base_dir, "Every One")
    os.makedirs(target_dir, exist_ok=True)

    dest_model_path = os.path.join(target_dir, VOSK_MODEL_NAME)
    zip_dest_path = os.path.join(target_dir, f"{VOSK_MODEL_NAME}.zip")

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
