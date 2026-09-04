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
import {
  CheckCircle2,
  AlertTriangle,
  Info,
  X,
  Bot,
  Wrench,
  Radio,
  Database,
  Zap,
  Activity
} from 'lucide-react';

export interface ToastItem {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'step';
  title: string;
  message: string;
  stepNumber?: number;
  totalSteps?: number;
  timestamp?: string;
}

interface ToastContainerProps {
  toasts: ToastItem[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
  if (!toasts || toasts.length === 0) return null;

  const getIcon = (type: ToastItem['type'], stepNumber?: number) => {
    if (type === 'step') {
      switch (stepNumber) {
        case 1:
          return <Bot className="w-5 h-5 text-[#adc7ff]" />;
        case 2:
          return <Wrench className="w-5 h-5 text-[#FBBC04]" />;
        case 3:
          return <Activity className="w-5 h-5 text-[#6ddd81]" />;
        case 4:
          return <Radio className="w-5 h-5 text-[#adc7ff]" />;
        case 5:
          return <Database className="w-5 h-5 text-[#adc7ff]" />;
        case 6:
          return <Zap className="w-5 h-5 text-[#FBBC04]" />;
        default:
          return <Zap className="w-5 h-5 text-[#adc7ff]" />;
      }
    }
    switch (type) {
      case 'success':
        return <CheckCircle2 className="w-5 h-5 text-[#6ddd81]" />;
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-[#FBBC04]" />;
      case 'error':
        return <AlertTriangle className="w-5 h-5 text-[#D93025]" />;
      case 'info':
      default:
        return <Info className="w-5 h-5 text-[#adc7ff]" />;
    }
  };

  const getBorderAndBg = (type: ToastItem['type']) => {
    switch (type) {
      case 'success':
        return 'border-[#30a550] bg-[#061e12]/95 shadow-[0_0_20px_rgba(48,165,80,0.35)]';
      case 'warning':
        return 'border-[#FBBC04] bg-[#2a1d00]/95 shadow-[0_0_20px_rgba(251,188,4,0.3)]';
      case 'error':
        return 'border-[#D93025] bg-[#2a0808]/95 shadow-[0_0_20px_rgba(217,48,37,0.35)]';
      case 'step':
        return 'border-[#1a73e8] bg-[#0b1938]/95 shadow-[0_0_25px_rgba(26,115,232,0.4)]';
      case 'info':
      default:
        return 'border-[#334155] bg-[#0d1526]/95 shadow-[0_0_20px_rgba(0,0,0,0.5)]';
    }
  };

  return (
    <aside aria-label="Operational Notifications" className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 max-w-md w-full pointer-events-none px-4 md:px-0">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto p-4 rounded-xl border backdrop-blur-md transition-all duration-300 transform translate-y-0 opacity-100 flex items-start gap-3.5 ${getBorderAndBg(
            t.type
          )}`}
        >
          <div className="mt-0.5 shrink-0">{getIcon(t.type, t.stepNumber)}</div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <h4 className="text-xs font-mono font-bold uppercase tracking-wider text-white truncate">
                {t.stepNumber && t.totalSteps
                  ? `[Step ${t.stepNumber}/${t.totalSteps}] ${t.title}`
                  : t.title}
              </h4>
              {t.timestamp && (
                <span className="text-[10px] font-mono text-[#8b909f] shrink-0">
                  {t.timestamp}
                </span>
              )}
            </div>
            <p className="text-xs text-[#dae2fd] font-sans mt-1 leading-snug break-words">
              {t.message}
            </p>
          </div>

          <button
            onClick={() => onDismiss(t.id)}
            className="text-[#8b909f] hover:text-white transition-colors p-1 -mr-1 -mt-1 rounded hover:bg-white/10 shrink-0"
            title="Dismiss"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </aside>
  );
};
