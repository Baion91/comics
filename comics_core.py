#!/usr/bin/env python3
"""Động cơ tải truyện dùng chung cho MỌI site (Asura, Raven, ...).

File này KHÔNG biết gì về từng site cụ thể — mọi khác biệt (lấy danh sách
chương, lấy URL ảnh, ảnh bìa, referer) nằm trong các "provider" ở providers.py.
Muốn thêm site mới: viết 1 provider, KHÔNG đụng file này.

Chứa: van điều tốc PoliteGate + cầu dao 429, tải ảnh có resume, đóng .cbz,
--pack, và vòng lặp tải chung (run()).
"""

import io
import json
import random
import re
import sys
import threading
import time
import zipfile
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import warnings
# 'requests' cảnh báo urllib3/charset_normalizer mới hơn range nó từng test — vô hại
# (tải vẫn chạy bình thường). Ẩn để console sạch, KHÔNG đụng môi trường Python; mọi
# lỗi/cảnh báo khác vẫn hiện.
warnings.filterwarnings("ignore", message=r".*supported version.*")
import requests

# Pillow chỉ để KIỂM TRA ảnh (giải mã thử + đo độ phẳng), KHÔNG dùng để nén lại —
# byte gốc luôn được ghi nguyên trạng (giữ chính sách không lossy-chồng-lossy).
# Thiếu Pillow thì tầng giải mã tự hạ xuống chỉ kiểm chữ ký (magic bytes).
try:
    from PIL import Image, ImageFile
except ImportError:
    Image = ImageFile = None

# In được tiếng Việt trên console Windows (mặc định cp1252)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

session = requests.Session()
session.headers.update({"User-Agent": UA})

IMG_EXTS = {".webp", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".avif"}

# Đơn vị chương mà provider trả về cho engine. ref là "chìa" mờ để lấy ảnh:
# mỗi site tự sinh & tự hiểu (Asura = URL API chương, Raven = URL trang chương).
Chapter = namedtuple("Chapter", "number title ref")


# ============================================================================
# LÕI KIỂM TRA ẢNH DÙNG CHUNG (downloader inline + tool quét check_library.py)
# ----------------------------------------------------------------------------
# Triết lý: mức tự động tỉ lệ với độ chắc chắn của tín hiệu.
#   Tầng 1 (độ dài truyền tải) + Tầng 2 (chữ ký + giải mã) = gần như 0 nhầm -> tự
#     xử (chặn lúc tải / cách ly khi quét).
#   Tầng 4 (đen/phẳng) = có thể nhầm với tranh đen -> CHỈ báo, không tự xóa.
# Toàn bộ ở đây để Asura/Raven/tool quét đi chung một trọng tài, không lệch.
# ============================================================================

# .reader-meta/ nằm cạnh script (KHÔNG trong folder truyện) — chung chỗ với reader.
META_DIR = Path(__file__).resolve().parent / ".reader-meta"

# Định dạng Pillow chắc chắn giải mã được (có sẵn trong wheel). avif/heif tùy codec.
_DECODABLE = {"png", "jpeg", "gif", "bmp", "webp"}

# Ảnh cụt nhưng còn đọc được >= ngưỡng này thì CỨU VỚT (lưu lại) thay vì vứt cả trang:
# thà đọc được phần lớn còn hơn mất trắng cả trang (đúng như trình duyệt vẫn hiển thị).
SALVAGE_MIN = 0.50
RETRY_BROKEN = False   # True = thử lại cả những ảnh đã biết hỏng ở nguồn (cờ --retry-broken)

# ============================================================================
# BẮT CRASH TẦNG C (Pillow/libwebp/OpenSSL... segfault / access violation)
# ----------------------------------------------------------------------------
# `try/except` của Python KHÔNG bắt được lỗi tầng C: tiến trình biến mất KHÔNG để lại
# traceback — đúng kiểu "đang tải bỗng dừng, .bat in Xong". Ba lớp phòng thủ:
#   1) faulthandler: khi crash tầng C -> ghi C-stack vào crash-trace.txt (crash Ở ĐÂU).
#   2) 'breadcrumb': ghi ảnh đang giải mã ra đĩa TRƯỚC im.load(); phiên sau khởi động
#      thấy file còn sót -> log lại ảnh đang xử lý lúc chết (crash Ở ẢNH NÀO).
#   3) chặn trước 2 nguồn crash bộ nhớ hay gặp: file quá lớn / ảnh 'bom' kích thước khủng.
# ============================================================================
SAFE_MAX_BYTES = 64 * 1024 * 1024   # ảnh > 64MB: gần như chắc rác/bom -> không giải mã
SAFE_MAX_PIXELS = 60_000_000        # > 60 triệu điểm ảnh: load()/convert() dễ ngốn RAM -> né

CRASH_TRACE = META_DIR / "crash-trace.txt"
DECODING_FILE = META_DIR / "decoding-now.txt"
try:
    import faulthandler
    META_DIR.mkdir(parents=True, exist_ok=True)
    _crash_fp = open(CRASH_TRACE, "a", encoding="utf-8")
    faulthandler.enable(file=_crash_fp)   # giữ tham chiếu toàn cục để fd không bị đóng
except Exception:
    _crash_fp = None

_decoding_lock = threading.Lock()
_decoding_now = {}   # ident luồng -> mô tả ảnh nó ĐANG giải mã (bỏ khỏi dict khi xong)


def _set_decoding(ident, what):
    """Ghi/xoá breadcrumb ảnh-đang-giải-mã của 1 luồng, đồng bộ ngay ra đĩa. Crash tầng C
    giết cả tiến trình -> file DECODING_FILE còn sót chính là (các) ảnh thủ phạm."""
    with _decoding_lock:
        if what is None:
            _decoding_now.pop(ident, None)
        else:
            _decoding_now[ident] = what
        try:
            DECODING_FILE.write_text("\n".join(_decoding_now.values()), encoding="utf-8")
        except OSError:
            pass


@contextmanager
def _decoding(what):
    ident = threading.get_ident()
    _set_decoding(ident, what)
    try:
        yield
    finally:
        _set_decoding(ident, None)


