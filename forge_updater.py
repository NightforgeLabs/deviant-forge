"""Install a Deviant Forge update without touching player data (run by "Update Deviant Forge.bat").

Usage:  python forge_updater.py [update file]
  The update file is a .zip or .tgz (e.g. forge-update.tgz). Without an argument the newest
  *forge-update* file in Downloads or the app folder is used.

Safety:
  - files under data/ in an update are refused (updates never carry player data)
  - your saved data (profile database + live/ folder) and the current code are backed up first to
    %LOCALAPPDATA%\\DeviantForge\\backups (newest 5 kept)
  - to undo, drag the code-*.zip backup onto "Update Deviant Forge.bat"
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

APP = Path(__file__).resolve().parent
KEEP = 5


def home() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "DeviantForge"


def data_dir() -> Path:
    env = os.environ.get("OH_ADVISOR_DATA")
    if env:
        return Path(env)
    return home() / "data" if os.name == "nt" else APP / "data"


def find_update(arg: str | None) -> Path | None:
    if arg:
        return Path(arg)
    spots = [Path.home() / "Downloads", APP]
    found = [p for d in spots if d.is_dir() for p in d.iterdir()
             if "forge-update" in p.name.lower() and p.suffix.lower() in (".zip", ".tgz", ".gz")]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def members(pkg: Path) -> list[tuple[str, bytes]]:
    out = []
    if zipfile.is_zipfile(pkg):
        with zipfile.ZipFile(pkg) as z:
            for i in z.infolist():
                if not i.is_dir():
                    out.append((i.filename, z.read(i)))
    else:
        with tarfile.open(pkg, "r:*") as t:
            for m in t.getmembers():
                if m.isfile():
                    out.append((m.name, t.extractfile(m).read()))
    return out


def clean(name: str) -> str | None:
    """Relative path inside the app, or None if it must not be written."""
    p = PurePosixPath(name.replace("\\", "/"))
    parts = [x for x in p.parts if x not in ("", ".")]
    if not parts or p.is_absolute() or ".." in parts or ":" in parts[0]:
        return None
    if parts[0] == "data" or "__pycache__" in parts:
        return None
    return "/".join(parts)


def backup(stamp: str) -> Path:
    bdir = home() / "backups"
    bdir.mkdir(parents=True, exist_ok=True)
    code = bdir / f"code-{stamp}.zip"
    with zipfile.ZipFile(code, "w", zipfile.ZIP_DEFLATED) as z:
        for f in APP.rglob("*"):
            rel = f.relative_to(APP)
            if f.is_file() and rel.parts[0] != "data" and "__pycache__" not in rel.parts:
                z.write(f, rel.as_posix())
    d = data_dir()
    db = d / "advisor.sqlite3"
    if db.is_file():  # sqlite's own backup is safe even while Deviant Forge is open
        dst = bdir / f"data-{stamp}.sqlite3"
        src = sqlite3.connect(db)
        out = sqlite3.connect(dst)
        with out:
            src.backup(out)
        src.close(); out.close()
    if (d / "live").is_dir():
        with zipfile.ZipFile(bdir / f"live-{stamp}.zip", "w", zipfile.ZIP_DEFLATED) as z:
            for f in (d / "live").rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(d).as_posix())
    for pat in ("code-*.zip", "data-*.sqlite3", "live-*.zip"):
        for old in sorted(bdir.glob(pat))[:-KEEP]:
            old.unlink()
    return code


def running() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:%s/api/health" % os.environ.get("OH_ADVISOR_PORT", "8765"), timeout=1) as r:
            return b"deviant-forge" in r.read()
    except Exception:  # noqa: BLE001
        return False


def main(argv: list[str]) -> int:
    pkg = find_update(argv[1] if len(argv) > 1 else None)
    if not pkg or not pkg.is_file():
        print("No update file found. Drag the update (.zip or .tgz) onto \"Update Deviant Forge.bat\",\n"
              "or put it in your Downloads folder with 'forge-update' in its name.")
        return 1
    print("Update file :", pkg)
    try:
        items = members(pkg)
    except Exception as e:  # noqa: BLE001
        print("That file isn't a readable .zip or .tgz:", e)
        return 1
    keep, refused = [], []
    for name, blob in items:
        rel = clean(name)
        (keep if rel else refused).append((rel or name, blob))
    if not keep:
        print("The update has no app files in it. Nothing changed.")
        return 1
    # a zip of the whole "Deviant Forge" folder: strip that top folder
    tops = {r.split("/", 1)[0] for r, _ in keep}
    if len(tops) == 1 and not (APP / next(iter(tops))).exists() and any("/" in r for r, _ in keep):
        top = next(iter(tops)) + "/"
        keep = [(r[len(top):], b) for r, b in keep if r.startswith(top) and r[len(top):]]
        keep = [(r, b) for r, b in keep if r.split("/", 1)[0] != "data"]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    print("Backing up your data and the current version ...")
    code = backup(stamp)
    for rel, blob in keep:
        dst = APP / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(blob)
    print(f"Installed {len(keep)} files. Your data was not touched:", data_dir())
    if refused:
        print(f"Skipped {len(refused)} files that would have touched data or gone outside the app folder.")
    print("Backups :", code.parent)
    print("Undo    : drag", code.name, "onto \"Update Deviant Forge.bat\"")
    if running():
        print("\nDeviant Forge is open: close its window and start it again to use the new version.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
