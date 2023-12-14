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

FROM google/cloud-sdk:latest AS executor
RUN apt-get install python-is-python3
RUN mkdir /PerfKitBenchmarker
COPY ./requirements_with_hashes.txt /PerfKitBenchmarker
# Clone forked PerfkitBenchmarker repo
RUN curl https://github.com/prakhag2/PerfKitBenchmarker/archive/9b35b71c1da28a10e799e7027b9bf227ff421f1b.tar.gz -Lo PerfKitBenchmarker.tar.gz
RUN tar --transform="s|PerfKitBenchmarker-9b35b71c1da28a10e799e7027b9bf227ff421f1b|PerfKitBenchmarker|" \
    -xzf PerfKitBenchmarker.tar.gz
WORKDIR /PerfKitBenchmarker
RUN pip3 install --require-hashes -r requirements_with_hashes.txt
ENV PERFKIT_FOLDER="/PerfKitBenchmarker"
