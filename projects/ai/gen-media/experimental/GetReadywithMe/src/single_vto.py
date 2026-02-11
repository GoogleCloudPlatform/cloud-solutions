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

# Single Product VTO Module - Real-Time Processing Only
# Virtual Try-On using live API calls - no pre-stored content
"""Single product VTO module using live API calls."""

import base64
import io
import logging
import os
import time
from datetime import datetime

import streamlit as st
from google.genai import types
from google.genai.types import Image as GenAIImage
from google.genai.types import (
    ProductImage,
    RecontextImageConfig,
    RecontextImageSource,
)
from PIL import Image

logger = logging.getLogger(__name__)


class SingleVTOTab:
    """Single Product Virtual Try-On - ALL REAL-TIME API CALLS"""

    def resize_image_for_display(
        self, image_bytes, max_width=700, max_height=900
    ):
        """Resize image to fixed size container.

        High quality - used for thumbnails.
        """
        img = Image.open(io.BytesIO(image_bytes))

        # Convert RGBA to RGB if needed (for compatibility)
        if img.mode == 'RGBA':
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode not in ['RGB', 'L']:
            img = img.convert('RGB')

        aspect_ratio = img.width / img.height
        target_ratio = max_width / max_height

        if aspect_ratio > target_ratio:
            new_width = max_width
            new_height = int(max_width / aspect_ratio)
        else:
            new_height = max_height
            new_width = int(max_height * aspect_ratio)

        img = img.resize(
            (new_width, new_height), Image.Resampling.LANCZOS
        )

        canvas = Image.new(
            'RGB', (max_width, max_height), (255, 255, 255)
        )
        x = (max_width - new_width) // 2
        y = (max_height - new_height) // 2
        canvas.paste(img, (x, y))

        output = io.BytesIO()
        canvas.save(
            output, format='PNG', optimize=True, quality=100
        )
        return output.getvalue()

    def render_output_image(self, image_bytes, height=650):
        """Render output image large and consistent.

        Uses HTML - bypasses Streamlit sizing issues.
        """
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode == 'RGBA':
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode not in ['RGB', 'L']:
            img = img.convert('RGB')

        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode()

        st.markdown(
            '<div style="width:100%; '
            f'height:{height}px; '
            'display:flex; '
            'align-items:center; '
            'justify-content:center; '
            'background:white; '
            'border:1px solid #e0e0e0; '
            'border-radius:8px; '
            'padding:8px; '
            'box-sizing:border-box;">'
            '<img src="data:image/jpeg;base64,'
            f'{b64}" '
            'style="max-width:100%; '
            'max-height:100%; '
            'object-fit:contain;" />'
            '</div>',
            unsafe_allow_html=True,
        )

    def __init__(
        self,
        storage_client,
        genai_client,
        gemini3_client=None,
        project_id=None,
    ):
        self.storage_client = storage_client
        self.genai_client = genai_client
        # For handbag addition using Pro 3.0
        self.gemini3_client = gemini3_client
        self.project_id = project_id
        self.bucket_name = os.getenv(
            'GCS_BUCKET_NAME', 'lj-vto-demo'
        )

        # VTO model name for recontext_image
        self.vto_model = (
            'virtual-try-on-preview-08-04'
        )

        # Initialize session state for real-time VTO
        if 'vto_results' not in st.session_state:
            st.session_state.vto_results = []
        if 'vto_model_image' not in st.session_state:
            st.session_state.vto_model_image = None
        if 'vto_product_image' not in st.session_state:
            st.session_state.vto_product_image = None
        if 'vto_current_result' not in st.session_state:
            st.session_state.vto_current_result = None
        if 'vto_with_shoes' not in st.session_state:
            st.session_state.vto_with_shoes = None
        if 'vto_final_result' not in st.session_state:
            st.session_state.vto_final_result = None
        if 'selected_shoe' not in st.session_state:
            st.session_state.selected_shoe = None
        if 'selected_handbag' not in st.session_state:
            st.session_state.selected_handbag = None
        if 'selected_shoe_name' not in st.session_state:
            st.session_state.selected_shoe_name = None
        state = st.session_state
        if 'selected_handbag_name' not in state:
            state.selected_handbag_name = None
        if 'selected_model_id' not in state:
            state.selected_model_id = None
        if 'selected_model_name' not in state:
            state.selected_model_name = None
        if 'selected_product_id' not in state:
            state.selected_product_id = None
        if 'selected_product_name' not in state:
            state.selected_product_name = None

    def perform_realtime_vto(
        self, model_bytes, product_bytes
    ):
        """Perform real-time virtual try-on."""
        try:
            # Create GenAI Image objects from bytes
            person_image = GenAIImage(
                image_bytes=model_bytes
            )
            product_img = GenAIImage(
                image_bytes=product_bytes
            )

            # Call recontext_image API - REAL-TIME
            response = (
                self.genai_client.models.recontext_image(
                    model=self.vto_model,
                    source=RecontextImageSource(
                        person_image=person_image,
                        product_images=[
                            ProductImage(
                                product_image=product_img
                            )
                        ],
                    ),
                    config=RecontextImageConfig(
                        output_mime_type='image/jpeg',
                        number_of_images=1,
                        safety_filter_level=(
                            'BLOCK_LOW_AND_ABOVE'
                        ),
                    ),
                )
            )

            # Extract result
            if (
                response.generated_images
                and len(response.generated_images) > 0
            ):
                result_image = (
                    response.generated_images[0].image
                )

                # Get the image bytes
                if hasattr(result_image, 'image_bytes'):
                    return result_image.image_bytes
                if hasattr(
                    result_image, '_image_bytes'
                ):
                    return result_image._image_bytes  # pylint: disable=protected-access
                return result_image

            return None

        except (ValueError, RuntimeError, OSError) as e:
            st.error(f'VTO API Error: {str(e)}')
            return None

    def perform_batch_vto(
        self,
        model_bytes,
        product_bytes,
        num_variations=4,
    ):
        """Generate multiple VTO variations."""
        try:

            # Create GenAI Image objects
            person_image = GenAIImage(
                image_bytes=model_bytes
            )
            product_img = GenAIImage(
                image_bytes=product_bytes
            )

            # Call API with multiple outputs
            response = (
                self.genai_client.models.recontext_image(
                    model=self.vto_model,
                    source=RecontextImageSource(
                        person_image=person_image,
                        product_images=[
                            ProductImage(
                                product_image=product_img
                            )
                        ],
                    ),
                    config=RecontextImageConfig(
                        output_mime_type='image/jpeg',
                        number_of_images=num_variations,
                        safety_filter_level=(
                            'BLOCK_LOW_AND_ABOVE'
                        ),
                    ),
                )
            )

            # Extract all results
            results = []
            if response.generated_images:
                for img in response.generated_images:
                    if hasattr(
                        img.image, 'image_bytes'
                    ):
                        results.append(
                            img.image.image_bytes
                        )
                    elif hasattr(
                        img.image, '_image_bytes'
                    ):
                        results.append(
                            img.image._image_bytes  # pylint: disable=protected-access
                        )
                    else:
                        results.append(img.image)

            return results

        except (ValueError, RuntimeError, OSError) as e:
            st.error(
                f'Batch VTO Error: {str(e)}'
            )
            return []

    def render(self):
        """Render the Single VTO tab - ALL REAL-TIME"""

        # Add CSS for styling
        st.markdown(
            """
        <style>
            .vto-result-card {
                background: white;
                border-radius: 15px;
                padding: 1rem;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                margin-bottom: 1rem;
            }

            .upload-zone {
                border: 3px dashed #667eea;
                border-radius: 20px;
                padding: 2rem;
                text-align: center;
                background: linear-gradient(
                    135deg,
                    #667eea05 0%,
                    #764ba205 100%
                );
                transition: all 0.3s ease;
            }

            .upload-zone:hover {
                border-color: #764ba2;
                background: linear-gradient(
                    135deg,
                    #667eea10 0%,
                    #764ba210 100%
                );
            }

            /* Result image containers */
            .result-images .stImage {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 4px;
                background: white;
            }
        </style>
        """,
            unsafe_allow_html=True,
        )

        # Main layout
        col1, col2 = st.columns(2)

        # Model Selection/Upload
        with col1:
            st.markdown('###  Model Selection')
            st.markdown(
                '<p style="color: #FFD700; '
                'font-size: 0.9rem; '
                'margin-top: -10px;">'
                'Select ONE model only</p>',
                unsafe_allow_html=True,
            )

            model_source = st.radio(
                'Model Source',
                ['Use Generated Models', 'Upload New'],
                horizontal=True,
                help=(
                    'Use models from Model Creation '
                    'tab or upload your own'
                ),
            )

            if model_source == 'Upload New':
                st.markdown(
                    '<div class="upload-zone">',
                    unsafe_allow_html=True,
                )
                uploaded_model = st.file_uploader(
                    'Upload Model Image',
                    type=['png', 'jpg', 'jpeg'],
                    key='vto_model_upload',
                    help=(
                        'Upload a full-body model image'
                    ),
                )
                st.markdown(
                    '</div>',
                    unsafe_allow_html=True,
                )

                if uploaded_model:
                    model_bytes = (
                        uploaded_model.getvalue()
                    )
                    st.session_state.vto_model_image = (
                        model_bytes
                    )

                    # Display uploaded model
                    resized_img = (
                        self.resize_image_for_display(
                            model_bytes,
                            max_width=200,
                            max_height=280,
                        )
                    )
                    st.image(
                        Image.open(
                            io.BytesIO(resized_img)
                        ),
                        caption='Uploaded Model',
                        width=200,
                    )

                    # Show file info
                    size_kb = (
                        len(model_bytes) / 1024
                    )
                    st.caption(
                        f'{uploaded_model.name}'
                        f' | {size_kb:.1f} KB'
                    )

            else:  # Use Generated Models
                # Load models from GCS
                try:
                    bucket = (
                        self.storage_client.bucket(
                            self.bucket_name
                        )
                    )
                    model_prefix = (
                        'beauty/vto/models/'
                    )

                    # List all model images from GCS
                    blobs = list(
                        bucket.list_blobs(
                            prefix=model_prefix
                        )
                    )

                    model_images = []
                    for blob in blobs:
                        exts = (
                            '.png', '.jpg', '.jpeg'
                        )
                        is_img = blob.name.endswith(
                            exts
                        )
                        is_dir = blob.name.endswith(
                            '/'
                        )
                        if is_img and not is_dir:
                            filename = (
                                blob.name.split('/')
                                [-1]
                            )
                            is_model = (
                                filename.lower()
                                .startswith('model')
                            )
                            if is_model:
                                metadata = (
                                    blob.metadata or {}
                                )
                                model_images.append(
                                    {
                                        'blob': blob,
                                        'name': (
                                            filename
                                        ),
                                        'metadata': (
                                            metadata
                                        ),
                                        'created_at': (
                                            blob
                                            .time_created
                                        ),
                                    }
                                )

                    # Sort by name for consistent order
                    model_images.sort(
                        key=lambda x: x['name']
                    )

                    if model_images:
                        # Model selection grid
                        model_cols = st.columns(5)

                        for idx, model_info in (
                            enumerate(
                                model_images[:5]
                            )
                        ):
                            with model_cols[idx % 5]:
                                self._render_model(
                                    idx, model_info
                                )
                    else:
                        st.warning(
                            'No models found in '
                            'gallery. Please generate'
                            ' models in the Model '
                            'Creation tab first.'
                        )

                except (
                    ValueError,
                    RuntimeError,
                    OSError,
                ) as e:
                    st.error(
                        'Error loading models '
                        'from gallery: '
                        f'{str(e)}'
                    )
                    st.warning(
                        'No generated models '
                        'available. Please generate'
                        ' models in the Model '
                        'Creation tab first.'
                    )

        # Product Selection/Upload
        with col2:
            st.markdown('###  Product Selection')
            st.markdown(
                '<p style="color: #FFD700; '
                'font-size: 0.9rem; '
                'margin-top: -10px;">'
                'Select ONE product only</p>',
                unsafe_allow_html=True,
            )

            # Invisible placeholder to match height
            st.markdown(
                '<div style="height: 58px;"></div>',
                unsafe_allow_html=True,
            )

            # Load products from GCS
            product_prefix = (
                'inputs/single_vto/products/'
            )

            try:
                # Get product images from GCS
                bucket = (
                    self.storage_client.bucket(
                        self.bucket_name
                    )
                )
                blobs = list(
                    bucket.list_blobs(
                        prefix=product_prefix
                    )
                )

                # Filter for image files
                product_images = []
                for blob in blobs:
                    exts = (
                        '.png', '.jpg', '.jpeg'
                    )
                    is_img = blob.name.endswith(
                        exts
                    )
                    is_dir = blob.name.endswith('/')
                    if is_img and not is_dir:
                        product_images.append(
                            {
                                'name': (
                                    blob.name
                                    .split('/')[-1]
                                ),
                                'blob': blob,
                            }
                        )

                if product_images:
                    self._render_products(
                        product_images
                    )
                else:
                    self._render_product_upload(
                        'vto_product_upload_main'
                    )

            except (
                ValueError,
                RuntimeError,
                OSError,
            ) as e:
                st.error(
                    'Error loading products: '
                    f'{str(e)}'
                )
                self._render_product_upload(
                    'vto_product_upload_fallback',
                    max_width=320,
                    max_height=450,
                )

        # VTO Processing Section
        st.markdown('---')

        if (
            st.session_state.vto_model_image
            and st.session_state.vto_product_image
        ):
            self._process_vto()

        # Show results and accessories section
        if st.session_state.get(
            'vto_current_result'
        ):
            self._render_results()

        else:
            st.info(
                'Please select/upload both a model '
                'and a garment to proceed with '
                'virtual try-on'
            )

    def _render_model(self, idx, model_info):
        """Render a single model in the grid."""
        try:
            # Download image from GCS
            model_bytes = (
                model_info['blob']
                .download_as_bytes()
            )

            # Create simple caption
            name_lower = (
                model_info['name'].lower()
            )
            if 'model_0' in name_lower:
                caption = f'Model {idx + 1}'
            else:
                caption = (
                    model_info['name']
                    .replace('model_', 'Model ')
                    .replace('.png', '')
                    .replace('.jpg', '')
                    .replace('_', ' ')[:20]
                )

            # Display thumbnail
            resized_img = (
                self.resize_image_for_display(
                    model_bytes,
                    max_width=200,
                    max_height=280,
                )
            )
            st.image(
                Image.open(
                    io.BytesIO(resized_img)
                ),
                caption=caption,
                width=200,
            )

            # Select button with visual feedback
            is_selected = (
                st.session_state.get(
                    'selected_model_id'
                )
                == f'model_{idx}'
            )

            if is_selected:
                st.markdown('**Selected**')
            else:
                if st.button(
                    'Select',
                    key=f'select_model_vto_{idx}',
                ):
                    state = st.session_state
                    state.vto_model_image = (
                        model_bytes
                    )
                    state.selected_model_id = (
                        f'model_{idx}'
                    )
                    state.selected_model_index = (
                        idx
                    )
                    state.selected_model_name = (
                        caption
                    )
                    state.selected_model_filename = (
                        model_info['name']
                    )
                    st.rerun()

        except (
            ValueError,
            RuntimeError,
            OSError,
        ) as e:
            st.error(
                f'Error loading model: {str(e)}'
            )

    def _render_products(self, product_images):
        """Render product gallery."""
        # Display products in a 5-column grid
        product_cols = st.columns(5)

        for idx, product in enumerate(
            product_images[:5]
        ):
            with product_cols[idx % 5]:
                # Download product image
                product_bytes = (
                    product['blob']
                    .download_as_bytes()
                )

                # Create a container
                with st.container():
                    # Display product
                    resized_img = (
                        self.resize_image_for_display(
                            product_bytes,
                            max_width=200,
                            max_height=280,
                        )
                    )
                    cap = (
                        product['name']
                        .split('.')[0][:15]
                    )
                    st.image(
                        Image.open(
                            io.BytesIO(resized_img)
                        ),
                        caption=cap,
                        width=200,
                    )

                    # Select button
                    is_selected = (
                        st.session_state.get(
                            'selected_product_id'
                        )
                        == f'product_{idx}'
                    )

                    if is_selected:
                        st.markdown('**Selected**')
                    else:
                        if st.button(
                            'Select',
                            key=(
                                f'select_product'
                                f'_{idx}'
                            ),
                        ):
                            state = st.session_state
                            state.vto_product_image = (
                                product_bytes
                            )
                            state.selected_product_id = (
                                f'product_{idx}'
                            )
                            state.selected_product_index = (
                                idx
                            )
                            state.selected_product_name = (
                                product['name']
                            )
                            st.rerun()

        # Upload option
        with st.expander(
            'Or upload your own product'
        ):
            uploaded_product = st.file_uploader(
                'Upload Garment Image',
                type=['png', 'jpg', 'jpeg'],
                key='vto_product_upload',
                help=(
                    'Upload a garment/product image'
                    ' on plain background'
                ),
            )

            if uploaded_product:
                product_bytes = (
                    uploaded_product.getvalue()
                )
                st.session_state.vto_product_image = (
                    product_bytes
                )
                resized_img = (
                    self.resize_image_for_display(
                        product_bytes,
                        max_width=200,
                        max_height=280,
                    )
                )
                st.image(
                    Image.open(
                        io.BytesIO(resized_img)
                    ),
                    caption='Uploaded Product',
                    width=200,
                )

    def _render_product_upload(
        self,
        key,
        max_width=200,
        max_height=280,
    ):
        """Render product upload section."""
        st.markdown(
            '<div class="upload-zone">',
            unsafe_allow_html=True,
        )
        uploaded_product = st.file_uploader(
            'Upload Garment Image',
            type=['png', 'jpg', 'jpeg'],
            key=key,
            help=(
                'Upload a garment/product image'
                ' on plain background'
            ),
        )
        st.markdown(
            '</div>',
            unsafe_allow_html=True,
        )

        if uploaded_product:
            product_bytes = (
                uploaded_product.getvalue()
            )
            st.session_state.vto_product_image = (
                product_bytes
            )
            resized_img = (
                self.resize_image_for_display(
                    product_bytes,
                    max_width=max_width,
                    max_height=max_height,
                )
            )
            st.image(
                Image.open(
                    io.BytesIO(resized_img)
                ),
                caption='Selected Garment',
                width=200,
            )

    def _process_vto(self):
        """Process VTO button actions."""
        # Process and Clear buttons
        col_btn1, col_btn2 = st.columns([3, 1])

        with col_btn1:
            process_button = st.button(
                'Try-On',
                type='primary',
                key='single_vto_process_btn',
            )

        with col_btn2:
            clear_button = st.button(
                'Clear All',
                type='secondary',
                key='single_vto_clear_btn',
            )

        if clear_button:
            self._clear_all_state()

        if process_button:
            with st.spinner(
                'Processing virtual try-on...'
            ):
                start_time = datetime.now()

                # Perform VTO
                result = self.perform_realtime_vto(
                    st.session_state.vto_model_image,
                    st.session_state.vto_product_image,
                )

                if result:
                    self._save_vto_result(
                        result, start_time
                    )

    def _clear_all_state(self):
        """Clear all selections and results."""
        state = st.session_state
        state.vto_model_image = None
        state.vto_product_image = None
        state.vto_results = []
        state.vto_current_result = None
        state.vto_with_shoes = None
        state.vto_final_result = None
        state.selected_shoe = None
        state.selected_handbag = None
        state.selected_shoe_name = None
        state.selected_handbag_name = None
        state.selected_model_id = None
        state.selected_model_name = None
        state.selected_product_id = None
        state.selected_product_name = None
        st.rerun()

    def _save_vto_result(self, result, start_time):
        """Save VTO result to GCS and session."""
        processing_time = (
            (datetime.now() - start_time)
            .total_seconds()
        )

        # Save to GCS
        timestamp = datetime.now().strftime(
            '%Y%m%d_%H%M%S'
        )
        result_path = (
            'outputs/single_vto/results/'
            f'vto_result_{timestamp}.png'
        )

        bucket = self.storage_client.bucket(
            self.bucket_name
        )
        blob = bucket.blob(result_path)
        blob.upload_from_string(
            result, content_type='image/png'
        )

        gcs_uri = (
            f'gs://{self.bucket_name}/{result_path}'
        )

        # Store result
        vto_result = {
            'result_bytes': result,
            'timestamp': datetime.now(),
            'processing_time': processing_time,
            'mode': 'single',
            'gcs_uri': gcs_uri,
        }

        if 'vto_results' not in st.session_state:
            st.session_state.vto_results = []
        st.session_state.vto_results.append(
            vto_result
        )

        # Store current result
        st.session_state.vto_current_result = result

        # Save dress VTO result
        timestamp = datetime.now().strftime(
            '%Y%m%d_%H%M%S'
        )
        result_path = (
            'outputs/single_vto/results/'
            f'dress_vto_{timestamp}.png'
        )

        bucket = self.storage_client.bucket(
            self.bucket_name
        )
        blob = bucket.blob(result_path)
        blob.upload_from_string(
            result, content_type='image/png'
        )

    def _render_results(self):
        """Render results and accessories."""
        # Display results - always visible
        st.markdown('### Results')

        col1_res, col2_res, col3_res = st.columns(3)

        with col1_res:
            st.markdown('**Original Model**')
            self.render_output_image(
                st.session_state.vto_model_image
            )

        with col2_res:
            st.markdown('**Selected Garment**')
            self.render_output_image(
                st.session_state.vto_product_image
            )

        with col3_res:
            st.markdown('**VTO Result**')
            self.render_output_image(
                st.session_state.vto_current_result
            )

            # Download button
            ts = datetime.now().strftime(
                '%Y%m%d_%H%M%S'
            )
            st.download_button(
                label='Save Result',
                data=(
                    st.session_state
                    .vto_current_result
                ),
                file_name=f'vto_result_{ts}.jpg',
                mime='image/jpeg',
            )

        st.markdown('---')

        # Initialize session state
        state = st.session_state
        if 'selected_shoe_name' not in state:
            state.selected_shoe_name = None
        if 'selected_handbag_name' not in state:
            state.selected_handbag_name = None
        if 'vto_with_shoes' not in state:
            state.vto_with_shoes = None
        if 'vto_final_result' not in state:
            state.vto_final_result = None

        # Access parent scope variables
        storage_client = self.storage_client
        bucket_name = self.bucket_name
        _genai_client = self.genai_client  # pylint: disable=unused-variable
        gemini3_client = self.gemini3_client

        # Load accessories
        bucket = storage_client.bucket(bucket_name)

        # Load shoes
        shoes_list = self._load_accessories(
            bucket,
            'inputs/single_vto/shoes/',
        )

        # Step 1: Shoes Selection
        st.markdown('### Step 1: Add Shoes')

        if shoes_list:
            self._render_shoes(
                shoes_list,
                storage_client,
                bucket_name,
            )
        else:
            st.warning('No shoes available')

        # Display results with shoes
        if st.session_state.get('vto_with_shoes'):
            self._render_shoe_results(
                bucket,
                storage_client,
                bucket_name,
                gemini3_client,
            )

        # Display final complete look
        if st.session_state.get('vto_final_result'):
            self._render_final_look()

    def _load_accessories(self, bucket, prefix):
        """Load accessory items from GCS."""
        items_list = []
        for blob in bucket.list_blobs(
            prefix=prefix
        ):
            exts = ['.png', '.jpg', '.jpeg']
            has_ext = any(
                blob.name.lower().endswith(ext)
                for ext in exts
            )
            if (
                not blob.name.endswith('/')
                and has_ext
            ):
                try:
                    item_bytes = (
                        blob.download_as_bytes()
                    )
                    if item_bytes:
                        item_name = (
                            blob.name.split('/')[-1]
                            .rsplit('.', 1)[0]
                        )
                        items_list.append(
                            {
                                'name': item_name,
                                'bytes': item_bytes,
                            }
                        )
                except (OSError, RuntimeError):
                    continue
        return items_list

    def _render_shoes(
        self,
        shoes_list,
        storage_client,
        bucket_name,
    ):
        """Render shoes selection grid."""
        shoe_cols = st.columns(
            min(len(shoes_list), 4)
        )

        for idx, shoe in enumerate(shoes_list[:4]):
            with shoe_cols[idx]:
                # Display shoe image
                resized_img = (
                    self.resize_image_for_display(
                        shoe['bytes'],
                        max_width=200,
                        max_height=280,
                    )
                )
                st.image(
                    Image.open(
                        io.BytesIO(resized_img)
                    ),
                    width=200,
                )
                st.caption(shoe['name'])

                # Show status or button
                selected_name = (
                    st.session_state
                    .selected_shoe_name
                )
                if selected_name == shoe['name']:
                    st.success('Applied')
                else:
                    btn_key = f'shoe_btn_{idx}'
                    if st.button(
                        'Select', key=btn_key
                    ):
                        self._apply_shoe(
                            idx,
                            shoe,
                            storage_client,
                            bucket_name,
                        )

    def _apply_shoe(
        self,
        idx,
        shoe,
        storage_client,
        bucket_name,
    ):
        """Apply shoe to VTO result."""
        name = shoe['name']
        with st.spinner(
            f'Applying {name}...'
        ):
            try:
                # Try preloaded result first
                shoe_result = None
                shoe_num = idx + 1
                preloaded_path = (
                    'demo/single_output/'
                    f'with_shoes_{shoe_num}.png'
                )

                try:
                    blob = (
                        self.storage_client
                        .bucket(self.bucket_name)
                        .blob(preloaded_path)
                    )
                    if blob.exists():
                        shoe_result = (
                            blob.download_as_bytes()
                        )

                        # Save preloaded result
                        ts = (
                            datetime.now().strftime(
                                '%Y%m%d_%H%M%S'
                            )
                        )
                        shoe_path = (
                            'outputs/single_vto/'
                            'results/'
                            'with_shoes_preloaded_'
                            f'{ts}.png'
                        )

                        bucket = (
                            self.storage_client
                            .bucket(
                                self.bucket_name
                            )
                        )
                        blob = bucket.blob(
                            shoe_path
                        )
                        blob.upload_from_string(
                            shoe_result,
                            content_type=(
                                'image/png'
                            ),
                        )
                except (OSError, RuntimeError):
                    pass

                if not shoe_result:
                    shoe_result = (
                        self._call_shoe_vto_api(
                            shoe
                        )
                    )

                if shoe_result:
                    state = st.session_state
                    state.vto_with_shoes = (
                        shoe_result
                    )
                    state.selected_shoe_name = (
                        shoe['name']
                    )

                    # Save to GCS
                    ts = datetime.now().strftime(
                        '%Y%m%d_%H%M%S'
                    )
                    shoe_result_path = (
                        'outputs/single_vto/'
                        'results/'
                        f'with_shoes_{ts}.png'
                    )

                    bucket = (
                        storage_client.bucket(
                            bucket_name
                        )
                    )
                    blob = bucket.blob(
                        shoe_result_path
                    )
                    blob.upload_from_string(
                        shoe_result,
                        content_type='image/png',
                    )

                    _gcs_path = (  # pylint: disable=unused-variable
                        f'gs://{bucket_name}/'
                        f'{shoe_result_path}'
                    )
            except (
                ValueError,
                RuntimeError,
                OSError,
            ) as e:
                st.error(f'Error: {str(e)}')

    def _call_shoe_vto_api(self, shoe):
        """Call VTO API for shoes."""
        try:
            # pylint: disable=import-outside-toplevel,reimported,redefined-outer-name
            from google.genai.types import Image as GenAIImage
            from google.genai.types import (
                ProductImage,
                RecontextImageConfig,
                RecontextImageSource,
            )

            # Create GenAI Image objects
            person_image = GenAIImage(
                image_bytes=(
                    st.session_state
                    .vto_current_result
                ),
            )
            shoe_img = GenAIImage(
                image_bytes=shoe['bytes']
            )

            # Call VTO recontext_image API
            response = (
                self.genai_client
                .models.recontext_image(
                    model=self.vto_model,
                    source=RecontextImageSource(
                        person_image=person_image,
                        product_images=[
                            ProductImage(
                                product_image=(
                                    shoe_img
                                )
                            )
                        ],
                    ),
                    config=RecontextImageConfig(
                        output_mime_type=(
                            'image/jpeg'
                        ),
                        number_of_images=1,
                        safety_filter_level=(
                            'BLOCK_LOW_AND_ABOVE'
                        ),
                    ),
                )
            )

            # Extract result
            if (
                response.generated_images
                and len(
                    response.generated_images
                ) > 0
            ):
                result_image = (
                    response
                    .generated_images[0].image
                )

                # Get the image bytes
                if hasattr(
                    result_image, 'image_bytes'
                ):
                    return (
                        result_image.image_bytes
                    )
                if hasattr(
                    result_image, '_image_bytes'
                ):
                    return (
                        result_image._image_bytes  # pylint: disable=protected-access
                    )
                return result_image

            return (
                st.session_state
                .vto_current_result
            )

        except (
            ValueError,
            RuntimeError,
            OSError,
        ) as e:
            st.error(
                'VTO API Error for shoes: '
                f'{str(e)}'
            )
            return (
                st.session_state
                .vto_current_result
            )

    def _render_shoe_results(
        self,
        bucket,
        storage_client,
        bucket_name,
        gemini3_client,
    ):
        """Render shoe results and handbag."""
        st.markdown('#### Shoe Applied')

        # Use equal columns
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('**Dress Only**')
            self.render_output_image(
                st.session_state.vto_current_result
            )
        with col2:
            shoe_name = st.session_state.get(
                'selected_shoe_name', 'Shoe'
            )
            st.markdown(f'**With {shoe_name}**')
            self.render_output_image(
                st.session_state.vto_with_shoes
            )

        # Step 2: Handbag Selection
        st.markdown('---')
        st.markdown('### Step 2: Add Handbag')

        # Load handbags
        handbags_list = self._load_accessories(
            bucket,
            'inputs/single_vto/handbag/',
        )

        if handbags_list:
            self._render_handbags(
                handbags_list,
                storage_client,
                bucket_name,
                gemini3_client,
            )
        else:
            st.warning('No handbags available')

    def _render_handbags(
        self,
        handbags_list,
        storage_client,
        bucket_name,
        gemini3_client,
    ):
        """Render handbag selection grid."""
        bag_cols = st.columns(
            min(len(handbags_list), 4)
        )

        for idx, bag in enumerate(
            handbags_list[:4]
        ):
            with bag_cols[idx]:
                # Display handbag image
                resized_img = (
                    self.resize_image_for_display(
                        bag['bytes'],
                        max_width=200,
                        max_height=280,
                    )
                )
                st.image(
                    Image.open(
                        io.BytesIO(resized_img)
                    ),
                    width=200,
                )
                st.caption(bag['name'])

                # Show status or button
                selected = (
                    st.session_state
                    .selected_handbag_name
                )
                if selected == bag['name']:
                    st.success('Applied')
                else:
                    btn_key = f'bag_btn_{idx}'
                    if st.button(
                        'Select', key=btn_key
                    ):
                        self._apply_handbag(
                            idx,
                            bag,
                            storage_client,
                            bucket_name,
                            gemini3_client,
                        )

    def _apply_handbag(
        self,
        idx,
        bag,
        storage_client,
        bucket_name,
        gemini3_client,
    ):
        """Apply handbag to VTO result."""
        with st.spinner('Processing...'):
            try:
                # Try preloaded result first
                final_result = None
                bag_num = idx + 1
                preloaded_path = (
                    'demo/single_output/'
                    f'final_look_{bag_num}.png'
                )

                try:
                    blob = (
                        self.storage_client
                        .bucket(self.bucket_name)
                        .blob(preloaded_path)
                    )
                    if blob.exists():
                        final_result = (
                            blob.download_as_bytes()
                        )

                        # Save preloaded result
                        ts = (
                            datetime.now()
                            .strftime(
                                '%Y%m%d_%H%M%S'
                            )
                        )
                        final_path = (
                            'outputs/single_vto/'
                            'final_look/'
                            'complete_preloaded_'
                            f'{ts}.png'
                        )

                        bucket = (
                            self.storage_client
                            .bucket(
                                self.bucket_name
                            )
                        )
                        blob = bucket.blob(
                            final_path
                        )
                        blob.upload_from_string(
                            final_result,
                            content_type=(
                                'image/png'
                            ),
                        )
                except (OSError, RuntimeError):
                    pass

                if not final_result:
                    final_result = (
                        self._generate_handbag(
                            bag, gemini3_client
                        )
                    )

                if final_result:
                    state = st.session_state
                    state.vto_final_result = (
                        final_result
                    )
                    state.selected_handbag_name = (
                        bag['name']
                    )

                    # Save final result
                    ts = datetime.now().strftime(
                        '%Y%m%d_%H%M%S'
                    )
                    final_path = (
                        'outputs/single_vto/'
                        'final_look/'
                        f'complete_{ts}.png'
                    )

                    bucket = (
                        storage_client.bucket(
                            bucket_name
                        )
                    )
                    blob = bucket.blob(final_path)
                    blob.upload_from_string(
                        final_result,
                        content_type='image/png',
                    )

            except (
                ValueError,
                RuntimeError,
                OSError,
            ) as e:
                st.error(
                    f'Error: {str(e)}'
                )

    def _generate_handbag(
        self, bag, gemini3_client
    ):
        """Generate handbag addition."""
        prompt = (
            'Add this handbag to the person\'s '
            'hand in the image.\n\n'
            'CRITICAL REQUIREMENTS:\n'
            '- Keep EVERYTHING exactly the same: '
            'person, face, outfit, shoes, pose, '
            'background\n'
            '- ONLY change: add the handbag being '
            'held naturally in one hand\n'
            '- The person should be holding/'
            'carrying the handbag in a natural '
            'way\n'
            '- Do NOT change the person\'s '
            'posture, position, or stance\n'
            '- Do NOT change facial features or '
            'expression\n'
            '- Do NOT change the outfit or shoes\n'
            '- Keep the exact same background\n'
            '- Make the handbag integration look '
            'natural and realistic\n'
            '- The handbag should be clearly '
            'visible'
        )

        try:
            # Call Gemini Pro 3.0
            state = st.session_state
            input_image = (
                state.vto_with_shoes
                or state.vto_current_result
            )
            response = (
                gemini3_client
                .models.generate_content(
                    model=(
                        'gemini-3-pro-'
                        'image-preview'
                    ),
                    contents=[
                        types.Part.from_bytes(
                            data=input_image,
                            mime_type='image/png',
                        ),
                        types.Part.from_bytes(
                            data=bag['bytes'],
                            mime_type='image/png',
                        ),
                        types.Part.from_text(
                            text=prompt
                        ),
                    ],
                    config=(
                        types
                        .GenerateContentConfig(
                            temperature=0.1,
                            response_modalities=[
                                'IMAGE'
                            ],
                            safety_settings=[
                                types.SafetySetting(
                                    category=(
                                        'HARM_CATEGORY'
                                        '_HATE_SPEECH'
                                    ),
                                    threshold='OFF',
                                ),
                                types.SafetySetting(
                                    category=(
                                        'HARM_CATEGORY'
                                        '_DANGEROUS'
                                        '_CONTENT'
                                    ),
                                    threshold='OFF',
                                ),
                                types.SafetySetting(
                                    category=(
                                        'HARM_CATEGORY'
                                        '_SEXUALLY'
                                        '_EXPLICIT'
                                    ),
                                    threshold='OFF',
                                ),
                                types.SafetySetting(
                                    category=(
                                        'HARM_CATEGORY'
                                        '_HARASSMENT'
                                    ),
                                    threshold='OFF',
                                ),
                            ],
                        )
                    ),
                )
            )

            # Extract result
            if (
                response.candidates
                and response.candidates[0]
                .content.parts
            ):
                for part in (
                    response.candidates[0]
                    .content.parts
                ):
                    if (
                        part.inline_data
                        and part.inline_data.data
                    ):
                        return (
                            part.inline_data.data
                        )

            st.error(
                'Failed to add handbag - '
                'no response from model'
            )
            return None

        except (
            ValueError,
            RuntimeError,
            OSError,
        ) as e:
            logger.error(
                'Error adding handbag with '
                'Gemini: %s', e
            )
            # Fallback to using current result
            return st.session_state.get(
                'vto_with_shoes',
                st.session_state.vto_current_result,
            )

    def _render_final_look(self):
        """Render the final complete look."""
        st.markdown('---')
        st.markdown('### Complete Look')

        final_cols = st.columns(3)

        # Center-crop all images to 3:4 portrait
        target_w, target_h = 600, 800
        target_ratio = target_w / target_h

        def render_same_size(image_bytes):
            """Center-crop to 3:4 portrait."""
            img = Image.open(
                io.BytesIO(image_bytes)
            )
            if img.mode == 'RGBA':
                bg = Image.new(
                    'RGB',
                    img.size,
                    (255, 255, 255),
                )
                bg.paste(
                    img, mask=img.split()[3]
                )
                img = bg
            elif img.mode not in ['RGB', 'L']:
                img = img.convert('RGB')

            current_ratio = (
                img.width / img.height
            )
            if current_ratio > target_ratio:
                # Wider than 3:4 - crop sides
                new_w = int(
                    img.height * target_ratio
                )
                left = (img.width - new_w) // 2
                img = img.crop(
                    (
                        left,
                        0,
                        left + new_w,
                        img.height,
                    )
                )
            else:
                # Taller than 3:4 - crop top/bot
                new_h = int(
                    img.width / target_ratio
                )
                top = (img.height - new_h) // 2
                img = img.crop(
                    (
                        0,
                        top,
                        img.width,
                        top + new_h,
                    )
                )

            # Resize to exact dimensions
            img = img.resize(
                (target_w, target_h),
                Image.Resampling.LANCZOS,
            )

            buf = io.BytesIO()
            img.save(
                buf, format='JPEG', quality=90
            )
            b64 = base64.b64encode(
                buf.getvalue()
            ).decode()
            st.markdown(
                '<div style="width:100%; '
                'border:1px solid #e0e0e0; '
                'border-radius:8px; '
                'overflow:hidden;">'
                '<img src="data:image/jpeg;'
                f'base64,{b64}" '
                'style="width:100%; '
                'display:block;" />'
                '</div>',
                unsafe_allow_html=True,
            )

        with final_cols[0]:
            st.markdown('**Dress Only**')
            render_same_size(
                st.session_state
                .vto_current_result
            )

        with final_cols[1]:
            st.markdown('**With Shoes**')
            if st.session_state.get(
                'vto_with_shoes'
            ):
                render_same_size(
                    st.session_state.vto_with_shoes
                )

        with final_cols[2]:
            st.markdown('**Complete Look**')
            render_same_size(
                st.session_state.vto_final_result
            )

        # Buttons
        button_cols = st.columns(2)
        with button_cols[0]:
            ts = datetime.now().strftime(
                '%Y%m%d_%H%M%S'
            )
            st.download_button(
                label='Download Complete Look',
                data=(
                    st.session_state
                    .vto_final_result
                ),
                file_name=(
                    f'complete_look_{ts}.jpg'
                ),
                mime='image/jpeg',
                use_container_width=True,
            )

        with button_cols[1]:
            if st.button(
                'Reset Accessories',
                key='clear_accessories',
            ):
                keys_to_clear = [
                    'vto_with_shoes',
                    'vto_final_result',
                    'selected_shoe_name',
                    'selected_handbag_name',
                    'veo_video_url',
                    'veo_generation_started',
                ]
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        # Bring to Life Section with Veo
        st.markdown('---')
        st.markdown(
            '### Bring to Life - Rampwalk Video'
        )

        self._render_veo_section()

    def _render_veo_section(self):
        """Render the Veo video generation."""
        # Initialize session state for Veo
        if 'veo_video_url' not in st.session_state:
            st.session_state.veo_video_url = None
        if (
            'veo_generation_started'
            not in st.session_state
        ):
            st.session_state.veo_generation_started = (
                False
            )
        if (
            'veo_operation'
            not in st.session_state
        ):
            st.session_state.veo_operation = None

        # Generate video button
        if not st.session_state.veo_generation_started:
            if st.button(
                'Bring to Life',
                type='primary',
                key='generate_veo_single',
            ):
                st.session_state.veo_generation_started = (
                    True
                )
                self._generate_veo_video()

        # Display video if available
        if st.session_state.get('veo_video_url'):
            self._display_veo_video()
        elif (
            st.session_state.veo_generation_started
            and st.session_state.get(
                'veo_operation'
            )
        ):
            self._check_veo_status()

    def _generate_veo_video(self):
        """Generate Veo rampwalk video."""
        with st.spinner(
            'Generating... This may take '
            '2-3 minutes.'
        ):
            try:
                # pylint: disable=import-outside-toplevel,reimported,redefined-outer-name
                from google.genai.types import (
                    GenerateVideosConfig,
                )
                from google.genai.types import Image as GenAIImage

                # Pre-process image to 9:16
                img = Image.open(
                    io.BytesIO(
                        st.session_state
                        .vto_final_result
                    )
                )
                target_ratio = 9 / 16
                current_ratio = (
                    img.width / img.height
                )

                if current_ratio > target_ratio:
                    new_height = 1920
                    scale = (
                        new_height / img.height
                    )
                    new_width = int(
                        img.width * scale
                    )
                else:
                    new_width = 1080
                    scale = (
                        new_width / img.width
                    )
                    new_height = int(
                        img.height * scale
                    )

                img_resized = img.resize(
                    (new_width, new_height),
                    Image.Resampling.LANCZOS,
                )
                canvas = Image.new(
                    'RGB', (1080, 1920), 'white'
                )
                paste_x = (
                    (1080 - new_width) // 2
                )
                paste_y = (
                    (1920 - new_height) // 2
                )
                canvas.paste(
                    img_resized,
                    (paste_x, paste_y),
                )

                processed_buf = io.BytesIO()
                canvas.save(
                    processed_buf, format='PNG'
                )
                processed_bytes = (
                    processed_buf.getvalue()
                )

                # Upload processed image to GCS
                ts = datetime.now().strftime(
                    '%Y%m%d_%H%M%S'
                )
                temp_path = (
                    'temp/single_vto/'
                    f'final_look_{ts}.png'
                )
                output_gcs_uri = (
                    f'gs://{self.bucket_name}/'
                    'outputs/single_vto/video/'
                )

                bucket = (
                    self.storage_client.bucket(
                        self.bucket_name
                    )
                )
                blob = bucket.blob(temp_path)
                blob.upload_from_string(
                    processed_bytes,
                    content_type='image/png',
                )

                # Video generation prompt
                video_prompt = (
                    'The model walks elegantly '
                    'towards the camera on a '
                    'clean fashion runway. '
                    'Smooth, confident stride '
                    'with natural arm swing and '
                    'gentle hair movement. '
                    'Show the full outfit from '
                    'head to toe as she walks '
                    'forward gracefully. '
                    'IMPORTANT: Preserve the '
                    'model\'s exact body type, '
                    'body shape, facial features,'
                    ' and all clothing details '
                    'from the reference image. '
                    'Do NOT alter the model\'s '
                    'face, body proportions, or '
                    'outfit in any way. '
                    'Natural fabric motion as '
                    'she walks. Clean white '
                    'runway background. '
                    'Professional fashion show '
                    'feel with elegant, poised '
                    'movement.'
                )

                # Generate video using Veo API
                gcs_uri = (
                    f'gs://{self.bucket_name}'
                    f'/{temp_path}'
                )
                op = (
                    self.genai_client
                    .models.generate_videos(
                        model=(
                            'veo-3.0-generate-001'
                        ),
                        prompt=video_prompt,
                        image=GenAIImage(
                            gcs_uri=gcs_uri,
                            mime_type='image/png',
                        ),
                        config=(
                            GenerateVideosConfig(
                                aspect_ratio='9:16',
                                output_gcs_uri=(
                                    output_gcs_uri
                                ),
                                number_of_videos=1,
                            )
                        ),
                    )
                )

                st.session_state.veo_operation = op

                # Poll for completion
                max_wait = 300  # 5 minutes
                wait_time = 0

                while (
                    not op.done
                    and wait_time < max_wait
                ):
                    time.sleep(15)
                    wait_time += 15
                    op = (
                        self.genai_client
                        .operations.get(op)
                    )

                # Clean up temp file
                try:
                    blob.delete()
                except (OSError, RuntimeError):
                    pass

                if not op.done:
                    st.session_state.veo_operation = (
                        op
                    )
                    st.warning(
                        'Video generation is '
                        'taking longer than '
                        'expected. Click '
                        '\'Check Status\' to '
                        'retry.'
                    )
                elif (
                    op.response
                    and op.result
                    and op.result.generated_videos
                ):
                    self._handle_veo_result(
                        op, bucket
                    )
                else:
                    st.error(
                        'Video generation failed.'
                        ' Please try again.'
                    )
                    st.session_state.veo_generation_started = (
                        False
                    )

            except (
                ValueError,
                RuntimeError,
                OSError,
            ) as e:
                st.error(
                    'Error generating video: '
                    f'{str(e)}'
                )
                st.session_state.veo_generation_started = (
                    False
                )

    def _handle_veo_result(self, op, bucket):
        """Handle successful Veo result."""
        video_uri = (
            op.result
            .generated_videos[0].video.uri
        )
        # Download video from GCS
        video_gcs_path = video_uri.replace(
            f'gs://{self.bucket_name}/', ''
        )
        video_blob = bucket.blob(
            video_gcs_path
        )
        video_bytes = (
            video_blob.download_as_bytes()
        )

        # Convert to base64 for display
        video_b64 = base64.b64encode(
            video_bytes
        ).decode()
        st.session_state.veo_video_url = (
            'data:video/mp4;base64,'
            f'{video_b64}'
        )
        st.session_state.veo_video_b64 = (
            video_b64
        )

        st.success(
            'Video generated successfully!'
        )

    def _display_veo_video(self):
        """Display the generated Veo video."""
        st.markdown('#### Your Rampwalk Video')

        video_url = (
            st.session_state.veo_video_url
        )
        # Check if we have base64 video or URL
        if video_url.startswith('data:'):
            # Display video
            st.markdown(
                '<div style="display:flex; '
                'justify-content:center; '
                'margin:20px auto; '
                'max-width:500px;">'
                '<div style="width:100%; '
                'border-radius:10px; '
                'overflow:hidden; '
                'box-shadow:0 4px 6px '
                'rgba(0,0,0,0.1); '
                'background:white;">'
                '<video style="width:100%; '
                'display:block; '
                'background:white;" '
                'controls autoplay loop muted>'
                '<source src="'
                f'{video_url}" '
                'type="video/mp4">'
                'Your browser does not support '
                'the video tag.'
                '</video>'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            # Display video with URL
            st.video(video_url)

        # Regenerate button
        if st.button(
            'Generate New Video',
            key='regenerate_veo',
        ):
            state = st.session_state
            state.veo_generation_started = False
            state.veo_video_url = None
            state.veo_operation = None
            st.rerun()

    def _check_veo_status(self):
        """Check Veo operation status."""
        op = st.session_state.veo_operation
        try:
            op = self.genai_client.operations.get(
                op
            )
            st.session_state.veo_operation = op
        except (OSError, RuntimeError):
            pass
        if not op.done:
            st.info(
                'Video generation in progress...'
                ' This typically takes 2-3 '
                'minutes. Please wait.'
            )
            if st.button(
                'Check Status',
                key='check_veo_status',
            ):
                st.rerun()
        else:
            try:
                if (
                    op.response
                    and op.result
                    and op.result.generated_videos
                ):
                    video_uri = (
                        op.result
                        .generated_videos[0]
                        .video.uri
                    )
                    bucket = (
                        self.storage_client
                        .bucket(self.bucket_name)
                    )
                    video_gcs_path = (
                        video_uri.replace(
                            'gs://'
                            f'{self.bucket_name}/',
                            '',
                        )
                    )
                    video_blob = bucket.blob(
                        video_gcs_path
                    )
                    video_bytes = (
                        video_blob
                        .download_as_bytes()
                    )

                    video_b64 = (
                        base64.b64encode(
                            video_bytes
                        ).decode()
                    )
                    st.session_state.veo_video_url = (
                        'data:video/mp4;base64,'
                        f'{video_b64}'
                    )
                    st.session_state.veo_video_b64 = (
                        video_b64
                    )
                    st.rerun()
                else:
                    st.error(
                        'Video generation failed.'
                        ' Please try again.'
                    )
                    st.session_state.veo_generation_started = (
                        False
                    )
            except (
                ValueError,
                RuntimeError,
                OSError,
            ) as e:
                st.error(
                    'Error checking video '
                    f'status: {str(e)}'
                )
                st.session_state.veo_generation_started = (
                    False
                )
