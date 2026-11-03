#!/usr/bin/env python3
"""Làm sạch ảnh truyện scan trong thư viện: tách trang đôi, dọn gáy, làm trắng nền, dọn vùng xám, làm nét.

Lõi xử lý chuyển từ chặng (a) của bộ dịch Rockman (rockman-en/scripts/prep.py), bỏ phần xoay / phóng
200→300 dpi / ghép tay, thêm THANG ĐO theo cỡ trang để chạy được với mọi độ phân giải (bản dịch tải về
thường chỉ 640–1600 px cao, dpi ghi trong file hay sai — Mega Man World ghi 120 cho mọi ảnh).

Làm gì với từng ảnh của 1 chương (thứ tự tên như reader):
  - Ảnh màu (bìa, trang màu, credit nhóm dịch), ảnh động, ảnh quá nhỏ (< 500 px cao), dải dọc kiểu
    webtoon, ảnh ngang quá dài -> chép NGUYÊN bytes, chỉ đổi số thứ tự.
  - Tờ đôi (ngang/cao 1.15–1.8, dò được gáy gần giữa) -> TÁCH 2 trang, nửa PHẢI trước (manga); lõi gáy
    (khe nền máy scan, vạch mép giấy) bỏ đi, lề gáy còn vệt bóng / mép rách tô trắng tới nét gần nhất.
    Tờ tranh liền gáy: xem mục dưới.
  - Mỗi trang: làm trắng (đường cong đơn điệu theo mức giấy đo cục bộ, giữ điểm đen; CỔNG AN TOÀN: ít
    giấy / hệ số quá lớn / mất chi tiết nhạt / vùng đen sáng lên -> giữ nguyên, chỉ tách) -> gọt vạch
    tối sát mép -> dọn vùng xám (lề ngoài khung về trắng, vệt mép scan, thớ giấy, bụi lẻ; không đụng
    nét đậm, tram, chấm vẽ tay) -> làm nét (unsharp kẹp min/max 3x3, không quầng, tự cân mỗi trang
    về độ nhoè mép ~0.95 px).
  - Trang đã làm mà còn THẤP (< 1400 px cao, vd nửa tờ 900×641 -> trang ~450 px: điện thoại phải kéo to
    2,6 lần -> nhoè) -> PHÓNG AI 2x bằng Real-ESRGAN (realesr-animevideov3, exe + model sẵn trong repo,
    cần GPU qua Vulkan), 1 lần gọi exe cho cả chương. Mảng tram mịn thành xám phẳng. Không phóng được
    (không GPU / exe lỗi) -> giữ cỡ gốc + báo. Tắt: --khong-phong hoặc "phong": false trong cấu hình.
  - Trang đen trắng lưu XÁM 1 kênh: nguồn PNG/BMP/GIF -> PNG, nguồn JPG/WebP/AVIF -> JPEG q92.
  - Tuỳ chọn ĐỔI CHỮ LỆCH FONT (doi_font.py): dòng nhóm dịch gõ bằng font hệ thống (mặc định Calibri Bold) giữa các
    bóng font truyện -> xoá đúng nét chữ cũ, in lại bằng font truyện (mặc định CC Wild Words Roman — phải cài trên
    máy chạy). Đọc chữ bằng khớp khuôn font đã biết + tự kiểm, không OCR. Dòng chắc tự đổi; dòng nghi (dính viền,
    còn dấu chưa đọc được, tràn chỗ...) chỉ đổi khi duyệt trong cấu hình. --soat-font xem trước, --doi-font đổi
    (chương đã làm sạch đổi tại chỗ), "doi_font": {"bat": true} = đổi luôn mỗi lần làm sạch.
Thang đo: u = chiều cao trang / 2020 (trang scan 300 dpi). Hằng số hình học (cửa sổ gáy, lề, khung,
vật thể...) nhân u; ngưỡng mức xám, cỡ hạt nhiễu, bán kính làm nét giữ theo điểm ảnh. Làm sạch ở CỠ GỐC
(thử phóng lên 300 dpi rồi mới làm: mất nét mảnh sát gáy, số trang nhạt đi), phóng AI là bước SAU CÙNG.

Tờ liền gáy (khung tranh vắt qua gáy): tự đo KHÔNG đáng tin (bộ Rockman: sai ~1/3) nên mặc định vẫn
TÁCH — đọc thấy tờ nào liền thì bấm "Join 2 pages" trong reader là xem lại thành tờ đôi (mặc định
phải-trái), khỏi chạy lại. Chỉ tự GIỮ NGUYÊN khi tranh chạm sát gáy cả hai bên ở > 30 % số dòng (đo trên
190 tờ có nhãn: không nhầm tờ nào nhưng chỉ bắt 4/28 tờ liền); tờ có tranh gần gáy được đánh dấu NGHI
trong báo cáo + ảnh lưới gáy (bắt đủ 28/28, nhưng với sách gáy hẹp báo nhầm nhiều). Muốn giữ nguyên /
ép tách: ghi vào file cấu hình rồi chạy lại với --lam-lai. Tờ giữ theo cấu hình "giu_nguyen": bỏ khe gáy
khi đo chắc (không dịch dọc — số đo lệch dọc không tin được), không thì để y; dải gáy không làm nét.

Mọi thứ của tool nằm trong 1 folder <truyện>/.lam-sach/ (chấm-đầu: reader, check_library, convert_webp,
--pack đều bỏ qua): cau-hinh.json, goc/ (bản gốc), soat/ (ảnh soát), tmp/ (chỉ có lúc đang chạy). Bản đầu
rải .goc-lam-sach / .lam-sach-soat / .lam-sach-tmp / .lam-sach.json ra folder truyện -> lần chạy thật sau gom về.

File cấu hình <folder truyện>/.lam-sach/cau-hinh.json (tool tạo mẫu ở lần chạy thật đầu tiên). Khoá chương = tên
folder chương (có arc thì "Arc/Chương"), "*" = mọi chương; ảnh = tên file GỐC, có hoặc không đuôi:
  {"doc": "phai-truoc" | "trai-truoc",
   "giu_nguyen": {"Chapter 1": ["016"]},   tờ liền gáy: giữ 1 ảnh, tự bỏ khe gáy nếu đo chắc
   "khong_ghep": {...},                    giữ 1 ảnh, không đụng gáy
   "tach":       {...},                    ép tách
   "bo_qua":     {...},                    chép nguyên, không xử lý gì
   "phong": true | false,                  phóng AI 2x trang thấp (mặc định true)
   "doi_font": {"bat": false,              true = đổi chữ lệch font ngay khi làm sạch
                "nguon": "Calibri Bold", "font": "CC Wild Words Roman",   tên font như Windows hiện / đường dẫn
                "duyet": {"Chapter 1": ["033:BOOMERAN"]},   dòng cần soát: đổi như ảnh xem trước
                "sua": {"Chapter 2": {"028:EFECTO": "SFX:"}},  đổi thành chữ ghi ở đây
                "bo": {"Chapter 1": ["014:CUT"]}}}       giữ nguyên chữ cũ
   (khoá "<ảnh>:<chữ đọc được>" lấy trong .lam-sach\\soat\\doi-font\\<chương>\\danh-sach.txt)

An toàn (như pdf_import): mỗi chương ghi ra <truyện>/.lam-sach/tmp/, kiểm từng ảnh giải mã được rồi mới
đổi chỗ: chương gốc -> <truyện>/.lam-sach/goc/<chương>/,
chương sạch vào đúng tên cũ (giữ .done và file phụ của tool tải). Ảnh đánh số lại 001…N liền nhau
(check_library không báo khuyết; reader gắn ?v=mtime nên điện thoại không giữ ảnh cũ). Dấu .lam-sach.json
trong chương (tham số + quyết định từng tờ) -> chạy lại bỏ qua chương đã làm; --lam-lai làm lại TỪ BẢN
GỐC (không bao giờ xử lý chồng 2 lần); --tra-goc trả bản gốc về chỗ cũ. Bị ngắt giữa chừng: chạy lại là
tự dọn / làm nốt. Ảnh soát: <truyện>/.lam-sach/soat/ (lưới gáy mỗi chương, ảnh trước|sau của --thu).

Cách dùng:
  python lam_sach_scan.py "downloads\\Mega Man World"                        # cả truyện (chương chưa làm)
  python lam_sach_scan.py "downloads\\Mega Man World\\Chapter 1 - World 1"   # 1 chương
  python lam_sach_scan.py "..." --dry-run      # chỉ kiểm + in kế hoạch, không ghi gì
  python lam_sach_scan.py "..." --thu 6        # làm thử 6 ảnh rải đều -> .lam-sach\\soat\\thu\\ (thư viện y nguyên)
  python lam_sach_scan.py "..." --lam-lai      # làm lại chương đã làm (từ bản gốc trong .lam-sach\\goc)
  python lam_sach_scan.py "..." --tra-goc      # trả bản gốc, bỏ bản đã làm sạch
  python lam_sach_scan.py "..." --trai-truoc   # truyện đọc trái->phải (truyện Tây / bản đã lật)
  python lam_sach_scan.py "..." --khong-phong  # không phóng AI trang thấp (giữ cỡ gốc)
  python lam_sach_scan.py "..." --soat-font    # dò chữ lệch font -> .lam-sach\\soat\\doi-font\\ (thư viện y nguyên)
  python lam_sach_scan.py "..." --doi-font     # đổi chữ lệch font (chương đã làm sạch: đổi tại chỗ)
Hoặc bấm `Lam sach scan.bat` (kéo-thả folder vào cũng được).

Máy: 1 tiến trình, tuần tự từng ảnh, OpenCV 2 luồng, ưu tiên thấp (reader vẫn mượt); ~1 s / 1 triệu
điểm ảnh + ~1 s / trang phóng AI. Cần numpy + opencv-python-headless + Pillow (requirements.txt).
Exit: 0 = ổn, 1 = có chương lỗi / bỏ qua vì lỗi, 2 = không thấy chương / thiếu thư viện / đang chạy.
"""

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import numpy as np
    import cv2
    from PIL import Image, ImageDraw
    _IMPORT_ERR = None
except ImportError as _e:   # báo rõ trong main(), không chết ngay lúc import
    np = cv2 = Image = ImageDraw = None
    _IMPORT_ERR = _e

BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS = BASE_DIR / "downloads"
SPREADS_FILE = BASE_DIR / ".reader-meta" / "spreads.json"   # cặp trang ghép tay của reader
CONF_NAME = ".lam-sach.json"   # trong folder chương: dấu đã làm + nhật ký (comics_core đọc đúng tên này)
# Mọi thứ khác của tool gom vào 1 folder chấm-đầu trong folder truyện (reader / check_library bỏ qua):
WORK_DIR = ".lam-sach"
SERIES_CONF = WORK_DIR + "/cau-hinh.json"   # cấu hình của truyện
TMP_DIR = WORK_DIR + "/tmp"     # chương đang ghi dở (cùng ổ đĩa -> đổi tên tức thì); xoá sau mỗi lần chạy
ORIG_DIR = WORK_DIR + "/goc"    # chương gốc
REVIEW_DIR = WORK_DIR + "/soat"  # ảnh soát
# bản đầu (02/11) rải 3 folder + 1 file ra folder truyện -> lần chạy thật đầu tiên gom về WORK_DIR
LEGACY = ((".goc-lam-sach", ORIG_DIR), (".lam-sach-soat", REVIEW_DIR), (".lam-sach.json", SERIES_CONF))
LEGACY_TMP = ".lam-sach-tmp"
VERSION = 2               # 2: thêm phóng AI trang thấp
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}   # = IMG_EXTS của reader
LOSSY_EXTS = {".jpg", ".jpeg", ".webp", ".avif"}
REF_H = 2020          # chiều cao trang scan 300 dpi (Rockman tập 1: 2006–2052 px) -> u = 1
MIN_H = 500           # trang thấp hơn (u < 0.25): quá nhỏ để đo -> chép nguyên
DOUBLE_AR = (1.15, 1.8)   # ngang/cao của tờ đôi (mẫu: 1.38–1.42; trang đơn 0.69–0.70)
TALL_AR = 2.2         # cao/ngang lớn hơn = dải dọc webtoon -> chép nguyên
COLOR_T = 0.02        # tỉ lệ vùng màu liền mảng: đen trắng ≤ 0.0034, bìa màu 0.32–0.73
SEC_PER_MP = 1.0      # ước thời gian: ~1 s / 1 triệu điểm ảnh (PC dev)
# Phóng AI trang thấp: cùng exe + model với lam-net.bat (model đã chốt: giữ chi tiết gốc tốt nhất, nhanh).
ESR_EXE = BASE_DIR / "realesrgan-ncnn-vulkan-v0.2.0-windows" / "realesrgan-ncnn-vulkan.exe"
ESR_MODEL = "realesr-animevideov3"
PHONG_H = 1400        # trang (sau tách) thấp hơn -> phóng AI; MMW: trang 634–1015 px nhoè trên điện thoại
PHONG_SCALE = 2
SEC_PER_PHONG = 1.0   # ước: ~0,7 s / trang 450 px (Intel Iris Xe, PC dev)

FONT_REVIEW = REVIEW_DIR + "/doi-font"   # ảnh trước|sau + danh-sach.txt của bước đổi font, mỗi chương 1 folder

CONF_TEMPLATE = {
    "_huong_dan": ("doc: 'phai-truoc' (manga) hoac 'trai-truoc'. Cac muc con lai: {ten chuong: [ten anh goc]} "
                   "(chuong co arc: 'Arc/Chuong'; '*' = moi chuong; ten anh co/khong duoi). giu_nguyen = to "
                   "tranh lien gay giu 1 anh (tu bo khe gay neu do chac); khong_ghep = giu 1 anh, khong dung gay; "
                   "tach = ep tach; bo_qua = chep nguyen. phong: true/false = phong AI 2x trang thap (< 1400 px, "
                   "Real-ESRGAN, can GPU). Sua xong chay lai voi --lam-lai. doi_font: doi chu go bang font he "
                   "thong (nguon, mac dinh Calibri Bold) sang font truyen (font, mac dinh CC Wild Words Roman); "
                   "bat = tu doi ngay khi lam sach; duyet / sua / bo: {ten chuong: [khoa]} / {ten chuong: {khoa: "
                   "chu moi}} voi khoa '<anh>:<chu>' in trong .lam-sach\\soat\\doi-font\\<chuong>\\danh-sach.txt, "
                   "sua xong chay --doi-font."),
    "doc": "phai-truoc",
    "phong": True,
    "giu_nguyen": {},
    "khong_ghep": {},
    "tach": {},
    "bo_qua": {},
    "doi_font": {"bat": False, "nguon": "Calibri Bold", "font": "CC Wild Words Roman",
                 "duyet": {}, "sua": {}, "bo": {}},
}
RULE_KEYS = ("bo_qua", "khong_ghep", "giu_nguyen", "tach")   # thứ tự ưu tiên khi 1 ảnh nằm ở nhiều mục
KIND_VI = dict(doi='tờ đôi', don='trang đơn', rong='ảnh ngang không thấy gáy', mau='ảnh màu', dong='ảnh động',
               nho='ảnh quá nhỏ', khac='dải dọc/băng ngang', bo_qua='bỏ qua theo cấu hình')


