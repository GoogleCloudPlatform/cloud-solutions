#!/bin/bash
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

# Install some dependencies required for the demo

# this is for running PyHive on Dataproc
sudo apt-get install -y libsasl2-dev

gsutil cp "gs://$(gcloud config get-value project)-hivebq-bucket/scripts/initialization-requirements.txt" ./requirements.txt

# These python libraries are being either being used in the demo (sh) or are required to run PyHive (sasl)
pip install --require-hashes -r ./requirements.txt
