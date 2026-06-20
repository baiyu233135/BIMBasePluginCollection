# -*- coding: utf-8 -*-
"""
几何元素定义 - v1.5 P0
所有画板上的2D几何图形（含3D高度属性）

所有坐标均采用世界坐标系（单位:mm，原点在左下角，Y轴向上）
3D属性: z_start/z_end/thickness 用于BIMBase同步时生成3D实体

v1.5 P0 更新内容 (2026-04-27):
- 新增3D高度属性（z_start, z_end, thickness）
- 新增to_dict/from_dict序列化支持（JSON保存/加载）
- ElementStyle添加clone()方法
- 图层支持（layer_name）
- 唯一ID（用于BIMBase Component关联）
"""

import math
import uuid
from enum import Enum
from typing import List, Tuple, Optional
from dataclasses import dataclass, field


class ElementType(Enum):
    """几何元素类型枚举"""
    LINE = "直线"
    POLYLINE = "多段线"
    POLYGON = "多边形"
    RECTANGLE = "矩形"
    ARC = "圆弧"
    CIRCLE = "圆"
    SPLINE = "样条曲线"
    ELLIPSE = "椭圆"
    ELLIPTICAL_ARC = "椭圆弧"
    POINT = "点"


@dataclass
class ElementStyle:
    """元素样式 - 支持图层和线型"""
    color: Tuple[int, int, int] = (0, 0, 0)  # RGB，默认黑色
    line_width: float = 0.25  # 线宽(mm)
    line_type: str = "solid"  # 线型: solid/dashed/dotted
    layer_name: str = "0"     # 所属图层名称，默认"0"层

    def clone(self):
        """创建样式的深拷贝副本"""
        return ElementStyle(
            color=self.color,
            line_width=self.line_width,
            line_type=self.line_type,
            layer_name=self.layer_name,
        )

    def to_qt_pen(self, scale: float = 1.0):
        """
        转换为Qt的QPen对象
        Args:
            scale: 当前缩放比例(像素/mm)
        Returns:
            QPen对象
        """
        from PyQt5.QtGui import QPen, QColor
        from PyQt5.QtCore import Qt

        pen = QPen()
        pen.setColor(QColor(*self.color))
        pixel_width = max(1, int(self.line_width * scale))
        pen.setWidth(pixel_width)
        pen.setCosmetic(True)

        if self.line_type == "dashed":
            pen.setStyle(Qt.DashLine)
        elif self.line_type == "dotted":
            pen.setStyle(Qt.DotLine)
        else:
            pen.setStyle(Qt.SolidLine)

        return pen


