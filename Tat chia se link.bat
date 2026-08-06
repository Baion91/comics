@echo off
title Tat link chia se
taskkill /IM cloudflared.exe /F >nul 2>&1
if %errorlevel%==0 (
  echo Da tat het duong ham chia se. Moi link deu chet ngay lap tuc.
) else (
  echo Khong co duong ham nao dang chay - ban dang an toan.
)
pause
