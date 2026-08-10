@echo off
chcp 65001 >nul
title Lam net anh truyen (Real-ESRGAN)
cd /d "%~dp0"

REM ============================================================
REM  Bo anh vao input\ (anh phang HOAC cac folder chuong con)
REM  roi bam dup file nay. Ket qua ra output-realesrgan\ (PNG 2x).
REM  Toan bo logic (sort chuong, tien do, bo qua anh loi) o lam_net.py
REM ============================================================

python "%~dp0lam_net.py"

echo.
pause
