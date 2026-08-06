#!/usr/bin/env python3
"""[Back-compat] Giữ lệnh cũ `python asura_downloader.py <slug|URL>` chạy như trước.

Toàn bộ logic đã dời sang: comics_core.py (động cơ) + providers.py (adapter Asura).
File này chỉ gọi CLI chung với provider Asura mặc định, nên gõ slug trần
(không có domain) vẫn hiểu là Asura như thói quen cũ.

Tool mới, đa site: python comic_downloader.py <URL>
"""

from comic_downloader import main
from providers import by_name

if __name__ == "__main__":
    main(default_provider=by_name["asura"])
