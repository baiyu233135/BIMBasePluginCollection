# -*- coding: utf-8 -*-
"""统一病害模型训练脚本（桥梁 7 类 + 隧道映射数据）。

数据集：桥梁病害识别/datasets/bridge_tunnel_unified_yolo/data.yaml
初始权重：ultralytics 官方 COCO 预训练 yolov8n.pt（桥梁病害识别/models/yolov8n.pt）
训练输出：隧道病害识别/training/runs/unified_disease_yolov8n/

CPU 训练调优要点（相对上一轮 epochs=50/batch=4/无 early stopping）：
- epochs=100 + patience=30 早停，避免上一轮 best 出现在 epoch 38 后续却退化的问题
- batch=8、workers=4，充分利用 CPU
- YOLO 默认数据增强保持开启
"""
import argparse
import os

from ultralytics import YOLO

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))  # pythonplugin 根


def main():
    ap = argparse.ArgumentParser(description="统一病害识别模型训练（YOLOv8n, CPU）")
    ap.add_argument("--data", default=os.path.join(
        _ROOT, "桥梁病害识别", "datasets", "bridge_tunnel_unified_yolo", "data.yaml"))
    ap.add_argument("--weights", default=os.path.join(
        _ROOT, "桥梁病害识别", "models", "yolov8n.pt"))
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--patience", type=int, default=30)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--project", default=os.path.join(_HERE, "runs"))
    ap.add_argument("--name", default="unified_disease_yolov8n")
    args = ap.parse_args()

    model = YOLO(args.weights)
    model.train(
        data=args.data,
        epochs=args.epochs,
        patience=args.patience,
        batch=args.batch,
        imgsz=args.imgsz,
        workers=args.workers,
        device="cpu",
        project=args.project,
        name=args.name,
        exist_ok=True,
    )


if __name__ == "__main__":
    main()
