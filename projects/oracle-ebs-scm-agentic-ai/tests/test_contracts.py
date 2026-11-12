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

"""Contract tests across the agent, the MCP Toolbox, SQL, and Terraform."""

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest
import sqlglot
import yaml
from oracle_ebs_scm_agentic_ai import guardrails, semantic_mapping
from oracle_ebs_scm_agentic_ai.config import ENVIRONMENT_VARIABLES
from sqlglot import exp

PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_YAML = PROJECT_DIR / "mcp-servers" / "mcp-toolbox-ebs" / "tools.yaml"
SCM_PACKAGE_SPEC = PROJECT_DIR / "ebs-scripts" / "ge_ebs_scm_tools_pkg.pls"
SCM_VIEWS_SQL = PROJECT_DIR / "ebs-scripts" / "install_scm_inventory_views.sql"
APPS_AI_SQL = PROJECT_DIR / "ebs-scripts" / "install_apps_ai_user.sql"
TERRAFORM_MAIN = PROJECT_DIR / "terraform" / "main.tf"
DEPLOY_SCRIPT = PROJECT_DIR / "scripts" / "deploy_stack.sh"
PACKAGE_DIR = PROJECT_DIR / "src" / "oracle_ebs_scm_agentic_ai"
AGENT_CARD = PACKAGE_DIR / "agent_card.json"


def toolbox_documents() -> list[dict[str, Any]]:
    """Load every YAML document of the MCP Toolbox configuration."""
    with TOOLS_YAML.open(encoding="utf-8") as handle:
        return [doc for doc in yaml.safe_load_all(handle) if doc]


def scm_semantic_map() -> dict[str, Any]:
    """Load the semantic map of the Supply Chain Resiliency views."""
    return next(
        smap
        for smap in semantic_mapping.load_semantic_maps()
        if smap["module"].startswith("Supply Chain Resiliency")
    )


def test_runtime_prompts_stay_out_of_the_docs_site() -> None:
    """MkDocs publishes every Markdown file under the project directory."""
    assert not list((PROJECT_DIR / "src").rglob("*.md"))


def test_bigquery_examples_never_alias_with_queries() -> None:
    """MCP Toolbox's dataset check rejects an alias on a WITH query."""
    maps_dir = semantic_mapping.SEMANTIC_MAPS_DIR
    path = maps_dir / "bigquery_signals_semantic_map.json"
    examples = json.loads(path.read_text(encoding="utf-8"))["example_queries"]
    for example in examples:
        sql = example["sql"]
        for name in re.findall(r"(\w+) AS \(SELECT", sql):
            assert not re.search(
                rf"\b(?:FROM|JOIN) {name} (?:AS )?"
                r"(?!(?:JOIN|ON|USING|WHERE|GROUP|ORDER)\b)\w",
                sql,
            ), name


READ_EXAMPLES = [
    pytest.param(
        example["sql"],
        "bigquery" if "BigQuery" in smap["module"] else "oracle",
        id=example["description"][:60],
    )
    for smap in semantic_mapping.load_semantic_maps()
    for example in smap["example_queries"]
]
OPEN_REQUISITION_FILTERS = (
    "h.authorization_status IN ('APPROVED', 'IN PROCESS', 'PRE-APPROVED')",
    "NVL(l.cancel_flag, 'N') = 'N'",
    "NVL(l.closed_code, 'OPEN') = 'OPEN'",
    "l.line_location_id IS NULL",
)
SURGE_TARGET = re.compile(
    r"CEIL\((?:\w+\.)?(\w+) \* (?:NVL\()?(?:\w+\.)?:?search_surge_multiplier"
    r"(?:, 1\))?\)"
)
MONEY_COLUMN = re.compile(
    r"PRICE|SPEND|VALUE|AMOUNT|COST|REVENUE|PENALTY|FREIGHT|BENEFIT"
)


@pytest.mark.parametrize(("sql", "dialect"), READ_EXAMPLES)
def test_examples_pass_the_read_guardrail(sql: str, dialect: str) -> None:
    problem, _ = guardrails.validate_read_query(
        sql, dialect, guardrails.MAX_RESULT_ROWS + 1
    )
    assert problem is None


