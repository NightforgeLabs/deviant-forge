"""Live data layer for Deviant Forge.

Everything the in-app Update button writes lives in data/live/ (player-side, never
shipped in update packages), so installing a new app version never wipes a newer
data refresh, the player's typed-in items, custom fights or NEW! badge history.

  data/live/thgl_snapshot.json  refreshed th.gl game data (used when newer than the shipped one)
  data/live/history/            backups of every snapshot that was replaced (for Undo)
  data/live/overrides.json      items the game data has no numbers for, typed in by the player
                                {"consumables": {}, "deviations": {}, "scenarios": {}}
  data/live/seen.json           first-seen date per item, per-source baselines, player verdicts
  data/live/mentions.json       which official post names which item (evidence for NEW! and scenario labels)
  data/live/names.json          th.gl name lists for foods and deviations
  data/live/news.json           official posts already read
  data/live/updates.jsonl       one line per update run (the change report)
  data/live/icons/, icons.json  pictures for items added after the app was packaged

This module never imports forge.py (forge imports it).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

import forge_effects as fe
import forge_extras as fx

def _read_version() -> str:
    try:
        return (Path(__file__).resolve().parent / "VERSION").read_text().strip()
    except OSError:
        return "unknown"


APP_VERSION = _read_version()  # one VERSION file in the app folder; shown in the sidebar and on Updates
ROOT = Path(__file__).resolve().parent
SHIPPED = ROOT / "gamedata" / "thgl_snapshot.json"
LIVE = Path(os.environ.get("OH_ADVISOR_DATA", ROOT / "data")).resolve() / "live"
LIVE_SNAP = LIVE / "thgl_snapshot.json"
HIST = LIVE / "history"
OVERRIDES = LIVE / "overrides.json"
SEEN = LIVE / "seen.json"
NAMES = LIVE / "names.json"
NEWS = LIVE / "news.json"
LOG = LIVE / "updates.jsonl"
ICON_DIR = LIVE / "icons"
ICON_INDEX = LIVE / "icons.json"
NEW_DAYS = 21          # a NEW! badge shows for this many days after an item first appears

BASES = ("boss", "abyss", "mobs")


def today() -> str:
    return dt.date.today().isoformat()


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return default


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(p)


# ------------------------------------------------------------------ game data file
def snapshot_date(p: Path) -> str:
    try:
        with p.open() as f:
            head = f.read(4000)
        m = re.search(r'"retrieved_at":\s*"([^"]+)"', head)
        return m.group(1) if m else ""
    except OSError:
        return ""


def active_snapshot() -> Path:
    """The refreshed copy if it's at least as new as the one shipped with the app."""
    if LIVE_SNAP.exists() and snapshot_date(LIVE_SNAP) >= snapshot_date(SHIPPED):
        return LIVE_SNAP
    return SHIPPED


# ------------------------------------------------------------------ typed-in items
def parse_buff(text: str) -> tuple[dict, list[str]]:
    """'Status DMG +25% at full Sanity' -> ({'status_dmg': 25.0}, [unparsed bits])."""
    p = fe.parse_effect(text or "", fe.scn("boss"), {})
    stats: dict[str, float] = {}
    for c in p.contributions:
        if not c.stat.startswith("_"):
            stats[c.stat] = stats.get(c.stat, 0.0) + float(c.raw)
    return stats, list(p.unmodeled)


def overrides() -> dict:
    o = read_json(OVERRIDES, {})
    for k in ("consumables", "deviations", "scenarios"):
        o.setdefault(k, {})
    return o


_APPLIED: dict[str, set] = {"consumables": set(), "deviations": set(), "scenarios": set()}


def scenario_key(name: str) -> str:
    return "c_" + (re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "fight")[:40]


