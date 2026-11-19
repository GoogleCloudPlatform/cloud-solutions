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

# pylint: disable=line-too-long

"""Disjoint O(N) pre-execution credential, metadata-IP, and env-var screener for sandboxes."""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from collections.abc import Mapping

from agents import interceptors
from agents.sandbox.models import MAX_SANDBOX_CODE_CHARS

_ZERO_WIDTH_STRIP_RE: re.Pattern[str] = re.compile(
    r"[\u00ad\u180e\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]"
)
_BLOCK_COMMENT_RE: re.Pattern[str] = re.compile(r"/\*.*?\*/", re.DOTALL)
_BASE64_CHUNK_RE: re.Pattern[str] = re.compile(r"[A-Za-z0-9+/_-]{16,}={0,2}")

# Disjoint O(N) patterns with zero nested or overlapping quantifiers (CodeQL polynomial-redos safe).
_CREDENTIAL_VALUE_SUBSTRINGS: tuple[str, ...] = (
    "ya29.",
    "-----begin ",
    "private_key",
    "google_application_credentials",
    "cloudsdk_auth_access_token",
    "aws_secret_access_key",
)
_AUTH_HEADER_BEARER_RE: re.Pattern[str] = re.compile(
    r"\b(?:x-serverless-)?authorization['\"]?\s*[:=]\s*['\"]?bearer\s+[a-z0-9._~+/-]{4,}",
    re.IGNORECASE,
)
_BEARER_VALUE_RE: re.Pattern[str] = re.compile(
    r"\bbearer\s+([a-z0-9._~+/-]{4,})",
    re.IGNORECASE,
)
_KNOWN_BEARER_PREFIXES: tuple[str, ...] = (
    "ya29.",
    "eyj",
    "ct-",
    "ghp_",
    "gho_",
    "sk-",
    "aiza",
    "akia",
)
_TENANT_SA_TOKEN_PATTERN: re.Pattern[str] = re.compile(
    r"\bct-[0-9a-f]{24}\b", re.IGNORECASE
)
_FORBIDDEN_CODE_SUBSTRINGS: tuple[str, ...] = (
    "169.254.169.254",
    "169.254.170.2",
    "::ffff:169.254.169.254",
    "::ffff:a9fe:a9fe",
    "0xa9.0xfe.0xa9.0xfe",
    "0251.0376.0251.0376",
    "metadata.google.internal",
    "/computeMetadata/v1",
    "/proc/self/",
    "/proc/1/",
    "/proc/thread-self/",
    "gc.get_objects",
    "ctypes.",
)
_FORBIDDEN_CODE_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b0x0*a9fea9fe\b", re.IGNORECASE),
    re.compile(r"\b0x0*a9feaa02\b", re.IGNORECASE),
    re.compile(r"\b2852039166\b"),
    re.compile(r"\b2852039298\b"),
    re.compile(r"/proc/(?:1|self|thread-self)(?:/|\b)", re.IGNORECASE),
    re.compile(r"\bfrom\s+(?:ctypes|gc)\s+import\b", re.IGNORECASE),
    re.compile(
        r"\bfrom\s+(?:ctypes|gc)\.[a-z0-9_.]+\s+import\b", re.IGNORECASE
    ),
)
_IMPORT_STMT_RE: re.Pattern[str] = re.compile(
    r"\bimport\s+([^\n;#]+)", re.IGNORECASE
)
_FORBIDDEN_ENV_KEYS: frozenset[str] = frozenset(
    {
        "AUTHORIZATION",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_AUTH_CREDENTIALS",
        "GOOGLE_OAUTH_ACCESS_TOKEN",
        "CLOUDSDK_AUTH_ACCESS_TOKEN",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_CREDENTIALS",
        "CYMBAL_GATEWAY_SIGNING_KEY",
        "DATABASE_URL",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "PYTHONPATH",
        "PYTHONHOME",
        "BASH_ENV",
        "ZDOTDIR",
    }
)


def _is_suspicious_bearer_token(token: str) -> bool:
    """Returns `True` when a token following `Bearer` resembles a secret rather than prose."""
    lowered = token.lower()
    if lowered.startswith(_KNOWN_BEARER_PREFIXES):
        return True
    if len(token) >= 6 and any(ch.isdigit() for ch in token):
        return True
    if len(token) >= 8 and any(ch in "._+/=" for ch in token):
        return True
    if (
        len(token) >= 12
        and any(ch.isupper() for ch in token[1:])
        and any(ch.islower() for ch in token)
    ):
        return True
    return len(token) >= 18


