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

'use client';

import React, { useState } from 'react';
import { AssetState, MitigationResponse, AgentApprovalResponse } from '../types';
import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  AlertTriangle,
  DollarSign,
  ShieldAlert,
  TrendingUp,
  Clock,
  Coins,
  ShieldCheck,
  RefreshCw,
  Lock,
  Server,
  Layers,
  AlertCircle
} from 'lucide-react';
import { isDataStale, getDataAgeInfo } from '../utils/telemetryUtils';

interface AgentCoPilotProps {
  selectedAsset: AssetState | null;
  mitigationData: MitigationResponse | null;
  isLoadingMitigation: boolean;
  onExecuteMitigation: (request: AssetState) => Promise<void>;
  onApproveAndApply: (assetId: string) => Promise<AgentApprovalResponse | void>;
  isDemoActive?: boolean;
}

export const AgentCoPilot: React.FC<AgentCoPilotProps> = ({
  selectedAsset,
  mitigationData,
  isLoadingMitigation,
  onExecuteMitigation,
  onApproveAndApply,
  isDemoActive = true,
}) => {
  const [isApplying, setIsApplying] = useState(false);
  const [appliedSuccess, setAppliedSuccess] = useState(false);
  const [approvalDetails, setApprovalDetails] = useState<AgentApprovalResponse | null>(null);

  React.useEffect(() => {
    if (selectedAsset && (selectedAsset.status === 'CRITICAL' || selectedAsset.is_anomaly) && mitigationData?.status !== 'RESOLVED') {
      setAppliedSuccess(false);
      setApprovalDetails(null);
    }
  }, [selectedAsset?.asset_id, selectedAsset?.status, selectedAsset?.is_anomaly, mitigationData?.status]);

  const handleApprove = async () => {
    if (!mitigationData || !isDemoActive) return;
    setIsApplying(true);
    try {
      const res = await onApproveAndApply(mitigationData.asset_id);
      if (res && typeof res === 'object' && res.success) {
        setApprovalDetails(res);
      }
      setAppliedSuccess(true);
    } catch (e) {
      console.error('Failed approving mitigation:', e);
    } finally {
      setIsApplying(false);
    }
  };

  const effectiveAsset = selectedAsset || (mitigationData ? {
    asset_id: mitigationData.asset_id,
    timestamp: mitigationData.timestamp || new Date().toISOString(),
    status: mitigationData.status === 'RESOLVED' ? 'OK' : (mitigationData.severity === 'CRITICAL' ? 'CRITICAL' : 'WARNING'),
    cpu_utilization: mitigationData.status === 'RESOLVED' ? 32.0 : 95.0,
    temperature_c: mitigationData.status === 'RESOLVED' ? 50.0 : 94.0,
    pressure_psi: mitigationData.status === 'RESOLVED' ? 35.0 : 155.0,
    memory_utilization_pct: mitigationData.status === 'RESOLVED' ? 40.0 : 88.0,
    is_anomaly: mitigationData.status !== 'RESOLVED',
  } as AssetState : null);

  const isMitigated =
    appliedSuccess || mitigationData?.status === 'RESOLVED';

  return (
    <section className={`w-full glass-panel rounded-2xl p-6 border transition-all duration-300 shadow-xl ${
      !isDemoActive ? 'border-[#334155]/60 bg-[#060e20]/90' : 'border-[#334155]'
    }`}>
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-[#334155]">
        <div>
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-[#adc7ff]" />
            <h2 className="text-lg font-headline font-bold text-white uppercase tracking-wide">
              Module 4b: Agent Execution Co-Pilot
            </h2>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider border flex items-center gap-1 ${
              isDemoActive
                ? 'bg-[#1a73e8]/20 text-[#adc7ff] border-[#1a73e8]/50'
                : 'bg-[#2d3449] text-[#8b909f] border-[#334155]'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isDemoActive ? 'bg-[#6ddd81] animate-pulse' : 'bg-[#8b909f]'}`} />
              {isDemoActive ? 'GEMINI 2.5 FLASH • CLOSED-LOOP' : 'AGENT CONTROLS LOCKED'}
            </span>
          </div>
          <p className="text-xs text-[#c1c6d6] font-sans mt-1">
            Gemini Enterprise Agent Platform (GEAP) Root Cause Analysis, Chain-of-Thought &amp; Autonomous Remediation Tools
          </p>
        </div>

        {mitigationData && (
          <div className="flex items-center gap-3">
            {isMitigated ? (
              <span className="px-3 py-1 rounded text-xs font-mono uppercase tracking-widest font-bold flex items-center gap-1.5 border bg-[#30a550]/20 text-[#6ddd81] border-[#30a550]">
                <ShieldCheck className="w-3.5 h-3.5" /> STATUS: RESOLVED • NOMINAL
              </span>
            ) : (
              <span className={`px-3 py-1 rounded text-xs font-mono uppercase tracking-widest font-bold flex items-center gap-1.5 border ${
                mitigationData.severity === 'CRITICAL'
                  ? 'bg-[#93000a] text-[#ffdad6] border-[#D93025] animate-pulse shadow-[0_0_12px_rgba(217,48,37,0.5)]'
                  : 'bg-[#FBBC04]/20 text-[#FBBC04] border-[#FBBC04]'
              }`}>
                <AlertTriangle className="w-3.5 h-3.5" /> SEVERITY: {mitigationData.severity}
              </span>
            )}
          </div>
        )}
      </div>

      {!effectiveAsset && !mitigationData && !isLoadingMitigation ? (
        <div className="mt-8 p-12 rounded-xl bg-[#131b2e]/50 border border-dashed border-[#334155] text-center flex flex-col items-center justify-center">
          <BrainCircuit className="w-12 h-12 text-[#8b909f] mb-3" />
          <h3 className="text-base font-headline font-bold text-[#dae2fd]">No Asset Selected</h3>
          <p className="text-xs text-[#c1c6d6] max-w-md mt-1 font-sans">
            {!isDemoActive
              ? 'Start the Kafka generator and Spark streaming job above to unlock the live operational grid and Co-Pilot.'
              : 'Select any asset tile in the Live Telemetry Grid and click "RUN GEMINI 2.5 RCA" to generate Root Cause Analysis and review the remediation plan.'}
          </p>
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: RCA & Chain of Thought */}
          <div className="lg:col-span-2 space-y-6">
            {/* Target Asset Banner */}
            {effectiveAsset && (() => {
              const ageInfo = getDataAgeInfo(effectiveAsset.timestamp);
              const isStale = ageInfo.isStale;

              return (
                <div className="space-y-3">
                  {isStale && (
                    <div className="p-3 rounded-lg bg-[#f59e0b]/15 border border-[#f59e0b]/50 text-xs font-sans text-[#dae2fd] flex items-start gap-2.5">
                      <AlertCircle className="w-4 h-4 text-[#f59e0b] shrink-0 mt-0.5" />
                      <div>
                        <strong className="text-[#fbbf24] font-mono uppercase">Telemetry Expired (&gt;60m):</strong>{' '}
                        <span>Selected asset data is too old. Activate the demonstration stream in Module 2 to ingest fresh sensor telemetry.</span>
                      </div>
                    </div>
                  )}

                  <div className="p-4 rounded-xl bg-[#131b2e]/90 border border-[#334155] flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#8b909f]">Target Asset</span>
                      <div className="text-base font-mono font-bold text-white flex items-center gap-2 mt-0.5">
                        <span>{effectiveAsset.asset_id}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded uppercase tracking-widest font-bold ${
                          isMitigated
                            ? 'bg-[#30a550]/20 text-[#6ddd81] border border-[#30a550]'
                            : isStale
                            ? 'bg-[#1e293b] text-[#94a3b8] border border-[#475569]/60'
                            : !isDemoActive
                            ? 'bg-[#1e293b] text-[#64748b] border border-[#334155]'
                            : effectiveAsset.status === 'CRITICAL'
                            ? 'bg-[#D93025] text-white animate-pulse'
                            : 'bg-[#30a550]/20 text-[#6ddd81] border border-[#30a550]'
                        }`}>
                          {isMitigated ? 'NOMINAL' : isStale ? 'EXPIRED' : effectiveAsset.status}
                        </span>
                        <span className="text-[11px] font-mono font-normal flex items-center gap-1 ml-2">
                          <Clock className={`w-3 h-3 ${isStale && !isMitigated ? 'text-[#f59e0b]' : 'text-[#adc7ff]'}`} />
                          <span className={isStale && !isMitigated ? 'text-[#f59e0b]' : 'text-[#8b909f]'}>
                            {ageInfo.relativeText}{isStale && !isMitigated ? ' (stale)' : ''}
                          </span>
                        </span>
                      </div>
                    </div>

                    <button
                      disabled={isLoadingMitigation || !isDemoActive || (isStale && !isMitigated) || !effectiveAsset}
                      onClick={() => {
                        if (!isDemoActive || (isStale && !isMitigated) || !effectiveAsset) return;
                        onExecuteMitigation(effectiveAsset);
                      }}
                      className={`px-4 py-2.5 rounded font-mono text-xs uppercase tracking-widest font-bold flex items-center gap-2 transition-all border ${
                        isStale && !isMitigated
                          ? 'bg-[#1e293b] border-[#475569]/40 text-[#64748b] cursor-not-allowed opacity-50 shadow-none'
                          : !isDemoActive
                          ? 'bg-[#1e293b] border-[#475569]/40 text-[#64748b] cursor-not-allowed opacity-50 shadow-none'
                          : 'bg-[#1a73e8] hover:bg-[#005bc0] text-white border-[#adc7ff]/40 shadow-lg shadow-[#1a73e8]/30 disabled:opacity-50'
                      }`}
                      title={isStale && !isMitigated ? 'Data too old (>60m). Activate demo stream to run live RCA.' : !isDemoActive ? 'Demo locked: Start pipeline above to enable' : 'Run Gemini 2.5 Flash Root Cause Analysis'}
                    >
                      {isLoadingMitigation ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (isStale && !isMitigated) || !isDemoActive ? (
                        <Lock className="w-4 h-4 text-[#64748b]" />
                      ) : (
                        <BrainCircuit className="w-4 h-4" />
                      )}
                      <span>{isStale && !isMitigated ? 'DATA TOO OLD' : 'RUN GEMINI 2.5 RCA'}</span>
                    </button>
                  </div>
                </div>
              );
            })()}

            {/* Root Cause Analysis Summary */}
            {mitigationData ? (
              <div className="p-5 rounded-xl bg-[#131b2e]/90 border border-[#1a73e8]/50 space-y-4">
                <div className="flex items-center gap-2 mb-1">
                  <ShieldAlert className="w-4 h-4 text-[#adc7ff]" />
                  <h3 className="text-sm font-headline font-bold text-white uppercase tracking-wide">
                    Root Cause Analysis Summary
                  </h3>
                </div>
                <p className="text-xs text-[#dae2fd] leading-relaxed font-sans">
                  {mitigationData.root_cause_summary}
                </p>

                {/* Chain of Thought Reasoning Box */}
                <div className="p-4 rounded-xl bg-[#060e20] border border-[#334155]">
                  <span className="text-[10px] font-mono text-[#adc7ff] uppercase tracking-widest font-bold block mb-2">
                    Gemini 2.5 Flash — Chain-of-Thought Diagnostic Trail
                  </span>
                  <pre className="text-xs font-mono text-[#dae2fd] whitespace-pre-wrap leading-relaxed">
                    {mitigationData.chain_of_thought}
                  </pre>
                </div>

                {/* Ordered Remediation Steps */}
                <div>
                  <span className="text-[10px] font-mono text-[#8b909f] uppercase tracking-widest font-bold block mb-2">
                    Autonomous Remediation Plan:
                  </span>
                  <div className="space-y-2">
                    {mitigationData.mitigation_steps.map((step, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg bg-[#060e20] border border-[#334155]/60 flex items-start gap-2.5 text-xs text-[#dae2fd] font-mono"
                      >
                        <span className="w-5 h-5 rounded-full bg-[#1a73e8]/20 border border-[#1a73e8] text-[#adc7ff] flex items-center justify-center text-[10px] font-bold shrink-0">
                          {idx + 1}
                        </span>
                        <span className="mt-0.5">{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : isLoadingMitigation ? (
              <div className="p-12 rounded-xl bg-[#131b2e]/90 border border-[#1a73e8]/30 flex flex-col items-center justify-center text-center">
                <RefreshCw className="w-8 h-8 text-[#adc7ff] animate-spin mb-3" />
                <h4 className="text-sm font-mono font-bold text-white">
                  Gemini 2.5 Flash Reasoning Engine In Progress...
                </h4>
                <p className="text-xs text-[#c1c6d6] font-sans mt-1">
                  Executing Model Armor sanitization &amp; diagnostic Chain of
                  Thought
                </p>
              </div>
            ) : (
              <div className="p-8 rounded-xl bg-[#131b2e]/60 border border-[#334155] text-center flex flex-col items-center justify-center space-y-2">
                <Bot className="w-10 h-10 text-[#adc7ff]" />
                <h4 className="text-sm font-headline font-bold text-white uppercase">
                  Asset Telemetry Inspected • Ready for RCA
                </h4>
                <p className="text-xs text-[#c1c6d6] max-w-lg font-sans">
                  Click{' '}
                  <strong className="text-[#adc7ff]">
                    &quot;RUN GEMINI 2.5 RCA&quot;
                  </strong>{' '}
                  to approach Gemini 2.5 Flash on GEAP to analyze telemetry
                  anomalies and formulate an autonomous remediation plan.
                </p>
              </div>
            )}

            {/* Behind-The-Scenes Live Closed-Loop Execution Trail */}
            {(appliedSuccess || isMitigated) && (
              <div className="p-5 rounded-xl bg-[#061e12]/90 border border-[#30a550] space-y-4 animate-fade-in shadow-xl shadow-[#30a550]/15">
                <div className="flex items-center justify-between border-b border-[#30a550]/40 pb-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-[#6ddd81]" />
                    <h3 className="text-sm font-headline font-bold text-white uppercase tracking-wide">
                      Live Behind-The-Scenes Closed-Loop Execution Trail
                    </h3>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#30a550]/20 text-[#6ddd81] border border-[#30a550]">
                    {approvalDetails?.execution_mode || 'AUTONOMOUS'}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
                  <div className="p-2.5 rounded bg-[#060e20] border border-[#334155]">
                    <span className="text-[#8b909f] block text-[10px] uppercase">Agent Target Route</span>
                    <span className="text-[#adc7ff] font-bold truncate block mt-0.5">
                      {approvalDetails?.execution_target || 'Vertex AI Reasoning Engine / Cloud Run'}
                    </span>
                  </div>
                  <div className="p-2.5 rounded bg-[#060e20] border border-[#334155]">
                    <span className="text-[#8b909f] block text-[10px] uppercase">Tool Activated</span>
                    <span className="text-[#6ddd81] font-bold block mt-0.5">
                      {approvalDetails?.tool_executed || 'IndustrialActuatorTool.throttle_and_cool'}
                    </span>
                  </div>
                </div>

                {/* Step Trace Timeline */}
                <div className="space-y-2 pt-1">
                  <span className="text-[10px] font-mono text-[#8b909f] uppercase tracking-widest font-bold block">
                    Execution Steps Timeline:
                  </span>
                  <div className="space-y-2">
                    {(approvalDetails?.steps || [
                      { step: 1, title: 'Agent Service Dispatch', detail: 'Dispatched approval to Reasoning Engine / Cloud Run Agent.', status: 'SUCCESS' },
                      { step: 2, title: 'Industrial Actuator Tool Invocation', detail: `Agent activated tool 'IndustrialActuatorTool.throttle_and_cool' targeting ${effectiveAsset?.asset_id || 'asset'}.`, status: 'SUCCESS' },
                      { step: 3, title: 'Physical Asset Actuation', detail: 'Actuator signal received. Engine load throttled to nominal baseline (~32% CPU, ~50°C).', status: 'SUCCESS' },
                      { step: 4, title: 'Kafka Telemetry Streaming Resumed', detail: 'Sensor simulator broadcasting healthy non-anomaly metrics to Kafka topic.', status: 'SUCCESS' },
                      { step: 5, title: 'BigQuery Governance Audit', detail: 'Incident resolution audit record & tokenomics logged to BigQuery table rca_events.', status: 'SUCCESS' },
                      { step: 6, title: 'Spark Dual-Sink Ingestion Convergence', detail: 'Dataproc PySpark (C++ Velox engine) synchronized state to Bigtable & BigQuery.', status: 'SUCCESS' },
                    ]).map((step: any) => (
                      <div
                        key={step.step}
                        className="p-3 rounded-lg bg-[#060e20] border border-[#334155]/80 flex items-start gap-3 text-xs font-mono"
                      >
                        <div className="w-5 h-5 rounded-full bg-[#30a550]/20 border border-[#30a550] text-[#6ddd81] flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                          {step.step}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-white">{step.title}</span>
                            <span className="text-[10px] text-[#8b909f]">{step.status}</span>
                          </div>
                          <p className="text-[11px] text-[#c1c6d6] font-sans mt-0.5">
                            {step.detail}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Financial Tokenomics & Human-in-the-Loop Action */}
          <div className="space-y-6">
            {mitigationData ? (
              <>
                {/* Tokenomics Card */}
                <div className="p-5 rounded-xl bg-[#131b2e]/90 border border-[#334155]">
                  <div className="flex items-center gap-2 mb-3 pb-2 border-b border-[#334155]/60">
                    <Coins className="w-4 h-4 text-[#6ddd81]" />
                    <h3 className="text-sm font-headline font-bold text-white uppercase tracking-wide">
                      Tokenomics &amp; Financial Metrics
                    </h3>
                  </div>

                  <div className="space-y-2.5 font-mono text-xs">
                    <div className="flex items-center justify-between p-2.5 rounded bg-[#060e20] border border-[#334155]/60">
                      <span className="text-[#8b909f] uppercase tracking-wider text-[11px]">Prompt Tokens:</span>
                      <span className="text-white font-bold">{mitigationData.tokenomics?.prompt_tokens ?? 168}</span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded bg-[#060e20] border border-[#334155]/60">
                      <span className="text-[#8b909f] uppercase tracking-wider text-[11px]">Completion Tokens:</span>
                      <span className="text-white font-bold">{mitigationData.tokenomics?.completion_tokens ?? 284}</span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded bg-[#060e20] border border-[#334155]/60">
                      <span className="text-[#8b909f] uppercase tracking-wider text-[11px]">Total Tokens:</span>
                      <span className="text-[#adc7ff] font-bold">{mitigationData.tokenomics?.total_tokens ?? 452}</span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded bg-[#060e20] border border-[#334155]/60">
                      <span className="text-[#8b909f] flex items-center gap-1 uppercase tracking-wider text-[11px]">
                        <Clock className="w-3 h-3 text-[#FBBC04]" /> Latency:
                      </span>
                      <span className="text-[#FBBC04] font-bold">{(mitigationData.tokenomics?.latency_ms ?? 342.5).toFixed(1)} ms</span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded bg-[#060e20] border border-[#334155]/60">
                      <span className="text-[#8b909f] flex items-center gap-1 uppercase tracking-wider text-[11px]">
                        <DollarSign className="w-3 h-3 text-[#6ddd81]" /> Inference Cost:
                      </span>
                      <span className="text-[#6ddd81] font-bold">${(mitigationData.tokenomics?.cost_usd ?? 0.00018).toFixed(5)}</span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded bg-[#30a550]/20 border border-[#30a550]">
                      <span className="text-[#6ddd81] font-bold flex items-center gap-1 uppercase tracking-wider text-[11px]">
                        <TrendingUp className="w-3 h-3 text-[#6ddd81]" /> Prevented Downtime:
                      </span>
                      <span className="text-[#6ddd81] font-extrabold">${(mitigationData.tokenomics?.prevented_downtime_usd ?? 5000).toLocaleString()}</span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded bg-[#1a73e8]/25 border border-[#1a73e8]">
                      <span className="text-[#adc7ff] font-bold uppercase tracking-wider text-[11px]">ROI Multiplier:</span>
                      <span className="text-[#adc7ff] font-extrabold">{(mitigationData.tokenomics?.roi_multiplier ?? 27777).toLocaleString()}x</span>
                    </div>
                  </div>
                </div>

                {/* Human-In-The-Loop Approve & Apply Button */}
                <div className="p-5 rounded-xl bg-[#131b2e]/90 border border-[#334155] space-y-3">
                  <div>
                    <span className="text-[10px] font-mono font-bold text-[#8b909f] uppercase tracking-widest block">
                      Step 4 &amp; 5: Human-in-the-Loop Tool Activation
                    </span>
                    <p className="text-[11px] text-[#c1c6d6] font-sans mt-0.5">
                      Approving activates Agent tool calling to signal the Kafka simulator and log tokenomics to BigQuery.
                    </p>
                  </div>

                  <button
                    disabled={isApplying || appliedSuccess || isMitigated || !isDemoActive}
                    onClick={handleApprove}
                    className={`w-full py-3.5 rounded font-mono text-xs uppercase tracking-widest font-bold transition-all border flex items-center justify-center gap-2 ${
                      !isDemoActive
                        ? 'bg-[#1e293b] border-[#475569]/40 text-[#64748b] cursor-not-allowed opacity-50 shadow-none'
                        : (isMitigated || appliedSuccess)
                        ? 'bg-[#30a550]/20 text-[#6ddd81] border-[#30a550] cursor-default'
                        : 'bg-[#30a550] hover:bg-[#6ddd81] hover:text-[#003210] text-white border-[#6ddd81]/40 shadow-lg shadow-[#30a550]/30 disabled:opacity-50'
                    }`}
                    title={!isDemoActive ? 'Demo locked: Start pipeline above to enable' : 'Approve and execute industrial actuator tools'}
                  >
                    {isApplying ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : !isDemoActive ? (
                      <Lock className="w-4 h-4 text-[#64748b]" />
                    ) : (isMitigated || appliedSuccess) ? (
                      <CheckCircle2 className="w-4 h-4 text-[#6ddd81]" />
                    ) : (
                      <ShieldCheck className="w-4 h-4 text-white" />
                    )}
                    <span>
                      {!isDemoActive
                        ? 'CONTROLS LOCKED (PIPELINE REQUIRED)'
                        : (isMitigated || appliedSuccess)
                        ? 'AGENT TOOLS EXECUTED & RESOLVED'
                        : 'APPROVE & EXECUTE AGENT TOOLS'}
                    </span>
                  </button>

                  {/* Summary Status Box */}
                  {(appliedSuccess || isMitigated) && (
                    <div className="p-3 rounded-lg bg-[#060e20] border border-[#30a550] space-y-2 text-xs font-mono">
                      <div className="flex items-center gap-1.5 text-[#6ddd81] font-bold">
                        <CheckCircle2 className="w-4 h-4 text-[#6ddd81]" />
                        <span>Closed-Loop Action Succeeded</span>
                      </div>
                      <ul className="text-[11px] text-[#c1c6d6] space-y-1 pl-1">
                        <li>• Tool: <code className="text-[#adc7ff]">IndustrialActuatorTool.throttle_and_cool</code></li>
                        <li>• Route: <span className="text-[#adc7ff]">{approvalDetails?.execution_mode || 'Agent Service'}</span></li>
                        <li>• Physical State: <span className="text-[#6ddd81]">Simulator emitting healthy telemetry</span></li>
                        <li>• Governance: <span className="text-[#6ddd81]">Audit &amp; Tokenomics logged to BigQuery</span></li>
                      </ul>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="p-5 rounded-xl bg-[#131b2e]/90 border border-[#334155] space-y-3">
                <div className="flex items-center gap-2 pb-2 border-b border-[#334155]/60">
                  <Coins className="w-4 h-4 text-[#6ddd81]" />
                  <h3 className="text-sm font-headline font-bold text-white uppercase tracking-wide">
                    Human-in-the-Loop Operations
                  </h3>
                </div>
                <div className="space-y-2.5 text-xs text-[#c1c6d6] font-sans">
                  <p>
                    <strong className="text-white font-mono">
                      1. Approach Agent:
                    </strong>{' '}
                    Request Gemini 2.5 Flash Root Cause Analysis.
                  </p>
                  <p>
                    <strong className="text-white font-mono">
                      2. Review Plan:
                    </strong>{' '}
                    Verify multi-step diagnostic reasoning &amp; tokenomics ROI.
                  </p>
                  <p>
                    <strong className="text-white font-mono">
                      3. Authorize:
                    </strong>{' '}
                    Execute industrial actuator tools to restore nominal state.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
};
