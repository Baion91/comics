#!/usr/bin/env python3
"""comix.to (Comick) — LOOP TẢI RIÊNG, không đi qua core.run().

Vì sao không theo hợp đồng provider thường (providers.py):
- API trả response MÃ HÓA {"e": "..."} + token ký per-request (`_=`, sinh bởi
  secure-*.js đổi theo build) -> KHÔNG craft request bằng requests được.
- Cách duy nhất đã kiểm chứng: mở trình duyệt thật (Playwright HEADFUL), để chính
  JS của site gọi API + giải mã, mình hook JSON.parse trong page bắt object
  {status, result} đã giải mã. Browser CHỈ lo metadata (danh sách chương + URL ảnh);
  tải ảnh vẫn bằng requests qua PoliteGate của comics_core (CDN *.wowpicN.store
  chỉ đòi Referer https://comix.to/).
- 1 chương có NHIỀU bản upload (official + các nhóm scan) -> phải CHỌN bản, và khi
  chạy lại có thể THAY bản scan cũ bằng bản Official mới xuất hiện. Logic này không
  có chỗ trong run() generic nên viết loop riêng, 5 site cũ không bị đụng.

Luật chọn bản per số chương (user chốt 09/08/2026):
  1. Lọc language == "en". Có bản isOfficial=true (tick "v") -> lấy official
     (nhiều official -> id lớn nhất).
  2. Không có official -> lấy bản scan có `id` (chapterId) LỚN NHẤT = upload mới
     nhất (id tăng đơn điệu theo thời gian; user bỏ yêu cầu tiebreak theo nhóm).
  3. Bản được chọn mà 0 trang (khóa/hỏng) -> thử ứng viên kế tiếp.

Upgrade -> official (sidecar `.source.json` trong folder chương):
  - Trên đĩa là official -> BỎ QUA vĩnh viễn (không tải lại).
  - Trên đĩa CHƯA phải official mà comix nay có bản "v" -> tải official vào
    downloads/.comix-tmp/ (reader bỏ qua folder đầu-dấu-chấm), ĐỦ ảnh mới tráo folder;
    tên folder GIỮ "Chapter N" (không gắn title) để bookmark/tiến trình không mất.
    "Chưa phải official" GỒM cả chương tải từ SITE KHÁC (Raven, Asura...) — folder có
    ảnh + .done nhưng KHÔNG có sidecar comix; trước đây bị coi là "đã xong" và skip
    (sự cố Dungeon Reset: 266 chương Raven bị bỏ qua). Nay khớp theo SỐ chương.
  - Chưa có "v" -> giữ nguyên, KHÔNG thay scan bằng scan (kể cả bản comix mới hơn).
  - Đang tải dở (chưa .done) -> tiếp đúng bản trong sidecar, tránh trộn ảnh 2 nhóm.

File DẤU cấp truyện (Cách 1): cuối mỗi lần chạy, ghi `_COMIX_official_{off}-{total}.txt`
ở gốc folder truyện (nhìn thấy trong Explorer, reader/check bỏ qua) để phân biệt folder
comix với folder scan tải từ site khác -> user tự tay xoá folder scan trùng.

URL ảnh KHÔNG có đuôi file (https://80pd.wowpic1.store/i5/<hash>) -> tải về đặt
tạm .webp rồi sniff magic bytes, sai thì đổi đuôi (Comix thực tế trả webp).

Cloudflare: chạy headful + profile Chromium cố định (.reader-meta/comix-profile)
giữ cookie cf_clearance. Nếu dính challenge tương tác -> gửi Telegram (đọc
.reader-meta/notify-config.json, ưu tiên admin_chat_ids) nhắc người mở màn hình
server tick "Verify you are human", chờ tối đa 5 phút rồi tự chạy tiếp.

Chặn QUẢNG CÁO + bền với chập chờn: browser CHỈ cho request tới comix.to +
cloudflare.com (route abort mọi domain khác) và tự đóng popup — diệt gốc cú
quảng cáo đẩy trang rời comix giữa lúc load (nguyên nhân 'chưa bắt được ảnh
chương'). Ngoài ra `_pump` trả None (không raise), `fetch_pages`/list tự MỞ LẠI
vài lần; một chương lấy hụt -> rơi xuống bản khác, hết bản -> ghi 'để sau' rồi
ĐI TIẾP (KHÔNG để 1 chương làm chết cả bộ), lần chạy sau tự bù.

Playwright là DEP TÙY CHỌN — chỉ import khi tải comix; thiếu thì in hướng dẫn cài:
    pip install playwright && python -m playwright install chromium
"""

import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

import comics_core as core

# Chromium của Playwright để TRONG PROJECT (.reader-meta/pw-browsers), KHÔNG dùng
# mặc định %LOCALAPPDATA%\ms-playwright: PC công ty chặn load DLL/manifest dưới
# AppData -> chrome.exe chết ngay từ CreateProcess với lỗi "side-by-side
# configuration is incorrect" (đã tét: cùng binary, chạy từ ổ project thì OK).
# Phải set TRƯỚC khi import playwright; cap-nhat.bat cũng set biến này khi
# `playwright install chromium` để tải browser vào đúng chỗ.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",
                      str(core.META_DIR / "pw-browsers"))

BASE = "https://comix.to"
REFERER = "https://comix.to/"
PROFILE_DIR = core.META_DIR / "comix-profile"   # giữ cf_clearance qua các lần chạy
NOTIFY_CONFIG = core.META_DIR / "notify-config.json"
TMP_DIRNAME = ".comix-tmp"    # dưới thư mục --out; đầu-dấu-chấm -> reader/check bỏ qua
SIDECAR = ".source.json"      # bản nào đang nằm trong folder chương (id/nhóm/official)
CHALLENGE_WAIT = 300          # giây chờ người xác minh Cloudflare trước khi bỏ cuộc
MAX_RELAUNCH = 3              # số lần TỰ dựng lại Chromium cho MỖI đợt sự cố (reset khi tải được thêm)
RELAUNCH_BACKOFF = 5.0        # giây nghỉ trước khi mở Chromium mới
FAIL_STREAK_LIMIT = 6         # số chương LIÊN TIẾP không lấy được ảnh (browser còn sống) -> dừng phiên
LAUNCH_WATCHDOG = 90          # giây tối đa cho CẢ khâu mở+setup Chromium; quá = nghi treo -> kill
LAUNCH_KILL_GRACE = 8         # giây chờ main-thread bật lỗi sau khi watchdog kill Chromium, trước khi os._exit
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0   # đừng bật cửa sổ console con (powershell dọn)

# JSON.parse hook — add_init_script nên chạy lại MỖI navigation (window.__cap tự reset,
# không phình RAM). Chỉ giữ object dạng {status, result} (API comix), bỏ qua thứ khác.
HOOK_JS = """
(() => {
  const orig = JSON.parse.bind(JSON);
  window.__cap = [];
  JSON.parse = function (s, r) {
    const o = orig(s, r);
    try {
      if (o && typeof o === 'object' && o.status !== undefined && o.result)
        window.__cap.push(o);
    } catch (e) {}
    return o;
  };
})();
"""


class BrowserGone(Exception):
    """Cửa sổ Chromium bị đóng/chết giữa chừng. run() bắt để TỰ DỰNG LẠI browser rồi
    tải tiếp (relaunch); quá MAX_RELAUNCH lần trong một đợt -> ném ra ngoài = fatal
    (thoát != 0 -> supervisor báo '❌ Lỗi tải' thay vì lặng lẽ '✅ Tải xong')."""


