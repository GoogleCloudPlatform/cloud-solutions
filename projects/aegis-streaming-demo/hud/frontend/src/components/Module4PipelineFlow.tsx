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
import {
  Layers,
  Database,
  Sparkles,
  ShieldCheck,
  TrendingUp,
  ArrowRight,
  ExternalLink,
  Cpu,
  Bot,
  Activity,
  CheckCircle2,
  Zap,
  Flame,
  FileText,
  AlertOctagon,
  Play,
  RefreshCw,
  Lock
} from 'lucide-react';
import { getConsoleLinks } from '../utils/gcpConsoleLinks';

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
  selectedAssetId = null,
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

  const steps = [
    {
      step: 1,
      title: 'Dual-Sink Streaming Ingestion',
      subtitle: 'Managed Kafka → Dataproc Spark (C++ Velox)',
      description: 'Kafka sensor events are ingested by Spark Streaming with native C++ acceleration and written continuously to a dual sink: Cloud Bigtable (operational state) & BigQuery (analytical history).',
      tech: 'Managed Kafka • Dataproc C++ • Bigtable • BigQuery',
      status: !isSimulatorRunning
        ? 'KAFKA PAUSED'
        : !isPipelineActive
        ? 'SPARK STOPPED'
        : 'STREAMING ACTIVE',
      statusColor: isDemoFullyActive
        ? 'text-[#6ddd81] bg-[#30a550]/20 border-[#30a550]/50'
        : 'text-[#FBBC04] bg-[#FBBC04]/20 border-[#FBBC04]/50',
      icon: <Layers className="w-5 h-5 text-[#adc7ff]" />,
      consoleUrl: consoleLinks.kafkaCluster,
      consoleLabel: 'Kafka Console',
    },
    {
      step: 2,
      title: 'Sub-Millisecond Operational HUD',
      subtitle: 'Cloud Bigtable Direct Read',
      description: 'The Operations HUD reads operational telemetry directly from Cloud Bigtable (telemetry_metrics) to render near-real-time asset states with sub-10ms point lookup latency.',
      tech: 'Cloud Bigtable • telemetry_metrics • SSE Streaming',
      status: 'BIGTABLE P99 <10ms',
      statusColor: 'text-[#adc7ff] bg-[#1a73e8]/20 border-[#1a73e8]/50',
      icon: <Database className="w-5 h-5 text-[#6ddd81]" />,
      consoleUrl: consoleLinks.bigtableTable,
      consoleLabel: 'Bigtable Console',
    },
    {
      step: 3,
      title: 'In-Stream Anomaly Detection & AI Agent',
      subtitle: 'Spark Detection → Gemini 2.5 Flash RCA',
      description: 'When an anomaly is detected in Spark tumbling windows, Spark approaches our Anomaly Mitigation Agent. Powered by Gemini 2.5 Flash on GEAP, the agent formulates a structured Root Cause Analysis & remediation plan for the user.',
      tech: 'Dataproc Anomaly Hook • Gemini 2.5 Flash • GEAP',
      status: criticalCount > 0 ? `${criticalCount} ANOMALY DETECTED` : 'MONITORING',
      statusColor: criticalCount > 0
        ? 'text-[#ffdad6] bg-[#D93025] border-[#ffdad6]/40 animate-pulse font-bold'
        : 'text-[#6ddd81] bg-[#30a550]/20 border-[#30a550]/50',
      icon: <Sparkles className="w-5 h-5 text-[#ffb4ab]" />,
      consoleUrl: consoleLinks.geminiEnterpriseAgentPlatform,
      consoleLabel: 'GEAP Agent Console',
    },
    {
      step: 4,
      title: 'Human-in-the-Loop Approval & Tool Action',
      subtitle: 'Operator Approval → Industrial Control Tool',
      description: 'After the operator reviews and approves the mitigation steps, the Agent executes "IndustrialActuatorTool.throttle_and_cool", which signals the Kafka simulator to emit non-anomaly healthy payloads—simulating physical remediation on the asset itself.',
      tech: 'Human-in-the-Loop • IndustrialActuatorTool • Simulator Signal',
      status: hasMitigation && criticalCount > 0 ? 'AWAITING / EXECUTING' : (hasMitigation ? 'RESOLVED • APPLIED' : 'READY'),
      statusColor: hasMitigation && criticalCount > 0
        ? 'text-[#FBBC04] bg-[#FBBC04]/20 border-[#FBBC04]/50 animate-pulse'
        : hasMitigation
        ? 'text-[#6ddd81] bg-[#30a550]/20 border-[#30a550]/50'
        : 'text-[#adc7ff] bg-[#1a73e8]/20 border-[#1a73e8]/50',
      icon: <Bot className="w-5 h-5 text-[#FBBC04]" />,
      consoleUrl: consoleLinks.hudBackendRun,
      consoleLabel: 'Cloud Run Backend',
    },
    {
      step: 5,
      title: 'Governance Audit & Tokenomics',
      subtitle: 'BigQuery Historical Analytics & ROI Log',
      description: 'The Agent writes every action taken, incident RCA, LLM token consumption ($0.00018), and prevented downtime value ($5,000) directly to BigQuery (rca_events) for compliance and executive auditing.',
      tech: 'BigQuery • rca_events • Tokenomics ROI',
      status: 'AUDIT STREAMING',
      statusColor: 'text-[#6ddd81] bg-[#30a550]/20 border-[#30a550]/50',
      icon: <TrendingUp className="w-5 h-5 text-[#6ddd81]" />,
      consoleUrl: consoleLinks.bigqueryRcaTable,
      consoleLabel: 'BigQuery RCA Table',
    },
  ];

  return (
    <div className="space-y-4">
      {/* Inactive Pipeline Warning / Activation Banner */}
      {!isDemoFullyActive && (
        <div className="p-5 rounded-2xl bg-[#93000a]/20 border-2 border-[#D93025] shadow-[0_0_25px_rgba(217,48,37,0.3)] animate-fade-in flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Lock className="w-5 h-5 text-[#ffb4ab]" />
              <h3 className="text-base font-headline font-bold text-white uppercase tracking-wider">
                Live Closed-Loop Demo Locked — Ingestion Pipeline Required
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-[#D93025] text-white">
                INACTIVE
              </span>
            </div>
            <p className="text-xs text-[#dae2fd] max-w-3xl font-sans">
              To experience the true closed-loop demo—where Kafka streams sensor data, Spark detects anomalies in real-time, and the Agent&apos;s mitigation signals the machine generator—both the <strong>Kafka CDC Generator</strong> and <strong>Managed Spark Streaming Job</strong> must be running.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1 text-xs font-mono">
              <span className="flex items-center gap-1">
                <span className={`w-2 h-2 rounded-full ${isSimulatorRunning ? 'bg-[#6ddd81]' : 'bg-[#D93025]'}`} />
                <span>Kafka CDC Generator: <strong className={isSimulatorRunning ? 'text-[#6ddd81]' : 'text-[#ffb4ab]'}>{isSimulatorRunning ? 'RUNNING' : 'STOPPED'}</strong></span>
              </span>
              <span className="text-[#8b909f]">|</span>
              <span className="flex items-center gap-1">
                <span className={`w-2 h-2 rounded-full ${isPipelineActive ? 'bg-[#6ddd81]' : 'bg-[#D93025]'}`} />
                <span>Managed Spark Pipeline: <strong className={isPipelineActive ? 'text-[#6ddd81]' : 'text-[#ffb4ab]'}>{isPipelineActive ? 'RUNNING' : 'STOPPED'}</strong></span>
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <button
              disabled={isStartingAll}
              onClick={handleActivateAll}
              className="px-4 py-2.5 rounded-lg bg-[#30a550] hover:bg-[#25853e] text-white font-mono text-xs uppercase tracking-wider font-bold transition-all shadow-lg shadow-[#30a550]/30 flex items-center gap-2 disabled:opacity-50"
            >
              {isStartingAll ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4 fill-white" />
              )}
              <span>START ALL &amp; UNLOCK DEMO</span>
            </button>

            {onNavigateToSimulator && (
              <button
                onClick={onNavigateToSimulator}
                className="px-3.5 py-2 rounded-lg border border-[#334155] hover:border-[#adc7ff] hover:bg-[#131b2e] text-[#dae2fd] text-xs font-mono tracking-wider transition-all"
              >
                <span>Go to Module 2 Controls ↗</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Active System Architecture Banner */}
      <section className="w-full glass-panel rounded-2xl p-6 border border-[#334155] shadow-xl space-y-4">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3 pb-3 border-b border-[#334155]">
          <div>
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-[#adc7ff]" />
              <h2 className="text-lg font-headline font-bold text-white uppercase tracking-wide">
                Module 4: Live Operational Lifecycle Architecture
              </h2>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-[#1a73e8]/20 text-[#adc7ff] border border-[#1a73e8]/50">
                5-STEP CLOSED-LOOP SYSTEM
              </span>
            </div>
            <p className="text-xs text-[#c1c6d6] font-sans mt-0.5">
              How Project Aegis ingests, monitors, detects anomalies, engages AI reasoning, and executes closed-loop remediation across GCP.
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs font-mono text-[#dae2fd] bg-[#0a0f1d] px-3 py-1.5 rounded-lg border border-[#334155]">
            <span className={`w-2 h-2 rounded-full ${isDemoFullyActive ? 'bg-[#6ddd81] animate-pulse' : 'bg-[#FBBC04]'}`} />
            <span>Infrastructure: <strong>Bigtable + Spark (C++ Velox) + GEAP + BigQuery</strong></span>
          </div>
        </div>

        {/* 5-Step Process Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-3 pt-2">
          {steps.map((item) => (
            <div
              key={item.step}
              className="relative rounded-xl p-4 bg-[#131b2e]/80 border border-[#334155] hover:border-[#adc7ff]/60 transition-all flex flex-col justify-between group shadow-md"
            >
              <div>
                {/* Step Badge & Status */}
                <div className="flex items-center justify-between gap-1 mb-2.5">
                  <span className="px-2 py-0.5 rounded bg-[#060e20] text-[#adc7ff] text-[10px] font-mono font-bold uppercase tracking-wider border border-[#334155]/60">
                    STEP {item.step}
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[9px] font-mono uppercase tracking-wider border ${item.statusColor}`}>
                    {item.status}
                  </span>
                </div>

                {/* Title & Subtitle */}
                <div className="flex items-start gap-2 mb-2">
                  <div className="p-1.5 rounded bg-[#060e20] border border-[#334155]/60 shrink-0 mt-0.5">
                    {item.icon}
                  </div>
                  <div>
                    <h3 className="text-xs font-mono font-bold text-white leading-tight">
                      {item.title}
                    </h3>
                    <span className="text-[10px] font-mono text-[#8b909f] block">
                      {item.subtitle}
                    </span>
                  </div>
                </div>

                {/* Description */}
                <p className="text-[11px] text-[#c1c6d6] font-sans leading-relaxed mb-3">
                  {item.description}
                </p>
              </div>

              {/* Bottom Tech & Console Deep Link */}
              <div className="pt-2 border-t border-[#334155]/50 space-y-2">
                <div className="text-[10px] font-mono text-[#8b909f] truncate" title={item.tech}>
                  {item.tech}
                </div>
                <a
                  href={item.consoleUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full py-1 px-2 rounded bg-[#060e20] hover:bg-[#1a73e8]/20 border border-[#334155] hover:border-[#adc7ff] text-[10px] font-mono text-[#adc7ff] flex items-center justify-between transition-all"
                >
                  <span>{item.consoleLabel}</span>
                  <ExternalLink className="w-3 h-3 text-[#8b909f]" />
                </a>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
