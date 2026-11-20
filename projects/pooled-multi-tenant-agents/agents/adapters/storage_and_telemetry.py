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

# pylint: disable=import-outside-toplevel,line-too-long

"""Live Firestore 5-level Memory Bank, BigQuery OTel sink, and GCS CMEK runbook vault."""

from __future__ import annotations

import datetime as dt
import hashlib
import os
from typing import Any

import httpx
from agents.adapters._bridge_runtime import (
    _CFG,
    DEFAULT_BQ_DATASET,
    DEFAULT_BQ_TABLE,
    DEFAULT_FIRESTORE_DB,
    DEFAULT_GCP_PROJECT,
    DEFAULT_GCP_REGION,
    _egress_guardrail,
    _tenant_headers,
    _tenant_policy,
)
from agents.context import ContextEnvelope, MemoryScope
from agents.interceptors import screen_tool_output_for_indirect_injection
from agents.memory_bank import (
    global_write_metadata,
    log_quarantine,
    screen_retrieved_chunk,
)
from agents.memory_crypto import (
    MemoryAccessDenied,
    OperatorPrincipal,
    SealedRecord,
    assert_can_read,
    assert_can_write,
    assert_stored_scope_matches,
    build_memory_key,
    get_memory_crypto,
    parse_memory_key,
)
from agents.shared_diagnostic_agent import get_clean_project_id


