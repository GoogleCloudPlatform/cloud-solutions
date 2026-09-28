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

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ShieldAlert, ArrowRight } from 'lucide-react';
import { getStackConfig, StackConfig } from '@/utils/stackConfig';
import { getGcpConfig } from '@/utils/gcpConsoleLinks';

interface HeaderProps {
  onNavigateHome?: () => void;
}

const THEME_STYLES: Record<
  StackConfig['stackTheme'],
  {
    container: string;
    dotPing: string;
    dotSolid: string;
    dotRing: string;
    prefix: string;
    chip: string;
  }
> = {
  emerald: {
    container:
      'border-emerald-500/35 bg-[#0b1326]/90 shadow-[0_0_24px_-8px_rgba(16,185,129,0.3)]',
    dotPing: 'bg-emerald-400',
    dotSolid: 'bg-emerald-400',
    dotRing: 'bg-emerald-500/15 border-emerald-400/40',
    prefix: 'text-emerald-400',
    chip: 'bg-emerald-950/50 text-emerald-200 border-emerald-500/25',
  },
  blue: {
    container:
      'border-[#1a73e8]/45 bg-[#0b1326]/90 shadow-[0_0_24px_-8px_rgba(26,115,232,0.35)]',
    dotPing: 'bg-cyan-400',
    dotSolid: 'bg-cyan-400',
    dotRing: 'bg-cyan-500/15 border-cyan-400/40',
    prefix: 'text-[#68abff]',
    chip: 'bg-[#132342]/70 text-[#dae2fd] border-white/10',
  },
  purple: {
    container:
      'border-cyan-500/35 bg-[#0b1326]/90 shadow-[0_0_24px_-8px_rgba(34,211,238,0.3)]',
    dotPing: 'bg-cyan-400',
    dotSolid: 'bg-cyan-400',
    dotRing: 'bg-cyan-500/15 border-cyan-400/40',
    prefix: 'text-cyan-400',
    chip: 'bg-cyan-950/50 text-cyan-200 border-cyan-500/25',
  },
};

export const Header: React.FC<HeaderProps> = () => {
  const [stackCfg, setStackCfg] = useState<StackConfig>(() => getStackConfig());
  const [gcpProject, setGcpProject] = useState<string>(
    () => getGcpConfig().project
  );

  useEffect(() => {
    setStackCfg(getStackConfig());
    setGcpProject(getGcpConfig().project);
  }, []);

  const theme = THEME_STYLES[stackCfg.stackTheme] || THEME_STYLES.blue;

  return (
    <header className="w-full bg-[#070d19]/90 backdrop-blur-md border-b border-white/[0.08] relative z-40 px-6 py-3">
      <div className="max-w-[1600px] mx-auto flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        {/* Brand & Project Identity - Clickable Link to Home / Slides */}
        <Link
          href="/slides"
          className="flex items-center gap-3 text-left group hover:opacity-95 transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#adc7ff] rounded-xl p-1 -m-1 shrink-0"
          title="Return to Presentation Deck"
        >
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[#1a73e8] to-[#005bc0] shadow-lg shadow-[#1a73e8]/25 border border-[#adc7ff]/30 group-hover:scale-105 transition-transform">
            <ShieldAlert className="w-5 h-5 text-white" />
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#adc7ff] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#adc7ff]"></span>
            </span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-headline font-bold tracking-tight text-white group-hover:text-[#adc7ff] transition-colors">
                PROJECT AEGIS
              </h1>
              <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-widest rounded-md bg-white/[0.04] text-[#adc7ff] border border-white/[0.08]">
                v1.0.0 HUD
              </span>
            </div>
            <p className="text-xs text-[#94a3b8] font-sans">
              Autonomous Real-Time Streaming Telemetry &amp; Threat Mitigation
              Co-Pilot
            </p>
          </div>
        </Link>

        {/* Persistent Deployed Stack Architecture Indicator */}
        <div className="flex items-center self-start lg:self-auto">
          <div
            className={`flex items-center gap-3.5 px-3.5 py-2 rounded-xl border backdrop-blur-md transition-all ${theme.container}`}
          >
            {/* Pulsing Status Orb */}
            <div
              className={`relative flex items-center justify-center w-6 h-6 rounded-full border shrink-0 ${theme.dotRing}`}
            >
              <span
                className={`animate-ping absolute inline-flex h-2.5 w-2.5 rounded-full opacity-75 ${theme.dotPing}`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${theme.dotSolid}`}
              />
            </div>

            {/* Stack Title & Tech Pipeline Chips */}
            <div className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-mono font-bold tracking-wider uppercase text-white">
                  <span className={theme.prefix}>ACTIVE STACK:</span>{' '}
                  {stackCfg.stackBadgeTitle}
                </span>
                {gcpProject && (
                  <span className="px-2 py-0.5 rounded bg-black/40 border border-white/[0.08] text-[10px] font-mono text-[#94a3b8]">
                    Project: <span className="text-[#e2e8f0]">{gcpProject}</span>
                  </span>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-1.5">
                {stackCfg.stackTechFlow.map((tech, idx) => (
                  <React.Fragment key={tech}>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-medium border ${theme.chip}`}
                    >
                      {tech}
                    </span>
                    {idx < stackCfg.stackTechFlow.length - 1 && (
                      <ArrowRight className="w-3 h-3 text-[#64748b] shrink-0" />
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
