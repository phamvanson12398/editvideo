@echo off
chcp 65001 >nul
title Director - Dung video
cd /d "%~dp0"
if not exist ".venv\Scripts\director.exe" (
  echo Chua cai dat. Hay chay 1_CAI_DAT.bat truoc.
  pause
  exit /b 1
)
set PYTHONIOENCODING=utf-8

rem Cach dung: keo tha 1 hoac nhieu file video vao file .bat nay, hoac chay roi dan duong dan.
if "%~1"=="" (
  ".venv\Scripts\director.exe" edit --ask -o "%~dp0outputs"
  goto :xong
)

:moi_video
if "%~1"=="" goto :xong
echo.
echo ============================================
echo   Video: %~nx1
echo ============================================
".venv\Scripts\director.exe" edit "%~1" --ask -o "%~dp0outputs"
shift
goto :moi_video

:xong
echo.
echo Ket qua nam trong thu muc outputs.
if exist "%~dp0outputs" start "" explorer "%~dp0outputs"
pause
