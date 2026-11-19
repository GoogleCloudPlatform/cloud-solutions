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

"""Two-tier runtime skill loading for pooled multi-tenant agents.

Implements the two-tier dynamic skill architecture:
1. **Shared Baseline Skills (`load_shared_baseline_skills_text`)**:
   - Reads provider-authored `SKILL.md` bundles from `plugins/cymbal-sre-diagnostics/skills/`
     so they remain byte-identical across tenants inside the shared prompt prefix cache.
   - Rejects dynamic template placeholders (`{temp:...}`, `{user:...}`) and concrete tenant IDs.
2. **Per-Tenant Custom Skills (`TenantCustomSkillLoader`)**:
   - Enforces synchronous tenant onboarding and URI prefix isolation before TTL cache lookup.
   - Fetches per-tenant `gs://` custom skills using brokered `ct-*` `2LO` credentials and verifies
     Cloud KMS CMEK encryption metadata in live GCP mode (with deterministic synthetic skill
     bodies in offline/hermetic mode).
   - Screens loaded skill bodies for indirect prompt injection and applies DLP egress masking
     before injecting them into the uncached turn suffix.
   - Evicts cached entries immediately on `offboard_tenant(tenant_id)`.
"""

from __future__ import annotations

import inspect
import json
import pathlib
import re
import threading
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import httpx
from agents import context as agent_context
from agents import interceptors
from agents.platform_config import is_live_mode, resolve_project_id
from agents.tenant_credentials import get_default_broker

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_PLUGIN_DIR = REPO_ROOT / "plugins" / "cymbal-sre-diagnostics"
DEFAULT_CUSTOM_SKILL_TTL_SECONDS = 300.0
MAX_CUSTOM_SKILL_TTL_SECONDS = 3600.0

_GCS_URI_RE = re.compile(
    r"^gs://([a-z0-9][a-z0-9._-]{1,61}[a-z0-9])/([a-zA-Z0-9._/-]{1,256})$"
)

_HERMETIC_CUSTOM_SKILL_BODIES: Mapping[str, str] = {
    "gs://cymbal-skills-prod/finvault/occ_regulatory_escalation_skill.md": (
        "# Skill: FinVault Regulatory & Payment-Gateway Triage\n"
        "1. Correlate P1 payment-gateway latency spikes against connection-pool telemetry.\n"
        "2. Verify SEC Rule 17a-4 / OCC escalation thresholds before drafting Jira tickets.\n"
        "3. Redact all banking SSNs, IBANs, and ABA routing numbers prior to egress."
    ),
    "gs://cymbal-skills-prod/retailstream/flash_sale_checkout_skill.md": (
        "# Skill: RetailStream Flash-Sale Checkout Diagnostics\n"
        "1. Inspect checkout-api 503 error budgets and Redis cart-lock saturation.\n"
        "2. Open ServiceNow ITOM incidents with sanitized payment diagnostics.\n"
        "3. Require VP approval for any retention discount exceeding 15 percent."
    ),
}


class CustomSkillUnavailableError(RuntimeError):
    """Raised when the Cloud Storage custom-skill backend is unreachable (`HTTP 503`)."""

    code = "E_CUSTOM_SKILL_BACKEND_UNAVAILABLE"

    def __init__(
        self, message: str, *, code: str = "E_CUSTOM_SKILL_BACKEND_UNAVAILABLE"
    ) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LoadedCustomSkill:
    """Verified, screened per-tenant custom skill document."""

    tenant_id: str
    skill_uri: str
    kms_key_name: str
    sanitized_content: str
    cache_hit: bool


@dataclass(frozen=True)
class CustomSkillFetchResult:
    """Raw custom skill payload returned by a synchronous storage backend."""

    kms_key_name: str
    raw_content: str


class CustomSkillBackend:
    """Synchronous protocol adapter fetching per-tenant custom skills."""

    def fetch_skill(
        self,
        *,
        envelope: agent_context.ContextEnvelope,
        bucket_name: str,
        object_path: str,
        skill_uri: str,
    ) -> CustomSkillFetchResult:
        """Fetches `gs://<bucket_name>/<object_path>` for `envelope`."""
        raise NotImplementedError


