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

# pylint: disable=line-too-long,use-implicit-booleaness-not-comparison

"""Context-key prewarm on Cloud Run (CPU throttled outside requests).

- A startup prewarm timeout is a WARNING (not an error/alert) saying verification fetches on
  demand, and it does not use up the kid's refetch budget: the first request fetches immediately.
- `ContextKeyWarmer` retries opportunistically on requests, at most one background attempt per
  interval, logs only the first failure at WARNING, and stops once warm.
- Fail-closed is unchanged: with KMS still down, verification raises ContextKeyUnavailableError.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from agents import context_token as ct
from agents import kms_rest
from app import main
from fastapi.testclient import TestClient
from tests.helpers.context_token_fakes import KEY, FakeKms, _real_kms_token


def _verifier(fake: FakeKms) -> ct.ContextTokenVerifier:
    return ct.ContextTokenVerifier(
        ct.KmsPublicKeySource(KEY, configured_version=1, client=fake)
    )


def test_prewarm_timeout_is_a_warning_and_leaves_the_budget_to_on_demand_fetch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = FakeKms()
    token = _real_kms_token(fake)
    fake.public_key_fail = kms_rest.KmsUnavailableError(
        "E_KMS_TIMEOUT: no KMS response"
    )
    verifier = _verifier(fake)
    with caplog.at_level(logging.DEBUG, logger="agents.context_token"):
        assert verifier.prewarm() is False
    records = [r for r in caplog.records if "prewarm" in r.getMessage()]
    assert records
    assert all(r.levelno == logging.WARNING for r in records)
    assert "fetch the key on demand" in records[0].getMessage()
    assert not verifier.is_warm()
    # Still fail-closed while KMS is down ...
    with pytest.raises(ct.ContextKeyUnavailableError):
        verifier.verify(token, audience="runtime")
    # ... and once it recovers, the next verification fetches at once (no rate-limit lockout).
    fake.public_key_fail = None
    verifier2 = _verifier(fake)
    fake.public_key_fail = kms_rest.KmsUnavailableError("E_KMS_TIMEOUT")
    verifier2.prewarm()
    fake.public_key_fail = None
    assert verifier2.verify(token, audience="runtime")["tenant_id"]
    assert verifier2.is_warm()


def test_disabled_key_at_prewarm_is_an_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = FakeKms()
    fake.disabled.add(f"{KEY}/cryptoKeyVersions/1")
    with caplog.at_level(logging.WARNING, logger="agents.context_token"):
        assert _verifier(fake).prewarm() is False
    assert any(
        r.levelno == logging.ERROR and "not usable" in r.getMessage()
        for r in caplog.records
    )


def test_warmer_retries_on_requests_without_blocking_or_log_spam(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake = FakeKms()
    fake.public_key_fail = kms_rest.KmsUnavailableError("E_KMS_TIMEOUT")
    verifier = _verifier(fake)
    now = [0.0]
    spawned: list[Any] = []
    warmer = ct.ContextKeyWarmer(
        lambda: verifier,
        min_interval_seconds=30,
        clock=lambda: now[0],
        spawn=spawned.append,
    )
    with caplog.at_level(logging.DEBUG, logger="agents.context_token"):
        warmer.kick()  # startup
        warmer.kick()  # in flight: no second attempt
        assert len(spawned) == 1
        spawned.pop()()  # run it: fails
        warmer.kick()  # within the interval: nothing
        assert spawned == []
        now[0] += 31
        for _ in range(5):
            warmer.kick()  # a burst of requests starts exactly one retry
        assert len(spawned) == 1
        spawned.pop()()  # fails again, quietly
        fake.public_key_fail = None
        now[0] += 31
        warmer.kick()
        spawned.pop()()  # succeeds
    assert warmer.warm
    assert warmer.attempts == 3
    warmer.kick()
    assert spawned == []  # warm: no more work, ever
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1  # only the first failure is a warning


def test_requests_kick_the_warmer(monkeypatch: pytest.MonkeyPatch) -> None:
    kicks: list[int] = []
    monkeypatch.setattr(
        main.CONTEXT_KEY_WARMER, "kick", lambda: kicks.append(1)
    )
    assert TestClient(main.app).get("/healthz").status_code == 200
    assert kicks == [1]
