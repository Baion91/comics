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

TÙY CHỌN (site ảnh KHÔNG có URL tải thẳng, vd moetruyen): render_pages(chapter, jobs) —
generator; core.run gọi ở main thread thay cho pool HTTP, jobs = [(url, đích)] các trang
còn thiếu; yield 1 bool mỗi job, CHỈ ghi file khi ảnh đạt kiểm tra.

THÊM SITE MỚI: viết 1 class như dưới rồi thêm vào PROVIDERS. Không đụng comics_core.
ĐỔI DOMAIN  : thêm domain mới vào `domains` (giữ cả domain cũ). Nếu đổi cả host
              API/CDN thì sửa hằng BASE/API trong đúng provider đó.
"""

import hashlib
import html as html_lib
import io
import json
import os
import random
import re
import sys
import time
from urllib.parse import parse_qs, urlparse

from comics_core import (META_DIR, Blocked, Challenged, Chapter, check_image_bytes, clear_bad,
                         fmt_num, get_json, get_text, uniform_frame)

# File override domain/base/referer do người dùng thêm qua bot (KHÔNG cần sửa code +
# push khi site xoay tên miền — vd TruyenQQ). Nằm trong .reader-meta/ (gitignore) nên
# git reset --hard của cap-nhat.bat không đụng. provider_admin.py là NGƯỜI GHI; ở đây
# chỉ ĐỌC lúc import -> mọi tiến trình con (downloader, check_updates) tự áp bản mới.
OVERRIDE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             ".reader-meta", "provider-domains.json")


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
                # Loại bản external (link bản quyền, ảnh KHÔNG ở MangaDex) và bản 0 trang
                # NGAY TỪ ĐẦU, trước dedup: nếu để vào, bản external (thường mới hơn -> gặp
                # trước do readableAt desc) sẽ GIÀNH slot dedup rồi bị bỏ vì rỗng, khiến bản
                # THẬT cũ hơn bị coi là trùng và mất luôn (sự cố Tondemo Skill ch1). Bỏ trước
                # -> newest-wins chỉ xét các bản CÓ ảnh, bản thật giữ được slot.
                if at.get("externalUrl") or not at.get("pages"):
                    continue
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


class TruyenQQProvider:
    """TruyenQQ - trang PHP tĩnh (HTML đủ, KHÔNG cần JS/API).

    Trang series `/truyen-tranh/{slug}` liệt kê link chương
    `/truyen-tranh/{slug}-chap-N` (số chương ở URL). HTML mỗi chương nhúng SẴN đủ URL
    ảnh trong `<img class="lazy" ... data-original="https://iNNN.truyenvua.com/.../N.jpg">`
    theo đúng thứ tự trang — chỉ việc regex `data-original`.

    ⚠️ CDN ảnh (truyenvua.com / hinhtruyen.com) CHỐNG HOTLINK: thiếu Referer trả 403,
    có `Referer: {BASE}/` trả 200 (đã kiểm). Host CDN là shard động (i216..., đổi theo
    truyện) nên KHÔNG hard-code — lấy nguyên URL từ data-original. Token `?r=...` trên
    URL ảnh KHÔNG bắt buộc, giữ nguyên cho tiện.

    ⚠️ Site ĐỔI DOMAIN thường xuyên (truyenqq.com/vn/to/ko...). Khi đổi: thêm domain mới
    vào `domains`, đổi BASE + referer sang domain mới (CDN đòi Referer = domain HIỆN HÀNH).

    Tên folder: slug là ASCII không dấu (hiep-si-giay-6555) nên lấy tên CÓ DẤU từ
    `<h1 itemprop="name">` của trang series thay vì title-case slug.
    """

    name = "truyenqq"
    BASE = "https://truyenqqko.com"
    # giữ các domain cũ để link cũ vẫn khớp REGISTRY (site hay đổi tên miền).
    # KHÔNG có truyenqq.com.vn: đó là site KHÁC (code/CDN/đánh số riêng) -> TruyenQQVNProvider.
    domains = ["truyenqqko.com", "truyenqqto.com", "truyenqqvn.com"]
    referer = "https://truyenqqko.com/"

    def __init__(self):
        self._html_cache = {}  # đỡ tải lại trang series (list_chapters + title + cover)

    def _series_html(self, slug: str) -> str:
        if slug not in self._html_cache:
            self._html_cache[slug] = get_text(f"{self.BASE}/truyen-tranh/{slug}") or ""
        return self._html_cache[slug]

    def series_slug(self, text: str) -> str:
        text = re.split(r"[?#]", text.strip())[0].rstrip("/")  # bỏ query/fragment
        seg = text.rsplit("/", 1)[-1]                          # lấy đoạn cuối path
        # người dùng lỡ dán URL 1 chương -> cắt đuôi -chap-N để về slug truyện
        seg = re.sub(r"-chap-[\d.\-]+$", "", seg, flags=re.I)
        return seg

    def title_from_slug(self, slug: str) -> str:
        html = self._series_html(slug)
        m = re.search(r'<h1[^>]*itemprop="name"[^>]*>([^<]+)</h1>', html, re.I)
        if m:
            return m.group(1).strip()
        # dự phòng: bỏ đuôi id số (-6555) rồi làm tên hiển thị từ slug
        name = re.sub(r"-\d+$", "", slug)
        return name.replace("-", " ").replace("_", " ").title()

    def list_chapters(self, slug: str):
        html = self._series_html(slug)
        pat = re.compile(
            r"/truyen-tranh/" + re.escape(slug) + r"-chap-([0-9]+(?:[.\-][0-9]+)?)\b",
            re.I)
        seen = {}  # number -> url (mỗi chương xuất hiện nhiều lần trong trang, dedup)
        for tail in pat.findall(html):
            try:
                num = float(tail.replace("-", "."))  # "10-5" -> 10.5
            except ValueError:
                continue
            seen[num] = f"{self.BASE}/truyen-tranh/{slug}-chap-{tail}"
        return [Chapter(num, "", seen[num]) for num in sorted(seen)]

    def chapter_images(self, chapter):
        html = get_text(chapter.ref)
        if not html:
            return []
        seen, out = set(), []   # giữ nguyên thứ tự xuất hiện, bỏ trùng
        for u in re.findall(r'data-original="(https?://[^"]+)"', html):
            low = u.split("?", 1)[0].lower()
            if not low.endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue          # bỏ avatar/icon lỡ có data-original
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def cover_url(self, slug: str):
        html = self._series_html(slug)
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if not m:
            return None
        u = m.group(1)
        return u if u.startswith("http") else self.BASE + u


class ACGNProvider:
    """comic.acgn.cc (動漫戲說/ACGN.cc) - truyện tiếng Trung phồn thể, HTML TĨNH.

    KHÔNG cần JS/API/Playwright: URL ảnh nhúng SẴN trong trang đọc. Hai loại trang:
      - Series : /manhua-{slug}.htm   (vd manhua-zzzs.htm) — tên + bìa + danh sách tập
      - Tập/ch : /view-{id}.htm        (vd view-11338.htm)  — trang đọc, nhúng ảnh

    Danh sách chương ở trang series: `<a href="view-{id}.htm" ...>VOL22</a>` — SỐ chương
    nằm trong TEXT thẻ <a> (giống Raven: VOL/第N話/第N集), view-id chỉ là "chìa" (ref).
    Ảnh mỗi tập: `<div id="pN" class="pic" _src="https://img.acgn.cc/img/{grp}/{id}/{n}.jpg">`
    — regex `_src` theo đúng thứ tự trang (đã kiểm: sạch, không lẫn div quảng cáo .img1).

    Người dùng hay dán URL 1 TẬP (/view-{id}.htm) chứ không phải series → series_slug tự
    tải trang tập đó, lấy link breadcrumb /manhua-{slug}.htm để về slug truyện (1 request).

    CDN ảnh img.acgn.cc: đã kiểm trên server VN -> 200, và KHÔNG đòi Referer (có/không đều
    trả cùng ảnh) nên referer=None. LƯU Ý: origin img.acgn.cc lọc theo vùng — nhiều nơi
    (vd DC ngoài VN) bị Cloudflare 522; server VN tải bình thường. Chương chưa có ảnh (mới
    tạo trang rỗng) -> _src rỗng -> skip như chương khóa.

    Tên hiển thị = tiếng Trung lấy từ <h1> (giữ nguyên chữ Hán theo ý user; safe_name của
    engine giữ CJK, chỉ bỏ ký tự cấm Windows). Chương KHÔNG rút được số (番外/特別篇...) bị
    bỏ qua như nút điều hướng — hiếm gặp.
    """

    name = "acgn"
    BASE = "https://comic.acgn.cc"
    domains = ["comic.acgn.cc"]
    referer = None   # đã kiểm: CDN ảnh KHÔNG đòi Referer

    def __init__(self):
        self._html_cache = {}  # đỡ tải lại trang series (list_chapters + title + cover)

    def _series_html(self, slug: str) -> str:
        if slug not in self._html_cache:
            self._html_cache[slug] = get_text(f"{self.BASE}/manhua-{slug}.htm") or ""
        return self._html_cache[slug]

    def series_slug(self, text: str) -> str:
        text = text.strip()
        base = re.split(r"[?#]", text)[0].rstrip("/")
        m = re.search(r"/manhua-([^/.]+)\.html?", base, re.I)
        if m:
            return m.group(1)
        # dán URL 1 tập /view-{id}.htm -> tải trang đó, lấy slug từ breadcrumb manhua-
        m = re.search(r"/view-\d+\.html?", base, re.I)
        if m:
            url = base if base.startswith("http") else self.BASE + m.group(0)
            html = get_text(url) or ""
            mm = re.search(r"/manhua-([^/.]+)\.html?", html, re.I)
            if mm:
                return mm.group(1)
        # dự phòng: đoạn cuối path, bỏ tiền tố manhua-/đuôi .htm
        seg = base.rsplit("/", 1)[-1]
        return re.sub(r"\.html?$", "", re.sub(r"^manhua-", "", seg, flags=re.I), flags=re.I)

    def title_from_slug(self, slug: str) -> str:
        html = self._series_html(slug)
        m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
        if m:
            return m.group(1).strip()
        return slug

    def list_chapters(self, slug: str):
        html = self._series_html(slug)
        # bó về khối danh sách chương cho chắc (trang chỉ liệt kê view- của CHÍNH bộ này,
        # nhưng cắt từ #comic_chapter tránh dính widget khác nếu site đổi layout)
        i = html.find("comic_chapter")
        area = html[i:] if i != -1 else html
        pat = re.compile(
            r'href="([^"]*view-\d+\.html?)"[^>]*>\s*([^<]+?)\s*</a>', re.I)
        seen = {}  # số chương -> url (mỗi tập có thể xuất hiện nhiều lần, dedup giữ đầu)
        for href, txt in pat.findall(area):
            m = re.search(r"(\d+(?:\.\d+)?)", txt)
            if not m:
                continue                       # 番外/nút điều hướng không số -> bỏ
            try:
                num = float(m.group(1))
            except ValueError:
                continue
            if num in seen:
                continue
            if not href.startswith("http"):
                href = f"{self.BASE}/{href.lstrip('/')}"
            seen[num] = href
        return [Chapter(num, "", seen[num]) for num in sorted(seen)]

    def chapter_images(self, chapter):
        html = get_text(chapter.ref)
        if not html:
            return []
        seen, out = set(), []   # giữ nguyên thứ tự xuất hiện, bỏ trùng
        for u in re.findall(r'_src=["\'](https?://img\.acgn\.cc/[^"\']+)["\']', html):
            low = u.split("?", 1)[0].lower()
            if not low.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                continue
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def cover_url(self, slug: str):
        html = self._series_html(slug)
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if not m:
            return None
        u = m.group(1)
        return u if u.startswith("http") else self.BASE + u


class NetTruyenProvider:
    """nettruyen.id - trang React/Next.js SSR, HTML render SẴN (KHÔNG cần JS/API).

    Khác TruyenQQ ở CHỖ chương là SUB-PATH: trang series `/truyen-tranh/{slug}` liệt kê
    link chương `/truyen-tranh/{slug}/chuong-N` (số chương ở đoạn cuối path, KHÔNG dính
    slug). Danh sách chương nhúng đủ trong 1 trang (không phân trang/AJAX). HTML mỗi
    chương nhúng SẴN đủ URL ảnh trong `<img class="lozad" data-src="https://images.
    truyenonline.cc/.../chapter_N/page_M.jpg">` theo đúng thứ tự trang.

    ⚠️ Trang là Next.js: link chương xuất hiện cả trong HTML render SẴN LẪN trong blob
    JSON `__NEXT_DATA__` (quote bị escape: `chuong-255\\"`). Regex số chương dùng lớp
    ký tự SỐ thuần `[0-9]` (không nuốt dấu `\\`) nên cả hai chỗ đều ra đúng số.

    CDN ảnh `images.truyenonline.cc`: đã kiểm KHÔNG chống hotlink (có/không Referer đều
    trả 200) → referer=None. Bó vùng lấy ảnh về khối `reading-detail` + lọc đuôi ảnh
    (host-agnostic: bộ nào đổi CDN vẫn chạy, không dính thumbnail/ads lỡ có sau này).

    Tên hiển thị = tên CÓ DẤU từ `<h1 class="title-detail">` (slug là ASCII không dấu).
    Cloudflare có mặt (Server: cloudflare) nhưng hiện KHÔNG challenge GET thường → dùng
    `core.session` trần như Raven/TruyenQQ; siết thì thêm curl_cffi sau như comix.
    Site họ nettruyen hay đổi domain — chỉ nhận `nettruyen.id` (clone khác backend/CDN
    KHÁC nhau, phải kiểm riêng trước khi thêm vào `domains`).
    """

    name = "nettruyen"
    BASE = "https://nettruyen.id"
    domains = ["nettruyen.id"]
    referer = None   # đã kiểm: CDN images.truyenonline.cc KHÔNG đòi Referer

    def __init__(self):
        self._html_cache = {}  # đỡ tải lại trang series (list_chapters + title + cover)

    def _series_html(self, slug: str) -> str:
        if slug not in self._html_cache:
            self._html_cache[slug] = get_text(f"{self.BASE}/truyen-tranh/{slug}") or ""
        return self._html_cache[slug]

    def series_slug(self, text: str) -> str:
        text = re.split(r"[?#]", text.strip())[0].rstrip("/")  # bỏ query/fragment
        m = re.search(r"/truyen-tranh/([^/]+)", text)
        return m.group(1) if m else text.rsplit("/", 1)[-1]

    def title_from_slug(self, slug: str) -> str:
        html = self._series_html(slug)
        m = re.search(r'<h1[^>]*class="title-detail"[^>]*>([^<]+)</h1>', html, re.I)
        if m:
            return m.group(1).strip()
        # dự phòng: bỏ đuôi id số nếu có rồi làm tên hiển thị từ slug
        name = re.sub(r"-\d+$", "", slug)
        return name.replace("-", " ").replace("_", " ").title()

    def list_chapters(self, slug: str):
        html = self._series_html(slug)
        # /truyen-tranh/{slug}/chuong-N ; số chương ở path (lẻ .5 dạng chuong-6-5)
        pat = re.compile(
            r"/truyen-tranh/" + re.escape(slug) + r"/chuong-([0-9]+(?:[.\-][0-9]+)?)")
        seen = {}  # number -> url (mỗi chương xuất hiện nhiều lần trong trang, dedup)
        for tail in pat.findall(html):
            try:
                num = float(tail.replace("-", "."))  # "6-5" -> 6.5
            except ValueError:
                continue
            seen[num] = f"{self.BASE}/truyen-tranh/{slug}/chuong-{tail}"
        return [Chapter(num, "", seen[num]) for num in sorted(seen)]

    def chapter_images(self, chapter):
        html = get_text(chapter.ref)
        if not html:
            return []
        i = html.find("reading-detail")   # bó về khối ảnh, tránh thumbnail/ads ngoài
        area = html[i:] if i != -1 else html
        seen, out = set(), []   # giữ nguyên thứ tự xuất hiện, bỏ trùng
        for u in re.findall(r'data-src="(https?://[^"]+)"', area):
            low = u.split("?", 1)[0].lower()
            if not low.endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue          # bỏ avatar/icon lỡ có data-src
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def cover_url(self, slug: str):
        html = self._series_html(slug)
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if not m:
            return None
        u = m.group(1)
        return u if u.startswith("http") else self.BASE + u


class ZetTruyenProvider:
    """zettruyen1.com (ZetTruyen) - danh sách chương qua API JSON, ảnh nhúng SẴN trong
    HTML trang đọc (SSR). Cloudflare có mặt nhưng KHÔNG challenge GET thường (như NetTruyen).

    Danh sách chương KHÔNG nằm trong HTML trang series (chỉ có nút First/Latest) — trang
    dùng `window.comicData.apiUrl` gọi AJAX. Endpoint JSON PHÂN TRANG:
        GET /api/comics/{slug}/chapters?per_page=100&page=N
        -> {"success":true,"data":{"chapters":[{chapter_num, chapter_slug, ...}],
                                    "total","current_page","per_page","last_page"}}
    per_page tối đa ~100 (500 -> 404). Lặp tới `last_page` gom hết. `chapter_num` là int cho
    chương nguyên, float cho chương lẻ; `chapter_slug` = "chapter-391" | "chapter-331-2".

    ⚠️ URL trang đọc chương LẺ dùng DẤU CHẤM: chương 331.2 -> /chuong-331.2 (ĐÚNG 8 ảnh);
    /chuong-331-2 lại rơi về chương 331 nguyên (SAI). Nên số cho URL = đuôi chapter_slug
    đổi '-' -> '.': "chapter-331-2" -> "331.2"; "chapter-391" -> "391".

    Ảnh mỗi chương: HTML trang đọc nhúng SẴN trong `<div class="chapter-images-container">`
    các thẻ `<img src='https://cdnN.zetimage.com/{slug}/{num}/{page}.jpg' ... onerror=...>`
    theo đúng thứ tự trang. ⚠️ HOST CDN ĐỔI THEO CHƯƠNG (thấy cdn1/cdn3/cdn4) -> lấy ảnh
    HOST-AGNOSTIC (khớp *.zetimage.com), KHÔNG hard-code host. Mỗi ảnh xuất hiện 2 lần
    (src + onerror cùng URL) -> dedup giữ thứ tự.

    ⚠️ Đuôi URL là .jpg nhưng BYTES thật là WebP/PNG (đổi theo chương/CDN), content-type
    image/jpeg. Engine đặt tên file theo đuôi URL (001.jpg) nhưng kiểm ảnh dựa NỘI DUNG
    (magic bytes + Pillow) nên vẫn "ok"; reader trả image/jpeg còn trình duyệt render theo
    content-sniffing. Không đụng core, chấp nhận lệch đuôi (cosmetic).

    ⚠️ CDN cdn*.zetimage.com CHỐNG HOTLINK: thiếu Referer -> 403; có Referer đúng DOMAIN site
    (www/non-www đều được) -> 200. `run()` gắn `referer` vào session TRƯỚC khi tải ảnh/bìa.
    (Danh sách chương qua API KHÔNG cần Referer -> check_updates.py peek được bình thường.)

    ⚠️ Site có số trong domain (zettruyen1) -> nhiều khả năng đổi như TruyenQQ. Khi đổi:
    thêm domain mới vào `domains`, đổi BASE + referer sang domain HIỆN HÀNH (CDN kiểm referer
    theo domain đó). Tên hiển thị có dấu từ `<h1 class="comic-title-content">`.
    """

    name = "zettruyen"
    BASE = "https://www.zettruyen1.com"
    API = "https://www.zettruyen1.com/api/comics"
    domains = ["zettruyen1.com"]              # resolver đã cắt "www." — chỉ cần domain trần
    referer = "https://www.zettruyen1.com/"   # CDN đòi hotlink; ĐỔI theo BASE khi rotate domain

    def __init__(self):
        self._html_cache = {}  # đỡ tải lại trang series (title + cover dùng chung)

    def _series_html(self, slug: str) -> str:
        if slug not in self._html_cache:
            self._html_cache[slug] = get_text(f"{self.BASE}/truyen-tranh/{slug}") or ""
        return self._html_cache[slug]

    def series_slug(self, text: str) -> str:
        text = re.split(r"[?#]", text.strip())[0].rstrip("/")  # bỏ query/fragment
        m = re.search(r"/truyen-tranh/([^/]+)", text)          # segment đầu (loại /chuong-N)
        return m.group(1) if m else text.rsplit("/", 1)[-1]

    def title_from_slug(self, slug: str) -> str:
        html = self._series_html(slug)
        m = re.search(r'<h1[^>]*class="comic-title-content"[^>]*>([^<]+)</h1>', html, re.I)
        if m:
            return m.group(1).strip()
        # dự phòng: bỏ đuôi id số nếu có rồi làm tên hiển thị từ slug
        name = re.sub(r"-\d+$", "", slug)
        return name.replace("-", " ").replace("_", " ").title()

    def list_chapters(self, slug: str):
        seen = {}  # number -> Chapter (dedup theo số chương)
        page, last = 1, 1
        while page <= last:
            data = get_json(f"{self.API}/{slug}/chapters?per_page=100&page={page}")
            if not data or not data.get("success"):
                break
            d = data.get("data") or {}
            last = d.get("last_page", page) or page
            for c in d.get("chapters") or []:
                # đuôi chapter_slug đổi '-' -> '.' = số dùng cho URL trang đọc (331-2 -> 331.2)
                tail = str(c.get("chapter_slug") or "").removeprefix("chapter-")
                if not tail:                       # dự phòng khi thiếu slug
                    tail = str(c.get("chapter_num", ""))
                numstr = tail.replace("-", ".")
                try:
                    num = float(numstr)
                except ValueError:
                    continue                       # nhãn phi-số hiếm gặp -> bỏ
                ref = f"{self.BASE}/truyen-tranh/{slug}/chuong-{numstr}"
                seen[num] = Chapter(num, "", ref)
            page += 1
        return [seen[n] for n in sorted(seen)]

    def chapter_images(self, chapter):
        html = get_text(chapter.ref)
        if not html:
            return []
        i = html.find("chapter-images-container")  # bó về khối ảnh, tránh thumbnail/ads ngoài
        area = html[i:] if i != -1 else html
        seen, out = set(), []   # giữ nguyên thứ tự xuất hiện, bỏ trùng (onerror lặp mỗi URL)
        for u in re.findall(r"src=['\"](https?://[^'\"]*zetimage\.com/[^'\"]+)['\"]", area):
            low = u.split("?", 1)[0].lower()
            if "/thumb/" in low:
                continue          # bỏ bìa truyện gợi ý (cdn*.zetimage.com/thumb/{slug}.jpg)
            if not low.endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            if not re.search(r"/[0-9.]+/\d+\.[a-z]+$", low):
                continue          # đòi đúng dạng /{num}/{page}.ext -> loại banner/logo lỡ có
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out

    def cover_url(self, slug: str):
        html = self._series_html(slug)
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if not m:
            return None
        u = m.group(1)
        return u if u.startswith("http") else self.BASE + u


class TruyenQQVNProvider:
    """truyenqq.com.vn — site RIÊNG, KHÁC họ truyenqqko/to/go/vn.com dù trùng tên (code
    khác: URL gốc `/{slug}` + `/{slug}/chapter-N`; CDN ảnh riêng `sNN.cc3t.net`). Ảnh NÉT
    hơn họ ko: rộng ~1000 vs 900px, nén nhẹ hơn, cắt trang khác (đo 27/09/2026).

    ⚠️ SỐ CHƯƠNG = SỐ THỨ TỰ CỦA SITE, không phải số chương thật: site đánh 1..N (có bộ
    0..N) liên tục, không có chương lẻ, chèn cả chương extra -> lệch số thật TĂNG DẦN (Tinh
    Giáp: +1 đầu bộ -> +15 cuối bộ). Site KHÔNG lộ số thật ở đâu cả. Vì vậy:
      - folder LUÔN có hậu tố SUFFIX (" [QQ.vn]") -> không bao giờ trộn với folder cùng tên
        của nguồn đánh số thật (ZetTruyen/TruyenQQ...) — trộn = hỏng thư viện âm thầm;
      - `positional_numbers = True` -> comic_downloader CHẶN ghép (into:/--dest-name).

    ⚠️ CLOUDFLARE CHẬP CHỜN (đo: 12/09 trang series 403-challenge, 27/09 429-challenge,
    28/09 mở; trang chương thì mở cả 3 lần). Nên:
      - KHÔNG BAO GIỜ gọi trang series: mọi thứ lấy từ 1 "trang chương mốc" — dropdown
        `<option value="/{slug}/chapter-N">` có ĐỦ danh sách chương, kèm og:title (tên
        truyện) + JSON `recently_viewed` (file bìa ở /media/book/);
      - THANG LEO 2 tầng trong `_fetch`: HTTP thường (core.get_text) -> bị challenge
        (core.Challenged) thì chuyển sang Chromium thật (cf_browser, import lười) cho phần
        còn lại của phiên. `fetch_mode` (cờ --fetch auto|http|browser) ép tầng;
        `allow_browser=False` (check_updates đặt) -> không mở Chromium, ném Challenged.
      - Ảnh LUÔN tải bằng HTTP (core, đa luồng): CDN cc3t.net không challenge, chỉ đòi
        `Referer: {BASE}/` (thiếu -> 403). Host CDN đổi theo truyện (s34, s25...) -> lấy
        nguyên URL.

    Đổi domain: /provider (thêm domain + set base/referer) — không sửa code."""

    name = "qqcomvn"
    BASE = "https://truyenqq.com.vn"
    domains = ["truyenqq.com.vn"]
    referer = "https://truyenqq.com.vn/"
    positional_numbers = True
    SUFFIX = " [QQ.vn]"
    PROFILE = "qqvn-profile"        # profile Chromium riêng trong .reader-meta
    LABEL = "TruyenQQ.com.vn"
    LAYOUT_FAIL_LIMIT = 3           # số chương LIỀN không nhận ra cấu trúc -> dừng phiên

    _CH_TAIL = re.compile(r"\s*[-:–]\s*Chapter\s+\d+(?:\.\d+)?\s*$", re.I)
    _IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")

    def __init__(self):
        self.fetch_mode = "auto"    # auto | http | browser  (comic_downloader --fetch)
        self.allow_browser = True   # check_updates tắt: dò chương không mở Chromium
        self._escalated = False     # đã leo lên trình duyệt trong tiến trình này
        self._browser = None
        self._hint = {}             # slug -> URL chương người dùng dán (mốc dự phòng)
        self._anchor = {}           # slug -> (url, html) trang chương mốc (cả khi hụt)
        self._layout_fail = 0

    # -- tải HTML: HTTP -> (challenge) -> Chromium ----------------------------------

    def _fetch(self, url):
        """HTML 1 trang hoặc None (404/mạng hỏng sau retry). Đã leo lên trình duyệt thì
        giữ tới hết tiến trình (khỏi dội Cloudflare bằng request chắc chắn bị chặn)."""
        if self.fetch_mode != "browser" and not self._escalated:
            try:
                page = get_text(url)
                if page is None or not re.search(
                        r"<title>\s*(?:just a moment|attention required)", page[:4000], re.I):
                    return page
                raise Challenged(f"Cloudflare trả trang xác minh tại {url}")
            except Challenged as e:
                if self.fetch_mode == "http" or not self.allow_browser:
                    raise
                print(f"\n  ! {e}\n  -> Chuyển sang TRÌNH DUYỆT THẬT (Chromium) cho phần còn "
                      "lại của phiên...", flush=True)
                self._escalated = True
        return self._get_browser().get_html(url)

    def _get_browser(self):
        if self._browser is None:
            import cf_browser    # lười: Playwright chỉ nạp khi thật sự bị chặn / ép --fetch
            host = urlparse(self.BASE).hostname or "truyenqq.com.vn"
            b = cf_browser.CFBrowser(self.PROFILE, host, self.LABEL)
            b.open()
            self._browser = b
        return self._browser

    def close(self):
        """comic_downloader gọi trong finally -> không để Chromium mồ côi ôm profile."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None

    # -- trang chương mốc -----------------------------------------------------------

    def _chapter_nums(self, slug, page):
        """Số chương từ dropdown `<option value>` (đủ cả bộ) + link thường (dự phòng);
        chấp nhận cả URL tuyệt đối lẫn tương đối để bền khi site đổi cách ghi."""
        pat = (r'(?:value|href)="(?:https?://[^/"]+)?/' + re.escape(slug)
               + r'/chapter-(\d+)/?"')
        return sorted({int(n) for n in re.findall(pat, page or "", re.I)})

    def _debug_dump(self, name, page):
        """Lưu HTML trang không đọc được -> sửa parser nhanh khi site đổi giao diện."""
        try:
            d = META_DIR / "qqvn-debug"
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{name}.html"
            p.write_text(page or "", encoding="utf-8")
            return p
        except OSError:
            return None

    def _anchor_page(self, slug):
        """(url, html) của trang chương có danh sách chương; ('', '') nếu không lấy được.
        Nhớ cả kết quả hụt -> title/list/cover không thử lại 3 lần. chapter-1 đứng đầu
        (luôn có JSON bìa), rồi link người dùng dán, rồi chapter-0 (bộ đánh số từ 0)."""
        if slug in self._anchor:
            return self._anchor[slug]
        tried, got = [], ("", "")
        for url in (f"{self.BASE}/{slug}/chapter-1", self._hint.get(slug),
                    f"{self.BASE}/{slug}/chapter-0"):
            if not url or url in tried:
                continue
            tried.append(url)
            page = self._fetch(url)
            if page and self._chapter_nums(slug, page):
                got = (url, page)
                break
            if page:
                p = self._debug_dump(f"{slug}-anchor", page)
                print(f"  ! {url}: không thấy danh sách chương (site đổi giao diện?)"
                      + (f" — HTML lưu tại {p}" if p else ""), file=sys.stderr)
        self._anchor[slug] = got
        return got

    # -- hợp đồng provider -----------------------------------------------------------

    def series_slug(self, text: str) -> str:
        t = re.split(r"[?#]", text.strip())[0]
        if "://" in t:
            parts = [p for p in urlparse(t).path.split("/") if p]
        else:
            parts = [p for p in t.split("/") if p]
            if parts and "." in parts[0]:
                parts = parts[1:]           # 'truyenqq.com.vn/slug' không có scheme
        if not parts:
            return ""
        slug = parts[0].lower()
        if len(parts) > 1 and re.fullmatch(r"chapter-\d+", parts[1], re.I):
            self._hint[slug] = f"{self.BASE}/{slug}/{parts[1].lower()}"
        return slug

    def title_from_slug(self, slug: str) -> str:
        _, page = self._anchor_page(slug)
        name = ""
        m = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', page, re.I)
        if m:
            name = m.group(1)
        else:
            m = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.I | re.S)
            if m:
                name = re.sub(r"<[^>]+>", "", m.group(1))
        # neo CUỐI chuỗi: giữ nguyên tên có dấu ':' ("Goblin Slayer Gaiden: Year One")
        name = self._CH_TAIL.sub("", html_lib.unescape(name)).strip()
        if not name:
            m = re.search(r"var\s+bname\s*=\s*'((?:[^'\\]|\\.)*)'", page)
            name = m.group(1).replace("\\'", "'").strip() if m else ""
        if not name:
            name = slug.replace("-", " ").title()
        return name + self.SUFFIX

    def list_chapters(self, slug: str):
        _, page = self._anchor_page(slug)
        return [Chapter(float(n), "", f"{self.BASE}/{slug}/chapter-{n}")
                for n in self._chapter_nums(slug, page)]

    def _parse_images(self, page, num):
        """(urls, nhận_ra_cấu_trúc). Chính: `<img>` trong khối `.reading-content` (tới
        thanh điều hướng dưới `reading-option`), đọc data-src/data-original (không phụ
        thuộc thứ tự thuộc tính). Dự phòng khi mất khối: URL tuyệt đối có `/chapter-N/`
        ở cả trang (loại ảnh quảng cáo `/media/images/...` dùng src tương đối)."""
        i = page.find('class="reading-content"')
        if i >= 0:
            j = page.find('class="reading-option', i)
            block, strict = page[i:j if j > 0 else len(page)], False
        else:
            block, strict = page, True
        seen, out = set(), []
        for tag in re.findall(r"<img\b[^>]*>", block, re.I):
            m = re.search(r'\bdata-(?:src|original|lazy-src)\s*=\s*"(https?://[^"]+)"', tag, re.I)
            if not m:
                continue
            u = html_lib.unescape(m.group(1).strip())
            path = urlparse(u).path.lower()
            if not path.endswith(self._IMG_EXT):
                continue
            if strict and f"/chapter-{num}/" not in path:
                continue
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out, i >= 0

    def chapter_images(self, chapter):
        num = int(chapter.number)
        cached = [pg for (u, pg) in self._anchor.values() if u and u == chapter.ref]
        page = cached[0] if cached else self._fetch(chapter.ref)
        if not page:
            return []    # 404/mạng: core coi như chưa có ảnh, KHÔNG .done -> lượt sau thử lại
        urls, known = self._parse_images(page, num)
        if urls or known:
            # khối đọc có mà rỗng = chương rỗng thật ở nguồn -> bỏ qua chương đó, KHÔNG dừng
            self._layout_fail = 0
            return urls
        # Không nhận ra cấu trúc trang đọc: vài chương liền = site đổi giao diện -> dừng
        # phiên + báo rõ (thay vì lặng lẽ ghi "khóa/không ảnh" cho cả trăm chương).
        self._layout_fail += 1
        p = self._debug_dump(urlparse(chapter.ref).path.strip("/").replace("/", "-"), page)
        print(f"  ! Chapter {num}: không nhận ra cấu trúc trang đọc"
              + (f" — HTML lưu tại {p}" if p else ""), file=sys.stderr)
        if self._layout_fail >= self.LAYOUT_FAIL_LIMIT:
            raise Blocked(f"{self.LABEL}: {self._layout_fail} chương liền không đọc được "
                          "trang (site đổi giao diện?) — cần sửa parser, xem .reader-meta/"
                          "qqvn-debug/")
        return []

    def cover_url(self, slug: str):
        _, page = self._anchor_page(slug)
        m = re.search(r'"image"\s*:\s*"([^"]+?\.(?:jpe?g|png|webp|gif))"', page, re.I)
        if m:
            f = m.group(1).replace("\\/", "/")
            return f if f.startswith("http") else f"{self.BASE}/media/book/{f.lstrip('/')}"
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', page, re.I)
        if m and m.group(1).strip():
            u = m.group(1).strip()
            return u if u.startswith("http") else self.BASE + "/" + u.lstrip("/")
        return None


