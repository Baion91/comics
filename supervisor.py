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


# --- Reader + cloudflared ---------------------------------------------------

class Supervisor:
    def __init__(self):
        self.cfg = load_config()
        self.stop = threading.Event()
        self.reader = None
        self.tunnel = None
        self.link = None
        self.lock = threading.Lock()

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
    def telegram_loop(self):
        token = self.cfg.get("bot_token")
        if not token:
            return
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
                offset = upd["update_id"] + 1          # xác nhận đã xử lý
                msg = upd.get("message") or upd.get("channel_post") or {}
                chat = msg.get("chat") or {}
                cid = chat.get("id")
                if cid is None:
                    continue
                is_new = add_chat(self.cfg, cid)       # tự đăng ký người nhận
                text = (msg.get("text") or "").strip().lower()
                link = self.cur_link()
                if text.startswith("/link") or text.startswith("/latest"):
                    tg_api(token, "sendMessage", {"chat_id": cid,
                        "text": f"📖 Link hiện tại:\n{link}" if link
                                else "Chưa có link (server đang khởi động). Thử lại chút nữa.",
                        "disable_web_page_preview": "true"})
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
                   threading.Thread(target=self.telegram_loop, daemon=True)]
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
