#!/usr/bin/env python3
"""Adapter cho từng site truyện. ĐÂY LÀ NƠI DUY NHẤT sửa khi thêm site / đổi domain.

Mỗi provider phải cung cấp đúng "hợp đồng" sau (engine chỉ cần bấy nhiêu):

    name            : str            - tên ngắn, để in log và cho cờ --site
    domains         : list[str]      - các domain site phụ trách (khớp URL người dùng dán)
    referer         : str | None     - Referer gửi kèm nếu CDN đòi (None = không gửi)
    series_slug(url_or_text) -> str          - tách slug/id truyện từ URL
    title_from_slug(slug)    -> str          - tên hiển thị (đặt tên folder)
    list_chapters(slug)      -> [Chapter(number, title, ref), ...]
    chapter_images(chapter)  -> [url, ...]   - URL ảnh đúng thứ tự trang ([] nếu khóa)
    cover_url(slug)          -> str | None   - URL ảnh bìa

THÊM SITE MỚI: viết 1 class như dưới rồi thêm vào PROVIDERS. Không đụng comics_core.
ĐỔI DOMAIN  : thêm domain mới vào `domains` (giữ cả domain cũ). Nếu đổi cả host
              API/CDN thì sửa hằng BASE/API trong đúng provider đó.
"""

import json
import re

from comics_core import Chapter, get_json, get_text


class AsuraProvider:
    """Asura Scans - web app riêng, có REST API JSON (ảnh đặt tên hash -> buộc dùng API)."""

    name = "asura"
    API = "https://api.asurascans.com/api"
    domains = ["asurascans.com", "asuracomic.net", "api.asurascans.com"]
    referer = "https://asuracomic.net/"

    def series_slug(self, text: str) -> str:
        text = text.strip().rstrip("/")
        m = re.search(r"/(?:comics|series)/([^/?#]+)", text)
        return m.group(1) if m else text

    def title_from_slug(self, slug: str) -> str:
        # chỉ cắt cụm cuối nếu đúng 8 ký tự hex có chữ số (hash kiểu -1d35e5bd);
        # slug từ API search không có hash, cắt mù sẽ mất chữ cuối tên truyện.
        name = slug
        last = name.rsplit("-", 1)[-1]
        if (name != last and re.fullmatch(r"[0-9a-f]{8}", last)
                and any(ch.isdigit() for ch in last)):
            name = name.rsplit("-", 1)[0]
        return name.replace("-", " ").replace("_", " ").title()

    def list_chapters(self, slug: str):
        data = get_json(f"{self.API}/series/{slug}/chapters")
        if not data or "data" not in data:
            return []
        out = []
        for c in data["data"]:
            num = float(c["number"])
            # số nguyên bỏ đuôi .0 (330.0 -> 330) khi ghép vào URL API; lẻ giữ nguyên
            n = int(num) if num.is_integer() else c["number"]
            ref = f"{self.API}/series/{slug}/chapters/{n}"
            out.append(Chapter(num, c.get("title") or "", ref))
        return sorted(out, key=lambda ch: ch.number)

    def chapter_images(self, chapter):
        data = get_json(chapter.ref)
        try:
            pages = data["data"]["chapter"]["pages"]
        except (TypeError, KeyError):
            return []
        return [p["url"] for p in pages]

    def cover_url(self, slug: str):
        data = get_json(f"{self.API}/series/{slug}")
        try:
            return data["series"]["cover"]
        except (TypeError, KeyError):
            return None


