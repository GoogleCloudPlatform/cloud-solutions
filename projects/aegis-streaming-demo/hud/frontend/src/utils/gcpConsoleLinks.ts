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

export const getGcpConfig = () => {
  const winConfig =
    typeof window !== 'undefined' ? window.__AEGIS_RUNTIME_CONFIG__ : undefined;

  const project =
    winConfig?.project ||
    process.env.GCP_PROJECT ||
    process.env.NEXT_PUBLIC_GCP_PROJECT ||
    '';
  const region =
    winConfig?.region ||
    process.env.GCP_REGION ||
    process.env.NEXT_PUBLIC_GCP_REGION ||
    '';
  const stackType = (
    winConfig?.stackType ||
    process.env.STACK_TYPE ||
    process.env.NEXT_PUBLIC_STACK_TYPE ||
    'oss'
  )
    .toLowerCase()
    .trim();
  const kafkaCluster =
    winConfig?.kafkaCluster || process.env.NEXT_PUBLIC_KAFKA_CLUSTER || '';
  const kafkaTopic =
    winConfig?.kafkaTopic ||
    process.env.NEXT_PUBLIC_KAFKA_TOPIC ||
    'telemetry-raw';
  const pubsubTopic =
    winConfig?.pubsubTopic ||
    process.env.NEXT_PUBLIC_PUBSUB_TOPIC ||
    'telemetry-raw';
  const pubsubSubscription =
    winConfig?.pubsubSubscription ||
    process.env.NEXT_PUBLIC_PUBSUB_SUBSCRIPTION ||
    'telemetry-raw-sub';
  const bigtableInstance =
    winConfig?.bigtableInstance ||
    process.env.NEXT_PUBLIC_BIGTABLE_INSTANCE ||
    '';
  const bigqueryDataset =
    winConfig?.bigqueryDataset ||
    process.env.NEXT_PUBLIC_BIGQUERY_DATASET ||
    '';
  const geapAgentId =
    winConfig?.geapAgentId || process.env.NEXT_PUBLIC_GEAP_AGENT_ID || '';

  return {
    project,
    region,
    stackType,
    kafkaCluster,
    kafkaTopic,
    pubsubTopic,
    pubsubSubscription,
    bigtableInstance,
    bigqueryDataset,
    geapAgentId,
  };
};

export const getConsoleLinks = () => {
  const {
    project,
    region,
    stackType,
    kafkaCluster,
    kafkaTopic,
    pubsubTopic,
    pubsubSubscription,
    bigtableInstance,
    bigqueryDataset,
    geapAgentId,
  } = getGcpConfig();

  const geapDirectUrl = geapAgentId
    ? `https://console.cloud.google.com/agent-platform/runtimes/locations/${region}/agent-engines/${geapAgentId}/dashboard?project=${project}`
    : `https://console.cloud.google.com/agent-platform?project=${project}`;

  const kafkaClusterUrl = `https://console.cloud.google.com/managedkafka/${region}/clusters/${kafkaCluster}?project=${project}`;
  const kafkaTopicUrl = `https://console.cloud.google.com/managedkafka/${region}/clusters/${kafkaCluster}/topics/${kafkaTopic}?project=${project}`;
  const pubsubTopicUrl = `https://console.cloud.google.com/cloudpubsub/topic/detail/${pubsubTopic}?project=${project}`;
  const pubsubSubscriptionUrl = `https://console.cloud.google.com/cloudpubsub/subscription/detail/${pubsubSubscription}?project=${project}`;

  const dataprocBatchesUrl = `https://console.cloud.google.com/dataproc/batches?project=${project}&region=${region}`;
  const dataflowJobsUrl = `https://console.cloud.google.com/dataflow/jobs?project=${project}&region=${region}`;
  const continuousQueriesUrl = `https://console.cloud.google.com/bigquery/continuous-queries?project=${project}`;

  const ingestionConsole =
    stackType === 'oss' ? kafkaClusterUrl : pubsubTopicUrl;
  const ingestionLabel =
    stackType === 'oss' ? 'Kafka Console' : 'Pub/Sub Console';

  let pipelineConsole = dataprocBatchesUrl;
  let pipelineLabel = 'Dataproc Batches';

  if (stackType === 'first_party') {
    pipelineConsole = dataflowJobsUrl;
    pipelineLabel = 'Dataflow Console';
  } else if (stackType === 'low_code') {
    pipelineConsole = continuousQueriesUrl;
    pipelineLabel = 'Continuous Query Studio';
  }

  return {
    stackType,
    kafkaCluster: kafkaClusterUrl,
    kafkaTopic: kafkaTopicUrl,
    pubsubTopic: pubsubTopicUrl,
    pubsubSubscription: pubsubSubscriptionUrl,
    dataprocBatches: dataprocBatchesUrl,
    dataflowJobs: dataflowJobsUrl,
    continuousQueries: continuousQueriesUrl,
    ingestionConsole,
    ingestionLabel,
    pipelineConsole,
    pipelineLabel,
    bigtableOverview: `https://console.cloud.google.com/bigtable/instances/${bigtableInstance}/overview?project=${project}`,
    bigtableTable: `https://console.cloud.google.com/bigtable/instances/${bigtableInstance}/tables/telemetry_metrics/overview?project=${project}`,
    bigqueryDataset: `https://console.cloud.google.com/bigquery?project=${project}&ws=!1m4!1m3!3m2!1s${project}!2s${bigqueryDataset}`,
    bigqueryRcaTable: `https://console.cloud.google.com/bigquery?project=${project}&ws=!1m4!1m3!3m2!1s${project}!2s${bigqueryDataset}!3srca_events`,
    agentServiceRun: `https://console.cloud.google.com/run/detail/${region}/agent-service/metrics?project=${project}`,
    hudBackendRun: `https://console.cloud.google.com/run/detail/${region}/hud-backend/metrics?project=${project}`,
    knowledgeGraph: `https://console.cloud.google.com/dataplex?project=${project}`,
    dataplexLineage: `https://console.cloud.google.com/dataplex?project=${project}`,
    modelArmor: `https://console.cloud.google.com/security/modelarmor?project=${project}`,
    geminiEnterpriseAgentPlatform: geapDirectUrl,
    vertexAiStudio: geapDirectUrl,
  };
};
