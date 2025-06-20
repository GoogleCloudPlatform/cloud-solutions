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
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import { subDays } from 'date-fns';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
);

interface DataPoint {
  timestamp: string;
  revenue: number;
  responseTime: number;
}

interface RevenueResponseTimeChartProps {
  onPointClick?: (data: DataPoint) => void;
}

const RevenueResponseTimeChart: React.FC<RevenueResponseTimeChartProps> = ({ onPointClick }) => {
  const [data, setData] = useState<DataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Generate mock data for the last 7 days
  const generateMockData = (): DataPoint[] => {
    const mockData: DataPoint[] = [];
    const now = new Date();

    for (let i = 6; i >= 0; i--) {
      const date = subDays(now, i);
      for (let hour = 0; hour < 24; hour++) {
        const timestamp = new Date(date);
        timestamp.setHours(hour, 0, 0, 0);

        // Simulate correlation between response time and revenue
        const baseRevenue = 1000 + Math.random() * 500;
        const responseTime = 100 + Math.random() * 200;

        // Add correlation: higher response time = lower revenue
        const correlationFactor = Math.max(0, 1 - (responseTime - 100) / 300);
        const adjustedRevenue = baseRevenue * (0.7 + 0.3 * correlationFactor);

        // Add some spikes for demonstration
        const isSpike = Math.random() < 0.05;
        const finalResponseTime = isSpike ? responseTime + 300 : responseTime;
        const finalRevenue = isSpike ? adjustedRevenue * 0.6 : adjustedRevenue;

        mockData.push({
          timestamp: timestamp.toISOString(),
          revenue: Math.round(finalRevenue),
          responseTime: Math.round(finalResponseTime)
        });
      }
    }
    return mockData;
  };

  useEffect(() => {
    // Simulate API call
    const fetchData = async () => {
      try {
        setLoading(true);
        // In real implementation, this would be an API call to BigQuery
        // await fetch('/api/data_access/revenue-response-time');

        // Simulate network delay
        await new Promise(resolve => setTimeout(resolve, 800));

        const mockData = generateMockData();
        setData(mockData);
      } catch (err) {
        setError('Failed to load chart data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const chartData = {
    labels: data.map(d => d.timestamp),
    datasets: [
      {
        label: 'Hourly Revenue ($)',
        data: data.map(d => d.revenue),
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        yAxisID: 'y',
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 6,
      },
      {
        label: 'Response Time (ms)',
        data: data.map(d => d.responseTime),
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        yAxisID: 'y1',
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 6,
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      title: {
        display: true,
        text: 'Revenue vs Response Time Correlation (Last 7 Days)',
        color: '#1f2937',
        font: {
          size: 16,
          weight: 'bold' as const,
        }
      },
      legend: {
        position: 'top' as const,
        labels: {
          usePointStyle: true,
          padding: 20,
          color: '#4b5563'
        }
      },
      tooltip: {
        callbacks: {
          afterBody: (context: any) => {
            const index = context[0].dataIndex;
            const point = data[index];
            if (point.responseTime > 250) {
              return 'High response time detected - potential impact on revenue';
            }
            return '';
          }
        }
      }
    },
    onClick: (event: any, elements: any) => {
      if (elements.length > 0 && onPointClick) {
        const index = elements[0].index;
        onPointClick(data[index]);
      }
    },
    scales: {
      x: {
        type: 'time' as const,
        time: {
          unit: 'hour' as const,
          displayFormats: {
            hour: 'MMM dd HH:mm'
          }
        },
        title: {
          display: true,
          text: 'Time',
          color: '#6b7280'
        },
        grid: {
          color: '#f3f4f6'
        }
      },
      y: {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        title: {
          display: true,
          text: 'Revenue ($)',
          color: '#6b7280'
        },
        grid: {
          color: '#f3f4f6'
        },
        ticks: {
          callback: function(value: any) {
            return '$' + value.toLocaleString();
          }
        }
      },
      y1: {
        type: 'linear' as const,
        display: true,
        position: 'right' as const,
        title: {
          display: true,
          text: 'Response Time (ms)',
          color: '#6b7280'
        },
        grid: {
          drawOnChartArea: false,
        },
        ticks: {
          callback: function(value: any) {
            return value + 'ms';
          }
        }
      },
    },
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
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
      <div className="h-80">
        <Line data={chartData} options={options} />
      </div>
      <div className="mt-4 text-sm text-gray-600">
        <p>Click on data points to get AI insights about performance correlations</p>
      </div>
    </div>
  );
};

export default RevenueResponseTimeChart;
