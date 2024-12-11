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

"""Tests for bigquery_utils."""

import unittest
from database_archival.common.utils import bigquery_utils
from absl.testing import parameterized


class TestBigQueryUtils(parameterized.TestCase):
    """Unit tests for bigquery_utils."""

    @parameterized.named_parameters(
        {
            'testcase_name': 'basic_case',
            'input_table_name': 'projectA.datasetT.tableX',
            'expected_output': {
                'project_id': 'projectA',
                'dataset_id': 'datasetT',
                'table_id': 'tableX',
            },
        },
        {
            'testcase_name': 'with_multiple_dots_in_table',
            'input_table_name': 'project2:dataset3.table4.suffix.final',
            'expected_output': {
                'project_id': 'project2',
                'dataset_id': 'dataset3',
                'table_id': 'table4.suffix.final',
            },
        },
        {
            'testcase_name': 'with_colon',
            'input_table_name': 'projectN:datasetI.tableT',
            'expected_output': {
                'project_id': 'projectN',
                'dataset_id': 'datasetI',
                'table_id': 'tableT',
            },
        },
        {
            'testcase_name': 'with_colon_and_multiple_dots',
            'input_table_name': 'projectT:dataset9.table9999.abc',
            'expected_output': {
                'project_id': 'projectT',
                'dataset_id': 'dataset9',
                'table_id': 'table9999.abc',
            },
        },
    )
    def test_split_table_name(self, input_table_name, expected_output):
        """Tests that split_table_name splits into expected parts."""
        output = bigquery_utils.split_table_name(input_table_name)

        self.assertDictEqual(output, expected_output)

    @parameterized.named_parameters(
        {
            'testcase_name': 'empty',
            'input_table_name': '',
        },
        {
            'testcase_name': 'None',
            'input_table_name': None,
        },
        {
            'testcase_name': 'no_dot',
            'input_table_name': 'project_dataset_table',
        },
        {
            'testcase_name': 'not_enough_parts',
            'input_table_name': 'project.dataset',
        },
        {
            'testcase_name': 'not_enough_parts_colon',
            'input_table_name': 'project:dataset',
        },
        {
            'testcase_name': 'multiple_colon',
            'input_table_name': 'project:dataset:table',
        },
        {
            'testcase_name': 'colon_on_table_name',
            'input_table_name': 'project:dataset.table:suffix',
        },
        {
            'testcase_name': 'empty_project',
            'input_table_name': '.dataset.table',
        },
        {
            'testcase_name': 'empty_project_colon',
            'input_table_name': ':dataset.table',
        },
        {
            'testcase_name': 'empty_dataset',
            'input_table_name': 'project..table',
        },
        {
            'testcase_name': 'empty_table',
            'input_table_name': 'project.dataset.',
        },
    )
    def test_split_table_name_raises_for_bad_table_name(self, input_table_name):
        """Tests that split_table_name raises for bad table names."""
        with self.assertRaisesRegex(
            ValueError,
            # pylint: disable-next=protected-access
            bigquery_utils._INVALID_TABLE_MESSAGE,
        ):
            bigquery_utils.split_table_name(input_table_name)

    @parameterized.named_parameters(
        {
            'testcase_name': 'basic_case',
            'input_table_resource': {
                'project_id': 'projectA',
                'dataset_id': 'datasetT',
                'table_id': 'tableX',
            },
            'expected_output': 'projectA.datasetT.tableX',
        },
        {
            'testcase_name': 'with_multiple_dots_in_table',
            'input_table_resource': {
                'project_id': 'project2',
                'dataset_id': 'dataset3',
                'table_id': 'table4.suffix.final',
            },
            'expected_output': 'project2.dataset3.table4.suffix.final',
        },
    )
    def test_join_table_name(self, input_table_resource, expected_output):
        """Tests that joins table name splits into expected parts."""
        output = bigquery_utils.join_table_name(input_table_resource)

        self.assertEqual(output, expected_output)

    @parameterized.named_parameters(
        {
            'testcase_name': 'empty_dict',
            'input_table_resource': {},
        },
        {
            'testcase_name': 'None',
            'input_table_resource': None,
        },
        {
            'testcase_name': 'empty_project',
            'input_table_resource': {
                'project_id': '',
                'dataset_id': 'dataset',
                'table_id': 'table',
            },
        },
        {
            'testcase_name': 'None_project',
            'input_table_resource': {
                'project_id': None,
                'dataset_id': 'dataset',
                'table_id': 'table',
            },
        },
        {
            'testcase_name': 'missing_project',
            'input_table_resource': {
                'dataset_id': 'dataset',
                'table_id': 'table',
            },
        },
        {
            'testcase_name': 'empty_dataset',
            'input_table_resource': {
                'project_id': 'project',
                'dataset_id': '',
                'table_id': 'table',
            },
        },
        {
            'testcase_name': 'None_dataset',
            'input_table_resource': {
                'project_id': 'project',
                'dataset_id': None,
                'table_id': 'table',
            },
        },
        {
            'testcase_name': 'missing_dataset',
            'input_table_resource': {
                'project_id': 'project',
                'table_id': 'table',
            },
        },
        {
            'testcase_name': 'empty_table',
            'input_table_resource': {
                'project_id': 'project',
                'dataset_id': 'dataset',
                'table_id': '',
            },
        },
        {
            'testcase_name': 'None_table',
            'input_table_resource': {
                'project_id': 'project',
                'dataset_id': 'dataset',
                'table_id': None,
            },
        },
        {
            'testcase_name': 'missing_table',
            'input_table_resource': {
                'project_id': 'project',
                'dataset_id': 'dataset',
            },
        },
    )
    def test_join_table_name_raises_bad_table_resource(
        self, input_table_resource
    ):
        """Tests that join_table_name raises for bad table_resource."""
        with self.assertRaisesRegex(
            ValueError,
            # pylint: disable-next=protected-access
            bigquery_utils._INVALID_TABLE_RESOURCE_MESSAGE,
        ):
            bigquery_utils.join_table_name(input_table_resource)


if __name__ == '__main__':
    unittest.main()
