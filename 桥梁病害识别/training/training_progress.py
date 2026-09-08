# -*- coding: utf-8 -*-
"""
YOLO 病害检测训练进度报告脚本

读取 ultralytics 训练生成的 results.csv，实时显示：
- 当前 epoch 和总 epoch
- 训练/验证损失
- mAP50、mAP50-95、Precision、Recall
- 预计剩余时间
- 最佳模型路径

使用方式：
    python training_progress.py
    python training_progress.py --run-dir runs/models/disease_yolov8n
"""

import os
import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime, timedelta


def parse_args():
    parser = argparse.ArgumentParser(description="YOLO 训练进度报告")
    parser.add_argument("--run-dir", default="runs/models/disease_yolov8n",
                        help="训练输出目录 (默认: runs/models/disease_yolov8n)")
    parser.add_argument("--refresh", type=int, default=0,
                        help="自动刷新间隔秒数 (默认: 0 表示只运行一次)")
    return parser.parse_args()


def read_results(csv_path: Path) -> list:
    """读取 results.csv"""
    if not csv_path.exists():
        return []
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records


def print_progress(records: list, total_epochs: int = 20):
    """打印当前进度"""
    if not records:
        print("[提示] 尚未找到训练记录，请确认训练已启动。")
        return

    latest = records[-1]
    epoch = int(latest.get("epoch", 0))
    time_elapsed = float(latest.get("time", 0))

    # 指标
    box_loss = float(latest.get("train/box_loss", 0))
    cls_loss = float(latest.get("train/cls_loss", 0))
    dfl_loss = float(latest.get("train/dfl_loss", 0))
    precision = float(latest.get("metrics/precision(B)", 0))
    recall = float(latest.get("metrics/recall(B)", 0))
    map50 = float(latest.get("metrics/mAP50(B)", 0))
    map5095 = float(latest.get("metrics/mAP50-95(B)", 0))

    # 历史最佳
    best_map50 = max(float(r.get("metrics/mAP50(B)", 0)) for r in records)
    best_epoch = max(records, key=lambda r: float(r.get("metrics/mAP50(B)", 0)))["epoch"]

    # 预计剩余时间
    if epoch > 0:
        avg_epoch_time = time_elapsed / epoch
        remaining_epochs = total_epochs - epoch
        remaining_seconds = avg_epoch_time * remaining_epochs
        remaining_str = str(timedelta(seconds=int(remaining_seconds)))
    else:
        remaining_str = "未知"

    print("\n" + "=" * 60)
    print(f"YOLO 病害检测训练进度报告")
    print(f"报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"当前 epoch: {epoch} / {total_epochs}")
    print(f"已用时: {timedelta(seconds=int(time_elapsed))}")
    print(f"预计剩余: {remaining_str}")
    print()
    print("最新指标:")
    print(f"  train/box_loss: {box_loss:.4f}")
    print(f"  train/cls_loss: {cls_loss:.4f}")
    print(f"  train/dfl_loss: {dfl_loss:.4f}")
    print(f"  val/precision:  {precision:.4f}")
    print(f"  val/recall:     {recall:.4f}")
    print(f"  val/mAP50:      {map50:.4f}")
    print(f"  val/mAP50-95:   {map5095:.4f}")
    print()
    print(f"历史最佳 mAP50: {best_map50:.4f} (epoch {best_epoch})")
    print("=" * 60)


def print_weights_info(run_dir: Path):
    """打印权重文件信息"""
    weights_dir = run_dir / "weights"
    if not weights_dir.exists():
        return

    best_pt = weights_dir / "best.pt"
    last_pt = weights_dir / "last.pt"

    print("模型权重:")
    for pt in [best_pt, last_pt]:
        if pt.exists():
            mtime = datetime.fromtimestamp(pt.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_mb = pt.stat().st_size / 1024 / 1024
            print(f"  {pt.name}: {size_mb:.1f} MB, 更新于 {mtime}")
        else:
            print(f"  {pt.name}: 不存在")
    print()


def main():
    args = parse_args()
    run_dir = Path(args.run_dir)
    csv_path = run_dir / "results.csv"

    print(f"监控目录: {run_dir.resolve()}")
    print(f"结果文件: {csv_path}")

    def show():
        records = read_results(csv_path)
        print_progress(records)
        print_weights_info(run_dir)

    if args.refresh > 0:
        import time
        try:
            while True:
                os.system("cls" if os.name == "nt" else "clear")
                show()
                print(f"[提示] 每 {args.refresh} 秒自动刷新，按 Ctrl+C 退出")
                time.sleep(args.refresh)
        except KeyboardInterrupt:
            print("\n[退出] 用户中断")
    else:
        show()


if __name__ == "__main__":
    main()
