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
import { useRouter } from 'next/navigation';
import { useHUD } from '@/context/HUDContext';
import { Module4PipelineFlow } from '@/components/Module4PipelineFlow';
import { TelemetryGrid } from '@/components/TelemetryGrid';
import { AgentCoPilot } from '@/components/AgentCoPilot';
import { PageNavigation } from '@/components/PageNavigation';

export const LiveGridAndCopilot: React.FC = () => {
  const router = useRouter();
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
    <div className="space-y-6 animate-fade-in">
      {/* 5-Step Operational Pipeline Progress Strip & Inactive Stream Banner */}
      <Module4PipelineFlow
        criticalCount={criticalCount}
        selectedAssetId={selectedAsset?.asset_id || null}
        hasMitigation={!!mitigationData}
        isSimulatorRunning={isSimulatorRunning}
        isPipelineActive={isPipelineActive}
        onStartSimulator={() => handleToggleSimulator(true)}
        onStartPipeline={() => handleTogglePipeline(true)}
        onStartBoth={handleStartBoth}
        onNavigateToSimulator={() => router.push('/simulator')}
      />

      {/* Side-by-Side Split Operations Workspace: Left 7 Cols Grid, Right 5 Cols Sticky AI Co-Pilot */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        <div className="xl:col-span-7">
          <TelemetryGrid
            assets={assets}
            selectedAssetId={selectedAsset?.asset_id || null}
            onSelectAsset={(asset) => {
              setSelectedAsset(asset);
              if (typeof window !== 'undefined' && window.innerWidth < 1280) {
                setTimeout(() => {
                  copilotRef.current?.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start',
                  });
                }, 50);
              }
            }}
            onInjectAnomaly={() => handleInjectAnomaly()}
            isInjecting={isInjectingAnomaly}
            isDemoActive={isDemoActive}
          />
        </div>

        <div ref={copilotRef} className="xl:col-span-5 xl:sticky xl:top-16">
          <AgentCoPilot
            selectedAsset={selectedAsset}
            mitigationData={mitigationData}
            isLoadingMitigation={isLoadingMitigation}
            onExecuteMitigation={handleExecuteMitigation}
            onApproveAndApply={handleApproveAndApply}
            isDemoActive={isDemoActive}
          />
        </div>
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
