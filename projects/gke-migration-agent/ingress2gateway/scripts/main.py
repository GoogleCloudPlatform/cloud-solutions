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

"""Main orchestrator for GKE Ingress to Gateway API migration sequence."""

import json
import logging
import os
import sys
import tempfile
from typing import Any, Dict, List, Tuple

import cluster_client

# Import our custom decoupled workspace modules
import config
import report_engine
import scanner
import state_manager
import translator
import yaml
from config import MigrationError


def discover_clusters() -> Tuple[str, str]:
    """Discovers GKE clusters and prompts the operator to select one.

    Following user selection, it configures the cluster as the active cluster.

    Returns:
        A tuple of (chosen_cluster_name, chosen_cluster_location).

    Raises:
        MigrationError: If no GKE clusters are found or configuration fails.
    """
    cluster_client.run_command(["gcloud", "config", "get-value", "account"])

    project = cluster_client.run_command(
        ["gcloud", "config", "get-value", "project"]
    )

    clusters_output = cluster_client.run_command(
        ["gcloud", "container", "clusters", "list", "--format=json"]
    )
    clusters = json.loads(clusters_output)
    if not clusters:
        raise MigrationError(
            "Zero valid GKE cluster components found under this active "
            "cloud identity."
        )

    cluster_list = [
        {"id": i, "name": c["name"], "location": c["location"]}
        for i, c in enumerate(clusters)
    ]

    # Dispatch JSON UI payload to prompt operator for target cluster choice
    cluster_client.emit_ui_payload(
        step_name="Cluster Targeting Selection",
        prompt_type="select_cluster",
        data={"project": project, "clusters": cluster_list},
    )

    logging.info("⏳ Waiting for operator cluster selection via UI panel...")
    ui_response_1 = cluster_client.get_ui_response()
    user_selections = ui_response_1.get("user_selections", {})

    chosen_cluster_name = user_selections.get("cluster_name")
    chosen_cluster_loc = user_selections.get("cluster_location")

    if not chosen_cluster_name or not chosen_cluster_loc:
        raise MigrationError(
            "Tracking states disrupted: missing verified cluster "
            "specifications."
        )

    # Mount target credentials locally inside our sandboxed context
    flag = "--region" if len(chosen_cluster_loc.split("-")) == 2 else "--zone"
    cluster_client.run_command(
        [
            "gcloud",
            "container",
            "clusters",
            "get-credentials",
            chosen_cluster_name,
            flag,
            chosen_cluster_loc,
            "--quiet",
        ]
    )

    # Extract cluster version details to populate document metadata header
    cluster_info = next(
        (c for c in clusters if c["name"] == chosen_cluster_name), {}
    )
    cluster_version = cluster_info.get("currentMasterVersion", "Unknown")

    report_engine.update_report_placeholder(
        "[Cluster Context Name]", chosen_cluster_name
    )
    report_engine.update_report_placeholder(
        "[Parsed GKE Master Version]", cluster_version
    )

    return chosen_cluster_name, chosen_cluster_loc


