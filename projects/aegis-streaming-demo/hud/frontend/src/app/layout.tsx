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

import React from 'react';
import { Hanken_Grotesk, Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { HUDProvider } from '@/context/HUDContext';
import { Header } from '@/components/Header';
import { NavigationMenu } from '@/components/NavigationMenu';

const hanken = Hanken_Grotesk({
  subsets: ['latin'],
  variable: '--font-hanken',
  weight: ['500', '600', '700'],
});

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  weight: ['400', '500'],
});

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains',
  weight: ['500', '700'],
});

export const metadata = {
  title: 'Project Aegis - Operations Control HUD',
  description: 'Autonomous Real-Time Streaming Telemetry Operations Dashboard with Gemini 2.5 Flash Agent Co-Pilot',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${hanken.variable} ${inter.variable} ${jetbrains.variable}`}>
      <body className="bg-[#0b1326] text-[#dae2fd] min-h-screen antialiased font-sans flex flex-col">
        <HUDProvider>
          {/* Top Sticky Header */}
          <Header />

          {/* Sticky Navigation Menu */}
          <NavigationMenu />

          {/* Page Workspace Container */}
          <main className="flex-1 max-w-[1600px] w-full mx-auto p-4 md:p-8 animate-fade-in">
            {children}
          </main>

          {/* Shared Footer */}
          <footer className="w-full border-t border-[#334155] py-6 px-6 text-center text-xs text-[#8b909f] font-mono tracking-wider">
            Project Aegis Operations HUD | Cloud Solutions Team | Eyal Ben Ivri
          </footer>
        </HUDProvider>
      </body>
    </html>
  );
}
