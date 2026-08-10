@echo off
chcp 65001 >nul
title Lam net anh truyen - LAM LAI TOAN BO (bo qua skip)
cd /d "%~dp0"

REM ============================================================
REM  Giong lam-net.bat nhung EP LAM LAI tat ca (ke ca chuong da xong).
REM  Dung khi muon convert lai tu dau (vd doi tham so, output loi...).
REM ============================================================

python "%~dp0lam_net.py" --force

echo.
pause
