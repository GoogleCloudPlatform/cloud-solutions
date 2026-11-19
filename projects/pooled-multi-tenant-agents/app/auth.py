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

"""Hop 0 wiring for the gateway: build the identity gate from config, plus the sandbox dev issuer.

Tenants describe how their users sign in under `identity:` in `config/tenants/<env>/*.yaml`
(direct federation with Google / Entra / Okta / Ping, or the Google Identity Platform broker).
`build_hop0()` turns that config into a `HopZeroFederationGate`, the same gate `exchange_federated_
idp_token` uses, so every caller identity is verified the same way.

**Sandbox dev issuer.** The demo UI, scripts and CI need real tokens without real IdP logins. When
`identity.dev_issuer` is on (allowed only in the `sandbox` environment with synthetic data, enforced
by config validation), an in-process RSA key is published as the signing key for every configured
issuer, and `mint_sandbox_token()` issues tokens in each tenant's own IdP format. They go through
the
exact production verification path; only the key source differs. In any other environment the gate
fetches real JWKS over HTTPS and the dev issuer does not exist.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from agents import platform_config
from agents.hop0_idp_federation import (
    DEFAULT_ENTRA_APP_ROLE_MAP,
    IDENTITY_ROLE_MAP,
    FederatedIdP,
    FederatedIdPConfig,
    HopZeroFederationGate,
    HttpJWKSResolver,
    IdentityPlatformBrokerConfig,
    IdentityPlatformTenantConfig,
    IdPFederationRegistry,
    StaticJWKSResolver,
)
from agents.platform_config import (
    LOCAL_SANDBOX_ENV,
    MANAGED_RUNTIME_ENV,
    PlatformConfig,
    TenantSpec,
    get_platform_config,
)
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)

_PROVIDERS = {
    "google": FederatedIdP.GOOGLE_WORKSPACE_OIDC,
    "entra": FederatedIdP.MICROSOFT_ENTRA_OIDC,
    "okta": FederatedIdP.OKTA_ENTERPRISE_OIDC,
    "ping": FederatedIdP.PING_IDENTITY,
}
_DEFAULT_ROLE_CLAIM = {
    "google": "user_role",
    "entra": "roles",
    "okta": "groups",
    "ping": "groups",
}
DEV_ISSUER_TOKEN_TTL_SECONDS = 3600


class SandboxIssuerDisabled(PermissionError):
    """The dev issuer was requested outside a synthetic sandbox."""


def _role_map(tenant: TenantSpec) -> dict[str, str]:
    ident = tenant.identity
    if ident.role_map:
        return dict(ident.role_map)
    if ident.provider == "entra":
        return dict(DEFAULT_ENTRA_APP_ROLE_MAP)
    if ident.provider == "google":
        return {}  # Google tokens carry the platform role name directly
    return dict(
        IDENTITY_ROLE_MAP
    )  # Okta / Ping groups named after platform roles


def _role_claim(tenant: TenantSpec) -> str:
    return (
        tenant.identity.role_claim
        or _DEFAULT_ROLE_CLAIM[tenant.identity.provider]
    )


def build_registry(cfg: PlatformConfig) -> IdPFederationRegistry:
    """Trusted issuers and tenant bindings, from config only."""
    token_policy = platform_config.resolve_effective_token_policy(cfg)
    broker = (
        IdentityPlatformBrokerConfig(
            project_id=cfg.identity.broker_project_id,
            max_token_lifetime_seconds=token_policy.idp_broker_max_token_lifetime_seconds,
        )
        if cfg.identity.broker_project_id
        else None
    )
    registry = IdPFederationRegistry(identity_platform=broker)
    for t in cfg.tenants:
        ident = t.identity
        if ident.gcip_tenant_id:
            registry.register_identity_platform_tenant(
                IdentityPlatformTenantConfig(
                    tenant_id=t.tenant_id,
                    gcip_tenant_id=ident.gcip_tenant_id,
                    upstream_idp=_PROVIDERS[ident.provider],
                    allowed_sign_in_providers=ident.sign_in_providers,
                    role_claim=ident.role_claim or "cymbal_role",
                    group_to_role=_role_map(t) or IDENTITY_ROLE_MAP,
                    max_token_lifetime_seconds=ident.max_token_lifetime_seconds,
                )
            )
            continue
        direct_lifetime_limit = (
            ident.max_token_lifetime_seconds
            if ident.max_token_lifetime_seconds is not None
            else token_policy.idp_direct_max_token_lifetime_seconds
        )
        registry.register(
            FederatedIdPConfig(
                tenant_id=t.tenant_id,
                provider=_PROVIDERS[ident.provider],
                issuer=ident.issuer,
                audience=ident.audience or cfg.identity.gateway_audience,
                directory_id=ident.directory_id,
                role_claim=_role_claim(t),
                group_to_role=_role_map(t),
                # Sandbox: never reach out to the real IdP; production: OIDC discovery.
                jwks_uri=None,
                max_token_lifetime_seconds=direct_lifetime_limit,
            )
        )
    return registry


@dataclass
class DevIssuer:
    """Sandbox-only signer whose public key verifies tokens for every configured issuer."""

    cfg: PlatformConfig
    resolver: StaticJWKSResolver
    kid: str
    private_key: Any

    @classmethod
    def create(
        cls, cfg: PlatformConfig, resolver: StaticJWKSResolver
    ) -> DevIssuer:
        if not cfg.identity.dev_issuer:
            raise SandboxIssuerDisabled(
                "E_DEV_ISSUER_DISABLED: dev issuer is off in this config."
            )
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        kid = f"cymbal-dev-{uuid.uuid4().hex[:8]}"
        issuers = {t.identity.issuer for t in cfg.tenants}
        for issuer in issuers:
            resolver.add_key(
                issuer=issuer, kid=kid, public_key=key.public_key()
            )
        return cls(cfg=cfg, resolver=resolver, kid=kid, private_key=key)

    def _tenant(self, tenant_id: str) -> TenantSpec:
        for t in self.cfg.tenants:
            if t.tenant_id == tenant_id:
                return t
        raise PermissionError(
            "E_DEV_ISSUER_UNKNOWN_TENANT: tenant is not configured."
        )

    def mint(self, *, tenant_id: str, sub: str, role: str) -> str:
        """A token in the tenant's own IdP format, for a synthetic user."""
        t = self._tenant(tenant_id)
        ident = t.identity
        token_policy = platform_config.resolve_effective_token_policy(self.cfg)
        default_idp_cap = (
            token_policy.idp_broker_max_token_lifetime_seconds
            if ident.gcip_tenant_id
            else token_policy.idp_direct_max_token_lifetime_seconds
        )
        effective_idp_cap = (
            ident.max_token_lifetime_seconds
            if ident.max_token_lifetime_seconds is not None
            else default_idp_cap
        )
        token_ttl_seconds = min(DEV_ISSUER_TOKEN_TTL_SECONDS, effective_idp_cap)
        now = int(time.time())
        idp_role = next((k for k, v in _role_map(t).items() if v == role), role)
        claims: dict[str, Any] = {
            "sub": sub,
            "iat": now,
            "exp": now + token_ttl_seconds,
            "jti": f"dev-{uuid.uuid4().hex}",
        }
        if ident.gcip_tenant_id:
            claims |= {
                "iss": ident.issuer,
                "aud": self.cfg.identity.broker_project_id,
                "user_id": sub,
                "auth_time": now - 5,
                "firebase": {
                    "tenant": ident.gcip_tenant_id,
                    "sign_in_provider": ident.sign_in_providers[0],
                    "identities": {},
                },
                ident.role_claim or "cymbal_role": idp_role,
            }
        else:
            claims |= {
                "iss": ident.issuer,
                "aud": ident.audience or self.cfg.identity.gateway_audience,
                _role_claim(t): (
                    idp_role if ident.provider == "google" else [idp_role]
                ),
            }
            if ident.provider == "entra":
                claims["tid"] = ident.directory_id
        return jwt.encode(
            claims,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.kid},
        )


