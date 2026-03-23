from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and evaluate YOLO model for weed control")
    parser.add_argument("--data", default="training/config/dataset.yaml", help="YOLO dataset config path")
    parser.add_argument("--model", default="yolov8n.pt", help="Base model or checkpoint")
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--imgsz", type=int, default=1024)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--project", default="runs/detect")
    parser.add_argument("--name", default="x-pilo-weeds")
    parser.add_argument("--report-json", default="training/reports/latest_eval.json")
    parser.add_argument("--report-md", default="training/reports/latest_eval.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from ultralytics import YOLO  # type: ignore[import-not-found]
    except Exception as exc:
        raise SystemExit(
            "Ultralytics is required. Install with: pip install 'ultralytics>=8.3.0'"
        ) from exc

    model = YOLO(args.model)

    train_result = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        verbose=True,
    )

    val_result = model.val(data=args.data, imgsz=args.imgsz, batch=args.batch, device=args.device)

    metrics = {
        "precision": _to_float(getattr(val_result.box, "mp", 0.0)),
        "recall": _to_float(getattr(val_result.box, "mr", 0.0)),
        "map50": _to_float(getattr(val_result.box, "map50", 0.0)),
        "map50_95": _to_float(getattr(val_result.box, "map", 0.0)),
    }

    p = metrics["precision"]
    r = metrics["recall"]
    f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
    metrics["f1"] = f1

    report = {
        "generated_at": _utc_now(),
        "data": args.data,
        "model": args.model,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "run_dir": str(getattr(train_result, "save_dir", "")),
        "best_weights": str(Path(getattr(train_result, "save_dir", "")) / "weights" / "best.pt"),
        "metrics": metrics,
        "notes": [
            "Check confusion between karpuz and kaktus before enabling autonomous intervention.",
            "Keep backend hard rule for uncertain targets enabled.",
        ],
    }

    report_json_path = Path(args.report_json)
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    report_md_path = Path(args.report_md)
    report_md_path.parent.mkdir(parents=True, exist_ok=True)
    report_md_path.write_text(
        "\n".join(
            [
                "# Eval Report",
                "",
                f"Generated: {report['generated_at']}",
                f"Data: {report['data']}",
                f"Model: {report['model']}",
                f"Best Weights: {report['best_weights']}",
                "",
                "## Metrics",
                "",
                f"- Precision: {metrics['precision']:.4f}",
                f"- Recall: {metrics['recall']:.4f}",
                f"- mAP50: {metrics['map50']:.4f}",
                f"- mAP50-95: {metrics['map50_95']:.4f}",
                f"- F1: {metrics['f1']:.4f}",
                "",
                "## Safety Gate",
                "",
                "- Autonomous intervention must remain blocked for uncertain detections.",
                "- Manual review is required before production release.",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Saved report json: {report_json_path}")
    print(f"Saved report md: {report_md_path}")


if __name__ == "__main__":
    main()
