
<p align="center">
  <img src="./data/captures/dashboard-preview.png" alt="ShelfSense Dashboard" width="800"/>
</p>

<h1 align="center">ShelfSense</h1>

<p align="center">
  <strong>AI-Powered Shelf Occupancy Monitoring — for Any Warehouse, Any Industry</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/react-19-61DAFB?logo=react&logoColor=white" alt="React"/>
  <img src="https://img.shields.io/badge/fastapi-0.110+-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/opencv-4.8+-5C3EE8?logo=opencv&logoColor=white" alt="OpenCV"/>
  <img src="https://img.shields.io/badge/yolov8-ultralytics-FF6F00" alt="YOLOv8"/>
  <img src="https://img.shields.io/badge/license-proprietary-red" alt="License"/>
</p>

---

## What is ShelfSense?

**ShelfSense** is a fully automated, camera-based inventory monitoring system that uses computer vision and deep learning to track shelf occupancy in real time. It tells you *exactly* how full every shelf section is, alerts you when stock is running low, and keeps a running history of trends — all without any manual counting or barcode scanning.

> **Domain-Agnostic by Design.** While this deployment is configured for **grocery retail shelves**, ShelfSense's architecture is completely domain-agnostic. It works with any shelf, rack, or storage system — from retail stores to industrial warehouses, pharmaceutical storage, electronics inventory, and beyond. Simply point a camera at your shelves, map your zones, and go.

---

## Why ShelfSense?

| Pain Point | ShelfSense Solution |
|---|---|
| **Manual stock checks** waste hours of employee time | Fully automated — runs 24/7 with zero human intervention |
| **Out-of-stock items** cause lost sales (avg. 4% revenue loss) | Real-time LOW / EMPTY alerts the moment stock drops |
| **No visibility** into stock trends over time | Historical trend charts per zone with time-series analytics |
| **Expensive sensor solutions** (RFID, weight mats) | Camera-only — uses existing CCTV or a single $30 webcam |
| **Vendor lock-in** to proprietary shelf hardware | Works with any shelf type, any camera, any product |

---

## Key Features

### 📊 Occupancy Fill-Level Detection (High Accuracy)
The core strength of ShelfSense. A hybrid computer vision pipeline computes precise fill-level percentages for each shelf zone by comparing the current shelf state against empty-shelf reference images. The system uses three complementary analysis channels — structural similarity (SSIM), chromatic analysis (HSV), and intensity differencing — fused together for robust performance across varying lighting conditions, shadows, and camera angles.

### 🔢 Product Counting (Experimental)
An optional YOLOv8 deep learning model, fine-tuned on the SKU-110K dataset, detects and counts individual products within each zone. **Note:** Product count accuracy is actively being improved and may not be fully precise in all scenarios — particularly in densely packed shelves with small or overlapping items. The occupancy fill-level remains the primary and most reliable metric. Product counting serves as a complementary data point and is improving with each iteration.

### 🎯 Interactive Zone Mapping
A built-in HTML5 Canvas tool lets operators upload a shelf photo, draw custom rectangular zones, assign product names, and set per-zone restock thresholds — all from the browser. No configuration files to edit.

### 📈 Real-Time Analytics Dashboard
A premium React-based dashboard with:
- **Summary cards** — overall stock health at a glance (FULL / LOW / EMPTY counts)
- **Zone grid** — per-zone fill percentages with color-coded status indicators
- **Restocking alerts** — flagged items falling below customizable thresholds
- **Trend charts** — historical fill-level data visualized with Chart.js
- **Live camera feed** — real-time MJPEG stream from the connected camera

### 📷 Camera Integration & Scheduling
Supports USB webcams and IP cameras (RTSP). A background scheduler automatically captures frames and runs analysis at configurable intervals (default: every 5 minutes), with auto-reconnect on stream failure.

### 🔄 Real-Time Push Updates (WebSocket)
Dashboard clients receive instant updates via WebSocket — no polling. When an analysis cycle completes or system state changes, all connected dashboards update simultaneously.

### 🛡️ Resilient Image Processing
Automatic handling of real-world conditions:
- **ECC alignment** corrects camera drift/bumps between captures
- **CLAHE normalization** handles changing lighting (overhead lights, time of day)
- **Multi-reference support** — compare against multiple empty-shelf references to reduce false positives from shadows and reflections

---

## System Architecture

ShelfSense follows a clean, modular, three-tier architecture:

