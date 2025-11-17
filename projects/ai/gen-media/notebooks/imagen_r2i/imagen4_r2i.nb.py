# ---
# jupyter:
#   jupytext:
#     formats: ipynb,nb.py
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.18.1
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
# # Imagen 4 Image Generation
#
# Use this notebook to generate reference images or upload your own assets before invoking the Imagen R2I model.

# %% [markdown] id="G1KDmM_PBAXz"
# | Author |
# | --- |
# | [Isidro De Loera Jr](isidrodeloera@google.com) |

# %% [markdown]
# # Overview
#
# The notebook designed to orchestrate Google Imagen reference-to-image (R2I) workflows within a standard Jupyter experience. It guides you through generating or uploading reference assets, reviewing previews, and invoking the R2I model.

# %% [markdown]
# ## Purpose
# The notebook streamlines experimentation with Imagen 4 R2I by:
# - Generating optional content and style seed images.
# - Allowing user-supplied content/style uploads.
# - Enforcing preview steps so every asset is validated before it reaches the model.
# - Building the correct Google GenAI payloads for editing calls.

# %% [markdown]
# ## Scope
# This project covers the Jupyter-based workflow only. Backend services, web apps, or automation pipelines are out of scope. The notebook assumes you already have access to Google Cloud Vertex AI and the Imagen R2I models.

# %% [markdown]
# ## Get Started

# %% [markdown]
# ### Install Dependancies
#
# If you are using VS Code read more on how to [Manage Jupyter Kernels in VS Code](https://code.visualstudio.com/docs/datascience/jupyter-kernel-management). You will need to ensure you have executed `pip install ipykernel` on the local terminal.

# %%
# %pip install --upgrade --quiet google-genai \
#                                ipywidgets \ 
#                                ipython \ 
#                                pillow

# %% [markdown]
# ## Imports

# %%
import os
import sys
from dataclasses import dataclass
from io import BytesIO
from typing import List, Literal, Optional, Tuple, Union

import google.auth
import ipywidgets as widgets
from google import genai
from google.genai import types
from IPython.display import Image, Markdown, clear_output, display

# %% [markdown]
# ### Set Google Cloud project information
#
# To get started using Vertex AI, you must have an existing Google Cloud project and [enable the Vertex AI API](https://console.cloud.google.com/flows/enableapi?apiid=aiplatform.googleapis.com).
#
# Learn more about [setting up a project and a development environment](https://cloud.google.com/vertex-ai/docs/start/cloud-environment).

# %%
IMAGEN_MODEL = os.environ.get("IMAGEN_MODEL", "imagen-4.0-generate-001")
R2I_MODEL = os.environ.get("R2I_MODEL", "imagen-4.0-ingredients-preview")
PROJECT_ID = os.environ.get(
    "GOOGLE_CLOUD_PROJECT", "consumer-genai-experiments"
)
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
USE_PREPROD_ENDPOINT = False
PREPROD_HTTP_ENDPOINT = "https://us-central1-preprod-aiplatform.googleapis.com"

if PROJECT_ID in (None, "", "<YOUR_GCP_PROJECT>"):
    raise ValueError(
        "Set GOOGLE_CLOUD_PROJECT or update PROJECT_ID with your GCP project ID."
    )

# %% [markdown]
# ### Authenticate your notebook environment (Colab only)

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
    project_id: str, location: str = "us-central1"
) -> None:
    """Validates ADC, sets env vars for Vertex AI, and creates a global genai.Client()."""
    global PROJECT_ID, LOCATION
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

    PROJECT_ID = resolved_project
    LOCATION = resolved_location
    print(f"Gemini configured for project {PROJECT_ID} in location {LOCATION}.")


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
        except ValueError as exc:
            print(f"Configuration failed: {exc}")


configure_button.on_click(on_configure_clicked)
display(project_input, location_input, configure_button, config_output)

