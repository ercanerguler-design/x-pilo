from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import yaml
from PIL import Image


def _xywhn_to_xyxy(x: float, y: float, w: float, h: float, img_w: int, img_h: int) -> tuple[float, float, float, float]:
    bw = w * img_w
    bh = h * img_h
    cx = x * img_w
    cy = y * img_h
    x1 = cx - bw / 2.0
    y1 = cy - bh / 2.0
    x2 = cx + bw / 2.0
    y2 = cy + bh / 2.0
    return x1, y1, x2, y2


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    inter = w * h
    if inter <= 0:
        return 0.0
    area_a = max(0.0, (a[2] - a[0]) * (a[3] - a[1]))
    area_b = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
    denom = area_a + area_b - inter
    return 0.0 if denom <= 0 else inter / denom


def _load_dataset_paths(data_yaml: Path) -> tuple[Path, Path, Path]:
    cfg = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    root = Path(cfg.get("path", "training/data"))
    if not root.is_absolute():
        root = (data_yaml.parent / root).resolve()
    val_images = root / cfg.get("val", "images/val")
    val_labels = root / "labels" / "val"
    return root, val_images, val_labels


def _find_image(stem: str, image_dir: Path) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        p = image_dir / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def _load_ground_truth(val_labels_dir: Path, val_images_dir: Path) -> dict[str, list[tuple[int, np.ndarray]]]:
    out: dict[str, list[tuple[int, np.ndarray]]] = {}
    for label_file in sorted(val_labels_dir.glob("*.txt")):
        image_file = _find_image(label_file.stem, val_images_dir)
        if image_file is None:
            continue
        with Image.open(image_file) as im:
            img_w, img_h = im.size

        items: list[tuple[int, np.ndarray]] = []
        for line in label_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            cls = int(float(parts[0]))
            x, y, w, h = map(float, parts[1:])
            xyxy = np.array(_xywhn_to_xyxy(x, y, w, h, img_w, img_h), dtype=float)
            items.append((cls, xyxy))
        out[image_file.name] = items
    return out


def _collect_predictions(model, val_images_dir: Path, min_conf: float) -> dict[str, list[tuple[int, float, np.ndarray]]]:
    preds: dict[str, list[tuple[int, float, np.ndarray]]] = {}
    results = model.predict(source=str(val_images_dir), conf=min_conf, save=False, verbose=False)
    for result in results:
        name = Path(result.path).name
        boxes = result.boxes
        items: list[tuple[int, float, np.ndarray]] = []
        if boxes is not None and len(boxes) > 0:
            cls_arr = boxes.cls.cpu().numpy()
            conf_arr = boxes.conf.cpu().numpy()
            xyxy_arr = boxes.xyxy.cpu().numpy()
            for cls, conf, xyxy in zip(cls_arr, conf_arr, xyxy_arr):
                items.append((int(cls), float(conf), np.array(xyxy, dtype=float)))
        preds[name] = items
    return preds


