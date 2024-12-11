#  Copyright 2024 Google LLC
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""Tests for task_namer."""

import unittest
from database_archival.dag.utils import task_namer
from absl.testing import parameterized


class TestTaskNamer(parameterized.TestCase):
    """Tests for task_namer."""

    @parameterized.parameters(
        {
            'database_table_name': 'tableA',
            'expected_output': 'tableA_workflow',
        },
        {
            'database_table_name': 'tableB',
            'expected_output': 'tableB_workflow',
        },
    )
    def test_get_table_task_group_name_returns_expected_name(
        self, database_table_name, expected_output
    ):
        """Tests that get_table_task_group_name gets expected name."""
        output = task_namer.get_table_task_group_name(database_table_name)

        self.assertEqual(output, expected_output)

    def test_get_table_task_group_name_raises_with_no_table(self):
        """Tests that get_table_task_group_name raises if no table is passed."""
        with self.assertRaisesRegex(
            ValueError, 'database_table_name must be provided.'
        ):
            task_namer.get_table_task_group_name(database_table_name=None)

    @parameterized.parameters(
        {
            'task_group_name': 'groupT',
            'database_table_name': 'tableR',
            'expected_output': 'tableR_workflow.groupT',
        },
        {
            'database_table_name': None,
            'task_group_name': 'groupW',
            'expected_output': 'groupW',
        },
    )
    def test_get_task_group_name_returns_expected_name(
        self, database_table_name, task_group_name, expected_output
    ):
        """Tests that get_task_group_name returns expected name."""
        output = task_namer.get_task_group_name(
            task_group_name=task_group_name,
            database_table_name=database_table_name,
        )

        self.assertEqual(output, expected_output)

    @parameterized.parameters(
        {
            'database_table_name': 'tableL',
            'task_group_name': None,
        },
        {
            'database_table_name': None,
            'task_group_name': None,
        },
    )
    def test_get_task_group_name_raises_with_no_task_group__name(
        self, task_group_name, database_table_name
    ):
        """Tests that get_task_group_name raises if no task group is passed."""
        with self.assertRaisesRegex(
            ValueError, 'task_group_name must be provided.'
        ):
            task_namer.get_task_group_name(
                task_group_name=task_group_name,
                database_table_name=database_table_name,
            )

    @parameterized.parameters(
        {
            'database_table_name': 'tableR',
            'task_group_name': 'groupT',
            'task_name': 'taskZ',
            'expected_output': 'tableR_workflow.groupT.taskZ',
        },
        {
            'database_table_name': 'tableL',
            'task_group_name': None,
            'task_name': 'taskR',
            'expected_output': 'tableL_workflow.taskR',
        },
        {
            'database_table_name': None,
            'task_group_name': None,
            'task_name': 'taskV',
            'expected_output': 'taskV',
        },
        {
            'database_table_name': None,
            'task_group_name': 'groupW',
            'task_name': 'taskA',
            'expected_output': 'groupW.taskA',
        },
    )
    def test_get_task_name_returns_expected_name(
        self, database_table_name, task_group_name, task_name, expected_output
    ):
        """Tests that get_task_name returns expected task name."""
        output = task_namer.get_task_name(
            database_table_name=database_table_name,
            task_group_name=task_group_name,
            task_name=task_name,
        )

        self.assertEqual(output, expected_output)

    @parameterized.parameters(
        {
            'database_table_name': 'tableR',
            'task_group_name': 'groupT',
            'task_name': None,
        },
        {
            'database_table_name': None,
            'task_group_name': 'groupW',
            'task_name': None,
        },
        {
            'database_table_name': 'tableL',
            'task_group_name': None,
            'task_name': None,
        },
        {
            'database_table_name': None,
            'task_group_name': None,
            'task_name': None,
        },
    )
    def test_get_task_namer_raises_with_no_task_name(
        self, task_group_name, database_table_name, task_name
    ):
        """Tests that get_task_name raises if no task_name is passed."""
        with self.assertRaisesRegex(ValueError, 'task_name must be provided.'):
            task_namer.get_task_name(
                task_group_name=task_group_name,
                database_table_name=database_table_name,
                task_name=task_name,
            )


if __name__ == '__main__':
    unittest.main()
