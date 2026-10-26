#!/usr/bin/env python3
"""Raspberry Pi OS용 음성인식(Vosk 한국어) 설치 스크립트.

설치하는 것
  1. 시스템 패키지: libportaudio2 (sounddevice가 마이크를 쓰려면 필요)
  2. Python 패키지: vosk, sounddevice  ->  .venv-pi 가상환경에 설치
     (run_raspberrypi.sh 와 같은 가상환경을 사용)
  3. 한국어 모델: Every One/vosk-model-small-ko-0.22
     - 이미 있고 정상이면 건너뜀
     - Git LFS 포인터만 받아진 경우(파일이 깨진 경우) 다시 내려받음

사용법 (프로젝트 루트에서)
  python3 install_voice_model.py              # 전체 설치
  python3 install_voice_model.py --force      # 모델을 무조건 다시 받기
  python3 install_voice_model.py --zip 파일.zip  # 미리 받아둔 zip으로 설치(오프라인)
  python3 install_voice_model.py --skip-verify   # 모델 로딩 테스트 생략
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------- 설정 ----
ROOT_DIR = Path(__file__).resolve().parent
GAME_DIR = ROOT_DIR / "Every One"
MODEL_NAME = "vosk-model-small-ko-0.22"
MODEL_DIR = GAME_DIR / MODEL_NAME
MODEL_URL = "https://alphacephei.com/vosk/models/{}.zip".format(MODEL_NAME)

VENV_DIR = ROOT_DIR / ".venv-pi"
VENV_PYTHON = VENV_DIR / "bin" / "python"

# voice_dependencies.py / requirements-raspberrypi.txt 와 같은 버전
PIP_PACKAGES = ["vosk==0.3.45", "sounddevice==0.5.6"]
APT_PACKAGES = ["libportaudio2"]

# 모델이 정상인지 판단할 파일과 최소 크기(byte)
REQUIRED_MODEL_FILES = {
    "am/final.mdl": 1_000_000,
    "conf/mfcc.conf": 10,
    "conf/model.conf": 10,
    "graph/Gr.fst": 1_000_000,
    "graph/HCLr.fst": 1_000_000,  # LFS 포인터면 130byte 정도라 여기서 걸러짐
    "graph/phones/word_boundary.int": 10,
    "ivector/final.ie": 1_000_000,
    "ivector/final.dubm": 10_000,
    "ivector/final.mat": 1_000,
    "ivector/global_cmvn.stats": 10,
    "ivector/online_cmvn.conf": 10,
    "ivector/splice.conf": 10,
}


# ---------------------------------------------------------------- 출력 ----
def step(msg):
    print("\n\033[1;36m==> {}\033[0m".format(msg), flush=True)


def ok(msg):
    print("  \033[32m[OK]\033[0m {}".format(msg), flush=True)


def warn(msg):
    print("  \033[33m[주의]\033[0m {}".format(msg), flush=True)


def fail(msg):
    print("\n\033[31m[실패]\033[0m {}".format(msg), file=sys.stderr, flush=True)
    sys.exit(1)


# ------------------------------------------------------------ 환경 확인 ----
def check_platform():
    step("환경 확인")
    if not sys.platform.startswith("linux"):
        fail("이 스크립트는 Raspberry Pi OS(리눅스)용입니다. 현재: {}".format(sys.platform))

    os_name = "알 수 없음"
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                os_name = line.split("=", 1)[1].strip('"')
    except OSError:
        pass

    arch = os.uname().machine
    ok("OS: {} / {}".format(os_name, arch))
    ok("Python: {}".format(sys.version.split()[0]))
    if arch != "aarch64":
        warn("64비트 OS(aarch64)가 아닙니다. mediapipe 등 다른 패키지가 설치되지 않을 수 있어요.")


# ------------------------------------------------------- 시스템 패키지 ----
def is_apt_installed(package):
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${db:Status-Status}", package],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "installed"


def install_apt_packages():
    step("시스템 패키지 확인: {}".format(", ".join(APT_PACKAGES)))
    if shutil.which("dpkg-query") is None:
        warn("dpkg가 없는 환경이라 건너뜁니다.")
        return

    missing = [p for p in APT_PACKAGES if not is_apt_installed(p)]
    if not missing:
        ok("이미 설치되어 있습니다.")
        return

    sudo = [] if os.geteuid() == 0 else ["sudo"]
    print("  설치합니다: {} (비밀번호를 물어볼 수 있어요)".format(", ".join(missing)))
    try:
        subprocess.run(sudo + ["apt-get", "update"], check=True)
        subprocess.run(sudo + ["apt-get", "install", "-y"] + missing, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        fail("apt 설치 실패: {}\n직접 실행해 보세요: sudo apt install {}".format(
            error, " ".join(missing)))
    ok("설치 완료")


# ------------------------------------------------------ Python 패키지 ----
def ensure_venv():
    step("Python 가상환경 확인: {}".format(VENV_DIR.name))
    if VENV_PYTHON.exists():
        ok("기존 가상환경을 사용합니다.")
        return
    print("  가상환경을 새로 만듭니다...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        fail("가상환경 생성 실패: {}\n'sudo apt install python3-venv' 후 다시 실행해 주세요.".format(error))
    ok("생성 완료")


def install_pip_packages():
    step("Python 패키지 설치: {}".format(", ".join(PIP_PACKAGES)))
    command = [str(VENV_PYTHON), "-m", "pip", "install",
               "--disable-pip-version-check", *PIP_PACKAGES]
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        fail("pip 설치 실패: {}\n인터넷 연결을 확인해 주세요.".format(error))
    ok("설치 완료")


# ------------------------------------------------------------- 모델 -------
def model_problems(model_dir):
    """모델 폴더에서 빠졌거나 깨진 파일 목록을 돌려준다. 비어 있으면 정상."""
    problems = []
    for rel_path, min_size in REQUIRED_MODEL_FILES.items():
        path = model_dir / rel_path
        if not path.is_file():
            problems.append("{} (없음)".format(rel_path))
            continue
        size = path.stat().st_size
        if size < min_size:
            with open(path, "rb") as f:
                head = f.read(40)
            if head.startswith(b"version https://git-lfs"):
                problems.append("{} (Git LFS 포인터만 있음)".format(rel_path))
            else:
                problems.append("{} (크기 {}byte, 손상 의심)".format(rel_path, size))
    return problems


def download(url, dest):
    print("  내려받는 중: {}".format(url))
    request = urllib.request.Request(url, headers={"User-Agent": "EveryOne-installer"})
    with urllib.request.urlopen(request, timeout=30) as response, open(dest, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        last_print = 0.0
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            now = time.time()
            if now - last_print > 0.5:
                last_print = now
                if total:
                    print("\r  {:5.1f}%  ({:.1f} / {:.1f} MB)".format(
                        done * 100 / total, done / 1e6, total / 1e6), end="", flush=True)
                else:
                    print("\r  {:.1f} MB".format(done / 1e6), end="", flush=True)
    print("\r  다운로드 완료 ({:.1f} MB)            ".format(done / 1e6), flush=True)


def extract_model(zip_path):
    """zip을 임시 폴더에 풀고 모델 폴더를 MODEL_DIR 위치로 옮긴다."""
    print("  압축 해제 중...")
    with tempfile.TemporaryDirectory(dir=GAME_DIR) as tmp:
        tmp = Path(tmp)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmp)
        except zipfile.BadZipFile:
            fail("zip 파일이 손상되었습니다: {}".format(zip_path))

        # zip 안에서 am/final.mdl 이 있는 폴더를 모델 루트로 본다
        candidates = [p.parent.parent for p in tmp.rglob("am/final.mdl")]
        if not candidates:
            fail("zip 안에서 Vosk 모델을 찾지 못했습니다.")
        extracted = candidates[0]

        problems = model_problems(extracted)
        if problems:
            fail("내려받은 모델이 불완전합니다:\n  " + "\n  ".join(problems))

        if MODEL_DIR.exists():
            backup = MODEL_DIR.with_name(MODEL_NAME + ".broken")
            if backup.exists():
                shutil.rmtree(backup)
            MODEL_DIR.rename(backup)
            warn("기존 모델 폴더를 {} 로 옮겨 두었습니다.".format(backup.name))
            shutil.move(str(extracted), str(MODEL_DIR))
            shutil.rmtree(backup, ignore_errors=True)
        else:
            shutil.move(str(extracted), str(MODEL_DIR))


def install_model(force=False, zip_file=None):
    step("한국어 음성인식 모델 확인: {}".format(MODEL_NAME))
    if not GAME_DIR.is_dir():
        fail("'Every One' 폴더를 찾을 수 없습니다. 이 파일을 프로젝트 루트(Game_EVERYONE)에 두고 실행해 주세요.")

    if MODEL_DIR.is_dir() and not force:
        problems = model_problems(MODEL_DIR)
        if not problems:
            ok("모델이 이미 정상적으로 설치되어 있습니다.")
            return
        warn("모델 파일에 문제가 있어 다시 설치합니다:")
        for p in problems:
            print("      - {}".format(p))
        if any("LFS" in p for p in problems):
            print("      (git-lfs 없이 clone하면 이렇게 됩니다. 'sudo apt install git-lfs && git lfs pull'로도 해결할 수 있어요.)")

    if zip_file:
        zip_path = Path(zip_file).expanduser().resolve()
        if not zip_path.is_file():
            fail("zip 파일이 없습니다: {}".format(zip_path))
        extract_model(zip_path)
    else:
        free_mb = shutil.disk_usage(GAME_DIR).free / 1e6
        if free_mb < 600:
            fail("저장 공간이 부족합니다 (남은 공간 {:.0f}MB, 600MB 이상 필요).".format(free_mb))
        fd, tmp_zip = tempfile.mkstemp(suffix=".zip", dir=GAME_DIR)
        os.close(fd)
        try:
            try:
                download(MODEL_URL, tmp_zip)
            except Exception as error:
                fail("모델 다운로드 실패: {}\n인터넷 연결을 확인하거나, 다른 PC에서 아래 주소로 받은 뒤 "
                     "--zip 옵션으로 설치해 주세요:\n  {}".format(error, MODEL_URL))
            extract_model(tmp_zip)
        finally:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
    ok("모델 설치 완료: {}".format(MODEL_DIR))


# ------------------------------------------------------------- 검증 -------
VERIFY_CODE = r"""
import sys
from vosk import Model, KaldiRecognizer, SetLogLevel
SetLogLevel(-1)
model = Model(sys.argv[1])
KaldiRecognizer(model, 16000)
print("모델 로딩 성공")
try:
    import sounddevice as sd
    dev = sd.query_devices(kind="input")
    print("기본 마이크: {}".format(dev["name"]))
