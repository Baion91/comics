@echo off
title Chia se link doc truyen (dong cua so nay = tat link)
echo ============================================================
echo  Dang tao link chia se tam thoi (trycloudflare.com)...
echo  Link se hien ben duoi sau vai giay - gui link do cho nguoi doc.
echo  LUU Y: dong cua so nay la link chet ngay lap tuc.
echo  (Nho bat server doc truyen truoc - shortcut "Web doc truyen")
echo ============================================================
"%~dp0.reader-meta\cloudflared.exe" tunnel --url http://localhost:8080
pause