class LiveOrHermeticCustomSkillBackend(CustomSkillBackend):
    """Fetches per-tenant custom skills from Cloud Storage in live mode or hermetic fixtures."""

    def __init__(
        self,
        *,
        project_id: str | None = None,
        live_mode_fn: Callable[[], bool] = is_live_mode,
        hermetic_overrides: Mapping[str, str] | None = None,
    ) -> None:
        """Initializes the live/hermetic custom skill storage backend.

        Args:
            project_id: Optional GCP project ID for brokered `ct-*` token exchange.
            live_mode_fn: Callable returning `True` when live Cloud Storage calls are active.
            hermetic_overrides: Optional synthetic `skill_uri -> markdown` map for tests/tenants.
        """
        self._explicit_project_id = project_id
        self._live_mode_fn = live_mode_fn
        self._hermetic_bodies: dict[str, str] = dict(
            _HERMETIC_CUSTOM_SKILL_BODIES
        )
        if hermetic_overrides is not None:
            self._hermetic_bodies.update(hermetic_overrides)

    def register_hermetic_skill(self, *, skill_uri: str, content: str) -> None:
        """Registers a deterministic custom skill body for hermetic/sandbox tenants.

        Args:
            skill_uri: Canonical `gs://` URI owned by the tenant.
            content: Markdown body for the tenant custom skill.
        """
        self._hermetic_bodies[skill_uri] = content

    def fetch_skill(
        self,
        *,
        envelope: agent_context.ContextEnvelope,
        bucket_name: str,
        object_path: str,
        skill_uri: str,
    ) -> CustomSkillFetchResult:
        """Fetches custom skill metadata + content from Cloud Storage or hermetic store.

        Args:
            envelope: Verified caller `ContextEnvelope`.
            bucket_name: Validated Cloud Storage bucket name.
            object_path: Validated object path inside `bucket_name`.
            skill_uri: Full `gs://` URI string.

        Returns:
            `CustomSkillFetchResult` containing verified KMS key metadata and raw text.

        Raises:
            PermissionError: If object is missing or encrypted with a foreign KMS key.
            CustomSkillUnavailableError: If Cloud Storage transport fails.
        """
        if not self._live_mode_fn():
            expected_kms = (
                envelope.tenant.cmek_key_name
                or f"cmek-{envelope.tenant.tenant_id}"
            )
            body = self._hermetic_bodies.get(skill_uri)
            if body is None:
                body = (
                    f"# Custom Tenant Skill ({envelope.tenant.tenant_id})\n"
                    f"1. Follow verified runbook URI `{skill_uri}` within tenant scope."
                )
            return CustomSkillFetchResult(
                kms_key_name=expected_kms,
                raw_content=body,
            )

        resolved_project = resolve_project_id(self._explicit_project_id)
        try:
            brokered = get_default_broker(resolved_project).credential_for(
                envelope
            )
            headers = {
                "Authorization": f"Bearer {brokered.token}",
                "X-Goog-User-Project": resolved_project,
            }
            encoded_obj = urllib.parse.quote(object_path, safe="")
            meta_url = f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o/{encoded_obj}"
            meta_response = httpx.get(meta_url, headers=headers, timeout=15.0)
            if meta_response.status_code in (403, 404):
                raise PermissionError(
                    f"403 Forbidden: E_CUSTOM_SKILL_ACCESS_DENIED: Cannot access '{skill_uri}'."
                )
            meta_response.raise_for_status()
            metadata = meta_response.json()
            media_response = httpx.get(
                f"{meta_url}?alt=media", headers=headers, timeout=15.0
            )
            media_response.raise_for_status()
        except PermissionError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
            raise CustomSkillUnavailableError(
                f"Custom skill storage transport error ({type(exc).__name__})."
            ) from exc

        object_kms = str(metadata.get("kmsKeyName", "") or "")
        return CustomSkillFetchResult(
            kms_key_name=object_kms,
            raw_content=media_response.text,
        )


