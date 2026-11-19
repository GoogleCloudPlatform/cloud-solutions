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

# pylint: disable=line-too-long,wrong-import-position

"""Validate platform configuration before any deploy (`make config-check ENV=<env>`).

Checks the layered config (schema, unique tenants and CMEK keys, file/tenant ID match) and that the
target project is real (no placeholder) when deploying. Exits non-zero on any problem.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.platform_config import (
    PLACEHOLDER_PROJECT_IDS,
    available_environments,
    load_platform_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env", default="sandbox", help=f"one of {available_environments()}"
    )
    parser.add_argument(
        "--for-deploy",
        action="store_true",
        help="also require a real (non-placeholder) project",
    )
    args = parser.parse_args()

    try:
        cfg = load_platform_config(args.env)
    except (OSError, TypeError, ValueError, yaml.YAMLError) as exc:
        # pydantic.ValidationError subclasses ValueError; anything else is a bug and should crash.
        print(f"[CONFIG ERROR] {args.env}: {exc}", file=sys.stderr)
        return 1

    problems = []
    if not cfg.tenants:
        problems.append(f"no tenants in config/{cfg.tenants_dir}")
    if args.for_deploy and cfg.gcp.project_id in PLACEHOLDER_PROJECT_IDS:
        problems.append(
            f"gcp.project_id is a placeholder in config/environments/{args.env}.yaml"
        )

    summary = {
        "environment": cfg.environment,
        "data_classification": cfg.data_classification,
        "project_id": cfg.gcp.project_id,
        "region": cfg.gcp.region,
        "tenants": {
            t.tenant_id: {
                "tier": t.tier,
                "issuer": t.identity.issuer,
                "cmek_key": cfg.kms_key_name(t.cmek_key),
                "row_policy": t.row_policy_id(),
            }
            for t in cfg.tenants
        },
        "problems": problems,
    }
    print(json.dumps(summary, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
