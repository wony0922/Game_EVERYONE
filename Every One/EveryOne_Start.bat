@echo off
title Every One - Game Launcher

echo ============================================
echo    Every One - Hand Motion Game Launcher
echo ============================================
echo.

py -3.14 --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.14 is not installed.
    pause
    exit /b 1
)

rem pygame has no Python 3.14 wheel yet, so install pygame-ce (same "import pygame")
py -3.14 -c "import pygame" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INSTALL] Installing pygame-ce...
    py -3.14 -m pip install pygame-ce
)

py -3.14 -c "import mediapipe" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INSTALL] Installing mediapipe...
    py -3.14 -m pip install mediapipe
)

py -3.14 -c "import cv2" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INSTALL] Installing opencv-python...
    py -3.14 -m pip install opencv-python
)

echo.
echo [START] Launching game...
echo.

cd /d "%~dp0"
py -3.14 main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Game exited with an error.
)

pause