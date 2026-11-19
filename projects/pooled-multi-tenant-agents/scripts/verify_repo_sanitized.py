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

"""Repository sanitization scanner.

Scope, both modes: the text content of files tracked by git in the working tree (`git ls-files`),
except this script. It does NOT scan git history, untracked files, binary files, file names, or
anything hosted on GitHub (pull requests, issues, review comments, releases, Actions logs).

Default mode (what CI runs on every change) fails on exactly these classes:

- Internal Buganizer ID: `b/` followed by six or more digits.
- Internal Critique CL: `cl/` followed by six or more digits.
- Internal corporate URL: the corp subdomain of the Google domain.
- Internal googleplex URL.
- Internal uplink proxy URL.
- Internal artifact registry name.
- Private RSA/EC key header (PEM `BEGIN ... PRIVATE KEY`).
- Internal workstation home path.
- Internal workstation hostname (the cloud workstation host domain).
- Internal leveling jargon (L7/L8 followed by a title).
- Internal pre-GA codename.
- Non-inclusive terminology (the allowlist antonym and the tool-list field named after it).

Default mode does NOT check internal shortlinks, internal document links, cloud project or
organization identifiers, third-party tenant identifiers or employee names. A passing default run
therefore does not mean the tree is fit to publish.

Public-export mode (`--public-export`) is the gate for a tree that is about to be published. It
runs the default checks plus:

- Internal shortlink (`go/<name>`).
- Internal document link (Docs / Drive / Slides / Sheets on the Google domain).
- Internal sandbox domain (altostrat).
- Corporate email address (`@google.com`).
- Internal infrastructure term (the internal sandbox-organization and cloud-workstation names).
- Every literal listed in the export denylist, by class: `project_id`, `project_number`, `org_id`,
  `resource_id`, `third_party_tenant`, `employee`.
- The export denylist file itself, if it is tracked inside the scanned tree.

The denylist holds the real identifiers and names, so it must never be published: pass it from
outside the export tree with `--denylist PATH`. Without a readable denylist public-export mode exits
2 instead of reporting a pass it cannot back.

Exit status: 0 = no findings, 1 = findings, 2 = public-export mode could not run.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

SELF_PATH = "scripts/verify_repo_sanitized.py"
DEFAULT_DENYLIST_PATH = "scripts/public_export_denylist.txt"
DENYLIST_CLASSES = (
    "project_id",
    "project_number",
    "org_id",
    "resource_id",
    "third_party_tenant",
    "employee",
)

Pattern = tuple[str, re.Pattern[str]]

DEFAULT_PATTERNS: tuple[Pattern, ...] = (
    ("Internal Buganizer ID", re.compile(r"\bb/\d{6,}\b")),
    ("Internal Critique CL", re.compile(r"\bcl/\d{6,}\b")),
    (
        "Internal corporate URL",
        re.compile(r"corp\.google" + r"\.com", re.IGNORECASE),
    ),
    (
        "Internal googleplex URL",
        re.compile(r"googleplex" + r"\.com", re.IGNORECASE),
    ),
    (
        "Internal uplink proxy URL",
        re.compile(r"uplink" + r"\.goog", re.IGNORECASE),
    ),
    (
        "Internal artifact registry name",
        re.compile(r"artifact" + r"-foundry", re.IGNORECASE),
    ),
    (
        "Private RSA/EC key header",
        re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
    ),
    (
        "Internal workstation home path",
        re.compile(r"/usr/local/" + r"google/home/"),
    ),
    (
        "Internal workstation hostname",
        re.compile(r"\.c\." + r"googlers\.com", re.IGNORECASE),
    ),
    (
        "Internal leveling jargon",
        re.compile(
            r"\bL[78]\s+(?:Principal|Architect|Staff|Distinguished)\b",
            re.IGNORECASE,
        ),
    ),
    ("Internal pre-GA codename", re.compile(r"\b" + r"sobi\b", re.IGNORECASE)),
    (
        "Non-inclusive terminology",
        re.compile(
            r"\b" + r"white" + r"list(?:ed|s|ing)?(?:_tools)?\b", re.IGNORECASE
        ),
    ),
)

PUBLIC_EXPORT_PATTERNS: tuple[Pattern, ...] = (
    # `go/<name>` not preceded by a path or word character (so `cargo/x` and `a/go/b` pass).
    (
        "Internal shortlink",
        re.compile(r"(?<![\w./-])go/[a-z0-9][a-z0-9_-]*", re.IGNORECASE),
    ),
    (
        "Internal document link",
        re.compile(
            r"https?://(?:docs|drive|slides|sheets)\.google\.com/",
            re.IGNORECASE,
        ),
    ),
    (
        "Internal sandbox domain",
        re.compile(r"alto" + r"st" + r"rat\.com", re.IGNORECASE),
    ),
    (
        "Corporate email address",
        re.compile(r"[A-Za-z0-9._%+-]+@google\.com\b", re.IGNORECASE),
    ),
    (
        "Internal infrastructure term",
        re.compile(r"\b(?:argo" + r"lis|cloud" + r"top)\b", re.IGNORECASE),
    ),
)

DENYLIST_FILE_LABEL = "Export denylist file tracked in the tree"


class DenylistError(RuntimeError):
    """The export denylist is missing, unreadable or malformed."""


def load_denylist(path: Path) -> tuple[Pattern, ...]:
    """Parses `class: literal` lines (`#` comments and blank lines ignored) into patterns.

    Literals match case-insensitively and only as whole tokens (no letter or digit on either side).
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DenylistError(
            f"cannot read export denylist {path}: {exc}"
        ) from exc
    patterns: list[Pattern] = []
    for line_no, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        cls, sep, literal = line.partition(":")
        cls, literal = cls.strip(), literal.strip()
        if not sep or cls not in DENYLIST_CLASSES or not literal:
            raise DenylistError(
                f"{path}:{line_no}: expected '<class>: <literal>' with class in "
                f"{', '.join(DENYLIST_CLASSES)}"
            )
        patterns.append(
            (
                f"Denylisted {cls}",
                re.compile(
                    rf"(?<![A-Za-z0-9]){re.escape(literal)}(?![A-Za-z0-9])",
                    re.IGNORECASE,
                ),
            )
        )
    if not patterns:
        raise DenylistError(f"export denylist {path} has no entries")
    return tuple(patterns)


