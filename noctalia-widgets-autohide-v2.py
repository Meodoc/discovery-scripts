#!/usr/bin/env python3
"""Hide Noctalia desktop widgets while a tiled (non-floating) window is on an
active niri workspace belonging to a monitor listed in WIDGET_OUTPUTS.

Windows on any other monitor are ignored, so an external display does not hide
the widgets on the laptop panel.

Note: noctalia's desktop-widgets-show/hide IPC commands are global -- they take
no monitor selector -- so if WIDGET_OUTPUTS lists several outputs, a window on
any one of them hides the widgets on all of them. That is a shell limitation,
not a bug here.
"""

import json
import subprocess
import sys

# Connector names of the monitors your desktop widgets sit on.
# Find yours with: niri msg outputs
# An empty set means "every output" (the previous behavior).
WIDGET_OUTPUTS = {"eDP-1"}

windows = {}      # window id -> (workspace id, is_floating)
ws_output = {}    # workspace id -> output name
active_ws = set() # workspace ids currently active on some output
state = None


def counts(ws, floating):
    """True when this window should force the widgets hidden."""
    if floating or ws not in active_ws:
        return False
    if not WIDGET_OUTPUTS:
        return True
    return ws_output.get(ws) in WIDGET_OUTPUTS


def occupied():
    return any(counts(ws, floating) for ws, floating in windows.values())


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


def remember(w):
    # Absent is_floating (older niri) counts as tiled, preserving old behavior.
    windows[w["id"]] = (w.get("workspace_id"), w.get("is_floating", False))


def handle(name, data):
    if name == "WorkspacesChanged":
        ws_output.clear()
        active_ws.clear()
        for ws in data["workspaces"]:
            ws_output[ws["id"]] = ws.get("output")
            if ws.get("is_active"):
                active_ws.add(ws["id"])

    elif name == "WorkspaceActivated":
        wid = data["id"]
        # Activating a workspace deactivates the others on the same output.
        out = ws_output.get(wid)
        active_ws.difference_update(
            {w for w in active_ws if ws_output.get(w) == out})
        active_ws.add(wid)

    elif name == "WindowsChanged":
        windows.clear()
        for w in data["windows"]:
            remember(w)

    elif name == "WindowOpenedOrChanged":
        # Also fires when a window is toggled floating/tiled or moved to
        # another workspace, so this keeps both fields current.
        remember(data["window"])

    elif name == "WindowClosed":
        windows.pop(data["id"], None)

    else:
        return  # nothing that can change what is on screen

    apply()


def main():
    proc = subprocess.Popen(["niri", "msg", "--json", "event-stream"],
                            stdout=subprocess.PIPE, text=True, bufsize=1)
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for name, data in event.items():
            handle(name, data)
    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
