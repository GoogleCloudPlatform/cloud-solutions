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

# pylint: disable=import-outside-toplevel,line-too-long,wrong-import-position

"""Operator tool: write platform-wide (GLOBAL) memory. Agents and tenants cannot write GLOBAL.

GLOBAL memory is read by every tenant, so it must contain **no tenant data**: shared ontology,
glossary terms, generic runbook heuristics. It is sealed with the platform KMS key
(`cymbal-platform-global`). Only curators hold *encrypt* on that key; the serving identity can
only decrypt, so it cannot forge GLOBAL entries (IAM is the enforcing control, see Terraform).

Safeguards:
- **Two names on record (audit, not enforcement):** `--operator` and `--approved-by` (must
  differ) are stored with the record, with the SHA-256 of the exact content. They are
  self-asserted and stored outside the AAD, so treat them as advisory; who can write at all is
  decided by the Encrypter grant on the platform key.
- **Reviewed content only:** `--dry-run` prints the content and its SHA-256; `--confirm` must be
  given that hash (`--sha256`) and refuses if the content changed.
- **No silent overwrite:** an existing entry for the same actor needs `--replace`.
- **Live mode only:** a non-live write would be sealed with a throwaway local key.
- **Tenant-name filter (best effort; the human review is the real control):** refuses content
  mentioning a configured tenant ID, display name, or a distinctive part of either, after
  Unicode NFKC, removal of invisible characters, folding of common Cyrillic/Greek look-alikes,
  case folding, and ignoring separators. Tenants come from the platform config for
  `CYMBAL_ENV`, so run this with the same environment as the deployment.

Usage:
    uv run python scripts/curate_global_memory.py --actor glossary --json-file entry.json --dry-run
    CYMBAL_LIVE_GCP=1 uv run python scripts/curate_global_memory.py --actor glossary \\
        --json-file entry.json --confirm --sha256 <from dry run> \\
        --operator you@example.com --approved-by reviewer@example.com
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agents.context import TENANT_DIRECTORY
from agents.memory_crypto import OperatorPrincipal
from agents.platform_config import get_platform_config, is_live_mode

_INVISIBLE = re.compile(
    r"[\u00ad\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]"
)
_NON_ALNUM = re.compile(r"[^0-9a-z]+")
# Common Cyrillic / Greek look-alikes of Latin letters (NFKC does not fold these).
_CONFUSABLES = str.maketrans(
    {
        "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i",  # noqa: RUF001
        "ј": "j", "ѕ": "s", "ԁ": "d", "ӏ": "l", "к": "k", "м": "m", "т": "t", "в": "b",  # noqa: RUF001
        "н": "h", "α": "a", "ο": "o", "ρ": "p", "ε": "e", "ι": "i", "κ": "k", "ν": "v",  # noqa: RUF001
        "τ": "t", "υ": "u", "χ": "x", "ꜰ": "f", "ɪ": "i", "ʟ": "l", "ɴ": "n", "ᴀ": "a",  # noqa: RUF001
    }
)  # fmt: skip
# Words too generic to identify a tenant on their own.
_GENERIC = {
    "tenant", "alpha", "beta", "gamma", "delta", "corp", "corporation", "inc", "llc", "ltd",
    "bank", "group", "the", "and", "company", "global", "prod", "test",
}  # fmt: skip
_MIN_TOKEN = 4


def _fold(text: str) -> str:
    """NFKC, drop invisible characters, strip accents (NFKD + combining marks), case- and
    look-alike-fold."""
    nfkc = _INVISIBLE.sub("", unicodedata.normalize("NFKC", text))
    no_marks = "".join(
        c
        for c in unicodedata.normalize("NFKD", nfkc)
        if not unicodedata.combining(c)
    )
    return no_marks.casefold().translate(_CONFUSABLES)


def _words(text: str) -> list[str]:
    return [w for w in _NON_ALNUM.split(_fold(text)) if w]


def _known_tenants() -> dict[str, str]:
    """tenant_id -> display name, from the platform config (plus this process's directory)."""
    names = {t.tenant_id: t.display_name for t in get_platform_config().tenants}
    for tenant_id, meta in TENANT_DIRECTORY.items():
        names.setdefault(tenant_id, str(meta.get("display_name", "")))
    return names


def tenant_markers(tenants: dict[str, str] | None = None) -> set[str]:
    """Separator-free strings that identify a tenant: full ID, full name, distinctive words."""
    markers: set[str] = set()
    for tenant_id, display in (
        tenants if tenants is not None else _known_tenants()
    ).items():
        for source in (tenant_id, display):
            words = _words(source)
            if not words:
                continue
            markers.add("".join(words))
            markers |= {
                w for w in words if len(w) >= _MIN_TOKEN and w not in _GENERIC
            }
    return markers


def tenant_mentions(
    content: dict[str, object], tenants: dict[str, str] | None = None
) -> list[str]:
    """Tenant markers found in `content`, ignoring case, separators, and look-alike letters."""
    squashed = "".join(_words(json.dumps(content, ensure_ascii=False)))
    return sorted(m for m in tenant_markers(tenants) if m in squashed)


def content_sha256(content: dict[str, object]) -> str:
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").splitlines()[0]
    )
    parser.add_argument(
        "--actor", required=True, help="logical author, e.g. 'glossary'"
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--json", help="inline JSON object")
    src.add_argument("--json-file", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and show, write nothing",
    )
    mode.add_argument(
        "--confirm", action="store_true", help="write after human review"
    )
    parser.add_argument(
        "--sha256",
        help="content hash printed by --dry-run (required to confirm)",
    )
    parser.add_argument(
        "--operator", help="who is writing (required to confirm)"
    )
    parser.add_argument(
        "--approved-by", help="a different person who reviewed the dry run"
    )
    parser.add_argument(
        "--replace", action="store_true", help="overwrite an existing entry"
    )
    args = parser.parse_args(argv)

    content = json.loads(
        args.json if args.json else args.json_file.read_text(encoding="utf-8")
    )
    if not isinstance(content, dict):
        raise SystemExit("[REFUSED] content must be a JSON object")
    if leaked := tenant_mentions(content):
        raise SystemExit(
            f"[REFUSED] GLOBAL memory must not mention tenants: {leaked}"
        )
    digest = content_sha256(content)

    if args.dry_run:
        print(
            f"[DRY RUN] GLOBAL memory for actor '{args.actor}' (review before --confirm):"
        )
        print(json.dumps(content, indent=2, ensure_ascii=False))
        print(f"[DRY RUN] sha256={digest}")
        return 0

    if args.sha256 != digest:
        raise SystemExit(
            "[REFUSED] --sha256 must match the reviewed dry run (content changed?)."
        )
    if not args.operator or not args.approved_by:
        raise SystemExit(
            "[REFUSED] --operator and --approved-by are required to confirm."
        )
    operator = OperatorPrincipal(
        operator=args.operator, approved_by=args.approved_by
    )
    if not is_live_mode():
        raise SystemExit(
            "[REFUSED] GLOBAL curation requires live KMS (set CYMBAL_LIVE_GCP=1)."
        )

    from agents.gcp_live_bridge import LiveFirestoreMemoryBank

    key = LiveFirestoreMemoryBank().write_global(
        operator=operator,
        actor=args.actor,
        content=content,
        replace=args.replace,
    )
    print(f"[OK] wrote GLOBAL memory {key} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