def natkey(s):
    """Khóa sắp xếp tự nhiên (giống reader): '10' đứng sau '2'."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


class Thang:
    """Thang đo theo cỡ trang: u = chiều cao trang / REF_H. Hằng số hình học của bản gốc (đo ở 300 dpi)
    nhân u, có sàn để không về 0. u = 1 thì mọi hằng số y như prep.py (kiểm hồi quy từng điểm)."""

    def __init__(self, u):
        self.u = float(u)

    def L(self, v, lo=1):
        """Độ dài (px)."""
        return max(lo, int(round(v * self.u)))

    def K(self, v, lo=3):
        """Cỡ nhân lẻ (blur / dilate / median)."""
        k = max(lo, int(round(v * self.u)))
        return k if k % 2 else k + 1

    def F(self, v, lo=0.5):
        """Số thực (sigma)."""
        return max(lo, v * self.u)


# ================================================================ tiện ích ảnh

def paper_level(g):
    h = np.bincount(g.ravel(), minlength=256).astype(np.float64)
    h[:150] = 0
    h = np.convolve(h, np.ones(5) / 5, mode='same')
    return int(h.argmax())


def color_coherent(rgb, g, P):
    """Tỉ lệ diện tích có màu THẬT. Trung bình theo khối (cạnh ≈ cao/128) để viền màu JPEG quanh nét tự
    triệt tiêu, cân trắng theo màu giấy, rồi chỉ tính vùng màu liền ≥ 6 khối. Bộ đo cũ của prep.py
    (tỉ lệ điểm > 0.5 %) coi ~2/3 trang bản dịch là ảnh màu vì nhiễu màu JPEG trên giấy ngà."""
    H, W = g.shape
    b = max(4, H // 128)
    hb, wb = H // b, W // b
    if hb < 2 or wb < 2:
        return 0.0
    s, gs = rgb[::2, ::2], g[::2, ::2]
    pp = s[(gs >= P - 6) & (gs <= P + 6)]
    pc = np.median(pp, axis=0).astype(np.float32) if len(pp) > 1000 else np.array([P, P, P], np.float32)
    blk = cv2.resize(rgb[:hb * b, :wb * b], (wb, hb), interpolation=cv2.INTER_AREA).astype(np.float32)
    blk *= 255.0 / np.maximum(pc, 1)
    col = ((blk.max(2) - blk.min(2)) > 25).astype(np.uint8)
    _, _, st, _ = cv2.connectedComponentsWithStats(col, connectivity=8)
    a = st[1:, 4]
    return float(a[a >= 6].sum()) / col.size


def runs(b):
    """Các đoạn liên tục True trong mảng 1 chiều → [(đầu, cuối)]."""
    d = np.diff(np.r_[0, b.astype(np.int8), 0])
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


# ================================================================ gáy

SEAM_R = 40   # nửa bề rộng vùng khảo sát quanh đường gáy (px, 300 dpi)
WIDE_R = 90   # nửa bề rộng vùng tìm khe rộng (px, 300 dpi)
# Tờ liền gáy — đo 02/11 trên 190 tờ đôi có nhãn (Rockman tập 1+2: 28 liền do người duyệt, 162 tách) + Mega Man
# World c1/016. cross = tỉ lệ dòng có mực sát lõi gáy CẢ HAI bên, clean = tỉ lệ dòng không có mực quanh gáy.
CROSS_KEEP = 0.3   # tự GIỮ NGUYÊN (không đụng gáy): nhầm 0/162 tách (tờ tách cao nhất 0.155), chỉ bắt 4/28 liền
CLEAN_NGHI = 0.85  # đánh dấu NGHI (vẫn tách): bắt 28/28 + c1/016; nhầm 70/162 ở Rockman (gáy hẹp, tranh tràn sát
                   # gáy), 0/35 ở Mega Man World (lề gáy rộng) — luật cũ của prep chỉ bắt 11/28 và sót c1/016


def find_seam(g, P):
    """Đường gáy = mép tờ giấy: bậc sáng hoặc vạch chạy liên tục trên phần giấy trắng.
    Trả về (x_giữa, độ dốc dx/dy, số dải ủng hộ, điểm). Bộ lọc mép ở mức điểm ảnh nên không đổi theo thang."""
    H, W = g.shape
    xa, xb = int(W * .40), int(W * .60)
    pad = 6
    sub = g[:, xa - pad:xb + pad].astype(np.float32)
    ok = cv2.erode((sub > P - 45).astype(np.uint8), np.ones((1, 9), np.uint8)).astype(bool)
    step = np.zeros_like(sub)
    step[:, 2:-2] = sub[:, 4:] - sub[:, :-4]
    line = np.zeros_like(sub)
    line[:, 3:-3] = sub[:, 3:-3] - (sub[:, :-6] + sub[:, 6:]) / 2
    nb = 16
    cands = []
    for k in range(nb):
        ya, yb = H * k // nb, H * (k + 1) // nb
        okb = ok[ya:yb]
        cnt = okb.sum(0)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            ms = np.abs(np.nanmedian(np.where(okb, step[ya:yb], np.nan), axis=0))
            ml = np.abs(np.nanmedian(np.where(okb, line[ya:yb], np.nan), axis=0))
        s = np.nan_to_num(np.maximum(ms, ml))
        s[cnt < 0.15 * (yb - ya)] = 0
        s[:pad] = 0
        s[-pad:] = 0
        for _ in range(3):
            i = int(s.argmax())
            if s[i] < 3:
                break
            cands.append(((ya + yb) / 2, xa - pad + i, float(s[i])))
            s[max(0, i - 4):i + 5] = 0
    if not cands:
        return None
    C = np.array(cands)
    yc = H / 2
    best = None
    for i in range(len(C)):
        for j in range(i, len(C)):
            if j != i and C[i, 0] == C[j, 0]:
                continue
            slope = 0.0 if j == i else (C[j, 1] - C[i, 1]) / (C[j, 0] - C[i, 0])
            if abs(slope) > 0.015:
                continue
            x0 = C[i, 1] + slope * (yc - C[i, 0])
            pred = x0 + slope * (C[:, 0] - yc)
            inl = np.abs(C[:, 1] - pred) <= 2
            sc = 0.0
            bands = set()
            for y in np.unique(C[inl, 0]):
                m = inl & (C[:, 0] == y)
                sc += C[m, 2].max()
                bands.add(y)
            if best is None or sc > best[0]:
                best = (sc, x0, slope, len(bands), inl)
    if best is None:
        return None
    sc, x0, slope, nbands, inl = best
    if inl.sum() >= 3:
        w = C[inl, 2]
        A = np.stack([np.ones(inl.sum()), C[inl, 0] - yc], 1)
        sol = np.linalg.lstsq(A * w[:, None] ** .5, C[inl, 1] * w ** .5, rcond=None)[0]
        if abs(sol[1]) <= 0.015:
            x0, slope = sol
    return dict(x=float(x0), slope=float(slope), bands=int(nbands), score=round(float(sc), 1))


def seam_x(seam, y, H):
    return seam['x'] + seam['slope'] * (y - H / 2)


def seam_profile(g, P, seam, R, sc):
    """Hồ sơ từng cột dọc theo đường gáy (bám độ nghiêng): mức giấy và tỉ lệ điểm tối.
    Mức giấy lấy trên các dòng mà hai đầu vùng khảo sát đều là giấy (ít tranh), nên phản ánh khe/bóng."""
    H, W = g.shape
    ys = np.arange(H)
    sx = seam_x(seam, ys, H)
    offs = np.arange(-R, R + 1)
    X = np.clip(np.rint(sx[:, None] + offs[None, :]).astype(int), 0, W - 1)
    S = g[ys[:, None], X].astype(np.float32)
    f = min(sc.L(12, 3), R)
    far = np.r_[0:f, 2 * R + 1 - f:2 * R + 1]
    paper_rows = (S[:, far] > P - 25).all(1)
    rows = S[paper_rows] if paper_rows.mean() >= 0.08 else S
    PL = np.median(rows, axis=0)
    dark = (S < P - 40).mean(0)
    bright = (S > P + 4).mean(0)
    return offs, PL, dark, bright, float(paper_rows.mean())


def seam_core(offs, PL, dark, bright, paper_ok, sc):
    """Lõi gáy cần bỏ, tương đối với đường gáy:
      - khe giữa hai lá = nền máy scan, sáng hơn giấy ở gần như mọi dòng (kể cả nơi có tranh);
      - vạch mép giấy sát khe (tối liên tục, hoặc vết lõm hẹp trên hồ sơ giấy).
    Không có khe thì chỉ bỏ vạch mép. Dải bóng sát mép (giấy tối dần, vẫn có nét vẽ) KHÔNG bỏ
    mà trả về để làm sáng lại theo cột."""
    R = (len(offs) - 1) // 2
    idx = lambda d: d + R
    n21, n22, n20, n10, n12, n24 = (min(sc.L(v), R) for v in (21, 22, 20, 10, 12, 24))
    nf = min(sc.L(12, 3), R)
    sideL = float(np.median(PL[:nf]))
    sideR = float(np.median(PL[-nf:]))
    # mức nền hai bên lấy xa đường gáy (±22..40) để không lẫn vạch mép
    bL = float(np.median(bright[:max(1, idx(-n21))]))
    bR = float(np.median(bright[idx(n22):]))
    dL = float(np.median(dark[:max(1, idx(-n21))]))
    dR = float(np.median(dark[idx(n22):]))
    near = slice(idx(-n10), idx(n10) + 1)
    pk = idx(-n10) + int(np.argmax(bright[near]))
    kind = 'none'
    # khe phải nổi hẳn so với hai bên ngay cạnh nó (một lá giấy sáng hơn lá kia chỉ là bậc, không phải khe)
    a7, a8 = sc.L(7), sc.L(8)
    wl_ = float(np.median(bright[max(0, pk - n20):max(1, pk - a7)]))
    wr_seg = bright[pk + a8:pk + n21]
    wr_ = float(np.median(wr_seg)) if len(wr_seg) else float(bright[-1])
    if bright[pk] >= 0.15 and bright[pk] - max(wl_, wr_) >= 0.12:
        kind = 'gap'
        lo = hi = pk
        tl = max(0.6 * bright[pk], wl_ + 0.06)
        tr = max(0.6 * bright[pk], wr_ + 0.06)
        while lo - 1 >= idx(-n20) and bright[lo - 1] >= tl:
            lo -= 1
        while hi + 1 <= idx(n20) and bright[hi + 1] >= tr:
            hi += 1
    else:
        # không có khe: tìm vạch mép giấy hẹp nhất rõ nhất (vạch mảnh ở mức điểm ảnh: so ±3 cột)
        dip = np.zeros(len(offs), bool)
        dip[3:-3] = PL[3:-3] < np.minimum(PL[:-6], PL[6:]) - 6
        cand = [i for i in range(idx(-n12), idx(n12) + 1) if dip[i]]
        if paper_ok and cand:
            c = min(cand, key=lambda i: PL[i])
            kind = 'line'
            lo = hi = c
        else:
            lo = hi = idx(0)

    def is_line(i, side_dark, side_pl):
        return dark[i] > side_dark + 0.25 or (paper_ok and PL[i] < side_pl - 30)
    # vạch có thể cách lõi 1–2 cột giấy: lấy cột vạch xa nhất trong 4 cột kế bên
    n4 = sc.L(4, 2)
    ext = [k for k in range(1, n4 + 1) if lo - k >= idx(-n24) and is_line(lo - k, dL, sideL)]
    lo -= max(ext, default=0)
    ext = [k for k in range(1, n4 + 1) if hi + k <= idx(n24) and is_line(hi + k, dR, sideR)]
    hi += max(ext, default=0)
    d_lo, d_hi = int(offs[lo]) - 1, int(offs[hi]) + 1
    band = {}
    if paper_ok:
        for rng, ref in ((range(lo - 2, -1, -1), sideL), (range(hi + 2, len(offs)), sideR)):
            for i in rng:
                if PL[i] < ref - 4:
                    band[int(offs[i])] = (float(PL[i]), ref)
                else:
                    break
    return d_lo, d_hi, band, dict(kind=kind, sideL=round(sideL, 1), sideR=round(sideR, 1),
                                  bL=round(bL, 3), bR=round(bR, 3))


def theil_sen(ys, xs, yc):
    """Đường x = a + b*(y - yc) bền với điểm lạc (trung vị độ dốc từng cặp)."""
    ys, xs = np.asarray(ys, float), np.asarray(xs, float)
    sl = [(xs[j] - xs[i]) / (ys[j] - ys[i]) for i in range(len(ys)) for j in range(i + 1, len(ys)) if ys[j] != ys[i]]
    b = float(np.median(sl)) if sl else 0.0
    b = max(-0.015, min(0.015, b))
    a = float(np.median(xs - b * (ys - yc)))
    return a, b


def core_edges(g, P, seam, kind, d_lo, d_hi, R, sc, nb=12):
    """Tinh chỉnh mép trái/phải của lõi gáy theo từng dải ngang rồi khớp thành 2 đường
    (khe giữa hai lá có thể hình nêm và trôi so với đường gáy chung).
    Trả về (cột đầu lõi, cột cuối lõi) cho từng dòng, và số dải dùng được."""
    H, W = g.shape
    ys_c, los, his = [], [], []
    tol = sc.L(8, 2)
    for k in range(nb):
        ya, yb = H * k // nb, H * (k + 1) // nb
        yc = (ya + yb) / 2
        sub_seam = dict(seam, x=seam_x(seam, yc, H))
        o, PLb, dkb, brb, prb = seam_profile(g[ya:yb], P, sub_seam, R, sc)
        lo_b, hi_b, _, inf = seam_core(o, PLb, dkb, brb, prb >= 0.08, sc)
        if inf['kind'] != kind or kind == 'none':
            continue
        # chỉ nhận dải có lõi gần lõi chung (tránh bắt nhầm nét tranh)
        if abs(lo_b - d_lo) > tol or abs(hi_b - d_hi) > tol:
            continue
        ys_c.append(yc)
        los.append(sub_seam['x'] + lo_b)
        his.append(sub_seam['x'] + hi_b)
    ys = np.arange(H)
    if len(ys_c) >= 4:
        a0, b0 = theil_sen(ys_c, los, H / 2)
        a1, b1 = theil_sen(ys_c, his, H / 2)
        c0 = np.rint(a0 + b0 * (ys - H / 2)).astype(int)
        c1 = np.rint(a1 + b1 * (ys - H / 2)).astype(int)
        c1 = np.maximum(c1, c0 + 1)
    else:
        sx = seam_x(seam, ys, H)
        c0 = np.rint(sx).astype(int) + d_lo
        c1 = np.rint(sx).astype(int) + d_hi
    return c0, c1, len(ys_c)


def wide_gap(g, P, seam, sc, nb=12):
    """Khe rộng giữa hai lá: dải gần như không có nét, có nền máy scan (sáng hơn giấy), sát đường gáy nhưng
    vượt ra ngoài vùng ±20 px mà seam_core xét (Rockman 0058: ~45 px). Mép khe = nơi tỉ lệ điểm tối của cột
    lên tới nửa mức tranh bên đó, đo theo 12 dải ngang rồi khớp thành 2 đường. CHỈ dùng cho tờ liền gáy.
    Trả về (cột đầu khe, cột cuối khe) từng dòng + thông tin, hoặc None nếu không có khe rộng."""
    H, W = g.shape
    R = sc.L(WIDE_R, 10)
    offs = np.arange(-R, R + 1)
    n10, n12, n13, n16, n25, n40 = (sc.L(v) for v in (10, 12, 13, 16, 25, 40))

    def prof(ya, yb):
        ys = np.arange(ya, yb)
        X = np.clip(np.rint(seam_x(seam, ys, H)[:, None] + offs[None, :]).astype(int), 0, W - 1)
        S = g[ys[:, None], X]
        return (S < P - 40).mean(0), (S > P + 4).mean(0)
    dk, br = prof(0, H)
    run = None
    for s, e in runs(dk <= 0.10):
        if e > R - n12 and s < R + n13 and (run is None or e - s > run[1] - run[0]):
            run = (int(s), int(e))
    if run is None or run[1] - run[0] < n16 or br[run[0]:run[1]].max() < 0.5:
        return None
    s0, e0 = run
    yc_l, xl, yc_r, xr = [], [], [], []
    for k in range(nb):
        ya, yb = H * k // nb, H * (k + 1) // nb
        yc = (ya + yb) / 2
        d, _ = prof(ya, yb)
        seg = d[max(0, s0 - n40):max(1, s0 - n10)]
        lvl = float(np.median(seg)) if len(seg) else 0.0
        if lvl >= 0.2:
            i = s0
            while i > max(0, s0 - n25) and d[i - 1] < 0.5 * lvl:
                i -= 1
            yc_l.append(yc)
            xl.append(seam_x(seam, yc, H) + offs[i])
        seg = d[min(len(d) - 1, e0 + n10):e0 + n40]
        lvr = float(np.median(seg)) if len(seg) else 0.0
        if lvr >= 0.2:
            j = e0 - 1
            while j < min(len(d) - 1, e0 + n25) and d[j + 1] < 0.5 * lvr:
                j += 1
            yc_r.append(yc)
            xr.append(seam_x(seam, yc, H) + offs[j])
    ys = np.arange(H)
    sx = seam_x(seam, ys, H)
    if len(xl) >= 4:
        a, b = theil_sen(yc_l, xl, H / 2)
        c0 = np.rint(a + b * (ys - H / 2)).astype(int)
    else:
        c0 = np.rint(sx + offs[s0]).astype(int)
    if len(xr) >= 4:
        a, b = theil_sen(yc_r, xr, H / 2)
        c1 = np.rint(a + b * (ys - H / 2)).astype(int)
    else:
        c1 = np.rint(sx + offs[e0 - 1]).astype(int)
    c1 = np.maximum(c1, c0 + 1)
    return c0, c1, dict(run=[int(offs[s0]), int(offs[e0 - 1])], bands_l=len(xl), bands_r=len(xr))


def core_is_gap(g, P, c0, c1, sc):
    """Cổng an toàn trước khi bỏ lõi của tờ liền gáy: vùng định bỏ không được là tranh. So tỉ lệ điểm mực
    trong lõi với hai dải 5–15 px ngay ngoài lõi; cột tối gần như suốt chiều cao (vạch mép giấy) không tính
    là tranh. Lõi gần như không có mực thì bỏ được (khe hoặc lề trống)."""
    H, W = g.shape
    ys = np.arange(0, H, 4)

    def ink(base, lo, hi):
        cols = base[ys][:, None] + np.arange(lo, hi)[None, :]
        return float((g[ys[:, None], np.clip(cols, 0, W - 1)] < P - 40).mean())
    wmax = int((c1 - c0).max()) + 1
    cols = c0[ys][:, None] + np.arange(wmax)[None, :]
    inside_mask = cols <= c1[ys][:, None]
    v = g[ys[:, None], np.clip(cols, 0, W - 1)] < P - 40
    colfrac = np.where(inside_mask, v, False).sum(0) / np.maximum(inside_mask.sum(0), 1)
    keep = colfrac < 0.85
    m = inside_mask & keep[None, :]
    inside = float(v[m].mean()) if m.any() else 0.0
    n5, n15, n6, n16 = sc.L(5), sc.L(15, 3), sc.L(6), sc.L(16, 3)
    left = ink(c0, -n15, -n5)
    right = ink(c1, n6, n16)
    ok = inside < 0.08 or inside < 0.5 * min(left, right)
    return ok, dict(ink_inside=round(inside, 3), ink_left=round(left, 3), ink_right=round(right, 3))


def apply_band(g, seam, band, B):
    """Làm sáng dải bóng sát mép giấy theo từng cột (đường cong đơn điệu như bước làm trắng)."""
    if not band:
        return g
    H, W = g.shape
    out = g.astype(np.float32)
    ys = np.arange(H)
    sx = seam_x(seam, ys, H)
    for d, (pl, ref) in band.items():
        k = min((ref - B) / max(pl - B, 1.0), 1.35)
        X = np.clip(np.rint(sx + d).astype(int), 0, W - 1)
        v = out[ys, X]
        out[ys, X] = B + (v - B) * k
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def crossing_features(g, P, xl, xr, sc):
    """Đặc trưng tranh vắt qua gáy: mực sát hai bên cùng dòng + tỉ lệ dòng sạch quanh gáy."""
    H, W = g.shape
    ya, yb = int(H * .03), int(H * .97)
    n6, n12 = sc.L(6, 2), sc.L(12, 3)
    L = g[ya:yb, max(0, xl - n6):xl] < 110
    Rr = g[ya:yb, xr:xr + n6] < 110
    both = (L.any(1) & Rr.any(1)).mean()
    clean = ~((g[ya:yb, max(0, xl - n12):xr + n12] < 110).any(1))
    return float(both), float(clean.mean())


def join_spread(g, c0, c1, P):
    """Tờ liền gáy: bỏ lõi gáy [c0, c1] rồi ghép sát hai lá. Nửa trái giữ nguyên toạ độ; nửa phải dịch trái
    MỘT khoảng cố định S = trung vị bề rộng lõi (dịch theo từng dòng thì lõi hình nêm làm cả nửa phải xô xiên
    — lỗi Rockman 0028/0060). Dòng có lõi rộng hơn S: còn khe hẹp → tô màu giấy; hẹp hơn S: hai lá chồng →
    mỗi bên bỏ một nửa phần chồng. KHÔNG dịch dọc (đo lệch dọc ở Rockman không tin được).
    Trả về (ảnh ghép, cột đường ghép từng dòng)."""
    H, W = g.shape
    wrow = c1 - c0 + 1
    S = int(round(float(np.median(wrow))))
    out = np.full((H, W - S), P, np.uint8)
    join = np.empty(H, int)
    for y in range(H):
        a, w = int(c0[y]), int(wrow[y])
        if w >= S:
            out[y, :a] = g[y, :a]
            out[y, a + w - S:] = g[y, a + w:]
            join[y] = a
        else:
            b = a - (S - w) // 2
            out[y, :b] = g[y, :b]
            out[y, b:] = g[y, b + S:]
            join[y] = b
    return out, join


def analyse_double(g, P, sc):
    """Dò gáy tờ đôi: đường gáy, lõi cần bỏ từng dòng, dải bóng đã làm sáng, đặc trưng liền gáy.
    Trả về dict (g đã làm sáng dải bóng, c0, c1, ...) hoặc None nếu không thấy gáy."""
    H, W = g.shape
    seam = find_seam(g, P)
    if seam is None:
        return None
    R = sc.L(SEAM_R, 8)
    offs, PL, dark, bright, prow = seam_profile(g, P, seam, R, sc)
    d_lo, d_hi, band, sides = seam_core(offs, PL, dark, bright, prow >= 0.08, sc)
    B0 = float(min(np.percentile(g, 1), 100))
    g = apply_band(g, seam, band, B0)
    c0, c1, nbands = core_edges(g, P, seam, sides['kind'], d_lo, d_hi, R, sc)
    xl, xr = int(c0.min()), int(c1.max() + 1)
    both, clean = crossing_features(g, P, xl, xr, sc)
    strong = both > CROSS_KEEP
    nghi = clean < CLEAN_NGHI and not strong
    info = dict(x=round(seam['x'], 1), slope=round(seam['slope'] * 1000, 2), bands=seam['bands'],
                kind=sides['kind'], core=[d_lo, d_hi], core_w=int(np.round(np.mean(c1 - c0 + 1))),
                edge_bands=nbands, band=len(band), cross=round(both, 3), clean=round(clean, 3),
                nghi=bool(nghi), lien_ro=bool(strong))
    return dict(g=g, seam=seam, c0=c0, c1=c1, info=info, nghi=nghi, strong=strong)


# ================================================================ làm trắng

def whiten(g, sc):
    """Đường cong đơn điệu từng điểm: giữ điểm đen B, đưa màu giấy (ước lượng cục bộ, mượt) về 255.
    Không lọc, không làm nét: nét và chấm tram giữ nguyên vị trí."""
    H, W = g.shape
    P = paper_level(g)
    band = (g >= P - 12) & (g <= P + 12)
    paper_frac = float(band.mean())
    B = float(min(np.percentile(g, 1), 100))
    tile = max(8, int(round(48 * sc.u)))     # 32 px ở 200 dpi
    th, tw = H // tile, W // tile
    gc = g[:th * tile, :tw * tile].astype(np.float32).reshape(th, tile, tw, tile)
    bc = band[:th * tile, :tw * tile].reshape(th, tile, tw, tile)
    cnt = bc.sum((1, 3)).astype(np.float32)
    ssum = (gc * bc).sum((1, 3))
    m = (cnt > 0.25 * tile * tile).astype(np.float32)
    val = np.where(m > 0, ssum / np.maximum(cnt, 1), 0).astype(np.float32)
    num = cv2.GaussianBlur(val * m, (0, 0), 3)
    den = cv2.GaussianBlur(m, (0, 0), 3)
    loc = np.where(den > 1e-3, num / np.maximum(den, 1e-6), P).astype(np.float32)
    loc = cv2.GaussianBlur(loc, (0, 0), 2)
    loc = np.clip(loc, P - 10, P + 6)
    Pl = cv2.resize(loc, (W, H), interpolation=cv2.INTER_CUBIC)
    gf = g.astype(np.float32)
    k = (255.0 - B) / np.maximum(Pl - B, 1.0)
    out = np.clip(np.rint(B + (gf - B) * k), 0, 255).astype(np.uint8)
    lost = float(((gf < Pl - 10) & (out >= 252)).mean())
    dark_shift = float(np.percentile(out, 2) - np.percentile(g, 2))
    info = dict(P=P, B=round(B, 1), paper_frac=round(paper_frac, 3), gain_max=round(float(k.max()), 3),
                local_range=round(float(loc.max() - loc.min()), 1), lost=round(lost, 6),
                dark_shift=round(dark_shift, 1))
    reasons = []
    if paper_frac < 0.12:
        reasons.append('ít giấy trắng')
    if info['gain_max'] > 1.35:
        reasons.append('hệ số quá lớn')
    if lost >= 5e-4:
        reasons.append('mất chi tiết nhạt')
    if dark_shift > 4:
        reasons.append('vùng đen sáng lên')
    info['ok'] = not reasons
    info['reasons'] = reasons
    return out, info


def clean_inner(w, inner_left, sc):
    """Dọn vệt ố/keo/mép rách ở lề gáy trang đã tách: tô trắng từ mép cắt tới nét gần nhất (trừ đệm)."""
    a = w if inner_left else w[:, ::-1]
    H, W = a.shape
    maxw = min(W, int(round(8 / 25.4 * 300 * sc.u)))   # 8 mm
    buf = sc.L(4, 2)
    f = a[:, :maxw].astype(np.float32)
    hp = np.abs(f - cv2.GaussianBlur(f, (0, 0), 2))
    k15 = sc.K(15)
    locm = cv2.blur(f, (k15, k15))
    content = (f < 150) | (hp > 25) | (locm < 225)
    k5 = sc.K(5)
    content = cv2.dilate(content.astype(np.uint8), np.ones((k5, k5), np.uint8)).astype(bool)
    bh = sc.L(8, 2)
    lim = np.zeros(H, np.int32)
    for y0 in range(0, H, bh):
        c = content[y0:y0 + bh].any(0)
        idx = int(np.argmax(c)) if c.any() else maxw
        lim[y0:y0 + bh] = max(0, idx - buf)
    lim = cv2.erode(lim.reshape(-1, 1).astype(np.float32), np.ones((5 * bh, 1), np.uint8)).ravel().astype(np.int32)
    region = np.arange(maxw)[None, :] < lim[:, None]
    b = a.copy()
    sub = b[:, :maxw]
    changed = int((region & (sub < 250)).sum())
    sub[region] = 255
    out = b if inner_left else b[:, ::-1]
    return np.ascontiguousarray(out), dict(cleaned_px=changed, max_w=int(lim.max()), mean_w=round(float(lim.mean()), 1))


# ================================================================ dọn vùng xám

EDGE = 12          # dải sát mép trang (px, 300 dpi): chỉ có vệt mép giấy / bóng scan → trong lề xoá hẳn
EDGE_DEEP = 30     # mảng chạm dải sát mép mà ăn sâu quá EDGE + 30 px = tranh / khung, không phải vệt mép
EDGE_BAND = 40     # vệt nhạt (đậm nhất ≥ 120) nằm trọn trong 40 px sát mép → có thể là vệt mép
PROT_PAD = 30      # đệm quanh đoạn tranh tràn lề
MIN_RUN = 0.10     # đường khung: đoạn thẳng dài ≥ 10% cạnh (tờ liền gáy: nửa tờ)
GUARD_T = 0.04     # chốt chặn: mật độ điểm xám (< 225) ngoài nét đậm > 4% trong ô 41x41 → tranh
GUARD_WIN = 41
GUARD_PAD = 20
ROUGH_T = 4.5      # trong 40 px sát mép: chỉ coi là tranh khi gồ ghề dọc theo cạnh (tram, mây) — bóng mép thì trơn
OBJ_MIN = 40       # mảng mực chạm lề dài hơn 40 px = vật thể lấn ra lề → không dọn


def trim_edge_lines(a, sc):
    """Vạch tối chạy dọc mép ảnh (bóng mép giấy / mép máy scan, dày 1–5 px) → tô trắng, sửa tại chỗ.
    Nhận là vạch khi ở độ sâu 0 có ≥ 50 % chiều dài mép tối (< 120) và tỉ lệ đó sụt xuống ≤ 40 % (và ≤ nửa)
    trong vài px; tranh tràn lề thì tỉ lệ tối giữ đều theo độ sâu nên không bị đụng. Gọt theo từng đoạn
    dọc mép (mép giấy xiên → vạch dày dần): mỗi đoạn gọt tới độ sâu đầu tiên còn ≤ 30 % điểm tối."""
    maxd, seg, n10 = sc.L(6, 2), sc.L(64, 8), sc.L(10, 3)
    info = {}
    for side, v in (('tren', a), ('duoi', a[::-1]), ('trai', a.T), ('phai', a.T[::-1])):
        fr = (v[:maxd] < 120).mean(1)
        if fr[0] < 0.5:
            continue
        k = next((k for k in range(1, maxd) if fr[k] <= 0.4 and fr[k] <= 0.5 * fr[0]), None)
        if k is None:
            continue
        ks = []
        for s in range(0, v.shape[1], seg):
            f = (v[:n10, s:s + seg] < 120).mean(1)
            kc = next((d for d in range(1, n10) if f[d] <= 0.3), k)
            v[:kc, s:s + seg] = 255
            ks.append(kc)
        info[side] = dict(k=k, max=max(ks))
    return info


def frame_margins(g, sc, spread=False, depth_frac=0.15, ext=None):
    """Lề = dải giữa mép trang và ĐƯỜNG KHUNG THẲNG gần mép nhất, độ sâu tính riêng từng cột.
      - Tranh tràn lề (mảng mực < 160 bắt đầu ngay sau dải sát mép, ăn sâu vào trong, không phải đường chạy
        dọc mép): chỉ bỏ đoạn đó (+đệm), không bỏ cả cạnh.
      - Vệt mép scan (mảng < 200 nông sát mép, hoặc vệt nhạt nằm trọn trong dải sát mép; chạy dọc mép hoặc
        đứng riêng; không dính tranh) không tính là khung và bị xoá hẳn (trả về Z). Cột "bận" (có mực sâu
        hơn dải sát mép, như hoa văn / tram tràn lề) thì không xoá gì ở dải sát mép.
      - Chỗ khung đứt (bóng thoại, chữ, tranh lấn ra lề; khe giữa 2 ô) lấp bằng độ sâu nông hơn của 2 bên,
        trừ khi sát đoạn tranh tràn lề (khi đó coi cả đoạn là tranh tràn lề).
    ext: độ sâu lề 2 cạnh vuông góc (lượt 2) — đoạn khung kết thúc trong lề cạnh vuông góc thì nối ra
    tới mép để phủ cả góc trang."""
    H, W = g.shape
    E, ED, EB, PP = sc.L(EDGE, 2), sc.L(EDGE_DEEP, 2), sc.L(EDGE_BAND, 3), sc.L(PROT_PAD, 2)
    band = sc.L(5, 2)
    n60, n100, n40, n20, n15, n30, p20 = (sc.L(60, 10), sc.L(100, 15), sc.L(40, 5), sc.L(20, 4),
                                          sc.L(15, 3), sc.L(30, 5), sc.L(20, 3))
    ink = g < 160
    dark = g < 200
    M = np.zeros((H, W), bool)
    Z = np.zeros((H, W), bool)
    info = {}
    unit_w = W / 2 if spread else W
    for side in ('bottom', 'top', 'left', 'right'):
        if side in ('bottom', 'top'):
            fl = (lambda X: X) if side == 'top' else (lambda X: X[::-1, :])
            L, minrun, Dm = W, MIN_RUN * unit_w, int(depth_frac * H)
        else:
            fl = (lambda X: X.T) if side == 'left' else (lambda X: X.T[::-1, :])
            L, minrun, Dm = H, MIN_RUN * H, int(depth_frac * W)
        A, A2 = fl(ink)[:Dm], fl(dark)[:Dm]
        n1, lab1, st1, _ = cv2.connectedComponentsWithStats(A[E:].astype(np.uint8), connectivity=8)
        cont = (st1[:, 1] <= 2) & (st1[:, 1] + st1[:, 3] > ED) & (st1[:, 2] <= 8 * st1[:, 3])
        cont[0] = False
        C = np.zeros_like(A)
        C[E:] = cont[lab1]
        z0 = E + ED
        n3, _, st3, _ = cv2.connectedComponentsWithStats(A[z0:z0 + n60].astype(np.uint8), connectivity=8)
        busy = np.zeros(L, bool)
        for i in range(1, n3):
            if st3[i, 2] < n100:                    # đường khung dài không tính
                busy[max(0, st3[i, 0] - n40):st3[i, 0] + st3[i, 2] + n40] = True
        n2, lab2, st2, _ = cv2.connectedComponentsWithStats(A2.astype(np.uint8), connectivity=8)
        mn2 = np.full(n2, 255, np.int32)
        np.minimum.at(mn2, lab2.ravel(), fl(g)[:Dm].ravel().astype(np.int32))
        along = (st2[:, 2] >= 2.5 * st2[:, 3]) & (st2[:, 2] >= n20)
        lone = np.array([not busy[st2[i, 0]:st2[i, 0] + st2[i, 2]].any() for i in range(n2)])
        cand = (((st2[:, 1] < E) & (st2[:, 1] + st2[:, 3] <= E + ED)) |
                ((st2[:, 1] + st2[:, 3] <= EB) & (mn2 >= 120)))
        cand[0] = False
        hitC = np.zeros(n2, bool)
        hitC[np.unique(lab2[C])] = True
        cand &= ~hitC
        # vệt dọc mép: chỉ xoá ở cột không bận (mẩu hoa văn bị mép cắt cũng trông như vệt dọc mép);
        # chấm / mẩu đứng riêng: xoá khi cả đoạn không bận
        Art = ((cand & along)[lab2] & ~busy[None, :]) | (cand & lone)[lab2]
        a0, a1 = (ext or {}).get(side, (0, 0))
        src = A & ~Art
        depth = np.zeros(L, int)
        for k in range(E, Dm - band):
            row = src[k:k + band].any(0)          # gộp vài hàng: chịu được khung hơi nghiêng
            for s, e in runs(row):
                if e - s < minrun:
                    continue
                s2 = 0 if s < max(0.05 * L, a0 + n15) else s
                e2 = L if e > min(0.95 * L, L - a1 - n15) else e
                seg = depth[s2:e2]
                seg[seg == 0] = k
        if not depth.any():
            info[side] = 0
            continue
        prot = np.zeros(L, bool)
        for i in np.nonzero(cont)[0]:
            x, w = st1[i, 0], st1[i, 2]
            prot[max(0, x - PP):x + w + PP] = True
        r = int(np.median(depth[depth > 0]))
        depth[depth > r + n30] = r                  # nét ngang dài trong tranh nằm sâu hơn khung chung
        filled = 0
        for s, e in runs(depth == 0):
            nbr = [d for d in ((depth[s - 1] if s > 0 else 0), (depth[e] if e < L else 0)) if d]
            if not nbr:
                continue
            if prot[max(0, s - p20):e + p20].any():
                prot[s:e] = True
                continue
            depth[s:e] = min(nbr)
            filled += int(e - s)
        depth[prot] = 0
        reg = np.arange(Dm)[:, None] < (depth - 2)[None, :]
        # dải sát mép: xoá giấy và vệt mép, giữ nét sẫm không phải vệt mép, bỏ qua cột bận
        zz = reg & (Art | ((np.arange(Dm)[:, None] < E) & ~(A2 & ~Art) & ~busy[None, :]))
        full = np.zeros((H, W) if side in ('top', 'bottom') else (W, H), bool)
        fz = full.copy()
        full[:Dm] = reg
        fz[:Dm] = zz
        if side == 'bottom':
            full, fz = full[::-1, :], fz[::-1, :]
        elif side == 'left':
            full, fz = full.T, fz.T
        elif side == 'right':
            full, fz = full[::-1, :].T, fz[::-1, :].T
        M |= full
        Z |= fz
        info[side] = dict(d=r, prot=int(prot.sum()), filled=filled)
    return M, Z, info


def margins(g, sc, spread=False):
    """Hai lượt dò khung (lượt 2 nối khung ra tới góc trang), rồi:
      - loang từ mép qua giấy: chỗ được nét đậm bao kín (trong bóng thoại / vật lấn ra lề) không phải lề;
      - vật thể lấn ra lề (mảng mực dài > OBJ_MIN) cùng phần nó bao kín không phải lề;
      - chốt chặn: chỗ có mật độ xám kiểu tram / mây / nét nhạt không phải lề (kèm đệm).
    Trả về (lề, dải xoá hẳn, thông tin)."""
    _, _, i1 = frame_margins(g, sc, spread)
    d = {k: (v['d'] if isinstance(v, dict) else 0) for k, v in i1.items()}
    ext = {'top': (d['left'], d['right']), 'bottom': (d['left'], d['right']),
           'left': (d['top'], d['bottom']), 'right': (d['top'], d['bottom'])}
    M, Z, info = frame_margins(g, sc, spread, ext=ext)
    h = g.copy()
    h[Z] = 255
    k5 = sc.K(5)
    barrier = cv2.dilate((h < 160).astype(np.uint8), np.ones((k5, k5), np.uint8)).astype(bool)
    free = M & ~barrier
    _, lab = cv2.connectedComponents(free.astype(np.uint8), connectivity=4)
    seeds = np.unique(lab[free & cv2.dilate(Z.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)])
    enclosed = free & ~np.isin(lab, seeds[seeds > 0])
    M &= ~enclosed
    # vật thể lấn ra lề (nắm tay, chữ tượng thanh, bóng thoại, nét tốc độ...): mảng mực chạm lề, dài > OBJ_MIN
    # → bỏ cả mảng lẫn phần nó bao kín khỏi lề: không nâng sáng, không xoá; chỉ dọn giấy xung quanh
    n, lab, st, _ = cv2.connectedComponentsWithStats((h < 160).astype(np.uint8), connectivity=8)
    hit = np.zeros(n, bool)
    hit[np.unique(lab[M])] = True
    big = hit & (np.maximum(st[:, 2], st[:, 3]) > sc.L(OBJ_MIN, 5))
    big[0] = False
    obj = big[lab]
    ff = np.pad((~obj).astype(np.uint8), 1, constant_values=1)       # viền 1 px quanh trang: loang từ mọi mép
    cv2.floodFill(ff, np.zeros((ff.shape[0] + 2, ff.shape[1] + 2), np.uint8), (0, 0), 2)   # ngoài vật thể = 2
    ff = ff[1:-1, 1:-1]
    objf = cv2.dilate((obj | (ff == 1)).astype(np.uint8), np.ones((k5, k5), np.uint8)).astype(bool)
    object_px = int((M & objf).sum())
    M &= ~objf
    k9 = sc.K(9)
    base = M & ~Z & ~cv2.dilate((g < 160).astype(np.uint8), np.ones((k9, k9), np.uint8)).astype(bool)
    gw = sc.K(GUARD_WIN)
    k = (gw, gw)
    f = cv2.blur((base & (g < 225)).astype(np.float32), k) / np.maximum(cv2.blur(base.astype(np.float32), k), 0.05)
    art = (f > GUARD_T) & base
    gf = g.astype(np.float32)
    gk = cv2.getGaussianKernel(9, 1.5)
    one = np.array([1.0])
    rough_y = cv2.blur(np.abs(gf - cv2.sepFilter2D(gf, -1, one, gk)), k)    # gồ ghề theo chiều dọc
    rough_x = cv2.blur(np.abs(gf - cv2.sepFilter2D(gf, -1, gk, one)), k)    # gồ ghề theo chiều ngang
    H, W = g.shape
    yy, xx = np.arange(H)[:, None], np.arange(W)[None, :]
    dv, dh = np.minimum(yy, H - 1 - yy), np.minimum(xx, W - 1 - xx)
    rough = np.where(dh <= dv, rough_y, rough_x)                              # dọc theo cạnh gần nhất
    art &= (np.minimum(dv, dh) >= sc.L(EDGE_BAND, 3)) | (rough > ROUGH_T)
    gp = sc.L(GUARD_PAD, 2)
    pk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * gp + 1, 2 * gp + 1))
    guard = cv2.dilate(art.astype(np.uint8), pk).astype(bool) & M
    info.update(enclosed_px=int(enclosed.sum()), object_px=object_px, guard_px=int(guard.sum()))
    return M & ~guard, Z & ~guard, info


def despeckle(g, sc, spread=False):
    """Dọn chấm xám còn lại sau làm trắng (thớ giấy, nhiễu JPEG, giấy tối sát mép, ô dán của nhóm dịch).
      - Dải sát mép / vệt mép scan trong lề: xoá hẳn.
      - Lề ngoài khung: nâng giấy về trắng, chỉ giữ nét đậm (< 200, kèm viền) và bỏ chấm đậm lẻ loi.
      - Trong khung: chỉ xoá thành phần cực nhạt (min ≥ 232), nhỏ (≤ 40 px), không nằm gần tram,
        trên nền trắng đều; mức xoá mềm dần theo nền nên nền xám nhạt không bị loang.
    Không bao giờ đụng nét đậm trong khung, thứ dính vào nét, tram, chấm vẽ tay (min < 232).
    Cỡ hạt nhiễu (≤ 40 / 150 / 25 px) giữ theo điểm ảnh: nhiễu JPEG tính theo điểm, không theo mm."""
    gf = g.astype(np.float32)
    M, Z, minfo = margins(g, sc, spread)
    # 1) lề: cùng đường cong đơn điệu như làm trắng, mức giấy đo cục bộ trên chính lề
    B = 60.0
    paper = M & ~Z & (g >= 215)
    sg = sc.F(12, 2.0)
    num = cv2.GaussianBlur(np.where(paper, gf, 0), (0, 0), sg)
    den = cv2.GaussianBlur(paper.astype(np.float32), (0, 0), sg)
    L = np.where(den > 0.05, num / np.maximum(den, 1e-6), 255.0)
    L = np.clip(L + 4, 225, 255)                # lấy hơi cao hơn trung bình để thớ giấy cũng thành trắng
    lifted = np.clip(np.rint(B + (gf - B) * (255 - B) / np.maximum(L - B, 1)), 0, 255)
    out = np.where(M & (g > B), lifted, gf).astype(np.uint8)
    out[Z] = 255
    # 2) thành phần nhạt (< 245)
    n, lab, st, _ = cv2.connectedComponentsWithStats((out < 245).astype(np.uint8), connectivity=8)
    lr = lab.ravel()
    mins = np.full(n, 255, np.int32)
    np.minimum.at(mins, lr, out.ravel().astype(np.int32))
    allM = np.ones(n, bool)
    np.logical_and.at(allM, lr, M.ravel())
    dust = allM & (mins >= 200) & (st[:, 4] <= 150)
    dust[0] = False
    # 3) trong khung: thớ giấy cực nhạt ở nền trắng đều, xa tram
    seed = (st[:, 4] <= 150) & (mins < 232)
    seed[0] = False
    k49 = sc.K(49)
    D = cv2.blur(seed[lab].astype(np.float32), (k49, k49))
    Dmax = np.zeros(n, np.float32)
    np.maximum.at(Dmax, lr, D.ravel())
    med = cv2.medianBlur(out, sc.K(9)).astype(np.float32)
    w = np.clip((med - 240) / 7, 0, 1)
    w[M] = 1
    wsum = np.zeros(n, np.float64)
    np.add.at(wsum, lr, w.ravel())
    wmean = wsum / np.maximum(st[:, 4], 1)
    grain = (mins >= 232) & (st[:, 4] <= 40) & (Dmax < 0.03) & (wmean >= 0.5)
    grain[0] = False
    erase = dust | grain
    keep = ~erase
    keep[0] = False
    near = cv2.dilate(keep[lab].astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    of = out.astype(np.float32)
    tgt = erase[lab] | (~near & (of >= 245))
    res = np.clip(np.rint(np.where(tgt, of + w * (255 - of), of)), 0, 255).astype(np.uint8)
    # 4) lề: chỉ giữ nét đậm (số trang, chữ) + viền; chấm đậm ≤ 25 px nằm trọn trong lề và cách
    #    mọi nét đậm khác xa là bụi → bỏ (cụm chấm như "…" thì giữ)
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats((out < 200).astype(np.uint8), connectivity=8)
    ok = st2[:, 4] >= 3
    ok[0] = False
    allM2 = np.ones(n2, bool)
    np.logical_and.at(allM2, lab2.ravel(), M.ravel())
    idx = np.nonzero(ok)[0]
    cen = st2[idx, :2] + st2[idx, 2:4] / 2.0
    far = sc.L(40, 5)
    lone = 0
    for j, i in enumerate(idx):
        if st2[i, 4] > 25 or not allM2[i]:
            continue
        d = np.hypot(*(cen - cen[j]).T)
        d[j] = 1e9
        if d.min() > far:
            ok[i] = False
            lone += 1
    keepM = cv2.dilate(ok[lab2].astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    wiped = M & ~keepM & ~Z & (out < 225)       # thứ "có màu" bị xoá trong lề: bụi, hoặc tram nếu dò lề sai
    edge = Z & (g < 225)                        # vệt mép scan bị xoá
    res[M & ~keepM] = 255
    info = dict(margin=minfo, margin_px=int(M.sum()), dust=int(dust.sum()), grain=int(grain.sum()),
                lone=lone, wiped_mid=int(wiped.sum()), edge_wiped=int(edge.sum()), changed=int((res != g).sum()))
    return res, info


# ================================================================ làm nét

SHARP_TARGET = 0.95     # độ nhoè mép mục tiêu (px ảnh ra)
SHARP_MAX = 1.5         # mức làm nét tối đa
SEAM_KEEP = 3           # tờ liền gáy: không làm nét trong ±3 px quanh đường ghép, mềm dần tới ±9 px


def edge_sigma(g):
    """Độ nhoè mép nét (px): coi mép mực–giấy là bậc thang bị nhoè Gauss σ, σ = C / (gmax·√(2π))."""
    f = g.astype(np.float32)
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3) / 8
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3) / 8
    mag = np.hypot(gx, gy)
    k9 = np.ones((9, 9), np.uint8)
    mx, mn = cv2.dilate(f, k9), cv2.erode(f, k9)
    C = mx - mn
    loc = (mag == cv2.dilate(mag, np.ones((3, 3), np.uint8))) & (C >= 140) & (mx >= 235) & (mn <= 110)
    s = mag[loc] / C[loc]
    s = s[s > 0]
    if len(s) < 300:
        return None, int(len(s))
    return float(1 / (np.median(s) * math.sqrt(2 * math.pi))), int(len(s))


def sharpen(g, sigma, amount, thr=2.0):
    """Unsharp mask bỏ dao động nhỏ (thớ giấy, nhiễu JPEG), kẹp trong [min, max] 3x3 của ảnh vào → không quầng."""
    f = g.astype(np.float32)
    d = f - cv2.GaussianBlur(f, (0, 0), sigma)
    d = np.sign(d) * np.maximum(np.abs(d) - thr, 0)
    k3 = np.ones((3, 3), np.uint8)
    s = np.minimum(np.maximum(f + amount * d, cv2.erode(f, k3)), cv2.dilate(f, k3))
    return np.clip(np.rint(s), 0, 255).astype(np.uint8)


def sharpen_auto(g, seam_mask=None):
    """Tự cân mức làm nét từng trang để mọi trang có cùng độ nhoè mép (đo ở cỡ ảnh ra, không phóng nên bán
    kính 1 px). Đường ghép tờ liền gáy giữ nguyên để vệt gáy không rõ thêm."""
    sg = 1.0
    s0, n = edge_sigma(g)
    info = dict(sigma=sg, edge_before=None if s0 is None else round(s0, 3), edges=n)
    if s0 is None or s0 <= SHARP_TARGET:
        info.update(amount=0.0, edge_after=info['edge_before'])
        return g, info

    def blur_of(a):
        return edge_sigma(sharpen(g, sg, a))[0] or 0.0
    lo, hi = 0.0, SHARP_MAX
    if blur_of(hi) > SHARP_TARGET:
        lo = hi
    else:
        for _ in range(6):
            a = (lo + hi) / 2
            if blur_of(a) > SHARP_TARGET:
                lo = a
            else:
                hi = a
    out = sharpen(g, sg, hi)
    if seam_mask is not None:
        dist = cv2.distanceTransform((~seam_mask).astype(np.uint8), cv2.DIST_L2, 3)
        wt = np.clip((dist - SEAM_KEEP) / 6, 0, 1)
        out = np.clip(np.rint(g + wt * (out.astype(np.float32) - g)), 0, 255).astype(np.uint8)
    s1 = edge_sigma(out)[0]
    info.update(amount=round(hi, 3), edge_after=None if s1 is None else round(s1, 3))
    return out, info


# ================================================================ 1 trang / 1 ảnh

def process_gray(g, sc, rec, inner=None, seam_cols=None):
    """Một trang (đã tách) hoặc một tờ giữ nguyên: làm trắng (nếu qua cổng) → dọn lề gáy → gọt vạch mép →
    dọn chấm → làm nét (3 bước cuối chỉ khi đã làm trắng). = prep.process_page bỏ xoay / phóng."""
    w, winfo = whiten(g, sc)
    rec['whiten'] = winfo
    if not winfo['ok']:
        return g.copy()
    if inner is not None:
        w, rec['clean'] = clean_inner(w, inner == 'L', sc)
    el = trim_edge_lines(w, sc)
    if el:
        rec['edge_lines'] = el
    w, rec['despeckle'] = despeckle(w, sc, spread=seam_cols is not None)
    seam_mask = None
    if seam_cols is not None:
        seam_mask = np.zeros(w.shape, bool)
        ys = np.arange(w.shape[0])
        for dx in (-1, 0):
            seam_mask[ys, np.clip(seam_cols + dx, 0, w.shape[1] - 1)] = True
    w, rec['sharpen'] = sharpen_auto(w, seam_mask)
    return w


def load_image(path):
    """Đọc ảnh -> (rgb, gray, số khung). Lớp trong suốt ghép lên nền trắng (như trình duyệt hiển thị)."""
    with Image.open(path) as im:
        frames = getattr(im, 'n_frames', 1)
        if frames > 1:
            return None, None, frames
        im.load()
        if im.mode in ('RGBA', 'LA', 'PA') or (im.mode == 'P' and 'transparency' in im.info):
            im = im.convert('RGBA')
            bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im)
        rgb = np.asarray(im.convert('RGB'))
    return rgb, cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), 1


def thumb(g, h=240):
    H, W = g.shape
    w = max(1, int(round(W * h / H)))
    return cv2.resize(g, (w, h), interpolation=cv2.INTER_AREA), h / H


def process_image(path, rule, doc, rec):
    """Xử lý 1 ảnh gốc. Trả về list kết quả theo thứ tự đọc: mảng xám (trang đã làm) hoặc None (= chép
    nguyên file gốc). rec ghi loại, quyết định, số đo; rec['_thumb'] (không lưu) cho ảnh lưới gáy."""
    rgb, g, frames = load_image(path)
    if rgb is None:
        rec['kind'] = 'dong'
        return [None]
    H, W = g.shape
    rec['size'] = [W, H]
    if rule == 'bo_qua':
        rec['kind'] = 'bo_qua'
        return [None]
    ar = W / H
    if H / W > TALL_AR or ar > DOUBLE_AR[1]:
        rec['kind'] = 'khac'          # dải webtoon / băng ngang
        return [None]
    if H < MIN_H:
        rec['kind'] = 'nho'
        return [None]
    P = paper_level(g)
    cf = color_coherent(rgb, g, P)
    rec['mau'] = round(cf, 4)
    if cf > COLOR_T:
        rec['kind'] = 'mau'
        return [None]
    del rgb
    sc = Thang(H / REF_H)
    rec['u'] = round(sc.u, 3)
    if ar < DOUBLE_AR[0]:
        rec['kind'] = 'don'
        return [process_gray(g, sc, rec)]
    a = analyse_double(g, P, sc)
    if a is None:
        rec['kind'] = 'rong'          # ảnh ngang không thấy gáy: làm như 1 trang
        return [process_gray(g, sc, rec)]
    rec['kind'] = 'doi'
    rec['seam'] = a['info']
    g2, c0, c1, seam = a['g'], a['c0'], a['c1'], a['seam']
    tb, k = thumb(g)
    auto_keep = rule is None and a['strong']      # tranh vắt qua gáy rõ: giữ nguyên, không đụng gáy
    keep = rule in ('giu_nguyen', 'khong_ghep') or auto_keep
    if not keep:
        # Cắt thẳng đứng (không cắt chéo để khỏi xô lệch dòng); phần lõi gáy nghiêng còn sót ở mép trong
        # được tô màu giấy theo từng dòng.
        rec['decision'] = 'tach'
        ext_l = int(c0.max())
        left = g2[:, :ext_l].copy()
        left[np.arange(ext_l)[None, :] >= c0[:, None]] = P
        x0 = int(c1.min() + 1)
        right = g2[:, x0:].copy()
        right[np.arange(x0, W)[None, :] <= c1[:, None]] = P
        halves = (('R', right, 'L'), ('L', left, 'R'))
        if doc == 'trai-truoc':
            halves = halves[::-1]
        outs, rec['pages'] = [], []
        for side, img, inner in halves:
            sub = dict(side=side)
            outs.append(process_gray(img, sc, sub, inner=inner))
            rec['pages'].append(sub)
        rec['_thumb'] = (tb, [(float(np.median(c0)) * k, 'cut'), (float(np.median(c1)) * k, 'cut')],
                         'NGHI lien gay' if a['nghi'] else 'tach', a['nghi'])
        return outs
    # tờ liền gáy giữ 1 ảnh: bỏ khe gáy khi đo chắc (khe rộng / khe / vạch mép + cổng không thấy tranh)
    ys = np.arange(H)
    joined = False
    if rule == 'giu_nguyen':
        cc0, cc1, kind = c0, c1, a['info']['kind']
        wg = wide_gap(g2, P, seam, sc)
        if wg is not None and min(wg[2]['bands_l'], wg[2]['bands_r']) >= 8:
            cc0, cc1, kind = wg[0], wg[1], 'khe_rong'
            rec['seam']['wide'] = wg[2]
        ok, gate = core_is_gap(g2, P, cc0, cc1, sc)
        rec['seam']['gate'] = gate
        if kind != 'none' and ok:
            canvas, seam_cols = join_spread(g2, cc0, cc1, P)
            joined = True
            rec['seam']['removed'] = int(np.round(np.median(cc1 - cc0 + 1)))
    if not joined:
        canvas, seam_cols = g2, np.rint(seam_x(seam, ys, H)).astype(int)
    rec['decision'] = 'giu_ghep' if joined else ('giu_tu_dong' if auto_keep else 'giu')
    sub = dict(side='S')
    out = process_gray(canvas, sc, sub, seam_cols=seam_cols)
    rec['pages'] = [sub]
    rec['_thumb'] = (tb, [(float(seam_x(seam, H / 2, H)) * k, 'keep')],
                     'GIU (ghep)' if joined else ('GIU tu dong' if auto_keep else 'GIU'), False)
    return [out]


# ================================================================ thư viện: truyện / chương / cấu hình

def has_images(d):
    try:
        return any(e.is_file() and os.path.splitext(e.name)[1].lower() in IMG_EXTS for e in os.scandir(d))
    except OSError:
        return False


def list_images(d):
    try:
        names = [e.name for e in os.scandir(d) if e.is_file() and os.path.splitext(e.name)[1].lower() in IMG_EXTS]
    except OSError:
        return []
    return sorted(names, key=natkey)


def series_chapters(series):
    """Chương của 1 truyện như reader thấy: folder con có ảnh (phẳng) hoặc arc/chương. Bỏ folder chấm-đầu."""
    out = []
    try:
        subs = sorted((d for d in os.scandir(series) if d.is_dir() and not d.name.startswith('.')),
                      key=lambda d: natkey(d.name))
    except OSError:
        return out
    for d in subs:
        if has_images(d.path) or (Path(d.path) / CONF_NAME).exists():
            out.append(d.name)
            continue
        try:
            chs = sorted((c for c in os.scandir(d.path) if c.is_dir() and not c.name.startswith('.')),
                         key=lambda c: natkey(c.name))
        except OSError:
            continue
        out += [f"{d.name}/{c.name}" for c in chs if has_images(c.path) or (Path(c.path) / CONF_NAME).exists()]
    return out


def resolve_target(target):
    """-> (folder truyện, [chương rel] hoặc None = cả truyện, lỗi)."""
    t = target.resolve()
    if not t.is_dir():
        return None, None, f"không thấy thư mục: {t}"
    try:
        rel = t.relative_to(DOWNLOADS.resolve())
        parts = rel.parts
    except ValueError:
        parts = None
    if parts is not None:
        if len(parts) == 0:
            return None, None, "hãy chọn 1 folder TRUYỆN (hoặc 1 chương), không chạy cả thư viện downloads\\"
        series = DOWNLOADS.resolve() / parts[0]
        if any(p.startswith('.') for p in parts):
            return None, None, "không chạy trong thư mục chấm-đầu (.lam-sach, .pdf-goc...)"
        if len(parts) == 1:
            # ảnh thẳng trong folder truyện (cover.jpg) không phải chương — chương là folder con có ảnh
            return series, None, None
        sub = "/".join(parts[1:])
        chs = series_chapters(series)
        if sub in chs:
            return series, [sub], None
        chs = [c for c in chs if c.startswith(sub + "/")]
        return (series, chs, None) if chs else (None, None, f"không thấy chương nào trong {t}")
    # ngoài downloads: có folder chương con = folder truyện, không thì folder có ảnh = 1 chương
    if series_chapters(t):
        return t, None, None
    if has_images(t) or (t / CONF_NAME).exists():
        return t.parent, [t.name], None
    return None, None, f"không thấy chương nào trong {t}"


def win(rel):
    return rel.replace('/', '\\')


def tool_path(series, rel):
    """<truyện>/<rel> (rel = ORIG_DIR / REVIEW_DIR / SERIES_CONF). Truyện còn kiểu cũ chưa gom (chỉ --dry-run /
    --thu gặp: lần chạy thật gom trước khi làm) -> trả chỗ cũ để vẫn đọc được."""
    new = series / rel
    if not new.exists():
        for old, nw in LEGACY:
            if nw == rel and (series / old).exists():
                return series / old
    return new


def merge_dir(src, dst):
    """Chuyển thư mục src vào dst (dst đã có thì gộp từng mục). Trả về số mục không chuyển được (trùng / khoá)."""
    if not dst.exists():
        return 0 if move_dir(src, dst) else 1
    left = 0
    for e in list(src.iterdir()):
        t = dst / e.name
        if e.is_dir() and t.is_dir():
            left += merge_dir(e, t)
        elif t.exists():
            left += 1
        else:
            try:
                os.replace(e, t)
            except OSError:
                left += 1
    try:
        src.rmdir()
    except OSError:
        pass
    return left


def migrate_legacy(series):
    """Gom đồ của bản đầu (.goc-lam-sach, .lam-sach-soat, .lam-sach.json, .lam-sach-tmp rải ở folder truyện)
    vào WORK_DIR. Chạy sau khi giữ khoá, TRƯỚC recover (dở dang trong tmp cũ cũng được làm nốt)."""
    notes = []
    for old, new in LEGACY:
        o, n = series / old, series / new
        if not o.exists():
            continue
        n.parent.mkdir(parents=True, exist_ok=True)
        if o.is_file():
            if n.exists():
                notes.append(f"! có cả {old} và {win(new)} — dùng {win(new)}, {old} để nguyên (xoá tay nếu thừa)")
                continue
            os.replace(o, n)
            left = 0
        else:
            left = merge_dir(o, n)
        notes.append(f"đã gom {old} -> {win(new)}" + (f" ({left} mục trùng tên còn lại ở {old})" if left else ""))
    t = series / LEGACY_TMP
    if t.is_dir():
        (t / 'lock.json').unlink(missing_ok=True)
        if merge_dir(t, series / TMP_DIR):
            notes.append(f"! {LEGACY_TMP} còn mục trùng tên với {win(TMP_DIR)} — để nguyên, xem tay")
    return notes


def prune_empty(d):
    """Xoá thư mục RỖNG từ dưới lên (cả d nếu rỗng); không bao giờ xoá file."""
    if not d.is_dir():
        return
    for p in sorted((x for x in d.rglob('*') if x.is_dir()), key=lambda x: len(x.parts), reverse=True):
        try:
            p.rmdir()
        except OSError:
            pass
    try:
        d.rmdir()
    except OSError:
        pass


def load_conf(series):
    p = tool_path(series, SERIES_CONF)
    conf = json.loads(json.dumps(CONF_TEMPLATE))
    if p.exists():
        try:
            user = json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError) as e:
            raise SystemExit(f"! File cấu hình lỗi, sửa lại rồi chạy: {p}\n  {e}")
        for k, v in user.items():
            if k in RULE_KEYS and not isinstance(v, dict):
                raise SystemExit(f"! {p}: mục '{k}' phải là {{\"tên chương\": [\"tên ảnh\", ...]}}")
            conf[k] = v
    if conf.get('doc') not in ('phai-truoc', 'trai-truoc'):
        raise SystemExit(f"! {p}: 'doc' chỉ nhận 'phai-truoc' hoặc 'trai-truoc'")
    if not isinstance(conf.get('phong'), bool):
        raise SystemExit(f"! {p}: 'phong' chỉ nhận true hoặc false")
    df = dict(CONF_TEMPLATE['doi_font'])
    if not isinstance(conf.get('doi_font'), dict):
        raise SystemExit(f"! {p}: 'doi_font' phải là {{\"bat\": false, \"font\": \"...\", ...}}")
    df.update(conf['doi_font'])
    if not isinstance(df['bat'], bool):
        raise SystemExit(f"! {p}: 'doi_font.bat' chỉ nhận true hoặc false")
    for k in ('nguon', 'font'):
        if not isinstance(df[k], str) or not df[k].strip():
            raise SystemExit(f"! {p}: 'doi_font.{k}' phải là tên font (vd \"CC Wild Words Roman\") hoặc đường dẫn file font")
    for k in ('duyet', 'bo'):
        if not (isinstance(df[k], dict) and all(isinstance(v, list) for v in df[k].values())):
            raise SystemExit(f"! {p}: 'doi_font.{k}' phải là {{\"tên chương\": [\"<ảnh>:<chữ>\", ...]}}")
    if not (isinstance(df['sua'], dict) and all(isinstance(v, dict) for v in df['sua'].values())):
        raise SystemExit(f"! {p}: 'doi_font.sua' phải là {{\"tên chương\": {{\"<ảnh>:<chữ>\": \"chữ mới\"}}}}")
    conf['doi_font'] = df
    return conf


def rule_for(conf, rel, name):
    stem = os.path.splitext(name)[0]
    for key in RULE_KEYS:
        lst = list(conf.get(key, {}).get(rel, [])) + list(conf.get(key, {}).get('*', []))
        if name in lst or stem in lst:
            return key
    return None


def safe_name(rel):
    return rel.replace('/', ' - ')


def joined_pairs(series_name, rel):
    """Số cặp trang ghép tay trong reader của chương (tên ảnh đổi -> cặp cũ mất tác dụng)."""
    try:
        sp = json.loads(SPREADS_FILE.read_text(encoding='utf-8'))
        return len(sp.get(series_name, {}).get(rel, []))
    except (OSError, ValueError, AttributeError):
        return 0


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def read_marker(ch_dir):
    try:
        return json.loads((ch_dir / CONF_NAME).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def move_dir(src, dst, tries=6):
    """Đổi tên thư mục (cùng ổ đĩa = tức thì). Windows khoá thư mục khi có file đang mở (reader đang gửi ảnh,
    Explorer tạo ảnh thu nhỏ) -> thử lại vài lần."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    for i in range(tries):
        try:
            os.replace(src, dst)
            return True
        except OSError:
            if i == tries - 1:
                return False
            time.sleep(1.0)
    return False


