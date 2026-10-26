#!/usr/bin/env python3
"""MarioPygame(손동작 조작) 설치 스크립트 - Raspberry Pi OS / Windows 공용.

  원본: https://github.com/Winter091/MarioPygame  (코드 MIT 라이선스)
  * 게임 그림/소리는 닌텐도 원작에서 가져온 것이라, 이 프로젝트 저장소(git)에는
    넣지 않고 설치할 때 내려받는다. (Every One/mario_pygame/ 은 .gitignore 대상)

설치하는 것
  1. 게임 파일 -> Every One/mario_pygame/  (원본의 Next 폴더 + LICENSE)
  2. pytmx (맵 파일 읽기용 Python 패키지)
     - 라즈베리파이: .venv-pi 가상환경 (run_raspberrypi.sh 와 같은 환경)
     - 윈도우: 이 스크립트를 실행한 Python (py -3.14)

사용법 (프로젝트 루트에서)
  라즈베리파이: python3 install_mario.py
  윈도우:       py -3.14 install_mario.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
from install_doom import download, fail, ok, step  # noqa: E402

COMMIT = "d4e1e438c8ca544b445b3d22f0552e761b1ea64a"   # 버전 고정 (2020-08-01)
REPO = "https://github.com/Winter091/MarioPygame"
ZIP_URL = "{}/archive/{}.zip".format(REPO, COMMIT)

TARGET = ROOT_DIR / "Every One" / "mario_pygame"
REQUIRED = ["Core.py", "Map.py", "Player.py", "worlds/1-1/W11.tmx",
            "images/super_mario_bros.png", "fonts/emulogic.ttf", "sounds/overworld.wav"]


def is_installed():
    return all((TARGET / rel).is_file() for rel in REQUIRED)


def copy_from_source(source_root):
    """원본 폴더(source_root)에서 Next 폴더 내용과 LICENSE 를 TARGET 으로 복사한다."""
    next_dir = source_root / "Next"
    if not (next_dir / "Core.py").is_file():
        fail("내려받은 파일에서 게임 코드를 찾지 못했습니다.")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(next_dir, TARGET)
    if (source_root / "LICENSE").is_file():
        shutil.copy2(source_root / "LICENSE", TARGET / "LICENSE")


def install_game_files():
    step("마리오 게임 파일 설치: {}".format(TARGET))
    if is_installed() and "--force" not in sys.argv:
        ok("이미 설치되어 있습니다. (다시 설치하려면 --force)")
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        source_root = None

        # 1순위: zip 다운로드 (git 없이도 됨)
        try:
            zip_path = tmp / "mario.zip"
            download(ZIP_URL, str(zip_path))
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmp / "zip")
            folders = [p for p in (tmp / "zip").iterdir() if p.is_dir()]
            source_root = folders[0] if folders else None
        except Exception as error:
            print("  zip 다운로드 실패({}), git clone 으로 다시 시도합니다.".format(error))

        # 2순위: git clone
        if source_root is None:
            if shutil.which("git") is None:
                fail("다운로드에 실패했고 git도 없습니다. 인터넷 연결을 확인해 주세요.")
            clone_dir = tmp / "clone"
            try:
                subprocess.run(["git", "clone", REPO, str(clone_dir)], check=True)
                subprocess.run(["git", "-C", str(clone_dir), "checkout", COMMIT], check=True)
            except (OSError, subprocess.CalledProcessError) as error:
                fail("git clone 실패: {}".format(error))
            source_root = clone_dir

        copy_from_source(source_root)

    if not is_installed():
        fail("설치 후 필요한 파일이 없습니다: {}".format(TARGET))
    ok("설치 완료")


def install_pytmx():
    if sys.platform == "win32":
        python = sys.executable
        where = "현재 Python ({})".format(python)
    else:
        python = str(ROOT_DIR / ".venv-pi" / "bin" / "python")
        where = ".venv-pi"
        if not os.path.exists(python):
            print("  가상환경이 없어 새로 만듭니다...")
            try:
                subprocess.run([sys.executable, "-m", "venv", str(ROOT_DIR / ".venv-pi")],
                               check=True)
            except (OSError, subprocess.CalledProcessError) as error:
                fail("가상환경 생성 실패: {}\n'sudo apt install python3-venv' 후 다시 실행해 주세요."
                     .format(error))

    step("Python 패키지 설치: pytmx -> {}".format(where))
    try:
        subprocess.run([python, "-m", "pip", "install", "--disable-pip-version-check",
                        "pytmx"], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        fail("pytmx 설치 실패: {}".format(error))
    ok("설치 완료")


def main():
    print("Every One - 마리오(손동작 조작) 설치를 시작합니다.")
    install_game_files()
    install_pytmx()
    print("\n마리오 설치가 끝났습니다!")
    if sys.platform == "win32":
        print("게임 실행: Every One\\EveryOne_Start.bat  ->  메뉴에서 MARIO 선택")
        input("엔터를 누르면 창이 닫힙니다...")
    else:
        print("게임 실행: ./run_raspberrypi.sh  ->  메뉴에서 MARIO 선택")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        sys.exit(130)
