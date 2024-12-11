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

"""Tests for config_validator."""

import enum
import unittest
from database_archival.common.utils import config_validator
from absl.testing import parameterized


class EnumForTest(enum.Enum):
    """Enum used for validating enum values on config validator."""

    A = 'a'
    B = 'b'


class TestBigQueryUtils(parameterized.TestCase):
    """Unit tests for config_validator."""

    @parameterized.parameters(True, False)
    def test_bool_passes(self, bool_value):
        """Tests assert boolean passes."""
        # Expect no assertion raised.
        config_validator.assert_is_valid_boolean(bool_value, 'bool_field')

    def test_bool_asserts_None(self):
        """Tests assert boolean asserts for None value."""
        with self.assertRaisesRegex(
            ValueError, 'bool_field is required and was not provided.'
        ):
            config_validator.assert_is_valid_boolean(None, 'bool_field')

    def test_bool_asserts_not_bool(self):
        """Tests assert boolean asserts for different type."""
        with self.assertRaisesRegex(
            ValueError, 'bool_field must be a boolean. Got: str.'
        ):
            config_validator.assert_is_valid_boolean('True', 'bool_field')

    @parameterized.parameters(
        (EnumForTest, 'A'),
        (EnumForTest, 'B'),
    )
    def test_enum_string_passes(self, enum_type, enum_value):
        """Tests assert enum string passes."""
        # Expect no assertion raised.
        config_validator.assert_is_valid_enum_string(
            enum_value,
            'enum_field',
            enum_type,
        )

    def test_enum_string_asserts_None(self):
        """Tests assert enum string asserts for None value."""
        with self.assertRaisesRegex(
            ValueError, 'enum_field is required and was not provided.'
        ):
            config_validator.assert_is_valid_enum_string(
                None,
                'enum_field',
                EnumForTest,
            )

    def test_enum_string_asserts_not_string(self):
        """Tests assert enum string asserts for non-string key."""
        with self.assertRaisesRegex(
            ValueError, 'enum_field must be a string. Got: int.'
        ):
            config_validator.assert_is_valid_enum_string(
                1,
                'enum_field',
                EnumForTest,
            )

    def test_enum_string_asserts_not_valid_key(self):
        """Tests assert enum string asserts for invalid key."""
        with self.assertRaisesRegex(
            ValueError, 'enum_field must be one of A, B. Got: C.'
        ):
            config_validator.assert_is_valid_enum_string(
                'C',
                'enum_field',
                EnumForTest,
            )

    @parameterized.parameters(-57, -1, 0, 1, 999)
    def test_int_passes(self, int_value):
        """Tests assert int passes."""
        # Expect no assertion raised.
        config_validator.assert_is_valid_integer(int_value, 'int_field')

    def test_int_asserts_None(self):
        """Tests assert int asserts for None value."""
        with self.assertRaisesRegex(
            ValueError, 'int_field is required and was not provided.'
        ):
            config_validator.assert_is_valid_integer(None, 'int_field')

    def test_int_asserts_not_int(self):
        """Tests assert int asserts for different type."""
        with self.assertRaisesRegex(
            ValueError, 'int_field must be an integer. Got: str.'
        ):
            config_validator.assert_is_valid_integer('1', 'int_field')

    @parameterized.parameters(0, 1, 999, -0)
    def test_positive_int_including_zero_passes(self, int_value):
        """Tests assert positive int passes, including zero."""
        # Expect no assertion raised.
        config_validator.assert_is_positive_integer(
            int_value, 'int_field', True
        )

    @parameterized.parameters(1, 999)
    def test_positive_int_excluding_zero_passes(self, int_value):
        """Tests assert positive int passes, excluding zero."""
        # Expect no assertion raised.
        config_validator.assert_is_positive_integer(
            int_value, 'int_field', False
        )

    @parameterized.parameters(-5, -99)
    def test_positive_int_asserts_for_negative(self, int_value):
        """Tests assert positive int asserts for negative values."""
        with self.assertRaisesRegex(
            ValueError, f'int_field must be positive or zero. Got: {int_value}.'
        ):
            config_validator.assert_is_positive_integer(
                int_value, 'int_field', True
            )

    @parameterized.parameters(-0, 0, -74)
    def test_positive_int_asserts_for_negative_or_zero(self, int_value):
        """Tests assert positive int asserts for negative or zero values."""
        with self.assertRaisesRegex(ValueError, 'int_field must be positive.'):
            config_validator.assert_is_positive_integer(
                int_value, 'int_field', False
            )

    @parameterized.parameters(True, False)
    def test_positive_int_asserts_None(self, include_zero):
        """Tests assert positive int asserts for None value."""
        with self.assertRaisesRegex(
            ValueError, 'int_field is required and was not provided.'
        ):
            config_validator.assert_is_positive_integer(
                None, 'int_field', include_zero
            )

    @parameterized.parameters(True, False)
    def test_positive_int_asserts_not_int(self, include_zero):
        """Tests assert positive int asserts for different type."""
        with self.assertRaisesRegex(
            ValueError, 'int_field must be an integer. Got: str.'
        ):
            config_validator.assert_is_positive_integer(
                '1', 'int_field', include_zero
            )

    @parameterized.parameters('abc', 'longer text_value')
    def test_str_passes(self, string_value):
        """Tests assert string passes."""
        # Expect no assertion raised.
        config_validator.assert_is_valid_string(string_value, 'string_field')

    def test_str_asserts_None(self):
        """Tests assert string asserts for None value."""
        with self.assertRaisesRegex(
            ValueError, 'string_field is required and was not provided.'
        ):
            config_validator.assert_is_valid_string(None, 'string_field')

    def test_str_asserts_empty_string(self):
        """Tests assert string asserts for empty value."""
        with self.assertRaisesRegex(
            ValueError, 'string_field is required and was not provided.'
        ):
            config_validator.assert_is_valid_string('', 'string_field')

    def test_str_asserts_not_string(self):
        """Tests assert string asserts for different type."""
        with self.assertRaisesRegex(
            ValueError, 'string_field must be a string. Got: bool.'
        ):
            config_validator.assert_is_valid_string(True, 'string_field')

    @parameterized.parameters(
        {'list_value': [0, 1, 2]},
        {'list_value': ['a', 'b', 'c']},
    )
    def test_list_passes(self, list_value):
        """Tests assert list passes."""
        # Expect no assertion raised.
        config_validator.assert_is_valid_list(list_value, 'list_field')

    def test_list_asserts_None(self):
        """Tests assert list asserts for None value."""
        with self.assertRaisesRegex(
            ValueError, 'list_field is required and was not provided.'
        ):
            config_validator.assert_is_valid_list(None, 'list_field')

    def test_list_asserts_empty_list(self):
        """Tests assert string asserts for empty value."""
        with self.assertRaisesRegex(
            ValueError, 'list_field is required and was not provided.'
        ):
            config_validator.assert_is_valid_list([], 'list_field')

    def test_list_asserts_not_list(self):
        """Tests assert string asserts for different type."""
        with self.assertRaisesRegex(
            ValueError, 'list_field must be a list. Got: str.'
        ):
            config_validator.assert_is_valid_list('text', 'list_field')


if __name__ == '__main__':
    unittest.main()
