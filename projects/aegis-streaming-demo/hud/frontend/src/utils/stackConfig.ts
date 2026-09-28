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

export type StackType = 'oss' | 'first_party' | 'low_code';

export interface StackConfig {
  stackType: StackType;
  stackBadgeTitle: string;
  stackTechFlow: string[];
  stackTheme: 'emerald' | 'blue' | 'purple';

  // Ingestion Plane Terminology
  ingestionName: string;
  ingestionShort: string;
  ingestionTopic: string;
  ingestionRateLabel: string;
  ingestionPausedLabel: string;
  generatorTitle: string;
  generatorShort: string;
  generatorDescription: string;

  // Stream Compute Plane Terminology
  pipelineName: string;
  pipelineShort: string;
  pipelineEngine: string;
  pipelineEngineBadge: string;
  pipelineStoppedLabel: string;
  pipelineButtonStart: string;
  pipelineButtonRetry: string;
  pipelineButtonStop: string;
  pipelineInitTitle: string;
  pipelineInitDesc: string;
  pipelineRunningDesc: string;
  pipelineStoppedDesc: string;
  pipelineErrorDesc: string;
  pipelineDescription: string;

  // Quick Start & UI Guidance
  quickStartStep1: string;
  quickStartStep2: string;
  lockBannerText: string;
  copilotEmptyState: string;
  infraSummary: string;

  // Step Trace & Module 4 Pipeline Flow
  module4Step1Subtitle: string;
  module4Step1Desc: string;
  module4Step1Tech: string;
  module4Step3Subtitle: string;
  module4Step3Desc: string;
  module4Step3Tech: string;

  // Toast Notifications
  toastAnomalyEmitted: string;
  toastMitigationResumed: string;
  toastPipelineSync: string;
  dataprocCluster: string;
}

declare global {
  interface Window {
    __AEGIS_RUNTIME_CONFIG__?: {
      stackType?: string;
      project?: string;
      region?: string;
      kafkaCluster?: string;
      kafkaTopic?: string;
      pubsubTopic?: string;
      pubsubSubscription?: string;
      bigtableInstance?: string;
      bigqueryDataset?: string;
      geapAgentId?: string;
      dataprocCluster?: string;
    };
  }
}

