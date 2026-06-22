# -*- coding: utf-8 -*-
"""
CAD画板主窗口 - v1.5 P0 (基于原始代码最小修改)

修改内容 (2026-04-27):
1. _show_snap_settings: 增加异常保护，防止BIMBase内嵌环境闪退
2. _undo/_redo: 改为完整历史栈（50步），替代简单的pop
3. 与新modify_advanced.py/modify_edit.py命令配合（类名和接口保持一致）
4. 元素增加to_dict/from_dict序列化支持（用于JSON保存/加载）
5. 增加Redo按钮
6. 工具栏快捷键增加点(PO)命令

原始代码架构保持不变:
- CADBoardWindow(QMainWindow)
- CanvasWidget(QWidget)
- QToolBar左侧工具栏 + QStatusBar底部状态栏
- 命令注册系统 + 快捷键映射
"""

import sys
import os
import math
import json
import traceback
from typing import List, Optional, Dict, Type

try:
    from PyQt5.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QToolBar, QPushButton, QLabel, QStatusBar,
        QFileDialog, QMessageBox, QAction, QApplication,
        QFrame, QSizePolicy, QDialog, QTextEdit,
        QProgressBar, QDialogButtonBox, QMenu, QInputDialog,
        QListWidget, QListWidgetItem, QColorDialog, QLineEdit,
        QDoubleSpinBox, QSpinBox, QFormLayout, QCheckBox, QComboBox, QComboBox
    )
    from PyQt5.QtGui import (
        QPainter, QPen, QColor, QBrush, QFont,
        QIcon, QCursor, QKeyEvent, QMouseEvent,
        QWheelEvent, QPaintEvent, QResizeEvent
    )
    from PyQt5.QtCore import Qt, QPoint, QSize, QRect
except ImportError:
    try:
        from PyQt6.QtWidgets import (
            QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QToolBar, QPushButton, QLabel, QStatusBar,
            QFileDialog, QMessageBox, QApplication, QFrame,
            QSizePolicy, QDialog, QTextEdit, QProgressBar,
            QDialogButtonBox, QMenu, QInputDialog, QListWidget,
            QListWidgetItem, QColorDialog, QLineEdit,
            QDoubleSpinBox, QSpinBox, QFormLayout, QCheckBox, QComboBox
        )
        from PyQt6.QtGui import (
            QPainter, QPen, QColor, QBrush, QFont,
            QIcon, QCursor, QKeyEvent, QMouseEvent,
            QWheelEvent, QPaintEvent, QResizeEvent, QAction
        )
        from PyQt6.QtCore import Qt, QPoint, QSize, QRect
    except ImportError:
        raise ImportError("请安装PyQt5: pip install PyQt5")

from utils.coord import CoordinateSystem
from utils.env_config import run_environment_configuration
from utils.layer_manager import LayerManager
from utils.snap import SnapSystem
from utils.dwg_handler import import_dwg, convert_dxf_to_dwg
from utils.pdf_handler import import_pdf
from utils.pdf_view_recognizer import auto_associate_from_pdf_views
from utils.drawing_recognizer import recognize_drawing_file, has_api_key, load_config
from drawing_ai_config_dialog import DrawingAIConfigDialog
from geometry.elements import BaseElement, LineElement, RectangleElement
from geometry.elements import CircleElement, ArcElement, PolylineElement
from geometry.elements import EllipseElement, PointElement
from commands.base_command import BaseCommand, SelectCommand
from commands.line_command import LineCommand
from commands.circle_command import CircleCommand
from commands.arc_command import ArcCommand
from commands.rectangle_command import RectangleCommand
from commands.polyline_command import PolylineCommand
from commands.polygon_command import PolygonCommand
from commands.ellipse_command import EllipseCommand
from commands.point_command import PointCommand
from commands.spline_command import SplineCommand
from commands.divide_command import DivideCommand, MeasureCommand
from commands.delete_command import DeleteCommand
from commands.modify_transform import CopyCommand, MoveCommand, RotateCommand, ScaleCommand
from commands.modify_advanced import MirrorCommand, OffsetCommand, ArrayCommand, StretchCommand
from commands.modify_edit import (
    TrimCommand, ExtendCommand, BreakCommand, BreakAtPointCommand,
    JoinCommand, ChamferCommand, FilletCommand, ExplodeCommand
)
from commands.solid_commands import (
    ExtrudeCommand, BoxCommand, SphereCommand, ConeCommand,
    TorusCommand, PyramidCommand, TriangularPrismCommand
)
import bimbase_sync

# 3D预览窗口导入
try:
    from preview_3d import Preview3DWindow
except ImportError:
    Preview3DWindow = None
from utils.ai_panel import AIPanel
from utils.face_mapper import ComponentFaceGroup
from geometry.faces import FaceManager
from utils.component_registry import infer_component_params_from_element, get_registry


def _write_board_log(msg):
    try:
        import os
        from datetime import datetime
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CADBoard_error.log")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [BOARD] {msg}\n")
    except Exception:
        pass


