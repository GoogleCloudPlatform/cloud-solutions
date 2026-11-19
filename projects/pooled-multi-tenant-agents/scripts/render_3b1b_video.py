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

"""Renders the 3Blue1Brown-style 1080p MP4 architecture & math walkthrough video.

Uses PyCairo (`cairo`) + `ffmpeg` to synthesize a 90-second (2,700 frames at 30 fps)
1920x1080 H.264 MP4 video with synchronized ambient harmonic audio in `docs/assets/cymbal_3b1b_walkthrough.mp4`.
Also exports 6 high-resolution chapter keyframe PNGs for visual inspection and documentation.
"""

from __future__ import annotations

import math
import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import cairo

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION_SECONDS = 90
TOTAL_FRAMES = (
    DURATION_SECONDS * FPS
)  # 2,700 frames (6 chapters x 15s = 450 frames/chapter)

# Iconic 3Blue1Brown (Manim) Color Palette (normalized RGB)
BG_DARK = (0.043, 0.059, 0.098)  # #0B0F19
BG_PANEL = (0.075, 0.102, 0.165)  # #131A2A
GRID_MINOR = (0.10, 0.15, 0.23, 0.35)
GRID_MAJOR = (0.16, 0.24, 0.36, 0.55)
BLUE_C = (0.345, 0.769, 0.867)  # #58C4DD (FinVault / Primary Math Vector)
BLUE_D = (0.161, 0.671, 0.792)  # #29ABCA
GOLD_C = (0.957, 0.816, 0.247)  # #F4D03F (RetailStream / Secondary Vector)
GREEN_C = (0.514, 0.757, 0.404)  # #83C167 (Verified / Passed)
RED_C = (0.988, 0.384, 0.333)  # #FC6255 (Attack / Blocked / Evicted)
PURPLE_C = (0.604, 0.447, 0.675)  # #9A72AC (Crypto / KMS / AEAD)
TEAL_C = (0.361, 0.816, 0.702)  # #5CD0B3 (Database / RLS / Cache)
WHITE = (0.96, 0.97, 0.99)
MUTED = (0.62, 0.67, 0.75)


def smooth(t: float) -> float:
    """Manim-style cubic smoothstep interpolation on [0, 1]."""
    clamped = max(0.0, min(1.0, t))
    return clamped * clamped * (3.0 - 2.0 * clamped)


def sub_alpha(local_t: float, start: float, end: float) -> float:
    """Returns smooth eased progress in [0, 1] as `local_t` moves from `start` to `end`."""
    if end <= start:
        return 1.0 if local_t >= start else 0.0
    return smooth((local_t - start) / (end - start))


def draw_rounded_rect(
    ctx: cairo.Context,
    x: float,
    y: float,
    w: float,
    h: float,
    r: float = 14.0,
) -> None:
    """Adds a rounded-rectangle path to `ctx`."""
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def draw_glow_circle(
    ctx: cairo.Context,
    cx: float,
    cy: float,
    radius: float,
    color: tuple[float, float, float],
    alpha: float = 1.0,
) -> None:
    """Draws a 3B1B glowing node with radial gradient halo."""
    ctx.new_path()
    pat = cairo.RadialGradient(cx, cy, radius * 0.2, cx, cy, radius * 2.4)
    pat.add_color_stop_rgba(0.0, color[0], color[1], color[2], 0.42 * alpha)
    pat.add_color_stop_rgba(0.5, color[0], color[1], color[2], 0.14 * alpha)
    pat.add_color_stop_rgba(1.0, color[0], color[1], color[2], 0.0)
    ctx.set_source(pat)
    ctx.arc(cx, cy, radius * 2.4, 0, 2 * math.pi)
    ctx.fill()

    ctx.new_path()
    ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], alpha)
    ctx.arc(cx, cy, radius, 0, 2 * math.pi)
    ctx.fill()

    ctx.new_path()
    ctx.set_line_width(3.0)
    ctx.set_source_rgba(color[0], color[1], color[2], alpha)
    ctx.arc(cx, cy, radius, 0, 2 * math.pi)
    ctx.stroke()


def draw_arrow(
    ctx: cairo.Context,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: tuple[float, float, float],
    alpha: float = 1.0,
    progress: float = 1.0,
    width: float = 3.2,
) -> None:
    """Draws an animated Manim-style vector arrow from (x1, y1) toward (x2, y2)."""
    if progress <= 0.01:
        return
    ex = x1 + (x2 - x1) * progress
    ey = y1 + (y2 - y1) * progress
    ctx.new_path()
    ctx.set_source_rgba(color[0], color[1], color[2], alpha)
    ctx.set_line_width(width)
    ctx.move_to(x1, y1)
    ctx.line_to(ex, ey)
    ctx.stroke()

    angle = math.atan2(ey - y1, ex - x1)
    head_len = 14.0
    ctx.new_path()
    ctx.move_to(ex, ey)
    ctx.line_to(
        ex - head_len * math.cos(angle - 0.42),
        ey - head_len * math.sin(angle - 0.42),
    )
    ctx.line_to(
        ex - head_len * math.cos(angle + 0.42),
        ey - head_len * math.sin(angle + 0.42),
    )
    ctx.close_path()
    ctx.fill()


def draw_text(
    ctx: cairo.Context,
    text: str,
    x: float,
    y: float,
    size: float = 24.0,
    color: tuple[float, float, float] = WHITE,
    alpha: float = 1.0,
    family: str = "DejaVu Serif",
    bold: bool = False,
    italic: bool = False,
    align: str = "left",
) -> None:
    """Draws crisp anti-aliased text with optional alignment (`left`, `center`, `right`)."""
    if alpha <= 0.01:
        return
    slant = cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face(family, slant, weight)
    ctx.set_font_size(size)
    extents = ctx.text_extents(text)
    draw_x = x
    if align == "center":
        draw_x = x - extents.width / 2.0
    elif align == "right":
        draw_x = x - extents.width
    ctx.move_to(draw_x, y)
    ctx.set_source_rgba(color[0], color[1], color[2], alpha)
    ctx.show_text(text)


def draw_number_plane(ctx: cairo.Context, t_global: float) -> None:
    """Draws the signature 3Blue1Brown subtle background coordinate grid."""
    ctx.set_source_rgb(*BG_DARK)
    ctx.paint()

    spacing = 60.0
    drift = (t_global * 6.0) % spacing
    ctx.set_line_width(1.0)
    for idx, x in enumerate(range(-60, WIDTH + 120, int(spacing))):
        gx = x + drift * 0.2
        ctx.set_source_rgba(*(GRID_MAJOR if idx % 4 == 0 else GRID_MINOR))
        ctx.move_to(gx, 0)
        ctx.line_to(gx, HEIGHT)
        ctx.stroke()

    for idx, y in enumerate(range(0, HEIGHT + 60, int(spacing))):
        ctx.set_source_rgba(*(GRID_MAJOR if idx % 4 == 0 else GRID_MINOR))
        ctx.move_to(0, y)
        ctx.line_to(WIDTH, y)
        ctx.stroke()