def reap_decode_crash():
    """Đầu phiên tải: nếu breadcrumb còn sót -> phiên trước CHẾT khi đang giải mã (nghi
    crash tầng C). Ghi tên ảnh thủ phạm vào download-log + crash-trace rồi xoá cờ. CỐ Ý
    KHÔNG tự đánh dấu hỏng (tránh bỏ nhầm ảnh tốt của luồng còn lại) — chỉ nêu tên để
    đối chiếu cùng C-stack mà faulthandler đã ghi ngay phía trên trong crash-trace.txt."""
    try:
        left = DECODING_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if left:
        items = " | ".join(left.splitlines())
        append_log("⚠ PHIÊN TRƯỚC CHẾT giữa lúc giải mã ảnh (nghi crash tầng C) — "
                   f"ảnh đang xử lý lúc đó: {items}")
        try:
            with open(CRASH_TRACE, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Ảnh ĐANG GIẢI MÃ lúc phiên "
                        f"trước chết (đối chiếu C-stack phía trên):\n  {items}\n")
        except OSError:
            pass
    try:
        DECODING_FILE.unlink()
    except OSError:
        pass


class _DecodeGate:
    """Cho nhiều luồng giải mã NGHIÊM song song; khi cần giải mã KHOAN DUNG thì độc chiếm.

    Giải mã khoan dung phải bật cờ TOÀN CỤC `ImageFile.LOAD_TRUNCATED_IMAGES`, nếu để
    luồng khác giải mã nghiêm trúng lúc cờ đang bật thì ảnh cụt sẽ 'qua bài' oan —
    đúng thứ ta đang muốn bắt. Nên: nghiêm = nhiều luồng (như khóa đọc), khoan dung =
    độc quyền (như khóa ghi). Giải mã khoan dung rất hiếm nên không ảnh hưởng tốc độ.
    """

    def __init__(self):
        self.cv = threading.Condition()
        self.readers = 0
        self.lenient = False

    @contextmanager
    def strict(self):
        with self.cv:
            while self.lenient:
                self.cv.wait()
            self.readers += 1
        try:
            yield
        finally:
            with self.cv:
                self.readers -= 1
                if not self.readers:
                    self.cv.notify_all()

    @contextmanager
    def lenient_mode(self):
        with self.cv:
            while self.lenient or self.readers:
                self.cv.wait()
            self.lenient = True
        old = ImageFile.LOAD_TRUNCATED_IMAGES
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        try:
            yield
        finally:
            ImageFile.LOAD_TRUNCATED_IMAGES = old
            with self.cv:
                self.lenient = False
                self.cv.notify_all()


_gate = _DecodeGate()

# --- Sổ ghi nhận sự cố ảnh (dùng chung downloader + tool quét) ------------------
# {"salvaged": {path: {...}}, "source_broken": {path: {...}}}
#   salvaged     : ảnh cụt nhưng đã cứu được phần lớn -> CÓ file trên đĩa, đừng báo hỏng lại.
#   source_broken: ảnh hỏng ngay tại nguồn (tải lại vẫn y hệt) -> KHÔNG có file, đừng thử lại,
#                  và khuyết trang do nó là 'đã biết', không phải việc cần làm.
ISSUES_FILE = META_DIR / "image-issues.json"
_issues_lock = threading.Lock()
_issues_cache = None