class LiveFirestoreMemoryBank:
    """Subsystem 4: Live Cloud Firestore 5-Level Memory Bank (`cymbal-memory-bank-prod`) with
    AEAD.
    """

    def __init__(
        self,
        project_id: str = DEFAULT_GCP_PROJECT,
        database: str = DEFAULT_FIRESTORE_DB,
        collection_name: str = "cymbal_memory_bank_v1",
    ) -> None:
        from agents.kms_rest import build_firestore_client

        self.project_id = project_id
        self.database = database
        self.collection_name = collection_name
        self._client = build_firestore_client(
            project_id=project_id, database=database
        )

    @staticmethod
    def doc_id_for(composite_key: str) -> str:
        """Injective document ID (a `/` -> `__` mapping let two keys share one document)."""
        return "m-" + hashlib.sha256(composite_key.encode()).hexdigest()

    def _doc(self, composite_key: str) -> Any:
        return self._client.collection(self.collection_name).document(
            self.doc_id_for(composite_key)
        )

    def _put(
        self,
        *,
        envelope: ContextEnvelope | None,
        composite_key: str,
        content: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        sealed = get_memory_crypto().seal(
            envelope=envelope, key=composite_key, payload=content
        )
        self._doc(composite_key).set(
            {
                "composite_key": composite_key,
                "tenant_id": (
                    envelope.tenant.tenant_id if envelope else "global"
                ),
                "scope": parse_memory_key(composite_key)["scope"],
                **sealed.to_storage(),
                **(metadata or {}),
                "updated_at": dt.datetime.now(dt.UTC).isoformat(),
            }
        )
        return composite_key

    def write_memory(
        self,
        *,
        envelope: ContextEnvelope,
        scope: MemoryScope,
        actor: str,
        content: dict[str, Any],
    ) -> str:
        """Seals with a per-record data key wrapped by the tenant's KMS key (as the tenant SA)."""
        assert_can_write(envelope, scope)
        composite_key = build_memory_key(
            tenant_id=envelope.tenant.tenant_id,
            sub=envelope.security.sub,
            scope=scope,
            session_id=envelope.request.session_id,
            actor=actor,
        )
        return self._put(
            envelope=envelope, composite_key=composite_key, content=content
        )

    def exists(self, composite_key: str) -> bool:
        return bool(self._doc(composite_key).get().exists)

    def write_global(
        self,
        *,
        operator: OperatorPrincipal,
        actor: str,
        content: dict[str, Any],
        replace: bool = False,
    ) -> str:
        """Operator tooling only: GLOBAL memory sealed with the platform key (no tenant data).

        Runs as the curator's identity; the serving identity has decrypt-only on the platform key,
        so this fails with a KMS 403 if serving code ever calls it.
        """
        assert_can_write(None, MemoryScope.GLOBAL, operator=operator)
        key = build_memory_key(
            tenant_id="",
            sub="",
            scope=MemoryScope.GLOBAL,
            session_id="",
            actor=actor,
        )
        if self.exists(key) and not replace:
            raise MemoryAccessDenied(
                "E_GLOBAL_EXISTS: GLOBAL entry exists; pass replace=True."
            )
        return self._put(
            envelope=None,
            composite_key=key,
            content=content,
            metadata=global_write_metadata(operator, content),
        )

    def read_memory(
        self, *, envelope: ContextEnvelope, target_composite_key: str
    ) -> dict[str, Any]:
        """Same rules as the in-process bank: code check, key-derived scope, KMS as the caller,
        then the injection screen (a flagged record is marked quarantined and refused from then on).
        """
        assert_can_read(envelope, target_composite_key)
        snap = self._doc(target_composite_key).get()
        if not snap.exists:
            raise KeyError("Firestore memory document not found.")
        data = snap.to_dict() or {}
        if data.get("composite_key") != target_composite_key:
            raise MemoryAccessDenied(
                "403 Forbidden: Stored record does not match its key."
            )
        if data.get("quarantined"):
            raise MemoryAccessDenied(
                "E_MEMORY_QUARANTINED: record is quarantined."
            )
        assert_stored_scope_matches(data, target_composite_key)
        is_global = parse_memory_key(target_composite_key)["kind"] == "global"
        payload = get_memory_crypto().open(
            envelope=None if is_global else envelope,
            key=target_composite_key,
            record=SealedRecord.from_storage(data),
        )
        if not screen_retrieved_chunk(payload):
            self._doc(target_composite_key).update(
                {
                    "quarantined": True,
                    "quarantined_at": dt.datetime.now(dt.UTC).isoformat(),
                }
            )
            log_quarantine(target_composite_key, data)
            raise MemoryAccessDenied(
                "E_MEMORY_QUARANTINED: record failed the injection screen."
            )
        return payload


class LiveVertexMemoryBankAdapter:
    """Managed Gemini Enterprise Memory Bank SDK adapter (`agent_engines.memories`, `C10`).

    Wraps `vertexai.Client(...).agent_engines.memories` (`create` and `retrieve`) with:
    1. Regional residency enforcement (`MemoryBankScopeStore.enforce_regional_org_policy`).
    2. Strict per-tenant SA credential brokering (`ct-<sha256(tenant_id)[:24]>`) so Cloud IAM
       evaluates `aiplatform.googleapis.com/memoryScope` CEL conditions against the tenant's SA.
    3. Canonical 1..5-key flat `scope` dict derived exclusively from verified `ContextEnvelope`
       (never caller-supplied identity strings).
    4. Retrieval indirect-prompt-injection screening (`screen_retrieved_chunk`).
    """

    def __init__(
        self,
        project_id: str = DEFAULT_GCP_PROJECT,
        location: str = DEFAULT_GCP_REGION,
        reasoning_engine_name: str | None = None,
        *,
        vertex_client_factory: Any | None = None,
    ) -> None:
        from agents.memory_bank_iam_and_residency import MemoryBankScopeStore
        from agents.platform_config import (
            get_platform_config,
            resolve_project_number,
        )

        self.project_id = get_clean_project_id(project_id)
        self.location = location.strip()
        MemoryBankScopeStore.enforce_regional_org_policy(self.location)
        default_mb = (
            f"projects/{self.project_id}/locations/{self.location}/"
            "reasoningEngines/cymbal-shared-mb"
        )
        raw_engine = (
            reasoning_engine_name
            or os.getenv("MEMORY_BANK_REASONING_ENGINE", "").strip()
            or os.getenv("AGENT_SANDBOX_REASONING_ENGINE_NAME", "").strip()
            or default_mb
        )
        allowed_prefixes = [
            f"projects/{self.project_id}/locations/{self.location}/reasoningEngines/",
        ]
        cfg = get_platform_config()
        resolved_number = resolve_project_number(cfg)
        active_env_project = (
            os.getenv("GOOGLE_CLOUD_PROJECT") or cfg.gcp.project_id or ""
        ).strip()
        if resolved_number and (
            cfg.gcp.project_id == self.project_id
            or active_env_project == self.project_id
        ):
            allowed_prefixes.append(
                f"projects/{resolved_number}/locations/{self.location}/reasoningEngines/"
            )
        if not any(raw_engine.startswith(p) for p in allowed_prefixes):
            raise PermissionError(
                "403 PERMISSION_DENIED: E_MEMORY_IAM_CEL_REGIONAL_LOCK: reasoning_engine_name "
                f"must reside under '{allowed_prefixes[0]}'."
            )
        self.reasoning_engine_name = raw_engine
        self._vertex_client_factory = vertex_client_factory

    @staticmethod
    def build_envelope_scope(
        envelope: ContextEnvelope,
        *,
        memory_scope: MemoryScope = MemoryScope.USER,
        agent_id: str | None = None,
    ) -> dict[str, str]:
        """Constructs the validated <=5-key flat `scope` dict strictly from `envelope`."""
        from agents.memory_bank_iam_and_residency import MemoryBankScopeStore

        if not isinstance(envelope, ContextEnvelope):
            raise PermissionError(
                "E_UNVERIFIED_ENVELOPE: Verified ContextEnvelope required."
            )
        if memory_scope == MemoryScope.GLOBAL:
            raise MemoryAccessDenied(
                "403 Forbidden: Serving runtime cannot write or scope GLOBAL Memory Bank entries."
            )
        resolved_agent = (
            agent_id or envelope.agent_id or "cymbal_shared_diagnostic_agent"
        ).strip()
        scope_dict: dict[str, str] = {
            "tenant_id": envelope.tenant.tenant_id,
            "agent_id": resolved_agent,
            "memory_scope": str(memory_scope.value),
        }
        if memory_scope in (MemoryScope.USER, MemoryScope.SESSION):
            scope_dict["user_id"] = envelope.security.sub
        if memory_scope == MemoryScope.SESSION:
            scope_dict["session_id"] = envelope.request.session_id
        MemoryBankScopeStore.validate_and_canonicalize_scope(scope_dict)
        return scope_dict

    def _client_for_envelope(
        self, envelope: ContextEnvelope
    ) -> tuple[Any, str]:
        """Builds a tenant-SA-scoped `vertexai.Client` using a brokered 300s `ct-*` token."""
        from agents.tenant_credentials import get_default_broker
        from google.oauth2.credentials import Credentials

        cred = get_default_broker(self.project_id).credential_for(envelope)
        oauth_creds = Credentials(token=cred.token)
        if self._vertex_client_factory is not None:
            return (
                self._vertex_client_factory(
                    project=self.project_id,
                    location=self.location,
                    credentials=oauth_creds,
                ),
                cred.principal,
            )
        import vertexai

        return (
            vertexai.Client(
                project=self.project_id,
                location=self.location,
                credentials=oauth_creds,
            ),
            cred.principal,
        )

    def create_memory(
        self,
        *,
        envelope: ContextEnvelope,
        fact: str,
        memory_scope: MemoryScope = MemoryScope.USER,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Creates a scoped memory fact via `agent_engines.memories.create` as the tenant SA."""
        from agents.memory_bank_iam_and_residency import MemoryBankScopeStore

        MemoryBankScopeStore.enforce_regional_org_policy(self.location)
        assert_can_write(envelope, memory_scope)
        clean_fact = fact.strip()
        if not clean_fact:
            raise ValueError(
                "E_EMPTY_MEMORY_FACT: Memory fact must be non-empty."
            )
        if not screen_retrieved_chunk({"fact": clean_fact}):
            raise MemoryAccessDenied(
                "E_MEMORY_QUARANTINED: fact failed the injection screen."
            )
        scope_dict = self.build_envelope_scope(
            envelope,
            memory_scope=memory_scope,
            agent_id=agent_id,
        )
        client, principal = self._client_for_envelope(envelope)
        create_kwargs: dict[str, Any] = {
            "name": self.reasoning_engine_name,
            "fact": clean_fact,
            "scope": scope_dict,
        }
        if self._vertex_client_factory is None:
            # `roles/aiplatform.memoryUser` grants `aiplatform.memories.*` (evaluated against
            # `memoryScope` IAM CEL) without `aiplatform.operations.get`, so live tenant `ct-*`
            # calls return the LRO handle without polling unscoped operations.get.
            create_kwargs["config"] = {"wait_for_completion": False}
        operation = client.agent_engines.memories.create(**create_kwargs)
        op_name = getattr(operation, "name", None) or str(operation)
        return {
            "status": "MEMORY_CREATED",
            "operation_name": op_name,
            "reasoning_engine_name": self.reasoning_engine_name,
            "location": self.location,
            "principal": principal,
            "scope": scope_dict,
        }

    def retrieve_memories(
        self,
        *,
        envelope: ContextEnvelope,
        search_query: str | None = None,
        top_k: int = 5,
        memory_scope: MemoryScope = MemoryScope.USER,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Retrieves exact-scope memories via `agent_engines.memories.retrieve` with screening."""
        from agents.memory_bank_iam_and_residency import MemoryBankScopeStore

        MemoryBankScopeStore.enforce_regional_org_policy(self.location)
        scope_dict = self.build_envelope_scope(
            envelope,
            memory_scope=memory_scope,
            agent_id=agent_id,
        )
        client, principal = self._client_for_envelope(envelope)
        retrieve_kwargs: dict[str, Any] = {
            "name": self.reasoning_engine_name,
            "scope": scope_dict,
        }
        if search_query and search_query.strip():
            retrieve_kwargs["similarity_search_params"] = {
                "search_query": search_query.strip(),
                "top_k": max(1, min(int(top_k), 25)),
            }
        else:
            retrieve_kwargs["simple_retrieval_params"] = {
                "page_size": max(1, min(int(top_k), 25)),
            }
        iterator = client.agent_engines.memories.retrieve(**retrieve_kwargs)
        clean_facts: list[str] = []
        quarantined_count = 0
        for item in iterator:
            mem_obj = getattr(item, "memory", item)
            raw_fact = str(getattr(mem_obj, "fact", "") or "")
            if not raw_fact:
                continue
            if not screen_retrieved_chunk({"fact": raw_fact}):
                quarantined_count += 1
                continue
            clean_facts.append(
                _egress_guardrail(
                    tenant_id=envelope.tenant.tenant_id,
                    tool_name="memory_bank_retrieve",
                    tool_args={"memory_scope": str(memory_scope.value)},
                    raw_output=raw_fact,
                )
            )
        return {
            "tenant_id": envelope.tenant.tenant_id,
            "reasoning_engine_name": self.reasoning_engine_name,
            "location": self.location,
            "principal": principal,
            "scope": scope_dict,
            "memories": clean_facts,
            "quarantined_count": quarantined_count,
        }


class LiveBigQueryOTelSink:
    """Subsystem 6 & FinOps: Live BigQuery OpenTelemetry Sink, Row Access Policies & COGS View."""

    def __init__(
        self,
        project_id: str = DEFAULT_GCP_PROJECT,
        dataset_id: str = DEFAULT_BQ_DATASET,
        table_id: str = DEFAULT_BQ_TABLE,
    ) -> None:
        from agents.kms_rest import configure_client_certificate_env
        from google.cloud import bigquery

        configure_client_certificate_env()
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        self.full_table_id = f"{project_id}.{dataset_id}.{table_id}"
        self.full_view_id = (
            f"{project_id}.{dataset_id}.v_tenant_tokenomics_cogs"
        )
        self._client = bigquery.Client(project=project_id)

    def verify_row_access_policies(self) -> dict[str, Any]:
        """Read-only check that every configured tenant has its row access policy.

        Policies and grantees are owned by Terraform (`google_bigquery_row_access_policy`); the
        runtime never issues DDL. Returns `{"policies": {...}, "missing": [...], "wrong_filter":
        [...]}`.
        """
        from agents.kms_rest import (
            build_spiffe_mtls_session,
            workload_spiffe_mtls_active,
        )

        if workload_spiffe_mtls_active():
            url = (
                f"https://bigquery.mtls.googleapis.com/bigquery/v2/projects/{self.project_id}/"
                f"datasets/{self.dataset_id}/tables/{self.table_id}/rowAccessPolicies"
            )
            resp = build_spiffe_mtls_session().get(url, timeout=30.0)
        else:
            import google.auth
            import google.auth.transport.requests

            creds, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            creds.refresh(google.auth.transport.requests.Request())
            url = (
                f"https://bigquery.googleapis.com/bigquery/v2/projects/{self.project_id}/datasets/"
                f"{self.dataset_id}/tables/{self.table_id}/rowAccessPolicies"
            )
            resp = httpx.get(
                url,
                headers={"Authorization": f"Bearer {creds.token}"},
                timeout=30.0,
            )
        resp.raise_for_status()
        found = {
            p["rowAccessPolicyReference"]["policyId"]: p.get(
                "filterPredicate", ""
            )
            for p in resp.json().get("rowAccessPolicies", [])
        }
        missing, wrong = [], []
        for tenant in _CFG.tenants:
            policy_id = tenant.row_policy_id()
            expected = f"tenant_id = '{tenant.tenant_id}'"
            if policy_id not in found:
                missing.append(policy_id)
            elif found[policy_id].replace('"', "'").strip() != expected:
                wrong.append(policy_id)
        return {"policies": found, "missing": missing, "wrong_filter": wrong}

    def insert_span(
        self,
        *,
        trace_id: str,
        tenant_id: str,
        subscription_tier: str,
        agent_id: str,
        model_id: str,
        tool_name: str | None,
        prompt_cache_hit: bool,
        thinking_tokens_budget: int,
        raw_input_tokens: int,
        billable_tokens: int,
        status: str,
    ) -> None:
        row = {
            "event_timestamp": dt.datetime.now(dt.UTC).isoformat(),
            "trace_id": trace_id,
            "tenant_id": tenant_id,
            "subscription_tier": subscription_tier,
            "agent_id": agent_id,
            "model_id": model_id,
            "tool_name": tool_name,
            "prompt_cache_hit": prompt_cache_hit,
            "thinking_tokens_budget": thinking_tokens_budget,
            "raw_input_tokens": raw_input_tokens,
            "billable_tokens": billable_tokens,
            "status": status,
        }
        errors = self._client.insert_rows_json(self.full_table_id, [row])
        if errors:
            raise RuntimeError(
                f"BigQuery OTel streaming insert failed: {errors}"
            )

    def query_tenant_cogs_view(self) -> list[dict[str, Any]]:
        """Queries `v_tenant_tokenomics_cogs` with mandatory resource attribution label."""
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            labels={"datacloud": "antigravity"}
        )
        sql = f"""
            SELECT
                tenant_id,
                subscription_tier,
                agent_id,
                model_id,
                total_turns,
                total_raw_tokens,
                total_billable_tokens,
                prompt_cache_savings_pct
            FROM `{self.full_view_id}`
            ORDER BY tenant_id, agent_id
        """
        rows = self._client.query(sql, job_config=job_config).result()
        return [dict(r.items()) for r in rows]


class LiveGCSCMEKRunbookVault:
    """Hop 5 Pooled Cloud Storage Runbook Vault (`gs://<project>-runbooks`) with Per-Object KMS
    CMEK.
    """

    def __init__(self, project_id: str = DEFAULT_GCP_PROJECT) -> None:
        self.project_id = get_clean_project_id(project_id)
        self.bucket_name = os.getenv(
            "RUNBOOK_BUCKET_NAME", _CFG.runbook_bucket(self.project_id)
        )

    def read_tenant_runbook(
        self, *, envelope: ContextEnvelope, target_object_path: str
    ) -> dict[str, Any]:
        """Reads a tenant runbook from the pooled GCS bucket, verifying prefix + per-object Cloud
        KMS CMEK.
        """
        expected_prefix = f"{envelope.tenant.tenant_id}/"
        if not target_object_path.startswith(expected_prefix):
            raise PermissionError(
                "403 Forbidden: E_RUNBOOK_CROSS_TENANT: Cross-Tenant Runbook Isolation "
                "— the object "
                "is outside the calling tenant's prefix."
            )

        _tenant_policy(self.project_id).assert_object(
            envelope.tenant.tenant_id, self.bucket_name, target_object_path
        )

        import urllib.parse

        headers = _tenant_headers(envelope, self.project_id)
        obj_enc = urllib.parse.quote(target_object_path, safe="")
        meta_url = f"https://storage.googleapis.com/storage/v1/b/{self.bucket_name}/o/{obj_enc}"
        meta_resp = httpx.get(meta_url, headers=headers, timeout=15.0)
        meta_resp.raise_for_status()
        meta = meta_resp.json()

        object_kms_key = str(meta.get("kmsKeyName", ""))
        if not object_kms_key.startswith(envelope.tenant.cmek_key_name):
            raise PermissionError(
                "E_CMEK_KEY_MISMATCH: the object is not encrypted with the calling tenant's CMEK "
                "key."
            )

        media_resp = httpx.get(
            f"{meta_url}?alt=media", headers=headers, timeout=15.0
        )
        media_resp.raise_for_status()
        raw_text = media_resp.text

        screen_tool_output_for_indirect_injection(
            raw_output=raw_text, tool_name="gcs_cmek_runbook_vault"
        )
        sanitized_text = _egress_guardrail(
            tenant_id=envelope.tenant.tenant_id,
            tool_name="gcs_cmek_runbook_vault",
            tool_args={"object": target_object_path},
            raw_output=raw_text,
        )
        return {
            "tenant_id": envelope.tenant.tenant_id,
            "bucket": self.bucket_name,
            "object_name": meta.get("name"),
            "kms_key_name": object_kms_key,
            "sanitized_content": sanitized_text,
        }