def draw_header_and_timeline(
    ctx: cairo.Context,
    chapter_idx: int,
    chapter_title: str,
    chapter_subtitle: str,
    t_global: float,
) -> None:
    """Draws the top 3B1B chapter banner and bottom timeline scrubber."""
    # Top banner
    draw_rounded_rect(ctx, 48, 28, WIDTH - 96, 86, r=16)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.90)
    ctx.fill_preserve()
    ctx.set_line_width(1.5)
    ctx.set_source_rgba(BLUE_C[0], BLUE_C[1], BLUE_C[2], 0.35)
    ctx.stroke()

    # Chapter pill
    draw_rounded_rect(ctx, 72, 46, 175, 48, r=10)
    ctx.set_source_rgba(BLUE_C[0], BLUE_C[1], BLUE_C[2], 0.18)
    ctx.fill_preserve()
    ctx.set_source_rgba(BLUE_C[0], BLUE_C[1], BLUE_C[2], 0.85)
    ctx.stroke()
    draw_text(
        ctx,
        f"CHAPTER {chapter_idx} / 6",
        159,
        77,
        size=19,
        color=BLUE_C,
        family="DejaVu Sans Mono",
        bold=True,
        align="center",
    )

    draw_text(
        ctx,
        chapter_title,
        270,
        68,
        size=28,
        color=WHITE,
        family="DejaVu Serif",
        bold=True,
    )
    draw_text(
        ctx,
        chapter_subtitle,
        270,
        98,
        size=17,
        color=MUTED,
        family="DejaVu Sans",
    )

    # Top-right timestamp badge
    mm = int(t_global) // 60
    ss = int(t_global) % 60
    draw_text(
        ctx,
        f"{mm:02d}:{ss:02d} / 01:30",
        WIDTH - 76,
        78,
        size=21,
        color=GOLD_C,
        family="DejaVu Sans Mono",
        bold=True,
        align="right",
    )

    # Bottom chapter progress bar
    bar_y = HEIGHT - 36
    ctx.set_line_width(6.0)
    ctx.set_source_rgba(1, 1, 1, 0.12)
    ctx.move_to(60, bar_y)
    ctx.line_to(WIDTH - 60, bar_y)
    ctx.stroke()

    progress = max(0.0, min(1.0, t_global / DURATION_SECONDS))
    ctx.set_source_rgba(BLUE_C[0], BLUE_C[1], BLUE_C[2], 0.95)
    ctx.move_to(60, bar_y)
    ctx.line_to(60 + (WIDTH - 120) * progress, bar_y)
    ctx.stroke()

    chapter_names = [
        "1. Cost & Isolation Paradox",
        "2. Hop 0/1 DPoP & 3-Key Ring",
        "3. KMS v2 & Ciphertext RAG",
        "4. Loop-Local FORCE RLS",
        "5. Atomic Offboarding",
        "6. Evals & 55/55 Proof",
    ]
    seg_w = (WIDTH - 120) / 6.0
    for idx, label in enumerate(chapter_names):
        sx = 60 + idx * seg_w
        active = (idx + 1) == chapter_idx
        ctx.new_path()
        ctx.set_source_rgba(
            *(GOLD_C if active else MUTED), 0.95 if active else 0.55
        )
        ctx.arc(sx, bar_y, 6.0 if active else 4.0, 0, 2 * math.pi)
        ctx.fill()
        draw_text(
            ctx,
            label,
            sx + seg_w / 2,
            bar_y - 12,
            size=14,
            color=GOLD_C if active else MUTED,
            family="DejaVu Sans",
            bold=active,
            align="center",
        )


def render_chapter_1(ctx: cairo.Context, local_t: float) -> None:
    """Chapter 1: The Multi-Tenant Cost & Isolation Paradox (0s - 15s)."""
    a1 = sub_alpha(local_t, 0.0, 2.0)
    a2 = sub_alpha(local_t, 2.0, 5.0)
    a3 = sub_alpha(local_t, 5.0, 8.5)
    a4 = sub_alpha(local_t, 8.5, 12.0)

    # Left Card: 250 Dedicated Silos vs Governed Pool
    draw_rounded_rect(ctx, 70, 145, 840, 430, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.88 * a1)
    ctx.fill_preserve()
    ctx.set_source_rgba(RED_C[0], RED_C[1], RED_C[2], 0.45 * a1)
    ctx.set_line_width(2.0)
    ctx.stroke()

    draw_text(
        ctx,
        "Baseline Hub-and-Spoke (1 Project / Tenant)",
        105,
        195,
        size=25,
        color=RED_C,
        bold=True,
        alpha=a1,
    )
    draw_text(
        ctx,
        "Cost_silo(N) = N × $780/mo  ⇒  $195,000/mo  (N = 250 tenants)",
        105,
        242,
        size=22,
        color=WHITE,
        italic=True,
        alpha=a1,
    )

    # Draw grid of mini silo boxes morphing/collapsing into the pooled manifold
    collapse = sub_alpha(local_t, 3.0, 6.5)
    target_cx, target_cy = 490.0, 420.0
    for row in range(4):
        for col in range(10):
            bx = 115 + col * 72
            by = 280 + row * 55
            cx = bx + (target_cx - bx) * collapse * 0.72
            cy = by + (target_cy - by) * collapse * 0.72
            alpha_box = a1 * (1.0 - 0.92 * collapse)
            draw_rounded_rect(ctx, cx, cy, 52, 36, r=6)
            ctx.set_source_rgba(RED_C[0], RED_C[1], RED_C[2], 0.22 * alpha_box)
            ctx.fill_preserve()
            ctx.set_source_rgba(RED_C[0], RED_C[1], RED_C[2], 0.75 * alpha_box)
            ctx.set_line_width(1.5)
            ctx.stroke()

    if collapse > 0.1:
        draw_glow_circle(
            ctx, target_cx, target_cy, 64 * collapse, BLUE_C, alpha=collapse
        )
        draw_text(
            ctx,
            "Pattern A Pool",
            target_cx,
            target_cy - 6,
            size=19,
            color=WHITE,
            family="DejaVu Sans",
            bold=True,
            align="center",
            alpha=collapse,
        )
        draw_text(
            ctx,
            "$2,125/mo (-98.91%)",
            target_cx,
            target_cy + 20,
            size=17,
            color=GREEN_C,
            family="DejaVu Sans Mono",
            bold=True,
            align="center",
            alpha=collapse,
        )

    # Right Card: Shared Prefix Cache Economics Equation
    draw_rounded_rect(ctx, 960, 145, 890, 430, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.88 * a2)
    ctx.fill_preserve()
    ctx.set_source_rgba(BLUE_C[0], BLUE_C[1], BLUE_C[2], 0.5 * a2)
    ctx.stroke()

    draw_text(
        ctx,
        "Immutable 32k Prefix Cache (READ_ONLY_IMMUTABLE_PREFIX)",
        995,
        195,
        size=21.5,
        color=BLUE_C,
        bold=True,
        alpha=a2,
    )
    draw_text(
        ctx,
        "C_uncached = P_sys(32,000) + T_turn(2,000) = 34,000 tokens",
        995,
        250,
        size=21,
        color=MUTED,
        italic=True,
        alpha=a2,
    )
    draw_text(
        ctx,
        "C_pooled = 0.10 · P_sys(32,000) + T_turn(2,000) = 5,200 tokens",
        995,
        296,
        size=21.5,
        color=GOLD_C,
        bold=True,
        italic=True,
        alpha=a2,
    )

    # Visual bar comparison
    bar_w_uncached = 720 * a2
    bar_w_pooled = 720 * (5200.0 / 34000.0) * a2
    draw_rounded_rect(ctx, 995, 340, max(10, bar_w_uncached), 42, r=8)
    ctx.set_source_rgba(RED_C[0], RED_C[1], RED_C[2], 0.35 * a2)
    ctx.fill()
    draw_text(
        ctx,
        "Uncached: 34,000 billed tokens / turn",
        1010,
        368,
        size=18,
        color=WHITE,
        family="DejaVu Sans Mono",
        alpha=a2,
    )

    draw_rounded_rect(ctx, 995, 405, max(10, bar_w_pooled), 42, r=8)
    ctx.set_source_rgba(GREEN_C[0], GREEN_C[1], GREEN_C[2], 0.75 * a2)
    ctx.fill()
    draw_text(
        ctx,
        "Pooled Cache Hit: 5,200 billed tokens  ⇒  -84.71% Input Token COGS",
        1010,
        433,
        size=18.5,
        color=GREEN_C,
        family="DejaVu Sans Mono",
        bold=True,
        alpha=a2,
    )

    draw_text(
        ctx,
        "Zero Tenant Write-Back to Shared Prefix  •  80% Core Reused in WS3 & WS4",
        995,
        525,
        size=19,
        color=TEAL_C,
        family="DejaVu Sans",
        bold=True,
        alpha=a3,
    )

    # Bottom Full-Width Card: The 4 AI-Specific Pooled Failure Modes Stopped
    draw_rounded_rect(ctx, 70, 610, 1780, 360, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.92 * a3)
    ctx.fill_preserve()
    ctx.set_source_rgba(GOLD_C[0], GOLD_C[1], GOLD_C[2], 0.45 * a3)
    ctx.stroke()

    draw_text(
        ctx,
        "Why a Naive Shared Agent Fails CISO Review — The 4 AI-Specific Failure Modes:",
        105,
        658,
        size=24,
        color=GOLD_C,
        bold=True,
        alpha=a3,
    )

    failures = [
        (
            "1. Mid-Turn Tool Bleed",
            "Tenant B's LLM calls Tenant A's Jira 3LO tool",
            "Stopped at Hop 2: before_agent_callback prunes ctx.active_tools",
            BLUE_C,
        ),
        (
            "2. Confused Deputy SA",
            "Shared Cloud Run SA has project-wide IAM",
            "Stopped at Hop 3/5: Per-tenant ct-<sha256[:24]> SA broker (Blast=1)",
            PURPLE_C,
        ),
        (
            "3. Memory & Vector Bleed",
            "Plaintext embeddings or shared DEKs leak",
            "Stopped at Hop 3: Per-record AES-256-GCM DEK + Ciphertext RAG",
            TEAL_C,
        ),
        (
            "4. Noisy-Neighbor Flood",
            "Standard 16k loop starves Enterprise TPM",
            "Stopped at Hop 3: 4,000-token clamp + Redis loop breaker (429)",
            GREEN_C,
        ),
    ]
    for idx, (title, problem, fix, col) in enumerate(failures):
        card_x = 105 + idx * 432
        draw_rounded_rect(ctx, card_x, 690, 412, 245, r=14)
        ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.9 * a4)
        ctx.fill_preserve()
        ctx.set_source_rgba(col[0], col[1], col[2], 0.65 * a4)
        ctx.set_line_width(2.0)
        ctx.stroke()

        draw_text(
            ctx,
            title,
            card_x + 20,
            732,
            size=20,
            color=col,
            family="DejaVu Sans",
            bold=True,
            alpha=a4,
        )
        draw_text(
            ctx,
            problem,
            card_x + 20,
            775,
            size=14.5,
            color=MUTED,
            family="DejaVu Sans",
            alpha=a4,
        )
        draw_rounded_rect(ctx, card_x + 16, 810, 380, 100, r=10)
        ctx.set_source_rgba(col[0], col[1], col[2], 0.12 * a4)
        ctx.fill()
        parts = fix.split(": ", 1)
        draw_text(
            ctx,
            parts[0] + ":",
            card_x + 28,
            845,
            size=14.5,
            color=GREEN_C,
            family="DejaVu Sans Mono",
            bold=True,
            alpha=a4,
        )
        draw_text(
            ctx,
            parts[1],
            card_x + 28,
            878,
            size=13.5,
            color=WHITE,
            family="DejaVu Sans",
            alpha=a4,
        )


