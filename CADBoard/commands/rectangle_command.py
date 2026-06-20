# -*- coding: utf-8 -*-
"""矩形命令 - REC（支持命令行输入长宽）"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import RectangleElement


class RectangleCommand(BaseCommand):
    name = "矩形"
    shortcut = "REC"
    description = "绘制矩形"

    def __init__(self, board):
        super().__init__(board)
        self._corner1 = None
        self._preview_corner = None

    def on_activate(self):
        self._corner1 = None
        self._preview_corner = None
        self.board.status_bar.showMessage(self.get_prompt())

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._corner1 is None:
                self._corner1 = (world_x, world_y)
                self.board.viewport.update()
                return True
            else:
                x = min(self._corner1[0], world_x)
                y = min(self._corner1[1], world_y)
                w = abs(world_x - self._corner1[0])
                h = abs(world_y - self._corner1[1])
                rect = RectangleElement(x, y, w, h)
                self.board.apply_current_layer_style(rect)
                self.board.add_element(rect)
                self._corner1 = None
                self._preview_corner = None
                self.board.viewport.update()
                return True
        elif button == 2:
            self._corner1 = None
            self._preview_corner = None
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._corner1:
            self._preview_corner = (world_x, world_y)
            w = abs(world_x - self._corner1[0])
            h = abs(world_y - self._corner1[1])
            self.board.status_bar.showMessage(f"矩形: {w:.2f} x {h:.2f} mm")
            self.board.viewport.update()
            return True
        else:
            self.board.status_bar.showMessage(f"光标: ({world_x:.2f}, {world_y:.2f}) - 点击指定第一个角点")
        return False

    def on_cmd_confirm(self, text):
        text = text.strip()
        parsed = self._parse_coord(text)
        if parsed and self._corner1 is None:
            self._corner1 = parsed
            self.board.status_bar.showMessage("矩形: 指定对角点或输入 长,宽")
            self.board.viewport.update()
            return True
        # 尝试解析 长,宽
        parts = text.replace('，', ',').split(',')
        if len(parts) == 2 and self._corner1:
            try:
                w = float(parts[0].strip())
                h = float(parts[1].strip())
                x = self._corner1[0]
                y = self._corner1[1]
                rect = RectangleElement(x, y, w, h)
                self.board.apply_current_layer_style(rect)
                self.board.add_element(rect)
                self._corner1 = None
                self._preview_corner = None
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
        if self._corner1 is None:
            return "矩形: 指定第一个角点"
        return "矩形: 指定对角点 或 输入 长,宽"

    def draw_preview(self, painter, coord_system):
        if self._corner1 and self._preview_corner:
            x = min(self._corner1[0], self._preview_corner[0])
            y = min(self._corner1[1], self._preview_corner[1])
            w = abs(self._preview_corner[0] - self._corner1[0])
            h = abs(self._preview_corner[1] - self._corner1[1])
            sx, sy = coord_system.world_to_screen(x, y + h)
            sw = coord_system.world_dist_to_screen(w)
            sh = coord_system.world_dist_to_screen(h)
            pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(sx, sy, sw, sh)
            return True
        return False
