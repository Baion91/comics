# Handoff — cập nhật lần cuối: 2026-08-11 (supervisor chống-chịu mạng + heartbeat, sau sự cố DNS)

> Kiến trúc ổn định (reader, provider, comix, supervisor, mạng…) nằm ở `.claude/ARCHITECTURE.md`.
> File này chỉ ghi TRẠNG THÁI hiện tại + việc đang dở.

## Đang làm / dở dang
- **[11/08] Supervisor chống-chịu mạng (B+C+D) + heartbeat — ĐÃ code + push + deploy; user
  xác nhận link về lại sau khi vá regression.** Nguyên nhân sự cố đêm 10→11: DNS server chập
  ~5 tiếng → cloudflared crash-loop → 2900 link rác + mất 8 truyện hàng đợi (chi tiết ở "Quyết
  định" + memory `comix-dns-crashloop-incident`). Đã sửa trong `supervisor.py`. **Regression đã
  vá**: bản đầu "xác minh rồi mới báo link" là one-shot → restart không thấy bắn link; nay
  `_confirm_and_notify` thử lại trong cửa sổ 120s. **CHƯA nghiệm thu qua một đêm mạng chập thật.**
  - Việc user cần làm: **bật heartbeat** (tạo 1 check healthchecks.io Simple 5'/20', dán Ping URL
    vào `notify-config.json` `heartbeat_url`, `cap-nhat.bat`). Webhook Telegram báo về Toony bot
    (POST `api.telegram.org/bot<TOKEN>/sendMessage`) — user đã **test OK**.
- **[10/08] Tool LÀM NÉT Real-ESRGAN (`realesrgan-.../lam_net.py`+`lam-net.bat`) — ĐÃ push
  (đã xác minh: tracked + local==origin). Tích hợp tự động vào `/tai` CHƯA làm.** Chi tiết tham
  số/skip ở "Lưu ý".
- **[10/08] Comix: tự dựng lại Chromium khi cửa sổ đóng + upgrade cross-site + file dấu — ĐÃ
  push, CHƯA nghiệm thu LIVE.** Nghiệm thu: `/tai` 1 bộ comix rồi đóng tay Chromium giữa chừng →
  phải nhận Telegram "🔄 tự mở lại" + tải tiếp; đóng lặp >3 lần → "❌ Lỗi tải" (không báo "xong" giả).

## Quyết định gần đây (mới nhất trước)
- **11/08: Reader CHỈ quét `downloads/`** (`SCAN_ROOTS` bỏ `BASE_DIR`) — trước quét cả
  gốc project nên `realesrgan-ncnn-vulkan-*` (có `input/`+`output-realesrgan/` chứa ảnh) hiện
  thành 1 bộ "truyện" giả; `cover`/`cover_webp` cũng chực vỡ. Đã xác nhận không có truyện thật
  nào ở gốc (series-meta 8 key = 8 folder downloads). Deploy `/update` + **restart** reader.
- **11/08: ACGNProvider (comic.acgn.cc, truyện tiếng Trung) — ĐÃ code, CHƯA nghiệm thu tải
  LIVE trên server.** HTML tĩnh, không JS/API (giống Dilib/TruyenQQ): ảnh nhúng `_src` trong
  `view-{id}.htm`, danh sách tập ở `manhua-{slug}.htm`, số chương từ text `VOL`/`第N話`. Dán URL
  1 tập thì `series_slug` tự tải trang đó lấy breadcrumb `manhua-` để về slug. **Tên folder GIỮ
  tiếng Trung** (user chọn, thay vì pinyin — tránh thêm dep `pypinyin`; nhờ vậy **deploy chỉ cần
  `/update`**, không cần `cap-nhat.bat`). `referer=None` (đã kiểm CDN không đòi). Đã test parse
  từ máy dev OK (zzzs 22 tập, codebreaker 228 chương/1 trang → không phân trang, VOL17=78 ảnh).
  **Chưa tải ảnh thật được từ máy dev**: CDN `img.acgn.cc` lọc vùng → 522 ngoài VN; server VN đã
  test `Invoke-WebRequest` trả 200 (~64KB, không cần Referer). Nghiệm thu = `/tai` link acgn trên
  server rồi soi `check_library.py`.
- **11/08: Supervisor chống-chịu mạng + heartbeat** — sau sự cố DNS. Gate mạng `_net_status()`
  ở run_tunnel/download_loop/health_loop; backoff cloudflared 3→300s; **báo link chỉ khi đã xác
  minh** (retry trong cửa sổ, tránh spam + tránh bỏ sót lúc restart); **giữ hàng đợi khi lỗi-mạng**
  (không xoá); regex loại link rác `api.trycloudflare.com`; heartbeat ping healthchecks.io. Vì sao
  KHÔNG làm named-tunnel (URL cố định, giải pháp gốc): user chưa có domain. Vì sao cần heartbeat:
  bot không tự báo được khi mạng server chết (cùng đường mạng đã hỏng).
- 10/08: **Tool làm nét Real-ESRGAN** — model `realesr-animevideov3` 2x + PNG (user soi crop 3x
  thắng waifu2x/x4plus); đo tiến độ = ĐẾM file output (exe đa luồng làm `%` sai); skip theo "đủ
  output", nút y/N để ép làm lại.
- 10/08: **Comix tự dựng lại Chromium** — `alive()` phân biệt browser-chết (fatal) vs điều-hướng-hụt;
  relaunch tại chỗ; `MAX_RELAUNCH=3`/`FAIL_STREAK_LIMIT=6` → thoát ≠0 báo lỗi thật thay vì "xong" giả.
- 09/08: **Comix bền với chương lỗi + chặn quảng cáo** — `ctx.route` chỉ cho comix/cloudflare;
  1 chương hụt KHÔNG giết cả bộ (exit 0, ghi `unfetched` đi tiếp).
- 09/08: **Comix upgrade CROSS-SITE + file dấu** — nhận cả bản site khác (ảnh+`.done`, không
  sidecar) → thay Official theo số chương; ghi `_COMIX_official_*.txt` để user tự xoá folder scan trùng.
- 09/08: **Comix = loop riêng `comix_site.py`** (Playwright headful + hook JSON.parse) — API mã
  hoá + token per-request; chọn official trước, scan id lớn nhất; skip official vĩnh viễn.
- 09/08: **TruyenQQProvider** (truyenqqko.com, HTML tĩnh, ĐÒI Referer chống hotlink).
- 09/08: **MangaDexProvider** (API, bản en, newest-wins, loại external/0-trang trước dedup, ĐÒI Referer).
- 09/08: **Chống crash tầng C downloader** (`faulthandler`+breadcrumb+chặn bom) + `.bat` báo trung
  thực (đọc errorlevel, tự chạy lại) + bỏ emoji khỏi console (giữ ở Telegram/log).
- 07/08: **Hàng đợi tải BỀN HOÁ + resume qua restart** (`bot-download-queue.json`) + **4 lệnh huỷ
  tải** (`/stop /killnow /clearq /stopall`). (Các quyết định cũ hơn: web admin, RavenProvider,
  login username-only, chuyển git/GitHub — đã gói trong ARCHITECTURE.md.)

## Việc tiếp theo
- **[ACGN nghiệm thu]** `day-len.bat` (dev) → `/update` trên bot (đủ, vì chỉ sửa `providers.py`,
  không thêm dep). Rồi `/tai https://comic.acgn.cc/view-11338.htm` (hoặc `manhua-zzzs.htm`) → xác
  nhận ra bộ `摺紙戰士` 22 tập, ảnh tải + decode OK; `check_library.py` soi. Nếu server báo 522 khi
  tải ảnh → origin đổi vùng lọc (hiếm), đợi/đổi đường ra.
- **[Heartbeat]** Bật trên server: tạo check healthchecks.io → dán `heartbeat_url` → `cap-nhat.bat`.
  Kiểm "Last Ping" chuyển xanh trong 5'. Thêm webhook cho chat_id em trai (integration Webhook thứ 2).
- **[Supervisor resilience]** Nghiệm thu tự nhiên: lần tới mạng server chập, xác nhận KHÔNG còn spam
  link + hàng đợi KHÔNG mất. Nếu restart mà vẫn không bắn link → xem log `Link ứng viên` vs
  `Mạng chưa sẵn sàng` để phân biệt lỗi xác minh vs gate mạng chặn nhầm.
- **[Tool làm nét → TƯƠNG LAI]** Tích hợp `/tai`: enhance hậu-xử-lý → resize → nén JPG/WebP ~80–85,
  xếp hàng 1 job/lúc (1050 Ti), whitelist truyện scan kém, báo Telegram khi hỏng.
- **[Comix LIVE]** `/update` rồi `/tai`: (a) đóng tay Chromium giữa chừng phải "🔄 tự mở lại";
  (b) the-lone-spellcaster (0qd3d) chương hụt cuối báo "Chưa lấy được: N" + chạy lại là bù;
  (c) Dungeon Reset (81djd) 266 ch Raven tự lên Official (mẻ lớn). Cloudflare challenge thì tick
  trên màn hình server.
- **[Nội dung]** `/tai` thử TruyenQQ 1 bộ; `/tai` lại Tondemo Skill bù chương 1; (tùy chọn) tải lại
  Pokemon Ouja no Saiten bằng engine cho đồng nhất naming rồi xoá bản cũ.
- (Tùy chọn, gốc rễ) **Named tunnel + domain** để URL cố định (hết đổi-link + lỗi 1033) — nếu mua domain rẻ.

## Lưu ý / rủi ro đang mở
- **Server mất mạng/DNS/điện thì reader vẫn KHÔNG vào được trong lúc đó** — B+C+D chỉ chặn hệ quả
  (spam link, mất hàng đợi), không cứu được downtime. Biết server sập = nhờ **heartbeat ngoài**.
- **`heartbeat_url` là BÍ MẬT** (như token) — không commit; nằm trong `.reader-meta/notify-config.json`
  (đã gitignore). Ai có URL chỉ có thể che cảnh báo, không đụng máy.
- **Sửa `supervisor.py` phải deploy bằng `cap-nhat.bat`/`server-BAT`** (nó kill+bật lại trọn
  supervisor). `/update` qua bot CHỈ restart reader → KHÔNG nạp lại supervisor.
- **Admin không mật khẩu** + tunnel public → người có link gõ tên `admin` là vào admin. Chấp nhận
  cho 2 anh em (link obscure). Muốn siết → thêm PIN.
- **1 hàng đợi CHUNG, 1 worker tuần tự FIFO** cho mọi admin (van chống-chặn-IP nằm trong mỗi tiến
  trình downloader, không phối hợp liên tiến-trình → 2 truyện song song = gấp đôi request). **Đừng
  bấm `Tai hang loat.bat`/`Tai truyen.bat` tay lúc bot đang tải** (song song = dễ chặn IP); lúc
  supervisor khởi động nó tự giết mọi `comic_downloader.py` lạc trước khi resume.
- **Comix** dễ vỡ nhất khi site đổi build/DOM (`navigator.webdriver`, phân trang `?page=N`).
  `downloads/.comix-tmp/` là chỗ tráo Official — đừng xoá tay lúc tải. Xoá sidecar `.source.json`
  = tool coi như chưa rõ nguồn (có thể tải/upgrade lại).
- **MangaDex** chỉ lấy bản `en`; chương chỉ-external (ảnh không ở MangaDex) sẽ hụt — giới hạn nguồn.
- **Nếu tải lại sập tầng C**: đọc `.reader-meta/crash-trace.txt` + dòng "PHIÊN TRƯỚC CHẾT" trong
  `download-log.txt` (tên ảnh thủ phạm).
- **Tool làm nét**: ảnh ra PNG 2x nặng nhiều lần gốc — phải nén trước khi vào reader. Cần GPU Vulkan.
  Chương lỗi lần trước (còn output cũ) bị skip — chọn `y`/`--force` để làm lại. Chỉ đệ quy 1 cấp folder.
- **Theo dõi tải qua bot**: chạy ẩn (CREATE_NO_WINDOW) — xem tin Telegram / folder `downloads\` /
  tail `.reader-meta\tai-run.log`. Script ad-hoc in tiếng Việt cần `PYTHONIOENCODING=utf-8`.
