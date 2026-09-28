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
import { AssetState } from '../types';
import {
  Cpu,
  Thermometer,
  Gauge,
  HardDrive,
  Flame,
  RefreshCw,
  Database,
  Lock,
  Clock,
  ArrowRight
} from 'lucide-react';
import { getDataAgeInfo, isFleetStale } from '../utils/telemetryUtils';
import { getStackConfig } from '../utils/stackConfig';

interface TelemetryGridProps {
  assets: AssetState[];
  selectedAssetId: string | null;
  onSelectAsset: (asset: AssetState) => void;
  onInjectAnomaly?: (assetId?: string) => Promise<void> | void;
  isInjecting?: boolean;
  isDemoActive?: boolean;
}

export const TelemetryGrid: React.FC<TelemetryGridProps> = ({
  assets,
  selectedAssetId,
  onSelectAsset,
  onInjectAnomaly,
  isInjecting = false,
  isDemoActive = true,
}) => {
  const [, setTick] = useState<number>(0);
  const stackConfig = getStackConfig();

  // 1-second interval to keep relative time strings ("6 seconds ago") fresh
  useEffect(() => {
    const interval = setInterval(() => {
      setTick((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Ensure 15 assets exist, filling defaults if stream initial connection
  const displayAssets: AssetState[] = Array.from({ length: 15 }, (_, i) => {
    const id = `Asset-${(i + 1).toString().padStart(2, '0')}`;
    const found = assets.find(a => a.asset_id === id);
    if (found) return found;
    return {
      asset_id: id,
      cpu_utilization: 30.0,
      temperature_c: 50.0,
      pressure_psi: 35.0,
      memory_utilization_pct: 40.0,
      status: 'OK',
      is_anomaly: false,
      timestamp: new Date().toISOString(),
    };
  });

  const fleetStale = isFleetStale(displayAssets);

  return (
    <section
      className={`w-full glass-panel rounded-2xl p-5 transition-all duration-300 space-y-4 ${
        fleetStale
          ? 'border-amber-500/35 bg-[#070d19]/95'
          : !isDemoActive
          ? 'border-white/[0.06] bg-[#070d19]/90'
          : ''
      }`}
    >
      {/* Header with Cloud Bigtable Provenance & Inject Anomaly CTA */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-3.5 border-b border-white/[0.08]">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Database className="w-4 h-4 text-[#68abff]" />
            <h2 className="text-base font-headline font-bold text-white uppercase tracking-wide">
              Cloud Bigtable Telemetry Grid
            </h2>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider border flex items-center gap-1 ${
                fleetStale
                  ? 'bg-amber-500/15 text-amber-400 border-amber-500/40'
                  : isDemoActive
                  ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                  : 'bg-white/[0.04] text-[#94a3b8] border-white/[0.08]'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  fleetStale
                    ? 'bg-amber-400'
                    : isDemoActive
                    ? 'bg-emerald-400 animate-pulse'
                    : 'bg-[#64748b]'
                }`}
              />
              {fleetStale
                ? 'STALE (>60M)'
                : isDemoActive
                ? 'LIVE • telemetry_metrics'
                : 'LOCKED'}
            </span>
          </div>
          <p className="text-xs text-[#94a3b8] font-sans mt-0.5">
            Click any asset tile to inspect in the AI Co-Pilot &bull; RowKey:{' '}
            <code className="text-[#68abff] font-mono">Asset-01..15</code>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 self-end sm:self-auto">
          {/* Compact Legend */}
          <div className="hidden md:flex items-center gap-2.5 text-[10px] font-mono uppercase tracking-wider px-2.5 py-1.5 rounded-lg bg-[#070d19] border border-white/[0.08]">
            <span className="flex items-center gap-1 text-[#cbd5e1]">
              <span className="w-2 h-2 rounded-full bg-emerald-400" /> OK
            </span>
            <span className="flex items-center gap-1 text-[#cbd5e1]">
              <span className="w-2 h-2 rounded-full bg-amber-400" /> &gt;75%
            </span>
            <span className="flex items-center gap-1 text-rose-300 font-bold">
              <span className="w-2 h-2 rounded-full bg-rose-500" /> &gt;90% CRIT
            </span>
          </div>

          {onInjectAnomaly && (
            <button
              type="button"
              disabled={isInjecting || !isDemoActive || fleetStale}
              onClick={() => {
                if (!isDemoActive || fleetStale) return;
                onInjectAnomaly();
              }}
              className={`px-3.5 py-2 rounded-xl font-mono text-xs uppercase tracking-wider font-bold transition-all duration-200 flex items-center gap-1.5 border ${
                fleetStale || !isDemoActive
                  ? 'bg-[#0f172a] border-white/[0.08] text-[#64748b] cursor-not-allowed opacity-50'
                  : 'bg-rose-600 hover:bg-rose-500 text-white border-rose-400/40 shadow-[0_0_18px_-3px_rgba(225,29,72,0.55)] cursor-pointer disabled:opacity-50'
              }`}
              title={
                fleetStale
                  ? 'Telemetry is stale (>60m). Activate the demo stream to enable live anomaly injection.'
                  : !isDemoActive
                  ? stackConfig.lockBannerText
                  : 'Inject thermal and compute anomaly into a random industrial asset'
              }
            >
              {isInjecting ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : fleetStale || !isDemoActive ? (
                <Lock className="w-3.5 h-3.5 text-[#64748b]" />
              ) : (
                <Flame className="w-3.5 h-3.5 text-amber-300" />
              )}
              <span>Inject Anomaly</span>
            </button>
          )}
        </div>
      </div>

      {/* Stale Telemetry Notice Banner when Fleet is Idle / Stale */}
      {fleetStale && (
        <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-500/40 flex items-start gap-3 animate-fade-in">
          <Clock className="w-4 h-4 text-amber-400 shrink-0 mt-0.5 animate-pulse" />
          <div className="text-xs text-[#e2e8f0] font-sans">
            <strong className="text-amber-300 font-mono uppercase">
              Telemetry Stream Idle (&gt;60m):
            </strong>{' '}
            Activate the stream in Module 2 and wait for fresh sensor windows to arrive.
          </div>
        </div>
      )}

      {/* 15 Asset Responsive Grid (3x5 on Desktop Split View) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
        {displayAssets.map((asset) => {
          const ageInfo = getDataAgeInfo(asset.timestamp);
          const isStale = ageInfo.isStale;
          const isCritical =
            !isStale &&
            (asset.cpu_utilization > 90 ||
              asset.temperature_c > 90 ||
              asset.status === 'CRITICAL' ||
              asset.is_anomaly);
          const isWarning =
            !isStale &&
            !isCritical &&
            (asset.cpu_utilization > 75 ||
              asset.temperature_c > 75 ||
              asset.status === 'WARNING');
          const isSelected = selectedAssetId === asset.asset_id;

          return (
            <div
              key={asset.asset_id}
              role="button"
              tabIndex={isStale || !isDemoActive ? -1 : 0}
              aria-pressed={isSelected}
              onClick={() => {
                if (!isDemoActive || isStale) return;
                onSelectAsset(asset);
              }}
              onKeyDown={(e) => {
                if (!isDemoActive || isStale) return;
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectAsset(asset);
                }
              }}
              className={`group relative rounded-xl p-3.5 transition-all duration-200 border flex flex-col justify-between ${
                isStale
                  ? 'bg-[#070d19]/60 border-white/[0.05] opacity-55 cursor-not-allowed select-none'
                  : !isDemoActive
                  ? 'bg-[#0b1326]/40 border-white/[0.05] opacity-60 cursor-not-allowed'
                  : isCritical
                  ? 'border-rose-500 bg-rose-950/35 shadow-[0_0_22px_-4px_rgba(239,68,68,0.55)] animate-anomaly-glow text-white cursor-pointer'
                  : isWarning
                  ? 'bg-amber-950/20 border-amber-500/50 text-white hover:border-amber-400 cursor-pointer'
                  : isSelected
                  ? 'bg-[#1a73e8]/15 border-[#68abff] ring-1 ring-[#68abff]/40 cursor-pointer'
                  : 'bg-[#070d19]/90 border-white/[0.08] hover:border-white/25 hover:bg-[#0d182e] cursor-pointer'
              }`}
            >
              {/* Tile Header */}
              <div className="flex items-center justify-between pb-2 border-b border-white/[0.06]">
                <div>
                  <span
                    className={`font-mono font-bold text-xs tracking-wider ${
                      isStale ? 'text-[#64748b]' : 'text-white'
                    }`}
                  >
                    {asset.asset_id}
                  </span>
                  <div className="text-[10px] font-mono flex items-center gap-1 mt-0.5 tabular-nums">
                    <Clock
                      className={`w-2.5 h-2.5 ${
                        isStale ? 'text-amber-400' : 'text-[#64748b]'
                      }`}
                    />
                    <span className={isStale ? 'text-amber-400' : 'text-[#64748b]'}>
                      {ageInfo.relativeText}
                    </span>
                  </div>
                </div>

                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider ${
                    isStale
                      ? 'bg-white/[0.04] text-[#64748b] border border-white/[0.08]'
                      : !isDemoActive
                      ? 'bg-white/[0.04] text-[#64748b] border border-white/[0.08]'
                      : isCritical
                      ? 'bg-rose-600 text-white animate-pulse shadow-sm'
                      : isWarning
                      ? 'bg-amber-500/15 text-amber-400 border border-amber-500/40'
                      : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/25'
                  }`}
                >
                  {isStale
                    ? 'STALE'
                    : isCritical
                    ? 'CRITICAL'
                    : isWarning
                    ? 'WARNING'
                    : asset.status || 'OK'}
                </span>
              </div>

              {/* Metric Gauges with Tabular Numerals & Calm Nominal Bars */}
              <div
                className={`mt-2.5 space-y-2 text-xs font-mono tabular-nums ${
                  isStale ? 'opacity-40 grayscale' : ''
                }`}
              >
                {/* CPU */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[#94a3b8] flex items-center gap-1 text-[11px]">
                      <Cpu className="w-3 h-3 text-[#68abff]" /> CPU
                    </span>
                    <span
                      className={`font-bold text-[11px] ${
                        isCritical && asset.cpu_utilization > 90
                          ? 'text-rose-300'
                          : 'text-[#e2e8f0]'
                      }`}
                    >
                      {asset.cpu_utilization.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-white/[0.06] h-1.5 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        isStale || !isDemoActive
                          ? 'bg-[#475569]'
                          : asset.cpu_utilization > 90
                          ? 'bg-rose-500'
                          : asset.cpu_utilization > 75
                          ? 'bg-amber-400'
                          : 'bg-blue-500/55'
                      }`}
                      style={{ width: `${Math.min(100, asset.cpu_utilization)}%` }}
                    />
                  </div>
                </div>

                {/* Temp */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[#94a3b8] flex items-center gap-1 text-[11px]">
                      <Thermometer className="w-3 h-3 text-[#68abff]" /> Temp
                    </span>
                    <span
                      className={`font-bold text-[11px] ${
                        isCritical && asset.temperature_c > 90
                          ? 'text-rose-300'
                          : 'text-[#e2e8f0]'
                      }`}
                    >
                      {asset.temperature_c.toFixed(1)}°C
                    </span>
                  </div>
                  <div className="w-full bg-white/[0.06] h-1.5 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${
                        isStale || !isDemoActive
                          ? 'bg-[#475569]'
                          : asset.temperature_c > 90
                          ? 'bg-rose-500'
                          : asset.temperature_c > 75
                          ? 'bg-amber-400'
                          : 'bg-blue-500/55'
                      }`}
                      style={{ width: `${Math.min(100, (asset.temperature_c / 120) * 100)}%` }}
                    />
                  </div>
                </div>

                {/* Pressure, Memory & Contextual Diagnose Indicator */}
                <div className="pt-1.5 flex items-center justify-between text-[10px] text-[#64748b] border-t border-white/[0.06]">
                  <span className="flex items-center gap-1">
                    <Gauge className="w-3 h-3 text-[#64748b]" /> {asset.pressure_psi.toFixed(0)} PSI
                  </span>
                  {isCritical ? (
                    <span className="inline-flex items-center gap-1 text-rose-300 font-bold uppercase tracking-wider">
                      <span>Diagnose</span>
                      <ArrowRight className="w-3 h-3" />
                    </span>
                  ) : isSelected ? (
                    <span className="text-[#68abff] font-bold uppercase tracking-wider">
                      Selected
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <HardDrive className="w-3 h-3 text-[#64748b]" />{' '}
                      {asset.memory_utilization_pct.toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