```
┌──────────────────────────────────────────────────────────────────┐
│                     React Dashboard (Vite)                       │
│  Zone Drawer · Summary Cards · Trend Charts · Camera Feed       │
│  Port 5173 ─── REST + WebSocket ──▶ Port 8000                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                               │
│  /api/zones · /api/analysis · /api/camera · /ws/status           │
│  Scheduler (APScheduler) · Static file serving                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
┌──────────┐ ┌───────────┐ ┌──────────────────┐
│ CV Core  │ │ YOLO      │ │ SQLite Database   │
│ Pipeline │ │ Counter   │ │ (zones, results,  │
│          │ │ (YOLOv8n) │ │  trend history)   │
└──────────┘ └───────────┘ └──────────────────────┘
```

### CV Pipeline Detail

```
Raw Frame ──▶ ImagePreprocessor ──▶ DissimilarityComputer ──▶ MorphologyRefiner
              │                     │                         │
              ├─ Gaussian Blur      ├─ SSIM (structural)      ├─ Otsu Threshold
              ├─ CLAHE Lighting     ├─ HSV (chromatic)        ├─ Open → Close
              └─ ECC Alignment      ├─ Intensity Diff         └─ Border Erosion
                                    └─ Weighted Fusion             │
                                                                   ▼
                                                          Occupancy Score (0–100%)
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | React 19 + Vite 6 | Interactive SPA dashboard |
| **Styling** | Vanilla CSS (dark theme) | Premium UI without framework overhead |
| **Charts** | Chart.js + react-chartjs-2 | Trend visualization |
| **Icons** | Lucide React | Consistent icon system |
| **Backend** | FastAPI + Uvicorn | High-performance async REST API |
| **CV Engine** | OpenCV 4.8+ | Image preprocessing, morphology, alignment |
| **Deep Learning** | YOLOv8 (Ultralytics) | Product detection and counting |
| **Training Data** | SKU-110K Dataset | 11,762 images of densely packed retail shelves |
| **Database** | SQLite + SQLAlchemy 2.0 | Zero-config persistent storage |
| **Scheduler** | APScheduler | Background analysis cycles |
| **Real-time** | WebSocket (FastAPI native) | Push updates to dashboards |
| **Config** | Pydantic Settings | Type-safe, env-overridable configuration |

---

## Getting Started

### Prerequisites

- **Python** 3.10+
- **Node.js** 18+
- A USB webcam or IP camera (optional — you can also analyze uploaded images)

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/your-org/ShelfSense.git
cd ShelfSense
```

**2. Backend setup**
```bash
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

**3. Frontend setup**
```bash
cd dashboard
npm install
cd ..
```

**4. (Optional) Place YOLO weights**

If you have trained weights, place them at `weights/best.pt`. See the [Training Guide](./training/README.md) for how to fine-tune on SKU-110K.

### Running

**Quick Start (Windows):**
Double-click `start_prototype.bat` — it launches both servers and opens the dashboard.

**Manual Start:**
```bash
# Terminal 1 — Backend (API on port 8000)
python -m uvicorn app:app --reload

