# Copyright 2025 Google LLC
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

"""
Tools for GenMedia Marketing Solution.
"""

import json
import logging
import os
import re
import shutil
import tempfile
from typing import Any, List, Optional

from google.cloud import storage
from moviepy import VideoFileClip
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from src.marketing_solutions.generate_contents.content_generator import (
    ContentGenerator,
    format_for_email,
)
from src.marketing_solutions.generate_videos.video_generator import (
    VideoGenerator,
)
from src.marketing_solutions.generate_visuals.image_generator import (
    ImageGenerator,
)

logger = logging.getLogger(__name__)

# Initialize generators and storage client
image_agent = ImageGenerator()
video_generator = VideoGenerator()
content_generator = ContentGenerator()
storage_client = storage.Client()
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")


def _download_from_gcs(gcs_uri: str, destination_folder: str) -> str:
    """Helper to download from a GCS URI."""
    if not gcs_uri.startswith("gs://"):
        raise ValueError(
          "Invalid GCS URI. Must start with 'gs://'"
        )

    bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)

    os.makedirs(destination_folder, exist_ok=True)
    destination_filename = os.path.join(
        destination_folder, os.path.basename(blob_name)
    )

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(destination_filename)
    logger.info("Downloaded %s to %s", gcs_uri, destination_filename)
    return destination_filename


def _upload_to_gcs(local_file_path: str, destination_blob_name: str) -> str:
    """Uploads a file to a GCS bucket.

    Args:
        local_file_path: The path to the local file to upload.
        destination_blob_name: The full path to the blob in the GCS bucket,
                               e.g., 'my-folder/my-file.mp4'.

    Returns:
        The GCS URI of the uploaded file.
    """
    if not GCS_BUCKET_NAME:
        raise ValueError("GCS_BUCKET_NAME environment variable is not set.")
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(local_file_path)
    gcs_uri = f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"
    logger.info("Successfully uploaded %s to %s", local_file_path, gcs_uri)
    return gcs_uri

async def generate_marketing_image(
    product_name: str,
    product_category: str,
    product_features: str,
    image_prompt: str,
) -> str:
    """
    Generates a marketing image based on product details and a custom prompt.

    Args:
        product_name: The official name of the product (e.g., "Sourdough
                      Bread").
        product_category: The category to which the product belongs
                          (e.g., "Artisan Breads").
        product_features: A comma-separated string of key features
                          (e.g., "organic, gluten-free").
        image_prompt: A descriptive sentence that guides the AI in generating
                      the visual scene (e.g., "A rustic loaf...").

    Returns:
        The GCS URI (e.g., 'gs://bucket-name/images/your-image.png') of the
        generated image.

    """
    logger.info("Generating marketing image for: %s", product_name)
    product_info = {
        "name": product_name,
        "category": product_category,
        "features": [
            feature.strip() for feature in product_features.split(",")
        ],
    }
    # The new image generator is async and returns a list with a GCS URI.
    image_uris = await image_agent.generate_and_save_image(
        product_info, custom_scene=image_prompt
    )
    if image_uris:
        gcs_uri = image_uris[0]
        logger.info("Image generated successfully. GCS URI: %s", gcs_uri)
        return gcs_uri
    logger.error("Failed to generate image.")
    raise ValueError("Failed to generate image.")

