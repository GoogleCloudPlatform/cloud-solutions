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
import { Play, Square, AlertTriangle, RefreshCw, CheckCircle, Activity, Cpu, Layers, Zap } from 'lucide-react';
import { PageNavigation } from './PageNavigation';
import { useHUD } from '@/context/HUDContext';
import { getStackConfig } from '../utils/stackConfig';

interface SimulatorControlProps {
  onInjectAnomaly: (targetAssetId?: string) => Promise<void>;
  onToggleSimulator: (start: boolean) => Promise<void>;
  isSimulatorRunning: boolean;
  pipelineStatus?: string;
  onTogglePipeline?: (start: boolean) => Promise<void>;
  onNavigate?: (tabId: string) => void;
}

export const SimulatorControl: React.FC<Partial<SimulatorControlProps>> = ({
  onToggleSimulator: propToggleSimulator,
  isSimulatorRunning: propSimulatorRunning,
  pipelineStatus: parentPipelineStatus,
  onTogglePipeline: parentTogglePipeline,
  onNavigate,
}) => {
  const hud = useHUD();

  const onToggleSimulator = propToggleSimulator || hud.handleToggleSimulator;
  const isSimulatorRunning = propSimulatorRunning ?? hud.isSimulatorRunning;
  const stackConfig = getStackConfig();
  const stackType = stackConfig.stackType;

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
  const [clusterName, setClusterName] = useState<string>(stackConfig.dataprocCluster);
  const [pipelineLoading, setPipelineLoading] = useState<string | null>(null);
  const [pipelineMessage, setPipelineMessage] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  // Kafka Live Throughput State
  const [kafkaCount, setKafkaCount] = useState<number>(0);
  const [kafkaRate, setKafkaRate] = useState<number>(0);
  const [kafkaHistory, setKafkaHistory] = useState<number[]>([]);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || '';

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
        if (data.cluster_name) setClusterName(data.cluster_name);
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
          showToast(data.message || (start ? `${stackConfig.pipelineShort} starting...` : `${stackConfig.pipelineShort} stopped`));
          await fetchPipelineStatus();
          window.dispatchEvent(new Event('pipeline-status-changed'));
        } else {
          showToast(`Error toggling ${stackConfig.pipelineShort}`);
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
    <section className="w-full glass-panel rounded-2xl p-6 space-y-6">
      {/* Section Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-[#1a73e8]/15 border border-[#1a73e8]/30 text-[#68abff]">
              <Activity className="w-4 h-4" />
            </div>
            <h2 className="text-lg font-headline font-bold text-white uppercase tracking-wide">
              Module 2: Ingestion &amp; Processing Pipeline Operations
            </h2>
          </div>
          <p className="text-xs text-[#94a3b8] font-sans mt-1">
            Operate real-time CDC message generators and {stackConfig.pipelineName} stream processing from the HUD
          </p>
        </div>
      </div>

      {/* Slim Single-Row Quick Start Readiness Bar */}
      <div className="px-4 py-3 rounded-xl bg-[#0b1326] border border-[#1a73e8]/35 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2.5 text-xs">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#1a73e8] text-white font-mono text-[10px] font-bold uppercase tracking-wider shrink-0">
            <Zap className="w-3.5 h-3.5" />
            Quick Start
          </span>
          <span className="text-[#e2e8f0] font-sans">
            <strong className="text-white font-mono">1.</strong> {stackConfig.quickStartStep1}
          </span>
          <span className="text-[#475569] hidden sm:inline">•</span>
          <span className="text-[#e2e8f0] font-sans">
            <strong className="text-white font-mono">2.</strong> {stackConfig.quickStartStep2}
          </span>
        </div>

        <Link
          href="/guide"
          className="px-3.5 py-1.5 rounded-lg bg-[#1a73e8] hover:bg-[#1557b0] text-white font-mono text-xs uppercase tracking-wider font-bold transition-all shadow-sm flex items-center gap-1.5 shrink-0 self-end lg:self-center"
        >
          <span>Go to 3. Demo Guide ↗</span>
        </Link>
      </div>

      {/* Grid of Two Operation Controllers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Card 1: CDC Stream Generator */}
        <div className="p-5 rounded-xl bg-[#0b1326]/90 border border-white/[0.08] flex flex-col justify-between space-y-5">
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[#68abff]" />
                <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                  {stackConfig.generatorTitle}
                </h3>
              </div>
              {/* Status Badge */}
              <div
                className={`px-2.5 py-1 rounded-md border text-[11px] font-mono uppercase tracking-widest font-bold flex items-center gap-1.5 ${
                  effectiveSimulatorRunning
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/35'
                    : 'bg-amber-500/15 text-amber-400 border-amber-500/35'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    effectiveSimulatorRunning ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                  }`}
                />
                <span>{effectiveSimulatorRunning ? 'RUNNING' : 'PAUSED'}</span>
              </div>
            </div>

            <p className="text-xs text-[#94a3b8] font-sans leading-relaxed">
              {stackConfig.generatorDescription}
            </p>

            {/* Live Throughput Hero Readout & Sparkline */}
            <div className="p-4 rounded-xl bg-[#070d19] border border-white/[0.08] flex items-center justify-between gap-4">
              <div>
                <div className="text-[11px] font-mono text-[#94a3b8] uppercase tracking-wider flex items-center gap-1.5">
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      effectiveSimulatorRunning ? 'bg-emerald-400 animate-ping' : 'bg-[#64748b]'
                    }`}
                  />
                  <span>{stackConfig.ingestionRateLabel}</span>
                </div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-3xl font-mono font-bold text-white tabular-nums tracking-tight">
                    {kafkaRate > 0
                      ? kafkaRate.toFixed(1)
                      : effectiveSimulatorRunning && kafkaCount > 0
                      ? (kafkaCount / 300.0).toFixed(1)
                      : '0.0'}
                  </span>
                  <span className="text-xs text-[#68abff] font-mono font-semibold">msgs/sec</span>
                  <span className="text-xs text-[#64748b] font-mono tabular-nums">
                    ({kafkaCount.toLocaleString()} in 5m)
                  </span>
                </div>
              </div>

              {/* SVG Sparkline */}
              <div className="w-40 h-14 flex items-end justify-end shrink-0">
                {kafkaHistory.length > 1 ? (
                  <svg
                    className="w-full h-full overflow-visible"
                    viewBox="0 0 100 40"
                    preserveAspectRatio="none"
                  >
                    <defs>
                      <linearGradient id="kafkaGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.45" />
                        <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>
                    {(() => {
                      const maxVal = Math.max(...kafkaHistory, 10);
                      const minVal = Math.min(...kafkaHistory, 0);
                      const range = maxVal - minVal || 1;
                      const points = kafkaHistory
                        .map((val, idx) => {
                          const x = (idx / (kafkaHistory.length - 1)) * 100;
                          const y = 38 - ((val - minVal) / range) * 35;
                          return `${x},${y}`;
                        })
                        .join(' ');
                      const areaPoints = `0,40 ${points} 100,40`;
                      return (
                        <>
                          <polygon points={areaPoints} fill="url(#kafkaGrad)" />
                          <polyline
                            points={points}
                            fill="none"
                            stroke="#60a5fa"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </>
                      );
                    })()}
                  </svg>
                ) : (
                  <div className="text-[10px] font-mono text-[#64748b]">Sampling 1s...</div>
                )}
              </div>
            </div>

            {/* Segmented Rate Pill Track */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-mono uppercase tracking-wider text-[#94a3b8] font-semibold flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Target Throughput Rate</span>
                </label>
                <span className="text-[11px] font-mono text-[#64748b]">
                  {effectiveSimulatorRunning ? (
                    <span className="text-emerald-400">● Locked while running</span>
                  ) : (
                    'Select rate before starting'
                  )}
                </span>
              </div>

              <div
                role="group"
                aria-label="Target Throughput Rate"
                className="grid grid-cols-5 gap-1 p-1 rounded-xl bg-[#070d19] border border-white/[0.08]"
              >
                {[
                  { value: 15, label: '15/s' },
                  { value: 50, label: '50/s' },
                  { value: 100, label: '100/s Default' },
                  { value: 250, label: '250/s' },
                  { value: 500, label: '500/s' },
                ].map((opt) => {
                  const isSelected = selectedRate === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      aria-pressed={isSelected}
                      disabled={effectiveSimulatorRunning}
                      onClick={() => {
                        setSelectedRate(opt.value);
                        if (hud?.setSimulatorRate) {
                          hud.setSimulatorRate(opt.value);
                        }
                      }}
                      title={
                        effectiveSimulatorRunning
                          ? 'Stop generator to change target rate'
                          : `Set target rate to ${opt.value} msgs/sec`
                      }
                      className={`px-2 py-2 rounded-lg text-center font-mono text-xs tabular-nums transition-all ${
                        isSelected
                          ? 'bg-[#1a73e8] text-white font-bold shadow-sm'
                          : 'bg-transparent hover:bg-white/[0.05] text-[#94a3b8] hover:text-white font-medium'
                      } ${
                        effectiveSimulatorRunning
                          ? 'opacity-60 cursor-not-allowed'
                          : 'cursor-pointer'
                      }`}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* State-Aware Primary Toggle Button */}
          <div className="pt-4 border-t border-white/[0.08] flex items-center justify-between gap-3">
            {effectiveSimulatorRunning ? (
              <button
                type="button"
                disabled={loadingAction === 'stop'}
                onClick={() => handleStartStop(false)}
                className="w-full px-4 py-2.5 rounded-xl font-mono text-xs uppercase tracking-wider font-bold transition-all flex items-center justify-center gap-2 bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/35 disabled:opacity-40 cursor-pointer"
              >
                {loadingAction === 'stop' ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Square className="w-3.5 h-3.5 fill-current" />
                )}
                <span>Stop Telemetry Generator</span>
              </button>
            ) : (
              <button
                type="button"
                disabled={loadingAction === 'start'}
                onClick={() => handleStartStop(true)}
                className="w-full px-4 py-2.5 rounded-xl font-mono text-xs uppercase tracking-wider font-bold transition-all flex items-center justify-center gap-2 bg-[#1a73e8] hover:bg-[#1557b0] text-white border border-[#adc7ff]/30 shadow-md shadow-[#1a73e8]/25 disabled:opacity-40 cursor-pointer"
              >
                {loadingAction === 'start' ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5 fill-white" />
                )}
                <span>Start Telemetry Generator ({selectedRate} msgs/s)</span>
              </button>
            )}
          </div>
        </div>

        {/* Card 2: Stream Processing Pipeline */}
        <div className="p-5 rounded-xl bg-[#0b1326]/90 border border-white/[0.08] flex flex-col justify-between space-y-5">
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#68abff]" />
                <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                  {stackConfig.pipelineName}
                </h3>
              </div>
              {/* Status Badge */}
              <div
                className={`px-2.5 py-1 rounded-md border text-[11px] font-mono uppercase tracking-widest font-bold flex items-center gap-1.5 ${
                  pipelineStatus === 'RUNNING' || pipelineStatus === 'ACTIVE'
                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/35'
                    : pipelineStatus === 'PENDING'
                    ? 'bg-[#1a73e8]/20 text-[#68abff] border-[#1a73e8]/40'
                    : pipelineStatus === 'FAILED'
                    ? 'bg-rose-500/15 text-rose-400 border-rose-500/35'
                    : 'bg-amber-500/15 text-amber-400 border-amber-500/35'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    isPipelineActive
                      ? pipelineStatus === 'PENDING'
                        ? 'bg-[#68abff] animate-ping'
                        : 'bg-emerald-400 animate-pulse'
                      : pipelineStatus === 'FAILED'
                      ? 'bg-rose-400'
                      : 'bg-amber-400'
                  }`}
                />
                <span>{pipelineStatus}</span>
              </div>
            </div>

            <p className="text-xs text-[#94a3b8] font-sans leading-relaxed">
              {stackConfig.pipelineDescription}
            </p>

            {/* Pre-warmed Cluster & Active Job Metadata */}
            <div className="flex flex-wrap items-center gap-2">
              {stackType === 'oss' && (
                <div className="text-[11px] font-mono text-emerald-300 bg-emerald-950/40 px-3 py-1.5 rounded-lg border border-emerald-500/25 inline-flex items-center gap-1.5">
                  <Zap className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span>
                    Warm Cluster: <strong>{clusterName}</strong> (Vectorized Spark)
                  </span>
                </div>
              )}
              {batchId && (
                <div className="text-[11px] font-mono text-[#94a3b8] bg-[#070d19] px-3 py-1.5 rounded-lg border border-white/[0.08] inline-block">
                  JOB ID: <span className="font-bold text-white">{batchId}</span>
                </div>
              )}
            </div>

            {/* Status Callout Box */}
            {pipelineStatus === 'FAILED' && (
              <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/35 text-rose-200 text-xs font-mono space-y-1">
                <div className="flex items-center gap-1.5 font-bold text-rose-400">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>PIPELINE EXECUTION FAILED</span>
                </div>
                <div className="text-[11px] leading-relaxed break-words">
                  {pipelineError || pipelineMessage || stackConfig.pipelineErrorDesc}
                </div>
              </div>
            )}

            {pipelineStatus === 'PENDING' && (
              <div className="p-3.5 rounded-xl bg-[#070d19] border border-[#1a73e8]/40 text-[#68abff] text-xs font-mono flex items-start gap-2.5">
                <RefreshCw className="w-4 h-4 animate-spin shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold text-white mb-0.5">{stackConfig.pipelineInitTitle}</div>
                  <div className="text-[11px] text-[#94a3b8] leading-relaxed">
                    {pipelineMessage || stackConfig.pipelineInitDesc}
                  </div>
                </div>
              </div>
            )}

            {(pipelineStatus === 'RUNNING' || pipelineStatus === 'ACTIVE') && (
              <div className="p-3.5 rounded-xl bg-[#070d19] border border-emerald-500/25 text-emerald-300 text-xs font-mono flex items-center gap-2.5">
                <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="truncate">
                  {pipelineMessage || stackConfig.pipelineRunningDesc}
                </span>
              </div>
            )}

            {(pipelineStatus === 'STOPPED' || pipelineStatus === 'CANCELLED') && (
              <div className="p-3.5 rounded-xl bg-[#070d19] border border-white/[0.08] text-[#94a3b8] text-xs font-mono flex items-center gap-2.5">
                <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
                <span>{pipelineMessage || stackConfig.pipelineStoppedDesc}</span>
              </div>
            )}
          </div>

          {/* State-Aware Primary Pipeline Button + Refresh */}
          <div className="pt-4 border-t border-white/[0.08] flex items-center gap-2.5">
            {isPipelineActive ? (
              <button
                type="button"
                disabled={pipelineLoading === 'stop'}
                onClick={() => handleTogglePipeline(false)}
                className="flex-1 px-4 py-2.5 rounded-xl font-mono text-xs uppercase tracking-wider font-bold transition-all flex items-center justify-center gap-2 bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/35 disabled:opacity-40 cursor-pointer"
              >
                {pipelineLoading === 'stop' ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Square className="w-3.5 h-3.5 fill-current" />
                )}
                <span>{stackConfig.pipelineButtonStop}</span>
              </button>
            ) : (
              <button
                type="button"
                disabled={pipelineLoading === 'start'}
                onClick={() => handleTogglePipeline(true)}
                className="flex-1 px-4 py-2.5 rounded-xl font-mono text-xs uppercase tracking-wider font-bold transition-all flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white border border-emerald-400/30 shadow-md shadow-emerald-600/20 disabled:opacity-40 cursor-pointer"
              >
                {pipelineLoading === 'start' ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-3.5 h-3.5 fill-white" />
                )}
                <span>
                  {pipelineStatus === 'FAILED'
                    ? stackConfig.pipelineButtonRetry
                    : stackConfig.pipelineButtonStart}
                </span>
              </button>
            )}

            <button
              type="button"
              onClick={fetchPipelineStatus}
              className="p-2.5 rounded-xl bg-[#070d19] border border-white/[0.08] hover:border-white/20 text-[#68abff] transition-all cursor-pointer"
              title="Refresh pipeline status"
            >
              <RefreshCw className={`w-4 h-4 ${isCheckingPipeline ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Notification Toast */}
      {toastMessage && (
        <div className="p-3 rounded-xl bg-[#0b1326] border border-[#1a73e8]/50 text-[#e2e8f0] text-xs font-mono uppercase tracking-wider flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
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
