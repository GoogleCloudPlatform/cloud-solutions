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

# pylint: disable=inconsistent-quotes,line-too-long,protected-access

"""Shared P-256 KMS, context-token, and credential-broker fakes for unit and security tests."""

from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from agents import context as ctx
from agents import context_signing as cs
from agents import context_token as ct
from agents import kms_rest
from agents.interceptors import enforce_tenant_isolation_interceptor
from agents.testing_fakes import MockADKCallbackContext
from agents.turn_engine import build_shared_diagnostic_agent
from broker_service.core import MintedCredential
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from mcp_server.server import handle_mcp_jsonrpc_request

FV = "tenant-finvault-alpha"
RS = "tenant-retailstream-beta"
PROJECT = "cymbal-multitenancy-example"
RUNTIME_SA = f"cymbal-pooled-runtime-sa@{PROJECT}.iam.gserviceaccount.com"
BROKER_URL = "https://cymbal-credential-broker.example"
KEY = "projects/test-project/locations/us-central1/keyRings/test-kr/cryptoKeys/ctx-signing"


def _envelope(
    tenant: str = RS, sub: str = "bob@retailstream.com", **kw: Any
) -> ctx.ContextEnvelope:
    """Mints a signed `ContextEnvelope` for `tenant` and `sub`."""
    claims = {
        "iss": str(ctx.TENANT_DIRECTORY[tenant]["iss"]),
        "sub": sub,
        "tenant_id": tenant,
        "user_role": "sre_admin",
        "exp": int(time.time()) + 600,
        "jti": f"gw-{uuid.uuid4().hex}",
        **kw,
    }
    return ctx.EdgeAuthVerifier().exchange_obo_token(
        verified_idp_claims=claims,
        dpop_proof={"jkt": f"jkt-{sub}", "jti": uuid.uuid4().hex},
        session_id=f"sess-{uuid.uuid4().hex[:8]}",
    )


def _envelope_with(
    issuer: cs.ContextTokenIssuer,
) -> tuple[str, ctx.ContextEnvelope]:
    """Mints a `(context_token, envelope)` pair using a custom `ContextTokenIssuer`."""
    envelope = ctx.EdgeAuthVerifier(context_issuer=issuer).exchange_obo_token(
        verified_idp_claims={
            "iss": str(ctx.TENANT_DIRECTORY[RS]["iss"]),
            "sub": "bob@retailstream.com",
            "tenant_id": RS,
            "user_role": "sre_admin",
            "exp": int(time.time()) + 600,
            "jti": f"gw-{uuid.uuid4().hex}",
        },
        dpop_proof={"jkt": "k", "jti": uuid.uuid4().hex},
        session_id="sess-kms",
    )
    return envelope.context_token, envelope


def _default_signer() -> cs.LocalTestSigner:
    """Returns the active per-run `LocalTestSigner` installed by `pytest_configure`."""
    signer = cs.get_context_token_issuer().signer
    assert isinstance(signer, cs.LocalTestSigner)
    return signer


def _compact(
    header: dict[str, Any],
    claims: dict[str, Any],
    sign: Callable[[bytes], bytes],
) -> str:
    """Serializes a compact JWS string signed by `sign`."""
    signing_input = (
        ct.b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + ct.b64url(json.dumps(claims, separators=(",", ":")).encode())
    )
    return f"{signing_input}.{ct.b64url(sign(signing_input.encode()))}"


def _es256(key: ec.EllipticCurvePrivateKey) -> Callable[[bytes], bytes]:
    """Returns a raw 64-byte `(r || s)` ES256 signing callable for `key`."""

    def _sign_payload(data: bytes) -> bytes:
        return ct.der_to_raw_signature(
            key.sign(data, ec.ECDSA(hashes.SHA256()))
        )

    return _sign_payload


def _with_token(state: dict[str, Any], token: str) -> dict[str, Any]:
    """Returns `state` carrying `token` and a matching depth-0 delegation tag."""
    return {
        **state,
        "temp:context_token": token,
        "temp:delegation_sig": ctx._delegation_tag(token, 0),
    }


async def _run_interceptor_check(state: dict[str, Any]) -> None:
    agent = build_shared_diagnostic_agent()
    await enforce_tenant_isolation_interceptor(
        MockADKCallbackContext(state=state, agent=agent)
    )


def _run_mcp_list(state: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(
        handle_mcp_jsonrpc_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            verified_adk_state=state,
        )
    )


