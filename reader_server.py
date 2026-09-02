#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Web reader kiểu Asura cho thư viện truyện local.

Chạy:  python reader_server.py  (tùy chọn: --port 8080)

- Tự quét truyện trong folder "downloads" (folder nào có chương chứa ảnh
  là thành truyện, không cần khai báo).
- Đọc trên PC: http://localhost:8080
- Đọc trên điện thoại cùng Wi-Fi: http://<IP-máy-tính>:8080 (in ra khi chạy).
- Không sửa/ghi gì vào folder truyện; vị trí đọc lưu trong trình duyệt.
"""

import argparse
import base64
import binascii
import hashlib
import html
import io
import json
import os
import re
import secrets
import socket
import sys
import threading
import time
import unicodedata
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlsplit

try:
    from PIL import Image
except ImportError:
    Image = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# CHỈ quét thư viện trong "downloads" — không quét thư mục gốc project để tránh
# các folder công cụ/phụ trợ (realesrgan-*, cover, cover_webp...) bị nhận nhầm
# thành truyện. Truyện chỉ nằm trong downloads.
SCAN_ROOTS = [os.path.join(BASE_DIR, "downloads")]
# Folder bỏ qua khi quét truyện (không phải thư viện ảnh truyện). Giữ "downloads"
# cho chắc dù giờ nó không còn là folder con của root nào được quét.
EXCLUDE_DIRS = {".claude", "downloads", "so-sanh-webp", "__pycache__"}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
    ".avif": "image/avif",
}
CACHE_TTL = 60          # giây; quét lại thư viện sau chừng này để thấy chương mới
COVER_WIDTH = 480       # bề ngang ảnh bìa thu nhỏ ở trang chủ
META_DIR = os.path.join(BASE_DIR, ".reader-meta")
SPREADS_FILE = os.path.join(META_DIR, "spreads.json")
SERIES_META_FILE = os.path.join(META_DIR, "series-meta.json")
# Tài khoản + dữ liệu đọc THEO TỪNG tài khoản (bookmark/tiến trình/đã đọc), tất cả
# trong .reader-meta\users.json. Đăng nhập bằng username (không mật khẩu). Cookie
# uid giữ phiên; đổi link tunnel thì mất phiên nhưng DỮ LIỆU còn (khóa theo tên).
USERS_FILE = os.path.join(META_DIR, "users.json")
USER_DATA_FILE = os.path.join(META_DIR, "user-data.json")  # [LEGACY] không còn dùng
# Heartbeat RIÊNG cho reader (độc lập supervisor) — xem reader_heartbeat_loop().
NOTIFY_CONFIG_FILE = os.path.join(META_DIR, "notify-config.json")
READER_HB_EVERY = 300      # giây giữa 2 nhịp heartbeat reader (5')
READER_HB_TIMEOUT = 10     # giây chờ mỗi cú tự-kiểm / ping
# Icon PNG cho home-screen / PWA (tạo sẵn tĩnh trong META_DIR). Whitelist để
# route chỉ phục vụ đúng các file này, không cho đọc file tùy ý.
ICON_FILES = {
    "icon-180.png", "icon-192.png", "icon-512.png", "icon-512-maskable.png",
    "og-image.png", "og-image.jpg", "og-image-wide.jpg",
}

# ---------------------------------------------------------------------------
# Quét thư viện
# ---------------------------------------------------------------------------

def natkey(s):
    """Khóa sắp xếp tự nhiên: '10' đứng sau '2'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def chapter_num(name):
    """Rút số chương từ tên folder, ưu tiên số đứng sau chữ Chương/Chapter/Ch.

    'Tập 01 - Chương 180- ...' -> 180 (không dính số tập),
    '[CORO²] Sun Moon- Chapter 001' -> 1, 'Ch. 14.2' -> 14.2.
    """
    n = unicodedata.normalize("NFC", name)
    for pat in (r"chương\s*(\d+(?:\.\d+)?)",
                r"chapter\s*(\d+(?:\.\d+)?)",
                r"\bch\.?\s*(\d+(?:\.\d+)?)",
                r"(\d+(?:\.\d+)?)"):
        m = re.search(pat, n, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return float("inf")


def first_num(name):
    """Số đầu tiên trong tên arc ('CHƯƠNG 618-654 - SUN MOON' -> 618)."""
    m = re.search(r"(\d+(?:\.\d+)?)", unicodedata.normalize("NFC", name))
    return float(m.group(1)) if m else float("inf")


def fmt_num(x):
    """Số chương gọn để hiển thị: 14.0 -> '14', 14.2 -> '14.2', inf -> ''."""
    if x == float("inf"):
        return ""
    return str(int(x)) if x.is_integer() else f"{x:g}"


def dir_has_image(path):
    try:
        with os.scandir(path) as it:
            for e in it:
                if e.is_file() and os.path.splitext(e.name)[1].lower() in IMG_EXTS:
                    return True
    except OSError:
        pass
    return False


def list_images(path):
    try:
        with os.scandir(path) as it:
            names = [e.name for e in it
                     if e.is_file() and os.path.splitext(e.name)[1].lower() in IMG_EXTS]
    except OSError:
        return []
    return sorted(names, key=natkey)


def build_series(path, name):
    """Nhận diện 1 folder truyện: phẳng (Chương/ảnh) hoặc 2 tầng (Arc/Chương/ảnh)."""
    flat, arc_dirs = [], []
    try:
        subs = [d for d in os.scandir(path) if d.is_dir()]
    except OSError:
        return None
    for d in subs:
        if dir_has_image(d.path):
            flat.append(d.name)
        else:
            try:
                chs = [c.name for c in os.scandir(d.path)
                       if c.is_dir() and dir_has_image(c.path)]
            except OSError:
                continue
            if chs:
                arc_dirs.append((d.name, chs))
    if not flat and not arc_dirs:
        return None

    arcs = []
    if flat:
        chapters = sorted(flat, key=lambda c: (chapter_num(c), natkey(c)))
        arcs.append({"name": "", "start": -1.0, "chapters": chapters})
    for arc_name, chs in arc_dirs:
        chapters = sorted(chs, key=lambda c: (chapter_num(c), natkey(c)))
        arcs.append({"name": arc_name, "start": first_num(arc_name), "chapters": chapters})
    arcs.sort(key=lambda a: (a["start"], natkey(a["name"])))

    order, byrel = [], {}
    for a in arcs:
        rels = []
        for ch in a["chapters"]:
            rel = f'{a["name"]}/{ch}' if a["name"] else ch
            byrel[rel] = {"name": ch, "arc": a["name"], "idx": len(order)}
            order.append(rel)
            rels.append({"name": ch, "rel": rel, "num": fmt_num(chapter_num(ch))})
        a["chapters"] = rels

    title = re.sub(r"_webp$", "", name)
    s = {"id": name, "title": title, "path": path, "arcs": arcs,
         "order": order, "byrel": byrel, "total": len(order)}
    # Xác định nguồn bìa + mtime NGAY lúc build (tốn scandir/getsize) rồi cache vào
    # series, để mỗi lần render trang chủ khỏi phải chạm đĩa lại (xem cover_ver/cover_jpeg).
    src = cover_source(s)
    s["cover_src"] = src
    try:
        s["cover_mt"] = str(os.stat(src).st_mtime_ns) if src else "0"
    except OSError:
        s["cover_mt"] = "0"
    return s


_lib_lock = threading.Lock()        # bảo vệ _lib_cache / _lib_refreshing
_lib_build_lock = threading.Lock()  # tuần tự hoá lần quét ĐỒNG BỘ (lúc chưa có cache)
_lib_cache = None       # (timestamp, dict sid -> series)
_lib_refreshing = False # đang có thread nền quét lại?


def _scan_library():
    """Quét toàn bộ thư viện từ ổ đĩa -> dict sid -> series. Tốn I/O (scandir mọi
    thư mục chương), nên chỉ gọi ở lần build lạnh hoặc thread nền, KHÔNG trên
    đường trả response khi đã có cache (xem get_library)."""
    series = {}
    for root in SCAN_ROOTS:
        if not os.path.isdir(root):
            continue
        for e in os.scandir(root):
            if not e.is_dir() or e.name in EXCLUDE_DIRS or e.name.startswith("."):
                continue
            s = build_series(e.path, e.name)
            if s:
                series[s["id"]] = s
    # có bản "<tên>_webp" thì bỏ bản gốc "<tên>" (tránh 2 card trùng tên)
    for sid in list(series):
        if sid + "_webp" in series:
            series.pop(sid, None)
    # tên hiển thị do admin đặt (nếu có) -> đè lên tên suy từ folder, TRƯỚC khi sort
    for sid, s in series.items():
        ov = series_title_override(sid)
        if ov:
            s["title"] = ov
    series = dict(sorted(series.items(), key=lambda kv: natkey(kv[1]["title"])))
    sync_series_meta(series)  # tự thêm truyện mới + đánh số order vào series-meta.json
    return series


def _library_signature():
    """Chữ ký RẺ của cây thư mục thư viện để phát hiện thêm/xoá chương ngay (không
    chờ hết TTL). Quét 2 tầng: folder truyện + folder con (arc-hoặc-chương), lấy
    mtime mỗi thư mục — KHÔNG lặn xuống tầng ảnh (đó mới là chỗ đắt của _scan_library).
    Thêm/xoá 1 chương phẳng đổi mtime folder truyện; thêm/xoá chương trong arc đổi
    mtime folder arc (tầng 2); thêm/xoá truyện đổi mtime root. Đủ bắt mọi thay đổi
    về SỐ chương. scandir cache sẵn stat trên Windows nên gần như miễn phí."""
    parts = []
    for root in SCAN_ROOTS:
        try:
            parts.append((root, os.stat(root).st_mtime_ns))
            entries = list(os.scandir(root))
        except OSError:
            continue
        for e in entries:
            if not e.is_dir() or e.name in EXCLUDE_DIRS or e.name.startswith("."):
                continue
            try:
                parts.append((e.path, e.stat().st_mtime_ns))
                subs = list(os.scandir(e.path))
            except OSError:
                continue
            for sub in subs:
                try:
                    if sub.is_dir():
                        parts.append((sub.path, sub.stat().st_mtime_ns))
                except OSError:
                    continue
    parts.sort()
    h = hashlib.sha1()
    for p, m in parts:
        h.update(p.encode("utf-8", "surrogatepass"))
        h.update(str(m).encode())
    return h.hexdigest()


def _refresh_library():
    """Quét lại ở nền rồi thay cache. Chạy trong daemon thread (stale-while-revalidate)."""
    global _lib_cache, _lib_refreshing
    try:
        series = _scan_library()
        sig = _library_signature()
        with _lib_lock:
            _lib_cache = (time.time(), series, sig)
    finally:
        with _lib_lock:
            _lib_refreshing = False


def get_library():
    """Trả thư viện. Chữ ký thư mục KHÔNG đổi -> dùng cache luôn (bất kể tuổi). Chữ
    ký đổi (thêm/xoá chương) hoặc hết TTL -> nếu còn bản cũ, trả stale NGAY và quét
    lại ở nền (không ai chờ scandir); lần đồng bộ kế (pageshow/visibility) sẽ nhận số
    mới. Chưa có cache (khởi động / vừa bust) -> buộc quét đồng bộ một lần."""
    global _lib_cache, _lib_refreshing
    sig = _library_signature()
    with _lib_lock:
        cache = _lib_cache
        # cache[2] = chữ ký lúc quét. Còn khớp + còn hạn TTL -> tươi chắc chắn.
        if cache and cache[2] == sig and time.time() - cache[0] < CACHE_TTL:
            return cache[1]
        if cache:
            # chữ ký đổi HOẶC quá TTL: phục vụ stale + làm mới nền (ngay lần này,
            # không đợi thêm 60s như trước -> số chương tự lành trong ~1-2s).
            if not _lib_refreshing:
                _lib_refreshing = True
                threading.Thread(target=_refresh_library, daemon=True).start()
            return cache[1]
    # build lạnh: tuần tự hoá để nhiều request đồng thời không cùng quét
    with _lib_build_lock:
        with _lib_lock:
            if _lib_cache:  # request khác vừa build xong trong lúc ta chờ lock
                return _lib_cache[1]
        series = _scan_library()
        sig2 = _library_signature()
        with _lib_lock:
            _lib_cache = (time.time(), series, sig2)
        return series


# ---------------------------------------------------------------------------
# Trang đôi ghép thủ công: lưu trong .reader-meta\spreads.json (không đụng
# folder truyện). Cấu trúc: {sid: {rel_chương: [{"left": file, "right": file}]}}
# ---------------------------------------------------------------------------

_spreads_lock = threading.Lock()
_spreads = None


def load_spreads():
    global _spreads
    with _spreads_lock:
        if _spreads is None:
            try:
                with open(SPREADS_FILE, encoding="utf-8") as f:
                    _spreads = json.load(f)
            except (OSError, ValueError):
                _spreads = {}
    return _spreads


def chapter_spreads(sid, rel):
    sp = load_spreads()
    return sp.get(sid, {}).get(rel, [])


def _save_spreads_locked():
    os.makedirs(META_DIR, exist_ok=True)
    tmp = SPREADS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_spreads, f, ensure_ascii=False, indent=1)
    os.replace(tmp, SPREADS_FILE)


def modify_spreads(sid, rel, action, a, b=None):
    """join/flip/split một cặp trang; trả về True nếu có thay đổi."""
    load_spreads()
    with _spreads_lock:
        chmap = _spreads.setdefault(sid, {})
        pairs = chmap.setdefault(rel, [])

        def find(fname):
            for p in pairs:
                if fname in (p["left"], p["right"]):
                    return p
            return None

        if action == "join":
            if not b:
                return False
            pa, pb = find(a), find(b)
            # a và b vốn ĐÃ là 1 cặp (bấm Join lại vì SW trả trang cache cũ) ->
            # coi như đã xong (idempotent), khỏi báo "Invalid action" oan.
            if pa is not None and pa is pb:
                return True
            # 1 trong 2 trang đã dính cặp khác -> không ghép được
            if pa is not None or pb is not None:
                return False
            # mặc định theo manga đọc phải->trái: trang đứng trước (a) là nửa PHẢI
            pairs.append({"left": b, "right": a})
        elif action == "flip":
            p = find(a)
            if not p:
                return False
            p["left"], p["right"] = p["right"], p["left"]
        elif action == "split":
            p = find(a)
            if not p:
                return False
            pairs.remove(p)
        else:
            return False
        if not pairs:
            del chmap[rel]
        if not chmap:
            _spreads.pop(sid, None)
        _save_spreads_locked()
        return True


# ---------------------------------------------------------------------------
# Trạng thái truyện (Completed / Ongoing): lưu trong .reader-meta\series-meta.json
# Cấu trúc {sid: {"status": "complete"|"ongoing"}}. Không có mục -> "ongoing".
# Sửa trạng thái bằng cách sửa TAY file JSON (key = tên folder truyện). Server tự
# nạp lại khi file đổi (theo mtime) nên không cần restart. Truyện mới tải về được
# server tự thêm vào (append-only, không đè giá trị đã sửa tay).
# ---------------------------------------------------------------------------

STATUS_LABELS = {"complete": "Completed", "ongoing": "Ongoing"}

_smeta_lock = threading.Lock()
_smeta = None
_smeta_mtime = None  # mtime của file lần nạp gần nhất; None = chưa nạp


def load_series_meta():
    """Trả về dict trạng thái, tự nạp lại nếu file đã đổi (mtime) -> sửa tay ăn
    ngay, khỏi restart."""
    global _smeta, _smeta_mtime
    with _smeta_lock:
        try:
            mt = os.path.getmtime(SERIES_META_FILE)
        except OSError:
            mt = None
        if _smeta is None or mt != _smeta_mtime:
            try:
                with open(SERIES_META_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                _smeta = data if isinstance(data, dict) else {}
            except (OSError, ValueError):
                _smeta = {}
            _smeta_mtime = mt
        return _smeta


def series_status(sid):
    """'complete' nếu đã đánh dấu hoàn thành, ngược lại 'ongoing' (mặc định)."""
    m = load_series_meta().get(sid)
    return "complete" if isinstance(m, dict) and m.get("status") == "complete" else "ongoing"


def series_title_override(sid):
    """Tên hiển thị do admin đặt trong series-meta.json (trường 'title'), hoặc None.
    Chỉ ĐỔI TÊN HIỂN THỊ — sid/folder giữ nguyên nên không đụng bookmark/tiến trình."""
    m = load_series_meta().get(sid)
    if isinstance(m, dict):
        t = m.get("title")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return None


def _order_value(m):
    """Giá trị 'order' hợp lệ (số, không phải bool) trong 1 mục meta; None nếu không có."""
    if isinstance(m, dict):
        o = m.get("order")
        if isinstance(o, (int, float)) and not isinstance(o, bool):
            return o
    return None


def series_order(sid):
    """Số thứ tự trang chủ (sửa tay trong series-meta.json). Không có -> +inf (xuống cuối)."""
    o = _order_value(load_series_meta().get(sid))
    return o if o is not None else float("inf")


def sync_series_meta(series):
    """Đảm bảo mọi truyện có mục trong file: thêm truyện mới (mặc định 'ongoing') và
    đảm bảo mọi truyện đều có 'order'. Truyện thiếu order được đánh số tăng dần SAU
    order lớn nhất hiện có -> **truyện mới tự = max+1**; lần đầu backfill theo tên
    A→Z để giữ đúng thứ tự đang hiển thị. Không đụng order/status người dùng đã sửa.
    `series` là dict {sid: series} để lấy tên khi backfill."""
    global _smeta, _smeta_mtime
    meta = load_series_meta()
    additions = [sid for sid in series if sid not in meta]
    max_order = 0
    for m in meta.values():
        o = _order_value(m)
        if o is not None and o > max_order:
            max_order = o
    # truyện (trong thư viện) chưa có order -> đánh số theo tên cho ổn định
    need_order = sorted((sid for sid in series if _order_value(meta.get(sid)) is None),
                        key=lambda sid: natkey(series[sid]["title"]))
    assign = {}
    for sid in need_order:
        max_order += 1
        assign[sid] = max_order
    if not additions and not assign:
        return
    with _smeta_lock:
        for sid in additions:
            meta.setdefault(sid, {"status": "ongoing"})
        for sid, ordval in assign.items():
            m = meta.setdefault(sid, {"status": "ongoing"})
            if isinstance(m, dict):
                m["order"] = ordval
        merged = {k: meta[k] for k in sorted(meta)}  # xếp key theo tên cho dễ đọc
        os.makedirs(META_DIR, exist_ok=True)
        tmp = SERIES_META_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SERIES_META_FILE)
        _smeta = merged
        try:
            _smeta_mtime = os.path.getmtime(SERIES_META_FILE)
        except OSError:
            _smeta_mtime = None


# ---------------------------------------------------------------------------
# Tài khoản (username-only) + dữ liệu đọc theo từng tài khoản.
# .reader-meta\users.json = {"byname": {tên_chuẩn_hóa: id},
#                            "users": {id: {display, bookmarks, progress, read}}}
# Đăng nhập = nhập tên: có thì vào, chưa có thì tạo (không mật khẩu — chỉ để TÁCH
# dữ liệu 2 người, không phải bảo mật). id ngẫu nhiên nên tên chứa ký tự gì cũng
# được (không dùng tên làm tên file). Guest (chưa đăng nhập) chỉ đọc, không lưu.
# ---------------------------------------------------------------------------

NAME_MAX = 24
# cho phép chữ (mọi ngôn ngữ, gồm tiếng Việt có dấu) + số + khoảng trắng + _ - .
_NAME_OK = re.compile(r"^[\w .\-]+$", re.UNICODE)

_users_lock = threading.Lock()
_users = None
_users_mtime = None


def _default_udata():
    return {"bookmarks": [], "progress": {}, "read": {}}


def clean_display(name):
    """Trim + gộp khoảng trắng thừa, GIỮ hoa/thường gốc (tên hiển thị)."""
    return " ".join(str(name or "").split())


def normalize_name(name):
    """Khóa so-trùng: gộp khoảng trắng + casefold -> 'Anh'/'anh'/' anh ' = một tài khoản."""
    return clean_display(name).casefold()


# Username (đã chuẩn hóa) có quyền admin trên web (toggle trạng thái, sắp thứ tự,
# dọn/refresh list). Thêm tên vào set này nếu muốn nhiều admin.
ADMIN_USERS = {"admin"}


def is_admin(user):
    return bool(user) and normalize_name(user.get("display", "")) in ADMIN_USERS


def validate_name(raw):
    """Trả (display, None) nếu hợp lệ, hoặc (None, thông_báo_lỗi)."""
    disp = clean_display(raw)
    if not disp:
        return None, "Tên trống"
    if len(disp) > NAME_MAX:
        return None, f"Tên quá dài (tối đa {NAME_MAX} ký tự)"
    if not _NAME_OK.match(disp):
        return None, "Tên chứa ký tự không hợp lệ (chỉ chữ, số, dấu cách, _ - .)"
    return disp, None


def _default_users():
    return {"byname": {}, "users": {}}