class CanvasWidget(QWidget):
    """画布控件 - 自定义绘制区域（所有事件处理加异常捕获）"""

    def __init__(self, board, parent=None):
        super().__init__(parent)
        self.board = board
        self.coord_system = board.coord_system
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.bg_color = QColor(30, 30, 30)
        self.grid_color = QColor(60, 60, 60)
        self.axis_color_x = QColor(180, 50, 50)
        self.axis_color_y = QColor(50, 180, 50)
        self.border_color = QColor(100, 100, 100)
        # 网格显示控制
        self.show_grid = True
        self.grid_major_color = QColor(80, 80, 80)   # 主网格线颜色（较亮）
        self.grid_minor_color = QColor(45, 45, 45)   # 次网格线颜色（较暗）

    def paintEvent(self, event: QPaintEvent):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.fillRect(self.rect(), self.bg_color)
            self._draw_grid(painter)
            self._draw_axes(painter)
            self._draw_canvas_border(painter)
            self._draw_elements(painter)
            if self.board.current_command:
                try:
                    self.board.current_command.draw_preview(painter, self.coord_system)
                except Exception as e:
                    _write_board_log(f"draw_preview error: {e}")
            if self.board._mouse_screen_pos:
                self._draw_crosshair(painter)
            snap_info = self.board.snap_system.get_snap_info()
            if snap_info:
                self._draw_snap_marker(painter, snap_info[0], snap_info[1])
        except Exception as e:
            _write_board_log(f"paintEvent error: {traceback.format_exc()}")

    def _draw_grid(self, painter: QPainter):
        if not self.show_grid:
            return
        cw = self.coord_system.canvas_width
        ch = self.coord_system.canvas_height
        scale = self.coord_system.get_scale()
        
        # 根据缩放级别确定主次网格间距
        if scale > 5:
            minor_spacing = 10
            major_spacing = 50
        elif scale > 2:
            minor_spacing = 10
            major_spacing = 50
        elif scale > 0.5:
            minor_spacing = 10
            major_spacing = 100
        else:
            minor_spacing = 50
            major_spacing = 200
        
        # 先画次网格线（细、暗）
        pen_minor = QPen(self.grid_minor_color, 1)
        painter.setPen(pen_minor)
        x = 0
        while x <= cw:
            sx, _ = self.coord_system.world_to_screen(x, 0)
            painter.drawLine(sx, 0, sx, self.height())
            x += minor_spacing
        y = 0
        while y <= ch:
            _, sy = self.coord_system.world_to_screen(0, y)
            painter.drawLine(0, sy, self.width(), sy)
            y += minor_spacing
        
        # 再画主网格线（粗、亮）
        pen_major = QPen(self.grid_major_color, 1)
        painter.setPen(pen_major)
        x = 0
        while x <= cw:
            sx, _ = self.coord_system.world_to_screen(x, 0)
            painter.drawLine(sx, 0, sx, self.height())
            x += major_spacing
        y = 0
        while y <= ch:
            _, sy = self.coord_system.world_to_screen(0, y)
            painter.drawLine(0, sy, self.width(), sy)
            y += major_spacing

    def _draw_axes(self, painter: QPainter):
        origin_x, origin_y = self.coord_system.world_to_screen(0, 0)
        pen_x = QPen(self.axis_color_x, 2)
        painter.setPen(pen_x)
        end_x, end_y = self.coord_system.world_to_screen(self.coord_system.canvas_width * 0.15, 0)
        painter.drawLine(origin_x, origin_y, end_x, end_y)
        painter.drawText(end_x + 5, end_y + 4, "X")
        pen_y = QPen(self.axis_color_y, 2)
        painter.setPen(pen_y)
        end_x, end_y = self.coord_system.world_to_screen(0, self.coord_system.canvas_height * 0.15)
        painter.drawLine(origin_x, origin_y, end_x, end_y)
        painter.drawText(end_x - 4, end_y - 8, "Y")
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawText(origin_x - 20, origin_y + 15, "O")

    def _draw_canvas_border(self, painter: QPainter):
        rect = self.coord_system.get_canvas_rect_screen()
        pen = QPen(self.border_color, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(*rect)

    def _draw_elements(self, painter: QPainter):
        # Phase 3 Enhancement: 面编辑模式下只绘制当前组件的面元素
        face_filter = self.board._face_filter
        face_cid = self.board._face_component_id
        is_face_edit = getattr(self.board, '_face_edit_mode', False)
        
        # v1.5 P3: 计算屏幕可见区域的世界坐标范围，用于裁剪
        vw = self.width()
        vh = self.height()
        try:
            v_x1, v_y1 = self.coord_system.screen_to_world(0, 0)
            v_x2, v_y2 = self.coord_system.screen_to_world(vw, vh)
            vis_min_x, vis_max_x = min(v_x1, v_x2), max(v_x1, v_x2)
            vis_min_y, vis_max_y = min(v_y1, v_y2), max(v_y1, v_y2)
            # 扩大一点边界，避免边缘元素被裁剪
            margin_w = (vis_max_x - vis_min_x) * 0.05
            margin_h = (vis_max_y - vis_min_y) * 0.05
            vis_min_x -= margin_w
            vis_max_x += margin_w
            vis_min_y -= margin_h
            vis_max_y += margin_h
        except Exception:
            vis_min_x = vis_max_x = vis_min_y = vis_max_y = None
        
        def _is_visible_region(elem):
            """检查元素包围盒是否与可见区域重叠"""
            if vis_min_x is None:
                return True
            try:
                b = elem.get_bounds()
                # 完全在区域外才跳过
                if b[2] < vis_min_x or b[0] > vis_max_x:
                    return False
                if b[3] < vis_min_y or b[1] > vis_max_y:
                    return False
                return True
            except Exception:
                return True
        
        # 先收集需要绘制的元素
        elements_to_draw = []
        face_elements = []
        for element in self.board.elements:
            if not getattr(element, 'visible', True):
                continue
            if not self.board.layer_manager.is_visible(element.style.layer_name):
                continue
            # 可见区域裁剪
            if not _is_visible_region(element):
                continue
            elem_face_info = getattr(element, 'face_info', {})
            # 面编辑模式：只绘制当前组件的面元素
            if is_face_edit:
                if not elem_face_info:
                    continue
                if face_cid and elem_face_info.get('component_id') != face_cid:
                    continue
                if face_filter != 'all':
                    fn = elem_face_info.get('face_name', '')
                    if fn != face_filter:
                        continue
                elements_to_draw.append(element)
                face_elements.append(element)
            else:
                # 正常模式：原有的过滤逻辑
                if face_cid and elem_face_info.get('component_id'):
                    if elem_face_info.get('component_id') != face_cid:
                        continue
                    if face_filter != 'all':
                        fn = elem_face_info.get('face_name', '')
                        if fn != face_filter:
                            continue
                elements_to_draw.append(element)
                if elem_face_info:
                    face_elements.append(element)
        
        # Phase 3a: 画面元素发光层（外发光效果，让面元素更醒目）
        for element in face_elements:
            if element.selected:
                continue
            try:
                self._draw_element_glow(painter, element)
            except Exception:
                pass
        
        # Phase 3b: 正常绘制所有元素
        for element in elements_to_draw:
            try:
                self._draw_element(painter, element)
            except Exception:
                pass

    def _draw_element_glow(self, painter: QPainter, element: BaseElement):
        """为面元素绘制发光层，增强视觉识别度"""
        scale = self.coord_system.get_scale()
        base_width = max(1, int(element.style.line_width * scale))
        glow_width = base_width + 3
        # 使用面元素颜色的半透明版本作为发光色
        r, g, b = element.style.color
        glow_pen = QPen(QColor(r, g, b, 60), glow_width)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.NoBrush)
        et = element.element_type.value
        
        if et in ('多段线', '多边形', '样条曲线'):
            segs = element.get_segments()
            for s, e in segs:
                s1 = self.coord_system.world_to_screen(s[0], s[1])
                e1 = self.coord_system.world_to_screen(e[0], e[1])
                painter.drawLine(s1[0], s1[1], e1[0], e1[1])
        elif et == '矩形':
            x, y = element.x, element.y
            sx, sy = self.coord_system.world_to_screen(x, y + element.height)
            sw = self.coord_system.world_dist_to_screen(element.width)
            sh = self.coord_system.world_dist_to_screen(element.height)
            painter.drawRect(sx, sy, sw, sh)
        elif et == '圆':
            cx, cy = self.coord_system.world_to_screen(element.cx, element.cy)
            r = self.coord_system.world_dist_to_screen(element.radius)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        elif et == '圆弧':
            pts = element.sample_points(36)
            sp = [self.coord_system.world_to_screen(p[0], p[1]) for p in pts]
            for i in range(len(sp) - 1):
                painter.drawLine(sp[i][0], sp[i][1], sp[i+1][0], sp[i+1][1])
        elif et == '椭圆':
            pts = element.sample_points(72)
            sp = [self.coord_system.world_to_screen(p[0], p[1]) for p in pts]
            for i in range(len(sp) - 1):
                painter.drawLine(sp[i][0], sp[i][1], sp[i+1][0], sp[i+1][1])
        elif et == '直线':
            sx1, sy1 = self.coord_system.world_to_screen(element.x1, element.y1)
            sx2, sy2 = self.coord_system.world_to_screen(element.x2, element.y2)
            painter.drawLine(sx1, sy1, sx2, sy2)

    def _draw_element(self, painter: QPainter, element: BaseElement):
        pen = element.style.to_qt_pen(self.coord_system.get_scale())
        if element.selected:
            # 面元素使用紫色高亮，普通元素使用蓝色
            if getattr(element, 'face_info', {}):
                pen = QPen(QColor(200, 50, 255), max(2, pen.width()), Qt.DashLine)
            else:
                pen = QPen(QColor(0, 120, 255), max(2, pen.width()))
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        et = element.element_type.value

        if et == '直线':
            sx1, sy1 = self.coord_system.world_to_screen(element.x1, element.y1)
            sx2, sy2 = self.coord_system.world_to_screen(element.x2, element.y2)
            painter.drawLine(sx1, sy1, sx2, sy2)
            if element.selected:
                painter.setBrush(QColor(0, 120, 255))
                painter.drawEllipse(sx1 - 4, sy1 - 4, 8, 8)
                painter.drawEllipse(sx2 - 4, sy2 - 4, 8, 8)

        elif et == '矩形':
            x, y = element.x, element.y
            sx, sy = self.coord_system.world_to_screen(x, y + element.height)
            sw = self.coord_system.world_dist_to_screen(element.width)
            sh = self.coord_system.world_dist_to_screen(element.height)
            painter.drawRect(sx, sy, sw, sh)
            if element.selected:
                painter.setBrush(QColor(0, 120, 255))
                for cx, cy in element.get_corners():
                    sx, sy = self.coord_system.world_to_screen(cx, cy)
                    painter.drawEllipse(sx - 4, sy - 4, 8, 8)

        elif et == '圆':
            cx, cy = self.coord_system.world_to_screen(element.cx, element.cy)
            r = self.coord_system.world_dist_to_screen(element.radius)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            if element.selected:
                painter.setBrush(QColor(0, 120, 255))
                painter.drawEllipse(cx - 4, cy - 4, 8, 8)
                painter.drawEllipse(cx + r - 4, cy - 4, 8, 8)
                painter.drawEllipse(cx - 4, cy + r - 4, 8, 8)
                painter.drawEllipse(cx + r - 4, cy + r - 4, 8, 8)

        elif et == '圆弧':
            pts = element.sample_points(36)
            sp = [self.coord_system.world_to_screen(p[0], p[1]) for p in pts]
            for i in range(len(sp) - 1):
                painter.drawLine(sp[i][0], sp[i][1], sp[i+1][0], sp[i+1][1])
            if element.selected:
                painter.setBrush(QColor(0, 120, 255))
                for p in [pts[0], pts[-1]]:
                    sx, sy = self.coord_system.world_to_screen(p[0], p[1])
                    painter.drawEllipse(sx - 4, sy - 4, 8, 8)

        elif et in ('多段线', '多边形', '样条曲线'):
            segs = element.get_segments()
            for s, e in segs:
                s1 = self.coord_system.world_to_screen(s[0], s[1])
                e1 = self.coord_system.world_to_screen(e[0], e[1])
                painter.drawLine(s1[0], s1[1], e1[0], e1[1])
            if element.selected:
                ctrl_color = QColor(200, 50, 255) if getattr(element, 'face_info', {}) else QColor(0, 120, 255)
                painter.setBrush(ctrl_color)
                for p in element.points:
                    sx, sy = self.coord_system.world_to_screen(p[0], p[1])
                    painter.drawEllipse(sx - 4, sy - 4, 8, 8)

        elif et == '椭圆':
            pts = element.sample_points(72)
            sp = [self.coord_system.world_to_screen(p[0], p[1]) for p in pts]
            for i in range(len(sp) - 1):
                painter.drawLine(sp[i][0], sp[i][1], sp[i+1][0], sp[i+1][1])
            if element.selected:
                painter.setBrush(QColor(0, 120, 255))
                for p in pts[::9]:
                    sx, sy = self.coord_system.world_to_screen(p[0], p[1])
                    painter.drawEllipse(sx - 4, sy - 4, 8, 8)

        elif et == '点':
            sx, sy = self.coord_system.world_to_screen(element.x, element.y)
            text_content = getattr(element, 'text_content', '')
            # v1.5 P3: 所有点元素正常模式下都不显示，只在选中时显示
            if element.selected:
                if text_content:
                    # 文本点选中时显示文本
                    painter.setPen(QPen(QColor(0, 120, 255), 1))
                    font = QFont("Microsoft YaHei", 9)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(sx + 5, sy - 5, str(text_content))
                else:
                    # 普通点选中时显示十字
                    r = 4
                    painter.drawLine(sx - r, sy, sx + r, sy)
                    painter.drawLine(sx, sy - r, sx, sy + r)
                painter.setBrush(QColor(0, 120, 255))
                painter.drawEllipse(sx - 4, sy - 4, 8, 8)

        # v1.5 P1: 3D高度标注
        if getattr(element, 'is_3d', False):
            self._draw_3d_label(painter, element)

        # 面元素名称标签 —— v1.5 P3: 只在面编辑模式下显示，且跳过原始PDF线条
        face_name = getattr(element, 'face_info', {}).get('face_name', '')
        is_pdf_original = getattr(element, 'face_info', {}).get('is_pdf_original', False)
        if face_name and not is_pdf_original:
            # 只在面编辑模式下显示标签，避免正常模式下标签覆盖整个画面
            if getattr(self.board, '_face_edit_mode', False):
                try:
                    from geometry.faces import FACE_NAME_LABELS
                    display_name = FACE_NAME_LABELS.get(face_name, face_name)
                    bounds = element.get_bounds()
                    sx, sy = self.coord_system.world_to_screen(bounds[0], bounds[3])
                    painter.setPen(QPen(QColor(200, 50, 255)))
                    painter.setFont(QFont("Microsoft YaHei", 9))
                    painter.drawText(int(sx) + 5, int(sy) - 5, f"[{display_name}]")
                except Exception:
                    pass

    def _draw_crosshair(self, painter: QPainter):
        mx, my = self.board._mouse_screen_pos
        pen = QPen(QColor(200, 200, 200), 1, Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(mx, 0, mx, self.height())
        painter.drawLine(0, my, self.width(), my)

    def _draw_snap_marker(self, painter: QPainter, snap_world: tuple, snap_type: str):
        sx, sy = self.coord_system.world_to_screen(snap_world[0], snap_world[1])
        color = QColor(255, 255, 0) if snap_type == 'grid' else QColor(0, 255, 0)
        pen = QPen(color, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(sx - 6, sy - 6, 12, 12)

    def _draw_3d_label(self, painter: QPainter, element: BaseElement):
        """绘制3D实体的高度标注"""
        try:
            h = getattr(element, 'height', 0) or getattr(element, 'thickness', 0)
            if h <= 0:
                return
            # 在元素包围盒的右上方绘制标注
            bx, by, bw_x, bh_y = element.get_bounds()
            sx, sy = self.coord_system.world_to_screen(bw_x, bh_y)
            label = f"H={h:.0f}"
            if getattr(element, 'entity_3d_type', ''):
                label = f"{element.entity_3d_type} {label}"
            pen = QPen(QColor(46, 125, 50), 1)
            painter.setPen(pen)
            font = QFont("Consolas", 9)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(sx + 5, sy - 5, label)
        except Exception:
            pass

    def resizeEvent(self, event: QResizeEvent):
        self.coord_system.update_viewport(self.width(), self.height())
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        try:
            self.setFocus()
            wx, wy = self.coord_system.screen_to_world(event.x(), event.y())
            wx, wy = self.board.snap_system.snap(wx, wy, self.coord_system, self.board.elements)
            button = 1 if event.button() == Qt.LeftButton else 2 if event.button() == Qt.RightButton else 4
            modifiers = 0
            if event.modifiers() & Qt.ControlModifier:
                modifiers |= 2
            if self.board.current_command:
                self.board.current_command.on_mouse_press(wx, wy, button, modifiers)
            # v1.5 P1: 选择后更新属性面板
            if (not self.board.current_command or
                isinstance(self.board.current_command, SelectCommand)):
                self.board._update_property_panel()
        except Exception as e:
            _write_board_log(f"mousePressEvent error: {traceback.format_exc()}")

    def mouseMoveEvent(self, event: QMouseEvent):
        try:
            self.board._mouse_screen_pos = (event.x(), event.y())
            wx, wy = self.coord_system.screen_to_world(event.x(), event.y())
            snap_result = self.board.snap_system.snap(wx, wy, self.coord_system, self.board.elements)
            if self.board.snap_system._snap_point:
                wx, wy = snap_result
            if self.board.current_command:
                need_update = self.board.current_command.on_mouse_move(wx, wy, 0)
                if need_update:
                    self.update()
            self.board.coord_label.setText(f"坐标: ({wx:.2f}, {wy:.2f}) mm")
        except Exception as e:
            _write_board_log(f"mouseMoveEvent error: {traceback.format_exc()}")

    def mouseReleaseEvent(self, event: QMouseEvent):
        try:
            wx, wy = self.coord_system.screen_to_world(event.x(), event.y())
            wx, wy = self.board.snap_system.snap(wx, wy, self.coord_system, self.board.elements)
            button = 1 if event.button() == Qt.LeftButton else 2 if event.button() == Qt.RightButton else 4
            if self.board.current_command:
                self.board.current_command.on_mouse_release(wx, wy, button, 0)
        except Exception as e:
            _write_board_log(f"mouseReleaseEvent error: {traceback.format_exc()}")

    def wheelEvent(self, event: QWheelEvent):
        try:
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else 0.9
            self.coord_system.zoom_at(event.x(), event.y(), factor)
            self.update()
        except Exception as e:
            _write_board_log(f"wheelEvent error: {traceback.format_exc()}")

    def keyPressEvent(self, event: QKeyEvent):
        try:
            key = event.key()
            key_text = event.text().upper()
            if key == Qt.Key_Escape:
                # v1.5 P3: ESC 退出面编辑模式（如果处于面编辑模式）
                if getattr(self.board, '_face_edit_mode', False):
                    self.board._exit_face_edit_mode()
                    return
                if self.board.current_command:
                    self.board.current_command.on_key_press('Escape', 0)
                return
            if key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
                return
            shortcut_map = self.board._shortcut_map
            if key_text in shortcut_map:
                cmd_class = shortcut_map[key_text]
                self.board.activate_command(cmd_class)
                return
            # 数字键支持命令行输入
            if Qt.Key_0 <= key <= Qt.Key_9 or key == Qt.Key_Minus or key == Qt.Key_Period:
                if self.board.cmd_input and self.board.cmd_input.hasFocus():
                    return
                # 数字直接传给当前命令的命令行处理
                if self.board.current_command and hasattr(self.board.current_command, 'on_cmd_text'):
                    self.board.cmd_input.setFocus()
                    self.board.cmd_input.setText(event.text())
                    self.board.cmd_input.setCursorPosition(len(event.text()))
        except Exception as e:
            _write_board_log(f"keyPressEvent error: {traceback.format_exc()}")

    def contextMenuEvent(self, event):
        """右键菜单 —— v1.5 P3: 面编辑模式下提供退出选项"""
        try:
            if not getattr(self.board, '_face_edit_mode', False):
                return
            menu = QMenu(self)
            exit_action = menu.addAction("❌ 退出面编辑模式")
            exit_action.triggered.connect(self.board._exit_face_edit_mode)
            menu.exec_(event.globalPos())
        except Exception as e:
            _write_board_log(f"contextMenuEvent error: {traceback.format_exc()}")


class CADBoardWindow(QMainWindow):
    """CAD画板主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAD画板 - BIMBase插件 v1.5")
        self.setGeometry(100, 100, 1400, 900)
        self.elements: List[BaseElement] = []
        self.coord_system = CoordinateSystem()
        self.layer_manager = LayerManager()
        self.snap_system = SnapSystem()
        self._mouse_screen_pos = None
        self._command_registry: Dict[str, Type[BaseCommand]] = {}
        self._shortcut_map: Dict[str, Type[BaseCommand]] = {}
        self.current_command: Optional[BaseCommand] = None
        self._default_command: Optional[SelectCommand] = None
        self._panning = False
        self._pan_start = None
        self.cmd_input = None  # 命令行输入框
        self.preview_3d_window = None  # 3D预览窗口

        # ========== Phase 3: 面编辑状态 ==========
        self._face_edit_mode = False
        self._face_filter = 'all'  # 'all' / 'top' / 'bottom' / 'front' / 'back' / 'left' / 'right'
        self._face_component_id = None
        self._face_group = None  # ComponentFaceGroup实例

        # ========== v1.5 P0: 完整Undo/Redo历史栈 ==========
        self._undo_stack: List[List[BaseElement]] = []
        self._redo_stack: List[List[BaseElement]] = []
        self._max_undo = 50

        self._init_ui()
        self._register_commands()
        self.set_default_command()

    # ---------- v1.5 P0: 完整Undo/Redo ----------

    def _save_undo_state(self):
        """保存当前元素状态到撤销栈"""
        cloned = []
        for e in self.elements:
            try:
                if hasattr(e, 'clone'):
                    cloned.append(e.clone())
            except Exception:
                pass
        self._undo_stack.append(cloned)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self):
        """撤销 - 恢复到上一个状态 (Ctrl+Z)"""
        if not self._undo_stack:
            self.status_bar.showMessage("撤销: 没有可撤销的操作")
            return
        # 保存当前状态到redo栈
        current = []
        for e in self.elements:
            try:
                if hasattr(e, 'clone'):
                    current.append(e.clone())
            except Exception:
                pass
        self._redo_stack.append(current)
        # 恢复上一个状态
        self.elements = self._undo_stack.pop()
        self.viewport.update()
        self.status_bar.showMessage("撤销完成 (Ctrl+Z)")

    def redo(self):
        """重做 - 恢复撤销前的状态 (Ctrl+Shift+Z / Ctrl+Y)"""
        if not self._redo_stack:
            self.status_bar.showMessage("重做: 没有可重做的操作")
            return
        # 保存当前状态到undo栈
        current = []
        for e in self.elements:
            try:
                if hasattr(e, 'clone'):
                    current.append(e.clone())
            except Exception:
                pass
        self._undo_stack.append(current)
        # 恢复redo栈的状态
        self.elements = self._redo_stack.pop()
        self.viewport.update()
        self.status_bar.showMessage("重做完成 (Ctrl+Shift+Z)")

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 左侧工具栏
        self.toolbar = QToolBar("绘图工具", self)
        self.toolbar.setMovable(False)
        self.toolbar.setOrientation(Qt.Vertical)
        self.addToolBar(Qt.LeftToolBarArea, self.toolbar)

        # 中间区域: 画布 + 底部命令行
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        # 画布
        self.viewport = CanvasWidget(self)
        center_layout.addWidget(self.viewport, 1)

        # 底部命令行 + 高度输入 + 状态栏
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(5, 0, 5, 0)
        bottom_layout.setSpacing(2)

        # 命令行 + 高度输入行
        cmd_row = QHBoxLayout()
        cmd_label = QLabel("命令:")
        cmd_label.setStyleSheet("color: #1565C0; font-weight: bold;")
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("输入坐标如(100,200) 或 长度/角度/参数...")
        self.cmd_input.setMinimumHeight(28)
        self.cmd_input.returnPressed.connect(self._on_cmd_return)
        self.cmd_input.textChanged.connect(self._on_cmd_text_changed)
        cmd_row.addWidget(cmd_label)
        cmd_row.addWidget(self.cmd_input, 1)

        # v1.5 P1: 当前高度输入框
        height_label = QLabel("高度:")
        height_label.setStyleSheet("color: #2E7D32; font-weight: bold;")
        self.height_input = QLineEdit("0")
        self.height_input.setMaximumWidth(60)
        self.height_input.setPlaceholderText("mm")
        self.height_input.setToolTip("新绘制3D元素的默认高度(mm)")
        cmd_row.addWidget(height_label)
        cmd_row.addWidget(self.height_input)

        bottom_layout.addLayout(cmd_row)

        # 状态栏
        self.status_bar = QStatusBar()
        self.coord_label = QLabel("坐标: (0.00, 0.00) mm")
        self.coord_label.setMinimumWidth(250)
        self.coord_label.setStyleSheet("QLabel { font-family: Consolas, monospace; }")
        self.status_bar.addPermanentWidget(self.coord_label)
        self.status_bar.addPermanentWidget(QLabel(" | "))
        self.cmd_label = QLabel("[选择模式]")
        self.cmd_label.setMinimumWidth(120)
        self.cmd_label.setStyleSheet("QLabel { font-weight: bold; color: #1565C0; }")
        self.status_bar.addPermanentWidget(self.cmd_label)
        bottom_layout.addWidget(self.status_bar)

        center_layout.addWidget(bottom_widget, 0)
        main_layout.addWidget(center_widget, 1)

        # v1.5 P1: 右侧属性面板
        self._build_property_panel()
        main_layout.addWidget(self.prop_panel, 0)

        # v1.5 P2: AI助手面板
        self.ai_panel = AIPanel(self)
        main_layout.addWidget(self.ai_panel, 0)

        self._create_toolbar_buttons()
        self._create_menubar()

    def _build_property_panel(self):
        """构建右侧属性面板 - 可编辑"""
        self.prop_panel = QFrame()
        self.prop_panel.setMaximumWidth(220)
        self.prop_panel.setMinimumWidth(180)
        self.prop_panel.setFrameShape(QFrame.StyledPanel)
        prop_layout = QVBoxLayout(self.prop_panel)
        prop_layout.setContentsMargins(8, 8, 8, 8)
        prop_layout.setSpacing(4)

        prop_layout.addWidget(QLabel("<b>属性面板</b>"))

        self.prop_inputs = {}
        # 通用属性 - 使用QLineEdit使其可编辑
        for label_text, key, default_val in [
            ("元素类型", "type", "-"),
            ("图层", "layer", "0"),
            ("Z起始(mm)", "z_start", "0.00"),
            ("Z终止(mm)", "z_end", "0.00"),
            ("厚度(mm)", "thickness", "0.00"),
            ("宽度(mm)", "width", "0.00"),
            ("高度(mm)", "height", "0.00"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label_text}:"))
            if key in ('type',):
                # 类型不可编辑
                val_widget = QLabel(default_val)
                val_widget.setStyleSheet("QLabel { color: #1565C0; }")
                self.prop_inputs[key] = val_widget
            else:
                val_widget = QLineEdit(default_val)
                val_widget.setMaximumWidth(90)
                if key == 'layer':
                    val_widget.setEnabled(True)
                else:
                    val_widget.setValidator(None)  # 允许数字输入
                self.prop_inputs[key] = val_widget
            row.addWidget(val_widget)
            prop_layout.addLayout(row)

        # 3D标记
        self.prop_3d_cb = QCheckBox("3D实体")
        prop_layout.addWidget(self.prop_3d_cb)

        self.prop_entity_input = QLineEdit()
        self.prop_entity_input.setPlaceholderText("实体类型")
        self.prop_entity_input.setMaximumWidth(120)
        prop_layout.addWidget(QLabel("实体类型:"))
        prop_layout.addWidget(self.prop_entity_input)

        # 面参数总览按钮（仅当选中面元素时显示）
        self.prop_face_overview_btn = QPushButton("面参数总览")
        self.prop_face_overview_btn.setStyleSheet("QPushButton { background-color: #E65100; color: white; }")
        self.prop_face_overview_btn.setToolTip("打开面参数总览对话框，批量修改组件参数")
        self.prop_face_overview_btn.clicked.connect(self._show_face_overview)
        self.prop_face_overview_btn.setVisible(False)
        prop_layout.addWidget(self.prop_face_overview_btn)

        # v1.5 P3: 属性面板中的退出面编辑按钮（面编辑模式下显示，更明显）
        self.prop_exit_face_btn = QPushButton("❌ 退出面编辑模式")
        self.prop_exit_face_btn.setStyleSheet(
            "QPushButton { background-color: #C62828; color: white; font-weight: bold; font-size: 12px; padding: 6px; }"
        )
        self.prop_exit_face_btn.setToolTip("退出面编辑模式，恢复正常编辑")
        self.prop_exit_face_btn.clicked.connect(self._exit_face_edit_mode)
        self.prop_exit_face_btn.setVisible(False)
        prop_layout.addWidget(self.prop_exit_face_btn)

        prop_layout.addStretch()
        # 应用按钮
        self.prop_apply_btn = QPushButton("应用修改")
        self.prop_apply_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        self.prop_apply_btn.clicked.connect(self._apply_property_changes)
        prop_layout.addWidget(self.prop_apply_btn)

        self._current_prop_element = None

    def _update_property_panel(self):
        """根据当前选中的元素更新属性面板 —— Phase 3 Enhancement: 面编辑模式下过滤属性"""
        selected = [e for e in self.elements if getattr(e, 'selected', False)]
        if len(selected) != 1:
            self.prop_inputs['type'].setText("-")
            self.prop_inputs['layer'].setText("0")
            self.prop_inputs['z_start'].setText("0.00")
            self.prop_inputs['z_end'].setText("0.00")
            self.prop_inputs['thickness'].setText("0.00")
            self.prop_inputs['width'].setText("0.00")
            self.prop_inputs['height'].setText("0.00")
            self.prop_3d_cb.setChecked(False)
            self.prop_entity_input.setText("")
            self.prop_face_overview_btn.setVisible(False)
            self._current_prop_element = None
            return

        elem = selected[0]
        self._current_prop_element = elem
        is_face = hasattr(elem, 'face_info') and bool(elem.face_info)

        self.prop_inputs['type'].setText(elem.element_type.value)
        self.prop_inputs['layer'].setText(elem.style.layer_name)
        self.prop_inputs['z_start'].setText(f"{elem.z_start:.2f}")
        self.prop_inputs['z_end'].setText(f"{elem.z_end:.2f}")
        self.prop_inputs['thickness'].setText(f"{elem.thickness:.2f}")
        # 宽度：矩形/圆/椭圆/多段线等
        if hasattr(elem, 'width'):
            self.prop_inputs['width'].setText(f"{elem.width:.2f}")
        elif hasattr(elem, 'radius'):
            self.prop_inputs['width'].setText(f"{elem.radius:.2f}")
        elif hasattr(elem, 'points'):
            b = elem.get_bounds()
            self.prop_inputs['width'].setText(f"{b[2] - b[0]:.2f}")
        else:
            self.prop_inputs['width'].setText("-")
        # 高度：矩形元素显示2D高度，多段线显示包围盒高度，其他显示3D拉伸高度
        if elem.__class__.__name__ == 'RectangleElement':
            self.prop_inputs['height'].setText(f"{elem.height:.2f}")
        elif hasattr(elem, 'points'):
            b = elem.get_bounds()
            self.prop_inputs['height'].setText(f"{b[3] - b[1]:.2f}")
        else:
            self.prop_inputs['height'].setText(f"{elem.z_end - elem.z_start:.2f}")
        self.prop_3d_cb.setChecked(elem.is_3d)
        self.prop_entity_input.setText(elem.entity_3d_type or "")

        # 显示/隐藏"面参数总览"按钮
        self.prop_face_overview_btn.setVisible(is_face)

        # Phase 3 Enhancement: 面编辑模式下禁用无关属性的编辑
        if self._face_edit_mode and is_face:
            # 面编辑模式：只允许修改几何参数（width/height/radius）
            self.prop_inputs['layer'].setEnabled(False)
            self.prop_inputs['z_start'].setEnabled(False)
            self.prop_inputs['z_end'].setEnabled(False)
            self.prop_inputs['thickness'].setEnabled(False)
            self.prop_3d_cb.setEnabled(False)
            self.prop_entity_input.setEnabled(False)
            # 面元素一定有width或radius，保持可用
            self.prop_inputs['width'].setEnabled(True)
            self.prop_inputs['height'].setEnabled(True)
        else:
            # 正常模式：恢复所有属性可编辑
            self.prop_inputs['layer'].setEnabled(True)
            self.prop_inputs['z_start'].setEnabled(True)
            self.prop_inputs['z_end'].setEnabled(True)
            self.prop_inputs['thickness'].setEnabled(True)
            self.prop_3d_cb.setEnabled(True)
            self.prop_entity_input.setEnabled(True)
            self.prop_inputs['width'].setEnabled(True)
            self.prop_inputs['height'].setEnabled(True)

    def _show_face_overview(self):
        """打开面参数总览对话框，批量修改组件参数。"""
        elem = self._current_prop_element
        if not elem or not hasattr(elem, 'face_info') or not elem.face_info:
            return

        # 获取当前组件的所有面元素
        component_id = elem.face_info.get('component_id')
        if not component_id or not self._face_group:
            QMessageBox.information(self, "面参数总览", "未找到组件的面元素。")
            return

        face_elems = self._face_group.get_elements_by_component(component_id)
        if not face_elems:
            QMessageBox.information(self, "面参数总览", "未找到面元素。")
            return

        component_type = face_elems[0].component_type
        component_params = dict(face_elems[0].component_params)

        # 弹出对话框
        from face_overview_dialog import FaceOverviewDialog
        dlg = FaceOverviewDialog(self, component_type, component_params, face_elems)
        if dlg.exec_() != QDialog.Accepted:
            return

        new_params = dlg.get_new_params()
        if not new_params or new_params == component_params:
            return

        self._save_undo_state()

        # 重新生成所有面
        from geometry.faces import FaceManager
        self._face_group.apply_params_and_regenerate(component_id, new_params)

        # 更新源元素参数
        source_elem = None
        for e in self.elements:
            if e.id == component_id:
                e.component_params = dict(new_params)
                source_elem = e
                break

        # 更新源元素高度
        if source_elem:
            if source_elem.component_type == '直角三棱柱':
                if '高度' in new_params:
                    source_elem.z_end = source_elem.z_start + float(new_params['高度'])
            else:
                z_bottom = new_params.get('z_bottom') or new_params.get('z1') or new_params.get('z', 0)
                z_top = new_params.get('z_top') or new_params.get('z2') or new_params.get('z', 0)
                if z_bottom is not None:
                    source_elem.z_start = float(z_bottom)
                if z_top is not None:
                    source_elem.z_end = float(z_top)

        # 同步到BIMBase（如果该组件已注册）
        if source_elem:
            try:
                from utils.component_registry import get_registry
                registry = get_registry()
                info = registry.get(source_elem.id)
                if info and info.get('instance'):
                    inst = info['instance']
                    for k, v in new_params.items():
                        if k in inst:
                            try:
                                inst[k] = v
                            except Exception:
                                pass
                    try:
                        inst.replace()
                    except Exception as e:
                        _write_board_log(f"inst.replace() error: {e}")
            except Exception as e:
                _write_board_log(f"BIMBase sync from overview error: {e}")

        self.viewport.update()
        if self.preview_3d_window:
            self.preview_3d_window.refresh_from_canvas(self.elements)
        self.status_bar.showMessage("面参数总览已应用，组件参数已更新")

        # 刷新属性面板（因为面元素的几何可能变了）
        self._update_property_panel()

    def _apply_property_changes(self):
        """应用属性面板中的修改到当前元素"""
        import traceback as _tb
        def _log_face(msg):
            try:
                log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'face_debug.log')
                with open(log_path, 'a', encoding='utf-8') as f:
                    from datetime import datetime
                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [PROP] {msg}\n")
            except Exception:
                pass

        elem = self._current_prop_element
        if not elem:
            _log_face("no current_prop_element")
            return
        self._save_undo_state()
        _log_face(f"elem={elem.__class__.__name__} id={elem.id} face_name={getattr(elem, 'face_info', {}).get('face_name', 'N/A')}")

        # 对面元素：在修改前保存 old_state，供 _apply_face_changes 使用
        is_face = hasattr(elem, 'face_info') and elem.face_info
        if is_face:
            from geometry.faces import FaceManager
            elem._face_old_state = FaceManager.capture_element_state(elem)
            _log_face(f"saved old_state: {elem._face_old_state}")

        changed = False
        try:
            elem.z_start = float(self.prop_inputs['z_start'].text())
        except ValueError:
            pass
        try:
            elem.z_end = float(self.prop_inputs['z_end'].text())
        except ValueError:
            pass
        try:
            elem.thickness = float(self.prop_inputs['thickness'].text())
        except ValueError:
            pass
        try:
            new_width = float(self.prop_inputs['width'].text())
            old_width = getattr(elem, 'width', None) or getattr(elem, 'radius', None)
            if hasattr(elem, 'width'):
                elem.width = new_width
                _log_face(f"width: {old_width} -> {new_width}")
                changed = True
            elif hasattr(elem, 'radius'):
                elem.radius = new_width
                _log_face(f"radius: {old_width} -> {new_width}")
                changed = True
        except ValueError:
            pass
        try:
            new_height = float(self.prop_inputs['height'].text())
            old_height = elem.height
            elem.height = new_height
            _log_face(f"height: {old_height} -> {new_height}")
            changed = True
            # 非矩形元素：height 修改同步更新 z_end（保持 z_start 不变）
            if elem.__class__.__name__ != 'RectangleElement':
                elem.z_end = elem.z_start + new_height
        except ValueError:
            pass
        elem.style.layer_name = self.prop_inputs['layer'].text() or elem.style.layer_name
        elem.is_3d = self.prop_3d_cb.isChecked()
        elem.entity_3d_type = self.prop_entity_input.text()

        # 给面元素打标记
        if changed and is_face:
            elem._face_modified = True
            _log_face(f"marked _face_modified for {elem.face_info.get('face_name', 'unknown')}")
            # 自动触发面修改应用：更新组件参数、重新生成所有面、更新源元素
            # 这样用户不需要再点一次"应用面修改"
            self._apply_face_changes()
            return  # _apply_face_changes 已经更新了UI和状态栏

        self._update_property_panel()
        self.status_bar.showMessage("属性已应用")
        self.viewport.update()

    def _create_toolbar_buttons(self):
        self.toolbar.addWidget(QLabel("<b>文件</b>"))

        import_btn = QPushButton("导入文件")
        import_btn.setToolTip("导入DWG/DXF/PDF文件")
        import_btn.setMinimumWidth(80)
        import_btn.clicked.connect(self._import_file)
        self.toolbar.addWidget(import_btn)

        export_btn = QPushButton("导出DWG")
        export_btn.setToolTip("导出为DXF/DWG文件")
        export_btn.setMinimumWidth(80)
        export_btn.clicked.connect(self._export_dwg)
        self.toolbar.addWidget(export_btn)

        sync_btn = QPushButton("同步到BIMBase")
        sync_btn.setToolTip("将当前画板内容同步为BIMBase参数化组件")
        sync_btn.setMinimumWidth(80)
        sync_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        sync_btn.clicked.connect(self._sync_to_bimbase)
        self.toolbar.addWidget(sync_btn)

        pull_btn = QPushButton("从BIMBase更新")
        pull_btn.setToolTip("从BIMBase读取参数更新画板")
        pull_btn.setMinimumWidth(80)
        pull_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        pull_btn.clicked.connect(self._sync_from_bimbase)
        self.toolbar.addWidget(pull_btn)

        # ===== 3D预览按钮 =====
        preview_btn = QPushButton("3D预览")
        preview_btn.setToolTip("打开3D预览窗口")
        preview_btn.setMinimumWidth(80)
        preview_btn.setStyleSheet("QPushButton { background-color: #4a90d9; color: white; font-weight: bold; }")
        preview_btn.clicked.connect(self._show_3d_preview)
        self.toolbar.addWidget(preview_btn)

        self.toolbar.addSeparator()

        # ===== Phase 3: 面编辑工具栏 =====
        self.toolbar.addWidget(QLabel("<b>面编辑</b>"))

        gen_face_btn = QPushButton("生成面元素")
        gen_face_btn.setToolTip("为选中的组件生成面元素")
        gen_face_btn.setMinimumWidth(90)
        gen_face_btn.setStyleSheet("QPushButton { background-color: #E65100; color: white; }")
        gen_face_btn.clicked.connect(self._generate_faces_for_selected)
        self.toolbar.addWidget(gen_face_btn)

        # Phase 3 Enhancement: 智能识别三视图按钮
        self._recognize_views_btn = QPushButton("🔍 识别三视图")
        self._recognize_views_btn.setToolTip("基于本地规则识别导入的PDF三视图")
        self._recognize_views_btn.setMinimumWidth(110)
        self._recognize_views_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; font-weight: bold; }")
        self._recognize_views_btn.clicked.connect(self._recognize_pdf_views)
        self.toolbar.addWidget(self._recognize_views_btn)

        # Phase 2 Enhancement: 复杂识别（Qwen-VL 多模态 AI）
        self._complex_recognize_btn = QPushButton("🧠 复杂识别")
        self._complex_recognize_btn.setToolTip("使用 Qwen-VL 从 PDF/图片识别复杂构件（如引桥桥墩）")
        self._complex_recognize_btn.setMinimumWidth(110)
        self._complex_recognize_btn.setStyleSheet("QPushButton { background-color: #7B1FA2; color: white; font-weight: bold; }")
        self._complex_recognize_btn.clicked.connect(self._recognize_complex_views)
        self.toolbar.addWidget(self._complex_recognize_btn)

        # Phase 3 Enhancement: 退出面编辑模式按钮（默认隐藏，进入面编辑后显示）
        self._exit_face_btn = QPushButton("❌ 退出面编辑")
        self._exit_face_btn.setToolTip("退出面编辑模式，恢复源元素显示")
        self._exit_face_btn.setMinimumWidth(100)
        self._exit_face_btn.setStyleSheet("QPushButton { background-color: #C62828; color: white; font-weight: bold; }")
        self._exit_face_btn.clicked.connect(self._exit_face_edit_mode)
        self._exit_face_btn.setVisible(False)
        self.toolbar.addWidget(self._exit_face_btn)

        self._face_mode_combo = QComboBox()
        self._face_mode_combo.setMinimumWidth(70)
        self._face_mode_combo.addItems(["三视图", "完整", "智能"])
        self._face_mode_combo.setToolTip("面生成模式：三视图=3个投影面，完整=所有面，智能=按组件类型自动决定")
        self.toolbar.addWidget(self._face_mode_combo)

        apply_face_btn = QPushButton("应用面修改")
        apply_face_btn.setToolTip("将面元素的变化应用到组件参数并重新生成")
        apply_face_btn.setMinimumWidth(90)
        apply_face_btn.setStyleSheet("QPushButton { background-color: #E65100; color: white; }")
        apply_face_btn.clicked.connect(self._apply_face_changes)
        self.toolbar.addWidget(apply_face_btn)

        self._face_filter_combo = QComboBox()
        self._face_filter_combo.setMinimumWidth(80)
        self._face_filter_combo.addItems(["全部面", "顶面", "前视图", "左视图", "侧面"])
        self._face_filter_combo.currentTextChanged.connect(self._on_face_filter_changed)
        self.toolbar.addWidget(self._face_filter_combo)

        self.toolbar.addSeparator()

        self.toolbar.addWidget(QLabel("<b>绘图</b>"))
        self._add_cmd_btn("直线 (L)", "L", LineCommand)
        self._add_cmd_btn("圆 (C)", "C", CircleCommand)
        self._add_cmd_btn("圆弧 (A)", "A", ArcCommand)
        self._add_cmd_btn("矩形 (REC)", "REC", RectangleCommand)
        self._add_cmd_btn("多段线 (PL)", "PL", PolylineCommand)
        self._add_cmd_btn("多边形 (POL)", "POL", PolygonCommand)
        self._add_cmd_btn("椭圆 (EL)", "EL", EllipseCommand)
        self._add_cmd_btn("样条曲线 (SPL)", "SPL", SplineCommand)
        self._add_cmd_btn("点 (PO)", "PO", PointCommand)

        self.toolbar.addSeparator()

        self.toolbar.addWidget(QLabel("<b>修改</b>"))
        self._add_cmd_btn("删除 (E)", "E", DeleteCommand)
        self._add_cmd_btn("复制 (CO)", "CO", CopyCommand)
        self._add_cmd_btn("镜像 (MI)", "MI", MirrorCommand)
        self._add_cmd_btn("偏移 (O)", "O", OffsetCommand)
        self._add_cmd_btn("阵列 (AR)", "AR", ArrayCommand)
        self._add_cmd_btn("移动 (M)", "M", MoveCommand)
        self._add_cmd_btn("旋转 (RO)", "RO", RotateCommand)
        self._add_cmd_btn("缩放 (SC)", "SC", ScaleCommand)
        self._add_cmd_btn("拉伸 (S)", "S", StretchCommand)
        self._add_cmd_btn("修剪 (TR)", "TR", TrimCommand)
        self._add_cmd_btn("延伸 (EX)", "EX", ExtendCommand)
        self._add_cmd_btn("打断 (BR)", "BR", BreakCommand)
        self._add_cmd_btn("打断于点", "", BreakAtPointCommand)
        self._add_cmd_btn("合并 (J)", "J", JoinCommand)
        self._add_cmd_btn("倒斜角 (CHA)", "CHA", ChamferCommand)
        self._add_cmd_btn("圆角 (F)", "F", FilletCommand)
        self._add_cmd_btn("分解 (X)", "X", ExplodeCommand)

        self.toolbar.addSeparator()

        self.toolbar.addWidget(QLabel("<b>等分</b>"))
        self._add_cmd_btn("定数等分 (DIV)", "DIV", DivideCommand)
        self._add_cmd_btn("定距等分 (ME)", "ME", MeasureCommand)

        self.toolbar.addSeparator()

        self.toolbar.addWidget(QLabel("<b>工具</b>"))

        # ===== 组件关联按钮 =====
        assoc_btn = QPushButton("组件关联")
        assoc_btn.setToolTip("将选中的元素关联为一个参数化组件")
        assoc_btn.setMinimumWidth(80)
        assoc_btn.setStyleSheet("QPushButton { background-color: #2E7D32; color: white; }")
        assoc_btn.clicked.connect(self._associate_component)
        self.toolbar.addWidget(assoc_btn)

        deselect_btn = QPushButton("取消选中")
        deselect_btn.setMinimumWidth(80)
        deselect_btn.clicked.connect(self._deselect_all)
        self.toolbar.addWidget(deselect_btn)

        undo_btn = QPushButton("撤销 (Ctrl+Z)")
        undo_btn.setMinimumWidth(80)
        undo_btn.clicked.connect(self.undo)
        self.toolbar.addWidget(undo_btn)

        # v1.5 P0: 增加Redo按钮
        redo_btn = QPushButton("重做 (Ctrl+Shift+Z)")
        redo_btn.setMinimumWidth(80)
        redo_btn.clicked.connect(self.redo)
        self.toolbar.addWidget(redo_btn)

        canvas_btn = QPushButton("画布设置")
        canvas_btn.setMinimumWidth(80)
        canvas_btn.clicked.connect(self._show_canvas_settings)
        self.toolbar.addWidget(canvas_btn)

        layer_btn = QPushButton("图层管理")
        layer_btn.setMinimumWidth(80)
        layer_btn.clicked.connect(self._show_layer_manager)
        self.toolbar.addWidget(layer_btn)

        snap_btn = QPushButton("吸附设置")
        snap_btn.setMinimumWidth(80)
        snap_btn.clicked.connect(self._show_snap_settings)
        self.toolbar.addWidget(snap_btn)

        env_btn = QPushButton("配置环境")
        env_btn.setToolTip("一键配置VSCode开发环境")
        env_btn.setMinimumWidth(80)
        env_btn.setStyleSheet("QPushButton { background-color: #2E7D32; color: white; }")
        env_btn.clicked.connect(self._show_env_config)
        self.toolbar.addWidget(env_btn)

        # v1.5 P1: 3D实体命令 (使用activate_command(cmd_class), 与2D命令一致)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(QLabel("<b>3D实体</b>"))

        self._add_solid_btn("拉伸体", ExtrudeCommand)
        self._add_solid_btn("立方体", BoxCommand)
        self._add_solid_btn("球体", SphereCommand)
        self._add_solid_btn("圆锥", ConeCommand)
        self._add_solid_btn("圆环", TorusCommand)
        self._add_solid_btn("棱锥", PyramidCommand)
        self._add_solid_btn("三棱柱", TriangularPrismCommand)

        # v1.5 P2: AI助手按钮
        self.toolbar.addSeparator()
        ai_btn = QPushButton("AI助手")
        ai_btn.setMinimumWidth(80)
        ai_btn.setStyleSheet("QPushButton { background-color: #7B1FA2; color: white; font-weight: bold; }")
        ai_btn.clicked.connect(self._toggle_ai_panel)
        self.toolbar.addWidget(ai_btn)

        self.toolbar.addSeparator()
        help_btn = QPushButton("快捷键")
        help_btn.setMinimumWidth(80)
        help_btn.clicked.connect(self._show_shortcuts)
        self.toolbar.addWidget(help_btn)

    def _add_solid_btn(self, label: str, cmd_class: Type[BaseCommand]):
        """添加3D实体命令按钮 - 使用activate_command与2D命令保持一致"""
        btn = QPushButton(label)
        btn.setMinimumWidth(80)
        btn.clicked.connect(lambda checked=False, cls=cmd_class: self.activate_command(cls))
        self.toolbar.addWidget(btn)

    def _add_cmd_btn(self, label: str, shortcut: str, cmd_class: Type[BaseCommand]):
        btn = QPushButton(label)
        btn.setMinimumWidth(80)
        btn.clicked.connect(lambda: self.activate_command(cmd_class))
        self.toolbar.addWidget(btn)

    def _create_menubar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        file_menu.addAction("导入文件 (DWG/DXF/PDF)", self._import_file)
        file_menu.addAction("导出DXF/DWG", self._export_dwg)
        file_menu.addSeparator()
        file_menu.addAction("同步到BIMBase", self._sync_to_bimbase)
        file_menu.addAction("从BIMBase更新", self._sync_from_bimbase)

        view_menu = menubar.addMenu("视图")
        view_menu.addAction("重置视图", self._reset_view)
        view_menu.addAction("适应窗口", self._fit_to_window)
        view_menu.addSeparator()
        # 网格显示开关
        self._grid_action = view_menu.addAction("显示网格")
        self._grid_action.setCheckable(True)
        self._grid_action.setChecked(True)
        self._grid_action.triggered.connect(self._toggle_grid)
        view_menu.addSeparator()
        view_menu.addAction("背景颜色", self._change_bg_color)
        view_menu.addAction("3D预览", self._show_3d_preview)

        sync_menu = menubar.addMenu("同步")
        sync_menu.addAction("同步到BIMBase", self._sync_to_bimbase)
        sync_menu.addAction("从BIMBase更新", self._sync_from_bimbase)
        sync_menu.addSeparator()
        sync_menu.addAction("同步设置...", self._show_sync_settings)
        sync_menu.addAction("图纸识别 API 配置...", self._show_drawing_ai_config)

    def _register_commands(self):
        commands = [
            SelectCommand,
            LineCommand, CircleCommand, ArcCommand, RectangleCommand,
            PolylineCommand, PolygonCommand, EllipseCommand,
            SplineCommand, PointCommand,
            DeleteCommand, CopyCommand, MirrorCommand, OffsetCommand,
            ArrayCommand, MoveCommand, RotateCommand, ScaleCommand,
            StretchCommand, TrimCommand, ExtendCommand,
            BreakCommand, BreakAtPointCommand, JoinCommand,
            ChamferCommand, FilletCommand, ExplodeCommand,
            DivideCommand, MeasureCommand,
            ExtrudeCommand, BoxCommand, SphereCommand, ConeCommand,
            TorusCommand, PyramidCommand, TriangularPrismCommand,
        ]
        for cmd_class in commands:
            self._command_registry[cmd_class.__name__] = cmd_class
            if cmd_class.shortcut:
                self._shortcut_map[cmd_class.shortcut.upper()] = cmd_class
        self._default_command = SelectCommand(self)

    def activate_command(self, cmd_class: Type[BaseCommand]):
        """激活指定命令（修改命令切换时保留已有选择）—— Phase 3 Enhancement: 面编辑模式拦截"""
        try:
            # Phase 3 Enhancement: 面编辑模式下只允许选择命令
            if self._face_edit_mode:
                from commands.base_command import SelectCommand
                if not issubclass(cmd_class, SelectCommand):
                    self.status_bar.showMessage("🔶 面编辑模式：请先退出面编辑再使用其他命令")
                    return
            old_cmd = self.current_command
            if old_cmd and old_cmd != self._default_command:
                old_cmd.deactivate()
            # v1.5 P0: 创建新命令前保存撤销状态
            self._save_undo_state()
            # 切换到新命令
            self.current_command = cmd_class(self)
            self.current_command.activate()
            self.cmd_label.setText(f"命令: {cmd_class.name}")
            self.status_bar.showMessage(self.current_command.get_prompt())
            self.viewport.update()
            # 更新命令行提示
            self._update_cmd_input_hint()
        except Exception as e:
            _write_board_log(f"activate_command error: {traceback.format_exc()}")
            self.status_bar.showMessage(f"命令激活失败: {e}")

    def set_default_command(self):
        """切换到默认选择命令"""
        try:
            if self.current_command and self.current_command != self._default_command:
                self.current_command.deactivate()
            self.current_command = self._default_command
            if self.current_command:
                self.current_command.activate()
            self.cmd_label.setText("命令: 选择")
            self.status_bar.showMessage("就绪 - 按快捷键选择绘图命令")
            self.viewport.update()
            self._update_cmd_input_hint()
        except Exception as e:
            _write_board_log(f"set_default_command error: {traceback.format_exc()}")

    def add_element(self, element: BaseElement):
        self.elements.append(element)
        self.status_bar.showMessage(
            f"已添加 {element.element_type.value}，共 {len(self.elements)} 个元素"
        )

    def apply_current_layer_style(self, element: BaseElement):
        self.layer_manager.apply_layer_style(element)

    # ---------- 命令行处理 ----------

    def _update_cmd_input_hint(self):
        """更新命令行输入提示"""
        if self.current_command:
            prompt = self.current_command.get_prompt()
            self.cmd_input.setPlaceholderText(prompt)
        else:
            self.cmd_input.setPlaceholderText("输入坐标如(100,200) 或 长度/角度/参数...")

    def _on_cmd_text_changed(self, text):
        """命令行文本变化时传递给当前命令"""
        if self.current_command and hasattr(self.current_command, 'on_cmd_text'):
            try:
                self.current_command.on_cmd_text(text)
            except Exception as e:
                _write_board_log(f"cmd_text error: {e}")

    def _on_cmd_return(self):
        """命令行回车确认"""
        text = self.cmd_input.text().strip()
        # v1.5 P1: 3D实体命令允许空文本回车（使用默认高度）
        is_solid = (self.current_command and 
                    getattr(self.current_command, 'is_solid_command', False))
        try:
            if self.current_command and hasattr(self.current_command, 'on_cmd_confirm'):
                # 3D命令: 空文本也调用on_cmd_confirm（使用默认高度）
                # 2D命令: 空文本直接返回（保持原有行为）
                if not text and not is_solid:
                    return
                result = self.current_command.on_cmd_confirm(text)
                if result:
                    self.cmd_input.clear()
                    self.viewport.update()
                    self._update_cmd_input_hint()
                    return
            # 非3D命令: 空文本不解析坐标
            if not text:
                return
            # 默认：尝试解析为坐标
            parsed = self._parse_coord_input(text)
            if parsed:
                wx, wy = parsed
                if self.current_command:
                    self.current_command.on_mouse_press(wx, wy, 1, 0)
                    self.viewport.update()
                self.cmd_input.clear()
        except Exception as e:
            _write_board_log(f"cmd_return error: {traceback.format_exc()}")
            self.status_bar.showMessage(f"输入解析错误: {e}")

    def _parse_coord_input(self, text):
        """解析坐标输入，支持 (100,200)、100,200、@100,200(相对)"""
        import re
        text = text.strip()
        # 去掉括号
        text = text.replace('(', '').replace(')', '').replace('，', ',')
        # 相对坐标
        relative = False
        if text.startswith('@'):
            relative = True
            text = text[1:]
        parts = text.split(',')
        if len(parts) == 2:
            try:
                x = float(parts[0].strip())
                y = float(parts[1].strip())
                if relative and self.current_command:
                    last_pt = self.current_command.get_last_point()
                    if last_pt:
                        x += last_pt[0]
                        y += last_pt[1]
                return (x, y)
            except ValueError:
                pass
        return None

    # ---------- 鼠标中键平移 ----------

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MidButton:
            self._panning = True
            self._pan_start = (event.x(), event.y())
            self.setCursor(Qt.ClosedHandCursor)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start:
            dx = event.x() - self._pan_start[0]
            dy = event.y() - self._pan_start[1]
            self.coord_system.pan(dx, dy)
            self._pan_start = (event.x(), event.y())
            self.viewport.update()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MidButton:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            return
        super().mouseReleaseEvent(event)

    # ---------- 视图操作 ----------

    def _reset_view(self):
        self.coord_system.zoom_reset()
        self.viewport.update()
        self.status_bar.showMessage("视图已重置")

    def _fit_to_window(self):
        self.coord_system.zoom_reset()
        self.viewport.update()
        self.status_bar.showMessage("视图已适应窗口")

    def _toggle_grid(self, checked):
        self.viewport.show_grid = checked
        self.viewport.update()
        status = "开启" if checked else "关闭"
        self.status_bar.showMessage(f"网格显示已{status}")

    def _change_bg_color(self):
        from PyQt5.QtWidgets import QColorDialog
        current = self.viewport.bg_color
        color = QColorDialog.getColor(current, self, "选择画板背景颜色")
        if color.isValid():
            self.viewport.bg_color = color
            # 根据背景亮度自动调整网格颜色
            brightness = color.red() * 0.299 + color.green() * 0.587 + color.blue() * 0.114
            if brightness > 180:
                # 浅色背景：网格用灰色
                self.viewport.grid_major_color = QColor(180, 180, 180)
                self.viewport.grid_minor_color = QColor(220, 220, 220)
                self.viewport.axis_color_x = QColor(200, 50, 50)
                self.viewport.axis_color_y = QColor(50, 180, 50)
            elif brightness > 100:
                # 中等背景
                self.viewport.grid_major_color = QColor(120, 120, 120)
                self.viewport.grid_minor_color = QColor(180, 180, 180)
                self.viewport.axis_color_x = QColor(180, 50, 50)
                self.viewport.axis_color_y = QColor(50, 160, 50)
            else:
                # 深色背景：恢复默认
                self.viewport.grid_major_color = QColor(80, 80, 80)
                self.viewport.grid_minor_color = QColor(45, 45, 45)
                self.viewport.axis_color_x = QColor(180, 50, 50)
                self.viewport.axis_color_y = QColor(50, 180, 50)
            self.viewport.update()
            self.status_bar.showMessage(f"背景颜色已更改为 RGB({color.red()}, {color.green()}, {color.blue()})")

    # ---------- 导入导出 ----------

    def _import_file(self):
        """导入文件 —— 支持DWG/DXF/PDF"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入文件", "",
            "CAD/PDF文件 (*.dwg *.dxf *.pdf);;DWG (*.dwg);;DXF (*.dxf);;PDF (*.pdf);;所有文件 (*.*)"
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            elements, errors = import_pdf(file_path, self.status_bar.showMessage)
            import_source = "PDF"
        else:
            elements, errors = import_dwg(file_path, self.status_bar.showMessage)
            import_source = "DWG/DXF"

        if elements:
            self._save_undo_state()
            layers_found = set()

            # 智能反色：检测背景色，深色背景上将黑色/深色线条反转为亮色
            bg_brightness = self.viewport.bg_color.red() * 0.299 + \
                           self.viewport.bg_color.green() * 0.587 + \
                           self.viewport.bg_color.blue() * 0.114
            is_dark_bg = bg_brightness < 128

            for e in elements:
                if is_dark_bg and hasattr(e, 'style') and e.style:
                    r, g, b = e.style.color
                    elem_brightness = r * 0.299 + g * 0.587 + b * 0.114
                    if elem_brightness < 80:
                        # 深色线条在深色背景上不可见，反转为亮灰色
                        e.style.color = (200, 200, 200)
                    # 同时确保线宽足够明显
                    if e.style.line_width < 0.5:
                        e.style.line_width = 0.5

                self.add_element(e)
                layers_found.add(e.style.layer_name)
            for ln in layers_found:
                if not self.layer_manager.layer_exists(ln):
                    self.layer_manager.add_layer(ln)

            # 画布自适应：平移并缩放到刚好容纳所有导入元素
            try:
                self._fit_canvas_to_elements(elements, margin=50)
            except Exception:
                pass

            self.viewport.update()
        msg = f"{import_source}导入完成: {len(elements)} 个元素"
        if errors:
            msg += f"\n错误: {len(errors)} 个"
            for e in errors[:3]:
                msg += f"\n- {e}"
        QMessageBox.information(self, "导入结果", msg)

    def _export_dwg(self):
        if not self.elements:
            QMessageBox.information(self, "导出", "画板为空，没有可导出的内容。")
            return
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "导出CAD文件", "",
            "DXF文件 (*.dxf);;DWG文件 (*.dwg)"
        )
        if not file_path:
            return
        try:
            is_dwg = "*.dwg" in selected_filter
            self._write_to_dxf_directly(file_path, is_dwg)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中出现错误:\n{str(e)}")

    def _write_to_dxf_directly(self, file_path: str, is_dwg: bool = False):
        try:
            import ezdxf
        except ImportError:
            txt_path = file_path.rsplit('.', 1)[0] + '.txt'
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write("CAD画板导出数据\n")
                f.write(f"元素数量: {len(self.elements)}\n")
            return
        dxf_path = file_path.rsplit('.', 1)[0] + '.dxf'
        doc = ezdxf.new('R2018')
        msp = doc.modelspace()
        # 统计导出的元素数量（用于提示）
        export_count = 0
        skip_count = 0
        face_count = 0
        for elem in self.elements:
            # 面元素也导出（用户需要在CAD中看到各面视图）
            # 面元素使用原始几何属性导出，layout_offset已通过translate反映到坐标中
            et = elem.element_type.value
            is_face = bool(getattr(elem, 'face_info', {}))
            if is_face:
                face_count += 1
            elem_id = getattr(elem, 'id', '')[:8]
            try:
                if et == '直线':
                    msp.add_line((elem.x1, elem.y1), (elem.x2, elem.y2))
                elif et == '矩形':
                    c = elem.get_corners()
                    pts = [(p[0], p[1]) for p in c] + [(c[0][0], c[0][1])]
                    msp.add_lwpolyline(pts, close=True)
                elif et == '圆':
                    msp.add_circle((elem.cx, elem.cy), elem.radius)
                elif et == '圆弧':
                    msp.add_arc((elem.cx, elem.cy), elem.radius,
                               elem.start_angle, elem.end_angle)
                elif et in ('多段线', '多边形', '样条曲线'):
                    msp.add_lwpolyline([(p[0], p[1]) for p in elem.points],
                                      close=getattr(elem, 'closed', False))
                elif et == '椭圆':
                    pts = elem.sample_points(72)
                    msp.add_lwpolyline([(p[0], p[1]) for p in pts], close=True)
                elif et == '椭圆弧':
                    # 椭圆弧用多段线近似
                    pts = elem.sample_points(72)
                    msp.add_lwpolyline([(p[0], p[1]) for p in pts], close=False)
                elif et == '点':
                    msp.add_point((elem.x, elem.y))
                else:
                    skip_count += 1
                    _write_board_log(f"export skip: unknown type '{et}' id={elem_id}")
                    continue
                export_count += 1
            except Exception as e:
                _write_board_log(f"export element error: {e} type={et} id={elem_id}")
        # 添加画布边界框
        try:
            cs = self.coord_system
            cw = getattr(cs, 'canvas_width', 420)
            ch = getattr(cs, 'canvas_height', 297)
            canvas_pts = [(0, 0), (cw, 0), (cw, ch), (0, ch), (0, 0)]
            msp.add_lwpolyline(canvas_pts, close=True)
            export_count += 1
            _write_board_log(f"export canvas frame: {cw}x{ch}")
        except Exception as e:
            _write_board_log(f"export canvas frame error: {e}")

        _write_board_log(f"export summary: total={len(self.elements)} exported={export_count} faces={face_count} skipped={skip_count}")
        doc.saveas(dxf_path)
        if is_dwg:
            converted, err_msg = convert_dxf_to_dwg(dxf_path, file_path)
            if converted:
                try:
                    os.remove(dxf_path)
                except Exception:
                    pass
                QMessageBox.information(self, "导出成功",
                    f"已成功导出 {export_count} 个元素到:\n{file_path}")
            else:
                QMessageBox.information(self, "导出成功（DXF格式）",
                    f"DWG转换失败({err_msg})，已保存为DXF:\n{dxf_path}\n请检查ODA File Converter是否正确安装")
        else:
            QMessageBox.information(self, "导出成功",
                f"已成功导出 {export_count} 个元素到:\n{dxf_path}")

    def _try_dxf_to_dwg(self, dxf_path: str, dwg_path: str) -> bool:
        import shutil
        import subprocess as sp
        import tempfile
        oda_exe = None
        for name in ["ODAFileConverter", "ODAFileConverter.exe"]:
            oda_exe = shutil.which(name)
            if oda_exe:
                break
        if not oda_exe:
            return False
        temp_in_dir = None
        temp_out_dir = None
        try:
            dxf_basename = os.path.splitext(os.path.basename(dxf_path))[0]
            temp_in_dir = tempfile.mkdtemp(prefix="oda_in_")
            temp_dxf = os.path.join(temp_in_dir, dxf_basename + ".dxf")
            shutil.copy2(dxf_path, temp_dxf)
            temp_out_dir = tempfile.mkdtemp(prefix="oda_out_")
            proc = sp.Popen(
                [oda_exe, temp_in_dir, temp_out_dir, "ACAD2018", "DWG", "0", "1"],
                stdout=sp.PIPE, stderr=sp.PIPE, text=True
            )
            stdout, stderr = proc.communicate(timeout=120)
            # 查找输出的 .dwg 文件
            for f in os.listdir(temp_out_dir):
                if f.lower().endswith('.dwg'):
                    temp_dwg = os.path.join(temp_out_dir, f)
                    final_dwg = dwg_path.rsplit('.', 1)[0] + '.dwg'
                    shutil.copy2(temp_dwg, final_dwg)
                    return True
        except Exception as e:
            _write_board_log(f"dxf_to_dwg error: {e}")
        finally:
            for td in [temp_in_dir, temp_out_dir]:
                if td and os.path.exists(td):
                    try:
                        shutil.rmtree(td)
                    except Exception:
                        pass
        return False

    # ---------- 取消选中 ----------

    def _associate_component(self):
        """将选中的元素关联为一个参数化组件，并生成标准面元素。"""
        selected = [e for e in self.elements if getattr(e, 'selected', False)]
        if not selected:
            QMessageBox.information(self, "组件关联", "请先选中至少一个元素。")
            return

        # 弹出关联对话框
        dlg = QDialog(self)
        dlg.setWindowTitle("组件关联")
        dlg.setMinimumWidth(300)
        layout = QVBoxLayout(dlg)

        form = QFormLayout()

        type_combo = QComboBox()
        type_combo.addItems([
            '直角三棱柱',
            '圆柱',
            '正方体',
            '长方体',
            'SweepBoxComponent',
            'Circle3DComponent',
            'Polygon3DComponent',
            'Arc3DComponent',
            'Ellipse3DComponent',
        ])
        form.addRow("组件类型:", type_combo)

        param_inputs = {}
        param_rows = {}

        def _on_type_changed(text):
            # 清除旧参数
            for row in param_rows.values():
                for i in range(row.count()):
                    widget = row.itemAt(i).widget()
                    if widget:
                        widget.setParent(None)
            param_inputs.clear()
            param_rows.clear()

            # 根据类型显示参数
            if text == '直角三棱柱':
                params = [('直角边1', '直角边1', 100), ('直角边2', '直角边2', 100), ('高度', '高度', 200)]
            elif text == '圆柱':
                params = [('半径', '半径', 50), ('高度', '高度', 100)]
            elif text == '正方体':
                params = [('边长', '边长', 100)]
            elif text == '长方体':
                params = [('长度', '长度', 200), ('宽度', '宽度', 100), ('高度', '高度', 150)]
            elif text == 'SweepBoxComponent':
                params = [('length', '长度', 100), ('width', '宽度', 100), ('z_bottom', 'Z起始', 0), ('z_top', 'Z终止', 100)]
            elif text == 'Circle3DComponent':
                params = [('radius', '半径', 50), ('z_bottom', 'Z起始', 0), ('z_top', 'Z终止', 100)]
            elif text == 'Polygon3DComponent':
                params = [('point_count', '顶点数', 3)]
                for i in range(6):
                    params.append((f'px{i}', f'X{i}', i * 100))
                    params.append((f'py{i}', f'Y{i}', 0))
            elif text == 'Arc3DComponent':
                params = [('radius', '半径', 50), ('start_angle', '起始角', 0), ('end_angle', '终止角', 90), ('z_bottom', 'Z起始', 0), ('z_top', 'Z终止', 100)]
            elif text == 'Ellipse3DComponent':
                params = [('rx', 'X半径', 50), ('ry', 'Y半径', 30), ('z_bottom', 'Z起始', 0), ('z_top', 'Z终止', 100)]
            else:
                params = []

            for key, label, default in params:
                line = QLineEdit(str(default))
                line.setMaximumWidth(100)
                param_inputs[key] = line
                row = QHBoxLayout()
                row.addWidget(QLabel(f"{label}:"))
                row.addWidget(line)
                param_rows[key] = row
                form.addRow(row)

        type_combo.currentTextChanged.connect(_on_type_changed)
        _on_type_changed(type_combo.currentText())

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        ok_btn.clicked.connect(dlg.accept)
        btn_layout.addWidget(ok_btn)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dlg.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        if dlg.exec_() != QDialog.Accepted:
            return

        comp_type = type_combo.currentText()
        params = {}
        for key, line in param_inputs.items():
            try:
                val = float(line.text())
                params[key] = val
            except ValueError:
                pass

        self._save_undo_state()

        # 创建源组件元素
        from utils.component_registry import create_element_from_params
        source_elem = create_element_from_params(params, comp_type)
        if not source_elem:
            QMessageBox.warning(self, "组件关联", f"无法创建 {comp_type} 组件，请检查参数。")
            return

        source_elem.component_type = comp_type
        source_elem.component_params = dict(params)
        self.elements.append(source_elem)

        # 删除原始选中的导入元素（它们已被转化为参数化组件，避免新旧重合）
        original_ids = {e.id for e in selected}
        self.elements = [e for e in self.elements if e.id not in original_ids]

        # 取消所有选中，选中源组件
        for e in self.elements:
            e.selected = False
        source_elem.selected = True
        self._face_component_id = source_elem.id

        # 为源组件生成面元素
        if self._face_group is None:
            from utils.face_mapper import ComponentFaceGroup
            self._face_group = ComponentFaceGroup(self)

        self._generate_faces_for_selected()

        self.viewport.update()
        if self.preview_3d_window:
            self.preview_3d_window.refresh_from_canvas(self.elements)
        self.status_bar.showMessage(f"已关联 {len(selected)} 个元素到 {comp_type}")
        QMessageBox.information(self, "组件关联", f"已创建 {comp_type} 组件并生成面元素。\n源元素ID: {source_elem.id}")

    def _deselect_all(self):
        for e in self.elements:
            e.selected = False
        self.viewport.update()
        self.status_bar.showMessage("已取消所有选中")

    # ---------- BIMBase同步 ----------

    def _test_noumenon_replace(self):
        """综合测试：找到CADBoard组件实例，测试KV可写性和noumenon接口。"""
        import traceback as _tb
        from pyp3d import get_all_instancekey, get_noumenon_from_instancekey, get_noumKV_from_instancekey

        log_lines = []
        def log(msg):
            log_lines.append(str(msg))
            _write_board_log(str(msg))

        try:
            keys = get_all_instancekey()
            log(f"Total instances: {len(keys)}")
            if not keys:
                QMessageBox.information(self, "测试", "BIMBase中没有找到任何组件实例。请先放置一个组件。")
                return

            # 先遍历找到第一个有CADBoard参数的实例
            target_key = None
            target_params = None
            cadboard_keys = {'z_bottom', 'z_top', 'length', 'width', 'radius',
                             'cx', 'cy', 'x', 'y', 'x1', 'y1', 'px0', 'py0',
                             'point_count', 'start_angle', 'end_angle', 'rx', 'ry',
                             'a', 'b', 'h'}
            log("Scanning for CADBoard component...")
            for idx, k in enumerate(keys):
                try:
                    params = get_noumKV_from_instancekey(k)
                    if params and isinstance(params, dict):
                        if set(params.keys()) & cadboard_keys:
                            target_key = k
                            target_params = dict(params)
                            log(f"Found CADBoard instance at index {idx}: params={list(target_params.keys())}")
                            break
                except Exception:
                    pass
                if idx > 200:
                    break

            if target_key is None:
                log("No CADBoard component found in first 200 instances. Please place one first.")
            else:
                # ===== 测试1: get_noumKV_from_instancekey 返回的 dict 是否可写 =====
                log("\n=== Test 1: KV dict writability ===")
                log(f"params type={type(target_params).__name__}")
                log(f"params MRO={[c.__name__ for c in type(target_params).__mro__]}")

                # 找一个数字参数尝试修改
                modified_param = None
                for p, v in target_params.items():
                    if isinstance(v, (int, float)) and v > 0:
                        try:
                            original_v = target_params[p]
                            target_params[p] = original_v + 10
                            log(f"SET params['{p}'] = {target_params[p]} (was {original_v})")
                            modified_param = p
                            break
                        except Exception as e:
                            log(f"SET params['{p}'] failed: {e}")

                if modified_param:
                    # 重新读取验证
                    try:
                        re_read = get_noumKV_from_instancekey(target_key)
                        re_val = re_read.get(modified_param) if re_read else None
                        log(f"RE-READ params['{modified_param}'] = {re_val}")
                        if re_val == target_params[modified_param]:
                            log("WARNING: KV dict might be a live proxy! Value persisted.")
                        else:
                            log("KV dict is a copy; modification did NOT persist in BIMBase.")
                    except Exception as e:
                        log(f"Re-read error: {e}")

                # ===== 测试2: get_noumenon_from_instancekey 的 ParaCmptProperty =====
                log("\n=== Test 2: Noumenon ParaCmptProperty ===")
                noum = get_noumenon_from_instancekey(target_key)
                log(f"noum type={type(noum).__name__}")
                for fld in ('ParaCmptProperty', 'ParaCmptInstance'):
                    try:
                        val = noum.at(fld)
                        log(f"at('{fld}') type={type(val).__name__} val={val}")
                        # 检查是否是嵌套 Noumenon
                        if hasattr(val, 'keys'):
                            sk = list(val.keys())
                            log(f"  {fld}.keys() count={len(sk)}: {sk}")
                        # 检查 .value
                        if hasattr(val, 'value'):
                            log(f"  {fld}.value = {val.value}")
                    except Exception as e:
                        log(f"at('{fld}') error: {e}")

                # ===== 测试3: 检查 place_to =====
                log("\n=== Test 3: place_to existence ===")
                try:
                    import pyp3d
                    if hasattr(pyp3d, 'place_to'):
                        log(f"place_to exists: {pyp3d.place_to}")
                        log(f"place_to type={type(pyp3d.place_to).__name__}")
                        import inspect
                        try:
                            sig = inspect.signature(pyp3d.place_to)
                            log(f"place_to signature: {sig}")
                        except Exception as e:
                            log(f"place_to signature error: {e}")
                    else:
                        log("place_to NOT found in pyp3d")
                except Exception as e:
                    log(f"place_to check error: {e}")

        except Exception as e:
            log(f"Overall test error: {e}")
            log(_tb.format_exc())

        # 写入日志文件并弹窗显示结果
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_noumenon_output.txt')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_lines))
        summary = '\n'.join(log_lines[:60])
        QMessageBox.information(self, "测试 noumenon 结果", summary + f"\n\n完整日志已保存到:\n{out_path}")

    def _sync_to_bimbase(self):
        if not bimbase_sync.is_bimbase_available():
            QMessageBox.warning(self, "同步失败",
                "未在BIMBase环境中运行，无法同步。\n请在BIMBase软件中运行插件。")
            return
        if not self.elements:
            QMessageBox.information(self, "同步", "画板为空，没有可同步的内容。")
            return
        count, errors, replaced = bimbase_sync.sync_to_bimbase(self)
        msg = f"同步到BIMBase完成: {count} 个元素成功"
        if replaced:
            msg += f"\n重新放置: {len(replaced)} 个（来源于BIMBase，已生成新组件）"
        if errors:
            msg += f"\n错误: {len(errors)} 个"
            for e in errors[:5]:
                msg += f"\n- {e}"
        if replaced:
            msg += "\n\n【注意】以下元素来源于BIMBase，已重新放置为新组件："
            for elem in replaced[:5]:
                ct = getattr(elem, 'component_type', '未知')
                msg += f"\n- {ct}"
            msg += "\n\n旧组件仍保留在BIMBase中，请手动删除："
            msg += "\n1. 在BIMBase 3D视图中选中旧组件"
            msg += "\n2. 按 Delete 键删除"
        else:
            if errors:
                msg += "\n\n部分元素自动放置失败，错误信息见上方。"
            else:
                msg += "\n\n元素已尝试自动放置到BIMBase。请在BIMBase 3D视图中检查；"
                msg += "若未显示，请尝试点击“视图”→“缩放全图”或切换到3D视图。"
        QMessageBox.information(self, "同步结果", msg)
        self.status_bar.showMessage(f"已同步 {count} 个元素到BIMBase")

    def _sync_from_bimbase(self):
        if not bimbase_sync.is_bimbase_available():
            QMessageBox.warning(self, "同步失败", "未在BIMBase环境中运行。")
            return
        # v1.5 P3: 增量更新（支持更新已有元素 + 导入新实体）
        self.status_bar.showMessage("正在从BIMBase获取组件，请稍候...")
        try:
            updated, created, errors = bimbase_sync.sync_from_bimbase(self)
        except Exception as e:
            import traceback
            err_detail = traceback.format_exc()
            _write_board_log(f"sync_from_bimbase error: {e}\n{err_detail}")
            QMessageBox.critical(self, "同步失败", f"从BIMBase同步时发生错误:\n{e}\n\n请检查 CADBoard_error.log")
            self.status_bar.showMessage("同步失败")
            return
        self.viewport.update()
        self._update_property_panel()
        
        # 如果当前处于面编辑模式且更新了源元素，重新生成三视图面
        if updated > 0 and getattr(self, '_face_component_id', None):
            try:
                face_cid = self._face_component_id
                source = None
                for e in self.elements:
                    if e.id == face_cid and not getattr(e, 'face_info', {}):
                        source = e
                        break
                if source and source.component_type and source.component_params:
                    faces = self._face_group.generate_faces_for_element(source)
                    if faces:
                        self._face_group.replace_faces(source.id, faces)
                        source.visible = False
                        self.viewport.update()
                        self.status_bar.showMessage("更新完成，三视图已重新生成")
            except Exception as e:
                _write_board_log(f"regenerate faces after sync error: {e}")
        
        msg_parts = []
        if updated > 0:
            msg_parts.append(f"更新 {updated} 个已有元素")
        if created > 0:
            msg_parts.append(f"导入 {created} 个新组件")
        if not msg_parts:
            msg_parts.append("未更新任何元素")
        msg = "从BIMBase更新完成:\n" + "\n".join(f"  • {p}" for p in msg_parts)
        if errors:
            msg += f"\n提示:"
            for e in errors[:5]:
                msg += f"\n  - {e}"
        QMessageBox.information(self, "更新结果", msg)
        self.status_bar.showMessage("更新完成")

    def _show_sync_settings(self):
        """显示BIMBase同步设置对话框"""
        dialog = SyncSettingsDialog(self)
        dialog.exec_()

    def _show_drawing_ai_config(self):
        """显示图纸识别 API 配置对话框"""
        dialog = DrawingAIConfigDialog(self)
        dialog.exec_()

    # ---------- 画布设置 ----------

    def _show_canvas_settings(self):
        dialog = CanvasSettingsDialog(self.coord_system, self)
        if dialog.exec_():
            self.coord_system.update_viewport(self.viewport.width(), self.viewport.height())
            self.viewport.update()

    # ---------- 图层管理 ----------

    def _show_layer_manager(self):
        dialog = LayerManagerDialog(self.layer_manager, self)
        dialog.exec_()
        self.viewport.update()

    def _fit_canvas_to_elements(self, elements=None, margin=50.0):
        """根据元素包围盒自适应画布尺寸并把元素平移到画布内部"""
        if elements is None:
            elements = self.elements
        bounds = []
        for e in elements:
            if getattr(e, 'visible', True) and hasattr(e, 'get_bounds'):
                try:
                    bounds.append(e.get_bounds())
                except Exception:
                    pass
        if not bounds:
            return
        min_x = min(b[0] for b in bounds)
        min_y = min(b[1] for b in bounds)
        max_x = max(b[2] for b in bounds)
        max_y = max(b[3] for b in bounds)
        dx = -min_x + margin
        dy = -min_y + margin
        for e in elements:
            try:
                e.translate(dx, dy)
            except Exception:
                pass
        self.coord_system.canvas_width = max(max_x - min_x + 2 * margin, 100)
        self.coord_system.canvas_height = max(max_y - min_y + 2 * margin, 100)
        self.coord_system.zoom_reset()
        self.coord_system.update_viewport(self.viewport.width(), self.viewport.height())
        self.status_bar.showMessage(
            f"画布已自适应为 {self.coord_system.canvas_width:.0f} x {self.coord_system.canvas_height:.0f} mm"
        )

    # ---------- Phase 3: 面编辑 ----------

    def _generate_faces_for_selected(self):
        """为选中的组件元素生成面元素 —— Phase 3 Enhancement: 弹出模式选择对话框，自动进入面编辑模式"""
        import traceback as _tb
        def _log_face(msg):
            try:
                log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'face_debug.log')
                with open(log_path, 'a', encoding='utf-8') as f:
                    from datetime import datetime
                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
            except Exception:
                pass

        try:
            selected = [e for e in self.elements if getattr(e, 'selected', False)]
            if not selected:
                QMessageBox.information(self, "面编辑", "请先选中一个几何元素。")
                return
            # 使用第一个有component_type且不是面元素的选中元素，或尝试推断
            source = None
            for e in selected:
                if e.component_type and not getattr(e, 'face_info', {}):
                    source = e
                    break
            # 如果没有同步过，尝试从几何类型推断组件参数
            if not source:
                for e in selected:
                    inferred_type, inferred_params = infer_component_params_from_element(e)
                    if inferred_type:
                        e.component_type = inferred_type
                        e.component_params = inferred_params
                        source = e
                        break
            if not source:
                QMessageBox.information(self, "面编辑",
                    "选中的元素不支持面编辑。\n目前支持：矩形、圆、多边形、多段线、直线、圆弧、椭圆、点。")
                return

            # Phase 3 Enhancement: 弹出模式选择对话框
            dialog = FaceGenerateDialog(self, source.component_type)
            if dialog.exec_() != QDialog.Accepted:
                return
            chosen_mode = dialog.get_selected_mode()

            _log_face(f"source type={source.component_type} params_keys={list(source.component_params.keys())[:10]}")

            self._save_undo_state()
            if self._face_group is None:
                self._face_group = ComponentFaceGroup(self)

            # 使用对话框选择的模式
            source.component_params['_face_mode'] = chosen_mode
            _log_face(f"calling generate_faces_for_element mode={chosen_mode}")
            faces = self._face_group.generate_faces_for_element(source, mode=chosen_mode)
            _log_face(f"generate_faces_for_element returned {len(faces) if faces else 0} faces")
            if not faces:
                QMessageBox.warning(self, "面编辑", "无法为该组件生成面元素。")
                return

            # 添加面元素到画板（如果已存在则替换）
            _log_face("calling replace_faces")
            self._face_group.replace_faces(source.id, faces)

            # 隐藏原始源元素，只显示三视图面元素
            source.visible = False

            # 取消选中所有元素，然后只选中第一个面元素（方便属性面板显示）
            for e in self.elements:
                e.selected = False
            face_elems = self._face_group.get_elements_by_component(source.id)
            if face_elems:
                face_elems[0].selected = True

            # Phase 3 Enhancement: 自动进入面编辑模式
            self._enter_face_edit_mode(source.component_type, source.id)

            self._update_property_panel()
            self.viewport.update()
            # 显示每个面元素的位置信息
            info_parts = []
            for fn, elem in faces.items():
                bounds = elem.get_bounds()
                info_parts.append(f"{fn}: ({bounds[0]:.1f},{bounds[1]:.1f})→({bounds[2]:.1f},{bounds[3]:.1f})")
            mode_label = {"三视图": "三视图", "完整": "完整面", "智能": "智能"}.get(chosen_mode, chosen_mode)
            msg = f"已生成 {len(faces)} 个面元素（{mode_label}）。🔶 已进入面编辑模式"
            if info_parts:
                msg += " 位置: " + "; ".join(info_parts[:3])
                if len(info_parts) > 3:
                    msg += f" 等"
            self.status_bar.showMessage(msg)
            _log_face(f"done: {msg}")
        except Exception as e:
            err_detail = _tb.format_exc()
            _log_face(f"CRASH: {e}\n{err_detail}")
            QMessageBox.critical(self, "面编辑错误", f"生成面元素时发生错误:\n{e}\n\n详细错误已记录到 face_debug.log")
            _write_board_log(f"_generate_faces_for_selected crash: {e}\n{err_detail}")

    def _enter_face_edit_mode(self, component_type, component_id):
        """进入面编辑模式：限制交互范围，更新UI状态"""
        self._face_edit_mode = True
        self._face_component_id = component_id
        self._face_filter = 'all'
        if hasattr(self, '_face_filter_combo'):
            self._face_filter_combo.setCurrentText("全部面")
        # 显示toolbar退出按钮
        if hasattr(self, '_exit_face_btn'):
            self._exit_face_btn.setVisible(True)
        # 显示属性面板退出按钮
        if hasattr(self, 'prop_exit_face_btn'):
            self.prop_exit_face_btn.setVisible(True)
        # 禁用非面编辑相关命令（通过命令激活拦截）
        self.status_bar.showMessage(f"🔶 面编辑模式 | 组件: {component_type} | 过滤: 全部面 — 只能编辑面元素")
        _write_board_log(f"Entered face edit mode: component={component_type} id={component_id}")

    def _recognize_pdf_views(self):
        """智能识别导入的PDF三视图并自动创建参数化组件"""
        self.status_bar.showMessage("正在分析三视图布局...")
        try:
            success, msg = auto_associate_from_pdf_views(self)
            if success:
                try:
                    self._fit_canvas_to_elements(margin=50)
                except Exception:
                    pass
                QMessageBox.information(self, "三视图识别", msg)
                self.status_bar.showMessage("三视图识别成功，画布已自适应")
            else:
                QMessageBox.warning(self, "三视图识别", msg)
                self.status_bar.showMessage("三视图识别失败")
        except Exception as e:
            import traceback
            _write_board_log(f"_recognize_pdf_views crash: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "三视图识别错误", f"识别过程中出错:\n{e}")
            self.status_bar.showMessage("三视图识别出错")

    def _recognize_complex_views(self):
        """复杂识别：使用 Qwen-VL 从 PDF/图片识别引桥桥墩等复杂构件"""
        # 未配置 API Key 时提示用户
        if not has_api_key():
            reply = QMessageBox.question(
                self,
                "图纸识别 API 未配置",
                "尚未配置 DashScope API Key，无法使用 AI 识别。\n"
                "是否打开配置对话框？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._show_drawing_ai_config()
            return

        # 选择图纸文件
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图纸文件",
            "",
            "PDF 文件 (*.pdf);;图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)",
        )
        if not file_path:
            return

        self.status_bar.showMessage("正在使用 Qwen-VL 识别图纸，请稍候...")
        try:
            results = recognize_drawing_file(file_path, component_hint='引桥桥墩')
            if not results:
                raise ValueError("未返回任何识别结果")

            result = results[0]
            comp_type = result.get('component_type')
            params = result.get('params') or {}
            if not comp_type:
                raise ValueError(f"无法识别构件类型：{result.get('notes', '')}")

            # 创建源占位元素
            from utils.component_registry import create_element_from_params
            params.setdefault('x', 0.0)
            params.setdefault('y', 0.0)
            params.setdefault('z_bottom', 0.0)
            elem = create_element_from_params(params, comp_type)
            if elem is None:
                raise ValueError(f"无法根据参数创建 {comp_type} 占位元素")

            self.apply_current_layer_style(elem)
            elem.component_type = comp_type
            elem.component_params = dict(params)
            elem.is_3d = True
            elem.pdf_recognized = True
            elem.pdf_anchor_x = float(params.get('x', 0.0))
            elem.pdf_anchor_y = float(params.get('y', 0.0))
            elem.pdf_anchor_z = float(params.get('z_bottom', 0.0))

            self._save_undo_state()
            self.add_element(elem)

            # 选中并生成三视图面元素
            for e in self.elements:
                e.selected = False
            elem.selected = True

            if self._face_group is None:
                self._face_group = ComponentFaceGroup(self)
            elem.component_params['_face_mode'] = '三视图'
            faces = self._face_group.generate_faces_for_element(elem, mode='三视图')
            if not faces:
                raise ValueError("无法生成三视图面元素")
            self._face_group.replace_faces(elem.id, faces)
            elem.visible = False

            face_elems = self._face_group.get_elements_by_component(elem.id)
            if face_elems:
                face_elems[0].selected = True
            self._enter_face_edit_mode(comp_type, elem.id)

            self._update_property_panel()
            self.viewport.update()

            conf = result.get('confidence', 0.0)
            notes = result.get('notes', '')
            msg = f"识别结果：{comp_type}\n置信度：{conf:.2f}"
            if notes:
                msg += f"\n备注：{notes}"
            QMessageBox.information(self, "图纸识别成功", msg)
            self.status_bar.showMessage("图纸识别完成，已进入面编辑模式")

        except Exception as e:
            import traceback
            err = traceback.format_exc()
            _write_board_log(f"_recognize_complex_views crash: {e}\n{err}")
            QMessageBox.critical(self, "图纸识别错误", f"识别过程中出错:\n{e}\n\n已记录到 drawing_recognizer.log")
            self.status_bar.showMessage("图纸识别出错")

    def _exit_face_edit_mode(self):
        """退出面编辑模式：恢复源元素显示，清理面元素，恢复正常交互"""
        import traceback as _tb
        _write_board_log("_exit_face_edit_mode called")
        try:
            if not self._face_edit_mode:
                _write_board_log("_exit_face_edit_mode: not in face edit mode, returning")
                return
            self._save_undo_state()
            cid = self._face_component_id
            
            # 清除所有原始PDF线条的 face_info（恢复为普通元素）
            cleared_count = 0
            for e in self.elements:
                fi = getattr(e, 'face_info', {})
                if fi and fi.get('component_id') == cid and fi.get('is_pdf_original'):
                    # 恢复原始颜色
                    orig_color = fi.get('original_color')
                    if orig_color:
                        e.style.color = tuple(orig_color)
                    # 清除面标记
                    e.face_info = {}
                    e.component_type = ''
                    e.component_params = {}
                    cleared_count += 1
            _write_board_log(f"_exit_face_edit: cleared {cleared_count} pdf original face marks")

            # 恢复被 PDF 识别隐藏的原线条
            restored_count = 0
            for e in self.elements:
                if getattr(e, '_pdf_hidden_original', False):
                    e.visible = True
                    e._pdf_hidden_original = False
                    restored_count += 1
            _write_board_log(f"_exit_face_edit: restored {restored_count} hidden pdf originals")
            
            # 删除由 face_group 生成的标准化面元素（非原始PDF线条）
            if self._face_group and cid:
                try:
                    self._face_group.replace_faces(cid, {})
                    _write_board_log(f"_exit_face_edit: replaced faces for {cid}")
                except Exception as e:
                    _write_board_log(f"_exit_face_edit: replace_faces error: {e}")
            
            # 恢复源元素可见
            if cid:
                for e in self.elements:
                    if e.id == cid:
                        e.visible = True
                        e.selected = True
                        break
            
            # 清除面编辑状态
            self._face_edit_mode = False
            self._face_filter = 'all'
            self._face_component_id = None
            if hasattr(self, '_face_filter_combo'):
                self._face_filter_combo.setCurrentText("全部面")
            # 隐藏toolbar退出按钮
            if hasattr(self, '_exit_face_btn'):
                self._exit_face_btn.setVisible(False)
            # 隐藏属性面板退出按钮
            if hasattr(self, 'prop_exit_face_btn'):
                self.prop_exit_face_btn.setVisible(False)
            self._update_property_panel()
            self.viewport.update()
            self.status_bar.showMessage("已退出面编辑模式，恢复正常编辑")
            _write_board_log("Exited face edit mode successfully")
        except Exception as e:
            _write_board_log(f"_exit_face_edit_mode crash: {e}\n{_tb.format_exc()}")
            QMessageBox.warning(self, "退出面编辑", f"退出时出错: {e}\n已强制恢复正常模式。")
            # 强制恢复
            self._face_edit_mode = False
            self._face_component_id = None
            self._face_filter = 'all'
            if hasattr(self, '_exit_face_btn'):
                self._exit_face_btn.setVisible(False)
            if hasattr(self, 'prop_exit_face_btn'):
                self.prop_exit_face_btn.setVisible(False)

    def _apply_face_changes(self):
        """应用面元素的变化到组件参数，并重新生成所有面。
        简化流程：如果当前选中了某个面元素，自动把属性面板的值应用到它，然后反推参数。"""
        import traceback as _tb
        def _log_face(msg):
            try:
                log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'face_debug.log')
                with open(log_path, 'a', encoding='utf-8') as f:
                    from datetime import datetime
                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [APPLY] {msg}\n")
            except Exception:
                pass

        if not self._face_component_id:
            QMessageBox.information(self, "面编辑", "请先生成面元素。")
            return
        if self._face_group is None:
            self._face_group = ComponentFaceGroup(self)

        self._save_undo_state()

        # 简化：如果当前选中了某个面元素，自动把属性面板的值应用到它
        selected = [e for e in self.elements if getattr(e, 'selected', False)]
        if len(selected) == 1:
            elem = selected[0]
            if hasattr(elem, 'face_info') and elem.face_info:
                face_name = elem.face_info.get('face_name', '')
                _log_face(f"auto-apply props to selected face={face_name}")
                # 在修改前先保存 old_state（确保是修改前的真实状态）
                if not getattr(elem, '_face_old_state', None):
                    from geometry.faces import FaceManager
                    elem._face_old_state = FaceManager.capture_element_state(elem)
                    _log_face(f"  captured old_state: {elem._face_old_state}")
                try:
                    new_width = float(self.prop_inputs['width'].text())
                    if hasattr(elem, 'width'):
                        elem.width = new_width
                        _log_face(f"  width -> {new_width}")
                    elif hasattr(elem, 'radius'):
                        elem.radius = new_width
                        _log_face(f"  radius -> {new_width}")
                except (ValueError, AttributeError):
                    pass
                try:
                    new_height = float(self.prop_inputs['height'].text())
                    if hasattr(elem, 'height'):
                        elem.height = new_height
                        _log_face(f"  height -> {new_height}")
                except (ValueError, AttributeError):
                    pass
                # 给这个面打标记，确保下面一定会处理它
                elem._face_modified = True

        # 获取当前组件的所有面元素
        face_elems = self._face_group.get_elements_by_component(self._face_component_id)
        if not face_elems:
            QMessageBox.information(self, "面编辑", "未找到面元素。")
            return

        # 逐个检测变化并更新参数
        component_type = face_elems[0].component_type
        original_params = dict(face_elems[0].component_params)
        new_params = dict(original_params)
        changed = False

        _log_face(f"start: component_type={component_type} original_params_keys={list(original_params.keys())}")

        # v1.5 P3: 检查是否有原始PDF线条面元素
        has_pdf_original = any(
            getattr(e, 'face_info', {}).get('is_pdf_original') 
            for e in face_elems
        )
        
        if has_pdf_original:
            # 原始PDF线条模式：按面名称分组计算包围盒，从中提取参数
            _log_face("PDF original face mode: computing bounds from grouped elements")
            face_bounds = {}  # face_name -> (min_x, min_y, max_x, max_y)
            for elem in face_elems:
                fn = elem.face_info.get('face_name', '')
                if not fn:
                    continue
                b = elem.get_bounds()
                if fn not in face_bounds:
                    face_bounds[fn] = [b[0], b[1], b[2], b[3]]
                else:
                    fb = face_bounds[fn]
                    fb[0] = min(fb[0], b[0])
                    fb[1] = min(fb[1], b[1])
                    fb[2] = max(fb[2], b[2])
                    fb[3] = max(fb[3], b[3])
            
            _log_face(f"PDF original face bounds: { {k: (v[2]-v[0], v[3]-v[1]) for k,v in face_bounds.items()} }")
            
            # 根据组件类型和包围盒更新参数
            updated = self._update_params_from_pdf_bounds(component_type, face_bounds, new_params)
            if updated != new_params:
                new_params = updated
                changed = True
                _log_face(f"PDF original params updated: {new_params}")
        else:
            # 标准化面元素模式（原有逻辑）
            for elem in face_elems:
                face_name = elem.face_info.get('face_name', '')

                # 优先策略1：如果面元素被 _apply_property_changes 标记为已修改，直接处理
                if getattr(elem, '_face_modified', False):
                    _log_face(f"face={face_name} has _face_modified flag")
                    old_state = getattr(elem, '_face_old_state', {})
                    updated = FaceManager.update_params_from_face(
                        component_type, face_name, elem, old_state, new_params
                    )
                    if updated != new_params:
                        diff_keys = [k for k in updated if updated[k] != new_params.get(k)]
                        _log_face(f"  -> changed keys: {diff_keys}")
                        new_params = updated
                        changed = True
                    elem._face_modified = False
                    elem._face_old_state = None
                    continue

                # 策略2：fallback 状态比较（用于拖拽等直接修改几何的情况）
                expected = FaceManager.generate_face_element(component_type, face_name, original_params)
                if not expected:
                    _log_face(f"face={face_name} skipped: no template")
                    continue

                # 对 expected 也应用相同的 layout_offset
                offset = elem.face_info.get('layout_offset', (0.0, 0.0))
                expected.translate(offset[0], offset[1])

                actual_state = FaceManager.capture_element_state(elem)
                expected_state = FaceManager.capture_element_state(expected)
                is_diff = actual_state != expected_state
                _log_face(f"face={face_name} offset={offset} actual={actual_state} expected={expected_state} diff={is_diff}")

                if is_diff:
                    updated = FaceManager.update_params_from_face(
                        component_type, face_name, elem, expected_state, new_params
                    )
                    if updated != new_params:
                        diff_keys = [k for k in updated if updated[k] != new_params.get(k)]
                        _log_face(f"  -> changed keys: {diff_keys}")
                        new_params = updated
                        changed = True
                    else:
                        _log_face(f"  -> updater returned same params")

        if not changed:
            _log_face("no changes detected, returning")
            self.status_bar.showMessage("面元素无变化")
            return

        _log_face(f"final new_params: { {k: new_params[k] for k in new_params if new_params[k] != original_params.get(k)} }")

        # 同时更新原始源元素的component_params和高度信息
        source_elem = None
        for e in self.elements:
            if e.id == self._face_component_id:
                e.component_params = dict(new_params)
                source_elem = e
                break

        if has_pdf_original:
            # v1.5 P3: 原始PDF线条模式——不重新生成标准化面元素
            # 只更新所有面元素的 component_params，保留原始线条
            for e in self.elements:
                if getattr(e, 'face_info', {}).get('component_id') == self._face_component_id:
                    e.component_params = dict(new_params)
            _log_face("PDF original mode: updated component_params on all face elements, no regeneration")
        else:
            # 标准化面元素模式：重新生成所有面元素
            self._face_group.apply_params_and_regenerate(self._face_component_id, new_params)

        # 更新源元素的3D高度显示（用于3D预览）
        if source_elem:
            if source_elem.component_type == '直角三棱柱':
                if '高度' in new_params:
                    source_elem.z_end = source_elem.z_start + float(new_params['高度'])
            elif source_elem.component_type == '圆柱':
                if '高度' in new_params:
                    source_elem.z_end = source_elem.z_start + float(new_params['高度'])
            elif source_elem.component_type == '正方体':
                if '边长' in new_params:
                    source_elem.z_end = source_elem.z_start + float(new_params['边长'])
            elif source_elem.component_type == '长方体':
                if '高度' in new_params:
                    source_elem.z_end = source_elem.z_start + float(new_params['高度'])
            elif source_elem.component_type == '引桥桥墩':
                pier_h = float(new_params.get('墩高', 1200)) + float(new_params.get('盖梁总高', 300))
                source_elem.z_end = source_elem.z_start + pier_h
            else:
                z_bottom = new_params.get('z_bottom') or new_params.get('z1') or new_params.get('z', 0)
                z_top = new_params.get('z_top') or new_params.get('z2') or new_params.get('z', 0)
                if z_bottom is not None:
                    source_elem.z_start = float(z_bottom)
                if z_top is not None:
                    source_elem.z_end = float(z_top)

        # 同步更新到 BIMBase（如果该组件已注册，或来源于BIMBase）
        if source_elem:
            try:
                registry = get_registry()
                info = registry.get(source_elem.id)
                if info and info.get('instance'):
                    # 方式1：通过已注册的 Python Component 实例更新（画板独立创建并 place 过的）
                    inst = info['instance']
                    for k, v in new_params.items():
                        if k in inst:
                            try:
                                inst[k] = v
                            except Exception:
                                pass
                    try:
                        inst.replace()
                        _log_face(f"BIMBase replace() called for {source_elem.id}")
                    except Exception as e:
                        _write_board_log(f"inst.replace() error: {e}")
                        _log_face(f"BIMBase replace() error: {e}")
                elif getattr(source_elem, '_bimbase_datakey', None) is not None:
                    # 方式2：元素来源于BIMBase。由于SDK限制，无法直接修改已有实例，跳过。
                    _log_face(f"BIMBase sync skipped: element {source_elem.id} originates from BIMBase (no SDK API to update existing component).")
                    _write_board_log(f"面修改已应用到画板，但元素 {source_elem.id} 来源于BIMBase，无法自动同步回BIMBase。请在BIMBase属性面板中手动修改参数。")
                else:
                    _write_board_log(f"BIMBase sync skipped: no instance or datakey for {source_elem.id}")
                    _log_face(f"BIMBase sync skipped: no instance or datakey for {source_elem.id}")
            except Exception as e:
                err = _tb.format_exc()
                _write_board_log(f"BIMBase sync from face edit error: {e}\n{err}")
                _log_face(f"BIMBase sync error: {e}")

        self.viewport.update()
        if self.preview_3d_window:
            self.preview_3d_window.refresh_from_canvas(self.elements)
        self.status_bar.showMessage("面修改已应用，组件参数已更新")

    def _update_params_from_pdf_bounds(self, component_type, face_bounds, params):
        """
        v1.5 P3: 根据原始PDF线条的包围盒更新组件参数。
        face_bounds: {face_name: [min_x, min_y, max_x, max_y]}
        返回: 更新后的参数字典
        """
        new_params = dict(params)
        
        if component_type == '长方体':
            top = face_bounds.get('top')
            front = face_bounds.get('front')
            left = face_bounds.get('left')
            if top:
                new_params['长度'] = round(top[2] - top[0], 1)
                new_params['宽度'] = round(top[3] - top[1], 1)
            if front:
                new_params['长度'] = round(front[2] - front[0], 1)
                new_params['高度'] = round(front[3] - front[1], 1)
            if left:
                new_params['宽度'] = round(left[2] - left[0], 1)
                new_params['高度'] = round(left[3] - left[1], 1)
        
        elif component_type == '正方体':
            # 取所有面的最大边长
            max_size = 0
            for fb in face_bounds.values():
                size = max(fb[2] - fb[0], fb[3] - fb[1])
                max_size = max(max_size, size)
            if max_size > 0:
                new_params['边长'] = round(max_size, 1)
        
        elif component_type == '圆柱':
            top = face_bounds.get('top')
            front = face_bounds.get('front')
            left = face_bounds.get('left')
            if top:
                # 俯视图是圆的外接正方形，直径 = 边长
                d = max(top[2] - top[0], top[3] - top[1])
                new_params['半径'] = round(d / 2, 1)
            if front:
                d = front[2] - front[0]
                new_params['半径'] = round(d / 2, 1)
                new_params['高度'] = round(front[3] - front[1], 1)
            if left:
                new_params['高度'] = round(left[3] - left[1], 1)
        
        elif component_type == '直角三棱柱':
            top = face_bounds.get('top')
            if top:
                new_params['直角边1'] = round(top[2] - top[0], 1)
                new_params['直角边2'] = round(top[3] - top[1], 1)
            for fn in ['side_a', 'front']:
                fb = face_bounds.get(fn)
                if fb:
                    new_params['高度'] = round(fb[3] - fb[1], 1)
                    break
        
        return new_params

    def _on_face_filter_changed(self, text):
        """面过滤下拉框变化 —— Phase 3 Enhancement: 更新状态栏显示当前模式"""
        mapping = {
            "全部面": "all",
            "顶面": "top",
            "前视图": "front",
            "左视图": "left",
            "侧面": "side",
            "侧面a": "side_a",
            "侧面b": "side_b",
            "斜面": "side_hypotenuse",
        }
        # 对于未知名称（如 side0, side1...），直接使用原名
        self._face_filter = mapping.get(text, text)
        self.viewport.update()
        if self._face_edit_mode and self._face_component_id:
            # 查找组件类型
            comp_type = ""
            for e in self.elements:
                if e.id == self._face_component_id and not getattr(e, 'face_info', {}):
                    comp_type = getattr(e, 'component_type', '')
                    break
            self.status_bar.showMessage(f"🔶 面编辑模式 | 组件: {comp_type} | 过滤: {text}")
        else:
            self.status_bar.showMessage(f"面过滤: {text}")

    # ---------- 吸附设置 (v1.5 P0: 增加异常保护防闪退) ----------

    def _show_snap_settings(self):
        """显示吸附设置对话框 - 增加异常保护防止BIMBase内嵌环境闪退"""
        try:
            dialog = SnapSettingsDialog(self.snap_system, self)
            dialog.exec_()
        except Exception as e:
            _write_board_log(f"_show_snap_settings error: {traceback.format_exc()}")
            self.status_bar.showMessage(f"吸附设置打开失败: {str(e)}")
            QMessageBox.warning(self, "吸附设置",
                f"无法打开吸附设置对话框。\n错误: {str(e)}\n\n"
                "这可能与BIMBase内嵌环境兼容性有关。")

    # ---------- 环境配置 ----------

    def _show_env_config(self):
        dialog = EnvConfigDialog(self)
        dialog.exec_()

    # ---------- 快捷键帮助 ----------

    def _toggle_ai_panel(self):
        """切换AI助手面板的显示/隐藏"""
        if self.ai_panel.isVisible():
            self.ai_panel.hide()
            self.status_bar.showMessage("AI助手已隐藏")
        else:
            self.ai_panel.show()
            self.status_bar.showMessage("AI助手已显示")

    def _show_3d_preview(self):
        """打开3D预览窗口"""
        try:
            if Preview3DWindow is None:
                QMessageBox.warning(self, "3D预览", "3D预览模块未加载。")
                return
            if self.preview_3d_window is None:
                self.preview_3d_window = Preview3DWindow(canvas_widget=self.viewport, parent=self)
            self.preview_3d_window.show()
            self.preview_3d_window.raise_()
            self.preview_3d_window.activateWindow()
            self.preview_3d_window.refresh_from_canvas(self.elements)
            self.status_bar.showMessage("3D预览已打开")
        except Exception as e:
            _write_board_log(f"_show_3d_preview error: {traceback.format_exc()}")
            QMessageBox.warning(self, "3D预览", f"打开3D预览失败:\n{str(e)}")

    def _show_shortcuts(self):
        shortcuts_text = """
        <h3>CAD画板 快捷键</h3>
        <table border="1" cellpadding="5">
        <tr><th>按键</th><th>命令</th></tr>
        <tr><td><b>L</b></td><td>直线</td></tr>
        <tr><td><b>C</b></td><td>圆</td></tr>
        <tr><td><b>A</b></td><td>圆弧</td></tr>
        <tr><td><b>REC</b></td><td>矩形</td></tr>
        <tr><td><b>PL</b></td><td>多段线</td></tr>
        <tr><td><b>POL</b></td><td>多边形</td></tr>
        <tr><td><b>EL</b></td><td>椭圆</td></tr>
        <tr><td><b>SPL</b></td><td>样条曲线</td></tr>
        <tr><td><b>PO</b></td><td>点</td></tr>
        <tr><td><b>E</b></td><td>删除</td></tr>
        <tr><td><b>CO</b></td><td>复制</td></tr>
        <tr><td><b>MI</b></td><td>镜像</td></tr>
        <tr><td><b>O</b></td><td>偏移</td></tr>
        <tr><td><b>AR</b></td><td>阵列</td></tr>
        <tr><td><b>M</b></td><td>移动</td></tr>
        <tr><td><b>RO</b></td><td>旋转</td></tr>
        <tr><td><b>SC</b></td><td>缩放</td></tr>
        <tr><td><b>S</b></td><td>拉伸</td></tr>
        <tr><td><b>TR</b></td><td>修剪</td></tr>
        <tr><td><b>EX</b></td><td>延伸</td></tr>
        <tr><td><b>BR</b></td><td>打断</td></tr>
        <tr><td><b>J</b></td><td>合并</td></tr>
        <tr><td><b>CHA</b></td><td>倒斜角</td></tr>
        <tr><td><b>F</b></td><td>圆角</td></tr>
        <tr><td><b>X</b></td><td>分解</td></tr>
        <tr><td><b>DIV</b></td><td>定数等分</td></tr>
        <tr><td><b>ME</b></td><td>定距等分</td></tr>
        <tr><td><b>ESC</b></td><td>取消/回到选择</td></tr>
        <tr><td><b>Ctrl+Z</b></td><td>撤销</td></tr>
        <tr><td><b>Ctrl+Shift+Z</b></td><td>重做</td></tr>
        </table>
        <p><b>视图操作:</b> 滚轮缩放 | 中键拖拽平移</p>
        <p><b>命令行:</b> 回车确认输入 | 支持坐标(100,200)、长度、角度</p>
        """
        QMessageBox.information(self, "快捷键帮助", shortcuts_text)

    def closeEvent(self, event):
        if self.elements:
            reply = QMessageBox.question(
                self, "确认关闭",
                "画板中有未导出的内容，是否确认关闭？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
        if self.current_command:
            try:
                self.current_command.deactivate()
            except Exception:
                pass
        event.accept()


# ============================================================
# 画布设置对话框
# ============================================================

class CanvasSettingsDialog(QDialog):
    def __init__(self, coord_system, parent=None):
        super().__init__(parent)
        self.coord_system = coord_system
        self.setWindowTitle("画布尺寸设置")
        self.setMinimumSize(300, 200)
        from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QLabel
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(10, 10000)
        self.width_spin.setValue(coord_system.canvas_width)
        self.width_spin.setSuffix(" mm")
        form.addRow("宽度:", self.width_spin)
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(10, 10000)
        self.height_spin.setValue(coord_system.canvas_height)
        self.height_spin.setSuffix(" mm")
        form.addRow("高度:", self.height_spin)
        layout.addLayout(form)
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._apply)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _apply(self):
        self.coord_system.canvas_width = self.width_spin.value()
        self.coord_system.canvas_height = self.height_spin.value()
        self.accept()


