# -*- coding: utf-8 -*-
"""
CADBoard BIMBase Python Plugin

基于VSCode的BIMBase Python建模插件 - CAD画板
"""

__version__ = "1.1.0"
__author__ = "CADBoard Developer"

# 包级导入便利
from board import CADBoardWindow
from main import run

__all__ = ["CADBoardWindow", "run"]
