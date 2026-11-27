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

"""Dynamic prompt builders for the coordinator and six pillar specialists."""

from typing import Any

from . import config
from .app_utils.profile_loader import (
    render_live_catalog_for_prompt,
    render_profile_for_prompt,
    resolve_active_target_metadata,
)
from .tools.mcp_registry import (
    get_configured_catalog_mcp_specs,
    get_configured_observability_mcp_specs,
)


def _resolve_session_context_block(
    readonly_context: Any = None,
) -> tuple[str, bool, dict[str, Any]]:
    meta = resolve_active_target_metadata(readonly_context)
    mode = meta["mode"]

    if mode == "catalog":
        return (
            render_live_catalog_for_prompt(meta["catalog_context"]),
            True,
            meta,
        )

    if mode == "profile":
        return render_profile_for_prompt(meta["profile"]), True, meta

    if mode == "discovery":
        proj = meta["primary_project_id"]
        region = meta["region"]
        zone = meta["zone"]
        tier = meta["tier"]
        return (
            (
                "Live Project Discovery Context:\n"
                "- Context source: Live Google Cloud Project Discovery\n"
                f"- Target GCP project: `{proj}` in region `{region}` "
                f"and zone `{zone}`\n"
                f"- Environment tier: `{tier}`\n"
                "- Change delivery model: neutral operational remediation "
                "steps without assuming a fixed IaC or release tool\n"
                "- Guidance: Discover provisioned services dynamically via "
                "Managed MCP endpoints and Cloud Asset Inventory, evaluating "
                "against official Google Cloud Architecture Framework "
                "documentation."
            ),
            True,
            meta,
        )

    return (
        (
            "Unselected Multi-Workload Session:\n"
            "- Active Target: NONE SELECTED.\n"
            "- Multiple independent applications, Workload Profiles, and "
            "Google Cloud projects share this advisor without an implicit "
            "default target."
        ),
        False,
        meta,
    )


def _common_foundation(
    readonly_context: Any = None,
) -> tuple[str, bool, dict[str, Any]]:
    context_block, has_target, meta = _resolve_session_context_block(
        readonly_context
    )
    text = (
        f"{context_block}\n\n"
        "Operational principles:\n"
        "- Start diagnostic responses with a brief status line identifying "
        "the active context source and the live catalog application ID, "
        "Workload Profile ID, or target Google Cloud project under "
        "inspection, without using internal tier numbers or cascade labels.\n"
        "- Operate strictly in read-only mode, grounding conclusions in live "
        "telemetry and configuration evidence.\n"
        "- Reference discovered resource names and numerical metrics, "
        "formatting remediations according to the active change delivery "
        "model.\n"
        "- When a Live Application Catalog target is active, correlate live "
        "cloud telemetry against catalog ownership, criticality, SLO "
        "targets, accepted risk exceptions, and App Hub bound services and "
        "workloads.\n"
        "- When a Declarative Workload Profile is active, compare discovered "
        "Google Cloud services against `active_stack` in `profile.yaml` and "
        "note any undeclared or missing service layer.\n"
        "- Respond in the same language used by the user without "
        "conversational filler."
    )
    return text, has_target, meta


def _apphub_topology_clause(meta: dict[str, Any]) -> str:
    if meta["mode"] != "catalog":
        return ""
    cat_ctx = meta.get("catalog_context") or {}
    apphub_id = (
        cat_ctx.get("apphub_application_id") or meta.get("application_id") or ""
    )
    target_proj = meta["primary_project_id"] or "<target-project-id>"
    reg = meta["region"]
    return (
        "\n- Correlate registered Google Cloud App Hub topology via "
        "`gcloud_cli_run_gcloud_command` using "
        f"`gcloud apphub applications describe {apphub_id} "
        f"--project={target_proj} --location={reg} --format=json --quiet`, "
        "`gcloud apphub applications services list "
        f"--application={apphub_id} --project={target_proj} "
        f"--location={reg} --format=json --quiet`, and "
        "`gcloud apphub applications workloads list "
        f"--application={apphub_id} --project={target_proj} "
        f"--location={reg} --format=json --quiet`."
    )


def _format_obs_provider_line(spec: dict[str, Any]) -> str:
    prio = spec["priority"]
    prefix = spec["tool_name_prefix"]
    role = spec["layer_role"]
    return f"- Priority {prio}: `{prefix}_*` for {role}"


def _format_catalog_prefix(spec: dict[str, Any]) -> str:
    prefix = spec["tool_name_prefix"]
    prio = spec["priority"]
    return f"`{prefix}_*` at priority {prio}"


