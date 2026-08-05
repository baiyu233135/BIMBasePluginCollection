# -*- coding: utf-8 -*-
"""
AI_Modeling 引桥桥墩（pier）链路回归测试
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
from ai_modeling.component_factory import _get_valid_kwargs, _filter_component_params, COMPONENT_CLASSES, COMPONENT_DEFAULTS
from ai_modeling.bimbase_modifier import infer_component_type_from_params


class PierParseTestCase(unittest.TestCase):
    """解析器对桥墩指令的解析"""

    def test_create_pier_at_coords(self):
        parsed = ModelingCommandParser.parse("在(0,0,0)生成一个桥墩")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'pier')
        self.assertEqual(parsed['position']['mode'], 'absolute')
        self.assertEqual((parsed['position']['x'], parsed['position']['y'], parsed['position']['z']), (0.0, 0.0, 0.0))

    def test_create_pier_with_params(self):
        parsed = ModelingCommandParser.parse("生成墩高2000、系梁根数3的引桥桥墩")
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'pier')
        self.assertEqual(parsed['params'].get('墩高'), 2000.0)
        self.assertEqual(parsed['params'].get('系梁根数'), 3.0)

    def test_modify_pier_preserve_position(self):
        parsed = ModelingCommandParser.parse("把选中桥墩的墩高改为2000，保持位置不变")
        self.assertEqual(parsed['action'], 'modify')
        self.assertEqual(parsed['target']['mode'], 'selected')
        self.assertEqual(parsed['params'].get('墩高'), 2000.0)
        self.assertTrue(parsed['preserve_position'])

    def test_copy_pier_to_coords(self):
        parsed = ModelingCommandParser.parse("复制选中的桥墩到(5000,0,0)")
        self.assertEqual(parsed['action'], 'copy')
        self.assertEqual(parsed['position']['mode'], 'absolute')
        self.assertEqual(parsed['position']['x'], 5000.0)

    def test_pier_linear_array(self):
        parsed = ModelingCommandParser.parse("沿x轴每隔30000布置一个桥墩，共5个")
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'pier')
        arr = parsed['array']
        self.assertIsNotNone(arr)
        self.assertEqual(arr['mode'], 'linear')
        self.assertEqual(arr['axis'], 'x')
        self.assertEqual(arr['spacing'], 30000.0)
        self.assertEqual(arr['count'], 5)

    def test_create_pier_no_position_is_manual(self):
        parsed = ModelingCommandParser.parse("生成一个桥墩")
        self.assertEqual(parsed['component_type'], 'pier')
        self.assertEqual(parsed['position']['mode'], 'manual')

    def test_chinese_numeral_array_count_and_spacing(self):
        # 用户实测指令：汉字数字“五个”“二十米”
        parsed = ModelingCommandParser.parse("以原点为起点，沿y轴方向间隔20米放置五个桥墩。")
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'pier')
        arr = parsed['array']
        self.assertIsNotNone(arr)
        self.assertEqual(arr['mode'], 'linear')
        self.assertEqual(arr['axis'], 'y')
        self.assertEqual(arr['spacing'], 20000.0)
        self.assertEqual(arr['count'], 5)

    def test_chinese_numeral_array_count_cn_spacing(self):
        parsed = ModelingCommandParser.parse("沿x轴每隔二十米放置三个桥墩")
        arr = parsed['array']
        self.assertEqual(arr['spacing'], 20000.0)
        self.assertEqual(arr['count'], 3)

    def test_chinese_numeral_params(self):
        parsed = ModelingCommandParser.parse("生成墩高两千、系梁根数为三的引桥桥墩")
        self.assertEqual(parsed['component_type'], 'pier')
        self.assertEqual(parsed['params'].get('墩高'), 2000.0)
        self.assertEqual(parsed['params'].get('系梁根数'), 3.0)

    def test_chinese_numeral_relative_position(self):
        parsed = ModelingCommandParser.parse("在选中组件上方五百生成一个立方体")
        self.assertEqual(parsed['component_type'], 'cube')
        self.assertEqual(parsed['position']['mode'], 'relative')
        self.assertEqual(parsed['position']['axis'], 'z')
        self.assertEqual(parsed['position']['distance'], 500.0)

    def test_chinese_numeral_modify(self):
        parsed = ModelingCommandParser.parse("把选中桥墩的墩高改为两千，保持位置不变")
        self.assertEqual(parsed['action'], 'modify')
        self.assertEqual(parsed['params'].get('墩高'), 2000.0)
        self.assertTrue(parsed['preserve_position'])


class PierTypeInferTestCase(unittest.TestCase):
    """从参数字典推断组件类型"""

    def test_infer_pier(self):
        params = {'盖梁总长': 1930.0, '盖梁总高': 300.0, '盖梁宽': 300.0,
                  '墩柱直径': 250.0, '墩柱间距': 1140.0, '墩高': 1200.0, '系梁根数': 2}
        self.assertEqual(infer_component_type_from_params(params), 'pier')

    def test_infer_pier_partial_keys(self):
        self.assertEqual(infer_component_type_from_params({'墩高': 1200.0, '系梁根数': 2}), 'pier')

    def test_infer_anchor(self):
        params = {'锚块总长': 5450.0, '锚块总高': 2039.0, '承台长度': 5680.0, '底柱半径': 170.0}
        self.assertEqual(infer_component_type_from_params(params), 'anchor')

    def test_infer_basic_types_unchanged(self):
        self.assertEqual(infer_component_type_from_params({'半径': 100, '高度': 200}), 'cylinder')
        self.assertEqual(infer_component_type_from_params({'边长': 100}), 'cube')
        self.assertIsNone(infer_component_type_from_params({}))
        self.assertIsNone(infer_component_type_from_params(None))


class PierFactoryTestCase(unittest.TestCase):
    """组件工厂的 pier 注册与参数过滤"""

    def test_pier_registered(self):
        self.assertIn('pier', COMPONENT_CLASSES)
        self.assertIsNotNone(COMPONENT_CLASSES['pier'])
        self.assertIn('墩高', COMPONENT_DEFAULTS['pier'])
        self.assertIn('系梁根数', COMPONENT_DEFAULTS['pier'])

    def test_get_valid_kwargs_passthrough_for_var_keyword(self):
        class FakePier:
            def __init__(self, **kwargs):
                pass
        kwargs = {'墩高': 2000.0, '系梁根数': 3}
        self.assertEqual(_get_valid_kwargs(FakePier, kwargs), kwargs)

    def test_get_valid_kwargs_filters_for_named_params(self):
        class FakeCube:
            def __init__(self, size=100, ox=0):
                pass
        result = _get_valid_kwargs(FakeCube, {'size': 200, 'junk': 1})
        self.assertEqual(result, {'size': 200})

    def test_filter_component_params_drops_junk(self):
        params = {'墩高': 2000.0, 'height': 2000.0, '\x07_transformation': 'x',
                  '系梁根数': 3, 'length': 100}
        filtered = _filter_component_params('pier', params)
        self.assertEqual(filtered, {'墩高': 2000.0, '系梁根数': 3})

    def test_filter_component_params_other_types_untouched(self):
        params = {'radius': 100, 'height': 200}
        self.assertEqual(_filter_component_params('cylinder', params), params)


if __name__ == '__main__':
    unittest.main(verbosity=2)
