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

"""Script to take a Jupyter Notebook file and deconstruct it into files.

This is a helper script, used mainly in development cycles, to facilitate the
developer to make changes directly to the notebook (.ipynb), and then run this
script in order to have those changes reflected in the paragraphs files (.mdx
and .code files).
"""

import argparse
import json
import os
import shutil
import sys

from state import ScriptState


def get_parser():
  """Returns the command line parser."""
  parser = argparse.ArgumentParser(prog="NotebookDeconstruct")
  parser.add_argument("NOTEBOOK_PATH", type=str)
  parser.add_argument("--paragraphs-path", type=str,
                      default=os.path.join("..", "notebook", "paragraphs"),
                      dest="paragraphs_path")
  return parser


comments_chars = ["#", "--"]


def run():
  """Main entry point for the script."""
  parser = get_parser()
  args = parser.parse_args(sys.argv[1:])
  tf_state = ScriptState.tf_state()
  notebook_path = args.NOTEBOOK_PATH
  paragraphs_path = args.paragraphs_path
  if notebook_path == "JUPYTER":
    bucket = ScriptState.gcs_client().get_bucket(
        ScriptState.tf_state().staging_bucket)
    blob = bucket.get_blob("notebooks/jupyter/notebook.ipynb")
    content = blob.download_as_string()
    f = json.loads(content)
  else:
    if not os.path.exists(notebook_path) or not os.path.isfile(notebook_path):
      print(f"{notebook_path} is not a path to a file")
      sys.exit(1)
    with open(notebook_path, "r", encoding="utf-8") as fp:
      f = json.load(fp)

  cells = f["cells"]

  shutil.rmtree(paragraphs_path)
  os.mkdir(paragraphs_path)

  for i, cell in enumerate(cells):
    num = str(i).zfill(4)
    suff = cell["cell_type"].replace("markdown", "mdx")
    file_path = os.path.join(paragraphs_path, f"{num}.{suff}")
    content = cell["source"]
    new_content = []
    for line in content:
      line = line.rstrip()
      for state_key, state in tf_state.__dict__.items():
        state_key_up = f"<{state_key.upper()}>"
        for comment_char in comments_chars:
          if line.endswith(f" {comment_char} variable: {state_key_up}"):
            line = line.replace(state, f"<{state_key.upper()}>")
            line = line.split(f"{comment_char} variable: ")[0].rstrip()

      new_content.append(line.rstrip() + "\n")
    if new_content:
      new_content[-1] = new_content[-1].rstrip()
      with open(file_path, "w", encoding="utf-8") as fp:
        fp.writelines(new_content)


if __name__ == "__main__":
  run()
