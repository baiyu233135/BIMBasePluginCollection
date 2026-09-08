# -*- coding: utf-8 -*-
"""直线命令 - L（支持命令行输入坐标和长度）"""
import math
from PyQt5.QtGui import QPainter, QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import LineElement


class LineCommand(BaseCommand):
    name = "直线"
    shortcut = "L"
    description = "绘制直线段"

    def __init__(self, board):
        super().__init__(board)
        self._preview_end = None
        self._angle_mode = False  # 是否正在输入角度
        self._length_mode = False  # 是否正在输入长度

    def on_activate(self):
        self.clear_points()
        self._preview_end = None
        self._angle_mode = False
        self._length_mode = False
        self.state = CommandState.ACTIVE
        self.board.status_bar.showMessage(self.get_prompt())
        self.board.cmd_input.setFocus()

    def on_cancel(self):
        self._preview_end = None
        self.board.viewport.update()

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self.point_count() == 0:
                self.add_point(world_x, world_y)
                self.board.status_bar.showMessage(self.get_prompt())
                self.board.viewport.update()
                return True
            elif self.point_count() >= 1:
                start = self.get_last_point()
                if start:
                    line = LineElement(start[0], start[1], world_x, world_y)
                    self.board.apply_current_layer_style(line)
                    self.board.add_element(line)
                    self.clear_points()
                    self.add_point(world_x, world_y)
                    self._preview_end = None
                    self.board.status_bar.showMessage(self.get_prompt())
                    self.board.viewport.update()
                    return True
        elif button == 2:
            if self.point_count() > 0:
                self.clear_points()
                self._preview_end = None
                self.board.viewport.update()
                self.board.status_bar.showMessage("右键点击结束直线绘制")
            else:
                self.cancel()
                self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self.point_count() >= 1:
            self._preview_end = (world_x, world_y)
            start = self.get_last_point()
            if start:
                dx = world_x - start[0]
                dy = world_y - start[1]
                length = math.hypot(dx, dy)
                angle = math.degrees(math.atan2(dy, dx))
                if angle < 0:
                    angle += 360
                self.board.status_bar.showMessage(
                    f"终点: ({world_x:.2f}, {world_y:.2f}) | 长度: {length:.2f}mm | 角度: {angle:.1f}°"
                )
            self.board.viewport.update()
            return True
        else:
            self.board.status_bar.showMessage(f"光标: ({world_x:.2f}, {world_y:.2f}) - 点击指定第一点")
        return False

    def on_cmd_confirm(self, text):
        """命令行输入确认"""
        text = text.strip()
        # 1. 尝试解析为坐标 (x,y)
        parsed = self._parse_coord(text)
        if parsed:
            wx, wy = parsed
            if self.point_count() == 0:
                self.add_point(wx, wy)
                self.board.status_bar.showMessage(self.get_prompt())
                self.board.viewport.update()
                return True
            else:
                start = self.get_last_point()
                line = LineElement(start[0], start[1], wx, wy)
                self.board.apply_current_layer_style(line)
                self.board.add_element(line)
                self.clear_points()
                self.add_point(wx, wy)
                self.board.viewport.update()
                return True
        # 2. 尝试解析为长度（数字）
        try:
            length = float(text)
            if self.point_count() >= 1:
                start = self.get_last_point()
                # 如果已有预览角度，使用预览角度；否则使用默认0度
                if hasattr(self, '_last_preview_angle'):
                    angle = math.radians(self._last_preview_angle)
                else:
                    angle = 0
                wx = start[0] + length * math.cos(angle)
                wy = start[1] + length * math.sin(angle)
                line = LineElement(start[0], start[1], wx, wy)
                self.board.apply_current_layer_style(line)
                self.board.add_element(line)
                self.clear_points()
                self.add_point(wx, wy)
                self.board.viewport.update()
                return True
        except ValueError:
            pass
        # 3. 尝试解析为 @长度<角度
        import re
        m = re.match(r'@?([\d.]+)<([\d.]+)', text)
        if m and self.point_count() >= 1:
            length = float(m.group(1))
            angle = math.radians(float(m.group(2)))
            start = self.get_last_point()
            wx = start[0] + length * math.cos(angle)
            wy = start[1] + length * math.sin(angle)
            line = LineElement(start[0], start[1], wx, wy)
            self.board.apply_current_layer_style(line)
            self.board.add_element(line)
            self.clear_points()
            self.add_point(wx, wy)
            self.board.viewport.update()
            return True
        return False

    def _parse_coord(self, text):
        """解析坐标字符串"""
        import re
        text = text.strip().replace('(', '').replace(')', '').replace('，', ',')
        if text.startswith('@'):
            text = text[1:]
            relative = True
        else:
            relative = False
        parts = text.split(',')
        if len(parts) == 2:
            try:
                x = float(parts[0].strip())
                y = float(parts[1].strip())
                if relative and self.point_count() >= 1:
                    last = self.get_last_point()
                    x += last[0]
                    y += last[1]
                return (x, y)
            except ValueError:
                pass
        return None

    def get_prompt(self):
        if self.point_count() == 0:
            return "直线: 指定第一点 (左键/坐标，右键取消)"
        return "直线: 指定下一点 或 输入长度 或 @长度<角度 (左键绘制，右键结束)"

    def draw_preview(self, painter, coord_system):
        if self.point_count() >= 1 and self._preview_end:
            start = self.get_last_point()
            if start:
                sx, sy = coord_system.world_to_screen(start[0], start[1])
                ex, ey = coord_system.world_to_screen(self._preview_end[0], self._preview_end[1])
                pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(sx, sy, ex, ey)
                # 计算并显示角度
                dx = self._preview_end[0] - start[0]
                dy = self._preview_end[1] - start[1]
                angle = math.degrees(math.atan2(dy, dx))
                if angle < 0:
                    angle += 360
                length = math.hypot(dx, dy)
                self._last_preview_angle = angle
                # 绘制角度标记
                mid_x = (sx + ex) // 2
                mid_y = (sy + ey) // 2
                painter.setPen(QPen(QColor(255, 200, 0), 1))
                painter.drawText(mid_x + 5, mid_y - 5, f"{length:.1f}mm @{angle:.1f}°")
                painter.setBrush(QColor(128, 128, 128))
                painter.drawEllipse(sx - 3, sy - 3, 6, 6)
                painter.drawEllipse(ex - 3, ey - 3, 6, 6)
                return True
        return False
