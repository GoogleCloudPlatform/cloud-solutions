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

import asyncio
import os
import sys

from ge_video.agent import assemble_final_video
from google.adk.agents.tool_context import ToolContext

async def main():
    ctx = ToolContext(session_id="test_session")
    ctx.state = {
        "va_num_scenes": 2,
        "va_company_name": "Test Co",
        "va_brand_context": "Test brand",
        "va_enable_music": False,
        "va_session_folder": "test_folder",
        "va_tagline": "Hello World",
        "va_scene_order": [1, 2],
        "va_scene_1_clip_uri": "gs://test/1.mp4",
        "va_scene_2_clip_uri": "gs://test/2.mp4",
        "va_scene_1_voiceover_uri": "",
        "va_scene_2_voiceover_uri": "",
        "va_assembly_prepared": True,
    }

    print("Running assemble_final_video...")
    res = await assemble_final_video(ctx)
    print("Result:", res)

if __name__ == "__main__":
    asyncio.run(main())