def _assert_every_verifier_rejects(state: dict[str, Any]) -> None:
    """Asserts ADK interceptor, MCP server, and subagent propagation all reject `state`."""
    with pytest.raises(
        PermissionError, match=r"E_SUBAGENT_STATE_TAMPERING|E_SUBAGENT_UNSIGNED"
    ):
        asyncio.run(_run_interceptor_check(state))
    assert _run_mcp_list(state)["error"]["code"] == -32001
    with pytest.raises(
        PermissionError, match=r"E_SUBAGENT_STATE_TAMPERING|E_SUBAGENT_UNSIGNED"
    ):
        ctx.propagate_to_subagent(state)


class FakeKms:
    """Deterministic in-memory Cloud KMS P-256 asymmetric signing test double."""

    def __init__(self, versions: int = 1) -> None:
        """Initializes the instance."""
        self.keys = {
            f"{KEY}/cryptoKeyVersions/{n}": ec.generate_private_key(
                ec.SECP256R1()
            )
            for n in range(1, versions + 1)
        }
        self.disabled: set[str] = set()
        self.sign_calls = 0
        self.public_key_calls: list[str] = []
        self.fail: Exception | None = None
        self.public_key_fail: Exception | None = None
        self.public_key_hang_seconds = 0.0
        self.hang_seconds = 0.0

    def asymmetric_sign(self, *, name: str, digest_sha256: bytes) -> bytes:
        """Signs a prehashed SHA-256 digest with key version `name`."""
        self.sign_calls += 1
        if self.hang_seconds:
            time.sleep(self.hang_seconds)
        if self.fail is not None:
            raise self.fail
        return self.keys[name].sign(
            digest_sha256, ec.ECDSA(Prehashed(hashes.SHA256()))
        )

    def get_public_key(self, *, name: str) -> tuple[str, str]:
        """Returns `(pem_public_key, EC_SIGN_P256_SHA256)` for key version `name`."""
        self.public_key_calls.append(name)
        if self.public_key_hang_seconds:
            time.sleep(self.public_key_hang_seconds)
        if self.public_key_fail is not None:
            raise self.public_key_fail
        if name not in self.keys:
            raise kms_rest.KmsKeyRejectedError("E_KMS_HTTP_404", status=404)
        if name in self.disabled:
            raise kms_rest.KmsKeyRejectedError("E_KMS_HTTP_400", status=400)
        pem = (
            self.keys[name]
            .public_key()
            .public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        return pem, kms_rest.EC_SIGN_P256_SHA256


def _real_kms_token(fake: FakeKms) -> str:
    """Mints a context token signed by `fake` version 1."""
    signer = cs.KmsContextSigner(f"{KEY}/cryptoKeyVersions/1", client=fake)
    return _envelope_with(cs.ContextTokenIssuer(signer))[0]


def _jwt_unsigned(claims: dict[str, Any]) -> str:
    """Builds a Cloud Run proxy-verified OIDC JWT test fixture."""

    def encode_segment(payload: dict[str, Any]) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(payload).encode())
            .rstrip(b"=")
            .decode()
        )

    return (
        f"{encode_segment({'alg': 'RS256', 'typ': 'JWT'})}."
        f"{encode_segment(claims)}.SIGNATURE_REMOVED_BY_GOOGLE"
    )


def _caller(email: str = RUNTIME_SA, **overrides: Any) -> str:
    """Builds a `Bearer <jwt>` header value for broker caller identity tests."""
    claims = {
        "iss": "https://accounts.google.com",
        "aud": BROKER_URL,
        "email": email,
        "email_verified": True,
        "exp": int(time.time()) + 3600,
        **overrides,
    }
    return "Bearer " + _jwt_unsigned(claims)


class FakeMint:
    """Deterministic IAMCredentials minting test double for `CredentialBroker` tests."""

    def __init__(self) -> None:
        """Initializes the instance."""
        self.calls: list[tuple[str, str, Any]] = []
        self.fail: Exception | None = None

    def access_token(
        self, *, principal: str, lifetime_seconds: int
    ) -> MintedCredential:
        """Mints a synthetic short-lived OAuth2 access token for `principal`."""
        self.calls.append(("access_token", principal, lifetime_seconds))
        if self.fail:
            raise self.fail
        return MintedCredential(
            kind="access_token",
            token=f"fake-access-token-{uuid.uuid4().hex}",
            expires_at=time.time() + lifetime_seconds,
            principal=principal,
        )

    def id_token(self, *, principal: str, audience: str) -> MintedCredential:
        """Mints a synthetic OIDC ID token for `principal` and `audience`."""
        self.calls.append(("id_token", principal, audience))
        if self.fail:
            raise self.fail
        return MintedCredential(
            kind="id_token",
            token="eyJ.fake.idt",
            expires_at=time.time() + 3600,
            principal=principal,
        )
