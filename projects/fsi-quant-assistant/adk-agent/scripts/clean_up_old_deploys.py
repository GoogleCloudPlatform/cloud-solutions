#!/usr/bin/env python3

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Script to clean up old Vertex AI Agent Engines."""

import argparse
import os

import vertexai

PROJECT_ID = os.environ.get("PROJECT_ID", "finance-bundle-1001")
REGION = os.environ.get("REGION", "us-central1")


def cleanup_old_agents(display_name: str, keep_count: int = 1):
    """
    Lists Vertex AI Agent Engines with a specific display name,
    sorts them by creation time, and deletes all but the latest ones.

    Args:
        display_name: The display_name to filter the agents by.
        keep_count: The number of most recent agents to keep.
    """
    print(
        f"--- Starting Agent Cleanup for Display Name: **{display_name}** ---"
    )
    client = vertexai.Client(
        project=PROJECT_ID,
        location=REGION,
    )

    agents = []

    # 1. Retrieve the list of agents
    for a in client.agent_engines.list(
        config={"filter": f'display_name="{display_name}"'},
    ):
        agents.append(a)

    # 2. Sort the list of agents by create_time
    # The key for sorting is the 'create_time' property inside the
    # 'api_resource'.
    # We use 'reverse=True' to put the newest agent (latest time) first.
    sorted_agents = sorted(
        agents, key=lambda agent: agent.api_resource.create_time, reverse=True
    )

    print(
        f"Found {len(sorted_agents)} agents with display_name='{display_name}'."
    )

    if not sorted_agents:
        print("No agents found. Exiting.")
        return

    # 3. Identify agents to keep and cleanup
    agents_to_keep = sorted_agents[:keep_count]
    old_agents_for_cleanup = sorted_agents[keep_count:]

    print(f"\n--- Keeping {len(agents_to_keep)} Agent(s) ---")
    for agent in agents_to_keep:
        print(
            f"Name: {agent.api_resource.name} | "
            f"Created: {agent.api_resource.create_time}"
        )

    if old_agents_for_cleanup:
        print(
            f"\n--- {len(old_agents_for_cleanup)} Old Agent(s) to Clean Up ---"
        )
        for old_agent in old_agents_for_cleanup:
            print(
                f"Name: {old_agent.api_resource.name} | "
                f"Created: {old_agent.api_resource.create_time}"
            )

            old_agent.delete(
                # Optional, if the agent has resources (e.g. sessions, memory)
                force=True,
            )

            print(f"-> Deleted {old_agent.api_resource.name}")
    else:
        print(
            f"\nNo old agents to clean up (found {len(sorted_agents)}, "
            f"keeping {keep_count})."
        )


def main():
    """
    Parses command-line arguments and calls the cleanup function.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Clean up old Vertex AI Agent Engines, keeping only the latest one."
        )
    )
    # Add the required command-line argument
    parser.add_argument(
        "-d",
        "--display_name",
        type=str,
        required=True,
        help="The display name of the Agent Engines to filter and clean up.",
    )

    parser.add_argument(
        "-k",
        "--keep",
        type=int,
        default=1,
        help=(
            "Number of recent agents to keep (default: 1). "
            "Set to 0 to delete all."
        ),
    )

    args = parser.parse_args()

    # Pass the argument to the cleanup function
    cleanup_old_agents(args.display_name, args.keep)


if __name__ == "__main__":
    main()