def _generate_videos_and_add_media(
    image_gcs_uri: str,
    video_duration: int,
    num_videos: int = 1,
    video_style: Optional[str] = None,
    music_prompt: Optional[str] = None,
    angles: Optional[List[str]] = None,
) -> List[str]:
    """
    Internal function to generate one or more videos in parallel and handle
    media processing.
    """
    logger.info("Generating marketing video from GCS image: %s", image_gcs_uri)

    if not video_style:
        video_style = "cinematic"
        logger.info("Video style not provided, using default: %s", video_style)

    if not music_prompt:
        music_prompt = (
            f"A {video_style} and upbeat instrumental track suitable for a"
            "bakery product promotion."
        )
        logger.info(
          "Music prompt not provided, using default: %s", music_prompt
        )

    if not angles:
        angles = [
            (
                "**Extreme close-up** on the product's texture, with the camera"
                "**pulling back slowly** to reveal the full product on a"
                "rustic wooden surface."
            ),
            (
                "A smooth **360-degree orbiting shot** around the product,"
                "showcasing all its sides. The background is a warm,"
                "out-of-focus bakery setting."
            ),
            (
                "A slightly wider **three-quarter angle shot**, showing the"
                "product on a plate next to a cup of coffee, with steam gently"
                "rising."
            ),
        ]

    temp_dir = tempfile.mkdtemp()
    try:
        local_image_path = _download_from_gcs(image_gcs_uri, temp_dir)

        intermediate_video_gcs_uris = video_generator.generate_video_uri(
            prompt_customized=f"A {video_style} video of the product.",
            image=local_image_path,
            video_style=video_style,
            video_dur=min(video_duration, 8),
            num_videos=num_videos,
            angles=angles,
        )
        if not intermediate_video_gcs_uris:
            raise ValueError("Failed to generate intermediate video(s).")

        local_intermediate_video_paths = [
            _download_from_gcs(uri, temp_dir)
            for uri in intermediate_video_gcs_uris
        ]

        if num_videos > 1:
            combined_video_path = os.path.join(temp_dir, "combined_video.mp4")
            video_generator.combine_videos(
                local_intermediate_video_paths, combined_video_path
            )
            video_to_add_audio_to = combined_video_path
            with VideoFileClip(combined_video_path) as combined_clip:
                total_duration = combined_clip.duration
        else:
            video_to_add_audio_to = local_intermediate_video_paths[0]
            total_duration = video_duration

        output_dir = "output/videos"
        os.makedirs(output_dir, exist_ok=True)
        base_filename = os.path.splitext(os.path.basename(local_image_path))[0]
        final_video_path = os.path.join(
            output_dir, f"{base_filename}_with_audio.mp4"
        )

        temp_music_path = video_generator.generate_music(
            music_prompt, duration_seconds=total_duration
        )
        if temp_music_path:
            final_video_with_audio_path = video_generator.add_audio_to_video(
                video_to_add_audio_to, temp_music_path, final_video_path
            )
            if final_video_with_audio_path:
                os.chmod(final_video_with_audio_path, 0o644)
                return [final_video_path]

        # Fallback to video without audio
        final_video_no_audio_path = os.path.join(
            output_dir, f"{base_filename}.mp4"
        )
        shutil.copy(video_to_add_audio_to, final_video_no_audio_path)
        os.chmod(final_video_no_audio_path, 0o644)
        return [final_video_no_audio_path]

    except Exception as e:
        logger.error("Error generating marketing video: %s", e)
        raise ValueError(f"Failed to generate video: {e}") from e
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def generate_marketing_video(
    image_gcs_uri: str,
    video_duration: int = 8,
    num_videos: int = 1,
    video_style: Optional[str] = None,
    music_prompt: Optional[str] = None,
    angles: Optional[List[str]] = None,
) -> List[str]:
    """
    Orchestrates the creation of a complete marketing video.

    This function manages a complex, multi-step workflow:
    1.  **Downloads Image**: Fetches the source marketing image from a GCS URI.
    2.  **Generates Video**: Creates one or more videos from the downloaded
        image, guided by a style prompt.
        If num_videos is 1 (default), a single video is generated.
        If num_videos >1, a sequence of videos is generated, where each video
        starts with the last frame of the previous one.
        Max is 3 for now, can be expanded.
    3.  **Generates Music**: Synthesizes background music.
    4.  **Combines Audio & Video**: Merges the generated video and music
                                    into MP4.
    5.  **Cleanup**: Removes all temporary files and directories.

    Args:
        image_gcs_uri: The GCS URI of the source image to be animated.
        video_duration: The target duration for the final video in seconds,
                        default is 8 seconds.
        num_videos: The number of videos to generate in sequence. Default is 1.
                    Max is 3 for now.
        video_style: Optional style (e.g., 'cinematic').
        music_prompt: Optional prompt for music generation.
        angles: Optional list of camera angle descriptions.

    Returns:
        The local file path to the final, composite video file.
    """
    logger.info("Generating marketing video from GCS image: %s", image_gcs_uri)
    default_angles = [
        (
            "**Extreme close-up** on the product's texture, with the camera"
            " **pulling back slowly** to reveal the full product on a rustic"
            " wooden surface."
        ),
        (
            "A smooth **360-degree orbiting shot** around the product,"
            " showcasing all its sides. The background is a warm, "
            "out-of-focus bakery setting."
        ),
        (
            "A slightly wider **three-quarter angle shot**, showing the "
            "product on a plate next to a cup of coffee, with steam "
            "gently rising."
        ),
    ]

    if num_videos == 1:
        if angles is None:
            # Use only the first default angle for a single video generation.
            angles_for_single_video = [default_angles[0]]
        else:
            angles_for_single_video = angles

        return _generate_videos_and_add_media(
            image_gcs_uri=image_gcs_uri,
            video_duration=video_duration,
            num_videos=1,
            video_style=video_style,
            music_prompt=music_prompt,
            angles=angles_for_single_video,
        )

    logger.info(
        "Generating a sequence of %s marketing videos, starting from %s",
        num_videos,
        image_gcs_uri,
    )

    all_final_video_paths = []
    current_image_gcs_uri = image_gcs_uri
    temp_dir = tempfile.mkdtemp()

    try:
        for i in range(num_videos):
            logger.info(
                "Generating sequential video %s/%s from %s",
                i + 1,
                num_videos,
                current_image_gcs_uri,
            )

            current_angle = (
                angles[i : i + 1] if angles and i < len(angles) else None
            )

            final_video_paths = _generate_videos_and_add_media(
                image_gcs_uri=current_image_gcs_uri,
                video_duration=video_duration,
                num_videos=1,
                video_style=video_style,
                music_prompt=music_prompt,
                angles=current_angle,
            )

            if not final_video_paths:
                raise ValueError(
                    f"Failed to generate video {i + 1} in the sequence."
                )

            final_video_path = final_video_paths[0]
            all_final_video_paths.append(final_video_path)

            if i < num_videos - 1:
                last_frame_path = os.path.join(
                    temp_dir, f"last_frame_of_video_{i}.png"
                )

                with VideoFileClip(final_video_path) as video_clip:
                    last_frame_time = video_clip.duration - 0.01
                    if last_frame_time < 0:
                        last_frame_time = 0
                    video_clip.save_frame(last_frame_path, t=last_frame_time)

                image_blob_name = (
                    f"images/sequential_frame_{i}_"
                    f"{os.path.basename(last_frame_path)}"
                )
                current_image_gcs_uri = _upload_to_gcs(
                    last_frame_path, image_blob_name
                )

        # If more than one video was generated, combine them
        if len(all_final_video_paths) > 1:
            base_name = os.path.basename(image_gcs_uri).split(".")[0]
            combined_video_filename = (
                f"combined_sequential_video_{base_name}.mp4"
            )
            combined_video_path = os.path.join(
                "output/videos", combined_video_filename
            )
            os.makedirs(os.path.dirname(combined_video_path), exist_ok=True)

            final_combined_video_local_path = video_generator.combine_videos(
                local_video_paths=all_final_video_paths,
                output_path=combined_video_path,
            )

            if final_combined_video_local_path:
                with VideoFileClip(
                    final_combined_video_local_path
                ) as combined_clip:
                    total_duration = combined_clip.duration

                music_prompt = (
                    f"A {video_style} and upbeat instrumental track suitable"
                    " for a bakery product promotion."
                )
                temp_music_path = video_generator.generate_music(
                    music_prompt, duration_seconds=total_duration
                )

                if temp_music_path:
                    audio_filename = (
                        f"combined_sequential_video_{base_name}"
                        "_with_audio.mp4"
                    )
                    final_video_with_audio_path = os.path.join(
                        "output/videos",
                        audio_filename,
                    )
                    final_video_with_audio_path = (
                        video_generator.add_audio_to_video(
                            final_combined_video_local_path,
                            temp_music_path,
                            final_video_with_audio_path,
                        )
                    )
                    if final_video_with_audio_path:
                        logger.info(
                            "All sequential videos combined and audio added"
                            " into: %s",
                            final_video_with_audio_path,
                        )
                        return [final_video_with_audio_path]

                logger.info(
                    "All sequential videos combined (without audio) into: %s",
                    final_combined_video_local_path,
                )
                return [final_combined_video_local_path]
            else:
                logger.error(
                    "Failed to combine sequential videos. Returning individual"
                    "video paths instead."
                )
                return all_final_video_paths
        else:
            return all_final_video_paths

    except Exception as e:
        logger.error("Error generating sequential marketing videos: %s", e)
        raise ValueError(f"Failed to generate sequential videos: {e}") from e
    finally:
        # Clean up temporary directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


