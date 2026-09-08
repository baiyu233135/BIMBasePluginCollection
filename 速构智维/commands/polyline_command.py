# -*- coding: utf-8 -*-
"""多段线命令 - PL"""
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import PolylineElement
class PolylineCommand(BaseCommand):
    name = "多段线"
    shortcut = "PL"
    description = "绘制多段线（连续线段，不闭合）"

    def __init__(self, board):
        super().__init__(board)
        self._preview_end = None

    def on_activate(self):
        self.clear_points()
        self._preview_end = None
        self.board.status_bar.showMessage(self.get_prompt())

    def on_cancel(self):
        self._finish_polyline()
        self._preview_end = None
        self.board.viewport.update()

    def _finish_polyline(self):
        if len(self._points) >= 2:
            poly = PolylineElement(list(self._points), closed=False)
            self.board.apply_current_layer_style(poly)
            self.board.add_element(poly)
        self.clear_points()

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            self.add_point(world_x, world_y)
            self._preview_end = None
            self.board.status_bar.showMessage(self.get_prompt())
            self.board.viewport.update()
            return True
        elif button == 2:
            self._finish_polyline()
            self._preview_end = None
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self.point_count() >= 1:
            self._preview_end = (world_x, world_y)
            self.board.status_bar.showMessage(
                f"多段线: {self.point_count()} 点 | 当前: ({world_x:.2f}, {world_y:.2f})"
            )
            self.board.viewport.update()
            return True
        else:
            self.board.status_bar.showMessage(f"光标: ({world_x:.2f}, {world_y:.2f}) - 点击指定第一点")
        return False

    def get_prompt(self):
        if self.point_count() == 0:
            return "多段线: 指定第一点 (左键添加点，右键结束)"
        return "多段线: 指定下一点 (左键添加，右键结束)"

    def draw_preview(self, painter, coord_system):
        if self.point_count() >= 1 and self._preview_end:
            pts_screen = []
            for p in self._points:
                pts_screen.append(coord_system.world_to_screen(p[0], p[1]))
            pts_screen.append(coord_system.world_to_screen(self._preview_end[0], self._preview_end[1]))
            pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
            painter.setPen(pen)
            for i in range(len(pts_screen) - 1):
                painter.drawLine(pts_screen[i][0], pts_screen[i][1],
                               pts_screen[i+1][0], pts_screen[i+1][1])
            return True
        return False