def _normalize_users(data):
    d = _default_users()
    if isinstance(data, dict):
        users = data.get("users")
        if isinstance(users, dict):
            for uid, u in users.items():
                if not isinstance(uid, str) or not isinstance(u, dict):
                    continue
                d["users"][uid] = {
                    "display": u.get("display") if isinstance(u.get("display"), str) else "",
                    "bookmarks": [x for x in u.get("bookmarks", []) if isinstance(x, str)],
                    "progress": {k: v for k, v in (u.get("progress") or {}).items()
                                 if isinstance(v, dict) and isinstance(v.get("rel"), str)},
                    "read": {k: [r for r in v if isinstance(r, str)]
                             for k, v in (u.get("read") or {}).items() if isinstance(v, list)},
                }
        byname = data.get("byname")
        if isinstance(byname, dict):
            d["byname"] = {k: v for k, v in byname.items()
                           if isinstance(k, str) and v in d["users"]}
    return d


def load_users():
    global _users, _users_mtime
    with _users_lock:
        try:
            mt = os.path.getmtime(USERS_FILE)
        except OSError:
            mt = None
        if _users is None or mt != _users_mtime:
            try:
                with open(USERS_FILE, encoding="utf-8") as f:
                    _users = _normalize_users(json.load(f))
            except (OSError, ValueError):
                _users = _default_users()
            _users_mtime = mt
        return _users


def _save_users_locked():
    global _users_mtime
    os.makedirs(META_DIR, exist_ok=True)
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_users, f, ensure_ascii=False, indent=1)
    os.replace(tmp, USERS_FILE)
    try:
        _users_mtime = os.path.getmtime(USERS_FILE)
    except OSError:
        _users_mtime = None


def get_or_create_user(raw):
    """Đăng nhập/tạo theo tên. Trả ({id, display}, None) hoặc (None, lỗi)."""
    disp, err = validate_name(raw)
    if err:
        return None, err
    norm = normalize_name(disp)
    load_users()
    with _users_lock:
        uid = _users["byname"].get(norm)
        if uid and uid in _users["users"]:
            return {"id": uid, "display": _users["users"][uid]["display"]}, None
        uid = secrets.token_hex(4)
        while uid in _users["users"]:
            uid = secrets.token_hex(4)
        _users["users"][uid] = {"display": disp, **_default_udata()}
        _users["byname"][norm] = uid
        _save_users_locked()
        return {"id": uid, "display": disp}, None


def user_by_id(uid):
    """{id, display} từ cookie uid, hoặc None nếu không hợp lệ (guest)."""
    if not uid:
        return None
    u = load_users()["users"].get(uid)
    return {"id": uid, "display": u.get("display", "")} if u else None


def user_data(uid):
    """Dữ liệu đọc của 1 tài khoản (để render). Guest/không thấy -> mặc định rỗng."""
    u = load_users()["users"].get(uid) if uid else None
    if not u:
        return _default_udata()
    return {"bookmarks": u.get("bookmarks", []),
            "progress": u.get("progress", {}), "read": u.get("read", {})}


def user_key(user):
    """Khoá NGẮN không-bí-mật để client namespace localStorage theo tài khoản
    (mirror tiến trình đọc, xem ls.js). KHÔNG nhúng uid thật vào HTML vì uid
    chính là cookie đăng nhập mà HTML lại nằm trong cache SW."""
    if not user:
        return ""
    return hashlib.sha1(user["id"].encode("utf-8")).hexdigest()[:8]


def update_user_data(uid, op):
    """Áp một thao tác /api/state cho ĐÚNG tài khoản uid; trả True nếu đổi."""
    if not isinstance(op, dict) or not uid:
        return False
    lib = get_library()
    kind = op.get("op")
    load_users()
    with _users_lock:
        d = _users["users"].get(uid)
        if d is None:
            return False
        d.setdefault("bookmarks", []); d.setdefault("progress", {}); d.setdefault("read", {})
        changed = False
        if kind == "bookmark":
            sid = op.get("sid")
            if sid not in lib:
                return False
            has = sid in d["bookmarks"]
            if op.get("on") and not has:
                d["bookmarks"].append(sid); changed = True
            elif not op.get("on") and has:
                d["bookmarks"].remove(sid); changed = True
        elif kind == "progress":
            sid, rel = op.get("sid"), op.get("rel")
            s = lib.get(sid)
            if not s or rel not in s["byrel"]:
                return False
            try:
                y = max(0, int(op.get("y") or 0))
            except (TypeError, ValueError):
                y = 0
            try:
                ts = max(0, int(op.get("ts") or 0))
            except (TypeError, ValueError):
                ts = 0
            # Guard chống pagehide-race: rời chương CŨ bắn keepalive, request có thể
            # VỀ SAU write của chương MỚI (qua tunnel chậm) -> đè ngược con trỏ đọc.
            # ts do client đóng dấu (Date.now() — cùng đồng hồ thiết bị nên so được);
            # chỉ chặn write cũ hơn trong CỬA SỔ 30s (đúng cỡ race) để không khoá
            # nhầm khi đổi thiết bị lệch giờ. Thiếu ts (JS cũ trong cache) -> nhận.
            old_ts = (d["progress"].get(sid) or {}).get("ts") or 0
            if ts and old_ts and ts < old_ts and old_ts - ts < 30_000:
                return False
            d["progress"][sid] = {"rel": rel, "y": y,
                                  "name": s["byrel"][rel]["name"], "ts": ts}
            changed = True
        elif kind == "read":
            sid, rel = op.get("sid"), op.get("rel")
            s = lib.get(sid)
            if not s or rel not in s["byrel"]:
                return False
            lst = d["read"].setdefault(sid, [])
            if rel not in lst:
                lst.append(rel)
                if len(lst) > 2000:
                    del lst[:-2000]
                changed = True
        else:
            return False
        if changed:
            _save_users_locked()
        return changed


def ordered_library(lib):
    """Thư viện theo thứ tự trang chủ: xếp theo trường 'order' trong series-meta.json
    (sửa tay), truyện thiếu order rơi xuống cuối theo tên A→Z."""
    return sorted(lib.values(), key=lambda s: (series_order(s["id"]), natkey(s["title"])))


def bust_library_cache():
    """Xóa cache thư viện để lần quét sau đọc lại folder thật ngay."""
    global _lib_cache
    with _lib_lock:
        _lib_cache = None


def _write_series_meta(meta):
    """Ghi đè series-meta.json (dùng cho các thao tác admin), cập nhật cache mtime."""
    global _smeta, _smeta_mtime
    with _smeta_lock:
        merged = {k: meta[k] for k in sorted(meta)}
        os.makedirs(META_DIR, exist_ok=True)
        tmp = SERIES_META_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SERIES_META_FILE)
        _smeta = merged
        try:
            _smeta_mtime = os.path.getmtime(SERIES_META_FILE)
        except OSError:
            _smeta_mtime = None


def set_series_status(sid, status):
    """Đặt trạng thái complete/ongoing cho 1 truyện."""
    if status not in ("complete", "ongoing"):
        return False
    meta = dict(load_series_meta())
    m = dict(meta.get(sid) or {})
    m["status"] = status
    meta[sid] = m
    _write_series_meta(meta)
    return True


def reorder_series(sid, move):
    """Sắp thứ tự trang chủ: move ∈ up/down/top. Đánh lại order 1..N cho toàn thư
    viện theo thứ tự mới (đơn giản, không lỗ hổng số)."""
    lib = get_library()
    ordered = [s["id"] for s in ordered_library(lib)]
    if sid not in ordered:
        return False
    i = ordered.index(sid)
    if move == "up" and i > 0:
        ordered[i - 1], ordered[i] = ordered[i], ordered[i - 1]
    elif move == "down" and i < len(ordered) - 1:
        ordered[i + 1], ordered[i] = ordered[i], ordered[i + 1]
    elif move == "top":
        ordered.insert(0, ordered.pop(i))
    else:
        return False
    meta = dict(load_series_meta())
    for pos, s2 in enumerate(ordered, start=1):
        m = dict(meta.get(s2) or {})
        m["order"] = pos
        meta[s2] = m
    _write_series_meta(meta)
    bust_library_cache()
    return True


def set_series_title(sid, title):
    """Đặt tên hiển thị cho 1 truyện (chỉ đổi trường 'title' trong series-meta.json,
    KHÔNG đổi folder/sid). title rỗng -> xoá override, quay về tên suy từ folder."""
    if sid not in get_library():
        return False
    t = clean_display(title)
    if len(t) > 120:
        return False
    meta = dict(load_series_meta())
    m = dict(meta.get(sid) or {})
    if t:
        m["title"] = t
    else:
        m.pop("title", None)
    meta[sid] = m
    _write_series_meta(meta)
    bust_library_cache()
    return True


