# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility functions."""

import os
import shutil
import tempfile
from typing import List, Optional, Tuple

import pandas as pd
from absl import logging


def read_csv(
    csv_filename: str, num_records: int
) -> Optional[List[Tuple[str, str]]]:
    """Reads csv and returns a list of tuples from 'prompt' and 'path' columns.

    Args:
      csv_filename: str The path to the CSV file.
      num_records: int number of record to process, if negative, process all.

    Returns:
        Optional[List[Tuple[str, str]]]: A list of tuples where each tuple
          contains a value from the 'prompt' and 'path' columns of the CSV file.
          If the csv_filename is None or empty, returns None.

    Raises:
        AssertionError: If the CSV file does not contain 'prompt' and 'path'.
        FileNotFoundError: If the specified CSV file does not exist.
    """
    if not csv_filename:
        return None

    print(f"Read {csv_filename}")
    df = pd.read_csv(open(csv_filename, encoding="utf-8"))
    if num_records > 0:
        df = df[:num_records]
    assert "prompt" in df.columns, "Expected column 'prompt' not found"
    assert "path" in df.columns, "Expected column 'path' not found"
    data_list: List[Tuple[str, str]] = list(
        df[["prompt", "path"]].itertuples(index=False, name=None)
    )
    return data_list


def get_local_filename(local_tmp_dir: str, filename: str) -> str:
    """Generates a local filename in the temporary directory.

    Args:
        local_tmp_dir (str): The local temporary directory where the file should
          be stored.
        filename (str): The original filename.

    Returns:
        str: The generated local filename within the temporary directory.
    """
    dirname, basename = os.path.split(filename)
    basename = basename.split("%")[0]  # remove any URL-style suffix
    if dirname == local_tmp_dir:
        basename = "local_copy." + basename
    return os.path.join(local_tmp_dir, basename)


class LocalCopy:
    """Context manager for handling local copy of a file."""

    def __init__(self, filename, should_open_file=False):
        """Initializes a local copy.

        Args:
          filename: Full filename for the output (can be either local or
            remote).
          should_open_file: Whether the file should be opened (in read
            mode). See class documentation for usage example.
        """
        self._filename = filename
        self._should_open_file = should_open_file
        self._tmp_dir_obj = tempfile.TemporaryDirectory()
        self._local_filename = get_local_filename(
            self._tmp_dir_obj.name, filename
        )

        shutil.copy(filename, self._local_filename)
        logging.info(
            "Creating local copy %s from %s.", self._local_filename, filename
        )

        if should_open_file:
            self._open_file = open(self._local_filename, "r", encoding="utf-8")

    def __enter__(self):
        """Enters runtime context."""

        return (
            self._open_file if self._should_open_file else self._local_filename
        )

    def __exit__(self, *exc):
        """Exits the runtime context and cleans up the resource."""

        if self._should_open_file:
            self._open_file.close()
        if os.path.exists(self._local_filename):
            os.remove(self._local_filename)
        self._tmp_dir_obj.cleanup()
