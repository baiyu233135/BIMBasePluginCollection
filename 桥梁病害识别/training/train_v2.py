# -*- coding: utf-8 -*-
"""v2 统一病害模型训练（GYU + v1 桥隧合并集）。

用 ultralytics 8.0.145 venv（C:\\temp\\ul_80145）训练，产出 BIMBase 原生可加载：
    C:\\temp\\ul_80145\\Scripts\\python.exe train_v2.py

输出：桥梁病害识别/models/disease_yolov8n_v2/（best.pt 等）
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 桥梁病害识别/
# cv2 在 Windows 读不了中文路径，训练数据须放在纯英文路径：
# 默认用 C:\temp\btgyu_v2（由 merge_v2_dataset.py 产物复制而来），
# 可用环境变量 DATA_YAML 覆盖
DATA_YAML = os.environ.get(
    "DATA_YAML",
    r"C:\temp\btgyu_v2\data.yaml")
PRETRAINED = os.path.join(BASE, "models", "yolov8n.pt")
PROJECT = os.path.join(BASE, "models")
NAME = "disease_yolov8n_v2"

import torch as _torch

# last.pt 是本脚本自己训出的可信文件；torch>=2.6 默认 weights_only=True 会拒绝反序列化
_orig_load = _torch.load
def _load_trusted(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig_load(*args, **kwargs)
_torch.load = _load_trusted

from ultralytics import YOLO

assert os.path.isfile(DATA_YAML), f"缺少数据集配置: {DATA_YAML}\n请先运行 merge_v2_dataset.py"

# RESUME=1 时从上次的 last.pt 断点续训（不丢已训轮数）
RESUME = os.environ.get("RESUME", "") == "1"
if RESUME:
    LAST = os.path.join(PROJECT, NAME, "weights", "last.pt")
    assert os.path.isfile(LAST), f"续训需要 {LAST}"
    model = YOLO(LAST)
    model.train(resume=True)
else:
    if not os.path.isfile(PRETRAINED):
        PRETRAINED = "yolov8n.pt"   # 让 ultralytics 自行下载
    model = YOLO(PRETRAINED)
    model.train(
        data=DATA_YAML,
        epochs=200,
        patience=30,        # 30 轮无提升自动早停
        batch=4,            # CPU 训练，保守批次
        imgsz=640,
        device="cpu",
        workers=2,
        project=PROJECT,
        name=NAME,
        exist_ok=True,
        seed=42,
    )
