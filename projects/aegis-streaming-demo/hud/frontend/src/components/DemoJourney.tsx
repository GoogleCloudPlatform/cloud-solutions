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
  TrendingUp,
  DollarSign,
  Activity,
  Cpu,
  Bot,
  Database,
  ShieldCheck,
  Zap,
  Radio,
  ArrowRight
} from 'lucide-react';
import Link from 'next/link';
import { getConsoleLinks } from '../utils/gcpConsoleLinks';
import { PageNavigation } from './PageNavigation';

interface DemoStep {
  stepNumber: string;
  stepName: string;
  icon: React.ReactNode;

  // Column 1: Demo Script & Live Action
  demoActionTitle: string;
  demoScript: string;
  screenTip?: string;

  // Column 2: GCP Technical Capability
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
  roiPillColor?: string;
}

export const DemoJourney: React.FC<{ onNavigate?: (tabId: string) => void }> = ({ onNavigate }) => {
  const links = getConsoleLinks();

  const demoSteps: DemoStep[] = [
    {
      stepNumber: '01',
      stepName: 'Edge Telemetry Ingestion',
      icon: <Radio className="w-5 h-5 text-[#adc7ff]" />,
      demoActionTitle: 'Start Stream on Previous Page',
      demoScript:
        '“The telemetry simulation service we started on the previous page is continuously streaming real-time IIoT sensor packets—such as core temperature, pressure, RPM, and vibration—from 15 industrial assets directly into Google Cloud Managed Apache Kafka.”',
      screenTip: 'Show active message rate in Stream Simulator or Kafka console.',
      techTitle: 'High-Throughput Elastic Ingestion',
      techSubtitle: 'Managed Apache Kafka & Cloud Pub/Sub',
      techDescription:
        'Fully managed, multi-zone distributed event streaming capable of absorbing millions of IoT events per second with sub-second delivery guarantees and zero infrastructure overhead.',
      gcpServices: ['Managed Apache Kafka', 'Cloud Pub/Sub'],
      consoleLink: links.kafkaCluster,
      consoleLinkLabel: 'View Kafka Cluster ↗',
      businessMetric: '99.99%',
      businessMetricLabel: 'Ingestion Reliability',
      businessImpactTitle: 'Eliminates Data Silos & Blindspots',
      businessValueNarrative:
        'Guarantees zero data loss across thousands of global connected machines, ensuring complete operational visibility for executive leadership with zero infrastructure management costs.',
      roiPillColor: 'text-[#6ddd81] bg-[#132d1e] border-[#30a550]'
    },
    {
      stepNumber: '02',
      stepName: 'Real-Time Vectorized Stream Compute',
      icon: <Cpu className="w-5 h-5 text-[#93b2ff]" />,
      demoActionTitle: 'Automated Tumbling-Window Evaluation',
      demoScript:
        '“In the background, Google Cloud Managed Spark continuously processes the stream in 10-second tumbling windows, calculating baseline statistical drift and detecting threshold anomalies the instant equipment begins to fail.”',
      screenTip: 'Point out sub-second latency from ingestion to evaluation.',
      techTitle: 'Serverless Stream Processing',
      techSubtitle: 'Managed Spark with C++ Lightning Engine (Velox)',
      techDescription:
        'Serverless stream processing engine accelerated by native C++ vectorization (Velox/Gluten), evaluating rolling anomaly detection windows without managing clusters.',
      gcpServices: ['Dataproc Serverless Spark', 'Velox C++ Engine'],
      consoleLink: links.dataprocBatches,
      consoleLinkLabel: 'View Managed Spark Jobs ↗',
      businessMetric: '73% Cut',
      businessMetricLabel: 'Compute TCO Reduction',
      businessImpactTitle: '4x Faster Streaming at Fraction of Cost',
      businessValueNarrative:
        'Processes streaming data 4x faster than legacy platforms while eliminating idle cloud spend, slashing data infrastructure bills by hundreds of thousands of dollars annually.',
      roiPillColor: 'text-[#6ddd81] bg-[#132d1e] border-[#30a550]'
    },
    {
      stepNumber: '03',
      stepName: 'Dual-Sink Persistence',
      icon: <Database className="w-5 h-5 text-[#adc7ff]" />,
      demoActionTitle: 'Dual Operational & Analytical Storage',
      demoScript:
        '“The stream branches automatically into two dedicated storage engines: sub-millisecond operational state writes into Cloud Bigtable for instant monitoring, while historical event records flow into BigQuery for enterprise-wide analytics.”',
      screenTip: 'Explain separation of live plant operations from enterprise BI.',
      techTitle: 'Sub-Millisecond & Analytical Storage',
      techSubtitle: 'Cloud Bigtable + BigQuery Streaming',
      techDescription:
        'Decoupled architecture delivering <5ms operational reads/writes via Bigtable alongside continuous analytical ingestion into BigQuery partitioned tables.',
      gcpServices: ['Cloud Bigtable', 'BigQuery Storage API'],
      consoleLink: links.bigtableTable,
      consoleLinkLabel: 'View Bigtable Instance ↗',
      businessMetric: '< 5 ms',
      businessMetricLabel: 'Operational Latency',
      businessImpactTitle: 'Instant Plant Visibility Without Lag',
      businessValueNarrative:
        'Provides operators and plant executives with real-time equipment status without dashboard lag, preventing costly blind spots while fulfilling compliance reporting automatically.',
      roiPillColor: 'text-[#adc7ff] bg-[#131b2e] border-[#1a73e8]'
    },
    {
      stepNumber: '04',
      stepName: 'Operations HUD & Anomaly Injection',
      icon: <Activity className="w-5 h-5 text-[#FBBC04]" />,
      demoActionTitle: 'Live Grid & Inject Anomaly',
      demoScript:
        '“On the next page (Live Grid), operators watch all 15 industrial machines in real time. We click ‘Inject Anomaly’ to trigger a random equipment fault (e.g. coolant valve malfunction) without knowing which asset was chosen, and watch the system automatically detect and flag the affected asset.”',
      screenTip: 'Demonstrate live state transition from green nominal to red critical on whichever asset was randomly selected.',
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
      roiPillColor: 'text-[#FBBC04] bg-[#2e2305] border-[#FBBC04]'
    },
    {
      stepNumber: '05',
      stepName: 'Cognitive RCA (Human-In-The-Loop)',
      icon: <Bot className="w-5 h-5 text-[#ffb691]" />,
      demoActionTitle: 'Summon Gemini 2.5 Flash Co-Pilot',
      demoScript:
        '“When the alarm fires, the operator summons the AI Co-Pilot. Powered by Gemini 2.5 Flash, the agent analyzes live sensor drift, confirms a coolant line blockage, and proposes a verified 3-step mitigation plan.”',
      screenTip: 'Highlight the human-in-the-loop review interface before action execution.',
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
      roiPillColor: 'text-[#ffb691] bg-[#2e1505] border-[#ff8c42]'
    },
    {
      stepNumber: '06',
      stepName: 'Agentic Governance & ROI Accounting',
      icon: <DollarSign className="w-5 h-5 text-[#6ddd81]" />,
      demoActionTitle: 'Approve Mitigation & Record Audit',
      demoScript:
        '“The operator clicks ‘Approve & Execute Mitigation’. The agent runs the remediation tools and automatically logs complete tokenomics, diagnostic rationale, and financial savings directly to BigQuery for auditability.”',
      screenTip: 'Show BigQuery token accounting metrics and financial ROI summary.',
      techTitle: 'Granular Tokenomics & Financial Audit',
      techSubtitle: 'BigQuery Agent Analytics SDK',
      techDescription:
        'Automatic streaming insertion of agent diagnostic runs, token consumption, execution latency, and USD cost into BigQuery rca_events audit tables.',
      gcpServices: ['BigQuery Analytics', 'Reasoning Engine Runtime'],
      consoleLink: links.bigqueryRcaTable,
      consoleLinkLabel: 'Query rca_events Table ↗',
      businessMetric: '52,000x',
      businessMetricLabel: 'Proven AI Return on Investment',
      businessImpactTitle: 'Quantifiable Proof of Financial Value',
      businessValueNarrative:
        'Proves that a $0.000096 AI query saved $5,000 in equipment damage—giving the CFO complete financial governance and unquestionable ROI on AI investments.',
      roiPillColor: 'text-[#6ddd81] bg-[#132d1e] border-[#30a550]'
    },
    {
      stepNumber: '07',
      stepName: 'Closed-Loop Mitigation & Recovery',
      icon: <ShieldCheck className="w-5 h-5 text-[#6ddd81]" />,
      demoActionTitle: 'Inspect Asset Status Return to Green',
      demoScript:
        '“The actuator tool dispatches corrective commands to the industrial equipment—flushing the valve and throttling engine load. In seconds, the anomalous asset returns to safe operating temperature and nominal green status.”',
      screenTip: 'Point to the affected asset temperature dropping and badge returning to green NOMINAL.',
      techTitle: 'Closed-Loop Industrial Actuation',
      techSubtitle: 'Secure Microservice Actuation Plane',
      techDescription:
        'Authenticated control plane API dispatching hardware control signals directly to industrial equipment, automatically updating state in Bigtable and closing the operational loop.',
      gcpServices: ['Cloud Run Actuation API', 'Cloud Bigtable Sink'],
      consoleLink: links.hudBackendRun,
      consoleLinkLabel: 'View Actuation Backend ↗',
      businessMetric: '100% Auto',
      businessMetricLabel: 'Closed-Loop Recovery',
      businessImpactTitle: 'Zero-Downtime Autonomous Self-Healing',
      businessValueNarrative:
        'Shortens Mean Time to Resolution (MTTR) from hours to seconds, completely preventing hardware burnouts and saving $50,000+ in replacement machinery costs.',
      roiPillColor: 'text-[#6ddd81] bg-[#132d1e] border-[#30a550]'
    }
  ];

  return (
    <div className="w-full space-y-6">
      {/* Module Banner & Header */}
      <section className="w-full glass-panel rounded-2xl p-6 border border-[#334155] shadow-xl relative overflow-hidden">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-[#334155]">
          <div>
            <div className="flex items-center gap-2">
              <Layers className="w-5 h-5 text-[#adc7ff]" />
              <h2 className="text-lg md:text-xl font-headline font-bold text-white uppercase tracking-wide">
                Module 3: End-to-End Customer Engineering Demo Guide
              </h2>
              <span className="px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-[#1a73e8]/20 text-[#adc7ff] border border-[#1a73e8]/50">
                7-STEP DEMO BLUEPRINT
              </span>
            </div>
            <p className="text-xs md:text-sm text-[#c1c6d6] font-sans mt-1">
              Presenter talk tracks, Google Cloud technical architecture capabilities, and executive business ROI for each stage of the live demonstration.
            </p>
          </div>

          {/* Direct Link to Live Grid */}
          <Link
            href="/grid"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1a73e8] hover:bg-[#005bc0] text-white font-mono text-xs uppercase tracking-wider font-bold transition-all shadow-md shrink-0"
          >
            <span>Proceed to 4. Live Grid ↗</span>
          </Link>
        </div>

        {/* Quick Summary Pill Bar */}
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-[#0b1326] border border-[#334155]/60 text-center">
            <span className="text-[10px] font-mono text-[#8b909f] uppercase tracking-wider block">Total Demo Time</span>
            <span className="text-sm font-mono font-bold text-white">~10 Minutes</span>
          </div>
          <div className="p-3 rounded-xl bg-[#0b1326] border border-[#334155]/60 text-center">
            <span className="text-[10px] font-mono text-[#8b909f] uppercase tracking-wider block">Target Audience</span>
            <span className="text-sm font-mono font-bold text-[#adc7ff]">CXOs &amp; Lead Architects</span>
          </div>
          <div className="p-3 rounded-xl bg-[#0b1326] border border-[#334155]/60 text-center">
            <span className="text-[10px] font-mono text-[#8b909f] uppercase tracking-wider block">Downtime Prevented</span>
            <span className="text-sm font-mono font-bold text-[#6ddd81]">$5,000+ / Incident</span>
          </div>
          <div className="p-3 rounded-xl bg-[#0b1326] border border-[#334155]/60 text-center">
            <span className="text-[10px] font-mono text-[#8b909f] uppercase tracking-wider block">AI Inference Cost</span>
            <span className="text-sm font-mono font-bold text-[#fbbf24]">&lt; $0.0001 USD</span>
          </div>
        </div>
      </section>

      {/* 3-Column x 7-Row Master Demo Table / Cards */}
      <section className="w-full glass-panel rounded-2xl p-6 border border-[#334155] shadow-xl space-y-4">
        {/* Table Header (Visible on Desktop / Tablet Landscape) */}
        <div className="hidden lg:grid grid-cols-12 gap-4 pb-3 border-b border-[#334155] text-xs font-mono font-bold uppercase tracking-widest text-[#8b909f]">
          <div className="col-span-5 flex items-center gap-2 text-[#dae2fd]">
            <Sparkles className="w-4 h-4 text-[#FBBC04]" />
            <span>1. Presenter Demo Script &amp; Live Action</span>
          </div>
          <div className="col-span-4 flex items-center gap-2 text-[#adc7ff]">
            <Cpu className="w-4 h-4 text-[#adc7ff]" />
            <span>2. GCP Technical Capability</span>
          </div>
          <div className="col-span-3 flex items-center gap-2 text-[#6ddd81]">
            <DollarSign className="w-4 h-4 text-[#6ddd81]" />
            <span>3. Executive Business ROI</span>
          </div>
        </div>

        {/* 7 Rows */}
        <div className="space-y-4">
          {demoSteps.map((step, idx) => (
            <div
              key={idx}
              className="p-5 rounded-xl bg-[#060e20] border border-[#334155]/80 hover:border-[#adc7ff]/50 transition-all shadow-md"
            >
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

                {/* Column 1 (5 cols): Presenter Demo Script & Live Action */}
                <div className="lg:col-span-5 space-y-3">
                  <div className="flex items-center gap-2.5">
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase tracking-widest bg-[#131b2e] text-[#adc7ff] border border-[#334155]">
                      STEP {step.stepNumber}
                    </span>
                    <div className="flex items-center gap-2">
                      {step.icon}
                      <h3 className="text-sm font-headline font-bold text-white">
                        {step.stepName}
                      </h3>
                    </div>
                  </div>

                  {/* Demo Script Quote Block */}
                  <div className="p-3.5 rounded-lg bg-[#0b1326] border border-[#1a73e8]/30 space-y-2">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-[#adc7ff] font-bold flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#adc7ff]" />
                      <span>{step.demoActionTitle}</span>
                    </div>
                    <p className="text-xs font-sans text-[#e2e8f0] leading-relaxed italic">
                      {step.demoScript}
                    </p>
                  </div>

                  {step.screenTip && (
                    <div className="text-[11px] font-sans text-[#8b909f] flex items-center gap-1.5 pl-1">
                      <span className="text-[#FBBC04] font-bold">💡 Tip:</span>
                      <span>{step.screenTip}</span>
                    </div>
                  )}
                </div>

                {/* Column 2 (4 cols): GCP Technical Capability */}
                <div className="lg:col-span-4 space-y-3 lg:border-l lg:border-[#334155]/60 lg:pl-6 pt-3 lg:pt-0 border-t lg:border-t-0 border-[#334155]/40">
                  <div className="space-y-1">
                    <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#adc7ff] block">
                      Platform Capability:
                    </span>
                    <h4 className="text-sm font-headline font-bold text-white">
                      {step.techTitle}
                    </h4>
                    <span className="text-xs font-mono text-[#93b2ff] block">
                      {step.techSubtitle}
                    </span>
                  </div>

                  <p className="text-xs font-sans text-[#c1c6d6] leading-relaxed">
                    {step.techDescription}
                  </p>

                  {/* GCP Tech Badges & Console Deep Link */}
                  <div className="pt-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap gap-1">
                      {step.gcpServices.map((svc, sIdx) => (
                        <span
                          key={sIdx}
                          className="px-2 py-0.5 rounded text-[9px] font-mono text-[#8b909f] bg-[#0a0f1d] border border-[#334155]"
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
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#1a73e8] hover:bg-[#005bc0] text-white font-mono text-[10px] uppercase tracking-wider font-bold transition-all shadow-sm shrink-0"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>{step.consoleLinkLabel || 'GCP Console ↗'}</span>
                      </a>
                    )}
                  </div>
                </div>

                {/* Column 3 (3 cols): Executive Business ROI (C-Suite) */}
                <div className="lg:col-span-3 space-y-3 lg:border-l lg:border-[#334155]/60 lg:pl-6 pt-3 lg:pt-0 border-t lg:border-t-0 border-[#334155]/40 flex flex-col justify-between h-full">
                  <div className="space-y-2">
                    {/* ROI Highlight Pill */}
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#6ddd81]">
                        Executive Value:
                      </span>
                      <div className={`px-2.5 py-1 rounded-lg border text-xs font-mono font-bold uppercase tracking-wider flex items-center gap-1 ${step.roiPillColor || 'text-[#6ddd81] bg-[#132d1e] border-[#30a550]'}`}>
                        <TrendingUp className="w-3.5 h-3.5" />
                        <span>{step.businessMetric}</span>
                      </div>
                    </div>

                    <h4 className="text-xs font-headline font-bold text-white uppercase tracking-wide">
                      {step.businessImpactTitle}
                    </h4>

                    <p className="text-xs font-sans text-[#dae2fd] leading-relaxed">
                      {step.businessValueNarrative}
                    </p>
                  </div>

                  <div className="pt-2 text-[10px] font-mono text-[#8b909f] border-t border-[#334155]/30">
                    ROI Focus: <span className="text-white font-semibold">{step.businessMetricLabel}</span>
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
