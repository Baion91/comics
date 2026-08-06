@echo off
chcp 65001 >nul
title Tao ban sach de mang sang server
cd /d "%~dp0"

set "DEST=..\comics-bundle"

echo ============================================================
echo  TAO BAN SACH (chi CODE + cloudflared.exe, BO du lieu truyen)
echo  Nguon : %~dp0
echo  Dich  : %DEST%   (canh thu muc du an)
echo  Loai  : downloads, __pycache__, .git, .venv, cloudflared.exe, file du lieu
echo  Giu   : *.py, *.bat, README, .claude, icon, config mau
echo  (cloudflared.exe KHONG dong goi - Drive bao malware nham. Tren server
echo   chay get-cloudflared.bat de tai tu Cloudflare chinh thuc.)
echo ============================================================
echo.
pause

robocopy "." "%DEST%" /E ^
  /XD downloads __pycache__ .git .venv "%DEST%" ^
  /XF cloudflared.exe user-data.json users.json series-meta.json spreads.json ^
      image-issues.json download-log.txt check-report.html notify-config.json ^
      current-link.txt supervisor-log.txt supervisor.pid download-queue.txt "*.tmp"

echo.
if %ERRORLEVEL% GEQ 8 (
  echo !!! robocopy bao loi (ma %ERRORLEVEL%^). Kiem tra lai duong dan.
) else (
  echo Xong. Ban sach o: %DEST%
  echo   -^> Nen (zip^) thu muc do lai roi mang sang server (khong con .exe nen
  echo      Drive/khac se khong bao malware nua^).
  echo   -^> Tren server: giai nen, chay get-cloudflared.bat (tai cloudflared),
  echo      cai thu vien, dien token vao notify-config, roi server-BAT-tudong.bat.
)
echo.
pause
