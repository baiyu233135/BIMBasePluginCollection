# -*- coding: utf-8 -*-
"""
AI助手面板 - v1.5 P2

功能:
1. DeepSeek API 对话 (交互询问 + 帮助画图)
2. 本地自然语言解析(基础): 识别"画圆/矩形/直线"等指令并自动执行
3. API配置对话框(方案B): 在面板内输入Key保存到本地文件

自然语言支持(基础):
- "在100,200画一个半径50的圆" → 自动画圆
- "画一个长200宽100的矩形" → 自动画矩形
- "删除选中的" → 删除选中元素
- "怎么用拉伸" → 给出操作步骤 (AI回答)
"""
import os
import json
import re
import traceback
from datetime import datetime

from utils.ai_executor import AICommandExecutor, AIResponseParser
from utils.voice_input import VoiceRecorder, BaiduSpeechRecognizer

try:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
        QPushButton, QLabel, QDialog, QFormLayout, QMessageBox,
        QSplitter, QListWidget, QListWidgetItem, QSizePolicy, QCheckBox, QComboBox,
        QGroupBox
    )
    from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt5.QtGui import QColor, QFont
except ImportError:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
        QPushButton, QLabel, QDialog, QFormLayout, QMessageBox,
        QSplitter, QListWidget, QListWidgetItem, QSizePolicy, QComboBox,
        QGroupBox
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QColor, QFont


# ========== 本地自然语言解析(基础) ==========

