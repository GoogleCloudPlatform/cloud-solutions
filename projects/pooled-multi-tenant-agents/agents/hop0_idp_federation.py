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

# pylint: disable=import-outside-toplevel,inconsistent-quotes,line-too-long
# pylint: disable=unused-argument

"""Hop 0: Multi-Tenant Enterprise IdP Federation via Google Identity Platform (Pattern A: Pool).

Hop 0 runs before Hop 1 (`EdgeAuthVerifier.exchange_obo_token`). It turns a raw ID token into a
normalized, verified claim set: `tenant_id`, `sub`, one intra-tenant RBAC role, and the upstream
IdP. Two modes share the same checks.

**Primary: Google Identity Platform broker (Pattern A reference diagram).**
Each tenant's IdP (Okta, Google, Ping, Microsoft Entra ID) is configured as a SAML/OIDC provider
on that tenant's Identity Platform tenant. Users sign in through Identity Platform, which issues
one short-lived (1 hour) RS256 ID token for every tenant:
- `iss = https://securetoken.google.com/{project}`, `aud = {project}`.
- `firebase.tenant` (signed by Google) identifies the Identity Platform tenant, and maps to
  exactly one pooled `tenant_id`.
- `firebase.sign_in_provider` (for example `saml.okta-tenant-a`) must be one of the providers
  onboarded for that tenant. This blocks password, anonymous, or another tenant's provider.
- The role comes from a custom claim set by a `beforeSignIn` blocking function (default
  `cymbal_role`), or from a SAML attribute in `firebase.sign_in_attributes`.
- There is no directory sync: identity and role are taken from the token on every request.

**Fallback: direct federation.** For tenants that cannot use the broker, the gateway trusts the
tenant's own issuer (Okta org, Entra directory, Google) with an exact issuer to tenant binding,
per-issuer JWKS, a per-tenant audience, the Entra `tid` directory check, and role mapping from
Okta `groups` or Entra App Roles (`roles`).

Both modes:
- reject `alg: none` and HMAC algorithms;
- pin the algorithm per issuer;
- verify the signature by `kid`;
- check `iss`, `aud`, `exp`, `iat`, and a maximum token lifetime (short-lived credentials);
- reject a self-asserted `tenant_id` that disagrees with the verified binding;
- fail closed when no role maps.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol

import jwt
from agents.context import TENANT_DIRECTORY, USER_ROLE_ALLOWED_SCOPES


class FederatedIdP(StrEnum):
    """Upstream IdP families. The first three match `workspace_plugins.IdPAdapterType`."""

    GOOGLE_WORKSPACE_OIDC = "google_workspace_oidc"
    MICROSOFT_ENTRA_OIDC = "microsoft_entra_oidc"
    OKTA_ENTERPRISE_OIDC = "okta_enterprise_oidc"
    PING_IDENTITY = "ping_identity"


AUTH_BROKER_IDENTITY_PLATFORM = "google_identity_platform"
AUTH_BROKER_DIRECT = "direct"

GCIP_ISSUER_PREFIX = "https://securetoken.google.com/"
GCIP_JWKS_URI = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"

# Asymmetric algorithms only. HMAC (`HS*`) and `none` can never be enabled for an issuer because a
# verifier that accepts them can be tricked into using a public key as an HMAC secret.
_PERMITTED_ASYMMETRIC_ALGS = frozenset(
    {"RS256", "RS384", "RS512", "PS256", "ES256", "ES384"}
)

# Entra ID "multi-tenant app" issuers are not bound to one directory and cannot anchor a tenant.
_ENTRA_NON_DIRECTORY_SEGMENTS = frozenset(
    {"common", "organizations", "consumers"}
)

# Most-privileged role wins when several IdP roles/groups map for the same user.
_ROLE_PRIVILEGE_ORDER = ("sre_admin", "compliance_officer", "read_only_analyst")

_MAX_SUB_LENGTH = 128

IDENTITY_ROLE_MAP: Mapping[str, str] = MappingProxyType(
    {role: role for role in _ROLE_PRIVILEGE_ORDER}
)
DEFAULT_ENTRA_APP_ROLE_MAP: Mapping[str, str] = MappingProxyType(
    {
        "Cymbal.SreAdmin": "sre_admin",
        "Cymbal.ComplianceOfficer": "compliance_officer",
        "Cymbal.ReadOnlyAnalyst": "read_only_analyst",
    }
)
DEFAULT_OKTA_GROUP_MAP: Mapping[str, str] = MappingProxyType(
    {
        "cymbal-sre-admins": "sre_admin",
        "cymbal-compliance-officers": "compliance_officer",
        "cymbal-read-only-analysts": "read_only_analyst",
    }
)

DEFAULT_GATEWAY_AUDIENCE = "https://agent-gateway.cymbal.internal"


def _validate_algs(algs: tuple[str, ...]) -> None:
    if not algs or not set(algs) <= _PERMITTED_ASYMMETRIC_ALGS:
        raise ValueError(
            f"E_HOP0_DISALLOWED_ALG_CONFIG: allowed_algs {algs} must be a non-empty subset of "
            f"{sorted(_PERMITTED_ASYMMETRIC_ALGS)}."
        )


def _validate_role_map(mapping: Mapping[str, str]) -> None:
    for role in mapping.values():
        if role not in USER_ROLE_ALLOWED_SCOPES:
            raise ValueError(
                f"E_HOP0_UNKNOWN_RBAC_ROLE: '{role}' is not a known role."
            )


# ---------------------------------------------------------------------------------------------
# Configuration records (control plane)
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class IdentityPlatformBrokerConfig:
    """The single Google Identity Platform project that brokers every pooled tenant's IdP."""

    project_id: str
    allowed_algs: tuple[str, ...] = ("RS256",)
    jwks_uri: str = GCIP_JWKS_URI
    max_token_lifetime_seconds: int = 3600

    def __post_init__(self) -> None:
        if not self.project_id or "/" in self.project_id:
            raise ValueError(
                "E_HOP0_INVALID_GCIP_PROJECT: project_id is required."
            )
        _validate_algs(self.allowed_algs)

    @property
    def issuer(self) -> str:
        return f"{GCIP_ISSUER_PREFIX}{self.project_id}"

    @property
    def audience(self) -> str:
        return self.project_id


