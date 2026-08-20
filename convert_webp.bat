@echo off
chcp 65001 >nul
title Chuyen anh sang WebP (cho nhe)
cd /d "%~dp0"

:menu
echo ============================================================
echo  CHUYEN / NEN anh sang WebP.
echo   - Mac dinh: PNG -^> WebP, xuat ra thu muc ^<ten^>_webp moi (GIU NGUYEN goc).
echo   - Re-nen anh comix.to (WebP nang) ve q85: tra loi 'y' o "Re-nen ca WebP".
echo   - NEN TAI CHO (sua thang folder goc, cho cac bo comix CU): tra loi 'y' o
echo     "Nen TAI CHO". Cach nay KHONG tao _webp -^> downloader tai tiep chuong moi
echo     vao dung folder do (khoi xoa/doi ten). Chi dung .webp, an toan (temp+verify).
echo  Dan duong dan thu muc, vd:  downloads\Overgeared
echo ============================================================
echo.
set "folder="
set /p folder="Thu muc can xu ly (Enter de thoat): "
if "%folder%"=="" goto :end
set "q="
set /p q="Chat luong WebP 1-100 (Enter = 85): "
set "inplace="
set /p inplace="Nen TAI CHO (sua thang folder goc - cho comix cu)? (y/N): "

set args="%folder%"
if not "%q%"=="" set args=%args% --quality %q%

if /i "%inplace%"=="y" goto :inplace

set "jpg="
set /p jpg="Nen ca JPG luon? (y/N): "
set "webp="
set /p webp="Re-nen ca WebP (dung cho anh comix.to)? (y/N): "
if /i "%jpg%"=="y" set args=%args% --jpg-too
if /i "%webp%"=="y" set args=%args% --webp-too
goto :run

:inplace
set args=%args% --in-place
echo.
echo   [!] Che do TAI CHO: se GHI DE anh .webp trong folder goc (co temp+verify,
echo       chi thay khi tiet kiem ^>=10%%, khong mat data). Nhan Ctrl-C de huy.

:run
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