def recover(series):
    """Dọn dở dang của lần chạy bị ngắt (chỗ chương bị trống giữa 2 lần đổi tên):
      - chương mới đã ghi đủ (dấu hoan_tat) -> đưa vào chỗ;
      - --tra-goc bị ngắt (bản sạch đã ra _cu/) -> đưa bản gốc về; mất bản gốc thì trả bản sạch lại.
    Còn lại trong .lam-sach\\tmp (chương ghi dở, bản sạch cũ chờ xoá) -> xoá."""
    tmp = series / TMP_DIR
    if not tmp.is_dir():
        return []
    notes = []
    # bản sạch mới (lượt 1) xét trước bản cũ trong _cu/ (lượt 2): --lam-lai bị ngắt thì bản mới thắng
    marks = sorted(tmp.rglob(CONF_NAME), key=lambda p: (p.relative_to(tmp).parts[0] == '_cu', str(p)))
    for mk in marks:
        d = mk.parent
        rel_parts = d.relative_to(tmp).parts
        if not rel_parts:
            continue
        m = read_marker(d)
        if rel_parts[0] == '_cu':
            rel_parts = rel_parts[1:]
            dst = series.joinpath(*rel_parts)
            orig = series / ORIG_DIR / Path(*rel_parts)
            if rel_parts and not dst.exists():
                if orig.is_dir() and move_dir(orig, dst):
                    notes.append(f"làm nốt --tra-goc bị ngắt: đã trả bản gốc {'/'.join(rel_parts)}")
                elif move_dir(d, dst):
                    notes.append(f"lần trước bị ngắt: đã đưa lại bản sạch {'/'.join(rel_parts)}")
            continue
        dst = series.joinpath(*rel_parts)
        if m and m.get('hoan_tat') and not dst.exists():
            if move_dir(d, dst):
                notes.append(f"làm nốt lần trước bị ngắt: đã đưa {'/'.join(rel_parts)} vào chỗ")
    for p in list(tmp.iterdir()):
        if p.name == 'lock.json':
            continue
        shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink(missing_ok=True)
    return notes


