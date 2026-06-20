# -*- coding: utf-8 -*-
"""
命令基类 - 所有绘图和修改命令的抽象接口

扩展:
- 支持选择模式（修改命令需要先选择目标元素）
- 支持框选/点选
- 支持预览高亮
- 所有事件方法自动异常捕获，防止闪退
"""

import math
import traceback
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Tuple, List


def _log_error(cmd_name, method, exc):
    """记录命令错误到日志文件"""
    try:
        import os
        from datetime import datetime
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "CADBoard_error.log")
        log_path = os.path.normpath(log_path)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [CMD:{cmd_name}.{method}] {exc}\n")
            f.write(traceback.format_exc() + "\n")
    except Exception:
        pass


class CommandState(Enum):
    """命令状态"""
    IDLE = "空闲"
    ACTIVE = "激活"
    WAITING_INPUT = "等待输入"
    WAITING_SELECTION = "等待选择"
    FINISHED = "完成"
    CANCELLED = "取消"


class BaseCommand(ABC):
    """绘图/修改命令基类"""

    name = "基础命令"
    shortcut = ""
    icon = ""
    description = ""
    is_modify_command = False

    def __init__(self, board):
        self.board = board
        self.state = CommandState.IDLE
        self._points: List[Tuple[float, float]] = []
        self._selected_elements: List = []

    def activate(self):
        self.state = CommandState.ACTIVE
        self._points = []
        self._selected_elements = []
        try:
            self.on_activate()
        except Exception as e:
            _log_error(self.name, "on_activate", e)
            self.board.status_bar.showMessage(f"{self.name} 激活失败: {e}")

    def deactivate(self):
        self.state = CommandState.IDLE
        self._points = []
        self._selected_elements = []
        try:
            self.on_deactivate()
        except Exception as e:
            _log_error(self.name, "on_deactivate", e)
        # 只有非修改命令切换时才清除选择（修改命令保留选择以便操作）
        if not self.is_modify_command:
            for e in self.board.elements:
                e.selected = False

    def finish(self):
        self.state = CommandState.FINISHED
        try:
            self.on_finish()
        except Exception as e:
            _log_error(self.name, "on_finish", e)

    def cancel(self):
        self.state = CommandState.CANCELLED
        self._points = []
        self._selected_elements = []
        try:
            self.on_cancel()
        except Exception as e:
            _log_error(self.name, "on_cancel", e)
        for e in self.board.elements:
            e.selected = False

    # ---------- 子类可重写 ----------

    def on_activate(self):
        if self.is_modify_command:
            self.state = CommandState.WAITING_SELECTION
            selected = self._get_selected_elements()
            if selected:
                self.board.status_bar.showMessage(
                    f"{self.name}: 已选中 {len(selected)} 个对象，左键确认操作，右键取消"
                )
            else:
                self.board.status_bar.showMessage(
                    f"{self.name}: 请选择对象 (点击选择，框选拖拽，右键确认，ESC取消)"
                )
        else:
            self.board.status_bar.showMessage(self.get_prompt())

    def on_deactivate(self):
        pass

    def on_finish(self):
        pass

    def on_cancel(self):
        pass

    def on_mouse_press(self, world_x: float, world_y: float,
                       button: int, modifiers: int) -> bool:
        return False

    def on_mouse_move(self, world_x: float, world_y: float,
                      modifiers: int) -> bool:
        return False

    def on_mouse_release(self, world_x: float, world_y: float,
                         button: int, modifiers: int) -> bool:
        return False

    def on_key_press(self, key: str, modifiers: int) -> bool:
        if key in ('Escape', 'Esc'):
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    @abstractmethod
    def get_prompt(self) -> str:
        pass

    @abstractmethod
    def draw_preview(self, painter, coord_system) -> bool:
        pass

    # ---------- 选择辅助 ----------

    def _try_select_at(self, wx: float, wy: float, multi: bool = False):
        """在坐标处尝试点选元素 —— 面编辑模式下只选面元素"""
        hit = None
        for elem in reversed(self.board.elements):
            if not getattr(elem, 'visible', True):
                continue
            if not self.board.layer_manager.is_visible(elem.style.layer_name):
                continue
            # Phase 3 Enhancement: 面编辑模式下只考虑面元素
            if getattr(self.board, '_face_edit_mode', False):
                if not getattr(elem, 'face_info', {}):
                    continue
                face_cid = self.board._face_component_id
                if face_cid and elem.face_info.get('component_id') != face_cid:
                    continue
                face_filter = self.board._face_filter
                if face_filter != 'all':
                    if elem.face_info.get('face_name', '') != face_filter:
                        continue
            try:
                if self._hit_test(elem, wx, wy):
                    hit = elem
                    break
            except Exception:
                continue

        if hit:
            if not multi:
                for e in self.board.elements:
                    e.selected = False
            hit.selected = True
            if hit not in self._selected_elements:
                self._selected_elements.append(hit)
            return True
        return False

    def _hit_test(self, elem, wx: float, wy: float) -> bool:
        """点选碰撞检测（默认15mm容差，可动态调整）"""
        # 根据当前缩放比例动态调整容差（小缩放=大容差，大缩放=精确）
        try:
            scale = self.board.coord_system.get_scale()
            tol = max(15.0, 10.0 / max(scale, 0.01))  # 最小15mm，缩放小时增大
        except Exception:
            tol = 15.0
        try:
            et = elem.element_type.value
        except Exception as e:
            _log_error(self.name, "_hit_test:element_type", e)
            return False

        if et == '直线':
            d = self._point_to_segment_dist(wx, wy, elem.x1, elem.y1, elem.x2, elem.y2)
            return d < tol
        elif et == '矩形':
            return (elem.x - tol <= wx <= elem.x + elem.width + tol and
                    elem.y - tol <= wy <= elem.y + elem.height + tol)
        elif et == '圆':
            d = math.hypot(wx - elem.cx, wy - elem.cy)
            return abs(d - elem.radius) < tol or d < elem.radius
        elif et == '圆弧':
            d = math.hypot(wx - elem.cx, wy - elem.cy)
            if abs(d - elem.radius) > tol:
                return False
            a = math.degrees(math.atan2(wy - elem.cy, wx - elem.cx))
            sa, ea = elem.start_angle, elem.end_angle
            if ea < sa:
                ea += 360
            while a < sa:
                a += 360
            return sa <= a <= ea
        elif et in ('多段线', '多边形'):
            segs = elem.get_segments()
            for s, e in segs:
                if self._point_to_segment_dist(wx, wy, s[0], s[1], e[0], e[1]) < tol:
                    return True
            return False
        elif et == '椭圆':
            pts = elem.sample_points(36)
            for i in range(len(pts) - 1):
                if self._point_to_segment_dist(wx, wy, pts[i][0], pts[i][1],
                                              pts[i+1][0], pts[i+1][1]) < tol:
                    return True
            return False
        elif et == '点':
            return math.hypot(wx - elem.x, wy - elem.y) < tol
        return False

    def _point_to_segment_dist(self, px, py, x1, y1, x2, y2) -> float:
        """点到线段的距离"""
        dx, dy = x2 - x1, y2 - y1
        len_sq = dx*dx + dy*dy
        if len_sq < 1e-12:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1)*dx + (py - y1)*dy) / len_sq))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    def _get_selected_elements(self) -> List:
        """获取当前选中的元素列表（从board.elements中读取selected状态）"""
        return [e for e in self.board.elements if getattr(e, 'selected', False)]

    def _clear_selection(self):
        """清除所有选择"""
        for e in self.board.elements:
            e.selected = False
        self._selected_elements = []

    # ---------- 辅助方法 ----------

    def add_point(self, x: float, y: float):
        self._points.append((x, y))

    def get_last_point(self) -> Optional[Tuple[float, float]]:
        if self._points:
            return self._points[-1]
        return None

    def clear_points(self):
        self._points = []

    def point_count(self) -> int:
        return len(self._points)


