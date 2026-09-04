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

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { AssetState, MitigationResponse, TelemetryStreamPayload, AgentApprovalResponse } from '@/types';
import { ToastItem, ToastContainer } from '@/components/ToastNotification';
import { getActiveAnomalies, isFleetStale as checkFleetStale } from '@/utils/telemetryUtils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

interface HUDContextType {
  assets: AssetState[];
  isConnected: boolean;
  selectedAsset: AssetState | null;
  setSelectedAsset: (asset: AssetState | null) => void;
  mitigationData: MitigationResponse | null;
  isLoadingMitigation: boolean;
  isInjectingAnomaly: boolean;
  isSimulatorRunning: boolean;
  pipelineStatus: string;
  isPipelineActive: boolean;
  isDemoActive: boolean;
  criticalCount: number;
  isFleetStale: boolean;
  simulatorRate: number;
  setSimulatorRate: (rate: number) => void;
  toasts: ToastItem[];
  addToast: (toast: Omit<ToastItem, 'id'>) => void;
  removeToast: (id: string) => void;
  handleTogglePipeline: (targetRunningState?: boolean) => Promise<void>;
  handleToggleSimulator: (targetRunningState?: boolean, targetRate?: number) => Promise<void>;
  handleStartBoth: (targetRate?: number) => Promise<void>;
  handleInjectAnomaly: (assetId?: string, metricType?: string) => Promise<void>;
  handleExecuteMitigation: (asset?: AssetState | null) => Promise<void>;
  handleApproveAndApply: (assetId: string) => Promise<AgentApprovalResponse | void>;
}

const HUDContext = createContext<HUDContextType | undefined>(undefined);