def generate_marketing_content(
    topic: str,
    product_name: str,
    product_features: str,
    scene: str,
    customer_name: str,
    company_name: str,
    website_url: str,
    user_name: str,
    image_path: Optional[str] = None, # pylint: disable=unused-argument
) -> dict:
    """
    Generates a suite of marketing content tailored
    for different platforms.

    Args:
        topic: The central theme of the marketing campaign
               (e.g., "Fall Specials").
        product_name: The name of the product being promoted.
        product_features: A comma-separated list of the product's
                          key selling points.
        scene: A brief description to guide the tone and setting
               of the content.
        customer_name: The placeholder name for the customer in the
                       email greeting.
        company_name: The name of the business sending the email.
        website_url: The business's website, to be included in the content.
        user_name: The name of the person purportedly sending the email.
        image_path: (Optional) The URL of an image to be associated with
                    the content.

    Returns:
        A dictionary containing the generated content, with keys for "twitter",
        "instagram",and "email".Can be expanded.

    """
    logger.info(
        "Generating marketing content for: %s on topic: %s",
        product_name,
        topic,
    )
    features = [feature.strip() for feature in product_features.split(",")]
    marketing_offer_raw = content_generator.generate_marketing_offer(
        topic,
        product_name,
        features,
        scene,
        website_url=website_url,
    )

    if marketing_offer_raw:
        email_body = format_for_email(# pylint: disable=unexpected-keyword-arg
            marketing_offer_raw["Email"],
            customer_name,
            user_name,
            _company_name=company_name,
        )
        content = {
            "twitter": marketing_offer_raw["X"],
            "instagram": marketing_offer_raw["Instagram"],
            "email": email_body,
        }
        logger.info("Marketing content generated successfully.")
        return content
    logger.error("Failed to generate marketing content.")
    raise ValueError("Failed to generate marketing content.")