@dataclass
class Hop0Wiring:
    gate: HopZeroFederationGate
    dev_issuer: DevIssuer | None


_WIRING: dict[str, Hop0Wiring] = {}
_LOCK = threading.Lock()


_METADATA_PROJECT_URL = (
    "http://metadata.google.internal/computeMetadata/v1/project/project-id"
)
_metadata_cache: list[str | None] = []  # one probe per process
# Managed Google runtimes (Cloud Run services and jobs, GKE): trust only the metadata server.
_MANAGED_RUNTIME_ENV = (
    MANAGED_RUNTIME_ENV  # one list, shared with agents.context_signing
)


def _metadata_project() -> str | None:
    """Project ID from the Cloud Run metadata server, or None if it can't be read."""
    import httpx

    try:
        resp = httpx.get(
            _METADATA_PROJECT_URL,
            headers={"Metadata-Flavor": "Google"},
            timeout=2.0,
        )
    except httpx.HTTPError:
        return None
    return (
        resp.text.strip()
        if resp.status_code == 200 and resp.text.strip()
        else None
    )


def on_managed_runtime() -> bool:
    """Cloud Run service/job or GKE (the platform sets these; see `MANAGED_RUNTIME_ENV`)."""
    return any(os.getenv(v) for v in _MANAGED_RUNTIME_ENV)


def local_sandbox_opted_in() -> bool:
    """`CYMBAL_LOCAL_SANDBOX=1`: the operator explicitly asked for sandbox mode off a managed
    runtime (`make serve`, the offline scripts, the test suite).
    """
    return os.getenv(LOCAL_SANDBOX_ENV) == "1"


