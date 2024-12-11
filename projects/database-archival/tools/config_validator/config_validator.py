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

"""Validates a JSON file with the configuration of the DAG.

CLI util to validate that the JSON file can be parsed, guaranteeing that the DAG
will be created. The tool does not validate that the DAG will run successfully.
For example, if the database details are wrong, but on the right format, the
JSON will pass the validation, the DAG will be created successfully, but the run
will fail on runtime.
"""

import json
import logging
import os
import sys
import argparse

from database_archival.dag.models import config_model
from typing import Iterable, Optional


_LOGGER = logging.getLogger(__name__)

_RUN_COMMAND_WITH_HELP_TEXT = (
    'Run with `--help` for more information on how to run this tool.'
)


def _parse_file_contents(config_data: str):
    """Parses and validates the DAG configuration.

    Args:
        config_data: config contents in plain text.
    """
    try:
        config_json = json.loads(config_data)
    except json.decoder.JSONDecodeError as e:
        _LOGGER.error('Unable to parse JSON file. %s.', str(e))
        return

    configs = []
    for i, table_config in enumerate(config_json):
        try:
            configs.append(config_model.TableConfig(**table_config))
        except ValueError as e:
            _LOGGER.error('Unable to parse config[%s]. %s', str(i), str(e))
            return

    if not configs:
        _LOGGER.warning('Detected 0 table configurations. Is this expected?')
        return

    _LOGGER.info(
        'Detected %s table configuration(s). '
        'All table configurations were loaded successfully. '
        'Do note that this does not guarantee that the DAG will run '
        'successfully.',
        str(len(config_json)),
    )


def _validate_config(file_path: str):
    """Validates the provided local JSON file.

    Args:
        file_path: path to the JSON file to validate.
    """
    current_directory = os.getcwd()
    file_path = os.path.join(current_directory, file_path)

    try:
        with open(file_path, 'r', encoding='utf-8') as config_file:
            _parse_file_contents(config_file.read())

    except FileNotFoundError:
        _LOGGER.error('File "%s" not found.', file_path)


def _parse_arguments(argv: Optional[Iterable[str]] = None):
    """Parses the arguments from the command line.

    Args:
        argv: command line arguments.

    Returns:
        A Tuple with the known and unknown arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--filename', type=str, help='path to the JSON file to validate'
    )
    return parser.parse_known_args(argv)


def main(argv: Optional[Iterable[str]] = None):
    """Acts as the entrypoint for the CLI to validate the JSON configuration.

    Args:
        argv: command line arguments.
    """
    try:
        command_args, unknown_args = _parse_arguments(argv)
    except (argparse.ArgumentError, SystemExit):
        _LOGGER.error(
            'Error: Unable to parse arguments. %s', _RUN_COMMAND_WITH_HELP_TEXT
        )
        return

    if unknown_args:
        _LOGGER.error(
            'Error: Detected unknown flags: %s. %s',
            str(unknown_args),
            _RUN_COMMAND_WITH_HELP_TEXT,
        )
        return

    if not command_args.filename:
        _LOGGER.error(
            'Error: Missing `--filename` argument. %s',
            _RUN_COMMAND_WITH_HELP_TEXT,
        )
        return

    _validate_config(command_args.filename)


if __name__ == '__main__':
    main(sys.argv)
