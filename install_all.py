#!/usr/bin/env python3
"""Every One 전체 설치 + 점검 스크립트 (Raspberry Pi OS 우선, Windows 지원).

[Raspberry Pi OS]  python3 install_all.py
  1. 기본 설치      : run_raspberrypi.sh setup  (시스템 패키지, .venv-pi, requirements)
  2. 음성 인식      : install_voice_model.py   (Vosk 한국어 모델 확인/복구)
  3. DOOM           : install_doom.py
  4. SuperTuxKart   : install_supertuxkart.py
  5. 마리오         : install_mario.py
  6. 전체 점검      : 패키지 import, 모델/게임 파일, 카메라/마이크/가상 입력 장치
  7. 바탕화면 아이콘: 더블클릭으로 Every One 실행 (.desktop)

[Windows]  py -3.14 install_all.py
  requirements.txt 설치 -> DOOM / SuperTuxKart / 마리오 설치 -> 점검

옵션
  --skip-doom  --skip-kart  --skip-mario   해당 게임 설치 건너뛰기
  --check-only                             설치 없이 점검만
  --no-launcher                            바탕화면 아이콘 만들지 않기

한 단계가 실패해도 다음 단계는 계속 진행하고, 마지막에 결과를 모아서 보여 준다.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
GAME_DIR = ROOT_DIR / "Every One"
IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
VENV_PYTHON = ROOT_DIR / ".venv-pi" / "bin" / "python"

ARGS = set(sys.argv[1:])


def header(msg):
    print("\n" + "=" * 60 + "\n  " + msg + "\n" + "=" * 60, flush=True)


# ══════════════════════════════════════════════════════════
#  1~5. 설치 단계
# ══════════════════════════════════════════════════════════
def run_step(title, command):
    """한 단계를 실행하고 성공 여부를 돌려준다. 실패해도 멈추지 않는다."""
    header(title)
    env = dict(os.environ, EVERYONE_NO_PAUSE="1")
    try:
        result = subprocess.run(command, cwd=ROOT_DIR, env=env)
        return result.returncode == 0
    except OSError as error:
        print("  실행하지 못했습니다: {}".format(error))
        return False


def install_steps():
    results = []
    py = sys.executable
    if IS_LINUX:
        results.append(("기본 설치 (run_raspberrypi.sh setup)",
                        run_step("1. 기본 설치: 시스템 패키지 + 가상환경",
                                 ["bash", str(ROOT_DIR / "run_raspberrypi.sh"), "setup"])))
        results.append(("음성 인식 모델",
                        run_step("2. 음성 인식 (Vosk)", [py, "install_voice_model.py"])))
    else:
        results.append(("기본 패키지 (requirements.txt)",
                        run_step("1. 기본 패키지 설치",
                                 [py, "-m", "pip", "install", "-r", "requirements.txt"])))
    if "--skip-doom" not in ARGS:
        results.append(("DOOM", run_step("3. DOOM", [py, "install_doom.py"])))
    if "--skip-kart" not in ARGS:
        results.append(("SuperTuxKart", run_step("4. SuperTuxKart", [py, "install_supertuxkart.py"])))
    if "--skip-mario" not in ARGS:
        results.append(("마리오", run_step("5. 마리오", [py, "install_mario.py"])))
    return results


# ══════════════════════════════════════════════════════════
#  6. 점검
# ══════════════════════════════════════════════════════════
# 게임을 실행하는 Python(라즈베리파이: .venv-pi)에서 import 가 되는지 확인한다
IMPORT_CHECK = r"""
import importlib, json
names = ["cv2", "mediapipe", "numpy", "pygame", "PIL", "vosk", "sounddevice", "pytmx"]
import sys
if sys.platform.startswith("linux"):
    names.append("evdev")
out = {}
for n in names:
    try:
        m = importlib.import_module(n)
        out[n] = [True, str(getattr(m, "__version__", getattr(m, "ver", "")))]
    except Exception as e:
        out[n] = [False, "{}: {}".format(type(e).__name__, e)[:120]]