def _pid_alive(pid):
    if pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259                                      # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def take_lock(series):
    lk = series / TMP_DIR / 'lock.json'
    if lk.exists():
        try:
            old = json.loads(lk.read_text(encoding='utf-8'))
            if old.get('pid') != os.getpid() and _pid_alive(int(old.get('pid', 0))):
                return False
        except (OSError, ValueError):
            pass
    lk.parent.mkdir(parents=True, exist_ok=True)
    lk.write_text(json.dumps({'pid': os.getpid(), 'time': time.strftime('%Y-%m-%d %H:%M:%S')}), encoding='utf-8')
    return True


def drop_lock(series):
    tmp = series / TMP_DIR
    (tmp / 'lock.json').unlink(missing_ok=True)
    # chỉ còn thư mục rỗng (vd _cu/ sau --lam-lai) -> xoá hẳn; còn file = dở dang -> để lần sau recover
    if tmp.is_dir() and not any(p.is_file() for p in tmp.rglob('*')):
        shutil.rmtree(tmp, ignore_errors=True)
    prune_empty(series / WORK_DIR)      # --tra-goc hết chương -> goc/ (và arc con) rỗng thì bỏ luôn


def low_priority():
    """1 tiến trình, OpenCV 2 luồng, ưu tiên thấp: chạy trên server mà reader vẫn mượt."""
    cv2.setNumThreads(2)
    if os.name == 'nt':
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)    # BELOW_NORMAL_PRIORITY_CLASS
        except Exception:
            pass