@pytest.mark.parametrize(("sql", "dialect"), READ_EXAMPLES)
def test_examples_return_money_with_its_currency(
    sql: str, dialect: str
) -> None:
    """An amount without its currency reads as US dollars in the answer.

    Every money column that an example returns either names USD or comes
    with the CURRENCY_CODE column.
    """
    statement = sqlglot.parse_one(sql, read=dialect)
    assert isinstance(statement, exp.Query)
    outputs = {name.upper() for name in statement.named_selects}
    amounts = {
        name
        for name in outputs
        if MONEY_COLUMN.search(name) and not name.endswith("_USD")
    }
    assert not amounts or "CURRENCY_CODE" in outputs, amounts


def test_requisition_examples_net_only_unordered_requisitions() -> None:
    """Open requisitions count until a purchase order takes them over.

    Other hubs' surplus comes first, and a missing search surge counts as 1.
    """
    examples = {
        example["description"].split(":")[0]: example["sql"]
        for example in scm_semantic_map()["example_queries"]
    }
    recommended = examples["Recommended requisition quantity"]
    listing = examples[
        "Open requisitions for an item at a hub that aren't on a purchase "
        "order yet"
    ]
    for condition in OPEN_REQUISITION_FILTERS:
        assert condition in recommended
        assert condition in listing
    assert (
        "CASE WHEN network_surplus_qty > 0 THEN 0 ELSE "
        "GREATEST(CEIL(baseline_safety_stock_qty * "
        "NVL(:search_surge_multiplier, 1)) - available_to_transact_qty "
        "- open_requisition_qty, 0) END"
    ) in recommended
    assert "x.organization_code <> n.organization_code" in recommended


def test_surge_targets_scale_the_baseline_safety_stock() -> None:
    """A confirmed surge level never feeds the next surge target."""
    scaled = [
        match.group(1)
        for smap in semantic_mapping.load_semantic_maps()
        for example in smap["example_queries"]
        for match in SURGE_TARGET.finditer(example["sql"])
    ]
    assert scaled
    assert set(scaled) == {"baseline_safety_stock_qty"}


def test_toolbox_sources_use_placeholders_only() -> None:
    sources = {
        doc["name"]: doc
        for doc in toolbox_documents()
        if doc["kind"] == "source"
    }
    oracle = sources["ebs-oracle"]
    for key in ("connectionString", "user", "password"):
        assert re.fullmatch(r"\$\{[A-Z_]+\}", oracle[key])
    bigquery = sources["scm-bigquery"]
    assert bigquery["readOnly"] is True
    assert bigquery["allowedDatasets"] == ["ebs_scm_agentic_ai"]


def test_toolbox_tools_match_the_agent_contract() -> None:
    tools = {
        doc["name"]: doc for doc in toolbox_documents() if doc["kind"] == "tool"
    }
    assert set(tools) == set(guardrails.MCP_TOOLS)
    assert tools["ebs_execute_sql"]["type"] == "oracle-execute-sql"
    assert tools["bq_execute_sql"]["type"] == "bigquery-execute-sql"
    assert tools["bq_forecast"]["type"] == "bigquery-forecast"


def test_toolbox_isg_source_uses_placeholders_only() -> None:
    isg = next(
        doc for doc in toolbox_documents() if doc.get("name") == "ebs-isg"
    )
    assert isg["type"] == "http"
    assert isg["baseUrl"] == "${EBS_ISG_URL}"
    assert isg["headers"]["Authorization"] == "Basic ${EBS_ISG_BASIC_AUTH}"


@pytest.mark.parametrize("tool_name", sorted(guardrails.WRITE_TOOLS))
def test_writeback_tools_post_to_isg(tool_name: str) -> None:
    tool = next(
        doc for doc in toolbox_documents() if doc.get("name") == tool_name
    )
    operation = tool_name.removeprefix("ebs_")
    responsibility = (
        "EBS_PURCHASING_RESPONSIBILITY"
        if operation == "stage_purchase_requisition"
        else "EBS_INVENTORY_RESPONSIBILITY"
    )
    assert tool["type"] == "http"
    assert tool["source"] == "ebs-isg"
    assert (tool["method"], tool["path"]) == (
        "POST",
        f"/webservices/rest/ge_ebs_scm_tools/{operation}/",
    )
    assert "Confirmed" in tool["description"]
    # The agent calls each writeback first to record the plan, so the
    # description must not tell the model to wait for the confirmation.
    assert "only after" not in tool["description"]
    names = [param["name"] for param in tool["bodyParams"]]
    rendered = tool["requestBody"].replace(f"${{{responsibility}}}", "R")
    for name in names:
        rendered = rendered.replace(f"{{{{json .{name}}}}}", '"v"')
    body = json.loads(rendered)[f"{operation.upper()}_Input"]
    assert body["RESTHeader"]["Responsibility"] == "R"
    assert list(body["InputParameters"]) == [
        f"P_{name.upper()}" for name in names
    ]
    spec = SCM_PACKAGE_SPEC.read_text(encoding="utf-8")
    assert f"FUNCTION {operation} (" in spec


