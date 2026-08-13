# Handoff — cập nhật lần cuối: 2026-08-13 (Bookmarked ở Home sắp theo thời điểm bấm)

> Kiến trúc ổn định (reader, provider, comix, supervisor, mạng…) nằm ở `.claude/ARCHITECTURE.md`.
> File này chỉ ghi TRẠNG THÁI hiện tại + việc đang dở.

## Đang làm / dở dang
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
- 11/08: **Reader CHỈ quét `downloads/`** (bỏ quét gốc project) — tránh nhận nhầm folder công cụ
  (`realesrgan-*`, `cover`) thành truyện. Deploy `/update` + restart reader.
- 11/08: **ACGNProvider** — HTML tĩnh (ảnh `_src` trong `view-{id}.htm`, list tập `manhua-{slug}.htm`,
  số chương từ text `VOL`/`第N話`); tên folder GIỮ tiếng Trung (khỏi dep pypinyin → deploy chỉ `/update`).
- 11/08: **Supervisor chống-chịu mạng + heartbeat + BỎ health_loop** — gate mạng mọi vòng, backoff
  cloudflared 3→300s, giữ hàng đợi khi lỗi-mạng, heartbeat ping healthchecks.io. **Bỏ health_loop**
  vì GET link công khai từ server sai ~2/3 (không hairpin) → giết nhầm tunnel tốt; báo link khi
  **reader nội bộ 127.0.0.1** sẵn sàng, tin cloudflared tự lo kết nối.
- 10/08: **Comix tự dựng lại Chromium** — `alive()` phân biệt browser-chết vs điều-hướng-hụt;
  `MAX_RELAUNCH=3`/`FAIL_STREAK_LIMIT=6` → thoát ≠0 báo lỗi thật thay vì "xong" giả.
- 09/08: **Comix = loop riêng `comix_site.py`** (Playwright headful + hook JSON.parse) — API mã hoá
  + token per-request; chọn official trước, scan id lớn nhất; skip official vĩnh viễn; upgrade cross-site.
- 09/08: **TruyenQQProvider** + **MangaDexProvider** (bản en, newest-wins, đòi Referer).
- 09/08: **Chống crash tầng C downloader** (`faulthandler`+breadcrumb+chặn bom) + `.bat` báo trung thực.

## Việc tiếp theo
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
