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
  Layers,
  Sparkles,
  CheckCircle2,
  FileText,
  Activity,
  Cpu,
  Database,
  Bot,
  ShieldCheck,
  Zap,
  ArrowRight
} from 'lucide-react';
import { PageNavigation } from './PageNavigation';

interface SlideMeta {
  number: number;
  title: string;
  category: string;
  image: string;
  description: string;
  keyHighlights: string[];
}

const SLIDES_DATA: SlideMeta[] = [
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
      'Managed Kafka: Partition-isolated high-throughput buffering',
      'Spark Serverless: 10s rolling window anomaly detection (>90% CPU / Temp / Pressure)',
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
  },
  {
    number: 7,
    title: 'Aegis Telemetry Streaming GCP Topology',
    category: 'End-to-End Blueprint',
    image: '/slides/slide-7.png',
    description: '7-Step End-to-End Reference Architecture: Bridging physical IIoT telemetry with real-time stream compute and closed-loop Gemini 2.5 Flash agent remediation.',
    keyHighlights: [
      '1. Ingestion: Monitored fleet streams real-time telemetry into Managed Apache Kafka topics.',
      '2. Stream Processing: Managed Spark continuously evaluates 10s windows and flags threshold anomalies.',
      '3. Dual-Sink Persistence: Sub-ms operational state lands in Bigtable; analytical audits sink to BigQuery.',
      '4. Operations HUD: Real-time command tower for live monitoring and on-demand fault injection.',
      '5. Cognitive RCA (HITL): Gemini 2.5 Flash performs root-cause analysis and formulates mitigation directives.',
      '6. Agentic Governance: Approved actions invoke connected tools and record financial ROI to BigQuery.',
      '7. Closed-Loop Mitigation: Actuator tools dispatch corrective commands to restore nominal equipment baseline.'
    ]
  }
];

interface SlideDeckViewerProps {
  pdfUrl?: string;
  title?: string;
  subtitle?: string;
  onNavigate?: (tabId: string) => void;
}

