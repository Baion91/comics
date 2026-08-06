# Kiến trúc & quy ước — project comics

## Tổng quan

Bộ công cụ cá nhân tải/quản lý/đọc truyện tranh, thuần Python (requests + Pillow),
chạy trên Windows. Không có framework, không có test tự động — kiểm chứng bằng
cách chạy thật + decode thử ảnh.

## Cấu trúc

- **Downloader đa site = engine chung + provider adapter** (refactor 22/07):
  - `comics_core.py` — ĐỘNG CƠ site-agnostic: `PoliteGate` + cầu dao 429,
    `_request`/`get_json`/`get_text` (mọi request qua van chung), `download_image`
    (resume + KIỂM TRA ảnh), `download_cover`, `make_cbz`/`pack_tree`, `run(provider, args)`
    (vòng lặp tải chung), và **LÕI KIỂM TRA ẢNH DÙNG CHUNG** (`sniff_format`,
    `inspect_image_bytes` [giải mã 1 lần: verdict + tùy chọn dò một-màu], `check_image_bytes`
    [bản gọn cho inline], `uniform_frame` [tầng 4: trang một màu], `intact_fraction` [đo phần
    cứu được của ảnh cụt], `_DecodeGate` [khóa đọc-ghi cho cờ toàn cục LOAD_TRUNCATED_IMAGES],
    sổ sự cố `load_issues`/`record_issue`/`is_known_broken`, `bad_marker`/`clear_bad`,
    `append_log`). Thêm site KHÔNG đụng file này.
  - **Kiểm tra chất lượng ảnh** (24/07): lõi ở `comics_core`, 2 đầu gọi vào —
    (1) *inline khi tải*: `download_image` kiểm tầng 1 (độ dài truyền tải) + tầng 2
    (chữ ký + giải mã) TRƯỚC khi ghi → ảnh hỏng không để lại file, resume tự tải bù;
    `run` báo chương thiếu trang (tầng 3). (2) *tool quét* `check_library.py` soi ảnh
    ĐÃ có trên đĩa: tầng 2 + soát khuyết trang + tầng 4 (đen/phẳng, chỉ báo). Cách ly
    ảnh hỏng = đổi tên `.bad` (reader tự ẩn vì sai đuôi; downloader tự tải bù, xong
    xóa `.bad`). Chi tiết "vì sao" xem phần Quyết định.
  - `providers.py` — NƠI DUY NHẤT chứa khác biệt từng site. Mỗi provider (class)
    khai: `name`, `domains`, `referer`, `series_slug`, `title_from_slug`,
    `list_chapters`→`[Chapter(number,title,ref)]`, `chapter_images`→`[url]`,
    `cover_url`. `ref` là "chìa" mờ mỗi site tự sinh/tự hiểu (Asura = URL API
    chương; Raven = URL trang chương). `PROVIDERS`/`by_name`/`REGISTRY` (map domain).
    Đang có: **AsuraProvider** (API JSON), **RavenProvider** (parse HTML + `ts_reader`).
  - `comic_downloader.py` — CLI mỏng: `resolve_provider()` tự nhận site theo domain
    của URL (hoặc cờ `--site`), rồi gọi `core.run`. Cờ giữ y hệt bản cũ
    (`--from/--to/--chapters/--cbz/--pack/--out/--workers/--delay`).
  - `asura_downloader.py` — **giờ chỉ là shim** gọi `comic_downloader.main(default=asura)`
    → lệnh/shortcut cũ + gõ slug trần vẫn chạy như Asura như trước.
  - `Tai truyen.bat` — shortcut trong folder (không ra Desktop): **vòng lặp** hỏi link
    → chương → cbz → chạy → "Tai truyen khac? (y/N)" (y quay lại, N thoát). Tự nhận site.
    Echo không dấu + `chcp 65001` (Python tự in tiếng Việt utf-8).
  - Thêm site mới: viết 1 provider + 1 dòng `PROVIDERS`. Đổi domain: thêm domain vào
    `domains` (giữ cũ); đổi host API/CDN thì sửa hằng `API`/`BASE` trong provider đó.
  - Nhiều session song song cùng sửa project — luôn đọc lại file trước khi sửa đè.
