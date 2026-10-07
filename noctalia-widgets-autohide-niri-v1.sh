#!/usr/bin/env bash
# Hide Noctalia desktop widgets while any window is on an active niri
# workspace; show them again when the desktop is clear.
# Needs: niri, jq, noctalia (v5+).

set -uo pipefail

# True when at least one window sits on a workspace active on some output.
occupied() {
    local active
    active=$(niri msg --json workspaces | jq -c '[.[] | select(.is_active) | .id]') || return 1
    niri msg --json windows | jq -e --argjson active "$active" \
        'any(.[]; .workspace_id as $w | $active | index($w) != null)' >/dev/null
}

last=""

niri msg --json event-stream \
| jq -r --unbuffered '
    if (keys[0] | IN("WindowOpenedOrChanged", "WindowClosed", "WindowsChanged",
                     "WorkspaceActivated", "WorkspacesChanged"))
    then "check" else empty end
  ' \
| while read -r _; do
    if occupied; then action=hide; else action=show; fi
    [[ "$action" == "$last" ]] && continue
    noctalia msg "desktop-widgets-$action" >/dev/null 2>&1 && last="$action"
  done