def render_chapter_2(ctx: cairo.Context, local_t: float) -> None:
    """Chapter 2: Hop 0/1 DPoP Token Exchange & 3-Key Rolling Signing Ring (15s - 30s)."""
    a1 = sub_alpha(local_t, 0.0, 2.5)
    a2 = sub_alpha(local_t, 2.5, 6.0)
    a3 = sub_alpha(local_t, 6.0, 10.5)
    a4 = sub_alpha(local_t, 10.5, 13.5)

    # Top Equation Box: RFC 9449 DPoP Sender-Constrained Binding
    draw_rounded_rect(ctx, 70, 140, 1780, 200, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.90 * a1)
    ctx.fill_preserve()
    ctx.set_source_rgba(BLUE_C[0], BLUE_C[1], BLUE_C[2], 0.45 * a1)
    ctx.set_line_width(2.0)
    ctx.stroke()

    draw_text(
        ctx,
        "Hop 0 + Hop 1: Unforgeable RFC 9449 DPoP Sender-Constrained Gateway Token",
        105,
        188,
        size=24,
        color=BLUE_C,
        bold=True,
        alpha=a1,
    )
    draw_text(
        ctx,
        "Token = Sign_ES256(active_kid, { iss, aud, sub, tenant_id, user_role, cnf: { jkt: SHA256(JWK_client) } })",
        105,
        238,
        size=22,
        color=GOLD_C,
        italic=True,
        alpha=a1,
    )
    draw_text(
        ctx,
        "Proof Verification:  htm == req.method  ∧  htu == canonical_url  ∧  ath == SHA256(Token)  ∧  SET dpop:jti NX EX 300 == True",
        105,
        286,
        size=19,
        color=TEAL_C,
        family="DejaVu Sans Mono",
        alpha=a1,
    )
    draw_text(
        ctx,
        "Strict Fail-Closed Contract: Coroutine/non-bool Redis client rejected; Redis/OS outage → HTTP 503 + Retry-After (never 401 or fail-open)",
        105,
        320,
        size=16,
        color=MUTED,
        family="DejaVu Sans",
        alpha=a1,
    )

    # Bottom 3-Stage Rolling Key Rotation Ring Diagram (PR #34 & #35)
    draw_rounded_rect(ctx, 70, 368, 1780, 602, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.92 * a2)
    ctx.fill_preserve()
    ctx.set_source_rgba(PURPLE_C[0], PURPLE_C[1], PURPLE_C[2], 0.5 * a2)
    ctx.stroke()

    draw_text(
        ctx,
        "Zero-Downtime 3-Key Rolling Signing Ring: (active_kid, previous_kid, next_kid)",
        105,
        416,
        size=25,
        color=PURPLE_C,
        bold=True,
        alpha=a2,
    )
    draw_text(
        ctx,
        "Why a 2-key (active, previous) ring fails during multi-replica Cloud Run rollouts — and how next_kid solves it:",
        105,
        452,
        size=18,
        color=MUTED,
        family="DejaVu Sans",
        alpha=a2,
    )

    stages = [
        (
            "STAGE 1: Pre-Stage Verify Key B",
            "active_kid = gw-key-A (signs)",
            "next_kid   = gw-key-B (verify-only)",
            "previous   = None",
            "All replicas learn public key B BEFORE any replica signs with B.",
            BLUE_C,
            a2,
        ),
        (
            "STAGE 2: Switch Signing to Key B",
            "active_kid   = gw-key-B (signs)",
            "previous_kid = gw-key-A (verify-only)",
            "next_kid     = None",
            "New Replica R2 signs with B → Old Replica R1 verifies via next_kid=B!",
            GOLD_C,
            a3,
        ),
        (
            "STAGE 3: Retire Old Key A",
            "active_kid   = gw-key-B (signs)",
            "previous_kid = None (A retired)",
            "next_kid     = None",
            "After token_ttl (600s) + skew (60s), Key A is dropped cleanly.",
            GREEN_C,
            a4,
        ),
    ]

    for idx, (
        st_title,
        line_one,
        line_two,
        line_three,
        desc,
        col,
        st_alpha,
    ) in enumerate(stages):
        sx = 105 + idx * 575
        sy = 485
        draw_rounded_rect(ctx, sx, sy, 545, 340, r=16)
        ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.92 * st_alpha)
        ctx.fill_preserve()
        ctx.set_source_rgba(col[0], col[1], col[2], 0.75 * st_alpha)
        ctx.set_line_width(2.5)
        ctx.stroke()

        draw_text(
            ctx,
            st_title,
            sx + 24,
            sy + 44,
            size=21,
            color=col,
            family="DejaVu Sans",
            bold=True,
            alpha=st_alpha,
        )

        # Draw key ring circle inside stage card
        rcx, rcy = sx + 100, sy + 165
        draw_glow_circle(ctx, rcx, rcy, 48, col, alpha=st_alpha)
        draw_text(
            ctx,
            f"Ring v{idx + 1}",
            rcx,
            rcy + 6,
            size=17,
            color=WHITE,
            family="DejaVu Sans Mono",
            bold=True,
            align="center",
            alpha=st_alpha,
        )

        draw_text(
            ctx,
            line_one,
            sx + 172,
            sy + 130,
            size=15.0,
            color=GREEN_C,
            family="DejaVu Sans Mono",
            bold=True,
            alpha=st_alpha,
        )
        draw_text(
            ctx,
            line_two,
            sx + 172,
            sy + 168,
            size=15.0,
            color=BLUE_C,
            family="DejaVu Sans Mono",
            alpha=st_alpha,
        )
        draw_text(
            ctx,
            line_three,
            sx + 172,
            sy + 206,
            size=15.0,
            color=MUTED,
            family="DejaVu Sans Mono",
            alpha=st_alpha,
        )

        draw_text(
            ctx,
            desc,
            sx + 22,
            sy + 295,
            size=14.2,
            color=WHITE,
            family="DejaVu Sans",
            alpha=st_alpha,
        )

        if idx < 2:
            draw_arrow(
                ctx,
                sx + 548,
                sy + 165,
                sx + 572,
                sy + 165,
                col,
                alpha=st_alpha,
                progress=st_alpha,
                width=3.5,
            )

    # Bottom guardrails summary banner
    draw_rounded_rect(ctx, 105, 850, 1710, 92, r=12)
    ctx.set_source_rgba(GREEN_C[0], GREEN_C[1], GREEN_C[2], 0.12 * a4)
    ctx.fill_preserve()
    ctx.set_source_rgba(GREEN_C[0], GREEN_C[1], GREEN_C[2], 0.55 * a4)
    ctx.set_line_width(1.5)
    ctx.stroke()
    draw_text(
        ctx,
        "Cryptographic Mutation Guards Verified:  alg='none' → REJECT  |  alg='HS256' → REJECT  |  Swapped kid → REJECT  |  Duplicate PEM version → REJECT",
        960,
        904,
        size=19,
        color=GREEN_C,
        family="DejaVu Sans Mono",
        bold=True,
        align="center",
        alpha=a4,
    )


