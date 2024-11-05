#!/bin/bash

#
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
#

#######################################
# Checks if the configuration file for
# patroni exists, and starts the
# patroni service.
# Should run under postgres user.
#
# Returns:
#   non-zero when the expected yml
#   configuration file does not exist
#######################################

config_file_path="$PGHOME/config/patroni.yml"

if [ ! -f "$config_file_path" ]; then
  echo "Configuration file $config_file_path does not exist, is not readable, or is not a file."
  exit 1
fi

patroni "$config_file_path"