- `check_library.py` — tool quét ảnh ĐÃ tải (offline, **đa luồng**), dùng chung lõi
  kiểm tra với downloader. Nhận đường dẫn tùy chọn (cả `downloads/` / 1 bộ / 1 chương);
  cờ `--fix` (cách ly `.bad`), `--recheck` (bỏ cache), `--workers N` (mặc định=số nhân,
  tối đa 8), **`--black`** (opt-in: thêm dò "trang một màu"; là quét SÂU — bỏ cache đọc,
  giải mã lại toàn bộ, chậm). MẶC ĐỊNH = tầng 2 (giải mã) + khuyết trang, **0 báo nhầm**.
  Xuất `.reader-meta/check-report.html` (thumbnail base64) + `.json`; cache
  `.reader-meta/check-cache.json` (mtime+size, ghi liên tục mỗi 1000 ảnh + ghi nguyên tử
  qua .tmp → Ctrl-C không mất tiến độ/không hỏng cache) → quét lại chỉ soi cái mới. Bỏ qua
  folder `.`-prefix, `.reader-meta`, `.cbz`, file `.bad`; bỏ file sửa <5s (đang tải dở).
  `check-ignore.txt` = trang một-màu đã duyệt là OK (bỏ báo); `image-issues.json` = sổ
  chung với downloader (`salvaged` = ảnh cụt đã cứu, đừng báo/đừng cách ly; `source_broken`
  = hỏng sẵn ở nguồn, khuyết trang do nó là "đã biết"). `Kiem tra truyen.bat` là shortcut
  (vòng lặp hỏi thư mục/--fix/--black → chạy).
- `pokespe_update.py` — cập nhật chương Scarlet Violet từ pokemonspecial.com
  (blog Blogger): đọc feed → so folder local → tải chương thiếu. (Có sẵn kiểm giải mã
  `im.load()` từ trước — tiền lệ của lõi kiểm tra chung.)
- `convert_webp.py` — chuyển PNG→WebP hàng loạt, xuất cây mới `<tên>_webp`,
  không đụng cây gốc. Tách riêng khỏi asura_downloader vì Asura đã webp sẵn.
- `reader_server.py` — web reader kiểu Asura (HTML/CSS/JS inline trong Python
  stdlib, không dependency ngoài Pillow tùy chọn), port mặc định **8080**, user
  bật thủ công bằng shortcut Desktop **"Toony"**. Tính năng chính: quét tự động
  2 tầng folder (arc/chương) lẫn phẳng, sort số chương tự nhiên (0.1, 14.2...),
  ghép trang đôi thủ công (nút ⧉ → POST `/api/spread`), bộ nạp ảnh tuần tự JS
  kèm retry (tự thử lại 3 lần backoff 1s-3s-8s → ô "chạm để tải lại" → hồi cả
  cụm khi chạm/`online`/`visibilitychange`), bìa sidecar `cover.*`, thanh công
  cụ chạm-để-hiện, **nút chỉnh cỡ ảnh** (stepper −/%/+ header cạnh ⧉, có ô gõ % tay;
  100%=800px, min 1% cap 300%, đổi `#strip{max-width:min(var(--imgw,800px),100%)}`,
  kẹp theo màn không cuộn ngang, nhớ localStorage, ẩn ≤480px). **UI reader bằng
  tiếng Anh** (Bookmark/Bookmarked, All Comics, First/Latest Chapter, Prev/Next,
  Newest/Oldest, END OF CHAPTER...); comment code + log terminal giữ tiếng Việt.
  **Trang chủ** 2 mục có header ô-icon kiểu Asura: **Bookmarked** (slider ngang
  `.frow`, icon sao vàng; card ghi chương đang đọc / chưa đọc thì chương đầu, dựng
  lại client từ `FOLLOWDATA`+`BM` khi bấm bookmark) + **All Comics** (grid, icon
  menu_book). Card = `<div>` chứa `<a.cardlink>`(bìa+`.ct` 1 dòng ellipsis+`.cm`
  "N chaps · status") + nút `.bkbtn` (Bookmark tím → Bookmarked nền xám/sao+chữ
  vàng). Trang truyện: bìa trái, cột phải title+meta + nút Bookmark ghim đáy
  (`margin-top:auto`); hàng `First Chapter | Latest Chapter`, đang đọc dở thì nút 2 =
  "Chapter X - reading" (xanh lá) — server render sẵn theo `progress`. Danh sách
  chương có **Search** (`#chq`, lọc client theo số+tên, ẩn arc rỗng) + toggle
  **Newest/Oldest** (`#sortbtn`, đảo DOM `.arcsec`, nhớ `chsort` localStorage).
  **Hồ sơ đọc CHUNG server-side** (`user-data.json` + `GET/POST /api/state`): bookmark
  + vị trí đọc `progress{sid:{rel,y,name}}` + chương đã đọc `read{sid:[rel]}` — một
  hồ sơ duy nhất, KHÔNG login/cookie/device-id (mọi client chung); reader ghi progress
  debounce ~2.5s + flush khi rời trang (`keepalive`), đánh dấu đã đọc qua op `read`.
  imgw + chsort vẫn localStorage per-máy. **Trạng thái + thứ tự truyện**:
  `series_status()`/`series_order()`/`load_series_meta()` đọc `series-meta.json` (nạp
  theo mtime → sửa tay F5 ăn); `get_library()` gọi `sync_series_meta()` thêm truyện
  mới (append-only) + **đánh `order` = max hiện có + 1**; `ordered_library()` sort theo
  `order`. **Feedback bấm** (`PRESS_JS` nhúng mọi trang qua `page()`): nhún (`.press`
  scale, pointerdown) cho mọi nút; loé sáng (`@keyframes`) chỉ dòng danh sách chương +
  toggle tại chỗ (Newest/Oldest, Bookmark); +`prefers-reduced-motion`. **PWA / thêm-vào-màn-hình-chính**: `page()` head có Web App Manifest
  (`/manifest.webmanifest`, `display:standalone`, `start_url:/`) + apple meta
  (`apple-mobile-web-app-capable`, status-bar `black-translucent`) +
  `apple-touch-icon`; route riêng phục vụ manifest & icon PNG (whitelist
  `ICON_FILES`, chặn đọc file tùy ý). Mở từ Home chạy fullscreen tràn đỉnh, bù
  `env(safe-area-inset-top)` cho `#topbar`+`.wrap` để header không bị Dynamic
  Island che. Sửa xong phải RESTART server mới ăn (HTML/CSS nằm trong hằng
  Python).
