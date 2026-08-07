# Handoff — cập nhật lần cuối: 2026-08-07

## Đang làm / dở dang
- Không có việc code dở. Vừa xong đợt: **(1) 4 lệnh huỷ tải qua bot; (2) web admin đổi tên
  hiển thị + đổi ảnh bìa**. Verify xong (reader chạy live port 8099: title override + cover
  upload OK; unit test drain queue + routing OK). **CHƯA push GitHub, CHƯA deploy.** Vì đã sửa
  `supervisor.py` → deploy phải bằng `cap-nhat.bat`/`server-BAT` (không dùng `/update` được).
- Đợt trước đó: hệ tài khoản + đồng bộ git + Telegram bot + web admin (đã push GitHub).

## Kiến trúc hiện tại (đã đổi nhiều so với bản 05/08)
- **Lưu dữ liệu đọc — HAI đường, tách riêng, KHÔNG di trú:**
  - **Đã đăng nhập** → server per-account trong `.reader-meta/users.json`
    (`byname` chuẩn-hoá→id, `users[id]` = display/bookmarks/progress/read). Login = nhập
    username (không mật khẩu, chỉ để tách người). Cookie `uid` (1 năm).
  - **Guest (chưa đăng nhập)** → localStorage per-device (`LS_JS`: `toony_bm`,
    `toony_prog`, `toony_read`). Bookmark/tiến trình/đọc-mờ đều chạy client-side.
- **Web admin**: đăng nhập username `admin` (trong `ADMIN_USERS`, KHÔNG mật khẩu — user đã
  từ chối PIN, chấp nhận rủi ro cho 2 anh em). Trang chủ hiện: toggle Complete/Ongoing,
  sắp thứ tự (⤒ lên đầu / ▲ / ▼ — đánh lại `order` 1..N), **Dọn list** (prune mục chết
  trong `series-meta.json`, backup `.bak`), **Refresh** (xoá cache). Endpoint POST
  `/api/admin` gate bằng `is_admin`.
- **Thư viện**: `get_library` **tự ẩn bản gốc `<tên>` khi có `<tên>_webp`**. Home có ô
  **Search comics** (lọc theo tên, client-side). Ô nhập tên + 2 ô search đều `font-size:16px`
  để iOS không tự zoom.
- **supervisor.py** (server): giữ reader + cloudflared sống, health-check, bắt link, gửi
  Telegram. **Vòng nghe getUpdates** xử lý lệnh bot (xem dưới). Có **hàng đợi tải** (`/tai`)
  chạy ở 1 luồng worker riêng.

## Đồng bộ code bằng git (thay copy tay/zip)
- Repo **Public**: https://github.com/Baion91/comics (nhánh `main`). `.gitignore` loại
  `downloads/`, secret/data trong `.reader-meta` (giữ icon/brand/og). Token thật CHỈ ở
  `.reader-meta/notify-config.json` (gitignore); `notify-config.example.json` để token rỗng.
- **Máy dev push**: `day-len.bat` (add+commit+push). **Server cập nhật**: `cap-nhat.bat`
  (git fetch + reset --hard origin/main → gọi `server-BAT`), HOẶC `/update` qua bot.
- **Server setup git lần đầu** (giữ nguyên truyện/token): trong folder tool chạy
  `git init -b main` → `git remote add origin <url>` → `git fetch` → `git reset --hard
  origin/main` (KHÔNG clone folder mới). Public nên khỏi đăng nhập.

## Lệnh Telegram bot (đều là lệnh 1 TỪ — Telegram không nhận lệnh có dấu cách)
- `/link` link hiện tại · `/whoami` chat_id · `/help` list lệnh · `/start` đăng ký nhận link.
- **Admin**: `/update` (git pull + restart reader, KHÔNG đổi link cloudflared) ·
  `/tai <link…>` (xếp hàng đợi, worker tải 1 lượt/lúc, báo bắt đầu/xong) ·
  `/adminclaim` (người đầu tiên → admin gốc) · `/adminlist` · `/adminadd <id>` ·
  `/adminremove <id>`. Đăng ký menu qua `setMyCommands` lúc khởi động.
