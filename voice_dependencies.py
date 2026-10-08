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
