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
    **Móc `render_pages` (30/09/2026, cho moetruyen)**: provider CÓ `render_pages(chapter, jobs)`
    thì `run()` gọi nó (generator, main thread, tuần tự) THAY pool HTTP `download_image` cho các
    trang còn thiếu; yield 1 bool/job. Hợp đồng: provider CHỈ ghi file khi ảnh đạt kiểm tra →
    tầng 3 (đếm thiếu/`.done`/tổng kết) giữ nguyên, trang hụt lượt sau tự bù. `chapter_images`
    vẫn phải trả đủ N "URL" (có thể giả, đuôi quyết định đuôi file) để core tính trang thiếu.
    Provider không có móc → đường cũ y nguyên (đã hồi quy ZetTruyen + qqcomvn).
    **Móc `png_to_webp` (01/10/2026, cho hentaivnx)**: trang PNG lưu thành `NNN.webp` mã hoá q90 lúc tải
    (`png_to_webp()` + tham số `to_webp` của `download_image`) — chi tiết + lý do ở mục HentaiVNX bên dưới.
    **Móc `drop_spacers` (08/10/2026, cho hentaivnx)**: provider khai `drop_spacers = True` → `run()`
    truyền `drop_spacer=True` cho `download_image`; ảnh qua tầng 1+2 mà có cạnh ≤ `SPACER_MAX_SIDE`=4px
    (`spacer_size()` đọc header) → KHÔNG ghi ảnh, ghi marker `spacer_marker(dest)` = `NNN.ext.spacer`
    (nội dung `WxH bytes url`) rồi trả True. Marker = trang ĐÃ CÓ ở mọi chỗ: `download_image` trả True
    ngay (mọi provider, rẻ 1 stat), `_have()` của `run()` (chương đủ → `.done`, resume không tải lại),
    `check_library.collect` cộng số trang marker vào `present` (đệm GIỮA chương không bị báo khuyết).
    Reader/`list_images`/cbz/`check_updates._has_images` lờ vì không đúng đuôi ảnh. VÌ SAO marker chứ
    không bỏ khỏi list URL: kích thước chỉ biết sau khi tải (dò trước = gấp đôi request cho ca hiếm),
    và tên trang gắn với VỊ TRÍ trong list → bỏ trang = lệch số/khuyết. Ảnh đệm đã lưu trước móc này vẫn
    nằm nguyên (không tự dọn). Provider không bật → đường cũ y nguyên (đo: cùng URL đệm → ghi file 916B).
    **`get_text(url, retries, encoding=None)` (08/10/2026, cho hentaivnreal)**: `encoding` ép bảng mã khi
    server KHÔNG khai charset (requests khi đó đoán ISO-8859-1 cho mọi `text/*` → tiếng Việt vỡ
    "ChÆ°Æ¡ng"). None = y như cũ (mọi provider khác không đổi).
    **`Challenged(Blocked)` (28/09/2026)**: `_request` thấy header `cf-mitigated: challenge`
    (Cloudflare đòi xác minh — thường kèm 429/403) → ném NGAY, **không kéo cầu dao 429**.
    Trước đó 429-challenge bị coi là rate-limit: ngủ 90s→5'→15' rồi `gate.abort` → trong
    `check_updates` làm hỏng MỌI truyện sau trong lượt dò. Challenge chờ bao lâu cũng không qua
    (cần JS/người) nên dừng ngay là đúng; site không bị challenge thì hành vi y cũ.
    **Bìa là PHỤ (01/10/2026)**: `run()` bọc `cover_url` + `download_cover` trong try — `Blocked`/
    `TooMany429` ở bước bìa chỉ in cảnh báo rồi tải chương tiếp (còn thiếu `cover.*` thì lần sau tự thử
    lại; reader tạm lấy trang đầu làm bìa). Trước đó bìa gọi NGOÀI khối try chính → 403 bung traceback,
    exit 1 trước khi tải chương nào (sự cố qqcomvn 30/09: bìa `/media/book/` nằm trên host site sau
    Cloudflare, thang leo Chromium chỉ lo HTML). 429/503 cạn ngân sách đã bật `gate.abort` → chương đầu
    tiên dừng phiên sạch (exit 2) như mọi lần.
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
    Đang có (+ nhentai/hentaifc/hitomi one-shot 18+ và phapbi blog Blogger, xem cuối danh sách): **AsuraProvider** (API JSON), **RavenProvider** (parse HTML + `ts_reader`),
    **DilibProvider** (parse HTML PHP), **MangaDexProvider** (API JSON, bản dịch `en`),
    **TruyenQQProvider** (parse HTML, họ `truyenqqko/to/vn.com` — KHÔNG gồm `truyenqq.com.vn`,
    site khác, xem TruyenQQVNProvider), **ACGNProvider** (parse HTML tĩnh,
    `comic.acgn.cc`, truyện tiếng Trung — ảnh nhúng `_src` trong trang `view-{id}.htm`,
    danh sách tập ở `manhua-{slug}.htm`; số chương từ text `VOL`/`第N話`; referer=None;
    CDN `img.acgn.cc` lọc theo vùng → 522 ngoài VN),
    **NetTruyenProvider** (parse HTML tĩnh, `nettruyen.id`, React/Next.js SSR — chương là
    SUB-PATH `/truyen-tranh/{slug}/chuong-N`, ảnh nhúng `<img class="lozad" data-src="…">`
    CDN `images.truyenonline.cc` KHÔNG đòi Referer → referer=None; tên có dấu từ
    `<h1 class="title-detail">`; regex số chương dùng `[0-9]` thuần để không nuốt dấu `\`
    của blob `__NEXT_DATA__`; chỉ nhận `nettruyen.id`, clone họ nettruyen backend/CDN KHÁC),
    **ZetTruyenProvider** (`zettruyen1.com`, LAI: danh sách chương qua API JSON PHÂN TRANG
    `/api/comics/{slug}/chapters?per_page=100&page=N` [trang series chỉ có nút First/Latest,
    `window.comicData.apiUrl` mới có list; per_page tối đa ~100, lặp tới `last_page`], nhưng
    ẢNH nhúng SẴN trong HTML trang đọc `<div class="chapter-images-container">`. Cloudflare
    KHÔNG challenge GET thường (như NetTruyen). Chương lẻ: `chapter_slug` "chapter-331-2" →
    URL trang đọc `/chuong-331.2` (đổi '-'→'.'; DÙNG DẤU CHẤM — `/chuong-331-2` rơi về chương
    331 nguyên, SAI). ⚠️ HOST CDN ĐỔI THEO CHƯƠNG (cdn1/cdn3/cdn4.zetimage.com) → lấy ảnh
    HOST-AGNOSTIC + đòi dạng `/{num}/{page}.ext`, dedup vì `onerror` lặp mỗi URL. ⚠️ Đuôi URL
    `.jpg` nhưng BYTES thật là WebP/PNG/JPEG lẫn lộn theo chương — file lưu `NNN.jpg` nhưng
    engine kiểm ảnh dựa NỘI DUNG nên OK, reader/browser content-sniff render; chấp nhận lệch
    đuôi (không đụng core). ⚠️ CDN cdn*.zetimage.com CHỐNG HOTLINK → referer=`{BASE}/` (kiểm
    theo domain site; API list KHÔNG cần referer nên check_updates peek được). Tên có dấu từ
    `<h1 class="comic-title-content">`. Domain có số (zettruyen1) → dễ đổi như TruyenQQ: đổi
    thì thêm `domains` + đổi BASE/referer sang domain hiện hành),
    **TruyenQQVNProvider** (`name="qqcomvn"`, `truyenqq.com.vn`, 28/09/2026) — site RIÊNG dù trùng
    tên họ ko (code khác: URL `/{slug}` + `/{slug}/chapter-N`; CDN riêng `sNN.cc3t.net`, host đổi
    theo truyện s34/s25… → lấy nguyên URL; CDN đòi `Referer: {BASE}/`, thiếu 403). **⚠️ SỐ CHƯƠNG =
    SỐ THỨ TỰ CỦA SITE**: site đánh 1..N (có bộ 0..N) liên tục, không chương lẻ, chèn cả extra →
    lệch số thật TĂNG DẦN (Tinh Giáp: vn N = thật N−1 đầu bộ → N−15 cuối bộ, đo bằng khớp chuỗi số
    trang với truyenqqko); site KHÔNG lộ số thật ở đâu → folder LUÔN hậu tố `SUFFIX=" [QQ.vn]"`
    (không bao giờ trộn với folder cùng tên của nguồn số thật — trộn = hỏng thư viện âm thầm) +
    `positional_numbers=True` (CLI chặn ghép `into:`/`--dest-name`). **⚠️ CLOUDFLARE CHẬP CHỜN**
    (trang series: 12/09 403-challenge, 27/09 429-challenge, 28/09 mở; trang chương mở cả 3 lần) →
    KHÔNG BAO GIỜ gọi trang series: mọi thứ lấy từ 1 **trang chương mốc** (thử `chapter-1` → link
    người dùng dán → `chapter-0`): dropdown `<option value="/{slug}/chapter-N">` có ĐỦ danh sách
    (regex chấp nhận value/href, URL tương đối lẫn tuyệt đối), `og:title` → bỏ đuôi ` - Chapter N`
    neo cuối (giữ tên có `:`), JSON `recently_viewed` `"image"` → bìa `/media/book/<file>` (nhỏ
    ~190×247; 28/09 chưa bị challenge, **30/09 đã bị 403** khi site chặn HTTP → bước bìa của core bỏ
    qua, không dừng phiên). Ảnh: `<img>` trong khối `.reading-content` (tới
    `reading-option` dưới), đọc `data-src`; mất khối → dự phòng URL tuyệt đối có `/chapter-N/`
    (loại ảnh quảng cáo `/media/images/` src tương đối); khối có mà rỗng = chương rỗng ở nguồn (bỏ
    qua, không dừng); `LAYOUT_FAIL_LIMIT=3` chương LIỀN không nhận ra cấu trúc → `Blocked` "site đổi
    giao diện" + lưu HTML mẫu `.reader-meta/qqvn-debug/`. **THANG LEO 2 TẦNG** (`_fetch`): HTTP
    thường (`get_text`; thêm dò title "Just a moment") → bị `Challenged` thì chuyển sang Chromium
    thật (`cf_browser`, import lười) cho HẾT tiến trình (`_escalated`, khỏi dội CF bằng request chắc
    bị chặn); ảnh LUÔN tải HTTP đa luồng (CDN không challenge). `fetch_mode` (cờ `--fetch
    auto|http|browser`), `allow_browser` (check_updates đặt False → ném Challenged thay vì mở
    Chromium), `close()` (dispatch gọi trong finally). **Chất lượng (đo 28/09, đính chính)**: phần
    lớn ảnh GIỐNG HỆT họ ko (vn ch2↔ko 1, vn 408↔ko 393: cùng MP/byte), có chương nét hơn (vn ch1
    1000 vs 900px) và có chương KÉM hơn (vn ch3 800 vs 900px, 0.85× điểm ảnh) — KHÔNG phải "bản
    xịn" đồng loạt.
    **MoeTruyenProvider** (`name="moetruyen"`, `moetruyen.net`, 30/09/2026) — ảnh bảo vệ IMGX: KHÔNG có
    URL ảnh (bytes qua `page-access` + worker, vẽ lên lớp canvas chặn `toDataURL`…; trang chương gửi
    header `X-AI-Policy: no-reverse-engineering`) → **CHỤP trang đã hiển thị** trong Chromium thật qua
    móc `render_pages`; chỉ quan sát DOM + chụp phần tử, KHÔNG đụng worker/page-access (cùng tinh thần
    "quan sát, không reverse" của comix). Tách 2 đường: **metadata HTTP** (Cloudflare hiện không
    challenge GET; bị challenge → thang leo `_fetch` chép khuôn qqcomvn, `allow_browser`/`fetch_mode`
    y hệt) — trang truyện `/manga/{id-slug}` chỉ có ~30 chương mới nhất → lấy 1 link chương làm MỐC
    (ưu tiên link người dùng dán), dropdown trang chương `data-href=".../chapters/N"` + "Ch. N — Tên"
    có ĐỦ bộ (gộp thêm list trang truyện); tên `data-reading-manga-title`; bìa og:image bản `-md` (bản
    lớn `-lg` 403 → `download_image` ném Forbidden = dừng phiên, nên KHÔNG đoán URL); số trang
    `data-reader-total-pages` → `chapter_images` trả URL GIẢ `moe://page/N.webp` (core đặt tên
    `NNN.webp`, chương đủ ảnh → `.done` KHÔNG mở trình duyệt; check_updates dò bằng HTTP → `ok`).
    **Chụp** (`render_pages`, profile `moe-profile`, `extra_hosts` = `truyen.moe`/`ibyteimg.com`/
    `tiktokcdn.com`/`cdn.jsdelivr.net` [bytes ảnh do JS site fetch từ `*.ibyteimg.com` — thiếu là không
    vẽ], `block_types=()`): mở chương 1 lần (`goto`) + CSS bỏ viền khung (0.67px) + ẩn `.reader-dock`;
    mỗi trang: card `.page-card:not(.reader-chapter-bridge)` thứ i (loại khung "Chương kế tiếp" nằm
    SAU trang cuối — bug của tool gốc user) → chờ `.page-protected-shell.is-loaded` + img
    `data-imgx-rendered="1"` (≤25s) → đọc cỡ thật W×H từ `data-imgx-width/height` **SAU khi vẽ** (HTML
    HTTP ghi SAI: 960x1440 vs thật 1116x1584) → nới `.reader-pages` = W px (+viewport W+200; ép từng
    `.page-frame` KHÔNG ăn) → ẩn mọi fixed/sticky ngoài khối trang → chụp shell → `_encode`: cỡ lệch
    ≤2px (cắt về W×H — chụp hay dư 1px cao), không `uniform_frame`, WebP **q90** (user chốt 30/09;
    PNG ~1.3MB → ~260KB, lệch TB 0.54/255; là lần mã hoá ĐẦU, không phải nén lại) giải mã được → ghi
    `.tmp` rồi `os.replace`. Trùng hệt trang trước → thử lại 1 lần rồi vẫn lưu + cảnh báo. Hụt 2 lần →
    để trống (lượt sau bù); **5 trang LIỀN hụt → `Blocked`** (site đổi/bật capture-guard/cần đăng
    nhập-18+). Số card trình duyệt ≠ HTML hoặc không mở được chương → bỏ chương; 3 chương liền →
    `Blocked`. Chromium chết giữa chương → `goto` lại (tự dựng lại). **Đo thực (30/09, Dragon Quest
    Emblem Of Roto ch.1)**: nới khung SAU khi vẽ = y hệt nới trước (lệch 0/255); chụp ở bố cục mặc định
    (~955px) mất nét thấy rõ (lưới chấm bệt, lệch 6/255) → bắt buộc nới; 72/72 trang đúng cỡ gốc (1116×
    1584 ×70, 1200×626, 1224×868), 94s cả chương (~1.2s/trang), 17MB; chụp lại 1 trang ra y hệt byte
    điểm ảnh (ổn định); chạy lại `.done` 1s không mở Chromium; xoá 3 trang → chỉ chụp bù 3 (12s).
    Số chương = số thật (`data-chapter-number`) → KHÔNG hậu tố, ghép `into:` được. `check_library` báo
    NHẦM "trang tráo ô" trên trang gần trắng (bộ dò comix) — bỏ qua.
    **Provider ONE-SHOT 18+ (01/10/2026): NHentaiToProvider (`name="nhentai"`, `nhentai.to`) +
    HentaiFCProvider (`name="hentaifc"`, `hentaifc.com`)** — HTTP trần, không Chromium, referer=None (CDN
    đã thử có/không). Mỗi link = 1 cuốn trọn → folder = `_short_title(tên ngắn, ≤100 ký tự cắt ở ranh giới
    từ) + " [nh{id}]"/" [fc{id}]"` (user chốt: tên ngắn trùng giữa bản dịch/nhóm → mã giữ 1 cuốn 1 folder;
    tên đầy đủ ~110 ký tự dễ vượt MAX_PATH) + `positional_numbers=True` (số chương không phải số thật →
    CLI chặn `into:`). 18+ để CHUNG thư viện (user chốt, không tách). **nhentai.to**: chỉ 1 request trang
    `/g/{id}/` — khối JS `new N.gallery({...})` (KHÔNG phải JSON hợp lệ: phẩy treo → regex từng trường):
    `media_id`, `title.pretty|english|japanese`, `num_pages`, `images.pages` **2 dạng**: gallery cũ = MẢNG
    (phần tử 0 = trang 1), gallery mới = DICT key LỆCH +1 ("2".."43" cho 42 trang; `43.webp` 404) → gom
    theo thứ tự (dict sắp theo key số) lấy phần tử i-1, đúng cả 2 dạng; lệch `num_pages` → dự phòng đuôi
    từ thumbnail `{n}t.{ext}`. id URL ≠ `"id"` JSON (id nội bộ) → dùng id URL. Ảnh `{cdn}/galleries/
    {media_id}/{n}.{w→webp|j→jpg|p→png|g→gif}`, host CDN đọc từ HTML (hiện `supercdn.site`), bìa
    `cover.{t}` 350px. CF có mặt nhưng không challenge GET. KHÔNG nhận nhentai.net (site khác).
    **hentaifc**: nginx trần không CF. Trang gallery `/e/{id}` → tên `<h1 class="heading">` + bìa =
    thumbnail ĐẦU khối `.thumbs` (`s3…/0.jpg`, bytes WebP 400px; khối "Same Artist" là bìa cuốn khác).
    Trang đọc `/e/{id}/c{N}` → dropdown `chapter_select` (`<option value="cN">`) ∪ link `/c{N}` trang
    gallery = danh sách chương; ảnh = `var ytaw=['104 116 …']` (mã ký tự cách dấu cách → URL
    `s2.hentaifc.com/token/<token>/{i}.jpg`, JPEG ~1100px), đối chiếu `var num_page`. Số chương c{N} →
    N+1 (c0 = Chapter 1); nhãn khác "Chapter N" → tên chương. URL có token (nghi có hạn, đo thực thấy
    ổn định ≥1h) → HTML trang đọc chỉ dùng lại trong `READER_TTL`=300s (one-shot: list_chapters tải 1
    lần, chapter_images dùng lại). 7/7 gallery đo 01/10 đều 1 chương c0. **Đo thực (01/10)**: tải
    nh218300 (23 JPEG, mảng), nh624421 (42 WebP, dict lệch), fc89351 (5 JPEG) → 73/73 ảnh `ok`, chạy lại
    `.done` bỏ qua, `--dest-name` bị chặn exit 1.
    **HentaiVNXProvider (`name="hentaivnx"`, `hentaivnx.com`, 01/10/2026)** — 18+ tiếng Việt, giao diện họ
    NetTruyen, CF không challenge GET → HTTP trần, referer=None (đã thử). Trang bộ `/truyen-hentai/{slug}-
    {idBộ}` có ĐỦ list chương; link chương `/truyen-hentai/{slug}/chapter-N/{idChương}` — slug chương = slug
    bộ BỎ `-{idBộ}` → lọc theo đó; link chương dán vào → breadcrumb trang chương ra idBộ. Trang bộ cache
    ~4h (`max-age=14400`) → chương mới có thể trễ. Ảnh: `var cdn1..cdn4='[json]'`; **chọn cdn1**
    (`sv{3,4,5}.2tcdn.cfd`, site tự lưu, 1..N, không token, = ảnh hiển thị mặc định; 18/18 mẫu có) — cdn3/4
    (`all.2tcdn.cfd`) có lúc lẫn ảnh LẠC bộ khác (`00.jpg`, lệch ±1), cdn2 = proxy duckduckgo (bộ cũ) hoặc
    dải liền 729×21250 token ~1 ngày (bộ mới; cdn1 = cùng dải cắt lát 729×5000, trang 20 so byte y hệt
    nguồn gốc). Dự phòng thứ tự cdn1→3→4→2; URL duckduckgo `/iu/?u=` → lấy URL gốc (core suy đuôi file
    từ path, `/iu/` ra tên rác); hậu tố `-----NN` (JS ghép ngang) → cắt + cảnh báo (0 ca trong 18 mẫu).
    Số chương = số site (`chapter-N`, lẻ `N-5`/`N.5`; one-shot cũ `chapter-0`) → không hậu tố, `into:` được.
    Bật **`png_to_webp`** (móc core, xem dưới). **Đo thực (01/10)**: Trò Chơi Mạo Hiểm ch.148 22 lát PNG
    (~75MB ước từ 3 lát 2.95–3.95MB; CDN chunked không có Content-Length) → 22 `.webp` 8.1MB `ok`, 29s;
    xoá 2 trang + `.done` → chỉ tải bù 2; ch.1-2 WebP 384px giữ nguyên; one-shot JPEG 36 trang giữ `.jpg`.
    **Mirror + ảnh đệm (08/10/2026)**: `domains` thêm `hentaivnx1.com` + `hentaivn.college` — CÙNG backend
    (cùng idBộ/idChương, `cdn1..cdn4` so JSON y hệt, CDN `sv3.2tcdn.cfd`), chỉ nhận link, vẫn tải qua BASE
    `www.hentaivnx.com` → cùng folder dù dán từ domain nào (watchlist so URL chuỗi → cùng bộ 2 domain = 2
    mục, vô hại). Domain TRẦN `hentaivn.college` bị nhà mạng chặn (cùng IP CF với www, timeout cả http/
    https) → đổi BASE sang mirror này phải giữ `www.`. Bật `drop_spacers`: bộ "Vì Nàng Bellumia" có JPEG
    900×1 916B ở ch.0 trang 9 + ch.2/3 trang 1 (10 chương mới nhất trang chủ sạch). cdn2 nay có thể là
    `cdn.sayhentai.cx` (không token). **Đo thực PC (08/10)**: tải bằng link college 3 chương 71 trang →
    3 marker `.spacer` đúng chỗ, `.done` cả 3; xoá `.done` → "đã đủ"; xoá thêm 1 trang → chỉ bù trang đó;
    link chương domain trần → về đúng bộ; `check_updates.check_one` college/x1 `ok`, link sai `error`.
    **Móc `png_to_webp` (core, 01/10/2026)**: provider khai `png_to_webp = True` → `run()` đổi đích trang
    URL `.png` thành `NNN.webp`, `download_image(..., to_webp=True)` sau KHI ảnh qua tầng 1+2 gọi
    `png_to_webp(data)`: chỉ khi bytes thật là PNG, cạnh ≤ `WEBP_MAX_DIM`=16383 (giới hạn WebP), trong
    `_gate.strict()` + breadcrumb `_decoding`; RGBA chỉ giữ alpha khi có điểm không đục; WebP
    `WEBP_TRANSCODE_Q`=90 method 4 (như moetruyen) rồi kiểm lại giải mã. Hụt bất kỳ điều kiện → ghi
    NGUYÊN bytes gốc (lệch đuôi `.webp` chứa PNG/JPEG — chấp nhận như tiền lệ ZetTruyen). VÌ SAO mã hoá
    lúc tải chứ không chạy `convert_webp.py` sau: core/`check_library` nhận trang theo TÊN FILE chính xác
    (`NNN.png`) → đổi đuôi sau khi tải = bị coi là thiếu trang, `--recheck` tải lại. Đo q90 trên lát 729×
    5000: 3.7MB→0.55MB (~15%), lệch TB ~1.4/255 (cao hơn moetruyen 0.54 vì PNG nguồn vốn nhiễu nén),
    0.6–1.3s/lát (chạy trong pool). Provider không bật → đường cũ y nguyên (hồi quy hentaifc).
    **LXMangaProvider (`name="lxmanga"`, `lxmanga.org`, 01/10/2026)** — 18+ tiếng Việt, WordPress theme
    riêng. ⚠️ **NHÀ MẠNG CHẶN SNI** (PC Viettel: DNS đúng IP Cloudflare nhưng bắt tay TLS bị cắt khi SNI =
    lxmanga.org; cùng IP SNI khác thì qua) → requests/curl KHÔNG BAO GIỜ tới. Chromium Playwright qua nhờ
    **ECH** (`/cdn-cgi/trace` → `sni=encrypted`, http/3) + tự qua CF managed challenge ~3s không cần tick
    (cf_clearance giữ trong profile `lx-profile`) → MỌI HTML qua `cf_browser`, KHÔNG thử HTTP (`fetch_mode`
    nào cũng dùng trình duyệt; `--fetch http` chỉ in nhắc). Pane browser của app Claude (Electron, UA
    `Claude/…`) bị LẶP challenge sau tick → đừng dùng nó thử site CF. Trang bộ `/{slug}.html`: HTML thô
    KHÔNG có list chương (JS nạp qua admin-ajax `baka_ajax`) → `goto` + chờ `ul.chapter-list li a` (25s) →
    `evaluate` đọc href+nhãn, title `h1.comic-title`, og:image (quan sát DOM, không tự gọi AJAX); mới nhất
    đứng đầu; bộ 263 chương ra đủ. Trang chương: HTML THÔ (`get_html`) có ảnh trong `<section id="viewer">`
    (`src`, "Server Gốc"); ảnh `cdn{1,2,3}.tymanga.com` KHÔNG bị chặn, không đòi Referer → core tải HTTP đa
    luồng (12/12 chương mẫu 4 bộ = cdn2); ảnh lỡ nằm trên lxmanga.org → bỏ + cảnh báo; lẫn PNG →
    `png_to_webp`. Bìa `.avif` trên lxmanga.org (bị chặn) → qua `i0.wp.com/<host><path>?ssl=1` = chính
    "Server CDN 1-3" của site (JS `chuyenServerImg`), trả JPEG → `cover.avif` chứa JPEG (reader `cover_jpeg`
    mã hoá lại theo nội dung → hiển thị đúng). **Số chương**: nhãn tự do → số từ nhãn (`Chap|Chương|Phần|
    Tập|C N`) rồi slug (`chap-N`, `cN`, `chap-N-M`→N.M); đủ số + trùng ≤ n/20 → SỐ THẬT (trùng lẻ tẻ giữ bản
    mới), không hậu tố, `into:` được; còn lại (thiếu số / trùng nhiều = TUYỂN TẬP, vd "Sex Tu Tiên Tổng
    Hợp", "[series] …", "Chap X Phần Y") → SỐ VỊ TRÍ (cũ nhất = 1) + nhãn làm tên chương + folder hậu tố
    `SUFFIX=" [LX]"` (không trộn folder nguồn số thật); 1 chương → số đọc được hoặc 1, không hậu tố. Nhãn
    do SITE cắt cụt ~23 ký tự (không có bản đầy đủ trong thẻ) — vẫn dùng vì ổn định + còn dấu. Chương
    nhãn có chữ **Raw** → BỎ QUA (bản dịch sẽ thay vào; tải raw thì `.done` chặn bản dịch); số vị trí vẫn
    tính cả raw. `allow_browser=False` (check_updates) → ném `Challenged` NGAY → status `browser` →
    supervisor vẫn xếp job tải mỗi lượt (như comix). Bộ không đọc được list / chương mất `#viewer` → lưu
    HTML `.reader-meta/lx-debug/`, 3 chương liền → `Blocked`. **Đo thực PC (01/10)**: Slave Wife ch.1 20
    JPEG 26s; Sex Tu Tiên ch.3 (`Chapter 3 - Dâm Nữ Đạo Chap 1`) 46 ảnh 36s; [series] ch.1 40 ảnh (1 PNG →
    WebP) 44s; tất cả `ok`; chạy lại `.done` 22s (chỉ mở Chromium đọc list). **CHƯA thử trên server** (mạng/
    IP/Chromium có thể khác).
    **HentaiVNRealProvider (`name="hentaivnreal"`, `hentaivnreal.com`, 08/10/2026)** — 18+ tiếng Việt
    ("HentaiVN Chính Chủ"), React Router v7 SSR; Cloudflare chỉ CACHE (trang bộ `s-maxage=1800`+swr 600,
    trang chương 3600 → chương mới trễ ≤~40'), không challenge GET → HTTP trần, referer=None (CDN đã thử
    có/không/lạ), `png_to_webp` bật phòng hờ (chưa gặp PNG; JPEG/WebP, manhwa dải dọc tới ~720×13870).
    Dữ liệu = `loaderData` TURBO-STREAM nhúng trong HTML (`streamController.enqueue("<chuỗi JSON>")`) →
    hàm module `_rr_loader_data` (giải mảng phẳng: object `{"_k":v}` = chỉ số khoá/giá trị, số âm = hằng
    -5 null/-7 undefined, mảng có phần tử đầu là CHUỖI = giá trị gắn tag như `SingleFetchClassInstance`
    (ObjectId) → None) + `_rr_route(data, trường)` chọn route theo TRƯỜNG ("chapters"/"pages", bỏ
    "root") chứ không theo id route. Trang bộ `/truyen/{slug}` → `story.title`, `cover`,
    `chapters[{slug,title,date}]` (ĐỦ, mới nhất trước); trang chương → `pages` (dự phòng `<img src
    data-idx>`). ⚠️ `Content-Type: text/html` KHÔNG charset → `get_text(..., encoding="utf-8")`.
    **Số chương THEO NHÃN, KHÔNG theo slug** (slug sai: `chap-12`="Chap 1.2", `chap-106`="Chương 104",
    `1chuong-685`="68.5", `103`; slug có `đ` → requests tự %-encode): regex nhãn như lxmanga + nhãn chỉ là
    số. Trùng ≤ max(1,n/20) + thiếu số ≤ max(2,n/10) và là thiểu số → SỐ THẬT, không hậu tố, `into:` được;
    trùng giữ bản mới (Sextoy "Chương 13" ×2 = cùng nội dung khác banner); chương không số lẻ tẻ = chương
    có số liền trước (cũ hơn) + 0.5 (liền nhau +0.6…+0.9, số trống đầu tiên; hết → bỏ + cảnh báo), nhãn làm
    tên chương (user chốt 08/10: vài chương lạ KHÔNG được lật cả bộ sang số vị trí → đổi folder → tải lại
    cả bộ — KHÁC lxmanga). Còn lại = TUYỂN TẬP ("Truyện của Rayasi" 20/43 nhãn tự do) → SỐ VỊ TRÍ + nhãn +
    hậu tố `SUFFIX=" [HVR]"`; 1 chương → số đọc được hoặc 1. Folder = `_short_title(story.title)`, KHÔNG
    gắn mã kể cả one-shot (user chốt 08/10, như hentaivnx). **Đo thực PC (08/10)**: oneshot 26 JPEG 19s;
    Sextoy ch.13 (bản mới `chuong-13-2`)/68.5/104 (slug `chap-106`) 48 ảnh; Anh em nhà nghèo ch.1.2;
    Rayasi ch.16 (`Chapter 16 - đời hư áo đưa em vào cơn phê`, slug có `đ`) — tất cả `ok`; chạy lại `.done`
    bỏ qua; `check_updates.check_one` ra `ok`/listed_max đúng, link 404 → `error`. CHƯA thử trên server.
    **HitomiProvider (`name="hitomi"`, `hitomi.la`, 08/10/2026)** — gallery 18+ đa ngôn ngữ, ONE-SHOT như
    nhentai (1 Chapter số 1, `positional_numbers`, folder `_short_title(title) + " [hi{id}]"`; title dạng
    "Romaji | English" GIỮ cả 2 phần, `\s*|\s*` → ` - ` — user chốt 08/10). nginx trần, không CF, nhà mạng
    không chặn → HTTP trần. Trang hitomi.la = VỎ SPA; dữ liệu ở `ltn.<CDN>` — host đọc từ `<script
    src="//ltn.X/gg.js">` của vỏ trang chủ (1 request/tiến trình; hằng `CDN="gold-usergeneratedcontent.net"`
    chỉ dự phòng, site đã đổi CDN 1 lần từ *.hitomi.la). Info `{LTN}/galleries/{id}.js` = `var galleryinfo =
    {json}` (raw_decode): `title`/`japanese_title`, `type` (`anime` = video → list rỗng + báo), `files[{hash,
    width,height,hasavif}]` đúng thứ tự trang (KHÔNG còn trường `haswebp`; reader site luôn dùng webp làm src).
    URL ảnh dựng y `common.js`: g = int(h[-1]+h[-3:-1],16) → `https://w{1+m(g)}.<CDN>/{b}{g}/{h}.webp`;
    `m`/mặc định/`b` parse từ `{LTN}/gg.js` (`case N:`… `o = K; break;`, `var o = K`, `b: '<ts>/'`; kiểm luôn
    `s(h)` còn dạng `(..)(.)$` + `m[2]+m[1]` — đổi định dạng → báo to, trả rỗng, KHÔNG đoán). ⚠️ THIẾU
    Referer `https://hitomi.la/` → 404 (sai subdomain/sai b cũng 404) → `referer` khai trên provider.
    ⚠️ `b` = mốc sinh gg.js, site sinh lại mỗi giờ (:00 GMT; `max-age=3600`; JS site tải lại mỗi 30') →
    gg.js cache `GG_TTL`=120s (đủ dùng chung cover_url + chapter_images của 1 cuốn). **Đo lúc xoay
    04:00 GMT 08/10**: URL b cũ vẫn 200 ngay sau và 5' sau (≥65' kể từ lúc cấp) → cuốn đang tải dở qua mốc
    :00 KHÔNG hỏng; NHƯNG server kiểm subdomain theo bảng CỦA b đó (b cũ + bảng mới: 18/30 trang 200, 12/30
    404 — đúng 12 trang tải được bằng subdomain đảo) → mỗi URL phải dựng từ TRỌN 1 bản gg.js (`_gg()` trả
    cả cặp m/b), không bao giờ trộn.
    WebP = đủ độ phân giải gốc (site không còn phục vụ jpg/png gốc); AVIF nhẹ ~50% nhưng chọn WebP (đồng bộ
    thư viện/iOS — user chốt). Bìa = thumbnail trang đầu `https://{chr(97+m(g))}tn.<CDN>/webpbigtn/{h[-1]}/
    {h[-3:-1]}/{h}.webp` (640px). Link nhận `/{loại}/{tên}-{lang}-{id}.html`, `/galleries/{id}.html`,
    `/reader/{id}.html#n`, số trần; trang `-all.html` (artist/tag/series) → báo "không phải 1 cuốn", không
    gọi mạng. Bản dịch khác của cùng tác phẩm (`languages[]`) KHÔNG xử lý — mỗi bản 1 link (user chốt).
    **Đo thực PC (08/10)**: hi4238970 30/30 WebP 2040×2880 (khớp `width/height` galleryinfo từng trang) +
    bìa, ~40MB; chạy lại `.done` bỏ qua; `--dest-name` chặn; link artist/gallery 404 → exit 1 có lý do;
    `check_updates.check_one` → `ok` listed_max 1 / `error`. CHƯA thử trên server.
    **PhapBiProvider (`name="phapbi"`, `truyentranhphapbi.blogspot.com` + `truyentranhphapbi.com`,
    08/10/2026)** — blog Blogger 1 người dịch (truyện Pháp-Bỉ + manga màu), 579 bài/43 nhãn. Google phục vụ,
    không CF, UTF-8 chuẩn → HTTP trần, `referer=None`. `www.truyentranhphapbi.com` (link cũ) 301 về blogspot;
    domain trần lỗi TLS. **1 bài = 1 tập**; site KHÔNG có "bộ": nhãn lẫn thể loại (`GENRE_LABELS`: Manga,
    Classic, Magic, Tổng hợp, New, Anh-Pháp, Truyện lẻ, Ly kỳ, Sci-fi) và 1 nhãn chứa nhiều bộ con.
    GOM BỘ (user chốt 08/10) = bài thuộc các nhãn KHÔNG-thể-loại của bài neo (GỘP feed các nhãn đó — Lucky
    Luke 41 mang Lucky Luke + Rantanplan) có cùng `_stem` (tên trước "Tập N", bỏ dấu + (Preview)/(truyện
    màu)/"màu"/full color + `_ALIASES` doraemon≡doremon, bảy/7 viên ngọc rồng≡dragon ball, siayan≡saiyan +
    BỎ khoảng trắng: "RAN TAN PLAN"). Tiêu đề "TÊN ALBUM (TẬP N)" (Tintin 23, Asterix…) → stem None = bộ
    chính của nhãn (`_main_stem` = stem có số phổ biến nhất). Mô phỏng offline cả 579 bài: 115 bộ.
    Feed `/feeds/posts/summary/-/<Nhãn>?alt=json&max-results=150&start-index=` — ⚠️ nhãn phân biệt hoa
    thường (lấy chuỗi đúng từ `span.post-labels` bài neo); ⚠️ số entry/trang THẤT THƯỜNG (19–66 dù xin
    150) → lặp `start-index += len(entry)` tới `openSearch$totalResults`, thiếu → cảnh báo; ⚠️ `content`
    feed chỉ tới jump break → ảnh PHẢI đọc HTML bài. SỐ từ tiêu đề (slug URL cắt/sai): "Tập N"/"Chương N";
    "Tập 2-3" = 2 (tên chương "Tập 2-3"); "Tập cuối" = max+1; trùng → bài MỚI nhất giữ N, cũ hơn N.1, N.2…
    (user chốt; 1 ca: Doremon dài Tập 9 Tây Du Ký → 9.1); bài không số lẫn bộ có số → 0.1…; bộ toàn bài không
    số → số vị trí theo ngày đăng. PREVIEW (~23%, bản đủ tác giả BÁN qua Drive — không tìm đường lấy): VẪN
    tải phần công khai, tên chương + " (preview)" (user chốt). ⚠️ `check_updates` so theo SỐ → chương preview
    đã `.done` chặn việc tự lấy bản đủ khi tác giả đăng lại → hướng dẫn user xoá folder "(preview)".
    Ảnh = khung đọc ĐẦU TIÊN trong `post-body` (`_BloggerPostImages`, HTMLParser có đếm độ sâu): 3 thế hệ
    template `div.overlay-data` (2017+) / `div#image-container` (~2015–17) / `div.read` (2013–18) + ảnh
    TRƯỚC `<a name="more">` (bìa = trang 1, không lặp trong khung) chèn đầu; ảnh sau khung ("Một vài thông tin
    chú thích", wikimedia) BỎ; không thấy khung → mọi ảnh sau "more" + cảnh báo. URL `/sNNN/` hoặc `=sNNN|wNNN`
    → `s0` = gốc (rộng 1300); `/img/a/…` không có tên file → gắn `#.jpg` cho core đặt đuôi (requests gửi
    `path_url`, KHÔNG gửi fragment — đã thử 200 image/jpeg). Trang cắt 2 NỬA `_01/_02` → giữ nguyên (user
    chốt). Folder = tên nhãn nếu `_stem(nhãn)` = stem bộ, không thì `_display(prefix)` của tập số nhỏ nhất
    (bỏ cụm màu, IN HOA → Title). Link nhận: bài `/YYYY/MM/<slug>.html` (`?m=1`, domain .com), nhãn
    `/search/label/<Nhãn>` (slug `label/<Nhãn>`). Cache trong instance: `_series`, `_feeds` (theo nhãn),
    `_pages` (3 HTML gần nhất — bài neo dùng lại khi tải). **Đo thực PC (08/10)**: Doremon 1 → 18 tập
    (1–17 + 9.1, 9 preview) 4.7s; Tintin 23/link nhãn → `Tintin` 20 tập; DB Mabu 7 → 8 tập (tập cuối = 8;
    TRƯỚC khi có luật hồi bên dưới);
    Lucky Luke 41 → `Lucky Luke` 75 tập; 11 HTML mẫu 2013–2026 tách ảnh đúng (preview khớp "Preview X/Y");
    tải Tintin 17 preview 13/13 JPEG vào `Chapter 17 - … (preview)`; `check_one` → `ok` 20 tập. CHƯA thử
    trên server.
    **Bộ CHIA HỒI (08/10 tối, user chốt)** — Dragon Ball: nhãn `Dragon Ball` 41 bài = 6 hồi (Tuổi thơ 9,
    Piccolo 7, Saiyan 4, Frieza 5, Cell/Android 8, Mabu 8), MỖI HỒI đánh lại Tập 1 → luật cũ ra 6 bộ, `into:`
    cũng không gộp được (trùng số). `_ARC` bắt "<BỘ> - hồi <X>" / "<BỘ> (HỒI X) MÀU" trong phần trước "Tập N" →
    stem = phần trước "hồi" (alias bảy/7 viên ngọc rồng ≡ dragon ball) → 1 bộ; `_numbered` đánh số TỪNG hồi
    bằng `_number_pairs` (luật cũ: cuối = max+1, trùng N.1…) rồi cộng offset = tổng số nguyên lớn nhất các hồi
    trước; thứ tự hồi = ngày đăng tập ĐẦU của hồi (khớp thứ tự truyện + mục lục tác giả). Tên chương "Hồi
    <X> - Tập N[ - phụ đề]", X = dạng viết thường phổ biến nhất (toàn IN HOA → Title: FRIEZA → Frieza).
    Số liên tục (không dùng khối 101…: user chốt) → rủi ro lệch nếu tác giả chèn tập vào hồi giữa (bộ đã trọn
    42 tập gốc). KHÔNG dùng số tập gốc trong tên file ảnh (v01–v42): Frieza 5 bài/8 tập gốc, Mabu 6+7 cùng v41.
    Mục lục "trọn bộ" trong bài do tác giả soạn tay, đã cũ (Mabu thiếu Tập cuối) → KHÔNG làm nguồn danh sách.
    Dragon Ball Super = nhãn RIÊNG (24 tập, còn ra) → folder riêng (user chốt). **Kiểm hồi quy** (mô phỏng
    offline 579 bài + 43 link nhãn, so trước/sau): chỉ 41 link Dragon Ball + link nhãn đổi (cũ 6 folder hồi →
    `Dragon Ball` 41 tập), mọi bộ khác y nguyên tên folder/số/tên chương; riêng link nhãn THỂ LOẠI `Manga`
    ("bộ chính" = bộ đông nhất) đổi từ Doremon Đại tuyển tập sang Dragon Ball — link vô nghĩa, không ai dùng.
    Thực: link Tuổi thơ 1 / Mabu 7 → `Dragon Ball` 41 tập (16 preview); DBS → `Dragon Ball Super` 24; tải
    Chapter 11 → `Chapter 11 - Hồi Piccolo - Tập 2 (preview)` 45/45. Folder hồi cũ (vd 9 tập Tuổi thơ) KHÔNG
    được nhận lại (core khớp folder chương theo tên đầy đủ) → xoá rồi tải lại.
  - `cf_browser.py` — **tầng TRÌNH DUYỆT THẬT dùng chung cho site sau Cloudflare** (28/09/2026;
    dùng bởi qqcomvn [lấy HTML] + moetruyen [chụp trang] + lxmanga [HTML + DOM list chương, LUÔN dùng
    vì nhà mạng chặn HTTP]). `CFBrowser(profile, host, label,
    extra_hosts=(), block_types=ảnh/media/font)`: `open()`/`get_html(url)`/`goto(url)`/`close()`.
    30/09: `get_html` + `goto` chung 1 đường `_load(url, want_html)` (goto để trang mở trên `self.page`
    cho provider thao tác DOM, trả True/False-404); `extra_hosts` = host ngoài site được tải (khớp cả
    subdomain), `block_types` = loại bị chặn trên host site — mặc định giữ nguyên hành vi cũ của qqcomvn.
    CHÉP (không refactor) công thức comix đã chạy thật trên server: Chromium trong
    `.reader-meta/pw-browsers` + playwright 1.55 (chung bản cài → comix "tập dượt" tầng này mỗi
    ngày), HEADFUL + `--disable-blink-features=AutomationControlled` + bỏ `--enable-automation`,
    `_Watchdog` 90s quanh mở+PROBE `evaluate('()=>1')`, `kill_profile_chrome` (match TÊN profile →
    không đụng comix/Chrome thường) trước khi mở, tự dựng lại ≤`MAX_RELAUNCH=3`/đợt. Profile riêng
    `<site>-profile` (qqcomvn: `qqvn-profile`) giữ cookie `cf_clearance`. Route: host site mở trừ
    image/media/font; ngoài site chỉ `*.cloudflare.com` (iframe Turnstile). `get_html`: van
    `core.gate` → goto → challenge (header `cf-mitigated` hoặc title) → `_wait_pass`: pha 1 im lặng
    `AUTO_PASS_WAIT=20s` (challenge JS/managed thường tự qua) → pha 2 Telegram "cần tick" (chung
    `notify-config.json`, chống spam `NOTIFY_GAP`) + chờ `HUMAN_WAIT=15'`, in log mỗi `HEARTBEAT=60s`
    (stall-watchdog 20' không giết oan), nhắc lại giữa chừng → qua thì goto LẠI lấy response sạch
    (`response.text()` = HTML thô y như HTTP → CHUNG parser); hết giờ → `core.Challenged` (dừng
    sạch, exit 2). **Mỗi URL chỉ chờ NGƯỜI 1 lần**: vừa tick mà CF chặn lại ngay (nghi CF chặn cả
    trình duyệt tự động) → chỉ chờ tự qua rồi dừng, không giữ hàng đợi cả giờ. 404/410 → None.
    `BrowserGone(Blocked)` → core dừng sạch. **KHÔNG BAO GIỜ tự bấm ô "Verify you are human".**
  - `comic_downloader.py` — CLI mỏng: `resolve_provider()` tự nhận site theo domain
    của URL (hoặc cờ `--site`), rồi gọi qua `dispatch()`: provider thường → `core.run`;
    provider có `custom_run` (hiện chỉ comix) → loop riêng. Cờ giữ y hệt bản cũ
    (`--from/--to/--chapters/--cbz/--pack/--out/--workers/--delay`). `dispatch()` (28/09): chặn
    `--dest-name` với provider `positional_numbers` (exit 1 + lý do — bot preview `into:` hiện
    500 ký tự cuối nên người dùng thấy); `--fetch` gán `provider.fetch_mode`; `finally` gọi
    `provider.close()` (đóng Chromium tầng trình duyệt kể cả khi exit/lỗi).
  - `comix_site.py` — **loop tải RIÊNG cho comix.to (Comick)**, KHÔNG đi qua
    `core.run()` nhưng tái dùng gân cốt core (PoliteGate, `download_image` + kiểm ảnh
    4 tầng, `make_cbz`, `safe_name`, `append_log`). Vì sao riêng: API mã hóa
    `{"e":...}` + token ký per-request (`secure-*.js` đổi theo build) → phải mở
    Chromium thật (Playwright HEADFUL, dep tùy chọn import lười) cho JS site tự gọi
    API rồi **hook `JSON.parse`** bắt payload đã giải mã; và 1 chương có NHIỀU bản
    upload (Official/scan) cần chọn + upgrade — không nhét vừa hợp đồng provider.
    Chỉ browser lo metadata; ảnh tải bằng HTTP client RIÊNG `ComixImageClient`
    (KHÔNG dùng `core.session` chung — xem "Danh tính tách đôi" ở Quyết định): giả
    vân tay TLS Chrome (`curl_cffi` impersonate, thiếu thì lùi về `requests`) + MƯỢN
    cf_clearance/UA thật từ browser đang sống; refresh vé ở MAIN THREAD (đầu mỗi
    chương + khi 403); 403 chỉ gắn cookie cho host `*.comix.to`, wowpic không cần.
    URL ảnh `*.wowpicN.store` KHÔNG có đuôi file → tải xong sniff magic bytes đổi đuôi.
    Luật chọn per chương: `isOfficial` trước → hết official mới tới scan CÓ tên nhóm
    (`id`/chapterId lớn nhất = mới nhất trước) → hết bản có nhóm mới tới scan KHÔNG nhóm
    (id lớn nhất trước). id tăng đơn điệu = độ mới (API không có timestamp thô, chỉ
    "2mos ago"). GIỮA các bản official (1 chương có thể có nhiều official song song khác
    nền tảng/typeset — vd Solo Leveling ch.0 có 7: Webcomic/Tapas/Manta/Yen Press/
    TappyToon/…) xếp theo `OFFICIAL_GROUP_RANK` (số nhỏ = ưu tiên cao: TappyToon 0 …
    Webcomic 99; nhóm lạ = hạng giữa `OFFICIAL_DEFAULT_RANK`), cùng hạng thì id mới nhất
    trước — KHÔNG chọn thuần theo độ mới nữa vì bản re-up mới nhất (Webcomic) thường kém
    bản dịch official tốt (TappyToon); sửa thứ tự chỉ cần sửa dict `OFFICIAL_GROUP_RANK`
    (user chốt 21/08). Ở nhóm SCAN thì ưu tiên NHÓM hơn độ mới vì bản "no group" hay là
    raw/batch đè lên bản nhóm scan cũ hơn nhưng chỉn chu hơn (vd Dai ch.345-349); cả số
    chương chỉ có bản không nhóm thì vẫn tải, không bỏ (user chốt 19/08). Xem
    `candidates_for()`.
    **GHIM NHÓM (02/09/2026)** — `--group NHÓM` (bot `/tai <link> [chương] NHÓM`; token
    chữ trong lệnh = nhóm, token số = chương; nhiều token chữ nối dấu cách → "Yen Press"):
    `resolve_pin()` đổi tên gõ → tên chuẩn trên site (chuẩn hoá `_norm_group`: bỏ hoa/
    thường/khoảng trắng/ký tự lạ; khớp đúng trước, không có thì chuỗi con DUY NHẤT; sai/mơ
    hồ → `exit 1` kèm danh sách nhóm có trên bộ — dòng log cuối = tin ❌ của bot).
    `candidates_for(versions, pin)` chỉ trả bản của nhóm đó (id mới nhất trước), KHÔNG rơi
    về nhóm khác. Ghim BỀN theo chương: sidecar ghi `"pin"`; `_effective_pin()` = ghim của
    lệnh > ghim sidecar > None, nên lượt sau không ghim (kể cả auto-check hằng ngày) vẫn
    coi chương đó ghim nhóm ấy → KHÔNG thay lại bằng Official (nếu không bền, auto-check
    đêm sau thay lại Tapas, công ghim mất). `--group auto` = xoá `pin` sidecar rồi luật mặc
    định ngay lượt đó. QUYẾT ĐỊNH 1 chương gom về `_chapter_plan(folder, cands, side, done,
    pin)` → `have`/`replace`/`fetch`/`nopin`, dùng CHUNG cho vòng lặp `run()` và báo cáo sớm
    `_report_comix_plan()` (trước đây 2 nơi chép tay cùng luật, dễ lệch). Ghim đè cả 2 luật
    "Official trên đĩa = skip vĩnh viễn" và "không thay scan→scan": đĩa có bản khác → `replace`
    qua đường tráo folder sẵn có. Bot: job có trường `group` (khoá dedup
    `(url, chapters, repair, group)`, nhãn `[Nhóm]`, nối `--group`); `_load_jobs` nay khôi
    phục đủ `repair` + `group` (trước rơi `repair` → job vá dở qua restart thành job tải).
    Upgrade→Official: điều kiện `has_content AND not on_disk_official AND
    best.isOfficial` — "chưa phải official" GỒM cả chương tải từ SITE KHÁC (folder có
    ảnh + `.done` nhưng KHÔNG có sidecar `.source.json`; sidecar chỉ do comix tạo),
    khớp theo SỐ chương (sự cố Dungeon Reset: 266 chương Raven chung folder từng bị
    skip vì thiếu sidecar). Tải bản mới vào `downloads/.comix-tmp/<Tên>/` (đầu-dấu-chấm
    → reader/check_library bỏ qua) rồi tráo bằng 2 lần rename (cũ→`.__trash`→xoá),
    crash giữa chừng vẫn còn 1 bản đọc được + đầu phiên sau tự dọn `.__trash`. Tên
    folder comix CỐ ĐỊNH "Chapter N" (không gắn title) để tráo không đổi tên folder →
    không mất bookmark/progress. Official đã tải = skip vĩnh viễn; KHÔNG thay scan→scan
    (kể cả bản comix mới hơn). **File dấu cấp truyện (Cách 1)**: cuối mỗi lần chạy ghi
    `_COMIX_official_{off}-{total}.txt` ở gốc folder (đếm official/scan/ngoài từ sidecar
    các chương; chỉ ghi khi comix đã đóng góp ≥1 chương) — file THƯỜNG (không dot) nên
    hiện trong Explorer, reader/check bỏ qua vì không phải ảnh; giúp user phân biệt
    folder comix với folder scan tải từ site khác để TỰ TAY xoá folder scan trùng
    (đã chốt: không tự khớp/gộp folder, chấp nhận duplicate khi 2 provider tên khác). Cloudflare challenge →
    nhắn Telegram (đọc `notify-config.json`) nhờ người tick trên màn hình server,
    chờ 5 phút. **3 bẫy môi trường đã gỡ (09/08/2026)**: chặn DLL dưới AppData →
    `PLAYWRIGHT_BROWSERS_PATH=.reader-meta/pw-browsers` (set trong module TRƯỚC import
    playwright + trong cap-nhat.bat lúc install); ghim `playwright==1.55.0` (bản 1.62
    kéo Chrome-for-Testing 151 lỗi side-by-side trên Win10); site check
    `navigator.webdriver` → bắt buộc `--disable-blink-features=AutomationControlled`
    + `ignore_default_args=["--enable-automation"]`, thiếu là JS site không boot
    (body rỗng, không gọi API). **Cửa sổ Chromium đóng giữa chừng → TỰ dựng lại (10/08)**:
    `alive()` (`page.is_closed`/`browser.is_connected`) phân biệt browser-chết (fatal) với
    điều-hướng-hụt (transient); `_goto`/`_pump` raise `BrowserGone`, `_resilient()` bọc mọi
    call fetch → chết thì `relaunch()` tại chỗ (cùng profile bền) rồi thử lại. Quá
    `MAX_RELAUNCH=3`/đợt hoặc `FAIL_STREAK_LIMIT=6` chương hụt LIÊN TIẾP (browser sống, nghi
    chặn IP mềm) → thoát ≠0 (supervisor báo "❌ Lỗi tải") thay vì nuốt lỗi thành "để sau" cả
    bộ rồi thoát 0 = "✅ Tải xong" giả. Streak reset khi tải được 1 chương.
    **Treo about:blank do PROFILE MỒ CÔI → tự dọn + watchdog (14/08/2026)**: profile bền
    `comix-profile` mà còn 1 Chromium mồ côi (từ lần treo/bị-kill trước) đang ôm → `launch_
    persistent_context` mở con MỚI, con mới thấy "đã có instance" → chuyển URL cho con cũ rồi
    TỰ THOÁT → Playwright mất kết nối → TREO vô hạn ở about:blank (chạy tay sau khi kill sạch
    chrome thì OK, chứng tỏ không phải lỗi site). Bộ dọn stray của supervisor chỉ chạy lúc KHỞI
    ĐỘNG (không per-job) nên mồ côi giữa phiên kẹt mọi job comix sau. Fix: `_kill_profile_chrome()`
    (kill chrome.exe match 'comix-profile' + xoá `Singleton*`/`lockfile`) chạy ở ĐẦU mỗi
    `run()` — an toàn vì comix 1 worker tuần tự, match theo profile nên không đụng Chrome
    thường. `_StartupWatchdog(90s)` bọc RIÊNG khâu launch (KHÔNG bọc goto có timeout 45s /
    chờ Cloudflare tối đa 5' vì đó là chờ NGƯỜI tick hợp lệ): quá giờ = kill Chromium +
    `os._exit(2)` (fail fast) → supervisor báo lỗi + chạy job kế thay vì treo câm 5+ phút.
    **Treo LẠI 17/08/2026 → chống-treo mở rộng (Cách B, 18/08/2026)**: bản 14/08 CHỈ bọc
    `launch_persistent_context`, còn treo 17/08 rơi vào các lệnh SAU launch (add_init_script/
    route/pages) + lần `ComixImageClient.refresh_identity` đầu — đều ngoài watchdog, không
    timeout đáng tin (triệu chứng: tab blank about:blank, kẹt ~5 tiếng, in tới "(Sẽ mở cửa sổ
    Chromium…)" rồi im). Sửa: (1) `_launch` bọc `_StartupWatchdog` QUANH CẢ mở + setup + thêm
    **PROBE `page.evaluate('()=>1')`** (renderer phải trả lời → bắt đúng ca wedge trong ≤90s);
    (2) bọc watchdog quanh `refresh_identity` đầu ở `ComixImageClient.__init__`; (3) watchdog
    đổi sang **Cách B**: nổ → `_kill_profile_chrome()` rồi CHỜ ÂN HẠN `LAUNCH_KILL_GRACE=8s`
    cho lệnh Playwright đang kẹt bật lỗi (chrome chết → CDP đứt → raise) → `_launch` bắt →
    ném `BrowserGone` → `_open_resilient` (mới) TỰ DỰNG LẠI trong phiên tối đa `MAX_RELAUNCH`
    lần (kill này dọn luôn orphan/lock nên lần dựng lại thường được); vẫn kẹt sau ân hạn →
    `os._exit(2)` (chốt chặn cứng). `_launch` giờ NÉM `BrowserGone` khi lỗi (thay vì lỗi thô);
    `relaunch()` mid-session cũng gọi `_kill_profile_chrome()` trước khi mở lại. Lưới bao chót
    cho MỌI kiểu treo khác = stall-watchdog ở supervisor (xem `supervisor.py`).
    **TRÁO Ô chống-scrape (bản Official) + giải-xáo (01/09/2026)**: payload trang có cờ
    `s` — `s:1` là trang bị **cắt lưới ô rồi xáo vị trí** (đo thực: đúng MỖI TRANG THỨ 10
    — 10,20,30…; xác minh 5 chương Farmer of Spirits). URL trả bytes XÁO cho mọi client
    (KHÔNG có URL sạch riêng); reader hiển thị sạch bằng cách dùng chunk `secure-*.js`
    (export `t` = hàm `vs`) tải ảnh rồi **giải-xáo VẼ LÊN `<canvas>`** (trang thường dùng
    `<img>`). `fetch_pages` nay trả `[{"url","s"}]`; trong `run()` trang thường tải HTTP như
    cũ, trang `s:1` đi `ComixSession.descramble_pages(url_path, pairs, img_client)`.
    **CÁCH GIẢI-XÁO — ghi bản đồ ô, KHÔNG đọc canvas** (chốt sau khi thử đọc canvas THẤT BẠI,
    xem dưới): `descramble_ops()` chạy `DESCRAMBLE_JS` (`page.evaluate`): `import(secureUrl)`
    (dò động qua Performance API → bền khi build đổi hash), ép `requestAnimationFrame` ĐỒNG BỘ,
    **chặn `CanvasRenderingContext2D.drawImage`** trong lúc gọi `vs(url).apply(canvas)` để GHI
    LẠI mọi lệnh vẽ (lưới ô: 1 lệnh nền + N lệnh chép ô `sx,sy,sw,sh→dx,dy,dw,dh`; vd trang
    940×1388 = 5×5 ô 188×277). ĐỒNG THỜI **tee `window.fetch`** để bắt ĐÚNG bytes ảnh xáo mà
    `vs` nhận (trả base64 kèm ops), rồi `_unscramble_ops()` xếp lại bằng PIL trên chính bytes
    đó (crop→(resize nếu khác cỡ)→paste theo thứ tự). **KHÔNG tải lại bằng `img_client`**: CDN
    trả BIẾN THỂ XÁO KHÁC theo client — cùng URL, browser nhận 116 798 B (sha 4f6d…) còn
    requests nhận 116 598 B (sha 4073…) → bản đồ ô lệch ảnh (đo p20 ch.1, 02/09; p10 trùng
    chỉ là may). Biến thể ổn định theo client (2 fetch no-store trùng hash). **Điều kiện bắt
    buộc**: `_route_filter` phải MỞ `*.wowpic*.store` cho resource type `fetch`/`xhr` (vẫn
    chặn `image` của thẻ `<img>` để không tốn băng thông) — vì `vs` phải tự tải ảnh trong
    browser thì `apply()` mới vẽ; filter cũ chặn hết → `descramble_ops` trả rỗng IM LẶNG =
    gốc lỗi "0 trang" của cả bản canvas 01/09 lẫn bản ops lần đầu (tái hiện được ở dev bằng
    chính `ComixSession`; mọi test trên Browser pane không có filter nên "chạy được" giả). **Vì sao KHÔNG toDataURL**: setup
    này (cả server lẫn dev) đọc pixel canvas ra RỖNG (114 bytes) dù màn hình thấy sạch — nghi
    chống-scrape chặn readback (reader chỉ hiển thị, không cần đọc lại); ghi tham số drawImage
    thì KHÔNG cần compositing/đọc canvas nên **chạy được cả khi server không màn hình / RDP
    ngắt**, và kiểm chứng offline được (đã dựng lại trang 10 ch.1 sạch bằng PIL). KHÔNG reverse
    permutation trong `secure.js` (obfuscate control-flow, dễ gãy) — chỉ QUAN SÁT drawImage.
    Lưu ý: bản xáo cũ trên đĩa có thể khác permutation hiện tại (token đổi theo thời gian) nên
    KHÔNG giải được từ file cũ → repair tải lại bytes mới rồi mới xếp. **Nghiệm thu "trang
    xáo đã xong chưa" = TÍN HIỆU THẬT, KHÔNG dùng detector** (sửa 02/09/2026): cổng cũ soi
    lại `looks_scrambled()` trên ảnh VỪA giải-xáo → detector DƯƠNG TÍNH GIẢ trên webtoon dải
    dài (rãnh giữa khung tranh rơi trúng lưới chia n∈{4,5,6,8,10} → điểm cao dù ảnh sạch: đo
    được 181 trang scan sạch Solo Leveling ≥4.0, cao nhất 42.2; Farmer of Spirits ch2 t10=8.09,
    ch3 t30=4.67 tuy ảnh liền mạch) → chương không bao giờ đóng `.done`, bot báo "thiếu trang
    10/30" mãi dù file có sẵn trên đĩa. Nay: trang `s:1` coi là XONG khi **giải-xáo lượt này
    trả ra bytes** (`got[i]`); trang `s:1` KHÔNG nằm trong danh sách cần giải-xáo (`scr_jobs`/
    `scr_pairs`) = đã sạch ở bước phát hiện. Đường tải (`_done_ok` trong `run()`) và `/repair`
    (`still` trong `_repair_scramble_chapter`) dùng chung nguyên tắc này → đóng `.done` đúng,
    giải-xáo HỤT (got không có bytes) vẫn bị bắt là "còn sót". `looks_scrambled()` nay CHỈ
    còn dùng ở audit `check_library` (báo, không quyết định gì).
    **Phát hiện trang xáo cũ = MỐC NGÀY GHI FILE, KHÔNG dùng detector** (sửa 27/09/2026):
    detector ÂM TÍNH GIẢ trên trang gần-trắng (credit TappyToon, "TO BE CONTINUED", trang tựa,
    bong bóng nền trắng: xáo mà chỉ ~2-3.9 điểm < ngưỡng 4.0) → `/repair` 02-03/09 bỏ sót 108
    trang/92 chương mà vẫn đóng `.done` (quét server 27/09 qua `/api/pages`, soi tay 97 trang:
    mọi trang có nét đều xáo thật). Hai phân bố chồng nhau (xáo-trắng ~2.4 / sạch-webtoon tới
    42) nên KHÔNG chỉnh ngưỡng được. Nay: `UNSCRAMBLE_SINCE` = **02/09/2026 12:45 (+07)** — trang
    ghi TRƯỚC mốc = bản xáo thô (code cũ không giải-xáo được); ghi SAU = đúng (chốt bằng bằng
    chứng: trang repair sớm nhất trên server 02/09 12:45:06, soi 9 trang đầu/giữa/cuối 3 đợt
    đều sạch, không trang nào ghi lại trước đó). Luật offline `repair_offline_state()` (DÙNG
    CHUNG cho job vá + quét toàn thư viện): chỉ chương Official (sidecar `isOfficial`) + `.done`
    + không thủng số trang; nghi khi còn trang **10,20,30..** ghi trước mốc (comix chèn trang xáo
    đúng các vị trí đó — ~450 chương có vết repair, chưa trang lẻ nào từng bị ghi lại). **Chốt
    chặn ngày file**: sidecar `at` trước mốc mà trung vị ngày trang thường SAU mốc = cả chương
    bị ghi lại (nén lại tại chỗ / chép backup) → "strict": làm lại MỌI trang 10,20.. + s:1.
    Vá xong ghi cờ sidecar `unscr_ok` → lượt sau bỏ qua khỏi mạng.
    **comix đã THÔI xáo** (phát hiện 27/09: Dungeon Reset ch.6 tải mới không còn cờ `s`, ảnh
    tại url sạch) → trang nghi mà site KHÔNG đánh s:1 thì **tải lại thẳng** (`_redownload_page`:
    vào `<chương>/.repair-tmp/`, qua kiểm tra `download_image` rồi mới thay file cũ; hụt giữ
    file cũ); trang site VẪN đánh s:1 thì giải-xáo như cũ. KHÔNG chỉ dựa cờ `s` (bản đầu của
    fix này dựa cờ → "soi comix, không cần sửa" oan khi site thôi xáo — bắt được nhờ test thật).
    Đường tải thường (chương tải dở trước mốc rồi tải tiếp): `_page_ok` coi trang s:1 ghi trước
    mốc là chưa xong; trang 10,20.. Official ghi trước mốc mà site không còn cờ → xoá để tải lại.
    **Sửa kho cũ**: `--repair-scramble` (chỉ comix, KHÔNG tải chương mới, không tải bìa; thiếu
    folder → dừng, không tạo folder rỗng; `--dest-name` khoá đúng folder). Online chỉ dùng ĐÚNG
    bản đang có (khớp `chapterId` sidecar trên TOÀN bộ bản của số chương); mất bản đó → `gone`,
    **KHÔNG lùi sang bản nhóm khác** (bản cũ lùi "official đầu tiên/cands[0]" = ghép ảnh 2 nhóm).
    Số trang đĩa ≠ số trang bản đó (xoá/đánh số lại tay) → `edited`, bỏ qua (ghi theo chỉ số sẽ
    đè nhầm). Chương chưa `.done` → `partialdl`, để `/tai` lo. Chương trên đĩa mà comix hết liệt
    kê → báo `gone`. Tổng kết in `REPAIR_RESULT_JSON:` (trước khối "===== SỬA TRÁO Ô" nên không
    lọt tin Telegram). Lý do phải có repair riêng: chương xáo cũ đã mang `.done` → `/tai` thường
    BỎ QUA. Xem memory `comix-scramble-s-flag`.
    **Bot `/repair <link…> [chương]`** (`supervisor.py`): mỗi link 1 job `--repair-scramble`
    vào CHUNG hàng đợi tải (dedup theo (url,chapters,repair,group,dest); nhãn 🧩), chạy TUẦN TỰ.
    **`/repair all`** (27/09): supervisor chạy `comic_downloader.py --repair-scan` (CHỈ đọc đĩa,
    in `REPAIR_SCAN_JSON:`; truyện comix nhận qua file dấu `_COMIX_official_*.txt` → slug → link;
    folder có Official mà thiếu file dấu → liệt kê riêng) → tin XEM TRƯỚC (cần vá bao nhiêu
    chương/trang mỗi truyện, bỏ qua kèm lý do, ước tính giờ) + nút `rpa:ok/no` (khuôn `_pending`
    như GHÉP, `kind`) → ✅ tạo ĐỢT: mỗi truyện 1 job `repair` + `dest`=folder + `batch`=mã đợt
    (bền qua restart). Job trong đợt KHÔNG báo "bắt đầu"; báo xong kèm `[k/N]`; kết quả ghi
    `.reader-meta/repair-batches.json`; job cuối của đợt xong (hoặc /stop, /clearq xoá hết
    job chờ) → `_batch_summary`: tổng kết + **quét đĩa lại** báo còn bao nhiêu chương nghi.
    Còn ngỏ (cosmetic): tin HUỶ/TREO của job vá vẫn dùng chữ "tải"/gợi ý "/tai". Đổi
    `supervisor.py` ⇒ `/update` phải kèm RESTART supervisor tay mới nạp lệnh mới.
  - `asura_downloader.py` — **giờ chỉ là shim** gọi `comic_downloader.main(default=asura)`
    → lệnh/shortcut cũ + gõ slug trần vẫn chạy như Asura như trước.
  - `Tai truyen.bat` — shortcut trong folder (không ra Desktop): **vòng lặp** hỏi link
    → chương → cbz → chạy → "Tai truyen khac? (y/N)" (y quay lại, N thoát). Tự nhận site.
    Echo không dấu + `chcp 65001` (Python tự in tiếng Việt utf-8).
  - Thêm site mới: viết 1 provider + 1 dòng `PROVIDERS`. Đổi domain: thêm domain vào
    `domains` (giữ cũ); đổi host API/CDN thì sửa hằng `API`/`BASE` trong provider đó.
  - **Override domain qua bot (KHÔNG sửa code, 12/09/2026)** — cho ca site xoay tên miền
    (TruyenQQ): `providers.py` đọc `.reader-meta/provider-domains.json` lúc IMPORT
    (`_apply_overrides`, TRƯỚC khi dựng `REGISTRY`) → nối `domains_add`, đổi `BASE`/`referer`
    lên INSTANCE. Mọi tiến trình con (downloader, check_updates) tự áp bản mới ở lần chạy kế →
    **KHÔNG cần restart supervisor** (supervisor stdlib-only, không import providers). `provider_admin.py`
    = CLI ghi file đó + xem trạng thái hiệu lực (import providers): `list|add|set|del|clear`;
    validate tên provider (chặn comix — browser, domain cố định), xoá được domain THÊM nhưng
    KHÔNG xoá domain gốc trong code. ⚠️ Chỉ thêm domain là đủ để NHẬN link; site chống-hotlink
    (TruyenQQ/Zet) còn phải set `base`+`referer` sang domain mới thì ảnh mới tải (CDN kiểm referer
    theo domain); site đã bật Cloudflare "Verify you are human" (challenge) thì thêm domain VÔ ÍCH
    (requests-trần không qua). Bot: `/provider` (list mở cho mọi người; add/set/del/clear cần admin)
    chạy `provider_admin.py` (subprocess) rồi relay stdout.
  - **GHÉP tải bù vào folder có sẵn (`--dest-name`, 12/09/2026)** — tải chương thiếu từ provider
    KHÁC vào ĐÚNG folder truyện đang có (reader định danh = tên folder = sid → giữ bookmark/tiến-
    trình/`series-meta`) thay vì tạo folder trùng. `core.run` khi có `args.dest_name`: `base_title` =
    dest-name (bỏ `title_from_slug` → khỏi 1 request), ép tên chương chỉ `Chapter N` (bỏ title, qua
    `_merge_folder`) để SỐ chương ↔ folder là 1:1 xuyên provider, và KHÔNG tải/đè bìa. An toàn 3 tầng
    (`_classify_merge`): (1) chương `.done` → bỏ qua tuyệt đối; (2) vắng hẳn → tải mới; (3) có ảnh
    CHƯA `.done` → CHỈ xoá-sạch-rồi-tải-trọn khi có `--chapters` chỉ định (chủ đích, `explicit`),
    KHÔNG chọn chương thì chỉ BÁO & bỏ qua (tránh nuốt folder cũ thiếu dấu `.done`; user chốt: tầng-3
    "tải lại trọn từ nguồn mới"). Giới hạn thật: tool KHÔNG bảo chứng "Chapter N của B = cùng nội dung
    với A" (numbering cross-provider) — preview để mắt người kiểm. `--dry-run` = in kế hoạch (buckets)
    + 1 dòng `PLAN_JSON:{…}` rồi thoát, KHÔNG chạm mạng per-chương (bot đọc để làm bước xác nhận). Chưa
    hỗ trợ nguồn comix (custom_run bỏ qua dest-name/dry-run — bot chặn `into:` cho comix.to).
  - Nhiều session song song cùng sửa project — luôn đọc lại file trước khi sửa đè.
- `check_library.py` — tool quét ảnh ĐÃ tải (offline, **đa luồng**), dùng chung lõi
  kiểm tra với downloader. Nhận đường dẫn tùy chọn (cả `downloads/` / 1 bộ / 1 chương);
  cờ `--fix` (cách ly `.bad`), `--recheck` (bỏ cache), `--workers N` (mặc định=số nhân,
  tối đa 8), **`--black`** (opt-in: thêm dò "trang một màu"; là quét SÂU — bỏ cache đọc,
  giải mã lại toàn bộ, chậm). MẶC ĐỊNH = tầng 2 (giải mã) + khuyết trang, **0 báo nhầm**.
  **Dò TRÁO Ô (comix, 01/09/2026)**: ảnh giải mã OK vẫn có thể bị tráo ô — thêm
  `looks_scrambled_bytes()` cho mỗi ảnh "ok"; trang dính vào mục "trang tráo ô" (KHÔNG
  cache 'tốt' → vẫn báo tới khi sửa), console/HTML gợi ý chạy
  `comic_downloader.py <url> --repair-scramble`. Chỉ BÁO, không tự cách ly (sửa qua repair).
  Xuất `.reader-meta/check-report.html` (thumbnail base64) + `.json`; cache
  `.reader-meta/check-cache.json` (mtime+size, ghi liên tục mỗi 1000 ảnh + ghi nguyên tử
  qua .tmp → Ctrl-C không mất tiến độ/không hỏng cache) → quét lại chỉ soi cái mới. Bỏ qua
  folder `.`-prefix, `.reader-meta`, `.cbz`, file `.bad`; bỏ file sửa <5s (đang tải dở).
  `check-ignore.txt` = trang một-màu đã duyệt là OK (bỏ báo); `image-issues.json` = sổ
  chung với downloader (`salvaged` = ảnh cụt đã cứu, đừng báo/đừng cách ly; `source_broken`
  = hỏng sẵn ở nguồn, khuyết trang do nó là "đã biết"). `Kiem tra truyen.bat` là shortcut
  (vòng lặp hỏi thư mục/--fix/--black → chạy).
- `convert_webp.py` — chuyển PNG→WebP hàng loạt, xuất cây mới `<tên>_webp`,
  không đụng cây gốc. Tách riêng khỏi asura_downloader vì Asura đã webp sẵn.
- `pdf_import.py` + `Nhap PDF.bat` (07/10/2026, gộp + SMask 08/10) — **nhập truyện PDF**: mỗi PDF đặt
  THẲNG trong folder truyện (hoặc 1 folder con chứa các PDF bị tách của 1 tập → gộp) → thư mục chương
  `Tập NN` (`001.jpg…`), PDF gốc → `<truyện>/.pdf-goc/`. *Vì sao tách chứ không
  cho reader đọc PDF*: reader + check_library + kho kích thước + ghép trang đôi + chữ ký thư viện đều
  mặc định "chương = thư mục ảnh" (~8–10 chỗ phải sửa, reader phải thêm bộ đọc PDF ngoài stdlib);
  pdf.js trên iPhone thì nặng (80–94MB/cuốn qua tunnel, mất nhớ vị trí/ghép trang). **Chỉ nhận trang
  "đúng 1 ảnh JPEG phủ kín trang"** (`page_jpeg`): content stream chỉ gồm q/Q/cm/Do/gs/màu/tham số nét
  (gặp BT/đường vẽ/ảnh inline → từ chối), đúng 1 lần `Do` một Image XObject `/DCTDecode` đơn, không
  `/Decode`/`/Mask`/`/ImageMask`, màu DeviceRGB/Gray hoặc ICCBased 1|3 kênh (không sRGB → cảnh báo),
  `/SMask` (xám 8-bit, không `/Matte`/`/Decode`, không nén DCT/JPX) đục 100% → nhận ngay (Acrobat hay gắn
  SMask toàn 255); có điểm trong suốt → `_alpha_bad_px` ghép JPEG lên nền TRẮNG như trình đọc PDF, lệch
  từng điểm = (255 − kênh tối nhất)·(1 − α), đếm điểm lệch > `ALPHA_TOL`=16/255: ≤ `ALPHA_MAX_PX`=64
  (1 ô 8×8) → vẫn chép JPEG gốc + cảnh báo; nhiều hơn = trong suốt thật → `_flatten_png` ghép lên nền
  trắng (giữ L/RGB + ICC) lưu **PNG** riêng trang đó (`page_jpeg` trả `(bytes, (W,H), đuôi)`), in danh
  sách trang PNG (08/10: Doraemon truyện ngắn Vol.01 trang 29 lệch 0 — điểm trong suốt vốn trắng; trang 101
  lệch tối đa 13 — viền elip mảnh quanh số trang; Vol.04 trang 11: 14 điểm hơi trong suốt, 2 điểm lệch 57
  — luật cũ "max lệch ≤ 16" từ chối oan cả tập; đều là vết thừa lúc chỉnh ảnh). PNG chứ không WebP/JPEG:
  không nén mất dữ liệu, reader đọc header PNG sẵn; `convert_webp.py` chỉ chạy tay. ExtGState không soft mask/alpha/
  blend, trang không xoay, CTM không xoay/lật, ảnh phủ vùng crop∩media lệch ≤ max(2pt, 0.5%), không kéo
  méo tỉ lệ, header JPEG khớp cỡ khai + RGB/L. Đạt → chép NGUYÊN stream (= file JPEG, pypdf `get_data()`
  không giải mã DCT); không đạt → dừng cả file, không ghi gì (chưa có bộ dựng trang — thêm pypdfium2 khi
  thật sự gặp PDF chữ/vector). Mỗi ảnh qua `check_image_bytes` trước khi ghi. **Tên**: số sau
  Tập/Vol/Quyển/Chương/Chapter/Chap/Ch/# (`NUM_KEY_RE`), không có thì số đầu tiên; `Tập {:02d}`, lẻ giữ
  phần thập phân (user chốt "Tập 01"/"Tập 07"); không số / trùng số trong 1 folder / PDF nằm ngay
  `downloads/` → báo, bỏ qua. **Ghi**: `downloads/.pdf-tmp/<truyện> - Tập NN/` (gốc downloads chấm-đầu =
  `_scan_library` bỏ qua; KHÔNG đặt tmp trong folder truyện vì `build_series` không lọc thư mục con
  chấm-đầu → thư mục tạm có ảnh sẽ hiện thành chương/arc) → đủ trang → `os.rename` sang chỗ thật
  (khác ổ thì `shutil.move`) → cất PDF (trùng tên thêm ` (2)`). `Tập NN` đã có: giống từng byte PDF →
  chỉ cất PDF (ca ngắt giữa đổi tên và cất); khác → bỏ qua. `.pdf-goc` trong folder truyện: `build_series`
  thấy nó là thư mục không ảnh, không thư mục con có ảnh → bỏ qua; check_library bỏ chấm-đầu. Exit 0/1
  (có file lỗi)/2 (không thấy PDF / thiếu pypdf) — `.bat` dùng 2 để khỏi hỏi "Tiến hành?". **Đo thực (07/10)**: Doraemon
  truyện dài Long 1 (189 trang, PDFsharp) + Vol.07 (206 trang, Acrobat, SMask toàn 255, 1 trang crop
  1527.81×2399.7, 1 trang ICC sRGB) → 395/395 ảnh giống từng byte stream trong PDF, 2.9s + 4.9s,
  check_library 0 lỗi, reader 8099: 2 chương, bìa trang 1, 189/206 ảnh tải, tỉ lệ đúng, 0 `nd`, 0 lỗi
  console. Ca giả (PDF Pillow): CCITT/CMYK(`/Decode`)/trang xoay/chèn `BT` đều bị từ chối đúng trang.
  ⚠️ Test `.bat` bằng chuyển hướng stdin phải bỏ `chcp 65001` — dưới 65001 `set /p` đọc file chuyển
  hướng ra RỖNG (gõ phím thật không bị).
  **Gộp tập bị tách (08/10)** — gặp `Doraemon truyện dài/01 - …/` + `14 - …/`: 1 tập = 6 PDF (Aspose,
  `…-0/-31/-61/-91/-121/-151`; bộ 14 phần đầu KHÔNG có số `…mo_Doremon 14 -.pdf`, đuôi rác `Doremon 1`
  → sắp tự nhiên đặt bìa ở trang 159). *Thiết kế*: 1 đường xử lý `Job` (items theo thứ tự, `dest`, `src`
  được cất); PDF lẻ = Job 1 phần → hành vi cũ giữ nguyên, toàn bộ an toàn (quét trước, ghi tmp, rename 1
  lần, so byte) dùng chung. **Chọn kiểu theo độ sâu so với `downloads/`** (`plan_jobs`, không có cờ): 2 =
  lẻ; 3 = cả folder con là 1 tập gộp (số từ TÊN FOLDER); 1 hoặc ≥4 → từ chối; ngoài downloads → lẻ. Đổi
  hành vi so với 07/10: PDF trong `<truyện>/<arc>/` trước ra `<arc>/Tập NN`, nay là gộp (chưa ai dùng).
  Folder gộp phải chỉ có PDF (+ Thumbs.db/desktop.ini) — có ảnh/thư mục con → từ chối (chặn hiểu nhầm
  folder arc/chương); tên folder trùng tên chương sẽ tạo (`Tập 14/`) → từ chối. Chọn 1 phần (kéo-thả 1
  file) → lấy CẢ folder (nếu không: ra tập 30 trang, lần nhập đủ sau bị "khác nội dung" → kẹt). Trùng
  đích tính theo `dest` (`_key` NFC+casefold), không theo folder chứa PDF (`Long 14.pdf` + folder `14 - …`
  cùng ra Tập 14). **Thứ tự** (`order_parts`): bỏ commonprefix của stem (NFC) — nếu prefix cắt giữa 1 dãy
  số (`…_1` của `…_1_x`/`…_15_x`) thì lùi về trước dãy số; `PART_NUM_RE` lấy số đầu phần còn lại (cho
  phép `_ - . ( ) [ ] #` và `phần/phan/part/p` đứng trước); ≥2 file không số / trùng số → dừng. **Kiểm**
  (`check_order`, sau khi biết số trang): số = trang bắt đầu cộng dồn từ 0|1 (phần không số = 0|1),
  hoặc cách đều bước k bắt đầu 0|1 (có phần không số: k|k+1) — 1,2,3 hoặc `-00/-03/-06…` (Doraemon 04,
  Aspose "Lite-Image-NN"; bước > 1 cần ≥ 3 phần, 2 số `0, 17` bước nào cũng khớp → từ chối) — số đầu cố
  định nên thiếu phần ĐẦU bị bắt, thiếu giữa phá cấp số cộng;
  thiếu phần CUỐI không có dữ liệu để bắt (bảng thứ tự + số trang luôn in ra). **Cất** cả folder bằng 1
  `os.rename` → `.pdf-goc/<folder>/` (không `shutil.move` cho thư mục: chép-xoá dở dang khi file bị khoá):
  bị ngắt chỉ còn 3 trạng thái, chạy lại tự xong; cất từng file thì ngắt giữa chừng → còn nửa số phần →
  kẹt. Cất lỗi (Explorer/trình đọc PDF đang mở 1 phần → WinError 5) → chương vẫn giữ, báo + exit 1, chạy
  lại = "đã tách từ trước" → chỉ cất. pypdf đọc nguyên file vào BytesIO rồi đóng → tool không tự giữ khoá.
  *Test 08/10* (bản sao trong scratchpad, `DOWNLOADS` vá sang đó): bộ 14 → 189 ảnh giống từng byte theo
  đúng thứ tự, `001.jpg` = bìa; Long 1 → Tập 01 189; truyện ngắn Vol.01 → Tập 01 192 (2 trang SMask nhận);
  `build_series` thấy Tập 01/07/14; chạy lại → exit 2; ca lỗi: kéo 1 phần, trùng đích, folder có ảnh, folder
  tên `Tập 14`, PDF quá sâu, thiếu phần giữa/đầu, `Tập 14` khác nội dung, PDF ngay downloads — đều dừng
  đúng, không đụng gì; ngắt sau tách (folder trả về chỗ cũ) → chỉ cất; trùng tên trong `.pdf-goc` → ` (2)`
  (cả file lẫn folder); `.pdf-tmp` rác cũ được dọn; file đang mở → báo, mở khoá chạy lại → cất xong.
  **Mục "Các tập lỗi" (08/10)** — chạy cả thư viện 17 tập lỗi thì dòng ✗ trôi mất: mọi đường lỗi đi qua
  `_fail(where, why, hint, nested)` (in như cũ + ghi `_FAILS`), trùng đích ghi từng nguồn, cất lỗi trong
  `_finish` cũng ghi → in "Các tập lỗi (N)" trước "Tổng", N = số lỗi/bỏ qua. `Job.where` = `<truyện>\<nguồn>`
  (+`\` nếu gộp). Thiếu pypdf kiểm 1 lần ở `main` (exit 2) thay vì mỗi tập 1 dòng. *Test*: 18 ca
  `check_order`; dry-run 3 mẫu `downloads/Doraemon lỗi` (04 → 209 trang, Vol.04 → 192 trang JPEG, 20 → 187;
  chạy chung thì 04 + Vol.04 trùng Tập 04 → 2 dòng trong mục lỗi); PDF giả SMask nửa trái α=0 → `002.png`
  nửa trái trắng tinh, nửa phải khớp JPEG 0 lệch, trang khác chép nguyên byte; chạy lại = "đã tách từ trước"
  (PNG ra cùng byte); thiếu phần `00/06/09`, đích khác nội dung → dòng con ✗ + mục lỗi.
  **PDF mã hoá AES (08/10 tối)** — server báo 6 tập DoremonVoz Vol.29/32–36 "DependencyError:
  cryptography>=3.1 is required for AES algorithm": Acrobat 20.12 khoá R6/AESV3 256-bit, `/P` cấm in/
  chép/sửa, mật khẩu mở RỖNG (`decrypt("")` = USER_PASSWORD). pypdf giải RC4 bằng code thuần Python
  nhưng AES phải có `cryptography` (hoặc pycryptodome); PC có sẵn `cryptography` 48 do `google-auth` kéo
  về nên chạy được, server thì không → thêm `cryptography` vào `requirements.txt` (`cap-nhat.bat` cài).
  `import_job` bắt `pypdf.errors.DependencyError` có chữ "AES" (R6 nổ lúc `decrypt`, AES-128 nổ lúc
  đọc stream — cả 2 nằm trong cùng khối try) → "PDF mã hoá AES, thiếu thư viện cryptography" + lệnh
  cài; mục "Các tập lỗi" in thêm 1 dòng "cài 1 lần". Không kiểm trước bằng `is_encrypted` vì RC4 không
  cần thư viện. Ảnh giải mã = đúng JPEG gốc (Vol.29: 191/191 trang giống từng byte `get_data()`).
  *Test*: chặn import `cryptography`/`Crypto` (meta_path) → provider `local_crypt_fallback`: Vol.29 thật,
  AES-128, AES-256 (rỗng + có mật khẩu) → thông báo mới; RC4-128 vẫn qua; có thư viện → 4/4 qua, AES-256
  có mật khẩu → "PDF có mật khẩu".
- `reader_server.py` — web reader kiểu Asura (HTML sinh trong Python stdlib; CSS/JS
  từ 21/08 tách ra file tĩnh versioned `/static/*` + có Service Worker `/sw.js`, xem
  mục "Tài nguyên tĩnh + Service Worker"; không dependency ngoài Pillow tùy chọn), port mặc định **8080**, user
  bật thủ công bằng shortcut Desktop **"Toony"**. **CHỈ quét thư viện trong
  `downloads/`** (`SCAN_ROOTS`; trước đây quét cả gốc project → các folder công cụ
  như `realesrgan-*`/`cover`/`cover_webp` có sub-folder chứa ảnh bị nhận nhầm thành
  truyện — đã bỏ quét gốc 11/08). Tính năng chính: quét tự động
  2 tầng folder (arc/chương) lẫn phẳng, sort số chương tự nhiên (0.1, 14.2...),
  ghép trang đôi thủ công (nút ⧉ → POST `/api/spread`), bộ nạp ảnh tuần tự JS
  kèm retry (tự thử lại 3 lần backoff 1s-3s-8s → ô "chạm để tải lại" → hồi cả
  cụm khi chạm/`online`/`visibilitychange`), bìa sidecar `cover.*`, **thanh công
  cụ KHÔNG tự bật khi vào chương** (kiểu Asura: `#topbar`/`#botbar` render sẵn class
  `hide`, `hid=true`; thay vào đó hiện pill `#tapcue` "Tap to show controls" nhấp nháy
  nhẹ ở đáy — `pointer-events:none` để chạm xuyên qua cho handler vùng đọc bật bars +
  ẩn pill; cuộn/chạm-lại → ẩn bars + pill trở lại), **nút chỉnh cỡ ảnh** (stepper −/%/+ header cạnh ⧉, có ô gõ % tay;
  100%=800px, min 1% cap 300%, đổi `#strip{max-width:min(var(--imgw,800px),100%)}`,
  kẹp theo màn không cuộn ngang, nhớ localStorage, ẩn ≤480px). **UI reader bằng
  tiếng Anh** (Bookmark/Bookmarked, All Comics, First/Latest Chapter, Prev/Next,
  Newest/Oldest, END OF CHAPTER...); comment code + log terminal giữ tiếng Việt.
  **Trang chủ** 2 mục có header ô-icon kiểu Asura: **Bookmarked** (slider ngang
  `.frow`, icon sao vàng; card ghi chương đang đọc / chưa đọc thì chương đầu, dựng
  lại client từ `FOLLOWDATA`+`BM` khi bấm bookmark). **Click card → trang LIST CHƯƠNG**
  (`u("series",sid)`), KHÔNG nhảy thẳng vào chương; nhãn `.fcm` vẫn hiện chương đang
  đọc dở (label từ `continue_info`, chỉ dùng cho nhãn — href lấy trang truyện). **Thứ tự = thời điểm bấm
  bookmark** (truyện bấm đầu đứng trái nhất; bỏ-rồi-bấm-lại về cuối) — server sắp
  `follows` theo `ud["bookmarks"]` (mảng append theo lần bấm) và truyền `BM` theo
  đúng thứ tự đó (KHÔNG `set()`); `renderFollows()` client duyệt theo `BM`, không
  theo thứ tự lưới. + **All Comics** (grid, icon
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
  debounce ~2.5s (**10s từ 01/10**, mirror localStorage 1s) + flush khi rời trang (`keepalive`), đánh dấu đã đọc qua op `read`.
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
  (nhật ký chương thiếu trang / hỏng nguồn khi tải + dòng "PHIÊN TRƯỚC CHẾT" nêu ảnh nghi làm
  crash), `crash-trace.txt` (C-stack do `faulthandler` ghi khi tiến trình sập tầng C — Pillow/
  libwebp; mở ở chế độ nối lúc import `comics_core`), `decoding-now.txt` (breadcrumb ảnh đang
  giải mã — ghi TRƯỚC `im.load()`, xoá khi xong; còn sót = crash tầng C, `reap_decode_crash()`
  đầu `run()` đọc rồi ghi thủ phạm vào 2 file trên),
  `bot-download-queue.json` (**hàng đợi tải `/tai` BỀN HOÁ** — {jobs:[{url,cid,state:
  pending|running,resumed}]}; supervisor ghi nguyên tử mỗi lần đổi, đọc lại lúc khởi động để
  **tải tiếp qua restart**; job xong/lỗi/huỷ-lệnh bị xoá, job bị restart-giết ở lại → resume),
  `tai-run.log` (output tiến trình `comic_downloader.py` do bot chạy — ghi thẳng ra file thay
  PIPE để supervisor chết không vỡ pipe + tail xem real-time; tự cắt khi >2MB; **stall-watchdog đọc
  SIZE file này mỗi 30s làm tín hiệu tiến-triển** — đứng im quá lâu = nghi treo, xem `supervisor.py`),
  `watchlist.json` (**danh sách truyện auto-check chương mới**, 1 nơi quản lý qua Telegram:
  `{last_run:"YYYY-MM-DD", series:[{url,title,provider,added_by,added_at,last_check,last_max,paused}]}`;
  supervisor ghi độc quyền, `check_updates.py` chỉ đọc),
  `watch-check-result.json` (kết quả 1 lần dò của `check_updates.py` để supervisor đọc lại:
  `{results:[{url,title,provider,status,listed_max,done_max,missing_count,new_since_last,error}], supported:[...]}`),
  `spreads.json` (cặp trang đôi đã ghép {left,right} theo sid/chương),
  `series-meta.json` ({sid: {status: complete|ongoing, order: N, title?: "tên hiển thị"}},
  key=tên folder; status thiếu=ongoing; `order` = thứ tự Home, sửa tay được, truyện mới
  auto=max+1; `title` (tùy chọn) = tên hiển thị đè lên tên-suy-từ-folder, do web admin đặt —
  đổi TÊN HIỂN THỊ chứ KHÔNG đổi folder/sid nên không mất bookmark/tiến-trình; rỗng/không có
  = dùng tên folder. server nạp lại theo mtime + thêm truyện mới append-only — không đè giá
  trị sửa tay),
  `user-data.json` (HỒ SƠ ĐỌC CHUNG: {bookmarks:[sid], progress:{sid:{rel,y,name}},
  read:{sid:[rel]}}; 1 hồ sơ cho mọi client, ghi qua `/api/state`, nạp theo mtime.
  **Reset = xoá cả file khi server ĐANG TẮT** — xoá lúc chạy có thể bị ghi đè lại từ
  cache RAM `_udata`),
  `reader-manga.ico` (favicon/icon shortcut Windows) + `icon-src.png` (nguồn
  1254² để sinh icon), **`icon-{180,192,512,512-maskable}.png`** (icon PWA
  home-screen, tạo tĩnh 1 lần bằng script từ `icon-src.png`), `brand.png` (logo
  chữ), `cloudflared.exe`.
- `supervisor.py` — **giám sát trên MÁY SERVER** (KHÔNG chạy máy dev): giữ `reader_server.py`
  + `cloudflared` quick-tunnel sống, bắt link `…trycloudflare.com` gửi Telegram, vòng nghe
  `getUpdates` xử lý lệnh bot (`/link /tai /update /stop…`, quyền `admin_chat_ids`), hàng đợi
  tải BỀN HOÁ 1-worker tuần tự (xem `bot-download-queue.json`). Bật/tắt qua
  `server-BAT-tudong.bat` / `server-TAT-tudong.bat`. **Lớp chống-chịu mạng (11/08/2026, sau
  sự cố DNS)**: `_net_status()` (connect IP thuần `1.1.1.1` + `getaddrinfo`) phân biệt *ok /
  dns hỏng / mất mạng hẳn*, làm CỔNG ở `run_tunnel` (mất mạng → KHÔNG bật cloudflared, chờ có
  backoff `3→300s`) và `download_loop` (offline → KHÔNG chạy job, giữ hàng đợi). Báo link khi
  **reader NỘI BỘ `127.0.0.1` đã phục vụ** (`_confirm_and_notify` → `_reader_alive`, chờ tối đa
  `READER_WAIT=60s`) + **khác link đã báo** (`_notified_link`) → hết spam. **KHÔNG** GET link
  CÔNG KHAI để đoán tunnel sống (mạng server không hairpin về chính tunnel của nó → sai ~2/3);
  regex `TUNNEL_RE` loại `api.trycloudflare.com` (host trong dòng lỗi). **Đã BỎ `health_loop`**
  (11/08): nó dùng cú GET công khai đó, 3 fail/180s → kill tunnel, hoá ra **giết nhầm tunnel
  đang tốt cho người đọc** mỗi ~3' → đổi link liên tục. Giờ tin cloudflared tự reconnect/thoát
  (chết thật → `run_tunnel` bắt + tạo link mới); reader chết → `run_reader` bật lại. Đánh đổi:
  reader TREO-mà-chưa-chết không tự phục hồi (ca hiếm, restart tay). Job lỗi kiểu-mạng
  (`NET_ERR_MARKERS` hoặc offline) → giữ `pending` thử lại, KHÔNG xoá (tránh mất hàng đợi khi mạng chập).
  **Stall-watchdog (18/08/2026, lưới bao chót chống treo câm)**: `download_loop` chờ downloader bằng
  `_wait_or_stall(proc, start_pos)` thay `proc.wait()` vô-timeout (cũ) — poll `os.path.getsize(tai-run.log)`
  mỗi `DL_STALL_POLL=30s`; log ĐỨNG IM > `dl_stall_limit` (config, mặc định `DL_STALL_LIMIT=1200s`) → nghi
  treo câm → `_kill(proc)` + `_kill_comix_chrome()` (terminate python KHÔNG giết chrome CON của Playwright →
  phải diệt riêng, kẻo mồ côi ôm profile; từ 28/09 match `TOOL_CHROME_RE` = mọi `.reader-meta\<tên>-profile`
  — comix + `qqvn-profile` của cf_browser; dùng chung cho dọn-lạc lúc khởi động) → nhánh `stalled`: GIỮ job `pending` thử
  lại (`stall_retries++`, backoff `DL_STALL_BACKOFF=120s`), quá `DL_STALL_RETRY_MAX=1` → bỏ + báo lỗi (daily
  tự enqueue lại). Vì sao đọc SIZE (không đọc nội dung): `getsize`=1 stat O(1), rẻ bất kể log to/nhỏ (log
  đã tự cắt ~2MB đầu mỗi job); size tăng đơn điệu trong 1 job = tín hiệu "còn sống". Vòng poll CHỈ tồn tại
  trong vòng đời 1 job (rảnh thì worker ngủ trên condition, không poll). Ngưỡng 1200s cố ý > cữ backoff 429
  tệ nhất của `comics_core` (1 lần sleep tới 900s) để KHÔNG giết nhầm job nghỉ-lịch-sự; `stop` set giữa
  chừng → kill sạch rồi thoát êm (job giữ 'running' cho resume). ① này bổ trợ ② (watchdog nội bộ comix):
  ② bắt nhanh ca mở-Chromium-wedge ~90s, ① phủ MỌI kiểu treo khác (≤20').
  **Heartbeat** (`heartbeat_loop`): mỗi 5' ping `heartbeat_url` (healthchecks.io) RA ngoài →
  dịch vụ ngoài báo khi server sập (kênh độc lập, sống cả khi bot câm); trống = tắt. LƯU Ý: check
  này nằm TRONG supervisor nên chỉ chứng minh SUPERVISOR sống, KHÔNG chứng minh reader phục vụ →
  reader có check RIÊNG (xem `reader_heartbeat_loop` trong reader). Supervisor chạy ẨN (`pythonw`)
  nên `log()` xoay file khi >2MB (`LOG_MAX`, giữ `.1`); soi log ở `.reader-meta/supervisor-log.txt`.
  **Giữ supervisor SỐNG — Hướng A** (24/08/2026, sau sự cố người-vào-server đóng cửa sổ supervisor):
  onlogon CHỈ start-1-lần, supervisor sập giữa phiên không ai bật lại (reader con vẫn phục vụ →
  healthchecks báo "down" mà web vẫn chạy, không "up"). KHÔNG chuyển Windows Service Session 0 vì
  comix cần desktop tick Cloudflare. Thay bằng: (1) supervisor chạy ẩn pythonw; (2) task `ToonyWatchdog`
  (`schtasks /sc MINUTE /mo 2 /it`) chạy `watchdog.ps1` [25/09: thay bằng `watchdog.pyw`] mỗi 2' — quét CommandLine `supervisor.py`, chết
  thì `Start-Process` pythonw bật lại (trong phiên đăng nhập → Chromium comix vẫn hiện), tôn trọng cờ
  `.reader-meta/toony-paused.flag`; (3) `server-TAT-tudong.bat` ĐẶT cờ pause + xoá cả 2 task → tắt sạch
  không bị watchdog cãi (để đồng nghiệp tắt máy test). Chi tiết & lý do: memory `supervisor-keepalive-huong-a`.
  **[25/09/2026] Watchdog = NƠI DUY NHẤT bật supervisor; BỎ task `ToonyServer`.** Sự cố 21→24/09: Windows
  Update reboot → `ToonyServer` (onlogon) bật supervisor → `schtasks /create` mặc định **"Stop the task if it
  runs longer than 72 hours"** → đúng 72h sau Task Scheduler GIẾT supervisor (`Last Result 267014` =
  `0x41306` SCHED_S_TASK_TERMINATED; con reader/cloudflared KHÔNG chết theo → link cũ vẫn đọc được, bot câm,
  healthchecks down). Watchdog lẽ ra cứu nhưng **chưa từng chạy đúng**: `server-BAT` truyền `-Base "%~dp0"`,
  `%~dp0` có `\` cuối → task lưu `-Base "...\"` → PowerShell `-File` hiểu `\"` là dấu nháy thường → `$Base`
  dư `"` → `Test-Path` sai → `exit 1` câm. Sửa: (1) `watchdog.ps1` lấy gốc từ `$PSScriptRoot` (`-Base` còn
  nhận nhưng BỎ QUA, để task kiểu cũ không vấp lúc chuyển đổi); ghi `watchdog-log.txt` cả nhánh LỖI (xoay
  >1MB); quét CIM lỗi → KHÔNG bật bừa (tránh 2 bản); `-Pyw` sai → dò `.venv`/PATH. (2) `server-BAT` xoá
  `ToonyServer`, KHÔNG `start` supervisor nữa mà `schtasks /run /tn ToonyWatchdog` (chỉ lùi về `start` khi
  đăng ký/`/run` hỏng); đặt cờ pause TẠM trong lúc dọn+đăng ký để nhịp watchdog không bật chen; cuối file
  đếm supervisor (in OK / 0 / nhiều bản); bỏ goto/label (file LF). Supervisor do watchdog bật là tiến trình
  RIÊNG, sống tiếp khi task (vài giây) kết thúc → không dính giới hạn 72h (đã test task thật ở dev). Đánh
  đổi: sau reboot supervisor lên chậm ≤2'. Deploy phải bằng `cap-nhat.bat` trên server (KHÔNG sửa
  `cap-nhat.bat` trong commit đổi bat/ps1: cmd đọc bat từng khúc, bị `reset --hard` ghi đè giữa chừng = chạy rác).
  **[25/09 vòng 2] Watchdog viết lại bằng Python — `watchdog.pyw` chạy bằng `pythonw.exe`** (xoá `watchdog.ps1`):
  task /it chạy `powershell.exe` thì MỖI 2' Windows bật 1 cửa sổ console PowerShell (nền xanh tím #012456)
  rồi tắt → cướp focus người dùng máy server + cắt ngang lúc tick Cloudflare. `pythonw` là GUI-subsystem → không
  console; powershell con (đếm supervisor qua CIM) gọi với `CREATE_NO_WINDOW`. Task action = `"<pythonw>"
  "<gốc>\watchdog.pyw"` (gốc lấy từ `__file__`). Bật supervisor bằng `Popen` `DETACHED_PROCESS |
  CREATE_NEW_PROCESS_GROUP` (+ thử `CREATE_BREAKAWAY_FROM_JOB`, job cấm thì bỏ cờ đó). Giữ nguyên: cờ pause, quét
  lỗi → KHÔNG bật (exit 2), log mọi nhánh (xoay >1MB). Cùng đợt: `server-TAT` CHƯA TỪNG chạy trọn — `echo ... (PID
  !SPID!) ...` trong khối `if` → `)` đóng khối → "va was unexpected", file dừng ngay SAU khi đặt cờ pause
  (supervisor còn sống, cờ nằm lại → watchdog thôi hồi sinh). Luật: **không để `(`/`)` trần trong echo nằm trong
  khối `if`/`for`** (bỏ ngoặc hoặc `^(`/`^)`; đừng đặt `rem` có ngoặc trong khối). Đã sửa cả `server-AUTOLOGIN`
  (lỗi ở lần chạy đầu khi chưa có Autologon64.exe), `day-len`/`tao-bundle` (mất chữ).
  **Auto-check chương mới** (`watch_loop`, 14/08/2026): mỗi ngày 1 lần lúc `check_hour:check_min`
  (mặc định 03:00 giờ server; bù nếu server tắt lúc đến hẹn — dò `last_run` trong watchlist so ngày
  hôm nay) chạy `check_updates.py` (subprocess) → `_apply_check_results`: cập nhật watchlist
  (`last_check`/`last_max`/`title`/`provider`, BỎ truyện site chưa hỗ trợ) + enqueue truyện cần tải
  vào ĐÚNG hàng đợi `/tai` (`_enqueue_jobs` dùng chung với `handle_tai`) + báo tóm tắt Telegram
  (`_summary_text`: 🆕 chương mới / ⤵️ tải bù / 📘 comix / ✅ không đổi / ⚠️ lỗi / ⛔ chưa hỗ trợ).
  Lệnh `/watchlist /watch /unwatch /checknow` (admin). Supervisor là NGƯỜI GHI DUY NHẤT
  `watchlist.json` (khoá `_wl_lock`, `_update_watchlist` đọc-sửa-ghi nguyên khối). enqueue auto đặt
  `cid` = `added_by` của truyện (người thêm nhận tin bắt đầu/xong tải). `_checking` chặn chạy chồng.
  **Lệnh `/provider` + GHÉP folder qua nút inline (12/09/2026)**: (1) `/provider [list|add|set|del|clear …]`
  (`handle_provider`) shell ra `provider_admin.py` rồi relay stdout — xem/sửa domain provider (xem mục
  providers.py "Override domain qua bot"); list mở, sửa cần admin. (2) `/tai <link> [chương] into:"Tên folder"`
  = GHÉP tải bù vào folder có sẵn: `handle_tai` tách `into:"…"` (regex, TRƯỚC parse chương/nhóm) → nếu có
  dest thì đi luồng PREVIEW: `_merge_preview` (chạy nền) gọi `comic_downloader.py … --dest-name --dry-run`,
  đọc `PLAN_JSON`, gửi tin kèm **nút inline** [✅/❌] (`reply_markup`), lưu `_pending[pid]` (TTL 10'). (3)
  `_process_update` nay xử lý `callback_query` (nút bấm) → `handle_callback`: `answerCallbackQuery` tắt spinner,
  kiểm admin, pop pending, bấm ✅ → `_enqueue_jobs(dest=…)` (job thêm trường `dest`, dedup key gồm dest,
  cmd `+= --dest-name`, `_load_jobs` khôi phục dest, `_job_label` hiện 🔀). Chặn `into:` cho comix (mở Chromium)
  + nhiều link + đi kèm ghim nhóm. Xem "GHÉP tải bù vào folder có sẵn" ở mục providers/core.
- `check_updates.py` — **dò chương mới cho watchlist, chạy dạng SUBPROCESS** (supervisor gọi; KHÔNG
  import vào supervisor để giữ nó stdlib-only + cô lập lỗi provider/mạng). Đọc `watchlist.json`, với
  mỗi truyện `resolve_provider` (bản riêng, trả None thay vì `sys.exit` khi site lạ) → `list_chapters`
  (peek CHỈ metadata, KHÔNG tải ảnh, qua PoliteGate chung) → so tập số chương với ĐĨA
  (`done_numbers`: folder `Chapter N` có `.done` **HOẶC chứa ảnh** — bắt cả thư viện cũ thiếu `.done`)
  → `missing_count` + `listed_max`/`done_max` + `new_since_last` (max tăng so `last_max` cũ). Status:
  `ok` (thiếu>0 → supervisor enqueue) / `comix` (luôn enqueue, không peek được — Chromium) /
  `browser` (28/09: provider có tầng trình duyệt bị Cloudflare chặn lúc dò — checker đặt
  `allow_browser=False` nên KHÔNG mở Chromium, bắt `core.Challenged` → supervisor VẪN enqueue, job tải tự
  chuyển Chromium; tin tóm tắt nhóm 🌐. Trước đây thành `error` = không bao giờ enqueue) /
  `unsupported` (site chưa provider) / `error` (list rỗng/lỗi, KHÔNG đụng state). Ghi kết quả ra
  `.reader-meta/watch-check-result.json` (supervisor đọc lại — KHÔNG parse stdout vì `_request` in
  429/503 ra stdout). Cờ `--only <url>` (lặp được) để check 1 vài truyện (dùng cho `/checknow`,
  `/watch` sau khi thêm). KHÔNG ghi watchlist (supervisor ghi). **Báo cáo chi tiết** (14/08):
  status `ok` xuất thêm `listed_count` (tổng chương site) + `missing_str` (`core.compact_chapters`:
  gộp dải `21-334`, số lẻ `.5` riêng, cắt bớt khi quá nhiều nhóm) → `supervisor._summary_text` in
  per-truyện `X/Y chương (thiếu K: ch. …)` theo nhóm 🆕 mới / ⤵️ tải-bù / ✅ đủ / 📘 comix / ⚠️ lỗi /
  ⛔ chưa-hỗ-trợ. comix KHÔNG có số ở đây (phải mở Chromium) → báo riêng từ lượt tải:
  `comix_site._report_comix_plan()` nhắn Telegram `X/Y` + "cần nâng cấp → Official {ch}" + "cần tải
  {ch}" ngay sau khi quét xong danh sách, TRƯỚC khi tải ảnh (chỉ đọc đĩa, phân loại MIRROR vòng lặp
  chính; "Official" = bản tick "v"). `core.compact_chapters` là helper dùng chung (khác `compact_ints`
  thuần-int: in số chương không đuôi `.0`, xử lý chương lẻ).
- **Auto-start / sống qua reboot** (Phương án A, 12/08/2026 — **[25/09] ĐÃ BỎ task `ToonyServer`**, giờ
  task `ToonyWatchdog` (/it, mỗi 2') bật supervisor sau khi đăng nhập; xem mục Heartbeat/Hướng A. Phần
  dưới là lịch sử): `server-BAT-tudong.bat` đăng ký task
  Windows `ToonyServer` (`schtasks /sc onlogon`) chạy `supervisor.py` khi ĐĂNG NHẬP — bằng **đường
  dẫn TUYỆT ĐỐI** tới `python.exe` (task onlogon không có PATH → tên trần `python`/`pythonw` lỗi
  `0x80070002`; suy `python.exe` từ `pythonw.exe` đã resolve để cùng thư mục). **[CẬP NHẬT 24/08]**
  giờ dùng `pythonw.exe` (chạy ẨN, không cửa sổ) — bỏ cửa sổ đóng-được để không tái diễn sự cố; log
  đọc ở file `.reader-meta/supervisor-log.txt`. Kèm task `ToonyWatchdog` hồi sinh mỗi 2' (xem mục
  Heartbeat/Hướng A). Trigger là *onlogon* nên cần một phiên đăng nhập; muốn tự lên sau reboot
  **không cần gõ mật khẩu** = `server-AUTOLOGIN.bat` bật **Sysinternals Autologon** (mã hoá mật khẩu
  vào LSA secret, không plaintext). Hệ quả A: supervisor gắn với phiên interactive Administrator →
  **Switch user** giữ sống, **Sign out** giết; desktop tự mở khoá sau reboot (đánh đổi bảo mật đã
  chấp nhận). Từ 24/08 muốn TẮT phải chạy `server-TAT-tudong.bat` (đóng cửa sổ vô nghĩa vì chạy ẩn +
  watchdog sẽ bật lại).
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

- **Comix: danh tính tách đôi → mượn vé sống + giả TLS Chrome** (12/08/2026, sau sự cố
  403/503 khi site siết): tải trót lọt cả ngày rồi bỗng **403 tại `static.comix.to`** + **503
  tại `wowpic`**, trong khi **mở Chrome trên server đọc vẫn bình thường**. Gốc rễ: metadata đi
  bằng Playwright (có cf_clearance + UA thật, qua Cloudflare ngon) nhưng ẢNH đi bằng `requests`
  trần (chỉ UA cứng + Referer, KHÔNG cf_clearance) — hai "người" khác nhau. Khi Cloudflare nâng
  độ nhạy, `static.comix.to` (sau Cloudflare) đòi vé → client trần bị 403; còn `wowpic` (CDN
  riêng, KHÔNG sau Cloudflare) 503 là transient thật. **Vì sao KHÔNG "clear cho sạch để đỡ bị
  soi"**: với Cloudflare, request vô danh = khách CHƯA xác minh = ÍT tin nhất; cf_clearance là
  VÉ QUA CỬA (buộc cứng IP+UA), reuse nhất quán mới giảm nghi, xoay/sạch mới bị challenge.
  Fix (Bậc 1+2): `ComixImageClient` **mượn cf_clearance+UA sống từ browser**, refresh ở MAIN
  THREAD (Playwright sync API cấm gọi chéo luồng — worker chỉ đọc snapshot dict) đầu mỗi chương
  + khi 403 (làm mới vé rồi thử NỐT 1 lần, vẫn 403 → dừng phiên; KHÔNG thử mù kẻo tụt điểm IP);
  **`curl_cffi` impersonate Chrome** cho vân tay TLS/JA3 giống Chrome thật (Cloudflare soi cả
  TLS — `requests`/urllib3 lộ ngay là Python nên vé Chrome chìa qua handshake không-Chrome bị
  coi replay → 403), thiếu curl_cffi thì lùi về `requests` (vẫn mượn vé, kém chắc). **Tách 403
  vs 503**: thêm `core.Forbidden(Blocked)` (403, cho phép refresh-retry) + breaker riêng
  `gate.tripped_503` (503 lùi giờ 15→180s, chịu 5 đợt mới bỏ — trước 1 cú 503 giết cả phiên);
  `gate.recover()` reset cầu dao sau mỗi chương trọn. Client riêng để KHÔNG rò cf_clearance/UA
  sang `core.session` dùng chung 5 site. curl_cffi thêm vào `requirements.txt` (optional,
  `cap-nhat.bat` tự cài lúc `/update`).
- **Supervisor chống-chịu mạng + heartbeat** (11/08/2026, sau sự cố DNS đêm 10→11): DNS server
  chập ~5 tiếng làm cloudflared crash-loop ~3s/lần → **2900 link rác** gửi Telegram + worker
  **nhai sạch 8 truyện** trong hàng đợi (mỗi job fail vì mạng → bị xoá vĩnh viễn), tin lỗi cũng
  không gửi được (`getaddrinfo failed`). Gốc rễ là môi trường (DNS) nhưng CODE khuếch đại sự cố
  nhỏ thành thảm hoạ. Sửa (chỉ `supervisor.py`, KHÔNG đổi kiến trúc quick-tunnel vì user chưa có
  domain): gate mạng ở mọi vòng + backoff cloudflared; **giữ hàng đợi khi lỗi-mạng**; regex loại
  link rác `api.*`. Thêm **heartbeat RA healthchecks.io** vì bot KHÔNG thể tự báo khi mạng server
  chết (cùng đường mạng đã hỏng) → cần kênh cảnh báo NGOÀI. Còn để ngỏ: **named-tunnel + domain**
  (URL cố định, xoá tận gốc đổi-link + lỗi 1033) — chưa làm vì chưa có domain.
- **Bỏ `health_loop` + xác minh link bằng reader NỘI BỘ, không GET link công khai** (11/08/2026,
  sau khi soi log thật): cách "xác minh/health-check bằng GET chính URL công khai từ server" **sai
  ~2/3** vì mạng server không hairpin được về tunnel của nó (mỗi tunnel rơi edge Cloudflare khác;
  server chỉ với được vài edge — log bimodal: link nào verify thì trong 7-8s + sống mãi, link
  "xịt" thì fail suốt 180s). Hệ quả: `health_loop` (3 fail/180s → kill) **giết nhầm tunnel đang
  tốt cho người đọc** mỗi ~3' → đổi link liên tục + spam link "chưa xác minh". Sửa: **bỏ hẳn
  `health_loop`**; `_confirm_and_notify` chỉ chờ **reader `127.0.0.1`** (localhost tin cậy, không
  hairpin) rồi báo. Tin cloudflared tự reconnect/thoát. User chọn "bỏ luôn cho đơn giản"; đánh đổi
  đã chấp nhận: reader treo-mà-chưa-chết không tự phục hồi (heartbeat cũng không thấy) → restart tay.
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
  reader đọc cả hai (`IMG_EXTS`). Cloudflare Raven hiện chưa challenge GET thường → Raven vẫn
  dùng `core.session` trần, để cầu dao 403/503 dừng gọn. (curl_cffi giả-TLS đã thêm NHƯNG chỉ
  cho comix qua `ComixImageClient`; site khác chưa cần — thêm khi thực sự vỡ.)
- **MangaDex dùng API công khai** (`api.mangadex.org`): slug = UUID trong `/title/{uuid}/`;
  chương từ `/manga/{uuid}/feed?translatedLanguage[]=en` + `contentRating[]` đủ 4 mức
  (mặc định API loại `pornographic` → manga 18+ ra rỗng nếu không xin) + `order[volume]=asc
  &order[chapter]=asc&order[readableAt]=desc` (phân trang `limit=500` theo `total`). **Dedup
  key `"{volume}:{chương}"`, giữ bản GẶP ĐẦU** — vì readableAt desc nên đó là bản **upload
  MỚI NHẤT** (newest-wins, khớp `mangadex-downloader` mặc định; tránh vớ bản scan cũ khi
  nhiều nhóm dịch). **Loại bản `externalUrl`/`pages==0` TRƯỚC dedup**: bản external (link
  bản quyền, ảnh KHÔNG ở MangaDex) thường mới hơn → nếu để vào sẽ giành slot rồi bị bỏ vì
  rỗng, làm bản THẬT cũ hơn bị coi là trùng và mất luôn (sự cố Tondemo Skill ch1). Chương
  `chapter=null` (oneshot) gán số `0.0` chứ không bỏ. Ảnh qua
  **@Home**: `/at-home/server/{chapterId}` → ghép `{baseUrl}/data/{hash}/{file}` (đuôi
  .png/.jpg thật). Bìa: relationship `cover_art` → `uploads.mangadex.org/covers/{uuid}/{fileName}`.
- **MangaDex chọn ngôn ngữ bằng `?lang=xx` trong URL** (07/10; mặc định `en`): `series_slug`
  trả `"{uuid}@vi"` (EN giữ UUID trần), các hàm còn lại tách bằng `_split()`. Mã ngôn ngữ
  NẰM TRONG URL vì URL là thứ duy nhất chảy nguyên vẹn qua hàng đợi bot, watchlist,
  `check_updates`, `into:` → không phải sửa supervisor. Bản khác EN → folder `"<tên> [VI]"`
  riêng (chương EN/VI cùng số không trộn; folder EN cũ không đổi tên).
- **Đối chiếu tool `mansuf/mangadex-downloader` v3** (nguồn logic trên): khớp dedup
  `f"{volume}:{chapter}"` + order + contentRating. Chỗ **CHƯA làm** (chấp nhận): không
  report về `api.mangadex.network/report`, không tự xin node @Home khác khi 1 node hỏng,
  không có DoH. Đã test 08/08: cả PC dev lẫn **server** đều resolve/tải được
  `api.mangadex.org` + node `*.mangadex.network` → **không cần DoH**. `mangadex.org` trần bị
  chặn DNS về `127.0.0.1` nhưng provider không hề resolve host đó (chỉ api/uploads/network).
  `_retry_after` đọc thêm header MangaDex `x-ratelimit-retry-after` (mốc epoch, không phải
  số giây chờ). Naming theo chuẩn engine (`Chapter N - Title`), KHÁC tool (`Ch. N`).
- **MangaDex @Home ĐÒI `Referer: https://mangadex.org/`**: ảnh **NGUỘI** (chưa cache
  Cloudflare) mà thiếu Referer trả **404** (không phải 403!). Ảnh đã có người xem =
  cache HIT thì kể cả thiếu Referer vẫn 200 → dễ tưởng nhầm là chạy được. Nên
  `MangaDexProvider.referer="https://mangadex.org/"` (khác Asura/Raven `referer=None`).
  Chỉ cần Referer, KHÔNG cần Origin. (Chẩn ra 07/08: batch tải nguội 404 hàng loạt trong
  khi ảnh test lẻ 200 vì đã warm cache.)
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
- **Chống crash tầng C khi giải mã ảnh** (09/08): sự cố thật — tải qua server bỗng dừng giữa
  chương mà `Tai hang loat.bat` vẫn in "Xong". Nguyên nhân: `Image.load()` (Pillow/libwebp) gặp
  ảnh dị dạng có thể **sập tầng C** → giết cả tiến trình, KHÔNG traceback nên `try/except` Python
  bó tay; `.bat` thì in "Xong" vô điều kiện sau dòng `python`. Ba lớp: (1) `faulthandler` ghi
  C-stack vào `crash-trace.txt` (crash Ở ĐÂU); (2) breadcrumb `decoding-now.txt` ghi ảnh đang
  giải mã TRƯỚC `im.load()`, `reap_decode_crash()` đầu `run()` đọc phần còn sót → ảnh thủ phạm
  (crash Ở ẢNH NÀO), CỐ Ý không tự đánh dấu hỏng để khỏi bỏ nhầm ảnh tốt của luồng kia; (3) chặn
  bom TRƯỚC decode: `SAFE_MAX_BYTES` (64MB) + `SAFE_MAX_PIXELS` (60MP, đọc `im.size` từ header
  trước khi `load`). `Tai hang loat.bat` đọc `errorlevel`: rc=0 "Xong THẬT SỰ", rc=2 (bị chặn IP)
  nhắc chờ, rc khác → tự chạy lại tối đa 5 lần (chương `.done` tự bỏ qua) — không lặp vô hạn.
- **Bỏ emoji khỏi output CONSOLE, giữ ở Telegram/log-file** (09/08, phương án A): cmd cổ điển
  (conhost) không có glyph emoji (`✅⚠⛔` → tofu) và `🔒` astral làm lệch con trỏ khi in đè `\r`;
  chữ Việt UTF-8 thì hiện tốt. Nên output màn hình của downloader dùng nhãn CHỮ (`Đủ ảnh:`...) +
  `!`/`!!`/`->` thay `⚠`/`⛔`/`→`. `run()` in **dòng tổng kết cả bộ LUÔN hiển thị** (đếm
  `n_full`/`n_skipped`/`n_locked`), trước chỉ "Hoàn tất" trơ trọi. Emoji trong tin Telegram
  (supervisor) và ghi file (`append_log`) GIỮ nguyên vì 2 nơi đó render emoji tốt.
- **Chính sách WebP**: PNG → WebP q85 (giảm 50-80%, mắt thường không phân biệt
  với truyện scan); JPG **giữ nguyên** (đã lossy, nén lại chồng suy hao).
- **Đặt tên folder từ slug**: chỉ cắt cụm cuối nếu đúng 8 ký tự hex có chữ số
  (hash kiểu `-1d35e5bd`); slug từ API search không có hash, cắt mù sẽ mất chữ
  cuối tên truyện (bug "The-Greatest-Estate" 16/07).
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
- **Cache thư viện = stale-while-revalidate + cache nguồn bìa** (19/08, trị TTFB màn-trắng): quét
  thư viện tốn I/O (`build_series`→`dir_has_image` scandir MỌI thư mục chương; ví dụ 9 bộ = ~1.483
  thư mục con / 29.4k file), nên KHÔNG chặn request. `get_library()` (`reader_server.py`): cache còn
  hạn (`CACHE_TTL=60s`) trả ngay; hết hạn nhưng còn bản cũ → trả **STALE** ngay + quét lại ở daemon
  thread (`_refresh_library`, cờ `_lib_refreshing` chống trùng); chỉ build LẠNH (cache `None` lúc khởi
  động / vừa `bust_library_cache`) mới quét đồng bộ, tuần tự hoá bằng `_lib_build_lock` (phần quét tách
  ra `_scan_library`). Nguồn bìa cache sẵn vào series lúc build: `build_series` tính `cover_src`+`cover_mt`
  (scandir/getsize 1 lần/bộ mỗi lượt scan) → `cover_ver` chỉ đọc `series["cover_mt"]`, `cover_jpeg` dùng
  `series["cover_src"]` → **render home ~0 I/O đĩa** (đo dev: `html_home` 0.6ms). **Chẩn đoán gốc**: DevTools cho thấy
  màn trắng 100% là "Waiting for server response" (TTFB server-side), mạng/tunnel vô can (DNS+Connect+SSL
  bằng nhau giữa máy 124ms và máy 4.27s) → app SSR nên splash-in-HTML vô ích.
  **[BỔ SUNG 23/08 — chữ ký tự-bust khi thêm/xoá chương]**: TTL 60s một mình khiến số chương trễ tới 60s (chương
  đổi ngoài tiến trình reader, không ai gọi `bust_library_cache`). Thêm `_library_signature()` — chữ ký RẺ quét
  2 tầng thư mục (mtime folder truyện + folder con arc/chương, **KHÔNG lặn xuống ảnh** = chỗ đắt của scan), chạy
  mỗi lần `get_library` (**từ 01/10: chỉ trong thread nền, tối đa `SIG_EVERY`=10s/lần** — xem mục "Bộ đo + đợt sửa 01/10"). `_lib_cache` nay là `(ts, series, sig)`: chữ ký khớp → dùng cache bất kể tuổi; chữ ký đổi
  (thêm/xoá chương/arc/truyện) → bust + quét nền NGAY (không đợi 60s), TTL chỉ còn là lưới an toàn. `bust_library_cache`
  vẫn giữ cho thay đổi META (title/order/status/cover — không đổi mtime thư mục nên chữ ký không bắt).
- **Số chương / trạng thái / bìa tự cập nhật xuyên bfcache+SW — `GET /api/library-meta` + sync khi hiển thị**
  (23/08). *Bối cảnh*: dữ liệu phái sinh (số chương…) nhúng cứng trong HTML được cache; SW SWR chỉ ghi cache cho
  lần sau (không vá UI đang mở → phải vào lại 2-3 lần), còn back về home = bfcache đóng băng → KHÔNG bao giờ đổi.
  *Cách làm*: **(server)** endpoint `GET /api/library-meta` (`no-store`) trả `{version, series:{sid:{total,status,
  label,cover}}}`, `version`=sha1 payload (đổi đúng khi có field đổi, bất kể nguồn). **(render)** số chương bọc trong
  `<span class="chapn">` ở `home_card_html`/`smeta`/`chcount` để vá điểm không phải dựng lại innerHTML. **(client)**
  HOME_JS + SERIES_JS thêm `syncCounts()` fetch meta trên `pageshow` (load thường + bfcache persisted) và
  `visibilitychange` → `applyMeta`/`applySeriesMeta` vá TẠI CHỖ `.chapn` (text), `.st` (class+label), bìa `img.src`;
  so `version` với lần trước để khỏi đụng DOM thừa. Mẫu **giống `syncBM`**. Fetch sống nên xuyên qua bfcache+SW;
  server thì đã tươi nhờ chữ ký tự-bust (mục cache ở trên). Đây là "SWR đóng vòng bằng reconcile UI + refresh trên
  pageshow" — remedy chuẩn web cho bfcache staleness. *(Cùng ngày, B6:)* manifest đổi `no-store`→`no-cache` (bỏ mâu
  thuẫn header no-store nhưng SW `isStatic` lại cache-first).
- **Search trang chủ giữ trạng thái khi back — list state restoration** (23/08). *Triệu chứng*: back từ trang truyện
  về home → ô search TRỐNG nhưng lưới vẫn lọc theo keyword cũ, không bấm được truyện khác; gõ-rồi-xoá mới về all.
  *Gốc*: iOS Safari xoá `value` ô `inputmode=search` khi khôi phục bfcache nhưng GIỮ `display:none` của card
  (inline style trong DOM snapshot), mà bộ lọc chỉ chạy ở sự kiện `input` → không đường nào đồng bộ lại → lệch pha.
  *Cách làm* (HOME_JS): tách bộ lọc thành hàm idempotent `applyHomeFilter()` (đọc `hq.value`); lưu keyword vào
  `sessionStorage['homeq']` **bền theo phiên tab** (bỏ `removeItem` một-lần cũ) mỗi lần gõ; lúc load →
  `restoreHomeq()` tái lập value **rồi** `applyHomeFilter()`. `homey` vẫn là cuộn one-shot của admin
  `reloadKeepSearch`; key `homeq` nay dùng chung (persistent) cho cả admin-reload lẫn back. Chuẩn UX quốc tế =
  giữ keyword+lọc+scroll như lúc rời đi. **Gotcha iOS (quan trọng):** trên bfcache-restore KHÔNG được ghi value
  đồng bộ trong `pageshow` — iOS Safari áp phần khôi phục form-control của RIÊNG nó **SAU** `pageshow`, ghi RỖNG
  đè lên (→ ô trống nhưng list vẫn lọc vì `applyHomeFilter` đã chạy trước; F5 lại đúng vì tải mới không có form-state
  để iOS khôi phục). Nhánh `persisted` vì thế **HOÃN** reconcile sang sau nhịp khôi phục của iOS: double-`rAF`
  + `setTimeout(120)` dự phòng → `reconcileSearch()` ép lại value từ sessionStorage (nguồn sự thật) + lọc lại,
  có chốt so-sánh `hq.value===saved` để idempotent (nhiều nhịp không nháy). URL-as-state (`?q=`) KHÔNG né được
  gotcha này (vẫn phải JS ghi value ô search khi restore) nên chỉ là nâng cấp chia-sẻ-link, không thay cho việc hoãn.
- **Trị bookmark "cũ" khi điều hướng — bù cho việc bật bfcache** (21/08). *Bối cảnh*: sau khi bật bfcache
  (mục dưới), lộ 2 kiểu hiện bookmark cũ, GỐC KHÁC NHAU nên fix riêng. **② back về home/series thấy chưa
  bookmark**: trang bị bfcache "đóng băng" từ trước lúc bookmark, back khôi phục nguyên trạng → JS hydrate
  KHÔNG chạy lại. **① vừa bookmark ở home rồi bấm vào truyện thấy chưa bookmark, vào lại mới đúng**: SW đã
  prefetch/cache HTML trang series TỪ TRƯỚC (bookmark còn OFF), SWR trả bản cũ trước; và series page render
  nút bookmark từ SERVER, không re-hydrate client khi ĐĂNG NHẬP (guest tự lành vì đọc localStorage mỗi lần
  tải). *Chọn hướng A* (giữ server-render, không client-hydrate khắp nơi). *Cách làm* (`reader_server.py`):
  **② pageshow.persisted** — HOME_JS + SERIES_JS thêm listener `pageshow`, chỉ chạy khi `e.persisted` (khôi
  phục bfcache); guest đọc lại `localStorage`, đăng nhập refetch `GET /api/state` (đã có sẵn, trả
  `{bookmarks,progress,read}`; fetch thường nên SW không chặn → luôn tươi), rồi ÁP LẠI trạng thái qua hàm
  idempotent (`applyBM`/`setSbk`) — KHÔNG re-init nên không double-bind click. Lỗi mạng → giữ nguyên DOM.
  **① SW purge-page** — khi toggle bookmark thành công (chỉ nhánh ĐĂNG NHẬP), client gọi
  `TOONY_PURGE_PAGE(url)` (expose ở ACCT_JS, load trên home+series, KHÔNG ở reader) → postMessage
  `{type:'purge-page',url}` cho SW xoá riêng key đó khỏi `PAGE_CACHE` (`cache.delete(url,{ignoreSearch})`)
  → lần vào sau tải bản tươi. Home dùng `FOLLOWDATA[sid].url`, series dùng `location.href`. *Vì sao chỉ
  đăng nhập*: guest hydrate nút từ localStorage mỗi lần tải nên KHÔNG lệ thuộc cache; purge cho guest chỉ
  phí tốc độ prefetch. *Chỉ bookmark*: tiến trình/đã-đọc chưa refresh (giới hạn có sẵn, để sau). *Đánh đổi*:
  đăng nhập tốn 1 request `/api/state` + "pop" nhẹ mỗi lần back; purge làm đúng series vừa toggle mất tốc
  độ prefetch 1 lần; đua-prefetch hiếm (prefetch bay trước, về sau purge). *KHÔNG phá bfcache*:
  pageshow/pagehide là sự kiện chính danh, không làm trang mất quyền vào bfcache. `SW_VERSION` tự bump vì
  ver của home/series/acct.js đổi → SW mới activate, dọn cache cũ.
- **Ghép/tách trang đôi báo "Invalid action" oan** (25/08). *Triệu chứng*: bật chế độ ghép (⧉) → bấm
  **Join 2 pages** → trang tự reload nhưng TRÔNG Y NHƯ CŨ (nút Join còn nguyên, chưa thấy spread) → bấm lại
  → hiện `alert("Invalid action")`. *Gốc (đã tái hiện bằng test)*: **cùng một cơ chế stale-cache như bookmark**
  nhưng thiếu purge — join THÀNH CÔNG ở server (POST `/api/spread` ghi `spreads.json`), rồi `location.reload()`
  đi qua navigation-SWR → SW `return hit` = **HTML bản cache TRƯỚC join** (nút Join cũ còn đó), chỉ revalidate
  ngầm; handler join KHÔNG hề purge trang như bookmark làm. User tưởng chưa ăn → bấm Join lần 2 lên đúng cặp
  đó → `modify_spreads` cũ trả `False` ở nhánh `find(a) or find(b)` → endpoint trả "Invalid action". *Cách
  làm* (`reader_server.py`, 3 lớp): **①** reader thêm `purgeAndReload()` — sau khi join/tách/đảo `ok:true`,
  postMessage `{type:'purge-page',url:location.href}` (chờ SW **ack qua MessageChannel** + timeout 400ms dự
  phòng) rồi mới reload → luôn thấy trạng thái mới (giống ý tưởng bookmark nhưng nay CÓ ở trang reader). **②**
  SW handler `purge-page` trả ack qua `e.ports[0]` (trước chỉ xoá, không báo) để client chờ đúng lúc, khỏi
  đua với chính lần reload. **③** `modify_spreads` join **idempotent**: nếu `a`&`b` VỐN đã là 1 cặp (`find(a)
  is find(b)`, cùng object) → trả `True` (coi như xong) thay vì báo lỗi; chỉ khi 1 trang dính **cặp khác** mới
  trả `False`. **④** bump `SW_VERSION` prefix `v1-`→`v2-` (băm precache không đổi khi sửa logic SW) → activate
  dọn sạch `PAGE_CACHE` cũ trước-khi-vá. *Đánh đổi*: mỗi thao tác ghép tốn 1 vòng purge (≤400ms) trước reload.
  *Ghi chú*: nút Join server-side chỉ hiện GIỮA 2 trang đơn liền nhau nên "cặp mồ côi" (file đã đổi tên/không
  liền nhau, vd sau upgrade Asura→Official hay đổi tên folder làm `sid` lệch → spread mồ côi) vẫn có thể để lại
  1 trang lẻ kèm nút Join mà `find()` chặn; idempotency KHÔNG che trường hợp này (đúng — trang thuộc cặp khác) —
  cần dọn `spreads.json` tay nếu gặp.
- **Trị "vuốt back nháy 1 phát" trên iOS Safari** (21/08). *Triệu chứng*: đọc qua link cloudflared trên
  iPhone (Safari + Web App), **vuốt trái→phải để back thì màn hình nháy trắng 1 phát**, còn bấm nút Back
  của trình duyệt thì không. *Vì sao*: vuốt-back là **animation tương tác** — Safari phải vẽ trang đích
  trượt vào NGAY; nếu trang không nằm sẵn trong **bfcache** (back-forward cache) thì nó bị **dựng lại từ
  đầu** và các frame trung gian lộ ra = nháy. Nút Back không animate tương tác nên che được. Hai gốc: **(a)**
  `send_page()` trả document với `Cache-Control: no-store` → WebKit đời mới coi trang `no-store` là
  **không đủ điều kiện vào bfcache** ⇒ back luôn dựng lại; **(b)** nền tối `#0b0c10` chỉ đặt trên `body`
  (nằm trong app.css tải qua `<link>` ngoài) và **không khai báo `color-scheme`** → canvas mặc định là
  **trắng**, frame đầu khi dựng lại là trắng ⇒ chớp trắng (`theme-color` chỉ đổi thanh Safari, không cứu
  canvas). *Cách làm* (đều trong `reader_server.py`): **①** `send_page()` đổi `no-store`→**`no-cache`** —
  vẫn buộc revalidate mỗi load (không hiện nhầm trạng thái đăng nhập cũ) NHƯNG **`no-cache` không chặn
  bfcache** ⇒ back tức thì, hết nháy; JSON/`api/*` giữ `no-store` như cũ. **②** thêm `color-scheme:dark` +
  nền tối trên `html` (không chỉ `body`) trong CSS, và nhân đôi inline trong `<head>` (`<meta
  name="color-scheme"...>` + `<style>html{color-scheme:dark;background:#0b0c10}...`) để áp TRƯỚC khi
  app.css về ⇒ khử frame trắng kể cả khi vẫn phải dựng lại. *Đã kiểm*: không có handler touch/swipe tùy
  biến (loại xung đột cử chỉ), không `unload`/WebSocket/EventSource chặn bfcache; `pagehide` (lưu vị trí)
  an toàn với bfcache. *Kiểm chứng*: macOS Safari → Develop nối iPhone, nghe `pageshow` → `event.persisted
  === true` = đang khôi phục từ bfcache (đã hết nháy). *Đánh đổi*: `no-cache` vẫn round-trip revalidate mỗi
  lần (chấp nhận — SWR của SW đã lo first-paint nguội); bfcache chỉ hoạt động khi SW không chặn (đã kiểm
  navigate handler không phá).
- **Tài nguyên tĩnh tách file + Service Worker** (21/08, trị màn-trắng khi mở NGUỘI + bìa-nháy khi
  login/logout). *Vì sao*: SWR ở trên trị TTFB do scandil; còn 2 nút thắt CLIENT: (a) document `no-store`
  nhúng inline toàn bộ CSS(16KB)+JS → không cache được, mỗi lần mở kéo lại hết; (b) khi kết nối tunnel
  nguội (mở lần đầu / sau >1' idle → trình duyệt hủy tab nền + đóng keep-alive), TTFB document lên 1-2s
  → màn trắng vì chưa có gì để vẽ. Bìa nháy đen khi reload vì route `/cover` THIẾU ETag → không 304 được,
  reload tải lại 200 full. *Cách làm* (đều trong `reader_server.py`): **① registry `STATIC_ASSETS`** (CSS
  + từng khối JS: base/ls/acct/home/admin/series/reader) phục vụ ở `/static/<name>?v=<sha1[:10]>`,
  `Cache-Control: immutable` + ETag; `page()`/`html_*` nạp qua `static_tag()`, chỉ còn script DATA động
  (FOLLOWDATA/BM/LOGGEDIN/SDATA/D) inline TRƯỚC các file — home doc 35.9KB→11.5KB. **② `/cover` gắn ETag**
  `"{cover_ver}-{len}"` (+ If-None-Match→304). **③ Service Worker** `SW_JS` phục vụ ở `/sw.js`
  (`Cache-Control: no-cache` để cập nhật ngay, header `Service-Worker-Allowed: /`), `SW_VERSION` = hash
  của precache-list nên đổi asset ⇒ SW mới ⇒ dọn cache cũ (activate): **cache-first** cho `/cover` `/img` (**`/img` bỏ khỏi SW từ 01/10**)
  `/static` + icon (an toàn VÌ URL đều versioned — `/cover?v=cover_ver`, `/static?v=sha1`, ảnh chương
  `/img/...?v=mtime`, xem ⑧), **stale-while-revalidate** cho điều hướng HTML
  (first paint từ cache tức thì, cập nhật nền cho lần sau), POST/`api/*` bỏ qua. **④** login/logout gọi
  `purgeAndReload()` (ACCT_JS): postMessage `{type:'purge-pages'}` cho SW xoá `PAGE_CACHE` (ack qua
  MessageChannel + fallback 300ms) rồi reload — BẮT BUỘC vì SW khoá theo URL, không phân biệt cookie `uid`,
  không purge sẽ hiện nhầm trạng thái đăng nhập cũ. **⑤ Logo header nhẹ**: `brand.png` gốc 469KB mà chỉ
  hiện `height:34px` → `_build_brand_asset()` thu nhỏ (PIL, height 120, GIỮ hình) ra WebP ~18KB, nhét vào
  `STATIC_ASSETS['brand.webp']` (⇒ tự versioned + precache + cache-first); header dùng `brand_src()`
  (fallback `/brand` nếu thiếu PIL). **⑥ Prefetch trang series** (trị "bấm series lần đầu 2-3s" = cache-miss
  SWR): SW có hàng đợi `pfQ`/`pumpPrefetch` (giới hạn `PF_MAX=2`, nhận `{type:'prefetch',urls}`, bỏ cái đã
  cache, xoá khi purge); HOME_JS nạp trước theo `pointerdown` [ý định] + `IntersectionObserver`+`requestIdleCallback`
  [card lọt viewport] → lần bấm đầu cũng cache-hit. **⑦ Prefetch trang CHƯƠNG kế/trước** (trị khựng 1-2s khi
  bấm Next / chọn chương): READER_JS lúc rảnh (`requestIdleCallback`) postMessage `{type:'prefetch',urls:[D.next,D.prev]}` (**từ 01/10 chỉ `D.next`**)
  cho cùng hàng đợi SW → Next/Prev sau đó lấy HTML từ cache gần như tức thì; việc render trước còn đo luôn
  kích thước ảnh chương đó vào kho phía server (`chapter_dims`, xem "Sửa 07/10"). Chỉ nạp HTML, KHÔNG kéo ảnh.
  **⑧ Ảnh chương versioned `?v=mtime`** (22/08, trị **méo ảnh trong reader dù file trên ĐĨA ĐÚNG**): SW cache
  `/img` cache-first + khoá theo URL, nhưng `img_url()` xưa KHÔNG gắn version (khác `/cover`). Khi 1 chương bị
  THAY bằng bản khác kích thước (vd upgrade comix: Asura 720×4000 → Official TappyToon 720×1334), URL
  `.../001.webp` ĐỨNG YÊN → SW trả bytes CŨ, còn HTML render `aspect-ratio` MỚI theo file mới → ảnh bị kéo méo
  (chỉ dính chương ĐÃ đọc trước đó + bị thay; disk luôn đúng). *Fix*: `img_url()` gắn `?v={st_mtime_ns}` (route
  `/img` dùng `urlsplit().path` nên bỏ qua query, vô hại; `ch_dir` có sẵn trong `html_reader`) → file đổi → mtime
  đổi → URL đổi → SW cache-miss → tải tươi. **TỰ khỏi, không cần xoá cache tay** (URL versioned là cache-miss dù
  bytes cũ vẫn nằm trong `IMG_CACHE`). Có hiệu lực sau ~1 lần mở lại (HTML qua SWR mới có URL `?v=`). KHÔNG dọn
  bản `?v=` cũ trong `IMG_CACHE`: rác nhỏ, chỉ sinh khi THAY ảnh (không phải khi tải chương mới), browser tự
  evict theo quota. *Lưu ý*: `mtime` đổi khi git-sync ghi lại file dù nội dung y hệt → client tải lại 1 lần (phí
  nhẹ, không sai) — chấp nhận vì `/cover` cũng dùng `mtime`.
  **⑧b SWR phải `e.waitUntil` + trang đọc tự đồng bộ danh sách ảnh** (02/09, trị **"repair thay ảnh
  tráo ô nhưng app mở lại cả chục lần vẫn ảnh cũ"**): nhánh navigate SWR trước đây `fetch(req).then(put)`
  "fire-and-forget" KHÔNG bọc `e.waitUntil` → theo spec, trình duyệt được tắt SW ngay khi `respondWith`
  xong; **iOS Safari tắt rất sớm** → revalidate bị hủy → `PAGE_CACHE` KHÔNG BAO GIỜ cập nhật → HTML cũ
  → `?v=` cũ → `IMG_CACHE` trả bytes cũ (desktop Chrome giữ SW sống thêm vài giây nên dev không thấy;
  đây cũng là gốc chung của 3 lần "SW giữ HTML cũ" 22/08, 25/08, 29/08). *Fix (1)* — ba việc, đo bằng
  diagnostic tạm ghi vào cache `toony-dbg` trên dev 8099: **(a)** revalidate navigate phải `fetch(req.url,
  {credentials:'same-origin', cache:'no-store'})` — TÁI DÙNG navigation Request `fetch(req)` rớt
  `TypeError: Failed to fetch` lúc được lúc không (mode navigate / redirect manual / signal gắn điều
  hướng) → `.catch` nuốt → cache đứng yên ngay cả trên Chromium (đây là gốc SÂU nhất, không chỉ iOS);
  **(b)** bọc `e.waitUntil` cho revalidate, `cache.put` nhánh miss/ảnh, và `pumpPrefetch()` (trả promise
  "cạn hàng đợi") trong message handler — iOS tắt SW sớm; **(c)** `SW_VERSION` = sha1(danh sách asset +
  CHÍNH `_SW_TEMPLATE`) — trước chỉ hash asset nên sửa logic SW không đổi ETag `/sw.js` → client nhận
  304 → giữ SW cũ mãi (dính ngay khi thử deploy (a)/(b): bản dbg không bao giờ được cài). Nay đổi mã SW
  là ETag + tên cache đổi → SW mới cài, dọn `PAGE_CACHE` kẹt. *Fix (2) — "mở là thấy ngay", không cần lần 2*:
  `GET /api/pages/<sid>/<rel>` (`no-store`, chỉ `stat`) trả `{version, pages:[{n,url,w,h}]}` (`version`
  = sha1 tên+mtime, `url` y hệt `img_url()`); `html_reader` nhúng `D.pv` + gắn `data-f` cho mọi `<img>`;
  `reader.js` `syncPages()` chạy ở `pageshow` (load + bfcache) và `visibilitychange`, lệch version thì
  vá TẠI CHỖ: ảnh chờ nạp → đổi `im._url` (bộ nạp tuần tự đọc `_url` lúc load, đã xoá `data-src`), ảnh
  đã/đang tải/lỗi → gán `src` mới, cập nhật `aspect-ratio` (đơn + spread). Cùng khuôn `syncCounts`/
  `syncReading`. Kiểm ở dev 8099: touch mtime 1 file → `pageshow` → `D.pv` + `src` đổi đúng, ảnh khác
  không đụng. Rác `?v=` cũ trong `IMG_CACHE` vẫn để browser evict (chưa dọn).
  **⑨ Navigation LUÔN trả 1 Response — không bao giờ null** (24/08, trị **"FetchEvent.respondWith received
  an error: Returned response is null"** trên iPhone): handler `navigate` cũ `return hit||net` với
  `net=fetch().catch(()=>hit)` → khi KHÔNG có cache VÀ mạng lỗi (điển hình: link quick-tunnel đã đổi/chết)
  thì `net` resolve về `undefined` → `respondWith(undefined)` = null → Safari "can't open the page". Đây
  chính là triệu chứng "web vào được, đọc ch1 ổn, sang ch2 ảnh fail, Next ra trang lỗi": SW phục vụ shell
  + ch1 TỪ CACHE (offline), ch2 chưa cache → ra mạng → tunnel chết → ảnh fail + navigate null. *Fix*: có
  cache → trả ngay + revalidate NGẦM (nuốt lỗi); không cache → `try fetch / catch` **luôn trả Response**
  (lỗi → trang 503 "Không kết nối được máy chủ — lấy link mới"). Đổi SW_JS body → `/sw.js` khác byte →
  browser tự cập nhật SW (served no-cache); cache-name (VER) không đổi nên không dọn IMG/PAGE cache.
  *Đánh đổi*: nội dung HTML trễ 1 lần mở (SWR); iOS
  Safari có thể evict SW sau ~7 ngày không dùng (mở lại chịu cold 1 lượt); prefetch tốn thêm băng thông
  (đã chặn 2 luồng + chỉ nạp cái chưa cache). *Gotcha*: header logo là `/brand` (KHÁC favicon `/logo`); đổi
  logo gốc thì phải để ý brand.webp cache-first sẽ giữ bản cũ tới khi SW_VERSION đổi.
- **Bộ đo tốc độ (diag) + đợt sửa theo số đo** (28/09 → 01/10). *Vì sao*: nhiều vòng đoán nguyên nhân màn trắng
  /đơ trên iPhone web app sai (origin đổi, SW khởi động chậm, quota evict…) → dựng bộ đo 3 nguồn rồi mới sửa.
  **Bộ đo**: `DIAG_JS` (trong base.js) gửi `POST /api/diag` mỗi lần mở trang (Navigation Timing: `workerStart`→
  `fetchStart` = SW khởi động, `responseStart`, DCL/FCP; kiểu mở; SW điều khiển?; đăng nhập?; bấm→trang mới qua
  `sessionStorage toony_tap`; đứng luồng chính >350ms; resume/bfcache; localStorage; vòng đệm sự kiện SW
  nav hit/miss/`open`/`match`/`net`/`dup`/`age`, pf, pfdrop; ở home ≤30'/lần thêm `storage.estimate` + số mục
  mỗi cache) → `.reader-meta/diag/client.jsonl`; server ghi 1 dòng/request (loại qua header `X-Toony-Kind`
  do SW gắn cho prefetch/revalidate, hoặc `Sec-Fetch-*`; ms; `lib`; ảnh đo nguội/ấm `dc/dw`; số request đồng
  thời; thiết bị) → `server.jsonl`, xoay vòng 5MB. Báo cáo `diag_report.py` (CLI / bot `/diag [clear|off|on]`
  / `GET /api/diag/report|raw?k=<token diag/token.txt>`, admin web không cần token). Tắt ghi: file `diag-off`.
  **Kết quả đo 30/09–01/10 (iPhone web app)**: (1) trắng khi mở app = `caches.open()` lúc SW vừa khởi động lạnh,
  tăng theo dung lượng Cache Storage (9ms khi 1.8MB → 1.3s khi ~527MB, kho ảnh `toony-img` tăng ~500MB/ngày,
  không giới hạn); SW khởi động chỉ ~5ms; SW đang chạy mở cache 0ms; đăng nhập/khách KHÔNG phải yếu tố. (2) tập
  Yu-Gi-Oh ~290 trang mở nguội 12–13s (PIL từng ảnh) + prefetch-rảnh 2 nút cùng lúc. (3) `_library_signature()`
  mỗi request: 78ms trung vị, 58% thời gian server. (4) tunnel ~380ms/request. Số "Website Data" trong Cài đặt
  Safari KHÔNG phản ánh bộ nhớ web app.
  **Sửa 01/10**: ① SW **không chặn `/img/`** nữa — ảnh chương giao HTTP cache trình duyệt (`/img?v=` trả
  `Cache-Control: public, max-age=31536000, immutable`; thiếu `?v` vẫn 7 ngày); bìa sang `COVER_CACHE='toony-cover'`
  (trần 150 mục); `PAGE_CACHE` trần 60 mục (`trim()` sau mỗi put — put lại 1 key đưa nó về cuối `keys()`, xoá từ
  đầu); activate xoá mọi cache khác (kể cả `toony-img` cũ). *Đánh đổi*: không còn đọc offline chương cũ; đọc lại
  chương cũ có thể tải lại nếu trình duyệt đã dọn HTTP cache. ② `html_reader` / `/api/pages` không chờ PIL:
  `dims_budget()` đo đồng bộ tối đa `DIMS_SYNC_BUDGET`=0.25s, còn lại `img_dims_nowait()` xếp hàng cho thread
  `_dims_worker` (ưu tiên); ảnh chưa đo mang `class="nd"` + tỉ lệ ước lượng (trung vị chương, không có thì 2/3),
  reader.js sửa tỉ lệ thật khi ảnh `load` (capture trên `#strip`). [ĐÃ BỎ 07/10 — xem "Sửa 07/10"] Thread `_dims_sweep` (sau khởi động 120s) đo cả
  thư viện ưu tiên thấp (`_sweep_wait`: chỉ chạy khi không request nào đang chạy VÀ request cuối xong ≥`DIMS_SWEEP_IDLE`=3s, kiểm trước mỗi chương + mỗi ảnh phải mở; 10ms/ảnh, 20ms/chương; tiến độ ghi bộ đo `k='sweep'` start/progress mỗi 300 chương/done/stop; tắt bằng file `dims-sweep-off`. Bản đầu 01/10 chỉ nhường khi CÓ request đang chạy → khe giữa 2 ảnh vẫn quét thư mục liên tục, chiếm HDD: 7 ảnh 1.1–4.7s); `dims-cache.json` (28/09)
  ghi 20s/lần, cache >20k mục thì 90s/lần (json.dump giữ GIL). Series chỉ đón đầu **1** nút (reading, không có thì
  First); reader chỉ đón đầu chương kế. ③ `get_library()` trả cache ngay, kiểm chữ ký trong thread nền tối đa
  10s/lần (`_lib_checked`), chương mới hiện sau ~10s + thời gian quét. ④ lưu vị trí: localStorage 1s, server 10s.
  **Sửa 07/10 — kích thước ảnh (bỏ quét cả thư viện)**: bộ đo 02–07/10 thấy `_dims_sweep` chạy ~5 GIỜ sau MỖI lần
  reader khởi động: trần `DIMS_MAX`=400k mục < 639k ảnh thư viện → chạm trần `_dim_cache.clear()` → lần sau đo lại
  từ đầu; Pillow 12 mở WebP = `WebPAnimDecoder(fp.read())` đọc NGUYÊN file; cache ~175MB RAM + ~50MB JSON ghi lại
  bằng `json.dump` thuần Python (giữ GIL) 90s/lần; ảnh chậm ~10× trong lúc quét. Thay bằng: (a) **chỉ đo chương đang
  mở / được render trước** — không còn luồng quét nền, không cờ `dims-sweep-off`; (b) `_hdr_size()` đọc 4KB đầu file:
  WebP (VP8 14 bit / VP8L 14 bit −1 / VP8X canvas 24 bit −1), PNG IHDR, JPEG đi theo độ dài đoạn tới SOF cuối trước
  SOS (y Pillow; đọc lại 4KB tại chỗ cần, quá 1MB → Pillow); GIF/BMP/AVIF/file lạ → Pillow dự phòng (`_measure`,
  bộ đo đếm `dp`). Đã so khớp 2152 file (thư viện dev + mẫu WebP lossy/lossless/alpha/động/EXIF/ICC, JPEG
  progressive/EXIF 60KB/ICC 200KB/CMYK/xám, PNG 4 kiểu, sai đuôi, file hỏng/cụt) = 0 lệch, nhanh ~57× kể cả OS cache
  ấm. (c) **Kho theo CHƯƠNG** `_dims_store`: khoá `"<sid>/<rel>"` → `(pages_version, array('I') [w0,h0,w1,h1,…])`
  theo thứ tự `list_images_mt`, 0,0 = không đo được; `pages_version` lệch (thêm/xoá/thay file) → đo lại cả chương;
  đang đo dở nằm ở `_dims_part` (chia sẻ giữa render đồng bộ và `_dims_worker`; `_dims_finish` chỉ ghi nếu part còn
  là bản hiện hành). `chapter_dims()` vẫn giữ ngân sách đồng bộ 0.25s + `class="nd"`. Lưu `.reader-meta/dims-v2.json`
  (`json.dumps` bộ mã hoá C, tmp + `os.replace`, 30s/lần chỉ khi có chương mới); **không bao giờ xoá sạch** —
  `_dims_prune()` mỗi giờ bỏ khoá không còn trong `_lib_cache` (RAM; thư viện rỗng/đang bust thì không dọn). Nạp lần
  đầu tự xoá `dims-cache.json` + `dims-sweep-off` cũ. Bộ đo thêm: request `dc` (đọc đầu file) / `dp` (Pillow) /
  `dw` (có sẵn) / `dq` (hết ngân sách → đo nền); `k='dims'` mỗi lần lưu (số chương/ảnh/KB/ms/dọn); `k='libscan'` mỗi
  lần QUÉT LẠI cả thư viện (`why` ttl|dir|bust|cold, ms quét + ms chữ ký) — đo chi phí quét lại mỗi `CACHE_TTL`
  trước khi quyết đổi sang quét theo truyện có thay đổi; selfping 5' kèm `ws`/`pm` (RAM reader MB, `proc_mem()` qua
  `K32GetProcessMemoryInfo`) + `dch`/`dpart`/`dhd`/`dpil`. Báo cáo mục [6] hiện đủ.
  **Bộ đo — 2 bẫy đo đã sửa 01/10**: (a) trang đọc nạp ảnh nối tiếp nên `load` tới rất muộn/không bao giờ → DIAG_JS
  đo muộn nhất DOMContentLoaded+5s, và gửi bản rút gọn khi `visibilitychange→hidden` (iOS hay bỏ trang ở nền mà
  không bắn `pagehide`); (b) mốc bấm `toony_tap` chỉ nhận nếu <30s (trang bị iOS bỏ rồi tự tải lại từng lấy mốc cũ
  → "bấm→trang mới 81s" ảo).
  **Gotcha đã dính**: SW chuẩn hoá URL prefetch thành TUYỆT ĐỐI (`new URL(raw, origin)`) — trang đọc gửi `D.next`
  tương đối; bản 28/09 gọi `new URL(url)` không base → ném lỗi sau khi tải xong → prefetch chương kế KHÔNG được
  lưu (Next luôn ra mạng 30/09–01/10) và key lệch key điều hướng (chống trùng hụt).
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
python comic_downloader.py "https://mangadex.org/title/{uuid}/..."   # MangaDex (bản dịch en; ?lang=vi = tiếng Việt)
python comic_downloader.py --site raven <slug>     # ép site khi gõ slug trần
python comic_downloader.py --pack "downloads\<Tên>"
python check_library.py [downloads\<Tên>] [--fix] [--recheck] [--workers N] [--black]  # kiểm ảnh đã tải
python asura_downloader.py <URL|slug> ...           # shim cũ, vẫn chạy (mặc định Asura)
# hoặc double-click "Tai truyen.bat" trong folder rồi dán link
python convert_webp.py "<folder>" [--quality 90] [--jpg-too]
python pdf_import.py ["downloads\<Tên>" | "<file>.pdf" | "<truyện>\<folder các phần>"] [--dry-run]   # PDF -> "Tập NN"; folder con = gộp (hoặc Nhap PDF.bat)
python reader_server.py [--port 8080]   # thường bật bằng shortcut "Toony"
```