- **Quyền**: `admin_chat_ids` trong notify-config. Rỗng → tạm ai cũng được (tới khi có
  người `/adminclaim`), sau đó strict theo danh sách. `_is_admin` gác `/update`,`/tai`,`/admin*`.

## Quyết định gần đây (mới nhất trước)
- 07/08: **4 lệnh huỷ tải bot** (`/stop` dừng+xoá-hàng-chờ của mình, `/killnow` chỉ kill,
  `/clearq` chỉ xoá hàng chờ, `/stopall` dừng+xoá tất cả của mọi người). Worker chuyển
  `subprocess.run`→**Popen** để kill được (`self._dl_proc`/`_dl_cur`/`_dl_cancelled`); huỷ báo
  "⏹ Đã huỷ" (không nhầm lỗi). Scope "của mình" = so `cid` gửi lệnh với `cid` lưu kèm mỗi URL.
  `/stopall` PHẢI check trước `/stop` (startswith). Xoá hàng chờ = drain rồi re-put phần giữ lại
  (khoá `_dlq_lock`). Tải lại sau huỷ tự bỏ qua chương `.done` (resume có sẵn).
- 07/08: **Web admin đổi TÊN = override hiển thị, KHÔNG đổi folder** (hướng A, user chốt): lưu
  trường `title` trong `series-meta.json`; `get_library` đè `s["title"]` trước sort. sid/folder
  giữ nguyên → không mất bookmark/tiến-trình, không đụng downloader (nó đặt tên folder theo slug).
  Tên rỗng = xoá override. `set_series_title()` + op `title` trong `/api/admin`.
- 07/08: **UI nút admin (theo mẫu user)**: icon Lucide **ImagePlus** nổi góc trên-phải ảnh bìa
  (`.covedit`, absolute, ngoài `.cardlink`) + **SquarePen** cuối tên truyện (`.titleedit`, trong
  `.ct` flex, TRONG thẻ `<a>` nên handler phải `preventDefault` chặn điều hướng). Bỏ 2 nút emoji
  cũ khỏi `.admrow`. SVG hằng `IMAGEPLUS_SVG`/`SQUAREPEN_SVG`.
- 07/08: **Web admin đổi BÌA**: chọn file → JS đọc base64 (data URL) → POST op `cover`.
  `/api/admin` nâng giới hạn body 200KB→12MB. `save_cover()` nén về JPEG 3:4 @480px (dùng lại
  logic `cover_jpeg`), ghi `cover.jpg`, XOÁ cover.* đuôi khác (giữ đúng 1 bìa), xoá `_cover_cache`.
  `cover_url?v=mtime` sẵn nên PWA tự tải bìa mới. Ảnh ngang giữ nguyên tỉ lệ (khung 3:4 cắt lúc
  hiển thị) — khuyến nghị chuẩn bị bìa **đúng 3:4 (900×1200)** để không bị cắt (đã ghi README).
- 07/08: **RavenProvider viết lại** cho site đại tu `.org`→`.net` (URL chương giờ là
  `/series/{slug}/chapter-{ID_nội_bộ}`, SỐ chương lấy từ TEXT "Chapter N", không ở URL);
  ảnh (`ts_reader`) + cover (`og:image`) giữ nguyên. Test live 193 chương OK. `domains` giữ
  cả `.org` cho link cũ, `BASE`=`.net`.
- 07/08: **Vòng nghe Telegram bọc try/except mỗi update** (1 lệnh lỗi KHÔNG làm chết cả bot)
  + log lệnh nhận được — trước đó 1 handler ném lỗi là bot im hẳn tới khi restart.
- 07/08: **Lệnh admin đổi thành 1 từ** (`/adminclaim/list/add/remove`) — Telegram bấm lệnh
  có dấu cách chỉ gửi phần trước dấu cách.