- `.reader-meta/` — dữ liệu phụ (reader + tool quét), KHÔNG nằm trong folder truyện:
  `check-report.html`/`.json` (báo cáo quét ảnh), `check-cache.json` (ảnh đã kiểm tốt,
  mtime+size), `check-ignore.txt` (trang một-màu đã duyệt là OK), `image-issues.json` (sổ
  ảnh cứu-vớt / hỏng-tại-nguồn, downloader + tool quét dùng chung), `download-log.txt`
  (nhật ký chương thiếu trang / hỏng nguồn khi tải),
  `spreads.json` (cặp trang đôi đã ghép {left,right} theo sid/chương),
  `series-meta.json` ({sid: {status: complete|ongoing, order: N}}, key=tên folder;
  status thiếu=ongoing; `order` = thứ tự Home, sửa tay được, truyện mới auto=max+1;
  server nạp lại theo mtime + thêm truyện mới append-only — không đè giá trị sửa tay),
  `user-data.json` (HỒ SƠ ĐỌC CHUNG: {bookmarks:[sid], progress:{sid:{rel,y,name}},
  read:{sid:[rel]}}; 1 hồ sơ cho mọi client, ghi qua `/api/state`, nạp theo mtime.
  **Reset = xoá cả file khi server ĐANG TẮT** — xoá lúc chạy có thể bị ghi đè lại từ
  cache RAM `_udata`),
  `reader-manga.ico` (favicon/icon shortcut Windows) + `icon-src.png` (nguồn
  1254² để sinh icon), **`icon-{180,192,512,512-maskable}.png`** (icon PWA
  home-screen, tạo tĩnh 1 lần bằng script từ `icon-src.png`), `brand.png` (logo
  chữ), `cloudflared.exe`.
- `Chia se link doc thu.bat` / `Tat chia se link.bat` — bật/tắt cloudflared
  quick tunnel (link trycloudflare ngẫu nhiên) cho người ngoài đọc thử.
- `downloads/<Tên truyện>/Chapter N/001.webp...` — thư viện; mỗi truyện 1 folder.
  Folder bắt đầu bằng dấu chấm bị reader bỏ qua (đang chứa backup PNG của Ouja).
- `README.md` — hướng dẫn sử dụng cho user (tiếng Việt).

## Mạng & chia sẻ

