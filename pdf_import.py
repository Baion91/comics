#!/usr/bin/env python3
"""Nhập truyện dạng PDF vào thư viện: mỗi file PDF -> 1 thư mục chương "Tập NN" chứa ảnh.

Reader chỉ hiểu "chương = thư mục ảnh", nên PDF phải tách ra một lần. Chỉ nhận loại PDF
"vỏ bọc ảnh": mỗi trang là ĐÚNG 1 ảnh JPEG phủ kín trang (bản scan/ghép ảnh thường gặp).
Khi đó bytes JPEG trong PDF được chép NGUYÊN TRẠNG ra `001.jpg, 002.jpg...` — không giải
mã/nén lại, không mất chất lượng, dung lượng ≈ PDF. Trang khác loại (có chữ/vector, ảnh nén
kiểu khác, nhiều ảnh ghép, xoay, trong suốt, CMYK...) -> DỪNG file đó + báo trang nào, không
đụng gì (chưa có bộ dựng trang — thêm khi thật sự gặp).

Đặt PDF THẲNG trong folder truyện:
  downloads/Doraemon truyện dài/Long 1 LITE.pdf
    -> downloads/Doraemon truyện dài/Tập 01/001.jpg ... 189.jpg
    -> PDF gốc chuyển vào downloads/Doraemon truyện dài/.pdf-goc/ (reader + check_library
       bỏ qua thư mục chấm-đầu; đọc thử thấy ổn thì tự tay xoá).
Số tập lấy theo chữ Tập/Vol/Chương/Chapter/Ch/# trong tên file, không có thì số ĐẦU TIÊN
("Long 1 LITE" -> Tập 01, "Long DoremonVoz Vol.07 (lite)" -> Tập 07). Tên file không có số
-> báo lỗi, đổi tên file rồi chạy lại.

An toàn: ghi vào `downloads/.pdf-tmp/` (reader không quét) + kiểm từng ảnh giải mã được, đủ
trang rồi mới đổi tên sang thư mục thật -> reader không bao giờ thấy chương dở. Thư mục
"Tập NN" đã có: giống hệt nội dung PDF (lần trước tách xong mà chưa kịp cất PDF) -> chỉ cất
PDF; khác -> bỏ qua, không ghi đè.

Cách dùng:
  python pdf_import.py                                   # tìm PDF trong cả downloads/
  python pdf_import.py "downloads\\Doraemon truyện dài"   # 1 folder (tìm cả folder con)
  python pdf_import.py "...\\Long 1 LITE.pdf"             # 1 file
  python pdf_import.py ... --dry-run                     # chỉ kiểm + in kế hoạch, không ghi
Hoặc bấm `Nhap PDF.bat` (kéo-thả file/folder vào cũng được).

Exit: 0 = ổn hết, 1 = có file lỗi/bỏ qua, 2 = không thấy PDF nào. Cần `pypdf` (thuần Python).
"""

import argparse
import io
import os
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

from comics_core import Image, check_image_bytes

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

DOWNLOADS = Path(__file__).resolve().parent / "downloads"
ORIG_DIR = ".pdf-goc"       # nơi cất PDF gốc, trong folder truyện
TMP_DIR = ".pdf-tmp"        # nơi ghi dở, ở gốc downloads/ (reader bỏ qua folder chấm-đầu)