def load_issues() -> dict:
    global _issues_cache
    with _issues_lock:
        if _issues_cache is None:
            try:
                d = json.loads(ISSUES_FILE.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                d = {}
            d.setdefault("salvaged", {})
            d.setdefault("source_broken", {})
            _issues_cache = d
        return _issues_cache


def record_issue(kind: str, dest: Path, info: dict):
    """Ghi 1 mục vào sổ (kind = 'salvaged' | 'source_broken') rồi lưu ngay ra đĩa."""
    d = load_issues()
    with _issues_lock:
        d.setdefault(kind, {})[str(Path(dest).resolve())] = {
            **info, "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        # mục này đã chuyển trạng thái -> bỏ khỏi nhóm còn lại cho khỏi mâu thuẫn
        other = "source_broken" if kind == "salvaged" else "salvaged"
        d.get(other, {}).pop(str(Path(dest).resolve()), None)
        try:
            META_DIR.mkdir(parents=True, exist_ok=True)
            tmp = ISSUES_FILE.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(ISSUES_FILE)
        except OSError:
            pass


def is_known_broken(dest: Path) -> bool:
    """Ảnh này đã được xác định hỏng-tại-nguồn từ trước? (để khỏi tải lại vô ích)"""
    return str(Path(dest).resolve()) in load_issues().get("source_broken", {})


SCRAMBLE_THRESH = 4.0   # ranh giới giữa vùng sạch (~1-2) và vùng tráo-ô (~9-22); xem ghi chú dưới


def _scramble_ratio(gray) -> float:
    """'Năng lượng đường nối' lớn nhất tại biên ô, chuẩn hóa theo nền, cho ảnh xám.

    comix.to (bản Official) chèn TRÁO Ô ở mỗi trang thứ 10: ảnh bị cắt thành lưới ô
    rồi xáo vị trí -> tại các bội số của bề rộng/cao ô xuất hiện đường nối tương phản
    mạnh. Đo trung bình |chênh lệch| giữa cột (và hàng) kề nhau TẠI các biên ô, chia
    cho nền chung. Ảnh sạch ~1-2; ảnh tráo ~9-22 (đo thực trên 9 trang xáo + 5 trang
    sạch của Farmer of Spirits) -> ngưỡng 4.0 tách chắc, biên an toàn rộng cả 2 phía.
    Chỉ dùng PIL (khỏi thêm numpy); các phép crop/Stat chạy ở lớp C nên nhanh."""
    from PIL import ImageChops, ImageStat
    w, h = gray.size
    best = 0.0
    # seam DỌC: chênh lệch giữa 2 cột kề nhau, đo tại biên ô x = k*(w/n)
    dv = ImageChops.difference(gray, ImageChops.offset(gray, -1, 0))
    base_v = ImageStat.Stat(dv).mean[0] or 0.001
    for n in (4, 5, 6, 8, 10):
        seams = []
        for k in range(1, n):
            x = int(round(k * w / n)) - 1
            if 1 <= x < w - 1:
                seams.append(ImageStat.Stat(dv.crop((x, 0, x + 1, h))).mean[0])
        if seams:
            best = max(best, (sum(seams) / len(seams)) / base_v)
    # seam NGANG: chênh lệch giữa 2 hàng kề nhau, đo tại biên ô y = k*(h/n)
    dh = ImageChops.difference(gray, ImageChops.offset(gray, 0, -1))
    base_h = ImageStat.Stat(dh).mean[0] or 0.001
    for n in (4, 5, 6, 8, 10):
        seams = []
        for k in range(1, n):
            y = int(round(k * h / n)) - 1
            if 1 <= y < h - 1:
                seams.append(ImageStat.Stat(dh.crop((0, y, w, y + 1))).mean[0])
        if seams:
            best = max(best, (sum(seams) / len(seams)) / base_h)
    return best


def looks_scrambled_bytes(data: bytes, thresh: float = SCRAMBLE_THRESH) -> bool:
    """Bytes ảnh này có dấu hiệu bị tráo ô (comix) không? Lỗi/thiếu Pillow -> False
    (tuyệt đối KHÔNG misflag ảnh thường thành hỏng)."""
    if Image is None:
        return False
    try:
        with Image.open(io.BytesIO(data)) as im:
            gray = im.convert("L")
        return _scramble_ratio(gray) >= thresh
    except Exception:
        return False


def looks_scrambled(path, thresh: float = SCRAMBLE_THRESH) -> bool:
    """File ảnh này có dấu hiệu bị tráo ô (comix) không? (xem [[comix-scramble-s-flag]])."""
    if Image is None:
        return False
    try:
        with Image.open(path) as im:
            gray = im.convert("L")
        return _scramble_ratio(gray) >= thresh
    except Exception:
        return False


def intact_fraction(data: bytes, who=None):
    """Ảnh cụt còn đọc được bao nhiêu? Trả (tỉ lệ 0..1, rộng, cao) hoặc None nếu chịu.

    Pillow bù phần chưa giải mã bằng một màu phẳng; dò từ đáy lên tới chỗ hết phẳng
    là ranh giới phần còn nguyên (nhị phân, ~log(h) lần cắt nên rất nhanh).
    """
    if Image is None or ImageFile is None:
        return None
    try:
        with _gate.lenient_mode():
            with Image.open(io.BytesIO(data)) as im:
                w, h = im.size
                if w * h > SAFE_MAX_PIXELS:
                    return None
                with _decoding((who or "?") + " [cứu-vớt]"):  # breadcrumb cho decode khoan dung
                    im.load()
                    g = im.convert("L")
        w, h = g.size
        if h < 2:
            return None
        lo_v, hi_v = g.crop((0, h - 1, w, h)).getextrema()
        if lo_v != hi_v:
            return (1.0, w, h)  # đáy không phẳng -> không thấy vùng bị bù
        filler = lo_v
        lo, hi = 0, h
        while lo < hi:                       # tìm dòng đầu tiên mà từ đó xuống toàn màu bù
            mid = (lo + hi) // 2
            if g.crop((0, mid, w, h)).getextrema() == (filler, filler):
                hi = mid
            else:
                lo = mid + 1
        return (lo / h, w, h)
    except Exception:
        return None


def append_log(msg: str):
    """Ghi 1 dòng có mốc thời gian vào .reader-meta/download-log.txt (nhật ký tải)."""
    try:
        META_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(META_DIR / "download-log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {msg}\n")
    except OSError:
        pass  # log hỏng không được làm chết phiên tải


def sniff_format(data: bytes):
    """Nhận định dạng ảnh từ vài byte đầu (magic). None = không phải ảnh đã biết.

    Bắt gọn ca CDN trả trang HTML lỗi (status 200) hay file rỗng — đầu file sẽ
    không khớp chữ ký ảnh nào.
    """
    if len(data) < 12:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:2] == b"BM":
        return "bmp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:8] == b"ftyp":  # họ ISO-BMFF: avif/heif
        return "avif" if b"avif" in data[8:24] else "heif"
    return None


def uniform_frame(im, *, min_side=200, flat_range=8):
    """Tầng 4 — dò TRANG MỘT MÀU (cả khung gần như 1 mức xám: đen/trắng/xám phẳng).
    Trả (nhãn, chi tiết) nếu nghi, None nếu bình thường. Nhận ảnh PIL ĐÃ mở (giải mã
    1 lần dùng chung với tầng 2, không mở lại).

    CHỈ bắt cả-khung-một-màu — tín hiệu mạnh, cực hiếm, gần như không nhầm: tranh tác
    giả vẽ (kể cả đen) luôn có nét/nhiễu -> cực trị xám giãn rộng -> lọt. Luật cũ "dải
    đáy phẳng" ĐÃ BỎ (nó bắt nhầm lề trắng cuối trang — bố cục webtoon bình thường; mục
    tiêu đáy-đen-do-cụt thì tầng 1/2 lúc tải đã lo)."""
    if Image is None:
        return None
    try:
        g = im.convert("L")
        w, h = g.size
        if w < min_side or h < min_side:
            return None  # spacer/trang trí nhỏ — vốn một màu hợp lệ, bỏ qua
        lo, hi = g.getextrema()
        if hi - lo <= flat_range:
            shade = "đen" if hi < 24 else ("trắng" if lo > 231 else f"xám~{(lo + hi) // 2}")
            return ("trang một màu",
                    f"cả ảnh gần như một màu {shade} ({lo}-{hi}) — gần như không có nội dung")
    except Exception:
        return None  # decode lỗi là việc của tầng 2, không phải tầng này
    return None


def inspect_image_bytes(data: bytes, want_uniform: bool = False, who=None):
    """Kiểm 1 ảnh trong RAM, GIẢI MÃ ĐÚNG 1 LẦN. Trả (verdict, chi tiết, uniform).

    verdict:
      "ok"          - dùng được (giải mã trót lọt; hoặc chỉ có chữ ký khi thiếu Pillow)
      "empty"       - 0 byte
      "not_image"   - không có chữ ký ảnh (vd trang HTML lỗi)
      "corrupt"     - có chữ ký nhưng giải mã lỗi (cụt dữ liệu / hỏng)
      "unsupported" - định dạng đúng nhưng máy thiếu codec -> KHÔNG kết luận hỏng
    uniform: (nhãn, chi tiết) nếu want_uniform và ảnh một màu, ngược lại None.
    Người gọi loại bỏ {empty, not_image, corrupt}; giữ {ok, unsupported}.
    """
    if not data:
        return ("empty", "0 byte", None)
    if len(data) > SAFE_MAX_BYTES:   # chặn TRƯỚC decode: file khổng lồ dễ làm codec C sập
        return ("corrupt", f"ảnh {len(data)} byte > {SAFE_MAX_BYTES} — bỏ để tránh crash bộ nhớ", None)
    fmt = sniff_format(data)
    if fmt is None:
        return ("not_image", f"không nhận ra chữ ký ảnh (đầu file: {data[:12]!r})", None)
    if Image is None:
        return ("ok", f"{fmt} (không có Pillow — chỉ kiểm chữ ký)", None)
    try:
        with _gate.strict():   # chặn không cho trùng lúc luồng khác bật cờ khoan dung
            im = Image.open(io.BytesIO(data))
            w, h = im.size   # đọc từ header, CHƯA giải mã -> chặn 'bom' kích thước trước khi load
            if w * h > SAFE_MAX_PIXELS:
                im.close()
                return ("corrupt", f"{fmt}: {w}x{h} = {w * h} điểm ảnh > {SAFE_MAX_PIXELS} "
                        "— bỏ để tránh crash bộ nhớ", None)
            with _decoding(who or f"{fmt} {w}x{h} {len(data)}B"):  # breadcrumb: crash tầng C -> còn dấu
                im.load()  # ép giải mã toàn bộ -> ảnh cụt dữ liệu báo lỗi tại đây
    except Exception as e:
        # Đúng định dạng lẽ ra giải mã được mà vẫn lỗi -> hỏng thật.
        # Định dạng lạ (avif/heif) thiếu codec -> chưa kết luận, đừng gắn cờ oan.
        if fmt not in _DECODABLE:
            return ("unsupported", f"{fmt}: thiếu codec ({e.__class__.__name__})", None)
        return ("corrupt", f"{fmt}: {e.__class__.__name__}: {e}", None)
    try:
        uniform = uniform_frame(im) if want_uniform else None
    finally:
        im.close()
    return ("ok", fmt, uniform)


def check_image_bytes(data: bytes, who=None):
    """Bản gọn cho đường tải inline: chỉ cần (verdict, chi tiết), không dò một-màu.
    `who` (thường là URL ảnh) đi vào breadcrumb để lỡ crash tầng C còn biết ảnh nào."""
    verdict, detail, _ = inspect_image_bytes(data, who=who)
    return (verdict, detail)


def bad_marker(dest: Path) -> Path:
    """Tên file cách ly: 001.jpg -> 001.jpg.bad (reader bỏ qua vì không đúng đuôi ảnh)."""
    return dest.with_name(dest.name + ".bad")


def clear_bad(dest: Path):
    """Xóa file .bad kế bên khi ảnh chuẩn đã tải lại thành công (đóng vòng cách ly->bù)."""
    b = bad_marker(dest)
    if b.exists():
        try:
            b.unlink()
        except OSError:
            pass


class Blocked(Exception):
    """Server trả 403/503 (challenge) - IP đang bị nghi ngờ, phải dừng ngay."""


class Forbidden(Blocked):
    """403 CỤ THỂ (khác 503) — tách khỏi Blocked chung để caller có cơ hội LÀM MỚI
    danh tính (vd comix: đọc lại cf_clearance + UA từ browser đang sống) rồi thử lại,
    thay vì dừng phiên ngay. Vẫn là con của Blocked nên mọi `except Blocked` cũ
    (5 site khác) bắt được y như trước -> không đổi hành vi của chúng."""


class TooMany429(Exception):
    """Bị nhắc 429 quá nhiều lần trong một phiên - dừng để giữ uy tín IP."""


class PoliteGate:
    """Van điều tốc dùng chung cho MỌI request (mọi site, mọi luồng).

    - wait_turn(): các luồng xếp hàng, request cách nhau 0.3-0.8s ngẫu nhiên
      -> tổng ~1.5-2 request/s dù chạy bao nhiêu luồng đi nữa.
    - tripped_429(): cầu dao tự ngắt - đẩy lùi thời điểm được gửi tiếp cho
      toàn bộ luồng (90s -> 5ph -> 15ph), quá 3 lần thì hủy cả phiên.
    """

    def __init__(self, min_gap: float = 0.3, max_gap: float = 0.8):
        self.lock = threading.Lock()
        self.min_gap, self.max_gap = min_gap, max_gap
        self.next_ok = 0.0   # mốc monotonic sớm nhất được gửi request kế tiếp
        self.trips = 0
        self.trips_503 = 0   # đếm riêng 503 (CDN chập chờn) — khoan hơn 429
        self.abort = False

    def wait_turn(self):
        while True:
            if self.abort:
                raise TooMany429("phiên đã bị hủy vì bị chặn nhiều lần")
            with self.lock:
                now = time.monotonic()
                if self.next_ok <= now:
                    self.next_ok = now + random.uniform(self.min_gap, self.max_gap)
                    return
                wait = self.next_ok - now
            time.sleep(min(wait, 2))

    def tripped_429(self, retry_after: float | None) -> float:
        with self.lock:
            now = time.monotonic()
            if self.next_ok > now + 30:
                return self.next_ok - now  # luồng khác vừa kéo cầu dao rồi
            self.trips += 1
            if self.trips > 3:
                self.abort = True
                raise TooMany429("bị 429 tới lần thứ 4 trong phiên")
            delay = retry_after or (90.0, 300.0, 900.0)[self.trips - 1]
            self.next_ok = now + delay
            return delay

    def tripped_503(self, retry_after: float | None) -> float:
        """503 = CDN/nguồn tạm quá tải (hay transient), KHÁC 429 (mình gửi nhanh quá).
        Không giết phiên ngay: đẩy lùi thời điểm gửi tiếp cho MỌI luồng rồi thử lại;
        backoff nhẹ hơn 429 và ngưỡng chịu đựng cao hơn (5 đợt) vì 503 thường tự khỏi.
        Quá ngưỡng -> ném Blocked (nguồn hỏng thật -> dừng, chờ vài giờ)."""
        with self.lock:
            now = time.monotonic()
            if self.next_ok > now + 10:
                return self.next_ok - now  # luồng khác vừa kéo cầu dao rồi
            self.trips_503 += 1
            if self.trips_503 > 5:
                self.abort = True
                raise Blocked("bị 503 quá nhiều lần trong phiên — nguồn/CDN đang lỗi")
            delay = retry_after or (15.0, 30.0, 60.0, 120.0, 180.0)[self.trips_503 - 1]
            self.next_ok = now + delay
            return delay

    def recover(self):
        """Tải được thêm nội dung = IP/CDN đang khỏe lại -> xoá sạch bộ đếm cầu dao để
        một đợt chập chờn ĐỘC LẬP về sau có đủ ngân sách retry (không cộng dồn cả phiên
        thành abort oan). Gọi khi một chương hoàn tất trọn vẹn."""
        with self.lock:
            self.trips = self.trips_503 = 0
            self.abort = False


gate = PoliteGate()


def _retry_after(resp) -> float | None:
    # MangaDex gửi 'x-ratelimit-retry-after' = MỐC epoch tuyệt đối (giây) -> đổi ra
    # số giây chờ = mốc trừ hiện tại. KHÁC 'Retry-After' (số giây chờ tương đối,
    # chuẩn HTTP/DDoS-Guard). Ưu tiên header MangaDex nếu có.
    xr = resp.headers.get("x-ratelimit-retry-after", "")
    if xr.replace(".", "", 1).isdigit():
        delay = float(xr) - time.time()
        return delay if delay > 0 else None
    ra = resp.headers.get("Retry-After", "")
    return float(ra) if ra.replace(".", "", 1).isdigit() else None


def _request(url: str, retries: int = 3):
    """GET qua van điều tốc, xử lý 429/403/503 chung. Trả Response hoặc None."""
    for attempt in range(retries + 2):
        gate.wait_turn()
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 429:
                delay = gate.tripped_429(_retry_after(r))
                print(f"\n  ! Server nhắc 429 - tạm dừng toàn bộ {delay:.0f}s "
                      f"rồi tự chạy tiếp...", flush=True)
                continue
            if r.status_code == 503:   # transient: lùi giờ + thử lại, chưa vội bỏ cuộc
                delay = gate.tripped_503(_retry_after(r))
                print(f"\n  ! Server 503 (nguồn tạm quá tải?) - tạm dừng {delay:.0f}s "
                      f"rồi thử lại...", flush=True)
                continue
            if r.status_code == 403:
                raise Forbidden(f"HTTP 403 khi gọi {url}")
            r.raise_for_status()
            return r
        except (Blocked, TooMany429):
            raise
        except Exception as e:
            if attempt >= retries - 1:
                print(f"  ! Lỗi khi gọi {url}: {e}", file=sys.stderr)
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def get_json(url: str, retries: int = 3):
    """Provider dùng để lấy JSON (site có API)."""
    r = _request(url, retries)
    if r is None:
        return None
    try:
        return r.json()
    except ValueError:
        print(f"  ! Trả về không phải JSON: {url}", file=sys.stderr)
        return None


def get_text(url: str, retries: int = 3):
    """Provider dùng để lấy HTML thô (site parse trang)."""
    r = _request(url, retries)
    return r.text if r is not None else None


def download_image(url: str, dest: Path, client=None) -> bool:
    """Tải 1 ảnh, KIỂM TRA rồi mới ghi. Chỉ ghi khi qua tầng 1+2 -> file trên đĩa
    luôn là ảnh dùng được; ảnh hỏng KHÔNG để lại file chuẩn nên resume tự tải lại
    lần sau. Tải bù thành công thì xóa file .bad cách ly kế bên (nếu có).

    `client` (tùy chọn): HTTP client thay cho `session` mặc định — comix truyền vào
    một client giả vân tay Chrome (curl_cffi) + mang cf_clearance/UA mượn từ browser.
    Chỉ cần có `.get(url, timeout=...)` trả response kiểu requests và tự gói lỗi mạng
    thành requests.RequestException. 403 -> raise Forbidden để caller thử làm mới vé."""
    cli = client if client is not None else session
    if dest.exists() and dest.stat().st_size > 0:
        return True  # đã tải rồi -> bỏ qua, không tốn request
    if not RETRY_BROKEN and is_known_broken(dest):
        return False  # đã xác định hỏng ở nguồn -> tải lại cũng thế, khỏi tốn request
    reason = ""       # lý do hỏng lần thử gần nhất (để in khi cạn lượt)
    prev_bad = None   # (số byte, verdict) lần hỏng trước -> lặp lại y hệt = nguồn hỏng
    for attempt in range(5):
        gate.wait_turn()
        try:
            r = cli.get(url, timeout=60)
            if r.status_code == 429:
                delay = gate.tripped_429(_retry_after(r))
                print(f"\n  ! Server nhắc 429 - tạm dừng toàn bộ {delay:.0f}s "
                      f"rồi tự tải tiếp...", flush=True)
                continue  # sau cữ nghỉ sẽ thử lại đúng ảnh này
            if r.status_code == 503:   # transient (CDN quá tải) -> lùi giờ + thử lại
                delay = gate.tripped_503(_retry_after(r))
                print(f"\n  ! Server 503 (CDN tạm quá tải?) - tạm dừng {delay:.0f}s "
                      f"rồi tự tải tiếp...", flush=True)
                continue
            if r.status_code == 403:   # thiếu/hết vé Cloudflare -> caller lo làm mới vé
                raise Forbidden(f"HTTP 403 tại {url}")
            if r.status_code == 404:
                print(f"    ! Không tồn tại (404): {url}", file=sys.stderr)
                return False
            if r.status_code >= 400:   # 5xx khác/4xx khác: coi là lỗi thoáng qua -> thử lại
                reason = f"HTTP {r.status_code}"
                time.sleep(1.5 * (attempt + 1))
                continue
            data = r.content

            # Tầng 1 — độ dài truyền tải: server báo N byte mà nhận thiếu = tải cụt
            # (nguồn số 1 của 'đen nửa dưới'). Coi như hỏng -> thử lại.
            clen = r.headers.get("Content-Length", "")
            if clen.isdigit() and int(clen) != len(data):
                reason = f"nhận {len(data)}/{clen} byte (cụt truyền tải)"
                time.sleep(1.5 * (attempt + 1))
                continue

            # Tầng 2 — chữ ký + giải mã (trong RAM, không nén lại). {ok, unsupported}
            # thì ghi; hỏng thì thử lại. unsupported = thiếu codec, không dám bỏ.
            verdict, detail = check_image_bytes(data, who=url)
            if verdict in ("empty", "not_image", "corrupt"):
                reason = f"{verdict}: {detail}"
                # Hỏng y hệt lần trước (cùng số byte, cùng kiểu) => file ở NGUỒN hỏng,
                # không phải chập mạng. Thử lại bao nhiêu cũng vậy -> dừng ngay.
                if prev_bad == (len(data), verdict):
                    frac = intact_fraction(data, who=url) if verdict == "corrupt" else None
                    if frac and frac[0] >= SALVAGE_MIN:
                        # CỨU VỚT: ghi byte gốc (không nén lại) — đọc được phần lớn còn
                        # hơn mất trắng cả trang; trình duyệt/reader vẫn hiển thị được.
                        dest.write_bytes(data)
                        clear_bad(dest)
                        record_issue("salvaged", dest, {
                            "url": url, "bytes": len(data), "intact": round(frac[0], 4),
                            "size": f"{frac[1]}x{frac[2]}", "reason": detail})
                        print(f"\n    ~ Ảnh hỏng tại nguồn nhưng CỨU được "
                              f"{frac[0] * 100:.0f}% — đã lưu: {dest.name}", flush=True)
                        return True
                    record_issue("source_broken", dest, {
                        "url": url, "bytes": len(data), "verdict": verdict,
                        "intact": round(frac[0], 4) if frac else None, "reason": detail})
                    print(f"\n    ! Ảnh HỎNG TẠI NGUỒN (tải lại vô ích), đã ghi nhận "
                          f"để lần sau bỏ qua: {url}", file=sys.stderr, flush=True)
                    return False
                prev_bad = (len(data), verdict)
                time.sleep(1.5 * (attempt + 1))
                continue

            dest.write_bytes(data)
            clear_bad(dest)
            return True
        except (Blocked, TooMany429):
            raise
        except requests.RequestException as e:
            reason = str(e)
            if attempt >= 2:  # lỗi mạng thoáng qua: thử tối đa 3 lần
                print(f"    ! Lỗi ảnh {url}: {e}", file=sys.stderr)
                return False
            time.sleep(2.0 * (attempt + 1))
    if reason:
        print(f"    ! Bỏ ảnh hỏng sau 5 lần thử ({reason}): {url}", file=sys.stderr)
    return False


def safe_name(name: str) -> str:
    """Bỏ ký tự không hợp lệ cho tên thư mục/tệp trên Windows.

    Ngoài nhóm cấm <>:"/\\|?* và ký tự điều khiển (thay bằng _), PHẢI cắt dấu chấm và
    khoảng trắng ở CUỐI tên: Windows tự lược bỏ chúng khi mkdir, nên tên Path (còn giữ
    '...') lệch tên thư mục thật trên đĩa (đã bị cắt) -> ghi ảnh vào trong báo
    FileNotFoundError. Title chương MangaDex hay kết thúc bằng '...' nên rất dễ dính.
    """
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().rstrip(" .")
    return cleaned or "untitled"


def fmt_num(num) -> str:
    """330.0 -> '330' ; 12.5 -> '12.5' (đặt nhãn chương)."""
    return int(num) if float(num).is_integer() else num


def download_cover(url: str, out_root: Path, client=None):
    """Tải ảnh bìa về cover.<ext>. Đã có cover.* thì thôi, không tốn request."""
    if any(p.stem.lower() == "cover" and p.suffix.lower() in IMG_EXTS
           for p in out_root.iterdir() if p.is_file()):
        return
    ext = "." + url.split("?")[0].rsplit(".", 1)[-1].lower()
    if ext not in IMG_EXTS:
        ext = ".webp"
    if download_image(url, out_root / f"cover{ext}", client=client):
        print(f"Đã tải ảnh bìa: cover{ext}")


def parse_selection(spec: str) -> set:
    """'5,7,20-25' -> {5,7,20,21,22,23,24,25}"""
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(float(part))
    return out


def list_images(folder: Path) -> list:
    """Các file ảnh nằm trực tiếp trong folder, sắp xếp theo tên."""
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in IMG_EXTS)


