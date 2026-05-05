# Copyright 2026 Google LLC
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

# pylint: disable=C0114, C0301, W0102

from pathlib import Path

from dotenv import load_dotenv  # type: ignore


def load_env_cascade(current_file: str, dependency_paths: list[str] = []) -> None:
    """
    Loads .env files in a specific precedence order (First Loaded Wins).

    Args:
        current_file: Pass __file__ of the calling agent.
        dependency_paths: Relative paths to other agents (e.g., ['../ad_generation_agent'])
    """
    # 1. Load the current agent's .env (Highest Priority)
    # Assumes standard structure: agent_dir/src/pkg -> agent_dir/
    # If standard structure is different, adjust accordingly.
    # Current structure seems to be:
    # agent_dir/agent_pkg/agent.py -> parent of parent is agent_dir

    current_path = Path(current_file).resolve()

    # Heuristic to find the "root" of the agent to locate .env
    # We look for pyproject.toml
    agent_root = current_path.parent
    while agent_root.name and not (agent_root / "pyproject.toml").exists():
        if agent_root == agent_root.parent: # Reached mounting point
            break
        agent_root = agent_root.parent

    if (agent_root / "pyproject.toml").exists():
        load_dotenv(agent_root / ".env")
    else:
        # Fallback to simple parent traversal if pyproject.toml not found (unlikely)
        load_dotenv(current_path.parent.parent / ".env")

    # 2. Load dependencies (Lower Priority - fill in gaps)
    for dep in dependency_paths:
        # resolve dependency path relative to the agent root
        dep_path = (agent_root / dep / ".env").resolve()
        if dep_path.exists():
            load_dotenv(dep_path)
