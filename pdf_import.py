#!/usr/bin/env python3
"""Nhập truyện dạng PDF vào thư viện: mỗi tập (1 file PDF, hoặc 1 folder chứa các phần bị
tách) -> 1 thư mục chương "Tập NN" chứa ảnh.

Reader chỉ hiểu "chương = thư mục ảnh", nên PDF phải tách ra một lần. Chỉ nhận loại PDF
"vỏ bọc ảnh": mỗi trang là ĐÚNG 1 ảnh JPEG phủ kín trang (bản scan/ghép ảnh thường gặp).
Khi đó bytes JPEG trong PDF được chép NGUYÊN TRẠNG ra `001.jpg, 002.jpg...` — không giải
mã/nén lại, không mất chất lượng, dung lượng ≈ PDF. Trang khác loại (có chữ/vector, ảnh nén
kiểu khác, nhiều ảnh ghép, xoay, trong suốt thật, CMYK...) -> DỪNG cả tập + báo trang nào,
không đụng gì (chưa có bộ dựng trang — thêm khi thật sự gặp). Lớp trong suốt "vết thừa"
(ghép lên nền trắng như trình đọc PDF mà lệch ≤ ALPHA_TOL/255) vẫn nhận, giữ JPEG gốc.

Bố cục quyết định cách nhập (không cần tuỳ chọn):
  1) PDF THẲNG trong folder truyện = 1 tập/file:
       downloads/Doraemon truyện dài/Long 1 LITE.pdf
         -> downloads/Doraemon truyện dài/Tập 01/001.jpg ... 189.jpg
     Số tập lấy theo chữ Tập/Vol/Chương/Chapter/Ch/# trong tên file, không có thì số ĐẦU
     TIÊN ("Long 1 LITE" -> Tập 01, "Long DoremonVoz Vol.07 (lite)" -> Tập 07).
  2) PDF trong 1 FOLDER CON của truyện = cả folder là 1 tập bị tách nhiều file (GỘP):
       downloads/Doraemon truyện dài/14 - Ba chàng hiệp sĩ mộng mơ/
           Doremon 14 - ..._Doremon 14 -.pdf, ..._31_Doremon 1.pdf, ..._61_..., ..._151_...
         -> downloads/Doraemon truyện dài/Tập 14/001.jpg ... 189.jpg (ảnh đánh số liền)
     Số tập lấy từ TÊN FOLDER. Thứ tự phần: bỏ phần tên chung, số đứng đầu phần còn lại
     (trang bắt đầu 0/31/61… hoặc 1/2/3), file KHÔNG có số = phần đầu; rồi đối chiếu số
     với số trang từng phần — lệch (thiếu phần giữa/đầu, đặt tên sai) -> dừng. Thiếu phần
     CUỐI thì không có gì để phát hiện: xem bảng thứ tự lúc --dry-run.
     Folder gộp chỉ được chứa PDF (có ảnh/thư mục con = bố cục khác -> từ chối). Chọn 1
     phần (kéo-thả 1 file) cũng lấy CẢ folder — không bao giờ ra tập thiếu trang.
  PDF ngay downloads/ hoặc sâu hơn 1 folder con -> từ chối. PDF ngoài downloads/ -> kiểu 1.
Tên không có số / 2 nguồn cùng ra 1 "Tập NN" -> báo lỗi, đổi tên rồi chạy lại.

Nguồn (PDF lẻ / cả folder gộp) chuyển vào <folder truyện>/.pdf-goc/ bằng 1 lần đổi tên
(reader + check_library bỏ qua thư mục chấm-đầu; đọc thử thấy ổn thì tự tay xoá).

An toàn: ghi vào `downloads/.pdf-tmp/` (reader không quét) + kiểm từng ảnh giải mã được, đủ
trang rồi mới đổi tên sang thư mục thật -> reader không bao giờ thấy chương dở. Thư mục
"Tập NN" đã có: giống hệt nội dung nguồn (lần trước tách xong mà chưa kịp cất) -> chỉ cất
nguồn; khác -> bỏ qua, không ghi đè. Bị ngắt ở bước nào chạy lại cũng tự xong.

Cách dùng:
  python pdf_import.py                                   # tìm PDF trong cả downloads/
  python pdf_import.py "downloads\\Doraemon truyện dài"   # 1 folder (tìm cả folder con)
  python pdf_import.py "...\\Long 1 LITE.pdf"             # 1 file
  python pdf_import.py "...\\14 - Ba chàng hiệp sĩ mộng mơ"  # 1 tập bị tách (gộp)
  python pdf_import.py ... --dry-run                     # chỉ kiểm + in kế hoạch, không ghi
Hoặc bấm `Nhap PDF.bat` (kéo-thả file/folder vào cũng được).

Exit: 0 = ổn hết, 1 = có tập lỗi/bỏ qua, 2 = không thấy PDF nào. Cần `pypdf` (thuần Python).
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
# Lớp trong suốt (SMask): trình đọc PDF ghép ảnh lên nền trang trắng. Bản ghép lệch JPEG gốc
# tối đa bao nhiêu (/255) thì coi là vết thừa vô hại, vẫn chép JPEG gốc. Gặp thật (Doraemon
# truyện ngắn Vol.01): trang 29 lệch 0 (điểm trong suốt vốn đã trắng), trang 101 lệch 13
# (viền elip mảnh quanh số trang) — mắt không thấy.
ALPHA_TOL = 16
# File hệ thống được phép nằm cùng các phần PDF trong folder gộp (đi theo folder vào .pdf-goc).
SYS_FILES = {"thumbs.db", "desktop.ini", ".ds_store"}

# Số tập: ưu tiên số đứng sau từ khoá, không có thì số đầu tiên trong tên.
NUM_KEY_RE = re.compile(
    r"\b(?:tập|tap|vol(?:ume)?|quyển|quyen|chương|chuong|chapter|chap|ch)\.?\s*(\d+(?:\.\d+)?)"
    r"|#\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
# Số thứ tự 1 phần: số đứng đầu phần tên còn lại sau khi bỏ phần chung ("31_Doremon 1", " (2)",
# " phần 2", "_part2").
PART_NUM_RE = re.compile(r"[\s_.,#()\[\]-]*(?:phần|phan|part|p)?[\s_.]*(\d+)", re.IGNORECASE)

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
    sm, mask = img.get("/SMask"), None
    if sm is not None:
        sm = sm.get_object()
        if (int(sm.get("/BitsPerComponent", 8)) != 8 or "/Decode" in sm or "/Matte" in sm
                or _names(sm.get("/ColorSpace")) not in ([], ["/DeviceGray"])
                or {"/DCTDecode", "/JPXDecode"} & set(_names(sm.get("/Filter")))):
            raise NotSimple("lớp trong suốt (SMask) kiểu lạ")
        raw = sm.get_data()
        if raw.strip(b"\xff"):
            mask = (sm, raw)    # có điểm trong suốt -> đo độ lệch khi đã có JPEG (dưới)
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
    if mask is not None:
        if Image is None:
            raise NotSimple("ảnh có vùng trong suốt (cần Pillow để kiểm)")
        dev = _alpha_deviation(data, *mask, (W, H))
        if dev > ALPHA_TOL:
            raise NotSimple(f"ảnh có vùng trong suốt thật (ghép lên nền trắng lệch {dev}/255)")
        warns.add(f"có trang kèm lớp trong suốt vô hại (ghép lên nền trắng lệch ≤ {ALPHA_TOL}/255)"
                  " — giữ JPEG gốc")
    return data, (W, H)


def _alpha_deviation(data, sm, raw, size):
    """Ảnh JPEG kèm lớp trong suốt: trình đọc PDF ghép ảnh lên nền trang TRẮNG. Trả độ lệch
    lớn nhất (0..255) giữa bản ghép đó và JPEG gốc = max (255 - kênh tối nhất)·(1 - alpha).
    Nhỏ = các điểm trong suốt vốn đã trắng -> chép JPEG gốc ra là đúng như PDF hiển thị."""
    from PIL import ImageChops
    W, H = size
    if (int(sm.get("/Width", 0)), int(sm.get("/Height", 0))) != (W, H) or len(raw) < W * H:
        raise NotSimple("lớp trong suốt khác cỡ ảnh")
    alpha = Image.frombytes("L", (W, H), raw[:W * H])
    with Image.open(io.BytesIO(data)) as im:
        chans = ImageChops.invert(im.convert("L" if im.mode == "L" else "RGB")).split()
    dark = chans[0]
    for c in chans[1:]:
        dark = ImageChops.lighter(dark, c)
    return ImageChops.multiply(dark, ImageChops.invert(alpha)).getextrema()[1]


def _natkey(s):
    """Sắp tự nhiên: 'x 2' < 'x 10'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def _key(p):
    """So đường dẫn kiểu Windows: không phân biệt hoa/thường, dấu dựng sẵn/tổ hợp."""
    return unicodedata.normalize("NFC", str(p)).casefold()


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
    return sorted(uniq, key=_natkey)