- **Tailscale** (cài 16/07, acc daotung.fpt@): PC `100.87.162.74`, iPhone
  `100.91.104.12`. Địa chỉ đọc chuẩn mọi nơi: `http://100.87.162.74:8080` —
  khuyên dùng thay IP LAN vì IP LAN đổi theo DHCP. Firewall rule
  "Web doc truyen 8080 (Tailscale)" chỉ mở TCP 8080 cho dải `100.64.0.0/10`.
- **Server bind `0.0.0.0:8080`** (nghe mọi interface, gồm cả LAN lẫn Tailscale) →
  đổi wifi / IP LAN đổi **KHÔNG cần restart server**; chỉ client phải đổi sang IP mới.
  Link LAN in ở banner do `lan_ip()` lấy IP default-route lúc khởi động → ephemeral,
  đổi wifi là chết → nên bookmark link Tailscale. Cạm bẫy: wifi mới bị Windows xếp
  "Public" có thể chặn 8080 cho LAN client; Tailscale không ảnh hưởng (rule lọc theo
  dải IP, không theo network profile).
- **KHÔNG bật UPnP** trên router: PC đặt ở mạng công ty, UPnP hạ an ninh cả
  văn phòng. Chấp nhận Tailscale đi DERP relay khi phone dùng 5G (chậm hơn).
- Server không có mật khẩu — chỉ dùng trong LAN/Tailscale, không phơi công khai
  lâu dài; chia sẻ tạm thì dùng quick tunnel và tắt ngay khi xong.

## Quyết định quan trọng & lý do

- **Engine chung + provider adapter thay vì copy 2 script** (22/07): 2 site chỉ khác
  đúng cách lấy danh sách chương + URL ảnh (~2 hàm); phần còn lại (PoliteGate/cầu dao
  429, tải resume, cbz, folder layout) giống hệt. Yếu tố quyết định là **không muốn 2
  bản PoliteGate/429 lệch nhau** — code tinh tế, sửa 1 nơi phải ăn mọi site. Site thứ
  3+ chỉ tốn ~40 dòng provider.
- **Raven lấy ảnh từ `ts_reader.run({...})`** (theme Themesia "mangareader", WP): danh
  sách chương = parse `<a href=".../{slug}-chapter-N/">` trong trang `/series/{slug}/`
  (1 request, có chương lẻ `chapter-162-5`=162.5); ảnh = regex khối `ts_reader` →
  `sources[0].images` (URL đầy đủ, đúng thứ tự). CDN `cdn1.ravenscans.org` trả **.jpg**,
  **không đòi Referer** (đã test 206). Chương khóa → images rỗng → skip như premium Asura.
- **Raven giữ .jpg, KHÔNG convert sang WebP**: nguồn đã JPEG lossy → nén lại chồng suy
  hao (đúng chính sách WebP bên dưới). Thư viện thành hỗn hợp webp(Asura)+jpg(Raven);
  reader đọc cả hai (`IMG_EXTS`). Cloudflare hiện chưa challenge GET thường → chưa thêm
  cloudscraper/curl_cffi, để cầu dao 403/503 dừng gọn, thêm khi thực sự vỡ.
- **Dùng API JSON thay vì parse HTML** (Asura): trả URL ảnh đúng thứ tự trang;
  bắt buộc vì chương mới đặt tên ảnh hash ngẫu nhiên, không đoán được URL.
- **PoliteGate + cầu dao 429** (sự cố 16/07/2026: 5 luồng không nghỉ → CDN chặn
  429 hàng loạt giữa chương 8): mọi request đi qua van chung ~2 req/s có jitter;
  gặp 429 → toàn bộ dừng chờ (90s→5ph→15ph, lần 4 hủy phiên); 403/503 → thoát
  ngay. Triết lý: **lịch sự chứ không lẩn trốn** — không proxy, không xoay UA.
  Bài test thực chiến: 223 chương/~2900 request/2 tiếng, 0 lần 429.
- **Kiểm tra ảnh: lõi chung, tự-động-theo-độ-chắc-chắn** (24/07): đặt lõi trong
  `comics_core` (không rải mỗi nơi một bản — đúng bài học PoliteGate). Chia tầng theo
  độ tin cậy tín hiệu: tầng 1 (độ dài truyền tải) + tầng 2 (chữ ký + giải mã) gần như
  0 nhầm → TỰ xử (chặn lúc tải, cách ly khi quét); tầng 4 (một-màu) có thể nhầm → CHỈ
  báo + **opt-in `--black`**. **Pillow chỉ để KIỂM TRA** (giải mã RAM) rồi ghi byte gốc
  → giữ chính sách không-lossy-chồng-lossy; tách vai trọng-tài ≠ máy-nén.
