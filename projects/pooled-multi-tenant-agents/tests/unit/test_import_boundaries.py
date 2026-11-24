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

# pylint: disable=line-too-long

"""Architectural import-layering and neutral-naming enforcement tests."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PACKAGE_DIRS: tuple[str, ...] = (
    "agents",
    "app",
    "broker_service",
    "evals",
    "mcp_server",
    "runtime_service",
    "scripts",
)

FORBIDDEN_FILENAME_SUBSTRINGS: tuple[str, ...] = (
    "elephant-goldfish",
    "goldfish",
    "devils_advocate",
)


def _iter_python_files(rel_dir: str) -> list[Path]:
    base = REPO_ROOT / rel_dir
    result: list[Path] = sorted(base.glob("*.py"))
    for child in sorted(base.iterdir()):
        if child.is_dir() and child.name != "__pycache__":
            result.extend(sorted(child.glob("*.py")))
            for grandchild in sorted(child.iterdir()):
                if grandchild.is_dir() and grandchild.name != "__pycache__":
                    result.extend(sorted(grandchild.glob("*.py")))
    return result


def _imported_top_packages(py_path: Path) -> set[str]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    packages: set[str] = set()
    stack: list[ast.AST] = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Import):
            for alias in node.names:
                packages.add(alias.name.split(".", 1)[0])
        elif (
            isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
        ):
            packages.add(node.module.split(".", 1)[0])
        stack.extend(ast.iter_child_nodes(node))
    return packages


def _imported_full_modules(py_path: Path) -> set[str]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    modules: set[str] = set()
    stack: list[ast.AST] = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif (
            isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
        ):
            modules.add(node.module)
        stack.extend(ast.iter_child_nodes(node))
    return modules


def test_runtime_and_cli_packages_never_import_tests() -> None:
    """Production services, agents, evals, and CLI scripts must never import `tests.*`."""
    violations: list[str] = []
    for pkg in PACKAGE_DIRS:
        for py_path in _iter_python_files(pkg):
            if "tests" in _imported_top_packages(py_path):
                violations.append(str(py_path.relative_to(REPO_ROOT)))
    assert (
        not violations
    ), f"Runtime/CLI modules importing tests.*: {violations}"


def test_strict_service_plane_import_layering() -> None:
    """Enforces one-way dependency layering across `agents`, `mcp_server`, and `broker_service`."""
    forbidden_by_pkg: dict[str, set[str]] = {
        "agents": {"app", "tests"},
        "mcp_server": {"app", "runtime_service", "tests"},
        "broker_service": {"app", "mcp_server", "runtime_service", "tests"},
    }
    violations: list[str] = []
    for pkg, forbidden in forbidden_by_pkg.items():
        for py_path in _iter_python_files(pkg):
            bad = _imported_top_packages(py_path) & forbidden
            if bad:
                violations.append(
                    f"{py_path.relative_to(REPO_ROOT)} -> {sorted(bad)}"
                )
    assert (
        not violations
    ), f"Architectural import-boundary violations: {violations}"


def test_pytest_modules_do_not_import_peer_test_modules_or_conftest() -> None:
    """Shared test doubles belong in `tests/helpers/` or `agents/testing_fakes.py`, not
    `test_*.py`.
    """
    violations: list[str] = []
    for suite in ("unit", "security", "integration"):
        for py_path in sorted((REPO_ROOT / "tests" / suite).glob("test_*.py")):
            for mod in _imported_full_modules(py_path):
                if mod.endswith(".conftest") or mod == "conftest":
                    violations.append(
                        f"{py_path.relative_to(REPO_ROOT)} imports {mod}"
                    )
                if mod.startswith(
                    (
                        "tests.unit.test_",
                        "tests.security.test_",
                        "tests.integration.test_",
                    )
                ):
                    violations.append(
                        f"{py_path.relative_to(REPO_ROOT)} imports {mod}"
                    )
    assert not violations, f"Cross-test module imports detected: {violations}"


def test_repository_python_filenames_are_neutral() -> None:
    """No Python module or test filename may contain personal stakeholder or meta-prompt names."""
    all_py = [
        *[p for pkg in PACKAGE_DIRS for p in _iter_python_files(pkg)],
        *_iter_python_files("tests"),
    ]
    bad_files = [
        str(p.relative_to(REPO_ROOT))
        for p in all_py
        if any(tok in p.name.lower() for tok in FORBIDDEN_FILENAME_SUBSTRINGS)
    ]
    assert not bad_files, f"Non-neutral filenames found: {bad_files}"
