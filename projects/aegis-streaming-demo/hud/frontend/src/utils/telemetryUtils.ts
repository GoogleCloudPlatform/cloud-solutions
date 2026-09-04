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

/**
 * Project Aegis - Telemetry & Staleness Utilities
 *
 * Provides centralized UTC timestamp analysis, staleness thresholds (>60m),
 * and timezone-independent relative time formatting across the Operations HUD.
 */

import {AssetState} from '../types';

export const STALE_THRESHOLD_MINUTES = 60;
export const STALE_THRESHOLD_MS = STALE_THRESHOLD_MINUTES * 60 * 1000; // 60 minutes in milliseconds

/**
 * Robustly parses a timestamp string into a Date object strictly in UTC,
 * independent of the browser's local timezone (e.g., UTC+2, UTC-4, etc.).
 *
 * Handles:
 * - ISO with Z: "2026-08-17T14:28:00Z"
 * - ISO with offset: "2026-08-17T14:28:00+00:00"
 * - Spark / SQL timestamp format with space: "2026-08-17 14:28:00" -> treated as UTC
 * - ISO without zone: "2026-08-17T14:28:00.123456" -> treated as UTC
 */
export function parseUtcDate(isoString?: string | null): Date | null {
  if (!isoString) return null;
  try {
    let s = String(isoString).trim();
    if (!s) return null;

    // Convert SQL space separator to ISO 'T'
    s = s.replace(' ', 'T');

    // If string has no timezone offset (no 'Z' and no '+/-HH:MM'), force UTC
    const hasTimezone = s.endsWith('Z') || /[+-]\d{2}(:\d{2})?$/.test(s);
    if (!hasTimezone) {
      s += 'Z';
    }

    const d = new Date(s);
    if (isNaN(d.getTime())) return null;
    return d;
  } catch {
    return null;
  }
}

/**
 * Determines whether an asset's telemetry timestamp is considered stale (>60m old or invalid).
 * Guaranteed timezone-independent.
 */
export function isDataStale(isoString?: string | null): boolean {
  const parsedDate = parseUtcDate(isoString);
  if (!parsedDate) return true;
  const diffMs = Date.now() - parsedDate.getTime();
  return diffMs > STALE_THRESHOLD_MS;
}

export interface DataAgeInfo {
  isStale: boolean;
  ageSeconds: number;
  ageMinutes: number;
  relativeText: string;
  badgeLabel: string;
  staleMessage: string;
}

/**
 * Returns comprehensive age and staleness metadata for any timestamp,
 * aligned strictly to UTC regardless of the user's geographic location.
 */
export function getDataAgeInfo(isoString?: string | null): DataAgeInfo {
  const parsedDate = parseUtcDate(isoString);
  if (!parsedDate) {
    return {
      isStale: true,
      ageSeconds: Infinity,
      ageMinutes: Infinity,
      relativeText: 'no timestamp',
      badgeLabel: 'DATA TOO OLD',
      staleMessage:
        'Data too old. Activate the demo and wait for new data to come in.',
    };
  }

  // Date.now() is UTC epoch ms, parsedDate.getTime() is UTC epoch ms
  const diffMs = Math.max(0, Date.now() - parsedDate.getTime());
  const ageSeconds = Math.floor(diffMs / 1000);
  const ageMinutes = Math.floor(ageSeconds / 60);
  const isStale = diffMs > STALE_THRESHOLD_MS;

  let relativeText = 'just now';
  if (ageSeconds < 3) {
    relativeText = 'just now';
  } else if (ageSeconds < 60) {
    relativeText = `${ageSeconds}s ago`;
  } else if (ageMinutes < 60) {
    relativeText = `${ageMinutes}m ago`;
  } else {
    const ageHours = Math.floor(ageMinutes / 60);
    const remMinutes = ageMinutes % 60;
    if (ageHours < 24) {
      relativeText = `${ageHours}h${remMinutes > 0 ? ` ${remMinutes}m` : ''} ago`;
    } else {
      const ageDays = Math.floor(ageHours / 24);
      relativeText = `${ageDays}d ago`;
    }
  }

  return {
    isStale,
    ageSeconds,
    ageMinutes,
    relativeText: `last update ${relativeText}`,
    badgeLabel: isStale ? 'DATA TOO OLD' : 'LIVE',
    staleMessage:
      'Data too old, activate the demo and wait for new data to come in.',
  };
}

/**
 * Returns true if all assets in the fleet have stale data (>60m old).
 */
export function isFleetStale(assets: AssetState[]): boolean {
  if (!assets || assets.length === 0) return true;
  return assets.every(a => isDataStale(a.timestamp));
}

/**
 * Filters and returns active, non-stale anomalies in the asset fleet.
 */
export function getActiveAnomalies(assets: AssetState[]): AssetState[] {
  if (!assets) return [];
  return assets.filter(a => {
    if (isDataStale(a.timestamp)) return false;
    return (
      a.cpu_utilization > 90.0 ||
      a.temperature_c > 90.0 ||
      a.status === 'CRITICAL' ||
      a.is_anomaly === true
    );
  });
}
