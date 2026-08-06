@echo off
chcp 65001 >nul
title Chuyen anh sang WebP (cho nhe)
cd /d "%~dp0"

:menu
echo ============================================================
echo  CHUYEN ANH PNG -^> WEBP (xuat ra thu muc ^<ten^>_webp moi,
echo  GIU NGUYEN thu muc goc). JPG mac dinh chi copy (khong nen lai).
echo  Dan duong dan thu muc can chuyen, vd:
echo    downloads\Pokemon Special
echo ============================================================
echo.
set "folder="
set /p folder="Thu muc can chuyen (Enter de thoat): "
if "%folder%"=="" goto :end
set "q="
set /p q="Chat luong WebP 1-100 (Enter = 85): "
set "jpg="
set /p jpg="Nen ca JPG luon? (y/N): "

set args="%folder%"
if not "%q%"=="" set args=%args% --quality %q%
if /i "%jpg%"=="y" set args=%args% --jpg-too

echo.
python "%~dp0convert_webp.py" %args%

echo.
echo ------------------------------------------------------------
set "again="
set /p again="Chuyen thu muc khac? (y/N): "
if /i "%again%"=="y" (
  echo.
  goto :menu
)

:end
echo.
echo Tam biet!
timeout /t 2 >nul