# Số tập: ưu tiên số đứng sau từ khoá, không có thì số đầu tiên trong tên.
NUM_KEY_RE = re.compile(
    r"\b(?:tập|tap|vol(?:ume)?|quyển|quyen|chương|chuong|chapter|chap|ch)\.?\s*(\d+(?:\.\d+)?)"
    r"|#\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
NUM_RE = re.compile(r"\d+(?:\.\d+)?")

# Toán tử content stream được phép trên trang "1 ảnh": lưu/khôi phục trạng thái, ma trận,
# vẽ XObject, ExtGState, tham số nét + màu (không ảnh hưởng ảnh RGB/xám). Gặp lệnh khác
# (chữ BT, đường vẽ re/f, ảnh inline, shading...) = trang không thuần ảnh.
SIMPLE_OPS = {b"q", b"Q", b"cm", b"Do", b"gs", b"w", b"J", b"j", b"M", b"d", b"ri", b"i",
              b"g", b"G", b"rg", b"RG", b"k", b"K", b"cs", b"CS", b"sc", b"SC", b"scn", b"SCN"}


class NotSimple(Exception):
    """Trang không phải "đúng 1 ảnh JPEG phủ kín trang" — lý do nằm trong message."""


def chapter_name(stem):
    """'Long 1 LITE' -> 'Tập 01', 'X Vol.07 (lite)' -> 'Tập 07', '... 7.5' -> 'Tập 07.5'.
    None nếu tên không có số."""
    s = unicodedata.normalize("NFC", stem)
    m = NUM_KEY_RE.search(s)
    num = (m.group(1) or m.group(2)) if m else None
    if num is None:
        m = NUM_RE.search(s)
        num = m.group(0) if m else None
    if num is None:
        return None
    whole, _, frac = num.partition(".")
    frac = frac.rstrip("0")
    return f"Tập {int(whole):02d}" + (f".{frac}" if frac else "")


def _mul(m, n):
    """Nhân ma trận PDF [a b c d e f]: m × n (lệnh `cm` m đặt CTM = m × CTM)."""
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + b * C, a * B + b * D,
            c * A + d * C, c * B + d * D,
            e * A + f * C + E, e * B + f * D + F)


def _names(v):
    """/Filter, /BM... có thể là 1 tên hoặc mảng tên -> list[str]."""
    if v is None:
        return []
    v = v.get_object() if hasattr(v, "get_object") else v
    return [str(x) for x in v] if isinstance(v, (list, tuple)) else [str(v)]


def _check_gs(gsd):
    gsd = gsd.get_object()
    sm = gsd.get("/SMask")
    if sm is not None and str(sm) != "/None":
        raise NotSimple("ExtGState có soft mask")
    for k in ("/ca", "/CA"):
        if k in gsd and float(gsd[k]) < 0.999:
            raise NotSimple("ảnh vẽ bán trong suốt")
    bm = _names(gsd.get("/BM"))
    if bm and bm[0] not in ("/Normal", "/Compatible"):
        raise NotSimple(f"chế độ hoà trộn {bm[0]}")


def _check_colorspace(img, warns):
    cs = img.get("/ColorSpace")
    cs = cs.get_object() if hasattr(cs, "get_object") else cs
    if cs is None or str(cs) in ("/DeviceRGB", "/DeviceGray"):
        return
    if isinstance(cs, (list, tuple)) and cs and str(cs[0]) == "/ICCBased":
        prof = cs[1].get_object()
        n = int(prof.get("/N", 0))
        if n not in (1, 3):
            raise NotSimple(f"hồ sơ màu ICC {n} kênh (CMYK?)")
        if n == 3 and b"sRGB" not in prof.get_data()[:4096]:
            warns.add("hồ sơ màu ICC không phải sRGB — trình duyệt hiểu là sRGB, màu có thể lệch nhẹ")
        return
    raise NotSimple(f"không gian màu {cs if not isinstance(cs, (list, tuple)) else cs[0]}")


