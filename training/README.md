# YOLOv8 Product Counter — Training Guide

Fine-tune YOLOv8n on the **SKU-110K** dataset to count individual products on
densely packed retail shelves.

## Strategy

**SKU-110K** is a single-class dataset (every product = `"object"`).
This is perfect for ShelfSense because:

- Your zone config already maps each zone to a specific product name
- YOLO just needs to **count** how many items are in each zone
- Zone context provides the product identity — YOLO provides the count

## Workflow Overview

| Step | What                     | Where         | Time    |
|------|--------------------------|---------------|---------|
| 1    | Upload notebook to Drive | Google Drive  | 1 min   |
| 2    | Open in Colab            | Browser       | 1 min   |
| 3    | Set GPU + Run all        | Colab         | 30–60m  |
| 4    | Download trained model   | Drive → local | 1 min   |

## Step-by-Step

### 1. Upload the Notebook
Copy `training/train_colab.ipynb` to your Google Drive
(e.g., `My Drive/ShelfSense/`).

### 2. Open in Colab
In Google Drive, right-click the `.ipynb` file →
**Open with** → **Google Colaboratory**.

### 3. Configure GPU + Run
1. Go to **Runtime → Change runtime type → T4 GPU**
2. Click **Runtime → Run all**
3. The notebook will automatically:
   - Install `ultralytics`
   - Download the full SKU-110K dataset (~13.6 GB)
   - Train YOLOv8n for 50 epochs
   - Evaluate and visualize results
   - Save the model to your Google Drive

### 4. Download the Trained Model
After training completes:
1. Go to your Google Drive
2. Find `ShelfSense/yolov8n-shelfsense.pt`
3. Download it
4. Place it in your ShelfSense project root: `ShelfSense/yolov8n-shelfsense.pt`

## Expected Results

After training you should see:
- **mAP@0.5**: ~0.50–0.60 (good for dense retail shelves)
- **Precision**: ~0.55–0.65
- **Recall**: ~0.50–0.60

These numbers are typical for SKU-110K because products are tightly packed.
The model will still produce usable counts via confidence thresholding.

## After Training — Integration

Once you have `yolov8n-shelfsense.pt`:
1. Drop it in the project root
2. We'll integrate a `ProductCounter` module into the core pipeline
3. The analyzer will run YOLO inference per-zone alongside occupancy estimation
4. Results flow through the existing API → Dashboard

## Dataset Details

- **Name**: SKU-110K
- **Size**: ~11,762 images of retail shelves
- **Classes**: 1 (`object`)
- **Source**: Ultralytics auto-download (no manual download needed)
- **Paper**: Goldman et al., "Precise Detection in Densely Packed Scenes", CVPR 2019
