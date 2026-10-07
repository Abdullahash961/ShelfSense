import { useState, useRef, useEffect, useCallback } from 'react';
import { Undo2, Save, Pencil } from 'lucide-react';
import './ZoneDrawer.css';

/**
 * ZoneDrawer — HTML5 Canvas zone drawing tool.
 *
 * Props:
 *   imageFile    — the File object the user uploaded
 *   onComplete   — callback({ zones, imageFile }) when user saves zones
 *   onCancel     — callback to go back without saving
 */
export default function ZoneDrawer({ imageFile, existingZones = [], onComplete, onCancel }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  // Original image dimensions (for coordinate scaling)
  const [imgElement, setImgElement] = useState(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [scale, setScale] = useState({ x: 1, y: 1 });

  // Drawing state
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [currentRect, setCurrentRect] = useState(null);

  // Saved zones (pending, not yet sent to API)
  const [pendingZones, setPendingZones] = useState([]);

  // Zone being named (index into pendingZones, or null)
  const [namingIndex, setNamingIndex] = useState(null);
  const [nameForm, setNameForm] = useState({ zone_name: '', product_name: '' });

  // ── Load image into memory ─────────────────────────────────────────

  useEffect(() => {
    if (!imageFile) return;

    const img = new Image();
    const url = URL.createObjectURL(imageFile);
    img.onload = () => {
      setImgElement(img);
      // Fit canvas to container width, maintain aspect ratio
      const container = containerRef.current;
      if (container) {
        const maxW = container.clientWidth;
        const ratio = img.height / img.width;
        const displayW = Math.min(maxW, img.width);
        const displayH = displayW * ratio;
        setCanvasSize({ width: displayW, height: displayH });
        setScale({
          x: img.width / displayW,
          y: img.height / displayH,
        });
      }
    };
    img.src = url;

    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  // ── Redraw canvas ──────────────────────────────────────────────────

  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imgElement) return;
    const ctx = canvas.getContext('2d');

    // Draw image
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(imgElement, 0, 0, canvas.width, canvas.height);

    // Draw saved zones
    pendingZones.forEach((z, i) => {
      ctx.strokeStyle = '#22c55e';
      ctx.lineWidth = 2;
      ctx.strokeRect(z.canvasX, z.canvasY, z.canvasW, z.canvasH);

      // Semi-transparent fill
      ctx.fillStyle = 'rgba(34, 197, 94, 0.1)';
      ctx.fillRect(z.canvasX, z.canvasY, z.canvasW, z.canvasH);

      // Label
      const label = z.zone_name || `Zone ${i + 1}`;
      ctx.font = '600 13px Inter, sans-serif';
      const textW = ctx.measureText(label).width;
      ctx.fillStyle = 'rgba(0,0,0,0.7)';
      ctx.fillRect(z.canvasX, z.canvasY - 22, textW + 12, 22);
      ctx.fillStyle = '#22c55e';
      ctx.fillText(label, z.canvasX + 6, z.canvasY - 6);
    });

    // Draw existing zones (from DB)
    existingZones.forEach((z) => {
      if (!scale || scale.x === 0 || scale.y === 0) return;
      const cx = z.x / scale.x;
      const cy = z.y / scale.y;
      const cw = z.width / scale.x;
      const ch = z.height / scale.y;

      ctx.strokeStyle = '#3b82f6'; // Blue for existing
      ctx.lineWidth = 2;
      ctx.strokeRect(cx, cy, cw, ch);

      ctx.fillStyle = 'rgba(59, 130, 246, 0.1)';
      ctx.fillRect(cx, cy, cw, ch);

      const label = z.zone_name;
      ctx.font = '600 13px Inter, sans-serif';
      const textW = ctx.measureText(label).width;
      ctx.fillStyle = 'rgba(0,0,0,0.7)';
      ctx.fillRect(cx, cy - 22, textW + 12, 22);
      ctx.fillStyle = '#3b82f6';
      ctx.fillText(label, cx + 6, cy - 6);
    });

    // Draw current rect being drawn
    if (currentRect) {
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = '#f0b429';
      ctx.lineWidth = 2;
      ctx.strokeRect(currentRect.x, currentRect.y, currentRect.w, currentRect.h);
      ctx.setLineDash([]);

      ctx.fillStyle = 'rgba(240, 180, 41, 0.08)';
      ctx.fillRect(currentRect.x, currentRect.y, currentRect.w, currentRect.h);
    }
  }, [imgElement, pendingZones, currentRect, existingZones, scale]);

  useEffect(() => {
    redraw();
  }, [redraw]);

  // ── Mouse handlers ─────────────────────────────────────────────────

  const getCanvasPos = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
  };

  const handleMouseDown = (e) => {
    if (namingIndex !== null) return; // don't draw while naming
    const pos = getCanvasPos(e);
    setIsDrawing(true);
    setStartPos(pos);
    setCurrentRect(null);
  };

  const handleMouseMove = (e) => {
    if (!isDrawing) return;
    const pos = getCanvasPos(e);
    const x = Math.min(startPos.x, pos.x);
    const y = Math.min(startPos.y, pos.y);
    const w = Math.abs(pos.x - startPos.x);
    const h = Math.abs(pos.y - startPos.y);
    setCurrentRect({ x, y, w, h });
  };

  const handleMouseUp = () => {
    if (!isDrawing) return;
    setIsDrawing(false);

    if (currentRect && currentRect.w > 10 && currentRect.h > 10) {
      // Add zone with canvas coords + real (scaled) coords
      const newZone = {
        canvasX: currentRect.x,
        canvasY: currentRect.y,
        canvasW: currentRect.w,
        canvasH: currentRect.h,
        // Scaled to original image dimensions
        x: Math.round(currentRect.x * scale.x),
        y: Math.round(currentRect.y * scale.y),
        width: Math.round(currentRect.w * scale.x),
        height: Math.round(currentRect.h * scale.y),
        zone_name: '',
        product_name: '',
      };
      setPendingZones((prev) => [...prev, newZone]);
      // Open naming form for this new zone
      setNamingIndex(pendingZones.length);
      setNameForm({ zone_name: '', product_name: '' });
    }
    setCurrentRect(null);
  };

  // ── Zone naming ────────────────────────────────────────────────────

  const confirmName = () => {
    if (namingIndex === null) return;
    setPendingZones((prev) => {
      const updated = [...prev];
      updated[namingIndex] = {
        ...updated[namingIndex],
        zone_name: nameForm.zone_name || `Zone ${namingIndex + 1}`,
        product_name: nameForm.product_name || 'Unassigned',
      };
      return updated;
    });
    setNamingIndex(null);
    setNameForm({ zone_name: '', product_name: '' });
  };

  const handleNameKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      confirmName();
    }
  };

  // ── Undo ───────────────────────────────────────────────────────────

  const undoLast = () => {
    setPendingZones((prev) => prev.slice(0, -1));
    if (namingIndex !== null && namingIndex >= pendingZones.length - 1) {
      setNamingIndex(null);
    }
  };

  // ── Save & Analyze ─────────────────────────────────────────────────

  const handleSave = () => {
    if (pendingZones.length === 0) return;

    // Make sure all zones are named (close any open form)
    let finalZones = pendingZones.map((z, i) => ({
      ...z,
      zone_name: z.zone_name || `Zone ${i + 1}`,
      product_name: z.product_name || 'Unassigned',
    }));

    onComplete({
      zones: finalZones.map((z) => ({
        zone_name: z.zone_name,
        product_name: z.product_name,
        x: z.x,
        y: z.y,
        width: z.width,
        height: z.height,
        full_threshold: 0.50,
        low_threshold: 0.15,
      })),
      imageFile,
    });
  };

  return (
    <div className="zone-drawer slide-up">
      <div className="zone-drawer-toolbar">
        <div className="zone-drawer-title">
          <Pencil size={15} />
          <span>Draw zones on the shelf image</span>
        </div>
        <div className="zone-drawer-actions">
          <span className="zone-drawer-count">{pendingZones.length} zone{pendingZones.length !== 1 ? 's' : ''}</span>
          <button className="btn btn-ghost btn-sm" onClick={undoLast} disabled={pendingZones.length === 0}>
            <Undo2 size={13} /> Undo
          </button>
          <button className="btn btn-ghost btn-sm" onClick={onCancel}>
            Cancel
          </button>
          <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={pendingZones.length === 0}>
            <Save size={13} /> Save Zones & Analyze
          </button>
        </div>
      </div>

      <div className="zone-drawer-hint">
        Click and drag to draw a rectangle. After drawing, name the zone. Repeat for each shelf section.
      </div>

      <div className="zone-drawer-canvas-container" ref={containerRef}>
        {canvasSize.width > 0 && (
          <canvas
            ref={canvasRef}
            width={canvasSize.width}
            height={canvasSize.height}
            className="zone-drawer-canvas"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={() => { if (isDrawing) { setIsDrawing(false); setCurrentRect(null); } }}
          />
        )}
      </div>

      {/* Naming form — appears after drawing a rectangle */}
      {namingIndex !== null && (
        <div className="zone-drawer-name-form fade-in">
          <span className="zone-drawer-name-label">Name Zone {namingIndex + 1}:</span>
          <input
            className="input"
            placeholder="Zone name (e.g. Zone A)"
            value={nameForm.zone_name}
            onChange={(e) => setNameForm({ ...nameForm, zone_name: e.target.value })}
            onKeyDown={handleNameKeyDown}
            autoFocus
          />
          <input
            className="input"
            placeholder="Product (e.g. Olpers Milk)"
            value={nameForm.product_name}
            onChange={(e) => setNameForm({ ...nameForm, product_name: e.target.value })}
            onKeyDown={handleNameKeyDown}
          />
          <button className="btn btn-primary btn-sm" onClick={confirmName}>
            Confirm
          </button>
        </div>
      )}

      {/* Zone list */}
      {pendingZones.length > 0 && (
        <div className="zone-drawer-list">
          {pendingZones.map((z, i) => (
            <div key={i} className="zone-drawer-list-item">
              <span className="zone-drawer-list-dot" />
              <span className="zone-drawer-list-name">{z.zone_name || `Zone ${i + 1}`}</span>
              <span className="zone-drawer-list-product">{z.product_name || 'Unassigned'}</span>
              <span className="zone-drawer-list-coords">{z.x},{z.y} — {z.width}×{z.height}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
