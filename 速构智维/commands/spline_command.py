# -*- coding: utf-8 -*-
"""样条曲线命令 - SPL"""
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import PolylineElement
class SplineCommand(BaseCommand):
    name = "样条曲线"
    shortcut = "SPL"
    description = "绘制样条曲线（用控制点近似）"

    def __init__(self, board):
        super().__init__(board)
        self._preview_end = None

    def on_activate(self):
        self.clear_points()
        self._preview_end = None
        self.board.status_bar.showMessage(self.get_prompt())

    def on_cancel(self):
        self._finish_spline()
        self._preview_end = None
        self.board.viewport.update()

    def _finish_spline(self):
        if len(self._points) >= 2:
            # 用控制点生成平滑曲线（简化：用多段线密集采样近似）
            smooth_pts = self._generate_spline_points(self._points)
            poly = PolylineElement(smooth_pts, closed=False)
            poly.element_type = poly.element_type.__class__("样条曲线")  # 标记为样条
            self.board.apply_current_layer_style(poly)
            self.board.add_element(poly)
        self.clear_points()

    def _generate_spline_points(self, control_points, segments_per_span=20):
        """用三次贝塞尔样条生成平滑点"""
        if len(control_points) < 2:
            return control_points
        # 简化实现：用Catmull-Rom样条
        pts = []
        # 复制首尾点做边界
        cps = [control_points[0]] + list(control_points) + [control_points[-1]]
        for i in range(1, len(cps) - 2):
            p0, p1, p2, p3 = cps[i-1], cps[i], cps[i+1], cps[i+2]
            for t in range(segments_per_span):
                s = t / segments_per_span
                # Catmull-Rom
                x = 0.5 * ((2 * p1[0]) +
                          (-p0[0] + p2[0]) * s +
                          (2*p0[0] - 5*p1[0] + 4*p2[0] - p3[0]) * s*s +
                          (-p0[0] + 3*p1[0] - 3*p2[0] + p3[0]) * s*s*s)
                y = 0.5 * ((2 * p1[1]) +
                          (-p0[1] + p2[1]) * s +
                          (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1]) * s*s +
                          (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1]) * s*s*s)
                pts.append((x, y))
        pts.append(control_points[-1])
        return pts

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            self.add_point(world_x, world_y)
            self._preview_end = None
            self.board.viewport.update()
            return True
        elif button == 2:
            self._finish_spline()
            self._preview_end = None
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self.point_count() >= 1:
            self._preview_end = (world_x, world_y)
            temp_pts = list(self._points) + [self._preview_end]
            smooth = self._generate_spline_points(temp_pts, 10)
            self._preview_points = smooth
            self.board.status_bar.showMessage(
                f"样条曲线: {self.point_count()} 控制点"
            )
            self.board.viewport.update()
            return True
        else:
            self.board.status_bar.showMessage(f"光标: ({world_x:.2f}, {world_y:.2f}) - 点击指定第一点")
        return False

    def get_prompt(self):
        if self.point_count() == 0:
            return "样条曲线: 指定第一点 (左键添加控制点，右键结束)"
        return "样条曲线: 指定下一点 (左键添加，右键结束)"

    def draw_preview(self, painter, coord_system):
        if self.point_count() >= 1 and hasattr(self, '_preview_points'):
            pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
            painter.setPen(pen)
            pts = [coord_system.world_to_screen(p[0], p[1]) for p in self._preview_points]
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
            # 绘制控制点
            painter.setBrush(QColor(128, 128, 128))
            for p in self._points:
                sx, sy = coord_system.world_to_screen(p[0], p[1])
                painter.drawEllipse(sx - 3, sy - 3, 6, 6)
            return True
        return False