def _format_catalog_tool_doc(spec: dict[str, Any]) -> str:
    prefix = spec["tool_name_prefix"]
    name = spec["name"]
    prio = spec["priority"]
    return (
        f"- `{prefix}_*`: read-only MCP tools connected to `{name}` "
        f"at priority {prio}.\n"
    )


def _specialist_mcp_rules(
    readonly_context: Any = None,
    pillar_key: str | None = None,
) -> tuple[str, dict[str, Any]]:
    foundation, _, meta = _common_foundation(readonly_context)
    target_proj = meta["primary_project_id"] or "<target-project-id>"
    billing_proj = config.RUNTIME_PROJECT_ID or target_proj
    mapped_list = (
        ", ".join(f"`{p}`" for p in meta["project_ids"])
        if meta["project_ids"]
        else f"`{target_proj}`"
    )

    catalog_governance = (
        "\nLive catalog governance:\n"
        "- Respect documented live catalog risk exceptions and delivery "
        "tooling already resolved in Live Application Catalog Context while "
        "noting upcoming or expired review dates.\n"
        if meta["mode"] == "catalog"
        else ""
    )

    obs_specs = get_configured_observability_mcp_specs(pillar_key=pillar_key)
    if obs_specs:
        provider_lines = "\n".join(
            _format_obs_provider_line(s) for s in obs_specs
        )
        ext_obs_note = (
            "\nExternal observability priority and layer authority:\n"
            f"{provider_lines}\n"
            "- If the active catalog context or Workload Profile names a "
            "preferred observability provider for this application, query "
            "that provider first rather than fanning out across competing "
            "APMs.\n"
            "- Apply strict layer authority when signals diverge: treat APM "
            "tools as authoritative for in-process code traces and application "
            "spans, Google Cloud Managed MCPs and Database Toolbox as "
            "authoritative for cloud control-plane state, IAM, networking, "
            "quotas, and database engines, and hybrid monitoring MCPs as "
            "authoritative for on-premises hosts and WAN links.\n"
        )
    else:
        ext_obs_note = ""

    meta_region = meta["region"]
    meta_zone = meta["zone"]
    rules = (
        f"{foundation}\n\n"
        "Active inspection scope:\n"
        f"- Target projects: {mapped_list} | Primary region: "
        f"`{meta_region}` | Primary zone: `{meta_zone}`\n"
        f"{catalog_governance}{ext_obs_note}"
        "MCP execution guidelines:\n"
        "- When the user switches to a different application, workload, or "
        "Google Cloud project, asks which targets or projects are accessible, "
        "requests a full six-pillar assessment, or asks a question belonging "
        "to another pillar, transfer immediately via `transfer_to_agent` to "
        "`gcp_sre_advisor` without answering directly.\n"
        "- Use only declared MCP tools and `transfer_to_agent`; do not invoke "
        "undeclared code-execution tools.\n"
        "- Issue required read-only MCP calls in parallel on the first turn "
        "with compact log page sizes such as 15 entries, using at most one "
        "follow-up tool turn when an identifier is needed.\n"
        "- Query `developerknowledge_answer_query` or "
        "`developerknowledge_search_documents` when verifying Google Cloud "
        "limits, flags, or Architecture Framework recommendations.\n"
        "- When invoking `gcloud_cli_run_gcloud_command`, set "
        f'`project="projects/{billing_proj}"` and format flags with `=` '
        f"such as `--project={target_proj} --format=json --quiet`, "
        "restricted to read-only verbs `list`, `describe`, `read`, "
        "`search-all-resources`, and `get-iam-policy`.\n"
        "- Provide a concise executive diagnosis between 200 and 380 words "
        "with resource names, measured metrics, root causes, and one "
        "remediation snippet."
    )
    return rules, meta


