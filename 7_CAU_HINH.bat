@echo off
chcp 65001 >nul
title Director - Cau hinh
cd /d "%~dp0"
echo Mo file cau hinh: am luong tieng dong / nhac, ngon ngu chu, che do 720p.
echo Sua so, bam Ctrl+S de luu, roi dong Notepad.
echo   am_luong_tieng_dong: 0 = tat, 50 = mac dinh, 100 = to
notepad "%~dp0cau_hinh.json"
