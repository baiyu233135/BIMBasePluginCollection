# -*- coding: utf-8 -*-
"""
修改命令集3 - v1.5 P0
修剪、延伸、打断、合并、倒角、圆角、分解（P0修复版，CAD标准流程）

ExtendCommand 重构:
- CAD标准: 先选择边界边(可多选,右键结束), 再选择要延伸的对象
- 延伸到最近的边界交点

FilletCommand 修复:
- CAD标准: 先设置半径, 再依次选择两条线
- 用真正的ArcElement圆弧连接两线
- 自动修剪两线到圆弧端点

ChamferCommand 修复:
- CAD标准: 设置两个距离(D1,D2), 依次选择两条线
- 两线分别从交点缩进D1/D2, 直线连接

v1.5 P0 更新内容 (2026-04-27):
- ExtendCommand: CAD标准两步流程（选边界→选延伸对象）
- FilletCommand: 流程修复为"先选两条线→点击命令→输入半径→自动执行"
- ChamferCommand: 流程修复为"先选两条线→点击命令→输入距离→自动执行"
- 整合v1.4 Trim/Break/Join/Explode修复
"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import LineElement, ArcElement, PolylineElement


# ============================================================
# 工具函数
# ============================================================
def _point_to_segment_dist(px, py, x1, y1, x2, y2):
    """点到线段的距离"""
    dx, dy = x2 - x1, y2 - y1
    len_sq = dx*dx + dy*dy
    if len_sq < 1e-12:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1)*dx + (py - y1)*dy) / len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _line_intersection(x1, y1, x2, y2, x3, y3, x4, y4):
    """计算两线段/直线的交点（不限于线段范围内）"""
    dx1, dy1 = x2 - x1, y2 - y1
    dx2, dy2 = x4 - x3, y4 - y3
    det = dx1 * dy2 - dy1 * dx2
    if abs(det) < 1e-12:
        return None  # 平行
    t = ((x3 - x1) * dy2 - (y3 - y1) * dx2) / det
    return (x1 + t * dx1, y1 + t * dy1)


def _extend_to_boundary(line_elem, bx1, by1, bx2, by2):
    """将直线延伸到与边界线的交点，返回延伸后的端点坐标，None表示无法延伸"""
    # 求直线与边界线的交点
    inter = _line_intersection(
        line_elem.x1, line_elem.y1, line_elem.x2, line_elem.y2,
        bx1, by1, bx2, by2
    )
    if inter is None:
        return None
    ix, iy = inter

    # 判断哪个端点需要延伸（离边界线近的端点）
    # 计算线段方向向量
    dx = line_elem.x2 - line_elem.x1
    dy = line_elem.y2 - line_elem.y1
    line_len = math.hypot(dx, dy)
    if line_len < 1e-12:
        return None

    # 参数化: P = P1 + t * (P2 - P1)
    # 求交点对应的t值
    if abs(dx) > abs(dy):
        t = (ix - line_elem.x1) / dx if abs(dx) > 1e-12 else 0
    else:
        t = (iy - line_elem.y1) / dy if abs(dy) > 1e-12 else 0

    # 判断哪个端点"朝向"边界线
    # 计算两端点到边界线的距离
    d1 = _point_to_segment_dist(line_elem.x1, line_elem.y1, bx1, by1, bx2, by2)
    d2 = _point_to_segment_dist(line_elem.x2, line_elem.y2, bx1, by1, bx2, by2)

    if d1 < d2:
        # 端点1更近，将端点1延伸到交点
        return (ix, iy, line_elem.x2, line_elem.y2)
    else:
        # 端点2更近，将端点2延伸到交点
        return (line_elem.x1, line_elem.y1, ix, iy)


def _trim_line_to_point(line_elem, tx, ty, keep_end='near'):
    """将直线修剪到指定点，保留朝指定方向的部分"""
    d1 = math.hypot(line_elem.x1 - tx, line_elem.y1 - ty)
    d2 = math.hypot(line_elem.x2 - tx, line_elem.y2 - ty)
    if keep_end == 'near':
        if d1 < d2:
            line_elem.x1, line_elem.y1 = tx, ty
        else:
            line_elem.x2, line_elem.y2 = tx, ty
    else:
        if d1 > d2:
            line_elem.x1, line_elem.y1 = tx, ty
        else:
            line_elem.x2, line_elem.y2 = tx, ty


# ============================================================
# 修剪
# ============================================================
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


# ============================================================
# 延伸 - CAD标准边界延伸（P0重构）
# ============================================================
class ExtendCommand(BaseCommand):
    name = "延伸"
    shortcut = "EX"
    description = "CAD标准延伸: 先选边界边(可多选,右键结束), 再选要延伸的对象"
    is_modify_command = True

    STEP_SELECT_BOUNDARY = 0
    STEP_EXTEND = 1

    def __init__(self, board):
        super().__init__(board)
        self._step = self.STEP_SELECT_BOUNDARY
        self._boundaries = []  # [(x1,y1,x2,y2), ...]

    def on_activate(self):
        self._step = self.STEP_SELECT_BOUNDARY
        self._boundaries = []
        self.board.status_bar.showMessage(
            "延伸: 选择边界边 (点击选择, 可多选, 右键结束边界选择)"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._step == self.STEP_SELECT_BOUNDARY:
                # 选择边界边
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if self._hit_test(elem, world_x, world_y):
                        et = elem.element_type.value
                        if et == '直线':
                            self._boundaries.append((elem.x1, elem.y1, elem.x2, elem.y2))
                            self.board.status_bar.showMessage(
                                f"延伸: 已选 {len(self._boundaries)} 条边界, 继续选择或右键结束"
                            )
                            self.board.viewport.update()
                        elif et in ('多段线', '多边形', '矩形'):
                            for s, e in elem.get_segments():
                                self._boundaries.append((s[0], s[1], e[0], e[1]))
                            self.board.status_bar.showMessage(
                                f"延伸: 已选 {len(self._boundaries)} 条边界边, 继续或右键结束"
                            )
                            self.board.viewport.update()
                        break
                return True
            elif self._step == self.STEP_EXTEND:
                # 选择要延伸的对象
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if self._hit_test(elem, world_x, world_y):
                        self._extend_element(elem)
                        self.board.viewport.update()
                        break
                return True
        elif button == 2:
            if self._step == self.STEP_SELECT_BOUNDARY:
                if not self._boundaries:
                    self.cancel()
                    self.board.set_default_command()
                    return True
                # 结束边界选择，进入延伸阶段
                self._step = self.STEP_EXTEND
                self.board.status_bar.showMessage(
                    f"延伸: 选择要延伸的对象 (已选 {len(self._boundaries)} 条边界 | 右键结束命令)"
                )
                self.board.viewport.update()
                return True
            else:
                self.cancel()
                self.board.set_default_command()
                return True
        return False

    def _extend_element(self, elem):
        """将对象延伸到最近的边界"""
        et = elem.element_type.value
        if et != '直线':
            self.board.status_bar.showMessage("延伸: 目前只支持直线延伸")
            return

        if not self._boundaries:
            return

        # 找到与直线最近的有效交点
        best_result = None
        best_dist = float('inf')

        for bx1, by1, bx2, by2 in self._boundaries:
            result = _extend_to_boundary(elem, bx1, by1, bx2, by2)
            if result:
                nx1, ny1, nx2, ny2 = result
                # 计算延伸量
                orig_len = elem.length()
                new_len = math.hypot(nx2 - nx1, ny2 - ny1)
                if new_len > orig_len:
                    d = new_len - orig_len
                    if d < best_dist:
                        best_dist = d
                        best_result = result

        if best_result:
            elem.x1, elem.y1, elem.x2, elem.y2 = best_result
            self.board.status_bar.showMessage(f"延伸完成: 延伸了 {best_dist:.2f}mm")
        else:
            self.board.status_bar.showMessage("延伸: 无法延伸到边界（平行或无交点）")

    def draw_preview(self, painter, coord_system):
        if self._boundaries:
            pen = QPen(QColor(255, 128, 0), 2, Qt.DashLine)
            painter.setPen(pen)
            for bx1, by1, bx2, by2 in self._boundaries:
                s1 = coord_system.world_to_screen(bx1, by1)
                s2 = coord_system.world_to_screen(bx2, by2)
                painter.drawLine(s1[0], s1[1], s2[0], s2[1])
            return True
        return False

    def get_prompt(self):
        if self._step == self.STEP_SELECT_BOUNDARY:
            return "延伸: 选择边界边 (点击选择, 右键结束)"
        return f"延伸: 选择要延伸的对象 (已选 {len(self._boundaries)} 条边界)"

    def on_mouse_move(self, world_x, world_y, modifiers):
        return False


# ============================================================
# 打断
# ============================================================
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


# ============================================================
# 打断于点
# ============================================================
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


# ============================================================
# 合并
# ============================================================
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

        all_pts = []
        for l in lines:
            all_pts.append((l.x1, l.y1))
            all_pts.append((l.x2, l.y2))

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
        if lines:
            poly.style = lines[0].style.clone() if hasattr(lines[0].style, 'clone') else lines[0].style
        self.board.add_element(poly)

        for l in lines:
            if l in self.board.elements:
                self.board.elements.remove(l)

        self._clear_selection()
        self.board.status_bar.showMessage(f"合并完成: {len(lines)} 条线段 -> 1 条多段线 ({len(ordered)} 个顶点)")
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


# ============================================================
# 倒斜角 - CAD标准双距离（v1.5 P0 流程修复）
# 流程: 先选中两条相交直线 → 点击倒斜角 → 输入距离 → 自动执行
# ============================================================
class ChamferCommand(BaseCommand):
    name = "倒斜角"
    shortcut = "CHA"
    description = "对两条相交直线倒斜角: 先框选/点选两条直线，再点击命令"
    is_modify_command = True

    def on_activate(self):
        """命令激活时立即检查选中状态并执行"""
        selected = self._get_selected_elements()
        lines = [e for e in selected if e.element_type.value == '直线']

        if len(lines) < 2:
            self.board.status_bar.showMessage(
                "倒斜角: 请先选中两条相交直线 (用选择模式框选或点选，再点击倒斜角)"
            )
            # 给提示后延迟返回选择模式
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(2000, self.board.set_default_command)
            return

        # 取前两条直线执行
        l1, l2 = lines[0], lines[1]

        # 弹窗输入两个距离
        dist1, dist2 = self._ask_distances()
        if dist1 is None:
            self.board.status_bar.showMessage("倒斜角: 已取消")
            self._clear_selection()
            self.board.set_default_command()
            return

        self._execute_chamfer(l1, l2, dist1, dist2)

    def _ask_distances(self):
        """弹出输入框获取两个距离，返回 (dist1, dist2) 或 (None, None)"""
        try:
            from PyQt5.QtWidgets import QInputDialog
            d1, ok1 = QInputDialog.getDouble(
                self.board, "倒斜角", "第一距离 (mm):", 10.0, 0.01, 9999.0, 2
            )
            if not ok1:
                return None, None
            d2, ok2 = QInputDialog.getDouble(
                self.board, "倒斜角", "第二距离 (mm):", d1, 0.01, 9999.0, 2
            )
            if not ok2:
                return None, None
            return d1, d2
        except Exception:
            return 10.0, 10.0

    def _execute_chamfer(self, l1, l2, dist1, dist2):
        """执行倒斜角核心计算"""
        inter = _line_intersection(
            l1.x1, l1.y1, l1.x2, l1.y2,
            l2.x1, l2.y1, l2.x2, l2.y2
        )
        if not inter:
            self.board.status_bar.showMessage("倒斜角: 两线平行或重合，无法倒斜角")
            self._clear_selection()
            self.board.set_default_command()
            return

        ix, iy = inter

        def trim_line_to_dist(line, cx, cy, dist):
            d1 = math.hypot(line.x1 - cx, line.y1 - cy)
            d2 = math.hypot(line.x2 - cx, line.y2 - cy)
            if d1 < d2:
                near_x, near_y, is_p1 = line.x1, line.y1, True
            else:
                near_x, near_y, is_p1 = line.x2, line.y2, False
            total_near = math.hypot(near_x - cx, near_y - cy)
            if total_near < 1e-12:
                return None
            ratio = min(1.0, dist / total_near)
            nx = cx + (near_x - cx) * ratio
            ny = cy + (near_y - cy) * ratio
            if is_p1:
                line.x1, line.y1 = nx, ny
            else:
                line.x2, line.y2 = nx, ny
            return (nx, ny)

        p1 = trim_line_to_dist(l1, ix, iy, dist1)
        p2 = trim_line_to_dist(l2, ix, iy, dist2)

        if p1 and p2:
            chamfer = LineElement(p1[0], p1[1], p2[0], p2[1])
            self.board.apply_current_layer_style(chamfer)
            self.board.add_element(chamfer)
            self.board.status_bar.showMessage(
                f"倒斜角完成: D1={dist1}mm, D2={dist2}mm"
            )
        else:
            self.board.status_bar.showMessage("倒斜角: 距离过大，无法完成")

        self._clear_selection()
        self.board.set_default_command()

    def get_prompt(self):
        return "倒斜角: 先选中两条相交直线，再点击此命令"

    def draw_preview(self, painter, coord_system):
        return False


# ============================================================
# 圆角 - CAD标准真正圆弧（v1.5 P0 流程修复）
# 流程: 先选中两条相交直线 → 点击圆角 → 输入半径 → 自动执行
# ============================================================
class FilletCommand(BaseCommand):
    name = "圆角"
    shortcut = "F"
    description = "对两条相交直线倒圆角: 先框选/点选两条直线，再点击命令"
    is_modify_command = True

    def on_activate(self):
        """命令激活时立即检查选中状态并执行"""
        selected = self._get_selected_elements()
        lines = [e for e in selected if e.element_type.value == '直线']

        if len(lines) < 2:
            self.board.status_bar.showMessage(
                "圆角: 请先选中两条相交直线 (用选择模式框选或点选，再点击圆角)"
            )
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(2000, self.board.set_default_command)
            return

        l1, l2 = lines[0], lines[1]

        # 弹窗输入半径
        radius = self._ask_radius()
        if radius is None:
            self.board.status_bar.showMessage("圆角: 已取消")
            self._clear_selection()
            self.board.set_default_command()
            return

        self._execute_fillet(l1, l2, radius)

    def _ask_radius(self):
        """弹出输入框获取半径，返回半径值或 None"""
        try:
            from PyQt5.QtWidgets import QInputDialog
            r, ok = QInputDialog.getDouble(
                self.board, "圆角", "圆角半径 (mm):", 10.0, 0.01, 9999.0, 2
            )
            if not ok:
                return None
            return r
        except Exception:
            return 10.0

    def _execute_fillet(self, l1, l2, radius):
        """执行圆角核心计算"""
        inter = _line_intersection(
            l1.x1, l1.y1, l1.x2, l1.y2,
            l2.x1, l2.y1, l2.x2, l2.y2
        )
        if not inter:
            self.board.status_bar.showMessage("圆角: 两线平行或重合，无法倒圆角")
            self._clear_selection()
            self.board.set_default_command()
            return

        ix, iy = inter
        r = radius
        if r <= 0:
            self.board.status_bar.showMessage("圆角: 半径必须大于0")
            self._clear_selection()
            self.board.set_default_command()
            return

        # 找到每条线上离交点最近的端点
        def _nearest_endpoint(line, cx, cy):
            d1 = math.hypot(line.x1 - cx, line.y1 - cy)
            d2 = math.hypot(line.x2 - cx, line.y2 - cy)
            if d1 < d2:
                return (line.x1, line.y1, True)
            return (line.x2, line.y2, False)

        ne1 = _nearest_endpoint(l1, ix, iy)
        ne2 = _nearest_endpoint(l2, ix, iy)

        def _direction(from_x, from_y, to_x, to_y):
            dx = to_x - from_x
            dy = to_y - from_y
            l = math.hypot(dx, dy)
            if l < 1e-12:
                return (0, 0)
            return (dx / l, dy / l)

        dir1 = _direction(ix, iy, ne1[0], ne1[1])
        dir2 = _direction(ix, iy, ne2[0], ne2[1])

        cos_angle = dir1[0] * dir2[0] + dir1[1] * dir2[1]
        cos_angle = max(-1.0, min(1.0, cos_angle))
        angle = math.acos(cos_angle)

        if angle < 1e-6 or abs(angle - math.pi) < 1e-6:
            self.board.status_bar.showMessage("圆角: 两线夹角太小或共线")
            self._clear_selection()
            self.board.set_default_command()
            return

        sin_half = math.sin(angle / 2)
        if abs(sin_half) < 1e-12:
            self.board.status_bar.showMessage("圆角: 计算错误")
            self._clear_selection()
            self.board.set_default_command()
            return

        d_center = r / sin_half
        bisector_x = dir1[0] + dir2[0]
        bisector_y = dir1[1] + dir2[1]
        bisector_len = math.hypot(bisector_x, bisector_y)
        if bisector_len < 1e-12:
            self.board.status_bar.showMessage("圆角: 计算错误")
            self._clear_selection()
            self.board.set_default_command()
            return

        bisector_x /= bisector_len
        bisector_y /= bisector_len
        cx = ix + bisector_x * d_center
        cy = iy + bisector_y * d_center

        def _tangent_point(center_x, center_y, rad, lx1, ly1, lx2, ly2):
            dx = lx2 - lx1
            dy = ly2 - ly1
            l2 = dx*dx + dy*dy
            if l2 < 1e-12:
                return None
            t = ((center_x - lx1) * dx + (center_y - ly1) * dy) / l2
            proj_x = lx1 + t * dx
            proj_y = ly1 + t * dy
            dcx = proj_x - center_x
            dcy = proj_y - center_y
            d = math.hypot(dcx, dcy)
            if d < 1e-12:
                return None
            scale = rad / d
            return (center_x + dcx * scale, center_y + dcy * scale)

        tp1 = _tangent_point(cx, cy, r, l1.x1, l1.y1, l1.x2, l1.y2)
        tp2 = _tangent_point(cx, cy, r, l2.x1, l2.y1, l2.x2, l2.y2)

        if not tp1 or not tp2:
            self.board.status_bar.showMessage("圆角: 无法计算切点")
            self._clear_selection()
            self.board.set_default_command()
            return

        # 计算圆弧的起始角和终止角
        sa = math.degrees(math.atan2(tp1[1] - cy, tp1[0] - cx))
        ea = math.degrees(math.atan2(tp2[1] - cy, tp2[0] - cx))

        # 修剪两条线到切点
        _trim_line_to_point(l1, tp1[0], tp1[1], keep_end='far')
        _trim_line_to_point(l2, tp2[0], tp2[1], keep_end='far')

        # 创建真正的圆弧
        arc = ArcElement(cx, cy, r, sa, ea)
        self.board.apply_current_layer_style(arc)
        self.board.add_element(arc)

        self.board.status_bar.showMessage(f"圆角完成: 半径 {r}mm")
        self._clear_selection()
        self.board.set_default_command()

    def get_prompt(self):
        return "圆角: 先选中两条相交直线，再点击此命令"

    def draw_preview(self, painter, coord_system):
        return False


# ============================================================
# 分解
# ============================================================
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
        elif et in ('多段线', '多边形', '样条曲线'):
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
        elif et == '圆弧':
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
                f"分解完成: {et} -> {len(new_elements)} 条线段")
        else:
            self.board.status_bar.showMessage("分解: 此对象不支持分解")
        self.cancel()
        self.board.set_default_command()

    def get_prompt(self):
        return "分解: 选择要分解的对象"

    def draw_preview(self, painter, coord_system):
        return False
