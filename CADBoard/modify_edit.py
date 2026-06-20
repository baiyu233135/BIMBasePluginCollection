# -*- coding: utf-8 -*-
"""
修改命令集3 - 修剪、延伸、打断、合并、倒角、圆角、分解（修复版，支持命令行参数）
"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import LineElement, ArcElement, PolylineElement


class TrimCommand(BaseCommand):
    name = "修剪"
    shortcut = "TR"
    description = "修剪对象到边界"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._boundary = None

    def on_activate(self):
        self._boundary = None
        self.board.status_bar.showMessage("修剪: 点击选择要修剪的对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            for elem in reversed(self.board.elements):
                if not getattr(elem, 'visible', True):
                    continue
                if self._hit_test(elem, world_x, world_y):
                    self._trim_element(elem, world_x, world_y)
                    self.board.viewport.update()
                    break
            return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _trim_element(self, elem, wx, wy):
        et = elem.element_type.value
        if et == '直线':
            t = self._project_on_line(wx, wy, elem.x1, elem.y1, elem.x2, elem.y2)
            if 0 <= t <= 1:
                px = elem.x1 + t * (elem.x2 - elem.x1)
                py = elem.y1 + t * (elem.y2 - elem.y1)
                d1 = math.hypot(wx - elem.x1, wy - elem.y1)
                d2 = math.hypot(wx - elem.x2, wy - elem.y2)
                if d1 < d2:
                    elem.x1 = px
                    elem.y1 = py
                else:
                    elem.x2 = px
                    elem.y2 = py
                self.board.status_bar.showMessage("修剪: 直线已修剪")
        elif et == '圆弧':
            a = math.degrees(math.atan2(wy - elem.cy, wx - elem.cx))
            sa, ea = elem.start_angle, elem.end_angle
            if ea < sa:
                ea += 360
            # 标准化
            while a < sa:
                a += 360
            if sa <= a <= ea:
                d_to_sa = abs(a - sa)
                d_to_ea = abs(a - ea)
                if d_to_sa < d_to_ea:
                    elem.start_angle = a
                else:
                    elem.end_angle = a

    def _project_on_line(self, px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        if l2 < 1e-12:
            return 0
        return ((px - x1) * dx + (py - y1) * dy) / l2

    def get_prompt(self):
        return "修剪: 点击要修剪的部分"

    def draw_preview(self, painter, coord_system):
        return False


class ExtendCommand(BaseCommand):
    name = "延伸"
    shortcut = "EX"
    description = "延伸对象 - 点击延伸20%，或输入延伸长度"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._target_elem = None
        self._extend_length = None

    def on_activate(self):
        self._target_elem = None
        self._extend_length = None
        self.board.status_bar.showMessage("延伸: 点击对象延伸20%，或先输入长度再点击 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            for elem in reversed(self.board.elements):
                if not getattr(elem, 'visible', True):
                    continue
                if self._hit_test(elem, world_x, world_y):
                    self._extend_element(elem)
                    self.board.viewport.update()
                    break
            return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _extend_element(self, elem):
        et = elem.element_type.value
        length = self._extend_length if self._extend_length else None
        if et == '直线':
            dx = elem.x2 - elem.x1
            dy = elem.y2 - elem.y1
            l = math.hypot(dx, dy)
            if l > 0:
                if length and length > 0:
                    ext = length
                else:
                    ext = l * 0.2
                elem.x1 -= (dx / l) * ext
                elem.y1 -= (dy / l) * ext
                elem.x2 += (dx / l) * ext
                elem.y2 += (dy / l) * ext
                self.board.status_bar.showMessage(f"延伸: 直线已延伸 {ext:.1f}mm")

    def on_cmd_confirm(self, text):
        try:
            val = float(text.strip())
            if val > 0:
                self._extend_length = val
                self.board.status_bar.showMessage(f"延伸: 长度设为 {val}mm，点击对象延伸")
                return True
        except ValueError:
            pass
        return False

    def get_prompt(self):
        ext = f"({self._extend_length}mm)" if self._extend_length else "(20%)"
        return f"延伸: 点击对象延伸 {ext}"

    def draw_preview(self, painter, coord_system):
        return False


class BreakCommand(BaseCommand):
    name = "打断"
    shortcut = "BR"
    description = "在两点之间打断对象"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._p1 = None
        self._p2 = None

    def on_activate(self):
        self._p1 = None
        self._p2 = None
        self.board.status_bar.showMessage("打断: 点击选择对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            selected = self._get_selected_elements()
            if not selected and not self._p1:
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    self._target = selected[0]
                    self._p1 = (world_x, world_y)
                    self.board.status_bar.showMessage("打断: 指定第二个打断点")
                    for e in self.board.elements:
                        e.selected = False
                    self.board.viewport.update()
                return True
            elif hasattr(self, '_target') and self._p1 and not self._p2:
                self._p2 = (world_x, world_y)
                self._execute_break()
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_break(self):
        elem = getattr(self, '_target', None)
        if not elem:
            self.cancel()
            self.board.set_default_command()
            return
        et = elem.element_type.value
        if et == '直线':
            t1 = self._project_on_line(self._p1[0], self._p1[1], elem.x1, elem.y1, elem.x2, elem.y2)
            t2 = self._project_on_line(self._p2[0], self._p2[1], elem.x1, elem.y1, elem.x2, elem.y2)
            t1 = max(0, min(1, t1))
            t2 = max(0, min(1, t2))
            if t1 > t2:
                t1, t2 = t2, t1
            px1 = elem.x1 + t1 * (elem.x2 - elem.x1)
            py1 = elem.y1 + t1 * (elem.y2 - elem.y1)
            px2 = elem.x1 + t2 * (elem.x2 - elem.x1)
            py2 = elem.y1 + t2 * (elem.y2 - elem.y1)
            l1 = LineElement(elem.x1, elem.y1, px1, py1)
            l2 = LineElement(px2, py2, elem.x2, elem.y2)
            self.board.apply_current_layer_style(l1)
            self.board.apply_current_layer_style(l2)
            added = 0
            if l1.length() > 1:
                self.board.add_element(l1)
                added += 1
            if l2.length() > 1:
                self.board.add_element(l2)
                added += 1
            if elem in self.board.elements:
                self.board.elements.remove(elem)
            self.board.status_bar.showMessage(f"打断: 已分成 {added} 段")
        self.cancel()
        self.board.set_default_command()

    def _project_on_line(self, px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        if l2 < 1e-12:
            return 0
        return ((px - x1) * dx + (py - y1) * dy) / l2

    def get_prompt(self):
        if not hasattr(self, '_target') or not self._p1:
            return "打断: 选择对象并指定第一点"
        return "打断: 指定第二点"

    def draw_preview(self, painter, coord_system):
        return False


class BreakAtPointCommand(BaseCommand):
    name = "打断于点"
    shortcut = ""
    description = "在指定点打断对象"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._target = None

    def on_activate(self):
        self._target = None
        self.board.status_bar.showMessage("打断于点: 点击选择对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._target is None:
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if self._hit_test(elem, world_x, world_y):
                        self._target = elem
                        self._execute_break_at(world_x, world_y)
                        break
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_break_at(self, wx, wy):
        elem = self._target
        if not elem:
            self.cancel()
            self.board.set_default_command()
            return
        et = elem.element_type.value
        if et == '直线':
            t = self._project_on_line(wx, wy, elem.x1, elem.y1, elem.x2, elem.y2)
            t = max(0, min(1, t))
            px = elem.x1 + t * (elem.x2 - elem.x1)
            py = elem.y1 + t * (elem.y2 - elem.y1)
            l1 = LineElement(elem.x1, elem.y1, px, py)
            l2 = LineElement(px, py, elem.x2, elem.y2)
            self.board.apply_current_layer_style(l1)
            self.board.apply_current_layer_style(l2)
            added = 0
            if l1.length() > 1:
                self.board.add_element(l1)
                added += 1
            if l2.length() > 1:
                self.board.add_element(l2)
                added += 1
            if elem in self.board.elements:
                self.board.elements.remove(elem)
            self.board.status_bar.showMessage(f"打断于点: 已分成 {added} 段")
        self.cancel()
        self.board.set_default_command()

    def _project_on_line(self, px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        if l2 < 1e-12:
            return 0
        return ((px - x1) * dx + (py - y1) * dy) / l2

    def get_prompt(self):
        return "打断于点: 点击对象上的打断位置"

    def draw_preview(self, painter, coord_system):
        return False


class JoinCommand(BaseCommand):
    name = "合并"
    shortcut = "J"
    description = "将多条线段合并为一条多段线整体"
    is_modify_command = True

    def on_activate(self):
        self.board.status_bar.showMessage("合并: 框选或点击选择多条线段，合并为一条多段线 (右键取消)")
        self._drag_start = None
        self._drag_end = None
        self._selecting = False

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            self._drag_start = (world_x, world_y)
            self._drag_end = (world_x, world_y)
            self._selecting = True
            self.board.viewport.update()
            return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._selecting:
            self._drag_end = (world_x, world_y)
            self.board.viewport.update()
            return True
        return False

    def on_mouse_release(self, world_x, world_y, button, modifiers):
        if button == 1 and self._selecting:
            self._drag_end = (world_x, world_y)
            self._selecting = False
            dx = abs(self._drag_end[0] - self._drag_start[0])
            dy = abs(self._drag_end[1] - self._drag_start[1])
            if dx > 5 or dy > 5:
                self._box_select(self._drag_start, self._drag_end)
            else:
                self._try_select_at(world_x, world_y)
            selected = self._get_selected_elements()
            self._execute_join(selected)
            return True
        return False

    def _box_select(self, p1, p2):
        x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1])
        x2, y2 = max(p1[0], p2[0]), max(p1[1], p2[1])
        for e in self.board.elements:
            if not getattr(e, 'visible', True):
                continue
            b = e.get_bounds()
            if b[0] <= x2 and b[2] >= x1 and b[1] <= y2 and b[3] >= y1:
                e.selected = True

    def _execute_join(self, elements):
        lines = [e for e in elements if e.element_type.value == '直线']
        if len(lines) < 2:
            self._clear_selection()
            self.board.status_bar.showMessage("合并: 请至少选择2条直线")
            self.cancel()
            self.board.set_default_command()
            return

        # 收集所有端点，按顺序连接
        all_pts = []
        for l in lines:
            all_pts.append((l.x1, l.y1))
            all_pts.append((l.x2, l.y2))

        # 简化：找到所有不同的端点，创建多段线
        unique_pts = []
        for p in all_pts:
            is_dup = False
            for up in unique_pts:
                if math.hypot(p[0]-up[0], p[1]-up[1]) < 1.0:
                    is_dup = True
                    break
            if not is_dup:
                unique_pts.append(p)

        if len(unique_pts) < 2:
            self._clear_selection()
            self.board.status_bar.showMessage("合并: 无法创建有效多段线")
            self.cancel()
            self.board.set_default_command()
            return

        # 创建多段线 - 按最近邻排序点
        ordered = [unique_pts[0]]
        remaining = unique_pts[1:]
        while remaining:
            last = ordered[-1]
            nearest_idx = 0
            nearest_dist = float('inf')
            for i, p in enumerate(remaining):
                d = math.hypot(p[0]-last[0], p[1]-last[1])
                if d < nearest_dist:
                    nearest_dist = d
                    nearest_idx = i
            ordered.append(remaining.pop(nearest_idx))

        poly = PolylineElement(ordered, closed=False)
        # 继承第一个选中元素的样式
        if lines:
            poly.style = lines[0].style.clone() if hasattr(lines[0].style, 'clone') else lines[0].style
        self.board.add_element(poly)

        # 删除原始线段
        for l in lines:
            if l in self.board.elements:
                self.board.elements.remove(l)

        self._clear_selection()
        self.board.status_bar.showMessage(f"合并完成: {len(lines)} 条线段 → 1 条多段线 ({len(ordered)} 个顶点)")
        self.cancel()
        self.board.set_default_command()

    def get_prompt(self):
        return "合并: 框选多条线段合并为多段线"

    def draw_preview(self, painter, coord_system):
        if self._selecting and self._drag_start and self._drag_end:
            s1 = coord_system.world_to_screen(*self._drag_start)
            s2 = coord_system.world_to_screen(*self._drag_end)
            x = min(s1[0], s2[0])
            y = min(s1[1], s2[1])
            w = abs(s2[0] - s1[0])
            h = abs(s2[1] - s1[1])
            pen = QPen(QColor(0, 120, 255), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(x, y, w, h)
            return True
        return False


class ChamferCommand(BaseCommand):
    name = "倒斜角"
    shortcut = "CHA"
    description = "在两线之间倒斜角"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._l1 = None
        self._l2 = None
        self._dist = 10.0

    def on_activate(self):
        self._l1 = None
        self._l2 = None
        self.board.status_bar.showMessage(f"倒斜角: 点击选择第一条线 (距离 {self._dist}mm) (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._l1 is None:
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if elem.element_type.value == '直线' and self._hit_test(elem, world_x, world_y):
                        self._l1 = elem
                        self.board.status_bar.showMessage("倒斜角: 选择第二条线")
                        self.board.viewport.update()
                        break
                return True
            elif self._l2 is None:
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if elem is not self._l1 and elem.element_type.value == '直线' and \
                       self._hit_test(elem, world_x, world_y):
                        self._l2 = elem
                        self._execute_chamfer()
                        return True
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_chamfer(self):
        if not self._l1 or not self._l2:
            self.cancel()
            self.board.set_default_command()
            return
        inter = self._line_intersection(
            self._l1.x1, self._l1.y1, self._l1.x2, self._l1.y2,
            self._l2.x1, self._l2.y1, self._l2.x2, self._l2.y2
        )
        if not inter:
            self.board.status_bar.showMessage("倒斜角: 两线不相交")
            self.cancel()
            self.board.set_default_command()
            return
        ix, iy = inter
        def trim_to_dist(line, cx, cy, dist):
            d1 = math.hypot(line.x1 - cx, line.y1 - cy)
            d2 = math.hypot(line.x2 - cx, line.y2 - cy)
            if d1 < d2:
                t = dist / d1 if d1 > 0 else 1
                line.x1 = cx + (line.x1 - cx) * min(1, t)
                line.y1 = cy + (line.y1 - cy) * min(1, t)
                return (line.x1, line.y1)
            else:
                t = dist / d2 if d2 > 0 else 1
                line.x2 = cx + (line.x2 - cx) * min(1, t)
                line.y2 = cy + (line.y2 - cy) * min(1, t)
                return (line.x2, line.y2)
        p1 = trim_to_dist(self._l1, ix, iy, self._dist)
        p2 = trim_to_dist(self._l2, ix, iy, self._dist)
        chamfer = LineElement(p1[0], p1[1], p2[0], p2[1])
        self.board.apply_current_layer_style(chamfer)
        self.board.add_element(chamfer)
        self.board.status_bar.showMessage("倒斜角: 已完成")
        self.cancel()
        self.board.set_default_command()

    def _line_intersection(self, x1, y1, x2, y2, x3, y3, x4, y4):
        dx1, dy1 = x2 - x1, y2 - y1
        dx2, dy2 = x4 - x3, y4 - y3
        det = dx1 * dy2 - dy1 * dx2
        if abs(det) < 1e-12:
            return None
        t = ((x3 - x1) * dy2 - (y3 - y1) * dx2) / det
        return (x1 + t * dx1, y1 + t * dy1)

    def on_cmd_confirm(self, text):
        try:
            d = float(text.strip())
            if d > 0:
                self._dist = d
                self.board.status_bar.showMessage(f"倒斜角距离设为 {d}mm")
                return True
        except ValueError:
            pass
        return False

    def get_prompt(self):
        if not self._l1:
            return f"倒斜角: 选择第一条线"
        return "倒斜角: 选择第二条线"

    def draw_preview(self, painter, coord_system):
        return False


class FilletCommand(BaseCommand):
    name = "圆角"
    shortcut = "F"
    description = "在两线之间倒圆角"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._l1 = None
        self._l2 = None
        self._radius = 10.0

    def on_activate(self):
        self._l1 = None
        self._l2 = None
        self.board.status_bar.showMessage(f"圆角: 点击选择第一条线 (半径 {self._radius}mm) (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._l1 is None:
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if elem.element_type.value == '直线' and self._hit_test(elem, world_x, world_y):
                        self._l1 = elem
                        self.board.status_bar.showMessage("圆角: 选择第二条线")
                        self.board.viewport.update()
                        break
                return True
            elif self._l2 is None:
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if elem is not self._l1 and elem.element_type.value == '直线' and \
                       self._hit_test(elem, world_x, world_y):
                        self._l2 = elem
                        self._execute_fillet()
                        return True
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_fillet(self):
        if not self._l1 or not self._l2:
            self.cancel()
            self.board.set_default_command()
            return
        inter = self._line_intersection(
            self._l1.x1, self._l1.y1, self._l1.x2, self._l1.y2,
            self._l2.x1, self._l2.y1, self._l2.x2, self._l2.y2
        )
        if not inter:
            self.board.status_bar.showMessage("圆角: 两线不相交")
            self.cancel()
            self.board.set_default_command()
            return
        ix, iy = inter
        def point_at_dist(line, cx, cy, dist):
            d1 = math.hypot(line.x1 - cx, line.y1 - cy)
            d2 = math.hypot(line.x2 - cx, line.y2 - cy)
            if d1 < d2:
                t = dist / d1 if d1 > 0 else 1
                return (cx + (line.x1 - cx) * t, cy + (line.y1 - cy) * t)
            else:
                t = dist / d2 if d2 > 0 else 1
                return (cx + (line.x2 - cx) * t, cy + (line.y2 - cy) * t)
        p1 = point_at_dist(self._l1, ix, iy, self._radius)
        p2 = point_at_dist(self._l2, ix, iy, self._radius)
        # 修改每条线上离交点最近的端点
        if math.hypot(self._l1.x1 - ix, self._l1.y1 - iy) < math.hypot(self._l1.x2 - ix, self._l1.y2 - iy):
            self._l1.x1, self._l1.y1 = p1
        else:
            self._l1.x2, self._l1.y2 = p1
        if math.hypot(self._l2.x1 - ix, self._l2.y1 - iy) < math.hypot(self._l2.x2 - ix, self._l2.y2 - iy):
            self._l2.x1, self._l2.y1 = p2
        else:
            self._l2.x2, self._l2.y2 = p2
        arc = LineElement(p1[0], p1[1], p2[0], p2[1])
        self.board.apply_current_layer_style(arc)
        self.board.add_element(arc)
        self.board.status_bar.showMessage("圆角: 已完成")
        self.cancel()
        self.board.set_default_command()

    def _line_intersection(self, x1, y1, x2, y2, x3, y3, x4, y4):
        dx1, dy1 = x2 - x1, y2 - y1
        dx2, dy2 = x4 - x3, y4 - y3
        det = dx1 * dy2 - dy1 * dx2
        if abs(det) < 1e-12:
            return None
        t = ((x3 - x1) * dy2 - (y3 - y1) * dx2) / det
        return (x1 + t * dx1, y1 + t * dy1)

    def on_cmd_confirm(self, text):
        try:
            r = float(text.strip())
            if r > 0:
                self._radius = r
                self.board.status_bar.showMessage(f"圆角半径设为 {r}mm")
                return True
        except ValueError:
            pass
        return False

    def get_prompt(self):
        if not self._l1:
            return f"圆角: 选择第一条线"
        return "圆角: 选择第二条线"

    def draw_preview(self, painter, coord_system):
        return False


class ExplodeCommand(BaseCommand):
    name = "分解"
    shortcut = "X"
    description = "分解多段线/多边形/矩形为线段"
    is_modify_command = True

    def on_activate(self):
        self.board.status_bar.showMessage("分解: 点击选择要分解的对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            for elem in reversed(self.board.elements):
                if not getattr(elem, 'visible', True):
                    continue
                if self._hit_test(elem, world_x, world_y):
                    self._execute_explode(elem)
                    self.board.viewport.update()
                    break
            return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_explode(self, elem):
        et = elem.element_type.value
        new_elements = []
        if et == '矩形':
            segs = elem.get_segments()
            for s, e in segs:
                l = LineElement(s[0], s[1], e[0], e[1])
                self.board.apply_current_layer_style(l)
                new_elements.append(l)
        elif et in ('多段线', '多边形'):
            segs = elem.get_segments()
            for s, e in segs:
                l = LineElement(s[0], s[1], e[0], e[1])
                self.board.apply_current_layer_style(l)
                new_elements.append(l)
        elif et == '圆':
            num = 36
            pts = []
            for i in range(num):
                a = 2 * math.pi * i / num
                pts.append((elem.cx + elem.radius * math.cos(a),
                           elem.cy + elem.radius * math.sin(a)))
            pts.append(pts[0])
            for i in range(len(pts) - 1):
                l = LineElement(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
                self.board.apply_current_layer_style(l)
                new_elements.append(l)
        elif et == '椭圆':
            pts = elem.sample_points(36)
            for i in range(len(pts) - 1):
                l = LineElement(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
                self.board.apply_current_layer_style(l)
                new_elements.append(l)

        if new_elements:
            for e in new_elements:
                self.board.add_element(e)
            if elem in self.board.elements:
                self.board.elements.remove(elem)
            self.board.status_bar.showMessage(
                f"分解完成: {elem.element_type.value} → {len(new_elements)} 条线段")
        else:
            self.board.status_bar.showMessage("分解: 此对象不支持分解")
        self.cancel()
        self.board.set_default_command()

    def get_prompt(self):
        return "分解: 选择要分解的对象"

    def draw_preview(self, painter, coord_system):
        return False
