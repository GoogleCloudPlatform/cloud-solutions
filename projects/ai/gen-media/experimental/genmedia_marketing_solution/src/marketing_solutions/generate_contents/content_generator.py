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
GenMedia Marketing Solution Module - Content.
"""

import json
import logging
import os
from typing import Dict, List, Optional

import vertexai
from dotenv import load_dotenv
from vertexai.generative_models import (
    GenerationConfig,
    GenerativeModel,
    HarmBlockThreshold,
    HarmCategory,
)

# --- Load environment variables ---
load_dotenv()


class ContentGenerator:
    """
    A class for generating various types of marketing content
    using generative AI model.

    This class provides methods for generating customer segments,
    outreach strategies,and marketing offers. It initializes the
    Vertex AI client and loads the necessary configuration from
    environment variables.
    """

    def __init__(self):
        """
        Initializes the ContentGenerator.

        This constructor performs several key setup operations:
        1.  Logging: Establishes a logger for tracking the
            generator's operations.
        2.  Configuration: Loads essential credentials and model
            details from environment variables.
        3.  Vertex AI Initialization: Connects to the Vertex AI service.
        4.  Model Loading: Instantiates the specified generative model.
        5.  Safety Settings: Configures content safety thresholds to
            prevent the generation of harmful or inappropriate content,
            blocking content rated medium or higher for categories like
            hate speech, and dangerous content etc.

        Raises:
            Exception: If the Vertex AI initialization fails, often due
                       to missing or incorrect credentials or environment
                       variables.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION")
        self.model_id = os.getenv("GEMINI_MODEL_NAME")

        try:
            vertexai.init(project=self.project_id, location=self.location)
            self.model = GenerativeModel(self.model_id)
            self.safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: (
                    HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                ),
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: (
                    HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                ),
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: (
                    HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                ),
                HarmCategory.HARM_CATEGORY_HARASSMENT: (
                    HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                ),
            }
        except Exception as e:# pylint: disable=broad-exception-caught
            self.logger.exception("Vertex AI initialization failed: %s", e)
            self.model = None

    def _generate_customer_segment(
        self, topic: str, product_name: str, _retries: int = 3
    ) -> Dict:
        """
        Generates a customer segment analysis based on a topic and product.
        """
        # Mock implementation for customer segmentation
        # Returning a predefined list of customer segments
        segments = [
            {
                "segment_name": "Morning Commuters (Daily Ritual)",
                "demographics": {
                    "age": "25-55",
                    "location": "Near transport hubs, business districts",
                    "income": "Mid to High",
                },
                "psychographics": {
                    "interests": [
                        "Efficiency",
                        "quality coffee",
                        "convenience",
                    ],
                    "values": [
                        "Time-saving",
                        "freshness",
                        "a good start to the day",
                    ],
                    "lifestyle": (
                        "Busy professionals, students, early risers seeking "
                        "quick, quality breakfast/coffee"
                    ),
                },
                "behavior": {
                    "purchasing_habits": (
                        "Regular, quick grab-and-go purchases (coffee, pastry),"
                        "loyal to convenience and quality."
                    ),
                    "brand_loyalty": (
                        "High if consistent quality and speed are met."
                    ),
                },
            },
            {
                "segment_name": "Afternoon Indulgers (Treat Yourself)",
                "demographics": {
                    "age": "18-65",
                    "location": "Residential areas, shopping districts",
                    "income": "Varied",
                },
                "psychographics": {
                    "interests": ["Sweet treats", "socializing", "relaxation"],
                    "values": ["Comfort", "taste", "small luxuries"],
                    "lifestyle": (
                        "Individuals seeking a break, parents with children,"
                        "friends meeting up"
                    ),
                },
                "behavior": {
                    "purchasing_habits": (
                        "Impulse buys of cakes, cookies, pastries. May linger "
                        "in cafe area."
                    ),
                    "brand_loyalty": (
                        "Moderate, influenced by seasonal offerings and new "
                        "products."
                    ),
                },
            },
            {
                "segment_name": (
                    "Special Occasion Planners (Celebration Focused)"
                ),
                "demographics": {
                    "age": "30-60+",
                    "location": "Broad, often ordering in advance",
                    "income": "Mid to High",
                },
                "psychographics": {
                    "interests": [
                        "Entertaining",
                        "gifting",
                        "memorable events",
                    ],
                    "values": [
                        "Quality presentation",
                        "customization",
                        "reliable service",
                    ],
                    "lifestyle": (
                        "Organizers of family gatherings, corporate events,"
                        "birthdays, anniversaries"
                    ),
                },
                "behavior": {
                    "purchasing_habits": (
                        "Large orders, custom requests (cakes, catering),"
                        "values reliability and aesthetic."
                    ),
                    "brand_loyalty": (
                        "High if previous experiences were positive for "
                        "important events."
                    ),
                },
            },
            {
                "segment_name": "Health-Conscious Snackers (Mindful Choices)",
                "demographics": {
                    "age": "20-45",
                    "location": "Urban/Suburban, near gyms or health stores",
                    "income": "Mid",
                },
                "psychographics": {
                    "interests": [
                        "Healthy eating",
                        "fitness",
                        "dietary restrictions",
                    ],
                    "values": ["Nutrition", "natural ingredients", "wellness"],
                    "lifestyle": (
                        "Actively manages diet, seeks guilt-free options,"
                        "reads nutritional labels"
                    ),
                },
                "behavior": {
                    "purchasing_habits": (
                        "Seeks options like gluten-free, vegan, low-sugar "
                        "pastries; reads ingredient lists carefully."
                    ),
                    "brand_loyalty": (
                        "Moderate, will switch for better healthy options or "
                        "specific dietary needs."
                    ),
                },
            },
        ]
        self.logger.info(
            "Mocking customer segment generation for topic: %s, product: %s",
            topic,
            product_name,
        )
        # For simplicity, returning the first segment
        return segments[0]

    def generate_outreach_strategy(
        self, customer_segment: Dict, product_name: str, retries: int = 3
    ) -> str:
        """
        Generates an outreach strategy.

        Args:
            customer_segment: A dictionary containing the target customer's
                              demographics,psychographics, and behaviorals.
            product_name: The name of the product to be marketed.
            retries: Attempt generating the strategy before failing.

        Returns:
            A string containing the complete, formatted outreach strategy.

        """
        PROMPT = (
              "As a marketing strategist, devise an outreach strategy for the "
              f"following customer segment and product.\n\n"
              "**Customer Segment:**\n"
              f"```json\n{json.dumps(customer_segment, indent=2)}\n```\n\n"
              f"**Product:** {product_name}\n\n"
              "The strategy should include:\n"
              "1.  **Key Messaging:** What is the core message that will "
              "resonate with this segment?\n"
              "2.  **Social Media Strategy:**\n"
              "    - Which platforms are most effective (e.g., Instagram, "
              "Facebook, TikTok)?\n"
              "    - What type of content should be created (e.g., "
              "behind-the-scenes, user-generated content, tutorials)?\n"
              "3.  **Email Campaign Strategy:**\n"
              "    - How can we nurture leads and drive conversions through "
              "email?\n"
              "    - Suggest a sequence of 2-3 email topics.\n\n"
              "Present the strategy as a concise summary."
          )
        for attempt in range(retries):
            try:
                response = self.model.generate_content(
                    PROMPT, generation_config=GenerationConfig(temperature=0.7)
                )
                return response.candidates[0].content.parts[0].text
            except Exception as e:# pylint: disable=broad-exception-caught
                self.logger.warning(
                   "Attempt %s failed with error: %s", attempt + 1, e
                )
                if attempt == retries - 1:
                    self.logger.error(
                        "Failed to generate outreach strategy after multiple "
                        "retries."
                    )
                    raise

    def generate_marketing_offer(
        self,
        topic: str,
        product_name: str,
        product_features: List[str],
        scene: str,
        _image_url: str = None,
        website_url: str = None,
        retries: int = 3,
    ) -> Dict[str, str]:
        """
        Generates a set of cross-platform marketing offers.
        Args:
            topic: The overarching theme of the marketing campaign.
            product_name: The name of the product to be featured.
            product_features: Key features that highlight the product's value.
            scene: A description of the visual or narrative
                   setting for the content.
            _image_url: (Optional) A URL for an image embedded in
                        the email content.
            website_url: (Optional) A URL to the business's website for
                         inclusion in the offers.
            retries: The number of attempts to make if the generation
                     or parsing fails.

        Returns:
            A dictionary containing the generated marketing content,
            with keys "X", "Instagram",and "Email". The value for "Email"
            is a nested dictionary with "subject" and "body".
        """
        OFFER_GENERATION_PROMPT = (
            "You are a marketing expert for a small bakery. Your goal is to "
            "generate marketing content for a campaign based on the following "
            f"topic:\n**Topic: {topic}**\n\n"
            "Based on the following product information, generate three "
            "engaging marketing offers in valid JSON format. The JSON should "
            "contain three keys: \"X\", \"Instagram\", and \"Email\".\n\n"
            f"Product Name: {product_name}\n"
            # pylint: disable=inconsistent-quotes
            f"Product Features: {', '.join(product_features)}\n"
            f"Scene: {scene}\n\n"
            "The offers should emphasize the benefits of the product and "
            "appeal to customer desires. Maintain a conversational tone "
            "suitable for each platform and adhere to the following "
            "word/character count requirements.\n\n"
            "**X (100-200 characters):** A concise message suitable for "
            "platform X. It must be relevant to the topic. Include 3 most "
            "relevant hashtags, <280 characters.\n\n"
            "**Instagram (150-200 characters):** A captivating message "
            "optimized for Instagram, relevant to a given topic. Include 3-4 "
            "most relevant hashtags.\n\n"
            "**Email (150-300 words):** A professional yet engaging email "
            "for the campaign. The value for the \"Email\" key MUST be a JSON "
            "object with two keys: \"subject\" and \"body\". The subject "
            "should be catchy and reflect the topic. The body should be warm "
            "and inviting. It should have a clear call to action. Do not "
            "include a salutation or signature in the email body.\n"
        )
        if website_url:
            OFFER_GENERATION_PROMPT += (
                 "You MUST include the website URL in the email body naturally."
             )

        OFFER_GENERATION_PROMPT += (
            "\nThe JSON *must* be valid and use double quotes around keys and "
            "strings.  Do not include any extra text outside the JSON object."
            "\n\nHere is an example of the expected JSON output:\n"
            "```json\n"
            "{\n"
            '  "X": "...",\n'
            '  "Instagram": "...",\n'
            '  "Email": {\n'
            '    "subject": "...",\n'
            '    "body": "..."\n'
            "  }\n"
            "}\n"
            "```\n\n"
            "Marketing Offers (JSON):\n"
        )

        generation_config = GenerationConfig(
            max_output_tokens=8192, temperature=0.7
        )

        for attempt in range(retries):
            try:
                response = self.model.generate_content(
                    OFFER_GENERATION_PROMPT,
                    generation_config=generation_config,
                    safety_settings=self.safety_settings,
                )
                offer_text = (
                    response.candidates[0]
                    .content.parts[0]
                    .text.replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

                try:
                    offer_json = json.loads(offer_text)
                    if not all(
                        key in offer_json for key in ["X", "Instagram", "Email"]
                    ):
                        raise ValueError("JSON missing required keys.")
                    if (
                        not isinstance(offer_json["Email"], dict)
                        or "subject" not in offer_json["Email"]
                        or "body" not in offer_json["Email"]
                        or not isinstance(offer_json["Email"]["body"], str)
                    ):
                        raise ValueError(
                            "Email JSON is not in the correct format or body is"
                            " not a string."
                        )
                    return offer_json
                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.warning(
                        "JSON validation/parsing error on attempt %s: %s. "
                        "Raw output: %s",
                        attempt + 1,
                        e,
                        offer_text,
                    )
                    continue

            except Exception as e: # pylint: disable=broad-exception-caught
                self.logger.error(
                    "LLM generation error on attempt %s: %s", attempt + 1, e
                )
                continue

        self.logger.critical(
            "Failed to generate marketing offer after %s retries.", retries
        )
        raise RuntimeError(
            "Failed to generate marketing offer after multiple retries."
        )


def format_for_email(
    offer_text: dict,
    customer_name: str,
    user_name: str,
    _company_name: Optional[str] = None,
) -> str:
    """
    Constructs a fully formatted email.

    Args:
        offer_text: A dictionary containing the `subject` and `body`
                    of the email.
        customer_name: The name of the customer.
        user_name: The name of the sender for the email closing.
        company_name: Optional. The name of the company.
    Returns:
        A single string containing the fully formatted email.
    """
    body = offer_text.get("body", "")
    if isinstance(body, dict):
        body = body.get("body", "")  # Try to get 'body' from the nested dict
        if isinstance(body, dict):
            body = str(body)  # Fallback to string conversion if still a dict

    subject = offer_text.get("subject", "")
    name_to_use = customer_name if customer_name else "Jennifer"
    salutation = f"Dear {name_to_use},\n\n"
    subject_line = f"Subject:  {subject}" + "\n\n"
    closing = f"\n\nWarmly,\n{user_name}"

    formatted_email = f"{salutation}{subject_line}{body}{closing}"
    return formatted_email