def apply() -> None:
    """Merge typed-in foods, deviations and custom fights into the hand-written tables."""
    o = overrides()
    for name in _APPLIED["consumables"]:
        fx.CONSUMABLES.pop(name, None)
    for name in _APPLIED["deviations"]:
        fx.DEVIATIONS.pop(name, None)
    for key in _APPLIED["scenarios"]:
        fe.SCENARIOS.pop(key, None)
    _APPLIED["consumables"], _APPLIED["deviations"], _APPLIED["scenarios"] = set(), set(), set()

    for name, c in o["consumables"].items():
        if name in fx.CONSUMABLES:          # hand-written entry wins unless the player asked to replace it
            if not c.get("replace"):
                continue
        slots = tuple(s for s in c.get("slots") or ["food"] if s in ("food", "drink")) or ("food",)
        stats, _ = parse_buff(c.get("text", ""))
        fx.CONSUMABLES[name] = {"slots": slots, "stats": stats, "text": c.get("text", ""),
                                "source": c.get("source") or "typed in by you", "typed": True,
                                **({"kw": c["kw"]} if c.get("kw") else {}),
                                **({"boss_only": True} if c.get("boss_only") else {})}
        _APPLIED["consumables"].add(name)
    fx.FOODS.clear(); fx.FOODS.update({k: v for k, v in fx.CONSUMABLES.items() if "food" in v["slots"]})
    fx.DRINKS.clear(); fx.DRINKS.update({k: v for k, v in fx.CONSUMABLES.items() if "drink" in v["slots"]})

    for name, d in o["deviations"].items():
        if name in fx.DEVIATIONS and not d.get("replace"):
            continue
        stats, _ = parse_buff(d.get("text", ""))
        fx.DEVIATIONS[name] = {"stats": stats, "text": d.get("text", ""), "source": d.get("source") or "typed in by you",
                               "typed": True, **({"unmodeled": True} if not stats else {})}
        _APPLIED["deviations"].add(name)

    for key, s in o["scenarios"].items():
        base = s.get("base") if s.get("base") in BASES else "boss"
        d = dict(fe.SCENARIOS[base])
        d["label"] = s.get("name") or key
        for f in ("weakspot_rate", "enemies_hit", "kill_uptime", "moving", "shield", "low_hp"):
            if isinstance(s.get(f), (int, float)):
                d[f] = s[f]
        buffs, unparsed = parse_buff(s.get("buff_text", ""))
        d.update({"custom": True, "base": base, "buffs": buffs, "buff_text": s.get("buff_text", ""),
                  "unparsed": unparsed, "note": s.get("note", ""), "source": s.get("source", "")})
        fe.SCENARIOS[key] = d
        _APPLIED["scenarios"].add(key)
    fe._SCN_CACHE.clear()


def save_item(kind: str, name: str, entry: dict | None) -> dict:
    """kind = consumables | deviations | scenarios. entry None deletes it."""
    if kind not in ("consumables", "deviations", "scenarios"):
        raise ValueError("unknown kind")
    o = overrides()
    if entry is None:
        o[kind].pop(name, None)
    else:
        entry = {k: v for k, v in entry.items() if v not in (None, "")}
        if kind == "scenarios":
            entry.setdefault("name", name)
        entry["saved_at"] = now()
        o[kind][name] = entry
    write_json(OVERRIDES, o)
    apply()
    return o


# ------------------------------------------------------------------ NEW! badges
# "New" has to mean new to the GAME, not new to the app. Two rules keep it honest:
#  1. Baseline per source. The first time the app reads a list (th.gl snapshot, th.gl food list,
#     th.gl deviation list, the app's own tables) everything on it is "baseline", never NEW!.
#  2. Patch-note evidence. An item that shows up later only gets the NEW! badge when an official
#     post names it. Items th.gl adds without any post are listed apart as "new to the data".
# Items named in a scenario post (e.g. Isles of Abyss) also get a scenario label, new or not.
MENTIONS = LIVE / "mentions.json"
EVIDENCE_DAYS = 60     # a post counts as evidence if it is at most this many days older than first-seen
PREVIEW_DAYS = 14      # dev blogs announce things ("coming soon") up to ~2 weeks before they're in the game
SCN_MIN_LEN = 5        # shorter names ("Salt", "Corn") are too generic for scenario labels


