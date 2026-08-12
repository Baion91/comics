@echo off
chcp 65001 >nul
title BAT tu dong (chi chay tren SERVER)
cd /d "%~dp0"

echo ============================================================
echo  BAT CO CHE TU DONG (chay tren MAY SERVER, KHONG chay tren may dev)
echo  - Dang ky chay lai khi DANG NHAP Windows (song qua reboot)
echo  - Bat supervisor NGAY: giu reader + cloudflared, gui link Telegram
echo  Phuong an A: muon server tu len sau reboot ma KHONG can go mat
echo  khau -^> chay them server-AUTOLOGIN.bat MOT lan de bat tu dang nhap.
echo ============================================================
echo.

rem --- chon Python: uu tien venv neu co ---
set "PY=python"
set "PYW=pythonw"
if exist "%~dp0.venv\Scripts\python.exe"  set "PY=%~dp0.venv\Scripts\python.exe"
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PYW=%~dp0.venv\Scripts\pythonw.exe"
rem --- Task onlogon KHONG co PATH cua user -> ten tran 'python'/'pythonw' se loi
rem     0x80070002 (file not found). Doi sang DUONG DAN TUYET DOI de task chay duoc. ---
if /i "%PYW%"=="pythonw" for /f "delims=" %%i in ('where pythonw 2^>nul') do set "PYW=%%i"
if /i "%PYW%"=="pythonw" for /f "delims=" %%i in ('where python 2^>nul') do set "PYW=%%~dpipythonw.exe"
rem --- Phuong an A: task onlogon dung python.exe (CO cua so log) thay vi pythonw an.
rem     Suy PY tu PYW da resolve tuyet doi -> chac chan cung thu muc, khoi le thuoc PATH. ---
if /i "%PY%"=="python" if /i not "%PYW%"=="pythonw" call set "PY=%%PYW:pythonw.exe=python.exe%%"

rem --- tao notify-config.json tu mau neu chua co (dien token o day) ---
if not exist "%~dp0.reader-meta" mkdir "%~dp0.reader-meta"
if not exist "%~dp0.reader-meta\notify-config.json" (
  copy "%~dp0notify-config.example.json" "%~dp0.reader-meta\notify-config.json" >nul
  echo Da tao .reader-meta\notify-config.json tu mau. Kiem tra token neu can.
)

rem --- DON supervisor/reader CU truoc khi bat (tranh 2 supervisor -> 409, va
rem     tranh reader cu giu cong 8080 lam code moi khong hieu luc). Chi giet dung
rem     tien trinh chay supervisor.py / reader_server.py -> KHONG dung Tai truyen. ---
echo Dang don supervisor/reader cu dang chay (neu co)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'supervisor\.py|reader_server\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
taskkill /IM cloudflared.exe /F >nul 2>&1
del "%~dp0.reader-meta\supervisor.pid" >nul 2>&1
echo Da don xong. Chi con 1 supervisor sau khi bat.
echo.

rem --- dang ky chay khi DANG NHAP (song qua reboot). Phuong an A: dung python.exe
rem     (CO cua so log) de sau khi Windows tu dang nhap, supervisor tu len KEM cua so. ---
schtasks /create /tn "ToonyServer" /sc onlogon /rl LIMITED /f ^
  /tr "\"%PY%\" \"%~dp0supervisor.py\""
if errorlevel 1 (
  echo !!! Khong dang ky duoc Task Scheduler. Thu chay file nay bang quyen Admin.
) else (
  echo Da dang ky "ToonyServer" chay khi dang nhap Windows ^(co cua so log^).
)

echo.
echo Nhac: mo Telegram nhan /start cho bot de supervisor lay duoc chat_id.
echo Bat supervisor ngay bay gio (cua so rieng se hien log + link)...
start "ToonyServer" "%PY%" "%~dp0supervisor.py"

echo.
echo Xong.
echo  - Muon tu len sau reboot ma khong can go mat khau: chay server-AUTOLOGIN.bat 1 lan.
echo  - Doi tai khoan ma van giu server: *Switch user* (DUNG *Sign out*).
echo  - Chi de 1 supervisor: dung tay roi thi dung bam lai (2 cai -^> Telegram loi 409).
echo  - Muon tat het: chay server-TAT-tudong.bat
pause
