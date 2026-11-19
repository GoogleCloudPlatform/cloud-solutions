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

# pylint: disable=inconsistent-quotes,line-too-long

"""Render the sequential Gemini End-to-End Request Flow SVG and 2x PNG diagram.

Builds a pure vector SVG (`docs/assets/ws2_pooled_5hop_architecture.svg`) and a
high-DPI PNG (`docs/assets/ws2_pooled_5hop_architecture.png`) illustrating the
strict left-to-right request sequence (Steps 1 to 6), Gemini Enterprise Agent
Gemini governance control plane (Global + Local Agent Registry),
Three-Layer Authorization (`Tenant ∩ User ∩ Agent`), stateless concurrent
agent runtimes (`ADK`, `LangGraph`, `BYO Docker`) plus ephemeral `gVisor`
sandboxes, egress Model Armor runtime decision monitoring at `Agent-to-Anywhere`
egress, and governed model routing.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path
from xml.sax import saxutils

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "docs" / "assets"
OUTPUT_SVG_PATH = ASSETS_DIR / "ws2_pooled_5hop_architecture.svg"
OUTPUT_PNG_PATH = ASSETS_DIR / "ws2_pooled_5hop_architecture.png"


def escape_xml(raw_text: str) -> str:
    """Escape plain text for safe inclusion in SVG elements.

    Args:
        raw_text: Unescaped label string.

    Returns:
        XML-escaped text string.
    """
    return saxutils.escape(raw_text)


def render_control_plane_card(
    coord_x: float,
    coord_y: float,
    width: float,
    height: float,
    title: str,
    lines: Sequence[str],
) -> str:
    """Render one Gemini Control Plane governance card.

    Args:
        coord_x: Left X coordinate.
        coord_y: Top Y coordinate.
        width: Card width in SVG units.
        height: Card height in SVG units.
        title: Bold blue card heading.
        lines: Concise descriptive lines.

    Returns:
        SVG markup string for the control plane card.
    """
    elements = [
        (
            f'  <rect x="{coord_x}" y="{coord_y}" width="{width}" height="{height}" '
            'rx="8" fill="#F8FAFD" stroke="#D2E3FC" stroke-width="1.2"/>'
        ),
        (
            f'  <text x="{coord_x + 12}" y="{coord_y + 21}" font-size="12.0" '
            f'font-weight="700" fill="#174EA6">{escape_xml(title)}</text>'
        ),
    ]
    line_y = coord_y + 39
    for text_line in lines:
        elements.append(
            f'  <text x="{coord_x + 12}" y="{line_y}" font-size="10.4" '
            f'fill="#3C4043">{escape_xml(text_line)}</text>'
        )
        line_y += 15
    return "\n".join(elements)


def render_pill_box(
    coord_x: float,
    coord_y: float,
    width: float,
    height: float,
    fill_color: str,
    border_color: str,
    heading: str,
    body_lines: Sequence[str],
) -> str:
    """Render a sub-box inside one of the numbered step cards.

    Args:
        coord_x: Left X coordinate.
        coord_y: Top Y coordinate.
        width: Box width.
        height: Box height.
        fill_color: Background hex color.
        border_color: Stroke hex color.
        heading: Bold sub-box title.
        body_lines: Short lines rendered inside the sub-box.

    Returns:
        SVG markup string for the sub-box.
    """
    output_lines = [
        (
            f'  <rect x="{coord_x}" y="{coord_y}" width="{width}" height="{height}" '
            f'rx="7" fill="{fill_color}" stroke="{border_color}" stroke-width="1"/>'
        ),
        (
            f'  <text x="{coord_x + 9}" y="{coord_y + 17}" font-size="10.5" '
            f'font-weight="700" fill="#202124">{escape_xml(heading)}</text>'
        ),
    ]
    text_y = coord_y + 31.5
    for row in body_lines:
        output_lines.append(
            f'  <text x="{coord_x + 9}" y="{text_y}" font-size="9.7" '
            f'fill="#3C4043">{escape_xml(row)}</text>'
        )
        text_y += 13.2
    return "\n".join(output_lines)


def render_step_card(
    coord_x: float,
    coord_y: float,
    width: float,
    height: float,
    step_num: str,
    title: str,
    subtitle: str,
    header_style: str,
    pills: Sequence[tuple[str, str, str, Sequence[str]]],
    deny_text: str,
) -> str:
    """Render a full vertical sequential step card (Steps 1 through 5).

    Args:
        coord_x: Left X coordinate.
        coord_y: Top Y coordinate.
        width: Card width.
        height: Card height.
        step_num: Step badge string.
        title: Primary card header title.
        subtitle: Secondary card header label.
        header_style: One of 'default', 'gemini', or 'broker'.
        pills: Sequence of (fill, stroke, heading, body_lines) tuples.
        deny_text: Red fail-closed footer string (empty if omitted).

    Returns:
        SVG markup string for the step card.
    """
    header_fill = "#FFFFFF"
    header_line = "#E8EAED"
    badge_bg = "#1967D2"
    badge_fg = "#FFFFFF"
    title_fg = "#202124"
    subtitle_fg = "#1967D2"

    if header_style == "gemini":
        header_fill = "#3B78E7"
        header_line = "#3B78E7"
        badge_bg = "#FFFFFF"
        badge_fg = "#174EA6"
        title_fg = "#FFFFFF"
        subtitle_fg = "#E8F0FE"
    elif header_style == "broker":
        header_fill = "#E6F4EA"
        header_line = "#A8DAB5"
        badge_bg = "#137333"
        badge_fg = "#FFFFFF"
        title_fg = "#202124"
        subtitle_fg = "#137333"

    header_height = 48
    parts = [
        (
            f'  <rect x="{coord_x}" y="{coord_y}" width="{width}" height="{height}" '
            'rx="12" fill="#FFFFFF" stroke="#DADCE0" stroke-width="1.5" '
            'filter="url(#shadow-sm)"/>'
        ),
        (
            f'  <path d="M {coord_x} {coord_y + 12} Q {coord_x} {coord_y} '
            f"{coord_x + 12} {coord_y} L {coord_x + width - 12} {coord_y} "
            f"Q {coord_x + width} {coord_y} {coord_x + width} {coord_y + 12} "
            f"L {coord_x + width} {coord_y + header_height} "
            f'L {coord_x} {coord_y + header_height} Z" fill="{header_fill}"/>'
        ),
        (
            f'  <line x1="{coord_x}" y1="{coord_y + header_height}" '
            f'x2="{coord_x + width}" y2="{coord_y + header_height}" '
            f'stroke="{header_line}" stroke-width="1"/>'
        ),
        (
            f'  <circle cx="{coord_x + 23}" cy="{coord_y + 24}" r="13" fill="{badge_bg}"/>'
        ),
        (
            f'  <text x="{coord_x + 23}" y="{coord_y + 28.5}" font-size="12.5" '
            f'font-weight="700" fill="{badge_fg}" text-anchor="middle">'
            f"{escape_xml(step_num)}</text>"
        ),
        (
            f'  <text x="{coord_x + 44}" y="{coord_y + 21}" font-size="12.2" '
            f'font-weight="700" fill="{title_fg}">{escape_xml(title)}</text>'
        ),
        (
            f'  <text x="{coord_x + 44}" y="{coord_y + 36}" font-size="9.7" '
            f'font-weight="600" fill="{subtitle_fg}">{escape_xml(subtitle)}</text>'
        ),
    ]

    cursor_y = coord_y + header_height + 9
    pill_width = width - 20
    for fill_color, stroke_color, pill_heading, pill_lines in pills:
        pill_height = 23 + len(pill_lines) * 13.2 + 4
        parts.append(
            render_pill_box(
                coord_x + 10,
                cursor_y,
                pill_width,
                pill_height,
                fill_color,
                stroke_color,
                pill_heading,
                pill_lines,
            )
        )
        cursor_y += pill_height + 6.5

    if deny_text:
        line_y = coord_y + height - 26
        parts.append(
            f'  <line x1="{coord_x + 10}" y1="{line_y}" '
            f'x2="{coord_x + width - 10}" y2="{line_y}" stroke="#DADCE0" '
            'stroke-width="1" stroke-dasharray="4 3"/>'
        )
        parts.append(
            f'  <text x="{coord_x + 10}" y="{coord_y + height - 10}" '
            f'font-size="9.5" font-weight="700" fill="#C5221F">'
            f"\u2715 {escape_xml(deny_text)}</text>"
        )

    return "\n".join(parts)


def render_step_arrow(
    start_x: float,
    end_x: float,
    center_y: float,
    label: str,
) -> str:
    """Render a short labeled horizontal arrow between sequential step cards.

    Args:
        start_x: Arrow start X coordinate.
        end_x: Arrow tip X coordinate.
        center_y: Vertical center Y coordinate.
        label: Compact token/state label above the arrow.

    Returns:
        SVG markup string for the connector arrow.
    """
    mid_x = (start_x + end_x) / 2.0
    return "\n".join(
        [
            (
                f'  <text x="{mid_x}" y="{center_y - 8}" font-size="9" '
                'font-weight="700" fill="#5F6368" text-anchor="middle">'
                f"{escape_xml(label)}</text>"
            ),
            (
                f'  <line x1="{start_x + 3}" y1="{center_y}" x2="{end_x - 8}" '
                f'y2="{center_y}" stroke="#1967D2" stroke-width="2.2"/>'
            ),
            (
                f'  <polygon points="{end_x - 2},{center_y} '
                f'{end_x - 9},{center_y - 4.5} {end_x - 9},{center_y + 4.5}" '
                'fill="#1967D2"/>'
            ),
        ]
    )


def render_target_card(
    coord_x: float,
    coord_y: float,
    width: float,
    height: float,
    fill_color: str,
    border_color: str,
    badge_color: str,
    step_tag: str,
    title: str,
    lines: Sequence[str],
) -> str:
    """Render one parallel target box in Step 6 (6A, 6B, or 6C).

    Args:
        coord_x: Left X coordinate.
        coord_y: Top Y coordinate.
        width: Box width.
        height: Box height.
        fill_color: Fill hex color.
        border_color: Border hex color.
        badge_color: Step pill fill color.
        step_tag: Tag text ('6A', '6B', '6C').
        title: Target heading.
        lines: Descriptive lines inside the target card.

    Returns:
        SVG markup string for the target card.
    """
    output_lines = [
        (
            f'  <rect x="{coord_x}" y="{coord_y}" width="{width}" height="{height}" '
            f'rx="10" fill="{fill_color}" stroke="{border_color}" stroke-width="1.5"/>'
        ),
        (
            f'  <rect x="{coord_x + 12}" y="{coord_y + 14}" width="28" height="19" '
            f'rx="9" fill="{badge_color}"/>'
        ),
        (
            f'  <text x="{coord_x + 26}" y="{coord_y + 27}" font-size="10.2" '
            'font-weight="700" fill="#FFFFFF" text-anchor="middle">'
            f"{escape_xml(step_tag)}</text>"
        ),
        (
            f'  <text x="{coord_x + 47}" y="{coord_y + 28}" font-size="11.6" '
            f'font-weight="700" fill="#202124">{escape_xml(title)}</text>'
        ),
    ]
    text_y = coord_y + 49
    for row in lines:
        output_lines.append(
            f'  <text x="{coord_x + 12}" y="{text_y}" font-size="10" '
            f'fill="#3C4043">{escape_xml(row)}</text>'
        )
        text_y += 14.5
    return "\n".join(output_lines)


def render_footer_card(
    coord_x: float,
    coord_y: float,
    width: float,
    height: float,
    accent_color: str,
    heading: str,
    lines: Sequence[str],
) -> str:
    """Render one bottom summary card clarifying gateway, runtime, or model logic.

    Args:
        coord_x: Left X coordinate.
        coord_y: Top Y coordinate.
        width: Card width.
        height: Card height.
        accent_color: Left accent bar hex color.
        heading: Card title.
        lines: Two concise explanation lines.

    Returns:
        SVG markup string for the footer card.
    """
    output_lines = [
        (
            f'  <rect x="{coord_x}" y="{coord_y}" width="{width}" height="{height}" '
            'rx="10" fill="#FFFFFF" stroke="#DADCE0" stroke-width="1.5"/>'
        ),
        (
            f'  <rect x="{coord_x}" y="{coord_y + 6}" width="4.5" '
            f'height="{height - 12}" rx="2" fill="{accent_color}"/>'
        ),
        (
            f'  <text x="{coord_x + 16}" y="{coord_y + 22}" font-size="11.4" '
            f'font-weight="700" fill="#202124">{escape_xml(heading)}</text>'
        ),
    ]
    text_y = coord_y + 39
    for row in lines:
        output_lines.append(
            f'  <text x="{coord_x + 16}" y="{text_y}" font-size="10.0" '
            f'fill="#3C4043">{escape_xml(row)}</text>'
        )
        text_y += 14.5
    return "\n".join(output_lines)


def build_svg() -> str:
    """Build the complete sequential Gemini End-to-End Request Flow SVG string.

    Returns:
        Complete XML/SVG document text.
    """
    parts: list[str] = [
        (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1800 880" '
            'width="1800" height="880" '
            "font-family=\"'Google Sans', Roboto, Arial, sans-serif\">"
        ),
        """  <defs>
    <filter id="shadow-sm" x="-2%" y="-2%" width="104%" height="106%">
      <feDropShadow dx="0" dy="2" stdDeviation="2.5" flood-color="#202124" flood-opacity="0.05"/>
    </filter>
    <marker id="fan-arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#1967D2"/>
    </marker>
  </defs>""",
        '  <rect width="1800" height="880" fill="#F8F9FA"/>',
        # Top Header
        (
            '  <rect x="24" y="16" width="1752" height="64" rx="12" fill="#FFFFFF" '
            'stroke="#DADCE0" stroke-width="1.5" filter="url(#shadow-sm)"/>'
        ),
        (
            '  <text x="44" y="43" font-size="19.2" font-weight="700" fill="#202124">'
            "Cymbal CloudOps ISV: End-to-End Request Sequence "
            "(Pattern A: Governed Pool)</text>"
        ),
        (
            '  <text x="44" y="63" font-size="12.0" fill="#5F6368">'
            "AI SRE SaaS Trace (Steps 1 \u2192 6)  |  "
            "Three-Layer Authz (Tenant \u2229 User \u2229 Agent)  |  "
            "Egress Model Armor (Runtime Decision Monitoring) &amp; Governed Model Routing</text>"
        ),
        (
            '  <rect x="1516" y="31" width="240" height="32" rx="16" '
            'fill="#E8F0FE" stroke="#AECBFA" stroke-width="1"/>'
        ),
        (
            '  <text x="1636" y="51" font-size="11.4" font-weight="700" '
            'fill="#174EA6" text-anchor="middle">ADK \u2022 LangGraph \u2022 BYO Docker</text>'
        ),
        # Gemini Control Plane Band
        (
            '  <rect x="24" y="94" width="1752" height="122" rx="12" fill="#FFFFFF" '
            'stroke="#AECBFA" stroke-width="1.5" filter="url(#shadow-sm)"/>'
        ),
        (
            '  <text x="40" y="116" font-size="12.0" font-weight="700" fill="#174EA6">'
            "GEMINI GOVERNANCE &amp; "
            "CONTROL PLANE (SAME OR SEPARATE GCP PROJECT)</text>"
        ),
        (
            '  <text x="1760" y="116" font-size="12" font-weight="700" fill="#174EA6" '
            'text-anchor="end">Policy Decision Point (PDP)</text>'
        ),
    ]

    control_plane_cards = [
        (
            "1. Auth Manager & IAM / PAB",
            [
                "Cloud KMS ctx+jwt (tid+uid+aid) signing, Cloud Run",
                "SPIFFE Agent Identity mTLS & out-of-process Broker.",
            ],
        ),
        (
            "2. Global + Local Agent Registry",
            [
                "Global Registry (shared agents/policies across regions) +",
                "Local Registry (project-specific agents & MCP servers).",
            ],
        ),
        (
            "3. AI Security (Step 5 Model Armor + DLP)",
            [
                "Model Armor at Agent-to-Anywhere egress",
                "(monitors runtime model & tool calls), Cloud DLP & quotas.",
            ],
        ),
        (
            "4. AI Observability & FinOps",
            [
                "Cloud Logging, Cloud Trace & OpenTelemetry spans tagged",
                "with tenant_hash, agent_id & model_id in BigQuery.",
            ],
        ),
    ]
    control_card_width = 419
    for card_index, (card_title, card_lines) in enumerate(control_plane_cards):
        parts.append(
            render_control_plane_card(
                40 + card_index * (control_card_width + 14),
                127,
                control_card_width,
                76,
                card_title,
                card_lines,
            )
        )

    # Sequential Flow Container
    parts.extend(
        [
            (
                '  <rect x="24" y="230" width="1752" height="542" rx="14" '
                'fill="#FFFFFF" stroke="#DADCE0" stroke-width="1.5" '
                'filter="url(#shadow-sm)"/>'
            ),
            (
                '  <text x="40" y="255" font-size="12.2" font-weight="700" '
                'fill="#202124">SEQUENTIAL REQUEST EXECUTION PATH (STEPS 1 \u2192 6):'
                "</text>"
            ),
            (
                '  <text x="392" y="255" font-size="11.4" fill="#5F6368">'
                "Each hop fails closed independently while propagating "
                "Tenant + User + Agent identity</text>"
            ),
        ]
    )

    card_y = 270
    card_height = 486
    mid_y = card_y + card_height / 2.0

    # Layout widths matching 1720px inner width:
    # 240 + 36 + 250 + 36 + 302 + 36 + 234 + 36 + 240 + 36 + 274 = 1720
    step1_x = 40
    step1_w = 240
    step2_x = step1_x + step1_w + 36
    step2_w = 250
    step3_x = step2_x + step2_w + 36
    step3_w = 302
    step4_x = step3_x + step3_w + 36
    step4_w = 234
    step5_x = step4_x + step4_w + 36
    step5_w = 240
    step6_x = step5_x + step5_w + 36
    step6_w = 274

    parts.append(
        render_step_card(
            step1_x,
            card_y,
            step1_w,
            card_height,
            "1",
            "IdP & ISV SaaS App",
            "OIDC + Cloud Run / GKE / GCE",
            "default",
            [
                (
                    "#E8F0FE",
                    "#AECBFA",
                    "Corporate OIDC Login (Hop 0)",
                    [
                        "Verifies FinVault Okta / RetailStream",
                        "Entra (1:1 iss \u2194 tid); extracts",
                        "tenant_id, user_id & mapped role.",
                    ],
                ),
                (
                    "#F8F9FA",
                    "#E8EAED",
                    "Existing ISV App Stack (Hop 1)",
                    [
                        "UI/BFF on Cloud Run, GKE, or GCE",
                        "exposes catalog agents (SRE, Audit);",
                        "Cloud Armor WAF + RPM/TPM caps.",
                    ],
                ),
                (
                    "#F8F9FA",
                    "#E8EAED",
                    "Sender-Constrained Token",
                    [
                        "Mints 600s DPoP at+jwt (cnf.jkt) +",
                        "KMS-signed ctx+jwt binding",
                        "tid + uid + routed agent_id.",
                    ],
                ),
            ],
            "Spoofed header/issuer \u2192 HTTP 401/422",
        )
    )
    parts.append(
        render_step_arrow(step1_x + step1_w, step2_x, mid_y, "ctx+jwt")
    )

    parts.append(
        render_step_card(
            step2_x,
            card_y,
            step2_w,
            card_height,
            "2",
            "agent gateway in Gemini",
            "Client-to-Agent (Ingress)",
            "gemini",
            [
                (
                    "#E6F4EA",
                    "#CEEAD6",
                    "Fast Sub-ms Admission Gate",
                    [
                        "Fronts backend Agent Runtimes with",
                        "zero duplicate content-scan latency",
                        "on upstream customer UX.",
                    ],
                ),
                (
                    "#F8F9FA",
                    "#E8EAED",
                    "Anti-Replay & Signature Gate",
                    [
                        "Verifies DPoP proof (htm, htu, ath),",
                        "single-use jti nonce & 3-key",
                        "(active, prev, next) KMS ring.",
                    ],
                ),
                (
                    "#E8F0FE",
                    "#AECBFA",
                    "Agent Routing & Body Hygiene",
                    [
                        "Routes to selected agent service",
                        "(e.g., SRE Agent) & rejects body",
                        "tenant_id / user_id overrides.",
                    ],
                ),
            ],
            "Replay \u2192 401 | Body override \u2192 422",
        )
    )
    parts.append(render_step_arrow(step2_x + step2_w, step3_x, mid_y, "routed"))

    parts.append(
        render_step_card(
            step3_x,
            card_y,
            step3_w,
            card_height,
            "3",
            "Agent Runtime & Sandboxes",
            "Per-Agent SPIFFE + Scale-Out",
            "default",
            [
                (
                    "#E8F0FE",
                    "#AECBFA",
                    "Stateless Turn Orchestrators",
                    [
                        "Per-agent Cloud Run services (SRE +",
                        "Compliance) with SPIFFE mTLS; hosts",
                        "ADK, LangGraph, or BYO Docker.",
                    ],
                ),
                (
                    "#E6F4EA",
                    "#CEEAD6",
                    "Stateless Scale + Agent Sandboxes",
                    [
                        "Concurrent stateless turns; dynamic",
                        "code runs in per-session Agent",
                        "Sandboxes (gVisor, zero credentials).",
                    ],
                ),
                (
                    "#F8F9FA",
                    "#E8EAED",
                    "Sessions, Memory & Skills",
                    [
                        "Firestore sessions (tid:uid), tenant",
                        "semantic + user memory (CMEK AAD),",
                        "32k cached skills + tenant GCS.",
                    ],
                ),
                (
                    "#F8F9FA",
                    "#E8EAED",
                    "Registry Tool Pruning",
                    [
                        "Loads only MCP tools allowed for",
                        "Tenant \u2229 User \u2229 Agent.",
                    ],
                ),
            ],
            "Unentitled agent/tool \u2192 HTTP 403",
        )
    )
    parts.append(render_step_arrow(step3_x + step3_w, step4_x, mid_y, "SPIFFE"))

    parts.append(
        render_step_card(
            step4_x,
            card_y,
            step4_w,
            card_height,
            "4",
            "Credential Broker",
            "Out-of-Process Auth Mgr",
            "broker",
            [
                (
                    "#E6F4EA",
                    "#CEEAD6",
                    "SPIFFE Agent Binding Gate",
                    [
                        "Separate Cloud Run service; verifies",
                        "caller SPIFFE ID matches signed",
                        "token.agent_id (403 on mismatch).",
                    ],
                ),
                (
                    "#F8F9FA",
                    "#E8EAED",
                    "300s Per-Tenant GCP SA",
                    [
                        "Mints ct-<sha256(tid)[:24]> (27-char",
                        "SA name) strictly for tenant KMS,",
                        "Secret Manager & GCS walls.",
                    ],
                ),
                (
                    "#E8F0FE",
                    "#AECBFA",
                    "Three-Layer Tuple Forwarded",
                    [
                        "Runtime proceeds with ctx+jwt",
                        "(tid+uid+aid) + SPIFFE ID +",
                        "brokered ct-<tid> GCP SA.",
                    ],
                ),
            ],
            "1 Key = 1 Tenant Max (Live 403)",
        )
    )
    parts.append(
        render_step_arrow(step4_x + step4_w, step5_x, mid_y, "3-layer")
    )

    parts.append(
        render_step_card(
            step5_x,
            card_y,
            step5_w,
            card_height,
            "5",
            "agent gateway in Gemini",
            "Agent-to-Anywhere (Egress)",
            "gemini",
            [
                (
                    "#E8F0FE",
                    "#AECBFA",
                    "Mandatory Model & Tool Egress",
                    [
                        "All LLM model routing, MCP calls &",
                        "3P API calls traverse this gateway",
                        "(no bespoke direct bypass).",
                    ],
                ),
                (
                    "#FEF7E0",
                    "#FDE293",
                    "Egress Model Armor (Runtime Check)",
                    [
                        "Monitors each runtime model, MCP",
                        "tool & API call once target model",
                        "and data context are known.",
                    ],
                ),
                (
                    "#F8F9FA",
                    "#E8EAED",
                    "Registry + Cloud DLP Masking",
                    [
                        "Verifies SPIFFE ID + Local/Global",
                        "Registry target & masks IBAN/SSN/",
                        "PAN before targets 6A / 6B / 6C.",
                    ],
                ),
            ],
            "Injection \u2192 400/422 | ACL \u2192 403",
        )
    )

    # Fan-out connector from Step 5 to 6A, 6B, 6C
    fan_x0 = step5_x + step5_w
    fan_xm = fan_x0 + 16
    fan_x1 = step6_x - 3
    target_height = 154
    target_gap = 12
    y_6a = card_y
    y_6b = card_y + target_height + target_gap
    y_6c = card_y + 2 * (target_height + target_gap)
    cy_a = y_6a + target_height / 2.0
    cy_b = y_6b + target_height / 2.0
    cy_c = y_6c + target_height / 2.0

    parts.extend(
        [
            (
                f'  <path d="M {fan_x0} {cy_b} L {fan_xm} {cy_b} '
                f'L {fan_xm} {cy_a} L {fan_x1} {cy_a}" fill="none" '
                'stroke="#1967D2" stroke-width="2.2" marker-end="url(#fan-arr)"/>'
            ),
            (
                f'  <path d="M {fan_x0} {cy_b} L {fan_x1} {cy_b}" fill="none" '
                'stroke="#1967D2" stroke-width="2.2" marker-end="url(#fan-arr)"/>'
            ),
            (
                f'  <path d="M {fan_x0} {cy_b} L {fan_xm} {cy_b} '
                f'L {fan_xm} {cy_c} L {fan_x1} {cy_c}" fill="none" '
                'stroke="#1967D2" stroke-width="2.2" marker-end="url(#fan-arr)"/>'
            ),
        ]
    )

    # Step 6 Target Cards
    parts.append(
        render_target_card(
            step6_x,
            y_6a,
            step6_w,
            target_height,
            "#E6F4EA",
            "#34A853",
            "#137333",
            "6A",
            "Shared & Local MCP \u2192 SQL (RLS)",
            [
                "Re-verifies KMS ctx+jwt (tid+uid+aid);",
                "sets SET LOCAL app.current_tenant_id",
                "under FORCE RLS + pre-retrieval",
                "user_id / group RAG ACL filter.",
                "Non-superuser role (cymbal_mcp_app).",
            ],
        )
    )
    parts.append(
        render_target_card(
            step6_x,
            y_6b,
            step6_w,
            target_height,
            "#E8F0FE",
            "#1967D2",
            "#174EA6",
            "6B",
            "Model Routing \u2192 Gemini & Garden",
            [
                "Governed routing to Pro (FinVault)",
                "or Flash + AskPro (RetailStream)",
                "over 32k shared immutable prefix",
                "cache (-89.9% input tokens, modeled)",
                "in us-central1 with OTel spans.",
            ],
        )
    )
    parts.append(
        render_target_card(
            step6_x,
            y_6c,
            step6_w,
            target_height,
            "#FEF7E0",
            "#F9AB00",
            "#B06000",
            "6C",
            "Enterprise 3P SaaS & PSC Spokes",
            [
                "Jira / ServiceNow / Drive via 3LO",
                "vault key {tid}:{uid}:{connector}",
                "plus per-tenant ct-<tid> IAM SA.",
                "Returns 401 OAuth step-up if user",
                "consent is unlinked; optional PSC.",
            ],
        )
    )

    # Bottom Clarification Strip
    footer_y = 786
    footer_height = 78
    footer_width = 574
    footer_cards = [
        (
            "#1967D2",
            "Existing ISV Stack (Step 1) + Client-to-Agent (Step 2)",
            [
                "ISV apps on Cloud Run, GKE, or GCE expose multiple agents (SRE, Compliance)",
                "and enter Step 2 for fast DPoP, replay & agent-routing admission checks.",
            ],
        ),
        (
            "#F9AB00",
            "Why Egress Model Armor & Model Routing Live at Step 5",
            [
                "Placing Model Armor at Agent-to-Anywhere monitors each runtime model and",
                "tool decision in context while governing outbound LLM routing and MCP calls.",
            ],
        ),
        (
            "#137333",
            "Scaling ADK, LangGraph & BYO Docker + Agent Sandboxes",
            [
                "Stateless agent services autoscale concurrently over Firestore sessions & CMEK",
                "semantic memory; untrusted code runs in per-session agent sandboxes in Gemini.",
            ],
        ),
    ]
    for card_index, (accent, footer_heading, footer_lines) in enumerate(
        footer_cards
    ):
        parts.append(
            render_footer_card(
                24 + card_index * (footer_width + 15),
                footer_y,
                footer_width,
                footer_height,
                accent,
                footer_heading,
                footer_lines,
            )
        )

    parts.append("</svg>\n")
    return "\n".join(parts)


def rasterize_svg_to_png(
    svg_path: Path, png_path: Path, width: int, height: int
) -> None:
    """Rasterize an SVG file to a crisp 2x Retina PNG using headless Chrome.

    Args:
        svg_path: Source vector SVG path.
        png_path: Destination PNG path.
        width: Base CSS viewport width (rendered at 2x scale).
        height: Base CSS viewport height (rendered at 2x scale).
    """
    chrome_bin = (
        shutil.which("google-chrome")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
    )
    if not chrome_bin:
        print(
            f"Skipping PNG rasterization (no Chrome binary found): {png_path}"
        )
        return

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", encoding="utf-8", delete=False
    ) as tmp_file:
        wrapper_html = Path(tmp_file.name)
        tmp_file.write(
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>*{{margin:0;padding:0;}}body{{width:{width}px;height:{height}px;"
            "overflow:hidden;background:#F8F9FA;}}</style></head><body>"
            f"{svg_path.read_text(encoding='utf-8')}</body></html>"
        )
    try:
        subprocess.run(
            [
                chrome_bin,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                f"--window-size={width},{height}",
                "--force-device-scale-factor=2",
                f"--screenshot={png_path}",
                str(wrapper_html),
            ],
            check=True,
        )
    finally:
        wrapper_html.unlink(missing_ok=True)


def main() -> None:
    """Generate both the vector SVG and 2x Retina PNG assets."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    svg_content = build_svg()
    OUTPUT_SVG_PATH.write_text(svg_content, encoding="utf-8")
    rasterize_svg_to_png(OUTPUT_SVG_PATH, OUTPUT_PNG_PATH, 1800, 880)
    print(f"Wrote {OUTPUT_SVG_PATH} and {OUTPUT_PNG_PATH}")


if __name__ == "__main__":
    main()