# %%
# !gcloud auth application-default set-quota-project {os.environ.get("GOOGLE_CLOUD_PROJECT", "Project ID not found in os.environ")}
# !gcloud config set project {os.environ.get("GOOGLE_CLOUD_PROJECT", "Project ID not found in os.environ")}

# %% [markdown]
# ### Get Credentials(Colab & Manual)

# %%
credentials, project = google.auth.default()
print("ADC status:", credentials is not None)
print("ADC project:", project)

# %% [markdown]
# ## Create GCP Client
#
# To get started using Vertex AI, you must have an existing Google Cloud project and [enable the Vertex AI API](https://console.cloud.google.com/flows/enableapi?apiid=aiplatform.googleapis.com).
#
# Learn more about [setting up a project and a development environment](https://cloud.google.com/vertex-ai/docs/start/cloud-environment).

# %%
client_kwargs = dict(vertexai=True, project=PROJECT_ID, location=LOCATION)
if USE_PREPROD_ENDPOINT:
    client_kwargs["http_options"] = {"base_url": PREPROD_HTTP_ENDPOINT}
vertex_client = genai.Client(**client_kwargs)

# %% [markdown]
# ## Helper Functions

# %%
MAX_CONTENT_REFERENCES = 3


@dataclass
class ReferenceImage:
    label: str
    data: bytes
    mime_type: str
    source: Literal["generated", "uploaded"]
    reference_type: Literal["content", "style"]


content_references: List[ReferenceImage] = []
style_reference: Optional[ReferenceImage] = None


def clear_reference_state() -> None:
    global content_references, style_reference
    content_references = []
    style_reference = None


def extract_bytes_and_mime(
    image_obj, fallback_mime: str = "image/jpeg"
) -> Tuple[bytes, str]:
    image = getattr(image_obj, "image", image_obj)
    mime = (
        getattr(image_obj, "mime_type", None)
        or getattr(image, "mime_type", None)
        or fallback_mime
    )
    image_bytes = getattr(image, "image_bytes", None) or getattr(
        image_obj, "image_bytes", None
    )
    if image_bytes:
        return bytes(image_bytes), mime
    inline = getattr(image, "inline_data", None)
    if inline:
        data = getattr(inline, "data", None) or getattr(
            inline, "bytes_data", None
        )
        inline_mime = getattr(inline, "mime_type", None) or mime
        if data:
            return bytes(data), inline_mime or mime
    pil = getattr(image, "_pil_image", None)
    if pil is not None:
        buffer = BytesIO()
        fmt = "PNG" if (mime or "").endswith("png") else "JPEG"
        pil.save(buffer, format=fmt)
        return buffer.getvalue(), mime or f"image/{fmt.lower()}"
    if isinstance(image_obj, (bytes, bytearray)):
        return bytes(image_obj), mime
    raise ValueError("Unable to extract bytes from provided image payload")


def preview_reference(ref: ReferenceImage) -> None:
    display(
        Markdown(
            f"**{ref.reference_type.title()} reference** - "
            f"{ref.label} ({ref.source})"
        )
    )
    img_format = (
        ref.mime_type.split("/")[-1]
        if ref.mime_type and "/" in ref.mime_type
        else "jpeg"
    )
    display(Image(data=ref.data, format=img_format))


def add_content_reference(ref: ReferenceImage) -> None:
    if len(content_references) >= MAX_CONTENT_REFERENCES:
        raise ValueError("Maximum content reference images reached.")
    content_references.append(ref)
    preview_reference(ref)


def set_style_reference(ref: ReferenceImage) -> None:
    global style_reference
    style_reference = ref
    preview_reference(ref)


def render_reference_summary() -> None:
    if not content_references and not style_reference:
        display(Markdown("No reference images selected yet."))
        return
    for ref in content_references:
        preview_reference(ref)
    if style_reference:
        preview_reference(style_reference)