def _assert_synchronous_skill_backend(backend: object) -> None:
    """Rejects coroutine objects or async `fetch_skill` implementations fail-closed."""
    if inspect.iscoroutine(backend) or inspect.iscoroutinefunction(backend):
        raise TypeError(
            "E_ASYNC_SKILL_BACKEND_FORBIDDEN: CustomSkillBackend must be synchronous."
        )
    fetch_attr = getattr(backend, "fetch_skill", None)
    if not callable(fetch_attr):
        raise TypeError(
            "E_INVALID_SKILL_BACKEND: Backend must implement callable 'fetch_skill'."
        )
    if inspect.iscoroutinefunction(fetch_attr):
        raise TypeError(
            "E_ASYNC_SKILL_BACKEND_FORBIDDEN: 'fetch_skill' cannot be async."
        )


def _tenant_slug_tokens(tenant_id: str) -> tuple[str, ...]:
    """Derives allowed path/bucket ownership tokens from canonical `tenant-<slug>-<suffix>` IDs."""
    tokens: list[str] = [tenant_id.lower()]
    stripped = tenant_id.lower().removeprefix("tenant-")
    if stripped and stripped != tenant_id.lower():
        tokens.append(stripped)
        parts = [part for part in stripped.split("-") if len(part) >= 3]
        if parts:
            tokens.append(parts[0])
    return tuple(dict.fromkeys(tokens))


def validate_tenant_skill_uri(
    *, tenant_id: str, skill_uri: str
) -> tuple[str, str]:
    """Validates `gs://` syntax, traversal safety, and strict tenant prefix ownership.

    Args:
        tenant_id: Authenticated caller tenant identifier.
        skill_uri: Candidate `gs://<bucket>/<object>` URI.

    Returns:
        Tuple `(bucket_name, object_path)`.

    Raises:
        PermissionError: If the URI is malformed, contains `..`, or belongs to another tenant.
    """
    match = _GCS_URI_RE.fullmatch(skill_uri.strip())
    if match is None:
        raise PermissionError(
            f"403 Forbidden: E_CUSTOM_SKILL_INVALID_URI: Malformed skill URI '{skill_uri}'."
        )
    bucket_name, object_path = match.group(1), match.group(2)
    segments = object_path.split("/")
    if any(seg in ("", ".", "..") for seg in segments) or "\\" in object_path:
        raise PermissionError(
            "403 Forbidden: E_CUSTOM_SKILL_PATH_TRAVERSAL: Traversal segment in skill URI."
        )
    if not object_path.lower().endswith(".md"):
        raise PermissionError(
            "403 Forbidden: E_CUSTOM_SKILL_EXTENSION_DENIED: Custom skills must be '.md' files."
        )

    allowed_tokens = _tenant_slug_tokens(tenant_id)
    first_segment = segments[0].lower()
    bucket_lower = bucket_name.lower()
    owns_prefix = first_segment in allowed_tokens or any(
        f"-{token}" in bucket_lower or bucket_lower.endswith(token)
        for token in allowed_tokens
    )
    if not owns_prefix:
        raise PermissionError(
            f"403 Forbidden: E_CUSTOM_SKILL_CROSS_TENANT_URI: Tenant '{tenant_id}' cannot load "
            f"foreign custom skill '{skill_uri}'."
        )
    return bucket_name, object_path


