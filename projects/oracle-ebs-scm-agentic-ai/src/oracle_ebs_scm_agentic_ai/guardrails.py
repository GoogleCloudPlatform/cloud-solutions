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

"""Deterministic guardrails wired into the ADK agent callbacks.

* ``before_agent``: answers greetings with the help menu and screens out
  common prompt injection phrases, database commands typed into the chat,
  and gibberish.
* ``before_tool``: accepts only single read-only SELECT statements over the
  objects in the semantic maps and caps their rows. A writeback call first
  becomes the planner's pending plan. It runs only on a later turn, when the
  planner's whole message is a confirmation and the call matches that plan
  exactly.
* ``after_tool``: bounds the rows and characters that reach the model, and
  replaces failed writeback results with a planner-safe message.
* ``on_tool_error`` and ``on_model_error``: replace transport and Gemini
  errors with planner-friendly messages. Cloud Logging keeps the detailed
  error, which the user never sees.
"""

import hashlib
import json
import logging
import re
import string
from functools import cache
from pathlib import Path
from typing import Any, Final

import sqlglot
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import errors as genai_errors
from google.genai import types
from oracle_ebs_scm_agentic_ai.failover import TRANSIENT_STATUS_CODES
from oracle_ebs_scm_agentic_ai.semantic_mapping import (
    DEFAULT_SCHEMAS,
    documented_objects,
)
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlglot.optimizer.scope import traverse_scope
from sqlglot.tokenizer_core import TokenType

logger = logging.getLogger(__name__)

SQL_TOOL_DIALECTS: Final[dict[str, str]] = {
    "ebs_execute_sql": "oracle",
    "bq_execute_sql": "bigquery",
}
FORECAST_TOOL: Final[str] = "bq_forecast"
GOOGLE_MAPS_TOOLS: Final[tuple[str, ...]] = (
    "maps_compute_routes",
    "places_search_text",
    "weather_alerts",
    "weather_daily_forecast",
)
WRITE_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "ebs_close_workflow_notification",
        "ebs_stage_interorg_transfer",
        "ebs_stage_purchase_requisition",
        "ebs_update_safety_stock",
    }
)
MCP_TOOLS: Final[tuple[str, ...]] = (
    *SQL_TOOL_DIALECTS,
    FORECAST_TOOL,
    *GOOGLE_MAPS_TOOLS,
    *sorted(WRITE_TOOLS),
)

