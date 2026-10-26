@echo off
chcp 65001 >nul
title Director - Cai them GPU
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua cai dat. Hay chay 1_CAI_DAT.bat truoc.
  pause
  exit /b 1
)
echo Cai PyTorch ban CUDA 12.6 (ho tro GTX 10xx) + Demucs tach thoai/nhac
echo va thu vien CUDA cho Whisper chay bang GPU. Dung luong tai ve khoang 3 GB.
echo.
".venv\Scripts\python.exe" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126 || goto :loi
".venv\Scripts\python.exe" -m pip install -e ".[separation]" || goto :loi
".venv\Scripts\python.exe" -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 || goto :loi
echo.
".venv\Scripts\director.exe" doctor
echo.
echo Xong. Neu muon nang net / slow motion bang GPU, tai them:
echo   - realesrgan-ncnn-vulkan: https://github.com/xinntao/Real-ESRGAN/releases
echo   - rife-ncnn-vulkan:       https://github.com/nihui/rife-ncnn-vulkan/releases
echo roi giai nen vao thu muc assets\bin
pause
exit /b 0

:loi
echo CO LOI KHI CAI. Chup man hinh gui lai de duoc ho tro.
pause
exit /b 1
