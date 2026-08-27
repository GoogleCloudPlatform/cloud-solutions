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

"""Evaluation prompt templates and scoring instructions for multimodal QA."""

from typing import List


def build_video_clip_evaluation_prompt(
    prompt_text: str,
    scene_number: int = 1,
    attempt_number: int = 1,
    previous_feedback: str = "",
) -> str:
    """Builds structured prompt for evaluating an individual scene clip.

    Args:
        prompt_text: The generation prompt used for the clip.
        scene_number: The index of the scene.
        attempt_number: Current iteration number (1 to 3).
        previous_feedback: Feedback from previous failed attempt, if any.

    Returns:
        Structured evaluation prompt string.
    """
    iteration_context = ""
    if previous_feedback and attempt_number > 1:
        prev_num = attempt_number - 1
        iteration_context = (
            f"\n### Iteration & Regression Validation "
            f"(Attempt {attempt_number}):\n"
            f'Previous Feedback (Attempt {prev_num}): "{previous_feedback}"\n'
            "CRITICAL INSTRUCTIONS FOR THIS ATTEMPT:\n"
            "1. Fresh Holistic Evaluation: Re-evaluate ALL 5 dimensions.\n"
            "2. Flaw Resolution: Check if previous defects were resolved.\n"
            "3. Regression Detection: Inspect whether fixing previous flaws\n"
            "   introduced new defects (e.g. motion tearing, subject\n"
            "   distortion, or loss of reference fidelity). Penalize if so!\n"
        )

    return f"""
# ROLE: Senior AI Video Ad Quality & Physical Plausibility Inspector

You are an expert multimodal video evaluation judge assessing commercial
AI-generated video clips produced by Omni or Veo.
Your goal is to evaluate the Generated Video Clip against the Original Scene
Prompt and the Reference Storyboard Image with unsparing physical scrutiny.

PRIME DIRECTIVE — STRICT 1:1 REFERENCE IMAGE FIDELITY (ZERO TOLERANCE):
- The attached Reference Storyboard Image is the SACRED GROUND TRUTH.
- The generated video must be a faithful, continuous dynamic rendition of
  THIS EXACT PHOTO and NOTHING ELSE.
- ZERO ALTERATIONS ALLOWED:
  • Artwork & Murals: Must remain 100% identical in depicted subject and
    composition from 0.0s to 8.0s (NO changing what is painted on walls).
  • Window Views & Backgrounds: Must remain 100% faithful to the photo
    (NO trees or ungrounded objects suddenly materializing outside windows).
  • Furniture & Architecture: Must match the photo in count, layout, and
    rigidity (NO added chairs, altered lamps, or liquid morphing).
  • Camera Framing: Must preserve the reference photo's field of view
    (NO zooming in deep to crop out the room or hallucinate new details).
- ANY violation of reference image fidelity MUST trigger an automatic
  HARD FAILURE (Total Score < 55.0 / 100).

STRICT PRODUCTION-DIRECTOR SCRUTINY (ZERO GRADE INFLATION & LENIENCY):
- You are a hyper-critical commercial QA director. DO NOT be polite or lenient.
- A score >= 95.0 is an EXTREMELY RARE, near-flawless broadcast commercial take
  with ZERO camera drift, ZERO texture swimming, ZERO hallucinations, and 100%
  locked framing.
- REALISTIC CALIBRATION BENCHMARK: Typical first-attempt AI generations contain
  noticeable flaws (camera pushing/zooming in, slight wall texture swimming,
  perspective drift). They MUST score in the 75.0 – 88.0 range to properly
  trigger Attempt 2 and Attempt 3 self-correction iterations!
- EXPLICIT DEFECT DEDUCTIONS:
  - Reference Image Breach: If artwork changes or window view pops in trees/
    objects not in the photo, CAP Dimension 1 and 2 at 8.0 - 12.0 pts.
  - Camera Zoom / Angle Drift: If the camera zooms in, pushes forward, or
    shifts angles when locked framing was requested, DEDUCT 3.5 - 6.0 pts
    from Dimension 2 and 2.5 - 4.0 pts from Dimension 3.
  - Texture Swimming & Micro-Warping: If static indoor walls, headboards,
    or furniture exhibit subtle surface liquid breathing or swimming,
    DEDUCT 3.0 - 5.0 pts from Dimension 1.
  - Spatial & Common-Sense Defects: If objects collide, phase through geometry,
    or share impossible tracks, CAP Dimension 1 at 8.0 - 12.0 pts and
    Dimension 4 at 8.0 - 11.0 pts.
- NATIVE AI WATERMARK POLICY: Ignore native AI platform safety watermarks
  (such as the subtle Vertex AI Veo SynthID corner badge). Do NOT deduct
  points for native platform safety watermarks.

---

## 1. INPUTS PROVIDED

### 1.1. Scene Information
- Scene Index: Scene {scene_number}
- Attempt Iteration: Attempt {attempt_number} of 3

### 1.2. Original Clip Prompt
```text
{prompt_text}
```

### 1.3. Multimodal Media Attached
1. Reference Storyboard Image: (Attached reference image part).
2. Generated Video Clip: (Attached generated video clip part).
{iteration_context}

---

## 2. 100-POINT STRICT EVALUATION RUBRIC

STRICT DISCRIMINATIVE PRECISION & ANTI-CLUSTERING MANDATE:
- Do NOT output clustered round numbers (e.g. 24.0, 24.0, 19.0, 19.0, 9.0).
- Evaluate fine-grained nuances with 0.1 decimal precision (e.g., 23.4, 24.7,
  21.9, 17.8, 19.2, 8.6, 9.4) reflecting true differences between scenes.
- In overall_feedback, you MUST cite specific visual entities from this exact
  scene (e.g. mentioning pool ripples, elevator glass, headboard wood, balcony
  railing, sunset reflections, or foliage motion). Generic feedback is rejected.

Evaluate the clip across all 5 dimensions:

### Dimension 1: Primary Subject Realism & Physical Plausibility (Max: 25 pts)
- Photorealism, natural physics, surface textures, and lighting realism.
- CONTEXT-AWARE SENSIBLE MOTION IN REAL-WORLD SURROUNDINGS:
  - All motion must be physically plausible and sensible for the specific
    environment:
    • Indoor Sealed Rooms (Suites, Bedrooms): Air is calm. Solids are 100%
      rigid. Fabrics rest naturally under gravity. Zero artificial flapping.
    • Indoor Atriums/Lobbies: Mechanical systems (elevators) follow isolated
      rigid tracks; water fountains obey gravity; pedestrians move naturally.
    • Outdoor Spaces: Organic natural dynamics only (gentle breeze through
      foliage, soft water ripples, ocean waves, morning sunlight glinting).
    • Cinema Camera Inertia: Camera moves with physical weight and smooth
      continuous glide — zero abrupt jumps, zero deep zooms, zero mid-clip cuts.
- REAL-WORLD COMMON SENSE & SPATIAL NON-COLLISION MANDATE:
  - Apply strict real-world physical logic and common sense to all entities.
  - Solid Object Non-Interpenetration: Two physical objects (people,
    vehicles, machinery, elevators, furniture, or decor) CANNOT occupy the
    same 3D space, bump into each other on impossible trajectories, or phase
    through solid geometry.
  - Mechanical & Kinematic Plausibility: Any moving mechanisms, transport
    systems, or moving parts must follow logical, independent, functional
    real-world paths without track sharing or impossible mechanical collisions.
  - Biological & Human Realism: Humans, limbs, and hands must obey natural
    anatomy, weight balance, and plausible motion without anatomical
    contortions or phantom clipping.
  - AUTOMATIC SCORE CAP FOR COMMON-SENSE & COLLISION DEFECTS: If solid objects
    collide, clip through each other, phase through walls/floors, or defy
    fundamental real-world causality, strictly CAP Dimension 1 at
    8.0 - 12.5 pts and flag in improvement_prompt.
- STATIC ARTWORK & SURFACE CONTENT INVARIANCE (ZERO METAMORPHIC SHIFTS):
  - Paintings, wall murals, framed photos, and wall decor are 100% STATIC
    PIGMENTED SURFACES.
  - A painting or wall mural must NEVER change what is depicted on it, morph
    its subjects, shift colors, or alter its shapes midway through the clip!
  - If artwork content morphs, changes subject matter, or behaves like a
    video screen/liquid paint, this is a FATAL PHYSICAL LOGIC BREACH!
    CAP Dimension 1 at 8.0 - 12.0 pts and Dimension 2 at 8.0 - 12.0 pts.
- ELEVATOR & MECHANICAL TRACK ISOLATION (ZERO TRACK SHARING / COLLISIONS):
  - In atriums, towers, and buildings, each glass elevator capsule MUST
    travel strictly within its own isolated vertical hoistway.
  - Two elevators CANNOT share, pass, or collide in the same vertical shaft!
  - If elevators overlap, phase through each other, or phantom capsules pop in
    midway down a shared shaft: CAP Dimension 1 at 8.0 - 11.0 pts and
    Dimension 4 at 8.0 - 10.0 pts (Automatic FAIL < 55.0 / 100).
- BACKGROUND & WINDOW PERSISTENCE (ZERO POP-IN / MATERIALIZATION):
  - The exterior view through windows, balconies, or in backgrounds must
    remain completely persistent with the reference image throughout all 8s.
  - If trees, buildings, foliage, or objects SPONTANEOUSLY POP IN, materialize
    out of nowhere, disappear, or morph outside windows or in the background,
    this is a CRITICAL TEMPORAL & PHYSICAL FAILURE!
    CAP Dimension 1 at 8.0 - 12.0 pts and Dimension 4 at 8.0 - 11.0 pts.
- INDOOR AERODYNAMIC & FABRIC REALISM (ZERO VIOLENT INDOOR CURTAIN FLAPPING):
  - In indoor rooms (bedrooms, suites, lobbies), curtains, drapes, bedding,
    and fabrics must remain predominantly static with natural resting gravity.
  - Curtains indoors must NEVER flap violently, whip around rapidly, or
    behave as if buffeted by a gale-force wind inside a sealed room!
  - If indoor curtains flutter rapidly or whip unnaturally towards the end:
    CAP Dimension 1 at 10.0 - 13.0 pts and Dimension 4 at 10.0 - 13.0 pts.
    Flag in improvement_prompt: "INDOOR FABRIC STABILITY: Keep indoor curtains
    and fabrics static and calm. Eliminate rapid or violent curtain flapping."
- Guidelines:
  - 23.6 - 25.0 pts: Pristine photorealism, 100% static solid objects/artwork.
  - 20.0 - 23.5 pts: Strong realism with minor micro-softness or subtle drift.
  - 13.0 - 19.9 pts: Noticeable unnatural rippling or subtle texture swimming.
  - 0.0 - 12.9 pts: Morphing artwork, elevator collisions, rapid indoor flapping.

### Dimension 2: Reference Image & Storyboard Consistency (Max: 25 pts)
- Visual continuity relative to attached reference image (composition,
  environment, color palette, lighting scheme, subject identity).
- STRICT INDOOR ROOM CONTAINMENT & ZERO WINDOW FLYTHROUGHS / GROUND DIVES:
  - In indoor scenes (hotel bedroom, suite), the virtual camera MUST REMAIN
    100% INSIDE the room for the entire 8.0 seconds.
  - The camera must NEVER fly out through the window, dive down to ground/street
    level, or hallucinate fictional exterior environments not in the photo!
  - If the camera flies out the window or dives down to the ground:
    THIS IS A FATAL PERSPECTIVE & CLOSED-WORLD HALLUCINATION!
    Strictly CAP Dimension 2 at 6.0 - 9.0 pts and Dimension 3 at 6.0 - 9.0 pts
    (Automatic FAIL < 45.0 / 100).
    Flag: "FATAL WINDOW FLYTHROUGH: Camera flew out the window down to the ground
    level and hallucinated ungrounded scenes. Keep camera strictly inside room."
- FULL STORYBOARD PRESERVATION (ZERO FOREGROUND OR CEILING CROPPING):
  - The clip must preserve the ENTIRE composition of the reference photo,
    including foreground fountains, pools, flooring, and ceiling skylights.
  - If major foreground assets (e.g. lobby fountain) or ceiling architecture
    are cropped out or missing, CAP Dimension 2 at 8.0 - 12.0 pts.
- STRICT CLOSED-WORLD ASSET FIDELITY (ZERO HALLUCINATED ADDITIONS):
  - The reference image is the absolute ground truth. The video must
    contain ONLY the subjects, environment, and objects visible in the photo.
  - ZERO MADE-UP ASSETS: If the model adds new people, phantom actors,
    extra furniture, ungrounded decor, or trees/buildings not present in the
    reference image, this is a SEVERE IMAGE FIDELITY BREACH!
  - AUTOMATIC SCORE CAP: Cap Dimension 2 at 8.0 - 12.5 pts and flag in
    improvement_prompt: "HALLUCINATED ASSETS: Remove ungrounded added
    elements (e.g. spontaneous trees, altered art) and restrict scene
    strictly to contents of the reference photo."
- FRAMING INVARIANCE & ZERO DEEP ZOOM HALLUCINATION MANDATE:
  - The clip MUST preserve the camera framing, perspective, and composition
    of the original reference photo throughout the entire 8.0 seconds.
  - If the camera zooms in excessively, pushes deep into the background,
    or crops in tightly to invent/hallucinate new ungrounded objects,
    altered geometry, or phantom elements not in the reference image:
    CAP Dimension 2 (Storyboard Consistency) at 10.0 - 13.5 pts and
    CAP Dimension 3 (Prompt Adherence) at 10.0 - 13.5 pts.
  - Explicitly flag in improvement_prompt:
    "EXCESSIVE ZOOM & HALLUCINATION: The camera zoomed in too deep and
    hallucinated ungrounded elements not present in the reference image.
    Lock camera framing to the original reference photo with only subtle
    ambient motion."
- Guidelines:
  - 23.6 - 25.0 pts: Exact architectural and environmental fidelity to photo.
  - 20.0 - 23.5 pts: Strong visual consistency with minor lighting variance.
  - 13.0 - 19.9 pts: Noticeable drift in environment, colors, or decor.
  - 0.0 - 12.9 pts: Morphing artwork, pop-in trees, deep zoom hallucinations.

### Dimension 3: Prompt Adherence & Action Execution (Max: 20 pts)
- Execution of described actions, camera movement, and pacing.
- SINGLE UNBROKEN SHOT (ZERO INTERNAL CUTS): The prompt commands ONE single
  unbroken 8-second shot. If the clip contains any internal cut, angle switch,
  or mini-montage, strictly CAP Dimension 3 at 6.0 - 9.0 pts.
- LOCKED FRAMING & VELOCITY: Steady continuous velocity without abrupt zooms.
- Guidelines:
  - 18.6 - 20.0 pts: Flawless camera motion and action execution.
  - 15.0 - 18.5 pts: Primary action captured with slight variation in speed.
  - 10.0 - 14.9 pts: Excessive zoom, missing motion intent, or focal drift.
  - 0.0 - 9.9 pts: Mid-clip cuts, scene switches, or disregards prompt.

### Dimension 4: Temporal Consistency, Motion Stability & Fluidity (Max: 20 pts)
- Frame stability, smooth motion flow, absence of flickering or tearing.
- ABSOLUTE ZERO INTERNAL CUTS & MONTAGE SHOTS MANDATE:
  - The entire 8-second clip MUST be ONE SINGLE UNBROKEN CONTINUOUS SHOT from
    0.0s to 8.0s!
  - ABSOLUTELY NO INTERNAL CUTS, NO JUMP CUTS, NO PERSPECTIVE JUMPS, AND NO
    MID-CLIP SCENE CHANGES!
- CALM RESORT POOL WATER FLUID REALISM (ZERO UNNATURAL SLOSHING):
  - Swimming pool water in resort sanctuaries must remain calm, tranquil, and
    crystal clear with gentle surface light reflections and micro-ripples.
  - If pool water sloshes violently, creates unnatural tidal waves, or churns
    unnaturally like a whirlpool: FATAL FLUID DYNAMICS FLAW (CAP at 4.0 - 6.0 / 20.0).
    Flag: "UNREALISTIC POOL SLOSHING: Pool water is sloshing or waving violently.
    Resort pool water must remain calm with subtle sparkling reflections."
- STEADY FRONT-MOVING FORWARD PAN-IN WITH COMPLETE DETAIL PRESERVATION:
  - Outdoor resort scenes should feature smooth, continuous front-moving forward
    glide (dolly-in) while maintaining 100% of the reference assets, palm trees,
    sun loungers, and poolside architecture without warping or disappearing.
  - If the clip cuts from wide to a closeup, switches angles midway, or stitches
    two different shots into one 8s clip:
    THIS IS A FATAL CINEMATOGRAPHY DEFECT!
    Strictly CAP Dimension 4 at 6.0 - 9.0 pts (Automatic FAIL < 50.0 / 100) and
    flag: "FATAL DEFECT: Mid-clip cut detected. Enforce ONE continuous unbroken
    take from 0.0s to 8.0s with zero scene cuts."
- SPATIAL INTEGRITY & CAUSAL CONTINUITY:
  - All moving elements must maintain solid continuous geometry and obey
    real-world physical momentum.
  - If moving objects collide, dissolve into each other, or teleport across
    space, CAP Dimension 4 at 8.0 - 11.0 pts.
- NATURAL OUTDOOR FLORA & FLUID DYNAMICS RULE: In outdoor landscape, resort,
  and garden scenes, natural breeze blowing through tree foliage, swaying palm
  fronds, rippling water fountains, and ocean wave currents are physically
  realistic environmental elements. Do NOT penalize natural organic motion of
  water, leaves, or grass as temporal instability. As long as primary
  architectural structures and camera movement remain continuous and stable
  without severe glitching or frame tearing, award high marks (18.6 - 20.0 pts).
- Guidelines:
  - 18.6 - 20.0 pts: Smooth continuous camera flow without unnatural warping.
  - 15.0 - 18.5 pts: Good overall flow with minor micro-jitter.
  - 10.0 - 14.9 pts: Noticeable object warping or liquid breathing.
  - 0.0 - 9.9 pts: Internal cuts, perspective jumps, severe collisions.

### Dimension 5: Commercial Production Quality & Polish (Max: 10 pts)
- Broadcast advertising quality, lighting harmony, contrast, sharpness.
- Guidelines:
  - 9.1 - 10.0 pts: Crisp 1080p broadcast advertising aesthetic.
  - 7.5 - 9.0 pts: Solid commercial quality with minor texture softness.
  - 4.5 - 7.4 pts: Flat contrast or visible compression noise.
  - 0.0 - 4.4 pts: Blurry or unpolished output.

---

## 3. PASS / FAIL GATING LOGIC & IMPROVEMENT DIRECTIVES

- Pass Threshold: Total Score >= 95.0 points.
- If Total Score >= 95.0:
  - Set passed_threshold = true, improvement_prompt = "".
- If Total Score < 95.0:
  - Set passed_threshold = false.
  - Provide concise improvement_prompt explaining what to adjust
    (e.g., "Keep static indoor furniture and wall artwork completely still
    and rigid, only apply slow cinematic camera push-in.").

---

## 4. OUTPUT FORMAT REQUIREMENTS

Your output must be a single, valid JSON object strictly conforming to schema.
"""


