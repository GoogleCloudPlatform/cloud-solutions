# Copyright 2026 Google LLC
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

"""Local CLI wrapper that re-execs inside the project virtualenv when needed."""

import importlib
import os
import sys
from pathlib import Path


def _run() -> None:
    venv_python = Path(__file__).resolve().parent / ".venv" / "bin" / "python3"
    if sys.prefix == sys.base_prefix and venv_python.exists():
        os.execv(str(venv_python), [str(venv_python), *sys.argv])

    cli_mod = importlib.import_module("deployment.cli")
    cli_mod.main()


if __name__ == "__main__":
    _run()
