# Bộ công cụ tải & quản lý truyện

Các script trong thư mục này, mỗi cái một việc:

| Script / File | Việc |
|---|---|
| `comic_downloader.py` | **Tải truyện đa site** — Asura, Raven... tự nhận theo link |
| `Tai truyen.bat` | Bấm để tải: dán link → chọn chương (chạy comic_downloader) |
| `check_library.py` | **Kiểm tra ảnh đã tải** — bắt ảnh hỏng/cụt/thiếu trang/đen |
| `Kiem tra truyen.bat` | Bấm để kiểm tra: chọn thư mục (chạy check_library) |
| `asura_downloader.py` | (cũ, vẫn chạy) lối tắt chỉ-Asura của comic_downloader |
| `convert_webp.py` | Chuyển folder ảnh PNG sang WebP để giảm dung lượng |
| `realesrgan-.../lam-net.bat` | **Làm nét ảnh scan** bằng Real-ESRGAN (AI upscale 2x) |
| `reader_server.py` | Web đọc truyện kiểu Asura, đọc từ PC lẫn điện thoại |

## Chuẩn bị (chỉ cần 1 lần)

- Đã cài Python 3 cùng 2 thư viện `requests` và `Pillow` (máy này có sẵn cả rồi).
- Cách mở terminal đúng chỗ: mở thư mục `D:\claude-code\comics` trong File
  Explorer → gõ `cmd` vào thanh địa chỉ → Enter.
- Nếu lệnh `python` không chạy, thay bằng `py`.

---

## 1. Tải truyện — `comic_downloader.py` (hoặc bấm `Tai truyen.bat`)

Một tool cho MỌI site, tự nhận site theo link (hiện hỗ trợ **Asura**, **Raven**, **Dilib**,
**MangaDex**, **TruyenQQ**, **Comix**, **ACGN**).

> **Raven Scans đã đổi `ravenscans.org` → `ravenscans.net`** (và đổi cấu trúc URL chương) —
> dùng link `.net` mới; link `.org` cũ vẫn được nhận.

> **MangaDex**: dán link `https://mangadex.org/title/...` như bình thường. Chỉ tải bản dịch
> **tiếng Anh**, tự chọn bản mới/nét nhất khi 1 chương có nhiều nhóm dịch. Truyện đã có bản
> quyền tiếng Anh đôi khi **thiếu vài chương** (bản "external" trỏ ra trang đọc chính thức,
> ảnh không nằm trên MangaDex) — đó là giới hạn nguồn, không phải lỗi tool.

> **TruyenQQ** (truyện tiếng Việt): dán link trang truyện `https://truyenqqko.com/truyen-tranh/...`
> (dán link 1 chương cũng được, tool tự về trang truyện). Ảnh trên CDN của site **chống hotlink**
> nên tool tự gửi kèm Referer — không cần làm gì thêm. ⚠️ Site này **đổi tên miền liên tục**
> (truyenqq.com → ...to → ...ko → ...); nếu link cũ không nhận nữa thì dùng **domain hiện hành**,
> hoặc báo để thêm domain mới vào provider.

