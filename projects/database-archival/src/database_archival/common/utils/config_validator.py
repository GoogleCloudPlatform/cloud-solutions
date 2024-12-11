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

"""Provides common utilities to validate config data."""

import enum
import re
from typing import Any


def _get_type_name(value: Any) -> str:
    """Gets the name of the typing of a variable.

    Args:
        value: value for which to get type name.

    Returns:
        Name of the class type.
    """
    type_str = str(type(value))
    type_name_re = re.search("<class '(.*?)'>", str(type_str), re.IGNORECASE)

    if type_name_re:
        return type_name_re.group(1)

    return str(type_str)


def assert_is_valid_boolean(field_value: Any, field_name: str):
    """Validates that a certain field is a valid boolean.

    Args:
        field_value: value of the field to validate.
        field_name: name of the field to validate.

    Raises:
        ValueError: field is None.
        ValueError: field is not a boolean.
    """
    if field_value is None:
        raise ValueError(f'{field_name} is required and was not provided.')

    if not isinstance(field_value, bool):
        raise ValueError(
            f'{field_name} must be a boolean. '
            f'Got: {_get_type_name(field_value)}.'
        )


def assert_is_valid_enum_string(
    field_value: Any, field_name: str, enum_class: enum.Enum
):
    """Validates that a certain field is a valid enum (string form).

    Args:
        field_value: value of the field to validate.
        field_name: name of the field to validate.
        enum_class: enum to which to the string should belong.

    Raises:
        ValueError: field is empty or None.
        ValueError: field is not a string.
    """
    assert_is_valid_string(field_value, field_name)

    try:
        enum_class[field_value.upper()]
    except KeyError as keyError:
        supported_values = ', '.join(
            [str(member) for member in enum_class.__members__]
        )
        raise ValueError(
            f'{field_name} must be one of {supported_values}. '
            f'Got: {field_value}.'
        ) from keyError


def assert_is_valid_integer(field_value: Any, field_name: str):
    """Validates that a certain field is a valid integer.

    Args:
        field_value: value of the field to validate.
        field_name: name of the field to validate.

    Raises:
        ValueError: field is None.
        ValueError: field is not a string.
    """
    if field_value is None:
        raise ValueError(f'{field_name} is required and was not provided.')

    if not isinstance(field_value, int):
        raise ValueError(
            f'{field_name} must be an integer. '
            f'Got: {_get_type_name(field_value)}.'
        )


def assert_is_positive_integer(
    field_value: Any, field_name: str, include_zero: bool = False
):
    """Validates that a certain field is a valid positive integer.

    Args:
        field_value: value of the field to validate.
        field_name: name of the field to validate.
        include_zero: whether to consider zero in the positive list.

    Raises:
        ValueError: value is below zero.
        ValueError: valie is zero and include_zero is False.
    """
    assert_is_valid_integer(field_value, field_name)
    if field_value < 0 or (field_value == 0 and not include_zero):
        include_zero_text = ' or zero' if include_zero else '.'
        raise ValueError(
            f'{field_name} must be positive{include_zero_text}. '
            f'Got: {field_value}.'
        )


def assert_is_valid_string(field_value: Any, field_name: str):
    """Validates that a certain field is a valid string.

    Args:
        field_value: value of the field to validate.
        field_name: name of the field to validate.

    Raises:
        ValueError: field is empty or None.
        ValueError: field is not a string.
    """
    if not field_value:
        raise ValueError(f'{field_name} is required and was not provided.')

    if not isinstance(field_value, str):
        raise ValueError(
            f'{field_name} must be a string. '
            f'Got: {_get_type_name(field_value)}.'
        )


def assert_is_valid_list(field_value: Any, field_name: str):
    """Validates that a certain field is a valid list.

    Args:
        field_value: value of the field to validate.
        field_name: name of the field to validate.

    Raises:
        ValueError: field is empty or None.
        ValueError: field is not a list.
    """
    if not field_value:
        raise ValueError(f'{field_name} is required and was not provided.')

    if not isinstance(field_value, list):
        raise ValueError(
            f'{field_name} must be a list. Got: {_get_type_name(field_value)}.'
        )
