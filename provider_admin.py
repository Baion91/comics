#!/usr/bin/env python3
"""Xem + quản lý DOMAIN/URL của provider qua file override (không sửa code).

Bot Telegram gọi script này (subprocess) cho lệnh /provider; in ra text tiếng Việt để
bot chuyển thẳng. Nguồn sự thật của phần người-dùng-thêm = .reader-meta/provider-domains.json;
providers.py ĐỌC file đó lúc import nên downloader/check_updates tự áp bản mới (KHÔNG cần
restart supervisor — mỗi job là tiến trình con mới).

    python provider_admin.py list
    python provider_admin.py add <name> <domain> [base] [referer]
    python provider_admin.py set <name> base|referer <value>
    python provider_admin.py del <name> <domain>
    python provider_admin.py clear <name>

LƯU Ý (in kèm khi thao tác site chống-hotlink): chỉ thêm domain là đủ để NHẬN link, nhưng
CDN ảnh của TruyenQQ/ZetTruyen kiểm Referer theo domain hiện hành -> phải set kèm base+referer
sang domain mới thì ảnh mới tải được. Và site đã bật Cloudflare "Verify you are human"
(challenge) thì thêm domain cũng vô ích (downloader requests-trần không qua được)."""

import json
import os
import sys

from providers import PROVIDERS, by_name, load_overrides, OVERRIDE_FILE

# comix không nằm trong PROVIDERS (browser, domain cố định) — hiển thị để đủ danh sách,
# nhưng KHÔNG cho sửa qua bot.
_COMIX_INFO = {"name": "comix", "domains": ["comix.to"], "base": "comix.to (browser)",
               "referer": None, "fixed": True}

HOTLINK = {"truyenqq", "zettruyen"}   # site CDN đòi referer -> nhắc set base+referer khi đổi


def _save_overrides(cfg: dict):
    os.makedirs(os.path.dirname(OVERRIDE_FILE), exist_ok=True)
    tmp = OVERRIDE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OVERRIDE_FILE)      # ghi nguyên tử


def _base_url(p):
    return getattr(p, "BASE", None) or getattr(p, "API", None) or "—"


def cmd_list():
    ov = load_overrides()
    lines = ["📚 Provider đang có (domain = link nhận diện; base = nơi tải trang):"]
    for p in PROVIDERS:
        o = ov.get(p.name) or {}
        added = {d.lower() for d in (o.get("domains_add") or [])}
        doms = " ".join(
            (d + " (thêm)") if d in added else d for d in p.domains)
        tag = " ✏️" if o else ""      # có override
        lines.append(f"\n• {p.name}{tag}")
        lines.append(f"   domain: {doms}")
        lines.append(f"   base: {_base_url(p)}   referer: {getattr(p, 'referer', None) or '—'}")
    c = _COMIX_INFO
    lines.append(f"\n• {c['name']}  (browser — domain cố định, không sửa qua bot)")
    lines.append(f"   domain: {' '.join(c['domains'])}")
    lines.append("\nSửa: /provider add <name> <domain> [base] [referer]"
                 " · /provider set <name> base|referer <url>"
                 " · /provider del <name> <domain> · /provider clear <name>")
    print("\n".join(lines))


def _check_name(name):
    if name == "comix" or name in _COMIX_INFO["name"]:
        sys.exit("⛔ comix dùng trình duyệt, domain cố định — không sửa qua bot.")
    if name not in by_name:
        sys.exit(f"⛔ Không có provider tên “{name}”. Đang có: "
                 f"{', '.join(sorted(by_name))}. Gõ /provider để xem.")


def _hotlink_note(name):
    return ("\n⚠️ Site này CDN đòi Referer theo domain — nhớ set cả base+referer sang domain "
            "mới thì ảnh mới tải được (và nếu site đã bật Cloudflare challenge thì thêm "
            "domain cũng không tải được).") if name in HOTLINK else ""