def tracked_files(repo_root: Path) -> list[str]:
    out = subprocess.check_output(
        ["git", "-C", str(repo_root), "ls-files"], text=True
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def scan_tracked_files(
    repo_root: Path,
    patterns: tuple[Pattern, ...] = DEFAULT_PATTERNS,
    *,
    skip: frozenset[str] = frozenset(),
) -> list[str]:
    """`<path>: <label> -> '<match>'` for every match of `patterns` in the tracked text files."""
    violations: list[str] = []
    for rel_path in tracked_files(repo_root):
        if (
            rel_path == SELF_PATH
            or rel_path.endswith(f"/{SELF_PATH}")
            or rel_path in skip
        ):
            continue
        full_path = repo_root / rel_path
        if not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in patterns:
            for match in pattern.finditer(content):
                violations.append(f"{rel_path}: {label} -> '{match.group(0)}'")
    return violations


def scan_public_export(repo_root: Path, denylist_path: Path) -> list[str]:
    """Default + public-export checks + denylist literals, for a tree about to be published."""
    denylist = load_denylist(denylist_path)
    violations: list[str] = []
    skip: set[str] = set()
    try:
        rel_denylist = (
            denylist_path.resolve().relative_to(repo_root.resolve()).as_posix()
        )
    except ValueError:
        rel_denylist = None
    if rel_denylist is not None and rel_denylist in tracked_files(repo_root):
        skip.add(rel_denylist)
        violations.append(
            f"{rel_denylist}: {DENYLIST_FILE_LABEL} -> exclude it from the export and pass it "
            "with --denylist"
        )
    violations += scan_tracked_files(
        repo_root,
        DEFAULT_PATTERNS + PUBLIC_EXPORT_PATTERNS + denylist,
        skip=frozenset(skip),
    )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n\n", maxsplit=1)[0]
    )
    parser.add_argument(
        "--public-export",
        action="store_true",
        help="Run the publish gate: default checks + shortlinks, doc links, identifiers, names.",
    )
    parser.add_argument(
        "--denylist",
        default="",
        help=f"Export denylist for --public-export (default: {DEFAULT_DENYLIST_PATH} in the repo).",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Repository to scan (default: the repository containing this script).",
    )
    args = parser.parse_args(argv)
    root = Path(args.repo_root)

    if args.public_export:
        denylist_path = (
            Path(args.denylist)
            if args.denylist
            else root / DEFAULT_DENYLIST_PATH
        )
        try:
            issues = scan_public_export(root, denylist_path)
        except DenylistError as exc:
            print(f"[SANITIZATION NOT RUN] {exc}", file=sys.stderr)
            return 2
        mode = "Public-export sanitization check"
    else:
        issues = scan_tracked_files(root)
        mode = "Sanitization check"

    if issues:
        for item in issues:
            print(f"[SANITIZATION FAILURE] {item}", file=sys.stderr)
        by_class = Counter(
            item.split(": ", 1)[1].split(" -> ", 1)[0] for item in issues
        )
        files = {item.split(": ", 1)[0] for item in issues}
        print(
            f"{mode} FAILED: {len(issues)} findings in {len(files)} files.",
            file=sys.stderr,
        )
        for label, count in sorted(by_class.items()):
            print(f"  {count:5d}  {label}", file=sys.stderr)
        return 1
    if args.public_export:
        print(
            f"{mode} passed: 0 findings in git-tracked files (tree only, not history)."
        )
    else:
        print(
            f"Default sanitization checks passed ({len(DEFAULT_PATTERNS)} pattern classes, "
            "git-tracked files only). This is not the publish gate: identifiers, names and "
            "internal links are checked only by --public-export."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
