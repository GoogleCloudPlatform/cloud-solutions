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
import { ArrowLeft, ArrowRight } from 'lucide-react';

interface TabLink {
  id: string;
  label: string;
}

interface PageNavigationProps {
  prevTab?: TabLink;
  nextTab?: TabLink;
  onNavigate?: (tabId: string) => void;
}

export const PageNavigation: React.FC<PageNavigationProps> = ({
  prevTab,
  nextTab,
  onNavigate,
}) => {
  if (!prevTab && !nextTab) return null;

  const getHref = (tab: TabLink) => {
    return tab.id.startsWith('/') ? tab.id : `/${tab.id}`;
  };

  return (
    <div className="pt-6 mt-6 border-t border-[#334155]/60 flex items-center justify-between gap-4">
      {prevTab ? (
        <Link
          href={getHref(prevTab)}
          onClick={() => onNavigate && onNavigate(prevTab.id)}
          className="px-4 py-2.5 rounded-xl bg-[#131b2e] hover:bg-[#1e293b] text-[#dae2fd] hover:text-white border border-[#334155] hover:border-[#adc7ff] font-mono text-xs uppercase tracking-wider font-bold transition-all shadow-md flex items-center gap-2 group cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4 text-[#adc7ff] group-hover:-translate-x-0.5 transition-transform" />
          <span>Previous: {prevTab.label}</span>
        </Link>
      ) : (
        <div />
      )}

      {nextTab && (
        <Link
          href={getHref(nextTab)}
          onClick={() => onNavigate && onNavigate(nextTab.id)}
          className="ml-auto px-5 py-2.5 rounded-xl bg-[#1a73e8] hover:bg-[#005bc0] text-white border border-[#adc7ff]/40 font-mono text-xs uppercase tracking-wider font-bold transition-all shadow-lg shadow-[#1a73e8]/30 flex items-center gap-2 group cursor-pointer"
        >
          <span>Next: {nextTab.label}</span>
          <ArrowRight className="w-4 h-4 text-white group-hover:translate-x-0.5 transition-transform" />
        </Link>
      )}
    </div>
  );
};

export default PageNavigation;
