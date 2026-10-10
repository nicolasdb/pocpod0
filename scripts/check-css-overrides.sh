#!/usr/bin/env bash
# Are our Community Solid Server customisations still applied, and still valid?
#
# Our look and copy live OUTSIDE the image, as read-only bind mounts
# (docker-compose.yml) plus static assets declared in infra/css/config.json.
# So pulling a new image never erases them — but it can silently invalidate
# them: an override is a whole-file copy of a stock template, and if upstream
# changes that template (new EJS variable, renamed form id), ours keeps
# shipping the old one. Two checks, run after any image change:
#
#   1. upstream  — hash the stock templates inside IMAGE (mounts not applied)
#                  against infra/css/upstream-baseline.sha256. A mismatch means
#                  re-diff upstream vs ours and merge before deploying.
#   2. served    — against a running server at URL, that what it serves is ours.
#
# Usage:
#   scripts/check-css-overrides.sh [IMAGE] [URL] [MD_URL]
#   scripts/check-css-overrides.sh --rebaseline [IMAGE]   # after merging
# Runs locally (podman) or on the VPS (docker): CONTAINER_CLI overrides.
set -uo pipefail
cd "$(dirname "$0")/.."

CLI="${CONTAINER_CLI:-$(command -v docker || echo podman)}"
[ -f /run/.containerenv ] && [ -z "${CONTAINER_CLI:-}" ] && CLI="distrobox-host-exec podman"
BASELINE=infra/css/upstream-baseline.sha256
IMAGE_DEFAULT="$(sed -n 's/^ *image: *\(solidproject\/community-server:.*\)$/\1/p' docker-compose.yml | head -1)"

stock_hashes() { # image -> "hash  path" lines for every overridden template
  local paths; paths="$(grep -v '^#' "$BASELINE" | awk '{print $2}' | sed 's/\$/\\$/g' | tr '\n' ' ')"
  $CLI run --rm --entrypoint sh "$1" -c "cd /community-server/templates && sha256sum $paths"
}

if [ "${1:-}" = "--rebaseline" ]; then
  image="${2:-$IMAGE_DEFAULT}"
  { grep '^#' "$BASELINE" | grep -v '^# image:'; echo "# image: $image"; stock_hashes "$image"; } > "$BASELINE.new" \
    && mv "$BASELINE.new" "$BASELINE" && echo "rebaselined against $image"
  exit
fi

image="${1:-$IMAGE_DEFAULT}"; url="${2:-}"; md_url="${3:-}"
fail=0
ok()  { echo "  ok    $*"; }
bad() { echo "  FAIL  $*"; fail=1; }

echo "1. upstream templates in $image vs $BASELINE"
actual="$(stock_hashes "$image")" || { bad "could not read templates from $image"; exit 1; }
while read -r hash path; do
  if grep -qF "$hash  $path" <<<"$actual"; then ok "$path unchanged upstream"
  else bad "$path CHANGED upstream: diff it against infra/css/, merge, then --rebaseline"; fi
done < <(grep -v '^#' "$BASELINE")

if [ -n "$url" ]; then
  url="${url%/}"
  echo "2. served by $url"
  page="$(curl -fsS -H "Accept: text/html" "$url/.account/login/password/")" || bad "login page unreachable"
  grep -q "Stale-sign-in self-repair" <<<"$page" && ok "main.html.ejs is ours" || bad "main.html.ejs is stock"
  grep -q "doc-view.js" <<<"$page" && ok "template loads doc-view.js" || bad "template does not load doc-view.js"
  curl -fsS "$url/.well-known/css/styles/main.css" | grep -q "Story 7.2" && ok "main.css is ours" || bad "main.css is stock"
  for a in tokens.css doc-view.css doc-view.js; do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$url/$a")"
    [ "$code" = 200 ] && ok "/$a served" || bad "/$a -> $code (config.json StaticAssetEntry or mount)"
  done
  if [ -n "$md_url" ]; then
    curl -fsS -H 'Accept: text/html' "$md_url" | grep -q "doc-view.js" && ok ".md page carries doc-view" || bad ".md page lacks doc-view"
  fi
fi

[ "$fail" = 0 ] && echo "all checks passed" || echo "CHECKS FAILED"
exit "$fail"
