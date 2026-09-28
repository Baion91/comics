#!/usr/bin/env python3
"""Tầng TRÌNH DUYỆT THẬT cho site nằm sau Cloudflare — lấy HTML 1 trang khi request
thường bị challenge. Provider gọi LƯỜI (chỉ import/mở khi thật sự bị chặn); ngày thường
không đụng tới. Hiện dùng bởi: qqcomvn (truyenqq.com.vn).

VÌ SAO MODULE RIÊNG (không tái dùng ComixSession): comix gắn cứng profile/route/hook
JSON.parse; refactor module mong manh nhất hệ thống để chia sẻ = rủi ro hồi quy. Ở đây
CHÉP ĐÚNG các công thức comix đã chạy thật trên server (ARCHITECTURE mục comix_site):
  - Chromium của Playwright để trong `.reader-meta/pw-browsers` (PC công ty chặn DLL dưới
    AppData) + playwright==1.55 (requirements) -> DÙNG CHUNG bản cài với comix, nên tầng
    này được comix "tập dượt" gián tiếp mỗi ngày.
  - HEADFUL + 2 cờ chống-lộ-automation (thiếu là site check navigator.webdriver).
  - Watchdog bọc khâu MỞ + PROBE `evaluate('()=>1')` (bắt ca treo about:blank), nổ ->
    kill Chromium của ĐÚNG profile này -> tự dựng lại tối đa MAX_RELAUNCH lần.
  - Dọn Chromium mồ côi của profile TRƯỚC khi mở (orphan ôm profile = gốc treo 14/08).
  - Challenge không tự qua -> Telegram nhờ NGƯỜI tick trên màn hình server rồi chờ.
Mỗi site 1 profile riêng (`<tên>-profile`) -> không đụng comix-profile, không tranh khoá.

KHÔNG BAO GIỜ tự bấm ô "Verify you are human". Challenge không tự qua trong
AUTO_PASS_WAIT -> nhắn người, chờ HUMAN_WAIT (in log mỗi HEARTBEAT giây để stall-watchdog
20' của supervisor không giết oan) -> quá giờ ném core.Challenged = dừng phiên SẠCH (ảnh +
.done giữ nguyên, lần chạy sau tải tiếp đúng chỗ).

Chỉ gọi từ MAIN THREAD (Playwright sync API) — core.run gọi provider ở main thread."""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

import comics_core as core

# PHẢI set TRƯỚC khi import playwright (import lười trong _launch). Cùng giá trị với
# comix_site + cap-nhat.bat -> dùng chung 1 bản Chromium đã cài.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(core.META_DIR / "pw-browsers"))

NOTIFY_CONFIG = core.META_DIR / "notify-config.json"
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

LAUNCH_WATCHDOG = 90       # giây tối đa cho khâu mở + khởi tạo Chromium (như comix)
LAUNCH_KILL_GRACE = 8      # ân hạn sau khi kill cho lệnh Playwright kẹt bật lỗi
MAX_RELAUNCH = 3           # số lần tự dựng lại Chromium trong 1 đợt sự cố
RELAUNCH_BACKOFF = 5       # giây nghỉ trước khi mở lại
NAV_TIMEOUT_MS = 45_000    # timeout 1 lần điều hướng
NAV_ATTEMPTS = 4           # số lần thử 1 URL (gồm cả lượt goto lại sau khi qua challenge)
AUTO_PASS_WAIT = 20        # giây chờ challenge KHÔNG tương tác tự qua (JS/managed) — im lặng
HUMAN_WAIT = 15 * 60       # giây chờ NGƯỜI tick (< 20' stall-watchdog của supervisor)
HEARTBEAT = 60             # giây giữa 2 dòng log "vẫn đang chờ" (giữ log tăng)
NOTIFY_GAP = 10 * 60       # tối thiểu giây giữa 2 tin "cần tick" (chống spam)

_CHALLENGE_TITLES = ("just a moment", "attention required")
_BLOCK_TYPES = {"image", "media", "font"}   # trên host site: không cần để lấy HTML


class BrowserGone(core.Blocked):
    """Không mở/giữ được Chromium (hỏng liên tục quá MAX_RELAUNCH). Là con của Blocked
    -> core.run dừng phiên sạch (exit 2) thay vì traceback."""