HELP_MENU_PATH: Final[Path] = Path(__file__).parent / "help_menu.txt"
GREETING_HELP_PHRASES: Final[frozenset[str]] = frozenset(
    {
        "capabilities",
        "commands",
        "good afternoon",
        "good evening",
        "good morning",
        "hello",
        "help",
        "help me",
        "hey",
        "hi",
        "how can you help",
        "menu",
        "options",
        "show capabilities",
        "show menu",
        "start",
        "what can you do",
        "who are you",
    }
)
GREETING_WORDS: Final[frozenset[str]] = frozenset({"hello", "hey", "hi"})
# A greeting word with up to two more words, such as "hi there", is a
# greeting. A longer message, or one with a code such as "hi MIA", is a
# question for the model.
MAX_GREETING_EXTRA_WORDS: Final[int] = 2
PROMPT_INJECTION_MARKERS: Final[tuple[str, ...]] = (
    "disregard the system prompt",
    "disregard your instructions",
    "ignore all previous instructions",
    "ignore previous instructions",
    "ignore your instructions",
    "print your instructions",
    "reveal your instructions",
    "reveal your system prompt",
    "show your system prompt",
)
# "You are now" counts only at the start of a sentence, so that a question
# such as "Show the plan you are now proposing" still reaches the model.
PROMPT_INJECTION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:"
    + "|".join(re.escape(marker) for marker in PROMPT_INJECTION_MARKERS)
    + r")\b|(?:^|[.!?])\s*you are now\b",
    re.IGNORECASE,
)
# Each data-changing command needs its SQL shape after the keywords, so that
# a request such as "Delete from the plan the requisition" reaches the model.
CHAT_SQL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:drop|truncate|alter)\s+(?:table|view|index|package|procedure|"
    r"user|schema)\b"
    r"|\bdelete\s+from\s+[\w.$#]+\s*(?:\bwhere\b|;|$)"
    r"|\binsert\s+into\s+[\w.$#]+\s*(?:\(|\bvalues\b|\bselect\b)"
    r"|\bupdate\s+[\w.$#]+\s+set\s+\w+\s*="
    r"|\bexecute\s+immediate\b"
    r"|\bgrant\s+\w+\s+on\s+[\w.$#]+\s+to\b"
    r"|\b(?:dbms|utl)_\w+",
    re.IGNORECASE,
)
CONFIRMATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\W*(?:confirmed|i confirm)\W*", re.IGNORECASE
)
PLAN_INVOCATION_KEY: Final[str] = "voltguard_plan_invocation"
PLAN_CALL_PREFIX: Final[str] = "voltguard_plan_call:"
FORBIDDEN_FUNCTION_PREFIXES: Final[tuple[str, ...]] = ("DBMS_", "UTL_")
FORBIDDEN_FUNCTIONS: Final[frozenset[str]] = frozenset(
    {
        "BFILENAME",
        "DBURITYPE",
        "EXTERNAL_QUERY",
        "HTTPURITYPE",
        "URIFACTORY",
        "XDBURITYPE",
        "XMLPARSE",
        "XMLTYPE",
    }
)
IDENTIFIER_TOKENS: Final[frozenset[TokenType]] = frozenset(
    {TokenType.IDENTIFIER, TokenType.VAR}
)
PACKAGE_CALL_PROBLEM: Final[str] = (
    "Queries can't call database packages or object methods such as "
    "{call}. Use plain SELECT expressions."
)
UNKNOWN_QUALIFIER_PROBLEM: Final[str] = (
    "{column} doesn't name a table, alias, or WITH query of this query. "
    "Qualify each column with a table alias, and don't call database "
    "packages."
)
WRITE_NODES: Final[tuple[type[exp.Expression], ...]] = (
    exp.Alter,
    exp.Command,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Lock,
    exp.Merge,
    exp.TruncateTable,
    exp.Update,
)
MAX_RESULT_ROWS: Final[int] = 200
MAX_RESULT_CHARS: Final[int] = 200_000
# Row bound of a forecast history query: about 2 years of daily issues for
# every hub and item, so it never truncates a documented series.
MAX_HISTORY_ROWS: Final[int] = 10_000
TABLE_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[A-Za-z_]\w*\.[A-Za-z_]\w*"
)
RESULT_TOOLS: Final[frozenset[str]] = frozenset(
    {*SQL_TOOL_DIALECTS, FORECAST_TOOL}
)

INJECTION_REPLY: Final[str] = (
    "I can't follow instructions that try to change my role or my rules. "
    "Ask me about inventory, SLA reservations, transfers, or purchase orders."
)
CHAT_SQL_REPLY: Final[str] = (
    "I don't run database commands typed into the chat. Describe what you "
    "need in plain words, and I'll query Oracle EBS and BigQuery for you."
)
GIBBERISH_REPLY: Final[str] = (
    "I couldn't understand that message. Type **help** to see what I can do."
)
PLAN_RECORDED: Final[str] = (
    "Nothing ran, and Oracle EBS hasn't changed: this exact call is now the "
    "pending plan. Present the plan and ask the planner to reply "
    '"Confirmed". After that reply, call this tool again with exactly the '
    "same values."
)
TOOL_UNAVAILABLE: Final[str] = (
    "The Oracle EBS and BigQuery data service did not respond. Tell the "
    "planner the data service is temporarily unavailable and to try again "
    "in a few minutes. Do not guess any values."
)
WRITE_FAILED: Final[str] = (
    "Oracle EBS did not confirm this change. Tell the planner that Oracle "
    "EBS hasn't confirmed the change and to check it before trying again. "
    "Do not guess the cause."
)
RESULT_TRUNCATED: Final[str] = (
    "The result shows only the first {rows} rows. Filter by hub, item, or "
    "date, or aggregate in SQL, before you draw conclusions from this result."
)
RESULT_TOO_LARGE: Final[str] = (
    "The result is too large to read. Select only the columns you need, and "
    "filter or aggregate the rows in SQL."
)
MODEL_BUSY: Final[str] = (
    "The AI model is busy right now, so I couldn't finish this analysis. "
    "Please try again in a minute."
)
MODEL_FAILED: Final[str] = (
    "I couldn't finish this analysis. Ask about a specific hub, item, or "
    "notification, or start a new conversation and try again."
)
QUERY_FAILED: Final[str] = (
    "The database rejected the query: {}. Fix the query and retry. Never "
    "show this error to the planner."
)
MAPS_UNAVAILABLE: Final[str] = (
    "Google Maps Platform could not answer this request. Check the "
    "coordinates and parameters, or answer without this data. Do not guess "
    "any values."
)
LOCAL_TOOL_FAILED: Final[str] = (
    "The tool couldn't draw the chart or map. Answer from the data you "
    "already have, say that the image isn't available, and don't retry it."
)
TOOL_ERROR_REPLIES: Final[dict[str, str]] = {
    **dict.fromkeys(RESULT_TOOLS, TOOL_UNAVAILABLE),
    **dict.fromkeys(WRITE_TOOLS, WRITE_FAILED),
    **dict.fromkeys(GOOGLE_MAPS_TOOLS, MAPS_UNAVAILABLE),
}
# The part of a failed query's error that helps the model fix the SQL: the
# Oracle error line, or the message of a BigQuery invalidQuery error.
QUERY_ERROR_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"ORA-\d{5}: [^\n]+|(?<=Error 400: )[^\n]+?(?=, invalidQuery)"
)
CONSONANT_RUN: Final[re.Pattern[str]] = re.compile(
    r"[bcdfghjklmnpqrstvwxz]{7,}"
)


