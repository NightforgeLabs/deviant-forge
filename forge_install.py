"""Install or update Deviant Forge on Windows (run by "Install or update Deviant Forge.bat").

There is exactly one real copy afterwards:
    %LOCALAPPDATA%\\DeviantForge\\app      <- the app (replaced on every update)
    %LOCALAPPDATA%\\DeviantForge\\data     <- your saved gear/profile (never touched by updates)
and a "Deviant Forge" shortcut on the Desktop and in the Start menu that always opens it.

Steps:
 1. stop any Deviant Forge that is already running (an old copy would otherwise keep answering)
 2. keep the previous app as a backup (newest 3 kept)
 3. copy this download into the app folder (never copies a data/ folder)
 4. bring over saved data from an old unzipped copy, once, if there is no saved data yet
 5. make the shortcuts, label old unzipped copies, and start the new version
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SRC = Path(__file__).resolve().parent
PORT = int(os.environ.get("OH_ADVISOR_PORT", "8765"))
URL = f"http://127.0.0.1:{PORT}/"
SKIP = {"data", "__pycache__", ".git"}
OLD_NOTE = "OLD COPY - use the Deviant Forge shortcut on your Desktop instead.txt"


def home() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "DeviantForge"


def version(folder: Path) -> str:
    try:
        return (folder / "VERSION").read_text().strip()
    except OSError:
        return "older than 2026.11.06.07"


def health() -> dict | None:
    try:
        with urllib.request.urlopen(URL + "api/health", timeout=1.5) as r:
            d = json.loads(r.read() or b"{}")
            return d if d.get("app") == "deviant-forge" else None
    except Exception:  # noqa: BLE001
        return None


def _pid_on_port(port: int) -> list[int]:
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=10).stdout
    except Exception:  # noqa: BLE001
        return []
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3].upper() == "LISTENING":
            if parts[4].isdigit():
                pids.add(int(parts[4]))
    return sorted(pids)


def stop_running(reason: str = "") -> bool:
    """Stop whatever Deviant Forge answers on our port. Only touches it after /api/health says it's Deviant Forge."""
    h = health()
    if not h:
        return True
    print(f"Stopping the Deviant Forge that is already running (version {h.get('version') or 'old'}){reason} ...")
    try:
        req = urllib.request.Request(URL + "api/shutdown", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=2).read()
    except Exception:  # noqa: BLE001  (old versions don't have /api/shutdown)
        pass
    for _ in range(20):
        if not health():
            return True
        time.sleep(0.25)
    if os.name == "nt" and health():
        for pid in _pid_on_port(PORT):
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        for _ in range(20):
            if not health():
                return True
            time.sleep(0.25)
    return not health()


def is_app_folder(p: Path) -> bool:
    return (p / "server.py").is_file() and (p / "forge.py").is_file()


def find_old_copies(skip: list[Path]) -> list[Path]:
    """Unzipped copies in the usual places (Desktop, Downloads, Documents, OneDrive), 3 folders deep."""
    roots = [Path.home() / n for n in ("Desktop", "Downloads", "Documents")]
    od = os.environ.get("OneDrive")
    if od:
        roots += [Path(od) / n for n in ("Desktop", "Documents", "Downloads")]
    skip_r = {s.resolve() for s in skip}
    found = []
    for r in roots:
        if not r.is_dir():
            continue
        stack = [(r, 0)]
        while stack:
            d, depth = stack.pop()
            try:
                if d.resolve() in skip_r:
                    continue
                if is_app_folder(d):
                    found.append(d)
                    continue
                if depth < 3:
                    stack += [(c, depth + 1) for c in d.iterdir() if c.is_dir() and not c.name.startswith(".")
                              and c.name.lower() not in ("node_modules", "appdata")]
            except OSError:
                continue
    return found


def copy_app(src: Path, dst: Path) -> int:
    n = 0
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        dirs[:] = [d for d in dirs if d not in SKIP and not (rel == Path(".") and d == "data")]
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for f in files:
            if f.endswith(".pyc") or f == OLD_NOTE:
                continue
            shutil.copy2(Path(root) / f, dst / rel / f)
            n += 1
    return n


def migrate_data(data: Path, old: list[Path]) -> Path | None:
    if (data / "advisor.sqlite3").exists():
        return None
    cands = [p / "data" for p in old if (p / "data" / "advisor.sqlite3").is_file()]
    if (SRC / "data" / "advisor.sqlite3").is_file():
        cands.append(SRC / "data")
    if not cands:
        return None
    best = max(cands, key=lambda d: (d / "advisor.sqlite3").stat().st_mtime)
    data.mkdir(parents=True, exist_ok=True)
    shutil.copytree(best, data, dirs_exist_ok=True)
    return best