def test_apps_ai_grants_match_the_oracle_semantic_maps() -> None:
    oracle_objects = {
        name for _, name in semantic_mapping.documented_objects("oracle")
    }
    grants = re.findall(
        r"^\s+'([A-Z_]+)',?$",
        APPS_AI_SQL.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    assert grants == sorted(grants)
    assert set(grants) == oracle_objects


def test_scm_views_return_every_documented_column() -> None:
    """An example that reads a documented column can't fail with ORA-00904."""
    views = {
        statement.this.name.upper(): {
            name.upper() for name in statement.expression.named_selects
        }
        for statement in sqlglot.parse(
            SCM_VIEWS_SQL.read_text(encoding="utf-8"), read="oracle"
        )
        if isinstance(statement, exp.Create)
    }
    for table in scm_semantic_map()["tables"]:
        name = table["table_name"].rpartition(".")[2].upper()
        documented = {column["name"].upper() for column in table["columns"]}
        assert documented <= views[name], name


def test_toolbox_placeholders_come_from_terraform() -> None:
    placeholders = set(
        re.findall(r"\$\{([A-Z_]+)\}", TOOLS_YAML.read_text(encoding="utf-8"))
    )
    terraform_env = set(
        re.findall(
            r'name\s*=\s*"([A-Z_]+)"',
            TERRAFORM_MAIN.read_text(encoding="utf-8"),
        )
    )
    assert placeholders <= terraform_env


def test_terraform_keeps_passwords_out_of_the_state() -> None:
    main_tf = " ".join(TERRAFORM_MAIN.read_text(encoding="utf-8").split())
    assert "secret_data = var." not in main_tf
    assert "secret_data_wo = var.oracle_db_password" in main_tf
    assert (
        'secret_data_wo = base64encode("${var.ebs_writeback_user}:'
        '${var.ebs_writeback_password}")'
    ) in main_tf
    variables = (TERRAFORM_MAIN.parent / "variables.tf").read_text(
        encoding="utf-8"
    )
    for name in ("oracle_db_password", "ebs_writeback_password"):
        block = variables.split(f'variable "{name}" {{', 1)[1].split("}", 1)[0]
        assert "ephemeral   = true" in block
        assert "sensitive   = true" in block


def test_terraform_pins_managed_secret_versions() -> None:
    main_tf = TERRAFORM_MAIN.read_text(encoding="utf-8")
    pinned = re.findall(
        r"version = google_secret_manager_secret_version\.(\w+)\.version",
        main_tf,
    )
    assert sorted(pinned) == [
        "db_password_version",
        "isg_credentials_version",
        "maps_api_key_version",
        "maps_static_api_key_version",
    ]


def test_agent_runs_adk_in_enterprise_mode() -> None:
    # Gemini Enterprise sends A2A parts with metadata. ADK drops that metadata
    # before it calls Gemini only in enterprise (Vertex AI) mode.
    main_tf = " ".join(TERRAFORM_MAIN.read_text(encoding="utf-8").split())
    assert 'name = "GOOGLE_GENAI_USE_ENTERPRISE" value = "true"' in main_tf


def test_cloud_run_services_scale_to_zero_by_default() -> None:
    """By default no service keeps a warm instance or bills Cloud Run idle.

    The agent keeps at most one instance, because sessions live in memory.
    """
    main_tf = TERRAFORM_MAIN.read_text(encoding="utf-8")
    assert re.findall(r"min_instance_count = (\S+)", main_tf) == [
        "var.min_instance_count",
        "var.min_instance_count",
    ]
    assert re.findall(r"max_instance_count = (\d+)", main_tf) == ["100", "1"]
    variables = (TERRAFORM_MAIN.parent / "variables.tf").read_text(
        encoding="utf-8"
    )
    block = variables.split('variable "min_instance_count" {', 1)[1]
    assert "default     = 0" in block.split("validation", 1)[0]


def test_terraform_sets_every_agent_setting() -> None:
    terraform_env = set(
        re.findall(
            r'name\s*=\s*"([A-Z0-9_]+)"',
            TERRAFORM_MAIN.read_text(encoding="utf-8"),
        )
    )
    assert set(ENVIRONMENT_VARIABLES.values()) <= terraform_env


def test_agent_card_version_matches_the_package() -> None:
    pyproject = tomllib.loads(
        (PROJECT_DIR / "pyproject.toml").read_text(encoding="utf-8")
    )
    card = json.loads(AGENT_CARD.read_text(encoding="utf-8"))
    assert card["version"] == pyproject["project"]["version"]


def test_terraform_enables_the_api_of_each_service_agent() -> None:
    """An IAM grant to a service agent fails until its API creates it."""
    main_tf = TERRAFORM_MAIN.read_text(encoding="utf-8")
    apis = set(re.findall(r'"([a-z-]+\.googleapis\.com)"', main_tf))
    agents = set(re.findall(r"@gcp-sa-([a-z]+)\.iam\.gserviceaccount", main_tf))
    assert agents == {"cloudaicompanion", "discoveryengine"}
    assert {f"{agent}.googleapis.com" for agent in agents} <= apis


def test_only_gemini_enterprise_and_the_developer_invoke_the_agent() -> None:
    main_tf = " ".join(TERRAFORM_MAIN.read_text(encoding="utf-8").split())
    invoker = main_tf.split(
        'resource "google_cloud_run_v2_service_iam_member" "agent_invoker" {', 1
    )[1].split("}", 1)[0]
    assert (
        "for_each = merge(local.gemini_enterprise_agents, "
        "local.developer_invoker)"
    ) in invoker


def test_cloud_build_stages_the_source_in_the_terraform_bucket() -> None:
    """Cloud Build reads the source back as the build service account."""
    main_tf = TERRAFORM_MAIN.read_text(encoding="utf-8")
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    bucket = re.search(
        r'"\$\{var\.project_id\}(-voltguard-build-source)"', main_tf
    )
    assert bucket is not None
    assert (
        f'--gcs-source-staging-dir="gs://${{PROJECT_ID}}{bucket.group(1)}/'
        'source"'
    ) in script
    assert (
        "-target=google_storage_bucket_iam_member.cloudbuild_source_reader"
    ) in script


@pytest.mark.parametrize(
    ("source_name", "base_url"),
    [
        ("google-places", "https://places.googleapis.com"),
        ("google-routes", "https://routes.googleapis.com"),
        ("google-weather", "https://weather.googleapis.com"),
    ],
)
def test_google_maps_sources_use_the_restricted_key(
    source_name: str, base_url: str
) -> None:
    source = next(
        doc for doc in toolbox_documents() if doc.get("name") == source_name
    )
    assert source["type"] == "http"
    assert source["baseUrl"] == base_url
    assert source["headers"]["X-Goog-Api-Key"] == "${MAPS_API_KEY}"


@pytest.mark.parametrize("tool_name", guardrails.GOOGLE_MAPS_TOOLS)
def test_google_maps_tools_are_read_only(tool_name: str) -> None:
    tool = next(
        doc for doc in toolbox_documents() if doc.get("name") == tool_name
    )
    assert tool["source"] in {
        "google-places",
        "google-routes",
        "google-weather",
    }
    assert tool_name not in guardrails.WRITE_TOOLS
    assert "hub_market_areas" in tool["description"]


def test_places_search_text_body_uses_every_parameter() -> None:
    tool = next(
        doc
        for doc in toolbox_documents()
        if doc.get("name") == "places_search_text"
    )
    rendered = tool["requestBody"]
    for name in [param["name"] for param in tool["bodyParams"]]:
        placeholder = f"{{{{json .{name}}}}}"
        assert placeholder in rendered
        rendered = rendered.replace(placeholder, "1")
    assert (tool["method"], tool["path"]) == ("POST", "/v1/places:searchText")
    assert json.loads(rendered) == {
        "textQuery": 1,
        "includedType": 1,
        "strictTypeFiltering": True,
        "pageSize": 1,
        "rankPreference": "DISTANCE",
        "locationBias": {
            "circle": {"center": {"latitude": 1, "longitude": 1}, "radius": 1}
        },
    }
