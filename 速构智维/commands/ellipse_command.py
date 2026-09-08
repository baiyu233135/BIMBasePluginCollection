# -*- coding: utf-8 -*-
"""椭圆命令 - EL（支持命令行输入参数）"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import EllipseElement


class EllipseCommand(BaseCommand):
    name = "椭圆"
    shortcut = "EL"
    description = "绘制椭圆（中心+长轴+短轴）"

    def __init__(self, board):
        super().__init__(board)
        self._center = None
        self._axis1 = None
        self._preview_axis2 = None

    def on_activate(self):
        self._center = None
        self._axis1 = None
        self._preview_axis2 = None
        self.board.status_bar.showMessage(self.get_prompt())

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._center is None:
                self._center = (world_x, world_y)
                self.board.viewport.update()
                return True
            elif self._axis1 is None:
                self._axis1 = (world_x, world_y)
                self.board.viewport.update()
                return True
            else:
                rx = math.hypot(self._axis1[0] - self._center[0],
                               self._axis1[1] - self._center[1])
                ry = math.hypot(world_x - self._center[0],
                               world_y - self._center[1])
                rot = math.degrees(math.atan2(self._axis1[1] - self._center[1],
                                              self._axis1[0] - self._center[0]))
                ellipse = EllipseElement(self._center[0], self._center[1], rx, ry, rot)
                self.board.apply_current_layer_style(ellipse)
                self.board.add_element(ellipse)
                self._center = None
                self._axis1 = None
                self._preview_axis2 = None
                self.board.viewport.update()
                return True
        elif button == 2:
            self._center = None
            self._axis1 = None
            self._preview_axis2 = None
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center and self._axis1:
            self._preview_axis2 = (world_x, world_y)
            rx = math.hypot(self._axis1[0] - self._center[0],
                           self._axis1[1] - self._center[1])
            ry = math.hypot(world_x - self._center[0], world_y - self._center[1])
            self.board.status_bar.showMessage(f"椭圆: rx={rx:.2f} ry={ry:.2f}")
            self.board.viewport.update()
            return True
        elif self._center:
            self.board.status_bar.showMessage("椭圆: 指定长轴端点")
            self.board.viewport.update()
            return True
        return False

    def on_cmd_confirm(self, text):
        text = text.strip()
        parsed = self._parse_coord(text)
        if parsed:
            if self._center is None:
                self._center = parsed
                self.board.status_bar.showMessage("椭圆: 指定长轴端点或输入 rx,ry[,rotation]")
                self.board.viewport.update()
                return True
        # 解析 rx,ry[,rotation]
        parts = text.replace('，', ',').split(',')
        if len(parts) >= 2:
            try:
                rx = float(parts[0].strip())
                ry = float(parts[1].strip())
                rot = 0
                if len(parts) >= 3:
                    rot = float(parts[2].strip())
                if self._center:
                    ellipse = EllipseElement(self._center[0], self._center[1], rx, ry, rot)
                    self.board.apply_current_layer_style(ellipse)
                    self.board.add_element(ellipse)
                    self._center = None
                    self._axis1 = None
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
            return "椭圆: 指定中心点"
        elif self._axis1 is None:
            return "椭圆: 指定长轴端点 或 输入 rx,ry[,rotation]"
        return "椭圆: 指定短轴端点"

    def draw_preview(self, painter, coord_system):
        if self._center and self._axis1:
            rx = math.hypot(self._axis1[0] - self._center[0],
                           self._axis1[1] - self._center[1])
            rot = math.atan2(self._axis1[1] - self._center[1],
                            self._axis1[0] - self._center[0])
            if self._preview_axis2:
                ry = math.hypot(self._preview_axis2[0] - self._center[0],
                               self._preview_axis2[1] - self._center[1])
            else:
                ry = rx * 0.6
            num = 72
            pts = []
            for i in range(num):
                t = 2 * math.pi * i / num
                lx = rx * math.cos(t)
                ly = ry * math.sin(t)
                px = self._center[0] + lx * math.cos(rot) - ly * math.sin(rot)
                py = self._center[1] + lx * math.sin(rot) + ly * math.cos(rot)
                pts.append(coord_system.world_to_screen(px, py))
            pts.append(pts[0])
            pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
            return True
        return False
