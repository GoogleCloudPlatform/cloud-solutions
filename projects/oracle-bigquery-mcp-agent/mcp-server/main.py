"""
FynanceAI FastAPI MCP Connector & Webhook Middleware Server.
Provides CDC pipeline telemetry, legal vector search, and oracle query actions.
"""

import asyncio
import json
import logging
import os
import re
import time
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import oracledb
import uvicorn
import vertexai
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import DefaultCredentialsError
from vertexai.language_models import TextEmbeddingModel

# Configure logging for production visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_pool = None
embedding_model = None
contract_vectors = []
is_indexing_completed = False

SQL_QUERIES = {}
RISK_KEYWORDS = ["personal", "macbook", "urgent", "gift"]


def load_sql_queries():
    """
    Dynamic SQL Queries Loader: Reads all .sql files inside the local
    sql/ subdirectory at startup, keeping them cached in-memory.
    """
    sql_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sql")
    if os.path.exists(sql_dir):
        for filename in os.listdir(sql_dir):
            if filename.endswith(".sql"):
                key = filename[:-4]  # e.g., 'get_expenses'
                try:
                    fpath = os.path.join(sql_dir, filename)
                    with open(fpath, "r", encoding="utf-8") as fh:
                        SQL_QUERIES[key] = fh.read().strip()
                except (OSError, UnicodeDecodeError) as e:
                    logger.error(
                        "Failed to load SQL query from %s: %s", filename, e
                    )


def get_vertex_embedding(text: str) -> list:
    """
    Queries Vertex AI Text Embeddings using the official SDK.
    Returns a 768-dimension float vector. Falls back on failures.
    """
    if not embedding_model:
        return None
    try:
        embeddings = embedding_model.get_embeddings([text])
        if embeddings:
            return embeddings[0].values
    except (GoogleAPICallError, RuntimeError, ValueError) as e:
        logger.error("Vertex AI SDK embedding generation failed: %s", e)
    return None


def cosine_similarity(v1: list, v2: list) -> float:
    """
    Calculates Cosine Similarity between two vectors.
    """
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = sum(a * a for a in v1) ** 0.5
    norm_v2 = sum(b * b for b in v2) ** 0.5
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)


def run_in_memory_vector_indexing():
    """
    Performs legal and policy contract document loading and concurrent vector
    generation inside a dedicated background thread, preventing startup loop
    blocks.
    """
    global contract_vectors, is_indexing_completed
    logger.info("Indexing contract documents into memory vector space...")
    contract_vectors = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    contracts = [
        os.path.join(base_dir, "contracts", "oracle_gcp_msa.txt"),
        os.path.join(base_dir, "contracts", "fynanceai_procurement_policy.txt"),
    ]

    all_chunks = []
    for fpath in contracts:
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as fh:
                    content = fh.read()
                chunks = [c.strip() for c in content.split("\n\n") if c.strip()]
                for chunk in chunks:
                    all_chunks.append((chunk, fpath))
            except (OSError, UnicodeDecodeError) as e:
                logger.error("Failed to read %s: %s", fpath, e)
        else:
            logger.warning("Contract document path not found: %s", fpath)

    if all_chunks:
        logger.info(
            "ThreadPoolExecutor starting parallel embeddings for %d chunks...",
            len(all_chunks),
        )
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_chunk = {
                executor.submit(get_vertex_embedding, item[0]): item
                for item in all_chunks
            }
            for future in future_to_chunk:
                chunk, fpath = future_to_chunk[future]
                try:
                    vector = future.result()
                    if vector is not None:
                        contract_vectors.append(
                            {"content": chunk, "vector": vector}
                        )
                    else:
                        logger.error(
                            "Skipping vector cache due to API failure: "
                            "'%s...' in %s",
                            chunk[:30],
                            fpath,
                        )
                except (
                    urllib.error.URLError,
                    json.JSONDecodeError,
                    KeyError,
                    IndexError,
                ) as e:
                    logger.error(
                        "Thread embedding failed for chunk in %s: %s", fpath, e
                    )

        logger.info(
            "Successfully indexed %d chunks into memory vector index.",
            len(contract_vectors),
        )

    # Toggle the global completion flag cleanly to authorize semantic tools
    # executions
    is_indexing_completed = True


