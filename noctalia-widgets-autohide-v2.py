#!/usr/bin/env python3
"""Hide Noctalia desktop widgets while a tiled (non-floating) window is on an
active niri workspace; show them when only floating windows remain.

Tracks workspace/window state from the niri event stream, so a decision needs
no IPC round-trips -- only an actual visibility flip spawns anything.
"""

import json
import subprocess
import sys

windows = {}      # window id -> (workspace id, is_floating)
ws_output = {}    # workspace id -> output name
active_ws = set() # workspace ids currently active on some output
state = None


def occupied():
    """True when a tiled window sits on a workspace active on some output."""
    return any(ws in active_ws and not floating
               for ws, floating in windows.values())


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
        # Also fires when a window is toggled floating/tiled, so this keeps
        # is_floating current without any extra event handling.
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
