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

"""External data source script fetching GEAP agent ID for Terraform.

Invoked by Terraform's `data "external" "geap_agent"` after
`null_resource.deploy_geap_agent` completes. Fails loudly with a non-zero exit
code if the project ID is missing, the Vertex AI API call fails, or no
matching `aegis-anomaly-mitigation-agent` Reasoning Engine exists.
"""

import json
import os
import sys

import google.auth.exceptions
import vertexai
from google.api_core.exceptions import GoogleAPICallError
from vertexai.preview import reasoning_engines

_VERTEXAI_EXCEPTIONS: tuple[type[Exception], ...] = (
    GoogleAPICallError,
    google.auth.exceptions.GoogleAuthError,
    ValueError,
    TypeError,
    KeyError,
    RuntimeError,
    OSError,
)


def main() -> None:
    """Fetch the deployed GEAP agent ID and print JSON to stdout."""
    input_data: dict[str, str] = {}
    if not sys.stdin.isatty():
        try:
            raw_stdin = sys.stdin.read().strip()
            if raw_stdin:
                input_data = json.loads(raw_stdin)
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            sys.stderr.write(
                f"Failed to parse Terraform external query JSON: {exc}\n"
            )
            sys.exit(1)

    project_id = (
        input_data.get("project_id")
        or os.environ.get("GCP_PROJECT")
        or os.environ.get("PROJECT_ID")
        or ""
    ).strip()
    region = (
        input_data.get("region")
        or os.environ.get("GCP_REGION")
        or os.environ.get("REGION")
        or "us-central1"
    ).strip()

    if not project_id:
        sys.stderr.write(
            "Error discovering GEAP agent ID: 'project_id' (or GCP_PROJECT) "
            "is required.\n"
        )
        sys.exit(1)

    try:
        vertexai.init(project=project_id, location=region)
        engines = reasoning_engines.ReasoningEngine.list()
        for engine in engines:
            if (
                getattr(engine, "display_name", "")
                == "aegis-anomaly-mitigation-agent"
            ):
                agent_id = engine.resource_name.split("/")[-1]
                print(
                    json.dumps(
                        {
                            "agent_id": str(agent_id),
                            "resource_name": str(engine.resource_name),
                        }
                    )
                )
                return
    except _VERTEXAI_EXCEPTIONS as exc:
        sys.stderr.write(
            f"Error querying Vertex AI Reasoning Engines in project "
            f"'{project_id}' ({region}): {exc}\n"
        )
        sys.exit(1)

    sys.stderr.write(
        "Error: No Vertex AI Reasoning Engine with display_name "
        f"'aegis-anomaly-mitigation-agent' found in project '{project_id}' "
        f"({region}). Ensure deploy_geap.py succeeded before querying.\n"
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
