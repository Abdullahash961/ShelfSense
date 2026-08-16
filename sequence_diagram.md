# ShelfSense — Sequence Diagrams

## 1. Main Shelf Analysis Pipeline

The primary flow: analyzing a shelf image against an empty reference to determine zone occupancy.

```mermaid
sequenceDiagram
    actor User
    participant Main as main.py
    participant SA as ShelfAnalyzer
    participant PP as ImagePreprocessor
    participant DC as DissimilarityComputer
    participant MR as MorphologyRefiner
    participant Config as Settings

    User->>Main: Run analysis
    Main->>Main: Load zones.json
    Main->>Main: cv2.imread(current_image)
    Main->>Main: cv2.imread(empty_reference)

    Main->>SA: analyze_shelf(current_img, ref_img, zones)
    
    Note over SA: Resize current to match reference if needed
    SA->>PP: align(current_image, reference_image)
    
    activate PP
    PP->>PP: cvtColor → Grayscale
    PP->>PP: findTransformECC(ref, current)
    PP->>PP: warpAffine(current, warp_matrix)
    PP-->>SA: aligned_image
    deactivate PP

    loop For each ZoneDefinition
        SA->>SA: Crop zone from current & reference
        SA->>SA: analyze_zone(zone_crop, ref_crop)

        SA->>PP: preprocess(zone_crop, ref_crop)
        activate PP
        PP->>PP: smooth(zone) — Gaussian blur
        PP->>PP: smooth(ref) — Gaussian blur
        PP->>PP: normalize_lighting(zone) — CLAHE on LAB L-channel
        PP->>PP: normalize_lighting(ref) — CLAHE on LAB L-channel
        PP->>PP: align(zone, ref) — ECC alignment
        PP-->>SA: (processed_zone, processed_ref)
        deactivate PP

        SA->>DC: compute_all(proc_zone, proc_ref)
        activate DC
        DC->>DC: ssim(gray_zone, gray_ref) → DSSIM map
        DC->>DC: color_hsv(zone, ref) → Chromatic dissimilarity
        DC->>DC: intensity(zone, ref) → Grayscale diff
        DC->>DC: fuse([dssim, color, intensity]) → pixel-wise max
        DC-->>SA: fused_dissimilarity_map
        deactivate DC

        SA->>MR: refine(fused_map)
        activate MR
        MR->>MR: threshold(fused_map) — Otsu + min floor
        MR->>MR: cleanup(binary) — OPEN then CLOSE
        MR->>MR: erode_borders(cleaned) — ignore shelf edges
        MR->>MR: Calculate occupancy ratio
        MR-->>SA: occupancy_score (0.0 – 1.0)
        deactivate MR

        SA->>SA: classify(score) → "FULL" / "LOW" / "EMPTY"
        SA->>SA: Append ZoneResult
    end

    SA-->>Main: list[ZoneResult]
    Main->>Main: Print results table
    Main->>SA: draw_results(image, results)
    SA-->>Main: annotated_image
    Main->>Main: cv2.imwrite(output)
    Main-->>User: Console output + annotated image
```

---

## 2. Zone Configuration Flow

Interactive tool for drawing zones on a shelf reference image.

```mermaid
sequenceDiagram
    actor User
    participant CZ as configure_zones.py
    participant CV as OpenCV Window
    participant FS as File System

    User->>CZ: Run script
    CZ->>FS: cv2.imread(reference_image)
    CZ->>CV: namedWindow("Draw zones")
    CZ->>CV: setMouseCallback(on_mouse)

    loop Interactive Drawing Loop
        CV->>CZ: Mouse events (LBUTTONDOWN → MOUSEMOVE → LBUTTONUP)
        CZ->>CZ: Update current_rect coordinates
        CZ->>CV: Render overlay (existing zones + active rect)

        alt User presses Enter
            CZ->>User: Prompt for zone name
            User->>CZ: "Zone A"
            CZ->>User: Prompt for product name
            User->>CZ: "Olpers Milk"
            CZ->>CZ: Append zone to list
        else User presses 'u'
            CZ->>CZ: Pop last zone (undo)
        else User presses 's'
            CZ->>FS: Write zones.json
        else User presses 'q'
            CZ->>FS: Write zones.json (if zones exist)
            CZ->>CV: destroyAllWindows()
        end
    end

    CZ-->>User: zones.json saved
```

---

## 3. Zone Migration Flow (JSON → SQLite)

One-time migration of zone definitions from `zones.json` into the database.

```mermaid
sequenceDiagram
    actor User
    participant MZ as migrate_zones.py
    participant FS as File System
    participant DB as init_db()
    participant ZR as ZoneRepository
    participant Session as SQLAlchemy Session

    User->>MZ: python -m tools.migrate_zones
    MZ->>FS: Read zones.json
    FS-->>MZ: JSON data (reference_image, zones[])

    MZ->>DB: init_db()
    DB->>DB: Base.metadata.create_all()
    Note over DB: Creates zones & analysis_results tables if missing

    MZ->>Session: SessionLocal()
    MZ->>ZR: ZoneRepository(session)

    loop For each zone in JSON
        MZ->>Session: Query ZoneModel by zone_name
        alt Zone already exists
            MZ->>MZ: Skip (log "already exists")
        else Zone is new
            MZ->>ZR: create(zone_name, product_name, x, y, ...)
            ZR->>Session: session.add(ZoneModel)
            ZR->>Session: session.flush()
            Session-->>ZR: zone.id assigned
            ZR-->>MZ: ZoneModel
        end
    end

    MZ->>Session: session.commit()
    MZ->>Session: session.close()
    MZ-->>User: "Done: N imported, M skipped"
```

