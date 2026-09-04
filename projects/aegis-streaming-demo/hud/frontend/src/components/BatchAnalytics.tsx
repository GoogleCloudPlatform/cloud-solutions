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

import React, { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import {
  Database,
  Play,
  RefreshCw,
  Table as TableIcon,
  Code,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Check,
  ExternalLink,
  Sparkles,
  Terminal,
  Clock,
  Layers,
  ArrowRight
} from 'lucide-react';
import { PageNavigation } from './PageNavigation';
import { getConsoleLinks } from '@/utils/gcpConsoleLinks';

interface QueryOption {
  query_id: string;
  title: string;
  badge: string;
  description: string;
  sql: string;
  columns: string[];
}

interface QueryResult {
  query_id: string;
  title: string;
  badge: string;
  sql: string;
  columns: string[];
  rows: Record<string, any>[];
  execution_time_ms: number;
  source: string;
}

interface BatchAnalyticsProps {
  onNavigate?: (tabId: string) => void;
}

// Fallback queries for immediate UI rendering while API loads
const DEFAULT_QUERIES: QueryOption[] = [
  {
    query_id: 'fleet_stress',
    title: 'Fleet-Wide Thermal & Compute Stress Summary',
    badge: 'Real-Time Aggregations',
    description: 'Aggregates 10-second tumbling window metrics across all 15 industrial assets to identify chronic thermal drift and compute saturation.',
    sql: `SELECT
  asset_id,
  COUNT(*) as total_readings,
  ROUND(AVG(cpu_utilization), 2) as avg_cpu_pct,
  ROUND(MAX(cpu_utilization), 2) as max_cpu_pct,
  ROUND(AVG(temperature_c), 2) as avg_temp_c,
  ROUND(MAX(temperature_c), 2) as max_temp_c,
  COUNTIF(status = 'CRITICAL' OR cpu_utilization > 85.0 OR temperature_c > 85.0) as critical_events
FROM \`aegis-streaming-1001.analytics.telemetry_events\`
GROUP BY asset_id
ORDER BY critical_events DESC, max_temp_c DESC
LIMIT 10`,
    columns: ['asset_id', 'total_readings', 'avg_cpu_pct', 'max_cpu_pct', 'avg_temp_c', 'max_temp_c', 'critical_events']
  },
  {
    query_id: 'thermal_spikes',
    title: 'High-Severity Thermal Spikes & Anomaly Windows',
    badge: 'Anomaly Detection',
    description: 'Filters historical stream ingestion for severe thermal events exceeding hardware safety thresholds (Temp > 80°C or CPU > 85%).',
    sql: `SELECT
  asset_id,
  TIMESTAMP_TRUNC(timestamp, MINUTE) as window_minute,
  ROUND(MAX(temperature_c), 2) as peak_temp_c,
  ROUND(MAX(cpu_utilization), 2) as peak_cpu_pct,
  ANY_VALUE(status) as status
FROM \`aegis-streaming-1001.analytics.telemetry_events\`
WHERE temperature_c > 80.0 OR cpu_utilization > 85.0
GROUP BY asset_id, window_minute
ORDER BY peak_temp_c DESC
LIMIT 15`,
    columns: ['asset_id', 'window_minute', 'peak_temp_c', 'peak_cpu_pct', 'status']
  },
  {
    query_id: 'mitigation_roi',
    title: 'AI Co-Pilot Mitigation ROI & Token Accounting',
    badge: 'Financial Provenance',
    description: 'Audits Gemini Enterprise Agent Platform (GEAP) reasoning token consumption versus prevented industrial machinery downtime value.',
    sql: `SELECT
  asset_id,
  COUNT(*) as mitigation_events,
  SUM(tokens_used) as total_tokens_consumed,
  ROUND(SUM(cost_usd), 6) as total_gemini_cost_usd,
  ROUND(SUM(5000.0), 2) as total_downtime_saved_usd,
  ROUND(SUM(5000.0) / NULLIF(SUM(cost_usd), 0), 1) as roi_multiplier
FROM \`aegis-streaming-1001.analytics.rca_events\`
GROUP BY asset_id
ORDER BY total_downtime_saved_usd DESC
LIMIT 10`,
    columns: ['asset_id', 'mitigation_events', 'total_tokens_consumed', 'total_gemini_cost_usd', 'total_downtime_saved_usd', 'roi_multiplier']
  }
];

// Syntax tokenizer for BigQuery Standard SQL
const highlightSqlLine = (line: string) => {
  const KEYWORDS = new Set([
    'SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'ORDER', 'LIMIT', 'AS', 'AND', 'OR', 'DESC', 'ASC',
    'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'ON', 'HAVING', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'DISTINCT', 'OVER', 'PARTITION', 'WINDOW', 'IN', 'NOT', 'NULL', 'IS', 'LIKE', 'BETWEEN'
  ]);
  const FUNCTIONS = new Set([
    'COUNT', 'COUNTIF', 'AVG', 'MAX', 'MIN', 'SUM', 'ROUND', 'TIMESTAMP_TRUNC', 'NULLIF',
    'ANY_VALUE', 'COALESCE', 'CONCAT', 'CAST', 'DATE_SUB', 'CURRENT_TIMESTAMP', 'IF', 'MINUTE', 'HOUR', 'DAY'
  ]);

  const tokenRegex = /(`[^`]+`|'[^']*'|--[^\n]*|\b[A-Za-z_][A-Za-z0-9_]*\b|\d+(?:\.\d+)?|[(),*+\-/=><!]+|\s+)/g;
  const tokens = line.match(tokenRegex) || [line];

  return tokens.map((tok, i) => {
    const upper = tok.toUpperCase();
    if (tok.startsWith('--')) {
      return <span key={i} className="text-[#8b909f] italic">{tok}</span>;
    }
    if (tok.startsWith('`') && tok.endsWith('`')) {
      return <span key={i} className="text-[#FBBC04] font-semibold">{tok}</span>;
    }
    if (tok.startsWith("'") && tok.endsWith("'")) {
      return <span key={i} className="text-[#ffb691]">{tok}</span>;
    }
    if (KEYWORDS.has(upper)) {
      return <span key={i} className="text-[#adc7ff] font-bold">{tok}</span>;
    }
    if (FUNCTIONS.has(upper)) {
      return <span key={i} className="text-[#6ddd81] font-semibold">{tok}</span>;
    }
    if (/^\d+(?:\.\d+)?$/.test(tok)) {
      return <span key={i} className="text-[#a855f7] font-mono">{tok}</span>;
    }
    return <span key={i} className="text-[#dae2fd]">{tok}</span>;
  });
};

export const BatchAnalytics: React.FC<BatchAnalyticsProps> = ({ onNavigate }) => {
  const [queries, setQueries] = useState<QueryOption[]>(DEFAULT_QUERIES);
  const [selectedQueryId, setSelectedQueryId] = useState<string>('fleet_stress');
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
  const links = getConsoleLinks();

  // Selected query definition
  const activeQuery = useMemo(() => {
    return queries.find((q) => q.query_id === selectedQueryId) || queries[0] || DEFAULT_QUERIES[0];
  }, [queries, selectedQueryId]);

  useEffect(() => {
    const fetchQueries = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/analytics/queries`);
        if (res.ok) {
          const data = await res.json();
          if (data.queries && data.queries.length > 0) {
            setQueries(data.queries);
          }
        }
      } catch (e) {
        // Fallback queries already loaded
      }
    };
    fetchQueries();
  }, [API_BASE]);

  // Select query template WITHOUT automatically running it
  const handleSelectQuery = (queryId: string) => {
    if (queryId !== selectedQueryId) {
      setSelectedQueryId(queryId);
      setResult(null); // Clear previous result so it does not falsely represent the new query
      setError(null);
    }
  };

  // Only run query upon explicit user action (button click)
  const runQuery = async (queryId: string) => {
    setSelectedQueryId(queryId);
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/analytics/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query_id: queryId }),
      });
      if (res.ok) {
        const data: QueryResult = await res.json();
        setResult(data);
      } else {
        setError('Failed to run analytics query.');
      }
    } catch (e) {
      setError('Network error running BigQuery analytics.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopySql = () => {
    if (!activeQuery?.sql) return;
    navigator.clipboard.writeText(activeQuery.sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section className="w-full glass-panel rounded-2xl p-6 md:p-8 border border-[#334155] shadow-2xl space-y-8 animate-fade-in">
      {/* Section Header Banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-6 border-b border-[#334155]">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-[#1a73e8]/20 border border-[#1a73e8]/40 text-[#adc7ff]">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg md:text-xl font-headline font-bold text-white uppercase tracking-wide flex items-center gap-2">
                Module 5: BigQuery Batch Analytics &amp; Financial Provenance
                <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-widest rounded bg-[#131b2e] text-[#6ddd81] border border-[#334155]">
                  GoogleSQL
                </span>
              </h2>
              <p className="text-xs md:text-sm text-[#c1c6d6] font-sans mt-0.5">
                Execute interactive Google Cloud BigQuery SQL aggregations across streaming telemetry and Gemini 2.5 Flash agent audit tables.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <a
            href={links.bigqueryDataset}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3.5 py-1.5 rounded-lg bg-[#131b2e] hover:bg-[#1e293b] border border-[#334155] hover:border-[#adc7ff] text-xs font-mono font-semibold text-[#adc7ff] hover:text-white flex items-center gap-1.5 transition-all shadow-sm"
            title="Open BigQuery Analytics Dataset in Google Cloud Console"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>BigQuery Console ↗</span>
          </a>
        </div>
      </div>

      {/* 1. Query Selector Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-mono font-bold uppercase tracking-widest text-[#8b909f] flex items-center gap-2">
            <Layers className="w-4 h-4 text-[#adc7ff]" />
            <span>Select BigQuery Analytics Template</span>
          </h3>
          <span className="text-[11px] font-mono text-[#8b909f]">
            Click card to preview SQL &bull; Click RUN to execute
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {queries.map((q) => {
            const isSelected = selectedQueryId === q.query_id;
            return (
              <div
                key={q.query_id}
                onClick={() => handleSelectQuery(q.query_id)}
                className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between group ${
                  isSelected
                    ? 'bg-[#1a73e8]/15 border-[#adc7ff] shadow-[0_0_20px_rgba(26,115,232,0.25)] ring-1 ring-[#adc7ff]/50'
                    : 'bg-[#131b2e]/80 border-[#2d3449] hover:border-[#60a5fa] hover:bg-[#171f33]'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <span className={`text-[11px] font-mono px-2 py-0.5 rounded font-bold border ${
                      isSelected
                        ? 'bg-[#1a73e8] text-white border-[#adc7ff]'
                        : 'bg-[#2d3449] text-[#adc7ff] border-[#334155]'
                    }`}>
                      {q.badge}
                    </span>
                    {isSelected && loading && (
                      <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#adc7ff]" />
                    )}
                  </div>
                  <h4 className="text-sm font-mono font-bold text-white mb-1.5 line-clamp-1 group-hover:text-[#adc7ff] transition-colors">
                    {q.title}
                  </h4>
                  <p className="text-xs text-[#c1c6d6] font-sans line-clamp-2 mb-4">
                    {q.description}
                  </p>
                </div>

                <button
                  disabled={loading}
                  onClick={(e) => {
                    e.stopPropagation();
                    runQuery(q.query_id);
                  }}
                  className={`w-full py-2 rounded-lg font-mono text-xs uppercase font-bold flex items-center justify-center gap-1.5 transition-all shadow-md ${
                    isSelected
                      ? 'bg-[#1a73e8] hover:bg-[#005bc0] text-white shadow-[#1a73e8]/30'
                      : 'bg-[#2d3449] hover:bg-[#334155] text-[#dae2fd]'
                  }`}
                >
                  {loading && isSelected ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>EXECUTING SQL...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3 h-3 fill-current" />
                      <span>RUN QUERY</span>
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. Pretty-Printed SQL Query Inspector Section */}
      <div className="rounded-2xl bg-[#060e20] border border-[#334155] overflow-hidden shadow-2xl">
        {/* Terminal Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-[#131b2e]/90 border-b border-[#334155]">
          <div className="flex items-center gap-3">
            {/* macOS-style window dots */}
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-[#ff5f56]/80 border border-[#e0443e]" />
              <span className="w-3 h-3 rounded-full bg-[#ffbd2e]/80 border border-[#dea123]" />
              <span className="w-3 h-3 rounded-full bg-[#27c93f]/80 border border-[#1aab29]" />
            </div>

            <div className="h-4 w-px bg-[#334155]" />

            <div className="flex items-center gap-2">
              <Terminal className="w-4 h-4 text-[#adc7ff]" />
              <span className="text-xs font-mono font-bold text-white tracking-wide">
                BigQuery Standard SQL: <span className="text-[#adc7ff]">{activeQuery.title}</span>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Target Dataset Pill */}
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-[#171f33] text-[#FBBC04] border border-[#334155]">
              Target: <code className="font-bold">analytics</code>
            </span>

            {/* Copy SQL Button */}
            <button
              type="button"
              onClick={handleCopySql}
              className="px-3 py-1.5 rounded-lg bg-[#171f33] hover:bg-[#222a3d] border border-[#334155] hover:border-[#adc7ff] text-xs font-mono text-[#dae2fd] hover:text-white flex items-center gap-1.5 transition-all shadow-sm"
              title="Copy SQL Query to Clipboard"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-[#6ddd81]" />
                  <span className="text-[#6ddd81] font-bold">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-[#adc7ff]" />
                  <span>Copy SQL</span>
                </>
              )}
            </button>

            {/* Run Query Direct Button */}
            <button
              type="button"
              disabled={loading}
              onClick={() => runQuery(activeQuery.query_id)}
              className="px-3.5 py-1.5 rounded-lg bg-[#1a73e8] hover:bg-[#005bc0] disabled:opacity-50 text-white text-xs font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all shadow-md shadow-[#1a73e8]/30"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3 h-3 fill-current" />}
              <span>{loading ? 'Running...' : 'Execute SQL'}</span>
            </button>
          </div>
        </div>

        {/* Code Editor Window with Line Numbers and Syntax Highlighting */}
        <div className="p-4 overflow-x-auto font-mono text-xs leading-relaxed bg-[#060e20]">
          <div className="flex min-w-[600px]">
            {/* Line numbers gutter */}
            <div className="select-none pr-4 text-right text-[#414754] font-mono border-r border-[#334155]/50 space-y-1">
              {activeQuery.sql.split('\n').map((_, idx) => (
                <div key={`ln-${idx}`} className="text-[11px] leading-5">
                  {idx + 1}
                </div>
              ))}
            </div>

            {/* Highlighted SQL Body */}
            <div className="pl-4 select-text space-y-1 font-mono">
              {activeQuery.sql.split('\n').map((line, idx) => (
                <div key={`code-${idx}`} className="text-[12px] leading-5 whitespace-pre font-mono">
                  {highlightSqlLine(line)}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Query Results Table */}
      {result ? (
        <div className="p-5 rounded-2xl bg-[#060e20] border border-[#334155] space-y-4 shadow-xl animate-fade-in">
          {/* Result Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-4 pb-3 border-b border-[#334155]/60">
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <TableIcon className="w-4 h-4 text-[#60a5fa]" />
                <h4 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
                  Query Results: <span className="text-[#adc7ff]">{result.title}</span>
                </h4>
              </div>
              <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-[#30a550]/20 text-[#6ddd81] border border-[#30a550] flex items-center gap-1 font-bold">
                <Clock className="w-3 h-3" /> {result.execution_time_ms} ms
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#2d3449] text-[#c1c6d6] border border-[#334155]">
                {result.rows.length} rows returned
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#131b2e] text-[#8b909f] border border-[#334155]">
                Source: {result.source}
              </span>
            </div>
          </div>

          {/* Table View */}
          <div className="overflow-x-auto rounded-xl border border-[#334155]/60">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-[#334155] bg-[#131b2e]/90 text-[#adc7ff] uppercase">
                  {result.columns.map((col) => (
                    <th key={col} className="p-3 font-bold tracking-wider whitespace-nowrap">
                      {col.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e293b] text-[#dae2fd]">
                {result.rows.length > 0 ? (
                  result.rows.map((row, idx) => (
                    <tr key={idx} className="hover:bg-[#131b2e]/60 transition-colors">
                      {result.columns.map((col) => {
                        const val = row[col];
                        let displayVal = val !== null && val !== undefined ? String(val) : '-';
                        let badgeClass = '';

                        if (col === 'status') {
                          badgeClass = val === 'CRITICAL'
                            ? 'text-[#ff6b60] font-bold bg-[#D93025]/20 px-2 py-0.5 rounded border border-[#D93025]/40 inline-block'
                            : val === 'WARNING'
                            ? 'text-[#FBBC04] font-bold bg-[#FBBC04]/20 px-2 py-0.5 rounded border border-[#FBBC04]/40 inline-block'
                            : 'text-[#6ddd81] font-bold bg-[#6ddd81]/20 px-2 py-0.5 rounded border border-[#6ddd81]/40 inline-block';
                        } else if (col === 'roi_multiplier') {
                          badgeClass = 'text-[#6ddd81] font-bold';
                          displayVal = `${Number(val).toLocaleString()}x`;
                        } else if (col === 'total_gemini_cost_usd' || col === 'cost_usd') {
                          displayVal = `$${Number(val).toFixed(6)}`;
                        } else if (col === 'total_downtime_saved_usd') {
                          badgeClass = 'text-[#6ddd81] font-bold';
                          displayVal = `$${Number(val).toLocaleString()}`;
                        } else if (col.includes('pct') || col.includes('utilization')) {
                          displayVal = `${val}%`;
                        } else if (col.includes('temp_c')) {
                          displayVal = `${val}°C`;
                        }

                        return (
                          <td key={col} className={`p-3 whitespace-nowrap ${badgeClass}`}>
                            {displayVal}
                          </td>
                        );
                      })}
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={result.columns.length} className="p-8 text-center text-[#8b909f] italic">
                      No matching records found in BigQuery table.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : !loading && (
        <div className="p-8 rounded-2xl bg-[#131b2e]/40 border border-dashed border-[#334155] text-center flex flex-col items-center justify-center gap-2">
          <Database className="w-8 h-8 text-[#8b909f] opacity-60" />
          <p className="text-sm font-mono font-bold text-[#dae2fd]">
            Interactive BigQuery Analytics Ready
          </p>
          <p className="text-xs text-[#8b909f] max-w-lg font-sans">
            Review the GoogleSQL query above and click <span className="font-mono text-[#adc7ff] font-bold">RUN QUERY</span> or <span className="font-mono text-[#adc7ff] font-bold">EXECUTE SQL</span> to run live aggregations against Google Cloud BigQuery.
          </p>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-[#D93025]/15 border border-[#D93025] text-[#ff6b60] text-xs font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Step Navigation to Previous/Next Module */}
      <PageNavigation
        prevTab={{ id: 'grid', label: '4. Live Grid & AI Co-Pilot' }}
        nextTab={{ id: 'slides', label: '1. Executive Deck' }}
        onNavigate={onNavigate}
      />
    </section>
  );
};

export default BatchAnalytics;
