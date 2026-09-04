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
import dynamic from 'next/dynamic';
import { Presentation, Loader2 } from 'lucide-react';

// Dynamically import SlideDeckViewer to ensure strict Client-Side Rendering (avoids DOMMatrix / SSR issues)
const SlideDeckViewer = dynamic(
  () => import('./SlideDeckViewer').then((mod) => mod.SlideDeckViewer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full glass-panel rounded-2xl p-12 border border-[#334155] shadow-2xl flex flex-col items-center justify-center space-y-4 min-h-[500px]">
        <div className="p-3 rounded-2xl bg-[#1a73e8]/20 border border-[#1a73e8]/40 text-[#adc7ff] animate-pulse">
          <Presentation className="w-8 h-8" />
        </div>
        <div className="flex items-center gap-2 text-sm font-mono text-[#adc7ff] uppercase tracking-wider">
          <Loader2 className="w-4 h-4 animate-spin text-[#1a73e8]" />
          <span>Initializing Presentation Deck Canvas...</span>
        </div>
      </div>
    ),
  }
);

interface ExecutiveSlideDeckProps {
  onNavigate?: (tabId: string) => void;
}

export const ExecutiveSlideDeck: React.FC<ExecutiveSlideDeckProps> = ({ onNavigate }) => {
  return (
    <SlideDeckViewer
      pdfUrl="/aegis_autonomous_streaming.pdf"
      title="AEGIS Autonomous Streaming Presentation"
      subtitle="Executive Architecture, C++ Velox Accelerated Compute & Agentic AI Mitigation Deck"
      onNavigate={onNavigate}
    />
  );
};

export default ExecutiveSlideDeck;