# ============================================================
# 图层管理对话框（简化版 - 避免QTableWidget兼容性问题）
# ============================================================

class LayerManagerDialog(QDialog):
    def __init__(self, layer_manager, parent=None):
        super().__init__(parent)
        self.layer_manager = layer_manager
        self.setWindowTitle("图层管理")
        self.setMinimumSize(450, 400)
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>图层列表</b> 蓝色=当前图层 | 灰色=不可见"))

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        # 选中图层信息显示
        info_layout = QHBoxLayout()
        self.name_label = QLabel("名称: -")
        self.color_btn = QPushButton("颜色")
        self.color_btn.clicked.connect(self._set_color)
        self.width_btn = QPushButton("线宽")
        self.width_btn.clicked.connect(self._set_width)
        self.vis_btn = QPushButton("切换可见")
        self.vis_btn.clicked.connect(self._toggle_visible)
        self.lock_btn = QPushButton("切换锁定")
        self.lock_btn.clicked.connect(self._toggle_locked)
        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.color_btn)
        info_layout.addWidget(self.width_btn)
        info_layout.addWidget(self.vis_btn)
        info_layout.addWidget(self.lock_btn)
        layout.addLayout(info_layout)

        btn_layout = QHBoxLayout()
        self.current_btn = QPushButton("设为当前图层")
        self.current_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; font-weight: bold; }")
        self.current_btn.clicked.connect(self._set_current)
        add_btn = QPushButton("新建图层")
        add_btn.clicked.connect(self._add_layer)
        del_btn = QPushButton("删除图层")
        del_btn.clicked.connect(self._delete_layer)
        btn_layout.addWidget(self.current_btn)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(del_btn)
        layout.addLayout(btn_layout)

        self.current_label = QLabel(f"<b>当前图层:</b> {self.layer_manager.get_current_layer()}")
        layout.addWidget(self.current_label)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _refresh_list(self):
        self.list_widget.clear()
        for layer in self.layer_manager.get_all_layers():
            name = layer.name
            vis = "可见" if layer.visible else "不可见"
            lock = " 锁定" if layer.locked else ""
            r, g, b = layer.color
            color_hex = f"RGB({r},{g},{b})"
            item = QListWidgetItem(f"{name} | {vis}{lock} | 线宽{layer.line_width}mm | {color_hex}")
            item.setData(Qt.UserRole, name)
            # 当前图层高亮
            if name == self.layer_manager.get_current_layer():
                item.setBackground(QColor(200, 230, 255))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            # 不可见图层灰色
            if not layer.visible:
                item.setForeground(QColor(128, 128, 128))
            self.list_widget.addItem(item)
        self.current_label.setText(f"<b>当前图层:</b> {self.layer_manager.get_current_layer()}")

    def _on_item_clicked(self, item):
        name = item.data(Qt.UserRole)
        layer = self.layer_manager.get_layer(name)
        if layer:
            self.name_label.setText(f"名称: {name}")

    def _get_selected_name(self):
        item = self.list_widget.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def _set_current(self):
        name = self._get_selected_name()
        if name and self.layer_manager.set_current_layer(name):
            self._refresh_list()
            if hasattr(self.parent(), 'viewport'):
                self.parent().viewport.update()

    def _add_layer(self):
        name, ok = QInputDialog.getText(self, "新建图层", "图层名称:")
        if ok and name:
            if self.layer_manager.add_layer(name):
                self._refresh_list()
            else:
                QMessageBox.warning(self, "错误", "图层已存在或名称无效")

    def _delete_layer(self):
        name = self._get_selected_name()
        if name and self.layer_manager.remove_layer(name):
            self._refresh_list()

    def _set_color(self):
        name = self._get_selected_name()
        if not name:
            return
        layer = self.layer_manager.get_layer(name)
        if layer:
            color = QColorDialog.getColor(QColor(*layer.color), self, f"设置 [{name}] 的颜色")
            if color.isValid():
                self.layer_manager.set_color(name, (color.red(), color.green(), color.blue()))
                self._refresh_list()
                if hasattr(self.parent(), 'viewport'):
                    self.parent().viewport.update()

    def _set_width(self):
        name = self._get_selected_name()
        if not name:
            return
        layer = self.layer_manager.get_layer(name)
        if layer:
            width, ok = QInputDialog.getDouble(self, "设置线宽", f"[{name}] 线宽(mm):", layer.line_width, 0.01, 10.0, 2)
            if ok:
                self.layer_manager.set_line_width(name, width)
                self._refresh_list()

    def _toggle_visible(self):
        name = self._get_selected_name()
        if name:
            layer = self.layer_manager.get_layer(name)
            if layer:
                self.layer_manager.set_visible(name, not layer.visible)
                self._refresh_list()
                if hasattr(self.parent(), 'viewport'):
                    self.parent().viewport.update()

    def _toggle_locked(self):
        name = self._get_selected_name()
        if name:
            layer = self.layer_manager.get_layer(name)
            if layer:
                self.layer_manager.set_locked(name, not layer.locked)
                self._refresh_list()


