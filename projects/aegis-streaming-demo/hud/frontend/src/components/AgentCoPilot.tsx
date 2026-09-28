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
  ShieldAlert,
  Coins,
  ShieldCheck,
  RefreshCw,
  Lock,
  AlertCircle
} from 'lucide-react';
import { getDataAgeInfo } from '../utils/telemetryUtils';
import { getStackConfig } from '../utils/stackConfig';

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
  const stackConfig = getStackConfig();

  React.useEffect(() => {
    const isCrit = selectedAsset && (
      selectedAsset.status === 'CRITICAL' ||
      selectedAsset.is_anomaly ||
      selectedAsset.cpu_utilization > 90 ||
      selectedAsset.temperature_c > 90
    );
    if (isCrit && mitigationData?.status !== 'RESOLVED') {
      setAppliedSuccess(false);
      setApprovalDetails(null);
    }
  }, [selectedAsset?.asset_id, selectedAsset?.status, selectedAsset?.is_anomaly, selectedAsset?.cpu_utilization, selectedAsset?.temperature_c, mitigationData?.status]);

  const handleApprove = async () => {
    if (!mitigationData || !isDemoActive) return;
    setIsApplying(true);
    try {
      const res = await onApproveAndApply(mitigationData.asset_id);
      if (res && typeof res === 'object' && res.success) {
        setApprovalDetails(res);
        setAppliedSuccess(true);
      }
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
    <section
      className={`w-full glass-panel rounded-2xl p-5 transition-all duration-300 space-y-4 ${
        !isDemoActive ? 'border-white/[0.06] bg-[#070d19]/90' : ''
      }`}
    >
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 pb-3.5 border-b border-white/[0.08]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Bot className="w-4 h-4 text-[#68abff]" />
            <h2 className="text-base font-headline font-bold text-white uppercase tracking-wide">
              AI Agent Co-Pilot
            </h2>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider border flex items-center gap-1 ${
                isDemoActive
                  ? 'bg-[#1a73e8]/15 text-[#68abff] border-[#1a73e8]/35'
                  : 'bg-white/[0.04] text-[#94a3b8] border-white/[0.08]'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isDemoActive ? 'bg-emerald-400 animate-pulse' : 'bg-[#64748b]'
                }`}
              />
              {isDemoActive ? 'GEMINI 2.5 FLASH • GEAP' : 'LOCKED'}
            </span>
          </div>
          <p className="text-xs text-[#94a3b8] font-sans mt-0.5">
            Model Armor Sanitized RCA &bull; Human-in-the-Loop Actuation
          </p>
        </div>

        {mitigationData && (
          <div>
            {isMitigated ? (
              <span className="px-2.5 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider font-bold flex items-center gap-1 border bg-emerald-500/15 text-emerald-400 border-emerald-500/35">
                <ShieldCheck className="w-3.5 h-3.5" /> RESOLVED
              </span>
            ) : (
              <span
                className={`px-2.5 py-1 rounded-md text-[10px] font-mono uppercase tracking-wider font-bold flex items-center gap-1 border ${
                  mitigationData.severity === 'CRITICAL'
                    ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse'
                    : 'bg-amber-500/15 text-amber-400 border-amber-500/35'
                }`}
              >
                <AlertTriangle className="w-3.5 h-3.5" /> {mitigationData.severity}
              </span>
            )}
          </div>
        )}
      </div>

      {!effectiveAsset && !mitigationData && !isLoadingMitigation ? (
        <div className="p-10 rounded-xl bg-[#070d19]/80 border border-dashed border-white/[0.1] text-center flex flex-col items-center justify-center space-y-2">
          <BrainCircuit className="w-10 h-10 text-[#68abff]/70 mb-1" />
          <h3 className="text-sm font-headline font-bold text-white">
            Select an Asset or Inject an Anomaly
          </h3>
          <p className="text-xs text-[#94a3b8] max-w-sm font-sans leading-relaxed">
            {!isDemoActive
              ? stackConfig.copilotEmptyState
              : 'Click any asset tile on the left or click "Inject Anomaly" to trigger real-time Gemini 2.5 Flash Root Cause Analysis.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Target Asset Header Card */}
          {effectiveAsset &&
            (() => {
              const ageInfo = getDataAgeInfo(effectiveAsset.timestamp);
              const isStale = ageInfo.isStale;
              const isCritical =
                !isStale &&
                !isMitigated &&
                (effectiveAsset.status === 'CRITICAL' ||
                  effectiveAsset.is_anomaly ||
                  effectiveAsset.cpu_utilization > 90 ||
                  effectiveAsset.temperature_c > 90);
              const isWarning =
                !isStale &&
                !isMitigated &&
                !isCritical &&
                (effectiveAsset.status === 'WARNING' ||
                  effectiveAsset.cpu_utilization > 75 ||
                  effectiveAsset.temperature_c > 75);

              return (
                <div className="space-y-2.5">
                  {isStale && (
                    <div className="p-3 rounded-xl bg-amber-950/30 border border-amber-500/40 text-xs font-sans text-[#e2e8f0] flex items-start gap-2">
                      <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                      <span>
                        <strong className="text-amber-300 font-mono uppercase">
                          Stale Data (&gt;60m):
                        </strong>{' '}
                        Start the stream in Module 2 to run live RCA.
                      </span>
                    </div>
                  )}

                  <div className="p-3.5 rounded-xl bg-[#070d19] border border-white/[0.08] flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#64748b] block">
                        Target Asset
                      </span>
                      <div className="text-sm font-mono font-bold text-white flex items-center gap-2 mt-0.5">
                        <span>{effectiveAsset.asset_id}</span>
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded uppercase tracking-wider font-bold ${
                            isMitigated
                              ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/35'
                              : isStale || !isDemoActive
                              ? 'bg-white/[0.04] text-[#64748b] border border-white/[0.08]'
                              : isCritical
                              ? 'bg-rose-600 text-white animate-pulse'
                              : isWarning
                              ? 'bg-amber-500/15 text-amber-400 border border-amber-500/35'
                              : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/35'
                          }`}
                        >
                          {isMitigated
                            ? 'NOMINAL'
                            : isStale
                            ? 'STALE'
                            : isCritical
                            ? 'CRITICAL'
                            : isWarning
                            ? 'WARNING'
                            : effectiveAsset.status || 'OK'}
                        </span>
                        <span className="text-[10px] font-mono font-normal text-[#64748b] tabular-nums">
                          {effectiveAsset.cpu_utilization.toFixed(1)}% CPU &bull;{' '}
                          {effectiveAsset.temperature_c.toFixed(1)}°C
                        </span>
                      </div>
                    </div>

                    <button
                      type="button"
                      disabled={
                        isLoadingMitigation ||
                        !isDemoActive ||
                        (isStale && !isMitigated) ||
                        !effectiveAsset
                      }
                      onClick={() => {
                        if (!isDemoActive || (isStale && !isMitigated) || !effectiveAsset) return;
                        onExecuteMitigation(effectiveAsset);
                      }}
                      className={`px-3.5 py-2 rounded-xl font-mono text-xs uppercase tracking-wider font-bold flex items-center gap-1.5 transition-all border ${
                        (isStale && !isMitigated) || !isDemoActive
                          ? 'bg-[#0f172a] border-white/[0.08] text-[#64748b] cursor-not-allowed opacity-50'
                          : 'bg-[#1a73e8] hover:bg-[#1557b0] text-white border-[#adc7ff]/30 shadow-md shadow-[#1a73e8]/25 cursor-pointer disabled:opacity-50'
                      }`}
                    >
                      {isLoadingMitigation ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (isStale && !isMitigated) || !isDemoActive ? (
                        <Lock className="w-3.5 h-3.5 text-[#64748b]" />
                      ) : (
                        <BrainCircuit className="w-3.5 h-3.5" />
                      )}
                      <span>{isStale && !isMitigated ? 'Stale' : 'Run Gemini RCA'}</span>
                    </button>
                  </div>
                </div>
              );
            })()}

          {/* RCA & Remediation Section */}
          {mitigationData ? (
            <div className="space-y-4">
              {/* Root Cause + Chain-of-Thought + 3-Step Plan */}
              <div className="p-4 rounded-xl bg-[#070d19]/90 border border-white/[0.08] space-y-3.5">
                <div>
                  <div className="flex items-center gap-1.5 mb-1">
                    <ShieldAlert className="w-4 h-4 text-[#68abff]" />
                    <h3 className="text-xs font-headline font-bold text-white uppercase tracking-wider">
                      Root Cause Analysis
                    </h3>
                  </div>
                  <p className="text-xs text-[#cbd5e1] leading-relaxed font-sans">
                    {mitigationData.root_cause_summary}
                  </p>
                </div>

                {/* Chain of Thought Reasoning Box */}
                <div className="p-3 rounded-lg bg-[#0b1326] border border-white/[0.08]">
                  <span className="text-[10px] font-mono text-[#68abff] uppercase tracking-widest font-bold block mb-1.5">
                    Chain-of-Thought Diagnostic Trail
                  </span>
                  <pre className="text-[11px] font-mono text-[#cbd5e1] whitespace-pre-wrap leading-relaxed max-h-40 overflow-y-auto scrollbar-thin">
                    {mitigationData.chain_of_thought}
                  </pre>
                </div>

                {/* Ordered Remediation Steps */}
                <div className="space-y-1.5">
                  <span className="text-[10px] font-mono text-[#94a3b8] uppercase tracking-widest font-bold block">
                    Recommended Mitigation Plan
                  </span>
                  <div className="space-y-1.5">
                    {mitigationData.mitigation_steps.map((step, idx) => (
                      <div
                        key={idx}
                        className="px-3 py-2 rounded-lg bg-[#0b1326]/70 border border-white/[0.06] flex items-start gap-2.5 text-xs text-[#e2e8f0] font-mono"
                      >
                        <span className="w-4 h-4 rounded-full bg-[#1a73e8]/20 border border-[#1a73e8]/50 text-[#68abff] flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 tabular-nums">
                          {idx + 1}
                        </span>
                        <span className="leading-snug">{step}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 3-Column ROI Hero Strip + Compact Tokenomics Subtitle */}
              <div className="p-4 rounded-xl bg-[#070d19]/90 border border-white/[0.08] space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-emerald-400 flex items-center gap-1.5">
                    <Coins className="w-3.5 h-3.5" />
                    <span>Tokenomics &amp; Financial ROI</span>
                  </span>
                  <span className="text-[10px] font-mono text-[#64748b] tabular-nums">
                    {mitigationData.tokenomics?.total_tokens ?? 452} tokens (
                    {mitigationData.tokenomics?.prompt_tokens ?? 168} in /{' '}
                    {mitigationData.tokenomics?.completion_tokens ?? 284} out) &bull;{' '}
                    {(mitigationData.tokenomics?.latency_ms ?? 342.5).toFixed(0)} ms
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2.5">
                  <div className="p-2.5 rounded-lg bg-[#0b1326] border border-white/[0.06]">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[#64748b] block">
                      AI Cost
                    </span>
                    <span className="text-sm font-mono font-bold text-white tabular-nums mt-0.5 block">
                      ${(mitigationData.tokenomics?.cost_usd ?? 0.00018).toFixed(5)}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-emerald-950/30 border border-emerald-500/25">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400/80 block">
                      Saved
                    </span>
                    <span className="text-sm font-mono font-bold text-emerald-400 tabular-nums mt-0.5 block">
                      $
                      {(
                        mitigationData.tokenomics?.prevented_downtime_usd ?? 5000
                      ).toLocaleString()}
                    </span>
                  </div>

                  <div className="p-2.5 rounded-lg bg-[#1a73e8]/15 border border-[#1a73e8]/35">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-[#68abff] block">
                      Net ROI
                    </span>
                    <span className="text-sm font-mono font-bold text-[#68abff] tabular-nums mt-0.5 block">
                      {(mitigationData.tokenomics?.roi_multiplier ?? 27777).toLocaleString()}x
                    </span>
                  </div>
                </div>
              </div>

              {/* Human-in-the-Loop Primary Action CTA */}
              <div className="space-y-3">
                <button
                  type="button"
                  disabled={isApplying || appliedSuccess || isMitigated || !isDemoActive}
                  onClick={handleApprove}
                  className={`w-full py-3.5 px-4 rounded-xl font-mono text-xs uppercase tracking-widest font-bold transition-all border flex items-center justify-center gap-2 ${
                    !isDemoActive
                      ? 'bg-[#0f172a] border-white/[0.08] text-[#64748b] cursor-not-allowed opacity-50'
                      : isMitigated || appliedSuccess
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/35 cursor-default'
                      : 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-400/40 shadow-lg shadow-emerald-600/25 cursor-pointer disabled:opacity-50'
                  }`}
                >
                  {isApplying ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : !isDemoActive ? (
                    <Lock className="w-4 h-4 text-[#64748b]" />
                  ) : isMitigated || appliedSuccess ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <ShieldCheck className="w-4 h-4 text-white" />
                  )}
                  <span>
                    {!isDemoActive
                      ? 'Controls Locked (Pipeline Required)'
                      : isMitigated || appliedSuccess
                      ? 'Mitigation Executed & Asset Restored'
                      : 'Approve & Execute Mitigation'}
                  </span>
                </button>

                {/* Compact Closed-Loop Execution Trail on Resolution */}
                {(appliedSuccess || isMitigated) && (
                  <div className="p-3.5 rounded-xl bg-emerald-950/25 border border-emerald-500/35 space-y-2 animate-fade-in">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="text-emerald-400 font-bold flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4" />
                        <span>Closed-Loop Actuation Complete</span>
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                        {approvalDetails?.execution_mode || 'AUTONOMOUS'}
                      </span>
                    </div>
                    <div className="text-[11px] font-mono text-[#cbd5e1] space-y-1">
                      <div>
                        • Tool:{' '}
                        <code className="text-[#68abff]">
                          {approvalDetails?.tool_executed ||
                            'IndustrialActuatorTool.throttle_and_cool'}
                        </code>
                      </div>
                      <div>
                        • Telemetry: Healthy baseline resumed on{' '}
                        <strong className="text-white">{ stackConfig.ingestionShort }</strong> &amp;{' '}
                        <strong className="text-emerald-400">Cloud Bigtable</strong>
                      </div>
                      <div>
                        • Governance: Audit &amp; ROI logged to BigQuery{' '}
                        <code className="text-emerald-400">analytics.rca_events</code>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : isLoadingMitigation ? (
            <div className="p-10 rounded-xl bg-[#070d19]/90 border border-[#1a73e8]/30 flex flex-col items-center justify-center text-center">
              <RefreshCw className="w-7 h-7 text-[#68abff] animate-spin mb-2.5" />
              <h4 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                Gemini 2.5 Flash Reasoning in Progress...
              </h4>
              <p className="text-xs text-[#94a3b8] font-sans mt-1">
                Sanitizing payload through Model Armor &amp; synthesizing 3-step mitigation plan
              </p>
            </div>
          ) : (
            <div className="p-6 rounded-xl bg-[#070d19]/80 border border-white/[0.08] text-center flex flex-col items-center justify-center space-y-2">
              <Bot className="w-8 h-8 text-[#68abff]" />
              <h4 className="text-xs font-headline font-bold text-white uppercase tracking-wider">
                Asset Selected • Ready for Diagnostic RCA
              </h4>
              <p className="text-xs text-[#94a3b8] max-w-sm font-sans leading-relaxed">
                Click <strong className="text-[#68abff]">Run Gemini RCA</strong> above to diagnose{' '}
                <strong className="text-white">{effectiveAsset?.asset_id}</strong> and generate an
                operator-approved mitigation plan.
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
