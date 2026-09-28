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

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Image from 'next/image';
import {
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Download,
  ExternalLink,
  Presentation,
  Play,
  Pause,
  Grid,
  Sparkles,
  CheckCircle2
} from 'lucide-react';
import { PageNavigation } from './PageNavigation';
import { getStackConfig, StackConfig } from '../utils/stackConfig';

interface SlideMeta {
  number: number;
  title: string;
  category: string;
  image: string;
  description: string;
  keyHighlights: string[];
}

export const getSlidesData = (stackConfig: StackConfig): SlideMeta[] => {
  const coreSlides: SlideMeta[] = [
  {
    number: 1,
    title: 'The Agentic Data Cloud: Project Aegis',
    category: 'Executive Vision',
    image: '/slides/slide-1.png',
    description: 'Autonomous Streaming & Real-Time Agentic Context Engines with Project Aegis: Turning Passive Telemetry into Real-Time Systems of Action.',
    keyHighlights: [
      'Sub-second telemetry ingestion for mission-critical IIoT fleets',
      'Cognitive Closed-Loop Remediation powered by Gemini 2.5 Flash',
      'Zero-loss operational state persistence on Cloud Bigtable'
    ]
  },
  {
    number: 2,
    title: 'Cloud Architecture Optimization & ROI',
    category: 'Business Value & Benchmarks',
    image: '/slides/slide-2.png',
    description: 'Resolving critical latency, JVM garbage collection overhead, and cost bottlenecks with Google Cloud blueprints.',
    keyHighlights: [
      '50-73% Dataflow compute cost reduction via At-Least-Once streaming',
      '4.9x Spark execution speedup with C++ Velox Lightning Engine',
      '34% BigQuery slot optimization with Continuous Queries',
      '63% Agent accuracy improvement using ADK & structured Pydantic schemas'
    ]
  },
  {
    number: 3,
    title: 'Decoupled 5-Tier Reference Architecture',
    category: 'Enterprise Topology',
    image: '/slides/slide-3.png',
    description: 'A decoupled five-tier logical framework mapping the path of data, insights, and autonomous mitigation actions.',
    keyHighlights: [
      'Layer 1: Managed Service for Apache Kafka & Cloud Pub/Sub with AI SMTs',
      'Layer 2: Dataproc Serverless (C++ Velox) & Dataflow Stream Compute',
      'Layer 3: BigQuery Continuous Queries & Apache Iceberg Lakehouses',
      'Layer 4: Cognitive AI Platform (ADK, MCP Gateways, A2A Handshakes)',
      'Layer 5: Governance & Security (Model Armor & OpenLineage Traceability)'
    ]
  },
  {
    number: 4,
    title: 'Project Aegis Implementation Pipeline',
    category: 'Operational Journey',
    image: '/slides/slide-4.png',
    description: 'An orchestrating autonomous closed-loop mitigation journey powered by Google Cloud and Gemini 2.5 Flash.',
    keyHighlights: [
      'Mock Fleet: Sub-second asynchronous publishing to telemetry-raw',
      stackConfig.stackType === 'first_party'
        ? 'Cloud Pub/Sub: Low-latency distributed message buffering'
        : stackConfig.stackType === 'low_code'
        ? 'Cloud Pub/Sub: Real-time streaming ingestion directly to BigQuery'
        : 'Managed Kafka: Partition-isolated high-throughput buffering',
      stackConfig.stackType === 'first_party'
        ? 'Cloud Dataflow: 10s fixed tumbling window anomaly detection (>90% CPU / Temp / Pressure)'
        : stackConfig.stackType === 'low_code'
        ? 'Continuous Queries: 10s tumbling SQL anomaly detection (>90% CPU / Temp / Pressure)'
        : 'Spark Serverless: 10s rolling window anomaly detection (>90% CPU / Temp / Pressure)',
      'Bigtable: Sub-millisecond state store for live control loops',
      'Experience Layer: Reactive Next.js & FastAPI Operations HUD with Human-in-the-Loop'
    ]
  },
  {
    number: 5,
    title: 'Next-Gen Google Cloud Streaming Stack',
    category: '2026 Technology Shifts',
    image: '/slides/slide-5.png',
    description: '2026 architectural shifts eliminating legacy bottlenecks across Ingestion, Compute, Analytics, AI, and Governance.',
    keyHighlights: [
      'Zero-Latency Classification: AI Inference Single Message Transforms',
      'Bypassing JVM Barriers: Dataproc Serverless native C++ vectorization',
      'Continuous Warehouse SQL: Live active stream evaluations in BigQuery',
      'Secure Model Reasoning: ADK runtime + YAML tool specifications',
      'Fortified Lineage: Dataplex Knowledge Catalog and Model Armor protection'
    ]
  },
  {
    number: 6,
    title: 'Architectural Shift to Agentic Data Cloud',
    category: 'Legacy vs. 2026 Pattern',
    image: '/slides/slide-6.png',
    description: 'Unlocking massive efficiencies and performance upgrades over legacy 2022-2025 distributed data architectures.',
    keyHighlights: [
      'Dynamic Processing: Constructs custom execution paths & queries on-the-fly',
      'Near-Zero-Overhead AI: In-transit predictions via AI SMTs and Continuous SQL',
      'No Idle Infrastructure: Slashing compute costs up to 73%',
      'C++ Vectorized Compute: 4.9x faster execution without cold starts or GC pauses',
      'Dynamic Model Armor: Zero-day prompt injection and PII leak protection'
    ]
  }
  ];

  const ossTopologySlide: Omit<SlideMeta, 'number'> = {
    title: 'Aegis Telemetry Streaming - Open Source Stack',
    category:
      stackConfig.stackType === 'oss'
        ? 'Active Blueprint: Open Source Stack'
        : 'Alternative Blueprint: Open Source Stack',
    image: '/slides/slide-7.png',
    description:
      '7-Step Open Source Reference Architecture: Managed Apache Kafka + Dataproc Serverless (Spark with C++ Lightning Engine) + Dual-Sink Bigtable/BigQuery + Vertex AI Remediation Agent.',
    keyHighlights: [
      '1. Ingestion: Monitored fleet streams real-time telemetry into Managed Apache Kafka (telemetry-raw).',
      '2. Stream Processing: Managed Spark with C++ Lightning Engine evaluates 10s tumbling windows.',
      '3. Dual-Sink Persistence: Sub-ms operational state lands in Cloud Bigtable; analytical audits sink to BigQuery.',
      '4. Operations HUD: Cloud Run command tower for live SSE monitoring and on-demand fault injection.',
      '5. Cognitive RCA (HITL): Vertex AI Gemini 2.5 Flash performs root-cause analysis and proposes remediation.',
      '6. Agentic Governance: Approved actions invoke Mitigation Tools and record financial ROI to BigQuery.',
      '7. Closed-Loop Mitigation: Cloud Run actuator dispatches corrective commands to restore equipment baseline.',
    ],
  };

  const firstPartyTopologySlide: Omit<SlideMeta, 'number'> = {
    title: 'Aegis Telemetry Streaming - First Party',
    category:
      stackConfig.stackType === 'first_party'
        ? 'Active Blueprint: First-Party Stack'
        : 'Alternative Blueprint: First-Party Stack',
    image: '/slides/slide-8.png',
    description:
      '7-Step Google Cloud Native Reference Architecture: Cloud Pub/Sub + Cloud Dataflow (Apache Beam Streaming Engine) + Dual-Sink Bigtable/BigQuery + Vertex AI Remediation Agent.',
    keyHighlights: [
      '1. Ingestion: Monitored fleet streams real-time telemetry into Google Cloud Pub/Sub (telemetry-raw).',
      '2. Stream Processing: Cloud Dataflow continuously evaluates 10s fixed windows and flags threshold anomalies.',
      '3. Dual-Sink Persistence: Sub-ms operational state lands in Cloud Bigtable; analytical audits sink to BigQuery.',
      '4. Operations HUD: Cloud Run command tower for live SSE monitoring and on-demand fault injection.',
      '5. Cognitive RCA (HITL): Vertex AI Gemini 2.5 Flash performs root-cause analysis and proposes remediation.',
      '6. Agentic Governance: Approved actions invoke Mitigation Tools and record financial ROI to BigQuery.',
      '7. Closed-Loop Mitigation: Cloud Run actuator dispatches corrective commands to restore equipment baseline.',
    ],
  };

  const lowCodeTopologySlide: Omit<SlideMeta, 'number'> = {
    title: 'Aegis Telemetry Streaming - Low-Code',
    category:
      stackConfig.stackType === 'low_code'
        ? 'Active Blueprint: Low-Code Stack'
        : 'Alternative Blueprint: Low-Code Stack',
    image: '/slides/slide-9.png',
    description:
      '7-Step Serverless SQL Reference Architecture: Cloud Pub/Sub + BigQuery Continuous Queries + Dual-Sink Bigtable/BigQuery + Vertex AI Remediation Agent.',
    keyHighlights: [
      '1. Ingestion: Monitored fleet streams real-time telemetry into Google Cloud Pub/Sub (telemetry-raw).',
      '2. Stream Processing: BigQuery Continuous Queries evaluate 10s SQL windows over active streams.',
      '3. Dual-Sink Persistence: Sub-ms operational state lands in Cloud Bigtable; analytical audits sink to BigQuery.',
      '4. Operations HUD: Cloud Run command tower for live SSE monitoring and on-demand fault injection.',
      '5. Cognitive RCA (HITL): Vertex AI Gemini 2.5 Flash performs root-cause analysis and proposes remediation.',
      '6. Agentic Governance: Approved actions invoke Mitigation Tools and record financial ROI to BigQuery.',
      '7. Closed-Loop Mitigation: Cloud Run actuator dispatches corrective commands to restore equipment baseline.',
    ],
  };

  const orderedTopologySlides =
    stackConfig.stackType === 'first_party'
      ? [firstPartyTopologySlide, ossTopologySlide, lowCodeTopologySlide]
      : stackConfig.stackType === 'low_code'
      ? [lowCodeTopologySlide, firstPartyTopologySlide, ossTopologySlide]
      : [ossTopologySlide, firstPartyTopologySlide, lowCodeTopologySlide];

  return [
    ...coreSlides,
    ...orderedTopologySlides.map((slide, idx) => ({
      ...slide,
      number: 7 + idx,
    })),
  ];
};

