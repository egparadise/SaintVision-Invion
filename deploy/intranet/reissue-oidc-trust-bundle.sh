#!/usr/bin/env bash
# Reissue the control plane's OIDC trust bundle from the live IdP.
#
# Run on the control-plane host, where identity.jwks_file lives.
#
# The bundle the control plane trusts expires at most seven days out -- that is the
# verifier's rule, not a convention -- so this has to run on a schedule or the
# control plane stops accepting tokens. The timer beside this script runs it DAILY,
# not weekly: with a seven-day bundle and a weekly job, one failed run is an
# outage. Daily leaves six days of margin to notice.
#
# Nothing is replaced unless the new bundle is complete and acceptable: the builder
# writes only what the verifier would accept, this script builds to a temporary file
# first, and the old bundle stays in place on any failure.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${SV_REPO:-$(cd "$HERE/../.." && pwd)}"
PYTHON="${SV_PYTHON:-python3}"

ISSUER="${SV_OIDC_ISSUER:?set SV_OIDC_ISSUER to exactly the configured identity.issuer}"
JWKS_URL="${SV_OIDC_JWKS_URL:-$ISSUER/protocol/openid-connect/certs}"
DEST="${SV_OIDC_BUNDLE:?set SV_OIDC_BUNDLE to the configured identity.jwks_file}"

umask 022
TMP="$(mktemp "${DEST}.new.XXXXXX")"
trap 'rm -f "$TMP"' EXIT

"$PYTHON" "$REPO/tools/make_oidc_trust_bundle.py" \
  --issuer "$ISSUER" --jwks-url "$JWKS_URL" --output "$TMP" --force

# Read it back the way the verifier will, before anything is replaced.
"$PYTHON" - "$REPO" "$TMP" "$ISSUER" <<'PY'
import datetime as dt, json, sys
sys.path.insert(0, sys.argv[1])
from tools.make_oidc_trust_bundle import BundleRefused, validate_bundle

bundle = json.loads(open(sys.argv[2], encoding="utf-8").read())
validate_bundle(bundle, now=dt.datetime.now(dt.timezone.utc))
if bundle["issuer"] != sys.argv[3]:
    raise BundleRefused("issuer does not match the configured issuer")
PY

chmod 644 "$TMP"
mv -f "$TMP" "$DEST"
trap - EXIT
echo "reissued $DEST from $JWKS_URL"
