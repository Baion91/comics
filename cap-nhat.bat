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
echo Da co code moi. Bat lai server de ap dung...
echo.
call "%~dp0server-BAT-tudong.bat"