> **ACGN** (comic.acgn.cc, 動漫戲說 — truyện tiếng Trung phồn thể): dán link trang truyện
> `https://comic.acgn.cc/manhua-{slug}.htm` **hoặc** link 1 tập `https://comic.acgn.cc/view-{id}.htm`
> (dán tập nào tool tự tìm về cả bộ). Site HTML tĩnh nên tải thẳng, không cần mở trình duyệt.
> **Tên folder giữ nguyên tiếng Trung** (vd `摺紙戰士`) — Windows/reader đọc bình thường; chương
> đánh số theo `VOL`/`第N話` trên site. ⚠️ CDN ảnh `img.acgn.cc` **lọc theo vùng**: server VN tải
> OK, nhưng nhiều nơi ngoài VN bị Cloudflare báo lỗi **522** (không phải lỗi tool) — nên **tải trên
> server** là chắc ăn.
>
> **Comix** (comix.to, tức Comick): dán link `https://comix.to/title/...`. Site mã hóa API nên
> tool phải **mở 1 cửa sổ Chromium** để lấy danh sách chương/ảnh — **đừng đóng cửa sổ đó**,
> xong tool tự đóng (cần cài 1 lần: `pip install -r requirements.txt` rồi
> `python -m playwright install chromium` — `cap-nhat.bat` trên server tự làm). Mỗi chương tự
> chọn **bản Official (tick ✓)** nếu có, không thì lấy **bản scan mới nhất CÓ tên nhóm** (chỉ khi
> không còn bản nào có nhóm mới lấy bản không nhóm); chương đã tải bằng
> bản scan mà sau này có bản Official thì **chạy lại lệnh là tự thay** (bản Official đã tải thì
> không bao giờ tải lại). Nếu bot nhắn "bị Cloudflare chặn" → ra màn hình server tick
> "Verify you are human" trong cửa sổ Chromium là tool tự chạy tiếp.
>
> ⚠️ **Cửa sổ Chromium đứng im ở trang trắng (about:blank)?** Trước đây nếu còn 1 cửa sổ
> Chromium comix **mồ côi** (từ lần chạy trước) thì lần mở sau bị treo. **Đã sửa (14/08)**:
> mỗi lần chạy comix tool **tự giết Chromium comix cũ + xoá khoá profile** trước khi mở, và có
> "watchdog" — mở quá 90s không xong thì tự thoát báo lỗi thay vì treo. Nên **không cần** tự tay
> tắt Chromium nữa. (Lỡ vẫn kẹt: tắt hết `chrome.exe` trên server rồi chạy lại.)
>
> **Thay bản đã tải từ site khác:** nếu trước đó bạn tải một bộ từ Raven/Asura/... rồi chạy lại
> bằng link comix của đúng bộ đó, các chương cũ (bản scan) sẽ **tự được thay bằng Official** khi
> comix có (khớp theo số chương). Nếu tên hai bên **khác nhau** thì sẽ thành **2 folder** — comix
> đặt một file dấu `_COMIX_official_*.txt` ở gốc folder của nó (mở trong Explorer thấy ngay số
> "official/tổng"); **giữ folder có file dấu, tự xoá folder scan trùng** (không có file dấu). Nếu
> tên trùng nhau thì cả hai dùng chung 1 folder, không cần xoá gì.
>
> **Nếu 1 chương lỗi tải:** tool **không còn dừng cả bộ** — chương nào chập chờn (mạng/quảng cáo
> chèn) sẽ được ghi "chưa lấy được" và **bỏ qua đi tiếp**, cuối vẫn báo "Tải xong" kèm danh sách
> chương còn thiếu; **chạy lại lệnh là tự bù**. (Quảng cáo của site đã được chặn sẵn trong trình
> duyệt tải nên hiếm khi dính.)

Cách nhanh nhất: **double-click `Tai truyen.bat`** → dán link → chọn chương → xong
hỏi tải tiếp. Hoặc chạy lệnh:

