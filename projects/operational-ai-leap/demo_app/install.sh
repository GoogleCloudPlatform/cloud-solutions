#!/usr/bin/env bash
# Copyright 2026 Google LLC
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

###
### Deploys the Cymbal Shops StyleSearch app
###
### NOTE: you need the latest version of gcloud to deploy this
###

# Deploy the registry
echo "Deploying front end dependencies."
source ./deployment/deploy-registry.sh

# Deploy the front end.
echo "Deploying the front end."
source ./deployment/deploy-frontend.sh

echo "Install complete."
