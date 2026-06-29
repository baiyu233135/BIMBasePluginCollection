# -*- coding: utf-8 -*-
"""
CAD画板3D预览窗口 - 完整版 v2

修复内容：
- PolylineElement/PolygonElement 的 points 是元组列表 [(x,y),...]
  原代码写 p.x/p.y 导致潜在错误，已改为 p[0]/p[1] 兼容访问
- 所有涉及 points 遍历的地方统一使用兼容写法

功能：
- 等轴测/透视投影显示画板元素的3D效果
- 鼠标左键拖拽旋转视图
- 滚轮缩放
- 鼠标中键拖拽平移
- 显示高度/厚度等3D属性
- 支持所有元素类型：Line/Rectangle/Circle/Arc/Ellipse/Point/Polygon/Polyline

使用方法（在 board.py 中）：
    from preview_3d import Preview3DWindow
    # 在 __init__ 中: self.preview_3d_window = None
    # 点击按钮时:
    if self.preview_3d_window is None:
        self.preview_3d_window = Preview3DWindow(canvas_widget=self.viewport, parent=self)
    self.preview_3d_window.show()
"""

import math
import traceback

try:
    from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                                   QLabel, QPushButton, QComboBox,
                                   QSlider, QFrame, QMainWindow, QStatusBar)
    from PyQt5.QtCore import Qt, QPoint, QPointF, QRectF
    from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                              QLinearGradient, QPolygonF, QTransform, QPalette)
except ImportError:
    from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                                   QLabel, QPushButton, QComboBox,
                                   QSlider, QFrame, QMainWindow, QStatusBar)
    from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF
    from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QFont,
                              QLinearGradient, QPolygonF, QTransform, QPalette)


# ============ 辅助函数：兼容 points 访问 ============

def _get_point_xy(p):
    """兼容提取点的x,y坐标（支持元组/列表/对象）"""
    if isinstance(p, (list, tuple)):
        return float(p[0]), float(p[1])
    elif hasattr(p, 'x') and hasattr(p, 'y'):
        return float(p.x), float(p.y)
    elif isinstance(p, dict):
        return float(p.get('x', 0)), float(p.get('y', 0))
    else:
        return 0.0, 0.0


