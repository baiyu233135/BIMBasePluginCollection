# -*- coding: utf-8 -*-
"""
桥隧病害识别 — 手动录入版主对话框

交互流程：
1. 导入无人机照片
2. 选择构件类型
3. 手动添加病害记录（类型、位置、严重程度、备注）
4. 生成Word诊断报告
"""

import os
import sys
import uuid
from datetime import datetime

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QComboBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QLineEdit, QTextEdit,
    QDoubleSpinBox, QFormLayout, QSplitter, QWidget, QScrollArea,
    QApplication
)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt

from report_generator import ReportGenerator
from disease_marker import MarkerRecord, get_marker_manager
from bimbase_query import get_component_query

# 桥梁构件类型（含基本几何体）
COMPONENT_CLASSES = [
    "直角三棱柱", "圆柱", "正方体", "长方体",
    "T梁", "主塔", "工字钢混凝土组合梁", "斜拉索", "湿接缝", "箱梁",
    "防撞护栏", "波形护栏", "主塔群桩承台", "异形盖梁", "扩大基础",
    "柱式桥台", "柱式桥墩", "桩基承台", "薄壁墩", "重力式桥台",
    "人行道及护栏", "路面及交通标线",
]

# 病害类型（含自动识别兜底标签）
DISEASE_CLASSES = ["异常区域", "裂缝", "剥落", "露筋", "蜂窝麻面", "渗水", "锈蚀"]

# 严重程度
SEVERITY_LEVELS = ["轻微", "中等", "严重", "极严重"]