def order_parts(pdfs):
    """Thứ tự các phần của 1 tập bị tách -> [(pdf, số|None)]. Bỏ phần tên chung của các file
    (không cắt giữa 1 dãy số: '…_1' chung của '…_1_x'/'…_15_x' phải lùi về '…_'); số đứng đầu
    phần còn lại = vị trí của phần; phần KHÔNG có số = phần đầu. Vd:
      '…mo_Doremon 14 -' / '…mo_31_Doremon 1' / … / '…mo_151_Doremon '  -> None, 31, …, 151
    Không xác định được (≥2 file không số, trùng số) -> ValueError."""
    if len(pdfs) == 1:
        return [(pdfs[0], None)]
    stems = [unicodedata.normalize("NFC", p.stem) for p in pdfs]
    pre = os.path.commonprefix(stems)
    if pre[-1:].isdigit() and any(s[len(pre):len(pre) + 1].isdigit() for s in stems):
        pre = pre.rstrip("0123456789")
    items = []
    for p, s in zip(pdfs, stems):
        m = PART_NUM_RE.match(s[len(pre):])
        items.append((p, int(m.group(1)) if m else None))
    nonum = [p.name for p, n in items if n is None]
    if len(nonum) > 1:
        raise ValueError(f"{len(nonum)} file không có số thứ tự (sau phần tên chung "
                         f"'{pre}'): " + ", ".join(nonum))
    nums = [n for _, n in items if n is not None]
    if len(set(nums)) != len(nums):
        raise ValueError("có file trùng số thứ tự: " + ", ".join(
            p.name for p, n in items if n is not None and nums.count(n) > 1))
    return sorted(items, key=lambda x: -1 if x[1] is None else x[1])