def save_cover(series, raw):
    """Ghi ảnh bìa mới cho 1 truyện: chuẩn hoá về JPEG 3:4 @COVER_WIDTH (như bìa
    thu nhỏ), lưu thành cover.jpg trong folder truyện, xoá các cover.* cũ để chỉ
    còn đúng 1 bìa. Trả True nếu thành công."""
    if Image is None:
        return False
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im = im.convert("RGB")
            if im.width > COVER_WIDTH:
                im = im.resize((COVER_WIDTH, round(im.height * COVER_WIDTH / im.width)))
            if im.height > im.width * 4 // 3:      # quá cao -> cắt còn 3:4 từ đỉnh
                im = im.crop((0, 0, im.width, im.width * 4 // 3))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
            data = buf.getvalue()
    except Exception:
        return False
    folder = series["path"]
    try:
        dest = os.path.join(folder, "cover.jpg")
        tmp = dest + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dest)
        # xoá các bìa cũ đuôi khác (cover.png/webp...) -> cover_source xác định
        for e in os.scandir(folder):
            if e.is_file():
                stem, ext = os.path.splitext(e.name)
                if stem.lower() == "cover" and ext.lower() != ".jpg" and ext.lower() in IMG_EXTS:
                    try:
                        os.remove(e.path)
                    except OSError:
                        pass
    except OSError:
        return False
    with _cover_lock:
        _cover_cache.pop(series["id"], None)   # bỏ bìa cũ trong cache RAM
    return True


def prune_series_meta():
    """Bỏ khỏi series-meta.json mọi mục không còn folder (bao gồm bản gốc đã bị ẩn
    vì có _webp). Backup ra .bak trước. Trả danh sách id đã bỏ."""
    lib = get_library()
    meta = load_series_meta()
    dead = [sid for sid in meta if sid not in lib]
    if not dead:
        return []
    try:
        import shutil
        shutil.copyfile(SERIES_META_FILE, SERIES_META_FILE + ".bak")
    except OSError:
        pass
    _write_series_meta({k: v for k, v in meta.items() if k in lib})
    return dead


def continue_info(s, progress=None):
    """(url, nhãn) cho card 'Bookmarked' của tài khoản đang đăng nhập: chương đang
    đọc dở; chưa có thì chương đầu tiên. Nhãn là tên chương gọn (vd 'Chapter 10')."""
    prog = (progress or {}).get(s["id"])
    if prog and prog.get("rel") in s["byrel"]:
        rel = prog["rel"]
        return read_url(s["id"], rel), s["byrel"][rel]["name"]
    if s["order"]:
        rel = s["order"][0]
        return read_url(s["id"], rel), s["byrel"][rel]["name"]
    return u("series", s["id"]), ""


# ---------------------------------------------------------------------------
# Cache kích thước ảnh (đặt aspect-ratio để trang không nhảy khi ảnh tải)
# và cache ảnh bìa thu nhỏ
# ---------------------------------------------------------------------------

_dim_lock = threading.Lock()
_dim_cache = {}


def img_dims(path):
    if Image is None:
        return None
    try:
        mt = os.stat(path).st_mtime_ns
    except OSError:
        return None
    with _dim_lock:
        c = _dim_cache.get(path)
        if c and c[0] == mt:
            return c[1]
    try:
        with Image.open(path) as im:
            wh = im.size
    except Exception:
        wh = None
    with _dim_lock:
        _dim_cache[path] = (mt, wh)
    return wh


_cover_lock = threading.Lock()
_cover_cache = {}


def cover_source(series):
    """Chọn file nguồn cho ảnh bìa.

    Ưu tiên file cover.* đặt trong folder truyện (quy ước chung của
    Mihon/Komga/Kavita); không có thì lấy trang đầu chương đầu, bỏ qua
    ảnh < 10KB (trang đệm một màu).
    """
    try:
        for e in os.scandir(series["path"]):
            if e.is_file():
                stem, ext = os.path.splitext(e.name)
                if stem.lower() == "cover" and ext.lower() in IMG_EXTS:
                    return e.path
    except OSError:
        pass
    if not series["order"]:
        return None
    ch_dir = os.path.join(series["path"], *series["order"][0].split("/"))
    imgs = list_images(ch_dir)
    for fname in imgs:
        p = os.path.join(ch_dir, fname)
        try:
            if os.path.getsize(p) >= 10 * 1024:
                return p
        except OSError:
            continue
    return os.path.join(ch_dir, imgs[0]) if imgs else None


def cover_jpeg(series):
    """Ảnh bìa thu nhỏ để trang chủ tải nhanh."""
    src = series.get("cover_src") if "cover_src" in series else cover_source(series)
    if not src:
        return None
    try:
        mt = os.stat(src).st_mtime_ns
    except OSError:
        return None
    with _cover_lock:
        c = _cover_cache.get(series["id"])
        if c and c[0] == (src, mt):
            return c[1]
    if Image is None:
        try:
            with open(src, "rb") as f:
                data = (MIME.get(os.path.splitext(src)[1].lower(), "image/jpeg"), f.read())
        except OSError:
            return None
    else:
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                if im.width > COVER_WIDTH:
                    im = im.resize((COVER_WIDTH, round(im.height * COVER_WIDTH / im.width)))
                # bìa chỉ cần phần trên, cắt theo tỉ lệ 3:4 cho card đều nhau
                if im.height > im.width * 4 // 3:
                    im = im.crop((0, 0, im.width, im.width * 4 // 3))
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=80)
                data = ("image/jpeg", buf.getvalue())
        except Exception:
            return None
    with _cover_lock:
        _cover_cache[series["id"]] = ((src, mt), data)
    return data


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

CSS = """
*{box-sizing:border-box}
/* color-scheme:dark + nền tối trên html: khi trang phải dựng lại (vd back không
   trúng bfcache), canvas mặc định là tối thay vì trắng -> hết chớp trắng lúc
   vuốt back. Nền tối cũng đặt trên html chứ không chỉ body vì vùng sau body
   dùng nền của html. */
html{color-scheme:dark;background:#0b0c10}
body{margin:0;background:#0b0c10;color:#e8e8ea;
  font-family:system-ui,'Segoe UI',Roboto,Arial,sans-serif;
  -webkit-tap-highlight-color:transparent}
a{color:inherit;text-decoration:none}
img{border:0}
[hidden]{display:none!important}
.bar{position:fixed;left:0;right:0;z-index:10;display:flex;align-items:center;
  gap:10px;padding:9px 12px;background:rgba(19,20,25,.93);
  backdrop-filter:blur(8px);transition:transform .25s ease}
#topbar{top:0;border-bottom:1px solid #26272e;
  padding-top:calc(9px + env(safe-area-inset-top,0px))}
#botbar{bottom:0;border-top:1px solid #26272e;justify-content:center;gap:12px;
  padding:12px 14px calc(18px + env(safe-area-inset-bottom,0px))}
#botbar .navbtn{font-size:16px;padding:15px 22px;border-radius:15px}
.chwrap{position:relative;flex:1;max-width:340px;min-width:0;display:flex;
  align-items:center;justify-content:center;gap:9px;background:#1d1e25;
  border:1px solid #2b2c34;border-radius:15px;padding:15px 14px;font-size:16px}
.chwrap .lbl{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.chwrap svg{flex:none;opacity:.85}
#chsel{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
#topbar.hide{transform:translateY(-110%)}
#botbar.hide{transform:translateY(110%)}
/* Gợi ý "chạm để hiện điều khiển" (kiểu Asura): pill mờ nhấp nháy nhẹ ở đáy,
   pointer-events:none -> chạm xuyên qua để handler vùng đọc bật thanh công cụ.
   Hiện khi bars đang ẩn; .off = mờ hẳn khi bars hiện. */
#tapcue{position:fixed;left:50%;transform:translateX(-50%);
  bottom:calc(16px + env(safe-area-inset-bottom,0px));z-index:9;
  background:rgba(0,0,0,.8);color:rgba(255,255,255,.72);font-size:12px;
  padding:6px 12px;border-radius:9999px;pointer-events:none;white-space:nowrap;
  animation:tappulse 2s cubic-bezier(.4,0,.6,1) infinite;transition:opacity .25s ease}
#tapcue.off{opacity:0;animation:none;pointer-events:none}
@keyframes tappulse{50%{opacity:.5}}
.iconbtn{display:flex;align-items:center;justify-content:center;width:38px;height:38px;
  border-radius:10px;background:#1d1e25;border:1px solid #2b2c34;color:#e8e8ea;
  font-size:18px;cursor:pointer;flex:none}
.iconbtn.home{width:46px;height:46px}
.zoomctl{display:flex;align-items:center;gap:1px;flex:none;background:#1d1e25;
  border:1px solid #2b2c34;border-radius:10px;padding:2px}
.zbtn{width:30px;height:34px;border:0;background:transparent;color:#e8e8ea;
  font-size:20px;line-height:1;cursor:pointer;border-radius:8px;padding:0;
  display:flex;align-items:center;justify-content:center}
.zbtn:active{background:#2b2c34}
.zval{width:48px;height:34px;border:0;background:transparent;color:#e8e8ea;
  font:600 14px/1 system-ui,'Segoe UI',sans-serif;text-align:center;cursor:text;padding:0}
.zval:focus{outline:2px solid #7c3aed;border-radius:6px}
@media(max-width:480px){.zoomctl{display:none}}
.tinfo{flex:1;min-width:0;display:flex;align-items:center;gap:10px}
.tcov{width:34px;height:46px;border-radius:8px;object-fit:cover;flex:none;background:#101116}
.titles{flex:1;min-width:0;text-align:left}
.titles .s{font-size:11px;color:#9a9aa5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.titles .c{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.navbtn{display:inline-block;padding:10px 16px;border-radius:12px;background:#1d1e25;
  border:1px solid #2b2c34;color:#e8e8ea;font-size:14px;cursor:pointer;flex:none;text-align:center;
  max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.navbtn.acc{background:#7c3aed;border-color:#7c3aed;font-weight:600}
.navbtn.dis{opacity:.35;pointer-events:none}
/* Màn hình hẹp: thu gọn nút 2 bên để tên chương ở giữa đủ chỗ hiện trọn */
@media(max-width:480px){
  #botbar{gap:8px;padding-left:10px;padding-right:10px}
  #botbar .navbtn{padding:15px 14px}
  .chwrap{padding:15px 10px;gap:7px}
}
/* Cột ảnh: 100% = 800px; nút chỉnh cỡ (--imgw) trong header đổi giá trị này.
   Kẹp min(...,100%) để không bao giờ vượt bề rộng màn (không cuộn ngang);
   mobile hẹp cũng tự về full-width nên bỏ được media 768 riêng cho #strip. */
#strip{margin:0 auto;width:100%;max-width:min(var(--imgw,800px),100%)}
#strip img{display:block;width:100%;height:auto;background:#15161b}
/* Ảnh hỏng hẳn (hết lượt tự retry): cả ô là nút "chạm để tải lại" */
#strip img.perr{cursor:pointer;min-height:230px;background:#15161b url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="220" height="120" viewBox="0 0 220 120"><g fill="none" stroke="%239a9aa5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" transform="translate(93,16) scale(1.4)"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></g><text x="110" y="102" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" fill="%239a9aa5">Image failed — tap to retry</text></svg>') center no-repeat}
#strip .spread img.perr{min-height:0}
@keyframes ldg{50%{background-color:#1e1f27}}
#strip img.ldg{animation:ldg 1.1s ease-in-out infinite}
.iconbtn.on{background:#7c3aed;border-color:#7c3aed}
.spread{position:relative;display:flex;width:min(96vw,200%);
  margin-left:50%;transform:translateX(-50%)}
.spread img{width:50%}
.jbar{display:none;justify-content:center;padding:8px 0;background:#101116}
body.jmode .jbar{display:flex}
.jbar button,.sctl button{padding:8px 14px;border-radius:10px;background:#1d1e25;
  border:1px solid #7c3aed;color:#e8e8ea;font-size:13px;cursor:pointer}
.sctl{display:none;position:absolute;top:8px;left:50%;transform:translateX(-50%);
  gap:8px;z-index:5}
body.jmode .sctl{display:flex}
#endbox{display:flex;flex-direction:column;gap:12px;align-items:center;
  padding:44px 16px 110px;text-align:center}
.endt{color:#9a9aa5;font-size:14px;letter-spacing:2px}
.endrow{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.wrap{max-width:1100px;margin:0 auto;
  padding:calc(26px + env(safe-area-inset-top,0px)) 16px 70px}
.wrap>.iconbtn{margin-bottom:16px}
.brand{display:flex;align-items:center;justify-content:center;margin:6px 0 22px}
.brand img{height:60px;width:auto;max-width:90%;object-fit:contain}
.topline{display:flex;align-items:center;gap:10px;margin-bottom:16px}
.topline .brand{flex:1;min-width:0;margin:0}
.topline::after{content:"";width:46px;flex:none}
/* Thanh header tài khoản (Home + trang truyện) */
.apphead{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:2px 0 20px}
.brandmini{display:inline-flex;align-items:center;flex:none}
.brandmini img{height:34px;width:auto;object-fit:contain}
.acct{margin-left:auto;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.uname{background:#15161c;border:1px solid #2c2d37;border-radius:10px;color:#eee;
  padding:8px 11px;font-size:16px;width:150px;max-width:44vw;outline:none}
.uname:focus{border-color:#7c5cff}
.uname.flash{animation:unflash .7s ease}
@keyframes unflash{0%,100%{box-shadow:0 0 0 0 rgba(124,92,255,0)}
  30%{box-shadow:0 0 0 3px rgba(124,92,255,.5)}}
.accbtn{border:1px solid #2c2d37;background:#1a1b22;color:#e8e8ea;border-radius:10px;
  padding:8px 14px;font-size:14px;font-weight:700;cursor:pointer}
.accbtn:hover{background:#22232c}
.accbtn.primary{background:#7c5cff;border-color:#7c5cff;color:#fff}
.accbtn.primary:hover{background:#6a49f2}
.accbtn:disabled{opacity:.6;cursor:default}
/* Admin (chỉ user 'admin'): toolbar trên lưới + hàng nút trên card */
.admbar{display:flex;gap:8px;align-items:center;margin:0 0 12px;flex-wrap:wrap}
.admmsg{font-size:13px;color:#8a8b96}
.adm{display:flex;flex-direction:column;gap:6px;margin-top:6px}
.adm .admstatus{width:100%}
.admrow{display:flex;gap:6px;flex-wrap:wrap}
.admrow .admbtn{flex:1 1 22px;min-width:22px}
.admbtn,.admstatus{border:1px solid #2c2d37;background:#1a1b22;color:#e8e8ea;border-radius:8px;
  padding:6px 8px;font-size:13px;font-weight:600;cursor:pointer;line-height:1;text-align:center}
.admbtn:hover,.admstatus:hover{background:#22232c}
.admbtn:disabled,.admstatus:disabled{opacity:.5;cursor:default}
.admstatus{background:#2a2130;border-color:#4a3a52}
.admstatus.complete{background:#123024;border-color:#1f5a3f;color:#8ef0c0}
.whoami{font-size:14px;color:#cdd0d8;max-width:40vw;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;font-weight:600}
.accerr{color:#ff6b6b;font-size:12.5px;flex-basis:100%;text-align:right;min-height:0}
h1{font-size:22px;margin:6px 0 18px;line-height:1.3}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px;
  min-height:70vh;align-content:start}
/* Giữ chiều cao tối thiểu vùng kết quả -> lọc search KHÔNG làm trang co lại đột ngột
   khiến iOS clamp scroll (nhảy mỗi ký tự). #chapters cũng vậy. */
#chapters{min-height:70vh}
.nores{display:none;grid-column:1/-1;color:#9a9aa5;text-align:center;
  padding:48px 10px;font-size:15px}
.nores.on{display:block}
.card{background:#15161c;border:1px solid #25262e;border-radius:14px;overflow:hidden;
  display:block;position:relative}
.card img{width:100%;aspect-ratio:3/4;object-fit:cover;display:block;background:#101116}
.cbody{padding:10px 12px}
.ct{font-size:14px;font-weight:600;line-height:1.35;
  display:flex;align-items:center;gap:6px}
.ct .cttext{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.cm{font-size:12px;color:#9a9aa5;margin-top:4px}
/* nút admin đổi bìa (ImagePlus): nổi góc trên-phải ảnh bìa */
.covedit{position:absolute;top:8px;right:8px;z-index:3;width:36px;height:36px;padding:0;
  display:flex;align-items:center;justify-content:center;border-radius:10px;cursor:pointer;
  background:rgba(19,20,25,.72);border:1px solid rgba(255,255,255,.16);color:#fff;
  -webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}
.covedit svg{width:19px;height:19px}
.covedit:hover{background:rgba(19,20,25,.92)}
.covedit:disabled{opacity:.5;cursor:default}
/* nút admin đổi tên (SquarePen): icon nhỏ cuối tên truyện */
.titleedit{flex:none;display:inline-flex;align-items:center;justify-content:center;
  width:22px;height:22px;padding:0;border:0;background:transparent;color:#9a9aa5;cursor:pointer}
.titleedit svg{width:16px;height:16px}
.titleedit:hover{color:#e8e8ea}
.titleedit:disabled{opacity:.5;cursor:default}
.st{font-weight:600}
.st.complete{color:#4ade80}
.st.ongoing{color:#60a5fa}
.shead{display:flex;gap:16px;align-items:stretch;margin-bottom:12px}
.shead img{width:130px;border-radius:12px;aspect-ratio:3/4;object-fit:cover;
  background:#101116;flex:none}
.sinfo{flex:1;min-width:0;display:flex;flex-direction:column}
.sinfo h1{margin:0 0 8px}
.smeta{font-size:13px;color:#9a9aa5}
.sfollow{margin-top:auto;padding-top:14px}      /* ghim nút Theo dõi xuống đáy = đáy bìa */
.sfollow .bkbtn{width:100%;border-radius:12px}
/* hàng 2 nút chương (bố cục First Chapter / Download của Asura) */
.chapbtns{display:flex;gap:10px;margin:0 0 6px}
.cbtn{flex:1 1 0;min-width:0;text-align:center;padding:14px 8px;border-radius:12px;
  font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  transition:transform .12s ease,filter .12s ease}
.cbtn.latest,.cbtn.reading{flex-grow:1.4}   /* nút phải rộng hơn để chữ reading đủ chỗ */
.cbtn:active{transform:scale(.97)}
.cbtn.first{background:#ececee;color:#15161c}
.cbtn.latest{background:#0000c9;color:#fff}
.cbtn.reading{background:#009b00;color:#fff}
@media(hover:hover){.cbtn:hover{filter:brightness(1.08)}}
h2.arc{font-size:14px;color:#c9c9d4;margin:26px 0 10px;padding-bottom:8px;
  border-bottom:1px solid #26272e;text-transform:uppercase;letter-spacing:.4px}
.chgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px}
a.ch{display:block;padding:10px 12px;background:#15161c;border:1px solid #25262e;
  border-radius:10px;font-size:13px;color:#d6d6de;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
a.ch:focus{outline:none}
@media(hover:hover){a.ch:hover{border-color:#7c3aed}}
a.ch.press{transform:scale(.97);animation:chflash .3s ease}
@keyframes chflash{from{background:#33354a}to{background:#15161c}}
a.ch.read{opacity:.45}
/* --- header mục Home (ô icon bo góc + tiêu đề, kiểu trending Asura) --- */
.secthead{display:flex;align-items:center;gap:12px;margin:0 0 14px}
.sicon{width:44px;height:44px;border-radius:12px;flex:none;display:flex;
  align-items:center;justify-content:center;background:rgba(124,58,237,.16)}
.sicon.star{background:rgba(245,197,24,.15)}
.sicon.star svg{color:#f5c518}
.sicon.all svg{color:#a78bfa}
.secthead h2{font-size:18px;font-weight:800;margin:0}
/* --- mục "Bookmarked": co/giãn mượt khi thêm/bỏ, tránh giật layout ở mốc 0↔1 --- */
.follows{display:grid;grid-template-rows:0fr;opacity:0;margin-bottom:0;
  transition:grid-template-rows .45s cubic-bezier(.37,0,.63,1),
    opacity .45s cubic-bezier(.37,0,.63,1),
    margin-bottom .45s cubic-bezier(.37,0,.63,1)}
.follows.open{grid-template-rows:1fr;opacity:1;margin-bottom:26px}
.follows-inner{overflow:hidden;min-height:0}
/* --- slider "Đang theo dõi" --- */
.frow{display:flex;gap:12px;overflow-x:auto;scroll-snap-type:x proximity;
  padding-bottom:8px;-webkit-overflow-scrolling:touch;scrollbar-width:thin}
.frow::-webkit-scrollbar{height:6px}
.frow::-webkit-scrollbar-thumb{background:#2b2c34;border-radius:3px}
.fcard{flex:0 0 130px;width:130px;scroll-snap-align:start}
.fcard img{width:100%;aspect-ratio:3/4;object-fit:cover;border-radius:12px;
  background:#101116;border:1px solid #25262e;display:block}
.fct{font-size:13px;font-weight:600;margin-top:7px;line-height:1.3;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fcm{font-size:12px;color:#9a9aa5;margin-top:3px;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
/* --- animation: nhún khi bấm; chỉ nhấc/đổ bóng trên máy có chuột (mobile khỏi kẹt hover) --- */
.cardlink{display:block}
.cardlink,.fcard,a.ch,.cbtn,.bkbtn,.navbtn,.iconbtn,.sortbtn{transition:transform .1s ease}
.press{transform:scale(.95)}
/* nút nhỏ (Home, Oldest/Newest): nhún rõ hơn chút */
.iconbtn.press,.sortbtn.press{transform:scale(.93)}
/* loé sáng chỉ dành cho: dòng danh sách (a.ch, xem trên) + toggle tại chỗ mà mình
   ở lại xem được (Oldest/Newest, Bookmark). Nút điều hướng (Home, Prev/Next...) chỉ nhún. */
.sortbtn.press{animation:btnflash .3s ease}
.bkbtn.press{animation:bkflash .3s ease}
@keyframes btnflash{from{background:#41434f}to{background:#1d1e25}}
@keyframes bkflash{from{filter:brightness(1.6)}to{filter:brightness(1)}}
/* tôn trọng cài đặt "giảm chuyển động" của hệ điều hành */
@media (prefers-reduced-motion:reduce){
  .press,.iconbtn.press,.sortbtn.press,a.ch.press,.bkbtn.press{transform:none;animation:none}
  .follows{transition:none}
  #totop{transition:none}
}
@media(hover:hover){
  .card{transition:transform .14s ease,border-color .15s,box-shadow .15s}
  .card:hover{transform:translateY(-3px);border-color:#7c3aed;
    box-shadow:0 10px 24px rgba(0,0,0,.4)}
  .fcard:hover img{border-color:#7c3aed;box-shadow:0 8px 20px rgba(0,0,0,.4)}
}
/* --- nút bookmark kiểu Asura: mặc định tím + ruy-băng; đã theo xanh lá + sao --- */
.bkbtn{width:100%;border:0;background:#7c3aed;color:#fff;
  font:700 13px/1 system-ui,'Segoe UI',sans-serif;padding:12px 8px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;gap:7px;text-align:center}
.bkbtn:hover{filter:brightness(1.06)}
.bkbtn.on{background:#33343d;color:#f5c518}   /* đã theo dõi: nền xám, sao + chữ vàng */
.bkbtn .bkic{width:17px;height:17px;flex:none}
.bkbtn .bkic-star{display:none}
.bkbtn.on .bkic-book{display:none}
.bkbtn.on .bkic-star{display:inline-block}
/* --- header danh sách chương (Asura: đếm + sort một hàng, ô tìm hàng dưới) --- */
.chhead{display:flex;align-items:center;justify-content:space-between;gap:12px;
  margin:24px 0 12px}
.chcount{font-size:16px;font-weight:700}
.sortbtn{display:flex;align-items:center;gap:7px;background:#1d1e25;
  border:1px solid #2b2c34;color:#e8e8ea;border-radius:11px;padding:9px 14px;
  font-size:14px;font-weight:600;cursor:pointer;flex:none}
.sortbtn:focus{outline:none}
@media(hover:hover){.sortbtn:hover{border-color:#7c3aed}}
.chsearch{position:relative;margin-bottom:16px}
.chsearch input{width:100%;background:#15161c;border:1px solid #2b2c34;color:#e8e8ea;
  border-radius:12px;padding:13px 44px 13px 15px;font-size:16px;outline:none}
.chsearch input:focus{border-color:#7c3aed}
.chsearch input::placeholder{color:#6b6c78}
.chsearch-ic{position:absolute;right:15px;top:50%;transform:translateY(-50%);
  color:#9a9aa5;pointer-events:none;transition:opacity .15s}
/* nút xoá (Asura): ô có chữ -> ẩn kính lúp, hiện X ĐÚNG chỗ đó; hit-area rộng */
.chsearch.has-val .chsearch-ic{opacity:0}
.chclear{position:absolute;right:6px;top:50%;transform:translateY(-50%);
  display:flex;align-items:center;justify-content:center;width:36px;height:36px;
  padding:0;border:0;border-radius:9px;background:transparent;color:#9a9aa5;
  cursor:pointer;opacity:0;pointer-events:none;transition:opacity .15s,color .15s}
.chsearch.has-val .chclear{opacity:1;pointer-events:auto}
@media(hover:hover){.chclear:hover{color:#e8e8ea}}
.chclear:active{color:#fff}
.chclear:focus{outline:none}
/* --- nút "lên đầu trang" kiểu Liquid Glass (chỉ Home + list chương) --- */
#totop{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom,0px));
  width:54px;height:54px;border-radius:50%;border:1px solid rgba(255,255,255,.22);
  background:rgba(255,255,255,.10);color:#e8e8ea;cursor:pointer;z-index:30;
  display:flex;align-items:center;justify-content:center;
  -webkit-backdrop-filter:blur(20px) saturate(180%);backdrop-filter:blur(20px) saturate(180%);
  box-shadow:0 8px 24px rgba(0,0,0,.35),inset 0 1px 0 rgba(255,255,255,.35);
  opacity:0;transform:translateY(8px) scale(.9);pointer-events:none;
  transition:opacity .28s cubic-bezier(.22,1,.36,1),transform .28s cubic-bezier(.22,1,.36,1)}
#totop.show{opacity:1;transform:translateY(0) scale(1);pointer-events:auto}
#totop:active{transform:translateY(0) scale(.9)}
#totop svg{width:26px;height:26px;display:block}
"""


HOME_SVG = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/>'
            '<path d="M5 9.5V21h14V9.5"/></svg>')


BRAND_HTML = '<div class="brand"><img src="/brand" alt="Toony Reader"></div>'

# Web App Manifest: cho phép "Add to Home Screen" chạy toàn màn hình (ẩn thanh
# trình duyệt) trên Android, và cấp icon cho cả Android lẫn iOS.
# start_url "/" -> mở app luôn về trang thư viện.
MANIFEST_JSON = json.dumps({
    "name": "Toony Reader",
    "short_name": "Toony",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "background_color": "#0b0c10",
    "theme_color": "#0b0c10",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png",
         "purpose": "any"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png",
         "purpose": "any"},
        {"src": "/icon-512-maskable.png", "sizes": "512x512", "type": "image/png",
         "purpose": "maskable"},
    ],
}, ensure_ascii=False)


# Nhún khi bấm cho MỌI nút/thẻ (chạy trên mọi trang). Dùng pointerdown (hợp nhất
# chuột + cảm ứng; iOS Safari không nảy :active khi chạm nhanh) -> scale hiện ngay.
PRESS_JS = ("(function(){var S='.cardlink,.fcard,a.ch,.cbtn,.bkbtn,.navbtn,.iconbtn,.sortbtn';"
            "function u(){var e=document.querySelectorAll('.press');"
            "for(var i=0;i<e.length;i++)e[i].classList.remove('press');}"
            "document.addEventListener('pointerdown',function(e){"
            "var el=e.target.closest(S);if(el)el.classList.add('press');},{passive:true});"
            "['pointerup','pointercancel','pointerleave','dragstart','scroll']"
            ".forEach(function(v){document.addEventListener(v,u,{passive:true});});})();")

# Nút "lên đầu trang" (chỉ render ở Home + list chương). Mũi tên LÊN.
TOTOP_HTML = ('<button type="button" id="totop" aria-label="Lên đầu trang">'
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M12 20V5M6 11l6-6 6 6"/></svg></button>')

# Hiện khi cuộn quá nửa khung hình, ẩn khi lùi dưới 0.45 khung (hysteresis chống
# nhấp nháy). Bấm = cuộn êm lên đầu (native smooth; reduced-motion thì nhảy thẳng).
# Chạy mọi trang nhưng tự no-op nếu không có #totop.
TOTOP_JS = """
(function(){
  var b=document.getElementById('totop'); if(!b) return;
  var shown=false,ticking=false;
  function upd(){ticking=false;
    var vh=innerHeight,y=pageYOffset||document.documentElement.scrollTop||0;
    if(!shown&&y>vh*0.5){shown=true;b.classList.add('show');}
    else if(shown&&y<vh*0.45){shown=false;b.classList.remove('show');}}
  addEventListener('scroll',function(){if(!ticking){ticking=true;requestAnimationFrame(upd);}},{passive:true});
  addEventListener('resize',upd,{passive:true});
  b.addEventListener('click',function(){
    var r=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
    scrollTo({top:0,behavior:r?'auto':'smooth'});});
  upd();
})();
"""


def page(title, body, body_class=""):
    return ("<!doctype html><html lang=\"vi\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">"
            "<meta name=\"theme-color\" content=\"#0b0c10\">"
            # color-scheme + nền tối inline: áp NGAY, trước khi app.css (link
            # ngoài) tải xong. Chặn frame trắng đầu tiên khi iOS dựng lại trang
            # lúc vuốt back.
            "<meta name=\"color-scheme\" content=\"dark\">"
            "<style>html{color-scheme:dark;background:#0b0c10}"
            "body{background:#0b0c10}</style>"
            # iOS: ẩn thanh Safari khi mở từ màn hình chính (không cần HTTPS)
            "<meta name=\"apple-mobile-web-app-capable\" content=\"yes\">"
            "<meta name=\"mobile-web-app-capable\" content=\"yes\">"
            "<meta name=\"apple-mobile-web-app-status-bar-style\" content=\"black-translucent\">"
            "<meta name=\"apple-mobile-web-app-title\" content=\"Toony\">"
            # Android: manifest điều khiển standalone (cần HTTPS mới có tác dụng)
            "<link rel=\"manifest\" href=\"/manifest.webmanifest\">"
            "<link rel=\"icon\" href=\"/logo\">"
            # iOS chỉ nhận icon home-screen qua apple-touch-icon dạng PNG
            "<link rel=\"apple-touch-icon\" href=\"/icon-180.png\">"
            f"<title>{html.escape(title)}</title>{static_tag('app.css')}</head>"
            f"<body class=\"{body_class}\">{body}"
            f"{static_tag('base.js')}{SW_REGISTER}</body></html>")


def u(*segs):
    return "/" + "/".join(quote(s, safe="") for s in segs)


def cover_ver(series):
    """mtime của bìa để gắn vào ?v=. Route /cover cache 7 ngày với URL cố định,
    nên thay cover.* mà URL không đổi thì trình duyệt kẹt ảnh cũ; đổi mtime ->
    đổi URL -> tự tải bản mới (ảnh trang không cần vì mỗi file 1 URL riêng).
    Ưu tiên giá trị đã cache lúc build_series (khỏi chạm đĩa mỗi lần render);
    đổi bìa qua admin sẽ bust cache -> build lại -> mtime mới."""
    mt = series.get("cover_mt")
    if mt is not None:
        return mt
    src = cover_source(series)  # fallback: series không qua build cache
    if not src:
        return "0"
    try:
        return str(os.stat(src).st_mtime_ns)
    except OSError:
        return "0"


def cover_url(series):
    return f'{u("cover", series["id"])}?v={cover_ver(series)}'


def read_url(sid, rel):
    return u("read", sid, *rel.split("/"))


# Icon cho header mục (ngôi sao vàng "Đang theo dõi", lưới "Tất cả truyện")
SECT_STAR_SVG = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">'
                 '<path d="M12 2.5l2.7 5.9 6.3.7-4.7 4.3 1.3 6.2L12 16.9 6.1 19.6'
                 'l1.3-6.2L2.7 9.1l6.3-.7z"/></svg>')
SECT_BOOK_SVG = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">'
                 '<path d="M21 5c-1.11-.35-2.33-.5-3.5-.5-1.95 0-4.05.4-5.5 1.5-1.45-1.1'
                 '-3.55-1.5-5.5-1.5S2.45 4.9 1 6v14.65c0 .25.25.5.5.5.1 0 .15-.05.25-.05'
                 'C3.1 20.45 5.05 20 6.5 20c1.95 0 4.05.4 5.5 1.5 1.35-.85 3.8-1.5 5.5-1.5'
                 '1.65 0 3.35.3 4.75 1.05.1.05.15.05.25.05.25 0 .5-.25.5-.5V6c-.6-.45-1.25'
                 '-.75-2-1zm0 13.5c-1.1-.35-2.3-.5-3.5-.5-1.7 0-4.15.65-5.5 1.5V8c1.35-.85'
                 '3.8-1.5 5.5-1.5 1.2 0 2.4.15 3.5.5v11.5z"/></svg>')