def build_final_ad_evaluation_prompt(
    company_name: str,
    tagline: str,
    scene_scripts: List[str],
    outro_script: str = "",
    attempt_number: int = 1,
    previous_feedback: str = "",
) -> str:
    """Builds prompt for evaluating the fully assembled commercial video ad.

    Args:
        company_name: Brand or company name.
        tagline: Campaign slogan / tagline.
        scene_scripts: List of voiceover scripts for each scene.
        outro_script: Outro script text.
        attempt_number: Assembly iteration number (1 to 3).
        previous_feedback: Feedback from previous assembly attempt.

    Returns:
        Structured evaluation prompt for full video advertisement.
    """
    script_bullets = "\n".join(
        [f'- Scene {i+1}: "{s}"' for i, s in enumerate(scene_scripts)]
    )

    iteration_context = ""
    if previous_feedback and attempt_number > 1:
        prev_num = attempt_number - 1
        iteration_context = (
            f"\n### Previous Assembly Feedback (Attempt {prev_num}):\n"
            f'"{previous_feedback}"\n'
            "Verify if this assembly resolved the audio/visual/logo issues "
            "without introducing any new audio truncation or overlay flaws.\n"
        )

    return f"""
# ROLE: Executive Creative Director & Commercial Video Ad QA Inspector

You are an expert commercial advertising QA director evaluating a fully
assembled Multi-Scene Video Advertisement (with Voiceover, Background Music,
Scene Dissolves, Logo Overlay, and Outro Tagline).

CRITICAL REALISM & SCORING CALIBRATION:
- A score of 100.0 is unrealistic. Pristine commercial video ad assemblies
  score 95.5 to 97.5.
- Evaluate the on-screen logo strictly against the attached Reference Logo
  asset without deducting points for brand name semantics.
- NATIVE AI WATERMARK POLICY: Ignore native AI platform safety badges
  (such as the subtle Vertex AI Veo SynthID corner watermark). Do NOT
  deduct points from Commercial Polish or Brand Identity for native
  platform safety watermarks.

---

## 1. CAMPAIGN CONTEXT

- Brand / Company: {company_name}
- Campaign Tagline: "{tagline}"
- Scene Voiceover Scripts:
{script_bullets}
- Outro Call-To-Action: "{outro_script}"
- Reference Logo Asset: (Attached reference logo image is the official logo).
- Assembly Attempt: Attempt {attempt_number} of 3
{iteration_context}

---

## 2. 100-POINT FULL-AD EVALUATION RUBRIC

Evaluate the complete assembled commercial video across 5 dimensions:

### Dimension 1: Voiceover & Audio Clarity, Pacing & Non-Truncation (25 pts)
- Audio speech clarity, zero word truncation/cutoffs at scene start or end,
  natural pacing, and clean audio ducking balance against background music.
- Guidelines:
  - 23.5 - 24.5 pts: Clear audible voiceover, zero truncation, clean ducking.
  - 20.0 - 23.0 pts: Good clarity with minor background music presence.
  - 14.0 - 19.5 pts: Voiceover noticeably masked by music or edge cutoffs.
  - 0.0 - 13.5 pts: Severely truncated words, garbled or inaudible speech.

### Dimension 2: Brand Identity, Logo Placement & Outro Aesthetics (20 pts)
- CRITICAL ASSET VALIDATION RULE: The attached Reference Logo asset (whether
  default Google logo or custom uploaded logo) is the 100% AUTHORIZED logo for
  this commercial ad. Evaluate purely on whether the on-screen logo matches
  this attached reference logo asset.
- DEFAULT LOGO & TYPOGRAPHY RULE: If the default logo is used, validate
  against the attached default logo asset. Do NOT penalize for brand graphic vs
  company name association. Award full marks (18.5 - 19.5 pts) for clean alpha
  transparency, corner positioning, and sharp outro presentation.
- MONOTONIC ATTEMPT IMPROVEMENT DIRECTIVE: When re-evaluating subsequent
  attempts (Attempt 2 & 3), do NOT fluctuate or penalize static branding or
  visual outro elements. Total composite score MUST monotonically improve as
  voiceover clarity and audio ducking parameters are optimized.
- Evaluate purely on visual rendering quality:
  1. Visual Fidelity: Does on-screen logo match the attached reference logo?
  2. Clean Alpha Transparency: Is the logo blended with zero bounding box?
  3. Positioning & Scaling: Proper corner margins without blocking subjects?
  4. Outro Card Presentation: Crisply rendered alongside the tagline?
- Guidelines:
  - 18.5 - 19.5 pts: Matches attached logo asset with clean transparency,
    proper corner placement, and sharp outro presentation.
  - 15.0 - 18.0 pts: Minor scaling or margin imperfection.
  - 10.0 - 14.5 pts: Awkward positioning or slight clipping.
  - 0.0 - 9.5 pts: Broken transparency, distorted aspect ratio, or missing.

### Dimension 3: Typography, Tagline & Font Appearance (15 pts)
- Font legibility, crisp rendering, high contrast against video background,
  proper margins without overlapping subjects.
- TAGLINE BACKDROP & HIGH-CONTRAST LEGIBILITY RULE: The tagline is rendered
  with a dark translucent protective pill backdrop and crisp high-contrast
  white typography. As long as the tagline text is legible, spelled correctly,
  and presented cleanly at the bottom of the video, award full high-tier marks
  (14.0 - 15.0 pts).
- ZERO ATTEMPT DEGRADATION DIRECTIVE: Do NOT artificially decrease typography
  score across attempts (e.g. docking 13.0 -> 10.0 -> 8.0) when audio ducking
  or transitions are being refined. Maintain consistent objective scoring.
- Guidelines:
  - 14.0 - 15.0 pts: Crisp legible tagline with high-contrast backdrop,
    readable across all scenes.
  - 12.0 - 13.5 pts: Readable font with minor styling variation.
  - 8.0 - 11.5 pts: Completely unreadable or obscured text.
  - 0.0 - 7.5 pts: Illegible, overlapping other text, or clipped.

### Dimension 4: Multi-Scene Transitions & Narrative Cohesion (20 pts)
- Smooth cross-dissolve transitions between scenes, visual continuity,
  logical narrative rhythm from opening hook to closing CTA.
- Guidelines:
  - 18.5 - 19.5 pts: Smooth cross-dissolves, cohesive narrative pacing.
  - 15.0 - 18.0 pts: Good transitions with minor abrupt pacing.
  - 10.0 - 14.5 pts: Choppy transitions or disjointed narrative rhythm.
  - 0.0 - 9.5 pts: Broken video stitching or black frame glitches.

### Dimension 5: Commercial Broadcast Polish & Sound Balance (20 pts)
- Complete broadcast standard, balanced sound mix (voiceover priority over
  background music), professional color consistency, and overall ad appeal.
- Guidelines:
  - 18.5 - 19.5 pts: Solid commercial finish ready for TV/Social video ads.
  - 15.0 - 18.0 pts: Good production quality with minor sound/color variance.
  - 10.0 - 14.5 pts: Rough audio balance or unpolished pacing.
  - 0.0 - 9.5 pts: Unbalanced audio or unpolished visual finish.

---

## 3. PASS / FAIL GATING & ASSEMBLY TUNING DIRECTIVES

- Pass Threshold: Total Score >= 95.0 points.
- If Total Score >= 95.0:
  - Set passed_threshold = true, improvement_prompt = "".
- If Total Score < 95.0:
  - Set passed_threshold = false.
  - Suggest assembly parameter adjustments:
    • recommended_music_volume (e.g. 0.25 to 0.40)
    • recommended_vo_padding (e.g. 0.4 to 0.8 seconds)
    • recommended_logo_scale (e.g. 0.10 to 0.15)
    • recommended_dissolve_duration (e.g. 0.3 to 0.8 seconds)

---

## 4. OUTPUT FORMAT REQUIREMENTS

Your output must be a single, valid JSON object conforming strictly to schema.
"""