def check_order(items, counts):
    """Các phần (đã xếp) có đủ + liền nhau không, đối chiếu số trong tên với số trang:
    - số = trang bắt đầu của phần, cộng dồn số trang, đếm từ 0 hoặc 1 (0/31/61…);
    - hoặc đánh số liên tiếp từ 0/1 (1, 2, 3…; có phần đầu không số thì từ 1/2).
    Phần đầu không số được tính là 0/1. Thiếu phần đầu/giữa -> False; thiếu phần CUỐI thì
    không có gì để đối chiếu (số trang cả tập không ghi ở đâu)."""
    nums = [n for _, n in items]
    if len(nums) < 2:
        return True
    for pos in ((0, 1) if nums[0] is None else (nums[0],)):
        if pos not in (0, 1):
            continue
        for n, c in zip(nums, counts):
            if n is not None and n != pos:
                break
            pos += c
        else:
            return True
    seq = [n for n in nums if n is not None]
    return (seq[0] in ((1, 2) if nums[0] is None else (0, 1))
            and seq == list(range(seq[0], seq[0] + len(seq))))


class Job:
    """1 tập cần nhập: các PDF `items` [(pdf, số|None)] theo thứ tự -> thư mục <folder
    truyện>/<name>. `src` = thứ được cất vào .pdf-goc/ sau khi xong: file PDF (lẻ) hoặc CẢ
    folder các phần (gộp — 1 lần đổi tên, bị ngắt giữa chừng thì các phần vẫn đủ ở 1 chỗ)."""

    def __init__(self, items, name, src, merged):
        self.items, self.name, self.src, self.merged = items, name, src, merged
        self.series = src.parent
        self.dest = self.series / name
        self.label = (f"{self.series.name}\\{src.name}\\  (gộp {len(items)} file PDF)"
                      if merged else f"{self.series.name}\\{src.name}")


