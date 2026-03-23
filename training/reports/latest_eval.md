# Latest Eval Report

Status: Not trained yet.

Run command:

```powershell
python training/scripts/train_yolo.py --data training/config/dataset.yaml --model yolov8n.pt --epochs 60
```

Expected metrics after run:

- mAP50
- mAP50-95
- precision
- recall
- f1
- confusion insights for `kaktus` vs `karpuz`
