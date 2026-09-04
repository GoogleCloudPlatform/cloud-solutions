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
  const project =
    process.env.NEXT_PUBLIC_GCP_PROJECT || process.env.GCP_PROJECT || '';
  const region = process.env.NEXT_PUBLIC_GCP_REGION || '';
  const kafkaCluster = process.env.NEXT_PUBLIC_KAFKA_CLUSTER || '';
  const kafkaTopic = process.env.NEXT_PUBLIC_KAFKA_TOPIC || '';
  const bigtableInstance = process.env.NEXT_PUBLIC_BIGTABLE_INSTANCE || '';
  const bigqueryDataset = process.env.NEXT_PUBLIC_BIGQUERY_DATASET || '';
  const geapAgentId = process.env.NEXT_PUBLIC_GEAP_AGENT_ID || '';

  return {
    project,
    region,
    kafkaCluster,
    kafkaTopic,
    bigtableInstance,
    bigqueryDataset,
    geapAgentId,
  };
};

export const getConsoleLinks = () => {
  const {
    project,
    region,
    kafkaCluster,
    kafkaTopic,
    bigtableInstance,
    bigqueryDataset,
    geapAgentId,
  } = getGcpConfig();

  const geapDirectUrl = geapAgentId
    ? `https://console.cloud.google.com/agent-platform/runtimes/locations/${region}/agent-engines/${geapAgentId}/dashboard?project=${project}`
    : `https://console.cloud.google.com/agent-platform?project=${project}`;

  return {
    kafkaCluster: `https://console.cloud.google.com/managedkafka/${region}/clusters/${kafkaCluster}?project=${project}`,
    kafkaTopic: `https://console.cloud.google.com/managedkafka/${region}/clusters/${kafkaCluster}/topics/${kafkaTopic}?project=${project}`,
    dataprocBatches: `https://console.cloud.google.com/dataproc/batches?project=${project}&region=${region}`,
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
