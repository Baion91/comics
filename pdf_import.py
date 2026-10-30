#!/usr/bin/env python3
"""Nhập truyện dạng PDF (hoặc CBZ / MOBI) vào thư viện: mỗi tập (1 file PDF/CBZ, hoặc 1 folder
chứa các PDF bị tách) -> 1 thư mục chương "Tập NN" chứa ảnh.

CBZ (= file ZIP chứa ảnh, vd bản rip Kindle/digital): ảnh chép NGUYÊN TRẠNG theo thứ tự tên
(sắp tự nhiên theo cả đường dẫn trong ZIP), đánh lại `001.jpg, 002.jpg...` (đuôi theo định
dạng thật). File không phải ảnh (ComicInfo.xml, .txt...) bỏ qua + báo; trang ngang (trang
đôi) giữ nguyên 1 ảnh. CBZ chỉ nhận kiểu 1 (thẳng trong folder truyện, không gộp), gốc cất
vào <folder truyện>/.cbz-goc/.

MOBI (.mobi/.azw — truyện tranh Kindle do KindleComicConverter/kindlegen tạo, KHÔNG DRM): ảnh
trong file chép NGUYÊN TRẠNG theo thứ tự trang của sách. Sách có mục lục (≥ 2 mục) -> mỗi mục
1 thư mục "Chapter NN" (số lấy từ tên mục: 'Chapter 14 END' -> Chapter 14); không có mục lục
-> cả sách 1 "Tập NN" như CBZ. Chỉ nhận kiểu 1 (thẳng trong folder truyện), gốc cất vào
<folder truyện>/.mobi-goc/. Có DRM / chỉ có định dạng KF8 (.azw3) / sách chữ -> từ chối.

Phần còn lại dưới đây nói về PDF.

Reader chỉ hiểu "chương = thư mục ảnh", nên PDF phải tách ra một lần. Chỉ nhận loại PDF
"vỏ bọc ảnh": mỗi trang là ĐÚNG 1 ảnh JPEG phủ kín trang (bản scan/ghép ảnh thường gặp),
hoặc thu vừa khổ giấy có lề trắng (nằm trọn trong trang, chạm 2 mép đối diện — bỏ lề, chỉ
lấy ảnh). Khi đó bytes JPEG trong PDF được chép NGUYÊN TRẠNG ra `001.jpg, 002.jpg...` — không
giải mã/nén lại, không mất chất lượng, dung lượng ≈ PDF. Trang khác loại (có chữ/vector, ảnh
nén kiểu khác, nhiều ảnh ghép, xoay, CMYK, ảnh tràn ra ngoài / nhỏ lọt giữa trang...) -> DỪNG
cả tập + báo trang nào, không đụng gì (chưa có bộ dựng trang — thêm khi thật sự gặp). Ảnh
kèm lớp trong suốt (SMask): trình đọc PDF ghép ảnh lên nền trang trắng — chỉ vài điểm lệch
(≤ ALPHA_MAX_PX điểm lệch quá ALPHA_TOL/255, vết thừa lúc chỉnh ảnh) -> vẫn chép JPEG gốc;
vùng trong suốt thật -> ghép lên nền trắng y như PDF hiển thị và lưu RIÊNG trang đó thành
PNG (không nén mất dữ liệu).

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
     (trang bắt đầu 0/31/61…, 1/2/3 hoặc cách đều 00/03/06…), file KHÔNG có số = phần đầu;
     rồi đối chiếu số với số trang từng phần — lệch (thiếu phần giữa/đầu, đặt tên sai) ->
     dừng. Thiếu phần CUỐI thì không có gì để phát hiện: xem bảng thứ tự lúc --dry-run.
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
  python pdf_import.py "...\\RockMan Series.mobi" --bia 3   # + trang 3 làm bìa (cover.jpg)
Hoặc bấm `Nhap PDF.bat` (kéo-thả file/folder vào cũng được).

--bia N (chỉ khi nhập đúng 1 file): chép trang N (đếm từ 1 trong cả file) thành cover.<đuôi>
trong folder truyện — reader ưu tiên file cover.* làm bìa. Đã có cover.* khác -> không ghi đè.

Cuối bảng có mục "Các tập lỗi" (mỗi tập 1 dòng lý do) — lỗi nhiều tập thì phần in phía trên
trôi mất.

Exit: 0 = ổn hết, 1 = có tập lỗi/bỏ qua, 2 = không thấy file nào / thiếu pypdf. Cần `pypdf`
(thuần Python) + `cryptography` cho PDF mã hoá AES (thiếu thì riêng tập đó báo lỗi kèm lệnh cài).
"""

import argparse
import bisect
import importlib.util
import io
import os
import re
import shutil
import struct
import sys
import time
import unicodedata
import zipfile
from pathlib import Path

from comics_core import Image, check_image_bytes, sniff_format

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

DOWNLOADS = Path(__file__).resolve().parent / "downloads"
ORIG_DIR = ".pdf-goc"       # nơi cất PDF gốc, trong folder truyện
CBZ_ORIG_DIR = ".cbz-goc"   # nơi cất CBZ gốc, trong folder truyện
MOBI_ORIG_DIR = ".mobi-goc"  # nơi cất MOBI gốc, trong folder truyện
TMP_DIR = ".pdf-tmp"        # nơi ghi dở, ở gốc downloads/ (reader bỏ qua folder chấm-đầu)
MOBI_EXTS = (".mobi", ".azw", ".azw3")
SRC_EXTS = (".pdf", ".cbz") + MOBI_EXTS
# Ảnh nhận trong CBZ = đuôi reader đọc được (IMG_EXTS của reader_server.py).
CBZ_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
# Sách MOBI có chữ thật (tiểu thuyết kèm minh hoạ...) không phải truyện tranh — chỉ lấy ảnh là
# mất chữ. Truyện KCC/kindlegen: text chỉ gồm thẻ ảnh/khung phóng to, 0 ký tự hiển thị.
MOBI_TEXT_MAX = 2000
# Lớp trong suốt (SMask): trình đọc PDF ghép ảnh lên nền trang trắng. Điểm lệch JPEG gốc quá
# ALPHA_TOL (/255) mà không quá ALPHA_MAX_PX điểm (1 ô 8×8) = vết thừa vô hại -> chép JPEG gốc;
# nhiều hơn = vùng trong suốt thật -> trang đó lưu PNG đã ghép nền trắng. Gặp thật: Doraemon
# truyện ngắn Vol.01 trang 29 lệch 0 (điểm trong suốt vốn đã trắng), trang 101 lệch tối đa 13
# (viền elip mảnh quanh số trang); Vol.04 trang 11: 14 điểm hơi trong suốt, 2 điểm lệch 57.
ALPHA_TOL = 16
ALPHA_MAX_PX = 64
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
    """Trang không phải "đúng 1 ảnh JPEG phủ kín / vừa khổ trang" — lý do nằm trong message."""