# ============================================================
# 吸附设置对话框（简化版 - 避免QGroupBox兼容性问题）
# ============================================================

class SnapSettingsDialog(QDialog):
    def __init__(self, snap_system, parent=None):
        super().__init__(parent)
        self.snap_system = snap_system
        self.setWindowTitle("吸附设置")
        self.setMinimumSize(320, 300)
        layout = QVBoxLayout(self)

        self.enabled_cb = QCheckBox("启用吸附总开关")
        self.enabled_cb.setChecked(snap_system.enabled)
        layout.addWidget(self.enabled_cb)

        layout.addWidget(QLabel("<b>对象吸附（优先级: 端点 > 交点 > 中心点 > 垂足）</b>"))
        self.endpoint_cb = QCheckBox("端点吸附")
        self.endpoint_cb.setChecked(snap_system.endpoint_snap)
        layout.addWidget(self.endpoint_cb)
        self.intersection_cb = QCheckBox("交点吸附")
        self.intersection_cb.setChecked(snap_system.intersection_snap)
        layout.addWidget(self.intersection_cb)
        self.center_cb = QCheckBox("中心点吸附（圆心/矩形中心/多边形重心）")
        self.center_cb.setChecked(snap_system.center_snap)
        layout.addWidget(self.center_cb)
        self.perpendicular_cb = QCheckBox("垂足吸附（点到线段的垂足）")
        self.perpendicular_cb.setChecked(snap_system.perpendicular_snap)
        layout.addWidget(self.perpendicular_cb)

        layout.addWidget(QLabel("<b>网格吸附</b>"))
        self.grid_cb = QCheckBox("网格吸附")
        self.grid_cb.setChecked(snap_system.grid_snap)
        layout.addWidget(self.grid_cb)
        layout.addWidget(QLabel("网格间距 (mm):"))
        self.spacing_edit = QLineEdit(str(snap_system.snap_size))
        layout.addWidget(self.spacing_edit)

        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self._apply)
        layout.addWidget(ok_btn)

    def _apply(self):
        self.snap_system.enabled = self.enabled_cb.isChecked()
        self.snap_system.endpoint_snap = self.endpoint_cb.isChecked()
        self.snap_system.intersection_snap = self.intersection_cb.isChecked()
        self.snap_system.center_snap = self.center_cb.isChecked()
        self.snap_system.perpendicular_snap = self.perpendicular_cb.isChecked()
        self.snap_system.grid_snap = self.grid_cb.isChecked()
        try:
            self.snap_system.snap_size = float(self.spacing_edit.text())
        except ValueError:
            pass
        self.accept()


