#!/usr/bin/env bash
# Netlify build step for both sites built from this repo (netlify.toml runs it).
#
#   worksona-blender-worlds  public site. Private worlds (META["private"] = True) are removed.
#   blender-harness-twins    the oil and gas worlds, private twins included. Password-protected
#                            in the Netlify dashboard. Recognised by its project name (Netlify sets
#                            SITE_NAME in every build), or by INCLUDE_PRIVATE=true on any project.
#                            TWINS_WORLDS (space- or comma-separated slugs) overrides the list.
#
# Every other project builds the public site: a misconfigured site fails safe, toward
# publishing less.
set -euo pipefail

TWINS_SITE="blender-harness-twins"
TWINS_WORLDS_DEFAULT="gas-station oil-refinery refinery-dusk purnell-test-shop purnell-spools"

echo "[netlify-build] SITE_NAME=${SITE_NAME:-<unset>} INCLUDE_PRIVATE=${INCLUDE_PRIVATE:-<unset>}"

# The guide links the cloud setup script through a symlink; publish a real copy.
rm -f app/cloud-env-setup.sh
cp scripts/cloud-env-setup.sh app/cloud-env-setup.sh

twins=""
if [[ "${SITE_NAME:-}" == "$TWINS_SITE" ]]; then
  twins="project name $TWINS_SITE"
elif [[ "${INCLUDE_PRIVATE:-}" == "true" ]]; then
  twins="INCLUDE_PRIVATE=true"
fi

if [[ -n "$twins" ]]; then
  worlds="${TWINS_WORLDS:-$TWINS_WORLDS_DEFAULT}"
  echo "[netlify-build] twins site ($twins): publishing only: $worlds (this site must be password-protected)"
  python3 tools/strip_private.py app --only "$worlds"
  cat > app/_headers <<'EOF'
/*
  X-Robots-Tag: noindex, nofollow
EOF
else
  echo "[netlify-build] public site"
  python3 tools/strip_private.py app
fi
