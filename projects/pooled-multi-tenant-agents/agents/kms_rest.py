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

# pylint: disable=import-outside-toplevel,line-too-long,protected-access

"""Minimal Cloud KMS REST client for the context-signing key (ADR-0014 D1).

Two calls only: `asymmetricSign` (gateway) and `getPublicKey` (verifiers). The repository talks to
Cloud KMS over REST elsewhere too (`agents/gcp_live_bridge.py`), so this adds no new dependency.

- Callers run every call under a hard overall deadline (`run_with_deadline`, credential refresh
  included), so a hung KMS becomes a bounded error instead of a stuck request.
- Request and response integrity is checked with CRC32C, as the KMS docs recommend.
- No key material is held here: KMS keys are non-exportable, and public keys are returned as PEM.

Tests inject a fake client with the same two methods; nothing in the hermetic suite calls GCP.
"""

from __future__ import annotations

import base64
import concurrent.futures
import functools
import os
import threading
from typing import Any, Protocol

KMS_API = "https://cloudkms.googleapis.com/v1"
KMS_MTLS_API = "https://cloudkms.mtls.googleapis.com/v1"
# Set on Cloud Run services with Cloud Run Agent Identity (--identity-certificate): their tokens are
# bound to the workload certificate, so Google APIs must be called over mTLS (A0/S0 spikes).
CERTIFICATE_CONFIG_ENV = "GOOGLE_API_CERTIFICATE_CONFIG"


def mtls_enabled() -> bool:
    """mTLS to Google APIs when a workload certificate config is present (`CYMBAL_KMS_MTLS=0`
    turns it off explicitly)."""
    return (
        bool(os.getenv(CERTIFICATE_CONFIG_ENV))
        and os.getenv("CYMBAL_KMS_MTLS", "1") != "0"
    )


def workload_spiffe_mtls_active() -> bool:
    """True when running on Cloud Run with a workload SPIFFE certificate config."""
    cert_cfg = (os.getenv(CERTIFICATE_CONFIG_ENV) or "").strip()
    if not cert_cfg:
        return False
    return bool(os.getenv("K_SERVICE")) or cert_cfg.startswith(
        "/var/run/secrets/workload-spiffe-credentials/"
    )


def configure_client_certificate_env() -> None:
    """Preserve workload SPIFFE mTLS on Cloud Run Agent Identity; disable corporate workstation mTLS
    locally.
    """
    if workload_spiffe_mtls_active():
        os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "true"
        return
    os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"
    os.environ["CLOUDSDK_CONTEXT_AWARE_USE_CLIENT_CERTIFICATE"] = "false"
    os.environ["CLOUDSDK_CONTEXT_AWARE_USE_MTLS_FOR_GRPC"] = "false"
    os.environ.pop(CERTIFICATE_CONFIG_ENV, None)


def build_spiffe_mtls_session() -> Any:
    """Builds a google-auth `AuthorizedSession` presenting the Cloud Run SPIFFE workload cert."""
    import google.auth
    import google.auth.transport.requests

    configure_client_certificate_env()
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = google.auth.transport.requests.AuthorizedSession(creds)
    session.configure_mtls_channel()
    if not getattr(session, "is_mtls", False):
        raise KmsUnavailableError(
            "E_KMS_MTLS_UNAVAILABLE: no workload certificate"
        )
    return session


def build_firestore_client(*, project_id: str, database: str) -> Any:
    """Builds `firestore.Client`, switching to `FirestoreRestTransport` over SPIFFE mTLS on Cloud
    Run Agent Identity (`firestore.Client`'s default gRPC helper skips mTLS endpoint switching).
    """
    from google.cloud import firestore

    configure_client_certificate_env()
    client = firestore.Client(project=project_id, database=database)
    if workload_spiffe_mtls_active():
        from google.cloud.firestore_v1.services.firestore import (
            client as fs_gapic,
        )

        client._firestore_api_internal = fs_gapic.FirestoreClient(
            credentials=client._credentials,
            transport="rest",
        )
    return client


DEFAULT_KMS_TIMEOUT_SECONDS = 5.0
EC_SIGN_P256_SHA256 = "EC_SIGN_P256_SHA256"

# Bounded pool: a hung KMS cannot pile up unbounded threads; callers still time out on schedule.
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="kms-rest"
)


