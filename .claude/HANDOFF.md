# Handoff — cập nhật lần cuối: 2026-08-23 (reader: search giữ trạng thái khi back + số chương tự cập nhật)

> Kiến trúc ổn định (reader, provider, comix, supervisor, mạng…) nằm ở `.claude/ARCHITECTURE.md`.
> File này chỉ ghi TRẠNG THÁI hiện tại + việc đang dở.

## Đang làm / dở dang
- **[23/08] Reader — 2 bug: (1) search kẹt khi back, (2) số chương cập nhật chậm — ĐÃ code + test dev, CHƯA nghiệm thu LIVE** (`reader_server.py`).
  Làm trọn B1–B6 sau khi rà soát tổng thể freshness (kết luận: chỉ 2 gốc thật + 1 điểm phụ; ảnh/static/API đã chuẩn).
  **Bug 1 — search giữ trạng thái khi back (B1+B2):** ô search trống nhưng lưới vẫn lọc sau khi back — iOS Safari
  xoá `value` ô search qua bfcache nhưng GIỮ `display:none` của card, mà bộ lọc chỉ chạy ở sự kiện `input` →
  lệch pha, không bấm được truyện khác. Fix trong `HOME_JS`: tách bộ lọc thành hàm idempotent `applyHomeFilter()`;
  lưu keyword vào `sessionStorage['homeq']` **bền theo phiên tab** (bỏ `removeItem` cũ); lúc load + `pageshow`
  (persisted) → `restoreHomeq()` tái lập value rồi `applyHomeFilter()`. Chuẩn UX quốc tế = "list state restoration
  on back" (giữ keyword+lọc+scroll như Google/Amazon). `homey` vẫn one-shot cho admin `reloadKeepSearch`.
  **Bug 2 — số chương tự cập nhật (B3+B4+B5):** 3 tầng cache không tầng nào bị bust khi thêm/xoá chương (folder đổi
  ngoài tiến trình reader): `_lib_cache` TTL 60s, SW PAGE_CACHE SWR, bfcache. List chương cần 2-3 lần vào lại; home
  (back=bfcache) KHÔNG bao giờ đổi. Fix: **B3** `_library_signature()` — chữ ký RẺ 2 tầng thư mục (mtime folder
  truyện + folder con arc/chương, KHÔNG lặn xuống ảnh) đưa vào `_lib_cache=(ts,series,sig)`; `get_library()` chữ ký
  đổi ⇒ bust + quét nền NGAY (không đợi 60s). **B4** `GET /api/library-meta` → `{version, series:{sid:{total,status,
  label,cover}}}` (`no-store`; version = sha1 payload). **B5** HOME_JS + SERIES_JS: `syncCounts()` fetch meta trên
  `pageshow` (load+bfcache) và `visibilitychange`, vá TẠI CHỖ `.chapn`/`.st`/bìa (mẫu giống `syncBM`), so `version`
  để khỏi đụng DOM thừa. Server render bọc số chương trong `<span class="chapn">` ở `home_card_html`/`smeta`/`chcount`.
  **B6** manifest: `no-store`→`no-cache` (bỏ mâu thuẫn "no-store nhưng SW cache-first"). **Test dev**: compile OK;
  `/api/library-meta` trả đúng payload; `.chapn` có ở home+series; **kiểm chứng B3**: tạo chương giả → sig đổi,
  total 2→3 trong ~1.2s (không chờ 60s), dọn xong về 2. **CHƯA**: xem live trên trình duyệt + qua tunnel (back giữ
  search; thêm/xoá chương → home & list tự cập nhật khi quay lại). **Deploy = `/update` qua bot** (chỉ `reader_server.py`).
- **[22/08] Reader — méo ảnh sau khi upgrade chương, ĐÃ code + compile OK, CHƯA nghiệm thu LIVE** (`reader_server.py`).
  *Triệu chứng*: file ảnh trên đĩa ĐÚNG (mở xem bình thường) nhưng reader hiển thị **méo** — chỉ ch0-2 của bộ
  vừa upgrade từ comix (vd Solo Leveling: Asura 720×4000 → Official TappyToon 720×1334). *Nguyên nhân*: SW cache
  `/img` cache-first khoá theo URL, mà `img_url()` KHÔNG versioned → sau khi thay bản khác kích thước, SW trả
  bytes CŨ trong khi HTML render `aspect-ratio` MỚI → kéo méo (chỉ dính chương đã đọc/đã cache trước đó). Khâu
  tải comix HOÀN TOÀN đúng (đã tái hiện: TappyToon tải 34/34 trang, crisp). *Fix*: `img_url()` gắn `?v={st_mtime_ns}`
  (route `/img` bỏ qua query nên vô hại) → file đổi ⇒ URL đổi ⇒ SW cache-miss ⇒ tải tươi. Tự khỏi, không cần
  xoá cache tay; hiệu lực sau ~1 lần mở lại (HTML qua SWR). Chi tiết: ARCHITECTURE mục Service Worker ⑧. **CHƯA**:
  xem live (mở chương đang méo, xác nhận hết méo sau reload). **Deploy = `/update` qua bot** (chỉ `reader_server.py`).
- **[21/08] Reader — tinh chỉnh 2 điểm UX, ĐÃ code + syntax OK, CHƯA nghiệm thu LIVE** (`reader_server.py`).
  **(A) Delay 2-3s khi bấm chương TỪ DANH SÁCH** (Next đã nhanh nhờ prefetch `D.next/D.prev`, nhưng
  link `a.ch` ở trang truyện là hard-nav render nguội → quét PIL từng ảnh). Fix: thêm block prefetch vào
  `SERIES_JS` — `pointerdown` + `mouseover` (hover PC) trên `a.ch`/`.cbtn` → `pf([href])` postMessage
  `{type:'prefetch'}` cho SW (tái dùng `pfQ`/handler + navigation SWR có sẵn); và `requestIdleCallback`
  prefetch các nút `.chapbtns .cbtn` (First/Latest/reading) lúc rảnh. KHÔNG đón đầu cả list (hàng trăm
  chương) — chỉ theo ý định + nút chính. Warm cả HTML (PAGE_CACHE) lẫn `_dim_cache` server.
  **(B) Pill "Tap to show controls" hiện liên tục gây khó chịu** → đổi thành **gợi ý MỘT LẦN**: thêm
  `cueGone` + `hideCue()` trong READER_JS; tự ẩn sau `setTimeout 3000`, ẩn ngay khi `scroll`, ẩn khi
  `setBars()` (chạm). Đã ẩn thì KHÔNG hiện lại (bỏ dòng `cue.classList.toggle('off',!h)` cũ khiến pill
  quay lại mỗi lần bars ẩn). CSS `#tapcue.off` thêm `animation:none` để keyframe không ghi đè `opacity:0`.
  **CHƯA**: xem live trên trình duyệt + qua tunnel. **Deploy = `/update` qua bot** (chỉ `reader_server.py`).
  Đây là bản kế thừa/hoàn thiện mục "[21/08] điểm 1+3" bên dưới (điểm 3 pill nay là hint-một-lần; điểm 1
  prefetch nay phủ thêm cả bấm-từ-danh-sách).
