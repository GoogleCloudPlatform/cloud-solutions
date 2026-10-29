-- Copyright 2026 Google LLC
--
-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

CREATE TABLE IF NOT EXISTS `soa_action_lineage.agent_sessions` (
  trace_id STRING NOT NULL,
  customer_id INT64 NOT NULL,
  target_order_id INT64,
  user_prompt STRING NOT NULL,
  started_at TIMESTAMP NOT NULL,
  PRIMARY KEY (trace_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `soa_action_lineage.workflow_nodes` (
  node_exec_id STRING NOT NULL,
  trace_id STRING NOT NULL,
  node_name STRING NOT NULL,
  step_order INT64 NOT NULL,
  latency_ms FLOAT64 NOT NULL,
  executed_at TIMESTAMP NOT NULL,
  PRIMARY KEY (node_exec_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `soa_action_lineage.policy_evaluations` (
  eval_id STRING NOT NULL,
  node_exec_id STRING NOT NULL,
  trace_id STRING NOT NULL,
  catalog_term_id STRING NOT NULL,
  policy_id STRING NOT NULL,
  policy_name STRING NOT NULL,
  observed_refunds_100d INT64 NOT NULL,
  max_refunds_100d INT64 NOT NULL,
  observed_order_age_days INT64,
  return_window_days INT64 NOT NULL,
  evaluation_result STRING NOT NULL,
  evaluated_at TIMESTAMP NOT NULL,
  PRIMARY KEY (eval_id) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `soa_action_lineage.agent_actions` (
  action_id STRING NOT NULL,
  eval_id STRING NOT NULL,
  trace_id STRING NOT NULL,
  action_type STRING NOT NULL,
  decision_status STRING NOT NULL,
  rejection_reason STRING,
  created_at TIMESTAMP NOT NULL,
  PRIMARY KEY (action_id) NOT ENFORCED
);

CREATE OR REPLACE PROPERTY GRAPH `soa_action_lineage.ActionLineageGraph`
  NODE TABLES (
    `soa_action_lineage.agent_sessions` AS AgentSession KEY (trace_id),
    `soa_action_lineage.workflow_nodes` AS WorkflowNode KEY (node_exec_id),
    `soa_action_lineage.policy_evaluations` AS PolicyEvaluation KEY (eval_id),
    `soa_action_lineage.agent_actions` AS AgentAction KEY (action_id)
  )
  EDGE TABLES (
    `soa_action_lineage.workflow_nodes` AS executed_node
      KEY (node_exec_id)
      SOURCE KEY (trace_id) REFERENCES AgentSession (trace_id)
      DESTINATION KEY (node_exec_id) REFERENCES WorkflowNode (node_exec_id),
    `soa_action_lineage.policy_evaluations` AS evaluated_policy
      KEY (eval_id)
      SOURCE KEY (node_exec_id) REFERENCES WorkflowNode (node_exec_id)
      DESTINATION KEY (eval_id) REFERENCES PolicyEvaluation (eval_id),
    `soa_action_lineage.agent_actions` AS triggered_action
      KEY (action_id)
      SOURCE KEY (eval_id) REFERENCES PolicyEvaluation (eval_id)
      DESTINATION KEY (action_id) REFERENCES AgentAction (action_id)
  );