@dataclass(frozen=True)
class IdentityPlatformTenantConfig:
    """Binds one Identity Platform tenant (`firebase.tenant`) to one pooled `tenant_id`."""

    tenant_id: str
    gcip_tenant_id: str
    upstream_idp: FederatedIdP
    allowed_sign_in_providers: tuple[str, ...]
    role_claim: str = "cymbal_role"
    group_to_role: Mapping[str, str] = IDENTITY_ROLE_MAP
    max_token_lifetime_seconds: int | None = None

    def __post_init__(self) -> None:
        if not self.gcip_tenant_id:
            raise ValueError(
                "E_HOP0_INVALID_GCIP_TENANT: gcip_tenant_id is required."
            )
        if not self.allowed_sign_in_providers:
            raise ValueError(
                "E_HOP0_NO_SIGN_IN_PROVIDERS: At least one sign-in provider "
                "(for example 'saml.okta-tenant-a') must be allowed."
            )
        if (
            self.max_token_lifetime_seconds is not None
            and self.max_token_lifetime_seconds < 60
        ):
            raise ValueError(
                "E_HOP0_INVALID_LIFETIME_CAP: max_token_lifetime_seconds must be >= 60."
            )
        _validate_role_map(self.group_to_role)


@dataclass(frozen=True)
class FederatedIdPConfig:
    """Direct-federation fallback: one tenant trusts its own IdP issuer."""

    tenant_id: str
    provider: FederatedIdP
    issuer: str
    audience: str
    allowed_algs: tuple[str, ...] = ("RS256",)
    directory_id: str | None = None
    role_claim: str = "groups"
    group_to_role: Mapping[str, str] = field(default_factory=dict)
    jwks_uri: str | None = None
    max_token_lifetime_seconds: int = 5400

    def __post_init__(self) -> None:
        _validate_algs(self.allowed_algs)
        if not self.issuer.startswith("https://"):
            raise ValueError(
                "E_HOP0_INSECURE_ISSUER: IdP issuer must be an https:// URL."
            )
        if self.issuer.startswith(GCIP_ISSUER_PREFIX):
            raise ValueError(
                "E_HOP0_BROKER_ISSUER_RESERVED: Identity Platform issuers are shared by all "
                "tenants and must be registered with IdentityPlatformTenantConfig."
            )
        if not self.audience:
            raise ValueError(
                "E_HOP0_MISSING_AUDIENCE: Tenant app/client ID (aud) is required."
            )
        _validate_role_map(self.group_to_role)
        if self.provider == FederatedIdP.MICROSOFT_ENTRA_OIDC:
            segments = self.issuer.removeprefix("https://").split("/")
            if (
                len(segments) < 2
                or segments[1].lower() in _ENTRA_NON_DIRECTORY_SEGMENTS
            ):
                raise ValueError(
                    "E_HOP0_ENTRA_MULTI_TENANT_ISSUER: Entra issuer must be directory-specific "
                    "(https://login.microsoftonline.com/{tid}/v2.0)."
                )
            if not self.directory_id or segments[1] != self.directory_id:
                raise ValueError(
                    "E_HOP0_ENTRA_DIRECTORY_MISMATCH: directory_id must equal the issuer's {tid}."
                )


