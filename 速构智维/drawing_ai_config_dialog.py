# -*- coding: utf-8 -*-
"""图纸识别 API 配置对话框"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.drawing_recognizer import load_config, save_config

try:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QFormLayout, QLineEdit,
        QPushButton, QHBoxLayout, QMessageBox, QDoubleSpinBox, QSpinBox
    )
    from PyQt5.QtCore import Qt
except ImportError:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QFormLayout, QLineEdit,
        QPushButton, QHBoxLayout, QMessageBox, QDoubleSpinBox, QSpinBox
    )
    from PyQt6.QtCore import Qt


class DrawingAIConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图纸识别 API 配置")
        self.setMinimumWidth(450)
        self._cfg = load_config()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.api_key_edit = QLineEdit(self._cfg.get("dashscope_api_key", ""))
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("DashScope API Key:", self.api_key_edit)

        self.api_base_edit = QLineEdit(self._cfg.get("api_base", ""))
        form.addRow("API Base:", self.api_base_edit)

        self.model_edit = QLineEdit(self._cfg.get("model", "qwen-vl-max"))
        form.addRow("模型:", self.model_edit)

        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 1.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(float(self._cfg.get("temperature", 0.2)))
        form.addRow("Temperature:", self.temp_spin)

        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(500, 4096)
        self.tokens_spin.setSingleStep(100)
        self.tokens_spin.setValue(int(self._cfg.get("max_tokens", 2000)))
        form.addRow("Max Tokens:", self.tokens_spin)

        layout.addLayout(form)

        btns = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _on_save(self):
        cfg = {
            "dashscope_api_key": self.api_key_edit.text().strip(),
            "api_base": self.api_base_edit.text().strip(),
            "model": self.model_edit.text().strip(),
            "temperature": self.temp_spin.value(),
            "max_tokens": self.tokens_spin.value(),
        }
        if not cfg["dashscope_api_key"]:
            QMessageBox.warning(self, "配置错误", "API Key 不能为空")
            return
        if save_config(cfg):
            QMessageBox.information(self, "保存成功", "图纸识别 API 配置已保存")
            self.accept()
        else:
            QMessageBox.critical(self, "保存失败", "无法写入配置文件")
