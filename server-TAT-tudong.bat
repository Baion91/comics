@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title TAT tu dong
cd /d "%~dp0"

echo ============================================================
echo  TAT CO CHE TU DONG
echo  - Dung supervisor (keo theo reader + cloudflared)
echo  - Go dang ky chay-khi-dang-nhap
echo ============================================================
echo.

rem --- DAT co PAUSE TRUOC khi giet: watchdog doc co nay se KHONG hoi sinh supervisor.
rem     Dat truoc de neu 1 luot watchdog dang xen vao thi cung thay co ma bo qua. ---
if not exist "%~dp0.reader-meta" mkdir "%~dp0.reader-meta"
type nul > "%~dp0.reader-meta\toony-paused.flag"
echo Da dat co PAUSE (watchdog se khong hoi sinh supervisor).
echo.

set "PIDFILE=%~dp0.reader-meta\supervisor.pid"
if exist "%PIDFILE%" (
  set /p SPID=<"%PIDFILE%"
  if not "!SPID!"=="" (
    taskkill /PID !SPID! /T /F >nul 2>&1
    echo Da dung supervisor (PID !SPID!) va cac tien trinh con.
  )
  del "%PIDFILE%" >nul 2>&1
) else (
  echo Khong thay supervisor.pid - supervisor co le khong chay.
)

rem --- phong ho-: giet supervisor + reader con sot theo CommandLine (phong khi pid file lac,
rem     hoac reader bi mo coi). Chi khop supervisor.py/reader_server.py -> KHONG dung Tai truyen. ---
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match 'supervisor\.py|reader_server\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

rem --- phong ho-: kill cloudflared con sot ---
taskkill /IM cloudflared.exe /F >nul 2>&1

rem --- go dang ky Task Scheduler (ca supervisor onlogon lan watchdog) ---
schtasks /delete /tn "ToonyWatchdog" /f >nul 2>&1
echo Da go dang ky "ToonyWatchdog" (neu co).
schtasks /delete /tn "ToonyServer" /f >nul 2>&1
echo Da go dang ky "ToonyServer" (neu co).

echo.
echo Da tat het. Link chia se da chet.
pause