def plan_jobs(pdfs):
    """Chia PDF thành các tập theo bố cục (xem đầu file). Lỗi bố cục -> in ra, không lập tập.
    Trả (jobs, số nguồn bị từ chối)."""
    jobs, bad, folders = [], 0, {}
    for pdf in pdfs:
        depth = len(pdf.relative_to(DOWNLOADS).parts) if _under(pdf, DOWNLOADS) else 2
        if depth == 1:
            print(f"✗ {pdf.name}: đang nằm ngay downloads\\ — tạo folder truyện, "
                  f"bỏ PDF vào đó rồi chạy lại")
            bad += 1
        elif depth == 2:
            name = chapter_name(pdf.stem)
            if name is None:
                print(f"✗ {pdf.name}: tên file không có số tập — đổi tên (vd 'Tập 3.pdf') "
                      f"rồi chạy lại")
                bad += 1
            else:
                jobs.append(Job([(pdf, None)], name, pdf, merged=False))
        elif depth == 3:
            folders.setdefault(pdf.parent, []).append(pdf)
        else:
            print(f"✗ {pdf.relative_to(DOWNLOADS)}: nằm quá sâu — PDF phải nằm thẳng trong "
                  f"folder truyện, hoặc trong 1 folder con của truyện (= 1 tập bị tách nhiều file)")
            bad += 1

    for folder, picked in folders.items():
        label = f"{folder.parent.name}\\{folder.name}\\"
        try:
            entries = list(os.scandir(folder))
        except OSError as e:
            print(f"✗ {label}: không đọc được folder ({e})")
            bad += 1
            continue
        parts = sorted((Path(e.path) for e in entries
                        if e.is_file() and e.name.lower().endswith(".pdf")), key=_natkey)
        other = [e.name for e in entries if not e.is_file()
                 or not (e.name.lower().endswith(".pdf") or e.name.lower() in SYS_FILES)]
        name = chapter_name(folder.name)
        if other:
            print(f"✗ {label}: ngoài PDF còn có {', '.join(other[:5])}"
                  f"{'…' if len(other) > 5 else ''} — folder con chỉ được chứa các file PDF "
                  f"của 1 tập (sẽ gộp thành 1 chương)")
            bad += 1
            continue
        if name is None:
            print(f"✗ {label}: tên folder không có số tập — đổi tên (vd '14 - <tên tập>') "
                  f"rồi chạy lại")
            bad += 1
            continue
        if _key(folder.name) == _key(name):
            print(f"✗ {label}: folder chứa PDF trùng tên chương sẽ tạo — đổi tên folder "
                  f"(vd '{name.split()[-1]} - <tên tập>') rồi chạy lại")
            bad += 1
            continue
        try:
            items = order_parts(parts)
        except ValueError as e:
            print(f"✗ {label}: {e} — không biết thứ tự các phần, đổi tên rồi chạy lại")
            bad += 1
            continue
        if len(picked) < len(parts):
            print(f"! {label}: mới chọn {len(picked)}/{len(parts)} file — tập gộp luôn lấy "
                  f"CẢ folder")
        jobs.append(Job(items, name, folder, merged=True))

    # 2 nguồn cùng ra 1 thư mục (vd 'Long 14.pdf' + folder '14 - …') -> loại cả 2.
    by_dest = {}
    for j in jobs:
        by_dest.setdefault(_key(j.dest), []).append(j)
    for group in by_dest.values():
        if len(group) > 1:
            print(f"✗ {len(group)} nguồn cùng ra '{group[0].name}' trong "
                  f"'{group[0].series.name}': " + ", ".join(j.src.name for j in group)
                  + " — đổi tên cho khác số rồi chạy lại")
            bad += len(group)
    jobs = [j for j in jobs if len(by_dest[_key(j.dest)]) == 1]
    return sorted(jobs, key=lambda j: _natkey(j.src)), bad


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


