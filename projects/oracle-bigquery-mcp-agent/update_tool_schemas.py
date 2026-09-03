#!/usr/bin/env python3

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

"""Updates Dialogflow CX OpenAPI tool schemas with endpoint and webhook token.

Replaces placeholders with live Cloud Run MCP service URI and secret token.
"""

import re
import sys


def update_schemas(mcp_uri: str, mcp_token: str, filepaths: list[str]) -> None:
    """Updates OpenAPI schema files with service URI and webhook token."""
    for filepath in filepaths:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        text_updated = re.sub(r"url:\s*https://\S+", f"url: {mcp_uri}", text)
        if mcp_token:
            text_updated = text_updated.replace(
                "YOUR_MCP_WEBHOOK_TOKEN", mcp_token
            )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text_updated)


def main() -> None:
    """Entrypoint parsing CLI arguments and updating schema files."""
    if len(sys.argv) < 3:
        print(
            "Usage: update_tool_schemas.py <mcp_uri> <mcp_token> "
            "[schema_files...]",
            file=sys.stderr,
        )
        sys.exit(1)

    mcp_uri = sys.argv[1]
    mcp_token = sys.argv[2]
    schema_files = sys.argv[3:]

    update_schemas(mcp_uri, mcp_token, schema_files)


if __name__ == "__main__":
    main()
