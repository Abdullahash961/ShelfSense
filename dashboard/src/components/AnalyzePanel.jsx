import { useState, useRef, useEffect } from 'react';
import { Upload, Loader, ImagePlus, PenTool } from 'lucide-react';
import { analyzeShelf, getZones, createZone, uploadReference } from '../api/client';
import ZoneDrawer from './ZoneDrawer';
import './AnalyzePanel.css';

export default function AnalyzePanel({ onSuccess, showToast }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  // Zone drawer state
  const [showDrawer, setShowDrawer] = useState(false);
  const [hasZones, setHasZones] = useState(null); // null = not checked yet
  const [existingZones, setExistingZones] = useState([]);

  // Check if zones exist when component mounts
  useEffect(() => {
    getZones()
      .then(async (zones) => {
        if (zones.length > 0) {
          setHasZones(true);
          setExistingZones(zones);
          const refImg = zones[0].reference_image;
          if (refImg) {
            try {
              const res = await fetch(`/references/${refImg}`);
              if (res.ok) {
                const blob = await res.blob();
                const f = new File([blob], refImg, { type: blob.type });
                setFile(f);
                const reader = new FileReader();
                reader.onload = (e) => setPreview(e.target.result);
                reader.readAsDataURL(f);
              }
            } catch (err) {
              console.error('Failed to load reference image', err);
            }
          }
        } else {
          setHasZones(false);
        }
      })
      .catch(() => setHasZones(false));
  }, []);

  const handleFile = (f) => {
    if (!f) return;
    setFile(f);
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target.result);
    reader.readAsDataURL(f);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('image/')) handleFile(f);
  };

  // When image is selected and no zones exist, auto-open drawer
  const handleAnalyzeClick = () => {
    if (!hasZones) {
      setShowDrawer(true);
    } else {
      runAnalysis(file);
    }
  };

  // Direct analysis (zones already exist)
  const runAnalysis = async (imageFile) => {
    if (!imageFile) return;
    setLoading(true);
    try {
      await analyzeShelf(imageFile);
      showToast('Analysis complete — results updated', 'success');
      // DO NOT clear the file so it remains remembered
      // setFile(null);
      // setPreview(null);
      setShowDrawer(false);
      onSuccess();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Zone drawer completed: save zones then analyze
  const handleDrawerComplete = async ({ zones, imageFile }) => {
    setLoading(true);
    try {
      let filename = null;
      // If the image is not already a saved reference image, upload it
      if (imageFile.name && imageFile.name.startsWith('empty_')) {
        filename = imageFile.name;
      } else {
        // Upload the image as a reference image
        const res = await uploadReference(imageFile);
        filename = res.filename;
      }

      // Save all zones to DB
      for (const zone of zones) {
        await createZone({ ...zone, reference_image: filename });
      }
      showToast(`${zones.length} zone(s) saved`, 'success');
      
      // Update existingZones state with new zones
      const updatedZones = await getZones();
      setExistingZones(updatedZones);

      // Now run analysis with the same image
      await analyzeShelf(imageFile);
      showToast('Analysis complete — results updated', 'success');

      // We don't clear the file/preview so the user can see their aisle picture
      setShowDrawer(false);
      setHasZones(true);
      onSuccess();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleDrawerCancel = () => {
    setShowDrawer(false);
  };

  const clear = () => {
    setFile(null);
    setPreview(null);
    setShowDrawer(false);
    if (inputRef.current) inputRef.current.value = '';
  };

  // ── Zone Drawer mode ───────────────────────────────────────────────

  if (showDrawer && file) {
    return (
      <div className="analyze-drawer-overlay fade-in">
        <div className="analyze-drawer-overlay-inner">
          <h2 className="section-title">Configure Zones & Analyze</h2>
          {loading ? (
            <div className="card" style={{ padding: '48px', textAlign: 'center' }}>
              <Loader size={24} className="spin" style={{ color: 'var(--accent)', marginBottom: '12px' }} />
              <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-size-sm)' }}>
                Saving zones and running analysis…
              </p>
            </div>
          ) : (
            <ZoneDrawer
              imageFile={file}
              existingZones={existingZones}
              onComplete={handleDrawerComplete}
              onCancel={handleDrawerCancel}
            />
          )}
        </div>
      </div>
    );
  }

  // ── Normal upload mode ─────────────────────────────────────────────

  return (
    <div className="section fade-in">
      <h2 className="section-title">Run Analysis</h2>
      <div className="card analyze-panel">
        <div
          className={`analyze-dropzone ${dragOver ? 'analyze-dropzone-active' : ''} ${preview ? 'analyze-dropzone-has-file' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          id="analyze-dropzone"
        >
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            onChange={(e) => handleFile(e.target.files[0])}
            hidden
          />
          {preview ? (
            <img src={preview} alt="Selected shelf" className="analyze-preview" />
          ) : (
            <div className="analyze-dropzone-content">
              <ImagePlus size={28} strokeWidth={1.5} />
              <span>Drop shelf image here or click to browse</span>
            </div>
          )}
        </div>

        <div className="analyze-actions">
          {file && (
            <button className="btn btn-ghost btn-sm" onClick={clear} disabled={loading}>
              Clear
            </button>
          )}

          {/* If zones exist, offer reconfigure option */}
          {file && hasZones && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setShowDrawer(true)}
              disabled={loading}
              title="Draw more zones on this image"
            >
              <PenTool size={13} />
              Add More Zones
            </button>
          )}

          <button
            className="btn btn-primary"
            onClick={handleAnalyzeClick}
            disabled={!file || loading}
            id="analyze-btn"
          >
            {loading ? (
              <>
                <Loader size={14} className="spin" />
                Analyzing…
              </>
            ) : !hasZones && file ? (
              <>
                <PenTool size={14} />
                Draw Zones & Analyze
              </>
            ) : (
              <>
                <Upload size={14} />
                Run Analysis
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
