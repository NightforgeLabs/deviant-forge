#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "$0")" && pwd)
if [[ "$repo" != ~/Projects/once-human-advisor ]]; then
  echo 'The desktop templates target ~/Projects/once-human-advisor.' >&2
  exit 1
fi

applications="$HOME/.local/share/applications"
icons="$HOME/.local/share/icons/hicolor/scalable/apps"
units="$HOME/.config/systemd/user"
mkdir -p "$applications" "$icons" "$units"
install -m 0644 "$repo/desktop/deviant-forge.desktop" "$applications/deviant-forge.desktop"
install -m 0644 "$repo/desktop/deviant-forge.svg" "$icons/deviant-forge.svg"
install -m 0644 "$repo/desktop/deviant-forge.service" "$units/deviant-forge.service"
chmod 0755 "$repo/launch-desktop.sh" "$repo/desktop/open-browser-window.sh"
desktop-file-validate "$applications/deviant-forge.desktop"
systemctl --user daemon-reload
update-desktop-database "$applications"
if command -v omarchy >/dev/null 2>&1; then omarchy menu refresh; fi
echo 'Deviant Forge launcher installed.'