# Icon trong nút bookmark: ruy-băng (mặc định) và ngôi sao (đã theo dõi)
BK_BOOK_SVG = ('<svg class="bkic bkic-book" viewBox="0 0 24 24" fill="none" '
               'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
               'stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10'
               'a2 2 0 0 1 2 2z"/></svg>')
BK_STAR_SVG = ('<svg class="bkic bkic-star" viewBox="0 0 24 24" fill="currentColor">'
               '<path d="M12 2.5l2.7 5.9 6.3.7-4.7 4.3 1.3 6.2L12 16.9 6.1 19.6'
               'l1.3-6.2L2.7 9.1l6.3-.7z"/></svg>')


def bookmark_btn(on, bid=None):
    """Nút theo dõi kiểu Asura: mặc định tím + ruy-băng 'Theo dõi', đã theo -> xanh
    lá + sao 'Đang theo dõi'. Icon đổi qua CSS theo class .on."""
    idattr = f' id="{bid}"' if bid else ""
    cls = "bkbtn on" if on else "bkbtn"
    txt = "Bookmarked" if on else "Bookmark"
    return (f'<button type="button"{idattr} class="{cls}">'
            f'{BK_BOOK_SVG}{BK_STAR_SVG}<span class="bktext">{txt}</span></button>')


def sect_head(icon_cls, svg, title):
    return (f'<div class="secthead"><span class="sicon {icon_cls}">{svg}</span>'
            f'<h2>{title}</h2></div>')


def follow_card_html(s, progress=None):
    # Click card -> trang LIST CHƯƠNG của truyện (không nhảy thẳng vào chương).
    # Nhãn .fcm vẫn hiện chương đang đọc dở / chương đầu (label từ continue_info).
    _url, label = continue_info(s, progress)
    t = html.escape(s["title"])
    return (f'<a class="fcard" data-sid="{html.escape(s["id"], quote=True)}" href="{u("series", s["id"])}">'
            f'<img src="{cover_url(s)}" loading="lazy" alt="">'
            f'<div class="fct" title="{t}">{t}</div>'
            f'<div class="fcm">{html.escape(label)}</div></a>')


def account_header(user):
    """Thanh ngang trên cùng (Home + trang truyện): logo nhỏ trái + khu tài khoản
    phải. Chưa đăng nhập -> ô nhập tên + Login; đã đăng nhập -> 'Hi, <tên>' + Logout."""
    if user:
        acc = (f'<div class="acct"><span class="whoami" title="{html.escape(user["display"], quote=True)}">'
               f'Hi, {html.escape(user["display"])}</span>'
               f'<button type="button" id="logoutbtn" class="accbtn">Logout</button></div>')
    else:
        acc = ('<form class="acct" id="loginform">'
               f'<input id="uname" class="uname" type="text" autocomplete="username" '
               f'maxlength="{NAME_MAX}" placeholder="Username">'
               '<button type="submit" class="accbtn primary">Login</button>'
               '<span class="accerr" id="accerr"></span></form>')
    return (f'<header class="apphead"><a class="brandmini" href="/">'
            f'<img src="{brand_src()}" alt="Toony" height="34"></a>{acc}</header>')


def admin_card_ctrl(st):
    """Hàng nút admin trên mỗi card: đổi trạng thái + sắp thứ tự."""
    cls = "admstatus complete" if st == "complete" else "admstatus"
    return ('<div class="adm">'
            f'<button type="button" class="{cls}" data-op="status">{STATUS_LABELS[st]}</button>'
            '<div class="admrow">'
            '<button type="button" class="admbtn" data-op="top" title="Lên đầu">⤒</button>'
            '<button type="button" class="admbtn" data-op="up" title="Lên">▲</button>'
            '<button type="button" class="admbtn" data-op="down" title="Xuống">▼</button>'
            '</div></div>')


# Icon Lucide cho nút admin đổi bìa/tên (dùng currentColor để theo màu chữ)
IMAGEPLUS_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                 'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                 '<path d="M16 5h6"/><path d="M19 2v6"/>'
                 '<path d="M21 11.5V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7.5"/>'
                 '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'
                 '<circle cx="9" cy="9" r="2"/></svg>')

SQUAREPEN_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                 'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                 '<path d="M12 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>'
                 '<path d="M18.375 2.625a1 1 0 0 1 3 3l-9.013 9.014a2 2 0 0 1-.853.505'
                 'l-2.873.84a.5.5 0 0 1-.62-.62l.84-2.873a2 2 0 0 1 .506-.852z"/></svg>')


def home_card_html(s, bookmarked, admin=False):
    sid = s["id"]
    st = series_status(sid)
    t = html.escape(s["title"])
    pen = (f'<button type="button" class="titleedit" data-op="title" '
           f'title="Đổi tên">{SQUAREPEN_SVG}</button>') if admin else ""
    covbtn = (f'<button type="button" class="covedit" data-op="cover" '
              f'title="Đổi bìa">{IMAGEPLUS_SVG}</button>') if admin else ""
    return (f'<div class="card" data-sid="{html.escape(sid, quote=True)}">'
            + covbtn
            + f'<a class="cardlink" href="{u("series", sid)}">'
            f'<img src="{cover_url(s)}" loading="lazy" alt="">'
            f'<div class="cbody"><div class="ct"><span class="cttext" title="{t}">{t}</span>'
            + pen + '</div>'
            f'<div class="cm"><span class="chapn">{s["total"]}</span> chaps · '
            f'<span class="st {st}">{STATUS_LABELS[st]}</span></div></div></a>'
            + bookmark_btn(bookmarked) + (admin_card_ctrl(st) if admin else "") + '</div>')


def html_home(lib, user=None):
    ordered = ordered_library(lib)
    admin = is_admin(user)
    ud = user_data(user["id"]) if user else _default_udata()
    bmset = set(ud["bookmarks"])                       # bookmark của tài khoản đang đăng nhập
    byid = {s["id"]: s for s in ordered}
    # Hàng "Bookmarked" sắp theo THỨ TỰ BẤM (ud["bookmarks"] append theo lần bấm,
    # bỏ-rồi-bấm-lại về cuối), KHÔNG theo thứ tự lưới. Bỏ sid không còn trong thư viện.
    bmorder = [sid for sid in ud["bookmarks"] if sid in byid]
    follows = [byid[sid] for sid in bmorder]
    slider = ('<section class="follows' + (' open' if follows else '') + '" id="follows">'
              + '<div class="follows-inner">'
              + sect_head("star", SECT_STAR_SVG, "Bookmarked")
              + '<div class="frow" id="frow">'
              + "".join(follow_card_html(s, ud["progress"]) for s in follows)
              + '</div></div></section>')
    admbar = ('<div class="admbar"><button type="button" id="admrefresh" class="admbtn">↻ Refresh</button>'
              '<button type="button" id="admprune" class="admbtn">🧹 Dọn list</button>'
              '<span id="admmsg" class="admmsg"></span></div>') if admin else ""
    homesearch = ('<div class="chsearch"><input id="homeq" type="text" inputmode="search" '
                  'autocomplete="off" placeholder="Search comics…">' + SEARCH_SVG + CLEAR_BTN + '</div>')
    grid = ('<section>' + sect_head("all", SECT_BOOK_SVG, "All Comics") + homesearch + admbar
            + '<div class="grid" id="grid">'
            + "".join(home_card_html(s, s["id"] in bmset, admin) for s in ordered)
            + '<div class="nores" id="homenores">Không tìm thấy truyện nào.</div>'
            + '</div></section>')
    # dữ liệu để JS dựng lại slider khi bấm bookmark (không tải lại trang)
    followdata = {}
    for s in ordered:
        _url, label = continue_info(s, ud["progress"])
        # url -> trang list chương (khớp follow_card_html), label giữ chương đang đọc dở
        followdata[s["id"]] = {"cover": cover_url(s), "title": s["title"],
                               "url": u("series", s["id"]), "label": label}
    body = ('<div class="wrap">' + account_header(user) + slider + grid + '</div>' + TOTOP_HTML
            + f'<script>const FOLLOWDATA={js(followdata)};let BM={js(bmorder)};'
            f'const LOGGEDIN={js(bool(user))};const ADMIN={js(admin)};'
            f'const UK={js(user_key(user))};</script>'
            + static_tag('ls.js') + static_tag('acct.js') + static_tag('home.js')
            + (static_tag('admin.js') if admin else ''))
    return page("TOONY READER", body)


SORT_SVG = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="M8 4v16m0-16-4 4m4-4 4 4'
            'M16 20V4m0 16 4-4m-4 4-4-4"/></svg>')

SEARCH_SVG = ('<svg class="chsearch-ic" width="18" height="18" viewBox="0 0 24 24" '
              'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
              'stroke-linejoin="round"><circle cx="11" cy="11" r="7"/>'
              '<path d="m21 21-4.3-4.3"/></svg>')

# Nút xoá text tìm kiếm (chỉ hiện khi ô có chữ — CSS lo). tabindex=-1: dùng Esc để
# xoá bằng bàn phím, giữ luồng Tab gọn.
CLEAR_BTN = ('<button type="button" class="chclear" aria-label="Xoá tìm kiếm" tabindex="-1">'
             '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
             'stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>')


def html_series(s, user=None):
    sid = s["id"]
    ud = user_data(user["id"]) if user else _default_udata()
    sections = []
    # Server render mặc định chương mới nhất trên cùng (đảo arc + chương trong arc);
    # nút sort đổi sang "Cũ nhất" thì JS đảo lại DOM. order/byrel (điều hướng đọc)
    # vẫn theo chiều tăng dần nên không bị ảnh hưởng. Mỗi arc bọc trong .arcsec để
    # JS đảo/lọc gọn.
    for a in reversed(s["arcs"]):
        inner = f'<h2 class="arc">{html.escape(a["name"])}</h2>' if a["name"] else ""
        items = "".join(
            f'<a class="ch" data-rel="{html.escape(ch["rel"], quote=True)}" '
            f'data-num="{html.escape(ch["num"], quote=True)}" '
            f'href="{read_url(sid, ch["rel"])}">{html.escape(ch["name"])}</a>'
            for ch in reversed(a["chapters"]))
        sections.append(f'<section class="arcsec">{inner}<div class="chgrid">{items}</div></section>')
    st = series_status(sid)
    n_arcs = sum(1 for a in s["arcs"] if a["name"])
    meta = (f'<span class="chapn">{s["total"]}</span> chaps'
            + (f' · {n_arcs} arc' if n_arcs > 1 else "")
            + f' · <span class="st {st}">{STATUS_LABELS[st]}</span>')
    # Server render theo tài khoản đang đăng nhập: nút bookmark, nút "reading"
    # (đang đọc dở) và làm mờ chương đã đọc. Guest -> mặc định (chưa theo dõi).
    # Chỉ là BEST-EFFORT ban đầu: HTML này nằm trong cache SW (SWR) nên có thể cũ;
    # series.js syncReading() sẽ vá lại nút reading + làm-mờ từ nguồn sống.
    bm = sid in set(ud["bookmarks"])
    first = s["order"][0] if s["order"] else None
    latest = s["order"][-1] if s["order"] else None
    prog = ud["progress"].get(sid)
    chapbtns = ""
    if first:
        chapbtns += f'<a class="cbtn first" href="{read_url(sid, first)}">First Chapter</a>'
        if prog and prog.get("rel") in s["byrel"]:
            rrel = prog["rel"]
            num = fmt_num(chapter_num(s["byrel"][rrel]["name"]))
            lbl = f'Chapter {num} - reading' if num else html.escape(s["byrel"][rrel]["name"]) + ' - reading'
            chapbtns += f'<a class="cbtn reading" href="{read_url(sid, rrel)}">{lbl}</a>'
        else:
            chapbtns += f'<a class="cbtn latest" href="{read_url(sid, latest)}">Latest Chapter</a>'
    chapbtns = f'<div class="chapbtns">{chapbtns}</div>' if chapbtns else ""
    chhead = (
        '<div class="chhead">'
        f'<span class="chcount"><span class="chapn">{s["total"]}</span> chapters</span>'
        f'<button type="button" id="sortbtn" class="sortbtn">{SORT_SVG}'
        '<span id="sortlbl">Newest</span></button></div>'
        '<div class="chsearch">'
        '<input id="chq" type="text" inputmode="search" autocomplete="off" '
        f'placeholder="Search chapters…">{SEARCH_SVG}{CLEAR_BTN}</div>')
    sdata = {"sid": sid, "read": ud["read"].get(sid, []), "uk": user_key(user)}
    body = (f'<div class="wrap">' + account_header(user)
            + f'<div class="shead"><img src="{cover_url(s)}" alt="">'
            f'<div class="sinfo"><h1>{html.escape(s["title"])}</h1>'
            f'<div class="smeta">{meta}</div>'
            f'<div class="sfollow">{bookmark_btn(bm, "sbk")}</div>'
            f'</div></div>' + chapbtns + chhead
            + '<div id="chapters" data-order="new">' + "".join(sections)
            + '<div class="nores" id="chnores">Không tìm thấy chương nào.</div></div></div>'
            + TOTOP_HTML
            + f'<script>const SDATA={js(sdata)};const LOGGEDIN={js(bool(user))};</script>'
            + static_tag('ls.js') + static_tag('acct.js') + static_tag('series.js'))
    return page(s["title"], body)