interface SlideDeckViewerProps {
  pdfUrl?: string;
  title?: string;
  subtitle?: string;
  onNavigate?: (tabId: string) => void;
}

export const SlideDeckViewer: React.FC<SlideDeckViewerProps> = ({
  pdfUrl = '/aegis_autonomous_streaming.pdf',
  title = 'AEGIS Autonomous Streaming Presentation',
  subtitle: customSubtitle,
  onNavigate,
}) => {
  const [currentSlide, setCurrentSlide] = useState<number>(1);
  const [zoom, setZoom] = useState<number>(1.0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [showThumbnails, setShowThumbnails] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  const stackConfig = getStackConfig();
  const subtitle =
    customSubtitle ||
    (stackConfig.stackType === 'first_party'
      ? 'Executive Architecture, Cloud Dataflow Streaming & Agentic AI Mitigation Deck'
      : stackConfig.stackType === 'low_code'
      ? 'Executive Architecture, BigQuery Continuous Queries & Agentic AI Mitigation Deck'
      : 'Executive Architecture, C++ Velox Accelerated Compute & Agentic AI Mitigation Deck');

  const containerRef = useRef<HTMLDivElement>(null);
  const slidesData = React.useMemo(() => getSlidesData(stackConfig), [stackConfig]);
  const totalSlides = slidesData.length;
  const activeSlideMeta = slidesData[currentSlide - 1] || slidesData[0];

  // Fullscreen change listener
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Navigation handlers
  const prevSlide = useCallback(() => {
    setCurrentSlide((prev) => Math.max(1, prev - 1));
  }, []);

  const nextSlide = useCallback(() => {
    setCurrentSlide((prev) => Math.min(totalSlides, prev + 1));
  }, [totalSlides]);

  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch((err) => {
        console.error('Error attempting to enable fullscreen:', err);
      });
    } else {
      document.exitFullscreen().catch((err) => {
        console.error('Error attempting to exit fullscreen:', err);
      });
    }
  }, []);

  // Auto-play slideshow timer (6s per slide)
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentSlide((prev) => {
        if (prev >= totalSlides) {
          setIsPlaying(false);
          return 1;
        }
        return prev + 1;
      });
    }, 6000);

    return () => clearInterval(interval);
  }, [isPlaying, totalSlides]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName)) {
        return;
      }

      if (e.key === 'ArrowRight' || e.key === 'PageDown' || (e.key === ' ' && !e.shiftKey)) {
        e.preventDefault();
        nextSlide();
      } else if (e.key === 'ArrowLeft' || e.key === 'PageUp' || (e.key === ' ' && e.shiftKey)) {
        e.preventDefault();
        prevSlide();
      } else if (e.key === 'Home') {
        e.preventDefault();
        setCurrentSlide(1);
      } else if (e.key === 'End') {
        e.preventDefault();
        setCurrentSlide(totalSlides);
      } else if (e.key.toLowerCase() === 'f') {
        e.preventDefault();
        toggleFullscreen();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nextSlide, prevSlide, totalSlides, toggleFullscreen]);

  return (
    <div
      ref={containerRef}
      className={`w-full flex flex-col transition-all ${
        isFullscreen
          ? 'bg-[#070d19] text-white h-screen p-4 overflow-y-auto'
          : 'glass-panel rounded-2xl p-4 md:p-7 space-y-5'
      }`}
    >
      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between pb-4 border-b border-white/[0.08] gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-[#1a73e8]/15 border border-[#1a73e8]/30 text-[#68abff]">
              <Presentation className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg md:text-xl font-headline font-bold text-white tracking-tight flex items-center gap-2.5">
                {title}
                <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-widest rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                  HD Pitch Deck
                </span>
              </h2>
              <p className="text-xs md:text-sm text-[#94a3b8] font-sans mt-0.5">
                {subtitle}
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 flex-wrap self-end lg:self-auto">
          {/* Slideshow Auto-play */}
          <button
            type="button"
            onClick={() => setIsPlaying(!isPlaying)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
              isPlaying
                ? 'bg-amber-500/15 border-amber-500/40 text-amber-400'
                : 'bg-[#0f172a] hover:bg-[#1e293b] border-white/[0.08] text-[#cbd5e1]'
            }`}
            title={isPlaying ? 'Pause Auto-Play (6s/slide)' : 'Start Auto-Play Slideshow'}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            <span>{isPlaying ? 'Playing (6s)' : 'Auto-Play'}</span>
          </button>

          {/* Thumbnail Strip Toggle */}
          <button
            type="button"
            onClick={() => setShowThumbnails(!showThumbnails)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
              showThumbnails
                ? 'bg-[#1a73e8] border-[#adc7ff]/40 text-white shadow-sm'
                : 'bg-[#0f172a] hover:bg-[#1e293b] border-white/[0.08] text-[#cbd5e1]'
            }`}
            title="Toggle Slide Grid / Thumbnails"
          >
            <Grid className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Thumbnails</span>
          </button>

          {/* Open Raw PDF */}
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 rounded-lg bg-[#0f172a] hover:bg-[#1e293b] border border-white/[0.08] text-[#cbd5e1] hover:text-white text-xs font-mono font-semibold flex items-center gap-1.5 transition-all"
            title="Open original PDF document in new browser tab"
          >
            <ExternalLink className="w-3.5 h-3.5 text-[#68abff]" />
            <span className="hidden sm:inline">Raw PDF</span>
          </a>

          {/* Download Deck */}
          <a
            href={pdfUrl}
            download="aegis_autonomous_streaming.pdf"
            className="px-3 py-1.5 rounded-lg bg-[#0f172a] hover:bg-[#1e293b] border border-white/[0.08] text-[#cbd5e1] hover:text-white text-xs font-mono font-semibold flex items-center gap-1.5 transition-all"
            title="Download original PDF presentation"
          >
            <Download className="w-3.5 h-3.5 text-emerald-400" />
            <span className="hidden sm:inline">Download</span>
          </a>

          {/* Fullscreen Toggle */}
          <button
            type="button"
            onClick={toggleFullscreen}
            className="px-3 py-1.5 rounded-lg bg-[#1a73e8] hover:bg-[#1557b0] border border-[#adc7ff]/30 text-white text-xs font-mono font-semibold flex items-center gap-1.5 transition-all cursor-pointer"
            title={isFullscreen ? 'Exit Fullscreen (F)' : 'Enter Fullscreen (F)'}
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">{isFullscreen ? 'Exit' : 'Fullscreen'}</span>
          </button>
        </div>
      </div>

      {/* Main Slide Viewer Layout */}
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        {/* Thumbnail Sidebar */}
        {showThumbnails && (
          <aside className="w-full lg:w-56 max-h-[700px] overflow-y-auto rounded-xl bg-[#090f1e] border border-white/[0.08] p-3 space-y-2.5 shrink-0 scrollbar-thin animate-fade-in">
            <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-[#94a3b8] pb-2 border-b border-white/[0.08] flex items-center justify-between">
              <span>All Slides</span>
              <span className="tabular-nums">{totalSlides}</span>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-1 gap-2">
              {slidesData.map((slide) => {
                const isSelected = slide.number === currentSlide;
                return (
                  <button
                    key={`thumb-${slide.number}`}
                    type="button"
                    onClick={() => {
                      setCurrentSlide(slide.number);
                      setIsPlaying(false);
                    }}
                    className={`group relative rounded-lg overflow-hidden border text-left transition-all p-1.5 cursor-pointer ${
                      isSelected
                        ? 'border-[#1a73e8] bg-[#1a73e8]/20 ring-1 ring-[#68abff]/40'
                        : 'border-white/[0.06] bg-[#0f172a]/60 hover:border-white/20 hover:bg-[#1e293b]/60'
                    }`}
                  >
                    <div className="aspect-[16/9] w-full overflow-hidden rounded bg-black/60 relative">
                      <Image
                        src={slide.image}
                        alt={`Slide ${slide.number}`}
                        fill
                        sizes="220px"
                        className="object-contain"
                      />
                    </div>
                    <div className="mt-1.5 px-0.5">
                      <div className="flex items-center justify-between">
                        <span
                          className={`text-[10px] font-mono font-bold tabular-nums ${
                            isSelected ? 'text-[#68abff]' : 'text-[#94a3b8] group-hover:text-white'
                          }`}
                        >
                          Slide {slide.number}
                        </span>
                        <span className="text-[9px] font-mono text-[#64748b] truncate max-w-[90px]">
                          {slide.category}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#e2e8f0] font-sans font-medium line-clamp-1 mt-0.5">
                        {slide.title}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </aside>
        )}

        {/* Primary Presentation Stage */}
        <div className="flex-1 w-full flex flex-col items-center space-y-3.5">
          {/* Active Slide Canvas with 16:9 Aspect Ratio (unobstructed corners) */}
          <div className="relative w-full rounded-2xl bg-[#030712] border border-white/[0.1] shadow-2xl overflow-hidden flex items-center justify-center aspect-[16/9] max-h-[780px] group">
            <div
              className="relative w-full h-full transition-transform duration-200"
              style={{ transform: `scale(${zoom})` }}
            >
              <Image
                src={activeSlideMeta.image}
                alt={activeSlideMeta.title}
                fill
                priority={currentSlide <= 2}
                sizes="(max-width: 1280px) 100vw, 1400px"
                className="object-contain select-none"
              />
            </div>

            {/* Quick Overlay Next/Previous Hitboxes on Hover */}
            <button
              type="button"
              onClick={prevSlide}
              disabled={currentSlide <= 1}
              aria-label="Previous Slide"
              className="absolute left-3 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-black/70 hover:bg-black/90 text-white border border-white/15 opacity-0 group-hover:opacity-100 disabled:opacity-0 transition-all shadow-xl backdrop-blur-sm cursor-pointer"
            >
              <ChevronLeft className="w-6 h-6" />
            </button>

            <button
              type="button"
              onClick={nextSlide}
              disabled={currentSlide >= totalSlides}
              aria-label="Next Slide"
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-black/70 hover:bg-black/90 text-white border border-white/15 opacity-0 group-hover:opacity-100 disabled:opacity-0 transition-all shadow-xl backdrop-blur-sm cursor-pointer"
            >
              <ChevronRight className="w-6 h-6" />
            </button>
          </div>

          {/* Unified Navigation & Metadata Control Bar */}
          <div className="w-full flex flex-col sm:flex-row items-center justify-between gap-4 px-4 py-2.5 rounded-xl bg-[#0b1326] border border-white/[0.08]">
            {/* Left: Previous / First */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setCurrentSlide(1);
                  setIsPlaying(false);
                }}
                disabled={currentSlide <= 1}
                className="px-2.5 py-1.5 rounded-lg bg-white/[0.03] hover:bg-white/[0.08] disabled:opacity-30 border border-white/[0.08] text-xs font-mono text-[#cbd5e1] transition-all cursor-pointer"
                title="First Slide (Home)"
              >
                First
              </button>
              <button
                type="button"
                onClick={() => {
                  prevSlide();
                  setIsPlaying(false);
                }}
                disabled={currentSlide <= 1}
                className="px-3.5 py-1.5 rounded-lg bg-[#1a73e8] hover:bg-[#1557b0] disabled:opacity-30 text-white font-mono text-xs font-bold uppercase tracking-wider flex items-center gap-1 transition-all cursor-pointer"
                title="Previous Slide (Left Arrow / PageUp)"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Prev</span>
              </button>
            </div>

            {/* Center: Slide Category Pill, Position & Scrub Slider */}
            <div className="flex items-center gap-3 w-full sm:w-auto justify-center flex-wrap">
              <span className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.04] border border-white/[0.08] text-[11px] font-mono text-emerald-400">
                <Sparkles className="w-3 h-3 text-amber-400" />
                {activeSlideMeta.category}
              </span>

              <span className="text-xs font-mono font-bold text-[#e2e8f0] whitespace-nowrap tabular-nums">
                Slide <span className="text-[#68abff]">{currentSlide}</span> / {totalSlides}
              </span>

              <input
                type="range"
                aria-label="Scrub slides"
                min={1}
                max={totalSlides}
                value={currentSlide}
                onChange={(e) => {
                  setCurrentSlide(Number(e.target.value));
                  setIsPlaying(false);
                }}
                className="w-28 sm:w-44 h-1.5 bg-[#070d19] rounded-lg appearance-none cursor-pointer accent-[#1a73e8]"
                title="Scrub slides"
              />
            </div>

            {/* Right: Zoom & Next */}
            <div className="flex items-center gap-2">
              <div className="hidden md:flex items-center gap-1 bg-[#070d19] p-1 rounded-lg border border-white/[0.08]">
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.max(0.8, Number((z - 0.1).toFixed(1))))}
                  className="p-1 text-[#94a3b8] hover:text-white hover:bg-white/[0.06] rounded transition cursor-pointer"
                  title="Zoom Out"
                >
                  <ZoomOut className="w-3.5 h-3.5" />
                </button>
                <span className="text-[11px] font-mono px-1 text-[#68abff] font-bold tabular-nums">
                  {Math.round(zoom * 100)}%
                </span>
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.min(1.5, Number((z + 0.1).toFixed(1))))}
                  className="p-1 text-[#94a3b8] hover:text-white hover:bg-white/[0.06] rounded transition cursor-pointer"
                  title="Zoom In"
                >
                  <ZoomIn className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setZoom(1.0)}
                  className="p-1 text-[#94a3b8] hover:text-white hover:bg-white/[0.06] rounded transition cursor-pointer"
                  title="Reset Zoom"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>

              <button
                type="button"
                onClick={() => {
                  nextSlide();
                  setIsPlaying(false);
                }}
                disabled={currentSlide >= totalSlides}
                className="px-3.5 py-1.5 rounded-lg bg-[#1a73e8] hover:bg-[#1557b0] disabled:opacity-30 text-white font-mono text-xs font-bold uppercase tracking-wider flex items-center gap-1 transition-all cursor-pointer"
                title="Next Slide (Right Arrow / Space / PageDown)"
              >
                <span>Next</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Active Slide Key Takeaways */}
          <div className="w-full p-5 rounded-xl bg-[#0b1326]/90 border border-white/[0.08] space-y-3">
            <div className="flex flex-wrap items-center justify-between border-b border-white/[0.08] pb-2.5 gap-2">
              <div className="flex items-center gap-2.5">
                <span className="px-2 py-0.5 rounded bg-[#1a73e8]/15 border border-[#1a73e8]/30 text-[#68abff] font-mono text-xs font-bold tabular-nums">
                  Slide {activeSlideMeta.number}
                </span>
                <h3 className="font-headline font-bold text-white text-base">
                  {activeSlideMeta.title}
                </h3>
              </div>
              <span className="text-[11px] font-mono text-[#64748b]">
                Use ← / → or Space to navigate • F for Fullscreen
              </span>
            </div>

            <p className="text-xs md:text-sm text-[#94a3b8] font-sans leading-relaxed">
              {activeSlideMeta.description}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
              {activeSlideMeta.keyHighlights.map((highlight, idx) => (
                <div
                  key={`hl-${idx}`}
                  className="flex items-start gap-2.5 px-3 py-2 rounded-lg bg-[#070d19]/70 border border-white/[0.06] text-xs text-[#e2e8f0]"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{highlight}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Step Navigation to Module 2 */}
      <PageNavigation
        nextTab={{ id: 'simulator', label: '2. Stream Simulator' }}
        onNavigate={onNavigate}
      />
    </div>
  );
};

export default SlideDeckViewer;
