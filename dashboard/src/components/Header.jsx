import { LayoutDashboard, RefreshCw } from 'lucide-react';
import './Header.css';

export default function Header({ lastAnalyzed, onRefresh, loading }) {
  const formatTime = (iso) => {
    if (!iso) return 'No scans yet';
    const d = new Date(iso);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  };

  return (
    <header className="header fade-in">
      <div className="header-brand">
        <div className="header-icon">
          <LayoutDashboard size={20} />
        </div>
        <div>
          <h1 className="header-title">ShelfSense</h1>
          <p className="header-subtitle">Shelf Monitoring Dashboard</p>
        </div>
      </div>

      <div className="header-actions">
        <div className="header-timestamp">
          <span className="header-label">Last Scan</span>
          <span className="header-time">{formatTime(lastAnalyzed)}</span>
        </div>
        <button
          className="btn btn-ghost btn-sm"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh data"
          id="refresh-btn"
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
          Refresh
        </button>
      </div>
    </header>
  );
}
