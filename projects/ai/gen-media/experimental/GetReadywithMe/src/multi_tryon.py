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

# Multi Try-On Module - Preloaded Results
# Displays preloaded VTO results and videos from GCS
'''Multi Try-On module with preloaded VTO results.'''

import base64
import io
import os

import streamlit as st
from google.api_core import exceptions as api_exceptions
from PIL import Image


class MultiTryOnTab:
    '''Multi Virtual Try-On with Preloaded Results'''

    def __init__(self, storage_client, genai_client, project_id):
        self.storage_client = storage_client
        self.genai_client = genai_client
        self.project_id = project_id
        self.bucket_name = os.getenv(
            'GCS_BUCKET_NAME', 'lj-vto-demo'
        )

        # Preloaded paths
        self.models_path = 'beauty/vto/models/'
        self.products_path = 'beauty/vto/multi_vto/'
        self.results_path = 'demo/multi_output/'
        self.videos_path = 'beauty/vto/multi_motion/'

        # Initialize session state
        if 'multi_selected_models' not in st.session_state:
            st.session_state.multi_selected_models = []
        if 'multi_selected_products' not in st.session_state:
            st.session_state.multi_selected_products = []
        if 'multi_show_results' not in st.session_state:
            st.session_state.multi_show_results = False

    def resize_image_for_display(
        self, image_bytes, max_width=250, max_height=350
    ):
        '''Resize image for thumbnails.'''
        try:
            img = Image.open(io.BytesIO(image_bytes))

            if img.mode == 'RGBA':
                bg = Image.new(
                    'RGB', img.size, (255, 255, 255)
                )
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
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )

            canvas = Image.new(
                'RGB',
                (max_width, max_height),
                (255, 255, 255)
            )
            x = (max_width - new_width) // 2
            y = (max_height - new_height) // 2
            canvas.paste(img, (x, y))

            output = io.BytesIO()
            canvas.save(
                output, format='PNG',
                optimize=True, quality=100
            )
            return output.getvalue()
        except (OSError, ValueError):
            return image_bytes

    def render_output_image(self, image_bytes, height=450):
        '''Render output image using HTML.'''
        try:
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode == 'RGBA':
                bg = Image.new(
                    'RGB', img.size, (255, 255, 255)
                )
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode not in ['RGB', 'L']:
                img = img.convert('RGB')

            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=90)
            b64 = base64.b64encode(
                buf.getvalue()
            ).decode()

            div_style = (
                'width:100%; '
                f'height:{height}px; '
                'display:flex; '
                'align-items:center; '
                'justify-content:center; '
                'background:white; '
                'border:1px solid #e0e0e0; '
                'border-radius:8px; '
                'padding:4px; '
                'box-sizing:border-box;'
            )
            img_style = (
                'max-width:100%; '
                'max-height:100%; '
                'object-fit:contain;'
            )
            img_src = f'data:image/jpeg;base64,{b64}'
            html = (
                f'<div style="{div_style}">'
                f'<img src="{img_src}" '
                f'style="{img_style}" />'
                '</div>'
            )

            st.markdown(html, unsafe_allow_html=True)
        except (OSError, ValueError):
            st.image(
                Image.open(io.BytesIO(image_bytes)),
                use_container_width=True
            )

    def load_preloaded_models(self):
        '''Load models from beauty/vto/models/.'''
        models = []
        try:
            bucket = self.storage_client.bucket(
                self.bucket_name
            )
            blobs = list(
                bucket.list_blobs(prefix=self.models_path)
            )

            for blob in blobs:
                extensions = ('.png', '.jpg', '.jpeg')
                if not blob.name.endswith(extensions):
                    continue
                if blob.name.endswith('/'):
                    continue
                filename = blob.name.split('/')[-1]

                # Only include files starting with "model"
                if not filename.lower().startswith('model'):
                    continue

                # Try to extract model number
                model_num = None
                if 'model_0' in filename:
                    model_num = int(
                        filename.split('model_0')[1][0]
                    )
                elif 'model' in filename.lower():
                    try:
                        parts = filename.lower().split(
                            'model'
                        )[1]
                        for char in parts:
                            if char.isdigit():
                                model_num = int(char)
                                break
                    except (ValueError, IndexError):
                        pass

                fallback = len(models) + 1
                num = model_num if model_num else fallback
                models.append({
                    'name': f'Model {num}',
                    'blob': blob,
                    'filename': filename,
                    'number': num
                })

            # Sort by model number, newest first
            models.sort(
                key=lambda x: (
                    x['number'],
                    -x['blob'].time_created
                    .timestamp()
                )
            )

            # Deduplicate by model number
            seen_numbers = set()
            unique_models = []
            for m in models:
                if m['number'] not in seen_numbers:
                    seen_numbers.add(m['number'])
                    unique_models.append(m)

            return unique_models[:5]

        except (
            api_exceptions.GoogleAPICallError,
            api_exceptions.RetryError,
            ValueError,
        ) as e:
            st.error(f'Error loading models: {e!s}')
            return []

    def load_preloaded_products(self):
        '''Load products from beauty/vto/multi_vto/.'''
        products = []
        try:
            bucket = self.storage_client.bucket(
                self.bucket_name
            )
            blobs = list(
                bucket.list_blobs(
                    prefix=self.products_path
                )
            )

            for blob in blobs:
                extensions = ('.png', '.jpg', '.jpeg')
                if not blob.name.endswith(extensions):
                    continue
                if blob.name.endswith('/'):
                    continue
                filename = blob.name.split('/')[-1]
                product_name = (
                    filename.split('.')[0]
                    .replace('_', ' ')
                    .title()
                )

                products.append({
                    'name': product_name,
                    'blob': blob,
                    'filename': filename
                })

            return products

        except (
            api_exceptions.GoogleAPICallError,
            api_exceptions.RetryError,
            ValueError,
        ) as e:
            st.error(
                f'Error loading products: {e!s}'
            )
            return []

    def find_result_image(self, model_num, product_name):
        '''Find preloaded result for model-product.'''
        try:
            bucket = self.storage_client.bucket(
                self.bucket_name
            )

            product_key = (
                product_name.lower().replace(' ', '')
            )

            if model_num < 10:
                model_str = f'model_{model_num:02d}'
            else:
                model_str = f'model_{model_num}'

            blobs = list(
                bucket.list_blobs(
                    prefix=self.results_path
                )
            )

            for blob in blobs:
                if blob.name.endswith('.png'):
                    blob_lower = blob.name.lower()
                    if (model_str in blob.name
                            and product_key in blob_lower):
                        return blob.download_as_bytes()

            return None

        except (
            api_exceptions.GoogleAPICallError,
            api_exceptions.RetryError,
            ValueError,
        ):
            return None

    def find_video(self, model_num, product_name):
        '''Find preloaded video for model-product.'''
        try:
            bucket = self.storage_client.bucket(
                self.bucket_name
            )

            product_key = (
                product_name.lower().replace(' ', '')
            )

            if model_num < 10:
                model_str_zero = (
                    f'model_{model_num:02d}'
                )
            else:
                model_str_zero = (
                    f'model_{model_num}'
                )
            model_str_simple = f'model{model_num}'

            blobs = list(
                bucket.list_blobs(
                    prefix=self.videos_path
                )
            )

            for blob in blobs:
                if blob.name.endswith('.mp4'):
                    blob_name = blob.name.lower()

                    has_model = (
                        model_str_zero in blob_name
                        or model_str_simple in blob_name
                        or f'm{model_num}' in blob_name
                        or f'_0{model_num}_' in blob_name
                        or f'_{model_num}_' in blob_name
                    )

                    product_underscore = (
                        product_name.lower()
                        .replace(' ', '_')
                    )
                    has_product = (
                        product_key in blob_name
                        or product_underscore in blob_name
                    )

                    if has_model and has_product:
                        return blob.download_as_bytes()

            return None

        except (
            api_exceptions.GoogleAPICallError,
            api_exceptions.RetryError,
            ValueError,
        ):
            return None

    def render(self):
        '''Render Multi Try-On tab.'''

        # Add CSS for styling
        st.markdown('''
        <style>
            /* Column spacing for better layout */
            [data-testid="column"] {
                padding: 0 3px !important;
            }

            .element-container {
                margin-bottom: 0.5rem !important;
            }

            /* Crop black bars from videos */
            [data-testid="stVideo"] {
                aspect-ratio: 3/4;
                overflow: hidden;
                border-radius: 8px;
            }
            [data-testid="stVideo"] video {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
        </style>
        ''', unsafe_allow_html=True)

        # Load preloaded models and products
        models = self.load_preloaded_models()
        products = self.load_preloaded_products()

        if not models or not products:
            st.warning(
                'No preloaded models or products found'
            )
            return

        # Main layout
        col1, col2 = st.columns(2)

        # Model Gallery
        with col1:
            st.markdown('### Model Gallery')

            # Select All checkbox for models
            select_all_models = st.checkbox(
                'Select All Models',
                key='multi_select_all_models'
            )

            # Display all 5 models in a single row
            model_cols = st.columns(5)

            st.session_state.multi_selected_models = []

            for idx, model in enumerate(models):
                with model_cols[idx]:
                    try:
                        model_bytes = (
                            model['blob'].download_as_bytes()
                        )
                        display_bytes = (
                            self.resize_image_for_display(
                                model_bytes
                            )
                        )

                        img = Image.open(
                            io.BytesIO(display_bytes)
                        )
                        st.image(
                            img,
                            caption=model['name'],
                            width=250,
                            output_format='PNG'
                        )

                        if select_all_models:
                            selected = {
                                'name': model['name'],
                                'blob': model['blob'],
                                'filename': (
                                    model['filename']
                                ),
                                'number': (
                                    model['number']
                                ),
                                'bytes': model_bytes
                            }
                            st.session_state \
                                .multi_selected_models \
                                .append(selected)

                    except (
                        OSError,
                        ValueError,
                        api_exceptions
                        .GoogleAPICallError,
                    ) as e:
                        st.error(
                            'Error loading model:'
                            f' {e!s}'
                        )

        # Product Gallery
        with col2:
            st.markdown('### Product Gallery')

            # Select All checkbox for products
            select_all_products = st.checkbox(
                'Select All Products',
                key='multi_select_all_products'
            )

            st.session_state.multi_selected_products = []

            num_products_to_show = min(
                5, len(products)
            )
            product_cols = st.columns(
                num_products_to_show
            )

            for idx, product in enumerate(
                products[:num_products_to_show]
            ):
                with product_cols[idx]:
                    try:
                        product_bytes = (
                            product['blob']
                            .download_as_bytes()
                        )
                        display_bytes = (
                            self.resize_image_for_display(
                                product_bytes
                            )
                        )

                        img = Image.open(
                            io.BytesIO(display_bytes)
                        )
                        st.image(
                            img,
                            caption=(
                                product['name'][:15]
                            ),
                            width=250,
                            output_format='PNG'
                        )

                        if select_all_products:
                            selected = {
                                'name': (
                                    product['name']
                                ),
                                'blob': (
                                    product['blob']
                                ),
                                'filename': (
                                    product['filename']
                                ),
                                'bytes': product_bytes
                            }
                            st.session_state \
                                .multi_selected_products \
                                .append(selected)

                    except (
                        OSError,
                        ValueError,
                        api_exceptions
                        .GoogleAPICallError,
                    ) as e:
                        st.error(
                            'Error loading product:'
                            f' {e!s}'
                        )

            # If more than 5 products, show second row
            if len(products) > 5:
                st.markdown('---')
                remaining = products[5:10]
                product_cols2 = st.columns(
                    min(5, len(remaining))
                )

                for idx, product in enumerate(
                    remaining
                ):
                    with product_cols2[idx]:
                        try:
                            product_bytes = (
                                product['blob']
                                .download_as_bytes()
                            )
                            display_bytes = (
                                self
                                .resize_image_for_display(
                                    product_bytes
                                )
                            )

                            img = Image.open(
                                io.BytesIO(
                                    display_bytes
                                )
                            )
                            st.image(
                                img,
                                caption=(
                                    product['name'][:15]
                                ),
                                width=250,
                                output_format='PNG'
                            )

                            if select_all_products:
                                selected = {
                                    'name': (
                                        product['name']
                                    ),
                                    'blob': (
                                        product['blob']
                                    ),
                                    'filename': (
                                        product[
                                            'filename'
                                        ]
                                    ),
                                    'bytes': (
                                        product_bytes
                                    )
                                }
                                st.session_state \
                                    .multi_selected_products \
                                    .append(selected)

                        except (
                            OSError,
                            ValueError,
                            api_exceptions
                            .GoogleAPICallError,
                        ) as e:
                            st.error(
                                'Error loading'
                                ' product:'
                                f' {e!s}'
                            )

        # Process Section
        st.markdown('---')

        # Show results button if selections made
        selected_models = (
            st.session_state.multi_selected_models
        )
        selected_products = (
            st.session_state.multi_selected_products
        )
        if selected_models and selected_products:
            num_combinations = (
                len(selected_models)
                * len(selected_products)
            )

            col_btn1, col_btn2 = st.columns([3, 1])

            with col_btn1:
                btn_label = (
                    f'View {num_combinations}'
                    ' Combinations'
                )
                if st.button(
                    btn_label,
                    type='primary',
                    key='view_results_btn'
                ):
                    st.session_state \
                        .multi_show_results = True

            with col_btn2:
                if st.button(
                    'Clear All',
                    type='secondary',
                    key='clear_all_btn'
                ):
                    st.session_state \
                        .multi_selected_models = []
                    st.session_state \
                        .multi_selected_products = []
                    st.session_state \
                        .multi_show_results = False
                    st.rerun()

            # Display results if button clicked
            if st.session_state.multi_show_results:
                st.markdown('### VTO Results')
                st.caption('Virtual try-on results')

                for m_idx, model in enumerate(
                    selected_models
                ):
                    model_name = model['name']
                    st.markdown(
                        f'#### {model_name}'
                    )

                    cols = st.columns(
                        len(selected_products) + 1
                    )

                    # Show original model
                    with cols[0]:
                        st.markdown('**Original**')
                        self.render_output_image(
                            model['bytes']
                        )

                    for idx, product in enumerate(
                        selected_products
                    ):
                        with cols[idx + 1]:
                            name = (
                                product['name'][:12]
                            )
                            st.markdown(
                                f'**{name}**'
                            )

                            result_bytes = (
                                self.find_result_image(
                                    model['number'],
                                    product['name']
                                )
                            )
                            if result_bytes:
                                self \
                                    .render_output_image(
                                        result_bytes
                                    )

                                m_name = (
                                    model['name']
                                )
                                p_name = (
                                    product['name']
                                )
                                fname = (
                                    f'{m_name}'
                                    f'_{p_name}.png'
                                )
                                st.download_button(
                                    label='Save',
                                    data=result_bytes,
                                    file_name=fname,
                                    mime='image/png',
                                    key=(
                                        'dl_m'
                                        f'{m_idx}'
                                        f'_{idx}'
                                    )
                                )
                            else:
                                st.info(
                                    'Result not'
                                    ' available'
                                )

                    st.markdown('---')

                # Bring to Life Section
                st.markdown(
                    '### Bring to Life'
                    ' - Rampwalk Video'
                )

                if (
                    'multi_show_videos'
                    not in st.session_state
                ):
                    st.session_state \
                        .multi_show_videos = False

                if st.button(
                    'Bring to Life',
                    type='primary',
                    key='bring_to_life_btn'
                ):
                    st.session_state \
                        .multi_show_videos = True

                if st.session_state.get(
                    'multi_show_videos'
                ):
                    # Display videos for Model 1 only
                    model_1 = next(
                        (m for m in selected_models
                         if m['number'] == 1),
                        None
                    )
                    if not model_1:
                        model_1 = selected_models[0]

                    st.markdown(
                        f"##### {model_1['name']}"
                    )

                    num_prods = len(
                        selected_products
                    )
                    videos_per_row = 5
                    num_rows = (
                        (
                            num_prods
                            + videos_per_row
                            - 1
                        )
                        // videos_per_row
                    )

                    for row in range(num_rows):
                        s_idx = (
                            row * videos_per_row
                        )
                        e_idx = min(
                            s_idx
                            + videos_per_row,
                            num_prods
                        )
                        num_in_row = (
                            e_idx - s_idx
                        )

                        video_cols = st.columns(
                            num_in_row
                        )

                        for c_idx, p_idx in (
                            enumerate(
                                range(
                                    s_idx,
                                    e_idx
                                )
                            )
                        ):
                            product = (
                                selected_products[
                                    p_idx
                                ]
                            )

                            with video_cols[
                                c_idx
                            ]:
                                p_name = (
                                    product[
                                        'name'
                                    ][:15]
                                )
                                st.caption(
                                    p_name
                                )

                                video_bytes = (
                                    self
                                    .find_video(
                                        model_1[
                                            'number'
                                        ],
                                        product[
                                            'name'
                                        ]
                                    )
                                )
                                if video_bytes:
                                    st.video(
                                        video_bytes,
                                        autoplay=True,
                                        loop=True,
                                        muted=True
                                    )

                                    m_name = (
                                        model_1[
                                            'name'
                                        ]
                                    )
                                    p_nm = (
                                        product[
                                            'name'
                                        ]
                                    )
                                    vfn = (
                                        f'{m_name}'
                                        f'_{p_nm}'
                                        '.mp4'
                                    )
                                    hlp = (
                                        'Download'
                                        f' {m_name}'
                                        ' -'
                                        f' {p_nm}'
                                    )
                                    st.download_button(
                                        label=(
                                            'Save'
                                        ),
                                        data=(
                                            video_bytes
                                        ),
                                        file_name=(
                                            vfn
                                        ),
                                        mime=(
                                            'video'
                                            '/mp4'
                                        ),
                                        key=(
                                            'dl_'
                                            'vid_'
                                            'm0'
                                            '_'
                                            f'{p_idx}'
                                        ),
                                        help=hlp
                                    )
                                else:
                                    st.info(
                                        'Video'
                                        ' not'
                                        ' available'
                                    )

                    st.markdown('---')

        else:
            st.info(
                'Please select models and products'
                ' to view combinations'
            )