- **[21/08] Reader (điểm 1+3) + comix (điểm 4) — ĐÃ code + validate, CHƯA nghiệm thu LIVE.**
  3 việc user chốt sau khi "chạy tool trong repo" để đối chiếu thật (dump DOM Asura + fetch danh sách
  bản comix qua ComixSession). **(1) Điểm 3 — thanh công cụ KHÔNG tự bật khi vào chương** (`reader_server.py`):
  `#topbar`/`#botbar` render sẵn class `hide`, `hid=true`; thêm pill `#tapcue` "Tap to show controls"
  fixed đáy giữa, `pointer-events:none`, `animation: tappulse 2s cubic-bezier(.4,0,.6,1)` (`@keyframes
  tappulse{50%{opacity:.5}}`) — **copy đúng spec Asura đã dump** (bg `rgba(0,0,0,.8)`, chữ trắng 72%,
  `rounded-full`, animate-pulse). `setBars(h)` toggle `.off` cho pill (mờ khi bars hiện). Chạm vùng đọc/
  chạm pill → bật bars; cuộn/chạm-lại → ẩn + pill trở lại. **(2) Điểm 1 — prefetch chương kế/trước** (trị
  khựng 1-2s bấm Next/chọn chương): READER_JS lúc `requestIdleCallback` postMessage `{type:'prefetch',
  urls:[D.next,D.prev]}` cho SW (tái dùng `pfQ`/handler có sẵn) → Next/Prev lấy HTML từ cache; render
  trước warm luôn `_dim_cache` server (hết mở PIL từng ảnh khi chương nguội). Chỉ nạp HTML, không kéo ảnh.
  **(3) Điểm 4 — ưu tiên nhóm official** (`comix_site.py`): thêm dict `OFFICIAL_GROUP_RANK` + `_official_rank`,
  `candidates_for` sort official theo `(hạng nhóm, -id)` thay vì thuần id. **Validate**: cú pháp OK cả 2
  file; reader.js cân bằng ngoặc + wiring đủ (SW đã có handler `prefetch`); comix test OFFLINE bằng đúng
  data Solo Leveling đã bắt → ch0 & ch200 nay chọn **TappyToon** (trước là Webcomic). **CHƯA**: xem live
  trên trình duyệt (pill + bars ẩn), chưa nghiệm thu prefetch qua tunnel. Deploy điểm 1+3 = `/update`
  (chỉ `reader_server.py`); điểm 4 = push + `cap-nhat.bat` (đụng `comix_site.py`, cần playwright).
