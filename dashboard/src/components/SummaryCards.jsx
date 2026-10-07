import { Package, TrendingDown, AlertTriangle, Layers, ShoppingCart } from 'lucide-react';
import './SummaryCards.css';

const cards = [
  { key: 'total', label: 'Total Zones', icon: Layers, color: 'var(--text-secondary)' },
  { key: 'FULL', label: 'Full', icon: Package, color: 'var(--status-full)' },
  { key: 'LOW', label: 'Low Stock', icon: TrendingDown, color: 'var(--status-low)' },
  { key: 'EMPTY', label: 'Empty', icon: AlertTriangle, color: 'var(--status-empty)' },
  { key: 'products', label: 'Total Products', icon: ShoppingCart, color: 'var(--accent)' },
];

export default function SummaryCards({ summary, totalZones, zones }) {
  // Sum product counts from all zones
  const totalProducts = zones
    ? zones.reduce((sum, z) => sum + (z.product_count ?? 0), 0)
    : 0;

  const counts = {
    total: totalZones ?? 0,
    FULL: summary?.FULL ?? 0,
    LOW: summary?.LOW ?? 0,
    EMPTY: summary?.EMPTY ?? 0,
    products: totalProducts,
  };

  return (
    <div className="section fade-in">
      <div className="grid-5">
        {cards.map((c, i) => {
          const Icon = c.icon;
          return (
            <div
              key={c.key}
              className={`card summary-card stagger-${i + 1}`}
              id={`summary-${c.key}`}
            >
              <div className="summary-card-header">
                <Icon size={16} style={{ color: c.color }} />
                <span className="summary-card-label">{c.label}</span>
              </div>
              <div className="summary-card-value" style={{ color: c.color }}>
                {counts[c.key]}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
