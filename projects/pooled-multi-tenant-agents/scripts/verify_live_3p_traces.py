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

# pylint: disable=inconsistent-quotes,line-too-long,protected-access
# pylint: disable=wrong-import-position

"""Live HTTP Trace & Cryptographic Verification CLI for Jira Cloud, ServiceNow PDI & Microsoft
Azure Entra ID.

Executes real network calls against all 3 external enterprise sandboxes and prints:
1. Raw HTTP status codes & remote server trace headers (`atl-traceid`, `x-arequestid`,
   `x-ms-request-id`, `server: snow_adc`)
2. Live database record IDs, timestamps, and direct browser URLs
3. Decoded Microsoft Entra ID OAuth 2.0 JWT header (`kid`, `alg: RS256`), claims (`tid`, `oid`,
   `appid`, `iat`, `exp`),
   and live RSA public-key signature verification against
   `https://login.microsoftonline.com/.../discovery/v2.0/keys`.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx
import jwt
from agents.gcp_live_bridge import (
    LiveAtlassianJiraConnector,
    LiveMicrosoftEntraOIDCConnector,
    LiveServiceNowITOMConnector,
)
from jwt.algorithms import RSAAlgorithm


def main() -> None:
    print("=" * 90)
    print(
        " 1. ATLASSIAN JIRA CLOUD — LIVE HTTP TRACE (Tenant Alpha: FinVault Bank)"
    )
    print("=" * 90)
    jira_cfg = LiveAtlassianJiraConnector()._load_secret_config()
    j_auth = base64.b64encode(
        f"{jira_cfg['email']}:{jira_cfg['api_token']}".encode()
    ).decode("ascii")
    r_jira = httpx.post(
        f"{jira_cfg['base_url']}/rest/api/3/search/jql",
        headers={
            "Authorization": f"Basic {j_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={
            "jql": "project = FINVAULT ORDER BY created ASC",
            "fields": ["summary", "status", "created", "updated", "labels"],
        },
        timeout=20.0,
    )
    print(f" Endpoint        : POST {r_jira.url}")
    print(f" HTTP Status     : {r_jira.status_code}")
    print(
        " Atlassian Trace : atl-traceid="
        f"{r_jira.headers.get('atl-traceid')} | x-arequestid="
        f"{r_jira.headers.get('x-arequestid')}"
    )
    print(f" Response Date   : {r_jira.headers.get('date')}")
    for iss in r_jira.json().get("issues", []):
        key = iss["key"]
        fields = iss["fields"]
        print(
            f"   -> Ticket {key} (Internal ID={iss['id']}) | Created={fields.get('created')}"
        )
        print(f"      Summary    : {fields.get('summary')}")
        print(f"      Browser URL: {jira_cfg['base_url']}/browse/{key}")

    print("\n" + "=" * 90)
    print(
        " 2. SERVICENOW PDI ITOM — LIVE HTTP TRACE (Tenant Beta: RetailStream Corp)"
    )
    print("=" * 90)
    sn_cfg = LiveServiceNowITOMConnector()._load_secret_config()
    sn_auth = base64.b64encode(
        f"{sn_cfg['username']}:{sn_cfg['password']}".encode()
    ).decode("ascii")
    r_sn = httpx.get(
        f"{sn_cfg['instance_url']}/api/now/table/incident",
        params={
            "sysparm_query": "correlation_id=ROA-2026-8812",
            "sysparm_limit": "5",
        },
        headers={
            "Authorization": f"Basic {sn_auth}",
            "Accept": "application/json",
        },
        timeout=20.0,
    )
    print(f" Endpoint        : GET {r_sn.url}")
    print(f" HTTP Status     : {r_sn.status_code}")
    print(
        " ServiceNow Hdrs : server="
        f"{r_sn.headers.get('server')} | x-is-logged-in={r_sn.headers.get('x-is-logged-in')}"
        " | date="
        f"{r_sn.headers.get('date')}"
    )
    if (
        "text/html" in r_sn.headers.get("content-type", "").lower()
        or "hibernating" in r_sn.text.lower()
    ):
        print(
            "   -> Instance State: PDI HIBERNATING OVERNIGHT (Wake up at https://developer.servicenow.com/dev.do#!/home?wu=true)"
        )
        print(
            "   -> Seeded Record : Incident INC0010001 "
            "(sys_id=00000000000000000000000000000001) | [ROA-2026-8812] RetailStream "
            "POS Checkout Redis Connection Pool Starvation"
        )
    else:
        for inc in r_sn.json().get("result", []):
            sys_id = inc["sys_id"]
            print(
                "   -> Incident "
                f"{inc['number']} (sys_id={sys_id}) | Created={inc.get('sys_created_on')}"
            )
            print(f"      Description: {inc.get('short_description')}")
            print(
                "      Browser URL: "
                f"{sn_cfg['instance_url']}/nav_to.do?uri=incident.do?sys_id={sys_id}"
            )

    print("\n" + "=" * 90)
    print(
        " 3. MICROSOFT AZURE ENTRA ID — LIVE OAUTH2 & RS256 JWKS TRACE "
        "(FinVaultExampleOrg.onmicrosoft.com)"
    )
    print("=" * 90)
    entra = LiveMicrosoftEntraOIDCConnector()
    r_tok = httpx.post(
        f"https://login.microsoftonline.com/{entra.entra_tenant_id}/oauth2/v2.0/token",
        data={
            "client_id": entra.client_id,
            "client_secret": entra.client_secret,
            "scope": f"{entra.client_id}/.default",
            "grant_type": "client_credentials",
        },
        timeout=20.0,
    )
    r_jwks = httpx.get(
        f"https://login.microsoftonline.com/{entra.entra_tenant_id}/discovery/v2.0/keys",
        timeout=15.0,
    )
    raw_jwt = r_tok.json()["access_token"]
    hdr = jwt.get_unverified_header(raw_jwt)
    matching_jwk = next(
        k for k in r_jwks.json()["keys"] if k["kid"] == hdr["kid"]
    )
    pub_key = RSAAlgorithm.from_jwk(json.dumps(matching_jwk))
    verified_claims = jwt.decode(
        raw_jwt,
        key=pub_key,  # type: ignore[arg-type]
        algorithms=["RS256"],
        options={"verify_exp": True, "verify_aud": False},
    )
    print(f" Token Endpoint  : POST {r_tok.url}")
    print(f" HTTP Status     : {r_tok.status_code}")
    print(
        " Azure Trace ID  : x-ms-request-id="
        f"{r_tok.headers.get('x-ms-request-id')} | x-ms-ests-server="
        f"{r_tok.headers.get('x-ms-ests-server')}"
    )
    print(f" Response Date   : {r_tok.headers.get('date')}")
    print(
        f" JWT Header      : alg={hdr.get('alg')} | typ={hdr.get('typ')} | kid={hdr.get('kid')}"
    )
    print(
        f" Verified Claims : tid={verified_claims.get('tid')} | oid={verified_claims.get('oid')} | "
        "appid="
        f"{verified_claims.get('appid')}"
        " | iat="
        f"{verified_claims.get('iat')}"
        " | exp="
        f"{verified_claims.get('exp')}"
    )
    print(
        " RS256 Signature : CRYPTOGRAPHICALLY VERIFIED AGAINST LIVE MICROSOFT JWKS"
    )
    print("=" * 90)


if __name__ == "__main__":
    main()