class KmsUnavailableError(RuntimeError):
    """KMS could not be reached, timed out, refused the call, or returned a corrupt response.

    `status` is the HTTP status when KMS answered (403 = the caller lacks IAM on the key).
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class KmsKeyRejectedError(KmsUnavailableError):
    """A definitive answer about the key version: not found (404) or not usable, e.g. DISABLED or
    DESTROYED (400 FAILED_PRECONDITION). Verifiers evict such a kid; signers still fail closed.
    """


class KmsClient(Protocol):
    def asymmetric_sign(self, *, name: str, digest_sha256: bytes) -> bytes:
        """DER-encoded ECDSA signature over `digest_sha256` by key version `name`."""
        ...

    def get_public_key(self, *, name: str) -> tuple[str, str]:
        """(PEM, algorithm) of key version `name`."""
        ...


def crc32c(data: bytes) -> int:
    import google_crc32c

    return int(google_crc32c.value(data))


def run_with_deadline(fn: Any, timeout: float) -> Any:
    """Runs `fn()` in the bounded pool; raises `KmsUnavailableError` after `timeout` seconds."""
    future = _EXECUTOR.submit(fn)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        raise KmsUnavailableError(
            f"E_KMS_TIMEOUT: no KMS response within {timeout}s"
        ) from exc
    except KmsUnavailableError:
        raise
    except Exception as exc:  # transport, auth, JSON: all availability errors
        raise KmsUnavailableError(
            f"E_KMS_UNAVAILABLE: {type(exc).__name__}"
        ) from exc


class KmsRestClient:
    """`KmsClient` over REST with the serving identity's Application Default Credentials."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_KMS_TIMEOUT_SECONDS,
        mtls: bool | None = None,
        session_factory: Any | None = None,
    ) -> None:
        """`mtls=None` follows `mtls_enabled()`. With mTLS, calls go to the KMS mTLS endpoint
        through a google-auth `AuthorizedSession` whose channel presents the workload certificate
        (`configure_mtls_channel`), as the agent-identity spike confirmed works.
        """
        self._timeout = timeout
        self._creds: Any = None
        self._lock = threading.Lock()
        self._mtls = mtls_enabled() if mtls is None else mtls
        self._session_factory = session_factory
        self._session: Any = None
        self.api = KMS_MTLS_API if self._mtls else KMS_API

    def _mtls_session(self) -> Any:
        with self._lock:
            if self._session is None:
                if os.getenv(CERTIFICATE_CONFIG_ENV):
                    os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "true"
                if self._session_factory is not None:
                    session = self._session_factory()
                else:
                    import google.auth
                    import google.auth.transport.requests

                    creds, _ = google.auth.default(
                        scopes=[
                            "https://www.googleapis.com/auth/cloud-platform"
                        ]
                    )
                    session = google.auth.transport.requests.AuthorizedSession(
                        creds
                    )
                    session.configure_mtls_channel()
                if not getattr(session, "is_mtls", False):
                    # Never fall back to a plain channel: cert-bound tokens would be refused, and
                    # a silent downgrade must not go unnoticed.
                    raise KmsUnavailableError(
                        "E_KMS_MTLS_UNAVAILABLE: no workload certificate"
                    )
                self._session = session
            return self._session

    def _auth_header(self) -> dict[str, str]:
        import google.auth
        import google.auth.transport.requests

        with self._lock:
            if self._creds is None:
                self._creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
            if not self._creds.valid:
                request = functools.partial(
                    google.auth.transport.requests.Request(),
                    timeout=self._timeout,
                )
                self._creds.refresh(request)
            headers = {"Authorization": f"Bearer {self._creds.token}"}
            quota_project = getattr(self._creds, "quota_project_id", None)
            if quota_project:
                headers["x-goog-user-project"] = str(quota_project)
            return headers

    def _call(
        self, method: str, url: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        import httpx

        # Callers (`KmsContextSigner`, `KmsPublicKeySource`) wrap this in `run_with_deadline`.
        if self._mtls:
            resp = self._mtls_session().request(
                method, url, json=body, timeout=self._timeout
            )
        else:
            resp = httpx.request(
                method,
                url,
                headers=self._auth_header(),
                json=body,
                timeout=self._timeout,
            )
        if resp.status_code in (400, 404):
            raise KmsKeyRejectedError(
                f"E_KMS_HTTP_{resp.status_code}", status=resp.status_code
            )
        if resp.status_code != 200:
            raise KmsUnavailableError(
                f"E_KMS_HTTP_{resp.status_code}", status=resp.status_code
            )
        return dict(resp.json())

    def asymmetric_sign(self, *, name: str, digest_sha256: bytes) -> bytes:
        body = {
            "digest": {
                "sha256": base64.b64encode(digest_sha256).decode("ascii")
            },
            "digestCrc32c": str(crc32c(digest_sha256)),
        }
        data = self._call("POST", f"{self.api}/{name}:asymmetricSign", body)
        if (
            data.get("name") != name
            or data.get("verifiedDigestCrc32c") is not True
        ):
            raise KmsUnavailableError(
                "E_KMS_INTEGRITY: request was corrupted in transit"
            )
        signature = base64.b64decode(data.get("signature", ""))
        if int(data.get("signatureCrc32c", -1)) != crc32c(signature):
            raise KmsUnavailableError(
                "E_KMS_INTEGRITY: signature was corrupted in transit"
            )
        return signature

    def get_public_key(self, *, name: str) -> tuple[str, str]:
        data = self._call("GET", f"{self.api}/{name}/publicKey")
        pem = str(data.get("pem", ""))
        if data.get("name") != name or int(data.get("pemCrc32c", -1)) != crc32c(
            pem.encode()
        ):
            raise KmsUnavailableError(
                "E_KMS_INTEGRITY: public key was corrupted in transit"
            )
        return pem, str(data.get("algorithm", ""))
