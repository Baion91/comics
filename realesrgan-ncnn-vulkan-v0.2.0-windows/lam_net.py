# -*- coding: utf-8 -*-
r"""
Lam net anh truyen scan bang Real-ESRGAN (ncnn / Vulkan).

- Doc anh tu  input\           (anh phang HOAC cac folder chuong con)
- Xuat ra      output-realesrgan\   (giu nguyen cau truc folder chuong)
- Model: realesr-animevideov3  |  Scale 2x  |  Dinh dang PNG  |  Tile 200

Diem manh so voi goi .exe truc tiep:
  * Sort folder chuong theo SO (1,2,3,...,10,...,43.5) thay vi theo chu cai.
  * Hien tien do gon: dang o chuong nao / tong bao nhieu / con lai / anh k/N / ETA.
  * 1 anh loi thi bo qua + ghi log roi chay tiep, khong treo ca bo.

Muon doi tham so: sua cac hang so ngay duoi day.
"""

import os
import re
import sys
import time
import shutil
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ==== Tham so (sua o day neu can) ============================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXE   = os.path.join(SCRIPT_DIR, "realesrgan-ncnn-vulkan.exe")
IN_DIR  = os.path.join(SCRIPT_DIR, "input")
OUT_DIR = os.path.join(SCRIPT_DIR, "output-realesrgan")
MODEL = "realesr-animevideov3"
SCALE = "2"
FORMAT = "png"          # da chot: xuat PNG (khong convert thang sang webp)
TILE = "200"            # co dinh, an toan VRAM 4GB, khong giam chat luong
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
# ============================================================================


def list_images(folder):
    """Danh sach file anh nam TRUC TIEP trong folder (khong de quy)."""
    out = []
    try:
        for name in os.listdir(folder):
            p = os.path.join(folder, name)
            if os.path.isfile(p) and name.lower().endswith(IMG_EXTS):
                out.append(name)
    except OSError:
        pass
    return sorted(out)


def list_subdirs(folder):
    out = []
    try:
        for name in os.listdir(folder):
            if os.path.isdir(os.path.join(folder, name)):
                out.append(name)
    except OSError:
        pass
    return out


def chapter_key(name):
    """Rut so chuong ra khoi ten folder de sort theo SO (ho tro thap phan).
    Vd: 'Chapter 1' -> 1.0, 'Ch. 0.1' -> 0.1, 'Chapter 43.5' -> 43.5.
    Folder khong co so xep cuoi cung, sort theo ten."""
    m = re.search(r"(\d+(?:\.\d+)?)", name)
    if m:
        return (0, float(m.group(1)), name.lower())
    return (1, 0.0, name.lower())


def fmt_eta(seconds):
    if seconds is None or seconds < 0:
        return "?"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"~{h}h{m:02d}m"
    if m > 0:
        return f"~{m}m{s:02d}s"
    return f"~{s}s"


def term_width():
    try:
        return shutil.get_terminal_size((100, 20)).columns
    except Exception:
        return 100


def draw_line(text):
    """Ve 1 dong tien do, dem khoang trang cho het be rong -> khong bi giat,
    khong sot ky tu cua dong dai truoc, khong xuong hang lam lech \\r."""
    w = max(20, term_width() - 1)
    sys.stdout.write("\r" + text[:w].ljust(w))
    sys.stdout.flush()


def clear_line():
    w = max(20, term_width() - 1)
    sys.stdout.write("\r" + " " * w + "\r")
    sys.stdout.flush()


def build_groups():
    """Tra ve list nhom can xu ly, THU TU: cac chuong (sort so) roi anh le."""
    groups = []
    for sub in sorted(list_subdirs(IN_DIR), key=chapter_key):
        imgs = list_images(os.path.join(IN_DIR, sub))
        if imgs:
            groups.append({
                "label": sub,
                "in": os.path.join(IN_DIR, sub),
                "out": os.path.join(OUT_DIR, sub),
                "imgs": imgs,
            })
    flat = list_images(IN_DIR)
    if flat:
        groups.append({
            "label": "(anh le)",
            "in": IN_DIR,
            "out": OUT_DIR,
            "imgs": flat,
        })
    return groups


def expected_out_name(img_name):
    """Ten file output tuong ung 1 anh input (doi duoi sang FORMAT)."""
    return os.path.splitext(img_name)[0] + "." + FORMAT


def is_done(g):
    """True neu MOI anh input cua nhom deu da co file output tuong ung."""
    if not os.path.isdir(g["out"]):
        return False
    have = {n.lower() for n in os.listdir(g["out"])}
    for name in g["imgs"]:
        if expected_out_name(name).lower() not in have:
            return False
    return True