def _stash(src):
    """Cất nguồn (file PDF / cả folder gộp) vào <folder truyện>/.pdf-goc/ bằng 1 lần đổi tên
    (trùng tên thì thêm ' (2)'...)."""
    dest_dir = src.parent / ORIG_DIR
    dest_dir.mkdir(exist_ok=True)
    is_dir = src.is_dir()
    stem, suffix = (src.name, "") if is_dir else (src.stem, src.suffix)
    target, k = dest_dir / src.name, 2
    while target.exists():
        target = dest_dir / f"{stem} ({k}){suffix}"
        k += 1
    if is_dir:
        os.rename(src, target)  # cùng folder truyện = cùng ổ; không chép-xoá dở dang
    else:
        _move(src, target)
    return target


def _same_as_pdf(folder, pages):
    """Thư mục đã có có đúng là bản tách từ nguồn này không (cùng số ảnh, từng byte)."""
    try:
        names = sorted((x for x in os.listdir(folder) if (folder / x).is_file()), key=_natkey)
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


def _finish(job, msg):
    """Cất nguồn vào .pdf-goc/ + in kết quả. Cất không được (file/folder đang bị chương trình
    khác mở) -> chương đã tách vẫn giữ; chạy lại thì tool thấy 'đã tách từ trước' và chỉ cất."""
    what = "folder PDF gốc" if job.merged else "PDF gốc"
    try:
        moved = _stash(job.src)
    except OSError as e:
        print(f"{msg}; NHƯNG chưa cất được {what} vào {ORIG_DIR}/ ({e.strerror or e}) — "
              f"đóng chương trình đang mở nó rồi chạy lại")
        return False
    print(f"{msg}; {what} -> {moved.parent.name}/{moved.name}{'/' if job.merged else ''}")
    return True


