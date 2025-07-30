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

import React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  BarChart3,
  Database,
  FileText,
  Home,
  Settings,
  Users,
  Activity,
  Brain,
  Zap,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

interface SidebarProps {
  activeItem: string;
  onItemSelect: (item: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  badge?: string;
}

const navItems: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: <Home className="h-4 w-4" /> },
  { id: 'analytics', label: 'Analytics', icon: <BarChart3 className="h-4 w-4" />, badge: '5' },
  { id: 'data', label: 'Data Sources', icon: <Database className="h-4 w-4" /> },
  { id: 'models', label: 'AI Models', icon: <Brain className="h-4 w-4" />, badge: 'New' },
  { id: 'monitoring', label: 'Monitoring', icon: <Activity className="h-4 w-4" /> },
  { id: 'automation', label: 'Automation', icon: <Zap className="h-4 w-4" /> },
  { id: 'reports', label: 'Reports', icon: <FileText className="h-4 w-4" /> },
  { id: 'users', label: 'Users', icon: <Users className="h-4 w-4" /> },
];

export function Sidebar({ activeItem, onItemSelect, isCollapsed, onToggleCollapse }: SidebarProps) {
  if (isCollapsed) {
    return (
      <aside className="w-16 bg-background border-r border-border flex flex-col h-full">
        {/* Collapsed Header */}
        <div className="p-2 border-b border-border">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
            className="w-full h-12"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        {/* Collapsed Navigation Icons - Scrollable */}
        <div className="flex-1 overflow-y-auto">
          <nav className="p-2 space-y-2">
            {navItems.map((item) => (
              <Button
                key={item.id}
                variant={activeItem === item.id ? "default" : "ghost"}
                size="icon"
                className="w-full h-12 relative"
                onClick={() => onItemSelect(item.id)}
                title={item.label}
              >
                {item.icon}
                {item.badge && (
                  <Badge className="absolute -top-2 -right-2 h-5 w-5 rounded-full p-0 text-xs flex items-center justify-center">
                    {item.badge.length > 2 ? '!' : item.badge}
                  </Badge>
                )}
              </Button>
            ))}
          </nav>
        </div>

        {/* Collapsed Settings - Fixed at bottom */}
        <div className="p-2 border-t border-border">
          <Button
            variant={activeItem === 'settings' ? "default" : "ghost"}
            size="icon"
            className="w-full h-12"
            onClick={() => onItemSelect('settings')}
            title="Settings"
          >
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-64 bg-background border-r border-border flex flex-col h-full">
      {/* Header with Toggle */}
      <div className="p-4 border-b border-border bg-background">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-6 h-6 bg-primary rounded flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-xs">CA</span>
            </div>
            <span className="font-medium text-sm">Navigation</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleCollapse}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Navigation - Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        <nav className="p-4 space-y-2">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4">
            Main Navigation
          </div>

          {navItems.map((item) => (
            <Button
              key={item.id}
              variant={activeItem === item.id ? "default" : "ghost"}
              className="w-full justify-start h-10 px-3"
              onClick={() => onItemSelect(item.id)}
            >
              {item.icon}
              <span className="ml-3 flex-1 text-left">{item.label}</span>
              {item.badge && (
                <Badge variant={activeItem === item.id ? "secondary" : "default"} className="ml-auto">
                  {item.badge}
                </Badge>
              )}
            </Button>
          ))}

          {/* Settings in scrollable area */}
          <div className="pt-4 border-t border-border">
            <Button
              variant={activeItem === 'settings' ? "default" : "ghost"}
              className="w-full justify-start h-10 px-3"
              onClick={() => onItemSelect('settings')}
            >
              <Settings className="h-4 w-4" />
              <span className="ml-3">Settings</span>
            </Button>
          </div>
        </nav>
      </div>

      {/* Footer - Fixed at bottom */}
      <div className="p-4 border-t border-border bg-background">
        <div className="bg-muted rounded-lg p-3">
          <div className="text-sm font-medium text-foreground mb-1">
            Pro Plan
          </div>
          <div className="text-xs text-muted-foreground mb-2">
            14 days remaining
          </div>
          <Button size="sm" className="w-full">
            Upgrade
          </Button>
        </div>
      </div>
    </aside>
  );
}
