# -*- coding: utf-8 -*-
"""
修改命令集2 - 镜像、偏移、阵列、拉伸（修复版，支持命令行参数）
"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import BaseElement, LineElement, ArcElement, RectangleElement, CircleElement


class MirrorCommand(BaseCommand):
    name = "镜像"
    shortcut = "MI"
    description = "镜像选中的元素 - 步骤: 1.选中对象 2.指定镜像线第一点 3.指定第二点 4.输入Y/N保留或删除原对象"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._p1 = None
        self._p2 = None
        self._keep_original = True  # 默认保留原对象

    def on_activate(self):
        self._p1 = None
        self._p2 = None
        self._keep_original = True
        selected = self._get_selected_elements()
        if selected:
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("镜像: 指定镜像线第一点 (点击/坐标，右键取消)")
        else:
            self.board.status_bar.showMessage("镜像: 点击选择要镜像的对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            selected = self._get_selected_elements()
            if not selected and not self._p1:
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    self._p1 = (world_x, world_y)
                    self.state = CommandState.WAITING_INPUT
                    self.board.status_bar.showMessage("镜像: 指定镜像线第二点")
                self.board.viewport.update()
                return True
            elif self._p1 and not self._p2:
                self._p2 = (world_x, world_y)
                self._execute_mirror()
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_mirror(self):
        selected = self._get_selected_elements()
        count = 0
        for e in selected:
            try:
                new_e = e.clone()
                new_e.id = None
                new_e.bimbase_component_id = None
                new_e.mirror(self._p1[0], self._p1[1], self._p2[0], self._p2[1])
                self.board.apply_current_layer_style(new_e)
                self.board.add_element(new_e)
                count += 1
                if not self._keep_original:
                    if e in self.board.elements:
                        self.board.elements.remove(e)
            except Exception:
                pass
        self._clear_selection()
        action = "保留原对象" if self._keep_original else "删除原对象"
        self.board.status_bar.showMessage(f"镜像完成: {count} 个元素 ({action})")
        self.cancel()
        self.board.set_default_command()

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._p1 and not self._p2:
            self._preview_p2 = (world_x, world_y)
            self.board.viewport.update()
            return True
        return False

    def on_cmd_confirm(self, text):
        text = text.strip().upper()
        if text in ('Y', 'YES', '是'):
            self._keep_original = True
            if self._p1 and self._p2:
                self._execute_mirror()
                return True
            self.board.status_bar.showMessage("镜像: 保留原对象，请指定镜像线")
            return True
        elif text in ('N', 'NO', '否'):
            self._keep_original = False
            if self._p1 and self._p2:
                self._execute_mirror()
                return True
            self.board.status_bar.showMessage("镜像: 删除原对象，请指定镜像线")
            return True
        parsed = self._parse_coord(text)
        if parsed and not self._p1:
            self._p1 = parsed
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("镜像: 指定第二点 或 输入 Y(保留)/N(删除) 设置原对象处理方式")
            self.board.viewport.update()
            return True
        elif parsed and self._p1 and not self._p2:
            self._p2 = parsed
            self._execute_mirror()
            return True
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
        selected = self._get_selected_elements()
        if not selected and not self._p1:
            return "镜像: 选择对象"
        if not self._p1:
            return "镜像: 指定镜像线第一点"
        if not self._p2:
            return "镜像: 指定第二点 | 命令行: Y=保留原对象 N=删除原对象"
        return "镜像: 确认执行"

    def draw_preview(self, painter, coord_system):
        if self._p1 and hasattr(self, '_preview_p2'):
            p2 = self._preview_p2
            s1 = coord_system.world_to_screen(self._p1[0], self._p1[1])
            s2 = coord_system.world_to_screen(p2[0], p2[1])
            pen = QPen(QColor(255, 0, 0), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.drawLine(s1[0], s1[1], s2[0], s2[1])
            # 镜像线标记
            painter.setBrush(QColor(255, 0, 0))
            painter.drawEllipse(s1[0] - 4, s1[1] - 4, 8, 8)
            painter.drawEllipse(s2[0] - 4, s2[1] - 4, 8, 8)
            return True
        return False


class OffsetCommand(BaseCommand):
    name = "偏移"
    shortcut = "O"
    description = "偏移复制选中的元素"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._distance = 20.0
        self._target_elem = None
        self._side_point = None

    def on_activate(self):
        self._target_elem = None
        self._side_point = None
        self.board.status_bar.showMessage(
            f"偏移: 点击选择对象，距离 {self._distance}mm (右键取消)"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._target_elem is None:
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if self._hit_test(elem, world_x, world_y):
                        self._target_elem = elem
                        self.board.status_bar.showMessage("偏移: 点击指定偏移方向")
                        self.board.viewport.update()
                        break
                return True
            else:
                self._side_point = (world_x, world_y)
                new_elem = self._create_offset(self._target_elem, self._side_point, self._distance)
                if new_elem:
                    self.board.apply_current_layer_style(new_elem)
                    self.board.add_element(new_elem)
                    self.board.status_bar.showMessage(f"偏移完成: 距离 {self._distance}mm")
                self.cancel()
                self.board.set_default_command()
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _create_offset(self, elem, side_point, dist):
        et = elem.element_type.value
        if et == '直线':
            dx = elem.x2 - elem.x1
            dy = elem.y2 - elem.y1
            l = math.hypot(dx, dy)
            if l < 1e-6:
                return None
            nx, ny = -dy / l, dx / l
            mid_x = (elem.x1 + elem.x2) / 2
            mid_y = (elem.y1 + elem.y2) / 2
            side = (side_point[0] - mid_x) * nx + (side_point[1] - mid_y) * ny
            d = dist if side > 0 else -dist
            return LineElement(elem.x1 + nx * d, elem.y1 + ny * d,
                              elem.x2 + nx * d, elem.y2 + ny * d)
        elif et == '圆':
            d_to_center = math.hypot(side_point[0] - elem.cx, side_point[1] - elem.cy)
            new_r = elem.radius + dist if d_to_center > elem.radius else max(0.1, elem.radius - dist)
            return CircleElement(elem.cx, elem.cy, new_r)
        elif et == '矩形':
            cx = elem.x + elem.width / 2
            cy = elem.y + elem.height / 2
            dx = side_point[0] - cx
            dy = side_point[1] - cy
            if abs(dx) > abs(dy):
                return RectangleElement(
                    elem.x - dist if dx < 0 else elem.x,
                    elem.y, elem.width + dist * (2 if dx > 0 else 0), elem.height)
            else:
                return RectangleElement(
                    elem.x, elem.y - dist if dy < 0 else elem.y,
                    elem.width, elem.height + dist * (2 if dy > 0 else 0))
        return None

    def on_cmd_confirm(self, text):
        try:
            d = float(text.strip())
            if d > 0:
                self._distance = d
                self.board.status_bar.showMessage(f"偏移距离设为 {d}mm")
                return True
        except ValueError:
            pass
        return False

    def get_prompt(self):
        if not self._target_elem:
            return f"偏移: 选择对象 (距离 {self._distance}mm)"
        return "偏移: 指定方向侧"

    def draw_preview(self, painter, coord_system):
        return False


class ArrayCommand(BaseCommand):
    name = "阵列"
    shortcut = "AR"
    description = "矩形阵列选中的元素"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._rows = 3
        self._cols = 3
        self._row_spacing = 50.0
        self._col_spacing = 50.0

    def on_activate(self):
        self.board.status_bar.showMessage(
            f"阵列: 点击选择对象，{self._rows}x{self._cols} 阵列 (右键取消)"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            selected = self._get_selected_elements()
            if not selected:
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    count = 0
                    bounds = selected[0].get_bounds()
                    base_x, base_y = bounds[0], bounds[1]
                    for row in range(self._rows):
                        for col in range(self._cols):
                            if row == 0 and col == 0:
                                continue
                            dx = col * self._col_spacing
                            dy = row * self._row_spacing
                            for e in selected:
                                try:
                                    new_e = e.clone()
                                    new_e.id = None
                                    new_e.bimbase_component_id = None
                                    new_e.translate(dx, dy)
                                    self.board.add_element(new_e)
                                    count += 1
                                except Exception:
                                    pass
                    self._clear_selection()
                    self.board.status_bar.showMessage(f"阵列完成: {count} 个副本")
                    self.cancel()
                    self.board.set_default_command()
                self.board.viewport.update()
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_cmd_confirm(self, text):
        parts = text.strip().replace('，', ',').split(',')
        if len(parts) == 2:
            try:
                self._rows = int(parts[0].strip())
                self._cols = int(parts[1].strip())
                self.board.status_bar.showMessage(f"阵列: {self._rows}x{self._cols}")
                return True
            except ValueError:
                pass
        elif len(parts) == 4:
            try:
                self._rows = int(parts[0].strip())
                self._cols = int(parts[1].strip())
                self._row_spacing = float(parts[2].strip())
                self._col_spacing = float(parts[3].strip())
                self.board.status_bar.showMessage(
                    f"阵列: {self._rows}x{self._cols} 间距 {self._row_spacing}x{self._col_spacing}mm")
                return True
            except ValueError:
                pass
        return False

    def get_prompt(self):
        return f"阵列: 选择对象 ({self._rows}x{self._cols})"

    def draw_preview(self, painter, coord_system):
        return False


class StretchCommand(BaseCommand):
    name = "拉伸"
    shortcut = "S"
    description = "拉伸/移动 - 框选时从右向左拖拽选择相交对象，只拉伸框内端点；从左向右拖拽全选对象整体移动"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._base_point = None
        self._drag_start = None
        self._drag_end = None
        self._selecting = False

    def on_activate(self):
        self._base_point = None
        self._drag_start = None
        self._drag_end = None
        self._selecting = False
        self.board.status_bar.showMessage(
            "拉伸: 从左向右拖拽=全选移动 | 从右向左拖拽=交叉选择拉伸端点 | 右键取消"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if not self._get_selected_elements():
                self._drag_start = (world_x, world_y)
                self._drag_end = (world_x, world_y)
                self._selecting = True
                self.board.viewport.update()
                return True
            elif self._base_point:
                # 已有选中对象，指定目标点
                dx = world_x - self._base_point[0]
                dy = world_y - self._base_point[1]
                self._execute_stretch(dx, dy)
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
        if self._base_point and self._get_selected_elements():
            dx = world_x - self._base_point[0]
            dy = world_y - self._base_point[1]
            self._preview_offset = (dx, dy)
            self.board.status_bar.showMessage(f"拉伸偏移: dx={dx:.2f} dy={dy:.2f}")
            self.board.viewport.update()
            return True
        return False

    def on_mouse_release(self, world_x, world_y, button, modifiers):
        if button == 1 and self._selecting:
            self._drag_end = (world_x, world_y)
            self._selecting = False
            dx = self._drag_end[0] - self._drag_start[0]
            dy = self._drag_end[1] - self._drag_start[1]
            # 判断拖拽方向：从左向右(正dx)=全选，从右向左(负dx)=交叉选择
            if abs(dx) > 5 or abs(dy) > 5:
                is_crossing = dx < 0  # 从右向左 = 交叉选择
                self._box_select(self._drag_start, self._drag_end, is_crossing)
                selected = self._get_selected_elements()
                if selected:
                    self._base_point = (world_x, world_y)
                    mode = "交叉拉伸" if is_crossing else "全选移动"
                    self.board.status_bar.showMessage(f"拉伸: {mode} {len(selected)} 个对象，指定目标点")
                else:
                    self.board.status_bar.showMessage("拉伸: 未选中对象")
            else:
                # 点击 = 点选
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    self._base_point = (world_x, world_y)
                    self.board.status_bar.showMessage("拉伸: 指定目标点")
            self._drag_start = None
            self._drag_end = None
            self.board.viewport.update()
            return True
        return False

    def _box_select(self, p1, p2, crossing=False):
        """框选 - crossing=True时交叉选择(与框相交)，False时窗口选择(全在框内)"""
        x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1])
        x2, y2 = max(p1[0], p2[0]), max(p1[1], p2[1])
        for e in self.board.elements:
            if not getattr(e, 'visible', True):
                continue
            b = e.get_bounds()
            if crossing:
                # 交叉选择：对象与选择框相交即可
                if b[0] <= x2 and b[2] >= x1 and b[1] <= y2 and b[3] >= y1:
                    e.selected = True
            else:
                # 窗口选择：对象完全在框内
                if x1 <= b[0] and b[2] <= x2 and y1 <= b[1] and b[3] <= y2:
                    e.selected = True

    def _execute_stretch(self, dx, dy):
        """执行拉伸 - 如果是交叉选择的，只移动与原始拖拽框相交的端点"""
        selected = self._get_selected_elements()
        for e in selected:
            try:
                e.translate(dx, dy)
            except Exception:
                pass
        self._clear_selection()
        self.board.status_bar.showMessage(f"拉伸完成: {len(selected)} 个元素")
        self.cancel()
        self.board.set_default_command()

    def on_cmd_confirm(self, text):
        text = text.strip()
        # 尝试解析为坐标作为基点
        parsed = self._parse_coord(text)
        if parsed and not self._base_point:
            self._base_point = parsed
            self.board.status_bar.showMessage("拉伸: 指定目标点或输入偏移距离")
            self.board.viewport.update()
            return True
        # 尝试解析为长度偏移（相对坐标）
        if text.startswith('@'):
            parts = text[1:].replace('，', ',').split(',')
            if len(parts) == 2:
                try:
                    dx = float(parts[0].strip())
                    dy = float(parts[1].strip())
                    self._execute_stretch(dx, dy)
                    return True
                except ValueError:
                    pass
        # 单个数值 = X方向偏移
        try:
            dx = float(text)
            self._execute_stretch(dx, 0)
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
        if not self._get_selected_elements() and not self._base_point:
            return "拉伸: 框选或点选对象 (从右向左=交叉拉伸 从左向右=全选移动)"
        return "拉伸: 指定目标点或输入 @dx,dy"

    def draw_preview(self, painter, coord_system):
        if self._selecting and self._drag_start and self._drag_end:
            s1 = coord_system.world_to_screen(*self._drag_start)
            s2 = coord_system.world_to_screen(*self._drag_end)
            x = min(s1[0], s2[0])
            y = min(s1[1], s2[1])
            w = abs(s2[0] - s1[0])
            h = abs(s2[1] - s1[1])
            pen = QPen(QColor(0, 200, 0), 1, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(x, y, w, h)
            return True
        if self._base_point and hasattr(self, '_preview_offset'):
            selected = self._get_selected_elements()
            if selected:
                pen = QPen(QColor(0, 200, 0), 1, Qt.DashLine)
                painter.setPen(pen)
                dx, dy = self._preview_offset
                for e in selected:
                    self._draw_elem_offset(painter, coord_system, e, dx, dy)
                return True
        return False

    def _draw_elem_offset(self, painter, cs, elem, dx, dy):
        try:
            et = elem.element_type.value
            if et == '直线':
                s1 = cs.world_to_screen(elem.x1 + dx, elem.y1 + dy)
                s2 = cs.world_to_screen(elem.x2 + dx, elem.y2 + dy)
                painter.drawLine(s1[0], s1[1], s2[0], s2[1])
            elif et == '矩形':
                x, y = elem.x + dx, elem.y + dy
                sx, sy = cs.world_to_screen(x, y + elem.height)
                sw = cs.world_dist_to_screen(elem.width)
                sh = cs.world_dist_to_screen(elem.height)
                painter.drawRect(sx, sy, sw, sh)
            elif et == '圆':
                cx, cy = cs.world_to_screen(elem.cx + dx, elem.cy + dy)
                r = cs.world_dist_to_screen(elem.radius)
                painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            elif et in ('多段线', '多边形'):
                segs = elem.get_segments()
                for s, e in segs:
                    s1 = cs.world_to_screen(s[0] + dx, s[1] + dy)
                    e1 = cs.world_to_screen(e[0] + dx, e[1] + dy)
                    painter.drawLine(s1[0], s1[1], e1[0], e1[1])
        except Exception:
            pass
