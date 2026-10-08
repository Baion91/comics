@echo off
chcp 65001 >nul
title Nhap truyen PDF vao thu vien
cd /d "%~dp0"

rem Keo-tha file/folder vao file .bat nay = dung duong dan do luon.
set "target=%~1"
if not "%target%"=="" goto :preview

:menu
echo ============================================================
echo  NHAP TRUYEN PDF  (moi tap -^> 1 thu muc "Tap NN" anh JPEG goc)
echo  - PDF dat THANG trong folder truyen = 1 file 1 tap, vd:
echo      downloads\Doraemon truyen dai\Long 1 LITE.pdf
echo    So tap lay tu ten file (Tap/Vol/Chuong/Chapter... hoac so dau tien).
echo  - 1 tap bi tach nhieu file PDF: bo chung vao 1 folder con cua truyen, vd:
echo      downloads\Doraemon truyen dai\14 - Ba chang hiep si mong mo\*.pdf
echo    -^> GOP thanh 1 tap. So tap lay tu ten folder, phan xep theo so trong ten file.
echo  PDF goc duoc cat vao ^<folder truyen^>\.pdf-goc\ (doc thu on thi tu xoa).
echo  Enter de trong = tim PDF trong ca thu vien downloads\
echo ============================================================
echo.
set "target="
set /p target="Folder / file PDF (Enter = tat ca): "

:preview
echo.
echo --- KIEM TRA (chua ghi gi) ---
if "%target%"=="" goto :preview_all
python "%~dp0pdf_import.py" "%target%" --dry-run
goto :ask
:preview_all
python "%~dp0pdf_import.py" --dry-run

:ask
if errorlevel 2 goto :again
echo.
set "go="
set /p go="Tien hanh tach? (y/N): "
if /i not "%go%"=="y" goto :again
echo.
if "%target%"=="" goto :run_all
python "%~dp0pdf_import.py" "%target%"
goto :again
:run_all
python "%~dp0pdf_import.py"

:again
echo.
echo ------------------------------------------------------------
set "again="
set /p again="Nhap PDF khac? (y/N): "
if /i "%again%"=="y" (
  echo.
  goto :menu
)

echo.
echo Tam biet!
timeout /t 2 >nul
