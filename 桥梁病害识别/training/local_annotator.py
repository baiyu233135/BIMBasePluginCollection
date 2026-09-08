# -*- coding: utf-8 -*-
"""
本地病害照片标注工具（YOLO 格式）

功能：
1. 浏览病害照片列表。
2. 用 CV 异常检测自动生成伪标签。
3. 人工增删改边界框，指定病害类别。
4. 保存 YOLO 格式标签（images/ + labels/）。
5. 导出 data.yaml。

使用：
    python local_annotator.py
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from typing import List, Tuple, Optional

# 添加桥梁病害识别根目录到路径
_module_dir = Path(__file__).resolve().parent.parent
if str(_module_dir) not in sys.path:
    sys.path.insert(0, str(_module_dir))

from cv_anomaly_detector import detect_anomalies_cv

# 病害类别
DISEASE_CLASSES = ["裂缝", "剥落", "露筋", "蜂窝麻面", "渗水", "锈蚀", "已修复"]
CLASS_TO_ID = {name: i for i, name in enumerate(DISEASE_CLASSES)}


class BoundingBox:
    def __init__(self, class_id: int, x1: int, y1: int, x2: int, y2: int):
        self.class_id = class_id
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def to_yolo(self, img_w: int, img_h: int) -> str:
        cx = (self.x1 + self.x2) / 2.0 / img_w
        cy = (self.y1 + self.y2) / 2.0 / img_h
        w = (self.x2 - self.x1) / img_w
        h = (self.y2 - self.y1) / img_h
        return f"{self.class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"

    def to_tuple(self) -> Tuple[int, int, int, int, int]:
        return (self.class_id, self.x1, self.y1, self.x2, self.y2)


def run_pseudo_label(image_path: str) -> List[BoundingBox]:
    """用 CV 生成伪标签，默认类别为"异常区域"（需要人工改类）"""
    try:
        results = detect_anomalies_cv(image_path)
        boxes = []
        for r in results:
            # 伪标签默认给 0 类，人工再改
            x1, y1, x2, y2 = r.bbox
            boxes.append(BoundingBox(0, x1, y1, x2, y2))
        return boxes
    except Exception as e:
        print(f"伪标签生成失败: {e}")
        return []


def export_dataset(images_dir: Path, labels_dir: Path, output_dir: Path):
    """导出 YOLO 格式数据集"""
    out_images = output_dir / "images"
    out_labels = output_dir / "labels"
    out_images.mkdir(parents=True, exist_ok=True)
    out_labels.mkdir(parents=True, exist_ok=True)

    for img_file in images_dir.glob("*.*"):
        if img_file.suffix.lower() not in [".jpg", ".jpeg", ".png", ".bmp"]:
            continue
        shutil.copy2(str(img_file), str(out_images / img_file.name))
        label_file = labels_dir / f"{img_file.stem}.txt"
        if label_file.exists():
            shutil.copy2(str(label_file), str(out_labels / f"{img_file.stem}.txt"))

    # 写 data.yaml
    yaml_path = output_dir / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(f"path: {output_dir.resolve().as_posix()}\n")
        f.write("train: images\n")
        f.write("val: images\n")
        f.write(f"nc: {len(DISEASE_CLASSES)}\n")
        f.write("names:\n")
        for name in DISEASE_CLASSES:
            f.write(f"  - {name}\n")

    print(f"数据集已导出到: {output_dir}")


def main_cli():
    """命令行模式：批量生成伪标签"""
    parser = argparse.ArgumentParser(description="本地病害照片标注工具")
    parser.add_argument("--images", required=True, help="图片目录")
    parser.add_argument("--output", required=True, help="输出标签目录")
    parser.add_argument("--export", help="导出为 YOLO 数据集目录")
    args = parser.parse_args()

    images_dir = Path(args.images)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for img_file in sorted(images_dir.glob("*.*")):
        if img_file.suffix.lower() not in [".jpg", ".jpeg", ".png", ".bmp"]:
            continue
        boxes = run_pseudo_label(str(img_file))
        label_path = output_dir / f"{img_file.stem}.txt"

        import cv2
        import numpy as np
        data = np.fromfile(str(img_file), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]

        with open(label_path, "w", encoding="utf-8") as f:
            for box in boxes:
                f.write(box.to_yolo(w, h) + "\n")

        print(f"{img_file.name}: {len(boxes)} 个框")

    if args.export:
        export_dataset(images_dir, output_dir, Path(args.export))


def main_gui():
    """GUI 模式：交互式标注"""
    try:
        from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                                     QHBoxLayout, QListWidget, QListWidgetItem, QLabel,
                                     QPushButton, QFileDialog, QMessageBox, QComboBox,
                                     QSpinBox, QSplitter)
        from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor
        from PyQt5.QtCore import Qt, QRect, QPoint
        import cv2
        import numpy as np
    except ImportError as e:
        print(f"GUI 依赖缺失: {e}")
        print("请安装: pip install PyQt5 opencv-python")
        sys.exit(1)

    class ImageCanvas(QLabel):
        def __init__(self):
            super().__init__()
            self.setAlignment(Qt.AlignCenter)
            self.setMinimumSize(640, 480)
            self.setStyleSheet("border: 1px solid gray; background: #f0f0f0;")
            self.pixmap = None
            self.boxes = []  # List[BoundingBox]
            self.scale = 1.0
            self.offset = QPoint(0, 0)
            self.drawing = False
            self.start_pos = None
            self.current_rect = None

        def set_image(self, image_path: str):
            data = np.fromfile(image_path, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if img is None:
                self.pixmap = None
                self.setText("无法加载图片")
                return

            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w, ch = img_rgb.shape
            bytes_per_line = ch * w
            q_img = QImage(img_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.pixmap = QPixmap.fromImage(q_img)
            self._update_display()

        def set_boxes(self, boxes: List[BoundingBox]):
            self.boxes = boxes
            self._update_display()

        def _update_display(self):
            if self.pixmap is None:
                return

            scaled = self.pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.scale = scaled.width() / self.pixmap.width()

            canvas = QPixmap(scaled.size())
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            painter.drawPixmap(0, 0, scaled)

            pen_colors = {
                0: QColor(255, 0, 0),      # 裂缝 红
                1: QColor(255, 128, 0),    # 剥落 橙
                2: QColor(255, 255, 0),    # 露筋 黄
                3: QColor(128, 0, 255),    # 蜂窝麻面 紫
                4: QColor(0, 128, 255),    # 渗水 蓝
                5: QColor(128, 128, 128),  # 锈蚀 灰
                6: QColor(0, 200, 0),      # 已修复 绿
            }

            for box in self.boxes:
                color = pen_colors.get(box.class_id, QColor(255, 0, 0))
                pen = QPen(color, 2)
                painter.setPen(pen)
                x1 = int(box.x1 * self.scale)
                y1 = int(box.y1 * self.scale)
                x2 = int(box.x2 * self.scale)
                y2 = int(box.y2 * self.scale)
                painter.drawRect(x1, y1, x2 - x1, y2 - y1)
                painter.drawText(x1 + 3, y1 + 15, DISEASE_CLASSES[box.class_id])

            if self.current_rect is not None:
                pen = QPen(QColor(0, 255, 0), 2)
                painter.setPen(pen)
                painter.drawRect(self.current_rect)

            painter.end()
            self.setPixmap(canvas)

        def mousePressEvent(self, event):
            if self.pixmap is None:
                return
            if event.button() == Qt.LeftButton:
                self.drawing = True
                self.start_pos = event.pos()
                self.current_rect = None

        def mouseMoveEvent(self, event):
            if self.drawing and self.start_pos:
                self.current_rect = QRect(self.start_pos, event.pos()).normalized()
                self._update_display()

        def mouseReleaseEvent(self, event):
            if event.button() == Qt.LeftButton and self.drawing and self.current_rect:
                self.drawing = False
                rect = self.current_rect
                x1 = int(rect.left() / self.scale)
                y1 = int(rect.top() / self.scale)
                x2 = int(rect.right() / self.scale)
                y2 = int(rect.bottom() / self.scale)

                # 限制在图片范围内
                if self.pixmap:
                    x1 = max(0, min(x1, self.pixmap.width()))
                    y1 = max(0, min(y1, self.pixmap.height()))
                    x2 = max(0, min(x2, self.pixmap.width()))
                    y2 = max(0, min(y2, self.pixmap.height()))

                if x2 > x1 and y2 > y1:
                    # 弹出选择类别对话框
                    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QListWidget, QDialogButtonBox
                    dialog = QDialog(self)
                    dialog.setWindowTitle("选择病害类型")
                    layout = QVBoxLayout()
                    list_widget = QListWidget()
                    for name in DISEASE_CLASSES:
                        list_widget.addItem(name)
                    layout.addWidget(list_widget)
                    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    buttons.accepted.connect(dialog.accept)
                    buttons.rejected.connect(dialog.reject)
                    layout.addWidget(buttons)
                    dialog.setLayout(layout)

                    if dialog.exec_() == QDialog.Accepted and list_widget.currentRow() >= 0:
                        class_id = list_widget.currentRow()
                        self.boxes.append(BoundingBox(class_id, x1, y1, x2, y2))
                        self._update_display()
                        if hasattr(self.parent(), 'refresh_box_list'):
                            self.parent().refresh_box_list()

                self.current_rect = None

    class AnnotatorWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("桥梁病害照片标注工具")
            self.setGeometry(100, 100, 1200, 800)

            self.images_dir = None
            self.labels_dir = None
            self.current_image_path = None
            self.boxes = []

            self._init_ui()

        def _init_ui(self):
            central = QWidget()
            self.setCentralWidget(central)
            layout = QHBoxLayout(central)

            splitter = QSplitter(Qt.Horizontal)

            # 左侧：图片列表
            left = QWidget()
            left_layout = QVBoxLayout(left)
            self.btn_open = QPushButton("打开图片目录")
            self.btn_open.clicked.connect(self.open_directory)
            left_layout.addWidget(self.btn_open)

            self.list_widget = QListWidget()
            self.list_widget.itemClicked.connect(self.on_image_selected)
            left_layout.addWidget(self.list_widget)

            # 右侧：画布和工具
            right = QWidget()
            right_layout = QVBoxLayout(right)

            self.canvas = ImageCanvas()
            self.canvas.parent = lambda: self
            right_layout.addWidget(self.canvas)

            # 工具按钮
            tools = QWidget()
            tools_layout = QHBoxLayout(tools)

            self.btn_pseudo = QPushButton("生成伪标签")
            self.btn_pseudo.clicked.connect(self.generate_pseudo_labels)
            tools_layout.addWidget(self.btn_pseudo)

            self.btn_delete = QPushButton("删除选中框")
            self.btn_delete.clicked.connect(self.delete_selected_box)
            tools_layout.addWidget(self.btn_delete)

            self.btn_save = QPushButton("保存标签")
            self.btn_save.clicked.connect(self.save_labels)
            tools_layout.addWidget(self.btn_save)

            self.btn_export = QPushButton("导出数据集")
            self.btn_export.clicked.connect(self.export_dataset)
            tools_layout.addWidget(self.btn_export)

            right_layout.addWidget(tools)

            # 框列表
            self.box_list = QListWidget()
            right_layout.addWidget(QLabel("边界框列表："))
            right_layout.addWidget(self.box_list)

            splitter.addWidget(left)
            splitter.addWidget(right)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 3)

            layout.addWidget(splitter)

        def open_directory(self):
            dir_path = QFileDialog.getExistingDirectory(self, "选择图片目录")
            if not dir_path:
                return
            self.images_dir = Path(dir_path)
            self.labels_dir = self.images_dir.parent / "labels"
            self.labels_dir.mkdir(exist_ok=True)

            self.list_widget.clear()
            for f in sorted(self.images_dir.glob("*.*")):
                if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp"]:
                    self.list_widget.addItem(f.name)

            QMessageBox.information(self, "提示", f"已加载 {self.list_widget.count()} 张图片")

        def on_image_selected(self, item: QListWidgetItem):
            if not self.images_dir:
                return
            self.current_image_path = self.images_dir / item.text()
            self.canvas.set_image(str(self.current_image_path))

            # 加载已有标签
            label_path = self.labels_dir / f"{self.current_image_path.stem}.txt"
            self.boxes = []
            if label_path.exists():
                with open(label_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            class_id = int(parts[0])
                            cx, cy, w, h = map(float, parts[1:5])
                            # 转回像素坐标
                            import cv2
                            import numpy as np
                            data = np.fromfile(str(self.current_image_path), dtype=np.uint8)
                            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
                            if img is not None:
                                ih, iw = img.shape[:2]
                                x1 = int((cx - w / 2) * iw)
                                y1 = int((cy - h / 2) * ih)
                                x2 = int((cx + w / 2) * iw)
                                y2 = int((cy + h / 2) * ih)
                                self.boxes.append(BoundingBox(class_id, x1, y1, x2, y2))

            self.canvas.set_boxes(self.boxes)
            self.refresh_box_list()

        def generate_pseudo_labels(self):
            if not self.current_image_path:
                QMessageBox.warning(self, "警告", "请先选择一张图片")
                return
            self.boxes = run_pseudo_label(str(self.current_image_path))
            self.canvas.set_boxes(self.boxes)
            self.refresh_box_list()
            QMessageBox.information(self, "提示", f"已生成 {len(self.boxes)} 个伪标签框")

        def refresh_box_list(self):
            self.box_list.clear()
            for i, box in enumerate(self.boxes):
                text = f"{i+1}. {DISEASE_CLASSES[box.class_id]} ({box.x1}, {box.y1}) -> ({box.x2}, {box.y2})"
                self.box_list.addItem(text)

        def delete_selected_box(self):
            row = self.box_list.currentRow()
            if 0 <= row < len(self.boxes):
                del self.boxes[row]
                self.canvas.set_boxes(self.boxes)
                self.refresh_box_list()

        def save_labels(self):
            if not self.current_image_path or not self.images_dir:
                QMessageBox.warning(self, "警告", "请先选择图片")
                return

            label_path = self.labels_dir / f"{self.current_image_path.stem}.txt"

            import cv2
            import numpy as np
            data = np.fromfile(str(self.current_image_path), dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if img is None:
                return
            ih, iw = img.shape[:2]

            with open(label_path, "w", encoding="utf-8") as f:
                for box in self.boxes:
                    f.write(box.to_yolo(iw, ih) + "\n")

            QMessageBox.information(self, "提示", f"标签已保存: {label_path}")

        def export_dataset(self):
            if not self.images_dir:
                QMessageBox.warning(self, "警告", "请先打开图片目录")
                return

            output_dir = QFileDialog.getExistingDirectory(self, "选择导出目录")
            if not output_dir:
                return

            export_dataset(self.images_dir, self.labels_dir, Path(output_dir))
            QMessageBox.information(self, "提示", f"数据集已导出到: {output_dir}")

    app = QApplication(sys.argv)
    window = AnnotatorWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main_cli()
    else:
        main_gui()
