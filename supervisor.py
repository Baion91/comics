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
import queue
import re
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

TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
HEALTH_EVERY = 60          # giây giữa 2 lần health-check
HEALTH_FAILS = 3           # số lần fail liên tiếp mới coi là tunnel chết
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
    "/tai <link> — tải truyện (nhiều link cách nhau dấu cách)\n"
    "/stop — dừng truyện đang tải + xoá hàng chờ (của bạn)\n"
    "/killnow — chỉ dừng truyện đang tải (của bạn)\n"
    "/clearq — chỉ xoá hàng chờ (của bạn)\n"
    "/stopall — dừng tất cả + xoá sạch hàng chờ (mọi người)\n"
    "/update — cập nhật code + restart reader\n"
    "/adminlist — xem chat đã đăng ký / admin\n"
    "/adminclaim — nhận quyền admin (khi chưa có ai)\n"
    "/adminadd <id> — thêm admin\n"
    "/adminremove <id> — bỏ admin"
)


# --- Reader + cloudflared ---------------------------------------------------

class Supervisor:
    def __init__(self):
        self.cfg = load_config()
        self.stop = threading.Event()
        self.reader = None
        self.tunnel = None
        self.link = None
        self.lock = threading.Lock()
        self._dlq = queue.Queue()   # hàng đợi tải truyện qua bot (/tai)
        self._dlq_lock = threading.Lock()  # gác thao tác gom/lọc hàng đợi (cancel)
        self._dl_proc = None        # tiến trình comic_downloader đang chạy (để kill)
        self._dl_cur = None         # (url, cid) truyện đang tải — để biết 'của ai'
        self._dl_cancelled = False  # cờ: lần kill này là do người dùng huỷ (không phải lỗi)

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
        while not self.stop.is_set():
            log("Bật cloudflared quick-tunnel ...")
            try:
                self.tunnel = subprocess.Popen(
                    [CLOUDFLARED, "tunnel", "--url", self.reader_url()],
                    cwd=BASE_DIR, creationflags=NO_WINDOW,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1)
            except Exception as e:
                log(f"! Không bật được cloudflared: {e}")
                self.stop.wait(5); continue
            found = None
            for line in self.tunnel.stdout:            # đọc output tới khi tiến trình thoát
                m = TUNNEL_RE.search(line)
                if m and m.group(0) != found:
                    found = m.group(0)
                    self.on_new_link(found)
            self.tunnel.wait()
            if self.stop.is_set():
                return
            log("! cloudflared thoát — tạo link mới sau 3s.")
            self.link = None
            self.stop.wait(3)

    def on_new_link(self, url):
        with self.lock:
            self.link = url
        log(f"LINK MỚI: {url}")
        try:
            with open(LINK_FILE, "w", encoding="utf-8") as f:
                f.write(url + "\n")
        except OSError:
            pass
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
            {"command": "tai", "description": "Tải truyện: /tai <link> (admin)"},
            {"command": "stop", "description": "Dừng tải + xoá hàng chờ của bạn (admin)"},
            {"command": "killnow", "description": "Chỉ dừng truyện đang tải của bạn (admin)"},
            {"command": "clearq", "description": "Chỉ xoá hàng chờ của bạn (admin)"},
            {"command": "stopall", "description": "Dừng tất cả + xoá sạch hàng chờ (admin)"},
            {"command": "update", "description": "Cập nhật code (admin)"},
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

    # health-check: tunnel còn sống thật không (khác với 'tiến trình còn chạy')
    def health_loop(self):
        fails = 0
        while not self.stop.wait(HEALTH_EVERY):
            with self.lock:
                url = self.link
            if not url:
                continue
            ok = False
            try:
                req = urllib.request.Request(url, method="GET",
                                             headers={"User-Agent": "toony-health"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    ok = 200 <= r.status < 500   # có phản hồi HTTP = tunnel còn thông
            except Exception:
                ok = False
            if ok:
                fails = 0
            else:
                fails += 1
                log(f"! Health-check fail {fails}/{HEALTH_FAILS} cho {url}")
                if fails >= HEALTH_FAILS:
                    fails = 0
                    log("! Tunnel coi như chết — kill cloudflared để tạo link mới.")
                    self._kill(self.tunnel)   # run_tunnel sẽ tự bật lại + báo link mới

    @staticmethod
    def _kill(proc):
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

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

    # --- Tải truyện qua bot (/tai <url...>) -> hàng đợi, worker chạy nền ----
    def handle_tai(self, token, cid, raw):
        if not self._is_admin(cid):
            tg_api(token, "sendMessage", {"chat_id": cid, "text": "⛔ Bạn không phải admin."})
            return
        urls = [w for w in raw.split()[1:] if w.startswith("http")]
        if not urls:
            tg_api(token, "sendMessage", {"chat_id": cid,
                "text": "Gửi: /tai <link truyện> [link2 ...]"})
            return
        for u in urls:
            self._dlq.put((u, cid))
        tg_api(token, "sendMessage", {"chat_id": cid,
            "text": f"📥 Đã thêm {len(urls)} truyện vào hàng đợi "
                    f"(đang chờ: {self._dlq.qsize()})."})

    def _drain_queue(self, cid=None):
        """Lấy hết hàng đợi ra, GIỮ LẠI các URL không thuộc diện huỷ (bỏ lại vào
        hàng đợi), trả về số URL đã xoá. cid=None -> xoá tất cả; có cid -> chỉ xoá
        URL do chat đó gửi. Có khoá để không giẫm chân worker/lệnh khác."""
        removed, keep = 0, []
        with self._dlq_lock:
            while True:
                try:
                    item = self._dlq.get_nowait()
                except queue.Empty:
                    break
                if cid is None or str(item[1]) == str(cid):
                    removed += 1
                else:
                    keep.append(item)
            for item in keep:
                self._dlq.put(item)
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
            with self.lock:
                cur = self._dl_cur
                proc = self._dl_proc
            if not cur or not proc:
                parts.append("Không có truyện nào đang tải.")
            elif not scope_all and str(cur[1]) != str(cid):
                parts.append("Truyện đang tải không phải của bạn "
                             "(dùng /stopall nếu muốn dừng tất cả).")
            else:
                self._dl_cancelled = True
                self._kill(proc)
                parts.append(f"⏹ Đã dừng truyện đang tải:\n{cur[0]}")
        # 2) Xoá hàng chờ (nếu yêu cầu)
        if clear:
            n = self._drain_queue(cid=None if scope_all else cid)
            scope_txt = "" if scope_all else " của bạn"
            parts.append(f"🗑 Đã xoá {n} truyện trong hàng chờ{scope_txt} "
                         f"(còn lại: {self._dlq.qsize()}).")
        tg_api(token, "sendMessage", {"chat_id": cid,
            "text": "\n".join(parts) if parts else "Không có gì để huỷ.",
            "disable_web_page_preview": "true"})

    def download_loop(self):
        """Worker: lần lượt tải từng truyện trong hàng đợi (1 lượt/lúc), báo bắt
        đầu/xong về đúng người gửi. Tải rất lâu nên chạy nền, KHÔNG timeout.
        Dùng Popen (không phải run) để lệnh /stop, /killnow kill được tiến trình."""
        while not self.stop.is_set():
            try:
                url, cid = self._dlq.get(timeout=1)
            except queue.Empty:
                continue
            token = self.cfg.get("bot_token")
            if token:
                tg_api(token, "sendMessage", {"chat_id": cid,
                    "text": f"⏳ Bắt đầu tải:\n{url}", "disable_web_page_preview": "true"})
            self._dl_cancelled = False
            try:
                proc = subprocess.Popen(
                    [sys.executable, os.path.join(BASE_DIR, "comic_downloader.py"), url],
                    cwd=BASE_DIR, creationflags=NO_WINDOW,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace")
                with self.lock:
                    self._dl_proc, self._dl_cur = proc, (url, cid)
                out, _ = proc.communicate()            # chờ tải xong (không timeout)
                rc = proc.returncode
                if self._dl_cancelled:
                    # Bị huỷ tay: chương đã xong đã đánh dấu .done -> lần sau /tai lại tự
                    # bỏ qua chương cũ, chỉ tải tiếp phần dở. Không coi là lỗi.
                    msg = (f"⏹ Đã huỷ tải:\n{url}\n"
                           "(Tải lại bằng /tai sẽ tự bỏ qua chương đã xong, "
                           "tiếp tục từ chỗ dở.)")
                elif rc == 0:
                    msg = f"✅ Tải xong:\n{url}"
                else:
                    tail = (out or "").strip().splitlines()
                    msg = f"❌ Lỗi tải:\n{url}" + (("\n" + tail[-1]) if tail else "")
            except Exception as e:
                msg = f"❌ Lỗi tải:\n{url}\n{e}"
            finally:
                with self.lock:
                    self._dl_proc, self._dl_cur = None, None
            if token:
                tg_api(token, "sendMessage", {"chat_id": cid, "text": msg,
                    "disable_web_page_preview": "true"})

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
        threads = [threading.Thread(target=self.run_reader, daemon=True),
                   threading.Thread(target=self.run_tunnel, daemon=True),
                   threading.Thread(target=self.health_loop, daemon=True),
                   threading.Thread(target=self.telegram_loop, daemon=True),
                   threading.Thread(target=self.download_loop, daemon=True)]
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