def page_jpeg(page, warns):
    """Bytes JPEG của trang nếu trang = ĐÚNG 1 ảnh JPEG phủ kín vùng hiển thị (crop box);
    không thì ném NotSimple. Bytes là nguyên stream DCTDecode trong PDF = 1 file JPEG."""
    if page.rotation % 360:
        raise NotSimple(f"trang xoay {page.rotation}°")
    res = page.get("/Resources")
    res = res.get_object() if res is not None else {}
    xobjs = res.get("/XObject")
    xobjs = xobjs.get_object() if xobjs is not None else {}
    gstates = res.get("/ExtGState")
    gstates = gstates.get_object() if gstates is not None else {}

    contents = page.get_contents()
    ops = contents.operations if contents is not None else []
    ctm, stack, drawn = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), [], []
    for operands, op in ops:
        if op not in SIMPLE_OPS:
            raise NotSimple(f"có lệnh vẽ ngoài ảnh ({op.decode('latin-1')}: chữ/vector)")
        if op == b"q":
            stack.append(ctm)
        elif op == b"Q":
            ctm = stack.pop() if stack else ctm
        elif op == b"cm":
            ctm = _mul(tuple(float(x) for x in operands), ctm)
        elif op == b"gs":
            if operands[0] not in gstates:
                raise NotSimple(f"thiếu ExtGState {operands[0]}")
            _check_gs(gstates[operands[0]])
        elif op == b"Do":
            drawn.append((operands[0], ctm))
    if len(drawn) != 1:
        raise NotSimple(f"vẽ {len(drawn)} đối tượng (cần đúng 1 ảnh)")
    name, (a, b, c, d, e, f) = drawn[0]
    if name not in xobjs:
        raise NotSimple(f"thiếu XObject {name}")
    img = xobjs[name].get_object()
    if str(img.get("/Subtype")) != "/Image":
        raise NotSimple("đối tượng vẽ không phải ảnh (form XObject)")
    filters = _names(img.get("/Filter"))
    if filters != ["/DCTDecode"]:
        raise NotSimple(f"ảnh nén {'+'.join(filters) or 'thô'} (không phải JPEG)")
    for k in ("/Decode", "/Mask", "/ImageMask"):
        if k in img:
            raise NotSimple(f"ảnh có {k}")
    _check_colorspace(img, warns)
    sm = img.get("/SMask")
    if sm is not None:
        sm = sm.get_object()
        if int(sm.get("/BitsPerComponent", 8)) != 8 or "/Decode" in sm:
            raise NotSimple("lớp trong suốt (SMask) kiểu lạ")
        if sm.get_data().strip(b"\xff"):
            raise NotSimple("ảnh có vùng trong suốt")
    W, H = int(img["/Width"]), int(img["/Height"])

    # Hình học: ảnh không xoay/lật/nghiêng, phủ kín vùng hiển thị (lệch ≤ 0.5%, tối thiểu
    # 2pt — vd crop box 1527.81×2399.7 trên ảnh 1528×2400), không bị kéo méo tỉ lệ.
    if abs(b) > 1e-3 * max(abs(a), abs(d)) or abs(c) > 1e-3 * max(abs(a), abs(d)):
        raise NotSimple("ảnh bị xoay/nghiêng")
    if a <= 0 or d <= 0:
        raise NotSimple("ảnh bị lật")
    mb, cb = page.mediabox, page.cropbox
    vx0, vy0 = max(float(mb.left), float(cb.left)), max(float(mb.bottom), float(cb.bottom))
    vx1, vy1 = min(float(mb.right), float(cb.right)), min(float(mb.top), float(cb.top))
    tx, ty = max(2.0, 0.005 * (vx1 - vx0)), max(2.0, 0.005 * (vy1 - vy0))
    if (abs(e - vx0) > tx or abs(e + a - vx1) > tx
            or abs(f - vy0) > ty or abs(f + d - vy1) > ty):
        raise NotSimple(f"ảnh không phủ kín trang (ảnh {a:.0f}×{d:.0f} tại {e:.0f},{f:.0f}; "
                        f"trang {vx1 - vx0:.0f}×{vy1 - vy0:.0f})")
    if abs((a / d) / (W / H) - 1) > 0.01:
        raise NotSimple("ảnh bị kéo méo tỉ lệ khi in lên trang")

    data = img.get_data()   # DCTDecode: pypdf trả nguyên bytes, không giải mã
    if data[:3] != b"\xff\xd8\xff":
        raise NotSimple("dữ liệu ảnh không phải JPEG")
    if Image is not None:   # đọc header (chưa giải mã) — khớp cỡ khai trong PDF, không CMYK
        with Image.open(io.BytesIO(data)) as im:
            if im.size != (W, H):
                raise NotSimple(f"JPEG {im.size[0]}×{im.size[1]} lệch cỡ khai {W}×{H}")
            if im.mode not in ("RGB", "L"):
                raise NotSimple(f"JPEG chế độ màu {im.mode}")
    return data, (W, H)


