@echo off
chcp 65001 >nul
title Lam net anh truyen (Real-ESRGAN)
cd /d "%~dp0"

REM ============================================================
REM  Bo anh vao input\ (anh phang HOAC cac folder chuong con)
REM  roi chay file nay. Ket qua ra output-realesrgan\ (PNG 2x).
REM  Mac dinh: bo qua chuong da xong. Chon 'y' de lam lai tat ca.
REM ============================================================

echo ============================================================
echo   LAM NET ANH TRUYEN (Real-ESRGAN)
echo   Bo anh / folder chuong vao input\  roi tiep tuc.
echo ============================================================
echo.
set "REDO="
set /p REDO="Lam lai ca chuong DA XONG? (y/N): "

echo.
if /i "%REDO%"=="y" (
  python "%~dp0lam_net.py" --force
) else (
  python "%~dp0lam_net.py"
)

echo.
pause
