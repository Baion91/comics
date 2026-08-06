#!/usr/bin/env python3
"""Tải truyện về máy - 1 tool cho MỌI site (tự nhận site theo domain của URL).

Ví dụ dùng:
  python comic_downloader.py https://ravenscans.org/series/rankers-return-remake/
  python comic_downloader.py https://asurascans.com/comics/overgeared-1d35e5bd --from 1 --to 10
  python comic_downloader.py https://ravenscans.org/series/xxx/ --chapters 5,7,20-25 --cbz
  python comic_downloader.py --site raven rankers-return-remake   # ép site khi gõ slug trần
  python comic_downloader.py --pack "downloads\\Rankers Return Remake"  # chỉ nén ảnh có sẵn

(PNG/JPG -> WebP? Dùng script riêng: convert_webp.py. Asura vốn đã webp; Raven là
jpg và KHÔNG nên nén lại - lossy chồng lossy.)
"""

import argparse
import random
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import comics_core as core
from providers import REGISTRY, by_name


def read_list(path):
    """Đọc file hàng đợi: mỗi dòng 1 link. Bỏ dòng trống và dòng bắt đầu bằng #."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as e:
        sys.exit(f"Không đọc được file danh sách '{path}': {e}")
    urls = [ln.strip() for ln in lines]
    return [u for u in urls if u and not u.startswith("#")]


def run_batch(urls, args, default_provider):
    """Tải LẦN LƯỢT nhiều truyện. 1 bộ lỗi -> bỏ qua chạy tiếp; bị chặn IP (exit 2)
    -> DỪNG cả hàng đợi. Nghỉ giữa các bộ cho lịch sự."""
    total = len(urls)
    print(f"HÀNG ĐỢI: {total} truyện\n")
    failed = []
    for i, url in enumerate(urls, 1):
        print(f"\n===== [{i}/{total}] {url} =====")
        try:
            args.series = url   # core.run lấy URL truyện từ args.series
            provider = resolve_provider(url, args.site, default_provider)
            core.run(provider, args)
        except SystemExit as e:
            if e.code == 2:   # bị chặn/nhắc 429 nhiều -> dừng cả mẻ (core đã in hướng dẫn)
                print("\n!!! DỪNG cả hàng đợi vì bị chặn IP. Chờ rồi chạy lại lệnh "
                      "--list để tiếp (ảnh đã tải không mất).", file=sys.stderr)
                raise
            # exit 1 / thông báo: lỗi 1 bộ (sai site, không có chương...) -> bỏ qua
            msg = e.code if isinstance(e.code, str) else "lỗi tải"
            print(f"  ! Bỏ qua truyện này ({msg}).", file=sys.stderr)
            failed.append(url)
        except Exception as e:
            print(f"  ! Bỏ qua truyện này (lỗi: {e}).", file=sys.stderr)
            failed.append(url)
        if i < total:
            rest = random.uniform(30, 60)
            print(f"  (nghỉ {rest:.0f}s giữa 2 truyện...)", flush=True)
            time.sleep(rest)
    print(f"\n===== XONG HÀNG ĐỢI: {total - len(failed)}/{total} bộ OK =====")
    if failed:
        print("Bộ lỗi/bỏ qua (sửa link rồi chạy lại là bù được):")
        for u in failed:
            print("   -", u)


def resolve_provider(series_arg, site_flag, default=None):
    """Chọn provider: ưu tiên cờ --site, rồi domain của URL, rồi default (back-compat)."""
    if site_flag:
        p = by_name.get(site_flag.lower())
        if not p:
            sys.exit(f"Site '{site_flag}' chưa hỗ trợ. Đang có: {', '.join(sorted(by_name))}")
        return p
    host = (urlparse(series_arg).hostname or "").removeprefix("www.") if series_arg else ""
    if host and host in REGISTRY:
        return REGISTRY[host]
    if default:
        return default
    sys.exit(
        f"Không nhận ra site từ '{series_arg}'.\n"
        f"  → Dán URL đầy đủ (vd https://ravenscans.org/series/xxx/)\n"
        f"  → hoặc thêm --site ({', '.join(sorted(by_name))}) nếu gõ slug trần."
    )


def main(default_provider=None):
    ap = argparse.ArgumentParser(description="Tải truyện tranh về máy (đa site).")
    ap.add_argument("series", nargs="?", help="URL truyện (khuyên dùng), hoặc slug + --site")
    ap.add_argument("--site", help=f"Ép site khi gõ slug trần: {', '.join(sorted(by_name))}")
    ap.add_argument("--pack", metavar="FOLDER",
                    help="Không tải gì, chỉ nén các thư mục ảnh có sẵn thành .cbz")
    ap.add_argument("--list", dest="list_file", metavar="FILE",
                    help="Tải HÀNG LOẠT: mỗi dòng trong FILE là 1 link, chạy lần lượt")
    ap.add_argument("--recheck", action="store_true",
                    help="Quét lại cả chương đã đánh dấu .done (mặc định bỏ qua cho nhanh)")
    ap.add_argument("--out", default="downloads", help="Thư mục lưu (mặc định: downloads)")
    ap.add_argument("--from", dest="c_from", type=float, help="Từ chương số ...")
    ap.add_argument("--to", dest="c_to", type=float, help="Đến chương số ...")
    ap.add_argument("--chapters", help="Chọn chương cụ thể, vd: 5,7,20-25")
    ap.add_argument("--workers", type=int, default=2,
                    help="Số luồng tải (mặc định 2; van điều tốc chung vẫn giữ "
                         "nhịp ~1.5-2 request/s nên tăng thêm cũng không nhanh hơn)")
    ap.add_argument("--delay", type=float, default=3.0,
                    help="Nghỉ giữa các chương, giây (mặc định 3, có ngẫu nhiên hóa)")
    ap.add_argument("--cbz", action="store_true", help="Đóng gói mỗi chương thành .cbz")
    ap.add_argument("--retry-broken", action="store_true",
                    help="Thử lại cả ảnh đã ghi nhận hỏng-tại-nguồn (mặc định bỏ qua)")
    args = ap.parse_args()
    core.RETRY_BROKEN = args.retry_broken

    if args.pack:
        core.pack_tree(Path(args.pack))
        return
    if args.list_file:
        urls = read_list(args.list_file)
        if not urls:
            sys.exit(f"File '{args.list_file}' không có link nào (bỏ dòng trống và #).")
        run_batch(urls, args, default_provider)
        return
    if not args.series:
        ap.error("cần URL/slug truyện, hoặc --list FILE, hoặc --pack FOLDER")

    provider = resolve_provider(args.series, args.site, default_provider)
    core.run(provider, args)


if __name__ == "__main__":
    main()