class BaseElement:
    """几何元素基类 - 所有画板元素的抽象
    增加3D属性：z_start, z_end, thickness
    """

    def __init__(self, element_type: ElementType):
        self.element_type = element_type
        self.style = ElementStyle()
        self.selected = False
        self.visible = True
        self.id = str(uuid.uuid4())
        self.bimbase_component_id = None

        # ========== 3D属性 ==========
        self.z_start: float = 0.0    # 起始高度(mm)
        self.z_end: float = 0.0      # 终止高度(mm)
        self.thickness: float = 0.0  # 厚度(mm)，闭合图形拉伸成实体时使用

        # ========== 3D实体标记 ==========
        self.is_3d: bool = False     # 是否为3D实体
        self.entity_3d_type: str = ""  # 3D实体类型: extrude/box/sphere/cone/torus/pyramid/triangular_prism
        self.height: float = 0.0     # 3D实体高度(mm)，与thickness统一用于拉伸/挤出

        # ========== BIMBase组件关联 ==========
        self.component_type: str = ""      # 关联的组件类名
        self.component_params: dict = {}   # 生成组件时的完整参数快照
        self.face_info: dict = {}          # 面关联信息 {component_id, face_name, param_map}

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """获取元素的包围盒 (min_x, min_y, max_x, max_y)"""
        raise NotImplementedError

    def translate(self, dx: float, dy: float):
        """平移元素（2D平移，Z高度不变）"""
        raise NotImplementedError

    def translate_3d(self, dx: float, dy: float, dz: float = 0.0):
        """3D平移 - 子类可重写以同时移动Z坐标"""
        self.translate(dx, dy)
        self.z_start += dz
        self.z_end += dz

    def clone(self):
        """克隆元素（保留类型、样式、3D属性，重置ID）"""
        raise NotImplementedError

    def _clone_3d_attrs(self, elem):
        """复制3D属性到克隆的元素"""
        elem.z_start = self.z_start
        elem.z_end = self.z_end
        elem.thickness = self.thickness
        elem.is_3d = self.is_3d
        elem.entity_3d_type = self.entity_3d_type
        elem.height = self.height
        elem.style = self.style
        elem.component_type = self.component_type
        elem.component_params = dict(self.component_params) if self.component_params else {}
        elem.face_info = dict(self.face_info) if self.face_info else {}

    def scale(self, cx: float, cy: float, factor: float):
        """以(cx,cy)为中心缩放"""
        raise NotImplementedError

    def rotate(self, cx: float, cy: float, angle_deg: float):
        """以(cx,cy)为中心旋转（角度：度，逆时针为正）"""
        raise NotImplementedError

    def mirror(self, x1: float, y1: float, x2: float, y2: float):
        """以过(x1,y1)-(x2,y2)的直线为轴镜像"""
        raise NotImplementedError

    def get_key_params(self) -> dict:
        """获取用于BIMBase参数化组件的关键参数（含3D属性）"""
        return {
            'z_start': self.z_start,
            'z_end': self.z_end,
            'thickness': self.thickness,
        }

    def apply_key_params(self, params: dict):
        """从BIMBase参数更新元素几何（含3D属性）"""
        if 'z_start' in params:
            self.z_start = params['z_start']
        if 'z_end' in params:
            self.z_end = params['z_end']
        if 'thickness' in params:
            self.thickness = params['thickness']

    def is_closed(self) -> bool:
        """是否为闭合图形（用于BIMBase同步时决定用Section还是Line）"""
        return False


class LineElement(BaseElement):
    """直线元素（含3D: z_start对应起点高度，z_end对应终点高度）"""

    def __init__(self, x1: float = 0, y1: float = 0,
                 x2: float = 0, y2: float = 0):
        super().__init__(ElementType.LINE)
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def get_bounds(self) -> Tuple[float, float, float, float]:
        return (min(self.x1, self.x2), min(self.y1, self.y2),
                max(self.x1, self.x2), max(self.y1, self.y2))

    def translate(self, dx: float, dy: float):
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy

    def clone(self):
        elem = LineElement(self.x1, self.y1, self.x2, self.y2)
        self._clone_3d_attrs(elem)
        return elem

    def scale(self, cx: float, cy: float, factor: float):
        self.x1 = cx + (self.x1 - cx) * factor
        self.y1 = cy + (self.y1 - cy) * factor
        self.x2 = cx + (self.x2 - cx) * factor
        self.y2 = cy + (self.y2 - cy) * factor

    def rotate(self, cx: float, cy: float, angle_deg: float):
        a = math.radians(angle_deg)
        cos_a, sin_a = math.cos(a), math.sin(a)
        for x, y in [(self.x1, self.y1), (self.x2, self.y2)]:
            dx, dy = x - cx, y - cy
            nx = cx + dx * cos_a - dy * sin_a
            ny = cy + dx * sin_a + dy * cos_a
            if (x, y) == (self.x1, self.y1):
                self.x1, self.y1 = nx, ny
            else:
                self.x2, self.y2 = nx, ny

    def mirror(self, x1: float, y1: float, x2: float, y2: float):
        dx, dy = x2 - x1, y2 - y1
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return
        for attr_x, attr_y in [('x1', 'y1'), ('x2', 'y2')]:
            px, py = getattr(self, attr_x), getattr(self, attr_y)
            t = ((px - x1) * dx + (py - y1) * dy) / len_sq
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            setattr(self, attr_x, 2 * proj_x - px)
            setattr(self, attr_y, 2 * proj_y - py)

    def get_key_params(self) -> dict:
        d = super().get_key_params()
        d.update({'x1': self.x1, 'y1': self.y1, 'x2': self.x2, 'y2': self.y2})
        return d

    def apply_key_params(self, params: dict):
        super().apply_key_params(params)
        self.x1 = params.get('x1', self.x1)
        self.y1 = params.get('y1', self.y1)
        self.x2 = params.get('x2', self.x2)
        self.y2 = params.get('y2', self.y2)

    def length(self) -> float:
        return math.sqrt((self.x2 - self.x1) ** 2 + (self.y2 - self.y1) ** 2)

    def angle(self) -> float:
        return math.atan2(self.y2 - self.y1, self.x2 - self.x1)

    def __repr__(self):
        return f"Line({self.x1:.1f},{self.y1:.1f} -> {self.x2:.1f},{self.y2:.1f})"


