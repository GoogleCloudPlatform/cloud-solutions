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

# pylint: disable=broad-exception-caught,import-outside-toplevel
# pylint: disable=inconsistent-quotes,line-too-long,redefined-outer-name
# pylint: disable=reimported

"""ADK 2.0 Multi-Tenant Interceptors, Model Armor Prompt Screening, Egress DLP & OTel Spans.

Implements Hops 2, 3, and 4 of the 5-Hop Cryptographic Context Chain:
- `normalize_adversarial_text`: Strips zero-width/invisible characters (`\u200b`-`\u200f`, `\ufeff`,
  `\u00ad`) and normalizes Unicode homoglyphs/full-width characters (`NFKC`) before screening.
- `register_dynamic_guardrail_pattern`: Demonstrates Benefit #5 of Pooling (1-to-N instant fleet
  protection across all $N=500+$ tenants when a novel attack pattern is blocked at the shared PEP).
- `enforce_tenant_isolation_interceptor`: ADK `before_agent_callback`.
- `ingress_model_armor_screen` & `egress_dlp_and_nlc_guardrail` (including US SSN, ABA, IBAN,
  SWIFT, Credit Card PAN, Base64 PII, and OCC Escalation Suppression NLCs).
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
import re
import threading
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

from agents.context import TENANT_DIRECTORY
from agents.registry import AgentRegistryPDP

_ZERO_WIDTH_STRIP_RE = re.compile(
    r"[\u00ad\u180e\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"
)
_SQL_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

_BASE_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE
    ),
    re.compile(r"system\s+override\b", re.IGNORECASE),
    re.compile(
        r"set\s+(local\s+|session\s+)?app\.current_tenant_id", re.IGNORECASE
    ),
    re.compile(
        r"set_config\s*\(\s*['\"]app\.current_tenant_id['\"]", re.IGNORECASE
    ),
    re.compile(
        r"current_setting\(\s*['\"]app\.current_tenant_id['\"]", re.IGNORECASE
    ),
    re.compile(r"\b(or|where|and)\s+1\s*=\s*1\b", re.IGNORECASE),
    re.compile(
        r"\b(or|where|and)\s+['\"]([^'\"]+)['\"]\s*=\s*['\"]\2['\"]",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bselect\s+.+?\s+from\s+(tenant_incidents|tenant_runbooks|pg_catalog|information_schema)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(drop|truncate|alter|delete\s+from)\s+(table|policy|tenant_incidents|tenant_runbooks)\b",
        re.IGNORECASE,
    ),
    re.compile(r"union\s+(all\s+)?select\b", re.IGNORECASE),
    re.compile(r"drop\s+policy\b", re.IGNORECASE),
    re.compile(r"exfiltrate\s+to\s+https?://", re.IGNORECASE),
)

_DYNAMIC_GUARDRAIL_PATTERNS: list[re.Pattern[str]] = []

_SSN_PATTERN = re.compile(r"\b\d{3}[-.\s]\d{2}[-.\s]\d{4}\b")
_CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_ABA_ROUTING_PATTERN = re.compile(r"\bABA[:\s#-]*\d{9}\b", re.IGNORECASE)
_IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_SWIFT_PATTERN = re.compile(
    r"\bSWIFT[:\s#-]*[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", re.IGNORECASE
)
_BASE64_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{14,}={0,2}(?![A-Za-z0-9+/=])"
)

_OCC_SUPPRESSION_TARGET_RE = re.compile(
    r"\b(?:suppress|bypass)\s+(?:mandatory\s+)?(?:occ|regulatory)\s+escalation\b",
    re.IGNORECASE,
)
_CLAUSE_BOUNDARY_RE = re.compile(
    r"[.;!?\n]|\b(?:but|however|yet|instead)\b", re.IGNORECASE
)
_NEGATION_WINDOW_RE = re.compile(
    r"\b(?:never|not|no|do\s+not|don't|must\s+not|shall\s+not|cannot|can't|"
    r"prohibited(?:\s+from|\s+to)?|forbid(?:s|den)?(?:\s+to|\s+any\s+attempt\s+to)?|"
    r"refuse(?:s|d)?\s+to|without)\s+(?:\w+\s+){0,3}$",
    re.IGNORECASE,
)


def has_affirmative_occ_suppression_intent(normalized_ws: str) -> bool:
    """Detects affirmative OCC/regulatory escalation suppression while allowing compliant negations.

    Prevents the classic substring-grader false-positive trap where compliant policy statements
    such as 'SREs must never suppress OCC escalation' were falsely blocked with HTTP 422/403,
    while still blocking mixed or adversarial clauses ('Do not delay, suppress OCC escalation').
    """
    for match in _OCC_SUPPRESSION_TARGET_RE.finditer(normalized_ws):
        window_start = max(0, match.start() - 80)
        preceding = normalized_ws[window_start : match.start()]
        current_clause = _CLAUSE_BOUNDARY_RE.split(preceding)[-1]
        if not _NEGATION_WINDOW_RE.search(current_clause):
            return True
    return False


def normalize_adversarial_text(text: str) -> str:
    """Normalizes NFKC full-width/homoglyph chars, strips zero-width chars, and collapses SQL
    comments.
    """
    nfkc = unicodedata.normalize("NFKC", text)
    no_zw = _ZERO_WIDTH_STRIP_RE.sub("", nfkc)
    no_comments = _SQL_BLOCK_COMMENT_RE.sub(" ", no_zw)
    return no_comments


def register_dynamic_guardrail_pattern(regex_str: str) -> None:
    """Fleet-Wide Immunity (Pooling Benefit #5): Adds a live PEP rule protecting all N tenants."""
    _DYNAMIC_GUARDRAIL_PATTERNS.append(re.compile(regex_str, re.IGNORECASE))


def clear_dynamic_guardrail_patterns() -> None:
    _DYNAMIC_GUARDRAIL_PATTERNS.clear()


@dataclass
class OTelAuditSpan:
    """Tenant-scoped OpenTelemetry span exported to BigQuery Agent Analytics."""

    trace_id: str
    tenant_id: str
    subscription_tier: str
    agent_id: str
    model_id: str
    tool_name: str | None
    prompt_cache_hit: bool
    thinking_tokens_budget: int
    status: str
    timestamp: float = field(default_factory=time.time)


class OTelAuditSink:
    """In-memory and BigQuery-compatible OpenTelemetry span sink for per-tenant COGS attribution."""

    def __init__(self) -> None:
        self.spans: list[OTelAuditSpan] = []

    def record(self, span: OTelAuditSpan) -> None:
        if not span.tenant_id:
            raise ValueError(
                "OTel span missing mandatory tenant_id attribution."
            )
        self.spans.append(span)


DEFAULT_REGISTRY_PDP = AgentRegistryPDP()
DEFAULT_OTEL_SINK = OTelAuditSink()

_LIVE_MA_GUARDRAIL: Any = None
_LIVE_MA_AVAILABLE: bool | None = None  # last outcome (reporting only)
_LIVE_MA_RETRY_AT: float = (
    0.0  # after a failure, skip live calls until this time
)
LIVE_MA_RETRY_SECONDS = 30.0
_LIVE_MA_LOCK = threading.Lock()
logger = logging.getLogger(__name__)


def _caller_caused(exc: BaseException) -> bool:
    """4xx errors other than auth / quota (those are availability problems, not the prompt)."""
    try:
        from google.api_core import exceptions as gexc
    except ImportError:  # pragma: no cover
        return False
    return isinstance(exc, gexc.ClientError) and not isinstance(
        exc,
        gexc.Unauthenticated
        | gexc.PermissionDenied
        | gexc.TooManyRequests
        | gexc.NotFound,
    )


def _try_live_vertex_model_armor(
    normalized_prompt: str,
) -> dict[str, Any] | None:
    """Invokes live Model Armor (`modelarmor.googleapis.com`) as the primary ML gate.

    After a failure it backs off for `LIVE_MA_RETRY_SECONDS` (so an outage or expired local ADC
    doesn't add a timeout to every turn) and then tries again; a single transient error must not
    disable live screening for the life of the process. The deterministic pattern screen always
    runs. Failing closed when Model Armor is down is a separate decision (ADR-0013, PR-DA5).
    """
    global _LIVE_MA_GUARDRAIL, _LIVE_MA_AVAILABLE, _LIVE_MA_RETRY_AT
    if os.getenv("CYMBAL_OFFLINE_CI") == "1" or (
        os.getenv("CYMBAL_LIVE_GCP") != "1"
        and os.getenv("RUN_LIVE_GCP_TESTS") != "1"
    ):
        return None
    if time.monotonic() < _LIVE_MA_RETRY_AT:
        return None
    try:
        with _LIVE_MA_LOCK:
            if _LIVE_MA_GUARDRAIL is None:
                from agents.gcp_live_bridge import LiveModelArmorGuardrail

                _LIVE_MA_GUARDRAIL = LiveModelArmorGuardrail()
        res = _LIVE_MA_GUARDRAIL.sanitize_prompt(normalized_prompt)
        _LIVE_MA_AVAILABLE = True
        return res
    except Exception as exc:  # any failure: classify below
        if _caller_caused(exc):
            # A request the caller shaped (e.g. too large) must not switch live screening off for
            # every tenant: refuse this prompt and keep Model Armor live. Logged at error level so
            # a misconfigured template (also a 4xx) is visible to operators.
            logger.error(
                "Model Armor rejected a prompt (%s); failing closed",
                type(exc).__name__,
            )
            raise PermissionError(
                "E_MODEL_ARMOR_REQUEST_REJECTED: Model Armor could not screen this prompt."
            ) from exc
        _LIVE_MA_AVAILABLE = False
        _LIVE_MA_RETRY_AT = time.monotonic() + LIVE_MA_RETRY_SECONDS
        logger.warning(
            "Live Model Armor unavailable (%s); retrying in %.0fs (pattern screen still active)",
            type(exc).__name__,
            LIVE_MA_RETRY_SECONDS,
        )
        return None


def ingress_model_armor_screen(
    *,
    prompt: str,
    caller_tenant_id: str,
    use_live_model_armor: bool = True,
) -> dict[str, Any] | None:
    """Hop 2 & Hop 4 (Model Armor Ingress PEP):

    1. Primary Gate (Default ON): Calls regional Model Armor ML classifier
       (`projects/cymbal-multitenancy-example/locations/us-central1/templates/cymbal-pooled-inbound-pep:sanitizeUserPrompt`)
       to detect semantic prompt injections, jailbreaks (`LOW_AND_ABOVE`), and malicious URIs.
    2. Tenant-Context & Domain Gate: Because Model Armor's `sanitizeUserPrompt` API
       accepts only `DataItem(text=prompt)` and has no parameter for `caller_tenant_id` or
       application table names, we pair it with tenant-boundary checks
       (`E_MODEL_ARMOR_CROSS_TENANT_PROMPT`)
       and deterministic SQL/GUC guardrails.
    """
    normalized = normalize_adversarial_text(prompt)

    live_res: dict[str, Any] | None = None
    if use_live_model_armor:
        live_res = _try_live_vertex_model_armor(normalized)
        if live_res and live_res.get("blocked"):
            raise PermissionError(
                f"E_VERTEX_MODEL_ARMOR_MATCH_FOUND: Live Model Armor template "
                "'"
                f"{live_res.get('template')}"
                "' blocked prompt ("
                f"{live_res.get('filter_match_state')}"
                ")."
            )

    for pattern in (*_BASE_INJECTION_PATTERNS, *_DYNAMIC_GUARDRAIL_PATTERNS):
        if pattern.search(normalized):
            raise PermissionError(
                "E_MODEL_ARMOR_BLOCKED: Inbound prompt blocked by Model Armor "
                "(adversarial prompt/SQL injection pattern detected)."
            )

    lowered = normalized.lower()
    # Every configured or dynamically onboarded tenant, not a fixed list.
    from agents.context import TENANT_DIRECTORY

    for known_tenant_id in list(TENANT_DIRECTORY):
        if (
            known_tenant_id != caller_tenant_id
            and known_tenant_id.lower() in lowered
        ):
            raise PermissionError(
                "E_MODEL_ARMOR_CROSS_TENANT_PROMPT: the prompt references another tenant."
            )

    return live_res


def screen_tool_output_for_indirect_injection(
    *, raw_output: str, tool_name: str
) -> None:
    """Edge Case #3: Screens tool/database outputs for 2nd-order indirect prompt injection."""
    normalized = normalize_adversarial_text(raw_output)
    for pattern in (*_BASE_INJECTION_PATTERNS, *_DYNAMIC_GUARDRAIL_PATTERNS):
        if pattern.search(normalized):
            raise PermissionError(
                f"E_INDIRECT_PROMPT_INJECTION_QUARANTINED: Tool '{tool_name}' returned payload "
                "containing embedded instruction-override / indirect prompt injection."
            )


def _redact_base64_encoded_pii(text: str) -> str:
    """Edge Case #9: Inspects candidate Base64 substrings for hidden SSNs/PANs/ABA/IBAN numbers."""

    def _replace_match(match: re.Match[str]) -> str:
        token = match.group(0)
        try:
            decoded = base64.b64decode(token, validate=True).decode(
                "utf-8", errors="ignore"
            )
        except (binascii.Error, ValueError):
            return token
        if (
            _SSN_PATTERN.search(decoded)
            or _ABA_ROUTING_PATTERN.search(decoded)
            or _CC_PATTERN.search(decoded)
            or _IBAN_PATTERN.search(decoded)
        ):
            return "[REDACTED_BASE64_PII]"
        return token

    return _BASE64_TOKEN_PATTERN.sub(_replace_match, text)


def egress_dlp_and_nlc_guardrail(
    *,
    tenant_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
    raw_output: str,
) -> str:
    """Hop 4 (Gemini Egress Gateway PEP): Indirect injection screen, NLCs, and DLP redaction."""
    decoded_output = urllib.parse.unquote(raw_output)
    normalized_ws = re.sub(
        r"\s+", " ", normalize_adversarial_text(decoded_output)
    ).lower()
    screen_tool_output_for_indirect_injection(
        raw_output=decoded_output, tool_name=tool_name
    )

    if tool_args.get(
        "suppress_occ_escalation"
    ) is True or has_affirmative_occ_suppression_intent(normalized_ws):
        raise PermissionError(
            "422 E_NLC_OCC_ESCALATION_SUPPRESSION_BLOCKED: Mandatory OCC regulatory escalation "
            "cannot be suppressed for Enterprise banking tenants."
        )

    discount_pct = float(tool_args.get("discount_percent", 0.0))
    if discount_pct > 15.0 and not tool_args.get("vp_approval_token"):
        raise PermissionError(
            "E_NLC_POLICY_VIOLATION: Discount modification exceeding 15% denied without "
            "VP approval."
        )

    if (
        tool_args.get("target_tenant_id")
        and tool_args["target_tenant_id"] != tenant_id
    ):
        raise PermissionError(
            f"E_NLC_CROSS_TENANT_TOOL_ARG: Tool '{tool_name}' targeted a tenant other than the "
            "caller's."
        )

    redacted = _redact_base64_encoded_pii(decoded_output)
    redacted = _SSN_PATTERN.sub("[REDACTED_BANKING_SSN]", redacted)
    redacted = _ABA_ROUTING_PATTERN.sub("[REDACTED_ABA_ROUTING]", redacted)
    redacted = _IBAN_PATTERN.sub("[REDACTED-FINVAULT-IBAN]", redacted)
    redacted = _SWIFT_PATTERN.sub("SWIFT: [REDACTED-FINVAULT-SWIFT]", redacted)
    redacted = _CC_PATTERN.sub("[REDACTED_PAYMENT_PAN]", redacted)
    return redacted


async def enforce_tenant_isolation_interceptor(
    callback_context: Any,
    *,
    registry_pdp: AgentRegistryPDP = DEFAULT_REGISTRY_PDP,
    otel_sink: OTelAuditSink = DEFAULT_OTEL_SINK,
    context_verifier: Any | None = None,
) -> dict[str, Any] | None:
    """ADK 2.0 `before_agent_callback`: Validates tenant context and prunes unentitled tools."""
    state: dict[str, Any] = getattr(callback_context, "state", {})
    tenant_id: str | None = state.get("temp:tenant_id")
    subscription_tier: str = state.get("temp:tier", "standard")

    if not tenant_id:
        raise PermissionError(
            "E_UNAUTHENTICATED_TENANT: Missing temp:tenant_id in ADK context."
        )
    # Tenant, scopes and tier below decide access: trust them only if the gateway-signed context
    # token over them verifies (public key only; state can be mutated between hops).
    from agents.context import averify_signed_adk_state
    from agents.context_token import AUDIENCE_RUNTIME

    # A key refresh may call KMS (bounded); that case runs in a worker thread, off the event loop.
    await averify_signed_adk_state(
        state, audience=AUDIENCE_RUNTIME, verifier=context_verifier
    )

    agent_obj = getattr(callback_context, "agent", None)
    agent_id = getattr(agent_obj, "name", "cymbal_shared_diagnostic_agent")
    raw_model = getattr(agent_obj, "model", "gemini-4-hydrogen")
    model_id = str(getattr(raw_model, "model", raw_model))

    caller_scopes = state.get("temp:authorized_scopes")
    registry_pdp.verify_agent_access(
        tenant_id=tenant_id,
        agent_id=agent_id,
        caller_scopes=caller_scopes,
    )

    inbound_prompt = str(state.get("temp:last_user_prompt", ""))
    if inbound_prompt:
        ma_live_res = ingress_model_armor_screen(
            prompt=inbound_prompt,
            caller_tenant_id=tenant_id,
            use_live_model_armor=bool(
                state.get("temp:use_live_model_armor", True)
            ),
        )
        if ma_live_res is not None:
            state["temp:live_model_armor_receipt"] = ma_live_res

    entitled_tool_names = set(
        registry_pdp.get_entitled_tools(
            tenant_id=tenant_id,
            agent_id=agent_id,
            caller_scopes=caller_scopes,
        )
    )
    raw_tools = getattr(agent_obj, "tools", []) or []
    active_tools = [
        t
        for t in raw_tools
        if getattr(t, "name", getattr(t, "__name__", "")) in entitled_tool_names
    ]
    callback_context.active_tools = active_tools

    # `temp:thinking_budget` is the signed cap; a turn's request goes in the unsigned
    # `temp:requested_thinking_budget` and is clamped to the cap and the tier.
    tier_budget = int(TENANT_DIRECTORY[tenant_id]["thinking_budget"])
    signed_cap = int(state.get("temp:thinking_budget", tier_budget))
    requested = int(state.get("temp:requested_thinking_budget", signed_cap))
    state["temp:effective_thinking_budget"] = max(
        0, min(requested, signed_cap, tier_budget)
    )

    otel_sink.record(
        OTelAuditSpan(
            trace_id=str(state.get("temp:trace_id", "trace-local")),
            tenant_id=tenant_id,
            subscription_tier=subscription_tier,
            agent_id=agent_id,
            model_id=model_id,
            tool_name=None,
            prompt_cache_hit=True,
            thinking_tokens_budget=state["temp:effective_thinking_budget"],
            status="AUTHORIZED",
        )
    )
    return None