print(json.dumps(out))
"""

# import 가 실패했을 때 설치해서 고쳐 볼 패키지
REPAIR_PACKAGES = {
    "cv2": "opencv-contrib-python",   # mediapipe 가 쓰는 OpenCV 배포판
    "pygame": "pygame-ce==2.5.8",
    "numpy": "numpy",
    "PIL": "Pillow",
    "pytmx": "pytmx",
    "evdev": "evdev",
    "vosk": "vosk==0.3.45",
    "sounddevice": "sounddevice==0.5.6",
}

PURPOSE = {
    "cv2": "카메라 영상 (OpenCV)",
    "mediapipe": "손 인식",
    "numpy": "영상 배열 계산",
    "pygame": "게임 화면/소리 (pygame-ce)",
    "PIL": "이미지 처리 (Pillow)",
    "vosk": "한국어 음성 인식",
    "sounddevice": "마이크 입력",
    "pytmx": "마리오 맵 읽기",
    "evdev": "외부 게임 가상 입력",
}


def game_python():
    if IS_LINUX:
        return str(VENV_PYTHON) if VENV_PYTHON.exists() else None
    return sys.executable


def check_imports(python):
    result = subprocess.run([python, "-c", IMPORT_CHECK], capture_output=True, text=True)
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"python": [False, result.stderr.strip()[-200:]]}


def repair_imports(python, imports):
    broken = [n for n, (ok, _) in imports.items() if not ok and n in REPAIR_PACKAGES]
    if not broken:
        return imports
    packages = [REPAIR_PACKAGES[n] for n in broken]
    header("자동 복구: " + ", ".join(packages))
    subprocess.run([python, "-m", "pip", "install", "--disable-pip-version-check", *packages])
    return check_imports(python)


def check_files_and_devices():
    """(항목, 성공 여부, 설명) 목록"""
    rows = []

    def add(name, ok, detail):
        rows.append((name, bool(ok), detail))

    task = ROOT_DIR / "hand_landmarker.task"
    add("손 인식 모델 hand_landmarker.task",
        task.is_file() and task.stat().st_size > 1_000_000,
        "있음" if task.is_file() else "없음 (git lfs pull 확인)")

    # 음성 모델: install_voice_model.py 의 검사 함수 재사용
    try:
        sys.path.insert(0, str(ROOT_DIR))
        from install_voice_model import MODEL_DIR, model_problems
        problems = model_problems(MODEL_DIR) if MODEL_DIR.is_dir() else ["폴더 없음"]
        add("한국어 음성 모델 (Vosk)", not problems, "정상" if not problems else ", ".join(problems)[:80])
    except Exception as error:
        add("한국어 음성 모델 (Vosk)", False, str(error)[:80])

    sys.path.insert(0, str(GAME_DIR))
    try:
        from external_game import windows_game_home
    except Exception:
        windows_game_home = None

    if "--skip-doom" not in ARGS:
        if IS_WINDOWS and windows_game_home:
            home = Path(windows_game_home("doom"))
            ok = (home / "chocolate-doom.exe").is_file() and (home / "freedoom1.wad").is_file()
        else:
            ok = bool(shutil.which("chocolate-doom") or os.path.exists("/usr/games/chocolate-doom")) \
                and os.path.isfile("/usr/share/games/doom/freedoom1.wad")
        add("DOOM (chocolate-doom + Freedoom)", ok, "설치됨" if ok else "python install_doom.py")

    if "--skip-kart" not in ARGS:
        if IS_WINDOWS and windows_game_home:
            ok = (Path(windows_game_home("supertuxkart")) / "stk-code" / "build-x86_64" / "bin"
                  / "supertuxkart.exe").is_file()
        else:
            ok = bool(shutil.which("supertuxkart") or os.path.exists("/usr/games/supertuxkart"))
        add("SuperTuxKart", ok, "설치됨" if ok else "python install_supertuxkart.py")

    if "--skip-mario" not in ARGS:
        ok = (GAME_DIR / "mario_pygame" / "Core.py").is_file()
        add("마리오 게임 파일", ok, "설치됨" if ok else "python install_mario.py")

    if IS_LINUX:
        uinput_ok = os.access("/dev/uinput", os.R_OK | os.W_OK)
        add("가상 입력 장치 /dev/uinput", uinput_ok,
            "사용 가능" if uinput_ok else "재부팅 후 다시 점검 (input 그룹 권한)")

        cams = sorted(p.name for p in Path("/dev").glob("video*")
                      if p.name[5:].isdigit() and int(p.name[5:]) < 10)
        add("카메라 (/dev/video0~9)", bool(cams),
            ", ".join(cams) if cams else "USB 웹캠을 연결해 주세요")

        mic = ""
        if shutil.which("arecord"):
            out = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
            mic = "\n".join(l for l in out.splitlines() if l.startswith(("card", "카드")))
        add("마이크 (녹음 장치)", bool(mic),
            mic.splitlines()[0][:70] if mic else "USB 마이크를 연결해 주세요")

        try:
            temp = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
            add("CPU 온도", temp < 75, "{:.0f}°C {}".format(temp, "" if temp < 75 else "(쿨러 확인)"))
        except OSError:
            pass
    return rows


def run_checks():
    header("6. 전체 점검")
    python = game_python()
    rows = []
    if python is None:
        rows.append(("게임용 Python (.venv-pi)", False, "기본 설치(1단계)가 끝나지 않았습니다"))
    else:
        imports = check_imports(python)
        imports = repair_imports(python, imports)
        for name, (ok, detail) in imports.items():
            label = "패키지 {} - {}".format(name, PURPOSE.get(name, ""))
            rows.append((label, ok, detail if detail else "설치됨"))
    rows += check_files_and_devices()
    return rows


# ══════════════════════════════════════════════════════════
#  7. 바탕화면 실행 아이콘 (라즈베리파이)
# ══════════════════════════════════════════════════════════
def desktop_dir():
    if shutil.which("xdg-user-dir"):
        out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True).stdout.strip()
        if out:
            return Path(out)
    return Path.home() / "Desktop"


def make_launcher():
    header("7. 바탕화면 실행 아이콘")
    icon_png = GAME_DIR / "everyone_gamepad.png"
    icon_ico = GAME_DIR / "everyone_gamepad.ico"
    python = game_python()
    if python and icon_ico.is_file() and not icon_png.is_file():
        subprocess.run([python, "-c",
                        "import sys; from PIL import Image; Image.open(sys.argv[1]).save(sys.argv[2])",
                        str(icon_ico), str(icon_png)])

    content = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Every One",
        "Comment=손동작/음성으로 즐기는 게임 모음",
        # 경로에 공백이 있어도 되도록 bash -c 안에서 따옴표로 감싼다
        "Exec=bash -c 'cd \"{0}\" && ./run_raspberrypi.sh game'".format(ROOT_DIR),
        "Path={}".format(ROOT_DIR),
        "Icon={}".format(icon_png if icon_png.is_file() else "applications-games"),
        "Terminal=false",
        "Categories=Game;",
        "",
    ])

    os.chmod(ROOT_DIR / "run_raspberrypi.sh", 0o755)
    targets = [desktop_dir() / "EveryOne.desktop",
               Path.home() / ".local" / "share" / "applications" / "EveryOne.desktop"]
    for target in targets:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            os.chmod(target, 0o755)
            print("  만들었습니다: {}".format(target))
        except OSError as error:
            print("  만들지 못했습니다: {} ({})".format(target, error))

    # 파일 관리자가 '실행할까요?'를 묻지 않도록 (Raspberry Pi OS 의 PCManFM 설정)
    libfm = Path.home() / ".config" / "libfm" / "libfm.conf"
    try:
        text = libfm.read_text(encoding="utf-8") if libfm.exists() else "[config]\n"
        if "quick_exec=1" not in text:
            if "quick_exec=" in text:
                text = text.replace("quick_exec=0", "quick_exec=1")
            elif "[config]" in text:
                text = text.replace("[config]", "[config]\nquick_exec=1", 1)
            else:
                text = "[config]\nquick_exec=1\n" + text
            libfm.parent.mkdir(parents=True, exist_ok=True)
            libfm.write_text(text, encoding="utf-8")
        print("  더블클릭 시 바로 실행되도록 설정했습니다.")
    except OSError:
        pass
    return True


# ══════════════════════════════════════════════════════════
def print_summary(install_results, check_rows):
    header("결과")
    if install_results:
        print("[설치]")
        for name, ok in install_results:
            print("  {}  {}".format("성공" if ok else "실패", name))
    print("\n[점검]")
    for name, ok, detail in check_rows:
        print("  {}  {:<36} {}".format("OK  " if ok else "확인", name, detail))

    failed = [r for r in check_rows if not r[1]] + [r for r in install_results if not r[1]]
    print()
    if not failed:
        print("모든 항목이 정상입니다. 시연 준비 완료!")
    else:
        print("'확인' / '실패' 항목을 위 설명대로 처리한 뒤  python3 install_all.py --check-only  로 다시 점검하세요.")
    if IS_LINUX and any("uinput" in r[0] and not r[1] for r in check_rows):
        print("가상 입력 권한은 재부팅 후 적용됩니다: sudo reboot")


def main():
    print("Every One 전체 설치를 시작합니다. (인터넷 연결 필요, 처음에는 20~40분 걸릴 수 있어요)")
    if not (IS_LINUX or IS_WINDOWS):
        print("Windows 또는 Raspberry Pi OS에서 실행해 주세요.")
        return 1

    install_results = [] if "--check-only" in ARGS else install_steps()
    check_rows = run_checks()
    if IS_LINUX and "--no-launcher" not in ARGS and "--check-only" not in ARGS:
        make_launcher()
    print_summary(install_results, check_rows)
    if IS_WINDOWS:
        input("\n엔터를 누르면 창이 닫힙니다...")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        sys.exit(130)
