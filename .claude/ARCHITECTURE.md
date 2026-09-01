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
    Đang có: **AsuraProvider** (API JSON), **RavenProvider** (parse HTML + `ts_reader`),
    **DilibProvider** (parse HTML PHP), **MangaDexProvider** (API JSON, bản dịch `en`),
    **TruyenQQProvider** (parse HTML, `truyenqqko.com`), **ACGNProvider** (parse HTML tĩnh,
    `comic.acgn.cc`, truyện tiếng Trung — ảnh nhúng `_src` trong trang `view-{id}.htm`,
    danh sách tập ở `manhua-{slug}.htm`; số chương từ text `VOL`/`第N話`; referer=None;
    CDN `img.acgn.cc` lọc theo vùng → 522 ngoài VN),
    **NetTruyenProvider** (parse HTML tĩnh, `nettruyen.id`, React/Next.js SSR — chương là
    SUB-PATH `/truyen-tranh/{slug}/chuong-N`, ảnh nhúng `<img class="lozad" data-src="…">`
    CDN `images.truyenonline.cc` KHÔNG đòi Referer → referer=None; tên có dấu từ
    `<h1 class="title-detail">`; regex số chương dùng `[0-9]` thuần để không nuốt dấu `\`
    của blob `__NEXT_DATA__`; chỉ nhận `nettruyen.id`, clone họ nettruyen backend/CDN KHÁC).
  - `comic_downloader.py` — CLI mỏng: `resolve_provider()` tự nhận site theo domain
    của URL (hoặc cờ `--site`), rồi gọi qua `dispatch()`: provider thường → `core.run`;
    provider có `custom_run` (hiện chỉ comix) → loop riêng. Cờ giữ y hệt bản cũ
    (`--from/--to/--chapters/--cbz/--pack/--out/--workers/--delay`).
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
    (export `t` = hàm `vs`) tải ảnh rồi **giải-xáo VẼ LÊN `<canvas>` qua rAF** (trang thường
    dùng `<img>`). `fetch_pages` nay trả `[{"url","s"}]`; trong `run()` trang thường tải HTTP
    như cũ, trang `s:1` đi `ComixSession.descramble_pages()` — chạy `DESCRAMBLE_JS` bằng
    `page.evaluate`: `import(secureUrl)` (dò động từ Performance API → bền khi build đổi hash),
    gọi `vs(url).apply(canvas)` trên canvas ẩn tự tạo, chờ vẽ xong (poll pixel) rồi `toDataURL`
    lấy bytes SẠCH (ảnh wowpic serve CORS mở → canvas KHÔNG taint, đọc lại được). KHÔNG tự
    reverse permutation vì `secure.js` obfuscate nặng (control-flow flattening) — dễ gãy;
    dùng chính thuật toán site. **Cần Chromium HEADFUL HIỂN THỊ** (rAF chỉ chạy khi cửa sổ
    compositing — desktop server phải mở, không khóa màn hình; đúng ràng buộc "KHÔNG Session 0"
    của comix). **Guard**: `comics_core.looks_scrambled()` (đo "năng lượng đường nối" tại biên
    ô bằng PIL, ngưỡng 4.0 — sạch ~1-2 / xáo ~9-22; không numpy) coi trang `s:1` còn dấu xáo là
    "CHƯA đúng" → không đánh `.done` → tự thử lại lần sau (giải-xáo hụt KHÔNG bao giờ bị nhận
    nhầm là xong). **Sửa kho cũ**: `--repair-scramble` (chỉ comix) — dò offline từng chương
    (bỏ NHANH chương không dính, không chạm mạng), chương còn ảnh xáo thì lấy payload bản ĐANG
    có trên đĩa (khớp `chapterId` sidecar, hoặc đòi khớp số trang) rồi giải-xáo lại ĐÚNG trang
    `s:1`, ghi đè tại chỗ + đóng lại `.done`; KHÔNG tải chương mới. Lý do phải có repair riêng:
    chương xáo cũ đã mang `.done` (file webp hợp lệ, `is_known_broken` chỉ tra sổ URL-hỏng nên
    không bắt được) → chạy `/tai` thường (kể cả `--recheck`) sẽ BỎ QUA/không tải lại. Xem
    memory `comix-scramble-s-flag`. **Bot `/repair <link> [chương]`** (`supervisor.py`):
    enqueue job `--repair-scramble` vào chung hàng đợi tải (dedup theo (url,chapters,repair)
    → không đè job /tai; nhãn 🧩); repair in progress mỗi chương để log tiến (tránh
    stall-watchdog kill oan khi quét chương sạch). Đổi `supervisor.py` ⇒ `/update` phải kèm
    RESTART supervisor tay mới nạp lệnh mới.
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
  phải diệt riêng qua match 'comix-profile', kẻo mồ côi ôm profile) → nhánh `stalled`: GIỮ job `pending` thử
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
  (`schtasks /sc MINUTE /mo 2 /it`) chạy `watchdog.ps1` mỗi 2' — quét CommandLine `supervisor.py`, chết
  thì `Start-Process` pythonw bật lại (trong phiên đăng nhập → Chromium comix vẫn hiện), tôn trọng cờ
  `.reader-meta/toony-paused.flag`; (3) `server-TAT-tudong.bat` ĐẶT cờ pause + xoá cả 2 task → tắt sạch
  không bị watchdog cãi (để đồng nghiệp tắt máy test). Chi tiết & lý do: memory `supervisor-keepalive-huong-a`.
  **Auto-check chương mới** (`watch_loop`, 14/08/2026): mỗi ngày 1 lần lúc `check_hour:check_min`
  (mặc định 03:00 giờ server; bù nếu server tắt lúc đến hẹn — dò `last_run` trong watchlist so ngày
  hôm nay) chạy `check_updates.py` (subprocess) → `_apply_check_results`: cập nhật watchlist
  (`last_check`/`last_max`/`title`/`provider`, BỎ truyện site chưa hỗ trợ) + enqueue truyện cần tải
  vào ĐÚNG hàng đợi `/tai` (`_enqueue_jobs` dùng chung với `handle_tai`) + báo tóm tắt Telegram
  (`_summary_text`: 🆕 chương mới / ⤵️ tải bù / 📘 comix / ✅ không đổi / ⚠️ lỗi / ⛔ chưa hỗ trợ).
  Lệnh `/watchlist /watch /unwatch /checknow` (admin). Supervisor là NGƯỜI GHI DUY NHẤT
  `watchlist.json` (khoá `_wl_lock`, `_update_watchlist` đọc-sửa-ghi nguyên khối). enqueue auto đặt
  `cid` = `added_by` của truyện (người thêm nhận tin bắt đầu/xong tải). `_checking` chặn chạy chồng.
- `check_updates.py` — **dò chương mới cho watchlist, chạy dạng SUBPROCESS** (supervisor gọi; KHÔNG
  import vào supervisor để giữ nó stdlib-only + cô lập lỗi provider/mạng). Đọc `watchlist.json`, với
  mỗi truyện `resolve_provider` (bản riêng, trả None thay vì `sys.exit` khi site lạ) → `list_chapters`
  (peek CHỈ metadata, KHÔNG tải ảnh, qua PoliteGate chung) → so tập số chương với ĐĨA
  (`done_numbers`: folder `Chapter N` có `.done` **HOẶC chứa ảnh** — bắt cả thư viện cũ thiếu `.done`)
  → `missing_count` + `listed_max`/`done_max` + `new_since_last` (max tăng so `last_max` cũ). Status:
  `ok` (thiếu>0 → supervisor enqueue) / `comix` (luôn enqueue, không peek được — Chromium) /
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
- **Auto-start / sống qua reboot** (Phương án A, 12/08/2026): `server-BAT-tudong.bat` đăng ký task
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
  mỗi lần `get_library`. `_lib_cache` nay là `(ts, series, sig)`: chữ ký khớp → dùng cache bất kể tuổi; chữ ký đổi
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
  của precache-list nên đổi asset ⇒ SW mới ⇒ dọn cache cũ (activate): **cache-first** cho `/cover` `/img`
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
  bấm Next / chọn chương): READER_JS lúc rảnh (`requestIdleCallback`) postMessage `{type:'prefetch',urls:[D.next,D.prev]}`
  cho cùng hàng đợi SW → Next/Prev sau đó lấy HTML từ cache gần như tức thì; việc render trước còn WARM luôn
  `_dim_cache` phía server (html_reader hết phải mở PIL từng ảnh khi chương nguội). Chỉ nạp HTML, KHÔNG kéo ảnh.
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
python comic_downloader.py "https://mangadex.org/title/{uuid}/..."   # MangaDex (bản dịch en)
python comic_downloader.py --site raven <slug>     # ép site khi gõ slug trần
python comic_downloader.py --pack "downloads\<Tên>"
python check_library.py [downloads\<Tên>] [--fix] [--recheck] [--workers N] [--black]  # kiểm ảnh đã tải
python asura_downloader.py <URL|slug> ...           # shim cũ, vẫn chạy (mặc định Asura)
# hoặc double-click "Tai truyen.bat" trong folder rồi dán link
python convert_webp.py "<folder>" [--quality 90] [--jpg-too]
python reader_server.py [--port 8080]   # thường bật bằng shortcut "Toony"
```
