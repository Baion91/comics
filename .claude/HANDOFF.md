# Handoff — cập nhật lần cuối: 2026-08-09 (chiều)

## Đang làm / dở dang
- **[09/08] Provider TruyenQQ + fix UI reader — ĐÃ push + user xác nhận đã update server.**
  `TruyenQQProvider` (truyenqqko.com, HTML tĩnh, ảnh từ `data-original`, list chương từ URL
  `-chap-N`, ĐÒI Referer `truyenqqko.com` chống hotlink, tên folder có dấu từ `<h1 itemprop=name>`,
  hỗ trợ chương lẻ `chap-43-5`→43.5). Test URL thật: 104 chương/40 ảnh/cover OK. Kèm fix web reader:
  `.grid{align-content:start}` chống stretch card khi search 1–2 truyện (bỏ khoảng trống dưới nút
  Bookmark). README cũng đã cập nhật (mục hỗ trợ + ghi chú TruyenQQ đổi domain).
- **[09/08] Provider MangaDex — ĐÃ push + user xác nhận đã update server.** `MangaDexProvider`
  (API `api.mangadex.org`, bản `en`, newest-wins dedup theo `(volume,chapter)`, loại bản
  external/0-trang trước dedup, oneshot→0.0, ĐÒI Referer). Kèm 2 fix engine dùng chung:
  `safe_name` cắt dấu chấm/space cuối (fix `FileNotFoundError` Windows khi title kết thúc `...`)
  + `_retry_after` đọc `x-ratelimit-retry-after`. Đã bỏ `pokespe_update.py`. Test server:
  resolve/tải MangaDex OK, **không cần DoH**. Còn tùy chọn: **Pokemon Ouja no Saiten** trong
  `downloads/` vẫn là bản tải bằng tool ngoài (naming `Ch. N`) — muốn đồng nhất chuẩn engine
  (`Chapter N - Title`) thì `/tai` lại rồi xoá bản cũ (choice B, CHƯA làm). **Tondemo Skill**:
  sau fix external-skip cần `/tai` lại trên server để bù **chương 1** (nếu chưa).
- **[09/08] Chống-chết cho downloader — ĐÃ PUSH GitHub, CHƯA xác minh server `/update`.** Gồm:
  (1) `Tai hang loat.bat` báo trung thực + tự tải tiếp khi đứt/crash; (2) `comics_core.py` bắt
  crash tầng C (`faulthandler`+breadcrumb) + chặn ảnh 'bom' trước decode; (3) dòng tổng kết cả bộ
  luôn hiển thị; (4) bỏ emoji khỏi output console (nhãn chữ). Đã test local. Xác minh (09/08):
  `origin/main:comics_core.py` chứa `faulthandler`, HEAD==origin/main (0 ahead/behind) → **đã lên
  GitHub**. `comics_core.py` không nằm trong `supervisor.py` nên chỉ cần **`/update`** trên bot là
  server ăn (không phải restart tay). → xem "Việc tiếp theo".
- Không có việc code dở. **Đã push + deploy** đợt: **(1) 4 lệnh huỷ tải qua bot; (2) web admin
  đổi tên hiển thị + đổi ảnh bìa (UI icon ImagePlus/SquarePen); (3) hàng đợi tải BỀN HOÁ ra đĩa
  + tự tải tiếp sau khi restart supervisor + ghi log downloader ra file.** Verify local xong
  (unit + integration test cho queue/resume/cancel/log-file; reader live 8099 cho title/cover).
  Chờ nghiệm thu LIVE trên server.
- **Cần tải lại thủ công 1 lần**: hôm nay 2 truyện bị mất do các lần deploy giết supervisor bản
  CŨ (chưa có persist): **spirit-farmer** (Raven) + **One Punch Man** (link dilib — em tải, xếp
  sau spirit-farmer nên chưa chạy → chưa tạo folder → mất khi restart). `/tai` lại cả hai.
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
- 09/08: **Thêm TruyenQQProvider** (truyenqqko.com). Site PHP tĩnh (giống Dilib): ảnh nhúng sẵn
  ở `data-original`, list chương từ URL `-chap-N`. CDN `truyenvua/hinhtruyen` **chống hotlink →
  ĐÒI Referer `truyenqqko.com`** (thiếu = 403; core tự gắn qua `provider.referer`). Tên folder lấy
  CÓ DẤU từ `<h1 itemprop=name>` (slug là ASCII không dấu). URL chương dùng gạch (`chap-43-5`) còn
  path ảnh dùng chấm (`/43.5/`) — lấy nguyên từ `data-original` nên không lệ thuộc. Khai báo sẵn
  vài domain cũ vì site đổi tên miền liên tục.
