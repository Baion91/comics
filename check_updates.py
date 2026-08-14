#!/usr/bin/env python3
"""Dò CHƯƠNG MỚI cho các truyện trong watchlist — chạy dạng subprocess bởi supervisor.

Vì sao TÁCH khỏi supervisor: supervisor cố tình chỉ dùng thư viện chuẩn (urllib) cho
bền; script này mới kéo `requests`/providers vào, nên mọi lỗi provider/mạng được CÔ LẬP
trong tiến trình con (fail 1 truyện không làm chết supervisor).

Cách dò (RẺ + ĐÚNG): với mỗi truyện gọi provider.list_chapters() — chỉ request METADATA
(1 request/site, KHÔNG tải ảnh) qua PoliteGate chung — rồi so tập số chương với ĐĨA
(các folder `Chapter N` có `.done`). Dùng ĐĨA làm sự thật (không dựa 1 con số lưu sẵn) để:
  - Chương premium KHOÁ: provider LIỆT KÊ nhưng chưa .done -> luôn hiện "còn thiếu" ->
    tự thử lại tới khi mở khoá (nếu lưu last_max thì sẽ kẹt, không bao giờ check lại).
  - Chương tải dở/thiếu trang: cũng chưa .done -> tự bù.

comix.to: KHÔNG có peek rẻ (phải mở Chromium) và số chương KHÔNG phản ánh việc bản 'v'
tick thay scan -> đánh dấu status="comix" để supervisor ENQUEUE mỗi ngày (loop comix tự
quyết new/upgrade/skip). Site CHƯA có provider -> status="unsupported" (không crash).

KHÔNG ghi đè watchlist.json (supervisor là người ghi duy nhất). Chỉ ĐỌC watchlist +
GHI kết quả ra .reader-meta/watch-check-result.json để supervisor đọc lại.

Dùng:
  python check_updates.py                 # kiểm mọi truyện trong watchlist
  python check_updates.py --only <url>    # chỉ 1 (hoặc lặp --only nhiều lần)
"""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import comics_core as core
from comic_downloader import _COMIX
from providers import REGISTRY, by_name

# In được tiếng Việt trên console Windows (cp1252)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
META_DIR = os.path.join(BASE_DIR, ".reader-meta")
WATCHLIST_FILE = os.path.join(META_DIR, "watchlist.json")
RESULT_FILE = os.path.join(META_DIR, "watch-check-result.json")
DOWNLOADS_DIR = Path(BASE_DIR) / "downloads"


def resolve_provider(url):
    """Trả provider theo domain của URL, hoặc None nếu site CHƯA hỗ trợ.
    KHÔNG dùng comic_downloader.resolve_provider (nó sys.exit khi không nhận ra site)."""
    host = (urlparse(url).hostname or "").removeprefix("www.")
    if not host:
        return None
    if host in _COMIX.domains:
        return _COMIX
    return REGISTRY.get(host)


def is_comix(provider):
    return provider is _COMIX or getattr(provider, "name", "") == "comix"


def _has_images(folder: Path) -> bool:
    """Folder có ≥1 file ảnh (khác marker .done/.bad). Rẻ: dừng ngay ảnh đầu tiên."""
    try:
        for p in folder.iterdir():
            if p.is_file() and p.suffix.lower() in core.IMG_EXTS:
                return True
    except OSError:
        pass
    return False


def done_numbers(out_root: Path):
    """Tập số chương ĐÃ CÓ trên đĩa = folder `Chapter N…` có marker .done HOẶC chứa ảnh.
    Khớp cách đặt tên core.run/comix (`Chapter {fmt_num}` + tùy chọn ` - title`).

    Vì sao 'chứa ảnh' chứ không chỉ .done: thư viện CŨ (tải trước khi có cơ chế .done)
    có đủ ảnh nhưng THIẾU marker .done -> nếu chỉ xét .done sẽ báo nhầm 'thiếu cả bộ' rồi
    enqueue tải lại vô ích. Mục tiêu của checker là dò CHƯƠNG MỚI, không phải soát đủ-trang
    (việc đó là của downloader khi thực sự tải). Chương khoá premium = KHÔNG có ảnh -> vẫn
    lọt vào 'thiếu' -> tự thử lại tới khi mở khoá (đúng ý)."""
    import re
    nums = set()
    if not out_root.is_dir():
        return nums
    for d in out_root.iterdir():
        if not d.is_dir():
            continue
        m = re.match(r"Chapter\s+(\d+(?:\.\d+)?)", d.name)
        if not m:
            continue
        if (d / ".done").exists() or _has_images(d):
            try:
                nums.add(float(m.group(1)))
            except ValueError:
                pass
    return nums


