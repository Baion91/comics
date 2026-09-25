@echo off
chcp 65001 >nul
title BAT tu dong (chi chay tren SERVER)
cd /d "%~dp0"

echo ============================================================
echo  BAT CO CHE TU DONG (chay tren MAY SERVER, KHONG chay tren may dev)
echo  - Dang ky WATCHDOG (moi 2 phut): bat + hoi sinh supervisor, ke ca sau reboot
echo  - Bat supervisor NGAY: giu reader + cloudflared, gui link Telegram
echo  Phuong an A: muon server tu len sau reboot ma KHONG can go mat
echo  khau -^> chay them server-AUTOLOGIN.bat MOT lan de bat tu dang nhap.
echo ============================================================
echo.

rem --- chon Python: uu tien venv neu co ---
set "PYW=pythonw"
if exist "%~dp0.venv\Scripts\pythonw.exe" set "PYW=%~dp0.venv\Scripts\pythonw.exe"
rem --- Task Scheduler KHONG co PATH cua user -> ten tran 'python'/'pythonw' se loi
rem     0x80070002 (file not found). Doi sang DUONG DAN TUYET DOI de task chay duoc. ---
if /i "%PYW%"=="pythonw" for /f "delims=" %%i in ('where pythonw 2^>nul') do set "PYW=%%i"
if /i "%PYW%"=="pythonw" for /f "delims=" %%i in ('where python 2^>nul') do set "PYW=%%~dpipythonw.exe"

rem --- tao notify-config.json tu mau neu chua co (dien token o day) ---
if not exist "%~dp0.reader-meta" mkdir "%~dp0.reader-meta"
if not exist "%~dp0.reader-meta\notify-config.json" (
  copy "%~dp0notify-config.example.json" "%~dp0.reader-meta\notify-config.json" >nul
  echo Da tao .reader-meta\notify-config.json tu mau. Kiem tra token neu can.
)

rem --- DAT co PAUSE TAM trong luc don + dang ky: nhip watchdog (task cu lan moi) roi dung
rem     khe nay se thay co ma bo qua -> KHONG bat chen 1 supervisor giua chung (tranh 2 ban
rem     -> Telegram 409 + 2 link). Cuoi file moi xoa co roi goi watchdog chay NGAY. ---
type nul > "%~dp0.reader-meta\toony-paused.flag"

rem --- DON supervisor/reader CU truoc khi bat (tranh 2 supervisor -> 409, va
rem     tranh reader cu giu cong lam code moi khong hieu luc). Chi giet dung
rem     tien trinh chay supervisor.py / reader_server.py -> KHONG dung Tai truyen. ---
echo Dang don supervisor/reader cu dang chay (neu co)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'supervisor\.py|reader_server\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
taskkill /IM cloudflared.exe /F >nul 2>&1
del "%~dp0.reader-meta\supervisor.pid" >nul 2>&1
echo Da don xong.
echo.

rem --- GO task onlogon "ToonyServer" (doi cu). schtasks /create mac dinh "Stop the task if it
rem     runs longer than 72 hours" -> supervisor do task nay bat bi Task Scheduler GIET sau dung
rem     72h (su co 21-^>24/09/2026: Windows Update reboot -^> 72h sau bot cam). Khong can no nua:
rem     sau reboot + autologon, nhip 2 phut ke tiep cua WATCHDOG se bat supervisor. ---
schtasks /delete /tn "ToonyServer" /f >nul 2>&1
echo Da go task cu "ToonyServer" (neu co) - watchdog se lo ca viec bat sau reboot.

rem --- WATCHDOG: moi 2 phut kiem supervisor con song khong; chet -> bat lai. /it = chay
rem     trong PHIEN DANG NHAP -> supervisor + Chromium comix o session tuong tac (tick duoc).
rem     Ton trong co .reader-meta\toony-paused.flag (co co -> khong hoi sinh).
rem     KHONG truyen thu muc goc: watchdog.ps1 tu lay $PSScriptRoot. (Ban cu truyen
rem     -Base "%~dp0" -> '\' cuoi nuot dau nhay -> watchdog exit 1 cam, chua tung hoi sinh.) ---
set "WD_OK=0"
schtasks /create /tn "ToonyWatchdog" /sc MINUTE /mo 2 /it /rl LIMITED /f ^
  /tr "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0watchdog.ps1\" -Pyw \"%PYW%\""
if errorlevel 1 (
  echo !!! Khong dang ky duoc Task "ToonyWatchdog" - se bat supervisor truc tiep, KHONG co hoi sinh.
) else (
  set "WD_OK=1"
  echo Da dang ky "ToonyWatchdog" ^(bat + hoi sinh supervisor moi 2 phut neu chet^).
)

rem --- xoa co PAUSE -> cho phep watchdog bat/hoi sinh ---
del "%~dp0.reader-meta\toony-paused.flag" >nul 2>&1

echo.
echo Nhac: mo Telegram nhan /start cho bot de supervisor lay duoc chat_id.
rem --- Bat supervisor NGAY qua CHINH watchdog (schtasks /run) -> watchdog la NOI DUY NHAT bat
rem     supervisor, khong con 2 duong (start + watchdog) chen nhau thanh 2 ban. Dang ky that
rem     bai (hoac /run loi) thi moi 'start' truc tiep.
rem     (Khong dung goto/label: file .bat xuong dong LF co the lam cmd tim nham label.) ---
set "STARTED=0"
if "%WD_OK%"=="1" (
  echo Bat supervisor ngay bay gio qua watchdog - chay AN, log .reader-meta\supervisor-log.txt
  schtasks /run /tn "ToonyWatchdog" >nul 2>&1
  if not errorlevel 1 set "STARTED=1"
)
if "%STARTED%"=="0" (
  echo Bat supervisor truc tiep - chay AN, log .reader-meta\supervisor-log.txt
  start "" "%PYW%" "%~dp0supervisor.py"
)

rem --- Kiem that: cho vai giay roi xem da co DUNG 1 supervisor chua ---
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep 6; $n = @(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'supervisor\.py' }).Count; if ($n -eq 1) { 'OK: dang co 1 supervisor chay.' } elseif ($n -eq 0) { '!!! CHUA thay supervisor - watchdog se bat trong <=2 phut; qua 2 phut van khong co thi xem .reader-meta\watchdog-log.txt' } else { \"!!! Dang co $n supervisor - chay lai file nay de don.\" }"

echo.
echo Xong.
echo  - Supervisor chay AN + WATCHDOG hoi sinh moi 2 phut neu no chet (ke ca sau reboot).
echo    -^> KHONG con cua so de dong; MUON TAT phai chay server-TAT-tudong.bat.
echo    (Dong cua so / kill se bi watchdog bat lai trong ~2 phut.)
echo  - Muon tu len sau reboot ma khong can go mat khau: chay server-AUTOLOGIN.bat 1 lan.
echo  - Doi tai khoan ma van giu server: *Switch user* (DUNG *Sign out*).
echo  - Xem tinh trang: Telegram /trangthai, hoac mo .reader-meta\supervisor-log.txt
echo    va .reader-meta\watchdog-log.txt (moi lan watchdog bat/loi deu ghi 1 dong).
pause