- **Tầng 4 chỉ bắt "trang MỘT MÀU toàn khung", đã bỏ "dải đáy phẳng"** (24/07): soi thật
  133 nghi ngờ trên thư viện → 131 là "dải đáy phẳng" bắt nhầm **lề TRẮNG cuối trang**
  (đo màu đáy ≈255, đúng bố cục webtoon bình thường), 0 lỗi thật. Bài học: dò "đáy phẳng"
  vô giá trị (mục tiêu đáy-đen-do-cụt đã do tầng 1/2 lo) mà nhiễu cao. Chỉ giữ dò
  cả-khung-một-màu (`getextrema` toàn ảnh sát nhau) — hiếm, mạnh, gần như không nhầm vì
  tranh vẽ (kể cả cảnh đêm) luôn có nét → cực trị giãn. Để opt-in vì cần giải mã đầy đủ
  (chậm) và giá trị cao đã nằm ở tầng 1/2/3.
- **Hỏng-tạm-thời vs HỎNG-TẠI-NGUỒN + cứu vớt ảnh cụt** (25/07): sự cố thật — Raven
  `worn-and-torn-newbie` ch.30 trang 3 hỏng, tool cứ bảo "chạy lại để tải bù" nên user
  chạy lại nhiều lần vô ích. Nguyên nhân: file trên CDN **vốn đã cụt** (thiếu 42 byte
  cuối, mất EOI `FFD9`; Content-Length khớp nên KHÔNG phải đứt mạng) → tải lại luôn ra
  đúng bản hỏng. Sửa 2 điểm: (a) **hỏng lặp lại y hệt (cùng số byte + cùng verdict) = nguồn
  hỏng** → dừng thử lại ngay, ghi `.reader-meta/image-issues.json`, lần sau bỏ qua không
  tốn request (cờ `--retry-broken` để thử lại), thông báo đúng bản chất thay vì xui chạy
  lại; (b) **cứu vớt**: ảnh cụt còn đọc được ≥`SALVAGE_MIN` (50%) thì VẪN ghi byte gốc —
  thà đọc được phần lớn còn hơn mất trắng cả trang (trình duyệt vốn cũng hiển thị được);
  tool quét đọc sổ nên không báo hỏng/không cách ly ảnh đã cứu, và coi khuyết-trang do
  nguồn-hỏng là "đã biết". **Bẫy kỹ thuật**: đo phần cứu được phải bật cờ TOÀN CỤC
  `ImageFile.LOAD_TRUNCATED_IMAGES`, nếu luồng khác giải mã nghiêm trúng lúc đó thì ảnh
  cụt "qua bài" oan → phải có `_DecodeGate` (nghiêm = nhiều luồng như khóa đọc; khoan dung
  = độc quyền). Sau lỗi `load()`, Pillow KHÔNG cho đọc pixel đã giải mã (đã thử) nên bắt
  buộc dùng cờ, không né được.
- **Ch.30 Worn And Torn Newbie: khuyết trang 3 là ĐÚNG, không thiếu nội dung** (25/07):
  đối chiếu pixel → ảnh hỏng đó TRÙNG nội dung trang 2 (lệch 0.02/255 = cùng file), và 7
  ảnh đang có khớp 1:1 với 7 trang nội dung bên Asura (5 trang khớp chính xác chiều cao,
  trang cuối = `008_p1`+`008_p2`). Tức nhóm up Raven đăng trùng 1 trang và bản trùng bị
  cụt. Quyết định: **giữ nguyên, không chèn bản Asura** (sẽ thành trang lặp), chỉ ghi sổ.
- **Cách ly bằng đổi tên `.bad`, hai đầu nối nhau** (24/07): `001.jpg→001.jpg.bad` — reader
  bỏ qua vì sai đuôi (`IMG_EXTS`), resume thấy tên chuẩn khuyết → tự tải bù, tải bù xong
  `clear_bad` xóa marker. Sự thật ở ĐĨA (`.bad` mất khi bù xong), report HTML chỉ là ảnh
  chụp. Cache chỉ nhớ ảnh sạch-hẳn; nghi-ngờ/unsupported không cache để lần sau còn soi lại.
- **Chính sách WebP**: PNG → WebP q85 (giảm 50-80%, mắt thường không phân biệt
  với truyện scan); JPG **giữ nguyên** (đã lossy, nén lại chồng suy hao).