def js(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _page_ver(ch_dir, fname):
    """mtime_ns của 1 trang — chính là phần ?v= trong URL ảnh (xem img_url)."""
    try:
        return os.stat(os.path.join(ch_dir, fname)).st_mtime_ns
    except OSError:
        return 0


def pages_version(ch_dir, files):
    """Chữ ký RẺ của danh sách ảnh 1 chương (tên + mtime, chỉ stat, không mở ảnh).
    Đổi khi thêm/xoá/THAY file (vd repair tráo ô ghi đè 010.webp) -> client so với
    D.pv để biết HTML đang cầm (có thể là bản SW cache cũ) đã lệch đĩa chưa."""
    h = hashlib.sha1()
    for f in files:
        h.update(f"{f}:{_page_ver(ch_dir, f)}|".encode("utf-8", "surrogatepass"))
    return h.hexdigest()[:12]


def chapter_pages(s, rel):
    """Payload /api/pages/<sid>/<rel>: {version, pages:[{n,url,w,h}]} — nguồn SỐNG để
    trang đọc tự vá src/aspect-ratio tại chỗ khi ảnh trên đĩa đổi (02/09: ảnh tráo ô
    được repair thay nhưng HTML trong SW cache vẫn trỏ ?v= cũ -> ảnh cũ). url y hệt
    img_url() của html_reader (?v=mtime) để cache SW/HTTP khớp khoá."""
    sid = s["id"]
    ch_dir = os.path.join(s["path"], *rel.split("/"))
    files = list_images(ch_dir)
    pages = []
    for f in files:
        v = _page_ver(ch_dir, f)
        base = u("img", sid, *rel.split("/"), f)
        wh = img_dims(os.path.join(ch_dir, f))
        pages.append({"n": f, "url": f"{base}?v={v}" if v else base,
                      "w": wh[0] if wh else 0, "h": wh[1] if wh else 0})
    return {"version": pages_version(ch_dir, files), "pages": pages}


def html_reader(s, rel, user=None):
    sid = s["id"]
    info = s["byrel"][rel]
    idx = info["idx"]
    prev_rel = s["order"][idx - 1] if idx > 0 else None
    next_rel = s["order"][idx + 1] if idx + 1 < len(s["order"]) else None
    prev_url = read_url(sid, prev_rel) if prev_rel else None
    next_url = read_url(sid, next_rel) if next_rel else None
    series_url = u("series", sid)

    ch_dir = os.path.join(s["path"], *rel.split("/"))
    files = list_images(ch_dir)

    # gom các cặp đã ghép thủ công thành 1 đơn vị hiển thị
    pairmap = {}
    for p in chapter_spreads(sid, rel):
        pairmap[frozenset((p["left"], p["right"]))] = (p["left"], p["right"])
    units = []
    i = 0
    while i < len(files):
        if i + 1 < len(files):
            key = frozenset((files[i], files[i + 1]))
            if key in pairmap:
                units.append(("spread",) + pairmap[key])
                i += 2
                continue
        units.append(("img", files[i]))
        i += 1

    def attr(fname):
        return html.escape(fname, quote=True)

    def img_url(fname):
        # Gắn ?v=mtime để URL ĐỔI mỗi khi file đổi (vd upgrade Asura->Official làm
        # ảnh đổi kích thước). SW cache ảnh kiểu cache-first + khoá theo URL: URL
        # đứng yên -> bytes CŨ bị giữ, nhồi vào aspect-ratio MỚI của HTML -> méo ảnh
        # (disk đúng nhưng reader méo). Cover đã versioned sẵn (cover_url) — đây là
        # chỗ ảnh chương còn thiếu. Route /img bỏ qua query nên ?v không phá gì.
        base = u("img", sid, *rel.split("/"), fname)
        try:
            return f"{base}?v={os.stat(os.path.join(ch_dir, fname)).st_mtime_ns}"
        except OSError:
            return base

    imgs = []
    for ui, unit in enumerate(units):
        # 3 đơn vị đầu tải ngay; còn lại để data-src cho bộ nạp tuần tự (JS)
        # nạp dần theo thứ tự đọc -> mở trang là cả chương tự về như Asura,
        # nhưng trang sát vị trí đọc luôn được ưu tiên về trước. Ảnh lỗi do
        # JS tự retry (xem READER_JS), kể cả 3 ảnh đầu.
        def src_attr(url, ui=ui):
            return f' src="{url}"' if ui < 3 else f' data-src="{url}"'
        if unit[0] == "img":
            fname = unit[1]
            wh = img_dims(os.path.join(ch_dir, fname))
            ar = f' style="aspect-ratio:{wh[0]}/{wh[1]}"' if wh else ""
            imgs.append(f'<img{src_attr(img_url(fname))} data-f="{attr(fname)}" '
                        f'decoding="async"{ar} alt="">')
            # nút ghép với trang kế (chỉ giữa 2 trang đơn, chỉ hiện ở chế độ ghép)
            nxt = units[ui + 1] if ui + 1 < len(units) else None
            if nxt and nxt[0] == "img":
                imgs.append(
                    f'<div class="jbar"><button data-act="join" data-a="{attr(fname)}" '
                    f'data-b="{attr(nxt[1])}">⧉ Join 2 pages (top–bottom)</button></div>')
        else:
            _, left, right = unit
            wl = img_dims(os.path.join(ch_dir, left))
            wr = img_dims(os.path.join(ch_dir, right))
            if wl and wr:
                rl, rr = wl[0] / wl[1], wr[0] / wr[1]
                ar = f'aspect-ratio:{rl + rr:.4f};'
                lpct, rpct = rl / (rl + rr) * 100, rr / (rl + rr) * 100
            else:
                ar, lpct, rpct = "", 50.0, 50.0
            imgs.append(
                f'<div class="spread" style="{ar}">'
                f'<img{src_attr(img_url(left))} data-f="{attr(left)}" decoding="async" '
                f'style="width:{lpct:.3f}%" alt="">'
                f'<img{src_attr(img_url(right))} data-f="{attr(right)}" decoding="async" '
                f'style="width:{rpct:.3f}%" alt="">'
                f'<div class="sctl"><button data-act="flip" data-a="{attr(left)}">⇄ Swap L/R</button>'
                f'<button data-act="split" data-a="{attr(left)}">Split</button></div></div>')

    opts = []
    # Chương mới nhất trên cùng, đồng bộ với trang danh sách chương.
    for a in reversed(s["arcs"]):
        grouped = bool(a["name"]) or len(s["arcs"]) > 1
        if grouped:
            opts.append(f'<optgroup label="{html.escape(a["name"] or "Khác", quote=True)}">')
        for ch in reversed(a["chapters"]):
            sel = " selected" if ch["rel"] == rel else ""
            opts.append(f'<option value="{read_url(sid, ch["rel"])}"{sel}>'
                        f'{html.escape(ch["name"])}</option>')
        if grouped:
            opts.append("</optgroup>")

    def navbtn(url, label, acc=False):
        cls = "navbtn" + (" acc" if acc else "") + ("" if url else " dis")
        href = f' href="{url}"' if url else ""
        return f'<a class="{cls}"{href}>{label}</a>'

    endbox = ('<div id="endbox"><div class="endt">— END OF CHAPTER —</div>'
              '<div class="endrow">'
              + navbtn(prev_url, "‹ Prev")
              + (navbtn(next_url, "Next Chapter ›", acc=True) if next_url
                 else navbtn(None, "Latest chapter"))
              + '</div>'
              + f'<a class="navbtn" href="{series_url}">Back to Series</a></div>')

    # Vị trí đọc dở: server nhúng D.y/D.ts theo tài khoản (best-effort — HTML này
    # có thể là bản SW cache/prefetch CŨ), client so ts với mirror localStorage
    # (ls.js) và lấy bản MỚI hơn khi khôi phục. D.name để ghi kèm vào progress
    # (nhãn card home), D.uk để namespace mirror theo tài khoản.
    prog = user_data(user["id"])["progress"].get(sid) if user else None
    cur = prog if (prog and prog.get("rel") == rel) else None
    data = {"sid": sid, "rel": rel, "name": info["name"],
            "prev": prev_url, "next": next_url,
            "y": cur["y"] if cur else 0,
            "ts": (cur.get("ts") or 0) if cur else 0,
            "uk": user_key(user),
            # chữ ký danh sách ảnh lúc render -> syncPages() (reader.js) so với
            # /api/pages để vá ảnh tại chỗ khi HTML này là bản SW cache cũ.
            "pv": pages_version(ch_dir, files)}
    body = (
        f'<header id="topbar" class="bar hide">'
        f'<a class="iconbtn home" href="/" title="Library">{HOME_SVG}</a>'
        f'<a class="tinfo" href="{series_url}" title="Chapters">'
        f'<img class="tcov" src="{cover_url(s)}" alt="">'
        f'<div class="titles"><div class="s">{html.escape(s["title"])}</div>'
        f'<div class="c">{html.escape(info["name"])}</div></div></a>'
        f'<div class="zoomctl" title="Image size — 100% default">'
        f'<button type="button" class="zbtn" id="zdec" title="Smaller">−</button>'
        f'<input id="zval" class="zval" type="text" inputmode="numeric" value="100%" aria-label="Image size">'
        f'<button type="button" class="zbtn" id="zinc" title="Larger">+</button></div>'
        f'<button id="jmode" class="iconbtn" title="Join double page">⧉</button></header>'
        '<script>(function(){try{var p=parseInt(localStorage.getItem("imgw"),10);'
        'if(p>=1)document.documentElement.style.setProperty("--imgw",(p/100*800)+"px");}catch(e){}})();</script>'
        f'<main id="strip">{"".join(imgs)}</main>{endbox}'
        f'<footer id="botbar" class="bar hide">'
        + navbtn(prev_url, "‹ Prev")
        + ('<div class="chwrap">'
           '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
           'stroke-width="2.2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>'
           f'<span class="lbl">{html.escape(info["name"])}</span>'
           '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
           'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>'
           f'<select id="chsel">{"".join(opts)}</select></div>')
        + navbtn(next_url, "Next ›", acc=True)
        + "</footer>"
        + '<div id="tapcue">Tap to show controls</div>'
        f"<script>const D={js(data)};const LOGGEDIN={js(bool(user))};</script>"
        + static_tag('ls.js') + static_tag('reader.js'))
    return page(f'{info["name"]} - {s["title"]}', body, body_class="reader")


# Kho localStorage per-device. GUEST (chưa đăng nhập): bookmark / tiến trình /
# đã-đọc lưu trọn ở đây. ĐÃ đăng nhập: nguồn chính vẫn là server per-account,
# nhưng tiến trình đọc có thêm MIRROR per-tài-khoản (key theo UK = hash ngắn của
# uid, server nhúng) — vì HTML server render nằm trong cache SW (stale-while-
# revalidate) nên nút "reading"/D.y bake sẵn có thể CŨ; entry nào cũng đóng dấu
# ts để client so độ tươi và lấy bản mới hơn. Không di trú guest<->account.
# Nạp trên cả 3 trang trước HOME/SERIES/READER JS.
LS_JS = """
(function(){
  function rd(k,d){try{var v=localStorage.getItem(k);return v?JSON.parse(v):d;}catch(e){return d;}}
  function wr(k,v){try{localStorage.setItem(k,JSON.stringify(v));}catch(e){}}
  window.LS={
    bms:function(){return rd('toony_bm',[]);},
    isBm:function(sid){return this.bms().indexOf(sid)>=0;},
    toggleBm:function(sid,on){var a=this.bms(),i=a.indexOf(sid);
      if(on&&i<0)a.push(sid); if(!on&&i>=0)a.splice(i,1); wr('toony_bm',a); return a;},
    getProg:function(sid){return rd('toony_prog',{})[sid]||null;},
    setProg:function(sid,rel,y,name){var p=rd('toony_prog',{});
      p[sid]={rel:rel,y:y,name:name||'',ts:Date.now()};wr('toony_prog',p);},
    // mirror tiến trình cho TÀI KHOẢN đang đăng nhập (uk rỗng -> no-op/null)
    mget:function(uk,sid){if(!uk)return null;return rd('toony_prog_u_'+uk,{})[sid]||null;},
    mset:function(uk,sid,rel,y,name){if(!uk)return;var k='toony_prog_u_'+uk,p=rd(k,{});
      p[sid]={rel:rel,y:y,name:name||'',ts:Date.now()};wr(k,p);},
    // chọn bản tiến trình MỚI hơn theo ts (entry cũ thiếu ts -> coi như 0)
    newer:function(a,b){if(!a)return b;if(!b)return a;return ((b.ts||0)>(a.ts||0))?b:a;},
    reads:function(sid){return rd('toony_read',{})[sid]||[];},
    addRead:function(sid,rel){var r=rd('toony_read',{}),a=r[sid]||[];
      if(a.indexOf(rel)<0){a.push(rel);r[sid]=a;wr('toony_read',r);}}
  };
})();
"""

ACCT_JS = """
(function(){
  // Login/logout đổi trạng thái theo tài khoản -> phải xoá cache HTML của SW
  // (khoá theo URL, không phân biệt cookie) rồi mới reload, để trang tải lại
  // đúng trạng thái mới. Bìa/CSS/JS vẫn nằm trong cache SW -> reload nhanh,
  // KHÔNG nháy đen bìa. Có ack qua MessageChannel để reload sau khi xoá xong;
  // fallback 300ms phòng SW không phản hồi.
  function purgeAndReload(){
    var sw=navigator.serviceWorker;
    if(!(sw&&sw.controller)){ location.reload(); return; }
    var done=false, go=function(){ if(!done){done=true;location.reload();} };
    try{
      var ch=new MessageChannel();
      ch.port1.onmessage=go;
      sw.controller.postMessage({type:'purge-pages'},[ch.port2]);
      setTimeout(go,300);
    }catch(e){ go(); }
  }
  // Xoá 1 trang khỏi cache HTML của SW khi bookmark của nó đổi (chỉ cần cho tài
  // khoản — trang series render nút bookmark từ server; guest thì series.js tự
  // hydrate từ localStorage nên không lệ thuộc cache). No-op nếu chưa có SW.
  window.TOONY_PURGE_PAGE=function(url){
    var sw=navigator.serviceWorker;
    if(sw&&sw.controller&&url){
      try{ sw.controller.postMessage({type:'purge-page',url:url}); }catch(e){}
    }
  };
  // đưa con trỏ vào ô đăng nhập (gọi khi guest bấm bookmark)
  window.TOONY_LOGIN=function(){
    var u=document.getElementById('uname');
    if(u){ u.focus(); u.classList.add('flash');
      setTimeout(function(){u.classList.remove('flash');},700); }
  };
  var f=document.getElementById('loginform');
  if(f) f.addEventListener('submit',function(e){
    e.preventDefault();
    var u=document.getElementById('uname'), err=document.getElementById('accerr');
    var name=(u.value||'').trim(); if(err) err.textContent='';
    if(!name){ TOONY_LOGIN(); return; }
    var btn=f.querySelector('button'); btn.disabled=true;
    fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:name})})
    .then(function(r){return r.json();}).then(function(res){
      btn.disabled=false;
      if(res&&res.ok){ purgeAndReload(); }
      else if(err){ err.textContent=(res&&res.error)?res.error:'Login failed'; }
    }).catch(function(){btn.disabled=false; if(err) err.textContent='Connection error';});
  });
  var lo=document.getElementById('logoutbtn');
  if(lo) lo.addEventListener('click',function(){
    lo.disabled=true;
    fetch('/api/logout',{method:'POST'}).then(function(){purgeAndReload();})
      .catch(function(){lo.disabled=false;});
  });
})();
"""

HOME_JS = """
(function(){
  var grid=document.getElementById('grid');
  function esc(s){return (s||'').replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}

  // tạo 1 card theo dõi (server nhúng sẵn label/url theo tiến trình của tài khoản)
  function buildFcard(sid){
    var d=FOLLOWDATA[sid]; if(!d) return null;
    var a=document.createElement('a');
    a.className='fcard'; a.href=d.url; a.dataset.sid=sid;
    a.innerHTML='<img src="'+d.cover+'" loading="lazy" alt="">'+
      '<div class="fct" title="'+esc(d.title)+'">'+esc(d.title)+'</div>'+
      '<div class="fcm">'+esc(d.label)+'</div>';
    return a;
  }
  // đồng bộ hàng "Bookmarked" theo THỨ TỰ BẤM (BM), CHÈN/GỠ từng card
  // (không dựng lại innerHTML -> ảnh không tải lại/chớp). Đóng/mở mục co giãn mượt.
  // BM giữ thứ tự bấm (afterToggle push cuối, bỏ-rồi-bấm-lại về cuối); lọc truyện
  // không còn dữ liệu card.
  function renderFollows(){
    var sec=document.getElementById('follows'), row=document.getElementById('frow');
    if(!sec||!row) return;
    var ids=BM.filter(function(s){return !!FOLLOWDATA[s];});
    if(ids.length===0){ sec.classList.remove('open'); return; }
    var idset={}; ids.forEach(function(s){idset[s]=1;});
    var have={};
    [].slice.call(row.children).forEach(function(el){
      if(idset[el.dataset.sid]) have[el.dataset.sid]=el; else row.removeChild(el);
    });
    ids.forEach(function(sid){
      var el=have[sid]||buildFcard(sid);
      if(el) row.appendChild(el);
    });
    sec.classList.add('open');
  }
  (function(){
    var sec=document.getElementById('follows'), row=document.getElementById('frow');
    if(!sec||!row) return;
    sec.addEventListener('transitionend',function(e){
      if(e.propertyName!=='grid-template-rows'||sec.classList.contains('open')) return;
      while(row.firstChild) row.removeChild(row.firstChild);
    });
  })();

  function setBk(b,on){
    b.classList.toggle('on',on);
    var t=b.querySelector('.bktext'); if(t) t.textContent=on?'Bookmarked':'Bookmark';
  }
  // bấm bookmark: guest -> mời đăng nhập; đã đăng nhập -> ghi server + cập nhật slider
  function afterToggle(sid,on,b){
    setBk(b,on);
    if(on){if(BM.indexOf(sid)<0)BM.push(sid);}
    else BM=BM.filter(function(x){return x!==sid;});
    renderFollows();
  }
  // Áp lại trạng thái bookmark cho toàn lưới + hàng follows theo BM hiện tại
  // (idempotent — gọi lại bao nhiêu lần cũng không double).
  function applyBM(){
    [].forEach.call(grid.querySelectorAll('.card'),function(c){
      var b=c.querySelector('.bkbtn'); if(b) setBk(b,BM.indexOf(c.dataset.sid)>=0);
    });
    renderFollows();
  }
  // Vá nhãn "đang đọc" (.fcm) của card theo dõi từ nguồn sống — nhãn bake trong
  // HTML/FOLLOWDATA có thể là bản SW cache cũ (SWR) -> hiện chương đọc dở đời
  // trước. progMap: sid -> {rel,y,name,ts}; đã đăng nhập thì so ts với mirror
  // localStorage (bản mới hơn thắng). Entry thiếu name (JS đời cũ) -> giữ nhãn cũ.
  function applyLabels(progMap){
    Object.keys(FOLLOWDATA).forEach(function(s){
      var p=progMap?progMap[s]:null;
      if(LOGGEDIN) p=LS.newer(p,LS.mget(UK,s));
      if(p&&p.name&&FOLLOWDATA[s]) FOLLOWDATA[s].label=p.name;
    });
    var row=document.getElementById('frow'); if(!row) return;
    [].forEach.call(row.children,function(el){
      var d=FOLLOWDATA[el.dataset.sid], m=el.querySelector('.fcm');
      if(d&&m&&m.textContent!==d.label) m.textContent=d.label;
    });
  }
  function guestProgMap(){                     // gom localStorage -> map cùng dạng
    var out={};
    Object.keys(FOLLOWDATA).forEach(function(s){
      var p=LS.getProg(s); if(p) out[s]=p; });
    return out;
  }
  // Nạp BM + nhãn đang đọc từ nguồn SỐNG (guest: localStorage; đăng nhập:
  // /api/state) rồi áp lại. Chạy cả lúc LOAD (HTML có thể là bản SW cache cũ) lẫn
  // khi khôi phục bfcache (DOM đóng băng trong lúc đọc ở trang khác). Lỗi mạng ->
  // giữ nguyên bookmark, riêng nhãn vẫn vá được từ mirror localStorage.
  function syncBM(){
    if(!LOGGEDIN){ BM=LS.bms(); applyBM(); applyLabels(guestProgMap()); return; }
    fetch('/api/state').then(function(r){return r.json();}).then(function(res){
      if(res&&Array.isArray(res.bookmarks)){ BM=res.bookmarks; applyBM(); }
      applyLabels(res&&res.progress?res.progress:null);
    }).catch(function(){ applyLabels(null); });
  }
  addEventListener('pageshow',function(e){ if(e.persisted) syncBM(); });
  grid.addEventListener('click',function(e){
    var b=e.target.closest('.bkbtn'); if(!b) return;
    e.preventDefault();
    var sid=b.closest('.card').dataset.sid, on=!b.classList.contains('on');
    if(!LOGGEDIN){ LS.toggleBm(sid,on); afterToggle(sid,on,b); return; }
    b.disabled=true;
    fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({op:'bookmark',sid:sid,on:on})})
    .then(function(r){return r.json();}).then(function(res){
      b.disabled=false;
      if(res&&res.ok){
        afterToggle(sid,on,b);
        // HTML server của trang series này giờ đã cũ trong cache SW -> xoá để
        // lần vào sau tải bản tươi (khớp nút bookmark). Guest không cần.
        var d=FOLLOWDATA[sid];
        if(d&&d.url&&window.TOONY_PURGE_PAGE) TOONY_PURGE_PAGE(d.url);
      }
    }).catch(function(){b.disabled=false;});
  });
  // hydrate lúc load từ nguồn sống: guest lấy localStorage (server render trung
  // tính); tài khoản hỏi /api/state — vì HTML server render có thể là bản SW
  // cache cũ (bookmark/nhãn đang đọc bake sẵn đã lỗi thời).
  syncBM();
  // --- Tìm truyện trong lưới All Comics + KHÔI PHỤC trạng thái lọc khi quay lại ---
  // Bộ lọc tách thành hàm idempotent -> chạy lại được ở MỌI đường vào (load / bfcache
  // / admin-reload) nên ô search và lưới luôn khớp. iOS Safari hay xoá value input khi
  // khôi phục bfcache nhưng GIỮ display:none của card -> tự tái lập value từ sessionStorage.
  var hq=document.getElementById('homeq');
  var hnr=document.getElementById('homenores');
  var hwrap=hq?hq.closest('.chsearch'):null;
  function applyHomeFilter(){
    var term=(hq?hq.value:'').trim().toLowerCase(), any=false;
    [].forEach.call(grid.querySelectorAll('.card'),function(c){
      var t=((c.querySelector('.ct')||{}).textContent||'').toLowerCase();
      var hit=(!term || t.indexOf(term)>=0);
      c.style.display=hit?'':'none'; if(hit)any=true;
    });
    if(hnr) hnr.classList.toggle('on', !!term && !any);
    // toggle nút X gộp vào đây -> đồng bộ ở MỌI đường vào (gõ / load / bfcache / reconcile)
    if(hwrap) hwrap.classList.toggle('has-val', !!(hq&&hq.value));
  }
  function clearHomeq(){                          // bấm X hoặc Esc: xoá + lọc lại + giữ focus
    if(!hq) return;
    hq.value='';
    try{ sessionStorage.removeItem('homeq'); }catch(e){}  // tránh bfcache kéo chữ về
    applyHomeFilter();
    hq.focus();
  }
  if(hwrap){ var hx=hwrap.querySelector('.chclear'); if(hx) hx.addEventListener('click', clearHomeq); }
  if(hq) hq.addEventListener('keydown',function(e){
    if(e.key==='Escape' && hq.value){ e.preventDefault(); clearHomeq(); }
  });
  function restoreHomeq(){                       // tái lập value ô search từ phiên tab
    try{ var sq=sessionStorage.getItem('homeq'); if(hq && sq!=null) hq.value=sq; }catch(e){}
  }
  if(hq) hq.addEventListener('input',function(){
    try{ sessionStorage.setItem('homeq', hq.value); }catch(e){}  // bền theo phiên tab
    applyHomeFilter();
  });
  // Lúc load: khôi phục keyword rồi áp lọc. 'homey' là cuộn one-shot do admin
  // reloadKeepSearch đặt (order/prune/refresh) -> dùng 1 lần rồi xoá.
  restoreHomeq();
  try{
    var sy=sessionStorage.getItem('homey'); sessionStorage.removeItem('homey');
    if(sy){ window.scrollTo(0, parseInt(sy,10)||0); }
  }catch(e){}
  applyHomeFilter();

  // --- B5: vá số chương / trạng thái / bìa TẠI CHỖ khi trang hiển thị (xuyên bfcache
  // + SW cache mà không tải lại cả trang). version = chữ ký payload -> chỉ đụng DOM
  // khi có thay đổi thật. Mẫu giống syncBM.
  var lastMetaVer=null;
  function applyMeta(res){
    if(!res||!res.series||!res.version||res.version===lastMetaVer) return;
    lastMetaVer=res.version; var S=res.series;
    [].forEach.call(document.querySelectorAll('.card'),function(c){
      var m=S[c.dataset.sid]; if(!m) return;
      var n=c.querySelector('.chapn'); if(n) n.textContent=m.total;
      var st=c.querySelector('.st'); if(st){ st.className='st '+m.status; st.textContent=m.label; }
      var img=c.querySelector('.cardlink img');
      if(img&&m.cover&&img.getAttribute('src')!==m.cover) img.src=m.cover;
      try{ if(FOLLOWDATA[c.dataset.sid]&&m.cover) FOLLOWDATA[c.dataset.sid].cover=m.cover; }catch(e){}
    });
  }
  function syncCounts(){
    fetch('/api/library-meta',{credentials:'same-origin'})
      .then(function(r){return r.json();}).then(applyMeta).catch(function(){});
  }
  // Khôi phục ô search sau khi khôi phục bfcache. iOS Safari áp phần khôi phục
  // form-control của RIÊNG nó SAU sự kiện pageshow -> nếu ghi value ĐỒNG BỘ ở đây
  // sẽ bị nó ghi RỖNG đè lên (ô trống nhưng list vẫn lọc, vì applyHomeFilter đã chạy
  // trước). Trị: HOÃN sang sau nhịp khôi phục của iOS (double-rAF + 1 setTimeout dự
  // phòng), rồi ÉP LẠI value từ sessionStorage (nguồn sự thật) + lọc lại. Hàm
  // idempotent + chốt so-sánh nên chạy nhiều nhịp không nháy: nhịp nào value đã đúng
  // thì bỏ qua, KHÔNG applyHomeFilter thừa.
  function reconcileSearch(){
    if(!hq) return;
    var saved=null; try{ saved=sessionStorage.getItem('homeq'); }catch(e){}
    if(saved==null) return;
    if(hq.value===saved) return;        // đã đúng (nhịp trước lo rồi) -> khỏi đụng
    hq.value=saved; applyHomeFilter();
  }
  function deferReconcile(){
    if(window.requestAnimationFrame){
      requestAnimationFrame(function(){ requestAnimationFrame(reconcileSearch); });
    } else { setTimeout(reconcileSearch,0); }
    setTimeout(reconcileSearch,120);    // dự phòng nếu iOS khôi phục trễ hơn 2 khung
  }
  // pageshow fires cả lúc load thường (persisted=false) lẫn khôi phục bfcache
  // (persisted=true) -> bao trọn mọi đường vào.
  addEventListener('pageshow',function(e){
    if(e.persisted) deferReconcile();   // bfcache: tái lập ô search SAU khi iOS xong
    syncCounts();
  });
  document.addEventListener('visibilitychange',function(){
    if(document.visibilityState==='visible') syncCounts();
  });

  // --- Prefetch trang series vào cache SW -> lần bấm ĐẦU cũng vào tức thì
  // (không còn chờ 2-3s tải HTML). Nạp trước khi (a) chạm/di chuột vào card
  // [ý định], và (b) card lọt tầm nhìn lúc rảnh [đón đầu], giới hạn trong SW.
  function pf(urls){
    var c=navigator.serviceWorker&&navigator.serviceWorker.controller;
    if(!c||!urls.length) return;
    try{ c.postMessage({type:'prefetch',urls:urls}); }catch(e){}
  }
  document.addEventListener('pointerdown',function(e){
    var a=e.target.closest&&e.target.closest('.cardlink,.fcard');
    if(a&&a.href) pf([a.href]);
  },{passive:true});
  if('IntersectionObserver' in window){
    var idle=window.requestIdleCallback||function(f){return setTimeout(f,300);};
    var io=new IntersectionObserver(function(ents){
      var urls=[];
      ents.forEach(function(en){
        if(en.isIntersecting&&en.target.href){ urls.push(en.target.href); io.unobserve(en.target); }
      });
      if(urls.length) idle(function(){ pf(urls); });
    },{rootMargin:'300px'});
    [].forEach.call(document.querySelectorAll('.cardlink,.fcard'),function(a){io.observe(a);});
  }
})();
"""

ADMIN_JS = """
(function(){
  if(typeof ADMIN==='undefined' || !ADMIN) return;
  function post(body){ return fetch('/api/admin',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(function(r){return r.json();}); }
  var grid=document.getElementById('grid');
  // Reload nhưng GIỮ ô search + vị trí cuộn (dùng cho order/prune/refresh — vốn phải
  // dựng lại cả danh sách). HOME_JS đọc lại 2 khoá này lúc trang load.
  function reloadKeepSearch(){
    try{
      var hq=document.getElementById('homeq');
      sessionStorage.setItem('homeq', hq?hq.value:'');
      sessionStorage.setItem('homey', String(window.pageYOffset||0));
    }catch(e){}
    location.reload();
  }
  // Đồng bộ card trong slider Bookmarked (nếu truyện đang được bookmark) + FOLLOWDATA
  // -> sửa tên/bìa tại chỗ không để slider hiển thị bản cũ. (status không hiện ở slider.)
  function syncSlider(sid, title, cover){
    var fc=null;
    [].forEach.call(document.querySelectorAll('.fcard'),function(f){
      if(f.dataset.sid===sid) fc=f; });
    if(fc){
      if(title!=null){ var ft=fc.querySelector('.fct');
        if(ft){ ft.textContent=title; ft.title=title; } }
      if(cover!=null){ var fi=fc.querySelector('img'); if(fi) fi.src=cover; }
    }
    try{
      if(typeof FOLLOWDATA!=='undefined' && FOLLOWDATA[sid]){
        if(title!=null) FOLLOWDATA[sid].title=title;
        if(cover!=null) FOLLOWDATA[sid].cover=cover;
      }
    }catch(e){}
  }
  // đổi bìa: 1 input file dùng chung, nhớ card đang thao tác
  var covin=document.createElement('input');
  covin.type='file'; covin.accept='image/*'; covin.style.display='none';
  document.body.appendChild(covin);
  var covBtn=null;
  covin.addEventListener('change',function(){
    var f=covin.files&&covin.files[0]; if(!f||!covBtn){covin.value='';return;}
    var sid=covBtn.closest('.card').dataset.sid, b=covBtn;
    var rd=new FileReader();
    rd.onload=function(){
      b.disabled=true;
      post({op:'cover',sid:sid,data:rd.result}).then(function(res){
        b.disabled=false;
        if(res&&res.ok){
          var img=b.closest('.card').querySelector('.cardlink img');
          if(img && res.cover) img.src=res.cover;   // URL có ?v= mtime mới -> tải bìa mới
          syncSlider(sid, null, res.cover);
        } else alert('Đổi bìa thất bại (ảnh lỗi hoặc quá lớn).');
      }).catch(function(){b.disabled=false;});
    };
    rd.readAsDataURL(f);
    covin.value='';
  });
  if(grid) grid.addEventListener('click',function(e){
    // Đổi bìa (ImagePlus, nổi trên ảnh) — nút nằm NGOÀI .cardlink
    var cov=e.target.closest('.covedit');
    if(cov){ e.preventDefault();
      var ccard=cov.closest('.card'); if(!ccard) return;
      covBtn=cov; covin.click(); return; }
    // Đổi tên (SquarePen, cuối tên) — nút nằm TRONG thẻ <a> nên phải chặn điều hướng
    var te=e.target.closest('.titleedit');
    if(te){ e.preventDefault();
      var tcard=te.closest('.card'), tsid=tcard?tcard.dataset.sid:null; if(!tsid) return;
      var cur=((tcard.querySelector('.cttext')||{}).textContent||'').trim();
      var nv=prompt('Tên hiển thị mới (để trống = về tên gốc theo folder):',cur);
      if(nv===null) return;               // bấm Cancel
      te.disabled=true;
      post({op:'title',sid:tsid,title:nv}).then(function(res){
        te.disabled=false;
        if(res&&res.ok){
          var tt=res.title||'';
          var span=tcard.querySelector('.cttext');
          if(span){ span.textContent=tt; span.title=tt; }   // textContent: an toàn XSS
          syncSlider(tsid, tt, null);
        } else alert('Đổi tên thất bại.');
      }).catch(function(){te.disabled=false;});
      return;
    }
    var b=e.target.closest('.adm button'); if(!b) return;
    e.preventDefault();
    var card=b.closest('.card'), sid=card?card.dataset.sid:null; if(!sid) return;
    var op=b.dataset.op;
    if(op==='status'){
      // hướng toggle đọc từ class hiện tại của NÚT (nguồn sự thật) -> cập nhật tại chỗ
      var next=b.classList.contains('complete')?'ongoing':'complete';
      b.disabled=true;
      post({op:'status',sid:sid,status:next}).then(function(res){
        b.disabled=false;
        if(res&&res.ok){
          b.classList.toggle('complete', res.status==='complete');
          b.textContent=res.label;                       // nhãn trên nút
          var st=card.querySelector('.cm .st');           // nhãn "N chaps · <status>"
          if(st){ st.className='st '+res.status; st.textContent=res.label; }
        }
      }).catch(function(){b.disabled=false;});
      return;
    }
    // order (top/up/down): đảo thứ tự cả lưới -> reload nhưng giữ search + scroll
    b.disabled=true;
    post({op:'order',sid:sid,move:op}).then(function(res){
      if(res&&res.ok) reloadKeepSearch(); else b.disabled=false;
    }).catch(function(){b.disabled=false;});
  });
  var pr=document.getElementById('admprune'), msg=document.getElementById('admmsg');
  if(pr) pr.addEventListener('click',function(){
    pr.disabled=true;
    post({op:'prune'}).then(function(res){
      if(res&&res.ok){ if(msg) msg.textContent='Đã bỏ '+res.removed+' mục'; reloadKeepSearch(); }
      else pr.disabled=false;
    }).catch(function(){pr.disabled=false;});
  });
  var rf=document.getElementById('admrefresh');
  if(rf) rf.addEventListener('click',function(){
    rf.disabled=true;
    post({op:'refresh'}).then(function(){reloadKeepSearch();})
      .catch(function(){rf.disabled=false;});
  });
})();
"""

SERIES_JS = """
(function(){
  var sid=SDATA.sid;
  // làm mờ chương đã đọc (server nhúng danh sách read của tài khoản)
  try{
    var read=new Set(SDATA.read||[]);
    if(!LOGGEDIN){ LS.reads(sid).forEach(function(r){read.add(r);}); }
    document.querySelectorAll('a.ch').forEach(function(a){
      if(read.has(a.dataset.rel)) a.classList.add('read'); });
  }catch(e){}

  // nút theo dõi (bookmark): guest -> localStorage; đã đăng nhập -> ghi server
  var sbk=document.getElementById('sbk');
  function setSbk(on){ sbk.classList.toggle('on',on);
    var t=sbk.querySelector('.bktext'); if(t) t.textContent=on?'Bookmarked':'Bookmark'; }
  if(sbk && !LOGGEDIN && LS.isBm(sid)) setSbk(true);   // hydrate trạng thái guest
  if(sbk) sbk.addEventListener('click',function(){
    var on=!sbk.classList.contains('on');
    if(!LOGGEDIN){ LS.toggleBm(sid,on); setSbk(on); return; }
    sbk.disabled=true;
    fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({op:'bookmark',sid:sid,on:on})})
    .then(function(r){return r.json();}).then(function(res){
      sbk.disabled=false;
      if(res&&res.ok){
        setSbk(on);
        // Trang này (cache SW) giờ render nút bookmark cũ -> xoá để vào lại tươi.
        if(window.TOONY_PURGE_PAGE) TOONY_PURGE_PAGE(location.href);
      }
    }).catch(function(){sbk.disabled=false;});
  });
  // Khôi phục từ bfcache (persisted): bookmark có thể đã đổi ở home/nơi khác ->
  // đồng bộ lại nút. Guest: đọc localStorage; đăng nhập: hỏi /api/state. Chỉ khi
  // persisted (tải mới thì hydrate ở trên đã đúng).
  addEventListener('pageshow',function(e){
    if(!e.persisted||!sbk) return;
    if(!LOGGEDIN){ setSbk(LS.isBm(sid)); return; }
    fetch('/api/state').then(function(r){return r.json();}).then(function(res){
      if(res&&Array.isArray(res.bookmarks)) setSbk(res.bookmarks.indexOf(sid)>=0);
    }).catch(function(){});
  });

  // --- B5: vá số chương / trạng thái TẠI CHỖ khi trang hiển thị (xuyên bfcache + SW).
  // .chapn có trong cả .chcount ("N chapters") lẫn .smeta ("N chaps"); .smeta .st là
  // nhãn trạng thái. version = chữ ký payload -> chỉ đụng DOM khi có đổi thật.
  var lastMetaVer=null;
  function applySeriesMeta(res){
    if(!res||!res.series||!res.version||res.version===lastMetaVer) return;
    var m=res.series[sid]; if(!m) return;
    lastMetaVer=res.version;
    document.querySelectorAll('.chapn').forEach(function(n){ n.textContent=m.total; });
    var st=document.querySelector('.smeta .st');
    if(st){ st.className='st '+m.status; st.textContent=m.label; }
  }
  function syncCounts(){
    fetch('/api/library-meta',{credentials:'same-origin'})
      .then(function(r){return r.json();}).then(applySeriesMeta).catch(function(){});
  }
  addEventListener('pageshow',function(){ syncCounts(); });   // load thường + bfcache
  document.addEventListener('visibilitychange',function(){
    if(document.visibilityState==='visible') syncCounts();
  });

  // sort Mới nhất / Cũ nhất — server render mặc định 'new'; 'old' = đảo DOM
  var container=document.getElementById('chapters');
  var sortbtn=document.getElementById('sortbtn'), sortlbl=document.getElementById('sortlbl');
  function applySort(o){
    if(o!==(container.dataset.order||'new')){
      [].slice.call(container.querySelectorAll('.arcsec')).reverse().forEach(function(sec){
        var grid=sec.querySelector('.chgrid');
        [].slice.call(grid.children).reverse().forEach(function(c){grid.appendChild(c);});
        container.appendChild(sec);
      });
      container.dataset.order=o;
    }
    if(sortlbl) sortlbl.textContent=(o==='old'?'Oldest':'Newest');
  }
  var order='new'; try{order=localStorage.getItem('chsort')||'new';}catch(e){}
  applySort(order);
  if(sortbtn) sortbtn.addEventListener('click',function(){
    var o=(container.dataset.order==='old'?'new':'old');
    try{localStorage.setItem('chsort',o);}catch(e){}
    applySort(o);
  });

  // tìm chương theo số + tên; tự ẩn arc không còn kết quả
  var q=document.getElementById('chq'), chnr=document.getElementById('chnores');
  var qwrap=q?q.closest('.chsearch'):null;
  function applyChFilter(){
    var term=(q?q.value:'').trim().toLowerCase(), anyAll=false;
    container.querySelectorAll('.arcsec').forEach(function(sec){
      var any=false;
      sec.querySelectorAll('a.ch').forEach(function(a){
        var hit=!term || a.textContent.toLowerCase().indexOf(term)>=0
                || (a.dataset.num&&a.dataset.num.indexOf(term)>=0);
        a.style.display=hit?'':'none'; if(hit)any=true;
      });
      sec.style.display=any?'':'none'; if(any)anyAll=true;
    });
    if(chnr) chnr.classList.toggle('on', !!term && !anyAll);
    if(qwrap) qwrap.classList.toggle('has-val', !!(q&&q.value));
  }
  if(q) q.addEventListener('input', applyChFilter);
  function clearChq(){                            // bấm X hoặc Esc: xoá + lọc lại + giữ focus
    if(!q) return; q.value=''; applyChFilter(); q.focus();
  }
  if(qwrap){ var qx=qwrap.querySelector('.chclear'); if(qx) qx.addEventListener('click', clearChq); }
  if(q) q.addEventListener('keydown',function(e){
    if(e.key==='Escape' && q.value){ e.preventDefault(); clearChq(); }
  });

  // --- Prefetch trang CHƯƠNG vào cache SW -> bấm chương từ list vào gần như tức
  // thì (khỏi 2-3s render nguội). Việc render trước cũng WARM _dim_cache phía
  // server (quét PIL từng ảnh) nên lần mở thật khỏi phải quét lại. Không đón đầu
  // cả list (có thể hàng trăm chương) -> chỉ nạp theo Ý ĐỊNH (chạm/di chuột) +
  // các nút hay bấm (First/Latest/reading) lúc rảnh.
  function pf(urls){
    var c=navigator.serviceWorker&&navigator.serviceWorker.controller;
    if(!c||!urls.length) return;
    try{ c.postMessage({type:'prefetch',urls:urls}); }catch(e){}
  }
  document.addEventListener('pointerdown',function(e){
    var a=e.target.closest&&e.target.closest('a.ch,.cbtn');
    if(a&&a.href) pf([a.href]);
  },{passive:true});
  document.addEventListener('mouseover',function(e){        // hover PC = ý định
    var a=e.target.closest&&e.target.closest('a.ch,.cbtn');
    if(a&&a.href) pf([a.href]);
  },{passive:true});
  (function(){                                              // đón đầu nút chính
    var urls=[];
    document.querySelectorAll('.chapbtns .cbtn').forEach(function(a){
      if(a.href) urls.push(a.href); });
    if(!urls.length) return;
    var idle=window.requestIdleCallback||function(f){return setTimeout(f,800);};
    idle(function(){ pf(urls); });
  })();

  // --- Đồng bộ nút "reading" + làm-mờ-đã-đọc từ NGUỒN SỐNG. HTML server render
  // nằm trong cache SW (stale-while-revalidate) VÀ bfcache -> nút reading bake sẵn
  // có thể trỏ chương CŨ (đọc dở ch7, mở lại thấy ch6). purge-page không với tới
  // bfcache nên phải vá DOM tại chỗ, cùng khuôn syncCounts/syncBM.
  // Guest: đọc localStorage (đồng bộ, zero-flash) — server luôn render trung tính
  // cho guest nên đây cũng là nơi DUY NHẤT guest có nút reading. Đã đăng nhập:
  // hỏi /api/state rồi so ts với mirror localStorage — mirror thắng cả khi server
  // lỡ bị pagehide-race đè ngược (mở đọc tiếp sẽ tự ghi giá trị đúng lại server).
  function applyReading(p){
    if(!p||!p.rel) return;
    var target=null;
    container.querySelectorAll('a.ch').forEach(function(a){
      if(a.dataset.rel===p.rel) target=a; });
    if(!target) return;                       // chương đã bị xoá -> giữ nguyên nút
    var btn=document.querySelector('.chapbtns .cbtn.reading')
          ||document.querySelector('.chapbtns .cbtn.latest');
    if(!btn) return;
    var href=target.getAttribute('href');
    if(btn.classList.contains('reading')&&btn.getAttribute('href')===href) return;
    btn.className='cbtn reading';
    btn.setAttribute('href',href);
    // nhãn cùng công thức với server: data-num = fmt_num(chapter_num(name))
    btn.textContent=(target.dataset.num?('Chapter '+target.dataset.num):target.textContent)+' - reading';
    pf([btn.href]);                           // đón đầu HTML chương mới trỏ tới
  }
  function applyReadList(list){
    try{ var rs=new Set(list||[]);
      container.querySelectorAll('a.ch').forEach(function(a){
        if(rs.has(a.dataset.rel)) a.classList.add('read'); });
    }catch(e){}
  }
  function syncReading(){
    if(!LOGGEDIN){ applyReading(LS.getProg(sid)); return; }
    var mp=LS.mget(SDATA.uk,sid);
    fetch('/api/state',{credentials:'same-origin'})
      .then(function(r){return r.json();}).then(function(res){
        var sp=(res&&res.progress)?res.progress[sid]:null;
        applyReading(LS.newer(sp,mp));
        if(res&&res.read) applyReadList(res.read[sid]);
      }).catch(function(){ applyReading(mp); });  // offline -> mirror vẫn vá được
  }
  syncReading();                                              // load thường (kể cả bản SW cache)
  addEventListener('pageshow',function(e){ if(e.persisted) syncReading(); });  // bfcache
  document.addEventListener('visibilitychange',function(){
    if(document.visibilityState==='visible') syncReading();
  });
})();
"""

READER_JS = """
(function(){
  var top=document.getElementById('topbar'), bot=document.getElementById('botbar'),
      cue=document.getElementById('tapcue');
  // --- ẩn/hiện thanh công cụ ---
  // KHÔNG tự bật khi vào chương (kiểu Asura): bars ẩn sẵn (class 'hide' từ server),
  // hid=true; thay vào đó hiện pill "Tap to show controls" nhấp nháy nhẹ ở đáy.
  // Chạm vùng đọc -> bật bars + ẩn pill; chạm lại / cuộn -> ẩn bars + pill trở lại.
  var hid=true, barT=Date.now();
  // Pill chỉ là gợi ý MỘT LẦN: tự ẩn sau 3s, hoặc ngay khi cuộn / chạm. Đã ẩn thì
  // KHÔNG hiện lại trong phiên (người dùng đã biết "chạm để hiện điều khiển").
  var cueGone=false;
  function hideCue(){ if(cueGone||!cue) return; cueGone=true; cue.classList.add('off'); }
  setTimeout(hideCue,3000);
  function setBars(h){
    hid=h; barT=Date.now();
    top.classList.toggle('hide',h);
    bot.classList.toggle('hide',h);
    hideCue();                                 // mọi thao tác bar -> gỡ pill hẳn
  }
  // lưu vị trí đọc lên server theo tài khoản (guest thì bỏ qua). Gộp ghi tối đa
  // mỗi 2.5s, và ghi ngay khi rời/ẩn trang để không mất vị trí cuối.
  var netT=0, netTimer=null;
  function sendPos(){
    netT=Date.now();
    if(netTimer){clearTimeout(netTimer);netTimer=null;}
    var y=Math.round(scrollY);
    if(!LOGGEDIN){ try{LS.setProg(D.sid,D.rel,y,D.name);}catch(e){} return; }
    // đã đăng nhập: ghi server + MIRROR localStorage (đồng bộ, sống sót cả khi
    // request keepalive thất lạc); ts để trang khác / lần mở sau so độ tươi với
    // HTML bake sẵn từ cache SW cũ.
    try{LS.mset(D.uk,D.sid,D.rel,y,D.name);}catch(e){}
    try{
      fetch('/api/state',{method:'POST',keepalive:true,
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({op:'progress',sid:D.sid,rel:D.rel,y:y,ts:Date.now()})});
    }catch(e){}
  }
  function savePos(){
    var wait=2500-(Date.now()-netT);
    if(wait<=0) sendPos();
    else if(!netTimer) netTimer=setTimeout(sendPos,wait);
  }
  function savePosNow(){ sendPos(); }
  addEventListener('pagehide',sendPos);
  document.addEventListener('visibilitychange',function(){
    if(document.visibilityState==='hidden') sendPos();
  });
  // --- chế độ ghép trang đôi ---
  document.getElementById('jmode').addEventListener('click',function(){
    var on=document.body.classList.toggle('jmode');
    this.classList.toggle('on',on);
  });
  // Sau khi ghép/tách/đảo, HTML trang ĐÃ đổi (nút Join biến mất, spread hiện ra).
  // Nhưng SW điều hướng theo stale-while-revalidate -> reload thường sẽ trả BẢN
  // CACHE CŨ (nút Join cũ còn nguyên) -> user bấm lại -> "Invalid action". Vì vậy
  // xoá đúng trang này khỏi PAGE_CACHE (chờ SW xác nhận, có timeout dự phòng) rồi
  // mới reload -> luôn thấy trạng thái mới. Không có SW thì reload thẳng.
  function purgeAndReload(){
    var sw=navigator.serviceWorker;
    var url=location.href.split('#')[0];
    if(!(sw&&sw.controller)){ location.reload(); return; }
    var done=false;
    function go(){ if(done) return; done=true; location.reload(); }
    try{
      var ch=new MessageChannel();
      ch.port1.onmessage=go;
      sw.controller.postMessage({type:'purge-page',url:url},[ch.port2]);
      setTimeout(go,400);            // SW không trả lời -> vẫn reload
    }catch(e){ go(); }
  }
  document.addEventListener('click',function(e){
    var b=e.target.closest('button[data-act]');
    if(!b) return;
    b.disabled=true;
    fetch('/api/spread',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({sid:D.sid,rel:D.rel,action:b.dataset.act,
                           a:b.dataset.a,b:b.dataset.b||null})})
    .then(function(r){return r.json();})
    .then(function(res){
      if(res.ok){savePosNow();sessionStorage.setItem('jmode','1');purgeAndReload();}
      else{alert(res.error||'Action failed');b.disabled=false;}
    })
    .catch(function(){alert('Lost connection to server');b.disabled=false;});
  });
  // giữ nguyên chế độ ghép sau khi trang tự tải lại
  if(sessionStorage.getItem('jmode')==='1'){
    sessionStorage.removeItem('jmode');
    document.body.classList.add('jmode');
    document.getElementById('jmode').classList.add('on');
  }
  var marked=false;
  function markRead(){
    if(marked) return;
    var dh=document.documentElement.scrollHeight;
    if(scrollY+innerHeight<dh*0.85) return;
    marked=true;
    if(!LOGGEDIN){ try{LS.addRead(D.sid,D.rel);}catch(e){} return; }
    try{
      fetch('/api/state',{method:'POST',keepalive:true,
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({op:'read',sid:D.sid,rel:D.rel})});
    }catch(e){}
  }
  // cuộn: chỉ ẨN thanh công cụ nếu đang hiện (không bao giờ tự bật);
  // muốn hiện lại thì chạm vào trang. Chờ 600ms sau cú chạm/lúc mở trang
  // để khỏi ẩn oan vì cuộn khôi phục vị trí hay trớn cuộn trên iOS.
  addEventListener('scroll',function(){
    hideCue();                                 // bắt đầu cuộn -> ẩn pill ngay
    if(!hid && Date.now()-barT>600) setBars(true);
    savePos(); markRead();
  },{passive:true});
  // chạm/click vùng đọc để bật tắt thanh công cụ (trừ ô "chạm để tải lại")
  document.addEventListener('click',function(e){
    if(e.target.closest('a,button,select,option,header,footer,img.perr')) return;
    setBars(!hid);
  });
  // phím tắt PC
  addEventListener('keydown',function(e){
    var t=e.target, tn=(t&&t.tagName||'').toLowerCase();
    if(tn==='input'||tn==='textarea'||tn==='select'||(t&&t.isContentEditable)) return;
    if(e.key==='ArrowLeft'&&D.prev) location=D.prev;
    if(e.key==='ArrowRight'&&D.next) location=D.next;
  });
  document.getElementById('chsel').addEventListener('change',function(){location=this.value;});
  // --- chỉnh cỡ ảnh: stepper −/%/+ trong header (100% = 800px, min 1%, cap 300%) ---
  (function(){
    var dec=document.getElementById('zdec'), inc=document.getElementById('zinc'),
        val=document.getElementById('zval');
    if(!dec||!inc||!val) return;              // ẩn trên mobile hẹp -> bỏ qua
    var MINP=1, MAXP=300, cur=100, root=document.documentElement;
    function apply(p,save){
      p=Math.round(p);
      if(isNaN(p)) p=100;
      if(p<MINP) p=MINP; if(p>MAXP) p=MAXP;   // kẹp 1..300
      cur=p;
      root.style.setProperty('--imgw',(p/100*800)+'px');
      val.value=p+'%';
      if(save){try{localStorage.setItem('imgw',p);}catch(e){}}
    }
    dec.addEventListener('click',function(){apply(cur-10,true);});
    inc.addEventListener('click',function(){apply(cur+10,true);});
    val.addEventListener('focus',function(){this.select();});
    val.addEventListener('keydown',function(e){
      e.stopPropagation();                    // khỏi lọt vào phím tắt ‹/›
      if(e.key==='Enter'){e.preventDefault();this.blur();}
    });
    val.addEventListener('blur',function(){
      var n=parseInt(val.value,10);
      if(isNaN(n)){val.value=cur+'%';return;} // gõ bậy -> giữ nguyên
      apply(n,true);
    });
    var init=100; try{var s=parseInt(localStorage.getItem('imgw'),10); if(s>=MINP) init=s;}catch(e){}
    apply(init,false);                        // đồng bộ nhãn + var với giá trị đã lưu
  })();
  // khôi phục vị trí đọc dở. Guest: localStorage (luôn tươi). Đã đăng nhập: D.y
  // bake từ server có thể CŨ (HTML từ SW cache/prefetch) -> so ts với mirror
  // localStorage của chính tài khoản, bản mới hơn thắng. Tắt auto-restore của
  // trình duyệt (nó reset về 0 sau RAF sớm) và bám đích vài frame tới khi tới
  // nơi — chiều cao đã được aspect-ratio giữ sẵn.
  try{ var _gy=D.y;
    if(!LOGGEDIN){ var gp=LS.getProg(D.sid); _gy=(gp&&gp.rel===D.rel)?gp.y:0; }
    else{ var mp=LS.mget(D.uk,D.sid);
      if(mp&&mp.rel===D.rel&&(mp.ts||0)>(D.ts||0)) _gy=mp.y; }
    if(_gy>200){
      if('scrollRestoration' in history) history.scrollRestoration='manual';
      var ty=_gy, tries=0;
      (function hop(){ scrollTo(0,ty);
        if(++tries<12 && Math.abs(scrollY-ty)>2) requestAnimationFrame(hop); })();
    }
  }catch(e){}
  markRead(); // chương ngắn hiện trọn trong 1 màn hình
  // --- bộ nạp tuần tự: tải dần cả chương, ưu tiên ảnh từ vị trí đọc trở xuống.
  // Ảnh lỗi tự thử lại 3 lần (1s-3s-8s); hết lượt thì thành ô "chạm để tải
  // lại". Chạm 1 ô, có mạng lại, hay mở lại màn hình -> cả cụm ảnh lỗi hồi.
  (function(){
    var MAX=3, DELAYS=[1000,3000,8000];
    var pend=[], active=0;
    var all=[].slice.call(document.querySelectorAll('#strip img'));
    all.forEach(function(im){
      im._tries=0;
      if(im.dataset.src){          // ảnh để dành cho bộ nạp
        im._url=im.dataset.src;
        im.removeAttribute('data-src');
        pend.push(im);
      }else if(im.getAttribute('src')){ // 3 ảnh đầu: trình duyệt đã tự tải
        im._url=im.src;
        if(im.complete&&!im.naturalWidth){fail(im);}
        else if(!im.complete){
          im.onerror=function(){fail(im);};
          im.onload=function(){im.onload=im.onerror=null;};
        }
      }
    });
    function fail(im){
      im.onload=im.onerror=null;
      im.removeAttribute('src'); // bỏ src để không hiện icon ảnh vỡ của trình duyệt
      im.classList.remove('ldg');
      im._tries++;
      if(im._tries<=DELAYS.length){
        setTimeout(function(){pend.push(im);next();},DELAYS[im._tries-1]);
      }else{
        im.classList.add('perr');
      }
    }
    function load(im){
      active++;
      im.classList.add('ldg');
      im.onload=function(){
        active--;im._tries=0;
        im.classList.remove('ldg','perr');
        im.onload=im.onerror=null;
        next();
      };
      im.onerror=function(){active--;fail(im);next();};
      im.src=im._url;
    }
    function pick(){
      if(!pend.length) return null;
      var limit=scrollY-innerHeight, idx=0;
      for(var i=0;i<pend.length;i++){
        if(pend[i].getBoundingClientRect().top+scrollY>=limit){idx=i;break;}
      }
      return pend.splice(idx,1)[0];
    }
    function next(){
      while(active<MAX&&pend.length){
        var im=pick(); if(!im) return;
        load(im);
      }
    }
    // tín hiệu "mạng có lẽ đã hồi": reset và xếp lại mọi ảnh đã bỏ cuộc;
    // ảnh được chạm (prio) tải ngay, không xếp hàng
    function revive(prio){
      var any=false;
      all.forEach(function(im){
        if(im!==prio&&im.classList.contains('perr')){
          im._tries=0;im.classList.remove('perr');
          pend.push(im);any=true;
        }
      });
      if(prio){prio._tries=0;prio.classList.remove('perr');load(prio);}
      if(any)next();
    }
    document.addEventListener('click',function(e){
      var im=e.target.closest('img.perr');
      if(im)revive(im);
    });
    addEventListener('online',function(){revive(null);});
    document.addEventListener('visibilitychange',function(){
      if(document.visibilityState==='visible')revive(null);
    });
    next();
  })();
  // --- Đồng bộ danh sách ảnh từ nguồn SỐNG (/api/pages, no-store). HTML này có thể
  // là bản SW cache / bfcache CŨ trỏ ?v= cũ (02/09: repair thay ảnh tráo ô nhưng
  // reader vẫn hiện ảnh cũ dù mở lại nhiều lần). So version với D.pv; lệch thì vá
  // TẠI CHỖ: ảnh chờ nạp -> đổi im._url (bộ nạp đọc lúc load); ảnh đã/đang tải ->
  // gán src mới (tải lại ngay); cập nhật aspect-ratio (đơn + spread). Không reload.
  function syncPages(){
    if(!D.sid||!D.rel) return;
    var api='/api/pages/'+encodeURIComponent(D.sid)+'/'
            +D.rel.split('/').map(encodeURIComponent).join('/');
    fetch(api,{credentials:'same-origin'})
      .then(function(r){return r.ok?r.json():null;})
      .then(function(res){
        if(!res||!res.version||!Array.isArray(res.pages)||res.version===D.pv) return;
        var byName={}, dims={};
        [].slice.call(document.querySelectorAll('#strip img[data-f]'))
          .forEach(function(im){byName[im.dataset.f]=im;});
        res.pages.forEach(function(p){
          if(p.w&&p.h) dims[p.n]=[p.w,p.h];
          var im=byName[p.n]; if(!im||!p.url) return;
          var cur=im._url||im.getAttribute('src')||'';
          if(cur===p.url) return;
          im._url=p.url;
          if(p.w&&p.h&&!im.closest('.spread')) im.style.aspectRatio=p.w+'/'+p.h;
          if(im.getAttribute('src')||im.classList.contains('perr')){
            im.classList.remove('perr');
            im.src=p.url;                       // đã/đang tải hoặc từng lỗi -> tải bản mới ngay
          }
        });
        [].slice.call(document.querySelectorAll('#strip .spread')).forEach(function(sp){
          var ims=sp.querySelectorAll('img[data-f]'); if(ims.length!==2) return;
          var a=dims[ims[0].dataset.f], b=dims[ims[1].dataset.f]; if(!a||!b) return;
          var rl=a[0]/a[1], rr=b[0]/b[1];
          sp.style.aspectRatio=(rl+rr).toFixed(4);
          ims[0].style.width=(rl/(rl+rr)*100).toFixed(3)+'%';
          ims[1].style.width=(rr/(rl+rr)*100).toFixed(3)+'%';
        });
        D.pv=res.version;
      }).catch(function(){});
  }
  addEventListener('pageshow',function(){ syncPages(); });   // load thường + bfcache
  document.addEventListener('visibilitychange',function(){
    if(document.visibilityState==='visible') syncPages();
  });
  // --- Prefetch trang chương KẾ (và trước) vào cache SW khi rảnh -> bấm Next/Prev
  // gần như tức thì (SW trả HTML từ cache, khỏi round-trip qua tunnel). Việc render
  // trước cũng WARM luôn cache kích thước ảnh (_dim_cache) phía server -> hết cảnh
  // mở nguội quét PIL từng ảnh. Chỉ nạp HTML (2 doc nhẹ), KHÔNG kéo ảnh chương.
  (function(){
    if(!('serviceWorker' in navigator)) return;
    var urls=[]; if(D.next) urls.push(D.next); if(D.prev) urls.push(D.prev);
    if(!urls.length) return;
    var idle=window.requestIdleCallback||function(f){return setTimeout(f,800);};
    function send(){ var c=navigator.serviceWorker.controller;
      if(c){ try{ c.postMessage({type:'prefetch',urls:urls}); }catch(e){} } }
    idle(function(){
      if(navigator.serviceWorker.controller) send();
      else navigator.serviceWorker.ready.then(function(){ setTimeout(send,50); });
    });
  })();
})();
"""


# ---------------------------------------------------------------------------
# Tài nguyên tĩnh (CSS/JS) phục vụ ở URL versioned + cache vĩnh viễn. Trước đây
# nhúng inline vào document no-store -> tải lại toàn bộ mỗi lần mở. Tách ra ->
# trình duyệt VÀ Service Worker cache được, document co lại còn phần động.
# ---------------------------------------------------------------------------

def _mkasset(text, ctype):
    data = text.encode("utf-8")
    return {"data": data, "ctype": ctype,
            "ver": hashlib.sha1(data).hexdigest()[:10]}


_JS_CT = "application/javascript; charset=utf-8"
STATIC_ASSETS = {
    "app.css":   _mkasset(CSS, "text/css; charset=utf-8"),
    "base.js":   _mkasset(PRESS_JS + "\n" + TOTOP_JS, _JS_CT),
    "ls.js":     _mkasset(LS_JS, _JS_CT),
    "acct.js":   _mkasset(ACCT_JS, _JS_CT),
    "home.js":   _mkasset(HOME_JS, _JS_CT),
    "admin.js":  _mkasset(ADMIN_JS, _JS_CT),
    "series.js": _mkasset(SERIES_JS, _JS_CT),
    "reader.js": _mkasset(READER_JS, _JS_CT),
}


def _build_brand_asset():
    """Thu nhỏ brand.png (gốc ~469KB, chỉ hiện ở height 34px) về ~3x cỡ hiển thị
    -> WebP vài KB. GIỮ nguyên hình, chỉ giảm dung lượng + có alpha. None nếu
    thiếu PIL/file (khi đó header quay về route /brand phục vụ file gốc)."""
    if Image is None:
        return None
    try:
        with Image.open(os.path.join(META_DIR, "brand.png")) as im:
            im = im.convert("RGBA")
            th = 120                       # 34px hiển thị × ~3.5 cho màn retina
            if im.height > th:
                im = im.resize((max(1, round(im.width * th / im.height)), th))
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=88, method=6)
            return buf.getvalue()
    except Exception:
        return None


