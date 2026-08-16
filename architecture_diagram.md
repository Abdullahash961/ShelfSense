# ShelfSense — Architecture Design Diagram

> **Version**: 2.0 (OOP Refactored)  
> **Generated**: July 2026  
> **Purpose**: Visual reference for the full system architecture of the ShelfSense shelf-occupancy monitoring platform.

---

## 1. High-Level System Overview

A bird's-eye view of all major components and their relationships.

```mermaid
graph TB
    subgraph External["🌐 External"]
        CAM["📷 Camera / Image Source"]
        USER["👤 User / Operator"]
        DASH["📊 Dashboard Client"]
    end

    subgraph ShelfSense["🏗️ ShelfSense Platform"]
        direction TB

        subgraph EntryPoints["⚡ Entry Points"]
            MAIN["main.py<br/>CLI Analyser"]
            CFG_TOOL["configure_zones.py<br/>Zone Drawer GUI"]
            MIG_TOOL["tools/migrate_zones.py<br/>JSON → DB Migration"]
        end

        subgraph Config["⚙️ Configuration"]
            SETTINGS["config.py<br/>Settings (Pydantic)"]
            ENV[".env File<br/>Environment Overrides"]
            ZONES_JSON["zones.json<br/>Zone Definitions"]
        end

        subgraph CoreEngine["🧠 Core — CV Engine"]
            ANALYZER["ShelfAnalyzer<br/>Orchestrator"]
            PREPROC["ImagePreprocessor<br/>Smooth · CLAHE · ECC"]
            DISSIM["DissimilarityComputer<br/>SSIM · HSV · Intensity"]
            MORPH["MorphologyRefiner<br/>Otsu · Open/Close · Erode"]
        end

        subgraph DataLayer["💾 Data Layer"]
            direction TB
            SCHEMAS["schemas.py<br/>Pydantic Schemas"]
            ORM["database.py<br/>SQLAlchemy ORM"]
            REPO["repository.py<br/>Zone & Analysis Repos"]
            DB[("SQLite<br/>shelfsense.db")]
        end

        subgraph DataDirs["📁 File Storage"]
            REFS["data/references/<br/>Empty Shelf Photos"]
            CAPS["data/captures/<br/>Camera Snapshots"]
        end
    end

    %% External connections
    CAM -->|"capture frame"| CAPS
    USER -->|"draw zones"| CFG_TOOL
    USER -->|"run analysis"| MAIN
    DASH -->|"API requests"| SCHEMAS

    %% Entry point connections
    MAIN --> SETTINGS
    MAIN --> ANALYZER
    MAIN --> ZONES_JSON
    CFG_TOOL --> ZONES_JSON
    MIG_TOOL --> ZONES_JSON
    MIG_TOOL --> REPO

    %% Config connections
    ENV -.->|"overrides"| SETTINGS

    %% Core pipeline
    ANALYZER --> PREPROC
    ANALYZER --> DISSIM
    ANALYZER --> MORPH
    ANALYZER --> SETTINGS

    %% Data layer
    REPO --> ORM
    ORM --> DB
    ORM --> SETTINGS
    SCHEMAS -.->|"validates"| REPO

    %% File I/O
    MAIN -->|"reads"| REFS
    MAIN -->|"reads"| CAPS
    ANALYZER -->|"processes"| REFS
    ANALYZER -->|"processes"| CAPS

    %% Styling
    classDef external fill:#1e293b,stroke:#60a5fa,stroke-width:2px,color:#f1f5f9
    classDef entry fill:#164e63,stroke:#22d3ee,stroke-width:2px,color:#ecfeff
    classDef config fill:#3b0764,stroke:#c084fc,stroke-width:2px,color:#faf5ff
    classDef core fill:#14532d,stroke:#4ade80,stroke-width:2px,color:#f0fdf4
    classDef data fill:#7c2d12,stroke:#fb923c,stroke-width:2px,color:#fff7ed
    classDef storage fill:#1e3a5f,stroke:#7dd3fc,stroke-width:2px,color:#f0f9ff

    class CAM,USER,DASH external
    class MAIN,CFG_TOOL,MIG_TOOL entry
    class SETTINGS,ENV,ZONES_JSON config
    class ANALYZER,PREPROC,DISSIM,MORPH core
    class SCHEMAS,ORM,REPO,DB data
    class REFS,CAPS storage
```