- **Đặt tên folder từ slug**: chỉ cắt cụm cuối nếu đúng 8 ký tự hex có chữ số
  (hash kiểu `-1d35e5bd`); slug từ API search không có hash, cắt mù sẽ mất chữ
  cuối tên truyện (bug "The-Greatest-Estate" 16/07).
- **Blog pokespe có 2 thời kỳ đặt tên ảnh**: bài cũ `001.png`, bài mới
  `... 028 page 18.jpg`. Ưu tiên mẫu "page N" vì tên thuần số dễ dính banner
  trang trí của blog (`1.png`, `3.png`). Ảnh Blogger: thay segment size trong
  URL bằng `/s0/` để lấy bản gốc full nét.
- **Mẫu kiểm chứng chuẩn** sau tải/convert: (A) đối chiếu từng file, (B) PIL
  `im.load()` toàn bộ ảnh (bắt file cụt dữ liệu), (C) soát dãy số trang liền mạch.
- **Retry ảnh backoff tăng dần, không đều** (1s-3s-8s): server là local/LAN nên
  lỗi chỉ có 2 loại — chập thoáng qua (<1s) hoặc mạng/server chết hẳn (retry vô
  ích). Với số lượt thử hữu hạn (3), giãn cách tăng dần phủ phân bố sự cố tốt hơn
  giãn đều; không phải để tránh quá tải server. Ba nguồn kích hoạt hồi phục
  (chạm ô lỗi / `online` / `visibilitychange`) dồn về chung một hàm `revive()`.
- **Trạng thái truyện = JSON tập trung + sửa tay live** (04/08): lưu ở
  `.reader-meta/series-meta.json` (không rải mỗi folder, nhất quán `spreads.json`);
  tra trạng thái LÚC RENDER nên không dính cache thư viện 60s. Sửa trạng thái bằng tay
  file JSON, `load_series_meta()` nạp lại theo **mtime** → F5 ăn ngay, khỏi restart;
  `get_library()` gọi `sync_series_meta()` tự thêm truyện mới (append-only, KHÔNG đè giá
  trị user sửa tay, không prune truyện đã xoá). Hiển thị **inline** cạnh số chương (đã thử
  badge góc bìa rồi bỏ theo ý user). (05/08 mở rộng: thêm trường `order` vào chính file này
  cho thứ tự Home; danh sách chương trang truyện chuyển sang **toggle Newest/Oldest** client
  thay vì cố định — dropdown `chsel` trong reader vẫn mới-nhất-trên-cùng; `order`/`byrel`
  điều hướng đọc luôn giữ tăng dần.)
- **Hồ sơ đọc = 1 JSON CHUNG server-side, không login/cookie/device-id** (05/08): trước đây
  vị trí đọc/chương-đã-đọc để localStorage → **chết theo origin**; user chia sẻ bằng
  cloudflared quick tunnel (`Chia se link doc thu.bat`) đổi URL ngẫu nhiên mỗi lần bật →
  mất sạch tiến trình. Đã cân nhắc device-id (cookie) và login: cả hai cũng neo theo host
  nên KHÔNG cứu được đổi-URL trừ khi gõ tay danh tính. Chọn **1 hồ sơ chung** (`user-data.json`):
  bền qua mọi đổi URL/IP/restart + PC↔điện thoại tự sync, đổi lại **khách qua tunnel dùng
  chung** (chấp nhận, tắt tunnel khi xong). Ghi progress có debounce + `keepalive` (flush khi
  rời trang). UI dịch sang tiếng Anh cùng đợt.
- **Feedback bấm: nhún nền + loé sáng chọn lọc** (05/08): nhún (scale, `.press` gắn bằng
  `pointerdown` — iOS Safari không nảy `:active` khi chạm nhanh) làm cue mặc định cho MỌI
  nút; loé sáng (`@keyframes`) chỉ dành cho **dòng danh sách chương + toggle tại chỗ**
  (Newest/Oldest, Bookmark) — nút điều hướng (Home, Prev/Next) rời trang ngay nên loé bị cắt,
  chỉ nhún. Hover chỉ trong `@media(hover:hover)` để cảm ứng không dính viền. Thêm
  `prefers-reduced-motion`.