# ================================================================ ảnh soát

def gutter_sheet(items, path, title):
    """Lưới tờ đôi của 1 chương: đường cắt đỏ (tách) / xanh (giữ), nhãn NGHI cam = tool nghi tranh liền gáy."""
    if not items:
        return
    tiles = []
    for label, (tb, lines, tag, nghi) in items:
        im = Image.fromarray(tb).convert('RGB')
        d = ImageDraw.Draw(im)
        for x, kind in lines:
            d.line([(x, 0), (x, im.height)], fill=(220, 0, 0) if kind == 'cut' else (0, 160, 0), width=1)
        cap = Image.new('RGB', (im.width, 18), (255, 255, 255))
        dc = ImageDraw.Draw(cap)
        dc.text((3, 3), f"{label}  {tag}", fill=(230, 110, 0) if nghi else
                ((0, 130, 0) if tag.startswith('GIU') else (40, 40, 40)))
        t = Image.new('RGB', (im.width, im.height + 18), (255, 255, 255))
        t.paste(im, (0, 0))
        t.paste(cap, (0, im.height))
        tiles.append(t)
    maxw = 1700
    rows, row, w = [], [], 0
    for t in tiles:
        if row and w + t.width + 6 > maxw:
            rows.append(row)
            row, w = [], 0
        row.append(t)
        w += t.width + 6
    rows.append(row)
    W = max(sum(t.width + 6 for t in r) for r in rows)
    H = 22 + sum(max(t.height for t in r) + 6 for r in rows)
    sheet = Image.new('RGB', (W, H), (90, 90, 90))
    ImageDraw.Draw(sheet).text((4, 4), title, fill=(255, 255, 255))
    y = 22
    for r in rows:
        x = 0
        for t in r:
            sheet.paste(t, (x, y))
            x += t.width + 6
        y += max(t.height for t in r) + 6
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=82)