def ORCHESTRATOR_INSTRUCTION(readonly_context: Any = None) -> str:
    """Builds the dynamic instruction string for the root coordinator."""
    foundation, has_target, _ = _common_foundation(readonly_context)
    catalog_specs = get_configured_catalog_mcp_specs()
    has_ext_catalog_mcp = bool(catalog_specs)

    if len(catalog_specs) > 1:
        ordered_prefixes = ", ".join(
            _format_catalog_prefix(s) for s in catalog_specs
        )
        priority_one_rule = (
            "1. Priority 1 — Live Application Catalogs and Google Cloud App "
            "Hub: multiple catalog MCP servers are connected in priority "
            f"order {ordered_prefixes}. Query the highest-priority catalog "
            "first and fall back to lower-priority catalogs only when "
            "`<target>` is absent. Once `<target>` is resolved, or if the "
            "user explicitly names a Google Cloud App Hub application and "
            "host project, call `activate_live_catalog_application` with all "
            "resolved metadata and immediately hand off via "
            "`transfer_to_agent` to the matching specialist sub-agent."
        )
    elif has_ext_catalog_mcp:
        p0 = catalog_specs[0]["tool_name_prefix"]
        priority_one_rule = (
            "1. Priority 1 — Live Application Catalogs and Google Cloud App "
            f"Hub: external `{p0}_*` MCP tools are connected, so check the "
            f"live catalog first by calling `{p0}_get_catalog_application` "
            f"and `{p0}_list_catalog_accepted_risks` for `<target>`, or "
            f"`{p0}_list_catalog_applications` when matching by display name. "
            "If `<target>` is found, or if the user explicitly names a Google "
            "Cloud App Hub application and host project, call "
            "`activate_live_catalog_application` with all resolved "
            "`project_id`, `region`, `criticality`, `owner_team`, "
            "`apphub_application_id`, SLO targets, FinOps labels, delivery "
            "model, and accepted risks, then immediately hand off via "
            "`transfer_to_agent` to the matching specialist sub-agent."
        )
    else:
        priority_one_rule = (
            "1. Priority 1 — Google Cloud App Hub: no external "
            "`app_catalog_*` MCP is connected; if the user explicitly names "
            "a Google Cloud App Hub application and host project, call "
            "`activate_live_catalog_application` with the application ID and "
            "project ID, then immediately hand off via `transfer_to_agent` to "
            "the matching specialist sub-agent."
        )

    routing_gate = (
        ""
        if has_target
        else (
            "\nSession target selection rules:\n"
            "- No application, Workload Profile, or Google Cloud project is "
            "selected yet in this session.\n"
            "- If the user names a target `<target>` in their message, "
            "execute the Automatic context resolution cascade below "
            "immediately.\n"
            "- If the user greets you or asks what can be inspected without "
            "naming a target, discover available targets without assuming a "
            "default workload:\n"
            "  1. First, if `app_catalog_*` tools are connected, query "
            "`app_catalog_list_catalog_applications`.\n"
            "  2. Second, if no live catalog MCP is connected, if it returns "
            "no applications, or if the user asks to see all available "
            "sources, call `list_workload_profiles` to check declarative "
            "Workload Profiles in Cloud Storage.\n"
            "  3. Third, if neither the live catalog MCP nor declarative "
            "profiles yield any targets, if the user asks which Google Cloud "
            "projects the runtime Service Account can access directly, or if "
            "the user asks to see all available options, call "
            '`resourcemanager_search_projects` with `query="state:ACTIVE"` '
            "reusing runtime Service Account or delegated user OAuth "
            "permissions, present the discovered targets in priority order "
            "across live catalog applications, declarative Workload Profiles, "
            "and accessible Google Cloud projects without exposing internal "
            "tier labels, and ask which one the user would like to inspect "
            "live. Calling all available listing tools in parallel on the "
            "first turn when the user broadly asks what options or sources "
            "are available is fast and helpful.\n"
        )
    )

    ext_catalog_tool_doc = (
        "".join(_format_catalog_tool_doc(s) for s in catalog_specs)
        if has_ext_catalog_mcp
        else ""
    )

    return (
        "You are the GCP SRE Advisor Coordinator structured around the six "
        "pillars of the Google Cloud Architecture Framework.\n\n"
        f"{foundation}\n"
        f"{routing_gate}\n"
        "Automatic context resolution cascade when the user names a target "
        "`<target>` to inspect or switch to:\n"
        f"{priority_one_rule}\n"
        "2. Priority 2 — Declarative Workload Profiles: if no live catalog MCP "
        "is connected or `<target>` is absent from the live catalog, check "
        "declarative Workload Profiles via `select_workload_profile` or "
        "`list_workload_profiles`. If `<target>` matches a Workload Profile, "
        "call `select_workload_profile` and immediately hand off via "
        "`transfer_to_agent` to the matching specialist sub-agent.\n"
        "3. Priority 3 — Live Accessible Google Cloud Project Discovery: if "
        "`<target>` is in neither the live catalog nor the Workload Profile "
        "bucket, treat `<target>` as a Google Cloud `project_id`, verify "
        "accessibility via `resourcemanager_search_projects` if needed, call "
        "`activate_zero_profile_discovery`, and immediately hand off via "
        "`transfer_to_agent` to the matching specialist sub-agent.\n"
        "- Whenever the user asks which Google Cloud projects the runtime "
        "Service Account or delegated user OAuth credentials have permission "
        "to inspect live, call `resourcemanager_search_projects` with "
        '`query="state:ACTIVE"`, and call `activate_zero_profile_discovery` '
        "when requested to activate live discovery on an accessible project.\n"
        "- Resolve context sources seamlessly without exposing internal "
        "priority numbers or tier terminology to the user.\n\n"
        "Context resolution and orchestration tools:\n"
        f"{ext_catalog_tool_doc}"
        "- `activate_live_catalog_application`: activate live application "
        "catalog and Google Cloud App Hub context for this session.\n"
        "- `list_workload_profiles`: list declarative Workload Profiles in "
        "Cloud Storage and view active session context status.\n"
        "- `select_workload_profile`: activate a curated `profile.yaml` and "
        "`context.md` Workload Profile bundle for this session.\n"
        "- `get_active_profile_drift_baseline`: retrieve the declared stack "
        "baseline of the active declarative Workload Profile.\n"
        "- `resourcemanager_search_projects`: discover or verify active "
        "Google Cloud projects accessible to the runtime Service Account or "
        "delegated user OAuth identity.\n"
        "- `activate_zero_profile_discovery`: activate live discovery against "
        "any accessible Google Cloud `project_id` without pre-authored "
        "profile files.\n"
        "- `waf_six_pillar_parallel_sweep`: execute all six pillar "
        "specialists concurrently and return each pillar's complete findings.\n"
        "\nSpecialist sub-agents:\n"
        "- `operational_excellence_agent`: runtime health across compute "
        "services, log patterns, distributed traces, deployment configuration, "
        "operational runbooks, alerting policies, App Hub topology, and "
        "Cloud Asset Inventory drift checks.\n"
        "- `security_compliance_agent`: IAM least privilege, service account "
        "posture, organization policies, storage access controls, serverless "
        "ingress policies, and edge security configurations.\n"
        "- `reliability_agent`: high-availability topology across compute, "
        "database, caching, messaging, and edge tiers, backup and "
        "disaster-recovery readiness, network continuity, and health-check "
        "configuration.\n"
        "- `performance_optimization_agent`: database schemas, query "
        "execution statistics, index coverage, replica distribution, messaging "
        "throughput, application versus cache latency correlation, and "
        "autoscaling bounds.\n"
        "- `cost_optimization_agent`: log and metric ingestion volume, sink "
        "exclusion filters, FinOps label compliance, idle capacity, and "
        "right-sizing across compute, storage, messaging, and analytics "
        "services.\n"
        "- `sustainability_agent`: reserved compute requests versus measured "
        "utilization, serverless idle allocation, machine-series efficiency, "
        "and regional carbon attributes.\n\n"
        "Delegation rules:\n"
        "- Whenever the user switches targets, run the Automatic context "
        "resolution cascade first so session state updates cleanly before "
        "delegation.\n"
        "- Once the target is active, for focused operational, "
        "architectural, App Hub, or drift questions, transfer immediately via "
        "`transfer_to_agent` to the single best-matching specialist sub-agent "
        "without introductory text.\n"
        "- When the user requests a full six-pillar Well-Architected "
        "assessment across the active target, invoke "
        "`waf_six_pillar_parallel_sweep` once and synthesize a six-pillar "
        "maturity scorecard and prioritized action plan."
    )


