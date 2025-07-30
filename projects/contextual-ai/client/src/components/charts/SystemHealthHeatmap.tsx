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

import React, { useEffect, useState } from 'react';
import { Activity, AlertCircle, CheckCircle, Clock } from 'lucide-react';

interface ServiceHealth {
  name: string;
  displayName: string;
  status: 'healthy' | 'warning' | 'critical';
  cpu: number;
  memory: number;
  responseTime: number;
  lastUpdate: string;
}

interface SystemHealthHeatmapProps {
  onServiceClick?: (service: ServiceHealth) => void;
}

const SystemHealthHeatmap: React.FC<SystemHealthHeatmapProps> = ({ onServiceClick }) => {
  const [services, setServices] = useState<ServiceHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const generateMockData = (): ServiceHealth[] => {
    const serviceConfigs = [
      { name: 'web-frontend', displayName: 'Web Frontend' },
      { name: 'payment-api', displayName: 'Payment API' },
      { name: 'inventory-service', displayName: 'Inventory Service' },
      { name: 'recommendation-engine', displayName: 'Recommendation Engine' }
    ];

    return serviceConfigs.map(config => {
      const cpu = Math.random() * 100;
      const memory = Math.random() * 100;
      const responseTime = 50 + Math.random() * 200;

      // Determine status based on thresholds
      let status: 'healthy' | 'warning' | 'critical' = 'healthy';
      if (cpu > 80 || memory > 85 || responseTime > 200) {
        status = 'critical';
      } else if (cpu > 60 || memory > 70 || responseTime > 150) {
        status = 'warning';
      }

      return {
        name: config.name,
        displayName: config.displayName,
        status,
        cpu: Math.round(cpu),
        memory: Math.round(memory),
        responseTime: Math.round(responseTime),
        lastUpdate: new Date().toISOString()
      };
    });
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // In real implementation, this would be an API call to BigQuery
        // await fetch('/api/data_access/system-health');

        await new Promise(resolve => setTimeout(resolve, 600));

        const mockData = generateMockData();
        setServices(mockData);
      } catch (err) {
        setError('Failed to load system health data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();

    // Set up auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'healthy':
        return 'bg-green-100 border-green-300 text-green-800';
      case 'warning':
        return 'bg-yellow-100 border-yellow-300 text-yellow-800';
      case 'critical':
        return 'bg-red-100 border-red-300 text-red-800';
      default:
        return 'bg-gray-100 border-gray-300 text-gray-800';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'warning':
        return <AlertCircle className="w-5 h-5 text-yellow-600" />;
      case 'critical':
        return <AlertCircle className="w-5 h-5 text-red-600" />;
      default:
        return <Activity className="w-5 h-5 text-gray-600" />;
    }
  };

  const getMetricColor = (value: number, type: 'cpu' | 'memory' | 'responseTime'): string => {
    let threshold1, threshold2;

    switch (type) {
      case 'cpu':
      case 'memory':
        threshold1 = 60;
        threshold2 = 80;
        break;
      case 'responseTime':
        threshold1 = 150;
        threshold2 = 200;
        break;
    }

    if (value > threshold2) return 'text-red-600 font-semibold';
    if (value > threshold1) return 'text-yellow-600 font-medium';
    return 'text-green-600';
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="grid grid-cols-2 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="text-center text-red-600">
          <p>{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 text-blue-600 hover:text-blue-800"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">System Health Status</h3>
        <div className="flex items-center text-sm text-gray-500">
          <Clock className="w-4 h-4 mr-1" />
          <span>Auto-refresh: 30s</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {services.map((service) => (
          <div
            key={service.name}
            className={`border-2 rounded-lg p-4 cursor-pointer transition-all duration-200 hover:shadow-md ${getStatusColor(service.status)}`}
            onClick={() => onServiceClick?.(service)}
          >
            <div className="mb-3">
              <div className="flex items-center space-x-2 mb-2">
                {getStatusIcon(service.status)}
                <h4 className="font-semibold">{service.displayName}</h4>
              </div>
              <span className="text-xs px-2 py-1 rounded-full bg-white bg-opacity-50 inline-block">
                {service.status.toUpperCase()}
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-sm">CPU Usage:</span>
                <span className={`text-sm ${getMetricColor(service.cpu, 'cpu')}`}>
                  {service.cpu}%
                </span>
              </div>

              <div className="flex justify-between items-center">
                <span className="text-sm">Memory:</span>
                <span className={`text-sm ${getMetricColor(service.memory, 'memory')}`}>
                  {service.memory}%
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Response Time:</span>
                <span className={`text-sm ${getMetricColor(service.responseTime, 'responseTime')}`}>
                  {service.responseTime}ms
                </span>
              </div>
            </div>
            <div className="mt-3 pt-2 border-t border-opacity-20 border-gray-400">
              <div className="text-xs opacity-75">
                Last updated: {new Date(service.lastUpdate).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 text-sm text-gray-600">
        <p>Click on service tiles to get AI insights about system health and performance</p>
      </div>
      <div className="mt-3 flex items-center space-x-4 text-xs text-gray-500">
        <div className="flex items-center space-x-1">
          <div className="w-3 h-3 bg-green-200 rounded"></div>
          <span>Healthy</span>
        </div>
        <div className="flex items-center space-x-1">
          <div className="w-3 h-3 bg-yellow-200 rounded"></div>
          <span>Warning</span>
        </div>
        <div className="flex items-center space-x-1">
          <div className="w-3 h-3 bg-red-200 rounded"></div>
          <span>Critical</span>
        </div>
      </div>
    </div>
  );
};

export default SystemHealthHeatmap;