class FetchStalled(Exception):
    """Nhiều chương LIÊN TIẾP không lấy được ảnh dù browser CÒN SỐNG (nghi bị chặn IP
    mềm / site đổi API). Dừng phiên + báo lỗi thật, thay vì ghi 'để sau' cả bộ rồi
    thoát 0 khiến người dùng tưởng đã tải xong."""


# --- Telegram (đọc chung notify-config.json với supervisor; lỗi thì im lặng) -----

def _notify_telegram(text):
    """Báo admin qua Telegram (ưu tiên admin_chat_ids, fallback chat_ids). Dùng khi
    cần NGƯỜI can thiệp trên màn hình server (Cloudflare challenge). Không có
    config/token (vd máy dev) -> chỉ in console, không lỗi."""
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
                {"chat_id": cid, "text": text,
                 "disable_web_page_preview": "true"}).encode()
            urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data, timeout=15).read()
        except Exception:
            pass


# --- Dọn Chromium lạc + khoá profile (chống treo do "chuyển cho instance cũ") ------

def _kill_profile_chrome():
    """Giết mọi chrome.exe đang dùng `comix-profile` + xoá các file khoá singleton cũ.

    VÌ SAO: Chromium dùng profile BỀN (persistent). Nếu còn 1 Chromium mồ côi (từ lần
    trước treo/bị kill) đang ôm profile này, thì `launch_persistent_context` mở chrome.exe
    MỚI sẽ phát hiện "đã có instance" -> chuyển URL cho con cũ rồi TỰ THOÁT -> Playwright
    vừa mở con đó mất kết nối -> TREO vô hạn ở about:blank (đúng sự cố 14/08). Dọn sạch
    TRƯỚC khi mở là diệt gốc. An toàn: hàng đợi comix chỉ 1 worker tuần tự (không có 2 job
    comix song song), và match theo 'comix-profile' nên KHÔNG đụng Chrome thường của user.

    Xoá cả file khoá (`SingletonLock/Socket/Cookie`, `lockfile`): chrome bị Force-kill để
    lại các file này trên đĩa -> lần mở sau đôi khi cũng kẹt. Best-effort, không raise."""
    if os.name == "nt":
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                 "Where-Object { $_.CommandLine -match 'comix-profile' } | "
                 "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
                 "-ErrorAction SilentlyContinue }"],
                creationflags=_NO_WINDOW, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile"):
        try:
            (PROFILE_DIR / name).unlink()
        except OSError:
            pass


class _StartupWatchdog:
    """Lưới an toàn: nếu khâu MỞ + KHỞI TẠO Chromium quá `LAUNCH_WATCHDOG` giây thì gần
    như chắc chắn đang TREO (browser bật lên nhưng Playwright không lái được — vd cửa sổ
    kẹt ở about:blank, sự cố 14/08 + 17/08). Watchdog kill Chromium: đường ống CDP đứt sẽ
    khiến lệnh Playwright đang kẹt ở MAIN THREAD bật lỗi -> `_launch` bắt được -> ném
    BrowserGone -> `_open_resilient`/`relaunch` tự dựng lại TRONG PHIÊN (Cách B). Kill này
    còn dọn luôn orphan/lock — nghi phạm gốc — nên lần dựng lại thường thành công.

    Nếu sau ÂN HẠN `LAUNCH_KILL_GRACE` giây mà main-thread VẪN kẹt (lệnh không thèm bật
    lỗi cả khi chrome đã chết) -> `os._exit` HARD làm chốt chặn cuối: downloader thoát != 0
    -> supervisor báo lỗi + chạy job kế, thay vì treo câm.

    BỌC cả khâu mở lẫn setup (add_init_script/route/pages/probe) — vùng này KHÔNG có
    timeout nội bộ đáng tin, đúng chỗ 17/08 treo. KHÔNG bọc các bước sau đó (goto có
    timeout 45s; chờ Cloudflare có người tick tối đa 5') để khỏi giết nhầm lúc chờ xác minh."""

    def __init__(self, timeout, label, grace=LAUNCH_KILL_GRACE):
        self._timeout = timeout
        self._grace = grace
        self._label = label
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
            return   # xong đúng hạn -> yên
        print(f"\n  !! Watchdog: {self._label} quá {self._timeout}s — nghi Chromium treo. "
              "Kill Chromium để phiên tự dựng lại...", file=sys.stderr, flush=True)
        _kill_profile_chrome()
        # Ân hạn cho main-thread bật lỗi + thoát khối watchdog -> phiên tự relaunch (khỏi os._exit).
        if self._done.wait(self._grace):
            return
        print(f"  !! Watchdog: vẫn kẹt sau {self._grace}s dù đã kill Chromium — thoát cứng "
              "(supervisor sẽ báo lỗi + chạy job kế).", file=sys.stderr, flush=True)
        os._exit(2)


# --- Phiên trình duyệt -----------------------------------------------------------

