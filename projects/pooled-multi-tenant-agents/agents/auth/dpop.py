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

# pylint: disable=inconsistent-quotes,line-too-long

"""RFC 7638 / RFC 8693 / RFC 9449 asymmetric ECDSA P-256 (`ES256`) JWT and `dpop+jwt` engine."""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url_uint(val: int, length: int = 32) -> str:
    return (
        base64.urlsafe_b64encode(val.to_bytes(length, "big"))
        .rstrip(b"=")
        .decode("ascii")
    )


class AsymmetricDPoPProvider:
    """Standards-compliant RFC 7638 / RFC 8693 / RFC 9449 ECDSA P-256 (`ES256`) JWT & DPoP
    Engine.
    """

    def __init__(self) -> None:
        self._idp_private_key = ec.generate_private_key(ec.SECP256R1())
        self._idp_public_key = self._idp_private_key.public_key()
        self._gateway_private_key = ec.generate_private_key(ec.SECP256R1())
        self._gateway_public_key = self._gateway_private_key.public_key()

    @staticmethod
    def generate_client_keypair() -> ec.EllipticCurvePrivateKey:
        """Generates an ephemeral ECDSA P-256 keypair for a sender-constrained DPoP client."""
        return ec.generate_private_key(ec.SECP256R1())

    @staticmethod
    def public_key_to_jwk(pub_key: ec.EllipticCurvePublicKey) -> dict[str, str]:
        """Serializes an EC P-256 public key into canonical RFC 7517 JWK format."""
        numbers = pub_key.public_numbers()
        return {
            "crv": "P-256",
            "kty": "EC",
            "x": _b64url_uint(numbers.x, 32),
            "y": _b64url_uint(numbers.y, 32),
        }

    @classmethod
    def compute_rfc7638_jwk_thumbprint(cls, jwk_dict: dict[str, str]) -> str:
        """Computes the RFC 7638 SHA-256 JWK thumbprint (`jkt`) with lexicographical keys."""
        canonical = json.dumps(
            {
                "crv": jwk_dict["crv"],
                "kty": jwk_dict["kty"],
                "x": jwk_dict["x"],
                "y": jwk_dict["y"],
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        digest = hashlib.sha256(canonical).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def mint_idp_oidc_jwt(
        self,
        *,
        iss: str,
        sub: str,
        tenant_id: str,
        aud: str = "https://agent-gateway.cymbal.internal",
        ttl_seconds: int = 3600,
    ) -> str:
        """Mints an asymmetric ES256-signed OIDC ID token representing Google OIDC or Entra ID."""
        now = int(time.time())
        claims = {
            "iss": iss,
            "sub": sub,
            "aud": aud,
            "tenant_id": tenant_id,
            "iat": now,
            "exp": now + ttl_seconds,
            "jti": f"oidc-{uuid.uuid4().hex[:12]}",
        }
        return jwt.encode(
            claims,
            self._idp_private_key,
            algorithm="ES256",
            headers={"kid": "idp-es256-1"},
        )

    @classmethod
    def mint_dpop_proof_jwt(
        cls,
        *,
        client_private_key: ec.EllipticCurvePrivateKey,
        htm: str = "POST",
        htu: str = "https://agent-gateway.cymbal.internal/api/v1/invoke-agent",
        jti: str | None = None,
        ath: str | None = None,
    ) -> str:
        """Mints an RFC 9449 `dpop+jwt` proof signed by the client's ECDSA P-256 private key.

        `ath` (base64url SHA-256 of the access token) binds the proof to that token.
        """
        jwk_pub = cls.public_key_to_jwk(client_private_key.public_key())
        payload: dict[str, Any] = {
            "htm": htm.upper(),
            "htu": htu,
            "iat": int(time.time()),
            "jti": jti or f"dpop-{uuid.uuid4().hex}",
        }
        if ath is not None:
            payload["ath"] = ath
        headers = {
            "typ": "dpop+jwt",
            "alg": "ES256",
            "jwk": jwk_pub,
        }
        return jwt.encode(
            payload, client_private_key, algorithm="ES256", headers=headers
        )

    def verify_and_decode_dpop_jwt(
        self,
        *,
        dpop_jwt: str,
        expected_htm: str = "POST",
        expected_htu: str | None = None,
    ) -> dict[str, Any]:
        """Verifies the embedded JWK signature of an RFC 9449 `dpop+jwt` and computes `cnf.jkt`."""
        unverified_header = jwt.get_unverified_header(dpop_jwt)
        if (
            unverified_header.get("typ") != "dpop+jwt"
            or unverified_header.get("alg") != "ES256"
        ):
            raise PermissionError(
                "E_INVALID_DPOP_HEADER: DPoP proof must use typ='dpop+jwt' and alg='ES256'."
            )

        jwk_dict = unverified_header.get("jwk")
        if (
            not isinstance(jwk_dict, dict)
            or jwk_dict.get("kty") != "EC"
            or jwk_dict.get("crv") != "P-256"
            or "d"
            in jwk_dict  # RFC 9449: the header must carry a public key only
        ):
            raise PermissionError(
                "E_INVALID_DPOP_JWK: DPoP header needs a public P-256 EC JWK."
            )

        pub_key = jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(jwk_dict))
        claims = jwt.decode(dpop_jwt, pub_key, algorithms=["ES256"])

        if str(claims.get("htm", "")).upper() != expected_htm.upper():
            raise PermissionError(
                "E_DPOP_HTM_MISMATCH: DPoP proof HTTP method mismatch."
            )
        if expected_htu and str(claims.get("htu", "")) != expected_htu:
            raise PermissionError(
                "E_DPOP_HTU_MISMATCH: DPoP proof bound to '"
                f"{claims.get('htu')}', expected '{expected_htu}'."
            )

        jkt = self.compute_rfc7638_jwk_thumbprint(jwk_dict)
        return {
            "jkt": jkt,
            "jti": str(claims["jti"]),
            "htm": str(claims["htm"]),
            "htu": str(claims["htu"]),
            "iat": int(claims["iat"]),
        }

    def verify_idp_jwt(self, idp_jwt: str) -> dict[str, Any]:
        """Verifies an inbound ES256 OIDC JWT signed by the federated IdP."""
        try:
            return dict(
                jwt.decode(
                    idp_jwt,
                    self._idp_public_key,
                    algorithms=["ES256"],
                    audience="https://agent-gateway.cymbal.internal",
                )
            )
        except jwt.PyJWTError as exc:
            raise PermissionError(f"E_INVALID_OIDC_JWT: {exc}") from exc
