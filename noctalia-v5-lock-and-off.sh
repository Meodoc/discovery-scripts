#!/usr/bin/env bash
# lock-and-off.sh — Noctalia v5
# Lock -> hold 2s -> fade all monitors -> power off.
#
# v5 notes:
#   * CLI is now `noctalia msg ...` (the old `qs -c noctalia-shell ipc call ...` is gone;
#     v5 is a C++ rewrite and no longer runs as a Quickshell config).
#   * The lockscreen is still an ext-session-lock surface, so a layer-shell overlay
#     (the old dim.qml) cannot be drawn on top of it. Instead we fade via
#     `brightness-set all`, which goes through Noctalia's brightness service and so
#     applies below compositing — it dims the locked screen AND external monitors.

HOLD=2         # seconds to sit on the lock screen before fading
STEPS=12       # fade granularity
DELAY=0.05     # seconds between steps
RESTORE=100    # brightness (%) to restore once monitors are off

# 1. Lock immediately — no window where the unlocked desktop is visible.
noctalia msg session lock

# 2. Hold on the lock screen.
sleep "$HOLD"

# 3. Fade every monitor to black. `all` targets all outputs.
for ((i = STEPS; i >= 0; i--)); do
    noctalia msg brightness-set all "$(( 100 * i / STEPS ))"
    sleep "$DELAY"
done

# 4. Cut monitor power.
noctalia msg dpms-off

# 5. Restore brightness while the panels are off, so the displays wake at a
#    normal level instead of fully dark. Invisible to you at this point.
noctalia msg brightness-set all "$RESTORE"