---

## 4. Database CRUD Operations

How the repository layer mediates all database interactions.

```mermaid
sequenceDiagram
    participant Caller as Application Code
    participant ZR as ZoneRepository
    participant AR as AnalysisRepository
    participant Session as SQLAlchemy Session
    participant SQLite as SQLite DB

    Note over Caller,SQLite: ── Zone CRUD ──

    Caller->>ZR: get_all()
    ZR->>Session: query(ZoneModel).order_by(id).all()
    Session->>SQLite: SELECT * FROM zones ORDER BY id
    SQLite-->>Session: Rows
    Session-->>ZR: list[ZoneModel]
    ZR-->>Caller: list[ZoneModel]

    Caller->>ZR: create(zone_name="Zone A", x=0, ...)
    ZR->>Session: session.add(ZoneModel)
    ZR->>Session: session.flush()
    Session->>SQLite: INSERT INTO zones (...) VALUES (...)
    SQLite-->>Session: id = auto-assigned
    Session-->>ZR: ZoneModel with id
    ZR-->>Caller: ZoneModel

    Caller->>ZR: update(zone_id=1, product_name="New Product")
    ZR->>Session: session.get(ZoneModel, 1)
    ZR->>ZR: setattr(zone, "product_name", "New Product")
    ZR->>Session: session.flush()
    Session->>SQLite: UPDATE zones SET product_name=... WHERE id=1
    ZR-->>Caller: Updated ZoneModel

    Caller->>ZR: delete(zone_id=1)
    ZR->>Session: session.get(ZoneModel, 1)
    ZR->>Session: session.delete(zone)
    ZR->>Session: session.flush()
    Session->>SQLite: DELETE FROM zones WHERE id=1
    ZR-->>Caller: True

    Note over Caller,SQLite: ── Analysis Results ──

    Caller->>AR: save_batch(results_list)
    AR->>Session: session.add_all(AnalysisResultModel[])
    AR->>Session: session.flush()
    Session->>SQLite: INSERT INTO analysis_results ...
    AR-->>Caller: list[AnalysisResultModel]

    Caller->>AR: get_latest()
    AR->>Session: Subquery: MAX(analyzed_at) GROUP BY zone_id
    AR->>Session: JOIN back for full rows
    Session->>SQLite: SELECT ... (subquery join)
    SQLite-->>Session: Latest result per zone
    AR-->>Caller: list[AnalysisResultModel]

    Caller->>AR: get_alerts(["LOW", "EMPTY"])
    AR->>AR: get_latest()
    AR->>AR: Filter by status ∈ {"LOW", "EMPTY"}
    AR-->>Caller: list[AnalysisResultModel] (needs attention)
```

---

## 5. CV Pipeline Detail — Single Zone Processing

A deeper look at the image processing stages within `analyze_zone`.

```mermaid
sequenceDiagram
    participant AZ as analyze_zone()
    participant Smooth as GaussianBlur
    participant CLAHE as CLAHE (LAB)
    participant ECC as ECC Alignment
    participant SSIM as SSIM Channel
    participant HSV as HSV Channel
    participant Intensity as Intensity Channel
    participant Fuse as Pixel-wise Max
    participant Otsu as Otsu Threshold
    participant Morph as Morphology Ops
    participant Border as Border Erosion

    AZ->>Smooth: GaussianBlur(zone, 5×5)
    Smooth-->>AZ: zone_smooth
    AZ->>Smooth: GaussianBlur(ref, 5×5)
    Smooth-->>AZ: ref_smooth

    AZ->>CLAHE: BGR → LAB → CLAHE(L) → LAB → BGR (zone)
    CLAHE-->>AZ: zone_normalized
    AZ->>CLAHE: BGR → LAB → CLAHE(L) → LAB → BGR (ref)
    CLAHE-->>AZ: ref_normalized

    AZ->>ECC: findTransformECC(ref_gray, zone_gray)
    ECC-->>AZ: warp_matrix
    AZ->>ECC: warpAffine(zone, warp_matrix)
    ECC-->>AZ: zone_aligned

    par Three Dissimilarity Channels
        AZ->>SSIM: DSSIM(gray_zone, gray_ref)
        Note over SSIM: Gaussian-weighted μ, σ² stats<br/>SSIM map → DSSIM = (1-SSIM)/2
        SSIM-->>AZ: dssim_map [0,1]

        AZ->>HSV: color_hsv(zone, ref)
        Note over HSV: Circular hue diff + sat diff<br/>0.6×hue + 0.4×sat
        HSV-->>AZ: color_map [0,1]

        AZ->>Intensity: abs(gray_zone - gray_ref) / 255
        Intensity-->>AZ: intensity_map [0,1]
    end

    AZ->>Fuse: max(dssim, color, intensity)
    Fuse-->>AZ: fused_map [0,1]

    AZ->>Otsu: threshold(fused_u8, OTSU)
    Note over Otsu: Floor at min_threshold=30<br/>if Otsu picks too low
    Otsu-->>AZ: binary_mask (0 or 255)

    AZ->>Morph: OPEN (small ellipse kernel) — remove noise
    Morph-->>AZ: cleaned_mask
    AZ->>Morph: CLOSE (large ellipse kernel) — fill gaps
    Morph-->>AZ: filled_mask

    AZ->>Border: Zero border pixels (3% margin)
    Border-->>AZ: refined_mask + border_mask

    AZ->>AZ: occupancy = mean(refined > 0) within valid pixels
    Note over AZ: Returns float ∈ [0.0, 1.0]
```