- **[21/08] Reader: hết màn-trắng khi mở NGUỘI + hết bìa nháy đen khi login/logout — ĐÃ code + test
  dev (đo + HTTP live localhost), CHƯA nghiệm thu LIVE qua tunnel.** Nối tiếp [19/08] (SWR đã trị màn
  trắng do scandir; còn 2 triệu chứng client/mạng). Chẩn đoán mới (user đo trên link cloudflared SERVER):
  login-vs-guest KHÔNG chênh (đã đo `html_home` guest/login/nhiều-bm = 0.46–0.58ms, server VÔ CAN);
  triệu chứng thật: (1) login/logout → bìa nháy đen ~1s (DevTools: `/cover/*` trả **200** = tải lại
  thật, vì route `/cover` THIẾU ETag → reload không 304 được); (2) mở nguội (lần đầu / sau >1' idle)
  trắng 2-3s, mở lại ngay <1s (TTFB document `/` cold = 1-2s = cost kết nối nguội + document `no-store`
  nhúng inline toàn bộ CSS/JS nên không cache được gì; "1 phút" = trình duyệt hủy tab nền + đóng
  keep-alive). **Fix 4 phần (chỉ `reader_server.py`):** ① **ETag cho `/cover`** (`"{cover_ver}-{len}"`,
  hỗ trợ If-None-Match→304); ② **tách CSS + JS ra file tĩnh versioned** `/static/<name>?v=<sha1[:10]>`
  (registry `STATIC_ASSETS`, `Cache-Control: immutable`, ETag) — home doc **35.9KB→11.5KB** (−68%);
  page/home/series/reader giờ nạp qua `static_tag()` (script data ĐỘNG vẫn inline trước); ③ **Service
  Worker** `/sw.js` (no-cache + `Service-Worker-Allowed:/`): precache shell, **cache-first** cho
  `/cover` `/img` `/static` + icon (bìa lấy cache → hết nháy đen), **stale-while-revalidate** cho
  điều hướng HTML (first paint từ cache tức thì kể cả kết nối nguội → hết màn trắng); ④ **login/logout
  `purgeAndReload()`**: postMessage SW xoá `PAGE_CACHE` (ack qua MessageChannel, fallback 300ms) rồi
  reload → trang tải lại đúng trạng thái đăng nhập (SW khoá theo URL không phân biệt cookie), bìa/CSS/JS
  vẫn từ cache nên reload nhanh + không nháy. **Test dev**: compile OK; HTTP live localhost — `/static/*`
  200+immutable+ETag & 304; `/sw.js` đúng header; `/cover` 200→304 khi revalidate; 3 trang render đúng,
  không còn `<style>`/`<script>{...}` inline sót; SW placeholders (`__VER__`/`__PRECACHE__`) đã thay.
  **Deploy = `/update` qua bot** (chỉ đụng `reader_server.py`, KHÔNG đụng supervisor). Nghiệm thu LIVE:
  xem "Việc tiếp theo". **[BỔ SUNG sau deploy — 2 sự cố mới do/sau SW, ĐÃ fix + test dev]:**
  **(5) Logo header tải 5-10s, hiện dần** — gốc: `brand.png` **469KB** mà chỉ hiện ở `height:34px`, LẠI
  không nằm trong SW cache/precache (SW chỉ có `/logo` favicon, còn header dùng `<img src="/brand">`) →
  luôn đi mạng, xếp hàng sau bìa qua HTTP/1.1 6-conn. Fix: `_build_brand_asset()` thu nhỏ brand.png (PIL,
  height 120 giữ hình) → **WebP 18KB (×25)**, đưa vào `STATIC_ASSETS['brand.webp']` (versioned+immutable,
  **tự được SW precache**), header trỏ `brand_src()` (fallback `/brand` nếu thiếu PIL); thêm `/brand` vào
  `isStatic` cho chắc. **(6) Bấm series LẦN ĐẦU chậm 2-3s** (lần sau nhanh) — bản chất SWR: URL chưa vào
  lần nào = cache-miss → tải HTML qua mạng (server render chỉ 1-9ms, VÔ CAN; nhưng bộ nhiều chương doc to,
  vd Pokemon 732ch = 218KB). Fix: **prefetch trang series vào `PAGE_CACHE`** — SW thêm hàng đợi
  `pfQ`/`pumpPrefetch` (giới hạn `PF_MAX=2` luồng, bỏ qua cái đã cache, purge khi login/logout); HOME_JS
  prefetch khi (a) `pointerdown` trên `.cardlink/.fcard` [ý định] + (b) card lọt viewport lúc rảnh
  (`IntersectionObserver` rootMargin 300px + `requestIdleCallback`). **Test dev (5)+(6)**: brand.webp
  200 image/webp 18878B immutable+ETag; `brand_src`→`/static/brand.webp`; SW_VERSION đổi (precache có
  brand.webp → deploy tự cập nhật SW + dọn cache cũ); home header dùng brand.webp; compile OK.
- **[21/08] convert_webp: chốt-tiết-kiệm + chế độ nén TẠI CHỖ (`--in-place`) — ĐÃ code + test dev,
  CHƯA nghiệm thu LIVE.** Nối tiếp mục [20/08]. Vấn đề: (a) `convert_webp.py --webp-too` KHÔNG có chốt
  nên nén webp đã-q85 lần nữa = suy hao vô ích (~99% cỡ gốc); (b) user cần nén **nhiều bộ comix cũ** —
  quy trình "convert → xóa gốc → đổi tên `_webp`→gốc" dễ sai (quên đổi tên → downloader coi như chưa
  tải, tải LẠI cả bộ, vì `out_root` tính theo tên truyện KHÔNG có `_webp`). Fix (5 phần): **B1** chốt
  `--min-save` (mặc định 10%) — chỉ thay bản webp khi tiết kiệm ≥10%, ảnh đã tối ưu (~1% nhỏ hơn) thì
  GIỮ NGUYÊN → chống nén-chồng, bấm nhầm/chạy lại đều an toàn (mỗi ảnh nén-có-ích 1 lần); **B2**
  `--in-place` re-nén webp NGAY trong folder gốc (không tạo `_webp`, chỉ đụng `.webp`, temp+verify+os.replace,
  giữ nguyên `.done`/`.source.json` → downloader tải tiếp chương mới bình thường, reader giữ bookmark);
  **B3** `convert_webp.bat` thêm nhánh "Nen TAI CHO?" (viết bằng goto tránh bẫy delayed-expansion trong
  khối `()`); **B4** README mục 3 + bảng đầu; **B5** đồng bộ ngưỡng: `_recompress_webp` (comix_site) đổi
  từ "nhỏ hơn là thay" sang "tiết kiệm ≥ `RECOMPRESS_MIN_SAVE`=10%". Tách helper chung `reencode_webp_bytes`
  (nén RAM + verify) cho cả tree lẫn in-place. **Test dev**: in-place trên folder trộn (1 raw q92 + 1 đã
  q85 + marker) → raw 469KB→276KB, q85 giữ nguyên, marker không đụng, không sót `.tmp`; **chạy lần 2 =
  idempotent** (giữ cả 2, không suy hao); tree `--webp-too` cùng data → nén raw, giữ q85, cây gốc nguyên;
  syntax + import OK. **Deploy = push + `/update`** (chỉ đụng `convert_webp.py`/`comix_site.py`; convert_webp
  chạy TAY nên chỉ cần code có trên đĩa server). Nghiệm thu: xem "Việc tiếp theo".
- **[20/08] Comix tự re-nén ảnh tải về q85 — ĐÃ code + test dev, CHƯA nghiệm thu LIVE trên server.**
  Đối chứng thực đo (Overgeared, cùng bản scan "Asura Scans" trên cả 2 site): comix trả WebP **giống
  hệt Asura từng pixel** (ch335: cả hai rộng 900px, tổng 169.5 MP, strip ghép trùng khít) — KHÔNG hề
  phân giải cao hơn; chỉ **nén nhẹ tay** nên nặng gấp ~1.56× (24.5MB vs 15.7MB, 0.151 vs 0.097 B/px).
  Re-nén về **q85** → ~12MB (còn nhẹ hơn cả Asura) mà crop zoom 100% **không phân biệt được**. Fix
  (3 chỗ): ① `comix_site.py` thêm `RECOMPRESS_Q=85` + `_recompress_webp(path,q)` (mở PIL, save WEBP
  q method=4, chỉ THAY khi bản nén nhỏ hơn + `verify()` mở lại được; webp-động/gif/avif bỏ qua; mọi
  lỗi giữ nguyên byte gốc), hook ngay sau `_fix_ext` trong vòng tải — CHỈ đụng ảnh MỚI tải (trong
  `jobs`) nên chương đã có sẵn không bị nén lại; ② `comic_downloader.py` thêm cờ `--comix-q` (mặc định
  85, `0`=tắt), comix đọc qua `getattr(args,"comix_q",RECOMPRESS_Q)`; ③ `convert_webp.py` thêm cờ
  `--webp-too` (re-nén WebP thay vì copy — cho ảnh comix tải TRƯỚC khi có tính năng này) + `convert_webp.bat`
  thêm dòng hỏi "Re-nen ca WebP?". **Test dev**: `_recompress_webp` trên tile thật 469KB→276KB (58%),
  ảnh mở lại OK đúng 900×1778; `--help` có `--comix-q`; `convert_webp.py --webp-too` trên 10 tile
  2.47MB→1.31MB (53%); syntax cả 3 file OK. **Deploy = push (`day-len.bat`) rồi `/update` là ĐỦ**:
  chỉ đụng `comix_site.py`/`comic_downloader.py`/`convert_webp.py`, KHÔNG đụng `supervisor.py`; `/update`
  `git reset --hard origin/main` kéo code về đĩa, và bot tải bằng cách **spawn subprocess
  `comic_downloader.py`** (đọc code mới từ đĩa mỗi lần) nên lượt `/tai` kế đã dùng bản mới (không cần
  `cap-nhat.bat` / restart supervisor). Nghiệm thu: xem "Việc tiếp theo".
- **[19/08] Reader màn-trắng khi mở web (TTFB cao) — ĐÃ code + test dev, CHƯA nghiệm thu LIVE trên
  server.** Chẩn đoán bằng DevTools (2 lần đo, cùng quick-tunnel `trycloudflare.com`): laptop 9 bộ
  TTFB **124ms**, server ~40 bộ TTFB **4.27s**; ba dòng DNS+Connect+SSL GẦN BẰNG NHAU ở cả hai (~160-190ms)
  → **mạng/tunnel VÔ CAN**, toàn bộ màn trắng là "Waiting for server response" = server-side compute.
  Gốc: `get_library()` khi cache 60s hết hạn **quét đồng bộ** toàn bộ (`build_series`→`dir_has_image`
  scandir mỗi thư mục chương; máy này 9 bộ = 1.483 thư mục con / 29.435 file), chặn ngay trên đường trả
  response → "nhiều lúc" trắng = request rơi trúng sau mốc hết-hạn-60s (cache stampede). Server chậm ×34
  dù chỉ nhiều hơn ×4.4 số bộ do khuếch đại: đĩa server chậm hơn (nghi HDD) + OS filesystem cache nguội +
  tranh chấp I/O với downloader đang cày. **KẾT LUẬN QUAN TRỌNG: splash-in-HTML VÔ ÍCH** — suốt 4.27s
  trình duyệt không nhận được byte nào (HTML chỉ 14.4kB, Content Download 4.6ms). **Fix (2 phần, bổ trợ):**
  ① **SWR (stale-while-revalidate) cho `get_library`**: tách phần quét ra `_scan_library()`; cache hết
  hạn nhưng còn bản cũ → trả STALE ngay + quét lại ở daemon thread (`_refresh_library`, cờ `_lib_refreshing`
  chống spawn trùng); chỉ build lạnh (cache None lúc khởi động / vừa bust) mới quét đồng bộ, tuần tự hoá
  bằng `_lib_build_lock`. ② **cache nguồn bìa vào series lúc build**: `build_series` tính sẵn `cover_src`
  + `cover_mt` (tốn scandir/getsize 1 lần/bộ mỗi lượt scan) → `cover_ver` chỉ đọc `series["cover_mt"]`
  (bỏ `cover_source`+`os.stat` ×2/bộ mỗi lần render), `cover_jpeg` dùng `series["cover_src"]`. **Test dev**:
  cold build 8 bộ 0.35s; warm ~0s; **`html_home` render 0.6ms** (trước phải scandir mỗi bộ); SWR trả stale
  0.6ms + thread nền làm mới cache OK. **Deploy = `/update` qua bot** (chỉ đụng `reader_server.py`, KHÔNG
  đụng supervisor). Nghiệm thu LIVE: xem mục "Việc tiếp theo".
- **[18/08] Chống-treo 2 lớp ①+② cho comix (fix 17/08 treo LẠI ~5 tiếng) — ĐÃ code + test dev,
  CHƯA nghiệm thu LIVE trên server.** Sự cố 17/08: auto-check 3h sáng enqueue comix `eqr1e-overgeared`
  → downloader mở Chromium rồi **treo câm ~5 tiếng** (tab blank about:blank), kẹt cả hàng đợi tới khi
  user `/stop` tay. Fix 14/08 (`_kill_profile_chrome` + `_StartupWatchdog`) CHỈ bọc đúng
  `launch_persistent_context`, còn treo rơi vào các lệnh SAU launch (add_init_script/route/pages +
  `ComixImageClient.refresh_identity`) — ngoài watchdog, và `supervisor.proc.wait()` KHÔNG timeout →
  không lưới nào bắt. **② (`comix_site.py`)**: mở rộng `_StartupWatchdog` bọc CẢ setup + thêm PROBE
  `page.evaluate('()=>1')` (bắt đúng ca about:blank wedge trong ≤90s); bọc luôn `refresh_identity` đầu;
  watchdog nổ → kill Chromium + ân hạn 8s cho lệnh Playwright bật lỗi → ném `BrowserGone` → `_open_resilient`
  **tự dựng lại trong phiên** (Cách B, tối đa MAX_RELAUNCH); vẫn kẹt sau ân hạn → `os._exit(2)`.
  **① (`supervisor.py`, lưới bao chót)**: thay `proc.wait()` bằng `_wait_or_stall` — poll `os.path.getsize(tai-run.log)`
  mỗi 30s; log đứng im > `dl_stall_limit` (mặc định 1200s) → kill downloader + Chromium comix → giữ job
  thử lại (backoff 120s), quá `DL_STALL_RETRY_MAX=1` → bỏ (daily tự enqueue lại). Ngưỡng 1200s > cữ
  backoff 429 tệ nhất (900s) nên KHÔNG giết nhầm job đang nghỉ-lịch-sự. **Đã test dev 12/12** (phát hiện
  treo + kill; job in tiến độ đều KHÔNG bị giết; stop sạch; relaunch trong phiên; quá ngân sách → fatal).
  **Deploy = `cap-nhat.bat` + chạy lại `server-BAT-tudong.bat`** (đụng `supervisor.py`). Nghiệm thu: xem mục
  "Việc tiếp theo".
- **[16/08] `/tai` chọn chương (như `Tai truyen.bat`) — ĐÃ code + commit `c1545a3`, CHƯA
  nghiệm thu LIVE trên server.** Trước `/tai` chỉ tải CẢ truyện; giờ `/tai <link> [chương]`
  nhận dải chương (`1-20`, `5,7,20-25`) → truyền `--chapters` cho `comic_downloader.py`; bỏ
  trống = cả truyện (như cũ). Chỉ sửa `supervisor.py`: `handle_tai` tách link/spec + validate
  `[0-9.,\-]+`, chuẩn hoá "5, 7 20-25"→"5,7,20-25"; job mang field `chapters` (bền hoá qua
  restart, `_load_jobs` giữ lại); `_enqueue_jobs` dedup theo `(url, chapters)` nên cùng truyện
  khác dải KHÔNG bị coi trùng; worker thêm `--chapters` vào lệnh; `/trangthai` + tin "Bắt đầu
  tải" + `/help` + setMyCommands hiện dải chương. **Đã test parse (dev) OK** (6 ca kể cả có
  khoảng trắng, đa link). **Deploy = `cap-nhat.bat` + chạy lại `server-BAT-tudong.bat`** (đụng
  `supervisor.py`, `/update` KHÔNG nạp lại supervisor). Nghiệm thu: `/tai <link> 1-3` → chỉ tải
  3 chương đó; `/tai <link>` (không spec) vẫn tải cả bộ.
