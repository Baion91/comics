# Bộ công cụ tải & quản lý truyện

Các script trong thư mục này, mỗi cái một việc:

| Script / File | Việc |
|---|---|
| `comic_downloader.py` | **Tải truyện đa site** — Asura, Raven... tự nhận theo link |
| `Tai truyen.bat` | Bấm để tải: dán link → chọn chương (chạy comic_downloader) |
| `check_library.py` | **Kiểm tra ảnh đã tải** — bắt ảnh hỏng/cụt/thiếu trang/đen |
| `Kiem tra truyen.bat` | Bấm để kiểm tra: chọn thư mục (chạy check_library) |
| `asura_downloader.py` | (cũ, vẫn chạy) lối tắt chỉ-Asura của comic_downloader |
| `pokespe_update.py` | Cập nhật Pokemon Special (pokemonspecial.com) — chạy riêng |
| `convert_webp.py` | Chuyển folder ảnh PNG sang WebP để giảm dung lượng |
| `reader_server.py` | Web đọc truyện kiểu Asura, đọc từ PC lẫn điện thoại |

## Chuẩn bị (chỉ cần 1 lần)

- Đã cài Python 3 cùng 2 thư viện `requests` và `Pillow` (máy này có sẵn cả rồi).
- Cách mở terminal đúng chỗ: mở thư mục `D:\claude-code\comics` trong File
  Explorer → gõ `cmd` vào thanh địa chỉ → Enter.
- Nếu lệnh `python` không chạy, thay bằng `py`.

---

## 1. Tải truyện — `comic_downloader.py` (hoặc bấm `Tai truyen.bat`)

Một tool cho MỌI site, tự nhận site theo link (hiện hỗ trợ **Asura**, **Raven**, **Dilib**).

Cách nhanh nhất: **double-click `Tai truyen.bat`** → dán link → chọn chương → xong
hỏi tải tiếp. Hoặc chạy lệnh:

```bat
:: Tải cả bộ (chạy lại = tải bù chương mới, tự bỏ qua ảnh đã có)
python comic_downloader.py https://ravenscans.org/series/rankers-return-remake/
python comic_downloader.py https://asurascans.com/comics/overgeared-1d35e5bd

:: Từ chương 1 đến 50 / chọn chương lẻ / kèm đóng .cbz
python comic_downloader.py <URL> --from 1 --to 50
python comic_downloader.py <URL> --chapters 5,7,20-25
python comic_downloader.py <URL> --cbz

:: Ép site khi lỡ gõ slug trần thay vì URL
python comic_downloader.py --site raven rankers-return-remake
```

- URL lấy từ thanh địa chỉ trình duyệt khi mở trang truyện.
- Ảnh lưu vào `downloads\<Tên truyện>\Chapter N\001...` — **Asura là .webp, Raven là
  .jpg** (giữ nguyên, không nén lại vì jpg nén tiếp là lossy chồng lossy).
- Ảnh bìa tự tải về `cover.*` trong folder truyện (đã có thì giữ nguyên).
- Chương premium/khóa chưa mở công khai sẽ được bỏ qua (có báo).
- **Tự kiểm ảnh khi tải**: mỗi ảnh được kiểm độ dài truyền tải + giải mã thử
  *trước khi ghi* — ảnh cụt/hỏng/không-phải-ảnh **không** để lại file, nên chạy
  lại lệnh là tự tải bù. Cuối phiên báo chương nào còn thiếu trang. (Ảnh "đen"
  do tác giả vẽ vẫn tải bình thường; xem mục kiểm tra bên dưới.)
- **Phân biệt lỗi mạng với lỗi của chính nguồn**: nếu tải lại mà ảnh vẫn hỏng
  **y hệt** (cùng số byte) thì đó là file hỏng sẵn trên server — tool dừng thử
  lại, ghi vào sổ `.reader-meta\image-issues.json` và **các lần chạy sau tự bỏ
  qua** (khỏi tốn request). Nó sẽ báo *"hỏng tại nguồn — tải lại vô ích"* chứ
  không xui bạn chạy lại. Muốn thử lại (vd nhóm dịch đã up lại): thêm cờ
  `--retry-broken`.
