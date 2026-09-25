# watchdog.ps1 - HOI SINH supervisor.py neu no chet (Huong A).
#
# Chay boi Task Scheduler "ToonyWatchdog" moi 2 phut voi /it (trong PHIEN DANG NHAP)
# -> supervisor duoc bat trong SESSION TUONG TAC, nho vay cua so Chromium cua comix
#    (tick Cloudflare) van hien duoc tren desktop. Neu chay o Session 0 thi Chromium
#    vo hinh -> comix treo; vi the task PHAI /it, va script nay chi Start-Process (khong
#    tu doi session).
#
# Day la NOI DUY NHAT bat supervisor (tu 25/09/2026): server-BAT-tudong.bat khong tu
# 'start' nua ma 'schtasks /run' task nay; sau reboot + autologon, nhip 2 phut ke tiep
# cung chinh la no bat supervisor. Da BO task onlogon "ToonyServer" vi schtasks mac dinh
# "Stop the task if it runs longer than 72 hours" -> Task Scheduler GIET supervisor do task
# do bat sau dung 72h (su co 21->24/09). Supervisor bat qua Start-Process o day la tien
# trinh RIENG, song tiep khi task nay ket thuc (vai giay) -> khong dinh gioi han 72h.
#
# Vi sao watchdog "do-roi-bat" thay vi "Restart on failure" cua Task Scheduler:
#   restart-on-failure chi kich khi tien trinh THOAT voi ma loi; con dong cua so / kill
#   co the KHONG tinh la 'failed'. Watchdog quet tien trinh nen bat duoc MOI kieu chet.
#
# Ton trong co PAUSE (.reader-meta\toony-paused.flag): server-TAT-tudong.bat dat co nay
# khi nguoi dung TAT chu dinh -> watchdog KHONG hoi sinh (de dong nghiep tat may de test).
#
# Thu muc goc lay tu $PSScriptRoot (cho chua chinh file nay), KHONG nhan qua tham so nua:
# ban cu truyen -Base "%~dp0" -> %~dp0 co '\' cuoi -> Task Scheduler luu -Base "...\" ->
# PowerShell hieu \" la dau nhay THUONG -> $Base = '...comics-bundle"' -> Test-Path sai ->
# exit 1 CAM (khong log) -> chua tung hoi sinh duoc lan nao. -Base van nhan (bo qua) de
# task dang ky kieu cu khong vang loi "khong co tham so" trong luc chuyen doi.

param(
  [string]$Pyw = "",   # duong dan tuyet doi toi pythonw.exe (server-BAT resolve san)
  [string]$Base = ""   # LEGACY - bo qua, xem ghi chu tren
)

$ErrorActionPreference = "SilentlyContinue"

$root = $PSScriptRoot
$meta = Join-Path $root ".reader-meta"
$flag = Join-Path $meta "toony-paused.flag"
$wlog = Join-Path $meta "watchdog-log.txt"

# Log RIENG cua watchdog (khong ghi chung supervisor-log.txt de tranh dung luc supervisor
# dang xoay file). Ghi CA nhanh loi -> khong bao gio hong cam nua. Xoay khi > 1MB (giu .1)
# vi nhanh loi co the lap moi 2 phut.
function Write-WdLog([string]$msg) {
  try {
    if (-not (Test-Path $meta)) { New-Item -ItemType Directory -Force $meta | Out-Null }
    if ((Test-Path $wlog) -and ((Get-Item $wlog).Length -gt 1MB)) {
      Move-Item -Force $wlog "$wlog.1"
    }
    $line = "[{0}] watchdog: {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Add-Content -Path $wlog -Value $line -Encoding UTF8
  } catch {}
}

if (Test-Path $flag) { exit 0 }   # da TAT chu dinh -> khong lam gi (khong log, tranh spam)

# Supervisor dang chay chua? Quet theo CommandLine (KHONG tin pid file - pid cu de 'ma').
# Quet LOI thi KHONG bat bua: bat khi khong chac = co the thanh 2 supervisor (Telegram 409).
try {
  $alive = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction Stop |
           Where-Object { $_.CommandLine -match 'supervisor\.py' }
} catch {
  Write-WdLog ("LOI quet tien trinh (WMI/CIM): {0} -> bo qua luot nay." -f $_.Exception.Message)
  exit 2
}
if ($alive) { exit 0 }

$script = Join-Path $root "supervisor.py"
if (-not (Test-Path $script)) {
  Write-WdLog "LOI: khong thay $script -> khong bat duoc supervisor."
  exit 1
}

# pythonw: uu tien tham so; mat/sai (vd nang cap Python) thi thu .venv roi PATH.
if (-not ($Pyw -and (Test-Path $Pyw))) {
  $cands = @((Join-Path $root ".venv\Scripts\pythonw.exe"))
  $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($cmd) { $cands += $cmd.Source }
  $found = $cands | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
  if (-not $found) {
    Write-WdLog "LOI: khong tim thay pythonw.exe (tham so -Pyw '$Pyw' khong ton tai) -> chay lai server-BAT-tudong.bat."
    exit 1
  }
  Write-WdLog "canh bao: -Pyw '$Pyw' khong ton tai -> dung $found."
  $Pyw = $found
}

# Chet -> bat lai (AN, pythonw khong co cua so). WorkingDirectory = root cho chac cwd dung.
try {
  $p = Start-Process -FilePath $Pyw -ArgumentList "`"$script`"" -WorkingDirectory $root `
                     -WindowStyle Hidden -PassThru -ErrorAction Stop
  Write-WdLog ("supervisor KHONG chay -> da bat lai (PID {0})." -f $p.Id)
} catch {
  Write-WdLog ("LOI Start-Process {0}: {1}" -f $Pyw, $_.Exception.Message)
  exit 1
}
exit 0