class RectangleElement(BaseElement):
    """矩形元素（含3D: thickness为截面拉伸高度）"""

    def __init__(self, x: float = 0, y: float = 0,
                 width: float = 0, height: float = 0):
        super().__init__(ElementType.RECTANGLE)
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def get_bounds(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def translate(self, dx: float, dy: float):
        self.x += dx
        self.y += dy

    def clone(self):
        elem = RectangleElement(self.x, self.y, self.width, self.height)
        self._clone_3d_attrs(elem)
        return elem

    def scale(self, cx: float, cy: float, factor: float):
        corners = self.get_corners()
        new_corners = []
        for px, py in corners:
            new_corners.append((cx + (px - cx) * factor, cy + (py - cy) * factor))
        self.x = min(c[0] for c in new_corners)
        self.y = min(c[1] for c in new_corners)
        self.width = max(c[0] for c in new_corners) - self.x
        self.height = max(c[1] for c in new_corners) - self.y

    def rotate(self, cx: float, cy: float, angle_deg: float):
        corners = self.get_corners()
        a = math.radians(angle_deg)
        cos_a, sin_a = math.cos(a), math.sin(a)
        new_corners = []
        for px, py in corners:
            dx, dy = px - cx, py - cy
            new_corners.append((cx + dx * cos_a - dy * sin_a,
                               cy + dx * sin_a + dy * cos_a))
        xs = [c[0] for c in new_corners]
        ys = [c[1] for c in new_corners]
        self.x = min(xs)
        self.y = min(ys)
        self.width = max(xs) - min(xs)
        self.height = max(ys) - min(ys)

    def mirror(self, x1: float, y1: float, x2: float, y2: float):
        dx, dy = x2 - x1, y2 - y1
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return
        corners = self.get_corners()
        new_corners = []
        for px, py in corners:
            t = ((px - x1) * dx + (py - y1) * dy) / len_sq
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            new_corners.append((2 * proj_x - px, 2 * proj_y - py))
        xs = [c[0] for c in new_corners]
        ys = [c[1] for c in new_corners]
        self.x = min(xs)
        self.y = min(ys)
        self.width = max(xs) - min(xs)
        self.height = max(ys) - min(ys)

    def get_key_params(self) -> dict:
        d = super().get_key_params()
        d.update({'x': self.x, 'y': self.y, 'width': self.width, 'height': self.height})
        return d

    def apply_key_params(self, params: dict):
        super().apply_key_params(params)
        self.x = params.get('x', self.x)
        self.y = params.get('y', self.y)
        self.width = params.get('width', self.width)
        self.height = params.get('height', self.height)

    def get_corners(self) -> List[Tuple[float, float]]:
        return [
            (self.x, self.y),
            (self.x + self.width, self.y),
            (self.x + self.width, self.y + self.height),
            (self.x, self.y + self.height),
        ]

    def get_segments(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        c = self.get_corners()
        return [(c[0], c[1]), (c[1], c[2]), (c[2], c[3]), (c[3], c[0])]

    def is_closed(self) -> bool:
        return True

    def __repr__(self):
        return f"Rect({self.x:.1f},{self.y:.1f} {self.width:.1f}x{self.height:.1f})"


class CircleElement(BaseElement):
    """圆元素（含3D: thickness为截面拉伸高度）"""

    def __init__(self, cx: float = 0, cy: float = 0, radius: float = 0):
        super().__init__(ElementType.CIRCLE)
        self.cx = cx
        self.cy = cy
        self.radius = radius

    def get_bounds(self) -> Tuple[float, float, float, float]:
        return (self.cx - self.radius, self.cy - self.radius,
                self.cx + self.radius, self.cy + self.radius)

    def translate(self, dx: float, dy: float):
        self.cx += dx
        self.cy += dy

    def clone(self):
        elem = CircleElement(self.cx, self.cy, self.radius)
        self._clone_3d_attrs(elem)
        return elem

    def scale(self, cx: float, cy: float, factor: float):
        self.cx = cx + (self.cx - cx) * factor
        self.cy = cy + (self.cy - cy) * factor
        self.radius *= abs(factor)

    def rotate(self, cx: float, cy: float, angle_deg: float):
        a = math.radians(angle_deg)
        dx, dy = self.cx - cx, self.cy - cy
        self.cx = cx + dx * math.cos(a) - dy * math.sin(a)
        self.cy = cy + dx * math.sin(a) + dy * math.sin(a)

    def mirror(self, x1: float, y1: float, x2: float, y2: float):
        dx, dy = x2 - x1, y2 - y1
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return
        t = ((self.cx - x1) * dx + (self.cy - y1) * dy) / len_sq
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        self.cx = 2 * proj_x - self.cx
        self.cy = 2 * proj_y - self.cy

    def get_key_params(self) -> dict:
        d = super().get_key_params()
        d.update({'cx': self.cx, 'cy': self.cy, 'radius': self.radius})
        return d

    def apply_key_params(self, params: dict):
        super().apply_key_params(params)
        self.cx = params.get('cx', self.cx)
        self.cy = params.get('cy', self.cy)
        self.radius = params.get('radius', self.radius)

    def is_closed(self) -> bool:
        return True

    def __repr__(self):
        return f"Circle({self.cx:.1f},{self.cy:.1f} r={self.radius:.1f})"


class ArcElement(BaseElement):
    """圆弧元素"""

    def __init__(self, cx: float = 0, cy: float = 0, radius: float = 0,
                 start_angle: float = 0, end_angle: float = 0):
        super().__init__(ElementType.ARC)
        self.cx = cx
        self.cy = cy
        self.radius = radius
        self.start_angle = start_angle  # 度数
        self.end_angle = end_angle      # 度数

    def get_bounds(self) -> Tuple[float, float, float, float]:
        pts = self.sample_points(36)
        if not pts:
            return (self.cx - self.radius, self.cy - self.radius,
                    self.cx + self.radius, self.cy + self.radius)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def sample_points(self, num_segments: int = 36) -> List[Tuple[float, float]]:
        """采样圆弧上的点"""
        if self.radius <= 0:
            return []
        sa = math.radians(self.start_angle)
        ea = math.radians(self.end_angle)
        if ea <= sa:
            ea += 2 * math.pi
        step = (ea - sa) / num_segments
        pts = []
        for i in range(num_segments + 1):
            a = sa + step * i
            pts.append((self.cx + self.radius * math.cos(a),
                       self.cy + self.radius * math.sin(a)))
        return pts

    def translate(self, dx: float, dy: float):
        self.cx += dx
        self.cy += dy

    def clone(self):
        elem = ArcElement(self.cx, self.cy, self.radius,
                         self.start_angle, self.end_angle)
        self._clone_3d_attrs(elem)
        return elem

    def scale(self, cx: float, cy: float, factor: float):
        self.cx = cx + (self.cx - cx) * factor
        self.cy = cy + (self.cy - cy) * factor
        self.radius *= abs(factor)

    def rotate(self, cx: float, cy: float, angle_deg: float):
        a = math.radians(angle_deg)
        dx, dy = self.cx - cx, self.cy - cy
        self.cx = cx + dx * math.cos(a) - dy * math.sin(a)
        self.cy = cy + dx * math.sin(a) + dy * math.sin(a)
        self.start_angle += angle_deg
        self.end_angle += angle_deg

    def mirror(self, x1: float, y1: float, x2: float, y2: float):
        dx, dy = x2 - x1, y2 - y1
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return
        t = ((self.cx - x1) * dx + (self.cy - y1) * dy) / len_sq
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        self.cx = 2 * proj_x - self.cx
        self.cy = 2 * proj_y - self.cy
        nx, ny = dy, -dx
        angle_norm = math.degrees(math.atan2(ny, nx))
        self.start_angle = 2 * angle_norm - self.start_angle
        self.end_angle = 2 * angle_norm - self.end_angle

    def get_key_params(self) -> dict:
        d = super().get_key_params()
        d.update({'cx': self.cx, 'cy': self.cy, 'radius': self.radius,
                'start_angle': self.start_angle, 'end_angle': self.end_angle})
        return d

    def apply_key_params(self, params: dict):
        super().apply_key_params(params)
        self.cx = params.get('cx', self.cx)
        self.cy = params.get('cy', self.cy)
        self.radius = params.get('radius', self.radius)
        self.start_angle = params.get('start_angle', self.start_angle)
        self.end_angle = params.get('end_angle', self.end_angle)

    def __repr__(self):
        return f"Arc({self.cx:.1f},{self.cy:.1f} r={self.radius:.1f} {self.start_angle:.1f}~{self.end_angle:.1f})"


class PolylineElement(BaseElement):
    """多段线/多边形元素 - 由一系列点组成"""

    def __init__(self, points: List[Tuple[float, float]] = None, closed: bool = False):
        super().__init__(ElementType.POLYLINE if not closed else ElementType.POLYGON)
        self.points = list(points) if points else []
        self.closed = closed

    def get_bounds(self) -> Tuple[float, float, float, float]:
        if not self.points:
            return (0, 0, 0, 0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def translate(self, dx: float, dy: float):
        self.points = [(p[0] + dx, p[1] + dy) for p in self.points]

    def clone(self):
        elem = PolylineElement(list(self.points), self.closed)
        self._clone_3d_attrs(elem)
        return elem

    def scale(self, cx: float, cy: float, factor: float):
        self.points = [(cx + (p[0] - cx) * factor, cy + (p[1] - cy) * factor)
                       for p in self.points]

    def rotate(self, cx: float, cy: float, angle_deg: float):
        a = math.radians(angle_deg)
        cos_a, sin_a = math.cos(a), math.sin(a)
        new_pts = []
        for px, py in self.points:
            dx, dy = px - cx, py - cy
            new_pts.append((cx + dx * cos_a - dy * sin_a,
                           cy + dx * sin_a + dy * cos_a))
        self.points = new_pts

    def mirror(self, x1: float, y1: float, x2: float, y2: float):
        dx, dy = x2 - x1, y2 - y1
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return
        new_pts = []
        for px, py in self.points:
            t = ((px - x1) * dx + (py - y1) * dy) / len_sq
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            new_pts.append((2 * proj_x - px, 2 * proj_y - py))
        self.points = new_pts

    def get_segments(self) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
        segs = []
        for i in range(len(self.points) - 1):
            segs.append((self.points[i], self.points[i + 1]))
        if self.closed and len(self.points) > 2:
            segs.append((self.points[-1], self.points[0]))
        return segs

    def get_key_params(self) -> dict:
        d = super().get_key_params()
        d.update({'points': list(self.points), 'closed': self.closed})
        return d

    def apply_key_params(self, params: dict):
        super().apply_key_params(params)
        if 'points' in params:
            self.points = list(params['points'])
        if 'closed' in params:
            self.closed = params['closed']

    def is_closed(self) -> bool:
        return self.closed

    def __repr__(self):
        name = "Polygon" if self.closed else "Polyline"
        return f"{name}({len(self.points)}pts)"


class EllipseElement(BaseElement):
    """椭圆元素"""

    def __init__(self, cx: float = 0, cy: float = 0,
                 rx: float = 0, ry: float = 0, rotation: float = 0):
        super().__init__(ElementType.ELLIPSE)
        self.cx = cx
        self.cy = cy
        self.rx = rx
        self.ry = ry
        self.rotation = rotation

    def get_bounds(self) -> Tuple[float, float, float, float]:
        pts = self.sample_points(36)
        if not pts:
            return (self.cx, self.cy, self.cx, self.cy)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def sample_points(self, num_segments: int = 36) -> List[Tuple[float, float]]:
        if self.rx <= 0 or self.ry <= 0:
            return []
        a = math.radians(self.rotation)
        cos_r, sin_r = math.cos(a), math.sin(a)
        pts = []
        for i in range(num_segments):
            t = 2 * math.pi * i / num_segments
            lx = self.rx * math.cos(t)
            ly = self.ry * math.sin(t)
            wx = self.cx + lx * cos_r - ly * sin_r
            wy = self.cy + lx * sin_r + ly * cos_r
            pts.append((wx, wy))
        pts.append(pts[0])
        return pts

    def translate(self, dx: float, dy: float):
        self.cx += dx
        self.cy += dy

    def clone(self):
        elem = EllipseElement(self.cx, self.cy, self.rx, self.ry, self.rotation)
        self._clone_3d_attrs(elem)
        return elem

    def scale(self, cx: float, cy: float, factor: float):
        self.cx = cx + (self.cx - cx) * factor
        self.cy = cy + (self.cy - cy) * factor
        self.rx *= abs(factor)
        self.ry *= abs(factor)

    def rotate(self, cx: float, cy: float, angle_deg: float):
        a = math.radians(angle_deg)
        dx, dy = self.cx - cx, self.cy - cy
        self.cx = cx + dx * math.cos(a) - dy * math.sin(a)
        self.cy = cy + dx * math.sin(a) + dy * math.cos(a)
        self.rotation += angle_deg

    def mirror(self, x1: float, y1: float, x2: float, y2: float):
        dx, dy = x2 - x1, y2 - y1
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return
        t = ((self.cx - x1) * dx + (self.cy - y1) * dy) / len_sq
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        self.cx = 2 * proj_x - self.cx
        self.cy = 2 * proj_y - self.cy
        angle_norm = math.degrees(math.atan2(dy, -dx))
        self.rotation = 2 * angle_norm - self.rotation

    def get_key_params(self) -> dict:
        d = super().get_key_params()
        d.update({'cx': self.cx, 'cy': self.cy, 'rx': self.rx,
                'ry': self.ry, 'rotation': self.rotation})
        return d

    def apply_key_params(self, params: dict):
        super().apply_key_params(params)
        self.cx = params.get('cx', self.cx)
        self.cy = params.get('cy', self.cy)
        self.rx = params.get('rx', self.rx)
        self.ry = params.get('ry', self.ry)
        self.rotation = params.get('rotation', self.rotation)

    def is_closed(self) -> bool:
        return True

    def __repr__(self):
        return f"Ellipse({self.cx:.1f},{self.cy:.1f} rx={self.rx:.1f} ry={self.ry:.1f})"


class PointElement(BaseElement):
    """点元素"""

    def __init__(self, x: float = 0, y: float = 0):
        super().__init__(ElementType.POINT)
        self.x = x
        self.y = y

    def get_bounds(self) -> Tuple[float, float, float, float]:
        r = 1.0
        return (self.x - r, self.y - r, self.x + r, self.y + r)

    def translate(self, dx: float, dy: float):
        self.x += dx
        self.y += dy

    def clone(self):
        elem = PointElement(self.x, self.y)
        self._clone_3d_attrs(elem)
        return elem

    def scale(self, cx: float, cy: float, factor: float):
        self.x = cx + (self.x - cx) * factor
        self.y = cy + (self.y - cy) * factor

    def rotate(self, cx: float, cy: float, angle_deg: float):
        a = math.radians(angle_deg)
        dx, dy = self.x - cx, self.y - cy
        self.x = cx + dx * math.cos(a) - dy * math.sin(a)
        self.y = cy + dx * math.sin(a) + dy * math.cos(a)

    def mirror(self, x1: float, y1: float, x2: float, y2: float):
        dx, dy = x2 - x1, y2 - y1
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return
        t = ((self.x - x1) * dx + (self.y - y1) * dy) / len_sq
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        self.x = 2 * proj_x - self.x
        self.y = 2 * proj_y - self.y

    def get_key_params(self) -> dict:
        d = super().get_key_params()
        d.update({'x': self.x, 'y': self.y})
        return d

    def apply_key_params(self, params: dict):
        super().apply_key_params(params)
        self.x = params.get('x', self.x)
        self.y = params.get('y', self.y)

    def __repr__(self):
        return f"Point({self.x:.1f},{self.y:.1f})"


# ============================================================
# 序列化支持 (to_dict / from_dict) - 用于JSON保存/加载
# ============================================================

def _element_to_dict(elem: BaseElement) -> dict:
    """将元素序列化为字典"""
    d = {
        'type': elem.element_type.name,
        'id': elem.id,
        'style': {
            'color': elem.style.color,
            'line_width': elem.style.line_width,
            'line_type': elem.style.line_type,
            'layer_name': elem.style.layer_name,
        },
        'selected': elem.selected,
        'visible': elem.visible,
        'z_start': elem.z_start,
        'z_end': elem.z_end,
        'thickness': elem.thickness,
        'is_3d': elem.is_3d,
        'entity_3d_type': elem.entity_3d_type,
        'height': elem.height,
        'component_type': elem.component_type,
        'component_params': elem.component_params,
        'face_info': elem.face_info,
    }
    # v1.5 P3: 保存文本标注内容
    if hasattr(elem, 'text_content'):
        d['text_content'] = elem.text_content
    # 根据类型添加几何参数
    et = elem.element_type
    if et == ElementType.LINE:
        d['x1'] = elem.x1; d['y1'] = elem.y1
        d['x2'] = elem.x2; d['y2'] = elem.y2
    elif et == ElementType.RECTANGLE:
        d['x'] = elem.x; d['y'] = elem.y
        d['width'] = elem.width; d['height'] = elem.height
    elif et == ElementType.CIRCLE:
        d['cx'] = elem.cx; d['cy'] = elem.cy; d['radius'] = elem.radius
    elif et == ElementType.ARC:
        d['cx'] = elem.cx; d['cy'] = elem.cy; d['radius'] = elem.radius
        d['start_angle'] = elem.start_angle; d['end_angle'] = elem.end_angle
    elif et in (ElementType.POLYLINE, ElementType.POLYGON):
        d['points'] = elem.points
        d['closed'] = elem.closed
    elif et == ElementType.ELLIPSE:
        d['cx'] = elem.cx; d['cy'] = elem.cy
        d['rx'] = elem.rx; d['ry'] = elem.ry; d['rotation'] = elem.rotation
    elif et == ElementType.SPLINE:
        d['points'] = elem.points
    elif et == ElementType.POINT:
        d['x'] = elem.x; d['y'] = elem.y
    return d


def _element_from_dict(d: dict) -> Optional[BaseElement]:
    """从字典反序列化元素"""
    type_name = d.get('type', '')
    et = None
    for e in ElementType:
        if e.name == type_name:
            et = e
            break
    if not et:
        return None

    elem = None
    if et == ElementType.LINE:
        elem = LineElement(d.get('x1',0), d.get('y1',0), d.get('x2',0), d.get('y2',0))
    elif et == ElementType.RECTANGLE:
        elem = RectangleElement(d.get('x',0), d.get('y',0), d.get('width',0), d.get('height',0))
    elif et == ElementType.CIRCLE:
        elem = CircleElement(d.get('cx',0), d.get('cy',0), d.get('radius',0))
    elif et == ElementType.ARC:
        elem = ArcElement(d.get('cx',0), d.get('cy',0), d.get('radius',0),
                         d.get('start_angle',0), d.get('end_angle',0))
    elif et in (ElementType.POLYLINE, ElementType.POLYGON):
        elem = PolylineElement(d.get('points',[]), d.get('closed', False))
    elif et == ElementType.ELLIPSE:
        elem = EllipseElement(d.get('cx',0), d.get('cy',0),
                             d.get('rx',0), d.get('ry',0), d.get('rotation',0))
    elif et == ElementType.SPLINE:
        elem = PolylineElement(d.get('points',[]), closed=False)
    elif et == ElementType.POINT:
        elem = PointElement(d.get('x',0), d.get('y',0))
    if not elem:
        return None

    # 恢复样式
    style = d.get('style', {})
    elem.style.color = tuple(style.get('color', [0,0,0]))
    elem.style.line_width = style.get('line_width', 0.25)
    elem.style.line_type = style.get('line_type', 'solid')
    elem.style.layer_name = style.get('layer_name', '0')
    elem.selected = d.get('selected', False)
    elem.visible = d.get('visible', True)
    elem.id = d.get('id', str(uuid.uuid4()))
    elem.z_start = d.get('z_start', 0.0)
    elem.z_end = d.get('z_end', 0.0)
    elem.thickness = d.get('thickness', 0.0)
    elem.is_3d = d.get('is_3d', False)
    elem.entity_3d_type = d.get('entity_3d_type', '')
    elem.height = d.get('height', 0.0)
    elem.component_type = d.get('component_type', '')
    elem.component_params = d.get('component_params', {})
    elem.face_info = d.get('face_info', {})
    # v1.5 P3: 恢复文本标注内容
    if 'text_content' in d:
        elem.text_content = d['text_content']
    return elem


# 绑定到BaseElement类上
BaseElement.to_dict = _element_to_dict
BaseElement.from_dict = classmethod(lambda cls, d: _element_from_dict(d))
