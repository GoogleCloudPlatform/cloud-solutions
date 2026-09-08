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

"""External data source script fetching GEAP agent ID for Terraform."""

import json
import os
import sys

try:
    import google.auth.exceptions
    import vertexai
    from google.api_core.exceptions import GoogleAPICallError
    from vertexai.preview import reasoning_engines

    HAVE_VERTEXAI = True
    _VERTEXAI_EXCEPTIONS: tuple[type[Exception], ...] = (
        GoogleAPICallError,
        google.auth.exceptions.GoogleAuthError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        OSError,
    )
except ImportError:
    vertexai = None  # type: ignore[assignment]
    reasoning_engines = None  # type: ignore[assignment]
    HAVE_VERTEXAI = False
    _VERTEXAI_EXCEPTIONS = (
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        OSError,
    )


def main():
    """Fetches or discovers the GEAP agent ID and returns JSON to stdout."""
    try:
        input_data = {}
        if not sys.stdin.isatty():
            try:
                input_data = json.load(sys.stdin)
            except (json.JSONDecodeError, ValueError, OSError):
                pass

        project_id = (
            input_data.get("project_id")
            or os.environ.get("GCP_PROJECT")
            or os.environ.get("PROJECT_ID", "aegis-streaming-1001")
        )
        region = (
            input_data.get("region")
            or os.environ.get("GCP_REGION")
            or os.environ.get("REGION", "us-central1")
        )

        if (
            HAVE_VERTEXAI
            and vertexai is not None
            and reasoning_engines is not None
        ):
            try:
                vertexai.init(project=project_id, location=region)
                engines = reasoning_engines.ReasoningEngine.list()
                for e in engines:
                    if (
                        getattr(e, "display_name", "")
                        == "aegis-anomaly-mitigation-agent"
                    ):
                        agent_id = e.resource_name.split("/")[-1]
                        print(
                            json.dumps(
                                {
                                    "agent_id": str(agent_id),
                                    "resource_name": str(e.resource_name),
                                }
                            )
                        )
                        return
            except _VERTEXAI_EXCEPTIONS:
                pass

        res_name = (
            f"projects/815700298786/locations/{region}/"
            "reasoningEngines/8078632548026023936"
        )
        print(
            json.dumps(
                {
                    "agent_id": "8078632548026023936",
                    "resource_name": res_name,
                }
            )
        )
    except _VERTEXAI_EXCEPTIONS as ex:
        sys.stderr.write(f"Error discovering GEAP agent ID: {ex}\n")
        print(
            json.dumps(
                {
                    "agent_id": "8078632548026023936",
                    "resource_name": "",
                    "error": "Failed to discover GEAP agent ID.",
                }
            )
        )


if __name__ == "__main__":
    main()
