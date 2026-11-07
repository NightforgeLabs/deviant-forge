"""App updates from GitHub Releases. Nothing is installed until the player presses "Update now".

How it works
  - check(): asks GitHub for the newest release of REPO (one small request, no account needed).
    The answer is cached for 6 hours; the Updates page can force a fresh check.
  - install(): downloads the release file for this computer, checks it against SHA256SUMS.txt from
    the same release, then
      Windows: unpacks it next to the saved data and starts its INSTALL step (forge_install.py --auto),
               which stops this copy, keeps a backup, installs, and starts the new version.
      Linux:   saves it as /tmp/forge-update.tgz and shows the usual install command.
  - Player data (data/) is never part of a release, and any release file that tries to write into
    data/ or outside its folder is refused.

Turn the check off with DF_NO_UPDATE_CHECK=1. Point it at another repo with DF_UPDATE_REPO=owner/name.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

APP = Path(__file__).resolve().parent
REPO = os.environ.get("DF_UPDATE_REPO", "NightforgeLabs/deviant-forge")
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases/latest"
TTL = 6 * 3600
SUMS = "SHA256SUMS.txt"

_lock = threading.Lock()
_st: dict = {"checked_at": 0.0, "release": None, "error": None}
_job: dict = {"stage": "idle", "pct": 0, "msg": "", "error": None, "target": None, "command": None}


def current() -> str:
    try:
        return (APP / "VERSION").read_text().strip()
    except OSError:
        return "unknown"


def vtuple(s: str | None) -> tuple:
    return tuple(int(p) for p in re.findall(r"\d+", s or ""))


def newer(a: str | None, b: str | None) -> bool:
    """True when version a is newer than version b (2026.11.06.07 style)."""
    ta, tb = vtuple(a), vtuple(b)
    return bool(ta) and (not tb or ta > tb)


def platform() -> str:
    return "windows" if os.name == "nt" else "linux"


def enabled() -> bool:
    return not os.environ.get("DF_NO_UPDATE_CHECK")


def _get(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": f"DeviantForge/{current()}",
                                               "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def parse_release(d: dict) -> dict:
    tag = str(d.get("tag_name") or "")
    return {"version": tag.lstrip("vV"), "name": d.get("name") or tag, "notes": (d.get("body") or "").strip(),
            "url": d.get("html_url") or PAGE, "published": d.get("published_at"),
            "assets": [{"name": a.get("name"), "url": a.get("browser_download_url"), "size": a.get("size")}
                       for a in d.get("assets") or []]}


def check(force: bool = False) -> None:
    if not enabled():
        return
    with _lock:
        if not force and _st["checked_at"] and time.time() - _st["checked_at"] < TTL:
            return
    try:
        with _get(API) as r:
            rel = parse_release(json.loads(r.read() or b"{}"))
        err = None
    except Exception as e:  # noqa: BLE001  (offline, rate limited, no release yet ...)
        rel, err = None, str(e)
    with _lock:
        _st.update(checked_at=time.time(), error=err)
        if rel:
            _st["release"] = rel


def check_soon(delay: float = 4.0) -> None:
    """Background check shortly after the server starts, so pages never wait on GitHub."""
    def run():
        time.sleep(delay)
        check()
    threading.Thread(target=run, daemon=True).start()


def pick_asset(rel: dict, plat: str | None = None) -> dict | None:
    plat = plat or platform()
    end = "-windows.zip" if plat == "windows" else "-linux.tgz"
    for a in rel.get("assets") or []:
        if str(a.get("name") or "").lower().endswith(end):
            return a
    return None


def status(refresh: bool = False) -> dict:
    if refresh:
        check(force=True)
    with _lock:
        rel, err, at = _st["release"], _st["error"], _st["checked_at"]
        job = dict(_job)
    cur = current()
    latest = rel["version"] if rel else None
    return {"enabled": enabled(), "repo": REPO, "page": PAGE, "current": cur, "latest": latest,
            "available": bool(rel and newer(latest, cur) and pick_asset(rel)),
            "notes": rel["notes"] if rel else "", "release_url": rel["url"] if rel else PAGE,
            "published": rel["published"] if rel else None,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(at)) if at else None,
            "error": err, "platform": platform(), "job": job}


# ---------- install ----------

def updates_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "DeviantForge" / "updates"
    return Path(os.environ.get("TMPDIR") or "/tmp")


def _set(**kw) -> None:
    with _lock:
        _job.update(kw)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_sums(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", line.strip())
        if m:
            out[m.group(2).strip()] = m.group(1).lower()
    return out


def safe_extract(zpath: Path, dest: Path) -> None:
    """Unzip, refusing absolute paths, '..', and anything inside a data/ folder."""
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            p = PurePosixPath(m.filename.replace("\\", "/"))
            if p.is_absolute() or ".." in p.parts or (p.parts and ":" in p.parts[0]):
                raise ValueError(f"unsafe path in update: {m.filename}")
            if "data" in p.parts[:3]:
                raise ValueError(f"update tried to include player data: {m.filename}")
        z.extractall(dest)


def find_installer(root: Path) -> Path | None:
    for p in sorted(root.rglob("forge_install.py")):
        if p.parent.name == "app" and (p.parent / "server.py").is_file():
            return p
    return None


def _download(url: str, dest: Path, size: int | None) -> None:
    with _get(url, timeout=30) as r, open(dest, "wb") as f:
        total = size or int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total:
                _set(pct=min(90, 5 + int(85 * got / total)))


def _run_install() -> None:
    try:
        with _lock:
            rel = _st["release"]
        if not rel:
            raise RuntimeError("no release information yet; press Check again")
        asset = pick_asset(rel)
        sums = next((a for a in rel["assets"] if a["name"] == SUMS), None)
        if not asset or not sums:
            raise RuntimeError("this release has no file for this computer")
        _set(stage="downloading", pct=3, msg=f"Downloading {asset['name']}", target=rel["version"])
        udir = updates_dir()
        udir.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":  # keep only this download
            for old in udir.iterdir():
                shutil.rmtree(old, ignore_errors=True) if old.is_dir() else old.unlink(missing_ok=True)
        pkg = udir / (asset["name"] if os.name == "nt" else "forge-update.tgz")
        _download(asset["url"], pkg, asset.get("size"))
        _set(stage="checking", pct=92, msg="Checking the download is complete and unchanged")
        with _get(sums["url"], timeout=15) as r:
            want = parse_sums(r.read().decode("utf-8", "replace")).get(asset["name"])
        got = sha256(pkg)
        if not want or want != got:
            pkg.unlink(missing_ok=True)
            raise RuntimeError("the download did not match its checksum, so it was deleted. Try again later.")
        if os.name != "nt":
            md5 = hashlib.md5(pkg.read_bytes()).hexdigest()
            cmd = f"md5sum {pkg} && bash {APP / 'tools' / 'install-forge-update.sh'}"
            _set(stage="ready_manual", pct=100, msg=f"Downloaded and verified (md5 {md5}). Run this in a terminal:",
                 command=cmd)
            return
        _set(stage="unpacking", pct=95, msg="Unpacking")
        dest = udir / f"v{rel['version']}"
        safe_extract(pkg, dest)
        inst = find_installer(dest)
        if not inst:
            raise RuntimeError("the download has no installer inside")
        _set(stage="restarting", pct=98, msg="Installing. Deviant Forge restarts by itself; this page reloads when it's back.")
        env = {**os.environ, "DF_NO_BROWSER": "1", "PYTHONUTF8": "1"}
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen([sys.executable, str(inst), "--auto"], cwd=str(inst.parent), env=env, creationflags=flags)
    except Exception as e:  # noqa: BLE001
        _set(stage="error", error=str(e), msg="")


def install() -> dict:
    with _lock:
        busy = _job["stage"] in ("downloading", "checking", "unpacking", "restarting")
    if busy:
        return status()
    s = status()
    if not s["available"]:
        return {**s, "job": {**s["job"], "stage": "error", "error": "you already have the newest version"}}
    _set(stage="downloading", pct=1, msg="Starting", error=None, command=None)
    threading.Thread(target=_run_install, daemon=True).start()
    return status()
