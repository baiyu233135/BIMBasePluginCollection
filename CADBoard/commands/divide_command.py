# -*- coding: utf-8 -*-
"""定数等分/定距等分命令 - DIV / ME（支持命令行输入参数）"""
import math
from PyQt5.QtGui import QPen, QColor

from commands.base_command import BaseCommand, CommandState
from geometry.elements import PointElement


class DivideCommand(BaseCommand):
    name = "定数等分"
    shortcut = "DIV"
    description = "将线段/圆弧等分为指定数量的段"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._num_segments = 5
        self._target_elem = None

    def on_activate(self):
        self._target_elem = None
        self.board.status_bar.showMessage(
            f"定数等分: 点击选择对象，分成 {self._num_segments} 段 (右键取消)"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._target_elem is None:
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if self._hit_test(elem, world_x, world_y):
                        self._target_elem = elem
                        self._execute_divide()
                        self.board.viewport.update()
                        break
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_divide(self):
        elem = self._target_elem
        if not elem:
            return
        pts = self._get_divide_points(elem, self._num_segments)
        for p in pts:
            pt = PointElement(p[0], p[1])
            self.board.apply_current_layer_style(pt)
            self.board.add_element(pt)
        self.board.status_bar.showMessage(
            f"定数等分完成: 在 {elem.element_type.value} 上放置 {len(pts)} 个点"
        )
        self.cancel()
        self.board.set_default_command()

    def _get_divide_points(self, elem, num):
        et = elem.element_type.value
        pts = []
        if et == '直线':
            for i in range(1, num):
                t = i / num
                pts.append((elem.x1 + (elem.x2 - elem.x1) * t,
                           elem.y1 + (elem.y2 - elem.y1) * t))
        elif et == '圆弧':
            sa = math.radians(elem.start_angle)
            ea = math.radians(elem.end_angle)
            if ea <= sa:
                ea += 2 * math.pi
            for i in range(1, num):
                t = i / num
                a = sa + (ea - sa) * t
                pts.append((elem.cx + elem.radius * math.cos(a),
                           elem.cy + elem.radius * math.sin(a)))
        elif et == '圆':
            for i in range(num):
                a = 2 * math.pi * i / num
                pts.append((elem.cx + elem.radius * math.cos(a),
                           elem.cy + elem.radius * math.sin(a)))
        elif et in ('多段线', '多边形'):
            segs = elem.get_segments()
            total_len = sum(math.hypot(e[0]-s[0], e[1]-s[1]) for s, e in segs)
            if total_len < 1e-6:
                return pts
            target_len = total_len / num
            curr_len = 0
            seg_idx = 0
            seg_pos = 0
            for i in range(1, num):
                need = i * target_len
                while curr_len < need and seg_idx < len(segs):
                    s, e = segs[seg_idx]
                    sl = math.hypot(e[0]-s[0], e[1]-s[1])
                    if curr_len + sl >= need:
                        t = (need - curr_len) / sl if sl > 0 else 0
                        pts.append((s[0] + (e[0]-s[0]) * t, s[1] + (e[1]-s[1]) * t))
                        break
                    curr_len += sl
                    seg_idx += 1
        return pts

    def on_cmd_confirm(self, text):
        try:
            n = int(text.strip())
            if n >= 2:
                self._num_segments = n
                self.board.status_bar.showMessage(f"定数等分: 段数设为 {n}")
                return True
        except ValueError:
            pass
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        return False

    def get_prompt(self):
        return f"定数等分: 选择对象分成 {self._num_segments} 段"

    def draw_preview(self, painter, coord_system):
        return False


class MeasureCommand(BaseCommand):
    name = "定距等分"
    shortcut = "ME"
    description = "按指定距离在对象上放置点"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._distance = 100.0
        self._target_elem = None

    def on_activate(self):
        self._target_elem = None
        self.board.status_bar.showMessage(
            f"定距等分: 点击选择对象，间距 {self._distance}mm (右键取消)"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            if self._target_elem is None:
                for elem in reversed(self.board.elements):
                    if not getattr(elem, 'visible', True):
                        continue
                    if self._hit_test(elem, world_x, world_y):
                        self._target_elem = elem
                        self._execute_measure()
                        self.board.viewport.update()
                        break
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_measure(self):
        elem = self._target_elem
        if not elem:
            return
        pts = self._get_measure_points(elem, self._distance)
        for p in pts:
            pt = PointElement(p[0], p[1])
            self.board.apply_current_layer_style(pt)
            self.board.add_element(pt)
        self.board.status_bar.showMessage(
            f"定距等分完成: 放置 {len(pts)} 个点，间距 {self._distance}mm"
        )
        self.cancel()
        self.board.set_default_command()

    def _get_measure_points(self, elem, dist):
        et = elem.element_type.value
        pts = []
        if et == '直线':
            l = math.hypot(elem.x2 - elem.x1, elem.y2 - elem.y1)
            if l < 1e-6:
                return pts
            num = int(l / dist)
            for i in range(1, num + 1):
                t = (i * dist) / l
                if t > 1:
                    break
                pts.append((elem.x1 + (elem.x2 - elem.x1) * t,
                           elem.y1 + (elem.y2 - elem.y1) * t))
        elif et == '圆弧':
            sa = math.radians(elem.start_angle)
            ea = math.radians(elem.end_angle)
            if ea <= sa:
                ea += 2 * math.pi
            arc_len = elem.radius * (ea - sa)
            num = int(arc_len / dist)
            for i in range(1, num + 1):
                t = (i * dist) / arc_len
                if t > 1:
                    break
                a = sa + (ea - sa) * t
                pts.append((elem.cx + elem.radius * math.cos(a),
                           elem.cy + elem.radius * math.sin(a)))
        elif et == '圆':
            circumference = 2 * math.pi * elem.radius
            num = int(circumference / dist)
            for i in range(num):
                a = 2 * math.pi * i / num
                pts.append((elem.cx + elem.radius * math.cos(a),
                           elem.cy + elem.radius * math.sin(a)))
        elif et in ('多段线', '多边形'):
            segs = elem.get_segments()
            total_len = sum(math.hypot(e[0]-s[0], e[1]-s[1]) for s, e in segs)
            num = int(total_len / dist)
            curr_len = 0
            seg_idx = 0
            for i in range(1, num + 1):
                need = i * dist
                while curr_len < need and seg_idx < len(segs):
                    s, e = segs[seg_idx]
                    sl = math.hypot(e[0]-s[0], e[1]-s[1])
                    if curr_len + sl >= need:
                        t = (need - curr_len) / sl if sl > 0 else 0
                        pts.append((s[0] + (e[0]-s[0]) * t, s[1] + (e[1]-s[1]) * t))
                        break
                    curr_len += sl
                    seg_idx += 1
        return pts

    def on_cmd_confirm(self, text):
        try:
            d = float(text.strip())
            if d > 0:
                self._distance = d
                self.board.status_bar.showMessage(f"定距等分: 间距设为 {d}mm")
                return True
        except ValueError:
            pass
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        return False

    def get_prompt(self):
        return f"定距等分: 选择对象，间距 {self._distance}mm"

    def draw_preview(self, painter, coord_system):
        return False
