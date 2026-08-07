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
set /a "try=0"

:RETRY
set /a "try+=1"
python "%~dp0comic_downloader.py" --list "%QUEUE%" %args%
set "rc=%errorlevel%"

echo.
echo ------------------------------------------------------------
if "%rc%"=="0" goto DONE
if "%rc%"=="2" goto BLOCKED

rem rc khac 0 va 2 = trinh tai KET THUC BAT THUONG (Python sap tang C, mat dien,
rem bi tat may...) -> CHUA tai xong. Tu chay lai: chuong .done se tu bo qua nen
rem chi tai tiep cho do, rat nhanh. Chan 5 lan de khong lap vo han neu loi lap lai.
echo *** Lan chay #%try% KET THUC BAT THUONG (ma loi %rc%) -- CHUA tai xong. ***
if %try% GEQ 5 (
  echo *** Da tu chay lai 5 lan van chua xong -^> dung lai de tranh lap vo han. ***
  echo *** Xem .reader-meta\crash-trace.txt + download-log.txt de biet anh/chuong gay loi. ***
  goto ENDPAUSE
)
echo *** Tu chay lai de tai tiep cho do (chuong da .done tu bo qua)... ***
timeout /t 5 >nul
goto RETRY

:BLOCKED
echo *** BI CHAN IP (429/403/503) -- ngung de giu uy tin IP. ***
echo *** Cho mot lat (429 ~1 gio; 403/503 vai gio) roi chay lai file nay de tai tiep. ***
goto ENDPAUSE

:DONE
echo Xong THAT SU. Chay lai file nay bat cu luc nao de tai bo moi / cap nhat chuong moi.

:ENDPAUSE
pause
