#!/usr/bin/env bash
# lock-and-off.sh — Noctalia v5
# Lock -> hold -> per-monitor proportional fade -> power off -> restore levels.
#
# Why this is more involved than "set everything to 0":
#   Monitors sit at DIFFERENT brightness levels. Ramping them all from a fixed
#   100% means a monitor at 40% JUMPS UP to 100% before fading down — a visible
#   flash. And restoring everything to a fixed value clobbers your per-monitor
#   levels. So each monitor is faded from its OWN current level and restored to it.
#
#   The two transports also have very different speeds: the laptop panel is sysfs
#   (instant) while external monitors go over DDC/I2C (~200-500ms per call). Fading
#   them in one serial loop makes the external lag badly behind the laptop, so each
#   monitor fades in its own background job, with step counts tuned per transport.
#
# Writes go through `noctalia msg brightness-set <connector> <pct>` so Noctalia's
# own brightness state stays in sync (reads use brightnessctl/ddcutil directly,
# since v5 has no brightness-get in its CLI).

set -uo pipefail

HOLD=2            # seconds on the lock screen before fading

INT_STEPS=16      # laptop panel: sysfs is fast, so fade finely
INT_DELAY=0.03

EXT_STEPS=4       # external: each DDC write is slow, keep the step count low
EXT_DELAY=0

# ---------------------------------------------------------------- discovery --

# Internal panel connector (eDP-1 / LVDS-1), as Noctalia names it.
INTERNAL=""
for d in /sys/class/drm/card*-eDP-* /sys/class/drm/card*-LVDS-*; do
    [ -e "$d" ] || continue
    INTERNAL="$(basename "$d" | sed 's/^card[0-9]*-//')"
    break
done

# External monitors: pair each "/dev/i2c-N" with its "DRM connector:" line,
# exactly the way Noctalia's brightness service parses ddcutil detect.
EXT_CONNECTORS=()
EXT_BUSES=()
while read -r conn bus; do
    [ -n "$conn" ] && [ -n "$bus" ] || continue
    EXT_CONNECTORS+=("$conn")
    EXT_BUSES+=("$bus")
done < <(ddcutil detect --terse 2>/dev/null | awk '
    /\/dev\/i2c-/   { if (match($0, /i2c-[0-9]+/)) bus = substr($0, RSTART+4, RLENGTH-4) }
    /DRM connector/ { conn = $NF; sub(/^card[0-9]+-/, "", conn) }
    conn != "" && bus != "" { print conn, bus; conn=""; bus="" }
')

# ------------------------------------------------------------ read current --

read_internal_pct() {
    brightnessctl -m 2>/dev/null | awk -F, 'NR==1 { gsub(/%/,"",$4); print $4 }'
}

read_external_pct() {  # $1 = i2c bus number
    ddcutil --bus "$1" getvcp 10 --terse 2>/dev/null \
        | awk '{ if ($5 > 0) printf "%d", 100*$4/$5 }'
}

# Snapshot every monitor's level BEFORE touching anything.
INT_ORIG=""
[ -n "$INTERNAL" ] && INT_ORIG="$(read_internal_pct)"

EXT_ORIG=()
for i in "${!EXT_CONNECTORS[@]}"; do
    EXT_ORIG+=("$(read_external_pct "${EXT_BUSES[$i]}")")
done

# ------------------------------------------------------------------- fade --

fade_down() {  # $1 = connector, $2 = starting %, $3 = steps, $4 = delay
    local conn="$1" from="$2" steps="$3" delay="$4" i
    [ -n "$from" ] || return 0
    for ((i = steps - 1; i >= 0; i--)); do
        noctalia msg brightness-set "$conn" "$(( from * i / steps ))" >/dev/null 2>&1
        [ "$delay" != "0" ] && sleep "$delay"
    done
}

# 1. Lock first — no window where the unlocked desktop is visible.
noctalia msg session lock

# 2. Hold on the lock screen.
sleep "$HOLD"

# 3. Fade every monitor from its own level, each in parallel so the slow DDC
#    writes don't hold up the laptop panel.
PIDS=()
if [ -n "$INTERNAL" ]; then
    fade_down "$INTERNAL" "$INT_ORIG" "$INT_STEPS" "$INT_DELAY" &
    PIDS+=($!)
fi
for i in "${!EXT_CONNECTORS[@]}"; do
    fade_down "${EXT_CONNECTORS[$i]}" "${EXT_ORIG[$i]}" "$EXT_STEPS" "$EXT_DELAY" &
    PIDS+=($!)
done
for p in "${PIDS[@]}"; do wait "$p"; done

# 4. Cut monitor power.
noctalia msg dpms-off

# 5. Restore each monitor to ITS OWN previous level, while the panels are off
#    so none of this is visible.
[ -n "$INTERNAL" ] && [ -n "$INT_ORIG" ] \
    && noctalia msg brightness-set "$INTERNAL" "$INT_ORIG" >/dev/null 2>&1
for i in "${!EXT_CONNECTORS[@]}"; do
    [ -n "${EXT_ORIG[$i]}" ] \
        && noctalia msg brightness-set "${EXT_CONNECTORS[$i]}" "${EXT_ORIG[$i]}" >/dev/null 2>&1
done