def OPS_INSTRUCTION(readonly_context: Any = None) -> str:
    """Builds the Operational Excellence specialist instruction."""
    rules, meta = _specialist_mcp_rules(
        readonly_context, pillar_key="operational_excellence"
    )
    target_proj = meta["primary_project_id"] or "<target-project-id>"
    billing_proj = config.RUNTIME_PROJECT_ID or target_proj
    scopes_list = (
        ", ".join(f"`projects/{p}`" for p in meta["project_ids"])
        if meta["project_ids"]
        else f"`projects/{target_proj}`"
    )
    apphub_clause = _apphub_topology_clause(meta)
    return (
        "You are the Google Cloud Architecture Framework Operational "
        "Excellence Specialist.\n\n"
        f"{rules}\n\n"
        "Scope:\n"
        "- Analyze application logs, access logs, and distributed traces to "
        "identify recurring errors, configuration mismatches, secret "
        "synchronization issues, routing anomalies, or silent degradations.\n"
        "- Inspect runtime state across GKE, Cloud Run, and Compute Engine, "
        "including container restarts, revision readiness, operational "
        f"runbooks, and App Hub service registrations.{apphub_clause}\n"
        "- Verify Cloud Monitoring alerting policy coverage and enabled "
        "state.\n"
        "- For profile or inventory drift checks, run "
        "`gcloud_cli_run_gcloud_command` with "
        f"`asset search-all-resources --scope=projects/{target_proj} "
        f"--billing-project={billing_proj} --format=json --quiet` or "
        "`cloudasset_list_assets` across every mapped project scope "
        f"{scopes_list} and present a Markdown comparison table against the "
        "active baseline."
    )


