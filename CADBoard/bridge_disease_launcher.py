# -*- coding: utf-8 -*-
"""
桥隧病害识别 — CADBoard 转发入口

原桥隧病害识别功能已独立到 ../桥隧病害识别/ 目录。
此文件仅作为 CADBoard.pyplugin 中"桥隧病害识别"按钮的入口保留，
实际逻辑转发到新模块执行，保持 BIMBase 面板按钮路径不变。
"""

import os
import sys

# 添加桥隧病害识别模块路径
_disease_dir = os.path.join(os.path.dirname(__file__), '..', '桥隧病害识别')
_disease_dir = os.path.normpath(_disease_dir)
if _disease_dir not in sys.path:
    sys.path.insert(0, _disease_dir)

# 转发执行
from bridge_disease_launcher import run_disease_recognition

if __name__ == "__main__":
    run_disease_recognition()
