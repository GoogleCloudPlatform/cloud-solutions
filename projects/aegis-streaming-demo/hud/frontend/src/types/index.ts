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

export interface AssetState {
  asset_id: string;
  cpu_utilization: number;
  temperature_c: number;
  pressure_psi: number;
  memory_utilization_pct: number;
  status: 'OK' | 'WARNING' | 'CRITICAL' | 'EXPIRED' | 'STALE';
  raw_status?: string;
  is_anomaly: boolean;
  is_stale?: boolean;
  data_age_seconds?: number;
  timestamp: string;
}

export interface TelemetryStreamPayload {
  timestamp: string;
  assets: AssetState[];
}

export interface TokenomicsMetrics {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number;
  cost_usd: number;
  prevented_downtime_usd: number;
  roi_multiplier: number;
}

export interface MitigationResponse {
  incident_id: string;
  asset_id: string;
  timestamp: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  root_cause_summary: string;
  chain_of_thought: string;
  recommended_action: string;
  mitigation_steps: string[];
  status: string;
  tokenomics: TokenomicsMetrics;
}

export interface ExecutionStepTrace {
  step: number;
  title: string;
  detail: string;
  status: 'SUCCESS' | 'WARNING' | 'INFO';
  timestamp: string;
}

export interface AgentApprovalResponse {
  success: boolean;
  incident_id: string;
  asset_id: string;
  execution_mode: string;
  execution_target: string;
  tool_executed: string;
  tool_status: string;
  action_taken: string;
  actuator_response?: Record<string, unknown>;
  bigquery_logged: boolean;
  steps: ExecutionStepTrace[];
  timestamp: string;
}

export interface ArchitectureComponent {
  id: string;
  title: string;
  category:
    | 'Ingestion'
    | 'Compute'
    | 'Storage'
    | 'Agent'
    | 'Security & Governance';
  tech: string;
  description: string;
  status: 'Healthy' | 'Active' | 'Optimal' | 'Guarded';
  metrics?: string;
  iconName: string;
  consoleLink?: string;
  consoleLinkLabel?: string;
}

export interface StreamStatusInfo {
  status: string;
  running: boolean;
  target_rate_msgs_per_sec?: number;
  total_messages_last_5m: number;
  rate_msgs_per_sec_5m: number;
  rate_formatted: string;
  active_anomalies: string[];
  assets_count: number;
  timestamp: string;
}