export const getStackConfig = (): StackConfig => {
  const winConfig =
    typeof window !== 'undefined' ? window.__AEGIS_RUNTIME_CONFIG__ : undefined;

  const rawType = (
    winConfig?.stackType ||
    process.env.STACK_TYPE ||
    process.env.NEXT_PUBLIC_STACK_TYPE ||
    'oss'
  )
    .toLowerCase()
    .trim();

  const dataprocCluster =
    winConfig?.dataprocCluster ||
    process.env.DATAPROC_CLUSTER_NAME ||
    process.env.NEXT_PUBLIC_DATAPROC_CLUSTER ||
    'aegis-spark-cluster';

  const stackType: StackType =
    rawType === 'first_party' || rawType === 'low_code' ? rawType : 'oss';

  if (stackType === 'first_party') {
    return {
      stackType: 'first_party',
      stackBadgeTitle: '1ST-PARTY MANAGED STREAMING',
      stackTechFlow: [
        'Cloud Pub/Sub',
        'Cloud Dataflow',
        'Bigtable & BQ',
        'GEAP',
      ],
      stackTheme: 'blue',
      dataprocCluster,

      ingestionName: 'Google Cloud Pub/Sub',
      ingestionShort: 'Pub/Sub',
      ingestionTopic: 'telemetry-raw',
      ingestionRateLabel: 'Pub/Sub Message Rate (5m)',
      ingestionPausedLabel: 'PUB/SUB PAUSED',
      generatorTitle: '1. CDC Pub/Sub Stream Generator',
      generatorShort: 'Pub/Sub CDC Generator',
      generatorDescription:
        'Continuously produces simulated IIoT industrial machinery sensor payloads and pushes authenticated messages directly into Google Cloud Pub/Sub (telemetry-raw).',

      pipelineName: 'Cloud Dataflow Streaming Pipeline',
      pipelineShort: 'Cloud Dataflow',
      pipelineEngine: 'Cloud Dataflow (Apache Beam engine)',
      pipelineEngineBadge: 'Apache Beam',
      pipelineStoppedLabel: 'DATAFLOW STOPPED',
      pipelineButtonStart: 'START DATAFLOW PIPELINE',
      pipelineButtonRetry: 'RETRY DATAFLOW PIPELINE',
      pipelineButtonStop: 'STOP DATAFLOW PIPELINE',
      pipelineInitTitle: 'PROVISIONING DATAFLOW WORKERS',
      pipelineInitDesc:
        'Allocating Dataflow streaming worker instances, establishing Pub/Sub subscription reader, and initializing Apache Beam execution graph (~60–90s)...',
      pipelineRunningDesc:
        'Ingestion active: Pub/Sub (telemetry-raw) ➔ Dataflow Beam ➔ Bigtable & BigQuery',
      pipelineStoppedDesc:
        'Pipeline stopped. Click START DATAFLOW PIPELINE to launch streaming job.',
      pipelineErrorDesc:
        'Cloud Dataflow job execution failed. Check Google Cloud resource quotas or configuration.',
      pipelineDescription:
        'Cloud Dataflow Apache Beam streaming job. Consumes from Google Cloud Pub/Sub and computes 10s fixed tumbling windows directly into Cloud Bigtable & BigQuery.',

      quickStartStep1:
        'Click START CDC SIMULATOR below to stream synthetic IIoT telemetry into Cloud Pub/Sub.',
      quickStartStep2:
        'Verify the Cloud Dataflow Streaming Pipeline is RUNNING with Apache Beam.',
      lockBannerText:
        'Demo locked: Start Pub/Sub generator & Dataflow pipeline above to enable anomaly injection',
      copilotEmptyState:
        'Start the Pub/Sub generator and Dataflow streaming pipeline above to unlock the live operational grid and Co-Pilot.',
      infraSummary: 'Bigtable + Dataflow (Apache Beam) + GEAP + BigQuery',

      module4Step1Subtitle: 'Cloud Pub/Sub → Cloud Dataflow (Apache Beam)',
      module4Step1Desc:
        'Pub/Sub telemetry streams are ingested by Cloud Dataflow (Apache Beam) with 10s fixed tumbling windows and written continuously to a dual sink: Cloud Bigtable (operational state) & BigQuery (analytical history).',
      module4Step1Tech: 'Cloud Pub/Sub • Cloud Dataflow • Bigtable • BigQuery',
      module4Step3Subtitle: 'Dataflow Anomaly → Gemini 2.5 Flash RCA',
      module4Step3Desc:
        'When an anomaly is detected in Dataflow tumbling windows, the Anomaly Mitigation Agent is invoked. Powered by Gemini 2.5 Flash on GEAP, the agent formulates a structured Root Cause Analysis & remediation plan for the operator.',
      module4Step3Tech: 'Dataflow Window Hook • Gemini 2.5 Flash • GEAP',

      toastAnomalyEmitted:
        'Critical telemetry emitted to Cloud Pub/Sub. Cloud Dataflow streaming ETL will detect the anomaly and update Bigtable.',
      toastMitigationResumed:
        "Sensor simulator resumed emitting healthy telemetry payloads to Pub/Sub topic 'telemetry-raw'.",
      toastPipelineSync:
        'Dataflow Streaming (Apache Beam) dual-sink synchronized to Bigtable and BigQuery.',
    };
  }

  if (stackType === 'low_code') {
    return {
      stackType: 'low_code',
      stackBadgeTitle: 'LOW-CODE SERVERLESS',
      stackTechFlow: [
        'Pub/Sub Direct',
        'BQ Continuous SQL',
        'Bigtable & BQ',
        'GEAP',
      ],
      stackTheme: 'purple',
      dataprocCluster,

      ingestionName: 'Google Cloud Pub/Sub',
      ingestionShort: 'Pub/Sub',
      ingestionTopic: 'telemetry-raw',
      ingestionRateLabel: 'Pub/Sub Message Rate (5m)',
      ingestionPausedLabel: 'PUB/SUB PAUSED',
      generatorTitle: '1. CDC Pub/Sub Stream Generator',
      generatorShort: 'Pub/Sub CDC Generator',
      generatorDescription:
        'Continuously produces simulated IIoT industrial machinery sensor payloads and pushes authenticated messages directly into Google Cloud Pub/Sub (telemetry-raw).',

      pipelineName: 'BigQuery Continuous Queries Engine',
      pipelineShort: 'BigQuery Continuous Query',
      pipelineEngine: 'BigQuery Continuous Query (SQL engine)',
      pipelineEngineBadge: 'Continuous SQL',
      pipelineStoppedLabel: 'BQ CQ STOPPED',
      pipelineButtonStart: 'START CONTINUOUS QUERY',
      pipelineButtonRetry: 'RETRY CONTINUOUS QUERY',
      pipelineButtonStop: 'STOP CONTINUOUS QUERY',
      pipelineInitTitle: 'INITIALIZING CONTINUOUS QUERY',
      pipelineInitDesc:
        'Starting continuous SQL execution slot allocation, connecting Pub/Sub stream, and syncing tumbling window state...',
      pipelineRunningDesc:
        'Ingestion active: Pub/Sub (telemetry-raw) ➔ BigQuery Continuous Queries ➔ Bigtable & BigQuery',
      pipelineStoppedDesc:
        'Pipeline stopped. Click START CONTINUOUS QUERY to launch continuous SQL.',
      pipelineErrorDesc:
        'BigQuery Continuous Query execution failed. Check Google Cloud resource quotas or configuration.',
      pipelineDescription:
        'BigQuery Continuous Queries serverless SQL engine. Continuously processes streaming Pub/Sub events with 10s SQL tumbling windows directly into Cloud Bigtable & BigQuery.',

      quickStartStep1:
        'Click START CDC SIMULATOR below to stream synthetic IIoT telemetry into Cloud Pub/Sub.',
      quickStartStep2:
        'Verify the BigQuery Continuous Queries Engine is RUNNING with continuous SQL.',
      lockBannerText:
        'Demo locked: Start Pub/Sub generator & Continuous Query above to enable anomaly injection',
      copilotEmptyState:
        'Start the Pub/Sub generator and Continuous Query engine above to unlock the live operational grid and Co-Pilot.',
      infraSummary: 'Bigtable + Continuous Queries + GEAP + BigQuery',

      module4Step1Subtitle: 'Cloud Pub/Sub → BigQuery Continuous Queries',
      module4Step1Desc:
        'Pub/Sub telemetry streams are processed serverless using BigQuery Continuous Queries and direct sinks into Cloud Bigtable and BigQuery analytics.',
      module4Step1Tech:
        'Cloud Pub/Sub • BigQuery Continuous Queries • Bigtable',
      module4Step3Subtitle: 'Continuous SQL Anomaly → Gemini 2.5 Flash RCA',
      module4Step3Desc:
        'When an anomaly is flagged by BigQuery Continuous Query SQL windows, the Anomaly Mitigation Agent is invoked. Powered by Gemini 2.5 Flash on GEAP, the agent formulates a structured Root Cause Analysis & remediation plan for the operator.',
      module4Step3Tech: 'BigQuery CQ Hook • Gemini 2.5 Flash • GEAP',

      toastAnomalyEmitted:
        'Critical telemetry emitted to Cloud Pub/Sub. BigQuery Continuous Queries will detect the anomaly and update Bigtable.',
      toastMitigationResumed:
        "Sensor simulator resumed emitting healthy telemetry payloads to Pub/Sub topic 'telemetry-raw'.",
      toastPipelineSync:
        'BigQuery Continuous Queries dual-sink synchronized to Bigtable and BigQuery.',
    };
  }

  // Default: OSS Stack
  return {
    stackType: 'oss',
    stackBadgeTitle: 'OSS / DIGITAL NATIVE',
    stackTechFlow: ['Managed Kafka', 'Dataproc Spark', 'Bigtable & BQ', 'GEAP'],
    stackTheme: 'emerald',
    dataprocCluster,

    ingestionName: 'Managed Apache Kafka',
    ingestionShort: 'Kafka',
    ingestionTopic: 'telemetry-raw',
    ingestionRateLabel: 'Kafka Message Rate (5m)',
    ingestionPausedLabel: 'KAFKA PAUSED',
    generatorTitle: '1. CDC Kafka Stream Generator',
    generatorShort: 'Kafka CDC Generator',
    generatorDescription:
      'Continuously produces simulated IIoT industrial machinery sensor payloads and pushes authenticated OAuth messages directly into Google Cloud Managed Kafka (telemetry-raw).',

    pipelineName: 'Dataproc Standard Spark Streaming',
    pipelineShort: 'Managed Spark',
    pipelineEngine: 'Dataproc Standard (Vectorized Spark)',
    pipelineEngineBadge: 'Vectorized Spark',
    pipelineStoppedLabel: 'SPARK STOPPED',
    pipelineButtonStart: 'START SPARK PIPELINE',
    pipelineButtonRetry: 'RETRY SPARK PIPELINE',
    pipelineButtonStop: 'STOP SPARK PIPELINE',
    pipelineInitTitle: 'SUBMITTING SPARK STREAMING JOB',
    pipelineInitDesc: `Submitting PySpark Structured Streaming job to warm Dataproc Standard Spark cluster (${dataprocCluster}) (~5–10s)...`,
    pipelineRunningDesc: `Auto-started by Terraform on warm cluster (${dataprocCluster}): Kafka (telemetry-raw) ➔ Vectorized Spark Engine ➔ Bigtable & BigQuery`,
    pipelineStoppedDesc: `Streaming job stopped (warm cluster ${dataprocCluster} remains active). Click START SPARK PIPELINE to re-launch in ~5–10s.`,
    pipelineErrorDesc: `Spark streaming job execution failed on ${dataprocCluster}. Check Dataproc cluster logs or configuration.`,
    pipelineDescription: `Dataproc Standard PySpark Structured Streaming job on warm vectorized Spark cluster (${dataprocCluster}). Pre-provisioned and auto-started by Terraform. Consumes from Managed Kafka and computes 10s tumbling windows directly into Cloud Bigtable & BigQuery.`,

    quickStartStep1:
      'Click START CDC SIMULATOR below to stream synthetic IIoT telemetry into Managed Kafka.',
    quickStartStep2: `Verify the Dataproc Standard Spark Streaming Job is already RUNNING (pre-warmed and auto-started by Terraform on cluster ${dataprocCluster}, or click START SPARK PIPELINE to restart in ~5–10s).`,
    lockBannerText:
      'Demo locked: Start Kafka generator & Spark pipeline above to enable anomaly injection',
    copilotEmptyState:
      'Start the Kafka generator and verify the Spark streaming job is running above to unlock the live operational grid and Co-Pilot.',
    infraSummary:
      'Bigtable + Dataproc Standard (Vectorized Spark) + GEAP + BigQuery',

    module4Step1Subtitle:
      'Managed Kafka → Dataproc Standard Spark (Vectorized)',
    module4Step1Desc: `Kafka sensor events are ingested by PySpark Structured Streaming on a warm Dataproc Standard cluster (${dataprocCluster}) with vectorized Spark execution and written continuously to Cloud Bigtable & BigQuery.`,
    module4Step1Tech:
      'Managed Kafka • Dataproc Standard Spark • Bigtable • BigQuery',
    module4Step3Subtitle: 'Spark Detection → Gemini 2.5 Flash RCA',
    module4Step3Desc:
      'When an anomaly is detected in Spark tumbling windows, the Anomaly Mitigation Agent is invoked. Powered by Gemini 2.5 Flash on GEAP, the agent formulates a structured Root Cause Analysis & remediation plan for the operator.',
    module4Step3Tech: 'Dataproc Anomaly Hook • Gemini 2.5 Flash • GEAP',

    toastAnomalyEmitted:
      'Critical telemetry emitted to Managed Kafka. Dataproc Standard Spark (Vectorized Spark) will detect the anomaly and update Bigtable.',
    toastMitigationResumed:
      "Sensor simulator resumed emitting healthy telemetry payloads to Kafka topic 'telemetry-raw'.",
    toastPipelineSync:
      'Dataproc Standard Spark (Vectorized Spark) dual-sink synchronized to Bigtable and BigQuery.',
  };
};
