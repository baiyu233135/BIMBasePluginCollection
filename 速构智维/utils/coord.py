# -*- coding: utf-8 -*-
"""
坐标转换工具 - 屏幕坐标与世界坐标的互相转换

支持: 平移(Pan)、缩放(Zoom)、自适应视口
- 虚拟画布默认 A3 尺寸: 420mm x 297mm
- 原点(0,0)在画布左下角（符合CAD惯例）
- Y轴向上（屏幕坐标Y向下，需要翻转）
"""

import math
from typing import Tuple, Optional

DEFAULT_CANVAS_WIDTH = 420.0
DEFAULT_CANVAS_HEIGHT = 297.0
DEFAULT_MARGIN = 20.0


class CoordinateSystem:
    """坐标系统 - 支持平移和缩放"""

    def __init__(self, canvas_width: float = DEFAULT_CANVAS_WIDTH,
                 canvas_height: float = DEFAULT_CANVAS_HEIGHT):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.margin = DEFAULT_MARGIN

        # 视口尺寸
        self._viewport_width = 0
        self._viewport_height = 0

        # 基础缩放（自适应画布到视口）
        self._base_scale = 1.0
        # 用户缩放因子（滚轮缩放）
        self._zoom_factor = 1.0
        # 总缩放 = 基础缩放 * 用户缩放
        self._scale = 1.0

        # 平移偏移（像素）
        self._pan_x = 0.0
        self._pan_y = 0.0

        # 最小/最大缩放限制
        self._min_zoom = 0.01
        self._max_zoom = 100.0

    def update_viewport(self, widget_width: int, widget_height: int):
        """窗口大小改变时更新基础缩放"""
        self._viewport_width = widget_width
        self._viewport_height = widget_height
        self._recalculate_scale()

    def _recalculate_scale(self):
        """重新计算总缩放比例"""
        if self._viewport_width <= 0 or self._viewport_height <= 0:
            return
        avail_w = self._viewport_width - 2 * self.margin
        avail_h = self._viewport_height - 2 * self.margin
        if avail_w <= 0 or avail_h <= 0:
            return
        scale_x = avail_w / self.canvas_width
        scale_y = avail_h / self.canvas_height
        self._base_scale = min(scale_x, scale_y)
        self._scale = self._base_scale * self._zoom_factor

    # ---------- 缩放和平移操作 ----------

    def zoom_at(self, screen_x: int, screen_y: int, factor: float):
        """以屏幕某点为中心缩放"""
        old_scale = self._scale
        new_zoom = self._zoom_factor * factor
        new_zoom = max(self._min_zoom, min(self._max_zoom, new_zoom))

        # 计算该点在旧坐标系中的世界坐标
        wx, wy = self.screen_to_world(screen_x, screen_y)

        self._zoom_factor = new_zoom
        self._recalculate_scale()

        # 调整平移，使世界坐标点保持在相同屏幕位置
        if old_scale > 0:
            new_screen_x = (wx * self._scale) + self._get_origin_x()
            new_screen_y = self._get_origin_y() - (wy * self._scale)
            self._pan_x += screen_x - new_screen_x
            self._pan_y += screen_y - new_screen_y

    def zoom_reset(self):
        """重置缩放到初始状态"""
        self._zoom_factor = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._recalculate_scale()

    def pan(self, dx: float, dy: float):
        """平移视口（像素）"""
        self._pan_x += dx
        self._pan_y += dy

    def get_scale(self) -> float:
        """获取当前总缩放比例(像素/mm)"""
        return self._scale

    def get_zoom_factor(self) -> float:
        """获取用户缩放因子"""
        return self._zoom_factor

    # ---------- 内部辅助 ----------

    def _get_origin_x(self) -> float:
        """画布原点(0,0)在屏幕上的X坐标"""
        avail_w = self._viewport_width - 2 * self.margin
        drawn_w = self.canvas_width * self._scale
        offset = self.margin + (avail_w - drawn_w) / 2
        return offset + self._pan_x

    def _get_origin_y(self) -> float:
        """画布原点(0,0)在屏幕上的Y坐标（注意Y轴翻转）"""
        avail_h = self._viewport_height - 2 * self.margin
        drawn_h = self.canvas_height * self._scale
        offset = self.margin + (avail_h - drawn_h) / 2
        return offset + drawn_h + self._pan_y  # 原点在左下角，所以是offset + drawn_h

    def world_to_screen(self, wx: float, wy: float) -> Tuple[int, int]:
        """世界坐标 → 屏幕坐标"""
        sx = int(self._get_origin_x() + wx * self._scale)
        sy = int(self._get_origin_y() - wy * self._scale)
        return (sx, sy)

    def screen_to_world(self, sx: int, sy: int) -> Tuple[float, float]:
        """屏幕坐标 → 世界坐标"""
        wx = (sx - self._get_origin_x()) / self._scale
        wy = (self._get_origin_y() - sy) / self._scale
        return (wx, wy)

    def world_dist_to_screen(self, wdist: float) -> int:
        """世界距离 → 屏幕距离"""
        return int(abs(wdist * self._scale))

    def screen_dist_to_world(self, sdist: float) -> float:
        """屏幕距离 → 世界距离"""
        if self._scale <= 0:
            return 0
        return abs(sdist / self._scale)

    def get_canvas_rect_screen(self) -> Tuple[int, int, int, int]:
        """画布在屏幕上的矩形 (x, y, w, h)"""
        x1, y1 = self.world_to_screen(0, self.canvas_height)
        x2, y2 = self.world_to_screen(self.canvas_width, 0)
        return (x1, y1, x2 - x1, y2 - y1)