def make_cbz(folder: Path, skip_existing: bool = False) -> bool:
    """Đóng gói thư mục ảnh thành 1 tệp .cbz (đọc trên app truyện)."""
    # không dùng with_suffix: folder "Chapter 12.5" sẽ bị cắt thành "Chapter 12.cbz"
    cbz = folder.parent / (folder.name + ".cbz")
    if skip_existing and cbz.exists() and cbz.stat().st_size > 0:
        print(f"  = Bỏ qua {cbz.name} (đã có)")
        return False
    imgs = list_images(folder)
    if not imgs:
        print(f"  ! {folder.name}: không có ảnh - bỏ qua")
        return False
    with zipfile.ZipFile(cbz, "w", zipfile.ZIP_STORED) as z:
        for img in imgs:
            z.write(img, img.name)
    print(f"  -> Đã tạo {cbz.name} ({len(imgs)} ảnh)")
    return True


def pack_tree(root: Path):
    """Quét root + mọi thư mục con; folder nào chứa ảnh thì nén thành .cbz cùng tên."""
    if not root.is_dir():
        print(f"Không tìm thấy thư mục: {root}", file=sys.stderr)
        sys.exit(1)
    targets = [d for d in [root, *sorted(root.rglob("*"))]
               if d.is_dir() and list_images(d)]
    if not targets:
        print("Không tìm thấy thư mục ảnh nào bên trong.", file=sys.stderr)
        sys.exit(1)
    print(f"Tìm thấy {len(targets)} thư mục ảnh trong: {root.resolve()}\n")
    created = 0
    for d in targets:
        created += 1 if make_cbz(d, skip_existing=True) else 0
    print(f"\nHoàn tất: tạo mới {created}/{len(targets)} tệp .cbz.")


