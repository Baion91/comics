@echo off
chcp 65001 >nul
title BAT tu dong (chi chay tren SERVER)
cd /d "%~dp0"

echo ============================================================
echo  BAT CO CHE TU DONG (chay tren MAY SERVER, KHONG chay tren may dev)
echo  - Dang ky chay lai khi dang nhap Windows (song qua reboot)
echo  - Bat supervisor NGAY: giu reader + cloudflared, gui link Telegram
echo ============================================================
echo.

rem --- chon Python: uu tien venv neu co ---
set "PY=python"
set "PYW=pythonw"
if exist "%~dp0.venv\Scripts\python.exe"  set "PY=%~dp0.venv\Scripts\python.exe"
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PYW=%~dp0.venv\Scripts\pythonw.exe"
rem --- Task onlogon KHONG co PATH cua user -> ten tran 'pythonw' se loi 0x80070002
rem     (file not found). Doi PYW sang DUONG DAN TUYET DOI de task chay duoc khi dang nhap. ---
if /i "%PYW%"=="pythonw" for /f "delims=" %%i in ('where pythonw 2^>nul') do set "PYW=%%i"
if /i "%PYW%"=="pythonw" for /f "delims=" %%i in ('where python 2^>nul') do set "PYW=%%~dpipythonw.exe"

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

rem --- dang ky chay khi dang nhap (song qua reboot); pythonw = khong cua so ---
schtasks /create /tn "ToonyServer" /sc onlogon /rl LIMITED /f ^
  /tr "\"%PYW%\" \"%~dp0supervisor.py\""
if errorlevel 1 (
  echo !!! Khong dang ky duoc Task Scheduler. Thu chay file nay bang quyen Admin.
) else (
  echo Da dang ky "ToonyServer" chay khi dang nhap Windows.
)

echo.
echo Nhac: mo Telegram nhan /start cho bot de supervisor lay duoc chat_id.
echo Bat supervisor ngay bay gio (cua so rieng se hien log + link)...
start "ToonyServer" "%PY%" "%~dp0supervisor.py"

echo.
echo Xong. Muon tat het: chay server-TAT-tudong.bat
pause
