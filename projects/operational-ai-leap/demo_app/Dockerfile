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

##
## Stage 1: Build the API
##
FROM node:22-alpine AS api-build

WORKDIR /src
COPY ./api .

RUN npm ci && npx tsc --outDir /dist

##
## Stage 2: Build the UI
##
FROM node:22-alpine AS ui-build

WORKDIR /app
COPY ./ui .

RUN npm ci --legacy-peer-deps && npm run build -- --output-path=/dist  # Remove space after --output-path

##
## Stage 3: Build Runtime
##
FROM node:22-alpine AS runtime

WORKDIR /app

# Copy build artifacts from the api-build stage
COPY --from=api-build /dist .
COPY --from=api-build /src/node_modules ./node_modules

# Copy build artifacts from the ui-build stage
COPY --from=ui-build /dist ./ui/dist/cymbal-shops-ui

EXPOSE 8080

CMD ["node", "index.js"]