def compact_ints(nums) -> str:
    """[15,16,17,20] -> '15-17, 20' (in danh sách trang thiếu cho gọn)."""
    nums = sorted(set(nums))
    if not nums:
        return ""
    runs, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        runs.append((start, prev))
        start = prev = n
    runs.append((start, prev))
    return ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in runs)


def compact_chapters(nums, max_groups=12) -> str:
    """Danh sách SỐ CHƯƠNG (có thể lẻ .5) -> chuỗi gọn: [21,22,...,334] -> '21-334';
    [119,120,121,130] -> '119-121, 130'. Số nguyên liền nhau gộp thành dải, số lẻ đứng
    riêng; số nguyên in không đuôi .0 (khác compact_ints thuần-int). Cắt bớt nếu quá
    max_groups nhóm -> tin Telegram khỏi dài lê thê khi thiếu cả trăm chương."""
    vals = sorted({float(n) for n in nums})
    if not vals:
        return ""
    groups, i, N = [], 0, len(vals)
    while i < N:
        j = i
        while (j + 1 < N and vals[j].is_integer() and vals[j + 1].is_integer()
               and vals[j + 1] == vals[j] + 1):
            j += 1
        groups.append(f"{fmt_num(vals[i])}" if j == i
                      else f"{fmt_num(vals[i])}-{fmt_num(vals[j])}")
        i = j + 1
    if len(groups) > max_groups:
        return ", ".join(groups[:max_groups]) + f", … (+{len(groups) - max_groups} nhóm)"
    return ", ".join(groups)


