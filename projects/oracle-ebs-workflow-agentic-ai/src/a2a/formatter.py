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

"""Markdown and executive response formatting for Oracle EBS Workflow A2A."""

import html
import logging
import re
from typing import Any

from google.genai import types
from src.a2a.ai_client import (
    GENAI_CALL_EXCEPTIONS,
    generate_content_with_models,
    get_ai_client,
)
from src.a2a.schemas import (
    NotificationItem,
    extract_amount_from_attributes,
    extract_amount_from_text,
    parse_amount_value,
)
from src.workflow.policy import PolicyEngine

logger = logging.getLogger("oracle_ebs_workflow.a2a.formatter")

HTML_TAG_RE = re.compile(r"<[^>]+>")


def clean_html_markup(raw: str) -> str:
    """Sanitize raw HTML tags, unescape entities, and normalize whitespace."""
    if not raw or not isinstance(raw, str):
        return ""
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    lines = [line.strip() for line in text.split("\n")]
    cleaned = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _format_risk_badge(risk: str) -> str:
    """Render emoji badge for a policy risk level."""
    if risk == "CRITICAL":
        return "🚨 CRITICAL"
    if risk in ("MEDIUM", "HIGH"):
        return "⚠️ " + risk
    return "🟢 LOW"


def _resolve_item_policy(
    item: dict[str, Any],
    raw_amt: float | None,
    attrs: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Resolve risk_level and recommended_action via PolicyEngine when unset."""
    risk = item.get("risk_level")
    rec = item.get("recommended_action") or item.get("recommendation")
    if risk and rec:
        return str(risk), str(rec)
    nid_val = item.get("notification_id") or item.get("nid") or 1
    eval_res = PolicyEngine.evaluate(
        NotificationItem(
            notification_id=int(nid_val) if str(nid_val).isdigit() else 1,
            message_type=str(item.get("message_type") or "N/A"),
            recipient_role=str(
                item.get("recipient_role") or item.get("requester") or "N/A"
            ),
            subject=str(item.get("subject") or ""),
            amount=raw_amt,
        ),
        attrs
        if isinstance(attrs, dict)
        else (
            item.get("attributes")
            if isinstance(item.get("attributes"), dict)
            else None
        ),
    )
    return (
        str(risk or eval_res.risk_level),
        str(rec or eval_res.recommendation),
    )


def render_full_items_table(items: list[dict[str, Any]]) -> str:
    """Render the full Markdown table displaying every item row-by-row."""
    rows: list[str] = [
        f"Showing {len(items)} notification(s):\n",
        (
            "| Notification ID | Type | Subject | Requester | Amount | "
            "Risk Status | Recommended Action |"
        ),
        "|:---|:---|:---|:---|:---|:---|:---|",
    ]
    for item in items:
        nid = item.get("notification_id") or item.get("nid", "N/A")
        mtype = item.get("message_type", "N/A")
        raw_subj = item.get("subject", "N/A") or "No Subject"
        subj = raw_subj.replace("|", "/")
        raw_req = item.get("requester") or item.get("recipient_role") or "-"
        req = raw_req.replace("|", "/")
        raw_amt = parse_amount_value(item.get("amount"))
        if raw_amt is None:
            raw_amt = extract_amount_from_attributes(
                item.get("attributes"), str(item.get("subject") or "")
            )
        amt = f"${raw_amt:,.2f}" if raw_amt is not None else "-"
        risk, rec = _resolve_item_policy(item, raw_amt)
        risk_badge = _format_risk_badge(risk)
        rows.append(
            f"| {nid} | {mtype} | {subj} | {req} | {amt} | "
            f"{risk_badge} | {rec} |"
        )
    return "\n".join(rows)


def render_evaluations_table(evals: list[dict[str, Any]]) -> str:
    """Render policy evaluations full table."""
    risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    sorted_evals = sorted(
        evals,
        key=lambda e: (
            0 if e.get("compliance_status") != "COMPLIANT" else 1,
            risk_order.get(str(e.get("risk_level", "LOW")), 3),
        ),
    )
    rows = [
        (
            "### 🛡️ Corporate Policy & Compliance Evaluation "
            f"({len(sorted_evals)} item(s))\n"
        ),
        (
            "| Notification ID | Type | Amount | Compliance Status | "
            "Risk Level | Recommendation | Details / Violations |"
        ),
        "|:---|:---|:---|:---|:---|:---|:---|",
    ]
    for ev in sorted_evals:
        nid = ev.get("notification_id", "N/A")
        mtype = ev.get("message_type", "N/A")
        ev_amt = parse_amount_value(ev.get("amount"))
        if ev_amt is None:
            ev_amt = extract_amount_from_text(str(ev.get("explanation") or ""))
        amt_col = f"${ev_amt:,.2f}" if ev_amt is not None else "-"
        c_status = ev.get("compliance_status", "COMPLIANT")
        risk = ev.get("risk_level", "LOW")
        if risk == "CRITICAL":
            risk_badge = "🚨 CRITICAL"
        elif risk in ("MEDIUM", "HIGH"):
            risk_badge = "⚠️ " + risk
        else:
            risk_badge = "🟢 LOW"
        rec = ev.get("recommended_action") or ev.get(
            "recommendation", "APPROVE"
        )
        viols = ev.get("violations", [])
        expl = ev.get("explanation", "")
        if viols and isinstance(viols, list):
            viol_strs: list[str] = []
            for v in viols:
                if isinstance(v, dict):
                    v_code = v.get("code", "FLAG")
                    v_msg = v.get("message", "")
                    viol_strs.append(f"{v_code}: {v_msg}")
                else:
                    viol_strs.append(str(v))
            detail_str = "; ".join(viol_strs)
        else:
            detail_str = expl or "Passed all policy checks"
        rows.append(
            f"| {nid} | {mtype} | {amt_col} | {c_status} | {risk_badge} | "
            f"{rec} | {detail_str} |"
        )
    return "\n".join(rows)


def render_results_table(raw: dict[str, Any]) -> str:
    """Render execution results table for both successes and failures."""
    action = raw.get("action", "ACTION")
    results = raw.get("results")
    if not results:
        results = []
        for p in raw.get("processed_items", []):
            results.append(
                {
                    "notification_id": p.get("notification_id", "N/A"),
                    "action": action,
                    "status": p.get("status", "SUCCESS"),
                    "execution_path": p.get("execution_path", "REST"),
                    "message": p.get("message", "Completed successfully"),
                }
            )
        for f in raw.get("failed_items", []):
            err = (
                f.get("error")
                or f.get("message")
                or "Notice: item cannot be transitioned"
            )
            results.append(
                {
                    "notification_id": f.get("notification_id", "N/A"),
                    "action": action,
                    "status": f.get("status", "FAILED"),
                    "execution_path": f.get("execution_path", "REST"),
                    "message": err,
                }
            )

    if not results:
        return (
            f"### ℹ️ Execution Notice for {action}\n\n"
            "No items were processed."
        )

    rows = [
        f"### 📋 Execution Results for {action}\n",
        "| Notification ID | Action | Status | Execution Path | Details |",
        "|:---|:---|:---|:---|:---|",
    ]
    for r in results:
        nid = r.get("notification_id", "N/A")
        act_name = r.get("action", action)
        st = r.get("status", "SUCCESS")
        badge = "✅ SUCCESS" if st == "SUCCESS" else f"❌ {st}"
        path = r.get("execution_path", "REST")
        msg = r.get("message", "Completed")
        rows.append(f"| {nid} | {act_name} | {badge} | {path} | {msg} |")
    return "\n".join(rows)


def render_single_notification_detail(
    hdr: dict[str, Any], raw_notifications: dict[str, Any]
) -> str:
    """Format single notification inspection detail cleanly in Markdown."""
    nid = hdr.get("notification_id") or hdr.get("nid")
    mtype = hdr.get("message_type")
    subj = hdr.get("subject", "N/A")
    recip = hdr.get("recipient_role", "N/A")
    st = hdr.get("status", "OPEN")
    b_date = hdr.get("begin_date", "N/A")
    d_date = hdr.get("due_date", "N/A")
    attrs = raw_notifications.get("attributes", {})
    if not isinstance(attrs, dict):
        attrs = {}
    amt = parse_amount_value(hdr.get("amount"))
    if amt is None:
        amt = extract_amount_from_attributes(attrs, str(subj))
    amt_str = f"${amt:,.2f}" if amt is not None else "-"
    risk, rec = _resolve_item_policy(hdr, amt, attrs)
    risk_badge = _format_risk_badge(risk)

    body_content = None
    clean_attrs: list[tuple[str, str]] = []
    for k, v in attrs.items():
        if not v or not isinstance(v, str):
            continue
        k_upper = k.upper().strip()
        v_upper = v.upper().strip()
        if (
            k_upper.startswith("#")
            or "DOCUMENT" in k_upper
            or "OA.JSP" in v_upper
            or v_upper.startswith("JSP:")
        ):
            continue
        if k_upper in ("HTML_BODY", "TEXT_BODY", "BODY"):
            c_text = clean_html_markup(v)
            if not body_content or len(c_text) > len(body_content):
                body_content = c_text
            continue
        clean_attrs.append((k, clean_html_markup(str(v))))

    attr_lines = [f"- **{k}**: {v}" for k, v in clean_attrs[:8]]
    attr_text = (
        "\n".join(attr_lines) if attr_lines else "_No additional attributes._"
    )
    body_section = (
        f"\n\n#### 📝 Message Content:\n{body_content}" if body_content else ""
    )
    return (
        f"### 📋 Notification #{nid} Details\n\n"
        f"- **Type**: `{mtype}`\n"
        f"- **Status**: `{st}`\n"
        f"- **Recipient**: `{recip}`\n"
        f"- **Subject**: {subj}\n"
        f"- **Amount**: {amt_str}\n"
        f"- **Risk Status**: {risk_badge}\n"
        f"- **Recommended Action**: `{rec}`\n"
        f"- **Begin Date**: {b_date}\n"
        f"- **Due Date**: {d_date}\n\n"
        f"#### Attributes:\n{attr_text}"
        f"{body_section}"
    )


def _render_status_or_confirmation(
    raw_notifications: dict[str, Any],
) -> str | None:
    """Render direct replies, error notices, or human confirmation gates."""
    has_data_keys = any(
        k in raw_notifications
        for k in (
            "items",
            "notifications",
            "evaluations",
            "results",
            "processed_items",
            "failed_items",
            "header",
            "details",
        )
    )
    if (
        raw_notifications.get("text") or raw_notifications.get("reply")
    ) and not has_data_keys:
        return str(
            raw_notifications.get("text") or raw_notifications.get("reply")
        )

    if raw_notifications.get("status") == "ERROR" or (
        "detail" in raw_notifications and not raw_notifications.get("items")
    ):
        detail = (
            raw_notifications.get("detail")
            or raw_notifications.get("message")
            or "An unexpected error occurred while processing the request."
        )
        return (
            f"⚠️ **Oracle EBS Workflow Notice**\n\n{detail}\n\n"
            "Please verify the notification ID or check your worklist."
        )

    if raw_notifications.get("status") == "CONFIRMATION_REQUIRED":
        proposal = raw_notifications.get("proposal", raw_notifications)
        prompt_msg = proposal.get(
            "confirmation_prompt", "Please review and confirm this action."
        )
        risk_summary = proposal.get("risk_summary", "Review requested.")
        nids = proposal.get("notification_ids", [])
        impact = proposal.get("total_financial_impact", 0.0)
        action_name = proposal.get("action", "APPROVE")
        return (
            f"⚠️ **Human Confirmation Gate Required**\n\n"
            f"**Action**: {action_name}\n"
            f"**Notification IDs**: `{nids}`\n"
            f"**Total Financial Impact**: ${impact:,.2f}\n"
            f"**Risk Summary**: {risk_summary}\n\n"
            f"*{prompt_msg}*\n\n"
            "👉 *To execute, reply with `confirmed=True` or `Confirm`.*"
        )

    return None


def _render_structured_details(
    raw_notifications: dict[str, Any],
) -> str | None:
    """Render action results, policy evaluations, or single item details."""
    has_results = (
        bool(raw_notifications.get("processed_items"))
        or bool(raw_notifications.get("failed_items"))
        or bool(raw_notifications.get("results"))
    )
    if has_results:
        return render_results_table(raw_notifications)

    details_list = raw_notifications.get("details")
    detail_sections: list[str] = []
    if isinstance(details_list, list) and details_list:
        for det in details_list:
            if isinstance(det, dict):
                det_hdr = (
                    det.get("header")
                    if isinstance(det.get("header"), dict)
                    else det
                )
                if isinstance(det_hdr, dict):
                    detail_sections.append(
                        render_single_notification_detail(det_hdr, det)
                    )

    if raw_notifications.get("evaluations"):
        eval_md = render_evaluations_table(raw_notifications["evaluations"])
        if detail_sections:
            return eval_md + "\n\n---\n\n" + "\n\n---\n\n".join(detail_sections)
        return eval_md

    if detail_sections:
        return "\n\n---\n\n".join(detail_sections)

    hdr = (
        raw_notifications.get("header")
        if isinstance(raw_notifications.get("header"), dict)
        else raw_notifications
    )
    is_single_hdr = (
        isinstance(hdr, dict)
        and ("notification_id" in hdr or "nid" in hdr)
        and "message_type" in hdr
        and "items" not in raw_notifications
    )
    if is_single_hdr and isinstance(hdr, dict):
        return render_single_notification_detail(hdr, raw_notifications)

    return None


def _extract_worklist_items(
    raw_notifications: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract notification items from worklist payload keys."""
    items = raw_notifications.get("items", [])
    if not items and "notifications" in raw_notifications:
        items = raw_notifications["notifications"]
    if not items and "item" in raw_notifications:
        items = [raw_notifications["item"]]
    if not items and "processed_items" in raw_notifications:
        items = raw_notifications["processed_items"]
    return items if isinstance(items, list) else []


def _render_empty_worklist_notice(raw_notifications: dict[str, Any]) -> str:
    """Render markdown message when no pending notifications are present."""
    if raw_notifications.get("markdown_table") and (
        raw_notifications["markdown_table"]
        != "_No pending workflow notifications found._"
    ):
        return str(raw_notifications["markdown_table"])

    recipient = raw_notifications.get("recipient")
    if recipient:
        return (
            f"🟢 **No pending notifications found for recipient "
            f"`{recipient}`.** All workflow items have been processed."
        )
    return (
        "🟢 **No pending notifications found.** "
        "All workflow items have been processed."
    )


def _build_triage_and_worklist_sections(
    raw_notifications: dict[str, Any],
    items: list[dict[str, Any]],
) -> tuple[str, str, str, str]:
    """Build triage summary, items table, risk alerts, and next steps."""
    triage_header = ""
    if (
        "high_risk_notifications" in raw_notifications
        or "proactive_next_steps" in raw_notifications
    ):
        total_cnt = raw_notifications.get("total_pending", len(items))
        hr_list = raw_notifications.get("high_risk_notifications", [])
        hr_cnt = len(hr_list) if isinstance(hr_list, list) else 0
        low_cnt = max(0, int(total_cnt) - hr_cnt)
        triage_header = (
            "### 📊 Workflow Triage Summary\n"
            f"- **Total Analyzed**: {total_cnt}\n"
            f"- **Auto-Approvable (Low Risk)**: {low_cnt}\n"
            f"- **Requires Human Review**: {hr_cnt}\n\n"
        )
    table_text = render_full_items_table(items)
    risk_alerts = raw_notifications.get("risk_alerts", [])
    alerts_text = ""
    if isinstance(risk_alerts, list) and risk_alerts:
        alerts_text = "\n\n**Risk Alerts:**\n" + "\n".join(
            f"- {a}" for a in risk_alerts
        )
    next_steps = raw_notifications.get("proactive_next_steps", [])
    next_steps_text = ""
    if next_steps:
        next_steps_text = (
            "\n\n### 💡 Recommended Next Steps (Proactive Actions)\n"
            + "\n".join(f"- {s}" for s in next_steps)
        )
    return triage_header, table_text, alerts_text, next_steps_text


def _synthesize_markdown_with_llm(
    user_prompt: str,
    table_text: str,
    alerts_text: str,
    next_steps_text: str,
) -> str | None:
    """Synthesize executive Markdown table using Gemini Flash when available."""
    ai_client = get_ai_client()
    if not ai_client:
        return None

    prompt = (
        f"You are the Oracle EBS Workflow Executive Assistant.\n"
        f"User Prompt: '{user_prompt}'\n"
        f"Format this workflow data into clean, executive Markdown:\n"
        f"{table_text}{alerts_text}{next_steps_text}\n\n"
        "Guidelines:\n"
        "1. Keep all notification rows intact in the Markdown table.\n"
        "2. Include risk badges (🟢 LOW, ⚠️ MEDIUM/HIGH, 🚨 CRITICAL).\n"
        "3. Keep Proactive Next Steps intact if present.\n"
        "4. Include instructions for user confirmation if approvals are needed."
    )
    try:
        config = types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=2048,
        )
        resp = generate_content_with_models(
            ai_client, prompt, config, fast_tier=True
        )
        if resp and getattr(resp, "text", None):
            text_out = str(resp.text)
            if "|" in text_out and ("-|-" in text_out or ":---" in text_out):
                return text_out
    except (*GENAI_CALL_EXCEPTIONS, RuntimeError) as exc:
        logger.warning("Gemini synthesis fallback triggered: %s", exc)
    return None


def synthesize_response(
    raw_notifications: dict[str, Any],
    user_prompt: str,
) -> str:
    """Use Gemini Flash to formulate an executive Markdown response."""
    status_md = _render_status_or_confirmation(raw_notifications)
    if status_md is not None:
        return status_md

    structured_md = _render_structured_details(raw_notifications)
    if structured_md is not None:
        return structured_md

    items = _extract_worklist_items(raw_notifications)
    if not items:
        return _render_empty_worklist_notice(raw_notifications)

    triage_header, table_text, alerts_text, next_steps_text = (
        _build_triage_and_worklist_sections(raw_notifications, items)
    )
    footer = "\n\n🟢 *Please reply with `confirmed=True` to execute approvals.*"
    default_md = (
        f"{triage_header}{table_text}{alerts_text}{next_steps_text}{footer}"
    )

    if len(items) > 10:
        return default_md

    llm_md = _synthesize_markdown_with_llm(
        user_prompt, table_text, alerts_text, next_steps_text
    )
    return llm_md if llm_md is not None else default_md
