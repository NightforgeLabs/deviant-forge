#!/usr/bin/env bash
set -euo pipefail

URL=http://127.0.0.1:8765
SERVICE=deviant-forge.service
state_dir=${XDG_STATE_HOME:-$HOME/.local/state}/deviant-forge
mkdir -p "$state_dir"
log() { printf '%s %s\n' "$(date --iso-8601=seconds)" "$*" >>"$state_dir/launcher.log"; }
log 'Desktop launch requested'

ready() {
  curl --silent --show-error --fail --max-time 2 "$URL/api/health" 2>/dev/null |
    grep --fixed-strings --quiet '"app": "deviant-forge"'
}

if ! ready; then
  log 'Starting user service'
  if ! systemctl --user start "$SERVICE"; then
    log 'User service start failed'
    exit 1
  fi
  for ((attempt=0; attempt<80; attempt++)); do
    if ready; then break; fi
    sleep 0.25
  done
fi

if ! ready; then
  log 'Server did not become ready'
  exit 1
fi
log 'Server ready'

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
browser_helper="$repo_dir/desktop/open-browser-window.sh"
if ! browser_info=$("$browser_helper" --check); then
  log 'No supported browser for a focus-safe launch'
  exit 1
fi
if ! command -v hyprctl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
  log 'Hyprland workspace routing unavailable; browser launch deferred'
  exit 1
fi

# Super+Space is a user launch. Put the window on the workspace from which the
# user invoked it. This is separate from background test routing rules.
active_workspace=$(hyprctl activeworkspace -j | jq -r '.id')
if [[ ! "$active_workspace" =~ ^[1-9][0-9]*$ ]]; then
  log "Active workspace $active_workspace is not a positive numbered workspace; browser launch deferred"
  exit 1
fi
target_workspace=$active_workspace

# An existing window on another workspace does not satisfy this launch.
# Reusing a window here avoids duplicate Forge windows on the same workspace.
existing=$(hyprctl clients -j | jq -r --argjson id "$target_workspace" \
  '[.[] | select(.workspace.id == $id and ((.class == "deviant-forge") or (.title | startswith("Deviant Forge")))) | .address][0] // empty')
if [[ -n "$existing" ]]; then
  log "Focusing existing Deviant Forge window on workspace $target_workspace"
  hyprctl dispatch focuswindow "address:$existing" >/dev/null
  exit 0
fi

log "Opening $browser_info on user workspace $target_workspace"
launch_command="hl.dsp.exec_cmd([[exec $browser_helper]], { workspace = '$target_workspace', no_initial_focus = false, focus_on_activate = true })"
if ! hyprctl dispatch "$launch_command" >/dev/null; then
  log 'Hyprland dispatch failed; browser launch deferred'
  exit 1
fi
for ((attempt=0; attempt<40; attempt++)); do
  if hyprctl clients -j | jq -e --argjson id "$target_workspace" \
      'any(.[]; .workspace.id == $id and ((.class == "deviant-forge") or (.title | startswith("Deviant Forge"))))' >/dev/null; then
    log "Browser window opened on workspace $target_workspace"
    exit 0
  fi
  sleep 0.25
done
log "Browser window did not appear on workspace $target_workspace"
exit 1