class LocalCommandParser:
    """本地命令解析器 - 无需联网，基础级别"""

    # 元素类型映射
    ELEMENT_MAP = {
        '圆': 'circle', '圆形': 'circle', 'circle': 'circle', 'c': 'circle',
        '矩形': 'rectangle', '长方形': 'rectangle', 'rect': 'rectangle', 'rec': 'rectangle',
        '直线': 'line', '线段': 'line', 'line': 'line', 'l': 'line',
        '圆弧': 'arc', 'arc': 'arc', 'a': 'arc',
        '多段线': 'polyline', 'pline': 'polyline', 'pl': 'polyline',
        '多边形': 'polygon', 'polygon': 'polygon',
        '椭圆': 'ellipse', 'ellipse': 'ellipse',
        '点': 'point', 'point': 'point', 'po': 'point',
        '样条': 'spline', 'spline': 'spline',
        '圆柱': '圆柱', '圆柱体': '圆柱',
        '正方体': '正方体', '立方体': '正方体',
        '长方体': '长方体', '拉伸体': '长方体',
        '球体': '球体', 'sphere': '球体', '球': '球体',
        '直角三棱柱': '直角三棱柱', '三棱柱': '直角三棱柱',
        '引桥桥墩': '引桥桥墩', '桥墩': '引桥桥墩',
    }

    # 操作映射
    ACTION_MAP = {
        '画': 'draw', '绘制': 'draw', '创建': 'draw', '画一个': 'draw',
        '删除': 'delete', '移除': 'delete', 'del': 'delete', 'e': 'delete', 'erase': 'delete',
        '复制': 'copy', '拷贝': 'copy', 'co': 'copy',
        '移动': 'move', 'm': 'move',
        '旋转': 'rotate', 'ro': 'rotate',
        '缩放': 'scale', 'sc': 'scale',
        '镜像': 'mirror', 'mi': 'mirror',
        '偏移': 'offset', 'o': 'offset',
        '拉伸': 'stretch', 's': 'stretch',
        '修剪': 'trim', 'tr': 'trim',
        '延伸': 'extend', 'ex': 'extend',
        '圆角': 'fillet', 'f': 'fillet',
        '倒角': 'chamfer', '倒斜角': 'chamfer', 'cha': 'chamfer',
        '阵列': 'array', 'ar': 'array',
        '打断': 'break', 'br': 'break',
        '合并': 'join', 'j': 'join',
        '分解': 'explode', 'x': 'explode',
    }

    # 面名称映射（用于三视图修改指令）
    FACE_NAME_MAP = {
        '顶面': 'top', 'top': 'top', '俯视图': 'top', '上面': 'top',
        '前视图': 'side_a', 'side_a': 'side_a', '侧面a': 'side_a', '前视': 'side_a',
        '左视图': 'side_b', 'side_b': 'side_b', '侧面b': 'side_b', '左视': 'side_b',
        '底面': 'bottom', 'bottom': 'bottom',
        '所有面': 'all', '全部面': 'all', 'all': 'all',
    }

    # 轴向映射（用于沿轴批量布置）
    AXIS_MAP = {
        'x轴': 'x', 'y轴': 'y', 'z轴': 'z',
        'x': 'x', 'y': 'y', 'z': 'z',
    }

    # 支持的3D实体类型
    SOLID_TYPES = {'圆柱', '正方体', '长方体', '球体', '直角三棱柱', '引桥桥墩'}

    @classmethod
    def parse(cls, text: str):
        """
        Phase 4增强: 解析自然语言，返回AI指令格式或None
        支持: 画图/删除/修改属性/变换/同步/面编辑
        """
        text = text.strip().lower().replace('，', ',').replace('（', '(').replace('）', ')')

        # Agent 快捷指令（无需操作关键词）
        if '重新生成面' in text or 'regenerate face' in text or '生成面' in text:
            return {'action': 'agent', 'tool': 'regenerate_faces', 'params': {}}
        if '应用面修改' in text or 'apply face' in text:
            return {'action': 'agent', 'tool': 'apply_face_changes', 'params': {}}
        if '查询状态' in text or 'query state' in text or '状态' in text:
            return {'action': 'agent', 'tool': 'query_state', 'params': {}}
        if '退出面编辑' in text or '退出面' in text:
            return {'action': 'agent', 'tool': 'exit_face_edit', 'params': {}}

        # 沿轴批量布置：如"沿X轴长度100间距20生成圆柱"（优先于操作检测，避免 x/y/z 被识别为命令快捷键）
        axis_cmd = cls._parse_axis_create(text)
        if axis_cmd:
            return axis_cmd

        # 1. 检测操作
        action = None
        for cn, en in cls.ACTION_MAP.items():
            if cn.lower() in text:
                action = en
                break

        if not action:
            # 尝试检测修改类指令 (如"把第一个矩形加长50")
            return cls._parse_modify(text)

        # 2. 删除操作
        if action == 'delete':
            target = cls._parse_target(text)
            return {'action': 'delete', 'target': target}

        # 3. 同步操作
        if '同步' in text or 'sync' in text:
            # 如果明确提到 Agent 同步（带目标），否则走旧 sync
            return {'action': 'agent', 'tool': 'sync_to_bimbase', 'params': {}}

        # 4. 检测元素类型
        elem_type = None
        for cn, cmd in cls.ELEMENT_MAP.items():
            if cn.lower() in text:
                elem_type = cmd
                break

        if action == 'draw' and not elem_type:
            return None

        if action != 'draw' and not elem_type:
            return {'action': action, 'params': {}}

        # 5. 提取参数
        params = cls._extract_params(text)

        return {
            'action': 'create' if action == 'draw' else action,
            'element': elem_type,
            'params': params
        }

    @classmethod
    def _split_target_prop(cls, combined_text: str):
        """从不带'的'的句子中拆分 target 和 property。
        例如: '圆柱半径' -> ('圆柱', '半径'), '高度' -> ('', '高度'),
              '宽度141.42' -> ('141.42', '宽度')"""
        import re
        if not combined_text:
            return '', ''
        # 也匹配中文属性名（支持结尾或开头）
        cn_props = ['高度', '长度', '宽度', '深度', '半径', '厚度', '颜色', '线宽', '线型', '边长']
        for prop in sorted(cn_props, key=len, reverse=True):
            if combined_text.endswith(prop):
                target = combined_text[:-len(prop)].strip()
                return target, prop
            if combined_text.startswith(prop):
                target = combined_text[len(prop):].strip()
                return target, prop
        # 匹配英文属性名（支持结尾或开头）
        en_props = ['height', 'width', 'length', 'depth', 'radius', 'thickness', 'color', 'size']
        text_lower = combined_text.lower()
        for prop in sorted(en_props, key=len, reverse=True):
            if text_lower.endswith(prop):
                target = combined_text[:-len(prop)].strip()
                return target, prop
            if text_lower.startswith(prop):
                target = combined_text[len(prop):].strip()
                return target, prop
        return combined_text, ''

    @classmethod
    def _parse_modify(cls, text: str):
        """解析修改类指令，如:\"把第一个矩形加长50\"\"所有元素高度改成200\""""
        import re

        # 0. 颜色修改模式（优先，避免与尺寸修改混淆）
        color_map = {
            '红': (255, 0, 0), '红色': (255, 0, 0),
            '绿': (0, 255, 0), '绿色': (0, 255, 0),
            '蓝': (0, 0, 255), '蓝色': (0, 0, 255),
            '黄': (255, 255, 0), '黄色': (255, 255, 0),
            '黑': (0, 0, 0), '黑色': (0, 0, 0),
            '白': (255, 255, 255), '白色': (255, 255, 255),
            '紫': (128, 0, 128), '紫色': (128, 0, 128),
            '橙': (255, 165, 0), '橙色': (255, 165, 0),
            '灰': (128, 128, 128), '灰色': (128, 128, 128),
            '粉红': (255, 192, 203), '粉色': (255, 192, 203),
        }
        color_pattern = r'(?:把|将|让)?\s*(.+?)\s*(?:的)?\s*(颜色|color|线型|line_type|线宽|line_width)\s*(?:改成|变成|设为)\s*(.+)'
        m = re.search(color_pattern, text)
        if m:
            target_text = m.group(1).strip()
            prop_text = m.group(2).strip()
            val_text = m.group(3).strip()
            target = cls._parse_target_text(target_text)
            prop = cls._parse_property_text(prop_text)
            if prop == 'color':
                val = color_map.get(val_text, val_text)
                if isinstance(val, str) and ',' in val:
                    try:
                        parts = [int(x.strip()) for x in val.split(',')]
                        if len(parts) >= 3:
                            val = tuple(parts[:3])
                    except Exception:
                        pass
            elif prop == 'line_type':
                type_map = {'实线': 'solid', 'solid': 'solid',
                           '虚线': 'dashed', 'dashed': 'dashed',
                           '点线': 'dotted', 'dotted': 'dotted'}
                val = type_map.get(val_text, val_text)
            elif prop == 'line_width':
                try:
                    val = float(val_text)
                except Exception:
                    val = 0.25
            else:
                val = val_text
            return {'action': 'modify', 'target': target, 'changes': {prop: val}}

        # 模式: 所有/全部 + 元素类型 + 属性 + 改成
        all_pattern = r'(?:所有|全部)\s*(.+?)\s*(?:的)?\s*(.+?)\s*(?:改成|变成|设为)\s*([+-]?\d+\.?\d*)'
        m = re.search(all_pattern, text)
        if m:
            elem_type_text = m.group(1).strip()
            prop_text = m.group(2).strip()
            val_str = m.group(3).strip()
            elem_type = None
            for cn, cmd in cls.ELEMENT_MAP.items():
                if cn.lower() in elem_type_text:
                    elem_type = cmd
                    break
            prop = cls._parse_property_text(prop_text)
            target = {'element_type': elem_type} if elem_type else {'index': 'all'}
            changes = {prop: float(val_str)}
            if elem_type and elem_type in ('圆柱', '正方体', '长方体', '直角三棱柱'):
                return {
                    'action': 'agent',
                    'tool': 'modify_component',
                    'params': {'target': target, 'changes': changes, 'path': 'auto'}
                }
            return {'action': 'modify', 'target': target, 'changes': changes}

        # 1. 先尝试匹配带 "的" 的模式（最准确）
        pat_with_de = r'(?:把|将|让)\s*(.+?)\s*的\s*(\S+?)\s*(?:改成|变成|设为|改为|增加|加长|加宽|加高|加大|减少|缩短|减小)\s*([+-]?\d+\.?\d*)'
        m = re.search(pat_with_de, text)
        if m:
            target_text = m.group(1).strip()
            prop_text = m.group(2).strip()
            val_str = m.group(3).strip()
        else:
            # 2. 再尝试匹配不带 "的" 的模式
            pat_without_de = r'(?:把|将|让)\s*(.*?)\s*(?:改成|变成|设为|改为|增加|加长|加宽|加高|加大|减少|缩短|减小)\s*([+-]?\d+\.?\d*)'
            m = re.search(pat_without_de, text)
            if m:
                combined_text = m.group(1).strip()
                val_str = m.group(2).strip()
                target_text, prop_text = cls._split_target_prop(combined_text)
            else:
                # 3. 回退到旧模式（兼容其他格式）
                modify_patterns = [
                    r'(?:把|将|让)\s*(.+?)\s*(?:的)?\s*(.+?)\s*(?:改成|变成|设为|改为)\s*([+-]?\d+\.?\d*)',
                    r'(?:把|将|让)\s*(.+?)\s*(?:的)?\s*(.+?)\s*(?:增加|加长|加宽|加高|加大)\s*([+-]?\d+\.?\d*)',
                    r'(?:把|将|让)\s*(.+?)\s*(?:的)?\s*(.+?)\s*(?:减少|缩短|减小)\s*([+-]?\d+\.?\d*)',
                    r'(.+?)\s*(?:的)?\s*(.+?)\s*(?:改成|变成|设为|改为)\s*([+-]?\d+\.?\d*)',
                ]
                for pat in modify_patterns:
                    m = re.search(pat, text)
                    if m:
                        target_text = m.group(1).strip()
                        prop_text = m.group(2).strip()
                        val_str = m.group(3).strip()
                        break
                else:
                    # 4. 纯属性修改（无主语）："高度改成100"、"半径增加20"
                    prop_only_pat = r'(高度|宽度|半径|长度|大小|深度|厚度|边长|直角边1|直角边2|h|a|b|r)\s*(?:改成|变成|设为|改为|增加|加长|加宽|加高|加大|减少|缩短|减小)\s*([+-]?\d+\.?\d*)'
                    m = re.search(prop_only_pat, text)
                    if m:
                        target_text = ''
                        prop_text = m.group(1).strip()
                        val_str = m.group(2).strip()
                    else:
                        return None

        target = cls._parse_target_text(target_text)
        prop = cls._parse_property_text(prop_text)
        if not prop:
            return None
        changes = {prop: float(val_str)}

        # 处理增加/减少（相对值）
        if '增加' in text or '加长' in text or '加宽' in text or '加大' in text:
            changes[prop] = '+' + val_str
        elif '减少' in text or '缩短' in text or '减小' in text:
            changes[prop] = '-' + val_str

        # 如果是组件级参数修改，交给 Agent 处理（支持双路径+自动同步）
        if 'component_type' in target:
            return {
                'action': 'agent',
                'tool': 'modify_component',
                'params': {'target': target, 'changes': changes, 'path': 'auto'}
            }

        # 几何参数（宽/高/半径等）即使 target 未识别为组件，也提升为 Agent 路径，
        # 让 Agent 根据当前选中元素判断是否为参数化组件并处理歧义。
        GEOM_PARAMS = {'width', 'height', 'radius', 'depth', 'size', 'length', 'thickness', 'a', 'b', 'h'}
        if prop in GEOM_PARAMS:
            return {
                'action': 'agent',
                'tool': 'modify_component',
                'params': {'target': target, 'changes': changes, 'path': 'auto'}
            }

        return {'action': 'modify', 'target': target, 'changes': changes}

    @classmethod
    def _parse_target_text(cls, text: str):
        """解析目标描述文本"""
        import re
        text = text.strip()

        # 第一个/第二个/第N个
        order_match = re.search(r'第\s*(\d+)\s*个', text)
        if order_match:
            idx = int(order_match.group(1)) - 1
            elem_type = None
            for cn, cmd in cls.ELEMENT_MAP.items():
                if cn.lower() in text:
                    elem_type = cmd
                    break
            if elem_type:
                # 如果是参数化组件，用 component_type 定位以便走 Agent 路径
                if elem_type in ('圆柱', '正方体', '长方体', '直角三棱柱'):
                    return {'component_type': elem_type, 'index': idx}
                return {'element_type': elem_type, 'index': idx}
            return {'index': idx}

        # 面名称（三视图）
        for cn, face_name in cls.FACE_NAME_MAP.items():
            if cn.lower() in text:
                return {'face_name': face_name}

        # 组件类型（用于组件级参数修改）
        component_type_map = {
            '三棱柱': '直角三棱柱',
            '拉伸盒': 'SweepBoxComponent',
            '圆柱': '圆柱',
            '正方体': '正方体',
            '长方体': '长方体',
            '多边形': 'Polygon3DComponent',
            '圆弧': 'Arc3DComponent',
            '椭圆': 'Ellipse3DComponent',
            '引桥桥墩': '引桥桥墩',
            '桥墩': '引桥桥墩',
        }
        for cn, ct in component_type_map.items():
            if cn in text:
                return {'component_type': ct}

        # 通用"组件"关键词
        if '组件' in text or '源组件' in text:
            return {'component': True}

        # 选中的
        if '选中' in text:
            return {'index': 'selected'}

        # 元素类型
        for cn, cmd in cls.ELEMENT_MAP.items():
            if cn.lower() in text:
                return {'element_type': cmd}

        return {'index': 'selected'}

    @classmethod
    def _parse_property_text(cls, text: str):
        """解析属性名"""
        prop_map = {
            # 几何尺寸
            '长': 'width', '长度': 'width', 'length': 'width',
            '宽': 'width', '宽度': 'width', 'width': 'width',
            '高': 'height', '高度': 'height', 'height': 'height',
            '半径': 'radius', 'r': 'radius',
            '厚度': 'thickness',
            # 坐标
            'x': 'x', 'y': 'y', 'cx': 'cx', 'cy': 'cy',
            'z_end': 'z_end', 'z_start': 'z_start',
            # 样式
            '颜色': 'color', 'color': 'color',
            '线宽': 'line_width', '线型': 'line_type',
            # 组件参数（直接透传）
            'a': 'a', 'b': 'b', 'h': 'h',
        }
        for cn, en in prop_map.items():
            if cn in text:
                return en
        return text  # 直接返回原文本作为属性名

    @classmethod
    def _extract_params(cls, text: str) -> dict:
        """提取参数: 坐标、半径、长宽高等"""
        params = {}

        # 坐标提取: 在(100,200,300) / 在(100,200) / 100,200 / @100,200
        coord_patterns = [
            r'在\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'坐标\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'在\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'在\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)',
            r'坐标\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
        ]
        for pat in coord_patterns:
            m = re.search(pat, text)
            if m:
                params['x'] = float(m.group(1))
                params['y'] = float(m.group(2))
                if m.lastindex >= 3:
                    params['z'] = float(m.group(3))
                break

        # 半径提取: 半径50 / r50 / 50mm半径
        r_patterns = [
            r'半径\s*(\d+\.?\d*)',
            r'[rR]\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*的?半径',
        ]
        for pat in r_patterns:
            m = re.search(pat, text)
            if m:
                params['radius'] = float(m.group(1))
                break

        # 长度提取: 长200 / 长度200 / 200mm长
        len_patterns = [
            r'长\s*(\d+\.?\d*)',
            r'长度\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*长',
        ]
        for pat in len_patterns:
            m = re.search(pat, text)
            if m:
                params['length'] = float(m.group(1))
                break

        # 宽度提取: 宽100 / 宽度100
        wid_patterns = [
            r'宽\s*(\d+\.?\d*)',
            r'宽度\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*宽',
        ]
        for pat in wid_patterns:
            m = re.search(pat, text)
            if m:
                params['width'] = float(m.group(1))
                break

        # 高度提取: 高50 / 高度50
        h_patterns = [
            r'高\s*(\d+\.?\d*)',
            r'高度\s*(\d+\.?\d*)',
        ]
        for pat in h_patterns:
            m = re.search(pat, text)
            if m:
                params['height'] = float(m.group(1))
                break

        # 角度提取: 角度45 / 45度
        ang_patterns = [
            r'角度\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*度',
        ]
        for pat in ang_patterns:
            m = re.search(pat, text)
            if m:
                params['angle'] = float(m.group(1))
                break

        # 距离提取(偏移/间距等): 距离20 / 间距20 / 每隔20
        # 注意：要避免把“半径2mm/高5mm”这类参数后面的 mm 误解析为 distance。
        # 先对文本做屏蔽：把“参数名+数值+mm”中的数值 mm 替换为占位符，再解析 distance。
        shielded_text = text
        shield_patterns = [
            r'半径\s*(\d+\.?\d*)\s*mm',
            r'[rR]\s*(\d+\.?\d*)\s*mm',
            r'高(?:度)?\s*(\d+\.?\d*)\s*mm',
            r'长(?:度)?\s*(\d+\.?\d*)\s*mm',
            r'宽(?:度)?\s*(\d+\.?\d*)\s*mm',
        ]
        for pat in shield_patterns:
            shielded_text = re.sub(pat, r'__SHIELD__\1__', shielded_text)

        dist_patterns = [
            r'间距\s*(\d+\.?\d*)',
            r'距离\s*(\d+\.?\d*)',
            r'每隔\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*mm',
        ]
        for pat in dist_patterns:
            m = re.search(pat, shielded_text)
            if m:
                params['distance'] = float(m.group(1))
                break

        # 3D 属性提取（仅在用户明确提到时才提取）
        # Z 起始 / z_bottom / z1
        z_start_patterns = [
            r'z起始\s*(\d+\.?\d*)',
            r'z_start\s*(\d+\.?\d*)',
            r'z1\s*(\d+\.?\d*)',
            r'z\s*起始\s*(\d+\.?\d*)',
        ]
        for pat in z_start_patterns:
            m = re.search(pat, text)
            if m:
                params['z_start'] = float(m.group(1))
                break

        # Z 终止 / z_top / z2
        z_end_patterns = [
            r'z终止\s*(\d+\.?\d*)',
            r'z_end\s*(\d+\.?\d*)',
            r'z2\s*(\d+\.?\d*)',
            r'z\s*终止\s*(\d+\.?\d*)',
        ]
        for pat in z_end_patterns:
            m = re.search(pat, text)
            if m:
                params['z_end'] = float(m.group(1))
                break

        # 厚度
        thickness_patterns = [
            r'厚度\s*(\d+\.?\d*)',
            r'thickness\s*(\d+\.?\d*)',
        ]
        for pat in thickness_patterns:
            m = re.search(pat, text)
            if m:
                params['thickness'] = float(m.group(1))
                break

        # 引桥桥墩专用参数
        pier_param_patterns = {
            '盖梁总长': r'盖梁总长\s*(\d+\.?\d*)',
            '盖梁总高': r'盖梁总高\s*(\d+\.?\d*)',
            '凸起宽': r'凸起宽\s*(\d+\.?\d*)',
            '凸起高': r'凸起高\s*(\d+\.?\d*)',
            '盖梁主体底宽': r'盖梁主体底宽\s*(\d+\.?\d*)',
            '斜边水平投影': r'斜边水平投影\s*(\d+\.?\d*)',
            '斜边垂直投影': r'斜边垂直投影\s*(\d+\.?\d*)',
            '盖梁宽': r'盖梁宽\s*(\d+\.?\d*)',
            '墩柱直径': r'墩柱直径\s*(\d+\.?\d*)',
            '墩柱间距': r'墩柱间距\s*(\d+\.?\d*)',
            '墩高': r'墩高\s*(\d+\.?\d*)',
            '系梁长': r'系梁长\s*(\d+\.?\d*)',
            '系梁宽': r'系梁宽\s*(\d+\.?\d*)',
            '系梁高': r'系梁高\s*(\d+\.?\d*)',
            '系梁数量': r'系梁数量\s*(\d+)',
            '系梁起始距顶': r'系梁起始距顶\s*(\d+\.?\d*)',
            '系梁间距': r'系梁间距\s*(\d+\.?\d*)',
        }
        for pname, pat in pier_param_patterns.items():
            m = re.search(pat, text)
            if m:
                params[pname] = float(m.group(1)) if pname != '系梁数量' else int(m.group(1))

        return params

    @classmethod
    def _parse_axis_create(cls, text: str):
        """解析"沿X/Y/Z轴..."批量布置指令"""
        if '沿' not in text:
            return None

        axis = None
        for cn, ax in cls.AXIS_MAP.items():
            if cn in text:
                axis = ax
                break
        if not axis:
            return None

        elem_type = None
        for cn, cmd in cls.ELEMENT_MAP.items():
            if cn.lower() in text:
                elem_type = cmd
                break
        if elem_type not in cls.SOLID_TYPES:
            return None

        params = cls._extract_params(text)
        start = cls._extract_3d_start(text)
        if start is None:
            start = [0.0, 0.0, 0.0]

        length = params.get('length')
        count = None
        m = re.search(r'(\d+)\s*个', text)
        if m:
            count = int(m.group(1))

        spacing = None
        # 支持“间距10/每隔10/每10”等多种说法
        sm = re.search(r'(?:间距|每隔|每)\s*(\d+\.?\d*)', text)
        if sm:
            spacing = float(sm.group(1))
        elif 'distance' in params:
            spacing = params['distance']

        # 根据已知两个量推导第三个
        if length is not None and spacing is not None:
            if count is None:
                count = int(round(length / spacing)) + 1
        elif length is not None and count is not None:
            spacing = length / (count - 1) if count > 1 else 0.0
        elif spacing is not None and count is not None:
            length = (count - 1) * spacing
        else:
            # 缺省值
            if length is None:
                length = 100.0
            if spacing is None:
                spacing = 20.0
            if count is None:
                count = int(round(length / spacing)) + 1
            else:
                # 只给了数量，按默认间距计算总长
                length = (count - 1) * spacing

        return {
            'action': 'create',
            'element': elem_type,
            'axis': axis,
            'start': [float(start[0]), float(start[1]), float(start[2])],
            'length': float(length),
            'spacing': float(spacing),
            'count': int(count),
            'params': params,
        }

    @classmethod
    def _extract_3d_start(cls, text: str):
        """提取 3D 起点，支持 (x,y,z) 或 (x,y)"""
        patterns = [
            r'从\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'起点\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'从\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
            r'起点\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)',
        ]
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                vals = [float(m.group(i)) for i in range(1, m.lastindex + 1)]
                if len(vals) == 2:
                    return [vals[0], vals[1], 0.0]
                return vals
        return None


