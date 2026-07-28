# Copyright 2026 Google LLC
# Author: Layolin Jesudhass
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

import subprocess
import re
import sys

def get_duration(file_path):
    cmd = ["ffmpeg", "-i", file_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", res.stderr)
    if m:
        return float(m.group(1))*3600 + float(m.group(2))*60 + float(m.group(3))
    return None

print(get_duration(sys.argv[1] if len(sys.argv) > 1 else "nonexistent"))