class RavenProvider:
    """Raven Scans - WordPress + theme Themesia 'mangareader' (đã đổi .org -> .net và
    đổi cả cấu trúc URL chương, ~2025-06).

    Danh sách chương: link dạng /series/{slug}/chapter-{ID_nội_bộ}/ trong trang
    /series/{slug}/ — SỐ chương nằm trong TEXT thẻ <a> ("Chapter N"), KHÔNG ở URL.
    URL ảnh: khối `ts_reader.run({...})` nhúng trong HTML mỗi chương -> sources[0].images
    (URL ảnh đầy đủ, CDN cdn1.ravenscans.org trả .jpg, KHÔNG đòi Referer).
    """

    name = "raven"
    BASE = "https://ravenscans.net"
    domains = ["ravenscans.net", "ravenscans.org"]   # giữ .org cho link cũ
    referer = None

    def __init__(self):
        self._html_cache = {}  # đỡ tải lại trang series (list_chapters + cover dùng chung)

    def _series_html(self, slug: str) -> str:
        if slug not in self._html_cache:
            self._html_cache[slug] = get_text(f"{self.BASE}/series/{slug}/") or ""
        return self._html_cache[slug]

    def series_slug(self, text: str) -> str:
        text = text.strip().rstrip("/")
        m = re.search(r"/series/([^/?#]+)", text)
        if m:
            return m.group(1)
        # người dùng lỡ dán URL 1 chương -> lấy slug bằng cách bỏ đuôi -chapter-N
        m = re.search(r"/([a-z0-9-]+)-chapter-[\d.-]+/?$", text)
        if m:
            return m.group(1)
        return text

    def title_from_slug(self, slug: str) -> str:
        return slug.replace("-", " ").replace("_", " ").title()

    def list_chapters(self, slug: str):
        html = self._series_html(slug)
        # link chương: .../series/{slug}/chapter-{ID}/ ; số chương ở TEXT ("Chapter N")
        pat = re.compile(
            r'<a[^>]+href="([^"]*?/series/' + re.escape(slug) + r'/chapter-\d+/?)"[^>]*>(.*?)</a>',
            re.S | re.I)
        seen = {}  # số chương -> url (dedup, mỗi chương xuất hiện nhiều lần trong trang)
        for href, inner in pat.findall(html):
            txt = re.sub(r"<[^>]+>", " ", inner)                 # bỏ thẻ con, còn lại text
            m = re.search(r"chapter\s*(\d+(?:[.-]\d+)?)", txt, re.I)
            if not m:
                continue                                          # nút First/Last... -> bỏ
            try:
                num = float(m.group(1).replace("-", "."))         # 162-5 -> 162.5
            except ValueError:
                continue
            if not href.startswith("http"):
                href = self.BASE + href
            seen[num] = href
        return [Chapter(num, "", seen[num]) for num in sorted(seen)]

    def chapter_images(self, chapter):
        html = get_text(chapter.ref)
        if not html:
            return []
        m = re.search(r"ts_reader\.run\((\{.*?\})\);", html, re.S)
        if not m:
            return []
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            return []
        sources = data.get("sources") or []
        if not sources:
            return []
        return [u for u in sources[0].get("images", []) if u]

    def cover_url(self, slug: str):
        html = self._series_html(slug)
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        return m.group(1) if m else None


