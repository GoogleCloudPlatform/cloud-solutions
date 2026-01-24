# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.20.0
#   kernelspec:
#     display_name: .venv
#     language: python
#     name: python3
# ---

# %% id="ijGzTHJJUCPY"
"""
Copyright 2025 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# cloud-solutions/ai-v0.0.1

# %% [markdown] id="VEqbX8OhE8y9"
# # Gemini 2.5 Flash Image Generation with Transparent Mask Overlay
#
# <table align="left">
#   <td style="text-align: center">
#     <a href="https://colab.research.google.com/github/GoogleCloudPlatform/cloud-solutions/blob/main/projects/ai/gen-media/notebooks/nano_banana/multi_turn_nano_banana_masking.ipynb">
#       <img width="32px" src="https://www.gstatic.com/pantheon/images/bigquery/welcome_page/colab-logo.svg" alt="Google Colaboratory logo"><br> Open in Colab
#     </a>
#   </td>
#   <td style="text-align: center">
#     <a href="https://console.cloud.google.com/vertex-ai/colab/import/https:%2F%2Fraw.githubusercontent.com%2FGoogleCloudPlatform%2Fcloud-solutions%2Fmain%2Fprojects%2Fai%2Fgen-media%2Fnotebooks%2Fnano_banana%2Fmulti_turn_nano_banana_masking.ipynb">
#       <img width="32px" src="https://lh3.googleusercontent.com/JmcxdQi-qOpctIvWKgPtrzZdJJK-J3sWE1RsfjZNwshCFgE_9fULcNpuXYTilIR2hjwN" alt="Google Cloud Colab Enterprise logo"><br> Open in Colab Enterprise
#     </a>
#   </td>
#   <td style="text-align: center">
#     <a href="https://console.cloud.google.com/vertex-ai/workbench/deploy-notebook?download_url=https://raw.githubusercontent.com/GoogleCloudPlatform/cloud-solutions/main/projects/ai/gen-media/notebooks/nano_banana/multi_turn_nano_banana_masking.ipynb">
#       <img src="https://www.gstatic.com/images/branding/gcpiconscolors/vertexai/v1/32px.svg" alt="Vertex AI logo"><br> Open in Vertex AI Workbench
#     </a>
#   </td>
#   <td style="text-align: center">
#     <a href="https://github.com/GoogleCloudPlatform/cloud-solutions/tree/main/projects/ai/gen-media/notebooks/nano_banana">
#       <img width="32px" src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="GitHub logo"><br> View on GitHub
#     </a>
#   </td>
# </table>
# <br clear="all">

# %% [markdown] id="G1KDmM_PBAXz"
# | Author |
# | --- |
# | [Isidro De Loera Jr](isidrodeloera@google.com) |

# %% [markdown]
# # Overview

# %% [markdown]
# This notebook demonstrates a **two-turn image editing workflow** using **Gemini 2.5 Flash (image preview)** on **Vertex AI**. In this notebook you will follow the steps:
#
# 1. Create a **transparent overlay mask** over a local image with a small Gradio app,
# 2. Send the masked image + prompt to Gemini 2.5 Flash for editing
# 3. Optionally **refine** the result with a second prompt.
#
# The notebook saves intermediate artifacts (`images/input.png`, `images/mask.png`, `images/overlay.png`) and renders model outputs inline.

# %% [markdown]
# ## Purpose
#
# * Provide a **practical reference** for guiding generative image edits using a **transparent mask overlay**.
# * Show how to **chain turns**: pass the first output back to the model along with a new instruction to refine the result.
# * Offer a minimal, **copy-paste-ready** setup for working with `google-genai` on Vertex AI.

# %% [markdown]
# ## Scope
#
# * Local, notebook-based workflow using **Vertex AI** endpoints (`project`, `location`) and the **Gemini 2.5 Flash Image** model.
# * A lightweight **Gradio** tool to draw/preview masks on an uploaded image and export a **transparent overlay**.
# * Examples of **Turn 1 (initial edit)** and **Turn 2 (refinement)** requests using the same conversation state.
# * Tested on Python 3.11.9

# %% [markdown]
# ## Get Started

# %% [markdown]
# ### Install Dependencies
#
# If you are using VS Code read more on how to [Manage Jupyter Kernels in VS Code](https://code.visualstudio.com/docs/datascience/jupyter-kernel-management). You will need to ensure you have executed `pip install ipykernel` on the local terminal.

# %%
# %pip install --upgrade --quiet google-genai==1.32.0 google-cloud-aiplatform==1.88.0 Pillow==11.3.0 ipython==9.0.0 numpy==2.3.2 gradio==5.44.1 ipywidgets google-auth-oauthlib nest-asyncio

# %% [markdown]
# ## Imports

# %%
import os
import sys
from io import BytesIO

import google.auth
import gradio as gr
import ipywidgets as widgets
import nest_asyncio
import numpy as np
from google import genai
from google.genai import types
from IPython.display import Markdown, display
from PIL import Image, ImageDraw
from vertexai.generative_models import GenerationResponse

nest_asyncio.apply()

# %% [markdown]
# ### Set Google Cloud project information
#
# To get started using Vertex AI, you must have an existing Google Cloud project and [enable the Vertex AI API](https://console.cloud.google.com/flows/enableapi?apiid=aiplatform.googleapis.com).
#
# Learn more about [setting up a project and a development environment](https://cloud.google.com/vertex-ai/docs/start/cloud-environment).

# %%
PROJECT_ID = "[your-project-id]"  # @param {type: "string", placeholder: "[your-project-id]", isTemplate: true}
if not PROJECT_ID or PROJECT_ID == "[your-project-id]":
    PROJECT_ID = str(os.environ.get("GOOGLE_CLOUD_PROJECT"))

LOCATION = (
    "global"  # @param {type: "string", placeholder: "global", isTemplate: true}
)

# %% [markdown]
# ### Authenticate your notebook environment (Colab)

# %%
if "google.colab" in sys.modules:
    from google.colab import auth  # pylint: disable=ungrouped-imports

    auth.authenticate_user()
    print("Authenticated as a user from colab.")


# %% [markdown]
# ### Authenticate your notebook environment (Manual)
#
# Log in to GCP from your on your local terminal.
# `gcloud auth application-default login`


# %%
def configure_gemini_with_gcloud(
    project_id: str, location: str = "global"
) -> None:
    """Validates ADC, sets env vars for Vertex AI, and creates a global genai.Client()."""
    global PROJECT_ID, LOCATION, client

    resolved_project = project_id or ""
    if not resolved_project:
        raise ValueError(
            "Project ID is required. Provide one or set a default with `gcloud"
            " config set project <PROJECT_ID>`."
        )
    resolved_location = (location or "global").strip()

    # Configure environment so google-genai routes via Vertex AI
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    os.environ["GOOGLE_CLOUD_PROJECT"] = resolved_project
    os.environ["GOOGLE_CLOUD_LOCATION"] = resolved_location

    client = genai.Client()

    PROJECT_ID = resolved_project
    LOCATION = resolved_location
    print(
        f"Gemini configured for project '{PROJECT_ID}' in location "
        f"'{LOCATION}'."
    )


# --- Small UI to configure once ---
project_input = widgets.Text(
    value=PROJECT_ID,
    description="Project ID:",
    placeholder="my-gcp-project",
    layout={"width": "55%"},
)
location_input = widgets.Text(
    value=LOCATION or "global",
    description="Location:",
    placeholder="global",
    layout={"width": "55%"},
)
configure_button = widgets.Button(
    description="Configure Gemini", button_style="success", icon="check"
)
config_output = widgets.Output()


def on_configure_clicked(_):
    with config_output:
        config_output.clear_output()
        try:
            configure_gemini_with_gcloud(
                project_input.value.strip(), location_input.value.strip()
            )
        except Exception as exc:
            print(
                f"Configuration failed: {exc}"
            )  # pylint: disable=-exception-caught


configure_button.on_click(on_configure_clicked)
display(project_input, location_input, configure_button, config_output)

# %%
# !gcloud auth application-default set-quota-project {os.environ.get('GOOGLE_CLOUD_PROJECT', 'Project ID not found in os.environ')}
# !gcloud config set project {os.environ.get('GOOGLE_CLOUD_PROJECT', 'Project ID not found in os.environ')}

# %% [markdown]
# ### Get Credentials(Colab & Manual)

# %%
credentials, project = google.auth.default()
print("ADC status:", credentials is not None)
print("ADC project:", project)

# %% [markdown]
# ## Create GCP Client

# %%
client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)

# %% [markdown]
# ### Set the Model

# %%
MODEL_ID = "gemini-2.5-flash-image"


# %% [markdown]
# ## Helper Functions


# %%
def display_image(response: GenerationResponse):
    """Render any IMAGE parts in a GenerationResponse."""
    for candidate in response.candidates:
        for part in candidate.content.parts:
            if part.inline_data:
                img = Image.open(BytesIO(part.inline_data.data))
                display(img)


def load_image_part(path: str, mime_type: str = "image/png") -> types.Part:
    """Read a local file as bytes and wrap it for genai."""
    with open(path, "rb") as f:
        data = f.read()
    return types.Part.from_bytes(data=data, mime_type=mime_type)


def turn_contents_from_response(response: GenerationResponse):
    """Extract the Content objects (with inline images) from a previous turn,

    so they can be fed back for editing.
    """
    return [candidate.content for candidate in response.candidates]


# %%
model_name = MODEL_ID
gen_config = types.GenerateContentConfig(
    temperature=1,
    top_p=0.95,
    max_output_tokens=32768,
    response_modalities=["TEXT", "IMAGE"],
    safety_settings=[
        types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT", threshold="OFF"
        ),
    ],
)


# %% [markdown]
# ## How to Use

# %% [markdown]
# ### 1) Launch the mask-drawing UI (Gradio)


# %%
def draw_masked_overlay(rgb_image, mask_image, alpha=0.5, color=(255, 0, 0)):
    rgb_image = rgb_image.convert("RGBA")
    mask_image = mask_image.convert("L")
    mask_image = mask_image.resize(rgb_image.size)
    colored_mask = Image.new("RGBA", rgb_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(colored_mask)
    mask_np = np.array(mask_image)
    ys, xs = np.where(mask_np > 0)
    a = int(alpha * 255)
    for y, x in zip(ys, xs):
        draw.point((x, y), fill=color + (a,))
    return Image.alpha_composite(rgb_image, colored_mask)


def to_np(img):
    if isinstance(img, Image.Image):
        return np.array(img.convert("RGB"))
    return img


def on_upload(img):
    """Immediately set the Sketchpad background to the uploaded image."""
    return to_np(img)


def sketchpad_mask_to_binary(mask_data):
    """Convert Sketchpad dict (background + layers) to white/black mask."""
    if not isinstance(mask_data, dict) or "background" not in mask_data:
        return None, "No sketchpad data."

    bg = mask_data["background"]  # H,W,3
    h, w, _ = bg.shape
    final_mask = np.zeros((h, w, 3), dtype=np.uint8)

    if mask_data.get("layers"):
        layer = mask_data["layers"][0]  # RGBA
        alpha_ch = layer[:, :, 3]
        drawn = alpha_ch > 0
        final_mask[drawn] = [255, 255, 255]

    Image.fromarray(bg).save("images/input.png")
    Image.fromarray(final_mask).save("images/mask.png")
    return final_mask, "Saved: images/input.png and images/mask.png"


def preview_overlay(alpha, hex_color):
    try:
        base = Image.open("images/input.png").convert("RGB")
        mask = Image.open("images/mask.png").convert("L")
    except FileNotFoundError:
        return None, "Please upload, draw, and generate the mask first."

    hex_color = hex_color.lstrip("#")
    color_rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    overlay = draw_masked_overlay(
        base, mask, alpha=float(alpha), color=color_rgb
    )
    overlay.save("images/overlay.png")
    return overlay, "Saved: images/overlay.png"


# %% [markdown]
# Run the **"Masking with Gradio"** cell. This opens a small app inline or at `http://127.0.0.1:7860`:
# * **Upload Image**: Choose the source image you want to edit.
# * **Draw Mask**: Use the Sketchpad to paint over regions you intend to modify.
# * Click **"Generate Mask (images/mask.png)"**:
#   * Saves your uploaded image as `images/input.png`.
#   * Saves the binary (white-on-black) mask as `images/mask.png`.
# * Click **"Preview Overlay & Save (images/overlay.png)"**:
#   * Combines `images/input.png` and `images/mask.png` to produce **`images/overlay.png`**, a transparent overlay visualization (you can adjust `alpha` and color to see the masked area).
# > **Why overlay?**
# > Gemini 2.5 Flash Image Generation can accept **masked images** as input. The recommended approach is to provide your original image with a **transparent mask overlaid** on the regions that should be edited. This helps the model **focus edits precisely** and **preserve unmasked content** (including any existing text/writing) in more complex scenes.

# %%
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        "# Draw Mask on Uploaded Image \nUpload → the image becomes the "
        "Sketchpad background → paint → generate mask → preview overlay."
    )

    img_input = gr.Image(type="pil", label="Upload Image")
    canvas = gr.Sketchpad(
        label="Draw directly on the uploaded image", type="numpy"
    )

    img_input.change(fn=on_upload, inputs=img_input, outputs=canvas)

    with gr.Row():
        gen_mask_btn = gr.Button("Generate Mask (images/mask.png)")
        alpha_slider = gr.Slider(
            0.0, 1.0, value=0.5, step=0.05, label="Overlay Alpha"
        )
        color_picker = gr.ColorPicker(value="#FF0000", label="Overlay Color")
        overlay_btn = gr.Button("Preview Overlay & Save (images/overlay.png)")

    mask_preview = gr.Image(label="Mask Preview (white=drawn)")
    overlay_preview = gr.Image(label="Overlay Preview")
    status = gr.Textbox(label="Status", interactive=False)

    gen_mask_btn.click(
        fn=sketchpad_mask_to_binary,
        inputs=canvas,
        outputs=[mask_preview, status],
    )
    overlay_btn.click(
        fn=preview_overlay,
        inputs=[alpha_slider, color_picker],
        outputs=[overlay_preview, status],
    )

demo.launch(share=False)

# %% [markdown]
# ### 2) Turn 1 — Initial Edit

# %%
image_path = "images/overlay.png"  # mask overlay image
first_prompt = (
    "Remove the small tomatoes which are masked and keep the other items."
)

# — Display the input image —
display(Markdown("## Input Image"))
input_img = Image.open(image_path)
display(input_img)

# Build the single Content for turn 1: [ imagePart, textPart ]
img_part = load_image_part(image_path)
first_contents = [
    types.Content(
        role="user", parts=[img_part, types.Part.from_text(text=first_prompt)]
    )
]

first_response = client.models.generate_content(
    model=model_name,
    contents=first_contents,
    config=gen_config,
)
# print(first_response)        # any text metadata
display_image(first_response)  # shows turn-1 output

# %% [markdown]
# ### 3) Turn 2 — Refinement

# %%
second_prompt = "add smoked salmon slices to the toast"
second_contents = (
    first_contents  # 1) original request
    + turn_contents_from_response(
        first_response
    )  # 2) the returned IMAGE+TEXT content
    + [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=second_prompt)
            ],  # 3) new edit instructions
        )
    ]
)

second_response = client.models.generate_content(
    model=model_name,
    contents=second_contents,
    config=gen_config,
)
display_image(second_response)  #

# %% [markdown]
# ## Best Practices & Tips
#
# * **Transparent overlay matters**: The model performs best when the edit intent is clear. Use a **transparent overlay** to indicate *where* changes should happen and keep everything else intact (including any existing text/writing you want preserved).
# * **Prompts should be specific**: Combine **what** to change, **where** (masked areas), and **what to preserve**.
# * **Iterate in turns**: Use Turn 2 (and beyond) to refine realism, add/remove items, or adjust style/scale.

# %% [markdown]
# ## Troubleshooting
#
# * **No overlay preview**
#   Ensure you clicked **Generate Mask** before **Preview Overlay**. The preview step requires both `images/input.png` and `images/mask.png`.
#
# * **Edits bleed outside the mask**
#   Reword your prompt to explicitly limit edits to **masked regions** and increase mask precision.
#
# * **Credential/permission errors**
#   Re-run the **Authentication** steps and verify your `PROJECT`/`LOCATION`/model name are correct in the notebook.

# %% [markdown]
# # Conclusion
#
# This notebook demonstrates a two-turn image editing workflow using Gemini 2.5 Flash on Vertex AI. It utilizes a Gradio app to create
# transparent overlay masks on local images, which are then sent to Gemini 2.5 Flash for editing. The workflow allows for initial edits and
# subsequent refinements with additional prompts, providing a practical reference for guiding generative image edits