# ========== DeepSeek API 线程 ==========

class AIChatThread(QThread):
    """AI对话后台线程 —— P2 Enhancement: 支持流式响应和扣子API"""
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    stream_chunk = pyqtSignal(str)  # 流式分片信号

    def __init__(self, api_key, messages, stream=True, api_config=None):
        super().__init__()
        self.api_key = api_key
        self.messages = messages
        self.stream = stream
        self.api_config = api_config or {}  # {'type': 'deepseek'|'coze', ...}

    def run(self):
        api_type = self.api_config.get('type', 'deepseek')
        try:
            if api_type == 'coze':
                self._run_coze()
            else:
                self._run_deepseek()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _run_deepseek(self):
        import urllib.request
        import json

        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        data = {
            "model": "deepseek-chat",
            "messages": self.messages,
            "temperature": 0.3,
            "max_tokens": 1500,
        }
        # 非流式模式才使用json_object（流式不支持强制格式）
        if not self.stream:
            data["response_format"] = {"type": "json_object"}
        else:
            data["stream"] = True

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        if not self.stream:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                content = result['choices'][0]['message']['content']
                self.response_ready.emit(content)
            return

        # 流式模式
        full_content = ""
        with urllib.request.urlopen(req, timeout=60) as resp:
            for line in resp:
                line = line.decode('utf-8').strip()
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk['choices'][0]['delta']
                        if 'content' in delta and delta['content']:
                            token = delta['content']
                            full_content += token
                            self.stream_chunk.emit(token)
                    except Exception:
                        pass
        self.response_ready.emit(full_content)

    def _run_coze(self):
        """扣子Bot API调用"""
        import urllib.request
        import json

        bot_id = self.api_config.get('coze_bot_id', '')
        token = self.api_config.get('coze_token', '')
        if not bot_id or not token:
            raise ValueError("扣子配置不完整，请检查Bot ID和Token")

        url = f"https://api.coze.cn/open_api/v2/chat"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        data = {
            "bot_id": bot_id,
            "user": "cadboard_user",
            "query": self.messages[-1]["content"] if self.messages else "",
            "stream": self.stream,
        }
        # 系统提示词作为conversation_id的额外信息无法直接传递，通过query前缀注入
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        if not self.stream:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                msgs = result.get('messages', [])
                for m in msgs:
                    if m.get('type') == 'answer':
                        self.response_ready.emit(m.get('content', ''))
                        return
                self.response_ready.emit('')
            return

        # 流式
        full_content = ""
        with urllib.request.urlopen(req, timeout=60) as resp:
            for line in resp:
                line = line.decode('utf-8').strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    if chunk.get('event') == 'message':
                        msg = chunk.get('message', {})
                        if msg.get('type') == 'answer':
                            token = msg.get('content', '')
                            full_content += token
                            self.stream_chunk.emit(token)
                except Exception:
                    pass
        self.response_ready.emit(full_content)


