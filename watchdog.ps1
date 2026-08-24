# watchdog.ps1 — HOI SINH supervisor.py neu no chet (Huong A).
#
# Chay boi Task Scheduler "ToonyWatchdog" moi 2 phut voi /it (trong PHIEN DANG NHAP)
# -> supervisor duoc bat trong SESSION TUONG TAC, nho vay cua so Chromium cua comix
#    (tick Cloudflare) van hien duoc tren desktop. Neu chay o Session 0 thi Chromium
#    vo hinh -> comix treo; vi the task PHAI /it, va script nay chi Start-Process (khong
#    tu doi session).
#
# Vi sao watchdog "do-roi-bat" thay vi "Restart on failure" cua Task Scheduler:
#   restart-on-failure chi kich khi tien trinh THOAT voi ma loi; con dong cua so / kill
#   co the KHONG tinh la 'failed'. Watchdog quet tien trinh nen bat duoc MOI kieu chet.
#
# Ton trong co PAUSE (.reader-meta\toony-paused.flag): server-TAT-tudong.bat dat co nay
# khi nguoi dung TAT chu dinh -> watchdog KHONG hoi sinh (de dong nghiep tat may de test).

param(
  [Parameter(Mandatory=$true)][string]$Pyw,   # duong dan tuyet doi toi pythonw.exe
  [Parameter(Mandatory=$true)][string]$Base   # thu muc goc project (chua supervisor.py)
)

$ErrorActionPreference = "SilentlyContinue"

$meta = Join-Path $Base ".reader-meta"
$flag = Join-Path $meta "toony-paused.flag"
if (Test-Path $flag) { exit 0 }   # da TAT chu dinh -> khong lam gi

# Supervisor dang chay chua? Quet theo CommandLine (KHONG tin pid file — pid cu de 'ma').
$alive = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
         Where-Object { $_.CommandLine -match 'supervisor\.py' }
if ($alive) { exit 0 }

# Chet -> bat lai (AN, pythonw khong co cua so). WorkingDirectory = Base cho chac cwd dung.
$script = Join-Path $Base "supervisor.py"
if (-not (Test-Path $script)) { exit 1 }
Start-Process -FilePath $Pyw -ArgumentList "`"$script`"" -WorkingDirectory $Base -WindowStyle Hidden

# Ghi 1 dong vao log RIENG cua watchdog (khong ghi chung supervisor-log.txt de tranh dung
# luc supervisor dang xoay file). Giup chan doan "da hoi sinh luc nao".
$logline = "[{0}] watchdog: supervisor KHONG chay -> da bat lai." -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
try { Add-Content -Path (Join-Path $meta "watchdog-log.txt") -Value $logline -Encoding UTF8 } catch {}
exit 0