def norm(name: str) -> str:
    """'Mist Core Clarity Soup' == 'Mistcore Clarity Soup', 'Chaos - Rebecca' == 'Chaos Rebecca'."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def seen() -> dict:
    s = read_json(SEEN, {})
    s.setdefault("items", {}); s.setdefault("verdicts", {})
    if "sources" not in s and s["items"]:
        _repair_legacy(s)
        write_json(SEEN, s)
    s.setdefault("sources", {})
    return s


def _repair_legacy(s: dict) -> None:
    """seen.json from 2026.11.05 baselined only the th.gl snapshot and the app tables. The th.gl
    food and deviation lists arrived a few minutes later and every name on them got a NEW! badge.
    Put those back to baseline (keep anything the update button or the player added)."""
    at = s.get("baseline_at") or now()
    s["sources"] = {"snapshot": at, "app": at}
    fixed = 0
    for k, v in s["items"].items():
        kind = k.split(":", 1)[0]
        if v.get("first") != "baseline" and v.get("via") == "app" and kind in ("food", "deviation"):
            s["items"][k] = {"first": "baseline", "via": "th.gl list (repaired)", "was": v.get("first")}
            fixed += 1
    if fixed or (NAMES.exists()):
        s["sources"]["thgl:food"] = at
        s["sources"]["thgl:deviation"] = at
    s.setdefault("repairs", []).append({"at": now(), "fixed": fixed,
                                        "why": "foods/deviations from the first th.gl list were wrongly marked NEW!"})


def item_keys(gd: dict, names: dict | None = None) -> dict[str, str]:
    """'weapon:AUG - Rapid Thunder' -> display kind, for everything the app knows about."""
    return {k: v[0] for k, v in item_sources(gd, names).items()}


def item_sources(gd: dict, names: dict | None = None) -> dict[str, tuple[str, str]]:
    """key -> (display kind, source list it came from)."""
    out: dict[str, tuple[str, str]] = {}
    for n in gd["weapons"]:
        out[f"weapon:{n}"] = ("Weapon", "snapshot")
    for n, a in gd["armor"].items():
        out[f"armor:{n}"] = ("Key armor" if n in fx.KEY_ARMOR else "Armor", "snapshot")
    for s in gd["sets"]:
        out[f"set:{s}"] = ("Armor set", "snapshot")
    for m in gd["mods"].values():
        out[f"mod:{m['name']}"] = ("Mod", "snapshot")
    names = names if names is not None else read_json(NAMES, {})
    typed = overrides()
    for n in (names.get("consumables") or {}):
        out[f"food:{n}"] = ("Food / drink", "thgl:food")
    for n in (names.get("deviations") or {}):
        out[f"deviation:{n}"] = ("Deviation", "thgl:deviation")
    for n in fx.CONSUMABLES:
        out[f"food:{n}"] = ("Food / drink", "typed" if n in typed["consumables"] else "app")
    for n in fx.DEVIATIONS:
        out[f"deviation:{n}"] = ("Deviation", "typed" if n in typed["deviations"] else "app")
    for k, s in fe.SCENARIOS.items():
        out[f"fight:{k}"] = ("Fight type", "typed" if s.get("custom") else "app")
    return out


def mark_seen(gd: dict, source: str = "app", names: dict | None = None) -> list[str]:
    """Record a first-seen date for anything never seen before. Returns the new keys.

    Anything on a list the app has never read before is baseline (not NEW!)."""
    s = seen()
    src = item_sources(gd, names)
    known = set(s["sources"])
    added = []
    for k, (_, origin) in src.items():
        if k in s["items"]:
            continue
        if origin in known or origin == "typed":
            s["items"][k] = {"first": today(), "via": "typed in" if origin == "typed" else source}
            added.append(k)
        else:
            s["items"][k] = {"first": "baseline", "via": origin}
    for origin in {o for _, o in src.values()} - known - {"typed"}:
        s["sources"][origin] = now()
    s.setdefault("baseline_at", now())
    write_json(SEEN, s)
    return added


# ---- patch-note evidence
def mentions() -> dict:
    m = read_json(MENTIONS, {})
    m.setdefault("posts", {}); m.setdefault("names", {})
    return m


def add_mentions(post: dict, found: list[dict]) -> None:
    """post: {url, title, date, kind, scenario}; found: [{name, how, scenario, line}] from one post."""
    m = mentions()
    url = post["url"]
    m["posts"][url] = {k: post.get(k) for k in ("title", "date", "kind", "scenario")}
    for nm in list(m["names"]):
        m["names"][nm] = [x for x in m["names"][nm] if x["url"] != url]
        if not m["names"][nm]:
            del m["names"][nm]
    for f in found:
        rec = {"url": url, "how": f.get("how", "named"), "scenario": f.get("scenario"), "line": (f.get("line") or "")[:240]}
        lst = m["names"].setdefault(norm(f["name"]), [])
        if not any(x["url"] == url and x["how"] == rec["how"] for x in lst):
            lst.append(rec)
    m["built_at"] = now()
    write_json(MENTIONS, m)


def evidence(name: str, m: dict | None = None) -> list[dict]:
    """Official posts naming this item, newest first: [{url, title, date, how, scenario, line}]."""
    m = m or mentions()
    keys = {norm(name)}
    if " - " in name:                       # 'SOCR - Cosmic Visitor' is often written 'Cosmic Visitor'
        keys.add(norm(name.split(" - ", 1)[1]))
    out = []
    for k in keys:
        for x in m["names"].get(k, []):
            p = m["posts"].get(x["url"], {})
            out.append({**x, "title": p.get("title"), "date": p.get("date"), "kind": p.get("kind"),
                        "scenario": x.get("scenario")})
    out.sort(key=lambda x: x.get("date") or "", reverse=True)
    return out


def dps_relevance(kind: str, name: str) -> str:
    """'gear' (weapon/armor/set/mod: counted by the optimizer), 'counted' (food/deviation with numbers),
    'no numbers' (food/deviation the app can't count yet), 'other'."""
    if kind in ("weapon", "armor", "set", "mod"):
        return "gear"
    if kind == "food":
        return "counted" if (fx.CONSUMABLES.get(name) or {}).get("stats") else "no numbers"
    if kind == "deviation":
        return "counted" if (fx.DEVIATIONS.get(name) or {}).get("stats") else "no numbers"
    return "other"


def _post_ok(first: str, date: str | None) -> bool:
    if not date:
        return False
    try:
        return dt.date.fromisoformat(date) >= dt.date.fromisoformat(first) - dt.timedelta(days=EVIDENCE_DAYS)
    except ValueError:
        return False


def classify() -> dict:
    """Split everything first seen in the NEW! window into
    new   - confirmed by an official post (or typed in by the player): NEW! badge everywhere
    data  - showed up on th.gl but no post names it: probably an older item; no badge
    and list items named in scenario posts (any age) under scenario."""
    s, m = seen(), mentions()
    cut = (dt.date.today() - dt.timedelta(days=NEW_DAYS)).isoformat()
    cut_blog = (dt.date.today() - dt.timedelta(days=NEW_DAYS + PREVIEW_DAYS)).isoformat()
    new, data, scenario = {}, {}, {}
    for k, v in s["items"].items():
        kind, _, name = k.partition(":")
        ev = evidence(name, m) if kind != "fight" else []
        verdict = s["verdicts"].get(k, {}).get("verdict")
        f = v.get("first", "baseline")
        ann = [e for e in ev if e.get("how") == "announced" and (e.get("date") or "") >= (cut_blog if e.get("kind") == "devBlog" else cut)]
        if f == "baseline" and ann and verdict != "not_new":
            # already in the data at the first read, but an official post announced it as new recently
            new[k] = {**v, "first": ann[-1]["date"], "via": "announced", "verdict": verdict, "dps": dps_relevance(kind, name),
                      "post": {x: ann[-1].get(x) for x in ("title", "url", "date", "how", "line")},
                      "scenario": next((e["scenario"] for e in ann if e.get("scenario")), None)}
        elif f != "baseline" and f >= cut and verdict != "not_new":
            good = [e for e in ev if _post_ok(f, e.get("date"))]
            rec = {**v, "verdict": verdict, "dps": dps_relevance(kind, name)}
            if good or v.get("via") == "typed in" or verdict == "cool":   # "It's new" / "Nice find" from the player
                rec["post"] = {x: good[0].get(x) for x in ("title", "url", "date", "how", "line")} if good else None
                rec["scenario"] = next((e["scenario"] for e in good if e.get("scenario")), None)
                new[k] = rec
            else:
                data[k] = rec
        scn = [e for e in ev if e.get("scenario")]
        if scn and len(name) >= SCN_MIN_LEN:
            e = scn[-1]   # the oldest scenario post: that's where it was introduced
            scenario[k] = {"scenario": e["scenario"], "title": e.get("title"), "url": e["url"], "date": e.get("date"),
                           "line": e.get("line"), "dps": dps_relevance(kind, name),
                           "new": k in new, "first": f}
    return {"new": new, "data": data, "scenario": scenario}


def new_marks() -> dict:
    """{'weapon:Name': {...}} for items with a NEW! badge (first seen recently AND named in a post)."""
    return classify()["new"]



def set_verdict(key: str, verdict: str | None, note: str = "") -> dict:
    """verdict: not_new | cool | wrong | None (clear). Kept for the next check-in with Computer."""
    s = seen()
    if verdict:
        s["verdicts"][key] = {"verdict": verdict, "note": note[:300], "at": now()}
    else:
        s["verdicts"].pop(key, None)
    write_json(SEEN, s)
    return s["verdicts"]


# ------------------------------------------------------------------ icons for new items
def live_icons() -> dict[str, str]:
    ix = read_json(ICON_INDEX, {})
    return {n: u for n, u in ix.items() if (ICON_DIR / u.rsplit("/", 1)[-1]).exists()}


def log_tail(n: int = 10) -> list[dict]:
    try:
        lines = LOG.read_text().splitlines()
    except OSError:
        return []
    out = []
    for ln in lines[-n:]:
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out[::-1]
