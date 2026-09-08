# -*- coding: utf-8 -*-
"""
桥梁病害检测模型训练脚本 — YOLOv8n

基于公开数据集训练轻量级病害检测模型，支持CPU训练（较慢）。

使用方法:
    # 准备数据集后
    python train_disease_yolo.py --data ../datasets/gyu-det/data.yaml --epochs 100

    # 使用已有数据集继续训练
    python train_disease_yolo.py --resume
"""

import os
import sys
import argparse
import traceback

# 添加项目根目录到路径
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def check_ultralytics():
    """检查并提示安装ultralytics"""
    try:
        import ultralytics
        print(f"✅ ultralytics 已安装 (版本: {ultralytics.__version__})")
        return True
    except ImportError:
        print("❌ ultralytics 未安装")
        print("请运行以下命令安装:")
        print("  pip install ultralytics")
        print("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu")
        return False


def train(data_yaml: str, epochs: int = 100, imgsz: int = 640,
          batch: int = 8, device: str = 'cpu', workers: int = 4,
          model_path: str = 'yolov8n.pt',
          output_dir: str = '../models',
          patience: int = 20):
    """
    训练YOLOv8n病害检测模型。

    Args:
        data_yaml: 数据集配置文件路径
        epochs: 训练轮数
        imgsz: 输入图像尺寸
        batch: 批次大小（CPU建议4-8）
        device: 训练设备 'cpu' 或 'cuda'
        workers: 数据加载线程数
        model_path: 预训练权重路径
        output_dir: 模型输出目录
        patience: 早停耐心值，0 表示关闭早停（训练完所有 epochs）
    """
    from ultralytics import YOLO
    
    print("=" * 60)
    print("YOLOv8n 桥梁病害检测模型训练")
    print("=" * 60)
    print(f"数据集: {data_yaml}")
    print(f"预训练权重: {model_path}")
    print(f"训练轮数: {epochs}")
    print(f"图像尺寸: {imgsz}")
    print(f"批次大小: {batch}")
    print(f"设备: {device}")
    print("=" * 60)
    
    # 加载预训练模型
    model = YOLO(model_path)
    
    # 训练
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        workers=workers,
        patience=patience,     # 早停耐心值，0=关闭早停
        save=True,
        project=output_dir,
        name='disease_yolov8n',
        exist_ok=True,
        pretrained=True,
        optimizer='SGD',
        lr0=0.01,              # 初始学习率
        lrf=0.01,              # 最终学习率
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=3.0,
        warmup_momentum=0.8,
        box=7.5,               # box损失增益
        cls=0.5,               # cls损失增益
        dfl=1.5,               # dfl损失增益
        label_smoothing=0.0,
        nbs=64,                # 名义批次大小
        overlap_mask=True,
        val=True,
        verbose=True,
    )
    
    print("\n" + "=" * 60)
    print("训练完成!")
    print("=" * 60)
    print(f"最佳模型: {os.path.join(output_dir, 'disease_yolov8n', 'weights', 'best.pt')}")
    print(f"最后模型: {os.path.join(output_dir, 'disease_yolov8n', 'weights', 'last.pt')}")
    
    return results


def export_model(model_path: str, output_path: str):
    """导出模型为ONNX格式（可选，用于加速推理）"""
    try:
        from ultralytics import YOLO
        model = YOLO(model_path)
        model.export(format='onnx', dynamic=True, simplify=True)
        print(f"ONNX模型已导出")
    except Exception as e:
        print(f"导出失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="训练桥梁病害检测YOLOv8n模型")
    parser.add_argument("--data", "-d", default="../datasets/gyu-det/data.yaml",
                       help="数据集YAML配置文件路径")
    parser.add_argument("--epochs", "-e", type=int, default=100,
                       help="训练轮数 (默认: 100)")
    parser.add_argument("--imgsz", type=int, default=640,
                       help="输入图像尺寸 (默认: 640)")
    parser.add_argument("--batch", "-b", type=int, default=8,
                       help="批次大小，CPU建议4-8 (默认: 8)")
    parser.add_argument("--device", default="cpu",
                       help="训练设备: cpu 或 cuda (默认: cpu)")
    parser.add_argument("--workers", "-w", type=int, default=4,
                       help="数据加载线程数 (默认: 4)")
    parser.add_argument("--model", "-m", default="yolov8n.pt",
                       help="预训练权重 (默认: yolov8n.pt)")
    parser.add_argument("--output", "-o", default="../models",
                       help="模型输出目录 (默认: ../models)")
    parser.add_argument("--patience", "-p", type=int, default=20,
                       help="早停耐心值，0 表示关闭早停 (默认: 20)")
    parser.add_argument("--export", action="store_true",
                       help="训练完成后导出ONNX模型")
    args = parser.parse_args()
    
    if not check_ultralytics():
        sys.exit(1)
    
    # 检查数据集
    if not os.path.exists(args.data):
        print(f"❌ 数据集配置文件不存在: {args.data}")
        print("请先运行 download_datasets.py 准备数据集")
        sys.exit(1)
    
    try:
        results = train(
            data_yaml=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            workers=args.workers,
            model_path=args.model,
            output_dir=args.output,
            patience=args.patience,
        )
        
        if args.export:
            best_path = os.path.join(args.output, 'disease_yolov8n', 'weights', 'best.pt')
            if os.path.exists(best_path):
                export_model(best_path, args.output)
    
    except Exception as e:
        print(f"\n❌ 训练失败: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