def create_customer_segment(topic: str, product_name: str) -> dict:
    """Analyzes customer data to create a target customer segment."""
    logger.info(
        "Creating customer segment for topic: %s and product: %s",
        topic,
        product_name,
    )
    # pylint: disable=protected-access
    customer_segment = content_generator._generate_customer_segment(
        topic, product_name
    )
    return customer_segment


def generate_outreach_strategy(
    customer_segment: dict, product_name: str
) -> str:
    """Generates an outreach strategy for a customer segment and product."""
    logger.info("Generating outreach strategy for: %s", product_name)
    outreach_strategy = content_generator.generate_outreach_strategy(
        customer_segment, product_name
    )
    return outreach_strategy


def draft_and_send_email(
    offer_json: dict,
    customer_name: str,
    company_name: str,
    website_url: str,
    customer_segment: Any,
    user_name: str,
    image_path: Optional[str] = None,
    _signature: str = "Warmly Betty",
) -> str:
    """
    THIS FUNCTION AIMS TO CREATE 'READ-TO-SEND' EMAIL.
    Assembles and formats a promotional email.

    Args:
        offer_json: A dictionary containing the core marketing message.
        customer_name: The placeholder for the recipient's name.
        company_name: The name of the business sending the email.
        website_url: The URL to be included for more information.
        customer_segment: The name or identifier of the target audience.
        user_name: The name of the sender, used in the email body.
        image_path: (Optional) A URL to an image to be embedded in the email.
        _signature: (Optional) The closing signature for the email (unused).

    Returns:
        A JSON string representing the drafted email, with keys for "to",
        "subject", and "body".
    """
    log = logging.getLogger("draft_and_send_email")
    log.info(
        "Drafting and 'sending' email for segment '%s'.", customer_segment
    )

    try:
        email_body = ""
        if "email" in offer_json:
            email_body = offer_json["email"]
        elif "Email" in offer_json:
            email_body = format_for_email(# pylint: disable=unexpected-keyword-arg
                offer_json["Email"],
                customer_name,
                user_name,
                _company_name=company_name,
            )
        else:
            return (
                "Error: The 'offer_json' dictionary provided to"
                "'draft_and_send_email' is missing both 'email' and 'Email'"
                "keys. Please ensure the correct marketing content is passed."
            )

        if image_path:
            email_body += (
                f'\n\n<img src="{image_path}" alt="Product Image"'
                ' style="width:100%;max-width:600px;">'
            )
        if website_url:
            email_body += f"\n\nLearn more at: {website_url}"

        segment_name = customer_segment

        email_data = {
            "to": f"{segment_name} Email List",
            "subject": f"A Special Offer for our {segment_name} Customers!",
            "body": email_body,
        }

        log.info(
            "Email campaign for segment '%s' has been 'sent'.",
            customer_segment,
        )

        return json.dumps(email_data)

    except Exception as e:# pylint: disable=broad-exception-caught
        log.error("Error drafting and sending email: %s", e)
        return f"Error: Failed to draft and send email. {e}"


