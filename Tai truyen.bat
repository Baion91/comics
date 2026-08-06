@echo off
chcp 65001 >nul
title Tai truyen ve may
cd /d "%~dp0"

:menu
echo ============================================================
echo  TAI TRUYEN VE MAY  (Asura / Raven / ... - tu nhan theo link)
echo  Dan link trang truyen, vd:
echo    https://ravenscans.org/series/rankers-return-remake/
echo    https://asurascans.com/comics/overgeared-1d35e5bd
echo ============================================================
echo.
set "url="
set /p url="Dan link truyen (Enter de thoat): "
if "%url%"=="" goto :end
set "ch="
set /p ch="Chuong (Enter = tat ca, vd 1-20 hoac 5,7,20-25): "
set "cbz="
set /p cbz="Dong goi .cbz de doc tren app? (y/N): "

set args=
if not "%ch%"=="" set args=--chapters "%ch%"
if /i "%cbz%"=="y" set args=%args% --cbz

echo.
python "%~dp0comic_downloader.py" "%url%" %args%

echo.
echo ------------------------------------------------------------
set "again="
set /p again="Tai truyen khac? (y/N): "
if /i "%again%"=="y" (
  echo.
  goto :menu
)

:end
echo.
echo Tam biet!
timeout /t 2 >nul
