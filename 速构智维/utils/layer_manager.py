# -*- coding: utf-8 -*-
"""
图层管理器 - 2D画板内部图层系统

功能:
- 创建/删除/重命名图层
- 设置图层颜色、线宽、可见性、锁定状态
- 当前图层切换
- 默认图层"0"不可删除
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Layer:
    """图层定义"""
    name: str
    color: Tuple[int, int, int] = (255, 255, 255)  # RGB
    line_width: float = 0.25
    visible: bool = True
    locked: bool = False


class LayerManager:
    """图层管理器"""

    def __init__(self):
        self._layers: Dict[str, Layer] = {}
        self._current_layer = "0"
        # 创建默认图层
        self._layers["0"] = Layer("0", color=(255, 255, 255))

    # ---------- 图层CRUD ----------

    def add_layer(self, name: str, color: Tuple[int, int, int] = (255, 255, 255),
                  line_width: float = 0.25) -> bool:
        """添加新图层"""
        if name in self._layers or not name or name == "0":
            return False
        self._layers[name] = Layer(name, color=color, line_width=line_width)
        return True

    def remove_layer(self, name: str) -> bool:
        """删除图层（默认图层不可删除）"""
        if name == "0" or name not in self._layers:
            return False
        del self._layers[name]
        if self._current_layer == name:
            self._current_layer = "0"
        return True

    def rename_layer(self, old_name: str, new_name: str) -> bool:
        """重命名图层"""
        if old_name == "0" or old_name not in self._layers:
            return False
        if new_name in self._layers or not new_name:
            return False
        layer = self._layers.pop(old_name)
        layer.name = new_name
        self._layers[new_name] = layer
        if self._current_layer == old_name:
            self._current_layer = new_name
        return True

    def get_layer(self, name: str) -> Optional[Layer]:
        return self._layers.get(name)

    def get_all_layers(self) -> List[Layer]:
        return list(self._layers.values())

    def layer_exists(self, name: str) -> bool:
        return name in self._layers

    # ---------- 当前图层 ----------

    def get_current_layer(self) -> str:
        return self._current_layer

    def set_current_layer(self, name: str) -> bool:
        if name in self._layers:
            self._current_layer = name
            return True
        return False

    # ---------- 图层属性 ----------

    def set_visible(self, name: str, visible: bool) -> bool:
        layer = self._layers.get(name)
        if layer:
            layer.visible = visible
            return True
        return False

    def set_locked(self, name: str, locked: bool) -> bool:
        layer = self._layers.get(name)
        if layer:
            layer.locked = locked
            return True
        return False

    def set_color(self, name: str, color: Tuple[int, int, int]) -> bool:
        layer = self._layers.get(name)
        if layer:
            layer.color = color
            return True
        return False

    def set_line_width(self, name: str, width: float) -> bool:
        layer = self._layers.get(name)
        if layer:
            layer.line_width = width
            return True
        return False

    def is_visible(self, name: str) -> bool:
        layer = self._layers.get(name)
        return layer.visible if layer else True

    def is_locked(self, name: str) -> bool:
        layer = self._layers.get(name)
        return layer.locked if layer else False

    # ---------- 应用图层样式到元素 ----------

    def apply_layer_style(self, element):
        """将当前图层的样式应用到元素"""
        layer = self._layers.get(self._current_layer)
        if layer:
            element.style.color = layer.color
            element.style.line_width = layer.line_width
            element.style.layer_name = layer.name
