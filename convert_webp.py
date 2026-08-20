#!/usr/bin/env python3
"""
Chuyển ảnh PNG trong một thư mục (và mọi thư mục con) sang WebP.

Kết quả xuất ra thư mục mới <tên>_webp, GIỮ NGUYÊN thư mục gốc:
  - PNG  -> WebP (mặc định q85, chỉnh bằng --quality)
  - JPG  -> copy nguyên trạng (JPG đã nén lossy, nén tiếp chỉ chồng suy hao;
            muốn nén cả JPG thì thêm --jpg-too)
  - WebP -> copy nguyên trạng (đã là WebP; muốn RE-NÉN lại ở --quality thấp hơn
            thì thêm --webp-too — dùng cho ảnh comix.to nén nhẹ tay, re-encode
            xuống q85 nhẹ đi ~nửa mà mắt thường không thấy khác)
  - File khác (txt, json, cbz...) -> copy nguyên trạng

CHỐT TIẾT KIỆM (chống nén-chồng vô ích): khi RE-NÉN một WebP, chỉ thay bằng bản
nén nếu nó tiết kiệm >= --min-save % (mặc định 10). Ảnh ĐÃ tối ưu (vd đã q85) nén
lại chỉ nhỏ ~1% -> dưới ngưỡng -> GIỮ NGUYÊN, không chồng thêm suy hao. Nhờ vậy
lỡ chạy nhầm/chạy lại trên folder đã nén cũng an toàn (mỗi ảnh chỉ nén-có-ích 1 lần).

NÉN TẠI CHỖ (--in-place): re-nén WebP NGAY trong folder gốc (không tạo _webp,
khỏi xóa/đổi tên). Chỉ đụng .webp (PNG/JPG bỏ qua); dùng temp + verify + chốt tiết
kiệm nên không mất data, chạy lại idempotent. Hợp cho các bộ comix.to CŨ đã tải:
nén xong downloader vẫn tải tiếp chương mới vào đúng folder đó (giữ .done/.source.json).

Chạy lại an toàn: (tree) file đã có trong thư mục đích được bỏ qua; (in-place) ảnh
đã tối ưu sẽ không bị nén lại nhờ chốt tiết kiệm.

Ví dụ dùng:
  python convert_webp.py "downloads\\Pokemon Special"
  python convert_webp.py "D:\\anh\\truyen-abc" --quality 90 --jpg-too
  python convert_webp.py "downloads\\Overgeared" --webp-too          # re-nén WebP -> cây _webp
  python convert_webp.py "downloads\\Overgeared" --in-place          # re-nén WebP tại chỗ (comix cũ)
"""

import argparse
import io
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Đảm bảo in được tiếng Việt trên console Windows (cp1252)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

MIN_SAVE_DEFAULT = 10   # % — chỉ THAY 1 webp bằng bản nén lại khi tiết kiệm >= mức này;
                        # dưới ngưỡng = "đã tối ưu" -> giữ nguyên (khỏi suy hao vô ích).


def convert_one(src: Path, dst: Path, quality: int) -> tuple[bool, int]:
    """Chuyển 1 ảnh (PNG/JPG) sang WebP. Trả về (ok, số byte kết quả)."""
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


def reencode_webp_bytes(src: Path, quality: int):
    """Nén lại 1 ảnh WEBP trong RAM. Trả bytes bản nén (ĐÃ verify mở lại được), hoặc
    None nếu là webp-ĐỘNG / không mở được / lỗi encode (người gọi giữ nguyên bản gốc).
    Tách riêng để cả tree-mode lẫn in-place dùng chung một logic + chốt tiết kiệm."""
    from PIL import Image
    try:
        with Image.open(src) as im:
            if getattr(im, "is_animated", False):
                return None                    # webp động -> đừng phá khung
            rgb = im.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, "WEBP", quality=quality, method=4)
        data = buf.getvalue()
        with Image.open(io.BytesIO(data)) as chk:   # bản nén phải mở lại được mới nhận
            chk.verify()
        return data
    except Exception:
        return None


def _worth(new_len: int, old_len: int, min_save: int) -> bool:
    """Bản nén có đáng thay không: phải nhỏ hơn bản gốc >= min_save %."""
    return new_len is not None and new_len <= old_len * (1 - min_save / 100)