def notify_telegram(text):
    """Báo admin qua Telegram (admin_chat_ids, fallback chat_ids) — chép từ comix_site.
    Không có config/token (vd máy dev) -> im lặng (console đã in)."""
    try:
        cfg = json.loads(NOTIFY_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    token = cfg.get("bot_token")
    ids = cfg.get("admin_chat_ids") or cfg.get("chat_ids") or []
    if not token or not ids:
        return
    for cid in ids:
        try:
            data = urllib.parse.urlencode(
                {"chat_id": cid, "text": text, "disable_web_page_preview": "true"}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage",
                                   data=data, timeout=15).read()
        except Exception:
            pass


def kill_profile_chrome(profile_dir):
    """Giết chrome.exe đang dùng ĐÚNG profile này + xoá file khoá singleton còn sót.
    Match theo tên thư mục profile (vd 'qqvn-profile') nên KHÔNG đụng Chrome thường của
    user lẫn Chromium comix. Best-effort, không raise."""
    name = profile_dir.name
    if os.name == "nt":
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                 f"Where-Object {{ $_.CommandLine -match '{name}' }} | "
                 "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
                 "-ErrorAction SilentlyContinue }"],
                creationflags=_NO_WINDOW, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    for lock in ("SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile"):
        try:
            (profile_dir / lock).unlink()
        except OSError:
            pass


class _Watchdog:
    """Bọc khâu mở + khởi tạo Chromium (vùng KHÔNG có timeout nội bộ đáng tin — sự cố
    17/08 của comix). Quá hạn -> gọi on_fire (kill Chromium của profile) để lệnh
    Playwright đang kẹt ở main thread bật lỗi -> _launch ném BrowserGone -> tự dựng lại.
    Vẫn kẹt sau ân hạn -> os._exit(2) (chốt cứng: supervisor báo lỗi + chạy job kế)."""

    def __init__(self, timeout, label, on_fire):
        self._timeout, self._label, self._on_fire = timeout, label, on_fire
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._done.set()
        return False

    def _run(self):
        if self._done.wait(self._timeout):
            return
        print(f"\n  !! Watchdog: {self._label} quá {self._timeout}s — nghi Chromium treo, "
              "kill để tự dựng lại...", file=sys.stderr, flush=True)
        self._on_fire()
        if self._done.wait(LAUNCH_KILL_GRACE):
            return
        print(f"  !! Watchdog: vẫn kẹt sau {LAUNCH_KILL_GRACE}s — thoát cứng.",
              file=sys.stderr, flush=True)
        os._exit(2)


