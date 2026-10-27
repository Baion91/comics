#!/usr/bin/env python3
"""comix.to (Comick) — LOOP TẢI RIÊNG, không đi qua core.run().

Vì sao không theo hợp đồng provider thường (providers.py):
- API trả response MÃ HÓA {"e": "..."} + token ký per-request (`_=`, sinh bởi
  secure-*.js đổi theo build) -> KHÔNG craft request bằng requests được.
- Cách duy nhất đã kiểm chứng: mở trình duyệt thật (Playwright HEADFUL), để chính
  JS của site gọi API + giải mã, rồi ĐỌC dữ liệu đã giải mã trong page (SNAP_JS).
  Trước 10/2026: hook JSON.parse bắt object {status, result}. Từ ~10/2026 (phát hiện
  27/10): site giải mã bằng parser JSON TỰ VIẾT + XÁO tên trường -> đọc React Query
  cache, nhận diện trường THEO GIÁ TRỊ rồi đổi về dạng cũ (_canon_chapters,
  _pages_from_detail); cả 2 đường cùng chạy, đường nào ra dữ liệu thì dùng. Không
  hiểu được dữ liệu -> SiteChanged (báo rõ, không giả làm lỗi mạng).
  Browser CHỈ lo metadata (danh sách chương + URL ảnh); tải ảnh vẫn bằng HTTP qua
  PoliteGate của comics_core. CDN cũ *.wowpicN.store đòi Referer https://comix.to/;
  CDN mới NNN.<ngẫu nhiên>.site lại CHẶN Referer đó -> Referer gửi theo host
  (ComixImageClient), kèm domain CDN dự phòng site cho sẵn.
- 1 chương có NHIỀU bản upload (official + các nhóm scan) -> phải CHỌN bản, và khi
  chạy lại có thể THAY bản scan cũ bằng bản Official mới xuất hiện. Logic này không
  có chỗ trong run() generic nên viết loop riêng, 5 site cũ không bị đụng.

Luật chọn bản per số chương (user chốt 09/08, cập nhật 19/08 & 21/08/2026):
  1. Lọc language == "en". Có bản isOfficial=true (tick "v") -> lấy official.
     Nhiều official song song -> theo HẠNG NHÓM (OFFICIAL_GROUP_RANK: TappyToon cao
     nhất ... Webcomic thấp nhất), cùng hạng thì id lớn nhất (mới nhất) trước.
  2. Không có official -> ưu tiên bản scan CÓ tên nhóm, id LỚN NHẤT trước (mới nhất);
     HẾT bản có nhóm mới tới bản KHÔNG có tên nhóm, id lớn nhất trước. Lý do: bản
     "no group" hay là raw/batch đè lên bản nhóm scan cũ hơn nhưng chỉn chu hơn
     (vd Dai ch.345-349). Cả số chương chỉ có bản không nhóm -> vẫn tải (không bỏ).
  3. Bản được chọn mà 0 trang (khóa/hỏng) -> thử ứng viên kế tiếp.

Upgrade -> official (sidecar `.source.json` trong folder chương):
  - Trên đĩa là official -> BỎ QUA vĩnh viễn (không tải lại).
  - Trên đĩa CHƯA phải official mà comix nay có bản "v" -> tải official vào
    downloads/.comix-tmp/ (reader bỏ qua folder đầu-dấu-chấm), ĐỦ ảnh mới tráo folder;
    tên folder GIỮ "Chapter N" (không gắn title) để bookmark/tiến trình không mất.
    "Chưa phải official" GỒM cả chương tải từ SITE KHÁC (Raven, Asura...) — folder có
    ảnh + .done nhưng KHÔNG có sidecar comix; trước đây bị coi là "đã xong" và skip
    (sự cố Dungeon Reset: 266 chương Raven bị bỏ qua). Nay khớp theo SỐ chương.
  - Chưa có "v" -> giữ nguyên, KHÔNG thay scan bằng scan (kể cả bản comix mới hơn).
  - Đang tải dở (chưa .done) -> tiếp đúng bản trong sidecar, tránh trộn ảnh 2 nhóm.

GHIM NHÓM (`--group NHÓM`, bot `/tai <link> [chương] NHÓM`; user chốt 02/09/2026):
  - Chỉ xét các bản của ĐÚNG nhóm đó (khớp tên không phân biệt hoa/thường/khoảng trắng,
    gõ một phần cũng được nếu không mơ hồ — xem resolve_pin). KHÔNG rơi về nhóm khác;
    chương không có bản nhóm đó -> báo + bỏ qua. Nhóm không có trên bộ -> thoát sớm kèm
    danh sách nhóm có trên bộ (tin ❌ của bot in dòng này) để user gõ lại.
  - Ghim ĐÈ cả 2 luật trên: đĩa đang Official (hoặc scan khác/bản ngoài) mà ghim nhóm
    khác -> tải bản ghim vào .comix-tmp rồi tráo folder (đường upgrade sẵn có).
  - Ghim BỀN theo chương: sidecar ghi thêm "pin": "<Nhóm>". Lượt sau KHÔNG ghim (kể cả
    auto-check hằng ngày) coi chương đó vẫn ghim nhóm ấy: đủ ảnh -> bỏ qua (KHÔNG thay
    bằng Official), dở -> tải tiếp đúng nhóm. Nếu không ghim bền thì auto-check đêm sau
    sẽ thay lại Official, công ghim mất.
  - Bỏ ghim: `--group auto` (bot: `/tai <link> <chương> auto`) -> xoá "pin" trong sidecar
    rồi chạy luật mặc định ngay lượt đó (có Official thì thay). Đổi nguồn: ghim nhóm khác.
  - Quyết định have/replace/fetch của 1 chương nằm ở `_chapter_plan()` — dùng CHUNG cho
    vòng lặp tải và báo cáo sớm Telegram, sửa luật chỉ sửa 1 chỗ.

File DẤU cấp truyện (Cách 1): cuối mỗi lần chạy, ghi `_COMIX_official_{off}-{total}.txt`
ở gốc folder truyện (nhìn thấy trong Explorer, reader/check bỏ qua) để phân biệt folder
comix với folder scan tải từ site khác -> user tự tay xoá folder scan trùng.

URL ảnh KHÔNG có đuôi file (https://80pd.wowpic1.store/i5/<hash>) -> tải về đặt
tạm .webp rồi sniff magic bytes, sai thì đổi đuôi (Comix thực tế trả webp).

Cloudflare: chạy headful + profile Chromium cố định (.reader-meta/comix-profile)
giữ cookie cf_clearance. Nếu dính challenge tương tác -> gửi Telegram (đọc
.reader-meta/notify-config.json, ưu tiên admin_chat_ids) nhắc người mở màn hình
server tick "Verify you are human", chờ tối đa 5 phút rồi tự chạy tiếp.

Chặn QUẢNG CÁO + bền với chập chờn: browser CHỈ cho request tới comix.to +
cloudflare.com (route abort mọi domain khác) và tự đóng popup — diệt gốc cú
quảng cáo đẩy trang rời comix giữa lúc load (nguyên nhân 'chưa bắt được ảnh
chương'). Ngoài ra `_pump` trả None (không raise), `fetch_pages`/list tự MỞ LẠI
vài lần; một chương lấy hụt -> rơi xuống bản khác, hết bản -> ghi 'để sau' rồi
ĐI TIẾP (KHÔNG để 1 chương làm chết cả bộ), lần chạy sau tự bù.

Playwright là DEP TÙY CHỌN — chỉ import khi tải comix; thiếu thì in hướng dẫn cài:
    pip install playwright && python -m playwright install chromium
"""

import base64
import io
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import comics_core as core

# Chromium của Playwright để TRONG PROJECT (.reader-meta/pw-browsers), KHÔNG dùng
# mặc định %LOCALAPPDATA%\ms-playwright: PC công ty chặn load DLL/manifest dưới
# AppData -> chrome.exe chết ngay từ CreateProcess với lỗi "side-by-side
# configuration is incorrect" (đã tét: cùng binary, chạy từ ổ project thì OK).
# Phải set TRƯỚC khi import playwright; cap-nhat.bat cũng set biến này khi
# `playwright install chromium` để tải browser vào đúng chỗ.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH",
                      str(core.META_DIR / "pw-browsers"))

BASE = "https://comix.to"
REFERER = "https://comix.to/"
PROFILE_DIR = core.META_DIR / "comix-profile"   # giữ cf_clearance qua các lần chạy
NOTIFY_CONFIG = core.META_DIR / "notify-config.json"
TMP_DIRNAME = ".comix-tmp"    # dưới thư mục --out; đầu-dấu-chấm -> reader/check bỏ qua
SIDECAR = ".source.json"      # bản nào đang nằm trong folder chương (id/nhóm/official)
RECOMPRESS_MIN_SAVE = 10      # % — chỉ THAY bản gốc bằng bản nén khi tiết kiệm >= mức này
                              # (đồng bộ --min-save của convert_webp.py; chống suy hao vô ích).
RECOMPRESS_Q = 85             # Re-nén ảnh comix tải về xuống mức WebP q này. Comix encode
                              # nhẹ tay (~q92) -> file to gấp ~1.6 lần Asura cho CÙNG pixel;
                              # hạ q85 nhẹ đi ~nửa (đối chứng ch335: 24.5MB->12MB) mà mắt
                              # thường không thấy khác bản Asura scan. Đổi bằng cờ --comix-q;
                              # --comix-q 0 = TẮT (giữ nguyên byte gốc từ site).
# MỐC GIẢI-XÁO ĐÚNG trên server. Trang TRÁO Ô (cờ s:1) có file ghi TRƯỚC mốc = bản xáo
# thô (code cũ không giải-xáo được) -> phải làm lại; ghi SAU mốc = đã giải-xáo đúng (từ
# 79d2509 trang s:1 CHỈ được ghi qua giải-xáo, hụt thì để thiếu chứ không ghi bản thô).
# Thay cho detector looks_scrambled làm cổng: detector ÂM TÍNH GIẢ trên trang gần-trắng
# (credit, TO BE CONTINUED, trang tựa: xáo mà chỉ ~2-3.9 điểm) -> /repair 02-03/09 bỏ sót
# 108 trang/92 chương. Chốt 27/09 bằng bằng chứng trên server: trang ghi lại sớm nhất là
# Farmer 02/09 12:45:06, soi tay 9 trang đầu/giữa/cuối 3 đợt repair đều sạch, không trang
# nào ghi lại trước đó. Khai +07 (giờ server) cho khỏi lệch múi. Xem [[comix-scramble-s-flag]].
UNSCRAMBLE_SINCE = datetime(2026, 9, 2, 12, 45,
                            tzinfo=timezone(timedelta(hours=7))).timestamp()
UNSCRAMBLE_SINCE_TXT = "02/09/2026 12:45"
UNSCR_FLAG = "unscr_ok"       # sidecar: chương đã soi trên comix + giải-xáo lại đủ theo mốc
                              # -> /repair bỏ qua luôn (khỏi chạm mạng mỗi lượt)
CHALLENGE_WAIT = 300          # giây chờ người xác minh Cloudflare trước khi bỏ cuộc
MAX_RELAUNCH = 3              # số lần TỰ dựng lại Chromium cho MỖI đợt sự cố (reset khi tải được thêm)
RELAUNCH_BACKOFF = 5.0        # giây nghỉ trước khi mở Chromium mới
FAIL_STREAK_LIMIT = 6         # số chương LIÊN TIẾP không lấy được ảnh (browser còn sống) -> dừng phiên
LAUNCH_WATCHDOG = 90          # giây tối đa cho CẢ khâu mở+setup Chromium; quá = nghi treo -> kill
LAUNCH_KILL_GRACE = 8         # giây chờ main-thread bật lỗi sau khi watchdog kill Chromium, trước khi os._exit
_NO_WINDOW = 0x08000000 if os.name == "nt" else 0   # đừng bật cửa sổ console con (powershell dọn)

# JSON.parse hook — add_init_script nên chạy lại MỖI navigation (window.__cap tự reset,
# không phình RAM). Chỉ giữ object dạng {status, result} (API comix), bỏ qua thứ khác.
HOOK_JS = """
(() => {
  const orig = JSON.parse.bind(JSON);
  window.__cap = [];
  JSON.parse = function (s, r) {
    const o = orig(s, r);
    try {
      if (o && typeof o === 'object' && o.status !== undefined && o.result)
        window.__cap.push(o);
    } catch (e) {}
    return o;
  };
})();
"""

# Ảnh chụp dữ liệu trang cho _pump: (1) rút window.__cap của HOOK_JS (định dạng CŨ) và
# (2) đọc React Query cache — định dạng MỚI (site đổi ~10/2026: giải mã bằng parser JSON
# TỰ VIẾT nên JSON.parse không còn thấy payload, xem _canon_chapters). QueryClient lấy từ
# props `client` của QueryClientProvider: đi NGƯỢC fiber (`__reactFiber$*`) từ phần tử
# DOM đầu tiên có fiber. Chỉ trả DỮ LIỆU query 'success' có chuỗi `needle` trong key hoặc
# dữ liệu (bỏ comments/recommended cho nhẹ); query không serialize được thì bỏ qua. Kèm
# chẩn đoán cho thông báo lỗi: react (trang đã render), client, total (số query), busy
# (query đang tải / lỗi API — query tắt 'pending'+'idle' không tính).
SNAP_JS = r"""
(needle) => {
  const cap = window.__cap || []; window.__cap = [];
  const isClient = c => !!c && typeof c.getQueryCache === 'function';
  let client = isClient(window.__rqc) ? window.__rqc : null, react = !!client;
  if (!client) {
    let tried = 0;
    for (const el of document.querySelectorAll('body *')) {
      const fk = Object.keys(el).find(k => k.startsWith('__reactFiber$'));
      if (!fk) continue;
      react = true;
      for (let f = el[fk], d = 0; f && d < 400 && !client; f = f.return, d++) {
        const p = f.memoizedProps;
        if (p && isClient(p.client)) client = p.client;
      }
      if (client || ++tried >= 40) break;
    }
    if (client) window.__rqc = client;
  }
  const queries = [];
  let total = 0, busy = 0;
  if (client) {
    for (const q of client.getQueryCache().getAll()) {
      total++;
      const st = q.state || {};
      if (st.fetchStatus === 'fetching' || st.status === 'error') busy++;
      const d = st.data;
      if (st.status !== 'success' || !d || typeof d !== 'object') continue;
      try {
        if (needle && !JSON.stringify(q.queryKey).includes(needle)
            && !JSON.stringify(d).includes(needle)) continue;
        queries.push({key: q.queryKey, data: d});
      } catch (e) {}
    }
  }
  return {cap: cap, react: react, client: !!client, total: total, busy: busy,
          queries: queries};
}
"""

# Giải-xáo trang TRÁO Ô (cờ s:1): dùng CHÍNH thuật toán của site nhưng KHÔNG đọc canvas.
# chunk secure-*.js xuất hàm `vs` (export 't'); vs(url) trả object có .apply(canvas) — nó
# tải ảnh xáo rồi VẼ CÁC Ô ĐÃ SẮP LẠI lên canvas bằng nhiều lệnh drawImage (lưới ô, vd
# 5×5 ô 188×277). Ta KHÔNG toDataURL (setup này chặn đọc pixel canvas -> ra rỗng, nghi
# chống-scrape) mà CHẶN drawImage để GHI LẠI BẢN ĐỒ Ô (sx,sy,sw,sh -> dx,dy,dw,dh), ĐỒNG
# THỜI tee window.fetch để BẮT ĐÚNG BYTES ảnh xáo mà vs nhận (CDN trả BIẾN THỂ XÁO KHÁC
# NHAU theo client: browser vs requests cùng URL khác hash -> tải lại bằng img_client là
# lệch bản đồ; đã đo 02/09). Python xếp lại bằng PIL trên chính bytes đó. Ghi tham số hàm
# KHÔNG cần compositing/đọc canvas nên chạy được cả khi server không màn hình / RDP ngắt.
# Ép requestAnimationFrame chạy đồng bộ để apply vẽ ngay trong lúc evaluate. Cần
# _route_filter mở wowpic cho fetch/xhr. Trả {idx: {w,h,ops:[{argc,a}],b64}} — null nếu hụt.
DESCRAMBLE_JS = r"""
async ({items, timeoutMs}) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let secUrl = null;
  for (let t = 0; t < 30 && !secUrl; t++) {
    secUrl = performance.getEntriesByType('resource').map(r => r.name)
      .find(n => /\/secure-[^\/]*\.js(\?|$)/.test(n));
    if (!secUrl) await sleep(200);
  }
  if (!secUrl) return {__error: 'secure.js not found'};
  let mod;
  try { mod = await import(secUrl); } catch (e) { return {__error: 'import: ' + e}; }
  const fns = (typeof mod.t === 'function') ? [mod.t]
              : Object.values(mod).filter(v => typeof v === 'function');
  const proto = CanvasRenderingContext2D.prototype;
  const origDraw = proto.drawImage;
  const origRAF = window.requestAnimationFrame;
  const origFetch = window.fetch;
  const isCdn = u => /wowpic\d*\.store/.test(String(u || ''));
  const toB64 = buf => {
    const u8 = new Uint8Array(buf); let s = '';
    for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000));
    return btoa(s);
  };
  const out = {};
  try {
    let depth = 0;   // rAF đồng bộ (có chặn đệ quy) -> apply vẽ NGAY, khỏi chờ khung hình
    window.requestAnimationFrame = (cb) => {
      if (depth < 300) { depth++; try { cb(performance.now()); } finally { depth--; } }
      return 0;
    };
    for (const it of items) {
      let rec = null;
      for (const fn of fns) {
        // TEE fetch: giữ lại bytes ảnh xáo mà vs nhận (clone response, không đụng luồng gốc)
        let captured = null;
        window.fetch = async function (input, init) {
          const resp = await origFetch.apply(this, arguments);
          try {
            const u = (typeof input === 'string') ? input : (input && input.url) || '';
            if (isCdn(u) && resp && resp.ok) captured = await resp.clone().arrayBuffer();
          } catch (e) {}
          return resp;
        };
        let obj = null;
        try {
          obj = await Promise.race([
            fn(it.url, new AbortController().signal),
            new Promise((_, rej) => setTimeout(() => rej(new Error('vs timeout')), timeoutMs)),
          ]);
        } catch (e) { window.fetch = origFetch; continue; }
        window.fetch = origFetch;
        if (!obj || typeof obj.apply !== 'function') continue;
        const ops = [];
        proto.drawImage = function (img, ...a) {   // a: [dx,dy]|[dx,dy,dw,dh]|[sx,sy,sw,sh,dx,dy,dw,dh]
          ops.push({argc: a.length, a: a});
          try { return origDraw.apply(this, [img, ...a]); } catch (e) { return; }
        };
        let c = null;
        try {
          c = document.createElement('canvas');
          obj.apply(c);            // vẽ NGAY (rAF đồng bộ) -> ops được ghi trong lúc này
          await sleep(30);
        } catch (e) {
        } finally {
          proto.drawImage = origDraw;
        }
        if (ops.length >= 1 && captured && captured.byteLength > 0) {
          rec = {w: c ? c.width : 0, h: c ? c.height : 0, ops: ops, b64: toB64(captured)};
          break;
        }
      }
      out[String(it.idx)] = rec;   // null nếu không ghi được lệnh drawImage / không bắt được bytes
    }
  } finally {
    proto.drawImage = origDraw;
    window.requestAnimationFrame = origRAF;
    window.fetch = origFetch;
  }
  return out;
};
"""


