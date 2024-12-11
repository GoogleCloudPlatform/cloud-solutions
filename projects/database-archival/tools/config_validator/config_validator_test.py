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

"""Tests for config_validator tool."""

import os
import unittest
from unittest import mock
from absl.testing import parameterized

import config_validator


class TestConfigModel(parameterized.TestCase):
    """Tests for config_validator tool."""

    def setUp(self):
        super().setUp()
        self.logger_mock = self.enter_context(
            mock.patch.object(config_validator, '_LOGGER', autospec=True)
        )

    def test_config_validator_validates_valid_file(self):
        """Tests that the tool validates and logs for valid configurations."""
        config_validator.main(
            ['--filename', './tools/config_validator/testdata/good_config.json']
        )

        self.logger_mock.info.assert_called_once_with(
            'Detected %s table configuration(s). '
            'All table configurations were loaded successfully. '
            'Do note that this does not guarantee that the DAG will run '
            'successfully.',
            '2',
        )

    @parameterized.parameters(
        [
            {
                'flags': ['--bad_flag'],
                'log_error_args': (
                    'Error: Detected unknown flags: %s. %s',
                    "['--bad_flag']",
                    'Run with `--help` for more information on how to run this '
                    'tool.',
                ),
            },
            {
                'flags': ['--filename'],
                'log_error_args': (
                    'Error: Unable to parse arguments. %s',
                    'Run with `--help` for more information on how to run this '
                    'tool.',
                ),
            },
            {
                'flags': ['--filename', 'not_existing_file.json'],
                'log_error_args': (
                    'File "%s" not found.',
                    f'{os.getcwd()}/not_existing_file.json',
                ),
            },
        ]
    )
    def test_config_validator_logs_errors_for_bad_call_arguments(
        self, flags, log_error_args
    ):
        """Tests that the tool fails and logs errors for bad commands."""
        config_validator.main(flags)

        self.logger_mock.error.assert_called_once_with(*log_error_args)

    @parameterized.parameters(
        [
            {
                'flags': [
                    '--filename',
                    'tools/config_validator/testdata/bad_config.json',
                ],
                'log_error_args': (
                    'Unable to parse config[%s]. %s',
                    '1',
                    'table_primary_key_columns is required and was not '
                    'provided.',
                ),
            },
            {
                'flags': [
                    '--filename',
                    'tools/config_validator/testdata/bad_format.json.txt',
                ],
                'log_error_args': (
                    'Unable to parse JSON file. %s.',
                    'Expecting property name enclosed in double quotes: '
                    'line 3 column 5 (char 10)',
                ),
            },
            {
                'flags': [
                    '--filename',
                    'tools/config_validator/testdata/empty_file.json.txt',
                ],
                'log_error_args': (
                    'Unable to parse JSON file. %s.',
                    'Expecting value: line 1 column 1 (char 0)',
                ),
            },
        ]
    )
    def test_config_validator_logs_errors_for_invalid_configs(
        self, flags, log_error_args
    ):
        """Tests that the tool fails and logs errors for bad config files."""
        config_validator.main(flags)

        self.logger_mock.error.assert_called_once_with(*log_error_args)

    @parameterized.parameters(
        [
            {
                'flags': [
                    '--filename',
                    'tools/config_validator/testdata/empty_config.json',
                ],
                'error_message': (
                    'Detected 0 table configurations. Is this expected?'
                ),
            },
        ]
    )
    def test_config_validator_warns_unexpected_configs(
        self, flags, error_message
    ):
        """Tests that the tool succeeds and wanrs for potential issues."""
        config_validator.main(flags)

        self.logger_mock.warning.assert_called_once_with(error_message)


if __name__ == '__main__':
    unittest.main()
