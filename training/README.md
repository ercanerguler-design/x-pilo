# Training Pipeline

This folder contains the model training and evaluation pipeline for real weed-vs-crop detection.

## Structure

- `config/dataset.yaml`: YOLO dataset config.
- `data/images/train`, `data/images/val`: training and validation images.
- `data/labels/train`, `data/labels/val`: YOLO label files.
- `scripts/train_yolo.py`: training and evaluation script.
- `reports/`: generated evaluation reports.

## Dataset Classes

The class order in dataset config is fixed:

1. `karpuz`
2. `kaktus`
3. `ot`
4. `belirsiz`

## Quick Start

```powershell
pip install ultralytics>=8.3.0
python train_yolo.py --data dataset.yaml --model yolov8n.pt --epochs 60
```

Alternative (inside training folder):

```powershell
python scripts/train_yolo.py --data config/dataset.yaml --model yolov8n.pt --epochs 60
```

Outputs:

- Best model path in `runs/detect/.../weights/best.pt`
- JSON summary in `training/reports/latest_eval.json`
- Markdown report in `training/reports/latest_eval.md`
- Label QC report in `training/reports/label_qc_report.json`
- Threshold tuning report in `training/reports/threshold_tuning.json`

## Label Quality Standardization

Run only label QC:

```powershell
python training/scripts/label_qc.py --data training/config/dataset.yaml --strict
```

This verifies:

- Class ids in range
- Normalized bbox values in [0,1]
- Matching image file exists for each label
- Empty or malformed label files

## Precision-Focused Threshold Tuning

After training, auto-tuning is run by default.
Manual execution:

```powershell
python training/scripts/tune_thresholds.py --data training/config/dataset.yaml --weights runs/detect/x-pilo-weeds/weights/best.pt
```

This writes recommended thresholds and updates `configs/mission.yaml` automatically.

## Production Rule

Backend hard rule blocks intervention for any target classified as `belirsiz`.
This safety rule must never be disabled in production.
