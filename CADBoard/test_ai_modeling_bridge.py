# -*- coding: utf-8 -*-
"""
ai_modeling_bridge 路由测试（纯标准库，无需 BIMBase/Qt 环境）

运行方式:
    python CADBoard/test_ai_modeling_bridge.py

验证点:
1. 3D 建模指令能被 AI_Modeling 解析器识别为可执行建模动作
2. 画板 2D 指令 / 闲聊 / 问句不会被误判为建模指令
"""
import os
import sys
import unittest

# 让 utils/ai_modeling_bridge.py 可被直接导入（桥接层顶层只依赖 os/importlib）
_UTILS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils')
if _UTILS_DIR not in sys.path:
    sys.path.insert(0, _UTILS_DIR)

import ai_modeling_bridge as bridge


class TestModelingBridgeParse(unittest.TestCase):

    def _check(self, text, action, **expect):
        parsed = bridge.parse_modeling_command(text)
        self.assertIsNotNone(parsed, f"未解析: {text}")
        self.assertEqual(parsed.get('action'), action, f"动作不符: {text} -> {parsed}")
        self.assertTrue(bridge.is_modeling_action(parsed), f"未判定为建模动作: {text}")
        params = parsed.get('params') or {}
        for key, val in expect.items():
            if key == 'params':
                for pk, pv in val.items():
                    self.assertAlmostEqual(params.get(pk), pv, places=6,
                                           msg=f"参数不符: {text} params.{pk}")
            else:
                self.assertEqual(parsed.get(key), val, f"字段不符: {text}.{key}")
        return parsed

    # ---- 应识别为建模指令 ----

    def test_create_cylinder(self):
        self._check('放一个半径2高5的圆柱', 'create',
                    component_type='cylinder',
                    params={'radius': 2.0, 'height': 5.0})

    def test_create_cylinder_absolute_position(self):
        parsed = self._check('在(1000,2000,500)生成半径300高800的圆柱', 'create',
                             component_type='cylinder',
                             params={'radius': 300.0, 'height': 800.0})
        pos = parsed.get('position') or {}
        self.assertEqual(pos.get('mode'), 'absolute')
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (1000.0, 2000.0, 500.0))

    def test_dot_separated_position(self):
        # 工程口语习惯：在500.200.100 → X=500, Y=200, Z=100
        parsed = self._check('在500.200.100的地方布置一个桥墩', 'create',
                             component_type='pier')
        pos = parsed.get('position') or {}
        self.assertEqual(pos.get('mode'), 'absolute')
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (500.0, 200.0, 100.0))

    def test_no_paren_comma_position(self):
        parsed = self._check('在500,200,100放一个圆柱', 'create',
                             component_type='cylinder')
        pos = parsed.get('position') or {}
        self.assertEqual(pos.get('mode'), 'absolute')
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (500.0, 200.0, 100.0))

    def test_no_paren_2d_position(self):
        parsed = self._check('在500,200放一个正方体', 'create', component_type='cube')
        pos = parsed.get('position') or {}
        self.assertEqual(pos.get('mode'), 'absolute')
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (500.0, 200.0, 0.0))

    # ---- 单位支持（内部统一毫米） ----

    def test_unit_suffix(self):
        parsed = self._check('在5m,4m,2m放一个半径50cm的圆柱', 'create',
                             component_type='cylinder', params={'radius': 500.0})
        pos = parsed.get('position') or {}
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (5000.0, 4000.0, 2000.0))

    def test_global_unit_declaration(self):
        parsed = self._check('单位用米，在5,4,2放一个桥墩', 'create', component_type='pier')
        pos = parsed.get('position') or {}
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (5000.0, 4000.0, 2000.0))

    def test_global_unit_short_form(self):
        # 用户实际输入的写法："单位m"
        parsed = self._check('在200，400，500的位置生成一个桥墩，单位m', 'create',
                             component_type='pier')
        pos = parsed.get('position') or {}
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (200000.0, 400000.0, 500000.0))

    def test_dot_triple_with_unit(self):
        parsed = self._check('在5.4.2米放一个桥墩', 'create', component_type='pier')
        pos = parsed.get('position') or {}
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (5000.0, 4000.0, 2000.0))

    def test_default_unit_is_mm(self):
        parsed = self._check('在500,200,100放一个圆柱', 'create', component_type='cylinder')
        pos = parsed.get('position') or {}
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (500.0, 200.0, 100.0))

    # ---- 不写入位置参数 ----

    def test_write_position_default_true(self):
        parsed = self._check('放一个半径2高5的圆柱', 'create')
        self.assertTrue(parsed.get('write_position'))

    def test_write_position_disabled(self):
        parsed = self._check('在500,400,200的位置放置一个桥墩，不要写入位置参数', 'create',
                             component_type='pier')
        self.assertFalse(parsed.get('write_position'))
        pos = parsed.get('position') or {}
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (500.0, 400.0, 200.0))

    def test_write_position_disabled_variant(self):
        # 用户实际输入的写法："不要位置参数"
        parsed = self._check('在200，300，400的位置放一个桥墩，不要位置参数，上成绿色', 'create',
                             component_type='pier')
        self.assertFalse(parsed.get('write_position'))
        self.assertEqual(parsed.get('color'), (0.0, 0.8, 0.0, 1.0))
        pos = parsed.get('position') or {}
        self.assertEqual((pos.get('x'), pos.get('y'), pos.get('z')), (200.0, 300.0, 400.0))

    def test_write_position_not_misfired_by_keep(self):
        # "位置不变" 是保留位置的修改指令，不能误判为"不写入"
        parsed = bridge.parse_modeling_command('把选中圆柱半径改成400，位置不变')
        self.assertIsNotNone(parsed)
        self.assertTrue(parsed.get('write_position'))

    # ---- 整体上色 ----

    def test_color_on_create(self):
        parsed = self._check('放一个红色的圆柱', 'create', component_type='cylinder')
        self.assertEqual(parsed.get('color'), (1.0, 0.0, 0.0, 1.0))

    def test_color_modify_selected(self):
        parsed = self._check('把选中的组件涂成半透明灰色', 'modify')
        self.assertEqual((parsed.get('params') or {}).get('颜色'), (0.5, 0.5, 0.5, 0.5))

    def test_no_color_by_default(self):
        parsed = self._check('放一个半径2高5的圆柱', 'create')
        self.assertIsNone(parsed.get('color'))

    # ---- AI JSON 颜色归一化 ----

    def test_normalize_color_value(self):
        self.assertEqual(bridge._normalize_color_value('红色'), (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(bridge._normalize_color_value('半透明灰'), (0.5, 0.5, 0.5, 0.5))
        self.assertEqual(bridge._normalize_color_value([1, 0, 0]), (1.0, 0.0, 0.0, 1.0))
        r, g, b, a = bridge._normalize_color_value([255, 0, 0, 1])
        self.assertAlmostEqual(r, 1.0)
        self.assertIsNone(bridge._normalize_color_value('没有颜色'))
        self.assertIsNone(bridge._normalize_color_value(None))

    def test_linear_array(self):
        parsed = self._check('沿X轴每隔10放5个圆柱', 'create', component_type='cylinder')
        arr = parsed.get('array') or {}
        self.assertEqual(arr.get('mode'), 'linear')
        self.assertEqual(arr.get('axis'), 'x')
        self.assertEqual(arr.get('count'), 5)
        self.assertAlmostEqual(arr.get('spacing'), 10.0)

    def test_rectangular_array(self):
        parsed = self._check('生成3×3方阵，间距2000，每个位置放一个正方体边长300', 'create',
                             component_type='cube', params={'size': 300.0})
        arr = parsed.get('array') or {}
        self.assertEqual(arr.get('mode'), 'rectangular')
        self.assertEqual((arr.get('rows'), arr.get('cols')), (3, 3))

    def test_copy_selected(self):
        parsed = self._check('复制选中的圆柱到(1000,2000,0)', 'copy')
        self.assertEqual((parsed.get('target') or {}).get('mode'), 'selected')

    def test_modify_selected(self):
        self._check('把选中的圆柱半径改成400', 'modify',
                    params={'radius': 400.0})

    def test_delete_selected(self):
        parsed = self._check('删除选中的组件', 'delete')
        self.assertEqual((parsed.get('target') or {}).get('mode'), 'selected')

    # ---- 不应误判为建模指令 ----

    def test_board_2d_command_not_modeling(self):
        # '画一个圆' 是画板 2D 指令，由画板解析器处理，建模解析器不应截胡
        parsed = bridge.parse_modeling_command('画一个半径50的圆')
        self.assertFalse(bridge.is_modeling_action(parsed))

    def test_chat_not_modeling(self):
        self.assertFalse(bridge.is_modeling_action(
            bridge.parse_modeling_command('今天天气怎么样')))

    def test_question_not_modeling(self):
        self.assertFalse(bridge.is_modeling_action(
            bridge.parse_modeling_command('怎么用拉伸')))

    # ---- 防御性输入 ----

    def test_empty_and_garbage(self):
        self.assertFalse(bridge.is_modeling_action(bridge.parse_modeling_command('')))
        self.assertFalse(bridge.is_modeling_action(None))
        self.assertFalse(bridge.is_modeling_action({}))


if __name__ == '__main__':
    unittest.main(verbosity=2)
