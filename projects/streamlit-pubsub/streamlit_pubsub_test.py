# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for streamlit pubsub.

Currently, only the Buffer class has tests.
"""


import unittest

from streamlit_pubsub import Buffer


class BufferTest(unittest.TestCase):
    """Test the Buffer streamlit pubsub class."""

    def test_basic(self):
        b = Buffer(max_elem=3)

        self.assertEqual(b.get_elems(-1), (-1, []))
        b.add("a")
        self.assertEqual(b.get_elems(-1), (0, ["a"]))
        self.assertEqual(b.get_elems(0), (0, []))
        self.assertEqual(b.get_elems(1), (0, []))
        b.add("b")
        self.assertEqual(b.get_elems(-1), (1, ["a", "b"]))
        self.assertEqual(b.get_elems(0), (1, ["b"]))
        self.assertEqual(b.get_elems(1), (1, []))
        self.assertEqual(b.get_elems(2), (1, []))
        b.add("c")
        self.assertEqual(b.get_elems(-1), (2, ["a", "b", "c"]))
        self.assertEqual(b.get_elems(0), (2, ["b", "c"]))
        self.assertEqual(b.get_elems(1), (2, ["c"]))
        self.assertEqual(b.get_elems(2), (2, []))
        self.assertEqual(b.get_elems(3), (2, []))
        b.add("d")
        self.assertEqual(b.get_elems(-1), (3, ["b", "c", "d"]))
        self.assertEqual(b.get_elems(0), (3, ["b", "c", "d"]))
        self.assertEqual(b.get_elems(1), (3, ["c", "d"]))
        self.assertEqual(b.get_elems(2), (3, ["d"]))
        self.assertEqual(b.get_elems(3), (3, []))
        self.assertEqual(b.get_elems(4), (3, []))
        b.add("e")
        self.assertEqual(b.get_elems(-1), (4, ["c", "d", "e"]))
        self.assertEqual(b.get_elems(0), (4, ["c", "d", "e"]))
        self.assertEqual(b.get_elems(1), (4, ["c", "d", "e"]))
        self.assertEqual(b.get_elems(2), (4, ["d", "e"]))
        self.assertEqual(b.get_elems(3), (4, ["e"]))
        self.assertEqual(b.get_elems(4), (4, []))
        self.assertEqual(b.get_elems(5), (4, []))
        b.add("f")
        self.assertEqual(b.get_elems(-1), (5, ["d", "e", "f"]))
        self.assertEqual(b.get_elems(0), (5, ["d", "e", "f"]))
        self.assertEqual(b.get_elems(1), (5, ["d", "e", "f"]))
        self.assertEqual(b.get_elems(2), (5, ["d", "e", "f"]))
        self.assertEqual(b.get_elems(3), (5, ["e", "f"]))
        self.assertEqual(b.get_elems(4), (5, ["f"]))
        self.assertEqual(b.get_elems(5), (5, []))
        self.assertEqual(b.get_elems(6), (5, []))
        b.add("g")
        self.assertEqual(b.get_elems(-1), (6, ["e", "f", "g"]))
        self.assertEqual(b.get_elems(0), (6, ["e", "f", "g"]))
        self.assertEqual(b.get_elems(1), (6, ["e", "f", "g"]))
        self.assertEqual(b.get_elems(2), (6, ["e", "f", "g"]))
        self.assertEqual(b.get_elems(3), (6, ["e", "f", "g"]))
        self.assertEqual(b.get_elems(4), (6, ["f", "g"]))
        self.assertEqual(b.get_elems(5), (6, ["g"]))
        self.assertEqual(b.get_elems(6), (6, []))
        self.assertEqual(b.get_elems(7), (6, []))