except Exception as e:
    print("MIC_WARN: {}".format(e))
"""


def verify():
    step("설치 확인 (모델 로딩에 10~30초 걸릴 수 있어요)")
    result = subprocess.run(
        [str(VENV_PYTHON), "-c", VERIFY_CODE, str(MODEL_DIR)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        fail("모델을 불러오지 못했습니다:\n{}".format(result.stderr.strip()[-1500:]))
    for line in result.stdout.strip().splitlines():
        if line.startswith("MIC_WARN:"):
            warn("마이크를 찾지 못했습니다. USB 마이크 연결을 확인해 주세요. ({})".format(
                line[len("MIC_WARN:"):].strip()))
        else:
            ok(line)


# ------------------------------------------------------------- main -------
def main():
    parser = argparse.ArgumentParser(description="Every One 음성인식(Vosk 한국어) 설치")
    parser.add_argument("--force", action="store_true", help="모델을 무조건 다시 내려받기")
    parser.add_argument("--zip", metavar="파일", help="미리 받아둔 모델 zip으로 설치")
    parser.add_argument("--skip-verify", action="store_true", help="설치 후 로딩 테스트 생략")
    args = parser.parse_args()

    print("Every One 음성인식 설치를 시작합니다.")
    check_platform()
    install_apt_packages()
    ensure_venv()
    install_pip_packages()
    install_model(force=args.force, zip_file=args.zip)
    if not args.skip_verify:
        verify()

    print("\n\033[1;32m음성인식 설치가 끝났습니다!\033[0m")
    print("게임 실행: ./run_raspberrypi.sh")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        sys.exit(130)