def _num(s):
    """Số tập/chương trong tên (chuỗi, vd '7.5'): ưu tiên số sau từ khoá, không có thì số đầu
    tiên. None nếu tên không có số."""
    s = unicodedata.normalize("NFC", s)
    m = NUM_KEY_RE.search(s)
    if m:
        return m.group(1) or m.group(2)
    m = NUM_RE.search(s)
    return m.group(0) if m else None


def chapter_name(stem, prefix="Tập"):
    """'Long 1 LITE' -> 'Tập 01', 'X Vol.07 (lite)' -> 'Tập 07', '... 7.5' -> 'Tập 07.5'.
    None nếu tên không có số."""
    num = _num(stem)
    if num is None:
        return None
    whole, _, frac = num.partition(".")
    frac = frac.rstrip("0")
    return f"{prefix} {int(whole):02d}" + (f".{frac}" if frac else "")


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
    """(bytes, (W, H), đuôi) của trang nếu trang = ĐÚNG 1 ảnh JPEG phủ kín vùng hiển thị (crop
    box) hoặc vừa khổ có lề trắng (lề bị bỏ); không thì ném NotSimple. Bytes = nguyên stream
    DCTDecode trong PDF = 1 file JPEG ('.jpg'); riêng ảnh có vùng trong suốt thật -> PNG đã
    ghép nền trắng ('.png')."""
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

    # Hình học: ảnh không xoay/lật/nghiêng, không bị kéo méo tỉ lệ, và phủ kín vùng hiển thị
    # (lệch ≤ 0.5%, tối thiểu 2pt — vd crop box 1527.81×2399.7 trên ảnh 1528×2400) HOẶC "vừa
    # khổ giấy": nằm trọn trong trang + chạm đủ 2 mép đối diện, lề trắng (công cụ ghép ảnh
    # thành PDF thu ảnh vừa khổ Letter/A4 rồi căn giữa — gặp thật: Doraemon_Long_Stories_v19,
    # 183 trang trên 612×792). Lề chắc chắn trống (vòng lặp trên chỉ cho đúng 1 lệnh vẽ ảnh) =
    # nền giấy, không phải nội dung -> bỏ, vẫn chép JPEG gốc. Ảnh tràn ra ngoài trang (PDF cắt
    # bớt) hoặc nhỏ lọt giữa trang (có thể là trang dàn ý đồ) -> vẫn từ chối.
    if abs(b) > 1e-3 * max(abs(a), abs(d)) or abs(c) > 1e-3 * max(abs(a), abs(d)):
        raise NotSimple("ảnh bị xoay/nghiêng")
    if a <= 0 or d <= 0:
        raise NotSimple("ảnh bị lật")
    mb, cb = page.mediabox, page.cropbox
    vx0, vy0 = max(float(mb.left), float(cb.left)), max(float(mb.bottom), float(cb.bottom))
    vx1, vy1 = min(float(mb.right), float(cb.right)), min(float(mb.top), float(cb.top))
    tx, ty = max(2.0, 0.005 * (vx1 - vx0)), max(2.0, 0.005 * (vy1 - vy0))
    geo = f"ảnh {a:.0f}×{d:.0f} tại {e:.0f},{f:.0f}; trang {vx1 - vx0:.0f}×{vy1 - vy0:.0f}"
    fit_w = abs(e - vx0) <= tx and abs(e + a - vx1) <= tx
    fit_h = abs(f - vy0) <= ty and abs(f + d - vy1) <= ty
    if e < vx0 - tx or e + a > vx1 + tx or f < vy0 - ty or f + d > vy1 + ty:
        raise NotSimple(f"ảnh tràn ra ngoài trang — PDF cắt bớt ảnh ({geo})")
    if not (fit_w or fit_h):
        raise NotSimple(f"ảnh nhỏ hơn trang, không chạm 2 mép đối diện ({geo})")
    if not (fit_w and fit_h):
        warns.add(f"có trang lề trắng quanh ảnh (PDF đặt ảnh vừa khổ giấy {vx1 - vx0:.0f}×"
                  f"{vy1 - vy0:.0f}pt) — bỏ lề, chép JPEG gốc")
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
        sm, raw = mask
        if (int(sm.get("/Width", 0)), int(sm.get("/Height", 0))) != (W, H) or len(raw) < W * H:
            raise NotSimple("lớp trong suốt khác cỡ ảnh")
        alpha = Image.frombytes("L", (W, H), raw[:W * H])
        if _alpha_bad_px(data, alpha) > ALPHA_MAX_PX:
            return _flatten_png(data, alpha), (W, H), ".png"
        warns.add(f"có trang kèm lớp trong suốt vô hại (ghép lên nền trắng: ≤ {ALPHA_MAX_PX} điểm "
                  f"ảnh lệch quá {ALPHA_TOL}/255) — giữ JPEG gốc")
    return data, (W, H), ".jpg"


def _alpha_bad_px(data, alpha):
    """Ảnh JPEG kèm lớp trong suốt `alpha`: trình đọc PDF ghép ảnh lên nền trang TRẮNG. Đếm số
    điểm mà bản ghép đó lệch JPEG gốc quá ALPHA_TOL; lệch = (255 - kênh tối nhất)·(1 - alpha),
    nên điểm trong suốt vốn đã trắng không tính."""
    from PIL import ImageChops
    with Image.open(io.BytesIO(data)) as im:
        chans = ImageChops.invert(im.convert("L" if im.mode == "L" else "RGB")).split()
    dark = chans[0]
    for c in chans[1:]:
        dark = ImageChops.lighter(dark, c)
    return sum(ImageChops.multiply(dark, ImageChops.invert(alpha)).histogram()[ALPHA_TOL + 1:])


def _flatten_png(data, alpha):
    """Trang có vùng trong suốt thật: ghép JPEG lên nền trắng y như trình đọc PDF hiển thị ->
    bytes PNG (không nén mất dữ liệu; giữ hồ sơ màu ICC nếu JPEG có)."""
    with Image.open(io.BytesIO(data)) as im:
        icc = im.info.get("icc_profile")
        im = im.convert("L" if im.mode == "L" else "RGB")
    out = Image.composite(im, Image.new(im.mode, im.size, 255 if im.mode == "L" else
                                        (255, 255, 255)), alpha)
    buf = io.BytesIO()
    out.save(buf, "PNG", **({"icc_profile": icc} if icc else {}))
    return buf.getvalue()