- **[14/08] Sửa comix TREO about:blank (bản đầu) — ĐÃ TREO LẠI 17/08 → thay bằng fix 18/08 ①+②
  ở trên.** Bản 14/08 (`_kill_profile_chrome` + `_StartupWatchdog` chỉ bọc `launch_persistent_context`)
  KHÔNG đủ: treo lần 17/08 rơi vào các lệnh SAU launch (ngoài watchdog) + supervisor `proc.wait()`
  không timeout. Chi tiết + fix mở rộng xem mục [18/08] đầu file. (Giữ dòng này để biết vì sao lần
  đầu chưa trọn.)
- **[14/08] Auto-check chương mới hằng ngày — ĐÃ code + push, CHƯA nghiệm thu LIVE trên server.**
  Watchlist `.reader-meta/watchlist.json` (1 nơi quản lý, gitignore) + script mới `check_updates.py`
  (subprocess, cô lập requests/providers khỏi supervisor stdlib): peek `list_chapters` (chỉ metadata,
  KHÔNG tải ảnh) so với ĐĨA (folder `Chapter N` có `.done` HOẶC chứa ảnh) → ra tập chương thiếu.
  Supervisor thêm luồng `watch_loop` (chạy 1 lần/ngày lúc `check_hour:check_min`, mặc định 03:00, bù
  nếu server tắt lúc đến hẹn) → gọi `check_updates.py` → báo tóm tắt Telegram + enqueue truyện có
  chương mới vào ĐÚNG hàng đợi `/tai`. Lệnh mới: `/watchlist /watch /unwatch /checknow`. comix =
  enqueue mỗi ngày (không peek rẻ được, loop comix tự lo new + "v"-tick upgrade). Site chưa hỗ trợ →
  `/watch` báo "chưa hỗ trợ", không nhận. **Đã test dev**: unsupported/comix/paused path OK; peek thật
  Asura Overgeared (334 ch, đĩa 20 → thiếu 315) OK; `done_numbers` đếm đúng thư viện CŨ thiếu `.done`
  (Solo Leveling 201, Worn And Torn 243). **Nghiệm thu LIVE**: sửa `supervisor.py` nên phải deploy
  bằng `cap-nhat.bat` + chạy lại `server-BAT-tudong.bat` (KHÔNG chỉ `/update`); rồi `/watch <link>`
  vài bộ → `/watchlist` → `/checknow` xem tóm tắt + hàng đợi chạy.
- **[12/08] Auto-start phương án A: server tự lên sau reboot KHÔNG cần gõ mật khẩu — ĐÃ code,
  CHƯA nghiệm thu LIVE.** Task `ToonyServer` (onlogon) đổi sang `python.exe` (có cửa sổ log) +
  đường dẫn tuyệt đối (suy từ `pythonw.exe` đã resolve); thêm `server-AUTOLOGIN.bat` (Sysinternals
  Autologon, mã hoá LSA). Nghiệm thu: `cap-nhat.bat` → **chạy lại `server-BAT-tudong.bat`** (đăng ký
  lại task, vì chỉ deploy file chưa đổi task đang trỏ `pythonw`) → `server-AUTOLOGIN.bat` (gõ pass) →
  reboot không đụng gì → hiện cửa sổ log + Telegram link mới + heartbeat 🟢. Luật A: *Switch user*
  giữ sống, *Sign out* giết supervisor.
- **[12/08] Comix chống 403/503 khi Cloudflare siết — ĐÃ code + push (commit `212c215`,
  working tree sạch), CHƯA nghiệm thu LIVE trên server.** Sự cố: tải cả ngày ngon rồi bỗng
  **403 `static.comix.to` + 503 `wowpic`**, trong khi Chrome trên server đọc vẫn bình thường
  → xác định "danh tính tách đôi" (metadata qua browser có vé, ảnh qua `requests` trần không
  vé). Fix Bậc 1+2: `ComixImageClient` mượn cf_clearance+UA sống + `curl_cffi` giả TLS Chrome;
  tách `Forbidden` (403, refresh-retry) khỏi breaker 503; `gate.recover()`. Chi tiết + "vì sao"
  ở ARCHITECTURE mục "danh tính tách đôi". **Đã test logic không-cần-browser OK** (breaker 503
  backoff/abort, lọc cookie theo host, dịch lỗi curl_cffi → RequestException). curl_cffi CHƯA
  cài trên máy dev → dev chạy fallback `requests`; server cài qua `cap-nhat.bat`.
- **[11/08] Supervisor chống-chịu mạng (B+C+D) + heartbeat + BỎ health_loop — ĐÃ code + push.**
  Diễn tiến: verify link bằng GET URL công khai hoá ra sai ~2/3 (mạng server không hairpin về
  tunnel của nó) → `health_loop` giết nhầm tunnel tốt mỗi ~3' (đổi link liên tục). **Chốt: bỏ hẳn
  `health_loop`; báo link khi reader NỘI BỘ `127.0.0.1` sẵn sàng** (`_reader_alive`). Tin cloudflared
  tự reconnect/thoát. **CHƯA nghiệm thu LIVE** (deploy `cap-nhat.bat`, xem log KHÔNG còn "Health-check
  fail"/"Tunnel coi như chết", chỉ 1 "LINK MỚI"). Việc user: **bật heartbeat** (dán `heartbeat_url`
  vào `notify-config.json`). Đổi lại: reader treo-mà-chưa-chết không tự phục hồi → restart tay.
- **[11/08] ACGNProvider (comic.acgn.cc, tiếng Trung) — ĐÃ code, CHƯA nghiệm thu tải LIVE.**
  Parse OK từ dev; ảnh `img.acgn.cc` lọc vùng (522 ngoài VN), server VN test `Invoke-WebRequest`
  200. Nghiệm thu = `/tai` link acgn trên server rồi soi `check_library.py`.
- **[10/08] Tool LÀM NÉT Real-ESRGAN — ĐÃ push. Tích hợp tự động vào `/tai` CHƯA làm.**

## Quyết định gần đây (mới nhất trước)
- **23/08: Freshness dữ liệu phái sinh (số chương/trạng thái/bìa) = event-invalidation ở nơi GHI + SWR reconcile UI
  + refresh trên `pageshow`/`visibilitychange`, key theo 1 freshness token** — chuẩn quốc tế cho dữ liệu "gần
  tức thời, không real-time". KHÔNG hạ TTL về 0 (giết perf, không trị bfcache), KHÔNG tắt bfcache (phá vuốt-back
  iOS), KHÔNG WebSocket (thừa). Chọn: chữ ký thư mục tự-bust `_lib_cache` + endpoint `/api/library-meta` + client
  vá tại chỗ khi hiển thị. Một cơ chế chung trị cả count/status/cover (thêm field sau không đẻ bug).