def check_one(entry):
    """Kiểm 1 truyện -> dict kết quả. KHÔNG raise (mọi lỗi -> status='error')."""
    url = entry.get("url", "")
    prev_max = entry.get("last_max")
    res = {
        "url": url, "title": entry.get("title") or url, "provider": "",
        "status": "error", "listed_max": None, "done_max": None,
        "listed_count": 0, "missing_count": 0, "missing_str": "",
        "new_since_last": False, "error": None,
    }
    provider = resolve_provider(url)
    if provider is None:
        res["status"] = "unsupported"
        res["error"] = "site chưa hỗ trợ"
        return res
    res["provider"] = getattr(provider, "name", "")

    if is_comix(provider):
        # Không peek rẻ được -> để supervisor enqueue mỗi ngày, loop comix tự lo.
        res["status"] = "comix"
        return res

    try:
        # Referer đặt theo site (giống core.run) — vài CDN/API đòi. Reset sau mỗi truyện.
        if getattr(provider, "referer", None):
            core.session.headers["Referer"] = provider.referer
        else:
            core.session.headers.pop("Referer", None)
        slug = provider.series_slug(url)
        chapters = provider.list_chapters(slug)
        if not chapters:
            res["error"] = "không lấy được danh sách chương (site đổi/khoá/URL sai?)"
            return res
        title = core.safe_name(provider.title_from_slug(slug))
        res["title"] = title
        listed = {float(c.number) for c in chapters}
        out_root = DOWNLOADS_DIR / title
        done = done_numbers(out_root)
        missing = listed - done
        listed_max = max(listed) if listed else None
        res["status"] = "ok"
        res["listed_max"] = listed_max
        res["done_max"] = max(done) if done else None
        res["listed_count"] = len(listed)
        res["missing_count"] = len(missing)
        res["missing_str"] = core.compact_chapters(missing)   # 'ch. 21-334' gọn
        # 'chương mới thật' = số chương cao nhất tăng so với lần check trước (dùng để
        # HIGHLIGHT noti; chương khoá thử-lại-hằng-ngày thì missing>0 nhưng KHÔNG new).
        if isinstance(prev_max, (int, float)) and listed_max is not None:
            res["new_since_last"] = listed_max > prev_max
    except SystemExit as e:      # provider/core có thể sys.exit -> nuốt, coi là lỗi
        res["error"] = f"thoát bất thường: {e.code}"
    except Exception as e:
        res["error"] = str(e)[:200]
    return res


def load_watchlist():
    try:
        with open(WATCHLIST_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    series = data.get("series") if isinstance(data, dict) else None
    return series if isinstance(series, list) else []


def main():
    ap = argparse.ArgumentParser(description="Dò chương mới cho watchlist.")
    ap.add_argument("--only", action="append", default=[],
                    help="Chỉ kiểm URL này (lặp lại được cho nhiều URL).")
    args = ap.parse_args()

    series = load_watchlist()
    if args.only:
        want = set(args.only)
        series = [s for s in series if s.get("url") in want]

    results = []
    for entry in series:
        if entry.get("paused"):
            continue
        r = check_one(entry)
        results.append(r)
        # log người-đọc ra stdout (supervisor đọc RESULT_FILE, không parse stdout)
        tag = {"ok": "OK", "comix": "comix", "unsupported": "CHƯA HỖ TRỢ",
               "error": "LỖI"}.get(r["status"], r["status"])
        extra = ""
        if r["status"] == "ok":
            extra = f" — mới nhất ch.{_fmt(r['listed_max'])}, thiếu {r['missing_count']}"
        elif r["error"]:
            extra = f" — {r['error']}"
        print(f"[{tag}] {r['title']}{extra}", flush=True)

    payload = {"results": results, "supported": sorted([*by_name, _COMIX.name])}
    try:
        os.makedirs(META_DIR, exist_ok=True)
        tmp = RESULT_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        os.replace(tmp, RESULT_FILE)
    except OSError as e:
        print(f"! Không ghi được kết quả: {e}", file=sys.stderr)
        sys.exit(1)


def _fmt(n):
    if n is None:
        return "?"
    return int(n) if float(n).is_integer() else n


if __name__ == "__main__":
    main()
