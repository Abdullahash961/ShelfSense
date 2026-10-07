import { useState, useMemo } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Filler,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { useZoneHistory } from '../hooks/useApi';
import './TrendChart.css';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler);

export default function TrendChart({ zones }) {
  const [selectedZoneId, setSelectedZoneId] = useState(null);
  const { data: history, loading } = useZoneHistory(selectedZoneId, 30);

  // Get unique zones from status results
  const uniqueZones = useMemo(() => {
    if (!zones) return [];
    const seen = new Set();
    return zones.filter((z) => {
      if (seen.has(z.zone_id)) return false;
      seen.add(z.zone_id);
      return true;
    });
  }, [zones]);

  // Reverse so oldest is first (left) on the chart
  const sorted = useMemo(() => [...history].reverse(), [history]);

  const chartData = {
    labels: sorted.map((r) => {
      const d = new Date(r.analyzed_at);
      return d.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    }),
    datasets: [
      {
        label: 'Fill %',
        data: sorted.map((r) => Math.round(r.fill_score * 100)),
        borderColor: '#f0b429',
        backgroundColor: 'rgba(240, 180, 41, 0.08)',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#f0b429',
        pointBorderColor: 'transparent',
        pointHoverRadius: 5,
        tension: 0.35,
        fill: true,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      intersect: false,
      mode: 'index',
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255,255,255,0.03)',
          drawBorder: false,
        },
        ticks: {
          color: 'rgba(240,240,245,0.3)',
          font: { size: 10, family: 'Inter' },
          maxTicksLimit: 8,
        },
      },
      y: {
        min: 0,
        max: 100,
        grid: {
          color: 'rgba(255,255,255,0.03)',
          drawBorder: false,
        },
        ticks: {
          color: 'rgba(240,240,245,0.3)',
          font: { size: 10, family: 'Inter' },
          callback: (v) => `${v}%`,
          stepSize: 25,
        },
      },
    },
    plugins: {
      tooltip: {
        backgroundColor: '#1a1a24',
        titleColor: '#f0f0f5',
        bodyColor: '#f0f0f5',
        borderColor: 'rgba(255,255,255,0.08)',
        borderWidth: 1,
        cornerRadius: 8,
        padding: 10,
        titleFont: { family: 'Inter', weight: '600' },
        bodyFont: { family: 'Inter' },
        callbacks: {
          label: (ctx) => `Fill: ${ctx.parsed.y}%`,
        },
      },
    },
  };

  return (
    <div className="section fade-in">
      <div className="trend-header">
        <h2 className="section-title" style={{ marginBottom: 0 }}>Fill Trend</h2>
        <select
          className="input trend-select"
          value={selectedZoneId || ''}
          onChange={(e) => setSelectedZoneId(e.target.value ? Number(e.target.value) : null)}
          id="trend-zone-select"
        >
          <option value="">Select a zone…</option>
          {uniqueZones.map((z) => (
            <option key={z.zone_id} value={z.zone_id}>
              {z.zone_name}
            </option>
          ))}
        </select>
      </div>

      <div className="card trend-chart-container">
        {!selectedZoneId ? (
          <div className="trend-placeholder">
            Select a zone to view its fill percentage over time
          </div>
        ) : loading ? (
          <div className="skeleton" style={{ height: 220 }} />
        ) : sorted.length === 0 ? (
          <div className="trend-placeholder">
            No history available for this zone
          </div>
        ) : (
          <div className="trend-chart-wrapper">
            <Line data={chartData} options={chartOptions} />
          </div>
        )}
      </div>
    </div>
  );
}