# ================================================================ phóng AI trang thấp

def save_gray(arr, dst, lossy):
    im = Image.fromarray(arr)
    if lossy:
        im.save(dst, 'JPEG', quality=92, optimize=True)
    else:
        im.save(dst, 'PNG', compress_level=6)


def phong_dir():
    """Thư mục tạm cho Real-ESRGAN (<tạm>/vao, <tạm>/ra). Exe SẬP (0xC0000409) khi đường dẫn có dấu tiếng
    Việt -> chọn chỗ đường dẫn thuần ASCII (thư mục tạm của Windows, không thì .reader-meta), tên ảnh = số."""
    for base in (Path(tempfile.gettempdir()), BASE_DIR / ".reader-meta"):
        if str(base).isascii():
            base.mkdir(parents=True, exist_ok=True)
            d = Path(tempfile.mkdtemp(prefix='lam-sach-phong-', dir=base))
            (d / 'vao').mkdir()
            (d / 'ra').mkdir()
            return d
    return None


def esrgan_dir(src, dst, n):
    """1 lần gọi Real-ESRGAN cho cả thư mục PNG. Exe trả mã 0 cả khi lỗi -> người gọi kiểm từng ảnh ra.
    Trả về câu lỗi hoặc None."""
    exe = Path(os.environ.get('LAM_SACH_ESRGAN') or ESR_EXE)
    if not exe.is_file():
        return f"không thấy {exe}"
    cmd = [str(exe), '-i', str(src), '-o', str(dst), '-m', str(exe.parent / 'models'),
           '-n', ESR_MODEL, '-s', str(PHONG_SCALE), '-f', 'png', '-t', '200']    # tile 200: an toàn VRAM 4 GB
    try:
        # ưu tiên thấp kế thừa từ tiến trình này; không bật cửa sổ console (khi chạy qua bot / pythonw)
        r = subprocess.run(cmd, capture_output=True, timeout=60 + 20 * n,
                           creationflags=0x08000000 if os.name == 'nt' else 0)
    except subprocess.TimeoutExpired:
        return "quá giờ (GPU bận hoặc máy không có GPU)"
    except OSError as e:
        return f"không chạy được {exe.name}: {e}"
    if not any(dst.iterdir()):
        msg = [ln.strip() for ln in r.stderr.decode('utf-8', 'replace').splitlines()
               if ln.strip() and not ln.strip().endswith('%')]
        return f"không ra ảnh nào (mã {r.returncode})" + (f": {msg[-1][:120]}" if msg else "")
    return None


def phong_ai(pdir, keys):
    """Phóng AI ảnh <pdir>/vao/<key>.png -> {key: ảnh xám PHONG_SCALE x, hoặc None nếu trang đó hỏng}, lỗi."""
    err = esrgan_dir(pdir / 'vao', pdir / 'ra', len(keys))
    got = {}
    for k in keys:
        got[k] = None
        if err:
            continue
        try:
            with Image.open(pdir / 'vao' / f"{k}.png") as im:
                want = (im.width * PHONG_SCALE, im.height * PHONG_SCALE)
            with Image.open(pdir / 'ra' / f"{k}.png") as im:
                if im.size == want:
                    got[k] = np.asarray(im.convert('L'))    # exe ra RGB lệch kênh vài chục mức -> về xám
        except Exception:
            pass
    n_ok = sum(v is not None for v in got.values())
    if not err and n_ok < len(keys):
        err = f"{len(keys) - n_ok} trang không ra ảnh"
    return got, err


# ================================================================ đổi chữ lệch font (doi_font.py)

def font_engine(conf):
    """-> (DoiFont, mô tả) hoặc (None, lỗi). Chỉ nạp doi_font khi cần (làm sạch thường không đụng tới)."""
    try:
        import doi_font
    except ImportError as e:
        return None, f"không nạp được doi_font.py ({e})"
    df = conf['doi_font']
    src, dst = doi_font.find_font(df['nguon']), doi_font.find_font(df['font'])
    if src is None:
        return None, f"không thấy font chữ lệch \"{df['nguon']}\" (doi_font.nguon trong {win(SERIES_CONF)})"
    if dst is None:
        return None, (f"không thấy font \"{df['font']}\" trên máy này — cài font (chuột phải file font > Install) "
                      f"hoặc ghi đường dẫn file font vào doi_font.font trong {win(SERIES_CONF)}")
    try:
        return doi_font.DoiFont(src, dst), f"\"{df['nguon']}\" -> \"{df['font']}\" ({dst})"
    except Exception as e:
        return None, f"không mở được font: {e}"


def font_page(fe, g, rules, name, out_dir, title, apply):
    """Dò chữ lệch font 1 trang xám; apply = đổi các dòng được đổi, không thì chỉ xem trước. Trang có chữ lệch font
    -> ảnh trước|sau vào out_dir. -> (ảnh mới hoặc None = không đổi gì, dòng danh sách, [dòng đã đổi] cho dấu,
    [khoá dòng chưa đổi cần soát])."""
    import doi_font
    page = fe.plan(g, rules, os.path.splitext(name)[0])
    if not page.lines:
        return None, [], [], []
    new = fe.render(page) if apply and any(d['ap'] for d in page.lines) else None
    after = (g if new is None else new) if apply else fe.render(page, preview=True)
    doi_font.sheet(g, after, page, out_dir / f"{os.path.splitext(name)[0]}.jpg", title)
    done = [dict(n=d['n'], doc=d['doc'], moi=d['moi'], kieu=d['kieu'], box=list(d['box']))
            for d in page.lines if d['ap']] if apply else []
    pend = [d['khoa'] for d in page.lines if not d['ap'] and d['trang_thai'] != 'bo']
    return new, doi_font.list_rows(name, page, applied_mode=apply), done, pend


def font_list(out_dir, rel, conf, rows, pend, apply):
    """<truyện>/.lam-sach/soat/doi-font/<chương>/danh-sach.txt: từng dòng + cách duyệt / sửa / bỏ."""
    df = conf['doi_font']
    ex = pend[0] if pend else rows[0].split('"')[1]
    txt = [f"Đổi chữ lệch font \"{df['nguon']}\" -> \"{df['font']}\"   ({time.strftime('%Y-%m-%d %H:%M')}, "
           f"{'--doi-font' if apply else '--soat-font'})",
           f"Chương: {rel}",
           "Ảnh trước|sau từng trang: cùng folder (bên trước: khung xanh = đổi, cam = chưa đổi / cần soát, xám = bỏ; "
           "#n = số dòng bên dưới).",
           "ĐÃ ĐỔI / CHƯA ĐỔI = kết quả lần chạy này." if apply else
           "TỰ = --doi-font đổi luôn; SOÁT = chỉ đổi khi duyệt; DUYỆT / SỬA / BỎ = theo cấu hình. "
           "Ảnh bên sau = xem trước như khi duyệt hết.",
           "", *rows, "",
           f"Duyệt / sửa / giữ nguyên 1 dòng: chép khoá (chuỗi trong ngoặc kép) vào {win(SERIES_CONF)}, "
           f"mục \"doi_font\", vd:",
           f'  "doi_font": {{"duyet": {{"{rel}": ["{ex}"]}},            <- đổi đúng như ảnh xem trước',
           f'               "sua":   {{"{rel}": {{"{ex}": "CHỮ MỚI"}}}},  <- đổi thành chữ ghi ở đây',
           f'               "bo":    {{"{rel}": ["{ex}"]}}}}             <- giữ nguyên chữ cũ',
           "rồi chạy lại với --doi-font (dòng đã đổi không bị đổi lại). Bỏ hết đổi font của chương: --lam-lai "
           "(làm sạch lại từ bản gốc, \"bat\": false)."]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'danh-sach.txt').write_text('\n'.join(txt) + '\n', encoding='utf-8')


def font_summary(r, rel, apply):
    if not r['dong']:
        return "không thấy chữ lệch font"
    s = f"{r['dong']} dòng chữ lệch font ở {r['trang']} trang"
    if apply:
        s += f" — đã đổi {r['doi']} dòng ({r['trang_doi']} trang)"
    if r['cho']:
        s += f", {r['cho']} dòng {'chưa đổi, cần soát' if apply else 'cần soát'}"
    return s + f" — xem {win(FONT_REVIEW)}\\{safe_name(rel)}\\danh-sach.txt"