def cmd_add(argv):
    if len(argv) < 2:
        sys.exit("Cú pháp: /provider add <name> <domain> [base] [referer]")
    name, domain = argv[0], argv[1].lower().strip().strip("/")
    base = argv[2] if len(argv) > 2 else None
    referer = argv[3] if len(argv) > 3 else None
    _check_name(name)
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    ov = load_overrides()
    o = ov.setdefault(name, {})
    doms = o.setdefault("domains_add", [])
    p = by_name[name]
    if domain in [d.lower() for d in p.domains] and domain not in [d.lower() for d in doms]:
        # đã là domain GỐC trong code -> vẫn cho set base/referer nhưng báo rõ
        msg = f"ℹ️ “{domain}” vốn đã là domain gốc của {name}."
    elif domain in [d.lower() for d in doms]:
        msg = f"ℹ️ “{domain}” đã có trong danh sách thêm của {name}."
    else:
        doms.append(domain)
        msg = f"✅ Đã thêm domain “{domain}” cho {name}."
    if base:
        o["base"] = base if base.startswith("http") else "https://" + base
    if referer is not None:
        o["referer"] = referer if referer.startswith("http") else "https://" + referer
    _save_overrides(ov)
    extra = []
    if base:
        extra.append(f"base = {o['base']}")
    if referer is not None:
        extra.append(f"referer = {o['referer']}")
    print(msg + (("\n" + " · ".join(extra)) if extra else "") + _hotlink_note(name)
          + "\n(Có hiệu lực ngay cho lần tải/kiểm tiếp theo.)")


def cmd_set(argv):
    if len(argv) < 3 or argv[1] not in ("base", "referer"):
        sys.exit("Cú pháp: /provider set <name> base|referer <url>")
    name, field, value = argv[0], argv[1], argv[2]
    _check_name(name)
    if value.lower() in ("none", "null", "-") and field == "referer":
        value = None
    elif not value.startswith("http"):
        value = "https://" + value
    ov = load_overrides()
    ov.setdefault(name, {})[field] = value
    _save_overrides(ov)
    print(f"✅ Đã đặt {field} = {value} cho {name}." + _hotlink_note(name)
          + "\n(Có hiệu lực ngay cho lần tải/kiểm tiếp theo.)")


def cmd_del(argv):
    if len(argv) < 2:
        sys.exit("Cú pháp: /provider del <name> <domain>")
    name, domain = argv[0], argv[1].lower().strip().strip("/")
    _check_name(name)
    ov = load_overrides()
    o = ov.get(name) or {}
    doms = o.get("domains_add") or []
    if domain in [d.lower() for d in doms]:
        o["domains_add"] = [d for d in doms if d.lower() != domain]
        if not o["domains_add"]:
            o.pop("domains_add", None)
        if not o:
            ov.pop(name, None)
        _save_overrides(ov)
        print(f"✅ Đã xoá domain thêm “{domain}” khỏi {name}.")
    elif domain in [d.lower() for d in by_name[name].domains]:
        sys.exit(f"⛔ “{domain}” là domain GỐC trong code của {name} — không xoá qua bot "
                 f"được (muốn bỏ hẳn thì sửa providers.py + /update).")
    else:
        sys.exit(f"ℹ️ {name} không có domain thêm “{domain}”.")


def cmd_clear(argv):
    if not argv:
        sys.exit("Cú pháp: /provider clear <name>")
    name = argv[0]
    _check_name(name)
    ov = load_overrides()
    if ov.pop(name, None) is None:
        sys.exit(f"ℹ️ {name} chưa có override nào để xoá.")
    _save_overrides(ov)
    print(f"✅ Đã xoá toàn bộ override (domain thêm + base + referer) của {name} — về mặc định code.")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    argv = sys.argv[1:]
    sub = argv[0] if argv else "list"
    rest = argv[1:]
    if sub == "list":
        cmd_list()
    elif sub == "add":
        cmd_add(rest)
    elif sub == "set":
        cmd_set(rest)
    elif sub == "del":
        cmd_del(rest)
    elif sub == "clear":
        cmd_clear(rest)
    else:
        sys.exit(f"Lệnh con lạ: {sub}. Dùng: list | add | set | del | clear")


if __name__ == "__main__":
    main()