def count_done_outputs(g, since_ts):
    """Dem so ANH cua nhom da co file output that su (mtime >= since_ts).
    Chi xet dung cac output ky vong cua nhom -> bo qua file rac; dung mtime
    de dung ca khi lam lai (--force) / chuong lam do co file cu san."""
    done = 0
    for name in g["imgs"]:
        p = os.path.join(g["out"], expected_out_name(name))
        try:
            if os.path.getmtime(p) >= since_ts:
                done += 1
        except OSError:
            pass
    return done


def process_group(g, gi, total_groups, total_imgs, overall_done, start_ts):
    """Chay exe cho 1 nhom, ve tien do 1 dong. Tra ve (successes, failures).
    Tien do do bang SO FILE OUTPUT sinh ra (poll ~0.3s) -> chinh xac ke ca khi
    exe chay da luong, va bo qua hoan toan file .done/.json (khong phai anh)."""
    n = len(g["imgs"])
    os.makedirs(g["out"], exist_ok=True)
    since = time.time() - 2.0   # tru 2s tranh sai lech lam tron mtime

    cmd = [EXE, "-i", g["in"], "-o", g["out"],
           "-n", MODEL, "-s", SCALE, "-f", FORMAT, "-t", TILE]
    proc = subprocess.Popen(
        cmd, cwd=SCRIPT_DIR,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    cur = 0

    def render():
        done_live = overall_done + cur
        elapsed = time.time() - start_ts
        eta = None
        if done_live > 0 and elapsed > 1:
            rate = done_live / elapsed
            if rate > 0:
                eta = (total_imgs - done_live) / rate
        draw_line(f"[Chuong {gi}/{total_groups}] {g['label']}  |  "
                  f"anh {cur}/{n}  |  tong {done_live}/{total_imgs}  |  "
                  f"ETA {fmt_eta(eta)}")

    render()
    while proc.poll() is None:
        time.sleep(0.3)
        cur = count_done_outputs(g, since)
        render()
    cur = count_done_outputs(g, since)   # dem lan cuoi sau khi exe xong
    render()

    successes = cur
    failures = n - successes
    clear_line()
    tick = "x" if failures else "v"
    tail = f" ({failures} loi)" if failures else ""
    print(f"[{tick}] [{gi}/{total_groups}] {g['label']} - {successes}/{n} anh{tail}")
    return successes, failures


def main():
    if not os.path.isfile(EXE):
        print(f"[LOI] Khong thay {EXE}")
        return 1
    os.makedirs(IN_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    force = any(a in ("--force", "--lam-lai") for a in sys.argv[1:])

    groups = build_groups()
    if not groups:
        print("Khong co anh nao trong 'input\\'.")
        print("  -> Bo anh phang vao input\\, HOAC copy cac folder chuong vao input\\ roi chay lai.")
        return 0

    # Bo qua chuong da xong (du output), tru khi chay che do lam lai (--force).
    if force:
        todo, skipped = groups, []
    else:
        todo = [g for g in groups if not is_done(g)]
        skipped = [g for g in groups if is_done(g)]

    total_groups = len(todo)
    total_imgs = sum(len(g["imgs"]) for g in todo)

    print("=" * 60)
    print("  Real-ESRGAN - Lam net anh truyen" + ("  [LAM LAI TOAN BO]" if force else ""))
    print(f"  Model: {MODEL}  |  {SCALE}x  |  {FORMAT}  |  tile {TILE}")
    msg = f"  Can xu ly: {total_groups} chuong  /  {total_imgs} anh"
    if skipped:
        msg += f"   (bo qua {len(skipped)} chuong da xong)"
    print(msg)
    print("=" * 60)

    if not todo:
        print("Tat ca chuong deu da xong -> khong co gi de lam.")
        print("(Muon lam lai tu dau: chay lai va chon 'y' o cau hoi dau.)")
        print(f"Ket qua nam trong: {OUT_DIR}")
        return 0

    start_ts = time.time()
    overall_done = 0
    overall_fail = 0
    fail_groups = []

    for gi, g in enumerate(todo, 1):
        s, f = process_group(g, gi, total_groups, total_imgs, overall_done, start_ts)
        overall_done += s
        overall_fail += f
        if f:
            fail_groups.append((g["label"], f))

    elapsed = time.time() - start_ts
    print("-" * 60)
    tail = f"  (bo qua {len(skipped)} chuong da xong)" if skipped else ""
    print(f"XONG {total_groups} chuong / {overall_done}/{total_imgs} anh "
          f"({overall_fail} loi) trong {fmt_eta(elapsed)}{tail}")
    if fail_groups:
        print("Cac chuong co anh loi (nen kiem tra lai):")
        for label, f in fail_groups:
            print(f"  - {label}: {f} anh loi")
    print(f"Ket qua nam trong: {OUT_DIR}")
    return 1 if overall_fail else 0


if __name__ == "__main__":
    sys.exit(main())
