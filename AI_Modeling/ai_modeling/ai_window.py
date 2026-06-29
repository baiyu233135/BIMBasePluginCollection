# -*- coding: utf-8 -*-
"""
BIMBase AI智能建模助手 - 主对话框
气泡聊天风格，支持本地解析 + DeepSeek API
"""
import os
import sys
import json
import re
import math
from datetime import datetime

_plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

try:
    from PyQt5.QtWidgets import (
        QDialog, QMainWindow, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
        QPushButton, QLabel, QFormLayout, QMessageBox, QCheckBox,
        QWidget, QScrollArea, QFrame, QSizePolicy, QApplication,
    )
    from PyQt5.QtCore import Qt, QTimer, pyqtSlot
    from PyQt5.QtGui import QFont, QColor, QTextCursor
    _QT_VER = 5
except ImportError:
    from PyQt6.QtWidgets import (
        QDialog, QMainWindow, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
        QPushButton, QLabel, QFormLayout, QMessageBox, QCheckBox,
        QWidget, QScrollArea, QFrame, QSizePolicy, QApplication,
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSlot
    from PyQt6.QtGui import QFont, QColor, QTextCursor
    _QT_VER = 6

from ai_modeling.config import load_config, set_api_key, get_api_key, save_config, CONFIG_DIR, CONFIG_FILE
from ai_modeling.chat_thread import AIChatThread, AIChatNonStreamThread
from ai_modeling.command_parser import ModelingCommandParser
from ai_modeling.component_factory import create_component, place_component_at, batch_place
from ai_modeling.array_generator import linear_array, rectangular_array, polar_array
from ai_modeling.route import Route, ArcRoute, sample_route_for_components
from ai_modeling.component_path import (
    sample_placement_frames, orient_component, resolve_path_name,
    get_component_route, build_oriented_components
)
from ai_modeling.bimbase_modifier import (
    modify_selected_component, get_selected_component_info, infer_component_type_from_params,
    get_selected_line_endpoints, get_selected_curve_arc_params
)


def _log(msg):
    try:
        log_path = os.path.join(_plugin_dir, 'ai_modeling_debug.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            ts = datetime.now().strftime('%H:%M:%S')
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


class APIConfigDialog(QDialog):
    """API Key 配置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI建模助手 - API配置")
        self.setMinimumSize(400, 200)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("sk-...")
        form.addRow("DeepSeek API Key:", self.key_input)

        self.baidu_key_input = QLineEdit()
        self.baidu_key_input.setEchoMode(QLineEdit.Password)
        self.baidu_key_input.setPlaceholderText("百度语音 API Key")
        form.addRow("百度 API Key:", self.baidu_key_input)

        self.baidu_secret_input = QLineEdit()
        self.baidu_secret_input.setEchoMode(QLineEdit.Password)
        self.baidu_secret_input.setPlaceholderText("百度语音 Secret Key")
        form.addRow("百度 Secret Key:", self.baidu_secret_input)

        self.show_cb = QCheckBox("显示密钥")
        self.show_cb.stateChanged.connect(self._toggle)
        form.addRow("", self.show_cb)

        info = QLabel(
            "<small>获取 DeepSeek Key: <a href='https://platform.deepseek.com'>platform.deepseek.com</a><br>"
            "获取百度语音 Key: <a href='https://ai.baidu.com/tech/speech'>ai.baidu.com/tech/speech</a><br>"
            "Key 仅保存在本地 ai_modeling_config.json</small>"
        )
        info.setOpenExternalLinks(True)
        form.addRow(info)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _toggle(self, state):
        mode = QLineEdit.Normal if state == Qt.Checked else QLineEdit.Password
        self.key_input.setEchoMode(mode)
        self.baidu_key_input.setEchoMode(mode)
        self.baidu_secret_input.setEchoMode(mode)

    def _load(self):
        cfg = load_config()
        self.key_input.setText(cfg.get('api_key', ''))
        self.baidu_key_input.setText(cfg.get('baidu_api_key', ''))
        self.baidu_secret_input.setText(cfg.get('baidu_secret_key', ''))

    def _save(self):
        cfg = load_config()
        cfg['api_key'] = self.key_input.text().strip()
        cfg['baidu_api_key'] = self.baidu_key_input.text().strip()
        cfg['baidu_secret_key'] = self.baidu_secret_input.text().strip()
        save_config(cfg)
        QMessageBox.information(self, "保存成功", "API Key 已保存")
        self.accept()


class AIModelingWindow(QDialog):
    """AI智能建模助手对话框 - 使用exec_()模态显示确保稳定"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🤖 BIMBase AI智能建模助手")
        self.setGeometry(200, 150, 520, 680)
        # 非模态 + 置顶，允许用户与BIMBase主窗口交互
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog { background-color: #f5f5f5; }
            QTextEdit { border: 1px solid #ddd; border-radius: 6px; background: #fff; }
            QLineEdit { border: 1px solid #ccc; border-radius: 4px; padding: 4px; }
            QPushButton { border-radius: 4px; padding: 6px 14px; }
        """)

        self.cfg = load_config()
        self.chat_history = []  # AI对话历史
        self._chat_thread = None
        self._streaming = False
        self._last_commands = []  # 最后执行的命令（用于撤销/查看）

        self._build_ui()
        self._show_welcome()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("<b style='font-size:14px;'>🤖 BIMBase AI智能建模助手</b>")
        header.addWidget(title)

        self.mode_indicator = QLabel("⚡ 本地")
        self.mode_indicator.setStyleSheet("QLabel { color: #1565C0; font-size: 12px; padding: 2px 6px; }")
        header.addWidget(self.mode_indicator)
        header.addStretch()

        config_btn = QPushButton("⚙️ 配置")
        config_btn.setMaximumWidth(60)
        config_btn.clicked.connect(self._show_config)
        header.addWidget(config_btn)

        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(self._clear_chat)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        # 聊天显示区
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFont(QFont("Microsoft YaHei", 10))
        self.chat_display.setStyleSheet("QTextEdit { padding: 8px; }")
        layout.addWidget(self.chat_display, 1)

        # 状态标签
        self.status_label = QLabel("就绪 - 输入指令如：在(1000,2000,500)生成半径300高800的圆柱")
        self.status_label.setStyleSheet("QLabel { color: #666; font-size: 11px; }")
        layout.addWidget(self.status_label)

        # 快捷提示按钮
        tips_layout = QHBoxLayout()
        for tip_text in [
            "生成圆柱", "生成正方体", "生成球体",
            "修改选中", "沿X轴阵列", "沿曲线布置",
        ]:
            btn = QPushButton(tip_text)
            btn.setStyleSheet("QPushButton { font-size: 10px; padding: 2px 6px; background: #e3f2fd; color: #1565C0; }")
            btn.setMaximumHeight(24)
            btn.clicked.connect(lambda checked=False, t=tip_text: self._fill_input(t))
            tips_layout.addWidget(btn)
        tips_layout.addStretch()
        layout.addLayout(tips_layout)

        # 输入区
        input_layout = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入自然语言指令，如：在(1000,2000,500)生成半径300高800的圆柱...")
        self.input_box.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_box, 1)

        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setToolTip("点击开始/停止语音输入（需配置百度语音API）")
        self.voice_btn.setMaximumWidth(40)
        self.voice_btn.clicked.connect(self._on_voice_toggle)
        input_layout.addWidget(self.voice_btn)

        self.send_btn = QPushButton("发送")
        self.send_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; font-weight: bold; }")
        self.send_btn.setMaximumWidth(60)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        layout.addLayout(input_layout)

        # 语音输入组件
        from ai_modeling.voice_input import VoiceRecorder, BaiduSpeechRecognizer
        self._voice_recorder = VoiceRecorder(self)
        self._voice_recorder.finished.connect(self._on_voice_finished)
        self._voice_recorder.error.connect(self._on_voice_error)
        self._voice_recognizer = None  # 延迟初始化

    def _fill_input(self, text):
        self.input_box.setText(text)
        self.input_box.setFocus()

    def _request_manual_coordinate(self, defaults=(0, 0, 0)):
        """弹出 X/Y/Z 三轴坐标输入对话框"""
        try:
            from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
            from PyQt5.QtCore import Qt
        except ImportError:
            from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
            from PyQt6.QtCore import Qt

        dx, dy, dz = [float(v) for v in defaults]
        dlg = QDialog(self)
        dlg.setWindowTitle("输入放置坐标")
        dlg.setWindowModality(Qt.ApplicationModal)
        layout = QFormLayout(dlg)
        x_edit = QLineEdit(str(dx))
        y_edit = QLineEdit(str(dy))
        z_edit = QLineEdit(str(dz))
        layout.addRow("X:", x_edit)
        layout.addRow("Y:", y_edit)
        layout.addRow("Z:", z_edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addRow(btns)
        exec_method = getattr(dlg, 'exec_', getattr(dlg, 'exec', None))
        if exec_method and exec_method() == QDialog.Accepted:
            try:
                return (
                    float(x_edit.text()),
                    float(y_edit.text()),
                    float(z_edit.text()),
                )
            except Exception:
                pass
        return None

    def _ensure_voice_recognizer(self):
        """延迟初始化语音识别器（不预取 token，避免网络阻塞/异常导致闪退）"""
        if self._voice_recognizer is not None:
            return True
        try:
            import os as _os
            from ai_modeling.voice_input import BaiduSpeechRecognizer as _BaiduSpeechRecognizer
            cfg = load_config()
            api_key = cfg.get('baidu_api_key', '')
            secret_key = cfg.get('baidu_secret_key', '')
            # 兜底：如果 load_config 没读到，直接读文件
            if not api_key or not secret_key:
                try:
                    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                        raw_cfg = json.load(f)
                    api_key = raw_cfg.get('baidu_api_key', '')
                    secret_key = raw_cfg.get('baidu_secret_key', '')
                except Exception as e2:
                    _log(f"_ensure_voice_recognizer direct read error: {e2}")
            file_exists = _os.path.exists(CONFIG_FILE)
            has_keys = bool(api_key and secret_key)
            _log(f"_ensure_voice_recognizer: CONFIG_DIR={CONFIG_DIR}, CONFIG_FILE={CONFIG_FILE}, exists={file_exists}, has_keys={has_keys}, key_type={type(api_key).__name__}")
            self._append_system(f"🛠 配置路径: {CONFIG_FILE}, 文件存在: {file_exists}, Key已填: {has_keys}")
            if not has_keys:
                return False
            self._voice_recognizer = _BaiduSpeechRecognizer(api_key, secret_key, self)
            self._voice_recognizer.result.connect(self._on_voice_text)
            self._voice_recognizer.error.connect(self._on_voice_error)
            return True
        except Exception as e:
            _log(f"_ensure_voice_recognizer error: {e}")
            import traceback
            _log(traceback.format_exc())
            return False

    def _on_voice_toggle(self):
        """点击语音按钮：开始/停止录音"""
        try:
            if self._voice_recorder.is_recording():
                self._voice_recorder.stop()
                self.voice_btn.setText("🎤")
                self.voice_btn.setStyleSheet("")
                self.status_label.setText("录音停止，处理中...")
            else:
                if not self._ensure_voice_recognizer():
                    self._append_system("未配置百度语音 API Key，请在 ⚙️配置 中设置。申请地址: https://ai.baidu.com/tech/speech", "#d32f2f")
                    return
                self._voice_recorder.start()
                self.voice_btn.setText("⏹")
                self.voice_btn.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; }")
                self.status_label.setText("正在录音... 再次点击停止")
                self._append_system("🎤 录音已开始，请说话...")
        except Exception as e:
            _log(f"_on_voice_toggle error: {e}")
            import traceback
            _log(traceback.format_exc())
            self._append_system(f"❌ 语音启动失败: {e}", "#d32f2f")
            self.voice_btn.setText("🎤")
            self.voice_btn.setStyleSheet("")

    def _on_voice_finished(self, wav_data: bytes, sample_rate: int):
        """录音完成，开始识别"""
        self._append_system(f"🎤 录音完成，音频大小: {len(wav_data)} bytes，采样率: {sample_rate}Hz，正在识别...")
        if self._voice_recognizer:
            self._voice_recognizer.recognize(wav_data, sample_rate)
        else:
            self._append_system("❌ 语音识别器未初始化", "#d32f2f")

    def _on_voice_text(self, text: str):
        """语音识别成功，填入输入框（不自动发送，像画板一样由用户确认）"""
        self.voice_btn.setText("🎤")
        self.voice_btn.setStyleSheet("")
        self.input_box.setText(text)
        self.status_label.setText(f"语音识别: {text}")
        self._append_system(f"🎤 识别结果: {text}")
        self.input_box.setFocus()

    def _on_voice_error(self, msg: str):
        """语音识别出错"""
        self.voice_btn.setText("🎤")
        self.voice_btn.setStyleSheet("")
        self.status_label.setText(f"语音错误: {msg}")
        self._append_system(f"❌ 语音输入错误: {msg}", "#d32f2f")

    def _show_welcome(self):
        welcome = (
            "<p style='color:#666;'><b>👋 欢迎使用 BIMBase AI智能建模助手！</b></p>"
            "<p style='color:#666;'>你可以这样对我说：</p>"
            "<ul style='color:#666;'>"
            "<li><b>生成组件：</b>在(1000,2000,500)生成半径300高800的圆柱</li>"
            "<li><b>相对位置：</b>在选中的实体上方500mm生成一个正方体，边长200</li>"
            "<li><b>阵列生成：</b>沿X轴每隔1000mm生成一个圆柱，共5个，半径200高500</li>"
            "<li><b>沿直线布置：</b>沿选中的直线每隔500mm放半径50高100的圆柱，共10个</li>"
            "<li><b>沿曲线布置：</b>沿圆心(0,0,0)半径500从0°到180°的圆弧每隔200mm放圆柱</li>"
            "<li><b>修改组件：</b>把选中的圆柱半径改成400，高度改成1000</li>"
            "<li><b>批量布置：</b>生成3×3方阵，间距2000，每个位置放一个正方体边长300</li>"
            "</ul>"
            "<p style='color:#999;font-size:11px;'>💡 提示：先在BIMBase中选中组件，再说'修改选中的...'</p>"
        )
        self._append_html(welcome)

    def _append_html(self, html):
        self.chat_display.append(html)
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_user(self, text):
        ts = datetime.now().strftime("%H:%M")
        html = f'<p style="margin:4px 0;"><span style="background:#1565C0;color:white;padding:4px 8px;border-radius:8px;display:inline-block;max-width:80%;"><b>[{ts}] 你:</b> {text}</span></p>'
        self._append_html(html)

    def _append_ai(self, text, is_streaming=False):
        ts = datetime.now().strftime("%H:%M")
        prefix = f"<b>[{ts}] AI:</b> "
        if is_streaming:
            # 流式输出模式：直接追加到最后一行
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.chat_display.setTextCursor(cursor)
            self.chat_display.insertHtml(text)
        else:
            html = f'<p style="margin:4px 0;text-align:right;"><span style="background:#e8f5e9;color:#2E7D32;padding:4px 8px;border-radius:8px;display:inline-block;max-width:80%;text-align:left;">{prefix}{text}</span></p>'
            self._append_html(html)

    def _append_system(self, text, color="#666"):
        ts = datetime.now().strftime("%H:%M")
        html = f'<p style="margin:2px 0;color:{color};font-size:12px;"><b>[{ts}] 系统:</b> {text}</p>'
        self._append_html(html)

    def _send_message(self):
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        self._append_user(text)

        # 1. 先尝试本地解析
        parsed = ModelingCommandParser.parse(text)
        _log(f"_send_message parsed: {parsed}")
        if parsed and parsed.get('action') == 'create' and parsed.get('component_type'):
            # 简单创建指令直接本地执行（响应最快）
            self.mode_indicator.setText("⚡ 本地")
            self.status_label.setText("本地执行中...")
            self._execute_local_create(parsed, text)
            return
        elif parsed and parsed.get('action') == 'modify':
            self.mode_indicator.setText("⚡ 本地")
            self.status_label.setText("本地执行修改...")
            self._execute_local_modify(parsed, text)
            return

        # 2. 本地无法解析，调用 AI
        api_key = get_api_key()
        if not api_key:
            self._append_system("未配置 API Key，请在 ⚙️配置 中设置 DeepSeek API Key", "#d32f2f")
            return

        self._call_ai(text)

    def _execute_local_create(self, parsed, original_text):
        """本地执行创建命令"""
        comp_type = parsed['component_type']
        params = parsed.get('params', {})
        pos = parsed.get('position', {'mode': 'absolute', 'x': 0, 'y': 0, 'z': 0})
        arr = parsed.get('array')
        route_info = parsed.get('route')

        # 处理沿组件路径布置（最高优先级）
        path_info = parsed.get('path')
        path_placements = None
        if path_info:
            path_placements = self._build_component_path_placements(path_info, comp_type, params)
            if path_placements is None:
                self.status_label.setText("就绪")
                return

        # 处理路线
        route_placements = None
        if path_placements is None and route_info:
            route_placements = self._build_route_placements(route_info, comp_type, params)
            if route_placements is None:
                self.status_label.setText("就绪")
                return

        # 处理位置
        coords = None
        if path_placements is None and route_placements is None:
            base_x, base_y, base_z = 0, 0, 0
            if pos['mode'] == 'manual':
                # 未指定位置时：有阵列/路线则默认从原点开始，完全没有位置信息才弹窗
                if arr or route_info:
                    base_x, base_y, base_z = 0, 0, 0
                else:
                    coord = self._request_manual_coordinate(defaults=(0, 0, 0))
                    if coord is None:
                        self._append_system("已取消，未获取到放置坐标", "#999")
                        self.status_label.setText("就绪")
                        return
                    base_x, base_y, base_z = coord
            elif pos['mode'] == 'absolute':
                base_x, base_y, base_z = pos.get('x', 0), pos.get('y', 0), pos.get('z', 0)
            elif pos['mode'] == 'relative':
                # 相对坐标：以当前选中实体为基准
                infos = get_selected_component_info()
                if infos:
                    p = infos[0].get('params', {})
                    base_x = float(p.get('cx', p.get('x', p.get('x1', 0))))
                    base_y = float(p.get('cy', p.get('y', p.get('y1', 0))))
                    base_z = float(p.get('z_top', p.get('z', p.get('高度', p.get('height', 0)))))
                axis = pos.get('axis', 'z')
                distance = pos.get('distance', 0)
                if axis == 'x':
                    base_x += distance
                elif axis == 'y':
                    base_y += distance
                elif axis == 'z':
                    base_z += distance
            elif pos['mode'] == 'selected':
                # 以选中实体位置为基准（不偏移）
                infos = get_selected_component_info()
                if infos:
                    p = infos[0].get('params', {})
                    base_x = float(p.get('cx', p.get('x', p.get('x1', 0))))
                    base_y = float(p.get('cy', p.get('y', p.get('y1', 0))))
                    base_z = float(p.get('z_top', p.get('z', 0)))

            # 处理阵列
            coords = [(base_x, base_y, base_z)]
            if arr:
                mode = arr.get('mode')
                if mode == 'linear':
                    coords = linear_array(base_x, base_y, base_z,
                                          arr['count'], arr['spacing'], arr['axis'])
                elif mode == 'rectangular':
                    coords = rectangular_array(base_x, base_y, base_z,
                                               arr['rows'], arr['cols'],
                                               arr['row_spacing'], arr['col_spacing'])

        # 生成并放置
        results = []
        if path_placements:
            for x, y, z, child_comp in path_placements:
                ok, msg = place_component_at(child_comp, x, y, z)
                results.append((ok, msg))
        elif route_placements:
            for x, y, z, child_comp in route_placements:
                ok, msg = place_component_at(child_comp, x, y, z)
                results.append((ok, msg))
        else:
            for x, y, z in coords:
                ok, msg = place_component_at(
                    create_component(comp_type, params),
                    x, y, z
                )
                results.append((ok, msg))

        success = sum(1 for ok, _ in results if ok)
        total = len(results)
        if path_info:
            self._append_system(f"✅ 沿组件路径布置完成：{success}/{total} 个成功", "#2E7D32")
        elif route_info:
            self._append_system(f"✅ 沿路线布置完成：{success}/{total} 个成功", "#2E7D32")
            for i, (x, y, z, _) in enumerate(route_placements):
                self._append_system(f"  [{i+1}] 坐标: ({x:.1f}, {y:.1f}, {z:.1f})", "#666")
        elif total == 1:
            self._append_system(f"✅ {results[0][1]}" if results[0][0] else f"❌ {results[0][1]}",
                                "#2E7D32" if results[0][0] else "#d32f2f")
        else:
            self._append_system(f"✅ 批量布置完成：{success}/{total} 个成功", "#2E7D32")
        for i, (ok, msg) in enumerate(results):
            if not ok:
                self._append_system(f"  [{i+1}] ❌ {msg}", "#d32f2f")

        self.status_label.setText("就绪")

    def _build_route_placements(self, route_info, comp_type, comp_params):
        """根据解析出的 route 信息生成沿路线的 (x, y, z, oriented_child_comp) 列表"""
        mode = route_info.get('mode', 'line')
        spacing = route_info.get('spacing')
        count = route_info.get('count')

        route = None
        route_desc = ""

        if mode == 'arc':
            center = route_info.get('center')
            radius = route_info.get('radius')
            start_angle = route_info.get('start_angle')
            end_angle = route_info.get('end_angle')
            axis = route_info.get('axis', 'z')
            if center is None or radius is None or start_angle is None or end_angle is None:
                self._append_system("❌ 圆弧参数不完整，请提供圆心、半径、起始角、终止角", "#d32f2f")
                return None
            route = ArcRoute(center, radius, start_angle, end_angle, axis=axis)
            route_desc = f"圆弧 圆心{center} 半径{radius} 角度{start_angle}°→{end_angle}°"

        elif mode == 'selected_curve':
            arc = get_selected_curve_arc_params()
            if arc is None:
                self._append_system("❌ 未在 BIMBase 中读取到有效的曲线（圆弧）参数", "#d32f2f")
                return None
            route = ArcRoute(
                arc['center'], arc['radius'],
                arc['start_angle'], arc['end_angle'],
                axis=arc.get('axis', 'z')
            )
            route_desc = (f"选中曲线 圆心{arc['center']} 半径{arc['radius']} "
                          f"角度{arc['start_angle']}°→{arc['end_angle']}°")
            self._append_system(f"🛤 已读取选中曲线：{route_desc}", "#666")

        else:
            # line / selected_line / 默认路线
            start = route_info.get('start')
            end = route_info.get('end')

            if mode == 'selected_line':
                line_pts = get_selected_line_endpoints()
                if line_pts is None:
                    self._append_system("⚠️ 未在 BIMBase 中选中有效的线，使用默认路线", "#999")
                else:
                    start, end = line_pts
                    self._append_system(f"🛤 已读取选中线：{start} → {end}", "#666")

            if start is None or end is None:
                axis = route_info.get('axis', 'x')
                length = route_info.get('length') or 100000.0
                start = (0.0, 0.0, 0.0)
                if axis == 'x':
                    end = (length, 0.0, 0.0)
                elif axis == 'y':
                    end = (0.0, length, 0.0)
                else:
                    end = (0.0, 0.0, length)
                self._append_system(f"🛤 未指定路线几何，使用默认路线：{start} → {end}", "#999")

            route = Route.line(start, end)
            route_desc = f"直线 {start} → {end}"

        if spacing is None and count is None:
            spacing = 20000.0 if mode in ('line', 'selected_line') else 1000.0

        frames = route.sample_frames(spacing=spacing, count=count, include_end=True)
        _log(f"_build_route_placements: mode={mode}, route={route_desc}, spacing={spacing}, count={count}, frames={len(frames)}")

        if not frames:
            self._append_system("❌ 路线采样未生成任何点", "#d32f2f")
            return None

        placements = []
        for pos, tangent in frames:
            child = create_component(comp_type, comp_params)
            if child is None:
                continue
            oriented = orient_component(child, tangent, comp_type=comp_type)
            placements.append((pos[0], pos[1], pos[2], oriented))

        self._append_system(f"🛤 沿 {route_desc} 生成 {len(placements)} 个放置点", "#666")
        return placements

    def _build_component_path_placements(self, path_info, child_type, child_params):
        """
        根据 parsed['path'] 生成沿组件路径的 (x, y, z, oriented_child_comp) 列表。
        若未指定 host_type，则使用当前 BIMBase 中选中的第一个组件。
        """
        host_type = path_info.get('host_type')
        path_desc = path_info.get('path_desc', '')
        spacing = path_info.get('spacing')
        count = path_info.get('count')

        # 未指定 host 类型时，读取当前选中组件
        if host_type is None:
            infos = get_selected_component_info()
            if not infos:
                self._append_system("❌ 未指定基准组件，也未在 BIMBase 中选中组件", "#d32f2f")
                return None
            host_info = infos[0]
            host_type = host_info.get('type')
            host_params = host_info.get('params', {})
            self._append_system(f"📦 使用选中组件作为路径基准：{host_type}", "#666")
        else:
            # 即使指定了类型，也尝试用选中组件获取更准确的参数（位置等）
            infos = get_selected_component_info()
            if infos and infer_component_type_from_params(infos[0].get('params', {})) == host_type:
                host_params = infos[0].get('params', {})
            else:
                host_params = {}

        # 解析路径名
        path_name = resolve_path_name(host_type, path_desc)
        if path_name is None:
            self._append_system(f"❌ 无法解析路径描述：'{path_desc}'", "#d32f2f")
            return None

        # 默认间距/数量
        if spacing is None and count is None:
            spacing = 1000.0

        try:
            placements = build_oriented_components(
                host_type, host_params, path_desc,
                child_type, child_params,
                spacing=spacing, count=count, include_end=True
            )
        except Exception as e:
            _log(f"_build_component_path_placements error: {e}")
            self._append_system(f"❌ 沿组件路径采样失败：{e}", "#d32f2f")
            return None

        if not placements:
            self._append_system("❌ 未生成任何放置点", "#d32f2f")
            return None

        self._append_system(f"🛤 沿 {host_type} 的 {path_desc} 生成 {len(placements)} 个放置点", "#666")
        return placements

    def _execute_local_modify(self, parsed, original_text):
        """本地执行修改命令"""
        changes = parsed.get('params', {})
        target = parsed.get('target', {'mode': 'selected'})

        if target.get('mode') == 'selected':
            ok, msg = modify_selected_component(changes)
            self._append_system(f"{'✅' if ok else '❌'} {msg}",
                                "#2E7D32" if ok else "#d32f2f")
        else:
            self._append_system("❌ 仅支持修改选中组件", "#d32f2f")

        self.status_label.setText("就绪")

    def _call_ai(self, text):
        """调用 DeepSeek AI"""
        self.mode_indicator.setText("☁ AI")
        self.status_label.setText("AI思考中...")
        self.send_btn.setEnabled(False)

        # 组装系统提示词
        system_prompt = self._build_system_prompt()

        messages = [{"role": "system", "content": system_prompt}]
        for msg in self.chat_history[-10:]:
            messages.append(msg)
        messages.append({"role": "user", "content": text})

        self._current_ai_text = ""
        self._chat_thread = AIChatThread(
            api_key=get_api_key(),
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        self._chat_thread.chunk_ready.connect(self._on_ai_chunk)
        self._chat_thread.response_ready.connect(self._on_ai_response)
        self._chat_thread.error_occurred.connect(self._on_ai_error)
        self._chat_thread.start()

    def _build_system_prompt(self):
        return (
            "你是BIMBase智能建模助手。将用户自然语言指令转化为JSON操作指令。\n\n"
            "## 输出规则\n"
            "1. 必须只返回一个JSON对象，不要有任何解释文字或markdown标记。\n"
            "2. 信息不足时返回：{\"action\": \"ask\", \"question\": \"追问内容\"}\n"
            "3. 闲聊/问答返回：{\"action\": \"chat\", \"message\": \"回答内容\"}\n\n"
            "## 操作JSON格式\n"
            "创建组件: {\"action\": \"create\", \"component_type\": \"cylinder|box|cube|sphere|cone\", "
            "\"params\": {\"radius\":300, \"height\":800}, "
            "\"position\": {\"mode\": \"absolute\", \"x\":1000, \"y\":2000, \"z\":500}, "
            "\"array\": null or {\"mode\":\"linear\",\"axis\":\"x\",\"spacing\":1000,\"count\":5}, "
            "\"route\": null or {\"mode\":\"line\",\"start\":[0,0,0],\"end\":[100000,0,0],\"spacing\":20000}}\n"
            "修改组件: {\"action\": \"modify\", \"target\": {\"mode\":\"selected\"}, "
            "\"changes\": {\"radius\":400, \"height\":1000}}\n"
            "删除组件: {\"action\": \"delete\", \"target\": {\"mode\":\"selected\"}}\n\n"
            "## 路线说明\n"
            "route 用于沿一条路线等距布置组件，被放置的组件会自动旋转使其轴线/长边与路线切线方向一致。\n"
            "mode 可以是 line（直线）、arc（圆弧）、selected_line（读取 BIMBase 中已选中的直线/直线组件）、selected_curve（读取已选中的曲线/圆弧组件）。\n"
            "line: start/end 是路线起点/终点（mm）。\n"
            "arc: center 是圆心，radius 是半径，start_angle/end_angle 是起止角（度），axis 是圆弧所在平面的法向（默认 z）。\n"
            "例如：沿一条 100m 直线每隔 20m 生成半径 10 高 50 的圆柱：\n"
            "{\"action\":\"create\",\"component_type\":\"cylinder\",\"params\":{\"radius\":10,\"height\":50},"
            "\"route\":{\"mode\":\"line\",\"start\":[0,0,0],\"end\":[100000,0,0],\"spacing\":20000}}\n"
            "例如：沿圆心(0,0,0)半径500从0°到180°的圆弧每隔200mm放圆柱：\n"
            "{\"action\":\"create\",\"component_type\":\"cylinder\",\"params\":{\"radius\":50,\"height\":100},"
            "\"route\":{\"mode\":\"arc\",\"center\":[0,0,0],\"radius\":500,\"start_angle\":0,\"end_angle\":180,\"axis\":\"z\",\"spacing\":200}}\n\n"
            "## 坐标系说明\n"
            "BIMBase使用右手坐标系，单位mm：X向右，Y向前，Z向上。\n"
            "相对位置描述：上方=+Z，下方=-Z，右方=+X，左方=-X，前方=+Y，后方=-Y。\n\n"
            "## 组件参数说明\n"
            "- cylinder（圆柱）: radius（半径）, height（高度）\n"
            "- box（长方体）: length（长度/X）, width（宽度/Y）, height（高度/Z）\n"
            "- cube（正方体）: size（边长）\n"
            "- sphere（球体）: radius（半径）\n"
            "- cone（圆锥）: radius（底面半径）, height（高度）\n"
        )

    @pyqtSlot(str)
    def _on_ai_chunk(self, chunk):
        if not self._streaming:
            self._streaming = True
            ts = datetime.now().strftime("%H:%M")
            self._current_ai_html = f'<p style="margin:4px 0;text-align:right;"><span style="background:#e8f5e9;color:#2E7D32;padding:4px 8px;border-radius:8px;display:inline-block;max-width:80%;text-align:left;"><b>[{ts}] AI:</b> '
            self._append_html(self._current_ai_html)
        self._current_ai_text += chunk
        # 流式追加（简化：直接显示原始文本）
        self.chat_display.insertPlainText(chunk)
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @pyqtSlot(str)
    def _on_ai_response(self, full_text):
        self._streaming = False
        self.send_btn.setEnabled(True)
        self.status_label.setText("就绪")

        # 保存到历史
        self.chat_history.append({"role": "user", "content": self.input_box.text()})
        self.chat_history.append({"role": "assistant", "content": full_text})

        # 尝试解析JSON并执行
        self._execute_ai_json(full_text)

    @pyqtSlot(str)
    def _on_ai_error(self, error):
        self._streaming = False
        self.send_btn.setEnabled(True)
        self.status_label.setText("AI调用失败")
        self._append_system(f"❌ API调用失败: {error}", "#d32f2f")

    def _execute_ai_json(self, text):
        """解析AI返回的JSON并执行"""
        try:
            # 提取JSON
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            action = data.get('action')

            if action == 'chat':
                msg = data.get('message', '')
                self._append_ai(msg)
                return
            elif action == 'ask':
                q = data.get('question', '')
                self._append_ai(q)
                return
            elif action == 'create':
                self._execute_local_create(data, "AI指令")
                return
            elif action == 'modify':
                changes = data.get('changes', {})
                target = data.get('target', {'mode': 'selected'})
                if target.get('mode') == 'selected':
                    ok, msg = modify_selected_component(changes)
                    self._append_system(f"{'✅' if ok else '❌'} {msg}",
                                        "#2E7D32" if ok else "#d32f2f")
                return
            elif action == 'delete':
                self._append_system("❌ 删除功能暂不支持（BIMBase未提供删除API）", "#d32f2f")
                return
            else:
                self._append_system(f"⚠️ 未知操作: {action}", "#999")
        except json.JSONDecodeError:
            # 不是JSON，作为普通文本显示
            self._append_ai(text)
        except Exception as e:
            self._append_system(f"❌ 执行AI指令失败: {e}", "#d32f2f")
            _log(f"execute_ai_json error: {e}")

    def _show_config(self):
        dlg = APIConfigDialog(self)
        dlg.exec()
        self.cfg = load_config()

    def _clear_chat(self):
        self.chat_display.clear()
        self.chat_history.clear()
        self._show_welcome()

    def closeEvent(self, event):
        # 停止线程
        if self._chat_thread and self._chat_thread.isRunning():
            self._chat_thread.terminate()
            self._chat_thread.wait(1000)
        event.accept()