def convert_tree(root: Path, quality: int, jpg_too: bool, webp_too: bool,
                 min_save: int, workers: int):
    import shutil

    if not root.is_dir():
        print(f"Không tìm thấy thư mục: {root}", file=sys.stderr)
        sys.exit(1)
    dest_root = root.parent / (root.name + "_webp")
    conv_exts = ({".png"} | ({".jpg", ".jpeg"} if jpg_too else set())
                 | ({".webp"} if webp_too else set()))

    files = [p for p in root.rglob("*") if p.is_file()]
    print(f"Nguồn : {root.resolve()} ({len(files)} file)")
    kinds = "PNG" + ("+JPG" if jpg_too else "") + ("+WebP" if webp_too else "")
    print(f"Đích  : {dest_root.resolve()} (q{quality}, {kinds}, "
          f"tiết kiệm tối thiểu {min_save}%, {workers} luồng)\n")

    jobs = []  # (src, dst, convert?)
    for p in files:
        rel = p.relative_to(root)
        if p.suffix.lower() in conv_exts:
            jobs.append((p, dest_root / rel.with_suffix(".webp"), True))
        else:
            jobs.append((p, dest_root / rel, False))
    for _, dst, _ in jobs:
        dst.parent.mkdir(parents=True, exist_ok=True)

    stats = {"conv": 0, "kept": 0, "copy": 0, "skip": 0, "err": 0, "in": 0, "out": 0}

    def handle(src: Path, dst: Path, conv: bool):
        if dst.exists() and dst.stat().st_size > 0:
            stats["skip"] += 1
            return
        if not conv:
            shutil.copy2(src, dst)
            stats["copy"] += 1
            return
        if src.suffix.lower() == ".webp":
            # RE-NÉN webp có chốt tiết kiệm: không đáng thì copy nguyên bản gốc.
            old = src.stat().st_size
            new = reencode_webp_bytes(src, quality)
            if _worth(len(new) if new is not None else None, old, min_save):
                dst.write_bytes(new)
                stats["conv"] += 1
                stats["in"] += old
                stats["out"] += len(new)
            else:
                shutil.copy2(src, dst)     # đã tối ưu / webp-động / lỗi -> giữ nguyên
                stats["kept"] += 1
            return
        # PNG/JPG -> WebP (luôn chuyển, không áp chốt)
        ok, out_size = convert_one(src, dst, quality)
        if ok:
            stats["conv"] += 1
            stats["in"] += src.stat().st_size
            stats["out"] += out_size
        else:
            stats["err"] += 1

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(handle, *j) for j in jobs]
        for f in as_completed(futures):
            f.result()
            done += 1
            if done % 500 == 0 or done == len(jobs):
                print(f"  ... {done}/{len(jobs)} (chuyển {stats['conv']}, "
                      f"giữ {stats['kept']}, copy {stats['copy']}, "
                      f"bỏ qua {stats['skip']}, lỗi {stats['err']})", flush=True)

    if stats["in"]:
        print(f"\nDung lượng phần đã nén: {stats['in']/1e9:.2f} GB -> "
              f"{stats['out']/1e9:.2f} GB (còn {100*stats['out']/stats['in']:.0f}%)")
    print(f"Hoàn tất: chuyển {stats['conv']}, giữ-nguyên {stats['kept']}, "
          f"copy {stats['copy']}, bỏ qua {stats['skip']}, lỗi {stats['err']}.")
    print(f"Cây gốc giữ nguyên. Kết quả ở: {dest_root.resolve()}")


