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

Upgrade scan -> official (sidecar `.source.json` trong folder chương):
  - Trên đĩa là official -> BỎ QUA vĩnh viễn (không tải lại).
  - Trên đĩa là scan + nay có bản "v" -> tải official vào downloads/.comix-tmp/
    (reader bỏ qua folder đầu-dấu-chấm ở tầng trên cùng), ĐỦ ảnh mới tráo folder;
    tên folder GIỮ "Chapter N" (comix cố ý KHÔNG gắn title vào tên folder) để
    bookmark/tiến trình đọc không mất.
  - Scan + chưa có "v" -> giữ nguyên, KHÔNG thay scan bằng scan (kể cả mới hơn).
  - Đang tải dở (chưa .done) -> tiếp đúng bản trong sidecar, tránh trộn ảnh 2 nhóm.

URL ảnh KHÔNG có đuôi file (https://80pd.wowpic1.store/i5/<hash>) -> tải về đặt
tạm .webp rồi sniff magic bytes, sai thì đổi đuôi (Comix thực tế trả webp).

Cloudflare: chạy headful + profile Chromium cố định (.reader-meta/comix-profile)
giữ cookie cf_clearance. Nếu dính challenge tương tác -> gửi Telegram (đọc
.reader-meta/notify-config.json, ưu tiên admin_chat_ids) nhắc người mở màn hình
server tick "Verify you are human", chờ tối đa 5 phút rồi tự chạy tiếp.

Playwright là DEP TÙY CHỌN — chỉ import khi tải comix; thiếu thì in hướng dẫn cài:
    pip install playwright && python -m playwright install chromium
"""

import json
import os
import random
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

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


# --- Phiên trình duyệt -----------------------------------------------------------

class ComixSession:
    """Playwright headful + hook JSON.parse. Chỉ dùng cho metadata (list + URL ảnh)."""

    def __init__(self):
        self._pw = None
        self.ctx = None
        self.page = None
        self._notified_challenge = False

    def __enter__(self):
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
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.set_default_timeout(45_000)
        return self

    def __exit__(self, *exc):
        # LUÔN đóng browser kẻo Chromium mồ côi chiếm profile (supervisor cũng có
        # lưới dọn lúc boot, nhưng đấy là phòng hờ crash, không phải đường chính).
        for obj in (self.ctx, self._pw):
            try:
                if obj is self.ctx and obj:
                    obj.close()
                elif obj is self._pw and obj:
                    obj.stop()
            except Exception:
                pass
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
                if attempt == 2:
                    raise RuntimeError(f"Không mở được {url}: {e}") from e
                time.sleep(3 * (attempt + 1))

    def _pump(self, want, timeout=35.0, desc="dữ liệu"):
        """Rút dần window.__cap tới khi gặp payload thỏa `want`. Site SPA gọi API
        ngay sau load nên thường bắt được trong ~1-2s."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                batch = self.page.evaluate(
                    "() => { const c = window.__cap || []; window.__cap = []; return c; }")
            except Exception:
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
        raise RuntimeError(f"Không bắt được {desc} từ comix.to "
                           "(site đổi cấu trúc API? thử lại sau)")

    def fetch_series(self, slug):
        """Gom TOÀN BỘ bản upload của truyện (mọi trang list, limit 20 do site cố
        định; phân trang bằng URL ?page=N — không lệ thuộc DOM nút bấm).
        Trả (title, cover_url, items)."""
        items, page_no, last = [], 1, None
        title = cover = None
        while last is None or page_no <= last:
            time.sleep(random.uniform(0.6, 1.2))   # nhịp giữa các trang list
            self._goto(f"{BASE}/title/{slug}?page={page_no}")

            def is_list(o, n=page_no):
                r = o.get("result") or {}
                meta, its = r.get("meta"), r.get("items")
                return (isinstance(meta, dict) and isinstance(its, list)
                        and meta.get("page") == n
                        and (not its or "isOfficial" in its[0]))

            payload = self._pump(is_list, desc=f"danh sách chương (trang {page_no})")
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

    def fetch_pages(self, url_path, chap_id):
        """URL ảnh của 1 bản upload (điều hướng tới trang đọc, hook bắt payload)."""
        time.sleep(random.uniform(0.6, 1.2))
        self._goto(BASE + url_path)

        def is_chap(o):
            r = o.get("result") or {}
            return r.get("id") == chap_id and isinstance(r.get("pages"), dict)

        payload = self._pump(is_chap, desc=f"ảnh chương (id {chap_id})")
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