- **PWA standalone (thêm vào màn hình chính)**: chọn status-bar `black-translucent`
  + `env(safe-area-inset-top)` thay vì `black` — để nội dung tràn edge-to-edge lên
  đỉnh (giống asura) thay vì để iOS chừa dải đen; ảnh (`#strip`) cố tình KHÔNG bù
  inset (giữ full-bleed), chỉ header/`.wrap` mới bù. **iOS không cần HTTPS**
  (`apple-mobile-web-app-capable` không bị gate TLS) → fullscreen ngay qua LAN
  IP/Tailscale IP http. **Android CẦN HTTPS** (manifest bị gate secure context) →
  qua http chỉ nhận đúng icon, chưa ẩn thanh; bật Tailscale Serve/cloudflare là
  ẩn, KHÔNG phải sửa code. Icon home-screen phải là **PNG** (iOS bỏ qua `.ico`);
  bản maskable chừa lề để Android cắt tròn không phạm hình. `#botbar` đã bù
  `safe-area-inset-bottom` từ trước.

## Ràng buộc từ user (xem thêm memory)

- **Không auto-start bất cứ gì** trên máy (PC làm việc công ty). Server bật tay
  qua shortcut. Khởi chạy tiến trình gì phải báo trước cửa sổ nào sẽ hiện.
- Quy trình quen thuộc: user hay yêu cầu "phân tích/đưa phương án, **chưa code**"
  trước, duyệt rồi mới cho code.

## Gotcha môi trường

- Console Windows mặc định cp1252 → script nào in tiếng Việt phải
  `reconfigure(encoding="utf-8")` (các script đều có sẵn); script ad-hoc thì
  chạy với `PYTHONIOENCODING=utf-8`.
- **`RequestsDependencyWarning` khi import `requests`** (Python 3.14 + urllib3/
  charset_normalizer mới hơn range requests test): vô hại, tải vẫn chạy. Đã ẩn bằng
  `warnings.filterwarnings(... "supported version" ...)` TRƯỚC `import requests` trong
  `comics_core.py`. KHÔNG `2>nul` trong .bat (chôn luôn lỗi thật). Tiến độ tải dùng `\r`
  ghi đè 1 dòng — bình thường; chỉ khi xem qua pipe/`cat -v` mới thấy tách nhiều dòng.
- Python của Windows không hiểu đường dẫn Git Bash `/c/...` — truyền path
  Windows vào phần Python.
- iOS Safari ẩn `:8080` trên thanh địa chỉ — user tưởng server chạy port 80.
- Windows cache icon shortcut theo ĐƯỜNG DẪN file — đổi icon phải trỏ sang tên
  file .ico MỚI, ghi đè file cũ sẽ không thấy đổi.
- **iOS cache icon/manifest/status-bar-style của home-screen shortcut lúc THÊM** —
  đổi các thứ này xong phải xoá icon cũ rồi Add to Home Screen lại mới thấy.
- **Bìa reader dùng URL `?v=<mtime>`** (`cover_url()`): route `/cover` cache 7 ngày với URL
  cố định → thay `cover.*` mà URL không đổi thì trình duyệt/PWA kẹt ảnh cũ. Gắn mtime vào
  query để đổi bìa là đổi URL → tự tải mới. Chỉ để **1 file `cover.*`** mỗi folder (nhiều
  file thì `cover_source` chọn theo thứ tự `os.scandir`, không xác định).
- Trang đôi manga đánh số ngược thứ tự đọc (file trước = trang bên PHẢI, đọc
  phải→trái) — default RTL của tính năng ghép dựa trên điều này.
- Ảnh user đính kèm trong chat không có file trên đĩa — vớt được qua clipboard:
  `[System.Windows.Forms.Clipboard]::GetImage()`.

## Lệnh thường dùng

```
python comic_downloader.py <URL> [--from A --to B | --chapters 5,7,20-25] [--cbz]   # tự nhận site
python comic_downloader.py --site raven <slug>     # ép site khi gõ slug trần
python comic_downloader.py --pack "downloads\<Tên>"
python check_library.py [downloads\<Tên>] [--fix] [--recheck] [--workers N] [--black]  # kiểm ảnh đã tải
python asura_downloader.py <URL|slug> ...           # shim cũ, vẫn chạy (mặc định Asura)
# hoặc double-click "Tai truyen.bat" trong folder rồi dán link
python convert_webp.py "<folder>" [--quality 90] [--jpg-too]
python pokespe_update.py [--dry-run]
python reader_server.py [--port 8080]   # thường bật bằng shortcut "Toony"
```
