# -*- coding: utf-8 -*-
"""
面参数总览对话框 - 方案A
当选中面元素时，显示当前组件所有面的参数，支持批量修改组件参数。
"""

import math

try:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QTableWidget, QTableWidgetItem, QFormLayout,
        QHeaderView, QMessageBox
    )
    from PyQt5.QtCore import Qt
except ImportError:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QTableWidget, QTableWidgetItem, QFormLayout,
        QHeaderView, QMessageBox
    )
    from PyQt6.QtCore import Qt


# 参数中文名映射
PARAM_LABELS = {
    'a': '直角边1 (a)',
    'b': '直角边2 (b)',
    'h': '高度 (h)',
    'length': '长度',
    'width': '宽度',
    'height': '高度',
    'radius': '半径',
    'cx': '圆心X',
    'cy': '圆心Y',
    'z_bottom': 'Z起始',
    'z_top': 'Z终止',
    'x': 'X位置',
    'y': 'Y位置',
    'x1': '起点X',
    'y1': '起点Y',
    'x2': '终点X',
    'y2': '终点Y',
    'start_angle': '起始角',
    'end_angle': '终止角',
    'rx': 'X半径',
    'ry': 'Y半径',
    'chamfer': '倒角',
    'point_count': '顶点数',
}

# 面中文名映射
FACE_LABELS = {
    'top': '顶面',
    'front': '前视图',
    'left': '左视图',
    'side': '侧面',
    'side_a': '侧面a',
    'side_b': '侧面b',
    'hypotenuse': '斜面',
    'bottom': '底面',
}


class FaceOverviewDialog(QDialog):
    """面参数总览对话框：显示组件参数（可编辑）和所有面信息（只读）"""

    def __init__(self, parent, component_type, component_params, face_elements):
        super().__init__(parent)
        self.component_type = component_type
        self.original_params = dict(component_params)
        self.new_params = dict(component_params)
        self.face_elements = face_elements
        self.param_inputs = {}
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(f"面参数总览 - {self.component_type}")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # === 组件参数编辑区 ===
        layout.addWidget(QLabel("<b>组件参数（修改后点击应用）</b>"))
        form = QFormLayout()
        form.setSpacing(6)

        # 筛选可编辑的数字参数
        editable_keys = []
        for key, val in sorted(self.original_params.items()):
            if key.startswith('_'):
                continue
            if isinstance(val, (int, float)):
                editable_keys.append(key)

        if not editable_keys:
            layout.addWidget(QLabel("此组件没有可编辑的参数。"))
        else:
            for key in editable_keys:
                val = self.original_params[key]
                label_text = PARAM_LABELS.get(key, key)
                line = QLineEdit(str(val))
                line.setMaximumWidth(100)
                self.param_inputs[key] = line
                form.addRow(f"{label_text}:", line)
            layout.addLayout(form)

        # === 面信息表格（只读）===
        layout.addWidget(QLabel("<b>当前各面几何尺寸</b>"))
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["面", "宽/半径", "高"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)

        rows = []
        for elem in self.face_elements:
            face_name = elem.face_info.get('face_name', 'unknown')
            face_label = FACE_LABELS.get(face_name, face_name)
            w = getattr(elem, 'width', getattr(elem, 'radius', '-'))
            h = getattr(elem, 'height', '-')
            rows.append((face_label, str(w), str(h)))

        table.setRowCount(len(rows))
        for i, (name, w, h) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(name))
            table.setItem(i, 1, QTableWidgetItem(w))
            table.setItem(i, 2, QTableWidgetItem(h))
        layout.addWidget(table)

        # === 按钮 ===
        btn_layout = QHBoxLayout()
        apply_btn = QPushButton("应用")
        apply_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(apply_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_apply(self):
        changed = False
        for key, line in self.param_inputs.items():
            try:
                val = float(line.text())
                if abs(val - self.original_params.get(key, 0)) > 0.001:
                    changed = True
                self.new_params[key] = val
            except ValueError:
                QMessageBox.warning(self, "输入错误", f"参数 '{key}' 必须是数字")
                return
        if not changed:
            QMessageBox.information(self, "提示", "参数没有变化")
            self.reject()
            return
        self.accept()

    def get_new_params(self):
        return self.new_params
