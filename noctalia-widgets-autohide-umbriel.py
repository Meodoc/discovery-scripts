#!/usr/bin/env python3
"""Hide Noctalia desktop widgets while a tiled (non-floating) window is on an
active Umbriel workspace belonging to a monitor listed in WIDGET_OUTPUTS.

Umbriel's event stream sends full snapshots per family rather than deltas, so
this just keeps the newest snapshot of each and recomputes -- no state merging.

Note: noctalia's desktop-widgets-show/hide IPC commands are global; they take
no monitor selector. If WIDGET_OUTPUTS lists several outputs, a window on any
one of them hides the widgets on all of them. Shell limitation, not a bug here.
"""

import json
import subprocess
import sys

# Connector names of the monitors your desktop widgets sit on.
# Find yours with: umbriel outputs
# An empty set means "every output".
WIDGET_OUTPUTS = {"eDP-1"}

# Umbriel reports which scratchpad a window belongs to, but not whether that
# scratchpad is currently summoned, so a stashed window is indistinguishable
# from a visible one. Default to ignoring them rather than hiding the widgets
# for a window that may be off screen.
IGNORE_SCRATCHPAD = True

windows = []      # newest "windows" snapshot
workspaces = []   # newest "workspaces" snapshot
seen = set()      # which families have arrived at least once
state = None


def occupied():
    # workspace id -> output, for workspaces currently active on their output
    active = {ws.get("id"): ws.get("output")
              for ws in workspaces if ws.get("active")}

    for w in windows:
        if w.get("floating"):
            continue
        if w.get("tab_hidden"):          # stacked behind another tab
            continue
        if IGNORE_SCRATCHPAD and w.get("scratchpad"):
            continue
        output = active.get(w.get("workspace"))
        if output is None:               # not on an active workspace
            continue
        if not WIDGET_OUTPUTS or output in WIDGET_OUTPUTS:
            return True
    return False


def apply():
    global state
    want = "hide" if occupied() else "show"
    if want == state:
        return
    try:
        subprocess.run(["noctalia", "msg", f"desktop-widgets-{want}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=True)
        state = want
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # leave state unset so the next event retries


def main():
    global windows, workspaces

    proc = subprocess.Popen(["umbriel", "subscribe", "windows,workspaces"],
                            stdout=subprocess.PIPE, text=True, bufsize=1)
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        family = msg.get("event")
        if family == "windows":
            windows = msg.get("data") or []
        elif family == "workspaces":
            workspaces = msg.get("data") or []
        else:
            continue
        seen.add(family)

        # Both snapshots are needed before a verdict means anything.
        if {"windows", "workspaces"} <= seen:
            apply()

    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
