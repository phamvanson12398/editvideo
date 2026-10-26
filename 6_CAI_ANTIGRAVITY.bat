@echo off
chcp 65001 >nul
title Director - Cai Antigravity CLI
echo Tool dung Antigravity CLI (agy) cua Google lam AI:
echo   hieu cau chuyen, len ke hoach dung, xem ban nhap va tu sua.
echo   Dang nhap bang tai khoan Google, KHONG can API key.
echo.
where agy >nul 2>nul
if not errorlevel 1 goto :dangnhap
if exist "%LOCALAPPDATA%\agy\bin\agy.exe" goto :dangnhap

echo [1/2] Cai Antigravity CLI...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://antigravity.google/cli/install.ps1 | iex"
if errorlevel 1 (
  echo.
  echo Cai tu dong khong thanh cong. Hay cai thu cong theo huong dan tai:
  echo   https://antigravity.google/docs/cli
  start "" "https://antigravity.google/docs/cli"
  pause
  exit /b 1
)

:dangnhap
echo.
echo [2/2] Dang nhap: cua so agy se mo, chon dang nhap bang tai khoan Google.
echo       Dang nhap xong, go /quit ^(hoac Ctrl+C^) de thoat ve day.
echo.
set "PATH=%LOCALAPPDATA%\agy\bin;%PATH%"
agy
echo.
"%~dp0.venv\Scripts\director.exe" doctor
echo.
echo Xong. Dong va mo lai cac file .bat de tool nhan Antigravity.
pause
