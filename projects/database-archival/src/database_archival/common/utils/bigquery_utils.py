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

"""Provides utilities to interact with BigQuery resources."""

from typing import Mapping

_INVALID_TABLE_MESSAGE = (
    'Expected table name in the format of '
    '"<project_id>.<dataset_id>.<table_id>". '
    'Example: "my-project.archival_dataset.tablename".'
)

_INVALID_TABLE_RESOURCE_MESSAGE = (
    'Expected table resource with project_id, dataset_id and table_id.'
)


def split_table_name(table_name: str) -> Mapping[str, str]:
    """Splits a table name into a table resource.

    Args:
        table_name: Table name in format <project_id>.<dataset_id>.<table_id>.

    Raises:
        ValueError: no table_name value.
        ValueError: table_name with no dots.
        ValueError: table_name with not enough parts to make project, dataset
            and table components.
        ValueError: table_name with one of project, dataset or table with empty
            values.

    Returns:
        Table resource broken down with project_id, dataset_id and table_id.
    """
    if not table_name:
        raise ValueError(_INVALID_TABLE_MESSAGE + ' Got empty value.')

    if '.' not in table_name:
        raise ValueError(_INVALID_TABLE_MESSAGE + f' Got: {table_name}.')

    if ':' in table_name:
        project_id, rest = table_name.split(':', maxsplit=1)
        if ':' in rest:
            raise ValueError(_INVALID_TABLE_MESSAGE + f' Got: {table_name}.')

        dataset_id, table_id = rest.split('.', maxsplit=1)
        if not project_id or not dataset_id or not table_id:
            raise ValueError(_INVALID_TABLE_MESSAGE + f' Got: {table_name}.')
        return {
            'project_id': project_id,
            'dataset_id': dataset_id,
            'table_id': table_id,
        }

    if len(table_name.split('.')) < 3:
        raise ValueError(_INVALID_TABLE_MESSAGE + f' Got: {table_name}.')

    project_id, dataset_id, table_id = table_name.split('.', maxsplit=2)
    if not project_id or not dataset_id or not table_id:
        raise ValueError(_INVALID_TABLE_MESSAGE + f' Got: {table_name}.')
    return {
        'project_id': project_id,
        'dataset_id': dataset_id,
        'table_id': table_id,
    }


def join_table_name(table_resource: Mapping[str, str]) -> str:
    """Joins a table resource into a table name.

    Args:
        table_resource: with project_id, dataset_id, table_id.

    Raises:
        ValueError: empty value.
        ValueError: project_id missing or empty.
        ValueError: dataset_id missing or empty.
        ValueError: table_id missing or empty.

    Returns:
        Table name as a string.
    """
    if not table_resource:
        raise ValueError(_INVALID_TABLE_RESOURCE_MESSAGE)

    project_id = table_resource.get('project_id')
    if not project_id:
        raise ValueError(
            _INVALID_TABLE_RESOURCE_MESSAGE
            + ' Missing project_id. Got: {table_resource}.'
        )

    dataset_id = table_resource.get('dataset_id')
    if not dataset_id:
        raise ValueError(
            _INVALID_TABLE_RESOURCE_MESSAGE
            + ' Missing dataset_id. Got: {table_resource}.'
        )

    table_id = table_resource.get('table_id')
    if not table_id:
        raise ValueError(
            _INVALID_TABLE_RESOURCE_MESSAGE
            + ' Missing table_id. Got: {table_resource}.'
        )

    return '.'.join([project_id, dataset_id, table_id])