# ========== API配置对话框 ==========

class APIConfigDialog(QDialog):
    """AI API配置对话框 —— P2 Enhancement: 支持DeepSeek和扣子Coze"""

    CONFIG_FILE = None  # 在初始化时设置路径

    def __init__(self, parent=None, plugin_dir=None):
        super().__init__(parent)
        self.setWindowTitle("AI API配置")
        self.setMinimumSize(420, 350)
        if plugin_dir:
            self.CONFIG_FILE = os.path.join(plugin_dir, "ai_config.json")
        else:
            self.CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "ai_config.json")
            self.CONFIG_FILE = os.path.normpath(self.CONFIG_FILE)

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # API类型选择
        self.api_type_combo = QComboBox()
        self.api_type_combo.addItems(["DeepSeek", "扣子(Coze)"])
        self.api_type_combo.currentTextChanged.connect(self._on_api_type_changed)
        form.addRow("API类型:", self.api_type_combo)

        # DeepSeek配置
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("输入DeepSeek API Key (sk-...)")
        form.addRow("API Key:", self.api_key_input)

        self.show_key_cb = QCheckBox("显示密钥")
        self.show_key_cb.stateChanged.connect(self._toggle_show_key)
        form.addRow("", self.show_key_cb)

        # 扣子配置（默认隐藏）
        self.coze_widget = QWidget()
        coze_layout = QFormLayout(self.coze_widget)
        self.coze_bot_input = QLineEdit()
        self.coze_bot_input.setPlaceholderText("扣子 Bot ID")
        coze_layout.addRow("Bot ID:", self.coze_bot_input)
        self.coze_token_input = QLineEdit()
        self.coze_token_input.setEchoMode(QLineEdit.Password)
        self.coze_token_input.setPlaceholderText("扣子 Personal Access Token")
        coze_layout.addRow("Token:", self.coze_token_input)
        form.addRow(self.coze_widget)
        self.coze_widget.setVisible(False)

        # 百度语音配置
        voice_group = QGroupBox("语音输入 (百度语音识别)")
        voice_layout = QFormLayout(voice_group)
        self.baidu_api_input = QLineEdit()
        self.baidu_api_input.setPlaceholderText("百度语音 API Key")
        voice_layout.addRow("API Key:", self.baidu_api_input)
        self.baidu_secret_input = QLineEdit()
        self.baidu_secret_input.setEchoMode(QLineEdit.Password)
        self.baidu_secret_input.setPlaceholderText("百度语音 Secret Key")
        voice_layout.addRow("Secret Key:", self.baidu_secret_input)
        form.addRow(voice_group)

        info = QLabel(
            "<b>DeepSeek:</b> 访问 <a href='https://platform.deepseek.com'>platform.deepseek.com</a> 获取Key<br>"
            "<b>扣子:</b> 访问 <a href='https://www.coze.cn'>coze.cn</a> 搭建Bot并发布API<br>"
            "<b>百度语音:</b> 访问 <a href='https://ai.baidu.com/tech/speech'>ai.baidu.com</a> 获取Key<br>"
            "配置保存在本地，不会上传到任何服务器。"
        )
        info.setOpenExternalLinks(True)
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

    def _on_api_type_changed(self, text):
        is_coze = text == "扣子(Coze)"
        self.coze_widget.setVisible(is_coze)

    def _toggle_show_key(self, state):
        mode = QLineEdit.Normal if state == Qt.Checked else QLineEdit.Password
        self.api_key_input.setEchoMode(mode)
        self.coze_token_input.setEchoMode(mode)

    def _load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    self.api_key_input.setText(cfg.get('api_key', ''))
                    self.api_type_combo.setCurrentText(cfg.get('api_type', 'DeepSeek'))
                    self.coze_bot_input.setText(cfg.get('coze_bot_id', ''))
                    self.coze_token_input.setText(cfg.get('coze_token', ''))
                    self.baidu_api_input.setText(cfg.get('baidu_api_key', ''))
                    self.baidu_secret_input.setText(cfg.get('baidu_secret_key', ''))
            except Exception:
                pass

    def _save_config(self):
        cfg = {
            'api_key': self.api_key_input.text().strip(),
            'api_type': self.api_type_combo.currentText(),
            'coze_bot_id': self.coze_bot_input.text().strip(),
            'coze_token': self.coze_token_input.text().strip(),
            'baidu_api_key': self.baidu_api_input.text().strip(),
            'baidu_secret_key': self.baidu_secret_input.text().strip(),
        }
        if not cfg['api_key'] and not cfg['coze_token']:
            QMessageBox.warning(self, "提示", "未配置任何API Key/Token，AI对话功能将不可用。")
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False)
            QMessageBox.information(self, "保存成功", "API配置已保存。")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"无法保存配置: {e}")

    @classmethod
    def load_config(cls, plugin_dir=None):
        """加载完整配置"""
        if plugin_dir:
            cfg_path = os.path.join(plugin_dir, "ai_config.json")
        else:
            cfg_path = os.path.join(os.path.dirname(__file__), "..", "ai_config.json")
            cfg_path = os.path.normpath(cfg_path)
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @classmethod
    def load_api_key(cls, plugin_dir=None):
        """加载已保存的API Key（兼容旧版）"""
        cfg = cls.load_config(plugin_dir)
        return cfg.get('api_key', '')