def discover_profile_ingress(chosen_cluster_name: str) -> List[Dict[str, Any]]:
    """Discovers Ingress resources and profiles risks for operator verification.

    Args:
        chosen_cluster_name: The name of the target GKE cluster.

    Returns:
        A list of approved Ingress resources for translation.
    """
    logging.info("\n▶ [PHASE 3] Resource Discovery & Target Inventory")
    ingresses = scanner.scan_ingresses()
    if not ingresses:
        logging.info(
            "\nℹ️  Zero active Ingress resources running "
            "inside target cluster context."
        )

        report_engine.update_report_placeholder(
            "[Populated in Phase 3]",
            "*No active Ingress resources were found in the "
            "target cluster context.*",
        )
        return []

    logging.info("\n▶ [PHASE 4] Ingress scanning & Risk Profiling")
    green_lane, red_lane = scanner.profile_risks(ingresses)

    # Fill Phase 3 Inventory section
    inventory_md = (
        "| Namespace | Ingress Name | Controller Class | Found Rules | "
        "Compatibility Status | Action Required |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
    )
    for g in green_lane:
        g_ns = g["namespace"]
        g_name = g["name"]
        g_ctrl = g["controller"]
        g_rules = g["rules"]
        inventory_md += (
            f"| `{g_ns}` | `{g_name}` | `{g_ctrl}` | {g_rules} | "
            "**Fully Compatible** | Ready to translate automatically. |\n"
        )
    for r in red_lane:
        r_ns = r["namespace"]
        r_name = r["name"]
        r_ctrl = r["controller"]
        r_rules = r["rules"]
        inventory_md += (
            f"| `{r_ns}` | `{r_name}` | `{r_ctrl}` | {r_rules} | "
            "**Review Required** | Custom configuration snippets require "
            "manual mapping. |\n"
        )
    report_engine.update_report_placeholder(
        "[Populated in Phase 3]", inventory_md
    )

    # Incrementally populate Phase 4 Anomalies section
    anomalies_md = "### 🛑 Critical Blockers\n"
    if not red_lane:
        anomalies_md += (
            "* None detected. All targets are valid for automated "
            "routing transitions.\n"
        )
    else:
        for r in red_lane:
            r_ns = r["namespace"]
            r_name = r["name"]
            anomalies_md += (
                f"* **Namespace:** `{r_ns}` | **Resource:** `{r_name}`\n"
                "  * Blocker: Custom native snippet formatting "
                "annotations found. These complicate automated "
                "compilation parsing.\n"
            )
    report_engine.update_report_placeholder(
        "[Populated in Phase 4]", anomalies_md
    )

    # ENFORCED STOP: Emit the UI verification payload regardless of risk status
    cluster_client.emit_ui_payload(
        step_name="Ingress Infrastructure Asset Analysis Gate",
        prompt_type="verify_risks",
        data={
            "cluster": chosen_cluster_name,
            "status": "CLEAN" if not red_lane else "RISKS_FOUND",
            "green_lane_assets": green_lane,
            "red_lane_assets": red_lane,
        },
    )

    logging.info(
        "🛑 [MANDATORY HOLD] Waiting for operator asset approval and "
        "explicit clearance from UI panel to proceed to Phase 5..."
    )
    ui_response_2 = cluster_client.get_ui_response()

    if ui_response_2.get("action") == "CANCEL":
        logging.info(
            "🛑 Migration sequence cancelled by operator at Phase 4 Gate."
        )
        return []

    approved_keys = ui_response_2.get("user_selections", {}).get(
        "approved_ingress_keys", []
    )

    # Auto-select all green lanes if the user approved the clean gate without
    # specifying explicit ingress keys or names.
    if not approved_keys and not red_lane:
        return ingresses

    target_ingresses = []
    for i in ingresses:
        ns = i["metadata"]["namespace"]
        name = i["metadata"]["name"]
        if f"{ns}/{name}" in approved_keys:
            target_ingresses.append(i)

    return target_ingresses