@cache
def help_menu() -> str:
    """Read the Markdown capabilities menu from disk once.

    Returns:
        The help menu.
    """
    return HELP_MENU_PATH.read_text(encoding="utf-8")


def user_text(content: types.Content | None) -> str:
    """Join the text parts of a user message.

    Args:
        content: The user message, or None.

    Returns:
        The message text, or an empty string.
    """
    if content is None or not content.parts:
        return ""
    return " ".join(part.text for part in content.parts if part.text).strip()


def reply(text: str) -> types.Content:
    """Wrap text as a model response.

    Args:
        text: The reply text.

    Returns:
        The model content with one text part.
    """
    return types.Content(role="model", parts=[types.Part(text=text)])


def is_greeting_or_help(text: str) -> bool:
    """Detect a greeting or a request for the capabilities menu.

    Args:
        text: The user message.

    Returns:
        True for a help request, or for a greeting word with at most
        MAX_GREETING_EXTRA_WORDS more words that aren't codes.
    """
    cleaned = " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())
    if cleaned in GREETING_HELP_PHRASES:
        return True
    words = re.sub(r"[^\w\s-]", " ", text).split()
    return (
        bool(words)
        and words[0].lower() in GREETING_WORDS
        and len(words) - 1 <= MAX_GREETING_EXTRA_WORDS
        and not any(_is_code(word) for word in words[1:])
    )


def _is_code(token: str) -> bool:
    """Detect hub codes, item codes, IDs, and acronyms.

    Args:
        token: One word of the message.

    Returns:
        True when the token holds a digit or a hyphen, or is an upper-case
        word of at most 6 letters.
    """
    has_code_char = any(char.isdigit() or char == "-" for char in token)
    return has_code_char or (token.isupper() and len(token) <= 6)


def is_gibberish(text: str) -> bool:
    """Detect keyboard mashing and messages without words or numbers.

    Codes such as PHX, MRP, and VG-GEN-7500 are not words, and only Latin
    letters count toward the vowel check, so messages in other scripts pass.

    Args:
        text: The user message.

    Returns:
        True for a message without letters or digits, with too few vowels,
        or with a long run of consonants.
    """
    if not any(char.isalnum() for char in text):
        return True
    words = [
        "".join(char for char in token.lower() if "a" <= char <= "z")
        for token in (part.strip(string.punctuation) for part in text.split())
        if token and not _is_code(token)
    ]
    letters = "".join(words)
    vowels = sum(char in "aeiouy" for char in letters)
    if len(letters) >= 6 and vowels / len(letters) < 0.15:
        return True
    return any(CONSONANT_RUN.search(word) for word in words)