# ========== AI助手面板主类 ==========

class AIPanel(QWidget):
    """AI助手面板 - 可折叠的右侧对话面板 —— P2 Enhancement: 快速模式+流式响应"""

    def __init__(self, board, parent=None):
        super().__init__(parent)
        self.board = board
        self.plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._api_config = APIConfigDialog.load_config(self.plugin_dir)
        self.api_key = self._api_config.get('api_key', '')
        self.chat_history = []  # AI对话历史
        self._chat_thread = None
        self._executor = AICommandExecutor(board)
        self._pending_commands = []  # 待确认执行的操作指令
        self._stream_buffer = ""  # 流式响应缓冲区

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        # 标题栏
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("<b>AI助手</b>"))

        # v1.5 P3: 自动模式 — 根据输入复杂度自动选择本地/API，无需手动切换
        self.mode_indicator = QLabel("🤖 自动")
        self.mode_indicator.setToolTip("AI会根据指令复杂度自动选择：简单指令→本地执行，复杂指令→调用API")
        title_layout.addWidget(self.mode_indicator)

        config_btn = QPushButton("配置")
        config_btn.setMaximumWidth(50)
        config_btn.clicked.connect(self._show_config)
        title_layout.addWidget(config_btn)

        clear_btn = QPushButton("清空")
        clear_btn.setMaximumWidth(50)
        clear_btn.clicked.connect(self._clear_chat)
        title_layout.addWidget(clear_btn)

        layout.addLayout(title_layout)

        # 聊天显示区
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        font = QFont("Microsoft YaHei", 10)
        self.chat_display.setFont(font)
        self.chat_display.setStyleSheet("QTextEdit { background-color: #f8f9fa; }")
        layout.addWidget(self.chat_display, 1)

        # 提示标签
        self.status_label = QLabel("输入自然语言命令或提问...")
        self.status_label.setStyleSheet("QLabel { color: #666; font-size: 9px; }")
        layout.addWidget(self.status_label)

        # 确认操作区（默认隐藏）
        self.confirm_layout = QHBoxLayout()
        self.confirm_label = QLabel("")
        self.confirm_label.setStyleSheet("QLabel { color: #d32f2f; font-weight: bold; }")
        self.confirm_layout.addWidget(self.confirm_label, 1)

        self.confirm_btn = QPushButton("✅ 确认执行")
        self.confirm_btn.setStyleSheet("QPushButton { background-color: #2E7D32; color: white; }")
        self.confirm_btn.clicked.connect(self._on_confirm_execute)
        self.confirm_btn.setVisible(False)
        self.confirm_layout.addWidget(self.confirm_btn)

        self.cancel_btn = QPushButton("❌ 取消")
        self.cancel_btn.clicked.connect(self._on_cancel_execute)
        self.cancel_btn.setVisible(False)
        self.confirm_layout.addWidget(self.cancel_btn)

        layout.addLayout(self.confirm_layout)

        # 输入区
        input_layout = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("输入命令如'画一个半径50的圆'或提问...")
        self.input_box.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_box, 1)

        # 语音输入按钮
        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setMaximumWidth(36)
        self.voice_btn.setToolTip("点击开始语音输入")
        self.voice_btn.clicked.connect(self._on_voice_toggle)
        input_layout.addWidget(self.voice_btn)

        send_btn = QPushButton("发送")
        send_btn.setMaximumWidth(50)
        send_btn.setStyleSheet("QPushButton { background-color: #1565C0; color: white; }")
        send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(send_btn)

        layout.addLayout(input_layout)

        # 语音输入组件
        self._voice_recorder = VoiceRecorder(self)
        self._voice_recorder.finished.connect(self._on_voice_finished)
        self._voice_recorder.error.connect(self._on_voice_error)
        self._voice_recognizer = None  # 延迟初始化，需要配置

        # 快捷提示
        tips = QLabel(
            "<small>快捷: '画圆 r50 @100,200' | '删除' | '怎么用拉伸'</small>"
        )
        tips.setStyleSheet("QLabel { color: #888; }")
        layout.addWidget(tips)

        # 欢迎消息
        self._append_message("system",
            "你好！我是CAD画板AI助手。\n"
            "你可以:\n"
            "1. 用自然语言画图，如'在100,200画一个半径50的圆'\n"
            "2. 询问命令用法，如'怎么用拉伸'\n"
            "3. 直接执行命令，如'删除选中的元素'\n"
            "4. 点击'配置'按钮设置DeepSeek API Key\n"
        )

    def _append_message(self, role, text):
        """添加消息到聊天显示区"""
        timestamp = datetime.now().strftime("%H:%M")
        if role == 'user':
            self.chat_display.append(f'<p style="color:#1565C0;"><b>[{timestamp}] 你:</b> {text}</p>')
        elif role == 'ai':
            # 将换行符转为HTML换行
            html_text = text.replace('\n', '<br>')
            self.chat_display.append(f'<p style="color:#2E7D32;"><b>[{timestamp}] AI:</b> {html_text}</p>')
        elif role == 'system':
            self.chat_display.append(f'<p style="color:#666;"><b>[{timestamp}] 系统:</b> {text}</p>')
        elif role == 'error':
            self.chat_display.append(f'<p style="color:#d32f2f;"><b>[{timestamp}] 错误:</b> {text}</p>')
        # 滚动到底部
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _send_message(self):
        """发送消息处理 —— v1.5 P3: 自动路由，根据内容复杂度选择本地/API"""
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        self._append_message('user', text)

        # v1.5 P3: 自动路由判断
        use_local = self._should_use_local(text)

        if use_local:
            # 本地执行路径
            self.mode_indicator.setText("⚡ 本地")
            parsed = LocalCommandParser.parse(text)
            if parsed:
                self._execute_local_command(parsed, text)
            else:
                self._append_message('system',
                    "本地无法识别该指令，尝试调用AI..."
                )
                # 本地失败，fallback到API
                self._try_api(text)
            return

        # API路径
        self.mode_indicator.setText("☁️ AI")
        self._try_api(text)

    def _try_api(self, text):
        """尝试调用API，如果未配置则fallback到本地"""
        if not self.api_key and not self._api_config.get('coze_token'):
            parsed = LocalCommandParser.parse(text)
            if parsed:
                self._execute_local_command(parsed, text)
            else:
                self._append_message('system',
                    "未配置API Key/Token，无法调用AI。请点击'配置'按钮设置DeepSeek或Coze。"
                )
            return
        self._call_ai(text, fast_mode=True)

    def _should_use_local(self, text: str) -> bool:
        """
        v1.5 P3: 自动判断是否应该使用本地解析。
        简单指令 → True（本地执行，快）
        复杂/模糊指令 → False（走API）
        """
        # 0. 沿轴批量布置指令强制走本地解析，避免被AI覆盖
        if '沿' in text:
            parsed = LocalCommandParser.parse(text)
            if parsed and parsed.get('axis'):
                return True

        # 1. 先尝试解析，解析失败直接走API
        parsed = LocalCommandParser.parse(text)
        if not parsed:
            return False

        # 2. 包含复杂/模糊关键词 → 走API
        complex_keywords = ['帮我', '建议', '分析', '优化', '设计', '如何', '为什么',
                            '怎么样', '是否', '请问', '解释', '说明', '推荐', '思路',
                            '方案', '比较', '区别', '优缺点', '怎么', '怎样']
        if any(kw in text for kw in complex_keywords):
            return False

        # 3. 开放式问题（以问号结尾且不是明确命令）→ 走API
        if (text.endswith('?') or text.endswith('？')) and parsed.get('action') != 'draw':
            return False

        # 4. 包含多个操作（用连接词串联）→ 走API
        multi_action = ['然后', '接着', '再', '先', '之后', '最后', '同时']
        if sum(1 for kw in multi_action if kw in text) >= 1:
            return False

        # 5. 长度超过一定阈值 → 走API（太长的指令通常较复杂）
        if len(text) > 80:
            return False

        # 6. 是明确的绘制/删除/修改操作 → 本地执行
        action = parsed.get('action', '')
        if action in ('create', 'delete', 'modify', 'agent'):
            return True

        return False

    def _execute_local_command(self, parsed, original_text):
        """Phase 4: 使用AICommandExecutor执行本地解析的指令"""
        self._append_message('system', f"正在执行: {original_text}")
        success, msg = self._executor.execute(parsed)
        if success:
            self._append_message('system', f"✅ {msg}")
        else:
            self._append_message('error', f"❌ {msg}")

    def _execute_draw_command(self, command, params):
        """根据解析的参数执行绘制命令"""
        board = self.board
        x = params.get('x', 100)
        y = params.get('y', 100)

        if command == 'circle':
            r = params.get('radius', 50)
            from geometry.elements import CircleElement
            elem = CircleElement(x, y, r)
            board.apply_current_layer_style(elem)
            board.add_element(elem)
            board.viewport.update()
            return True

        elif command == 'rectangle':
            w = params.get('length', params.get('width', 100))
            h = params.get('width', params.get('length', 80))
            # 如果同时有length和width，length=长，width=宽
            if 'length' in params and 'width' in params:
                w = params['length']
                h = params['width']
            from geometry.elements import RectangleElement
            elem = RectangleElement(x, y, w, h)
            board.apply_current_layer_style(elem)
            board.add_element(elem)
            board.viewport.update()
            return True

        elif command == 'line':
            x2 = x + params.get('length', 100)
            y2 = y
            if 'angle' in params:
                a = math.radians(params['angle'])
                l = params.get('length', 100)
                x2 = x + l * math.cos(a)
                y2 = y + l * math.sin(a)
            from geometry.elements import LineElement
            elem = LineElement(x, y, x2, y2)
            board.apply_current_layer_style(elem)
            board.add_element(elem)
            board.viewport.update()
            return True

        elif command == 'arc':
            r = params.get('radius', 50)
            from geometry.elements import ArcElement
            elem = ArcElement(x, y, r, 0, 90)
            board.apply_current_layer_style(elem)
            board.add_element(elem)
            board.viewport.update()
            return True

        elif command == 'point':
            from geometry.elements import PointElement
            elem = PointElement(x, y)
            board.apply_current_layer_style(elem)
            board.add_element(elem)
            board.viewport.update()
            return True

        return False

    def _call_ai(self, text, fast_mode=False):
        """调用DeepSeek AI - P2 Enhancement: 支持快速模式(上下文压缩)和流式响应"""
        self.status_label.setText("AI思考中...")
        self._stream_buffer = ""
        # 预显示流式占位
        self._append_message('ai', '<i>AI正在思考...</i>')
        self._current_ai_msg_index = self.chat_display.toPlainText().count('[AI]') - 1

        # 组装画板上下文（快速模式下压缩）
        context = self._build_board_context(fast=fast_mode)
        bimbase_state = self._build_bimbase_context(fast=fast_mode)

        system_prompt = (
            "你是CAD画板AI助手，将用户指令转为JSON操作。只输出JSON，不要解释。\n\n"
            "输出格式:{\"commands\":[...],\"summary\":\"描述\"}\n"
            "commands每项含action+参数:\n"
            "create:element类型(circle/rectangle/line/arc/point/polyline/polygon/ellipse/圆柱/正方体/长方体/直角三棱柱)+params坐标尺寸\n"
            "modify:target必须是字典{\"index\":\"selected\"}或{\"index\":N}或{\"element_type\":\"circle\"}+changes属性键值(支持+50/*2)\n"
            "transform:transform_type(translate/rotate/scale/mirror)+target字典+params\n"
            "delete:target字典\n"
            "set_property:target字典+properties(z_start/z_end/height/is_3d/thickness)\n"
            "agent:tool(modify_component/sync_to_bimbase/query_state/regenerate_faces)+params\n"
            "face_edit:sub_action(generate/apply)\n"
            "sync:无参\n"
            "信息不足返回{\"action\":\"ask\",\"question\":\"...\"}\n"
            "闲聊返回{\"action\":\"chat\",\"message\":\"...\"}\n\n"
            "歧义规则:未明确来源且画板+BIMBase都有同类型→追问;仅一方有→直接执行该方。\n\n"
            "画板状态:\n" + context + "\n\n"
            "BIMBase状态:\n" + bimbase_state + "\n"
        )

        messages = [
            {"role": "system", "content": system_prompt}
        ]
        # 快速模式下只保留最近3轮对话历史
        history_limit = 3 if fast_mode else 10
        for msg in self.chat_history[-history_limit:]:
            messages.append(msg)
        messages.append({"role": "user", "content": text})

        self._last_user_text = text
        api_cfg = {'type': 'deepseek'}
        if self._api_config.get('api_type') == '扣子(Coze)':
            api_cfg = {
                'type': 'coze',
                'coze_bot_id': self._api_config.get('coze_bot_id', ''),
                'coze_token': self._api_config.get('coze_token', ''),
            }
        self._chat_thread = AIChatThread(self.api_key, messages, stream=True, api_config=api_cfg)
        self._chat_thread.stream_chunk.connect(self._on_stream_chunk)
        self._chat_thread.response_ready.connect(self._on_ai_response)
        self._chat_thread.error_occurred.connect(self._on_ai_error)
        self._chat_thread.start()

    def _build_board_context(self, fast=False):
        """构建画板上下文描述 —— P2 Enhancement: 快速模式下压缩上下文"""
        board = self.board
        lines = [f"画板共有 {len(board.elements)} 个元素"]
        comp_types = {}
        selected_elems = []

        # 收集参数化组件统计
        for elem in board.elements:
            if elem.component_type:
                comp_types[elem.component_type] = comp_types.get(elem.component_type, 0) + 1
            if getattr(elem, 'selected', False):
                selected_elems.append(elem)

        if comp_types:
            lines.append(f"参数化组件统计: {comp_types}")

        # 快速模式：只发送选中元素 + 前30个元素摘要
        if fast:
            lines.append("【快速模式：仅显示部分元素】")
            if selected_elems:
                lines.append(f"已选中 {len(selected_elems)} 个元素:")
                for elem in selected_elems:
                    lines.append(self._describe_element(elem, detailed=True))
            else:
                lines.append("无选中元素")
            # 只发送前20个非面元素的摘要
            count = 0
            for elem in board.elements:
                if getattr(elem, 'face_info', {}):
                    continue
                lines.append(self._describe_element(elem, detailed=False))
                count += 1
                if count >= 20:
                    lines.append(f"... 等共 {len(board.elements)} 个元素")
                    break
            return "\n".join(lines)

        # 普通模式：发送所有元素详情
        for i, elem in enumerate(board.elements):
            lines.append(self._describe_element(elem, detailed=True, index=i))
        if comp_types:
            lines.append(f"参数化组件统计: {comp_types}")
        return "\n".join(lines)

    def _describe_element(self, elem, detailed=True, index=None):
        """描述单个元素（用于上下文构建）"""
        et = elem.__class__.__name__
        prefix = f"[{index}] " if index is not None else ""
        desc = f"{prefix}{et}"
        if not detailed:
            return desc
        if et == 'RectangleElement':
            desc += f" ({elem.x:.1f},{elem.y:.1f}) {elem.width:.1f}x{elem.height:.1f}"
        elif et == 'CircleElement':
            desc += f" ({elem.cx:.1f},{elem.cy:.1f}) r={elem.radius:.1f}"
        elif et == 'LineElement':
            desc += f" ({elem.x1:.1f},{elem.y1:.1f})->({elem.x2:.1f},{elem.y2:.1f})"
        elif et == 'ArcElement':
            desc += f" ({elem.cx:.1f},{elem.cy:.1f}) r={elem.radius:.1f} {elem.start_angle:.0f}~{elem.end_angle:.0f}"
        elif et == 'PointElement':
            desc += f" ({elem.x:.1f},{elem.y:.1f})"
        elif et in ('PolygonElement', 'PolylineElement'):
            desc += f" {len(elem.points)}个点"
        elif et == 'EllipseElement':
            desc += f" ({elem.cx:.1f},{elem.cy:.1f}) rx={elem.rx:.1f} ry={elem.ry:.1f}"
        if elem.is_3d:
            desc += f" [3D H={elem.height:.1f}]"
        if elem.component_type:
            desc += f" [组件:{elem.component_type}]"
        if elem.face_info:
            from geometry.faces import FACE_NAME_LABELS
            fn = elem.face_info.get('face_name', '')
            desc += f" [面:{FACE_NAME_LABELS.get(fn, fn)}]"
        if getattr(elem, 'selected', False):
            desc += " (已选中)"
        return desc

    def _build_bimbase_context(self, fast=False):
        """构建BIMBase上下文描述（轻量扫描）—— P2 Enhancement: 快速模式下跳过扫描"""
        lines = []
        # P2: 快速模式下大幅减少BIMBase扫描（只返回缓存或极简信息）
        if fast:
            try:
                from bimbase_sync import get_all_instancekey
                if get_all_instancekey is None:
                    lines.append("BIMBase 不可用")
                else:
                    keys = get_all_instancekey() or []
                    lines.append(f"BIMBase 有 {len(keys)} 个实例（快速模式未扫描详情）")
            except Exception:
                lines.append("BIMBase 不可用")
            return "\n".join(lines)

        try:
            from bimbase_sync import get_entityid_from_boxselection
            if get_entityid_from_boxselection is not None:
                sel_ids = get_entityid_from_boxselection() or []
                if sel_ids:
                    lines.append(f"BIMBase 当前有 {len(sel_ids)} 个实体被选中")
        except Exception:
            pass

        try:
            from bimbase_sync import BIMBaseSync, get_all_instancekey
            if get_all_instancekey is None:
                lines.append("BIMBase 不可用（pyp3d未加载）")
                return "\n".join(lines)
            sync = BIMBaseSync(self.board)
            keys = get_all_instancekey() or []
            if not keys:
                lines.append("BIMBase 中无组件实例")
                return "\n".join(lines)
            types = {}
            count = 0
            for ik in keys[:200]:  # 最多扫描200个
                try:
                    p = sync._get_params_from_datakey(ik)
                    if p:
                        ct = p.get('_type', '未知')
                        types[ct] = types.get(ct, 0) + 1
                        count += 1
                except Exception:
                    pass
            if types:
                lines.append(f"BIMBase 中扫描到 {count} 个CADBoard参数化组件:")
                for ct, num in sorted(types.items()):
                    lines.append(f"  - {ct}: {num} 个")
            else:
                lines.append("BIMBase 中未扫描到可读取参数的CADBoard组件（可能是代理实体）")
            return "\n".join(lines)
        except Exception as e:
            lines.append(f"BIMBase 扫描失败: {e}")
            return "\n".join(lines)

    def _on_stream_chunk(self, token):
        """P2 Enhancement: 流式响应分片处理 —— 实时更新AI消息"""
        self._stream_buffer += token
        # 更新最后一条AI消息的显示（替换<it>占位符）
        try:
            # 简单方式：将HTML中的最后一条AI消息替换为累积内容
            html_text = self._stream_buffer.replace('\n', '<br>')
            # 使用JavaScript-like方式更新最后一段不太可行，直接追加显示
            # 改为：在聊天区显示一个动态更新的临时消息
            self.status_label.setText(f"AI接收中... {len(self._stream_buffer)} 字")
        except Exception:
            pass

    def _on_ai_response(self, text):
        """Agent模式响应处理：支持追问、聊天、待确认指令 —— P2 Enhancement: 流式结束后处理"""
        import json

        self.status_label.setText("输入自然语言命令或提问...")
        self._stream_buffer = ""

        # 尝试解析新的结构化JSON
        parsed = None
        try:
            clean = text.strip()
            if clean.startswith('```json'):
                clean = clean[7:]
            if clean.startswith('```'):
                clean = clean[3:]
            if clean.endswith('```'):
                clean = clean[:-3]
            clean = clean.strip()
            parsed = json.loads(clean)
        except Exception:
            pass

        # 新模式处理
        if isinstance(parsed, dict):
            action = parsed.get('action', '')

            # 1. 追问模式
            if action == 'ask':
                question = parsed.get('question', '请补充信息')
                self._append_message('ai', f"🤔 {question}")
                user_text = getattr(self, '_last_user_text', '')
                self.chat_history.append({"role": "user", "content": user_text})
                self.chat_history.append({"role": "assistant", "content": text})
                self.status_label.setText("AI等待补充信息...")
                return

            # 2. 聊天模式
            if action == 'chat':
                msg = parsed.get('message', '')
                if msg:
                    self._append_message('ai', msg)
                user_text = getattr(self, '_last_user_text', '')
                self.chat_history.append({"role": "user", "content": user_text})
                self.chat_history.append({"role": "assistant", "content": text})
                self.status_label.setText("输入自然语言命令或提问...")
                return

            # 3. 命令模式 {"commands": [...], "summary": "..."}
            commands = parsed.get('commands', [])
            if commands:
                summary = parsed.get('summary', f"执行 {len(commands)} 个操作")
                self._pending_commands = commands
                self.confirm_label.setText(f"AI建议: {summary}")
                self.confirm_btn.setVisible(True)
                self.cancel_btn.setVisible(True)
                self._append_message('system', f"🤖 AI建议执行: {summary}")
                user_text = getattr(self, '_last_user_text', '')
                self.chat_history.append({"role": "user", "content": user_text})
                self.chat_history.append({"role": "assistant", "content": text})
                self.status_label.setText("请确认或取消AI建议的操作")
                return

        # 回退到旧模式解析（兼容旧版AI回复）
        commands, plain_text = AIResponseParser.parse(text)
        if plain_text:
            self._append_message('ai', plain_text)
        if commands:
            self._pending_commands = commands
            self.confirm_label.setText(f"AI建议执行 {len(commands)} 个操作")
            self.confirm_btn.setVisible(True)
            self.cancel_btn.setVisible(True)
            self._append_message('system', f"🤖 检测到 {len(commands)} 个操作指令，等待确认...")
        else:
            self.status_label.setText("输入自然语言命令或提问...")

        user_text = getattr(self, '_last_user_text', '')
        self.chat_history.append({"role": "user", "content": user_text})
        self.chat_history.append({"role": "assistant", "content": text})

    def _on_confirm_execute(self):
        """用户确认执行待执行的AI指令"""
        if not self._pending_commands:
            return
        commands = self._pending_commands
        self._pending_commands = []
        self.confirm_btn.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.confirm_label.setText("")
        self._append_message('system', f"正在执行 {len(commands)} 个操作...")
        # 调试：打印原始命令JSON
        for i, cmd in enumerate(commands):
            self._append_message('system', f"[命令{i+1}] {cmd}")
        results = self._executor.execute_batch(commands)
        for success, msg in results:
            role = 'system' if success else 'error'
            self._append_message(role, msg)
        self.status_label.setText("操作已完成")

    def _on_cancel_execute(self):
        """用户取消待执行的AI指令"""
        self._pending_commands = []
        self.confirm_btn.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.confirm_label.setText("")
        self._append_message('system', "已取消AI建议的操作")
        self.status_label.setText("输入自然语言命令或提问...")

    def _on_ai_error(self, error):
        self._append_message('error', f"API调用失败: {error}\n请检查API Key是否正确以及网络连接。")
        self.status_label.setText("AI调用失败")

    def _show_config(self):
        """显示API配置对话框 —— P2 Enhancement: 加载完整配置（含扣子）"""
        plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dialog = APIConfigDialog(self, plugin_dir)
        if dialog.exec_():
            self._api_config = APIConfigDialog.load_config(plugin_dir)
            self.api_key = self._api_config.get('api_key', '')
            api_type = self._api_config.get('api_type', 'DeepSeek')
            if self.api_key or self._api_config.get('coze_token'):
                self._append_message('system', f'{api_type} API配置已更新')
            else:
                self._append_message('system', 'API配置已清空')

    def _clear_chat(self):
        """清空聊天记录"""
        self.chat_display.clear()
        self.chat_history.clear()
        self._append_message('system', '聊天记录已清空')

    # ---------- 语音输入 ----------

    def _ensure_voice_recognizer(self):
        """延迟初始化语音识别器，预获取 token 减少识别延迟"""
        if self._voice_recognizer is not None:
            return True
        api_key = self._api_config.get('baidu_api_key', '')
        secret_key = self._api_config.get('baidu_secret_key', '')
        if not api_key or not secret_key:
            return False
        self._voice_recognizer = BaiduSpeechRecognizer(api_key, secret_key, self)
        self._voice_recognizer.result.connect(self._on_voice_text)
        self._voice_recognizer.error.connect(self._on_voice_error)
        # 后台预获取 token，减少第一次识别的延迟
        try:
            self._voice_recognizer._get_token()
        except Exception:
            pass
        return True

    def _on_voice_toggle(self):
        """点击语音按钮：开始/停止录音"""
        if self._voice_recorder.is_recording():
            self._voice_recorder.stop()
            self.voice_btn.setText("🎤")
            self.voice_btn.setStyleSheet("")
            self.status_label.setText("录音停止，处理中...")
        else:
            if not self._ensure_voice_recognizer():
                self._append_message('system',
                    "未配置百度语音 API Key，请点击'配置'按钮设置。"
                    "申请地址: https://ai.baidu.com/tech/speech"
                )
                return
            self._voice_recorder.start()
            self.voice_btn.setText("⏹")
            self.voice_btn.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; }")
            self.status_label.setText("正在录音... 再次点击停止")
            self._append_message('system', "🎤 录音已开始，请说话...")

    def _on_voice_finished(self, wav_data: bytes, sample_rate: int):
        """录音完成，开始识别"""
        self._append_message('system', f"🎤 录音完成，音频大小: {len(wav_data)} bytes，采样率: {sample_rate}Hz，正在识别...")
        if self._voice_recognizer:
            self._voice_recognizer.recognize(wav_data, sample_rate)
        else:
            self._append_message('error', "语音识别器未初始化")

    def _on_voice_text(self, text: str):
        """语音识别成功，填入输入框"""
        self.input_box.setText(text)
        self.status_label.setText(f"语音识别: {text}")
        self._append_message('system', f"🎤 识别结果: {text}")

    def _on_voice_error(self, msg: str):
        """语音识别出错"""
        self.status_label.setText(f"语音错误: {msg}")
        self._append_message('error', f"🎤 语音输入错误: {msg}")
