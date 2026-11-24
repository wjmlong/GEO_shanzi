#!/usr/bin/env bash
set -euo pipefail

mkdir -p /data/profile
# Clean stale Chromium singleton locks from previous container lifecycle
rm -f /data/profile/SingletonLock /data/profile/SingletonCookie /data/profile/SingletonSocket

rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 "${SCREEN_WIDTH:-1440}x${SCREEN_HEIGHT:-900}x24" -ac +extension GLX +render -noreset &
sleep 1

fluxbox >/dev/null 2>&1 &

# Configure VNC auth if BROWSER_HUB_VNC_PASSWORD is set
VNC_AUTH_ARGS=(-nopw)
if [ -n "${BROWSER_HUB_VNC_PASSWORD:-}" ]; then
    x11vnc -storepasswd "${BROWSER_HUB_VNC_PASSWORD}" /tmp/vncpass >/dev/null 2>&1
    VNC_AUTH_ARGS=(-rfbauth /tmp/vncpass)
fi

x11vnc -display :99 -forever -shared -rfbport 5900 "${VNC_AUTH_ARGS[@]}" >/var/log/x11vnc.log 2>&1 &

# Redirect root / of noVNC to auto-connect scaling view for 1-click convenience
cat >/usr/share/novnc/index.html <<'HTML'
<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=vnc.html?autoconnect=true&resize=scale"></head><body></body></html>
HTML

websockify --web=/usr/share/novnc/ 6080 localhost:5900 >/var/log/novnc.log 2>&1 &

# Launch real headed Chromium with persistent profile & local CDP port 9222
/usr/bin/chromium \
    --no-sandbox \
    --disable-setuid-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --disable-blink-features=AutomationControlled \
    --no-first-run \
    --no-default-browser-check \
    --window-position=0,0 \
    --window-size="${SCREEN_WIDTH:-1440},${SCREEN_HEIGHT:-900}" \
    --user-data-dir=/data/profile \
    --remote-debugging-address=127.0.0.1 \
    --remote-debugging-port=9222 \
    "${STARTUP_URL:-https://mp.toutiao.com/profile_v4/graphic/publish}" \
    >/var/log/chromium.log 2>&1 &

exec uvicorn server:app --host 0.0.0.0 --port 8090 --log-level info
