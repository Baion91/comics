@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title Bat tu dang nhap Windows (Phuong an A - chi tren SERVER)
cd /d "%~dp0"

echo ============================================================
echo  PHUONG AN A: BAT WINDOWS TU DANG NHAP (autologon)
echo  Muc dich: sau khi reboot, Windows TU dang nhap tai khoan nay
echo            -^> task "ToonyServer" tu chay -^> server tu len,
echo            KHONG can ai go mat khau.
echo  Cong cu: Sysinternals Autologon (ma hoa mat khau vao LSA
echo           secret, KHONG luu plaintext nhu netplwiz/registry tay).
echo ============================================================
echo.
echo  LUU Y QUAN TRONG:
echo   - Chay file nay bang quyen ADMINISTRATOR.
echo   - Autologon hien 1 cua so: dien Username + Domain (ten may,
echo     hoac dau "." cho tai khoan noi bo) + Password cua CHINH tai
echo     khoan nay, roi bam ENABLE.
echo   - Toi KHONG dien mat khau ho - ban tu go trong cua so do.
echo   - Sau reboot desktop se TU MO KHOA (danh doi cua phuong an A:
echo     ai cham duoc console/RDP la thay desktop da dang nhap san).
echo   - Doi/dung tai khoan khac ma VAN giu server song: bam Start -^>
echo     avatar -^> *Switch user*. DUNG *Sign out* (sign out ket thuc
echo     phien Administrator -^> giet luon supervisor).
echo   - Tat autologon sau nay: mo lai Autologon roi bam *Disable*.
echo.

set "DEST=%~dp0.reader-meta\Autologon64.exe"
set "URL=https://live.sysinternals.com/Autologon64.exe"
rem  Du phong (ban zip): https://download.sysinternals.com/files/Autologon.zip

if not exist "%~dp0.reader-meta" mkdir "%~dp0.reader-meta"

if exist "%DEST%" goto :launch

echo Dang tai Autologon tu Sysinternals (nguon Microsoft chinh thuc)...
rem --- Uu tien PowerShell + ep TLS 1.2 (server Windows cu mac dinh TLS 1.0 -> tai hut).
rem     curl co the KHONG co tren Windows Server cu -> dung lam du phong. ---
powershell -NoProfile -Command "try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;Invoke-WebRequest -UseBasicParsing -Uri '%URL%' -OutFile '%DEST%'}catch{exit 1}"
if not exist "%DEST%" (
  echo.
  echo !!! PowerShell that bai. Thu bang curl (neu co)...
  curl -L -o "%DEST%" "%URL%" 2>nul
)
if not exist "%DEST%" (
  echo.
  echo !!! Khong tai duoc Autologon. Tai tay tai dia chi:
  echo     %URL%
  echo   roi luu thanh Autologon64.exe vao thu muc .reader-meta\ va chay lai file nay.
  echo   (Hoac tai ban .../Autologon.zip roi giai nen lay Autologon64.exe.)
  echo.
  pause
  exit /b 1
)

:launch
echo.
echo Mo Autologon... (lan dau se hien EULA - bam Agree)
echo Dien Password cua tai khoan nay roi bam ENABLE.
start "" "%DEST%"

echo.
echo ------------------------------------------------------------
echo  SAU KHI BAM ENABLE XONG, kiem theo thu tu:
echo   1) Da chay server-BAT-tudong.bat MOT lan (de co task "ToonyServer").
echo      Kiem: schtasks /query /tn "ToonyServer" /v /fo LIST  (State=Ready)
echo   2) Reboot thu -^> KHONG dung gi -^> cho ~1-2 phut.
echo   3) Windows tu dang nhap -^> hien cua so log "ToonyServer" +
echo      Telegram nhan link moi + heartbeat xanh + /trangthai tra loi.
echo ------------------------------------------------------------
echo.
pause
