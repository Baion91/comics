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

rem --- phong ho-: kill cloudflared con sot ---
taskkill /IM cloudflared.exe /F >nul 2>&1

rem --- go dang ky Task Scheduler ---
schtasks /delete /tn "ToonyServer" /f >nul 2>&1
echo Da go dang ky "ToonyServer" (neu co).

echo.
echo Da tat het. Link chia se da chet.
pause
