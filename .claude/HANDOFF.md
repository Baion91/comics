# Handoff — cập nhật lần cuối: 2026-08-05

## Đang làm / dở dang
- Không có việc code dở.
- **Vừa xong (05/08): 3 tinh chỉnh UI reader (trên nền reader "v2")**
  - **Hết giật dòng "Bookmarked" ở Home**: bỏ bật/tắt `hidden` (chèn/rút ~300px tức
    thời) → mục **co/giãn có animation** bằng `grid-template-rows:0fr↔1fr` + wrapper
    `.follows-inner` (overflow:hidden) + toggle class `.open`. Server render sẵn `.open`
    khi có bookmark; mỗi `fcard` có `data-sid`.
  - **`renderFollows` incremental**: không dựng lại `innerHTML` nữa — **chèn/gỡ/di chuyển
    từng card** (dùng `appendChild` để move node sẵn có → ảnh không tải lại/chớp); dọn
    card sót ở `transitionend` (có guard chống mất card khi bấm lại giữa chừng).
  - **Độ êm animation = Preset A**: `cubic-bezier(.37,0,.63,1)` (easeInOutSine) `.45s`,
    opacity đồng bộ `.45s`. (Đã thử easeOutExpo `.32s` → user thấy "đập/mạnh", đổi sang
    ease-in-out mềm mới thật nhẹ.) `prefers-reduced-motion` vẫn nhảy thẳng.
  - **Nút "lên đầu trang" `#totop` kiểu Liquid Glass**: tròn 54px góc phải-dưới, mũi tên
    **LÊN**, `backdrop-filter:blur(20px) saturate(180%)` (+`-webkit-`) + nền mờ sáng +
    viền/highlight/bóng. **Chỉ Home + trang truyện (series)**; trang đọc ảnh KHÔNG có nút.
    Hiện khi cuộn `>0.5·vh`, ẩn khi `<0.45·vh` (hysteresis). Bấm = `scrollTo top` native
    smooth (reduced-motion → `auto`). JS gate `#totop`, chạy mọi trang tự no-op.
  - **CHƯA nghiệm thu LIVE** trên trình duyệt — mới verify server-side render + parse
    Python. User tự mở bằng shortcut "Toony" (ràng buộc không auto-start).

## Quyết định gần đây (tối đa ~10 dòng, mỗi dòng 1 quyết định)
- 05/08: **Dòng Bookmarked co/giãn có animation thay cho toggle `hidden`** — vì `hidden`
  chèn/rút cả khối ~300px tức thời gây giật ở mốc 0↔1 bookmark.
- 05/08: **Animation Bookmarked chốt Preset A (easeInOutSine `.45s`)** — easeOutExpo bung
  nhanh lúc đầu = "đập/mạnh"; ease-in-out khởi động từ tốn mới thật nhẹ nhàng.
- 05/08: **`renderFollows` chuyển sang incremental (chèn/gỡ từng card)** — tránh dựng lại
  innerHTML làm ảnh trong slider tải lại/chớp mỗi lần bấm.
- 05/08: **Nút lên-đầu-trang: mũi tên LÊN + native smooth scroll** — đơn giản trước, để
  ngỏ nâng cấp rAF ease-out nếu chưa đủ êm.
- 05/08: **Hồ sơ đọc = 1 JSON CHUNG server-side** (`user-data.json`), không login/cookie/
  device-id — vì localStorage chết theo origin (link trycloudflare đổi URL → mất tiến trình).
- 05/08: **Thứ tự Home vào `series-meta.json` (`order`), bỏ kéo-thả**; truyện mới auto `max+1`.
- 05/08: **Sort chương thành TOGGLE Newest/Oldest (client) + Search chương**.
- 05/08: **UI reader sang tiếng Anh**; giữ comment/log tiếng Việt.
- 05/08: **Feedback: nhún = nền mọi nút; loé sáng chỉ cho dòng danh sách + toggle tại chỗ**.
- 04/08: **Trạng thái truyện = JSON tập trung + sửa tay live (mtime)** `series-meta.json`.

## Việc tiếp theo
- **User nghiệm thu LIVE 3 tinh chỉnh mới** (restart Toony + F5): (1) bookmark/bỏ bookmark
  mốc 0↔1 ở Home có êm không; (2) nút kính lên-đầu-trang hiện/ẩn đúng nửa màn + cuộn êm,
  ở cả Home lẫn trang truyện; (3) trang đọc ảnh không có nút. Đặc biệt xem hiệu ứng kính
  `backdrop-filter` trên iPhone thật.
- (Nếu vẫn thấy animation Bookmarked hơi mạnh) lever tiếp = **giảm chiều cao shelf** (thu
  nhỏ card theo dõi) để quãng dịch lưới dưới ngắn lại — chưa làm.
- **User nghiệm thu LIVE reader v2** trên iPhone + PC (nhún/loé, bố cục trang truyện, English).
- (Tùy chọn) dịch nốt **log terminal** (`main()`) sang tiếng Anh.
- Backlog tải (CHƯA XÁC MINH lại phiên này — số cũ 25/07): Rankers Return còn ~77 chương;
  Overgeared local 517 ảnh / nguồn 332 chương.

## Lưu ý / rủi ro đang mở
- **Nút `#totop` dùng `backdrop-filter`**: cần bản `-webkit-` cho Safari iOS (đã có).
  Hiệu ứng kính CHƯA nghiệm thu trên iPhone thật.
- **Animation `grid-template-rows` là layout-bound** (không GPU) → máy yếu / Home nặng có
  thể micro-stutter nhẹ; trần vật lý: shelf cao ~300px nên lưới dưới vẫn dịch một quãng dài.
- **Reset hồ sơ đọc**: xoá cả file `.reader-meta/user-data.json` — NHƯNG phải **TẮT server
  trước** (xoá lúc đang chạy có thể bị ghi đè lại data cũ từ cache RAM `_udata`).
- **Hồ sơ CHUNG, không mật khẩu**: khách qua link tunnel thấy & sửa được bookmark/tiến
  trình → bật tunnel chỉ khi cần, tắt (`Tat chia se link.bat`) khi xong.
- Sửa **CODE** `reader_server.py` phải RESTART Toony; sửa tay **`series-meta.json`** thì F5 (mtime).
- `check-report.html` là ảnh chụp; `.bad` trên đĩa mới là sự thật. `--black` là quét SÂU (chậm).
- Script ad-hoc in tiếng Việt cần `PYTHONIOENCODING=utf-8` (console cp1252).