class SelectCommand(BaseCommand):
    """默认选择命令 - 用于浏览和框选"""

    name = "选择"
    shortcut = ""
    description = "选择和浏览模式"

    def __init__(self, board):
        super().__init__(board)
        self._drag_start = None
        self._drag_end = None

    def on_activate(self):
        self.board.status_bar.showMessage(
            "选择模式: 点击选择，拖拽框选，Ctrl+点击多选，滚轮缩放，中键平移"
        )

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            self._drag_start = (world_x, world_y)
            self._drag_end = (world_x, world_y)
            multi = (modifiers & 2) != 0
            self._try_select_at(world_x, world_y, multi)
            self.board.viewport.update()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._drag_start:
            self._drag_end = (world_x, world_y)
            self.board.viewport.update()
            return True
        return False

    def on_mouse_release(self, world_x, world_y, button, modifiers):
        if button == 1 and self._drag_start:
            if self._drag_end:
                dx = abs(self._drag_end[0] - self._drag_start[0])
                dy = abs(self._drag_end[1] - self._drag_start[1])
                if dx > 5 or dy > 5:
                    self._box_select(self._drag_start, self._drag_end)
            self._drag_start = None
            self._drag_end = None
            self.board.viewport.update()
            return True
        return False

    def _box_select(self, p1, p2):
        """框选 —— 面编辑模式下只框选面元素"""
        x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1])
        x2, y2 = max(p1[0], p2[0]), max(p1[1], p2[1])
        for e in self.board.elements:
            if not getattr(e, 'visible', True):
                continue
            if not self.board.layer_manager.is_visible(e.style.layer_name):
                continue
            # Phase 3 Enhancement: 面编辑模式下只考虑面元素
            if getattr(self.board, '_face_edit_mode', False):
                if not getattr(e, 'face_info', {}):
                    continue
                face_cid = self.board._face_component_id
                if face_cid and e.face_info.get('component_id') != face_cid:
                    continue
                face_filter = self.board._face_filter
                if face_filter != 'all':
                    if e.face_info.get('face_name', '') != face_filter:
                        continue
            b = e.get_bounds()
            if b[0] <= x2 and b[2] >= x1 and b[1] <= y2 and b[3] >= y1:
                e.selected = True

    def get_prompt(self):
        return "就绪"

    def draw_preview(self, painter, coord_system):
        if self._drag_start and self._drag_end:
            from PyQt5.QtGui import QPen, QColor
            from PyQt5.QtCore import Qt
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
