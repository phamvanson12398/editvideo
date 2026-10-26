@echo off
chcp 65001 >nul
title Director - Cai dat
cd /d "%~dp0"
echo ============================================
echo   DIRECTOR - CAI DAT LAN DAU
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [THIEU] Python chua duoc cai. Tai Python 3.11 tai https://www.python.org/downloads/
  echo         Nho tich "Add python.exe to PATH" khi cai.
  pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo [THIEU] Node.js chua duoc cai. Tai ban LTS tai https://nodejs.org/
  pause
  exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [THIEU] ffmpeg chua co trong PATH.
  echo         Tai ban "full" tai https://www.gyan.dev/ffmpeg/builds/ , giai nen,
  echo         roi them thu muc bin vao PATH ^(hoac chep ffmpeg.exe, ffprobe.exe vao thu muc nay^).
  pause
  exit /b 1
)

tasklist /fi "imagename eq director.exe" | find /i "director.exe" >nul
if not errorlevel 1 (
  echo Director dang chay ^(Studio hoac cua so dung video^). Tam tat de cai dat...
  taskkill /f /im director.exe >nul 2>nul
  timeout /t 2 >nul
)
if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Tao moi truong Python ^(.venv^)...
  python -m venv .venv || goto :loi
)

echo [2/4] Cai thu vien Python ^(lan dau mat vai phut^)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -e ".[asr,ocr,studio,export]" || goto :loi

echo [3/4] Cai Remotion ^(npm install^)...
pushd remotion
call npm install --no-audit --no-fund || (popd & goto :loi)
popd

echo [4/4] Kiem tra moi truong...
".venv\Scripts\director.exe" doctor

echo.
echo ============================================
echo   CAI DAT XONG!
echo   - Dung video: keo tha video vao file 2_DUNG_VIDEO.bat
echo   - Giao dien web: chay 4_STUDIO.bat
echo   - Muon tach thoai/nhac bang GPU: chay 5_CAI_THEM_GPU.bat
echo   - Muon dung AI Antigravity: chay 6_CAI_ANTIGRAVITY.bat
echo ============================================
pause
exit /b 0

:loi
echo.
echo CO LOI KHI CAI DAT. Chup man hinh nay gui lai de duoc ho tro.
pause
exit /b 1
