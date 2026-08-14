#  Copyright 2026 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Configuration variables and shared custom exception definition."""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
WORKSPACE_DIR = os.path.abspath(os.path.join(SKILL_DIR, "..", ".."))

TEMPLATE_PATH = os.path.join(SKILL_DIR, "assets", "report_template.md")
OUTPUT_DIR = os.path.join(SKILL_DIR, "output")
ANALYSIS_PATH = os.path.join(
    OUTPUT_DIR, "GKE_Ingress_to_Gateway_API_Migration_Analysis_Report.md"
)
BIN_DIR = os.path.join(SKILL_DIR, "bin")

# Configurable timeout for reading interactive user response on stdin (seconds).
# Defaults to 120.0 seconds if not set
if "--no-timeout" in sys.argv:
    # Waits indefinitely for a response
    STDIN_TIMEOUT = None
else:
    # Environment variable takes precedence over default value
    env_timeout = os.environ.get("MIGRATION_AGENT_TIMEOUT")
    if env_timeout is not None:
        try:
            val = float(env_timeout)
            STDIN_TIMEOUT = None if val <= 0 else val
        except ValueError:
            # Invalid value, default to 120.0 seconds
            STDIN_TIMEOUT = 120.0
    else:
        # No environment variable set, default to 120.0 seconds
        STDIN_TIMEOUT = 120.0


class MigrationError(Exception):
    pass
