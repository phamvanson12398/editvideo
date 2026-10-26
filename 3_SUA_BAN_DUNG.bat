@echo off
chcp 65001 >nul
title Director - Sua ban dung
cd /d "%~dp0"
if not exist ".venv\Scripts\director.exe" (
  echo Chua cai dat. Hay chay 1_CAI_DAT.bat truoc.
  pause
  exit /b 1
)
set PYTHONIOENCODING=utf-8

rem Keo tha file *.plan.json vao day de sua ban do; khong keo gi = sua ban dung gan nhat.
if "%~1"=="" (
  ".venv\Scripts\director.exe" revise last -o "%~dp0outputs"
) else (
  ".venv\Scripts\director.exe" revise "%~1" -o "%~dp0outputs"
)
echo.
if exist "%~dp0outputs" start "" explorer "%~dp0outputs"
pause
