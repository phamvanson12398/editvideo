@echo off
chcp 65001 >nul
title Director - Dat API Claude
echo Dan API key Claude (bat dau bang sk-ant-...) roi bam Enter.
echo Bo trong va bam Enter de huy.
set /p KEY=API key: 
if "%KEY%"=="" exit /b 0
setx ANTHROPIC_API_KEY "%KEY%" >nul
echo.
echo Da luu. Dong va mo lai cac file .bat de ap dung.
pause