def write_page(p, arr):
    """Ghi đè 1 ảnh trong chương: ghi file tạm cạnh nó (đuôi lạ, reader không thấy), đọc lại kiểm, rồi đổi tên."""
    tmp = p.with_name(p.name + '.doi-font-tmp')
    try:
        im = Image.fromarray(arr)
        if p.suffix.lower() in LOSSY_EXTS:
            im.save(tmp, 'JPEG', quality=92, optimize=True)
        else:
            im.save(tmp, 'PNG', compress_level=6)
        with Image.open(tmp) as chk:
            chk.verify()
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return f"ghi lỗi: {e}"
    for i in range(6):
        try:
            os.replace(tmp, p)
            return None
        except OSError:
            if i < 5:
                time.sleep(1.0)
    tmp.unlink(missing_ok=True)
    return "ảnh đang bị khoá (reader/Explorer đang mở?) — chạy lại sau"


def write_marker(ch, m):
    tmp = ch / (CONF_NAME + '.tmp')
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1, default=_json_default), encoding='utf-8')
    os.replace(tmp, ch / CONF_NAME)


def font_chapter(series, rel, conf, fe, apply, progress):
    """--soat-font / --doi-font cho 1 chương ĐÃ làm sạch: dò từng trang xám (PNG/JPG). apply = ghi đè trang có dòng
    được đổi + ghi vào dấu .lam-sach.json; không thì chỉ ra ảnh soát. -> dict tóm tắt."""
    import doi_font
    t0 = time.time()
    ch = series.joinpath(*rel.split('/'))
    rules = doi_font.page_rules(conf['doi_font'], rel)
    out_dir = series / FONT_REVIEW / safe_name(rel)
    shutil.rmtree(out_dir, ignore_errors=True)
    for p in ch.glob('*.doi-font-tmp'):         # lần trước bị ngắt giữa lúc ghi
        p.unlink(missing_ok=True)
    names = list_images(ch)
    rows, done, pend, errs, n_pages = [], {}, [], [], 0
    for i, name in enumerate(names, 1):
        progress(i, len(names), name)
        p = ch / name
        if p.suffix.lower() not in ('.png', '.jpg', '.jpeg'):
            continue
        try:
            with Image.open(p) as im:
                if im.mode != 'L':
                    continue                     # trang màu / ảnh chép nguyên
                g = np.asarray(im).copy()
            new, r, dn, pk = font_page(fe, g, rules, name, out_dir, f"{series.name} / {rel} / {name}", apply)
        except Exception as e:
            errs.append(f"{name}: {type(e).__name__}: {e}")
            continue
        rows += r
        pend += pk
        n_pages += bool(r)
        if new is not None:
            e = write_page(p, new)
            if e:
                errs.append(f"{name}: {e}")
            else:
                done[name] = dn
    if rows:
        font_list(out_dir, rel, conf, rows, pend, apply)
    if done:
        m = read_marker(ch) or {}
        f = m.setdefault('doi_font', {})
        f.update(nguon=conf['doi_font']['nguon'], font=conf['doi_font']['font'],
                 time=time.strftime('%Y-%m-%d %H:%M:%S'), cho_soat=len(pend))
        tr = f.setdefault('trang', {})
        for name, dn in done.items():
            tr[name] = tr.get(name, []) + dn
        write_marker(ch, m)
    return dict(dong=len(rows), trang=n_pages, doi=sum(len(v) for v in done.values()), trang_doi=len(done),
                cho=len(pend), loi=errs, secs=time.time() - t0)


def run_font(series, chapters, conf, fe, apply):
    """--soat-font (apply=False) / phần đổi tại chỗ của --doi-font, cho các chương đã làm sạch. -> 1 nếu có lỗi."""
    bad = False
    print()
    for ci, rel in enumerate(chapters, 1):
        ch = series.joinpath(*rel.split('/'))
        head = f"[{'đổi font' if apply else 'soát font'} {ci}/{len(chapters)}] {rel}"
        if not (ch / CONF_NAME).exists():
            print(f"{head}: chưa làm sạch — bỏ qua (đổi font chạy trên trang đã làm sạch)")
            continue

        def progress(i, n, name, head=head):
            print(f"\r{head}: ảnh {i}/{n} {name}"[:110].ljust(112), end='', flush=True)
        r = font_chapter(series, rel, conf, fe, apply, progress)
        print("\r" + " " * 112 + "\r", end='')
        print(f"{head}: {font_summary(r, rel, apply)}  ({r['secs']:.0f}s)")
        for e in r['loi']:
            print(f"    ! lỗi (trang giữ nguyên) {e}")
        bad |= bool(r['loi'])
    if not apply:
        print(f"\nThư viện giữ nguyên. Ảnh trước|sau + danh sách: {series / FONT_REVIEW}")
    return 1 if bad else 0


# ================================================================ 1 chương

def chapter_plan(series, rel, redo, restore):
    """Trạng thái 1 chương -> dict(status, src, note). status: moi / da_lam / lam_lai / tra_goc / loi."""
    ch = series.joinpath(*rel.split('/'))
    orig = tool_path(series, ORIG_DIR) / Path(*rel.split('/'))
    mk = ch / CONF_NAME
    if mk.exists():
        if not (redo or restore):
            return dict(status='da_lam', src=orig)
        if not orig.is_dir():
            return dict(status='loi', note=f"không còn bản gốc ở {win(ORIG_DIR)}\\{safe_name(rel)} (đã xoá?)")
        return dict(status='tra_goc' if restore else 'lam_lai', src=orig)
    if restore:
        return dict(status='bo', note='chưa làm sạch')
    if orig.exists():
        return dict(status='loi', note=f"đã có {win(ORIG_DIR)}\\{safe_name(rel)} mà chương chưa có dấu — "
                                       f"xoá/đổi tên folder đó rồi chạy lại")
    try:
        bad = [e.name for e in os.scandir(ch) if e.name.endswith('.bad')]
        subdirs = [e.name for e in os.scandir(ch) if e.is_dir()]
    except OSError as e:
        return dict(status='loi', note=str(e))
    if bad:
        return dict(status='loi', note=f"có {len(bad)} ảnh hỏng đang cách ly (.bad) — tải bù trước")
    if subdirs:
        return dict(status='loi', note=f"có thư mục con ({', '.join(subdirs[:3])}) — chưa hỗ trợ")
    return dict(status='moi', src=ch)


def restore_chapter(series, rel):
    ch = series.joinpath(*rel.split('/'))
    orig = series / ORIG_DIR / Path(*rel.split('/'))
    old = series / TMP_DIR / '_cu' / Path(*rel.split('/'))
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
    if not move_dir(ch, old):
        return "chương đang bị khoá (reader/Explorer đang mở ảnh?) — chạy lại sau"
    if not move_dir(orig, ch):
        move_dir(old, ch)
        return "không đưa được bản gốc về chỗ — đã trả bản sạch lại như cũ"
    shutil.rmtree(old, ignore_errors=True)
    return None


def process_chapter(series, rel, plan, conf, doc, progress, fe=None):
    """Làm 1 chương vào .lam-sach\\tmp rồi đổi chỗ. fe = DoiFont: đổi chữ lệch font ở bước cuối mỗi trang.
    Trả về dict tóm tắt (có 'loi' nếu hỏng)."""
    t0 = time.time()
    ch = series.joinpath(*rel.split('/'))
    orig = series / ORIG_DIR / Path(*rel.split('/'))
    src = plan['src']
    tmp = series / TMP_DIR / Path(*rel.split('/'))
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    names = list_images(src)
    fnt = None
    if fe is not None:
        import doi_font
        fnt = dict(rules=doi_font.page_rules(conf['doi_font'], rel), dir=series / FONT_REVIEW / safe_name(rel),
                   rows=[], done={}, pend=[], loi=[], trang=0)
        shutil.rmtree(fnt['dir'], ignore_errors=True)

    def fix_font(arr, name):
        """Bước cuối mỗi trang xám (sau phóng AI): đổi chữ lệch font nếu bật."""
        if fnt is None:
            return arr
        try:
            new, r, dn, pk = font_page(fe, arr, fnt['rules'], name, fnt['dir'], f"{series.name} / {rel} / {name}", True)
        except Exception as e:
            fnt['loi'].append(f"{name}: {type(e).__name__}: {e}")
            return arr
        fnt['rows'] += r
        fnt['pend'] += pk
        fnt['trang'] += bool(r)
        if new is None:
            return arr
        fnt['done'][name] = dn
        return new

    # file phụ (.done, .source.json...) lấy ở chương hiện tại (mới nhất), trừ dấu của tool
    extras = [e for e in os.scandir(ch) if e.is_file() and e.name != CONF_NAME and
              os.path.splitext(e.name)[1].lower() not in IMG_EXTS]
    width = max(3, len(str(2 * len(names))))
    recs, thumbs, outs_all = [], [], []
    n = 0
    # trang thấp chờ phóng AI: ghi PNG không mất dữ liệu vào thư mục tạm (không giữ cả chương trong RAM),
    # phóng 1 lần cho cả chương rồi mới ghi vào chỗ (nguồn JPG không bị nén JPEG 2 lần)
    pdir, pend, ph = None, [], None
    want_phong = conf.get('phong', True)
    try:
        for i, name in enumerate(names, 1):
            progress(i, len(names), name)
            rec = dict(src=name)
            rule = rule_for(conf, rel, name)
            if rule:
                rec['rule'] = rule
            try:
                outs = process_image(src / name, rule, doc, rec)
            except Exception as e:      # ảnh lạ làm hỏng bước nào đó: chép nguyên, báo lại
                rec['loi'] = f"{type(e).__name__}: {e}"
                rec['kind'] = rec.get('kind', '?') + '/loi'
                outs = [None]
            rec['out'] = []
            lossy = os.path.splitext(name)[1].lower() in LOSSY_EXTS
            pages = rec.get('pages') or [rec]
            for j, arr in enumerate(outs):
                n += 1
                if arr is None:
                    dst = tmp / f"{n:0{width}d}{os.path.splitext(name)[1].lower()}"
                    shutil.copyfile(src / name, dst)
                else:
                    dst = tmp / f"{n:0{width}d}{'.jpg' if lossy else '.png'}"
                    if want_phong and arr.shape[0] < PHONG_H and pdir is None:
                        pdir = phong_dir()
                        if pdir is None:
                            want_phong = False
                            ph = dict(cho=0, n=0, loi="đường dẫn thư mục tạm có dấu tiếng Việt (exe Real-ESRGAN sập)")
                    if want_phong and arr.shape[0] < PHONG_H:
                        Image.fromarray(arr).save(pdir / 'vao' / f"{dst.stem}.png", 'PNG', compress_level=1)
                        pend.append((dst, lossy, pages[j] if j < len(pages) else rec))
                    else:
                        save_gray(fix_font(arr, dst.name), dst, lossy)
                rec['out'].append(dst.name)
                outs_all.append(dst)
            th = rec.pop('_thumb', None)
            if th is not None:
                thumbs.append((os.path.splitext(name)[0], th))
            recs.append(rec)
        if pend:
            progress(len(names), len(names), f"phóng AI {PHONG_SCALE}x {len(pend)} trang (Real-ESRGAN)...")
            got, err = phong_ai(pdir, [d.stem for d, _, _ in pend])
            for dst, lossy, page in pend:
                a = got[dst.stem]
                if a is None:       # không phóng được: ghi cỡ gốc
                    with Image.open(pdir / 'vao' / f"{dst.stem}.png") as im:
                        a = np.asarray(im.convert('L'))
                else:
                    page['phong'] = PHONG_SCALE
                save_gray(fix_font(a, dst.name), dst, lossy)
            ph = dict(model=ESR_MODEL, scale=PHONG_SCALE, nguong=PHONG_H, cho=len(pend),
                      n=sum(v is not None for v in got.values()))
            if err:
                ph['loi'] = err
    finally:
        if pdir is not None:
            shutil.rmtree(pdir, ignore_errors=True)
    # kiểm từng ảnh ra giải mã được, đủ số lượng
    for p in outs_all:
        try:
            with Image.open(p) as im:
                im.verify()
        except Exception as e:
            shutil.rmtree(tmp, ignore_errors=True)
            return dict(loi=f"ảnh ra hỏng {p.name}: {e}")
    if len(outs_all) != n or not outs_all:
        shutil.rmtree(tmp, ignore_errors=True)
        return dict(loi="không có ảnh ra")
    for e in extras:
        shutil.copy2(e.path, tmp / e.name)
    marker = dict(tool='lam_sach_scan', version=VERSION, time=time.strftime('%Y-%m-%d %H:%M:%S'),
                  doc=doc, goc=f"{ORIG_DIR}/{rel}", n_in=len(names), n_out=n,
                  phong=ph if ph is not None else bool(conf.get('phong', True)), pages=recs, hoan_tat=True)
    if fnt is not None and fnt['done']:
        marker['doi_font'] = dict(nguon=conf['doi_font']['nguon'], font=conf['doi_font']['font'],
                                  time=marker['time'], cho_soat=len(fnt['pend']), trang=fnt['done'])
    (tmp / CONF_NAME).write_text(json.dumps(marker, ensure_ascii=False, indent=1, default=_json_default),
                                 encoding='utf-8')
    # đổi chỗ
    if plan['status'] == 'moi':
        if not move_dir(ch, orig):
            shutil.rmtree(tmp, ignore_errors=True)
            return dict(loi="chương đang bị khoá (reader/Explorer đang mở ảnh?) — chạy lại sau")
        if not move_dir(tmp, ch):
            move_dir(orig, ch)
            shutil.rmtree(tmp, ignore_errors=True)
            return dict(loi="không đưa được bản sạch vào chỗ — đã trả bản gốc lại như cũ")
    else:   # lam_lai: bản gốc giữ nguyên trong .lam-sach\goc, bản sạch cũ bỏ
        old = series / TMP_DIR / '_cu' / Path(*rel.split('/'))
        if old.exists():
            shutil.rmtree(old, ignore_errors=True)
        if not move_dir(ch, old):
            shutil.rmtree(tmp, ignore_errors=True)
            return dict(loi="chương đang bị khoá (reader/Explorer đang mở ảnh?) — chạy lại sau")
        if not move_dir(tmp, ch):
            move_dir(old, ch)
            shutil.rmtree(tmp, ignore_errors=True)
            return dict(loi="không đưa được bản sạch vào chỗ — đã trả bản cũ lại như cũ")
        shutil.rmtree(old, ignore_errors=True)
    if thumbs:
        gutter_sheet(thumbs, series / REVIEW_DIR / f"{safe_name(rel)} - gay.jpg",
                     f"{series.name} / {rel}: do = cat (tach), xanh = giu nguyen, cam NGHI = co the la tranh lien gay")
    font = None
    if fnt is not None:
        if fnt['rows']:
            font_list(fnt['dir'], rel, conf, fnt['rows'], fnt['pend'], True)
        font = dict(dong=len(fnt['rows']), trang=fnt['trang'], doi=sum(len(v) for v in fnt['done'].values()),
                    trang_doi=len(fnt['done']), cho=len(fnt['pend']), loi=fnt['loi'])
    kinds = {}
    for r in recs:
        kinds[r.get('kind', '?')] = kinds.get(r.get('kind', '?'), 0) + 1
    return dict(n_in=len(names), n_out=n, kinds=kinds, secs=time.time() - t0, phong=ph, font=font,
                nghi=[r['src'] for r in recs if r.get('seam', {}).get('nghi') and r.get('decision') == 'tach'],
                tu_giu=[r['src'] for r in recs if r.get('decision') == 'giu_tu_dong'],
                giu=[r['src'] for r in recs if r.get('decision') in ('giu', 'giu_ghep')],
                trang_khong_trang=[f"{r['src']}" + (f"[{p['side']}]" if p.get('side') not in (None, 'S') else '')
                                   for r in recs for p in (r.get('pages') or [r])
                                   if 'whiten' in p and not p['whiten']['ok']],
                loi_anh=[f"{r['src']}: {r['loi']}" for r in recs if r.get('loi')])


# ================================================================ chạy thử (--thu)