class DiseaseDialog(QDialog):
    """桥隧病害识别主对话框（手动录入版）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("桥隧病害识别 — 手动录入")
        self.setMinimumSize(1100, 750)

        # 状态
        self.current_image_path = ""
        self.current_component_type = ""
        self.records = []  # 手动录入的病害记录列表
        self._selected_component = None  # 当前选中的BIMBase组件 {key, params, comp_type}
        self._marker_manager = get_marker_manager()

        self._init_ui()

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
        self.btn_import = QPushButton("📷 导入无人机照片")
        self.btn_import.setMinimumHeight(36)
        self.btn_import.clicked.connect(self._on_import_photo)
        v.addWidget(self.btn_import)

        self.btn_detect_anomalies = QPushButton("🔍 自动识别异常区域")
        self.btn_detect_anomalies.setMinimumHeight(36)
        self.btn_detect_anomalies.setStyleSheet(
            "QPushButton{background:#E65100;color:white;font-weight:bold;}"
        )
        self.btn_detect_anomalies.setToolTip("使用传统 CV 自动圈出裂缝、渗水等异常区域")
        self.btn_detect_anomalies.clicked.connect(self._on_detect_anomalies)
        self.btn_detect_anomalies.setEnabled(False)
        v.addWidget(self.btn_detect_anomalies)

        self.lbl_photo_name = QLabel("未选择照片")
        self.lbl_photo_name.setStyleSheet("color:#666;")
        v.addWidget(self.lbl_photo_name)
        layout.addWidget(group_photo)

        # === 构件信息 ===
        group_comp = QGroupBox("2. 构件信息")
        f = QFormLayout(group_comp)
        self.combo_component = QComboBox()
        self.combo_component.addItems(COMPONENT_CLASSES)
        f.addRow("构件类型：", self.combo_component)
        self.edit_bridge_name = QLineEdit()
        self.edit_bridge_name.setPlaceholderText("例如：K12+350 大桥")
        f.addRow("桥梁名称：", self.edit_bridge_name)
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
        
        # 面投影测试（半透明薄片）
        self.btn_face_project = QPushButton("🔴 面投影测试(薄片)")
        self.btn_face_project.setStyleSheet("QPushButton{background:#C62828;color:white;font-weight:bold;}")
        self.btn_face_project.setToolTip("根据构件参数，在指定面上创建彩色半透明薄片")
        self.btn_face_project.clicked.connect(self._on_face_project)
        f.addRow(self.btn_face_project)
        
        # 纹理贴图测试
        self.btn_texture_project = QPushButton("🎨 纹理贴图测试")
        self.btn_texture_project.setStyleSheet("QPushButton{background:#E65100;color:white;font-weight:bold;}")
        self.btn_texture_project.setToolTip("生成PNG纹理图片并贴到构件表面")
        self.btn_texture_project.clicked.connect(self._on_texture_project)
        f.addRow(self.btn_texture_project)
        
        # 点云投影测试
        self.btn_pointcloud_project = QPushButton("☁️ 点云投影测试")
        self.btn_pointcloud_project.setStyleSheet("QPushButton{background:#2E7D32;color:white;font-weight:bold;}")
        self.btn_pointcloud_project.setToolTip("在构件表面生成大量彩色小点模拟点云投影")
        self.btn_pointcloud_project.clicked.connect(self._on_pointcloud_project)
        f.addRow(self.btn_pointcloud_project)
        
        self.lbl_scan_result = QLabel("请先点击【获取当前选中组件】扫描构件，再选择投影方式")
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
        self.edit_position.setPlaceholderText("例如：箱梁底板跨中位置")
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

        self.btn_clear = QPushButton("🗑 清空记录")
        self.btn_clear.clicked.connect(self._on_clear_records)
        va.addWidget(self.btn_clear)

        layout.addWidget(group_action)
        layout.addStretch()
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 照片预览
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.lbl_image = QLabel("请导入照片")
        self.lbl_image.setAlignment(Qt.AlignCenter)
        self.lbl_image.setStyleSheet("background:#1e1e1e;color:#888;font-size:16px;")
        self.lbl_image.setMinimumSize(500, 350)
        self.scroll.setWidget(self.lbl_image)
        layout.addWidget(self.scroll, 1)

        # 病害列表
        group = QGroupBox("已录入病害列表")
        v = QVBoxLayout(group)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["#", "病害类型", "严重程度", "位置", "尺寸", "备注"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        v.addWidget(self.table)

        self.lbl_count = QLabel("共 0 条记录")
        v.addWidget(self.lbl_count)
        
        # 投影按钮
        self.btn_project = QPushButton("📍 投影选中记录到BIMBase")
        self.btn_project.setMinimumHeight(36)
        self.btn_project.setStyleSheet(
            "QPushButton{background:#C62828;color:white;font-size:13px;font-weight:bold;}"
        )
        self.btn_project.setToolTip("将当前选中的病害记录投影为红色标记到BIMBase对应构件位置")
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
        self.lbl_photo_name.setText(os.path.basename(path))
        self.lbl_photo_name.setStyleSheet("color:#1565C0;font-weight:bold;")
        self.btn_detect_anomalies.setEnabled(True)

        # 显示预览
        pix = QPixmap(path)
        if not pix.isNull():
            scaled = pix.scaled(
                self.scroll.width() - 20, self.scroll.height() - 20,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.lbl_image.setPixmap(scaled)

    def _on_detect_anomalies(self):
        """使用传统 CV 自动识别异常区域，并在照片上圈出。"""
        if not self.current_image_path:
            QMessageBox.warning(self, "提示", "请先导入照片")
            return

        self.btn_detect_anomalies.setEnabled(False)
        self.btn_detect_anomalies.setText("🔍 识别中...")
        QApplication.processEvents()

        try:
            from disease_detector import DiseaseDetector
            detector = DiseaseDetector()
            results = detector.detect_anomalies(self.current_image_path)

            if not results:
                QMessageBox.information(self, "识别完成", "未检测到明显异常区域。\n\n"
                    "可尝试导入更清晰的 T 梁照片，或在后续版本中调整检测参数。")
                self.btn_detect_anomalies.setEnabled(True)
                self.btn_detect_anomalies.setText("🔍 自动识别异常区域")
                return

            # 生成带框预览图
            from cv_anomaly_detector import draw_anomaly_results
            preview_path = draw_anomaly_results(self.current_image_path, results)
            if preview_path and os.path.exists(preview_path):
                pix = QPixmap(preview_path)
                if not pix.isNull():
                    scaled = pix.scaled(
                        self.scroll.width() - 20, self.scroll.height() - 20,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.lbl_image.setPixmap(scaled)

            # 清空当前图片已有的异常区域记录，避免重复
            self.records = [r for r in self.records
                            if not (r.get("photo") == self.current_image_path
                                    and r.get("disease") == "异常区域")]

            # 将检测结果加入记录
            component_type = self.combo_component.currentText()
            bridge_name = self.edit_bridge_name.text().strip() or "未命名桥梁"
            component_no = self.edit_component_no.text().strip() or "未编号"
            for idx, r in enumerate(results, 1):
                x1, y1, x2, y2 = r.bbox
                w = x2 - x1
                h = y2 - y1
                severity = self._confidence_to_severity(r.confidence)
                record = {
                    "id": str(uuid.uuid4())[:8],
                    "photo": self.current_image_path,
                    "component": component_type,
                    "bridge": bridge_name,
                    "component_no": component_no,
                    "disease": "异常区域",
                    "severity": severity,
                    "position": f"像素坐标: x={x1}, y={y1}",
                    "size": f"宽{w} × 高{h} 像素",
                    "note": f"自动识别第 {idx} 处异常区域，置信度 {r.confidence:.2f}",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                self.records.append(record)

            self._refresh_table()
            self.btn_report.setEnabled(True)
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
    def _confidence_to_severity(confidence: float) -> str:
        """根据置信度映射严重程度"""
        if confidence >= 0.75:
            return "严重"
        elif confidence >= 0.5:
            return "中等"
        else:
            return "轻微"

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
            "bridge": self.edit_bridge_name.text().strip() or "未命名桥梁",
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
            self.table.setItem(i, 2, QTableWidgetItem(r["severity"]))
            self.table.setItem(i, 3, QTableWidgetItem(r["position"]))
            self.table.setItem(i, 4, QTableWidgetItem(r["size"]))
            self.table.setItem(i, 5, QTableWidgetItem(r["note"]))
        self.table.resizeColumnsToContents()
        self.lbl_count.setText(f"共 {len(self.records)} 条记录")

    def _on_clear_records(self):
        if not self.records:
            return
        reply = QMessageBox.question(self, "确认", "确定清空所有记录？")
        if reply == QMessageBox.Yes:
            self.records.clear()
            self._refresh_table()
            self.btn_report.setEnabled(False)

    def _on_generate_report(self):
        if not self.records:
            QMessageBox.warning(self, "提示", "请先添加至少一条病害记录")
            return

        # 组装为MarkerRecord格式
        mr_list = []
        for r in self.records:
            mr_list.append(MarkerRecord(
                record_id=r["id"],
                photo_path=r["photo"],
                component_type=r["component"],
                component_key=r["component_no"],
                disease_class=r["disease"],
                confidence={"轻微": 0.3, "中等": 0.55, "严重": 0.8, "极严重": 0.95}.get(r["severity"], 0.5),
                bbox=(0, 0, 0, 0),
                marker_x=0, marker_y=0, marker_z=0,
                created_at=r["time"],
            ))

        default_name = f"桥梁病害诊断报告_{datetime.now().strftime('%Y%m%d')}.docx"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存报告", default_name, "Word文档 (*.docx)"
        )
        if not path:
            return

        # 详细日志帮助排查
        _log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bridge_disease_debug.log")
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
            bridge = self.edit_bridge_name.text().strip() or "未命名桥梁"
            gen.set_project_info("桥梁定期检测项目", bridge)
            _local_log("ReportGenerator initialized")

            ok = gen.generate(mr_list, path)
            _local_log(f"generate() returned {ok}")

            if ok:
                QMessageBox.information(self, "完成", f"报告已生成：\n{path}")
            else:
                QMessageBox.critical(self, "失败", "报告生成失败，请查看 bridge_disease_debug.log 获取详情")
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
                        params = {key: p[key] for key in p}
                    elif p is not None and isinstance(p, dict):
                        params = dict(p)
                    else:
                        params = dict(raw)
                else:
                    params = dict(raw)

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

            interest_keys = {'长度', '宽度', '高度', '边长', '半径', '直角边1', '直角边2',
                             'x', 'y', 'z_bottom', 'z_top', '主纵梁长度', '底板宽'}
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
        _log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bridge_disease_debug.log")
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

        # ===== 策略2：如果策略1拿不到参数，扫描所有 instance key =====
        if not params:
            _dbg("Strategy1 failed, fallback to scanning all instances...")
            try:
                params, dk = self._scan_all_instances_for_params()
                if params:
                    _dbg(f"Strategy2 success: params keys={list(params.keys())[:10]}")
            except Exception as e:
                _dbg(f"Strategy2 scan failed: {e}")

        if not params or not isinstance(params, dict):
            QMessageBox.warning(self, "无参数", 
                "无法读取选中组件的参数。\n\n可能原因:\n"
                "1. 选中的是参数化组件代理，没有直接datakey\n"
                "2. BIMBase API暂时不可用\n\n"
                "建议: 尝试重新选中组件后再次点击。")
            self.lbl_scan_result.setText("获取失败: 无法读取参数")
            return

        param_keys = [pk for pk in params.keys() if isinstance(pk, str)]
        _dbg(f"Param keys: {param_keys}")

        # 匹配构件类型
        from bimbase_query import infer_bridge_component_type
        comp_type = infer_bridge_component_type(params)
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

        # 更新UI
        idx = self.combo_component.findText(comp_type)
        if idx >= 0:
            self.combo_component.setCurrentIndex(idx)
        
        info = f"已获取: {comp_type}\n参数: {', '.join(param_keys[:6])}"
        self.lbl_scan_result.setText(info)
        
        if self.records:
            self.btn_project.setEnabled(True)

        QMessageBox.information(self, "获取成功", 
            f"已获取选中组件！\n\n类型: {comp_type}\n参数: {', '.join(param_keys)}")
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
            plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
                        place_to(marker, _translate(wx, wy, wz))
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
                plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if plugin_dir not in sys.path:
                    sys.path.insert(0, plugin_dir)
                from bimbase_sync import place_to, translate as _translate
                original_argv0 = sys.argv[0]
                sys.argv[0] = os.path.join(plugin_dir, 'bimbase_sync.py')
                try:
                    place_to(marker, _translate(wx, wy, wz))
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
                plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if plugin_dir not in sys.path:
                    sys.path.insert(0, plugin_dir)
                from bimbase_sync import place_to, translate as _translate
                original_argv0 = sys.argv[0]
                sys.argv[0] = os.path.join(plugin_dir, 'bimbase_sync.py')
                try:
                    place_to(marker, _translate(face.center[0], face.center[1], face.center[2]))
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

            # 策略2：回退到扫描所有 instance key
            if not params:
                params, dk = self._scan_all_instances_for_params()

            if not params:
                return

            from bimbase_query import infer_bridge_component_type
            comp_type = infer_bridge_component_type(params) if params else ""

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
                    f"已在BIMBase中放置红色病害标记！\n\n"
                    f"构件: {comp_type}\n"
                    f"位置: ({x:.1f}, {y:.1f}, {z:.1f})\n"
                    f"病害: {record['disease']} ({record['severity']})")
            else:
                QMessageBox.warning(self, "投影失败", "标记创建失败，请检查BIMBase连接状态")
        except Exception as e:
            import traceback
            QMessageBox.critical(self, "投影异常", f"投影到BIMBase时出错:\n{e}\n\n{traceback.format_exc()}")
