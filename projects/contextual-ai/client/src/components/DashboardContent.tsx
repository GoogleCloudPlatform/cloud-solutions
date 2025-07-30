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

import React, { useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  TrendingUp,
  TrendingDown,
  Users,
  DollarSign,
  Activity,
  Eye,
  Clock,
  CheckCircle,
  AlertTriangle
} from 'lucide-react';
import RevenueResponseTimeChart from './charts/RevenueResponseTimeChart';
import SystemHealthHeatmap from './charts/SystemHealthHeatmap';
import ErrorRateTrendChart from './charts/ErrorRateTrendChart';
import WidgetAnalysisService from '@/services/widgetAnalysisService';
// import ChatService from '@/services/chatService'; // Not needed since we use backend API

interface DashboardContentProps {
  activeItem: string;
  onAnalysisStart?: () => void;
  onAnalysisEnd?: () => void;
}

// Add a global flag to prevent multiple simultaneous analyses
let isAnalyzing = false;

const dashboardStats = [
  {
    title: 'Total Revenue',
    value: '$45,231',
    change: '+20.1%',
    trend: 'up' as const,
    icon: <DollarSign className="h-4 w-4" />
  },
  {
    title: 'Active Users',
    value: '2,345',
    change: '+12.5%',
    trend: 'up' as const,
    icon: <Users className="h-4 w-4" />
  },
  {
    title: 'Page Views',
    value: '54,321',
    change: '-5.2%',
    trend: 'down' as const,
    icon: <Eye className="h-4 w-4" />
  },
  {
    title: 'Response Time',
    value: '1.2s',
    change: '+2.1%',
    trend: 'down' as const,
    icon: <Clock className="h-4 w-4" />
  }
];

const recentActivities = [
  { id: 1, action: 'User registration completed', time: '2 minutes ago', status: 'success' },
  { id: 2, action: 'Payment processed', time: '5 minutes ago', status: 'success' },
  { id: 3, action: 'API rate limit exceeded', time: '10 minutes ago', status: 'warning' },
  { id: 4, action: 'Database backup completed', time: '1 hour ago', status: 'success' },
  { id: 5, action: 'Server health check', time: '2 hours ago', status: 'success' }
];

