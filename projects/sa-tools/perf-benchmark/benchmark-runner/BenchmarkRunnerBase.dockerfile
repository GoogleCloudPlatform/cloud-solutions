#
# Copyright 2023 Google LLC
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
#

FROM google/cloud-sdk:476.0.0 AS executor
RUN apt-get install --no-install-recommends -y python-is-python3
RUN mkdir /PerfKitBenchmarker \
    # Clone forked PerfkitBenchmarker repo
    && curl https://github.com/GoogleCloudPlatform/PerfKitBenchmarker/archive/224a10d1d322d89e2602858ac98db2d602e0fcc1.tar.gz -Lo PerfKitBenchmarker.tar.gz \
    && tar --transform="s|PerfKitBenchmarker-224a10d1d322d89e2602858ac98db2d602e0fcc1|PerfKitBenchmarker|" \
    -xzf PerfKitBenchmarker.tar.gz \
    && rm PerfKitBenchmarker.tar.gz

COPY ./prakhag2_changes.diff /PerfKitBenchmarker
COPY ./requirements.in /PerfKitBenchmarker
COPY ./requirements_with_hashes.txt /PerfKitBenchmarker

WORKDIR /PerfKitBenchmarker
## Pass if requirements.txt has not changed
RUN diff -q requirements.in requirements.txt \
    ## Apply prakhag2 changes
    && patch -p1 < prakhag2_changes.diff \
    ## Install required python dependencies
    && pip3 install \
      --no-cache-dir \
      --require-hashes \
      -r requirements_with_hashes.txt

ENV PERFKIT_FOLDER="/PerfKitBenchmarker"