- 09/08: **Fix UI web reader** — `.grid{align-content:start}`: `min-height:70vh` (chống iOS
  scroll-jump) cộng grid `align-content/align-items` mặc định = `stretch` kéo giãn card khi ít
  kết quả → khoảng trống lớn dưới nút Bookmark lúc search 1–2 truyện. `align-content:start` dồn
  hàng lên đầu, phần dư thành nền trống.
- 09/08: **Thêm MangaDexProvider** (API `api.mangadex.org`, bản `en`). Dedup key `(volume,chapter)`
  giữ bản newest (`order[readableAt]=desc`, khớp `mangadex-downloader`); **loại bản
  `externalUrl`/`pages==0` TRƯỚC dedup** (kẻo bản external mới hơn giành slot rồi bị bỏ vì rỗng →
  mất bản thật cũ hơn; sự cố Tondemo Skill ch1); `contentRating[]` đủ 4 mức (kẻo manga 18+ rỗng);
  oneshot (`chapter=null`)→`0.0`; @Home **ĐÒI `Referer: mangadex.org`** (ảnh nguội thiếu → 404).
  Bản licensed có chương chỉ-external (ảnh không ở MangaDex) sẽ hụt — giới hạn nguồn, không sửa được.
- 09/08: **`safe_name` cắt dấu chấm/space cuối + loại ký tự điều khiển** (`comics_core.py`): title
  MangaDex hay kết thúc `...`; Windows lược chấm cuối khi `mkdir` → tên Path lệch tên đĩa → ghi ảnh
  `FileNotFoundError` + crash (không bắt vì chỉ bắt `requests.RequestException`). Bug engine chung.
- 09/08: **Bỏ `pokespe_update.py`** (tool tải Pokemon Special hardcode path tuyệt đối, lỗi trên
  server) — thay bằng luồng provider chuẩn.
- 09/08: **Chống crash tầng C cho downloader** (`comics_core.py`): (1) `faulthandler`→
  `.reader-meta/crash-trace.txt` (crash tầng C Pillow/libwebp — `except` Python không bắt được);
  (2) breadcrumb `decoding-now.txt` + `reap_decode_crash()` đầu `run()` → ghi ảnh thủ phạm khi
  phiên trước chết (không tự đánh dấu hỏng, tránh bỏ nhầm ảnh tốt); (3) chặn bom TRƯỚC decode
  `SAFE_MAX_BYTES` 64MB / `SAFE_MAX_PIXELS` 60MP. Vì sao: tải qua server bỗng dừng giữa chương mà
  `.bat` vẫn in "Xong" — do crash tầng C, không traceback.
- 09/08: **`Tai hang loat.bat` báo trung thực + tự tải tiếp**: đọc `errorlevel` — rc=0 "Xong THẬT
  SỰ"; rc=2 (chặn IP) nhắc chờ; rc khác → "CHƯA xong" rồi tự chạy lại tối đa 5 lần (chương `.done`
  tự bỏ qua). Trước `.bat` in "Xong" vô điều kiện sau dòng `python` nên đánh lừa "đã xong".
- 09/08: **Dòng tổng kết cả bộ LUÔN hiển thị** (`run()` đếm `n_full`/`n_skipped`/`n_locked`):
  in *Đủ ảnh / Đã xong trước / Thiếu trang / Hỏng tại nguồn / Khóa* kể cả khi mọi thứ ổn (trước
  chỉ "Hoàn tất" trơ trọi, không rõ bao nhiêu chương lỗi).
- 09/08: **Bỏ emoji khỏi output CONSOLE** (phương án A user chốt): `✅⏭⚠⛔🔒`→nhãn chữ, `⚠`→`!`,
  `⛔`→`!!`, `→`→`->` (cả `comic_downloader.py`). Vì cmd cổ điển thiếu glyph emoji + `🔒` astral
  lệch con trỏ khi in đè `\r`. Emoji ở Telegram + `append_log` (file) GIỮ nguyên.
