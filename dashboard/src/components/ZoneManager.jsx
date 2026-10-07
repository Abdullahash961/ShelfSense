import { useState, useEffect } from 'react';
import { Settings, Plus, Edit2, Trash2, Save, X, ChevronUp } from 'lucide-react';
import { useZones } from '../hooks/useApi';
import * as api from '../api/client';
import './ZoneManager.css';

const EMPTY_FORM = {
  zone_name: '',
  product_name: '',
  x: 0,
  y: 0,
  width: 100,
  height: 100,
  full_threshold: 0.5,
  low_threshold: 0.15,
};

export default function ZoneManager({ showToast, refreshKey }) {
  const { data: zones, loading, refresh } = useZones();

  // Re-fetch zones when refreshKey changes (e.g. after drawing new zones)
  useEffect(() => {
    if (refreshKey) refresh();
  }, [refreshKey, refresh]);
  const [expanded, setExpanded] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [isAdding, setIsAdding] = useState(false);
  const [addForm, setAddForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);

  // ── Edit handlers ───────────────────────────────────────────────────

  const startEdit = (zone) => {
    setEditingId(zone.id);
    setEditForm({
      zone_name: zone.zone_name,
      product_name: zone.product_name,
      x: zone.x,
      y: zone.y,
      width: zone.width,
      height: zone.height,
      full_threshold: zone.full_threshold,
      low_threshold: zone.low_threshold,
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm({});
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      await api.updateZone(editingId, editForm);
      showToast('Zone updated');
      setEditingId(null);
      refresh();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  // ── Delete handler ──────────────────────────────────────────────────

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete "${name}"? This also removes all its analysis history.`)) return;
    setSaving(true);
    try {
      await api.deleteZone(id);
      showToast('Zone deleted');
      refresh();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  // ── Add handler ─────────────────────────────────────────────────────

  const handleAdd = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createZone({
        zone_name: addForm.zone_name,
        product_name: addForm.product_name || 'Unassigned',
        x: Number(addForm.x),
        y: Number(addForm.y),
        width: Number(addForm.width),
        height: Number(addForm.height),
        full_threshold: Number(addForm.full_threshold),
        low_threshold: Number(addForm.low_threshold),
      });
      showToast('Zone created');
      setIsAdding(false);
      setAddForm({ ...EMPTY_FORM });
      refresh();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  // ── Collapsed state ─────────────────────────────────────────────────

  if (!expanded) {
    return (
      <div className="section fade-in">
        <button
          className="btn btn-ghost zone-manager-toggle"
          onClick={() => setExpanded(true)}
          id="toggle-zone-manager"
        >
          <Settings size={16} />
          Manage Zones
        </button>
      </div>
    );
  }

  // ── Expanded state ──────────────────────────────────────────────────

  return (
    <div className="section slide-up">
      <div className="zone-mgr-header">
        <h2 className="section-title" style={{ marginBottom: 0 }}>Zone Management</h2>
        <button className="btn btn-ghost btn-sm" onClick={() => setExpanded(false)}>
          <ChevronUp size={14} />
          Collapse
        </button>
      </div>

      <div className="card zone-mgr-card">
        {loading ? (
          <div className="skeleton" style={{ height: 200 }} />
        ) : zones.length === 0 ? (
          <p className="zone-mgr-empty">No zones defined yet.</p>
        ) : (
          <div className="zone-mgr-table-wrap">
            <table className="zone-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Product</th>
                  <th>Position</th>
                  <th>Size</th>
                  <th>Thresholds</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {zones.map((z) =>
                  editingId === z.id ? (
                    <tr key={z.id} className="zone-table-editing">
                      <td className="text-dim">{z.id}</td>
                      <td>
                        <input
                          className="input tbl-input"
                          value={editForm.zone_name}
                          onChange={(e) => setEditForm({ ...editForm, zone_name: e.target.value })}
                        />
                      </td>
                      <td>
                        <input
                          className="input tbl-input"
                          value={editForm.product_name}
                          onChange={(e) => setEditForm({ ...editForm, product_name: e.target.value })}
                        />
                      </td>
                      <td>
                        <div className="tbl-pair">
                          <input type="number" className="input tbl-num" value={editForm.x} onChange={(e) => setEditForm({ ...editForm, x: Number(e.target.value) })} />
                          <span className="tbl-sep">,</span>
                          <input type="number" className="input tbl-num" value={editForm.y} onChange={(e) => setEditForm({ ...editForm, y: Number(e.target.value) })} />
                        </div>
                      </td>
                      <td>
                        <div className="tbl-pair">
                          <input type="number" className="input tbl-num" value={editForm.width} onChange={(e) => setEditForm({ ...editForm, width: Number(e.target.value) })} />
                          <span className="tbl-sep">×</span>
                          <input type="number" className="input tbl-num" value={editForm.height} onChange={(e) => setEditForm({ ...editForm, height: Number(e.target.value) })} />
                        </div>
                      </td>
                      <td>
                        <div className="tbl-pair">
                          <input type="number" step="0.05" className="input tbl-num" value={editForm.full_threshold} onChange={(e) => setEditForm({ ...editForm, full_threshold: Number(e.target.value) })} />
                          <span className="tbl-sep">/</span>
                          <input type="number" step="0.05" className="input tbl-num" value={editForm.low_threshold} onChange={(e) => setEditForm({ ...editForm, low_threshold: Number(e.target.value) })} />
                        </div>
                      </td>
                      <td>
                        <div className="tbl-actions">
                          <button className="btn btn-primary btn-sm" onClick={saveEdit} disabled={saving}><Save size={13} /></button>
                          <button className="btn btn-ghost btn-sm" onClick={cancelEdit} disabled={saving}><X size={13} /></button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    <tr key={z.id}>
                      <td className="text-dim">{z.id}</td>
                      <td className="text-medium">{z.zone_name}</td>
                      <td>{z.product_name}</td>
                      <td className="text-dim tabular">{z.x}, {z.y}</td>
                      <td className="text-dim tabular">{z.width} × {z.height}</td>
                      <td className="text-dim tabular">{Math.round(z.full_threshold * 100)}% / {Math.round(z.low_threshold * 100)}%</td>
                      <td>
                        <div className="tbl-actions">
                          <button className="btn btn-ghost btn-sm" onClick={() => startEdit(z)} title="Edit"><Edit2 size={13} /></button>
                          <button className="btn btn-danger btn-sm" onClick={() => handleDelete(z.id, z.zone_name)} title="Delete"><Trash2 size={13} /></button>
                        </div>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Add zone section */}
        <div className="zone-mgr-add">
          {isAdding ? (
            <form className="add-zone-form fade-in" onSubmit={handleAdd}>
              <h4 className="add-zone-heading">New Zone</h4>
              <div className="add-zone-grid">
                <div className="add-zone-field">
                  <label>Zone Name</label>
                  <input
                    required
                    className="input"
                    placeholder="e.g. Zone A"
                    value={addForm.zone_name}
                    onChange={(e) => setAddForm({ ...addForm, zone_name: e.target.value })}
                  />
                </div>
                <div className="add-zone-field">
                  <label>Product Name</label>
                  <input
                    className="input"
                    placeholder="e.g. Olpers Milk"
                    value={addForm.product_name}
                    onChange={(e) => setAddForm({ ...addForm, product_name: e.target.value })}
                  />
                </div>
              </div>
              <div className="add-zone-coords">
                {[
                  { label: 'X', key: 'x' },
                  { label: 'Y', key: 'y' },
                  { label: 'Width', key: 'width' },
                  { label: 'Height', key: 'height' },
                  { label: 'Full Threshold', key: 'full_threshold', step: '0.05' },
                  { label: 'Low Threshold', key: 'low_threshold', step: '0.05' },
                ].map((f) => (
                  <div key={f.key} className="add-zone-field">
                    <label>{f.label}</label>
                    <input
                      required
                      type="number"
                      step={f.step || '1'}
                      className="input"
                      value={addForm[f.key]}
                      onChange={(e) => setAddForm({ ...addForm, [f.key]: e.target.value })}
                    />
                  </div>
                ))}
              </div>
              <div className="add-zone-actions">
                <button type="button" className="btn btn-ghost" onClick={() => setIsAdding(false)} disabled={saving}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  <Plus size={14} />
                  Create Zone
                </button>
              </div>
            </form>
          ) : (
            <button className="btn btn-ghost add-zone-btn" onClick={() => setIsAdding(true)}>
              <Plus size={16} />
              Add Zone
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
