#!/usr/bin/env bash
set -euo pipefail

# 스크립트가 있는 폴더의 상위(프로젝트 루트)로 이동하여 라즈베리파이 런처 실행
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

chmod +x "${ROOT_DIR}/run_raspberrypi.sh" 2>/dev/null || true
exec "${ROOT_DIR}/run_raspberrypi.sh" game "$@"
