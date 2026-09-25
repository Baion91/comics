# watchdog.pyw — HỒI SINH supervisor.py nếu nó chết (Hướng A).
#
# Chạy bởi Task Scheduler "ToonyWatchdog" mỗi 2 phút với /it (trong PHIÊN ĐĂNG NHẬP)
# -> supervisor được bật trong SESSION TƯƠNG TÁC, nhờ vậy cửa sổ Chromium của comix
#    (tick Cloudflare) vẫn hiện được trên desktop. Chạy ở Session 0 thì Chromium vô hình
#    -> comix treo; vì thế task PHẢI /it.
#
# Vì sao .pyw chạy bằng pythonw.exe (thay watchdog.ps1 từ 25/09/2026): task /it chạy
# powershell.exe thì MỖI 2 PHÚT bật 1 cửa sổ console xanh/tím rồi tắt (cướp focus của người
# đang dùng máy server, cắt ngang lúc tick Cloudflare). pythonw là GUI-subsystem -> KHÔNG có
# console nào; powershell con gọi với CREATE_NO_WINDOW -> cũng không cửa sổ.
#
# Đây là NƠI DUY NHẤT bật supervisor (từ 25/09/2026): server-BAT-tudong.bat 'schtasks /run'
# task này thay vì tự 'start'; sau reboot + autologon, nhịp 2 phút kế tiếp bật supervisor.
# Đã BỎ task onlogon "ToonyServer" vì schtasks mặc định "Stop the task if it runs longer than
# 72 hours" -> Task Scheduler GIẾT tiến trình task bật trực tiếp sau 72h (sự cố 21->24/09).
# Supervisor bật ở đây là tiến trình TÁCH RIÊNG, sống tiếp khi task (vài giây) kết thúc.
#
# Vì sao "dò-rồi-bật" thay vì "Restart on failure" của Task Scheduler: restart-on-failure
# chỉ kích khi tiến trình THOÁT với mã lỗi; đóng cửa sổ / kill có thể KHÔNG tính là 'failed'.
#
# Tôn trọng cờ PAUSE (.reader-meta\toony-paused.flag): server-TAT-tudong.bat đặt cờ khi TẮT
# chủ đích -> watchdog KHÔNG hồi sinh (để đồng nghiệp tắt máy test).
#
# Thư mục gốc lấy từ vị trí CHÍNH file này -> không nhận đường dẫn qua tham số (bản .ps1 cũ
# nhận -Base "%~dp0", '\' cuối nuốt dấu nháy -> exit 1 câm, chưa từng hồi sinh được lần nào).
# stdlib-only; KHÔNG print (pythonw không có stdout) — mọi thứ ghi watchdog-log.txt.

import os
import subprocess
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
META = os.path.join(ROOT, ".reader-meta")
FLAG = os.path.join(META, "toony-paused.flag")
WLOG = os.path.join(META, "watchdog-log.txt")
SCRIPT = os.path.join(ROOT, "supervisor.py")
WLOG_MAX = 1_000_000   # xoay log khi > ~1MB (giữ .1) — nhánh lỗi có thể lặp mỗi 2 phút

NO_WINDOW = 0x08000000             # CREATE_NO_WINDOW: powershell con không bật console
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000

# Đếm python/pythonw có 'supervisor.py' trong CommandLine (KHÔNG tin pid file — pid cũ dễ 'ma').
# -ErrorAction Stop: WMI/CIM hỏng -> mã thoát ≠ 0 -> watchdog KHÔNG bật bừa.
PS_COUNT = (
    "$ErrorActionPreference='Stop'; "
    "@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | "
    "Where-Object { $_.CommandLine -match 'supervisor\\.py' }).Count"
)


def log(msg):
    try:
        os.makedirs(META, exist_ok=True)
        try:
            if os.path.getsize(WLOG) > WLOG_MAX:
                os.replace(WLOG, WLOG + ".1")
        except OSError:
            pass
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(WLOG, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] watchdog: {msg}\n")
    except OSError:
        pass


def supervisor_count():
    """Số supervisor đang chạy; raise nếu KHÔNG chắc (quét lỗi) -> người gọi bỏ lượt."""
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", PS_COUNT],
        creationflags=NO_WINDOW, timeout=90, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out.isdigit():
        raise RuntimeError(f"rc={r.returncode} out={out[:80]!r} err={(r.stderr or '').strip()[:200]!r}")
    return int(out)


def pythonw_exe():
    """pythonw.exe để chạy supervisor ẨN: chính trình đang chạy watchdog (task truyền đường
    dẫn tuyệt đối); lỡ chạy tay bằng python.exe thì đổi sang pythonw.exe cùng thư mục."""
    exe = sys.executable
    if os.path.basename(exe).lower() == "python.exe":
        cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(cand):
            exe = cand
    return exe


def start_supervisor():
    """Bật supervisor thành tiến trình TÁCH RIÊNG (không console, nhóm tiến trình riêng). Thử
    thoát khỏi job của Task Scheduler (nếu job cho phép) để chắc chắn không bị giết theo task;
    job cấm breakaway -> CreateProcess lỗi -> bật lại không cờ đó (test dev: vẫn sống tiếp)."""
    base = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True)
    cmd = [pythonw_exe(), SCRIPT]
    try:
        return subprocess.Popen(cmd, creationflags=base | CREATE_BREAKAWAY_FROM_JOB, **kw)
    except OSError:
        return subprocess.Popen(cmd, creationflags=base, **kw)


def main():
    if os.path.exists(FLAG):
        return 0                  # đã TẮT chủ đích -> không làm gì (không log, tránh spam)
    try:
        n = supervisor_count()
    except Exception as e:
        log(f"LỖI quét tiến trình ({e}) -> bỏ qua lượt này, KHÔNG bật (tránh 2 supervisor).")
        return 2
    if n > 0:
        return 0
    if not os.path.exists(SCRIPT):
        log(f"LỖI: không thấy {SCRIPT} -> không bật được supervisor.")
        return 1
    try:
        p = start_supervisor()
    except Exception as e:
        log(f"LỖI bật supervisor bằng {pythonw_exe()}: {e}")
        return 1
    log(f"supervisor KHÔNG chạy -> đã bật lại (PID {p.pid}).")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:        # lưới chót: không bao giờ hỏng câm
        log(f"LỖI không lường: {e!r}")
        code = 1
    sys.exit(code)