_brand_data = _build_brand_asset()
if _brand_data:
    STATIC_ASSETS["brand.webp"] = {"data": _brand_data, "ctype": "image/webp",
                                   "ver": hashlib.sha1(_brand_data).hexdigest()[:10]}


def static_url(name):
    return f"/static/{name}?v={STATIC_ASSETS[name]['ver']}"


def static_tag(name):
    """Thẻ tải tài nguyên tĩnh đã versioned (<link> cho css, <script> cho js)."""
    if name.endswith(".css"):
        return f'<link rel="stylesheet" href="{static_url(name)}">'
    return f'<script src="{static_url(name)}"></script>'


def brand_src():
    """URL logo header: bản WebP nhẹ đã versioned nếu dựng được, không thì /brand gốc."""
    return static_url("brand.webp") if "brand.webp" in STATIC_ASSETS else "/brand"


# ---------------------------------------------------------------------------
# Service Worker: cache-first cho tài nguyên tĩnh + ảnh (bìa/trang), stale-
# while-revalidate cho trang HTML. Trị: (a) màn trắng khi mở nguội - shell trả
# từ cache tức thì không chờ mạng; (b) bìa nháy đen khi reload - ảnh lấy từ
# cache, không tải lại qua tunnel.
# ---------------------------------------------------------------------------

