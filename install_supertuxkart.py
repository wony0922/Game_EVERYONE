#!/usr/bin/env python3
"""SuperTuxKart(손동작 조작) 설치 스크립트 - Raspberry Pi OS / Windows 공용.

[Raspberry Pi OS]  python3 install_supertuxkart.py
  1. apt: supertuxkart, python3-dev / build-essential (evdev 빌드용)
  2. pip: evdev  ->  .venv-pi 가상환경
  3. 가상 입력 장치(/dev/uinput) 권한 설정
  (2, 3은 DOOM과 같은 설정이라 install_doom.py 를 이미 실행했다면 금방 끝남)

[Windows]  py -3.14 install_supertuxkart.py
  GitHub에서 SuperTuxKart 1.5 윈도우판(약 920MB)을 내려받아
  64비트 실행 파일과 게임 데이터만 영문 경로에 설치 (약 800MB)
    %LOCALAPPDATA%\\EveryOne\\supertuxkart  (안 되면 C:\\EveryOne\\supertuxkart)
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "Every One"))

# 출력/다운로드/uinput 설정 등은 DOOM 설치 스크립트와 같은 함수를 쓴다
from install_doom import (  # noqa: E402
    _sudo, pause, download, fail, install_pip, ok, run, setup_uinput, sha256_of, step,
    verify_linux,
)
from external_game import windows_game_home  # noqa: E402

# ══════════════════════════════════════════════════════════
#  Windows
# ══════════════════════════════════════════════════════════
WIN_URL = ("https://github.com/supertuxkart/stk-code/releases/download/1.5/"
           "SuperTuxKart-1.5-win.zip")
WIN_SHA256 = "9df7e2d67e8562127a3bb633030f1bd4ee77fa9e7f0ae110897473025af8acdc"
ZIP_ROOT = "SuperTuxKart-1.5-win/"
# zip 안에서 필요한 부분만 푼다 (32비트/ARM용 실행 파일은 건너뜀)
KEEP_PREFIXES = (
    ZIP_ROOT + "stk-code/build-x86_64/bin/",
    ZIP_ROOT + "stk-code/data/",
)
NEEDED_FREE_GB = 2.0   # 다운로드(0.9GB) + 설치(0.8GB) + 여유


def install_windows():
    home = Path(windows_game_home("supertuxkart"))
    exe = home / "stk-code" / "build-x86_64" / "bin" / "supertuxkart.exe"
    step("설치 위치: {}".format(home))

    if exe.is_file() and "--force" not in sys.argv:
        ok("이미 설치되어 있습니다. (다시 설치하려면 --force)")
        return

    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        fail("설치 폴더를 만들지 못했습니다: {}".format(error))

    free_gb = shutil.disk_usage(home).free / 1e9
    if free_gb < NEEDED_FREE_GB:
        fail("저장 공간이 부족합니다 (남은 공간 {:.1f}GB, {:.0f}GB 이상 필요).".format(
            free_gb, NEEDED_FREE_GB))

    zip_path = home / "download.zip"
    try:
        step("SuperTuxKart 1.5 내려받기 (약 920MB, 몇 분 걸려요)")
        try:
            download(WIN_URL, str(zip_path))
        except Exception as error:
            fail("다운로드 실패: {}\n인터넷 연결을 확인해 주세요.".format(error))

        step("파일 확인")
        if sha256_of(zip_path) != WIN_SHA256:
            fail("내려받은 파일이 손상되었습니다(체크섬 불일치). 다시 실행해 주세요.")
        ok("정상")

        step("압축 해제 (64비트 실행 파일 + 게임 데이터)")
        with zipfile.ZipFile(zip_path) as zf:
            members = [m for m in zf.infolist()
                       if not m.is_dir()
                       and m.filename.startswith(KEEP_PREFIXES)
                       and not m.filename.endswith(".pdb")]   # 디버그 파일 제외
            for i, info in enumerate(members, 1):
                target = home / info.filename[len(ZIP_ROOT):]
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                if i % 200 == 0 or i == len(members):
                    print("\r  {} / {} 파일".format(i, len(members)), end="", flush=True)
        print()
    finally:
        if zip_path.exists():
            zip_path.unlink()

    if not exe.is_file():
        fail("supertuxkart.exe 를 찾을 수 없습니다.")
    ok("설치 완료: {}".format(exe))


# ══════════════════════════════════════════════════════════
#  Raspberry Pi OS (Linux)
# ══════════════════════════════════════════════════════════
APT_PACKAGES = ["supertuxkart", "python3-dev", "build-essential"]


def install_apt():
    step("시스템 패키지 설치: {}".format(", ".join(APT_PACKAGES)))
    if shutil.which("apt-get") is None:
        fail("apt가 없는 리눅스입니다. Raspberry Pi OS에서 실행해 주세요.")

    def installed(pkg):
        r = subprocess.run(["dpkg-query", "-W", "-f=${db:Status-Status}", pkg],
                           capture_output=True, text=True)
        return r.returncode == 0 and r.stdout.strip() == "installed"

    missing = [p for p in APT_PACKAGES if not installed(p)]
    if not missing:
        ok("이미 모두 설치되어 있습니다.")
        return
    print("  설치합니다: {} (비밀번호를 물어볼 수 있어요, 게임 데이터가 커서 몇 분 걸려요)".format(
        ", ".join(missing)))
    run(_sudo() + ["apt-get", "update"], "apt 목록 갱신")
    run(_sudo() + ["apt-get", "install", "-y"] + missing, "apt 설치")
    ok("설치 완료")


def install_linux():
    install_apt()
    if not (shutil.which("supertuxkart") or os.path.exists("/usr/games/supertuxkart")):
        fail("supertuxkart 실행 파일을 찾을 수 없습니다.")
    install_pip()
    need_relogin = setup_uinput()
    verify_linux(need_relogin)
    return need_relogin


# ══════════════════════════════════════════════════════════
def main():
    print("Every One - SuperTuxKart(손동작 조작) 설치를 시작합니다.")
    need_relogin = False
    if sys.platform == "win32":
        install_windows()
    elif sys.platform.startswith("linux"):
        need_relogin = install_linux()
    else:
        fail("Windows 또는 Raspberry Pi OS에서 실행해 주세요. (현재: {})".format(sys.platform))

    print("\nSuperTuxKart 설치가 끝났습니다!")
    if need_relogin:
        print("권한 적용을 위해 라즈베리파이를 한 번 재부팅해 주세요: sudo reboot")
    if sys.platform == "win32":
        print("게임 실행: Every One\\EveryOne_Start.bat  ->  메뉴에서 SUPERTUXKART 선택")
        pause()
    else:
        print("게임 실행: ./run_raspberrypi.sh  ->  메뉴에서 SUPERTUXKART 선택")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        sys.exit(130)
