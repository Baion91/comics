#!/usr/bin/env python3
"""Kiểm tra ảnh ĐÃ TẢI trong thư viện — quét lại đống cũ + khám định kỳ.

Bổ trợ cho kiểm-tra-lúc-tải (nằm trong comics_core): downloader chặn ảnh hỏng
từ lúc tải, còn tool này soi những gì ĐÃ nằm trên đĩa (tải trước khi có kiểm tra,
hoặc hỏng về sau). Dùng CHUNG lõi kiểm tra với downloader nên không lệch nhau.

Làm gì:
  - MẶC ĐỊNH: giải mã thử từng ảnh (bắt cụt/hỏng/không-phải-ảnh) + soát khuyết trang.
    Chạy nhiều luồng, ghi nhớ ảnh tốt (cache) nên lần sau chỉ soi cái mới -> nhanh.
  - `--black`: THÊM dò 'trang một màu' (cả khung đen/trắng/xám phẳng = vô nội dung).
    Chỉ BÁO, không tự xóa. Rất hiếm; là cách duy nhất tách chắc ảnh đen thật khỏi
    tranh đen do tác giả vẽ (tranh vẽ luôn có nét -> lọt). Đây là lượt QUÉT SÂU:
    bỏ qua cache (giải mã lại tất cả) nên chậm — dùng khi cố ý săn ảnh một-màu.

Trạng thái sống ở ĐĨA: ảnh chắc chắn hỏng được cách ly bằng đổi tên .bad (reader
tự ẩn; chạy lại lệnh tải là tự tải bù, xong tự xóa .bad).

Cách dùng:
  python check_library.py                       # quét cả downloads/ (nhanh)
  python check_library.py "downloads\\Tên bộ"   # chỉ 1 bộ
  python check_library.py --fix                 # cách ly (.bad) ảnh chắc chắn hỏng
  python check_library.py --black               # thêm dò trang một màu (quét sâu, chậm)
  python check_library.py --recheck             # bỏ cache, kiểm lại toàn bộ
  python check_library.py --workers 4           # số luồng (mặc định = số nhân, tối đa 8)

Kết quả: tóm tắt ở console + báo cáo .reader-meta\\check-report.html (mở bằng
trình duyệt, có ảnh thu nhỏ) + check-report.json. Ảnh 'một màu' đã xác nhận là
bình thường thì thêm đường-dẫn vào .reader-meta\\check-ignore.txt để thôi báo.
"""

import argparse
import base64
import html as html_mod
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from comics_core import (IMG_EXTS, META_DIR, Image, bad_marker, compact_ints,
                         inspect_image_bytes, load_issues, looks_scrambled_bytes)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

DOWNLOADS = Path(__file__).resolve().parent / "downloads"
CACHE_FILE = META_DIR / "check-cache.json"      # {abspath: [mtime, size]} ảnh đã kiểm tốt
IGNORE_FILE = META_DIR / "check-ignore.txt"     # đường dẫn (rel downloads) một-màu đã duyệt là OK
REPORT_JSON = META_DIR / "check-report.json"
REPORT_HTML = META_DIR / "check-report.html"
RECENT_SECS = 5                                 # bỏ qua file vừa sửa (có thể đang tải dở)
FLUSH_EVERY = 1000                              # ghi cache mỗi N ảnh (chống mất tiến độ)


def load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(cache: dict):
    META_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache), encoding="utf-8")
    tmp.replace(CACHE_FILE)  # ghi nguyên tử: Ctrl-C giữa chừng không hỏng cache


