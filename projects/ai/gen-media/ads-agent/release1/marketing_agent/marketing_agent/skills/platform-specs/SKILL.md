---
name: platform-specs
description: "Ad platform specifications and best practices. Covers Google Ads, YouTube, Instagram, TikTok, and Meta ad formats, dimensions, character limits, and optimization tips. Load this skill when creating platform-specific content or recommending campaign settings."
---
<!-- markdownlint-disable -->

# Platform Specs Skill

## Google Ads — Responsive Search Ads (RSA)

### Format
```json
{"headlines": ["H1", "H2", "H3"], "descriptions": ["D1", "D2", "D3"]}
```

### Limits
- Headlines: 3-15 headlines, **max 30 chars each**
- Descriptions: 2-4 descriptions, **max 90 chars each**
- Display URL paths: 2 paths, max 15 chars each

### Best Practices
- Pin H1 to position 1 (brand/primary message)
- Use keyword insertion where appropriate
- Include at least 1 CTA ("Shop Now", "Learn More", "Get Started")
- Avoid excessive capitalization or punctuation

## Google Ads — Display Ads

### Image Sizes
- Landscape: 1200x628 (recommended), 1200x900
- Square: 1200x1200
- Portrait: 900x1200 (mobile)

### Rules
- Text overlay: max 20% of image area
- Logo: clearly visible, undistorted
- High-quality imagery (no blurry/pixelated)
- File size: max 5MB, PNG or JPG

## YouTube — Video Ads

### Formats
- Bumper ad: 6 seconds (non-skippable)
- In-stream: 15-30 seconds (skippable after 5s)
- Shorts: 15-60 seconds (vertical 9:16)

### Best Practices
- Hook in first 5 seconds (before skip button)
- Brand within first 5 seconds
- Clear CTA in final 3 seconds
- Audio essential (but design for sound-off too)

## Instagram / Meta

### Image Ad Sizes
- Feed: 1080x1080 (square) or 1080x1350 (portrait)
- Stories/Reels: 1080x1920 (9:16)

### Text Limits
- Primary text: 125 chars (visible without "more")
- Headline: 40 chars
- Description: 30 chars

## TikTok

### Video Specs
- Aspect ratio: 9:16 (vertical mandatory)
- Duration: 15-60 seconds (sweet spot: 21-34s)
- Resolution: 1080x1920 minimum

### Best Practices
- Native feel (not overly polished)
- Sound-on design
- Hook in first 1-2 seconds
- Trending audio when possible

## Campaign Settings Recommendations

### Budget Allocation (by objective)
- Awareness: 60% video, 30% display, 10% search
- Consideration: 40% video, 30% search, 30% display
- Conversion: 50% search, 30% display, 20% video

### Bidding Strategy
- New campaigns: Start with maximize clicks, shift to target CPA after 50+ conversions
- Brand awareness: target CPM
- App installs: target CPI

Read `references/platform-dimensions.md` for the complete dimensions reference.