class MoeTruyenProvider:
    """moetruyen.net (Mòe Truyện) — truyện tiếng Việt. Ảnh trang bị bảo vệ IMGX: KHÔNG có
    URL ảnh tải thẳng (bytes qua `page-access` + worker, vẽ lên lớp canvas chặn đọc ngược).
    Nên tách 2 đường:

      - METADATA bằng HTTP thường (Cloudflare hiện không challenge GET; bị challenge thì
        THANG LEO sang Chromium như qqcomvn). Trang truyện `/manga/{slug}` chỉ liệt kê ~30
        chương mới nhất -> lấy 1 link chương làm MỐC: dropdown trang chương (`data-href=
        ".../chapters/N"` + "Ch. N — Tên") có ĐỦ cả bộ; gộp thêm list trang truyện cho chắc.
        Tên: `data-reading-manga-title`. Bìa: og:image (bản -md; bản lớn có chỗ 403 ->
        download_image ném Forbidden = dừng phiên, nên KHÔNG đoán URL). Số trang:
        `data-reader-total-pages` -> chapter_images trả URL GIẢ `moe://page/N.webp` để core
        đặt tên 001.webp… và biết trang nào thiếu MÀ KHÔNG mở trình duyệt (chương đủ -> .done
        ngay; check_updates dò chương bằng HTTP).
      - ẢNH = CHỤP trang đã hiển thị trong Chromium thật (cf_browser, profile `moe-profile`)
        qua móc `render_pages` của core.run. Chỉ QUAN SÁT DOM + chụp phần tử, KHÔNG đụng
        worker/page-access (site gửi header `X-AI-Policy: no-reverse-engineering`).

    Đo thực 30/09/2026 (Dragon Quest Emblem Of Roto ch.1, 72 trang, ~1.2 s/trang):
      - Cỡ trong HTML (`data-imgx-width/height`) SAI (960x1440); site ghi lại cỡ thật
        (1116x1584) khi img có `data-imgx-rendered="1"` -> CHỈ đọc cỡ trong trình duyệt.
      - Bố cục mặc định bóp khung ~955px -> chụp mất nét (lưới chấm bệt). Nới `.reader-pages`
        = đúng cỡ gốc W (ép từng `.page-frame` KHÔNG ăn) -> ảnh chụp đúng W px; nới SAU khi đã
        vẽ ra y hệt nới trước (lệch 0/255) -> đổi W theo từng trang là đủ.
      - Khung có viền 0.67px -> border:0; ảnh chụp có lúc dư 1px cao -> cắt về W×H.
      - Vẽ xong = `.page-protected-shell.is-loaded` + img `data-imgx-rendered="1"`.
      - Lớp phủ cố định: `aside.reader-dock` (ẩn cả lớp fixed/sticky ngoài khối trang). Khung
        "Chương kế tiếp" (`.reader-chapter-bridge`) nằm SAU trang cuối -> loại bằng selector.
      - Bytes ảnh do JS site fetch từ `*.ibyteimg.com` -> phải mở host đó cho Chromium.
    Lưu WebP q90 (PNG chụp ~1.3MB/trang; q90 ~260KB, lệch TB 0.54/255 — user chốt 30/09).
    Là lần mã hoá ĐẦU (không có byte gốc để giữ), không phải nén lại."""

    name = "moetruyen"
    BASE = "https://moetruyen.net"
    domains = ["moetruyen.net"]
    referer = None               # đã kiểm: bìa u.truyen.moe KHÔNG đòi Referer
    PROFILE = "moe-profile"      # profile Chromium riêng trong .reader-meta
    LABEL = "MoeTruyen"
    # Host ngoài site mà JS trang đọc gọi (đo 30/09): bytes ảnh ở *.ibyteimg.com, api/ảnh
    # *.truyen.moe; tiktokcdn + jsdelivr có trong CSP của site. Google/fonts/analytics bị
    # chặn vẫn hiển thị đủ.
    EXTRA_HOSTS = ("truyen.moe", "ibyteimg.com", "tiktokcdn.com", "cdn.jsdelivr.net")
    WEBP_Q = 90
    READY_TIMEOUT = 25           # giây chờ 1 trang vẽ xong
    PAGE_TRIES = 2               # số lần chụp 1 trang trước khi để lượt sau
    FAIL_STREAK_LIMIT = 5        # số trang LIỀN hụt -> dừng phiên (site đổi / chặn chụp)
    LAYOUT_FAIL_LIMIT = 3        # số chương LIỀN không đọc được cấu trúc -> dừng phiên
    VIEW_MIN_W, VIEW_H, VIEW_MARGIN = 1280, 900, 200

    _CARD = ".page-card:not(.reader-chapter-bridge)"
    _CSS = (".page-protected-shell,.page-media{border:0!important}"
            ".reader-dock{visibility:hidden!important}")
    _READY_JS = """(i) => {
      const c = document.querySelectorAll('%s')[i]; if (!c) return false;
      const s = c.querySelector('.page-protected-shell'), im = c.querySelector('img[data-imgx-width]');
      return !!(s && s.classList.contains('is-loaded') && im && im.dataset.imgxRendered === '1');
    }""" % _CARD
    _DIMS_JS = """(i) => {
      const c = document.querySelectorAll('%s')[i];
      const im = c.querySelector('img[data-imgx-width]'), s = c.querySelector('.page-protected-shell');
      return [+im.dataset.imgxWidth || 0, +im.dataset.imgxHeight || 0,
              s ? Math.round(s.getBoundingClientRect().width) : 0];
    }""" % _CARD
    _WIDTH_JS = """(w) => {
      let s = document.getElementById('moe-dl-width');
      if (!s) { s = document.createElement('style'); s.id = 'moe-dl-width'; document.head.appendChild(s); }
      s.textContent = '.reader-pages{width:' + w + 'px!important;max-width:none!important}'
                    + '.page-card,.page-frame{max-width:none!important}';
    }"""
    _HIDE_JS = """() => {
      const keep = document.querySelector('.reader-pages');
      for (const e of document.querySelectorAll('body *')) {
        const p = getComputedStyle(e).position;
        if ((p === 'fixed' || p === 'sticky') && !(keep && keep.contains(e)))
          e.style.setProperty('visibility', 'hidden', 'important');
      }
    }"""
    _TITLE_TXT = re.compile(r"^\s*Ch(?:apter|ương)?\.?\s*[0-9]+(?:\.[0-9]+)?\s*(?:[—–:-]\s*(.*))?$",
                            re.I | re.S)

    def __init__(self):
        self.fetch_mode = "auto"    # auto | http | browser (--fetch) — chỉ cho METADATA
        self.allow_browser = True   # check_updates tắt: dò chương không mở Chromium
        self._escalated = False
        self._browser = None
        self._hint = {}             # slug -> URL chương người dùng dán (mốc ưu tiên)
        self._series = {}           # slug -> HTML trang truyện
        self._anchor = {}           # slug -> (url, html) trang chương mốc (cả khi hụt)
        self._n_pages = {}          # chapter.ref -> số trang theo HTML
        self._layout_fail = 0
        self._render_fail = 0

    # -- tải HTML: HTTP -> (challenge) -> Chromium (y khuôn qqcomvn) --------------------

    def _fetch(self, url):
        if self.fetch_mode != "browser" and not self._escalated:
            try:
                page = get_text(url)
                if page is None or not re.search(
                        r"<title>\s*(?:just a moment|attention required)", page[:4000], re.I):
                    return page
                raise Challenged(f"Cloudflare trả trang xác minh tại {url}")
            except Challenged as e:
                if self.fetch_mode == "http" or not self.allow_browser:
                    raise
                print(f"\n  ! {e}\n  -> Chuyển sang TRÌNH DUYỆT THẬT (Chromium) cho phần còn "
                      "lại của phiên...", flush=True)
                self._escalated = True
        return self._get_browser().get_html(url)

    def _get_browser(self):
        if self._browser is None:
            import cf_browser    # lười: Playwright chỉ nạp khi cần chụp trang / bị chặn
            host = urlparse(self.BASE).hostname or "moetruyen.net"
            b = cf_browser.CFBrowser(self.PROFILE, host, self.LABEL,
                                     extra_hosts=self.EXTRA_HOSTS, block_types=())
            b.open()
            self._browser = b
        return self._browser

    def close(self):
        """comic_downloader gọi trong finally -> không để Chromium mồ côi ôm profile."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None

    def _debug_dump(self, name, page):
        try:
            d = META_DIR / "moe-debug"
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{name}.html"
            p.write_text(page or "", encoding="utf-8")
            return p
        except OSError:
            return None

    # -- metadata -------------------------------------------------------------------

    def _series_page(self, slug):
        if slug not in self._series:
            self._series[slug] = self._fetch(f"{self.BASE}/manga/{slug}") or ""
        return self._series[slug]

    def _chapter_links(self, slug, page):
        """[(số, đoạn URL, tên)] từ dropdown trang chương (có tên) + mọi link chương (dự
        phòng, không tên). Đoạn URL giữ nguyên để dựng ref; số lẻ nhận cả '.'/'-'."""
        base = r'(?:https?://[^/"]+)?/manga/' + re.escape(slug) + r'/chapters/([^"/?#]+)"'
        out = []
        for seg, inner in re.findall(r'data-href="' + base + r'[^>]*>\s*<span[^>]*'
                                     r'reader-dropdown-option-text[^>]*>(.*?)</span>', page or "", re.S):
            txt = html_lib.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
            m = self._TITLE_TXT.match(txt)
            out.append((seg, (m.group(1) or "").strip() if m else ""))
        out += [(seg, "") for seg in re.findall(r'(?:href|data-href|value)="' + base, page or "")]
        res = []
        for seg, title in out:
            if not re.fullmatch(r"[0-9]+(?:[.-][0-9]+)?", seg):
                continue
            res.append((float(seg.replace("-", ".")), seg, title))
        return res

    def _anchor_page(self, slug):
        """(url, html) trang chương có dropdown đủ bộ; ('', '') nếu không lấy được. Thử link
        người dùng dán trước, rồi 2 link chương đầu tiên thấy trên trang truyện."""
        if slug in self._anchor:
            return self._anchor[slug]
        cands = [self._hint.get(slug)]
        cands += [f"{self.BASE}/manga/{slug}/chapters/{seg}"
                  for _, seg, _ in self._chapter_links(slug, self._series_page(slug))[:2]]
        tried, got = [], ("", "")
        for url in cands:
            if not url or url in tried:
                continue
            tried.append(url)
            page = self._fetch(url)
            if page and "data-reader-option" in page and self._chapter_links(slug, page):
                got = (url, page)
                break
            if page:
                p = self._debug_dump(f"{slug}-anchor", page)
                print(f"  ! {url}: không thấy danh sách chương (site đổi giao diện?)"
                      + (f" — HTML lưu tại {p}" if p else ""), file=sys.stderr)
        self._anchor[slug] = got
        return got

    def series_slug(self, text: str) -> str:
        t = re.split(r"[?#]", text.strip())[0]
        m = re.search(r"/manga/([^/]+)(?:/chapters/([^/]+))?", t)
        if not m:
            return t.rstrip("/").rsplit("/", 1)[-1]
        slug = m.group(1)
        if m.group(2):
            self._hint[slug] = f"{self.BASE}/manga/{slug}/chapters/{m.group(2)}"
        return slug

    def title_from_slug(self, slug: str) -> str:
        _, page = self._anchor_page(slug)
        m = re.search(r'data-reading-manga-title="([^"]*)"', page)
        name = html_lib.unescape(m.group(1)).strip() if m else ""
        if not name:   # og:title trang truyện: "Tên [Tới Chap 92]"
            m = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"',
                          self._series_page(slug), re.I)
            if m:
                name = re.sub(r"\s*\[[^\]]*\]\s*$", "", html_lib.unescape(m.group(1))).strip()
        return name or re.sub(r"^\d+-", "", slug).replace("-", " ").title()

    def list_chapters(self, slug: str):
        _, page = self._anchor_page(slug)
        found = {}   # số -> (đoạn URL, tên); dropdown (đủ bộ, có tên) trước, trang truyện bù
        for src in (page, self._series_page(slug)):
            for num, seg, title in self._chapter_links(slug, src):
                if num not in found or (title and not found[num][1]):
                    found[num] = (seg, title)
        return [Chapter(n, found[n][1], f"{self.BASE}/manga/{slug}/chapters/{found[n][0]}")
                for n in sorted(found)]

    def cover_url(self, slug: str):
        for page in (self._series_page(slug), self._anchor_page(slug)[1]):
            m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', page or "", re.I)
            if m and m.group(1).strip():
                u = html_lib.unescape(m.group(1).strip())
                return u if u.startswith("http") else self.BASE + "/" + u.lstrip("/")
        return None

    def chapter_images(self, chapter):
        """URL GIẢ cho từng trang (ảnh thật do render_pages chụp). Số trang lấy từ HTML
        (HTTP) -> chương đủ ảnh trên đĩa thì core đánh .done mà không mở trình duyệt."""
        cached = [pg for (u, pg) in self._anchor.values() if u and u == chapter.ref]
        page = cached[0] if cached else self._fetch(chapter.ref)
        if not page:
            return []    # 404/mạng: coi như chưa có ảnh, KHÔNG .done -> lượt sau thử lại
        m = re.search(r'data-reader-total-pages="(\d+)"', page)
        n = int(m.group(1)) if m else len(re.findall(r'class="page-card"', page))
        if not m and not n:
            self._layout_fail += 1
            p = self._debug_dump(urlparse(chapter.ref).path.strip("/").replace("/", "-"), page)
            print(f"  ! Chapter {chapter.number:g}: không nhận ra trang đọc (khoá/cần đăng nhập, "
                  "hoặc site đổi giao diện)" + (f" — HTML lưu tại {p}" if p else ""),
                  file=sys.stderr)
            if self._layout_fail >= self.LAYOUT_FAIL_LIMIT:
                raise Blocked(f"{self.LABEL}: {self._layout_fail} chương liền không đọc được "
                              "trang (site đổi giao diện?) — xem .reader-meta/moe-debug/")
            return []
        self._layout_fail = 0
        self._n_pages[chapter.ref] = n
        return [f"moe://page/{k}.webp" for k in range(1, n + 1)]

    # -- chụp trang (móc render_pages của core.run) ----------------------------------

    def _open_chapter(self, ref):
        """Mở trang chương trên Chromium + CSS chụp; None nếu không mở được."""
        b = self._get_browser()
        if not b.goto(ref):
            return None
        page = b.page
        page.add_style_tag(content=self._CSS)
        if page.locator("[data-reader-capture-guard-enabled='true']").count():
            print(f"\n  ! {self.LABEL} đang BẬT chống chụp (capture-guard) — ảnh chụp có thể "
                  "hỏng; bộ kiểm sẽ loại khung phẳng.", file=sys.stderr, flush=True)
        return page

    def _wait_ready(self, page, i):
        end = time.monotonic() + self.READY_TIMEOUT
        while time.monotonic() < end:
            if page.evaluate(self._READY_JS, i):
                return True
            time.sleep(0.25)
        return False

    def _capture(self, page, i, cur_w):
        """Chụp trang i (0-based). Trả (bytes WebP | None, lý do hụt, W đang áp, chữ ký)."""
        card = page.locator(self._CARD).nth(i)
        card.scroll_into_view_if_needed(timeout=15000)
        if not self._wait_ready(page, i):
            return None, f"chưa vẽ xong sau {self.READY_TIMEOUT}s", cur_w, None
        w, h, _ = page.evaluate(self._DIMS_JS, i)
        if not (w and h):
            return None, "không đọc được cỡ trang", cur_w, None
        if w != cur_w:
            # Nới khối trang = đúng cỡ gốc (viewport rộng hơn để không bị bóp) rồi chờ khung
            # giãn đủ + site vẽ lại. Trang liền nhau thường cùng W -> ít khi phải đổi.
            page.set_viewport_size({"width": max(self.VIEW_MIN_W, w + self.VIEW_MARGIN),
                                    "height": self.VIEW_H})
            page.evaluate(self._WIDTH_JS, w)
            cur_w = w
            card.scroll_into_view_if_needed(timeout=15000)
            end = time.monotonic() + 5
            while page.evaluate(self._DIMS_JS, i)[2] != w and time.monotonic() < end:
                time.sleep(0.2)
            if not self._wait_ready(page, i):
                return None, "chưa vẽ lại xong sau khi nới khung", cur_w, None
            time.sleep(0.3)
        page.evaluate(self._HIDE_JS)
        png = card.locator(".page-protected-shell").screenshot(
            type="png", animations="disabled", caret="hide", timeout=30000)
        data, why, sig = self._encode(png, w, h)
        return data, why, cur_w, sig

    def _encode(self, png, w, h):
        """PNG chụp -> (WebP q90 | None, lý do hụt, chữ ký pixel). Kiểm: đúng cỡ gốc (±2px,
        cắt về W×H), không phải khung một màu, WebP ra giải mã được."""
        from PIL import Image
        try:
            im = Image.open(io.BytesIO(png))
            im.load()
        except Exception as e:
            return None, f"ảnh chụp lỗi ({e.__class__.__name__})", None
        iw, ih = im.size
        if abs(iw - w) > 2 or abs(ih - h) > 2:
            return None, f"cỡ chụp {iw}x{ih} lệch cỡ gốc {w}x{h}", None
        if (iw, ih) != (w, h):
            im = im.crop((0, 0, min(iw, w), min(ih, h)))
        flat = uniform_frame(im)
        if flat:
            return None, f"khung một màu — {flat[1]}", None
        rgb = im.convert("RGB")
        buf = io.BytesIO()
        rgb.save(buf, "WEBP", quality=self.WEBP_Q, method=4)
        data = buf.getvalue()
        verdict, detail = check_image_bytes(data)
        if verdict not in ("ok", "unsupported"):
            return None, f"WebP hỏng: {detail}", None
        return data, "", hashlib.sha1(rgb.tobytes()).digest()

    def render_pages(self, chapter, jobs):
        """Chụp các trang còn thiếu của 1 chương, TUẦN TỰ ở main thread; yield True/False
        mỗi job. Trang hụt KHÔNG ghi file -> core đếm thiếu, lượt sau chụp bù."""
        page = self._open_chapter(chapter.ref)
        n = page.locator(self._CARD).count() if page is not None else 0
        want = self._n_pages.get(chapter.ref)
        if page is None or (want and n != want):
            why = ("trình duyệt không mở được trang" if page is None
                   else f"trình duyệt thấy {n} trang, HTML báo {want}")
            print(f"\n  ! Chapter {chapter.number:g}: {why} — bỏ chương này, để lượt sau.",
                  file=sys.stderr, flush=True)
            self._render_fail += 1
            if self._render_fail >= self.LAYOUT_FAIL_LIMIT:
                raise Blocked(f"{self.LABEL}: {self._render_fail} chương liền không mở/đếm được "
                              f"trang trong trình duyệt ({why})")
            for _ in jobs:
                yield False
            return
        self._render_fail = 0
        cur_w, prev_sig, streak = None, None, 0
        for url, dest in jobs:
            if page is None:        # mất trình duyệt, dựng lại cũng không mở được chương
                yield False
                continue
            i = int(url.rsplit("/", 1)[-1].split(".")[0]) - 1
            data, why, sig = None, "", None
            for attempt in range(self.PAGE_TRIES):
                try:
                    data, why, cur_w, sig = self._capture(page, i, cur_w)
                except Blocked:
                    raise
                except Exception as e:
                    data, why = None, f"lỗi trình duyệt ({e.__class__.__name__})"
                    if not self._browser.alive():
                        page = self._open_chapter(chapter.ref)   # dựng lại + mở lại chương
                        cur_w = None
                        if page is None:
                            break
                    continue
                if data is not None and sig == prev_sig and attempt + 1 < self.PAGE_TRIES:
                    data, why = None, "giống hệt trang trước"   # nghi chụp nhầm -> thử lại
                    time.sleep(1)
                    continue
                if data is not None:
                    break
                time.sleep(1)
            if data is None:
                streak += 1
                print(f"\n    ! Trang {i + 1}: {why} — để lượt sau chụp bù.",
                      file=sys.stderr, flush=True)
                if streak >= self.FAIL_STREAK_LIMIT:
                    raise Blocked(f"{self.LABEL}: {streak} trang liền không chụp được ({why}) — "
                                  "site đổi giao diện / bật chống chụp / truyện cần đăng nhập?")
                yield False
                continue
            if sig == prev_sig:
                print(f"\n    ~ Trang {i + 1} giống hệt trang trước (đã thử lại) — vẫn lưu, "
                      "nên xem tay.", file=sys.stderr, flush=True)
            streak = 0
            tmp = dest.with_name(dest.name + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, dest)
            clear_bad(dest)
            prev_sig = sig
            yield True
            time.sleep(random.uniform(0.2, 0.5))


def _short_title(name: str, limit: int = 100) -> str:
    """Tên one-shot (nhentai/hentaifc) có thể rất dài -> cắt ở ranh giới từ <= `limit` ký tự,
    bỏ dấu câu treo cuối. Cộng hậu tố mã + `\\Chapter 1\\001.webp` vẫn dưới MAX_PATH Windows."""
    name = re.sub(r"\s+", " ", name).strip()
    if len(name) <= limit:
        return name
    cut = name[:limit]
    if " " in cut[limit // 2:]:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" -–—:,.;([{")


class NHentaiToProvider:
    """nhentai.to — clone Laravel của nhentai (KHÔNG phải nhentai.net: backend/CDN khác, chưa
    kiểm). Mỗi link `/g/{id}/` là 1 cuốn ONE-SHOT trọn (không chia chương) -> 1 Chapter số 1.

    1 request trang gallery là đủ: khối JS `new N.gallery({...})` có `media_id`, `title`
    {english, japanese, pretty}, `images.pages` (t = w/j/p/g -> webp/jpg/png/gif), `num_pages`.
    Khối đó KHÔNG phải JSON hợp lệ (dấu phẩy treo trước `})`) -> regex từng trường.
    ⚠️ `images.pages` có 2 dạng (đo 01/10/2026): gallery cũ = MẢNG (phần tử 0 = trang 1);
    gallery mới = DICT key LỆCH +1 ("2".."43" cho 42 trang, g624421; `43.webp` 404). Gom về
    thứ tự (mảng giữ nguyên, dict sắp theo key số) rồi lấy phần tử i-1 cho trang i — đúng cả 2
    dạng, không phụ thuộc độ lệch. Số lượng lệch `num_pages` -> dự phòng đuôi từ thumbnail
    `{n}t.{ext}` trong HTML (thumbnail cùng đuôi với ảnh lớn).
    ⚠️ id trên URL (624421) KHÁC "id" trong JSON (606921, id nội bộ) -> luôn dùng id URL.
    Ảnh `supercdn.site/galleries/{media_id}/{n}.{ext}` (1280px; host đọc từ HTML, không cứng),
    bìa `cover.{ext}` (350px). Cloudflare có mặt nhưng KHÔNG challenge GET thường; CDN KHÔNG đòi
    Referer (đã thử có/không).
    Folder = tên NGẮN (`pretty`) + " [nh{id}]": tên đầy đủ ~110 ký tự dễ vượt MAX_PATH, còn tên
    ngắn trùng giữa các bản dịch/nhóm -> mã gallery giữ mỗi cuốn 1 folder riêng (user chốt
    01/10/2026). `positional_numbers`: số chương (luôn 1) không phải số thật -> chặn `into:`.
    """

    name = "nhentai"
    BASE = "https://nhentai.to"
    CDN = "https://supercdn.site"     # dự phòng khi HTML không lộ host ảnh
    domains = ["nhentai.to"]
    referer = None
    positional_numbers = True
    SUFFIX = " [nh<mã gallery>]"      # chỉ để CLI in lý do chặn into:; hậu tố thật gắn theo id
    _EXT = {"w": "webp", "j": "jpg", "p": "png", "g": "gif"}

    def __init__(self):
        self._html_cache = {}   # id -> HTML trang gallery (title + list + ảnh + bìa dùng chung)
        self._info_cache = {}

    def _gallery(self, gid: str) -> str:
        if gid not in self._html_cache:
            self._html_cache[gid] = get_text(f"{self.BASE}/g/{gid}/") or ""
        return self._html_cache[gid]

    def _info(self, gid: str):
        """{'cdn', 'media', 'exts': [đuôi trang 1..N], 'cover'} hoặc None (gallery xoá/đổi giao diện)."""
        if gid in self._info_cache:
            return self._info_cache[gid]
        html = self._gallery(gid)
        i = html.find("new N.gallery(")
        blk = html[i:] if i >= 0 else ""
        m_media = re.search(r'"media_id":\s*"(\d+)"', blk)
        m_num = re.search(r'"num_pages":\s*(\d+)', blk)
        if not (m_media and m_num):
            if html:
                print(f"  ! {self.name}: không thấy khối N.gallery (media_id/num_pages) — "
                      "site đổi giao diện?", file=sys.stderr)
            return None
        media, npages = m_media.group(1), int(m_num.group(1))
        exts = []
        m_pages = re.search(r'"pages":\s*(\[.*?\]|\{.*?\})\s*,\s*"cover"', blk, re.S)
        try:
            raw = json.loads(m_pages.group(1)) if m_pages else []
            seq = raw if isinstance(raw, list) else [raw[k] for k in sorted(raw, key=int)]
            exts = [self._EXT.get((p or {}).get("t"), "") for p in seq]
        except (ValueError, TypeError, AttributeError):
            exts = []
        if len(exts) != npages or not all(exts):
            thumbs = dict(re.findall(r"/galleries/%s/(\d+)t\.(\w+)" % media, html))
            print(f"  ! {self.name}: images.pages lệch num_pages ({len(exts)}≠{npages}) — "
                  f"lấy đuôi theo thumbnail ({len(thumbs)} cái)", file=sys.stderr)
            exts = [thumbs.get(str(n), "webp") for n in range(1, npages + 1)]
        m_cdn = re.search(r"(https?://[^/\"'\s]+)/galleries/%s/" % media, html)
        m_cover = re.search(r'"cover":\s*\{"t":"(\w)"', blk)
        info = {"cdn": m_cdn.group(1) if m_cdn else self.CDN, "media": media, "exts": exts,
                "cover": self._EXT.get(m_cover.group(1)) if m_cover else None}
        self._info_cache[gid] = info
        return info

    def series_slug(self, text: str) -> str:
        m = re.search(r"/g/(\d+)", text)
        return m.group(1) if m else text.strip().strip("/")

    def title_from_slug(self, slug: str) -> str:
        html = self._gallery(slug)
        i = html.find("new N.gallery(")
        blk = html[i:] if i >= 0 else ""
        name = ""
        for key in ("pretty", "english", "japanese"):
            m = re.search(r'"%s":\s*("(?:[^"\\]|\\.)*")' % key, blk)
            if m:
                try:
                    name = json.loads(m.group(1)).strip()
                except ValueError:
                    name = ""
            if name:
                break
        if not name:
            m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
            name = html_lib.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
        return f"{_short_title(name) or 'nhentai'} [nh{slug}]"

    def list_chapters(self, slug: str):
        return [Chapter(1, "", slug)] if self._info(slug) else []

    def chapter_images(self, chapter):
        info = self._info(chapter.ref)
        if not info:
            return []
        base = f"{info['cdn']}/galleries/{info['media']}"
        return [f"{base}/{n}.{ext}" for n, ext in enumerate(info["exts"], 1)]

    def cover_url(self, slug: str):
        info = self._info(slug)
        if not info:
            return None
        ext = info["cover"] or (info["exts"][0] if info["exts"] else "webp")
        return f"{info['cdn']}/galleries/{info['media']}/cover.{ext}"


class HentaiFCProvider:
    """hentaifc.com — gallery 18+ tiếng Anh (cùng loại nội dung nhentai), nginx trần, KHÔNG
    Cloudflare. Gần như mọi gallery là ONE-SHOT 1 chương `c0` (đo 7 gallery 01/10/2026), nhưng
    trang đọc có dropdown chương -> vẫn đọc đủ danh sách nếu gặp cuốn nhiều chương.

    - Trang gallery `/e/{id}`: tên `<h1 class="heading">`; khối `.thumbs` = thumbnail từng trang
      (`s3.hentaifc.com/token/.../0.jpg`, thực chất WebP 400px) -> thumbnail ĐẦU làm BÌA (trang
      không có bìa riêng; khối "Same Artist" bên phải là bìa cuốn KHÁC). Link "Read Online"
      -> `/e/{id}/c{N}`.
    - Trang đọc `/e/{id}/c{N}`: `<select class="chapter_select">` (`<option value="cN">`) =
      danh sách chương; URL ảnh nằm trong `var ytaw=['104 116 ...', ...]` — mỗi phần tử là chuỗi
      MÃ KÝ TỰ cách nhau dấu cách (JS `String.fromCharCode`) -> `s2.hentaifc.com/token/<token>/
      {i}.jpg` (JPEG ~1100px). Chỉ là che URL khỏi bot quét chữ, không phải mã hoá. Đối chiếu
      `var num_page = N`.
    - URL ảnh mang TOKEN (JS trang có logic tải lại ảnh lỗi) -> nghi có hạn: KHÔNG lưu URL; HTML
      trang đọc chỉ dùng lại trong `READER_TTL` giây (list_chapters vừa tải -> chapter_images
      khỏi tải lại cho one-shot), quá thì tải mới.
    - CDN trả `application/octet-stream`, KHÔNG đòi Referer (đã thử có/không) -> referer=None.
    Số chương: c{N} -> N+1 (c0 = Chapter 1, đồng bộ one-shot nhentai); nhãn dropdown khác kiểu
    "Chapter N" thì làm tên chương. Folder = tên + " [fc{id}]"; `positional_numbers` như nhentai.
    """

    name = "hentaifc"
    BASE = "https://hentaifc.com"
    domains = ["hentaifc.com"]
    referer = None
    positional_numbers = True
    SUFFIX = " [fc<mã gallery>]"
    READER_TTL = 300

    def __init__(self):
        self._html_cache = {}     # id -> HTML trang gallery (title + list + bìa)
        self._reader_cache = {}   # url trang đọc -> (thời điểm tải, HTML)

    def _gallery(self, gid: str) -> str:
        if gid not in self._html_cache:
            self._html_cache[gid] = get_text(f"{self.BASE}/e/{gid}") or ""
        return self._html_cache[gid]

    def _reader(self, url: str) -> str:
        hit = self._reader_cache.get(url)
        if hit and time.time() - hit[0] < self.READER_TTL:
            return hit[1]
        html = get_text(url) or ""
        if html:
            self._reader_cache[url] = (time.time(), html)
        return html

    def series_slug(self, text: str) -> str:
        m = re.search(r"/e/(\d+)", text)
        return m.group(1) if m else text.strip().strip("/")

    def title_from_slug(self, slug: str) -> str:
        html = self._gallery(slug)
        m = re.search(r'<h1 class="heading">(.*?)</h1>', html, re.S)
        name = html_lib.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            name = re.sub(r"\s*-\s*HentaiFC\s*$", "", html_lib.unescape(m.group(1))).strip() if m else ""
        return f"{_short_title(name) or 'hentaifc'} [fc{slug}]"

    def list_chapters(self, slug: str):
        html = self._gallery(slug)
        if not html:
            return []
        found = {int(n): "" for n in re.findall(r"/e/%s/c(\d+)" % slug, html)}
        first = min(found) if found else 0
        page = self._reader(f"{self.BASE}/e/{slug}/c{first}")
        sel = re.search(r'<select[^>]*class="chapter_select[^"]*"[^>]*>(.*?)</select>', page, re.S)
        if sel:
            for n, label in re.findall(r'<option value="c(\d+)"[^>]*>([^<]*)</option>', sel.group(1)):
                found[int(n)] = html_lib.unescape(label).strip()
        if not found and "var ytaw" in page:
            found[0] = ""
        out = []
        for n in sorted(found):
            label = found[n]
            title = "" if not label or re.fullmatch(r"(?i)chapter\s*\d+", label) else label
            out.append(Chapter(n + 1, title, f"{self.BASE}/e/{slug}/c{n}"))
        return out

    def chapter_images(self, chapter):
        page = self._reader(chapter.ref)
        m = re.search(r"var ytaw=\[(.*?)\];", page, re.S)
        if not m:
            if page:
                print(f"  ! {self.name}: không thấy mảng ảnh `ytaw` — site đổi giao diện?",
                      file=sys.stderr)
            return []
        urls = []
        for codes in re.findall(r"'([\d ]+)'", m.group(1)):
            u = "".join(chr(int(x)) for x in codes.split())
            if u.startswith("http"):
                urls.append(u)
        n = re.search(r"var num_page = (\d+)", page)
        if n and int(n.group(1)) != len(urls):
            print(f"  ! {self.name}: giải được {len(urls)} URL ảnh nhưng trang báo "
                  f"{n.group(1)} trang", file=sys.stderr)
        return urls

    def cover_url(self, slug: str):
        html = self._gallery(slug)
        i = html.find('class="thumbs"')
        m = re.search(r'<img[^>]+data-src="(https?://[^"]+)"', html[i:]) if i >= 0 else None
        return m.group(1) if m else None


class HentaiVNXProvider:
    """hentaivnx.com (HentaiVn) — truyện 18+ tiếng Việt, giao diện họ NetTruyen (`title-detail`),
    Cloudflare có mặt nhưng KHÔNG challenge GET thường -> HTTP trần.

    - Trang bộ `/truyen-hentai/{slug}-{idBộ}`: ĐỦ danh sách chương trong HTML (đo bộ 147/147), link
      `/truyen-hentai/{slug}/chapter-N/{idChương}` — slug chương = slug bộ BỎ đuôi `-{idBộ}` -> lọc
      theo đó (trang còn khối truyện khác). ⚠️ Trang bộ bị cache ~4h (`max-age=14400`): chương mới
      có thể vắng vài giờ dù trang chủ đã hiện. Bộ cũ/doujin one-shot chỉ có `chapter-0`.
      Link 1 chương -> breadcrumb trang chương dẫn về trang bộ (có idBộ).
    - Trang chương: `var cdn1..cdn4 = '[json]'` = các nguồn ảnh. **cdn1** (`sv{3,4,5}.2tcdn.cfd`,
      bản site tự lưu, đánh số 1..N, KHÔNG token) = ảnh trang hiển thị mặc định -> CHỌN; có mặt
      18/18 chương mẫu (01/10/2026). Nguồn khác chỉ là dự phòng: cdn3/cdn4 (`all.2tcdn.cfd`) có lúc
      lẫn 1 ảnh LẠC của bộ khác (`00.jpg`, lệch ±1 trang); cdn2 = bọc proxy duckduckgo (bộ cũ) hoặc
      DẢI LIỀN 729×21250 có token hết hạn ~1 ngày (bộ mới; cdn1 cắt dải đó thành lát 729×5000 —
      cùng điểm ảnh, lát hợp reader/iOS hơn và vừa giới hạn WebP 16383px).
    - Ảnh JPEG/WebP/PNG tuỳ bộ (PNG ~3.7MB/lát -> ~80MB/chương) -> `png_to_webp`: core mã hoá lại
      WebP q90 lúc tải (đo: ~13-15% dung lượng). CDN KHÔNG đòi Referer (đã thử có/không).
    - JS trang xử lý 2 ca: URL có `-----NN` (ảnh ghép ngang NN%) và URL duckduckgo (no-referrer)
      — chưa gặp ca `-----` trong dữ liệu thật; gặp thì cắt hậu tố + cảnh báo (bố cục ngang mất).
    Bìa `.col-image img` (`/images/comics/{slug}.jpg`, bytes WebP ~233×350). Số chương = số thật
    trên site (`chapter-N`, lẻ `N-5`/`N.5`) -> không hậu tố, ghép `into:` được.
    """

    name = "hentaivnx"
    BASE = "https://www.hentaivnx.com"
    domains = ["hentaivnx.com"]          # resolver đã cắt "www."
    referer = None
    png_to_webp = True
    _CDN_ORDER = ("cdn1", "cdn3", "cdn4", "cdn2")

    def __init__(self):
        self._html_cache = {}

    def _series_html(self, slug: str) -> str:
        if slug not in self._html_cache:
            self._html_cache[slug] = get_text(f"{self.BASE}/truyen-hentai/{slug}") or ""
        return self._html_cache[slug]

    def series_slug(self, text: str) -> str:
        text = re.split(r"[?#]", text.strip())[0].rstrip("/")
        m = re.search(r"/truyen-hentai/([^/]+)(/chapter-[^/]+/\d+)?", text)
        if not m:
            return text.rsplit("/", 1)[-1]
        if not m.group(2):
            return m.group(1)
        # link 1 chương: slug chương KHÔNG có idBộ -> hỏi breadcrumb trang chương
        page = get_text(f"{self.BASE}/truyen-hentai/{m.group(1)}{m.group(2)}") or ""
        b = re.search(r'/truyen-hentai/(%s-\d+)"' % re.escape(m.group(1)), page)
        return b.group(1) if b else m.group(1)

    def title_from_slug(self, slug: str) -> str:
        html = self._series_html(slug)
        m = re.search(r'<h1[^>]*class="title-detail"[^>]*>(.*?)</h1>', html, re.S)
        name = html_lib.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
        if not name:
            name = re.sub(r"-\d+$", "", slug).replace("-", " ").title()
        return name

    def list_chapters(self, slug: str):
        html = self._series_html(slug)
        base = re.sub(r"-\d+$", "", slug)
        pat = re.compile(r'href="([^"]*/truyen-hentai/%s/chapter-([0-9]+(?:[.\-][0-9]+)?)/\d+)"'
                         % re.escape(base))
        seen = {}
        for url, tail in pat.findall(html):
            num = float(tail.replace("-", "."))
            seen.setdefault(num, url if url.startswith("http") else self.BASE + url)
        return [Chapter(n, "", seen[n]) for n in sorted(seen)]

    def chapter_images(self, chapter):
        html = get_text(chapter.ref) or ""
        lists = {}
        for k in self._CDN_ORDER:
            m = re.search(r"var %s = '(.*?)';" % k, html)
            if not m:
                continue
            try:
                arr = json.loads(m.group(1).replace("\\'", "'"))
            except ValueError:
                continue
            lists[k] = [html_lib.unescape(u) for u in arr if isinstance(u, str) and u.strip()]
        if not lists:
            if html:
                print(f"  ! {self.name}: không thấy biến cdn1..cdn4 — site đổi giao diện?",
                      file=sys.stderr)
            return []
        src, urls = next(((k, lists[k]) for k in self._CDN_ORDER if lists.get(k)), (None, []))
        if src and src != "cdn1":
            print(f"  ~ {self.name}: cdn1 rỗng — dùng {src}", file=sys.stderr)
        out = []
        for u in urls:
            if "-----" in u:   # ảnh ghép ngang (JS đặt float:left width%) -> reader xếp dọc
                print(f"  ~ {self.name}: ảnh ghép ngang, bố cục ngang sẽ mất: {u}", file=sys.stderr)
                u = u.split("-----", 1)[0]
            if "duckduckgo.com/iu" in u:   # proxy: core suy đuôi file từ path '/iu/' -> lấy URL gốc
                u = (parse_qs(urlparse(u).query).get("u") or [u])[0]
            out.append(u)
        return out

    def cover_url(self, slug: str):
        html = self._series_html(slug)
        m = re.search(r'class="[^"]*\bcol-image\b[^"]*"[^>]*>\s*<img[^>]+src="([^"]+)"', html)
        if not m:
            return None
        u = m.group(1)
        return u if u.startswith("http") else self.BASE + u


class LXMangaProvider:
    """lxmanga.org — truyện 18+ tiếng Việt (WordPress, theme riêng "lxmanga").

    ⚠️ NHÀ MẠNG CHẶN SNI (đo 01/10/2026, PC mạng Viettel): DNS đúng (IP Cloudflare) nhưng bắt
    tay TLS bị cắt khi SNI = lxmanga.org -> requests/curl KHÔNG BAO GIỜ tới. Chromium Playwright
    qua nhờ ECH (`/cdn-cgi/trace` -> `sni=encrypted`) và tự qua CF managed challenge ~3s, không
    cần tick (cf_clearance giữ trong profile) => MỌI HTML qua cf_browser, KHÔNG thử HTTP. (Pane
    browser trong app Claude — Electron — bị LẶP challenge sau tick: đừng dùng nó để thử site.)
    - Trang bộ `/{slug}.html`: HTML thô KHÔNG có danh sách chương (JS nạp qua admin-ajax
      `baka_ajax`) -> `goto` + chờ `ul.chapter-list li a` rồi đọc DOM (quan sát, không tự gọi
      AJAX). Mới nhất đứng đầu; bộ 263 chương ra đủ 263. Tên `h1.comic-title`, bìa og:image.
    - Trang chương `/{slug}/{chương}.html`: HTML THÔ có sẵn ảnh trong `<section id="viewer">`
      -> `get_html`. Ảnh "Server Gốc" `cdn{1,2,3}.tymanga.com` KHÔNG bị chặn, KHÔNG đòi Referer
      -> core tải HTTP đa luồng như site thường (12/12 chương mẫu của 4 bộ đều cdn2). Lẫn vài
      trang PNG -> `png_to_webp` như hentaivnx.
    - Bìa (`.avif` trên lxmanga.org — bị chặn với HTTP) -> qua proxy ảnh `i0.wp.com`, chính là
      "Server CDN 1-3" của site (JS `chuyenServerImg` đổi src sang `i{n}.wp.com/…?ssl=1`); proxy
      trả JPEG -> file `cover.avif` chứa bytes JPEG (lệch đuôi, tiền lệ ZetTruyen).
    - SỐ CHƯƠNG: nhãn tự do. Bộ thường "Chap N" / "Chap N END" / "Chương N" (slug `chap-N`) ->
      số thật, KHÔNG hậu tố, ghép `into:` được. Bộ TUYỂN TẬP ("Sex Tu Tiên Tổng Hợp": "Chương 1",
      "Dâm Nữ Đạo Chap 1", "(Dâm Nữ Đạo) C3"…; "series-…": "(✮Update) Lén lút … 4") -> số trùng/
      thiếu -> SỐ VỊ TRÍ (cũ nhất = 1) + nhãn làm tên chương + folder hậu tố SUFFIX (không bao
      giờ trộn folder nguồn số thật). ⚠️ Site xoá/chèn chương giữa chừng thì số vị trí lệch.
    - Chương "Raw" (vd "Phần 7 Raw [Sẽ Xóa Sau Khi Dịch Xong]") BỎ QUA: bản dịch sẽ thay vào cùng
      chỗ; tải raw thì `.done` chặn luôn bản dịch. Số vị trí vẫn tính cả chương raw (ổn định khi
      bản dịch thay vào).
    - check_updates (allow_browser=False) -> ném Challenged ngay -> status 'browser' -> supervisor
      vẫn xếp job tải (job mở Chromium), như comix.
    """

    name = "lxmanga"
    BASE = "https://lxmanga.org"
    domains = ["lxmanga.org"]
    referer = None                    # đã thử: cdn2.tymanga.com KHÔNG đòi Referer
    png_to_webp = True
    PROFILE = "lx-profile"            # profile Chromium riêng trong .reader-meta
    LABEL = "LXManga"
    SUFFIX = " [LX]"                  # chỉ bộ đánh số VỊ TRÍ (tuyển tập)
    COVER_PROXY = "https://i0.wp.com/"
    LIST_TIMEOUT_MS = 25_000          # chờ JS nạp danh sách chương
    LAYOUT_FAIL_LIMIT = 3             # số chương LIỀN không thấy khối ảnh -> dừng phiên

    _READ_JS = """() => {
      const q = s => document.querySelector(s);
      const og = q('meta[property="og:image"]'), ogt = q('meta[property="og:title"]');
      return {
        title: (q('h1.comic-title') || {}).textContent || '',
        og_title: ogt ? ogt.content : '',
        cover: og ? og.content : '',
        chapters: [...document.querySelectorAll('ul.chapter-list li a')]
                    .map(a => [a.href, (a.textContent || '').trim()]),
      };
    }"""
    _NUM_LABEL = re.compile(
        r"(?:chap(?:ter)?|ch\.|chương|chuong|phần|phan|tập|tap|\bc)\s*\.?\s*([0-9]+(?:[.,][0-9]+)?)",
        re.I)
    _NUM_SLUG = re.compile(r"(?:^|-)(?:chap|chapter|chuong|c)-?([0-9]+)(?:-([0-9]+))?(?=-|$)", re.I)
    _RAW = re.compile(r"\braw\b", re.I)

    def __init__(self):
        self.fetch_mode = "auto"      # mọi chế độ đều dùng trình duyệt (không có đường HTTP)
        self.allow_browser = True     # check_updates tắt -> ném Challenged, không mở Chromium
        self._browser = None
        self._series = {}             # slug -> {title, chapters, cover} (None nếu 404)
        self._num_cache = {}          # slug -> kết quả _numbered
        self._layout_fail = 0

    # -- trình duyệt --------------------------------------------------------------------

    def _get_browser(self):
        if self.fetch_mode == "http":
            print(f"  ({self.name} luôn lấy trang bằng trình duyệt — nhà mạng chặn HTTP, danh sách "
                  "chương nạp bằng JS — bỏ qua --fetch http)", file=sys.stderr)
            self.fetch_mode = "auto"
        if not self.allow_browser:
            raise Challenged("lxmanga cần trình duyệt (nhà mạng chặn HTTP, danh sách chương nạp "
                             "bằng JS) — job tải sẽ mở Chromium")
        if self._browser is None:
            import cf_browser    # lười: chỉ nạp Playwright khi thật sự cần
            host = urlparse(self.BASE).hostname or "lxmanga.org"
            b = cf_browser.CFBrowser(self.PROFILE, host, self.LABEL)
            b.open()
            self._browser = b
        return self._browser

    def close(self):
        """comic_downloader gọi trong finally -> không để Chromium mồ côi ôm profile."""
        if self._browser is not None:
            self._browser.close()
            self._browser = None

    def _debug_dump(self, name, html):
        """Lưu HTML trang không đọc được -> sửa parser nhanh khi site đổi giao diện."""
        try:
            d = META_DIR / "lx-debug"
            d.mkdir(parents=True, exist_ok=True)
            p = d / f"{re.sub(r'[^A-Za-z0-9_.-]+', '_', name)[:120]}.html"
            p.write_text(html or "", encoding="utf-8")
            return p
        except OSError:
            return None

    # -- trang bộ (DOM sau JS) -----------------------------------------------------------

    def _load_series(self, slug):
        if slug in self._series:
            return self._series[slug]
        b = self._get_browser()
        info = None
        if b.goto(f"{self.BASE}/{slug}.html"):
            page = b.page
            try:
                page.wait_for_selector("ul.chapter-list li a", timeout=self.LIST_TIMEOUT_MS)
            except Exception:
                pass                          # bộ rỗng / site đổi giao diện -> báo bên dưới
            info = page.evaluate(self._READ_JS)
            if not info.get("chapters"):
                p = self._debug_dump(f"{slug}-series", page.content())
                print(f"  ! {self.name}: không thấy danh sách chương (ul.chapter-list) — site đổi "
                      "giao diện?" + (f" HTML lưu tại {p}" if p else ""), file=sys.stderr)
        self._series[slug] = info
        return info

    def _number(self, url, label):
        m = self._NUM_LABEL.search(label or "")
        if m:
            return float(m.group(1).replace(",", "."))
        tail = re.sub(r"\.html?$", "", urlparse(url).path.rstrip("/").rsplit("/", 1)[-1], flags=re.I)
        m = self._NUM_SLUG.search(tail)
        if m:
            return float(m.group(1) + ("." + m.group(2) if m.group(2) else ""))
        return None

    def _numbered(self, slug):
        """(chapters đã đánh số [Chapter], positional: bool). Chưa lọc Raw. Nhớ theo slug
        (title_from_slug lẫn list_chapters đều cần -> cảnh báo không in 2 lần)."""
        if slug not in self._num_cache:
            self._num_cache[slug] = self._number_all(slug)
        return self._num_cache[slug]

    def _number_all(self, slug):
        info = self._load_series(slug)
        if not info:
            return [], False
        seen, items = set(), []           # (url, nhãn), mới nhất trước, bỏ link trùng/ngoài bộ
        for url, label in info.get("chapters") or []:
            if urlparse(url).path.startswith(f"/{slug}/") and url not in seen:
                seen.add(url)
                items.append((url, re.sub(r"\s+", " ", label).strip()))
        if not items:
            return [], False
        nums = [self._number(u, lb) for u, lb in items]
        known = [n for n in nums if n is not None]
        dup = len(known) - len(set(known))
        if len(items) == 1:
            return [Chapter(nums[0] if nums[0] is not None else 1.0, "", items[0][0])], False
        if None not in nums and dup <= max(0, len(items) // 20):
            out, taken = [], set()
            for (u, lb), n in zip(items, nums):   # trùng số lẻ tẻ: giữ bản MỚI nhất (đứng trước)
                if n in taken:
                    print(f"  ~ {self.name}: trùng số chương {fmt_num(n)} — bỏ bản cũ '{lb}'",
                          file=sys.stderr)
                    continue
                taken.add(n)
                out.append(Chapter(n, "", u))
            return out, False
        # tuyển tập: số trùng/thiếu -> số VỊ TRÍ, cũ nhất = 1, nhãn làm tên chương
        return [Chapter(float(i), lb, u) for i, (u, lb) in enumerate(reversed(items), 1)], True

    # -- hợp đồng provider -----------------------------------------------------------------

    def series_slug(self, text: str) -> str:
        t = re.split(r"[?#]", text.strip())[0]
        parts = [p for p in (urlparse(t).path if "://" in t else t).split("/") if p]
        if parts and "." in parts[0] and not re.search(r"\.html?$", parts[0], re.I):
            parts = parts[1:]             # 'lxmanga.org/slug.html' không có scheme
        return re.sub(r"\.html?$", "", parts[0], flags=re.I) if parts else ""

    def title_from_slug(self, slug: str) -> str:
        info = self._load_series(slug) or {}
        name = re.sub(r"\s+", " ", info.get("title") or "").strip()
        if not name:
            name = re.sub(r"^\s*(?:Đọc\s+)?Truyện\s+|\s+Tiếng Việt\s*$", "",
                          info.get("og_title") or "").strip()
        if not name:
            name = slug.replace("-", " ").title()
        return name + (self.SUFFIX if self._numbered(slug)[1] else "")

    def list_chapters(self, slug: str):
        chapters, positional = self._numbered(slug)
        if positional:
            print(f"  ~ {self.name}: bộ tuyển tập (số chương trùng/thiếu) — đánh SỐ VỊ TRÍ, "
                  f"folder hậu tố '{self.SUFFIX.strip()}'", file=sys.stderr)
        raw = [c for c in chapters if self._RAW.search(c.title or "")] if positional else []
        if not positional:
            labels = {u: lb for u, lb in (self._load_series(slug) or {}).get("chapters") or []}
            raw = [c for c in chapters if self._RAW.search(labels.get(c.ref, ""))]
        if raw:
            print(f"  ~ {self.name}: bỏ qua {len(raw)} chương Raw (chờ bản dịch): "
                  f"{', '.join(str(fmt_num(c.number)) for c in raw)}", file=sys.stderr)
        skip = {c.ref for c in raw}
        return sorted((c for c in chapters if c.ref not in skip), key=lambda c: c.number)

    def chapter_images(self, chapter):
        html = self._get_browser().get_html(chapter.ref) or ""
        i = html.find('id="viewer"')
        if i < 0:
            if html:
                self._layout_fail += 1
                p = self._debug_dump(urlparse(chapter.ref).path.strip("/"), html)
                print(f"  ! {self.name}: không thấy khối ảnh #viewer — site đổi giao diện?"
                      + (f" HTML lưu tại {p}" if p else ""), file=sys.stderr)
                if self._layout_fail >= self.LAYOUT_FAIL_LIMIT:
                    raise Blocked(f"{self.LABEL}: {self._layout_fail} chương liền không đọc được "
                                  "khối ảnh — site đổi giao diện")
            return []
        self._layout_fail = 0
        j = html.find("</section>", i)
        blk = html[i:j if j > 0 else len(html)]
        out, blocked = [], 0
        for tag in re.findall(r"<img\b[^>]*>", blk):
            m = re.search(r'\bdata-src="([^"]+)"', tag) or re.search(r'\bsrc="([^"]+)"', tag)
            if not m:
                continue
            u = html_lib.unescape(m.group(1)).strip()
            host = urlparse(u).hostname or ""
            if not u.startswith("http"):
                continue
            if host == "lxmanga.org" or host.endswith(".lxmanga.org"):
                blocked += 1              # host site: HTTP bị nhà mạng chặn -> không tải được
                continue
            if u not in out:
                out.append(u)
        if blocked:
            print(f"  ! {self.name}: {blocked} ảnh nằm trên lxmanga.org (HTTP bị chặn) — bỏ qua",
                  file=sys.stderr)
        return out

    def cover_url(self, slug: str):
        info = self._load_series(slug) or {}
        c = (info.get("cover") or "").strip()
        if not c.startswith("http"):
            return None
        p = urlparse(c)
        if p.hostname == "lxmanga.org" or (p.hostname or "").endswith(".lxmanga.org"):
            return f"{self.COVER_PROXY}{p.hostname}{p.path}?ssl=1"
        return c


# --- Đăng ký: thêm site mới = thêm 1 dòng vào đây -------------------------------
PROVIDERS = [AsuraProvider(), RavenProvider(), DilibProvider(), MangaDexProvider(),
             TruyenQQProvider(), ACGNProvider(), NetTruyenProvider(), ZetTruyenProvider(),
             TruyenQQVNProvider(), MoeTruyenProvider(), NHentaiToProvider(), HentaiFCProvider(),
             HentaiVNXProvider(), LXMangaProvider()]


def load_overrides() -> dict:
    """Đọc file override; trả {} nếu không có/hỏng. Dùng chung cho apply + provider_admin."""
    try:
        with open(OVERRIDE_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def _apply_overrides(providers):
    """Áp override lên INSTANCE trước khi dựng REGISTRY: nối domain, đổi BASE/referer.
    Cho phép đổi domain khi site xoay tên miền mà KHÔNG phải sửa code + push + /update.
    Định dạng: { "<name>": {"domains_add":[...], "base":"https://...", "referer":"..."} }.
    LƯU Ý: chỉ thêm domain là ĐỦ để nhận URL; site chống-hotlink (TruyenQQ/Zet) còn cần
    set 'base'+'referer' sang domain mới thì ảnh mới tải được (CDN kiểm referer theo domain)."""
    cfg = load_overrides()
    for p in providers:
        o = cfg.get(p.name)
        if not isinstance(o, dict):
            continue
        if o.get("base"):
            p.BASE = o["base"]
        if "referer" in o:                 # cho phép referer: null (bỏ referer)
            p.referer = o["referer"] or None
        add = [d.lower() for d in (o.get("domains_add") or []) if d]
        if add:
            p.domains = list(dict.fromkeys([*p.domains, *add]))


_apply_overrides(PROVIDERS)               # áp TRƯỚC khi dựng REGISTRY (gồm cả domain thêm)
by_name = {p.name: p for p in PROVIDERS}                 # tra theo cờ --site
REGISTRY = {d: p for p in PROVIDERS for d in p.domains}  # tra theo domain của URL
