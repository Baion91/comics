@echo off
chcp 65001 >nul
title Lam sach anh scan (tach trang doi, don gay, lam trang, lam net)
cd /d "%~dp0"

rem Keo-tha folder truyen / chuong vao file .bat nay = dung duong dan do luon.
set "target=%~1"
if not "%target%"=="" goto :preview

:menu
echo ============================================================
echo  LAM SACH ANH SCAN: tach trang doi, don gay, lam trang nen, don vung xam, lam net
echo  - Chon 1 folder TRUYEN (vd downloads\Mega Man World) hoac 1 folder CHUONG.
echo  - Chuong da lam sach thi bo qua. Do cua tool gom het vao 1 folder ^<truyen^>\.lam-sach\
echo    (cau-hinh.json, goc\ = ban goc, soat\ = anh soat). Reader bo qua folder nay.
echo  - To tranh lien gay van bi tach: doc thay thi bam "Join 2 pages" trong reader,
echo    hoac ghi ten anh vao .lam-sach\cau-hinh.json muc "giu_nguyen" roi chon "l".
echo  - Truyen doc trai-^>phai: sua "doc": "trai-truoc" trong .lam-sach\cau-hinh.json.
echo  - Trang nho (cao ^< 1400 px) duoc PHONG AI 2x (Real-ESRGAN, can GPU) cho net tren dien thoai.
echo    Khong muon: chon "k" ben duoi, hoac sua "phong": false trong .lam-sach\cau-hinh.json.
echo  - Anh soat (luoi gay tung chuong, anh lam thu): ^<truyen^>\.lam-sach\soat\
echo  - Chu go nham font (Calibri) giua cac bong: chon "x" xem truoc, "f" doi sang font truyen
echo    (CC Wild Words Roman, phai cai font tren may). Dong can soat: duyet / sua / bo trong
echo    .lam-sach\cau-hinh.json muc "doi_font" (huong dan trong .lam-sach\soat\doi-font\^<chuong^>\danh-sach.txt).
echo ============================================================
echo.
set "target="
set /p target="Folder truyen / chuong (Enter = thoat): "
if "%target%"=="" goto :end

:preview
echo.
echo --- KIEM TRA (chua ghi gi) ---
python "%~dp0lam_sach_scan.py" "%target%" --dry-run
if errorlevel 2 goto :again
echo.
echo   y = lam that
echo   t = lam thu 6 anh (anh truoc^|sau vao .lam-sach\soat\thu\, thu vien giu nguyen)
echo   l = lam lai chuong DA lam (tu ban goc trong .lam-sach\goc)
echo   g = tra ban goc ve cho cu (bo ban da lam sach)
echo   k = lam that nhung KHONG phong AI (giu co goc)
echo   x = soat chu lech font (anh truoc^|sau vao .lam-sach\soat\doi-font\, thu vien giu nguyen)
echo   f = doi chu lech font sang font truyen (chuong da lam sach: doi tai cho)
set "go="
set /p go="Chon y / t / l / g / k / x / f (Enter = thoi): "
echo.
if /i "%go%"=="y" python "%~dp0lam_sach_scan.py" "%target%"
if /i "%go%"=="k" python "%~dp0lam_sach_scan.py" "%target%" --khong-phong
if /i "%go%"=="x" python "%~dp0lam_sach_scan.py" "%target%" --soat-font
if /i "%go%"=="f" python "%~dp0lam_sach_scan.py" "%target%" --doi-font
if /i "%go%"=="t" python "%~dp0lam_sach_scan.py" "%target%" --thu 6
if /i "%go%"=="l" python "%~dp0lam_sach_scan.py" "%target%" --lam-lai
if /i "%go%"=="g" python "%~dp0lam_sach_scan.py" "%target%" --tra-goc

:again
echo.
echo ------------------------------------------------------------
set "again="
set /p again="Lam truyen / chuong khac? (y/N): "
if /i "%again%"=="y" (
  echo.
  goto :menu
)

:end
echo.
echo Tam biet!
timeout /t 2 >nul
