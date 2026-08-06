@echo off
chcp 65001 >nul
title Kiem tra truyen da tai
cd /d "%~dp0"

:menu
echo ============================================================
echo  KIEM TRA TRUYEN DA TAI  (anh hong / cut / thieu trang / den)
echo  Enter de trong = quet ca thu vien downloads\
echo  Hoac dan duong dan 1 bo / 1 chuong de quet rieng, vd:
echo    downloads\Rankers Return Remake
echo    downloads\Rankers Return Remake\Chapter 5
echo ============================================================
echo.
set "path_arg="
set /p path_arg="Quet thu muc nao (Enter = tat ca): "
set "fixq="
set /p fixq="Cach ly (.bad) anh chac chan hong luon? (y/N): "
set "blackq="
set /p blackq="Quet sau: do them 'trang mot mau' den/trang? (cham) (y/N): "

set args=
if not "%path_arg%"=="" set args="%path_arg%"
if /i "%fixq%"=="y" set args=%args% --fix
if /i "%blackq%"=="y" set args=%args% --black

echo.
python "%~dp0check_library.py" %args%

echo.
echo ------------------------------------------------------------
echo Mo bao cao: .reader-meta\check-report.html (bang trinh duyet)
echo.
set "again="
set /p again="Kiem tra tiep? (y/N): "
if /i "%again%"=="y" (
  echo.
  goto :menu
)

:end
echo.
echo Tam biet!
timeout /t 2 >nul
