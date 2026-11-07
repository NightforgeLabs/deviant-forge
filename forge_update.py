"""The Update button: refresh game data, read patch notes, report what changed.

One run (start() -> background thread -> status()) does, in order:
  1. Official news  - new posts on oncehuman.game/news/update and /news/devBlog since the last run.
                      Lines that mention balance changes, new gear, new scenarios or items the app
                      knows are pulled out and tagged.
  2. Name lists     - every food and deviation th.gl lists. New names get a NEW! badge; th.gl has
                      no buff numbers for them, so they go on the "needs numbers" list.
  3. Game data      - (full mode) a fresh read of all weapons, armor and mods from oncehuman.th.gl
                      into a staging copy. It's checked (no big drops, few errors), the old copy is
                      backed up to data/live/history/, then it replaces the old one.
  4. Diff           - old vs new, in plain words ("MPS7 magazine 40 -> 30, 10 fewer bullets").
  5. Build impact   - best build, Starchrom plan and theory ranking before vs after.
  6. Log            - the report goes to data/live/updates.jsonl and seen.json (NEW! badges).

It changes data only. Model code (formulas, hand-written tables) still changes through
app updates. Nothing here reads or touches the game install or the game process.
"""
from __future__ import annotations

import datetime as dt
import html
import difflib
import json
import re
import shutil
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

import forge_live as fl

ROOT = Path(__file__).resolve().parent
NEWS_LISTS = ["https://www.oncehuman.game/news/update/", "https://www.oncehuman.game/news/devBlog/"]
POST_RE = re.compile(r'href="((?:https?:)?//www\.oncehuman\.game/news/(update|devBlog)/(\d{8})/\d+_\d+\.html|/news/(?:update|devBlog)/\d{8}/\d+_\d+\.html)"[^>]*?title="([^"]*)"')
UA = {"User-Agent": "Mozilla/5.0 (DeviantForge update check)"}
THGL = "https://oncehuman.th.gl"
FIRST_RUN_NEWS_DAYS = 45
MAX_POSTS = 12

_LOCK = threading.Lock()
JOB: dict = {"running": False}


def _tools():
    p = str(ROOT / "tools")
    if p not in sys.path:
        sys.path.insert(0, p)
    import import_thgl_gamedata as I  # noqa: E402
    import import_thgl_icons as IC  # noqa: E402
    return I, IC


def _get(url: str, timeout: int = 40) -> str:
    last = None
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"could not read {url}: {last}")


# ======================================================================= 1. news
def post_lines(page: str) -> tuple[str, list[str]]:
    b = re.sub(r"(?is)<(script|style).*?</\1>", "", page)
    b = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>|</tr>", "\n", b)
    b = html.unescape(re.sub(r"<[^>]+>", "", b))
    L = [re.sub(r"\s+", " ", x).strip() for x in b.split("\n")]
    L = [x for x in L if x]
    start = next((i for i, x in enumerate(L) if x.startswith("Dear Metas") or x.startswith("Dear ")), None)
    title = L[start - 1] if start else ""
    if start is None:
        return title, L[:200]
    end = next((i for i in range(start, len(L)) if L[i].startswith("Once Human Development Team")), len(L))
    return title, L[start:end]