def render_chapter_3(ctx: cairo.Context, local_t: float) -> None:
    """Chapter 3: KMS v2 Envelope Encryption & Ciphertext-Only RAG Embeddings (30s - 45s)."""
    a1 = sub_alpha(local_t, 0.0, 2.5)
    a2 = sub_alpha(local_t, 2.5, 6.5)
    a3 = sub_alpha(local_t, 6.5, 11.0)
    a4 = sub_alpha(local_t, 11.0, 14.0)

    # Left Panel: v2 Envelope Encryption & Ciphertext-Only Embeddings
    draw_rounded_rect(ctx, 70, 145, 880, 825, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.90 * a1)
    ctx.fill_preserve()
    ctx.set_source_rgba(PURPLE_C[0], PURPLE_C[1], PURPLE_C[2], 0.5 * a1)
    ctx.set_line_width(2.0)
    ctx.stroke()

    draw_text(
        ctx,
        "Hop 3: Per-Record KMS v2 Envelope + Sealed Embeddings",
        105,
        195,
        size=24,
        color=PURPLE_C,
        bold=True,
        alpha=a1,
    )
    draw_text(
        ctx,
        "1. Fresh 256-bit DEK per write:  DEK_i ← os.urandom(32)",
        105,
        245,
        size=17.5,
        color=WHITE,
        family="DejaVu Sans Mono",
        alpha=a1,
    )
    draw_text(
        ctx,
        "2. Wrap DEK under Tenant SA:  W_i = KMS_Wrap(cmek_tenant, DEK_i, AAD_key)",
        105,
        282,
        size=17.5,
        color=GOLD_C,
        family="DejaVu Sans Mono",
        alpha=a1,
    )
    draw_text(
        ctx,
        "3. Seal Payload:    C_payload = AES-256-GCM(DEK_i, nonce_p, JSON, AAD_v2)",
        105,
        319,
        size=17.5,
        color=BLUE_C,
        family="DejaVu Sans Mono",
        alpha=a1,
    )
    draw_text(
        ctx,
        "4. Seal Embedding:  C_emb     = AES-256-GCM(DEK_i, nonce_e, float64[], AAD_emb)",
        105,
        356,
        size=17.5,
        color=TEAL_C,
        family="DejaVu Sans Mono",
        bold=True,
        alpha=a1,
    )

    # Stored Firestore Record Box (proving NO plaintext "embedding" field exists)
    draw_rounded_rect(ctx, 105, 395, 810, 290, r=14)
    ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.95 * a2)
    ctx.fill_preserve()
    ctx.set_source_rgba(TEAL_C[0], TEAL_C[1], TEAL_C[2], 0.65 * a2)
    ctx.stroke()

    draw_text(
        ctx,
        "Firestore Document State (_store[key]) — Zero Plaintext Vectors:",
        130,
        435,
        size=19,
        color=TEAL_C,
        family="DejaVu Sans",
        bold=True,
        alpha=a2,
    )
    record_lines = [
        '{  "v": 2,',
        '   "scope": "user",',
        '   "kms_key_name": ".../cryptoKeys/finvault-alpha-cmek",',
        '   "wrapped_dek_b64": "CiQAz9...7xQ==",',
        '   "nonce_hex": "9f4c2b8011e4a7c1d309ab12",',
        '   "ciphertext_hex": "4a88e1...f09b",',
        '   "embedding_nonce_hex": "31a7d099bc4210fe88512c04",',
        '   "embedding_ciphertext_hex": "e7219c04...881a"  }',
    ]
    for idx, line in enumerate(record_lines):
        col = GREEN_C if "embedding_" in line else WHITE
        draw_text(
            ctx,
            line,
            135,
            472 + idx * 25,
            size=16,
            color=col,
            family="DejaVu Sans Mono",
            bold=("embedding_" in line),
            alpha=a2,
        )

    # Downgrade defense callout
    draw_rounded_rect(ctx, 105, 710, 810, 230, r=14)
    ctx.set_source_rgba(RED_C[0], RED_C[1], RED_C[2], 0.12 * a3)
    ctx.fill_preserve()
    ctx.set_source_rgba(RED_C[0], RED_C[1], RED_C[2], 0.55 * a3)
    ctx.stroke()
    draw_text(
        ctx,
        "Downgrade & Tamper Defense (PR #33):",
        130,
        750,
        size=20,
        color=RED_C,
        family="DejaVu Sans",
        bold=True,
        alpha=a3,
    )
    draw_text(
        ctx,
        "• Unencrypted 'embedding' field injected in store → MemoryAccessDenied",
        130,
        790,
        size=17,
        color=WHITE,
        family="DejaVu Sans",
        alpha=a3,
    )
    draw_text(
        ctx,
        "• Swapping Tenant B's embedding_ciphertext_hex into Tenant A's record",
        130,
        825,
        size=17,
        color=WHITE,
        family="DejaVu Sans",
        alpha=a3,
    )
    draw_text(
        ctx,
        "  fails AES-GCM tag check (AAD binds v2:embedding + tenant + user + key)",
        130,
        855,
        size=16.5,
        color=GOLD_C,
        family="DejaVu Sans Mono",
        alpha=a3,
    )
    draw_text(
        ctx,
        "• reseal_legacy_embeddings() migrates legacy records to ciphertext-only",
        130,
        895,
        size=17,
        color=GREEN_C,
        family="DejaVu Sans",
        bold=True,
        alpha=a3,
    )

    # Right Panel: Cosine Similarity in Decrypted Tenant Subspace + DEK Cache Reuse
    draw_rounded_rect(ctx, 980, 145, 870, 825, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.90 * a2)
    ctx.fill_preserve()
    ctx.set_source_rgba(BLUE_C[0], BLUE_C[1], BLUE_C[2], 0.5 * a2)
    ctx.stroke()

    draw_text(
        ctx,
        "Ciphertext-Only RAG Search & Zero-Extra-Unwrap DEK Reuse",
        1015,
        195,
        size=23,
        color=BLUE_C,
        bold=True,
        alpha=a2,
    )
    draw_text(
        ctx,
        "sim(q, v_i) = ⟨q, Open_Embedding(C_emb,i)⟩ / (‖q‖ · ‖v_i‖)",
        1015,
        242,
        size=22,
        color=GOLD_C,
        italic=True,
        alpha=a2,
    )

    # Draw 2D vector space circle on right panel
    origin_x, origin_y = 1360.0, 515.0
    radius = 185.0
    ctx.new_path()
    ctx.set_line_width(1.5)
    ctx.set_source_rgba(1, 1, 1, 0.18 * a2)
    ctx.arc(origin_x, origin_y, radius, 0, 2 * math.pi)
    ctx.stroke()
    ctx.new_path()
    ctx.move_to(origin_x - radius - 20, origin_y)
    ctx.line_to(origin_x + radius + 20, origin_y)
    ctx.move_to(origin_x, origin_y - radius - 20)
    ctx.line_to(origin_x, origin_y + radius + 20)
    ctx.stroke()

    # Query vector q (Gold)
    q_angle = -0.32
    qx = origin_x + radius * 0.90 * math.cos(q_angle)
    qy = origin_y + radius * 0.90 * math.sin(q_angle)
    draw_arrow(
        ctx,
        origin_x,
        origin_y,
        qx,
        qy,
        GOLD_C,
        alpha=a2,
        progress=a2,
        width=4.0,
    )
    draw_text(
        ctx,
        "Query q (Alice)",
        qx + 14,
        qy - 6,
        size=17.5,
        color=GOLD_C,
        bold=True,
        alpha=a2,
    )

    # Alice FinVault candidate vectors (Blue/Green — decrypted & scored)
    candidates = [
        (0.18, "v_1 (score=0.991) [Top-1]", GREEN_C),
        (-0.82, "v_2 (score=0.968) [Top-2]", BLUE_C),
        (-1.42, "v_3 (score=0.612)", BLUE_D),
    ]
    for ang, label, col in candidates:
        vx = origin_x + radius * 0.85 * math.cos(ang)
        vy = origin_y + radius * 0.85 * math.sin(ang)
        draw_arrow(
            ctx,
            origin_x,
            origin_y,
            vx,
            vy,
            col,
            alpha=a3,
            progress=a3,
            width=3.0,
        )
        draw_text(
            ctx,
            label,
            vx + 14,
            vy + (16 if ang > 0 else -8),
            size=15.5,
            color=col,
            family="DejaVu Sans Mono",
            align="left",
            alpha=a3,
        )

    # RetailStream vector (Locked Red/Purple in quadrant III — never unwrapped!)
    rx = origin_x + radius * 0.78 * math.cos(2.35)
    ry = origin_y + radius * 0.78 * math.sin(2.35)
    draw_glow_circle(ctx, rx, ry, 24, RED_C, alpha=a3)
    draw_text(
        ctx,
        "RetailStream C_emb (Skipped by ACL — 0 KMS Unwraps)",
        rx - 30,
        ry + 44,
        size=16,
        color=RED_C,
        family="DejaVu Sans Mono",
        bold=True,
        alpha=a3,
    )

    # Bottom right summary box: KMS unwrap math
    draw_rounded_rect(ctx, 1015, 760, 800, 180, r=14)
    ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.92 * a4)
    ctx.fill_preserve()
    ctx.set_source_rgba(GREEN_C[0], GREEN_C[1], GREEN_C[2], 0.65 * a4)
    ctx.stroke()
    draw_text(
        ctx,
        "DEK Cache Accounting + Leaf-Level RAG Quarantine:",
        1040,
        800,
        size=19,
        color=GREEN_C,
        family="DejaVu Sans",
        bold=True,
        alpha=a4,
    )
    draw_text(
        ctx,
        "• Candidate embedding decrypt caches DEK in MemoryCrypto._cache (300s TTL)",
        1040,
        838,
        size=16.5,
        color=WHITE,
        family="DejaVu Sans",
        alpha=a4,
    )
    draw_text(
        ctx,
        "• Opening Top-K payloads hits cached DEK → 0 extra Cloud KMS RPCs!",
        1040,
        872,
        size=16.5,
        color=GOLD_C,
        family="DejaVu Sans",
        bold=True,
        alpha=a4,
    )
    draw_text(
        ctx,
        "• Indirect injection in payload → quarantined=True (E_MEMORY_QUARANTINED)",
        1040,
        906,
        size=16.5,
        color=TEAL_C,
        family="DejaVu Sans",
        alpha=a4,
    )


