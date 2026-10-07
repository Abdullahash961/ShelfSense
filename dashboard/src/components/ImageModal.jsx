import { useState, useRef } from 'react';
import { X } from 'lucide-react';
import './ImageModal.css';

export default function ImageModal({ zone, onClose }) {
  const [naturalSize, setNaturalSize] = useState(null);
  const imgRef = useRef(null);

  if (!zone || !zone.image_path) return null;

  const imageUrl = `/captures/${zone.image_path}`;

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose();
  };

  const handleImageLoad = (e) => {
    setNaturalSize({
      width: e.target.naturalWidth,
      height: e.target.naturalHeight
    });
  };

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-content image-modal">
        <div className="image-modal-header">
          <span className="image-modal-title">{zone.zone_name} - {zone.image_path}</span>
          <button
            className="btn btn-ghost btn-icon"
            onClick={onClose}
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>
        <div className="image-modal-body" style={{ position: 'relative' }}>
          <img
            ref={imgRef}
            src={imageUrl}
            alt="Shelf capture"
            className="image-full"
            onLoad={handleImageLoad}
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.parentElement.innerHTML =
                '<p style="color: var(--text-tertiary); padding: 48px;">Image not found</p>';
            }}
          />
          {naturalSize && zone.width > 0 && (
            <svg 
              className="zone-overlay-svg"
              viewBox={`0 0 ${naturalSize.width} ${naturalSize.height}`}
              preserveAspectRatio="none"
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                pointerEvents: 'none',
              }}
            >
              <rect
                x={zone.x}
                y={zone.y}
                width={zone.width}
                height={zone.height}
                fill="rgba(240, 180, 41, 0.2)"
                stroke="var(--accent)"
                strokeWidth="4"
              />
              <text
                x={zone.x + 8}
                y={zone.y + 24}
                fill="#000"
                fontSize="18"
                fontWeight="bold"
                style={{
                  paintOrder: 'stroke',
                  stroke: 'var(--accent)',
                  strokeWidth: '4px',
                  strokeLinecap: 'butt',
                  strokeLinejoin: 'miter'
                }}
              >
                {zone.zone_name}
              </text>
            </svg>
          )}
        </div>
      </div>
    </div>
  );
}
