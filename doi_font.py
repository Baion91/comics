#!/usr/bin/env python3
"""Đổi chữ lệch font trong trang truyện đã làm sạch — bước tuỳ chọn của lam_sach_scan.py (--soat-font / --doi-font).

Bản dịch hay có vài chỗ nhóm dịch gõ bằng font hệ thống thay vì font truyện tranh. Mega Man World: tên robot, tên
chiêu, tiếng hét, ghi chú tiếng động gõ Calibri Bold giữa các bóng CC Wild Words Roman. Font lệch là font ĐÃ BIẾT
(có sẵn trong Windows) nên:
  - Đọc chữ KHÔNG cần OCR: mỗi mảnh mực trên nền trắng so với khuôn từng ký tự của font lệch (A-Z, 0-9, ! ?) co về
    đúng khung; chữ dính nhau (UT, AM) cắt thử ở cột ít mực nhất; "!" có / không dính chấm.
  - Tự kiểm: in lại từng từ vừa đọc bằng font lệch rồi so nét với ảnh (F-score, dung sai 1 px). Chữ font lệch thật
    khớp 0,98-1,00; chữ font truyện tranh / nét vẽ <= 0,974 (đo 74 trang MMW: 61/61 dòng đúng, không nhầm dòng nào).
  - Xoá đúng các mảnh mực của chữ (không đụng viền bóng), in lại bằng font đích: chữ hoa cao bằng chữ cũ, cùng chân
    chữ, cùng tâm ngang (dịch trong chỗ trống / co tối đa 15 % nếu tràn).
Dòng TỰ (đổi luôn) phải: khớp >= 0,98, hơn font đích >= 0,03, không còn dấu chưa đọc được quanh dòng, không sát nét
khác (chữ dính viền bóng), không chạm mép trang, không tràn chỗ trống. Còn lại là SOÁT: chỉ đổi khi duyệt trong cấu
hình (duyet / sua). Không bắt: chữ đè lên tranh / tram (cần nền trắng), dòng < 3 ký tự, chữ thường, chữ hoa < 12 px.

Dùng qua lam_sach_scan.py; module này chỉ có phần ảnh: find_font, DoiFont.plan / render, page_rules, sheet, list_rows."""

import os
import re
from pathlib import Path

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?'
DARK = 150          # mực
PAPER = 215         # giấy (đo nền trắng quanh chữ)
FREE = 200          # điểm trống khi tìm chỗ in chữ mới
CAL_OK = 0.98       # in lại bằng font lệch khớp >= ngưỡng = đọc đúng + đúng font lệch
MARGIN = 0.03       # font đích cũng khớp gần bằng -> không chắc
MIN_CAP = 12        # chữ hoa thấp hơn: chấm / nét vẽ lẻ khớp bừa
MIN_GLYPHS = 3
WORD_GAP = 0.3      # khe > 0,3 x cao chữ = cách từ
SHRINK = 0.85       # co chữ mới tối đa khi tràn chỗ trống
K3 = np.ones((3, 3), np.uint8)


# ================================================================ tìm file font

def _font_dirs():
    yield Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
    la = os.environ.get('LOCALAPPDATA')
    if la:
        yield Path(la) / 'Microsoft' / 'Windows' / 'Fonts'     # font cài "cho riêng tôi"


