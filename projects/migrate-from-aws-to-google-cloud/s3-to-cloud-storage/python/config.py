# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This module contains the configuration for the Gemini API.

It defines various constants used throughout the application, including:
- GEMINI_RECOMMENDATION_PROMPT: The template for the prompt sent to the
 Gemini model.
- GEMINI_MODEL: Specifies the particular Gemini model to be utilized.
- GEMINI_USER_AGENT: A user agent string for identifying API requests made
 to Gemini.
- EXTERNAL_CONTEXT_URL: A URL from which additional context for migration
 recommendations is fetched.
"""

# The prompt template for generating Gemini recommendations.
GEMINI_RECOMMENDATION_PROMPT = """
You are a cloud infrastructure consultant analyzing an AWS S3 inventory
 for a client.
Your task is to create a detailed migration recommendation.

## CLIENT INVENTORY DATA
{inventory_data}

## GOOGLE CLOUD MIGRATION CONTEXT
{external_context}

## YOUR TASK
Create a single markdown table with the following columns:

*   **Bucket Name**
*   **Number of Objects**
*   **Total Size**
*   **Enabled S3 Features**
*   **Migration Recommendation**

The `Enabled S3 Features` column should be a bullet point list of the enabled features for the S3 bucket.
The `Migration Recommendation` column should provide concise, bullet-point recommendations for migrating the S3 bucket to Google Cloud Storage, leveraging *only* the provided Google Cloud Migration Context.
"""

# The Gemini model to use for generating recommendations.
GEMINI_MODEL = "gemini-2.5-flash"
# The user agent to use when making Gemini API calls.
GEMINI_USER_AGENT = "cloud-solutions/mmb-s3-inventory-v1"
# The URL to fetch external context from for Gemini recommendations.
EXTERNAL_CONTEXT_URL = (
    "https://cloud.google.com/architecture/migrate-amazon-s3-to-cloud-storage"
)
