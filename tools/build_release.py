"""Build the files for one GitHub release into dist/.

    python3 tools/build_release.py            # uses ./VERSION

Makes
    dist/Deviant-Forge-<ver>-windows.zip   top folder "Deviant Forge/": INSTALL .bat, READ ME, app/
    dist/deviant-forge-<ver>-linux.tgz     the app files (extract over an install, or run server.py)
    dist/SHA256SUMS.txt                    checked by the in-app updater before installing
    dist/notes.md                          this version's changelog lines (release description)

Player data (data/) and caches are never included; the build stops if any would be.
"""
from __future__ import annotations

import hashlib
import io
import re
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
NEVER = {"data", "__pycache__", ".git", "dist", ".github"}
NOT_IN_APP = {"tests", "research", "desktop", "windows", "install-desktop.sh", "launch-desktop.sh", "launch.sh",
              "tools/install-forge-update.sh"}
NOT_IN_LINUX = {"windows", "research", "desktop"}


def files(skip: set[str]) -> list[Path]:
    out = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        parts = rel.split("/")
        if any(x in NEVER for x in parts) or p.suffix == ".pyc":
            continue
        if parts[0] in skip or rel in skip:
            continue
        out.append(p)
    return out


def guard(names: list[str]) -> None:
    bad = [n for n in names if "data" in PurePosixPath(n).parts[:3] or n.endswith((".sqlite3", ".pyc"))]
    if bad:
        sys.exit(f"refusing to package player data: {bad[:5]}")


def notes(ver: str) -> str:
    try:
        text = (ROOT / "docs" / "FORGE_HANDOFF.md").read_text()
    except OSError:
        return f"Deviant Forge {ver}"
    lines = [l for l in text.splitlines() if l.startswith(f"- {ver}")]
    body = "\n".join(re.sub(r"^- \S+\s+[—-]\s*", "- ", l) for l in lines) or f"Deviant Forge {ver}"
    return body + "\n\nYour saved gear is never touched by an update."


def zinfo(name: str) -> zipfile.ZipInfo:
    zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = 0o644 << 16
    return zi


def main() -> int:
    ver = (ROOT / "VERSION").read_text().strip()
    DIST.mkdir(exist_ok=True)
    for old in DIST.iterdir():
        old.unlink()
    win = DIST / f"Deviant-Forge-{ver}-windows.zip"
    lin = DIST / f"deviant-forge-{ver}-linux.tgz"
    top = "Deviant Forge"

    app_files = files(NOT_IN_APP)
    names = [f"{top}/app/{p.relative_to(ROOT).as_posix()}" for p in app_files]
    guard(names)
    with zipfile.ZipFile(win, "w") as z:
        for n in ("INSTALL or UPDATE - double-click me.bat", "READ ME FIRST - Windows.txt"):
            z.writestr(zinfo(f"{top}/{n}"), (ROOT / "windows" / n).read_bytes())
        z.writestr(zinfo(f"{top}/app/Start Deviant Forge.bat"), (ROOT / "windows" / "Start Deviant Forge.bat").read_bytes())
        for p, n in zip(app_files, names):
            z.writestr(zinfo(n), p.read_bytes())

    lin_files = files(NOT_IN_LINUX)
    guard([p.relative_to(ROOT).as_posix() for p in lin_files])
    with tarfile.open(lin, "w:gz") as t:
        for p in lin_files:
            ti = t.gettarinfo(str(p), arcname=p.relative_to(ROOT).as_posix())
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            ti.mtime = 1767225600
            with open(p, "rb") as f:
                t.addfile(ti, f)

    sums = "".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n" for f in (win, lin))
    (DIST / "SHA256SUMS.txt").write_text(sums)
    (DIST / "notes.md").write_text(notes(ver))
    print(f"Deviant Forge {ver}")
    for f in (win, lin):
        print(f"  {f.name}  {f.stat().st_size / 1e6:.1f} MB  {len(app_files) if f == win else len(lin_files)} files")
    print(sums, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
