from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


@dataclass(slots=True)
class QcIssue:
    level: str
    code: str
    file: str
    detail: str


def _iter_label_files(labels_dir: Path) -> Iterable[Path]:
    if not labels_dir.exists():
        return []
    return sorted(labels_dir.rglob("*.txt"))


def _corresponding_image(images_dir: Path, stem: str) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        p = images_dir / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def run_qc(data_yaml: Path) -> tuple[dict, list[QcIssue]]:
    cfg = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    data_root = (data_yaml.parent / cfg.get("path", "")).resolve() if not Path(str(cfg.get("path", ""))).is_absolute() else Path(cfg.get("path")).resolve()
    train_images = data_root / cfg.get("train", "images/train")
    val_images = data_root / cfg.get("val", "images/val")
    train_labels = data_root / "labels" / "train"
    val_labels = data_root / "labels" / "val"

    names = cfg.get("names", {})
    class_count = len(names) if isinstance(names, dict) else len(names or [])

    issues: list[QcIssue] = []

    def scan_split(split_name: str, images_dir: Path, labels_dir: Path) -> dict:
        split_stats = {
            "split": split_name,
            "image_dir": str(images_dir),
            "label_dir": str(labels_dir),
            "label_files": 0,
            "objects": 0,
            "empty_labels": 0,
        }

        if not images_dir.exists():
            issues.append(QcIssue("error", "MISSING_IMAGES_DIR", str(images_dir), "Image directory does not exist"))
        if not labels_dir.exists():
            issues.append(QcIssue("error", "MISSING_LABEL_DIR", str(labels_dir), "Label directory does not exist"))
            return split_stats

        for label_file in _iter_label_files(labels_dir):
            split_stats["label_files"] += 1
            image = _corresponding_image(images_dir, label_file.stem)
            if image is None:
                issues.append(QcIssue("warning", "MISSING_IMAGE", str(label_file), "No matching image file for label"))

            lines = [ln.strip() for ln in label_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if not lines:
                split_stats["empty_labels"] += 1
                issues.append(QcIssue("warning", "EMPTY_LABEL", str(label_file), "Label file is empty"))
                continue

            for idx, line in enumerate(lines, start=1):
                parts = line.split()
                if len(parts) != 5:
                    issues.append(QcIssue("error", "INVALID_FIELD_COUNT", str(label_file), f"Line {idx}: expected 5 values, got {len(parts)}"))
                    continue

                cls_raw, x_raw, y_raw, w_raw, h_raw = parts
                try:
                    cls = int(float(cls_raw))
                    x = float(x_raw)
                    y = float(y_raw)
                    w = float(w_raw)
                    h = float(h_raw)
                except Exception:
                    issues.append(QcIssue("error", "PARSE_ERROR", str(label_file), f"Line {idx}: non-numeric values"))
                    continue

                if cls < 0 or cls >= max(1, class_count):
                    issues.append(QcIssue("error", "CLASS_OUT_OF_RANGE", str(label_file), f"Line {idx}: class id {cls} out of range"))

                if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                    issues.append(QcIssue("error", "BOX_OUT_OF_RANGE", str(label_file), f"Line {idx}: normalized bbox values out of range"))

                split_stats["objects"] += 1

        return split_stats

    train_stats = scan_split("train", train_images, train_labels)
    val_stats = scan_split("val", val_images, val_labels)

    summary = {
        "data_yaml": str(data_yaml),
        "class_count": class_count,
        "train": train_stats,
        "val": val_stats,
        "errors": sum(1 for i in issues if i.level == "error"),
        "warnings": sum(1 for i in issues if i.level == "warning"),
    }
    return summary, issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YOLO dataset label quality check")
    parser.add_argument("--data", default="training/config/dataset.yaml")
    parser.add_argument("--report-json", default="training/reports/label_qc_report.json")
    parser.add_argument("--report-md", default="training/reports/label_qc_report.md")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any error exists")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary, issues = run_qc(Path(args.data))

    payload = {
        "summary": summary,
        "issues": [issue.__dict__ for issue in issues],
    }

    report_json = Path(args.report_json)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report_md = Path(args.report_md)
    report_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Label QC Report",
        "",
        f"Data: {summary['data_yaml']}",
        f"Errors: {summary['errors']}",
        f"Warnings: {summary['warnings']}",
        "",
        "## Split Stats",
        "",
        f"- Train label files: {summary['train']['label_files']}",
        f"- Train objects: {summary['train']['objects']}",
        f"- Val label files: {summary['val']['label_files']}",
        f"- Val objects: {summary['val']['objects']}",
        "",
        "## Issues",
        "",
    ]
    if not issues:
        lines.append("- No issues found.")
    else:
        for issue in issues[:400]:
            lines.append(f"- [{issue.level.upper()}] {issue.code} | {issue.file} | {issue.detail}")

    report_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Saved label QC json: {report_json}")
    print(f"Saved label QC md: {report_md}")

    if args.strict and summary["errors"] > 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
