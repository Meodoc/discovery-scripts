#!/usr/bin/bash

# Lock first, give the lock screen a moment to render on top
qs -c noctalia-shell ipc call lockScreen lock
sleep 0.7

# Remember current brightness, then fade the backlight to 0
orig=$(brightnessctl get)
steps=20
for ((i = steps; i >= 0; i--)); do
    brightnessctl -q set "$(( orig * i / steps ))"
    sleep 0.04
done

# Now cut monitor power
#qs -c noctalia-shell ipc call monitors off
niri msg action power-off-monitors

sleep 0.5

# Restore brightness while the panel is off — invisible now,
# so it wakes back up at normal brightness instead of black
brightnessctl -q set "$orig"

