# -*- coding: utf-8 -*-
"""
修改命令集2 - v1.5 P0
镜像、偏移、阵列、拉伸（P0修复版，CAD标准流程）

StretchCommand 重构要点:
- 从左向右=窗口选择: 完全在框内的对象整体移动
- 从右向左=交叉选择: 与框相交的对象，只移动在原始框内的端点
- 支持直线、多段线、矩形、圆弧的端点精确判断
- 支持先点选/框选对象，再指定基点和目标点

v1.5 P0 更新内容 (2026-04-27):
- StretchCommand: CAD标准交叉窗口拉伸，三步流程（框选→基点→目标点）
- 整合v1.4 Mirror/Offset/Array修复
"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import (BaseElement, LineElement, ArcElement,
                               RectangleElement, CircleElement, PolylineElement)


# ============================================================
# 镜像
# ============================================================
class MirrorCommand(BaseCommand):
    name = "镜像"
    shortcut = "MI"
    description = "镜像选中的元素 - 步骤: 1.选中对象 2.指定镜像线第一点 3.指定第二点 4.输入Y/N保留或删除原对象"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._p1 = None
        self._p2 = None
        self._keep_original = True

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
            self.board.status_bar.showMessage("镜像: 指定第二点 或 输入 Y(保留)/N(删除)")
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
            painter.setBrush(QColor(255, 0, 0))
            painter.drawEllipse(s1[0] - 4, s1[1] - 4, 8, 8)
            painter.drawEllipse(s2[0] - 4, s2[1] - 4, 8, 8)
            return True
        return False


# ============================================================
# 偏移
# ============================================================
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


# ============================================================
# 阵列
# ============================================================
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


# ============================================================
# 拉伸 - CAD标准交叉窗口拉伸（P0重构）
# ============================================================
class StretchCommand(BaseCommand):
    name = "拉伸"
    shortcut = "S"
    description = ("CAD标准拉伸: "
                   "从左向右=窗口全选整体移动 | "
                   "从右向左=交叉选择只拉伸框内端点")
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        # 选择阶段
        self._drag_start = None
        self._drag_end = None
        self._selecting = False
        self._is_crossing = False  # True=交叉选择(从右向左), False=窗口选择(从左向右)
        # 位移阶段
        self._base_point = None
        self._target_point = None
        self._preview_offset = None

    def on_activate(self):
        self._reset_state()
        self.board.status_bar.showMessage(
            "拉伸: 框选或点选对象 (从左向右=窗口全选移动 从右向左=交叉拉伸端点 | 右键取消)"
        )

    def _reset_state(self):
        self._drag_start = None
        self._drag_end = None
        self._selecting = False
        self._is_crossing = False
        self._base_point = None
        self._target_point = None
        self._preview_offset = None
        self._sel_box = None

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            # 阶段1: 还没有选中任何对象 → 开始选择
            selected = self._get_selected_elements()
            if not selected and not self._base_point:
                self._drag_start = (world_x, world_y)
                self._drag_end = (world_x, world_y)
                self._selecting = True
                self.board.viewport.update()
                return True
            # 阶段2: 已有选中对象，还没指定基点 → 记录基点
            elif selected and not self._base_point:
                self._base_point = (world_x, world_y)
                self.board.status_bar.showMessage(
                    "拉伸: 指定目标点 (点击/输入@dx,dy/输入距离)"
                )
                self.board.viewport.update()
                return True
            # 阶段3: 有基点 → 指定目标点，执行拉伸
            elif self._base_point:
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
            # 实时预览选择方向
            if self._drag_start and self._drag_end:
                ddx = self._drag_end[0] - self._drag_start[0]
                mode = "交叉拉伸" if ddx < 0 else "窗口全选"
                self.board.status_bar.showMessage(
                    f"拉伸: 拖拽中... {mode}"
                )
            self.board.viewport.update()
            return True
        if self._base_point and not self._target_point:
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
            if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                # 判断方向: 从左向右=窗口选择(dx>0), 从右向左=交叉选择(dx<0)
                self._is_crossing = dx < 0
                self._box_select(self._drag_start, self._drag_end, self._is_crossing)
                selected = self._get_selected_elements()
                if selected:
                    mode = "交叉拉伸(框内端点)" if self._is_crossing else "窗口全选移动"
                    self.board.status_bar.showMessage(
                        f"拉伸: {mode} {len(selected)} 个对象，指定基点"
                    )
                else:
                    self.board.status_bar.showMessage("拉伸: 未选中对象，请重新选择")
            else:
                # 点选
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    self.board.status_bar.showMessage("拉伸: 指定基点")
            self._drag_start = None
            self._drag_end = None
            self.board.viewport.update()
            return True
        return False

    def _box_select(self, p1, p2, crossing=False):
        """CAD标准框选
        crossing=True(从右向左): 与框相交的对象被选中
        crossing=False(从左向右): 完全在框内的对象被选中
        """
        x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1])
        x2, y2 = max(p1[0], p2[0]), max(p1[1], p2[1])
        self._sel_box = (x1, y1, x2, y2)  # 保存选择框用于交叉拉伸端点判断
        for e in self.board.elements:
            if not getattr(e, 'visible', True):
                continue
            b = e.get_bounds()
            if crossing:
                # 交叉选择: 包围盒与选择框相交即可
                if b[0] <= x2 and b[2] >= x1 and b[1] <= y2 and b[3] >= y1:
                    e.selected = True
            else:
                # 窗口选择: 完全在框内
                if x1 <= b[0] and b[2] <= x2 and y1 <= b[1] and b[3] <= y2:
                    e.selected = True

    def _point_in_rect(self, px: float, py: float, r1, r2) -> bool:
        """判断点是否在选择框内"""
        x1, y1 = min(r1[0], r2[0]), min(r1[1], r2[1])
        x2, y2 = max(r1[0], r2[0]), max(r1[1], r2[1])
        return x1 <= px <= x2 and y1 <= py <= y2

    def _execute_stretch(self, dx: float, dy: float):
        """执行拉伸 - CAD标准逻辑"""
        selected = self._get_selected_elements()
        if not selected:
            self.board.status_bar.showMessage("拉伸: 没有选中对象")
            self.cancel()
            self.board.set_default_command()
            return

        # 获取原始选择框（用于交叉选择的端点判断）
        # 注意：需要保存选择时的框，所以在on_mouse_release中计算
        count = 0
        for e in selected:
            try:
                et = e.element_type.value
                if self._is_crossing:
                    # 交叉选择模式: 只移动在原始选择框内的端点
                    count += self._stretch_element_crossing(e, dx, dy)
                else:
                    # 窗口选择模式: 整体移动
                    e.translate(dx, dy)
                    count += 1
            except Exception:
                pass

        mode = "交叉拉伸" if self._is_crossing else "窗口全选移动"
        self._clear_selection()
        self.board.status_bar.showMessage(f"拉伸完成: {mode} {count} 个元素")
        self.cancel()
        self.board.set_default_command()

    def _stretch_element_crossing(self, elem, dx: float, dy: float) -> int:
        """交叉选择模式: 只移动原始选择框内的端点，返回修改的端点数"""
        et = elem.element_type.value
        # 使用保存的选择框坐标
        if not hasattr(self, '_sel_box'):
            # 如果没有保存的选择框（点选模式），整体移动
            elem.translate(dx, dy)
            return 1

        bx1, by1, bx2, by2 = self._sel_box
        modified = 0

        if et == '直线':
            p1_in = bx1 <= elem.x1 <= bx2 and by1 <= elem.y1 <= by2
            p2_in = bx1 <= elem.x2 <= bx2 and by1 <= elem.y2 <= by2
            if p1_in:
                elem.x1 += dx
                elem.y1 += dy
                modified += 1
            if p2_in:
                elem.x2 += dx
                elem.y2 += dy
                modified += 1
        elif et in ('多段线', '多边形'):
            for i, (px, py) in enumerate(elem.points):
                if bx1 <= px <= bx2 and by1 <= py <= by2:
                    elem.points[i] = (px + dx, py + dy)
                    modified += 1
        elif et == '矩形':
            corners = elem.get_corners()
            new_corners = list(corners)
            for i, (px, py) in enumerate(corners):
                if bx1 <= px <= bx2 and by1 <= py <= by2:
                    new_corners[i] = (px + dx, py + dy)
                    modified += 1
            # 从角点重建矩形（简化：取新的包围盒）
            xs = [c[0] for c in new_corners]
            ys = [c[1] for c in new_corners]
            elem.x = min(xs)
            elem.y = min(ys)
            elem.width = max(xs) - min(xs)
            elem.height = max(ys) - min(ys)
        elif et == '圆弧':
            # 圆心在框内则移动整个圆弧
            center_in = bx1 <= elem.cx <= bx2 and by1 <= elem.cy <= by2
            if center_in:
                elem.cx += dx
                elem.cy += dy
                modified += 1
        elif et == '圆':
            center_in = bx1 <= elem.cx <= bx2 and by1 <= elem.cy <= by2
            if center_in:
                elem.cx += dx
                elem.cy += dy
                modified += 1
        elif et == '椭圆':
            center_in = bx1 <= elem.cx <= bx2 and by1 <= elem.cy <= by2
            if center_in:
                elem.cx += dx
                elem.cy += dy
                modified += 1
        elif et == '点':
            if bx1 <= elem.x <= bx2 and by1 <= elem.y <= by2:
                elem.x += dx
                elem.y += dy
                modified += 1

        if modified == 0:
            # 没有端点在框内，但整体相交 → 整体移动
            elem.translate(dx, dy)
            return 1
        return 1

    def on_cmd_confirm(self, text):
        text = text.strip()
        parsed = self._parse_coord(text)
        if parsed and not self._base_point:
            self._base_point = parsed
            self.board.status_bar.showMessage("拉伸: 指定目标点或输入偏移距离")
            self.board.viewport.update()
            return True
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
        try:
            val = float(text)
            # 使用最后预览的角度方向
            if hasattr(self, '_last_preview_angle'):
                angle = math.radians(self._last_preview_angle)
                dx = val * math.cos(angle)
                dy = val * math.sin(angle)
            else:
                dx = val
                dy = 0
            self._execute_stretch(dx, dy)
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
        selected = self._get_selected_elements()
        if not selected and not self._base_point:
            return "拉伸: 框选或点选对象 (从右向左=交叉拉伸 从左向右=全选移动)"
        if not self._base_point:
            return "拉伸: 指定基点"
        return "拉伸: 指定目标点或输入 @dx,dy"

    def draw_preview(self, painter, coord_system):
        # 选择框预览
        if self._selecting and self._drag_start and self._drag_end:
            s1 = coord_system.world_to_screen(*self._drag_start)
            s2 = coord_system.world_to_screen(*self._drag_end)
            x = min(s1[0], s2[0])
            y = min(s1[1], s2[1])
            w = abs(s2[0] - s1[0])
            h = abs(s2[1] - s1[1])
            # 从右向左(交叉)=绿色虚线，从左向右(窗口)=蓝色实线
            ddx = self._drag_end[0] - self._drag_start[0]
            if ddx < 0:
                pen = QPen(QColor(0, 200, 0), 1, Qt.DashLine)
            else:
                pen = QPen(QColor(0, 120, 255), 1, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(x, y, w, h)
            return True
        # 位移预览
        if self._base_point and self._preview_offset:
            selected = self._get_selected_elements()
            if selected:
                pen = QPen(QColor(0, 200, 0), 1, Qt.DashLine)
                painter.setPen(pen)
                odx, ody = self._preview_offset
                for e in selected:
                    self._draw_elem_offset(painter, coord_system, e, odx, ody)
                # 绘制基点
                bp = coord_system.world_to_screen(self._base_point[0], self._base_point[1])
                painter.setBrush(QColor(255, 0, 0))
                painter.drawEllipse(bp[0] - 4, bp[1] - 4, 8, 8)
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
            elif et == '圆弧':
                pts = elem.sample_points(36)
                sp = [cs.world_to_screen(p[0] + dx, p[1] + dy) for p in pts]
                for i in range(len(sp) - 1):
                    painter.drawLine(sp[i][0], sp[i][1], sp[i+1][0], sp[i+1][1])
            elif et in ('多段线', '多边形'):
                segs = elem.get_segments()
                for s, e in segs:
                    s1 = cs.world_to_screen(s[0] + dx, s[1] + dy)
                    e1 = cs.world_to_screen(e[0] + dx, e[1] + dy)
                    painter.drawLine(s1[0], s1[1], e1[0], e1[1])
        except Exception:
            pass
