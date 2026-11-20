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

# pylint: disable=broad-exception-caught,line-too-long,wrong-import-position

"""Pre-deploy check for the context-signing key (ADR-0014 B2).

Signs one digest with the configured KMS key version, fetches that version's public key, and
verifies the signature locally: the same two calls the gateway and its verifiers make. Run it as
the serving identity before deploying, e.g. with ADC impersonating the runtime SA:

    gcloud auth application-default login \
        --impersonate-service-account=cymbal-pooled-runtime-sa@<project>.iam.gserviceaccount.com
    CYMBAL_ENV=sandbox uv run python scripts/preflight_context_signing.py

Exit code 0 = ready. Otherwise prints which step failed and the likely cause (missing key or
version, disabled version, missing IAM, wrong algorithm, KMS unreachable).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import kms_rest
from agents.context_token import (
    load_p256_public_key_pem,
    resolve_context_signing_kms_key,
)
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

_CAUSES = {
    403: "the caller lacks roles/cloudkms.signerVerifier on this key (or the KMS API is disabled)",
    404: "the key ring, key or key version does not exist (check the name and location)",
    400: "the key version is not ENABLED (disabled, destroyed or pending), or the key is not an "
    "asymmetric-signing key",
}


def _explain(exc: BaseException) -> str:
    status = getattr(exc, "status", None) or getattr(
        exc.__cause__, "status", None
    )
    if status in _CAUSES:
        return f"HTTP {status}: {_CAUSES[status]}"
    if "TIMEOUT" in str(exc):
        return "KMS did not answer in time (network, VPC-SC or quota)"
    cause = exc.__cause__ or exc
    return f"{type(cause).__name__}: {cause}"


def preflight(
    key_version: str, *, client: Any | None = None, timeout: float = 10.0
) -> list[str]:
    """Problems found (empty = ready). Never raises for KMS errors."""
    client = client or kms_rest.KmsRestClient(timeout=timeout)
    digest = hashlib.sha256(b"cymbal-context-signing-preflight").digest()
    try:
        der = kms_rest.run_with_deadline(
            lambda: client.asymmetric_sign(
                name=key_version, digest_sha256=digest
            ),
            timeout,
        )
    except Exception as exc:
        return [f"asymmetricSign failed: {_explain(exc)}"]
    try:
        pem, algorithm = kms_rest.run_with_deadline(
            lambda: client.get_public_key(name=key_version), timeout
        )
    except Exception as exc:
        return [f"getPublicKey failed: {_explain(exc)}"]
    if algorithm != kms_rest.EC_SIGN_P256_SHA256:
        return [
            f"key algorithm is {algorithm!r}; ADR-0014 requires EC_SIGN_P256_SHA256"
        ]
    try:
        load_p256_public_key_pem(pem).verify(
            der, digest, ec.ECDSA(Prehashed(hashes.SHA256()))
        )
    except (ValueError, InvalidSignature) as exc:
        return [
            f"the KMS signature does not verify with the version's public key ({exc!r})"
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--key-version",
        help="Full cryptoKeyVersions resource (default: config)",
    )
    args = parser.parse_args(argv)
    key_version = args.key_version
    if not key_version:
        resolved = resolve_context_signing_kms_key()
        if resolved is None:
            print(
                "FAIL: no context-signing key configured (identity.context_signing_kms_key)"
            )
            return 1
        key_version = resolved[1]
    problems = preflight(key_version)
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        return 1
    print(f"OK: signed and verified with {key_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