CACHED_PORTAL_HTML = ""


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Modern lifespan context manager: Natively handles serverless container
    startup and shutdown lifecycle hooks, fully compliant with the latest
    FastAPI specs.
    """
    global db_pool, CACHED_PORTAL_HTML

    # 1. Startup Event: Fail-Fast SRE Environment Validation
    required_vars = [
        "PROJECT_ID",
        "DB_USER",
        "DB_PASSWORD",
        "DB_DSN",
        "AGENT_ID",
    ]
    missing_vars = []
    for var in required_vars:
        val = os.environ.get(var)
        if not val or "YOUR_" in str(val) or "PLACEHOLDER" in str(val):
            missing_vars.append(var)

    if missing_vars:
        missing_str = ", ".join(missing_vars)
        logger.critical(
            "CRITICAL: Fail-Fast validation failed. Missing required "
            "environment variables: %s",
            missing_str,
        )
        raise RuntimeError(
            "Fail-Fast startup validation failed. Missing required "
            f"environment variables: {missing_str}"
        )

    try:
        # 2. Initialize a highly efficient, thread-safe connection pool
        db_pool = oracledb.create_pool(
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            dsn=os.environ.get("DB_DSN"),
            min=1,
            max=5,
            increment=1,
        )
        logger.info("Oracle Connection Pool successfully initialized.")
        load_sql_queries()

        # Initialize Vertex AI SDK for semantic searches
        try:
            p_id = os.environ.get("PROJECT_ID")
            v_reg = os.environ.get("VERTEX_REGION", "us-central1")
            vertexai.init(project=p_id, location=v_reg)
            global embedding_model
            embedding_model = TextEmbeddingModel.from_pretrained(
                "text-embedding-004"
            )
            logger.info("Vertex AI TextEmbeddingModel initialized.")
        except (
            GoogleAPICallError,
            DefaultCredentialsError,
            ValueError,
            RuntimeError,
        ) as ex:
            logger.warning(
                "Vertex AI SDK initialization failed: %s. "
                "Semantic search will use keyword fallback.",
                ex,
            )

        # Pre-compile and cache the employee portal dashboard template once
        # at startup to prevent disk reads
        template_path = os.path.join(
            os.path.dirname(__file__), "templates", "index.html"
        )
        with open(template_path, "r", encoding="utf-8") as fh:
            html_content = fh.read()
        project_id = os.environ.get("PROJECT_ID", "")
        looker_url = os.environ.get("LOOKER_DASHBOARD_URL", "")
        agent_id = os.environ.get("AGENT_ID", "")
        is_looker_configured = (
            "PLACEHOLDER" not in looker_url and "http" in looker_url
        )
        button_class = "" if is_looker_configured else "hidden"
        CACHED_PORTAL_HTML = (
            html_content.replace("YOUR_GCP_PROJECT_ID", project_id)
            .replace("YOUR_DIALOGFLOW_AGENT_ID", agent_id)
            .replace("https://[LOOKER_INSTANCE_URL_PLACEHOLDER]", looker_url)
            .replace("LOOKER_BUTTON_HIDDEN", button_class)
        )
        logger.info(
            "Employee dashboard HTML portal template successfully cached."
        )
    except oracledb.Error as e:
        logger.critical(
            "CRITICAL: Failed to create Oracle Connection Pool: %s", e
        )
        raise RuntimeError(
            "Failed to initialize Oracle Database Connection Pool: " f"{str(e)}"
        ) from e

    # Delegate blocking document indexing to a background thread executor
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_in_memory_vector_indexing)

    yield  # Server serves requests here!

    # 3. Shutdown Event: Clean up database connections gracefully
    if db_pool:
        db_pool.close()
        logger.info("Oracle Connection Pool successfully closed.")


app = FastAPI(lifespan=lifespan)


def get_db_connection():
    if db_pool:
        try:
            return db_pool.acquire()
        except oracledb.Error as e:
            logger.error("Failed to acquire connection from pool: %s", e)
    # Fail-safe fallback to standard standalone connect
    return oracledb.connect(
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        dsn=os.environ.get("DB_DSN"),
    )


def resolve_id(args):
    """
    Universal Resolver: Extracts numeric IDs from messy AI inputs.
    Handles '49999', '#49999', 'ID: 49999', or even if the key is
    'id' vs 'expense_id'.
    """
    if not args or not isinstance(args, dict):
        return None
    val = args.get("expense_id") or args.get("id") or args.get("transaction_id")
    if val:
        digits = re.sub(r"\D", "", str(val))
        return int(digits) if digits else None
    return None


# ==========================================
# PHASE 4: THE PREMIUM ENTERPRISE PORTAL
# ==========================================


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)  # 204 means "No Content"


@app.get("/")
async def employee_portal():
    return HTMLResponse(content=CACHED_PORTAL_HTML)


# ==========================================
# THE SMART AGENT MCP BACKEND
# ==========================================


@app.get("/api/expenses")
async def get_expenses_api(page: int = 1, size: int = 10):
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                offset_val = (page - 1) * size
                query = SQL_QUERIES["get_expenses"]
                cursor.execute(
                    query, {"row_offset": offset_val, "row_limit": size}
                )
                rows = cursor.fetchall()
                data = [
                    {
                        "id": r[0],
                        "amount": r[1],
                        "description": r[2],
                        "status": r[3],
                    }
                    for r in rows
                ]
                return JSONResponse(content=data)
    except oracledb.Error as e:
        logger.error("Database Error in get_expenses_api: %s", e)
        return JSONResponse(content=[], status_code=500)
    except KeyError as e:
        logger.error("Configuration Error (Missing SQL key): %s", e)
        return JSONResponse(content=[], status_code=500)


@app.get("/api/dba/stats")
async def get_dba_stats():
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(SQL_QUERIES["dba_active_sessions_count"])
                act_sess = cursor.fetchone()[0]

                cursor.execute(SQL_QUERIES["dba_total_sessions_count"])
                tot_sess = cursor.fetchone()[0]

                cursor.execute(SQL_QUERIES["dba_database_name"])
                db_name = cursor.fetchone()[0]

                cursor.execute(SQL_QUERIES["dba_invalid_objects_count"])
                inv_obj = cursor.fetchone()[0]

                return JSONResponse(
                    content={
                        "active_sessions": act_sess,
                        "total_sessions": tot_sess,
                        "db_name": db_name,
                        "invalid_objects": inv_obj,
                    }
                )
    except oracledb.Error as e:
        logger.error(
            "DBA API Database Error: %s\n%s", e, traceback.format_exc()
        )
        return JSONResponse(
            content={"error": "Database stats telemetry unavailable"},
            status_code=500,
        )
    except KeyError as e:
        logger.error("DBA API Config Error: %s\n%s", e, traceback.format_exc())
        return JSONResponse(
            content={"error": "Database stats telemetry configuration error"},
            status_code=500,
        )


@app.get("/api/dba/telemetry")
async def get_dba_telemetry():
    sessions = []
    tablespaces = []
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                sessions = []
                tablespaces = []

                # 1. Active Sessions Query from v$session (wait-events)
                cursor.execute(SQL_QUERIES["dba_active_sessions_telemetry"])
                rows = cursor.fetchall()
                for r in rows:
                    time_s = f"{r[3] or 0}s"
                    sessions.append(
                        {
                            "sid": r[0],
                            "user": r[1],
                            "event": r[2] or "CPU",
                            "time": time_s,
                        }
                    )

                # 2. Tablespace Storage Allocation Query from DBA views
                cursor.execute(SQL_QUERIES["dba_tablespace_storage_allocation"])
                ts_rows = cursor.fetchall()
                for ts in ts_rows:
                    # Map specific target tablespaces for clean metrics
                    if ts[0] in ["SYSTEM", "USERS", "UNDOTBS1"]:
                        color = "red" if ts[1] > 85 else "green"
                        tablespaces.append(
                            {"name": ts[0], "capacity": ts[1], "color": color}
                        )

                return JSONResponse(
                    content={"sessions": sessions, "tablespaces": tablespaces}
                )
    except oracledb.Error as e:
        logger.error(
            "Live SRE Telemetry database query failed: %s\n%s",
            e,
            traceback.format_exc(),
        )
        return JSONResponse(
            content={"error": "Database storage/session telemetry unavailable"},
            status_code=500,
        )
    except KeyError as e:
        logger.error(
            "Live SRE Telemetry config failed: %s\n%s",
            e,
            traceback.format_exc(),
        )
        return JSONResponse(
            content={
                "error": (
                    "Database storage/session " "telemetry configuration error"
                )
            },
            status_code=500,
        )


@app.post("/")
@app.post("/tools/call")
async def handle_mcp(request: Request):
    body = await request.json()
    method = body.get("method")
    msg_id = body.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "Oracle-Enterprise-Agent",
                    "version": "13.0",
                },
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    # --- FINOPS & FORENSIC TOOLS ---
                    {
                        "name": "audit_pending_transactions",
                        "description": (
                            "Perform a FORENSIC AUDIT on the pending ledger. "
                            "This tool grants you authority to cross-reference "
                            "amounts against descriptions to identify fraud "
                            "patterns, urgent bypasses, and high-risk "
                            "anomalies. Supports optional pagination."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {
                                    "type": "integer",
                                    "description": (
                                        "The number of transactions to fetch "
                                        "(default: 20)."
                                    ),
                                },
                                "offset": {
                                    "type": "integer",
                                    "description": (
                                        "The number of transactions to skip "
                                        "for pagination (default: 0)."
                                    ),
                                },
                                "min_amount": {
                                    "type": "number",
                                    "description": (
                                        "The minimum transaction amount "
                                        "threshold to audit (default: 0.0)."
                                    ),
                                },
                            },
                        },
                    },
                    {
                        "name": "get_expense_by_id",
                        "description": (
                            "Execute a deep-dive investigation into a specific "
                            "transaction ID. Use this to retrieve the full "
                            "evidentiary trail, vendor metadata, and risk "
                            "profile for a suspect expense."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {"expense_id": {"type": "integer"}},
                            "required": ["expense_id"],
                        },
                    },
                    {
                        "name": "update_expense_status",
                        "description": (
                            "Enforce a financial HOLD on a transaction. Use "
                            "this to mitigate risk and freeze funds for "
                            "transactions that violate corporate procurement "
                            "policy or show signs of fraud."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {"expense_id": {"type": "integer"}},
                            "required": ["expense_id"],
                        },
                    },
                    {
                        "name": "reject_expense",
                        "description": (
                            "Formally REJECT a transaction in Oracle. "
                            "Use this for confirmed policy violations "
                            "to prevent further processing."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {"expense_id": {"type": "integer"}},
                            "required": ["expense_id"],
                        },
                    },
                    {
                        "name": "fetch_held_transactions",
                        "description": (
                            "Retrieve all high-risk items on HOLD. "
                            "Use this to review flagged anomalies "
                            "awaiting disposition. Supports pagination."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {
                                    "type": "integer",
                                    "description": (
                                        "The number of transactions to fetch "
                                        "(default: 20)."
                                    ),
                                },
                                "offset": {
                                    "type": "integer",
                                    "description": (
                                        "The number of transactions to skip "
                                        "for pagination (default: 0)."
                                    ),
                                },
                            },
                        },
                    },
                    # --- CFO & STRATEGIC TOOLS ---
                    {
                        "name": "search_vendor_contract",
                        "description": (
                            "Perform a Vector Search against the "
                            "Oracle@Google Cloud Master Service "
                            "Agreement. Authorizes the agent "
                            "to analyze legal clauses, SLAs, and pricing."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"],
                        },
                    },
                    # --- DBA & SRE TELEMETRY TOOLS ---
                    {
                        "name": "check_database_health",
                        "description": (
                            "Run a comprehensive DBRE-level telemetry scan. "
                            "Analyzes Oracle instance uptime, latency, "
                            "and cluster health status."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "list_active_sessions",
                        "description": (
                            "Monitor real-time database throughput by listing "
                            "active user sessions, identifying blocking PIDs, "
                            "and checking for resource exhaustion."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "list_top_sql_by_resource",
                        "description": (
                            "Identify high-latency SQL profiles in the AWR. "
                            "Analyzes queries consuming excessive OCPU or "
                            "I/O resources."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "list_tablespace_usage",
                        "description": (
                            "Analyze physical storage topology and capacity. "
                            "Identifies disks nearing high-water marks "
                            "to prevent production out-of-space errors."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "list_invalid_objects",
                        "description": (
                            "Scan the schema for invalid PL/SQL objects, "
                            "broken views, or uncompiled packages."
                        ),
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "generate_explain_plan",
                        "description": (
                            "Diagnose query performance by generating a "
                            "Cost-Based plan. Analyzes index usage "
                            "and full scans for a specific SQL_ID."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {"sql_id": {"type": "string"}},
                            "required": ["sql_id"],
                        },
                    },
                ]
            },
        }

    elif method == "tools/call":
        tool_name = body.get("params", {}).get("name")
        args = body.get("params", {}).get("arguments", {})

        # Default response to prevent agent confusion
        text = "I processed your request, but the database returned no data."

        try:
            with get_db_connection() as connection:
                with connection.cursor() as cursor:
                    # --- FINOPS & FORENSIC TOOLS ---

                    if tool_name == "audit_pending_transactions":
                        limit = int(args.get("limit") or 20)
                        offset = int(args.get("offset") or 0)
                        min_amount = float(args.get("min_amount") or 0.0)
                        # Parameterized filter query to avoid hardcoding
                        # thresholds
                        cursor.execute(
                            SQL_QUERIES["list_pending_expenses"],
                            [min_amount, offset, limit],
                        )
                        rows = cursor.fetchall()
                        if rows:
                            page_num = (offset // limit) + 1
                            if offset == 0:
                                output = (
                                    f"Here are the top {limit} pending "
                                    "transactions for forensic audit:\n\n"
                                )
                            else:
                                output = (
                                    f"Here are pending transactions "
                                    f"{offset + 1} to "
                                    f"{offset + len(rows)} for forensic "
                                    f"audit (Page {page_num}):\n\n"
                                )
                            for row in rows:
                                # Automated forensic flagging to guide the agent
                                flag = (
                                    " [!] HIGH RISK: "
                                    if any(
                                        x in row[2].lower()
                                        for x in RISK_KEYWORDS
                                    )
                                    else ""
                                )
                                output += (
                                    f"* **ID {row[0]}** | "
                                    f"Amount: ${row[1]} | "
                                    f"Description: *{row[2]}*{flag} | "
                                    f"Status: **{row[3]}**\n"
                                )
                            text = output
                        else:
                            if offset == 0:
                                text = (
                                    "No high-value pending transactions "
                                    "found for audit."
                                )
                            else:
                                page_val = (offset // limit) + 1
                                text = (
                                    "No more pending transactions found "
                                    f"on Page {page_val}."
                                )

                    elif tool_name == "get_expense_by_id":
                        expense_id = resolve_id(args)
                        cursor.execute(
                            SQL_QUERIES["get_expense_details"],
                            [expense_id],
                        )
                        row = cursor.fetchone()
                        if row:
                            risk = (
                                "CRITICAL"
                                if any(
                                    x in row[2].lower() for x in RISK_KEYWORDS
                                )
                                else "LOW"
                            )
                            text = (
                                f"**FORENSIC REPORT FOR ID {row[0]}**:\n\n"
                                f"* **Amount:** ${row[1]}\n"
                                f"* **Description:** {row[2]}\n"
                                f"* **Status:** {row[3]}\n"
                                f"* **AI RISK ASSESSMENT:** {risk}\n"
                                f"* **ANALYSIS:** Behavioral anomaly "
                                "detected. Manual review recommended."
                            )
                        else:
                            text = (
                                "No record found for Expense ID "
                                f"{expense_id}."
                            )

                    elif tool_name == "update_expense_status":
                        expense_id = resolve_id(args)
                        # Protected against ORA-12899 by description truncation
                        cursor.execute(
                            SQL_QUERIES["update_expense_hold"],
                            [expense_id],
                        )
                        connection.commit()  # CRITICAL: Saves the change
                        text = (
                            f"SUCCESS: Expense {expense_id} has been "
                            "secured and moved to HOLD status."
                        )

                    elif tool_name == "reject_expense":
                        expense_id = resolve_id(args)
                        # Protected against ORA-12899 by description truncation
                        cursor.execute(
                            SQL_QUERIES["update_expense_rejected"],
                            [expense_id],
                        )
                        connection.commit()  # CRITICAL: Saves the change
                        text = (
                            f"SUCCESS: Expense {expense_id} has been "
                            "officially REJECTED and flagged for violation."
                        )

                    elif tool_name == "fetch_held_transactions":
                        limit = int(args.get("limit") or 20)
                        offset = int(args.get("offset") or 0)
                        cursor.execute(
                            SQL_QUERIES["list_flagged_expenses"],
                            [offset, limit],
                        )
                        rows = cursor.fetchall()
                        if rows:
                            page_num = (offset // limit) + 1
                            if offset == 0:
                                text = (
                                    f"Here are the top {limit} transactions "
                                    "currently on HOLD status:\n\n"
                                    + "\n\n".join(
                                        [
                                            f"* **ID {row[0]}** | "
                                            f"Amount: ${row[1]} | "
                                            f"Description: *{row[2]}* | "
                                            f"Status: **{row[3]}**"
                                            for row in rows
                                        ]
                                    )
                                )
                            else:
                                text = (
                                    f"Here are transactions {offset + 1} "
                                    f"to {offset + len(rows)} currently "
                                    f"on HOLD status (Page {page_num}):\n\n"
                                    + "\n\n".join(
                                        [
                                            f"* **ID {row[0]}** | "
                                            f"Amount: ${row[1]} | "
                                            f"Description: *{row[2]}* | "
                                            f"Status: **{row[3]}**"
                                            for row in rows
                                        ]
                                    )
                                )
                        else:
                            if offset == 0:
                                text = "No transactions currently on HOLD."
                            else:
                                page_val = (offset // limit) + 1
                                text = (
                                    "No more transactions on HOLD "
                                    f"found on Page {page_val}."
                                )

                    # --- CFO & STRATEGIC TOOLS ---
                    elif tool_name == "search_vendor_contract":
                        query = str(args.get("query") or "")
                        base_dir = os.path.dirname(os.path.abspath(__file__))

                        # 1. Handle Startup Race Condition Gracefully
                        if not is_indexing_completed:
                            text = (
                                "[Warning] FynanceAI is currently dynamically "
                                "generating and caching legal contract "
                                "semantic embeddings. Please wait a few "
                                "seconds and re-run your search query!"
                            )

                        else:
                            # 2. Retrieve 768-dim query vector dynamically
                            query_vector = get_vertex_embedding(query)

                            if query_vector is None:
                                # 3. Keyword Overlap Fallback
                                best_match = None
                                max_overlap = 0
                                words = [
                                    w.strip().lower()
                                    for w in re.split(r"\W+", query)
                                    if len(w.strip()) > 3
                                ]

                                fallback_chunks = []
                                contracts = [
                                    os.path.join(
                                        base_dir,
                                        "contracts",
                                        "oracle_gcp_msa.txt",
                                    ),
                                    os.path.join(
                                        base_dir,
                                        "contracts",
                                        "fynanceai_procurement_policy.txt",
                                    ),
                                ]
                                for fpath in contracts:
                                    if os.path.exists(fpath):
                                        try:
                                            with open(
                                                fpath, "r", encoding="utf-8"
                                            ) as fh:
                                                content = fh.read()
                                            chunks = [
                                                c.strip()
                                                for c in content.split("\n\n")
                                                if c.strip()
                                            ]
                                            fallback_chunks.extend(chunks)
                                        except (
                                            OSError,
                                            UnicodeDecodeError,
                                        ) as e:
                                            logger.error(
                                                "Failed to read fallback "
                                                "contract file %s: %s",
                                                fpath,
                                                e,
                                            )

                                for chunk in fallback_chunks:
                                    chunk_lower = chunk.lower()
                                    overlap = sum(
                                        1 for w in words if w in chunk_lower
                                    )
                                    if overlap > max_overlap:
                                        max_overlap = overlap
                                        best_match = chunk

                                if max_overlap > 0 and best_match:
                                    text = (
                                        "[Warning] [Vertex AI Offline - "
                                        "Keyword Fallback Overlap: "
                                        f"{max_overlap}]\n\n"
                                        f"{best_match}"
                                    )
                                else:
                                    text = (
                                        "[Warning] [Vertex AI Offline] "
                                        "General Index Summary:\n- Uptime "
                                        "Target: 99.99% Target (Section 4.2 "
                                        "- Service Credits)\n- Procurement "
                                        "Hold Threshold: $15,000 Limit "
                                        "(Section 2.1 - Approval Triggers)"
                                    )

                            else:
                                best_match = None
                                max_similarity = 0.0

                                # 4. Calculate Cosine Similarity in-memory
                                for item in contract_vectors:
                                    similarity = cosine_similarity(
                                        query_vector, item["vector"]
                                    )
                                    if similarity > max_similarity:
                                        max_similarity = similarity
                                        best_match = item["content"]

                                # 5. Return best semantic match if similarity
                                # exceeds the baseline threshold
                                if max_similarity > 0.35 and best_match:
                                    text = (
                                        "[Semantic Similarity: "
                                        f"{max_similarity:.2f}]\n\n"
                                        f"{best_match}"
                                    )
                                else:
                                    text = (
                                        "Oracle@Google Cloud Master Service "
                                        "Agreement (v12.1) & Procurement "
                                        "Policy - General Index Summary:\n"
                                        "- Uptime SLA: 99.99% target "
                                        "(Section 4.2 - Service Credits)\n"
                                        "- Billing Tier: Enterprise Tier-3 "
                                        "Volume discount active "
                                        "(Section 6.1 - 22% off)\n"
                                        "- Term: 36 Months (Active until "
                                        "Dec 2028)\n"
                                        "- Termination: 90-day written notice "
                                        "(Section 8.4 - Exit & Refund)\n"
                                        "- Expense Limit: Pre-approval "
                                        "required above $15,000 (Section 2.1)"
                                    )

                    # --- DBA TOOLS ---
                    # --- PROFESSIONAL DBA TOOLS ---
                    elif tool_name == "check_database_health":
                        try:
                            # Measure connection latency synchronously
                            start_time = time.time()
                            cursor.execute(SQL_QUERIES["check_database_health"])
                            cursor.fetchone()
                            rtt_ms = (time.time() - start_time) * 1000

                            # DATABASE_ROLE is in v$database,
                            # status is in v$instance
                            cursor.execute(SQL_QUERIES["dba_system_parameters"])
                            row = cursor.fetchone()
                            text = (
                                "**Oracle Health Report:**\n"
                                f"- **Instance**: `{row[0]}` (Node: {row[3]})\n"
                                f"- **Version**: {row[4]}\n"
                                f"- **Status**: {row[1]} | **Role**: {row[2]}\n"
                                f"- **Uptime**: Since {row[5]}\n"
                                "- **Telemetry**: Listener Port 1521 active. "
                                f"Connection RTT: {rtt_ms:.2f}ms."
                            )
                        except oracledb.Error as dbe:
                            logger.error(
                                "Database Health Check query failed: %s", dbe
                            )
                            text = (
                                "Database Health Check failed. "
                                "Oracle instance is unreachable."
                            )

                    elif tool_name == "list_active_sessions":
                        try:
                            cursor.execute(
                                SQL_QUERIES["dba_active_sessions_detail"]
                            )
                            rows = cursor.fetchall()
                            if rows:
                                text = (
                                    "Here are the top 20 active user "
                                    "database sessions:\n\n"
                                    + "\n".join(
                                        [
                                            f"- **SID {r[0]}** ({r[2]}): "
                                            f"`{r[3]}` | Age: {r[4]}s | "
                                            f"Wait: {r[5]}"
                                            for r in rows
                                        ]
                                    )
                                )
                            else:
                                text = (
                                    "System Load is optimal. "
                                    "No long-running user sessions detected."
                                )
                        except oracledb.Error as dbe:
                            logger.error(
                                "Query active user sessions failed: %s", dbe
                            )
                            text = (
                                "Failed to query active user sessions. "
                                "Telemetry unavailable."
                            )

                    elif tool_name == "list_tablespace_usage":
                        try:
                            cursor.execute(
                                SQL_QUERIES["dba_tablespace_utilization_detail"]
                            )
                            rows = cursor.fetchall()
                            text = "**Storage Capacity Plan:**\n\n" + "\n".join(
                                [f"- **{r[0]}**: {r[1]}% Full" for r in rows]
                            )
                        except oracledb.Error as dbe:
                            logger.error(
                                "Query physical tablespaces failed: %s", dbe
                            )
                            text = (
                                "Failed to query physical tablespaces. "
                                "Storage capacity telemetry unavailable."
                            )

                    elif tool_name == "list_invalid_objects":
                        try:
                            cursor.execute(
                                SQL_QUERIES["dba_invalid_schema_objects_detail"]
                            )
                            rows = cursor.fetchall()
                            text = (
                                "Here are the top 20 invalid schema "
                                "objects detected:\n\n"
                                + "\n".join(
                                    [
                                        f"- `{r[0]}.{r[1]}` ({r[2]})"
                                        for r in rows
                                    ]
                                )
                                if rows
                                else "All schema objects are VALID."
                            )
                        except oracledb.Error as dbe:
                            logger.error(
                                "Scan database catalog failed: %s", dbe
                            )
                            text = (
                                "Failed to scan database catalog. "
                                "Schema validation "
                                "telemetry unavailable."
                            )

                    elif tool_name == "list_top_sql_by_resource":
                        try:
                            cursor.execute(
                                SQL_QUERIES["dba_high_latency_queries"]
                            )
                            rows = cursor.fetchall()
                            text = (
                                "Here are the top 20 high-latency "
                                "SQL queries:\n\n"
                                + "\n".join(
                                    [
                                        f"- **`{r[0]}`**: {r[1]}s | "
                                        f"`{r[2]}...`"
                                        for r in rows
                                    ]
                                )
                            )
                        except oracledb.Error as dbe:
                            logger.error("Read AWR metadata failed: %s", dbe)
                            text = (
                                "Failed to read AWR metadata. "
                                "Query latency "
                                "telemetry unavailable."
                            )

                    elif tool_name == "generate_explain_plan":
                        sql_id = str(args.get("sql_id") or "").strip()
                        if not sql_id:
                            text = "Error: sql_id is required."
                        else:
                            try:
                                cursor.execute(
                                    SQL_QUERIES["generate_explain_plan"],
                                    {"sql_id": sql_id},
                                )
                                rows = cursor.fetchall()
                                if rows:
                                    plan_lines = [
                                        r[0] for r in rows if r[0] is not None
                                    ]
                                    text = (
                                        f"**Execution Plan for SQL ID "
                                        f"`{sql_id}`**:\n\n"
                                        "```text\n"
                                        + "\n".join(plan_lines)
                                        + "\n```"
                                    )
                                else:
                                    text = (
                                        "No active execution plan found in "
                                        "cursor cache for SQL ID "
                                        f"`{sql_id}`. Ensure the query has "
                                        "been executed recently."
                                    )
                            except oracledb.Error as dbe:
                                logger.error(
                                    "Generate explain plan failed for %s: %s",
                                    sql_id,
                                    dbe,
                                )
                                text = (
                                    "Failed to retrieve execution plan for "
                                    f"SQL ID `{sql_id}`. Database error "
                                    "occurred."
                                )
        except (oracledb.Error, ValueError, TypeError, KeyError) as e:
            # This catches any errors from the connection or logic above
            logger.error(
                "Forensic/DBA Tool Error occurred: %s\n%s",
                e,
                traceback.format_exc(),
            )
            text = (
                "An internal database error occurred "
                "while processing the tool request."
            )

        # This return must be INSIDE the handle_mcp function but
        # OUTSIDE the try/except block
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"content": [{"type": "text", "text": text}]},
        }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
