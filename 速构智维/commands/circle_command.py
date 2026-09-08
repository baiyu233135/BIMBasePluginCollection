# -*- coding: utf-8 -*-
"""圆命令 - C（支持命令行输入坐标和半径）"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import CircleElement


class CircleCommand(BaseCommand):
    name = "圆"
    shortcut = "C"
    description = "绘制圆"

    def __init__(self, board):
        super().__init__(board)
        self._center = None
        self._preview_radius = 0

    def on_activate(self):
        self._center = None
        self._preview_radius = 0
        self.board.status_bar.showMessage(self.get_prompt())

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._center is None:
                self._center = (world_x, world_y)
                self.board.status_bar.showMessage(self.get_prompt())
                self.board.viewport.update()
                return True
            else:
                r = math.hypot(world_x - self._center[0], world_y - self._center[1])
                circle = CircleElement(self._center[0], self._center[1], r)
                self.board.apply_current_layer_style(circle)
                self.board.add_element(circle)
                self._center = None
                self._preview_radius = 0
                self.board.status_bar.showMessage(self.get_prompt())
                self.board.viewport.update()
                return True
        elif button == 2:
            self._center = None
            self._preview_radius = 0
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center:
            self._preview_radius = math.hypot(world_x - self._center[0], world_y - self._center[1])
            self.board.status_bar.showMessage(
                f"圆心: ({self._center[0]:.2f}, {self._center[1]:.2f}) | 半径: {self._preview_radius:.2f}mm"
            )
            self.board.viewport.update()
            return True
        else:
            self.board.status_bar.showMessage(f"光标: ({world_x:.2f}, {world_y:.2f}) - 点击指定圆心")
        return False

    def on_cmd_confirm(self, text):
        text = text.strip()
        parsed = self._parse_coord(text)
        if parsed and self._center is None:
            self._center = parsed
            self.board.status_bar.showMessage(self.get_prompt())
            self.board.viewport.update()
            return True
        try:
            r = float(text)
            if self._center:
                circle = CircleElement(self._center[0], self._center[1], r)
                self.board.apply_current_layer_style(circle)
                self.board.add_element(circle)
                self._center = None
                self._preview_radius = 0
                self.board.viewport.update()
                return True
        except ValueError:
            pass
        return False

    def _parse_coord(self, text):
        text = text.strip().replace('(', '').replace(')', '').replace('，', ',')
        parts = text.split(',')
        if len(parts) == 2:
            try:
                return (float(parts[0].strip()), float(parts[1].strip()))
            except ValueError:
                pass
        return None

    def get_prompt(self):
        if self._center is None:
            return "圆: 指定圆心 (坐标/点击，右键取消)"
        return "圆: 指定半径 (点击/输入数值，右键取消)"

    def draw_preview(self, painter, coord_system):
        if self._center and self._preview_radius > 0:
            cx, cy = coord_system.world_to_screen(self._center[0], self._center[1])
            r = coord_system.world_dist_to_screen(self._preview_radius)
            pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            return True
        return False