export function DashboardContent({ activeItem, onAnalysisStart, onAnalysisEnd }: DashboardContentProps) {

  // Handle revenue/response time chart clicks
  const handleRevenueResponseTimeClick = useCallback(async (dataPoint: {
    timestamp: string;
    revenue: number;
    responseTime: number;
  }) => {
    console.log('Revenue/Response Time analysis requested:', dataPoint);

    onAnalysisStart?.();
    try {
      // Pass the real dashboard KPIs to the AI
      const currentKPIs = {
        totalRevenue: 45231,
        activeUsers: 2345,
        pageViews: 54321,
        responseTime: '1.2s'
      };

      const result = await WidgetAnalysisService.analyzeRevenueResponseChart(dataPoint, currentKPIs);
      if (result) {
        console.log('Analysis result:', result);

        // The backend API has already created the conversation
        // The chat UI will automatically refresh via polling
      }
    } catch (error) {
      console.error('Widget analysis failed:', error);
    } finally {
      onAnalysisEnd?.();
    }
  }, [onAnalysisStart, onAnalysisEnd]);

  // Handle system health heatmap clicks
  const handleSystemHealthClick = useCallback(async (service: {
    name: string;
    displayName: string;
    status: string;
    cpu: number;
    memory: number;
    responseTime: number;
  }) => {
    console.log('System Health analysis requested:', service);

    onAnalysisStart?.();
    try {
      // Pass the real dashboard KPIs to the AI
      const currentKPIs = {
        totalRevenue: 45231,
        activeUsers: 2345,
        pageViews: 54321,
        responseTime: '1.2s'
      };

      const result = await WidgetAnalysisService.analyzeSystemHealthHeatmap(service, currentKPIs);
      if (result) {
        console.log('Analysis result:', result);

        // The backend API has already created the conversation
        // The chat UI will automatically refresh via polling
      }
    } catch (error) {
      console.error('Widget analysis failed:', error);
    } finally {
      onAnalysisEnd?.();
    }
  }, [onAnalysisStart, onAnalysisEnd]);

  // Handle error rate trend chart clicks
  const handleErrorRateClick = useCallback(async (dataPoint: {
    timestamp: string;
    errorRate: number;
    totalRequests: number;
    errors: number;
    isAnomaly?: boolean;
    incident?: string;
  }) => {
    console.log('Error Rate analysis requested:', dataPoint);

    // Prevent multiple simultaneous analyses
    if (isAnalyzing) {
      console.log('Analysis already in progress, ignoring click');
      return;
    }

    isAnalyzing = true;
    onAnalysisStart?.();

    try {
      console.log('Starting error rate analysis for:', dataPoint);

      // Pass the real dashboard KPIs to the AI
      const currentKPIs = {
        totalRevenue: 45231,
        activeUsers: 2345,
        pageViews: 54321,
        responseTime: '1.2s'
      };

      const result = await WidgetAnalysisService.analyzeErrorRateChart(dataPoint, currentKPIs);
      if (result) {
        console.log('Analysis result:', result);
        // The backend API has already created the conversation
        // The chat UI will automatically refresh via polling
      }
    } catch (error) {
      console.error('Widget analysis failed:', error);
    } finally {
      isAnalyzing = false;
      onAnalysisEnd?.();
    }
  }, [onAnalysisStart, onAnalysisEnd]);

  const renderDashboard = () => (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {dashboardStats.map((stat, index) => (
          <Card key={index}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.title}
              </CardTitle>
              <div className="text-muted-foreground">
                {stat.icon}
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <div className="flex items-center text-xs text-muted-foreground">
                {stat.trend === 'up' ? (
                  <TrendingUp className="h-3 w-3 text-green-500 mr-1" />
                ) : (
                  <TrendingDown className="h-3 w-3 text-red-500 mr-1" />
                )}
                <span className={stat.trend === 'up' ? 'text-green-500' : 'text-red-500'}>
                  {stat.change}
                </span>
                <span className="ml-1">from last month</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue vs Response Time Chart */}
        <div className="lg:col-span-2">
          <RevenueResponseTimeChart
            onPointClick={handleRevenueResponseTimeClick}
          />
        </div>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentActivities.map((activity) => (
                <div key={activity.id} className="flex items-start space-x-3">
                  <div className="mt-1">
                    {activity.status === 'success' ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <AlertTriangle className="h-4 w-4 text-yellow-500" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground">
                      {activity.action}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {activity.time}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Health Heatmap */}
        <SystemHealthHeatmap
          onServiceClick={handleSystemHealthClick}
        />

        {/* Error Rate Trend */}
        <ErrorRateTrendChart
          onAnomalyClick={handleErrorRateClick}
        />
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              <Button variant="outline" className="h-20 flex flex-col items-center">
                <Users className="h-6 w-6 mb-2" />
                <span className="text-sm">Add User</span>
              </Button>
              <Button variant="outline" className="h-20 flex flex-col items-center">
                <Activity className="h-6 w-6 mb-2" />
                <span className="text-sm">View Reports</span>
              </Button>
              <Button variant="outline" className="h-20 flex flex-col items-center">
                <DollarSign className="h-6 w-6 mb-2" />
                <span className="text-sm">Billing</span>
              </Button>
              <Button variant="outline" className="h-20 flex flex-col items-center">
                <Eye className="h-6 w-6 mb-2" />
                <span className="text-sm">Analytics</span>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>System Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">API Server</span>
                <Badge className="bg-green-500">Online</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Database</span>
                <Badge className="bg-green-500">Online</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Cache</span>
                <Badge className="bg-yellow-500">Warning</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Storage</span>
                <Badge className="bg-green-500">Online</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );

  const renderGenericContent = (title: string) => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[400px] bg-muted rounded-lg flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <div className="text-6xl mb-4">🚧</div>
              <p className="text-lg font-medium">Coming Soon</p>
              <p className="text-sm">This {title.toLowerCase()} section is under development</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );

  switch (activeItem) {
    case 'dashboard':
      return renderDashboard();
    case 'analytics':
      return renderGenericContent('Analytics');
    case 'data':
      return renderGenericContent('Data Sources');
    case 'models':
      return renderGenericContent('AI Models');
    case 'monitoring':
      return renderGenericContent('Monitoring');
    case 'automation':
      return renderGenericContent('Automation');
    case 'reports':
      return renderGenericContent('Reports');
    case 'users':
      return renderGenericContent('User Management');
    case 'settings':
      return renderGenericContent('Settings');
    default:
      return renderDashboard();
  }
}