def cbz_pages(cbz, warns):
    """[(bytes, (W, H), đuôi)] các trang trong CBZ, sắp tự nhiên theo cả đường dẫn trong ZIP.
    Bytes chép NGUYÊN TRẠNG; đuôi theo định dạng thật ('.jpeg' -> '.jpg'). File không phải ảnh
    -> bỏ qua + báo; rác hệ thống (__MACOSX/, ._x, Thumbs.db) -> bỏ im lặng. Không có ảnh / có
    mật khẩu -> NotSimple."""
    with zipfile.ZipFile(cbz) as z:
        imgs, skipped = [], []
        for info in z.infolist():
            if info.is_dir():
                continue
            parts = info.filename.split("/")
            base = parts[-1]
            if parts[0] == "__MACOSX" or base.startswith(".") or base.lower() in SYS_FILES:
                continue
            (imgs if Path(base).suffix.lower() in CBZ_IMG_EXTS else skipped).append(info)
        if not imgs:
            raise NotSimple("CBZ không có ảnh nào")
        if any(i.flag_bits & 0x1 for i in imgs):
            raise NotSimple("CBZ có mật khẩu")
        imgs.sort(key=lambda i: _natkey(i.filename))
        dirs = {i.filename.rpartition("/")[0] for i in imgs}
        if len(dirs) > 1:
            warns.add(f"ảnh nằm trong {len(dirs)} thư mục con — xếp theo tên thư mục rồi tên file")
        if skipped:
            names = [i.filename.rpartition("/")[2] for i in skipped]
            warns.add("bỏ qua file không phải ảnh: " + ", ".join(names[:5])
                      + ("…" if len(names) > 5 else ""))
        pages = []
        for n, info in enumerate(imgs, 1):
            data = z.read(info)     # zipfile tự kiểm CRC
            # Kiểm ngay lúc đọc (rẻ, khác PDF) để --dry-run cũng bắt được ảnh hỏng.
            verdict, detail = check_image_bytes(data, who=f"{cbz.name}/{info.filename}")
            if verdict != "ok":
                raise NotSimple(f"trang {n} ({info.filename}): ảnh lỗi ({verdict}: {detail})")
            fmt = sniff_format(data)
            ext = (".jpg" if fmt == "jpeg" else f".{fmt}") if fmt else Path(info.filename).suffix.lower()
            wh = (0, 0)
            if Image is not None:
                with Image.open(io.BytesIO(data)) as im:
                    wh = im.size
            pages.append((data, wh, ext))
    return pages


# ---- MOBI ----
# Truyện tranh Kindle (KCC/kindlegen) = sách bố cục cố định: mỗi trang 1 thẻ
# <img recindex="NNNNN"> trong text, ảnh nằm nguyên trong record (ảnh đầu + NNNNN - 1). File
# .mobi của KCC là bản lai MOBI7 + KF8 dùng chung ảnh -> chỉ đọc phần MOBI7 (record 0): text
# nén PalmDOC, mục lục = index NCX (record INDX, nhãn nằm trong record CNCX). Cấu trúc theo
# KindleUnpack (mobi_header / mobi_index). Gặp thật: RockMan Series.mobi (KCC 5.5.2, 527 trang
# JPEG xám 1072×1448, mục lục 14 chương; 5 trang credit nhóm dịch trùng byte — giữ nguyên).

IMG_TAG_RE = re.compile(rb"""<img\b[^>]*?\brecindex=["']?(\d+)""", re.IGNORECASE)
NCX_NONE = 0xFFFFFFFF
INDX_WORDS = ("len", "nul1", "type", "gen", "start", "count", "code", "lng", "total", "ordt",
              "ligt", "nligt", "nctoc")


def _mobi_records(f):
    """File PalmDB (MOBI) đang mở -> (hàm đọc record thứ i, số record)."""
    head = f.read(78)
    if len(head) < 78 or head[60:68] != b"BOOKMOBI":
        raise NotSimple("không phải file MOBI (thiếu chữ ký BOOKMOBI)")
    n = struct.unpack(">H", head[76:78])[0]
    tbl = f.read(8 * n)
    size = f.seek(0, 2)
    if n < 2 or len(tbl) < 8 * n:
        raise NotSimple("file MOBI hỏng (bảng record cụt)")
    offs = [struct.unpack_from(">I", tbl, 8 * i)[0] for i in range(n)] + [size]
    if any(a > b for a, b in zip(offs, offs[1:])):
        raise NotSimple("file MOBI hỏng (bảng record sai thứ tự)")

    def rec(i):
        if not 0 <= i < n:
            raise NotSimple(f"file MOBI hỏng (trỏ tới record {i}, file chỉ có {n})")
        f.seek(offs[i])
        return f.read(offs[i + 1] - offs[i])
    return rec, n


def _trailing(r, flags):
    """Số byte "trailing entries" cuối 1 record text (cờ extra_flags của header MOBI) — phải
    cắt trước khi giải nén. Mỗi bit 1..15 = 1 mục, độ dài ghi ngược từ cuối (7 bit/byte, byte
    mang bit 0x80 là byte đầu); bit 0 = phần dư ký tự nhiều byte."""
    num, size, t = 0, len(r), flags >> 1
    while t:
        if t & 1:
            val = shift = 0
            pos = size - num
            while pos > 0:
                b = r[pos - 1]
                val |= (b & 0x7F) << shift
                shift += 7
                pos -= 1
                if b & 0x80 or shift >= 28:
                    break
            num += val
        t >>= 1
    if flags & 1 and size > num:
        num += (r[size - num - 1] & 3) + 1
    return min(num, size)


def _palmdoc(d):
    """Giải nén PalmDOC (LZ77 kiểu Palm) — kiểu nén text của MOBI. Hỏng -> IndexError."""
    out = bytearray()
    i, n = 0, len(d)
    while i < n:
        c = d[i]
        i += 1
        if c == 0 or 9 <= c <= 0x7F:
            out.append(c)
        elif c <= 8:
            out += d[i:i + c]
            i += c
        elif c >= 0xC0:
            out += bytes((0x20, c ^ 0x80))
        else:
            c = (c << 8) | d[i]
            i += 1
            dist, ln = (c >> 3) & 0x7FF, (c & 7) + 3
            if not 0 < dist <= len(out):
                raise IndexError("PalmDOC trỏ ngược quá đầu")
            for _ in range(ln):
                out.append(out[-dist])
    return bytes(out)


def _vwi(d, o):
    """Số độ dài thay đổi tại d[o] (7 bit/byte, byte cuối mang bit 0x80) -> (số byte, giá trị)."""
    v = c = 0
    while True:
        b = d[o + c]
        c += 1
        v = (v << 7) | (b & 0x7F)
        if b & 0x80:
            return c, v


