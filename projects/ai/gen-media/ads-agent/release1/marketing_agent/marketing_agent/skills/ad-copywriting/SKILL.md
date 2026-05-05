<!-- markdownlint-disable -->
---
name: ad-copywriting
description: "Google Ads copywriting expertise. Covers Responsive Search Ad (RSA) best practices, headline formulas, description frameworks, and character limits. Load this skill when generating text ads, headlines, or ad copy."
---

# Ad Copywriting Skill

## Google Ads Responsive Search Ad (RSA) Format

You MUST output ads in this exact JSON structure:
```json
{"headlines": ["H1", "H2", "H3"], "descriptions": ["D1", "D2", "D3"]}
```

### Character Limits (STRICT)
- Headlines: **max 30 characters** each
- Descriptions: **max 90 characters** each

### Headline Rules (3 required)
1. **Headline 1 — Primary Hook**: Lead with the strongest benefit or the brand name. This headline shows most often.
2. **Headline 2 — Value Proposition**: Differentiate from competitors. What makes this product unique?
3. **Headline 3 — Call-to-Action or Social Proof**: Drive urgency or trust ("Shop Now", "Award-Winning", "Free Shipping").

### Headline Formulas That Convert
- `[Benefit] + [Product]` → "Ultra-Clear 4K Security"
- `[Brand] + [Category]` → "SecureVision Smart Cameras"
- `[Number] + [Benefit]` → "24/7 AI-Powered Protection"
- `[Question]` → "Need Smarter Security?"
- `[Action] + [Benefit]` → "See Everything, Miss Nothing"

### Description Rules (3 required)
1. **Description 1 — Expand the Hook**: Elaborate on the primary benefit with specifics.
2. **Description 2 — Features + Benefits**: 2-3 key features tied to outcomes.
3. **Description 3 — CTA + Trust Signal**: Clear action + reason to act now.

### Description Frameworks
- **PAS (Problem-Agitate-Solve)**: State problem → amplify pain → present solution
- **BAB (Before-After-Bridge)**: Current state → desired state → product as bridge
- **4U (Urgent, Unique, Ultra-specific, Useful)**: Every description should hit at least 2

### Quality Checklist
- [ ] Brand name appears in at least 1 headline
- [ ] No headline exceeds 30 chars
- [ ] No description exceeds 90 chars
- [ ] Each headline is distinct (no repetition)
- [ ] At least 1 CTA in descriptions
- [ ] No invented product features
- [ ] Tone matches target audience segment
- [ ] If persona is set, copy resonates with that customer type

Read `references/headline-examples.md` for proven headline patterns by industry.
