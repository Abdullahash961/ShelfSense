
# ShelfSense 🛒

**An Intelligent Retail Shelf Occupancy Monitoring System**

ShelfSense is an automated computer-vision based system designed to monitor retail shelves in real-time. It analyzes camera feeds to detect out-of-stock (OOS) items, tracks inventory levels across customized zones, and provides an interactive dashboard for store managers to prevent stockouts and optimize shelf layout.

![ShelfSense Dashboard](./data/captures/dashboard-preview.png)
*(Note: Replace this image placeholder with an actual screenshot of your dashboard before submission!)*

---

## 🎯 Key Features

1. **Intelligent Occupancy Pipeline**: Uses a hybrid Computer Vision approach (SSIM, HSV color analysis, and intensity masking) to calculate precise fill percentages for specific shelf zones without relying solely on computationally expensive deep learning models.
2. **Interactive Zone Mapping**: A built-in HTML5 Canvas tool allows users to upload a shelf photo, draw custom zones, name products, and define specific restock thresholds directly from the dashboard.
3. **Real-Time Analytics Dashboard**: A premium, React-based dashboard displaying overall stock health, low-stock alerts, and historical trend charts for every product zone.
4. **Resilient Alignment**: Automatically handles slight camera bumps or lighting shifts using Enhanced Correlation Coefficient (ECC) alignment and Contrast Limited Adaptive Histogram Equalization (CLAHE).

---

## 🏗️ System Architecture

ShelfSense follows a modular, decoupled architecture:

* **Backend (FastAPI)**: A high-performance Python REST API that handles all image processing, coordinates the SQLite database, and exposes data endpoints.
* **Core CV Pipeline (OpenCV)**: A multi-stage image processing engine (`ImagePreprocessor` ➔ `DissimilarityComputer` ➔ `MorphologyRefiner`) designed for robust real-world performance.
* **Frontend (React + Vite)**: A dynamic, single-page application built with React, styled with vanilla CSS (dark-theme optimized), and utilizing Chart.js for data visualization.

---

## 🚀 Quick Start Guide (For Evaluators)

To run the prototype seamlessly, you can use the provided quick-start script.

### Prerequisites
- Python 3.10+
- Node.js 18+

### Step 1: Install Dependencies

**Backend Setup:**
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # On Windows
pip install -r requirements.txt
```

**Frontend Setup:**
```bash
cd dashboard
npm install
cd ..
```

### Step 2: Run the Prototype

Simply double-click the **`start_prototype.bat`** file in the root directory. 
This script will automatically:
1. Start the FastAPI backend server on port 8000.
2. Start the React dashboard on port 5173.
3. Open your default web browser to the dashboard.

*Alternatively, run manually:*
- **Backend:** `python -m uvicorn app:app --reload`
- **Frontend:** `cd dashboard && npm run dev`

---

## 📖 How to Use the Dashboard

1. **Configure Zones:** Drag and drop an image of a fully-stocked shelf into the "Run Analysis" panel. If no zones exist, the Zone Drawer will open.
2. **Draw:** Click and drag to map rectangles over products. Assign a Name (e.g., "Zone A") and a Product (e.g., "Milk").
3. **Analyze:** Click "Save Zones & Analyze". The system will process the image, calculate occupancy percentages, and populate the dashboard.
4. **Manage Alerts:** Check the "Restocking Alerts" panel for any items falling below their defined `LOW` threshold (default 15%).

---

## 📁 Directory Structure

```text
ShelfSense/
├── app.py                   # FastAPI application entry point
├── config.py                # Global settings & paths
├── core/                    # Computer Vision pipeline modules
│   ├── analyzer.py
│   ├── dissimilarity.py
│   └── preprocessing.py
├── api/                     # REST API endpoints (routes)
├── db/                      # Database models and repository
├── dashboard/               # React Vite frontend application
│   ├── src/components/      # UI components (ZoneDrawer, Charts, etc.)
│   └── src/hooks/           # API interaction logic
├── scripts/                 # Utility scripts
└── data/                    # SQLite DB, shelf captures, and references
```

---
*Developed for Final Year Project (FYP) Submission.*