class Preview3DCanvas(QWidget):
    """3D预览画布 - 使用软件渲染的等轴测投影"""

    # 配色方案
    COLORS = {
        'background': QColor(25, 30, 40),
        'background_top': QColor(35, 40, 55),
        'grid': QColor(55, 65, 85),
        'grid_major': QColor(75, 85, 110),
        'axis_x': QColor(220, 80, 80),
        'axis_y': QColor(80, 200, 80),
        'axis_z': QColor(80, 120, 220),
        'line': QColor(220, 220, 100),
        'rectangle': QColor(100, 180, 220),
        'rectangle_top': QColor(130, 200, 240),
        'rectangle_side': QColor(70, 140, 180),
        'circle': QColor(220, 150, 100),
        'circle_top': QColor(240, 180, 130),
        'arc': QColor(180, 120, 220),
        'ellipse': QColor(100, 220, 160),
        'polygon': QColor(220, 200, 120),
        'polyline': QColor(160, 220, 180),
        'point': QColor(255, 80, 80),
        'text': QColor(230, 230, 230),
        'selection': QColor(255, 200, 50),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 400)
        p = self.palette()
        p.setColor(QPalette.Window, self.COLORS['background'])
        self.setPalette(p)
        self.setAutoFillBackground(True)

        # 相机参数
        self.rot_x = -35
        self.rot_y = 0
        self.rot_z = 45
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        # 元素数据
        self.elements = []
        self.selected_ids = set()

        # 鼠标状态
        self.last_pos = None
        self.drag_button = None

        # 渲染选项
        self.show_grid = True
        self.show_axes = True
        self.show_labels = True
        self.wireframe = False
        self.projection = 'isometric'

        # 透视参数
        self.camera_distance = 2000

    def _get_z_range(self, elem):
        """获取元素的Z范围，如果高度为0则给默认预览高度100"""
        z_bottom = getattr(elem, 'z_start', 0)
        z_top = getattr(elem, 'z_end', 0)
        if z_top <= z_bottom:
            z_top = z_bottom + 100
        return z_bottom, z_top

    def set_elements(self, elements):
        # 过滤掉面元素，避免每个面被渲染成独立几何体
        if elements:
            self.elements = [e for e in elements if not getattr(e, 'face_info', {})]
        else:
            self.elements = []
        self.update()

    def set_selected_ids(self, ids):
        self.selected_ids = set(ids) if ids else set()
        self.update()

    # ========== 3D投影核心 ==========

    def _rotate_point(self, x, y, z):
        rz = math.radians(self.rot_z)
        x1 = x * math.cos(rz) - y * math.sin(rz)
        y1 = x * math.sin(rz) + y * math.cos(rz)
        z1 = z

        rx = math.radians(self.rot_x)
        x2 = x1
        y2 = y1 * math.cos(rx) - z1 * math.sin(rx)
        z2 = y1 * math.sin(rx) + z1 * math.cos(rx)

        ry = math.radians(self.rot_y)
        x3 = x2 * math.cos(ry) + z2 * math.sin(ry)
        y3 = y2
        z3 = -x2 * math.sin(ry) + z2 * math.cos(ry)

        return x3, y3, z3

    def _project(self, x, y, z):
        rx, ry, rz = self._rotate_point(x, y, z)

        if self.projection == 'perspective':
            d = self.camera_distance
            if rz + d < 1:
                rz = 1 - d
            factor = d / (rz + d)
            sx = rx * factor * self.scale
            sy = ry * factor * self.scale
        else:
            sx = rx * self.scale
            sy = ry * self.scale

        screen_x = self.width() / 2 + sx + self.offset_x
        screen_y = self.height() / 2 - sy + self.offset_y
        return screen_x, screen_y, rz

    def _project_point(self, pt):
        if isinstance(pt, dict):
            return self._project(pt.get('x', 0), pt.get('y', 0), pt.get('z', 0))
        elif hasattr(pt, 'x') and hasattr(pt, 'y'):
            z = getattr(pt, 'z', 0)
            return self._project(pt.x, pt.y, z)
        elif len(pt) >= 3:
            return self._project(pt[0], pt[1], pt[2])
        elif len(pt) == 2:
            return self._project(pt[0], pt[1], 0)
        return self._project(0, 0, 0)

    # ========== 绘制辅助 ==========

    def _draw_line_3d(self, painter, p1, p2, color=None, width=1, style=Qt.SolidLine):
        x1, y1, z1 = self._project_point(p1)
        x2, y2, z2 = self._project_point(p2)
        pen = QPen(color or self.COLORS['line'], width, style)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    def _draw_polygon_3d(self, painter, points, fill_color, edge_color=None, edge_width=1):
        projected = []
        avg_z = 0
        for pt in points:
            sx, sy, sz = self._project_point(pt)
            projected.append((sx, sy, sz))
            avg_z += sz
        avg_z /= len(points) if points else 1

        polygon = QPolygonF()
        for sx, sy, _ in projected:
            polygon.append(QPointF(sx, sy))

        if not self.wireframe and fill_color:
            depth_factor = max(0.5, min(1.0, 1.0 - avg_z / 5000))
            adjusted_color = QColor(fill_color)
            adjusted_color.setRed(int(adjusted_color.red() * depth_factor))
            adjusted_color.setGreen(int(adjusted_color.green() * depth_factor))
            adjusted_color.setBlue(int(adjusted_color.blue() * depth_factor))
            painter.setBrush(QBrush(adjusted_color))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(polygon)

        if edge_color:
            pen = QPen(edge_color, edge_width)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(polygon)

    def _draw_text_3d(self, painter, pt, text, color=None, font_size=10):
        sx, sy, _ = self._project_point(pt)
        painter.setPen(QPen(color or self.COLORS['text']))
        font = QFont("Microsoft YaHei", font_size)
        painter.setFont(font)
        painter.drawText(int(sx) + 5, int(sy), text)

    # ========== 元素绘制 ==========

    def _draw_line_element(self, painter, elem):
        z1, z2 = self._get_z_range(elem)
        thickness = getattr(elem, 'thickness', 0)
        is_sel = getattr(elem, 'id', '') in self.selected_ids
        color = self.COLORS['selection'] if is_sel else self.COLORS['line']

        p1 = {'x': elem.x1, 'y': elem.y1, 'z': z1}
        p2 = {'x': elem.x2, 'y': elem.y2, 'z': z2}

        if thickness > 0 and z1 != z2:
            self._draw_extruded_line(painter, p1, p2, thickness, color)
        else:
            self._draw_line_3d(painter, p1, p2, color, 2)

        if self.show_labels and thickness > 0:
            mid = {'x': (elem.x1 + elem.x2) / 2,
                   'y': (elem.y1 + elem.y2) / 2,
                   'z': max(z1, z2)}
            self._draw_text_3d(painter, mid, f"T={thickness}", color, 8)

    def _draw_extruded_line(self, painter, p1, p2, thickness, color):
        dx = p2['x'] - p1['x']
        dy = p2['y'] - p1['y']
        length = math.sqrt(dx * dx + dy * dy)
        if length < 0.001:
            length = 1

        perp_x = -dy / length * thickness / 2
        perp_y = dx / length * thickness / 2

        bottom = [
            {'x': p1['x'] + perp_x, 'y': p1['y'] + perp_y, 'z': p1['z']},
            {'x': p2['x'] + perp_x, 'y': p2['y'] + perp_y, 'z': p2['z']},
            {'x': p2['x'] - perp_x, 'y': p2['y'] - perp_y, 'z': p2['z']},
            {'x': p1['x'] - perp_x, 'y': p1['y'] - perp_y, 'z': p1['z']},
        ]

        top = [
            {'x': p1['x'] + perp_x, 'y': p1['y'] + perp_y, 'z': p2['z']},
            {'x': p2['x'] + perp_x, 'y': p2['y'] + perp_y, 'z': p2['z']},
            {'x': p2['x'] - perp_x, 'y': p2['y'] - perp_y, 'z': p2['z']},
            {'x': p1['x'] - perp_x, 'y': p1['y'] - perp_y, 'z': p2['z']},
        ]

        faces = []
        for i in range(4):
            j = (i + 1) % 4
            face = [bottom[i], bottom[j], top[j], top[i]]
            avg_z = sum(self._project_point(p)[2] for p in face) / 4
            faces.append((avg_z, face, color))

        faces.sort(key=lambda f: f[0], reverse=True)
        for _, face, c in faces:
            self._draw_polygon_3d(painter, face, c, QColor(c).darker(120), 1)

    def _draw_rectangle_element(self, painter, elem):
        x, y = elem.x, elem.y
        w, h = elem.width, elem.height
        z_bottom, z_top = self._get_z_range(elem)
        is_3d = True
        is_sel = getattr(elem, 'id', '') in self.selected_ids
        color = self.COLORS['selection'] if is_sel else self.COLORS['rectangle']

        bottom = [
            {'x': x, 'y': y, 'z': z_bottom},
            {'x': x + w, 'y': y, 'z': z_bottom},
            {'x': x + w, 'y': y + h, 'z': z_bottom},
            {'x': x, 'y': y + h, 'z': z_bottom},
        ]

        if is_3d and z_top > z_bottom:
            top_face = [
                {'x': x, 'y': y, 'z': z_top},
                {'x': x + w, 'y': y, 'z': z_top},
                {'x': x + w, 'y': y + h, 'z': z_top},
                {'x': x, 'y': y + h, 'z': z_top},
            ]

            faces = []
            avg_z = sum(self._project_point(p)[2] for p in bottom) / 4
            faces.append((avg_z, bottom, self.COLORS['rectangle_side']))

            for i in range(4):
                j = (i + 1) % 4
                side = [bottom[i], bottom[j], top_face[j], top_face[i]]
                avg_z = sum(self._project_point(p)[2] for p in side) / 4
                faces.append((avg_z, side, self.COLORS['rectangle_side']))

            avg_z = sum(self._project_point(p)[2] for p in top_face) / 4
            faces.append((avg_z, top_face, self.COLORS['rectangle_top']))

            faces.sort(key=lambda f: f[0], reverse=True)
            for _, face, c in faces:
                self._draw_polygon_3d(painter, face, c, QColor(c).darker(130), 1)

            if self.show_labels:
                center = {'x': x + w / 2, 'y': y + h / 2, 'z': z_top}
                height = z_top - z_bottom
                self._draw_text_3d(painter, center, f"H={height:.0f}", color, 9)
        else:
            self._draw_polygon_3d(painter, bottom, color, QColor(color).darker(130), 2)

    def _draw_circle_element(self, painter, elem):
        cx, cy = elem.cx, elem.cy
        r = elem.radius
        z_bottom, z_top = self._get_z_range(elem)
        is_3d = True
        is_sel = getattr(elem, 'id', '') in self.selected_ids
        color = self.COLORS['selection'] if is_sel else self.COLORS['circle']

        segments = max(16, int(r / 10))
        segments = min(segments, 64)

        if is_3d and z_top > z_bottom:
            bottom_circle = []
            top_circle = []
            for i in range(segments):
                angle = 2 * math.pi * i / segments
                px = cx + r * math.cos(angle)
                py = cy + r * math.sin(angle)
                bottom_circle.append({'x': px, 'y': py, 'z': z_bottom})
                top_circle.append({'x': px, 'y': py, 'z': z_top})

            for i in range(segments):
                j = (i + 1) % segments
                side = [bottom_circle[i], bottom_circle[j],
                        top_circle[j], top_circle[i]]
                self._draw_polygon_3d(
                    painter, side,
                    self.COLORS['circle'],
                    QColor(self.COLORS['circle']).darker(120), 1
                )

            self._draw_polygon_3d(
                painter, top_circle,
                self.COLORS['circle_top'],
                QColor(self.COLORS['circle_top']).darker(110), 1
            )

            if self.show_labels:
                center = {'x': cx, 'y': cy, 'z': z_top}
                height = z_top - z_bottom
                self._draw_text_3d(painter, center, f"H={height:.0f}", color, 9)
        else:
            circle_pts = []
            for i in range(segments):
                angle = 2 * math.pi * i / segments
                circle_pts.append({
                    'x': cx + r * math.cos(angle),
                    'y': cy + r * math.sin(angle),
                    'z': z_bottom
                })
            self._draw_polygon_3d(painter, circle_pts, color,
                                  QColor(color).darker(120), 2)

    def _draw_arc_element(self, painter, elem):
        cx, cy = elem.cx, elem.cy
        r = elem.radius
        sa = elem.start_angle
        ea = elem.end_angle
        z_bottom, z_top = self._get_z_range(elem)
        is_sel = getattr(elem, 'id', '') in self.selected_ids
        color = self.COLORS['selection'] if is_sel else self.COLORS['arc']

        if ea < sa:
            ea += 2 * math.pi

        arc_length = ea - sa
        segments = max(8, int(arc_length * r / 20))
        segments = min(segments, 64)

        arc_pts = []
        for i in range(segments + 1):
            angle = sa + arc_length * i / segments
            arc_pts.append({
                'x': cx + r * math.cos(angle),
                'y': cy + r * math.sin(angle),
                'z': z_bottom
            })

        if z_top > z_bottom:
            for i in range(len(arc_pts) - 1):
                p1 = arc_pts[i]
                p2 = arc_pts[i + 1]
                p1_top = {**p1, 'z': z_top}
                p2_top = {**p2, 'z': z_top}
                side = [p1, p2, p2_top, p1_top]
                self._draw_polygon_3d(painter, side, color,
                                      QColor(color).darker(120), 1)
        else:
            for i in range(len(arc_pts) - 1):
                self._draw_line_3d(painter, arc_pts[i], arc_pts[i + 1], color, 2)

    def _draw_ellipse_element(self, painter, elem):
        cx, cy = elem.cx, elem.cy
        rx = elem.rx
        ry = elem.ry
        rotation = getattr(elem, 'rotation', 0)
        z_bottom, z_top = self._get_z_range(elem)
        is_sel = getattr(elem, 'id', '') in self.selected_ids
        color = self.COLORS['selection'] if is_sel else self.COLORS['ellipse']

        segments = 32
        ellipse_pts = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            px = cx + rx * math.cos(angle) * math.cos(rotation) - ry * math.sin(angle) * math.sin(rotation)
            py = cy + rx * math.cos(angle) * math.sin(rotation) + ry * math.sin(angle) * math.cos(rotation)
            ellipse_pts.append({'x': px, 'y': py, 'z': z_bottom})

        if z_top > z_bottom:
            for i in range(len(ellipse_pts)):
                j = (i + 1) % len(ellipse_pts)
                p1 = ellipse_pts[i]
                p2 = ellipse_pts[j]
                p1_top = {**p1, 'z': z_top}
                p2_top = {**p2, 'z': z_top}
                side = [p1, p2, p2_top, p1_top]
                self._draw_polygon_3d(painter, side, color,
                                      QColor(color).darker(120), 1)
        else:
            self._draw_polygon_3d(painter, ellipse_pts, color,
                                  QColor(color).darker(120), 2)

    def _draw_point_element(self, painter, elem):
        x, y = elem.x, elem.y
        z = getattr(elem, 'z', 0)
        size = getattr(elem, 'size', 5)
        is_sel = getattr(elem, 'id', '') in self.selected_ids
        color = self.COLORS['selection'] if is_sel else self.COLORS['point']

        sx, sy, _ = self._project(x, y, z)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(int(sx - size), int(sy - size), int(size * 2), int(size * 2))

    def _draw_polygon_element(self, painter, elem):
        """绘制多边形 - 兼容元组列表 points [(x,y),...]"""
        z_bottom, z_top = self._get_z_range(elem)
        is_3d = True
        is_sel = getattr(elem, 'id', '') in self.selected_ids
        color = self.COLORS['selection'] if is_sel else self.COLORS['polygon']

        if hasattr(elem, 'points') and elem.points:
            bottom = []
            for p in elem.points:
                px, py = _get_point_xy(p)
                bottom.append({'x': px, 'y': py, 'z': z_bottom})

            if is_3d and z_top > z_bottom:
                top_face = []
                for p in elem.points:
                    px, py = _get_point_xy(p)
                    top_face.append({'x': px, 'y': py, 'z': z_top})

                for i in range(len(bottom)):
                    j = (i + 1) % len(bottom)
                    side = [bottom[i], bottom[j], top_face[j], top_face[i]]
                    self._draw_polygon_3d(painter, side, color,
                                          QColor(color).darker(120), 1)

                self._draw_polygon_3d(painter, top_face,
                                      QColor(color).lighter(110),
                                      QColor(color).darker(110), 1)
            else:
                self._draw_polygon_3d(painter, bottom, color,
                                      QColor(color).darker(120), 2)

    def _draw_polyline_element(self, painter, elem):
        """绘制多段线/多边形 - 兼容元组列表 points [(x,y),...]"""
        z_bottom, z_top = self._get_z_range(elem)
        is_sel = getattr(elem, 'id', '') in self.selected_ids
        color = self.COLORS['selection'] if is_sel else self.COLORS['polyline']

        if hasattr(elem, 'points') and len(elem.points) > 1:
            points = []
            for p in elem.points:
                px, py = _get_point_xy(p)
                points.append({'x': px, 'y': py, 'z': z_bottom})

            is_closed = getattr(elem, 'closed', False) or elem.element_type.name == 'POLYGON'

            if z_top > z_bottom:
                # 绘制侧面（所有边）
                edges = len(points) - 1
                if is_closed:
                    edges = len(points)  # 闭合多边形多一条边
                for i in range(edges):
                    p1 = points[i]
                    p2 = points[(i + 1) % len(points)]
                    p1_top = {**p1, 'z': z_top}
                    p2_top = {**p2, 'z': z_top}
                    side = [p1, p2, p2_top, p1_top]
                    self._draw_polygon_3d(painter, side, color,
                                          QColor(color).darker(120), 1)
                # 闭合多边形：绘制顶面和底面
                if is_closed:
                    top_pts = [{**p, 'z': z_top} for p in points]
                    bottom_pts = list(points)
                    self._draw_polygon_3d(painter, top_pts, color,
                                          QColor(color).darker(150), 2)
                    self._draw_polygon_3d(painter, bottom_pts, color,
                                          QColor(color).darker(150), 2)
            else:
                for i in range(len(points) - 1):
                    self._draw_line_3d(painter, points[i], points[i + 1], color, 2)
                if is_closed and len(points) > 2:
                    self._draw_line_3d(painter, points[-1], points[0], color, 2)

    # ========== 网格和坐标轴 ==========

    def _draw_grid(self, painter):
        if not self.show_grid:
            return
        grid_size = 1000
        grid_step = 100
        major_step = 500

        for i in range(-grid_size, grid_size + 1, grid_step):
            is_major = (i % major_step == 0)
            color = self.COLORS['grid_major'] if is_major else self.COLORS['grid']
            width = 1 if is_major else 0.5
            self._draw_line_3d(painter,
                {'x': i, 'y': -grid_size, 'z': 0},
                {'x': i, 'y': grid_size, 'z': 0},
                color, width)
            self._draw_line_3d(painter,
                {'x': -grid_size, 'y': i, 'z': 0},
                {'x': grid_size, 'y': i, 'z': 0},
                color, width)

    def _draw_axes(self, painter):
        if not self.show_axes:
            return
        axis_length = 800

        self._draw_line_3d(painter,
            {'x': 0, 'y': 0, 'z': 0},
            {'x': axis_length, 'y': 0, 'z': 0},
            self.COLORS['axis_x'], 3)
        self._draw_line_3d(painter,
            {'x': 0, 'y': 0, 'z': 0},
            {'x': 0, 'y': axis_length, 'z': 0},
            self.COLORS['axis_y'], 3)
        self._draw_line_3d(painter,
            {'x': 0, 'y': 0, 'z': 0},
            {'x': 0, 'y': 0, 'z': axis_length},
            self.COLORS['axis_z'], 3)

        font = QFont("Arial", 14, QFont.Bold)
        painter.setFont(font)

        sx, sy, _ = self._project(axis_length + 50, 0, 0)
        painter.setPen(QPen(self.COLORS['axis_x']))
        painter.drawText(int(sx), int(sy), "X")

        sx, sy, _ = self._project(0, axis_length + 50, 0)
        painter.setPen(QPen(self.COLORS['axis_y']))
        painter.drawText(int(sx), int(sy), "Y")

        sx, sy, _ = self._project(0, 0, axis_length + 50)
        painter.setPen(QPen(self.COLORS['axis_z']))
        painter.drawText(int(sx), int(sy), "Z")

    # ========== 主绘制 ==========

    def _log_draw_error(self, msg):
        try:
            import os
            from datetime import datetime
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CADBoard_error.log")
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] [3DPreview] {msg}\n")
        except Exception:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, self.COLORS['background_top'])
        gradient.setColorAt(1, self.COLORS['background'])
        painter.fillRect(self.rect(), gradient)

        self._draw_grid(painter)
        self._draw_axes(painter)

        sorted_elements = []
        for elem in self.elements:
            z = self._get_element_z(elem)
            sorted_elements.append((z, elem))
        sorted_elements.sort(key=lambda x: x[0], reverse=True)

        for _, elem in sorted_elements:
            try:
                self._draw_element(painter, elem)
            except Exception as e:
                self._log_draw_error(f"draw_element error: {e}\n{traceback.format_exc()}")

        self._draw_info(painter)

    def _get_element_z(self, elem):
        elem_type = elem.__class__.__name__
        try:
            if elem_type == 'LineElement':
                return max(getattr(elem, 'z_start', 0), getattr(elem, 'z_end', 0))
            elif elem_type == 'PointElement':
                return getattr(elem, 'z', 0)
            elif elem_type in ('RectangleElement', 'CircleElement', 'ArcElement',
                                'EllipseElement', 'PolygonElement', 'PolylineElement'):
                return getattr(elem, 'z_end', getattr(elem, 'z_start', 0))
        except Exception:
            pass
        return 0

    def _draw_element(self, painter, elem):
        elem_type = elem.__class__.__name__
        draw_methods = {
            'LineElement': self._draw_line_element,
            'RectangleElement': self._draw_rectangle_element,
            'CircleElement': self._draw_circle_element,
            'ArcElement': self._draw_arc_element,
            'EllipseElement': self._draw_ellipse_element,
            'PointElement': self._draw_point_element,
            'PolygonElement': self._draw_polygon_element,
            'PolylineElement': self._draw_polyline_element,
        }
        method = draw_methods.get(elem_type)
        if method:
            try:
                method(painter, elem)
            except Exception as e:
                self._log_draw_error(f"{elem_type} draw error: {e}\n{traceback.format_exc()}")

    def _draw_info(self, painter):
        info_lines = [
            f"Elements: {len(self.elements)}",
            f"Scale: {self.scale:.2f}x",
            f"Rot: X={self.rot_x:.0f} Y={self.rot_y:.0f} Z={self.rot_z:.0f}",
            "",
            "Controls:",
            "  Left drag: Rotate",
            "  Wheel: Zoom",
            "  Middle drag: Pan",
        ]
        painter.setPen(QPen(QColor(200, 200, 200)))
        font = QFont("Consolas", 9)
        painter.setFont(font)
        y = 20
        for line in info_lines:
            painter.drawText(10, y, line)
            y += 14

    # ========== 鼠标交互 ==========

    def mousePressEvent(self, event):
        self.last_pos = event.pos()
        if event.button() == Qt.LeftButton:
            self.drag_button = 'rotate'
        elif event.button() == Qt.MiddleButton:
            self.drag_button = 'pan'

    def mouseMoveEvent(self, event):
        if self.last_pos is None:
            return
        dx = event.pos().x() - self.last_pos.x()
        dy = event.pos().y() - self.last_pos.y()

        if self.drag_button == 'rotate':
            self.rot_z += dx * 0.5
            self.rot_x += dy * 0.5
            self.rot_x = max(-89, min(89, self.rot_x))
            self.update()
        elif self.drag_button == 'pan':
            self.offset_x += dx
            self.offset_y += dy
            self.update()

        self.last_pos = event.pos()

    def mouseReleaseEvent(self, event):
        self.last_pos = None
        self.drag_button = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        zoom_factor = 1.1 if delta > 0 else 0.9
        self.scale *= zoom_factor
        self.scale = max(0.01, min(100.0, self.scale))
        self.update()

    def reset_view(self):
        self.rot_x = -35
        self.rot_y = 0
        self.rot_z = 45
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.update()

    def fit_to_view(self):
        if not self.elements:
            self.reset_view()
            return

        min_x = min_y = min_z = float('inf')
        max_x = max_y = max_z = float('-inf')

        for elem in self.elements:
            try:
                et = elem.__class__.__name__
                if et == 'LineElement':
                    pts = [(elem.x1, elem.y1, getattr(elem, 'z_start', 0)),
                           (elem.x2, elem.y2, getattr(elem, 'z_end', 0))]
                elif et == 'PointElement':
                    pts = [(elem.x, elem.y, getattr(elem, 'z', 0))]
                elif et in ('RectangleElement', 'CircleElement', 'ArcElement',
                            'EllipseElement'):
                    if hasattr(elem, 'center_x'):
                        r = getattr(elem, 'radius', 0) or max(getattr(elem, 'radius_x', 0), getattr(elem, 'radius_y', 0))
                        pts = [(elem.center_x, elem.center_y, getattr(elem, 'z_start', 0)),
                               (elem.center_x, elem.center_y, getattr(elem, 'z_end', 0))]
                    elif hasattr(elem, 'x'):
                        pts = [(elem.x, elem.y, getattr(elem, 'z_start', 0)),
                               (elem.x + getattr(elem, 'width', 0), elem.y + getattr(elem, 'height', 0), getattr(elem, 'z_end', 0))]
                    else:
                        pts = [(0, 0, 0)]
                elif et in ('PolygonElement', 'PolylineElement'):
                    # 兼容元组列表 points
                    if hasattr(elem, 'points') and elem.points:
                        pts = []
                        for p in elem.points:
                            px, py = _get_point_xy(p)
                            pts.append((px, py, getattr(elem, 'z_start', 0)))
                    else:
                        pts = [(0, 0, 0)]
                else:
                    pts = [(0, 0, 0)]

                for px, py, pz in pts:
                    min_x = min(min_x, px)
                    min_y = min(min_y, py)
                    min_z = min(min_z, pz)
                    max_x = max(max_x, px)
                    max_y = max(max_y, py)
                    max_z = max(max_z, pz)
            except Exception:
                pass

        if min_x == float('inf'):
            self.reset_view()
            return

        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2
        cz = (min_z + max_z) / 2

        size_x = max_x - min_x
        size_y = max_y - min_y
        size = max(size_x, size_y, 1)

        view_size = min(self.width(), self.height()) * 0.7
        self.scale = view_size / size

        screen_cx, screen_cy, _ = self._project(cx, cy, cz)
        self.offset_x = self.width() / 2 - screen_cx
        self.offset_y = self.height() / 2 - screen_cy
        self.update()