def screen_user_message(text: str) -> str | None:
    """Pick a canned reply for a message that the model must not handle.

    Args:
        text: The user message.

    Returns:
        The help menu, or the reply that screens out prompt injection,
        database commands, or gibberish, or None to let the model answer.
    """
    if is_greeting_or_help(text):
        return help_menu()
    if PROMPT_INJECTION_PATTERN.search(text):
        logger.warning("Blocked prompt injection: %r", text)
        return INJECTION_REPLY
    if CHAT_SQL_PATTERN.search(text):
        logger.warning("Blocked database command typed in chat: %r", text)
        return CHAT_SQL_REPLY
    if is_gibberish(text):
        logger.info("Rejected gibberish: %r", text)
        return GIBBERISH_REPLY
    return None


def before_agent(callback_context: CallbackContext) -> types.Content | None:
    """Screen every user message (ADK before_agent_callback).

    Args:
        callback_context: The ADK callback context with the user message.

    Returns:
        The canned reply that ends the turn, or None to run the agent.
    """
    canned = screen_user_message(user_text(callback_context.user_content))
    return reply(canned) if canned is not None else None


def _forbidden_identifier(sql: str, dialect: str) -> str | None:
    """Return the first DBMS_ or UTL_ identifier in the SQL text.

    The check reads tokens, not the parse tree, because sqlglot rewrites
    some package calls, such as DBMS_RANDOM.VALUE, into plain functions.

    Args:
        sql: The SQL text.
        dialect: The sqlglot dialect.

    Returns:
        The identifier in upper case, or None.
    """
    for token in sqlglot.tokenize(sql, read=dialect):
        name = token.text.upper()
        if token.token_type in IDENTIFIER_TOKENS and name.startswith(
            FORBIDDEN_FUNCTION_PREFIXES
        ):
            return name
    return None


def _column_qualifiers(statement: exp.Expr) -> set[str]:
    """Collect the table, alias, and WITH query names that qualify columns.

    Args:
        statement: The parsed query.

    Returns:
        The names in upper case.
    """
    names = {table.name.upper() for table in statement.find_all(exp.Table)}
    for alias in statement.find_all(exp.TableAlias):
        names.add(alias.name.upper())
        names.update(column.name.upper() for column in alias.columns)
    return names - {""}


def _function_call_problem(
    statement: exp.Expr, sql: str, dialect: str
) -> str | None:
    """Find a package call, an object method, or an outbound built-in.

    Args:
        statement: The parsed query.
        sql: The SQL text.
        dialect: The sqlglot dialect.

    Returns:
        The problem for the model, or None.
    """
    package = _forbidden_identifier(sql, dialect)
    if package is not None:
        return f"Queries can't call {package}."
    for dot in statement.find_all(exp.Dot):
        if isinstance(dot.expression, exp.Func):
            return PACKAGE_CALL_PROBLEM.format(call=dot.sql(dialect=dialect))
    qualifiers = _column_qualifiers(statement)
    for column in statement.find_all(exp.Column):
        if column.args.get("db") is not None or (
            column.table and column.table.upper() not in qualifiers
        ):
            return UNKNOWN_QUALIFIER_PROBLEM.format(
                column=column.sql(dialect=dialect)
            )
    for function in statement.find_all(exp.Anonymous):
        if function.name.upper() in FORBIDDEN_FUNCTIONS:
            return f"Queries can't call {function.name.upper()}."
    return None


def _table_allowed(table: exp.Table, cte_names: set[str], dialect: str) -> bool:
    """Check one table reference against the dialect's allowlist.

    Args:
        table: The table reference.
        cte_names: The WITH query names that the reference can see, in upper
            case.
        dialect: The sqlglot dialect.

    Returns:
        True for a documented object, a visible WITH query without a schema,
        or Oracle DUAL.
    """
    name = table.name.upper()
    schema = table.db.upper()
    if table.catalog or not name:
        return False
    if not schema and (
        name in cte_names or (dialect == "oracle" and name == "DUAL")
    ):
        return True
    default_schema = DEFAULT_SCHEMAS[dialect]
    return (schema or default_schema, name) in documented_objects(dialect)


