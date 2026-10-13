#!/usr/bin/env bash
# Netlify build step for both sites built from this repo (netlify.toml runs it).
#
#   worksona-blender-worlds  public site. Private worlds (META["private"] = True) are removed.
#   blender-harness-twins    the oil and gas worlds, private twins included. Password-protected
#                            in the Netlify dashboard; its environment sets INCLUDE_PRIVATE=true.
#                            TWINS_WORLDS (space- or comma-separated slugs) overrides the list.
#
# Anything other than INCLUDE_PRIVATE=true (unset, "1", "yes") builds the public site: a
# misconfigured site fails safe, toward publishing less.
set -euo pipefail

TWINS_WORLDS_DEFAULT="gas-station oil-refinery refinery-dusk purnell-test-shop purnell-spools"

# The guide links the cloud setup script through a symlink; publish a real copy.
rm -f app/cloud-env-setup.sh
cp scripts/cloud-env-setup.sh app/cloud-env-setup.sh

if [[ "${INCLUDE_PRIVATE:-}" == "true" ]]; then
  worlds="${TWINS_WORLDS:-$TWINS_WORLDS_DEFAULT}"
  echo "[netlify-build] INCLUDE_PRIVATE=true: publishing only: $worlds (this site must be password-protected)"
  python3 tools/strip_private.py app --only "$worlds"
  cat > app/_headers <<'EOF'
/*
  X-Robots-Tag: noindex, nofollow
EOF
else
  python3 tools/strip_private.py app
fi
