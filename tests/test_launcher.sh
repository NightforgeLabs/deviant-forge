#!/usr/bin/env bash
# No desktop commands or browser processes: verify user-invoked routing with mocks.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/state"
cat >"$tmp/bin/curl" <<'EOF'
#!/usr/bin/env bash
if [[ "${TEST_COLD_START:-}" == 1 && ! -f "${TEST_READY_MARKER:-/nonexistent}" ]]; then exit 7; fi
printf '{"app": "deviant-forge", "status": "ready"}\n'
EOF
cat >"$tmp/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$TEST_SERVICE_LOG"
if [[ "$*" == '--user start deviant-forge.service' ]]; then touch "$TEST_READY_MARKER"; fi
EOF
cat >"$tmp/bin/hyprctl" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  activeworkspace) printf '{"id": %s}\n' "$TEST_WORKSPACE" ;;
  clients)
    if [[ "${TEST_NO_FORGE_AFTER_DISPATCH:-}" == 1 ]]; then
      printf '[{"workspace":{"id":%s},"class":"discord","title":"Discord","address":"0x99"}]\n' "$TEST_WORKSPACE"
    elif [[ -f "$TEST_LOG" ]] && grep -q 'hl.dsp.exec_cmd' "$TEST_LOG"; then
      printf '[{"workspace":{"id":%s},"class":"deviant-forge","title":"Deviant Forge","address":"0x8"}]\n' "$TEST_WORKSPACE"
    elif [[ "${TEST_EXISTING:-}" == same ]]; then
      printf '[{"workspace":{"id":%s},"class":"deviant-forge","title":"Deviant Forge","address":"0x8"}]\n' "$TEST_WORKSPACE"
    else
      printf '[{"workspace":{"id":7},"class":"brave-browser","title":"Deviant Forge","address":"0x7"}]\n'
    fi ;;
  dispatch) printf '%s\n' "${*:2}" >>"$TEST_LOG" ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$tmp/bin/curl" "$tmp/bin/systemctl" "$tmp/bin/hyprctl"
export PATH="$tmp/bin:$PATH" XDG_STATE_HOME="$tmp/state" TEST_LOG="$tmp/dispatch.log"
export TEST_READY_MARKER="$tmp/ready" TEST_SERVICE_LOG="$tmp/service.log"
export TEST_WORKSPACE=8 TEST_EXISTING=other
bash "$repo/launch-desktop.sh"
grep -q "workspace = '8'" "$TEST_LOG"
! grep -q "workspace = '7'" "$TEST_LOG"
: >"$TEST_LOG"
export TEST_EXISTING=same
bash "$repo/launch-desktop.sh"
grep -q 'focuswindow address:0x8' "$TEST_LOG"
! grep -q 'hl.dsp.exec_cmd' "$TEST_LOG"
: >"$TEST_LOG"
export TEST_WORKSPACE=10 TEST_EXISTING=other
bash "$repo/launch-desktop.sh"
grep -q "workspace = '10'" "$TEST_LOG"
: >"$TEST_LOG"
export TEST_WORKSPACE=8 TEST_EXISTING=other TEST_NO_FORGE_AFTER_DISPATCH=1
if bash "$repo/launch-desktop.sh"; then exit 1; fi
grep -q 'Browser window did not appear on workspace 8' "$tmp/state/deviant-forge/launcher.log"
unset TEST_NO_FORGE_AFTER_DISPATCH
rm -f "$TEST_READY_MARKER"
: >"$TEST_LOG"
export TEST_COLD_START=1 TEST_WORKSPACE=8 TEST_EXISTING=other
bash "$repo/launch-desktop.sh"
grep -q -- '--user start deviant-forge.service' "$TEST_SERVICE_LOG"
grep -q "workspace = '8'" "$TEST_LOG"
bash "$repo/launch-desktop.sh"
test "$(wc -l <"$TEST_SERVICE_LOG")" -eq 1
unset TEST_COLD_START
printf 'Launcher routing mock passed: user workspaces 8 and 10, same-workspace reuse, unrelated window rejected. No real workspace 10 window was opened.\n'
