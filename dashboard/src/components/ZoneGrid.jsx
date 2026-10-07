import { Eye, Package } from 'lucide-react';
import './ZoneGrid.css';

function FillGauge({ value }) {
  const pct = Math.round(value * 100);
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value * circumference);

  let color = 'var(--status-empty)';
  if (pct >= 50) color = 'var(--status-full)';
  else if (pct >= 15) color = 'var(--status-low)';

  return (
    <div className="fill-gauge">
      <svg width="68" height="68" viewBox="0 0 68 68">
        <circle
          cx="34" cy="34" r={radius}
          fill="none"
          stroke="var(--border-subtle)"
          strokeWidth="4"
        />
        <circle
          cx="34" cy="34" r={radius}
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 34 34)"
          style={{ transition: 'stroke-dashoffset 600ms ease' }}
        />
      </svg>
      <span className="fill-gauge-text" style={{ color }}>{pct}%</span>
    </div>
  );
}

function StatusBadge({ status }) {
  const cls = `badge badge-${status.toLowerCase()}`;
  return <span className={cls}>{status}</span>;
}

export default function ZoneGrid({ zones, onViewImage }) {
  if (!zones || zones.length === 0) {
    return (
      <div className="section fade-in">
        <h2 className="section-title">Zone Status</h2>
        <div className="card empty-state">
          <p>No zones analyzed yet. Upload a shelf image to get started.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="section fade-in">
      <h2 className="section-title">Zone Status</h2>
      <div className="grid-3">
        {zones.map((zone, i) => (
          <div
            key={zone.id}
            className={`card card-interactive zone-card stagger-${Math.min(i + 1, 6)}`}
            id={`zone-card-${zone.zone_id}`}
          >
            <div className="zone-card-top">
              <div>
                <h3 className="zone-card-name">{zone.zone_name}</h3>
                <p className="zone-card-product">{zone.product_name}</p>
              </div>
              <FillGauge value={zone.fill_score} />
            </div>

            {zone.product_count != null && (
              <div className="zone-card-count">
                <Package size={13} />
                <span>{zone.product_count} product{zone.product_count !== 1 ? 's' : ''} detected</span>
              </div>
            )}

            <div className="zone-card-bottom">
              <StatusBadge status={zone.status} />
              {zone.image_path && (
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewImage(zone);
                  }}
                  title="View shelf capture"
                >
                  <Eye size={13} />
                  View
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