def create_marketing_document(
    agent_response_text: str, filename: str = "agent_text_output"
) -> str:
    """
    Creates a professionally formatted PDF file from a string of text.

    Args:
        agent_response_text: A string containing the entire content to be
                             formatted into the PDF.
        filename: The base name for the output file (e.g.,
                  "marketing_plan_q3").

    Returns:
        The GCS URI of the final, uploaded PDF document.

    """
    # --- Sanitize Input ---
    agent_response_text = re.sub(r"<[^>]*>", "", agent_response_text)
    base_name_no_ext = os.path.splitext(os.path.basename(filename))[0]
    doc_filename = base_name_no_ext.replace(" ", "_").lower() + ".pdf"

    output_dir = "output/documents"
    os.makedirs(output_dir, exist_ok=True)
    local_file_path = os.path.join(output_dir, doc_filename)

    # --- Color Scheme Definition ---
    # Primary: #0074C7 (Blue) - For Titles
    primary_color = HexColor("#0074C7")
    # Heading 4: #06477C (Darker Blue) - For Main Headers
    heading_h4_color = HexColor("#06477C")
    # Text Primary: #0F2744 (Dark blue) - For all body/list text
    main_text_color = HexColor("#0F2744")
    # Secondary: #6E7087 (Grayish blue) - For Header/Footer text
    secondary_color = HexColor("#6E7087")
    # Grayscale 400: #C6C9D1 - For Header/Footer lines
    header_line_color = HexColor("#C6C9D1")

    # --- Setup ReportLab Document ---
    document = SimpleDocTemplate(
        local_file_path,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    styles = getSampleStyleSheet()
    story: List[object] = []

    # --- Custom Styles ---
    styles.add(
        ParagraphStyle(
            name="TitlePage",
            parent=styles["h1"],
            fontSize=36,
            leading=42,
            alignment=TA_CENTER,
            textColor=primary_color,
            spaceAfter=24,
            fontName="Helvetica-Bold",
        )
    )

    styles.add(
        ParagraphStyle(
            name="MainHeader",
            parent=styles["h1"],
            fontSize=24,
            leading=28,
            # alignment=TA_CENTER,
            # textColor=primary_color,
            alignment=TA_LEFT,  # Alignment set to left for modern look
            textColor=heading_h4_color,  # Darker Blue Color
            spaceAfter=18,
            fontName="Helvetica-Bold",
        )
    )

    styles.add(
        ParagraphStyle(
            name="SubHeader",
            parent=styles["h2"],
            fontSize=16,
            leading=20,
            textColor=heading_h4_color,
            spaceBefore=12,  # <--- ADD THIS
            spaceAfter=12,
            fontName="Helvetica-Bold",
        )
    )

    styles.add(
        ParagraphStyle(
            name="ListBullet",
            parent=styles["Normal"],
            fontName="Helvetica",
            leftIndent=36,
            bulletIndent=18,
            spaceBefore=1,
            spaceAfter=1,
            alignment=TA_LEFT,
            textColor=main_text_color,
        )
    )

    styles.add(
        ParagraphStyle(
            name="NormalParagraph",
            parent=styles["Normal"],
            fontName="Helvetica",
            spaceBefore=6,
            spaceAfter=6,
            alignment=TA_LEFT,
            textColor=main_text_color,
            fontSize=11,
            leading=14,
        )
    )

    # --- Header and Footer ---
    def _header(canvas, _):
        canvas.saveState()
        # 1. Draw Logo
        title_x_offset = inch

        # 2. Draw Document Title
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(secondary_color)
        canvas.drawString(
            title_x_offset, 10.5 * inch, "Marketing Strategy Document"
        )

        # 3. Draw Separator Line
        canvas.setStrokeColor(header_line_color)
        canvas.setLineWidth(0.5)
        canvas.line(
            inch, 10.4 * inch, (8.5 - inch), 10.4 * inch
        )  # 8.5 is page width

        canvas.restoreState()

    def _footer(canvas, doc): # pylint: disable=unused-variable
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(secondary_color)
        canvas.drawString(inch, 0.75 * inch, f"Page {doc.page}")

        # Draw a line above the footer text
        canvas.setStrokeColor(header_line_color)
        canvas.setLineWidth(0.5)
        canvas.line(inch, 0.85 * inch, (8.5 - inch), 0.85 * inch)

        canvas.restoreState()

    # --- Text Preprocessing (Handle Bold and Italics) ---
    reportlab_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", agent_response_text)
    reportlab_text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", reportlab_text)

    # --- Process and Render Content Blocks ---
    lines = reportlab_text.split("\n")
    current_list_items = []
    current_list_type = None

    def finalize_list():
        nonlocal current_list_items, current_list_type
        if current_list_items:
            # Check if list items contain any ReportLab recognized markup.
            list_paragraphs = []
            for item in current_list_items:
                # Use Paragraph to handle bold/italics in list items
                list_paragraphs.append(
                    ListItem(Paragraph(item, styles["ListBullet"]))
                )
            list_params = (
                {"bulletType": "1"}
                if current_list_type == "numbered"
                else {
                    "bulletType": "bullet",
                    "start": "bulletchar",
                    "bulletChar": "•",
                }
            )
            story.append(
                ListFlowable(
                    list_paragraphs,
                    leftIndent=36,
                    bulletIndent=18,
                    **list_params,
                )
            )
            current_list_items = []
            current_list_type = None
            story.append(Spacer(1, 6))

    numbered_list_pattern = re.compile(r"^\s*\d+\.\s+")

    # --- Title Page ---
    title = "Marketing Strategy Proposal"  # Default title
    if lines and lines[0].startswith("# "):
        title = lines[0].replace("# ", "", 1).strip()

    story.append(Paragraph(title, styles["TitlePage"]))
    story.append(Spacer(1, 2 * inch))

    # --- Main Content ---
    for line in lines:
        line = line.strip()
        if not line:
            finalize_list()
            continue

        if line.startswith("# "):
            finalize_list()

            # Use a left-aligned MainHeader (h1)
            p_style = styles["MainHeader"]
            p_style.alignment = TA_LEFT
            story.append(Paragraph(line.replace("# ", "", 1), p_style))
            story.append(Spacer(1, 18))
        elif line.startswith("## "):
            finalize_list()
            if "Recommended Suppliers" in line:
                try:
                    suppliers_json = line.split("\n", 1)[1]
                    suppliers_data = json.loads(suppliers_json)
                    for supplier in suppliers_data["suppliers"]:
                        story.append(
                            Paragraph(
                                f"<b>{supplier["name"]}</b>",
                                styles["SubHeader"],
                            )
                        )
                        story.append(
                            Paragraph(
                                supplier["address"], styles["NormalParagraph"]
                            )
                        )
                        story.append(
                            Paragraph(
                                f'<a href="{supplier["maps_url"]}">View'
                                " Map</a>",
                                styles["NormalParagraph"],
                            )
                        )
                        story.append(Spacer(1, 12))
                except (IndexError, json.JSONDecodeError) as e:
                    logger.error("Error parsing suppliers JSON: %s", e)
                    story.append(
                        Paragraph(line, styles["SubHeader"])
                    )  # Fallback to printing the raw line
            else:
                story.append(
                    Paragraph(line.replace("## ", "", 1), styles["SubHeader"])
                )
                story.append(Spacer(1, 12))

        elif line.startswith("### "):
            finalize_list()
            story.append(Paragraph(line.replace("### ", "", 1), styles["h3"]))
            story.append(Spacer(1, 8))
        elif line.startswith("* ") or line.startswith("- "):
            list_type = "bullet"
            text = line[2:].strip()
            if current_list_type and current_list_type != list_type:
                finalize_list()
            current_list_type = list_type
            current_list_items.append(text)

        elif numbered_list_pattern.match(line):
            list_type = "numbered"
            text = numbered_list_pattern.sub("", line).strip()
            if current_list_type and current_list_type != list_type:
                finalize_list()
            current_list_type = list_type
            current_list_items.append(text)
        else:
            finalize_list()
            story.append(Paragraph(line, styles["NormalParagraph"]))

    finalize_list()

    # --- Build Document ---
    try:
        document.build(story, onFirstPage=_header, onLaterPages=_header)
        logger.info("Marketing document created at: %s", local_file_path)

        # Upload to GCS
        if not GCS_BUCKET_NAME:
            raise ValueError("GCS_BUCKET_NAME environment variable is not set.")
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f"documents/{doc_filename}")
        blob.upload_from_filename(local_file_path)
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/documents/{doc_filename}"
        logger.info("Successfully uploaded marketing document to %s", gcs_uri)

        return gcs_uri

    except Exception as e: # pylint: disable=broad-exception-caught
        logger.error("Error building PDF: %s", e)
        return f"Error: Could not generate PDF. {e}"