def running_project_id() -> str | None:
    """Where this process really runs.

    On managed runtimes (Cloud Run service/job, GKE) the answer comes only from the metadata server,
    read once
    per process: environment variables and config can be copied or changed at runtime, so they are
    never trusted there, and an unreadable metadata server means "unknown" (None). Off Cloud Run
    (local dev, CI) it is `GOOGLE_CLOUD_PROJECT` if set, else the config's project.
    """
    if on_managed_runtime():
        if not _metadata_cache:
            _metadata_cache.append(_metadata_project())
            if _metadata_cache[0] is None:
                logger.error(
                    "Running project unknown (metadata server unreadable): sandbox off."
                )
        return _metadata_cache[0]
    return (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or get_platform_config().gcp.project_id
    )


def sandbox_mode_active(cfg: PlatformConfig) -> bool:
    """Synthetic sandbox config *and* running in that config's own project.

    Gates every sandbox-only endpoint (demo personas, scripted scenarios, live 3P sandboxes) and
    the dev issuer, so a sandbox overlay deployed into another project exposes none of them.

    Off a managed runtime the "running project" is only an environment variable or the config's own
    value, which proves nothing, and `CYMBAL_ENV` defaults to `sandbox`. So there sandbox mode also
    needs the explicit `CYMBAL_LOCAL_SANDBOX=1` opt-in: without it a bare local run, or the
    container image started on a plain VM, exposes no dev issuer and no sandbox-only endpoint.
    """
    if not (
        cfg.environment == "sandbox"
        and cfg.data_classification == "synthetic"
        and bool(cfg.gcp.project_id)
    ):
        return False
    if not on_managed_runtime() and not local_sandbox_opted_in():
        return False
    return running_project_id() == cfg.gcp.project_id


def dev_issuer_allowed(cfg: PlatformConfig) -> bool:
    """Config labels alone are not enough: the process must also run in the sandbox's own project
    (see `running_project_id`). Guards against a defaulted `CYMBAL_ENV=sandbox` or a copied
    sandbox overlay deployed into another project, where the dev issuer would mint admin tokens.
    """
    if not cfg.identity.dev_issuer:
        return False
    if not sandbox_mode_active(cfg):
        if not on_managed_runtime() and not local_sandbox_opted_in():
            logger.error(
                "Sandbox dev issuer REFUSED: not on a managed runtime and %s=1 is not set",
                LOCAL_SANDBOX_ENV,
            )
        else:
            logger.error(
                "Sandbox dev issuer REFUSED: config project %s, running project %s",
                cfg.gcp.project_id,
                running_project_id(),
            )
        return False
    logger.warning(
        "SANDBOX DEV ISSUER ENABLED (project %s): anyone who can call the gateway can mint "
        "synthetic user tokens. Never enable outside the synthetic sandbox.",
        cfg.gcp.project_id,
    )
    return True


def build_hop0(cfg: PlatformConfig) -> Hop0Wiring:
    """Gate (and, in a synthetic sandbox only, the dev issuer) for one environment's config.

    The dev issuer's key lives in this process only: with several instances or workers, a token
    minted by one is unknown to another. Run the sandbox gateway with one instance (or move the
    key to Secret Manager) before relying on tokens across instances.
    """
    registry = build_registry(cfg)
    if dev_issuer_allowed(cfg):
        resolver = StaticJWKSResolver()
        issuer = DevIssuer.create(cfg, resolver)
        return Hop0Wiring(
            HopZeroFederationGate(registry=registry, resolver=resolver), issuer
        )
    return Hop0Wiring(
        HopZeroFederationGate(registry=registry, resolver=HttpJWKSResolver()),
        None,
    )


def get_hop0() -> Hop0Wiring:
    """Process-wide wiring for the current environment (built once per environment)."""
    cfg = get_platform_config()
    with _LOCK:
        if cfg.environment not in _WIRING:
            _WIRING[cfg.environment] = build_hop0(cfg)
        return _WIRING[cfg.environment]


def reset_hop0_cache() -> None:
    """Clears cached Hop 0 registry wiring so tests and config reloads pick up policy changes."""
    with _LOCK:
        _WIRING.clear()


def mint_sandbox_token(*, tenant_id: str, sub: str, role: str) -> str:
    """Sandbox only: an ID token for a synthetic user. Raises outside a synthetic sandbox."""
    wiring = get_hop0()
    # Re-checked per call: the wiring is cached per environment, the gate is not.
    if wiring.dev_issuer is None or not sandbox_mode_active(
        get_platform_config()
    ):
        raise SandboxIssuerDisabled(
            "E_DEV_ISSUER_DISABLED: not available in this environment."
        )
    return wiring.dev_issuer.mint(tenant_id=tenant_id, sub=sub, role=role)