- **23/08: Search khi back — GIỮ keyword + list lọc + scroll (không xoá)** — chuẩn "list state restoration on back"
  (Google/Amazon/YouTube: back từ chi tiết về đúng kết quả đang duyệt). Trạng thái cũ (ô trống + list lọc) là bug
  lệch pha do iOS xoá value input qua bfcache, không phải lựa chọn thiết kế. Không tin trình duyệt giữ value → tự
  tái lập từ sessionStorage + chạy lại bộ lọc idempotent ở mọi đường vào.
- **21/08: comix — giữa nhiều bản official, chọn theo `OFFICIAL_GROUP_RANK` chứ KHÔNG thuần id mới nhất** —
  vì truyện license có nhiều official song song khác nền tảng/typeset (Solo Leveling ch0 có 7); bản re-up
  mới nhất (Webcomic) thường kém bản dịch tốt (TappyToon). User chốt: TappyToon cao nhất, Webcomic thấp nhất;
  dict dễ sửa ở đầu `comix_site.py`. Verify offline: ch0/ch200 nay chọn TappyToon.
- **21/08: Reader — bars KHÔNG tự bật khi vào chương, thay bằng pill "Tap to show controls" nhấp nháy (kiểu
  Asura)** — user muốn UX giống Asura; đã lái Chrome thật dump DOM Asura xác nhận spec (div fixed đáy,
  `pointer-events:none`, `animate-pulse 2s`, `@keyframes pulse{50%{opacity:.5}}`) rồi copy 1:1.
- **21/08: Reader — prefetch chương kế/trước (`D.next`/`D.prev`) vào `PAGE_CACHE` khi rảnh** — trị khựng
  1-2s khi bấm Next/chọn chương (hard-nav + render nguội quét PIL); render trước còn warm `_dim_cache` server.
- **21/08: Trị bookmark "cũ" khi điều hướng (2 gốc khác nhau) — bù cho việc bật bfcache** — sau khi bật
  bfcache lộ 2 lỗi: **②** back về home/series thấy chưa bookmark (bfcache đóng băng DOM, JS hydrate không
  chạy lại); **①** bookmark ở home rồi bấm vào truyện thấy chưa bookmark, vào lại mới đúng (SW prefetch/SWR
  trả HTML cũ + series render server, không hydrate client khi đăng nhập). Chọn **hướng A** (giữ
  server-render). Fix trong `reader_server.py`: **②** thêm `pageshow.persisted` ở HOME_JS/SERIES_JS →
  guest đọc lại localStorage, đăng nhập refetch `GET /api/state` (đã có sẵn), áp lại bằng hàm idempotent
  (không re-init → không double-bind). **①** khi toggle (chỉ đăng nhập) gọi `TOONY_PURGE_PAGE(url)` (ACCT_JS)
  → SW xoá đúng key khỏi `PAGE_CACHE`. Guest không cần purge (tự hydrate từ localStorage). CHỈ bookmark;
  tiến trình/đã-đọc để sau. Không phá bfcache. Chi tiết ở ARCHITECTURE.md.
- **21/08: Trị "vuốt back nháy 1 phát" iOS Safari = KHÔI PHỤC BFCACHE, không phải xử lý cử chỉ** — vuốt
  trái→phải để back trên iPhone (Safari/Web App qua cloudflared) nháy trắng, còn nút Back thì không, vì
  vuốt-back là animation tương tác phải vẽ trang đích NGAY: trang không vào được bfcache (do document trả
  `no-store`) nên bị dựng lại từ đầu, các frame trung gian lộ ra = nháy. Fix trong `reader_server.py`:
  `send_page()` đổi `no-store`→**`no-cache`** (không chặn bfcache mà vẫn revalidate mỗi load) + thêm
  `color-scheme:dark`/nền tối trên `html` (CSS + inline `<head>`) để canvas mặc định là tối, khử chớp
  trắng kể cả khi vẫn phải dựng lại. Đã kiểm: không có handler touch tùy biến, không `unload`/WebSocket
  chặn bfcache; `pagehide` an toàn. Chi tiết ở ARCHITECTURE.md. Kiểm chứng: `pageshow`→`persisted===true`.
- **21/08: Trị màn-trắng cold + bìa-nháy bằng SERVICE WORKER, không phải tối ưu server thêm** — đã
  chứng minh server render 0.5ms (vô can); nút thắt còn lại là client không có gì hiện ngay khi kết nối
  nguội + document `no-store` không cache được. SW (SWR shell + cache-first ảnh) cắt mạng khỏi đường
  tới-hạn của first paint. Đồng thời tách CSS/JS ra file versioned immutable (cache được + document co
  68%) và gắn ETag `/cover` (reload 304 thay vì tải lại). login/logout phải purge `PAGE_CACHE` của SW
  vì SW khoá theo URL không phân biệt cookie → nếu không sẽ hiện nhầm trạng thái đăng nhập cũ.
- **21/08: Chống nén-chồng bằng CHỐT-TIẾT-KIỆM (stateless), KHÔNG cố đọc q gốc** — không thể đọc
  được quality của một webp có sẵn, nên thay vì "phát hiện đã q85 rồi skip", dùng heuristic "chỉ thay
  khi bản nén tiết kiệm ≥10%". Nó tự phân loại: q92→q85 (~60%) thì nén, q85→q85 (~99%) thì giữ nguyên;
  và tự biến việc nén thành gần-idempotent (sau lần nén-có-ích đầu, các lần sau đều ~0% tiết kiệm → bị
  từ chối) → bấm nhầm/chạy lại vô hại. Ngưỡng 10% đặt ở 2 nơi (`convert_webp.MIN_SAVE_DEFAULT`,
  `comix_site.RECOMPRESS_MIN_SAVE`) cho nhất quán. **Và chọn `--in-place` làm cách chính cho comix cũ**
  (thay quy trình xóa+đổi-tên dễ sai): downloader tính `out_root` theo TÊN TRUYỆN không có `_webp`, nên
  giữ đuôi `_webp` = mất dấu = tải lại cả bộ; nén tại chỗ giữ nguyên tên/marker nên tải tiếp trơn.
- **20/08: Comix nặng hơn Asura là do NÉN NHẸ TAY, KHÔNG phải phân giải cao hơn → tự re-nén q85 lúc
  tải** — đo thực (cùng bản "Asura Scans" ch335): 2 site giống hệt pixel (900px, strip trùng khít),
  comix chỉ để B/px cao hơn (0.151 vs 0.097). Nên hạ về q85 ngay khi tải là "nhẹ ~nửa, chất lượng
  nhìn thấy y nguyên" (đối chứng crop 100%). Chọn q85 (không phải thấp hơn): dư biên độ, kết quả vẫn
  nhẹ hơn cả Asura; hạ nữa (q82) nhẹ thêm chút nhưng để mặc định an toàn. Re-nén **inline trong vòng
  tải** (không phải hậu xử lý riêng) để chương tải xong là đã tối ưu, và CHỈ đụng ảnh mới tải (idempotent
  theo `.done`/file-đã-có). Là transcode lossy→lossy nên **chạy đúng 1 lần**; ảnh comix cũ dùng
  `convert_webp.py --webp-too` (cũng chỉ nên 1 lần). Không đụng engine chung `comics_core` (giữ an toàn
  cho 6 site kia) — logic nằm gọn trong `comix_site.py`.
