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
$env:PYTHONPATH="src"
python training/scripts/train_yolo.py --data training/config/dataset.yaml --model yolov8n.pt --epochs 60
```

Outputs:

- Best model path in `runs/detect/.../weights/best.pt`
- JSON summary in `training/reports/latest_eval.json`
- Markdown report in `training/reports/latest_eval.md`

## Production Rule

Backend hard rule blocks intervention for any target classified as `belirsiz`.
This safety rule must never be disabled in production.
