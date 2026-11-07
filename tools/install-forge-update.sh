#!/usr/bin/env bash
# Deviant Forge optimizer update. Backs up first; never touches data/ or game files.
set -euo pipefail
APP="${APP:-$(cd "$(dirname "$0")/.." && pwd)}"
PKG=/tmp/forge-update.tgz
[ -f "$APP/server.py" ] && [ -f "$APP/forge.py" ] || { echo "Not a Deviant Forge folder: $APP (run this from the app's tools/ folder, or set APP=...)"; exit 1; }
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$HOME/deviant-forge-backup-$STAMP.tgz"
[ -f "$PKG" ] || { echo "Missing $PKG"; exit 1; }
echo "1/4 Backing up code (and a copy of data/advisor.sqlite3) to $BACKUP"
tar czf "$BACKUP" -C "$APP" --exclude=data/media --exclude=__pycache__ .
echo "2/4 Installing new files"
tar xzf "$PKG" -C "$APP"
echo "3/4 Running the new optimizer tests"
( cd "$APP" && python3 -m unittest tests.test_forge_optimizer -q 2>&1 | tail -3 )
echo "4/4 Restarting the Deviant Forge server (no browser is opened)"
systemctl --user restart deviant-forge.service || echo "Service restart failed; start it with: $APP/launch.sh"
sleep 2
curl -s -o /dev/null -w "Server answered HTTP %{http_code}\n" http://127.0.0.1:8765/ || true
echo
echo "Done. Open http://127.0.0.1:8765/  (old tools: http://127.0.0.1:8765/classic)"
echo "To undo: tar xzf $BACKUP -C $APP && systemctl --user restart deviant-forge.service"