def load_ignore() -> set:
    try:
        return {ln.strip() for ln in IGNORE_FILE.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#")}
    except OSError:
        return set()


def rel_key(path: Path) -> str:
    """Đường dẫn tương đối so với downloads/ (khóa cho ignore-list, dễ đọc & di động)."""
    try:
        return str(path.resolve().relative_to(DOWNLOADS)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def page_number(stem: str):
    """Số trang từ tên file: '001'->1, '028 page 18'->28. None nếu không mở đầu bằng số."""
    m = re.match(r"(\d+)", stem)
    return int(m.group(1)) if m else None


def fmt_eta(secs: float) -> str:
    secs = int(secs)
    return f"{secs // 60}:{secs % 60:02d}" if secs >= 60 else f"{secs}s"


def thumb_data_uri(path: Path, max_w=240) -> str:
    """Ảnh thu nhỏ base64 để nhúng thẳng vào HTML (xem trang một-màu tận mắt)."""
    if Image is None:
        return ""
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            if im.width > max_w:
                im = im.resize((max_w, round(im.height * max_w / im.width)))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=70)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def collect(scan_root: Path, cache: dict, use_cache: bool):
    """Đi cây 1 lượt: dựng danh sách folder (kèm trang có mặt / .bad) + job cần kiểm.

    Trả (folders, jobs, total_imgs). Job = (fidx, name, fp, key, mtime, size)."""
    folders, jobs, total_imgs = [], [], 0
    now = time.time()
    for dirpath, dirnames, filenames in os.walk(scan_root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))  # bỏ .reader-meta, .backup...
        imgs = sorted(f for f in filenames if Path(f).suffix.lower() in IMG_EXTS)
        if not imgs:
            continue
        folder = Path(dirpath)
        fidx = len(folders)
        present, quarantined = [], sorted(f for f in filenames if f.endswith(".bad"))
        total_imgs += len(imgs)
        for name in imgs:
            stem = Path(name).stem
            n = page_number(stem)
            if n is not None and stem.lower() != "cover":
                present.append(n)
            fp = folder / name
            try:
                st = fp.stat()
            except OSError:
                continue
            if now - st.st_mtime < RECENT_SECS:
                continue  # có thể đang tải dở -> đừng báo cụt oan
            key = str(fp.resolve())
            if use_cache and cache.get(key) == [st.st_mtime, st.st_size]:
                continue  # đã kiểm 'tốt' trước đó -> bỏ qua cho nhanh
            jobs.append((fidx, name, fp, key, st.st_mtime, st.st_size))
        folders.append({"folder": folder, "rel": rel_key(folder), "imgs": imgs,
                        "present": present, "quarantined": quarantined,
                        "bad": [], "suspect": [], "unsupported": [], "salvaged": [],
                        "scrambled": []})
    return folders, jobs, total_imgs


