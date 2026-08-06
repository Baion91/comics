@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Tai cloudflared (tren server)
cd /d "%~dp0"

set "DEST=%~dp0.reader-meta\cloudflared.exe"
set "URL=https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

echo ============================================================
echo  TAI CLOUDFLARED tu nguon CHINH THUC cua Cloudflare (GitHub)
echo  Luu vao: .reader-meta\cloudflared.exe
echo ============================================================
echo.

if exist "%DEST%" (
  set "again="
  set /p again="Da co cloudflared.exe roi. Tai lai de cap nhat? (y/N): "
  if /i not "!again!"=="y" goto :done
)

if not exist "%~dp0.reader-meta" mkdir "%~dp0.reader-meta"

echo Dang tai... (vai chuc MB, cho chut)
rem curl co san tren Windows 10 (1803+)/11; -L de theo redirect cua GitHub
curl -L -o "%DEST%" "%URL%"

if not exist "%DEST%" (
  echo.
  echo !!! Tai bang curl that bai. Thu bang PowerShell...
  powershell -NoProfile -Command "try{Invoke-WebRequest -Uri '%URL%' -OutFile '%DEST%'}catch{exit 1}"
)

if exist "%DEST%" (
  echo.
  echo Xong. Da luu cloudflared.exe vao .reader-meta\
) else (
  echo.
  echo !!! Van khong tai duoc. Tai tay bang trinh duyet:
  echo     %URL%
  echo   roi doi ten thanh cloudflared.exe, bo vao thu muc .reader-meta\
)

:done
echo.
pause
