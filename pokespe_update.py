#!/usr/bin/env python3
"""
Cập nhật chương mới Pokemon Special (arc Scarlet Violet) từ pokemonspecial.com.

Cách hoạt động:
  1. Đọc feed Blogger của web, tìm các bài "[CORO²] Scarlet Violet: Chapter NNN".
  2. So với các folder chương đã có trong thư viện -> biết chương nào còn thiếu.
  3. Tải ảnh trang (bản gốc /s0/ full nét), PNG chuyển WebP q85, JPG giữ nguyên,
     xếp vào đúng cấu trúc "[CORO²] Scarlet Violet- Chapter NNN".

Ví dụ dùng:
  python pokespe_update.py            # tải mọi chương còn thiếu
  python pokespe_update.py --dry-run  # chỉ liệt kê chương thiếu, không tải
"""

import argparse
import io
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import requests
from PIL import Image

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

FEED = "https://www.pokemonspecial.com/feeds/posts/default"
LIB = Path(r"D:\claude-code\comics\downloads\Pokemon Special_webp"
           r"\CHƯƠNG 698-- - SCARLET VIOLET")
TITLE_RE = re.compile(r"\[CORO²\] Scarlet Violet: Chapter (\d+)")
QUALITY = 85
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

session = requests.Session()
session.headers.update({"User-Agent": UA})


def polite_get(url: str, *, timeout: int = 30, **kw) -> requests.Response:
    """GET có phép lịch sự: gặp 429 thì dừng-chờ rồi thử lại, 403/503 thì thoát."""
    for attempt in range(4):
        r = session.get(url, timeout=timeout, **kw)
        if r.status_code == 429:
            ra = r.headers.get("Retry-After", "")
            delay = float(ra) if ra.replace(".", "", 1).isdigit() else 90.0 * (attempt + 1)
            print(f"\n  ! Server nhắc 429 - nghỉ {delay:.0f}s rồi thử lại...", flush=True)
            time.sleep(delay)
            continue
        if r.status_code in (403, 503):
            sys.exit(f"Bị chặn (HTTP {r.status_code}) - dừng phiên, thử lại sau vài giờ.")
        r.raise_for_status()
        return r
    sys.exit("Bị 429 liên tục - dừng phiên để giữ uy tín IP, thử lại sau ~1 giờ.")


def web_chapters() -> dict[int, str]:
    """{số chương: link bài} từ feed của blog."""
    r = polite_get(FEED, params={"alt": "json", "max-results": 150})
    out = {}
    for e in r.json()["feed"]["entry"]:
        m = TITLE_RE.search(e["title"]["$t"])
        if m:
            link = next(l["href"] for l in e["link"] if l["rel"] == "alternate")
            out[int(m.group(1))] = link
    return out


def local_chapters() -> set[int]:
    return {int(m.group(1)) for d in LIB.iterdir() if d.is_dir()
            if (m := re.search(r"Chapter (\d+)", d.name))}


def page_images(post_url: str) -> list[tuple[int, str, str]]:
    """[(số trang, url /s0/, đuôi file)] lấy từ 1 bài đăng, sắp theo số trang.

    Blog dùng 2 kiểu tên ảnh tùy thời kỳ: "001.png" (bài cũ) và
    "... 028 page 18.jpg" (bài mới). Ưu tiên kiểu "page N" vì kiểu tên
    thuần số dễ dính nhầm ảnh trang trí của blog (banner 1.png, 3.png...).
    """
    import html as html_mod
    raw = polite_get(post_url).text
    raw = html_mod.unescape(raw).replace("\\x26", "&")
    urls = re.findall(r'https://blogger\.googleusercontent\.com/img/[^"\' ]+', raw)
    paged, numeric = {}, {}
    for u in urls:
        name = unquote(u.rsplit("/", 1)[-1])
        m = re.search(r"page\s*0*(\d+)\.(png|jpe?g)$", name, re.IGNORECASE)
        bucket = paged
        if not m:
            m = re.fullmatch(r"0*(\d+)\.(png|jpe?g)", name, re.IGNORECASE)
            bucket = numeric
        if not m:
            continue  # bỏ ảnh trang trí (CREDIT, Asset...)
        num, ext = int(m.group(1)), m.group(2).lower()
        parts = u.rsplit("/", 2)  # .../<size>/<file> -> ép về /s0/ (bản gốc)
        bucket.setdefault(num, (f"{parts[0]}/s0/{parts[2]}", ext))
    pages = paged or numeric
    return sorted((n, u, e) for n, (u, e) in pages.items())


def save_page(num: int, url: str, ext: str, folder: Path) -> bool:
    r = polite_get(url, timeout=60)
    data = r.content
    im = Image.open(io.BytesIO(data))
    im.load()  # ảnh cụt dữ liệu sẽ báo lỗi ngay tại đây
    if ext == "png":
        if im.mode == "P":
            im = im.convert("RGBA" if "transparency" in im.info else "RGB")
        im.save(folder / f"{num:03d}.webp", "WEBP", quality=QUALITY)
    else:
        (folder / f"{num:03d}.{ext}").write_bytes(data)
    return True


def main():
    ap = argparse.ArgumentParser(description="Tải chương Scarlet Violet còn thiếu.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Chỉ liệt kê chương thiếu, không tải")
    args = ap.parse_args()

    web = web_chapters()
    have = local_chapters()
    missing = sorted(n for n in web if n not in have)
    print(f"Web có {len(web)} chương (mới nhất: {max(web)}), "
          f"máy có {len(have)} chương (mới nhất: {max(have)}).")
    if not missing:
        print("Không có chương mới. Thư viện đã đủ.")
        return
    print(f"Thiếu {len(missing)} chương: {missing}\n")
    if args.dry_run:
        return

    for n in missing:
        folder = LIB / f"[CORO²] Scarlet Violet- Chapter {n:03d}"
        folder.mkdir(exist_ok=True)
        pages = page_images(web[n])
        if not pages:
            print(f"[Chapter {n:03d}] KHÔNG tìm thấy ảnh trang - bỏ qua",
                  file=sys.stderr)
            continue
        nums = [p[0] for p in pages]
        gaps = sorted(set(range(min(nums), max(nums) + 1)) - set(nums))
        print(f"[Chapter {n:03d}] {len(pages)} trang ...", end=" ", flush=True)
        ok = 0
        for num, url, ext in pages:
            try:
                ok += save_page(num, url, ext, folder)
            except Exception as e:
                print(f"\n  ! Lỗi trang {num}: {e}", file=sys.stderr)
            time.sleep(random.uniform(0.2, 0.5))
        note = f" (CẢNH BÁO: khuyết số trang {gaps})" if gaps else ""
        print(f"xong {ok}/{len(pages)}{note}")
        time.sleep(1)

    print("\nHoàn tất.")


if __name__ == "__main__":
    main()
