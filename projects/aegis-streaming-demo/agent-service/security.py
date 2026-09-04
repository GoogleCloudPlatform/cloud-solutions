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

"""Security Module for Project Aegis Agent Service.

Provides ModelArmorGuard for payload sanitization, prompt injection defense,
and PII masking across incoming prompts and model responses.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    import google.auth
    import google.auth.transport.requests

    HAVE_GOOGLE_AUTH = True
except ImportError:
    HAVE_GOOGLE_AUTH = False

logger = logging.getLogger("ModelArmorGuard")


class ModelArmorGuard:
    """ModelArmorGuard provides security guardrails for Gemini LLM calls."""

    EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    PHONE_REGEX = re.compile(
        r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b"
    )
    SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    IPV4_REGEX = re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    )
    API_KEY_REGEX = re.compile(
        r"\b(?:AIzaSy[a-zA-Z0-9_-]{33}|ya29\.[a-zA-Z0-9_-]+|"
        r"sk-[a-zA-Z0-9]{32,})\b"
    )
    SECRET_PATTERN = re.compile(
        r"(?i)(?:password|secret|api_key|access_token|private_key)\s*[:=]\s*"
        r'["\']?([^\s"\'\`]+)["\']?'
    )

    PROMPT_INJECTION_PATTERNS = [
        re.compile(
            r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+"
            r"(instructions|prompts|rules)"
        ),
        re.compile(
            r"(?i)disregard\s+(all\s+)?(previous|prior|above)\s+"
            r"(instructions|prompts|rules)"
        ),
        re.compile(r"(?i)you\s+are\s+now\s+a\s+(dan|jailbroken|unrestricted)"),
        re.compile(r"(?i)system\s*override"),
        re.compile(r"(?i)forget\s+(your\s+)?(system\s+)?prompt"),
        re.compile(r"(?i)reveal\s+(your\s+)?(system\s+)?prompt"),
        re.compile(r"(?i)<\s*script[^>]*>"),
        re.compile(r"(?i)eval\s*\(.*\)"),
        re.compile(r"(?i)sudo\s+rm\s+-rf"),
    ]

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.project_id = os.getenv("GCP_PROJECT", "aegis-streaming-1001")
        self.template_id = os.getenv(
            "MODEL_ARMOR_TEMPLATE", "aegis-defense-shield"
        )
        self.location = os.getenv("MODEL_ARMOR_LOCATION", "us")
        self.api_url = (
            f"https://modelarmor.{self.location}.rep.googleapis.com/v1/"
            f"projects/{self.project_id}/locations/{self.location}/"
            f"templates/{self.template_id}:sanitizeUserPrompt"
        )

    def _get_auth_token(self) -> Optional[str]:
        """Obtain access token for Model Armor API requests."""
        if not HAVE_GOOGLE_AUTH:
            return None
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
            return credentials.token
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.debug(
                "[ModelArmorGuard] Auth token acquisition failed: %s", e
            )
            return None

    def call_cloud_model_armor(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Call live Google Cloud Model Armor API to screen prompt."""
        token = self._get_auth_token()
        if not token:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            body = {"userPromptData": {"text": prompt}}
            resp = requests.post(
                self.api_url, json=body, headers=headers, timeout=2.5
            )
            if resp.status_code == 200:
                data = resp.json()
                f_state = data.get("sanitizationResult", {}).get(
                    "filterMatchState"
                )
                logger.info(
                    "[ModelArmorGuard] Live Model Armor response: %s",
                    f_state,
                )
                return data
            logger.warning(
                "[ModelArmorGuard] Live API returned %d: %s",
                resp.status_code,
                resp.text,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.debug("[ModelArmorGuard] Live API call skipped (%s).", exc)
        return None

    def sanitize_prompt(self, prompt: str) -> str:
        """Sanitize input prompt by removing control chars and PII."""
        if not prompt or not isinstance(prompt, str):
            return ""

        sanitized = self._normalize_text(prompt)

        cloud_result = self.call_cloud_model_armor(sanitized)
        if cloud_result:
            san_res = cloud_result.get("sanitizationResult", {})
            if san_res.get("filterMatchState") == "MATCH_FOUND":
                err_msg = san_res.get("sanitizationMetadata", {}).get(
                    "errorMessage", "Model Armor Policy Violation"
                )
                logger.warning(
                    "[ModelArmorGuard] Live Model Armor blocked: %s",
                    err_msg,
                )
                sanitized = f"[REDACTED_BY_CLOUD_MODEL_ARMOR: {err_msg}]"
                return sanitized

        sanitized = self.mask_pii(sanitized)

        is_injection, detected_triggers = self.detect_prompt_injection(
            sanitized
        )
        if is_injection:
            logger.warning(
                "[ModelArmorGuard] Prompt injection detected! Triggers: %s",
                detected_triggers,
            )
            sanitized = self.neutralize_injection(sanitized)

        return sanitized

    def sanitize_response(self, response: str) -> str:
        """Sanitize model response output by masking PII."""
        if not response or not isinstance(response, str):
            return ""

        sanitized = self._normalize_text(response)
        sanitized = self.mask_pii(sanitized)
        sanitized = re.sub(
            r"(?i)<\s*script[^>]*>.*?</\s*script\s*>",
            "[REDACTED_SCRIPT]",
            sanitized,
        )
        return sanitized

    def mask_pii(self, text: str) -> str:
        """Identify and mask PII in text."""
        text = self.API_KEY_REGEX.sub("[REDACTED_API_KEY]", text)
        text = self.EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
        text = self.SSN_REGEX.sub("[REDACTED_SSN]", text)
        text = self.PHONE_REGEX.sub("[REDACTED_PHONE]", text)
        text = self.IPV4_REGEX.sub("[REDACTED_IP]", text)
        text = self.SECRET_PATTERN.sub(r"Key/Secret: [REDACTED_SECRET]", text)
        return text

    def detect_prompt_injection(self, text: str) -> Tuple[bool, List[str]]:
        """Check if text contains prompt injection signatures."""
        matched = []
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if pattern.search(text):
                matched.append(pattern.pattern)
        return len(matched) > 0, matched

    def neutralize_injection(self, text: str) -> str:
        """Redact or sanitize detected prompt injection commands."""
        neutralized = text
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            neutralized = pattern.sub(
                "[REDACTED_PROMPT_INJECTION_ATTEMPT]", neutralized
            )
        return neutralized

    def _normalize_text(self, text: str) -> str:
        """Strip control characters and normalize whitespace."""
        text = re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200d\ufeff]", "", text
        )
        return text.strip()
