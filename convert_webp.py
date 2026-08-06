#!/usr/bin/env python3
"""
Chuyển ảnh PNG trong một thư mục (và mọi thư mục con) sang WebP.

Kết quả xuất ra thư mục mới <tên>_webp, GIỮ NGUYÊN thư mục gốc:
  - PNG  -> WebP (mặc định q85, chỉnh bằng --quality)
  - JPG  -> copy nguyên trạng (JPG đã nén lossy, nén tiếp chỉ chồng suy hao;
            muốn nén cả JPG thì thêm --jpg-too)
  - File khác (txt, json, cbz...) -> copy nguyên trạng

Chạy lại an toàn: file đã có trong thư mục đích sẽ được bỏ qua (resume).

Ví dụ dùng:
  python convert_webp.py "downloads\\Pokemon Special"
  python convert_webp.py "D:\\anh\\truyen-abc" --quality 90 --jpg-too
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Đảm bảo in được tiếng Việt trên console Windows (cp1252)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def convert_one(src: Path, dst: Path, quality: int) -> tuple[bool, int]:
    """Chuyển 1 ảnh sang WebP. Trả về (ok, số byte kết quả)."""
    from PIL import Image
    try:
        im = Image.open(src)
        if im.mode == "P":  # ảnh bảng màu: WebP không nhận trực tiếp
            im = im.convert("RGBA" if "transparency" in im.info else "RGB")
        try:
            im.save(dst, "WEBP", quality=quality)
        except OSError:
            im.convert("RGB").save(dst, "WEBP", quality=quality)
        return True, dst.stat().st_size
    except Exception as e:
        print(f"  ! Lỗi {src}: {e}", file=sys.stderr)
        return False, 0


def convert_tree(root: Path, quality: int, jpg_too: bool, workers: int):
    import shutil

    if not root.is_dir():
        print(f"Không tìm thấy thư mục: {root}", file=sys.stderr)
        sys.exit(1)
    dest_root = root.parent / (root.name + "_webp")
    conv_exts = {".png"} | ({".jpg", ".jpeg"} if jpg_too else set())

    files = [p for p in root.rglob("*") if p.is_file()]
    print(f"Nguồn : {root.resolve()} ({len(files)} file)")
    print(f"Đích  : {dest_root.resolve()} (q{quality}, "
          f"{'PNG+JPG' if jpg_too else 'chỉ PNG'}, {workers} luồng)\n")

    jobs = []  # (src, dst, convert?)
    for p in files:
        rel = p.relative_to(root)
        if p.suffix.lower() in conv_exts:
            jobs.append((p, dest_root / rel.with_suffix(".webp"), True))
        else:
            jobs.append((p, dest_root / rel, False))
    for _, dst, _ in jobs:
        dst.parent.mkdir(parents=True, exist_ok=True)

    stats = {"conv": 0, "copy": 0, "skip": 0, "err": 0, "in": 0, "out": 0}

    def handle(src: Path, dst: Path, conv: bool):
        if dst.exists() and dst.stat().st_size > 0:
            stats["skip"] += 1
            return
        if conv:
            ok, out_size = convert_one(src, dst, quality)
            if ok:
                stats["conv"] += 1
                stats["in"] += src.stat().st_size
                stats["out"] += out_size
            else:
                stats["err"] += 1
        else:
            shutil.copy2(src, dst)
            stats["copy"] += 1

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(handle, *j) for j in jobs]
        for f in as_completed(futures):
            f.result()
            done += 1
            if done % 500 == 0 or done == len(jobs):
                print(f"  ... {done}/{len(jobs)} "
                      f"(chuyển {stats['conv']}, copy {stats['copy']}, "
                      f"bỏ qua {stats['skip']}, lỗi {stats['err']})", flush=True)

    if stats["in"]:
        print(f"\nDung lượng phần đã chuyển: {stats['in']/1e9:.2f} GB -> "
              f"{stats['out']/1e9:.2f} GB (còn {100*stats['out']/stats['in']:.0f}%)")
    print(f"Hoàn tất: chuyển {stats['conv']}, copy {stats['copy']}, "
          f"bỏ qua {stats['skip']}, lỗi {stats['err']}.")
    print(f"Cây gốc giữ nguyên. Kết quả ở: {dest_root.resolve()}")


def main():
    ap = argparse.ArgumentParser(
        description="Chuyển ảnh PNG trong thư mục sang WebP, xuất ra thư mục *_webp.")
    ap.add_argument("folder", help="Thư mục nguồn (giữ nguyên, không bị sửa)")
    ap.add_argument("--quality", type=int, default=85,
                    help="Chất lượng WebP (mặc định 85)")
    ap.add_argument("--jpg-too", action="store_true",
                    help="Nén cả JPG (mặc định chỉ copy nguyên trạng)")
    ap.add_argument("--workers", type=int, default=8,
                    help="Số luồng xử lý song song (mặc định 8)")
    args = ap.parse_args()
    convert_tree(Path(args.folder), args.quality, args.jpg_too, args.workers)


if __name__ == "__main__":
    main()