def find_pdfs(targets):
    """Danh sách PDF từ đối số (file hoặc folder — tìm cả folder con, bỏ folder chấm-đầu
    như .pdf-goc). Không đối số = cả downloads/."""
    out = []
    for t in targets or [str(DOWNLOADS)]:
        p = Path(t).resolve()
        if p.is_file():
            if p.suffix.lower() == ".pdf":
                out.append(p)
            else:
                print(f"  ! Bỏ qua (không phải PDF): {p}")
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [x for x in dirs if not x.startswith(".")]
                out += [Path(root) / x for x in files if x.lower().endswith(".pdf")]
        else:
            print(f"  ! Không thấy: {p}")
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return sorted(uniq, key=lambda x: [int(t) if t.isdigit() else t.lower()
                                       for t in re.split(r"(\d+)", str(x))])


def _under(p, root):
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def _move(src, dst):
    """Đổi tên (nguyên tử, cùng ổ); khác ổ (junction) thì chép rồi xoá."""
    try:
        os.rename(src, dst)
    except OSError:
        shutil.move(str(src), str(dst))


def _stash_pdf(pdf):
    """Cất PDF gốc vào <folder truyện>/.pdf-goc/ (trùng tên thì thêm ' (2)'...)."""
    dest_dir = pdf.parent / ORIG_DIR
    dest_dir.mkdir(exist_ok=True)
    target, k = dest_dir / pdf.name, 2
    while target.exists():
        target = dest_dir / f"{pdf.stem} ({k}){pdf.suffix}"
        k += 1
    _move(pdf, target)
    return target


def _same_as_pdf(folder, pages):
    """Thư mục đã có có đúng là bản tách từ PDF này không (cùng số ảnh, từng byte)."""
    try:
        names = sorted((x for x in os.listdir(folder) if (folder / x).is_file()),
                       key=lambda x: [int(t) if t.isdigit() else t.lower()
                                      for t in re.split(r"(\d+)", x)])
    except OSError:
        return False
    if len(names) != len(pages):
        return False
    for name, (data, _) in zip(names, pages):
        try:
            if (folder / name).read_bytes() != data:
                return False
        except OSError:
            return False
    return True


def import_pdf(pdf, name, dry_run):
    """Tách 1 PDF. Trả True nếu xong (hoặc dry-run kiểm đạt), False nếu lỗi/bỏ qua."""
    t0 = time.time()
    try:
        from pypdf import PdfReader
    except ImportError:
        print("  ✗ Thiếu thư viện pypdf — cài:  python -m pip install pypdf")
        return False
    try:
        reader = PdfReader(str(pdf))
        if reader.is_encrypted and not reader.decrypt(""):
            print("  ✗ PDF có mật khẩu — bỏ qua")
            return False
        warns, pages = set(), []
        for i, page in enumerate(reader.pages, 1):
            try:
                pages.append(page_jpeg(page, warns))
            except NotSimple as e:
                print(f"  ✗ Trang {i}: {e}. File này chưa tách được (không đụng gì).")
                return False
    except Exception as e:
        print(f"  ✗ Không đọc được PDF: {e.__class__.__name__}: {e}")
        return False
    if not pages:
        print("  ✗ PDF không có trang nào")
        return False
    for w in sorted(warns):
        print(f"  ! {w}")
    sizes = {wh for _, wh in pages}
    size_txt = (f"{next(iter(sizes))[0]}×{next(iter(sizes))[1]}" if len(sizes) == 1
                else f"{len(sizes)} cỡ khác nhau")
    total = sum(len(dta) for dta, _ in pages)
    dest = pdf.parent / name
    info = f"{len(pages)} trang JPEG {size_txt}, {total / 1048576:.1f}MB"

    if dest.exists():
        if _same_as_pdf(dest, pages):
            if dry_run:
                print(f"  = '{name}' đã tách từ trước ({info}) — sẽ chỉ cất PDF vào {ORIG_DIR}/")
                return True
            moved = _stash_pdf(pdf)
            print(f"  = '{name}' đã tách từ trước — cất PDF -> {moved.parent.name}/{moved.name}")
            return True
        print(f"  ✗ Đã có thư mục '{name}' (nội dung khác PDF này) — không ghi đè. "
              f"Đổi tên/xoá thư mục đó hoặc đổi tên file PDF rồi chạy lại.")
        return False
    if dry_run:
        print(f"  ✓ -> '{name}/' ({info})")
        return True

    # Ghi vào downloads/.pdf-tmp/ (reader không quét) rồi mới đổi tên sang chỗ thật.
    tmp_root = DOWNLOADS / TMP_DIR if _under(pdf, DOWNLOADS) else pdf.parent / TMP_DIR
    tmp = tmp_root / f"{pdf.parent.name} - {name}"
    if tmp.exists():
        shutil.rmtree(tmp)          # bản dở của lần chạy trước bị ngắt
    tmp.mkdir(parents=True)
    width = max(3, len(str(len(pages))))
    try:
        for i, (data, _) in enumerate(pages, 1):
            verdict, detail = check_image_bytes(data, who=f"{pdf.name} trang {i}")
            if verdict != "ok":
                raise RuntimeError(f"trang {i}: ảnh JPEG lỗi ({verdict}: {detail})")
            (tmp / f"{i:0{width}d}.jpg").write_bytes(data)
        if len(os.listdir(tmp)) != len(pages):
            raise RuntimeError("số ảnh ghi ra lệch số trang")
        _move(tmp, dest)
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"  ✗ {e} — đã huỷ, không đụng gì")
        return False
    finally:
        try:
            tmp_root.rmdir()        # chỉ xoá khi rỗng
        except OSError:
            pass
    moved = _stash_pdf(pdf)
    print(f"  ✓ -> '{name}/' ({info}, {time.time() - t0:.1f}s); "
          f"PDF gốc -> {moved.parent.name}/{moved.name}")
    return True