def build_physion_arc_evaluation_prompt(
    company_name: str,
    tagline: str,
    scene_scripts: List[str],
    outro_script: str = "",
) -> str:
    """Builds evaluation prompt for the 16-metric Physion ARC 1.0 benchmark."""
    script_bullets = "\n".join(
        [f'- Scene {i+1}: "{s}"' for i, s in enumerate(scene_scripts)]
    )

    return f"""
# ROLE: Official Physion ARC-1.0 Multimodal Benchmark Inspector

You are an expert video AI benchmark evaluator scoring this multi-scene video ad
against the official 16 metrics of the Physion ARC 1.0 Benchmark
(https://physionlabs.ai/).

---

## 1. CAMPAIGN CONTEXT
- Brand / Company: {company_name}
- Campaign Tagline: "{tagline}"
- Scene Voiceover Scripts:
{script_bullets}
- Outro Call-To-Action: "{outro_script}"

---

## 2. THE 16 PHYSION ARC-1.0 METRICS (0-100 SCALE PER METRIC)

Evaluate each of the 16 metrics on a 0-100 scale:

### DIMENSION 1: NARRATIVE COHERENCE (NC)
1. beat_segmentation (Objective): Logical segmentation of story beats.
2. narrative_alignment (Objective): Alignment of visuals/speech with goals.
3. identity_consistency (Objective): Subject identity persistence across cuts.
4. prop_persistence (Objective): Objects & clothing remain unchanged.
5. environment_consistency (Objective): Spatial continuity of architecture.
6. causal_logic (Objective): Physical causality (doors, gravity, interactions).
7. emotional_intent (Subjective): Emotional delivery of tone, music, atmosphere.

### DIMENSION 2: CINEMATIC LANGUAGE (CL)
8. camera_grammar (Subjective): Classical camera moves (push-in, pan, framing).
9. composition_blocking (Subjective): Rule of thirds, depth, subject framing.
10. director_style_adherence (Subjective): Adherence to cinematic cues.
11. rhythm_pacing (Subjective): Tempo, cut duration, transition flow.
12. audio_integration (Subjective): Speech clarity, music ducking, audio sync.

### DIMENSION 3: PRODUCTION QUALITY (PQ)
13. lighting_consistency (Subjective): Color temperature and light continuity.
14. spatial_consistency (Objective): 3D geometry stability without warping.
15. technical_coherence (Objective): Resolution, sharpness, zero compression.
16. color_treatment (Subjective): Color grading harmony and unified palette.

---

## 3. OUTPUT FORMAT REQUIREMENTS
Your output must be a single, valid JSON object conforming strictly to schema.
"""
