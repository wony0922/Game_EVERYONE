@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ===================================================
echo   [Learning Mode] 학습 및 테스트 모드를 시작합니다.
echo ===================================================
py -3.14 Learning_Mode.py
pause