# ============================================================
# 环境配置对话框
# ============================================================

# ============================================================
# BIMBase同步设置对话框 - v1.5 P3
# ============================================================

class SyncSettingsDialog(QDialog):
    """BIMBase同步设置对话框"""

    CONFIG_FILE = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BIMBase同步设置")
        self.setMinimumSize(400, 250)
        import os
        self.CONFIG_FILE = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "sync_config.json"
        )
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.auto_sync_cb = QCheckBox("启用自动同步(元素变动后自动同步到BIMBase)")
        self.auto_sync_cb.setChecked(False)
        form.addRow(self.auto_sync_cb)

        self.confirm_sync_cb = QCheckBox("同步前显示确认对话框")
        self.confirm_sync_cb.setChecked(True)
        form.addRow(self.confirm_sync_cb)

        self.show_report_cb = QCheckBox("同步后显示结果报告")
        self.show_report_cb.setChecked(True)
        form.addRow(self.show_report_cb)

        info = QLabel(
            "<b>同步说明:</b><br>"
            "- 同步到BIMBase: 将当前画板的所有元素转为参数化组件<br>"
            "- 从BIMBase更新: 从BIMBase读取参数更新画板(增量更新)<br>"
            "- 3D实体: 闭合截面用Section+place()生成拉伸体，球体用圆截面表示<br>"
            "- 建议在完成一组操作后手动同步，而非自动同步"
        )
        info.setWordWrap(True)
        form.addRow(info)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        save_btn.clicked.connect(self._save_config)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    self.auto_sync_cb.setChecked(cfg.get('auto_sync', False))
                    self.confirm_sync_cb.setChecked(cfg.get('confirm_sync', True))
                    self.show_report_cb.setChecked(cfg.get('show_report', True))
            except Exception:
                pass

    def _save_config(self):
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'auto_sync': self.auto_sync_cb.isChecked(),
                    'confirm_sync': self.confirm_sync_cb.isChecked(),
                    'show_report': self.show_report_cb.isChecked(),
                }, f, ensure_ascii=False)
            QMessageBox.information(self, "保存成功", "同步设置已保存。")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存: {e}")

    @classmethod
    def should_confirm(cls):
        import os
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sync_config.json")
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get('confirm_sync', True)
            except Exception:
                pass
        return True


class EnvConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置开发环境")
        self.setMinimumSize(600, 450)
        self._setup_ui()

    def _setup_ui(self):
        from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton
        layout = QVBoxLayout(self)
        info_label = QLabel(
            "<b>一键配置CAD画板开发环境</b><br>"
            "1. 检测BIMBase安装路径<br>"
            "2. 配置VSCode的Python解释器和代码补全<br>"
            "3. 安装所需的Python依赖包"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.Monospace)
        self.log_text.setFont(font)
        layout.addWidget(self.log_text, 1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        self.button_box = QDialogButtonBox()
        self.start_btn = self.button_box.addButton("开始配置", QDialogButtonBox.ActionRole)
        self.close_btn = self.button_box.addButton("关闭", QDialogButtonBox.RejectRole)
        self.start_btn.clicked.connect(self._start_configuration)
        self.close_btn.clicked.connect(self.reject)
        layout.addWidget(self.button_box)

    def _log(self, message: str):
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        QApplication.processEvents()

    def _start_configuration(self):
        self.start_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_text.clear()
        try:
            result = run_environment_configuration(self._log)
            if result and result.get('success'):
                self._log("")
                self._log("=" * 50)
                self._log("环境配置全部完成！")
                self._log("=" * 50)
                self.start_btn.setText("配置完成")
            else:
                self._log("")
                self._log("=" * 50)
                self._log("环境配置部分完成")
                self._log("=" * 50)
                self.start_btn.setEnabled(True)
                self.start_btn.setText("重试")
        except Exception as e:
            self._log(f"配置异常: {str(e)}")


# ============================================================
# Phase 3 Enhancement: 面生成模式选择对话框
# ============================================================

class FaceGenerateDialog(QDialog):
    """面生成模式选择对话框 —— 让用户明确选择生成三视图还是完整面"""

    def __init__(self, parent=None, component_type: str = ""):
        super().__init__(parent)
        self.setWindowTitle(f"生成面元素 — {component_type}")
        self.setMinimumSize(350, 220)
        self._selected_mode = "三视图"
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(
            "<b>请选择面生成模式：</b><br>"
            "<small>生成后将进入面编辑模式，只能修改面参数</small>"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # 模式选择按钮组
        self._btn_group = []
        modes = [
            ("三视图", "生成3个标准投影面（俯视图/主视图/左视图）", "三视图"),
            ("完整", "生成组件的所有面（可能包含底面/后视图/斜面等）", "完整"),
            ("智能", "根据组件类型自动选择最合适的模式", "智能"),
        ]
        for label, desc, mode_val in modes:
            btn = QPushButton(f"<b>{label}</b><br><small>{desc}</small>")
            btn.setStyleSheet(
                "QPushButton { text-align: left; padding: 8px; border: 2px solid #ccc; border-radius: 6px; }"
                "QPushButton:checked { border: 2px solid #E65100; background-color: #FFF3E0; }"
            )
            btn.setCheckable(True)
            btn.setProperty("mode", mode_val)
            btn.clicked.connect(lambda checked, m=mode_val, b=btn: self._on_mode_clicked(m, b))
            self._btn_group.append(btn)
            layout.addWidget(btn)

        # 默认选中三视图
        if self._btn_group:
            self._btn_group[0].setChecked(True)
            self._selected_mode = "三视图"

        # 确定/取消按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定生成")
        ok_btn.setStyleSheet("QPushButton { background-color: #E65100; color: white; font-weight: bold; padding: 6px 16px; }")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _on_mode_clicked(self, mode, clicked_btn):
        self._selected_mode = mode
        for btn in self._btn_group:
            if btn != clicked_btn:
                btn.setChecked(False)
        clicked_btn.setChecked(True)

    def get_selected_mode(self):
        return self._selected_mode
