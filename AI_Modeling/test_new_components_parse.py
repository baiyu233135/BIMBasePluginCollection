# -*- coding: utf-8 -*-
"""
AI_Modeling 门式桥墩（gate_pier）/ 承台及桩基（pile_foundation）链路回归测试
无需启动 BIMBase，仅测试命令解析、组件类型推断、参数过滤等本地逻辑。
"""
import os
import sys
import unittest

# 确保 AI_Modeling 在路径中
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

from ai_modeling.command_parser import ModelingCommandParser
from ai_modeling.component_factory import _filter_component_params, COMPONENT_CLASSES, COMPONENT_DEFAULTS
from ai_modeling.bimbase_modifier import infer_component_type_from_params


class GatePierParseTestCase(unittest.TestCase):
    """解析器对门式桥墩指令的解析"""

    def test_create_gate_pier(self):
        parsed = ModelingCommandParser.parse("在(0,0,0)生成一个门式桥墩")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'gate_pier')

    def test_create_gate_pier_alias(self):
        for alias in ("门式墩", "门架墩"):
            parsed = ModelingCommandParser.parse("生成一个%s" % alias)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed['component_type'], 'gate_pier', alias)

    def test_gate_pier_params(self):
        parsed = ModelingCommandParser.parse("生成墩高6000、柱底宽1500的门式桥墩")
        self.assertEqual(parsed['component_type'], 'gate_pier')
        self.assertEqual(parsed['params'].get('墩高'), 6000.0)
        self.assertEqual(parsed['params'].get('柱底宽'), 1500.0)

    def test_plain_pier_not_hijacked(self):
        """'桥墩' 仍应解析为引桥桥墩 pier，不被 gate_pier 抢占"""
        parsed = ModelingCommandParser.parse("生成一个桥墩")
        self.assertEqual(parsed['component_type'], 'pier')

    def test_gate_pier_param_filter(self):
        filtered = _filter_component_params('gate_pier', {'墩高': 6000.0, '无关参数': 1.0})
        self.assertIn('墩高', filtered)
        self.assertNotIn('无关参数', filtered)


class PileFoundationParseTestCase(unittest.TestCase):
    """解析器对承台及桩基指令的解析"""

    def test_create_pile_foundation(self):
        parsed = ModelingCommandParser.parse("在(0,0,0)生成承台及桩基")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'pile_foundation')

    def test_pile_foundation_alias(self):
        for alias in ("承台", "桩基", "桩基础"):
            parsed = ModelingCommandParser.parse("生成一个%s" % alias)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed['component_type'], 'pile_foundation', alias)

    def test_pile_foundation_params(self):
        parsed = ModelingCommandParser.parse("生成承台长6000、桩列数8的承台及桩基")
        self.assertEqual(parsed['component_type'], 'pile_foundation')
        self.assertEqual(parsed['params'].get('承台长'), 6000.0)
        self.assertEqual(parsed['params'].get('桩列数'), 8.0)

    def test_anchor_not_hijacked(self):
        """含'承台'的锚锭指令仍应归 anchor"""
        parsed = ModelingCommandParser.parse("生成索缆锚锭 承台长度2600")
        self.assertEqual(parsed['component_type'], 'anchor')


class NewComponentFactoryTestCase(unittest.TestCase):
    """组件工厂对两个新类型的注册与默认值"""

    def test_classes_registered(self):
        self.assertIn('gate_pier', COMPONENT_CLASSES)
        self.assertIn('pile_foundation', COMPONENT_CLASSES)

    def test_defaults(self):
        gp = COMPONENT_DEFAULTS['gate_pier']
        self.assertEqual(gp['盖梁总长'], 4700.0)
        self.assertEqual(gp['墩高'], 5000.0)
        self.assertEqual(gp['墩柱间距'], 3500.0)
        pf = COMPONENT_DEFAULTS['pile_foundation']
        self.assertEqual(pf['承台长'], 5500.0)
        self.assertEqual(pf['桩列数'], 9)
        self.assertEqual(pf['桩排数'], 4)

    def test_infer_type_from_params(self):
        self.assertEqual(infer_component_type_from_params({'柱顶宽': 1200.0}), 'gate_pier')
        self.assertEqual(infer_component_type_from_params({'桩列数': 9}), 'pile_foundation')
        self.assertEqual(infer_component_type_from_params({'承台长': 5500.0}), 'pile_foundation')
        # 回归：现有类型不受影响（pier 的判别键为 盖梁总长/墩柱间距/系梁根数）
        self.assertEqual(infer_component_type_from_params({'盖梁总长': 1930.0}), 'pier')


class FallbackCopySelectedTestCase(unittest.TestCase):
    """无类型布置指令 → 复制选中组件（沿选中组件布置 / 沿轴阵列）"""

    def test_relative_above_selected(self):
        parsed = ModelingCommandParser.parse("沿我当前选中的组件的位置上方500米布置这一个组件")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['action'], 'copy')
        self.assertEqual(parsed['target'], {'mode': 'selected'})
        self.assertEqual(parsed['position']['mode'], 'relative')
        self.assertEqual(parsed['position']['axis'], 'z')
        self.assertEqual(parsed['position']['distance'], 500000.0)

    def test_relative_along_selected_default_x(self):
        parsed = ModelingCommandParser.parse("沿当前选中组件5米布置一个门式桥墩")
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'gate_pier')
        self.assertEqual(parsed['position']['mode'], 'relative')
        self.assertEqual(parsed['position']['axis'], 'x')
        self.assertEqual(parsed['position']['distance'], 5000.0)
        self.assertIsNone(parsed['path'])  # 不能误判为沿路径布置

    def test_axis_array_without_type(self):
        parsed = ModelingCommandParser.parse("沿X轴每隔5米布置10个组件")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['action'], 'copy')
        arr = parsed['array']
        self.assertIsNotNone(arr)
        self.assertEqual(arr['mode'], 'linear')
        self.assertEqual(arr['axis'], 'x')
        self.assertEqual(arr['spacing'], 5000.0)
        self.assertEqual(arr['count'], 10)

    def test_axis_array_with_type_unchanged(self):
        parsed = ModelingCommandParser.parse("沿X轴每隔5米布置10个承台及桩基")
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'pile_foundation')
        self.assertEqual(parsed['array']['count'], 10)

    def test_bare_create_component_still_none(self):
        self.assertIsNone(ModelingCommandParser.parse("生成一个组件"))


if __name__ == '__main__':
    unittest.main()
