# -*- coding: utf-8 -*-
"""
3D实体命令 - v1.5 P1 修复版

修复: 移除QInputDialog和QTimer，改用命令行输入获取高度，避免BIMBase内嵌环境闪退

8种3D实体: 拉伸体/立方体/球体/圆锥/圆环/棱锥/直角三棱柱
高度来源(优先级): 1.命令行输入 2.底部height_input输入框 3.默认值100mm

BIMBase同步时根据entity_3d_type生成对应3D参数化组件
"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand
from geometry.elements import (RectangleElement, CircleElement, PolylineElement,
                               ArcElement, PointElement)


class _SolidBaseCommand(BaseCommand):
    """3D实体命令基类 - 统一高度处理(从命令行或底部输入框获取)"""
    is_solid_command = True

    def _get_height(self, text_input: str = "") -> float:
        """获取3D高度 - 优先级: 命令行输入 > 底部height_input > 默认值100"""
        if text_input:
            text = text_input.strip()
            try:
                return float(text)
            except ValueError:
                pass
        try:
            if hasattr(self.board, 'height_input'):
                val = self.board.height_input.text().strip()
                if val:
                    return float(val)
        except (ValueError, AttributeError):
            pass
        return 100.0

    def _mark_3d(self, elem, entity_type: str, height: float):
        """标记元素为3D实体"""
        elem.is_3d = True
        elem.entity_3d_type = entity_type
        elem.height = height
        elem.thickness = height
        elem.style.color = (46, 125, 50)

    def _finish_solid(self, msg: str):
        """完成3D实体创建，返回选择模式"""
        self.board.status_bar.showMessage(msg)
        self._clear_selection()
        self.board.set_default_command()


# ============================================================
# 拉伸体 - 选中闭合截面 + 指定高度
# ============================================================
class ExtrudeCommand(_SolidBaseCommand):
    name = "拉伸体"
    shortcut = "EXT"
    description = "将选中的闭合2D图形拉伸为3D实体: 先选中闭合图形, 再输入高度(或直接执行使用默认高度)"

    def __init__(self, board):
        super().__init__(board)
        self._step = 0
        self._closed_elems = []

    def on_activate(self):
        self._step = 0
        self._closed_elems = []
        selected = self._get_selected_elements()
        closed = [e for e in selected if getattr(e, 'is_closed', False)]
        if not closed:
            self.board.status_bar.showMessage(
                "拉伸体: 请先选中闭合图形(矩形/圆/多边形), 然后重新执行此命令"
            )
            return
        self._closed_elems = closed
        h = self._get_height()
        self.board.status_bar.showMessage(
            f"拉伸体: 已选中{len(closed)}个闭合图形, 当前高度={h}mm "
            "(回车确认/输入新高度覆盖/右键取消)"
        )
        if hasattr(self.board, 'cmd_input'):
            self.board.cmd_input.setFocus()
        self._step = 1

    def on_cmd_confirm(self, text):
        if self._step == 1:
            height = self._get_height(text)
            for elem in self._closed_elems:
                self._mark_3d(elem, "extrude", height)
                self.board.apply_current_layer_style(elem)
            self._finish_solid(f"拉伸体完成: 高度{height}mm, {len(self._closed_elems)}个实体")
            return True
        return False

    def get_prompt(self):
        return "拉伸体: 输入高度(mm)后回车, 或直接用默认高度回车确认"

    def draw_preview(self, painter, coord_system):
        return False


# ============================================================
# 立方体 - 两点对角 + 指定高度
# ============================================================
class BoxCommand(_SolidBaseCommand):
    name = "立方体"
    shortcut = "BOX"
    description = "画立方体底面(矩形) + 输入高度"

    def __init__(self, board):
        super().__init__(board)
        self._p1 = None

    def on_activate(self):
        self._p1 = None
        self.board.status_bar.showMessage("立方体: 指定底面第一个角点")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._p1 is None:
                self._p1 = (world_x, world_y)
                self.board.status_bar.showMessage("立方体: 指定底面第二个角点")
                return True
            else:
                x = min(self._p1[0], world_x)
                y = min(self._p1[1], world_y)
                w = abs(world_x - self._p1[0])
                h = abs(world_y - self._p1[1])
                if w < 1 or h < 1:
                    self.board.status_bar.showMessage("立方体: 底面太小")
                    self.board.set_default_command()
                    return True
                self._rect_data = (x, y, w, h)
                default_h = self._get_height()
                self.board.status_bar.showMessage(
                    f"立方体: 底面{x:.1f},{y:.1f} {w:.1f}x{h:.1f}, "
                    f"高度={default_h}mm (回车确认/输入新高度/右键取消)"
                )
                # 焦点设置到命令行，确保回车触发_on_cmd_return
                if hasattr(self.board, 'cmd_input'):
                    self.board.cmd_input.setFocus()
                return True
        elif button == 2:
            self.board.set_default_command()
            return True
        return False

    def on_cmd_confirm(self, text):
        if hasattr(self, '_rect_data'):
            height = self._get_height(text)
            x, y, w, h = self._rect_data
            rect = RectangleElement(x, y, w, h)
            self._mark_3d(rect, "box", height)
            self.board.apply_current_layer_style(rect)
            self.board.add_element(rect)
            self._finish_solid(f"立方体: {w:.1f}x{h:.1f}x{height:.1f}mm")
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._p1:
            self._preview_p2 = (world_x, world_y)
            self.board.viewport.update()
            return True
        return False

    def get_prompt(self):
        if not self._p1:
            return "立方体: 指定底面第一个角点"
        if not hasattr(self, '_rect_data'):
            return "立方体: 指定底面第二个角点"
        return f"立方体: 输入高度(mm), 默认={self._get_height()}"

    def draw_preview(self, painter, coord_system):
        if self._p1 and hasattr(self, '_preview_p2'):
            p2 = self._preview_p2
            x = min(self._p1[0], p2[0])
            y = min(self._p1[1], p2[1])
            sx, sy = coord_system.world_to_screen(x, y + abs(p2[1] - self._p1[1]))
            sw = coord_system.world_dist_to_screen(abs(p2[0] - self._p1[0]))
            sh = coord_system.world_dist_to_screen(abs(p2[1] - self._p1[1]))
            pen = QPen(QColor(46, 125, 50), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(sx, sy, sw, sh)
            return True
        return False


# ============================================================
# 球体 - 圆心 + 半径 + 高度=直径
# ============================================================
class SphereCommand(_SolidBaseCommand):
    name = "球体"
    shortcut = "SPH"
    description = "画球体底面(圆) + 高度=直径"

    def __init__(self, board):
        super().__init__(board)
        self._center = None

    def on_activate(self):
        self._center = None
        self.board.status_bar.showMessage("球体: 指定球心投影点(底面圆心)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._center is None:
                self._center = (world_x, world_y)
                self.board.status_bar.showMessage("球体: 指定半径")
                return True
            else:
                r = math.hypot(world_x - self._center[0], world_y - self._center[1])
                if r < 1:
                    self.board.status_bar.showMessage("球体: 半径太小")
                    self.board.set_default_command()
                    return True
                self._sphere_data = (self._center[0], self._center[1], r)
                default_h = r * 2
                self.board.status_bar.showMessage(
                    f"球体: 半径{r:.1f}mm, 默认直径高度={default_h:.1f}mm "
                    f"(回车确认/输入新高度/右键取消)"
                )
                if hasattr(self.board, 'cmd_input'):
                    self.board.cmd_input.setFocus()
                return True
        elif button == 2:
            self.board.set_default_command()
            return True
        return False

    def on_cmd_confirm(self, text):
        if hasattr(self, '_sphere_data'):
            cx, cy, r = self._sphere_data
            default_h = r * 2
            height = self._get_height(text)
            if not text.strip():
                height = default_h
            circle = CircleElement(cx, cy, r)
            self._mark_3d(circle, "sphere", height)
            self.board.apply_current_layer_style(circle)
            self.board.add_element(circle)
            self._finish_solid(f"球体: 半径{r:.1f}mm 直径{height:.1f}mm")
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center:
            self._preview_r = math.hypot(world_x - self._center[0], world_y - self._center[1])
            self.board.viewport.update()
            return True
        return False

    def get_prompt(self):
        if not self._center:
            return "球体: 指定球心投影点"
        if not hasattr(self, '_sphere_data'):
            return "球体: 指定半径"
        return f"球体: 输入高度(mm), 默认直径={self._get_height()}"

    def draw_preview(self, painter, coord_system):
        if self._center and hasattr(self, '_preview_r'):
            cx, cy = coord_system.world_to_screen(self._center[0], self._center[1])
            r = coord_system.world_dist_to_screen(self._preview_r)
            pen = QPen(QColor(46, 125, 50), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            return True
        return False


# ============================================================
# 圆锥 - 底面圆心 + 半径 + 输入高度
# ============================================================
class ConeCommand(_SolidBaseCommand):
    name = "圆锥"
    shortcut = "CONE"
    description = "画圆锥底面(圆) + 输入高度"

    def __init__(self, board):
        super().__init__(board)
        self._center = None

    def on_activate(self):
        self._center = None
        self.board.status_bar.showMessage("圆锥: 指定底面圆心")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._center is None:
                self._center = (world_x, world_y)
                self.board.status_bar.showMessage("圆锥: 指定底面半径")
                return True
            else:
                r = math.hypot(world_x - self._center[0], world_y - self._center[1])
                if r < 1:
                    self.board.status_bar.showMessage("圆锥: 半径太小")
                    self.board.set_default_command()
                    return True
                self._cone_data = (self._center[0], self._center[1], r)
                default_h = self._get_height()
                self.board.status_bar.showMessage(
                    f"圆锥: 底面半径{r:.1f}mm, 高度={default_h}mm "
                    f"(回车确认/输入新高度/右键取消)"
                )
                if hasattr(self.board, 'cmd_input'):
                    self.board.cmd_input.setFocus()
                return True
        elif button == 2:
            self.board.set_default_command()
            return True
        return False

    def on_cmd_confirm(self, text):
        if hasattr(self, '_cone_data'):
            cx, cy, r = self._cone_data
            height = self._get_height(text)
            circle = CircleElement(cx, cy, r)
            self._mark_3d(circle, "cone", height)
            self.board.apply_current_layer_style(circle)
            self.board.add_element(circle)
            self._finish_solid(f"圆锥: 底面半径{r:.1f}mm 高{height:.1f}mm")
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center:
            self._preview_r = math.hypot(world_x - self._center[0], world_y - self._center[1])
            self.board.viewport.update()
            return True
        return False

    def get_prompt(self):
        if not self._center:
            return "圆锥: 指定底面圆心"
        if not hasattr(self, '_cone_data'):
            return "圆锥: 指定底面半径"
        return f"圆锥: 输入高度(mm), 默认={self._get_height()}"

    def draw_preview(self, painter, coord_system):
        if self._center and hasattr(self, '_preview_r'):
            cx, cy = coord_system.world_to_screen(self._center[0], self._center[1])
            r = coord_system.world_dist_to_screen(self._preview_r)
            pen = QPen(QColor(46, 125, 50), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            return True
        return False


# ============================================================
# 圆环 - 中心 + 外半径 + 内半径 + 管径高度
# ============================================================
class TorusCommand(_SolidBaseCommand):
    name = "圆环"
    shortcut = "TOR"
    description = "画圆环俯视图(两个同心圆) + 输入管径高度"

    def __init__(self, board):
        super().__init__(board)
        self._center = None
        self._outer_r = None

    def on_activate(self):
        self._center = None
        self._outer_r = None
        self.board.status_bar.showMessage("圆环: 指定中心点")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._center is None:
                self._center = (world_x, world_y)
                self.board.status_bar.showMessage("圆环: 指定外半径")
                return True
            elif self._outer_r is None:
                self._outer_r = math.hypot(world_x - self._center[0], world_y - self._center[1])
                if self._outer_r < 2:
                    self.board.status_bar.showMessage("圆环: 半径太小")
                    self.board.set_default_command()
                    return True
                self.board.status_bar.showMessage("圆环: 指定内半径(管径的一半)")
                return True
            else:
                inner_r = math.hypot(world_x - self._center[0], world_y - self._center[1])
                inner_r = min(inner_r, self._outer_r - 1)
                if inner_r < 1:
                    inner_r = self._outer_r * 0.3
                tube_r = self._outer_r - inner_r
                self._torus_data = (self._center[0], self._center[1], self._outer_r, inner_r)
                default_h = tube_r
                self.board.status_bar.showMessage(
                    f"圆环: 外径{self._outer_r:.1f} 内径{inner_r:.1f} "
                    f"默认管径高度={default_h:.1f}mm (回车确认/输入新高度/右键取消)"
                )
                if hasattr(self.board, 'cmd_input'):
                    self.board.cmd_input.setFocus()
                return True
        elif button == 2:
            self.board.set_default_command()
            return True
        return False

    def on_cmd_confirm(self, text):
        if hasattr(self, '_torus_data'):
            cx, cy, outer_r, inner_r = self._torus_data
            tube_r = outer_r - inner_r
            height = self._get_height(text)
            if not text.strip():
                height = tube_r
            outer = CircleElement(cx, cy, outer_r)
            self._mark_3d(outer, "torus", height)
            outer.style.line_type = "solid"
            self.board.apply_current_layer_style(outer)
            self.board.add_element(outer)
            inner = CircleElement(cx, cy, inner_r)
            inner.style.color = (46, 125, 50)
            inner.style.line_type = "dashed"
            self.board.apply_current_layer_style(inner)
            self.board.add_element(inner)
            self._finish_solid(
                f"圆环: 外径{outer_r:.1f} 内径{inner_r:.1f} 管径{height:.1f}mm")
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center:
            if self._outer_r is None:
                self._preview_r = math.hypot(world_x - self._center[0], world_y - self._center[1])
            else:
                self._preview_inner = math.hypot(world_x - self._center[0], world_y - self._center[1])
            self.board.viewport.update()
            return True
        return False

    def draw_preview(self, painter, coord_system):
        if self._center:
            cx, cy = coord_system.world_to_screen(self._center[0], self._center[1])
            pen = QPen(QColor(46, 125, 50), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            if self._outer_r is None and hasattr(self, '_preview_r'):
                r = coord_system.world_dist_to_screen(self._preview_r)
                painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
                return True
            elif hasattr(self, '_preview_inner'):
                r1 = coord_system.world_dist_to_screen(self._outer_r)
                r2 = coord_system.world_dist_to_screen(self._preview_inner)
                painter.drawEllipse(cx - r1, cy - r1, r1 * 2, r1 * 2)
                painter.drawEllipse(cx - r2, cy - r2, r2 * 2, r2 * 2)
                return True
        return False

    def get_prompt(self):
        if not self._center:
            return "圆环: 指定中心点"
        if self._outer_r is None:
            return "圆环: 指定外半径"
        if not hasattr(self, '_torus_data'):
            return "圆环: 指定内半径"
        return f"圆环: 输入管径高度(mm), 默认={self._get_height()}"


# ============================================================
# 棱锥 - 底面多边形 + 输入高度
# ============================================================
class PyramidCommand(_SolidBaseCommand):
    name = "棱锥"
    shortcut = "PYR"
    description = "画棱锥底面(多边形) + 输入高度"

    def __init__(self, board):
        super().__init__(board)
        self._center = None
        self._sides = 4

    def on_activate(self):
        self._center = None
        self._sides = 4
        self.board.status_bar.showMessage(
            "棱锥: 指定底面中心点 (命令行输入边数如'6'可修改, 默认4边形)"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._center is None:
                self._center = (world_x, world_y)
                self.board.status_bar.showMessage("棱锥: 指定底面半径(中心到顶点距离)")
                return True
            else:
                r = math.hypot(world_x - self._center[0], world_y - self._center[1])
                if r < 1:
                    self.board.status_bar.showMessage("棱锥: 半径太小")
                    self.board.set_default_command()
                    return True
                self._pyramid_data = (self._center[0], self._center[1], r)
                default_h = self._get_height()
                self.board.status_bar.showMessage(
                    f"棱锥: {self._sides}边形 半径{r:.1f}mm, "
                    f"高度={default_h}mm (回车确认/输入新高度/右键取消)"
                )
                if hasattr(self.board, 'cmd_input'):
                    self.board.cmd_input.setFocus()
                return True
        elif button == 2:
            self.board.set_default_command()
            return True
        return False

    def on_cmd_confirm(self, text):
        if self._center and not hasattr(self, '_pyramid_data'):
            try:
                n = int(text.strip())
                if n >= 3:
                    self._sides = n
                    self.board.status_bar.showMessage(f"棱锥: 边数设为{n}, 请指定半径")
                    return True
            except ValueError:
                pass
        if hasattr(self, '_pyramid_data'):
            cx, cy, r = self._pyramid_data
            height = self._get_height(text)
            points = []
            for i in range(self._sides):
                a = 2 * math.pi * i / self._sides - math.pi / 2
                px = cx + r * math.cos(a)
                py = cy + r * math.sin(a)
                points.append((px, py))
            poly = PolylineElement(points, closed=True)
            self._mark_3d(poly, "pyramid", height)
            self.board.apply_current_layer_style(poly)
            self.board.add_element(poly)
            self._finish_solid(
                f"棱锥: {self._sides}边形 半径{r:.1f}mm 高{height:.1f}mm")
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center:
            self._preview_r = math.hypot(world_x - self._center[0], world_y - self._center[1])
            self.board.viewport.update()
            return True
        return False

    def draw_preview(self, painter, coord_system):
        if self._center and hasattr(self, '_preview_r'):
            r = self._preview_r
            points = []
            for i in range(self._sides):
                a = 2 * math.pi * i / self._sides - math.pi / 2
                px = self._center[0] + r * math.cos(a)
                py = self._center[1] + r * math.sin(a)
                points.append(coord_system.world_to_screen(px, py))
            pen = QPen(QColor(46, 125, 50), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for i in range(len(points)):
                p1 = points[i]
                p2 = points[(i + 1) % len(points)]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])
            return True
        return False

    def get_prompt(self):
        if not self._center:
            return f"棱锥: 指定中心点 (当前{self._sides}边形, 输入数字改边数)"
        if not hasattr(self, '_pyramid_data'):
            return f"棱锥: 指定底面半径 (当前{self._sides}边形)"
        return f"棱锥: 输入高度(mm), 默认={self._get_height()}"


# ============================================================
# 直角三棱柱 - 直角三角形底面 + 输入高度
# ============================================================
class TriangularPrismCommand(_SolidBaseCommand):
    name = "直角三棱柱"
    shortcut = "TPRISM"
    description = "画直角三角形底面 + 输入高度"

    def __init__(self, board):
        super().__init__(board)
        self._p1 = None
        self._p2 = None

    def on_activate(self):
        self._p1 = None
        self._p2 = None
        self.board.status_bar.showMessage("直角三棱柱: 指定直角顶点")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._p1 is None:
                self._p1 = (world_x, world_y)
                self.board.status_bar.showMessage("直角三棱柱: 指定水平边终点")
                return True
            elif self._p2 is None:
                self._p2 = (world_x, world_y)
                self.board.status_bar.showMessage("直角三棱柱: 指定垂直方向终点")
                return True
            else:
                p3 = (self._p2[0], world_y)
                points = [self._p1, self._p2, p3]
                self._prism_data = points
                default_h = self._get_height()
                self.board.status_bar.showMessage(
                    f"直角三棱柱: 高度={default_h}mm (回车确认/输入新高度/右键取消)"
                )
                if hasattr(self.board, 'cmd_input'):
                    self.board.cmd_input.setFocus()
                return True
        elif button == 2:
            self.board.set_default_command()
            return True
        return False

    def on_cmd_confirm(self, text):
        if hasattr(self, '_prism_data'):
            height = self._get_height(text)
            points = self._prism_data
            poly = PolylineElement(points, closed=True)
            self._mark_3d(poly, "triangular_prism", height)
            self.board.apply_current_layer_style(poly)
            self.board.add_element(poly)
            self._finish_solid(f"直角三棱柱: 高{height:.1f}mm")
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._p1:
            if self._p2 is None:
                self._preview_h = (world_x, world_y)
            else:
                self._preview_v = (world_x, world_y)
            self.board.viewport.update()
            return True
        return False

    def draw_preview(self, painter, coord_system):
        if self._p1 and self._p2 is None and hasattr(self, '_preview_h'):
            s1 = coord_system.world_to_screen(self._p1[0], self._p1[1])
            s2 = coord_system.world_to_screen(self._preview_h[0], self._preview_h[1])
            pen = QPen(QColor(46, 125, 50), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(s1[0], s1[1], s2[0], s2[1])
            return True
        elif self._p1 and self._p2 and hasattr(self, '_preview_v'):
            s1 = coord_system.world_to_screen(self._p1[0], self._p1[1])
            s2 = coord_system.world_to_screen(self._p2[0], self._p2[1])
            p3 = (self._p2[0], self._preview_v[1])
            s3 = coord_system.world_to_screen(p3[0], p3[1])
            pen = QPen(QColor(46, 125, 50), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(s1[0], s1[1], s2[0], s2[1])
            painter.drawLine(s1[0], s1[1], s3[0], s3[1])
            painter.drawLine(s2[0], s2[1], s3[0], s3[1])
            return True
        return False

    def get_prompt(self):
        if not self._p1:
            return "直角三棱柱: 指定直角顶点"
        if self._p2 is None:
            return "直角三棱柱: 指定水平边终点"
        if not hasattr(self, '_prism_data'):
            return "直角三棱柱: 指定垂直方向终点"
        return f"直角三棱柱: 输入高度(mm), 默认={self._get_height()}"
