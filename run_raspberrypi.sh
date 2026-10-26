#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-game}"
if [[ $# -gt 0 ]]; then
    shift
fi

if [[ ! -r /etc/os-release ]]; then
    printf 'Raspberry Pi OS 또는 Debian 계열 OS에서 실행해 주세요.\n' >&2
    exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "raspbian" && "${ID:-}" != "debian" ]]; then
    printf '지원하지 않는 OS입니다: %s (Raspberry Pi OS 64-bit가 필요합니다.)\n' \
        "${PRETTY_NAME:-${ID:-unknown}}" >&2
    exit 1
fi

ARCH="$(uname -m)"
if [[ "${ARCH}" != "aarch64" ]]; then
    printf '64비트 ARM OS가 필요합니다. 현재 아키텍처: %s\n' "${ARCH}" >&2
    exit 1
fi

OS_VERSION="${VERSION_ID:-0}"
OS_MAJOR="${OS_VERSION%%.*}"
if [[ ! "${OS_MAJOR}" =~ ^[0-9]+$ ]] || (( OS_MAJOR < 12 )); then
    printf 'Raspberry Pi OS Bookworm (버전 12) 이상이 필요합니다. 현재 버전: %s\n' \
        "${VERSION_ID:-unknown}" >&2
    exit 1
fi

if [[ ! -f "${ROOT_DIR}/hand_landmarker.task" ]]; then
    printf 'MediaPipe 모델 파일을 찾을 수 없습니다: %s\n' \
        "${ROOT_DIR}/hand_landmarker.task" >&2
    exit 1
fi

case "${MODE}" in
    game|learning|hand-app)
        ;;
    *)
        printf '사용법: %s [game|learning|hand-app]\n' "$0" >&2
        exit 2
        ;;
esac

APT_PACKAGES=(
    python3-venv
    python3-tk
    libgl1
    libglib2.0-0
    libsm6
    libxext6
    libxrender1
    libsdl2-2.0-0
    libportaudio2
    fonts-noto-cjk
    wget
    unzip
)

if (( OS_MAJOR >= 13 )); then
    APT_PACKAGES+=(libasound2t64)
else
    APT_PACKAGES+=(libasound2)
fi

MISSING_PACKAGES=()
for package in "${APT_PACKAGES[@]}"; do
    if ! dpkg-query -W -f='${db:Status-Status}' "${package}" 2>/dev/null \
        | grep -qx installed; then
        MISSING_PACKAGES+=("${package}")
    fi
done

