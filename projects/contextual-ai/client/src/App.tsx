// Copyright 2024 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import React, { useState } from 'react';
import { Header } from '@/components/Header';
import { Sidebar } from '@/components/Sidebar';
import { DashboardContent } from '@/components/DashboardContent';
import { ChatPanel } from '@/components/ChatPanel';
import './App.css';

function App() {
  const [activeItem, setActiveItem] = useState('dashboard');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  return (
    <div className="h-screen bg-background flex flex-col">
      {/* Header - Fixed at top */}
      <Header />

      {/* Main Layout - Three Column */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar
          activeItem={activeItem}
          onItemSelect={setActiveItem}
          isCollapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* Main Content - Scrollable */}
        <main className="flex-1 overflow-y-auto min-w-0">
          <div className="p-6 max-w-none">
            <DashboardContent
              activeItem={activeItem}
              onAnalysisStart={() => setIsAnalyzing(true)}
              onAnalysisEnd={() => setIsAnalyzing(false)}
            />
          </div>
        </main>

        {/* Right Chat Panel */}
        <ChatPanel
          isCollapsed={chatCollapsed}
          onToggleCollapse={() => setChatCollapsed(!chatCollapsed)}
          externalThinking={isAnalyzing}
        />
      </div>
    </div>
  );
}

export default App;
