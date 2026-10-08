# Handoff — cập nhật lần cuối: 2026-10-08 (MỚI ĐÃ push 08/10: 1a2f4c0 [`pdf_import` gộp tập bị tách + nới SMask — CHƯA chạy thật trên thư viện] + 9cfbaed [provider `hitomi` + `hentaivnreal` — CHƯA thử server]; trước đó ĐÃ push: 06db97e [nhập PDF] + kích thước ảnh theo chương [bỏ quét 5 giờ] + 94f3f75 [4 provider 18+] + 7f4c1df [MangaDex `?lang=`], CHỜ `/update` + thử trên server)

> Kiến trúc ổn định (reader, provider, comix, supervisor, mạng…) nằm ở `.claude/ARCHITECTURE.md`.
> File này chỉ ghi TRẠNG THÁI hiện tại + việc đang dở.

## Đang làm / dở dang
- **[08/10] `pdf_import.py`: gộp tập bị tách nhiều PDF + nới luật lớp trong suốt — ĐÃ code + test trên BẢN SAO, ĐÃ commit/push 1a2f4c0, CHƯA chạy thật trên thư viện** (sửa: `pdf_import.py`, `Nhap PDF.bat` [chỉ chữ menu], README [mục "Nhập truyện PDF"], ARCHITECTURE [mục `pdf_import.py` đoạn "Gộp tập bị tách (08/10)" + SMask + Lệnh thường dùng]). KHÔNG đụng reader. *User chốt 08/10*: làm gộp nhưng giữ kiểu 1 file = 1 tập; mặc định ngoài `downloads\` = kiểu lẻ; tên `Tập NN`. Kiểu chọn theo vị trí: PDF thẳng trong folder truyện = 1 tập/file; PDF trong 1 folder con của truyện = cả folder là 1 tập (số từ tên folder, thứ tự phần theo số trong tên + đối chiếu số trang). Lớp trong suốt: ghép lên nền trắng lệch ≤16/255 → nhận, giữ JPEG gốc. **Trạng thái thư viện thật lúc code (user tự sắp)**: `Doraemon truyện dài/` = `Long 1 LITE.pdf` (user đã xoá `Tập 01` cũ và đưa PDF ra lại) + folder `14 - Ba chàng hiệp sĩ mộng mơ/` (6 PDF, 189 trang 900×1415) + `Tập 07` + `.pdf-goc/` (Vol.07); `Doraemon truyện ngắn/` = `DoremonVoz Vol.01 (lite).pdf` (192 trang 1528×2400, trang 29/101 có SMask vô hại). Folder `01 - Thăm công viên khủng long/` (6 PDF) user ĐÃ bỏ — nó là bản 900×1414 của đúng Tập 01 (189/189 trang khớp nội dung, kém nét hơn bản Long 1 LITE 1528×2400). **Dry-run thật (không ghi)**: 3/3 tập kiểm đạt → Tập 14 (gộp 6, đúng thứ tự, bìa trang 1), Tập 01 dài, Tập 01 ngắn. Test chi tiết: ARCHITECTURE. **Việc kế**: user chạy `Nhap PDF.bat` (Enter = cả thư viện) → `y`; mở reader xem Tập 01/07/14 + truyện ngắn; server: tự chép thư mục đã tách (không cần PDF).
- **[08/10] Provider `hitomi` (hitomi.la) — ĐÃ code + test PC, ĐÃ commit/push 9cfbaed (chung commit với hentaivnreal), CHỜ `/update`, CHƯA thử server** (`providers.py`: `HitomiProvider` + đăng ký `PROVIDERS`; README + ARCHITECTURE đã ghi; KHÔNG đụng core/bot). HTTP trần, không Chromium; Referer `https://hitomi.la/` bắt buộc. Test tải thật vào thư mục TẠM scratchpad (không đụng `downloads/`): hi4238970 30/30 WebP 2040×2880 khớp kích thước galleryinfo từng trang + `cover.webp`; chạy lại → `.done` bỏ qua; `--dest-name` bị chặn; link artist `-all.html` + gallery 404 → exit 1 có lý do; `check_updates.check_one` → `ok` listed_max 1 / `error`. Đo xoay gg.js lúc 04:00 GMT: URL b cũ còn sống, nhưng chỉ với bảng subdomain cũ → provider luôn dựng URL từ trọn 1 bản gg.js (chi tiết ARCHITECTURE).
- **[08/10] Provider `hentaivnreal` (hentaivnreal.com) — ĐÃ code + test trên PC, ĐÃ commit/push 9cfbaed, CHỜ `/update`** (`providers.py`: `HentaiVNRealProvider` + 2 hàm module `_rr_loader_data`/`_rr_route` giải turbo-stream React Router, đăng ký `PROVIDERS`; `comics_core.py`: `get_text(..., encoding=None)`; README + ARCHITECTURE đã ghi). HTTP trần, không Chromium. Test tải thật vào thư mục TẠM scratchpad (không đụng `downloads/`): oneshot link user 26/26 JPEG 19s; Sextoy ch.13/68.5/104 48 ảnh (trùng 13 giữ bản mới, slug `chap-106`=ch.104 đúng); Anh em nhà nghèo ch.1.2; Rayasi (tuyển tập → ` [HVR]`) ch.16 slug có `đ` — tất cả `ok`; chạy lại → 3 chương `.done` bỏ qua; `check_updates.check_one` (gọi hàm, KHÔNG ghi file kết quả thật) ra `ok`, link 404 → `error`; `provider_admin list` thấy provider; `py_compile` mọi `.py` OK. Đánh số đã thử ca biên bằng dữ liệu giả (extra lẻ/liền nhau, mở đầu → 0.5, trùng, tuyển tập). CHƯA thử server.
- **[07/10 tối] Nhập truyện PDF — ĐÃ code + test + CHẠY THẬT trên PC, ĐÃ commit/push 06db97e** *(08/10: user đã xoá `Tập 01` + đưa `Long 1 LITE.pdf` ra lại folder truyện — xem mục 08/10 ở trên)* (MỚI: `pdf_import.py`, `Nhap PDF.bat`; sửa: `requirements.txt` [+`pypdf`], README [mục "Nhập truyện PDF"], ARCHITECTURE [mục `pdf_import.py` + Lệnh thường dùng]). KHÔNG đụng reader. *Bối cảnh*: user có `downloads/Doraemon truyện dài/` chỉ chứa 2 PDF → reader không thấy chương nào. *User chốt 07/10*: tách PDF → thư mục ảnh (không cho reader đọc PDF, không pdf.js); PDF gốc → `<truyện>/.pdf-goc/`; tên `Tập 01`/`Tập 07`; giữ JPEG gốc (không WebP). Thiết kế + lý do: ARCHITECTURE mục `pdf_import.py`. **Đã chạy thật (đã kiểm lại đĩa)**: `Tập 01` 189 ảnh + `Tập 07` 206 ảnh, `.pdf-goc/` có 2 PDF gốc, không sót `downloads/.pdf-tmp`. **Đã test**: bản sao scratchpad → 395/395 ảnh giống từng byte stream DCT trong PDF (2.9s + 4.9s); `check_library` 0 lỗi (bỏ qua `.pdf-goc`); reader dev 8099 trên thư viện thật: 2 chương, bìa trang 1, 189/206 ảnh tải, tỉ lệ 1528/2400, 0 `nd`, 0 lỗi console; ca giả (PDF Pillow) — CCITT, CMYK, trang xoay, chèn `BT`, tên không số, trùng số, PDF ngay `downloads\` đều bị từ chối, không đụng file; chạy lại (đã tách → chỉ cất PDF, tên trùng thêm ` (2)`), thư mục đích khác nội dung → bỏ qua, rác `.pdf-tmp` cũ được dọn; `.bat` (bản bỏ `chcp`) 3 luồng kéo-thả/menu/không có PDF đúng. **Việc kế**: user mở reader thật (8080) xem 2 tập; commit/push (`day-len.bat`) nếu user muốn; **server**: `downloads/` không đồng bộ git → user tự chép 2 thư mục `Tập 01`/`Tập 07` (không cần PDF) vào `downloads\Doraemon truyện dài\` trên server; muốn CHẠY tool trên server thì cần `cap-nhat.bat` để cài `pypdf` (`/update` chỉ kéo code, không cài thư viện — đã grep supervisor.py, không có pip). Khi xong đọc thử ổn → user tự xoá `.pdf-goc` (~173MB).
- **[07/10] Reader: bỏ luồng quét kích thước cả thư viện (~5 giờ HDD sau MỖI lần khởi động) — ĐÃ code + test dev, ĐÃ commit/push, CHỜ `/update`** (chỉ `reader_server.py` + `diag_report.py`; KHÔNG đổi SW/JS → `SW_VERSION` giữ nguyên, điện thoại không mất cache; KHÔNG cần restart supervisor). Gốc + thiết kế: ARCHITECTURE "Sửa 07/10 — kích thước ảnh". Tóm tắt: chỉ đo chương đang mở/render trước, đọc 4KB đầu file thay Pillow, kho theo chương `dims-v2.json` không bao giờ xoá sạch; bộ đo thêm `dp`/`dq`, `k='dims'`, `k='libscan'`, RAM reader trong selfping. Test dev: so khớp Pillow 2152 file 0 lệch (~57× nhanh hơn); ngân sách 0 → 40 ảnh `nd` rồi luồng nền đo xong, render sau đủ; restart → 0 ảnh đo lại; thay 1 ảnh → chỉ chương đó đo lại (kích thước mới đúng), chương khác 0 đọc; xoá chương → `_dims_prune` bỏ đúng 1 khoá, không có `_lib_cache` → không dọn; 8 luồng cùng chương không lỗi, không sót `_dims_part`; rảnh 15s → 0 lần đo/0 `Image.open`; Chromium 8099: 15/15 ảnh tỉ lệ khớp ảnh thật, trang ghép đôi đúng tỉ lệ, 0 lỗi console; `dims-cache.json` cũ bị xoá. **Nghiệm thu (user)**: `/update` → `/diag clear` → dùng 1–2 ngày → `/diag`: không còn dòng "luồng đo kích thước nền"; ảnh trung vị ≤~10ms, p90 ≤~80ms kể cả vài giờ đầu sau khởi động; chương mở lần đầu server ≤~100ms; `dp` ≈ 0; RAM reader giảm. **Việc kế**: xem dòng "quét lại thư viện" (mỗi 60s khi có người đọc / 5' do selfping, cả thư viện) → quyết có đổi sang quét theo truyện có thay đổi không; rồi `/diag off`.
- **[07/10] MangaDex chọn ngôn ngữ bằng `?lang=xx` sau link — ĐÃ code + test PC, ĐÃ commit/push 7f4c1df, CHỜ `/update`** (`providers.py` [MangaDexProvider], `supervisor.py` [chỉ 2 dòng `/help`]). Mặc định vẫn `en`; `/tai <link>?lang=vi` → slug `{uuid}@vi` → feed `translatedLanguage[]=vi`, folder `"<tên> [VI]"` (bản EN giữ UUID trần → folder EN cũ không đổi tên). Ngôn ngữ nằm trong URL nên tự chảy qua `/tai`, `/watch`, `check_updates`, `into:` — không sửa parser bot. Test PC: `series_slug` 7 dạng link (`?lang=`, `&lang=`, `?tab=..?lang=VI`, `es-la`, `en`→UUID trần, UUID trần + `?lang=`) đúng; API thật Tsuzura-senpai (`8db5faa9-…`) VI 7 ch / EN 10 ch, ảnh ch.7 VI 20 trang; One Piece VI = 0 ch (bản quyền). `/update` là đủ (downloader + `check_updates` đều là tiến trình con); dòng `/help` mới chỉ hiện sau lần RESTART supervisor kế. **CHƯA**: `/tai <link>?lang=vi` thật trên server + xem folder `[VI]` trên reader.
- **[01/10] Provider one-shot 18+ `nhentai` (nhentai.to) + `hentaifc` (hentaifc.com) — ĐÃ code + test, ĐÃ commit/push 94f3f75 (07/10), CHỜ `/update`**: `NHentaiToProvider` + `HentaiFCProvider` + helper `_short_title` trong `providers.py`, đăng ký `PROVIDERS`; README + ARCHITECTURE đã ghi. Test tải thật vào thư mục TẠM (không đụng `downloads/`): nh218300 23 JPEG + nh624421 42 WebP + fc89351 5 JPEG → 73/73 ảnh (gồm bìa) `check_image_bytes`=ok; chạy lại → `.done` bỏ qua; `--dest-name` → exit 1 đúng lý do. CHƯA xem trên reader (bìa hentaifc đuôi `.jpg` bytes WebP — tiền lệ ZetTruyen chạy ổn). CHƯA thử `/tai` qua bot trên server.
- **[01/10] Provider `hentaivnx` (hentaivnx.com) + móc core `png_to_webp` — ĐÃ code + test, ĐÃ commit/push 94f3f75 (07/10), CHỜ `/update`**: `HentaiVNXProvider` chọn cdn1; `comics_core`: hằng `WEBP_TRANSCODE_Q`/`WEBP_MAX_DIM`, hàm `png_to_webp()`, `download_image(..., to_webp=)`, `run()` đổi đích `.png`→`.webp` khi provider bật cờ. Test thư mục TẠM: Trò Chơi Mạo Hiểm ch.148 22 lát PNG → 22 `.webp` 8.1MB `ok` (29s); xoá 2 trang + `.done` → tải bù đúng 2; ch.1-2 WebP + one-shot JPEG `chapter-0` 36 trang giữ nguyên đuôi; link chương → tự về trang bộ; hồi quy hentaifc (không bật móc) y cũ; `py_compile` 6 module OK. CHƯA thử trên server/reader.
- **[01/10] Provider `lxmanga` (lxmanga.org) — ĐÃ code + test trên PC, ĐÃ commit/push 94f3f75 (07/10), CHƯA thử server**: `LXMangaProvider` — HTML LUÔN qua `cf_browser` (profile `lx-profile`; nhà mạng chặn SNI, Chromium qua nhờ ECH), list chương đọc DOM sau JS, ảnh `cdn2.tymanga.com` tải HTTP, bìa qua `i0.wp.com`, bộ tuyển tập → số vị trí + hậu tố ` [LX]`, bỏ chương Raw. Test PC thư mục TẠM: Slave Wife ch.1 (20), Sex Tu Tiên ch.3 (46, `Chapter 3 - Dâm Nữ Đạo Chap 1`), [series] ch.1 (40, 1 PNG→WebP) → tất cả `ok`; chạy lại `.done` 22s; `--fetch http` in nhắc rồi vẫn chạy; `allow_browser=False` → Challenged. `--help`/README/ARCHITECTURE/cf_browser docstring đã ghi.
- **[01/10 chiều] Đo lại sau `/update` (30 phút dữ liệu) + 2 sửa nhỏ — ĐÃ code + test dev, ĐÃ commit/push, CHỜ `/update`**: server cải thiện rõ (quét thư viện/request 78→0ms; ảnh 93→15ms; dựng trang chương p90 606ms→39ms, max 12.7s→92ms; Tap 3 298 trang 92ms; `/api/state` 100→1ms; lưu vị trí 10s; prefetch chương kế đã vào cache). Mở cache lúc SW khởi động lạnh vẫn 269–568ms (5 lần, chỉ 1–2 phút sau khi SW mới xoá kho 527MB) → CHƯA kết luận, chờ thêm dữ liệu + số dung lượng [10]. Sửa: (1) `_sweep_wait()` — luồng đo nền chỉ chạy khi server rảnh ≥3s (bản đầu làm 7 ảnh Tap 3 mất 1.1–4.7s lúc 13:09) + ghi tiến độ `k='sweep'` vào bộ đo, báo cáo mục [6] hiện; (2) DIAG_JS đo muộn nhất DCL+5s + gửi khi app vào nền, bỏ mốc bấm >30s (con số "81s" là ảo). Test dev: bận → 0 ảnh đo, rảnh <IDLE → 0, sau đó chạy + ghi start/progress; mốc bấm 60s bị bỏ, mốc mới giữ.
- **[01/10] ĐÃ SỬA theo số đo (code + test dev Chromium 8099, ĐÃ commit/push, CHỜ `/update` — chỉ `reader_server.py` + `diag_report.py`, KHÔNG cần restart supervisor)**: ① SW không chặn `/img/` (HTTP cache `immutable`), bìa → `toony-cover` (≤150), `PAGE_CACHE` ≤60, activate xoá `toony-img` 527MB; ② trang chương/`/api/pages` đo PIL tối đa 0.25s rồi xếp hàng thread nền (`class="nd"` + tỉ lệ ước lượng, JS sửa khi ảnh về) + quét kích thước cả thư viện ưu tiên thấp sau khởi động 120s (tắt: file `.reader-meta/dims-sweep-off`); series đón đầu 1 nút, reader chỉ chương kế; ③ `get_library()` kiểm chữ ký ở thread nền ≤10s/lần; ④ lưu vị trí server 10s (localStorage 1s); ⑤ báo cáo: tách `open` SW nguội/ấm, sửa `cache {}`. **Lỗi tự gây (28/09) đã sửa**: URL prefetch tương đối (`D.next`) làm `new URL()` ném lỗi → chương kế không bao giờ được lưu cache (30/09–01/10 bấm Next luôn ra mạng). Đã test dev: cold render 27 ảnh budget 0 = 7ms, đo nền xong <1.5s; `toony-img` cũ bị xoá khi activate; ảnh chương không vào cache SW, header immutable; Next = cache-hit (byte đầu 4ms); 200×get_library = 0.2ms. **CHƯA**: nghiệm thu iPhone (đo lại bằng `/diag` sau `/diag clear`).
- **[01/10] KẾT QUẢ BỘ ĐO (30/09 12:26 → 01/10 12:18, iPhone web app đăng nhập; 200 bản ghi client, 8105 request server):**
  (1) **Trắng khi mở app = `caches.open()` lúc SW vừa khởi động lạnh, tăng theo dung lượng cache**: SW nguội (age<2s) mở PAGE_CACHE 146→392→476→1329ms khi bộ nhớ web app tăng 1.8MB→154→197→327→527MB trong ~1 ngày (`toony-img` 14→1122 mục, không giới hạn, KHÔNG xoá theo SW_VERSION); SW ấm 0ms; tab Safari cache nhỏ 23ms. `workerStart`→`fetchStart` chỉ ~5ms (khởi động SW KHÔNG phải nút thắt). Mở app từ nền không tải lại (resume) 30 lần = tức thì. Đăng nhập/khách không phải yếu tố (`/api/state` 13–19KB, chạy sau khi trang hiện). Số "Website Data" trong Cài đặt Safari KHÔNG phản ánh bộ nhớ web app (thật: 527MB).
  (2) **Đơ khi bấm tập Yu-Gi-Oh vẫn xảy ra 30/09 14:57 (sau deploy)**: mỗi "Tap" ~280–380 trang (không phải 60); mở series → prefetch-rảnh nút First (Tap 1, 289 ảnh) + reading (Tap 2, 280 ảnh) cùng lúc bấm Tap 3 (298 ảnh) → 3 render nguội song song 12.4–13.0s (PIL ~20–45ms/ảnh HDD). Sửa touch-prefetch có tác dụng (không thấy bão prefetch khi cuộn); dims lưu đĩa có tác dụng (lần sau 53ms).
  (3) **`get_library()` mỗi request: trung vị 78ms / p90 232ms / max 1.1s** — chiếm 83/93ms của mỗi request ảnh, 58% tổng thời gian xử lý server (506/868s).
  (4) Đường truyền tunnel + mạng điện thoại: ~380ms/request (p90 ~650ms), có đột biến 3.5s (DQ ch18: server 375ms, client chờ 4.2s).
  (5) POST `/api/state` (lưu vị trí 2.5s/lần) 3027 lần/ngày, mỗi lần ghi users.json. Đứng luồng chính: chủ yếu 0.4–1s ở trang đọc ảnh lớn; 1 lần 67.9s gần như chắc là iOS treo trang không bắn visibilitychange (không phải lỗi thật).
  Báo cáo lỗi nhỏ: mục [10] in `cache {}` khi bản ghi cuối không có số đếm.
- **[30/09] Provider MỚI `moetruyen` (moetruyen.net) — ĐÃ code + test dev, CHƯA commit/push, CHƯA nghiệm thu
  server** (`providers.py` [MoeTruyenProvider], `comics_core.py` [móc `render_pages`], `cf_browser.py`
  [`extra_hosts`/`block_types`/`goto`], `comic_downloader.py` [help `--fetch`], `.gitignore` [`*.zip`], README,
  ARCHITECTURE). Nguồn: bản tool của user `moetruyen_downloader_v1.1.zip` (gốc repo, nay bị `.gitignore` chặn) —
  KHÔNG dùng nguyên: có bug lưu khung "Chương kế tiếp" thành trang thừa, selector chờ `:nth-child` không bao giờ
  khớp từ trang 2 (chờ 5s/trang rồi chụp bừa), chụp cỡ CSS ~955px (mất nét), PNG, headless.
  *Cách làm*: metadata HTTP (dropdown trang chương mốc = đủ bộ; số trang `data-reader-total-pages`), ẢNH = chụp
  `.page-protected-shell` sau khi nới `.reader-pages` = cỡ gốc đọc SAU khi vẽ; WebP q90. Chi tiết + số đo:
  ARCHITECTURE mục MoeTruyenProvider + móc `render_pages`.
  **Đã test (dev, `--out` thư mục tạm, 30/09)**: metadata HTTP 92 chương có tên, bìa `-md`; E2E `--chapters 1` →
  bìa + 72/72 trang đúng cỡ gốc (70×1116×1584, 1200×626, 1224×868), `.done`, 17MB, 94s, rc 0; chạy lại → bỏ qua
  1s không mở Chromium; xoá `.done` + 3 trang → chỉ chụp bù 3 (12s), trang chụp lại lệch 0/255 so bản cũ;
  `check_one` → `ok` 92/thiếu 2-92, không nạp Playwright; `check_library` 0 hỏng/0 khuyết/0 một-màu (+1 báo nhầm
  "tráo ô" trang 72 gần trắng); hồi quy ZetTruyen ch0 26/26 (nhánh HTTP) + qqcomvn `--fetch browser` ch3 53/53
  (sau khi đặt bìa giả — xem lỗi bìa 403 ở Lưu ý); 0 Chromium `qqvn|moe-profile` sót. **CHƯA test**: server (HDD,
  phiên desktop), chương lẻ (chưa gặp bộ có chương .5), truyện 18+/cần đăng nhập, site bị Cloudflare challenge.
  **Deploy**: commit/push (day-len.bat) → `/update` là ĐỦ (không đụng `supervisor.py`; `moe-profile` đã khớp
  `TOOL_CHROME_RE`) → `/tai <link moetruyen> 1` thử 1 chương trên server.
- **[28/09] Reader: BỘ ĐO (diag) + sửa "bấm đọc đơ >5s" — ĐÃ code + test dev (Chromium localhost:8099), ĐÃ commit/push 30/09 (28→30/09 code nằm quên trên máy dev, /update khi đó chỉ kéo được qqcomvn), CHƯA nghiệm thu iPhone** (`reader_server.py`, `diag_report.py` [mới], `supervisor.py`).
  *Bối cảnh (21–28/09, user đo tay trên iPhone)*: web app trắng 3–5s khi mở (login lâu hơn khách, tăng dần theo lượng đọc); laptop cùng link nhanh; xoá Website Data + gỡ/cài lại web app → mở <1s, đọc 40 chương → 1–2s (Cài đặt Safari báo 21.7MB → 1.3MB, không tăng theo ảnh — số này KHÔNG đáng tin cho bộ nhớ riêng web app). Sau khi xoá: lần ĐẦU mở Yu-Gi-Oh (mỗi "Tap" = tập ~60 trang, chưa từng đọc) → list chương hiện dở + bấm đọc đơ >5s, về Home 1–2 lần mới vào được.
  *Chẩn đoán "đơ" (chắc chắn cao, khớp mọi chi tiết)*: render chương nguội = stat + mở PIL TỪNG ảnh (dims chỉ trong RAM, mất mỗi lần restart) → tập 60 trang trên HDD nguội vài giây; **prefetch bắn ở `pointerdown` kể cả khi chạm-để-CUỘN** → vuốt list = prefetch mọi tập dưới ngón tay, hàng đợi SW không giới hạn, vẫn chạy sau khi rời trang; bấm thật trúng chương đang prefetch → SW gửi request thứ 2 = render trùng tranh đĩa; web app standalone không có thanh tải → trông như đơ. Về Home rồi vào lại = prefetch đã xong, trúng cache.
  *Sửa*: (1) series.js + home.js bỏ prefetch khi `pointerType==='touch'` (+ bỏ mouseover giả lập sau chạm); (2) SW: `PF_QMAX=6` (giữ ý định mới nhất), xoá hàng đợi khi có điều hướng, map `inflight` URL→promise: điều hướng trúng URL đang prefetch thì CHỜ lượt đó (đo thật: `dup:1`, server chỉ render 1 lần), prefetch tới sau điều hướng thì bỏ; (3) `dims-cache.json` (.reader-meta, lưu mỗi 20s nếu có mục mới, nguyên tử, trần 400k mục) + `list_images_mt()` 1 scandir/chương thay 2–3 stat/ảnh (đã kiểm mtime scandir == os.stat → `?v=` KHÔNG đổi, iPhone không tải lại ảnh); (4) thanh tiến trình `#navbar` (NAV_JS trong base.js, hiện sau 120ms; điều hướng bằng JS gọi `TOONY_NAV(url)`).
  *Bộ đo*: DIAG_JS (base.js, mọi trang, sau load 1.5s hoặc lúc pagehide nếu rời sớm) gửi POST `/api/diag` → `.reader-meta/diag/client.jsonl`: Navigation Timing (`workerStart`→`fetchStart` = SW khởi động, `responseStart`, DCL, FCP), kiểu mở, SW điều khiển?, đăng nhập?, bấm→trang mới (`sessionStorage toony_tap`), đứng luồng chính >350ms, resume/bfcache, localStorage (+`chsort`), vòng đệm sự kiện SW (nav hit/miss/open/match/net/dup/age, pf, pfdrop); ở home ≤30'/lần thêm `storage.estimate` + số mục mỗi cache. Server ghi 1 dòng/request → `server.jsonl` (loại qua header `X-Toony-Kind` prefetch/revalidate do SW gắn, hoặc Sec-Fetch; ms; `lib` = get_library ms; `dc/dw` ảnh đo nguội/ấm; số request đồng thời; thiết bị). File xoay vòng 5MB (`*.old.jsonl`). Xem: `python diag_report.py [giờ]`, bot `/diag` (tóm tắt + link `/api/diag/report?k=<token>`; token ở `diag/token.txt`; `/diag clear|off|on`; cờ tắt = file `.reader-meta/diag-off`), `/api/diag/raw?k=..&f=client|server`. Admin web (cookie) cũng xem được không cần token.
  **Đã test (dev)**: SW mới cài + điều khiển; beacon về đủ 2 phía; touch không prefetch, chuột có; dedupe; `D.pv` == `/api/pages`; 23/23 ảnh tải; `/api/diag/report` không token → 403; handler bot `/diag` chạy offline (tg_api giả). **CHƯA test**: iPhone thật (Pointer Events touch, `workerStart` trên WebKit, sendBeacon), HDD server.
  **Deploy**: commit + push (day-len.bat) → `/update` → **RESTART supervisor 1 lần** (`supervisor.py` thêm `/diag`) → `/diag clear` → user chạy kịch bản thử (mở app sau nền ≥15' ×3, mở lại ngay ×3, mở 1 tập Yu-Gi-Oh chưa đọc + cuộn list rồi bấm, đăng xuất/đăng nhập mở app ×2) → `/diag` → gửi link báo cáo cho Claude (máy dev không đọc trực tiếp file server).
- **[28/09] Provider MỚI `qqcomvn` (truyenqq.com.vn) + tầng TRÌNH DUYỆT tự leo khi Cloudflare chặn — ĐÃ code + test dev (offline + LIVE site thật + E2E CLI), ĐÃ commit/push, CHỜ `/update` + RESTART supervisor (gộp chung lần restart của `/repair all`)** (`providers.py`, `cf_browser.py` [mới], `comics_core.py`, `comic_downloader.py`, `check_updates.py`, `supervisor.py`, `provider_admin.py`; docs ARCHITECTURE + README).
  *Khảo sát (27-28/09)*: `.com.vn` là site RIÊNG (khác họ truyenqqko dù trùng tên: URL `/{slug}/chapter-N`, CDN `sNN.cc3t.net` đòi Referer). **Số chương = số THỨ TỰ của site** (1..N liên tục, lệch số thật tăng dần +1→+15 ở Tinh Giáp; không lộ số thật) → folder hậu tố ` [QQ.vn]` + chặn ghép `into:`. **Cloudflare chập chờn**: trang series 12/09 403-challenge, 27/09 429-challenge, 28/09 mở; trang chương luôn mở → không gọi trang series, lấy mọi thứ từ trang chương mốc. **Chất lượng (đính chính)**: phần lớn ảnh GIỐNG HỆT họ ko, có chương nét hơn (ch1 1000 vs 900px) có chương KÉM hơn (ch3 800 vs 900px) — không phải "bản xịn" đồng loạt (user đã biết, vẫn chốt thêm provider).
  *Thiết kế (user chốt 27-28/09: D1 số của site + hậu tố `[QQ.vn]`, D2 tên `qqcomvn`, D3 chặn ghép, D4 core fail-fast challenge, chờ tick 15', được sửa supervisor)*: **thang leo** HTTP → (core `Challenged`) → Chromium thật `cf_browser` cho hết phiên; ảnh luôn HTTP. Challenge: chờ tự qua 20s im lặng → Telegram "cần tick" + chờ 15' (log mỗi 60s) → quá giờ dừng sạch exit 2. Mỗi URL chỉ chờ người 1 lần. **Vá 4 lỗ hổng**: (1) core 429-challenge không còn ngủ 21' + abort cả lượt check; (2) `check_updates` không mở Chromium, challenge → status `browser` → supervisor VẪN enqueue (cũ: `error` = không bao giờ tải) + nhóm tin 🌐; (3) supervisor diệt Chromium mồ côi theo `TOOL_CHROME_RE` (mọi `.reader-meta\*-profile`, không chỉ comix); (4) chặn `into:`. Bỏ `truyenqq.com.vn` khỏi `TruyenQQProvider.domains` (cũ: nhận nhầm rồi 404).
  **Đã test (dev)**: core — fake 429/403/503 + `cf-mitigated` → `Challenged` tức thì, `trips=0`/`abort=False`; hồi quy Zet 410 ch + truyenqqko 399 ch OK. Provider HTTP — `series_slug` 6 dạng URL; Tinh Giáp 408 ch 1→408 liên tục, Vạn Cổ 558 ch 0→557, Goblin tên có `:` giữ nguyên, ảnh ch1/2/408 = 35/48/14, host s34 + s25, bìa OK. `cf_browser` giả lập CF bằng server cục bộ — ok/404/tự-qua-theo-title/tự-qua-theo-header/chờ-người-hết-giờ (3 tin Telegram giả)/không mồ côi: ALL PASS (1 lượt có Chromium bị đóng giữa chờ → tự dựng lại đúng). Leo tầng trên site THẬT (giả lập HTTP bị chặn) → Chromium lấy 408 ch + ảnh, sau khi leo 0 request HTTP tới trang. **E2E CLI**: `--chapters 1,2,408` → bìa + 97/97 ảnh, chạy lại bỏ qua 3; `--fetch browser` ch3 → 45/45; Goblin ch1 (s25) 36/36; mọi ảnh Pillow decode, `.done` đủ, 0 Chromium `qqvn-profile` sót. `--dest-name` → exit 1 + lý do. `check_one` → `ok` 408; giả lập challenge → `browser`, không mở Chromium; `_summary_text` có nhóm 🌐 + enqueue. Regex `TOOL_CHROME_RE` (PowerShell thật): khớp comix/qqvn-profile, KHÔNG khớp Chrome thường.
  **CHƯA test**: chờ-người với Cloudflare THẬT (hôm nay site không challenge — logic đã kiểm bằng giả lập); chạy comix 1 chương sau đổi `dispatch` (chỉ bọc try/finally, comix không có `close`/`fetch_mode`).
  **Deploy**: đã push → trên server `/update` → **RESTART supervisor** (`server-BAT-tudong.bat`; `supervisor.py` đổi — gộp với restart cho `/repair all`) → `/provider` kiểm KHÔNG còn override gán `truyenqq.com.vn` cho `truyenqq` (có thì `/provider del truyenqq truyenqq.com.vn`) → `/tai https://truyenqq.com.vn/<slug>` → `/watch <link>`. Folder ra `"<Tên> [QQ.vn]"`; muốn ẩn hậu tố thì đổi tên hiển thị qua web admin (không đổi folder).
  **Còn ngỏ**: site đánh số lại (chèn chương giữa) → folder cũ lệch âm thầm, triệu chứng = chương cuối trùng (cố ý không dò: so số trang báo nhầm khi site up lại chương mới nhất); CF chặn cả Chromium tự động → dừng sạch, khi đó cần phương án khác; bìa nhỏ 190×247.
- **[27-28/09] comix — ảnh "bị tráo pixel" sót sau `/repair`: ĐÃ code + test dev (unit + LIVE comix thật), CHỜ push + `/update` + RESTART supervisor + chạy `/repair all`** (`comix_site.py`, `comic_downloader.py`, `supervisor.py`; docs ARCHITECTURE mục comix_site). Chưa commit.
  *Gốc (bằng chứng server, quét `/api/pages` mtime + soi tay 97 trang)*: `/repair` 02-03/09 lọc trang `s:1` bằng detector `looks_scrambled` (ngưỡng 4.0) → trang xáo GẦN-TRẮNG (credit TappyToon, TO BE CONTINUED, trang tựa, bong bóng nền trắng) chỉ ~2-3.9 điểm → bỏ qua mà vẫn đóng `.done`. Quét ~1.860/10.600 chương (9 truyện đủ + mẫu): **92 chương / 108 trang** sót (Dungeon Reset 75 ch; Farmer 6; Level Up 3; Overgeared 3; My Life 2; Ranker's 2; Solo Leveling 1 — 5 truyện sau chỉ lấy mẫu 8 chương nên thực tế NHIỀU hơn). Trang repair đã ghi là đúng. Tải mới ở dev KHÔNG tái hiện (trang vắng → luôn xử lý).
  *Fix (user chốt từng điểm 27/09)*: phát hiện bằng **MỐC ngày ghi file `UNSCRAMBLE_SINCE` = 02/09/2026 12:45 +07** (bằng chứng: trang repair sớm nhất server 12:45:06, soi 9 trang đầu/giữa/cuối 3 đợt sạch) — chế độ MẶC ĐỊNH: chương Official `.done` còn trang 10,20.. ghi trước mốc mới lên comix; **chốt chặn** cả chương bị ghi lại sau ngày tải sidecar → strict. Online: đúng `chapterId` sidecar (mất → `gone`, KHÔNG lùi nhóm khác); lệch số trang → `edited` bỏ qua; chưa `.done` → `partialdl`. Cờ sidecar `unscr_ok`. **Phát hiện 28/09: comix ĐÃ THÔI xáo** (DR ch.6 + Ranker's Return: payload hết cờ `s`, ảnh tại url sạch) → trang nghi không cờ = **tải lại thẳng** (`.repair-tmp` rồi mới thay), còn cờ thì giải-xáo. Đường tải thường cũng áp mốc. Bot **`/repair all`**: `--repair-scan` (chỉ đĩa, qua file dấu → slug) → xem trước + nút ✅/❌ → đợt job (`dest`=folder, `batch`), báo `[k/N]` từng truyện + tổng kết cuối kèm quét lại.
  **Đã test (dev)**: 17 unit test `_repair_scramble_chapter` (fake comix) PASS; supervisor offline (mock Telegram): preview/nút/enqueue/label/ghi đợt/tổng kết PASS. **LIVE comix**: (1) dựng lại đúng ca server DR ch.6 (010 xáo lấy từ server, ngày file như server) → `--repair-scan` thấy "1 ch ~1 trang" → job `--repair-scramble --dest-name` → "Đã sửa 1 chương (1 trang)", 010 mới GIỐNG HỆT bản sạch (diff 0.0), 020-070 không bị đụng, cờ ghi, quét lại "sạch". (Lượt đầu bản fix còn dựa cờ `s` → "không cần sửa" oan — đã sửa thành tải lại thẳng.) (2) Ranker's Return dev (8 ch Official 09/08 chưa vá) → 8 ch / 79 trang tải lại thẳng, 71 trang sao lưu trước đều là bản xáo, sau sạch (soi mắt).
  **Deploy**: `day-len.bat` → `/update` → **RESTART supervisor** (`server-BAT-tudong.bat`; `supervisor.py` đổi — thiếu bước này bot không biết `/repair all`, nút không phản hồi) → gửi `/repair all` → xem trước → ✅ (ước ~2-4 giờ, nên chạy lúc rảnh). **Nghiệm thu LIVE**: tổng kết cuối "Quét lại trên ổ: không còn chương nào nghi ✓"; mở DR ch.6 trang 010 trên reader thấy sạch; `/repair all` lần 2 báo 0 chương. Chương `edited`/`gone`/`partialdl` trong tổng kết: user tự quyết.
  **Còn ngỏ**: (a) comix thôi xáo → code giải-xáo (descramble_ops/DESCRAMBLE_JS) hiện không được gọi; GIỮ lại phòng site bật lại. (b) tin HUỶ/TREO job vá vẫn chữ "tải". (c) `looks_scrambled` giờ chỉ còn ở audit check_library.
- **[25/09] Supervisor chết 24/09, bot câm, link cũ vẫn đọc được — ĐÃ tìm gốc (bằng chứng trên server) + code + test dev bằng Task Scheduler thật + ĐÃ DEPLOY (`cap-nhat.bat`, commit 24c561f) + ĐÃ NGHIỆM THU LIVE 4/5 bước (25/09), còn chờ kiểm tự nhiên lần reboot kế** (`watchdog.pyw` [thay `watchdog.ps1`], `server-BAT-tudong.bat`, `server-TAT-tudong.bat`, `server-AUTOLOGIN.bat`; docs README + ARCHITECTURE). *KHÔNG đụng `supervisor.py` / `cap-nhat.bat`.*
  *Chẩn đoán (server `F:\Soft_Khac\comics-bundle`, Python 3.14, user Administrator)*: healthchecks "Toony Supervisor" down + bot không trả lời, reader/cloudflared vẫn chạy (mồ côi). Không có `supervisor.py` trong tiến trình; log dừng ngang (không dòng "Supervisor dừng"), không event crash. **Gốc 1**: Windows Update reboot 21/09 10:43 → `ToonyServer` (onlogon) bật supervisor 10:58:59 → mặc định `schtasks` "Stop task if runs >72h" → 24/09 ~10:59 Task Scheduler giết (`Last Result 267014`=`0x41306`). **Gốc 2**: `ToonyWatchdog` `Last Result 1` mỗi 2', không có `watchdog-log.txt` — `-Base "%~dp0"` (`\` cuối nuốt dấu nháy) → watchdog `exit 1` câm từ 24/08, chưa từng hồi sinh.
  *Fix*: watchdog lấy gốc `$PSScriptRoot` + log cả nhánh lỗi + quét CIM lỗi thì không bật + fallback pythonw; `server-BAT` xoá `ToonyServer`, watchdog là nơi DUY NHẤT bật supervisor (`schtasks /run`, chỉ `start` trực tiếp khi task hỏng), cờ pause tạm trong lúc dọn, cuối file đếm supervisor, bỏ goto. Chi tiết ARCHITECTURE mục Heartbeat/Hướng A.
  *Đã test (dev, thư mục nháp, supervisor GIẢ, task đổi tên `ZZTest*` rồi xoá sạch)*: chạy bản copy `server-BAT` → xoá task onlogon giả, task mới KHÔNG còn `-Base`, in "OK: dang co 1 supervisor", `watchdog-log` có dòng, tiến trình giả sống tiếp sau khi task kết thúc (Last Result 0). Kill → chạy watchdog → lên lại; đang sống → không bật trùng; cờ pause → không bật; tham số KIỂU CŨ (`-Base "...\"`) → vẫn chạy đúng; `-Pyw` sai → fallback + cảnh báo. **Tái hiện gốc 1**: task giới hạn 1 phút chạy thẳng pythonw → bị giết, `LastTaskResult 267014 (0x41306)` y như server.
  **Deploy (trên server, RDP)**: `cap-nhat.bat` (bot đang chết nên `/update` không dùng được; mà `/update` cũng không đăng ký lại task). Link sẽ ĐỔI (bot gửi link mới). **Nghiệm thu LIVE**: (1) cuối `server-BAT` in `OK: dang co 1 supervisor chay.` + bot gửi link + `/link` trả lời + `watchdog-log.txt` có dòng + healthchecks "up"; (2) `schtasks /query /tn ToonyServer` → không tìm thấy; (3) kill supervisor tay → ≤2' tự lên lại + thêm dòng log + link mới; (4) `server-TAT` → KHÔNG tự lên, rồi `server-BAT` bật lại; (5) lần reboot sau (WU) → ~2-3' sau đăng nhập bot gửi link.
  **✅ NGHIỆM THU LIVE 25/09 (user xác nhận đủ)**: server lên lại bằng `cap-nhat.bat`; (1) OK 1 supervisor + link mới; hết cửa sổ xanh/tím chớp mỗi 2 phút; (3) kill supervisor tay → watchdog tự bật lại ≤2' + log + link mới (LẦN ĐẦU watchdog hồi sinh được thật); (4) `server-TAT` chạy trọn tới "Da tat het", supervisor KHÔNG tự lên, `server-BAT` bật lại OK. **Còn lại**: (5) reboot — chờ lần Windows Update kế tiếp (không cần làm tay).
  **Còn ngỏ**: (a) supervisor bị kill thì cloudflared CŨ mồ côi vẫn chạy song song tunnel mới (link cũ sống tới khi `server-BAT`) — vô hại, chưa dọn. (b) Khi watchdog đã chạy thật, có thể cho `/update` tự thoát supervisor khi `supervisor.py` đổi để watchdog bật lại (hết phải RDP) — để sau. (c) Chưa có khoá 1-bản trong chính supervisor (hiện dựa vào watchdog là nơi duy nhất bật). (d) Trong lúc `cap-nhat.bat` đang pip install, task watchdog CŨ trỏ `watchdog.ps1` đã bị xoá → chớp cửa sổ lỗi vài lần tới khi `server-BAT` đăng ký lại — vô hại.
  **[25/09 vòng 2 — user báo sau commit 3bc70b8, TRƯỚC khi deploy]** (1) `server-TAT` chỉ chớp cửa sổ rồi tắt, bot vẫn chạy: tái hiện ở dev = `va was unexpected at this time` — `echo ... (PID !SPID!) ...` trong khối `if` (lỗi từ commit đầu 06/08, `server-TAT` chưa từng chạy trọn); file dừng SAU khi đặt cờ pause → trên server cờ `toony-paused.flag` bị bỏ lại (đã dặn user xoá tay). Quét mọi .bat: `server-AUTOLOGIN` cũng vỡ (lần đầu, khi chưa có Autologon64.exe), `day-len`/`tao-bundle` chỉ mất chữ → sửa hết. (2) Cửa sổ xanh/tím chớp mỗi 2 phút = console PowerShell của task watchdog (/it) — registry `ScreenColors 0x56`/`#012456`; mọi powershell do Python gọi đã `CREATE_NO_WINDOW`. Fix: `watchdog.pyw` chạy bằng `pythonw` (không console), xoá `watchdog.ps1`. **Test dev (task thật `ZZTest*`, supervisor giả, đã xoá sạch)**: `server-BAT` copy → action `"pythonw.exe" "…\watchdog.pyw"`, OK 1 supervisor, sống sau khi task xong; đang sống → không trùng; kill → lên lại; cờ pause → không bật; quét lỗi (giả lập) → exit 2 + log, không bật; `server-TAT` copy → chạy TRỌN tới `pause`, giết supervisor giả qua pid, gỡ task, exit 0. **Nghiệm thu LIVE thêm**: không còn cửa sổ nào chớp mỗi 2 phút trên server; `server-TAT` in đủ các dòng tới "Da tat het".
- **[12/09] Bot: `/provider` (quản-lý-domain) + GHÉP tải bù `/tai … into:"folder"` (nút inline) + `--dest-name` — ĐÃ code + test dev (engine 4 nhánh + luồng bot offline), CHỜ push + `/update` + RESTART supervisor** (`providers.py`, `provider_admin.py` [MỚI], `comics_core.py`, `comic_downloader.py`, `supervisor.py`; docs ARCHITECTURE + README).
  *4 yêu cầu user*: (1) TruyenQQ url mới `truyenqq.com.vn` — **GÁC LẠI**: đã kiểm là **Cloudflare Turnstile "Verify you are human"** (requests 403, browser cũng cần người tick) → phải làm provider MỚI kiểu comix-lite (transport browser + parser mượn TruyenQQ), không phải thêm domain; chưa làm. (2)(3) lệnh bot xem/sửa domain provider. (4) tải bù vào folder có sẵn (tránh trùng truyện trên reader).
  **#2+#3 — override domain (KHÔNG sửa code)**: `providers.py._apply_overrides()` đọc `.reader-meta/provider-domains.json` lúc import (trước `REGISTRY`) → nối `domains_add` + đổi `BASE`/`referer` lên instance; tiến trình con tự áp, **KHÔNG cần restart supervisor**. `provider_admin.py` = CLI `list|add|set|del|clear` (validate tên, chặn comix, không xoá domain gốc). Bot `/provider` (list mở; sửa cần admin) relay stdout. ⚠️ Site chống-hotlink phải set kèm base+referer; site Turnstile thêm domain vô ích (đã in cảnh báo).
  **#4 — GHÉP `--dest-name` (siết 3 tầng, user đã chốt)**: `core.run` dùng dest-name làm tên folder + ép `Chapter N` (bỏ title) + không đè bìa. `_classify_merge`: `.done`→bỏ qua; vắng hẳn→tải mới; có-ảnh-chưa-`.done`→ghi-đè-trọn CHỈ khi có `--chapters` (không thì báo & bỏ qua — an toàn folder cũ). `--dry-run`→in buckets + `PLAN_JSON`. Bot: `into:"…"` → `_merge_preview` (dry-run nền) → tin + **nút inline ✅/❌** → `handle_callback` (callback_query MỚI) → enqueue job có `dest`.
  **Đã test (dev)**: compile 5 file OK. Engine: dry-run plan đúng (done/add/overwrite/missing_src); merge THẬT vào folder scratchpad → bỏ qua 2 chương `.done`, thêm Chapter 1 (26 ảnh, tên trần, không đè cover); partial-skip khi bulk; overwrite (xoá ảnh giả + tải trọn) khi có `--chapters`. Bot offline (mock tg_api): parse `into:`, `_merge_preview` ra nút [✅/❌]+pid, `handle_callback` ✅→job có `dest`+cmd `--dest-name`, pid hết hạn xử lý đúng, chặn comix/nhiều-link/nhóm. `/provider add` áp vào REGISTRY+BASE+referer (fresh import), `del` giữ base/referer, `clear` xoá sạch, del domain gốc bị từ chối.
  **Deploy**: push (`day-len.bat`) → `/update` → **RỒI RESTART supervisor** (`server-BAT-tudong.bat`) vì `supervisor.py` đổi (thêm callback_query + lệnh — không restart thì bot chưa có `/provider`, nút inline không phản hồi). Phần `--dest-name`/`--dry-run`/override tự nạp (tiến trình con mới). **CHƯA nghiệm thu LIVE**: bấm nút ✅ trên Telegram thật; `/provider add` domain thật rồi tải; `/tai … into:"<folder có sẵn>"` gộp đúng không tạo folder trùng trên reader.
  **Còn ngỏ**: numbering cross-provider tool không tự bảo chứng (preview để mắt người); ghép chưa hỗ trợ nguồn comix.
- **[12/09] Provider MỚI: ZetTruyen (`zettruyen1.com`) — ĐÃ code + NGHIỆM THU E2E ở dev, đã push (commit 7db3a42)** (`providers.py`; docs ARCHITECTURE).
  *Yêu cầu*: thêm site `https://www.zettruyen1.com/truyen-tranh/tinh-giap-hon-tuong`. *Kiến trúc site (đã khảo sát thật)*: LAI — danh sách chương qua **API JSON PHÂN TRANG** `/api/comics/{slug}/chapters?per_page=100&page=N` (trang series chỉ có nút First/Latest; list thật ở `window.comicData.apiUrl`; lặp tới `last_page`), nhưng **ẢNH nhúng SẴN** trong HTML trang đọc `<div class="chapter-images-container">`. Cloudflare không challenge GET thường (như NetTruyen) → dùng `core.session` trần.
  **Điểm bẫy đã xử lý**: (1) chương LẺ URL trang đọc DÙNG DẤU CHẤM — `chapter_slug` "chapter-331-2" → `/chuong-331.2` (đổi '-'→'.'); `/chuong-331-2` rơi về chương 331 nguyên (SAI). (2) HOST CDN ĐỔI THEO CHƯƠNG (cdn1/cdn3/cdn4.zetimage.com) → lấy ảnh HOST-AGNOSTIC + đòi dạng `/{num}/{page}.ext`; dedup vì `onerror` lặp mỗi URL. (3) Đuôi URL `.jpg` nhưng BYTES thật WebP/PNG/JPEG lẫn lộn → file lưu `NNN.jpg`, engine kiểm ảnh dựa NỘI DUNG nên OK, reader/browser content-sniff render (KHÔNG đụng core, chấp nhận lệch đuôi cosmetic). (4) CDN cdn*.zetimage.com CHỐNG HOTLINK → `referer="{BASE}/"` (`run()` gắn vào session trước khi tải ảnh/bìa; API list KHÔNG cần referer → check_updates peek được). (5) Domain có số (zettruyen1) → dễ đổi như TruyenQQ.
  **Đã kiểm (E2E dev, `--out` thư mục tạm)**: `series_slug` (series/chapter/slug bắt đầu "chuong-") OK; title có dấu "Tinh Giáp Hồn Tướng"; `list_chapters` = **408 chương** (392 nguyên [0..391] không gap + 16 lẻ), ref lẻ dùng dấu chấm; `chapter_images` đúng mọi ca (ch0 26 ảnh cdn3, ch1 cdn4, ch391 94 ảnh cdn1, lẻ 221.1/331.2). **`comic_downloader.py … --chapters 0,221.1`**: cover.jpg + ch0 26/26 (thực PNG) + ch221.1 folder "Chapter 221.1" 4/4 (thực JPEG) → **30/30 OK, 0 hỏng**, mọi ảnh Pillow decode được.
  **Deploy**: push (`day-len.bat`) → trên server `/update` (chỉ `providers.py`; downloader chạy tiến trình mới mỗi job + `check_updates` nạp `REGISTRY` mới → **KHÔNG cần restart supervisor**). Auto-check watchlist chạy đầy đủ (site peek-được qua API). Thêm vào watchlist: `/watch <link>`.
- **[02/09] comix — bot báo "thiếu trang 10/30" tuy ẢNH CÓ SẴN & SẠCH trên đĩa: ĐÃ code + test OFFLINE logic, CHƯA nghiệm thu LIVE** (`comix_site.py`).
  *Gốc (đã xác nhận trên server: ch2 t10=8.09, ch3 t30=4.67 — ảnh liền mạch, mắt thường không lỗi)*: cổng nghiệm thu "trang tráo ô đã xong chưa" soi lại `looks_scrambled()` trên ảnh VỪA giải-xáo. Detector (năng lượng đường nối tại lưới n∈{4,5,6,8,10}, ngưỡng 4.0) **dương tính giả** trên webtoon dải dài: rãnh giữa khung tranh rơi trúng lưới → điểm cao dù ảnh sạch (đo tại repo: 181 trang scan sạch Solo Leveling ≥4.0, cao nhất 42.2 ở trang 720×7681). Trang 10/30 Farmer of Spirits giải-xáo ĐÚNG nhưng bị chấm ≥4.0 → vào `missing`/`retryable` → không `_mark_done` → bot "thiếu" mãi; chạy lại chỉ giải-xáo lại rồi lại bị gắn cờ. Không do tính năng ghim nhóm; lỗi ngầm từ đợt giải-xáo 02/09, ghim làm lộ ra.
  **Fix (user chốt: Mục 1, KHÔNG làm Mục 2 vì giải-xáo đang đúng)**: nghiệm thu bằng TÍN HIỆU THẬT thay detector. Đường tải `run()` (`_done_ok`): trang `s:1` = xong khi giải-xáo lượt này trả ra bytes (`got[i]`); `s:1` không nằm trong `scr_jobs` = đã sạch ở discovery. `/repair` (`still`): "còn sót" = `s:1` thiếu hẳn file HOẶC đã thử vá mà `got` không trả bytes. `looks_scrambled()` GIỮ ở bước PHÁT HIỆN (discovery `/repair`, `--recheck`, audit `check_library`) — nơi cần dò file CŨ còn xáo; dương-tính-giả ở đó chỉ tốn công quét lại 1 chương sạch, không hỏng dữ liệu, và giờ tự đóng `.done`. Đánh đổi đã chấp nhận: nếu tương lai giải-xáo HỎNG thật (bản đồ ô thiếu → ghi ra ảnh vẫn xáo) đường tải sẽ đóng `.done` cho trang đó (rủi ro thấp; gặp thật thì làm Mục 2 = đo tại đúng biên ô đã ghi).
  **Đã kiểm (offline)**: `py_compile` OK; mô phỏng `_done_ok`/`still`: giải-xáo OK (kể cả trang chấm ≥4.0) → missing=[]; giải-xáo hụt t30 → missing=[30]; `--recheck` fix xong → missing=[]. **Cần làm**: deploy `/update` (chỉ `comix_site.py`, downloader chạy tiến trình mới mỗi job nên tự nạp — KHÔNG cần restart supervisor); nghiệm thu LIVE `/tai <link Farmer of Spirits> 2,3 Hivetoon` → bot báo ĐỦ, chương 2/3 đóng `.done` (ảnh sạch sẵn nên không tải lại).
- **[02/09] comix — GHIM NHÓM (chọn cố định nguồn): ĐÃ code + test OFFLINE (luật chọn/plan/sidecar/parse lệnh), CHƯA chạy E2E với Chromium, CHƯA nghiệm thu LIVE** (`comix_site.py`, `comic_downloader.py`, `supervisor.py`, README, ARCHITECTURE).
  *Yêu cầu*: có Official Tapas nhưng muốn bản Hivetoon → `/tai <link> <chương> Hivetoon` chỉ tải đúng nguồn đó; để trống = luật cũ. *Thiết kế (user chốt)*: **(1)** CLI `--group NHÓM`; bot parse token chữ = nhóm (nối dấu cách → "Yen Press"), token số = chương; chỉ nhận với link comix.to. **(2)** `resolve_pin()` khớp tên không phân biệt hoa/thường/khoảng trắng, chuỗi con duy nhất OK; sai/mơ hồ → exit 1 + liệt kê nhóm có trên bộ (thành tin ❌ của bot). **(3)** `candidates_for(versions, pin)` chỉ bản của nhóm đó, không rơi về nhóm khác; chương không có → `nopin` báo + bỏ qua (có dòng riêng ở TỔNG KẾT + báo cáo sớm). **(4)** Ghim BỀN theo chương: sidecar `"pin"`; `_effective_pin()` = lệnh > sidecar; lượt sau không ghim (kể cả auto-check 3h) KHÔNG thay lại bằng Official. **(5)** Bỏ ghim `--group auto` / `/tai <link> 5 auto` → xoá `pin` + luật mặc định ngay. **(6)** Gom quyết định vào `_chapter_plan()` (have/replace/fetch/nopin) dùng chung cho `run()` và `_report_comix_plan()`. **(7)** Sửa kèm lỗi sẵn có: `_load_jobs` rơi cờ `repair` (job vá dở qua restart thành job tải) — nay giữ đủ `repair`+`group`; dedup job `(url, chapters, repair, group)`; nhãn `/trangthai` thêm `[Nhóm]`.
  **Đã kiểm (offline, không Chromium)**: `py_compile` 3 file OK; test nhanh: default `[9,10,12,11,5]` (Yen Press rank 1 trước Tapas 2), pin Hivetoon `[12,11]`; `resolve_pin`: `HIVETOON`/`hive`/`yenpress` đúng, `xyz` → "không có trên bộ", `t` → "mơ hồ (Tapas, Hivetoon)"; plan: đĩa Official+done & pin Hivetoon → `replace`; đĩa Hivetoon pinned + default run + site có Official → `have`; `auto` → `replace`; nhóm không có trên site → `have`/`nopin`. Parse bot: `/tai <url> 5 Hivetoon`, `/tai <url> Yen Press 1-3`, `/tai <url> 5 auto` đúng.
  **Cần làm**: E2E dev `python comic_downloader.py <link comix> --chapters N --group <Nhóm> --out <tmp>` → soi sidecar có `pin`; chạy lại KHÔNG `--group` → chương không bị thay; `--group auto` → thay lại Official. Deploy: push → `/update` + **chạy lại `server-BAT-tudong.bat`** (đụng `supervisor.py`). Nghiệm thu LIVE: `/tai <link> 5 Hivetoon` → tin bắt đầu có "(ghim nhóm [Hivetoon])", báo cáo sớm có "Ghim nhóm", `/trangthai` nhãn `[Hivetoon]`.
  **Còn ngỏ**: chưa có lệnh xem danh sách nhóm của 1 bộ mà không tải (phải mở Chromium — tạm dùng cách gõ sai để tool liệt kê); ghim chỉ theo CHƯƠNG, chưa có ghim cấp bộ cho chương MỚI (cố ý: "để trống = luật cũ").
- **[02/09] Reader — "repair thay ảnh tráo ô nhưng app mở lại cả chục lần vẫn ảnh cũ": ĐÃ code + KIỂM CHỨNG trên dev 8099 (SW thật, đo bằng diagnostic), CHƯA nghiệm thu LIVE trên iPhone** (`reader_server.py`).
  *Gốc (3 tầng, tìm ra bằng chèn diagnostic tạm ghi vào cache `toony-dbg`)*: **(a)** revalidate SWR tái dùng navigation Request `fetch(req)` rớt `TypeError: Failed to fetch` lúc được lúc không → `.catch` nuốt → `PAGE_CACHE` đứng yên **ngay cả trên Chromium** (đo: cache vẫn HTML cũ sau 6 s dù server đã render mới); **(b)** không bọc `e.waitUntil` → iOS tắt SW sớm, càng không bao giờ cập nhật; **(c)** `SW_VERSION` chỉ hash asset → sửa logic SW không đổi ETag `/sw.js` → client 304 → SW cũ mãi (bản dbg đầu không cài được vì thế). Server thì đúng từ đầu (`img_url` stat mtime lúc render, `_dim_cache` khóa mtime, `/img` đọc thẳng file).
  **Fix (1) SW**: revalidate = `fetch(req.url, {credentials:'same-origin', cache:'no-store'})` + `cache.put(req.url, …)`; `e.waitUntil` cho revalidate/put miss/put ảnh/`pumpPrefetch()` (trả promise cạn hàng đợi); `SW_VERSION = "v3-" + sha1(asset list + _SW_TEMPLATE)` (template tách ra, version tính sau). **Fix (2) trang đọc tự vá**: `GET /api/pages/<sid>/<rel>` (`no-store`) → `{version, pages:[{n,url,w,h}]}` (`pages_version` = sha1 tên+mtime, `chapter_pages`); `html_reader` nhúng `D.pv` + `data-f` mọi `<img>`; `reader.js` `syncPages()` ở `pageshow`+`visibilitychange`: lệch version → ảnh chờ đổi `im._url`, ảnh đã/đang tải/lỗi gán `src` mới, cập nhật aspect-ratio (đơn + spread). Chi tiết ARCHITECTURE ⑧b + memory `reader-sw-waituntil-syncpages`.
  **Đã kiểm (dev 8099, series tạm `_test_sync` từ e2e, đã xoá)**: `/api/pages` 200 `no-store` 92 trang; `D.pv`/`data-f` có trong HTML; SW `v3-60da…` controlling. Touch mtime `010.webp` → nav: HTML nhận pv CŨ (SWR) → `syncPages` đổi `D.pv` + `src` 010 sang `?v=` mới, ảnh tải xong, ảnh khác không đụng → cache SW sau revalidate = pv MỚI → nav kế nhận thẳng HTML mới. Trước fix (a): cache cũ mãi (đo). `py_compile` + `node --check` reader.js/sw.js OK.
  **Deploy**: `/update` (chỉ `reader_server.py`; reader restart tự động). Sau update, lần mở ĐẦU trên iPhone: SW mới cài (ETag đổi) → dọn `PAGE_CACHE` cũ → HTML tươi; các lần sau "mở là thấy ngay" nhờ `syncPages`, không cần link mới/xoá cache. **CHƯA nghiệm thu iOS thật** (chỉ Chromium dev); nếu iPhone vẫn kẹt → kiểm link tunnel còn đúng `/link` không (network chết cũng ra triệu chứng y hệt).
  **Còn ngỏ**: rác `?v=` cũ trong `IMG_CACHE` chưa dọn (browser evict); chưa có banner "đang xem bản offline" khi revalidate thất bại.
- **[02/09] comix — ảnh Official lỗi định kỳ do TRÁO Ô: ĐÃ code + KIỂM CHỨNG E2E bằng chính `comic_downloader.py` ở dev (tải ch.1 92/92 sạch; tái hiện chương kẹt → repair vá 9/9 trang). Chờ chạy `/repair` trên server** (`comix_site.py`, `comics_core.py`, `comic_downloader.py`, `check_library.py`, `supervisor.py`).
  *Lịch sử 3 vòng*: (01/09) canvas-`toDataURL` → server 0 trang. (02/09 sáng) đổi sang ghi bản đồ ô (chặn drawImage) + tải lại bằng `img_client` → server VẪN 0 trang + chương 1 bị đóng `.done` sai. (02/09 chiều) **tự chạy tool thật ở dev, tái hiện được lỗi, tìm ra 3 nguyên nhân và sửa cả 3**:
  **(1) `_route_filter` chặn `wowpic*.store`** → `vs(url)` không tải nổi ảnh trong browser → `apply()` không vẽ → `descramble_ops` rỗng IM LẶNG (không có dòng lỗi nào). Đây là gốc "0 trang" của CẢ HAI bản trước; mọi test trên Browser pane "chạy được" là giả vì pane không có filter. Fix: mở `*.wowpic*.store` CHỈ cho resource type `fetch`/`xhr` (thẻ `<img>` type `image` vẫn chặn, không tốn băng thông).
  **(2) CDN trả biến thể xáo KHÁC theo client**: cùng URL p20, browser 116 798 B (sha 4f6d…) vs requests 116 598 B (sha 4073…) → tải lại bằng `img_client` lệch bản đồ (p10 trùng chỉ là may). Fix: tee `window.fetch` trong `DESCRAMBLE_JS` bắt ĐÚNG bytes `vs` nhận (base64 kèm ops); Python xếp lại trên bytes đó; bỏ hẳn tải lại. Biến thể ổn định theo client (2 fetch no-store trùng hash).
  **(3) repair đóng `.done` sai khi trang `s:1` THIẾU**: `still` chỉ đếm file đang có → 0 trang vẫn "fixed" → `_mark_done` → `/tai` báo "Đã xong trước" (chương 1 kẹt: 83 sạch + 9 thiếu + `.done`). Fix: kích hoạt repair cả khi có khoảng trống số trang; `still` đếm cả trang `s:1` thiếu; chỉ đóng `.done` khi hết sót.
  *Gốc (đã dump payload đã-giải-mã, xác minh 5 chương Farmer of Spirits)*: payload trang có cờ `s`; `s:1` = trang bị **cắt lưới ô + xáo vị trí**, đúng MỖI TRANG THỨ 10 (10,20,30…). URL trả bytes XÁO cho mọi client (không có URL sạch riêng); reader hiển thị sạch nhờ chunk `secure-*.js` (export `t`=`vs`) giải-xáo VẼ LÊN `<canvas>` qua rAF. `fetch_pages` cũ chỉ đọc `url`, bỏ cờ `s` → lưu bytes xáo; `is_known_broken` chỉ tra sổ URL-hỏng nên không bắt (file webp hợp lệ) → chương xáo vẫn `.done` → chạy lại/`--recheck` BỎ QUA. Mọi chương Official đã tải đều dính (~9 trang/chương).
  **Fix** (chi tiết + lý do ở ARCHITECTURE mục comix_site + memory `comix-scramble-s-flag`): **①** `fetch_pages` trả `[{"url","s"}]`; `run()` tách trang thường (HTTP như cũ) vs trang `s:1` → `ComixSession.descramble_pages(url_path, pairs, img_client)`: **(a)** `descramble_ops()` chạy `DESCRAMBLE_JS` (`page.evaluate`) — `import(secure.js)` (dò URL động qua Performance API), ép rAF đồng bộ, **chặn `drawImage`** lúc gọi `vs(url).apply(canvas)` để GHI bản đồ ô (1 lệnh nền + N lệnh chép ô `sx,sy,sw,sh→dx,dy,dw,dh`); KHÔNG đọc canvas. **(b)** `img_client` tải LẠI ảnh xáo (byte ổn định theo URL), `_unscramble_ops()` xếp lại bằng PIL (crop→resize-nếu-khác→paste theo thứ tự) → webp sạch. KHÔNG reverse permutation trong secure.js (obfuscate) — chỉ quan sát drawImage. **②** `--repair-scramble` (comix): dò offline từng chương (bỏ nhanh chương sạch, không chạm mạng), chương còn ảnh xáo → lấy payload bản đang có trên đĩa (khớp `chapterId` sidecar / hoặc đòi khớp số trang) → giải-xáo lại đúng trang `s:1`, ghi đè + đóng lại `.done`; KHÔNG tải chương mới. **③** `comics_core.looks_scrambled()` (seam-energy biên ô bằng PIL, ngưỡng 4.0, không numpy): GUARD trong `run()` (trang `s:1` còn dấu xáo = chưa xong → không `.done` → tự bù) + trigger repair + audit `check_library.py`.
  **Đã kiểm (E2E thật, dev, `--out` thư mục tạm, KHÔNG ghi đè route)**: `py_compile` 5 file OK. `debug_ch1.py` qua `ComixSession`: p10+p20 → 26 ops + bytes → `looks_scrambled=False`. **`comic_downloader.py <url> --chapters 1`** (đường `/tai`): "giải-xáo 9 trang tráo ô" → **92/92 ảnh, cả 9 trang s:1 sạch, `.done=True`**, rc=0; p050 xem tận mắt sạch. **Tái hiện chương kẹt** (xoá 010–090, GIỮ `.done`) → **`--repair-scramble --chapters 1`**: "Đã sửa: 1 chương (9 trang giải-xáo)" → 92/92, 9 trang sạch, `.done` giữ, rc=0. Trước đó cũng đã dựng lại p10/p20 sạch bằng `_unscramble_ops()` trên bytes bắt từ fetch-tee. Detector: xáo 8.6–22 vs sạch 1.1–1.7.
  **Vì sao bền**: ghi tham số drawImage + tee fetch KHÔNG cần compositing/đọc canvas → chạy được cả khi **server không màn hình / RDP ngắt**; pixel do PIL lo → **kiểm chứng offline được**. Lưu ý chưa xác minh: detector có thể báo nhầm 1 trang sạch (đó là cách chương 1 lọt vào nhánh "fixed" ở vòng trước) — hậu quả đã bị chặn bởi fix (3), nhưng nếu thấy repair "chạm mạng" ở chương thực ra sạch thì xem lại ngưỡng 4.0.
  **Cần làm trên server**: `/update` → `/repair <link> 1` (chương 1 đang kẹt sẽ tự được vá — kích hoạt theo khoảng trống số trang) → mở trang 10 xem sạch → `/repair <link>` cả bộ → các bộ Official khác.
  **Lệnh bot `/repair`** (thêm 01/09, trong `supervisor.py`): `/repair <link…> [chương]` — gom NHIỀU link (mỗi link 1 job) `--repair-scramble` vào CHUNG hàng đợi tải, chạy TUẦN TỰ 1 worker (chung queue với /tai; dedup (url,chapters,repair) nên không đè job /tai; nhãn 🧩 trong /trangthai). Báo per-job GIỐNG /tai: ack "🧩 Đã thêm N bộ" → "🧩 Bắt đầu SỬA TRÁO Ô" → "✅ Sửa tráo ô xong" + bảng số liệu (đã sửa X chương/Y trang, còn sót, không lấy được URL) — KHÔNG phải digest gộp. `comix_site` in progress mỗi chương để log luôn tiến (tránh stall-watchdog 1200s kill oan khi quét chương sạch). Vẫn dùng được CLI `python comic_downloader.py <url> --repair-scramble`. **Còn ngỏ (cosmetic, user đã biết — chưa sửa vì nhỏ)**: tin HUỶ/TREO của job vá vẫn dùng chữ "tải"/gợi ý "/tai" (chức năng đúng, chạy lại /repair là bù, idempotent); chưa có "/repair all" theo watchlist (phải liệt kê link).
  **Deploy**: push (`day-len.bat`) → trên server `/update` (bot). Vòng 02/09 CHỈ đổi `comix_site.py` (downloader chạy tiến trình mới mỗi job nên tự nạp) → `/update` là đủ cho phần giải-xáo. LƯU Ý: lệnh bot `/repair` nằm trong `supervisor.py` (đổi ở vòng 01/09) — nếu **chưa RESTART supervisor** kể từ lần đó thì phải chạy lại `server-BAT-tudong.bat` một lần mới có `/repair`; `/update` tự nhắc khi supervisor.py đổi. Muốn chạy repair mà chưa restart supervisor: dùng CLI `python comic_downloader.py <url> --repair-scramble`.
- **[29/08] Reader — nút "reading" trỏ chương CŨ (đọc dở ch7, mở lại vào ch6) — ĐÃ code + test dev + nghiệm thu browser dev, CHƯA nghiệm thu LIVE trên server** (`reader_server.py`, README.md).
  *Gốc (đã chứng minh bằng đọc code + tái hiện stale-doc trong browser dev)*: con trỏ đọc dở được **bake cứng vào HTML** ở 3 chỗ — nút "Chapter X - reading" trang series (`html_series` chapbtns), nhãn `.fcm`/`FOLLOWDATA.label` trang home, và `D.y` (vị trí cuộn) trang reader — mà HTML đi qua **SW stale-while-revalidate** (trả bản cache cũ trước, revalidate ngầm) LẪN **bfcache** (DOM đóng băng khi back) → mở lại là thấy con trỏ của PHIÊN TRƯỚC, lệch đúng 1 nhịp. Ghi progress thì `_save_users_locked()` atomic NGAY mỗi op (đã xác minh) nên dữ liệu server luôn đúng — chỉ HTML hiển thị là cũ. Purge-page KHÔNG dùng được: không với tới bfcache.
  **Fix (①+ theo khuôn syncBM/syncCounts sẵn có):** **①** `SERIES_JS.syncReading()` — vá nút reading + làm-mờ-đã-đọc **tại chỗ từ nguồn sống** (guest: `LS.getProg` đồng bộ — guest GIỜ MỚI CÓ nút reading, trước server render trung tính không ai vá; đã đăng nhập: fetch `/api/state` + so `ts` với mirror), chạy lúc load + `pageshow(persisted)` + `visibilitychange`; nhãn tái tạo từ `a.ch[data-num]` (đúng công thức server `fmt_num(chapter_num)`); vá xong `pf([href])` prefetch lại. **②** **mirror localStorage per-account**: `ls.js` thêm `mget/mset/newer` (key `toony_prog_u_<UK>`, `UK` = sha1(uid)[:8] server nhúng — KHÔNG nhúng uid thật vì uid là cookie auth mà HTML nằm trong SW cache); reader `sendPos` (đã đăng nhập) ghi server + mirror; khôi phục cuộn so `mp.ts > D.ts` → mirror thắng bake cũ. Mọi entry progress (LS + server) giờ có `ts` + `name`. **③** `HOME_JS.applyLabels()` vá `.fcm` + `FOLLOWDATA.label` trong cùng fetch `syncBM` (giờ chạy cả lúc LOAD, không chỉ bfcache). **④** server `update_user_data` op progress: **ts guard chống pagehide-race** — chặn write CŨ HƠN trong cửa sổ 30s (rời ch6 bắn keepalive về SAU write ch7 → không đè ngược nữa); thiếu ts (JS cũ) thì nhận (tương thích). Server vẫn render nút reading best-effort (KHÔNG đổi sang trung tính — tránh flash Latest→reading mỗi lần cho tài khoản).
  **Test dev đã chạy**: `py_compile` OK; `node --check` cả 6 JS asset OK; smoke test guard ts 4 ca (nhận mới / chặn race 1s / nhận lệch >30s / nhận thiếu-ts) OK; render 3 trang nhúng đúng `UK`/`SDATA.uk`/`D.ts` (login vs guest). **Nghiệm thu browser dev (server 8099)**: guest — LS có progress → reload → nút thành "Chapter 365 - reading" đúng href+nhãn; logged-in — mirror ts mới hơn thắng server (nút đổi theo mirror sau `pageshow(persisted)` giả lập); home logged-in — card Bookmarked hiện nhãn tươi nhất (mirror thắng). *Không test được tầng SW sống trong browser sandbox (đã biết từ 25/08) + browser dev có quirk không gửi cookie theo navigation — nhưng chính nhờ đó đã tái hiện được "trang stale" và thấy client patch tự sửa đúng.*
  **Deploy = `/update` qua bot** (chỉ `reader_server.py`; JS đổi → `SW_VERSION` tự đổi theo hash → SW mới activate tự dọn PAGE_CACHE cũ, các trang "ch6 kẹt" được flush luôn).
  **Còn ngỏ**: (a) khe đua sub-giây cho tài khoản (bấm nút trước khi fetch `/api/state` về — trước đây sai cả phiên, giờ chỉ còn <1s; guest = 0 vì LS đồng bộ). (b) Đổi thiết bị lệch giờ >30s + chuyển máy trong <30s → 1 write bị guard chặn oan (tự hồi khi cuộn tiếp). (c) LS entry ghi bởi JS đời cũ thiếu `ts`/`name` → nhãn home giữ bản server tới khi đọc lại 1 lần (tự lành).
- **[25/08] Reader — Join/tách/đảo trang đôi báo "Invalid action" oan — ĐÃ code + test dev (tái hiện + xác nhận fix ở tầng server) + parse OK, CHƯA nghiệm thu LIVE trên trình duyệt thật/SW** (`reader_server.py`).
  *Gốc (đã TÁI HIỆN bằng server thật)*: join THÀNH CÔNG rồi `location.reload()`, nhưng navigation-SWR của SW trả **HTML cache TRƯỚC join** (nút Join cũ còn) và handler join KHÔNG purge như bookmark → user tưởng chưa ăn, bấm lại đúng cặp → `find(a)/find(b)` chặn → "Invalid action". *SW-layer KHÔNG chạy được trong trình duyệt in-app của sandbox* (đăng ký `/sw.js` báo "unknown error", dù curl 200) → phần "SW trả bản cũ" chứng minh bằng đọc code + khác biệt HTML trước/sau (11→10 nút, Join(00→01) mất, spread 1→2), KHÔNG chạy SW sống.
  **Fix 3+1 lớp** (`reader_server.py`): **①** reader thêm `purgeAndReload()` — join `ok:true` → postMessage `{type:'purge-page',url}` chờ SW ack (MessageChannel + timeout 400ms) rồi reload. **②** SW `purge-page` trả ack qua `e.ports[0]`. **③** `modify_spreads` join **idempotent** — `a`&`b` đã là 1 cặp → trả `True`; chỉ khi dính cặp KHÁC mới `False`. **④** bump `SW_VERSION` `v1-`→`v2-` để activate dọn `PAGE_CACHE` cũ. Chi tiết + đánh đổi: ARCHITECTURE mục "Ghép/tách trang đôi báo Invalid action oan".
  **Test dev đã chạy** (server cổng 8099, `spreads.json` sao lưu+khôi phục nguyên trạng): join mới→`ok:true`; join TRÙNG cặp→**`ok:true`** (trước là "Invalid action"); join `01→02` khi `01` đã ghép `00`→vẫn `Invalid action` (đúng). `/sw.js` lên `v2-…` + có ack. **CHƯA**: nghiệm thu LIVE trên iPhone/Chrome thật — join 1 cặp → sau reload thấy NGAY spread (không cần reload lần 2), không còn "Invalid action" khi lỡ bấm lại.
  **Deploy = `/update` qua bot** (chỉ `reader_server.py`). Sau deploy user cần **đóng hết tab reader 1 lần** hoặc chờ SW `v2` activate để cache cũ được dọn.
  **Còn ngỏ**: "cặp mồ côi" (file đổi tên/đổi định dạng, vd jpg→webp, hoặc đổi tên folder làm `sid` lệch — đã thấy bằng chứng key `Pokemon Special_webp` trong `spreads.json` trong khi folder giờ là `Pokemon Special`) vẫn để 1 trang lẻ kèm nút Join mà `find()` chặn; idempotency KHÔNG che (đúng bản chất). Nếu user báo lại "Invalid action" ở bộ cụ thể → khả năng cao là dọn `spreads.json` tay (xoá key mồ côi) / hoặc làm migrate sid khi đổi tên folder (chưa làm).
- **[24/08] Giữ supervisor SỐNG (Hướng A) + vá bug Service Worker "Returned response is null" — ĐÃ code + compile/parse OK + push; phần WATCHDOG/pause/TAT hỏng suốt tới 25/09, đã thay + NGHIỆM THU LIVE ở mục [25/09]** (`supervisor.py`, `reader_server.py`, `watchdog.ps1` [mới, nay là `watchdog.pyw`], `server-BAT-tudong.bat`, `server-TAT-tudong.bat`, `notify-config.example.json`).
  *Bối cảnh sự cố 24/08:* người của cty vào server đóng cửa sổ/kill supervisor → supervisor chết, reader (tiến trình con RIÊNG, `NO_WINDOW`) vẫn phục vụ; heartbeat nằm trong supervisor nên tắt theo → healthchecks báo "down" lúc 16h mà web vẫn chạy, **không bao giờ "up"** vì task `ToonyServer` là **onlogon (chỉ chạy lúc đăng nhập, KHÔNG keep-alive)**. Ràng buộc: comix mở Chromium HEADFUL để NGƯỜI tick Cloudflare → **KHÔNG** dùng Windows Service Session 0 (Chromium vô hình). Chọn **Hướng A**: giữ phiên tương tác (autologon) + auto-restart.
  **① supervisor chạy ẨN** bằng `pythonw.exe` (bỏ cửa sổ đóng-được); log vẫn ở `.reader-meta/supervisor-log.txt` + thêm **xoay file** khi >2MB (`LOG_MAX`, giữ 1 bản `.1`). Sửa `server-BAT-tudong.bat` dùng `%PYW%` cho cả task onlogon lẫn `start`.
  **② WATCHDOG** `watchdog.ps1` + task `ToonyWatchdog` (`schtasks /sc MINUTE /mo 2 /it`): mỗi 2' quét CommandLine xem `supervisor.py` còn chạy không, chết → `Start-Process` pythonw bật lại (ẩn, trong phiên đăng nhập nên Chromium comix vẫn hiện). Bắt MỌI kiểu chết (crash/kill/đóng cửa sổ). Ghi `watchdog-log.txt` riêng.
  **③ reader tự-ping** check RIÊNG: `reader_heartbeat_loop()` mỗi 5' TỰ gọi `127.0.0.1:<port>/` (readiness, bắt cả reader-treo) rồi ping `reader_heartbeat_url`. 2 check độc lập → nhìn cặp tín hiệu biết CÁI NÀO chết. Trống url = tắt. **Cần tạo check thứ 2 ở healthchecks.io + điền `reader_heartbeat_url`.**
  **④ cờ pause** `.reader-meta/toony-paused.flag`: `server-TAT-tudong.bat` ĐẶT cờ (trước khi giết) + xoá cả 2 task + kill supervisor/reader theo CommandLine (phòng pid lạc) → watchdog KHÔNG hồi sinh (để đồng nghiệp tắt máy test); `server-BAT-tudong.bat` xoá cờ khi bật. **KHÔNG tạo shortcut Desktop** (user chốt: bật/tắt bằng .bat trong folder).
  **⑤ vá bug SW (gây màn "FetchEvent.respondWith … Returned response is null"):** navigation handler cũ `return hit||net` với `net=fetch().catch(()=>hit)` → khi KHÔNG có cache + mạng lỗi (link tunnel đã chết) thì trả `undefined` → respondWith null → Safari không mở nổi trang. Sửa: có cache → trả ngay + revalidate ngầm nuốt lỗi; không cache → `try fetch / catch` **LUÔN trả 1 Response** (lỗi → trang 503 "Không kết nối được máy chủ, lấy link mới"). *Đây chính là triệu chứng iPhone 24/08: web vào được (SW cache phục vụ shell+ch1 đã đọc) nhưng ch2 chưa cache → ra mạng → tunnel chết → ảnh fail + Next ra null.*
  **Test dev**: `py_compile` supervisor+reader OK; parse `watchdog.ps1` OK. **CHƯA nghiệm thu LIVE**: kill supervisor tay → ≤2' tự lên lại + `watchdog-log.txt` có dòng; `server-TAT` → KHÔNG tự lên lại; reboot → 2 task lên + 2 check xanh; iPhone với link MỚI → ch2 tải được.
  **Deploy = push (`day-len.bat`) → trên server `/update` (hoặc cap-nhat.bat) → RỒI chạy lại `server-BAT-tudong.bat` MỘT lần** để đăng ký task `ToonyWatchdog` (task KHÔNG tự tạo qua /update). *Chi tiết & lý do trong memory `supervisor-keepalive-huong-a`.*
  **Còn ngỏ:** (a) chưa rõ sản phẩm test của đồng nghiệp có đụng cổng 8080 không — trùng thì đổi `reader_port`. (b) Link quick-tunnel ĐỔI mỗi lần restart → mỗi lần supervisor lên lại là link mới (gốc của "link chết" iPhone); cách trị tận gốc = named-tunnel + domain (chưa làm).
- **[23/08] Reader — nút ✕ xoá ô search (cả tìm CHƯƠNG lẫn tìm TRUYỆN) — ĐÃ code + compile OK + push, CHƯA nghiệm thu LIVE** (`reader_server.py`).
  Layout do user chốt (2 câu hỏi): **giữ kính lúp bên PHẢI, X THAY CHỖ** (ô rỗng = kính lúp; có chữ = ✕ đúng vị trí đó) + **có phím Esc**. Dùng chung `.chsearch` cho cả 2 ô.
  **CSS** (`.chsearch`): thêm `.chsearch.has-val .chsearch-ic{opacity:0}` (ẩn kính lúp khi có chữ) + `.chclear` (button phủ đúng chỗ kính lúp, hit-area 36×36, `pointer-events` chỉ bật khi `.has-val`, fade .15s, hover/active sáng dần). **Hằng** `CLEAR_BTN` (button `tabindex=-1` + SVG ✕) chèn sau `SEARCH_SVG` ở cả `homesearch` và `chhead`.
  **home.js**: gộp toggle `has-val` **vào trong** `applyHomeFilter()` → đồng bộ nút X ở MỌI đường vào (gõ / load / bfcache `reconcileSearch`); `clearHomeq()` = xoá value + **xoá `sessionStorage['homeq']`** (chống bfcache kéo chữ về) + lọc lại + giữ focus; wiring click ✕ + keydown Esc. **series.js**: tách filter inline thành `applyChFilter()` (thêm toggle `has-val`), `clearChq()` xoá + lọc lại + focus; wiring ✕ + Esc. **Test dev**: `py_compile` OK. **CHƯA**: xem live (gõ → hiện ✕, bấm/Esc → xoá sạch + hiện lại kính lúp + giữ focus; back không kéo chữ về ở home). **Deploy = `/update` qua bot** (chỉ `reader_server.py`).
- **[23/08] Reader — 2 bug: (1) search kẹt khi back, (2) số chương cập nhật chậm — ĐÃ code + test dev, CHƯA nghiệm thu LIVE** (`reader_server.py`).
  Làm trọn B1–B6 sau khi rà soát tổng thể freshness (kết luận: chỉ 2 gốc thật + 1 điểm phụ; ảnh/static/API đã chuẩn).
  **Bug 1 — search giữ trạng thái khi back (B1+B2):** ô search trống nhưng lưới vẫn lọc sau khi back — iOS Safari
  xoá `value` ô search qua bfcache nhưng GIỮ `display:none` của card, mà bộ lọc chỉ chạy ở sự kiện `input` →
  lệch pha, không bấm được truyện khác. Fix trong `HOME_JS`: tách bộ lọc thành hàm idempotent `applyHomeFilter()`;
  lưu keyword vào `sessionStorage['homeq']` **bền theo phiên tab** (bỏ `removeItem` cũ); lúc load + `pageshow`
  (persisted) → `restoreHomeq()` tái lập value rồi `applyHomeFilter()`. Chuẩn UX quốc tế = "list state restoration
  on back" (giữ keyword+lọc+scroll như Google/Amazon). `homey` vẫn one-shot cho admin `reloadKeepSearch`.
  **[FOLLOW-UP 23/08 — trị timing iOS]** Bản đầu vẫn lỗi trên iOS: back thì ô TRỐNG nhưng list VẪN lọc, F5 mới hiện
  keyword. Gốc: iOS Safari áp phần khôi phục form-control của RIÊNG nó **SAU** `pageshow` → ghi rỗng đè lên lần
  restore đồng bộ của tôi (list vẫn lọc vì `applyHomeFilter` đã chạy trước). Fix (Cách C): nhánh `persisted` **HOÃN**
  reconcile bằng **double-`requestAnimationFrame` + 1 `setTimeout(120)` dự phòng** → `reconcileSearch()` ép lại value
  từ sessionStorage + lọc lại, có **chốt so-sánh** `hq.value===saved` nên chạy nhiều nhịp không nháy/không applyHomeFilter
  thừa. (F5 đã chứng minh init path đúng → chỉ sửa nhánh bfcache.) home.js mới `?v=8388c4bccc`.
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
- **08/10: hitomi — folder giữ CẢ 2 phần tên "Romaji | English" (`|` → `-`) + ` [hi{id}]`; ảnh WebP (không AVIF); không làm `?lang=`; không nhận trang `-all.html` và loại `anime`** — user chốt; WebP đủ độ phân giải gốc + đồng bộ thư viện/iOS (AVIF nhẹ ~50% nhưng rủi ro hiển thị); mỗi bản dịch trên hitomi đã là 1 link riêng.
- **08/10: hentaivnreal — folder = tên truyện KHÔNG gắn mã (kể cả one-shot); chương không số lẻ tẻ = chương liền trước + 0.5 (KHÁC lxmanga: không lật cả bộ sang số vị trí); sửa charset bằng tham số `encoding` của `get_text` ở core** — user chốt cả 3 đề xuất; tên site là tên đầy đủ (ít trùng), lật số vị trí = đổi folder → tải lại cả bộ, tự giải mã lại mojibake sẽ hỏng nếu server thêm charset sau này.
- **07/10: Ngôn ngữ MangaDex đi trong URL (`?lang=`), không thêm tham số bot riêng; bản khác EN vào folder `[XX]` riêng** — URL là thứ duy nhất chảy nguyên vẹn qua hàng đợi/watchlist/check_updates nên không phải sửa supervisor; folder riêng tránh trộn chương EN/VI cùng số.
- **01/10: 18+ để CHUNG thư viện; one-shot = folder `tên ngắn + [nh{id}]/[fc{id}]`, 1 `Chapter 1`, chặn `into:`; PNG hentaivnx sẽ chuyển WebP NGAY LÚC TẢI** — user chốt; tên ngắn trùng giữa bản dịch, tên đầy đủ dễ vượt MAX_PATH; chuyển WebP sau khi tải sẽ làm core/`check_library` tưởng thiếu `NNN.png`.
- **01/10: Ảnh chương ra khỏi cache SW (giao HTTP cache `immutable`), không dùng LRU trong SW** — user chọn; kho ảnh SW không giới hạn là nguyên nhân đo được của màn trắng khi mở app (caches.open lạnh 9ms→1.3s trong 1 ngày); HTTP cache do trình duyệt tự giới hạn/dọn. Đổi lại mất đọc offline chương cũ.
- **01/10: Trang chương không bao giờ chờ đo hết kích thước ảnh** (ngân sách 0.25s + đo nền + quét cả thư viện ưu tiên thấp) — tập ~290 trang mở lần đầu từng mất 12–13s.
- **30/09: moetruyen = provider thường + móc `render_pages` trong core (không custom_run, không reverse IMGX)** —
  site không có URL ảnh; chụp trang hiển thị giữ được toàn bộ vòng tải chung (.done/bù trang/tổng kết/into:/
  check_updates). KHÔNG đào worker/page-access vì site gửi `X-AI-Policy: no-reverse-engineering`. Lưu WebP **q90**
  (user chốt; chỉ nặng hơn q85 ~4%). Ghi chú: comix VẪN re-nén q85 lúc tải (`--comix-q` mặc định 85) — user tưởng
  đã bỏ, đã đối chiếu code: chưa bỏ.
- **28/09: Đo trước khi sửa phần "trắng khi mở app"; chỉ sửa ngay phần "bấm đọc đơ" (đã đủ chắc)** — user chốt làm cả hai: bộ đo 3 nguồn (iPhone/SW/server) dồn về 1 chỗ trên server + bot `/diag` gửi link để Claude tự đọc. Giả thuyết cũ "IMG_CACHE phình → iOS evict" đã BỊ BÁC bởi số đo (21.7MB, không tăng theo ảnh); giả thuyết "origin quick-tunnel đổi" không phải nguyên nhân khi dùng bình thường (link mới vẫn trắng). User KHÔNG muốn dùng domain (giữ quick-tunnel).
- **28/09: Chạm (touch) KHÔNG prefetch** — `pointerdown` bắn trước khi trình duyệt biết là cuộn; prefetch theo ý định chỉ hợp với chuột. Cú bấm thật tự điều hướng, SW gộp nếu có lượt đang chạy.
- **25/09: Bỏ task onlogon `ToonyServer`, watchdog là nơi DUY NHẤT bật supervisor** — `schtasks /create` gắn sẵn giới
  hạn 72h cho task; tiến trình task bật trực tiếp bị giết sau 72h (đã bị thật 21→24/09). Supervisor do watchdog
  `Start-Process` là tiến trình riêng, task watchdog kết thúc sau vài giây nên không dính giới hạn. Một cơ chế thay
  hai, hết khe 2 đường bật chen nhau thành 2 bản (409). Đánh đổi chấp nhận: sau reboot lên chậm ≤2'.
- **29/08: Con trỏ "đang đọc" (nút reading / nhãn .fcm / vị trí cuộn) = client-sync từ nguồn sống + mirror
  localStorage per-account có ts, KHÔNG purge-page và KHÔNG render trung tính** — purge không với tới bfcache;
  render trung tính gây flash Latest→reading MỖI lần cho tài khoản (phạt ca thường để trị ca hiếm). Server vẫn
  bake best-effort, client vá lại tại chỗ (cùng khuôn syncBM/syncCounts đã chạy ổn). Mirror per-uid (key hash
  ngắn `UK`, không nhúng uid thật vào HTML vì uid = cookie auth) + `ts` mọi entry → so được độ tươi giữa 3 nguồn
  (bake/server/mirror), mirror còn tự chữa lành server nếu bị pagehide-race đè (lần đọc kế ghi giá trị đúng lại).
  Guard ts phía server chỉ chặn write cũ hơn trong CỬA SỔ 30s — đủ bắt race (cỡ giây) mà không khoá nhầm
  chuyển-thiết-bị lệch giờ (cỡ phút). Bonus: guest có nút reading (trước không có vì server không biết LS).
- **23/08: Nút ✕ xoá search — giữ kính lúp bên PHẢI + X thay chỗ (không thêm cột icon), kèm Esc** — user chọn phương án
  ít đổi layout nhất (thay vì kính-lúp-trái/X-phải kiểu Asura). Toggle bằng 1 class `.has-val` trên `.chsearch` (CSS lo
  ẩn/hiện) + gộp việc toggle vào chính hàm lọc để đồng bộ ở mọi đường vào; clear ở home phải xoá luôn `sessionStorage['homeq']`
  nếu không logic khôi phục bfcache sẽ kéo chữ về (bug). Dùng chung 1 CSS + 2 hàm clear cho cả 2 ô.
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
- **[hitomi — nghiệm thu server]** (ĐÃ push 9cfbaed 08/10) `/update` → `/tai https://hitomi.la/galleries/4238970.html` → xem reader (folder `Taiken Sasete! Onii-chan - Give Me Experience Onii-chan! [hi4238970]`, bìa `cover.webp`, 30 trang). Lỗi 404 hàng loạt trên server → kiểm Referer / log "gg.js đổi định dạng" / host `ltn.` trong vỏ trang.
- **[hentaivnreal — nghiệm thu server]** (ĐÃ push 9cfbaed 08/10) `/update` → `/tai https://hentaivnreal.com/truyen/rape-famale-boss-rape-female-boss/oneshot` → xem reader (bìa `cover.jpg`, 26 trang). Bộ dài thử 1–2 chương (vd `/tai https://hentaivnreal.com/truyen/sextoy-ket-noi-khong-day 13`).
- **[MangaDex `?lang=` — nghiệm thu]** (đã push 7f4c1df) `/update` → `/tai https://mangadex.org/title/8db5faa9-811e-4b1f-8d00-1814ec68b96c/x?lang=vi 1` (hoặc bộ user muốn, xem trên MangaDex có cờ VN) → folder `"… [VI]"` trên reader, đúng bản tiếng Việt.
- **[Provider 18+ — deploy & nghiệm thu]** (đã push 94f3f75) `/update` → `/tai` 1 link mỗi site trên server: nhentai.to, hentaifc, hentaivnx (1 chương PNG → thấy `.webp`), **lxmanga 1 chương** (= bài thử mạng/Chromium/Cloudflare trên server; lỗi thì đọc log `/tai`: chặn mạng / Cloudflare / site đổi). Xem reader: bìa `cover.avif`(JPEG) + `cover.jpg`(WebP) hiển thị đúng.
- **[Nghiệm thu sửa 01/10]** `/update` → `/diag clear` → dùng 1–2 ngày (gồm mở app sau khi để nền lâu, mở 1 tập/chương chưa đọc, bấm Next liên tiếp) → `/diag` gửi link. Kỳ vọng: [4] "mở cache: SW vừa khởi động" trung vị < 50ms và không tăng theo ngày; [10] dung lượng web app vài MB thay vì trăm MB; [6] `get_library` ~0ms; prefetch chương kế có hit (Next byte đầu vài ms); [7] không còn render `/read/` >2s. Xong thì `/diag off`.
- **[moetruyen — deploy & nghiệm thu server]** commit/push → `/update` → `/tai https://moetruyen.net/manga/1200-dragon-quest-emblem-of-roto 1`
  (hoặc bộ user muốn): cửa sổ Chromium `moe-profile` hiện trên server, 72/72, không stall; reader hiển thị
  `Chapter 1 - …` đúng; `/watch` bộ đó → auto-check báo `ok`. Khi gặp bộ có chương lẻ: kiểm dạng URL `/chapters/N.5`.
- **[Bộ đo + sửa đơ — deploy & đo]** commit/push → `/update` → restart supervisor → `/diag clear` → kịch bản thử (xem mục Đang làm) → `/diag` → gửi link. Đọc báo cáo để CHỐT: (R1) SW khởi động trên iOS có chiếm phần lớn thời gian trắng không (`workerStart`→`fetchStart`, SW `age`<2s) vs `responseStart`/server `ms`; (R4) `/api/state` dung lượng + chênh login/khách; "đứng luồng" lúc list chương hiện dở; `chsort` còn sống sau xoá dữ liệu (phần bộ nhớ nào sót). Ứng viên sửa tiếp tuỳ số liệu: HTML network-first timeout ~1.5–2s (+ Navigation Preload nếu iOS hỗ trợ) thay SWR; LRU `PAGE_CACHE`/`IMG_CACHE`; `/api/state` home bỏ `read`; `_library_signature()` hết chạy mỗi request (xem `lib` trong báo cáo server).
- **[Nút reading tươi — nghiệm thu LIVE]** `/update` qua bot (chỉ `reader_server.py`). Kịch bản đúng bug gốc:
  đăng nhập trên điện thoại, đọc dở chương N, **Next sang N+1**, đọc dở rồi TẮT hẳn app/tab → mở lại link →
  vào trang truyện: nút xanh lá phải ghi **"Chapter N+1 - reading"** NGAY LẦN ĐẦU (không cần F5), bấm vào phải
  ĐÚNG chương N+1 và trôi về đúng chỗ đang đọc dở. Thêm: back từ reader về trang truyện (bfcache) → nút cập nhật
  theo chương vừa đọc; card Bookmarked ở home ghi đúng chương; guest (chưa đăng nhập) đọc dở 1 chương → trang
  truyện có nút "reading" (tính năng mới). Sau deploy nhớ **đóng hết tab reader 1 lần** cho SW mới activate.
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
- **[Auto-start nghiệm thu — chỉ còn bước reboot, xem mục [25/09]]** Lần Windows Update/reboot kế: không đụng gì →
  ~2-3' sau khi Windows tự đăng nhập: Telegram link mới + heartbeat 🟢 + `/trangthai` trả lời +
  `watchdog-log.txt` có dòng "da bat lai". (Không còn task `ToonyServer` / cửa sổ log.)
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
- **hentaivnreal**: (a) Cloudflare cache trang bộ ~30' (+10' stale) → chương mới trễ ≤~40' so với trang chủ (đã thấy trang chủ "Chap 10" khi trang bộ còn 9); (b) bộ tuyển tập đánh số VỊ TRÍ → site xoá/chèn chương giữa chừng thì số lệch; (c) ngưỡng thật/tuyển tập theo tỉ lệ → bộ đổi ngưỡng (vd tuyển tập ≥200 chương, hay bộ thường thêm nhiều chương không số) sẽ đổi folder (thêm/bỏ ` [HVR]`) — hiếm; (d) dữ liệu đọc từ turbo-stream React Router: site đổi framework → `list_chapters` rỗng (in cảnh báo), ảnh còn dự phòng `<img data-idx>`.
- **lxmanga bị nhà mạng chặn SNI** (PC Viettel: requests/curl đứt handshake) — Chromium Playwright qua nhờ ECH (`sni=encrypted`) + tự qua CF ~3s; pane browser của app Claude (Electron) bị LẶP challenge sau tick → đừng dùng pane để thử site CF. Nếu CF/nhà mạng tắt ECH → cần VPN/WARP trên server. Số vị trí của bộ tuyển tập lệch nếu site xoá/chèn chương giữa chừng; nhãn chương bị site cắt ~23 ký tự. Auto-check lxmanga = xếp job tải mỗi lượt (mở Chromium ~20s/bộ).
- **Sửa 01/10**: (a) đọc lại chương cũ có thể tải lại ảnh qua tunnel nếu iOS đã dọn HTTP cache (đánh đổi đã chốt); (b) [đã bỏ 07/10] luồng `_dims_sweep` quét cả thư viện; (c) chương mới tải về hiện trên web sau ~10s + thời gian quét (trước: ~1–2s); (d) lần đầu mở chương có ảnh chưa đo: ảnh mang tỉ lệ ước lượng tới khi tải về (trang có thể "nhảy" nhẹ phía dưới vị trí đang đọc).
- **qqcomvn khi Cloudflare chặn HTTP: ĐÃ SỬA 01/10 (chưa push)** — bìa `/media/book/…` bị 403 → trước đây
  traceback exit 1 trước mọi chương; nay core coi bìa là phụ (cảnh báo, tải chương tiếp). Test dev: thư mục
  trống, `--fetch auto` → tự leo Chromium, bỏ bìa, ch3 53/53, rc 0; Zet vẫn tải bìa. Folder qqcomvn tải lúc site
  chặn sẽ THIẾU `cover.*` (reader dùng trang đầu) — lượt tải sau khi site mở tự bù bìa.
- **moetruyen phụ thuộc giao diện site**: đổi selector/cơ chế IMGX hoặc bật `capture-guard` → 5 trang liền hụt
  = `Blocked` dừng sạch (không lưu rác) + HTML mẫu `.reader-meta/moe-debug/`. Chụp chậm (~1.2s/trang) và cần
  phiên desktop như comix. `check_library` báo nhầm "tráo ô" trang gần trắng — đừng `--repair-scramble`.
- **Bộ đo ghi 1 dòng cho MỌI request** (kể cả từng ảnh) + 1 beacon/trang — nhẹ nhưng không miễn phí; xong đợt đo thì `/diag off` (file cờ, reader kiểm ≤10s/lần). Kho kích thước `dims-v2.json` (07/10) chỉ chứa chương đã từng mở/render trước; chương chưa từng mở lần đầu trên HDD nguội có thể vượt ngân sách 0.25s → ảnh còn lại mang tỉ lệ ước lượng tới khi tải về (như trước). Đổi logic SW → `SW_VERSION` tự đổi → lần mở đầu sau deploy `PAGE_CACHE` bị dọn (trắng 1 lần là bình thường).
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
  phải **Switch user**. Supervisor chạy ẨN (pythonw); kill tay sẽ bị watchdog bật lại ≤2' (tắt sạch:
  `server-TAT-tudong.bat`). Watchdog (/it) chỉ chạy khi ĐĂNG NHẬP; autologon lo phần tự đăng nhập sau reboot.
- **Task tạo bằng `schtasks /create` có sẵn giới hạn "Stop if runs >72h"** — ĐỪNG cho task chạy THẲNG tiến
  trình sống lâu (bị giết sau 72h). Muốn tiến trình dài hạn: task chỉ `Start-Process` rồi thoát (như watchdog).
- **.bat: KHÔNG để `(`/`)` trần trong `echo` (hay `rem`) nằm trong khối `if (...)`/`for`** — `)` đóng khối → lỗi cú
  pháp, CẢ FILE dừng ngang (cửa sổ chớp rồi tắt). Bỏ ngoặc hoặc `^(`/`^)`. Sửa .bat xong nên chạy thử bản copy.
- **Task /it chạy console app (powershell/cmd/python.exe) = chớp cửa sổ mỗi lần chạy** — task định kỳ phải dùng
  `pythonw.exe` (hoặc app GUI-subsystem), con console gọi với `CREATE_NO_WINDOW`.
- **Tham số `.bat` → `schtasks /tr` → PowerShell `-File`: ĐỪNG truyền đường dẫn có `\` cuối trong nháy**
  (`"%~dp0"`) — `\"` thành dấu nháy thường. Bỏ `\` cuối, hoặc để script tự lấy `$PSScriptRoot`.
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
