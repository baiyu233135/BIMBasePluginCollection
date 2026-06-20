# -*- coding: utf-8 -*-
"""
桥梁构件图像分类模型训练脚本 — EfficientNet-B0

训练19类桥梁构件分类器，用于自动识别无人机照片中的构件类型。

使用方法:
    # 准备数据集（目录结构如下）:
    # datasets/component_cls/
    #   train/
    #     T梁/      (图片)
    #     箱梁/
    #     ...
    #   val/
    #     T梁/
    #     ...
    
    python train_classifier.py --data ../datasets/component_cls --epochs 50
"""

import os
import sys
import argparse
import traceback
from typing import Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, transforms, models
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights

# 19种构件类型
COMPONENT_CLASSES = [
    "T梁", "主塔", "工字钢混凝土组合梁", "斜拉索", "湿接缝", "箱梁", "防撞护栏", "波形护栏",
    "主塔群桩承台", "异形盖梁", "扩大基础", "柱式桥台", "柱式桥墩", "桩基承台", 
    "薄壁墩", "重力式桥台", "人行道及护栏", "路面及交通标线",
]


def get_data_transforms(input_size: int = 224):
    """获取数据预处理变换"""
    train_transform = transforms.Compose([
        transforms.Resize((input_size, input_size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                            std=[0.229, 0.224, 0.225]),
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize((input_size, input_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                            std=[0.229, 0.224, 0.225]),
    ])
    
    return train_transform, val_transform


def create_model(num_classes: int, device: str = 'cpu'):
    """创建EfficientNet-B0模型"""
    model = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1)
    
    # 冻结特征提取层（可选，用于快速训练）
    # for param in model.features.parameters():
    #     param.requires_grad = False
    
    # 修改分类头
    num_features = model.classifier[1].in_features
    model.classifier[1] = nn.Linear(num_features, num_classes)
    
    model = model.to(device)
    return model


def train_epoch(model, dataloader, criterion, optimizer, device):
    """训练一个epoch"""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0
    
    for batch_idx, (inputs, labels) in enumerate(dataloader):
        inputs, labels = inputs.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        running_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()
        
        if batch_idx % 10 == 0:
            print(f"  Batch {batch_idx}/{len(dataloader)} | "
                  f"Loss: {loss.item():.4f} | Acc: {100.*correct/total:.2f}%")
    
    epoch_loss = running_loss / len(dataloader)
    epoch_acc = 100. * correct / total
    return epoch_loss, epoch_acc


def validate(model, dataloader, criterion, device):
    """验证"""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    
    with torch.no_grad():
        for inputs, labels in dataloader:
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            
            running_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
    
    epoch_loss = running_loss / len(dataloader)
    epoch_acc = 100. * correct / total
    return epoch_loss, epoch_acc


def train(data_dir: str, epochs: int = 50, batch_size: int = 16,
          lr: float = 0.001, device: str = 'cpu',
          output_dir: str = '../models'):
    """训练分类模型"""
    
    print("=" * 60)
    print("EfficientNet-B0 桥梁构件分类模型训练")
    print("=" * 60)
    print(f"数据集: {data_dir}")
    print(f"训练轮数: {epochs}")
    print(f"批次大小: {batch_size}")
    print(f"学习率: {lr}")
    print(f"设备: {device}")
    print("=" * 60)
    
    train_dir = os.path.join(data_dir, 'train')
    val_dir = os.path.join(data_dir, 'val')
    
    if not os.path.exists(train_dir):
        print(f"❌ 训练目录不存在: {train_dir}")
        print("请按以下结构准备数据集:")
        print("  datasets/component_cls/")
        print("    train/")
        print("      T梁/ (*.jpg)")
        print("      箱梁/ (*.jpg)")
        print("      ...")
        print("    val/")
        print("      T梁/ (*.jpg)")
        print("      ...")
        sys.exit(1)
    
    # 数据预处理
    input_size = 224
    train_transform, val_transform = get_data_transforms(input_size)
    
    train_dataset = datasets.ImageFolder(train_dir, transform=train_transform)
    
    if os.path.exists(val_dir):
        val_dataset = datasets.ImageFolder(val_dir, transform=val_transform)
    else:
        # 如果没有val目录，从train中分割20%
        from torch.utils.data import random_split
        val_size = int(0.2 * len(train_dataset))
        train_size = len(train_dataset) - val_size
        train_dataset, val_dataset = random_split(
            train_dataset, [train_size, val_size]
        )
        # 注意：random_split后的数据集没有transform，需要重新包装
        # 这里简化处理，实际使用时建议预先分好数据集
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, 
                             shuffle=True, num_workers=2)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, 
                           shuffle=False, num_workers=2)
    
    num_classes = len(train_dataset.classes)
    print(f"\n类别数: {num_classes}")
    print(f"训练样本: {len(train_dataset)}")
    print(f"验证样本: {len(val_dataset)}")
    print(f"类别映射: {train_dataset.class_to_idx}")
    
    # 创建模型
    model = create_model(num_classes, device)
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)
    
    # 训练循环
    best_acc = 0.0
    os.makedirs(output_dir, exist_ok=True)
    
    for epoch in range(epochs):
        print(f"\nEpoch {epoch+1}/{epochs}")
        print("-" * 40)
        
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = validate(model, val_loader, criterion, device)
        scheduler.step()
        
        print(f"Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.2f}%")
        print(f"Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2f}%")
        
        # 保存最佳模型
        if val_acc > best_acc:
            best_acc = val_acc
            best_path = os.path.join(output_dir, 'component_classifier.pt')
            torch.save(model.state_dict(), best_path)
            print(f"✅ 最佳模型已保存: {best_path} (Acc: {best_acc:.2f}%)")
    
    print("\n" + "=" * 60)
    print("训练完成!")
    print(f"最佳验证准确率: {best_acc:.2f}%")
    print(f"模型保存路径: {os.path.join(output_dir, 'component_classifier.pt')}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="训练桥梁构件分类模型")
    parser.add_argument("--data", "-d", default="../datasets/component_cls",
                       help="数据集根目录 (默认: ../datasets/component_cls)")
    parser.add_argument("--epochs", "-e", type=int, default=50,
                       help="训练轮数 (默认: 50)")
    parser.add_argument("--batch", "-b", type=int, default=16,
                       help="批次大小 (默认: 16)")
    parser.add_argument("--lr", type=float, default=0.001,
                       help="学习率 (默认: 0.001)")
    parser.add_argument("--device", default="cpu",
                       help="训练设备: cpu 或 cuda (默认: cpu)")
    parser.add_argument("--output", "-o", default="../models",
                       help="模型输出目录 (默认: ../models)")
    args = parser.parse_args()
    
    try:
        train(
            data_dir=args.data,
            epochs=args.epochs,
            batch_size=args.batch,
            lr=args.lr,
            device=args.device,
            output_dir=args.output,
        )
    except Exception as e:
        print(f"\n❌ 训练失败: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