def load_shared_baseline_skills_text(
    *, plugin_dir: pathlib.Path = DEFAULT_PLUGIN_DIR
) -> str:
    """Loads provider-authored baseline `SKILL.md` files for the shared static prompt prefix.

    Args:
        plugin_dir: Directory containing `plugin.json` and `skills/*/SKILL.md`.

    Returns:
        Concatenated baseline skill instructions safe for global per-model prefix caching.

    Raises:
        PermissionError: If a baseline skill contains dynamic `{temp:...}` placeholders or
            concrete tenant IDs that would poison the shared prefix cache.
    """
    plugin_manifest_path = plugin_dir / "plugin.json"
    if not plugin_manifest_path.is_file():
        return ""
    plugin_meta = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))
    skills_root = (
        plugin_dir / str(plugin_meta.get("skills_dir", "skills"))
    ).resolve()
    if not skills_root.is_dir():
        return ""

    skill_sections: list[str] = []
    for child_name in sorted(
        p.name for p in skills_root.iterdir() if p.is_dir()
    ):
        skill_md = skills_root / child_name / "SKILL.md"
        if not skill_md.is_file():
            continue
        raw_text = skill_md.read_text(encoding="utf-8").strip()
        lowered = raw_text.lower()
        if "{temp:" in lowered or "{user:" in lowered:
            raise PermissionError(
                f"E_CACHE_POISONING_DETECTED: Baseline skill '{skill_md.name}' contains dynamic "
                "state template placeholders."
            )
        for registered_tenant in agent_context.TENANT_DIRECTORY:
            if registered_tenant.lower() in lowered:
                raise PermissionError(
                    f"E_CACHE_POISONING_DETECTED: Baseline skill '{skill_md.name}' embeds tenant "
                    f"identifier '{registered_tenant}'."
                )
        skill_sections.append(raw_text)
    return "\n\n".join(skill_sections)