class CFBrowser:
    """Chromium headful, profile bền riêng (giữ cookie cf_clearance qua các lần chạy).

        b = CFBrowser("qqvn-profile", "truyenqq.com.vn", "TruyenQQ.com.vn")
        b.open(); html = b.get_html(url); b.close()

    get_html trả HTML THÔ của response (y như request thường -> provider dùng CHUNG
    parser cho 2 tầng), None nếu trang 404/410; ném core.Challenged nếu không qua được
    Cloudflare, BrowserGone nếu Chromium hỏng liên tục."""

    def __init__(self, profile, host, label):
        self.profile_dir = core.META_DIR / profile
        self.host = host.lower()
        self.label = label
        self._pw = self.ctx = self.page = None
        self._relaunch_streak = 0
        self._last_notify = None      # monotonic lần gửi "cần tick" gần nhất

    # -- vòng đời -----------------------------------------------------------------

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def open(self):
        """Mở lần đầu: dọn orphan của profile rồi mở; hụt/treo -> thử lại <= MAX_RELAUNCH."""
        print(f"  (Mở Chromium [{self.profile_dir.name}] — cửa sổ trình duyệt sẽ hiện; "
              "đừng đóng nó trong lúc tải)", flush=True)
        self._kill()
        attempt = 0
        while True:
            try:
                self._launch()
                return
            except BrowserGone as e:
                attempt += 1
                if attempt > MAX_RELAUNCH:
                    raise BrowserGone(
                        f"Không mở nổi Chromium sau {MAX_RELAUNCH} lần thử: {e}") from e
                print(f"  ! Mở Chromium hụt/treo — dọn rồi thử lại (lần {attempt}/"
                      f"{MAX_RELAUNCH})...", file=sys.stderr, flush=True)
                self._close_pw()
                self._kill()
                time.sleep(RELAUNCH_BACKOFF)

    def close(self):
        """LUÔN gọi (provider.close trong finally): Chromium mồ côi ôm profile = treo lần sau."""
        self._close_pw()

    def _kill(self):
        kill_profile_chrome(self.profile_dir)

    def _launch(self):
        try:
            with _Watchdog(LAUNCH_WATCHDOG, "mở + khởi tạo Chromium", self._kill):
                from playwright.sync_api import sync_playwright
                self._pw = sync_playwright().start()
                self.profile_dir.mkdir(parents=True, exist_ok=True)
                self.ctx = self._pw.chromium.launch_persistent_context(
                    str(self.profile_dir), headless=False,
                    viewport={"width": 1280, "height": 900},
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"])
                self.ctx.route("**/*", self._route)
                self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
                self.page.set_default_timeout(NAV_TIMEOUT_MS)
                self.ctx.on("page", self._on_popup)
                self.page.evaluate("() => 1")      # PROBE: renderer phải trả lời
        except Exception as e:
            self._close_pw()
            raise BrowserGone(f"Mở/khởi tạo Chromium thất bại: {e}") from e

    def _close_pw(self):
        for obj, fn in ((self.ctx, "close"), (self._pw, "stop")):
            if obj is not None:
                try:
                    getattr(obj, fn)()
                except Exception:
                    pass
        self.ctx = self.page = self._pw = None

    def alive(self):
        """Chỉ đọc trạng thái cục bộ (không IPC) -> không báo nhầm lúc trang đang tải."""
        try:
            if self.page is None or self.page.is_closed():
                return False
            br = self.ctx.browser if self.ctx else None
            return br is None or br.is_connected()
        except Exception:
            return False

    def _relaunch(self, why):
        """Dựng lại Chromium tại chỗ (cùng profile -> giữ cookie). Ngân sách MAX_RELAUNCH
        cho mỗi ĐỢT sự cố (reset khi lấy được 1 trang); quá -> BrowserGone = dừng phiên."""
        while True:
            self._relaunch_streak += 1
            if self._relaunch_streak > MAX_RELAUNCH:
                raise BrowserGone(f"Chromium hỏng liên tục ({why}) — đã tự dựng lại "
                                  f"{MAX_RELAUNCH} lần vẫn hỏng")
            print(f"\n  ! Chromium {why} — tự dựng lại (lần {self._relaunch_streak}/"
                  f"{MAX_RELAUNCH})...", file=sys.stderr, flush=True)
            self._close_pw()
            self._kill()
            time.sleep(RELAUNCH_BACKOFF)
            try:
                self._launch()
                return
            except BrowserGone:
                continue

    # -- lọc request: chỉ trang của site + challenge của Cloudflare -------------------

    def _route(self, route):
        try:
            req = route.request
            host = (urllib.parse.urlparse(req.url).hostname or "").lower()
            if host == self.host or host.endswith("." + self.host):
                # Trang + script/xhr của site (gồm /cdn-cgi/challenge-platform của CF);
                # ảnh/font/media bỏ — chỉ cần HTML, ảnh tải riêng bằng HTTP.
                ok = req.resource_type not in _BLOCK_TYPES
            else:
                # Ô tick Turnstile nằm trong iframe challenges.cloudflare.com -> mở hết.
                ok = host == "cloudflare.com" or host.endswith(".cloudflare.com")
        except Exception:
            ok = False
        try:
            route.continue_() if ok else route.abort()
        except Exception:
            pass

    def _on_popup(self, page):
        if page is not self.page:
            try:
                page.close()
            except Exception:
                pass

    # -- Cloudflare -----------------------------------------------------------------

    def _challenge_present(self):
        """True khi trang ĐANG là challenge. Đọc title lỗi (trang đang tự reload giữa
        chừng) -> coi như VẪN challenge: chỉ công nhận 'đã qua' khi chắc chắn."""
        try:
            t = (self.page.title() or "").lower()
        except Exception:
            return True
        return any(m in t for m in _CHALLENGE_TITLES)

    @staticmethod
    def _resp_challenged(resp):
        try:
            return (resp.headers.get("cf-mitigated") or "").lower() == "challenge"
        except Exception:
            return False

    def _notify(self, text, force=False):
        now = time.monotonic()
        if force or self._last_notify is None or now - self._last_notify >= NOTIFY_GAP:
            self._last_notify = now
            notify_telegram(text)

    def _wait_pass(self, url, allow_human=True):
        """Chờ challenge qua. Pha 1 (im lặng): challenge JS/managed thường tự qua với
        Chromium thật. Pha 2 (chỉ khi allow_human): nhắn người tick, chờ HUMAN_WAIT.
        Không qua -> core.Challenged (dừng phiên sạch)."""
        end = time.monotonic() + AUTO_PASS_WAIT
        while time.monotonic() < end:
            time.sleep(1)
            if not self.alive():
                raise BrowserGone("Chromium đóng trong lúc chờ Cloudflare")
            if not self._challenge_present():
                print("  -> Cloudflare tự qua (không cần tick).", flush=True)
                return
        if not allow_human:
            # Vừa có người tick mà CF lại chặn ngay = nhiều khả năng CF chặn cả trình duyệt
            # tự động -> chờ thêm vô ích (và giữ hàng đợi cả giờ). Dừng sạch, báo rõ.
            self._notify(f"⛔ {self.label}: Cloudflare vẫn chặn ngay sau khi xác minh — "
                         "phiên tải dừng. Thử /tai lại sau vài giờ.", force=True)
            raise core.Challenged(f"Cloudflare chặn lại ngay sau khi xác minh ({url})")
        mins = HUMAN_WAIT // 60
        print(f"\n  ! Cloudflare đòi xác minh NGƯỜI tại {url}\n"
              f"    -> Mở màn hình máy server, tick ô \"Verify you are human\" trên cửa "
              f"sổ Chromium đang hiện. Chờ tối đa {mins} phút...", flush=True)
        self._notify(
            f"⚠️ Tải {self.label} đang bị Cloudflare chặn.\n\n"
            "CẦN LÀM: mở màn hình máy server → cửa sổ Chromium đang hiện → tick ô "
            "\"Verify you are human\" (Xác minh bạn là người).\n\n"
            f"Tool chờ tối đa {mins} phút rồi tự tải tiếp; quá giờ sẽ dừng phiên (ảnh "
            "đã tải giữ nguyên, lần sau tải tiếp đúng chỗ).")
        start = last_beat = time.monotonic()
        reminded = False
        while (elapsed := time.monotonic() - start) < HUMAN_WAIT:
            time.sleep(3)
            if not self.alive():
                raise BrowserGone("Chromium đóng trong lúc chờ xác minh")
            if not self._challenge_present():
                print("  -> Đã qua Cloudflare, tải tiếp.", flush=True)
                self._notify(f"✅ {self.label}: đã qua Cloudflare, đang tải tiếp.", force=True)
                return
            now = time.monotonic()
            if now - last_beat >= HEARTBEAT:
                last_beat = now
                print(f"  … vẫn chờ xác minh Cloudflare ({int(elapsed // 60)}/{mins} phút)",
                      flush=True)
            if not reminded and elapsed >= HUMAN_WAIT / 2:
                reminded = True
                self._notify(f"⏳ Nhắc lại: {self.label} vẫn chờ tick Cloudflare trên máy "
                             f"server (còn ~{mins - int(elapsed // 60)} phút).", force=True)
        self._notify(f"⛔ {self.label}: quá {mins} phút chưa qua Cloudflare — phiên tải "
                     "dừng. Xác minh xong hãy /tai lại (tải tiếp đúng chỗ).", force=True)
        raise core.Challenged(f"Cloudflare không được xác minh trong {mins} phút ({url})")

    # -- lấy HTML ---------------------------------------------------------------------

    def get_html(self, url):
        """HTML thô của `url` (str), None nếu 404/410. Qua challenge thì goto LẠI để lấy
        response sạch (sau khi tick, CF tự reload nhưng response gốc là trang challenge)."""
        last_err = None
        n_challenge = 0                       # chỉ chờ NGƯỜI tick 1 lần cho mỗi URL
        for attempt in range(NAV_ATTEMPTS):
            if not self.alive():
                self._relaunch("đã đóng")
            core.gate.wait_turn()             # chung van điều tốc với mọi request khác
            try:
                resp = self.page.goto(url, wait_until="domcontentloaded")
            except Exception as e:
                last_err = e
                if not self.alive():
                    continue                  # đầu vòng sau tự dựng lại
                time.sleep(3 * (attempt + 1))
                continue
            try:
                if self._resp_challenged(resp) or self._challenge_present():
                    self._wait_pass(url, allow_human=(n_challenge == 0))
                    n_challenge += 1
                    continue                  # goto lại -> response thật (đã có cookie)
            except BrowserGone:
                self._relaunch("đóng giữa lúc chờ Cloudflare")
                continue
            if resp is None:
                last_err = RuntimeError("không có response")
                continue
            if resp.status in (404, 410):
                return None
            if resp.status >= 400:
                last_err = RuntimeError(f"HTTP {resp.status}")
                time.sleep(3 * (attempt + 1))
                continue
            try:
                html = resp.text()
            except Exception as e:
                last_err = e
                continue
            self._relaunch_streak = 0         # đợt sự cố (nếu có) đã qua
            return html
        if self.alive() and self._challenge_present():
            raise core.Challenged(f"vẫn bị Cloudflare chặn sau {NAV_ATTEMPTS} lần thử ({url})")
        print(f"  ! Trình duyệt không lấy được {url}: {last_err}", file=sys.stderr)
        return None