class Preview3DWindow(QMainWindow):
    """3D预览独立窗口"""

    def __init__(self, canvas_widget=None, parent=None):
        super().__init__(parent)
        self.canvas_widget = canvas_widget
        self.setWindowTitle("CADBoard - 3D Preview")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(2, 2, 2, 2)

        # 工具栏
        toolbar = QHBoxLayout()

        self.combo_projection = QComboBox()
        self.combo_projection.addItems(["Isometric", "Perspective"])
        self.combo_projection.currentTextChanged.connect(self._on_projection_changed)
        toolbar.addWidget(QLabel("Projection:"))
        toolbar.addWidget(self.combo_projection)

        toolbar.addSpacing(10)

        self.btn_grid = QPushButton("Grid")
        self.btn_grid.setCheckable(True)
        self.btn_grid.setChecked(True)
        self.btn_grid.clicked.connect(self._on_grid_toggled)
        toolbar.addWidget(self.btn_grid)

        self.btn_axes = QPushButton("Axes")
        self.btn_axes.setCheckable(True)
        self.btn_axes.setChecked(True)
        self.btn_axes.clicked.connect(self._on_axes_toggled)
        toolbar.addWidget(self.btn_axes)

        self.btn_wire = QPushButton("Wireframe")
        self.btn_wire.setCheckable(True)
        self.btn_wire.clicked.connect(self._on_wireframe_toggled)
        toolbar.addWidget(self.btn_wire)

        toolbar.addStretch()

        self.btn_reset = QPushButton("Reset View")
        self.btn_reset.clicked.connect(self._on_reset)
        toolbar.addWidget(self.btn_reset)

        self.btn_fit = QPushButton("Fit to View")
        self.btn_fit.clicked.connect(self._on_fit)
        toolbar.addWidget(self.btn_fit)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._on_refresh)
        toolbar.addWidget(self.btn_refresh)

        self.btn_sync = QPushButton("Sync to BIMBase")
        self.btn_sync.setStyleSheet("background-color: #4a90d9; color: white; font-weight: bold;")
        self.btn_sync.clicked.connect(self._on_sync)
        toolbar.addWidget(self.btn_sync)

        layout.addLayout(toolbar)

        # 3D画布
        self.preview_canvas = Preview3DCanvas()
        layout.addWidget(self.preview_canvas, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Drag to rotate, Wheel to zoom, Middle drag to pan")

        if canvas_widget:
            self._on_refresh()

    def _on_projection_changed(self, text):
        self.preview_canvas.projection = text.lower()
        self.preview_canvas.update()

    def _on_grid_toggled(self, checked):
        self.preview_canvas.show_grid = checked
        self.preview_canvas.update()

    def _on_axes_toggled(self, checked):
        self.preview_canvas.show_axes = checked
        self.preview_canvas.update()

    def _on_wireframe_toggled(self, checked):
        self.preview_canvas.wireframe = checked
        self.preview_canvas.update()

    def _on_reset(self):
        self.preview_canvas.reset_view()
        self.status_bar.showMessage("View reset")

    def _on_fit(self):
        self.preview_canvas.fit_to_view()
        self.status_bar.showMessage("Fitted to view")

    def _on_refresh(self):
        if self.canvas_widget:
            try:
                if hasattr(self.canvas_widget, 'board') and hasattr(self.canvas_widget.board, 'elements'):
                    elements = self.canvas_widget.board.elements
                    self.preview_canvas.set_elements(elements)
                    sel_ids = [e.id for e in elements if getattr(e, 'selected', False) and hasattr(e, 'id')]
                    self.preview_canvas.set_selected_ids(sel_ids)
                    count = len(elements)
                    self.status_bar.showMessage(f"Refreshed: {count} elements loaded")
                elif hasattr(self.canvas_widget, 'elements'):
                    elements = self.canvas_widget.elements
                    self.preview_canvas.set_elements(elements)
                    count = len(elements)
                    self.status_bar.showMessage(f"Refreshed: {count} elements loaded")
                else:
                    self.status_bar.showMessage("Canvas has no elements attribute")
            except Exception as e:
                self.status_bar.showMessage(f"Refresh error: {str(e)}")
        else:
            self.status_bar.showMessage("No canvas widget connected")

    def _on_sync(self):
        try:
            from bimbase_sync import sync_to_bimbase
            if self.canvas_widget and hasattr(self.canvas_widget, 'board'):
                board = self.canvas_widget.board
                count, errors, replaced, manual = sync_to_bimbase(board)
                msg = f"Sync: {count} placed"
                if errors:
                    msg += f", {len(errors)} errors"
                self.status_bar.showMessage(msg)
            else:
                self.status_bar.showMessage("No canvas/board connected")
        except Exception as e:
            self.status_bar.showMessage(f"Sync error: {str(e)}")

    def refresh_from_canvas(self, elements, selected_ids=None):
        self.preview_canvas.set_elements(elements)
        if selected_ids:
            self.preview_canvas.set_selected_ids(selected_ids)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
