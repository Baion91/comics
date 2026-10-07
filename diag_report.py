#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bộ đo reader (diag): đọc .reader-meta/diag/{client,server}.jsonl -> báo cáo chữ.

Nguồn dữ liệu (đều nằm trên máy SERVER):
  - server.jsonl : reader_server.py ghi 1 dòng / request — loại (nav/prefetch/img/...),
                   thời gian xử lý, số ảnh phải đo kích thước (mới/có sẵn), số request
                   đồng thời; thêm dòng nền: k='libscan' (quét lại thư viện), k='dims'
                   (lưu kho kích thước), selfping 5' kèm RAM reader + số liệu kho.
  - client.jsonl : trình duyệt gửi POST /api/diag — Navigation Timing (SW khởi động,
                   byte đầu, trang hiện), bấm -> trang mới, đứng luồng chính, sự kiện SW.
Xem báo cáo:
  - python diag_report.py [số giờ]         (in ra màn hình, mặc định 48h gần nhất)
  - bot Telegram /diag                      (tóm tắt + link báo cáo đầy đủ)
  - GET /api/diag/report?k=<token>[&h=giờ]  (qua link reader; token ở diag/token.txt)
  - GET /api/diag/raw?k=<token>&f=client|server[&n=dòng]  (dữ liệu thô)
