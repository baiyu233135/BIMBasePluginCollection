# -*- coding: utf-8 -*-
"""
可交互病害框图片控件

在原图上以矢量叠加方式绘制病害框（不再烘焙进图片），支持：
- 点击红框：选中（高亮为黄色），发射 boxClicked
- 在空白处拖拽：框选新病害区域，发射 boxDrawn（照片像素坐标）
- 选中框后按 Delete：发射 deleteRequested

坐标约定：照片左上角为原点 (0,0)，单位像素。
"""

from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, pyqtSignal, QRect


class ImageBoxLabel(QLabel):
    """可交互的病害框图片显示控件"""

    boxClicked = pyqtSignal(int)          # 点击了第几个框
    boxDrawn = pyqtSignal(tuple)          # 框选出新区块 (x1,y1,x2,y2) 照片像素坐标
    deleteRequested = pyqtSignal(int)     # 选中框上按了 Delete 键
    selectionCleared = pyqtSignal()       # 取消选中（再点一次选中的框 / 单击空白处）
    calibrationDrawn = pyqtSignal(tuple)  # 标定模式下拖出参照物框 (x1,y1,x2,y2) 照片像素坐标

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#1e1e1e;color:#888;font-size:16px;")
        self.setMinimumSize(500, 350)
        self.setFocusPolicy(Qt.StrongFocus)
        self._pixmap = None
        self._boxes = []          # [(x1,y1,x2,y2,label)] 照片像素坐标
        self._selected = -1
        self._drag_start = None   # 照片像素坐标
        self._drag_cur = None
        self._calibration_mode = False   # 参照物标定模式：拖拽结果走 calibrationDrawn
        self._calibration_box = None     # 已标定的参照物框 (x1,y1,x2,y2)，青色绘制

    # ---------- 标定模式 ----------

    def set_calibration_mode(self, enabled: bool):
        """进入/退出参照物标定模式。标定模式下拖拽不选中框、不产生病害记录。"""
        self._calibration_mode = bool(enabled)
        if not self._calibration_mode:
            self._drag_start = None
            self._drag_cur = None
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)
        self.update()

    def get_calibration_mode(self):
        return self._calibration_mode

    def set_calibration_box(self, bbox):
        """设置/清除已标定的参照物框（照片像素坐标，None 清除），青色持久绘制"""
        self._calibration_box = tuple(bbox) if bbox else None
        self.update()

    # ---------- 数据接口 ----------

    def set_photo(self, path):
        """加载原图并清空所有框"""
        pix = QPixmap(path)
        self._pixmap = pix if not pix.isNull() else None
        self._boxes = []
        self._selected = -1
        self._drag_start = None
        self._drag_cur = None
        self._calibration_box = None   # 换照片后旧的参照物框不再适用
        if self._pixmap is None:
            self.setText("无法加载照片")
        else:
            self.setText("")
        self.update()

    def set_boxes(self, boxes):
        """设置病害框列表 [(x1,y1,x2,y2,label), ...]（照片像素坐标）"""
        self._boxes = list(boxes)
        if self._selected >= len(self._boxes):
            self._selected = -1
        self.update()

    def set_selected(self, idx):
        """高亮第几个框（-1 取消）"""
        self._selected = idx if 0 <= idx < len(self._boxes) else -1
        self.update()

    def get_selected(self):
        return self._selected

    # ---------- 坐标换算 ----------

    def _view_transform(self):
        """返回 (scale, offset_x, offset_y)；无图片返回 None"""
        if self._pixmap is None:
            return None
        pw, ph = self._pixmap.width(), self._pixmap.height()
        if pw <= 0 or ph <= 0:
            return None
        scale = min((self.width() - 20) / pw, (self.height() - 20) / ph)
        scale = max(scale, 1e-6)
        ox = (self.width() - pw * scale) / 2.0
        oy = (self.height() - ph * scale) / 2.0
        return scale, ox, oy

    def _to_photo(self, pos):
        """控件坐标 → 照片像素坐标"""
        t = self._view_transform()
        if t is None:
            return None
        scale, ox, oy = t
        return (pos.x() - ox) / scale, (pos.y() - oy) / scale

    # ---------- 绘制 ----------

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._pixmap is None:
            return
        t = self._view_transform()
        if t is None:
            return
        scale, ox, oy = t

        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(
            int(ox), int(oy),
            self._pixmap.scaled(
                int(self._pixmap.width() * scale),
                int(self._pixmap.height() * scale),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

        font = p.font()
        font.setPointSize(9)
        font.setBold(True)
        p.setFont(font)

        for i, box in enumerate(self._boxes):
            x1, y1, x2, y2, label = box[:5]
            # 第 6 个元素为可选的框颜色 (r,g,b)，缺省红色；选中态始终黄色高亮
            box_color = box[5] if len(box) > 5 else (255, 0, 0)
            selected = (i == self._selected)
            color = QColor(255, 220, 0) if selected else QColor(*box_color)
            pen = QPen(color, 3 if selected else 2)
            p.setPen(pen)
            r = QRect(int(ox + x1 * scale), int(oy + y1 * scale),
                      max(1, int((x2 - x1) * scale)), max(1, int((y2 - y1) * scale)))
            p.drawRect(r)
            # 标签
            metrics = p.fontMetrics()
            tw = metrics.width(label) + 8
            th = metrics.height() + 4
            label_rect = QRect(r.left(), r.top() - th, tw, th)
            p.fillRect(label_rect, color)
            p.setPen(QColor(255, 255, 255))
            p.drawText(label_rect, Qt.AlignCenter, label)

        # 已标定的参照物框（青色实线 + 标签，区别于病害红框）
        if self._calibration_box is not None:
            cx1, cy1, cx2, cy2 = self._calibration_box
            cal_color = QColor(0, 200, 255)
            p.setPen(QPen(cal_color, 3))
            cr = QRect(int(ox + cx1 * scale), int(oy + cy1 * scale),
                       max(1, int((cx2 - cx1) * scale)), max(1, int((cy2 - cy1) * scale)))
            p.drawRect(cr)
            metrics = p.fontMetrics()
            cal_label = "参照物标定"
            tw = metrics.width(cal_label) + 8
            th = metrics.height() + 4
            label_rect = QRect(cr.left(), cr.bottom() + 2, tw, th)
            p.fillRect(label_rect, cal_color)
            p.setPen(QColor(255, 255, 255))
            p.drawText(label_rect, Qt.AlignCenter, cal_label)

        # 正在拖拽的框（青色虚线；标定模式下为实线）
        if self._drag_start is not None and self._drag_cur is not None:
            x1, y1 = self._drag_start
            x2, y2 = self._drag_cur
            r = QRect(int(ox + min(x1, x2) * scale), int(oy + min(y1, y2) * scale),
                      max(1, int(abs(x2 - x1) * scale)), max(1, int(abs(y2 - y1) * scale)))
            pen_style = Qt.SolidLine if self._calibration_mode else Qt.DashLine
            p.setPen(QPen(QColor(0, 200, 255), 2, pen_style))
            p.drawRect(r)

        p.end()

    # ---------- 鼠标/键盘 ----------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._pixmap is not None:
            pt = self._to_photo(event.pos())
            if pt is not None:
                if self._calibration_mode:
                    # 标定模式：始终开始拖拽参照物框，不做框选/点选联动
                    self._drag_start = pt
                    self._drag_cur = pt
                    self.update()
                    super().mousePressEvent(event)
                    return
                hit = self._hit_test(*pt)
                if hit >= 0:
                    if hit == self._selected:
                        # 再点一次已选中的框 → 取消选中
                        self._selected = -1
                        self.selectionCleared.emit()
                    else:
                        self._selected = hit
                        self.boxClicked.emit(hit)
                    self.update()
                else:
                    self._drag_start = pt
                    self._drag_cur = pt
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            pt = self._to_photo(event.pos())
            if pt is not None:
                self._drag_cur = pt
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_start is not None:
            start = self._drag_start
            self._drag_start = None
            self._drag_cur = None
            self.update()
            pt = self._to_photo(event.pos())
            if pt is not None and self._pixmap is not None:
                x1, y1 = start
                x2, y2 = pt
                if abs(x2 - x1) >= 5 and abs(y2 - y1) >= 5:
                    # 裁剪到照片范围内
                    pw, ph = self._pixmap.width(), self._pixmap.height()
                    xa = int(max(0, min(x1, x2)))
                    ya = int(max(0, min(y1, y2)))
                    xb = int(min(pw, max(x1, x2)))
                    yb = int(min(ph, max(y1, y2)))
                    if self._calibration_mode:
                        # 标定框只用于换算比例，不算病害记录
                        self.calibrationDrawn.emit((xa, ya, xb, yb))
                    else:
                        self.boxDrawn.emit((xa, ya, xb, yb))
                elif self._selected >= 0:
                    # 空白处单击（未拖动）→ 取消选中
                    self._selected = -1
                    self.selectionCleared.emit()
                    self.update()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self._calibration_mode:
            # 标定模式下 Delete 不误删病害记录
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_Delete and self._selected >= 0:
            self.deleteRequested.emit(self._selected)
            return
        super().keyPressEvent(event)

    def _hit_test(self, x, y):
        """返回包含点 (x,y) 的框索引（后画的优先），无命中返回 -1"""
        for i in range(len(self._boxes) - 1, -1, -1):
            x1, y1, x2, y2 = self._boxes[i][:4]
            if x1 <= x <= x2 and y1 <= y <= y2:
                return i
        return -1
