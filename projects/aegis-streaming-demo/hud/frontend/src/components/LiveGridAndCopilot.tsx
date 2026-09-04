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

import React, { useRef } from 'react';
import { useHUD } from '@/context/HUDContext';
import { Module4PipelineFlow } from '@/components/Module4PipelineFlow';
import { TelemetryGrid } from '@/components/TelemetryGrid';
import { AgentCoPilot } from '@/components/AgentCoPilot';
import { PageNavigation } from '@/components/PageNavigation';

export const LiveGridAndCopilot: React.FC = () => {
  const {
    assets,
    criticalCount,
    selectedAsset,
    setSelectedAsset,
    mitigationData,
    isLoadingMitigation,
    isInjectingAnomaly,
    isSimulatorRunning,
    isPipelineActive,
    isDemoActive,
    handleToggleSimulator,
    handleTogglePipeline,
    handleStartBoth,
    handleInjectAnomaly,
    handleExecuteMitigation,
    handleApproveAndApply,
  } = useHUD();

  const copilotRef = useRef<HTMLDivElement>(null);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* 5-Step Operational Pipeline Flow Cards & Inactive Stream Banner */}
      <Module4PipelineFlow
        criticalCount={criticalCount}
        selectedAssetId={selectedAsset?.asset_id || null}
        hasMitigation={!!mitigationData}
        isSimulatorRunning={isSimulatorRunning}
        isPipelineActive={isPipelineActive}
        onStartSimulator={() => handleToggleSimulator(true)}
        onStartPipeline={() => handleTogglePipeline(true)}
        onStartBoth={handleStartBoth}
        onNavigateToSimulator={() => {}}
      />

      {/* Live Bigtable Operational Telemetry Grid */}
      <TelemetryGrid
        assets={assets}
        selectedAssetId={selectedAsset?.asset_id || null}
        onSelectAsset={(asset) => {
          setSelectedAsset(asset);
          setTimeout(() => {
            copilotRef.current?.scrollIntoView({
              behavior: 'smooth',
              block: 'start',
            });
          }, 50);
        }}
        onInjectAnomaly={() => handleInjectAnomaly()}
        onNavigateToSimulator={() => {}}
        isInjecting={isInjectingAnomaly}
        isDemoActive={isDemoActive}
      />

      {/* AI Agent Execution Co-Pilot */}
      <div ref={copilotRef} className="pt-4 border-t border-[#334155]/80">
        <AgentCoPilot
          selectedAsset={selectedAsset}
          mitigationData={mitigationData}
          isLoadingMitigation={isLoadingMitigation}
          onExecuteMitigation={handleExecuteMitigation}
          onApproveAndApply={handleApproveAndApply}
          isDemoActive={isDemoActive}
        />
      </div>

      {/* Step Navigation */}
      <PageNavigation
        prevTab={{ id: 'guide', label: '3. Demo Guide' }}
        nextTab={{ id: 'analytics', label: '5. Batch Analytics' }}
      />
    </div>
  );
};

export default LiveGridAndCopilot;