class DilibProvider:
    """dilib.vn (Thư Viện Số) - trang PHP thường, KHÔNG cần JS/API/Referer.

    Trang series `/{slug}.html` liệt kê link chương `/truyen-tranh/{slug}-chap-N.html`.
    HTML mỗi chương (tải thẳng bằng requests) đã nhúng SẴN đủ URL ảnh trong các thẻ
    <img src="/img/comic/{Folder}/img_NNNNN.webp?v=..."> theo đúng thứ tự trang — chỉ
    việc regex rồi ghép domain. Ảnh đánh số LIÊN TỤC toàn truyện (chap1=00000..00019,
    chap2=00020..), nhưng engine tự đánh lại 001,002,... theo vị trí trong list nên
    số toàn cục đó không ảnh hưởng gì. Ảnh KHÔNG đòi Referer (đã kiểm), giữ nguyên webp.
    """

    name = "dilib"
    BASE = "https://dilib.vn"
    domains = ["dilib.vn"]
    referer = None

    def __init__(self):
        self._html_cache = {}  # đỡ tải lại trang series (list_chapters + cover dùng chung)

    def _series_html(self, slug: str) -> str:
        if slug not in self._html_cache:
            self._html_cache[slug] = get_text(f"{self.BASE}/{slug}.html") or ""
        return self._html_cache[slug]

    def series_slug(self, text: str) -> str:
        text = re.split(r"[?#]", text.strip())[0].rstrip("/")  # bỏ query/fragment
        seg = text.rsplit("/", 1)[-1]                          # lấy đoạn cuối path
        seg = re.sub(r"\.html?$", "", seg, flags=re.I)         # bỏ đuôi .html
        # người dùng lỡ dán URL 1 chương -> cắt đuôi -chap-N để về slug truyện
        seg = re.sub(r"-chap-[\d.\-]+$", "", seg, flags=re.I)
        return seg

    def title_from_slug(self, slug: str) -> str:
        # slug luôn có đuôi id số (vd -16189) — bỏ đi trước khi làm tên hiển thị
        name = re.sub(r"-\d+$", "", slug)
        return name.replace("-", " ").replace("_", " ").title()

    def list_chapters(self, slug: str):
        html = self._series_html(slug)
        pat = re.compile(
            r"/truyen-tranh/" + re.escape(slug) + r"-chap-([0-9]+(?:[.\-][0-9]+)?)\.html")
        seen = {}  # number -> url (mỗi chương xuất hiện nhiều lần trong trang, dedup)
        for tail in pat.findall(html):
            try:
                num = float(tail.replace("-", "."))  # "10-5" -> 10.5
            except ValueError:
                continue
            seen[num] = f"{self.BASE}/truyen-tranh/{slug}-chap-{tail}.html"
        return [Chapter(num, "", seen[num]) for num in sorted(seen)]

    def chapter_images(self, chapter):
        html = get_text(chapter.ref)
        if not html:
            return []
        seen, out = set(), []   # giữ nguyên thứ tự xuất hiện, bỏ trùng
        for u in re.findall(r'src="(/img/comic/[^"]+)"', html):
            if u not in seen:
                seen.add(u)
                out.append(self.BASE + u)
        return out

    def cover_url(self, slug: str):
        html = self._series_html(slug)
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if not m:
            return None
        u = m.group(1)
        return u if u.startswith("http") else self.BASE + u


