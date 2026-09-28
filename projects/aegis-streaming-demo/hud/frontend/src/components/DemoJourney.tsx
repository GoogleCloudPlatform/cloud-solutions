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

import React from 'react';
import {
  Layers,
  ExternalLink,
  Sparkles,
  CheckCircle2,
  DollarSign,
  Activity,
  Cpu,
  Bot,
  Database,
  ShieldCheck,
  Radio,
} from 'lucide-react';
import Link from 'next/link';
import { getConsoleLinks } from '../utils/gcpConsoleLinks';
import { getStackConfig } from '../utils/stackConfig';
import { PageNavigation } from './PageNavigation';

interface DemoStep {
  stepNumber: string;
  stepName: string;
  icon: React.ReactNode;

  // Column 1: Customer-Facing Key Points
  keyPoints: string[];

  // Column 2: Google Cloud Technical Capability
  techTitle: string;
  techSubtitle: string;
  techDescription: string;
  gcpServices: string[];
  consoleLink?: string;
  consoleLinkLabel?: string;

  // Column 3: Executive Business Value & ROI (C-Suite)
  businessMetric: string;
  businessMetricLabel: string;
  businessImpactTitle: string;
  businessValueNarrative: string;
  metricColor?: string;
}

export const DemoJourney: React.FC<{ onNavigate?: (tabId: string) => void }> = ({ onNavigate }) => {
  const links = getConsoleLinks();
  const stackConfig = getStackConfig();

  const demoSteps: DemoStep[] = [
    {
      stepNumber: '01',
      stepName: 'Edge Telemetry Ingestion',
      icon: <Radio className="w-4 h-4 text-[#68abff]" />,
      keyPoints: [
        stackConfig.stackType === 'oss'
          ? 'Streams real-time IIoT telemetry (core temperature, pressure, RPM, vibration) from 15 industrial assets into Google Cloud Managed Apache Kafka.'
          : 'Streams real-time IIoT telemetry (core temperature, pressure, RPM, vibration) from 15 industrial assets into Google Cloud Pub/Sub.',
        'Absorbs high-velocity sensor bursts with multi-zone durability and OAuth2 / IAM service authentication.',
        'Decouples edge equipment publishers from downstream stream processors with zero message loss.',
      ],
      techTitle: 'High-Throughput Elastic Ingestion',
      techSubtitle: stackConfig.ingestionName,
      techDescription:
        'Fully managed, multi-zone distributed event streaming capable of absorbing millions of IoT events per second with sub-second delivery guarantees and zero infrastructure overhead.',
      gcpServices: [stackConfig.ingestionName],
      consoleLink: links.ingestionConsole,
      consoleLinkLabel: `View ${stackConfig.ingestionShort} Console ↗`,
      businessMetric: '99.99%',
      businessMetricLabel: 'Ingestion Reliability',
      businessImpactTitle: 'Eliminates Data Silos & Blindspots',
      businessValueNarrative:
        'Guarantees zero data loss across thousands of global connected machines, ensuring complete operational visibility for executive leadership with zero infrastructure management costs.',
      metricColor: 'text-emerald-400',
    },
    {
      stepNumber: '02',
      stepName: 'Real-Time Vectorized Stream Compute',
      icon: <Cpu className="w-4 h-4 text-[#68abff]" />,
      keyPoints: [
        stackConfig.stackType === 'first_party'
          ? 'Evaluates 10-second fixed tumbling windows in Google Cloud Dataflow with 1-second early processing-time triggers.'
          : stackConfig.stackType === 'low_code'
          ? 'Evaluates 10-second tumbling SQL windows continuously in BigQuery Continuous Queries.'
          : `Evaluates 10-second tumbling windows on warm Dataproc Standard Spark cluster (${stackConfig.dataprocCluster}) accelerated by Vectorized Spark execution.`,
        'Computes rolling statistical drift and flags CRITICAL thermal or compute threshold breaches (>90%) in real time.',
        'Eliminates JVM garbage collection pauses and cold-start delays for continuous low-latency stream evaluation.',
      ],
      techTitle:
        stackConfig.stackType === 'oss'
          ? 'Warm Standard Cluster + Vectorized Spark'
          : 'Serverless Stream Processing',
      techSubtitle: stackConfig.pipelineName,
      techDescription:
        stackConfig.stackType === 'first_party'
          ? 'Serverless Apache Beam stream processing engine evaluating 10s fixed tumbling windows directly into Bigtable and BigQuery without managing clusters.'
          : stackConfig.stackType === 'low_code'
          ? 'Serverless continuous SQL evaluation engine processing 10s tumbling windows directly into Bigtable and BigQuery without managing infrastructure.'
          : 'Pre-warmed Dataproc Standard Spark cluster (1 Master + 2 Workers) with Vectorized Spark execution and pre-baked Kafka/Bigtable dependencies.',
      gcpServices:
        stackConfig.stackType === 'first_party'
          ? ['Cloud Dataflow', 'Apache Beam']
          : stackConfig.stackType === 'low_code'
          ? ['BigQuery Continuous Queries', 'Serverless SQL']
          : ['Dataproc Standard Cluster', 'Vectorized Spark Execution'],
      consoleLink: links.pipelineConsole,
      consoleLinkLabel: `View ${stackConfig.pipelineShort} Jobs ↗`,
      businessMetric: '73% Cut',
      businessMetricLabel: 'Compute TCO Reduction',
      businessImpactTitle: '4x Faster Streaming at Fraction of Cost',
      businessValueNarrative:
        'Processes streaming data 4x faster than legacy platforms while eliminating idle cloud spend, slashing data infrastructure bills by hundreds of thousands of dollars annually.',
      metricColor: 'text-emerald-400',
    },
    {
      stepNumber: '03',
      stepName: 'Dual-Sink Persistence',
      icon: <Database className="w-4 h-4 text-[#68abff]" />,
      keyPoints: [
        'Writes sub-millisecond operational state directly to Cloud Bigtable (telemetry_metrics) for live control loops.',
        'Streams historical window records into partitioned BigQuery tables (analytics.telemetry_events) for long-term analytics.',
        'Isolates high-frequency operational dashboard reads from heavy analytical SQL queries.',
      ],
      techTitle: 'Sub-Millisecond & Analytical Storage',
      techSubtitle: 'Cloud Bigtable + BigQuery Streaming',
      techDescription:
        'Decoupled architecture delivering <5ms operational reads/writes using Bigtable alongside continuous analytical ingestion into BigQuery partitioned tables.',
      gcpServices: ['Cloud Bigtable', 'BigQuery Storage API'],
      consoleLink: links.bigtableTable,
      consoleLinkLabel: 'View Bigtable Instance ↗',
      businessMetric: '< 5 ms',
      businessMetricLabel: 'Operational Latency',
      businessImpactTitle: 'Instant Plant Visibility Without Lag',
      businessValueNarrative:
        'Provides operators and plant executives with real-time equipment status without dashboard lag, preventing costly blind spots while fulfilling compliance reporting.',
      metricColor: 'text-[#68abff]',
    },
    {
      stepNumber: '04',
      stepName: 'Operations HUD & Anomaly Injection',
      icon: <Activity className="w-4 h-4 text-amber-400" />,
      keyPoints: [
        'Streams live state updates from Cloud Bigtable to the Operations HUD over Server-Sent Events (SSE).',
        'Supports on-demand chaos fault injection across the 15-asset fleet to test end-to-end anomaly detection.',
        'Automatically surfaces critical thermal and compute alerts in under 1 second as soon as thresholds are breached.',
      ],
      techTitle: 'Reactive Operational Command Center',
      techSubtitle: 'Next.js HUD & Cloud Run SSE Subscriptions',
      techDescription:
        'Live streaming dashboard consuming Server-Sent Events (SSE) from Cloud Run backend microservices, enabling millisecond alert dispatch and on-demand synthetic chaos injection.',
      gcpServices: ['Cloud Run Microservices', 'Server-Sent Events (SSE)'],
      consoleLink: links.hudBackendRun,
      consoleLinkLabel: 'View Cloud Run Backend ↗',
      businessMetric: '< 1 Sec',
      businessMetricLabel: 'Mean Time to Detect (MTTD)',
      businessImpactTitle: 'Proactive Early Failure Detection',
      businessValueNarrative:
        'Shrinks failure detection time from hours of manual inspection to under 1 second, catching mechanical stress before it turns into catastrophic factory shutdowns.',
      metricColor: 'text-amber-400',
    },
    {
      stepNumber: '05',
      stepName: 'Cognitive RCA (Human-In-The-Loop)',
      icon: <Bot className="w-4 h-4 text-amber-400" />,
      keyPoints: [
        'Sanitizes inbound telemetry alerts through Model Armor to mask PII and block prompt injection attacks.',
        'Invokes Gemini 2.5 Flash on Gemini Enterprise Agent Platform (GEAP) to perform multi-step root-cause analysis.',
        'Presents a structured 3-step mitigation plan for Human-in-the-Loop (HITL) operator review prior to actuation.',
      ],
      techTitle: 'Enterprise Agent Platform & Model Armor',
      techSubtitle: 'Gemini 2.5 Flash Reasoning Engine',
      techDescription:
        'Enterprise Agent Platform (GEAP) reasoning agent with structured Pydantic schema enforcement and Model Armor security guardrails to sanitize payloads against prompt injection.',
      gcpServices: ['Gemini Enterprise Agent Platform', 'Model Armor'],
      consoleLink: links.geminiEnterpriseAgentPlatform,
      consoleLinkLabel: 'View Deployed Agent ↗',
      businessMetric: '< 800 ms',
      businessMetricLabel: 'AI Diagnostic Time',
      businessImpactTitle: 'Avoids $5,000/Hour In Downtime Costs',
      businessValueNarrative:
        'Eliminates expensive engineering escalation delays by diagnosing root causes in milliseconds, protecting against $5,000+ per hour in unplanned downtime while keeping human engineers in full control.',
      metricColor: 'text-amber-400',
    },
    {
      stepNumber: '06',
      stepName: 'Agentic Governance & ROI Accounting',
      icon: <DollarSign className="w-4 h-4 text-emerald-400" />,
      keyPoints: [
        'Tracks prompt tokens, completion tokens, inference latency, and exact USD cost for every AI diagnostic run.',
        'Logs complete financial tokenomics and net downtime savings to BigQuery (analytics.rca_events).',
        'Provides auditable governance linking every autonomous recommendation to measurable business ROI.',
      ],
      techTitle: 'Granular Tokenomics & Financial Audit',
      techSubtitle: 'BigQuery Agent Analytics SDK',
      techDescription:
        'Continuous streaming insertion of agent diagnostic runs, token consumption, execution latency, and USD cost into BigQuery rca_events audit tables.',
      gcpServices: ['BigQuery Analytics', 'Reasoning Engine Runtime'],
      consoleLink: links.bigqueryRcaTable,
      consoleLinkLabel: 'Query rca_events Table ↗',
      businessMetric: '52,000x',
      businessMetricLabel: 'Proven AI Return on Investment',
      businessImpactTitle: 'Quantifiable Proof of Financial Value',
      businessValueNarrative:
        'Proves that a $0.000096 AI query saved $5,000 in equipment damage—giving the CFO complete financial governance and unquestionable ROI on AI investments.',
      metricColor: 'text-emerald-400',
    },
    {
      stepNumber: '07',
      stepName: 'Closed-Loop Mitigation & Recovery',
      icon: <ShieldCheck className="w-4 h-4 text-emerald-400" />,
      keyPoints: [
        'Executes IndustrialActuatorTool.throttle_and_cool upon operator approval using authenticated OIDC service calls.',
        'Flushes cooling valves, throttles compute load, and restores physical asset telemetry to nominal green baseline.',
        'Synchronizes recovered asset state through Cloud Bigtable back to the live Operations HUD.',
      ],
      techTitle: 'Closed-Loop Industrial Actuation',
      techSubtitle: 'Secure Microservice Actuation Plane',
      techDescription:
        'Authenticated control plane API dispatching hardware control signals directly to industrial equipment, updating state in Bigtable and closing the operational loop.',
      gcpServices: ['Cloud Run Actuation API', 'Cloud Bigtable Sink'],
      consoleLink: links.hudBackendRun,
      consoleLinkLabel: 'View Actuation Backend ↗',
      businessMetric: '100% Auto',
      businessMetricLabel: 'Closed-Loop Recovery',
      businessImpactTitle: 'Zero-Downtime Autonomous Self-Healing',
      businessValueNarrative:
        'Shortens Mean Time to Resolution (MTTR) from hours to seconds, completely preventing hardware burnouts and saving $50,000+ in replacement machinery costs.',
      metricColor: 'text-emerald-400',
    },
  ];

  return (
    <div className="w-full space-y-6">
      {/* Module Header & KPI Summary Strip */}
      <section className="w-full glass-panel rounded-2xl p-6 space-y-5">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 rounded-lg bg-[#1a73e8]/15 border border-[#1a73e8]/30 text-[#68abff]">
                <Layers className="w-4 h-4" />
              </div>
              <h2 className="text-lg md:text-xl font-headline font-bold text-white uppercase tracking-wide">
                Module 3: End-to-End Architecture &amp; Demo Guide
              </h2>
              <span className="px-2.5 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#1a73e8]/15 text-[#68abff] border border-[#1a73e8]/35">
                7-STAGE BLUEPRINT
              </span>
            </div>
            <p className="text-xs md:text-sm text-[#94a3b8] font-sans mt-1">
              Key operational capabilities, Google Cloud architecture components, and executive business ROI across the 7 stages of Project Aegis.
            </p>
          </div>

          <Link
            href="/grid"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1a73e8] hover:bg-[#1557b0] text-white font-mono text-xs uppercase tracking-wider font-bold transition-all shadow-md shadow-[#1a73e8]/25 shrink-0"
          >
            <span>Proceed to 4. Live Grid ↗</span>
          </Link>
        </div>

        {/* 4-Metric Executive Summary Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-xl bg-[#070d19] border border-white/[0.08]">
            <span className="text-[10px] font-mono text-[#64748b] uppercase tracking-wider block">
              End-to-End Flow
            </span>
            <span className="text-base font-mono font-bold text-white tabular-nums mt-0.5 block">
              7 Autonomous Stages
            </span>
          </div>
          <div className="p-3.5 rounded-xl bg-[#070d19] border border-white/[0.08]">
            <span className="text-[10px] font-mono text-[#64748b] uppercase tracking-wider block">
              Operational State Latency
            </span>
            <span className="text-base font-mono font-bold text-[#68abff] tabular-nums mt-0.5 block">
              &lt; 5 Milliseconds
            </span>
          </div>
          <div className="p-3.5 rounded-xl bg-[#070d19] border border-white/[0.08]">
            <span className="text-[10px] font-mono text-[#64748b] uppercase tracking-wider block">
              Downtime Prevented
            </span>
            <span className="text-base font-mono font-bold text-emerald-400 tabular-nums mt-0.5 block">
              $5,000+ / Incident
            </span>
          </div>
          <div className="p-3.5 rounded-xl bg-[#070d19] border border-white/[0.08]">
            <span className="text-[10px] font-mono text-[#64748b] uppercase tracking-wider block">
              AI Inference Cost
            </span>
            <span className="text-base font-mono font-bold text-amber-400 tabular-nums mt-0.5 block">
              &lt; $0.0001 USD
            </span>
          </div>
        </div>
      </section>

      {/* 7-Step Vertical Timeline & 3-Column Matrix */}
      <section className="w-full glass-panel rounded-2xl p-6 space-y-5">
        {/* Column Headers (Visible on Desktop) */}
        <div className="hidden lg:grid grid-cols-12 gap-6 pb-3 border-b border-white/[0.08] text-xs font-mono font-bold uppercase tracking-widest text-[#94a3b8] pl-14">
          <div className="col-span-5 flex items-center gap-2 text-white">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span>1. Key Points</span>
          </div>
          <div className="col-span-4 flex items-center gap-2 text-[#68abff]">
            <Cpu className="w-4 h-4 text-[#68abff]" />
            <span>2. Google Cloud Technical Capability</span>
          </div>
          <div className="col-span-3 flex items-center gap-2 text-emerald-400">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span>3. Executive Business ROI</span>
          </div>
        </div>

        {/* Timeline Steps */}
        <div className="relative space-y-4">
          {/* Vertical Spine on Desktop */}
          <div className="hidden lg:block absolute left-5 top-6 bottom-6 w-px bg-gradient-to-b from-[#1a73e8] via-[#1a73e8]/40 to-emerald-500/40" />

          {demoSteps.map((step, idx) => (
            <div key={idx} className="relative flex items-start gap-4">
              {/* Step Number Node on Timeline */}
              <div className="hidden lg:flex items-center justify-center w-10 h-10 rounded-xl bg-[#0b1326] border border-[#1a73e8]/50 text-[#68abff] font-mono text-xs font-bold tabular-nums shrink-0 mt-4 z-10 shadow-md">
                {step.stepNumber}
              </div>

              {/* 3-Column Card */}
              <div className="flex-1 p-5 rounded-xl bg-[#070d19]/90 border border-white/[0.08] hover:border-white/20 transition-all">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                  {/* Column 1 (5 cols): Key Points */}
                  <div className="lg:col-span-5 space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="lg:hidden px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-[#1a73e8]/20 text-[#68abff] border border-[#1a73e8]/40 tabular-nums">
                        {step.stepNumber}
                      </span>
                      {step.icon}
                      <h3 className="text-sm font-headline font-bold text-white">
                        {step.stepName}
                      </h3>
                    </div>

                    <ul className="space-y-2">
                      {step.keyPoints.map((point, pIdx) => (
                        <li
                          key={pIdx}
                          className="flex items-start gap-2 text-xs font-sans text-[#cbd5e1] leading-relaxed"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 text-[#68abff] shrink-0 mt-0.5" />
                          <span>{point}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Column 2 (4 cols): Google Cloud Technical Capability */}
                  <div className="lg:col-span-4 space-y-3 lg:border-l lg:border-white/[0.08] lg:pl-6 pt-3 lg:pt-0 border-t lg:border-t-0 border-white/[0.08]">
                    <div>
                      <h4 className="text-sm font-headline font-bold text-white">
                        {step.techTitle}
                      </h4>
                      <span className="text-xs font-mono text-[#68abff] block mt-0.5">
                        {step.techSubtitle}
                      </span>
                    </div>

                    <p className="text-xs font-sans text-[#94a3b8] leading-relaxed">
                      {step.techDescription}
                    </p>

                    <div className="pt-1 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap gap-1.5">
                        {step.gcpServices.map((svc, sIdx) => (
                          <span
                            key={sIdx}
                            className="px-2 py-0.5 rounded text-[10px] font-mono text-[#cbd5e1] bg-white/[0.04] border border-white/[0.08]"
                          >
                            {svc}
                          </span>
                        ))}
                      </div>

                      {step.consoleLink && (
                        <a
                          href={step.consoleLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#1a73e8]/15 hover:bg-[#1a73e8] text-[#68abff] hover:text-white border border-[#1a73e8]/35 font-mono text-[10px] uppercase tracking-wider font-bold transition-all shrink-0"
                        >
                          <ExternalLink className="w-3 h-3" />
                          <span>{step.consoleLinkLabel || 'Console ↗'}</span>
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Column 3 (3 cols): Executive Business ROI */}
                  <div className="lg:col-span-3 space-y-2 lg:border-l lg:border-white/[0.08] lg:pl-6 pt-3 lg:pt-0 border-t lg:border-t-0 border-white/[0.08]">
                    <div className="flex items-baseline justify-between gap-2">
                      <span
                        className={`text-2xl font-mono font-bold tabular-nums tracking-tight ${
                          step.metricColor || 'text-emerald-400'
                        }`}
                      >
                        {step.businessMetric}
                      </span>
                      <span className="text-[10px] font-mono uppercase tracking-wider text-[#64748b]">
                        {step.businessMetricLabel}
                      </span>
                    </div>

                    <h4 className="text-xs font-headline font-bold text-white uppercase tracking-wide">
                      {step.businessImpactTitle}
                    </h4>

                    <p className="text-xs font-sans text-[#94a3b8] leading-relaxed">
                      {step.businessValueNarrative}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Step Navigation to Prev (2. Stream Simulator) & Next (4. Live Grid) */}
      <PageNavigation
        prevTab={{ id: 'simulator', label: '2. Stream Simulator' }}
        nextTab={{ id: 'grid', label: '4. Live Grid & AI Co-Pilot' }}
        onNavigate={onNavigate}
      />
    </div>
  );
};

export default DemoJourney;