def _evaluate_threshold(
    threshold: float,
    gt: dict[str, list[tuple[int, np.ndarray]]],
    pred: dict[str, list[tuple[int, float, np.ndarray]]],
    iou_thr: float,
) -> dict:
    tp = 0
    fp = 0
    fn = 0

    image_names = sorted(set(gt.keys()) | set(pred.keys()))
    for name in image_names:
        gt_items = gt.get(name, [])
        pred_items = [p for p in pred.get(name, []) if p[1] >= threshold]
        pred_items.sort(key=lambda x: x[1], reverse=True)

        used_gt: set[int] = set()
        for pred_cls, _pred_conf, pred_box in pred_items:
            best_idx = -1
            best_iou = 0.0
            for idx, (gt_cls, gt_box) in enumerate(gt_items):
                if idx in used_gt:
                    continue
                if gt_cls != pred_cls:
                    continue
                iou = _iou(pred_box, gt_box)
                if iou > best_iou:
                    best_iou = iou
                    best_idx = idx
            if best_idx >= 0 and best_iou >= iou_thr:
                tp += 1
                used_gt.add(best_idx)
            else:
                fp += 1

        fn += max(0, len(gt_items) - len(used_gt))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "threshold": round(float(threshold), 3),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune mission thresholds from validation predictions")
    parser.add_argument("--data", default="training/config/dataset.yaml")
    parser.add_argument("--weights", required=True, help="Path to best.pt")
    parser.add_argument("--min-recall", type=float, default=0.35)
    parser.add_argument("--iou-thr", type=float, default=0.5)
    parser.add_argument("--report-json", default="training/reports/threshold_tuning.json")
    parser.add_argument("--report-md", default="training/reports/threshold_tuning.md")
    parser.add_argument("--update-mission-config", default="configs/mission.yaml")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from ultralytics import YOLO  # type: ignore[import-not-found]
    except Exception as exc:
        raise SystemExit("Ultralytics is required for threshold tuning") from exc

    data_yaml = Path(args.data)
    _root, val_images, val_labels = _load_dataset_paths(data_yaml)

    if not val_images.exists() or not val_labels.exists():
        raise SystemExit("Validation images/labels not found for threshold tuning")

    model = YOLO(args.weights)
    gt = _load_ground_truth(val_labels, val_images)
    pred = _collect_predictions(model, val_images, min_conf=0.05)

    grid = [round(v, 2) for v in np.arange(0.2, 0.96, 0.05)]
    rows = [_evaluate_threshold(thr, gt, pred, iou_thr=args.iou_thr) for thr in grid]

    candidates = [r for r in rows if r["recall"] >= args.min_recall and r["tp"] > 0]
    if candidates:
        best = max(candidates, key=lambda r: (r["precision"], r["f1"], -r["threshold"]))
    else:
        best = max(rows, key=lambda r: (r["f1"], r["precision"]))

    action_conf = float(best["threshold"])
    precision_conf = min(0.99, action_conf + 0.08)
    min_conf = max(0.45, action_conf - 0.12)

    recommendation = {
        "min_confidence": round(min_conf, 3),
        "action_confidence": round(action_conf, 3),
        "precision_confidence": round(precision_conf, 3),
    }

    payload = {
        "best": best,
        "rows": rows,
        "recommendation": recommendation,
        "notes": [
            "Precision-first tuning selected to reduce false intervention risk.",
            "Keep uncertain-target hard-block enabled in backend.",
        ],
    }

    report_json = Path(args.report_json)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report_md = Path(args.report_md)
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text(
        "\n".join(
            [
                "# Threshold Tuning Report",
                "",
                f"Weights: {args.weights}",
                f"Data: {args.data}",
                "",
                "## Selected Threshold",
                "",
                f"- Threshold: {best['threshold']:.3f}",
                f"- Precision: {best['precision']:.4f}",
                f"- Recall: {best['recall']:.4f}",
                f"- F1: {best['f1']:.4f}",
                "",
                "## Mission Config Recommendation",
                "",
                f"- min_confidence: {recommendation['min_confidence']:.3f}",
                f"- action_confidence: {recommendation['action_confidence']:.3f}",
                f"- precision_confidence: {recommendation['precision_confidence']:.3f}",
            ]
        ),
        encoding="utf-8",
    )

    mission_cfg_path = Path(args.update_mission_config)
    if mission_cfg_path.exists():
        mission_cfg = yaml.safe_load(mission_cfg_path.read_text(encoding="utf-8"))
        mission_cfg.setdefault("thresholds", {})
        mission_cfg["thresholds"].update(recommendation)
        mission_cfg_path.write_text(yaml.safe_dump(mission_cfg, sort_keys=False), encoding="utf-8")

    print(f"Saved threshold tuning json: {report_json}")
    print(f"Saved threshold tuning md: {report_md}")


if __name__ == "__main__":
    main()
