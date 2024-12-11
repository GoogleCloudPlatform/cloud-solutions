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

"""Generates task names for DAG tasks."""

from typing import Optional


def get_table_task_group_name(database_table_name: str) -> str:
    """Gets the task name for the top workflow name.

    Args:
        database_table_name: table name of this task group.

    Returns:
        Name of the overall task group for this table.
    """
    if not database_table_name:
        raise ValueError('database_table_name must be provided.')

    return f'{database_table_name}_workflow'


def get_task_group_name(
    *, database_table_name: Optional[str], task_group_name: str
) -> str:
    """Gets the task group name for a certain task.

    Args:
        database_table_name: table name to which this task group belongs.
        task_group_name: name of the task group.

    Returns:
        Name of the task group.
    """
    if not task_group_name:
        raise ValueError('task_group_name must be provided.')

    name_parts = []

    if database_table_name:
        name_parts.append(get_table_task_group_name(database_table_name))

    name_parts.append(task_group_name)

    return '.'.join(name_parts)


def get_task_name(
    *,
    database_table_name: Optional[str] = None,
    task_group_name: Optional[str] = None,
    task_name: str,
) -> str:
    """Generates the task name.

    Args:
        database_table_name: table name where this task belongs.
        task_group_name: name of the task group where this task belongs.
        task_name: name of the task to get.

    Raises:
        ValueError: task_name not provided.

    Returns:
        Name of the task.
    """
    if not task_name:
        raise ValueError('task_name must be provided.')

    name_parts = []

    if task_group_name:
        name_parts.append(
            get_task_group_name(
                database_table_name=database_table_name,
                task_group_name=task_group_name,
            )
        )
    elif database_table_name:
        name_parts.append(get_table_task_group_name(database_table_name))

    name_parts.append(task_name)

    return '.'.join(name_parts)