export const HUDProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [assets, setAssets] = useState<AssetState[]>([]);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [selectedAsset, setSelectedAsset] = useState<AssetState | null>(null);
  const [mitigationData, setMitigationData] = useState<MitigationResponse | null>(null);
  const [isLoadingMitigation, setIsLoadingMitigation] = useState<boolean>(false);
  const [isInjectingAnomaly, setIsInjectingAnomaly] = useState<boolean>(false);
  const [isSimulatorRunning, setIsSimulatorRunning] = useState<boolean>(false);
  const [simulatorRate, setSimulatorRate] = useState<number>(100);
  const [pipelineStatus, setPipelineStatus] = useState<string>('RUNNING');
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const isPipelineActive =
    pipelineStatus === 'RUNNING' ||
    pipelineStatus === 'ACTIVE' ||
    pipelineStatus === 'PENDING';
  const isDemoActive = isSimulatorRunning && isPipelineActive;

  const handleSetSelectedAsset = useCallback(
    (asset: AssetState | null) => {
      setSelectedAsset(asset);
      if (
        asset &&
        mitigationData &&
        mitigationData.asset_id !== asset.asset_id
      ) {
        setMitigationData(null);
      }
    },
    [mitigationData]
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((toast: Omit<ToastItem, 'id'>) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    const newToast: ToastItem = { ...toast, id };
    setToasts((prev) => [...prev.slice(-5), newToast]);

    setTimeout(() => {
      removeToast(id);
    }, 8500);
  }, [removeToast]);

  const fetchPipelineStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/pipeline/status`);
      if (res.ok) {
        const data = await res.json();
        if (data.status) {
          setPipelineStatus(data.status);
        }
      }
    } catch (e) {
      // Ignore polling errors
    }
  }, []);

  const fetchSimulatorStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/stream-status`);
      if (res.ok) {
        const data = await res.json();
        if (typeof data.running === 'boolean') {
          setIsSimulatorRunning(data.running);
        }
        if (data.running && data.target_rate_msgs_per_sec) {
          setSimulatorRate(data.target_rate_msgs_per_sec);
        }
      }
    } catch (e) {
      // Ignore polling errors
    }
  }, []);

  useEffect(() => {
    fetchSimulatorStatus();
    fetchPipelineStatus();

    const interval = setInterval(() => {
      fetchSimulatorStatus();
      fetchPipelineStatus();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchSimulatorStatus, fetchPipelineStatus]);

  // Initialize SSE connection to GET /api/stream
  useEffect(() => {
    let eventSource: EventSource | null = null;
    let reconnectTimer: NodeJS.Timeout | null = null;
    let isCleanedUp = false;

    const connectSSE = () => {
      if (isCleanedUp) return;
      try {
        const streamUrl = `${API_BASE}/api/stream`;
        eventSource = new EventSource(streamUrl);

        eventSource.onopen = () => {
          if (!isCleanedUp) setIsConnected(true);
        };

        eventSource.onmessage = (event) => {
          if (isCleanedUp) return;
          try {
            const data: TelemetryStreamPayload = JSON.parse(event.data);
            if (data && Array.isArray(data.assets)) {
              setAssets(data.assets);
              setIsConnected(true);

              setSelectedAsset((prev) => {
                if (!prev) return null;
                const target = data.assets.find((a) => a.asset_id === prev.asset_id);
                return target || prev;
              });
            }
          } catch (err) {
            console.error('Error parsing SSE event data:', err);
          }
        };

        eventSource.onerror = (err) => {
          if (isCleanedUp) return;
          console.warn('SSE connection interrupted, retrying in 3s...', err);
          setIsConnected(false);
          if (eventSource) {
            eventSource.close();
            eventSource = null;
          }
          if (!reconnectTimer && !isCleanedUp) {
            reconnectTimer = setTimeout(() => {
              reconnectTimer = null;
              connectSSE();
            }, 3000);
          }
        };
      } catch (err) {
        if (!isCleanedUp) {
          console.error('Failed to initialize SSE:', err);
          setIsConnected(false);
        }
      }
    };

    connectSSE();

    return () => {
      isCleanedUp = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  const handleTogglePipeline = async (targetRunningState?: boolean) => {
    const isCurrentlyRunning = isPipelineActive;
    const shouldStart = targetRunningState !== undefined ? targetRunningState : !isCurrentlyRunning;

    const actionText = shouldStart ? 'Starting' : 'Pausing';
    addToast({
      type: 'info',
      title: `${actionText} Pipeline Stream`,
      message: `Dispatching request to ${shouldStart ? 'launch' : 'drain'} Dataproc Serverless Lightning Engine job...`,
      timestamp: new Date().toLocaleTimeString(),
    });

    try {
      const endpoint = shouldStart ? '/api/pipeline/start' : '/api/pipeline/stop';
      const res = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setPipelineStatus(data.status || (shouldStart ? 'RUNNING' : 'STOPPED'));
        addToast({
          type: 'success',
          title: `Pipeline ${shouldStart ? 'Active' : 'Drained'}`,
          message: data.message || `C++ Velox Spark execution engine is now ${shouldStart ? 'RUNNING' : 'STOPPED'}.`,
          timestamp: new Date().toLocaleTimeString(),
        });
      } else {
        setPipelineStatus(shouldStart ? 'RUNNING' : 'STOPPED');
      }
    } catch (e) {
      setPipelineStatus(shouldStart ? 'RUNNING' : 'STOPPED');
    }
  };

  const handleToggleSimulator = async (targetRunningState?: boolean, targetRate?: number) => {
    const shouldStart = targetRunningState !== undefined ? targetRunningState : !isSimulatorRunning;
    const rateToUse = targetRate ?? simulatorRate;

    addToast({
      type: 'info',
      title: `${shouldStart ? 'Starting' : 'Pausing'} Sensor Simulator`,
      message: shouldStart
        ? `Configuring IIoT telemetry publication across 15 fleet turbines at ${rateToUse} msgs/sec...`
        : `Pausing sensor stream...`,
      timestamp: new Date().toLocaleTimeString(),
    });

    try {
      const endpoint = shouldStart ? '/api/start-stream' : '/api/stop-stream';
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: shouldStart ? JSON.stringify({ rate_msgs_per_sec: rateToUse }) : undefined,
      });
      if (res.ok) {
        const data = await res.json();
        setIsSimulatorRunning(shouldStart);
        if (data.target_rate_msgs_per_sec) {
          setSimulatorRate(data.target_rate_msgs_per_sec);
        }
        addToast({
          type: 'success',
          title: `Simulator ${shouldStart ? 'Streaming' : 'Paused'}`,
          message: data.message || `Telemetry sensor streaming is ${shouldStart ? `active at ${rateToUse} msgs/sec` : 'idle'}.`,
          timestamp: new Date().toLocaleTimeString(),
        });
      } else {
        setIsSimulatorRunning(shouldStart);
      }
    } catch (e) {
      setIsSimulatorRunning(shouldStart);
    }
  };

  const handleStartBoth = async (targetRate?: number) => {
    await handleTogglePipeline(true);
    await handleToggleSimulator(true, targetRate);
  };

  const handleInjectAnomaly = async () => {
    setIsInjectingAnomaly(true);
    addToast({
      type: 'warning',
      title: 'Injecting Fleet Anomaly',
      message: 'Triggering thermal & compute overload in a randomly selected fleet asset...',
      timestamp: new Date().toLocaleTimeString(),
    });

    try {
      const res = await fetch(`${API_BASE}/api/create-anomoly`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (res.ok) {
        addToast({
          type: 'error',
          title: 'Fleet Anomaly Injected',
          message: 'Critical telemetry emitted to Managed Kafka. Spark C++ Velox streaming ETL will detect the anomaly and update Bigtable.',
          timestamp: new Date().toLocaleTimeString(),
        });
      } else {
        const data = await res.json().catch(() => ({}));
        addToast({
          type: 'error',
          title: 'Anomaly Injection Failed',
          message: data.detail || 'Could not trigger fleet anomaly.',
          timestamp: new Date().toLocaleTimeString(),
        });
      }
    } catch (err) {
      console.error('Error injecting anomaly:', err);
    } finally {
      setIsInjectingAnomaly(false);
    }
  };

  const handleExecuteMitigation = async (assetToMitigate?: AssetState | null) => {
    const target = assetToMitigate || selectedAsset || assets[0];
    if (!target) return;

    // Immediately set selectedAsset so the HUD and Co-Pilot lock onto the target
    setSelectedAsset(target);
    setIsLoadingMitigation(true);

    addToast({
      type: 'info',
      title: 'Invoking Gemini 2.5 Flash Co-Pilot',
      message: `Analyzing root cause and formulating remediation plan for ${target.asset_id}...`,
      timestamp: new Date().toLocaleTimeString(),
    });

    try {
      const res = await fetch(`${API_BASE}/api/agent/recommendation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id: target.asset_id,
          temperature_c: target.temperature_c,
          memory_utilization_pct: target.memory_utilization_pct,
          pressure_psi: target.pressure_psi,
          cpu_utilization: target.cpu_utilization,
        }),
      });

      if (res.ok) {
        const result: MitigationResponse = await res.json();
        setMitigationData(result);
        const preventedUsd = result.tokenomics?.prevented_downtime_usd
          ? `$${result.tokenomics.prevented_downtime_usd.toLocaleString()}`
          : '$5,000';
        addToast({
          type: 'success',
          title: 'Mitigation Plan Formulated',
          message: `Root cause identified for ${target.asset_id}. Autonomous plan ready (${preventedUsd} prevented downtime).`,
          timestamp: new Date().toLocaleTimeString(),
        });
      } else {
        const err = await res.json().catch(() => ({}));
        addToast({
          type: 'error',
          title: 'Agent RCA Error',
          message: err.detail || `Agent service returned status ${res.status}. Please retry.`,
          timestamp: new Date().toLocaleTimeString(),
        });
      }
    } catch (err) {
      console.error('Error invoking agent mitigation:', err);
      addToast({
        type: 'error',
        title: 'Agent Connection Error',
        message: 'Could not connect to the agent service. Please retry.',
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      setIsLoadingMitigation(false);
    }
  };

  const handleApproveAndApply = async (assetId: string): Promise<AgentApprovalResponse | void> => {
    addToast({
      type: 'step',
      stepNumber: 1,
      totalSteps: 6,
      title: 'Approaching Agent Service',
      message: `Dispatching human approval for ${assetId} to Reasoning Engine / Agent Service...`,
      timestamp: new Date().toLocaleTimeString(),
    });

    try {
      const res = await fetch(`${API_BASE}/api/agent/mitigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id: assetId,
          incident_id: mitigationData?.incident_id,
          approved_by: 'Plant Operator (Console)',
        }),
      });

      if (res.ok) {
        const data: AgentApprovalResponse = await res.json();

        setMitigationData((prev) => prev ? { ...prev, status: 'RESOLVED', severity: 'LOW' } : null);

        if (selectedAsset && selectedAsset.asset_id === assetId) {
          setSelectedAsset((prev) => prev ? { ...prev, status: 'OK', is_anomaly: false, cpu_utilization: 35.0, temperature_c: 52.0 } : null);
        }
        setAssets((prev) => prev.map(a => a.asset_id === assetId ? { ...a, status: 'OK', is_anomaly: false, cpu_utilization: 35.0, temperature_c: 52.0 } : a));

        setTimeout(() => {
          addToast({
            type: 'step',
            stepNumber: 2,
            totalSteps: 6,
            title: 'Actuator Tool Invoked',
            message: `Agent activated tool 'IndustrialActuatorTool.throttle_and_cool' via ${data.execution_mode || 'Agent Service'}.`,
            timestamp: new Date().toLocaleTimeString(),
          });
        }, 350);

        setTimeout(() => {
          addToast({
            type: 'step',
            stepNumber: 3,
            totalSteps: 6,
            title: 'Physical Asset Relieved',
            message: `Signal accepted by ${assetId}. Hardware reset to baseline (CPU ~32%, Temp ~50°C, Status OK).`,
            timestamp: new Date().toLocaleTimeString(),
          });
        }, 750);

        setTimeout(() => {
          addToast({
            type: 'step',
            stepNumber: 4,
            totalSteps: 6,
            title: 'Kafka Telemetry Streaming',
            message: `Sensor simulator resumed emitting healthy telemetry payloads to Kafka topic 'telemetry-raw'.`,
            timestamp: new Date().toLocaleTimeString(),
          });
        }, 1150);

        setTimeout(() => {
          addToast({
            type: 'step',
            stepNumber: 5,
            totalSteps: 6,
            title: 'BigQuery Governance Audit',
            message: `Incident audit record & tokenomics logged to BigQuery table 'analytics.rca_events'.`,
            timestamp: new Date().toLocaleTimeString(),
          });
        }, 1550);

        setTimeout(() => {
          addToast({
            type: 'success',
            stepNumber: 6,
            totalSteps: 6,
            title: 'Closed-Loop Remediation Complete',
            message: `Spark Streaming (C++ Velox) dual-sink synchronized to Bigtable and BigQuery.`,
            timestamp: new Date().toLocaleTimeString(),
          });
        }, 1950);

        setTimeout(() => {
          addToast({
            type: 'info',
            title: `Asset ${assetId} Normalization Underway`,
            message: `Operational mitigation directives successfully dispatched to ${assetId}. Real-time telemetry metrics are stabilizing and will reflect nominal operating baselines across the live grid within the next ingestion cycle.`,
            timestamp: new Date().toLocaleTimeString(),
          });
        }, 2500);

        return data;
      }
    } catch (err) {
      console.error('Failed to execute agent mitigation tools:', err);
      addToast({
        type: 'error',
        title: 'Mitigation Failed',
        message: 'Could not complete closed-loop agent execution.',
        timestamp: new Date().toLocaleTimeString(),
      });
    }
  };

  const criticalCount = getActiveAnomalies(assets).length;
  const isFleetStale = checkFleetStale(assets);

  return (
    <HUDContext.Provider
      value={{
        assets,
        isConnected,
        selectedAsset,
        setSelectedAsset: handleSetSelectedAsset,
        mitigationData,
        isLoadingMitigation,
        isInjectingAnomaly,
        isSimulatorRunning,
        pipelineStatus,
        isPipelineActive,
        isDemoActive,
        criticalCount,
        isFleetStale,
        simulatorRate,
        setSimulatorRate,
        toasts,
        addToast,
        removeToast,
        handleTogglePipeline,
        handleToggleSimulator,
        handleStartBoth,
        handleInjectAnomaly,
        handleExecuteMitigation,
        handleApproveAndApply,
      }}
    >
      {children}
      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </HUDContext.Provider>
  );
};

export const useHUD = () => {
  const context = useContext(HUDContext);
  if (!context) {
    throw new Error('useHUD must be used within a HUDProvider');
  }
  return context;
};