if [[ ${#MISSING_PACKAGES[@]} -gt 0 ]]; then
    if [[ "${EUID}" -eq 0 ]]; then
        SUDO=()
    elif command -v sudo >/dev/null 2>&1; then
        SUDO=(sudo)
    else
        printf '시스템 패키지 설치에 sudo가 필요합니다.\n' >&2
        exit 1
    fi

    printf '필요한 Raspberry Pi OS 패키지를 설치합니다: %s\n' \
        "${MISSING_PACKAGES[*]}"
    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y "${MISSING_PACKAGES[@]}"
fi

# 사용자 video, audio 그룹 권한 자동 확인 및 추가
CURRENT_USER="${SUDO_USER:-${USER:-$(id -un)}}"
MISSING_GROUPS=()
for grp in video audio; do
    if ! id -nG "${CURRENT_USER}" 2>/dev/null | grep -qw "${grp}"; then
        MISSING_GROUPS+=("${grp}")
    fi
done

if [[ ${#MISSING_GROUPS[@]} -gt 0 ]]; then
    printf '사용자(%s) 권한 보장을 위해 %s 그룹에 추가합니다.\n' "${CURRENT_USER}" "${MISSING_GROUPS[*]}"
    if [[ "${EUID}" -eq 0 ]]; then
        for grp in "${MISSING_GROUPS[@]}"; do
            usermod -aG "${grp}" "${CURRENT_USER}" || true
        done
    elif command -v sudo >/dev/null 2>&1; then
        for grp in "${MISSING_GROUPS[@]}"; do
            sudo usermod -aG "${grp}" "${CURRENT_USER}" || true
        done
    fi
fi

# 카메라 장치 사전 진단
if ! ls /dev/video* >/dev/null 2>&1; then
    printf '[안내] /dev/video* 장치가 감지되지 않았습니다. USB 웹캠을 연결해 주세요.\n'
fi

VENV_DIR="${ROOT_DIR}/.venv-pi"
VENV_PYTHON="${VENV_DIR}/bin/python"
if [[ ! -x "${VENV_PYTHON}" ]]; then
    printf 'Python 가상환경을 만듭니다: %s\n' "${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
fi

REQUIREMENTS="${ROOT_DIR}/requirements-raspberrypi.txt"
INSTALL_KEY="$("${VENV_PYTHON}" --version 2>&1)-${ARCH}-$(sha256sum "${REQUIREMENTS}" | cut -d ' ' -f 1)"
INSTALL_MARKER="${VENV_DIR}/.requirements-raspberrypi"
if [[ ! -f "${INSTALL_MARKER}" ]] || [[ "$(<"${INSTALL_MARKER}")" != "${INSTALL_KEY}" ]]; then
    printf 'Python 패키지를 설치/갱신합니다. 인터넷 연결이 필요합니다.\n'
    "${VENV_PYTHON}" -m pip install --upgrade pip
    "${VENV_PYTHON}" -m pip install -r "${REQUIREMENTS}"
    printf '%s\n' "${INSTALL_KEY}" > "${INSTALL_MARKER}"
fi

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    printf '그래픽 데스크톱 세션이 감지되지 않았습니다. Raspberry Pi OS 데스크톱에서 실행해 주세요.\n' >&2
    exit 1
fi

# 한국어 Vosk 음성인식 모델 무결성 검사 (Git LFS 포인터/손상 자동 감지 시 공식 원본 다운로드)
VOSK_DIR="${ROOT_DIR}/Every One/vosk-model-small-ko-0.22"
HCLR_FILE="${VOSK_DIR}/graph/HCLr.fst"
NEED_DOWNLOAD=false

if [[ ! -f "${HCLR_FILE}" ]]; then
    NEED_DOWNLOAD=true
else
    FILE_SIZE=$(wc -c < "${HCLR_FILE}" 2>/dev/null || echo 0)
    # 정상 HCLr.fst는 약 180MB. 10MB 미만이거나 헤더가 'vers'(Git LFS 포인터)이면 손상
    if (( FILE_SIZE < 10485760 )); then
        NEED_DOWNLOAD=true
    elif head -c 4 "${HCLR_FILE}" 2>/dev/null | grep -q "^vers"; then
        NEED_DOWNLOAD=true
    fi
fi

if [[ "${NEED_DOWNLOAD}" = true ]]; then
    printf '[음성 모델] 한국어 Vosk 공식 원본 모델을 다운로드합니다 (약 180MB)...\n'
    rm -rf "${VOSK_DIR}"
    TMP_ZIP="${ROOT_DIR}/Every One/vosk_model_tmp.zip"
    wget -q --show-progress -O "${TMP_ZIP}" "https://alphacephei.com/vosk/models/vosk-model-small-ko-0.22.zip"
    unzip -q -o "${TMP_ZIP}" -d "${ROOT_DIR}/Every One"
    rm -f "${TMP_ZIP}"
    printf '[음성 모델] 공식 모델 설치가 완료되었습니다.\n'
fi

case "${MODE}" in
    game)
        cd -- "${ROOT_DIR}/Every One"
        exec "${VENV_PYTHON}" main.py "$@"
        ;;
    learning)
        cd -- "${ROOT_DIR}"
        exec "${VENV_PYTHON}" Learning_Mode.py "$@"
        ;;
    hand-app)
        cd -- "${ROOT_DIR}"
        exec "${VENV_PYTHON}" hand_app.py "$@"
        ;;
esac