IssuerConfig = FederatedIdPConfig | IdentityPlatformBrokerConfig


# ---------------------------------------------------------------------------------------------
# Signing key resolution
# ---------------------------------------------------------------------------------------------


class JWKSKeyResolver(Protocol):
    """Returns the verification key for `(issuer, kid)`; raises `LookupError` if unknown."""

    def get_key(self, *, config: IssuerConfig, kid: str) -> Any: ...


class StaticJWKSResolver:
    """In-memory JWKS for hermetic tests and offline demos (no network)."""

    def __init__(self) -> None:
        self._keys: dict[tuple[str, str], Any] = {}

    def add_key(self, *, issuer: str, kid: str, public_key: Any) -> None:
        self._keys[(issuer, kid)] = public_key

    def get_key(self, *, config: IssuerConfig, kid: str) -> Any:
        try:
            return self._keys[(config.issuer, kid)]
        except KeyError as exc:
            raise LookupError(
                "E_HOP0_UNKNOWN_KID: signing key not published by the issuer"
            ) from exc


class HttpJWKSResolver:
    """Live JWKS resolver using PyJWT's `PyJWKClient` (cached per issuer).

    Identity Platform publishes a fixed JWKS URI. Direct-federation issuers without a configured
    `jwks_uri` use OIDC discovery, and the discovered `issuer` must equal the configured issuer.
    `PyJWKClient` refetches once on an unknown `kid`, which covers IdP signing key rotation.
    """

    def __init__(
        self,
        *,
        discovery_fetcher: Callable[[str], dict[str, Any]] | None = None,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self._discovery_fetcher = discovery_fetcher or self._fetch_discovery
        self._ttl = cache_ttl_seconds
        self._clients: dict[str, jwt.PyJWKClient] = {}
        self._clients_lock = threading.Lock()

    @staticmethod
    def _fetch_discovery(issuer: str) -> dict[str, Any]:
        import httpx

        resp = httpx.get(
            f"{issuer.rstrip('/')}/.well-known/openid-configuration",
            timeout=10.0,
        )
        resp.raise_for_status()
        return dict(resp.json())

    def _client_for(self, config: IssuerConfig) -> jwt.PyJWKClient:
        client = self._clients.get(config.issuer)
        if client is not None:
            return client
        # One discovery fetch per issuer even when many threads see the first token at once.
        with self._clients_lock:
            client = self._clients.get(config.issuer)
            if client is not None:
                return client
            jwks_uri = config.jwks_uri
            if not jwks_uri:
                meta = self._discovery_fetcher(config.issuer)
                if meta.get("issuer") != config.issuer:
                    raise LookupError(
                        "OIDC discovery issuer does not match configured issuer"
                    )
                jwks_uri = str(meta["jwks_uri"])
            client = jwt.PyJWKClient(
                jwks_uri, cache_keys=True, lifespan=self._ttl
            )
            self._clients[config.issuer] = client
            return client

    def get_key(self, *, config: IssuerConfig, kid: str) -> Any:
        try:
            return self._client_for(config).get_signing_key(kid).key
        except jwt.PyJWKClientError as exc:
            raise LookupError(str(exc)) from exc


# ---------------------------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------------------------


class IdPFederationRegistry:
    """Control-plane index of trusted issuers and their tenant bindings."""

    def __init__(
        self, identity_platform: IdentityPlatformBrokerConfig | None = None
    ) -> None:
        self.identity_platform = identity_platform
        self._by_issuer: dict[str, FederatedIdPConfig] = {}
        self._by_gcip_tenant: dict[str, IdentityPlatformTenantConfig] = {}

    @staticmethod
    def _require_tenant_issuer(tenant_id: str, issuer: str) -> None:
        tenant_meta = TENANT_DIRECTORY.get(tenant_id)
        if tenant_meta is None:
            raise ValueError(
                f"E_HOP0_UNKNOWN_TENANT: '{tenant_id}' must be onboarded in TENANT_DIRECTORY "
                "before federating an IdP."
            )
        if tenant_meta.get("iss") != issuer:
            raise ValueError(
                f"E_HOP0_TENANT_ISSUER_MISMATCH: TENANT_DIRECTORY issuer for '{tenant_id}' is "
                f"'{tenant_meta.get('iss')}', not '{issuer}'."
            )

    def register(self, config: FederatedIdPConfig) -> None:
        """Direct-federation fallback: exactly one tenant per exact issuer."""
        self._require_tenant_issuer(config.tenant_id, config.issuer)
        existing = self._by_issuer.get(config.issuer)
        if existing is not None and existing.tenant_id != config.tenant_id:
            raise ValueError(
                f"E_HOP0_DUPLICATE_ISSUER: Issuer '{config.issuer}' is already federated to "
                f"'{existing.tenant_id}'. Shared issuers must use the Identity Platform broker."
            )
        self._by_issuer[config.issuer] = config

    def register_identity_platform_tenant(
        self, config: IdentityPlatformTenantConfig
    ) -> None:
        """Primary mode: bind one Identity Platform tenant to one pooled tenant."""
        if self.identity_platform is None:
            raise ValueError(
                "E_HOP0_BROKER_NOT_CONFIGURED: Create the registry with an "
                "IdentityPlatformBrokerConfig before registering Identity Platform tenants."
            )
        self._require_tenant_issuer(
            config.tenant_id, self.identity_platform.issuer
        )
        existing = self._by_gcip_tenant.get(config.gcip_tenant_id)
        if existing is not None and existing.tenant_id != config.tenant_id:
            raise ValueError(
                f"E_HOP0_DUPLICATE_GCIP_TENANT: Identity Platform tenant "
                f"'{config.gcip_tenant_id}' is already bound to '{existing.tenant_id}'."
            )
        for other in self._by_gcip_tenant.values():
            if (
                other.tenant_id == config.tenant_id
                and other.gcip_tenant_id != config.gcip_tenant_id
            ):
                raise ValueError(
                    f"E_HOP0_DUPLICATE_TENANT_BINDING: '{config.tenant_id}' is already bound to "
                    f"Identity Platform tenant '{other.gcip_tenant_id}'."
                )
        self._by_gcip_tenant[config.gcip_tenant_id] = config

    def is_broker_issuer(self, issuer: str) -> bool:
        return (
            self.identity_platform is not None
            and issuer == self.identity_platform.issuer
        )

    def for_issuer(self, issuer: str) -> FederatedIdPConfig:
        config = self._by_issuer.get(issuer)
        if config is None:
            raise PermissionError(
                f"E_HOP0_UNKNOWN_ISSUER: Issuer '{issuer}' is not federated to any tenant."
            )
        return config

    def for_gcip_tenant(
        self, gcip_tenant_id: str
    ) -> IdentityPlatformTenantConfig:
        config = self._by_gcip_tenant.get(gcip_tenant_id)
        if config is None:
            raise PermissionError(
                f"E_HOP0_GCIP_UNKNOWN_TENANT: Identity Platform tenant '{gcip_tenant_id}' is not "
                "bound to any pooled tenant."
            )
        return config

    @classmethod
    def with_anchor_tenants(cls) -> IdPFederationRegistry:
        """Direct-federation anchors: FinVault (Google OIDC) and RetailStream (Entra ID)."""
        registry = cls()
        registry.register(
            FederatedIdPConfig(
                tenant_id="tenant-finvault-alpha",
                provider=FederatedIdP.GOOGLE_WORKSPACE_OIDC,
                issuer="https://accounts.google.com",
                audience=DEFAULT_GATEWAY_AUDIENCE,
                role_claim="user_role",
            )
        )
        registry.register(
            FederatedIdPConfig(
                tenant_id="tenant-retailstream-beta",
                provider=FederatedIdP.MICROSOFT_ENTRA_OIDC,
                issuer="https://login.microsoftonline.com/retailstream-tenant-id/v2.0",
                audience=DEFAULT_GATEWAY_AUDIENCE,
                directory_id="retailstream-tenant-id",
                role_claim="roles",
                group_to_role=DEFAULT_ENTRA_APP_ROLE_MAP,
            )
        )
        return registry


# ---------------------------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------------------------


class HopZeroFederationGate:
    """Verifies a raw ID token (broker or direct) and returns Hop 1-ready normalized claims."""

    def __init__(
        self,
        *,
        registry: IdPFederationRegistry,
        resolver: JWKSKeyResolver,
        leeway_seconds: int = 60,
    ) -> None:
        self.registry = registry
        self.resolver = resolver
        self.leeway_seconds = leeway_seconds

    def verify_and_normalize(self, raw_jwt: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(raw_jwt)
            unverified = jwt.decode(
                raw_jwt, options={"verify_signature": False}
            )
        except jwt.PyJWTError as exc:
            raise PermissionError(f"E_HOP0_MALFORMED_TOKEN: {exc}") from exc

        alg = str(header.get("alg", ""))
        if alg not in _PERMITTED_ASYMMETRIC_ALGS:
            raise PermissionError(
                f"E_HOP0_DISALLOWED_ALG: '{alg}' is not an accepted asymmetric algorithm."
            )
        kid = str(header.get("kid", ""))
        issuer = str(unverified.get("iss", ""))

        if self.registry.is_broker_issuer(issuer):
            return self._verify_identity_platform(raw_jwt, alg=alg, kid=kid)
        return self._verify_direct(raw_jwt, alg=alg, kid=kid, issuer=issuer)

    # -- Primary: Google Identity Platform --------------------------------------------------

    def _verify_identity_platform(
        self, raw_jwt: str, *, alg: str, kid: str
    ) -> dict[str, Any]:
        broker = self.registry.identity_platform
        if broker is None:
            raise PermissionError(
                "E_HOP0_BROKER_NOT_CONFIGURED: No Identity Platform broker."
            )
        claims = self._verify_signature_and_standard_claims(
            raw_jwt,
            config=broker,
            alg=alg,
            kid=kid,
            required=("iss", "sub", "aud", "exp", "iat", "auth_time"),
            enforce_lifetime=False,
        )

        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub or len(sub) > _MAX_SUB_LENGTH:
            raise PermissionError(
                "E_HOP0_INVALID_SUBJECT: `sub` must be 1-128 characters."
            )
        if int(claims["auth_time"]) > int(time.time()) + self.leeway_seconds:
            raise PermissionError(
                "E_HOP0_INVALID_AUTH_TIME: `auth_time` is in the future."
            )

        raw_firebase = claims.get("firebase")
        firebase: dict[str, Any] = (
            raw_firebase if isinstance(raw_firebase, dict) else {}
        )
        gcip_tenant = firebase.get("tenant")
        if not isinstance(gcip_tenant, str) or not gcip_tenant:
            raise PermissionError(
                "E_HOP0_GCIP_MISSING_TENANT: Token was not issued for an Identity Platform "
                "tenant (project-level users are not pooled tenants)."
            )
        config = self.registry.for_gcip_tenant(gcip_tenant)

        effective_lifetime_limit = (
            config.max_token_lifetime_seconds
            if config.max_token_lifetime_seconds is not None
            else broker.max_token_lifetime_seconds
        )
        token_lifetime = int(claims["exp"]) - int(claims["iat"])
        if token_lifetime > effective_lifetime_limit:
            raise PermissionError(
                f"E_HOP0_TOKEN_LIFETIME_TOO_LONG: Token lifetime {token_lifetime}s exceeds the "
                f"{effective_lifetime_limit}s short-lived credential limit."
            )

        sign_in_provider = str(firebase.get("sign_in_provider", ""))
        if sign_in_provider not in config.allowed_sign_in_providers:
            raise PermissionError(
                "E_HOP0_GCIP_PROVIDER_NOT_ALLOWED: the sign-in provider is not onboarded for this "
                "tenant."
            )

        self._reject_tenant_spoof(
            claims, config.tenant_id, f"tenant '{gcip_tenant}'"
        )

        raw_values = claims.get(config.role_claim)
        attributes = firebase.get("sign_in_attributes")
        if raw_values is None and isinstance(attributes, dict):
            raw_values = attributes.get(config.role_claim)
        user_role = self._map_role(
            config.group_to_role, raw_values, config.role_claim
        )

        return {
            "iss": broker.issuer,
            "sub": sub,
            "exp": int(claims["exp"]),
            "iat": int(claims["iat"]),
            "jti": str(claims.get("jti") or f"hop0-{uuid.uuid4().hex}"),
            "tenant_id": config.tenant_id,
            "user_role": user_role,
            "idp_provider": str(config.upstream_idp),
            "auth_broker": AUTH_BROKER_IDENTITY_PLATFORM,
            "sign_in_provider": sign_in_provider,
            "gcip_tenant_id": gcip_tenant,
        }

    # -- Fallback: direct federation ---------------------------------------------------------

    def _verify_direct(
        self, raw_jwt: str, *, alg: str, kid: str, issuer: str
    ) -> dict[str, Any]:
        config = self.registry.for_issuer(issuer)
        claims = self._verify_signature_and_standard_claims(
            raw_jwt,
            config=config,
            alg=alg,
            kid=kid,
            required=("iss", "sub", "aud", "exp", "iat"),
        )

        if (
            config.provider == FederatedIdP.MICROSOFT_ENTRA_OIDC
            and claims.get("tid") != config.directory_id
        ):
            raise PermissionError(
                "E_HOP0_ENTRA_DIRECTORY_MISMATCH: the token's directory is not the onboarded one."
            )

        self._reject_tenant_spoof(
            claims, config.tenant_id, f"issuer '{config.issuer}'"
        )
        user_role = self._resolve_direct_role(config, claims)

        return {
            "iss": config.issuer,
            "sub": str(claims["sub"]),
            "exp": int(claims["exp"]),
            "iat": int(claims["iat"]),
            "jti": str(
                claims.get("jti")
                or claims.get("uti")
                or f"hop0-{uuid.uuid4().hex}"
            ),
            "tenant_id": config.tenant_id,
            "user_role": user_role,
            "idp_provider": str(config.provider),
            "auth_broker": AUTH_BROKER_DIRECT,
        }

    # -- Shared helpers ------------------------------------------------------------------------

    def _verify_signature_and_standard_claims(
        self,
        raw_jwt: str,
        *,
        config: IssuerConfig,
        alg: str,
        kid: str,
        required: tuple[str, ...],
        enforce_lifetime: bool = True,
    ) -> dict[str, Any]:
        if alg not in config.allowed_algs:
            raise PermissionError(
                f"E_HOP0_DISALLOWED_ALG: '{alg}' is not allowed for issuer '{config.issuer}' "
                f"(allowed: {list(config.allowed_algs)})."
            )
        try:
            key = self.resolver.get_key(config=config, kid=kid)
        except LookupError as exc:
            raise PermissionError(f"E_HOP0_UNKNOWN_KID: {exc}") from exc

        try:
            claims = dict(
                jwt.decode(
                    raw_jwt,
                    key,
                    algorithms=list(config.allowed_algs),
                    audience=config.audience,
                    issuer=config.issuer,
                    leeway=self.leeway_seconds,
                    options={"require": list(required)},
                )
            )
        except jwt.ExpiredSignatureError as exc:
            raise PermissionError(
                "E_HOP0_TOKEN_EXPIRED: ID token has expired."
            ) from exc
        except jwt.InvalidAudienceError as exc:
            raise PermissionError(
                f"E_HOP0_AUDIENCE_MISMATCH: Token audience is not '{config.audience}'."
            ) from exc
        except jwt.InvalidSignatureError as exc:
            raise PermissionError(
                "E_HOP0_INVALID_SIGNATURE: Signature check failed."
            ) from exc
        except jwt.PyJWTError as exc:
            raise PermissionError(f"E_HOP0_INVALID_TOKEN: {exc}") from exc

        if enforce_lifetime:
            lifetime = int(claims["exp"]) - int(claims["iat"])
            if lifetime > config.max_token_lifetime_seconds:
                raise PermissionError(
                    f"E_HOP0_TOKEN_LIFETIME_TOO_LONG: Token lifetime {lifetime}s exceeds the "
                    f"{config.max_token_lifetime_seconds}s short-lived credential limit."
                )
        return claims

    @staticmethod
    def _reject_tenant_spoof(
        claims: dict[str, Any], tenant_id: str, bound_by: str
    ) -> None:
        asserted = claims.get("tenant_id")
        if asserted is not None and asserted != tenant_id:
            raise PermissionError(
                "E_HOP0_TENANT_CLAIM_SPOOF: the token asserts a tenant that its issuer is not "
                "bound to."
            )

    @staticmethod
    def _map_role(
        mapping: Mapping[str, str], raw_values: Any, claim_name: str
    ) -> str:
        if raw_values is None:
            raw_values = []
        elif isinstance(raw_values, str):
            raw_values = [raw_values]
        mapped = {
            mapping[v]
            for v in raw_values
            if isinstance(v, str) and v in mapping
        }
        for role in _ROLE_PRIVILEGE_ORDER:
            if role in mapped:
                return role
        raise PermissionError(
            f"E_HOP0_NO_RBAC_ROLE: No '{claim_name}' value maps to an intra-tenant role."
        )

    def _resolve_direct_role(
        self, config: FederatedIdPConfig, claims: dict[str, Any]
    ) -> str:
        if (
            config.provider == FederatedIdP.GOOGLE_WORKSPACE_OIDC
            and not config.group_to_role
        ):
            return self._map_role(
                IDENTITY_ROLE_MAP,
                claims.get(config.role_claim),
                config.role_claim,
            )

        raw_values = claims.get(config.role_claim)
        claim_names = claims.get("_claim_names")
        if (
            raw_values is None
            and config.provider == FederatedIdP.MICROSOFT_ENTRA_OIDC
            and isinstance(claim_names, dict)
            and "groups" in claim_names
        ):
            raise PermissionError(
                "E_HOP0_ENTRA_GROUP_OVERAGE: Token has a groups overage marker and no App "
                "Roles. Assign users or groups to Cymbal App Roles in Entra ID."
            )
        return self._map_role(
            config.group_to_role, raw_values, config.role_claim
        )
