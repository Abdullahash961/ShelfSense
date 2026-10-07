import { AlertTriangle, CheckCircle, Package } from 'lucide-react';
import './AlertsPanel.css';

export default function AlertsPanel({ alerts, loading }) {
  return (
    <div className="section fade-in">
      <h2 className="section-title">Restocking Alerts</h2>

      {loading ? (
        <div className="card">
          <div className="skeleton" style={{ height: 60 }} />
        </div>
      ) : alerts.length === 0 ? (
        <div className="card alerts-clear">
          <CheckCircle size={20} className="alerts-clear-icon" />
          <span>All shelves stocked</span>
        </div>
      ) : (
        <div className="alerts-list">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`card alert-row alert-row-${alert.status.toLowerCase()}`}
              id={`alert-${alert.id}`}
            >
              <div className="alert-row-left">
                <AlertTriangle
                  size={14}
                  style={{
                    color: alert.status === 'EMPTY'
                      ? 'var(--status-empty)'
                      : 'var(--status-low)',
                  }}
                />
                <div>
                  <span className="alert-zone">{alert.zone_name}</span>
                  <span className="alert-product">{alert.product_name}</span>
                </div>
              </div>
              <div className="alert-row-right">
                <span className="alert-fill">{Math.round(alert.fill_score * 100)}%</span>
                {alert.product_count != null && (
                  <span className="alert-count" title="Products detected">
                    <Package size={11} />
                    {alert.product_count}
                  </span>
                )}
                <span className={`badge badge-${alert.status.toLowerCase()}`}>
                  {alert.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