---

## 2. Layered Architecture

The system follows a clean **4-layer architecture** with strict dependency direction (top → bottom).

```mermaid
graph TB
    subgraph L1["Layer 1 — Presentation & Entry"]
        direction LR
        CLI["🖥️ CLI<br/>main.py"]
        GUI["🖱️ Zone Drawer GUI<br/>configure_zones.py"]
        API["🌐 REST API<br/>(Future — FastAPI)"]
        DASHBOARD["📊 Dashboard<br/>(Future — Web UI)"]
    end

    subgraph L2["Layer 2 — Application / Business Logic"]
        direction LR
        SA["ShelfAnalyzer<br/>Orchestrates analysis"]
        ZD["ZoneDefinition<br/>Dataclass"]
        ZR["ZoneResult<br/>Dataclass"]
        CLASSIFY["classify()<br/>FULL · LOW · EMPTY"]
    end

    subgraph L3["Layer 3 — Core Processing Engines"]
        direction LR
        PP["ImagePreprocessor<br/>Gaussian · CLAHE · ECC"]
        DC["DissimilarityComputer<br/>SSIM · HSV · Intensity · Fuse"]
        MR["MorphologyRefiner<br/>Otsu · Open · Close · Erode"]
    end

    subgraph L4["Layer 4 — Data & Persistence"]
        direction LR
        ZREPO["ZoneRepository<br/>CRUD zones"]
        AREPO["AnalysisRepository<br/>Save & query results"]
        ORMM["ORM Models<br/>ZoneModel · AnalysisResultModel"]
        PYDANTIC["Pydantic Schemas<br/>ZoneCreate · ZoneResponse · ..."]
        DATABASE[("SQLite DB<br/>shelfsense.db")]
    end

    subgraph L5["Layer 5 — Infrastructure"]
        direction LR
        CONF["Settings<br/>config.py"]
        FS["File System<br/>data/ · zones.json"]
        OPENCV["OpenCV<br/>cv2"]
        SQLA["SQLAlchemy<br/>Engine · Session"]
    end

    L1 --> L2
    L2 --> L3
    L2 --> L4
    L3 --> L5
    L4 --> L5

    classDef layer1 fill:#0c4a6e,stroke:#38bdf8,stroke-width:2px,color:#e0f2fe
    classDef layer2 fill:#14532d,stroke:#4ade80,stroke-width:2px,color:#f0fdf4
    classDef layer3 fill:#713f12,stroke:#facc15,stroke-width:2px,color:#fefce8
    classDef layer4 fill:#7c2d12,stroke:#fb923c,stroke-width:2px,color:#fff7ed
    classDef layer5 fill:#3b0764,stroke:#c084fc,stroke-width:2px,color:#faf5ff

    class CLI,GUI,API,DASHBOARD layer1
    class SA,ZD,ZR,CLASSIFY layer2
    class PP,DC,MR layer3
    class ZREPO,AREPO,ORMM,PYDANTIC,DATABASE layer4
    class CONF,FS,OPENCV,SQLA layer5
```

---

## 3. CV Pipeline — Internal Architecture

Detailed view of the three-stage computer vision pipeline inside `core/`.