- **Cứu vớt ảnh cụt**: ảnh hỏng ở nguồn nhưng còn đọc được ≥50% thì **vẫn được
  lưu** (giữ nguyên byte gốc, phần cuối hiện xám) thay vì mất trắng cả trang —
  đúng như trình duyệt vẫn hiển thị. Có ghi chú trong báo cáo, và tool quét sẽ
  **không** báo hỏng hay cách ly nó nữa.
- `asura_downloader.py <URL|slug>` cũ **vẫn chạy** (mặc định Asura) — nay chỉ là lối tắt.

### Nén folder ảnh thành .cbz

```bat
python comic_downloader.py --pack "downloads\Overgeared"
```

Quét mọi thư mục con chứa ảnh, mỗi thư mục nén thành 1 file `.cbz` cùng tên
đặt bên cạnh (nhận webp/jpg/png/gif...). Cái nào có `.cbz` rồi thì bỏ qua.

## 2. Kiểm tra ảnh đã tải — `check_library.py` (hoặc bấm `Kiem tra truyen.bat`)

Downloader đã chặn ảnh hỏng ngay lúc tải, nhưng **đống truyện tải từ trước** thì
chưa được soi. Tool này quét lại ảnh **đã nằm trên đĩa**:

```bat
:: Quét cả thư viện downloads\ (lần đầu chậm, các lần sau nhanh nhờ cache)
python check_library.py

:: Chỉ quét 1 bộ / 1 chương
python check_library.py "downloads\Rankers Return Remake"
python check_library.py "downloads\Rankers Return Remake\Chapter 5"

:: Cách ly (đổi tên .bad) ảnh CHẮC CHẮN hỏng; khám lại bỏ cache; chỉnh số luồng
python check_library.py --fix
python check_library.py --recheck
python check_library.py --workers 4

:: QUÉT SÂU: thêm dò 'trang một màu' (bỏ cache, chậm — dùng khi cố ý săn ảnh đen)
python check_library.py --black
```

Quét mặc định (nhanh) bắt 2 loại:
- **Hỏng/cụt/không-phải-ảnh** — giải mã thử từng ảnh. Thêm `--fix` sẽ đổi tên
  ảnh hỏng thành `<tên>.bad` (reader tự ẩn); chạy lại lệnh **tải** bộ đó là tự
  tải bù chỗ trống (tải xong tự xóa `.bad`, **không phải xóa tay**).
- **Khuyết trang** — số trang trong chương bị đứt quãng (vd có 001,002,004 →
  thiếu 003).

Những trang đã xác định **hỏng sẵn ở nguồn** (ghi trong `image-issues.json`) sẽ
được báo là *"đã biết — tải lại vô ích, không cần làm gì"*, và ảnh đã **cứu vớt**
thì không bị báo hỏng/cách ly nữa — nên bạn chỉ thấy việc thật sự cần xử lý.

Thêm `--black` mới bật loại thứ 3 (**quét sâu, chậm**):
- **Trang một màu** — ảnh mà **cả khung** gần như một màu (đen/trắng/xám phẳng =
  không có nội dung). Chỉ bắt trang một-màu-toàn-phần nên **tranh đen/cảnh đêm do
  tác giả vẽ KHÔNG bị báo nhầm** (tranh vẽ luôn có nét). Chỉ **báo**, không tự
  xóa: mở báo cáo xem tận mắt rồi tự quyết. Trang đen/trắng có chủ ý thì thêm
  đường-dẫn của nó vào `.reader-meta\check-ignore.txt` để thôi báo (báo cáo ghi
  sẵn dòng cần thêm).

Kết quả: tóm tắt ở cửa sổ lệnh (có bộ đếm + ETA) + **báo cáo
`.reader-meta\check-report.html`** (mở bằng trình duyệt — có ảnh thu nhỏ). Chạy
nhiều luồng (mặc định = số nhân CPU, tối đa 8) và ghi nhớ ảnh tốt (cache) nên
**lần quét sau chỉ soi cái mới/đổi → rất nhanh**; lỡ Ctrl-C giữa chừng cũng không
mất tiến độ, chạy lại là tiếp. Cần Pillow (máy này có sẵn); thiếu Pillow thì chỉ
kiểm được chữ ký file, bỏ phần giải mã & dò một-màu.

## 3. Cập nhật Pokemon Special — `pokespe_update.py`

