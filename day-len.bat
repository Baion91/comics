@echo off
chcp 65001 >nul
title Day code len GitHub
cd /d "%~dp0"

echo ============================================================
echo  DAY CODE LEN GITHUB (chay tren MAY DEV cua ban)
echo  - git add + commit + push len origin/main
echo ============================================================
echo.

rem --- co gi de day khong? ---
git status --short
echo.

set "MSG="
set /p "MSG=Ghi chu commit (Enter de dung mac dinh): "
if "%MSG%"=="" set "MSG=cap nhat %DATE% %TIME%"

git add -A
git commit -m "%MSG%"
if errorlevel 1 (
  echo.
  echo (Khong co thay doi nao de commit - co the code da day roi.)
)

echo.
echo Dang push len GitHub...
git push origin main
if errorlevel 1 (
  echo.
  echo !!! Push loi. Kiem tra mang / dang nhap GitHub.
) else (
  echo.
  echo Xong. Da day len GitHub. Tren server chay cap-nhat.bat hoac nhan /update cho bot.
)
echo.
pause
