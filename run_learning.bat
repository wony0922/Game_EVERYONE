@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ===================================================
echo   [Learning Mode] 학습 및 테스트 모드를 시작합니다.
echo ===================================================
py -3.14 -c "import pygame, mediapipe, cv2, PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [SETUP] 필요한 패키지를 자동으로 설치합니다...
    py -3.14 -m pip install -r requirements.txt
)
py -3.14 Learning_Mode.py
pause