def list_posts() -> list[dict]:
    out, seen = [], set()
    for u in NEWS_LISTS:
        page = _get(u)
        for m in re.finditer(r'href="([^"]*news/(update|devBlog)/(\d{8})/\d+_\d+\.html)"([^>]*)>', page):
            url = m.group(1)
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = "https://www.oncehuman.game" + url
            if url in seen:
                continue
            seen.add(url)
            t = re.search(r'title="([^"]*)"', m.group(4))
            d = m.group(3)
            out.append({"url": url, "kind": m.group(2), "date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                        "title": html.unescape(t.group(1)) if t else ""})
    out.sort(key=lambda p: p["date"], reverse=True)
    return out


BALANCE_VERB = re.compile(r"\b(increas|decreas|reduc|adjust|buff|nerf|rebalanc|optimi[sz]ed .*(?:DMG|damage)|now (?:deals|grants|has)|changed? (?:from|to)|from [+-]?\d)", re.I)
STAT_WORD = re.compile(r"\b(DMG|damage|Crit Rate|Crit DMG|Weakspot|magazine|fire rate|reload speed|Psi Intensity|Attack|Status DMG|Elemental DMG|Shrapnel|Burn|Frost Vortex|Power Surge|Unstable Bomber|Bounce|Fast Gunner|Bull's Eye|Fortress Warfare)\b", re.I)
JUNK_NAME = re.compile(r"\b(Added|Coming|Soon|Released|Launch(?:es|ed)?|Update|Details|Overview)\b|^(?:and|the|of)\b", re.I)
NEW_HEAD = re.compile(r"^(?:[IVX]+\.\s*|\d+\.\s*|•\s*|▪\s*)?(?:Brand[- ]new|New)\s+(Weapons?|Armor|Gear|Key Armor|Mods?|Deviations?|Deviants?|Scenario|Season|Food|Recipes?|Cradle|Calibration)\b[:\s-]*(.*)$", re.I)
SCN_RE = [re.compile(r"\[([A-Z][^\]\[]{2,40})\]\s*Scenario"),
          re.compile(r"(?:New|new)\s+(?:Survival\s+|PvE\s+|PvP\s+)?Scenario[:\s]+[\"“\[]?([A-Z][\w'’ ]{2,40}?)[\"”\]]?(?:\s+(?:Launches|is|will|arrives|coming)|[.,:!]|$)"),
          re.compile(r"(?:the\s+)?([A-Z][\w'’]+(?:\s+(?:of\s+|the\s+)?[A-Z][\w'’]+){0,3})\s+(?:Game Mode|Scenario|game mode)")]
CRADLE = re.compile(r"\bCradle\b(?!\s*(?:Charm|Skin|Cosmetic|Appearance))", re.I)
CRADLE_CTX = re.compile(r"overrid|bonus|effect|return|back|added|remov|mode|scenario|season|abyss|nightmare|dungeon", re.I)


def known_names(gd: dict) -> dict[str, str]:
    import forge_extras as fx
    import forge_effects as fe
    names: dict[str, str] = {}
    for n in gd["weapons"]:
        names[n] = "weapon"
        if " - " in n:
            names[n.split(" - ", 1)[1]] = "weapon"
    for m in gd["mods"].values():
        names[m["name"]] = "mod"
    for s in gd["sets"]:
        if len(s) >= 4:
            names[s] = "armor set"
    for n in fx.KEY_ARMOR:
        names[n] = "key armor (hand-written)"
    for n in fx.CONSUMABLES:
        names[n] = "food (hand-written)"
    for n in fx.DEVIATIONS:
        names[n] = "deviation (hand-written)"
    lists = fl.read_json(fl.NAMES, {})
    for n in (lists.get("consumables") or {}):
        names.setdefault(n, "food")
    for n in (lists.get("deviations") or {}):
        names.setdefault(n, "deviation")
    for k in fe.KEYWORDS:
        names[k] = "keyword"
    for c in fx.CLASSES.values():
        names[c["label"]] = "class"
    return {k: v for k, v in names.items() if len(k) >= 4}


def title_scenario(title: str) -> str | None:
    """'Dev Blog | New Survival Scenario Isles of Abyss Launches ...' -> 'Isles of Abyss'."""
    for r in SCN_RE[1:]:
        for m in r.finditer(title or ""):
            nm = m.group(1).strip()
            if nm and not re.search(r"\bNew\b|Once Human|^Survival$|^(?:the|this|a)$", nm, re.I):
                return nm
    return None


def analyse_post(title: str, lines: list[str], names: dict[str, str], known_scenarios: list[str] | None = None) -> dict:
    lower = {n.lower(): n for n in names}
    rx = re.compile(r"(?<![\w])(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?![\w])") if names else None
    compact = {fl.norm(n): n for n in names if len(fl.norm(n)) >= 10}   # 'Mist Core Clarity Soup' -> 'Mistcore Clarity Soup'
    t_scn = title_scenario(title)
    scn_names = sorted({*(known_scenarios or []), *([t_scn] if t_scn else [])}, key=len, reverse=True)
    highlights, announced, scenarios, cradle, found = [], [], [], False, []
    prev_new = False
    for i, ln in enumerate(lines):
        tags, hits = [], []
        if rx:
            hits = sorted({m.group(1) for m in rx.finditer(ln)})
        nln = fl.norm(ln)
        extra = sorted({n for c, n in compact.items() if c in nln and n not in hits})
        line_scn = t_scn or next((s for s in scn_names if s.lower() in ln.lower()), None)
        m = NEW_HEAD.match(ln)
        for h in hits + extra:
            if names.get(h) in ("keyword", "class"):
                continue
            if names.get(h) == "weapon" and " " not in h:      # lone gun suffix: 'Corrosion' in 'Corrosion Cannon'
                continue
            if re.search(r"(?<![\w])" + re.escape(h) + r"\s+-\s+[A-Z]", ln):   # 'Director Fox - Vacation' is a skin
                continue
            found.append({"name": h, "how": "announced" if (m or prev_new) else "named", "scenario": line_scn, "line": ln[:240]})
        prev_new = bool(m) and not (m.group(2) or "").strip()
        hits = sorted(set(hits) | set(extra))
        if m:
            tags.append("new " + m.group(1).lower().rstrip("s"))
            nm = m.group(2).strip(" :-")
            if not nm and i + 1 < len(lines) and len(lines[i + 1]) < 60 and not NEW_HEAD.match(lines[i + 1]):
                nm = lines[i + 1].strip()
            if nm and len(nm) < 60 and not JUNK_NAME.search(nm):
                announced.append({"name": nm, "kind": m.group(1).lower().rstrip("s"),
                                  "in_data": nm.lower() in lower or any(nm.lower() in k for k in lower)})
        if BALANCE_VERB.search(ln) and STAT_WORD.search(ln):
            tags.append("balance")
        for r in SCN_RE:
            for sm in r.finditer(ln):
                nm = sm.group(1).strip()
                if nm and nm.lower() not in ("the", "this", "new", "a") and nm not in scenarios \
                        and not re.search(r"\bNew\b|Once Human", nm):
                    scenarios.append(nm)
                    tags.append("scenario")
        if CRADLE.search(ln) and CRADLE_CTX.search(ln):
            cradle = True
            tags.append("cradle")
        if hits and not tags:
            tags.append("mentions")
        if tags:
            highlights.append({"text": ln[:600], "tags": sorted(set(tags)), "names": hits,
                               "hand_written": [h for h in hits if "hand-written" in names.get(h, "")]
                               if ("balance" in tags or any(t.startswith("new") for t in tags)) else []})
    for sm in SCN_RE[1:]:
        for m in sm.finditer(title):
            if m.group(1).strip() not in scenarios and not re.search(r"\bNew\b|Once Human|^Survival$", m.group(1).strip()):
                scenarios.append(m.group(1).strip())
    scenarios = [x for x in scenarios if not any(x != y and x in y for y in scenarios)]
    seen_a, ann = set(), []
    for a in announced:
        if a["name"].lower() not in seen_a:
            seen_a.add(a["name"].lower()); ann.append(a)
    for a in ann:   # announced on a 'New Deviation: Duet' line: strong evidence even if the name list lacks it
        found.append({"name": a["name"], "how": "announced", "scenario": t_scn, "line": ""})
    return {"highlights": highlights[:60], "announced": ann, "scenarios": scenarios[:6], "cradle": cradle,
            "title_scenario": t_scn, "found": found}


def check_news(gd: dict, log) -> dict:
    state = fl.read_json(fl.NEWS, {"seen": [], "checked_at": None})
    first = not state["seen"]
    posts = list_posts()
    cut = (dt.date.today() - dt.timedelta(days=FIRST_RUN_NEWS_DAYS)).isoformat()
    fresh = [p for p in posts if p["url"] not in state["seen"] and (not first or p["date"] >= cut)][:MAX_POSTS]
    names = known_names(gd)
    ev = fl.mentions()
    # evidence index missing (first run of 2026.11.05.2): re-read recent posts already seen, for evidence only
    backfill = [] if ev["posts"] else [p for p in posts if p["date"] >= cut and p not in fresh][:MAX_POSTS * 2]
    known_scn = sorted({v.get("scenario") for v in ev["posts"].values() if v.get("scenario")})
    out = []
    for p in sorted(backfill, key=lambda x: x["date"]) + fresh:
        log(f"reading “{p['title'][:70]}”" + (" (for patch-note evidence)" if p in backfill else ""))
        try:
            title, lines = post_lines(_get(p["url"]))
            a = analyse_post(title or p["title"], lines, names, known_scn)
            if a.get("title_scenario") and a["title_scenario"] not in known_scn:
                known_scn.append(a["title_scenario"])
            fl.add_mentions({**p, "title": title or p["title"], "scenario": a.get("title_scenario")}, a.pop("found"))
            if p in fresh:
                out.append({**p, **a, "lines": len(lines)})
        except Exception as exc:  # noqa: BLE001
            if p in fresh:
                out.append({**p, "error": str(exc)[:200], "highlights": [], "announced": [], "scenarios": []})
    state["seen"] = sorted(set(state["seen"]) | {p["url"] for p in posts if first or p in fresh} | {p["url"] for p in fresh})
    state["checked_at"] = fl.now()
    state["latest"] = posts[0] if posts else None
    return {"posts": out, "listed": len(posts), "first_run": first, "_state": state}


# ======================================================================= 2. names
def fetch_names(log) -> dict:
    I, _ = _tools()
    out = {"consumables": {}, "deviations": {}, "retrieved_at": fl.now()}
    ch = I.flight_payload(_get(f"{THGL}/db/consumables"))
    for cid, name, grp, text in re.findall(r'\{"id":"(\d+)","name":"([^"]+)","groupId":"(oh_group_food)","text":"([^"]*)"', ch):
        out["consumables"][html.unescape(name)] = {"id": cid, "text": text}
    ch = I.flight_payload(_get(f"{THGL}/db/deviations"))
    for name, url in re.findall(r'\{"@type":"ListItem","position":\d+,"name":"([^"]+)","url":"(https://oncehuman\.th\.gl/db/deviations/\d+)"\}', ch):
        out["deviations"][html.unescape(name)] = {"url": url}
    log(f"{len(out['consumables'])} foods and {len(out['deviations'])} deviations listed on th.gl")
    return out


def deviation_text(url: str) -> str:
    I, _ = _tools()
    L = I.text_lines(_get(url))
    if "Abilities" in L:
        i = L.index("Abilities")
        end = next((k for k in range(i, len(L)) if L[k] in ("Lore", "Sources", "Details")), i + 8)
        return " ".join(L[i + 1:end])[:700]
    return ""


# ======================================================================= 3/4. game data diff
def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _g(x) -> str:
    return f"{x:g}" if isinstance(x, float) else str(x)


def num_change(label: str, o, n, unit: str = "", word: tuple[str, str] | None = None) -> str | None:
    o, n = _f(o), _f(n)
    if o is None and n is None or o == n:
        return None
    if o is None or n is None:
        return f"{label}: {'—' if o is None else _g(o)} → {'—' if n is None else _g(n)}{unit}"
    d = n - o
    rel = f", {d / o * 100:+.1f}%" if o else ""
    if word:
        return f"{label} {_g(o)} → {_g(n)}{unit} ({_g(abs(d))} {word[0] if d > 0 else word[1]}{rel})"
    return f"{label} {_g(o)} → {_g(n)}{unit} ({'+' if d > 0 else '−'}{_g(abs(d))}{rel})"


NUM_IN_TEXT = re.compile(r"[+-]?\d+(?:\.\d+)?%?")


# th.gl appends crafting / unlock / obtain boilerplate to effect text; its wording changes don't matter
BOILER = re.compile(r"\s*(Crafted (from|In)\b|Unlock(ed)? By\b|Details Obtain\b|Obtain from\b).*$", re.S)


def clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", BOILER.sub("", t or "")).strip()


def _changed_part(o: str, n: str) -> tuple[str, str]:
    """Just the differing stretch of two texts, with a few words of context."""
    sm = difflib.SequenceMatcher(None, o, n)
    ops = [op for op in sm.get_opcodes() if op[0] != "equal"]
    i1, i2, j1, j2 = ops[0][1], ops[-1][2], ops[0][3], ops[-1][4]
    pre = max(0, min(i1, j1) - 40)
    cut = lambda t, a, b: ("…" if a > 0 else "") + t[a:b + 40].strip() + ("…" if b + 40 < len(t) else "")
    return cut(o, pre, i2), cut(n, pre, j2)


def text_change(label: str, o: str, n: str) -> list[str]:
    o, n = clean_text(o), clean_text(n)
    if o == n:
        return []
    a, b = NUM_IN_TEXT.findall(o), NUM_IN_TEXT.findall(n)
    if a and len(a) == len(b) and NUM_IN_TEXT.sub("#", o) == NUM_IN_TEXT.sub("#", n):
        return [f"{label}: " + ", ".join(f"{x} → {y}" for x, y in zip(a, b) if x != y) + f" (now: “{n[:220]}”)"]
    if not o:
        return [f"{label} added: “{n[:260]}”"]
    if not n:
        return [f"{label} removed (was “{o[:200]}”)"]
    a, b = _changed_part(o, n)
    return [f"{label} reworded. Before: “{a[:260]}” After: “{b[:260]}”"]


def weapon_lines(o: dict, n: dict) -> list[str]:
    out = [num_change("Magazine", o.get("magazine"), n.get("magazine"), "", ("more bullets", "fewer bullets")),
           num_change("Base damage", o.get("dmg"), n.get("dmg")),
           num_change("Fire rate", o.get("fire_rate_rpm"), n.get("fire_rate_rpm"), " rpm"),
           num_change("Crit Rate", o.get("crit_rate_pct"), n.get("crit_rate_pct"), "%"),
           num_change("Crit DMG", o.get("crit_dmg_pct"), n.get("crit_dmg_pct"), "%"),
           num_change("Weakspot DMG", o.get("weakspot_dmg_pct"), n.get("weakspot_dmg_pct"), "%"),
           num_change("Reload speed", o.get("reload_speed"), n.get("reload_speed"))]
    os_, ns = o.get("dmg_per_star") or {}, n.get("dmg_per_star") or {}
    top = max([int(k) for k in set(os_) & set(ns)] or [0])
    if top and _f(os_.get(str(top))) != _f(ns.get(str(top))) and _f(o.get("dmg")) == _f(n.get("dmg")):
        out.append(num_change(f"Damage at {top}★", os_.get(str(top)), ns.get(str(top))))
    if o.get("type") != n.get("type"):
        out.append(f"Weapon type {o.get('type')} → {n.get('type')}")
    out += text_change("Weapon effect", o.get("effect_text", ""), n.get("effect_text", ""))
    return [x for x in out if x]


def armor_lines(o: dict, n: dict) -> list[str]:
    out = [num_change("Psi Intensity", o.get("psi_intensity"), n.get("psi_intensity")),
           num_change("HP", o.get("hp"), n.get("hp"))]
    oe, ne = o.get("set_effects") or {}, n.get("set_effects") or {}
    for k in sorted(set(oe) | set(ne), key=str):
        out += text_change(f"{k}-piece effect", str(oe.get(k, "")), str(ne.get(k, "")))
    return [x for x in out if x]


def mod_lines(o: dict, n: dict) -> list[str]:
    oc, nc = o.get("core_effect_by_level") or {}, n.get("core_effect_by_level") or {}
    top = max([int(k) for k in nc] or [0])
    out = text_change(f"Effect (level {top})" if top else "Effect",
                      oc.get(str(top), o.get("summary", "")), nc.get(str(top), n.get("summary", "")))
    ot, nt = o.get("substat_values_by_tier") or {}, n.get("substat_values_by_tier") or {}
    for k in sorted(set(ot) & set(nt)):
        if ot[k] != nt[k]:
            out.append(f"{k[:50]} rolls {ot[k][-1] if ot[k] else '—'} → {nt[k][-1] if nt[k] else '—'} (top grade)")
    if (o.get("slot") or "") != (n.get("slot") or ""):
        out.append(f"Slot {o.get('slot')} → {n.get('slot')}")
    return out


KIND_WORD = {"weapons": "Weapon", "armor": "Armor", "mods": "Mod"}


def diff_snapshots(old: dict, new: dict) -> dict:
    changes, added, removed = [], [], []
    for kind, fn in (("weapons", weapon_lines), ("armor", armor_lines), ("mods", mod_lines)):
        o = {x["name"]: x for x in old.get(kind) or []}
        n = {x["name"]: x for x in new.get(kind) or []}
        for name in sorted(set(n) - set(o)):
            added.append({"kind": KIND_WORD[kind], "name": name, "url": n[name].get("source_url")})
        for name in sorted(set(o) - set(n)):
            removed.append({"kind": KIND_WORD[kind], "name": name})
        for name in sorted(set(o) & set(n)):
            ln = fn(o[name], n[name])
            if ln:
                changes.append({"kind": KIND_WORD[kind], "name": name, "lines": ln, "url": n[name].get("source_url")})
    return {"changes": changes, "added": added, "removed": removed}


def validate(old: dict, new: dict) -> tuple[bool, str]:
    for k in ("weapons", "armor", "mods"):
        a, b = len(old.get(k) or []), len(new.get(k) or [])
        if a and b < 0.8 * a:
            return False, f"th.gl returned only {b} {k} (was {a}). That looks like a site problem, so the old data was kept."
    jobs = sum(len(new.get(k) or []) for k in ("weapons", "armor", "mods")) + len(new.get("errors") or [])
    errs = len(new.get("errors") or [])
    if errs > max(8, 0.05 * jobs):
        return False, f"{errs} of {jobs} item pages failed to load. The old data was kept; try again later."
    return True, ""


def carry_over(old: dict, new: dict) -> list[str]:
    """Items whose page failed this time keep their previous values instead of disappearing."""
    kept = []
    blob = json.dumps(new.get("errors") or [])
    for k in ("weapons", "armor", "mods"):
        have = {x["name"] for x in new.get(k) or []}
        for x in old.get(k) or []:
            if x["name"] not in have and (x["name"] in blob or str(x.get("id", "")) in blob):
                new[k].append({**x, "carried_over": True})
                kept.append(x["name"])
    return kept


def backup_and_swap(new: dict) -> str:
    fl.HIST.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    cur = fl.active_snapshot()
    if cur == fl.LIVE_SNAP:
        shutil.copy2(cur, fl.HIST / f"{ts}-before.json")
    else:
        (fl.HIST / f"{ts}-before.shipped").write_text(str(cur))
    fl.write_json(fl.LIVE_SNAP, new)
    olds = sorted(fl.HIST.glob("*-before.*"))
    for p in olds[:-10]:
        p.unlink(missing_ok=True)
    return ts


def rollback() -> dict:
    with _LOCK:
        if JOB.get("running"):
            raise RuntimeError("an update is running")
        olds = sorted(fl.HIST.glob("*-before.*")) if fl.HIST.exists() else []
        if not olds:
            raise RuntimeError("nothing to undo")
        last = olds[-1]
        if last.suffix == ".shipped":
            fl.LIVE_SNAP.unlink(missing_ok=True)
        else:
            shutil.copy2(last, fl.LIVE_SNAP)
        last.unlink()
    import forge
    forge.reload_data()
    entry = {"id": dt.datetime.now().strftime("%Y%m%d-%H%M%S"), "kind": "undo", "finished": fl.now(),
             "summary": [f"Undid the last data refresh. Game data is back to {fl.snapshot_date(fl.active_snapshot())[:16]}."]}
    _append_log(entry)
    return entry


# ======================================================================= icons
def fetch_icons(names: set[str], log) -> int:
    if not names:
        return 0
    _, IC = _tools()
    import forge
    have = forge.icon_map()
    want = {n for n in names if n not in have and n.lower() not in have}
    if not want:
        return 0
    ix = fl.read_json(fl.ICON_INDEX, {})
    fl.ICON_DIR.mkdir(parents=True, exist_ok=True)
    got = 0
    for cat in ("gear", "mods", "deviations", "consumables"):
        try:
            rows = IC.entries(cat)
        except Exception:  # noqa: BLE001
            continue
        for _id, name, _grp, url in rows:
            nm = IC.norm(name)
            if nm not in want:
                continue
            if not url.endswith((".webp", ".png")):
                continue
            fn = url.split("/")[-1]
            try:
                if not (fl.ICON_DIR / fn).exists():
                    (fl.ICON_DIR / fn).write_bytes(IC.get(IC.CDN + url))
                ix[nm] = f"/live-icons/{fn}"
                got += 1
                want.discard(nm)
            except Exception:  # noqa: BLE001
                pass
    fl.write_json(fl.ICON_INDEX, ix)
    log(f"downloaded {got} new pictures")
    return got


# ======================================================================= 5. build impact
def snapshot_of_builds() -> dict:
    import forge
    import forge_theory
    prof = forge.load_profile()
    r = forge.optimize(prof)
    b = r.get("best") or {}
    scn = prof.get("scenario") or "boss"
    try:
        t = forge_theory.theory(scn, top_n=5)
        top = [{"weapon": x["weapon"]["name"], "dps": round(x["dps"])} for x in (t.get("builds") or [])[:5]]
    except Exception:  # noqa: BLE001
        top = []
    return {"best": {"weapon": (b.get("weapon") or {}).get("name"), "dps": round(b.get("dps") or 0),
                     "sets": b.get("sets") or {}},
            "upgrades": [{"title": u.get("title"), "gain": round(u.get("gain_pct") or 0, 1), "cost": u.get("cost_starchrom")}
                         for u in (r.get("upgrades") or [])[:5]],
            "weapon_dps": {k: round(v.get("dps") or 0) for k, v in (r.get("weapon_dps") or {}).items()},
            "theory": top, "scenario": scn}


def impact_lines(a: dict, b: dict, added_weapons: list[str]) -> list[str]:
    out = []
    ab, bb = a["best"], b["best"]
    if ab["weapon"] != bb["weapon"]:
        out.append(f"Your best build changed: {ab['weapon']} ({ab['dps']:,} DPS) → {bb['weapon']} ({bb['dps']:,} DPS).")
    elif ab["dps"] != bb["dps"]:
        d = (bb["dps"] / ab["dps"] - 1) * 100 if ab["dps"] else 0
        out.append(f"Your best build ({bb['weapon']}) went {ab['dps']:,} → {bb['dps']:,} estimated DPS ({d:+.1f}%).")
    else:
        out.append(f"Your best build is unchanged ({bb['weapon']}, {bb['dps']:,} estimated DPS).")
    at, bt = [x["weapon"] for x in a["theory"]], [x["weapon"] for x in b["theory"]]
    if bt and at != bt:
        out.append("The strongest-possible ranking moved: " + ", ".join(f"#{i + 1} {w}" for i, w in enumerate(bt[:3])) +
                   (f" (was {', '.join(at[:3])})." if at else "."))
    au, bu = [u["title"] for u in a["upgrades"]], [u["title"] for u in b["upgrades"]]
    if bu and au[:1] != bu[:1]:
        out.append(f"Your top Starchrom pick is now: {bu[0]}.")
    best = bb["dps"] or 1
    for w in added_weapons:
        d = b["weapon_dps"].get(w)
        if d:
            out.append(f"New weapon {w}: about {d:,} DPS with your gear at 1★ ({(d / best - 1) * 100:+.0f}% vs your best).")
    return out


# ======================================================================= the run
def _append_log(entry: dict) -> None:
    fl.LOG.parent.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in entry.items() if k != "_state"}
    with fl.LOG.open("a") as f:
        f.write(json.dumps(slim, ensure_ascii=False) + "\n")
    fl.write_json(fl.LIVE / "last_report.json", slim)


def run(mode: str = "full", progress=None, delay: float = 0.3, limit: int = 0) -> dict:
    import forge
    progress = progress or (lambda pct, msg: None)
    log_msgs: list[str] = []

    def log(msg):
        log_msgs.append(msg)
        progress(None, msg)

    rep = {"id": dt.datetime.now().strftime("%Y%m%d-%H%M%S"), "kind": "update", "mode": mode, "started": fl.now(),
           "app_version": fl.APP_VERSION, "errors": [], "summary": []}
    gd = forge.gamedata()
    rep["data_before"] = gd.get("retrieved_at")
    progress(2, "working out your current best build")
    before = snapshot_of_builds()

    # 1 news
    progress(5, "reading official patch notes")
    try:
        news = check_news(gd, log)
        fl.write_json(fl.NEWS, news.pop("_state"))
        rep["news"] = news
    except Exception as exc:  # noqa: BLE001
        rep["errors"].append(f"Patch notes: {exc}")
        rep["news"] = {"posts": []}

    # 2 names
    progress(10, "checking th.gl for new foods and deviations")
    names_before = fl.read_json(fl.NAMES, {})
    try:
        names = fetch_names(log)
        fl.write_json(fl.NAMES, names)
    except Exception as exc:  # noqa: BLE001
        rep["errors"].append(f"th.gl name lists: {exc}")
        names = names_before

    # 3/4 game data
    swapped, diff, new_weapons = False, {"changes": [], "added": [], "removed": []}, []
    if mode == "full":
        I, _ = _tools()
        progress(12, "reading every weapon, armor piece and mod from th.gl")
        try:
            new = I.build_snapshot(limit=limit, delay=delay,
                                   progress=lambda n, t, m: progress(12 + int(70 * n / max(t, 1)), f"{m} {n}/{t}"))
            new = json.loads(json.dumps(new, default=str))  # same key types as the saved copy
            old = json.loads(fl.active_snapshot().read_text())
            kept = carry_over(old, new)
            ok, why = validate(old, new) if not limit else (True, "")
            diff = diff_snapshots(old, new)
            if ok and limit:
                ok, why = False, "test run with a limit; data not replaced"
            if ok:
                rep["backup"] = backup_and_swap(new)
                swapped = True
                forge.reload_data()
            else:
                rep["errors"].append(why)
            rep["carried_over"] = kept
            new_weapons = [a["name"] for a in diff["added"] if a["kind"] == "Weapon"]
        except Exception as exc:  # noqa: BLE001
            rep["errors"].append(f"Game data refresh: {exc}")
            import traceback
            log(f"game data refresh failed: {traceback.format_exc()[-1500:]}")
    rep["swapped"] = swapped
    rep.update(diff)

    # NEW! badges
    gd2 = forge.gamedata()
    added_keys = fl.mark_seen(gd2, "update button", names)   # lists read for the first time = baseline
    cls = fl.classify()
    rep["new_keys"] = added_keys
    rep["confirmed_new"] = [k for k in added_keys if k in cls["new"]]
    rep["data_only"] = [k for k in added_keys if k in cls["data"]]
    rep["data_after"] = gd2.get("retrieved_at")

    # foods / deviations without numbers
    import forge_extras as fx
    need = []
    for k in rep["confirmed_new"]:
        kind, _, name = k.partition(":")
        if kind == "food" and name not in fx.CONSUMABLES:
            need.append({"kind": "food", "name": name, "text": (names.get("consumables") or {}).get(name, {}).get("text", "")})
        elif kind == "deviation" and name not in fx.DEVIATIONS:
            url = (names.get("deviations") or {}).get(name, {}).get("url", "")
            txt = ""
            if url:
                try:
                    txt = deviation_text(url)
                except Exception:  # noqa: BLE001
                    pass
            need.append({"kind": "deviation", "name": name, "text": txt, "url": url})
    have = {(x["kind"], x["name"]) for x in need}
    for p in (rep["news"].get("posts") or []):
        for a in p.get("announced") or []:
            kind = {"deviation": "deviation", "deviant": "deviation", "food": "food", "recipe": "food"}.get(a["kind"])
            nm = a["name"]
            if not kind or (kind, nm) in have or nm in fx.DEVIATIONS or nm in fx.CONSUMABLES:
                continue
            url = (names.get("deviations") or {}).get(nm, {}).get("url", "") if kind == "deviation" else ""
            txt = ""
            if url:
                try:
                    txt = deviation_text(url)
                except Exception:  # noqa: BLE001
                    pass
            need.append({"kind": kind, "name": nm, "text": txt, "url": url, "post": p.get("title"), "post_url": p.get("url")})
            have.add((kind, nm))
    rep["needs_numbers"] = need

    # pictures for anything new
    progress(85, "fetching pictures for new items")
    try:
        fetch_icons({k.partition(":")[2] for k in added_keys}, log)
        forge.icon_map.cache_clear()
    except Exception as exc:  # noqa: BLE001
        rep["errors"].append(f"Pictures: {exc}")

    # 5 impact
    progress(90, "re-running your builds")
    after = snapshot_of_builds()
    rep["impact"] = {"before": before, "after": after, "lines": impact_lines(before, after, new_weapons)}
    for b in (before, after):
        b.pop("weapon_dps", None)

    # summary in plain words
    S = rep["summary"]
    posts = rep["news"].get("posts") or []
    S.append(f"{len(posts)} new official post{'s' if len(posts) != 1 else ''} read." if posts else "No new official posts since the last check.")
    if mode == "full":
        if swapped:
            S.append(f"Game data refreshed from th.gl: {len(diff['changes'])} items changed, {len(diff['added'])} added, {len(diff['removed'])} gone.")
        else:
            S.append("Game data was not replaced (see problems below).")
    else:
        S.append("Quick check: game numbers were not re-read. Use the full check to catch stat changes.")
    nc, nd = len(rep["confirmed_new"]), len(rep["data_only"])
    if nc:
        S.append(f"{nc} new item{'s' if nc != 1 else ''} named in official patch notes, marked NEW!.")
    if nd:
        S.append(f"{nd} more showed up on th.gl without any patch-note mention. They're listed apart (probably older items th.gl just added), no NEW! badge.")
    if need:
        S.append(f"{len(need)} new food/deviation entr{'ies need' if len(need) != 1 else 'y needs'} numbers before they count.")
    scn = sorted({x for p in posts for x in p.get("scenarios") or []})
    if scn:
        S.append("Scenarios named in the posts: " + ", ".join(scn) + ". Set one up under Custom fights to plan for it.")
    if any(p.get("cradle") for p in posts):
        S.append("A post mentions the Cradle. Check your map in Class & settings: the app counts Cradle overrides only on maps that have one, and you can type your tooltip values there.")
    hw = sorted({h for p in posts for x in p.get("highlights") or [] for h in x.get("hand_written") or []})
    if hw:
        S.append("Hand-written items mentioned in patch notes (numbers may be out of date): " + ", ".join(hw) + ".")
    S += rep["impact"]["lines"]
    rep["finished"] = fl.now()
    rep["log"] = log_msgs[-40:]
    rep["ok"] = not rep["errors"]
    _append_log(rep)
    progress(100, "done")
    return rep


def start(mode: str = "full") -> dict:
    with _LOCK:
        if JOB.get("running"):
            return status()
        JOB.clear()
        JOB.update({"running": True, "mode": mode, "pct": 0, "msg": "starting", "started": fl.now(), "report": None})

    def prog(pct, msg):
        if pct is not None:
            JOB["pct"] = pct
        JOB["msg"] = msg

    def work():
        try:
            JOB["report"] = run(mode, prog)
        except Exception as exc:  # noqa: BLE001
            JOB["error"] = f"{exc}"
            JOB["trace"] = traceback.format_exc()[-1500:]
        finally:
            JOB["running"] = False
            JOB["pct"] = 100
    threading.Thread(target=work, daemon=True).start()
    return status()


def status() -> dict:
    out = {k: v for k, v in JOB.items() if k != "trace"}
    if not out.get("report"):
        out["report"] = fl.read_json(fl.LIVE / "last_report.json", None)
    return out


# ======================================================================= handoff
def _fight_label(key) -> str:
    key = key or "boss"
    try:
        import forge  # noqa: F401  (applies custom fights)
        import forge_effects as fe
        sc = fe.scn(key)
        return f"{sc.get('label') or key}" + (f" (custom, base {sc.get('base')})" if sc.get("custom") else "")
    except Exception:  # noqa: BLE001
        return str(key)


def handoff_text() -> str:
    """A paste-able status note so a new Computer session can pick up without starting over."""
    import forge
    info = forge.data_info()
    prof = forge.load_profile()
    ex = prof.get("extras") or {}
    try:
        inv = forge.inventory(prof)
    except Exception:  # noqa: BLE001
        inv = {}
    try:
        r = forge.optimize(prof)
        b = r.get("best") or {}
        best = f"{(b.get('weapon') or {}).get('name')} · {round(b.get('dps') or 0):,} est. DPS · sets {b.get('sets')}"
        ups = [f"{u['title']} ({u['gain_pct']:+.1f}%, {u.get('cost_starchrom') or 0:,} Starchrom)" for u in (r.get('upgrades') or [])[:3]]
    except Exception as exc:  # noqa: BLE001
        best, ups = f"(could not compute: {exc})", []
    last = fl.read_json(fl.LIVE / "last_report.json", None) or {}
    s = fl.seen()
    o = fl.overrides()
    L = ["# Deviant Forge status for Computer",
         "Paste this into a Computer chat in the Deviant Forge project. The full handoff is in the app folder: docs/FORGE_HANDOFF.md.",
         "",
         "## App and data",
         f"- App version: {info['app_version']} (folder ~/Projects/once-human-advisor, service deviant-forge.service, http://127.0.0.1:8765)",
         f"- Game data from th.gl: {str(info['retrieved_at'])[:16]} ({'refreshed by the Update button' if info['refreshed'] else 'the copy shipped with the app'})",
         f"- Last update check: {info.get('last_check') or 'never'}",
         f"- Newest official post seen: {(info.get('latest_post') or {}).get('date', '—')} {(info.get('latest_post') or {}).get('title', '')}",
         "",
         "## Player",
         f"- Class {ex.get('class') or 'not set (Freelancer default)'} · deviation {ex.get('deviation') or 'not set'} · fight {_fight_label(prof.get('scenario'))} · play style {ex.get('effort') or 'normal'}",
         f"- {len(inv.get('weapons') or prof.get('weapons') or [])} weapons, {len(inv.get('mods') or prof.get('mods') or [])} mods recorded · Psi {prof.get('psi_intensity') or 'not typed (app estimates it)'} · Starchrom {prof.get('starchrom') or 0:,}",
         f"- Best build now: {best}"]
    L += [f"- Next pick: {u}" for u in ups]
    if last:
        L += ["", f"## Last update report ({last.get('finished', '')[:16]})"] + [f"- {x}" for x in last.get("summary") or []]
        for c in (last.get("changes") or [])[:15]:
            L.append(f"- {c['kind']} {c['name']}: " + "; ".join(c["lines"])[:300])
        for e in last.get("errors") or []:
            L.append(f"- Problem: {e}")
        nn = last.get("needs_numbers") or []
        if nn:
            L += ["", "## New items with no numbers yet"] + [f"- {x['kind']}: {x['name']} — {x.get('text', '')[:160]}" for x in nn]
    typed = [(k, n, v) for k in ("consumables", "deviations") for n, v in o[k].items()]
    if typed:
        L += ["", "## Typed in by the player (please verify and move into the hand-written tables)"]
        L += [f"- {k[:-1]}: {n} — “{v.get('text', '')}”" for k, n, v in typed]
    if o["scenarios"]:
        L += ["", "## Custom fights"] + [f"- {v.get('name', k)} (base {v.get('base', 'boss')}): buffs “{v.get('buff_text', '')}” {v.get('note', '')}" for k, v in o["scenarios"].items()]
    vs = s.get("verdicts") or {}
    if vs:
        word = {"not_new": "says NOT new", "wrong": "says WRONG", "cool": "likes it"}
        L += ["", "## Player's checks on NEW! items"] + [f"- {k}: {word.get(v['verdict'], v['verdict'])}{(' — ' + v['note']) if v.get('note') else ''}" for k, v in vs.items()]
    L += ["", "## House rules", "- Workspace 10 is Once Human: never launch, move, focus or send input there.",
          "- Never modify game files or touch the game process.",
          "- Best-build numbers are estimates with a 'not counted' list.", "- Update packages never include data/."]
    return "\n".join(L)