# --- Vòng tải chính --------------------------------------------------------------

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
    print("(Sẽ mở 1 cửa sổ Chromium để lấy metadata — ĐỪNG đóng nó, tool tự đóng khi xong.)")

    try:
        with ComixSession() as cs:
            title, cover, items = cs.fetch_series(slug)
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
                # thử bản full (bỏ '@280') trước, hụt (404) thì lấy luôn bản thumb
                full = re.sub(r"@\d+(\.\w+)$", r"\1", cover)
                for cu in dict.fromkeys([full, cover]):
                    core.download_cover(cu, out_root)
                    if any(p.stem.lower() == "cover" for p in out_root.iterdir()
                           if p.is_file() and p.suffix.lower() in core.IMG_EXTS):
                        break
            print(f"Sẽ xử lý {len(nums)} chương vào: {out_root.resolve()}\n")

            total = len(nums)
            active = 0
            incomplete, source_broken = [], []
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

                # 1) Trên đĩa đã là bản Official -> skip vĩnh viễn
                if side and side.get("isOfficial") and done:
                    print(f"{prefix} — đã có bản Official (bỏ qua)")
                    n_skipped += 1
                    if args.cbz:
                        core.make_cbz(folder, skip_existing=True)
                    continue

                upgrade = bool(side) and not side.get("isOfficial") \
                    and bool(best.get("isOfficial"))

                # 2) Scan đã đủ ảnh + chưa có official -> giữ nguyên (không thay scan->scan)
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

                # 4) Thử lần lượt ứng viên tới khi có ảnh
                chosen, urls = None, []
                for ver in pool:
                    d_side = read_sidecar(dest)
                    if d_side and d_side.get("chapterId") != ver["id"]:
                        _clear_images(dest)      # đổi bản -> dọn ảnh bản cũ trước
                    write_sidecar(dest, ver)
                    urls = cs.fetch_pages(ver["url"], ver["id"])
                    if urls:
                        chosen = ver
                        break
                    print(f"{prefix} — bản [{_group_name(ver)}] 0 trang, thử bản khác...")
                if not chosen:
                    print(f"{prefix} — không bản nào có ảnh (khóa?), bỏ qua")
                    n_locked += 1
                    continue

                tag = "Official" if chosen.get("isOfficial") else _group_name(chosen)
                pages = list(enumerate(urls, 1))
                jobs = [(i, u) for i, u in pages if _page_file(dest, i) is None]
                have = len(pages) - len(jobs)
                ok = done_ct = have
                print(f"\r{prefix} [{tag}] — {done_ct}/{len(urls)} ảnh, đang tải...   ",
                      end="", flush=True)
                if jobs:
                    with ThreadPoolExecutor(max_workers=args.workers) as pool_ex:
                        futures = [pool_ex.submit(core.download_image, u,
                                                  dest / f"{i:03d}.webp")
                                   for i, u in jobs]
                        try:
                            for f in as_completed(futures):
                                if f.result():
                                    ok += 1
                                done_ct += 1
                                print(f"\r{prefix} [{tag}] — {done_ct}/{len(urls)} ảnh, "
                                      "đang tải...   ", end="", flush=True)
                        except (core.Blocked, core.TooMany429):
                            core.gate.abort = True
                            pool_ex.shutdown(cancel_futures=True)
                            raise
                    # URL không có đuôi -> sửa đuôi theo định dạng thật sau khi tải
                    for i, _ in jobs:
                        p = dest / f"{i:03d}.webp"
                        if p.exists() and p.stat().st_size > 0:
                            _fix_ext(p)

                missing = [i for i, _ in pages if _page_file(dest, i) is None]
                broken = [i for i in missing
                          if core.is_known_broken(dest / f"{i:03d}.webp")]
                retryable = [i for i in missing if i not in broken]
                complete = not retryable

                if complete:
                    _mark_done(dest)
                    if upgrade:
                        # Tráo an toàn: cũ -> __trash (cùng ổ đĩa, rename là xong),
                        # tạm -> tên thật, rồi mới xóa rác. Crash điểm nào cũng còn
                        # nguyên 1 bản đọc được; xác __trash dọn ở đầu phiên sau.
                        trash = tmp_root / f"{label}.__trash"
                        old_group = side.get("group", "?")
                        if folder.exists():
                            folder.rename(trash)
                        dest.rename(folder)
                        shutil.rmtree(trash, ignore_errors=True)
                        n_upgraded += 1
                        print(f"\r{prefix} — DA THAY bản [{old_group}] bằng bản "
                              f"Official ({len(urls)} ảnh)          ")
                        core.append_log(f"{title} / {label}: thay bản scan "
                                        f"[{old_group}] bằng bản Official")
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
    except (core.Blocked, core.TooMany429) as e:
        print(f"\n!!! Dừng phiên: {e}", file=sys.stderr)
        print("Ảnh đã tải không mất. Chờ một lúc (429: ~1 giờ; 403/503/Cloudflare: "
              "vài giờ) rồi chạy lại đúng lệnh này - tự tải tiếp chỗ dở.", file=sys.stderr)
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
    print("\nHoàn tất.")