export const SlideDeckViewer: React.FC<SlideDeckViewerProps> = ({
  pdfUrl = '/aegis_autonomous_streaming.pdf',
  title = 'AEGIS Autonomous Streaming Presentation',
  subtitle = 'Executive Architecture, C++ Velox Accelerated Compute & Agentic AI Mitigation Deck',
  onNavigate,
}) => {
  const [currentSlide, setCurrentSlide] = useState<number>(1);
  const [zoom, setZoom] = useState<number>(1.0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [showThumbnails, setShowThumbnails] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const totalSlides = SLIDES_DATA.length;
  const activeSlideMeta = SLIDES_DATA[currentSlide - 1] || SLIDES_DATA[0];

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
          ? 'bg-[#060e20] text-white h-screen p-4 overflow-y-auto'
          : 'glass-panel rounded-2xl p-4 md:p-8 border border-[#334155] shadow-2xl space-y-6'
      }`}
    >
      {/* Header Banner */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between pb-4 border-b border-[#334155] gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-[#1a73e8]/20 border border-[#1a73e8]/40 text-[#adc7ff]">
              <Presentation className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg md:text-xl font-headline font-bold text-white tracking-wide flex items-center gap-2">
                {title}
                <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-widest rounded bg-[#131b2e] text-[#6ddd81] border border-[#334155]">
                  HD Pitch Deck
                </span>
              </h2>
              <p className="text-xs md:text-sm text-[#c1c6d6] font-sans mt-0.5">
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
            className={`px-3 py-1.5 rounded-lg border text-xs font-mono font-semibold flex items-center gap-1.5 transition-all shadow-sm ${
              isPlaying
                ? 'bg-[#FBBC04]/20 border-[#FBBC04] text-[#FBBC04]'
                : 'bg-[#131b2e] hover:bg-[#1e293b] border-[#334155] text-[#dae2fd]'
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
            className={`px-3 py-1.5 rounded-lg border text-xs font-mono font-semibold flex items-center gap-1.5 transition-all ${
              showThumbnails
                ? 'bg-[#1a73e8] border-[#adc7ff] text-white shadow-md shadow-[#1a73e8]/30'
                : 'bg-[#131b2e] hover:bg-[#1e293b] border-[#334155] text-[#dae2fd]'
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
            className="px-3 py-1.5 rounded-lg bg-[#131b2e] hover:bg-[#1e293b] border border-[#334155] text-[#dae2fd] hover:text-white text-xs font-mono font-semibold flex items-center gap-1.5 transition-all"
            title="Open original PDF document in new browser tab"
          >
            <ExternalLink className="w-3.5 h-3.5 text-[#adc7ff]" />
            <span className="hidden sm:inline">Raw PDF</span>
          </a>

          {/* Download Deck */}
          <a
            href={pdfUrl}
            download="aegis_autonomous_streaming.pdf"
            className="px-3 py-1.5 rounded-lg bg-[#131b2e] hover:bg-[#1e293b] border border-[#334155] text-[#dae2fd] hover:text-white text-xs font-mono font-semibold flex items-center gap-1.5 transition-all"
            title="Download original PDF presentation"
          >
            <Download className="w-3.5 h-3.5 text-[#6ddd81]" />
            <span className="hidden sm:inline">Download</span>
          </a>

          {/* Fullscreen Toggle */}
          <button
            type="button"
            onClick={toggleFullscreen}
            className="px-3 py-1.5 rounded-lg bg-[#1a73e8]/80 hover:bg-[#1a73e8] border border-[#adc7ff]/40 text-white text-xs font-mono font-semibold flex items-center gap-1.5 transition-all shadow-md shadow-[#1a73e8]/20"
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
          <aside className="w-full lg:w-56 max-h-[700px] overflow-y-auto rounded-xl bg-[#060e20]/90 border border-[#334155] p-3 space-y-3 shrink-0 scrollbar-thin animate-fade-in">
            <div className="text-[11px] font-mono font-bold uppercase tracking-widest text-[#8b909f] pb-2 border-b border-[#334155]/60 flex items-center justify-between">
              <span>All Slides</span>
              <span>{totalSlides}</span>
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-1 gap-2.5">
              {SLIDES_DATA.map((slide) => {
                const isSelected = slide.number === currentSlide;
                return (
                  <button
                    key={`thumb-${slide.number}`}
                    type="button"
                    onClick={() => {
                      setCurrentSlide(slide.number);
                      setIsPlaying(false);
                    }}
                    className={`group relative rounded-lg overflow-hidden border text-left transition-all p-1.5 ${
                      isSelected
                        ? 'border-[#adc7ff] bg-[#1a73e8]/30 shadow-md ring-2 ring-[#adc7ff]/50'
                        : 'border-[#334155] bg-[#131b2e]/60 hover:border-[#8b909f] hover:bg-[#1e293b]'
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
                          className={`text-[10px] font-mono font-bold ${
                            isSelected ? 'text-[#adc7ff]' : 'text-[#8b909f] group-hover:text-white'
                          }`}
                        >
                          Slide {slide.number}
                        </span>
                        <span className="text-[9px] font-mono text-[#8b909f] truncate max-w-[90px]">
                          {slide.category}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#dae2fd] font-sans font-medium line-clamp-1 mt-0.5">
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
        <div className="flex-1 w-full flex flex-col items-center space-y-4">
          {/* Active Slide Canvas with 16:9 Aspect Ratio */}
          <div className="relative w-full rounded-2xl bg-black border border-[#334155] shadow-2xl overflow-hidden flex items-center justify-center aspect-[16/9] max-h-[780px] group">
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
              className="absolute left-3 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-black/60 hover:bg-black/90 text-white border border-white/20 opacity-0 group-hover:opacity-100 disabled:opacity-0 transition-all shadow-xl backdrop-blur-sm"
            >
              <ChevronLeft className="w-6 h-6" />
            </button>

            <button
              type="button"
              onClick={nextSlide}
              disabled={currentSlide >= totalSlides}
              aria-label="Next Slide"
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-black/60 hover:bg-black/90 text-white border border-white/20 opacity-0 group-hover:opacity-100 disabled:opacity-0 transition-all shadow-xl backdrop-blur-sm"
            >
              <ChevronRight className="w-6 h-6" />
            </button>

            {/* Slide Index Badge in Bottom-Right */}
            <div className="absolute bottom-3 right-3 bg-black/80 backdrop-blur-md px-3 py-1 rounded-full border border-white/20 text-xs font-mono font-bold text-white shadow-lg pointer-events-none flex items-center gap-2">
              <span className="text-[#adc7ff]">{currentSlide}</span> / {totalSlides}
            </div>

            {/* Slide Category Pill in Top-Left */}
            <div className="absolute top-3 left-3 bg-black/80 backdrop-blur-md px-3 py-1 rounded-lg border border-white/20 text-[11px] font-mono font-bold text-[#6ddd81] shadow-lg pointer-events-none flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-[#FBBC04]" />
              <span>{activeSlideMeta.category}</span>
            </div>
          </div>

          {/* Navigation Control Bar */}
          <div className="w-full flex flex-col sm:flex-row items-center justify-between gap-4 p-3 rounded-xl bg-[#131b2e]/90 border border-[#334155] shadow-lg">
            {/* Left: Previous / First */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setCurrentSlide(1);
                  setIsPlaying(false);
                }}
                disabled={currentSlide <= 1}
                className="px-2.5 py-1.5 rounded-lg bg-[#060e20] hover:bg-[#1e293b] disabled:opacity-30 border border-[#334155] text-xs font-mono text-[#dae2fd] transition-all"
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
                className="px-4 py-2 rounded-lg bg-[#1a73e8] hover:bg-[#005bc0] disabled:opacity-30 text-white font-mono text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all shadow-md shadow-[#1a73e8]/20"
                title="Previous Slide (Left Arrow / PageUp)"
              >
                <ChevronLeft className="w-4 h-4" />
                <span>Prev</span>
              </button>
            </div>

            {/* Center: Slide Position & Scrub Slider */}
            <div className="flex items-center gap-3 w-full sm:w-auto justify-center">
              <span className="text-xs font-mono font-bold text-[#dae2fd] whitespace-nowrap">
                Slide <span className="text-[#adc7ff]">{currentSlide}</span> of {totalSlides}
              </span>

              <input
                type="range"
                min={1}
                max={totalSlides}
                value={currentSlide}
                onChange={(e) => {
                  setCurrentSlide(Number(e.target.value));
                  setIsPlaying(false);
                }}
                className="w-28 sm:w-48 h-1.5 bg-[#060e20] rounded-lg appearance-none cursor-pointer accent-[#1a73e8]"
                title="Scrub slides"
              />
            </div>

            {/* Right: Next / Zoom */}
            <div className="flex items-center gap-2">
              {/* Zoom Controls */}
              <div className="hidden md:flex items-center gap-1 bg-[#060e20] p-1 rounded-lg border border-[#334155]">
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.max(0.8, Number((z - 0.1).toFixed(1))))}
                  className="p-1 text-[#8b909f] hover:text-white hover:bg-[#1e293b] rounded transition"
                  title="Zoom Out"
                >
                  <ZoomOut className="w-3.5 h-3.5" />
                </button>
                <span className="text-[11px] font-mono px-1 text-[#adc7ff] font-bold">
                  {Math.round(zoom * 100)}%
                </span>
                <button
                  type="button"
                  onClick={() => setZoom((z) => Math.min(1.5, Number((z + 0.1).toFixed(1))))}
                  className="p-1 text-[#8b909f] hover:text-white hover:bg-[#1e293b] rounded transition"
                  title="Zoom In"
                >
                  <ZoomIn className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => setZoom(1.0)}
                  className="p-1 text-[#8b909f] hover:text-white hover:bg-[#1e293b] rounded transition"
                  title="Reset Zoom"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Next Slide Button */}
              <button
                type="button"
                onClick={() => {
                  nextSlide();
                  setIsPlaying(false);
                }}
                disabled={currentSlide >= totalSlides}
                className="px-4 py-2 rounded-lg bg-[#1a73e8] hover:bg-[#005bc0] disabled:opacity-30 text-white font-mono text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all shadow-md shadow-[#1a73e8]/20"
                title="Next Slide (Right Arrow / Space / PageDown)"
              >
                <span>Next</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Keyboard Shortcuts Helper Bar */}
          <div className="w-full flex items-center justify-between text-[11px] font-mono text-[#8b909f] px-2">
            <div className="flex items-center gap-4 flex-wrap">
              <span><kbd className="bg-[#131b2e] px-1.5 py-0.5 rounded border border-[#334155] text-[#dae2fd]">←</kbd> <kbd className="bg-[#131b2e] px-1.5 py-0.5 rounded border border-[#334155] text-[#dae2fd]">→</kbd> or <kbd className="bg-[#131b2e] px-1.5 py-0.5 rounded border border-[#334155] text-[#dae2fd]">Space</kbd> Navigate</span>
              <span><kbd className="bg-[#131b2e] px-1.5 py-0.5 rounded border border-[#334155] text-[#dae2fd]">F</kbd> Fullscreen</span>
              <span><kbd className="bg-[#131b2e] px-1.5 py-0.5 rounded border border-[#334155] text-[#dae2fd]">Home</kbd> / <kbd className="bg-[#131b2e] px-1.5 py-0.5 rounded border border-[#334155] text-[#dae2fd]">End</kbd> First/Last</span>
            </div>
            <div className="flex items-center gap-1.5 text-[#6ddd81]">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>High-DPI Retina Rendering</span>
            </div>
          </div>

          {/* Active Slide Detailed Overview & Executive Notes */}
          <div className="w-full p-5 rounded-2xl bg-[#131b2e]/80 border border-[#334155] space-y-3 mt-2 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#334155]/60 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded bg-[#1a73e8]/20 border border-[#1a73e8]/40 text-[#adc7ff] font-mono text-xs font-bold">
                  Slide {activeSlideMeta.number} Notes
                </span>
                <h3 className="font-headline font-bold text-white text-base">
                  {activeSlideMeta.title}
                </h3>
              </div>
              <span className="text-xs font-mono text-[#8b909f]">
                {activeSlideMeta.category}
              </span>
            </div>

            <p className="text-xs md:text-sm text-[#c1c6d6] font-sans leading-relaxed">
              {activeSlideMeta.description}
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
              {activeSlideMeta.keyHighlights.map((highlight, idx) => (
                <div
                  key={`hl-${idx}`}
                  className="flex items-start gap-2 p-2.5 rounded-lg bg-[#060e20]/60 border border-[#334155]/50 text-xs text-[#dae2fd]"
                >
                  <CheckCircle2 className="w-4 h-4 text-[#6ddd81] shrink-0 mt-0.5" />
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
