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

export ML_HOST=ppe-automl-vi
export ML_PORT=8501

export MQTT_HOST=mosquitto
export MQTT_PORT=1883

python3 /opt/app/camera_client.py \
  --protocol file \
  --address /var/lib/viai/camera-data/ppe/images/ppe-image001.jpg \
  --device_id 'filecam' \
  --mode single \
  --ml \
  --ml_host "${ML_HOST}" \
  --ml_port "${ML_PORT}"
