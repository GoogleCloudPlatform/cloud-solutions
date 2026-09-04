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
import { usePathname } from 'next/navigation';
import {
  Presentation,
  Cpu,
  BookOpen,
  Radio,
  Activity,
  BarChart3
} from 'lucide-react';

export interface NavigationItem {
  id: string;
  href: string;
  label: string;
  shortLabel: string;
  icon: React.ReactNode;
}

interface NavigationMenuProps {
  activeTab?: string;
  onSelectTab?: (tabId: string) => void;
}

export const NavigationMenu: React.FC<NavigationMenuProps> = ({
  activeTab: propActiveTab,
  onSelectTab,
}) => {
  const pathname = usePathname();

  const navItems: NavigationItem[] = [
    {
      id: 'slides',
      href: '/slides',
      label: '1. Executive Deck',
      shortLabel: '1. Slides',
      icon: <Presentation className="w-4 h-4" />
    },
    {
      id: 'simulator',
      href: '/simulator',
      label: '2. Stream Simulator',
      shortLabel: '2. Simulator',
      icon: <Radio className="w-4 h-4" />
    },
    {
      id: 'guide',
      href: '/guide',
      label: '3. Demo Guide',
      shortLabel: '3. Demo Guide',
      icon: <BookOpen className="w-4 h-4" />
    },
    {
      id: 'grid',
      href: '/grid',
      label: '4. Live Grid & AI Co-Pilot',
      shortLabel: '4. Grid & Co-Pilot',
      icon: <Activity className="w-4 h-4" />
    },
    {
      id: 'analytics',
      href: '/analytics',
      label: '5. Batch Analytics',
      shortLabel: '5. Analytics',
      icon: <BarChart3 className="w-4 h-4" />
    }
  ];

  // Helper to determine active state
  const isItemActive = (item: NavigationItem) => {
    if (propActiveTab) {
      return propActiveTab === item.id;
    }
    if (item.id === 'slides' && (pathname === '/' || pathname === '/slides')) {
      return true;
    }
    return pathname === item.href || pathname?.startsWith(`${item.href}/`);
  };

  return (
    <nav className="sticky top-0 z-50 w-full bg-[#0b1326]/95 backdrop-blur-md border-b border-[#334155] py-2.5 px-4 md:px-6 shadow-2xl transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-center md:justify-between gap-3 overflow-x-auto no-scrollbar py-1">
        {navItems.map((item) => {
          const active = isItemActive(item);
          return (
            <Link
              key={item.id}
              href={item.href}
              onClick={() => onSelectTab && onSelectTab(item.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl font-mono text-xs transition-all duration-200 whitespace-nowrap border shrink-0 group cursor-pointer ${
                active
                  ? 'bg-[#1a73e8] text-white border-[#adc7ff] shadow-lg shadow-[#1a73e8]/40 font-bold scale-[1.02]'
                  : 'bg-[#131b2e]/80 hover:bg-[#1e293b] text-[#c1c6d6] border-[#334155]/60 hover:border-[#8b909f]/60 hover:text-white font-medium'
              }`}
            >
              <span className={active ? 'text-white' : 'text-[#adc7ff] group-hover:text-white transition-colors'}>
                {item.icon}
              </span>
              <span className="hidden md:inline">{item.label}</span>
              <span className="inline md:hidden">{item.shortLabel}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
};

export default NavigationMenu;
