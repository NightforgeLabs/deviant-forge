"""Windows starter for Deviant Forge (run by "Start Deviant Forge.bat").

Player data (profile, gear, settings, refreshed game data) lives in
%LOCALAPPDATA%\\DeviantForge\\data, outside the app folder, so replacing or
updating the app folder can never remove it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP = Path(__file__).resolve().parent
PORT = int(os.environ.get("OH_ADVISOR_PORT", "8765"))
URL = f"http://127.0.0.1:{PORT}/"


def data_home() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "DeviantForge" / "data"


def running() -> bool:
    try:
        with urllib.request.urlopen(URL + "api/health", timeout=1) as r:
            return b"deviant-forge" in r.read()
    except Exception:  # noqa: BLE001
        return False


def health() -> dict:
    try:
        import json
        with urllib.request.urlopen(URL + "api/health", timeout=1) as r:
            return json.loads(r.read() or b"{}")
    except Exception:  # noqa: BLE001
        return {}


def migrate(data: Path) -> None:
    """Older copies kept data inside the app folder. Copy it once; the old copy is left alone."""
    old = APP / "data"
    if (old / "advisor.sqlite3").is_file() and not (data / "advisor.sqlite3").exists():
        print(f"Moving your saved data from {old} to {data} (one time) ...")
        shutil.copytree(old, data, dirs_exist_ok=True)


def ensure_pillow() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        pass
    print("Installing Pillow (one time, needed for item pictures) ...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--disable-pip-version-check", "pillow"])
    if r.returncode == 0:
        return True
    print("\nCould not install Pillow automatically. Open Command Prompt and run:\n"
          f'  "{sys.executable}" -m pip install --user pillow\nthen start Deviant Forge again.')
    return False


def open_when_ready() -> None:
    for _ in range(240):
        if running():
            webbrowser.open(URL)
            return
        time.sleep(0.25)
    print("The server didn't answer after 60 s. Try opening", URL, "yourself.")


def main() -> int:
    if sys.version_info < (3, 10):
        print("Deviant Forge needs Python 3.10 or newer. You have", sys.version.split()[0])
        return 1
    if running():
        h = health()
        mine = (APP / "VERSION").read_text().strip() if (APP / "VERSION").is_file() else None
        same = h and h.get("version") == mine and Path(h.get("app_dir") or "").resolve() == APP
        if same:
            print("Deviant Forge", mine, "is already running. Opening", URL)
            webbrowser.open(URL)
            return 0
        # an older copy (another folder or version) is answering: stop it, or you'd keep seeing the old app
        import forge_install
        if not forge_install.stop_running(" so this copy can start"):
            print(f"Another Deviant Forge is using port {PORT}. Close its black window and start again.")
            return 1
    data = data_home()
    data.mkdir(parents=True, exist_ok=True)
    migrate(data)
    if not ensure_pillow():
        return 1
    no_browser = os.environ.pop("DF_NO_BROWSER", None)  # after "Update now" the open page reloads by itself
    env = {**os.environ, "OH_ADVISOR_DATA": str(data), "PYTHONUTF8": "1"}
    print("Deviant Forge", (APP / "VERSION").read_text().strip() if (APP / "VERSION").is_file() else "")
    print("  App folder :", APP)
    print("  Your data  :", data)
    print("  Address    :", URL)
    print("Keep this window open while you use Deviant Forge. Close it to stop.\n")
    if not no_browser:
        threading.Thread(target=open_when_ready, daemon=True).start()
    try:
        return subprocess.call([sys.executable, "-X", "utf8", str(APP / "server.py"), "--host", "127.0.0.1", "--port", str(PORT)],
                               cwd=str(APP), env=env)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    code = main()
    if code:
        print(f"\nDeviant Forge stopped (code {code}). If it says the address is in use, another program has port {PORT}.")
    sys.exit(code)