def render_chapter_4(ctx: cairo.Context, local_t: float) -> None:
    """Chapter 4: Loop-Local AlloyDB FORCE RLS Pool & Posture Verification (45s - 60s)."""
    a1 = sub_alpha(local_t, 0.0, 2.5)
    a2 = sub_alpha(local_t, 2.5, 6.5)
    a3 = sub_alpha(local_t, 6.5, 10.5)
    a4 = sub_alpha(local_t, 10.5, 14.0)

    # Top Left: Per-Event-Loop WeakKeyDictionary Isolation
    draw_rounded_rect(ctx, 70, 145, 880, 825, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.90 * a1)
    ctx.fill_preserve()
    ctx.set_source_rgba(TEAL_C[0], TEAL_C[1], TEAL_C[2], 0.5 * a1)
    ctx.set_line_width(2.0)
    ctx.stroke()

    draw_text(
        ctx,
        "Hop 5: Loop-Local RLSDatabasePool (PR #30 & #35)",
        105,
        195,
        size=24,
        color=TEAL_C,
        bold=True,
        alpha=a1,
    )
    draw_text(
        ctx,
        "Why keying on id(loop) fails: GC reuses memory addresses for new loops!",
        105,
        235,
        size=17.5,
        color=RED_C,
        family="DejaVu Sans",
        bold=True,
        alpha=a1,
    )
    draw_text(
        ctx,
        "_pools_by_loop: WeakKeyDictionary[AbstractEventLoop, asyncpg.Pool]",
        105,
        275,
        size=18.5,
        color=GOLD_C,
        family="DejaVu Sans Mono",
        alpha=a1,
    )

    # Draw 3 Event Loop nodes mapping to isolated asyncpg.Pool instances
    loops = [
        ("Main Uvicorn uvloop", "asyncpg.Pool #1 (Active)", GREEN_C, False),
        ("Worker Thread Loop A", "asyncpg.Pool #2 (Active)", BLUE_C, False),
        (
            "Ephemeral Test Loop B",
            "loop.close() → pool.terminate() + pop",
            RED_C,
            True,
        ),
    ]
    for idx, (l_name, p_name, col, is_closed) in enumerate(loops):
        ly = 335 + idx * 140
        draw_rounded_rect(ctx, 105, ly, 320, 96, r=12)
        ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.92 * a2)
        ctx.fill_preserve()
        ctx.set_source_rgba(col[0], col[1], col[2], 0.75 * a2)
        ctx.stroke()
        draw_text(
            ctx,
            l_name,
            265,
            ly + 45,
            size=17,
            color=WHITE,
            family="DejaVu Sans",
            bold=True,
            align="center",
            alpha=a2,
        )
        draw_text(
            ctx,
            "asyncio / uvloop",
            265,
            ly + 74,
            size=14,
            color=MUTED,
            family="DejaVu Sans Mono",
            align="center",
            alpha=a2,
        )

        draw_arrow(
            ctx,
            430,
            ly + 48,
            505,
            ly + 48,
            col,
            alpha=a2,
            progress=a2,
            width=3.0,
        )

        draw_rounded_rect(ctx, 515, ly, 395, 96, r=12)
        ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.92 * a2)
        ctx.fill_preserve()
        ctx.set_source_rgba(col[0], col[1], col[2], 0.75 * a2)
        ctx.stroke()
        draw_text(
            ctx,
            p_name,
            712,
            ly + 45,
            size=16.5,
            color=col,
            family="DejaVu Sans Mono",
            bold=True,
            align="center",
            alpha=a2,
        )
        sub_label = (
            "Breaks pool._loop strong ref cycle!"
            if is_closed
            else "Per-loop asyncio.Lock init guard"
        )
        draw_text(
            ctx,
            sub_label,
            712,
            ly + 74,
            size=14.5,
            color=WHITE,
            family="DejaVu Sans",
            align="center",
            alpha=a2,
        )

    # Bottom-left fail-closed contract box
    draw_rounded_rect(ctx, 105, 765, 805, 175, r=14)
    ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.92 * a3)
    ctx.fill_preserve()
    ctx.set_source_rgba(GOLD_C[0], GOLD_C[1], GOLD_C[2], 0.65 * a3)
    ctx.stroke()
    draw_text(
        ctx,
        "Fail-Closed Pool Lifecycle (Zero Demo Fallback):",
        130,
        805,
        size=19,
        color=GOLD_C,
        family="DejaVu Sans",
        bold=True,
        alpha=a3,
    )
    draw_text(
        ctx,
        "• await db_pool.close() closes ONLY the current running loop's pool",
        130,
        842,
        size=16.5,
        color=WHITE,
        family="DejaVu Sans",
        alpha=a3,
    )
    draw_text(
        ctx,
        "• Subsequent queries raise RuntimeError('E_DB_POOL_CLOSED') — never demo rows",
        130,
        876,
        size=16.5,
        color=GREEN_C,
        family="DejaVu Sans Mono",
        alpha=a3,
    )
    draw_text(
        ctx,
        "• Verified across 20 uvloop churn cycles + real asyncpg.create_pool",
        130,
        910,
        size=16.5,
        color=TEAL_C,
        family="DejaVu Sans",
        alpha=a3,
    )

    # Right Panel: Live PostgreSQL Catalog RLS Posture Verification (PR #33)
    draw_rounded_rect(ctx, 980, 145, 870, 825, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.90 * a2)
    ctx.fill_preserve()
    ctx.set_source_rgba(GREEN_C[0], GREEN_C[1], GREEN_C[2], 0.5 * a2)
    ctx.stroke()

    draw_text(
        ctx,
        "Startup Gate: verify_live_rls_posture() (PR #33)",
        1015,
        195,
        size=24,
        color=GREEN_C,
        bold=True,
        alpha=a2,
    )
    draw_text(
        ctx,
        "Wired into scripts/init_postgres_rls.py AND FastAPI _gateway_lifespan:",
        1015,
        235,
        size=18,
        color=MUTED,
        family="DejaVu Sans",
        alpha=a2,
    )

    # SQL Catalog Equations
    draw_rounded_rect(ctx, 1015, 265, 800, 250, r=14)
    ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.95 * a3)
    ctx.fill_preserve()
    ctx.set_source_rgba(BLUE_C[0], BLUE_C[1], BLUE_C[2], 0.6 * a3)
    ctx.stroke()

    sql_lines = [
        "-- 1. Verify active role cannot bypass RLS (pg_catalog.pg_roles)",
        "SELECT rolname, rolsuper, rolbypassrls FROM pg_catalog.pg_roles",
        " WHERE rolname = current_user;  -- Must be cymbal_mcp_app (false, false)",
        "",
        "-- 2. Schema-qualified table check (pg_class JOIN pg_namespace)",
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity",
        "  FROM pg_catalog.pg_class c",
        "  JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace",
        " WHERE n.nspname = 'public' AND c.relname = ANY($1::text[]);",
    ]
    for idx, line in enumerate(sql_lines):
        col = TEAL_C if line.startswith("--") else WHITE
        draw_text(
            ctx,
            line,
            1035,
            302 + idx * 24,
            size=15.5,
            color=col,
            family="DejaVu Sans Mono",
            alpha=a3,
        )

    # 4 Binary Gates Checked at Startup
    gates = [
        (
            "rolsuper == False",
            "Rejects postgres superuser DSN with E_RLS_POSTURE_VIOLATION",
        ),
        (
            "rolbypassrls == False",
            "Rejects any role granted BYPASSRLS privilege",
        ),
        (
            "relrowsecurity == True",
            "Verifies ENABLE ROW LEVEL SECURITY on public tables",
        ),
        (
            "relforcerowsecurity == True",
            "Verifies FORCE ROW LEVEL SECURITY on public tables",
        ),
    ]
    for idx, (g_expr, g_desc) in enumerate(gates):
        gy = 545 + idx * 95
        draw_rounded_rect(ctx, 1015, gy, 800, 78, r=12)
        ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.92 * a4)
        ctx.fill_preserve()
        ctx.set_source_rgba(GREEN_C[0], GREEN_C[1], GREEN_C[2], 0.7 * a4)
        ctx.stroke()
        draw_text(
            ctx,
            f"✓  {g_expr}",
            1040,
            gy + 34,
            size=19,
            color=GREEN_C,
            family="DejaVu Sans Mono",
            bold=True,
            alpha=a4,
        )
        draw_text(
            ctx,
            g_desc,
            1040,
            gy + 62,
            size=16,
            color=WHITE,
            family="DejaVu Sans",
            alpha=a4,
        )


