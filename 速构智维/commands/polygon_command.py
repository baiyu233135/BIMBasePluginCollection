# -*- coding: utf-8 -*-
"""多边形命令 - POL（支持命令行输入边数）"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import PolylineElement


class PolygonCommand(BaseCommand):
    name = "多边形"
    shortcut = "POL"
    description = "绘制正多边形"

    def __init__(self, board):
        super().__init__(board)
        self._center = None
        self._num_sides = 6
        self._preview_radius = 0

    def on_activate(self):
        self._center = None
        self._preview_radius = 0
        self.board.status_bar.showMessage(self.get_prompt())

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._center is None:
                self._center = (world_x, world_y)
                self.board.viewport.update()
                return True
            else:
                r = math.hypot(world_x - self._center[0], world_y - self._center[1])
                self._create_polygon(r)
                self.board.viewport.update()
                return True
        elif button == 2:
            self._center = None
            self._preview_radius = 0
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _create_polygon(self, r):
        points = []
        for i in range(self._num_sides):
            a = 2 * math.pi * i / self._num_sides - math.pi / 2
            points.append((
                self._center[0] + r * math.cos(a),
                self._center[1] + r * math.sin(a)
            ))
        poly = PolylineElement(points, closed=True)
        self.board.apply_current_layer_style(poly)
        self.board.add_element(poly)
        self._center = None
        self._preview_radius = 0

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center:
            self._preview_radius = math.hypot(world_x - self._center[0], world_y - self._center[1])
            self.board.status_bar.showMessage(
                f"多边形: 中心({self._center[0]:.2f},{self._center[1]:.2f}) | "
                f"半径: {self._preview_radius:.2f}mm | 边数: {self._num_sides}"
            )
            self.board.viewport.update()
            return True
        else:
            self.board.status_bar.showMessage(f"光标: ({world_x:.2f}, {world_y:.2f}) - 点击指定中心点")
        return False

    def on_cmd_confirm(self, text):
        text = text.strip()
        try:
            n = int(text)
            if n >= 3:
                self._num_sides = n
                self.board.status_bar.showMessage(f"多边形: 边数设为 {n}")
                return True
        except ValueError:
            pass
        # 解析坐标作为中心
        text = text.replace('(', '').replace(')', '').replace('，', ',')
        parts = text.split(',')
        if len(parts) == 2:
            try:
                x = float(parts[0].strip())
                y = float(parts[1].strip())
                self._center = (x, y)
                self.board.status_bar.showMessage("多边形: 指定半径或输入半径数值")
                self.board.viewport.update()
                return True
            except ValueError:
                pass
        # 解析半径
        try:
            r = float(text)
            if self._center:
                self._create_polygon(r)
                self.board.viewport.update()
                return True
        except ValueError:
            pass
        return False

    def get_prompt(self):
        if self._center is None:
            return f"多边形: 指定中心点 (默认{self._num_sides}边，输入数字改边数)"
        return f"多边形: 指定半径 (左键确定，右键取消)"

    def draw_preview(self, painter, coord_system):
        if self._center and self._preview_radius > 0:
            points = []
            for i in range(self._num_sides):
                a = 2 * math.pi * i / self._num_sides - math.pi / 2
                px = self._center[0] + self._preview_radius * math.cos(a)
                py = self._center[1] + self._preview_radius * math.sin(a)
                points.append(coord_system.world_to_screen(px, py))
            pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for i in range(len(points)):
                p1 = points[i]
                p2 = points[(i + 1) % len(points)]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])
            return True
        return False
