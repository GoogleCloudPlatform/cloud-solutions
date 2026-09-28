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
import Link from 'next/link';
import {
  Layers,
  Database,
  Sparkles,
  TrendingUp,
  ExternalLink,
  Bot,
  Activity,
  Play,
  RefreshCw,
  Lock
} from 'lucide-react';
import { getConsoleLinks } from '../utils/gcpConsoleLinks';
import { getStackConfig } from '../utils/stackConfig';

interface Module4PipelineFlowProps {
  criticalCount?: number;
  selectedAssetId?: string | null;
  hasMitigation?: boolean;
  isSimulatorRunning?: boolean;
  isPipelineActive?: boolean;
  onStartSimulator?: () => Promise<void>;
  onStartPipeline?: () => Promise<void>;
  onStartBoth?: () => Promise<void>;
  onNavigateToSimulator?: () => void;
}

export const Module4PipelineFlow: React.FC<Module4PipelineFlowProps> = ({
  criticalCount = 0,
  hasMitigation = false,
  isSimulatorRunning = false,
  isPipelineActive = false,
  onStartSimulator,
  onStartPipeline,
  onStartBoth,
  onNavigateToSimulator,
}) => {
  const consoleLinks = getConsoleLinks();
  const [isStartingAll, setIsStartingAll] = useState(false);

  const isDemoFullyActive = isSimulatorRunning && isPipelineActive;

  const handleActivateAll = async () => {
    setIsStartingAll(true);
    try {
      if (onStartBoth) {
        await onStartBoth();
      } else {
        if (!isSimulatorRunning && onStartSimulator) await onStartSimulator();
        if (!isPipelineActive && onStartPipeline) await onStartPipeline();
      }
    } finally {
      setIsStartingAll(false);
    }
  };

  const stackConfig = getStackConfig();

  const step1Subtitle = stackConfig.module4Step1Subtitle;
  const ingestionStoppedLabel = stackConfig.ingestionPausedLabel;
  const pipelineStoppedLabel = stackConfig.pipelineStoppedLabel;

  const step3Subtitle = stackConfig.module4Step3Subtitle;

  const steps = [
    {
      step: 1,
      title: 'Streaming Ingestion',
      subtitle: step1Subtitle,
      status: !isSimulatorRunning
        ? ingestionStoppedLabel
        : !isPipelineActive
        ? pipelineStoppedLabel
        : 'STREAMING',
      isActive: isDemoFullyActive,
      isAlert: false,
      icon: <Layers className="w-4 h-4 text-[#68abff]" />,
      consoleUrl: consoleLinks.ingestionConsole,
      consoleLabel: consoleLinks.ingestionLabel,
    },
    {
      step: 2,
      title: 'Bigtable State',
      subtitle: 'telemetry_metrics (<5ms)',
      status: 'P99 < 5ms',
      isActive: isDemoFullyActive,
      isAlert: false,
      icon: <Database className="w-4 h-4 text-emerald-400" />,
      consoleUrl: consoleLinks.bigtableTable,
      consoleLabel: 'Bigtable Console',
    },
    {
      step: 3,
      title: 'Anomaly Detection',
      subtitle: step3Subtitle,
      status: criticalCount > 0 ? `${criticalCount} CRITICAL` : 'MONITORING',
      isActive: isDemoFullyActive,
      isAlert: criticalCount > 0,
      icon: <Sparkles className="w-4 h-4 text-amber-400" />,
      consoleUrl: consoleLinks.geminiEnterpriseAgentPlatform,
      consoleLabel: 'GEAP Agent',
    },
    {
      step: 4,
      title: 'HITL Mitigation',
      subtitle: 'IndustrialActuatorTool',
      status:
        hasMitigation && criticalCount > 0
          ? 'AWAITING APPROVAL'
          : hasMitigation
          ? 'RESOLVED'
          : 'READY',
      isActive: hasMitigation,
      isAlert: hasMitigation && criticalCount > 0,
      icon: <Bot className="w-4 h-4 text-[#68abff]" />,
      consoleUrl: consoleLinks.hudBackendRun,
      consoleLabel: 'Cloud Run API',
    },
    {
      step: 5,
      title: 'BigQuery ROI Audit',
      subtitle: 'analytics.rca_events',
      status: 'AUDIT ACTIVE',
      isActive: isDemoFullyActive,
      isAlert: false,
      icon: <TrendingUp className="w-4 h-4 text-emerald-400" />,
      consoleUrl: consoleLinks.bigqueryRcaTable,
      consoleLabel: 'BigQuery Table',
    },
  ];

  return (
    <div className="space-y-4">
      {/* Inactive Pipeline Warning / Activation Banner */}
      {!isDemoFullyActive && (
        <div className="p-4 rounded-2xl bg-rose-950/40 border border-rose-500/40 shadow-[0_0_24px_-6px_rgba(239,68,68,0.25)] animate-fade-in flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-rose-400" />
              <h3 className="text-sm font-headline font-bold text-white uppercase tracking-wider">
                Live Closed-Loop Demo Locked — Ingestion Pipeline Required
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-rose-500/20 text-rose-300 border border-rose-500/40">
                INACTIVE
              </span>
            </div>
            <p className="text-xs text-[#cbd5e1] max-w-3xl font-sans">
              Start both the <strong>{stackConfig.generatorShort}</strong> and{' '}
              <strong>{stackConfig.pipelineName}</strong> to stream live telemetry and unlock chaos anomaly injection.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-0.5 text-xs font-mono">
              <span className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isSimulatorRunning ? 'bg-emerald-400' : 'bg-rose-400'
                  }`}
                />
                <span>
                  {stackConfig.generatorShort}:{' '}
                  <strong className={isSimulatorRunning ? 'text-emerald-400' : 'text-rose-400'}>
                    {isSimulatorRunning ? 'RUNNING' : 'STOPPED'}
                  </strong>
                </span>
              </span>
              <span className="text-[#475569]">|</span>
              <span className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    isPipelineActive ? 'bg-emerald-400' : 'bg-rose-400'
                  }`}
                />
                <span>
                  {stackConfig.pipelineShort}:{' '}
                  <strong className={isPipelineActive ? 'text-emerald-400' : 'text-rose-400'}>
                    {isPipelineActive ? 'RUNNING' : 'STOPPED'}
                  </strong>
                </span>
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <button
              type="button"
              disabled={isStartingAll}
              onClick={handleActivateAll}
              className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs uppercase tracking-wider font-bold transition-all shadow-md shadow-emerald-600/20 flex items-center gap-2 disabled:opacity-50 cursor-pointer"
            >
              {isStartingAll ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5 fill-white" />
              )}
              <span>Start All &amp; Unlock Demo</span>
            </button>

            <Link
              href="/simulator"
              onClick={onNavigateToSimulator}
              className="px-3.5 py-2 rounded-xl border border-white/[0.08] hover:border-white/20 bg-[#0b1326] text-[#cbd5e1] text-xs font-mono tracking-wider transition-all cursor-pointer"
            >
              <span>Module 2 Controls ↗</span>
            </Link>
          </div>
        </div>
      )}

      {/* Compact 5-Step Operational Lifecycle Stepper */}
      <section className="w-full glass-panel rounded-2xl px-5 py-4 space-y-3">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-[#1a73e8]/15 border border-[#1a73e8]/30 text-[#68abff]">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm md:text-base font-headline font-bold text-white uppercase tracking-wide flex items-center gap-2">
                <span>Module 4: Live Operations &amp; Cognitive Co-Pilot</span>
                <span className="hidden sm:inline-block px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-[#1a73e8]/15 text-[#68abff] border border-[#1a73e8]/30">
                  CLOSED-LOOP PIPELINE
                </span>
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-2 text-[11px] font-mono text-[#cbd5e1] bg-[#070d19] px-3 py-1 rounded-lg border border-white/[0.08]">
            <span
              className={`w-2 h-2 rounded-full ${
                isDemoFullyActive ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span>{stackConfig.infraSummary}</span>
          </div>
        </div>

        {/* 5-Stage Horizontal Progress Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
          {steps.map((item) => (
            <div
              key={item.step}
              className={`rounded-xl px-3.5 py-2.5 border transition-all flex flex-col justify-between gap-2 ${
                item.isAlert
                  ? 'bg-rose-950/35 border-rose-500/50 shadow-[0_0_16px_-4px_rgba(239,68,68,0.3)]'
                  : 'bg-[#070d19]/90 border-white/[0.08] hover:border-white/20'
              }`}
            >
              <div className="flex items-center justify-between gap-1.5">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="text-[10px] font-mono font-bold text-[#68abff] tabular-nums shrink-0">
                    0{item.step}
                  </span>
                  {item.icon}
                  <span className="text-xs font-headline font-bold text-white truncate">
                    {item.title}
                  </span>
                </div>

                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase tracking-wider shrink-0 border ${
                    item.isAlert
                      ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse'
                      : item.isActive
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                      : 'bg-white/[0.04] text-[#94a3b8] border-white/[0.08]'
                  }`}
                >
                  {item.status}
                </span>
              </div>

              <div className="flex items-center justify-between gap-2 pt-1 border-t border-white/[0.06]">
                <span className="text-[10px] font-mono text-[#64748b] truncate" title={item.subtitle}>
                  {item.subtitle}
                </span>
                <a
                  href={item.consoleUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[10px] font-mono text-[#68abff] hover:text-white shrink-0 transition-colors"
                  title={`Open ${item.consoleLabel}`}
                >
                  <span>{item.consoleLabel}</span>
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
