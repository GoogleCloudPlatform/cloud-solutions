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

import React from 'react';
import Link from 'next/link';
import { ShieldAlert } from 'lucide-react';

interface HeaderProps {
  onNavigateHome?: () => void;
}

export const Header: React.FC<HeaderProps> = () => {
  return (
    <header className="w-full glass-panel border-b border-[#334155] sticky top-0 z-50 px-6 py-4">
      <div className="max-w-[1600px] mx-auto flex items-center justify-between gap-4">
        {/* Brand & Project Identity - Clickable Link to Home / Slides */}
        <Link
          href="/slides"
          className="flex items-center gap-3 text-left group hover:opacity-95 transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-[#adc7ff] rounded-xl p-1 -m-1"
          title="Return to Presentation Deck"
        >
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[#1a73e8] to-[#005bc0] shadow-lg shadow-[#1a73e8]/30 border border-[#adc7ff]/30 group-hover:scale-105 transition-transform">
            <ShieldAlert className="w-6 h-6 text-white" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#adc7ff] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-[#adc7ff]"></span>
            </span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-headline font-bold tracking-tight text-white group-hover:text-[#adc7ff] transition-colors">
                PROJECT AEGIS
              </h1>
              <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase tracking-widest rounded bg-[#131b2e] text-[#adc7ff] border border-[#334155]">
                v1.0.0 HUD
              </span>
            </div>
            <p className="text-xs text-[#c1c6d6] font-sans">
              Autonomous Real-Time Streaming Telemetry &amp; Threat Mitigation Co-Pilot
            </p>
          </div>
        </Link>
      </div>
    </header>
  );
};

export default Header;
