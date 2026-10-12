#!/bin/bash
# Blender for Claude Code on the web: paste this whole file into your environment's
# "Setup script" (claude.ai/code -> environment settings).
#
# It runs once. The environment is then saved as a snapshot and reused for every session, so
# Blender is NOT downloaded per session. It is re-run only if you edit this script or the
# network settings, or after about 7 days. Self-contained on purpose: it doesn't need the repo.
#
# Network: allow download.blender.org (Custom access) for the official build. On the default
# "Trusted" network it falls back to Blender as a Python module (bpy) from PyPI.
set -u
V=5.2.2
LOG=/tmp/blender-setup.log

if [ -x /opt/blender/blender ] || [ -x "$HOME/.local/share/blender-harness/bpy-venv/bin/python" ]; then
  echo "[blender] already installed"
  exit 0
fi

# Shared libraries Blender loads even when headless.
apt-get update -qq >>"$LOG" 2>&1 || true
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
  ca-certificates curl xz-utils libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 \
  libxkbcommon0 libsm6 libice6 libgl1 libegl1 >>"$LOG" 2>&1 || true

# Official build, streamed straight into /opt (no temporary 380 MB file).
URL="https://download.blender.org/release/Blender${V%.*}/blender-${V}-linux-x64.tar.xz"
if curl -fsSL --retry 3 --connect-timeout 15 "$URL" | tar -xJ -C /opt 2>>"$LOG"; then
  rm -rf /opt/blender && mv "/opt/blender-${V}-linux-x64" /opt/blender
  ln -sf /opt/blender/blender /usr/local/bin/blender
  echo "[blender] $(/opt/blender/blender --version 2>/dev/null | head -1) installed in /opt/blender"
  exit 0
fi
rm -rf "/opt/blender-${V}-linux-x64"

# Fallback for the Trusted network: bpy wheel from PyPI in a Python 3.13 venv.
echo "[blender] download.blender.org not reachable; installing bpy from PyPI"
VENV="$HOME/.local/share/blender-harness/bpy-venv"
python3 -m pip install -q --user --break-system-packages uv >>"$LOG" 2>&1 || true
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
if "$UV" venv -q --python 3.13 "$VENV" >>"$LOG" 2>&1 && \
   "$UV" pip install -q --python "$VENV/bin/python" "bpy==${V}" >>"$LOG" 2>&1; then
  echo "[blender] bpy ${V} installed in $VENV"
else
  echo "[blender] install failed (see $LOG); the session hook will retry"
fi
exit 0