```bat
:: Tải cả bộ (chạy lại = tải bù chương mới, tự bỏ qua ảnh đã có)
python comic_downloader.py https://ravenscans.net/series/rankers-return-remake/
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
- **Cuối mỗi bộ có dòng tổng kết**: số chương *đủ ảnh / đã xong trước / thiếu
  trang / hỏng tại nguồn / khóa* — liếc là biết bộ nào cần chạy lại để bù.
- **Chống crash nửa chừng**: lỡ một ảnh lỗi làm Python sập bất ngờ (không có thông
  báo lỗi), tool tự ghi chỗ sập vào `.reader-meta\crash-trace.txt` + tên ảnh thủ
  phạm vào `download-log.txt`, và chặn sẵn ảnh "bom" quá khổ *trước khi* giải mã.
  Chạy lại lệnh cũ là tải tiếp bình thường.
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

## 3. Chuyển PNG sang WebP — `convert_webp.py`

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

## Làm nét ảnh scan — Real-ESRGAN (`realesrgan-ncnn-vulkan-v0.2.0-windows\lam-net.bat`)

Tool AI làm nét/upscale cho **trang truyện scan mờ**. Bản portable (ncnn/Vulkan), cần **GPU**
(máy này + server dùng GTX 1050 Ti). Lõi xử lý là `lam_net.py`, `lam-net.bat` chỉ là nút bấm
(giống `Tai truyen.bat` → `comic_downloader.py`). Cách dùng:

1. Bỏ ảnh cần làm nét vào thư mục `realesrgan-ncnn-vulkan-v0.2.0-windows\input\` — có thể để
   **ảnh phẳng** trực tiếp, HOẶC **copy cả các folder chương** (`Chapter 1`, `Chapter 2`...) vào `input\`
2. Bấm đúp `lam-net.bat` — chạy xong kết quả nằm ở `output-realesrgan\` (**PNG**, 2x), **giữ nguyên
   cấu trúc folder chương** như input (mỗi chương ra 1 folder cùng tên)

- **Model đã chốt: `realesr-animevideov3` scale 2x** — sau khi test thật (soi crop zoom 3x)
  đây là bản sắc nét mà **giữ nguyên chi tiết gốc** tốt nhất, lại nhanh. Đã bỏ 2 model nặng
  không dùng (`realesrgan-x4plus`, `realesrgan-x4plus-anime`) cho nhẹ.
- Xuất **PNG** (lossless) và **tile cố định 200** (an toàn VRAM 4GB khi chạy batch dài, không
  giảm chất lượng). Muốn đổi thì sửa các hằng số `FORMAT`/`TILE`/`SCALE`/`MODEL` đầu `lam_net.py`.
- **Đọc chương đúng thứ tự SỐ**: `lam_net.py` rút số ra khỏi tên folder rồi sort theo số
  (`1, 2, 3, ..., 10, ..., 43.5`), không dính lỗi kiểu chữ-cái `Chapter 1 → Chapter 10 → Chapter 2`.
  Hỗ trợ cả tên `Ch. 0.1`, chương thập phân.
- **Chỉ tính file ảnh**: tổng và tiến độ chỉ đếm ảnh (`.png/.jpg/.jpeg/.webp/.bmp`). File
  dấu của tool tải (`.done`, `.source.json`, `_COMIX_official_*.txt`) **bị bỏ qua hoàn toàn**,
  không tính vào tổng, không báo lỗi ảo.
- **Tiến độ gọn** (giống tool tải): một dòng cập nhật tại chỗ `[Chương k/N] tên | ảnh i/n |
  tổng x/y | ETA ...`. Tiến độ đo bằng **số file output thật sinh ra** (không đọc `%` của exe)
  nên **chính xác kể cả khi exe chạy đa luồng** và **không chớp tắt**. Mỗi chương xong in 1 dòng
  chốt, cuối tổng kết. **1 ảnh THẬT lỗi (không ra file) → tính lỗi + bỏ qua + chạy tiếp**, không
  treo cả bộ; cuối liệt kê chương có ảnh lỗi.
- **Tự bỏ qua chương đã xong**: chạy lại tool, chương nào đã có **đủ ảnh** trong
  `output-realesrgan\` sẽ bị **skip** (in "bỏ qua N chương đã xong"), chỉ làm chương mới/còn
  thiếu → thêm chương vào bộ rồi chạy lại rất nhanh, không phí GPU làm lại. Chương làm **dở**
  (output thiếu ảnh so với input) sẽ được **làm lại cả chương** cho chắc.
- **Muốn ép làm lại từ đầu** (kể cả chương đã xong — vd đổi tham số, output lỗi): lúc chạy
  `lam-net.bat`, ở câu hỏi `Lam lai ca chuong DA XONG? (y/N)` chọn **`y`** (tương đương
  `lam_net.py --force`). Bỏ trống/`n` = chế độ thường (bỏ qua chương đã xong).
- ⚠️ Để **folder chương trực tiếp** trong `input\`, đừng bọc thêm 1 lớp folder bộ truyện bên
  ngoài (chỉ xử lý 1 cấp folder con).
- ⚠️ Ảnh ra là **PNG 2x, nặng nhiều lần bản gốc**. Muốn đưa vào reader thì nên **nén lại**
  (dùng `convert_webp.py` hoặc hạ JPG/WebP q80–85) — đừng để nguyên PNG 2x cho cả kho.
- Thư mục `input\` và `output-realesrgan\` được `.gitignore` (không đẩy ảnh lên repo).
- **Chạy tự động trên server**: chưa tích hợp vào `/tai`. Kế hoạch (xem HANDOFF): enhance là
  bước hậu xử lý sau tải, xếp hàng tuần tự (GPU chỉ 1 job/lúc), enhance → resize xuống → nén,
  chỉ bật cho truyện scan kém.

## 4. Web đọc truyện — `reader_server.py`

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
  **Completed/Ongoing** + **⤒/▲/▼** sắp thứ tự + **đổi tên** + **đổi bìa** — bấm là
  đổi ngay, khỏi sửa file tay. (Sửa tay `series-meta.json` vẫn dùng được như mô tả trên/dưới.)
  - **Đổi tên** (icon bút vuông cạnh tên truyện): nhập tên hiển thị mới (để trống = về lại
    tên gốc theo folder). Chỉ đổi **tên hiển thị trên web**, lưu vào `series-meta.json` —
    **folder trên server GIỮ NGUYÊN** nên bookmark/tiến-trình đọc không bị mất.
  - **Đổi bìa** (icon ảnh-dấu-cộng ở góc trên-phải ảnh bìa): chọn 1 ảnh từ máy → server tự
    chuẩn hoá và ghi thành `cover.jpg` trong folder truyện (thay bìa cũ). Nên chọn ảnh
    **tỉ lệ 3:4** (xem mục Ảnh bìa) để không bị cắt.
- Có cả folder `<tên>` lẫn `<tên>_webp` thì reader **tự ẩn bản gốc**, chỉ hiện bản `_webp`.
- **Ảnh bìa**: đặt file `cover.jpg`/`cover.png`/`cover.webp` vào folder truyện
  là bìa hiện đúng ảnh đó (truyện Asura được downloader tự tải bìa sẵn), hoặc dùng nút
  **🖼️ Đổi bìa** ở web admin. Không có thì lấy trang đầu chương đầu.
  - **Kích thước chuẩn = tỉ lệ 3:4 (dọc)**, khuyến nghị **900×1200px** (hoặc 600×800). Mọi ô
    hiển thị (card trang chủ, bìa trang truyện 130×173, slider Bookmark) đều là khung **3:4,
    cắt tràn** — ảnh **đúng 3:4 sẽ KHÔNG bị cắt** ở đâu cả. Ảnh **rộng hơn** 3:4 bị cắt bớt
    **hai bên**; ảnh **cao hơn** 3:4 bị cắt bớt **phần dưới**. Server lưu bìa tối đa **480px
    ngang** (đủ nét cho mọi ô) nên ảnh nguồn ≥480px ngang là được.
  - Mỗi folder chỉ nên để **đúng 1 file `cover.*`** (nút 🖼️ tự xoá bìa cũ khi đổi).
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

## 5. Chạy trên SERVER (tự động) + đồng bộ code + điều khiển qua Telegram

Ngoài chạy tay ở trên, bộ này dựng được thành **server đọc chung** (vd máy khác) tự bật
khi đăng nhập Windows, tự tạo link đọc từ xa và báo qua Telegram.

- **Bật/tắt trên server**: `server-BAT-tudong.bat` (đăng ký chạy-khi-đăng-nhập + bật ngay
  reader + cloudflared + Telegram; **tự kill tiến trình cũ** nên bấm lại an toàn) /
  `server-TAT-tudong.bat` (tắt hết + gỡ đăng ký).
- **Tự lên sau reboot mà KHÔNG cần gõ mật khẩu** (Phương án A, từ 12/08): task chạy-khi-đăng-nhập
  chỉ lên khi có người đăng nhập Windows. Muốn sau reboot (vd Windows Update) server tự lên không
  cần thao tác: chạy **`server-AUTOLOGIN.bat`** một lần (quyền Admin) để bật Windows **tự đăng nhập**
  (dùng Sysinternals Autologon, mật khẩu mã hoá vào LSA — không lưu plaintext). Sau đó reboot là
  Windows tự đăng nhập → task tự chạy → **hiện cửa sổ log** + báo link Telegram.
  - **Lưu ý dùng phương án A**: server gắn với phiên đăng nhập → muốn chuyển tài khoản mà vẫn giữ
    server chạy thì bấm **Switch user** (ĐỪNG **Sign out** — sign out sẽ tắt server). Cửa sổ log là
    `python.exe`: đừng đóng/Ctrl-C (sẽ tắt server); tắt sạch bằng `server-TAT-tudong.bat`. Đánh đổi:
    desktop tự mở khoá sau reboot. Muốn tắt autologon: mở lại Autologon → **Disable**.
- **Link đọc từ xa**: cloudflared quick-tunnel tự tạo link `…trycloudflare.com` và gửi qua
  **Telegram bot** cho ai đã nhắn bot. Link **đổi mỗi lần server/tunnel khởi động lại**.
  Trên server chạy `get-cloudflared.bat` một lần để tải cloudflared.
- **Chống loạn khi mạng/DNS server chập chờn** (từ 11/08): trước đây mạng server rớt là
  cloudflared quay vòng tạo link liên tục → **spam hàng loạt link** qua Telegram + **mất
  sạch hàng chờ tải**. Nay supervisor **kiểm tra mạng trước khi bật lại tunnel** (mất mạng thì
  nằm im chờ, có backoff), **chỉ báo link sau khi reader đã sẵn sàng** (mở link không dính 502), và
  **giữ nguyên hàng đợi khi lỗi do mạng** (tự thử lại thay vì xoá). Mất mạng thì reader vẫn
  không vào được trong lúc đó (không tránh khỏi), nhưng **hết loạn link + không mất truyện**.
  (Lưu ý kỹ thuật: đã **bỏ health-check kiểu tự-GET link công khai** — mạng server không "vòng
  về" chính tunnel của nó được nên hay báo nhầm tunnel chết → đổi link liên tục mỗi ~3 phút. Giờ
  tin cloudflared tự lo kết nối; đổi lại nếu **reader treo mà chưa chết hẳn** thì phải bật lại tay.)
- **Đồng bộ code bằng git** (repo GitHub `Baion91/comics`, Public — không chứa secret):
  - Máy dev: **`day-len.bat`** = đẩy code lên GitHub (git add + commit + push).
  - Server: **`cap-nhat.bat`** = kéo code mới + restart, HOẶC nhắn **`/update`** cho bot
    (chỉ restart reader, **giữ nguyên link**). Sửa `supervisor.py` thì phải dùng `cap-nhat.bat`.
- **Lệnh Telegram bot** (gõ **`/help`** để xem đủ; mỗi lệnh là **1 từ liền**):
  - `/link` link hiện tại · `/whoami` xem chat_id của bạn · `/help` danh sách lệnh.
  - **Admin**: `/tai <link>` tải truyện (xếp hàng đợi, báo bắt đầu/xong) · `/update` cập
    nhật code · `/adminclaim` (người đầu tiên → admin gốc) · `/adminlist` ·
    `/adminadd <id>` · `/adminremove <id>`.
  - **Huỷ tải** (admin): `/stop` dừng truyện đang tải **+ xoá hàng chờ của bạn** ·
    `/killnow` **chỉ** dừng truyện đang tải · `/clearq` **chỉ** xoá hàng chờ · `/stopall`
    dừng tất cả + xoá **sạch** hàng chờ (của mọi người). `/stop`/`/killnow`/`/clearq` chỉ
    đụng request **do chính bạn** gửi; dừng truyện của người kia thì dùng `/stopall`.
  - **Tự động check chương mới** (admin): `/watchlist` xem danh sách truyện đang theo dõi ·
    `/watch <link>` thêm truyện · `/unwatch <số|link>` bỏ · `/checknow [link]` kiểm tra
    NGAY (bỏ trống = cả danh sách; kèm link = 1 truyện).
- **`/tai` tải TUẦN TỰ, 1 hàng đợi CHUNG cho mọi admin**: `/tai` của **bất kỳ admin nào** đều
  đổ vào **cùng 1 hàng đợi**, chỉ **1 truyện tải mỗi lúc**, theo thứ tự **vào trước chạy trước**
  (không phân biệt ai gửi). Cố ý 1 luồng để **giữ nhịp chống chặn IP** (2 truyện song song =
  gấp đôi request). Chạy **ẩn** (không cửa sổ), báo "Tải xong" khi hoàn tất.
  ⚠️ Cũng đừng bấm `Tai hang loat.bat`/`Tai truyen.bat` tay lúc bot đang tải — 2 cái đó nằm
  ngoài hàng đợi bot nên chạy **song song** với bot, gấp đôi request → dễ bị chặn IP.
- **Huỷ xong tải lại vẫn an toàn**: chương đã tải xong được đánh dấu `.done`, nên lần sau
  `/tai` lại đúng link đó sẽ **tự bỏ qua chương cũ**, chỉ tải tiếp phần còn dở.
- **Tự động check chương mới hằng ngày** (mới): bot giữ **1 danh sách theo dõi** (watchlist,
  ở `.reader-meta\watchlist.json`). Mỗi ngày **1 lần** (mặc định **03:00 giờ server**, đổi
  bằng `"check_hour"`/`"check_min"` trong `notify-config.json`) bot **dò chương mới** cho từng
  truyện — chỉ gọi **metadata** (danh sách chương), **không tải ảnh**, nên rất nhẹ — rồi **báo
  tóm tắt** qua Telegram; truyện nào có chương mới thì **tự đổ vào hàng đợi tải** (đúng cơ chế
  `/tai`, tuần tự, chống trùng). Cách dò: so danh sách chương của site với **ảnh đã có trên
  đĩa** → xử đúng cả các ca **chương khoá premium** (chưa có ảnh → tự thử lại mỗi ngày tới khi
  mở khoá), **comix bản "v" tick thay scan** (comix được enqueue mỗi ngày để loop comix tự nâng
  cấp), **truyện thư viện cũ** (đã có ảnh nhưng chưa có `.done` vẫn tính là đã tải). **Báo cáo
  chi tiết**: mỗi truyện ghi rõ **`X/Y chương (thiếu K: ch. …)`** — ví dụ *"Solo Leveling —
  200/205 (thiếu 5: ch. 201–205)"*. Riêng **comix** không đếm nhanh được (phải mở Chromium), nên
  số chương của nó (X/Y + danh sách "cần nâng cấp → Official" + "cần tải") được **báo riêng ngay
  khi lượt tải mở Chromium quét xong**, trước khi tải ảnh. Quản lý
  bằng `/watch` / `/unwatch` / `/watchlist`, ép chạy ngay bằng `/checknow`. Server tắt đúng giờ
  hẹn thì **bật lại sẽ check bù** cho ngày đó. Site **chưa có provider** thì `/watch` báo "chưa
  hỗ trợ" và không nhận vào danh sách.
- **Sống qua restart server**: hàng đợi tải được **lưu ra đĩa** (`.reader-meta\bot-download-queue.json`),
  nên khi cập nhật code (`cap-nhat.bat`) hay bật lại server, **truyện đang tải dở + hàng chờ
  KHÔNG mất** — lên lại là bot tự tải tiếp (báo *"🔄 Đang tiếp tục"*), bỏ qua chương đã xong.
  Muốn xem tiến độ real-time: mở/tail file **`.reader-meta\tai-run.log`** (output downloader).
- Token bot để trong `.reader-meta\notify-config.json` (**không** commit lên git).
- **Báo khi SERVER SẬP (heartbeat — tùy chọn nhưng nên bật)**: khi server mất điện/mất
  mạng/treo thì **chính con bot cũng câm** (nó gửi tin qua đúng đường mạng đã hỏng) → bạn
  không hề hay biết. Cách vá: dùng dịch vụ giám sát NGOÀI. Server cứ 5 phút "ping" ra
  **[healthchecks.io](https://healthchecks.io)** (free); quá hạn không nghe ping, dịch vụ
  đó **tự báo bạn** (Email/Telegram) — báo được **cả khi server đã chết** vì nó chạy trên
  hạ tầng của họ. Cách bật: tạo 1 check (Simple, Period 5 phút / Grace ~20 phút), copy
  **Ping URL** dán vào `.reader-meta\notify-config.json` trường **`"heartbeat_url"`**, rồi
  `cap-nhat.bat`. Trống trường này = tắt heartbeat. Muốn báo về **chính Toony bot**: thêm
  một integration **Webhook** trên healthchecks trỏ tới `https://api.telegram.org/bot<TOKEN>/sendMessage`
  (POST, body JSON `{"chat_id":"<id>","text":"..."}`). ⚠️ `heartbeat_url` là **bí mật** như token — không commit.
- **Tải hàng loạt** (chạy tay): `Tai hang loat.bat` — dán nhiều link vào `download-queue.txt`
  rồi chạy lần lượt (bỏ qua chương đã đủ nhờ dấu `.done`). Tải xong nó báo **"Xong THẬT SỰ"**;
  nếu bị đứt/lỗi/crash giữa chừng thì báo **"CHƯA xong" rồi tự chạy lại để tải tiếp** (tối đa
  5 lần, chương đã xong tự bỏ qua); còn bị chặn IP thì dừng và nhắc chờ.

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