def _visible_cte_names(statement: exp.Expr) -> dict[int, set[str]]:
    """Find the WITH query names that each table reference can see.

    SQL scoping makes a WITH query visible to the WITH queries after it, to
    the query that declares it and its subqueries, and inside its own
    definition for recursion. Anywhere else the same name means a database
    object, which the allowlist must cover.

    Args:
        statement: The parsed query.

    Returns:
        The visible names in upper case, keyed by the id of each table
        reference.
    """
    visible: dict[int, set[str]] = {}
    for scope in traverse_scope(statement):
        in_scope = {name.upper() for name in scope.cte_sources}
        for table in scope.tables:
            names = set(in_scope)
            cte = table.find_ancestor(exp.CTE)
            while cte is not None:
                names.add(cte.alias_or_name.upper())
                cte = cte.find_ancestor(exp.CTE)
            visible[id(table)] = names
    return visible


def _object_problem(statement: exp.Expr, dialect: str) -> str | None:
    """Find objects that the dialect's semantic maps don't describe.

    Args:
        statement: The parsed query.
        dialect: The sqlglot dialect.

    Returns:
        The problem that names the objects, or None.
    """
    visible = _visible_cte_names(statement)
    unknown = sorted(
        {
            ".".join(
                filter(None, (table.catalog, table.db, table.name))
            ).upper()
            or table.sql(dialect=dialect)
            for table in statement.find_all(exp.Table)
            if not _table_allowed(table, visible.get(id(table), set()), dialect)
        }
    )
    if unknown:
        names = ", ".join(unknown)
        return (
            f"{names} is not in the semantic maps. Query only the documented "
            "views and tables, named as the semantic maps name them."
        )
    return None


def _row_bound(limit: exp.Expr | None) -> int | None:
    """Read the literal row bound of a LIMIT or FETCH clause.

    Args:
        limit: The LIMIT or FETCH clause, or None.

    Returns:
        The number of rows, or None for a missing, non-literal, or
        percentage bound.
    """
    if isinstance(limit, exp.Fetch):
        if "PERCENT" in str(limit.args.get("limit_options") or "").upper():
            return None
        count = limit.args.get("count")
        if count is None:
            return 1
    elif isinstance(limit, exp.Limit):
        count = limit.expression
    else:
        return None
    if isinstance(count, exp.Literal) and count.is_int:
        return int(count.this)
    return None


def cap_rows(statement: exp.Query, dialect: str, max_rows: int) -> str:
    """Generate the query's SQL with at most max_rows rows and no comments.

    A missing, non-literal, percentage, or larger LIMIT or FETCH bound on
    the outermost query becomes max_rows. The SQL comes from the parse
    tree, so the database runs exactly the query that passed validation.

    Args:
        statement: The validated query.
        dialect: The sqlglot dialect.
        max_rows: The most rows that the outermost query may return.

    Returns:
        The SQL to run.
    """
    bound = _row_bound(statement.args.get("limit"))
    if bound is None or bound > max_rows:
        statement = statement.limit(max_rows)
    return statement.sql(dialect=dialect, comments=False)


def validate_read_query(
    sql: object, dialect: str, max_rows: int
) -> tuple[str | None, str]:
    """Validate one read-only SELECT.

    Args:
        sql: The SQL text that the model passed to the tool.
        dialect: The sqlglot dialect, either ``oracle`` or ``bigquery``.
        max_rows: The most rows that the outermost query may return.

    Returns:
        A (problem, SQL to run) pair. The problem is None for a valid query,
        and the SQL is empty for an invalid one.
    """
    if not isinstance(sql, str) or not sql.strip():
        return "Provide one SQL SELECT statement.", ""
    try:
        statements = [
            statement
            for statement in sqlglot.parse(sql, read=dialect)
            if statement is not None
            and not isinstance(statement, exp.Semicolon)
        ]
    except ParseError as exc:
        detail = str(exc).splitlines()[0] if str(exc) else "syntax error"
        return f"The guardrail couldn't parse the SQL: {detail}.", ""
    if len(statements) != 1:
        return "Run exactly one SQL statement per call.", ""
    statement = statements[0]
    if not isinstance(statement, exp.Query) or statement.find(*WRITE_NODES):
        return "The SQL tools run only read-only SELECT queries.", ""
    problem = _function_call_problem(
        statement, sql, dialect
    ) or _object_problem(statement, dialect)
    if problem is not None:
        return problem, ""
    return None, cap_rows(statement, dialect, max_rows)


