/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import {NextResponse} from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  const stackTypeRaw = (
    process.env.STACK_TYPE ||
    process.env.NEXT_PUBLIC_STACK_TYPE ||
    'oss'
  )
    .toLowerCase()
    .trim();

  const stackType =
    stackTypeRaw === 'first_party' || stackTypeRaw === 'low_code'
      ? stackTypeRaw
      : 'oss';

  return NextResponse.json({
    stackType,
    project:
      process.env.GCP_PROJECT || process.env.NEXT_PUBLIC_GCP_PROJECT || '',
    region:
      process.env.GCP_REGION ||
      process.env.NEXT_PUBLIC_GCP_REGION ||
      'us-central1',
    kafkaCluster:
      process.env.KAFKA_CLUSTER_ID ||
      process.env.NEXT_PUBLIC_KAFKA_CLUSTER ||
      '',
    kafkaTopic:
      process.env.KAFKA_TOPIC_ID ||
      process.env.NEXT_PUBLIC_KAFKA_TOPIC ||
      'telemetry-raw',
    pubsubTopic:
      process.env.PUBSUB_TOPIC ||
      process.env.NEXT_PUBLIC_PUBSUB_TOPIC ||
      'telemetry-raw',
    pubsubSubscription:
      process.env.PUBSUB_SUBSCRIPTION ||
      process.env.NEXT_PUBLIC_PUBSUB_SUBSCRIPTION ||
      'telemetry-raw-dataflow-sub',
    bigtableInstance:
      process.env.BIGTABLE_INSTANCE_ID ||
      process.env.NEXT_PUBLIC_BIGTABLE_INSTANCE ||
      'aegis-bigtable',
    bigqueryDataset:
      process.env.BIGQUERY_DATASET_ID ||
      process.env.NEXT_PUBLIC_BIGQUERY_DATASET ||
      'analytics',
    geapAgentId:
      process.env.GEAP_AGENT_ID || process.env.NEXT_PUBLIC_GEAP_AGENT_ID || '',
    dataprocCluster:
      process.env.DATAPROC_CLUSTER_NAME ||
      process.env.NEXT_PUBLIC_DATAPROC_CLUSTER ||
      'aegis-spark-cluster',
  });
}