def render_chapter_5(ctx: cairo.Context, local_t: float) -> None:
    """Chapter 5: Atomic Tenant Offboarding & Generation-Guarded Eviction (60s - 75s)."""
    a1 = sub_alpha(local_t, 0.0, 2.5)
    a2 = sub_alpha(local_t, 2.5, 6.5)
    a3 = sub_alpha(local_t, 6.5, 11.0)
    a4 = sub_alpha(local_t, 11.0, 14.0)

    # Top Hub: offboard_tenant(tenant_id) + WeakSet Eviction Registry
    draw_rounded_rect(ctx, 70, 145, 1780, 410, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.92 * a1)
    ctx.fill_preserve()
    ctx.set_source_rgba(RED_C[0], RED_C[1], RED_C[2], 0.5 * a1)
    ctx.set_line_width(2.0)
    ctx.stroke()

    draw_text(
        ctx,
        "Atomic Single-Call Tenant Offboarding: offboard_tenant(tenant_id) (PR #33)",
        105,
        195,
        size=25,
        color=RED_C,
        bold=True,
        alpha=a1,
    )
    draw_text(
        ctx,
        "Removes tenant from TENANT_DIRECTORY + iterates over _TENANT_EVICTION_TARGETS (weakref.WeakSet) to purge all 5 caches:",
        105,
        232,
        size=18,
        color=MUTED,
        family="DejaVu Sans",
        alpha=a1,
    )

    targets = [
        (
            "1. MemoryCrypto",
            "Evicts unwrapped 256-bit DEKs",
            "evicted_memory_deks",
            PURPLE_C,
        ),
        (
            "2. CredentialBroker",
            "Evicts ct-<sha256> SA tokens",
            "evicted_broker_tokens",
            BLUE_C,
        ),
        (
            "3. KMSVerifyCache",
            "Evicts 60s KMS probe receipts",
            "evicted_kms_verify_entries",
            TEAL_C,
        ),
        (
            "4. AuthManager3LOVault",
            "Evicts Jira / SNOW 3LO tokens",
            "evicted_3lo_tokens",
            GOLD_C,
        ),
        (
            "5. TokenBucketBulkhead",
            "Purges RPM & session turns",
            "evicted_bulkhead_state",
            GREEN_C,
        ),
    ]
    for idx, (t_name, t_desc, t_key, col) in enumerate(targets):
        tx = 105 + idx * 344
        ty = 265
        draw_rounded_rect(ctx, tx, ty, 326, 255, r=14)
        ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.92 * a2)
        ctx.fill_preserve()
        ctx.set_source_rgba(col[0], col[1], col[2], 0.75 * a2)
        ctx.stroke()

        draw_text(
            ctx,
            t_name,
            tx + 18,
            ty + 42,
            size=19,
            color=col,
            family="DejaVu Sans",
            bold=True,
            alpha=a2,
        )
        draw_text(
            ctx,
            t_desc,
            tx + 18,
            ty + 80,
            size=15,
            color=WHITE,
            family="DejaVu Sans",
            alpha=a2,
        )
        draw_rounded_rect(ctx, tx + 16, ty + 110, 294, 52, r=8)
        ctx.set_source_rgba(RED_C[0], RED_C[1], RED_C[2], 0.16 * a2)
        ctx.fill()
        draw_text(
            ctx,
            ".evict_tenant(tenant_id)",
            tx + 163,
            ty + 142,
            size=15.5,
            color=RED_C,
            family="DejaVu Sans Mono",
            bold=True,
            align="center",
            alpha=a2,
        )
        draw_text(
            ctx,
            f"→ {t_key}",
            tx + 18,
            ty + 210,
            size=14.5,
            color=GREEN_C,
            family="DejaVu Sans Mono",
            alpha=a2,
        )

    # Bottom Panel: In-Flight TOCTOU Race Guard (_eviction_generation)
    draw_rounded_rect(ctx, 70, 585, 1780, 385, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.92 * a3)
    ctx.fill_preserve()
    ctx.set_source_rgba(GOLD_C[0], GOLD_C[1], GOLD_C[2], 0.55 * a3)
    ctx.stroke()

    draw_text(
        ctx,
        "Closing the In-Flight Offboarding TOCTOU Window via _eviction_generation[tenant_id]",
        105,
        635,
        size=24,
        color=GOLD_C,
        bold=True,
        alpha=a3,
    )
    draw_text(
        ctx,
        "What if Thread A passes the policy check and starts a slow Cloud KMS unwrap or IAM mint, and Thread B offboards the tenant before Thread A finishes?",
        105,
        672,
        size=17.5,
        color=WHITE,
        family="DejaVu Sans",
        alpha=a3,
    )

    # Timeline steps
    steps = [
        (
            "t = 0 ms (Thread A)",
            "Snapshots gen_before = _eviction_generation[t] (= 0)",
            "Starts slow KMS unwrap() / backend.mint() outside lock",
            BLUE_C,
        ),
        (
            "t = 12 ms (Thread B)",
            "Calls offboard_tenant(t) → evict_tenant(t)",
            "Increments _eviction_generation[t] = 1 & clears _cache",
            RED_C,
        ),
        (
            "t = 25 ms (Thread A)",
            "Acquires _lock; checks gen_now (1) != gen_before (0)",
            "Drops DEK/token & raises E_TENANT_OFFBOARDED_DURING_*!",
            GREEN_C,
        ),
    ]
    for idx, (s_time, s_line1, s_line2, col) in enumerate(steps):
        sx = 105 + idx * 580
        sy = 710
        draw_rounded_rect(ctx, sx, sy, 545, 220, r=14)
        ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.94 * a4)
        ctx.fill_preserve()
        ctx.set_source_rgba(col[0], col[1], col[2], 0.75 * a4)
        ctx.set_line_width(2.5)
        ctx.stroke()

        draw_text(
            ctx,
            s_time,
            sx + 24,
            sy + 45,
            size=20,
            color=col,
            family="DejaVu Sans Mono",
            bold=True,
            alpha=a4,
        )
        draw_text(
            ctx,
            s_line1,
            sx + 22,
            sy + 100,
            size=15.5,
            color=WHITE,
            family="DejaVu Sans",
            alpha=a4,
        )
        draw_text(
            ctx,
            s_line2,
            sx + 22,
            sy + 145,
            size=14.0,
            color=GOLD_C if idx == 2 else MUTED,
            family="DejaVu Sans Mono",
            bold=(idx == 2),
            alpha=a4,
        )
        if idx < 2:
            draw_arrow(
                ctx,
                sx + 548,
                sy + 110,
                sx + 575,
                sy + 110,
                col,
                alpha=a4,
                progress=a4,
                width=3.5,
            )