def translate_validate(
    binary_path: str,
    target_ingresses: List[Dict[str, Any]],
    chosen_cluster_name: str,
) -> Tuple[str, str]:
    """Translates approved Ingresses to Gateway API resources and runs dry-run.

    Args:
        binary_path: The file path to the ingress2gateway executable.
        target_ingresses: The approved list of Ingress manifests.
        chosen_cluster_name: The name of the target GKE cluster.

    Returns:
        A tuple of (action, gateway_yaml) from the operator's response.
    """
    logging.info("\n▶ [PHASE 5] Translation & Dry Run validation")
    gateway_yaml = translator.compile_translation(binary_path, target_ingresses)

    # Execute remote server dry-run validation gate
    translator.execute_server_dry_run(gateway_yaml)

    # Format and append translation mapping to the Markdown report file
    ticks = "`" * 3
    bundle = {"apiVersion": "v1", "kind": "List", "items": target_ingresses}
    old_manifests_yaml = yaml.dump(bundle, default_flow_style=False)

    architecture_md = (
        "The legacy parameters mapped directly onto the decoupled "
        "infrastructure framework layout below:\n\n"
    )
    architecture_md += (
        f"#### Target Compiled Manifest Spec\n{ticks}yaml\n"
        + gateway_yaml
        + f"{ticks}"
    )
    report_engine.update_report_placeholder(
        "[Populated in Phase 5 & 6]", architecture_md
    )

    # Request absolute deployment approval from UI operator context
    cluster_client.emit_ui_payload(
        step_name="Architectural Transformation Specification Review",
        prompt_type="approve_deployment",
        data={
            "target_cluster": chosen_cluster_name,
            "source_manifest_summary": old_manifests_yaml,
            "translated_gateway_yaml": gateway_yaml,
        },
    )

    logging.info("⏳ Waiting for final production deployment signature...")
    ui_response_3 = cluster_client.get_ui_response()
    action = ui_response_3.get("action", "DECLINE")
    return action, gateway_yaml


def deploy_gateway(action: str, gateway_yaml: str) -> None:
    """Deploys the generated Gateway API resource or creates a local fallback.

    Args:
        action: The deployment approval response (APPROVE or otherwise).
        gateway_yaml: The translated Gateway API YAML specification.
    """
    ticks = "`" * 3
    if action == "APPROVE":
        logging.info(
            "🚀 Injecting validated Gateway API resources "
            "into live data spaces..."
        )

        stdout = cluster_client.run_command(
            ["kubectl", "apply", "-f", "-"], input_data=gateway_yaml
        )

        next_steps_md = (
            "### ✅ Execution Result\n* Manifest successfully applied "
            "live to target GKE data plane routes.\n\n"
        )
        next_steps_md += (
            f"#### Transaction Receipt\n{ticks}text\n" + stdout + f"\n{ticks}"
        )
        report_engine.update_report_placeholder(
            "[Populated in Phase 6]", next_steps_md
        )
        logging.info("\n🎉 Migration sequence finalized successfully!")
    else:
        fallback_file = os.path.join(
            config.SKILL_DIR, "migration-fallback.yaml"
        )
        with open(fallback_file, "w", encoding="utf-8") as f:
            f.write(gateway_yaml)

        abort_md = (
            "### 🛑 Deployment Paused\nDeployment declined by operator. "
            "Pre-compiled target manifests recorded locally to: "
            f"`{fallback_file}`"
        )

        report_engine.update_report_placeholder(
            "[Populated in Phase 6]", abort_md
        )
        logging.info(
            "\n🛑 Deployment declined. Fallback configurations written "
            "to local output file: %s",
            fallback_file,
        )