class TenantCustomSkillLoader:
    """Loads, CMEK-verifies, screens, and TTL-caches per-tenant custom runtime skills."""

    def __init__(
        self,
        *,
        backend: CustomSkillBackend | None = None,
        clock_fn: Callable[[], float] = time.monotonic,
        ttl_seconds: float = DEFAULT_CUSTOM_SKILL_TTL_SECONDS,
    ) -> None:
        """Initializes the tenant-partitioned custom skill loader.

        Args:
            backend: Synchronous `CustomSkillBackend` implementation.
            clock_fn: Monotonic clock callable returning seconds (`time.monotonic`).
            ttl_seconds: Per-entry cache TTL in `(0, 3600]`.

        Raises:
            TypeError: If `backend` is a coroutine or exposes an async `fetch_skill`.
            ValueError: If `ttl_seconds` is outside `(0, 3600]`.
        """
        resolved_backend = (
            LiveOrHermeticCustomSkillBackend() if backend is None else backend
        )
        _assert_synchronous_skill_backend(resolved_backend)
        if ttl_seconds <= 0 or ttl_seconds > MAX_CUSTOM_SKILL_TTL_SECONDS:
            raise ValueError(
                f"ttl_seconds must be in (0, {MAX_CUSTOM_SKILL_TTL_SECONDS}], got {ttl_seconds}."
            )
        self._backend = resolved_backend
        self._clock = clock_fn
        self._ttl_seconds = float(ttl_seconds)
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str], tuple[float, LoadedCustomSkill]] = {}
        agent_context.register_tenant_eviction_target(self)

    def evict_tenant(self, tenant_id: str) -> int:
        """Purges all cached custom skills for `tenant_id` on offboarding.

        Args:
            tenant_id: Offboarded tenant identifier.

        Returns:
            Number of evicted cache entries.
        """
        with self._lock:
            matching_keys = [
                cache_key
                for cache_key in self._cache
                if cache_key[0] == tenant_id
            ]
            for cache_key in matching_keys:
                self._cache.pop(cache_key, None)
            return len(matching_keys)

    def load_skills_for_turn(
        self,
        *,
        envelope: agent_context.ContextEnvelope,
        skill_uris: Sequence[str],
    ) -> list[LoadedCustomSkill]:
        """Loads and screens `skill_uris` for `envelope` with policy-before-cache ordering.

        Args:
            envelope: Verified caller `ContextEnvelope`.
            skill_uris: Ordered `gs://` custom skill URIs configured on the tenant manifest.

        Returns:
            List of `LoadedCustomSkill` documents safe for the uncached turn suffix.

        Raises:
            PermissionError: On offboarded tenant, cross-tenant URI, CMEK mismatch, or IPI.
            CustomSkillUnavailableError: When Cloud Storage is unreachable.
        """
        if not isinstance(envelope, agent_context.ContextEnvelope):
            raise PermissionError(
                "403 Forbidden: E_UNVERIFIED_ENVELOPE: Verified ContextEnvelope required."
            )
        tenant_id = envelope.tenant.tenant_id
        if not tenant_id or tenant_id not in agent_context.TENANT_DIRECTORY:
            raise PermissionError(
                "403 Forbidden: E_TENANT_OFFBOARDED: Tenant is not active in TENANT_DIRECTORY."
            )

        loaded_documents: list[LoadedCustomSkill] = []
        for raw_uri in skill_uris:
            clean_uri = raw_uri.strip()
            bucket_name, object_path = validate_tenant_skill_uri(
                tenant_id=tenant_id,
                skill_uri=clean_uri,
            )
            now = self._clock()
            cache_key = (tenant_id, clean_uri)
            with self._lock:
                cached_entry = self._cache.get(cache_key)
                if cached_entry is not None and cached_entry[0] > now:
                    cached_doc = cached_entry[1]
                    loaded_documents.append(
                        LoadedCustomSkill(
                            tenant_id=cached_doc.tenant_id,
                            skill_uri=cached_doc.skill_uri,
                            kms_key_name=cached_doc.kms_key_name,
                            sanitized_content=cached_doc.sanitized_content,
                            cache_hit=True,
                        )
                    )
                    continue
                if cached_entry is not None:
                    self._cache.pop(cache_key, None)

            fetched = self._backend.fetch_skill(
                envelope=envelope,
                bucket_name=bucket_name,
                object_path=object_path,
                skill_uri=clean_uri,
            )
            if inspect.iscoroutine(fetched):
                fetched.close()
                raise CustomSkillUnavailableError(
                    "Async coroutine returned by synchronous custom skill backend."
                )
            expected_cmek = envelope.tenant.cmek_key_name
            if expected_cmek and not fetched.kms_key_name.startswith(
                expected_cmek
            ):
                raise PermissionError(
                    f"403 Forbidden: E_CUSTOM_SKILL_CMEK_MISMATCH: Skill '{clean_uri}' is not "
                    f"encrypted under tenant '{tenant_id}' CMEK key."
                )

            interceptors.screen_tool_output_for_indirect_injection(
                tool_name="tenant_custom_skill_loader",
                raw_output=fetched.raw_content,
            )
            sanitized_body = str(
                interceptors.egress_dlp_and_nlc_guardrail(
                    tenant_id=tenant_id,
                    tool_name="tenant_custom_skill_loader",
                    tool_args={"skill_uri": clean_uri},
                    raw_output=fetched.raw_content,
                )
            )
            fresh_doc = LoadedCustomSkill(
                tenant_id=tenant_id,
                skill_uri=clean_uri,
                kms_key_name=fetched.kms_key_name,
                sanitized_content=sanitized_body,
                cache_hit=False,
            )
            with self._lock:
                if tenant_id in agent_context.TENANT_DIRECTORY:
                    self._cache[cache_key] = (
                        self._clock() + self._ttl_seconds,
                        fresh_doc,
                    )
            loaded_documents.append(fresh_doc)
        return loaded_documents


_DEFAULT_CUSTOM_SKILL_LOADER: TenantCustomSkillLoader | None = None
_DEFAULT_LOADER_LOCK = threading.Lock()


def get_default_custom_skill_loader() -> TenantCustomSkillLoader:
    """Returns the shared process-wide `TenantCustomSkillLoader` singleton."""
    global _DEFAULT_CUSTOM_SKILL_LOADER
    if _DEFAULT_CUSTOM_SKILL_LOADER is None:
        with _DEFAULT_LOADER_LOCK:
            if _DEFAULT_CUSTOM_SKILL_LOADER is None:
                _DEFAULT_CUSTOM_SKILL_LOADER = TenantCustomSkillLoader()
    return _DEFAULT_CUSTOM_SKILL_LOADER