```bat
:: Xem web có chương Scarlet Violet mới không (chưa tải gì)
python pokespe_update.py --dry-run

:: Tải mọi chương còn thiếu vào đúng chỗ trong thư viện
python pokespe_update.py
```

- Tự so danh sách chương trên blog với folder trong
  `downloads\Pokemon Special_webp\CHƯƠNG 698-- - SCARLET VIOLET`.
- Ảnh tải bản gốc full nét; PNG tự chuyển WebP q85, JPG giữ nguyên.
- Mỗi trang đều được kiểm tra toàn vẹn ngay khi tải, ảnh hỏng không lọt vào
  thư viện.

## 4. Chuyển PNG sang WebP — `convert_webp.py`

```bat
:: Cơ bản: PNG -> WebP q85, JPG và file khác copy nguyên trạng
python convert_webp.py "downloads\Ten-folder-truyen"

:: Tùy chọn thêm
python convert_webp.py "..." --quality 90    :: nét hơn, to hơn chút
python convert_webp.py "..." --jpg-too       :: nén cả JPG (lưu ý: lossy chồng lossy)
```

- Kết quả xuất ra thư mục mới `<tên>_webp` **bên cạnh** thư mục gốc —
  **không sửa/xóa gì ở thư mục gốc**. Ưng kết quả rồi mới tự tay xóa gốc.
- Với truyện scan, q85 giảm ~50–80% dung lượng mà mắt thường không phân biệt
  được.

## 5. Web đọc truyện — `reader_server.py`

```bat
:: Bật server đọc truyện (để cửa sổ này mở trong lúc đọc)
python reader_server.py

:: Nếu cổng 8080 bị chiếm
python reader_server.py --port 8081
```

- **Đọc trên PC**: mở trình duyệt vào `http://localhost:8080`.
- **Đọc trên điện thoại**: điện thoại cùng Wi-Fi với PC, mở địa chỉ
  `http://<IP-máy-tính>:8080` — IP chính xác được in ra màn hình khi chạy
  script. Lần đầu chạy nếu Windows Firewall hỏi thì chọn **Allow access**.
- Giao diện kiểu Asura (**chữ tiếng Anh**): cuộn dọc (vuốt trên điện thoại / con
  lăn chuột trên PC), thanh công cụ tự ẩn khi cuộn xuống — chạm màn hình để hiện
  lại, nút **Prev/Next** + dropdown chọn chương (nhóm theo arc với Pokemon Special).
- **Thứ tự chương**: dropdown chọn chương (lúc đang đọc) xếp **mới nhất trên cùng**;
  còn danh sách ở trang truyện mặc định mới-nhất-trên-cùng, bấm **Newest ⇄ Oldest**
  để đảo (xem mục Trang truyện). Prev/Next và First/Latest Chapter luôn đọc xuôi
  theo thứ tự chương.
- Trên PC dùng nút `−`/`+` góc phải để chỉnh độ rộng trang; phím `←`/`→`
  chuyển chương; zoom thêm bằng `Ctrl` + lăn chuột (điện thoại: véo 2 ngón).
- **Theo dõi truyện (bookmark)**: bấm nút **Bookmark** (tím, dưới mỗi truyện ở
  trang chủ / cạnh ảnh bìa ở trang truyện) → chuyển **nền xám, sao + chữ vàng
  "Bookmarked"**. Truyện đang theo dõi hiện thành hàng **"Bookmarked"** cuộn ngang
  trên cùng trang chủ; card ghi luôn chương đang đọc (chưa đọc thì chương đầu),
  bấm là mở đúng chỗ đó. (Giao diện reader đã chuyển sang tiếng Anh.)
- **Đổi thứ tự trang chủ**: sửa `.reader-meta\series-meta.json`, thêm trường số
  `"order"` cho truyện (đi cùng `"status"`) — số nhỏ lên trước; truyện **không có**
  `order` rơi xuống cuối theo A→Z. Lưu rồi **F5** (không cần restart). Truyện mới
  tải về **tự được đánh `order` = số lớn nhất hiện có + 1** (xuống cuối), bạn chỉ
  sửa lại số khi muốn xếp lên trên. Ví dụ:
  `"Solo Leveling": { "status": "ongoing", "order": 1 }`.