# Danh sách precache lúc cài SW (shell tối thiểu để trang chủ hiện được ngay).
_SW_PRECACHE = ([static_url(n) for n in STATIC_ASSETS]
                + ["/manifest.webmanifest", "/logo", "/icon-180.png"])

# SW_VERSION tính SAU template: hash danh sách asset + CHÍNH mã SW (xem cuối _SW_TEMPLATE).
# Trước đây chỉ hash asset -> sửa LOGIC SW mà không đổi asset thì ETag /sw.js giữ nguyên
# -> trình duyệt nhận 304 -> giữ SW cũ mãi (dính khi thêm e.waitUntil 02/09).

_SW_TEMPLATE = ("""
const VER = '__VER__';
const STATIC_CACHE = 'toony-static-' + VER;
const PAGE_CACHE   = 'toony-pages-' + VER;
const IMG_CACHE    = 'toony-img';           // ảnh: URL đã versioned/độc nhất
const PRECACHE = __PRECACHE__;

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(STATIC_CACHE).then((c) => c.addAll(PRECACHE)));
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => {
      if (k === STATIC_CACHE || k === PAGE_CACHE || k === IMG_CACHE) return null;
      return caches.delete(k);   // dọn phiên bản shell/pages cũ
    }));
    await self.clients.claim();
  })());
});

// Hàng đợi prefetch trang series (giới hạn luồng để không ngốn băng thông /
// tranh kết nối với ảnh đang tải). Trang gửi URL qua postMessage.
let pfQ = [], pfActive = 0, pfWaiters = [];
const PF_MAX = 2;
// Báo "hàng đợi đã cạn" cho các promise đang chờ (để e.waitUntil giữ SW sống tới lúc đó).
function pfSettle() {
  if (pfQ.length || pfActive) return;
  const w = pfWaiters; pfWaiters = [];
  w.forEach((r) => r());
}
function pumpPrefetch() {
  while (pfActive < PF_MAX && pfQ.length) {
    const url = pfQ.shift();
    pfActive++;
    caches.open(PAGE_CACHE).then(async (cache) => {
      if (await cache.match(url)) return;            // đã có -> bỏ qua
      try {
        const res = await fetch(url, {credentials: 'same-origin'});
        if (res && res.ok) await cache.put(url, res.clone());
      } catch (e) {}
    }).finally(() => { pfActive--; pumpPrefetch(); pfSettle(); });
  }
  // Trả promise resolve khi cạn hàng đợi -> message handler bọc e.waitUntil (iOS tắt
  // SW rất sớm; không giữ sống thì prefetch bị cắt giữa chừng).
  return new Promise((r) => { pfWaiters.push(r); pfSettle(); });
}

self.addEventListener('message', (e) => {
  const d = e.data || {};
  // Trang báo "vừa login/logout" -> xoá cache HTML để lần mở sau không hiện
  // nhầm trạng thái đăng nhập cũ.
  if (d.type === 'purge-pages') {
    pfQ = [];                                         // bỏ prefetch cũ (khác user)
    e.waitUntil(caches.delete(PAGE_CACHE).then(() => {
      if (e.ports && e.ports[0]) e.ports[0].postMessage({ok: true});
    }));
  } else if (d.type === 'purge-page' && d.url) {
    // Bookmark 1 truyện đổi, HOẶC vừa ghép/tách/đảo trang đôi -> HTML server đã
    // cache của ĐÚNG trang đó thành cũ (nút bookmark / nút Join render sai). Xoá
    // riêng key đó để lần vào sau tải bản tươi; các trang khác giữ nguyên tốc độ
    // prefetch/SWR. Có port -> xác nhận để trang chờ xoá xong mới reload (khỏi
    // đua với chính lần reload đó).
    e.waitUntil(caches.open(PAGE_CACHE).then((c) => c.delete(d.url, {ignoreSearch: true}))
      .then(() => { if (e.ports && e.ports[0]) e.ports[0].postMessage({ok: true}); }));
  } else if (d.type === 'prefetch' && Array.isArray(d.urls)) {
    for (const u of d.urls) if (pfQ.indexOf(u) < 0) pfQ.push(u);
    e.waitUntil(pumpPrefetch());
  }
});

function isImg(url) {
  return url.pathname.startsWith('/cover/') || url.pathname.startsWith('/img/');
}
function isStatic(url) {
  return url.pathname.startsWith('/static/')
      || url.pathname === '/manifest.webmanifest'
      || url.pathname === '/logo' || url.pathname === '/brand'
      || /^\\/(icon|og)-[\\w-]+\\.(png|jpg)$/.test(url.pathname);
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;                 // POST /api/* -> mạng thẳng
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Ảnh + tài nguyên tĩnh: cache-first (URL đã đổi khi nội dung đổi).
  if (isImg(url) || isStatic(url)) {
    const cacheName = isImg(url) ? IMG_CACHE : STATIC_CACHE;
    e.respondWith((async () => {
      const cache = await caches.open(cacheName);
      const hit = await cache.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      // waitUntil: giữ SW sống tới khi put xong (iOS tắt SW ngay sau respondWith).
      if (res && res.ok) e.waitUntil(cache.put(req, res.clone()).catch(() => {}));
      return res;
    })());
    return;
  }

  // Điều hướng HTML: stale-while-revalidate -> first paint từ cache tức thì,
  // cập nhật ngầm cho lần mở sau. Không có cache -> mạng.
  if (req.mode === 'navigate') {
    e.respondWith((async () => {
      const cache = await caches.open(PAGE_CACHE);
      const hit = await cache.match(req);
      if (hit) {
        // Có bản cache -> trả ngay, revalidate NGẦM (nuốt lỗi mạng, khỏi vỡ điều hướng).
        // PHẢI bọc e.waitUntil: không có nó, iOS Safari tắt SW ngay khi respondWith
        // xong -> fetch/put bị hủy -> PAGE_CACHE KHÔNG BAO GIỜ cập nhật (02/09: mở lại
        // cả chục lần vẫn HTML cũ -> ảnh tráo ô cũ). Desktop Chrome giữ SW sống thêm
        // vài giây nên không lộ.
        // Revalidate bằng Request MỚI theo URL, KHÔNG tái dùng navigation Request `req`:
        // fetch(req) (mode navigate / redirect manual / signal gắn điều hướng) rớt
        // "TypeError: Failed to fetch" lúc được lúc không (đo bằng diagnostic 02/09) ->
        // .catch nuốt -> cache không đổi. cache:'no-store' để khỏi dính HTTP cache/304.
        e.waitUntil(
          fetch(req.url, {credentials: 'same-origin', cache: 'no-store'})
            .then((res) => { if (res && res.ok) return cache.put(req.url, res.clone()); })
            .catch(() => {}));
        return hit;
      }
      // KHÔNG có cache: phải ra mạng. Mạng lỗi (vd link tunnel đã đổi/chết) mà TRẢ VỀ
      // undefined thì respondWith báo "Returned response is null" (Safari không mở nổi
      // trang). Vì vậy LUÔN trả 1 Response: thành công -> res; lỗi -> trang báo tử tế.
      try {
        const res = await fetch(req);
        if (res && res.ok) e.waitUntil(cache.put(req, res.clone()).catch(() => {}));
        return res;
      } catch (err) {
        return new Response(
          '<!doctype html><meta charset=utf-8>'
          + '<meta name=viewport content="width=device-width,initial-scale=1">'
          + '<style>body{background:#111;color:#ccc;margin:0;min-height:100vh;display:flex;'
          + 'flex-direction:column;align-items:center;justify-content:center;text-align:center;'
          + 'font:16px/1.5 system-ui,-apple-system,sans-serif;padding:28px;gap:8px}'
          + 'b{color:#fff;font-size:19px}a{color:#a78bfa}</style>'
          + '<body><b>Không kết nối được máy chủ</b>'
          + '<div>Link chia sẻ có thể đã đổi hoặc server đang tắt.<br>'
          + 'Hãy lấy link mới rồi mở lại.</div>'
          + '<div><a href="/">Thử lại trang chủ</a></div></body>',
          {status: 503, headers: {'Content-Type': 'text/html; charset=utf-8'}});
      }
    })());
    return;
  }
});
""")