def _indx_head(d):
    if d[:4] != b"INDX":
        raise ValueError("thiếu INDX")
    return dict(zip(INDX_WORDS, struct.unpack_from(f">{len(INDX_WORDS)}L", d, 4)))


def _tagmap(cbc, table, d, start, end):
    """Các thẻ của 1 mục index: {mã thẻ: [giá trị]} (theo bảng TAGX + `cbc` byte điều khiển)."""
    tags, out, ci, ds = [], {}, 0, start + cbc
    for tag, per, mask, endf in table:
        if endf == 1:
            ci += 1
            continue
        v = d[start + ci] & mask
        if not v:
            continue
        if v == mask and bin(mask).count("1") > 1:     # độ dài (byte) ghi riêng ngay sau
            c, v = _vwi(d, ds)
            ds += c
            tags.append((tag, None, v, per))
        else:
            while not mask & 1:
                mask >>= 1
                v >>= 1
            tags.append((tag, v, None, per))
    for tag, cnt, nbytes, per in tags:
        vals = []
        if cnt is not None:
            for _ in range(cnt * per):
                c, x = _vwi(d, ds)
                ds += c
                vals.append(x)
        else:
            used = 0
            while used < nbytes:
                c, x = _vwi(d, ds)
                ds += c
                used += c
                vals.append(x)
        out[tag] = vals
    if ds > end:
        raise ValueError("mục index tràn")
    return out


def _ncx(rec, idx):
    """Mục lục NCX (index bắt đầu ở record `idx`) -> [(cấp, vị trí trong text, nhãn)]. Thẻ: 1 =
    vị trí (filepos), 3 = nhãn (offset trong CNCX), 4 = cấp."""
    d0 = rec(idx)
    h = _indx_head(d0)
    tx = h["len"]
    if d0[tx:tx + 4] != b"TAGX":
        raise ValueError("thiếu TAGX")
    feo, cbc = struct.unpack_from(">LL", d0, tx + 4)
    table = [tuple(d0[tx + i:tx + i + 4]) for i in range(12, feo, 4)]
    cncx = {}
    for k in range(h["nctoc"]):
        d, o = rec(idx + h["count"] + 1 + k), 0
        while o < len(d) and d[o]:
            c, ln = _vwi(d, o)
            cncx[k * 0x10000 + o] = d[o + c:o + c + ln].decode("utf-8", "replace").strip()
            o += c + ln
    out = []
    for i in range(1, h["count"] + 1):
        d = rec(idx + i)
        hh = _indx_head(d)
        pos = [struct.unpack_from(">H", d, hh["start"] + 4 + 2 * j)[0] for j in range(hh["count"])]
        for s, e in zip(pos, pos[1:] + [hh["start"]]):
            tags = _tagmap(cbc, table, d, s + 1 + d[s], e)
            if 1 in tags:
                out.append((tags.get(4, [0])[0], tags[1][0], cncx.get(tags.get(3, [-1])[0], "")))
    return out


def mobi_book(path):
    """Cấu trúc 1 truyện MOBI (chưa đọc ảnh) -> (recs, toc, warns): recs = [số record ảnh] theo
    thứ tự trang; toc = [(nhãn, trang đầu đếm từ 0)] các mục cấp ngoài cùng của mục lục, xếp
    theo trang, mục đầu luôn từ trang 0 (rỗng = không có mục lục). Không đọc được / không phải
    truyện tranh -> NotSimple."""
    warns = set()
    with open(path, "rb") as f:
        rec, n = _mobi_records(f)
        r0 = rec(0)
        if len(r0) < 132 or r0[16:20] != b"MOBI":
            raise NotSimple("không phải file MOBI (thiếu header MOBI)")
        comp, _, _, ntext, _, enc = struct.unpack_from(">HHIHHH", r0)
        hl, ver = struct.unpack_from(">I", r0, 20)[0], struct.unpack_from(">I", r0, 36)[0]
        if enc:
            raise NotSimple("sách có DRM (khoá bản quyền Kindle) — không mở được")
        if ver >= 8:
            raise NotSimple("sách chỉ có định dạng KF8 (AZW3) — chưa hỗ trợ; xuất lại bằng KCC "
                            "kiểu MOBI")
        if comp not in (1, 2):
            raise NotSimple("text nén kiểu " + ("HUFF/CDIC" if comp == 17480 else str(comp))
                            + " — chưa hỗ trợ")
        first_img = struct.unpack_from(">I", r0, 108)[0]
        flags = struct.unpack_from(">H", r0, 242)[0] if hl >= 0xE4 and len(r0) >= 244 else 0
        ncx = struct.unpack_from(">I", r0, 244)[0] if hl >= 0xE8 and len(r0) >= 248 else NCX_NONE
        text = bytearray()
        for i in range(1, ntext + 1):
            r = rec(i)
            r = r[:len(r) - _trailing(r, flags)]
            try:
                text += _palmdoc(r) if comp == 2 else r
            except IndexError:
                raise NotSimple(f"file MOBI hỏng (giải nén text record {i} lỗi)") from None
        tags = [(m.start(), int(m.group(1))) for m in IMG_TAG_RE.finditer(text)]
        if not tags:
            raise NotSimple("sách không có ảnh trang nào — không phải truyện tranh")
        chars = len(re.sub(rb"\s+", b"", re.sub(rb"<[^>]*>", b"", bytes(text))))
        if chars > MOBI_TEXT_MAX:
            raise NotSimple(f"sách có {chars} ký tự chữ — không phải truyện tranh dạng ảnh (chỉ "
                            f"lấy ảnh sẽ mất chữ)")
        recs = [first_img + k - 1 for _, k in tags]
        for k, r in enumerate(recs, 1):
            if not 0 < r < n:
                raise NotSimple(f"file MOBI hỏng (trang {k} trỏ tới record {r}, file có {n})")
        entries = []
        if ncx != NCX_NONE:
            try:
                entries = _ncx(rec, ncx)
            except Exception as e:
                warns.add(f"mục lục hỏng ({e.__class__.__name__}: {e}) — bỏ qua mục lục")

    starts = [s for s, _ in tags]
    top = sorted((fp, label) for depth, fp, label in entries if depth == 0)
    if len(top) < len(entries):
        warns.add("mục lục nhiều cấp — chia chương theo cấp ngoài cùng")
    toc = []
    for fp, label in top:
        pg = bisect.bisect_left(starts, fp)     # trang đầu tiên bắt đầu từ vị trí mục trỏ tới
        if pg >= len(starts):
            warns.add(f"mục lục '{label}' trỏ ra sau trang cuối — bỏ")
        elif toc and toc[-1][1] == pg:
            warns.add(f"mục lục '{label}' cùng trang với '{toc[-1][0]}' — gộp")
        else:
            toc.append((label, pg))
    if toc and toc[0][1]:
        warns.add(f"{toc[0][1]} trang trước mục đầu tiên của mục lục — gộp vào '{toc[0][0]}'")
        toc[0] = (toc[0][0], 0)
    return recs, toc, warns


