@echo off
echo 손 동작 인식 앱을 실행합니다...
cd /d "%~dp0"
py -3.14 -c "import pygame, mediapipe, cv2, PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [SETUP] 필요한 패키지를 자동으로 설치합니다...
    py -3.14 -m pip install -r requirements.txt
)
py -3.14 hand_app.py
pause