def write_html(report: dict):
    e = html_mod.escape
    rows = []
    for r in report["results"]:
        parts = [f"<h3>{e(r['folder'])} <small>({r['images']} ảnh)</small></h3>"]
        if r["gaps"]:
            parts.append(f"<p class='gap'>◻ Khuyết trang: <b>{e(compact_ints(r['gaps']))}"
                         f"</b> → tải lại chương này.</p>")
        if r.get("known_gaps"):
            parts.append(f"<p class='known'>✓ Khuyết trang <b>{e(compact_ints(r['known_gaps']))}"
                         f"</b> — đã biết: ảnh hỏng sẵn ở nguồn, tải lại vô ích. Không cần làm gì.</p>")
        for x in r.get("salvaged", []):
            pct = f"{x['intact'] * 100:.0f}%" if x.get("intact") else "phần lớn"
            parts.append(f"<p class='known'>◐ <b>{e(x['file'])}</b> — ảnh hỏng ở nguồn, "
                         f"đã cứu vớt (đọc được {e(pct)}). Giữ nguyên, không cách ly.</p>")
        if r.get("scrambled"):
            files = ", ".join(e(x["file"]) for x in r["scrambled"])
            parts.append(f"<p class='bad'>🧩 Nghi TRÁO Ô (comix official chèn mỗi trang "
                         f"thứ 10): <b>{files}</b> → chạy "
                         f"<code>comic_downloader.py &lt;url&gt; --repair-scramble</code> "
                         f"để tự giải-xáo lại.</p>")
        if r["quarantined"]:
            parts.append("<p class='bad'>⛔ Đang cách ly (chờ tải bù): "
                         + ", ".join(e(x) for x in r["quarantined"]) + "</p>")
        for x in r["bad"]:
            parts.append(f"<p class='bad'>✗ <b>{e(x['file'])}</b> — {e(x['reason'])}: "
                         f"{e(x['detail'])}{'  ['+e(x['action'])+']' if x.get('action') else ''}</p>")
        for x in r["unsupported"]:
            parts.append(f"<p class='warn'>? <b>{e(x['file'])}</b> — {e(x['detail'])} "
                         f"(chưa kết luận được)</p>")
        for x in r["suspect"]:
            thumb = f"<img src='{x['thumb']}'>" if x.get("thumb") else ""
            parts.append(f"<div class='suspect'>{thumb}<div>⚑ <b>{e(x['file'])}</b> — "
                         f"{e(x['label'])}<br><small>{e(x['detail'])}</small><br>"
                         f"<small class='hint'>Nếu là trang bình thường (đen/trắng có chủ ý): "
                         f"thêm dòng <code>{e(r['folder'])}/{e(x['file'])}</code> vào "
                         f"check-ignore.txt để thôi báo.</small></div></div>")
        rows.append("<section>" + "".join(parts) + "</section>")

    t = report["totals"]
    summary = (f"Quét lúc {e(report['scanned_at'])} · phạm vi <code>{e(report['scope'])}</code> "
               f"· {'CÓ' if report['black'] else 'KHÔNG'} dò trang-một-màu<br>"
               f"{t['images']} ảnh · {t['bad']} hỏng · {t['gaps']} chương khuyết trang · "
               f"{t['suspect']} trang một màu · {t.get('scrambled', 0)} trang tráo ô · "
               f"{t['unsupported']} chưa kiểm được"
               + (f" · đã cách ly {t['fixed']}" if t['fixed'] else "")
               + (f" · {t.get('salvaged', 0)} ảnh cứu vớt" if t.get('salvaged') else "")
               + (f" · {t.get('known_gaps', 0)} khuyết trang đã biết"
                  if t.get('known_gaps') else ""))
    body = "".join(rows) or "<p class='ok'>✓ Không phát hiện vấn đề trong phạm vi quét.</p>"
    css = ("body{font:15px/1.5 system-ui,Segoe UI,sans-serif;max-width:900px;margin:24px auto;"
           "padding:0 16px;color:#222}h1{font-size:20px}section{border:1px solid #e3e3e3;"
           "border-radius:10px;padding:8px 16px;margin:14px 0}h3{margin:.5em 0}.bad{color:#b00}"
           ".gap{color:#a35a00}.warn{color:#7a6a00}.ok{color:#0a7a2f;font-size:17px}"
           ".known{color:#5a6570}"
           ".suspect{display:flex;gap:12px;align-items:flex-start;background:#faf7ef;"
           "border-radius:8px;padding:8px;margin:8px 0}.suspect img{width:120px;height:auto;"
           "border:1px solid #ccc;border-radius:4px}.hint{color:#666}code{background:#f0f0f0;"
           "padding:1px 4px;border-radius:4px}small{color:#555}"
           "@media(prefers-color-scheme:dark){body{background:#1b1b1b;color:#ddd}"
           "section{border-color:#333}.suspect{background:#242017}code{background:#333}"
           "small{color:#aaa}}")
    doc = (f"<!doctype html><meta charset='utf-8'><title>Kiểm tra thư viện truyện</title>"
           f"<style>{css}</style><h1>Kiểm tra thư viện truyện</h1><p>{summary}</p>{body}")
    META_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_HTML.write_text(doc, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Kiểm tra ảnh đã tải (hỏng/cụt/thiếu/một-màu).")
    ap.add_argument("path", nargs="?", help="Thư mục cần quét (mặc định: cả downloads/)")
    ap.add_argument("--fix", action="store_true",
                    help="Cách ly ảnh CHẮC CHẮN hỏng bằng đổi tên .bad (mặc định chỉ báo)")
    ap.add_argument("--black", action="store_true",
                    help="Thêm dò 'trang một màu' (quét sâu, bỏ cache -> chậm)")
    ap.add_argument("--recheck", action="store_true", help="Bỏ cache, kiểm lại toàn bộ")
    ap.add_argument("--workers", type=int, default=0,
                    help="Số luồng (mặc định = số nhân CPU, tối đa 8)")
    args = ap.parse_args()

    scan_root = Path(args.path).resolve() if args.path else DOWNLOADS
    if not scan_root.is_dir():
        sys.exit(f"Không tìm thấy thư mục: {scan_root}")
    if Image is None:
        print("! Không có Pillow — chỉ kiểm được chữ ký (magic), bỏ giải mã & dò một-màu.\n",
              file=sys.stderr)
    workers = args.workers if args.workers > 0 else min(8, os.cpu_count() or 4)
    # --black là lượt quét sâu: bỏ đọc cache để giải mã lại & kiểm một-màu mọi ảnh.
    use_cache_read = not (args.recheck or args.black)

    # LUÔN nạp cache cũ: --recheck chỉ có nghĩa "đừng TIN cache khi quét" (use_cache_read),
    # KHÔNG được xóa sổ cache. Trước đây bắt đầu bằng {} nên quét --recheck một chương lại
    # ghi đè cache toàn thư viện chỉ còn mấy mục -> lần quét sau phải giải mã lại từ đầu.
    cache = load_cache()
    ignore = load_ignore()
    issues = load_issues()
    salvaged = issues.get("salvaged", {})
    # trang đã biết hỏng-tại-nguồn, gom theo folder -> khuyết trang do nó là 'đã biết'
    broken_by_folder = {}
    for k in issues.get("source_broken", {}):
        p = Path(k)
        n = page_number(p.stem)
        if n is not None:
            broken_by_folder.setdefault(p.parent, set()).add(n)
    stats = {"images": 0, "bad": 0, "gaps": 0, "suspect": 0, "unsupported": 0,
             "fixed": 0, "salvaged": 0, "known_gaps": 0, "scrambled": 0}

    folders, jobs, total_imgs = collect(scan_root, cache, use_cache_read)
    stats["images"] = total_imgs
    print(f"Quét: {scan_root}")
    print(f"  {len(folders)} folder · {total_imgs} ảnh · cần kiểm {len(jobs)} "
          f"({total_imgs - len(jobs)} đã trong cache) · {workers} luồng"
          + ("  · CÓ dò trang-một-màu (quét sâu)" if args.black else "") + "\n")

    def work(job):
        fidx, name, fp, key, mt, sz = job
        try:
            data = fp.read_bytes()
        except OSError as ex:
            return (fidx, name, fp, key, mt, sz, "unreadable", str(ex), None, False)
        v, d, u = inspect_image_bytes(data, want_uniform=args.black)
        # ảnh giải mã OK vẫn có thể bị TRÁO Ô (comix official chèn mỗi trang thứ 10) —
        # magic/decode không bắt được; dò 'năng lượng đường nối'. Xem comics_core.looks_scrambled.
        sc = (v == "ok") and looks_scrambled_bytes(data)
        return (fidx, name, fp, key, mt, sz, v, d, u, sc)

    start = time.time()
    done = last_flush = 0
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(work, j) for j in jobs]
            for fut in as_completed(futures):
                fidx, name, fp, key, mt, sz, v, d, u, sc = fut.result()
                fe = folders[fidx]
                if v in ("empty", "not_image", "corrupt", "unreadable") \
                        and str(fp.resolve()) in salvaged:
                    # Ảnh cụt nhưng đã CỨU VỚT có chủ ý (nguồn hỏng) — đã biết, đừng
                    # báo hỏng lại và TUYỆT ĐỐI không cách ly, kẻo mất phần đọc được.
                    info = salvaged[str(fp.resolve())]
                    fe["salvaged"].append({"file": name, "detail": d,
                                           "intact": info.get("intact")})
                    stats["salvaged"] += 1
                elif v in ("empty", "not_image", "corrupt", "unreadable"):
                    entry = {"file": name, "reason": v, "detail": d}
                    if args.fix and v != "unreadable":
                        try:
                            fp.rename(bad_marker(fp))
                            entry["action"] = "đã cách ly -> " + name + ".bad"
                            stats["fixed"] += 1
                        except OSError as ex:
                            entry["action"] = f"cách ly lỗi: {ex}"
                    fe["bad"].append(entry)
                    stats["bad"] += 1
                elif v == "unsupported":
                    fe["unsupported"].append({"file": name, "detail": d})
                    stats["unsupported"] += 1
                elif sc and rel_key(fp) not in ignore:      # v == "ok" nhưng bị TRÁO Ô
                    fe["scrambled"].append({"file": name, "thumb": thumb_data_uri(fp)})
                    stats["scrambled"] += 1
                    # KHÔNG cache 'tốt' -> vẫn báo tới khi sửa (comic_downloader --repair-scramble)
                elif u and rel_key(fp) not in ignore:      # v == "ok", có cờ một-màu
                    fe["suspect"].append({"file": name, "label": u[0], "detail": u[1],
                                          "thumb": thumb_data_uri(fp)})
                    stats["suspect"] += 1
                else:                                       # sạch -> ghi nhớ
                    cache[key] = [mt, sz]

                done += 1
                if done % 20 == 0 or done == len(jobs):
                    el = time.time() - start
                    eta = (len(jobs) - done) * el / done if done else 0
                    bar = f"[{done}/{len(jobs)} · {done * 100 // max(len(jobs), 1)}% · còn ~{fmt_eta(eta)}]"
                    print(("\r" + bar + " " + fe["rel"])[:110].ljust(112), end="", flush=True)
                if done - last_flush >= FLUSH_EVERY:
                    save_cache(cache)
                    last_flush = done
        print("\r" + " " * 112 + "\r", end="")
    except KeyboardInterrupt:
        save_cache(cache)
        print("\n\n! Đã dừng giữa chừng. Ảnh đã kiểm tốt đã lưu vào cache — "
              "chạy lại lệnh này để tiếp tục chỗ dở (không quét lại từ đầu).", file=sys.stderr)
        raise SystemExit(130)
    save_cache(cache)

    # gộp kết quả: khuyết trang tính từ số trang có mặt; chỉ giữ folder có vấn đề
    results = []
    for fe in folders:
        gaps = []
        if fe["present"]:
            gaps = sorted(set(range(min(fe["present"]), max(fe["present"]) + 1)) - set(fe["present"]))
        # khuyết do ảnh hỏng sẵn ở nguồn = 'đã biết', không phải việc cần làm
        known = broken_by_folder.get(fe["folder"].resolve(), set())
        known_gaps = [g for g in gaps if g in known]
        gaps = [g for g in gaps if g not in known]
        if gaps:
            stats["gaps"] += 1
        if known_gaps:
            stats["known_gaps"] += len(known_gaps)
        if (fe["bad"] or fe["suspect"] or fe["unsupported"] or gaps or fe["quarantined"]
                or fe["salvaged"] or known_gaps or fe["scrambled"]):
            results.append({"folder": fe["rel"], "images": len(fe["imgs"]), "gaps": gaps,
                            "known_gaps": known_gaps, "bad": fe["bad"],
                            "quarantined": fe["quarantined"], "suspect": fe["suspect"],
                            "unsupported": fe["unsupported"], "salvaged": fe["salvaged"],
                            "scrambled": fe["scrambled"]})

    report = {"scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              "scope": rel_key(scan_root), "black": args.black, "totals": stats,
              "results": results}
    META_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    write_html(report)

    # Tóm tắt console
    el = time.time() - start
    print(f"Đã kiểm {stats['images']} ảnh trong {fmt_eta(el)}.")
    if not results:
        print("✓ Không phát hiện vấn đề.")
    else:
        for r in results:
            bits = []
            if r["gaps"]:
                bits.append(f"khuyết trang {compact_ints(r['gaps'])}")
            if r["bad"]:
                bits.append(f"{len(r['bad'])} hỏng")
            if r["quarantined"]:
                bits.append(f"{len(r['quarantined'])} đang cách ly")
            if r["suspect"]:
                bits.append(f"{len(r['suspect'])} trang một màu")
            if r.get("scrambled"):
                bits.append(f"{len(r['scrambled'])} trang tráo ô")
            if r["unsupported"]:
                bits.append(f"{len(r['unsupported'])} chưa kiểm được")
            if r.get("salvaged"):
                bits.append(f"{len(r['salvaged'])} ảnh cứu vớt (đã biết)")
            if r.get("known_gaps"):
                bits.append(f"khuyết trang {compact_ints(r['known_gaps'])} do nguồn hỏng (đã biết)")
            print(f"  • {r['folder']}: " + "; ".join(bits))
        print(f"\nTổng: {stats['bad']} hỏng, {stats['gaps']} chương khuyết trang, "
              f"{stats['suspect']} trang một màu"
              + (f", đã cách ly {stats['fixed']}" if stats["fixed"] else "")
              + (".  Dùng --fix để cách ly ảnh hỏng." if stats["bad"] and not args.fix else "."))
    print(f"\nBáo cáo: {REPORT_HTML}")
    print("        (mở bằng trình duyệt để xem ảnh tận mắt)")
    if stats["bad"] or stats["gaps"]:
        print("→ Sau khi cách ly, chạy lại lệnh tải bộ đó để tự tải bù các trang thiếu.")
    if stats.get("scrambled"):
        print(f"→ {stats['scrambled']} trang TRÁO Ô (comix): chạy "
              "'comic_downloader.py <url> --repair-scramble' để tự giải-xáo lại.")


if __name__ == "__main__":
    main()