def main():
    ap = argparse.ArgumentParser(description="Tách PDF (mỗi trang 1 ảnh JPEG) thành thư mục "
                                             "chương 'Tập NN' cho reader.")
    ap.add_argument("targets", nargs="*", help="file PDF / folder (mặc định: cả downloads/)")
    ap.add_argument("--dry-run", action="store_true", help="chỉ kiểm + in kế hoạch, không ghi gì")
    args = ap.parse_args()

    pdfs = find_pdfs(args.targets)
    if not pdfs:
        print("Không thấy file PDF nào.")
        return 2

    # Đặt tên + chặn lỗi bố cục TRƯỚC khi đụng file nào.
    plan, names = [], {}
    for pdf in pdfs:
        name = chapter_name(pdf.stem)
        if pdf.parent == DOWNLOADS:
            print(f"✗ {pdf.name}: đang nằm ngay downloads\\ — tạo folder truyện, "
                  f"bỏ PDF vào đó rồi chạy lại")
            continue
        if name is None:
            print(f"✗ {pdf.name}: tên file không có số tập — đổi tên (vd 'Tập 3.pdf') rồi chạy lại")
            continue
        names.setdefault((pdf.parent, name), []).append(pdf)
        plan.append((pdf, name))
    for (parent, name), group in names.items():
        if len(group) > 1:
            print(f"✗ {len(group)} file cùng ra '{name}' trong '{parent.name}': "
                  + ", ".join(p.name for p in group) + " — đổi tên cho khác số rồi chạy lại")
            plan = [(p, n) for p, n in plan if p not in group]

    if any(not _under(p, DOWNLOADS) for p, _ in plan):
        print("! Lưu ý: reader chỉ đọc truyện trong downloads\\ — file ngoài đó tách xong "
              "phải tự chép vào.")
    ok = 0
    for pdf, name in plan:
        print(f"{pdf.parent.name}\\{pdf.name}")
        ok += import_pdf(pdf, name, args.dry_run)
    bad = len(pdfs) - ok
    verb = "kiểm đạt" if args.dry_run else "xong"
    print(f"\nTổng: {ok}/{len(pdfs)} file {verb}" + (f", {bad} lỗi/bỏ qua" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
