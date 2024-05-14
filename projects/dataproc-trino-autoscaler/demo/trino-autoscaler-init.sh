#!/usr/bin/env bash
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

## Description: Template for Dataproc initialization script to install Autoscaler application as a daemon.

# Update with your configuration for the uri
CONFIG_JAR_FILE_GCS_URI=""
CONFIG_PROTO_FILE_GCS_URI=""

ROLE=$(/usr/share/google/get_metadata_value attributes/dataproc-role)
TRINO_AUTO_SCALER_SERVICE="/usr/lib/systemd/system/trino_autoscaler.service"
TRINO_AUTOSCALE_FOLDER="/opt/trino_autoscaler"

readonly CONFIG_JAR_FILE_GCS_URI
readonly CONFIG_PROTO_FILE_GCS_URI
readonly ROLE
readonly TRINO_AUTO_SCALER_SERVICE
readonly TRINO_AUTOSCALE_FOLDER

function setup_trino_autoscaler {

  mkdir -p "${TRINO_AUTOSCALE_FOLDER}"

  # Copy JAR from GCS to local
  gsutil cp "${CONFIG_JAR_FILE_GCS_URI}" "${TRINO_AUTOSCALE_FOLDER}/trino_autoscaler.jar"

  # Copy Config file from GCS to local
  gsutil cp "${CONFIG_PROTO_FILE_GCS_URI}" "${TRINO_AUTOSCALE_FOLDER}/config.textproto"

  # Create Log file
  touch "${TRINO_AUTOSCALE_FOLDER}/trino_autoscaler.log"
  chmod a+r "${TRINO_AUTOSCALE_FOLDER}/trino_autoscaler.log"
  ln -s "${TRINO_AUTOSCALE_FOLDER}/trino_autoscaler.log" /var/log/trino_autoscaler.log

  # Create systemd service
  cat <<EOF >"${TRINO_AUTO_SCALER_SERVICE}"
[Unit]
Description=Trino Autoscaler Service
After=trino.service

[Service]
Type=simple
ExecStart=java -jar ${TRINO_AUTOSCALE_FOLDER}/trino_autoscaler.jar ${TRINO_AUTOSCALE_FOLDER}/config.textproto
ExecStop=/bin/kill -15 \$MAINPID
Restart=always
StandardOutput=append:/var/log/trino_autoscaler.log
StandardError=append:/var/log/trino_autoscaler.log

[Install]
WantedBy=multi-user.target
EOF
  chmod a+rx ${TRINO_AUTO_SCALER_SERVICE}
}

if [[ "${ROLE}" == 'Master' ]]; then
  # Run only on Master
  setup_trino_autoscaler
  systemctl daemon-reload
  systemctl enable trino_autoscaler
  systemctl start trino_autoscaler
fi