def recompress_in_place(root: Path, quality: int, min_save: int, workers: int):
    """Re-nén MỌI .webp trong `root` (đệ quy) NGAY TẠI CHỖ. An toàn:
      - Nén ra RAM + verify; chỉ THAY khi tiết kiệm >= min_save% (chốt idempotent:
        ảnh đã tối ưu nén lại chỉ nhỏ ~1% -> dưới ngưỡng -> KHÔNG đụng).
      - Ghi ra file .tmp rồi os.replace (thay nguyên tử), lỗi thì bỏ .tmp, giữ gốc.
      - CHỈ đụng .webp; PNG/JPG/marker (.done/.source.json/...) không động tới, nên
        folder giữ nguyên tên + trạng thái -> downloader tải tiếp chương mới bình thường.
    """
    if not root.is_dir():
        print(f"Không tìm thấy thư mục: {root}", file=sys.stderr)
        sys.exit(1)
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".webp"]
    print(f"Nén TẠI CHỖ (sửa thẳng folder gốc): {root.resolve()}")
    print(f"  {len(files)} ảnh .webp | q{quality} | tiết kiệm tối thiểu {min_save}% | "
          f"{workers} luồng\n")

    stats = {"conv": 0, "kept": 0, "skip": 0, "err": 0, "in": 0, "out": 0}

    def handle(p: Path):
        old = p.stat().st_size
        new = reencode_webp_bytes(p, quality)
        if new is None:
            stats["skip"] += 1             # webp-động / không mở được -> để nguyên
            return
        if not _worth(len(new), old, min_save):
            stats["kept"] += 1             # đã tối ưu -> giữ nguyên
            return
        tmp = p.with_suffix(".webp.tmp")
        try:
            tmp.write_bytes(new)
            os.replace(tmp, p)
            stats["conv"] += 1
            stats["in"] += old
            stats["out"] += len(new)
        except Exception as e:
            try:
                tmp.unlink()
            except OSError:
                pass
            stats["err"] += 1
            print(f"  ! Lỗi ghi {p}: {e}", file=sys.stderr)

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(handle, p) for p in files]
        for f in as_completed(futures):
            f.result()
            done += 1
            if done % 500 == 0 or done == len(files):
                print(f"  ... {done}/{len(files)} (nén {stats['conv']}, "
                      f"giữ {stats['kept']}, bỏ qua {stats['skip']}, "
                      f"lỗi {stats['err']})", flush=True)

    if stats["in"]:
        print(f"\nDung lượng phần đã nén: {stats['in']/1e9:.2f} GB -> "
              f"{stats['out']/1e9:.2f} GB (còn {100*stats['out']/stats['in']:.0f}%)")
    print(f"Hoàn tất (TẠI CHỖ): nén {stats['conv']}, giữ-nguyên {stats['kept']}, "
          f"bỏ qua {stats['skip']}, lỗi {stats['err']}.")


def main():
    ap = argparse.ArgumentParser(
        description="Chuyển ảnh PNG sang WebP (xuất *_webp), hoặc re-nén WebP tại chỗ.")
    ap.add_argument("folder", help="Thư mục nguồn")
    ap.add_argument("--quality", type=int, default=85,
                    help="Chất lượng WebP (mặc định 85)")
    ap.add_argument("--jpg-too", action="store_true",
                    help="Nén cả JPG (mặc định chỉ copy nguyên trạng)")
    ap.add_argument("--webp-too", action="store_true",
                    help="RE-NÉN cả WebP về --quality (mặc định copy nguyên trạng). "
                         "Dùng cho ảnh comix.to nén nhẹ tay: q85 giảm ~nửa dung lượng "
                         "mà mắt thường không thấy khác.")
    ap.add_argument("--in-place", action="store_true",
                    help="Re-nén WebP NGAY trong folder gốc (không tạo _webp; chỉ đụng "
                         ".webp). Hợp cho comix.to CŨ: nén xong downloader vẫn tải tiếp "
                         "chương mới vào đúng folder. Ghi đè có temp+verify, an toàn.")
    ap.add_argument("--min-save", type=int, default=MIN_SAVE_DEFAULT,
                    help=f"Chỉ thay bản webp khi bản nén tiết kiệm >= X%% (mặc định "
                         f"{MIN_SAVE_DEFAULT}); dưới mức coi như đã tối ưu, giữ nguyên.")
    ap.add_argument("--workers", type=int, default=8,
                    help="Số luồng xử lý song song (mặc định 8)")
    args = ap.parse_args()
    if args.in_place:
        if args.jpg_too or args.webp_too:
            print("  (lưu ý: --in-place chỉ re-nén .webp; --jpg-too/--webp-too bị bỏ qua)",
                  file=sys.stderr)
        recompress_in_place(Path(args.folder), args.quality, args.min_save, args.workers)
    else:
        convert_tree(Path(args.folder), args.quality, args.jpg_too, args.webp_too,
                     args.min_save, args.workers)


if __name__ == "__main__":
    main()
