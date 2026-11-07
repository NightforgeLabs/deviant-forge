#!/usr/bin/env python3
"""Download item pictures (weapons, armor, mods, deviations, food) for the Forge UI.

Source: oncehuman.th.gl, which publishes data and icons taken from the current
Once Human game files. Pictures are saved to static/icons/ and indexed in
gamedata/icons.json as {"<kind>": {"<item name>": "/icons/<file>"}}.
Only reads from the web; never touches the game install.

Usage: python3 tools/import_thgl_icons.py [--no-download]
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "static" / "icons"
INDEX = ROOT / "gamedata" / "icons.json"
BASE = "https://oncehuman.th.gl"
CDN = "https://cdn.th.gl/once-human/icons/"
UA = {"User-Agent": "Mozilla/5.0 (DeviantForge icon import)"}
CATS = {"gear": "gear", "mods": "mods", "deviations": "deviations", "consumables": "consumables", "materials": "materials"}
FANDOM_API = "https://once-human.fandom.com/api.php"
# app name -> name used by th.gl, when they differ
ALIASES = {"Frost Tactical": "Frost Tactical Vest", "Yellow Paint Mask": "Yellow Painted Mask"}
ENTRY = re.compile(r'\{"id":"([^"]+)","name":"([^"]+)"(?:,"groupId":"([^"]*)")?[^{}]*?"icon":\{"url":"([^"]+)"')


def get(url: str) -> bytes:
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception:
            if i == 2:
                raise
            time.sleep(2 * (i + 1))
    return b""


def entries(cat: str) -> list[tuple[str, str, str, str]]:
    page = get(f"{BASE}/db/{cat}").decode("utf-8", "replace")
    flat = page.replace('\\\\\\"', '"').replace('\\"', '"')
    seen, out = set(), []
    for m in ENTRY.finditer(flat):
        key = (m.group(1), m.group(4))
        if key not in seen:
            seen.add(key)
            out.append((m.group(1), html.unescape(m.group(2)), m.group(3) or "", m.group(4)))
    # also the server-rendered rows (same data, different markup)
    for m in re.finditer(r'href="/db/[a-z-]+/([^"]+)"><img[^>]*src="' + re.escape(CDN) + r'([^"]+)"[^>]*/><span class="min-w-0"><span[^>]*>([^<]+)<', page):
        key = (m.group(1), m.group(2))
        if key not in seen:
            seen.add(key)
            out.append((m.group(1), html.unescape(m.group(3)), "", m.group(2)))
    return out


def norm(name: str) -> str:
    return re.sub(r"\s*\(Tier \d\)$", "", name).strip()


def wanted() -> set[str]:
    """Only pictures the Forge shows: legendary gear, mods, deviations, key armor, food and drinks."""
    sys.path.insert(0, str(ROOT))
    import forge, forge_extras as fx  # noqa: E402
    gd = forge.gamedata()
    names = set(gd["weapons"]) | set(gd["armor"]) | {m["name"] for m in gd["mods"].values()}
    names |= set(getattr(fx, "MASK_HIDES", {})) | set(getattr(fx, "HIDE_ORIGIN", {}))
    names |= set(fx.KEY_ARMOR) | set(fx.FOODS) | set(fx.DRINKS) | {v.get("aka") for v in fx.FOODS.values() if v.get("aka")}
    return {n.lower() for n in names if n}


def main() -> int:
    download = "--no-download" not in sys.argv
    want = wanted()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index: dict[str, dict[str, str]] = {}
    for kind, cat in CATS.items():
        rows = entries(cat)
        bucket = index.setdefault(kind, {})
        for _id, name, group, rel in rows:
            n = norm(name)
            if not rel.endswith((".webp", ".png")):
                continue
            fname = rel.split("/")[-1]
            if n in bucket:
                continue
            bucket[n] = f"/icons/{fname}"
            keep = kind == "deviations" or (kind != "materials" and group == "oh_group_food") or n.lower() in want
            if not keep:
                bucket.pop(n, None); bucket.pop(n.lower(), None)
                continue
            if download and not (OUT_DIR / fname).exists():
                try:
                    (OUT_DIR / fname).write_bytes(get(CDN + rel))
                except Exception as e:  # keep going; the UI falls back to a letter tile
                    print("icon failed", n, e, file=sys.stderr)
        print(f"{kind}: {len(rows)} entries")
    # aliases, then the Fandom wiki for anything th.gl doesn't list (e.g. some key armor)
    have = {n.lower() for b in index.values() if isinstance(b, dict) for n in b}
    fb = index.setdefault("fallback", {})
    for app_name, thgl_name in ALIASES.items():
        for b in list(index.values()):
            if isinstance(b, dict) and thgl_name in b:
                fb[app_name] = b[thgl_name]; have.add(app_name.lower()); break
    sys.path.insert(0, str(ROOT))
    import forge_extras as fx  # noqa: E402
    need = set(fx.KEY_ARMOR) | set(getattr(fx, "MASK_HIDES", {})) | set(getattr(fx, "HIDE_ORIGIN", {}))
    for n in sorted(x for x in need if x.lower() not in have):
        try:
            q = urllib.parse.urlencode({"action": "query", "titles": n, "prop": "pageimages", "pithumbsize": 256,
                                        "format": "json", "redirects": 1})
            pages = json.loads(get(f"{FANDOM_API}?{q}"))["query"]["pages"].values()
            src = next(((p.get("thumbnail") or {}).get("source") for p in pages if p.get("thumbnail")), None)
            if not src:
                print("no picture anywhere for", n, file=sys.stderr); continue
            fname = "wiki_" + re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_") + ".png"
            if download and not (OUT_DIR / fname).exists():
                (OUT_DIR / fname).write_bytes(get(src))
            fb[n] = f"/icons/{fname}"
        except Exception as e:
            print("wiki picture failed", n, e, file=sys.stderr)
    index["_source"] = {"site": BASE, "note": "icons from oncehuman.th.gl (extracted from Once Human game files)",
                        "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    INDEX.write_text(json.dumps(index, indent=0, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