def mobi_outs(stem, toc, warns):
    """Thư mục chương của 1 truyện MOBI -> [(tên, trang đầu)]. Mục lục ≥ 2 mục: mỗi mục 1
    'Chapter NN' (số từ nhãn mục; nhãn thiếu số / số không tăng dần -> 01, 02… theo thứ tự);
    không có -> cả sách 1 'Tập NN' (số từ tên file, như PDF/CBZ). None = tên file không có số."""
    if len(toc) < 2:
        name = chapter_name(stem)
        return [(name, 0)] if name else None
    nums = [_num(label) for label, _ in toc]
    if all(nums) and all(float(a) < float(b) for a, b in zip(nums, nums[1:])):
        return [(chapter_name(label, "Chapter"), pg) for label, pg in toc]
    warns.add("nhãn mục lục thiếu số hoặc số không tăng dần — đặt tên chương 01, 02… theo thứ tự")
    return [(f"Chapter {k:02d}", pg) for k, (_, pg) in enumerate(toc, 1)]


def mobi_pages(path, recs):
    """[(bytes, (W, H), đuôi)] các trang MOBI theo thứ tự sách — bytes ảnh chép NGUYÊN TRẠNG,
    kiểm giải mã được ngay lúc đọc (như CBZ, để --dry-run cũng bắt được ảnh hỏng)."""
    pages = []
    with open(path, "rb") as f:
        rec, _ = _mobi_records(f)
        for k, r in enumerate(recs, 1):
            data = rec(r)
            verdict, detail = check_image_bytes(data, who=f"{path.name} trang {k}")
            if verdict != "ok":
                raise NotSimple(f"trang {k} (record {r}): ảnh lỗi ({verdict}: {detail})")
            fmt = sniff_format(data)
            if fmt is None:
                raise NotSimple(f"trang {k} (record {r}): định dạng ảnh lạ")
            wh = (0, 0)
            if Image is not None:
                with Image.open(io.BytesIO(data)) as im:
                    wh = im.size
            pages.append((data, wh, ".jpg" if fmt == "jpeg" else f".{fmt}"))
    return pages


