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
from ai_modeling.component_factory import create_component, place_component_at, batch_place, _infer_component_type_from_comp, apply_component_color
from ai_modeling.component_registry import ComponentRegistry, get_registry
from ai_modeling.array_generator import linear_array, rectangular_array, polar_array
from ai_modeling.route import Route, ArcRoute, sample_route_for_components
from ai_modeling.component_path import (
    sample_placement_frames, orient_component, resolve_path_name,
    get_component_route, build_oriented_components
)
from ai_modeling.bimbase_modifier import (
    modify_selected_component, get_selected_component_info, infer_component_type_from_params,
    get_selected_line_endpoints, get_selected_curve_arc_params,
    get_selected_component_position, get_selected_instance_keys,
    delete_selected_components
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
        self.setGeometry(200, 150, 860, 680)
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
        self._registry = get_registry()

        self._build_ui()
        self._validate_registry()
        self._show_welcome()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 标题栏（仅保留模式指示器和功能按钮，标题已在窗口标题栏显示）
        header = QHBoxLayout()

        self.mode_indicator = QLabel("⚡ 本地")
        self.mode_indicator.setStyleSheet("QLabel { color: #1565C0; font-size: 12px; padding: 2px 6px; }")
        header.addWidget(self.mode_indicator)
        header.addStretch()

        config_btn = QPushButton("⚙️ 配置")
        config_btn.setFixedWidth(250)
        config_btn.setToolTip("配置 DeepSeek / 百度语音 API Key")
        config_btn.clicked.connect(self._show_config)
        header.addWidget(config_btn)

        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setFixedWidth(250)
        clear_btn.setToolTip("清空当前聊天记录")
        clear_btn.clicked.connect(self._clear_chat)
        header.addWidget(clear_btn)

        cache_btn = QPushButton("🧹 清理缓存")
        cache_btn.setFixedWidth(250)
        cache_btn.setToolTip("清空 AI 建模组件注册表和日志文件（不删除 BIMBase 几何体）")
        cache_btn.clicked.connect(self._clear_ai_cache)
        header.addWidget(cache_btn)
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
            "修改选中", "沿X轴阵列", "沿曲线布置", "删除选中",
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

    def _validate_registry(self):
        """启动时校验注册表与当前 BIMBase 场景的一致性"""
        try:
            from pyp3d import get_all_instancekey, get_entity_bounds
            self._registry.validate_and_update(
                get_all_keys_func=get_all_instancekey,
                bounds_func=get_entity_bounds
            )
        except Exception as e:
            _log(f"_validate_registry error: {e}")

    def _get_position_from_registry_by_entity_id(self):
        """根据当前选中的 entity id，在注册表中查找匹配的位置"""
        try:
            from ai_modeling.bimbase_modifier import get_selected_entity_ids
            entity_ids = get_selected_entity_ids()
            _log(f"_get_position_from_registry_by_entity_id: entity_ids count={len(entity_ids)}")
            for eid in entity_ids:
                # 优先用 entity 对象本身匹配（注册表 key 会同时包含 ModelId+ElementId）
                record = self._registry.get_by_entity_id(eid)
                if not record:
                    record = self._registry.get(eid)
                if record and record.get('placement'):
                    p = record['placement']
                    pos = (float(p.get('x', 0)), float(p.get('y', 0)), float(p.get('z', 0)))
                    _log(f"_get_position_from_registry_by_entity_id: matched {eid} -> {pos}")
                    return pos
        except Exception as e:
            _log(f"_get_position_from_registry_by_entity_id error: {e}")
        return None

    def _get_last_created_position(self):
        """获取最近一次 AI 生成组件的位置（用于未选中任何实体时的回退）"""
        try:
            records = self._registry.all_records()
            if not records:
                return None
            # 按 created_at 排序，取最新的一条
            latest = None
            latest_ts = ''
            for key, record in records.items():
                ts = record.get('created_at', '')
                if ts > latest_ts:
                    latest_ts = ts
                    latest = record
            if latest and latest.get('placement'):
                p = latest['placement']
                return (float(p.get('x', 0)), float(p.get('y', 0)), float(p.get('z', 0)))
        except Exception as e:
            _log(f"_get_last_created_position error: {e}")
        return None

    def _show_welcome(self):
        welcome = (
            "<p style='color:#666;'><b>👋 欢迎使用 BIMBase AI智能建模助手！</b></p>"
            "<p style='color:#666;'>你可以这样对我说：</p>"
            "<ul style='color:#666;'>"
            "<li><b>生成组件：</b>在(1000,2000,500)生成半径300高800的圆柱</li>"
            "<li><b>选中位置生成：</b>在选中的圆柱位置生成半径200的正方体</li>"
            "<li><b>相对位置：</b>在选中的实体上方500mm生成一个正方体，边长200</li>"
            "<li><b>复制组件：</b>复制选中的圆柱到(1000,2000,0)</li>"
            "<li><b>阵列生成：</b>沿X轴每隔1000mm生成一个圆柱，共5个，半径200高500</li>"
            "<li><b>沿直线布置：</b>沿选中的直线每隔500mm放半径50高100的圆柱，共10个</li>"
            "<li><b>沿曲线布置：</b>沿圆心(0,0,0)半径500从0°到180°的圆弧每隔200mm放圆柱</li>"
            "<li><b>修改组件：</b>把选中的圆柱半径改成400，高度改成1000</li>"
            "<li><b>修改保留位置：</b>把选中圆柱半径改成400，位置不变</li>"
            "<li><b>删除组件：</b>删除选中的组件</li>"
            "<li><b>批量布置：</b>生成3×3方阵，间距2000，每个位置放一个正方体边长300</li>"
            "</ul>"
            "<p style='color:#999;font-size:11px;'>💡 提示：先在BIMBase中选中组件，再说'修改选中的...'或'复制选中的...'</p>"
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
        elif parsed and parsed.get('action') == 'copy':
            self.mode_indicator.setText("⚡ 本地")
            self.status_label.setText("本地执行复制...")
            self._execute_local_copy(parsed, text)
            return
        elif parsed and parsed.get('action') == 'modify':
            self.mode_indicator.setText("⚡ 本地")
            self.status_label.setText("本地执行修改...")
            self._execute_local_modify(parsed, text)
            return
        elif parsed and parsed.get('action') == 'delete':
            self.mode_indicator.setText("⚡ 本地")
            self.status_label.setText("本地执行删除...")
            self._execute_local_delete(parsed, text)
            return
        elif parsed and parsed.get('action') == 'move':
            self.mode_indicator.setText("⚡ 本地")
            self.status_label.setText("本地执行移动...")
            self._execute_local_move(parsed, text)
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
        # 用户要求"不写入位置参数"时，放置坐标不烘焙进组件参数
        write_pos = parsed.get('write_position', True)
        # 整体上色（6面统一色）：颜色作为参数传入 create_component，
        # 由组件类的 replace() 保持颜色，阵列/路线布置的子组件同样生效
        color = parsed.get('color')
        if color:
            params = dict(params)
            params['颜色'] = color

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
                elif re.search(r'位置|坐标', original_text):
                    # 用户给了坐标语境但没解析出坐标（如语音连读中文数字）：
                    # 明确报错，不弹窗、不静默用默认位置
                    self._append_system("❌ 无法识别坐标，请用阿拉伯数字如 500,200,100", "#d32f2f")
                    self.status_label.setText("就绪")
                    return
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
                base_pos = get_selected_component_position()
                if base_pos is None:
                    # 回退1：按 entity id 查注册表
                    base_pos = self._get_position_from_registry_by_entity_id()
                    if base_pos:
                        self._append_system(f"⚠️ 未从实体读取到位置，使用注册表中该组件记录的位置 ({base_pos[0]:.1f}, {base_pos[1]:.1f}, {base_pos[2]:.1f}) 作为基准", "#f57c00")
                if base_pos is None:
                    # 相对基准解析失败必须报错终止，不允许静默回退到原点/上次位置（防止"假成功"）
                    self._append_system("❌ 相对布置失败：未在 BIMBase 中选中有效组件，无法确定相对基准，请先选中基准组件", "#d32f2f")
                    self.status_label.setText("就绪")
                    return
                base_x, base_y, base_z = base_pos
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
                base_pos = get_selected_component_position()
                if base_pos is None:
                    base_pos = self._get_position_from_registry_by_entity_id()
                    if base_pos:
                        self._append_system(f"⚠️ 未从实体读取到位置，使用注册表中该组件记录的位置 ({base_pos[0]:.1f}, {base_pos[1]:.1f}, {base_pos[2]:.1f})", "#f57c00")
                if base_pos is None:
                    base_pos = self._get_last_created_position()
                    if base_pos:
                        self._append_system(f"⚠️ 未检测到选中组件，使用最近一次生成位置 ({base_pos[0]:.1f}, {base_pos[1]:.1f}, {base_pos[2]:.1f}) 作为基准", "#f57c00")
                if base_pos is None:
                    self._append_system("❌ 未在 BIMBase 中选中有效组件，也无法从注册表获取位置", "#d32f2f")
                    self.status_label.setText("就绪")
                    return
                base_x, base_y, base_z = base_pos

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
                ok, msg = place_component_at(child_comp, x, y, z, bake=write_pos)
                results.append((ok, msg))
        elif route_placements:
            for x, y, z, child_comp in route_placements:
                ok, msg = place_component_at(child_comp, x, y, z, bake=write_pos)
                results.append((ok, msg))
        else:
            for x, y, z in coords:
                ok, msg = place_component_at(
                    create_component(comp_type, params),
                    x, y, z, bake=write_pos
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

    def _execute_local_copy(self, parsed, original_text):
        """本地执行复制命令：复制选中的组件到指定位置"""
        target = parsed.get('target', {'mode': 'selected'})
        pos = parsed.get('position', {'mode': 'selected'})
        _log(f"_execute_local_copy: text={original_text!r} pos={pos} array={parsed.get('array')}")

        if target.get('mode') != 'selected':
            self._append_system("❌ 复制功能目前仅支持复制选中组件", "#d32f2f")
            self.status_label.setText("就绪")
            return

        # 获取选中组件信息
        infos = get_selected_component_info()
        _log(f"_execute_local_copy: get_selected_component_info -> {len(infos)} infos")
        if not infos:
            self._append_system("❌ 未在 BIMBase 中选中任何组件，请先选中要复制的组件", "#d32f2f")
            self.status_label.setText("就绪")
            return

        info = infos[0]
        comp_type = info.get('type')
        params = info.get('params') or {}
        _log(f"_execute_local_copy: comp_type={comp_type} param_keys={list(params.keys())[:10]}")

        if not comp_type:
            # 尝试从注册表匹配
            keys = get_selected_instance_keys()
            if keys:
                record = self._registry.get(keys[0])
                if record:
                    comp_type = record.get('component_type')
                    params = record.get('params', {})
            if not comp_type:
                _log("_execute_local_copy: cannot infer component type, abort")
                self._append_system("❌ 无法识别选中组件类型", "#d32f2f")
                self.status_label.setText("就绪")
                return

        # 确定目标位置
        if pos['mode'] == 'absolute':
            x, y, z = pos.get('x', 0), pos.get('y', 0), pos.get('z', 0)
        elif pos['mode'] == 'relative':
            base_pos = get_selected_component_position()
            if base_pos is None:
                base_pos = self._get_position_from_registry_by_entity_id()
                if base_pos:
                    self._append_system("⚠️ 未从实体读取到位置，使用注册表中该组件记录的位置作为复制基准", "#f57c00")
            if base_pos is None:
                # 相对基准解析失败必须报错终止，不允许静默回退到上次位置（防止"假成功"）
                self._append_system("❌ 相对布置失败：未在 BIMBase 中选中有效组件，无法确定相对基准，请先选中基准组件", "#d32f2f")
                self.status_label.setText("就绪")
                return
            bx, by, bz = base_pos
            axis = pos.get('axis', 'z')
            distance = pos.get('distance', 0)
            x, y, z = bx, by, bz
            if axis == 'x':
                x += distance
            elif axis == 'y':
                y += distance
            elif axis == 'z':
                z += distance
        else:
            # 默认复制到原位置
            base_pos = get_selected_component_position()
            if base_pos is None:
                base_pos = self._get_position_from_registry_by_entity_id()
                if base_pos:
                    self._append_system("⚠️ 未从实体读取到位置，复制到注册表中该组件记录的位置", "#f57c00")
            if base_pos is None:
                base_pos = self._get_last_created_position()
                if base_pos:
                    self._append_system("⚠️ 未检测到选中组件，复制到最近一次生成位置", "#f57c00")
            if base_pos is None:
                self._append_system("❌ 无法读取选中组件位置，也没有可回退的位置", "#d32f2f")
                self.status_label.setText("就绪")
                return
            x, y, z = base_pos

        # 阵列复制：如“沿X轴每隔5米布置10个组件”（无类型布置指令由解析器转为 copy+array）
        arr = parsed.get('array')
        if arr and arr.get('mode') == 'linear' and arr.get('count'):
            coords = linear_array(x, y, z, int(arr['count']),
                                  float(arr.get('spacing', 0) or 0), arr.get('axis', 'x'))
            results = []
            for cx, cy, cz in coords:
                ok_i, msg_i = place_component_at(create_component(comp_type, params), cx, cy, cz,
                                                 bake=parsed.get('write_position', True))
                results.append((ok_i, msg_i))
            success = sum(1 for ok_i, _ in results if ok_i)
            self._append_system(
                f"{'✅' if success == len(results) else '⚠️'} 阵列复制完成：{success}/{len(results)} 个成功",
                "#2E7D32" if success == len(results) else "#f57c00")
            for i, (ok_i, msg_i) in enumerate(results):
                if not ok_i:
                    self._append_system(f"  [{i+1}] ❌ {msg_i}", "#d32f2f")
            self.status_label.setText("就绪")
            return

        ok, msg = place_component_at(create_component(comp_type, params), x, y, z,
                                     bake=parsed.get('write_position', True))
        self._append_system(
            f"{'✅' if ok else '❌'} {msg}",
            "#2E7D32" if ok else "#d32f2f"
        )
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
        preserve_position = parsed.get('preserve_position', False)

        if target.get('mode') != 'selected':
            self._append_system("❌ 仅支持修改选中组件", "#d32f2f")
            self.status_label.setText("就绪")
            return

        # 如要求保留位置，先记录当前位置
        original_pos = None
        selected_keys = get_selected_instance_keys()
        if preserve_position:
            original_pos = get_selected_component_position()
            if original_pos is None and selected_keys:
                record = self._registry.get(selected_keys[0])
                if record:
                    p = record.get('placement', {})
                    original_pos = (float(p.get('x', 0)), float(p.get('y', 0)), float(p.get('z', 0)))

        ok, msg = modify_selected_component(changes)
        self._append_system(f"{'✅' if ok else '❌'} {msg}",
                            "#2E7D32" if ok else "#d32f2f")

        # 保留位置：更新注册表中的 placement 为修改前的位置
        if ok and preserve_position and original_pos is not None and selected_keys:
            try:
                record = self._registry.get(selected_keys[0])
                if record:
                    record['placement'] = {
                        'x': float(original_pos[0]),
                        'y': float(original_pos[1]),
                        'z': float(original_pos[2]),
                    }
                    self._registry.save()
                    self._append_system(f"📍 已保留原位置: ({original_pos[0]:.1f}, {original_pos[1]:.1f}, {original_pos[2]:.1f})")
            except Exception as e:
                _log(f"_execute_local_modify preserve_position error: {e}")

        self.status_label.setText("就绪")

    def _execute_local_delete(self, parsed, original_text):
        """本地执行删除命令：删除当前在 BIMBase 中选中的组件"""
        target = parsed.get('target') or {'mode': 'selected'}

        # 批量删除（所有/全部）暂不支持
        if '所有' in original_text or '全部' in original_text:
            self._append_system("❌ 暂不支持批量删除，请先在 BIMBase 中选中要删除的组件，再说'删除选中的组件'", "#d32f2f")
            self.status_label.setText("就绪")
            return

        if target.get('mode') != 'selected':
            self._append_system("❌ 删除功能目前仅支持删除选中组件，请先在 BIMBase 中选中", "#d32f2f")
            self.status_label.setText("就绪")
            return

        # 多选时弹框确认数量（单个直接删）
        try:
            from ai_modeling.bimbase_modifier import get_selected_entity_ids
            n_sel = max(len(get_selected_entity_ids()), len(get_selected_instance_keys()))
        except Exception as e:
            _log(f"_execute_local_delete count selection error: {e}")
            n_sel = 0
        if n_sel > 1:
            try:
                from PyQt5.QtWidgets import QMessageBox
            except ImportError:
                from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"当前选中了 {n_sel} 个组件，确定全部删除吗？\n（该操作不可撤销）",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                self._append_system("已取消删除", "#999")
                self.status_label.setText("就绪")
                return

        ok, msg, _deleted = delete_selected_components()
        self._append_system(f"{'✅' if ok else '❌'} {msg}",
                            "#2E7D32" if ok else "#d32f2f")
        self.status_label.setText("就绪")

    def _execute_local_move(self, parsed, original_text=""):
        """本地执行移动命令：对目标实体施加平移变换，并同步注册表 placement"""
        target = parsed.get('target') or {'mode': 'selected'}
        move = parsed.get('move')
        if not move:
            self._append_system("❌ 未解析到移动参数（方向+距离 或 目标坐标）", "#d32f2f")
            self.status_label.setText("就绪")
            return

        # 1. 解析目标实体（选中 / 注册表按类型或第N个/最后一个查找）
        eid, record = self._resolve_move_target(parsed, target)
        if eid is None:
            self._append_system("❌ 未找到要移动的组件，请先在 BIMBase 中选中目标组件", "#d32f2f")
            self.status_label.setText("就绪")
            return

        # 2. 计算平移增量（mm）
        new_pos = None
        if move.get('mode') == 'absolute':
            cur = self._get_entity_position(eid)
            if cur is None and record:
                p = record.get('placement') or {}
                cur = (float(p.get('x', 0)), float(p.get('y', 0)), float(p.get('z', 0)))
            if cur is None:
                self._append_system("❌ 无法读取目标组件当前位置，绝对移动失败", "#d32f2f")
                self.status_label.setText("就绪")
                return
            new_pos = (float(move.get('x', 0)), float(move.get('y', 0)), float(move.get('z', 0)))
            dx, dy, dz = new_pos[0] - cur[0], new_pos[1] - cur[1], new_pos[2] - cur[2]
        else:
            dx = float(move.get('dx', 0))
            dy = float(move.get('dy', 0))
            dz = float(move.get('dz', 0))

        # 3. 施加平移变换
        try:
            try:
                from pyp3d import python_transformation_operation, trans
            except ImportError:
                from pyp3d import python_transformation_operation, translate as trans
            python_transformation_operation(eid, trans(dx, dy, dz))
        except Exception as e:
            _log(f"_execute_local_move transform error: {e}")
            self._append_system(f"❌ 移动失败: {e}", "#d32f2f")
            self.status_label.setText("就绪")
            return

        # 4. 同步注册表 placement
        if record is not None:
            try:
                p = record.get('placement') or {}
                if new_pos is None:
                    new_pos = (float(p.get('x', 0)) + dx,
                               float(p.get('y', 0)) + dy,
                               float(p.get('z', 0)) + dz)
                record['placement'] = {
                    'x': float(new_pos[0]),
                    'y': float(new_pos[1]),
                    'z': float(new_pos[2]),
                }
                self._registry.save()
            except Exception as e:
                _log(f"_execute_local_move registry update error: {e}")

        if move.get('mode') == 'absolute':
            self._append_system(f"✅ 已移动到 ({new_pos[0]}, {new_pos[1]}, {new_pos[2]})", "#2E7D32")
        else:
            self._append_system(f"✅ 已移动 ({dx}, {dy}, {dz}) mm", "#2E7D32")
        self.status_label.setText("就绪")

    def _resolve_move_target(self, parsed, target):
        """按 target/component_type 解析要移动的实体。
        返回 (entity_id, registry_record)；失败返回 (None, None)。"""
        mode = target.get('mode', 'selected')
        comp_type = parsed.get('component_type')

        # 选中模式且未按类型指定时，直接使用当前选中实体
        if mode == 'selected' and not comp_type:
            try:
                from ai_modeling.bimbase_modifier import get_selected_entity_ids, get_selected_instance_keys
                eids = get_selected_entity_ids()
                if eids:
                    record = None
                    keys = get_selected_instance_keys()
                    if keys:
                        record = self._registry.get(keys[0])
                    if record is None:
                        record = self._registry.get_by_entity_id(eids[0])
                    return eids[0], record
            except Exception as e:
                _log(f"_resolve_move_target selected error: {e}")
            return None, None

        # 注册表查找：按类型过滤（如有），支持 第N个 / 最后一个
        items = list(self._registry.all_records().items())
        if comp_type:
            items = [(k, r) for k, r in items if r.get('component_type') == comp_type]
        items.sort(key=lambda kv: kv[1].get('created_at', ''))
        if not items:
            return None, None
        if mode == 'index':
            idx = int(target.get('index', 0))
            if not (0 <= idx < len(items)):
                return None, None
            _, record = items[idx]
        else:
            _, record = items[-1]
        eid = self._find_entity_by_id_string(record.get('entity_id'))
        return eid, record

    def _find_entity_by_id_string(self, eid_str):
        """把注册表中的 "ModelId=..;ElementId=.." 字符串还原为场景中的实体对象"""
        if not eid_str or not isinstance(eid_str, str):
            return None
        try:
            mid = eid_val = None
            for part in eid_str.split(';'):
                k, _, v = part.partition('=')
                if k.strip() == 'ModelId':
                    mid = int(v)
                elif k.strip() == 'ElementId':
                    eid_val = int(v)
            if eid_val is None:
                return None
            from pyp3d import get_all_entityid
            for e in get_all_entityid() or []:
                ee = getattr(e, '_ElementId', None)
                em = getattr(e, '_ModelId', None)
                if ee == eid_val and (mid is None or em == mid):
                    return e
        except Exception as e:
            _log(f"_find_entity_by_id_string error: {e}")
        return None

    def _get_entity_position(self, eid):
        """读取实体当前位置：复用 bimbase_modifier 的 \\a_transformation 提取链路"""
        try:
            from ai_modeling.bimbase_modifier import _read_params_from_entity
            params = _read_params_from_entity(eid)
            if params and params.get('x') is not None:
                return (float(params.get('x', 0)),
                        float(params.get('y', 0)),
                        float(params.get('z', 0)))
        except Exception as e:
            _log(f"_get_entity_position error: {e}")
        return None

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
            "创建组件: {\"action\": \"create\", \"component_type\": \"cylinder|box|cube|sphere|cone|pier|anchor|gate_pier|pile_foundation\", "
            "\"params\": {\"radius\":300, \"height\":800}, "
            "\"position\": {\"mode\": \"absolute\", \"x\":1000, \"y\":2000, \"z\":500}, "
            "\"array\": null or {\"mode\":\"linear\",\"axis\":\"x\",\"spacing\":1000,\"count\":5}, "
            "\"route\": null or {\"mode\":\"line\",\"start\":[0,0,0],\"end\":[100000,0,0],\"spacing\":20000}}\n"
            "复制组件: {\"action\": \"copy\", \"target\": {\"mode\":\"selected\"}, "
            "\"position\": {\"mode\": \"absolute\", \"x\":1000, \"y\":2000, \"z\":500}}\n"
            "修改组件: {\"action\": \"modify\", \"target\": {\"mode\":\"selected\"}, "
            "\"changes\": {\"radius\":400, \"height\":1000}, "
            "\"preserve_position\": false}\n"
            "删除组件: {\"action\": \"delete\", \"target\": {\"mode\":\"selected\"}}\n"
            "移动组件: {\"action\": \"move\", \"target\": {\"mode\":\"selected\"}, "
            "\"move\": {\"mode\":\"relative\",\"dx\":0,\"dy\":0,\"dz\":500}} "
            "或 {\"mode\":\"absolute\",\"x\":1000,\"y\":2000,\"z\":0}}\n\n"
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
            "- pier（引桥桥墩）: 盖梁总长, 盖梁总高, 盖梁宽, 墩柱直径, 墩柱间距, 墩高, 系梁根数\n"
            "- gate_pier（门式桥墩）: 盖梁总长, 盖梁总高, 盖梁宽, 墩高, 墩柱间距, 柱顶宽, 柱底宽, 柱顶厚, 柱底厚, 系梁根数\n"
            "- pile_foundation（承台及桩基）: 承台长, 承台宽, 承台高, 桩径, 桩长, 桩间距, 桩列数, 桩排数\n"
            "- anchor（索缆锚锭/索塔锚块）: 锚块总长, 锚块总高, 锚块宽度, 承台长度, 承台宽度, 承台高度, 底柱半径, 底柱高度\n"
            "## 位置模式说明\n"
            "- absolute: 绝对坐标 (x,y,z)\n"
            "- relative: 相对选中实体偏移，如 {\"mode\":\"relative\",\"axis\":\"z\",\"distance\":500} 表示上方 500mm\n"
            "- selected: 使用选中实体当前位置\n"
            "## 保留位置\n"
            "当用户说'位置不变'、'保留位置'时，modify 指令设置 preserve_position=true\n"
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
                    preserve = data.get('preserve_position', False)
                    original_pos = None
                    selected_keys = get_selected_instance_keys()
                    if preserve:
                        original_pos = get_selected_component_position()
                        if original_pos is None and selected_keys:
                            record = self._registry.get(selected_keys[0])
                            if record:
                                p = record.get('placement', {})
                                original_pos = (float(p.get('x', 0)), float(p.get('y', 0)), float(p.get('z', 0)))
                    ok, msg = modify_selected_component(changes)
                    self._append_system(f"{'✅' if ok else '❌'} {msg}",
                                        "#2E7D32" if ok else "#d32f2f")
                    if ok and preserve and original_pos is not None and selected_keys:
                        try:
                            record = self._registry.get(selected_keys[0])
                            if record:
                                record['placement'] = {
                                    'x': float(original_pos[0]),
                                    'y': float(original_pos[1]),
                                    'z': float(original_pos[2]),
                                }
                                self._registry.save()
                                self._append_system(f"📍 已保留原位置: ({original_pos[0]:.1f}, {original_pos[1]:.1f}, {original_pos[2]:.1f})")
                        except Exception as e:
                            _log(f"_execute_ai_json preserve_position error: {e}")
                return
            elif action == 'copy':
                self._execute_local_copy(data, "AI指令")
                return
            elif action == 'delete':
                self._execute_local_delete(data, "AI指令")
                return
            elif action == 'move':
                self._execute_local_move(data, "AI指令")
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

    def _clear_ai_cache(self):
        """清理 AI 建模缓存：注册表 + 日志"""
        try:
            from PyQt5.QtWidgets import QMessageBox
            _Qt = 5
        except ImportError:
            from PyQt6.QtWidgets import QMessageBox
            _Qt = 6

        reply = QMessageBox.question(
            self,
            "确认清理缓存",
            "确定要清空 AI 建模的组件注册表和日志文件吗？\n（不会删除 BIMBase 中已生成的几何体）",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        cleared = []
        try:
            count = self._registry.clear()
            cleared.append(f"注册表记录 {count} 条")
        except Exception as e:
            _log(f"_clear_ai_cache registry error: {e}")
            self._append_system(f"❌ 清空注册表失败: {e}", "#d32f2f")

        log_files = [
            'ai_modeling.log',
            'ai_modeling_debug.log',
            'debug_selection.log',
            'ai_modeling_config_debug.log',
        ]
        removed_logs = 0
        for name in log_files:
            path = os.path.join(_plugin_dir, name)
            try:
                if os.path.exists(path):
                    os.remove(path)
                    removed_logs += 1
            except Exception as e:
                _log(f"_clear_ai_cache remove log {name} error: {e}")
        if removed_logs > 0:
            cleared.append(f"日志文件 {removed_logs} 个")

        if cleared:
            self._append_system(f"🧹 已清理：{', '.join(cleared)}")
        else:
            self._append_system("🧹 没有需要清理的缓存")

    def closeEvent(self, event):
        # 停止线程
        if self._chat_thread and self._chat_thread.isRunning():
            self._chat_thread.terminate()
            self._chat_thread.wait(1000)
        event.accept()