def find_font(name):
    """Tên font như Windows hiện ('CC Wild Words Roman', 'Calibri Bold'), tên file hoặc đường dẫn -> Path / None."""
    p = Path(name)
    if p.is_file():
        return p
    for d in _font_dirs():
        if (d / name).is_file():
            return d / name
    want = name.strip().lower()
    if os.name == 'nt':
        import winreg
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                k = winreg.OpenKey(root, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')
            except OSError:
                continue
            with k:
                i = 0
                while True:
                    try:
                        disp, val, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    if re.sub(r'\s*\((TrueType|OpenType)\)$', '', disp, flags=re.I).strip().lower() != want:
                        continue
                    f = Path(val)
                    if not f.is_absolute():
                        f = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts' / val
                    if f.is_file():
                        return f
    for d in _font_dirs():      # máy không có registry đúng: đọc tên trong từng file font
        for f in sorted(d.glob('*')):
            if f.suffix.lower() not in ('.ttf', '.otf', '.ttc'):
                continue
            try:
                fam, sty = ImageFont.truetype(str(f), 10).getname()
            except Exception:
                continue
            fam, sty = (fam or '').lower(), (sty or '').lower()      # vài font không ghi tên họ / kiểu
            if f"{fam} {sty}" == want or (fam == want and sty in ('regular', 'roman')):
                return f
    return None


# ================================================================ quy tắc trong cấu hình

def page_rules(df, rel):
    """doi_font.duyet / sua / bo của 1 chương (gộp "*") -> dict(duyet=set, sua=dict, bo=set) theo khoá "<ảnh>:<chữ>"."""
    out = dict(duyet=set(), sua={}, bo=set())
    for ch in ('*', rel):
        out['duyet'].update(df.get('duyet', {}).get(ch, []))
        out['bo'].update(df.get('bo', {}).get(ch, []))
        out['sua'].update(df.get('sua', {}).get(ch, {}))
    return out


# ================================================================ đo / đọc

def _tight(m):
    ys, xs = np.where(m)
    if not len(ys):
        return m[:0, :0]
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _render(text, path, size):
    f = ImageFont.truetype(path, size)
    l, t, r, b = f.getbbox(text)
    im = Image.new('L', (r - l + 8, b - t + 8), 0)
    ImageDraw.Draw(im).text((4 - l, 4 - t), text, font=f, fill=255)
    return _tight(np.asarray(im) > 127)


def _fscore(a, b):
    """Độ khớp nét 2 mặt nạ cùng cỡ, dung sai 1 px."""
    da, db = cv2.dilate(a.astype(np.uint8), K3) > 0, cv2.dilate(b.astype(np.uint8), K3) > 0
    p = (b & da).sum() / max(b.sum(), 1)
    r = (a & db).sum() / max(a.sum(), 1)
    return 2 * p * r / max(p + r, 1e-6)


def _fit(m, w, h):
    return cv2.resize(m.astype(np.uint8) * 255, (w, h), interpolation=cv2.INTER_AREA) > 127


class Page:
    def __init__(self, g, lab, lines):
        self.g, self.lab, self.lines = g, lab, lines


class DoiFont:
    """Khuôn chữ font lệch + font đích. Khuôn đã co theo cỡ được nhớ lại (1 trang có nhiều chữ cùng cỡ)."""

    def __init__(self, src_path, dst_path):
        self.src, self.dst = str(src_path), str(dst_path)
        self.T = {c: _render(c, self.src, 160) for c in CHARS}
        self.parts = {c: cv2.connectedComponents(t.astype(np.uint8), connectivity=8)[0] - 1 for c, t in self.T.items()}
        self._tpl, self._word = {}, {}
        l, t, r, b = ImageFont.truetype(self.dst, 100).getbbox('H', anchor='ls')
        self.cap_dst = (b - t) / 100            # cao chữ hoa font đích / cỡ font

    # ---------------------------------------------------------------- 1 ký tự
    def _t(self, c, w, h):
        k = (c, w, h)
        v = self._tpl.get(k)
        if v is None:
            if len(self._tpl) > 50000:
                self._tpl.clear()
            r = _fit(self.T[c], w, h)
            v = self._tpl[k] = (r, cv2.dilate(r.astype(np.uint8), K3) > 0, max(int(r.sum()), 1))
        return v

    def classify(self, m, parts):
        """Ký tự font lệch khớp nhất cho mặt nạ 1 ký tự -> (ký tự, điểm). Điểm = F (dung sai 1 px) + 0,01 x F chặt
        để tách hoà ("I" với "!" dính chấm)."""
        h, w = m.shape
        dm = cv2.dilate(m.astype(np.uint8), K3) > 0
        ms = max(int(m.sum()), 1)
        best, bc = 0.0, '?'
        for c, t in self.T.items():
            if parts > 1 and self.parts[c] == 1:
                continue
            ar = (w / h) / (t.shape[1] / t.shape[0])
            if not 0.7 < ar < 1.43:
                continue
            r, dr, rs = self._t(c, w, h)
            p = (r & dm).sum() / rs
            rc = (m & dr).sum() / ms
            sc = 2 * p * rc / max(p + rc, 1e-6) + 0.01 * 2 * (m & r).sum() / (ms + rs)
            if sc > best:
                best, bc = sc, c
        return bc, min(best, 1.0)

    def split(self, m, parts, depth=2):
        """Chữ dính nhau -> thử cắt ở cột ít mực nhất, nhận nếu mọi phần đều khớp tốt hơn cả khối.
        -> [(x0, x1, ký tự, điểm)] theo toạ độ trong m."""
        h, w = m.shape
        c, sc = self.classify(m, parts)
        if sc >= 0.92 or depth == 0 or w < 0.9 * h:
            return [(0, w, c, sc)]
        ink = m.sum(0)
        best = None
        for x in sorted(range(int(0.2 * w), int(0.8 * w) + 1), key=lambda x: ink[x])[:5]:
            L, R = m[:, :x], m[:, x:]
            if L.sum() < 4 or R.sum() < 4:
                continue
            out = []
            for part, off in ((L, 0), (R, x)):
                xs, ys = np.where(part.any(0))[0], np.where(part.any(1))[0]
                sub = part[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
                out += [(off + xs.min() + a, off + xs.min() + b, cc, ss) for a, b, cc, ss in self.split(sub, 1, depth - 1)]
            mn = min(t[3] for t in out)
            if best is None or mn > best[0]:
                best = (mn, out)
        if best and best[0] > max(sc, 0.9):
            return best[1]
        return [(0, w, c, sc)]

    # ---------------------------------------------------------------- trang
    def glyphs(self, g):
        """Mảnh mực cỡ chữ nằm trên nền trắng -> ký tự đọc được, nhãn mảnh, bảng mảnh."""
        H, W = g.shape
        gmax = max(90, int(0.06 * H))
        n, lab, st, _ = cv2.connectedComponentsWithStats((g < DARK).astype(np.uint8), 8)
        small = (st[:, 3] <= gmax) & (st[:, 2] <= gmax)
        small[0] = False
        # nền trắng đo khi đã bỏ các mảnh cỡ chữ (chữ to đậm tự che nền của nó)
        white = cv2.blur(((g > PAPER) | small[lab]).astype(np.float32), (31, 31)) > 0.5
        x, y, w, h, a = (st[:, k].astype(np.int64) for k in range(5))
        ok = small & (a >= 4) & ~((h >= 8) & (w > 0.4 * h) & (a > 0.75 * w * h + 20))
        ok &= white[np.minimum(y + h // 2, H - 1), np.minimum(x + w // 2, W - 1)]
        idx = np.nonzero(ok)[0]
        if not len(idx):
            return [], lab, st
        X0, Y0, X1, Y1, HH = x[idx], y[idx], x[idx] + w[idx], y[idx] + h[idx], h[idx]
        box = np.stack([X0, Y0, X1, Y1], 1)
        # chấm của "!" "?" tách khỏi thân: gộp vào thân mảnh phía trên (chồng ngang, hở dọc nhỏ, chấm thấp)
        used = np.zeros(len(idx), bool)
        grp = [[int(i)] for i in idx]
        for k in np.argsort(Y0, kind='stable'):
            if used[k] or HH[k] < 8 or w[idx[k]] > 0.9 * HH[k]:
                continue
            bx0, by0, bx1, by1 = box[k]
            c = ~used & (Y0 >= by1 - 1) & (Y0 - by1 <= 0.35 * max(by1 - by0, 6)) & (HH < 0.45 * (by1 - by0))
            c[k] = False
            if not c.any():
                continue
            c &= (np.minimum(X1, bx1) - np.maximum(X0, bx0)) > 0.5 * np.minimum(X1 - X0, bx1 - bx0)
            for j in np.nonzero(c)[0]:
                box[k] = [min(box[k][0], X0[j]), box[k][1], max(box[k][2], X1[j]), max(box[k][3], Y1[j])]
                grp[k] += grp[j]
                used[j] = True
        out = [[*map(int, box[k]), grp[k]] for k in range(len(idx)) if not used[k] and box[k][3] - box[k][1] >= 8]
        if not out:
            return [], lab, st
        # chỉ đọc mảnh có hàng xóm cùng dòng (bỏ nét vẽ lẻ -> nhanh)
        B = np.array([c[:4] for c in out], float)
        h = B[:, 3] - B[:, 1]
        cy = (B[:, 1] + B[:, 3]) / 2
        keep = np.zeros(len(out), bool)
        for i0 in range(0, len(out), 2000):
            sl = slice(i0, i0 + 2000)
            hr = h[sl, None] / h[None, :]
            hm = np.maximum(h[sl, None], h[None, :])
            gap = np.maximum(B[sl, None, 0], B[None, :, 0]) - np.minimum(B[sl, None, 2], B[None, :, 2])
            ok = (hr > 0.7) & (hr < 1.43) & (np.abs(cy[sl, None] - cy[None, :]) < 0.3 * hm) & (gap < hm)
            ok[np.arange(ok.shape[0]), np.arange(i0, i0 + ok.shape[0])] = False
            keep[sl] = ok.any(1)
        res = []
        for (x0, y0, x1, y1, ids), k in zip(out, keep):
            if not k or x1 - x0 > 3 * (y1 - y0):
                continue
            m = np.isin(lab[y0:y1, x0:x1], ids)
            for a, b, c, sc in self.split(m, len(ids)):
                if sc > 0.6:
                    res.append(dict(b=(x0 + a, y0, x0 + b, y1), c=c, s=sc, ids=ids))
        return res, lab, st

    @staticmethod
    def lines(gs):
        """Ký tự cùng hàng, cao tương đương, khe < 1 chữ -> dòng (>= 3 ký tự)."""
        n = len(gs)
        par = list(range(n))

        def f(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for i in range(n):
            a = gs[i]['b']
            for j in range(i + 1, n):
                b = gs[j]['b']
                ha, hb = a[3] - a[1], b[3] - b[1]
                if not 0.7 < ha / hb < 1.43:
                    continue
                hm = max(ha, hb)
                if abs((a[1] + a[3]) - (b[1] + b[3])) / 2 > 0.3 * hm:
                    continue
                if max(a[0], b[0]) - min(a[2], b[2]) < hm:
                    par[f(i)] = f(j)
        grp = {}
        for i in range(n):
            grp.setdefault(f(i), []).append(gs[i])
        out = []
        for v in grp.values():
            if len(v) < MIN_GLYPHS:
                continue
            v.sort(key=lambda d: d['b'][0])
            hh = float(np.median([d['b'][3] - d['b'][1] for d in v]))
            words, cur = [], [v[0]]
            for p, q in zip(v, v[1:]):
                if q['b'][0] - p['b'][2] > WORD_GAP * hh:
                    words.append(cur)
                    cur = []
                cur.append(q)
            words.append(cur)
            out.append(dict(g=v, words=words, box=(min(d['b'][0] for d in v), min(d['b'][1] for d in v),
                                                   max(d['b'][2] for d in v), max(d['b'][3] for d in v))))
        return out

    def _word_mask(self, text, path):
        k = (text, path)
        v = self._word.get(k)
        if v is None:
            if len(self._word) > 5000:
                self._word.clear()
            v = self._word[k] = _render(text, path, 120)
        return v

    def check(self, L, lab):
        """In lại từng từ bằng font lệch / font đích, so nét -> (khớp font lệch, khớp font đích), cộng theo số ký tự."""
        cs, ds, ns = [], [], []
        for wd in L['words']:
            bx0, by0 = min(d['b'][0] for d in wd), min(d['b'][1] for d in wd)
            bx1, by1 = max(d['b'][2] for d in wd), max(d['b'][3] for d in wd)
            crop = _tight(np.isin(lab[by0:by1, bx0:bx1], sorted({i for d in wd for i in d['ids']})))
            h, w = crop.shape
            txt = ''.join(d['c'] for d in wd)
            cs.append(_fscore(crop, _fit(self._word_mask(txt, self.src), w, h)))
            ds.append(_fscore(crop, _fit(self._word_mask(txt, self.dst), w, h)))
            ns.append(len(wd))
        return float(np.average(cs, weights=ns)), float(np.average(ds, weights=ns))

    def _tail(self, L, dark):
        """Ký tự cuối dính viền bóng: khuôn đặt ở ô kế tiếp phải nằm trọn trên nét tối (phủ >= 0,97) mà quanh nó
        ít tối (nét viền mảnh, không phải mảng tranh). -> (ký tự, x, mặt nạ) hoặc None."""
        x0, y0, x1, y1 = L['box']
        h = y1 - y0
        W = dark.shape[1]
        darkd = cv2.dilate(dark[y0:y1].astype(np.uint8), K3) > 0
        v = L['g']
        gaps = [q['b'][0] - p['b'][2] for p, q in zip(v, v[1:]) if q['b'][0] - p['b'][2] < WORD_GAP * h]
        sp = int(np.median(gaps)) if gaps else 2
        best = None
        for c, t in self.T.items():
            if c in '!?':
                continue
            tw = max(2, round(t.shape[1] * h / t.shape[0]))
            r = _fit(t, tw, h)
            for dx in range(sp - 2, sp + 3):
                xs = x1 + dx
                if xs + tw >= W - 2:        # ô chạm mép trang: chữ có thể bị cắt, không đoán
                    continue
                win = darkd[:, xs:xs + tw]
                if win.shape != r.shape:
                    continue
                cov = (win & r).sum() / max(r.sum(), 1)
                other = (dark[y0:y1, xs:xs + tw] & ~r).sum() / max((~r).sum(), 1)
                if cov >= 0.97 and other < 0.3 and (best is None or r.sum() > best[0]):
                    best = (int(r.sum()), c, xs, r)
        return None if best is None else best[1:]

    def plan(self, g, rules, stem):
        """Dò + đọc + quyết định từng dòng của 1 trang xám -> Page. Mỗi dòng: n, doc (chữ đọc được), key, moi (chữ
        sẽ in), trang_thai (tu / soat / bo), kieu (tu / duyet / sua / ''), ap (sẽ đổi), ly_do, cal, alt, tail,
        thua (mảnh dấu chưa đọc quanh dòng), cùng chỗ in (size, x, base)."""
        H, W = g.shape
        gs, lab, st = self.glyphs(g)
        dark = g < DARK
        lines = []
        for L in self.lines(gs):
            x0, y0, x1, y1 = L['box']
            letters = [d for d in L['g'] if d['c'] not in '!?']
            cap = float(np.median([d['b'][3] - d['b'][1] for d in letters])) if letters else float(y1 - y0)
            text = ' '.join(''.join(d['c'] for d in wd) for wd in L['words'])
            if cap < MIN_CAP or len(re.findall('[A-Z]', text)) < 2:
                continue
            cal, alt = self.check(L, lab)
            if cal < CAL_OK:
                continue
            text = re.sub(r' +([!?])', r'\1', text)
            text = re.sub(r'!I(?=\s|$)', '!!', text)
            ids = {i for d in L['g'] for i in d['ids']}
            h = y1 - y0
            why = []
            if alt >= cal - MARGIN:
                why.append(f"font đích cũng khớp {alt:.2f} — không chắc là chữ lệch font")
            # mảnh nhỏ chưa đọc được nằm gọn quanh dòng: dấu : . , ' * ... -> phải xoá cùng
            rx0, rx1 = x0 - 1.0 * h, x1 + 1.0 * h
            ry0, ry1 = y0 - 0.25 * h, y1 + 0.25 * h
            sx0, sx1 = max(0, int(rx0)), min(W, int(rx1) + 1)
            sy0, sy1 = max(0, int(ry0)), min(H, int(ry1) + 1)
            thua = []
            for i in np.unique(lab[sy0:sy1, sx0:sx1]):
                if i == 0 or i in ids:
                    continue
                x, y, w, hh, a = st[i]
                # dấu câu >= ~0,2 cao chữ; chấm tram / bụi nhỏ hơn 0,12 thì không tính
                if (a >= 3 and max(w, hh) >= 0.12 * cap and x >= rx0 and x + w <= rx1 and y >= ry0 and y + hh <= ry1
                        and hh <= 1.3 * h and w <= 1.5 * h):
                    thua.append(int(i))
            if thua:
                why.append(f"còn {len(thua)} dấu chưa đọc được quanh dòng (xoá cùng khi duyệt — chữ mới ghi đủ ở \"sua\")")
            # sát nét khác (viền bóng / tranh) ngay đầu hoặc cuối dòng
            tail = None
            r0, r1 = int(y0 + 0.15 * h), max(int(y0 + 0.15 * h) + 1, int(y1 - 0.15 * h))
            zone = dark[r0:r1] & ~np.isin(lab[r0:r1], list(ids) + thua)
            cw = max(2, int(0.3 * h))         # chữ dính viền bắt đầu ngay sau khe chữ (~0,05-0,15 cao chữ)
            right = zone[:, x1 + 1:x1 + 1 + cw]
            left = zone[:, max(0, x0 - cw):max(0, x0 - 1)]
            if right.size and right.mean() > 0.02:
                tail = self._tail(L, dark)
                why.append(f"cuối dòng dính viền / nét vẽ — tool đoán thêm chữ \"{tail[0]}\" (xoá chữ đó có thể "
                           f"làm đứt viền — xem ảnh)" if tail else
                           "cuối dòng sát viền / nét vẽ")
            if left.size and left.mean() > 0.02:
                why.append("đầu dòng sát viền / nét vẽ")
            if x0 <= 2 or y0 <= 2 or x1 >= W - 3 or y1 >= H - 3:
                why.append("chạm mép trang (có thể mất chữ)")
            lines.append(dict(box=(int(x0), int(y0), int(x1), int(y1)), cap=cap, base=int(y1), ids=sorted(ids),
                              doc=text, cal=round(cal, 3), alt=round(alt, 3), tail=tail, thua=thua, ly_do=why))
        lines.sort(key=lambda d: (d['box'][1], d['box'][0]))
        cnt = {}
        for d in lines:
            cnt[d['doc']] = cnt.get(d['doc'], 0) + 1
        seen = {}
        for n, d in enumerate(lines, 1):
            seen[d['doc']] = seen.get(d['doc'], 0) + 1
            d['n'] = n
            d['key'] = f"{stem}:{d['doc']}"
            keys = (d['key'], f"{d['key']}#{seen[d['doc']]}") if cnt[d['doc']] > 1 else (d['key'],)
            d['khoa'] = keys[-1]                     # khoá in ra danh sách (trùng chữ trong trang -> #k)
            de_xuat = d['doc'] + (d['tail'][0] if d['tail'] else '')
            if any(k in rules['bo'] for k in keys):
                d.update(trang_thai='bo', kieu='', ap=False, moi=de_xuat)
            elif any(k in rules['sua'] for k in keys):
                d.update(trang_thai='soat' if d['ly_do'] else 'tu', kieu='sua', ap=True,
                         moi=str(next(rules['sua'][k] for k in reversed(keys) if k in rules['sua'])))
            elif any(k in rules['duyet'] for k in keys):
                d.update(trang_thai='soat' if d['ly_do'] else 'tu', kieu='duyet', ap=True, moi=de_xuat)
            else:
                d.update(trang_thai='soat' if d['ly_do'] else 'tu', kieu='tu' if not d['ly_do'] else '',
                         ap=not d['ly_do'], moi=de_xuat)
            # dòng duyệt / sửa: xoá cả ký tự đoán dính viền khi chữ mới dài hơn chữ đọc được
            d['xoa_tail'] = bool(d['tail']) and (
                d['kieu'] == 'duyet' or (d['kieu'] == 'sua' and len(d['moi'].replace(' ', '')) > len(d['doc'].replace(' ', ''))))
        page = Page(g, lab, lines)
        self._layout(page)
        return page

    # ---------------------------------------------------------------- xoá + in
    def _erase(self, page, sel, out, full=False):
        """Xoá chữ cũ của các dòng sel trong out (float). Dòng duyệt / sửa xoá cả dấu thừa quanh dòng; ký tự đoán dính
        viền xoá theo xoa_tail. full = xem trước như khi duyệt hết (dòng chưa duyệt coi như duyệt nguyên đề xuất)."""
        g, lab = page.g, page.lab
        H, W = g.shape
        for d in sel:
            x0, y0, x1, y1 = d['box']
            use_tail = bool(d['tail']) and (d['xoa_tail'] or (full and d['kieu'] != 'sua'))
            if use_tail:
                x1 = d['tail'][1] + d['tail'][2].shape[1]
            pad = max(3, int(1.2 * (y1 - y0)))
            X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
            ok = full or d['kieu'] in ('duyet', 'sua')
            m = np.isin(lab[Y0:Y1, X0:X1], d['ids'] + (d['thua'] if ok else []))
            m = cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
            if use_tail:                    # chữ dính viền: xoá theo khuôn, nở 1 px (đỡ đứt viền bóng)
                _, tx, r = d['tail']
                t = np.zeros_like(m)
                ty = y0 - Y0
                sub = t[ty:ty + r.shape[0], tx - X0:tx - X0 + r.shape[1]]
                sub |= r[:sub.shape[0], :sub.shape[1]]
                m |= cv2.dilate(t.astype(np.uint8), K3) > 0
            # tô bằng màu giấy TẠI CHỖ (trung bình các điểm giấy quanh đó): giấy ngà / loang không thành mảng trắng
            reg = out[Y0:Y1, X0:X1]
            w = ((reg > FREE) & ~m).astype(np.float32)
            k = max(9, int(1.5 * (y1 - y0)) | 1)
            den = cv2.blur(w, (k, k))
            bg = np.where(den > 0.05, cv2.blur(reg * w, (k, k)) / np.maximum(den, 1e-6), 255.0)
            sel = m & (np.abs(reg - bg) > 3)    # cả quầng sáng do làm nét quanh nét chữ cũ (giấy không trắng tinh)
            reg[sel] = bg[sel]

    def _layout(self, page):
        """Chỗ in mỗi dòng (không phải 'bo'): cỡ = chữ hoa cao bằng chữ cũ, chân chữ cũ, tâm ngang cũ — dịch trong
        dải trống của dòng (sau khi xoá chữ cũ) / co tối đa SHRINK nếu tràn; vẫn tràn -> ghi lý do (thành SOÁT)."""
        sel = [d for d in page.lines if d['trang_thai'] != 'bo']
        if not sel:
            return
        tmp = page.g.astype(np.float32).copy()
        self._erase(page, sel, tmp, full=True)
        H, W = page.g.shape
        for d in sel:
            x0, y0, x1, y1 = d['box']
            if d['tail'] and (d['xoa_tail'] or d['kieu'] != 'sua'):   # chữ đoán dính viền nằm trong dòng
                x1 = d['tail'][1] + d['tail'][2].shape[1]
            cap = d['cap']
            size0 = max(6, round(cap / self.cap_dst))
            band = tmp[y0:y1] > FREE
            free = band.all(0)
            c = int(round((x0 + x1) / 2))
            if not free[c]:
                L = R = c
            else:
                L = c
                while L > 0 and free[L - 1]:
                    L -= 1
                R = c
                while R < W - 1 and free[R + 1]:
                    R += 1
            m = max(3, 0.2 * cap)
            avail = (R - L) - 2 * m
            size, w = size0, self._width(d['moi'], size0)
            if w > avail and avail > 0:
                size = max(int(size0 * SHRINK), int(size0 * avail / w))
                w = self._width(d['moi'], size)
            over = w > avail
            if over:
                d['ly_do'].append(f"chữ mới rộng hơn chỗ trống (đã co còn {SHRINK:.0%})")
                if d['kieu'] == 'tu':           # tự đổi thì phải vừa chỗ
                    d.update(trang_thai='soat', kieu='', ap=False)
                elif d['kieu'] in ('duyet', 'sua'):
                    d['trang_thai'] = 'soat'
            cx = (x0 + x1) / 2
            if not over:
                cx = min(max(cx, L + m + w / 2), R - m - w / 2)
            d.update(size=int(size), cx=float(cx), w=int(w))

    def _width(self, text, size):
        l, t, r, b = ImageFont.truetype(self.dst, size).getbbox(text, anchor='ls')
        return r - l

    def render(self, page, preview=False):
        """Ảnh trang sau khi đổi: dòng ap (hoặc mọi dòng không 'bo' nếu preview) xoá chữ cũ + in chữ mới."""
        sel = [d for d in page.lines if (d['trang_thai'] != 'bo' if preview else d['ap'])]
        if not sel:
            return page.g
        out = page.g.astype(np.float32).copy()
        self._erase(page, sel, out, full=preview)
        H, W = out.shape
        for d in sel:
            f = ImageFont.truetype(self.dst, d['size'])
            l, t, r, b = f.getbbox(d['moi'], anchor='ls')
            x = d['cx'] - (l + r) / 2
            X0, Y0 = int(max(0, x + l - 4)), int(max(0, d['base'] + t - 4))
            X1, Y1 = int(min(W, x + r + 5)), int(min(H, d['base'] + b + 5))
            if X1 <= X0 or Y1 <= Y0:
                continue
            im = Image.new('L', (X1 - X0, Y1 - Y0), 0)
            ImageDraw.Draw(im).text((x - X0, d['base'] - Y0), d['moi'], font=f, fill=255, anchor='ls')
            a = np.asarray(im).astype(np.float32) / 255
            out[Y0:Y1, X0:X1] *= 1 - a
        return np.clip(out + 0.5, 0, 255).astype(np.uint8)


# ================================================================ soát

TT_VI = dict(tu='TỰ', soat='SOÁT', bo='BỎ')


def status_vi(d, applied=None):
    if applied is not None:
        return 'ĐÃ ĐỔI' if applied else ('BỎ' if d['trang_thai'] == 'bo' else 'CHƯA ĐỔI')
    if d['kieu'] in ('duyet', 'sua'):
        return 'DUYỆT' if d['kieu'] == 'duyet' else 'SỬA'
    return TT_VI[d['trang_thai']]


def sheet(before, after, page, path, title):
    """Ảnh trước | sau 1 trang: bên trước khung xanh = đổi, cam = cần soát / chưa đổi, xám = bỏ; số = #n trong danh sách."""
    sc = min(1.0, 1600 / before.shape[0])
    a = Image.fromarray(before).convert('RGB')
    b = Image.fromarray(after).convert('RGB')
    d = ImageDraw.Draw(a)
    for ln in page.lines:
        x0, y0, x1, y1 = ln['box']
        col = (150, 150, 150) if ln['trang_thai'] == 'bo' else ((0, 170, 0) if ln['ap'] else (240, 120, 0))
        w = max(2, round(2 / sc))
        d.rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], outline=col, width=w)
        d.text((x0 - 4, y0 - 6 - 11 / sc), f"#{ln['n']}", fill=col)
    if sc < 1:
        a = a.resize((round(a.width * sc), round(a.height * sc)), Image.LANCZOS)
        b = b.resize(a.size, Image.LANCZOS)
    sh = Image.new('RGB', (a.width * 2 + 12, a.height + 22), (90, 90, 90))
    sh.paste(a, (0, 22))
    sh.paste(b, (a.width + 12, 22))
    ImageDraw.Draw(sh).text((4, 5), title, fill=(255, 255, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    sh.save(path, quality=88)


def list_rows(name, page, applied_mode=False):
    """Dòng cho file danh-sach.txt của 1 trang."""
    rows = []
    for d in page.lines:
        st = status_vi(d, d['ap'] if applied_mode else None)
        moi = '' if d['moi'] == d['doc'] else f' -> "{d["moi"]}"'
        why = ('  — ' + '; '.join(d['ly_do'])) if d['ly_do'] else ''
        rows.append(f"  {name:<10} #{d['n']:<2} {st:<8} \"{d['khoa']}\"{moi}{why}")
    return rows