def build_reference_payloads(
    style_description: str,
) -> List[Union[types.ContentReferenceImage, types.StyleReferenceImage]]:
    if not content_references:
        raise ValueError(
            "Add at least one content reference image before calling the R2I model."
        )
    references: List[
        Union[types.ContentReferenceImage, types.StyleReferenceImage]
    ] = []
    for idx, ref in enumerate(content_references, 1):
        references.append(
            types.ContentReferenceImage(
                reference_id=idx,
                reference_image=types.Image(
                    image_bytes=ref.data, mime_type=ref.mime_type
                ),
            )
        )
    if style_reference:
        description = style_description.strip() or "style reference"
        references.append(
            types.StyleReferenceImage(
                reference_id=100,
                reference_image=types.Image(
                    image_bytes=style_reference.data,
                    mime_type=style_reference.mime_type,
                ),
                config=types.StyleReferenceConfig(
                    style_description=description
                ),
            )
        )
    return references


# %% [markdown]
# ### Generate or Upload Reference and Style Images
#
# #### Generate Reference Images (optional)

# %%
# input content generation prompts in the list below, add another prompt
# to have 3 content references images
content_generation_prompts = [
    "a close-up photo of a young woman",
    "a close-up photo of a young man",
]
style_generation_prompt = "a painting in watercolor style"
style_description_default = "watercolor style"


# %%
def generate_references_from_prompts(
    content_prompts,
    style_prompt=None,
    number_of_images: int = 1,
    aspect_ratio: str = "1:1",
    style_aspect_ratio: str = "1:1",
    output_mime: str = "image/jpeg",
) -> None:
    for prompt in content_prompts:
        if len(content_references) >= MAX_CONTENT_REFERENCES:
            print(
                "Content reference limit reached; "
                "skipping remaining prompts."
            )
            break
        response = vertex_client.models.generate_images(
            model=IMAGEN_MODEL,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=number_of_images,
                aspect_ratio=aspect_ratio,
                output_mime_type=output_mime,
                include_rai_reason=True,
            ),
        )
        images = getattr(response, "images", None)
        if not images:
            print(f"No image returned for prompt: {prompt}")
            continue
        image_obj = images[0]
        data, mime = extract_bytes_and_mime(image_obj, output_mime)
        try:
            add_content_reference(
                ReferenceImage(
                    label=f"Prompt: {prompt}",
                    data=data,
                    mime_type=mime,
                    source="generated",
                    reference_type="content",
                )
            )
        except ValueError as exc:
            print(str(exc))
            break
    if style_prompt:
        if style_reference:
            print("Style reference already set; skipping generation.")
        else:
            response = vertex_client.models.generate_images(
                model=IMAGEN_MODEL,
                prompt=style_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=style_aspect_ratio,
                    output_mime_type=output_mime,
                    include_rai_reason=True,
                ),
            )
            images = getattr(response, "images", None)
            if not images:
                print("No style image returned.")
            else:
                data, mime = extract_bytes_and_mime(images[0], output_mime)
                set_style_reference(
                    ReferenceImage(
                        label=f"Prompt: {style_prompt}",
                        data=data,
                        mime_type=mime,
                        source="generated",
                        reference_type="style",
                    )
                )


# %%
generate_references_from_prompts(
    content_generation_prompts,
    style_prompt=style_generation_prompt,
    aspect_ratio="1:1",
    style_aspect_ratio="16:9",
    output_mime="image/jpeg",
)

# %% [markdown]
# #### Upload Reference Images (optional)

# %%
style_description_default = "water color painting"

# %%
style_description_text = widgets.Text(
    value=style_description_default,
    description="Style desc",
    placeholder="Describe the style influence",
)
content_upload = widgets.FileUpload(
    accept="image/*", multiple=True, description="Content uploads"
)
style_upload = widgets.FileUpload(
    accept="image/*", multiple=False, description="Style upload"
)
process_uploads_button = widgets.Button(
    description="Add uploads", button_style="primary"
)
reset_button = widgets.Button(
    description="Reset references", button_style="warning"
)
upload_feedback = widgets.Output()


def _extract_files(upload_value):
    if isinstance(upload_value, dict):
        return list(upload_value.values())
    return list(upload_value)