- 09/08: **Chốt quy trình deploy** (KHÔNG "push qua telebot"): viết code ở máy dev → push (Claude
  hoặc `day-len.bat`) → `/update` trên bot kéo về server. Lý do: code mới nằm ở **máy dev**, server
  không push hộ được; `/update` chạy trên server và chỉ **PULL** (`reset --hard origin/main`).
  "Push qua telebot" chỉ khả thi nếu máy dev bật + chạy listener riêng (đã bàn, tạm không làm).
- 07/08: **Hàng đợi tải BỀN HOÁ + tự resume qua restart** (`supervisor.py`). Vì sao: mỗi
  `cap-nhat.bat` → `call server-BAT` → dòng 30 `Stop-Process` giết supervisor cũ → downloader
  (con) vỡ pipe stdout chết + hàng đợi RAM mất sạch (đó là lý do spirit-farmer đứt 11:54).
  Sửa: bỏ `queue.Queue` → **danh sách `_jobs` bền hoá ra `.reader-meta\bot-download-queue.json`**
  (ghi nguyên tử, Condition thay Lock để đánh thức worker). Job xong/lỗi/huỷ-lệnh → xoá khỏi
  file; job bị **restart giết đột ngột** → code xoá không kịp chạy → **ở lại file → khởi động
  sau tự tải tiếp** (resume bỏ qua `.done`). Lúc boot `resume_jobs()`: **giết downloader lạc**
  (`_kill_stray_downloaders`, vì server-BAT KHÔNG dọn comic_downloader.py → chống tải trùng)
  rồi nạp lại hàng đợi. Job từng 'running' báo **"🔄 Đang tiếp tục"**, khác 'pending' báo "⏳".
  **Output downloader ghi ra FILE** `.reader-meta\tai-run.log` (Popen `-u`, `stdout=file` thay
  PIPE) → supervisor chết không vỡ pipe + tail xem real-time + đọc đuôi lỗi từ file. File queue
  nằm trong `.reader-meta/*` (gitignore) nên `git reset --hard` không đụng.
- 07/08: **4 lệnh huỷ tải bot** (`/stop` dừng+xoá-hàng-chờ của mình, `/killnow` chỉ kill,
  `/clearq` chỉ xoá hàng chờ, `/stopall` dừng+xoá tất cả của mọi người). Worker chuyển
  `subprocess.run`→**Popen** để kill được (`self._dl_proc`/`_dl_cur`/`_dl_cancelled`); huỷ báo
  "⏹ Đã huỷ" (không nhầm lỗi). Scope "của mình" = so `cid` gửi lệnh với `cid` lưu kèm mỗi URL.
  `/stopall` PHẢI check trước `/stop` (startswith). Xoá hàng chờ = drain rồi re-put phần giữ lại
  (khoá `_dlq_lock`). Tải lại sau huỷ tự bỏ qua chương `.done` (resume có sẵn).
- (Các quyết định 07/08 cũ hơn — web admin đổi tên/bìa, viết lại RavenProvider `.net`, bot
  try/except + lệnh admin 1-từ, `/update` giữ link, server-BAT tự kill cũ — và 06/08 chuyển
  sang git/GitHub + login username-only đã gói trong "Kiến trúc hiện tại" + "Đồng bộ code bằng git".)

## Việc tiếp theo
- **[09/08] Toàn bộ code (TruyenQQ, fix reader, MangaDex, chống-chết downloader) đã lên server
  — user xác nhận.** Việc nội dung còn mở: `/tai` **TruyenQQ** thử 1 bộ trên server cho chắc;
  `/tai` lại **Tondemo Skill** bù chương 1 (sau fix external-skip); tùy chọn tải lại **Pokemon
  Ouja no Saiten** bằng engine cho đồng nhất naming `Chapter N - Title` rồi xoá bản `Ch. N` cũ.
- **Nghiệm thu LIVE** (đã deploy): 4 lệnh huỷ (`/stop`, `/killnow`, `/clearq`, `/stopall`),
  nút web admin đổi tên/đổi bìa, và **thử hàng đợi sống qua restart**: `/tai` 1 truyện → chạy
  `cap-nhat.bat` giữa chừng → sau khi lên lại bot phải báo "🔄 Đang tiếp tục". Tail
  `.reader-meta\tai-run.log` xem tiến độ.
- **Tải lại `spirit-farmer` (Raven) + One Punch Man (link dilib)** — mất trong các lần deploy
  hôm nay, trước khi có persist.