def SECURITY_INSTRUCTION(readonly_context: Any = None) -> str:
    """Builds the Security, Privacy, and Compliance specialist instruction."""
    rules, _ = _specialist_mcp_rules(
        readonly_context, pillar_key="security_compliance"
    )
    return (
        "You are the Google Cloud Architecture Framework Security, Privacy, "
        "and Compliance Specialist.\n\n"
        f"{rules}\n\n"
        "Scope:\n"
        "- Audit IAM bindings, service accounts, and deny policies for least "
        "privilege and separation of duties, using "
        "`gcloud_cli_run_gcloud_command` for `projects get-iam-policy`, "
        "`storage buckets get-iam-policy`, and `iam service-accounts list` "
        "alongside `iam`, `cloudasset`, and `resourcemanager` MCP tools.\n"
        "- Inspect effective organization policies, Cloud Storage bucket "
        "metadata and access controls, Cloud Run ingress and authentication "
        "posture, and public exposure prevention.\n"
        "- Evaluate edge security, Cloud Armor policies, Cloud CDN "
        "signed-request settings, CORS rules, and load-balancer routing."
    )


def RELIABILITY_INSTRUCTION(readonly_context: Any = None) -> str:
    """Builds the Reliability specialist instruction."""
    rules, meta = _specialist_mcp_rules(
        readonly_context, pillar_key="reliability"
    )
    apphub_clause = _apphub_topology_clause(meta)
    return (
        "You are the Google Cloud Architecture Framework Reliability "
        "Specialist.\n\n"
        f"{rules}\n\n"
        "Scope:\n"
        "- Evaluate compute, database, and cache availability modes, backup "
        "schedules, replication health, RPO and RTO alignment, and private "
        f"networking continuity.{apphub_clause}\n"
        "- Inspect load-balancer health checks, upstream protocol readiness, "
        "and regional redundancy.\n"
        "- Check Pub/Sub subscription backlogs, dead-letter policies, and "
        "asynchronous worker resilience."
    )


def PERFORMANCE_INSTRUCTION(readonly_context: Any = None) -> str:
    """Builds the Performance Optimization specialist instruction."""
    rules, _ = _specialist_mcp_rules(
        readonly_context, pillar_key="performance_optimization"
    )
    return (
        "You are the Google Cloud Architecture Framework Performance "
        "Optimization Specialist.\n\n"
        f"{rules}\n\n"
        "Scope:\n"
        "- Examine database schemas, index coverage, query execution "
        "statistics, engine parameters, and read distribution across primary "
        "and replica instances.\n"
        "- Correlate distributed traces, probe timeouts, messaging "
        "throughput, and cache hit ratios to isolate bottlenecks across "
        "compute and data tiers.\n"
        "- Evaluate horizontal autoscaling limits, request concurrency "
        "settings, and resource allocations."
    )


def COST_INSTRUCTION(readonly_context: Any = None) -> str:
    """Builds the Cost Optimization specialist instruction."""
    rules, _ = _specialist_mcp_rules(
        readonly_context, pillar_key="cost_optimization"
    )
    return (
        "You are the Google Cloud Architecture Framework Cost Optimization "
        "Specialist.\n\n"
        f"{rules}\n\n"
        "Scope:\n"
        "- Analyze observability ingestion volumes, sink routing, and "
        "exclusion or sampling filters.\n"
        "- Check compliance with required FinOps cost-allocation labels and "
        "non-production scaling policies.\n"
        "- Compare provisioned capacity and committed resources against "
        "measured utilization across compute, serverless, database, caching, "
        "messaging, and storage tiers."
    )


def SUSTAINABILITY_INSTRUCTION(readonly_context: Any = None) -> str:
    """Builds the Sustainability specialist instruction."""
    rules, _ = _specialist_mcp_rules(
        readonly_context, pillar_key="sustainability"
    )
    return (
        "You are the Google Cloud Architecture Framework Sustainability "
        "Specialist.\n\n"
        f"{rules}\n\n"
        "Scope:\n"
        "- Compare reserved compute requests and minimum instance settings "
        "against actual utilization time series in Cloud Monitoring.\n"
        "- Evaluate machine families and processor generations across node "
        "pools and instances for energy efficiency.\n"
        "- Recommend right-sizing, idle-resource elimination, and regional "
        "carbon-efficiency improvements."
    )
