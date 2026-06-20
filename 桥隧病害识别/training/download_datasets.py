# -*- coding: utf-8 -*-
"""
公开桥梁病害数据集下载脚本

支持下载以下数据集：
- GYU-DET: 11,123张桥梁表面病害图像，6类（YOLO格式）
- CODEBRIM: 1,022张，5类病害

使用方法:
    python download_datasets.py --output ../datasets
"""

import os
import sys
import argparse
import urllib.request
import zipfile
import traceback

# 数据集配置
DATASETS = {
    "gyu-det": {
        "name": "GYU-DET (Multi-defect type beam bridge dataset)",
        "url": "https://github.com/user-attachments/files/gyu-det.zip",  # 占位，实际需替换
        "description": "11,123张图像，6类病害：裂缝、剥落、渗水、蜂窝麻面、露筋、孔洞",
        "format": "YOLO",
    },
    "codebrim": {
        "name": "CODEBRIM (COncrete DEfect BRidge IMage dataset)",
        "url": "https://github.com/notation-ai/CODEBRIM/archive/refs/heads/master.zip",
        "description": "1,022张图像，5类病害：裂缝、腐蚀、风化、剥落、露筋",
        "format": "COCO-like",
    },
}


def download_file(url: str, dest_path: str, chunk_size: int = 8192) -> bool:
    """下载文件并显示进度"""
    try:
        print(f"Downloading: {url}")
        print(f"Destination: {dest_path}")
        
        def reporthook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(downloaded * 100 / total_size, 100) if total_size > 0 else 0
            print(f"\r  Progress: {percent:.1f}% ({downloaded}/{total_size} bytes)", end="")
        
        urllib.request.urlretrieve(url, dest_path, reporthook)
        print("\n  Download complete.")
        return True
    except Exception as e:
        print(f"\n  Download failed: {e}")
        return False


def extract_zip(zip_path: str, extract_to: str) -> bool:
    """解压ZIP文件"""
    try:
        print(f"Extracting: {zip_path}")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_to)
        print("  Extraction complete.")
        return True
    except Exception as e:
        print(f"  Extraction failed: {e}")
        return False


def prepare_gyu_det(dataset_dir: str):
    """
    准备GYU-DET数据集。
    
    由于GYU-DET可能需要通过论文/学术渠道获取，这里提供：
    1. 数据集元信息说明
    2. 目录结构模板
    3. 转换脚本框架
    """
    gyu_dir = os.path.join(dataset_dir, "gyu-det")
    os.makedirs(gyu_dir, exist_ok=True)
    
    # 创建标准YOLO目录结构
    for split in ['train', 'val', 'test']:
        os.makedirs(os.path.join(gyu_dir, 'images', split), exist_ok=True)
        os.makedirs(os.path.join(gyu_dir, 'labels', split), exist_ok=True)
    
    # 创建data.yaml
    yaml_content = """path: {gyu_dir}
train: images/train
val: images/val
test: images/test

nc: 6
names:
  - 裂缝
  - 剥落
  - 渗水
  - 蜂窝麻面
  - 露筋
  - 孔洞
""".format(gyu_dir=gyu_dir.replace('\\', '/'))
    
    yaml_path = os.path.join(gyu_dir, "data.yaml")
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
    
    print(f"\nGYU-DET 数据集目录已创建: {gyu_dir}")
    print("请将下载的数据集图片和标注放入对应目录:")
    print("  images/train/  labels/train/")
    print("  images/val/    labels/val/")
    print("  images/test/   labels/test/")
    print(f"\ndata.yaml 已生成: {yaml_path}")


def prepare_codebrim(dataset_dir: str):
    """准备CODEBRIM数据集"""
    cb_dir = os.path.join(dataset_dir, "codebrim")
    os.makedirs(cb_dir, exist_ok=True)
    
    print(f"\nCODEBRIM 数据集目录已创建: {cb_dir}")
    print("CODEBRIM可通过以下方式获取:")
    print("  1. 访问: https://github.com/notation-ai/CODEBRIM")
    print("  2. 或使用 Kaggle: https://www.kaggle.com/datasets/")
    print("\n下载后放入该目录即可。")


def main():
    parser = argparse.ArgumentParser(description="下载桥梁病害公开数据集")
    parser.add_argument("--output", "-o", default="../datasets", 
                       help="数据集输出目录 (默认: ../datasets)")
    parser.add_argument("--dataset", "-d", choices=["gyu-det", "codebrim", "all"],
                       default="all", help="要准备的数据集")
    args = parser.parse_args()
    
    dataset_dir = os.path.abspath(args.output)
    os.makedirs(dataset_dir, exist_ok=True)
    
    print("=" * 60)
    print("桥梁病害数据集准备工具")
    print("=" * 60)
    print(f"输出目录: {dataset_dir}")
    
    if args.dataset in ("gyu-det", "all"):
        prepare_gyu_det(dataset_dir)
    
    if args.dataset in ("codebrim", "all"):
        prepare_codebrim(dataset_dir)
    
    print("\n" + "=" * 60)
    print("数据集准备完成！")
    print("=" * 60)
    print("\n下一步：")
    print("  1. 将数据集图片放入对应目录")
    print("  2. 运行 train_disease_yolo.py 训练病害检测模型")


if __name__ == "__main__":
    main()
