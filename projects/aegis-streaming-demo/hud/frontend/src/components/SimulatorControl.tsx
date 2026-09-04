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

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Play, Square, AlertTriangle, RefreshCw, Flame, CheckCircle, Activity, Cpu, Layers, Zap, ArrowRight } from 'lucide-react';
import { PageNavigation } from './PageNavigation';
import { useHUD } from '@/context/HUDContext';

interface SimulatorControlProps {
  onInjectAnomaly: (targetAssetId?: string) => Promise<void>;
  onToggleSimulator: (start: boolean) => Promise<void>;
  isSimulatorRunning: boolean;
  pipelineStatus?: string;
  onTogglePipeline?: (start: boolean) => Promise<void>;
  onNavigate?: (tabId: string) => void;
}

export const SimulatorControl: React.FC<Partial<SimulatorControlProps>> = ({
  onInjectAnomaly: propInjectAnomaly,
  onToggleSimulator: propToggleSimulator,
  isSimulatorRunning: propSimulatorRunning,
  pipelineStatus: parentPipelineStatus,
  onTogglePipeline: parentTogglePipeline,
  onNavigate,
}) => {
  const hud = useHUD();

  const onInjectAnomaly = propInjectAnomaly || (() => hud.handleInjectAnomaly());
  const onToggleSimulator = propToggleSimulator || hud.handleToggleSimulator;
  const isSimulatorRunning = propSimulatorRunning ?? hud.isSimulatorRunning;
  const onTogglePipeline = parentTogglePipeline || hud.handleTogglePipeline;

  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [selectedRate, setSelectedRate] = useState<number>(hud?.simulatorRate || 100);

  // Simulator State
  const [localSimulatorRunning, setLocalSimulatorRunning] = useState<boolean>(isSimulatorRunning);
  const effectiveSimulatorRunning = localSimulatorRunning;

  useEffect(() => {
    setLocalSimulatorRunning(isSimulatorRunning);
  }, [isSimulatorRunning]);

  useEffect(() => {
    if (hud?.simulatorRate) {
      setSelectedRate(hud.simulatorRate);
    }
  }, [hud?.simulatorRate]);

  // Pipeline State
  const [localPipelineStatus, setLocalPipelineStatus] = useState<string>('RUNNING');
  const pipelineStatus = parentPipelineStatus || localPipelineStatus;
  const [isCheckingPipeline, setIsCheckingPipeline] = useState<boolean>(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState<string | null>(null);
  const [pipelineMessage, setPipelineMessage] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  // Kafka Live Throughput State
  const [kafkaCount, setKafkaCount] = useState<number>(0);
  const [kafkaRate, setKafkaRate] = useState<number>(0);
  const [kafkaHistory, setKafkaHistory] = useState<number[]>([]);

  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || '';

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 5000);
  };

  const fetchPipelineStatus = async () => {
    setIsCheckingPipeline(true);
    try {
      const res = await fetch(`${API_BASE}/api/pipeline/status`);
      if (res.ok) {
        const data = await res.json();
        if (data.status) {
          setLocalPipelineStatus(data.status);
        }
        if (data.batch_id) setBatchId(data.batch_id);
        if (data.message) setPipelineMessage(data.message);
        if (data.error) setPipelineError(data.error);
        else if (data.status !== 'FAILED') setPipelineError(null);
      }
    } catch (e) {
      // Retain existing state on transient errors
    } finally {
      setIsCheckingPipeline(false);
    }
  };

  useEffect(() => {
    fetchPipelineStatus();
    const interval = setInterval(fetchPipelineStatus, 15000); // Check every 15s
    const handleSync = () => fetchPipelineStatus();
    window.addEventListener('pipeline-status-changed', handleSync);
    return () => {
      clearInterval(interval);
      window.removeEventListener('pipeline-status-changed', handleSync);
    };
  }, [API_BASE]);

  useEffect(() => {
    const fetchSimulatorStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/stream-status`);
        if (res.ok) {
          const data = await res.json();
          if (typeof data.running === 'boolean') {
            setLocalSimulatorRunning(data.running);
          }
          if (data.running && data.target_rate_msgs_per_sec) {
            setSelectedRate(data.target_rate_msgs_per_sec);
          }
          const count = typeof data.total_messages_last_5m === 'number' ? data.total_messages_last_5m : data.kafka_messages_last_5m;
          const rate = typeof data.rate_msgs_per_sec_5m === 'number' ? data.rate_msgs_per_sec_5m : 0;
          if (typeof rate === 'number') {
            setKafkaRate(rate);
          }
          if (typeof count === 'number') {
            setKafkaCount(prev => {
              if (count === 0 && effectiveSimulatorRunning && prev > 0) {
                return prev;
              }
              return count;
            });
            setKafkaHistory(prev => {
              const val = (count === 0 && effectiveSimulatorRunning && prev.length > 0 && prev[prev.length - 1] > 0)
                ? prev[prev.length - 1]
                : count;
              const next = [...prev, val];
              return next.slice(-30);
            });
          }
        }
      } catch (e) {
        // ignore errors during polling
      }
    };
    fetchSimulatorStatus();
    const simInterval = setInterval(fetchSimulatorStatus, 6000);
    return () => clearInterval(simInterval);
  }, [API_BASE, effectiveSimulatorRunning]);

  const handleStartStop = async (start: boolean) => {
    setLocalSimulatorRunning(start);
    setLoadingAction(start ? 'start' : 'stop');
    try {
      if (hud?.handleToggleSimulator) {
        await hud.handleToggleSimulator(start, selectedRate);
      } else {
        await onToggleSimulator(start);
      }
      showToast(start ? `CDC Telemetry Generator Started at ${selectedRate} msgs/sec` : 'CDC Telemetry Generator Paused');
    } catch (e) {
      showToast('Error toggling simulator');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleInject = async (assetId?: string) => {
    setLoadingAction('inject');
    try {
      await onInjectAnomaly(assetId);
      showToast('🔥 Thermal & compute anomaly injected into fleet. Observe telemetry grid to detect anomaly!');
    } catch (e) {
      showToast('Failed to inject anomaly');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleTogglePipeline = async (start: boolean) => {
    setPipelineLoading(start ? 'start' : 'stop');
    try {
      if (parentTogglePipeline) {
        await parentTogglePipeline(start);
      } else {
        const endpoint = start ? `${API_BASE}/api/pipeline/start` : `${API_BASE}/api/pipeline/stop`;
        const res = await fetch(endpoint, { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          showToast(data.message || (start ? 'Managed Spark Pipeline starting...' : 'Managed Spark Pipeline stopped'));
          await fetchPipelineStatus();
          window.dispatchEvent(new Event('pipeline-status-changed'));
        } else {
          showToast('Error toggling Managed Spark pipeline');
        }
      }
    } catch (e) {
      showToast('Error communicating with backend pipeline API');
    } finally {
      setPipelineLoading(null);
    }
  };

  const isPipelineActive = pipelineStatus === 'RUNNING' || pipelineStatus === 'PENDING' || pipelineStatus === 'ACTIVE';

  return (
    <section className="w-full glass-panel rounded-2xl p-6 border border-[#334155] shadow-xl space-y-6">
      {/* Section Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-[#334155]">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-[#adc7ff]" />
            <h2 className="text-lg font-headline font-bold text-white uppercase tracking-wide">
              Module 2: Ingestion &amp; Processing Pipeline Operations
            </h2>
          </div>
          <p className="text-xs text-[#c1c6d6] font-sans mt-1">
            Operate real-time CDC message generators and Serverless C++ Lightning Engine (Velox) ETL stream processing from the HUD
          </p>
        </div>
      </div>

      {/* Quick Start Instructions Banner */}
      <div className="p-4 rounded-xl bg-[#131b2e]/90 border border-[#1a73e8]/40 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-[#1a73e8] text-white shrink-0 mt-0.5">
            <Zap className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <h4 className="text-sm font-headline font-bold text-white flex items-center gap-2">
              <span>Quick Start Demo Workflow</span>
              <span className="px-2 py-0.5 text-[10px] font-mono uppercase bg-[#1a73e8]/20 text-[#adc7ff] rounded border border-[#1a73e8]/50">
                Step 1: Start Stream First
              </span>
            </h4>
            <div className="text-xs text-[#dae2fd] font-sans leading-relaxed space-y-0.5">
              <p>1. Click <strong className="text-white font-mono font-semibold">START CDC SIMULATOR</strong> below to stream synthetic IIoT telemetry into Managed Kafka.</p>
              <p>2. Verify the <strong className="text-white font-mono font-semibold">Managed Spark Streaming Job</strong> is RUNNING with native C++ Velox acceleration.</p>
              <p>3. Click <strong className="text-[#adc7ff] font-mono font-semibold">Proceed to 3. Demo Guide ↗</strong> to review the customer presentation talk track and inspect live GCP Console links.</p>
            </div>
          </div>
        </div>

        <Link
          href="/guide"
          className="px-4 py-2 rounded-lg bg-[#1a73e8] hover:bg-[#005bc0] text-white font-mono text-xs uppercase tracking-wider font-bold transition-all shadow-md flex items-center gap-1.5 shrink-0 self-end md:self-center"
        >
          <span>Go to Demo Guide ↗</span>
        </Link>
      </div>

      {/* Grid of Two Operation Controllers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Card 1: Kafka CDC Stream Generator */}
        <div className="p-5 rounded-xl bg-[#131b2e]/80 border border-[#2d3449] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[#adc7ff]" />
                <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                  1. CDC Kafka Stream Generator
                </h3>
              </div>
              {/* Status Badge */}
              <div className={`px-2.5 py-1 rounded border text-[11px] font-mono uppercase tracking-widest font-bold flex items-center gap-1.5 ${
                effectiveSimulatorRunning
                  ? 'bg-[#30a550]/20 text-[#6ddd81] border-[#30a550]'
                  : 'bg-[#FBBC04]/20 text-[#FBBC04] border-[#FBBC04]'
              }`}>
                <span className={`w-2 h-2 rounded-full ${effectiveSimulatorRunning ? 'bg-[#6ddd81] animate-pulse' : 'bg-[#FBBC04]'}`} />
                <span>{effectiveSimulatorRunning ? 'RUNNING' : 'PAUSED'}</span>
              </div>
            </div>
            <p className="text-xs text-[#c1c6d6] font-sans mb-4">
              Continuously produces simulated IIoT industrial machinery sensor payloads and pushes authenticated OAuth messages directly into Google Cloud Managed Kafka (<code className="text-[#adc7ff]">telemetry-raw</code>).
            </p>

            {/* Live Kafka Throughput Metric Card & Graph */}
            <div className="mb-4 p-3 rounded-lg bg-[#0a0f1d] border border-[#334155]/60 flex items-center justify-between gap-4">
              <div>
                <div className="text-[11px] font-mono text-[#adc7ff] uppercase tracking-wider flex items-center gap-1.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${effectiveSimulatorRunning ? 'bg-[#6ddd81] animate-ping' : 'bg-[#8b909f]'}`} />
                  <span>Kafka Message Rate (5m)</span>
                </div>
                <div className="text-2xl font-mono font-bold text-white mt-0.5 flex items-baseline gap-2">
                  <span>{kafkaRate > 0 ? kafkaRate.toFixed(1) : (effectiveSimulatorRunning && kafkaCount > 0 ? (kafkaCount / 300.0).toFixed(1) : '0.0')}</span>
                  <span className="text-xs text-[#adc7ff] font-mono">msgs/sec</span>
                  <span className="text-xs text-[#8b909f] font-sans">({kafkaCount.toLocaleString()} in 5m)</span>
                </div>
              </div>

              {/* SVG Sparkline */}
              <div className="w-36 h-12 flex items-end justify-end">
                {kafkaHistory.length > 1 ? (
                  <svg className="w-full h-full overflow-visible" viewBox="0 0 100 40" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="kafkaGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.4" />
                        <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>
                    {(() => {
                      const maxVal = Math.max(...kafkaHistory, 10);
                      const minVal = Math.min(...kafkaHistory, 0);
                      const range = maxVal - minVal || 1;
                      const points = kafkaHistory.map((val, idx) => {
                        const x = (idx / (kafkaHistory.length - 1)) * 100;
                        const y = 38 - ((val - minVal) / range) * 35;
                        return `${x},${y}`;
                      }).join(' ');
                      const areaPoints = `0,40 ${points} 100,40`;
                      return (
                        <>
                          <polygon points={areaPoints} fill="url(#kafkaGrad)" />
                          <polyline points={points} fill="none" stroke="#60a5fa" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </>
                      );
                    })()}
                  </svg>
                ) : (
                  <div className="text-[10px] font-mono text-[#8b909f]">Sampling 1s...</div>
                )}
              </div>
            </div>

            {/* Message Rate / Backpressure Selector */}
            <div className="mb-4 p-3 rounded-lg bg-[#0a0f1d] border border-[#334155]/60 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-mono uppercase tracking-wider text-[#adc7ff] font-semibold flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-[#6ddd81]" />
                  <span>Target Telemetry Throughput</span>
                </label>
                <span className="text-[11px] font-mono text-[#8b909f]">
                  {effectiveSimulatorRunning ? (
                    <span className="text-[#6ddd81] font-semibold">● Locked (Stream Running)</span>
                  ) : (
                    'Select rate before starting'
                  )}
                </span>
              </div>

              {/* Rate Pills */}
              <div className="grid grid-cols-5 gap-1.5">
                {[
                  { value: 15, label: '15 /s', desc: 'Baseline' },
                  { value: 50, label: '50 /s', desc: 'Moderate' },
                  { value: 100, label: '100 /s', desc: 'Default (Rec)' },
                  { value: 250, label: '250 /s', desc: 'High Velocity' },
                  { value: 500, label: '500 /s', desc: 'Stress Test' },
                ].map((opt) => {
                  const isSelected = selectedRate === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      disabled={effectiveSimulatorRunning}
                      onClick={() => {
                        setSelectedRate(opt.value);
                        if (hud?.setSimulatorRate) {
                          hud.setSimulatorRate(opt.value);
                        }
                      }}
                      title={
                        effectiveSimulatorRunning
                          ? `Stream is actively publishing. Stop the stream to change rate.`
                          : `Set emission target to ${opt.value} messages/sec (${opt.desc})`
                      }
                      className={`px-2 py-1.5 rounded text-center transition-all ${
                        isSelected
                          ? 'bg-[#1a73e8] text-white border border-[#adc7ff] shadow-md shadow-[#1a73e8]/30 font-bold'
                          : 'bg-[#131b2e] hover:bg-[#1e293b] text-[#c1c6d6] border border-[#334155]'
                      } ${
                        effectiveSimulatorRunning
                          ? 'opacity-60 cursor-not-allowed'
                          : 'cursor-pointer hover:border-[#adc7ff]/50'
                      }`}
                    >
                      <div className="text-xs font-mono font-bold leading-none">{opt.label}</div>
                      <div className="text-[9px] font-sans opacity-75 mt-0.5 leading-tight truncate">{opt.desc}</div>
                    </button>
                  );
                })}
              </div>

              {effectiveSimulatorRunning && (
                <p className="text-[10px] font-sans text-[#8b909f] italic">
                  💡 To test different backpressure rates, click <strong>STOP GENERATOR</strong>, select a new rate, and restart.
                </p>
              )}
            </div>
          </div>

          {/* Buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-[#334155]/60">
            <button
              disabled={effectiveSimulatorRunning || loadingAction === 'start'}
              onClick={() => handleStartStop(true)}
              className="px-4 py-2 rounded font-mono text-xs uppercase tracking-wider font-bold transition-all duration-200 flex items-center gap-1.5 bg-[#1a73e8] hover:bg-[#005bc0] text-white disabled:opacity-40 disabled:cursor-not-allowed shadow-md shadow-[#1a73e8]/20"
            >
              {loadingAction === 'start' ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5 fill-white" />
              )}
              <span>START GENERATOR</span>
            </button>

            <button
              disabled={!effectiveSimulatorRunning || loadingAction === 'stop'}
              onClick={() => handleStartStop(false)}
              className="px-4 py-2 rounded font-mono text-xs uppercase tracking-wider font-bold transition-all duration-200 flex items-center gap-1.5 border border-[#8b909f] hover:border-[#adc7ff] hover:bg-[#2d3449] text-[#dae2fd] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loadingAction === 'stop' ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Square className="w-3.5 h-3.5 fill-[#dae2fd]" />
              )}
              <span>STOP GENERATOR</span>
            </button>
          </div>
        </div>

        {/* Card 2: Managed Spark PySpark Pipeline */}
        <div className="p-5 rounded-xl bg-[#131b2e]/80 border border-[#2d3449] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#adc7ff]" />
                <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                  2. Managed Spark Streaming Job
                </h3>
              </div>
              {/* Status Badge */}
              <div className={`px-2.5 py-1 rounded border text-[11px] font-mono uppercase tracking-widest font-bold flex items-center gap-1.5 ${
                pipelineStatus === 'RUNNING' || pipelineStatus === 'ACTIVE'
                  ? 'bg-[#30a550]/20 text-[#6ddd81] border-[#30a550]'
                  : pipelineStatus === 'PENDING'
                  ? 'bg-[#1a73e8]/20 text-[#adc7ff] border-[#1a73e8]'
                  : pipelineStatus === 'FAILED'
                  ? 'bg-[#D93025]/20 text-[#ff897d] border-[#D93025]'
                  : 'bg-[#FBBC04]/20 text-[#FBBC04] border-[#FBBC04]'
              }`}>
                <span className={`w-2 h-2 rounded-full ${
                  isPipelineActive
                    ? (pipelineStatus === 'PENDING' ? 'bg-[#adc7ff] animate-ping' : 'bg-[#6ddd81] animate-pulse')
                    : (pipelineStatus === 'FAILED' ? 'bg-[#ff897d]' : 'bg-[#FBBC04]')
                }`} />
                <span>{pipelineStatus}</span>
              </div>
            </div>
            <p className="text-xs text-[#c1c6d6] font-sans mb-3">
              Dataproc Serverless PySpark ETL job with C++ Velox Lightning Engine. Consumes from Managed Kafka and computes 10s tumbling windows directly into Cloud Bigtable &amp; BigQuery.
            </p>

            {/* Batch ID Banner */}
            {batchId && (
              <div className="text-[11px] font-mono text-[#adc7ff] bg-[#0b1326] px-2.5 py-1 rounded border border-[#334155]/60 inline-block mb-3">
                BATCH ID: <span className="font-bold text-white">{batchId}</span>
              </div>
            )}

            {/* Rich Status / Error Banner */}
            {pipelineStatus === 'FAILED' && (
              <div className="p-3 mb-3 rounded-lg bg-[#3a0f12] border border-[#ffb4ab]/40 text-[#ffb4ab] text-xs font-mono">
                <div className="flex items-center gap-1.5 font-bold mb-1">
                  <AlertTriangle className="w-4 h-4 text-[#ff897d] shrink-0" />
                  <span>BATCH EXECUTION FAILED</span>
                </div>
                <div className="text-[11px] leading-relaxed text-[#dae2fd]/90 break-words">
                  {pipelineError || pipelineMessage || 'Spark Serverless batch execution failed. Check GCP resource quotas or configuration.'}
                </div>
              </div>
            )}

            {pipelineStatus === 'PENDING' && (
              <div className="p-3 mb-3 rounded-lg bg-[#0b1b36] border border-[#1a73e8]/50 text-[#adc7ff] text-xs font-mono flex items-start gap-2.5">
                <RefreshCw className="w-4 h-4 text-[#60a5fa] animate-spin shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-white mb-0.5">INITIALIZING SPARK CLUSTER</div>
                  <div className="text-[11px] text-[#c1c6d6] leading-relaxed">
                    {pipelineMessage || 'Provisioning serverless compute nodes, configuring Velox C++ engine, and subscribing to Kafka partition consumers (~60–90s)...'}
                  </div>
                </div>
              </div>
            )}

            {(pipelineStatus === 'RUNNING' || pipelineStatus === 'ACTIVE') && (
              <div className="p-2.5 mb-3 rounded-lg bg-[#0d2215] border border-[#30a550]/40 text-[#6ddd81] text-[11px] font-mono flex items-center gap-2">
                <CheckCircle className="w-3.5 h-3.5 text-[#6ddd81] shrink-0" />
                <span className="truncate">{pipelineMessage || 'Ingestion active: Kafka (telemetry-raw) ➔ Spark C++ Velox ➔ Bigtable & BigQuery'}</span>
              </div>
            )}

            {(pipelineStatus === 'STOPPED' || pipelineStatus === 'CANCELLED') && (
              <div className="p-2.5 mb-3 rounded-lg bg-[#1a1c24] border border-[#334155]/60 text-[#c1c6d6] text-[11px] font-mono flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#FBBC04] shrink-0" />
                <span>{pipelineMessage || 'Pipeline stopped. Click START SPARK PIPELINE to launch Serverless ETL.'}</span>
              </div>
            )}
          </div>

          {/* Buttons */}
          <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-[#334155]/60">
            <button
              disabled={isPipelineActive || pipelineLoading === 'start'}
              onClick={() => handleTogglePipeline(true)}
              className="px-4 py-2 rounded font-mono text-xs uppercase tracking-wider font-bold transition-all duration-200 flex items-center gap-1.5 bg-[#30a550] hover:bg-[#25853e] text-white disabled:opacity-40 disabled:cursor-not-allowed shadow-md shadow-[#30a550]/20"
            >
              {pipelineLoading === 'start' ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3.5 h-3.5 fill-white" />
              )}
              <span>{pipelineStatus === 'FAILED' ? 'RETRY SPARK PIPELINE' : 'START SPARK PIPELINE'}</span>
            </button>

            <button
              disabled={!isPipelineActive || pipelineLoading === 'stop'}
              onClick={() => handleTogglePipeline(false)}
              className="px-4 py-2 rounded font-mono text-xs uppercase tracking-wider font-bold transition-all duration-200 flex items-center gap-1.5 border border-[#8b909f] hover:border-[#ffdad6] hover:bg-[#D93025]/20 hover:text-[#ffdad6] text-[#dae2fd] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {pipelineLoading === 'stop' ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Square className="w-3.5 h-3.5 fill-[#dae2fd]" />
              )}
              <span>STOP PIPELINE</span>
            </button>

            <button
              onClick={fetchPipelineStatus}
              className="ml-auto p-2 rounded border border-[#334155] hover:bg-[#2d3449] text-[#adc7ff] transition-all"
              title="Refresh status"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isCheckingPipeline ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

      </div>

      {/* Notification Toast */}
      {toastMessage && (
        <div className="p-3 rounded bg-[#131b2e]/90 border border-[#1a73e8] text-[#adc7ff] text-xs font-mono uppercase tracking-wider flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-[#6ddd81] shrink-0" />
            <span>{toastMessage}</span>
          </div>
        </div>
      )}

      {/* Step Previous & Next Navigation */}
      <PageNavigation
        prevTab={{ id: 'slides', label: '1. Executive Deck' }}
        nextTab={{ id: 'guide', label: '3. Demo Guide' }}
        onNavigate={onNavigate}
      />
    </section>
  );
};
