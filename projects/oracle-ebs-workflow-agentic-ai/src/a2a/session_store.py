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

"""Session store and conversation state management for A2A Gateway.

Maintains multi-turn conversation history, staged confirmation proposals,
and recent worklist triage items across stateless HTTP invocations.
"""

import re
import threading
import time
from collections.abc import Mapping
from typing import Any

CONFIRMATION_KEYWORDS = {
    "confirm",
    "confirmed",
    "confirmed=true",
    "confirm=true",
    "yes",
    "yes please",
    "proceed",
    "execute",
    "go ahead",
    "do it",
    "accept",
}

CONFIRMATION_REGEX = re.compile(
    r"^(?:(?:yes|please|i|ok|okay)\s*,?\s*)?"
    r"(?:confirm(?:ed)?(?:\s*=\s*true|\s+(?:approval|approve|reject|"
    r"rejection|action|it|them|all))?|"
    r"yes(?:\s+please)?|proceed|execute|go\s+ahead|do\s+it|accept)$",
    re.IGNORECASE,
)


def is_confirmation_prompt(text: str) -> bool:
    """Check if user prompt is an affirmative confirmation command."""
    clean = text.strip().strip("!.,?:;\"'`").strip().lower()
    if not clean:
        return False
    if clean in CONFIRMATION_KEYWORDS:
        return True
    return bool(CONFIRMATION_REGEX.match(clean))


