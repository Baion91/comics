@echo off
chcp 65001 >nul
title Cap nhat code tu GitHub + restart
cd /d "%~dp0"

echo ============================================================
echo  CAP NHAT CODE (chay tren MAY SERVER)
echo  - Keo code moi nhat tu GitHub (fetch + reset --hard origin/main)
echo  - Khong dung downloads/ va .reader-meta (da .gitignore)
echo  - Sau do bat lai server (server-BAT tu kill cai cu -> khong lo 409)
echo ============================================================
echo.
pause

echo Dang keo code moi nhat...
git fetch origin
if errorlevel 1 (
  echo !!! Khong fetch duoc. Kiem tra mang / URL repo. Dung lai.
  echo.
  pause
  exit /b 1
)
git reset --hard origin/main
if errorlevel 1 (
  echo !!! reset that bai. Dung lai.
  echo.
  pause
  exit /b 1
)

echo.
echo Dang cai/cap nhat thu vien Python (requests, Pillow, Playwright)...
python -m pip install -r requirements.txt
if errorlevel 1 echo !!! pip install loi - tool tai co the thieu thu vien (van chay tiep).
rem Chromium de TRONG project (.reader-meta\pw-browsers) - KHONG dung AppData
rem (PC cong ty chan load DLL duoi AppData -> chrome khong khoi dong duoc).
rem comix_site.py cung tro vao dung cho nay luc chay.
set "PLAYWRIGHT_BROWSERS_PATH=%~dp0.reader-meta\pw-browsers"
python -m playwright install chromium
if errorlevel 1 echo !!! playwright install loi - tai comix.to se KHONG chay (site khac khong anh huong).

echo.
echo Da co code moi. Bat lai server de ap dung...
echo.
call "%~dp0server-BAT-tudong.bat"