class MangaDexProvider:
    """MangaDex - API JSON công khai (api.mangadex.org), KHÔNG scrape HTML.

    Slug = UUID truyện trong URL /title/{uuid}/{tên}. Danh sách chương lấy từ
    /manga/{uuid}/feed (lọc translatedLanguage=en, phân trang limit 500). Nhiều nhóm
    dịch có thể up cùng 1 số chương -> DEDUP theo (volume, chương), và vì sắp
    order[readableAt]=desc nên bản GIỮ LẠI là bản UPLOAD MỚI NHẤT (khớp hành vi mặc
    định của tool `mangadex-downloader`: tránh vớ nhầm bản scan cũ). Ảnh qua server
    @Home động: /at-home/server/{chapterId} trả baseUrl + hash + list file -> ghép
    {baseUrl}/data/{hash}/{file} (bản full nét; đuôi .png/.jpg -> engine đặt tên đúng).
    CDN @Home ĐÒI Referer mangadex.org. Bìa: relationship cover_art -> uploads.mangadex.org.

    Đối chiếu logic tool mansuf/mangadex-downloader v3 (chapter.py): dedup key
    `f"{volume}:{chapter}"`, order[volume/chapter]=asc + order[readableAt]=desc,
    contentRating[] đủ 4 mức (mặc định API loại 'pornographic' -> manga 18+ ra rỗng
    nếu không xin rõ), chương oneshot (chapter=null) vẫn giữ.
    """

    name = "mangadex"
    API = "https://api.mangadex.org"
    UPLOADS = "https://uploads.mangadex.org"
    LANG = "en"                       # chỉ lấy bản dịch tiếng Anh
    domains = ["mangadex.org"]
    # CDN @Home đòi Referer mangadex.org: ảnh NGUỘI (chưa cache Cloudflare) mà thiếu
    # header này trả 404. Đặt ở đây -> core.run gắn vào session cho mọi request.
    referer = "https://mangadex.org/"

    def series_slug(self, text: str) -> str:
        text = text.strip()
        # URL chuẩn: https://mangadex.org/title/{uuid}/{slug}?tab=...
        m = re.search(r"/title/([0-9a-fA-F-]{36})", text)
        if m:
            return m.group(1).lower()
        # người dùng lỡ dán thẳng UUID trần
        m = re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text)
        return m.group(0).lower() if m else text

    def title_from_slug(self, slug: str) -> str:
        data = get_json(f"{self.API}/manga/{slug}")
        try:
            t = data["data"]["attributes"]["title"]
        except (TypeError, KeyError):
            return slug
        # ưu tiên 'en'; nhiều truyện chỉ có 'ja-ro'/'ja' -> lấy giá trị đầu tiên
        return t.get("en") or next(iter(t.values()), slug)

    def list_chapters(self, slug: str):
        # key = "{volume}:{chương}"; bản GẶP ĐẦU của mỗi key được giữ, và vì feed sắp
        # order[readableAt]=desc nên "đầu" = bản upload MỚI NHẤT (newest-wins). Dedup
        # kèm volume để không gộp nhầm 2 chương cùng số ở 2 volume khác nhau.
        seen = {}
        offset, total = 0, None
        while total is None or offset < total:
            url = (
                f"{self.API}/manga/{slug}/feed"
                f"?translatedLanguage[]={self.LANG}"
                "&contentRating[]=safe&contentRating[]=suggestive"
                "&contentRating[]=erotica&contentRating[]=pornographic"
                "&order[volume]=asc&order[chapter]=asc&order[readableAt]=desc"
                f"&limit=500&offset={offset}")
            data = get_json(url)
            if not data or "data" not in data:
                break
            total = data.get("total", 0)
            for c in data["data"]:
                at = c["attributes"]
                key = f"{at.get('volume')}:{at.get('chapter')}"
                if key in seen:
                    continue          # bản cũ hơn của đúng chương này -> bỏ
                raw = at.get("chapter")
                try:
                    # oneshot/chương không số -> gán 0.0 (engine đặt tên theo số) thay
                    # vì loại bỏ; nhãn chương phi-số hiếm gặp thì mới bỏ.
                    num = 0.0 if raw is None else float(raw)
                except (TypeError, ValueError):
                    continue
                seen[key] = Chapter(num, at.get("title") or "", c["id"])
            offset += 500
        return sorted(seen.values(), key=lambda ch: ch.number)

    def chapter_images(self, chapter):
        data = get_json(f"{self.API}/at-home/server/{chapter.ref}")
        try:
            base = data["baseUrl"]
            h = data["chapter"]["hash"]
            files = data["chapter"]["data"]
        except (TypeError, KeyError):
            return []
        return [f"{base}/data/{h}/{f}" for f in files]

    def cover_url(self, slug: str):
        data = get_json(f"{self.API}/manga/{slug}?includes[]=cover_art")
        try:
            rels = data["data"]["relationships"]
        except (TypeError, KeyError):
            return None
        for rel in rels:
            if rel.get("type") == "cover_art":
                fn = (rel.get("attributes") or {}).get("fileName")
                if fn:
                    return f"{self.UPLOADS}/covers/{slug}/{fn}"
        return None


# --- Đăng ký: thêm site mới = thêm 1 dòng vào đây -------------------------------
PROVIDERS = [AsuraProvider(), RavenProvider(), DilibProvider(), MangaDexProvider()]

by_name = {p.name: p for p in PROVIDERS}                 # tra theo cờ --site
REGISTRY = {d: p for p in PROVIDERS for d in p.domains}  # tra theo domain của URL
