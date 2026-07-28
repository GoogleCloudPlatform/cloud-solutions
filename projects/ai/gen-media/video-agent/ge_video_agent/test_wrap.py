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
from ge_video.agent import generate_voice_preview, _create_voice_card_png, _wrap_mp3_as_mp4

async def main():
    print("Generating voice preview MP3...")
    mp3_bytes = await generate_voice_preview("Aoede", emotion="Calm", speaking_rate=1.0)
    print(f"Generated MP3 bytes: {len(mp3_bytes) if mp3_bytes else 0}")

    print("Creating PNG card...")
    card_png = _create_voice_card_png("Aoede", 2, "female")
    print(f"Generated PNG card: {len(card_png)}")

    print("Wrapping as MP4...")
    mp4_bytes = _wrap_mp3_as_mp4(mp3_bytes, card_png)
    print(f"Generated MP4 bytes: {len(mp4_bytes) if mp4_bytes else 0}")

if __name__ == "__main__":
    asyncio.run(main())