def shortcut(lnk: Path, target: Path, workdir: Path, icon: Path | None) -> bool:
    if os.name != "nt":
        return False
    lnk.parent.mkdir(parents=True, exist_ok=True)
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:DF_LNK);"
          "$s.TargetPath=$env:DF_TARGET;$s.WorkingDirectory=$env:DF_WD;"
          "if($env:DF_ICON){$s.IconLocation=$env:DF_ICON};$s.Description='Deviant Forge';$s.Save()")
    env = {**os.environ, "DF_LNK": str(lnk), "DF_TARGET": str(target), "DF_WD": str(workdir),
           "DF_ICON": str(icon) if icon and icon.exists() else ""}
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       env=env, capture_output=True, text=True)
    return r.returncode == 0


def desktop_dir() -> Path:
    if os.name == "nt":
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                               capture_output=True, text=True, timeout=15)
            if r.stdout.strip():
                return Path(r.stdout.strip())
        except Exception:  # noqa: BLE001
            pass
    return Path.home() / "Desktop"


AUTO = "--auto" in sys.argv  # started by the app's "Update now" button


def main() -> int:
    if sys.version_info < (3, 10):
        print("Deviant Forge needs Python 3.10 or newer. You have", sys.version.split()[0])
        return 1
    H = home()
    app, data, backups = H / "app", H / "data", H / "backups"
    new_v, old_v = version(SRC), (version(app) if is_app_folder(app) else None)
    print("Deviant Forge installer")
    print("  New version     :", new_v)
    print("  Installed before:", old_v or "nothing yet")
    print("  Installing to   :", app)
    print("  Your saved data :", data, "(never replaced)\n")

    if not is_app_folder(SRC):
        print("This doesn't look like a Deviant Forge download (server.py is missing).")
        print("Right-click the zip > Extract All, then run the .bat from the extracted folder.")
        return 1
    if SRC.resolve() == app.resolve():
        print("This is already the installed copy. To update, run the installer from a NEW download.")
        return 1

    if not stop_running():
        print(f"Could not stop the Deviant Forge on port {PORT}. Close its black window, then run this again.")
        return 1

    if is_app_folder(app):
        backups.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = backups / f"app-{old_v.split()[0] if old_v else 'old'}-{stamp}"
        for i in range(40):  # the old window may still be closing and holding the folder for a moment
            try:
                shutil.move(str(app), str(dest)); break
            except OSError:
                if i == 39:
                    raise
                time.sleep(0.5)
        olds = sorted([p for p in backups.glob("app-*") if p.is_dir()], key=lambda p: p.stat().st_mtime)
        for p in olds[:-3]:
            shutil.rmtree(p, ignore_errors=True)
        print("Previous version kept in", dest)
    n = copy_app(SRC, app)
    print(f"Copied {n} files.")

    olds = find_old_copies([app, SRC, backups])
    moved = migrate_data(data, olds)
    if moved:
        print("Brought your saved data over from", moved)

    start = app / "Start Deviant Forge.bat"
    icon = app / "static" / "favicon.ico"
    ok1 = shortcut(desktop_dir() / "Deviant Forge.lnk", start, app, icon)
    sm = Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Deviant Forge.lnk"
    shortcut(sm, start, app, icon)
    print("Desktop shortcut 'Deviant Forge':", "made" if ok1 else "could not be made (start it from " + str(start) + ")")

    for o in olds:
        try:
            (o / OLD_NOTE).write_text(f"This folder is an old copy of Deviant Forge (version {version(o)}).\n"
                                      f"The real one is installed in {app}\nand opens from the 'Deviant Forge' shortcut on your Desktop.\n"
                                      "Your saved gear is kept separately, so you can delete this folder.\n")
        except OSError:
            pass
    if olds:
        print("\nOld unzipped copies found (marked with a note, safe to delete):")
        for o in olds:
            print("  -", o, f"(version {version(o)})")
    print("\nAfter this, always open Deviant Forge from the Desktop shortcut.")
    if not AUTO:
        print("You can delete the downloaded zip and this extracted folder.\n")
    print("Starting Deviant Forge", new_v, "...")
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", "Deviant Forge", str(start)], cwd=str(app))
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001
        print("\nThe update stopped:", e)
        code = 1
    if AUTO:
        if code:
            input("\nPress Enter to close. Your previous version is still in the backups folder.")
        else:
            print("Done. This window closes in 5 seconds.")
            time.sleep(5)
    sys.exit(code)