def render_chapter_6(ctx: cairo.Context, local_t: float) -> None:
    """Chapter 6: Statistical AI Engineering Evals & 55/55 Verification Waterfall (75s - 90s)."""
    a1 = sub_alpha(local_t, 0.0, 2.5)
    a2 = sub_alpha(local_t, 2.5, 6.5)
    a3 = sub_alpha(local_t, 6.5, 10.5)
    a4 = sub_alpha(local_t, 10.5, 14.0)

    # Left Panel: 5-Stage Guardrail Ablation Waterfall (18/55 -> 55/55)
    draw_rounded_rect(ctx, 70, 145, 880, 560, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.90 * a1)
    ctx.fill_preserve()
    ctx.set_source_rgba(BLUE_C[0], BLUE_C[1], BLUE_C[2], 0.5 * a1)
    ctx.set_line_width(2.0)
    ctx.stroke()

    draw_text(
        ctx,
        "5-Layer Guardrail Ablation Waterfall (N = 55 Golden Suite)",
        105,
        195,
        size=23,
        color=BLUE_C,
        bold=True,
        alpha=a1,
    )

    bars = [
        ("Stage 0: Raw Model (No Gates)", 18, 55, 32.7, RED_C),
        ("Stage 1: + Hop 0/1 DPoP & Bulkhead", 29, 55, 52.7, GOLD_C),
        ("Stage 2: + Hop 2 Registry & Model Armor", 41, 55, 74.5, BLUE_C),
        ("Stage 3: + Hop 3/5 KMS CMEK & FORCE RLS", 48, 55, 87.3, TEAL_C),
        ("Stage 4: + Hop 4 DLP, NLC & Full Stack", 55, 55, 100.0, GREEN_C),
    ]
    for idx, (label, passed, total, pct, col) in enumerate(bars):
        by = 240 + idx * 88
        draw_text(
            ctx,
            label,
            105,
            by + 22,
            size=16.5,
            color=WHITE,
            family="DejaVu Sans",
            bold=(idx == 4),
            alpha=a2,
        )
        max_w = 560.0
        bw = max_w * (pct / 100.0) * a2
        draw_rounded_rect(ctx, 105, by + 32, max(12, bw), 34, r=8)
        ctx.set_source_rgba(col[0], col[1], col[2], 0.80 * a2)
        ctx.fill()
        draw_text(
            ctx,
            f"{passed}/{total} ({pct:.1f}%)",
            118 + bw,
            by + 55,
            size=17,
            color=col,
            family="DejaVu Sans Mono",
            bold=True,
            alpha=a2,
        )

    # Right Panel: Calibrated Judge & Horvitz-Thompson Smart Sampler Math
    draw_rounded_rect(ctx, 980, 145, 870, 560, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.90 * a2)
    ctx.fill_preserve()
    ctx.set_source_rgba(GOLD_C[0], GOLD_C[1], GOLD_C[2], 0.5 * a2)
    ctx.stroke()

    draw_text(
        ctx,
        "Statistical Evaluation & Online Sampling Mathematics",
        1015,
        195,
        size=23,
        color=GOLD_C,
        bold=True,
        alpha=a2,
    )

    math_cards = [
        (
            "1. Sub-Millisecond Deterministic Verifier (< 1 ms, $0 LLM Cost)",
            "Regex + AST extraction of INC-*, FINVAULT-*, metrics, units & negation clauses",
            TEAL_C,
        ),
        (
            "2. Rogan-Gladen Prevalence-Corrected Binary Judge (κ = 0.892)",
            "θ̂_RG = clip_[0,1]( (p̂_obs + q_0 − 1) / (q_1 + q_0 − 1) )  •  Position-Swapped (A,B)/(B,A)",
            BLUE_C,
        ),
        (
            "3. Paired McNemar Discordant Significance Test",
            "χ² = (|b − c| − 1)² / (b + c)  verifies guardrail gains across prompt revisions",
            PURPLE_C,
        ),
        (
            "4. Horvitz-Thompson Inverse-Probability Smart Sampler (-97.5% Judge Cost)",
            "μ̂_HT = (1/N) Σ (y_i / π_i),  π_anomaly = 1.0,  π_clean = 0.025  ⇒  Net -$35.00/day",
            GREEN_C,
        ),
    ]
    for idx, (m_title, m_eq, col) in enumerate(math_cards):
        my = 230 + idx * 112
        draw_rounded_rect(ctx, 1015, my, 800, 96, r=12)
        ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.92 * a3)
        ctx.fill_preserve()
        ctx.set_source_rgba(col[0], col[1], col[2], 0.65 * a3)
        ctx.stroke()
        draw_text(
            ctx,
            m_title,
            1038,
            my + 36,
            size=17.5,
            color=col,
            family="DejaVu Sans",
            bold=True,
            alpha=a3,
        )
        draw_text(
            ctx,
            m_eq,
            1038,
            my + 72,
            size=16.5,
            color=WHITE,
            family="DejaVu Serif",
            italic=True,
            alpha=a3,
        )

    # Bottom Full-Width Final Scorecard Banner
    draw_rounded_rect(ctx, 70, 730, 1780, 240, r=18)
    ctx.set_source_rgba(BG_PANEL[0], BG_PANEL[1], BG_PANEL[2], 0.95 * a4)
    ctx.fill_preserve()
    ctx.set_source_rgba(GREEN_C[0], GREEN_C[1], GREEN_C[2], 0.8 * a4)
    ctx.set_line_width(2.5)
    ctx.stroke()

    draw_text(
        ctx,
        "Workstream 2 (Pattern A: Governed Pooled Multi-Tenancy) — Production Verification Gate",
        960,
        778,
        size=24,
        color=WHITE,
        family="DejaVu Serif",
        bold=True,
        align="center",
        alpha=a4,
    )

    badges = [
        ("514 / 514", "Pytest Suite (0 Mocks)", GREEN_C),
        ("55 / 55", "Golden Eval Benchmark", BLUE_C),
        ("10 / 10", "Breach Vectors Blocked", GOLD_C),
        ("35 / 35", "JSONL Batch Audit", TEAL_C),
        ("12 / 12", "5-Act Live Demo Checks", PURPLE_C),
        ("0 Leaks", "Ruff + Repo Sanitized", GREEN_C),
    ]
    for idx, (b_num, b_lbl, col) in enumerate(badges):
        bx = 105 + idx * 288
        by = 805
        draw_rounded_rect(ctx, bx, by, 268, 135, r=14)
        ctx.set_source_rgba(BG_DARK[0], BG_DARK[1], BG_DARK[2], 0.95 * a4)
        ctx.fill_preserve()
        ctx.set_source_rgba(col[0], col[1], col[2], 0.85 * a4)
        ctx.stroke()
        draw_text(
            ctx,
            b_num,
            bx + 134,
            by + 62,
            size=30,
            color=col,
            family="DejaVu Sans Mono",
            bold=True,
            align="center",
            alpha=a4,
        )
        draw_text(
            ctx,
            b_lbl,
            bx + 134,
            by + 105,
            size=15.5,
            color=WHITE,
            family="DejaVu Sans",
            align="center",
            alpha=a4,
        )