class BrowserGone(Exception):
    """Cửa sổ Chromium bị đóng/chết giữa chừng. run() bắt để TỰ DỰNG LẠI browser rồi
    tải tiếp (relaunch); quá MAX_RELAUNCH lần trong một đợt -> ném ra ngoài = fatal
    (thoát != 0 -> supervisor báo '❌ Lỗi tải' thay vì lặng lẽ '✅ Tải xong')."""


class FetchStalled(Exception):
    """Nhiều chương LIÊN TIẾP không lấy được ảnh dù browser CÒN SỐNG (nghi bị chặn IP
    mềm / site đổi API). Dừng phiên + báo lỗi thật, thay vì ghi 'để sau' cả bộ rồi
    thoát 0 khiến người dùng tưởng đã tải xong."""


class SiteChanged(RuntimeError):
    """Trang comix mở được nhưng tool KHÔNG đọc ra dữ liệu (site đổi cấu trúc/API) —
    thử lại vô ích, phải sửa code. run() bắt để in 1 dòng rõ ràng làm tin ❌ của bot.
    Thông điệp KHÔNG được chứa dấu hiệu lỗi mạng (NET_ERR_MARKERS của supervisor, vd
    'mạng chập chờn') kẻo supervisor giữ job thử lại âm thầm 4 lần (sự cố 27/10)."""


# --- Đọc dữ liệu site — định dạng XÁO TÊN (từ ~10/2026) ---------------------------
#
# Phát hiện 27/10/2026 (build 35595e3d...): API vẫn mã hoá {"e":..} nhưng site giải mã ra
# BYTES rồi parse bằng parser JSON TỰ VIẾT -> hook JSON.parse chỉ còn thấy phong bì; dữ
# liệu nay lấy từ React Query cache (SNAP_JS). Tên trường còn bị XÁO (items/meta ->
# t9/zV, isOfficial -> e8, url -> q4...) và nhiều khả năng đổi theo mỗi bản build, nên
# NHẬN DIỆN TRƯỜNG THEO GIÁ TRỊ (url chương, id khớp url, bool duy nhất...) rồi đổi về
# đúng dạng CŨ ({id, url, number, language, isOfficial, group, groupId}) — phần còn lại
# của file không phải biết gì. Tên trong KEY_HINTS CHỈ để phân xử khi nhiều trường cùng
# hợp lệ theo giá trị (tên xáo có thể bị gán nghĩa khác ở build sau -> không bao giờ tin
# một tên khi giá trị không khớp). Không chắc chắn -> SiteChanged, KHÔNG đoán bừa rồi tải
# nhầm bản. Xem [[comix-site-change-oct26]].

CH_URL_RE = re.compile(r"/title/([^/?#]+)/(\d+)-chapter-([^/?#]*)")
LANG_RE = re.compile(r"^[a-z]{2,3}(?:[-_][a-z0-9]{2,8})?$", re.I)
DOMAIN_RE = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$", re.I)
KEY_HINTS = {          # tên thật (định dạng cũ) + tên xáo quan sát được ở build 10/2026
    "url": ("url", "q4"), "id": ("id", "yH"), "number": ("number", "_x"),
    "language": ("language", "UC"), "isOfficial": ("isOfficial", "e8"),
    "group": ("group", "Jj"), "name": ("name", "ek"), "pages": ("pages", "rB"),
}
# URL ảnh -> URL cùng ảnh trên domain DỰ PHÒNG của CDN (site gửi kèm mỗi trang). Ghi ở
# main thread (fetch_pages), worker tải ảnh chỉ đọc (ComixImageClient.get).
_ALT_URLS = {}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _pick(cands, field):
    """1 ứng viên -> nó; nhiều -> tên trong KEY_HINTS[field]; vẫn mơ hồ -> None."""
    cands = sorted(set(cands))
    if len(cands) == 1:
        return cands[0]
    for h in KEY_HINTS.get(field, ()):
        if h in cands:
            return h
    return None


def _url_num(url):
    """'/title/x/123-chapter-53.2' -> 53.2 ; không có số -> None."""
    m = CH_URL_RE.search(url or "")
    try:
        return float(m.group(3)) if m and m.group(3) else None
    except ValueError:
        return None


def _canon_group(g):
    """Object nhóm (xáo tên) -> {"id", "name"}; None/không phải dict -> None."""
    if isinstance(g, str):
        return {"id": None, "name": g} if g else None
    if not isinstance(g, dict):
        return None
    if "name" in g:                                   # định dạng cũ
        return g
    strs = [k for k, v in g.items() if isinstance(v, str)]
    ints = [k for k, v in g.items() if _is_int(v)]
    nk = _pick(strs, "name") or (sorted(strs)[0] if strs else None)
    ik = _pick(ints, "id") or (sorted(ints)[0] if ints else None)
    return {"id": g.get(ik) if ik else None, "name": g.get(nk) if nk else None}


def _canon_chapters(raw):
    """Danh sách bản upload (định dạng xáo tên) -> dạng CŨ. Nhận diện trên TOÀN BỘ danh
    sách (mọi trang list gộp lại) để đủ dữ liệu khử mơ hồ:
      url        = chuỗi khớp /title/<slug>/<id>-chapter-<số> ở MỌI bản
      id         = số nguyên BẰNG <id> trong url
      number     = số BẰNG <số> trong url (url không có số -> trường số/None); không ra -> lấy từ url
      language   = mã ngôn ngữ ngắn (en, pt-br...) ở mọi bản
      group      = object (hoặc null) có chuỗi tên — null = bản không nhóm
      isOfficial = trường bool (hoặc null); nhiều trường bool -> trường True ở các bản
                   nhóm official đã biết (OFFICIAL_GROUP_RANK), rồi mới tới KEY_HINTS
    Định dạng cũ (đã có id/url) trả nguyên. Không chắc -> SiteChanged."""
    raw = [o for o in raw if isinstance(o, dict)]
    if not raw or all("id" in o and "url" in o for o in raw):
        return raw
    keys = set().union(*(o.keys() for o in raw))

    def every(pred):
        return [k for k in keys if all(pred(o.get(k), o) for o in raw)]

    url_k = _pick(every(lambda v, o: isinstance(v, str) and CH_URL_RE.search(v)), "url")
    if not url_k:
        raise SiteChanged("không nhận ra trường url chương trong danh sách")

    def uid(o):
        return int(CH_URL_RE.search(o[url_k]).group(2))

    id_k = _pick(every(lambda v, o: _is_int(v) and v == uid(o)), "id")
    if not id_k:
        raise SiteChanged("không nhận ra trường id chương (khớp id trong url)")

    num_k = None
    if any(_url_num(o[url_k]) is not None for o in raw):
        def num_ok(v, o):
            u = _url_num(o[url_k])
            return (v is None or _is_num(v)) if u is None else (_is_num(v) and abs(v - u) < 1e-6)
        num_c = [k for k in every(num_ok) if k != id_k]
        # Nhiều trường cùng bằng số trong url ở MỌI bản -> lấy trường nào cũng ra cùng số.
        num_k = _pick(num_c, "number") or (sorted(num_c)[0] if num_c else None)

    lang_c = every(lambda v, o: isinstance(v, str) and LANG_RE.match(v))
    lang_k = _pick(lang_c, "language")
    if lang_k is None and lang_c:     # mơ hồ -> trường mà 'en' xuất hiện nhiều nhất
        lang_k = max(sorted(lang_c), key=lambda k: sum(o.get(k) == "en" for o in raw))
    if lang_k is None:
        raise SiteChanged("không nhận ra trường ngôn ngữ của bản upload")

    grp_c = [k for k in every(lambda v, o: v is None or (
                 isinstance(v, dict) and any(isinstance(x, str) for x in v.values())))
             if any(isinstance(o.get(k), dict) for o in raw)]
    grp_k = _pick(grp_c, "group")
    if grp_k is None and len(grp_c) > 1:
        raise SiteChanged(f"mơ hồ trường nhóm dịch ({', '.join(sorted(grp_c))})")

    off_c = [k for k in every(lambda v, o: v is None or isinstance(v, bool))
             if any(isinstance(o.get(k), bool) for o in raw)]
    if not off_c:
        raise SiteChanged("không nhận ra trường Official (bool) của bản upload")
    off_k = off_c[0] if len(off_c) == 1 else None
    if off_k is None:
        known = {_norm_group(n) for n in OFFICIAL_GROUP_RANK}

        def score(k):
            s = 0
            for o in raw:
                g = _canon_group(o.get(grp_k)) if grp_k else None
                if g and _norm_group(g.get("name")) in known:
                    s += 1 if o.get(k) is True else -1
            return s
        scores = {k: score(k) for k in off_c}
        best = max(scores.values())
        tops = [k for k, s in scores.items() if s == best]
        off_k = tops[0] if best > 0 and len(tops) == 1 else _pick(off_c, "isOfficial")
    if off_k is None:
        raise SiteChanged(f"mơ hồ trường Official ({', '.join(sorted(off_c))})")

    out = []
    for o in raw:
        url = o[url_k]
        if url.startswith("http"):
            url = urllib.parse.urlparse(url).path
        group = _canon_group(o.get(grp_k)) if grp_k else None
        num = o.get(num_k) if num_k else None
        out.append({"id": o[id_k], "url": url,
                    "number": num if num is not None else _url_num(url),
                    "language": o.get(lang_k), "isOfficial": bool(o.get(off_k)),
                    "group": group, "groupId": group.get("id") if group else None})
    return out


def _key_opt(key, name):
    """Tham số số nguyên trong queryKey (vd [.., {"page": 2, "limit": 20}], "page") -> 2."""
    for part in key if isinstance(key, list) else []:
        if isinstance(part, dict) and _is_int(part.get(name)):
            return part[name]
    return None


def _list_from_data(data):
    """Dữ liệu 1 query -> (mảng bản upload, meta) nếu là danh sách chương, không thì None.
    Mảng chương = list các dict có chuỗi url chương; meta = dict có >= 3 số nguyên. Trang
    list RỖNG (lật quá trang cuối) -> ([], meta) khi data chỉ có đúng 1 list và nó rỗng."""
    if not isinstance(data, dict):
        return None
    arrs = [v for v in data.values() if isinstance(v, list)]
    lists = [v for v in arrs if v
             and all(isinstance(o, dict) and any(isinstance(x, str) and CH_URL_RE.search(x)
                                                  for x in o.values()) for o in v)]
    metas = [v for v in data.values() if isinstance(v, dict)
             and sum(_is_int(x) for x in v.values()) >= 3]
    meta = metas[0] if len(metas) == 1 else None
    if len(lists) == 1:
        return lists[0], meta
    if not lists and len(arrs) == 1 and not arrs[0]:
        return [], meta
    return None


def _snap_list_page(snap, n, hid):
    """Ảnh chụp SNAP_JS -> trang list chương số n: {"items", "last", "per"} hoặc None.
    `last` None = meta không cho biết chắc trang cuối (người gọi lật tới trang thiếu).
    Định dạng cũ (window.__cap) trả item nguyên; mới trả item THÔ (chuẩn hoá sau, khi đủ
    mọi trang). Chỉ nhận query có page == n trong key và url chương đúng truyện `hid`
    (phần mã trước '-' của slug) — trang rỗng thì key phải chứa `hid`."""
    for o in snap.get("cap") or []:                               # định dạng cũ
        r = o.get("result") if isinstance(o, dict) else None
        if not isinstance(r, dict):
            continue
        meta, its = r.get("meta"), r.get("items")
        if (isinstance(meta, dict) and isinstance(its, list) and meta.get("page") == n
                and (not its or "isOfficial" in its[0])):
            return {"items": its, "last": int(meta.get("lastPage") or 1),
                    "per": meta.get("perPage") or 20}
    for q in snap.get("queries") or []:                           # định dạng mới
        key = q.get("key")
        if _key_opt(key, "page") != n:
            continue
        got = _list_from_data(q.get("data"))
        if got is None:
            continue
        its, meta = got
        if its:
            urls = [next(x for x in o.values() if isinstance(x, str) and CH_URL_RE.search(x))
                    for o in its]
            if any(CH_URL_RE.search(u).group(1).split("-")[0] != hid for u in urls):
                continue
        elif hid not in json.dumps(key):
            continue
        per = _key_opt(key, "limit") or 20
        return {"items": its, "last": _last_page(meta, per), "per": per}
    return None


def _snap_reason(snap):
    """Ảnh chụp cuối của 1 lượt hụt -> (site_doi: bool, mô tả). site_doi=True khi trang
    ĐÃ render + đọc được React Query + không query nào đang tải/lỗi mà vẫn không ra dữ
    liệu = tool không hiểu cấu trúc mới (thử lại vô ích). Ngược lại là mạng/API chậm."""
    if not isinstance(snap, dict):
        return False, "trang không phản hồi"
    if not snap.get("react"):
        return False, "trang chưa hiện nội dung"
    if not snap.get("client"):
        return True, "trang đã hiện nhưng không tìm thấy kho dữ liệu React Query"
    if snap.get("busy"):
        return False, f"{snap['busy']} truy vấn API còn đang tải/lỗi"
    return True, (f"đọc được {snap.get('total', 0)} truy vấn nhưng không nhận ra dữ "
                  "liệu cần lấy")