- **Trang truyện**: nút **First Chapter** (chương đầu) và **Latest Chapter** (chương
  mới nhất, nền xanh dương); nếu đang đọc dở thì nút thứ 2 thành **"Chapter X -
  reading"** (nền xanh lá) mở đúng chỗ đọc dở. Ô **Search chapters…** lọc theo
  số/tên tức thì; nút **Newest ⇄ Oldest** đảo thứ tự danh sách chương.
- **Tài khoản & nhớ chỗ đọc**: góc trên phải có ô **Username** — nhập tên rồi **Login**
  (không mật khẩu, chỉ để tách người). Khi **đã đăng nhập**, bookmark / vị trí đọc dở /
  chương đã đọc lưu **trên server theo tài khoản** (`.reader-meta\users.json`) → đăng nhập
  lại ở máy nào cũng thấy, không mất khi đổi link/restart. **Chưa đăng nhập (guest)** thì
  mấy dữ liệu này lưu **trong trình duyệt máy đó** (localStorage) — mỗi máy riêng, không
  đụng người khác. Hai bên **tách riêng**, không trộn. Cỡ ảnh + kiểu sort chương luôn để
  riêng từng máy.
- **Tìm truyện**: ô **Search comics** ở trang chủ lọc theo tên tức thì.
- **Web admin** (đăng nhập đúng username `admin`): trang chủ hiện thêm **Refresh** +
  **Dọn list** (bỏ mục truyện đã xoá khỏi danh sách), và mỗi truyện có nút đổi
  **Completed/Ongoing** + **⤒/▲/▼** sắp thứ tự — bấm là đổi ngay, khỏi sửa file tay.
  (Sửa tay `series-meta.json` vẫn dùng được như mô tả trên/dưới.)
- Có cả folder `<tên>` lẫn `<tên>_webp` thì reader **tự ẩn bản gốc**, chỉ hiện bản `_webp`.
- **Ảnh bìa**: đặt file `cover.jpg`/`cover.png`/`cover.webp` vào folder truyện
  là bìa hiện đúng ảnh đó (truyện Asura được downloader tự tải bìa sẵn).
  Không có thì lấy trang đầu chương đầu.