```mermaid
graph LR
    INPUT_CUR["📷 Current Frame<br/>(BGR)"]
    INPUT_REF["🖼️ Empty Reference<br/>(BGR)"]

    subgraph Stage1["Stage 1 — ImagePreprocessor"]
        direction TB
        S1A["Resize to Match"]
        S1B["Gaussian Blur<br/>k=5, suppress noise"]
        S1C["CLAHE<br/>LAB L-channel<br/>clip=2.0, grid=8×8"]
        S1D["ECC Alignment<br/>Translation model<br/>Corrects camera drift"]
        S1A --> S1B --> S1C --> S1D
    end

    subgraph Stage2["Stage 2 — DissimilarityComputer"]
        direction TB
        S2A["SSIM Channel<br/>Structural dissimilarity<br/>Gaussian window 11×11"]
        S2B["HSV Channel<br/>Hue (0.6) + Sat (0.4)<br/>Shadow-immune"]
        S2C["Intensity Channel<br/>Grayscale abs diff<br/>Brightness changes"]
        S2D["Pixel-wise MAX Fusion<br/>→ Fused Map [0,1]"]
        S2A --> S2D
        S2B --> S2D
        S2C --> S2D
    end

    subgraph Stage3["Stage 3 — MorphologyRefiner"]
        direction TB
        S3A["Otsu Thresholding<br/>Adaptive binary mask<br/>Floor = 30/255"]
        S3B["OPEN<br/>Small ellipse kernel<br/>3% of min dim<br/>Removes speckle noise"]
        S3C["CLOSE<br/>Large ellipse kernel<br/>8% of min dim<br/>Fills product gaps"]
        S3D["Border Erosion<br/>3% margin<br/>Ignores shelf edges"]
        S3E["Occupancy Ratio<br/>occupied / valid pixels<br/>→ score ∈ [0, 1]"]
        S3A --> S3B --> S3C --> S3D --> S3E
    end

    CLASSIFY_BOX["📋 Classification<br/>≥50% → FULL<br/>≥15% → LOW<br/>&lt;15% → EMPTY"]

    INPUT_CUR --> Stage1
    INPUT_REF --> Stage1
    Stage1 -->|"preprocessed pair"| Stage2
    Stage2 -->|"fused dissimilarity map"| Stage3
    Stage3 -->|"occupancy score"| CLASSIFY_BOX

    classDef input fill:#1e293b,stroke:#60a5fa,stroke-width:2px,color:#f1f5f9
    classDef stage1 fill:#164e63,stroke:#22d3ee,stroke-width:2px,color:#ecfeff
    classDef stage2 fill:#14532d,stroke:#4ade80,stroke-width:2px,color:#f0fdf4
    classDef stage3 fill:#713f12,stroke:#facc15,stroke-width:2px,color:#fefce8
    classDef output fill:#7c2d12,stroke:#fb923c,stroke-width:2px,color:#fff7ed

    class INPUT_CUR,INPUT_REF input
    class S1A,S1B,S1C,S1D stage1
    class S2A,S2B,S2C,S2D stage2
    class S3A,S3B,S3C,S3D,S3E stage3
    class CLASSIFY_BOX output
```

---

## 4. Data Model (ERD)

Entity-Relationship diagram showing the database schema and table relationships.

```mermaid
erDiagram
    ZONES ||--o{ ANALYSIS_RESULTS : "has many"

    ZONES {
        int id PK "AUTO INCREMENT"
        string zone_name "NOT NULL"
        string product_name "DEFAULT 'Unassigned'"
        int x "NOT NULL"
        int y "NOT NULL"
        int width "NOT NULL"
        int height "NOT NULL"
        float full_threshold "DEFAULT 0.50"
        float low_threshold "DEFAULT 0.15"
        string reference_image "NULLABLE"
        datetime created_at "UTC timestamp"
    }

    ANALYSIS_RESULTS {
        int id PK "AUTO INCREMENT"
        int zone_id FK "CASCADE DELETE"
        float fill_score "0.0 to 1.0"
        string status "FULL | LOW | EMPTY"
        string image_path "NULLABLE"
        datetime analyzed_at "UTC timestamp"
    }
```

---

## 5. Data Flow — End-to-End Analysis Run

Complete data flow from image capture through to persisted results.

