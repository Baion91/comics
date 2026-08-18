#!/usr/bin/env python3
"""Giám sát cho SERVER đọc truyện (chạy trên máy server, KHÔNG chạy trên máy dev).

Nhiệm vụ:
  1. Giữ reader_server.py sống (chết -> tự bật lại).
  2. Giữ cloudflared quick-tunnel sống, BẮT link https://....trycloudflare.com.
  3. Health-check định kỳ: tunnel rớt (dù tiến trình còn) -> kill + bật lại.
  4. Có link MỚI -> gửi Telegram cho bạn (tự đọc getUpdates lấy chat_id lần đầu).
  5. Ghi link hiện tại ra .reader-meta/current-link.txt + log ra supervisor-log.txt.

CHỈ dùng thư viện chuẩn (urllib) — không cần requests/Pillow. Bật/tắt qua 2 file
server-BAT-tudong.bat / server-TAT-tudong.bat (đăng ký Task Scheduler "At startup").

Cấu hình: .reader-meta/notify-config.json
  {"bot_token":"123:ABC","chat_id":"", "reader_port":8080}
chat_id để trống -> supervisor tự điền khi bạn nhắn /start cho bot.
"""

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
META_DIR = os.path.join(BASE_DIR, ".reader-meta")
CONFIG_FILE = os.path.join(META_DIR, "notify-config.json")
LINK_FILE = os.path.join(META_DIR, "current-link.txt")
LOG_FILE = os.path.join(META_DIR, "supervisor-log.txt")
PID_FILE = os.path.join(META_DIR, "supervisor.pid")
CLOUDFLARED = os.path.join(META_DIR, "cloudflared.exe")
# Hàng đợi tải BỀN HOÁ ra đĩa (sống qua restart supervisor). Gitignore .reader-meta/*
# nên git reset --hard của cap-nhat.bat KHÔNG đụng file này. Tên khác download-queue.txt
# (file của tool tải-tay Tai hang loat.bat) để khỏi lẫn.
QUEUE_FILE = os.path.join(META_DIR, "bot-download-queue.json")
DL_LOG_FILE = os.path.join(META_DIR, "tai-run.log")   # output downloader (tail xem tiến độ)
DL_LOG_MAX = 2_000_000    # cắt log khi vượt ~2MB
# Watchlist auto-check chương mới. watchlist.json = 1 NƠI quản lý danh sách truyện tự
# check (gitignore .reader-meta/* nên sống qua git reset của cap-nhat.bat). check_updates.py
# chạy dạng SUBPROCESS (cô lập requests/providers khỏi supervisor stdlib) và ghi kết quả
# ra CHECK_RESULT_FILE để supervisor đọc lại (KHÔNG parse stdout — _request có thể in 429/503).
WATCHLIST_FILE = os.path.join(META_DIR, "watchlist.json")
CHECK_SCRIPT = os.path.join(BASE_DIR, "check_updates.py")
CHECK_RESULT_FILE = os.path.join(META_DIR, "watch-check-result.json")
CHECK_TIMEOUT = 1500      # giây tối đa cho 1 lần quét cả watchlist

# Bắt link tunnel: subdomain NGẪU NHIÊN .trycloudflare.com. Nhóm 1 = subdomain để LOẠI
# 'api' — 'api.trycloudflare.com' là host cloudflared in trong DÒNG LỖI (không phải link);
# regex cũ bắt nhầm nó -> báo link rác. Đêm 11/08 spam ~2900 "LINK MỚI: api.trycloudflare.com".
TUNNEL_RE = re.compile(r"https://([a-z0-9][a-z0-9-]*)\.trycloudflare\.com")
# Backoff khi cloudflared bật lên rồi CHẾT NGAY (không lập nổi tunnel — thường do mất mạng/DNS):
# thay vì quay vòng 3s/lần (2900 lần/đêm), giãn dần 3→6→12…→trần 5' tới khi mạng về.
TUNNEL_BACKOFF_MIN = 3     # giây, lần đầu
TUNNEL_BACKOFF_MAX = 300   # trần 5 phút
TUNNEL_HEALTHY_SECS = 60   # tunnel chạy được ngần này coi như ổn -> reset backoff
NET_RECHECK = 20           # giây giữa 2 lần dò mạng khi đang chờ mạng về
NET_HOSTS = ["api.telegram.org", "one.one.one.one"]  # tên để thử PHÂN GIẢI (bắt lỗi DNS)
NET_IP = ("1.1.1.1", 443)  # IP THUẦN (không cần DNS) -> phân biệt 'DNS hỏng' vs 'mất mạng hẳn'
DL_NET_RETRY_MAX = 4       # mạng đã OK mà job vẫn fail kiểu-mạng quá số này -> coi là lỗi nội dung
# Dấu hiệu lỗi MẠNG trong log downloader -> GIỮ job lại thử lại (khác lỗi nội dung -> xoá).
NET_ERR_MARKERS = ("getaddrinfo", "nameresolution", "failed to resolve", "max retries",
                   "mạng chập chờn", "connection aborted", "connectionreset",
                   "connection reset", "timed out", "temporarily unavailable")
# Stall-watchdog (lưới bao chót): job đang chạy mà LOG ĐỨNG IM (không thêm byte) quá
# DL_STALL_LIMIT giây = nghi treo câm (vd Chromium comix wedge lọt qua watchdog nội bộ) ->
# kill tiến trình + Chromium comix rồi giữ job thử lại. Phát hiện bằng os.path.getsize (1
# lệnh stat, O(1) — KHÔNG đọc nội dung nên không phụ thuộc log to/nhỏ). Vòng poll CHỈ chạy
# khi ĐANG có 1 job (thay proc.wait); lúc rảnh worker ngủ trên condition, không poll gì.
# Ngưỡng phải > cữ backoff 429 tệ nhất của comics_core (một lần sleep tới 900s) + biên, để
# KHÔNG giết nhầm job đang nghỉ-lịch-sự hợp lệ. Đọc đè được từ notify-config.json.
DL_STALL_LIMIT = 1200      # giây log đứng im -> coi là treo (đè bằng cfg "dl_stall_limit")
DL_STALL_POLL = 30         # giây giữa 2 lần kiểm size log
DL_STALL_BACKOFF = 120     # giây nghỉ trước khi thử lại job vừa bị kill vì treo
DL_STALL_RETRY_MAX = 1     # số lần GIỮ+thử lại 1 job treo; quá -> bỏ (daily tự enqueue lại)
HEARTBEAT_EVERY = 300      # giây giữa 2 nhịp heartbeat (5') ping RA dịch vụ giám sát ngoài
HEARTBEAT_TIMEOUT = 10     # giây chờ mỗi cú ping
# Chờ READER NỘI BỘ (127.0.0.1) sẵn sàng trước khi báo link (để user mở link không dính 502).
# KHÔNG kiểm URL công khai nữa: mạng server không "hairpin" được về chính tunnel của nó (sai ~2/3)
# → trước đây làm health_loop giết nhầm tunnel đang sống + báo link 'chưa xác minh'. Localhost thì
# luôn tin cậy được (không qua Cloudflare/hairpin).
READER_WAIT = 60           # giây: chờ reader nội bộ tối đa ngần này rồi vẫn báo
READER_RETRY = 3           # giây giữa 2 lần thử reader nội bộ
NO_WINDOW = 0x08000000 if os.name == "nt" else 0   # đừng bật cửa sổ console con

# In được tiếng Việt trên console Windows (cp1252)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass


def log(msg):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(META_DIR, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    cfg.setdefault("bot_token", "")
    cfg.setdefault("reader_port", 8080)
    cfg.setdefault("heartbeat_url", "")   # URL ping healthchecks.io (trống = tắt heartbeat)
    cfg.setdefault("check_hour", 3)       # giờ (0-23) chạy auto-check chương mới hằng ngày
    cfg.setdefault("check_min", 0)        # phút (0-59)
    cfg.setdefault("dl_stall_limit", DL_STALL_LIMIT)  # giây log tải đứng im -> coi là treo
    # chat_ids: DANH SÁCH người nhận (cả 2 anh em). Tự gom khi ai nhắn bot.
    ids = cfg.get("chat_ids")
    if not isinstance(ids, list):
        ids = []
    # tương thích ngược: config cũ có "chat_id" (một) -> gộp vào danh sách
    old = cfg.get("chat_id")
    if old and str(old) not in [str(x) for x in ids]:
        ids.append(str(old))
    cfg["chat_ids"] = [str(x) for x in ids]
    return cfg


def save_config(cfg):
    try:
        os.makedirs(META_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CONFIG_FILE)
    except OSError as e:
        log(f"! Không ghi được config: {e}")


# --- Telegram (urllib, không cần requests) ---------------------------------

def tg_api(token, method, params, timeout=20):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"! Lỗi gọi Telegram {method}: {e}")
        return None