class ComixSession:
    """Playwright headful + hook JSON.parse. Chỉ dùng cho metadata (list + URL ảnh)."""

    def __init__(self):
        self._pw = None
        self.ctx = None
        self.page = None
        self._notified_challenge = False
        self._relaunch_streak = 0     # số lần dựng lại Chromium trong ĐỢT sự cố hiện tại

    def __enter__(self):
        self._open_resilient()
        return self

    def _open_resilient(self):
        """Mở phiên LẦN ĐẦU; nếu wedge (BrowserGone) -> dọn orphan/lock rồi thử lại tối đa
        MAX_RELAUNCH lần (Cách B). Nhờ vậy ca 'about:blank treo lúc mở' (17/08) tự khỏi
        trong phiên thay vì hỏng cả lượt tải. Quá ngân sách -> ném ra ngoài = fatal."""
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
                print(f"  ! Mở Chromium hụt/treo — dọn rồi thử lại "
                      f"(lần {attempt}/{MAX_RELAUNCH})...", file=sys.stderr, flush=True)
                self._close_playwright()
                _kill_profile_chrome()          # diệt orphan/lock trước khi thử lại
                time.sleep(RELAUNCH_BACKOFF)

    def _launch(self):
        """Mở Chromium + gắn hook/route/popup + PROBE. Tách riêng để relaunch() gọi lại
        được khi cửa sổ bị đóng giữa chừng (cùng profile bền -> khỏi verify Cloudflare lại).

        BỌC _StartupWatchdog QUANH CẢ mở lẫn setup: các bước sau launch (add_init_script/
        route/pages/probe) KHÔNG có timeout nội bộ đáng tin — đúng vùng treo câm 17/08.
        PROBE `evaluate('() => 1')` xác nhận renderer thật sự trả lời trước khi giao việc:
        trang tốt trả 1 tức thì, trang wedge (about:blank kẹt) làm probe treo -> watchdog nổ.
        Bất kỳ lỗi nào (kể cả khi watchdog kill Chromium giữa chừng) -> ném BrowserGone để
        _open_resilient/_resilient tự dựng lại."""
        try:
            with _StartupWatchdog(LAUNCH_WATCHDOG, "mở + khởi tạo Chromium"):
                from playwright.sync_api import sync_playwright
                self._pw = sync_playwright().start()
                PROFILE_DIR.mkdir(parents=True, exist_ok=True)
                # 2 cờ chống-lộ-automation là BẮT BUỘC: site check navigator.webdriver,
                # true là JS site KHÔNG boot (SSR có title nhưng body rỗng, không gọi API).
                self.ctx = self._pw.chromium.launch_persistent_context(
                    str(PROFILE_DIR), headless=False, viewport={"width": 1280, "height": 900},
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"])
                self.ctx.add_init_script(HOOK_JS)
                # Chặn MỌI request ra domain lạ (quảng cáo). Trình duyệt CHỈ cần comix.to
                # (JSON metadata) + cloudflare.com (challenge); ảnh do requests tải riêng,
                # không cần render trong browser. Đây là gốc rễ sự cố "chưa bắt được ảnh
                # chương": script quảng cáo (vd masterlythehague.com) đẩy trang rời comix.to
                # giữa lúc load -> hook JSON.parse không thấy payload -> tưởng lỗi. Chặn hẳn là hết.
                self.ctx.route("**/*", self._route_filter)
                self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
                self.page.set_default_timeout(45_000)
                # Popup quảng cáo (window.open/target=_blank) -> đóng ngay, giữ đúng 1 trang.
                self.ctx.on("page", self._on_popup)
                # PROBE: renderer phải trả lời được — bắt đúng ca wedge (about:blank treo).
                self.page.evaluate("() => 1")
        except Exception as e:
            # Lỗi mở thật, hoặc watchdog vừa kill Chromium làm lệnh Playwright kẹt bật lỗi.
            self._close_playwright()
            raise BrowserGone(f"Mở/khởi tạo Chromium thất bại: {e}") from e

    def alive(self) -> bool:
        """Browser còn sống không? Để phân biệt 'Chromium đã đóng' (fatal, phải dựng
        lại) với 'một lần điều hướng hụt' (tạm thời, cứ retry). Chỉ đọc trạng thái cục
        bộ (page.is_closed / browser.is_connected) — không IPC nên không false-positive
        lúc trang đang navigate."""
        try:
            if self.page is None or self.page.is_closed():
                return False
            br = self.ctx.browser if self.ctx else None
            if br is not None and not br.is_connected():
                return False
            return True
        except Exception:
            return False

    def mark_progress(self):
        """Vừa tải được 1 chương -> reset bộ đếm dựng-lại (mỗi ĐỢT sự cố có ngân sách
        MAX_RELAUNCH riêng, để browser chập chờn cả phiên dài không cộng dồn thành fatal)."""
        self._relaunch_streak = 0

    def relaunch(self):
        """Dựng lại Chromium TẠI CHỖ sau khi cửa sổ bị đóng/chết (cùng profile bền ->
        giữ cf_clearance; .done/sidecar giúp bỏ qua chương đã xong, y như restart tay).
        Quá MAX_RELAUNCH lần trong một đợt -> ném BrowserGone = fatal (thoát != 0)."""
        self._relaunch_streak += 1
        if self._relaunch_streak > MAX_RELAUNCH:
            raise BrowserGone(
                f"Chromium đóng liên tục — đã tự dựng lại {MAX_RELAUNCH} lần vẫn hỏng")
        print(f"\n  ! Cửa sổ Chromium đã đóng — tự dựng lại "
              f"(lần {self._relaunch_streak}/{MAX_RELAUNCH}), tải tiếp...",
              file=sys.stderr, flush=True)
        _notify_telegram(
            "🔄 Comix: cửa sổ Chromium bị đóng giữa chừng — tool TỰ mở lại "
            f"(lần {self._relaunch_streak}/{MAX_RELAUNCH}) và tải tiếp. Không cần làm gì.")
        self._close_playwright()
        _kill_profile_chrome()          # diệt orphan/lock trước khi mở lại (nghi phạm gốc wedge)
        time.sleep(RELAUNCH_BACKOFF)
        try:
            self._launch()
        except Exception as e:
            raise BrowserGone(f"Không dựng lại được Chromium: {e}") from e

    @staticmethod
    def _route_filter(route):
        try:
            host = (urllib.parse.urlparse(route.request.url).hostname or "").lower()
        except Exception:
            host = ""
        ok = (host == "comix.to" or host.endswith(".comix.to")
              or host.endswith(".cloudflare.com") or host == "cloudflare.com")
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

    def _close_playwright(self):
        for obj in (self.ctx, self._pw):
            try:
                if obj is self.ctx and obj:
                    obj.close()
                elif obj is self._pw and obj:
                    obj.stop()
            except Exception:
                pass
        self.ctx = self.page = self._pw = None   # để alive()=False + _launch gán lại sạch

    def __exit__(self, *exc):
        # LUÔN đóng browser kẻo Chromium mồ côi chiếm profile (supervisor cũng có
        # lưới dọn lúc boot, nhưng đấy là phòng hờ crash, không phải đường chính).
        self._close_playwright()
        return False

    # -- Cloudflare -------------------------------------------------------------

    def _challenge_present(self):
        try:
            t = (self.page.title() or "").lower()
        except Exception:
            return False
        return "just a moment" in t or "attention required" in t

    def _wait_challenge(self):
        """Dính challenge tương tác: nhắn Telegram cho người tick, chờ tối đa 5 phút."""
        print("\n  ! Cloudflare đang chặn — cần NGƯỜI xác minh trên màn hình server "
              "(cửa sổ Chromium đang mở). Đã nhắn Telegram, chờ tối đa "
              f"{CHALLENGE_WAIT // 60} phút...", flush=True)
        if not self._notified_challenge:
            self._notified_challenge = True
            _notify_telegram(
                "⚠️ Tải comix.to đang bị Cloudflare chặn.\n\n"
                "CẦN LÀM: mở màn hình máy server → cửa sổ Chromium đang hiện → "
                "tick ô \"Verify you are human\" (Xác minh bạn là người).\n\n"
                f"Tool chờ tối đa {CHALLENGE_WAIT // 60} phút rồi tự tải tiếp; "
                "quá giờ sẽ dừng phiên (chạy lại /tai sau khi xác minh).")
        end = time.monotonic() + CHALLENGE_WAIT
        while time.monotonic() < end:
            time.sleep(3)
            if not self._challenge_present():
                print("  -> Đã qua Cloudflare, chạy tiếp.", flush=True)
                _notify_telegram("✅ Comix: đã qua Cloudflare, đang tải tiếp.")
                return
        _notify_telegram("⛔ Comix: quá 5 phút chưa qua Cloudflare — phiên tải dừng. "
                         "Xác minh xong hãy /tai lại.")
        raise core.Blocked("Cloudflare challenge không được xác minh trong "
                           f"{CHALLENGE_WAIT}s")

    # -- Điều hướng + bắt dữ liệu ------------------------------------------------

    def _goto(self, url):
        for attempt in range(3):
            try:
                self.page.goto(url, wait_until="domcontentloaded")
                # tab quảng cáo lỡ bật (target=_blank) -> đóng, giữ đúng 1 page
                for p in list(self.ctx.pages):
                    if p is not self.page:
                        try:
                            p.close()
                        except Exception:
                            pass
                if self._challenge_present():
                    self._wait_challenge()
                return
            except core.Blocked:
                raise
            except Exception as e:
                # Chromium đã đóng hẳn -> retry vô ích; báo fatal để run() dựng lại.
                if not self.alive():
                    raise BrowserGone(f"Chromium đã đóng khi mở {url}: {e}") from e
                if attempt == 2:
                    raise RuntimeError(f"Không mở được {url}: {e}") from e
                time.sleep(3 * (attempt + 1))

    def _pump(self, want, timeout=20.0, desc="dữ liệu"):
        """Rút dần window.__cap tới khi gặp payload thỏa `want`. Site SPA gọi API ngay
        sau load nên thường bắt được trong ~1-2s. Trả payload, hoặc None nếu hết giờ
        (KHÔNG raise — người gọi tự quyết retry / rơi xuống bản khác / bỏ qua)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                batch = self.page.evaluate(
                    "() => { const c = window.__cap || []; window.__cap = []; return c; }")
            except Exception:
                if not self.alive():
                    raise BrowserGone("Chromium đã đóng khi đọc payload")
                batch = []
            for o in batch or []:
                try:
                    if want(o):
                        return o
                except Exception:
                    pass
            if self._challenge_present():
                self._wait_challenge()
                end = time.monotonic() + timeout   # qua challenge -> làm mới đồng hồ
            time.sleep(0.4)
        return None

    def fetch_series(self, slug):
        """Gom TOÀN BỘ bản upload của truyện (mọi trang list, limit 20 do site cố
        định; phân trang bằng URL ?page=N — không lệ thuộc DOM nút bấm).
        Trả (title, cover_url, items)."""
        items, page_no, last = [], 1, None
        title = cover = None
        while last is None or page_no <= last:
            def is_list(o, n=page_no):
                r = o.get("result") or {}
                meta, its = r.get("meta"), r.get("items")
                return (isinstance(meta, dict) and isinstance(its, list)
                        and meta.get("page") == n
                        and (not its or "isOfficial" in its[0]))

            # Retry mỗi trang list: cùng nguyên nhân với ảnh chương (quảng cáo/mạng
            # chèn) có thể làm hụt 1 lần — mở lại vài lần trước khi chịu thua.
            payload = None
            for attempt in range(3):
                time.sleep(random.uniform(0.6, 1.2))
                try:
                    self._goto(f"{BASE}/title/{slug}?page={page_no}")
                except (core.Blocked, BrowserGone):
                    raise
                except Exception:
                    continue
                payload = self._pump(is_list, desc=f"danh sách chương (trang {page_no})")
                if payload is not None:
                    break
            if payload is None:
                raise RuntimeError(
                    f"Không lấy được danh sách chương (trang {page_no}) từ comix.to — "
                    "mạng chập chờn? Thử /tai lại sau.")
            r = payload["result"]
            last = int(r["meta"].get("lastPage") or 1)
            items.extend(r["items"])
            if title is None:
                # Site KHÔNG có og:image — bìa là <img> đầu tiên trỏ static.comix.to,
                # dạng .../68deeb...@280.jpg (thumbnail 280px; bỏ '@280' = bản full).
                title, cover = self.page.evaluate(
                    """() => {
                        const t = document.querySelector('meta[property="og:title"]');
                        let name = (t && t.content) || document.title || '';
                        name = name.replace(/\\s*[\\u00b7|–—-]\\s*Comix.*$/i, '').trim();
                        const img = [...document.querySelectorAll('img')].find(
                            i => (i.currentSrc || i.src || '').includes('static.comix.to'));
                        return [name, img ? (img.currentSrc || img.src) : null];
                    }""")
            print(f"\r  Danh sách chương: trang {page_no}/{last} — "
                  f"cộng dồn {len(items)} bản upload   ", end="", flush=True)
            page_no += 1
        print()
        return title or slug, cover, items

    def fetch_pages(self, url_path, chap_id, tries=3):
        """URL ảnh của 1 bản upload (điều hướng tới trang đọc, hook bắt payload).

        Trả:
          [url, ...] - lấy được (rỗng nếu payload có nhưng 0 trang = khóa/premium thật)
          None       - KHÔNG bắt được payload sau `tries` lần (mạng/quảng cáo chèn) ->
                       người gọi rơi xuống bản khác / đánh dấu 'để sau', KHÔNG raise.
        """
        def is_chap(o):
            r = o.get("result") or {}
            return r.get("id") == chap_id and isinstance(r.get("pages"), dict)

        payload = None
        for attempt in range(tries):
            time.sleep(random.uniform(0.6, 1.2))
            try:
                self._goto(BASE + url_path)
            except (core.Blocked, BrowserGone):
                raise
            except Exception:
                continue                      # goto hỏng -> mở lại
            payload = self._pump(is_chap, desc=f"ảnh chương (id {chap_id})")
            if payload is not None:
                break                          # bắt được (kể cả 0 trang) -> thôi retry
        if payload is None:
            print(f"\n    ! Chưa lấy được ảnh chương (id {chap_id}) sau {tries} lần thử "
                  "(mạng/quảng cáo chèn?).", file=sys.stderr, flush=True)
            return None

        pg = payload["result"]["pages"]
        base = (pg.get("baseUrl") or "").rstrip("/")
        out = []
        for it in pg.get("items") or []:
            u = it.get("url") or ""
            if not u:
                continue
            if not u.startswith("http"):
                u = base + "/" + u.lstrip("/")
            out.append(u)
        return out


# --- Client tải ảnh (giả vân tay Chrome + mượn vé Cloudflare) ---------------------

class ComixImageClient:
    """HTTP client CHỈ để tải ảnh comix, khác `core.session` mặc định ở 2 điểm:

    1. VÂN TAY TLS: dùng curl_cffi impersonate="chrome" -> handshake JA3/JA4 + HTTP2
       giống Chrome thật. Cloudflare đời mới soi cả vân tay TLS; `requests` (urllib3)
       lộ ngay là "Python" nên khi site siết, vé cf_clearance chìa qua handshake
       không-phải-Chrome bị coi là replay -> 403. Impersonate xoá đúng lỗ hổng đó.
       Thiếu curl_cffi -> tự lùi về requests thường (vẫn mượn vé, chỉ không giả TLS).
    2. DANH TÍNH MƯỢN SỐNG: đọc UA thật + cookie .comix.to (gồm cf_clearance) từ
       CHÍNH browser Playwright đang mở, nạp vào client. Nhờ vậy request ảnh mang cùng
       "vé + UA + Referer + TLS" như trình duyệt đang qua cửa -> Cloudflare cho đi.

    An toàn luồng: refresh_identity() ĐỘNG tới browser (page.evaluate/ctx.cookies) nên
    CHỈ được gọi ở MAIN THREAD (Playwright sync API cấm gọi chéo luồng). get() không
    đụng browser -> worker thread gọi thoải mái. Vé làm mới CHỦ ĐỘNG mỗi chương + khi
    dính 403 (đều ở main thread), worker chỉ đọc snapshot dict đã nạp sẵn."""

    def __init__(self, cs: "ComixSession"):
        self.cs = cs
        self._cookies = {}          # {name: value} cookie .comix.to (snapshot, đọc từ worker OK)
        self._impl = None
        self.backend = None
        self._build()
        # Lần đọc danh tính ĐẦU chạm browser (page.evaluate + ctx.cookies) — nửa sau của
        # "cửa sổ im lặng" trong sự cố 17/08. Probe ở _launch đã xác nhận trang lái được,
        # nhưng bọc watchdog cho kín: treo ở đây thì watchdog kill Chromium -> lần chạm
        # browser kế (fetch_series) bật lỗi -> _resilient tự dựng lại.
        with _StartupWatchdog(LAUNCH_WATCHDOG, "đọc danh tính từ browser (refresh_identity)"):
            self.refresh_identity()
        print(f"  (client tải ảnh: {self.backend})", flush=True)

    def _build(self):
        """Dựng client nền: ưu tiên curl_cffi (giả TLS Chrome), thiếu thì requests riêng."""
        try:
            from curl_cffi import requests as cffi
            self._impl = cffi.Session(impersonate="chrome")
            self.backend = "curl_cffi (giả vân tay Chrome)"
            return
        except Exception:
            pass
        # Fallback Bậc 1: requests RIÊNG (không đụng core.session dùng chung 5 site) —
        # vẫn mượn được vé + UA, chỉ thiếu lớp giả TLS.
        self._impl = requests.Session()
        self.backend = "requests (KHÔNG giả TLS — cài curl_cffi để chắc hơn)"

    def refresh_identity(self):
        """Đọc UA thật + cookie .comix.to từ browser, nạp vào client. Gọi ở MAIN THREAD:
        lúc khởi tạo, đầu mỗi chương (vé có thể xoay), và ngay khi dính 403."""
        try:
            ua = self.cs.page.evaluate("() => navigator.userAgent")
            if ua:
                self._impl.headers["User-Agent"] = ua
        except Exception:
            pass   # giữ UA cũ nếu page đang bận/hụt
        self._impl.headers["Referer"] = REFERER
        cookies = {}
        try:
            for c in self.cs.ctx.cookies():
                dom = (c.get("domain") or "").lstrip(".").lower()
                if dom == "comix.to" or dom.endswith(".comix.to"):
                    cookies[c["name"]] = c["value"]
        except Exception:
            pass
        if cookies:                # chỉ đè khi đọc được, tránh xoá sạch vé lúc đọc hụt
            self._cookies = cookies

    def get(self, url, timeout=60):
        """Bề mặt kiểu requests cho core.download_image. Gắn cookie comix CHỈ cho host
        *.comix.to (wowpic không cần vé, cookie sai host còn phản tác dụng). Gói lỗi
        nền (curl_cffi ném lớp riêng) thành requests.RequestException để core coi như
        lỗi mạng mà retry, thay vì vỡ ra ngoài."""
        try:
            host = (urllib.parse.urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
        send = self._cookies if host.endswith("comix.to") else None
        try:
            return self._impl.get(url, timeout=timeout, cookies=send)
        except requests.RequestException:
            raise
        except Exception as e:
            raise requests.RequestException(str(e)) from e

    def close(self):
        try:
            self._impl.close()
        except Exception:
            pass


# --- Chọn bản + sidecar ----------------------------------------------------------

def series_slug(text):
    """'https://comix.to/title/6elqg-rankers-return?...' -> '6elqg-rankers-return'.
    Dán nhầm URL 1 chương (/title/{slug}/{id}-chapter-N) cũng ra đúng slug truyện."""
    m = re.search(r"/title/([^/?#]+)", text.strip())
    return m.group(1) if m else text.strip()


def group_versions(items):
    """{số chương: [item, ...]} — chỉ giữ bản en, có id + url; số hỏng thì bỏ."""
    by = {}
    for it in items:
        if (it.get("language") or "en") != "en":
            continue
        if not it.get("id") or not it.get("url"):
            continue
        raw = it.get("number")
        try:
            num = 0.0 if raw is None else float(raw)   # oneshot/không số -> 0.0
        except (TypeError, ValueError):
            continue
        by.setdefault(num, []).append(it)
    return by


def candidates_for(versions):
    """Thứ tự ưu tiên tải: official (id mới nhất trước) rồi scan (id mới nhất trước).
    Bản đầu 0 trang thì caller tự rơi xuống bản kế."""
    off = sorted((v for v in versions if v.get("isOfficial")),
                 key=lambda v: v["id"], reverse=True)
    scan = sorted((v for v in versions if not v.get("isOfficial")),
                  key=lambda v: v["id"], reverse=True)
    return off + scan


def _group_name(ver):
    g = ver.get("group")
    return (g.get("name") if isinstance(g, dict) else g) or "?"


def read_sidecar(folder: Path):
    try:
        # utf-8-sig: tha cho file bị editor/PowerShell chèn BOM (json.loads chê BOM)
        return json.loads((folder / SIDECAR).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def write_sidecar(folder: Path, ver):
    folder.mkdir(parents=True, exist_ok=True)
    data = {"chapterId": ver["id"], "groupId": ver.get("groupId"),
            "group": _group_name(ver), "isOfficial": bool(ver.get("isOfficial")),
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    (folder / SIDECAR).write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# --- Tiện ích file trong folder chương -------------------------------------------

def _page_file(folder: Path, i: int):
    """File trang i đã có trên đĩa (đuôi bất kỳ — sau sniff có thể là .jpg/.png)."""
    for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".avif", ".bmp"):
        p = folder / f"{i:03d}{ext}"
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def _fix_ext(path: Path) -> Path:
    """URL comix không có đuôi -> tải về đặt .webp rồi sửa theo magic bytes thật."""
    try:
        with path.open("rb") as f:
            head = f.read(32)
    except OSError:
        return path
    fmt = core.sniff_format(head)
    want = {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif",
            "bmp": ".bmp", "avif": ".avif", "heif": ".avif"}.get(fmt)
    if not want or path.suffix.lower() == want or \
            (want == ".jpg" and path.suffix.lower() == ".jpeg"):
        return path
    new = path.with_suffix(want)
    try:
        path.rename(new)
        return new
    except OSError:
        return path


def _clear_images(folder: Path):
    """Đổi sang bản upload khác -> dọn ảnh (và .done) của bản cũ kẻo trộn ảnh 2 nhóm."""
    if not folder.is_dir():
        return
    for p in folder.iterdir():
        if p.is_file() and (p.suffix.lower() in core.IMG_EXTS
                            or p.name == ".done" or p.name.endswith(".bad")):
            try:
                p.unlink()
            except OSError:
                pass


def _mark_done(folder: Path):
    try:
        (folder / ".done").write_text("", encoding="utf-8")
    except OSError:
        pass


def _folder_has_images(folder: Path) -> bool:
    """Folder chương này có ≥1 ảnh thật không (để phân biệt 'đã có nội dung' với rỗng)."""
    if not folder.is_dir():
        return False
    try:
        for p in folder.iterdir():
            if p.is_file() and p.suffix.lower() in core.IMG_EXTS:
                return True
    except OSError:
        pass
    return False


def _report_comix_plan(title, nums, by_num, out_root, args):
    """Nhắn Telegram BÁO CÁO SỚM cho comix: X/Y chương + danh sách cần nâng cấp/tải,
    tính TỪ ĐĨA (không thêm request), TRƯỚC khi tải ảnh. Phân loại MIRROR đúng vòng lặp
    chính (official-sẵn / đã-có / nâng-cấp-lên-Official / cần-tải) — sửa luật ở loop thì
    nhớ sửa cả đây. 'Official' = bản tick 'v' (isOfficial). Best-effort, không raise ra."""
    official_have, have_other, upgrade_list, need_list = [], [], [], []
    recheck = getattr(args, "recheck", False)
    for num in nums:
        folder = out_root / f"Chapter {core.fmt_num(num)}"
        cands = candidates_for(by_num.get(num) or [])
        best = cands[0] if cands else {}
        side = read_sidecar(folder)
        done = (folder / ".done").exists() and not recheck
        on_disk_official = bool(side) and side.get("isOfficial")
        if on_disk_official and done:
            official_have.append(num)
            continue
        upgrade = (_folder_has_images(folder) and not on_disk_official
                   and bool(best.get("isOfficial")))
        if done and not upgrade:
            have_other.append(num)
        elif upgrade:
            upgrade_list.append(num)
        else:
            need_list.append(num)
    have_total = len(official_have) + len(have_other)
    lines = [f"📘 {title} — comix",
             f"• Trên site: {len(nums)} chương",
             f"• Đã có sẵn: {have_total} (Official {len(official_have)})",
             f"• Cần nâng cấp → Official: {len(upgrade_list)}"
             + (f" — ch. {core.compact_chapters(upgrade_list)}" if upgrade_list else ""),
             f"• Cần tải mới/tải tiếp: {len(need_list)}"
             + (f" — ch. {core.compact_chapters(need_list)}" if need_list else "")]
    lines.append("→ Bắt đầu tải..." if (upgrade_list or need_list)
                 else "→ Không có gì cần tải (đã đủ).")
    _notify_telegram("\n".join(lines))


# --- File DẤU cấp truyện (Cách 1: nhìn thấy được trong Explorer) ------------------
# Đánh dấu folder do comix quản (có / đang lên bản Official) để user phân biệt với
# folder scan tải từ site khác mà TỰ TAY xoá folder scan trùng. Tên file mang sẵn số
# 'official/tổng' nên khỏi mở ra đọc; reader + check_library bỏ qua vì không phải ảnh.
MARKER_PREFIX = "_COMIX_official_"    # + "{off}-{total}.txt"


def write_series_marker(out_root: Path, slug: str):
    """Ghi/đè file dấu ở gốc folder truyện. Đếm theo sidecar từng chương:
      official = bản tick 'v'; scan = bản nhóm do comix tải; ngoài = có ảnh nhưng
      KHÔNG có sidecar (tải từ site khác, chưa nâng cấp). CHỈ ghi khi comix thực sự
      đã đóng góp ≥1 chương (off+scan>0) — folder toàn bản ngoài thì chưa đánh dấu."""
    off = scan = foreign = 0
    try:
        subdirs = [d for d in out_root.iterdir() if d.is_dir()]
    except OSError:
        return
    for d in subdirs:
        if not _folder_has_images(d):
            continue
        sc = read_sidecar(d)
        if sc is None:
            foreign += 1
        elif sc.get("isOfficial"):
            off += 1
        else:
            scan += 1
    if off + scan == 0:        # comix chưa đóng góp gì vào folder này -> chưa đánh dấu
        return
    total = off + scan + foreign
    for old in out_root.glob(MARKER_PREFIX + "*.txt"):   # dọn file dấu cũ (số khác)
        try:
            old.unlink()
        except OSError:
            pass
    lines = [
        "FOLDER NAY DO COMIX (comix.to) QUAN LY.",
        "Giu folder nay. Neu co folder trung truyen tai tu site khac (khong co file "
        "dau nay) thi XOA folder do.",
        "",
        f"slug     : {slug}",
        f"official : {off} chuong (ban tick 'v')",
        f"scan     : {scan} chuong (comix chua co official)",
        f"ngoai    : {foreign} chuong (tai tu site khac, chua nang cap)",
        f"tong     : {total} chuong",
        f"cap nhat : {datetime.now():%Y-%m-%d %H:%M:%S}",
    ]
    try:
        (out_root / f"{MARKER_PREFIX}{off}-{total}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


# --- Vòng tải chính --------------------------------------------------------------

def _resilient(cs, call):
    """Chạy `call()` trên session `cs`; Chromium chết giữa chừng -> cs.relaunch() rồi
    thử lại trên browser mới. Quá ngưỡng dựng lại -> relaunch() ném BrowserGone ra
    ngoài = fatal. `call` phải là lambda tham chiếu `cs` (đừng truyền bound method của
    session cũ — relaunch thay ctx/page BÊN TRONG cùng object nên bound method vẫn đúng,
    nhưng lambda cho rõ ý)."""
    while True:
        try:
            return call()
        except BrowserGone:
            cs.relaunch()


def run(args):
    try:
        import playwright  # noqa: F401 — dep tùy chọn, chỉ cần cho comix
    except ImportError:
        print("Thiếu Playwright (chỉ site comix.to cần). Cài bằng:\n"
              "   pip install playwright\n"
              "   python -m playwright install chromium", file=sys.stderr)
        sys.exit(1)

    core.reap_decode_crash()
    core.session.headers["Referer"] = REFERER   # CDN wowpic đòi Referer comix.to

    slug = series_slug(args.series)
    print(f"Site: comix  |  Truyện: {slug}")
    # Dọn Chromium mồ côi + khoá profile cũ TRƯỚC khi mở, kẻo con mới chuyển URL cho
    # con cũ rồi tự thoát -> Playwright treo ở about:blank (sự cố 14/08). An toàn vì 1
    # worker tuần tự. Nghỉ 1s cho OS nhả handle trước khi launch_persistent_context.
    _kill_profile_chrome()
    time.sleep(1)
    print("(Sẽ mở 1 cửa sổ Chromium để lấy metadata — ĐỪNG đóng nó, tool tự đóng khi xong.)")

    try:
        with ComixSession() as cs:
            img_client = ComixImageClient(cs)   # tải ảnh: giả TLS Chrome + mượn vé sống
            title, cover, items = _resilient(cs, lambda: cs.fetch_series(slug))
            by_num = group_versions(items)
            if not by_num:
                print("Không lấy được danh sách chương. Kiểm tra lại URL.", file=sys.stderr)
                sys.exit(1)
            nums = sorted(by_num)
            print(f"Tổng số chương tìm thấy: {len(nums)} "
                  f"({sum(len(v) for v in by_num.values())} bản upload)")

            if args.chapters:
                wanted = core.parse_selection(args.chapters)
                nums = [n for n in nums if n in wanted]
            else:
                if args.c_from is not None:
                    nums = [n for n in nums if n >= args.c_from]
                if args.c_to is not None:
                    nums = [n for n in nums if n <= args.c_to]
            if not nums:
                print("Không có chương nào khớp lựa chọn.", file=sys.stderr)
                sys.exit(1)

            out_root = Path(args.out) / core.safe_name(title)
            tmp_root = Path(args.out) / TMP_DIRNAME / core.safe_name(title)
            out_root.mkdir(parents=True, exist_ok=True)
            # xác tráo-folder dở từ phiên trước (crash giữa swap) -> dọn
            if tmp_root.exists():
                for d in tmp_root.glob("*.__trash"):
                    shutil.rmtree(d, ignore_errors=True)
            if cover:
                # fetch_series vừa (có thể) giải Cloudflare -> lấy vé mới cho cover.
                img_client.refresh_identity()
                # thử bản full (bỏ '@280') trước, hụt (404) thì lấy luôn bản thumb.
                # Cover là phụ: 403/lỗi ở đây KHÔNG được giết cả phiên tải chương.
                full = re.sub(r"@\d+(\.\w+)$", r"\1", cover)
                try:
                    for cu in dict.fromkeys([full, cover]):
                        core.download_cover(cu, out_root, client=img_client)
                        if any(p.stem.lower() == "cover" for p in out_root.iterdir()
                               if p.is_file() and p.suffix.lower() in core.IMG_EXTS):
                            break
                except core.Blocked:
                    print("  ! Bỏ qua ảnh bìa (bị chặn tạm) — tải chương vẫn tiếp tục.",
                          file=sys.stderr)
                    core.gate.abort = False   # gỡ cầu dao nếu cover vừa kéo, để tải chương
            print(f"Sẽ xử lý {len(nums)} chương vào: {out_root.resolve()}\n")

            # BÁO CÁO SỚM (Option 1, user chốt 14/08): đã có danh sách chương + trạng thái
            # đĩa -> nhắn Telegram X/Y + cần nâng cấp/tải NGAY, TRƯỚC khi tải ảnh. comix không
            # có peek rẻ nên báo cáo này phải chờ Chromium mở xong (không tức thì như site
            # thường). Chỉ ĐỌC ĐĨA (không thêm request). Lỗi ở đây KHÔNG được cản việc tải.
            try:
                _report_comix_plan(title, nums, by_num, out_root, args)
            except Exception as e:
                print(f"  (bỏ qua báo cáo sớm: {e})", file=sys.stderr, flush=True)

            total = len(nums)
            active = 0
            fail_streak = 0   # số chương LIÊN TIẾP hụt ảnh (browser còn sống) -> cầu dao
            incomplete, source_broken, unfetched = [], [], []
            n_full = n_skipped = n_locked = n_upgraded = 0
            img_ok = img_missing = img_broken = 0

            for idx, num in enumerate(nums, 1):
                label = f"Chapter {core.fmt_num(num)}"
                prefix = f"[{idx}/{total}] {label}"
                folder = out_root / label   # tên CỐ ĐỊNH (không title) để tráo bản an toàn
                cands = candidates_for(by_num[num])
                best = cands[0]
                side = read_sidecar(folder)
                done = (folder / ".done").exists() and not getattr(args, "recheck", False)
                # Folder đã có ảnh nhưng KHÔNG mang sidecar comix = bản tải từ site KHÁC
                # (Raven, Asura...) hoặc bản comix rất cũ. Coi là "bản ngoài/scan" để luật
                # upgrade cũng áp cho nó (thay bằng Official nếu comix nay có) — đây là ca
                # Dungeon Reset: 266 chương Raven .done, không sidecar, trước đây bị skip.
                on_disk_official = bool(side) and side.get("isOfficial")

                # 1) Trên đĩa đã là bản Official -> skip vĩnh viễn
                if on_disk_official and done:
                    print(f"{prefix} — đã có bản Official (bỏ qua)")
                    n_skipped += 1
                    if args.cbz:
                        core.make_cbz(folder, skip_existing=True)
                    continue

                # Upgrade khi: đĩa đang có nội dung CHƯA phải Official (gồm cả bản ngoài
                # không sidecar) và comix nay có bản Official. KHÔNG bao giờ thay scan->scan.
                has_content = _folder_has_images(folder)
                upgrade = has_content and not on_disk_official \
                    and bool(best.get("isOfficial"))

                # 2) Đã đủ ảnh + không phải ca upgrade -> giữ nguyên (kể cả bản ngoài;
                # không thay scan->scan dù bản scan comix có mới hơn)
                if done and not upgrade:
                    print(f"{prefix} — đã xong trước đó (bỏ qua, khỏi quét mạng)")
                    n_skipped += 1
                    if args.cbz:
                        core.make_cbz(folder, skip_existing=True)
                    continue

                # 3) Chọn nơi tải + thứ tự ứng viên
                if upgrade:
                    dest = tmp_root / label      # tải bản official vào chỗ tạm, xong mới tráo
                    pool = cands                 # best là official
                else:
                    dest = folder
                    if side:   # tải dở -> ưu tiên tiếp ĐÚNG bản cũ, tránh trộn ảnh 2 nhóm
                        same = [v for v in cands if v["id"] == side.get("chapterId")]
                        pool = same + [v for v in cands if v["id"] != side.get("chapterId")]
                    else:
                        pool = cands

                # 4) Thử lần lượt ứng viên tới khi có ảnh. Chỉ ĐỘNG vào đĩa (dọn ảnh cũ +
                # ghi sidecar) khi bản này thực sự lấy được ảnh — bản fetch hụt/0-trang
                # KHÔNG được xoá nội dung đang có (tránh phá bản tải dở khi chỉ chập mạng).
                chosen, urls, fetch_failed = None, [], False
                for ver in pool:
                    res = _resilient(cs, lambda v=ver: cs.fetch_pages(v["url"], v["id"]))
                    if res is None:              # bắt hụt (mạng/quảng cáo) -> thử bản khác
                        fetch_failed = True
                        print(f"{prefix} — bản [{_group_name(ver)}] chưa lấy được, thử bản khác...")
                        continue
                    if not res:                  # payload có nhưng 0 trang = khóa/premium thật
                        print(f"{prefix} — bản [{_group_name(ver)}] 0 trang, thử bản khác...")
                        continue
                    d_side = read_sidecar(dest)
                    # Dọn ảnh cũ nếu dest đang giữ bản KHÁC id, hoặc có ảnh không rõ nguồn
                    # (bản ngoài) — kẻo trộn ảnh 2 bản.
                    if (d_side and d_side.get("chapterId") != ver["id"]) \
                            or (d_side is None and _folder_has_images(dest)):
                        _clear_images(dest)
                    write_sidecar(dest, ver)
                    chosen, urls = ver, res
                    break
                if not chosen:
                    # Không dừng cả bộ: fetch hụt -> 'để sau' (chạy lại bù); 0-trang thật -> khóa.
                    if fetch_failed:
                        print(f"{prefix} — chưa lấy được ảnh (mạng/quảng cáo chèn?), "
                              "sẽ bù ở lần chạy sau")
                        unfetched.append(label)
                        core.append_log(f"{title} / {label}: chưa lấy được ảnh "
                                        "(mạng/quảng cáo) — chạy lại để bù")
                        # Cầu dao: browser CÒN SỐNG mà hụt nhiều chương liên tiếp = nghi bị
                        # chặn IP mềm / site đổi API -> dừng phiên + báo lỗi thật (thay vì
                        # ghi 'để sau' cả bộ rồi thoát 0 khiến tưởng đã tải xong).
                        fail_streak += 1
                        if fail_streak >= FAIL_STREAK_LIMIT:
                            raise FetchStalled(
                                f"{fail_streak} chương liên tiếp không lấy được ảnh dù "
                                "Chromium còn sống — nghi bị chặn IP mềm hoặc site đổi API")
                    else:
                        print(f"{prefix} — không bản nào có ảnh (khóa/premium?), bỏ qua")
                        n_locked += 1
                        fail_streak = 0   # site vẫn trả lời (khóa thật) -> không tính chuỗi hụt
                    continue

                # Chọn được bản có ảnh = có tiến triển -> reset các bộ đếm sự cố.
                cs.mark_progress()
                fail_streak = 0

                tag = "Official" if chosen.get("isOfficial") else _group_name(chosen)
                pages = list(enumerate(urls, 1))
                jobs = [(i, u) for i, u in pages if _page_file(dest, i) is None]
                have = len(pages) - len(jobs)
                ok = done_ct = have
                print(f"\r{prefix} [{tag}] — {done_ct}/{len(urls)} ảnh, đang tải...   ",
                      end="", flush=True)
                if jobs:
                    # Vé mới nhất từ browser TRƯỚC khi tải (main thread) — bắt kịp ca
                    # cf_clearance hết hạn qua đêm / vừa xoay giữa phiên.
                    img_client.refresh_identity()
                    forbidden_retry = 0
                    while True:
                        remaining = [(i, u) for i, u in jobs
                                     if _page_file(dest, i) is None]
                        if not remaining:
                            break
                        done_ct = len(urls) - len(
                            [i for i, _ in pages if _page_file(dest, i) is None])
                        try:
                            with ThreadPoolExecutor(max_workers=args.workers) as pool_ex:
                                futures = [pool_ex.submit(core.download_image, u,
                                                          dest / f"{i:03d}.webp", img_client)
                                           for i, u in remaining]
                                try:
                                    for f in as_completed(futures):
                                        if f.result():
                                            ok += 1
                                        done_ct += 1
                                        print(f"\r{prefix} [{tag}] — {done_ct}/{len(urls)} "
                                              "ảnh, đang tải...   ", end="", flush=True)
                                except (core.Blocked, core.TooMany429):
                                    core.gate.abort = True
                                    pool_ex.shutdown(cancel_futures=True)
                                    raise
                            break   # mẻ xong không lỗi -> thôi vòng retry
                        except core.Forbidden:
                            # 403 giữa chương: nhiều khả năng vé vừa xoay. Làm mới vé
                            # (main thread) rồi tải NỐT phần thiếu ĐÚNG 1 lần; vẫn 403
                            # -> để Forbidden bay ra = dừng phiên (chờ vài giờ). KHÔNG
                            # thử mù nhiều lần kẻo tụt điểm uy tín IP.
                            if forbidden_retry >= 1:
                                raise
                            forbidden_retry += 1
                            core.gate.abort = False   # gỡ cầu dao do pool vừa kéo
                            img_client.refresh_identity()
                            print(f"\n{prefix} — 403 (vé Cloudflare?), đã làm mới vé từ "
                                  "browser, thử lại phần còn thiếu...", flush=True)
                            time.sleep(2.0)
                    # URL không có đuôi -> sửa đuôi theo định dạng thật sau khi tải
                    for i, _ in jobs:
                        p = dest / f"{i:03d}.webp"
                        if p.exists() and p.stat().st_size > 0:
                            _fix_ext(p)
                # ok/done chuẩn theo ĐĨA (retry có thể làm lệch bộ đếm cộng dồn)
                ok = len([i for i, _ in pages if _page_file(dest, i) is not None])

                missing = [i for i, _ in pages if _page_file(dest, i) is None]
                broken = [i for i in missing
                          if core.is_known_broken(dest / f"{i:03d}.webp")]
                retryable = [i for i in missing if i not in broken]
                complete = not retryable

                if complete:
                    _mark_done(dest)
                    core.gate.recover()   # 1 chương trọn vẹn = IP/CDN khỏe -> reset cầu dao
                    if upgrade:
                        # Tráo an toàn: cũ -> __trash (cùng ổ đĩa, rename là xong),
                        # tạm -> tên thật, rồi mới xóa rác. Crash điểm nào cũng còn
                        # nguyên 1 bản đọc được; xác __trash dọn ở đầu phiên sau.
                        trash = tmp_root / f"{label}.__trash"
                        # side có thể None (bản tải từ site khác, không sidecar)
                        old_group = (side.get("group") if side else None) \
                            or "bản ngoài (không rõ nhóm)"
                        if folder.exists():
                            folder.rename(trash)
                        dest.rename(folder)
                        shutil.rmtree(trash, ignore_errors=True)
                        # cbz cũ (nếu bản trước có) nay lệch nội dung -> bỏ; args.cbz sẽ nén lại
                        old_cbz = folder.parent / (label + ".cbz")
                        if old_cbz.exists():
                            try:
                                old_cbz.unlink()
                            except OSError:
                                pass
                        n_upgraded += 1
                        print(f"\r{prefix} — DA THAY [{old_group}] bằng bản "
                              f"Official ({len(urls)} ảnh)          ")
                        core.append_log(f"{title} / {label}: thay [{old_group}] "
                                        f"bằng bản Official")
                    else:
                        n_full += 1
                        print(f"\r{prefix} [{tag}] — xong {ok}/{len(urls)} ảnh"
                              "                    ")
                else:
                    note = f" — THIẾU {len(retryable)}: trang {core.compact_ints(retryable)}"
                    if broken:
                        note += (f" — {len(broken)} trang hỏng tại nguồn: "
                                 f"{core.compact_ints(broken)}")
                    if upgrade:
                        note += " — GIỮ bản cũ, chạy lại để tải bù rồi mới thay"
                    print(f"\r{prefix} [{tag}] — xong {ok}/{len(urls)} ảnh{note}          ")
                    incomplete.append((label, retryable))
                    core.append_log(f"{title} / {label}: thiếu "
                                    f"{len(retryable)}/{len(urls)} trang "
                                    f"[{core.compact_ints(retryable)}] — chạy lại để tải bù")
                if broken:
                    source_broken.append((label, broken))

                img_ok += len(urls) - len(missing)
                img_missing += len(retryable)
                img_broken += len(broken)

                if args.cbz and (complete or not upgrade):
                    # sau upgrade phải nén lại (đè cbz cũ của bản scan)
                    core.make_cbz(folder, skip_existing=not (upgrade and complete))

                active += 1
                if active % 10 == 0:
                    rest = random.uniform(60, 90)
                    print(f"  (đang nghỉ {rest:.0f}s cho giống nhịp người đọc — KHÔNG "
                          f"phải treo, sẽ tự chạy tiếp...)", flush=True)
                    time.sleep(rest)
                else:
                    time.sleep(random.uniform(0.7, 1.3) * args.delay)

            # Đóng dấu folder comix (Cách 1) — quét lại toàn bộ chương để số official/
            # tổng phản ánh đúng trạng thái sau lượt này.
            write_series_marker(out_root, slug)
            img_client.close()
    except (core.Blocked, core.TooMany429) as e:
        print(f"\n!!! Dừng phiên: {e}", file=sys.stderr)
        print("Ảnh đã tải không mất. Chờ một lúc (429: ~1 giờ; 403/503/Cloudflare: "
              "vài giờ) rồi chạy lại đúng lệnh này - tự tải tiếp chỗ dở.", file=sys.stderr)
        sys.exit(2)
    except (BrowserGone, FetchStalled) as e:
        # Thoát != 0 -> supervisor vào nhánh '❌ Lỗi tải' (đính dòng log cuối này). KHÁC
        # đường cũ: browser chết từng bị nuốt thành 'để sau' cả bộ rồi thoát 0 -> '✅ Tải
        # xong' giả, không ai hay. Nay có báo thật.
        print(f"\n!!! Dừng phiên: {e}", file=sys.stderr)
        print("Ảnh đã tải KHÔNG mất — chạy lại đúng lệnh này để tải tiếp chỗ dở "
              "(chương đã xong tự bỏ qua).", file=sys.stderr)
        sys.exit(2)

    # ---- Tổng kết cả bộ (format khớp engine chung) ----
    bits = [f"Đủ ảnh: {n_full}"]
    if n_upgraded:
        bits.append(f"Đã thay bằng Official: {n_upgraded}")
    if n_skipped:
        bits.append(f"Đã xong trước: {n_skipped}")
    if incomplete:
        bits.append(f"Thiếu trang: {len(incomplete)} (tải lại là bù được)")
    if source_broken:
        bits.append(f"Hỏng tại nguồn: {len(source_broken)}")
    if unfetched:
        bits.append(f"Chưa lấy được: {len(unfetched)} (chạy lại là bù được)")
    if n_locked:
        bits.append(f"Khóa/không ảnh: {n_locked}")
    print(f"\n===== TỔNG KẾT: {title} — {total} chương =====")
    print("   " + "   |   ".join(bits))
    img_bits = [f"OK {img_ok}"]
    if img_missing:
        img_bits.append(f"thiếu {img_missing}")
    if img_broken:
        img_bits.append(f"hỏng nguồn {img_broken}")
    tail = f"  (chưa gồm {n_skipped} chương đã xong trước)" if n_skipped else ""
    print("   Ảnh: " + ", ".join(img_bits) + tail)
    if incomplete:
        print(f"\n! {len(incomplete)} chương còn thiếu trang:")
        for label, miss in incomplete:
            print(f"   - {label}: thiếu {core.compact_ints(miss)}")
        print("-> Chạy lại đúng lệnh vừa rồi để tự tải bù.")
    if unfetched:
        print(f"\n! {len(unfetched)} chương CHƯA lấy được ảnh lần này "
              "(mạng/quảng cáo chèn — KHÔNG phải khóa):")
        print("   " + ", ".join(unfetched))
        print("-> Chạy lại đúng lệnh vừa rồi để tự tải bù các chương này.")
    print("\nHoàn tất.")
