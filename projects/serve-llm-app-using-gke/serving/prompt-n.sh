#!/bin/bash
# Copyright 2024 Google LLC
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

USER_PROMPT="I'm looking for comfortable cycling shorts for women, what are some good options?"

curl -X POST http://localhost:"$1"/generate \
  -H "Content-Type: application/json" \
  -d @- <<EOF #| jq -r .predictions[0]
{
    "prompt": "<start_of_turn>user\n${USER_PROMPT}<end_of_turn>\n<start_of_turn>model\n",
    "temperature": 0.70,
    "top_p": 1.0,
    "top_k": 1.0,
    "max_tokens": 256
}
EOF
#    "prompt": "<start_of_turn>user\n${USER_PROMPT}<end_of_turn>\n",
