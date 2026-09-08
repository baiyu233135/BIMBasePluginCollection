# -*- coding: utf-8 -*-
"""
修改命令集 - 复制、移动、旋转、缩放（修复版，支持命令行参数）
"""
import math
from PyQt5.QtGui import QPen, QColor
from PyQt5.QtCore import Qt

from commands.base_command import BaseCommand, CommandState
from geometry.elements import BaseElement


class CopyCommand(BaseCommand):
    name = "复制"
    shortcut = "CO"
    description = "复制选中的元素"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._base_point = None
        self._target_point = None

    def on_activate(self):
        self._base_point = None
        self._target_point = None
        selected = self._get_selected_elements()
        if selected:
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("复制: 指定基点 (点击/坐标，右键取消)")
        else:
            self.board.status_bar.showMessage("复制: 点击选择要复制的对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            selected = self._get_selected_elements()
            if not selected and not self._base_point:
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    self._base_point = (world_x, world_y)
                    self.state = CommandState.WAITING_INPUT
                    self.board.status_bar.showMessage("复制: 指定目标点")
                self.board.viewport.update()
                return True
            elif self._base_point and not self._target_point:
                self._target_point = (world_x, world_y)
                dx = self._target_point[0] - self._base_point[0]
                dy = self._target_point[1] - self._base_point[1]
                count = 0
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
                self.board.status_bar.showMessage(f"复制完成: {count} 个元素")
                self.cancel()
                self.board.set_default_command()
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._base_point and not self._target_point:
            dx = world_x - self._base_point[0]
            dy = world_y - self._base_point[1]
            self._preview_offset = (dx, dy)
            self.board.status_bar.showMessage(f"复制偏移: dx={dx:.2f} dy={dy:.2f}")
            self.board.viewport.update()
            return True
        return False

    def on_cmd_confirm(self, text):
        text = text.strip()
        parsed = self._parse_coord(text)
        if parsed and not self._base_point:
            self._base_point = parsed
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("复制: 指定目标点")
            self.board.viewport.update()
            return True
        elif parsed and self._base_point:
            self._target_point = parsed
            dx = self._target_point[0] - self._base_point[0]
            dy = self._target_point[1] - self._base_point[1]
            selected = self._get_selected_elements()
            count = 0
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
            self.board.status_bar.showMessage(f"复制完成: {count} 个元素")
            self.cancel()
            self.board.set_default_command()
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
        if not selected and not self._base_point:
            return "复制: 选择对象"
        if not self._base_point:
            return "复制: 指定基点"
        return "复制: 指定目标点"

    def draw_preview(self, painter, coord_system):
        if self._base_point and hasattr(self, '_preview_offset'):
            selected = self._get_selected_elements()
            if selected:
                pen = QPen(QColor(128, 128, 128), 1, Qt.DashLine)
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


class MoveCommand(BaseCommand):
    name = "移动"
    shortcut = "M"
    description = "移动选中的元素"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._base_point = None

    def on_activate(self):
        self._base_point = None
        selected = self._get_selected_elements()
        if selected:
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("移动: 指定基点 (点击/坐标，右键取消)")
        else:
            self.board.status_bar.showMessage("移动: 点击选择要移动的对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            selected = self._get_selected_elements()
            if not selected and not self._base_point:
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    self._base_point = (world_x, world_y)
                    self.state = CommandState.WAITING_INPUT
                    self.board.status_bar.showMessage("移动: 指定目标点")
                self.board.viewport.update()
                return True
            elif self._base_point:
                dx = world_x - self._base_point[0]
                dy = world_y - self._base_point[1]
                for e in selected:
                    try:
                        e.translate(dx, dy)
                    except Exception:
                        pass
                self._clear_selection()
                self.board.status_bar.showMessage(f"移动完成: {len(selected)} 个元素")
                self.cancel()
                self.board.set_default_command()
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._base_point:
            dx = world_x - self._base_point[0]
            dy = world_y - self._base_point[1]
            self._preview_offset = (dx, dy)
            self.board.status_bar.showMessage(f"移动偏移: dx={dx:.2f} dy={dy:.2f}")
            self.board.viewport.update()
            return True
        return False

    def on_cmd_confirm(self, text):
        text = text.strip()
        parsed = self._parse_coord(text)
        if parsed and not self._base_point:
            self._base_point = parsed
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("移动: 指定目标点")
            self.board.viewport.update()
            return True
        elif parsed and self._base_point:
            dx = parsed[0] - self._base_point[0]
            dy = parsed[1] - self._base_point[1]
            selected = self._get_selected_elements()
            for e in selected:
                try:
                    e.translate(dx, dy)
                except Exception:
                    pass
            self._clear_selection()
            self.board.status_bar.showMessage(f"移动完成: {len(selected)} 个元素")
            self.cancel()
            self.board.set_default_command()
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
        if not selected and not self._base_point:
            return "移动: 选择对象"
        if not self._base_point:
            return "移动: 指定基点"
        return "移动: 指定目标点"

    def draw_preview(self, painter, coord_system):
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


class RotateCommand(BaseCommand):
    name = "旋转"
    shortcut = "RO"
    description = "旋转选中的元素"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._center = None
        self._angle = None

    def on_activate(self):
        self._center = None
        self._angle = None
        selected = self._get_selected_elements()
        if selected:
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("旋转: 指定旋转中心 (点击/坐标，右键取消)")
        else:
            self.board.status_bar.showMessage("旋转: 点击选择要旋转的对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            selected = self._get_selected_elements()
            if not selected and not self._center:
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    self._center = (world_x, world_y)
                    self.state = CommandState.WAITING_INPUT
                    self.board.status_bar.showMessage("旋转: 指定目标点确定角度 或 输入角度值")
                self.board.viewport.update()
                return True
            elif self._center and not self._angle:
                a = math.degrees(math.atan2(world_y - self._center[1], world_x - self._center[0]))
                self._angle = a
                self._execute_rotate(selected, a)
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_rotate(self, selected, angle):
        for e in selected:
            try:
                e.rotate(self._center[0], self._center[1], angle)
            except Exception:
                pass
        self._clear_selection()
        self.board.status_bar.showMessage(f"旋转完成: {len(selected)} 个元素, 角度 {angle:.1f}°")
        self.cancel()
        self.board.set_default_command()

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center and not self._angle:
            a = math.degrees(math.atan2(world_y - self._center[1], world_x - self._center[0]))
            self._preview_angle = a
            self.board.status_bar.showMessage(f"旋转角度: {a:.1f}°")
            self.board.viewport.update()
            return True
        return False

    def on_cmd_confirm(self, text):
        text = text.strip()
        parsed = self._parse_coord(text)
        if parsed and not self._center:
            self._center = parsed
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("旋转: 输入角度值(度)")
            self.board.viewport.update()
            return True
        try:
            a = float(text)
            selected = self._get_selected_elements()
            if selected and self._center:
                self._execute_rotate(selected, a)
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
        if not selected and not self._center:
            return "旋转: 选择对象"
        if not self._center:
            return "旋转: 指定中心"
        return "旋转: 指定目标点或输入角度"

    def draw_preview(self, painter, coord_system):
        if self._center and hasattr(self, '_preview_angle'):
            selected = self._get_selected_elements()
            if selected:
                pen = QPen(QColor(0, 200, 0), 1, Qt.DashLine)
                painter.setPen(pen)
                cx, cy = coord_system.world_to_screen(self._center[0], self._center[1])
                painter.setBrush(QColor(255, 0, 0))
                painter.drawEllipse(cx - 4, cy - 4, 8, 8)
                return True
        elif self._center:
            cx, cy = coord_system.world_to_screen(self._center[0], self._center[1])
            painter.setBrush(QColor(255, 0, 0))
            painter.drawEllipse(cx - 4, cy - 4, 8, 8)
        return False


class ScaleCommand(BaseCommand):
    name = "缩放"
    shortcut = "SC"
    description = "缩放选中的元素"
    is_modify_command = True

    def __init__(self, board):
        super().__init__(board)
        self._center = None
        self._factor = None

    def on_activate(self):
        self._center = None
        self._factor = None
        selected = self._get_selected_elements()
        if selected:
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("缩放: 指定缩放中心 (点击/坐标，右键取消)")
        else:
            self.board.status_bar.showMessage("缩放: 点击选择要缩放的对象 (右键取消)")

    def on_mouse_press(self, world_x, world_y, button, modifiers):
        if button == 1:
            selected = self._get_selected_elements()
            if not selected and not self._center:
                self._try_select_at(world_x, world_y)
                selected = self._get_selected_elements()
                if selected:
                    self._center = (world_x, world_y)
                    self.state = CommandState.WAITING_INPUT
                    self.board.status_bar.showMessage("缩放: 指定目标点确定比例 或 输入比例值")
                self.board.viewport.update()
                return True
            elif self._center and not self._factor:
                d = math.hypot(world_x - self._center[0], world_y - self._center[1])
                self._factor = d / 100.0 if d > 0 else 1.0
                self._execute_scale(selected, self._factor)
                return True
        elif button == 2:
            self.cancel()
            self.board.set_default_command()
            return True
        return False

    def _execute_scale(self, selected, factor):
        for e in selected:
            try:
                e.scale(self._center[0], self._center[1], factor)
            except Exception:
                pass
        self._clear_selection()
        self.board.status_bar.showMessage(f"缩放完成: 比例 {factor:.3f}x")
        self.cancel()
        self.board.set_default_command()

    def on_mouse_move(self, world_x, world_y, modifiers):
        if self._center and not self._factor:
            d = math.hypot(world_x - self._center[0], world_y - self._center[1])
            f = d / 100.0 if d > 0 else 1.0
            self._preview_factor = f
            self.board.status_bar.showMessage(f"缩放比例: {f:.3f}x")
            self.board.viewport.update()
            return True
        return False

    def on_cmd_confirm(self, text):
        text = text.strip()
        parsed = self._parse_coord(text)
        if parsed and not self._center:
            self._center = parsed
            self.state = CommandState.WAITING_INPUT
            self.board.status_bar.showMessage("缩放: 输入比例值")
            self.board.viewport.update()
            return True
        try:
            f = float(text)
            selected = self._get_selected_elements()
            if selected and self._center:
                self._execute_scale(selected, f)
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
        if not selected and not self._center:
            return "缩放: 选择对象"
        if not self._center:
            return "缩放: 指定中心"
        return "缩放: 指定目标点或输入比例"

    def draw_preview(self, painter, coord_system):
        if self._center:
            selected = self._get_selected_elements()
            if selected:
                pen = QPen(QColor(0, 200, 0), 1, Qt.DashLine)
                painter.setPen(pen)
                cx, cy = coord_system.world_to_screen(self._center[0], self._center[1])
                painter.setBrush(QColor(255, 0, 0))
                painter.drawEllipse(cx - 4, cy - 4, 8, 8)
                return True
        return False