def add_chat(cfg, chat_id):
    """Thêm chat_id vào danh sách nhận nếu chưa có; lưu config. Trả True nếu mới."""
    cid = str(chat_id)
    ids = cfg.setdefault("chat_ids", [])
    if cid not in ids:
        ids.append(cid)
        save_config(cfg)
        log(f"Thêm người nhận Telegram: {cid} (tổng {len(ids)})")
        return True
    return False


def notify_all(cfg, text):
    """Gửi 1 tin tới TẤT CẢ chat_id đã đăng ký (cả 2 anh em)."""
    token = cfg.get("bot_token")
    if not token:
        log("! Chưa có bot_token — bỏ qua gửi Telegram.")
        return
    ids = cfg.get("chat_ids") or []
    if not ids:
        log("! Chưa ai nhắn bot (chat_ids rỗng) — nhắn /start cho bot rồi sẽ tự nhận.")
        return
    for cid in ids:
        tg_api(token, "sendMessage", {"chat_id": cid, "text": text,
                                      "disable_web_page_preview": "true"})


HELP_TEXT = (
    "📖 Toony bot — các lệnh:\n"
    "/link — link đọc hiện tại\n"
    "/whoami — xem chat_id của bạn\n"
    "/help — danh sách lệnh\n\n"
    "Admin:\n"
    "/tai <link> [chương] — tải truyện; thêm dải chương để chỉ tải phần đó\n"
    "     vd: /tai <link> 1-20  hoặc  /tai <link> 5,7,20-25  (bỏ trống = cả truyện)\n"
    "/trangthai — xem truyện đang tải + hàng chờ\n"
    "/stop — dừng truyện đang tải + xoá hàng chờ (của bạn)\n"
    "/killnow — chỉ dừng truyện đang tải (của bạn)\n"
    "/clearq — chỉ xoá hàng chờ (của bạn)\n"
    "/stopall — dừng tất cả + xoá sạch hàng chờ (mọi người)\n"
    "/update — cập nhật code + restart reader\n\n"
    "Tự động check chương mới:\n"
    "/watchlist — xem danh sách truyện được auto-check\n"
    "/watch <link> — thêm truyện vào danh sách\n"
    "/unwatch <số|link> — bỏ truyện khỏi danh sách\n"
    "/checknow [link] — kiểm tra chương mới NGAY (tất cả, hoặc 1 truyện)\n"
    "/adminlist — xem chat đã đăng ký / admin\n"
    "/adminclaim — nhận quyền admin (khi chưa có ai)\n"
    "/adminadd <id> — thêm admin\n"
    "/adminremove <id> — bỏ admin"
)


# --- Dò mạng: phân biệt 'mạng OK' / 'DNS hỏng' / 'mất mạng hẳn' -------------
# Đêm 11/08 thủ phạm là DNS (getaddrinfo failed) chứ máy vẫn sống. Gate này để các
# vòng (tunnel/tải/health) BIẾT KHI NÀO nên nằm im chờ thay vì quay cuồng vô ích.

def _net_status():
    """'ok' = phân giải được tên miền; 'dns' = với tới IP thuần nhưng KHÔNG phân giải
    được tên (DNS hỏng); 'down' = không với tới cả IP (mất mạng hẳn)."""
    ip_ok = False
    try:
        with socket.create_connection(NET_IP, timeout=4):
            ip_ok = True
    except OSError:
        ip_ok = False
    for host in NET_HOSTS:
        try:
            socket.getaddrinfo(host, 443)   # phép thử DNS THẬT (đúng khâu đêm 11/08 gục)
            return "ok"
        except OSError:
            continue
    return "dns" if ip_ok else "down"


# --- Reader + cloudflared ---------------------------------------------------

