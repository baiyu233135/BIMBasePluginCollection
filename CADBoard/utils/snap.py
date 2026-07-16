# -*- coding: utf-8 -*-
"""
网格吸附系统 - 鼠标坐标吸附到网格或已有几何关键点

支持:
- 端点吸附 (端点)
- 交点吸附 (两条线的交点)
- 中心点吸附 (圆心/矩形中心/圆弧中心)
- 垂足吸附 (点到线段的垂足)
- 网格吸附 (网格交点)

显示吸附提示标记
"""

import math
from typing import Tuple, List, Optional


class SnapSystem:
    """吸附系统"""

    SNAP_RADIUS_SCREEN = 10  # 吸附半径（像素）

    def __init__(self):
        self.enabled = True
        self.grid_snap = True
        self.endpoint_snap = True
        self.intersection_snap = True    # 交点
        self.center_snap = True          # 中心点
        self.perpendicular_snap = True   # 垂足
        self.snap_size = 10.0            # 网格间距(mm)
        self._snap_point = None
        self._snap_type = None

    def snap(self, wx: float, wy: float, coord_system,
             elements: List = None) -> Tuple[float, float]:
        if not self.enabled:
            self._snap_point = None
            self._snap_type = None
            return (wx, wy)

        candidates = []  # [(sx, sy, type, priority), ...]

        # 1. 网格吸附 (priority 5 - 最低)
        if self.grid_snap and self.snap_size > 0:
            gx = round(wx / self.snap_size) * self.snap_size
            gy = round(wy / self.snap_size) * self.snap_size
            candidates.append((gx, gy, 'grid', 5))

        if elements:
            # 2. 端点吸附 (priority 1 - 最高)
            if self.endpoint_snap:
                endpoints = self._collect_endpoints(elements)
                for ex, ey in endpoints:
                    candidates.append((ex, ey, 'endpoint', 1))

            # 3. 交点吸附 (priority 2)
            if self.intersection_snap:
                intersections = self._collect_intersections(elements)
                for ix, iy in intersections:
                    candidates.append((ix, iy, 'intersection', 2))

            # 4. 中心点吸附 (priority 3)
            if self.center_snap:
                centers = self._collect_centers(elements)
                for cx, cy in centers:
                    candidates.append((cx, cy, 'center', 3))

            # 5. 垂足吸附 (priority 4)
            if self.perpendicular_snap:
                perps = self._collect_perpendiculars(elements, wx, wy)
                for px, py in perps:
                    candidates.append((px, py, 'perpendicular', 4))

        if not candidates:
            self._snap_point = None
            self._snap_type = None
            return (wx, wy)

        # 选择最近的候选点（在屏幕距离阈值内）
        best = None
        best_dist = float('inf')
        sr = self.SNAP_RADIUS_SCREEN
        orig_scr_x, orig_scr_y = coord_system.world_to_screen(wx, wy)

        for sx, sy, stype, priority in candidates:
            scr_x, scr_y = coord_system.world_to_screen(sx, sy)
            d = math.hypot(scr_x - orig_scr_x, scr_y - orig_scr_y)
            if d <= sr:
                # 优先级越小的越优先，同优先级距离近的优先
                score = priority * 1000 + d
                if score < best_dist:
                    best_dist = score
                    best = (sx, sy, stype)

        if best:
            self._snap_point = (best[0], best[1])
            self._snap_type = best[2]
            return (best[0], best[1])

        self._snap_point = None
        self._snap_type = None
        return (wx, wy)

    def _collect_endpoints(self, elements: List) -> List[Tuple[float, float]]:
        """收集所有端点"""
        pts = []
        for elem in elements:
            if not getattr(elem, 'visible', True):
                continue
            et = elem.element_type.value
            if et == '直线':
                pts.extend([(elem.x1, elem.y1), (elem.x2, elem.y2)])
            elif et in ('多段线', '多边形'):
                pts.extend([p for p in elem.points if p is not None])
            elif et == '矩形':
                pts.extend(elem.get_corners())
            elif et == '圆':
                pts.extend([(elem.cx + elem.radius, elem.cy),
                           (elem.cx - elem.radius, elem.cy),
                           (elem.cx, elem.cy + elem.radius),
                           (elem.cx, elem.cy - elem.radius)])
            elif et == '圆弧':
                for a in [elem.start_angle, elem.end_angle]:
                    ar = math.radians(a)
                    pts.append((elem.cx + elem.radius * math.cos(ar),
                               elem.cy + elem.radius * math.sin(ar)))
                pts.append((elem.cx, elem.cy))
            elif et == '椭圆':
                pts.extend([(elem.cx + elem.rx, elem.cy),
                           (elem.cx - elem.rx, elem.cy),
                           (elem.cx, elem.cy + elem.ry),
                           (elem.cx, elem.cy - elem.ry)])
            elif et == '点':
                pts.append((elem.x, elem.y))
        return pts

    def _collect_intersections(self, elements: List) -> List[Tuple[float, float]]:
        """收集线段交点。v1.5 P3: 当线段过多时跳过计算，避免O(n^2)卡死UI"""
        pts = []
        lines = []
        for elem in elements:
            if not getattr(elem, 'visible', True):
                continue
            et = elem.element_type.value
            if et == '直线':
                lines.append((elem.x1, elem.y1, elem.x2, elem.y2))
            elif et in ('多段线', '多边形'):
                for s, e in elem.get_segments():
                    lines.append((s[0], s[1], e[0], e[1]))
            elif et == '矩形':
                for s, e in elem.get_segments():
                    lines.append((s[0], s[1], e[0], e[1]))

        # v1.5 P3: 线段过多时跳过交点计算，避免O(n^2)卡死
        MAX_LINES_FOR_INTERSECTION = 500
        if len(lines) > MAX_LINES_FOR_INTERSECTION:
            return pts

        # 计算所有线段对的交点
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                inter = self._line_intersection(*lines[i], *lines[j])
                if inter:
                    pts.append(inter)
        return pts

    def _line_intersection(self, x1, y1, x2, y2, x3, y3, x4, y4):
        """计算两线段交点"""
        dx1, dy1 = x2 - x1, y2 - y1
        dx2, dy2 = x4 - x3, y4 - y3
        det = dx1 * dy2 - dy1 * dx2
        if abs(det) < 1e-12:
            return None
        t = ((x3 - x1) * dy2 - (y3 - y1) * dx2) / det
        s = ((x3 - x1) * dy1 - (y3 - y1) * dx1) / det
        # 交点在两条线段范围内才算
        if 0 <= t <= 1 and 0 <= s <= 1:
            return (x1 + t * dx1, y1 + t * dy1)
        return None

    def _collect_centers(self, elements: List) -> List[Tuple[float, float]]:
        """收集中心点（圆心、矩形中心、圆弧中心）"""
        pts = []
        for elem in elements:
            if not getattr(elem, 'visible', True):
                continue
            et = elem.element_type.value
            if et == '圆':
                pts.append((elem.cx, elem.cy))
            elif et == '圆弧':
                pts.append((elem.cx, elem.cy))
            elif et == '矩形':
                pts.append((elem.x + elem.width / 2, elem.y + elem.height / 2))
            elif et == '椭圆':
                pts.append((elem.cx, elem.cy))
            elif et == '多边形':
                # 多边形重心
                valid = [p for p in elem.points if p is not None]
                if valid:
                    xs = [p[0] for p in valid]
                    ys = [p[1] for p in valid]
                    pts.append((sum(xs) / len(xs), sum(ys) / len(ys)))
        return pts

    def _collect_perpendiculars(self, elements: List, px: float, py: float) -> List[Tuple[float, float]]:
        """收集点到线段的垂足"""
        pts = []
        lines = []
        for elem in elements:
            if not getattr(elem, 'visible', True):
                continue
            et = elem.element_type.value
            if et == '直线':
                lines.append((elem.x1, elem.y1, elem.x2, elem.y2))
            elif et in ('多段线', '多边形'):
                for s, e in elem.get_segments():
                    lines.append((s[0], s[1], e[0], e[1]))
            elif et == '矩形':
                for s, e in elem.get_segments():
                    lines.append((s[0], s[1], e[0], e[1]))

        for x1, y1, x2, y2 in lines:
            dx, dy = x2 - x1, y2 - y1
            l2 = dx * dx + dy * dy
            if l2 < 1e-12:
                continue
            t = ((px - x1) * dx + (py - y1) * dy) / l2
            if 0 <= t <= 1:
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                pts.append((proj_x, proj_y))
        return pts

    def get_snap_info(self) -> Optional[Tuple[Tuple[float, float], str]]:
        if self._snap_point and self._snap_type:
            return (self._snap_point, self._snap_type)
        return None

    def clear(self):
        self._snap_point = None
        self._snap_type = None