def import_job(job, dry_run):
    """Tách 1 tập. Trả True nếu xong (hoặc dry-run kiểm đạt), False nếu lỗi/bỏ qua."""
    t0 = time.time()
    try:
        from pypdf import PdfReader
    except ImportError:
        print("  ✗ Thiếu thư viện pypdf — cài:  python -m pip install pypdf")
        return False
    unit = "Tập" if job.merged else "File"
    warns, pages, counts = set(), [], []
    for pdf, _ in job.items:
        who = f"{pdf.name}: " if job.merged else ""
        try:
            reader = PdfReader(str(pdf))
            if reader.is_encrypted and not reader.decrypt(""):
                print(f"  ✗ {who}PDF có mật khẩu — bỏ qua")
                return False
            n0 = len(pages)
            for i, page in enumerate(reader.pages, 1):
                try:
                    pages.append(page_jpeg(page, warns))
                except NotSimple as e:
                    print(f"  ✗ {who}Trang {i}: {e}. {unit} này chưa tách được (không đụng gì).")
                    return False
        except Exception as e:
            print(f"  ✗ {who}Không đọc được PDF: {e.__class__.__name__}: {e}")
            return False
        counts.append(len(pages) - n0)
        if not counts[-1]:
            print(f"  ✗ {who}PDF không có trang nào")
            return False
    if job.merged:
        for k, ((pdf, _), n) in enumerate(zip(job.items, counts), 1):
            print(f"    {k}. {pdf.name}  ({n} trang)")
        if not check_order(job.items, counts):
            print("  ✗ Số trong tên các phần không khớp số trang — phải là trang bắt đầu của "
                  "phần (0/31/61…) hoặc 1, 2, 3… liên tiếp. Thiếu phần hoặc đặt tên sai? "
                  "Kiểm lại rồi chạy lại (không đụng gì).")
            return False
    for w in sorted(warns):
        print(f"  ! {w}")
    sizes = {wh for _, wh in pages}
    size_txt = (f"{next(iter(sizes))[0]}×{next(iter(sizes))[1]}" if len(sizes) == 1
                else f"{len(sizes)} cỡ khác nhau")
    total = sum(len(dta) for dta, _ in pages)
    name, dest = job.name, job.dest
    info = f"{len(pages)} trang JPEG {size_txt}, {total / 1048576:.1f}MB"
    what = "folder PDF gốc" if job.merged else "PDF gốc"

    if dest.exists():
        if _same_as_pdf(dest, pages):
            if dry_run:
                print(f"  = '{name}' đã tách từ trước ({info}) — sẽ chỉ cất {what} vào {ORIG_DIR}/")
                return True
            return _finish(job, f"  = '{name}' đã tách từ trước")
        print(f"  ✗ Đã có thư mục '{name}' (nội dung khác nguồn này) — không ghi đè. "
              f"Đổi tên/xoá thư mục đó hoặc đổi tên {'folder' if job.merged else 'file PDF'} "
              f"rồi chạy lại.")
        return False
    if dry_run:
        print(f"  ✓ -> '{name}/' ({info})")
        return True

    # Ghi vào downloads/.pdf-tmp/ (reader không quét) rồi mới đổi tên sang chỗ thật.
    tmp_root = DOWNLOADS / TMP_DIR if _under(job.src, DOWNLOADS) else job.series / TMP_DIR
    tmp = tmp_root / f"{job.series.name} - {name}"
    if tmp.exists():
        shutil.rmtree(tmp)          # bản dở của lần chạy trước bị ngắt
    tmp.mkdir(parents=True)
    width = max(3, len(str(len(pages))))
    try:
        for i, (data, _) in enumerate(pages, 1):
            verdict, detail = check_image_bytes(data, who=f"{job.src.name} trang {i}")
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
    return _finish(job, f"  ✓ -> '{name}/' ({info}, {time.time() - t0:.1f}s)")


def main():
    ap = argparse.ArgumentParser(description="Tách PDF (mỗi trang 1 ảnh JPEG) thành thư mục "
                                             "chương 'Tập NN' cho reader. PDF trong folder con "
                                             "của truyện = 1 tập bị tách, gộp lại.")
    ap.add_argument("targets", nargs="*", help="file PDF / folder (mặc định: cả downloads/)")
    ap.add_argument("--dry-run", action="store_true", help="chỉ kiểm + in kế hoạch, không ghi gì")
    args = ap.parse_args()

    pdfs = find_pdfs(args.targets)
    if not pdfs:
        print("Không thấy file PDF nào.")
        return 2

    # Chia tập + chặn lỗi bố cục TRƯỚC khi đụng file nào.
    jobs, bad = plan_jobs(pdfs)
    if any(not _under(j.src, DOWNLOADS) for j in jobs):
        print("! Lưu ý: reader chỉ đọc truyện trong downloads\\ — file ngoài đó tách xong "
              "phải tự chép vào.")
    ok = 0
    for job in jobs:
        print(job.label)
        ok += import_job(job, args.dry_run)
    total = len(jobs) + bad
    bad = total - ok
    verb = "kiểm đạt" if args.dry_run else "xong"
    print(f"\nTổng: {ok}/{total} tập {verb}" + (f", {bad} lỗi/bỏ qua" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
