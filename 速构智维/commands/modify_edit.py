# -*- coding: utf-8 -*-
"""
修改命令集3 - v1.6
修剪、延伸、打断、合并、倒角、圆角、分解

v1.6 简化交互 (2026-09):
- ExtendCommand: 单步流程——点击直线(靠近要延伸的一端)即自动延伸到最近的其它元素交点
- ChamferCommand: 依次点击两条直线即执行，距离用命令行输入 ("20" 或 "20,30")，不再弹窗
- FilletCommand: 依次点击两条直线即执行(真正ArcElement圆弧+修剪两线)，半径用命令行输入，
  不再弹窗；修复 keep_end 方向错误导致整线被裁掉只剩端部的问题，圆弧保证走劣弧
- Trim/Break/Join/Explode 维持原有可用流程
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


def _side_direction(line, ix, iy, click_x, click_y):
    """直线点击侧的单位方向向量(从交点指向点击一侧，沿线方向)"""
    dx, dy = line.x2 - line.x1, line.y2 - line.y1
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return None
    ux, uy = dx / length, dy / length
    if (click_x - ix) * ux + (click_y - iy) * uy < 0:
        ux, uy = -ux, -uy
    return (ux, uy)


def _set_side_endpoint(line, ix, iy, dirx, diry, px, py):
    """把直线在 dir 反方向一侧(靠近角/交点)的端点移到 (px,py)；dir 为要保留的一侧方向"""
    side1 = (line.x1 - ix) * dirx + (line.y1 - iy) * diry
    side2 = (line.x2 - ix) * dirx + (line.y2 - iy) * diry
    if side1 <= side2:
        line.x1, line.y1 = px, py
    else:
        line.x2, line.y2 = px, py


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
# 延伸 - 简化单步流程（v1.6 修复）
# 点击要延伸的直线(靠近要延伸的一端) → 自动延伸到最近的其它元素交点
# ============================================================
class ExtendCommand(BaseCommand):
    name = "延伸"
    shortcut = "EX"
    description = "点击要延伸的直线，自动延伸到最近的其它元素交点"
    is_modify_command = True

    def on_activate(self):
        self.board.status_bar.showMessage(
            "延伸: 点击要延伸的直线(靠近要延伸的一端), 自动延伸到最近交点 (右键取消)"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            for elem in reversed(self.board.elements):
                if not getattr(elem, 'visible', True):
                    continue
                if self._hit_test(elem, world_x, world_y):
                    self._extend_element(elem, world_x, world_y)
                    self.board.viewport.update()
                    break
            return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _iter_boundary_segments(self, exclude):
        """收集除exclude外所有可见元素的线段作为候选边界"""
        for e in self.board.elements:
            if e is exclude or not getattr(e, 'visible', True):
                continue
            try:
                et = e.element_type.value
            except Exception:
                continue
            if et == '直线':
                yield (e.x1, e.y1, e.x2, e.y2)
            elif et in ('多段线', '多边形', '矩形', '样条曲线'):
                try:
                    for s, t in e.get_segments():
                        yield (s[0], s[1], t[0], t[1])
                except Exception:
                    continue

    def _extend_element(self, elem, wx, wy):
        """将直线被点击的一端延伸到最近的边界交点"""
        et = elem.element_type.value
        if et != '直线':
            self.board.status_bar.showMessage("延伸: 目前只支持直线延伸")
            return

        # 被点击的一端为延伸端
        d1 = math.hypot(wx - elem.x1, wy - elem.y1)
        d2 = math.hypot(wx - elem.x2, wy - elem.y2)
        if d1 <= d2:
            ox, oy = elem.x2, elem.y2   # 固定端
            ex, ey = elem.x1, elem.y1   # 延伸端
            extend_p1 = True
        else:
            ox, oy = elem.x1, elem.y1
            ex, ey = elem.x2, elem.y2
            extend_p1 = False

        dx, dy = ex - ox, ey - oy
        line_len = math.hypot(dx, dy)
        if line_len < 1e-12:
            return

        # 在所有边界线段上找"延伸方向上"的最近交点
        best = None
        best_u = float('inf')
        for bx1, by1, bx2, by2 in self._iter_boundary_segments(elem):
            inter = _line_intersection(ox, oy, ex, ey, bx1, by1, bx2, by2)
            if inter is None:
                continue
            ix, iy = inter
            # 交点必须在延伸端的前方(超出当前端点)
            u = ((ix - ox) * dx + (iy - oy) * dy) / (line_len * line_len)
            if u <= 1.0 + 1e-9:
                continue
            # 交点必须落在边界线段上(允许少量误差)
            sdx, sdy = bx2 - bx1, by2 - by1
            slen_sq = sdx * sdx + sdy * sdy
            if slen_sq < 1e-12:
                continue
            t = ((ix - bx1) * sdx + (iy - by1) * sdy) / slen_sq
            if t < -0.01 or t > 1.01:
                continue
            if u < best_u:
                best_u = u
                best = (ix, iy)

        if best:
            if extend_p1:
                elem.x1, elem.y1 = best
            else:
                elem.x2, elem.y2 = best
            ext = (best_u - 1.0) * line_len
            self.board.status_bar.showMessage(f"延伸完成: 延伸了 {ext:.2f}mm")
        else:
            self.board.status_bar.showMessage("延伸: 该方向上没有可延伸到的边界")

    def get_prompt(self):
        return "延伸: 点击要延伸的直线(靠近要延伸的一端)"

    def draw_preview(self, painter, coord_system):
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
# 倒斜角 - 简化流程（v1.6 修复）
# 流程: 点击第1条直线 → 点击第2条直线 → 自动执行
#       距离随时可在命令行输入 ("20" 或 "20,30")，默认10mm
# ============================================================
class ChamferCommand(BaseCommand):
    name = "倒斜角"
    shortcut = "CHA"
    description = "对两条相交直线倒斜角: 依次点击两条直线 (命令行可改距离)"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._dist1 = 10.0
        self._dist2 = 10.0
        self._lines = []
        self._clicks = []

    def on_activate(self):
        self._lines = []
        self._clicks = []
        self.board.status_bar.showMessage(
            f"倒斜角: 点击第1条直线 (距离 D1={self._dist1} D2={self._dist2}, "
            f"命令行输入如 20 或 20,30 修改, 右键取消)"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            for elem in reversed(self.board.elements):
                if not getattr(elem, 'visible', True):
                    continue
                if elem in self._lines:
                    continue
                if self._hit_test(elem, world_x, world_y):
                    if elem.element_type.value != '直线':
                        self.board.status_bar.showMessage("倒斜角: 只支持直线，请重新点击")
                        return True
                    self._lines.append(elem)
                    self._clicks.append((world_x, world_y))
                    if len(self._lines) == 1:
                        self.board.status_bar.showMessage("倒斜角: 点击第2条直线")
                    else:
                        self._execute_chamfer(self._lines[0], self._lines[1],
                                              self._dist1, self._dist2)
                        self._lines = []
                        self._clicks = []
                    self.board.viewport.update()
                    return True
            return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_cmd_confirm(self, text):
        text = text.strip().replace('，', ',')
        parts = text.split(',')
        try:
            if len(parts) == 1:
                d = float(parts[0])
                if d > 0:
                    self._dist1 = self._dist2 = d
                    self.board.status_bar.showMessage(f"倒斜角: 距离设为 {d}mm")
                    return True
            elif len(parts) == 2:
                d1, d2 = float(parts[0]), float(parts[1])
                if d1 > 0 and d2 > 0:
                    self._dist1, self._dist2 = d1, d2
                    self.board.status_bar.showMessage(
                        f"倒斜角: 距离设为 D1={d1} D2={d2}mm")
                    return True
        except ValueError:
            pass
        return False

    def _execute_chamfer(self, l1, l2, dist1, dist2):
        """执行倒斜角核心计算: 两线点击侧各从交点缩进 D1/D2, 直线连接"""
        inter = _line_intersection(
            l1.x1, l1.y1, l1.x2, l1.y2,
            l2.x1, l2.y1, l2.x2, l2.y2
        )
        if not inter:
            self.board.status_bar.showMessage("倒斜角: 两线平行或重合，无法倒斜角")
            return

        ix, iy = inter
        dir1 = _side_direction(l1, ix, iy, *self._clicks[0])
        dir2 = _side_direction(l2, ix, iy, *self._clicks[1])
        if not dir1 or not dir2:
            self.board.status_bar.showMessage("倒斜角: 无效直线")
            return

        # 点击侧端点缩进到距交点 D1/D2 处
        p1 = (ix + dir1[0] * dist1, iy + dir1[1] * dist1)
        p2 = (ix + dir2[0] * dist2, iy + dir2[1] * dist2)
        _set_side_endpoint(l1, ix, iy, dir1[0], dir1[1], p1[0], p1[1])
        _set_side_endpoint(l2, ix, iy, dir2[0], dir2[1], p2[0], p2[1])

        chamfer = LineElement(p1[0], p1[1], p2[0], p2[1])
        self.board.apply_current_layer_style(chamfer)
        self.board.add_element(chamfer)
        self.board.status_bar.showMessage(
            f"倒斜角完成: D1={dist1}mm, D2={dist2}mm (可继续点选下两条线, 右键退出)"
        )

    def get_prompt(self):
        if not self._lines:
            return f"倒斜角: 点击第1条直线 (D1={self._dist1} D2={self._dist2})"
        return "倒斜角: 点击第2条直线"

    def draw_preview(self, painter, coord_system):
        return False


# ============================================================
# 圆角 - 简化流程（v1.6 修复）
# 流程: 点击第1条直线 → 点击第2条直线 → 用ArcElement圆弧连接并修剪两线
#       半径随时可在命令行输入，默认10mm
# ============================================================
class FilletCommand(BaseCommand):
    name = "圆角"
    shortcut = "F"
    description = "对两条相交直线倒圆角: 依次点击两条直线 (命令行可改半径)"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._radius = 10.0
        self._lines = []
        self._clicks = []

    def on_activate(self):
        self._lines = []
        self._clicks = []
        self.board.status_bar.showMessage(
            f"圆角: 点击第1条直线 (半径 R={self._radius}mm, "
            f"命令行输入数字修改, 右键取消)"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            for elem in reversed(self.board.elements):
                if not getattr(elem, 'visible', True):
                    continue
                if elem in self._lines:
                    continue
                if self._hit_test(elem, world_x, world_y):
                    if elem.element_type.value != '直线':
                        self.board.status_bar.showMessage("圆角: 只支持直线，请重新点击")
                        return True
                    self._lines.append(elem)
                    self._clicks.append((world_x, world_y))
                    if len(self._lines) == 1:
                        self.board.status_bar.showMessage("圆角: 点击第2条直线")
                    else:
                        self._execute_fillet(self._lines[0], self._lines[1],
                                             self._radius)
                        self._lines = []
                        self._clicks = []
                    self.board.viewport.update()
                    return True
            return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_cmd_confirm(self, text):
        try:
            r = float(text.strip())
            if r > 0:
                self._radius = r
                self.board.status_bar.showMessage(f"圆角: 半径设为 {r}mm")
                return True
        except ValueError:
            pass
        return False

    def _execute_fillet(self, l1, l2, radius):
        """执行圆角核心计算: 在两线点击侧之间生成切弧并修剪两线"""
        inter = _line_intersection(
            l1.x1, l1.y1, l1.x2, l1.y2,
            l2.x1, l2.y1, l2.x2, l2.y2
        )
        if not inter:
            self.board.status_bar.showMessage("圆角: 两线平行或重合，无法倒圆角")
            return

        ix, iy = inter
        r = radius
        if r <= 0:
            self.board.status_bar.showMessage("圆角: 半径必须大于0")
            return

        dir1 = _side_direction(l1, ix, iy, *self._clicks[0])
        dir2 = _side_direction(l2, ix, iy, *self._clicks[1])
        if not dir1 or not dir2:
            self.board.status_bar.showMessage("圆角: 无效直线")
            return

        cos_angle = dir1[0] * dir2[0] + dir1[1] * dir2[1]
        cos_angle = max(-1.0, min(1.0, cos_angle))
        angle = math.acos(cos_angle)

        if angle < 1e-6 or abs(angle - math.pi) < 1e-6:
            self.board.status_bar.showMessage("圆角: 两线夹角太小或共线")
            return

        # 圆心在角平分线上, 距交点 r/sin(半角); 切点距交点 r/tan(半角)
        sin_half = math.sin(angle / 2)
        tan_half = math.tan(angle / 2)
        if abs(sin_half) < 1e-12 or abs(tan_half) < 1e-12:
            self.board.status_bar.showMessage("圆角: 计算错误")
            return
        d_center = r / sin_half
        t_dist = r / tan_half

        bisector_x = dir1[0] + dir2[0]
        bisector_y = dir1[1] + dir2[1]
        bisector_len = math.hypot(bisector_x, bisector_y)
        if bisector_len < 1e-12:
            self.board.status_bar.showMessage("圆角: 计算错误")
            return
        bisector_x /= bisector_len
        bisector_y /= bisector_len
        cx = ix + bisector_x * d_center
        cy = iy + bisector_y * d_center

        tp1 = (ix + dir1[0] * t_dist, iy + dir1[1] * t_dist)
        tp2 = (ix + dir2[0] * t_dist, iy + dir2[1] * t_dist)

        # 计算圆弧的起始角和终止角，保证走劣弧(夹角<180°)
        sa = math.degrees(math.atan2(tp1[1] - cy, tp1[0] - cx))
        ea = math.degrees(math.atan2(tp2[1] - cy, tp2[0] - cx))
        if (ea - sa) % 360 > 180:
            sa, ea = ea, sa

        # 修剪两条线的点击侧端点到切点
        _set_side_endpoint(l1, ix, iy, dir1[0], dir1[1], tp1[0], tp1[1])
        _set_side_endpoint(l2, ix, iy, dir2[0], dir2[1], tp2[0], tp2[1])

        # 创建真正的圆弧
        arc = ArcElement(cx, cy, r, sa, ea)
        self.board.apply_current_layer_style(arc)
        self.board.add_element(arc)

        self.board.status_bar.showMessage(
            f"圆角完成: 半径 {r}mm (可继续点选下两条线, 右键退出)")

    def get_prompt(self):
        if not self._lines:
            return f"圆角: 点击第1条直线 (R={self._radius}mm)"
        return "圆角: 点击第2条直线"

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