def _natkey(s):
    """Sắp tự nhiên: 'x 2' < 'x 10'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def _key(p):
    """So đường dẫn kiểu Windows: không phân biệt hoa/thường, dấu dựng sẵn/tổ hợp."""
    return unicodedata.normalize("NFC", str(p)).casefold()


def find_sources(targets):
    """Danh sách PDF/CBZ/MOBI từ đối số (file hoặc folder — tìm cả folder con, bỏ folder
    chấm-đầu như .pdf-goc). Không đối số = cả downloads/."""
    out = []
    for t in targets or [str(DOWNLOADS)]:
        p = Path(t).resolve()
        if p.is_file():
            if p.suffix.lower() in SRC_EXTS:
                out.append(p)
            else:
                print(f"  ! Bỏ qua (không phải PDF/CBZ/MOBI): {p}")
        elif p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs[:] = [x for x in dirs if not x.startswith(".")]
                out += [Path(root) / x for x in files if x.lower().endswith(SRC_EXTS)]
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
    - hoặc đánh số cách đều từ 0/1: liên tiếp 1, 2, 3… hoặc bước k 00, 03, 06… (bước > 1
      cần ≥ 3 phần mới chắc là cách đều — 2 số '0, 17' thì bước nào cũng khớp).
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
    step = seq[1] - seq[0] if len(seq) > 1 else 1
    if step < 1 or (step > 1 and len(nums) < 3):
        return False
    return (seq[0] in ((step, step + 1) if nums[0] is None else (0, 1))
            and seq == list(range(seq[0], seq[0] + step * len(seq), step)))


class Job:
    """1 nguồn cần nhập: các PDF `items` [(pdf, số|None)] theo thứ tự (hoặc 1 CBZ / MOBI) ->
    thư mục <folder truyện>/<name>; MOBI có mục lục -> nhiều thư mục `outs` [(tên, trang đầu)]
    (`recs` = record ảnh từng trang, `warns` = lưu ý lúc đọc cấu trúc). `src` = thứ được cất vào
    .pdf-goc/ (.cbz-goc/, .mobi-goc/) sau khi xong: file lẻ hoặc CẢ folder các phần (gộp — 1
    lần đổi tên, bị ngắt giữa chừng thì các phần vẫn đủ ở 1 chỗ)."""

    def __init__(self, items, name, src, merged, outs=None, recs=None, warns=()):
        self.items, self.name, self.src, self.merged = items, name, src, merged
        ext = src.suffix.lower()
        self.kind = "pdf" if merged or ext == ".pdf" else "cbz" if ext == ".cbz" else "mobi"
        self.raw = self.kind != "pdf"     # ảnh chép nguyên trạng từ file (CBZ/MOBI)
        self.outs = outs or [(name, 0)]
        self.recs, self.warns = recs, set(warns)
        self.orig_dir = {"pdf": ORIG_DIR, "cbz": CBZ_ORIG_DIR, "mobi": MOBI_ORIG_DIR}[self.kind]
        self.what = "folder PDF gốc" if merged else f"{self.kind.upper()} gốc"
        self.series = src.parent
        self.dests = [self.series / nm for nm, _ in self.outs]
        self.where = f"{self.series.name}\\{src.name}" + ("\\" if merged else "")
        self.label = self.where + (f"  (gộp {len(items)} file PDF)" if merged else
                                   f"  (mục lục {len(self.outs)} chương)" if len(self.outs) > 1
                                   else "")


_FAILS = []     # [(nguồn, lý do)] -> mục "Các tập lỗi" cuối bảng


def _fail(where, why, hint=None, nested=False):
    """In 1 lỗi (`nested` = dòng con dưới tên tập) + ghi vào mục "Các tập lỗi". Trả False."""
    tail = f" — {hint}" if hint else ""
    print(f"  ✗ {why}{tail}" if nested else f"✗ {where}: {why}{tail}")
    _FAILS.append((where, why))
    return False


def plan_jobs(srcs):
    """Chia PDF/CBZ thành các tập theo bố cục (xem đầu file). Lỗi bố cục -> in ra, không lập
    tập. Trả (jobs, số nguồn bị từ chối)."""
    jobs, bad, folders = [], 0, {}
    for pdf in srcs:
        depth = len(pdf.relative_to(DOWNLOADS).parts) if _under(pdf, DOWNLOADS) else 2
        if depth == 1:
            bad += 1
            _fail(pdf.name, "đang nằm ngay downloads\\",
                  "tạo folder truyện, bỏ file vào đó rồi chạy lại")
        elif depth == 2 and pdf.suffix.lower() in MOBI_EXTS:
            where = f"{pdf.parent.name}\\{pdf.name}"
            try:
                recs, toc, warns = mobi_book(pdf)
            except NotSimple as e:
                bad += 1
                _fail(where, str(e), "bỏ qua")
                continue
            except Exception as e:      # không đọc được file / cấu trúc lạ
                bad += 1
                _fail(where, f"không đọc được MOBI ({e.__class__.__name__}: {e})")
                continue
            outs = mobi_outs(pdf.stem, toc, warns)
            if outs is None:
                bad += 1
                _fail(where, "sách không có mục lục và tên file không có số tập",
                      f"đổi tên (vd 'Tập 3{pdf.suffix.lower()}') rồi chạy lại")
            else:
                jobs.append(Job([(pdf, None)], outs[0][0], pdf, merged=False, outs=outs,
                                recs=recs, warns=warns))
        elif depth == 2:
            name = chapter_name(pdf.stem)
            if name is None:
                bad += 1
                _fail(f"{pdf.parent.name}\\{pdf.name}", "tên file không có số tập",
                      f"đổi tên (vd 'Tập 3{pdf.suffix.lower()}') rồi chạy lại")
            else:
                jobs.append(Job([(pdf, None)], name, pdf, merged=False))
        elif depth == 3 and pdf.suffix.lower() != ".pdf":
            kind = pdf.suffix[1:].upper()
            bad += 1
            _fail(str(pdf.relative_to(DOWNLOADS)), f"{kind} nằm trong folder con",
                  f"{kind} phải nằm thẳng trong folder truyện (1 file = 1 nguồn, không gộp)")
        elif depth == 3:
            folders.setdefault(pdf.parent, []).append(pdf)
        else:
            bad += 1
            _fail(str(pdf.relative_to(DOWNLOADS)), "nằm quá sâu",
                  "PDF phải nằm thẳng trong folder truyện, hoặc trong 1 folder con của truyện "
                  "(= 1 tập bị tách nhiều file)")

    for folder, picked in folders.items():
        label = f"{folder.parent.name}\\{folder.name}\\"
        try:
            entries = list(os.scandir(folder))
        except OSError as e:
            bad += 1
            _fail(label, f"không đọc được folder ({e.strerror or e})")
            continue
        parts = sorted((Path(e.path) for e in entries
                        if e.is_file() and e.name.lower().endswith(".pdf")), key=_natkey)
        other = [e.name for e in entries if not e.is_file()
                 or not (e.name.lower().endswith(".pdf") or e.name.lower() in SYS_FILES)]
        name = chapter_name(folder.name)
        if other:
            bad += 1
            _fail(label, f"ngoài PDF còn có {', '.join(other[:5])}{'…' if len(other) > 5 else ''}",
                  "folder con chỉ được chứa các file PDF của 1 tập (sẽ gộp thành 1 chương)")
            continue
        if name is None:
            bad += 1
            _fail(label, "tên folder không có số tập",
                  "đổi tên (vd '14 - <tên tập>') rồi chạy lại")
            continue
        if _key(folder.name) == _key(name):
            bad += 1
            _fail(label, "folder chứa PDF trùng tên chương sẽ tạo",
                  f"đổi tên folder (vd '{name.split()[-1]} - <tên tập>') rồi chạy lại")
            continue
        try:
            items = order_parts(parts)
        except ValueError as e:
            bad += 1
            _fail(label, str(e), "không biết thứ tự các phần, đổi tên rồi chạy lại")
            continue
        if len(picked) < len(parts):
            print(f"! {label}: mới chọn {len(picked)}/{len(parts)} file — tập gộp luôn lấy "
                  f"CẢ folder")
        jobs.append(Job(items, name, folder, merged=True))

    # 2 nguồn cùng ra 1 thư mục (vd 'Long 14.pdf' + folder '14 - …') -> loại cả 2.
    by_dest = {}
    for j in jobs:
        for d in j.dests:
            by_dest.setdefault(_key(d), (d.name, []))[1].append(j)
    clash = []
    for name, group in by_dest.values():
        if len(group) > 1:
            print(f"✗ {len(group)} nguồn cùng ra '{name}' trong '{group[0].series.name}': "
                  + ", ".join(j.src.name for j in group) + " — đổi tên cho khác số rồi chạy lại")
            for j in group:
                _FAILS.append((j.where, f"trùng đích '{name}' với " + ", ".join(
                    o.src.name for o in group if o is not j)))
                if j not in clash:
                    clash.append(j)
    bad += len(clash)
    jobs = [j for j in jobs if j not in clash]
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


def _stash(src, orig_dir):
    """Cất nguồn (file PDF/CBZ / cả folder gộp) vào <folder truyện>/<orig_dir>/ bằng 1 lần đổi
    tên (trùng tên thì thêm ' (2)'...)."""
    dest_dir = src.parent / orig_dir
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


def _same_as_src(folder, pages):
    """Thư mục đã có có đúng là bản tách từ nguồn này không (cùng số ảnh, từng byte)."""
    try:
        names = sorted((x for x in os.listdir(folder) if (folder / x).is_file()), key=_natkey)
    except OSError:
        return False
    if len(names) != len(pages):
        return False
    for name, (data, _, _) in zip(names, pages):
        try:
            if (folder / name).read_bytes() != data:
                return False
        except OSError:
            return False
    return True


def _finish(job, msg):
    """Cất nguồn vào .pdf-goc/ (.cbz-goc/) + in kết quả. Cất không được (file/folder đang bị
    chương trình khác mở) -> chương đã tách vẫn giữ; chạy lại thì tool thấy 'đã tách từ trước'
    và chỉ cất."""
    what = job.what
    try:
        moved = _stash(job.src, job.orig_dir)
    except OSError as e:
        print(f"{msg}; NHƯNG chưa cất được {what} vào {job.orig_dir}/ ({e.strerror or e}) — "
              f"đóng chương trình đang mở nó rồi chạy lại")
        _FAILS.append((job.where, f"đã tách nhưng chưa cất được {what} vào {job.orig_dir}/ "
                                  f"({e.strerror or e})"))
        return False
    print(f"{msg}; {what} -> {moved.parent.name}/{moved.name}{'/' if job.merged else ''}")
    return True


def _describe(pages, job):
    """'49 trang JPEG 1072×1448, 19.6MB' — mô tả 1 thư mục chương sắp ghi."""
    wide = any(w > h for _, (w, h), _ in pages)
    sizes = {wh for _, wh, _ in pages}
    size_txt = (f"{next(iter(sizes))[0]}×{next(iter(sizes))[1]}" if len(sizes) == 1
                else f"{len(sizes)} cỡ khác nhau")
    if job.raw and len(sizes) == 2 and wide:    # trang dọc + trang đôi: in cỡ trang dọc
        size_txt = "{}×{}".format(*next(wh for wh in sizes if wh[0] <= wh[1])) + " (+ trang đôi)"
    exts = sorted({ext for _, _, ext in pages})
    png = sum(ext == ".png" for _, _, ext in pages)
    kind = (" + ".join(e[1:].upper().replace("JPG", "JPEG") for e in exts) if job.raw
            else f"JPEG + {png} PNG" if png else "JPEG")
    total = sum(len(dta) for dta, _, _ in pages)
    return f"{len(pages)} trang {kind} {size_txt}, {total / 1048576:.1f}MB"


def _cover(series, n, page, dry_run):
    """--bia: ghi trang `n` thành cover.<đuôi> trong folder truyện (reader ưu tiên file cover.*
    làm bìa). Đã có cover.*: giống hệt thì thôi, khác thì KHÔNG ghi đè. Trả dòng báo."""
    data, _, ext = page
    try:
        olds = sorted(e.name for e in os.scandir(series) if e.is_file()
                      and os.path.splitext(e.name)[0].lower() == "cover"
                      and os.path.splitext(e.name)[1].lower() in CBZ_IMG_EXTS)
    except OSError as e:
        return f"  ! bìa: không đọc được folder truyện ({e.strerror or e})"
    for name in olds:
        try:
            if (series / name).read_bytes() == data:
                return f"  = bìa: {name} đã là trang {n}"
        except OSError:
            pass
    if olds:
        return (f"  ! bìa: đã có {olds[0]} (ảnh khác) — không ghi đè; muốn đổi thì xoá nó rồi "
                f"chạy lại, hoặc đổi bìa trên reader")
    dest = series / f"cover{ext}"
    if not dry_run:
        tmp = dest.with_name(dest.name + ".tmp")
        try:
            tmp.write_bytes(data)
            os.replace(tmp, dest)
        except OSError as e:
            return f"  ! bìa: không ghi được {dest.name} ({e.strerror or e})"
    return f"  ✓ bìa: trang {n} -> {dest.name}"


def import_job(job, dry_run, cover=None):
    """Tách 1 nguồn (1 tập; MOBI có mục lục -> nhiều chương). `cover` = số trang (đếm từ 1 trong
    cả nguồn) ghi thành cover.* của folder truyện. Trả True nếu xong (hoặc dry-run kiểm đạt),
    False nếu lỗi/bỏ qua."""
    t0 = time.time()

    def fail(why, hint=None):
        return _fail(job.where, why, hint, nested=True)

    warns, pages, counts = set(job.warns), [], []
    if job.kind == "cbz":
        try:
            pages = cbz_pages(job.src, warns)
        except NotSimple as e:
            return fail(str(e), "chưa tách được (không đụng gì)")
        except Exception as e:      # ZIP hỏng / sai CRC / không đọc được file
            return fail(f"không đọc được CBZ ({e.__class__.__name__}: {e})")
    elif job.kind == "mobi":
        try:
            pages = mobi_pages(job.src, job.recs)
        except NotSimple as e:
            return fail(str(e), "chưa tách được (không đụng gì)")
        except Exception as e:      # file đổi/hỏng từ lúc đọc cấu trúc, không đọc được
            return fail(f"không đọc được MOBI ({e.__class__.__name__}: {e})")
    else:
        from pypdf import PdfReader     # main() đã kiểm có pypdf
        from pypdf.errors import DependencyError
        for pdf, _ in job.items:
            who = f"{pdf.name}: " if job.merged else ""
            try:
                reader = PdfReader(str(pdf))
                if reader.is_encrypted and not reader.decrypt(""):
                    return fail(f"{who}PDF có mật khẩu", "bỏ qua")
                n0 = len(pages)
                for i, page in enumerate(reader.pages, 1):
                    try:
                        pages.append(page_jpeg(page, warns))
                    except NotSimple as e:
                        return fail(f"{who}trang {i}: {e}", "chưa tách được (không đụng gì)")
            except DependencyError as e:
                # PDF mã hoá AES (vd Acrobat khoá cấm in/chép, mở không cần mật khẩu): pypdf cần
                # `cryptography` để giải mã — thiếu thì nó báo lúc kiểm mật khẩu (R6) hoặc lúc đọc
                # stream (AES-128). Mã hoá RC4 cũ thì pypdf tự giải được, không tới đây.
                if "AES" not in str(e):
                    return fail(f"{who}không đọc được PDF (thiếu thư viện: {e})")
                return fail(f"{who}PDF mã hoá AES, thiếu thư viện cryptography để giải mã",
                            "cài:  python -m pip install cryptography  (hoặc chạy cap-nhat.bat) rồi "
                            "chạy lại")
            except Exception as e:
                return fail(f"{who}không đọc được PDF ({e.__class__.__name__}: {e})")
            counts.append(len(pages) - n0)
            if not counts[-1]:
                return fail(f"{who}PDF không có trang nào")
    if job.merged:
        for k, ((pdf, _), n) in enumerate(zip(job.items, counts), 1):
            print(f"    {k}. {pdf.name}  ({n} trang)")
        if not check_order(job.items, counts):
            return fail("số trong tên các phần không khớp số trang",
                        "phải là trang bắt đầu của phần (0/31/61…) hoặc đánh số cách đều 1, 2, "
                        "3… / 00, 03, 06…. Thiếu phần hoặc đặt tên sai? Kiểm lại rồi chạy lại "
                        "(không đụng gì)")
    for w in sorted(warns):
        print(f"  ! {w}")
    png = [i for i, (_, _, ext) in enumerate(pages, 1) if ext == ".png"]
    if png and not job.raw:
        print(f"  ! {len(png)} trang có vùng trong suốt thật -> lưu PNG đã ghép nền trắng (y như "
              f"PDF hiển thị): trang {', '.join(map(str, png))}")
    wide = [i for i, (_, (w, h), _) in enumerate(pages, 1) if w > h]
    if wide and job.raw:
        print(f"  ! {len(wide)} trang ngang (thường là trang đôi, giữ nguyên 1 ảnh): trang "
              f"{', '.join(map(str, wide))}")
    if cover is not None and not 1 <= cover <= len(pages):
        return fail(f"--bia {cover}: nguồn chỉ có {len(pages)} trang", "không đụng gì")
    what, multi = job.what, len(job.outs) > 1

    # Kiểm hết các thư mục đích TRƯỚC khi ghi: đã có + giống hệt = xong từ lần trước (bỏ qua),
    # đã có + khác = dừng cả nguồn, không ghi chương nào.
    ends = [a for _, a in job.outs[1:]] + [len(pages)]
    plan = []       # [(tên, trang, mô tả, đã có)]
    for (name, a), b in zip(job.outs, ends):
        pgs = pages[a:b]
        dest = job.series / name
        done = dest.exists()
        if done and not _same_as_src(dest, pgs):
            return fail(f"đã có thư mục '{name}' (nội dung khác nguồn này)",
                        f"không ghi đè. Đổi tên/xoá thư mục đó hoặc đổi tên "
                        f"{'folder' if job.merged else 'file ' + job.src.suffix[1:].upper()} rồi "
                        f"chạy lại")
        plan.append((name, pgs, _describe(pgs, job), done))
    all_done = all(done for *_, done in plan)

    if dry_run:
        for k, (name, _, info, done) in enumerate(plan, 1):
            tail = (f" — sẽ chỉ cất {what} vào {job.orig_dir}/" if all_done and k == len(plan)
                    else "")
            print((f"  = '{name}' đã tách từ trước ({info})" if done
                   else f"  ✓ -> '{name}/' ({info})") + tail)
        if cover is not None:
            print(_cover(job.series, cover, pages[cover - 1], dry_run=True))
        return True

    # Ghi vào downloads/.pdf-tmp/ (reader không quét), kiểm đủ TẤT CẢ chương rồi mới đổi tên
    # sang chỗ thật -> reader không bao giờ thấy chương dở / nguồn mới nhập một nửa.
    tmp_root = DOWNLOADS / TMP_DIR if _under(job.src, DOWNLOADS) else job.series / TMP_DIR
    tmps, moved = [], 0
    try:
        for name, pgs, _, done in plan:
            if done:
                continue
            tmp = tmp_root / f"{job.series.name} - {name}"
            if tmp.exists():
                shutil.rmtree(tmp)          # bản dở của lần chạy trước bị ngắt
            tmp.mkdir(parents=True)
            tmps.append((tmp, job.series / name))
            width = max(3, len(str(len(pgs))))
            for i, (data, _, ext) in enumerate(pgs, 1):
                verdict, detail = check_image_bytes(data, who=f"{job.src.name} {name} trang {i}")
                if verdict != "ok":
                    raise RuntimeError(f"{name + ' ' if multi else ''}trang {i}: ảnh lỗi "
                                       f"({verdict}: {detail})")
                (tmp / f"{i:0{width}d}{ext}").write_bytes(data)
            if len(os.listdir(tmp)) != len(pgs):
                raise RuntimeError(f"{name + ': ' if multi else ''}số ảnh ghi ra lệch số trang")
        for tmp, dest in tmps:
            _move(tmp, dest)
            moved += 1
    except Exception as e:
        for tmp, _ in tmps:
            shutil.rmtree(tmp, ignore_errors=True)
        return fail(str(e), "đã huỷ, không đụng gì" if not moved else
                    f"đã chuyển {moved}/{len(tmps)} chương vào chỗ — chạy lại để làm nốt")
    finally:
        try:
            tmp_root.rmdir()        # chỉ xoá khi rỗng
        except OSError:
            pass

    secs = time.time() - t0
    if multi:
        for name, _, info, done in plan:
            print(f"  = '{name}' đã tách từ trước ({info})" if done
                  else f"  ✓ -> '{name}/' ({info})")
        msg = (f"  = cả {len(plan)} chương đã tách từ trước" if all_done else
               f"  ✓ {len(tmps)}/{len(plan)} chương mới, {len(pages)} trang ({secs:.1f}s)")
    else:
        name, _, info, done = plan[0]
        msg = (f"  = '{name}' đã tách từ trước" if done
               else f"  ✓ -> '{name}/' ({info}, {secs:.1f}s)")
    ok = _finish(job, msg)
    if cover is not None:
        print(_cover(job.series, cover, pages[cover - 1], dry_run=False))
    return ok


def main():
    ap = argparse.ArgumentParser(description="Tách PDF (mỗi trang 1 ảnh JPEG) / CBZ / MOBI thành "
                                             "thư mục chương cho reader. PDF trong folder con "
                                             "của truyện = 1 tập bị tách, gộp lại.")
    ap.add_argument("targets", nargs="*",
                    help="file PDF/CBZ/MOBI / folder (mặc định: cả downloads/)")
    ap.add_argument("--dry-run", action="store_true", help="chỉ kiểm + in kế hoạch, không ghi gì")
    ap.add_argument("--bia", type=int, metavar="N",
                    help="chép trang N (đếm từ 1 trong cả file) thành cover.* trong folder "
                         "truyện (chỉ khi nhập đúng 1 file)")
    args = ap.parse_args()

    srcs = find_sources(args.targets)
    if not srcs:
        print("Không thấy file PDF/CBZ/MOBI nào.")
        return 2
    if (any(p.suffix.lower() == ".pdf" for p in srcs)
            and importlib.util.find_spec("pypdf") is None):
        print("✗ Thiếu thư viện pypdf (để đọc PDF) — cài:  python -m pip install pypdf")
        return 2

    # Chia tập + chặn lỗi bố cục TRƯỚC khi đụng file nào.
    _FAILS.clear()
    jobs, bad = plan_jobs(srcs)
    if args.bia is not None and len(jobs) + bad != 1:
        print(f"✗ --bia chỉ dùng khi nhập đúng 1 file/tập (đang có {len(jobs) + bad})")
        return 2
    if any(not _under(j.src, DOWNLOADS) for j in jobs):
        print("! Lưu ý: reader chỉ đọc truyện trong downloads\\ — file ngoài đó tách xong "
              "phải tự chép vào.")
    ok = 0
    for job in jobs:
        print(job.label)
        ok += import_job(job, args.dry_run, args.bia)
    total = len(jobs) + bad
    bad = total - ok
    verb = "kiểm đạt" if args.dry_run else "xong"
    if _FAILS:
        print(f"\nCác tập lỗi ({len(_FAILS)}):")
        for where, why in _FAILS:
            print(f"  - {where}: {why}")
        if any("thiếu thư viện cryptography" in why for _, why in _FAILS):
            print("  -> Cài 1 lần cho máy này:  python -m pip install cryptography  (hoặc chạy "
                  "cap-nhat.bat) rồi chạy lại")
    print(f"\nTổng: {ok}/{total} tập {verb}" + (f", {bad} lỗi/bỏ qua" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
