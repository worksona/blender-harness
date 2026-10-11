#!/usr/bin/env bash
# Install headless Blender for the harness. Safe to re-run: exits fast when Blender is present.
#
# Tries, in order:
#   1. An existing Blender (PATH, /opt/blender, ~/.local/opt/blender, macOS app, bpy venv)
#   2. The official Linux x64 build from download.blender.org   (needs that domain reachable)
#   3. The `bpy` wheel from PyPI in a Python 3.13 venv via uv   (works on Claude's default
#      "Trusted" cloud network, which allows PyPI and GitHub but not download.blender.org)
#
# Self-contained on purpose: you can paste this whole file into a Claude Code cloud
# environment's setup script so the install is cached between sessions.
#
#   scripts/setup.sh            install if needed
#   scripts/setup.sh --quiet    only print the final status line
#   scripts/setup.sh --check    report what's installed, install nothing
#
# Env: BLENDER_VERSION (default 5.2.2), BLENDER_PREFIX (install dir), BPY_VENV, SKIP_BINARY=1
set -uo pipefail

BLENDER_VERSION="${BLENDER_VERSION:-5.2.2}"
SERIES="${BLENDER_VERSION%.*}"
BPY_VENV="${BPY_VENV:-$HOME/.local/share/blender-harness/bpy-venv}"
QUIET=0
CHECK=0
for arg in "$@"; do
  case "$arg" in
    --quiet) QUIET=1 ;;
    --check) CHECK=1 ;;
  esac
done

log() { [[ $QUIET == 1 ]] || echo "[setup] $*" >&2; }

SUDO=""
if [[ $(id -u) -ne 0 ]] && command -v sudo >/dev/null && sudo -n true 2>/dev/null; then
  SUDO="sudo"
fi
if [[ -z "${BLENDER_PREFIX:-}" ]]; then
  if [[ $(id -u) -eq 0 || -n "$SUDO" ]]; then BLENDER_PREFIX=/opt/blender
  else BLENDER_PREFIX="$HOME/.local/opt/blender"; fi
fi

existing() {
  local c
  for c in "${BLENDER:-}" "$(command -v blender 2>/dev/null || true)" "$BLENDER_PREFIX/blender" \
           /opt/blender/blender "$HOME/.local/opt/blender/blender" \
           /Applications/Blender.app/Contents/MacOS/Blender; do
    if [[ -n "$c" && -x "$c" ]] && "$c" --version >/dev/null 2>&1; then
      echo "binary $c $("$c" --version 2>/dev/null | head -1)"
      return 0
    fi
  done
  if [[ -x "$BPY_VENV/bin/python" ]] &&
     v=$("$BPY_VENV/bin/python" -c 'import bpy; print(bpy.app.version_string)' 2>/dev/null); then
    echo "bpy $BPY_VENV/bin/python Blender $v"
    return 0
  fi
  return 1
}

install_system_libs() {
  # Shared libraries Blender loads even when headless. Ubuntu/Debian only; best effort.
  command -v apt-get >/dev/null || return 0
  [[ $(id -u) -eq 0 || -n "$SUDO" ]] || return 0
  local pkgs="ca-certificates curl xz-utils libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1
              libxkbcommon0 libsm6 libice6 libgl1 libegl1"
  # shellcheck disable=SC2086
  if ! dpkg -s $pkgs >/dev/null 2>&1; then
    log "installing system libraries"
    $SUDO apt-get update -qq >/dev/null 2>&1 || true
    # shellcheck disable=SC2086
    DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq --no-install-recommends $pkgs \
      >/dev/null 2>&1 || log "warning: apt-get install failed (continuing)"
  fi
}

install_binary() {
  [[ "${SKIP_BINARY:-0}" == 1 ]] && return 1
  [[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || return 1
  local name="blender-${BLENDER_VERSION}-linux-x64"
  local url="https://download.blender.org/release/Blender${SERIES}/${name}.tar.xz"
  local tmp
  tmp="$(mktemp -d)"
  log "downloading $url"
  if ! curl -fL --retry 3 --connect-timeout 15 -sS "$url" -o "$tmp/blender.tar.xz"; then
    log "download.blender.org not reachable (allow it in the environment's network settings)"
    rm -rf "$tmp"
    return 1
  fi
  log "extracting to $BLENDER_PREFIX"
  tar -xJf "$tmp/blender.tar.xz" -C "$tmp" || { rm -rf "$tmp"; return 1; }
  $SUDO rm -rf "$BLENDER_PREFIX"
  $SUDO mkdir -p "$(dirname "$BLENDER_PREFIX")"
  $SUDO mv "$tmp/$name" "$BLENDER_PREFIX"
  rm -rf "$tmp"
  if [[ $(id -u) -eq 0 || -n "$SUDO" ]]; then
    $SUDO ln -sf "$BLENDER_PREFIX/blender" /usr/local/bin/blender
  else
    mkdir -p "$HOME/.local/bin" && ln -sf "$BLENDER_PREFIX/blender" "$HOME/.local/bin/blender"
  fi
  "$BLENDER_PREFIX/blender" --version >/dev/null 2>&1
}

find_uv() {
  command -v uv 2>/dev/null && return 0
  [[ -x "$HOME/.local/bin/uv" ]] && { echo "$HOME/.local/bin/uv"; return 0; }
  local tools="$HOME/.local/share/blender-harness/tools-venv"
  [[ -x "$tools/bin/uv" ]] && { echo "$tools/bin/uv"; return 0; }
  log "installing uv from PyPI"
  python3 -m pip install -q --user --break-system-packages uv >/dev/null 2>&1 &&
    [[ -x "$HOME/.local/bin/uv" ]] && { echo "$HOME/.local/bin/uv"; return 0; }
  python3 -m venv "$tools" >/dev/null 2>&1 && "$tools/bin/pip" install -q uv >/dev/null 2>&1 &&
    { echo "$tools/bin/uv"; return 0; }
  return 1
}

install_bpy() {
  local uv
  uv="$(find_uv)" || { log "could not install uv"; return 1; }
  log "creating Python 3.13 venv at $BPY_VENV and installing bpy==$BLENDER_VERSION (~400 MB)"
  "$uv" venv -q --python 3.13 "$BPY_VENV" >&2 || return 1
  "$uv" pip install -q --python "$BPY_VENV/bin/python" "bpy==$BLENDER_VERSION" >&2 || return 1
  "$BPY_VENV/bin/python" -c 'import bpy' >/dev/null 2>&1
}

if status="$(existing)"; then
  echo "[setup] Blender ready: $status"
  [[ "$status" == *"Blender $SERIES"* ]] || log "note: harness is tested with Blender $BLENDER_VERSION"
  exit 0
fi
if [[ $CHECK == 1 ]]; then
  echo "[setup] Blender not installed. Run scripts/setup.sh"
  exit 1
fi

[[ "$(uname -s)" == Linux ]] && install_system_libs
install_binary || install_bpy || {
  echo "[setup] FAILED to install Blender." >&2
  echo "[setup] Allow download.blender.org (or pypi.org + files.pythonhosted.org + github.com)" >&2
  echo "[setup] in the environment's network settings, or install Blender $BLENDER_VERSION manually." >&2
  exit 1
}
echo "[setup] Blender ready: $(existing)"
