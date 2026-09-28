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
import {
  Database,
  Play,
  RefreshCw,
  Table as TableIcon,
  AlertTriangle,
  Copy,
  Check,
  ExternalLink,
  Terminal,
  Clock
} from 'lucide-react';
import { PageNavigation } from './PageNavigation';
import { getConsoleLinks, getGcpConfig } from '@/utils/gcpConsoleLinks';

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
  rows: Record<string, unknown>[];
  execution_time_ms: number;
  source: string;
}

interface BatchAnalyticsProps {
  onNavigate?: (tabId: string) => void;
}

// Fallback queries for immediate UI rendering while API loads
const getDefaultQueries = (project: string, dataset: string): QueryOption[] => [
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
FROM \`${project}.${dataset}.telemetry_events\`
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
FROM \`${project}.${dataset}.telemetry_events\`
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
FROM \`${project}.${dataset}.rca_events\`
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
      return <span key={i} className="text-emerald-400 font-semibold">{tok}</span>;
    }
    if (/^\d+(?:\.\d+)?$/.test(tok)) {
      return <span key={i} className="text-cyan-400 font-mono">{tok}</span>;
    }
    return <span key={i} className="text-[#e2e8f0]">{tok}</span>;
  });
};

export const BatchAnalytics: React.FC<BatchAnalyticsProps> = ({ onNavigate }) => {
  const gcpConfig = getGcpConfig();
  const defaultQueries = useMemo(
    () =>
      getDefaultQueries(
        gcpConfig.project || 'aegis-streaming-demo-oss-1001',
        gcpConfig.bigqueryDataset || 'analytics'
      ),
    [gcpConfig.project, gcpConfig.bigqueryDataset]
  );

  const [queries, setQueries] = useState<QueryOption[]>(defaultQueries);
  const [selectedQueryId, setSelectedQueryId] = useState<string>('fleet_stress');
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
  const links = getConsoleLinks();

  // Selected query definition
  const activeQuery = useMemo(() => {
    return queries.find((q) => q.query_id === selectedQueryId) || queries[0] || defaultQueries[0];
  }, [queries, selectedQueryId, defaultQueries]);

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
      } catch {
        // Fallback queries already loaded
      }
    };
    fetchQueries();
  }, [API_BASE]);

  const handleSelectQuery = (queryId: string) => {
    if (queryId !== selectedQueryId) {
      setSelectedQueryId(queryId);
      setResult(null);
      setError(null);
    }
  };

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
    } catch {
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
    <section className="w-full glass-panel rounded-2xl p-6 space-y-6 animate-fade-in">
      {/* Section Header Banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-[#1a73e8]/15 border border-[#1a73e8]/30 text-[#68abff]">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg md:text-xl font-headline font-bold text-white uppercase tracking-wide flex items-center gap-2.5">
              <span>Module 5: BigQuery Batch Analytics &amp; Financial Provenance</span>
              <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-widest rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                GoogleSQL
              </span>
            </h2>
            <p className="text-xs md:text-sm text-[#94a3b8] font-sans mt-0.5">
              Execute interactive Google Cloud BigQuery SQL aggregations across partitioned telemetry and Gemini 2.5 Flash audit tables.
            </p>
          </div>
        </div>

        <a
          href={links.bigqueryDataset}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3.5 py-2 rounded-xl bg-[#0b1326] hover:bg-[#1e293b] border border-white/[0.08] hover:border-white/20 text-xs font-mono font-semibold text-[#68abff] hover:text-white flex items-center gap-1.5 transition-all shrink-0"
          title="Open BigQuery Analytics Dataset in Google Cloud Console"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          <span>BigQuery Console ↗</span>
        </a>
      </div>

      {/* 1. Compact 3-Tab Horizontal Query Selector Bar */}
      <div className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2 p-1.5 rounded-xl bg-[#070d19] border border-white/[0.08]">
          {queries.map((q, idx) => {
            const isSelected = selectedQueryId === q.query_id;
            return (
              <button
                key={q.query_id}
                type="button"
                onClick={() => handleSelectQuery(q.query_id)}
                className={`p-3 rounded-lg text-left transition-all cursor-pointer flex flex-col justify-between gap-1 border ${
                  isSelected
                    ? 'bg-[#1a73e8]/20 border-[#68abff]/50 shadow-sm'
                    : 'bg-transparent hover:bg-white/[0.04] border-transparent'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`text-[10px] font-mono uppercase tracking-wider font-bold px-2 py-0.5 rounded ${
                      isSelected
                        ? 'bg-[#1a73e8] text-white'
                        : 'bg-white/[0.05] text-[#94a3b8]'
                    }`}
                  >
                    0{idx + 1} &bull; {q.badge}
                  </span>
                  {isSelected && loading && (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#68abff]" />
                  )}
                </div>
                <div className="text-xs font-headline font-bold text-white line-clamp-1 mt-1">
                  {q.title}
                </div>
              </button>
            );
          })}
        </div>

        {/* Active Query Description Bar */}
        <div className="px-4 py-2.5 rounded-xl bg-[#0b1326]/70 border border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-[#94a3b8]">
          <span>{activeQuery.description}</span>
          <span className="text-[11px] font-mono text-[#64748b] shrink-0">
            Dataset: <code className="text-amber-400">{gcpConfig.bigqueryDataset || 'analytics'}</code>
          </span>
        </div>
      </div>

      {/* 2. Pretty-Printed SQL Query Inspector Section */}
      <div className="rounded-xl bg-[#070d19] border border-white/[0.08] overflow-hidden shadow-xl">
        {/* Clean SQL Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 bg-[#0b1326] border-b border-white/[0.08]">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-[#68abff]" />
            <span className="text-xs font-mono font-bold text-white tracking-wide">
              {activeQuery.title}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Copy SQL Button */}
            <button
              type="button"
              onClick={handleCopySql}
              className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] text-xs font-mono text-[#cbd5e1] hover:text-white flex items-center gap-1.5 transition-all cursor-pointer"
              title="Copy SQL Query to Clipboard"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400 font-bold">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-[#68abff]" />
                  <span>Copy SQL</span>
                </>
              )}
            </button>

            {/* Primary Execute SQL CTA */}
            <button
              type="button"
              disabled={loading}
              onClick={() => runQuery(activeQuery.query_id)}
              className="px-4 py-1.5 rounded-lg bg-[#1a73e8] hover:bg-[#1557b0] disabled:opacity-50 text-white text-xs font-mono font-bold uppercase tracking-wider flex items-center gap-1.5 transition-all shadow-md shadow-[#1a73e8]/25 cursor-pointer"
            >
              {loading ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play className="w-3 h-3 fill-current" />
              )}
              <span>{loading ? 'Running...' : 'Execute SQL'}</span>
            </button>
          </div>
        </div>

        {/* Code Editor Window with Line Numbers and Syntax Highlighting */}
        <div className="p-4 overflow-x-auto font-mono text-xs leading-relaxed bg-[#070d19]">
          <div className="flex min-w-[600px]">
            {/* Line numbers gutter */}
            <div className="select-none pr-4 text-right text-[#475569] font-mono border-r border-white/[0.06] space-y-1 tabular-nums">
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
        <div className="p-5 rounded-xl bg-[#070d19] border border-white/[0.08] space-y-4 animate-fade-in">
          {/* Result Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-white/[0.08]">
            <div className="flex items-center gap-2.5 flex-wrap">
              <TableIcon className="w-4 h-4 text-[#68abff]" />
              <h4 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                Results: <span className="text-[#68abff]">{result.title}</span>
              </h4>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1 font-bold tabular-nums">
                <Clock className="w-3 h-3" /> {result.execution_time_ms} ms
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-[#cbd5e1] border border-white/[0.08] tabular-nums">
                {result.rows.length} rows
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-white/[0.04] text-[#64748b] border border-white/[0.08]">
                Source: {result.source}
              </span>
            </div>
          </div>

          {/* Table View with Tabular Numerals & Inline Bars */}
          <div className="overflow-x-auto rounded-xl border border-white/[0.08]">
            <table className="w-full text-left border-collapse font-mono text-xs tabular-nums">
              <thead>
                <tr className="border-b border-white/[0.08] bg-[#0b1326] text-[#94a3b8] uppercase text-[11px]">
                  {result.columns.map((col) => (
                    <th key={col} className="p-3 font-bold tracking-wider whitespace-nowrap">
                      {col.replace(/_/g, ' ')}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.06] text-[#e2e8f0]">
                {result.rows.length > 0 ? (
                  result.rows.map((row, idx) => (
                    <tr key={idx} className="hover:bg-white/[0.03] transition-colors">
                      {result.columns.map((col) => {
                        const val = row[col];
                        const numVal = Number(val);
                        const isPctOrTemp =
                          !Number.isNaN(numVal) &&
                          (col.includes('pct') ||
                            col.includes('utilization') ||
                            col.includes('temp_c'));

                        if (col === 'status') {
                          const statusBadge =
                            val === 'CRITICAL'
                              ? 'text-rose-300 font-bold bg-rose-500/20 px-2 py-0.5 rounded border border-rose-500/40 inline-block'
                              : val === 'WARNING'
                              ? 'text-amber-300 font-bold bg-amber-500/15 px-2 py-0.5 rounded border border-amber-500/35 inline-block'
                              : 'text-emerald-400 font-bold bg-emerald-500/15 px-2 py-0.5 rounded border border-emerald-500/30 inline-block';
                          return (
                            <td key={col} className="p-3 whitespace-nowrap">
                              <span className={statusBadge}>{String(val)}</span>
                            </td>
                          );
                        }

                        if (isPctOrTemp) {
                          const suffix = col.includes('temp_c') ? '°C' : '%';
                          const maxScale = col.includes('temp_c') ? 120 : 100;
                          const pctWidth = Math.min(100, Math.max(0, (numVal / maxScale) * 100));
                          const barColor =
                            numVal > 85
                              ? 'bg-rose-500'
                              : numVal > 75
                              ? 'bg-amber-400'
                              : 'bg-[#1a73e8]';
                          return (
                            <td key={col} className="p-3 whitespace-nowrap">
                              <div className="flex items-center gap-2.5">
                                <span
                                  className={`w-14 font-bold ${
                                    numVal > 85 ? 'text-rose-300' : 'text-[#e2e8f0]'
                                  }`}
                                >
                                  {numVal.toFixed(1)}
                                  {suffix}
                                </span>
                                <div className="w-16 h-1.5 bg-white/[0.06] rounded-full overflow-hidden hidden sm:block">
                                  <div
                                    className={`h-full rounded-full ${barColor}`}
                                    style={{ width: `${pctWidth}%` }}
                                  />
                                </div>
                              </div>
                            </td>
                          );
                        }

                        let displayVal = val !== null && val !== undefined ? String(val) : '-';
                        let cellClass = '';

                        if (col === 'roi_multiplier') {
                          cellClass = 'text-emerald-400 font-bold';
                          displayVal = `${Number(val).toLocaleString()}x`;
                        } else if (col === 'total_gemini_cost_usd' || col === 'cost_usd') {
                          cellClass = 'text-cyan-400';
                          displayVal = `$${Number(val).toFixed(6)}`;
                        } else if (col === 'total_downtime_saved_usd') {
                          cellClass = 'text-emerald-400 font-bold';
                          displayVal = `$${Number(val).toLocaleString()}`;
                        } else if (col === 'asset_id') {
                          cellClass = 'font-bold text-white';
                        }

                        return (
                          <td key={col} className={`p-3 whitespace-nowrap ${cellClass}`}>
                            {displayVal}
                          </td>
                        );
                      })}
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      colSpan={result.columns.length}
                      className="p-8 text-center text-[#64748b] italic"
                    >
                      No matching records found in BigQuery table.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        !loading && (
          <div className="p-8 rounded-xl bg-[#070d19]/60 border border-dashed border-white/[0.1] text-center flex flex-col items-center justify-center gap-1.5">
            <Database className="w-7 h-7 text-[#68abff]/70" />
            <p className="text-xs font-mono font-bold text-white uppercase tracking-wider">
              Interactive BigQuery Analytics Ready
            </p>
            <p className="text-xs text-[#94a3b8] max-w-md font-sans">
              Select a query template tab above and click{' '}
              <span className="font-mono text-[#68abff] font-bold">Execute SQL</span> to query
              Google Cloud BigQuery in real time.
            </p>
          </div>
        )
      )}

      {error && (
        <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs font-mono flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
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