def run_trial(series, chapters, conf, doc, count):
    pool = []
    for rel in chapters:
        ch = series.joinpath(*rel.split('/'))
        src = tool_path(series, ORIG_DIR) / Path(*rel.split('/')) if (ch / CONF_NAME).exists() else ch
        pool += [(rel, src, n) for n in list_images(src)]
    if not pool:
        print("Không có ảnh nào để thử.")
        return 2
    count = max(1, min(count, len(pool)))
    pick = [pool[int(round(i * (len(pool) - 1) / max(1, count - 1)))] for i in range(count)] if count > 1 else [pool[0]]
    out_dir = series / REVIEW_DIR / 'thu'
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Làm thử {count} ảnh (thư viện giữ nguyên) -> {out_dir}")
    for rel, src, name in pick:
        t0 = time.time()
        rec = dict(src=name)
        try:
            outs = process_image(src / name, rule_for(conf, rel, name), doc, rec)
        except Exception as e:
            print(f"  {rel} / {name}: LỖI {type(e).__name__}: {e}")
            continue
        rec.pop('_thumb', None)
        tags, ph_note = [''] * len(outs), ''
        idx = [j for j, a in enumerate(outs) if a is not None and a.shape[0] < PHONG_H]
        if conf.get('phong', True) and idx:
            pdir = phong_dir()
            got, err = {}, "đường dẫn thư mục tạm có dấu tiếng Việt"
            if pdir is not None:
                try:
                    for j in idx:
                        Image.fromarray(outs[j]).save(pdir / 'vao' / f"{j}.png", 'PNG', compress_level=1)
                    got, err = phong_ai(pdir, [str(j) for j in idx])
                finally:
                    shutil.rmtree(pdir, ignore_errors=True)
            for j in idx:
                if got.get(str(j)) is not None:
                    outs[j] = got[str(j)]
                    tags[j] = f' (AI {PHONG_SCALE}x)'
            ph_note = f" phóng AI {PHONG_SCALE}x" if not err else f" ! KHÔNG phóng AI được: {err}"
        with Image.open(src / name) as im:
            before = im.convert('RGB')
        h = 1000
        tiles = [before.resize((max(1, round(before.width * h / before.height)), h), Image.LANCZOS)]
        for arr in outs:
            im = before if arr is None else Image.fromarray(arr).convert('RGB')
            tiles.append(im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS))
        W = sum(t.width for t in tiles) + 12 * (len(tiles) - 1)
        sheet = Image.new('RGB', (W, h + 22), (90, 90, 90))
        x = 0
        for j, t in enumerate(tiles):
            sheet.paste(t, (x, 22))
            ImageDraw.Draw(sheet).text((x + 4, 5), 'GOC' if j == 0 else f'SAU {j}{tags[j - 1]}', fill=(255, 255, 255))
            x += t.width + 12
        p = out_dir / f"{safe_name(rel)} - {os.path.splitext(name)[0]}.jpg"
        sheet.save(p, quality=85)
        wh = [q['whiten']['ok'] for q in (rec.get('pages') or [rec]) if 'whiten' in q]
        print(f"  {rel} / {name}: {rec.get('kind')} {rec.get('decision', '')} -> {len(outs)} trang"
              f"{'' if all(wh) else ' (có trang KHÔNG qua cổng làm trắng)'}"
              f"{' NGHI liền gáy' if rec.get('seam', {}).get('nghi') else ''}{ph_note}  ({time.time() - t0:.1f}s)")
    return 0


# ================================================================ main

def header_kind(path):
    """Phân loại sơ bộ theo cỡ (chỉ đọc đầu file) cho --dry-run -> (loại, triệu điểm ảnh, cao)."""
    try:
        with Image.open(path) as im:
            W, H = im.size
            frames = getattr(im, 'n_frames', 1)
    except Exception:
        return '?', 0, 0
    if frames > 1:
        return 'dong', 0, H
    ar = W / H
    if H / W > TALL_AR or ar > DOUBLE_AR[1]:
        return 'khac', 0, H
    if H < MIN_H:
        return 'nho', 0, H
    return ('doi' if ar >= DOUBLE_AR[0] else 'don'), W * H / 1e6, H


def main():
    ap = argparse.ArgumentParser(description="Làm sạch ảnh scan: tách trang đôi, dọn gáy, làm trắng, dọn xám, làm nét.")
    ap.add_argument('target', help='folder truyện (hoặc 1 chương) trong downloads\\')
    ap.add_argument('--dry-run', action='store_true', help='chỉ kiểm + in kế hoạch, không ghi gì')
    ap.add_argument('--thu', type=int, default=0, metavar='N', help='làm thử N ảnh rải đều ra .lam-sach\\soat\\thu\\')
    ap.add_argument('--lam-lai', action='store_true', help='làm lại chương đã làm (từ bản gốc)')
    ap.add_argument('--tra-goc', action='store_true', help='trả bản gốc về chỗ, bỏ bản đã làm sạch')
    ap.add_argument('--trai-truoc', action='store_true', help='truyện đọc trái->phải (trang trái trước)')
    ap.add_argument('--khong-phong', action='store_true', help=f'không phóng AI trang thấp (< {PHONG_H} px)')
    ap.add_argument('--soat-font', action='store_true',
                    help='dò chữ lệch font (Calibri) ở chương đã làm sạch -> ảnh trước|sau + danh sách vào '
                         '.lam-sach\\soat\\doi-font\\, thư viện y nguyên')
    ap.add_argument('--doi-font', action='store_true',
                    help='đổi chữ lệch font sang font truyện (CC Wild Words Roman): chương đã làm sạch đổi tại chỗ, '
                         'chương làm sạch trong lần này đổi luôn')
    a = ap.parse_args()
    if _IMPORT_ERR is not None:
        print(f"! Thiếu thư viện ({_IMPORT_ERR}). Cài: python -m pip install numpy opencv-python-headless Pillow")
        return 2
    if a.soat_font and a.doi_font:
        print("! Chọn 1: --soat-font (chỉ soát) hoặc --doi-font (đổi thật).")
        return 2
    if (a.soat_font or a.doi_font) and (a.thu or a.tra_goc):
        print("! --soat-font / --doi-font không đi cùng --thu / --tra-goc.")
        return 2
    series, only, err = resolve_target(Path(a.target))
    if err:
        print(f"! {err}")
        return 2
    conf = load_conf(series)
    doc = 'trai-truoc' if a.trai_truoc else conf['doc']
    if a.khong_phong:
        conf['phong'] = False
    writes = not a.dry_run and not a.thu and not a.soat_font
    if writes and not take_lock(series):
        print(f"! Truyện này đang được làm ở cửa sổ khác ({series / TMP_DIR / 'lock.json'}).")
        return 2
    try:
        if writes:
            # cấu hình đã đọc ở trên (chỗ cũ hoặc mới) = cùng nội dung, gom xong không cần đọc lại
            for note in migrate_legacy(series) + recover(series):
                print("  " + note)
        # liệt kê chương SAU khi dọn dở dang: chương bị ngắt giữa 2 lần đổi tên vừa được đưa lại chỗ
        chapters = only if only is not None else series_chapters(series)
        if not chapters:
            print(f"! Không thấy chương nào (folder con có ảnh) trong {series}")
            return 2
        return _run(a, series, chapters, conf, doc)
    finally:
        if writes:
            drop_lock(series)


def _run(a, series, chapters, conf, doc):
    low_priority()
    print(f"Truyện: {series}")
    print(f"  {len(chapters)} chương · đọc {'trái -> phải' if doc == 'trai-truoc' else 'phải -> trái (manga)'}"
          f" · cấu hình {'có' if tool_path(series, SERIES_CONF).exists() else 'mặc định'} ({win(SERIES_CONF)})")
    twin = series.parent / (series.name + "_webp")
    if twin.is_dir():
        print(f"  ! Có bản '{twin.name}' — reader đang hiện bản đó, không phải folder này.")
    if a.thu:
        return run_trial(series, chapters, conf, doc, a.thu)
    fe = None
    if (a.soat_font or a.doi_font or conf['doi_font']['bat']) and not a.tra_goc:
        fe, fdesc = font_engine(conf)
        if fe is None:
            if a.soat_font or a.doi_font:
                print(f"! Đổi font: {fdesc}")
                return 2
            print(f"  ! doi_font.bat = true nhưng {fdesc} — lần này làm sạch KHÔNG đổi font.")
        else:
            print(f"  đổi chữ lệch font: {fdesc}")
    if a.soat_font:
        return run_font(series, chapters, conf, fe, False)
    plans = {rel: chapter_plan(series, rel, a.lam_lai, a.tra_goc) for rel in chapters}
    todo_status = ('tra_goc',) if a.tra_goc else ('moi', 'lam_lai')
    todo = [rel for rel in chapters if plans[rel]['status'] in todo_status]
    font_only = [rel for rel in chapters if a.doi_font and plans[rel]['status'] == 'da_lam']
    # bảng kế hoạch
    tot_mp, tot, tot_ph = 0.0, dict(doi=0, don=0, khac=0), 0
    lab = dict(moi='LÀM', lam_lai='LÀM LẠI', tra_goc='TRẢ GỐC', da_lam='đã làm (bỏ qua)', loi='LỖI', bo='bỏ qua')
    print()
    for rel in chapters:
        p = plans[rel]
        line = f"  {lab[p['status']] if rel not in font_only else 'ĐỔI FONT':<16} {rel}"
        if p['status'] in ('moi', 'lam_lai'):
            cnt, n_ph = dict(doi=0, don=0, khac=0), 0
            for name in list_images(p['src']):
                k, mp, h = header_kind(p['src'] / name)
                cnt['doi' if k == 'doi' else 'don' if k == 'don' else 'khac'] += 1
                tot_mp += mp
                if conf['phong'] and k in ('doi', 'don') and h < PHONG_H:
                    n_ph += 2 if k == 'doi' else 1
            for k in cnt:
                tot[k] += cnt[k]
            tot_ph += n_ph
            line += f"  — {sum(cnt.values())} ảnh: {cnt['doi']} tờ đôi, {cnt['don']} trang đơn, {cnt['khac']} chép nguyên"
            if n_ph:
                line += f", ~{n_ph} trang thấp sẽ phóng AI {PHONG_SCALE}x"
            pairs = joined_pairs(series.name, rel)
            if pairs:
                line += f"  ! {pairs} cặp ghép tay trong reader sẽ mất (tên ảnh đổi)"
        elif p.get('note'):
            line += f"  — {p['note']}"
        print(line)
    if not todo and not font_only:
        print("\nKhông có chương nào cần làm.")
        return 1 if any(p['status'] == 'loi' for p in plans.values()) else 0
    if font_only:
        print(f"\nĐổi chữ lệch font tại chỗ {len(font_only)} chương đã làm sạch: chỉ ghi đè trang có dòng được đổi, "
              f"dòng cần soát để nguyên. Ảnh trước|sau + danh sách: {series.name}\\{win(FONT_REVIEW)}\\.")
    if todo and fe is not None:
        print(f"\nChương làm sạch lần này: đổi chữ lệch font ở bước cuối mỗi trang.")
    if todo and not a.tra_goc:
        print(f"\nSẽ làm {len(todo)} chương: {tot['doi']} tờ đôi -> tách (trừ tờ tranh vắt qua gáy rõ / ghi giữ trong cấu hình), "
              f"{tot['don']} trang đơn, {tot['khac']} ảnh chép nguyên (ảnh màu đo lúc chạy, cũng chép nguyên).")
        print(f"Ước ~{max(1, round((tot_mp * SEC_PER_MP + tot_ph * SEC_PER_PHONG) / 60))} phút. "
              f"Bản gốc cất vào {series.name}\\{win(ORIG_DIR)}\\.")
        if tot_ph:
            exe = Path(os.environ.get('LAM_SACH_ESRGAN') or ESR_EXE)
            print(f"Phóng AI {PHONG_SCALE}x (Real-ESRGAN, cần GPU) trang cao < {PHONG_H} px — tắt: --khong-phong hoặc "
                  f"\"phong\": false trong {win(SERIES_CONF)}."
                  + ("" if exe.is_file() else f"\n  ! Không thấy {exe} -> sẽ giữ cỡ gốc."))
        elif not conf['phong']:
            print(f"Không phóng AI (đã tắt) — trang giữ cỡ gốc.")
    if a.dry_run:
        print("\n(--dry-run: chưa ghi gì)")
        return 0
    if not a.tra_goc and not (series / SERIES_CONF).exists():
        (series / SERIES_CONF).parent.mkdir(parents=True, exist_ok=True)
        (series / SERIES_CONF).write_text(json.dumps(CONF_TEMPLATE, ensure_ascii=False, indent=1), encoding='utf-8')
    print()
    errors, sums = [], []
    t_all = time.time()
    for ci, rel in enumerate(todo, 1):
        head = f"[{ci}/{len(todo)}] {rel}"
        if a.tra_goc:
            e = restore_chapter(series, rel)
            print(f"{head}: {'đã trả bản gốc' if not e else 'LỖI ' + e}")
            if e:
                errors.append(f"{rel}: {e}")
            continue

        def progress(i, n, name, head=head):
            print(f"\r{head}: ảnh {i}/{n} {name}"[:110].ljust(112), end='', flush=True)
        r = process_chapter(series, rel, plans[rel], conf, doc, progress, fe)
        print("\r" + " " * 112 + "\r", end='')
        if 'loi' in r:
            print(f"{head}: LỖI — {r['loi']}")
            errors.append(f"{rel}: {r['loi']}")
            continue
        ks = ', '.join(f"{v} {KIND_VI.get(k, k)}" for k, v in sorted(r['kinds'].items()))
        print(f"{head}: {r['n_in']} ảnh ({ks}) -> {r['n_out']} trang  ({r['secs']:.0f}s)")
        for key, title in (('nghi', 'tờ NGHI tranh liền gáy (đã tách — liền thật thì bấm Join trong reader '
                                    'hoặc ghi vào giu_nguyen rồi --lam-lai)'),
                           ('tu_giu', 'tờ TỰ GIỮ NGUYÊN vì tranh vắt qua gáy rõ (sai thì ghi vào "tach" rồi --lam-lai)'),
                           ('giu', 'tờ giữ nguyên theo cấu hình'),
                           ('trang_khong_trang', 'trang KHÔNG qua cổng làm trắng (chỉ tách, giữ nền gốc)'),
                           ('loi_anh', 'ảnh lỗi (đã chép nguyên)')):
            if r[key]:
                print(f"    {title}: {', '.join(r[key])}")
        ph = r.get('phong')
        if ph and ph['n']:
            print(f"    phóng AI {PHONG_SCALE}x: {ph['n']}/{ph['cho']} trang thấp (< {PHONG_H} px)")
        if ph and ph.get('loi'):
            left = ph['cho'] - ph['n']
            print(f"    ! KHÔNG phóng AI được{f' {left} trang' if left else ''} — giữ cỡ gốc ({ph['loi']}). "
                  f"Sửa xong (GPU / exe) thì chạy lại với --lam-lai.")
        if r.get('font') is not None:
            print(f"    đổi font: {font_summary(r['font'], rel, True)}")
            for e in r['font']['loi']:
                print(f"    ! đổi font lỗi (trang giữ chữ cũ) {e}")
        sums.append(r)
    if todo and not a.tra_goc:
        print(f"\nXong {len(sums)}/{len(todo)} chương trong {time.time() - t_all:.0f}s.", end='')
        if sums:
            print(f" Ảnh soát (lưới gáy từng chương): {series / REVIEW_DIR}")
        else:
            print()
    if font_only:
        if todo:
            print()
        if run_font(series, font_only, conf, fe, True):
            errors.append("đổi font: có trang lỗi (xem trên)")
    if errors:
        print("\nCác chương lỗi:")
        for e in errors:
            print("  - " + e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
