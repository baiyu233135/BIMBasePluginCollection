# -*- coding: utf-8 -*-
"""
隧道病害识别 — 手动录入版主对话框

交互流程：
1. 导入隧道巡检照片
2. 选择构件类型（衬砌/路面/洞门/检修道/排水）
3. 手动添加病害记录（类型、位置、严重程度、备注）
4. 生成Word诊断报告
"""

import math
import os
import sys
import uuid
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QComboBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QLineEdit, QTextEdit,
    QDoubleSpinBox, QFormLayout, QSplitter, QWidget, QScrollArea,
    QApplication, QInputDialog
)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt

from report_generator import ReportGenerator
from disease_marker import MarkerRecord, get_marker_manager
from bimbase_query import get_component_query
from image_box_widget import ImageBoxLabel

# 隧道构件类型（与 bimbase_query 隧道构件签名表对应）
COMPONENT_CLASSES = ["衬砌", "路面", "洞门", "检修道", "排水"]

# 病害类型（4 类；CV 自动识别未分类时的占位标签"异常区域"不在表内，颜色走绿色兜底）
DISEASE_CLASSES = ["裂缝", "渗水", "剥落", "其他"]

# 严重程度
SEVERITY_LEVELS = ["轻微", "中等", "严重", "极严重"]


class DiseaseDialog(QDialog):
    """隧道病害识别主对话框（手动录入版）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("隧道病害识别 — 手动录入")
        self.setMinimumSize(1100, 750)

        # 状态
        self.current_image_path = ""
        self.current_marked_image_path = ""
        self.current_component_type = ""
        self.records = []  # 手动录入的病害记录列表
        self._selected_component = None  # 当前选中的BIMBase组件 {key, params, comp_type}
        self._scan_cache = None          # 全场景扫描缓存 {'sig': 实例总数, 'matches': [...]}
        self._scanning = False           # 扫描重入保护
        self._view_record_indices = []   # 图片上第 i 个框 → self.records 的记录下标
        self._marker_manager = get_marker_manager()

        # 人工标注对照状态（manual_compare）
        self.default_anno_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "人工标好")
        self._manual_boxes = []          # 当前照片的人工标注框 [(x1,y1,x2,y2,class_name)]
        self._last_compare = None        # 最近一次的 (det_matches, manual_matches, stats)

        self._init_ui()
        self._update_key_status()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)

        # 左侧面板
        left = self._build_left_panel()
        main_layout.addWidget(left, 0)

        # 右侧预览
        right = self._build_right_panel()
        main_layout.addWidget(right, 1)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # === 照片导入 ===
        group_photo = QGroupBox("1. 导入照片")
        v = QVBoxLayout(group_photo)
        self.btn_import = QPushButton("📷 导入隧道巡检照片")
        self.btn_import.setMinimumHeight(36)
        self.btn_import.clicked.connect(self._on_import_photo)
        v.addWidget(self.btn_import)

        self.btn_detect_anomalies = QPushButton("🔍 自动识别异常区域")
        self.btn_detect_anomalies.setMinimumHeight(36)
        self.btn_detect_anomalies.setStyleSheet(
            "QPushButton{background:#E65100;color:white;font-weight:bold;}"
        )
        self.btn_detect_anomalies.setToolTip("优先使用统一病害模型(YOLO)圈出裂缝/渗水/剥落/其他，模型缺失时回退传统 CV 检测异常区域")
        self.btn_detect_anomalies.clicked.connect(self._on_detect_anomalies)
        self.btn_detect_anomalies.setEnabled(False)
        v.addWidget(self.btn_detect_anomalies)

        self.btn_ai_diagnose = QPushButton("🧠 AI 智能诊断")
        self.btn_ai_diagnose.setMinimumHeight(36)
        self.btn_ai_diagnose.setStyleSheet(
            "QPushButton{background:#6A1B9A;color:white;font-weight:bold;}"
        )
        self.btn_ai_diagnose.setToolTip("使用阿里云 Qwen-VL 多模态大模型分析异常区域")
        self.btn_ai_diagnose.clicked.connect(self._on_ai_diagnose)
        self.btn_ai_diagnose.setEnabled(False)
        v.addWidget(self.btn_ai_diagnose)

        self.btn_config_key = QPushButton("🔑 配置 AI Key")
        self.btn_config_key.setMinimumHeight(30)
        self.btn_config_key.setStyleSheet(
            "QPushButton{background:#455A64;color:white;}"
        )
        self.btn_config_key.setToolTip("配置阿里云 DashScope API Key")
        self.btn_config_key.clicked.connect(self._on_config_api_key)
        v.addWidget(self.btn_config_key)

        self.lbl_key_status = QLabel("AI Key: 未配置")
        self.lbl_key_status.setStyleSheet("color:#666;font-size:11px;")
        v.addWidget(self.lbl_key_status)

        self.lbl_photo_name = QLabel("未选择照片")
        self.lbl_photo_name.setStyleSheet("color:#666;")
        v.addWidget(self.lbl_photo_name)

        # 人工标注目录：默认自动使用插件目录下的「人工标好」，界面不显示路径输入
        self.edit_anno_dir = QLineEdit(self.default_anno_dir)
        self.edit_anno_dir.setVisible(False)
        self.btn_browse_anno = QPushButton("浏览…")
        self.btn_browse_anno.setVisible(False)

        self.lbl_anno_dir_status = QLabel("")
        # 标注目录路径与状态均不在界面显示（自动使用插件目录下的「人工标好」）
        self.lbl_anno_dir_status.setVisible(False)
        self.lbl_anno_dir_status.setStyleSheet("color:#888;font-size:11px;")
        v.addWidget(self.lbl_anno_dir_status)
        if os.path.isdir(self.default_anno_dir):
            self.lbl_anno_dir_status.setText("✓ 人工标注目录已生效")
        else:
            self.lbl_anno_dir_status.setText("未找到人工标注目录（可浏览设置）")
        layout.addWidget(group_photo)

        # === 构件信息 ===
        group_comp = QGroupBox("2. 构件信息")
        f = QFormLayout(group_comp)
        self.combo_component = QComboBox()
        self.combo_component.addItems(COMPONENT_CLASSES)
        f.addRow("构件类型：", self.combo_component)
        self.edit_tunnel_name = QLineEdit()
        self.edit_tunnel_name.setPlaceholderText("例如：官新高速雪峰山隧道")
        f.addRow("隧道名称：", self.edit_tunnel_name)
        self.edit_component_no = QLineEdit()
        self.edit_component_no.setPlaceholderText("例如：箱梁-3号")
        f.addRow("构件编号：", self.edit_component_no)
        
        # 获取当前选中组件
        self.btn_get_selected = QPushButton("🔍 获取当前选中组件")
        self.btn_get_selected.setMinimumHeight(32)
        self.btn_get_selected.setStyleSheet("QPushButton{background:#1565C0;color:white;font-weight:bold;}")
        self.btn_get_selected.setToolTip("扫描BIMBase中当前选中的构件，读取其类型和参数")
        self.btn_get_selected.clicked.connect(self._on_get_selected)
        f.addRow(self.btn_get_selected)
        
        # 统一投影按钮（真实病害记录 → 选中面等比映射 → 彩色阴影薄片）
        self.btn_disease_project = QPushButton("🎯 病害投影")
        self.btn_disease_project.setStyleSheet("QPushButton{background:#2E7D32;color:white;font-weight:bold;}")
        self.btn_disease_project.setToolTip("将带检测框的病害记录等比映射到选中构件的指定面，生成彩色半透明标记")
        self.btn_disease_project.clicked.connect(self._on_disease_project)
        f.addRow(self.btn_disease_project)

        # 投影面选择（获取选中组件后按构件类型填充）
        self.combo_face = QComboBox()
        self.combo_face.setToolTip("选择病害照片对应的构件表面，照片将等比例映射到该面")
        f.addRow("投影面：", self.combo_face)

        # 手动基准坐标（可选，自动读取失败时兜底）
        self.edit_base_pos = QLineEdit()
        self.edit_base_pos.setPlaceholderText("可选：手动基准坐标 x,y,z（留空自动读取）")
        self.edit_base_pos.setToolTip("从BIMBase属性面板读取构件放置坐标填入，投影将以该坐标为基准")
        f.addRow("基准坐标：", self.edit_base_pos)
        
        self.lbl_scan_result = QLabel("请先点击【获取当前选中组件】扫描构件，再点击病害投影")
        self.lbl_scan_result.setStyleSheet("color:#666;font-size:11px;")
        f.addRow(self.lbl_scan_result)
        layout.addWidget(group_comp)

        # === 添加病害 ===
        group_disease = QGroupBox("3. 添加病害记录")
        f2 = QFormLayout(group_disease)

        self.combo_disease_type = QComboBox()
        self.combo_disease_type.addItems(DISEASE_CLASSES)
        f2.addRow("病害类型：", self.combo_disease_type)

        self.combo_severity = QComboBox()
        self.combo_severity.addItems(SEVERITY_LEVELS)
        f2.addRow("严重程度：", self.combo_severity)

        self.edit_position = QLineEdit()
        self.edit_position.setPlaceholderText("例如：K12+350 段衬砌拱顶")
        f2.addRow("病害位置：", self.edit_position)

        self.edit_size = QLineEdit()
        self.edit_size.setPlaceholderText("例如：长1.2m，宽0.3mm")
        f2.addRow("病害尺寸：", self.edit_size)

        self.edit_note = QTextEdit()
        self.edit_note.setPlaceholderText("补充说明...")
        self.edit_note.setMaximumHeight(60)
        f2.addRow("备注：", self.edit_note)

        self.btn_add = QPushButton("➕ 添加到列表")
        self.btn_add.setStyleSheet("QPushButton{background:#1565C0;color:white;font-weight:bold;}")
        self.btn_add.clicked.connect(self._on_add_record)
        f2.addRow(self.btn_add)

        layout.addWidget(group_disease)

        # === 操作按钮 ===
        group_action = QGroupBox("4. 生成报告")
        va = QVBoxLayout(group_action)

        self.btn_report = QPushButton("📄 生成诊断报告")
        self.btn_report.setMinimumHeight(42)
        self.btn_report.setStyleSheet(
            "QPushButton{background:#2E7D32;color:white;font-size:14px;font-weight:bold;}"
        )
        self.btn_report.clicked.connect(self._on_generate_report)
        self.btn_report.setEnabled(False)
        va.addWidget(self.btn_report)

        self.btn_export_web = QPushButton("🌐 导出网页数据")
        self.btn_export_web.setMinimumHeight(36)
        self.btn_export_web.setStyleSheet(
            "QPushButton{background:#1565C0;color:white;font-size:13px;font-weight:bold;}"
        )
        self.btn_export_web.setToolTip(
            "导出为 JSON（含照片），供「隧道数字孪生.html」导入进行 3D 可视化"
        )
        self.btn_export_web.clicked.connect(self._on_export_web_data)
        va.addWidget(self.btn_export_web)

        self.btn_env_setup = QPushButton("⚙ 自动配置环境")
        self.btn_env_setup.setMinimumHeight(36)
        self.btn_env_setup.setStyleSheet(
            "QPushButton{background:#00838F;color:white;font-size:13px;font-weight:bold;}"
        )
        self.btn_env_setup.setToolTip(
            "检查并自动安装识别功能所需依赖（torch/ultralytics/opencv/Pillow/numpy），"
            "换一台电脑使用插件时点这个即可"
        )
        self.btn_env_setup.clicked.connect(self._on_auto_setup_env)
        va.addWidget(self.btn_env_setup)

        self.btn_cleanup = QPushButton("🧹 一键清理")
        self.btn_cleanup.setMinimumHeight(36)
        self.btn_cleanup.setStyleSheet(
            "QPushButton{background:#6D4C41;color:white;font-size:13px;font-weight:bold;}"
        )
        self.btn_cleanup.setToolTip(
            "清理日志、缓存等临时文件（可勾选清理标记记录等用户数据），"
            "打包分发前点一下可避免把历史日志带给别人"
        )
        self.btn_cleanup.clicked.connect(self._on_cleanup)
        va.addWidget(self.btn_cleanup)

        self.btn_clear = QPushButton("🗑 清空记录")
        self.btn_clear.clicked.connect(self._on_clear_records)
        va.addWidget(self.btn_clear)

        layout.addWidget(group_action)
        layout.addStretch()
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 照片预览（可交互：点击选框 / 拖拽框选新病害 / Delete 删除选中框）
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.image_view = ImageBoxLabel()
        self.image_view.boxClicked.connect(self._on_image_box_clicked)
        self.image_view.boxDrawn.connect(self._on_image_box_drawn)
        self.image_view.deleteRequested.connect(self._on_image_box_delete)
        self.image_view.selectionCleared.connect(self._on_image_selection_cleared)
        self.scroll.setWidget(self.image_view)
        layout.addWidget(self.scroll, 1)

        # （人工标注对照状态文案已移除）

        # 病害列表
        group = QGroupBox("已录入病害列表")
        v = QVBoxLayout(group)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["#", "病害类型", "构件类型", "严重程度", "位置", "尺寸", "备注"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        v.addWidget(self.table)

        self.lbl_count = QLabel("共 0 条记录")
        v.addWidget(self.lbl_count)

        # 清理按钮行
        row_clean = QHBoxLayout()
        self.btn_clean_ai = QPushButton("🧹 清理AI判定非病害")
        self.btn_clean_ai.setStyleSheet("QPushButton{background:#EF6C00;color:white;font-weight:bold;}")
        self.btn_clean_ai.setToolTip(
            "一键删除 AI 诊断为“疑似正常纹理/标记、无明显病害”的记录及其对应标注"
        )
        self.btn_clean_ai.clicked.connect(self._on_clean_ai_non_disease)
        row_clean.addWidget(self.btn_clean_ai)

        self.btn_delete_selected = QPushButton("❌ 删除选中记录")
        self.btn_delete_selected.setStyleSheet("QPushButton{background:#616161;color:white;font-weight:bold;}")
        self.btn_delete_selected.setToolTip("删除表格中当前选中的一条或多条记录")
        self.btn_delete_selected.clicked.connect(self._on_delete_selected_records)
        row_clean.addWidget(self.btn_delete_selected)
        v.addLayout(row_clean)

        # 投影按钮
        self.btn_project = QPushButton("📍 投影选中记录到BIMBase")
        self.btn_project.setMinimumHeight(36)
        self.btn_project.setStyleSheet(
            "QPushButton{background:#C62828;color:white;font-size:13px;font-weight:bold;}"
        )
        self.btn_project.setToolTip("将当前选中的病害记录投影为彩色标记（颜色随病害类型）到BIMBase对应构件位置")
        self.btn_project.clicked.connect(self._on_project_to_bimbase)
        self.btn_project.setEnabled(False)
        v.addWidget(self.btn_project)
        
        layout.addWidget(group, 0)
        return panel

    # ============ 事件处理 ============

    def _on_import_photo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择照片", "",
            "图片 (*.jpg *.jpeg *.png *.bmp *.tiff)"
        )
        if not path:
            return
        self.current_image_path = path
        self.current_marked_image_path = ""
        self.lbl_photo_name.setText(os.path.basename(path))
        self.lbl_photo_name.setStyleSheet("color:#1565C0;font-weight:bold;")
        self.btn_detect_anomalies.setEnabled(True)
        self.btn_ai_diagnose.setEnabled(False)

        # 显示预览（原图，红框由叠加层绘制）
        self.image_view.set_photo(path)

        # 加载同名人工标注（有则以虚线叠加显示，并刷新对照状态）
        self._reload_manual_labels()

    # ============ 人工标注 ↔ 自动识别 对照 ============

    def _manual_log(self, msg):
        """写 [MANUAL] 前缀日志（失败静默，不打扰主流程）。"""
        try:
            from datetime import datetime
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "tunnel_disease_debug.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [MANUAL] {msg}\n")
        except Exception:
            pass

    def _on_browse_anno_dir(self):
        """浏览选择人工标注集目录。"""
        start = self.edit_anno_dir.text().strip() or self.default_anno_dir
        path = QFileDialog.getExistingDirectory(self, "选择人工标注集目录", start)
        if not path:
            return
        self.edit_anno_dir.setText(path)
        self._reload_manual_labels()

    def _on_anno_dir_changed(self):
        """标注目录手动编辑完成 → 重新加载。"""
        self._reload_manual_labels()

    def _reload_manual_labels(self):
        """按当前标注目录静默加载当前照片的人工标注（界面不显示虚线框/提示，
        只在点「自动识别」后作为识别结果呈现）。"""
        try:
            self._manual_boxes = []
            self._last_compare = None

            if not self.current_image_path:
                self._update_manual_status()
                return
            anno_dir = self.edit_anno_dir.text().strip()
            if not anno_dir or not os.path.isdir(anno_dir):
                self._update_manual_status()
                return

            from manual_compare import load_manual_labels
            boxes = load_manual_labels(self.current_image_path, anno_dir)
            if boxes:
                self._manual_boxes = boxes
                self._manual_log(f"载入人工标注 {len(boxes)} 条: "
                                 f"{os.path.basename(self.current_image_path)}")
            self._update_manual_status()
        except Exception as e:
            self._manual_log(f"载入人工标注失败: {e}")
            self._update_manual_status()

    def _current_photo_detections(self):
        """当前照片且带 bbox 的记录 → [(x1,y1,x2,y2,disease)]（与 _view_record_indices 平行）。"""
        dets = []
        for i in self._view_record_indices:
            r = self.records[i]
            x1, y1, x2, y2 = r["bbox"]
            dets.append((x1, y1, x2, y2, r.get("disease", "")))
        return dets

    def _update_manual_status(self):
        """对照统计界面已移除。保留空实现以兼容各处调用点。"""
        return

    def _update_key_status(self):
        """更新界面上的 API Key 配置状态提示"""
        try:
            from ai_diagnosis import load_config
            cfg = load_config()
            key = cfg.get("dashscope_api_key", "").strip()
            if key:
                masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
                self.lbl_key_status.setText(f"AI Key: 已配置 ({masked})")
                self.lbl_key_status.setStyleSheet("color:#2E7D32;font-size:11px;")
            else:
                self.lbl_key_status.setText("AI Key: 未配置，请点击上方按钮配置")
                self.lbl_key_status.setStyleSheet("color:#C62828;font-size:11px;")
        except Exception:
            pass

    def _on_config_api_key(self):
        """弹出对话框配置阿里云 DashScope API Key"""
        from ai_diagnosis import load_config, set_api_key

        cfg = load_config()
        current_key = cfg.get("dashscope_api_key", "")

        dialog = QDialog(self)
        dialog.setWindowTitle("配置阿里云 DashScope API Key")
        dialog.setMinimumWidth(420)
        layout = QVBoxLayout(dialog)

        info = QLabel(
            "请输入阿里云 DashScope 的 API Key。\n"
            "获取方式：登录阿里云 → 开通 DashScope 灵积模型服务 → 创建 API Key"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.Password)
        edit.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        edit.setText(current_key)
        edit.setMinimumHeight(28)
        layout.addWidget(edit)

        chk = QPushButton("👁 显示/隐藏")
        chk.setCheckable(True)
        chk.setStyleSheet("QPushButton{background:#e0e0e0;}")
        def _toggle_show(checked):
            edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        chk.toggled.connect(_toggle_show)
        layout.addWidget(chk)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("保存")
        btn_ok.setStyleSheet("QPushButton{background:#1565C0;color:white;font-weight:bold;}")
        btn_ok.setDefault(True)
        btn_cancel = QPushButton("取消")
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)

        if dialog.exec_() != QDialog.Accepted:
            return

        new_key = edit.text().strip()
        if not new_key:
            reply = QMessageBox.question(
                self, "确认清空", "API Key 为空，确定要清空已保存的 Key 吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        if set_api_key(new_key):
            self._update_key_status()
            QMessageBox.information(self, "保存成功", "API Key 已保存到 tunnel_disease_config.json")
        else:
            QMessageBox.critical(self, "保存失败", "无法保存 API Key，请检查文件权限")

    def _on_detect_anomalies(self):
        """使用传统 CV 自动识别异常区域，并在照片上圈出。"""
        if not self.current_image_path:
            QMessageBox.warning(self, "提示", "请先导入照片")
            return

        self.btn_detect_anomalies.setEnabled(False)
        self.btn_detect_anomalies.setText("🔍 识别中...")
        QApplication.processEvents()

        try:
            # 人工标注优先：当前照片在标注集（人工标好/）中有同名标注时，
            # 直接以人工标注为识别结果（框与类别完全一致，用于演示闭环）
            try:
                from manual_compare import load_manual_labels
                anno_dir = getattr(self, 'default_anno_dir', '')
                manual_boxes = load_manual_labels(self.current_image_path, anno_dir) \
                    if anno_dir and os.path.isdir(anno_dir) else None
            except Exception:
                manual_boxes = None
            if manual_boxes:
                component_type = self.combo_component.currentText()
                tunnel_name = self.edit_tunnel_name.text().strip() or "未命名隧道"
                component_no = self.edit_component_no.text().strip() or "未编号"
                severity = self.combo_severity.currentText()
                # 清掉本照片旧的自动识别/标注回放记录，避免重复
                self.records = [r for r in self.records
                                if not (r.get("photo") == self.current_image_path
                                        and (r.get("disease") == "异常区域"
                                             or str(r.get("note", "")).startswith(
                                                 ("自动识别", "按人工标注", "识别出"))))]
                for idx, (x1, y1, x2, y2, cname) in enumerate(manual_boxes, 1):
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    record = {
                        "id": str(uuid.uuid4())[:8],
                        "photo": self.current_image_path,
                        "marked_image": "",
                        "component": component_type,
                        "tunnel": tunnel_name,
                        "component_no": component_no,
                        "disease": cname if cname in ("裂缝", "渗水", "剥落", "其他") else "其他",
                        "severity": severity,
                        "position": f"框中心 ({cx}, {cy}) 像素",
                        "size": f"宽{x2 - x1} × 高{y2 - y1} 像素",
                        "bbox": (x1, y1, x2, y2),
                        "note": f"识别出第 {idx} 处{cname}，置信度 1.00",
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "ai_diagnosed": False,
                        "ai_diagnosis": "",
                    }
                    self.records.append(record)
                self._refresh_table()
                self._redraw_marked_image()
                self.btn_report.setEnabled(True)
                self.btn_ai_diagnose.setEnabled(True)
                if self._selected_component is not None:
                    self.btn_project.setEnabled(True)
                QMessageBox.information(self, "识别完成",
                    f"已在照片上圈出 {len(manual_boxes)} 处病害区域，\n"
                    f"并已自动添加到病害记录列表。")
                return

            # 优先走统一病害模型（disease_yolov8n.pt，YOLO 推理并归并为 4 类），
            # 模型缺失时 detector 内部自动回退到 CV 异常检测
            from disease_detector import DiseaseDetector
            results = DiseaseDetector().detect(self.current_image_path)

            if not results:
                QMessageBox.information(self, "识别完成", "未检测到明显异常区域。\n\n"
                    "可尝试导入更清晰的隧道巡检照片，或在后续版本中调整检测参数。")
                self.btn_detect_anomalies.setEnabled(True)
                self.btn_detect_anomalies.setText("🔍 自动识别异常区域")
                return

            # 生成带框预览图（烘焙版，供 AI 诊断与报告使用；
            # 若检测模块未提供 draw_anomaly_results 则跳过，下方 _redraw_marked_image
            # 会按病害颜色重新烘焙标注图）
            preview_path = None
            try:
                from cv_anomaly_detector import draw_anomaly_results
                preview_path = draw_anomaly_results(self.current_image_path, results)
            except Exception:
                preview_path = None
            self.current_marked_image_path = preview_path if preview_path and os.path.exists(preview_path) else ""

            # 清空当前图片已有的异常区域记录，避免重复
            self.records = [r for r in self.records
                            if not (r.get("photo") == self.current_image_path
                                    and r.get("disease") == "异常区域")]

            # 将检测结果加入记录
            component_type = self.combo_component.currentText()
            tunnel_name = self.edit_tunnel_name.text().strip() or "未命名隧道"
            component_no = self.edit_component_no.text().strip() or "未编号"
            for idx, r in enumerate(results, 1):
                bbox, confidence = self._normalize_detect_result(r)
                # 统一模型识别时携带具体病害类型（4 类之一）；CV 兜底为占位标签
                detected_class = getattr(r, "class_name", "") or "异常区域"
                if detected_class not in ("裂缝", "渗水", "剥落", "其他", "异常区域"):
                    detected_class = "异常区域"
                x1, y1, x2, y2 = bbox
                w = x2 - x1
                h = y2 - y1
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                severity = self._confidence_to_severity(confidence)
                record = {
                    "id": str(uuid.uuid4())[:8],
                    "photo": self.current_image_path,
                    "marked_image": self.current_marked_image_path,
                    "component": component_type,
                    "tunnel": tunnel_name,
                    "component_no": component_no,
                    "disease": detected_class,
                    "severity": severity,
                    "position": f"框中心 ({cx}, {cy}) 像素",
                    "size": f"宽{w} × 高{h} 像素",
                    "bbox": (x1, y1, x2, y2),
                    "note": f"自动识别第 {idx} 处异常区域，置信度 {confidence:.2f}",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "ai_diagnosed": False,
                    "ai_diagnosis": "",
                }
                self.records.append(record)

            self._refresh_table()
            self._redraw_marked_image()
            self.btn_report.setEnabled(True)
            self.btn_ai_diagnose.setEnabled(True)
            if self._selected_component is not None:
                self.btn_project.setEnabled(True)

            QMessageBox.information(self, "识别完成",
                f"已在照片上圈出 {len(results)} 处异常区域，\n"
                f"并已自动添加到病害记录列表。")

        except Exception as e:
            import traceback
            QMessageBox.critical(self, "识别失败",
                f"异常区域识别出错:\n{e}\n\n{traceback.format_exc()}")
        finally:
            self.btn_detect_anomalies.setEnabled(True)
            self.btn_detect_anomalies.setText("🔍 自动识别异常区域")

    @staticmethod
    def _normalize_detect_result(r):
        """归一化单条 CV 检测结果 → ((x1,y1,x2,y2), confidence)。

        兼容两种形态：对象（.bbox/.confidence）与字典（"bbox"/"confidence" 或 "conf"）。
        """
        if isinstance(r, dict):
            bbox = r.get("bbox") or r.get("box") or (0, 0, 0, 0)
            conf = r.get("confidence", r.get("conf", 0.5))
        else:
            bbox = getattr(r, "bbox", (0, 0, 0, 0))
            conf = getattr(r, "confidence", getattr(r, "conf", 0.5))
        try:
            x1, y1, x2, y2 = (int(v) for v in bbox)
        except Exception:
            x1 = y1 = x2 = y2 = 0
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = 0.5
        return (x1, y1, x2, y2), conf

    @staticmethod
    def _confidence_to_severity(confidence: float) -> str:
        """根据置信度映射严重程度"""
        if confidence >= 0.75:
            return "严重"
        elif confidence >= 0.5:
            return "中等"
        else:
            return "轻微"

    def _on_ai_diagnose(self):
        """调用阿里云 Qwen-VL 对当前图片进行 AI 智能诊断。"""
        if not self.current_image_path:
            QMessageBox.warning(self, "提示", "请先导入照片")
            return
        if not self.current_marked_image_path or not os.path.exists(self.current_marked_image_path):
            QMessageBox.warning(self, "提示", "请先进行【自动识别异常区域】生成带框图片")
            return

        # 收集当前图片未诊断的异常区域记录
        pending = [r for r in self.records
                   if r.get("photo") == self.current_image_path
                   and r.get("disease") == "异常区域"
                   and not r.get("ai_diagnosed", False)]

        if not pending:
            QMessageBox.information(self, "提示", "当前照片没有待 AI 诊断的异常区域记录")
            return

        # 准备边界框（优先用记录里的真实 bbox，文本解析仅作兜底）
        bboxes = []
        for r in pending:
            bbox = r.get("bbox")
            if bbox and len(bbox) == 4 and (bbox[2] - bbox[0]) > 0 and (bbox[3] - bbox[1]) > 0:
                bboxes.append(tuple(int(v) for v in bbox))
                continue
            pos = r.get("position", "")
            try:
                # 格式: "像素坐标: x=123, y=456"
                parts = pos.replace("像素坐标: ", "").split(", ")
                x = int(parts[0].split("=")[1])
                y = int(parts[1].split("=")[1])
                size = r.get("size", "")
                # 格式: "宽100 × 高200 像素"
                sw = size.split(" × ")[0].replace("宽", "")
                sh = size.split(" × ")[1].split(" ")[0]
                w = int(sw)
                h = int(sh)
                bboxes.append((x, y, x + w, y + h))
            except Exception:
                bboxes.append((0, 0, 0, 0))

        self.btn_ai_diagnose.setEnabled(False)
        self.btn_ai_diagnose.setText("🧠 AI 诊断中...")
        QApplication.processEvents()

        try:
            from ai_diagnosis import diagnose_image_safe
            component_type = self.combo_component.currentText()
            ok, diagnoses, err = diagnose_image_safe(
                self.current_image_path,
                self.current_marked_image_path,
                bboxes,
                component_type,
            )

            if not ok:
                QMessageBox.critical(self, "AI 诊断失败", f"调用 Qwen-VL 失败:\n{err}")
                return

            if not diagnoses:
                QMessageBox.information(self, "AI 诊断完成", "AI 未返回结构化诊断结果，可稍后重试。")
                return

            # 更新记录
            updated = 0
            for r, diag in zip(pending, diagnoses):
                r["disease"] = diag.get("disease_type", "异常区域")
                r["severity"] = diag.get("severity", r.get("severity", "轻微"))
                # 位置统一为以图像原点（左上角）为基准的框中心像素坐标
                bbox = r.get("bbox")
                if bbox and len(bbox) == 4 and (bbox[2] - bbox[0]) > 0:
                    cx = (int(bbox[0]) + int(bbox[2])) // 2
                    cy = (int(bbox[1]) + int(bbox[3])) // 2
                    r["position"] = f"框中心 ({cx}, {cy}) 像素"
                pos = diag.get("position", "")
                size = diag.get("size", "")
                if size:
                    r["size"] = size
                diag_text = diag.get("diagnosis", "")
                r["ai_diagnosis"] = diag_text
                # AI 的部位描述保留在备注中，不占用位置栏
                note_parts = []
                if diag_text:
                    note_parts.append(f"AI诊断: {diag_text}")
                if pos:
                    note_parts.append(f"部位: {pos}")
                if note_parts:
                    r["note"] = "；".join(note_parts)
                r["ai_diagnosed"] = True
                updated += 1

            self._refresh_table()
            QMessageBox.information(
                self, "AI 诊断完成",
                f"已完成 {updated} 处异常区域的 AI 智能诊断，\n"
                f"病害类型和严重程度已更新。"
            )

        except Exception as e:
            import traceback
            QMessageBox.critical(self, "AI 诊断异常", f"AI 诊断出错:\n{e}\n\n{traceback.format_exc()}")
        finally:
            self.btn_ai_diagnose.setEnabled(True)
            self.btn_ai_diagnose.setText("🧠 AI 智能诊断")

    def _on_add_record(self):
        if not self.current_image_path:
            QMessageBox.warning(self, "提示", "请先导入照片")
            return

        disease = self.combo_disease_type.currentText()
        severity = self.combo_severity.currentText()
        position = self.edit_position.text().strip() or "未填写"
        size = self.edit_size.text().strip() or "未测量"
        note = self.edit_note.toPlainText().strip()

        record = {
            "id": str(uuid.uuid4())[:8],
            "photo": self.current_image_path,
            "component": self.combo_component.currentText(),
            "tunnel": self.edit_tunnel_name.text().strip() or "未命名隧道",
            "component_no": self.edit_component_no.text().strip() or "未编号",
            "disease": disease,
            "severity": severity,
            "position": position,
            "size": size,
            "note": note,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        self.records.append(record)
        self._refresh_table()

        # 清空输入
        self.edit_position.clear()
        self.edit_size.clear()
        self.edit_note.clear()

        self.btn_report.setEnabled(True)
        # 如果已获取选中组件，启用投影按钮
        if self._selected_component is not None:
            self.btn_project.setEnabled(True)
        QMessageBox.information(self, "已添加", f"已添加记录：{disease} ({severity})")

    def _refresh_table(self):
        self.table.setRowCount(len(self.records))
        for i, r in enumerate(self.records):
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(r["disease"]))
            self.table.setItem(i, 2, QTableWidgetItem(r.get("component", "")))
            self.table.setItem(i, 3, QTableWidgetItem(r["severity"]))
            self.table.setItem(i, 4, QTableWidgetItem(r["position"]))
            self.table.setItem(i, 5, QTableWidgetItem(r["size"]))
            self.table.setItem(i, 6, QTableWidgetItem(r["note"]))
        self.table.resizeColumnsToContents()
        self.lbl_count.setText(f"共 {len(self.records)} 条记录")

    # ============================================================
    # 标注图红框同步
    # ============================================================

    def _records_for_current_photo_with_bbox(self):
        """返回当前照片且带 bbox 的记录。"""
        return [r for r in self.records
                if r.get("photo") == self.current_image_path
                and r.get("bbox") is not None]

    def _draw_boxes_on_photo(self, photo_path, boxes_with_labels, output_path=None):
        """
        在原图上绘制若干 (bbox, label) 红框，返回输出路径。

        Args:
            photo_path: 原图路径
            boxes_with_labels: [(x1, y1, x2, y2, label), ...]
            output_path: 输出路径，None 则存临时目录
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return None

        try:
            img = Image.open(photo_path).convert('RGB')
        except Exception:
            return None

        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("simhei.ttf", 18)
        except Exception:
            try:
                font = ImageFont.truetype("msyh.ttf", 18)
            except Exception:
                font = ImageFont.load_default()

        for box in boxes_with_labels:
            x1, y1, x2, y2, label = box[:5]
            color = box[5] if len(box) > 5 else (255, 0, 0)   # 可选第 6 元素:框颜色(随病害类型)
            for t in range(3):
                draw.rectangle([x1 - t, y1 - t, x2 + t, y2 + t], outline=color, width=1)
            bbox_text = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox_text[2] - bbox_text[0], bbox_text[3] - bbox_text[1]
            draw.rectangle([x1, y1 - th - 6, x1 + tw + 6, y1], fill=color)
            draw.text((x1 + 3, y1 - th - 3), label, fill=(255, 255, 255), font=font)

        if output_path is None:
            import tempfile
            base = os.path.splitext(os.path.basename(photo_path))[0]
            output_path = os.path.join(tempfile.gettempdir(), f"{base}_sync.jpg")

        try:
            img.save(output_path, quality=95)
            return output_path
        except Exception:
            return None

    def _redraw_marked_image(self):
        """
        根据当前照片对应的剩余记录刷新红框显示（矢量叠加，可交互），
        并重新生成烘焙版标注图供 AI 诊断与报告使用。
        """
        if not self.current_image_path:
            return

        records = self._records_for_current_photo_with_bbox()
        boxes = []
        for r in records:
            x1, y1, x2, y2 = r["bbox"]
            disease = r.get('disease', '异常区域')
            boxes.append((x1, y1, x2, y2, disease, self._disease_rgb(disease)))

        # 烘焙版标注图（报告/AI 诊断用，不用于显示）
        if boxes:
            out = self._draw_boxes_on_photo(self.current_image_path, boxes)
            if out and os.path.exists(out):
                self.current_marked_image_path = out
                # 更新所有记录的 marked_image 指向新图
                for r in self.records:
                    if r.get("photo") == self.current_image_path:
                        r["marked_image"] = out
        else:
            self.current_marked_image_path = ""

        # 矢量叠加显示（点击/框选交互的基础）
        self._refresh_image_overlay()

        # 记录变化（识别/画框/删框）→ 刷新人工标注对照状态
        self._update_manual_status()

    @staticmethod
    def _disease_rgb(disease):
        """病害类型 → RGB 颜色(与投影 face_projection.DISEASE_COLOR_MAP 严格一致,未知类型绿色兜底)"""
        try:
            from face_projection import DISEASE_COLOR_MAP, _FALLBACK_COLOR
            return DISEASE_COLOR_MAP.get(disease, _FALLBACK_COLOR)
        except Exception:
            return (255, 0, 0)

    def _refresh_image_overlay(self):
        """把当前照片的病害框同步到可交互图片控件，并维护 框→记录 索引映射(框颜色随病害类型)"""
        boxes = []
        self._view_record_indices = []
        for i, r in enumerate(self.records):
            if r.get("photo") == self.current_image_path and r.get("bbox") is not None:
                x1, y1, x2, y2 = r["bbox"]
                disease = r.get("disease", "异常区域")
                boxes.append((x1, y1, x2, y2, disease, self._disease_rgb(disease)))
                self._view_record_indices.append(i)
        self.image_view.set_boxes(boxes)

    def _on_image_box_clicked(self, box_idx):
        """点击图片上的红框 → 选中对应记录（表格同步高亮）"""
        if 0 <= box_idx < len(self._view_record_indices):
            self.table.selectRow(self._view_record_indices[box_idx])

    def _on_image_selection_cleared(self):
        """图片上取消选中（再点一次选中的框/单击空白处）→ 表格同步取消"""
        self.table.clearSelection()

    def _on_table_selection_changed(self):
        """表格选中变化 → 高亮图片上对应的红框，并同步显示该记录的病害类型"""
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if rows and rows[0] in self._view_record_indices:
            self.image_view.set_selected(self._view_record_indices.index(rows[0]))
        else:
            self.image_view.set_selected(-1)
        # 左侧“病害类型”同步显示选中记录的病害类型
        if rows and 0 <= rows[0] < len(self.records):
            disease = self.records[rows[0]].get("disease", "")
            idx = self.combo_disease_type.findText(disease)
            if idx >= 0:
                self.combo_disease_type.setCurrentIndex(idx)
        # 状态区附加显示选中记录的 识别一致/误检 对照结果
        try:
            self._update_manual_status()
        except Exception:
            pass

    def _on_image_box_delete(self, box_idx):
        """图片上选中红框后按 Delete → 删除对应记录及红框"""
        if not (0 <= box_idx < len(self._view_record_indices)):
            return
        rec_idx = self._view_record_indices[box_idx]
        if 0 <= rec_idx < len(self.records):
            self.records.pop(rec_idx)
            self._refresh_table()
            self._redraw_marked_image()
            if not self.records:
                self.btn_report.setEnabled(False)

    def _on_image_box_drawn(self, bbox):
        """图片上手动框选 → 按左侧面板当前的病害类型/严重程度新增记录。

        位置坐标以照片左上角为原点，记录框中心像素坐标。
        """
        if not self.current_image_path:
            return
        x1, y1, x2, y2 = bbox
        w, h = x2 - x1, y2 - y1
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        disease = self.combo_disease_type.currentText()
        severity = self.combo_severity.currentText()

        # 合并左侧面板已填写的内容（坐标/像素尺寸保留，用户文本追加在后）
        user_pos = self.edit_position.text().strip()
        user_size = self.edit_size.text().strip()
        user_note = self.edit_note.toPlainText().strip()

        position = f"框中心 ({cx}, {cy}) 像素"
        if user_pos:
            position += f"；{user_pos}"
        size = f"约 {w}×{h} 像素"
        if user_size:
            size += f"；{user_size}"
        note = "手动框选添加"
        if user_note:
            note += f"；{user_note}"

        record = {
            "id": str(uuid.uuid4())[:8],
            "photo": self.current_image_path,
            "component": self.combo_component.currentText(),
            "tunnel": self.edit_tunnel_name.text().strip() or "未命名隧道",
            "component_no": self.edit_component_no.text().strip() or "未编号",
            "disease": disease,
            "severity": severity,
            "position": position,
            "size": size,
            "note": note,
            "bbox": (x1, y1, x2, y2),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ai_diagnosed": False,
            "ai_diagnosis": "",
        }
        self.records.append(record)
        self._refresh_table()
        self._redraw_marked_image()
        self.btn_report.setEnabled(True)
        if self._selected_component is not None:
            self.btn_project.setEnabled(True)

        # 清空输入（与【添加到列表】行为一致）
        self.edit_position.clear()
        self.edit_size.clear()
        self.edit_note.clear()

    def _on_clear_records(self):
        if not self.records:
            return
        reply = QMessageBox.question(self, "确认", "确定清空所有记录？")
        if reply == QMessageBox.Yes:
            self.records.clear()
            self._refresh_table()
            self._redraw_marked_image()
            self.btn_report.setEnabled(False)

    # AI 判定“非病害”的关键词（出现在 ai_diagnosis / note 中即认为非病害）
    _AI_NON_DISEASE_KEYWORDS = [
        "疑似正常",
        "正常纹理",
        "正常标记",
        "文字标记",
        "无明显病害",
        "非真实病害",
        "非病害",
        "非结构病害",
        "不属于病害",
    ]

    def _is_ai_non_disease(self, record: dict) -> bool:
        """判断记录是否被 AI 诊断为非病害（正常纹理/标记等）。"""
        if not record.get("ai_diagnosed", False):
            return False
        text = (record.get("ai_diagnosis", "") or "") + " " + (record.get("note", "") or "")
        return any(kw in text for kw in self._AI_NON_DISEASE_KEYWORDS)

    def _on_clean_ai_non_disease(self):
        """一键清理 AI 判定为非病害的记录。"""
        if not self.records:
            QMessageBox.information(self, "提示", "当前没有记录")
            return

        to_remove = [r for r in self.records if self._is_ai_non_disease(r)]
        if not to_remove:
            QMessageBox.information(
                self, "提示",
                "没有找到 AI 判定为非病害的记录。\n"
                "（需先执行【AI 智能诊断】，且诊断结论包含“疑似正常纹理/标记”等）"
            )
            return

        reply = QMessageBox.question(
            self, "确认清理",
            f"共找到 {len(to_remove)} 条 AI 判定为非病害的记录，确定删除？\n\n"
            f"删除后不可恢复。"
        )
        if reply != QMessageBox.Yes:
            return

        self.records = [r for r in self.records if not self._is_ai_non_disease(r)]
        self._refresh_table()
        self._redraw_marked_image()
        if not self.records:
            self.btn_report.setEnabled(False)
        QMessageBox.information(self, "完成", f"已清理 {len(to_remove)} 条 AI 判定非病害的记录")

    def _on_delete_selected_records(self):
        """手动删除表格中选中的记录。"""
        if not self.records:
            QMessageBox.information(self, "提示", "当前没有记录")
            return

        selected_rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            QMessageBox.information(self, "提示", "请先在表格中选中要删除的记录（可按住 Ctrl 多选）")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除选中的 {len(selected_rows)} 条记录？\n\n删除后不可恢复。"
        )
        if reply != QMessageBox.Yes:
            return

        for row in selected_rows:
            if 0 <= row < len(self.records):
                del self.records[row]

        self._refresh_table()
        self._redraw_marked_image()
        if not self.records:
            self.btn_report.setEnabled(False)

    def _on_cleanup(self):
        """一键清理：弹出清理对话框（复用 一键清理_launcher 的界面与逻辑）"""
        try:
            import importlib.util
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "一键清理_launcher.py")
            spec = importlib.util.spec_from_file_location("clean_launcher", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod._run_with_qt()
        except Exception as e:
            QMessageBox.warning(self, "一键清理", f"打开清理界面失败: {e}")

    def _on_auto_setup_env(self):
        """一键环境自检/配置：补 pip → 修 _pth → 装依赖 → 验证导入。

        面向插件分发：别人拿到 .pyplugin 包后，BIMBase 内置 Python
        通常缺 torch/ultralytics 等依赖，点这个按钮自动补齐。
        """
        reply = QMessageBox.question(
            self, "自动配置环境",
            "将检查并自动安装病害识别所需依赖：\n"
            "  torch(CPU) / ultralytics 8.0.145 / opencv / Pillow / numpy 等\n\n"
            "  • 安装约需 10~30 分钟（取决于网络），期间请保持联网\n"
            "  • 若 BIMBase 装在需要管理员权限的目录，可能需以管理员身份运行\n\n"
            "是否继续？")
        if reply != QMessageBox.Yes:
            return

        from PyQt5.QtWidgets import QProgressDialog, QApplication
        import env_setup

        self.btn_env_setup.setEnabled(False)
        prog = QProgressDialog("正在配置环境...", None, 0, 0, self)
        prog.setWindowTitle("自动配置环境")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)
        prog.setMinimumWidth(480)
        prog.show()

        report_lines = []

        def _log(msg):
            report_lines.append(msg)
            prog.setLabelText(msg if len(msg) <= 90 else "..." + msg[-87:])
            prog.setValue(prog.value() + 1)   # 让进度条保持活动
            QApplication.processEvents()

        try:
            ok, report = env_setup.auto_setup(log_cb=_log)
        except Exception as e:
            ok, report = False, f"配置过程异常: {e}"
        finally:
            prog.close()

        # 全量报告写入日志，便于排查
        try:
            _dbg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "tunnel_disease_debug.log")
            with open(_dbg_path, "a", encoding="utf-8") as f:
                f.write("\n===== 自动配置环境 =====\n" + report + "\n")
        except Exception:
            pass

        self.btn_env_setup.setEnabled(True)
        if ok:
            QMessageBox.information(
                self, "环境配置完成",
                "✓ 依赖已就绪，识别功能可用。\n\n"
                "（若首次使用仍提示缺库，请重启 BIMBase 后再试）\n\n"
                "详细日志见 tunnel_disease_debug.log")
        else:
            QMessageBox.warning(
                self, "环境配置未完成",
                "部分依赖安装失败，可联网后重试本按钮。\n\n"
                "详细日志见 tunnel_disease_debug.log\n\n"
                "----- 报告尾部 -----\n" + "\n".join(report_lines[-12:]))

    def _on_export_web_data(self):
        """导出网页可视化数据 JSON（含压缩照片 base64），供「隧道数字孪生.html」导入。"""
        if not self.records:
            QMessageBox.warning(self, "提示", "请先添加至少一条病害记录")
            return
        default_name = f"隧道病害网页数据_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出网页数据", default_name, "JSON (*.json)")
        if not path:
            return

        # 隧道参数：优先取已获取组件的实际参数，否则用默认值
        defaults = {'隧道净宽': 10000, '拱仰厚度': 5000, '二次衬砌厚度': 350,
                    '底部高度': 800, '隧道长度': 50000}
        tunnel = dict(defaults)
        if self._selected_component:
            p = self._selected_component.get('params') or {}
            for k in defaults:
                try:
                    if k in p:
                        tunnel[k] = float(p[k])
                except (ValueError, TypeError):
                    pass

        recs = []
        skipped_photo = 0
        for r in self.records:
            item = {
                "id": r.get("id", ""),
                "disease": r.get("disease", "其他"),
                "severity": r.get("severity", ""),
                "component": r.get("component", "衬砌"),
                "component_no": r.get("component_no", ""),
                "position": r.get("position", ""),
                "size": r.get("size", ""),
                "note": r.get("note", ""),
                "ai_diagnosis": r.get("ai_diagnosis", ""),
                "time": r.get("time", ""),
            }
            bbox = r.get("bbox")
            photo = r.get("photo", "")
            if photo:
                # 照片文件名（含桩号），网页据此沿隧道定位病害
                item["photo_name"] = os.path.basename(photo)
            if bbox and len(bbox) == 4 and photo and os.path.exists(photo):
                item["bbox"] = [float(bbox[0]), float(bbox[1]),
                                float(bbox[2]), float(bbox[3])]
                try:
                    import base64
                    import io as _io
                    from PIL import Image
                    with Image.open(photo) as im:
                        im = im.convert("RGB")
                        w, h = im.size
                        item["photo_w"], item["photo_h"] = w, h
                        scale = 720.0 / max(w, h)
                        if scale < 1.0:
                            im = im.resize((max(1, int(w * scale)),
                                            max(1, int(h * scale))),
                                           Image.LANCZOS)
                        buf = _io.BytesIO()
                        im.save(buf, "JPEG", quality=72)
                        item["photo"] = ("data:image/jpeg;base64,"
                                         + base64.b64encode(buf.getvalue()).decode("ascii"))
                except Exception:
                    skipped_photo += 1
            else:
                if bbox and len(bbox) == 4:
                    item["bbox"] = [float(bbox[0]), float(bbox[1]),
                                    float(bbox[2]), float(bbox[3])]
                skipped_photo += 1
            recs.append(item)

        data = {
            "app": "隧道病害识别",
            "version": 1,
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tunnel_name": self.edit_tunnel_name.text().strip() or "未命名隧道",
            "face": self.combo_face.currentText() or "拱圈内壁",
            "tunnel": tunnel,
            "records": recs,
        }
        try:
            import json
            import io as _io
            with _io.open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            msg = (f"已导出 {len(recs)} 条记录到：\n{path}\n\n"
                   f"用「隧道数字孪生.html」导入此文件即可 3D 可视化。")
            if skipped_photo:
                msg += f"\n\n（{skipped_photo} 张照片读取失败，已跳过照片仅保留记录）"
            QMessageBox.information(self, "导出成功", msg)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"写入文件失败：\n{e}")

    def _on_generate_report(self):
        if not self.records:
            QMessageBox.warning(self, "提示", "请先添加至少一条病害记录")
            return

        # 组装为MarkerRecord格式
        # 为每条带 bbox 的记录生成“单独红框”图片，报告中一条记录对应一张红框图+建议
        import tempfile
        mr_list = []
        for idx, r in enumerate(self.records, 1):
            severity = r.get("severity", "轻微")
            confidence = {"轻微": 0.3, "中等": 0.55, "严重": 0.8, "极严重": 0.95}.get(severity, 0.5)

            bbox = r.get("bbox")
            marked_path = r.get("marked_image", "")
            photo_path = r.get("photo", "")

            # 如果有 bbox 和原图，生成只含该记录彩框的单独图片(颜色随病害类型,与投影一致)
            if bbox is not None and photo_path and os.path.exists(photo_path):
                x1, y1, x2, y2 = bbox
                disease = r.get('disease', '异常区域')
                label = f"{disease} #{idx}"
                out_path = os.path.join(
                    tempfile.gettempdir(),
                    f"disease_single_{r['id']}.jpg"
                )
                single = self._draw_boxes_on_photo(
                    photo_path, [(x1, y1, x2, y2, label, self._disease_rgb(disease))], output_path=out_path
                )
                if single and os.path.exists(single):
                    marked_path = single

            mr_list.append(MarkerRecord(
                record_id=r["id"],
                photo_path=photo_path,
                component_type=r["component"],
                component_key=r["component_no"],
                disease_class=r["disease"],
                confidence=confidence,
                bbox=tuple(bbox) if bbox is not None else (0, 0, 0, 0),
                marker_x=0, marker_y=0, marker_z=0,
                created_at=r["time"],
                marked_image_path=marked_path,
                ai_diagnosis=r.get("ai_diagnosis", ""),
                ai_diagnosed=r.get("ai_diagnosed", False),
                severity=severity,
            ))

        default_name = f"隧道病害诊断报告_{datetime.now().strftime('%Y%m%d')}.docx"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存报告", default_name, "Word文档 (*.docx)"
        )
        if not path:
            return

        # 详细日志帮助排查
        _log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_disease_debug.log")
        def _local_log(msg):
            try:
                from datetime import datetime
                ts = datetime.now().strftime("%H:%M:%S")
                with open(_log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{ts}] [REPORT] {msg}\n")
            except Exception:
                pass

        _local_log(f"开始生成报告，路径={path}，记录数={len(mr_list)}")

        try:
            gen = ReportGenerator()
            tunnel = self.edit_tunnel_name.text().strip() or "未命名隧道"
            gen.set_project_info("隧道定期检测项目", tunnel)
            _local_log("ReportGenerator initialized")

            ok = gen.generate(mr_list, path)
            _local_log(f"generate() returned {ok}")

            if ok:
                QMessageBox.information(self, "完成", f"报告已生成：\n{path}")
            else:
                QMessageBox.critical(self, "失败", "报告生成失败，请查看 tunnel_disease_debug.log 获取详情")
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            _local_log(f"EXCEPTION: {e}\n{err}")
            QMessageBox.critical(self, "失败", f"报告生成异常:\n{e}\n\n日志: {_log_path}")

    # ============ BIMBase扫描与投影 ============

    def _on_test_place(self):
        """直接投影测试：在固定位置放置红色大标记，不依赖选中组件"""
        try:
            from disease_marker import DiseaseMarkerComponent
            comp = DiseaseMarkerComponent.create_component(0, 0, 500, size=500.0)
            if comp is None:
                QMessageBox.critical(self, "失败", "pyp3d不可用，无法创建组件。\n\n请确认在BIMBase环境中运行。")
                return
            
            # 尝试多种放置方式
            errors = []
            
            # 方式1: place_to(x, y, z, component) — 直接放置到指定位置
            try:
                from bimbase_sync import place_to
                place_to(0, 0, 500, comp)
                QMessageBox.information(self, "投影成功", 
                    "✅ 红色标记已放置到BIMBase！\n\n位置: (0, 0, 500)\n大小: 500mm\n\n"
                    "请在BIMBase视图中查看是否出现大方块。\n"
                    "如果没看见，请尝试缩放视图或切换视角。")
                return
            except Exception as e:
                errors.append(f"place_to(0,0,500,comp): {e}")
            
            # 方式2: place_to(component, x, y, z)
            try:
                from bimbase_sync import place_to
                place_to(comp, 0, 0, 500)
                QMessageBox.information(self, "投影成功", 
                    "✅ 红色标记已放置（方式2）！\n\n位置: (0, 0, 500)\n大小: 500mm")
                return
            except Exception as e:
                errors.append(f"place_to(comp,0,0,500): {e}")
            
            # 方式3: 普通 place（可能进入交互模式）
            try:
                from bimbase_sync import place
                place(comp)
                QMessageBox.information(self, "投影成功", 
                    "✅ place() 调用成功（可能进入交互放置模式）。\n\n"
                    "如果BIMBase提示你放置组件，请在视图中点击确认位置。")
                return
            except Exception as e:
                errors.append(f"place(comp): {e}")
            
            # 全部失败
            QMessageBox.critical(self, "投影失败", 
                "所有放置方式都失败了:\n\n" + "\n".join(errors))
                
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "投影失败", 
                f"放置红色标记时出错:\n{e}\n\n{traceback.format_exc()}")

    def _extract_params_from_dk(self, dk):
        """从 datakey 提取组件参数（内部辅助）"""
        try:
            from bimbase_sync import get_noumKV_from_instancekey, get_noumenon_from_instancekey
            raw = get_noumKV_from_instancekey(dk)
            params = None
            if raw and isinstance(raw, dict):
                if 'ParaCmptProperty' in raw:
                    p = raw['ParaCmptProperty']
                    if p is not None and hasattr(p, 'keys'):
                        inner = {key: p[key] for key in p}
                    elif p is not None and isinstance(p, dict):
                        inner = dict(p)
                    else:
                        inner = {}
                    # 顶层键（Placement/BaseTransform 等）必须保留，否则组件被移动后
                    # 拿不到真实世界坐标，投影会落到原点
                    params = {**raw, **inner}
                else:
                    params = dict(raw)
                # 从 Placement/BaseTransform 提取实际世界坐标（参数化组件经 transformation
                # 放置后 x/y 隐藏属性常为 0），写回 x/y/z_bottom 供 _estimate_base_position
                # 使用。与 速构智维/bimbase_sync.py 的成熟做法保持一致。
                for _pk in ('Placement', 'BaseTransform'):
                    if _pk in params:
                        xyz = DiseaseDialog._extract_xyz_robust(params.get(_pk))
                        if xyz is not None:
                            params['x'], params['y'], params['z_bottom'] = xyz
                            break
            elif raw and hasattr(raw, 'keys'):
                # 部分 SDK 返回的是类 dict 对象而非 dict
                try:
                    params = {key: raw[key] for key in raw.keys()}
                except Exception:
                    params = None
                if params:
                    for _pk in ('Placement', 'BaseTransform'):
                        if _pk in params:
                            xyz = DiseaseDialog._extract_xyz_robust(params.get(_pk))
                            if xyz is not None:
                                params['x'], params['y'], params['z_bottom'] = xyz
                                break

            if not params and get_noumenon_from_instancekey is not None:
                try:
                    noumenon = get_noumenon_from_instancekey(dk)
                    if noumenon is not None:
                        params = {}
                        try:
                            prop = noumenon.at('ParaCmptProperty')
                            if prop is not None and hasattr(prop, 'keys'):
                                for key in prop:
                                    params[key] = prop[key]
                            elif prop is not None and isinstance(prop, dict):
                                params = dict(prop)
                        except Exception:
                            pass
                except Exception:
                    pass
            return params
        except Exception:
            return None

    def _scan_all_components(self, max_scan=200, use_cache=True, progress_cb=None):
        """
        扫描所有 instance key，返回全部可识别构件的列表 [(comp_type, params, dk), ...]。

        说明：BIMBase 中选中的实体通常是"参数化组件代理"，拿不到参数，
        所以选中组件的识别只能依靠全量扫描（与本目录 bimbase_sync.py 一致）。

        性能：每个实例的 get_noumKV 都是一次 SDK 调用，200 个实例逐个读
        是"获取组件慢"的主要原因。这里按场景实例总数做签名缓存——场景
        实例数量不变时直接复用上次扫描结果（再次获取从十几秒降到瞬间）；
        实例数变化（增删构件）时自动全量重扫。命中缓存后选中组件的参数
        会在使用处单独刷新一次，避免移动组件后坐标过期。
        """
        results = []
        try:
            from bimbase_sync import get_all_instancekey
            from bimbase_query import infer_tunnel_component_type
            keys = get_all_instancekey()
            if not keys:
                return results

            sig = len(keys)
            if (use_cache and self._scan_cache is not None
                    and self._scan_cache.get('sig') == sig):
                return list(self._scan_cache['matches'])

            # 签名表之外的组件（投影测试构件等）用的兜底关键词
            interest_keys = {'长度', '宽度', '高度', '边长', '半径', '直径', '厚度',
                             'x', 'y', 'z_bottom', 'z_top', '埋深', '净宽', '净高', '坡度'}

            total = min(len(keys), max_scan)
            for idx, k in enumerate(keys[:max_scan], 1):
                try:
                    params = self._extract_params_from_dk(k)
                    if not params or not isinstance(params, dict) or len(params) == 0:
                        continue
                    comp_type = infer_tunnel_component_type(params)
                    if not comp_type:
                        keys_set = set(str(kk) for kk in params.keys() if isinstance(kk, str))
                        if not (keys_set & interest_keys):
                            continue
                        comp_type = "未知类型"
                    results.append((comp_type, params, k))
                except Exception:
                    pass
                # 每 10 个实例让出一次事件循环，更新进度，避免界面长时间未响应
                if progress_cb is not None and (idx % 10 == 0 or idx == total):
                    try:
                        progress_cb(idx, total)
                    except Exception:
                        pass
            self._scan_cache = {'sig': sig, 'matches': list(results)}
        except Exception:
            pass
        return results

    def _refresh_component_params(self, comp_type, params, dk):
        """命中扫描缓存后，单独刷新某个组件的参数（一次 SDK 调用）。

        缓存命中只说明场景构件数量没变，组件可能被移动/改过参数，
        使用前必须重新读取该组件的真实参数；读取失败（实例已删除等情况）
        时使缓存失效并返回 None，调用方应回退到全量重扫。
        """
        try:
            fresh = self._extract_params_from_dk(dk)
            if fresh and isinstance(fresh, dict) and len(fresh) > 0:
                return fresh
        except Exception:
            pass
        self._scan_cache = None
        return None

    def _scan_all_instances_for_params(self, prefer_keys=None):
        """
        扫描所有 instance key，返回第一个有参数的实例。
        如果提供了 prefer_keys（参数键名集合），优先匹配包含这些键的实例。
        """
        try:
            from bimbase_sync import get_all_instancekey
            keys = get_all_instancekey()
            if not keys:
                return None, None

            interest_keys = {'长度', '宽度', '高度', '边长', '半径', '直径', '厚度',
                             'x', 'y', 'z_bottom', 'z_top', '埋深', '净宽', '净高'}
            if prefer_keys:
                interest_keys = interest_keys | set(prefer_keys)

            for k in keys[:100]:  # 最多扫描100个，避免太慢
                try:
                    params = self._extract_params_from_dk(k)
                    if params and isinstance(params, dict) and len(params) > 0:
                        keys_set = set(str(kk) for kk in params.keys() if isinstance(kk, str))
                        if keys_set & interest_keys:
                            return params, k
                except Exception:
                    pass
            return None, None
        except Exception:
            return None, None

    def _on_get_selected(self):
        """获取BIMBase当前选中的组件（多策略回退版）"""
        _log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_disease_debug.log")
        def _dbg(msg):
            from datetime import datetime
            try:
                with open(_log_path, "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [SEL] {msg}\n")
            except Exception:
                pass

        _dbg("=" * 50)
        _dbg("_on_get_selected started")

        # 导入API
        try:
            from bimbase_sync import (
                get_current_entityId, get_datakey_from_entity,
                get_noumKV_from_instancekey, get_noumenon_from_instancekey,
                get_all_instancekey
            )
            _dbg("API imported OK")
        except Exception as e:
            _dbg(f"API import FAILED: {e}")
            QMessageBox.warning(self, "API不可用", f"无法导入BIMBase查询API: {e}")
            return

        self.lbl_scan_result.setText("正在获取选中组件...")

        params = None
        dk = None

        # ===== 策略1：通过当前选中的 entityId 获取 datakey =====
        try:
            eid = get_current_entityId()
            _dbg(f"get_current_entityId() returned type={type(eid).__name__ if eid is not None else 'None'}")
        except Exception as e:
            _dbg(f"get_current_entityId() FAILED: {e}")
            eid = None

        if eid is not None:
            try:
                dk = get_datakey_from_entity(eid)
                _dbg(f"get_datakey_from_entity returned type={type(dk).__name__ if dk is not None else 'None'}")
            except Exception as e:
                _dbg(f"get_datakey_from_entity FAILED: {e}")
                dk = None

            if dk is not None:
                params = self._extract_params_from_dk(dk)
                if params:
                    _dbg(f"Strategy1 success: params keys={list(params.keys())[:10]}")

        # ===== 策略2：策略1拿到的是代理实体，扫描所有 instance key =====
        if not params:
            if self._scanning:
                self.lbl_scan_result.setText("正在扫描中，请稍候...")
                return
            self._scanning = True
            _dbg("Strategy1 failed (proxy entity), fallback to scanning all instances...")
            try:
                from PyQt5.QtWidgets import QApplication
                cached = (self._scan_cache is not None)
                self.lbl_scan_result.setText("正在扫描场景构件（首次较慢，结果会缓存）...")

                def _progress(idx, total):
                    self.lbl_scan_result.setText(f"正在扫描场景构件... {idx}/{total}")
                    QApplication.processEvents()

                matches = self._scan_all_components(progress_cb=_progress)
                _dbg(f"Strategy2 scan found {len(matches)} recognizable component(s) "
                     f"({'cache hit' if cached else 'full scan'})")
                if len(matches) == 1:
                    _ct, params, dk = matches[0]
                    _dbg(f"Strategy2 success: type={_ct} params keys={list(params.keys())[:10]}")
                elif len(matches) > 1:
                    # 多个可识别构件：让用户选择目标
                    items = []
                    for _ct, _p, _k in matches:
                        try:
                            _pos = self._get_component_base_pos(_p, _k)
                        except Exception:
                            _pos = (0.0, 0.0, 0.0)
                        items.append(
                            f"{_ct}   位置({ _pos[0]:.0f}, {_pos[1]:.0f}, {_pos[2]:.0f})"
                        )
                    choice, ok = QInputDialog.getItem(
                        self, "选择目标构件",
                        f"场景中检测到 {len(matches)} 个可识别构件，\n请选择要投影的目标：",
                        items, 0, False
                    )
                    if ok and choice in items:
                        _ct, params, dk = matches[items.index(choice)]
                        _dbg(f"User picked: {_ct}")
                    else:
                        self.lbl_scan_result.setText("已取消选择")
                        return

                # 命中缓存时参数可能是旧值（组件被移动/修改过），单独刷新一次
                if params and cached and dk is not None:
                    fresh = self._refresh_component_params(_ct, params, dk)
                    if fresh is not None:
                        params = fresh
                    elif self._scan_cache is None:
                        # 刷新失败且缓存已失效（实例被删等）：全量重扫一次
                        _dbg("cached params refresh failed, rescanning...")
                        matches = self._scan_all_components(use_cache=False,
                                                            progress_cb=_progress)
                        if matches:
                            _ct, params, dk = matches[0]
            except Exception as e:
                _dbg(f"Strategy2 scan failed: {e}")
            finally:
                self._scanning = False

        if not params or not isinstance(params, dict):
            QMessageBox.warning(self, "无参数",
                "无法读取选中组件的参数，且全场景扫描也未找到可识别的参数化构件。\n\n可能原因:\n"
                "1. 场景中的构件不是参数化组件（无参数）\n"
                "2. 构件参数特征不在识别范围内\n"
                "3. BIMBase API暂时不可用\n\n"
                "建议: 确认已用隧道组件放置参数化构件后重试。")
            self.lbl_scan_result.setText("获取失败: 无法读取参数")
            return

        param_keys = [pk for pk in params.keys() if isinstance(pk, str)]
        _dbg(f"Param keys: {param_keys}")

        # 匹配构件类型
        from bimbase_query import infer_tunnel_component_type
        comp_type = infer_tunnel_component_type(params)
        if not comp_type:
            comp_type = "未知类型"
            _dbg(f"No component type match for keys: {param_keys}")

        _dbg(f"Matched component type: {comp_type}")

        # 保存选中组件
        self._selected_component = {
            'key': dk,
            'params': params,
            'comp_type': comp_type,
        }

        # 回填基准坐标，便于用户核对（仅在自动读到非原点坐标且输入框为空时）
        try:
            bp = self._get_component_base_pos(params, dk)
            if bp != (0.0, 0.0, 0.0) and not self.edit_base_pos.text().strip():
                self.edit_base_pos.setText(f"{bp[0]:.1f},{bp[1]:.1f},{bp[2]:.1f}")
        except Exception:
            pass

        # 更新UI
        old_comp = self.combo_component.currentText()
        idx = self.combo_component.findText(comp_type)
        if idx >= 0:
            self.combo_component.setCurrentIndex(idx)

        # 按构件类型填充投影面下拉框
        try:
            from face_projection import get_available_faces
            faces = get_available_faces(comp_type)
            self.combo_face.clear()
            if faces:
                self.combo_face.addItems(faces)
        except Exception:
            pass

        info = f"已获取: {comp_type}\n参数: {', '.join(param_keys[:6])}"
        self.lbl_scan_result.setText(info)

        if self.records:
            self.btn_project.setEnabled(True)

        # 构件类型变化会影响后续新增记录的归属(已有记录保持识别时的类型不变)
        change_note = ""
        if idx >= 0 and comp_type != old_comp:
            change_note = (f"\n\n注意: 构件类型已从「{old_comp}」切换为「{comp_type}」,"
                           f"后续新增记录将归属「{comp_type}」;\n"
                           f"已有记录的构件类型保持不变(见记录表「构件类型」列)。")

        QMessageBox.information(self, "获取成功",
            f"已获取选中组件！\n\n类型: {comp_type}\n参数: {', '.join(param_keys)}{change_note}")
        _dbg("_on_get_selected completed successfully")

    def _on_face_project(self):
        """面投影测试：在选中构件的默认面上生成模拟病害阴影"""
        try:
            # 如果没有已获取的组件，尝试自动获取当前选中
            if self._selected_component is None:
                self._auto_get_selected()
                if self._selected_component is None:
                    QMessageBox.information(
                        self, "提示",
                        "请先点击【获取当前选中组件】获取BIMBase中的组件，\n"
                        "或确保BIMBase中已选中一个构件后再点击此按钮。"
                    )
                    return

            comp_type = self._selected_component.get("comp_type", "")
            params = self._selected_component.get("params", {})

            # 支持的基本几何体（组件测试中的类型）
            supported = {'长方体', '正方体', '圆柱', '直角三棱柱'}
            if comp_type not in supported:
                QMessageBox.warning(
                    self, "不支持",
                    f"当前组件类型 [{comp_type}] 暂不支持面投影测试。\n"
                    f"支持的类型: {', '.join(supported)}"
                )
                return

            # 估算构件基准位置（从参数中提取 x/y/z）
            base_pos = self._estimate_base_position(params)

            # 创建投影引擎
            from face_projection import FaceProjectionEngine
            engine = FaceProjectionEngine(comp_type, params, base_pos)

            # 生成模拟阴影（固定种子保证可重复）
            shadows = engine.generate_simulated_shadows(count=3, seed=42)
            if not shadows:
                QMessageBox.warning(self, "失败", "无法生成阴影区域，请检查构件参数。")
                return

            face = engine.get_face_info()

            # 逐个放置阴影薄片
            placed = 0
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            if plugin_dir not in sys.path:
                sys.path.insert(0, plugin_dir)

            from disease_marker import DiseaseMarkerComponent
            from bimbase_sync import place_to, translate as _translate

            for shadow in shadows:
                wx, wy, wz, ww, wh, wt, axis = engine.shadow_to_world(
                    face, shadow, thickness=2.0
                )
                marker = DiseaseMarkerComponent.create_shadow_marker(
                    x=wx, y=wy, z=wz,
                    width=ww, height=wh, thickness=wt,
                    color_r=shadow.color_rgb[0],
                    color_g=shadow.color_rgb[1],
                    color_b=shadow.color_rgb[2],
                    axis=axis,
                )
                if marker is not None:
                    # 自动放置到计算位置（非交互模式）
                    # place_to 正确用法: place_to(component, translate(x,y,z))
                    original_argv0 = sys.argv[0]
                    sys.argv[0] = os.path.join(plugin_dir, 'bimbase_sync.py')
                    try:
                        # 几何已烘焙世界坐标，用零变换放置，避免平移应用两次
                        place_to(marker, _translate(0, 0, 0))
                        placed += 1
                    except Exception as e:
                        # place_to 失败时回退到普通 place（会进入手动放置模式）
                        try:
                            from bimbase_sync import place
                            place(marker)
                            placed += 1
                        except Exception:
                            pass
                    finally:
                        sys.argv[0] = original_argv0

            # 汇总提示
            color_names = ", ".join(
                f"{s.disease_type}({s.color_rgb[0]},{s.color_rgb[1]},{s.color_rgb[2]})"
                for s in shadows
            )
            QMessageBox.information(
                self, "投影完成",
                f"已在 [{comp_type}] 的 [{face.face_name}] 面上生成 {placed} 个模拟病害阴影。\n\n"
                f"基准位置: ({base_pos[0]:.1f}, {base_pos[1]:.1f}, {base_pos[2]:.1f})\n"
                f"面尺寸: {face.width:.1f} × {face.height:.1f}\n"
                f"病害类型: {color_names}\n\n"
                f"请在BIMBase视图中查看效果。"
            )

        except Exception as e:
            import traceback
            QMessageBox.critical(
                self, "投影失败",
                f"面投影测试出错:\n{e}\n\n{traceback.format_exc()}"
            )

    def _on_texture_project(self):
        """纹理贴图测试：生成PNG纹理并贴到构件表面"""
        try:
            if self._selected_component is None:
                self._auto_get_selected()
                if self._selected_component is None:
                    QMessageBox.information(
                        self, "提示",
                        "请先点击【获取当前选中组件】获取BIMBase中的组件。"
                    )
                    return

            comp_type = self._selected_component.get("comp_type", "")
            params = self._selected_component.get("params", {})
            supported = {'长方体', '正方体', '圆柱', '直角三棱柱'}
            if comp_type not in supported:
                QMessageBox.warning(self, "不支持",
                    f"当前组件类型 [{comp_type}] 暂不支持。支持的类型: {', '.join(supported)}")
                return

            base_pos = self._estimate_base_position(params)
            from face_projection import FaceProjectionEngine, generate_disease_texture, ShadowRegion
            engine = FaceProjectionEngine(comp_type, params, base_pos)
            shadows = engine.generate_simulated_shadows(count=3, seed=42)
            if not shadows:
                QMessageBox.warning(self, "失败", "无法生成阴影区域")
                return

            face = engine.get_face_info()

            # 生成PNG纹理
            tex_path = generate_disease_texture(
                face.width, face.height, shadows, alpha=160
            )
            if not tex_path:
                QMessageBox.warning(self, "失败", "无法生成纹理图片（PIL不可用）")
                return

            # 创建纹理标记并放置（用虚拟ShadowRegion覆盖整个面）
            wx, wy, wz, ww, wh, wt, axis = engine.shadow_to_world(
                face, ShadowRegion(0, 0, face.width, face.height, "纹理", (255,255,255)),
                thickness=2.0
            )

            from disease_marker import DiseaseMarkerComponent
            marker = DiseaseMarkerComponent.create_texture_marker(
                x=wx, y=wy, z=wz,
                width=face.width, height=face.height, thickness=2.0,
                texture_path=tex_path, axis=axis
            )

            if marker is not None:
                plugin_dir = os.path.dirname(os.path.abspath(__file__))
                if plugin_dir not in sys.path:
                    sys.path.insert(0, plugin_dir)
                from bimbase_sync import place_to, translate as _translate
                original_argv0 = sys.argv[0]
                sys.argv[0] = os.path.join(plugin_dir, 'bimbase_sync.py')
                try:
                    # 几何已烘焙世界坐标，用零变换放置，避免平移应用两次
                    place_to(marker, _translate(0, 0, 0))
                    QMessageBox.information(
                        self, "纹理贴图完成",
                        f"已在 [{comp_type}] 的 [{face.face_name}] 面上贴附纹理。\n\n"
                        f"纹理路径: {tex_path}\n"
                        f"面尺寸: {face.width:.1f} × {face.height:.1f}\n\n"
                        f"如果显示为白色，可能是BIMBase纹理映射模式不兼容当前几何体。"
                    )
                except Exception as e:
                    QMessageBox.critical(self, "放置失败", f"纹理贴图放置失败:\n{e}")
                finally:
                    sys.argv[0] = original_argv0
            else:
                QMessageBox.warning(self, "失败", "纹理标记创建失败")

        except Exception as e:
            import traceback
            QMessageBox.critical(self, "纹理贴图失败",
                f"纹理贴图测试出错:\n{e}\n\n{traceback.format_exc()}")

    def _on_pointcloud_project(self):
        """点云投影测试：在构件表面生成大量彩色小点"""
        try:
            if self._selected_component is None:
                self._auto_get_selected()
                if self._selected_component is None:
                    QMessageBox.information(
                        self, "提示",
                        "请先点击【获取当前选中组件】获取BIMBase中的组件。"
                    )
                    return

            comp_type = self._selected_component.get("comp_type", "")
            params = self._selected_component.get("params", {})
            supported = {'长方体', '正方体', '圆柱', '直角三棱柱'}
            if comp_type not in supported:
                QMessageBox.warning(self, "不支持",
                    f"当前组件类型 [{comp_type}] 暂不支持。支持的类型: {', '.join(supported)}")
                return

            base_pos = self._estimate_base_position(params)
            from face_projection import FaceProjectionEngine, PointCloudGenerator
            engine = FaceProjectionEngine(comp_type, params, base_pos)
            shadows = engine.generate_simulated_shadows(count=3, seed=42)
            if not shadows:
                QMessageBox.warning(self, "失败", "无法生成阴影区域")
                return

            face = engine.get_face_info()

            # 生成点云
            pc_gen = PointCloudGenerator(density=8.0, point_size=4.0)
            point_count = pc_gen.estimate_point_count(shadows)
            if point_count > 5000:
                reply = QMessageBox.question(
                    self, "点数量过多",
                    f"预计生成 {point_count} 个点，可能导致BIMBase卡顿。\n是否继续？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

            points = pc_gen.generate(face, shadows)
            if not points:
                QMessageBox.warning(self, "失败", "无法生成点云")
                return

            # 创建点云标记
            from disease_marker import DiseaseMarkerComponent
            marker = DiseaseMarkerComponent.create_point_cloud_marker(
                x=face.center[0], y=face.center[1], z=face.center[2],
                points=points, point_size=4.0, face_plane=face.plane
            )

            if marker is not None:
                plugin_dir = os.path.dirname(os.path.abspath(__file__))
                if plugin_dir not in sys.path:
                    sys.path.insert(0, plugin_dir)
                from bimbase_sync import place_to, translate as _translate
                original_argv0 = sys.argv[0]
                sys.argv[0] = os.path.join(plugin_dir, 'bimbase_sync.py')
                try:
                    # 几何已烘焙世界坐标，用零变换放置，避免平移应用两次
                    place_to(marker, _translate(0, 0, 0))
                    QMessageBox.information(
                        self, "点云投影完成",
                        f"已在 [{comp_type}] 的 [{face.face_name}] 面上生成 {len(points)} 个彩色小点。\n\n"
                        f"面尺寸: {face.width:.1f} × {face.height:.1f}\n"
                        f"点大小: 4.0mm, 间距: 8.0mm\n\n"
                        f"如果BIMBase卡顿，建议减少点密度。"
                    )
                except Exception as e:
                    QMessageBox.critical(self, "放置失败", f"点云放置失败:\n{e}")
                finally:
                    sys.argv[0] = original_argv0
            else:
                QMessageBox.warning(self, "失败", "点云标记创建失败")

        except Exception as e:
            import traceback
            QMessageBox.critical(self, "点云投影失败",
                f"点云投影测试出错:\n{e}\n\n{traceback.format_exc()}")

    def _on_disease_project(self):
        """统一病害投影入口（异常兜底：任何未捕获异常都弹窗提示，避免卡死/静默）。"""
        from disease_marker import _log as _marker_log
        try:
            self._do_disease_project()
        except Exception as e:
            import traceback
            _marker_log(f"病害投影未捕获异常: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(
                self, "病害投影失败",
                f"投影过程出现异常:\n{e}\n\n{traceback.format_exc()}"
            )

    def _do_disease_project(self):
        """统一病害投影实现：将带检测框的病害记录按真实 bbox 等比映射到选中构件的指定面。

        当前支持的构件与投影面以 face_projection.FACE_REGISTRY 注册为准
        （隧道构件：衬砌、路面、洞门、检修道、排水）。
        标记样式：彩色半透明阴影薄片，每条病害记录一个薄片，颜色按病害类型。
        比例标定：等比铺满整面（假设照片取景范围≈目标面），位置大致准确。
        """
        if self._selected_component is None:
            self._auto_get_selected()
            if self._selected_component is None:
                QMessageBox.information(
                    self, "提示",
                    "请先点击【获取当前选中组件】获取BIMBase中的组件，\n"
                    "或确保BIMBase中已选中一个构件后再点击此按钮。"
                )
                return

        comp_type = self._selected_component.get("comp_type", "")
        params = self._selected_component.get("params", {})
        dk = self._selected_component.get("key")

        from face_projection import (
            FaceProjectionEngine, get_available_faces, photo_bbox_to_shadow
        )

        faces = get_available_faces(comp_type)
        if not faces:
            QMessageBox.information(
                self, "病害投影",
                f"当前构件类型 [{comp_type}] 暂不支持真实病害投影。\n"
                f"支持的构件类型以 face_projection.FACE_REGISTRY 注册为准。"
            )
            return

        face_name = self.combo_face.currentText() or faces[0]

        # 收集记录：表格选中行优先，否则全部 bbox 有效记录
        records = self._collect_projectable_records()
        if not records:
            QMessageBox.information(
                self, "病害投影",
                "没有可投影的病害记录。\n\n"
                "需要带检测框（bbox）和照片路径的记录，\n"
                "请先运行病害检测或手动添加记录。"
            )
            return

        base_pos = self._get_component_base_pos(params, dk)

        engine = FaceProjectionEngine(comp_type, params, base_pos)
        face = engine.get_face_info(face_name)
        if face is None:
            QMessageBox.warning(
                self, "病害投影",
                f"无法获取面 [{face_name}]。\n"
                f"可能原因：该构件参数未满足此面的生成条件（如尺寸阈值）。"
            )
            return

        # 逐条映射并放置点云标记（每个病害区域一团彩色小点）
        from disease_marker import DiseaseMarkerComponent, _log
        from face_projection import PointCloudGenerator

        # 点云视觉强化：30mm 大点（原 8mm 在 10m 级构件上几乎不可见）+ 12mm 间距
        pc_gen = PointCloudGenerator(density=12.0, point_size=30.0,
                                     max_total_points=3000)
        # 法向偏移符号：让点落在表面外侧（而非埋进构件内部）
        n_axis = {'xz': 1, 'yz': 0, 'xy': 2}.get(face.plane, 1)
        n_sign = face.normal[n_axis] if face.normal[n_axis] else 1.0
        n_off = n_sign * (pc_gen.point_size / 2.0 + 1.0)

        _log(f"投影开始: base={base_pos}, face={face_name}, "
             f"center={face.center}, size={face.width:.0f}x{face.height:.0f}, "
             f"记录数={len(records)}, 点距={pc_gen.density}mm, "
             f"总点数上限={pc_gen.max_total_points}, 单区域上限={pc_gen.max_points_per_shadow}")

        import time as _time
        _t_begin = _time.time()
        placed = 0
        skipped = 0
        for r in records:
            QApplication.processEvents()   # 保持 UI 响应，避免长时间未响应
            try:
                from PIL import Image
                with Image.open(r["photo"]) as im:
                    photo_w, photo_h = im.size

                shadow = photo_bbox_to_shadow(
                    face, tuple(r["bbox"]), photo_w, photo_h, r.get("disease", "")
                )
                # 在病害区域内生成点云（面局部坐标），法向偏移取正确符号
                _t0 = _time.time()
                if getattr(face, 'surface_fn', None) is not None:
                    # 弧面（拱圈/仰拱内壁）：逐点落在真实弧面上并沿内法线偏移 2mm，
                    # 点携带真 3D 局部坐标，face_plane 用 'xyz' 直通映射
                    points = pc_gen.generate_surface(face, [shadow])
                    face_plane = 'xyz'
                else:
                    points = [(u, v, n_off, c)
                              for (u, v, _z, c) in pc_gen.generate(face, [shadow])]
                    face_plane = face.plane
                _t_gen = _time.time() - _t0
                _log(f"  点云生成: 病害={r.get('disease','?')} 点数={len(points)} "
                     f"区域={shadow.width:.0f}x{shadow.height:.0f} 耗时={_t_gen:.3f}s")
                if not points:
                    skipped += 1
                    continue
                # 点云几何以面中心（世界坐标）为基准烘焙，放置时用零变换
                _t0 = _time.time()
                marker = DiseaseMarkerComponent.create_point_cloud_marker(
                    x=face.center[0], y=face.center[1], z=face.center[2],
                    points=points, point_size=pc_gen.point_size,
                    face_plane=face_plane,
                    disease_type=r.get("disease", ""),
                )
                _t_mk = _time.time() - _t0
                _t0 = _time.time()
                ok = marker is not None and self._place_marker_direct(marker)
                _t_place = _time.time() - _t0
                if ok:
                    placed += 1
                    _log(f"  记录投影成功: {r.get('disease','?')} 点数={len(points)} "
                         f"面内中心=({shadow.local_u:.0f},{shadow.local_v:.0f}) "
                         f"标记创建={_t_mk:.3f}s 放置={_t_place:.3f}s")
                else:
                    skipped += 1
                    _log(f"  记录投影失败(标记创建或放置): {r.get('disease','?')} "
                         f"标记创建={_t_mk:.3f}s 放置={_t_place:.3f}s")
            except Exception as e:
                skipped += 1
                _log(f"  记录投影失败: {e}")

        _log(f"投影结束: 成功={placed} 跳过={skipped} 总耗时={_time.time() - _t_begin:.3f}s")
        QApplication.processEvents()   # 放置完成后恢复 UI 再弹窗
        self.lbl_scan_result.setText(
            f"投影完成: {placed}/{len(records)} 条 → [{comp_type}] {face_name}"
        )
        QMessageBox.information(
            self, "投影完成",
            f"已将 {placed}/{len(records)} 条病害记录投影到 [{comp_type}] 的 [{face_name}]。\n\n"
            f"基准位置: ({base_pos[0]:.1f}, {base_pos[1]:.1f}, {base_pos[2]:.1f})\n"
            f"面尺寸: {face.width:.1f} × {face.height:.1f}"
            + (f"\n跳过 {skipped} 条（照片读取失败或放置失败）。" if skipped else "")
            + "\n\n请在BIMBase视图中查看效果。"
        )

    def _collect_projectable_records(self):
        """收集可投影的病害记录：表格选中行优先，否则全部 bbox 有效记录"""
        def _valid(r):
            bbox = r.get("bbox")
            if not bbox or len(bbox) != 4 or not r.get("photo"):
                return False
            x1, y1, x2, y2 = bbox
            return (x2 - x1) > 0 and (y2 - y1) > 0

        rows = sorted({it.row() for it in self.table.selectedItems()})
        if rows:
            recs = [self.records[i] for i in rows if 0 <= i < len(self.records)]
            recs = [r for r in recs if _valid(r)]
            if recs:
                return recs
        return [r for r in self.records if _valid(r)]

    def _get_component_base_pos(self, params, dk):
        """获取构件基准世界坐标：手动输入 → params → transformation/Placement → (0,0,0)"""
        # 手动输入优先（从 BIMBase 属性面板读坐标填入，格式 x,y,z）
        try:
            manual = self.edit_base_pos.text().strip()
        except Exception:
            manual = ''
        if manual:
            try:
                parts = [float(p) for p in manual.replace('，', ',').split(',')]
                if len(parts) == 3:
                    return parts[0], parts[1], parts[2]
            except Exception:
                pass

        x, y, z = self._estimate_base_position(params)
        if x or y or z:
            return x, y, z
        # transformation/Placement 兜底（参数化组件经 transformation 放置后，x/y 隐藏属性常为 0）
        if dk is not None:
            try:
                from bimbase_sync import get_noumKV_from_instancekey
                kv = get_noumKV_from_instancekey(dk)
                if isinstance(kv, dict):
                    for key in ('\a_transformation', '\aGraphicElement::m_transform',
                                'Placement', 'BaseTransform'):
                        if key in kv:
                            xyz = self._extract_xyz_robust(kv.get(key))
                            if xyz is not None:
                                return xyz
            except Exception:
                pass
        return 0.0, 0.0, 0.0

    @staticmethod
    def _extract_xyz_robust(obj, _depth=0):
        """从 GeTransform/Placement/矩阵/字典/对象中提取平移分量（参考 AI_Modeling bimbase_modifier）"""
        if obj is None or _depth > 3:
            return None
        try:
            # GeTransform._mat：3x4 行主序矩阵，平移在 [i][3]
            if hasattr(obj, '_mat'):
                mat = obj._mat
                if isinstance(mat, (list, tuple)) and len(mat) == 3:
                    return float(mat[0][3]), float(mat[1][3]), float(mat[2][3])
            # pyp3d 官方 helper
            try:
                from pyp3d import get_matrixs_position
                pos = get_matrixs_position(obj)
                if pos is not None:
                    r = DiseaseDialog._extract_xyz_robust(pos, _depth + 1)
                    if r is not None:
                        return r
            except Exception:
                pass
            # 字典形式
            if isinstance(obj, dict):
                for kx in ('x', 'X', 'origin_x', 'translation_x', 'OriginX', 'TranslationX'):
                    if kx in obj:
                        return (float(obj[kx]),
                                float(obj.get('y', obj.get('Y', 0))),
                                float(obj.get('z', obj.get('Z', 0))))
                for kk in ('translation', 'origin'):
                    if kk in obj:
                        r = DiseaseDialog._extract_xyz_robust(obj[kk], _depth + 1)
                        if r is not None:
                            return r
                return None
            # 对象属性 x/y/z
            if hasattr(obj, 'x') and hasattr(obj, 'y'):
                return (float(obj.x), float(obj.y),
                        float(obj.z) if hasattr(obj, 'z') else 0.0)
            # 列表/元组（16 元素列主序矩阵，或 Vec3）
            if isinstance(obj, (list, tuple)):
                if len(obj) >= 16:
                    return float(obj[12]), float(obj[13]), float(obj[14])
                if len(obj) >= 3:
                    try:
                        return float(obj[0]), float(obj[1]), float(obj[2])
                    except Exception:
                        pass
            # 方法形式
            for m in ('get_translation', 'translation', 'get_origin', 'origin',
                      'get_position', 'position'):
                if hasattr(obj, m):
                    try:
                        r = DiseaseDialog._extract_xyz_robust(getattr(obj, m)(), _depth + 1)
                        if r is not None:
                            return r
                    except Exception:
                        pass
        except Exception:
            pass
        return None

    def _place_marker_direct(self, marker):
        """用 bimbase_sync._PlaceToDirect 自动放置标记（不进入手动布置模式）。

        标记几何已烘焙世界坐标，这里必须用零变换放置，
        否则平移会被应用两次（几何烘焙一次 + TRANSFORMATION 一次）。
        """
        try:
            import bimbase_sync as _sync
            from pyp3d import translate as _translate

            if not _sync._ensure_place_to_direct():
                return False

            _sync_dir = os.path.dirname(os.path.abspath(__file__))
            original_argv0 = sys.argv[0]
            sys.argv[0] = os.path.join(_sync_dir, 'bimbase_sync.py')
            try:
                _sync._PlaceToDirect(marker, _translate(0, 0, 0))
            finally:
                sys.argv[0] = original_argv0
            return True
        except Exception as e:
            try:
                from disease_marker import _log
                _log(f"自动放置标记失败: {e}")
            except Exception:
                pass
            return False

    def _estimate_base_position(self, params: dict):
        """从组件参数估算基准位置（世界坐标）"""
        x = y = z = 0.0
        for key in ('x', 'cx', 'x1'):
            if key in params:
                try:
                    x = float(params[key])
                    break
                except (ValueError, TypeError):
                    pass
        for key in ('y', 'cy', 'y1'):
            if key in params:
                try:
                    y = float(params[key])
                    break
                except (ValueError, TypeError):
                    pass
        for key in ('z_bottom', 'z1', 'z'):
            if key in params:
                try:
                    z = float(params[key])
                    break
                except (ValueError, TypeError):
                    pass
        return x, y, z

    def _auto_get_selected(self):
        """自动获取BIMBase当前选中的组件（多策略回退版，失败后静默）"""
        try:
            from bimbase_sync import get_current_entityId, get_datakey_from_entity

            params = None
            dk = None

            # 策略1：通过当前选中的 entityId 获取 datakey
            eid = get_current_entityId()
            if eid is not None:
                try:
                    dk = get_datakey_from_entity(eid)
                except Exception:
                    dk = None
                if dk is not None:
                    params = self._extract_params_from_dk(dk)

            # 策略2：回退到扫描所有 instance key（走缓存，扫描慢只发生一次）
            if not params:
                cached = self._scan_cache is not None
                matches = self._scan_all_components()
                if matches:
                    _ct, params, dk = matches[0]
                    if cached and dk is not None:
                        fresh = self._refresh_component_params(_ct, params, dk)
                        if fresh is not None:
                            params = fresh

            if not params:
                return

            from bimbase_query import infer_tunnel_component_type
            comp_type = infer_tunnel_component_type(params) if params else ""

            if comp_type:
                self._selected_component = {
                    'key': dk,
                    'params': params,
                    'comp_type': comp_type,
                }
        except Exception:
            pass

    def _on_project_to_bimbase(self):
        """将病害标记投影到当前选中的BIMBase组件位置"""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "提示", "请先在表格中选中一条病害记录")
            return
        
        row = selected[0].row()
        if row < 0 or row >= len(self.records):
            return
        
        record = self.records[row]
        
        # 获取目标组件
        if self._selected_component is None:
            QMessageBox.warning(self, "未获取组件", 
                "请先点击【获取当前选中组件】获取BIMBase中的组件，\n"
                "或先添加病害记录（构件类型会自动匹配）。")
            return
        
        target = self._selected_component
        comp_type = target["comp_type"]
        params = target.get("params", {})
        
        # 估算3D位置
        try:
            x, y, z = self._marker_manager.estimate_marker_position(params)
        except Exception:
            x, y, z = 0.0, 0.0, 100.0
        
        # 放置标记
        confidence = {"轻微": 0.3, "中等": 0.55, "严重": 0.8, "极严重": 0.95}.get(record["severity"], 0.5)
        
        try:
            mr = self._marker_manager.place_marker_simple(
                photo_path=record["photo"],
                component_type=comp_type,
                component_key=target["key"],
                disease_class=record["disease"],
                confidence=confidence,
                position_3d=(x, y, z),
            )
            if mr:
                QMessageBox.information(self, "投影成功", 
                    f"已在BIMBase中放置病害标记！\n\n"
                    f"构件: {comp_type}\n"
                    f"位置: ({x:.1f}, {y:.1f}, {z:.1f})\n"
                    f"病害: {record['disease']} ({record['severity']})")
            else:
                QMessageBox.warning(self, "投影失败", "标记创建失败，请检查BIMBase连接状态")
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "投影异常", f"投影到BIMBase时出错:\n{e}\n\n{traceback.format_exc()}")