- 07/08: **`/update` chỉ restart reader, KHÔNG đụng cloudflared** → link giữ nguyên (đúng ý:
  cập nhật khỏi mất link). `/update` chạy luồng nền + timeout git + `GIT_TERMINAL_PROMPT=0`
  (trước bị treo khi mạng server nghẽn).
- 07/08: **server-BAT tự kill supervisor/reader cũ trước khi bật** (lọc đúng
  supervisor.py/reader_server.py) → hết lỗi 2 tiến trình song song (Telegram 409).
- 06/08: **Đồng bộ code bằng git/GitHub (repo Public)** thay copy tay/zip.
- 06/08: **Login username-only + dữ liệu per-account server-side**; **guest dùng localStorage**;
  hai bên tách riêng, không di trú → ĐẢO quyết định 05/08 "hồ sơ chung server-side".
- 06/08: **Web admin** (username `admin`, không PIN) cho status/thứ tự/prune/refresh.
- 06/08: **Ẩn bản gốc khi có `_webp`**; **Search comics** ở home.

## Việc tiếp theo
- **Push GitHub (`day-len.bat`) rồi deploy `cap-nhat.bat`** trên server — đợt này sửa
  `supervisor.py` nên KHÔNG dùng `/update` được. Nghiệm thu LIVE: 4 lệnh huỷ (`/stop`,
  `/killnow`, `/clearq`, `/stopall`), nút web admin ✏️ đổi tên + 🖼️ đổi bìa.
- Đợt cũ chờ nghiệm thu LIVE: `/help`, `/adminclaim`, `/tai`, search home, guest bookmark iPhone.
- Server mạng ra internet chập chờn (getUpdates/tunnel hay timeout) — nếu kéo dài, cân nhắc
  **Tailscale/LAN** thay quick-tunnel cho ổn định.
- (Tùy chọn) đồng hồ server nhanh ~5 phút — sync giờ Windows nếu muốn log khớp.

## Lưu ý / rủi ro đang mở
- **Admin không mật khẩu** + tunnel public → người lạ có link về lý thuyết gõ tên `admin`
  là vào admin. Chấp nhận cho phạm vi 2 anh em (bot/link obscure). Muốn siết → thêm PIN.
- **Sửa `supervisor.py`** phải deploy bằng `cap-nhat.bat`/`server-BAT` (`/update` chỉ nạp
  lại reader, không nạp lại chính supervisor — bot có cảnh báo dòng này).
- **Đừng bấm `server-BAT` khi đã có supervisor chạy** trừ khi muốn restart (bản mới tự kill
  cũ nên an toàn, nhưng nhớ chỉ để 1 supervisor poll 1 token, kẻo 409).
- Sửa **CODE** `reader_server.py` phải restart reader; sửa tay **`series-meta.json`** thì F5
  (mtime tự nạp). Prune/reorder/status trong web admin ăn ngay (không cần restart).
- `.reader-meta/notify-config.json` chứa **token thật** — không commit (đã gitignore).
- **Tải song song**: `/tai` qua bot dùng **1 hàng đợi + 1 worker → tuần tự** (giữ đúng van
  điều tốc, "1 ảnh 1 lần"). NHƯNG `Tai hang loat.bat`/`Tai truyen.bat` bấm tay là tiến trình
  NGOÀI hàng đợi bot → chạy song song với worker bot = gấp đôi request, tăng rủi ro chặn IP.
  Đừng chạy tay lúc bot đang tải (và ngược lại).
- Download qua bot chạy **ẩn (CREATE_NO_WINDOW)** — không có cửa sổ là bình thường; theo dõi
  bằng tin Telegram "Tải xong"/"Lỗi" hoặc folder `downloads\`.
- Script ad-hoc in tiếng Việt cần `PYTHONIOENCODING=utf-8` (console cp1252).