- **Trạng thái truyện (Completed / Ongoing)**: hiện cạnh số chương ở trang chủ và
  trang truyện (xanh lá = Completed, xanh dương = Ongoing). Mặc định mọi truyện là
  **Ongoing**; muốn đánh dấu đã hoàn thành thì mở `.reader-meta\series-meta.json`,
  đổi `"status": "ongoing"` thành `"complete"` cho đúng truyện (khóa là **tên
  folder** trong `downloads\`, ví dụ `Pokemon Special_webp`), lưu lại rồi **F5** —
  **không cần tắt/bật server**. Truyện mới tải về tự được thêm vào file này (mặc
  định Ongoing), nên bạn chỉ việc sửa giá trị khi cần.
- **Ghép trang đôi** (truyện để 2 nửa trang rời như Pokemon Ouja no Saiten):
  bấm nút `⧉` trên thanh công cụ để vào chế độ ghép → giữa các trang hiện nút
  **Ghép 2 trang trên–dưới**. Ghép xong nếu ngược chiều thì bấm **⇄ Đảo
  trái/phải**, muốn hoàn tác bấm **Tách**. Lựa chọn lưu ở
  `.reader-meta\spreads.json` — mọi thiết bị cùng thấy, ảnh gốc không bị sửa.
- **Đọc ngoài mạng nhà (Tailscale)**: PC và iPhone đã cài + đăng nhập sẵn.
  Ra ngoài chỉ cần bật app Tailscale trên điện thoại rồi mở
  `http://100.87.162.74:8080`. Muốn cho người khác đọc: vào
  https://login.tailscale.com/admin/users → **Invite users** → nhập email họ;
  họ cài app Tailscale, đăng nhập là mở được đúng địa chỉ trên (PC phải bật).
- Tự quét thư mục này và `downloads\`: truyện tải mới, chương tải mới
  **tự xuất hiện**, không phải cấu hình gì. Không sửa/ghi gì vào folder truyện.
- Server **bật thủ công** bằng shortcut Desktop **"Toony"** (không đặt tự chạy cùng
  Windows — giữ toàn quyền bật/tắt trên máy làm việc).

---

## 6. Chạy trên SERVER (tự động) + đồng bộ code + điều khiển qua Telegram

Ngoài chạy tay ở trên, bộ này dựng được thành **server đọc chung** (vd máy khác) tự bật
khi đăng nhập Windows, tự tạo link đọc từ xa và báo qua Telegram.

- **Bật/tắt trên server**: `server-BAT-tudong.bat` (đăng ký chạy-khi-đăng-nhập + bật ngay
  reader + cloudflared + Telegram; **tự kill tiến trình cũ** nên bấm lại an toàn) /
  `server-TAT-tudong.bat` (tắt hết + gỡ đăng ký).
- **Link đọc từ xa**: cloudflared quick-tunnel tự tạo link `…trycloudflare.com` và gửi qua
  **Telegram bot** cho ai đã nhắn bot. Link **đổi mỗi lần server/tunnel khởi động lại**.
  Trên server chạy `get-cloudflared.bat` một lần để tải cloudflared.
- **Đồng bộ code bằng git** (repo GitHub `Baion91/comics`, Public — không chứa secret):
  - Máy dev: **`day-len.bat`** = đẩy code lên GitHub (git add + commit + push).
  - Server: **`cap-nhat.bat`** = kéo code mới + restart, HOẶC nhắn **`/update`** cho bot
    (chỉ restart reader, **giữ nguyên link**). Sửa `supervisor.py` thì phải dùng `cap-nhat.bat`.
- **Lệnh Telegram bot** (gõ **`/help`** để xem đủ; mỗi lệnh là **1 từ liền**):
  - `/link` link hiện tại · `/whoami` xem chat_id của bạn · `/help` danh sách lệnh.
  - **Admin**: `/tai <link>` tải truyện (xếp hàng đợi, báo bắt đầu/xong) · `/update` cập
    nhật code · `/adminclaim` (người đầu tiên → admin gốc) · `/adminlist` ·
    `/adminadd <id>` · `/adminremove <id>`.
- Token bot để trong `.reader-meta\notify-config.json` (**không** commit lên git).
- **Tải hàng loạt** (chạy tay): `Tai hang loat.bat` — dán nhiều link vào `download-queue.txt`
  rồi chạy lần lượt (bỏ qua chương đã đủ nhờ dấu `.done`).

---

## Ghi nhớ chung

- Bộ *Pokemon Ouja no Saiten* đã được chuyển sang WebP q85 (605MB -> 454MB,
  trang nặng 2-4.5MB nay còn vài trăm KB). Bản PNG gốc còn nguyên trong
  `downloads\.Pokemon Ouja no Saiten_png-goc` (folder ẩn, web reader bỏ qua) —
  muốn khôi phục thì đổi tên hai folder ngược lại là xong.

- **Chạy lại luôn an toàn**: các script tải đều bỏ qua thứ đã có — đứt mạng hay
  tắt máy giữa chừng thì chạy lại đúng lệnh cũ là tiếp tục từ chỗ dở. Nay ảnh
  hỏng cũng không để lại file, nên chạy lại là tự tải bù đúng chỗ đó.
- **Chống bị chặn (429)**: script tải có van điều tốc (~1.5-2 ảnh/giây, nghỉ
  ngẫu nhiên, giải lao mỗi 10 chương) và cầu dao tự ngắt — server nhắc 429 là
  toàn bộ tạm dừng rồi tự chạy tiếp. Nếu script tự kết thúc sớm vì bị chặn
  nhiều lần: chờ ~1 giờ rồi chạy lại đúng lệnh cũ. Đừng chỉnh `--workers` cao —
  không nhanh hơn (van chung vẫn giữ nhịp) mà chỉ thêm rủi ro.
- **Đọc trên máy tính**: mở `.cbz` bằng SumatraPDF hoặc CDisplayEx.
- **Đọc trên điện thoại giống web truyện**: chép `.cbz` vào
  `Bộ nhớ trong\Mihon\local\<Tên truyện>\` (app Mihon, Android) rồi chọn chế
  độ đọc Webtoon; iOS dùng app Panels.
- Truyện tải về chỉ dùng đọc cá nhân, không chia sẻ lại.
