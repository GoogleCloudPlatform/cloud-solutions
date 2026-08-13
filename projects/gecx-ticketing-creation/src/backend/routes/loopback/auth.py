# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=line-too-long, broad-exception-caught
"""Module for loopback authentication endpoints."""

import hashlib
import hmac
import json
import os
import time

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

router = APIRouter()


def get_secret_key() -> str:
    """Helper to retrieve SECRET_KEY at runtime."""
    key = os.getenv("SECRET_KEY")
    if not key:
        raise RuntimeError("SECRET_KEY environment variable is missing!")
    return key


USERS_FILE = os.path.join("src", "backend", "data", "users.json")

# In-memory dictionary to track rate limiting failed attempts per account
# format: { account: { "count": int, "locked_until": float } }
failed_attempts = {}


class PINVerifyRequest(BaseModel):
    account: str = Field(..., description="User account identifier")
    pin: str = Field(..., description="4-digit security PIN")

    @field_validator("pin")
    @classmethod
    def validate_pin(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 4:
            raise ValueError("PIN must be exactly 4 digits")
        return v


def get_hash(val: str) -> str:
    return hashlib.sha256(val.encode()).hexdigest()


def sign_account(account: str) -> str:
    sig = hmac.new(
        get_secret_key().encode(), account.encode(), hashlib.sha256
    ).hexdigest()
    return f"{account}:{sig}"


def verify_signed_account(cookie_val: str) -> str | None:
    try:
        account, sig = cookie_val.split(":", 1)
        expected_sig = hmac.new(
            get_secret_key().encode(), account.encode(), hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(sig, expected_sig):
            return account
    except Exception:
        pass
    return None


@router.post("/auth/verify")
def verify_pin(payload: PINVerifyRequest, response: Response):
    account = payload.account
    pin = payload.pin
    now = time.time()

    # 1. Check Rate Limiting Lockout
    attempt_info = failed_attempts.get(account)
    if attempt_info and attempt_info["locked_until"] > now:
        time_left = int(attempt_info["locked_until"] - now)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Account locked for {time_left} seconds.",
        )

    # 2. Load users data
    if not os.path.exists(USERS_FILE):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User database not found.",
        )

    with open(USERS_FILE, "r", encoding="utf-8") as f:
        users = json.load(f)

    # 3. Check account existence
    if account not in users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid account or PIN.",
        )

    # 4. Validate PIN Hash
    input_hash = get_hash(pin)
    stored_hash = users[account]

    if input_hash == stored_hash:
        # Success: reset failed attempts
        if account in failed_attempts:
            del failed_attempts[account]

        # Set session cookie
        signed_cookie = sign_account(account)
        response.set_cookie(
            key="session",
            value=signed_cookie,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=3600,
        )
        return {"authenticated": True}
    else:
        # Failure: increment failed attempts
        if not attempt_info:
            failed_attempts[account] = {"count": 1, "locked_until": 0}
        else:
            failed_attempts[account]["count"] += 1
            if failed_attempts[account]["count"] >= 5:
                failed_attempts[account]["locked_until"] = now + 60
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed attempts. Account locked for 60 seconds.",
                )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid account or PIN.",
        )


@router.get("/auth/me")
def get_current_user(request: Request):
    # Retrieve user email injected by Google Cloud IAP
    iap_email = request.headers.get("x-goog-authenticated-user-email")
    if iap_email:
        # Google prefixes the email with "accounts.google.com:"
        email = iap_email.replace("accounts.google.com:", "")
        return {"email": email, "authenticated": True}

    # Fallback/Development mock user if running locally
    return {"email": "local-dev-admin@cymbal.com", "authenticated": False}
