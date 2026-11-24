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

"""Local-default hardening: the sanitizer says what it checks, and docker-compose is loopback-only.

- `scripts/verify_repo_sanitized.py`: the default mode's documented checks match its patterns and
  it passes on this repository; `--public-export` catches each class it documents (shortlinks,
  document links, sandbox domain, corporate email, denylisted identifiers and names), refuses to
  run without a denylist, and flags a denylist that is tracked inside the tree.
- `docker-compose.yml`: ports are published on 127.0.0.1 only and no password is committed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml
from scripts import verify_repo_sanitized as sanitizer

REPO = Path(__file__).resolve().parents[2]

# Built from pieces so this file never trips the public-export gate itself.
SHORTLINK = "g" + "o/" + "some-internal-page"
DOC_LINK = "https://docs." + "google.com/" + "document/d/abc"
SANDBOX_DOMAIN = "admin@someone.alto" + "st" + "rat.com"
CORP_EMAIL = "someone@" + "google.com"
WORKSTATION_HOST = "http://myhost1.c." + "googlers.com:8080"
INFRA_TERMS = ("Argo" + "lis", "cloud" + "top")
FAKE_DENYLIST = (
    "# comment\n"
    "project_id: acme-real-project\n"
    "project_number: 123456789012\n"
    "org_id: 987654321098\n"
    "resource_id: 5555555555555555555\n"
    "third_party_tenant: 11111111-2222-3333-4444-555555555555\n"
    "employee: jdoe\n"
    "private_repository: acme-private-org\n"
)


def _git_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    return repo


def _labels(violations: list[str]) -> set[str]:
    return {v.split(": ", 1)[1].split(" -> ", 1)[0] for v in violations}


def test_default_mode_passes_on_this_repository(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert sanitizer.scan_tracked_files(REPO) == []
    assert sanitizer.main([]) == 0
    out = capsys.readouterr().out
    assert "Default sanitization checks passed" in out
    assert "not the publish gate" in out
    # The pass message must not claim more than the default mode checks.
    assert "0 internal references" not in out
    assert "secrets found" not in out


def test_docstring_lists_every_check_and_no_default_claim_it_does_not_make() -> (
    None
):
    doc = sanitizer.__doc__ or ""
    default_part, sep, export_part = doc.partition("Public-export mode")
    assert sep
    for label, _ in sanitizer.DEFAULT_PATTERNS:
        assert label.lower() in default_part.lower(), label
    for label, _ in sanitizer.PUBLIC_EXPORT_PATTERNS:
        assert label.lower() in export_part.lower(), label
    for cls in sanitizer.DENYLIST_CLASSES:
        assert f"`{cls}`" in export_part
    # The default mode documents that it does not check these (it used to claim shortlinks).
    assert "does NOT check internal shortlinks" in default_part
    assert "does NOT scan git history" in default_part


def test_default_mode_does_not_flag_what_only_the_export_gate_checks(
    tmp_path: Path,
) -> None:
    repo = _git_repo(
        tmp_path,
        {
            "notes.md": "\n".join(
                [
                    SHORTLINK,
                    DOC_LINK,
                    SANDBOX_DOMAIN,
                    CORP_EMAIL,
                    "acme-real-project",
                    "",
                ]
            )
        },
    )
    assert sanitizer.scan_tracked_files(repo) == []


def test_public_export_mode_catches_each_documented_class(
    tmp_path: Path,
) -> None:
    denylist = tmp_path / "denylist.txt"
    denylist.write_text(FAKE_DENYLIST, encoding="utf-8")
    samples = {
        "Internal shortlink": f"see {SHORTLINK} for details",
        "Internal document link": f"deck: {DOC_LINK}",
        "Internal sandbox domain": f"user:{SANDBOX_DOMAIN}",
        "Corporate email address": f"owner {CORP_EMAIL}",
        "Denylisted project_id": 'project = "ACME-real-project"',
        "Denylisted project_number": "projects/123456789012/locations/us-central1",
        "Denylisted org_id": "agents.global.org-987654321098.system.id.goog",
        "Denylisted resource_id": "reasoningEngines/5555555555555555555",
        "Denylisted third_party_tenant": "tid=11111111-2222-3333-4444-555555555555",
        "Denylisted employee": "reviewed by jdoe on Tuesday",
        "Denylisted private_repository": "https://github.com/acme-private-org/repo/pull/7",
        "Internal Buganizer ID": "tracked in b/" + "123456789",
        "Internal workstation hostname": f"open {WORKSTATION_HOST}",
        "Internal infrastructure term": f"use {INFRA_TERMS[0]} ADC, not {INFRA_TERMS[1]} certs",
    }
    repo = _git_repo(
        tmp_path, {f"f{i}.txt": text for i, text in enumerate(samples.values())}
    )
    found = _labels(sanitizer.scan_public_export(repo, denylist))
    assert found == set(samples)
    assert (
        sanitizer.main(
            [
                "--public-export",
                "--repo-root",
                str(repo),
                "--denylist",
                str(denylist),
            ]
        )
        == 1
    )


def test_public_export_mode_matches_whole_tokens_only(tmp_path: Path) -> None:
    denylist = tmp_path / "denylist.txt"
    denylist.write_text(FAKE_DENYLIST, encoding="utf-8")
    repo = _git_repo(
        tmp_path,
        {
            "ok.txt": (
                "jdoesnt 1234567890123 acme-real-projects cargo/build third_party/go/gc "
                "https://github.com/google/adk-python user@example.com\n"
            )
        },
    )
    assert sanitizer.scan_public_export(repo, denylist) == []
    assert (
        sanitizer.main(
            [
                "--public-export",
                "--repo-root",
                str(repo),
                "--denylist",
                str(denylist),
            ]
        )
        == 0
    )


def test_public_export_mode_refuses_to_run_without_a_usable_denylist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _git_repo(tmp_path, {"clean.txt": "nothing to see\n"})
    assert sanitizer.main(["--public-export", "--repo-root", str(repo)]) == 2
    assert "SANITIZATION NOT RUN" in capsys.readouterr().err
    for bad in (
        "",
        "# only a comment\n",
        "nonsense line\n",
        "unknown_class: x\n",
        "employee:\n",
    ):
        bad_file = tmp_path / "bad.txt"
        bad_file.write_text(bad, encoding="utf-8")
        with pytest.raises(sanitizer.DenylistError):
            sanitizer.load_denylist(bad_file)


def test_public_export_mode_flags_a_denylist_tracked_in_the_tree(
    tmp_path: Path,
) -> None:
    repo = _git_repo(
        tmp_path,
        {
            "clean.txt": "nothing to see\n",
            sanitizer.DEFAULT_DENYLIST_PATH: FAKE_DENYLIST,
        },
    )
    violations = sanitizer.scan_public_export(
        repo, repo / sanitizer.DEFAULT_DENYLIST_PATH
    )
    assert _labels(violations) == {sanitizer.DENYLIST_FILE_LABEL}


def test_repository_denylist_parses_and_stays_out_of_the_container_image() -> (
    None
):
    if not (REPO / sanitizer.DEFAULT_DENYLIST_PATH).is_file():
        pytest.skip("Export denylist is excluded from public exports.")
    patterns = sanitizer.load_denylist(REPO / sanitizer.DEFAULT_DENYLIST_PATH)
    assert {label.removeprefix("Denylisted ") for label, _ in patterns} == set(
        sanitizer.DENYLIST_CLASSES
    )
    for ignore_file in (".dockerignore", ".gcloudignore"):
        assert (
            sanitizer.DEFAULT_DENYLIST_PATH
            in (REPO / ignore_file).read_text().splitlines()
        )


def test_docker_compose_publishes_loopback_only_and_commits_no_password() -> (
    None
):
    text = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    compose = yaml.safe_load(text)
    assert set(compose["services"]) == {"postgres-rls", "redis-bulkhead"}
    for name, service in compose["services"].items():
        assert service["ports"], name
        for port in service["ports"]:
            assert str(port).startswith(
                "127.0.0.1:"
            ), f"{name} publishes {port} beyond loopback"
    pg_env = compose["services"]["postgres-rls"]["environment"]
    assert re.fullmatch(
        r"\$\{POSTGRES_PASSWORD:\?[^}]+\}", pg_env["POSTGRES_PASSWORD"]
    )
    redis = compose["services"]["redis-bulkhead"]
    assert re.fullmatch(
        r"\$\{REDIS_PASSWORD:\?[^}]+\}", redis["environment"]["REDIS_PASSWORD"]
    )
    assert "--requirepass" in " ".join(redis["command"])
    # No literal credential anywhere in the file: every *PASSWORD value is a required variable.
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = re.match(r"\s*\w*PASSWORD\w*:\s*(.+)$", line)
        if m:
            assert m.group(1).startswith("${"), line


def test_postgres_init_script_has_no_built_in_superuser_dsn() -> None:
    source = (REPO / "scripts" / "init_postgres_rls.py").read_text(
        encoding="utf-8"
    )
    main_block = source.split('if __name__ == "__main__":', 1)[1]
    assert 'os.getenv("DATABASE_URL", "")' in main_block
    assert "raise SystemExit(" in main_block
    assert not re.search(r"postgresql://\w+:[^$@\s]+@", main_block)


def test_workstation_hostname_fails_the_default_mode_but_infra_terms_do_not(
    tmp_path: Path,
) -> None:
    repo = _git_repo(
        tmp_path,
        {
            "host.md": f"{WORKSTATION_HOST}\n",
            "terms.md": " ".join(INFRA_TERMS) + "\n",
        },
    )
    assert _labels(sanitizer.scan_tracked_files(repo)) == {
        "Internal workstation hostname"
    }


def test_repository_denylist_covers_concatenated_usernames_and_record_ids() -> (
    None
):
    """Whole-token matching means a username that merely contains a listed name needs its own
    line; so do record and request IDs returned by the real third-party tenants.
    """
    if not (REPO / sanitizer.DEFAULT_DENYLIST_PATH).is_file():
        pytest.skip("Export denylist is excluded from public exports.")
    entries = [
        line.partition(":")[2].strip()
        for line in (REPO / sanitizer.DEFAULT_DENYLIST_PATH)
        .read_text()
        .splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(entries) == len(
        {e.lower() for e in entries}
    ), "duplicate denylist entries"
    by_class = {
        cls: sum(
            1
            for label, _ in sanitizer.load_denylist(
                REPO / sanitizer.DEFAULT_DENYLIST_PATH
            )
            if label == f"Denylisted {cls}"
        )
        for cls in sanitizer.DENYLIST_CLASSES
    }
    assert by_class["employee"] >= 25
    assert by_class["private_repository"] >= 2
    assert by_class["third_party_tenant"] >= 10
    assert by_class["resource_id"] >= 5