def _last_page(meta, per):
    """Trang cuối từ meta xáo tên: tổng = số nguyên LỚN NHẤT, trang cuối = ceil(tổng/per)
    — chỉ nhận khi con số đó CÓ trong meta (đối chiếu), hoặc = 1. Không chắc -> None
    (người gọi lật tiếp tới khi gặp trang thiếu)."""
    if not isinstance(meta, dict) or not per:
        return None
    if _is_int(meta.get("lastPage")):
        return max(1, meta["lastPage"])
    ints = [v for v in meta.values() if _is_int(v)]
    if not ints:
        return None
    lp = max(1, -(-max(ints) // per))
    return lp if (lp == 1 or lp in ints) else None


def _alt_urls(url, domains):
    """Đổi domain gốc của URL ảnh sang các domain DỰ PHÒNG, GIỮ tiền tố (vd '447.'):
    https://447.a.site/hi/x + ['b.site'] -> ['https://447.b.site/hi/x']. Đã thử thật
    27/10: domain dự phòng trả đúng cùng ảnh."""
    try:
        p = urllib.parse.urlparse(url)
    except ValueError:
        return []
    labels = (p.hostname or "").split(".")
    pre = ".".join(labels[:-2])            # tiền tố trước domain gốc 2 nhãn, vd '447'
    out = []
    for d in domains or []:
        host = d if not pre or d.startswith(pre + ".") else f"{pre}.{d}"
        if host != p.hostname:
            out.append(p._replace(netloc=host).geturl())
    return out


def _pages_from_detail(data, chap_id):
    """Dữ liệu query chi tiết chương -> [{"url", "s", "alts"}], [] nếu chương đúng id
    nhưng không có trang (khoá), None nếu KHÔNG phải chương chap_id. Mảng trang = list
    các dict có URL http(s); URL ảnh = chuỗi http KHÁC NHAU giữa các trang; domain dự
    phòng = list chuỗi dạng domain. Định dạng cũ ({id, pages:{baseUrl, items}}) vẫn đọc."""
    if not isinstance(data, dict):
        return None
    if data.get("id") == chap_id and isinstance(data.get("pages"), dict):   # định dạng cũ
        pg = data["pages"]
        base = (pg.get("baseUrl") or "").rstrip("/")
        out = []
        for it in pg.get("items") or []:
            u = it.get("url") or ""
            if u:
                if not u.startswith("http"):
                    u = base + "/" + u.lstrip("/")
                out.append({"url": u, "s": it.get("s") == 1, "alts": []})
        return out
    if not any(_is_int(v) and v == chap_id for v in data.values()):
        return None

    def is_http(x):
        return isinstance(x, str) and x.startswith(("http://", "https://"))

    arrs = {k: v for k, v in data.items() if isinstance(v, list) and v
            and all(isinstance(o, dict) and any(is_http(x) for x in o.values()) for o in v)}
    if not arrs:
        return []
    pk = _pick(arrs, "pages") or max(sorted(arrs), key=lambda k: len(arrs[k]))
    pages = arrs[pk]
    keys = set().union(*(o.keys() for o in pages))
    url_c = [k for k in keys if all(is_http(o.get(k)) for o in pages)]
    if len(pages) > 1:     # URL ảnh khác nhau giữa các trang; chuỗi http cố định thì không phải
        url_c = [k for k in url_c if len({o[k] for o in pages}) == len(pages)] or url_c
    url_k = _pick(url_c, "url") or (sorted(url_c)[0] if url_c else None)
    if not url_k:
        raise SiteChanged("không nhận ra trường URL ảnh trong chương")
    alt_ks = [k for k in keys if all(isinstance(o.get(k), list) and o[k] and all(
        isinstance(x, str) and DOMAIN_RE.match(x) for x in o[k]) for o in pages)]
    out = []
    for o in pages:
        doms = [d for k in sorted(alt_ks) for d in o[k]]
        out.append({"url": o[url_k], "s": o.get("s") == 1,
                    "alts": _alt_urls(o[url_k], list(dict.fromkeys(doms)))})
    return out


# --- Telegram (đọc chung notify-config.json với supervisor; lỗi thì im lặng) -----

def _notify_telegram(text):
    """Báo admin qua Telegram (ưu tiên admin_chat_ids, fallback chat_ids). Dùng khi
    cần NGƯỜI can thiệp trên màn hình server (Cloudflare challenge). Không có
    config/token (vd máy dev) -> chỉ in console, không lỗi."""
    try:
        cfg = json.loads(NOTIFY_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    token = cfg.get("bot_token")
    ids = cfg.get("admin_chat_ids") or cfg.get("chat_ids") or []
    if not token or not ids:
        return
    for cid in ids:
        try:
            data = urllib.parse.urlencode(
                {"chat_id": cid, "text": text,
                 "disable_web_page_preview": "true"}).encode()
            urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data, timeout=15).read()
        except Exception:
            pass


# --- Dọn Chromium lạc + khoá profile (chống treo do "chuyển cho instance cũ") ------

def _kill_profile_chrome():
    """Giết mọi chrome.exe đang dùng `comix-profile` + xoá các file khoá singleton cũ.

    VÌ SAO: Chromium dùng profile BỀN (persistent). Nếu còn 1 Chromium mồ côi (từ lần
    trước treo/bị kill) đang ôm profile này, thì `launch_persistent_context` mở chrome.exe
    MỚI sẽ phát hiện "đã có instance" -> chuyển URL cho con cũ rồi TỰ THOÁT -> Playwright
    vừa mở con đó mất kết nối -> TREO vô hạn ở about:blank (đúng sự cố 14/08). Dọn sạch
    TRƯỚC khi mở là diệt gốc. An toàn: hàng đợi comix chỉ 1 worker tuần tự (không có 2 job
    comix song song), và match theo 'comix-profile' nên KHÔNG đụng Chrome thường của user.

    Xoá cả file khoá (`SingletonLock/Socket/Cookie`, `lockfile`): chrome bị Force-kill để
    lại các file này trên đĩa -> lần mở sau đôi khi cũng kẹt. Best-effort, không raise."""
    if os.name == "nt":
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                 "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                 "Where-Object { $_.CommandLine -match 'comix-profile' } | "
                 "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
                 "-ErrorAction SilentlyContinue }"],
                creationflags=_NO_WINDOW, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile"):
        try:
            (PROFILE_DIR / name).unlink()
        except OSError:
            pass


class _StartupWatchdog:
    """Lưới an toàn: nếu khâu MỞ + KHỞI TẠO Chromium quá `LAUNCH_WATCHDOG` giây thì gần
    như chắc chắn đang TREO (browser bật lên nhưng Playwright không lái được — vd cửa sổ
    kẹt ở about:blank, sự cố 14/08 + 17/08). Watchdog kill Chromium: đường ống CDP đứt sẽ
    khiến lệnh Playwright đang kẹt ở MAIN THREAD bật lỗi -> `_launch` bắt được -> ném
    BrowserGone -> `_open_resilient`/`relaunch` tự dựng lại TRONG PHIÊN (Cách B). Kill này
    còn dọn luôn orphan/lock — nghi phạm gốc — nên lần dựng lại thường thành công.

    Nếu sau ÂN HẠN `LAUNCH_KILL_GRACE` giây mà main-thread VẪN kẹt (lệnh không thèm bật
    lỗi cả khi chrome đã chết) -> `os._exit` HARD làm chốt chặn cuối: downloader thoát != 0
    -> supervisor báo lỗi + chạy job kế, thay vì treo câm.

    BỌC cả khâu mở lẫn setup (add_init_script/route/pages/probe) — vùng này KHÔNG có
    timeout nội bộ đáng tin, đúng chỗ 17/08 treo. KHÔNG bọc các bước sau đó (goto có
    timeout 45s; chờ Cloudflare có người tick tối đa 5') để khỏi giết nhầm lúc chờ xác minh."""

    def __init__(self, timeout, label, grace=LAUNCH_KILL_GRACE):
        self._timeout = timeout
        self._grace = grace
        self._label = label
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._done.set()
        return False

    def _run(self):
        if self._done.wait(self._timeout):
            return   # xong đúng hạn -> yên
        print(f"\n  !! Watchdog: {self._label} quá {self._timeout}s — nghi Chromium treo. "
              "Kill Chromium để phiên tự dựng lại...", file=sys.stderr, flush=True)
        _kill_profile_chrome()
        # Ân hạn cho main-thread bật lỗi + thoát khối watchdog -> phiên tự relaunch (khỏi os._exit).
        if self._done.wait(self._grace):
            return
        print(f"  !! Watchdog: vẫn kẹt sau {self._grace}s dù đã kill Chromium — thoát cứng "
              "(supervisor sẽ báo lỗi + chạy job kế).", file=sys.stderr, flush=True)
        os._exit(2)


# --- Phiên trình duyệt -----------------------------------------------------------

class ComixSession:
    """Playwright headful + hook JSON.parse. Chỉ dùng cho metadata (list + URL ảnh)."""

    def __init__(self):
        self._pw = None
        self.ctx = None
        self.page = None
        self._notified_challenge = False
        self._relaunch_streak = 0     # số lần dựng lại Chromium trong ĐỢT sự cố hiện tại

    def __enter__(self):
        self._open_resilient()
        return self

    def _open_resilient(self):
        """Mở phiên LẦN ĐẦU; nếu wedge (BrowserGone) -> dọn orphan/lock rồi thử lại tối đa
        MAX_RELAUNCH lần (Cách B). Nhờ vậy ca 'about:blank treo lúc mở' (17/08) tự khỏi
        trong phiên thay vì hỏng cả lượt tải. Quá ngân sách -> ném ra ngoài = fatal."""
        attempt = 0
        while True:
            try:
                self._launch()
                return
            except BrowserGone as e:
                attempt += 1
                if attempt > MAX_RELAUNCH:
                    raise BrowserGone(
                        f"Không mở nổi Chromium sau {MAX_RELAUNCH} lần thử: {e}") from e
                print(f"  ! Mở Chromium hụt/treo — dọn rồi thử lại "
                      f"(lần {attempt}/{MAX_RELAUNCH})...", file=sys.stderr, flush=True)
                self._close_playwright()
                _kill_profile_chrome()          # diệt orphan/lock trước khi thử lại
                time.sleep(RELAUNCH_BACKOFF)

    def _launch(self):
        """Mở Chromium + gắn hook/route/popup + PROBE. Tách riêng để relaunch() gọi lại
        được khi cửa sổ bị đóng giữa chừng (cùng profile bền -> khỏi verify Cloudflare lại).

        BỌC _StartupWatchdog QUANH CẢ mở lẫn setup: các bước sau launch (add_init_script/
        route/pages/probe) KHÔNG có timeout nội bộ đáng tin — đúng vùng treo câm 17/08.
        PROBE `evaluate('() => 1')` xác nhận renderer thật sự trả lời trước khi giao việc:
        trang tốt trả 1 tức thì, trang wedge (about:blank kẹt) làm probe treo -> watchdog nổ.
        Bất kỳ lỗi nào (kể cả khi watchdog kill Chromium giữa chừng) -> ném BrowserGone để
        _open_resilient/_resilient tự dựng lại."""
        try:
            with _StartupWatchdog(LAUNCH_WATCHDOG, "mở + khởi tạo Chromium"):
                from playwright.sync_api import sync_playwright
                self._pw = sync_playwright().start()
                PROFILE_DIR.mkdir(parents=True, exist_ok=True)
                # 2 cờ chống-lộ-automation là BẮT BUỘC: site check navigator.webdriver,
                # true là JS site KHÔNG boot (SSR có title nhưng body rỗng, không gọi API).
                self.ctx = self._pw.chromium.launch_persistent_context(
                    str(PROFILE_DIR), headless=False, viewport={"width": 1280, "height": 900},
                    args=["--disable-blink-features=AutomationControlled"],
                    ignore_default_args=["--enable-automation"])
                self.ctx.add_init_script(HOOK_JS)
                # Chặn MỌI request ra domain lạ (quảng cáo). Trình duyệt CHỈ cần comix.to
                # (JSON metadata) + cloudflare.com (challenge); ảnh do requests tải riêng,
                # không cần render trong browser. Đây là gốc rễ sự cố "chưa bắt được ảnh
                # chương": script quảng cáo (vd masterlythehague.com) đẩy trang rời comix.to
                # giữa lúc load -> hook JSON.parse không thấy payload -> tưởng lỗi. Chặn hẳn là hết.
                self.ctx.route("**/*", self._route_filter)
                self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
                self.page.set_default_timeout(45_000)
                # Popup quảng cáo (window.open/target=_blank) -> đóng ngay, giữ đúng 1 trang.
                self.ctx.on("page", self._on_popup)
                # PROBE: renderer phải trả lời được — bắt đúng ca wedge (about:blank treo).
                self.page.evaluate("() => 1")
        except Exception as e:
            # Lỗi mở thật, hoặc watchdog vừa kill Chromium làm lệnh Playwright kẹt bật lỗi.
            self._close_playwright()
            raise BrowserGone(f"Mở/khởi tạo Chromium thất bại: {e}") from e

    def alive(self) -> bool:
        """Browser còn sống không? Để phân biệt 'Chromium đã đóng' (fatal, phải dựng
        lại) với 'một lần điều hướng hụt' (tạm thời, cứ retry). Chỉ đọc trạng thái cục
        bộ (page.is_closed / browser.is_connected) — không IPC nên không false-positive
        lúc trang đang navigate."""
        try:
            if self.page is None or self.page.is_closed():
                return False
            br = self.ctx.browser if self.ctx else None
            if br is not None and not br.is_connected():
                return False
            return True
        except Exception:
            return False

    def mark_progress(self):
        """Vừa tải được 1 chương -> reset bộ đếm dựng-lại (mỗi ĐỢT sự cố có ngân sách
        MAX_RELAUNCH riêng, để browser chập chờn cả phiên dài không cộng dồn thành fatal)."""
        self._relaunch_streak = 0

    def relaunch(self):
        """Dựng lại Chromium TẠI CHỖ sau khi cửa sổ bị đóng/chết (cùng profile bền ->
        giữ cf_clearance; .done/sidecar giúp bỏ qua chương đã xong, y như restart tay).
        Quá MAX_RELAUNCH lần trong một đợt -> ném BrowserGone = fatal (thoát != 0)."""
        self._relaunch_streak += 1
        if self._relaunch_streak > MAX_RELAUNCH:
            raise BrowserGone(
                f"Chromium đóng liên tục — đã tự dựng lại {MAX_RELAUNCH} lần vẫn hỏng")
        print(f"\n  ! Cửa sổ Chromium đã đóng — tự dựng lại "
              f"(lần {self._relaunch_streak}/{MAX_RELAUNCH}), tải tiếp...",
              file=sys.stderr, flush=True)
        _notify_telegram(
            "🔄 Comix: cửa sổ Chromium bị đóng giữa chừng — tool TỰ mở lại "
            f"(lần {self._relaunch_streak}/{MAX_RELAUNCH}) và tải tiếp. Không cần làm gì.")
        self._close_playwright()
        _kill_profile_chrome()          # diệt orphan/lock trước khi mở lại (nghi phạm gốc wedge)
        time.sleep(RELAUNCH_BACKOFF)
        try:
            self._launch()
        except Exception as e:
            raise BrowserGone(f"Không dựng lại được Chromium: {e}") from e

    @staticmethod
    def _route_filter(route):
        try:
            host = (urllib.parse.urlparse(route.request.url).hostname or "").lower()
        except Exception:
            host = ""
        ok = (host == "comix.to" or host.endswith(".comix.to")
              or host.endswith(".cloudflare.com") or host == "cloudflare.com")
        # CDN ảnh wowpic*.store: CHỈ mở cho fetch/xhr. Hàm giải-xáo `vs` của site phải TỰ
        # tải ảnh xáo trong browser thì apply() mới vẽ -> mới ghi được bản đồ ô (chặn là
        # descramble_ops trả rỗng im lặng — đúng gốc lỗi "0 trang" 02/09). Thẻ <img> của
        # reader là type 'image' -> vẫn chặn để không tốn băng thông tải cả trang.
        if not ok and re.search(r"(^|\.)wowpic\d*\.store$", host):
            try:
                ok = route.request.resource_type in ("fetch", "xhr")
            except Exception:
                ok = False
        try:
            route.continue_() if ok else route.abort()
        except Exception:
            pass

    def _on_popup(self, page):
        if page is not self.page:
            try:
                page.close()
            except Exception:
                pass

    def _close_playwright(self):
        for obj in (self.ctx, self._pw):
            try:
                if obj is self.ctx and obj:
                    obj.close()
                elif obj is self._pw and obj:
                    obj.stop()
            except Exception:
                pass
        self.ctx = self.page = self._pw = None   # để alive()=False + _launch gán lại sạch

    def __exit__(self, *exc):
        # LUÔN đóng browser kẻo Chromium mồ côi chiếm profile (supervisor cũng có
        # lưới dọn lúc boot, nhưng đấy là phòng hờ crash, không phải đường chính).
        self._close_playwright()
        return False

    # -- Cloudflare -------------------------------------------------------------

    def _challenge_present(self):
        try:
            t = (self.page.title() or "").lower()
        except Exception:
            return False
        return "just a moment" in t or "attention required" in t

    def _wait_challenge(self):
        """Dính challenge tương tác: nhắn Telegram cho người tick, chờ tối đa 5 phút."""
        print("\n  ! Cloudflare đang chặn — cần NGƯỜI xác minh trên màn hình server "
              "(cửa sổ Chromium đang mở). Đã nhắn Telegram, chờ tối đa "
              f"{CHALLENGE_WAIT // 60} phút...", flush=True)
        if not self._notified_challenge:
            self._notified_challenge = True
            _notify_telegram(
                "⚠️ Tải comix.to đang bị Cloudflare chặn.\n\n"
                "CẦN LÀM: mở màn hình máy server → cửa sổ Chromium đang hiện → "
                "tick ô \"Verify you are human\" (Xác minh bạn là người).\n\n"
                f"Tool chờ tối đa {CHALLENGE_WAIT // 60} phút rồi tự tải tiếp; "
                "quá giờ sẽ dừng phiên (chạy lại /tai sau khi xác minh).")
        end = time.monotonic() + CHALLENGE_WAIT
        while time.monotonic() < end:
            time.sleep(3)
            if not self._challenge_present():
                print("  -> Đã qua Cloudflare, chạy tiếp.", flush=True)
                _notify_telegram("✅ Comix: đã qua Cloudflare, đang tải tiếp.")
                return
        _notify_telegram("⛔ Comix: quá 5 phút chưa qua Cloudflare — phiên tải dừng. "
                         "Xác minh xong hãy /tai lại.")
        raise core.Blocked("Cloudflare challenge không được xác minh trong "
                           f"{CHALLENGE_WAIT}s")

    # -- Điều hướng + bắt dữ liệu ------------------------------------------------

    def _goto(self, url):
        for attempt in range(3):
            try:
                self.page.goto(url, wait_until="domcontentloaded")
                # tab quảng cáo lỡ bật (target=_blank) -> đóng, giữ đúng 1 page
                for p in list(self.ctx.pages):
                    if p is not self.page:
                        try:
                            p.close()
                        except Exception:
                            pass
                if self._challenge_present():
                    self._wait_challenge()
                return
            except core.Blocked:
                raise
            except Exception as e:
                # Chromium đã đóng hẳn -> retry vô ích; báo fatal để run() dựng lại.
                if not self.alive():
                    raise BrowserGone(f"Chromium đã đóng khi mở {url}: {e}") from e
                if attempt == 2:
                    raise RuntimeError(f"Không mở được {url}: {e}") from e
                time.sleep(3 * (attempt + 1))

    def _pump(self, extract, needle="", timeout=20.0, desc="dữ liệu"):
        """Chụp dữ liệu trang (SNAP_JS: window.__cap định dạng cũ + React Query cache định
        dạng mới) tới khi `extract(snap)` trả khác None. Site SPA gọi API ngay sau load nên
        thường có trong ~1-2s. Trả kết quả extract, hoặc None nếu hết giờ (KHÔNG raise —
        người gọi tự quyết retry / rơi xuống bản khác / bỏ qua); ảnh chụp cuối để ở
        self.last_snap cho chẩn đoán (_snap_reason). SiteChanged của extract bay thẳng ra
        (dữ liệu đã có mà không hiểu được — chụp lại cũng vậy)."""
        end = time.monotonic() + timeout
        self.last_snap = None
        while time.monotonic() < end:
            try:
                snap = self.page.evaluate(SNAP_JS, needle)
            except Exception:
                if not self.alive():
                    raise BrowserGone("Chromium đã đóng khi đọc payload")
                snap = None
            if isinstance(snap, dict):
                self.last_snap = snap
                try:
                    res = extract(snap)
                except SiteChanged:
                    raise
                except Exception:
                    res = None
                if res is not None:
                    return res
            if self._challenge_present():
                self._wait_challenge()
                end = time.monotonic() + timeout   # qua challenge -> làm mới đồng hồ
            time.sleep(0.4)
        return None

    def fetch_series(self, slug):
        """Gom TOÀN BỘ bản upload của truyện (mọi trang list, limit 20 do site cố
        định; phân trang bằng URL ?page=N — không lệ thuộc DOM nút bấm). Đọc cả định
        dạng cũ (hook JSON.parse) lẫn mới (React Query, tên trường XÁO — gom THÔ mọi trang
        rồi mới chuẩn hoá 1 lần bằng _canon_chapters cho đủ dữ liệu khử mơ hồ).
        Trả (title, cover_url, items). Hụt sau 3 lần mở: trang render được mà không nhận
        ra dữ liệu -> SiteChanged (thử lại vô ích); trang trắng / API chậm-lỗi ->
        RuntimeError kiểu mạng (supervisor giữ job thử lại)."""
        hid = slug.split("-")[0]
        raw, page_no, last = [], 1, None
        title = cover = None
        while last is None or page_no <= last:
            # Retry mỗi trang list: cùng nguyên nhân với ảnh chương (quảng cáo/mạng
            # chèn) có thể làm hụt 1 lần — mở lại vài lần trước khi chịu thua.
            got = None
            for attempt in range(3):
                time.sleep(random.uniform(0.6, 1.2))
                try:
                    self._goto(f"{BASE}/title/{slug}?page={page_no}")
                except (core.Blocked, BrowserGone):
                    raise
                except Exception:
                    continue
                got = self._pump(lambda s, n=page_no: _snap_list_page(s, n, hid), needle=hid,
                                 desc=f"danh sách chương (trang {page_no})")
                if got is not None:
                    break
            if got is None:
                changed, why = _snap_reason(getattr(self, "last_snap", None))
                if changed:
                    raise SiteChanged(f"{why} (danh sách chương, trang {page_no})")
                raise RuntimeError(
                    f"Không lấy được danh sách chương (trang {page_no}) từ comix.to ({why}) "
                    "— mạng chập chờn? Thử /tai lại sau.")
            raw.extend(got["items"])
            if got["last"] is not None:
                last = got["last"]
            elif len(got["items"]) < got["per"]:
                last = page_no          # meta không rõ trang cuối: trang thiếu = trang cuối
            if title is None:
                # Site KHÔNG có og:image — bìa là <img> đầu tiên trỏ static.comix.to,
                # dạng .../68deeb...@280.jpg (thumbnail 280px; bỏ '@280' = bản full).
                title, cover = self.page.evaluate(
                    """() => {
                        const t = document.querySelector('meta[property="og:title"]');
                        let name = (t && t.content) || document.title || '';
                        name = name.replace(/\\s*[\\u00b7|–—-]\\s*Comix.*$/i, '').trim();
                        const img = [...document.querySelectorAll('img')].find(
                            i => (i.currentSrc || i.src || '').includes('static.comix.to'));
                        return [name, img ? (img.currentSrc || img.src) : null];
                    }""")
            print(f"\r  Danh sách chương: trang {page_no}/{last or '?'} — "
                  f"cộng dồn {len(raw)} bản upload   ", end="", flush=True)
            page_no += 1
        print()
        return title or slug, cover, _canon_chapters(raw)

    def fetch_pages(self, url_path, chap_id, tries=3):
        """URL ảnh của 1 bản upload (điều hướng tới trang đọc, hook bắt payload).

        Trả:
          [{"url":.., "s":bool, "alts":[..]}, ...] - lấy được (rỗng nếu chương có nhưng
                       0 trang = khóa/premium thật). `s`=True là trang bị TRÁO Ô (định
                       dạng cũ, comix official chèn mỗi trang thứ 10): url trả bytes xáo,
                       phải giải-xáo qua canvas của site — xem descramble_pages +
                       [[comix-scramble-s-flag]]. `alts` = cùng ảnh trên domain CDN dự
                       phòng (định dạng mới) — ghi luôn vào _ALT_URLS cho client tải ảnh.
          None       - KHÔNG bắt được dữ liệu sau `tries` lần (mạng/quảng cáo chèn) ->
                       người gọi rơi xuống bản khác / đánh dấu 'để sau', KHÔNG raise.
        Dữ liệu chương có mà không nhận ra trường URL ảnh -> SiteChanged.
        """
        def extract(snap):
            for o in snap.get("cap") or []:                       # định dạng cũ
                got = _pages_from_detail(o.get("result") if isinstance(o, dict) else None,
                                         chap_id)
                if got is not None:
                    return got
            # Định dạng mới: query có chap_id NGAY TRONG key (["chapters","detail",id])
            # xét trước — query khác (vd chi tiết truyện) có thể tình cờ mang id này.
            qs = snap.get("queries") or []
            in_key = [q for q in qs if isinstance(q.get("key"), list)
                      and any(k in (chap_id, str(chap_id)) for k in q["key"])]
            for q in in_key + [q for q in qs if q not in in_key]:
                got = _pages_from_detail(q.get("data"), chap_id)
                if got is not None:
                    return got
            return None

        out = None
        for attempt in range(tries):
            time.sleep(random.uniform(0.6, 1.2))
            try:
                self._goto(BASE + url_path)
            except (core.Blocked, BrowserGone):
                raise
            except Exception:
                continue                      # goto hỏng -> mở lại
            out = self._pump(extract, needle=str(chap_id),
                             desc=f"ảnh chương (id {chap_id})")
            if out is not None:
                break                          # bắt được (kể cả 0 trang) -> thôi retry
        if out is None:
            _changed, why = _snap_reason(getattr(self, "last_snap", None))
            print(f"\n    ! Chưa lấy được ảnh chương (id {chap_id}) sau {tries} lần thử "
                  f"({why}).", file=sys.stderr, flush=True)
            return None
        for it in out:
            if it.get("alts"):
                _ALT_URLS[it["url"]] = it["alts"]
        return out

    def descramble_ops(self, url_path, urls, timeout_ms=12000):
        """GHI bản đồ tráo ô cho từng URL trang `s:1`: chạy DESCRAMBLE_JS (chặn drawImage
        lúc apply chạy). Trả {idx: {"w","h","ops":[...]}} (null nếu ghi hụt). CHỈ đụng
        browser — không tải/không xếp ảnh (việc đó để Python làm, xem descramble_pages).

        Cần đang ở TRANG ĐỌC comix (import() same-origin + chunk secure.js đã nạp);
        thường đúng vì fetch_pages vừa điều hướng tới đây. Browser chết -> BrowserGone."""
        if not urls:
            return {}
        try:
            cur = self.page.url or ""
        except Exception:
            cur = ""
        if not cur.startswith(BASE + url_path):
            self._goto(BASE + url_path)
            time.sleep(1.5)                   # chờ SPA nạp chunk reader (secure.js)
        items = [{"idx": i, "url": u} for i, u in urls]
        try:
            res = self.page.evaluate(
                DESCRAMBLE_JS, {"items": items, "timeoutMs": timeout_ms})
        except Exception as e:
            if not self.alive():
                raise BrowserGone(f"Chromium đã đóng khi ghi bản đồ tráo ô: {e}") from e
            raise
        if isinstance(res, dict) and res.get("__error"):
            print(f"\n    ! Ghi bản đồ tráo ô lỗi: {res['__error']}",
                  file=sys.stderr, flush=True)
            return {}
        out = {}
        for k, rec in (res or {}).items():
            if rec and rec.get("ops"):
                try:
                    out[int(k)] = rec
                except (TypeError, ValueError):
                    pass
        return out

    def descramble_pages(self, url_path, pairs, img_client=None, timeout_ms=12000):
        """Giải-xáo các trang TRÁO Ô (cờ s:1), trả {idx: bytes webp SẠCH}. Cách làm:
        (1) browser GHI bản đồ ô + BẮT ĐÚNG bytes ảnh xáo mà vs nhận (descramble_ops —
        không đọc canvas), (2) xếp lại bằng PIL (_unscramble_ops) trên chính bytes đó.
        KHÔNG tải lại bằng img_client: CDN trả biến thể xáo KHÁC theo client (browser vs
        requests cùng URL khác hash) -> lệch bản đồ (đo 02/09). `img_client` giữ trong
        chữ ký để tương thích, không dùng. Trang ghi hụt -> bỏ (người gọi coi là thiếu,
        chạy lại bù). `pairs` = [(idx, url), ...]. Xem [[comix-scramble-s-flag]]."""
        if not pairs:
            return {}
        recs = self.descramble_ops(url_path, pairs, timeout_ms=timeout_ms)
        out = {}
        for idx, rec in recs.items():
            try:
                b64 = rec.get("b64")
                if not b64:
                    continue
                data = base64.b64decode(b64)
                clean = _unscramble_ops(data, rec.get("w"), rec.get("h"), rec["ops"])
                if clean:
                    out[idx] = clean
            except Exception as e:
                print(f"\n    ! Giải-xáo trang {idx:03d} hụt (giải mã/xếp): {e}",
                      file=sys.stderr, flush=True)
        return out


# --- Client tải ảnh (giả vân tay Chrome + mượn vé Cloudflare) ---------------------

class ComixImageClient:
    """HTTP client CHỈ để tải ảnh comix, khác `core.session` mặc định ở 2 điểm:

    1. VÂN TAY TLS: dùng curl_cffi impersonate="chrome" -> handshake JA3/JA4 + HTTP2
       giống Chrome thật. Cloudflare đời mới soi cả vân tay TLS; `requests` (urllib3)
       lộ ngay là "Python" nên khi site siết, vé cf_clearance chìa qua handshake
       không-phải-Chrome bị coi là replay -> 403. Impersonate xoá đúng lỗ hổng đó.
       Thiếu curl_cffi -> tự lùi về requests thường (vẫn mượn vé, chỉ không giả TLS).
    2. DANH TÍNH MƯỢN SỐNG: đọc UA thật + cookie .comix.to (gồm cf_clearance) từ
       CHÍNH browser Playwright đang mở, nạp vào client. Nhờ vậy request ảnh mang cùng
       "vé + UA + TLS" như trình duyệt đang qua cửa -> Cloudflare cho đi.
    3. REFERER THEO HOST (27/10/2026): Referer comix.to CHỈ gửi cho host comix.to /
       wowpic*.store (CDN cũ đòi). CDN mới `NNN.<ngẫu nhiên>.site` (Cloudflare WAF) gặp
       Referer comix.to là chặn 403 "you have been blocked" — chính site dùng
       referrerpolicy=no-referrer. Ảnh hỏng ở domain gốc -> thử domain DỰ PHÒNG site gửi
       kèm (_ALT_URLS, fetch_pages ghi).

    An toàn luồng: refresh_identity() ĐỘNG tới browser (page.evaluate/ctx.cookies) nên
    CHỈ được gọi ở MAIN THREAD (Playwright sync API cấm gọi chéo luồng). get() không
    đụng browser -> worker thread gọi thoải mái. Vé làm mới CHỦ ĐỘNG mỗi chương + khi
    dính 403 (đều ở main thread), worker chỉ đọc snapshot dict đã nạp sẵn."""

    def __init__(self, cs: "ComixSession"):
        self.cs = cs
        self._cookies = {}          # {name: value} cookie .comix.to (snapshot, đọc từ worker OK)
        self._impl = None
        self.backend = None
        self._build()
        # Lần đọc danh tính ĐẦU chạm browser (page.evaluate + ctx.cookies) — nửa sau của
        # "cửa sổ im lặng" trong sự cố 17/08. Probe ở _launch đã xác nhận trang lái được,
        # nhưng bọc watchdog cho kín: treo ở đây thì watchdog kill Chromium -> lần chạm
        # browser kế (fetch_series) bật lỗi -> _resilient tự dựng lại.
        with _StartupWatchdog(LAUNCH_WATCHDOG, "đọc danh tính từ browser (refresh_identity)"):
            self.refresh_identity()
        print(f"  (client tải ảnh: {self.backend})", flush=True)

    def _build(self):
        """Dựng client nền: ưu tiên curl_cffi (giả TLS Chrome), thiếu thì requests riêng."""
        try:
            from curl_cffi import requests as cffi
            self._impl = cffi.Session(impersonate="chrome")
            self.backend = "curl_cffi (giả vân tay Chrome)"
            return
        except Exception:
            pass
        # Fallback Bậc 1: requests RIÊNG (không đụng core.session dùng chung 5 site) —
        # vẫn mượn được vé + UA, chỉ thiếu lớp giả TLS.
        self._impl = requests.Session()
        self.backend = "requests (KHÔNG giả TLS — cài curl_cffi để chắc hơn)"

    def refresh_identity(self):
        """Đọc UA thật + cookie .comix.to từ browser, nạp vào client. Gọi ở MAIN THREAD:
        lúc khởi tạo, đầu mỗi chương (vé có thể xoay), và ngay khi dính 403."""
        try:
            ua = self.cs.page.evaluate("() => navigator.userAgent")
            if ua:
                self._impl.headers["User-Agent"] = ua
        except Exception:
            pass   # giữ UA cũ nếu page đang bận/hụt
        # KHÔNG đặt Referer chung cho session: CDN mới chặn Referer comix.to (xem get()).
        self._impl.headers.pop("Referer", None)
        cookies = {}
        try:
            for c in self.cs.ctx.cookies():
                dom = (c.get("domain") or "").lstrip(".").lower()
                if dom == "comix.to" or dom.endswith(".comix.to"):
                    cookies[c["name"]] = c["value"]
        except Exception:
            pass
        if cookies:                # chỉ đè khi đọc được, tránh xoá sạch vé lúc đọc hụt
            self._cookies = cookies

    def _get1(self, url, timeout):
        try:
            host = (urllib.parse.urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
        comix = host == "comix.to" or host.endswith(".comix.to")
        send = self._cookies if comix else None
        hdrs = {"Referer": REFERER} if comix or re.search(r"(^|\.)wowpic\d*\.store$", host) \
            else None
        try:
            return self._impl.get(url, timeout=timeout, cookies=send, headers=hdrs)
        except requests.RequestException:
            raise
        except Exception as e:
            raise requests.RequestException(str(e)) from e

    def get(self, url, timeout=60):
        """Bề mặt kiểu requests cho core.download_image. Gắn cookie comix CHỈ cho host
        *.comix.to (CDN không cần vé, cookie sai host còn phản tác dụng); Referer comix.to
        chỉ cho comix/wowpic (xem docstring lớp). Gói lỗi nền (curl_cffi ném lớp riêng)
        thành requests.RequestException để core coi như lỗi mạng mà retry, thay vì vỡ ra
        ngoài. Domain gốc lỗi (exception / 403 / 404 / 5xx — KHÔNG gồm 429: giãn nhịp là
        việc của gate) mà có domain dự phòng -> thử lần lượt, cái đầu tiên OK thắng; hụt
        hết thì trả/ném kết quả của domain gốc."""
        try:
            r, err = self._get1(url, timeout), None
        except requests.RequestException as e:
            r, err = None, e
        alts = _ALT_URLS.get(url)
        if alts and (r is None or (r.status_code >= 400 and r.status_code != 429)):
            for alt in alts:
                try:
                    r2 = self._get1(alt, timeout)
                except requests.RequestException:
                    continue
                if r2.status_code < 400:
                    return r2
        if r is None:
            raise err
        return r

    def close(self):
        try:
            self._impl.close()
        except Exception:
            pass


# --- Chọn bản + sidecar ----------------------------------------------------------

def series_slug(text):
    """'https://comix.to/title/6elqg-rankers-return?...' -> '6elqg-rankers-return'.
    Dán nhầm URL 1 chương (/title/{slug}/{id}-chapter-N) cũng ra đúng slug truyện."""
    m = re.search(r"/title/([^/?#]+)", text.strip())
    return m.group(1) if m else text.strip()


def group_versions(items):
    """{số chương: [item, ...]} — chỉ giữ bản en, có id + url; số hỏng thì bỏ."""
    by = {}
    for it in items:
        if (it.get("language") or "en") != "en":
            continue
        if not it.get("id") or not it.get("url"):
            continue
        raw = it.get("number")
        try:
            num = 0.0 if raw is None else float(raw)   # oneshot/không số -> 0.0
        except (TypeError, ValueError):
            continue
        by.setdefault(num, []).append(it)
    return by


# Ưu tiên GIỮA các bản official (bản tick "v") khi 1 số chương có NHIỀU official
# song song — vd Solo Leveling ch.0 có 7 official (Webcomic/Tapas/Manta/Yen Press/
# TappyToon/...). Số NHỎ = ưu tiên CAO (tải trước). Nhóm không có trong bảng ->
# hạng OFFICIAL_DEFAULT_RANK (giữa). Cùng hạng -> id mới nhất trước. Khớp KHÔNG phân
# biệt hoa/thường. Sửa thứ tự chỉ cần sửa bảng này (user chốt: TappyToon cao nhất,
# Webcomic thấp nhất).
OFFICIAL_GROUP_RANK = {
    "tappytoon": 0,        # dịch official Hàn -> Anh chất lượng, ưu tiên số 1
    "yen press": 1,        # NXB chính thống, typeset chuẩn
    "tapas": 2,
    "manta": 3,
    "pocket comics": 4,
    "official": 5,         # nhãn chung, mơ hồ
    "webcomic": 99,        # thấp nhất: chỉ tải khi không còn official nào khác
}
OFFICIAL_DEFAULT_RANK = 50  # nhóm official lạ chưa xếp hạng -> nằm giữa


def _official_rank(ver):
    return OFFICIAL_GROUP_RANK.get(_group_name(ver).lower(), OFFICIAL_DEFAULT_RANK)


def candidates_for(versions, pin=None):
    """Thứ tự ưu tiên tải:
      0. pin=<nhóm> (GHIM) -> CHỈ các bản của nhóm đó, id mới nhất trước; KHÔNG rơi về
         nhóm khác (rỗng = chương không có bản nhóm này). Các luật dưới KHÔNG áp.
      1. official — theo HẠNG NHÓM (OFFICIAL_GROUP_RANK), cùng hạng thì id mới nhất trước.
      2. scan CÓ tên nhóm (id mới nhất trước).
      3. scan KHÔNG có tên nhóm (id mới nhất trước) — chỉ dùng khi hết bản có nhóm.
    Bản đầu 0 trang thì caller tự rơi xuống bản kế.

    Trong nhóm official, KHÔNG chọn thuần theo độ mới nữa (user chốt): 1 chương có thể
    có nhiều official khác nền tảng/chất lượng typeset khác nhau -> ưu tiên nhóm dịch tốt
    (TappyToon...) hơn bản re-up mới nhất (Webcomic). Xem OFFICIAL_GROUP_RANK.

    Vì sao ưu tiên NHÓM hơn ĐỘ MỚI ở nhóm SCAN (user chốt 19/08): các bản "no group"
    thường là raw/batch đè lên bản nhóm scan cũ hơn nhưng chỉn chu hơn (vd Dai ch.345-349:
    bản 'no group' 6 tháng đè lên bản Square Ocean 10 tháng). Ưu tiên bản có nhóm cho chất
    lượng ổn định; bản không nhóm chỉ để DỰ PHÒNG (nếu cả số chương chỉ có bản không
    nhóm thì vẫn tải, KHÔNG bỏ chương — user chốt phương án 1)."""
    if pin:
        want = _norm_group(pin)
        return sorted((v for v in versions if _norm_group(_group_name(v)) == want),
                      key=lambda v: v["id"], reverse=True)
    off = sorted((v for v in versions if v.get("isOfficial")),
                 key=lambda v: (_official_rank(v), -v["id"]))
    scan = [v for v in versions if not v.get("isOfficial")]
    grouped = sorted((v for v in scan if _group_name(v) != "?"),
                     key=lambda v: v["id"], reverse=True)
    ungrouped = sorted((v for v in scan if _group_name(v) == "?"),
                       key=lambda v: v["id"], reverse=True)
    return off + grouped + ungrouped


def _group_name(ver):
    g = ver.get("group")
    return (g.get("name") if isinstance(g, dict) else g) or "?"


PIN_AUTO = "auto"   # --group auto = BỎ ghim (xoá "pin" sidecar, về luật mặc định)


def _norm_group(name):
    """'Yen Press' / 'yenpress' / 'YEN-PRESS' -> 'yenpress': so khớp tên nhóm KHÔNG phân
    biệt hoa/thường, khoảng trắng, ký tự lạ (user gõ tay trên Telegram)."""
    return re.sub(r"[^0-9a-z]+", "", str(name or "").lower())


def resolve_pin(requested, by_num):
    """Tên nhóm user gõ -> tên HIỂN THỊ chuẩn trên site (ghi sidecar/log). Khớp đúng (đã
    chuẩn hoá) trước; không có thì khớp CHUỖI CON duy nhất ('hive' -> Hivetoon). Không
    khớp / mơ hồ -> ValueError kèm danh sách nhóm có trên bộ (1 dòng — supervisor lấy dòng
    log cuối làm tin ❌) để user gõ lại; KHÔNG tải nhầm nhóm."""
    names = {}
    for vers in by_num.values():
        for v in vers:
            g = _group_name(v)
            if g != "?":
                names.setdefault(_norm_group(g), g)
    want = _norm_group(requested)
    if want and want in names:
        return names[want]
    subs = [n for n in names if want and want in n]
    if len(subs) == 1:
        return names[subs[0]]
    avail = ", ".join(sorted(names.values(), key=str.lower)) or "(không có nhóm nào)"
    why = (f"mơ hồ — khớp {len(subs)} nhóm ({', '.join(names[n] for n in subs)})"
           if subs else "không có trên bộ này")
    raise ValueError(f"Nhóm '{requested}' {why}. Nhóm có trên bộ: {avail}")


def read_sidecar(folder: Path):
    try:
        # utf-8-sig: tha cho file bị editor/PowerShell chèn BOM (json.loads chê BOM)
        return json.loads((folder / SIDECAR).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def write_sidecar(folder: Path, ver, pin=None):
    """pin = tên nhóm GHIM (chuẩn) -> ghi thêm "pin" để lượt sau không thay bằng Official."""
    data = {"chapterId": ver["id"], "groupId": ver.get("groupId"),
            "group": _group_name(ver), "isOfficial": bool(ver.get("isOfficial")),
            "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    if pin:
        data["pin"] = pin
    _save_sidecar(folder, data)


def _save_sidecar(folder: Path, data):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / SIDECAR).write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# --- Tiện ích file trong folder chương -------------------------------------------

def _page_file(folder: Path, i: int):
    """File trang i đã có trên đĩa (đuôi bất kỳ — sau sniff có thể là .jpg/.png)."""
    for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".avif", ".bmp"):
        p = folder / f"{i:03d}{ext}"
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def _unscramble_ops(scrambled, w, h, ops):
    """Xếp lại 1 ảnh TRÁO Ô theo bản đồ drawImage ghi từ apply() của site (xem
    descramble_ops). Mỗi op áp THEO THỨ TỰ (op sau đè op trước) lên canvas cỡ (w,h):
      argc 2 -> drawImage(img,dx,dy)                   : dán FULL ảnh nguồn tại (dx,dy)
      argc 4 -> drawImage(img,dx,dy,dw,dh)             : co FULL về (dw,dh) rồi dán
      argc 8 -> drawImage(img,sx,sy,sw,sh,dx,dy,dw,dh) : cắt ô nguồn ->(co nếu khác cỡ)-> dán
    Trả webp bytes; thiếu Pillow / lỗi -> None (người gọi coi trang là thiếu, chạy lại bù)."""
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        src = Image.open(io.BytesIO(scrambled)).convert("RGB")
    except Exception:
        return None

    def _i(x):
        try:
            return int(round(float(x)))
        except (TypeError, ValueError):
            return 0

    W = _i(w) or src.width
    H = _i(h) or src.height
    if W <= 0 or H <= 0 or W * H > 64 * 1024 * 1024:   # cỡ vô lý -> bỏ
        return None
    dst = Image.new("RGB", (W, H))
    for op in ops or []:
        a = op.get("a") or []
        argc = op.get("argc")
        try:
            if argc == 2 and len(a) >= 2:
                dst.paste(src, (_i(a[0]), _i(a[1])))
            elif argc == 4 and len(a) >= 4:
                dst.paste(src.resize((max(1, _i(a[2])), max(1, _i(a[3])))),
                          (_i(a[0]), _i(a[1])))
            elif argc == 8 and len(a) >= 8:
                sx, sy, sw, sh = _i(a[0]), _i(a[1]), max(1, _i(a[2])), max(1, _i(a[3]))
                dx, dy, dw, dh = _i(a[4]), _i(a[5]), max(1, _i(a[6])), max(1, _i(a[7]))
                tile = src.crop((sx, sy, sx + sw, sy + sh))
                if (dw, dh) != (sw, sh):
                    tile = tile.resize((dw, dh))
                dst.paste(tile, (dx, dy))
        except Exception:
            continue
    try:
        buf = io.BytesIO()
        dst.save(buf, "WEBP", quality=92, method=4)
        return buf.getvalue()
    except Exception:
        return None


def _fix_ext(path: Path) -> Path:
    """URL comix không có đuôi -> tải về đặt .webp rồi sửa theo magic bytes thật."""
    try:
        with path.open("rb") as f:
            head = f.read(32)
    except OSError:
        return path
    fmt = core.sniff_format(head)
    want = {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif",
            "bmp": ".bmp", "avif": ".avif", "heif": ".avif"}.get(fmt)
    if not want or path.suffix.lower() == want or \
            (want == ".jpg" and path.suffix.lower() == ".jpeg"):
        return path
    new = path.with_suffix(want)
    try:
        path.rename(new)
        return new
    except OSError:
        return path


def _recompress_webp(path: Path, q: int):
    """Nén lại 1 ảnh WEBP vừa tải về mức chất lượng q (comix nén nhẹ tay -> file to gấp
    ~1.6 lần Asura cho cùng pixel; hạ q85 nhẹ đi ~nửa mà không mất nét nhìn thấy).

    CHỈ đụng .webp TĨNH; gif/avif/webp-động bỏ qua (đừng phá khung ảnh động). An toàn:
    nén ra file .tmp, chỉ THAY bản gốc khi mở lại được VÀ tiết kiệm >= MIN_SAVE% (ảnh vốn
    đã nén chặt thì giữ nguyên, khỏi suy hao vô ích). Ngưỡng đồng bộ với convert_webp.py
    để hành vi nhất quán; ở đây ảnh luôn là bản thô comix (~q92) nên thường vượt xa ngưỡng.
    Mọi lỗi -> giữ nguyên byte gốc (không bao giờ để lại ảnh hỏng: download_image đã xác
    thực bản gốc rồi)."""
    if q <= 0 or path.suffix.lower() != ".webp":
        return
    tmp = path.with_suffix(".webp.tmp")
    try:
        from PIL import Image
        with Image.open(path) as im:
            if getattr(im, "is_animated", False):
                return                       # webp động (hiếm) -> đừng đụng
            rgb = im.convert("RGB")
        rgb.save(tmp, "WEBP", quality=q, method=4)
        if tmp.stat().st_size <= path.stat().st_size * (1 - RECOMPRESS_MIN_SAVE / 100):
            with Image.open(tmp) as chk:      # chắc chắn bản nén mở được trước khi thay
                chk.verify()
            os.replace(tmp, path)
        else:
            tmp.unlink()
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass


def _clear_images(folder: Path):
    """Đổi sang bản upload khác -> dọn ảnh (và .done) của bản cũ kẻo trộn ảnh 2 nhóm."""
    if not folder.is_dir():
        return
    for p in folder.iterdir():
        if p.is_file() and (p.suffix.lower() in core.IMG_EXTS
                            or p.name == ".done" or p.name.endswith(".bad")):
            try:
                p.unlink()
            except OSError:
                pass


def _mark_done(folder: Path):
    try:
        (folder / ".done").write_text("", encoding="utf-8")
    except OSError:
        pass


def _folder_has_images(folder: Path) -> bool:
    """Folder chương này có ≥1 ảnh thật không (để phân biệt 'đã có nội dung' với rỗng)."""
    if not folder.is_dir():
        return False
    try:
        for p in folder.iterdir():
            if p.is_file() and p.suffix.lower() in core.IMG_EXTS:
                return True
    except OSError:
        pass
    return False


def _effective_pin(side, pin, unpin):
    """Nhóm ghim ÁP CHO CHƯƠNG này: ghim của lệnh (--group) > ghim đã nhớ trong sidecar
    (lượt trước tải theo ghim) > None. unpin (--group auto) -> bỏ qua ghim sidecar."""
    if pin:
        return pin
    if side and side.get("pin") and not unpin:
        return side["pin"]
    return None


def _chapter_plan(folder, cands, side, done, pin):
    """QUYẾT ĐỊNH cho 1 chương -> 'have' (giữ nguyên, bỏ qua) | 'replace' (tải bản khác
    vào .comix-tmp rồi tráo folder) | 'fetch' (tải mới / tải tiếp thẳng vào folder).
    Dùng CHUNG cho vòng lặp tải (run) và báo cáo sớm (_report_comix_plan) -> 2 nơi không
    bao giờ lệch luật; sửa luật chỉ sửa đây.
      pin=None : luật mặc định — đĩa Official & done -> have; đĩa có nội dung CHƯA
                 Official (gồm bản ngoài không sidecar) mà site có Official -> replace;
                 done -> have; còn lại fetch. KHÔNG thay scan->scan.
      pin=nhóm : chỉ so với NHÓM ghim — đĩa đã là bản nhóm đó & done -> have; đĩa có
                 nội dung của bản KHÁC (kể cả Official) -> replace; còn lại fetch.
    `cands` đã lọc theo pin (candidates_for). cands RỖNG khi ghim = site không có bản
    nhóm đó: done -> have (giữ nguyên), else -> 'nopin' (caller báo + bỏ qua)."""
    has_content = _folder_has_images(folder)
    if pin:
        if not cands:
            return "have" if done else "nopin"
        on_disk_pinned = bool(side) and _norm_group(side.get("group")) == _norm_group(pin)
        if on_disk_pinned and done:
            return "have"
        if has_content and not on_disk_pinned:
            return "replace"
        return "fetch"
    on_disk_official = bool(side) and bool(side.get("isOfficial"))
    if on_disk_official and done:
        return "have"
    best = cands[0] if cands else {}
    upgrade = has_content and not on_disk_official and bool(best.get("isOfficial"))
    if done and not upgrade:
        return "have"
    return "replace" if upgrade else "fetch"


def _report_comix_plan(title, nums, by_num, out_root, args, pin=None, unpin=False):
    """Nhắn Telegram BÁO CÁO SỚM cho comix: X/Y chương + danh sách cần nâng cấp/tải,
    tính TỪ ĐĨA (không thêm request), TRƯỚC khi tải ảnh. Phân loại qua `_chapter_plan`
    (cùng hàm với vòng lặp tải) nên không lệch. 'Official' = bản tick 'v' (isOfficial).
    Best-effort, không raise ra."""
    official_have, have_other, upgrade_list, repin_list, need_list, nopin_list = \
        [], [], [], [], [], []
    recheck = getattr(args, "recheck", False)
    for num in nums:
        folder = out_root / f"Chapter {core.fmt_num(num)}"
        side = read_sidecar(folder)
        eff_pin = _effective_pin(side, pin, unpin)
        cands = candidates_for(by_num.get(num) or [], eff_pin)
        done = (folder / ".done").exists() and not recheck
        plan = _chapter_plan(folder, cands, side, done, eff_pin)
        if plan == "have":
            (official_have if (side and side.get("isOfficial")) else have_other).append(num)
        elif plan == "replace":
            (repin_list if eff_pin else upgrade_list).append(num)
        elif plan == "nopin":
            nopin_list.append(num)
        else:
            need_list.append(num)
    have_total = len(official_have) + len(have_other)
    lines = [f"📘 {title} — comix"]
    if pin:
        lines.append(f"• Ghim nhóm: [{pin}] — chỉ tải bản của nhóm này")
    elif unpin:
        lines.append("• Bỏ ghim nhóm (auto) — về luật mặc định")
    lines += [f"• Trên site: {len(nums)} chương",
              f"• Đã có sẵn: {have_total} (Official {len(official_have)})",
              f"• Cần nâng cấp → Official: {len(upgrade_list)}"
              + (f" — ch. {core.compact_chapters(upgrade_list)}" if upgrade_list else "")]
    if repin_list:
        lines.append(f"• Cần thay bằng bản ghim: {len(repin_list)}"
                     f" — ch. {core.compact_chapters(repin_list)}")
    lines.append(f"• Cần tải mới/tải tiếp: {len(need_list)}"
                 + (f" — ch. {core.compact_chapters(need_list)}" if need_list else ""))
    if nopin_list:
        lines.append(f"• Không có bản nhóm ghim (bỏ qua): {len(nopin_list)}"
                     f" — ch. {core.compact_chapters(nopin_list)}")
    lines.append("→ Bắt đầu tải..." if (upgrade_list or repin_list or need_list)
                 else "→ Không có gì cần tải (đã đủ).")
    _notify_telegram("\n".join(lines))


# --- File DẤU cấp truyện (Cách 1: nhìn thấy được trong Explorer) ------------------
# Đánh dấu folder do comix quản (có / đang lên bản Official) để user phân biệt với
# folder scan tải từ site khác mà TỰ TAY xoá folder scan trùng. Tên file mang sẵn số
# 'official/tổng' nên khỏi mở ra đọc; reader + check_library bỏ qua vì không phải ảnh.
MARKER_PREFIX = "_COMIX_official_"    # + "{off}-{total}.txt"


def write_series_marker(out_root: Path, slug: str):
    """Ghi/đè file dấu ở gốc folder truyện. Đếm theo sidecar từng chương:
      official = bản tick 'v'; scan = bản nhóm do comix tải; ngoài = có ảnh nhưng
      KHÔNG có sidecar (tải từ site khác, chưa nâng cấp). CHỈ ghi khi comix thực sự
      đã đóng góp ≥1 chương (off+scan>0) — folder toàn bản ngoài thì chưa đánh dấu."""
    off = scan = foreign = 0
    try:
        subdirs = [d for d in out_root.iterdir() if d.is_dir()]
    except OSError:
        return
    for d in subdirs:
        if not _folder_has_images(d):
            continue
        sc = read_sidecar(d)
        if sc is None:
            foreign += 1
        elif sc.get("isOfficial"):
            off += 1
        else:
            scan += 1
    if off + scan == 0:        # comix chưa đóng góp gì vào folder này -> chưa đánh dấu
        return
    total = off + scan + foreign
    for old in out_root.glob(MARKER_PREFIX + "*.txt"):   # dọn file dấu cũ (số khác)
        try:
            old.unlink()
        except OSError:
            pass
    lines = [
        "FOLDER NAY DO COMIX (comix.to) QUAN LY.",
        "Giu folder nay. Neu co folder trung truyen tai tu site khac (khong co file "
        "dau nay) thi XOA folder do.",
        "",
        f"slug     : {slug}",
        f"official : {off} chuong (ban tick 'v')",
        f"scan     : {scan} chuong (comix chua co official)",
        f"ngoai    : {foreign} chuong (tai tu site khac, chua nang cap)",
        f"tong     : {total} chuong",
        f"cap nhat : {datetime.now():%Y-%m-%d %H:%M:%S}",
    ]
    try:
        (out_root / f"{MARKER_PREFIX}{off}-{total}.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


# --- Vòng tải chính --------------------------------------------------------------

def _resilient(cs, call):
    """Chạy `call()` trên session `cs`; Chromium chết giữa chừng -> cs.relaunch() rồi
    thử lại trên browser mới. Quá ngưỡng dựng lại -> relaunch() ném BrowserGone ra
    ngoài = fatal. `call` phải là lambda tham chiếu `cs` (đừng truyền bound method của
    session cũ — relaunch thay ctx/page BÊN TRONG cùng object nên bound method vẫn đúng,
    nhưng lambda cho rõ ý)."""
    while True:
        try:
            return call()
        except BrowserGone:
            cs.relaunch()


def _scan_pages(folder: Path):
    """{số trang: (Path, mtime)} của các file ảnh trang (tên mở đầu bằng số) trong folder
    chương. Dùng scandir: trên Windows stat có sẵn từ lượt liệt kê nên quét cả thư viện
    (vài nghìn chương) vẫn nhanh. Folder không có -> {}."""
    out = {}
    try:
        with os.scandir(folder) as it:
            for e in it:
                stem, ext = os.path.splitext(e.name)
                if ext.lower() not in core.IMG_EXTS or stem.lower() == "cover":
                    continue
                m = re.match(r"(\d+)", stem)
                if not m:
                    continue
                try:
                    if e.is_file():
                        out[int(m.group(1))] = (Path(e.path), e.stat().st_mtime)
                except OSError:
                    pass
    except OSError:
        pass
    return out


def _parse_at(s):
    """Trường "at" của sidecar ('%Y-%m-%d %H:%M:%S', giờ máy) -> epoch; hỏng/thiếu -> None."""
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp()
    except (TypeError, ValueError):
        return None


def _scr_page_trusted(path: Path) -> bool:
    """Trang TRÁO Ô trên đĩa đã là bản giải-xáo đúng chưa? = file ghi SAU mốc
    UNSCRAMBLE_SINCE (trước mốc code chưa giải-xáo được -> chắc chắn còn xáo)."""
    try:
        return path.stat().st_mtime >= UNSCRAMBLE_SINCE
    except OSError:
        return False


def _mark_unscr(folder: Path, side):
    """Ghi cờ UNSCR_FLAG vào sidecar: chương đã soi comix + giải-xáo đủ theo mốc."""
    data = dict(side or read_sidecar(folder) or {})
    data[UNSCR_FLAG] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_sidecar(folder, data)


def repair_offline_state(folder: Path, side, done: bool):
    """Phân loại 1 chương cho /repair CHỈ bằng ĐĨA (sidecar + ngày ghi file), KHÔNG mạng.
    Dùng CHUNG cho job vá (_repair_scramble_chapter) và quét toàn thư viện (repair_scan)
    -> bản xem trước trên bot khớp đúng việc job sẽ làm. Trả (state, info):
      'noimg'       folder trống/không có                      -> bỏ qua
      'notofficial' không sidecar (site khác) / bản scan nhóm  -> bỏ qua (chỉ Official xáo)
      'ok'          đã soi (cờ unscr_ok) / mọi trang 10,20,30.. đều ghi SAU mốc
      'partialdl'   chưa .done = đang tải dở -> để /tai lo (resume tự giải-xáo lại, _page_ok)
      'edited'      .done mà THỦNG số trang (xoá tay?) -> bỏ qua + báo, info["gaps"]
      'check'       cần soi comix. info["old"] = trang 10,20.. còn ngày cũ; info["strict"]
                    = True khi ngày file KHÔNG đáng tin (tải trước mốc mà phần lớn trang
                    thường lại mang ngày SAU mốc = cả chương bị ghi lại, vd nén lại tại
                    chỗ) -> làm lại MỌI trang xáo bất kể ngày.
    Vì sao lúc dò offline chỉ nhìn trang bội 10: comix chèn trang xáo đúng các vị trí đó
    (dump payload 01/09 + ~450 chương có vết repair, chưa trang lẻ nào từng bị ghi lại).
    Lên mạng rồi thì dùng cờ s:1 THẬT của site, không đoán nữa."""
    pages = _scan_pages(folder)
    if not pages:
        return "noimg", {}
    if not side or not side.get("isOfficial"):
        return "notofficial", {}
    if side.get(UNSCR_FLAG):
        return "ok", {}
    if not done:
        return "partialdl", {}
    gaps = sorted(set(range(1, max(pages) + 1)) - set(pages))
    if gaps:
        return "edited", {"gaps": gaps}
    tens = sorted(i for i in pages if i % 10 == 0)
    rest = [mt for i, (_p, mt) in pages.items() if i % 10]
    at = _parse_at(side.get("at"))
    if at is not None and at < UNSCRAMBLE_SINCE and rest \
            and statistics.median(rest) >= UNSCRAMBLE_SINCE:
        return "check", {"strict": True, "old": tens}
    old = [i for i in tens if pages[i][1] < UNSCRAMBLE_SINCE]
    if not old:
        return "ok", {}
    return "check", {"strict": False, "old": old}


def _repair_scramble_chapter(cs, img_client, folder, versions, side, args):
    """Vá 1 chương ĐÃ tải còn trang TRÁO Ô (bản Official). Trả (status, n_fixed, info).
    Dò bằng repair_offline_state (đĩa, không mạng) — trạng thái khác 'check' trả nguyên
    ('noimg'/'notofficial'/'ok'/'partialdl'/'edited'), KHÔNG chạm mạng. 'check' mới lên comix:
      'gone'      - bản upload đang nằm trên đĩa (sidecar chapterId) không còn trên comix
                    (hoặc 0 trang) -> bỏ qua + báo. KHÔNG lùi sang bản nhóm khác (sẽ ghép
                    ảnh 2 nhóm vào 1 chương — user chốt 27/09).
      'fetchfail' - chưa lấy được danh sách trang (mạng/quảng cáo) -> chạy lại để bù
      'edited'    - số trang trên đĩa khác số trang của ĐÚNG bản đó (xoá/đánh số lại tay?)
                    -> bỏ qua: ghi theo số thứ tự sẽ đè nhầm trang khác
      'verified'  - không trang nghi nào cần làm lại -> ghi cờ, lần sau bỏ qua khỏi mạng
      'fixed'     - đã làm lại đủ trang nghi -> ghi cờ
      'partial'   - vá hụt vài trang (info["still"]) -> chạy lại để bù
    Trang nghi site VẪN đánh s:1 -> giải-xáo; site đã THÔI xáo (không cờ) -> tải lại thẳng
    (ảnh tại url nay sạch). Chỉ đụng trang nghi của ĐÚNG bản đang có; trang thường giữ
    nguyên. Nghiệm thu bằng tín hiệu thật (giải-xáo trả bytes / tải qua kiểm tra), KHÔNG
    soi detector. Xem [[comix-scramble-s-flag]]."""
    done = (folder / ".done").exists()
    state, info = repair_offline_state(folder, side, done)
    if state != "check":
        return state, 0, info
    ver = next((v for v in versions if v.get("id") == side.get("chapterId")), None)
    if ver is None:
        return "gone", 0, {"group": side.get("group")}
    page_items = _resilient(cs, lambda: cs.fetch_pages(ver["url"], ver["id"]))
    if page_items is None:
        return "fetchfail", 0, {}
    if not page_items:
        return "gone", 0, {"group": side.get("group"), "empty": True}
    pages = _scan_pages(folder)
    if set(pages) != set(range(1, len(page_items) + 1)):
        return "edited", 0, {"disk": len(pages), "site": len(page_items)}
    s1 = {i for i, it in enumerate(page_items, 1) if it.get("s")}
    # Trang NGHI = trang 10,20,.. còn ngày cũ (dò offline) + trang site đang đánh s:1 mà
    # còn ngày cũ. Ngày file không đáng tin (strict) -> mọi trang 10,20,.. + mọi trang s:1.
    # KHÔNG chỉ dựa cờ s:1: comix có thể THÔI xáo (27/09: Dungeon Reset ch.6 hết cờ s, ảnh
    # tại url đã sạch) -> chỉ nhìn cờ thì trang xáo cũ trên đĩa bị coi là "sạch" oan.
    if info.get("strict"):
        sus = {i for i in pages if i % 10 == 0} | s1
    else:
        sus = set(info.get("old") or []) | {i for i in s1 if pages[i][1] < UNSCRAMBLE_SINCE}
    if not sus:
        _mark_unscr(folder, side)
        return "verified", 0, {}
    scr_t = sorted(sus & s1)    # site VẪN xáo trang này -> giải-xáo như đường tải
    http_t = sorted(sus - s1)   # site nay trả ảnh SẠCH tại url -> tải lại thẳng
    q = getattr(args, "comix_q", RECOMPRESS_Q)
    done_ok = set()
    if scr_t:
        pairs = [(i, page_items[i - 1]["url"]) for i in scr_t]
        got = _resilient(cs, lambda: cs.descramble_pages(ver["url"], pairs, img_client))
        for i in scr_t:
            data = got.get(i)
            if not data:
                continue
            old = pages[i][0]
            if old.suffix.lower() != ".webp":
                try:
                    old.unlink()
                except OSError:
                    pass
            (folder / f"{i:03d}.webp").write_bytes(data)
            _recompress_webp(_fix_ext(folder / f"{i:03d}.webp"), q)
            done_ok.add(i)
    if http_t:
        img_client.refresh_identity()   # vé mới nhất từ browser (main thread) trước khi tải
        for i in http_t:
            if _redownload_page(folder, i, page_items[i - 1]["url"], img_client, q):
                done_ok.add(i)
        _drop_repair_tmp(folder)
    still = sorted(sus - done_ok)
    how = {"scr": len([i for i in scr_t if i in done_ok]),
           "http": len([i for i in http_t if i in done_ok])}
    if still:
        return "partial", len(done_ok), {"still": still, **how}
    _mark_unscr(folder, side)
    return "fixed", len(done_ok), how


REPAIR_TMP = ".repair-tmp"   # trong folder chương; đầu-dấu-chấm -> reader/check bỏ qua


def _redownload_page(folder: Path, i: int, url: str, img_client, q: int) -> bool:
    """Tải LẠI thẳng trang i (comix nay trả ảnh sạch tại url) vào chỗ tạm, qua kiểm tra
    của download_image rồi mới THAY file cũ — hụt thì file cũ giữ nguyên (không bao giờ để
    trang trống). 403 lần đầu -> làm mới vé rồi thử 1 lần; lần 2 để Forbidden bay ra (dừng
    phiên như đường tải thường, tránh thử mù tụt uy tín IP)."""
    tmpd = folder / REPAIR_TMP
    tmpd.mkdir(exist_ok=True)
    for p in tmpd.glob(f"{i:03d}.*"):
        try:
            p.unlink()
        except OSError:
            pass
    tmp = tmpd / f"{i:03d}.webp"
    try:
        ok = core.download_image(url, tmp, img_client)
    except core.Forbidden:
        img_client.refresh_identity()
        ok = core.download_image(url, tmp, img_client)
    if not ok or not tmp.exists() or tmp.stat().st_size == 0:
        return False
    tmp = _fix_ext(tmp)
    _recompress_webp(tmp, q)
    old = _page_file(folder, i)
    if old is not None:
        try:
            old.unlink()
        except OSError:
            return False
    os.replace(tmp, folder / tmp.name)
    return True


def _drop_repair_tmp(folder: Path):
    shutil.rmtree(folder / REPAIR_TMP, ignore_errors=True)


def _how_note(info):
    """'giải-xáo 1, tải lại thẳng 2' — trang site vẫn xáo vs site đã thôi xáo."""
    bits = []
    if info.get("scr"):
        bits.append(f"giải-xáo {info['scr']}")
    if info.get("http"):
        bits.append(f"tải lại thẳng {info['http']}")
    return ", ".join(bits) or "0"


def _edited_note(info):
    """Mô tả ngắn chương 'lệch số trang' cho log/Telegram."""
    if "site" in info:
        return f"đĩa {info['disk']} trang / comix {info['site']} trang"
    return f"thiếu trang {core.compact_ints(info.get('gaps') or [])}"


def _chapter_num_of(dirname: str):
    """'Chapter 12.5' -> 12.5 ; tên khác -> None (folder chương comix luôn 'Chapter N')."""
    m = re.fullmatch(r"Chapter (\d+(?:\.\d+)?)", dirname)
    return float(m.group(1)) if m else None


def _marker_slug(series_dir: Path):
    """Đọc slug từ file dấu _COMIX_official_*.txt ở gốc folder truyện; không có -> None."""
    for mk in series_dir.glob(MARKER_PREFIX + "*.txt"):
        try:
            for line in mk.read_text(encoding="utf-8", errors="replace").splitlines():
                k, _, v = line.partition(":")
                if k.strip() == "slug" and v.strip():
                    return v.strip()
        except OSError:
            pass
    return None


def repair_scan(out_dir: Path):
    """Quét TOÀN thư viện (chỉ đĩa, không mạng) tìm chương comix còn trang xáo -> dict cho
    lệnh bot `/repair all` (xem trước + tạo job) và tổng kết 'kiểm lại'. Truyện comix nhận
    qua file dấu (có slug -> link). Folder có chương Official mà THIẾU file dấu -> liệt kê
    riêng (không suy ra link được, user /repair tay). Phân loại qua repair_offline_state
    (cùng hàm job dùng) nên số xem trước khớp việc job làm."""
    series, nomarker = [], []
    try:
        dirs = sorted(d for d in out_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
    except OSError:
        dirs = []
    for sd in dirs:
        slug = _marker_slug(sd)
        chaps = []
        try:
            chaps = [d for d in sd.iterdir() if d.is_dir() and _chapter_num_of(d.name) is not None]
        except OSError:
            pass
        if not slug:
            if any((d / SIDECAR).exists() and (read_sidecar(d) or {}).get("isOfficial")
                   for d in chaps):
                nomarker.append(sd.name)
            continue
        rec = {"folder": sd.name, "slug": slug, "url": f"{BASE}/title/{slug}",
               "official": 0, "check": [], "strict": [], "check_pages": 0,
               "edited": [], "partialdl": []}
        for d in sorted(chaps, key=lambda d: _chapter_num_of(d.name)):
            side = read_sidecar(d)
            state, info = repair_offline_state(d, side, (d / ".done").exists())
            num = _chapter_num_of(d.name)
            if side and side.get("isOfficial"):
                rec["official"] += 1
            if state == "check":
                rec["check"].append(num)
                rec["check_pages"] += len(info.get("old") or [])
                if info.get("strict"):
                    rec["strict"].append(num)
            elif state == "edited":
                rec["edited"].append([num, info.get("gaps") or []])
            elif state == "partialdl":
                rec["partialdl"].append(num)
        series.append(rec)
    return {"since": UNSCRAMBLE_SINCE_TXT, "series": series, "nomarker": nomarker}


def print_repair_scan(out_dir: Path):
    """In kết quả repair_scan cho người đọc + 1 dòng REPAIR_SCAN_JSON cho bot."""
    res = repair_scan(out_dir)
    print(f"Quét trang TRÁO Ô trên đĩa ({out_dir}) — mốc: ghi trước "
          f"{UNSCRAMBLE_SINCE_TXT} = chưa giải-xáo")
    for s in res["series"]:
        line = f"  {s['folder']}: Official {s['official']} chương"
        if s["check"]:
            line += (f" | CẦN soi comix {len(s['check'])} chương (~{s['check_pages']} trang)"
                     f" — ch. {core.compact_chapters(s['check'], max_groups=60)}")
        else:
            line += " | sạch"
        if s["strict"]:
            line += f" | ngày file không tin được: {len(s['strict'])}"
        if s["edited"]:
            line += f" | lệch số trang: {len(s['edited'])}"
        if s["partialdl"]:
            line += f" | đang tải dở: {len(s['partialdl'])}"
        print(line)
    if res["nomarker"]:
        print("  Có bản Official nhưng THIẾU file dấu (cần /repair <link> tay): "
              + ", ".join(res["nomarker"]))
    print("REPAIR_SCAN_JSON:" + json.dumps(res, ensure_ascii=False))


def run(args):
    try:
        import playwright  # noqa: F401 — dep tùy chọn, chỉ cần cho comix
    except ImportError:
        print("Thiếu Playwright (chỉ site comix.to cần). Cài bằng:\n"
              "   pip install playwright\n"
              "   python -m playwright install chromium", file=sys.stderr)
        sys.exit(1)

    core.reap_decode_crash()
    core.session.headers["Referer"] = REFERER   # CDN wowpic đòi Referer comix.to

    slug = series_slug(args.series)
    print(f"Site: comix  |  Truyện: {slug}")
    # Dọn Chromium mồ côi + khoá profile cũ TRƯỚC khi mở, kẻo con mới chuyển URL cho
    # con cũ rồi tự thoát -> Playwright treo ở about:blank (sự cố 14/08). An toàn vì 1
    # worker tuần tự. Nghỉ 1s cho OS nhả handle trước khi launch_persistent_context.
    _kill_profile_chrome()
    time.sleep(1)
    print("(Sẽ mở 1 cửa sổ Chromium để lấy metadata — ĐỪNG đóng nó, tool tự đóng khi xong.)")

    try:
        with ComixSession() as cs:
            img_client = ComixImageClient(cs)   # tải ảnh: giả TLS Chrome + mượn vé sống
            title, cover, items = _resilient(cs, lambda: cs.fetch_series(slug))
            by_num = group_versions(items)
            if not by_num:
                print("Không lấy được danh sách chương. Kiểm tra lại URL.", file=sys.stderr)
                sys.exit(1)
            nums = sorted(by_num)
            print(f"Tổng số chương tìm thấy: {len(nums)} "
                  f"({sum(len(v) for v in by_num.values())} bản upload)")

            # GHIM NHÓM (--group): đổi tên user gõ -> tên chuẩn trên site; không có trên bộ
            # -> thoát 1 (dòng cuối log = tin ❌ của bot, kèm danh sách nhóm để gõ lại).
            pin_name, unpin = None, False
            group_arg = (getattr(args, "group", None) or "").strip()
            if group_arg.lower() == PIN_AUTO:
                unpin = True
                print("Bỏ ghim nhóm (auto): chương nào đang ghim sẽ về luật mặc định.")
            elif group_arg:
                try:
                    pin_name = resolve_pin(group_arg, by_num)
                except ValueError as e:
                    print(f"!!! {e}", file=sys.stderr)
                    sys.exit(1)
                print(f"Ghim nhóm: [{pin_name}] — chỉ tải bản của nhóm này "
                      "(không rơi về nhóm khác).")

            if args.chapters:
                wanted = core.parse_selection(args.chapters)
                nums = [n for n in nums if n in wanted]
            else:
                if args.c_from is not None:
                    nums = [n for n in nums if n >= args.c_from]
                if args.c_to is not None:
                    nums = [n for n in nums if n <= args.c_to]
            if not nums:
                print("Không có chương nào khớp lựa chọn.", file=sys.stderr)
                sys.exit(1)

            repair_mode = getattr(args, "repair_scramble", False)
            # Chế độ vá: KHOÁ đúng folder đã có. `/repair all` truyền --dest-name = folder
            # mang file dấu (phòng comix đổi tên truyện -> tên suy từ title lệch folder cũ).
            # Không thấy folder -> dừng, KHÔNG tạo folder rỗng (repair không tải chương mới).
            dest_name = getattr(args, "dest_name", None) if repair_mode else None
            out_root = Path(args.out) / core.safe_name(dest_name or title)
            tmp_root = Path(args.out) / TMP_DIRNAME / core.safe_name(title)
            if repair_mode and not out_root.is_dir():
                print(f"Không thấy folder truyện “{out_root.name}” trong {args.out} — "
                      "repair chỉ vá chương đã tải, không tạo mới.", file=sys.stderr)
                sys.exit(1)
            out_root.mkdir(parents=True, exist_ok=True)
            # xác tráo-folder dở từ phiên trước (crash giữa swap) -> dọn
            if tmp_root.exists():
                for d in tmp_root.glob("*.__trash"):
                    shutil.rmtree(d, ignore_errors=True)
            if cover and not repair_mode:     # vá thì khỏi đụng ảnh bìa
                # fetch_series vừa (có thể) giải Cloudflare -> lấy vé mới cho cover.
                img_client.refresh_identity()
                # thử bản full (bỏ '@280') trước, hụt (404) thì lấy luôn bản thumb.
                # Cover là phụ: 403/lỗi ở đây KHÔNG được giết cả phiên tải chương.
                full = re.sub(r"@\d+(\.\w+)$", r"\1", cover)
                try:
                    for cu in dict.fromkeys([full, cover]):
                        core.download_cover(cu, out_root, client=img_client)
                        if any(p.stem.lower() == "cover" for p in out_root.iterdir()
                               if p.is_file() and p.suffix.lower() in core.IMG_EXTS):
                            break
                except core.Blocked:
                    print("  ! Bỏ qua ảnh bìa (bị chặn tạm) — tải chương vẫn tiếp tục.",
                          file=sys.stderr)
                    core.gate.abort = False   # gỡ cầu dao nếu cover vừa kéo, để tải chương
            print(f"Sẽ xử lý {len(nums)} chương vào: {out_root.resolve()}\n")

            # BÁO CÁO SỚM (Option 1, user chốt 14/08): đã có danh sách chương + trạng thái
            # đĩa -> nhắn Telegram X/Y + cần nâng cấp/tải NGAY, TRƯỚC khi tải ảnh. comix không
            # có peek rẻ nên báo cáo này phải chờ Chromium mở xong (không tức thì như site
            # thường). Chỉ ĐỌC ĐĨA (không thêm request). Lỗi ở đây KHÔNG được cản việc tải.
            if not repair_mode:
                try:
                    _report_comix_plan(title, nums, by_num, out_root, args,
                                       pin_name, unpin)
                except Exception as e:
                    print(f"  (bỏ qua báo cáo sớm: {e})", file=sys.stderr, flush=True)

            total = len(nums)
            active = 0
            fail_streak = 0   # số chương LIÊN TIẾP hụt ảnh (browser còn sống) -> cầu dao
            incomplete, source_broken, unfetched = [], [], []
            n_full = n_skipped = n_locked = n_upgraded = n_repinned = 0
            nopin = []        # chương ghim nhóm mà site không có bản nhóm đó (bỏ qua)
            img_ok = img_missing = img_broken = 0
            # Kết quả chế độ vá, theo nhóm -> tổng kết + REPAIR_RESULT_JSON (bot gộp đợt).
            rep = {"fixed": [], "verified": [], "partial": [], "fetchfail": [],
                   "gone": [], "edited": [], "partialdl": []}
            img_repaired = 0
            visited = set()   # folder chương đã đi qua (còn lại = chương không còn trên comix)

            for idx, num in enumerate(nums, 1):
                label = f"Chapter {core.fmt_num(num)}"
                prefix = f"[{idx}/{total}] {label}"
                folder = out_root / label   # tên CỐ ĐỊNH (không title) để tráo bản an toàn
                side = read_sidecar(folder)
                # --group auto: xoá ghim đã nhớ trong sidecar -> chương về luật mặc định.
                if unpin and side and side.get("pin"):
                    print(f"{prefix} — bỏ ghim [{side['pin']}]")
                    side.pop("pin", None)
                    _save_sidecar(folder, side)
                # Ghim áp cho chương này: của lệnh, hoặc đã nhớ trong sidecar lượt trước
                # (để auto-check hằng ngày KHÔNG thay lại bằng Official).
                eff_pin = _effective_pin(side, pin_name, unpin)
                cands = candidates_for(by_num[num], eff_pin)

                # CHẾ ĐỘ SỬA TRÁO Ô (--repair-scramble): chỉ vá chương ĐÃ tải còn trang xáo,
                # KHÔNG tải chương mới (dùng lệnh tải thường cho việc đó). Dò offline theo
                # MỐC ngày ghi file -> chương đã sạch bỏ nhanh, khỏi chạm mạng.
                if repair_mode:
                    visited.add(label)
                    # In tiến độ MỖI chương (kể cả chương bỏ nhanh) để log luôn tiến —
                    # tránh stall-watchdog supervisor kill oan khi quét nhiều chương sạch.
                    print(f"\r[{idx}/{total}] {label} — dò tráo ô...            ",
                          end="", flush=True)
                    status, nfix, info = _repair_scramble_chapter(
                        cs, img_client, folder, by_num[num], side, args)
                    img_repaired += nfix
                    if status == "fixed":
                        rep["fixed"].append(num)
                        cs.mark_progress()
                        print(f"{prefix} — đã làm lại {nfix} trang ({_how_note(info)})")
                        if args.cbz:
                            core.make_cbz(folder, skip_existing=False)
                    elif status == "verified":
                        rep["verified"].append(num)
                        cs.mark_progress()
                        print(f"{prefix} — soi comix: không trang xáo nào cần làm lại")
                    elif status == "partial":
                        rep["partial"].append(num)
                        cs.mark_progress()
                        print(f"{prefix} — giải-xáo {nfix} trang, CÒN sót trang "
                              f"{core.compact_ints(info['still'])} (chạy lại để bù)")
                    elif status == "fetchfail":
                        rep["fetchfail"].append(num)
                        print(f"{prefix} — chưa lấy được danh sách trang (mạng?), "
                              "chạy lại để bù")
                    elif status == "gone":
                        rep["gone"].append([num, info.get("group") or "?"])
                        print(f"{prefix} — bản gốc [{info.get('group') or '?'}] không còn "
                              "trên comix, bỏ qua (KHÔNG lấy bản nhóm khác)")
                    elif status == "edited":
                        rep["edited"].append([num, _edited_note(info)])
                        print(f"{prefix} — lệch số trang ({_edited_note(info)}), bỏ qua")
                    elif status == "partialdl":
                        rep["partialdl"].append(num)
                    # Chỉ nghỉ khi có CHẠM MẠNG; trạng thái offline bỏ nhanh (thuần đọc đĩa)
                    # nên khỏi nghỉ -> quét cả bộ rất nhanh.
                    if status in ("fixed", "verified", "partial", "fetchfail") \
                            or "site" in info or info.get("empty"):
                        active += 1
                        if active % 10 == 0:
                            rest = random.uniform(60, 90)
                            print(f"  (đang nghỉ {rest:.0f}s cho giống nhịp người đọc — "
                                  "KHÔNG phải treo...)", flush=True)
                            time.sleep(rest)
                        else:
                            time.sleep(random.uniform(0.7, 1.3) * args.delay)
                    continue

                done = (folder / ".done").exists() and not getattr(args, "recheck", False)
                # Folder đã có ảnh nhưng KHÔNG mang sidecar comix = bản tải từ site KHÁC
                # (Raven, Asura...) hoặc bản comix rất cũ. Coi là "bản ngoài/scan" để luật
                # upgrade cũng áp cho nó (thay bằng Official nếu comix nay có) — đây là ca
                # Dungeon Reset: 266 chương Raven .done, không sidecar, trước đây bị skip.
                on_disk_official = bool(side) and side.get("isOfficial")

                # 1)+2) QUYẾT ĐỊNH qua _chapter_plan (chung với báo cáo sớm): 'have' = giữ
                # nguyên (Official sẵn / đã xong / đã đúng bản ghim); 'replace' = đĩa có bản
                # khác -> tải vào chỗ tạm rồi tráo (Official thay scan/bản ngoài, hoặc bản
                # ghim thay bất kỳ); 'fetch' = tải mới/tiếp; 'nopin' = ghim mà site không có.
                plan = _chapter_plan(folder, cands, side, done, eff_pin)
                if plan == "have":
                    if eff_pin:
                        why = f"đã có bản ghim [{eff_pin}] (bỏ qua)"
                    elif on_disk_official:
                        why = "đã có bản Official (bỏ qua)"
                    else:
                        why = "đã xong trước đó (bỏ qua, khỏi quét mạng)"
                    print(f"{prefix} — {why}")
                    n_skipped += 1
                    if args.cbz:
                        core.make_cbz(folder, skip_existing=True)
                    continue
                if plan == "nopin":
                    print(f"{prefix} — site không có bản nhóm [{eff_pin}], bỏ qua "
                          "(giữ nguyên trên đĩa)")
                    nopin.append(label)
                    continue
                upgrade = plan == "replace"

                # 3) Chọn nơi tải + thứ tự ứng viên
                if upgrade:
                    dest = tmp_root / label      # tải bản mới vào chỗ tạm, xong mới tráo
                    pool = cands                 # đầu danh sách = Official / bản ghim
                else:
                    dest = folder
                    if side:   # tải dở -> ưu tiên tiếp ĐÚNG bản cũ, tránh trộn ảnh 2 nhóm
                        same = [v for v in cands if v["id"] == side.get("chapterId")]
                        pool = same + [v for v in cands if v["id"] != side.get("chapterId")]
                    else:
                        pool = cands

                # 4) Thử lần lượt ứng viên tới khi có ảnh. Chỉ ĐỘNG vào đĩa (dọn ảnh cũ +
                # ghi sidecar) khi bản này thực sự lấy được ảnh — bản fetch hụt/0-trang
                # KHÔNG được xoá nội dung đang có (tránh phá bản tải dở khi chỉ chập mạng).
                chosen, page_items, fetch_failed = None, [], False
                for ver in pool:
                    res = _resilient(cs, lambda v=ver: cs.fetch_pages(v["url"], v["id"]))
                    if res is None:              # bắt hụt (mạng/quảng cáo) -> thử bản khác
                        fetch_failed = True
                        print(f"{prefix} — bản [{_group_name(ver)}] chưa lấy được, thử bản khác...")
                        continue
                    if not res:                  # payload có nhưng 0 trang = khóa/premium thật
                        print(f"{prefix} — bản [{_group_name(ver)}] 0 trang, thử bản khác...")
                        continue
                    d_side = read_sidecar(dest)
                    # Dọn ảnh cũ nếu dest đang giữ bản KHÁC id, hoặc có ảnh không rõ nguồn
                    # (bản ngoài) — kẻo trộn ảnh 2 bản.
                    if (d_side and d_side.get("chapterId") != ver["id"]) \
                            or (d_side is None and _folder_has_images(dest)):
                        _clear_images(dest)
                    write_sidecar(dest, ver, eff_pin)   # ghim -> nhớ trong sidecar
                    chosen, page_items = ver, res
                    break
                if not chosen:
                    # Không dừng cả bộ: fetch hụt -> 'để sau' (chạy lại bù); 0-trang thật -> khóa.
                    if fetch_failed:
                        print(f"{prefix} — chưa lấy được ảnh (mạng/quảng cáo chèn?), "
                              "sẽ bù ở lần chạy sau")
                        unfetched.append(label)
                        core.append_log(f"{title} / {label}: chưa lấy được ảnh "
                                        "(mạng/quảng cáo) — chạy lại để bù")
                        # Cầu dao: browser CÒN SỐNG mà hụt nhiều chương liên tiếp = nghi bị
                        # chặn IP mềm / site đổi API -> dừng phiên + báo lỗi thật (thay vì
                        # ghi 'để sau' cả bộ rồi thoát 0 khiến tưởng đã tải xong).
                        fail_streak += 1
                        if fail_streak >= FAIL_STREAK_LIMIT:
                            raise FetchStalled(
                                f"{fail_streak} chương liên tiếp không lấy được ảnh dù "
                                "Chromium còn sống — nghi bị chặn IP mềm hoặc site đổi API")
                    else:
                        print(f"{prefix} — không bản nào có ảnh (khóa/premium?), bỏ qua")
                        n_locked += 1
                        fail_streak = 0   # site vẫn trả lời (khóa thật) -> không tính chuỗi hụt
                    continue

                # Chọn được bản có ảnh = có tiến triển -> reset các bộ đếm sự cố.
                cs.mark_progress()
                fail_streak = 0

                tag = "Official" if chosen.get("isOfficial") else _group_name(chosen)
                if eff_pin:      # bản ghim: hiện tên nhóm (Official cũng ghi rõ nhóm nào)
                    tag = f"ghim {_group_name(chosen)}" \
                        + (" Official" if chosen.get("isOfficial") else "")
                urls = [it["url"] for it in page_items]
                # Trang TRÁO Ô (cờ s:1) tải thô sẽ ra ảnh xáo -> phải giải-xáo qua canvas
                # của site; trang thường tải HTTP như cũ. Xem [[comix-scramble-s-flag]].
                scr = {i for i, it in enumerate(page_items, 1) if it.get("s")}
                pages = list(enumerate(urls, 1))
                # Trang 10,20,.. của bản Official còn ngày TRƯỚC mốc mà site nay KHÔNG đánh
                # s:1 = bản xáo thô thời chưa giải-xáo được (chương tải dở từ trước 02/09 rồi
                # tải tiếp). comix đã thôi xáo -> ảnh tại url nay sạch: xoá để tải lại.
                if chosen.get("isOfficial"):
                    for i in range(10, len(urls) + 1, 10):
                        f = _page_file(dest, i)
                        if f is not None and i not in scr and not _scr_page_trusted(f):
                            try:
                                f.unlink()
                            except OSError:
                                pass

                def _page_ok(i, _scr=scr, _dest=dest):
                    """Trang i đã ĐÚNG trên đĩa chưa? Trang tráo ô ghi TRƯỚC mốc = còn
                    xáo (tải dở từ thời chưa giải-xáo được) -> CHƯA. Không dùng detector
                    looks_scrambled: âm tính giả trên trang gần-trắng (xem UNSCRAMBLE_SINCE)."""
                    f = _page_file(_dest, i)
                    if f is None:
                        return False
                    if i in _scr and not _scr_page_trusted(f):
                        return False
                    return True

                http_jobs = [(i, u) for i, u in pages
                             if i not in scr and _page_file(dest, i) is None]
                scr_jobs = [(i, u) for i, u in pages if i in scr and not _page_ok(i)]
                have = len([i for i, _ in pages if _page_ok(i)])
                ok = done_ct = have
                print(f"\r{prefix} [{tag}] — {done_ct}/{len(urls)} ảnh, đang tải...   ",
                      end="", flush=True)
                if http_jobs:
                    # Vé mới nhất từ browser TRƯỚC khi tải (main thread) — bắt kịp ca
                    # cf_clearance hết hạn qua đêm / vừa xoay giữa phiên.
                    img_client.refresh_identity()
                    forbidden_retry = 0
                    while True:
                        remaining = [(i, u) for i, u in http_jobs
                                     if _page_file(dest, i) is None]
                        if not remaining:
                            break
                        done_ct = have + (len(http_jobs) - len(remaining))
                        try:
                            with ThreadPoolExecutor(max_workers=args.workers) as pool_ex:
                                futures = [pool_ex.submit(core.download_image, u,
                                                          dest / f"{i:03d}.webp", img_client)
                                           for i, u in remaining]
                                try:
                                    for f in as_completed(futures):
                                        if f.result():
                                            ok += 1
                                        done_ct += 1
                                        print(f"\r{prefix} [{tag}] — {done_ct}/{len(urls)} "
                                              "ảnh, đang tải...   ", end="", flush=True)
                                except (core.Blocked, core.TooMany429):
                                    core.gate.abort = True
                                    pool_ex.shutdown(cancel_futures=True)
                                    raise
                            break   # mẻ xong không lỗi -> thôi vòng retry
                        except core.Forbidden:
                            # 403 giữa chương: nhiều khả năng vé vừa xoay. Làm mới vé
                            # (main thread) rồi tải NỐT phần thiếu ĐÚNG 1 lần; vẫn 403
                            # -> để Forbidden bay ra = dừng phiên (chờ vài giờ). KHÔNG
                            # thử mù nhiều lần kẻo tụt điểm uy tín IP.
                            if forbidden_retry >= 1:
                                raise
                            forbidden_retry += 1
                            core.gate.abort = False   # gỡ cầu dao do pool vừa kéo
                            img_client.refresh_identity()
                            print(f"\n{prefix} — 403 (vé Cloudflare?), đã làm mới vé từ "
                                  "browser, thử lại phần còn thiếu...", flush=True)
                            time.sleep(2.0)
                got = {}     # {idx: bytes} — trang tráo ô giải-xáo được lượt này
                if scr_jobs:
                    # Trang tráo ô: giải-xáo bằng canvas của site rồi ghi bytes sạch.
                    # Browser chết -> _resilient dựng lại & thử lại (tự goto lại trang đọc).
                    print(f"\r{prefix} [{tag}] — giải-xáo {len(scr_jobs)} trang tráo ô "
                          "(canvas site)...          ", end="", flush=True)
                    got = _resilient(
                        cs, lambda: cs.descramble_pages(chosen["url"], scr_jobs, img_client))
                    for i, _u in scr_jobs:
                        data = got.get(i)
                        if not data:
                            continue
                        old = _page_file(dest, i)
                        if old is not None and old.suffix.lower() != ".webp":
                            try:
                                old.unlink()
                            except OSError:
                                pass
                        (dest / f"{i:03d}.webp").write_bytes(data)
                if http_jobs or scr_jobs:
                    # URL không có đuôi -> sửa đuôi theo định dạng thật, rồi RE-NÉN webp
                    # về q85 (comix nén nhẹ tay; xem RECOMPRESS_Q). Chỉ chạm ảnh MỚI tải/
                    # giải-xáo -> chương đã có sẵn không bị đụng lại khi chạy tiếp.
                    for i, _ in http_jobs + scr_jobs:
                        p = dest / f"{i:03d}.webp"
                        if p.exists() and p.stat().st_size > 0:
                            p = _fix_ext(p)
                            _recompress_webp(p, getattr(args, "comix_q", RECOMPRESS_Q))
                # ok/done chuẩn theo ĐĨA (retry có thể làm lệch bộ đếm cộng dồn). Trang
                # TRÁO Ô: nghiệm thu bằng TÍN HIỆU THẬT "giải-xáo có trả ra bytes chưa"
                # (got), KHÔNG soi lại looks_scrambled trên ảnh vừa giải-xáo — detector
                # (năng lượng đường nối) DƯƠNG TÍNH GIẢ trên webtoon dải dài: ảnh sạch vẫn
                # ~4-22 vì rãnh giữa khung tranh rơi trúng lưới chia (đo 02/09: Farmer of
                # Spirits ch2 t10=8.09, ch3 t30=4.67 tuy ảnh liền mạch; Solo Leveling 181
                # trang scan sạch >=4.0). Trang s:1 CÓ trong scr_jobs mà got không trả bytes
                # = giải-xáo hụt -> chưa xong; s:1 KHÔNG trong scr_jobs = đã sạch từ discovery.
                # Xem [[comix-scramble-s-flag]].
                scr_tried = {i for i, _ in scr_jobs}

                def _done_ok(i, _tried=scr_tried, _got=got, _dest=dest):
                    if _page_file(_dest, i) is None:
                        return False
                    if i in _tried and not _got.get(i):
                        return False
                    return True

                ok = len([i for i, _ in pages if _done_ok(i)])

                missing = [i for i, _ in pages if not _done_ok(i)]
                broken = [i for i in missing
                          if core.is_known_broken(dest / f"{i:03d}.webp")]
                retryable = [i for i in missing if i not in broken]
                complete = not retryable

                if complete:
                    _mark_done(dest)
                    core.gate.recover()   # 1 chương trọn vẹn = IP/CDN khỏe -> reset cầu dao
                    if upgrade:
                        # Tráo an toàn: cũ -> __trash (cùng ổ đĩa, rename là xong),
                        # tạm -> tên thật, rồi mới xóa rác. Crash điểm nào cũng còn
                        # nguyên 1 bản đọc được; xác __trash dọn ở đầu phiên sau.
                        trash = tmp_root / f"{label}.__trash"
                        # side có thể None (bản tải từ site khác, không sidecar)
                        old_group = (side.get("group") if side else None) \
                            or "bản ngoài (không rõ nhóm)"
                        if folder.exists():
                            folder.rename(trash)
                        dest.rename(folder)
                        shutil.rmtree(trash, ignore_errors=True)
                        # cbz cũ (nếu bản trước có) nay lệch nội dung -> bỏ; args.cbz sẽ nén lại
                        old_cbz = folder.parent / (label + ".cbz")
                        if old_cbz.exists():
                            try:
                                old_cbz.unlink()
                            except OSError:
                                pass
                        if eff_pin:
                            n_repinned += 1
                        else:
                            n_upgraded += 1
                        new_tag = tag if eff_pin else "Official"
                        print(f"\r{prefix} — DA THAY [{old_group}] bằng bản "
                              f"{new_tag} ({len(urls)} ảnh)          ")
                        core.append_log(f"{title} / {label}: thay [{old_group}] "
                                        f"bằng bản {new_tag}")
                    else:
                        n_full += 1
                        print(f"\r{prefix} [{tag}] — xong {ok}/{len(urls)} ảnh"
                              "                    ")
                else:
                    note = f" — THIẾU {len(retryable)}: trang {core.compact_ints(retryable)}"
                    if broken:
                        note += (f" — {len(broken)} trang hỏng tại nguồn: "
                                 f"{core.compact_ints(broken)}")
                    if upgrade:
                        note += " — GIỮ bản cũ, chạy lại để tải bù rồi mới thay"
                    print(f"\r{prefix} [{tag}] — xong {ok}/{len(urls)} ảnh{note}          ")
                    incomplete.append((label, retryable))
                    core.append_log(f"{title} / {label}: thiếu "
                                    f"{len(retryable)}/{len(urls)} trang "
                                    f"[{core.compact_ints(retryable)}] — chạy lại để tải bù")
                if broken:
                    source_broken.append((label, broken))

                img_ok += len(urls) - len(missing)
                img_missing += len(retryable)
                img_broken += len(broken)

                if args.cbz and (complete or not upgrade):
                    # sau upgrade phải nén lại (đè cbz cũ của bản scan)
                    core.make_cbz(folder, skip_existing=not (upgrade and complete))

                active += 1
                if active % 10 == 0:
                    rest = random.uniform(60, 90)
                    print(f"  (đang nghỉ {rest:.0f}s cho giống nhịp người đọc — KHÔNG "
                          f"phải treo, sẽ tự chạy tiếp...)", flush=True)
                    time.sleep(rest)
                else:
                    time.sleep(random.uniform(0.7, 1.3) * args.delay)

            # Vá cả bộ: chương trên ĐĨA còn trang xáo mà số chương KHÔNG còn trong danh
            # sách comix -> vòng trên không đi qua -> báo 'bản gốc không còn' cho khỏi sót
            # im lặng (lần quét kiểm lại vẫn sẽ thấy nó).
            if repair_mode and not (args.chapters or args.c_from is not None
                                    or args.c_to is not None):
                for d in sorted(out_root.iterdir(), key=lambda d: d.name):
                    num = _chapter_num_of(d.name)
                    if num is None or not d.is_dir() or d.name in visited:
                        continue
                    sd = read_sidecar(d)
                    if repair_offline_state(d, sd, (d / ".done").exists())[0] == "check":
                        rep["gone"].append([num, (sd or {}).get("group") or "?"])

            # Đóng dấu folder comix (Cách 1) — quét lại toàn bộ chương để số official/
            # tổng phản ánh đúng trạng thái sau lượt này.
            write_series_marker(out_root, slug)
            img_client.close()
    except (core.Blocked, core.TooMany429) as e:
        print(f"\n!!! Dừng phiên: {e}", file=sys.stderr)
        print("Ảnh đã tải không mất. Chờ một lúc (429: ~1 giờ; 403/503/Cloudflare: "
              "vài giờ) rồi chạy lại đúng lệnh này - tự tải tiếp chỗ dở.", file=sys.stderr)
        sys.exit(2)
    except (BrowserGone, FetchStalled) as e:
        # Thoát != 0 -> supervisor vào nhánh '❌ Lỗi tải' (đính dòng log cuối này). KHÁC
        # đường cũ: browser chết từng bị nuốt thành 'để sau' cả bộ rồi thoát 0 -> '✅ Tải
        # xong' giả, không ai hay. Nay có báo thật.
        print(f"\n!!! Dừng phiên: {e}", file=sys.stderr)
        print("Ảnh đã tải KHÔNG mất — chạy lại đúng lệnh này để tải tiếp chỗ dở "
              "(chương đã xong tự bỏ qua).", file=sys.stderr)
        sys.exit(2)
    except SiteChanged as e:
        # Thử lại vô ích -> thoát 1; dòng CUỐI (supervisor cắt 200 ký tự) = tin ❌ của bot.
        # KHÔNG chứa dấu hiệu lỗi mạng kẻo supervisor giữ job thử lại âm thầm (sự cố 27/10).
        print(f"\n!!! comix.to đổi cấu trúc, tool chưa đọc được: {e} — cần sửa code, "
              "/tai lại không giúp.", file=sys.stderr)
        sys.exit(1)

    # ---- Tổng kết chế độ SỬA TRÁO Ô ----
    if repair_mode:
        def cc(nums):
            return core.compact_chapters(nums, max_groups=60)

        def some(pairs, fmt):
            txt = "; ".join(fmt(a, b) for a, b in pairs[:15])
            return txt + (f"; … (+{len(pairs) - 15})" if len(pairs) > 15 else "")

        # Dòng máy-đọc cho bot gộp đợt `/repair all`. In TRƯỚC khối tổng kết: bot cắt tin
        # Telegram từ '===== SỬA TRÁO Ô' nên dòng này không lọt vào tin.
        print("REPAIR_RESULT_JSON:" + json.dumps(
            {"title": title, "folder": out_root.name, "pages": img_repaired, **rep},
            ensure_ascii=False))
        print(f"\n===== SỬA TRÁO Ô: {title} — quét {total} chương =====")
        print(f"   (mốc: trang xáo ghi trước {UNSCRAMBLE_SINCE_TXT} = chưa giải-xáo)")
        print(f"   Đã sửa: {len(rep['fixed'])} chương ({img_repaired} trang)"
              + (f" — ch. {cc(rep['fixed'])}" if rep["fixed"] else ""))
        if rep["verified"]:
            print(f"   Soi comix, không cần sửa: {len(rep['verified'])} chương")
        retry = rep["partial"] + rep["fetchfail"]
        if retry:
            print(f"   Còn sót (chạy lại /repair để bù): {len(retry)} — ch. {cc(retry)}")
        if rep["edited"]:
            print(f"   Bỏ qua — lệch số trang (đã sửa tay?): {len(rep['edited'])} — "
                  + some(rep["edited"], lambda n, note: f"ch. {core.fmt_num(n)} ({note})"))
        if rep["gone"]:
            print(f"   Bỏ qua — bản gốc không còn trên comix: {len(rep['gone'])} — "
                  + some(rep["gone"], lambda n, g: f"ch. {core.fmt_num(n)} [{g}]"))
        if rep["partialdl"]:
            print(f"   Bỏ qua — chương đang tải dở (/tai để tải nốt): "
                  f"{len(rep['partialdl'])} — ch. {cc(rep['partialdl'])}")
        if not (rep["fixed"] or retry or rep["edited"] or rep["gone"]):
            print("   ✓ Không chương nào còn trang tráo ô.")
        print("\nHoàn tất.")
        return

    # ---- Tổng kết cả bộ (format khớp engine chung) ----
    bits = [f"Đủ ảnh: {n_full}"]
    if n_upgraded:
        bits.append(f"Đã thay bằng Official: {n_upgraded}")
    if n_repinned:
        bits.append(f"Đã thay bằng bản ghim [{pin_name}]: {n_repinned}")
    if nopin:
        bits.append(f"Không có bản nhóm ghim: {len(nopin)}")
    if n_skipped:
        bits.append(f"Đã xong trước: {n_skipped}")
    if incomplete:
        bits.append(f"Thiếu trang: {len(incomplete)} (tải lại là bù được)")
    if source_broken:
        bits.append(f"Hỏng tại nguồn: {len(source_broken)}")
    if unfetched:
        bits.append(f"Chưa lấy được: {len(unfetched)} (chạy lại là bù được)")
    if n_locked:
        bits.append(f"Khóa/không ảnh: {n_locked}")
    print(f"\n===== TỔNG KẾT: {title} — {total} chương =====")
    print("   " + "   |   ".join(bits))
    img_bits = [f"OK {img_ok}"]
    if img_missing:
        img_bits.append(f"thiếu {img_missing}")
    if img_broken:
        img_bits.append(f"hỏng nguồn {img_broken}")
    tail = f"  (chưa gồm {n_skipped} chương đã xong trước)" if n_skipped else ""
    print("   Ảnh: " + ", ".join(img_bits) + tail)
    if incomplete:
        print(f"\n! {len(incomplete)} chương còn thiếu trang:")
        for label, miss in incomplete:
            print(f"   - {label}: thiếu {core.compact_ints(miss)}")
        print("-> Chạy lại đúng lệnh vừa rồi để tự tải bù.")
    if unfetched:
        print(f"\n! {len(unfetched)} chương CHƯA lấy được ảnh lần này "
              "(mạng/quảng cáo chèn — KHÔNG phải khóa):")
        print("   " + ", ".join(unfetched))
        print("-> Chạy lại đúng lệnh vừa rồi để tự tải bù các chương này.")
    if nopin:
        print(f"\n! {len(nopin)} chương site KHÔNG có bản nhóm ghim (giữ nguyên trên đĩa):")
        print("   " + ", ".join(nopin))
        print("-> Muốn tải nhóm khác cho các chương này: /tai <link> <chương> <Nhóm khác>; "
              "về luật mặc định: ... auto")
    print("\nHoàn tất.")