def _mark_done(folder: Path):
    """Ghi dấu .done vào thư mục chương đã đủ -> lần chạy sau BỎ QUA, khỏi quét mạng.
    (.done không phải ảnh nên list_images/make_cbz/reader đều lờ đi.)"""
    try:
        (folder / ".done").write_text("", encoding="utf-8")
    except OSError:
        pass


def run(provider, args):
    """Vòng lặp tải chung cho mọi site. `provider` cấp phần khác biệt của site."""
    reap_decode_crash()   # phiên trước chết giữa lúc giải mã? ghi lại ảnh thủ phạm rồi dọn cờ
    # Referer đặt theo từng site (Asura cần asuracomic.net; Raven không cần)
    if getattr(provider, "referer", None):
        session.headers["Referer"] = provider.referer
    else:
        session.headers.pop("Referer", None)

    slug = provider.series_slug(args.series)
    base_title = safe_name(provider.title_from_slug(slug))
    print(f"Site: {provider.name}  |  Truyện: {slug}")

    chapters = provider.list_chapters(slug)
    if not chapters:
        print("Không lấy được danh sách chương. Kiểm tra lại URL/slug.", file=sys.stderr)
        sys.exit(1)
    print(f"Tổng số chương tìm thấy: {len(chapters)}")

    # Lọc chương theo lựa chọn
    if args.chapters:
        wanted = parse_selection(args.chapters)
        chapters = [c for c in chapters if c.number in wanted]
    else:
        if args.c_from is not None:
            chapters = [c for c in chapters if c.number >= args.c_from]
        if args.c_to is not None:
            chapters = [c for c in chapters if c.number <= args.c_to]
    if not chapters:
        print("Không có chương nào khớp lựa chọn.", file=sys.stderr)
        sys.exit(1)

    out_root = Path(args.out) / base_title
    out_root.mkdir(parents=True, exist_ok=True)
    cover = provider.cover_url(slug)
    if cover:
        download_cover(cover, out_root)
    print(f"Sẽ tải {len(chapters)} chương vào: {out_root.resolve()}\n")

    total = len(chapters)
    active = 0  # đếm chương có tải thật, để nghỉ giải lao định kỳ
    incomplete = []     # [(nhãn chương, trang còn thiếu)] — chạy lại là bù được
    source_broken = []  # [(nhãn chương, trang hỏng tại nguồn)] — tải lại vô ích
    n_full = 0     # chương ĐỦ ẢNH sau lượt này (tải mới xong, hoặc đã đủ sẵn)
    n_skipped = 0  # chương .done -> bỏ qua từ lượt trước (khỏi quét mạng)
    n_locked = 0   # chương KHÔNG có ảnh (khóa/premium/xóa nguồn)
    img_ok = 0        # tổng ẢNH tốt (có trên đĩa) của các chương quét lượt này
    img_missing = 0   # tổng ẢNH còn thiếu (tải lại là bù được)
    img_broken = 0    # tổng ẢNH hỏng tại nguồn (tải lại vô ích)
    try:
        for idx, c in enumerate(chapters, 1):
            label = f"Chapter {fmt_num(c.number)}"
            prefix = f"[{idx}/{total}] {label}"  # vị trí chương / tổng số sẽ tải
            folder = out_root / safe_name(f"{label}{' - ' + c.title if c.title else ''}")
            folder.mkdir(exist_ok=True)

            # Chương đã đánh dấu .done từ lần trước -> BỎ QUA, không gọi mạng lấy
            # danh sách ảnh (giúp chạy lại hàng đợi rất nhanh). Cờ --recheck để quét lại.
            if (folder / ".done").exists() and not getattr(args, "recheck", False):
                print(f"{prefix} — đã xong trước đó (bỏ qua, khỏi quét mạng)")
                n_skipped += 1
                if args.cbz:
                    make_cbz(folder, skip_existing=True)
                continue

            urls = provider.chapter_images(c)
            if not urls:
                print(f"{prefix} — không có ảnh (khóa/premium?), bỏ qua")
                n_locked += 1
                continue

            # 1 trang = (số thứ tự, url, đích). Giữ nguyên list để cuối còn soát đủ/thiếu.
            pages = []
            for i, url in enumerate(urls, 1):
                ext = url.split("?")[0].rsplit(".", 1)[-1] or "webp"
                pages.append((i, url, folder / f"{i:03d}.{ext}"))

            def _have(d):  # ảnh coi là 'đã có' khi tồn tại & khác rỗng
                return d.exists() and d.stat().st_size > 0

            # chỉ tải phần còn thiếu; chương đủ rồi thì không làm phiền server
            jobs = [(u, d) for _, u, d in pages if not _have(d)]
            if not jobs:
                print(f"{prefix} — đã đủ {len(urls)} ảnh, bỏ qua")
                n_full += 1
                img_ok += len(urls)
                _mark_done(folder)   # đủ rồi -> đánh dấu để lần sau khỏi quét
                if args.cbz:
                    make_cbz(folder, skip_existing=True)
                continue

            # đếm sống trên cùng 1 dòng (ghi đè bằng \r) -> biết đang tải tới đâu
            have = len(pages) - len(jobs)   # ảnh đã có sẵn từ trước
            ok = have
            done = have
            print(f"\r{prefix} — {done}/{len(urls)} ảnh, đang tải...   ",
                  end="", flush=True)
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(download_image, u, d) for u, d in jobs]
                try:
                    for f in as_completed(futures):
                        if f.result():
                            ok += 1
                        done += 1
                        print(f"\r{prefix} — {done}/{len(urls)} ảnh, đang tải...   ",
                              end="", flush=True)
                except (Blocked, TooMany429):
                    gate.abort = True  # cho các luồng đang chờ thoát nhanh
                    pool.shutdown(cancel_futures=True)
                    raise

            # Tầng 3 — đủ trang: ảnh trượt tầng 1/2 KHÔNG được ghi -> đích khuyết.
            # Số kỳ vọng lấy từ provider (Asura API / Raven ts_reader). Tách 2 loại:
            # hỏng-tại-nguồn (tải lại vô ích) vs còn thiếu (chạy lại là bù được).
            missing = [i for i, _, d in pages if not _have(d)]
            broken = [i for i, _, d in pages if not _have(d) and is_known_broken(d)]
            retryable = [i for i in missing if i not in broken]
            if not retryable:   # đủ, hoặc chỉ còn trang hỏng-tại-nguồn -> coi như xong
                _mark_done(folder)
            if missing:
                note = (f" — THIẾU {len(retryable)}: trang {compact_ints(retryable)}"
                        if retryable else "")
                note += (f" — {len(broken)} trang hỏng tại nguồn: {compact_ints(broken)}"
                         if broken else "")
                print(f"\r{prefix} — xong {ok}/{len(urls)} ảnh{note}          ")
                if retryable:
                    incomplete.append((label, retryable))
                    append_log(f"{base_title} / {label}: thiếu {len(retryable)}/{len(urls)} "
                               f"trang [{compact_ints(retryable)}] — chạy lại lệnh để tải bù")
                if broken:
                    source_broken.append((label, broken))
                    append_log(f"{base_title} / {label}: {len(broken)} trang HỎNG TẠI NGUỒN "
                               f"[{compact_ints(broken)}] — tải lại vô ích, đã ghi nhận")
            else:
                n_full += 1
                print(f"\r{prefix} — xong {ok}/{len(urls)} ảnh                    ")

            # cộng dồn cấp ẢNH cho tổng kết: tốt = kỳ vọng - thiếu (gồm cả ảnh có sẵn)
            img_ok += len(urls) - len(missing)
            img_missing += len(retryable)
            img_broken += len(broken)

            if args.cbz:
                make_cbz(folder)

            active += 1
            if active % 10 == 0:
                rest = random.uniform(60, 90)
                print(f"  (đang nghỉ {rest:.0f}s cho giống nhịp người đọc — KHÔNG "
                      f"phải treo, sẽ tự chạy tiếp...)", flush=True)
                time.sleep(rest)
            else:
                time.sleep(random.uniform(0.7, 1.3) * args.delay)
    except (Blocked, TooMany429) as e:
        print(f"\n!!! Dừng phiên: {e}", file=sys.stderr)
        print("Ảnh đã tải không mất. Chờ một lúc (429: ~1 giờ; 403/503: vài giờ) "
              "rồi chạy lại đúng lệnh này - tự tải tiếp chỗ dở.", file=sys.stderr)
        sys.exit(2)

    # ---- Tổng kết CẢ BỘ: luôn in 1 dòng số liệu (kể cả khi mọi thứ đều ổn) ----
    bits = [f"Đủ ảnh: {n_full}"]
    if n_skipped:
        bits.append(f"Đã xong trước: {n_skipped}")
    if incomplete:
        bits.append(f"Thiếu trang: {len(incomplete)} (tải lại là bù được)")
    if source_broken:
        bits.append(f"Hỏng tại nguồn: {len(source_broken)}")
    if n_locked:
        bits.append(f"Khóa/không ảnh: {n_locked}")
    print(f"\n===== TỔNG KẾT: {base_title} — {total} chương =====")
    print("   " + "   |   ".join(bits))
    # Dòng cấp ẢNH (điều hay cần: bao nhiêu ảnh OK / lỗi). Chương .done bỏ qua không
    # quét mạng nên KHÔNG đếm được ảnh -> ghi chú rõ để khỏi tưởng thiếu.
    img_bits = [f"OK {img_ok}"]
    if img_missing:
        img_bits.append(f"thiếu {img_missing}")
    if img_broken:
        img_bits.append(f"hỏng nguồn {img_broken}")
    tail = f"  (chưa gồm {n_skipped} chương đã xong trước)" if n_skipped else ""
    print("   Ảnh: " + ", ".join(img_bits) + tail)

    # Tổng kết: tách rõ 'chạy lại là bù được' với 'nguồn hỏng, chạy lại vô ích'.
    if incomplete:
        print(f"\n! {len(incomplete)} chương còn thiếu trang (ảnh hỏng đã bị loại, "
              f"KHÔNG để lại file lỗi):")
        for label, missing in incomplete:
            print(f"   - {label}: thiếu {compact_ints(missing)}")
        print("-> Chạy lại đúng lệnh vừa rồi để tự tải bù các trang này "
              "(chi tiết đã ghi vào .reader-meta/download-log.txt).")
    if source_broken:
        print(f"\n!! {len(source_broken)} chương có trang HỎNG TẠI NGUỒN — file trên "
              f"server vốn đã hỏng, tải lại KHÔNG giải quyết được:")
        for label, pages_ in source_broken:
            print(f"   - {label}: trang {compact_ints(pages_)}")
        print("-> Đã ghi nhận, các lần chạy sau sẽ tự bỏ qua (khỏi tốn request). "
              "Muốn thử lại: thêm cờ --retry-broken.")
    print("\nHoàn tất.")