# Đổi khi logic SW đổi HOẶC bất kỳ asset nào đổi -> tên cache mới, SW mới dọn cache cũ,
# ETag /sw.js đổi -> mọi client cập nhật (không còn phải tự bump tiền tố).
SW_VERSION = "v3-" + hashlib.sha1(
    ("|".join(_SW_PRECACHE) + "\n" + _SW_TEMPLATE).encode("utf-8")).hexdigest()[:10]
SW_JS = (_SW_TEMPLATE.replace("__VER__", SW_VERSION)
         .replace("__PRECACHE__", json.dumps(_SW_PRECACHE)))


# Đăng ký SW (nhúng inline vào mọi trang, rất nhẹ). Chạy sau 'load' để không
# tranh băng thông với nội dung trang lần đầu.
SW_REGISTER = ("<script>if('serviceWorker' in navigator){"
               "addEventListener('load',function(){"
               "navigator.serviceWorker.register('/sw.js').catch(function(){});"
               "});}</script>")


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # im lặng, đỡ nhiễu console
        pass

    def _inject_og(self, body):
        """Chèn thẻ Open Graph/Twitter vào <head> với URL ảnh TUYỆT ĐỐI.
        Facebook/Messenger bắt buộc og:image là URL đầy đủ; host lấy từ request
        nên tự đúng dù chạy localhost, LAN hay qua Cloudflare tunnel."""
        if "</head>" not in body or "og:image" in body:
            return body
        host = self.headers.get("Host") or ""
        proto = self.headers.get("X-Forwarded-Proto")
        if not proto:
            local = ("localhost" in host or host.startswith("127.")
                     or host.startswith("192.168.") or host.startswith("10."))
            proto = "http" if local else "https"
        base = f"{proto}://{host}" if host else ""
        m = re.search(r"<title>(.*?)</title>", body, re.S)
        title = m.group(1) if m else "Toony Reader"   # đã được html.escape ở page()
        img = f"{base}/og-image-wide.jpg"   # 1200x630 (1.91:1) — tỉ lệ Meta ưa nhất
        url = f"{base}{self.path}"
        desc = "Kho truyện tranh — đọc mượt, không quảng cáo."
        tags = (
            '<meta property="og:type" content="website">'
            '<meta property="og:site_name" content="Toony Reader">'
            f'<meta property="og:title" content="{title}">'
            f'<meta property="og:description" content="{desc}">'
            f'<meta property="og:image" content="{img}">'
            f'<meta property="og:image:secure_url" content="{img}">'
            '<meta property="og:image:type" content="image/jpeg">'
            '<meta property="og:image:width" content="1200">'
            '<meta property="og:image:height" content="630">'
            '<meta property="og:image:alt" content="Toony Reader">'
            f'<meta property="og:url" content="{url}">'
            '<meta name="twitter:card" content="summary_large_image">'
            f'<meta name="twitter:title" content="{title}">'
            f'<meta name="twitter:description" content="{desc}">'
            f'<meta name="twitter:image" content="{img}">'
        )
        return body.replace("</head>", tags + "</head>", 1)

    def send_page(self, body, code=200):
        body = self._inject_og(body)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        # no-cache (KHÔNG phải no-store): vẫn buộc revalidate mỗi lần load nên
        # không hiện nhầm trạng thái đăng nhập cũ, NHƯNG không chặn back-forward
        # cache. no-store làm iOS Safari phải dựng lại trang khi back -> vuốt back
        # (animation tương tác) lộ frame dựng lại thành "nháy". no-cache giữ được
        # bfcache -> back tức thì, hết nháy.
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_notfound(self):
        self.send_page(page("Not found", '<div class="wrap"><h1>404 — Not found</h1>'
                            '<a class="navbtn" href="/">Back to Library</a></div>'), 404)

    def send_file_bytes(self, ctype, data, etag=None):
        # Hỗ trợ HTTP Range (206) và HEAD: một số proxy ảnh khó tính của Meta
        # (bong bóng link trong chat Messenger) HEAD hoặc xin từng phần trước khi
        # nhận; thiếu là chúng bỏ, ra ô ảnh trắng. Client dễ tính vẫn GET như cũ.
        total = len(data)
        start, end, status = 0, total - 1, 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            try:
                s, _, e = rng[6:].partition("-")
                if s == "":                       # bytes=-N: N byte cuối
                    start = max(0, total - int(e))
                else:
                    start = int(s)
                    end = int(e) if e else total - 1
                end = min(end, total - 1)
                if 0 <= start <= end:
                    status = 206
                else:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{total}")
                    self.end_headers()
                    return
            except ValueError:
                start, end, status = 0, total - 1, 200
        body = data[start:end + 1] if status == 206 else data
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(body)))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
        self.send_header("Cache-Control", "public, max-age=604800")
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def safe_join(self, base, parts):
        """Ghép đường dẫn từ URL, chặn mọi kiểu thoát ra ngoài folder truyện."""
        for p in parts:
            if not p or p in (".", "..") or "/" in p or "\\" in p or ":" in p:
                return None
        full = os.path.abspath(os.path.join(base, *parts))
        if not full.startswith(os.path.abspath(base) + os.sep):
            return None
        return full

    def send_json(self, obj, code=200, set_cookie=None):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def current_user(self):
        """Tài khoản theo cookie uid, hoặc None (guest)."""
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "uid":
                return user_by_id(unquote(v))
        return None

    def do_POST(self):
        try:
            path = urlsplit(self.path).path
            if path == "/api/logout":
                return self.send_json({"ok": True},
                                      set_cookie="uid=; Path=/; Max-Age=0; SameSite=Lax")
            if path not in ("/api/spread", "/api/state", "/api/login", "/api/admin"):
                return self.send_json({"ok": False, "error": "Not found"}, 404)
            length = int(self.headers.get("Content-Length") or 0)
            # /api/admin có thể tải ảnh bìa (base64) -> cho phép lớn hơn nhiều
            limit = 12_000_000 if path == "/api/admin" else 200000
            if not 0 < length <= limit:
                return self.send_json({"ok": False, "error": "Invalid content"}, 400)
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/api/login":
                user, err = get_or_create_user(data.get("name"))
                if err:
                    return self.send_json({"ok": False, "error": err}, 400)
                cookie = f"uid={quote(user['id'])}; Path=/; Max-Age=31536000; SameSite=Lax"
                return self.send_json({"ok": True, "display": user["display"]}, set_cookie=cookie)
            if path == "/api/state":
                user = self.current_user()
                if not user:
                    return self.send_json({"ok": False, "error": "Not logged in"}, 401)
                update_user_data(user["id"], data)
                return self.send_json({"ok": True})
            if path == "/api/admin":
                if not is_admin(self.current_user()):
                    return self.send_json({"ok": False, "error": "Not admin"}, 403)
                op = data.get("op")
                if op == "prune":
                    removed = prune_series_meta()
                    bust_library_cache()
                    return self.send_json({"ok": True, "removed": len(removed)})
                if op == "refresh":
                    bust_library_cache()
                    return self.send_json({"ok": True})
                sid = data.get("sid")
                # status/title/cover trả thêm giá trị ĐÃ RESOLVE để client cập nhật TẠI CHỖ
                # (khỏi reload -> giữ nguyên ô search + vị trí cuộn khi sửa nhiều truyện).
                if op == "status":
                    if set_series_status(sid, data.get("status")):
                        st = series_status(sid)
                        return self.send_json({"ok": True, "status": st,
                                               "label": STATUS_LABELS[st]})
                    return self.send_json({"ok": False}, 400)
                if op == "title":
                    if set_series_title(sid, data.get("title") or ""):
                        s2 = get_library().get(sid)   # tên hiển thị đã chuẩn hoá / về-folder
                        return self.send_json({"ok": True, "title": s2["title"] if s2 else ""})
                    return self.send_json({"ok": False}, 400)
                if op == "cover":
                    s = get_library().get(sid)
                    raw = None
                    b64 = data.get("data") or ""
                    if isinstance(b64, str):
                        b64 = b64.split(",", 1)[-1]   # bỏ tiền tố data:image/...;base64,
                        try:
                            raw = base64.b64decode(b64, validate=True)
                        except (binascii.Error, ValueError):
                            raw = None
                    if s and raw and save_cover(s, raw):
                        bust_library_cache()
                        s2 = get_library().get(sid) or s   # mtime bìa đổi -> URL ?v= mới
                        return self.send_json({"ok": True, "cover": cover_url(s2)})
                    return self.send_json({"ok": False}, 400)
                # order: đảo thứ tự nhiều card -> client reload (giữ search qua sessionStorage)
                if op == "order":
                    ok = reorder_series(sid, data.get("move"))
                else:
                    ok = False
                return self.send_json({"ok": bool(ok)}, 200 if ok else 400)
            sid, rel = data.get("sid"), data.get("rel")
            action, a, b = data.get("action"), data.get("a"), data.get("b")
            s = get_library().get(sid)
            if not s or rel not in s["byrel"] or not a:
                return self.send_json({"ok": False, "error": "Chapter not found"}, 404)
            files = set(list_images(os.path.join(s["path"], *rel.split("/"))))
            if a not in files or (action == "join" and b not in files):
                return self.send_json({"ok": False, "error": "Page not found"}, 404)
            if not modify_spreads(sid, rel, action, a, b):
                return self.send_json({"ok": False, "error": "Invalid action"}, 400)
            return self.send_json({"ok": True})
        except (ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception:
            try:
                self.send_json({"ok": False, "error": "Server error"}, 500)
            except Exception:
                pass

    def do_HEAD(self):
        # Chạy đúng định tuyến của GET; send_page/send_file_bytes tự bỏ phần thân
        # khi command == "HEAD", chỉ trả header (đúng chuẩn HTTP HEAD).
        self.do_GET()

    def do_GET(self):
        try:
            self.route()
        except (ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception:
            try:
                self.send_page(page("Error", '<div class="wrap"><h1>500 — Server error</h1>'
                                    '<a class="navbtn" href="/">Back to Library</a></div>'), 500)
            except Exception:
                pass

    def route(self):
        path = urlsplit(self.path).path
        segs = [unquote(p) for p in path.split("/") if p]
        lib = get_library()
        user = self.current_user()

        if not segs:
            return self.send_page(html_home(lib, user))

        if segs == ["api", "state"]:
            d = user_data(user["id"]) if user else _default_udata()
            return self.send_json({"bookmarks": d["bookmarks"],
                                   "progress": d["progress"], "read": d["read"]})

        # Dữ liệu phái sinh theo-truyện (số chương / trạng thái / bìa) để client tự
        # vá tại chỗ khi hiển thị (pageshow/visibilitychange) — xuyên qua bfcache +
        # SW cache mà không phải tải lại cả trang. 'version' = chữ ký của CHÍNH payload
        # nên đổi đúng khi có field đổi (bất kể do thêm/xoá chương hay admin sửa meta).
        # Danh sách ảnh SỐNG của 1 chương (no-store) — trang đọc gọi lúc pageshow/
        # visibilitychange, so 'version' với D.pv rồi vá src/aspect-ratio tại chỗ.
        if len(segs) >= 4 and segs[0] == "api" and segs[1] == "pages":
            s = lib.get(segs[2])
            rel = "/".join(segs[3:])
            if not s or rel not in s["byrel"]:
                return self.send_json({"error": "not found"}, 404)
            return self.send_json(chapter_pages(s, rel))

        if segs == ["api", "library-meta"]:
            meta = {}
            for sid, s in lib.items():
                st = series_status(sid)
                meta[sid] = {"total": s["total"], "status": st,
                             "label": STATUS_LABELS[st], "cover": cover_url(s)}
            ver = hashlib.sha1(json.dumps(meta, sort_keys=True, ensure_ascii=False)
                               .encode("utf-8")).hexdigest()[:12]
            return self.send_json({"version": ver, "series": meta})

        if segs[0] == "series" and len(segs) == 2:
            s = lib.get(segs[1])
            return self.send_page(html_series(s, user)) if s else self.send_notfound()

        if segs[0] == "read" and len(segs) >= 3:
            s = lib.get(segs[1])
            rel = "/".join(segs[2:])
            if not s or rel not in s["byrel"]:
                return self.send_notfound()
            return self.send_page(html_reader(s, rel, user))

        if segs[0] == "img" and len(segs) >= 4:
            s = lib.get(segs[1])
            if not s:
                return self.send_notfound()
            full = self.safe_join(s["path"], segs[2:])
            if not full or not os.path.isfile(full):
                return self.send_notfound()
            ext = os.path.splitext(full)[1].lower()
            if ext not in IMG_EXTS:
                return self.send_notfound()
            st = os.stat(full)
            etag = f'"{st.st_mtime_ns}-{st.st_size}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            with open(full, "rb") as f:
                data = f.read()
            return self.send_file_bytes(MIME.get(ext, "application/octet-stream"), data, etag)

        if segs[0] == "static" and len(segs) == 2:
            a = STATIC_ASSETS.get(segs[1])
            if not a:
                return self.send_notfound()
            etag = f'"{a["ver"]}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            data = a["data"]
            self.send_response(200)
            self.send_header("Content-Type", a["ctype"])
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
            self.send_header("ETag", etag)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
            return

        if segs == ["sw.js"]:
            data = SW_JS.encode("utf-8")
            etag = f'"{SW_VERSION}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            # no-cache: trình duyệt luôn kiểm lại sw.js -> đổi SW là cập nhật ngay
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Service-Worker-Allowed", "/")
            self.send_header("ETag", etag)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
            return

        if segs[0] == "manifest.webmanifest" and len(segs) == 1:
            data = MANIFEST_JSON.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type",
                             "application/manifest+json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            # no-cache (KHÔNG no-store): SW cache-first vẫn giữ được manifest cho
            # offline launch; bỏ mâu thuẫn "no-store nhưng SW lại cache".
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)
            return

        if len(segs) == 1 and segs[0] in ICON_FILES:
            full = os.path.join(META_DIR, segs[0])
            if not os.path.isfile(full):
                return self.send_notfound()
            st = os.stat(full)
            etag = f'"{st.st_mtime_ns}-{st.st_size}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            with open(full, "rb") as f:
                data = f.read()
            ctype = MIME.get(os.path.splitext(segs[0])[1].lower(), "image/png")
            return self.send_file_bytes(ctype, data, etag)

        if segs[0] in ("logo", "brand") and len(segs) == 1:
            name, ctype = (("reader-manga.ico", "image/x-icon") if segs[0] == "logo"
                           else ("brand.png", "image/png"))
            full = os.path.join(META_DIR, name)
            if not os.path.isfile(full):
                return self.send_notfound()
            st = os.stat(full)
            etag = f'"{st.st_mtime_ns}-{st.st_size}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            with open(full, "rb") as f:
                data = f.read()
            return self.send_file_bytes(ctype, data, etag)

        if segs[0] == "cover" and len(segs) == 2:
            s = lib.get(segs[1])
            cov = cover_jpeg(s) if s else None
            if not cov:
                return self.send_notfound()
            # ETag để reload có thể trả 304 thay vì tải lại nguyên ảnh bìa (trước
            # đây thiếu -> mỗi lần reload là 200 full -> bìa nháy đen). Khóa theo
            # mtime nguồn bìa + kích thước JPEG đã encode.
            etag = f'"{cover_ver(s)}-{len(cov[1])}"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "public, max-age=604800")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            return self.send_file_bytes(cov[0], cov[1], etag)

        return self.send_notfound()


class QuietServer(ThreadingHTTPServer):
    """Không in traceback khi client ngắt kết nối giữa chừng (đóng tab,
    chuyển trang, mất sóng...) - chuyện thường ngày, không phải lỗi."""

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                            BrokenPipeError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def lan_ip():
    try:
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sk.connect(("8.8.8.8", 80))
        ip = sk.getsockname()[0]
        sk.close()
        return ip
    except OSError:
        return None


def reader_heartbeat_loop(port):
    """Dead-man's-switch RIÊNG cho reader, ĐỘC LẬP với heartbeat của supervisor.

    Mỗi READER_HB_EVERY giây: TỰ gọi http://127.0.0.1:<port>/ (READINESS — reader còn
    PHỤC VỤ được không, bắt cả ca 'treo mà chưa chết' mà run_reader của supervisor không
    thấy) rồi mới ping `reader_heartbeat_url` RA healthchecks.io. Tự-kiểm hỏng → KHÔNG
    ping → dịch vụ ngoài thấy im lặng → báo 'reader down' (đúng ý đồ). Vì đây là check
    RIÊNG, nhìn cặp tín hiệu (supervisor-check vs reader-check) biết CÁI NÀO chết:
    supervisor chết mà reader-check còn xanh = reader mồ côi vẫn phục vụ (đúng ca sự cố).
    Đọc URL từ notify-config.json MỖI vòng → điền URL xong không cần restart reader.
    Trống URL = tắt heartbeat này."""
    self_url = f"http://127.0.0.1:{port}/"
    last_ok = None
    while True:
        try:
            cfg = json.loads(open(NOTIFY_CONFIG_FILE, encoding="utf-8").read())
        except Exception:
            cfg = {}
        url = (cfg.get("reader_heartbeat_url") or "").strip()
        if url:
            ok = False
            try:
                with urllib.request.urlopen(self_url, timeout=READER_HB_TIMEOUT) as r:
                    if 200 <= r.status < 300:
                        r.read(64)   # chạm nội dung → chắc chắn reader phục vụ được, không chỉ mở cổng
                        req = urllib.request.Request(
                            url, headers={"User-Agent": "toony-reader-hb"})
                        with urllib.request.urlopen(req, timeout=READER_HB_TIMEOUT) as hr:
                            ok = 200 <= hr.status < 300
            except Exception:
                ok = False
            if ok != last_ok:   # chỉ in khi ĐỔI trạng thái → khỏi phình log mỗi 5'
                print("[reader-heartbeat] " + ("OK." if ok else
                      "ping THẤT BẠI (reader treo / mất mạng?)"), flush=True)
                last_ok = ok
        time.sleep(READER_HB_EVERY)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Web reader kiểu Asura cho truyện local")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    lib = get_library()
    print("=" * 52)
    print("  Web reader — thư viện truyện")
    print("=" * 52)
    if not lib:
        print("Không tìm thấy truyện nào! Kiểm tra lại folder.")
    for s in lib.values():
        n_arcs = sum(1 for a in s["arcs"] if a["name"])
        extra = f" ({n_arcs} arc)" if n_arcs > 1 else ""
        print(f"  - {s['title']:<38} {s['total']:>4} chương{extra}")
    if Image is None:
        print("  (!) Chưa có thư viện Pillow — vẫn đọc được, nhưng nên: pip install Pillow")
    print()
    print("Đọc tại:")
    print(f"  - Trên PC này  : http://localhost:{args.port}")
    ip = lan_ip()
    if ip:
        print(f"  - Điện thoại   : http://{ip}:{args.port}   (cùng Wi-Fi với PC)")
    print()
    print("Lần đầu chạy nếu Windows Firewall hỏi -> chọn Allow access.")
    print("Dừng server: Ctrl+C")
    print("=" * 52)
    sys.stdout.flush()

    try:
        srv = QuietServer(("0.0.0.0", args.port), Handler)
    except OSError as e:
        print(f"Không mở được cổng {args.port} ({e}). Thử: python reader_server.py --port 8081")
        sys.exit(1)
    # Heartbeat reader RA healthchecks.io (độc lập supervisor) — trống url trong config = tắt.
    threading.Thread(target=reader_heartbeat_loop, args=(args.port,), daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng server.")


if __name__ == "__main__":
    main()