def _read_quoted_literal(text: str, start: int) -> tuple[str, str, int] | None:
    """Reads a single/double/backtick/triple-quoted literal at `start` in O(len) time."""
    quote = text[start]
    if quote not in ('"', "'", "`"):
        return None
    if quote != "`" and text[start : start + 3] == quote * 3:
        end_idx = text.find(quote * 3, start + 3)
        if end_idx == -1:
            return None
        return (quote, text[start + 3 : end_idx], end_idx + 3)
    i = start + 1
    n = len(text)
    chars: list[str] = []
    while i < n:
        ch = text[i]
        if ch == "\\":
            if i + 1 < n:
                nxt = text[i + 1]
                if nxt in ('"', "'", "`", "\\"):
                    chars.append(nxt)
                elif nxt == "n":
                    chars.append("\n")
                elif nxt == "t":
                    chars.append("\t")
                elif nxt == "r":
                    chars.append("\r")
                else:
                    chars.append(ch)
                    chars.append(nxt)
                i += 2
                continue
            chars.append(ch)
            i += 1
            continue
        if ch == quote:
            return (quote, "".join(chars), i + 1)
        if ch == "\n" and quote != "`":
            return None
        chars.append(ch)
        i += 1
    return None


def _collapse_string_concatenation(text: str) -> str:
    """Collapses adjacent string-literal concatenations (`'a' + 'b'` or `'a' 'b'`) in O(N)."""
    if '"' not in text and "'" not in text and "`" not in text:
        return text
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ('"', "'", "`"):
            parsed = _read_quoted_literal(text, i)
            if parsed is None:
                out.append(ch)
                i += 1
                continue
            quote, inner, pos = parsed
            parts = [inner]
            cursor = pos
            while cursor < n:
                scan = cursor
                while scan < n and text[scan] in " \t\r\n":
                    scan += 1
                has_plus = scan < n and text[scan] == "+"
                if has_plus:
                    scan += 1
                    while scan < n and text[scan] in " \t\r\n":
                        scan += 1
                if (
                    scan < n
                    and text[scan] in ('"', "'", "`")
                    and (has_plus or (quote != "`" and text[scan] != "`"))
                ):
                    nxt_parsed = _read_quoted_literal(text, scan)
                    if nxt_parsed is not None:
                        _, nxt_inner, nxt_pos = nxt_parsed
                        parts.append(nxt_inner)
                        cursor = nxt_pos
                        continue
                break
            out.append(quote)
            out.append("".join(parts))
            out.append(quote)
            i = cursor
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _decode_base64_utf8_chunk(chunk: str) -> str | None:
    """Decodes a >= 16-char base64/base64url chunk if it produces valid UTF-8 text."""
    stripped = chunk.rstrip("=")
    if len(stripped) % 4 == 1:
        return None
    padded = chunk + "=" * (-len(chunk) % 4)
    try:
        if "-" in chunk or "_" in chunk:
            decoded_bytes = base64.urlsafe_b64decode(padded)
        else:
            decoded_bytes = base64.b64decode(padded, validate=True)
        return decoded_bytes.decode("utf-8", errors="strict")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None


def _scan_normalized_variant(variant: str, *, context_label: str) -> None:
    """Checks one normalized text variant for metadata, forbidden import, or secret markers."""
    lowered = variant.lower()
    for forbidden_marker in _FORBIDDEN_CODE_SUBSTRINGS:
        if forbidden_marker.lower() in lowered:
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_CREDENTIAL_OR_METADATA_BLOCKED: "
                f"Sandbox {context_label} attempted metadata-server, host-memory, "
                "or forbidden introspection."
            )
    for forbidden_regex in _FORBIDDEN_CODE_REGEXES:
        if forbidden_regex.search(variant) is not None:
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_CREDENTIAL_OR_METADATA_BLOCKED: "
                f"Sandbox {context_label} attempted metadata-server, host-memory, "
                "or forbidden introspection."
            )
    for import_match in _IMPORT_STMT_RE.finditer(variant):
        for raw_item in import_match.group(1).split(","):
            tokens = raw_item.strip().split()
            if tokens and tokens[0].split(".")[0].lower() in {"ctypes", "gc"}:
                raise PermissionError(
                    "403 Forbidden: E_SANDBOX_CREDENTIAL_OR_METADATA_BLOCKED: "
                    f"Sandbox {context_label} attempted metadata-server, host-memory, "
                    "or forbidden introspection."
                )

    for secret_marker in _CREDENTIAL_VALUE_SUBSTRINGS:
        if secret_marker in lowered:
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_CREDENTIAL_INJECTION_BLOCKED: "
                f"Forbidden credential material detected in sandbox {context_label}."
            )
    if _AUTH_HEADER_BEARER_RE.search(variant) is not None:
        raise PermissionError(
            "403 Forbidden: E_SANDBOX_CREDENTIAL_INJECTION_BLOCKED: "
            f"Forbidden credential material detected in sandbox {context_label}."
        )
    for bearer_match in _BEARER_VALUE_RE.finditer(variant):
        if _is_suspicious_bearer_token(bearer_match.group(1)):
            raise PermissionError(
                "403 Forbidden: E_SANDBOX_CREDENTIAL_INJECTION_BLOCKED: "
                f"Forbidden credential material detected in sandbox {context_label}."
            )
    if _TENANT_SA_TOKEN_PATTERN.search(variant) is not None:
        raise PermissionError(
            "403 Forbidden: E_SANDBOX_CREDENTIAL_INJECTION_BLOCKED: "
            f"Per-tenant service account identifier/token detected in sandbox {context_label}."
        )