```mermaid
flowchart TB
    START(["🚀 Start Analysis"])

    subgraph Input["📥 Input Collection"]
        LOAD_ZONES["Load Zone Definitions<br/>from DB or zones.json"]
        LOAD_CUR["Load Current Frame<br/>from data/captures/"]
        LOAD_REF["Load Empty Reference<br/>from data/references/"]
    end

    subgraph FullImg["🖼️ Full-Image Preparation"]
        RESIZE["Resize Current → Reference dims"]
        ALIGN_FULL["ECC Align (full image)<br/>Corrects camera drift"]
    end

    subgraph PerZone["🔁 Per-Zone Loop"]
        CROP["Crop zone from both images<br/>current[y:y+h, x:x+w]"]
        
        subgraph Pipeline["CV Pipeline"]
            PRE["Preprocess<br/>Smooth → CLAHE → Align"]
            DISS["Compute Dissimilarity<br/>SSIM ∪ HSV ∪ Intensity"]
            REFINE["Morphological Refinement<br/>Threshold → Clean → Erode"]
        end

        SCORE["Occupancy Score<br/>0.0 – 1.0"]
        STATUS["Classify<br/>FULL · LOW · EMPTY"]
        RESULT["Build ZoneResult"]
    end

    subgraph Output["📤 Output"]
        CONSOLE["Print Summary Table<br/>to Terminal"]
        ANNOTATE["Draw Annotated Image<br/>Coloured overlays + labels"]
        SAVE_IMG["Save zone_output.jpg"]
        JSON_OUT["JSON Payload<br/>Dashboard-ready"]
        DB_SAVE["Save to Database<br/>via AnalysisRepository"]
    end

    DONE(["✅ Complete"])

    START --> Input
    LOAD_ZONES --> FullImg
    LOAD_CUR --> FullImg
    LOAD_REF --> FullImg
    RESIZE --> ALIGN_FULL
    ALIGN_FULL --> PerZone
    CROP --> PRE --> DISS --> REFINE --> SCORE --> STATUS --> RESULT
    RESULT --> Output
    CONSOLE --> DONE
    ANNOTATE --> SAVE_IMG --> DONE
    JSON_OUT --> DONE
    DB_SAVE --> DONE

    classDef start fill:#14532d,stroke:#4ade80,stroke-width:3px,color:#f0fdf4
    classDef input fill:#1e3a5f,stroke:#7dd3fc,stroke-width:2px,color:#f0f9ff
    classDef prep fill:#164e63,stroke:#22d3ee,stroke-width:2px,color:#ecfeff
    classDef pipeline fill:#713f12,stroke:#facc15,stroke-width:2px,color:#fefce8
    classDef output fill:#7c2d12,stroke:#fb923c,stroke-width:2px,color:#fff7ed
    classDef done fill:#14532d,stroke:#4ade80,stroke-width:3px,color:#f0fdf4

    class START start
    class LOAD_ZONES,LOAD_CUR,LOAD_REF input
    class RESIZE,ALIGN_FULL prep
    class CROP,PRE,DISS,REFINE,SCORE,STATUS,RESULT pipeline
    class CONSOLE,ANNOTATE,SAVE_IMG,JSON_OUT,DB_SAVE output
    class DONE done
```

---

## 6. Module Dependency Graph

Shows which modules import from which — useful for understanding coupling.

```mermaid
graph BT
    CONFIG["config.py<br/>Settings"]

    subgraph core_pkg["core/"]
        CORE_INIT["__init__.py"]
        ANALYZER["analyzer.py<br/>ShelfAnalyzer"]
        PREPROC["preprocessing.py<br/>ImagePreprocessor"]
        DISSIM["dissimilarity.py<br/>DissimilarityComputer"]
        MORPHO["morphology.py<br/>MorphologyRefiner"]
    end

    subgraph models_pkg["models/"]
        MOD_INIT["__init__.py"]
        DATABASE["database.py<br/>ORM + Engine"]
        SCHEMAS["schemas.py<br/>Pydantic Models"]
    end

    subgraph db_pkg["db/"]
        DB_INIT["__init__.py"]
        REPO["repository.py<br/>Repositories"]
    end

    subgraph tools_pkg["tools/"]
        MIGRATE["migrate_zones.py"]
    end

    MAIN["main.py<br/>CLI Entry"]
    CFG_ZONES["configure_zones.py<br/>Zone GUI"]

    %% Core internal deps
    CORE_INIT --> ANALYZER
    ANALYZER --> PREPROC
    ANALYZER --> DISSIM
    ANALYZER --> MORPHO
    ANALYZER --> CONFIG

    %% Data layer deps
    DATABASE --> CONFIG
    REPO --> DATABASE

    %% Tools deps
    MIGRATE --> DATABASE
    MIGRATE --> REPO

    %% Entry point deps
    MAIN -.->|"uses (legacy)"| CONFIG

    %% External libraries (implied)

    classDef config fill:#3b0764,stroke:#c084fc,stroke-width:2px,color:#faf5ff
    classDef core fill:#14532d,stroke:#4ade80,stroke-width:2px,color:#f0fdf4
    classDef models fill:#7c2d12,stroke:#fb923c,stroke-width:2px,color:#fff7ed
    classDef db fill:#713f12,stroke:#facc15,stroke-width:2px,color:#fefce8
    classDef tools fill:#164e63,stroke:#22d3ee,stroke-width:2px,color:#ecfeff
    classDef entry fill:#1e293b,stroke:#60a5fa,stroke-width:2px,color:#f1f5f9

    class CONFIG config
    class CORE_INIT,ANALYZER,PREPROC,DISSIM,MORPHO core
    class MOD_INIT,DATABASE,SCHEMAS models
    class DB_INIT,REPO db
    class MIGRATE tools
    class MAIN,CFG_ZONES entry
```