# Terminal 2 — Frontend (Dashboard on port 5173)
cd dashboard
npm run dev
```

**Access:**
- 🖥️ Dashboard: [http://localhost:5173](http://localhost:5173)
- 📡 API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- 📖 ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## How It Works

### 1. Setup Your Shelf
Upload a photo of a **fully stocked shelf** as a reference, and a photo of an **empty shelf** as the baseline.

### 2. Map Your Zones
Use the interactive Zone Drawer to define rectangular regions on the shelf image. Give each zone a name (e.g., "Zone A"), assign a product label (e.g., "Milk"), and set custom LOW/EMPTY thresholds.

### 3. Run Analysis
Drop a current shelf photo into the Analyze panel — or let the automated scheduler capture and analyze on a timer. The CV pipeline compares the current state against the empty-shelf reference to compute fill levels.

### 4. Monitor & Act
The dashboard updates in real time with:
- Per-zone fill percentages and status (FULL / LOW / EMPTY)
- Product counts per zone (when YOLO is enabled)
- Restocking alerts for zones below threshold
- Historical trend data

---

## Configuration

All settings are centralized in `config.py` and can be overridden via environment variables (prefix: `SHELFSENSE_`) or a `.env` file.

| Setting | Default | Description |
|---|---|---|
| `FULL_THRESHOLD` | `0.50` | Fill score ≥ 50% → FULL status |
| `LOW_THRESHOLD` | `0.15` | Fill score ≥ 15% → LOW status |
| `ANALYSIS_INTERVAL_MINUTES` | `5` | Auto-analysis frequency |
| `CAMERA_SOURCE` | `0` | Webcam index or RTSP URL |
| `CAMERA_ENABLED` | `false` | Enable live camera integration |
| `YOLO_ENABLED` | `true` | Enable product counting module |
| `YOLO_CONFIDENCE` | `0.15` | Minimum YOLO detection confidence |

---

## Project Structure

```
ShelfSense/
├── app.py                       # FastAPI application entry point
├── config.py                    # Centralized configuration (Pydantic Settings)
├── requirements.txt             # Python dependencies
├── start_prototype.bat          # One-click launcher (Windows)
│
├── core/                        # Computer Vision pipeline
│   ├── analyzer.py              # Top-level orchestrator (ShelfAnalyzer)
│   ├── preprocessing.py         # Gaussian blur, CLAHE, ECC alignment
│   ├── dissimilarity.py         # SSIM + HSV + Intensity fusion
│   ├── morphology.py            # Thresholding, cleanup, occupancy scoring
│   ├── product_counter.py       # YOLOv8 product detection & counting
│   ├── camera.py                # Webcam / RTSP camera manager
│   ├── scheduler.py             # Background analysis scheduler (APScheduler)
│   └── ws_manager.py            # WebSocket push updates
│
├── api/                         # REST API routes
│   ├── analysis.py              # Analysis endpoints (trigger, results, trends)
│   ├── camera.py                # Camera control & MJPEG stream
│   ├── uploads.py               # Image upload handling
│   └── zones.py                 # Zone CRUD operations
│
├── models/                      # SQLAlchemy ORM models
│   └── database.py              # DB engine, session factory, table definitions
│
├── db/                          # Data access layer
│   └── repository.py            # Zone & Analysis repositories
│
├── dashboard/                   # React + Vite frontend
│   └── src/
│       ├── components/          # UI: ZoneDrawer, ZoneGrid, TrendChart,
│       │                        #     AlertsPanel, CameraPanel, etc.
│       ├── hooks/               # API interaction hooks
│       └── api/                 # API client utilities
│
├── training/                    # YOLO model training
│   ├── train_colab.ipynb        # Google Colab notebook (GPU training)
│   ├── train.py                 # Local training script
│   └── dataset.yaml             # SKU-110K dataset configuration
│
├── weights/                     # Trained model weights (best.pt)
├── data/                        # SQLite DB, shelf captures, references
├── diagnostics/                 # Diagnostic test outputs & annotated images
├── tools/                       # Utility scripts (migrations, etc.)
└── tests/                       # Test suite
```

---

## Adapting to Your Domain

ShelfSense is built to be **domain-agnostic**. Here's how to adapt it:

| Use Case | What to Change |
|---|---|
| **Grocery Store** | ✅ Ready out of the box (current config) |
| **Electronics Store** | Upload new reference images, map zones to SKUs |
| **Warehouse Racks** | Works with any rack layout — just draw zones on rack photos |
| **Pharmacy Shelves** | Same setup — label zones with medication names |
| **Hardware Store** | Supports large and small items equally |
| **Cold Storage / Fridges** | Works through glass doors with proper reference images |

**No code changes needed.** Just provide new reference images and draw your zones.

---

## API Reference

Full interactive documentation is auto-generated at `/docs` (Swagger) and `/redoc` (ReDoc) when the server is running.

### Core Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/analysis/upload-and-analyze` | Upload an image and run analysis |
| `GET` | `/api/analysis/latest` | Get the most recent analysis results |
| `GET` | `/api/analysis/trends` | Get historical trend data |
| `GET/POST` | `/api/zones` | List / create shelf zones |
| `POST` | `/api/camera/connect` | Connect to a camera source |
| `GET` | `/api/camera/feed` | Live MJPEG video stream |
| `POST` | `/api/scheduler/start` | Start automated analysis |
| `WS` | `/ws/status` | Real-time status push updates |

---

## Roadmap

- [ ] **Improved product counting accuracy** — active R&D on model fine-tuning and post-processing
- [ ] **Multi-camera support** — monitor multiple aisles simultaneously
- [ ] **Notification integrations** — Email, SMS, and webhook alerts (architecture ready)
- [ ] **Cloud deployment** — Docker containerization + cloud-hosted dashboard
- [ ] **Mobile companion app** — Push notifications for floor staff
- [ ] **Planogram compliance** — verify products are in the correct zone
- [ ] **Multi-store management** — centralized dashboard across locations

---

## License

This software is proprietary. All rights reserved. Contact us for licensing inquiries.

---

<p align="center">
  <strong>ShelfSense</strong> — See your shelves. Know your stock. Act before it's too late.
</p>