def generate_ambient_audio_wav(
    wav_path: Path, duration_seconds: int = DURATION_SECONDS
) -> None:
    """Synthesizes a warm, unobtrusive 3Blue1Brown-style ambient harmonic chord progression."""
    sample_rate = 22050
    num_samples = sample_rate * duration_seconds
    # Gentle warm C-major-9 / A-minor-9 ambient pad frequencies
    chords = [
        (130.81, 196.00, 246.94, 293.66),  # Cmaj9
        (110.00, 164.81, 220.00, 261.63),  # Am7
        (174.61, 220.00, 261.63, 329.63),  # Fmaj7
        (196.00, 246.94, 293.66, 392.00),  # G6
        (130.81, 164.81, 196.00, 246.94),  # Cmaj7
        (130.81, 196.00, 261.63, 329.63),  # C Octave resolution
    ]
    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        chunk = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            chapter_idx = min(5, int(t // 15.0))
            freqs = chords[chapter_idx]
            local_t = t % 15.0
            env = min(1.0, local_t / 1.5) * min(1.0, (15.0 - local_t) / 1.5)
            val = 0.0
            for f in freqs:
                val += math.sin(2.0 * math.pi * f * t) * 0.22
                val += math.sin(2.0 * math.pi * (f * 2.0) * t) * 0.04
            sample = int(max(-1.0, min(1.0, val * env * 0.18)) * 32767)
            chunk.extend(struct.pack("<h", sample))
        wav_file.writeframes(bytes(chunk))


def render_video(output_mp4: Path, preview_dir: Path | None = None) -> None:
    """Renders all 2,700 frames at 1920x1080 and encodes to H.264 MP4 via `ffmpeg`."""
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    if preview_dir is not None:
        preview_dir.mkdir(parents=True, exist_ok=True)

    chapters = [
        (
            1,
            "The Multi-Tenant Cost & Isolation Paradox",
            "250 Silos ($195k/mo) vs. Pattern A Governed Pool ($2,125/mo, -84.71% Input Token COGS)",
            render_chapter_1,
        ),
        (
            2,
            "Hop 0/1: Sender-Constrained DPoP & 3-Key Rolling Ring",
            "RFC 9449 Proof-of-Possession + Zero-Downtime (active_kid, previous_kid, next_kid) Rollout",
            render_chapter_2,
        ),
        (
            3,
            "Hop 3: KMS v2 Envelope Encryption & Ciphertext-Only RAG",
            "Per-Record 256-bit DEKs, Sealed Embedding Vectors & Zero-Extra-Unwrap Top-K Retrieval",
            render_chapter_3,
        ),
        (
            4,
            "Hop 5: Loop-Local AlloyDB FORCE RLS & Catalog Posture Gate",
            "WeakKeyDictionary Per-Loop Pools + Startup verify_live_rls_posture() Enforcement",
            render_chapter_4,
        ),
        (
            5,
            "Atomic Tenant Offboarding & Generation-Guarded Eviction",
            "WeakSet Eviction Target Registry + _eviction_generation In-Flight TOCTOU Race Guard",
            render_chapter_5,
        ),
        (
            6,
            "Statistical AI Engineering Evals & 55/55 Proof Waterfall",
            "Deterministic Verifier (<1ms), Rogan-Gladen Judge (κ=0.892) & Horvitz-Thompson Sampler",
            render_chapter_6,
        ),
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        wav_path = Path(tmp_dir) / "ambient_track.wav"
        generate_ambient_audio_wav(wav_path)

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgra",
            "-s",
            f"{WIDTH}x{HEIGHT}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-i",
            str(wav_path),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_mp4),
        ]

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
        ctx = cairo.Context(surface)

        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        assert proc.stdin is not None

        for frame_idx in range(TOTAL_FRAMES):
            t_global = frame_idx / FPS
            chapter_slot = min(5, int(t_global // 15.0))
            local_t = t_global - (chapter_slot * 15.0)
            c_num, c_title, c_sub, render_fn = chapters[chapter_slot]

            draw_number_plane(ctx, t_global)
            draw_header_and_timeline(ctx, c_num, c_title, c_sub, t_global)
            render_fn(ctx, local_t)

            surface.flush()
            proc.stdin.write(surface.get_data())

            # Save a keyframe snapshot at local_t == 12.5s of each chapter for visual verification
            if preview_dir is not None and frame_idx % 450 == 375:
                surface.write_to_png(str(preview_dir / f"chapter_{c_num}.png"))

        proc.stdin.close()
        stderr_bytes = proc.stderr.read() if proc.stderr is not None else b""
        return_code = proc.wait()
        if return_code != 0:
            raise RuntimeError(
                f"ffmpeg failed ({return_code}): {stderr_bytes.decode('utf-8', 'ignore')}"
            )


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    mp4_out = repo_root / "docs" / "assets" / "cymbal_3b1b_walkthrough.mp4"
    preview_env = os.environ.get("CYMBAL_3B1B_PREVIEW_DIR")
    preview_out = Path(preview_env) if preview_env else None
    render_video(mp4_out, preview_dir=preview_out)
    print(
        f"Rendered 3B1B video: {mp4_out} ({mp4_out.stat().st_size / 1024:.1f} KB)"
    )