def _file_info_to_reference(file_info, reference_type):
    mime = file_info.get("type") or "image/jpeg"
    data = file_info.get("content")
    if data is None:
        raise ValueError("Uploaded file payload is missing bytes.")
    if isinstance(data, memoryview):
        data = data.tobytes()
    elif isinstance(data, bytearray):
        data = bytes(data)
    elif not isinstance(data, bytes):
        data = bytes(data)
    return ReferenceImage(
        label=f"Upload: {file_info.get("name", "image")}",
        data=data,
        mime_type=mime,
        source="uploaded",
        reference_type=reference_type,
    )


def process_uploads(_):
    with upload_feedback:
        clear_output()
        style_files = _extract_files(style_upload.value)
        if style_files:
            if len(style_files) > 1:
                print("Upload one style image at a time.")
            elif style_reference:
                print("Style reference already set; reset to replace it.")
            else:
                try:
                    ref = _file_info_to_reference(style_files[0], "style")
                    set_style_reference(ref)
                except ValueError as exc:
                    print(str(exc))
            style_upload.value = ()
            if hasattr(style_upload, "_counter"):
                style_upload._counter = 0
        content_files = _extract_files(content_upload.value)
        if content_files:
            for file_info in content_files:
                if len(content_references) >= MAX_CONTENT_REFERENCES:
                    print(
                        "Content reference limit reached; "
                        "skipping remaining uploads."
                    )
                    break
                try:
                    ref = _file_info_to_reference(file_info, "content")
                    add_content_reference(ref)
                except ValueError as exc:
                    print(str(exc))
                    break
            content_upload.value = ()
            if hasattr(content_upload, "_counter"):
                content_upload._counter = 0
        if not style_files and not content_files:
            print("No files to upload.")


def reset_references(_):
    with upload_feedback:
        clear_output()
        clear_reference_state()
        print("Cleared all references.")


process_uploads_button.on_click(process_uploads)
reset_button.on_click(reset_references)

display(
    widgets.VBox(
        [
            widgets.HTML(
                "<b>Style description used for the style reference (if provided)</b>"
            ),
            style_description_text,
            widgets.HTML("<b>Upload reference images</b>"),
            widgets.HTML(
                "- Content: up to 3 images<br>- Style: at most 1 image"
            ),
            widgets.HBox([content_upload, style_upload]),
            widgets.HBox([process_uploads_button, reset_button]),
            upload_feedback,
        ]
    )
)

# %%
render_reference_summary()

# %% [markdown]
# ###  Invoke Imagen R2I

# %%
# add prompt below to combine images
edit_prompt = (
    "a man, a woman, talking in a cafe in Lodon, looking at each other"
)
edit_config = types.EditImageConfig(
    aspect_ratio="9:16",
    number_of_images=1,
    output_mime_type="image/jpeg",
)

# %%
style_description = (
    style_description_text.value
    if "style_description_text" in globals()
    else style_description_default
)
reference_images = build_reference_payloads(style_description)
response = vertex_client.models.edit_image(
    model=R2I_MODEL,
    prompt=edit_prompt,
    reference_images=reference_images,
    config=edit_config,
)
generated = getattr(response, "generated_images", None)
if not generated:
    raise ValueError("Model did not return any generated images.")
generated_bytes, generated_mime = extract_bytes_and_mime(
    generated[0], "image/jpeg"
)
display(Markdown("**R2I output preview**"))
img_format = (
    generated_mime.split("/")[-1]
    if generated_mime and "/" in generated_mime
    else "jpeg"
)
display(Image(data=generated_bytes, format=img_format))

# %% [markdown]
# # Conclusion
#
# This repository is designed as a comprehensive resource to help you quickly locate and leverage GenAI solutions. Explore the assets, adapt the work as needed, and feel free to contribute improvements. Our structured, use-case-oriented approach ensures that useful solutions are easily accessible and ready to evolve.
# Happy innovating!
