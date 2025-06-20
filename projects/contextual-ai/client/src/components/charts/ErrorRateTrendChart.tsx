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
  Filler,
  TimeScale,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-adapter-date-fns';
import { subHours, format } from 'date-fns';
import { AlertTriangle } from 'lucide-react';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  TimeScale
);

interface ErrorDataPoint {
  timestamp: string;
  errorRate: number;
  totalRequests: number;
  errors: number;
  isAnomaly?: boolean;
  incident?: string;
}

interface ErrorRateTrendChartProps {
  onAnomalyClick?: (data: ErrorDataPoint) => void;
}

const ErrorRateTrendChart: React.FC<ErrorRateTrendChartProps> = ({ onAnomalyClick }) => {
  const [data, setData] = useState<ErrorDataPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const generateMockData = (): ErrorDataPoint[] => {
    const mockData: ErrorDataPoint[] = [];
    const now = new Date();

    for (let i = 23; i >= 0; i--) {
      const timestamp = subHours(now, i);

      // Base error rate between 0.1% and 2%
      let errorRate = 0.1 + Math.random() * 1.9;
      const totalRequests = 1000 + Math.random() * 2000;

      // Add some anomalies/spikes
      const isAnomaly = Math.random() < 0.08; // 8% chance of anomaly
      let incident = undefined;

      if (isAnomaly) {
        errorRate = 5 + Math.random() * 10; // Spike to 5-15%
        const incidents = [
          'Database connection timeout',
          'Payment gateway failure',
          'High traffic spike',
          'Third-party API timeout',
          'Memory leak detected'
        ];
        incident = incidents[Math.floor(Math.random() * incidents.length)];
      }

      // Add known incidents at specific times
      if (i === 8) {
        errorRate = 12.5;
        incident = 'Scheduled maintenance - Database';
      } else if (i === 15) {
        errorRate = 8.2;
        incident = 'CDN outage affecting static assets';
      }

      const errors = Math.round((errorRate / 100) * totalRequests);

      mockData.push({
        timestamp: timestamp.toISOString(),
        errorRate: Math.round(errorRate * 100) / 100,
        totalRequests: Math.round(totalRequests),
        errors,
        isAnomaly: errorRate > 4,
        incident
      });
    }

    return mockData;
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // In real implementation, this would be an API call to BigQuery
        // await fetch('/api/data_access/error-rates');

        await new Promise(resolve => setTimeout(resolve, 700));

        const mockData = generateMockData();
        setData(mockData);
      } catch (err) {
        setError('Failed to load error rate data');
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
        label: 'Error Rate (%)',
        data: data.map(d => d.errorRate),
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        fill: true,
        tension: 0.4,
        pointRadius: data.map(d => d.isAnomaly ? 6 : 3),
        pointBackgroundColor: data.map(d => d.isAnomaly ? '#dc2626' : 'rgb(239, 68, 68)'),
        pointBorderColor: data.map(d => d.isAnomaly ? '#fff' : 'rgb(239, 68, 68)'),
        pointBorderWidth: data.map(d => d.isAnomaly ? 2 : 1),
        pointHoverRadius: 8,
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
        text: 'Error Rate Trend (Last 24 Hours)',
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
            const lines = [];

            lines.push(`Total Requests: ${point.totalRequests.toLocaleString()}`);
            lines.push(`Error Count: ${point.errors.toLocaleString()}`);

            if (point.incident) {
              lines.push('');
              lines.push(`Incident: ${point.incident}`);
            }

            if (point.isAnomaly) {
              lines.push('');
              lines.push('⚠️ Anomaly detected - click for AI analysis');
            }

            return lines;
          }
        }
      }
    },
    onClick: (event: any, elements: any) => {
      if (elements.length > 0 && onAnomalyClick) {
        const index = elements[0].index;
        const point = data[index];
        if (point.isAnomaly) {
          onAnomalyClick(point);
        }
      }
    },
    scales: {
      x: {
        type: 'time' as const,
        time: {
          unit: 'hour' as const,
          displayFormats: {
            hour: 'HH:mm'
          }
        },
        title: {
          display: true,
          text: 'Time (Last 24 Hours)',
          color: '#6b7280'
        },
        grid: {
          color: '#f3f4f6'
        }
      },
      y: {
        type: 'linear' as const,
        display: true,
        title: {
          display: true,
          text: 'Error Rate (%)',
          color: '#6b7280'
        },
        grid: {
          color: '#f3f4f6'
        },
        ticks: {
          callback: function(value: any) {
            return value + '%';
          }
        },
        min: 0
      }
    },
  };

  const anomalies = data.filter(d => d.isAnomaly);
  const currentErrorRate = data.length > 0 ? data[data.length - 1].errorRate : 0;

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
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-600">Current Error Rate:</span>
          <span className={`text-lg font-semibold ${currentErrorRate > 5 ? 'text-red-600' : currentErrorRate > 2 ? 'text-yellow-600' : 'text-green-600'}`}>
            {currentErrorRate}%
          </span>
        </div>
        {anomalies.length > 0 && (
          <div className="flex items-center text-amber-600">
            <AlertTriangle className="w-4 h-4 mr-1" />
            <span className="text-sm">{anomalies.length} anomalies detected</span>
          </div>
        )}
      </div>
      <div className="h-64">
        <Line data={chartData} options={options} />
      </div>
      {anomalies.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Recent Incidents:</h4>
          <div className="space-y-1">
            {anomalies.slice(-3).map((anomaly, index) => (
              <div key={index} className="text-xs text-gray-600 flex items-center justify-between">
                <span>{format(new Date(anomaly.timestamp), 'HH:mm')} - {anomaly.incident || 'High error rate detected'}</span>
                <span className="text-red-600 font-medium">{anomaly.errorRate}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="mt-4 text-sm text-gray-600">
        <p>Click on anomaly points (larger dots) to get AI insights about error spikes</p>
      </div>
    </div>
  );
};

export default ErrorRateTrendChart;
