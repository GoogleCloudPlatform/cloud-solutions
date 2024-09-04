# Copyright 2024 Google LLC
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

FROM tensorflow/tensorflow:2.17.0-gpu

RUN pip install --no-cache-dir --ignore-installed \
    "google-cloud-aiplatform[autologging]"==1.65.0 \
    tensorflow-datasets==4.9.6 \
    keras==3.5.0 \
    keras-cv==0.9.0

ENV PYTHONUNBUFFERED="true"

COPY trainer/ /trainer/

ENTRYPOINT ["python3", "/trainer/main.py"]