---

## 7. Directory Structure

```
ShelfSense/
├── main.py                     # CLI entry point (legacy monolith)
├── config.py                   # Centralized settings (Pydantic)
├── configure_zones.py          # Interactive zone drawing tool (OpenCV GUI)
├── zones.json                  # Zone definitions (legacy flat file)
├── requirements.txt            # Python dependencies
│
├── core/                       # 🧠 Computer Vision Engine
│   ├── __init__.py             #   Exports ShelfAnalyzer
│   ├── analyzer.py             #   Orchestrator (composes the 3 stages)
│   ├── preprocessing.py        #   Stage 1: Smooth → CLAHE → ECC Align
│   ├── dissimilarity.py        #   Stage 2: SSIM · HSV · Intensity → Fuse
│   └── morphology.py           #   Stage 3: Otsu → Open/Close → Border Erode
│
├── models/                     # 💾 Data Definitions
│   ├── __init__.py
│   ├── database.py             #   SQLAlchemy ORM models + engine setup
│   └── schemas.py              #   Pydantic request/response schemas
│
├── db/                         # 🗄️ Repository Layer
│   ├── __init__.py
│   └── repository.py           #   ZoneRepository + AnalysisRepository
│
├── tools/                      # 🔧 Utilities
│   ├── __init__.py
│   └── migrate_zones.py        #   One-time JSON → SQLite migration
│
├── tests/                      # ✅ Test Suite
│   ├── __init__.py
│   ├── test_analyzer.py        #   CV pipeline unit tests
│   └── test_repository.py      #   Database CRUD tests
│
└── data/                       # 📁 Runtime Data
    ├── references/             #   Empty shelf reference photos
    ├── captures/               #   Camera snapshot storage
    └── shelfsense.db           #   SQLite database (auto-created)
```

---

## 8. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Language** | Python 3.12+ | Core runtime |
| **CV Engine** | OpenCV (cv2) | Image processing, SSIM, morphology, ECC alignment |
| **Numerical** | NumPy | Array operations, matrix math |
| **ORM** | SQLAlchemy 2.x | Database abstraction, model mapping |
| **Database** | SQLite 3 | Lightweight embedded storage |
| **Config** | Pydantic Settings | Type-safe configuration with `.env` support |
| **Validation** | Pydantic v2 | Request/response schema validation |
| **Testing** | pytest | Unit and integration testing |
| **Object Detection** | YOLOv8 (ultralytics) | Pre-trained model available (`yolov8n.pt`) |

---

## 9. Design Principles

```mermaid
mindmap
  root(("🏗️ ShelfSense<br/>Architecture"))
    ("🔌 Dependency Injection")
      ("ShelfAnalyzer accepts<br/>custom components")
      ("Easy to swap algorithms")
      ("Mockable for testing")
    ("📐 Separation of Concerns")
      ("Preprocessing ≠ Dissimilarity ≠ Morphology")
      ("ORM ≠ Repository ≠ Schema")
      ("Config isolated from logic")
    ("🧱 Layered Architecture")
      ("Presentation → Business → Core → Data")
      ("Strict top-down dependency")
      ("No circular imports")
    ("🔄 Pipeline Pattern")
      ("Composable stages")
      ("Each stage is testable")
      ("Clear data contracts")
    ("⚙️ Configuration-Driven")
      ("All thresholds externalized")
      ("Env vars override defaults")
      ("Per-zone threshold support")
```