Tắt ghi: tạo file .reader-meta/diag-off (bot: /diag off).
"""

import json
import os
import secrets
import statistics
import sys
import time

FILES = ("client", "server")


def diag_dir(meta_dir):
    return os.path.join(meta_dir, "diag")


def get_token(meta_dir):
    """Token bảo vệ link báo cáo (tạo 1 lần, lưu diag/token.txt)."""
    d = diag_dir(meta_dir)
    p = os.path.join(d, "token.txt")
    try:
        with open(p, encoding="utf-8") as f:
            tok = f.read().strip()
        if tok:
            return tok
    except OSError:
        pass
    os.makedirs(d, exist_ok=True)
    tok = secrets.token_urlsafe(12)
    try:
        with open(p, "x", encoding="utf-8") as f:
            f.write(tok)
    except FileExistsError:                  # tiến trình khác vừa tạo -> dùng của nó
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    return tok


def check_token(meta_dir, tok):
    if not tok:
        return False
    try:
        return secrets.compare_digest(tok, get_token(meta_dir))
    except Exception:
        return False


def _paths(meta_dir, name):
    d = diag_dir(meta_dir)
    return [os.path.join(d, name + ".old.jsonl"), os.path.join(d, name + ".jsonl")]


def load(meta_dir, name, since_ms=0):
    out = []
    for p in _paths(meta_dir, name):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(r, dict) and (r.get("rt") or r.get("t") or 0) >= since_ms:
                        out.append(r)
        except OSError:
            pass
    return out


def tail(meta_dir, name, n=3000):
    lines = []
    for p in _paths(meta_dir, name):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                lines.extend(f.readlines())
        except OSError:
            pass
    return "".join(lines[-max(1, n):])


def clear(meta_dir):
    n = 0
    for name in FILES:
        for p in _paths(meta_dir, name):
            try:
                os.remove(p)
                n += 1
            except OSError:
                pass
    return n


# --- tiện ích thống kê ---------------------------------------------------------

def _pct(vals, q):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]


def _fmt(x):
    if x is None:
        return "–"
    return f"{x / 1000:.1f}s" if x >= 1000 else f"{int(round(x))}ms"


def _stat(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return "–"
    return f"{_fmt(statistics.median(v))} / {_fmt(_pct(v, .9))} / max {_fmt(max(v))}"


def _statb(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return "–"
    f = lambda b: f"{b / 1000:.1f}KB"
    return f"{f(statistics.median(v))} / {f(_pct(v, .9))} / max {f(max(v))}"


def _hm(ms):
    return time.strftime("%d/%m %H:%M:%S", time.localtime((ms or 0) / 1000))


def _swboot(r):
    """Thời gian SW khởi động trước khi xử lý điều hướng (0 nếu SW đang sống)."""
    ws, fs = r.get("workerStart"), r.get("fetchStart")
    if ws and fs and fs >= ws:
        return fs - ws
    return None


def _shown(r):
    return r.get("domContentLoadedEventEnd") or r.get("domInteractive")


def _dev(r):
    d = r.get("d") or "?"
    return ("app" if r.get("sa") else "web") + "-" + d


# --- báo cáo -------------------------------------------------------------------

def build_report(meta_dir, hours=48.0, brief=False):
    since = int((time.time() - hours * 3600) * 1000)
    cl = load(meta_dir, "client", since)
    sv = load(meta_dir, "server", since)
    L = []
    add = L.append
    add(f"BÁO CÁO BỘ ĐO READER — {hours:g}h gần nhất (đến {_hm(time.time() * 1000)})")
    add(f"client: {len(cl)} bản ghi | server: {len(sv)} request")
    add("Ký hiệu: trung vị / p90 / max. 'app' = web app (standalone), 'web' = tab trình duyệt;"
        " ios/pc theo thiết bị.")

    navs = [r for r in cl if r.get("ev") == "nav"]

    # [1] mở trang theo nhóm
    add("")
    add("[1] MỞ TRANG — SW khởi động | byte đầu | trang hiện (DCL) | n")
    groups = {}
    for r in navs:
        li = "đăng nhập" if r.get("li") else ("khách" if r.get("li") is False else "?")
        groups.setdefault((_dev(r), r.get("pk") or "?", li), []).append(r)
    for key in sorted(groups):
        g = groups[key]
        add(f"  {key[0]:<8} {key[1]:<6} {key[2]:<9} | SW {_stat([_swboot(r) for r in g])}"
            f" | byte đầu {_stat([r.get('responseStart') for r in g])}"
            f" | hiện {_stat([_shown(r) for r in g])} | n={len(g)}")

    # [2] lần mở chậm nhất
    slow = sorted(navs, key=lambda r: -(_shown(r) or 0))[:5 if brief else 12]
    add("")
    add("[2] LẦN MỞ CHẬM NHẤT (giờ | thiết bị | trang | kiểu | SW điều khiển | đăng nhập |"
        " SW khởi động | byte đầu | hiện | bấm→bắt đầu)")
    for r in slow:
        add(f"  {_hm(r.get('rt'))} {_dev(r):<8} {(r.get('path') or '')[:48]:<48} "
            f"{r.get('type', '?'):<12} ctl={int(bool(r.get('ctl')))} li={r.get('li')} "
            f"| {_fmt(_swboot(r))} | {_fmt(r.get('responseStart'))} | {_fmt(_shown(r))}"
            f" | {_fmt(r.get('tap'))}" + (" [rời trang trước khi đo đủ]" if r.get("early") else ""))

    # [3] bấm -> trang mới
    taps = [r for r in navs if r.get("tap") is not None]
    add("")
    add("[3] BẤM → TRANG MỚI CÓ BYTE ĐẦU (tap + responseStart)")
    if taps:
        tot = [(r.get("tap") or 0) + (r.get("responseStart") or 0) for r in taps]
        add(f"  n={len(taps)} | {_stat(tot)}")
        for r in sorted(taps, key=lambda r: -((r.get('tap') or 0) + (r.get('responseStart') or 0)))[:5]:
            add(f"  {_hm(r.get('rt'))} {(r.get('path') or '')[:60]} → "
                f"{_fmt((r.get('tap') or 0) + (r.get('responseStart') or 0))}")
    else:
        add("  (chưa có)")

    # [4] Service Worker
    swev = []
    for r in navs:
        sw = r.get("sw") or {}
        if isinstance(sw, dict):
            swev.extend(e for e in (sw.get("ev") or []) if isinstance(e, dict))
    nav_ev = [e for e in swev if e.get("e") == "nav"]
    add("")
    add("[4] SERVICE WORKER")
    if nav_ev:
        hits = [e for e in nav_ev if e.get("hit")]
        miss = [e for e in nav_ev if not e.get("hit")]
        dups = [e for e in nav_ev if e.get("dup")]
        add(f"  điều hướng: {len(nav_ev)} | trúng cache {len(hits)} | ra mạng {len(miss)}"
            f" | chờ prefetch sẵn có {len(dups)}")
        cold = [e for e in nav_ev if (e.get("age") or 0) < 2000]
        warm = [e for e in nav_ev if (e.get("age") or 0) >= 2000]
        add(f"  mở cache: SW vừa khởi động {_stat([e.get('open') for e in cold])} (n={len(cold)})"
            f" | SW đang chạy {_stat([e.get('open') for e in warm])}"
            f" | tra cache {_stat([e.get('match') for e in nav_ev])}")
        add(f"  mạng khi trượt cache {_stat([e.get('net') for e in miss])}")
        add(f"  SW vừa khởi động (<2s) lúc điều hướng: "
            f"{sum(1 for e in nav_ev if (e.get('age') or 0) < 2000)}/{len(nav_ev)}")
    pf = [e for e in swev if e.get("e") == "pf"]
    drops = sum(e.get("n") or 0 for e in swev if e.get("e") == "pfdrop")
    add(f"  prefetch: {len(pf)} lượt, mạng {_stat([e.get('net') for e in pf])}; bỏ khỏi hàng đợi {drops}")
    to = sum(1 for r in navs if isinstance(r.get("sw"), dict) and r["sw"].get("timeout"))
    if to:
        add(f"  SW KHÔNG trả lời câu hỏi đo: {to} lần")

    # [5] đứng luồng chính
    gaps = []
    for r in cl:
        if r.get("ev") == "gaps":
            for g in r.get("g") or []:
                if isinstance(g, list) and len(g) == 2:
                    gaps.append((g[1], g[0], r))
    add("")
    add("[5] ĐỨNG LUỒNG CHÍNH (>350ms khi trang đang hiện)")
    if gaps:
        add(f"  {len(gaps)} lần, tổng {_fmt(sum(g[0] for g in gaps))}")
        for g, at, r in sorted(gaps, key=lambda x: -x[0])[:3 if brief else 8]:
            add(f"  {_hm(r.get('rt'))} {_dev(r):<8} {(r.get('path') or '')[:50]} "
                f"tại {_fmt(at)} dài {_fmt(g)}")
    else:
        add("  (không có)")

    res = [r for r in cl if r.get("ev") == "resume"]
    bf = [r for r in cl if r.get("ev") == "bfcache"]
    add(f"  mở lại app từ nền không tải lại trang: {len(res)} | khôi phục bfcache: {len(bf)}")

    # [6] server
    real = [r for r in sv if r.get("k") not in ("selfping", "sweep", "libscan", "dims")]
    add("")
    add("[6] SERVER theo loại request (thời gian xử lý)")
    kinds = {}
    for r in real:
        kinds.setdefault(r.get("k") or "?", []).append(r)
    for k in sorted(kinds, key=lambda k: -len(kinds[k])):
        g = kinds[k]
        add(f"  {k:<10} n={len(g):<6} {_stat([r.get('ms') for r in g])}")
    add(f"  get_library (mỗi request) {_stat([r.get('lib') for r in real])}")
    tot = {k: sum(r.get(k) or 0 for r in real) for k in ("dc", "dp", "dw", "dq")}
    add(f"  kích thước ảnh: đo mới (đọc đầu file) {tot['dc']} | phải mở Pillow {tot['dp']}"
        f" | có sẵn trong kho {tot['dw']} | hết ngân sách, để đo nền {tot['dq']}")
    add(f"  số request đồng thời tối đa: {max([r.get('fl') or 0 for r in real] or [0])}")
    dm = [r for r in sv if r.get("k") == "dims"]
    if dm:
        r = dm[-1]
        add(f"  kho kích thước (lưu gần nhất {_hm(r.get('t'))}): {r.get('ch')} chương,"
            f" {r.get('img')} ảnh, {r.get('kb')}KB, ghi {_fmt(r.get('ms'))} | {len(dm)} lần lưu,"
            f" dọn {sum(x.get('pr') or 0 for x in dm)} chương đã xoá")
    ls = [r for r in sv if r.get("k") == "libscan"]
    if ls:
        why = {}
        for r in ls:
            why[r.get("why")] = why.get(r.get("why"), 0) + 1
        add(f"  quét lại thư viện: {len(ls)} lần ({', '.join(f'{k} {v}' for k, v in sorted(why.items()))})"
            f" | quét {_stat([r.get('ms') for r in ls])} | chữ ký {_stat([r.get('sig') for r in ls])}"
            f" | {ls[-1].get('n')} truyện, {ls[-1].get('ch')} chương")
    sp = [r for r in sv if r.get("k") == "selfping"]
    mem = [r for r in sp if r.get("ws")]
    if sp:
        line = f"  tự kiểm 5': n={len(sp)} {_stat([r.get('ms') for r in sp])}"
        if mem:
            ws = [r["ws"] for r in mem]
            r = mem[-1]
            line += (f" | RAM reader {min(ws)}–{max(ws)}MB (gần nhất {_hm(r.get('t'))}: {r['ws']}MB,"
                     f" private {r.get('pm')}MB; kho {r.get('dch')} chương, đang đo dở"
                     f" {r.get('dpart')}; từ lúc chạy: đầu file {r.get('dhd')}, Pillow {r.get('dpil')})")
        add(line)
    sw = [r for r in sv if r.get("k") == "sweep"]     # luồng quét cả thư viện (đã bỏ 07/10)
    if sw:
        r = sw[-1]
        add(f"  luồng đo kích thước nền: {r.get('p')} lúc {_hm(r.get('t'))} — {r.get('ch')} chương,"
            f" đo mới {r.get('new')} ảnh, có sẵn {r.get('had')}, chạy {_fmt(r.get('ms'))}"
            f" (bắt đầu {_hm(sw[0].get('t') - (sw[0].get('ms') or 0))})")

    add("")
    add("[7] REQUEST SERVER CHẬM NHẤT (giờ | loại | path | ms | ảnh đo mới/có sẵn | đồng thời | thư viện)")
    for r in sorted(real, key=lambda r: -(r.get("ms") or 0))[:6 if brief else 15]:
        add(f"  {_hm(r.get('t'))} {r.get('k', '?'):<9} {(r.get('p') or '')[:55]:<55} "
            f"{_fmt(r.get('ms'))} | {r.get('dc', 0)}/{r.get('dw', 0)} | {r.get('fl')} | {_fmt(r.get('lib'))}")

    # [8] render trùng: cùng path, 1 prefetch + 1 điều hướng, chồng thời gian
    # (chỉ tính cặp có prefetch — đúng kịch bản prefetch + bấm thật cùng một chương)
    docs = [r for r in real if r.get("k") in ("prefetch", "nav")]
    byp = {}
    for r in docs:
        byp.setdefault((r.get("p"), r.get("d")), []).append(r)
    dup = []
    for (p, _), g in byp.items():
        g.sort(key=lambda r: r.get("t") or 0)
        for a, b in zip(g, g[1:]):
            if ("prefetch" in (a.get("k"), b.get("k"))
                    and (b.get("t") or 0) < (a.get("t") or 0) + (a.get("ms") or 0)):
                dup.append((a, b))
    add("")
    add(f"[8] RENDER TRÙNG (prefetch + request khác cùng trang, chồng thời gian): {len(dup)}")
    for a, b in dup[:5]:
        add(f"  {_hm(a.get('t'))} {(a.get('p') or '')[:60]} {a.get('k')}+{b.get('k')}")

    # [9] /api/state
    st = [r for r in real if r.get("p") == "/api/state" and r.get("m") == "G"]
    add(f"[9] GET /api/state: n={len(st)} | dung lượng {_statb([r.get('b') for r in st])}"
        f" | xử lý {_stat([r.get('ms') for r in st])}")

    # [10] lưu trữ
    add("")
    add("[10] LƯU TRỮ TRÊN THIẾT BỊ (bản đo gần nhất mỗi thiết bị)")
    # dung lượng và số mục cache lấy RIÊNG bản gần nhất có từng thứ (có lần đo có
    # dung lượng mà SW không kịp trả số mục -> trước đây in nhầm 'cache {}')
    last_st, last_cc = {}, {}
    for r in navs:
        if r.get("st"):
            last_st[_dev(r)] = r
        if isinstance(r.get("sw"), dict) and r["sw"].get("cc"):
            last_cc[_dev(r)] = r
    for dev in sorted(set(last_st) | set(last_cc)):
        rs, rc = last_st.get(dev), last_cc.get(dev)
        line = f"  {dev}:"
        if rs:
            stg, ls = rs.get("st") or {}, rs.get("ls") or {}
            line += (f" {_hm(rs.get('rt'))} dùng {(stg.get('u') or 0) / 1e6:.1f}MB / quota "
                     f"{(stg.get('q') or 0) / 1e6:.0f}MB | localStorage {ls.get('n')} khoá "
                     f"{(ls.get('sz') or 0) / 1000:.0f}K ký tự, chsort={ls.get('chsort')}")
        if rc:
            line += f" | số mục cache ({_hm(rc.get('rt'))}): {rc['sw']['cc']}"
        add(line)
    if not last_st and not last_cc:
        add("  (chưa có — đo ở trang chủ, tối đa 30 phút/lần)")
    vers = sorted({(r.get("sw") or {}).get("ver") for r in navs
                   if isinstance(r.get("sw"), dict) and (r.get("sw") or {}).get("ver")})
    if vers:
        add(f"  phiên bản SW đã thấy: {', '.join(vers)}")
    return "\n".join(L)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    h = float(sys.argv[1]) if len(sys.argv) > 1 else 48
    meta = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".reader-meta")
    print(build_report(meta, h))
    print(f"\nLink báo cáo: <link reader>/api/diag/report?k={get_token(meta)}")