class Supervisor:
    def __init__(self):
        self.cfg = load_config()
        self.stop = threading.Event()
        self.reader = None
        self.tunnel = None
        self.link = None            # link ứng viên mới nhất (kể cả chưa xác minh) — cho /link
        self._notified_link = None  # link ĐÃ báo Telegram gần nhất — chỉ báo khi link ĐỔI
        self.lock = threading.Lock()
        # Hàng đợi tải = DANH SÁCH bền hoá (không dùng queue.Queue để lưu ra đĩa được).
        # _jobs: [{"url","cid","state":pending|running,"resumed":bool}]. Condition vừa
        # làm khoá vừa đánh thức worker khi có job mới.
        self._dlq_lock = threading.Condition()
        self._jobs = []
        self._dl_proc = None        # tiến trình comic_downloader đang chạy (để kill)
        self._dl_cur = None         # job dict đang tải — để biết 'của ai'
        self._dl_cancelled = False  # cờ: lần kill này là do người dùng huỷ (không phải lỗi)
        self._dl_logpos = 0         # offset đầu log của job đang chạy — /trangthai đọc tiến độ
        self._wl_lock = threading.Lock()   # bảo vệ ghi watchlist.json (supervisor = writer duy nhất)
        self._checking = False             # đang chạy 1 lần auto-check -> chặn chạy chồng

    def reader_url(self):
        return f"http://127.0.0.1:{self.cfg.get('reader_port', 8080)}"

    # reader_server.py: chết thì bật lại
    def run_reader(self):
        while not self.stop.is_set():
            log("Bật reader_server.py ...")
            try:
                self.reader = subprocess.Popen(
                    [sys.executable, os.path.join(BASE_DIR, "reader_server.py"),
                     "--port", str(self.cfg.get("reader_port", 8080))],
                    cwd=BASE_DIR, creationflags=NO_WINDOW,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                log(f"! Không bật được reader: {e}")
                self.stop.wait(5); continue
            self.reader.wait()
            if self.stop.is_set():
                return
            log("! reader thoát — bật lại sau 3s.")
            self.stop.wait(3)

    # cloudflared: chạy, bắt link trên output; thoát thì vòng lặp bật lại (link mới)
    def run_tunnel(self):
        if not os.path.exists(CLOUDFLARED):
            log(f"! Không thấy {CLOUDFLARED} — không tạo được link chia sẻ.")
            return
        backoff = TUNNEL_BACKOFF_MIN
        while not self.stop.is_set():
            # GATE MẠNG: mất mạng/DNS thì cloudflared bật lên cũng chết ngay -> chờ mạng về,
            # KHÔNG bật để khỏi quay vòng tạo link rác (đêm 11/08: 2900 lần bật vô ích).
            st = _net_status()
            if st != "ok":
                log(f"! Mạng chưa sẵn sàng ({st}) — hoãn bật cloudflared, dò lại sau {NET_RECHECK}s.")
                if self.stop.wait(NET_RECHECK):
                    return
                continue
            log("Bật cloudflared quick-tunnel ...")
            started = time.monotonic()
            try:
                self.tunnel = subprocess.Popen(
                    [CLOUDFLARED, "tunnel", "--url", self.reader_url()],
                    cwd=BASE_DIR, creationflags=NO_WINDOW,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1)
            except Exception as e:
                log(f"! Không bật được cloudflared: {e}")
                if self.stop.wait(backoff):
                    return
                backoff = min(backoff * 2, TUNNEL_BACKOFF_MAX)
                continue
            found = None
            for line in self.tunnel.stdout:            # đọc output tới khi tiến trình thoát
                m = TUNNEL_RE.search(line)
                if not m or m.group(1) == "api":       # 'api.trycloudflare.com' = host lỗi, bỏ
                    continue
                url = m.group(0)
                if url != found:
                    found = url
                    self.on_new_link(url)              # đặt link + XÁC MINH rồi mới báo Telegram
            self.tunnel.wait()
            if self.stop.is_set():
                return
            ran = time.monotonic() - started
            self.link = None
            if ran >= TUNNEL_HEALTHY_SECS:             # tunnel vừa chạy ổn định -> reset backoff
                backoff = TUNNEL_BACKOFF_MIN
                log(f"! cloudflared thoát sau {ran:.0f}s — tạo lại sau {backoff}s.")
                if self.stop.wait(backoff):
                    return
            else:                                      # thoát nhanh = chưa lập nổi tunnel -> giãn
                log(f"! cloudflared thoát nhanh ({ran:.0f}s, chưa lập nổi tunnel) — "
                    f"chờ {backoff}s (backoff) rồi thử lại.")
                if self.stop.wait(backoff):
                    return
                backoff = min(backoff * 2, TUNNEL_BACKOFF_MAX)

    def on_new_link(self, url):
        with self.lock:
            self.link = url          # /link trả link mới nhất ngay (kể cả chưa xác minh)
        log(f"Link ứng viên: {url}")
        try:
            with open(LINK_FILE, "w", encoding="utf-8") as f:
                f.write(url + "\n")
        except OSError:
            pass
        # Xác minh + báo Telegram ở LUỒNG NỀN: không chặn vòng đọc stdout của cloudflared,
        # và chỉ báo khi link THẬT SỰ mở được reader + KHÁC link đã báo lần trước (chống spam).
        self._run_bg(self._confirm_and_notify, url)

    def _reader_alive(self):
        """GET reader NỘI BỘ 127.0.0.1 -> đang phục vụ HTTP chưa. Localhost nên KHÔNG dính
        hairpin/Cloudflare (khác hẳn GET link công khai) -> tín hiệu đáng tin để biết mở link
        ra có 502 không."""
        try:
            req = urllib.request.Request(self.reader_url(), method="GET",
                                         headers={"User-Agent": "toony-health"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return 200 <= r.status < 500
        except Exception:
            return False

    def _confirm_and_notify(self, url):
        # cloudflared đã IN url = ĐÃ đăng ký với edge (tunnel dùng được cho người đọc). Ta chỉ
        # chờ READER NỘI BỘ sẵn sàng để user mở link không dính 502, rồi báo. KHÔNG GET link
        # công khai để "xác minh" nữa: mạng server không hairpin về chính nó (sai ~2/3) → từng
        # làm health_loop giết nhầm tunnel tốt + kẹt 120s báo 'chưa xác minh'.
        deadline = time.monotonic() + READER_WAIT
        while time.monotonic() < deadline:
            with self.lock:
                if self.link != url:
                    return           # đã có link mới hơn (cloudflared restart) -> để lần đó lo
            if self._reader_alive():
                break
            if self.stop.wait(READER_RETRY):
                return
        with self.lock:
            if self.link != url or url == self._notified_link:
                return               # link đã đổi / đã báo rồi -> khỏi báo
            self._notified_link = url
        log(f"LINK MỚI: {url}")
        notify_all(self.cfg, f"📖 Link đọc truyện MỚI:\n{url}\n\n(Link tạm — đổi mỗi lần "
                             f"server khởi động lại. Mở link rồi Thêm-vào-màn-hình-chính.)")

    def cur_link(self):
        with self.lock:
            return self.link

    # vòng NGHE Telegram: long-poll getUpdates, tự gom chat_id (cả 2 anh em) và trả
    # lời lệnh /link, /start. CHỈ một tiến trình được poll 1 token (đừng chạy 2 nơi).
    @staticmethod
    def _register_commands(token):
        """Đăng ký danh sách lệnh -> Telegram hiện menu gợi ý khi gõ '/'."""
        cmds = [
            {"command": "link", "description": "Lấy link đọc hiện tại"},
            {"command": "whoami", "description": "Xem chat_id của bạn"},
            {"command": "tai", "description": "Tải truyện: /tai <link> [chương vd 1-20] (admin)"},
            {"command": "trangthai", "description": "Xem tải đang chạy + hàng chờ (admin)"},
            {"command": "stop", "description": "Dừng tải + xoá hàng chờ của bạn (admin)"},
            {"command": "killnow", "description": "Chỉ dừng truyện đang tải của bạn (admin)"},
            {"command": "clearq", "description": "Chỉ xoá hàng chờ của bạn (admin)"},
            {"command": "stopall", "description": "Dừng tất cả + xoá sạch hàng chờ (admin)"},
            {"command": "update", "description": "Cập nhật code (admin)"},
            {"command": "watchlist", "description": "Xem danh sách truyện auto-check (admin)"},
            {"command": "watch", "description": "Thêm truyện vào danh sách: /watch <link> (admin)"},
            {"command": "unwatch", "description": "Bỏ truyện: /unwatch <số|link> (admin)"},
            {"command": "checknow", "description": "Kiểm tra chương mới ngay (admin)"},
            {"command": "adminlist", "description": "Xem chat đã đăng ký / admin"},
            {"command": "adminclaim", "description": "Nhận quyền admin (khi chưa có ai)"},
            {"command": "adminadd", "description": "Thêm admin: /adminadd <id>"},
            {"command": "adminremove", "description": "Bỏ admin: /adminremove <id>"},
            {"command": "help", "description": "Danh sách lệnh"},
            {"command": "start", "description": "Đăng ký nhận link"},
        ]
        tg_api(token, "setMyCommands", {"commands": json.dumps(cmds, ensure_ascii=False)})

    def telegram_loop(self):
        token = self.cfg.get("bot_token")
        if not token:
            return
        self._register_commands(token)
        offset = None
        while not self.stop.is_set():
            params = {"timeout": 25}
            if offset is not None:
                params["offset"] = offset
            res = tg_api(token, "getUpdates", params, timeout=35)  # > long-poll 25s
            if not res or not res.get("ok"):
                self.stop.wait(5)   # lỗi/mạng -> nghỉ chút rồi thử lại
                continue
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1          # xác nhận đã xử lý (kể cả lệnh lỗi)
                try:
                    self._process_update(token, upd)
                except Exception as e:
                    log(f"! Lỗi xử lý lệnh Telegram: {e}")   # 1 lệnh lỗi KHÔNG làm chết bot

    def _process_update(self, token, upd):
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is None:
            return
        is_new = add_chat(self.cfg, cid)       # tự đăng ký người nhận
        raw = (msg.get("text") or "").strip()  # GIỮ nguyên hoa/thường cho URL/tham số
        text = raw.lower()                     # chỉ để so khớp từ khóa lệnh
        if text.startswith("/"):
            log(f"Lệnh Telegram từ {cid}: {text[:50]}")
        link = self.cur_link()
        if text.startswith("/link") or text.startswith("/latest"):
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": f"📖 Link hiện tại:\n{link}" if link
                        else "Chưa có link (server đang khởi động). Thử lại chút nữa.",
                "disable_web_page_preview": "true"})
        elif text.startswith("/update"):
            self._run_bg(self.handle_update, token, cid)
        elif text.startswith("/watchlist"):   # PHẢI xét trước /watch (tiền tố trùng)
            self.handle_watchlist(token, cid)
        elif text.startswith("/watch"):
            self.handle_watch(token, cid, raw)
        elif text.startswith("/unwatch"):
            self.handle_unwatch(token, cid, raw)
        elif text.startswith("/checknow"):
            self.handle_checknow(token, cid, raw)
        elif text.startswith("/whoami"):
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": f"chat_id của bạn: {cid}"})
        elif text.startswith("/help"):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": HELP_TEXT,
                "disable_web_page_preview": "true"})
        elif text.startswith("/adminclaim"):
            self.handle_admin(token, cid, "claim", raw)
        elif text.startswith("/adminlist"):
            self.handle_admin(token, cid, "list", raw)
        elif text.startswith("/adminadd"):
            self.handle_admin(token, cid, "add", raw)
        elif text.startswith("/adminremove"):
            self.handle_admin(token, cid, "remove", raw)
        elif text.startswith("/trangthai"):
            self.handle_status(token, cid)
        elif text.startswith("/tai"):
            self.handle_tai(token, cid, raw)
        elif text.startswith("/stopall"):
            self.handle_cancel(token, cid, kill=True, clear=True, scope_all=True)
        elif text.startswith("/stop"):
            self.handle_cancel(token, cid, kill=True, clear=True, scope_all=False)
        elif text.startswith("/killnow"):
            self.handle_cancel(token, cid, kill=True, clear=False, scope_all=False)
        elif text.startswith("/clearq"):
            self.handle_cancel(token, cid, kill=False, clear=True, scope_all=False)
        elif text.startswith("/start") or is_new:
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "✅ Đã đăng ký nhận link đọc truyện.\n"
                        + (f"📖 Link hiện tại:\n{link}" if link
                           else "Sẽ gửi link khi có.")
                        + "\n\nGõ /link bất cứ lúc nào để lấy link mới nhất.",
                "disable_web_page_preview": "true"})

    # (Đã BỎ health_loop: nó GET link CÔNG KHAI để đoán tunnel sống/chết, nhưng mạng server
    # không hairpin về chính tunnel của nó (sai ~2/3) → giết nhầm tunnel đang tốt cho người đọc,
    # gây đổi link liên tục mỗi ~3'. Giờ tin cloudflared tự reconnect/thoát: cloudflared chết
    # thật thì run_tunnel bắt được + tạo link mới. Reader chết thì run_reader bật lại.)

    # heartbeat: ping RA dịch vụ ngoài (healthchecks.io) -> nó tự báo bạn KHI SERVER SẬP
    def heartbeat_loop(self):
        """Dead-man's-switch vá đúng khoảng mù 'mất mạng thì bot không tự báo được'.
        Mỗi HEARTBEAT_EVERY giây ping 1 cú RA URL bí mật ở healthchecks.io. Dịch vụ đó
        (chạy trên hạ tầng của họ, vẫn sống khi máy này chết) thấy im lặng quá kỳ hạn ->
        gửi cảnh báo cho bạn (email/Telegram). Ping THẤT BẠI (đang mất mạng/DNS, hoặc
        supervisor/máy chết) là ĐÚNG Ý ĐỒ: chính sự im lặng đó kích cảnh báo."""
        url = (self.cfg.get("heartbeat_url") or "").strip()
        if not url:
            log("! Chưa có heartbeat_url trong notify-config.json — bỏ qua heartbeat. "
                "(Muốn được báo khi server sập: tạo 1 check ở healthchecks.io, dán URL ping vào.)")
            return
        log(f"Heartbeat: bật — ping mỗi {HEARTBEAT_EVERY}s tới dịch vụ giám sát ngoài.")
        last_ok = None
        while not self.stop.is_set():
            ok = False
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "toony-heartbeat"})
                with urllib.request.urlopen(req, timeout=HEARTBEAT_TIMEOUT) as r:
                    ok = 200 <= r.status < 300
            except Exception:
                ok = False
            if ok != last_ok:   # CHỈ log khi đổi trạng thái -> khỏi phình log mỗi 5'
                log("Heartbeat: OK." if ok else
                    "! Heartbeat: ping THẤT BẠI (mất mạng/DNS?) — nếu kéo dài, dịch vụ ngoài sẽ báo.")
                last_ok = ok
            if self.stop.wait(HEARTBEAT_EVERY):
                return

    @staticmethod
    def _kill(proc):
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

    @staticmethod
    def _kill_comix_chrome():
        """Giết Chromium (Playwright, tải comix) nhận diện qua profile 'comix-profile' trong
        command line — KHÔNG đụng Chrome thường của user. Dùng khi kill job treo: terminate
        tiến trình python downloader KHÔNG giết được chrome CON (Playwright mở) -> nó thành
        mồ côi ôm profile -> đúng thứ gây wedge lần sau. Best-effort, Windows-only."""
        if os.name != "nt":
            return
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                "Where-Object { $_.CommandLine -match 'comix-profile' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
                "-ErrorAction SilentlyContinue }"],
                creationflags=NO_WINDOW, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            log(f"! Không kill được Chromium comix treo: {e}")

    # --- Lệnh /update: kéo code mới từ git rồi restart reader --------------
    @staticmethod
    def _run_bg(fn, *a):
        """Chạy fn ở luồng nền để việc chậm (git/tải) không chặn vòng nghe Telegram."""
        threading.Thread(target=fn, args=a, daemon=True).start()

    @staticmethod
    def _git(*args, timeout=120):
        """Chạy 1 lệnh git trong thư mục dự án. GIT_TERMINAL_PROMPT=0 để KHÔNG bao giờ
        treo chờ nhập mật khẩu; có timeout để mạng nghẽn không kẹt vô hạn."""
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
        try:
            r = subprocess.run(["git", "-C", BASE_DIR, *args],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", creationflags=NO_WINDOW,
                               timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError("git quá thời gian (mạng server ra GitHub chậm/nghẽn).")
        if r.returncode != 0:
            raise RuntimeError((r.stderr or r.stdout or "git error").strip()[:300])
        return (r.stdout or "").strip()

    def handle_update(self, token, cid):
        """Kéo code mới nhất (git fetch + reset --hard origin/main) rồi khởi động
        lại reader để áp dụng. CHỈ cho chat có quyền: admin_chat_ids nếu được cấu
        hình, không thì mọi chat_ids đã đăng ký (bot ẩn danh nên đủ dùng cho 2 anh em;
        muốn siết thì thêm "admin_chat_ids": ["<chat_id_cua_ban>"] vào notify-config)."""
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "⛔ Bạn không có quyền dùng /update."})
            return
        if getattr(self, "_updating", False):
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "⏳ Đang có một lần cập nhật chạy dở — đợi nó xong đã."})
            return
        self._updating = True
        try:
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⏳ Đang kéo code mới (git)..."})
            try:
                before = self._git("rev-parse", "HEAD")
                self._git("fetch", "origin", "--quiet")
                self._git("reset", "--hard", "origin/main")
                after = self._git("rev-parse", "HEAD")
            except Exception as e:
                log(f"! /update lỗi git: {e}")
                tg_api(token, "sendMessage", {"chat_id": cid, "text": f"❌ Lỗi git:\n{e}"})
                return
            if before == after:
                tg_api(token, "sendMessage", {"chat_id": cid,
                    "text": "✔ Không có gì mới — code đã là bản mới nhất."})
                return
            try:
                files = [f for f in self._git("diff", "--name-only", before, after).splitlines()
                         if f.strip()]
            except Exception:
                files = []
            warn = ("\n⚠️ supervisor.py đã đổi — cần restart tay (server-BAT) để nạp phần này."
                    if any("supervisor.py" in f for f in files) else "")
            log(f"/update: {before[:7]} -> {after[:7]} ({len(files)} file). Restart reader.")
            self._kill(self.reader)     # run_reader tự bật lại với code mới trên đĩa
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": f"✅ Đã cập nhật {len(files)} file — reader chạy lại. "
                        f"Link cũ vẫn dùng được (không đổi).{warn}",
                "disable_web_page_preview": "true"})
        finally:
            self._updating = False

    # --- Quyền admin (admin_chat_ids trong notify-config.json) -------------
    def _admins(self):
        return [str(x) for x in (self.cfg.get("admin_chat_ids") or [])]

    def _is_admin(self, cid):
        admins = self._admins()
        return (not admins) or (str(cid) in admins)   # chưa set admin -> tạm ai cũng được

    def _set_admins(self, ids):
        seen, out = set(), []
        for x in ids:
            x = str(x)
            if x and x not in seen:
                seen.add(x); out.append(x)
        self.cfg["admin_chat_ids"] = out
        save_config(self.cfg)

    def handle_admin(self, token, cid, sub, raw):
        """Quản lý admin_chat_ids qua các lệnh 1 TỪ (Telegram chỉ nhận lệnh không dấu
        cách): /adminclaim /adminlist /adminadd <id> /adminremove <id>."""
        parts = raw.split()
        arg = parts[1] if len(parts) > 1 else None
        admins = self._admins()
        if sub == "claim":
            if admins:
                tg_api(token, "sendMessage", {"chat_id": cid,
                    "text": "Đã có admin rồi — nhờ admin dùng /adminadd <id>."})
            else:
                self._set_admins([cid])
                tg_api(token, "sendMessage", {"chat_id": cid,
                    "text": "✅ Bạn là admin đầu tiên. /adminadd <id> để thêm người, "
                            "/adminlist để xem các chat đã nhắn bot."})
            return
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⛔ Bạn không phải admin."})
            return
        if sub == "list":
            ids = [str(x) for x in (self.cfg.get("chat_ids") or [])]
            lines = [("⭐ " if i in admins else "• ") + i for i in ids] or ["(chưa ai nhắn bot)"]
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "Chat đã đăng ký (⭐ = admin):\n" + "\n".join(lines)
                        + "\n\n/adminadd <id> | /adminremove <id>"})
        elif sub == "add" and arg:
            self._set_admins(admins + [arg])
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "✅ Thêm admin: " + arg})
        elif sub == "remove" and arg:
            self._set_admins([a for a in admins if a != arg])
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "✅ Bỏ admin: " + arg})
        else:
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "Cú pháp: /adminlist | /adminclaim | /adminadd <id> | /adminremove <id>"})

    # --- Hàng đợi tải BỀN HOÁ (sống qua restart supervisor) -----------------
    def _save_jobs_locked(self):
        """Ghi _jobs ra đĩa (nguyên tử). PHẢI đang giữ self._dlq_lock khi gọi."""
        try:
            os.makedirs(META_DIR, exist_ok=True)
            tmp = QUEUE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"jobs": self._jobs}, f, ensure_ascii=False, indent=1)
            os.replace(tmp, QUEUE_FILE)
        except OSError as e:
            log(f"! Không ghi được hàng đợi tải: {e}")

    @staticmethod
    def _load_jobs():
        """Đọc hàng đợi đã bền hoá lúc khởi động. Job 'running' (bị restart cắt giữa
        chừng) -> đánh 'resumed' để báo 'đang tiếp tục'. Tất cả về 'pending' để chạy lại."""
        try:
            with open(QUEUE_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return []
        raw = data.get("jobs") if isinstance(data, dict) else None
        out = []
        if isinstance(raw, list):
            for j in raw:
                if isinstance(j, dict) and j.get("url"):
                    out.append({"url": str(j["url"]), "cid": j.get("cid"),
                                "state": "pending",
                                "resumed": j.get("state") == "running",
                                "chapters": j.get("chapters")})
        return out

    def _kill_stray_downloaders(self):
        """Giết mọi comic_downloader.py còn sót từ supervisor phiên trước — server-BAT
        KHÔNG dọn nó (chỉ giết supervisor.py/reader_server.py) nên con mồ côi có thể còn
        sống. Dọn TRƯỚC khi resume để không có 2 tiến trình cùng tải 1 truyện (chống trùng
        request -> chặn IP). Windows-only (server là Windows)."""
        if os.name != "nt":
            return
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR "
                "Name='pythonw.exe'\" | Where-Object { $_.CommandLine -match "
                "'comic_downloader\\.py' } | ForEach-Object { Stop-Process -Id "
                "$_.ProcessId -Force -ErrorAction SilentlyContinue }; "
                # Chromium (Playwright, tải comix) mồ côi: nhận diện qua profile
                # riêng 'comix-profile' trong command line — KHÔNG đụng Chrome thường.
                "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                "Where-Object { $_.CommandLine -match 'comix-profile' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
                "-ErrorAction SilentlyContinue }"],
                creationflags=NO_WINDOW, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            log(f"! Không dọn được downloader lạc: {e}")

    def resume_jobs(self):
        """Lúc khởi động: dọn downloader lạc rồi nạp lại hàng đợi đã bền hoá -> worker
        tự tải tiếp (resume bỏ qua chương .done). Gọi TRƯỚC khi start các luồng."""
        self._kill_stray_downloaders()
        loaded = self._load_jobs()
        if loaded:
            with self._dlq_lock:
                self._jobs = loaded
                self._save_jobs_locked()
            log(f"Nạp lại {len(loaded)} truyện trong hàng đợi từ phiên trước -> tải tiếp.")

    def _enqueue_jobs(self, pairs):
        """Thêm [(url, cid[, chapters]), ...] vào hàng đợi tải. chapters = None -> tải cả
        truyện; hoặc chuỗi chọn chương '5,7,20-25' (như --chapters). Chống trùng theo CẢ
        (url, chapters) nên tải cùng truyện khác dải chương KHÔNG bị coi là trùng. Trả
        (added, dup). Dùng chung cho /tai và auto-check chương mới."""
        added, dup = [], 0
        with self._dlq_lock:
            have = {(j["url"], j.get("chapters")) for j in self._jobs}
            for pair in pairs:
                url, cid = pair[0], pair[1]
                chapters = pair[2] if len(pair) > 2 else None
                key = (url, chapters)
                if key in have:
                    dup += 1
                else:
                    self._jobs.append({"url": url, "cid": cid, "state": "pending",
                                       "resumed": False, "chapters": chapters})
                    have.add(key)
                    added.append(url)
            if added:
                self._save_jobs_locked()
                self._dlq_lock.notify()   # đánh thức worker
        return added, dup

    # --- Tải truyện qua bot (/tai <url...>) -> hàng đợi, worker chạy nền ----
    def handle_tai(self, token, cid, raw):
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⛔ Bạn không phải admin."})
            return
        words = raw.split()[1:]
        urls = [w for w in words if w.startswith("http")]
        # Phần còn lại (không phải link) = chọn chương, vd "1-20" hoặc "5,7,20-25".
        # Gộp mọi mẩu rồi bỏ khoảng trắng + gộp dấu phẩy thừa -> chịu được cả
        # "5,7,20-25", "5, 7, 20-25" lẫn "5 7 20-25".
        spec_raw = ",".join(w for w in words if not w.startswith("http"))
        chapters = re.sub(r",+", ",", spec_raw.replace(" ", "")).strip(",") or None
        if not urls:
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "Gửi: /tai <link truyện> [chương] [link2 ...]\n"
                        "Ví dụ:\n"
                        "  /tai https://... — tải cả truyện\n"
                        "  /tai https://... 1-20 — chỉ chương 1→20\n"
                        "  /tai https://... 5,7,20-25 — chương lẻ + dải"})
            return
        if chapters and not re.fullmatch(r"[0-9.,\-]+", chapters):
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": f"⚠ Chọn chương không hợp lệ: “{chapters}”.\n"
                        "Chỉ dùng số, dấu phẩy, gạch nối — vd 1-20 hoặc 5,7,20-25."})
            return
        added, dup = self._enqueue_jobs([(u, cid, chapters) for u in urls])
        parts = []
        scope = f"chương {chapters}" if chapters else "cả truyện"
        if added:
            parts.append(f"📥 Đã thêm {len(added)} truyện vào hàng đợi ({scope}).")
        if dup:
            parts.append(f"⏭ {dup} truyện đã có trong hàng đợi cùng dải chương (bỏ qua).")
        parts.append("Gõ /trangthai để xem đang tải gì và còn chờ mấy truyện.")
        tg_api(token, "sendMessage", {"chat_id": cid, "text": "\n".join(parts),
            "disable_web_page_preview": "true"})

    @staticmethod
    def _slug(url):
        """Rút tên gọn từ URL để hiển thị (bỏ đuôi '/', lấy cụm cuối có ý nghĩa)."""
        s = url.rstrip("/").split("/")
        return s[-1] if s and s[-1] else (s[-2] if len(s) > 1 else url)

    @classmethod
    def _job_label(cls, job):
        """Tên gọn + dải chương (nếu có) để hiển thị trong /trangthai và tin báo."""
        lbl = cls._slug(job["url"])
        return f"{lbl} (ch {job['chapters']})" if job.get("chapters") else lbl

    def handle_status(self, token, cid):
        """/trangthai — ảnh chụp hàng đợi: truyện đang tải (kèm tiến độ đọc từ log)
        + danh sách đang chờ. Đọc trong khoá để không trúng lúc worker đổi state."""
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⛔ Bạn không phải admin."})
            return
        with self._dlq_lock:
            cur = self._dl_cur
            logpos = self._dl_logpos
            pending = [j for j in self._jobs if j["state"] == "pending"]
        lines = []
        if cur:
            prog = self._read_log_tail(logpos, maxchars=120)
            head = "🔄 Đang tiếp tục" if cur.get("resumed") else "▶️ Đang tải"
            lines.append(f"{head}: {self._job_label(cur)}")
            if prog:
                lines.append(f"   {prog}")
        else:
            lines.append("💤 Không có truyện nào đang tải.")
        if pending:
            lines.append(f"⏳ Đang chờ ({len(pending)}):")
            for i, j in enumerate(pending[:15], 1):
                lines.append(f"   {i}. {self._job_label(j)}")
            if len(pending) > 15:
                lines.append(f"   … và {len(pending) - 15} truyện nữa")
        else:
            lines.append("⏳ Hàng chờ trống.")
        tg_api(token, "sendMessage", {"chat_id": cid, "text": "\n".join(lines),
            "disable_web_page_preview": "true"})

    def _drain_queue(self, cid=None):
        """Xoá các job ĐANG CHỜ (pending) khỏi hàng đợi + file, trả số đã xoá.
        cid=None -> xoá tất cả; có cid -> chỉ của chat đó. KHÔNG đụng job đang chạy
        (việc kill do handle_cancel lo). Có khoá để không giẫm worker/lệnh khác."""
        removed = 0
        with self._dlq_lock:
            keep = []
            for j in self._jobs:
                if j["state"] == "pending" and (cid is None or str(j["cid"]) == str(cid)):
                    removed += 1
                else:
                    keep.append(j)
            self._jobs = keep
            self._save_jobs_locked()
        return removed

    def handle_cancel(self, token, cid, kill, clear, scope_all):
        """Huỷ tải: kill truyện đang chạy và/hoặc xoá hàng chờ.
        scope_all=False -> chỉ đụng request do CHÍNH người gọi gửi; True -> mọi người."""
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⛔ Bạn không phải admin."})
            return
        parts = []
        # 1) Kill truyện đang tải (nếu yêu cầu)
        if kill:
            with self._dlq_lock:
                cur = self._dl_cur
                proc = self._dl_proc
            if not cur or not proc:
                parts.append("Không có truyện nào đang tải.")
            elif not scope_all and str(cur.get("cid")) != str(cid):
                parts.append("Truyện đang tải không phải của bạn "
                             "(dùng /stopall nếu muốn dừng tất cả).")
            else:
                self._dl_cancelled = True     # huỷ tay -> worker xoá job khỏi file (khỏi resume)
                self._kill(proc)
                parts.append(f"⏹ Đã dừng truyện đang tải:\n{cur['url']}")
        # 2) Xoá hàng chờ (nếu yêu cầu)
        if clear:
            n = self._drain_queue(cid=None if scope_all else cid)
            with self._dlq_lock:
                left = sum(1 for j in self._jobs if j["state"] == "pending")
            scope_txt = "" if scope_all else " của bạn"
            parts.append(f"🗑 Đã xoá {n} truyện trong hàng chờ{scope_txt} (còn lại: {left}).")
        tg_api(token, "sendMessage", {"chat_id": cid,
            "text": "\n".join(parts) if parts else "Không có gì để huỷ.",
            "disable_web_page_preview": "true"})

    @staticmethod
    def _read_log_tail(start_pos, maxchars=200):
        """Đọc phần log downloader ghi TỪ vị trí start_pos (đầu của job này) -> lấy
        dòng cuối có nội dung làm đuôi báo lỗi. Bỏ \\r (downloader ghi đè tiến độ)."""
        try:
            with open(DL_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                f.seek(start_pos)
                text = f.read()
        except OSError:
            return ""
        lines = [l for l in text.replace("\r", "\n").splitlines() if l.strip()]
        return lines[-1][:maxchars] if lines else ""

    @staticmethod
    def _read_summary(start_pos, maxchars=1500):
        """Trích khối '===== TỔNG KẾT' downloader in ở cuối lượt (số liệu chương + ảnh
        OK/thiếu/hỏng + chi tiết chương thiếu trang) -> đính vào tin 'Tải xong'."""
        try:
            with open(DL_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                f.seek(start_pos)
                text = f.read()
        except OSError:
            return ""
        text = text.replace("\r", "\n")
        idx = text.rfind("===== TỔNG KẾT")
        if idx < 0:
            return ""
        lines = [l.rstrip() for l in text[idx:].splitlines() if l.strip()]
        return "\n".join(lines)[:maxchars]

    @staticmethod
    def _read_log_text(start_pos, maxchars=4000):
        """Đọc NGUYÊN đoạn log của job (từ start_pos) -> quét dấu hiệu lỗi mạng. Khác
        _read_log_tail (chỉ lấy 1 dòng cuối): marker 'getaddrinfo' có thể nằm ở dòng
        giữa (vd asura in getaddrinfo rồi in 'Không lấy được danh sách chương' ở dòng cuối)."""
        try:
            with open(DL_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                f.seek(start_pos)
                text = f.read()
        except OSError:
            return ""
        return text[-maxchars:]

    def _wait_or_stall(self, proc, start_pos):
        """Chờ downloader xong; nếu LOG ĐỨNG IM quá lâu (nghi treo câm) -> kill downloader
        + Chromium comix, trả (rc, stalled=True). Bình thường job xong/chết -> (rc, False).

        Chỉ đọc SIZE log (os.path.getsize = 1 stat, O(1) — không đọc nội dung, không phụ
        thuộc log to/nhỏ). Nhịp do proc.wait(timeout=POLL) giữ (chờ ở tầng OS, không busy-
        loop); hàm này CHỈ tồn tại trong vòng đời 1 job (rảnh thì worker ngủ ở download_loop,
        không gọi tới đây). Log chỉ tăng đơn điệu trong 1 job (cắt-nhỏ chỉ xảy ra ĐẦU job)."""
        limit = int(self.cfg.get("dl_stall_limit", DL_STALL_LIMIT) or DL_STALL_LIMIT)
        try:
            last_size = os.path.getsize(DL_LOG_FILE)
        except OSError:
            last_size = start_pos
        last_grow = time.monotonic()
        while True:
            try:
                rc = proc.wait(timeout=DL_STALL_POLL)
                return rc, False                 # tải xong / tự thoát (kể cả bị /stop kill)
            except subprocess.TimeoutExpired:
                pass
            if self.stop.is_set():               # supervisor tắt -> kill để khỏi mồ côi rồi thoát
                self._kill(proc)
                self._kill_comix_chrome()
                try:
                    proc.wait(timeout=15)
                except Exception:
                    pass
                return None, False
            try:
                size = os.path.getsize(DL_LOG_FILE)
            except OSError:
                size = last_size
            now = time.monotonic()
            if size > last_size:
                last_size, last_grow = size, now
            elif now - last_grow > limit:
                log(f"! Tải ĐỨNG IM > {limit}s (nghi treo câm) — kill downloader + Chromium comix.")
                self._kill(proc)
                self._kill_comix_chrome()        # terminate python KHÔNG giết chrome con -> diệt riêng
                try:
                    proc.wait(timeout=15)
                except Exception:
                    pass
                return proc.returncode, True

    def download_loop(self):
        """Worker: tải tuần tự từng job trong _jobs (bền hoá ra đĩa), 1 lượt/lúc.
        Output downloader ghi ra FILE (không PIPE) -> supervisor chết không làm vỡ pipe
        + tail xem tiến độ real-time. Job xong (kể cả lỗi) -> xoá khỏi file; job bị
        RESTART giết đột ngột -> code xoá không kịp chạy -> ở lại file -> phiên sau resume."""
        while not self.stop.is_set():
            with self._dlq_lock:
                has_pending = any(j["state"] == "pending" for j in self._jobs)
                if not has_pending:
                    self._dlq_lock.wait(timeout=1)     # ngủ tới khi có job mới / hết 1s
                    continue
            # Có job chờ nhưng MẠNG CHƯA LÊN -> đừng chạy (sẽ fail ngay rồi bị coi là lỗi).
            # Chờ mạng về; hàng đợi GIỮ NGUYÊN (đêm 11/08 mất 8 truyện vì bỏ qua bước này).
            if _net_status() != "ok":
                if self.stop.wait(NET_RECHECK):
                    return
                continue
            with self._dlq_lock:
                job = next((j for j in self._jobs if j["state"] == "pending"), None)
                if job is None:
                    continue
                job["state"] = "running"
                self._save_jobs_locked()
                self._dl_proc = None
                self._dl_cur = job
                self._dl_cancelled = False
            url, cid = job["url"], job.get("cid")
            token = self.cfg.get("bot_token")
            # Chỉ báo 'bắt đầu' ở lần chạy ĐẦU của job; lần thử lại do lỗi mạng (net_retries>0)
            # thì im để khỏi lặp tin mỗi vòng.
            if token and cid is not None and job.get("net_retries", 0) == 0:
                scope = f"\n(chỉ chương {job['chapters']})" if job.get("chapters") else ""
                tg_api(token, "sendMessage", {"chat_id": cid,
                    "text": (f"🔄 Đang tiếp tục truyện bị gián đoạn:\n{url}{scope}"
                             if job.get("resumed") else f"⏳ Bắt đầu tải:\n{url}{scope}"),
                    "disable_web_page_preview": "true"})
            start_pos = 0
            keep = False        # True = lỗi MẠNG tạm -> giữ job trong hàng đợi, thử lại (không xoá)
            stalled = False     # True = job treo câm (log đứng im) -> bị kill bởi stall-watchdog
            try:
                try:      # cắt log nếu phình to
                    if os.path.getsize(DL_LOG_FILE) > DL_LOG_MAX:
                        open(DL_LOG_FILE, "w", encoding="utf-8").close()
                except OSError:
                    pass
                stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(DL_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"\n=== [{stamp}] "
                            f"{'TIẾP TỤC' if job.get('resumed') else 'BẮT ĐẦU'}: {url} ===\n")
                try:
                    start_pos = os.path.getsize(DL_LOG_FILE)
                except OSError:
                    start_pos = 0
                with self._dlq_lock:                      # để /trangthai đọc tiến độ đúng job
                    self._dl_logpos = start_pos
                logf = open(DL_LOG_FILE, "ab")            # con ghi thẳng vào file (nối tiếp)
                try:
                    cmd = [sys.executable, "-u",
                           os.path.join(BASE_DIR, "comic_downloader.py"), url]
                    if job.get("chapters"):               # chọn chương cụ thể (như tai-truyen.bat)
                        cmd += ["--chapters", job["chapters"]]
                    proc = subprocess.Popen(              # -u: không buffer -> tail real-time
                        cmd, cwd=BASE_DIR, creationflags=NO_WINDOW,
                        stdout=logf, stderr=subprocess.STDOUT)
                    with self._dlq_lock:
                        self._dl_proc = proc
                    # Chờ tải xong, KÈM stall-watchdog: log đứng im quá lâu -> kill + báo treo.
                    rc, stalled = self._wait_or_stall(proc, start_pos)
                finally:
                    logf.close()
                if rc is None and self.stop.is_set():
                    return   # supervisor đang tắt (đã kill proc) -> thoát êm; job 'running' để resume
                if self._dl_cancelled:
                    msg = (f"⏹ Đã huỷ tải:\n{url}\n"
                           "(Tải lại bằng /tai sẽ tự bỏ qua chương đã xong, "
                           "tiếp tục từ chỗ dở.)")
                elif stalled:
                    # Treo câm (log đứng im quá ngưỡng) -> đã kill. GIỮ job thử lại (resume bỏ
                    # qua chương .done -> không mất ảnh); quá DL_STALL_RETRY_MAX -> bỏ (daily tự
                    # enqueue lại). Báo lần treo ĐẦU + lần BỎ; im ở các lần thử lại giữa.
                    job["stall_retries"] = job.get("stall_retries", 0) + 1
                    n = job["stall_retries"]
                    if n > DL_STALL_RETRY_MAX:
                        log(f"! Job treo câm quá {DL_STALL_RETRY_MAX} lần — bỏ: {url}")
                        msg = (f"❌ Tải bị treo lặp lại (đã tự kill {n} lần) — bỏ qua:\n{url}\n"
                               "(Chạy /tai lại để thử tiếp; chương đã xong tự bỏ qua.)")
                    else:
                        keep = True
                        log(f"! Job treo câm — giữ lại thử lại (lần {n}): {url}")
                        msg = (f"⚠️ Tải bị treo (đứng im quá lâu) — đã tự kill Chromium và sẽ "
                               f"thử lại:\n{url}") if n == 1 else None
                elif rc == 0:
                    summary = self._read_summary(start_pos)   # số liệu chương + ảnh
                    msg = f"✅ Tải xong:\n{url}" + (("\n\n" + summary) if summary else "")
                else:
                    # LỖI MẠNG (mất mạng lúc này, HOẶC log có dấu hiệu mạng: getaddrinfo,
                    # 'mạng chập chờn'...) -> GIỮ job trong hàng đợi, thử lại sau; KHÔNG xoá
                    # (đêm 11/08 mất sạch 8 truyện vì xoá mọi job rc≠0). Chỉ khi mạng đã OK
                    # mà vẫn fail kiểu-mạng quá DL_NET_RETRY_MAX lần -> coi lỗi nội dung, mới xoá.
                    st = _net_status()
                    body = self._read_log_text(start_pos).lower()
                    net_like = st != "ok" or any(k in body for k in NET_ERR_MARKERS)
                    if net_like and st == "ok":
                        job["net_retries"] = job.get("net_retries", 0) + 1
                    if net_like and (st != "ok" or job.get("net_retries", 0) <= DL_NET_RETRY_MAX):
                        keep = True
                        msg = None      # lỗi mạng tạm -> KHÔNG nhắn (tránh spam khi mạng chập chờn)
                        log(f"! Tải lỗi MẠNG ({st}) — giữ job, thử lại sau: {url}")
                    else:
                        tail = self._read_log_tail(start_pos)
                        msg = f"❌ Lỗi tải:\n{url}" + (("\n" + tail) if tail else "")
            except Exception as e:
                msg = f"❌ Lỗi tải:\n{url}\n{e}"
            # Gửi báo TRƯỚC, rồi mới xoá job khỏi file: nếu bị giết giữa 2 việc thì thà
            # báo trùng (resume chạy lại thấy .done -> báo 'xong' lần nữa) còn hơn mất tin.
            if msg and token and cid is not None:
                tg_api(token, "sendMessage", {"chat_id": cid, "text": msg,
                    "disable_web_page_preview": "true"})
            with self._dlq_lock:
                self._dl_proc = None
                self._dl_cur = None
                self._dl_logpos = 0
                if keep:
                    job["state"] = "pending"      # trả về hàng đợi để thử lại (KHÔNG xoá)
                else:
                    try:
                        self._jobs.remove(job)
                    except ValueError:
                        pass
                self._save_jobs_locked()
            # backoff trước khi thử lại job này (treo câm nghỉ lâu hơn lỗi mạng thoáng qua)
            if keep and self.stop.wait(DL_STALL_BACKOFF if stalled else NET_RECHECK):
                return

    # --- Watchlist + auto-check chương mới ---------------------------------
    @staticmethod
    def _fmt_num(n):
        """50.0 -> 50 ; 12.5 -> 12.5 ; None/khác -> nguyên trạng (hiển thị số chương)."""
        if n is None:
            return "?"
        try:
            return int(n) if float(n).is_integer() else n
        except (TypeError, ValueError):
            return n

    def _load_watchlist(self):
        """Đọc watchlist.json -> dict {series:[...], last_run:"YYYY-MM-DD"}. Không lỗi
        khi file thiếu/hỏng (trả cấu trúc rỗng). Supervisor là NGƯỜI GHI DUY NHẤT."""
        try:
            with open(WATCHLIST_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        if not isinstance(data.get("series"), list):
            data["series"] = []
        data.setdefault("last_run", "")
        return data

    def _save_watchlist_locked(self, data):
        """Ghi watchlist.json (nguyên tử). PHẢI đang giữ self._wl_lock khi gọi."""
        try:
            os.makedirs(META_DIR, exist_ok=True)
            tmp = WATCHLIST_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, WATCHLIST_FILE)
        except OSError as e:
            log(f"! Không ghi được watchlist: {e}")

    def _update_watchlist(self, fn):
        """Đọc-sửa-ghi watchlist trong khoá (đọc+ghi liền nhau để khỏi giẫm lệnh khác).
        `fn(data)` sửa data tại chỗ; giá trị fn trả về được chuyển tiếp cho người gọi."""
        with self._wl_lock:
            data = self._load_watchlist()
            result = fn(data)
            self._save_watchlist_locked(data)
        return result

    def _mark_checked_today(self):
        today = datetime.now().strftime("%Y-%m-%d")

        def _set(d):
            d["last_run"] = today
        self._update_watchlist(_set)

    def _default_notify_cid(self):
        """Chat nhận báo tải cho truyện auto-check thiếu 'added_by': admin đầu, rồi chat đầu."""
        admins = self._admins()
        if admins:
            return admins[0]
        ids = self.cfg.get("chat_ids") or []
        return ids[0] if ids else None

    def handle_watchlist(self, token, cid):
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⛔ Bạn không phải admin."})
            return
        wl = self._load_watchlist()
        series = wl.get("series", [])
        if not series:
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "📭 Watchlist trống.\nThêm bằng: /watch <link truyện>"})
            return
        lines = ["📚 Đang auto-check (mỗi ngày):"]
        for i, s in enumerate(series, 1):
            title = s.get("title") or self._slug(s.get("url", ""))
            mx = s.get("last_max")
            info = f" — mới nhất ch.{self._fmt_num(mx)}" if mx is not None else ""
            flags = ""
            if s.get("provider"):
                flags += f" [{s['provider']}]"
            if s.get("paused"):
                flags += " ⏸"
            lines.append(f"{i}. {title}{info}{flags}")
        hh = int(self.cfg.get("check_hour", 3))
        mm = int(self.cfg.get("check_min", 0))
        lines.append("")
        lines.append(f"⏰ Giờ check: {hh:02d}:{mm:02d}"
                     + (f" · lần cuối {wl.get('last_run')}" if wl.get("last_run") else ""))
        lines.append("/watch <link> thêm · /unwatch <số|link> bỏ · /checknow kiểm ngay")
        tg_api(token, "sendMessage", {"chat_id": cid, "text": "\n".join(lines),
            "disable_web_page_preview": "true"})

    def handle_watch(self, token, cid, raw):
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⛔ Bạn không phải admin."})
            return
        urls = [w for w in raw.split()[1:] if w.startswith("http")]
        if not urls:
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "Gửi: /watch <link truyện> [link2 ...]"})
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        def _add(d):
            have = {s.get("url") for s in d["series"]}
            added = []
            for u in urls:
                if u in have:
                    continue
                d["series"].append({"url": u, "title": self._slug(u), "provider": "",
                                    "added_by": str(cid), "added_at": now,
                                    "last_check": "", "last_max": None, "paused": False})
                have.add(u)
                added.append(u)
            return added
        added = self._update_watchlist(_add)
        dup = len(urls) - len(added)
        parts = []
        if added:
            parts.append(f"➕ Đã thêm {len(added)} truyện vào watchlist.")
        if dup:
            parts.append(f"⏭ {dup} đã có sẵn trong watchlist.")
        if added:
            parts.append("Đang kiểm tra chương mới cho truyện vừa thêm "
                         "(có chương mới sẽ tự tải)...")
        tg_api(token, "sendMessage", {"chat_id": cid, "text": "\n".join(parts),
            "disable_web_page_preview": "true"})
        if added:
            self._run_bg(self.run_check, cid, added, False)

    def handle_unwatch(self, token, cid, raw):
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⛔ Bạn không phải admin."})
            return
        parts = raw.split()
        if len(parts) < 2:
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "Gửi: /unwatch <số thứ tự trong /watchlist | link>"})
            return
        arg = parts[1]

        def _rm(d):
            series = d["series"]
            idx = None
            if arg.isdigit():
                i = int(arg) - 1
                if 0 <= i < len(series):
                    idx = i
            else:
                for i, s in enumerate(series):
                    if s.get("url") == arg or arg in (s.get("url") or ""):
                        idx = i
                        break
            return series.pop(idx) if idx is not None else None
        removed = self._update_watchlist(_rm)
        if removed:
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": f"➖ Đã bỏ khỏi watchlist:\n{removed.get('title') or removed.get('url')}",
                "disable_web_page_preview": "true"})
        else:
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "Không tìm thấy truyện đó (xem /watchlist để lấy số thứ tự)."})

    def handle_checknow(self, token, cid, raw):
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⛔ Bạn không phải admin."})
            return
        parts = raw.split()
        only = [parts[1]] if len(parts) > 1 and parts[1].startswith("http") else None
        tg_api(token, "sendMessage", {"chat_id": cid,
            "text": "🔍 Đang kiểm tra chương mới "
                    + ("(1 truyện)..." if only else "(cả watchlist)...")})
        self._run_bg(self.run_check, cid, only, False)

    def _read_check_result(self):
        try:
            with open(CHECK_RESULT_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return None
        return data

    def run_check(self, cid=None, only_urls=None, scheduled=False):
        """Chạy check_updates.py (subprocess) rồi enqueue truyện có chương mới + báo tóm
        tắt. cid=None -> báo cho mọi người (notify_all, dùng cho lần chạy hẹn giờ);
        có cid -> chỉ trả lời người gọi (/checknow, /watch). scheduled=True -> đánh dấu
        đã chạy hôm nay (để watch_loop khỏi chạy lại)."""
        token = self.cfg.get("bot_token")
        if self._checking:
            if cid is not None and token:
                tg_api(token, "sendMessage", {"chat_id": cid,
                    "text": "⏳ Đang có một lần kiểm tra chạy dở — đợi nó xong đã."})
            return
        self._checking = True
        try:
            if _net_status() != "ok":
                log("! Auto-check: mạng chưa sẵn sàng — hoãn.")
                if cid is not None and token:
                    tg_api(token, "sendMessage", {"chat_id": cid,
                        "text": "⚠️ Mạng chưa sẵn sàng — thử lại sau."})
                return   # scheduled: KHÔNG mark last_run -> watch_loop thử lại phút sau
            wl = self._load_watchlist()
            active = [s for s in wl.get("series", []) if not s.get("paused")]
            if only_urls:
                want = set(only_urls)
                active = [s for s in active if s.get("url") in want]
            if not active:
                if cid is not None and token:
                    tg_api(token, "sendMessage", {"chat_id": cid,
                        "text": ("📭 Watchlist trống — thêm bằng /watch <link>."
                                 if not only_urls else
                                 "Truyện chưa có trong watchlist — dùng /watch để thêm trước.")})
                if scheduled:
                    self._mark_checked_today()
                return
            cmd = [sys.executable, "-u", CHECK_SCRIPT]
            for u in (only_urls or []):
                cmd += ["--only", u]
            log(f"Auto-check: quét {len(active)} truyện ...")
            try:
                subprocess.run(cmd, cwd=BASE_DIR, creationflags=NO_WINDOW,
                               timeout=CHECK_TIMEOUT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            except subprocess.TimeoutExpired:
                log("! Auto-check quá thời gian.")
                if cid is not None and token:
                    tg_api(token, "sendMessage", {"chat_id": cid,
                        "text": "❌ Kiểm tra quá thời gian."})
                return
            payload = self._read_check_result()
            if payload is None:
                log("! Auto-check: không đọc được kết quả.")
                if cid is not None and token:
                    tg_api(token, "sendMessage", {"chat_id": cid,
                        "text": "❌ Không đọc được kết quả kiểm tra."})
                return
            self._apply_check_results(payload, cid)
            if scheduled:
                self._mark_checked_today()
        finally:
            self._checking = False

    def _apply_check_results(self, payload, cid):
        """Cập nhật watchlist theo kết quả check, enqueue truyện cần tải, gửi tóm tắt."""
        results = payload.get("results", [])
        supported = payload.get("supported", [])
        token = self.cfg.get("bot_token")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        wl0 = self._load_watchlist()
        added_by = {s.get("url"): s.get("added_by") for s in wl0.get("series", [])}
        by_url = {r["url"]: r for r in results}
        unsupported = {r["url"] for r in results if r.get("status") == "unsupported"}

        def _upd(d):
            keep = []
            for s in d.get("series", []):
                u = s.get("url")
                if u in unsupported:
                    continue    # site chưa hỗ trợ -> bỏ khỏi watchlist (không check được)
                r = by_url.get(u)
                if r:
                    s["last_check"] = now
                    if r.get("status") == "ok":
                        s["last_max"] = r.get("listed_max")
                        if r.get("title"):
                            s["title"] = r["title"]
                    if r.get("provider"):
                        s["provider"] = r["provider"]
                keep.append(s)
            d["series"] = keep
        self._update_watchlist(_upd)

        # Enqueue: comix (mỗi ngày) + provider thường còn thiếu chương (mới/khoá/dở).
        pairs = []
        for r in results:
            st = r.get("status")
            if st == "comix" or (st == "ok" and r.get("missing_count", 0) > 0):
                job_cid = added_by.get(r["url"]) or cid or self._default_notify_cid()
                pairs.append((r["url"], job_cid))
        added, dup = self._enqueue_jobs(pairs) if pairs else ([], 0)

        text = self._summary_text(results, supported, added, dup)
        if cid is not None:
            if token:
                tg_api(token, "sendMessage", {"chat_id": cid, "text": text,
                    "disable_web_page_preview": "true"})
        else:
            notify_all(self.cfg, text)

    @staticmethod
    def _detail_line(r):
        """1 dòng 'Tên — X/Y (thiếu K: ch. …)' cho site thường (đã có listed_count +
        missing_str). Y=0 (dữ liệu cũ/chưa có) -> chỉ in tên cho khỏi '0/0'."""
        y = r.get("listed_count") or 0
        miss = r.get("missing_count", 0)
        if not y:
            return f"• {r.get('title')}"
        line = f"• {r.get('title')} — {y - miss}/{y} chương"
        if miss:
            ms = r.get("missing_str") or ""
            line += f" (thiếu {miss}" + (f": ch. {ms}" if ms else "") + ")"
        return line

    def _summary_text(self, results, supported, added, dup):
        ok = [r for r in results if r.get("status") == "ok"]
        new = [r for r in ok if r.get("new_since_last") and r.get("missing_count", 0) > 0]
        catching = [r for r in ok
                    if r.get("missing_count", 0) > 0 and not r.get("new_since_last")]
        uptodate = [r for r in ok if r.get("missing_count", 0) == 0]
        comix = [r for r in results if r.get("status") == "comix"]
        errs = [r for r in results if r.get("status") == "error"]
        unsup = [r for r in results if r.get("status") == "unsupported"]

        def _bucket(header, rs, cap=15):
            out = ["", header]
            out += [self._detail_line(r) for r in rs[:cap]]
            if len(rs) > cap:
                out.append(f"   … và {len(rs) - cap} truyện nữa")
            return out

        lines = [f"🔍 Đã kiểm tra {len(results)} truyện."]
        if new:
            lines += _bucket("🆕 Có chương mới:", new)
        if catching:
            lines += _bucket("⤵️ Tải tiếp/bù (chưa đủ từ trước):", catching)
        if comix:
            lines.append("")
            lines.append(f"📘 comix ({len(comix)}) — số chương sẽ báo riêng khi mở Chromium tải:")
            lines += [f"• {r.get('title')}" for r in comix[:15]]
            if len(comix) > 15:
                lines.append(f"   … và {len(comix) - 15} truyện nữa")
        if uptodate:
            lines += _bucket("✅ Không đổi (đã đủ):", uptodate)
        if errs:
            lines.append("")
            lines.append(f"⚠️ Lỗi kiểm tra ({len(errs)}):")
            lines += [f"• {r.get('title')} — {r.get('error') or 'lỗi'}" for r in errs[:10]]
        if unsup:
            lines.append("")
            lines.append("⛔ Đã bỏ (site chưa hỗ trợ): "
                         + ", ".join(r.get("title") or r.get("url") for r in unsup[:8]))
            lines.append("   Đang hỗ trợ: " + ", ".join(supported))
        lines.append("")
        if added:
            lines.append(f"📥 Thêm {len(added)} truyện vào hàng đợi tải"
                         + (f" (bỏ {dup} đã có trong hàng)." if dup else "."))
        elif dup:
            lines.append(f"📥 {dup} truyện cần tải đã có sẵn trong hàng đợi.")
        else:
            lines.append("📥 Không có gì cần tải thêm.")
        return "\n".join(lines)

    def watch_loop(self):
        """Auto-check chương mới 1 lần/ngày vào giờ hẹn (check_hour:check_min, giờ server).
        Bù nếu server tắt lúc đến hẹn: khởi động lại sau giờ đó mà hôm nay chưa chạy ->
        chạy ngay. Mạng chưa sẵn sàng -> run_check tự hoãn (không mark) -> thử lại phút sau."""
        while not self.stop.is_set():
            if self.stop.wait(60):
                return
            try:
                hour = int(self.cfg.get("check_hour", 3))
                minute = int(self.cfg.get("check_min", 0))
            except (TypeError, ValueError):
                hour, minute = 3, 0
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            if self._load_watchlist().get("last_run") == today:
                continue
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now < target:
                continue
            log("Đến giờ auto-check chương mới hằng ngày.")
            try:
                self.run_check(cid=None, only_urls=None, scheduled=True)
            except Exception as e:
                log(f"! Lỗi auto-check: {e}")

    def run(self):
        log("=== Supervisor khởi động ===")
        try:
            os.makedirs(META_DIR, exist_ok=True)
            with open(PID_FILE, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))   # để server-TAT-tudong.bat dừng gọn cả cây
        except OSError:
            pass
        if not self.cfg.get("bot_token"):
            log("! LƯU Ý: notify-config.json chưa có bot_token — reader vẫn chạy, "
                "chỉ là không gửi Telegram được.")
        self.resume_jobs()   # dọn downloader lạc + nạp lại hàng đợi -> tải tiếp sau restart
        threads = [threading.Thread(target=self.run_reader, daemon=True),
                   threading.Thread(target=self.run_tunnel, daemon=True),
                   threading.Thread(target=self.telegram_loop, daemon=True),
                   threading.Thread(target=self.download_loop, daemon=True),
                   threading.Thread(target=self.heartbeat_loop, daemon=True),
                   threading.Thread(target=self.watch_loop, daemon=True)]
        for t in threads:
            t.start()
        try:
            while not self.stop.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            log("=== Supervisor dừng — tắt reader + cloudflared ===")
            self.stop.set()
            self._kill(self.tunnel)
            self._kill(self.reader)
            try:
                os.remove(PID_FILE)
            except OSError:
                pass


if __name__ == "__main__":
    Supervisor().run()