- **19/08: Trị màn-trắng reader = giảm TTFB phía server, KHÔNG dùng splash** — đo DevTools chứng minh
  màn trắng 100% là "Waiting for server response" (mạng vô can: DNS+Connect+SSL bằng nhau giữa máy nhanh
  124ms và máy chậm 4.27s). App là SSR nên splash nhét trong HTML vô nghĩa (trình duyệt không có gì để
  vẽ suốt lúc chờ). Chốt fix ở gốc: (1) SWR — không request nào phải chờ scandir, cache hết hạn trả bản
  cũ + làm mới nền; (2) cache `cover_src`/`cover_mt` vào series để render home ~0 I/O đĩa. Không phụ thuộc
  đĩa server nhanh/chậm. Muốn "phản hồi khi bấm chuyển trang" (khác vấn đề này) thì dùng thanh progress ở
  đỉnh — để dành, chưa làm. Splash cấp-OS cho PWA (icon home-screen) cũng để dành, chỉ ích khi mở từ icon.
- **18/08: Chống-treo comix = 2 lớp bổ trợ, KHÔNG đụng engine chung `comics_core`** — ② watchdog nội
  bộ (bọc cả setup + probe evaluate, Cách B tự relaunch trong phiên) bắt ca mở-Chromium-wedge ~90s;
  ① supervisor stall-watchdog (poll `getsize(tai-run.log)` mỗi 30s, ngưỡng 1200s) là lưới bao chót cho
  MỌI kiểu treo khác. Ngưỡng ① phải >900s (cữ backoff 429 tệ nhất của `comics_core` là 1 lần sleep tới
  900s) để không giết nhầm job nghỉ-lịch-sự hợp lệ; poll bằng `getsize` (stat O(1), không đọc nội dung)
  + chỉ chạy khi ĐANG có job (rảnh worker ngủ) → không tốn tài nguyên. User chốt: không thêm heartbeat
  vào `comics_core` (giữ engine chung an toàn), chấp nhận hồi phục ① chậm hơn (≤20').
- **16/08: `/tai` chọn chương — 1 spec/lệnh, áp cho MỌI link trong lệnh đó; dedup theo
  `(url, chapters)`** — spec là phần token không-http (gộp lại, bỏ khoảng trắng, gộp phẩy thừa
  nên "5, 7 20-25"→"5,7,20-25"). Dedup gồm cả `chapters` để `/tai url 1-20` rồi `/tai url 30-40`
  (hoặc cả bộ) là 2 job khác nhau, không bị nuốt; downloader tự bỏ qua `.done`. Auto-check vẫn
  enqueue `chapters=None` (tải cả bộ) — `_enqueue_jobs` chịu cả tuple 2 lẫn 3 phần tử.
- **14/08: Báo cáo check chi tiết X/Y + chương thiếu (A: site thường; B: comix báo từ lượt tải)** —
  trước chỉ in tên truyện, giờ mỗi truyện in `X/Y chương (thiếu K: ch. …)`. Site thường: `check_updates.py`
  xuất thêm `listed_count`+`missing_str` (dùng `core.compact_chapters` gộp dải `21-334`, cắt bớt khi
  quá nhiều nhóm); `supervisor._summary_text` in per-truyện theo nhóm 🆕/⤵️/✅/📘/⚠️/⛔. comix KHÔNG
  đếm nhanh được (phải mở Chromium) → `comix_site._report_comix_plan()` nhắn Telegram X/Y + danh sách
  "cần nâng cấp → Official" + "cần tải" NGAY sau khi Chromium quét xong, TRƯỚC khi tải ảnh (chỉ đọc đĩa,
  không thêm request; báo trễ ~30-60s chứ không tức thì — bản chất site). "Official" = bản tick "v"
  (isOfficial). **Deploy: cần `cap-nhat.bat` + chạy lại `server-BAT-tudong.bat`** (đụng `supervisor.py`).
- **14/08: Comix tự dọn profile TRƯỚC mỗi lần chạy + watchdog khâu launch** — profile Chromium bền
  (`comix-profile`) mà còn con mồ côi ôm nó thì con mới "chuyển URL cho con cũ rồi tự thoát" →
  Playwright treo about:blank. Không chỉ dựa bộ dọn-lúc-khởi-động của supervisor (không per-job);
  `comix_site.run()` tự `_kill_profile_chrome()` (kill chrome match 'comix-profile' + xoá `Singleton*`)
  ở đầu mỗi lần. Watchdog 90s bọc riêng khâu launch (không bọc goto/chờ-Cloudflare vì đó chờ NGƯỜI
  tick hợp lệ) → treo thì kill + `os._exit(2)` (fail fast) thay vì đứng im. An toàn vì comix 1 worker.
- **14/08: Dò chương mới = so `list_chapters` với ĐĨA, KHÔNG lưu `last_max` làm chuẩn** — vì chương
  khoá premium được site LIỆT KÊ nhưng chưa tải được: nếu chuẩn là `last_max` thì max không tăng →
  kẹt, không bao giờ thử lại. So với đĩa thì chương chưa có ảnh luôn "thiếu" → tự thử lại tới khi mở
  khoá. `last_max` CHỈ để highlight "🆕 chương mới" trong noti (số cao nhất tăng so lần trước).
- **14/08: "Đã có trên đĩa" = folder chứa ẢNH, không chỉ `.done`** — thư viện CŨ (Solo Leveling,
  Worn And Torn…) đủ ảnh nhưng THIẾU marker `.done` (tải trước khi có cơ chế đó); nếu chỉ xét `.done`
  sẽ báo nhầm "thiếu cả bộ" rồi enqueue tải lại vô ích. Checker chỉ lo DÒ CHƯƠNG MỚI, việc soát
  đủ-trang là của downloader khi thực sự tải.
- **14/08: comix enqueue mỗi ngày (không peek)** — comix không có peek rẻ (phải mở Chromium) và số
  chương KHÔNG phản ánh việc bản "v" tick thay scan; chỉ loop comix mới quyết đúng new/upgrade/skip →
  cứ đổ vào hàng đợi hằng ngày, nó tự bỏ qua `.done` + tự nâng cấp. Đánh đổi: mở Chromium ~1-2'/ngày.
- **14/08: `check_updates.py` là SUBPROCESS, không import vào supervisor** — giữ supervisor stdlib-only
  (bền); mọi lỗi provider/mạng cô lập trong tiến trình con. Kết quả ghi ra `watch-check-result.json`
  (KHÔNG parse stdout vì `_request` in 429/503 ra stdout). Supervisor là NGƯỜI GHI DUY NHẤT watchlist.
- **13/08: Click card Bookmarked → trang LIST CHƯƠNG** (trước: nhảy thẳng chương đang đọc/mới nhất).
  Đổi `href` trong `follow_card_html` + `FOLLOWDATA.url` sang `u("series",sid)`; nhãn `.fcm` giữ
  nguyên (label chương đang đọc dở từ `continue_info`).
- **13/08: Hàng "Bookmarked" ở Home sắp theo THỜI ĐIỂM BẤM, không theo thứ tự lưới** — dữ liệu
  vốn đã lưu đúng thứ tự bấm (`d["bookmarks"]` append/remove server-side; `toony_bm` localStorage
  guest), chỉ khâu hiển thị sai. Sửa 3 chỗ trong `reader_server.py`: (1) `follows` render server
  sắp theo `ud["bookmarks"]`; (2) truyền `BM` sang JS theo đúng thứ tự (bỏ `set()` làm mất thứ tự);
  (3) `renderFollows()` client duyệt theo `BM` thay vì theo `.card` trong lưới. Bỏ-rồi-bấm-lại →
  về cuối (đúng append). Không migration, tương thích dữ liệu cũ.
- **12/08: Auto-start = Phương án A (autologon), KHÔNG chạy SYSTEM/service** — vì Python cài per-user
  (hồ sơ Administrator) nên chạy SYSTEM/Session-0 dễ lỗi câm `0x80070002`; autologon tái tạo đúng môi
  trường đã chạy tốt. Task onlogon đổi sang `python.exe` (có cửa sổ). Đổi lại: desktop tự mở khoá sau
  reboot + supervisor gắn phiên (Switch user, đừng Sign out).
- **12/08: Comix danh tính tách đôi → mượn vé sống + giả TLS Chrome** — `ComixImageClient` (curl_cffi
  impersonate + cf_clearance/UA mượn từ browser, refresh ở main thread); `Forbidden(Blocked)` cho 403
  (refresh-retry 1 lần) tách khỏi breaker 503 mới (`tripped_503`, lùi 15→180s, chịu 5 đợt);
  `gate.recover()` reset sau chương trọn. Vì sao KHÔNG "clear sạch": Cloudflare coi request vô danh
  là ÍT tin nhất, vé nhất quán mới giảm nghi. Client riêng để không rò vé sang `core.session` chung.
  (Các quyết định 11/08 [reader chỉ quét downloads/, ACGNProvider, supervisor chống-chịu mạng] và cũ hơn
  09-10/08 về comix loop/relaunch đã ghi đầy đủ ở ARCHITECTURE.)

## Việc tiếp theo
- **[Reader pill + prefetch nghiệm thu LIVE]** `/update` qua bot (chỉ `reader_server.py`). Mở 1 chương:
  xác nhận **KHÔNG** tự hiện thanh công cụ, thay vào đó pill "Tap to show controls" nhấp nháy nhẹ ở đáy;
  chạm bất kỳ đâu → bật bars + pill tắt; cuộn/chạm-lại → ẩn bars + pill trở lại. Bấm Next / chọn chương:
  cảm giác chuyển gần như tức thì (không còn khựng 1-2s) sau khi trang đã rảnh 1 nhịp (prefetch xong).
- **[Comix ưu tiên official nghiệm thu LIVE]** Push (`day-len.bat`) → `cap-nhat.bat` trên server (đụng
  `comix_site.py`). `/tai <link Solo Leveling>` (hoặc bộ license nhiều official khác) 1 chương chưa có →
  soi log/sidecar `.source.json` thấy `group` = TappyToon (không phải Webcomic). Muốn đổi thứ tự: sửa dict
  `OFFICIAL_GROUP_RANK` đầu `comix_site.py`.
- **[convert_webp in-place nghiệm thu LIVE]** Push (`day-len.bat`) → code có trên server (convert_webp
  chạy TAY nên không cần `/update`, chỉ cần file trên đĩa). Nén 1 bộ comix CŨ: `convert_webp.bat` →
  chọn "Nen TAI CHO? y" (mức 85) HOẶC `python convert_webp.py "downloads\<bộ>" --in-place`. Xác nhận:
  ảnh nhẹ ~nửa, `.done`/`.source.json` còn nguyên, **chạy lại lần 2 báo "giữ-nguyên" hết** (idempotent);
  rồi `/tai <link bộ đó>` → chỉ tải chương mới (bỏ qua chương cũ), KHÔNG tải lại từ đầu.
- **[Comix q85 nghiệm thu LIVE]** Push (`day-len.bat`) → `/update` qua bot (đủ, không cần restart
  supervisor). `/tai <comix url>` 1 chương chưa có → xác nhận log downloader chạy trơn; soi dung lượng
  ảnh trong `downloads\<bộ>\Chapter N\` ~nửa so với comix gốc (mỗi trang vài trăm KB thay vì ~nửa MB),
  và mở reader thấy vẫn nét. Muốn tắt/đổi: `--comix-q 0` (giữ gốc) / `--comix-q 82`. Ảnh comix **đã tải
  từ trước**: chạy tay `convert_webp.bat` (mức 85, trả lời `y` ở "Re-nen ca WebP?") hoặc
  `python convert_webp.py "downloads\<bộ>" --webp-too` → kiểm folder `<bộ>_webp` rồi mới thay.
- **[Reader TTFB nghiệm thu LIVE]** `/update` qua bot (chỉ đụng `reader_server.py`). Trên server mở
  DevTools → Network → tab Timing của request document trang chủ: xác nhận "Waiting for server response"
  tụt từ ~4s xuống dưới ~vài trăm ms. Phép thử "nhiều lúc": để trang > 60s (cache hết hạn) rồi F5 —
  KHÔNG còn cú trắng 4s (giờ trả stale ngay, quét lại ở nền). Chỉ lần MỞ SERVER đầu tiên (cache lạnh)
  mới chịu 1 lượt quét đồng bộ. Đổi bìa qua admin vẫn hiện đúng bản mới (bust cache → build lại `cover_mt`).
- **[Reader SW + tách CSS/JS + ETag bìa nghiệm thu LIVE]** `/update` qua bot (chỉ `reader_server.py`).
  Mở link tunnel, DevTools → Application → Service Workers: xác nhận `sw.js` "activated". (a) **Bìa nháy**:
  login rồi logout → bìa KHÔNG còn nháy đen; Network `/cover/*` là `(ServiceWorker)`/`304`, không còn 200
  full. (b) **Màn trắng cold**: đóng web app, chờ >1' rồi mở lại → nội dung hiện gần như tức thì (shell từ
  cache SW), không còn trắng 2-3s. (c) **Đúng trạng thái**: sau login/logout, header + hàng Bookmarked
  phản ánh đúng tài khoản (nhờ purge `PAGE_CACHE`). (d) **Cập nhật nội dung**: thêm/sửa truyện → lần mở kế
  hiện bản cũ (SWR) rồi lần mở sau nữa là mới — chấp nhận được; nếu cần thấy ngay thì F5 lần 2. Lưu ý iOS
  Safari: SW có thể bị evict sau ~7 ngày không dùng → lần mở đầu sau đó chịu cold 1 lượt rồi ấm lại.
  (e) **Logo**: hiện gần như tức thì (WebP 18KB, cache-first + precache), không còn 5-10s vẽ dần. (f)
  **Prefetch series**: mở app, để lướt qua vài card (hoặc chạm giữ) rồi bấm vào → vào trang chương gần
  như tức thì ngay LẦN ĐẦU (trước 2-3s). Network sẽ thấy request `/series/*` do SW nạp nền trước khi bấm.
- **[Chống-treo ①+② nghiệm thu LIVE]** `cap-nhat.bat` → chạy lại `server-BAT-tudong.bat` (đụng
  `supervisor.py`). (a) Bình thường: `/tai <comix url>` → tải chạy trơn, KHÔNG bị kill oan (log tăng đều).
  (b) Giả treo mở-Chromium: trước khi `/tai`, mở tay 1 chrome ôm `comix-profile` để gây wedge → xác nhận
  tool tự "dọn rồi thử lại (lần k/3)" và cuối cùng tải được (② Cách B). (c) Giả treo câm: tạm hạ
  `dl_stall_limit` trong `notify-config.json` xuống ~120 rồi bắt job kẹt → xác nhận supervisor báo
  "⚠️ Tải bị treo… sẽ thử lại" + tự kill, KHÔNG kẹt cả hàng đợi; xong trả `dl_stall_limit` về 1200.
- **[/tai chọn chương nghiệm thu LIVE]** `cap-nhat.bat` → chạy lại `server-BAT-tudong.bat` →
  `/tai <link> 1-3` (chỉ 3 chương) rồi `/tai <link>` (cả bộ); soi `/trangthai` hiện "(ch 1-3)".
- **[Auto-check nghiệm thu LIVE]** Server: `cap-nhat.bat` → **chạy lại `server-BAT-tudong.bat`**
  (đổi supervisor phải restart, `/update` không nạp lại supervisor) → `/watch <link>` vài bộ đang
  theo dõi → `/watchlist` xác nhận có tên + provider + "mới nhất ch.N" → `/checknow` xem tóm tắt +
  hàng đợi tải chạy. Chỉnh giờ check qua `check_hour`/`check_min` trong `notify-config.json` nếu muốn
  khác 03:00. Sau 1 đêm: xác nhận có tin tóm tắt "🔍 Đã kiểm tra N truyện…" đúng giờ.
- **[Auto-start A nghiệm thu]** Trên server: `cap-nhat.bat` → chạy lại `server-BAT-tudong.bat` (đăng
  ký lại task bằng `python.exe`) → `server-AUTOLOGIN.bat` gõ pass (Enable) → reboot không đụng gì →
  xác nhận cửa sổ log "ToonyServer" hiện + Telegram link mới + heartbeat 🟢 + `/trangthai` trả lời.
- **[Comix 403/503 nghiệm thu LIVE]** Trên server: `/update` (xác nhận log in `(client tải ảnh:
  curl_cffi (giả vân tay Chrome))` = Bậc 2 bật; nếu in `requests (KHÔNG giả TLS…)` thì curl_cffi
  chưa cài — kiểm `pip install curl_cffi`). Chờ qua đợt siết rồi `/tai` lại bộ comix đang dở →
  xác nhận không còn chết vì 403; nếu 403 giữa chương phải thấy "làm mới vé… thử lại"; 503 wowpic
  phải thấy "tạm dừng Ns rồi tự tải tiếp" thay vì dừng phiên.
- **[Heartbeat]** Bật trên server: tạo check healthchecks.io → dán `heartbeat_url` → `cap-nhat.bat`.
- **[ACGN nghiệm thu]** `/update` → `/tai https://comic.acgn.cc/view-11338.htm` → xác nhận ra bộ
  `摺紙戰士` 22 tập, ảnh tải+decode OK; `check_library.py` soi.
- **[Supervisor resilience]** Nghiệm thu tự nhiên lần mạng server chập tới: KHÔNG spam link + hàng
  đợi KHÔNG mất.
- **[Tool làm nét → TƯƠNG LAI]** Tích hợp `/tai`: enhance → resize → nén, 1 job/lúc (1050 Ti).
- (Tùy chọn, gốc rễ) **Named tunnel + domain** để URL cố định — nếu mua domain rẻ.

## Lưu ý / rủi ro đang mở
- **Comix re-nén q85 là transcode LOSSY→LOSSY — nhưng chốt-tiết-kiệm 10% đã chặn nén-chồng**: cả
  `_recompress_webp` (inline lúc tải, chỉ ảnh mới trong `jobs`) lẫn `convert_webp.py` (tree/in-place) nay
  chỉ THAY bản gốc khi bản nén **tiết kiệm ≥10%** + `verify()` mở được; ảnh đã tối ưu (~1% nhỏ hơn) →
  GIỮ NGUYÊN. Nhờ vậy chạy lại/bấm nhầm KHÔNG suy hao thêm (idempotent trên thực tế). webp-động/gif/avif
  bỏ qua. Muốn giữ nguyên byte gốc từ site khi tải: `--comix-q 0`. Nếu SAU NÀY hạ ngưỡng xuống rất thấp
  (vd 1%) thì mất tính chống-chồng — giữ ~10%.
- **`--in-place` GHI ĐÈ ảnh gốc**: an toàn nhờ temp+verify+os.replace + chốt-tiết-kiệm (không mất data,
  không phình), nhưng KHÁC tree-mode ở chỗ không còn bản gốc để đối chiếu. Ai muốn chắc ăn thì chạy
  tree-mode (`--webp-too`) xem `_webp` ưng rồi mới đổi tên. `--in-place` chỉ đụng `.webp` (PNG/JPG kệ).
- **ĐỪNG giữ folder `<tên>_webp` rồi xóa gốc `<tên>`**: downloader ghi vào `downloads/<Title>` (KHÔNG có
  `_webp`) nên sẽ tải LẠI cả bộ. Dùng `_webp` thì phải đổi tên về `<tên>`; hoặc dùng `--in-place`.
- **Reader SWR: cache thư viện + bìa có thể cũ tối đa ~60s (CACHE_TTL)** — `cover_ver`/`cover_src` giờ
  đọc từ series cache thay vì stat đĩa mỗi render, nên thay file `cover.*` TAY (không qua admin) có thể
  chậm hiện ≤60s tới khi thread nền quét lại. Đổi bìa qua ADMIN thì tức thì (đã `bust_library_cache`).
  Chương mới xuất hiện trong list cũng trễ ≤60s (như trước). Nếu sau này cần "thấy ngay", giảm CACHE_TTL
  hoặc bust sau khi tải xong.
- **Reader: KHÔNG thêm splash-in-HTML để trị màn trắng** — đã chứng minh vô ích (SSR, TTFB thuần server).
  Nếu ai đề xuất lại, chỉ đường tới quyết định 19/08. Muốn feedback khi bấm = thanh progress đỉnh trang.
- **Stall-watchdog ① ngưỡng 1200s (`dl_stall_limit`)**: cố tình > cữ backoff 429 tệ nhất của
  `comics_core` (1 lần `sleep` tới 900s). Nếu SAU NÀY sửa `comics_core` (thêm cữ nghỉ dài hơn 900s,
  hoặc site trả `Retry-After` rất lớn) thì phải NÂNG `dl_stall_limit` tương ứng kẻo giết nhầm job đang
  nghỉ hợp lệ (giết nhầm không mất ảnh — resume bỏ qua `.done` — nhưng reset nhịp lịch sự IP). Chờ
  Cloudflare tick người (300s) + nhịp nghỉ mỗi-10-chương (≤90s) đều < 1200s nên an toàn.
- **② watchdog nổ mà Playwright KHÔNG bật lỗi sau khi kill chrome** → sau ân hạn 8s sẽ `os._exit(2)`
  (downloader thoát, supervisor báo lỗi + chạy job kế; ① là lưới cuối nếu cả cái này hụt).
- **Phương án A (autologon) — desktop tự mở khoá sau reboot** (ai chạm console/RDP thấy phiên đã đăng
  nhập). Supervisor gắn phiên interactive Administrator → **Sign out = giết server**, đổi tài khoản
  phải **Switch user**. Cửa sổ log giờ là `python.exe` — đóng nhầm/Ctrl-C = tắt server (tắt sạch:
  `server-TAT-tudong.bat`). Task chỉ chạy khi ĐĂNG NHẬP; autologon lo phần tự đăng nhập sau reboot.
- **curl_cffi là dep OPTIONAL cho comix**: thiếu → tự lùi về `requests` (vẫn mượn vé, kém chắc trước
  Cloudflare có vân tay TLS). Muốn Bậc 2 chắc ăn phải `pip install curl_cffi` (đã trong
  `requirements.txt`, `cap-nhat.bat` tự cài). Dev máy này CHƯA cài → dev chỉ test được Bậc 1.
- **Refresh vé chỉ được gọi ở MAIN THREAD** (Playwright sync API cấm gọi chéo luồng). Nếu sau này
  đổi cách tải ảnh, đừng để worker thread gọi `refresh_identity()`/chạm `cs.page`/`cs.ctx`.
- **403 giữa chương chỉ tự thử lại 1 lần** rồi dừng phiên (cố ý, tránh hammer 403 tụt điểm IP) —
  chạy lại đúng lệnh sẽ tải tiếp chỗ dở. 503 dồn >5 đợt cũng dừng phiên (nguồn/CDN lỗi thật).
- **Server mất mạng/DNS/điện thì reader vẫn KHÔNG vào được** — biết server sập = nhờ heartbeat ngoài.
- **Reader TREO mà chưa chết hẳn = không tự phục hồi** (đã bỏ health_loop): `run_reader` chỉ bật lại
  khi reader THOÁT; heartbeat không kiểm reader. Ca hiếm; gặp thì restart tay (`server-BAT`) / `/update`.
- **Server không hairpin được về tunnel công khai của nó** (GET link công khai từ server sai ~2/3) →
  đừng dùng phép "server tự GET link công khai" để đoán tunnel sống; xác minh dùng reader `127.0.0.1`.
- **`heartbeat_url` là BÍ MẬT** — không commit; trong `.reader-meta/notify-config.json` (đã gitignore).
- **Sửa `supervisor.py` phải deploy bằng `cap-nhat.bat`/`server-BAT`** (`/update` qua bot CHỈ restart
  reader → KHÔNG nạp lại supervisor).
- **Comix** dễ vỡ nhất khi site đổi build/DOM. `downloads/.comix-tmp/` là chỗ tráo Official — đừng
  xoá tay lúc tải. Xoá sidecar `.source.json` = tool coi như chưa rõ nguồn (có thể tải/upgrade lại).
- **1 hàng đợi CHUNG, 1 worker tuần tự FIFO**; đừng bấm `Tai truyen.bat` tay lúc bot đang tải
  (song song = dễ chặn IP).
- **Nếu tải lại sập tầng C**: đọc `.reader-meta/crash-trace.txt` + dòng "PHIÊN TRƯỚC CHẾT" trong
  `download-log.txt`.
- **Theo dõi tải qua bot**: chạy ẩn — xem Telegram / folder `downloads\` / tail `.reader-meta\tai-run.log`.
