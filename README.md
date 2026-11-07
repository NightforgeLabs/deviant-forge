# Deviant Forge

A companion app for **Once Human**. Tell it the weapons, armor, mods and Starchrom you have, and it works out the strongest build you can make right now. It also tells you what to chase next for a real jump in damage: a new gear set, a new weapon, or new mods.

All damage numbers are labeled estimates, and each answer lists what it did not count.

Deviant Forge runs on your own computer and opens in your browser. It only reads public game data and what you type in. It never changes the game, its files or its memory.

## Install on Windows

1. Install **Python 3.10 or newer** from [python.org](https://www.python.org/downloads/windows/). During setup, tick **"Add python.exe to PATH"**.
2. Open the [latest release](https://github.com/NightforgeLabs/deviant-forge/releases/latest). Under **Assets**, download **Source code (zip)**.
3. Right-click the zip and choose **Extract All…**. Then double-click **"INSTALL or UPDATE - double-click me.bat"** in the extracted folder.
4. From then on, open it with the **Deviant Forge** shortcut on your Desktop.

## Updates

When a new version is published, Deviant Forge shows a green bar at the top: **"Deviant Forge … is ready"**. Press **Update now** to install it, or **Later** to skip it for now. Nothing installs unless you press the button.

When you press it, the app:

1. Downloads that release's code zip from GitHub.
2. Checks that every file is intact and that the zip is the version it claims to be.
3. Keeps your previous version as a backup.
4. Installs the update and restarts.

Your saved gear lives in `%LOCALAPPDATA%\DeviantForge\data` and is never touched by an update.

The update check is a single request to GitHub. To turn it off, set the environment variable `DF_NO_UPDATE_CHECK=1`.

## Linux

Download **Source code (tar.gz)** from the latest release and extract it. Then run `python3 server.py` and open <http://127.0.0.1:8765>. In the app, **Download update** saves a checked package to `/tmp/forge-update.tgz` and shows the command to install it.

## For developers

- `VERSION` holds the app version. Each release is tagged `v<VERSION>`, and the updater downloads GitHub's code zip for that tag.
- `python3 tools/build_release.py` builds a friendlier Windows zip and a Linux tgz into `dist/` for sharing by hand.
- To run the tests: `python3 -m unittest tests.test_forge_optimizer`.
- `TECHNICAL_README.md` and `docs/` hold the engine notes, and `docs/FORGE_HANDOFF.md` holds the changelog.

Once Human is a trademark of its owners. This is an unofficial fan tool, and it is not affiliated with or endorsed by NetEase or Starry Studio.