def is_explicit_confirmation(text: str) -> bool:
    """Check whether the planner's whole message confirms the plan.

    Args:
        text: The user message.

    Returns:
        True for "Confirmed" or "I confirm" with nothing else but
        punctuation and spaces.
    """
    return CONFIRMATION_PATTERN.fullmatch(text) is not None


def _normalized(value: object) -> object:
    """Normalize one writeback value so that equal plans compare equal.

    Args:
        value: The argument value.

    Returns:
        Text with collapsed spaces in lowercase, a whole float as an int, or
        any other value unchanged.
    """
    if isinstance(value, str):
        return " ".join(value.split()).casefold()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def plan_key(tool_name: str, args: dict[str, Any]) -> str:
    """Derive the session state key of one exact writeback call.

    Args:
        tool_name: The writeback tool name.
        args: The call arguments.

    Returns:
        The state key, a prefix plus the SHA-256 digest of the call.
    """
    call = [tool_name, {name: _normalized(v) for name, v in args.items()}]
    digest = hashlib.sha256(
        json.dumps(call, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"{PLAN_CALL_PREFIX}{digest}"


def gate_writeback(
    tool_name: str, args: dict[str, Any], tool_context: ToolContext
) -> dict[str, Any] | None:
    """Run a writeback only when it matches the confirmed pending plan.

    The plan is the set of writeback calls that the latest planning turn
    recorded. A call runs when the planner's current message is a
    confirmation and that earlier turn recorded the same call. Any
    other call replaces the plan, so the planner must confirm it first.

    Args:
        tool_name: Name of the writeback tool.
        args: Arguments of the call.
        tool_context: ADK context with the session state and user message.

    Returns:
        None to run the call, or the pending-plan result for the model.
    """
    state = tool_context.state
    key = plan_key(tool_name, args)
    plan_invocation = state.get(PLAN_INVOCATION_KEY)
    if (
        plan_invocation not in (None, tool_context.invocation_id)
        and state.get(key) == plan_invocation
        and is_explicit_confirmation(user_text(tool_context.user_content))
    ):
        state[key] = None
        logger.info("Running confirmed %s", tool_name)
        return None
    state[PLAN_INVOCATION_KEY] = tool_context.invocation_id
    state[key] = tool_context.invocation_id
    logger.info("Recorded %s as the pending plan", tool_name)
    return {"status": "pending_confirmation", "message": PLAN_RECORDED}


def _blocked(tool_name: str, reason: str) -> dict[str, Any]:
    """Log a blocked tool call and build the result that the model sees.

    Args:
        tool_name: The tool name.
        reason: The problem for the model.

    Returns:
        The blocked status and the reason.
    """
    logger.warning("Blocked %s: %s", tool_name, reason)
    return {"status": "blocked", "error": reason}


def validate_history(history: object) -> tuple[str | None, str]:
    """Validate the history_data input of the ad hoc forecast tool.

    Args:
        history: A ``dataset.table`` name or one GoogleSQL SELECT statement.

    Returns:
        A (problem, history to run) pair, as validate_read_query returns.
    """
    name = history.strip() if isinstance(history, str) else ""
    if TABLE_NAME_PATTERN.fullmatch(name):
        dataset, _, table = name.upper().partition(".")
        if (dataset, table) in documented_objects("bigquery"):
            return None, name
        return (
            f"{name.upper()} is not in the semantic maps. Use a documented "
            "BigQuery table or one SELECT statement as the history."
        ), ""
    return validate_read_query(history, "bigquery", MAX_HISTORY_ROWS)


def before_tool(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> dict[str, Any] | None:
    """Check SQL and gate writebacks before each tool call.

    ADK runs this as the before_tool_callback. It replaces the SQL or the
    forecast history with the validated, row-capped text.

    Args:
        tool: The tool that the model calls.
        args: The call arguments, which the callback can change.
        tool_context: The ADK tool context.

    Returns:
        The result that replaces the call, or None to run the tool.
    """
    if tool.name in WRITE_TOOLS:
        return gate_writeback(tool.name, args, tool_context)
    if tool.name in SQL_TOOL_DIALECTS:
        problem, query = validate_read_query(
            args.get("sql"), SQL_TOOL_DIALECTS[tool.name], MAX_RESULT_ROWS + 1
        )
        if problem is not None:
            return _blocked(tool.name, problem)
        args["sql"] = query
    elif tool.name == FORECAST_TOOL:
        problem, history = validate_history(args.get("history_data"))
        if problem is not None:
            return _blocked(tool.name, problem)
        args["history_data"] = history
    logger.info(
        "Running %s for invocation %s with arguments %s",
        tool.name,
        tool_context.invocation_id,
        sorted(args),
    )
    return None


def _tool_failure(
    tool_name: str, tool_response: dict[str, Any]
) -> dict[str, Any]:
    """Pass only a query's database error to the model and log the rest.

    Args:
        tool_name: The tool name.
        tool_response: The MCP error response.

    Returns:
        The error result for the model.
    """
    content = tool_response.get("content")
    items = content if isinstance(content, list) else []
    text = " ".join(str(item.get("text", "")) for item in items)
    logger.error("%s failed: %s", tool_name, text)
    match = QUERY_ERROR_PATTERN.search(text)
    if tool_name in RESULT_TOOLS and match is not None:
        return {"status": "error", "error": QUERY_FAILED.format(match[0])}
    return {"status": "error", "error": tool_error_reply(tool_name)}


def tool_error_reply(tool_name: str) -> str:
    """Pick the planner-safe error message for a failed tool.

    Args:
        tool_name: The tool name.

    Returns:
        The message for the data service, the writebacks, Google Maps
        Platform, or the local chart and map tools.
    """
    return TOOL_ERROR_REPLIES.get(tool_name, LOCAL_TOOL_FAILED)


def after_tool(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict[str, Any],
) -> dict[str, Any] | None:
    """Bound tool results and hide error details (ADK after_tool_callback).

    Args:
        tool: The tool that ran.
        args: The call arguments, which the callback doesn't read.
        tool_context: The ADK tool context, which the callback doesn't read.
        tool_response: The tool result.

    Returns:
        The replacement result, or None to keep the result unchanged.
    """
    del args, tool_context
    if tool_response.get("isError"):
        return _tool_failure(tool.name, tool_response)
    rows = tool_response.get("content")
    if tool.name not in RESULT_TOOLS or not isinstance(rows, list):
        return None
    logger.info("%s returned %d rows", tool.name, len(rows))
    kept = rows[:MAX_RESULT_ROWS]
    if sum(len(str(row.get("text", ""))) for row in kept) > MAX_RESULT_CHARS:
        return _blocked(tool.name, RESULT_TOO_LARGE)
    if len(rows) <= MAX_RESULT_ROWS:
        return None
    note = RESULT_TRUNCATED.format(rows=MAX_RESULT_ROWS)
    return {**tool_response, "content": [*kept, {"type": "text", "text": note}]}


def on_tool_error(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    error: Exception,
) -> dict[str, Any]:
    """Hide transport error details (ADK on_tool_error_callback).

    Args:
        tool: The tool that failed.
        args: The call arguments. Only their names reach the log.
        tool_context: The ADK tool context.
        error: The exception.

    Returns:
        The planner-safe error result.
    """
    logger.error(
        "Tool %s failed for invocation %s with arguments %s: %r",
        tool.name,
        tool_context.invocation_id,
        sorted(args),
        error,
    )
    return {"status": "error", "error": tool_error_reply(tool.name)}


def on_model_error(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
    error: Exception,
) -> LlmResponse:
    """Answer a failed Gemini call in plain words.

    ADK runs this as the on_model_error_callback. Cloud Logging keeps the
    detailed Gemini error, which the planner never sees.

    Args:
        callback_context: The ADK callback context.
        llm_request: The model request, which the callback doesn't read.
        error: The exception.

    Returns:
        The busy reply for the timeout, quota, and server errors that fail
        over to another model, or the general reply.
    """
    del llm_request
    logger.error(
        "Gemini call failed for invocation %s: %r",
        callback_context.invocation_id,
        error,
    )
    busy = (
        isinstance(error, genai_errors.APIError)
        and error.code in TRANSIENT_STATUS_CODES
    )
    return LlmResponse(content=reply(MODEL_BUSY if busy else MODEL_FAILED))
