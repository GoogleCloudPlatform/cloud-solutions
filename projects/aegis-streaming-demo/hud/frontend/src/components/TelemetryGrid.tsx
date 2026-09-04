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
import { Cpu, Thermometer, Gauge, HardDrive, AlertOctagon, Bot, ShieldCheck, Flame, RefreshCw, Database, ExternalLink, Activity, Lock, Clock, AlertTriangle, ArrowRight } from 'lucide-react';
import { getConsoleLinks } from '../utils/gcpConsoleLinks';
import { isDataStale, getDataAgeInfo, isFleetStale } from '../utils/telemetryUtils';

interface TelemetryGridProps {
  assets: AssetState[];
  selectedAssetId: string | null;
  onSelectAsset: (asset: AssetState) => void;
  onInjectAnomaly?: (assetId?: string) => Promise<void> | void;
  onNavigateToSimulator?: () => void;
  isInjecting?: boolean;
  isDemoActive?: boolean;
}

export const TelemetryGrid: React.FC<TelemetryGridProps> = ({
  assets,
  selectedAssetId,
  onSelectAsset,
  onInjectAnomaly,
  onNavigateToSimulator,
  isInjecting = false,
  isDemoActive = true,
}) => {
  const [isRefreshingBt, setIsRefreshingBt] = useState<boolean>(false);
  const [, setTick] = useState<number>(0);
  const consoleLinks = getConsoleLinks();

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
    <section className={`w-full glass-panel rounded-2xl p-6 border transition-all duration-300 shadow-xl space-y-4 ${
      fleetStale
        ? 'border-[#f59e0b]/40 bg-[#060e20]/95'
        : !isDemoActive
        ? 'border-[#334155]/60 bg-[#060e20]/90'
        : 'border-[#334155]'
    }`}>
      {/* Header with Cloud Bigtable Provenance */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 pb-4 border-b border-[#334155]">
        <div>
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-[#adc7ff]" />
            <h2 className="text-lg font-headline font-bold text-white uppercase tracking-wide">
              Module 4a: Cloud Bigtable Operational Telemetry Grid
            </h2>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider border flex items-center gap-1 ${
              fleetStale
                ? 'bg-[#f59e0b]/20 text-[#fbbf24] border-[#f59e0b]/50'
                : isDemoActive
                ? 'bg-[#1a73e8]/20 text-[#adc7ff] border-[#1a73e8]/50'
                : 'bg-[#2d3449] text-[#8b909f] border-[#334155]'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${
                fleetStale
                  ? 'bg-[#f59e0b]'
                  : isDemoActive
                  ? 'bg-[#6ddd81] animate-pulse'
                  : 'bg-[#8b909f]'
              }`} />
              {fleetStale
                ? 'TELEMETRY EXPIRED (>60M)'
                : isDemoActive
                ? 'LIVE BIGTABLE SINK'
                : 'INGESTION INACTIVE (LOCKED)'}
            </span>
          </div>
          <p className="text-xs text-[#c1c6d6] font-sans mt-1">
            Real-Time State Table: <code className="text-[#adc7ff] font-mono">telemetry_metrics</code> (Family: <code className="text-[#6ddd81] font-mono">metrics</code>) — Sub-Millisecond Point Lookups &amp; State Serving
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Bigtable Console Link */}
          <a
            href={consoleLinks.bigtableTable}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 rounded bg-[#131b2e] hover:bg-[#1f2b48] border border-[#334155] text-xs font-mono text-[#adc7ff] flex items-center gap-1.5 transition-all"
            title="Open Cloud Bigtable Table in Google Cloud Console"
          >
            <Database className="w-3.5 h-3.5" />
            <span>Bigtable Console</span>
            <ExternalLink className="w-3 h-3 text-[#c1c6d6]" />
          </a>

          {/* Status Legend */}
          <div className="flex items-center gap-3 text-xs font-mono uppercase tracking-wider px-2 py-1 rounded bg-[#0a0f1d] border border-[#334155]/60">
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#6ddd81]" />
              <span className="text-[#dae2fd]">OK</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#FBBC04]" />
              <span className="text-[#dae2fd]">&gt;75%</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-[#D93025]" />
              <span className="text-[#ffb4ab] font-bold">&gt;90% CRITICAL</span>
            </div>
            <div className="flex items-center gap-1 pl-1 border-l border-[#334155]">
              <span className="w-2 h-2 rounded-full bg-[#8b909f]" />
              <span className="text-[#8b909f]">&gt;60m STALE</span>
            </div>
          </div>

          {onInjectAnomaly && (
            <button
              disabled={isInjecting || !isDemoActive || fleetStale}
              onClick={() => {
                if (!isDemoActive || fleetStale) return;
                onInjectAnomaly();
              }}
              className={`px-3.5 py-1.5 rounded font-mono text-xs uppercase tracking-wider font-bold transition-all duration-200 flex items-center gap-1.5 border ${
                fleetStale
                  ? 'bg-[#1e293b] border-[#475569]/50 text-[#64748b] cursor-not-allowed opacity-50 shadow-none'
                  : !isDemoActive
                  ? 'bg-[#1e293b] border-[#475569]/50 text-[#64748b] cursor-not-allowed opacity-50 shadow-none'
                  : 'bg-[#D93025] hover:bg-[#ff6b60] text-white border-[#ffdad6]/40 shadow-[0_0_15px_rgba(217,48,37,0.4)] animate-pulse disabled:opacity-50 disabled:cursor-not-allowed'
              }`}
              title={
                fleetStale
                  ? 'Telemetry is stale (>60m). Activate the demo stream to enable live anomaly injection.'
                  : !isDemoActive
                  ? 'Demo locked: Start Kafka generator & Spark pipeline above to enable anomaly injection'
                  : 'Inject thermal and compute anomaly into a random industrial asset'
              }
            >
              {isInjecting ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : fleetStale || !isDemoActive ? (
                <Lock className="w-3.5 h-3.5 text-[#64748b]" />
              ) : (
                <Flame className="w-3.5 h-3.5 text-[#FBBC04]" />
              )}
              <span>INJECT ANOMALY</span>
            </button>
          )}
        </div>
      </div>

      {/* Stale Telemetry Notice Banner when Fleet is Idle / Stale */}
      {fleetStale && (
        <div className="p-4 rounded-xl bg-[#131b2e]/95 border border-[#f59e0b]/50 shadow-[0_0_20px_rgba(245,158,11,0.15)] flex flex-col md:flex-row items-start md:items-center justify-between gap-4 animate-fade-in">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-lg bg-[#f59e0b]/20 border border-[#f59e0b]/50 text-[#fbbf24] shrink-0 mt-0.5">
              <Clock className="w-5 h-5 text-[#f59e0b] animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-headline font-bold text-white uppercase tracking-wider">
                  Telemetry Stream Idle — Data Too Old (&gt;60 Minutes)
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-[#f59e0b]/20 text-[#fbbf24] border border-[#f59e0b]/50">
                  DEMO IDLE
                </span>
              </div>
              <p className="text-xs text-[#dae2fd] mt-1 font-sans">
                The demonstration pipeline has not ingested new events for more than 60 minutes. Asset metrics below are grayed out. <strong>Activate the demo in Module 2 and wait for new streaming data to arrive.</strong>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Bigtable Storage Architecture Banner */}
      <div className="p-3 rounded-lg bg-[#0a0f1d]/80 border border-[#2d3449] flex flex-col md:flex-row items-start md:items-center justify-between gap-2 text-xs font-mono text-[#c1c6d6]">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#6ddd81]" />
          <span>Operational Bigtable Instance: <strong className="text-white">aegis-bigtable</strong></span>
          <span className="text-[#8b909f]">|</span>
          <span>Dual Sink: <strong className="text-[#adc7ff]">Bigtable (Operational) + BigQuery (Analytics)</strong></span>
        </div>
        <div className="text-[11px] text-[#8b909f] flex items-center gap-2">
          <span>RowKey: <code className="text-[#adc7ff]">Asset-XX</code></span>
          <span>•</span>
          <span>Column Family: <code className="text-[#6ddd81]">metrics:cpu,temp,pressure,memory,status</code></span>
        </div>
      </div>

      {/* 15 Asset Responsive Grid with tight data-density-sm (gap-2) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
        {displayAssets.map((asset) => {
          const ageInfo = getDataAgeInfo(asset.timestamp);
          const isStale = ageInfo.isStale;
          const isCritical = !isStale && (asset.cpu_utilization > 90 || asset.temperature_c > 90 || asset.status === 'CRITICAL');
          const isWarning = !isStale && !isCritical && (asset.cpu_utilization > 75 || asset.temperature_c > 75 || asset.status === 'WARNING');
          const isSelected = selectedAssetId === asset.asset_id;

          return (
            <div
              key={asset.asset_id}
              onClick={() => {
                if (!isDemoActive || isStale) return;
                onSelectAsset(asset);
              }}
              className={`relative rounded-lg p-3.5 transition-all duration-300 border flex flex-col justify-between ${
                isStale
                  ? 'bg-[#060e20]/60 border-[#334155]/50 opacity-60 cursor-not-allowed select-none'
                  : !isDemoActive
                  ? 'bg-[#131b2e]/40 border-[#334155]/40 opacity-60 cursor-not-allowed'
                  : isCritical
                  ? 'border-2 border-[#D93025] bg-[#93000a]/30 shadow-[0_0_20px_rgba(217,48,37,0.5)] animate-anomaly-glow text-white cursor-pointer'
                  : isWarning
                  ? 'bg-[#2d3449]/80 border-[#FBBC04] text-white hover:border-[#FBBC04] cursor-pointer'
                  : isSelected
                  ? 'bg-[#1a73e8]/25 border-2 border-[#adc7ff] shadow-[0_0_15px_rgba(173,199,255,0.25)] cursor-pointer'
                  : 'bg-[#131b2e]/70 border-[#334155] hover:border-[#adc7ff]/60 hover:bg-[#171f33]/80 cursor-pointer'
              }`}
            >
              {/* Tile Header */}
              <div>
                <div className="flex items-center justify-between pb-1.5 border-b border-[#334155]/60">
                  <div>
                    <span className={`font-mono font-bold text-sm tracking-widest ${isStale ? 'text-[#8b909f]' : 'text-white'}`}>
                      {asset.asset_id}
                    </span>
                    <div className="text-[10px] font-mono flex items-center gap-1 mt-0.5">
                      <Clock className={`w-2.5 h-2.5 ${isStale ? 'text-[#f59e0b]' : 'text-[#adc7ff]'}`} />
                      <span className={isStale ? 'text-[#f59e0b]' : 'text-[#8b909f]'}>
                        {ageInfo.relativeText}{isStale ? ' (stale)' : ''}
                      </span>
                    </div>
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest ${
                    isStale
                      ? 'bg-[#1e293b] text-[#94a3b8] border border-[#475569]/60'
                      : !isDemoActive
                      ? 'bg-[#1e293b] text-[#64748b] border border-[#334155]'
                      : isCritical
                      ? 'bg-[#D93025] text-white animate-pulse shadow-[0_0_8px_rgba(217,48,37,0.8)]'
                      : isWarning
                      ? 'bg-[#FBBC04]/20 text-[#FBBC04] border border-[#FBBC04]/50'
                      : 'bg-[#30a550]/20 text-[#6ddd81] border border-[#30a550]/50'
                  }`}>
                    {isStale ? 'EXPIRED' : asset.status}
                  </span>
                </div>

                {/* Stale Asset In-Card Notice */}
                {isStale && (
                  <div className="my-2.5 p-2 rounded-lg bg-[#0b1326]/90 border border-[#334155] text-center space-y-0.5">
                    <div className="flex items-center justify-center gap-1 text-[#fbbf24] font-mono text-[10px] font-bold uppercase tracking-wider">
                      <Clock className="w-3 h-3 text-[#f59e0b]" />
                      <span>Data Too Old (&gt;60m)</span>
                    </div>
                    <p className="text-[10px] text-[#94a3b8] font-sans leading-tight">
                      Activate demo &amp; wait for new data
                    </p>
                  </div>
                )}

                {/* Metric Gauges */}
                <div className={`mt-2.5 space-y-2 text-xs font-mono ${isStale ? 'opacity-40 grayscale' : ''}`}>
                  {/* CPU */}
                  <div className="flex items-center justify-between">
                    <span className="text-[#c1c6d6] flex items-center gap-1">
                      <Cpu className="w-3.5 h-3.5 text-[#adc7ff]" /> CPU:
                    </span>
                    <span className={`font-bold ${isStale ? 'text-[#8b909f]' : !isDemoActive ? 'text-[#8b909f]' : asset.cpu_utilization > 90 ? 'text-[#ffb4ab] font-extrabold' : 'text-[#dae2fd]'}`}>
                      {asset.cpu_utilization.toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-[#060e20] h-1.5 rounded-full overflow-hidden border border-[#334155]/40">
                    <div
                      className={`h-full transition-all duration-300 ${
                        isStale ? 'bg-[#475569]' : !isDemoActive ? 'bg-[#475569]' : asset.cpu_utilization > 90 ? 'bg-[#D93025]' : asset.cpu_utilization > 75 ? 'bg-[#FBBC04]' : 'bg-[#adc7ff]'
                      }`}
                      style={{ width: `${Math.min(100, asset.cpu_utilization)}%` }}
                    />
                  </div>

                  {/* Temp */}
                  <div className="flex items-center justify-between">
                    <span className="text-[#c1c6d6] flex items-center gap-1">
                      <Thermometer className="w-3.5 h-3.5 text-[#ffb691]" /> Temp:
                    </span>
                    <span className={`font-bold ${isStale ? 'text-[#8b909f]' : !isDemoActive ? 'text-[#8b909f]' : asset.temperature_c > 90 ? 'text-[#ffb4ab] font-extrabold' : 'text-[#dae2fd]'}`}>
                      {asset.temperature_c.toFixed(1)}°C
                    </span>
                  </div>
                  <div className="w-full bg-[#060e20] h-1.5 rounded-full overflow-hidden border border-[#334155]/40">
                    <div
                      className={`h-full transition-all duration-300 ${
                        isStale ? 'bg-[#475569]' : !isDemoActive ? 'bg-[#475569]' : asset.temperature_c > 90 ? 'bg-[#D93025]' : asset.temperature_c > 75 ? 'bg-[#FBBC04]' : 'bg-[#ffb691]'
                      }`}
                      style={{ width: `${Math.min(100, (asset.temperature_c / 120) * 100)}%` }}
                    />
                  </div>

                  {/* Pressure & Memory */}
                  <div className="pt-1.5 flex items-center justify-between text-[11px] text-[#8b909f] border-t border-[#334155]/40">
                    <span className="flex items-center gap-1">
                      <Gauge className="w-3 h-3 text-[#6ddd81]" /> {asset.pressure_psi.toFixed(0)} PSI
                    </span>
                    <span className="flex items-center gap-1">
                      <HardDrive className="w-3 h-3 text-[#adc7ff]" /> {asset.memory_utilization_pct.toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <div className="mt-3 pt-2 border-t border-[#334155]/60">
                {isStale ? (
                  <button
                    disabled
                    className="w-full py-1.5 rounded bg-[#1e293b]/70 border border-[#334155]/60 text-[#64748b] font-mono text-[11px] tracking-wider flex items-center justify-center gap-1.5 cursor-not-allowed opacity-70"
                    title="Data is older than 60 minutes. Activate the demo and wait for new data to come in."
                  >
                    <Clock className="w-3 h-3 text-[#64748b]" />
                    <span>DATA TOO OLD</span>
                  </button>
                ) : !isDemoActive ? (
                  <button
                    disabled
                    className="w-full py-1.5 rounded bg-[#1e293b] border border-[#334155]/60 text-[#64748b] font-mono text-[11px] tracking-wider flex items-center justify-center gap-1 cursor-not-allowed opacity-50 shadow-none"
                    title="Demo locked: Start Kafka generator & Spark pipeline above to enable"
                  >
                    <Lock className="w-3 h-3 text-[#64748b]" />
                    <span>LOCKED</span>
                  </button>
                ) : isCritical ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectAsset(asset);
                    }}
                    className="w-full py-1.5 rounded bg-[#D93025] hover:bg-[#ff6b60] text-white font-mono text-[11px] font-bold tracking-widest flex items-center justify-center gap-1.5 transition-all shadow-md shadow-[#93000a]"
                  >
                    <span>Inspect Asset</span>
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectAsset(asset);
                    }}
                    className="w-full py-1 rounded border border-[#8b909f]/60 hover:border-[#adc7ff] hover:bg-[#1a73e8] text-[#dae2fd] hover:text-white font-mono text-[11px] tracking-wider flex items-center justify-center gap-1 transition-all"
                  >
                    <span>Inspect Asset</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};
