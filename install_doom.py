#!/usr/bin/env python3
"""DOOM(손동작 조작) 설치 스크립트 - Raspberry Pi OS / Windows 공용.

[Raspberry Pi OS]  python3 install_doom.py
  1. apt: chocolate-doom(둠 엔진), freedoom(무료 게임 데이터),
          python3-dev / build-essential (evdev 빌드용)
  2. pip: evdev  ->  .venv-pi 가상환경 (run_raspberrypi.sh 와 같은 환경)
  3. 가상 입력 장치(/dev/uinput) 권한 설정 (input 그룹)

[Windows]  py -3.14 install_doom.py
  1. GitHub에서 chocolate-doom(윈도우 64비트)과 Freedoom을 내려받아
     영문 경로에 설치  (%LOCALAPPDATA%\\EveryOne\\doom, 안 되면 C:\\EveryOne\\doom)
     * chocolate-doom은 한글 경로에서 문제가 생길 수 있어 프로젝트 폴더에 두지 않는다.
  2. 추가 Python 패키지는 필요 없음 (윈도우 기본 기능 ctypes 사용)
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------- 출력 ----
def step(msg):
    print("\n==> {}".format(msg), flush=True)


def ok(msg):
    print("  [OK] {}".format(msg), flush=True)


def warn(msg):
    print("  [주의] {}".format(msg), flush=True)


def fail(msg):
    print("\n[실패] {}".format(msg), file=sys.stderr, flush=True)
    if sys.platform == "win32":
        input("엔터를 누르면 창이 닫힙니다...")
    sys.exit(1)


# ══════════════════════════════════════════════════════════
#  Windows
# ══════════════════════════════════════════════════════════
WIN_DOWNLOADS = [
    {
        "name": "chocolate-doom 3.1.1 (Windows 64비트)",
        "url": "https://github.com/chocolate-doom/chocolate-doom/releases/download/"
               "chocolate-doom-3.1.1/chocolate-doom-3.1.1-win64.zip",
        "sha256": "58c34c61ae954493fce5ff01fd553898240a0de25658aa97b43ac9510c49581f",
        "files": None,  # 전부 풀기 (exe + dll)
    },
    {
        "name": "Freedoom 0.13.0",
        "url": "https://github.com/freedoom/freedoom/releases/download/v0.13.0/freedoom-0.13.0.zip",
        "sha256": "3f9b264f3e3ce503b4fb7f6bdcb1f419d93c7b546f4df3e874dd878db9688f59",
        "files": ["freedoom1.wad", "freedoom2.wad", "COPYING.txt"],
    },
]


def windows_doom_home():
    """게임 쪽(doom_classic.py)과 같은 경로를 쓰도록 공통 모듈의 함수를 사용한다."""
    sys.path.insert(0, str(ROOT_DIR / "Every One"))
    from external_game import windows_game_home
    return windows_game_home("doom")


def download(url, dest):
    print("  내려받는 중: {}".format(url))
    request = urllib.request.Request(url, headers={"User-Agent": "EveryOne-installer"})
    with urllib.request.urlopen(request, timeout=30) as response, open(dest, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done, last = 0, 0.0
        while True:
            chunk = response.read(256 * 1024)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total and time.time() - last > 0.5:
                last = time.time()
                print("\r  {:5.1f}%  ({:.1f} / {:.1f} MB)".format(
                    done * 100 / total, done / 1e6, total / 1e6), end="", flush=True)
    print("\r  다운로드 완료 ({:.1f} MB)            ".format(done / 1e6), flush=True)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def install_windows():
    home = Path(windows_doom_home())
    step("설치 위치: {}".format(home))
    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        fail("설치 폴더를 만들지 못했습니다: {}".format(error))

    engine_ok = (home / "chocolate-doom.exe").is_file()
    wad_ok = (home / "freedoom1.wad").is_file()
    if engine_ok and wad_ok and "--force" not in sys.argv:
        ok("이미 설치되어 있습니다. (다시 설치하려면 --force)")
        return

    with tempfile.TemporaryDirectory() as tmp:
        for item in WIN_DOWNLOADS:
            step(item["name"])
            zip_path = os.path.join(tmp, "download.zip")
            try:
                download(item["url"], zip_path)
            except Exception as error:
                fail("다운로드 실패: {}\n인터넷 연결을 확인해 주세요.".format(error))
            if sha256_of(zip_path) != item["sha256"]:
                fail("내려받은 파일이 손상되었습니다(체크섬 불일치). 다시 실행해 주세요.")

            with zipfile.ZipFile(zip_path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    name = os.path.basename(info.filename)
                    if item["files"] is not None and name not in item["files"]:
                        continue
                    # 폴더 구조 없이 설치 폴더 바로 아래에 푼다
                    with zf.open(info) as src, open(home / name, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            os.remove(zip_path)
            ok("설치 완료")

    step("확인")
    for name in ["chocolate-doom.exe", "SDL2.dll", "freedoom1.wad", "freedoom2.wad"]:
        if not (home / name).is_file():
            fail("{} 파일이 없습니다.".format(name))
        ok(name)


# ══════════════════════════════════════════════════════════
#  Raspberry Pi OS (Linux)
# ══════════════════════════════════════════════════════════
VENV_DIR = ROOT_DIR / ".venv-pi"
VENV_PYTHON = VENV_DIR / "bin" / "python"
APT_PACKAGES = ["chocolate-doom", "freedoom", "python3-dev", "build-essential"]
PIP_PACKAGES = ["evdev"]
WAD_CANDIDATES = [
    "/usr/share/games/doom/freedoom1.wad",
    "/usr/share/games/doom/freedoom2.wad",
]
UDEV_RULE_PATH = "/etc/udev/rules.d/99-everyone-uinput.rules"
UDEV_RULE = 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"\n'
MODULES_LOAD_PATH = "/etc/modules-load.d/everyone-uinput.conf"


def _sudo():
    return [] if os.geteuid() == 0 else ["sudo"]


def run(cmd, what):
    try:
        subprocess.run(cmd, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        fail("{} 실패: {}\n실행한 명령: {}".format(what, error, " ".join(cmd)))


def sudo_write(path, content):
    try:
        subprocess.run(_sudo() + ["tee", path], input=content, text=True,
                       stdout=subprocess.DEVNULL, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        fail("{} 파일을 쓰지 못했습니다: {}".format(path, error))


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
    print("  설치합니다: {} (비밀번호를 물어볼 수 있어요)".format(", ".join(missing)))
    run(_sudo() + ["apt-get", "update"], "apt 목록 갱신")
    run(_sudo() + ["apt-get", "install", "-y"] + missing, "apt 설치")
    ok("설치 완료")


def check_linux_game_files():
    step("둠 실행 파일과 게임 데이터 확인")
    engine = shutil.which("chocolate-doom") or (
        "/usr/games/chocolate-doom" if os.path.exists("/usr/games/chocolate-doom") else None)
    if engine is None:
        fail("chocolate-doom 실행 파일을 찾을 수 없습니다.")
    ok("엔진: {}".format(engine))
    wads = [w for w in WAD_CANDIDATES if os.path.isfile(w)]
    if not wads:
        fail("Freedoom WAD 파일을 찾을 수 없습니다: {}".format(", ".join(WAD_CANDIDATES)))
    for w in wads:
        ok("게임 데이터: {}".format(w))


def install_pip():
    step("Python 패키지 설치: {} (.venv-pi)".format(", ".join(PIP_PACKAGES)))
    if not VENV_PYTHON.exists():
        print("  가상환경이 없어 새로 만듭니다...")
        run([sys.executable, "-m", "venv", str(VENV_DIR)], "가상환경 생성")
    run([str(VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check",
         *PIP_PACKAGES], "pip 설치 (evdev 빌드에 1~2분 걸릴 수 있어요)")
    ok("설치 완료")


def setup_uinput():
    """반환값: 재부팅(재로그인)이 필요하면 True"""
    import getpass
    import grp

    step("가상 입력 장치(uinput) 권한 설정")
    need_relogin = False
    sudo = _sudo()

    if not os.path.exists(MODULES_LOAD_PATH):
        sudo_write(MODULES_LOAD_PATH, "uinput\n")
    subprocess.run(sudo + ["modprobe", "uinput"], check=False)

    current = Path(UDEV_RULE_PATH).read_text() if os.path.exists(UDEV_RULE_PATH) else ""
    if current != UDEV_RULE:
        sudo_write(UDEV_RULE_PATH, UDEV_RULE)
        subprocess.run(sudo + ["udevadm", "control", "--reload-rules"], check=False)
        subprocess.run(sudo + ["udevadm", "trigger", "--name-match=uinput"], check=False)

    if os.path.exists("/dev/uinput"):
        subprocess.run(sudo + ["chgrp", "input", "/dev/uinput"], check=False)
        subprocess.run(sudo + ["chmod", "0660", "/dev/uinput"], check=False)
    else:
        warn("/dev/uinput 이 아직 없습니다. 재부팅 후 생깁니다.")
        need_relogin = True

    user = os.environ.get("SUDO_USER") or getpass.getuser()
    try:
        group = grp.getgrnam("input")
    except KeyError:
        fail("input 그룹이 없습니다. Raspberry Pi OS가 맞는지 확인해 주세요.")
    if user not in group.gr_mem:
        run(sudo + ["usermod", "-aG", "input", user], "input 그룹 추가")
        ok("사용자 '{}'를 input 그룹에 추가했습니다.".format(user))
    if os.geteuid() != 0 and group.gr_gid not in os.getgroups():
        need_relogin = True

    ok("설정 완료")
    return need_relogin


def verify_linux(need_relogin):
    step("가상 입력 장치 테스트")
    if need_relogin:
        warn("권한이 새 로그인부터 적용되어 테스트를 건너뜁니다.")
        return
    code = ("from evdev import UInput, ecodes as e\n"
            "ui = UInput({e.EV_KEY: [e.KEY_SPACE]}, name='everyone-test')\n"
            "ui.close()\n")
    r = subprocess.run([str(VENV_PYTHON), "-c", code], capture_output=True, text=True)
    if r.returncode != 0:
        warn("가상 입력 장치를 만들지 못했습니다. 재부팅 후 다시 실행해 보세요.\n{}".format(
            r.stderr.strip()[-600:]))
    else:
        ok("가상 키보드를 만들 수 있습니다.")


def install_linux():
    install_apt()
    check_linux_game_files()
    install_pip()
    need_relogin = setup_uinput()
    verify_linux(need_relogin)
    return need_relogin


# ══════════════════════════════════════════════════════════
def main():
    print("Every One - DOOM(손동작 조작) 설치를 시작합니다.")
    need_relogin = False
    if sys.platform == "win32":
        install_windows()
    elif sys.platform.startswith("linux"):
        need_relogin = install_linux()
    else:
        fail("Windows 또는 Raspberry Pi OS에서 실행해 주세요. (현재: {})".format(sys.platform))

    print("\nDOOM 설치가 끝났습니다!")
    if need_relogin:
        print("권한 적용을 위해 라즈베리파이를 한 번 재부팅해 주세요: sudo reboot")
    if sys.platform == "win32":
        print("게임 실행: Every One\\EveryOne_Start.bat  ->  메뉴에서 DOOM 선택")
        input("엔터를 누르면 창이 닫힙니다...")
    else:
        print("게임 실행: ./run_raspberrypi.sh  ->  메뉴에서 DOOM 선택")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        sys.exit(130)
