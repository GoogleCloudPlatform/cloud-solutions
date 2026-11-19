#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ============================================================================
# Atlassian Jira API Token Rotator (Secret Manager is the single source of truth)
#
#   1. Verifies the NEW token against Jira Cloud (/rest/api/3/myself) before storing it.
#   2. Adds a new version to GCP Secret Manager (cymbal-finvault-jira-credentials).
#      This step is mandatory: the script fails if gcloud is not authenticated.
#   3. Disables older secret versions so a stale token can never be read again.
#   4. Optionally updates a local .env (offline sandbox only) with --also-update-local-env.
#
# Live mode never reads Jira credentials from .env; see docs/secrets_management.md.
#
# Usage:
#   ./scripts/rotate_jira_api_token.sh "<NEW_JIRA_API_TOKEN>" [--also-update-local-env]
# ============================================================================
set -euo pipefail

if [[ $# -lt 1 || -z "${1:-}" ]]; then
  echo "Usage: ./scripts/rotate_jira_api_token.sh \"<NEW_JIRA_API_TOKEN>\" [--also-update-local-env]"
  echo ""
  echo "1. Create a new token at: https://id.atlassian.com/manage-profile/security/api-tokens"
  echo "2. Run: ./scripts/rotate_jira_api_token.sh \"<PASTE_TOKEN_HERE>\""
  exit 1
fi

NEW_TOKEN="$1"
UPDATE_LOCAL_ENV="${2:-}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-cymbal-multitenancy-example}"
SECRET_ID="cymbal-finvault-jira-credentials"
export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.ai-agent"

# 0. gcloud must be authenticated: Secret Manager is not optional.
if ! gcloud auth print-access-token >/dev/null 2>&1; then
  echo "ERROR: gcloud is not authenticated. Run:"
  echo "  gcloud auth login <admin-account> --force --no-launch-browser"
  echo "Nothing was changed."
  exit 1
fi

# 1. Build the new payload from the CURRENT secret (keeps base_url/email/project_key) and verify
#    the new token against Jira before storing anything. The token is never printed.
CURRENT_SECRET=$(gcloud secrets versions access latest --secret="$SECRET_ID" --project="$PROJECT_ID")
NEW_PAYLOAD=$(
  CURRENT_SECRET="$CURRENT_SECRET" NEW_TOKEN="$NEW_TOKEN" python3 - <<'PY'
import base64, json, os, sys, urllib.error, urllib.request
cfg = json.loads(os.environ["CURRENT_SECRET"])
cfg["api_token"] = os.environ["NEW_TOKEN"].strip()
auth = base64.b64encode(f"{cfg['email']}:{cfg['api_token']}".encode()).decode()
req = urllib.request.Request(
  f"{cfg['base_url']}/rest/api/3/myself",
  headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
)
try:
  status = urllib.request.urlopen(req, timeout=20).status
except urllib.error.HTTPError as exc:
  status = exc.code
if status != 200:
  sys.exit(f"ERROR: Jira rejected the new token (HTTP {status}). Nothing was changed.")
sys.stdout.write(json.dumps(cfg))
PY
)
unset CURRENT_SECRET
echo "[1/4] New token verified against Jira Cloud (/myself = 200)"

# 2. Store it in Secret Manager (hard failure if this does not succeed).
NEW_VERSION=$(printf "%s" "$NEW_PAYLOAD" | gcloud secrets versions add "$SECRET_ID" \
  --project="$PROJECT_ID" --data-file=- --format="value(name)")
NEW_VERSION="${NEW_VERSION##*/}"
echo "[2/4] Added Secret Manager version $NEW_VERSION of $SECRET_ID ($PROJECT_ID)"

# 3. Disable every older enabled version so stale tokens cannot be read.
for v in $(gcloud secrets versions list "$SECRET_ID" --project="$PROJECT_ID" \
  --filter="state=ENABLED" --format="value(name)"); do
  v="${v##*/}"
  if [[ "$v" != "$NEW_VERSION" ]]; then
    gcloud secrets versions disable "$v" --secret="$SECRET_ID" --project="$PROJECT_ID" --format=none
    echo "[3/4] Disabled stale version $v"
  fi
done

# 4. Optional: offline sandbox .env (never read in live mode).
if [[ "$UPDATE_LOCAL_ENV" == "--also-update-local-env" && -f "$REPO_DIR/.env" ]]; then
  NEW_TOKEN="$NEW_TOKEN" python3 - "$REPO_DIR/.env" <<'PY'
import os, re, sys
from pathlib import Path
p = Path(sys.argv[1]); text = p.read_text(encoding="utf-8")
line = f"JIRA_API_TOKEN={os.environ['NEW_TOKEN'].strip()}"
text = re.sub(r"^JIRA_API_TOKEN=.*$", line, text, flags=re.M) if re.search(r"^JIRA_API_TOKEN=", text, flags=re.M) else text.rstrip() + f"\n{line}\n"
p.write_text(text, encoding="utf-8")
PY
  echo "[4/4] Updated offline-sandbox .env (live mode ignores it)"
else
  echo "[4/4] Local .env not touched (live mode reads Secret Manager only)"
fi