def _normalized_text_variants(text: str) -> list[str]:
    """Builds NFKC/zero-width, space/empty comment-stripped, and concat-collapsed variants."""
    nfkc_no_zw = _ZERO_WIDTH_STRIP_RE.sub(
        "", unicodedata.normalize("NFKC", text)
    )
    space_comments = interceptors.normalize_adversarial_text(text)
    empty_comments = _BLOCK_COMMENT_RE.sub("", nfkc_no_zw)
    candidates: list[str] = []
    for base_variant in (nfkc_no_zw, space_comments, empty_comments):
        candidates.append(base_variant)
        collapsed = _collapse_string_concatenation(base_variant)
        if collapsed != base_variant:
            candidates.append(collapsed)
    return list(dict.fromkeys(candidates))


def _screen_untrusted_text(text: str, *, context_label: str) -> str:
    """Normalizes obfuscated text and blocks credential, `ct-*`, and metadata markers."""
    variants = _normalized_text_variants(text)
    scanned_b64: set[str] = set()
    for variant in variants:
        _scan_normalized_variant(variant, context_label=context_label)
        for chunk_match in _BASE64_CHUNK_RE.finditer(variant):
            chunk = chunk_match.group(0)
            if chunk in scanned_b64:
                continue
            scanned_b64.add(chunk)
            decoded = _decode_base64_utf8_chunk(chunk)
            if decoded is not None:
                for decoded_variant in _normalized_text_variants(decoded):
                    _scan_normalized_variant(
                        decoded_variant, context_label=context_label
                    )
    return variants[1] if len(variants) > 1 else variants[0]


def assert_zero_credentials_and_egress_safe(
    *,
    code: str,
    environment_variables: Mapping[str, str] | None = None,
    readonly_input_json: str | None = None,
) -> None:
    """Verifies `code`, `environment_variables`, and `readonly_input_json` carry zero secrets.

    Runs in strict O(N) linear time over bounded inputs with zero backtracking regexes.

    Args:
        code: Source snippet or shell command submitted for sandbox execution.
        environment_variables: Optional non-secret environment variables for `/workspace`.
        readonly_input_json: Optional serialized read-only input JSON passed to `/workspace`.

    Raises:
        ValueError: If `code` is empty or exceeds `MAX_SANDBOX_CODE_CHARS`.
        PermissionError: If credentials, `ct-*` principals, host `/proc` paths, or metadata-server
            endpoints (`169.254.169.254`, `metadata.google.internal`) are detected.
    """
    if not isinstance(code, str) or not code.strip():
        raise ValueError(
            "E_SANDBOX_EMPTY_CODE: Sandbox code must be a non-empty string."
        )
    if len(code) > MAX_SANDBOX_CODE_CHARS:
        raise ValueError(
            f"E_SANDBOX_CODE_TOO_LARGE: Sandbox code exceeds {MAX_SANDBOX_CODE_CHARS} characters."
        )

    _screen_untrusted_text(code, context_label="workload")

    if environment_variables is not None:
        for raw_key, raw_value in environment_variables.items():
            key_text = str(raw_key)
            normalized_key = (
                interceptors.normalize_adversarial_text(key_text)
                .strip()
                .upper()
            )
            if (
                normalized_key in _FORBIDDEN_ENV_KEYS
                or normalized_key.endswith(
                    (
                        "_TOKEN",
                        "_SECRET",
                        "_KEY",
                        "_PASSWORD",
                        "_CREDENTIAL",
                        "_CREDENTIALS",
                    )
                )
            ):
                raise PermissionError(
                    "403 Forbidden: E_SANDBOX_CREDENTIAL_INJECTION_BLOCKED: "
                    f"Forbidden credential environment variable '{normalized_key}'."
                )
            _screen_untrusted_text(
                key_text, context_label="environment variable key"
            )
            _screen_untrusted_text(
                str(raw_value), context_label="environment variable value"
            )

    if readonly_input_json:
        _screen_untrusted_text(
            readonly_input_json, context_label="readonly_tool_output"
        )
