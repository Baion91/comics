@echo off
chcp 65001 >nul
title Tai hang loat (nhieu truyen mot luot)
cd /d "%~dp0"

set "QUEUE=%~dp0download-queue.txt"

rem --- tao file mau neu chua co ---
if not exist "%QUEUE%" (
  >  "%QUEUE%" echo # HANG DOI TAI TRUYEN - moi dong 1 link. Dong trong va dong # bi bo qua.
  >> "%QUEUE%" echo # Dan link vao duoi day roi luu lai. Vi du:
  >> "%QUEUE%" echo # https://dilib.vn/hiep-si-giay-origami-fighter-16189.html
)

echo ============================================================
echo  TAI HANG LOAT: dan nhieu link (moi dong 1), chay lan luot 1 -^> het.
echo  - 1 bo loi thi bo qua chay tiep; bi chan IP thi dung ca me.
echo  - Chuong da tai du (.done) tu bo qua khi chay lai -^> update rat nhanh.
echo ============================================================
echo.
echo Mo file danh sach... DAN link, LUU lai, roi DONG Notepad de bat dau.
start /wait notepad "%QUEUE%"

set "cbz="
set /p cbz="Dong goi .cbz de doc tren app? (y/N): "
set "recheck="
set /p recheck="Quet lai ca chuong da .done? (cham hon) (y/N): "

set args=
if /i "%cbz%"=="y" set args=%args% --cbz
if /i "%recheck%"=="y" set args=%args% --recheck

echo.
python "%~dp0comic_downloader.py" --list "%QUEUE%" %args%

echo.
echo ------------------------------------------------------------
echo Xong. Chay lai file nay bat cu luc nao de tai bo moi / cap nhat chuong moi.
pause