class SessionData:
    """In-memory session state holding dialogue turns and staged actions."""

    def __init__(self, session_id: str) -> None:
        self.session_id: str = session_id
        now = time.time()
        self.created_at: float = now
        self.last_accessed: float = now
        self.pending_proposal: dict[str, Any] | None = None
        self.last_notification_ids: list[int] = []
        self.last_low_risk_ids: list[int] = []
        self.last_items_by_type: dict[str, list[int]] = {}
        self.last_recommendations: list[str] = []
        self.dialogue_turns: list[dict[str, str]] = []

    def touch(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = time.time()

    def has_context(self) -> bool:
        """Return True if session holds any active proposal or history."""
        return bool(
            self.pending_proposal
            or self.last_notification_ids
            or self.last_low_risk_ids
            or self.last_items_by_type
            or self.dialogue_turns
        )

    def add_turn(self, role: str, text: str) -> None:
        """Add dialogue turn and maintain rolling window of 10 turns."""
        self.touch()
        clean_text = text.strip()
        if not clean_text:
            return
        self.dialogue_turns.append({"role": role, "text": clean_text})
        if len(self.dialogue_turns) > 10:
            self.dialogue_turns = self.dialogue_turns[-10:]

    def get_formatted_turns(self, max_turns: int = 6) -> list[str]:
        """Return formatted conversation history turns for LLM prompt."""
        self.touch()
        selected = self.dialogue_turns[-max_turns:]
        lines: list[str] = []
        for turn in selected:
            role = turn["role"].capitalize()
            text = turn["text"]
            lines.append(f"{role}: {text}")
        return lines

    def set_pending_proposal(self, proposal: dict[str, Any]) -> None:
        """Stage pending proposal awaiting human confirmation."""
        self.touch()
        self.pending_proposal = proposal
        nids = proposal.get("notification_ids") or []
        if nids:
            self.last_notification_ids = [int(nid) for nid in nids]

    def clear_pending_proposal(self) -> dict[str, Any] | None:
        """Clear and return the staged pending proposal."""
        self.touch()
        prop = self.pending_proposal
        self.pending_proposal = None
        return prop

    def remove_completed_notifications(self, nids: list[int]) -> None:
        """Remove closed or processed notification IDs from session state."""
        if not nids:
            return
        self.touch()
        closed_set = {int(x) for x in nids}
        self.last_notification_ids = [
            nid for nid in self.last_notification_ids if nid not in closed_set
        ]
        self.last_low_risk_ids = [
            nid for nid in self.last_low_risk_ids if nid not in closed_set
        ]
        for m_type, type_nids in list(self.last_items_by_type.items()):
            self.last_items_by_type[m_type] = [
                nid for nid in type_nids if nid not in closed_set
            ]

    def set_triage_items(
        self,
        notification_ids: list[int],
        low_risk_ids: list[int] | None = None,
        items_by_type: dict[str, list[int]] | None = None,
        recommendations: list[str] | None = None,
    ) -> None:
        """Record recently triaged items for bulk confirmation binding."""
        self.touch()
        self.last_notification_ids = list(notification_ids)
        self.last_low_risk_ids = list(low_risk_ids or notification_ids)
        if items_by_type is not None:
            self.last_items_by_type = dict(items_by_type)
        if recommendations is not None:
            self.last_recommendations = list(recommendations)


class SessionStore:
    """Thread-safe multi-session manager with automatic TTL pruning."""

    def __init__(self, ttl_seconds: float = 1800.0) -> None:
        self._sessions: dict[str, SessionData] = {}
        self._lock = threading.Lock()
        self.ttl_seconds: float = ttl_seconds

    def get_or_create(self, session_id: str) -> SessionData:
        """Retrieve existing session or instantiate an isolated session."""
        clean_id = session_id.strip() or "default_session"
        with self._lock:
            self._cleanup_expired_locked()
            if clean_id not in self._sessions:
                self._sessions[clean_id] = SessionData(clean_id)
            else:
                self._sessions[clean_id].touch()
            return self._sessions[clean_id]

    def get(self, session_id: str) -> SessionData | None:
        """Retrieve existing session if present and active."""
        clean_id = session_id.strip() or "default_session"
        with self._lock:
            self._cleanup_expired_locked()
            session = self._sessions.get(clean_id)
            if session:
                session.touch()
            return session

    def bind_alias(self, alias_id: str, session: SessionData) -> None:
        """Bind an alias context/task ID to an existing SessionData object."""
        clean_alias = alias_id.strip()
        if not clean_alias:
            return
        with self._lock:
            self._cleanup_expired_locked()
            self._sessions[clean_alias] = session

    def get_latest_pending_proposal(self) -> dict[str, Any] | None:
        """Pop and return the most recent staged proposal across sessions."""
        with self._lock:
            self._cleanup_expired_locked()
            candidates = [
                s
                for s in self._sessions.values()
                if s.pending_proposal is not None
            ]
            if not candidates:
                return None
            latest = max(candidates, key=lambda s: s.last_accessed)
            return latest.clear_pending_proposal()

    def get_latest_active_session(self) -> SessionData | None:
        """Return the most recently accessed session holding active context."""
        with self._lock:
            self._cleanup_expired_locked()
            candidates = [s for s in self._sessions.values() if s.has_context()]
            if not candidates:
                return None
            return max(candidates, key=lambda s: s.last_accessed)

    def sync_completed_notifications(self, nids: list[int]) -> None:
        """Clear pending proposals and completed IDs across active sessions."""
        with self._lock:
            seen: set[int] = set()
            for session in self._sessions.values():
                if id(session) in seen:
                    continue
                seen.add(id(session))
                if session.pending_proposal is not None:
                    prop_nids = {
                        int(x)
                        for x in (
                            session.pending_proposal.get("notification_ids")
                            or []
                        )
                    }
                    if not nids or prop_nids.intersection(
                        {int(x) for x in nids}
                    ):
                        session.clear_pending_proposal()
                if nids:
                    session.remove_completed_notifications(nids)

    def clear(self, session_id: str) -> None:
        """Explicitly remove session."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def _cleanup_expired_locked(self) -> None:
        """Internal helper to prune sessions older than TTL."""
        now = time.time()
        expired = [
            sid
            for sid, s in self._sessions.items()
            if now - s.last_accessed > self.ttl_seconds
        ]
        for sid in expired:
            self._sessions.pop(sid, None)


_GLOBAL_SESSION_STORE = SessionStore()


def get_session_store() -> SessionStore:
    """Retrieve shared global session store singleton."""
    return _GLOBAL_SESSION_STORE


def extract_session_id(
    body: dict[str, Any],
    headers: Mapping[str, str] | None = None,
) -> str:
    """Extract session identifier across Gemini, A2A, and HTTP headers."""
    keys = (
        "session_id",
        "sessionId",
        "session",
        "context_id",
        "contextId",
        "conversation_id",
        "conversationId",
        "task_id",
        "taskId",
    )
    for container in (
        body,
        body.get("params") if isinstance(body.get("params"), dict) else {},
        (
            body["params"].get("message")
            if isinstance(body.get("params"), dict)
            and isinstance(body["params"].get("message"), dict)
            else {}
        ),
        body.get("message") if isinstance(body.get("message"), dict) else {},
    ):
        if isinstance(container, dict):
            for key in keys:
                val = container.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()

    if headers:
        for h_key in (
            "x-session-id",
            "x-conversation-id",
            "x-context-id",
            "session-id",
        ):
            val_h = headers.get(h_key)
            if isinstance(val_h, str) and val_h.strip():
                return val_h.strip()

    user_val = body.get("user_id") or body.get("recipient")
    if isinstance(user_val, str) and user_val.strip():
        return f"user:{user_val.strip()}"

    return "default_session"
