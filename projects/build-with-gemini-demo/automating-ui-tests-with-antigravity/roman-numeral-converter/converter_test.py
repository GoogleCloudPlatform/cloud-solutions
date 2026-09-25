# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for Roman numeral converter module."""

import unittest

import converter


class ConverterTest(unittest.TestCase):
    """Tests for number_to_roman function."""

    def test_single_digits(self):
        self.assertEqual(converter.number_to_roman(1), "I")
        self.assertEqual(converter.number_to_roman(4), "IV")
        self.assertEqual(converter.number_to_roman(5), "V")
        self.assertEqual(converter.number_to_roman(9), "IX")

    def test_double_digits(self):
        self.assertEqual(converter.number_to_roman(10), "X")
        self.assertEqual(converter.number_to_roman(25), "XXV")
        self.assertEqual(converter.number_to_roman(40), "XL")
        self.assertEqual(converter.number_to_roman(50), "L")
        self.assertEqual(converter.number_to_roman(90), "XC")

    def test_hundreds_and_thousands(self):
        self.assertEqual(converter.number_to_roman(100), "C")
        self.assertEqual(converter.number_to_roman(400), "CD")
        self.assertEqual(converter.number_to_roman(500), "D")
        self.assertEqual(converter.number_to_roman(900), "CM")
        self.assertEqual(converter.number_to_roman(1000), "M")
        self.assertEqual(converter.number_to_roman(2026), "MMXXVI")

    def test_string_integer_input(self):
        self.assertEqual(converter.number_to_roman("10"), "X")
        self.assertEqual(converter.number_to_roman("25"), "XXV")

    def test_zero_or_negative_raises_value_error(self):
        with self.assertRaises(ValueError):
            converter.number_to_roman(0)
        with self.assertRaises(ValueError):
            converter.number_to_roman(-10)

    def test_invalid_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            converter.number_to_roman("invalid")


if __name__ == "__main__":
    unittest.main()