def main() -> None:
    """Executes the GKE Ingress to Gateway API migration workflow.

    Orchestrates the end-to-end migration process across multiple phases:
    1. Environment initialization and report template setup.
    2. Cluster inventory and risk profiling of existing Ingress manifests.
    3. Interactive operator review and traffic routing analysis.
    4. Manifest translation using the ingress2gateway tool and dry-run
       server validation.
    5. Final deployment approval and cutover runbook generation.

    Raises:
        MigrationError: If critical failures occur during report setup, binary
            acquisition, cluster communication, or manifest translation.
    """
    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="%(message)s"
    )
    logging.info("\n==========================================================")
    logging.info("☸️   GKE Ingress -> Gateway API Runtime Migration Engine  ☸️")
    logging.info("==========================================================\n")

    # Reset state if requested
    if "--reset" in sys.argv:
        state_manager.clear_state()
        logging.info("🧹 Migration state reset requested.")

    state = state_manager.load_state()
    phase = state.get("phase", "PHASE_2")

    # Enforce and verify the translation binary engine exists at startup.
    binary_path = translator.ensure_ingress2gateway_binary()

    # Isolate active Kubeconfig variables inside a sandboxed tempfile context
    with tempfile.NamedTemporaryFile(
        suffix="-kubeconfig.yaml", delete=False
    ) as kube_temp:
        temp_kubeconfig_path = kube_temp.name
    cluster_client.SANDBOX_ENV["KUBECONFIG"] = temp_kubeconfig_path

    try:
        # Re-authenticate if we are resuming an active cluster context
        chosen_cluster_name = state.get("chosen_cluster_name")
        chosen_cluster_loc = state.get("chosen_cluster_location")
        if chosen_cluster_name and chosen_cluster_loc:
            flag = (
                "--region"
                if len(chosen_cluster_loc.split("-")) == 2
                else "--zone"
            )
            cluster_client.run_command(
                [
                    "gcloud",
                    "container",
                    "clusters",
                    "get-credentials",
                    chosen_cluster_name,
                    flag,
                    chosen_cluster_loc,
                    "--quiet",
                ]
            )

        # ======================================================================
        # PHASE 2: IDENTITY & CONTEXT RESOLUTION
        # ======================================================================
        if phase == "PHASE_2":
            logging.info("▶ [PHASE 2] Identity & Context Resolution")
            try:
                report_engine.initialize_report_from_template()
            except MigrationError as e:
                logging.error("❌ Initialization Failed: %s", e)
                sys.exit(1)

            chosen_cluster_name, chosen_cluster_loc = discover_clusters()

            state["phase"] = "PHASE_3_4"
            state["chosen_cluster_name"] = chosen_cluster_name
            state["chosen_cluster_location"] = chosen_cluster_loc
            state_manager.save_state(state)

        # ======================================================================
        # PHASE 3 & 4: RESOURCE DISCOVERY, SCANNING & RISK PROFILING
        # ======================================================================
        if state.get("phase") == "PHASE_3_4":
            chosen_cluster_name = state["chosen_cluster_name"]
            target_ingresses = discover_profile_ingress(chosen_cluster_name)
            if not target_ingresses:
                logging.info(
                    "🛑 Process halted: No configuration targets were approved "
                    "for translation operations."
                )
                state_manager.clear_state()
                return

            state["phase"] = "PHASE_5"
            state["target_ingresses"] = target_ingresses
            state_manager.save_state(state)

        # ======================================================================
        # PHASE 5: TRANSLATION & DRY RUN VALIDATION
        # ======================================================================
        if state.get("phase") == "PHASE_5":
            chosen_cluster_name = state["chosen_cluster_name"]
            target_ingresses = state["target_ingresses"]
            action, gateway_yaml = translate_validate(
                binary_path, target_ingresses, chosen_cluster_name
            )

            state["phase"] = "PHASE_6"
            state["action"] = action
            state["gateway_yaml"] = gateway_yaml
            state_manager.save_state(state)

        # ======================================================================
        # PHASE 6: APPROVAL AND EXECUTION
        # ======================================================================
        if state.get("phase") == "PHASE_6":
            logging.info("\n▶ [PHASE 6] Approval and execution\n")
            action = state["action"]
            gateway_yaml = state["gateway_yaml"]
            deploy_gateway(action, gateway_yaml)
            state_manager.clear_state()

    # Necessary to log and record all runtime errors in the final report.
    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Migration execution failed: {e}"
        if os.path.exists(config.ANALYSIS_PATH):
            with open(config.ANALYSIS_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n## ❌ Runtime Processing Error\n{error_msg}\n")
        logging.error("\n❌ %s", error_msg)
        sys.exit(1)
    finally:
        if os.path.exists(temp_kubeconfig_path):
            os.remove(temp_kubeconfig_path)


if __name__ == "__main__":
    main()
