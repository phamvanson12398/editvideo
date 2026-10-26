@echo off
chcp 65001 >nul
title Director Studio
cd /d "%~dp0"
if not exist ".venv\Scripts\director.exe" (
  echo Chua cai dat. Hay chay 1_CAI_DAT.bat truoc.
  pause
  exit /b 1
)
set PYTHONIOENCODING=utf-8
echo Dang mo Director Studio tai http://127.0.0.1:7860
echo Dong cua so nay de tat Studio.
start "" "http://127.0.0.1:7860"
".venv\Scripts\director.exe" studio --port 7860 -o "%~dp0outputs"
pause
