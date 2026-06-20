# -*- coding: utf-8 -*-
"""圆弧命令 - A（支持命令行输入半径）"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import ArcElement


class ArcCommand(BaseCommand):
    name = "圆弧"
    shortcut = "A"
    description = "绘制圆弧（圆心+起点+终点）"

    def __init__(self, board):
        super().__init__(board)
        self._center = None
        self._start_pt = None
        self._end_pt = None
        self._radius = None

    def on_activate(self):
        self._center = None
        self._start_pt = None
        self._end_pt = None
        self._radius = None
        self.board.status_bar.showMessage(self.get_prompt())

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._center is None:
                self._center = (world_x, world_y)
                self.board.viewport.update()
                return True
            elif self._start_pt is None:
                self._start_pt = (world_x, world_y)
                self._radius = math.hypot(world_x - self._center[0], world_y - self._center[1])
                self.board.viewport.update()
                return True
            else:
                self._end_pt = (world_x, world_y)
                r = self._radius
                sa = math.degrees(math.atan2(self._start_pt[1] - self._center[1],
                                             self._start_pt[0] - self._center[0]))
                ea = math.degrees(math.atan2(self._end_pt[1] - self._center[1],
                                            self._end_pt[0] - self._center[0]))
                arc = ArcElement(self._center[0], self._center[1], r, sa, ea)
                self.board.apply_current_layer_style(arc)
                self.board.add_element(arc)
                self._center = None
                self._start_pt = None
                self._end_pt = None
                self._radius = None
                self.board.viewport.update()
                return True
        elif button == 2:
            self._center = None
            self._start_pt = None
            self._end_pt = None
            self._radius = None
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center and self._start_pt:
            self._end_pt = (world_x, world_y)
            sa = math.degrees(math.atan2(self._start_pt[1] - self._center[1],
                                         self._start_pt[0] - self._center[0]))
            ea = math.degrees(math.atan2(world_y - self._center[1],
                                         world_x - self._center[0]))
            if ea < sa:
                ea += 360
            self.board.status_bar.showMessage(f"圆弧: 起点角{sa:.1f}° → 终点角{ea:.1f}°")
            self.board.viewport.update()
            return True
        elif self._center:
            self._radius = math.hypot(world_x - self._center[0], world_y - self._center[1])
            self.board.status_bar.showMessage(f"圆弧: 半径 {self._radius:.2f}mm")
            self.board.viewport.update()
            return True
        return False

    def on_cmd_confirm(self, text):
        text = text.strip()
        try:
            r = float(text)
            if self._center and self._start_pt is None:
                # 固定半径，在鼠标方向生成起点
                # 需要鼠标位置来确定方向，这里简化为X轴正方向
                self._start_pt = (self._center[0] + r, self._center[1])
                self._radius = r
                self.board.status_bar.showMessage("圆弧: 指定终点角度")
                self.board.viewport.update()
                return True
        except ValueError:
            pass
        return False

    def get_prompt(self):
        if self._center is None:
            return "圆弧: 指定圆心"
        elif self._start_pt is None:
            return "圆弧: 指定起点（确定半径）或输入半径数值"
        return "圆弧: 指定终点"

    def draw_preview(self, painter, coord_system):
        if not self._center:
            return False
        cx, cy = self._center
        scx, scy = coord_system.world_to_screen(cx, cy)
        if self._start_pt and self._end_pt:
            r = self._radius
            sa = math.atan2(self._start_pt[1] - cy, self._start_pt[0] - cx)
            ea = math.atan2(self._end_pt[1] - cy, self._end_pt[0] - cx)
            if ea < sa:
                ea += 2 * math.pi
            sr = coord_system.world_dist_to_screen(r)
            pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            num = max(3, int((ea - sa) * sr / 5))
            num = min(num, 72)
            step = (ea - sa) / num
            pts = []
            for i in range(num + 1):
                a = sa + step * i
                px = scx + sr * math.cos(a)
                py = scy - sr * math.sin(a)
                pts.append((px, py))
            for i in range(len(pts) - 1):
                painter.drawLine(int(pts[i][0]), int(pts[i][1]),
                                int(pts[i+1][0]), int(pts[i+1][1]))
            return True
        elif self._start_pt:
            sr = coord_system.world_dist_to_screen(self._radius)
            pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(scx - sr, scy - sr, sr * 2, sr * 2)
            return True
        return False
