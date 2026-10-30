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
"""Unit tests for GKE App Migration Execution Orchestrator."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from execute_migration import (
    PHASES,
    archive_existing_state,
    execute_phase_action,
    get_matching_manifest_docs,
    initialize_state,
    load_or_prompt_state,
    load_state,
    save_state,
    validate_handoff_files,
    validate_schema,
)


class TestExecuteMigrationState(unittest.TestCase):
    """Tests state management helper functions."""

    def test_initialize_state(self):
        state = initialize_state("test-ns")
        self.assertEqual(state["target_namespace"], "test-ns")
        self.assertEqual(state["overall_status"], "IN_PROGRESS")
        self.assertEqual(state["current_phase"], PHASES[0])
        self.assertEqual(len(state["phases"]), len(PHASES))
        for phase in PHASES:
            self.assertIn(phase, state["phases"])
            self.assertEqual(state["phases"][phase]["status"], "PENDING")

    def test_load_and_save_state(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "migration-state.json"
            initial_data = {"test": "data"}

            save_state(initial_data, state_path)
            self.assertTrue(state_path.exists())

            loaded_data = load_state(state_path)
            self.assertEqual(loaded_data, initial_data)

    def test_load_nonexistent_state(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "nonexistent.json"
            self.assertEqual(load_state(state_path), {})

    def test_archive_existing_state(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "migration-execution-state.json"
            save_state({"test": "archive"}, state_path)

            archive_existing_state(state_path)
            self.assertFalse(state_path.exists())
            archived_files = list(
                Path(tmp_dir).glob("migration-execution-state.json.old-*")
            )
            self.assertEqual(len(archived_files), 1)


class TestHandoffSchemaValidation(unittest.TestCase):
    """Tests JSON schema validation for handoff and mapping files."""

    def test_validate_schema_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            schema_path = Path(tmp_dir) / "test.schema.json"
            schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            }
            schema_path.write_text(json.dumps(schema), encoding="utf-8")

            valid_data = {"name": "test-cluster"}
            validate_schema(valid_data, schema_path)

    def test_validate_handoff_files_integration(self):
        schemas_dir = (
            Path(__file__).resolve().parent.parent / "assets" / "schemas"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            handoff_dir = Path(tmp_dir)
            identity_map_file = handoff_dir / "identity-map.json"
            valid_identity_map = [
                {
                    "source": "arn:aws:iam::123456789012:role/my-role",
                    "target": "my-sa@my-project.iam.gserviceaccount.com",
                }
            ]
            identity_map_file.write_text(
                json.dumps(valid_identity_map), encoding="utf-8"
            )

            # Should complete cleanly without error
            validate_handoff_files(handoff_dir, schemas_dir)

    def test_validate_handoff_files_invalid_schema(self):
        schemas_dir = (
            Path(__file__).resolve().parent.parent / "assets" / "schemas"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            handoff_dir = Path(tmp_dir)
            identity_map_file = handoff_dir / "identity-map.json"
            invalid_identity_map = [{"invalid_field": True}]
            identity_map_file.write_text(
                json.dumps(invalid_identity_map), encoding="utf-8"
            )

            with self.assertRaises(RuntimeError):
                validate_handoff_files(handoff_dir, schemas_dir)


class TestManifestParsing(unittest.TestCase):
    """Tests parsing and filtering GKE manifest files."""

    def test_get_matching_manifest_docs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_dir = Path(tmp_dir)
            yaml_file = manifest_dir / "workloads.yaml"
            yaml_content = (
                "apiVersion: apps/v1\n"
                "kind: Deployment\n"
                "metadata:\n"
                "  name: app-dep\n"
                "---\n"
                "apiVersion: v1\n"
                "kind: Service\n"
                "metadata:\n"
                "  name: app-svc\n"
            )
            yaml_file.write_text(yaml_content, encoding="utf-8")

            deployments = get_matching_manifest_docs(
                manifest_dir, {"Deployment"}
            )
            self.assertEqual(len(deployments), 1)
            self.assertEqual(deployments[0]["kind"], "Deployment")

            services = get_matching_manifest_docs(manifest_dir, {"Service"})
            self.assertEqual(len(services), 1)
            self.assertEqual(services[0]["kind"], "Service")

            secrets = get_matching_manifest_docs(manifest_dir, {"Secret"})
            self.assertEqual(len(secrets), 0)


class TestPhaseExecutionAction(unittest.TestCase):
    """Tests phase action execution with mock and kubectl."""

    def test_execute_phase_action_mock(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_dir = Path(tmp_dir)
            result = execute_phase_action(
                "Phase 3: Workloads Deployment",
                manifest_dir,
                "default",
                mock=True,
            )
            self.assertTrue(result)

    def test_execute_phase_action_no_resources(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_dir = Path(tmp_dir)
            result = execute_phase_action(
                "Phase 3: Workloads Deployment",
                manifest_dir,
                "default",
                mock=False,
            )
            self.assertTrue(result)

    @patch("subprocess.run")
    def test_execute_phase_action_kubectl_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_dir = Path(tmp_dir)
            yaml_file = manifest_dir / "dep.yaml"
            yaml_file.write_text(
                "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name:"
                " test",
                encoding="utf-8",
            )

            result = execute_phase_action(
                "Phase 3: Workloads Deployment",
                manifest_dir,
                "production",
                mock=False,
                request_timeout="45s",
            )
            self.assertTrue(result)
            mock_run.assert_called_once()
            cmd_args = mock_run.call_args[0][0]
            self.assertIn("kubectl", cmd_args)
            self.assertIn("apply", cmd_args)
            self.assertIn("--request-timeout=45s", cmd_args)
            self.assertIn("-n", cmd_args)
            self.assertIn("production", cmd_args)


class TestLoadOrPromptState(unittest.TestCase):
    """Tests load_or_prompt_state logic."""

    @patch("execute_migration.ask_user_choice")
    def test_load_or_prompt_state_completed_start_fresh(self, mock_ask):
        mock_ask.return_value = "START_FRESH"
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "state.json"
            save_state(
                {
                    "overall_status": "COMPLETED",
                    "migration_id": "mig-123",
                    "target_namespace": "prod",
                },
                state_path,
            )

            state = load_or_prompt_state(state_path, "prod", force_fresh=False)
            self.assertEqual(state["overall_status"], "IN_PROGRESS")
            self.assertEqual(state["target_namespace"], "prod")
            mock_ask.assert_called_once()

    @patch("execute_migration.ask_user_choice")
    def test_load_or_prompt_state_failed_resume(self, mock_ask):
        mock_ask.return_value = "RESUME"
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "state.json"
            save_state(
                {
                    "overall_status": "FAILED",
                    "migration_id": "mig-123",
                    "current_phase": "Phase 2: Storage and Data Sync",
                    "phases": {},
                },
                state_path,
            )

            state = load_or_prompt_state(state_path, "prod", force_fresh=False)
            self.assertEqual(state["overall_status"], "IN_PROGRESS")
            self.assertEqual(state["migration_id"], "mig-123")
            mock_ask.assert_called_once()

    def test_get_matching_manifest_docs_list_unpacking_and_sorting(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_dir = Path(tmp_dir)
            yaml_file = manifest_dir / "resources.yaml"
            yaml_content = (
                "apiVersion: v1\n"
                "kind: List\n"
                "items:\n"
                "  - apiVersion: v1\n"
                "    kind: ServiceAccount\n"
                "    metadata:\n"
                "      name: sa-first\n"
                "  - apiVersion: v1\n"
                "    kind: Namespace\n"
                "    metadata:\n"
                "      name: ns-target\n"
            )
            yaml_file.write_text(yaml_content, encoding="utf-8")

            docs = get_matching_manifest_docs(
                manifest_dir, {"Namespace", "ServiceAccount"}
            )
            self.assertEqual(len(docs), 2)
            self.assertEqual(docs[0]["kind"], "Namespace")
            self.assertEqual(docs[1]["kind"], "ServiceAccount")

    def test_execute_phase_action_returns_resources_created(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_dir = Path(tmp_dir)
            yaml_file = manifest_dir / "dep.yaml"
            yaml_file.write_text(
                "apiVersion: apps/v1\n"
                "kind: Deployment\n"
                "metadata:\n"
                "  name: my-app",
                encoding="utf-8",
            )
            success, created = execute_phase_action(
                "Phase 3: Workloads Deployment",
                manifest_dir,
                "default",
                mock=True,
            )
            self.assertTrue(success)
            self.assertEqual(created, ["Deployment/my-app"])

    def test_load_or_prompt_state_auto_approve(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "state.json"
            save_state(
                {
                    "overall_status": "FAILED",
                    "migration_id": "mig-auto",
                    "current_phase": "Phase 2: Storage and Data Sync",
                    "phases": {},
                },
                state_path,
            )

            state = load_or_prompt_state(
                state_path, "prod", force_fresh=False, auto_approve=True
            )
            self.assertEqual(state["overall_status"], "IN_PROGRESS")
            self.assertEqual(state["migration_id"], "mig-auto")


if __name__ == "__main__":
    unittest.main()
