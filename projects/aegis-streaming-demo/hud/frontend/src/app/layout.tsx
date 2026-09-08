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

export const dynamic = 'force-dynamic';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const stackTypeRaw = (
    process.env.STACK_TYPE ||
    process.env.NEXT_PUBLIC_STACK_TYPE ||
    'oss'
  ).toLowerCase().trim();

  const stackType =
    stackTypeRaw === 'first_party' || stackTypeRaw === 'low_code'
      ? stackTypeRaw
      : 'oss';

  const runtimeConfig = {
    stackType,
    project: process.env.GCP_PROJECT || process.env.NEXT_PUBLIC_GCP_PROJECT || '',
    region: process.env.GCP_REGION || process.env.NEXT_PUBLIC_GCP_REGION || 'us-central1',
    kafkaCluster: process.env.KAFKA_CLUSTER_ID || process.env.NEXT_PUBLIC_KAFKA_CLUSTER || '',
    kafkaTopic: process.env.KAFKA_TOPIC_ID || process.env.NEXT_PUBLIC_KAFKA_TOPIC || 'telemetry-raw',
    pubsubTopic: process.env.PUBSUB_TOPIC || process.env.NEXT_PUBLIC_PUBSUB_TOPIC || 'telemetry-raw',
    pubsubSubscription:
      process.env.PUBSUB_SUBSCRIPTION || process.env.NEXT_PUBLIC_PUBSUB_SUBSCRIPTION || 'telemetry-raw-dataflow-sub',
    bigtableInstance: process.env.BIGTABLE_INSTANCE_ID || process.env.NEXT_PUBLIC_BIGTABLE_INSTANCE || 'aegis-bigtable',
    bigqueryDataset: process.env.BIGQUERY_DATASET_ID || process.env.NEXT_PUBLIC_BIGQUERY_DATASET || 'analytics',
    geapAgentId: process.env.GEAP_AGENT_ID || process.env.NEXT_PUBLIC_GEAP_AGENT_ID || '',
  };

  return (
    <html lang="en" className={`${hanken.variable} ${inter.variable} ${jetbrains.variable}`}>
      <head>
        <script
          id="aegis-runtime-config"
          dangerouslySetInnerHTML={{
            __html: `window.__AEGIS_RUNTIME_CONFIG__ = ${JSON.stringify(runtimeConfig)};`,
          }}
        />
      </head>
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
