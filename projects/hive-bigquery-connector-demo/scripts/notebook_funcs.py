# Copyright 2023 Google LLC
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

"""Functions to build the Jupyter Notebook from the paragraph files.

These functions are used to build the Jupyter Notebook from the paragraph files.
while replacing the variables/placeholders with the actual values.
"""

import json
import logging
import os
import uuid

from state import ScriptState

logger = logging.getLogger(__name__)
logger.info(__name__)


def compile_notebook():
  """Compiles the Jupyter Notebook from the paragraph files."""
  logger.info("Compiling Jupyter Notebook")

  def replace_line(line):
    for state_key, state in ScriptState.tf_state().__dict__.items():
      state_key_up = f"<{state_key.upper()}>"
      if state_key_up in line:
        line = line.rstrip().replace(
            state_key_up, state) + " # variable: " + state_key_up
    return line.rstrip() + "\n"

  notebook_path = "../notebook"
  paragraphs_path = "../notebook/paragraphs"
  cells = []
  for f in sorted(list(os.listdir(paragraphs_path))):
    with open(os.path.join(paragraphs_path, f), "r", encoding="utf-8") as fp:
      content = fp.readlines()
    content = [replace_line(line) for line in content if line.strip()]
    content[-1] = content[-1].rstrip()
    cell_type = f.split(".")[-1].replace("mdx", "markdown")
    cell = {
        "cell_type": cell_type,
        "source": content,
        "execution_count": None,
        "id": str(uuid.uuid1()),
        "metadata": {},
        "outputs": [],
    }
    cells.append(cell)
  notebook_json = {
      "cells": cells,
      "metadata": {
          "kernelspec": {
              "display_name": "Python 3",
              "language": "python",
              "name": "python3",
          },
          "language_info": {
              "codemirror_mode": {
                  "name": "ipython",
                  "version": 3,
              },
              "file_extension": ".py",
              "mimetype": "text/x-python",
              "name": "python",
              "nbconvert_exporter": "python",
              "pygments_l0exer": "ipython3",
              "version": "3.10.8"
          },
      },
      "nbformat": 4,
      "nbformat_minor": 5
  }
  notebook_full_path = os.path.join(notebook_path, "notebook.ipynb")
  with open(notebook_full_path, "w", encoding="utf-8") as fp:
    json.dump(notebook_json, fp, indent=2)
  return notebook_full_path


def update_notebook(notebook_full_path, staging_bucket):
  logger.info("Uploading Jupyter Notebook")
  gcs_bucket = ScriptState.gcs_client().get_bucket(staging_bucket)
  filename = notebook_full_path.split("/")[-1]
  blob_name = f"notebooks/jupyter/{filename}"
  gcs_blob = gcs_bucket.blob(blob_name)
  gcs_blob.upload_from_filename(notebook_full_path)
