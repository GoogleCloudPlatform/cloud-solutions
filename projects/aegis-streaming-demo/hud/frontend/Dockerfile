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

# Step 1: Base image
FROM node:20-alpine AS base

# Step 2: Install dependencies
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Step 3: Builder
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_GCP_PROJECT
ARG NEXT_PUBLIC_GCP_REGION
ARG NEXT_PUBLIC_KAFKA_CLUSTER
ARG NEXT_PUBLIC_KAFKA_TOPIC
ARG NEXT_PUBLIC_BIGTABLE_INSTANCE
ARG NEXT_PUBLIC_BIGQUERY_DATASET
ARG NEXT_PUBLIC_GEAP_AGENT_ID
ENV NEXT_PUBLIC_GCP_PROJECT=${NEXT_PUBLIC_GCP_PROJECT}
ENV NEXT_PUBLIC_GCP_REGION=${NEXT_PUBLIC_GCP_REGION}
ENV NEXT_PUBLIC_KAFKA_CLUSTER=${NEXT_PUBLIC_KAFKA_CLUSTER}
ENV NEXT_PUBLIC_KAFKA_TOPIC=${NEXT_PUBLIC_KAFKA_TOPIC}
ENV NEXT_PUBLIC_BIGTABLE_INSTANCE=${NEXT_PUBLIC_BIGTABLE_INSTANCE}
ENV NEXT_PUBLIC_BIGQUERY_DATASET=${NEXT_PUBLIC_BIGQUERY_DATASET}
ENV NEXT_PUBLIC_GEAP_AGENT_ID=${NEXT_PUBLIC_GEAP_AGENT_ID}
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Step 4: Runner
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=8080
ENV HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Automatically leverage output traces to reduce image size
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 8080

CMD ["node", "server.js"]