- Đợt cũ chờ nghiệm thu LIVE: `/help`, `/adminclaim`, `/tai`, search home, guest bookmark iPhone.
- Server mạng ra internet chập chờn (getUpdates/tunnel hay timeout) — nếu kéo dài, cân nhắc
  **Tailscale/LAN** thay quick-tunnel cho ổn định.
- (Tùy chọn) đồng hồ server nhanh ~5 phút — sync giờ Windows nếu muốn log khớp.

## Lưu ý / rủi ro đang mở
- **MangaDex**: chỉ lấy bản `en`; manga đã license tiếng Anh có thể có chương **chỉ-external**
  (ảnh không nằm trên MangaDex) → hụt đúng chương đó, KHÔNG phải lỗi (tool nào cũng vậy, kể cả
  `mangadex-downloader`). Provider ĐÒI `Referer: mangadex.org` (đã set sẵn trong class). Naming
  engine (`Chapter N - Title`) KHÁC tool ngoài (`Ch. N`) → 2 bản không nối liền, coi chừng trùng
  folder khi migrate. Không cần DoH (server đã test truy cập được).
- **Nếu tải (bot hoặc tay) lại sập tầng C**: đọc `.reader-meta/crash-trace.txt` (C-stack, biết
  crash ở đâu) + dòng "PHIÊN TRƯỚC CHẾT" trong `download-log.txt` (tên ảnh thủ phạm) để vá đúng
  nguồn. Crash loại này hiếm; gói 09/08 chỉ đảm bảo `.bat` không còn "nói dối" + tự bù chỗ dở.
- **Admin không mật khẩu** + tunnel public → người lạ có link về lý thuyết gõ tên `admin`
  là vào admin. Chấp nhận cho phạm vi 2 anh em (bot/link obscure). Muốn siết → thêm PIN.
- **Sửa `supervisor.py`** phải deploy bằng `cap-nhat.bat`/`server-BAT` (`/update` chỉ nạp
  lại reader, không nạp lại chính supervisor — bot có cảnh báo dòng này).
- **Đừng bấm `server-BAT` khi đã có supervisor chạy** trừ khi muốn restart (bản mới tự kill
  cũ nên an toàn, nhưng nhớ chỉ để 1 supervisor poll 1 token, kẻo 409). Từ nay restart
  KHÔNG còn mất tải: hàng đợi bền hoá + tự resume (job đang chạy sẽ tải tiếp từ chỗ dở).
- Sửa **CODE** `reader_server.py` phải restart reader; sửa tay **`series-meta.json`** thì F5
  (mtime tự nạp). Prune/reorder/status trong web admin ăn ngay (không cần restart).
- `.reader-meta/notify-config.json` chứa **token thật** — không commit (đã gitignore).
- **1 hàng đợi CHUNG cho MỌI admin**: `/tai` của mọi admin (mọi `cid`) đổ vào **cùng
  `_jobs`**, chỉ **1 worker** xử lý **tuần tự, FIFO** (vào trước chạy trước, KHÔNG phân biệt
  admin, không luân phiên). Cố ý 1 luồng vì van điều tốc PoliteGate nằm TRONG mỗi tiến trình
  `comic_downloader.py`, KHÔNG phối hợp giữa các tiến trình → 2 truyện song song = gấp đôi
  request = dễ chặn IP. (Đây là lý do 07/08 One Punch Man của em xếp sau spirit-farmer, chưa
  tới lượt thì restart xoá mất.)
- **Tải song song (rủi ro)**: `Tai hang loat.bat`/`Tai truyen.bat` bấm tay là tiến trình NGOÀI
  hàng đợi bot → chạy song song với worker bot = gấp đôi request. Đừng chạy tay lúc bot đang
  tải (và ngược lại). Lúc supervisor **khởi động** nó tự **giết mọi `comic_downloader.py` lạc**
  trước khi resume (chống 2 tiến trình cùng tải) — nên tránh chạy tay đúng lúc supervisor bật
  lại (sẽ bị dọn nhầm).
- Download qua bot chạy **ẩn (CREATE_NO_WINDOW)** — không có cửa sổ là bình thường; theo dõi
  bằng tin Telegram "Tải xong"/"Lỗi", folder `downloads\`, hoặc **tail `.reader-meta\tai-run.log`**
  (output downloader ghi vào file này, real-time).
- Script ad-hoc in tiếng Việt cần `PYTHONIOENCODING=utf-8` (console cp1252).
