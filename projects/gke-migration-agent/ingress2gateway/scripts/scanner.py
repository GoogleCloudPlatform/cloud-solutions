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

"""Scanner module to discover and profile risk of Ingress resources."""

import json
from json import JSONDecodeError
from typing import Any, Dict, List, Tuple

from cluster_client import run_command
from config import MigrationError


def scan_ingresses() -> List[Dict[str, Any]]:
    """Gathers an exhaustive list of all active cluster Ingress manifests.

    Queries the Kubernetes cluster across all namespaces using kubectl and
    parses the JSON response.

    Returns:
        A list of dictionaries representing the raw Kubernetes Ingress items.

    Raises:
        MigrationError: If the kubectl query fails or the returned JSON data
            cannot be parsed.
    """
    raw_ingress = run_command(["kubectl", "get", "ingress", "-A", "-o", "json"])
    if not raw_ingress:
        return []
    try:
        return json.loads(raw_ingress).get("items", [])
    except (MigrationError, JSONDecodeError) as e:
        raise MigrationError(
            f"Failed to parse cluster Ingress configurations: {e}"
        ) from e


def profile_risks(
    ingresses: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Evaluates the footprint of discovered Ingress manifests.

    Separates the manifests into clear transformations (Green lane) or
    blocker layouts requiring custom intervention (Red lane).

    Args:
        ingresses: A list of raw Kubernetes Ingress item dictionaries.

    Returns:
        A tuple of two lists `(green_lane, red_lane)` containing summarized
        asset information dictionaries for clean and blocked resources.
    """

    green_lane: List[Dict[str, Any]] = []
    red_lane: List[Dict[str, Any]] = []

    for ing in ingresses:
        metadata = ing.get("metadata", {})
        namespace = metadata.get("namespace", "default")
        name = metadata.get("name", "unknown")
        annotations = metadata.get("annotations", {})

        # Check for custom rewrite snippets or configurations that break
        # standard specs

        has_snippet = any(
            k
            for k in annotations
            if "snippet" in k or "configuration-snippet" in k
        )

        # Extract operational rules details for documentation metrics
        rules = ing.get("spec", {}).get("rules", [])
        rules_summary_list = []
        for r in rules:
            host = r.get("host", "*")
            paths_count = len(r.get("http", {}).get("paths", []))
            rules_summary_list.append(f"{host} (Paths: {paths_count})")

        rules_summary = ", ".join(rules_summary_list)
        if not rules_summary:
            rules_summary = "Default Backend Fallback Routing"

        asset_info = {
            "namespace": namespace,
            "name": name,
            "rules": rules_summary,
            "controller": annotations.get("kubernetes.io/ingress.class", "gce"),
        }

        if has_snippet:
            red_lane.append(asset_info)
        else:
            green_lane.append(asset_info)

    return green_lane, red_lane
