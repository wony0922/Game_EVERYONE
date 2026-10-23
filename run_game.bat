@echo off
title Every One - Game Launcher
chcp 65001 > nul
cd /d "%~dp0"

echo ============================================
echo    Every One - Hand Motion Game Launcher
echo ============================================
echo.

py -3.14 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.14가 설치되어 있지 않습니다.
    echo https://www.python.org 에서 Python 3.14를 설치해 주세요.
    pause
    exit /b 1
)

rem 필요한 필수 패키지 확인 및 설치
py -3.14 -c "import pygame, mediapipe, cv2, vosk, sounddevice, PIL" >nul 2>&1
if %errorlevel% neq 0 (
    echo [SETUP] 필요한 패키지를 자동으로 설치합니다...
    py -3.14 -m pip install -r requirements.txt
)

echo.
echo [START] 게임을 실행합니다...
echo.

cd /d "%~dp0Every One"
py -3.14 -X faulthandler main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 게임이 오류와 함께 종료되었습니다.
)

pause
