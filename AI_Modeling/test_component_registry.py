# -*- coding: utf-8 -*-
"""
AI_Modeling 组件注册表与解析器回归测试
无需启动 BIMBase，仅测试注册表持久化、命令解析等本地逻辑。
"""
import os
import sys
import json
import tempfile
import unittest

# 确保 AI_Modeling 在路径中
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

from ai_modeling.component_registry import ComponentRegistry
from ai_modeling.command_parser import ModelingCommandParser


class ComponentRegistryTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.registry_file = os.path.join(self.tmp_dir, 'test_registry.json')
        # 重置单例，确保每个测试使用独立的注册表
        ComponentRegistry._instance = None
        self.registry = ComponentRegistry(self.registry_file)

    def tearDown(self):
        ComponentRegistry._instance = None
        try:
            import shutil
            shutil.rmtree(self.tmp_dir)
        except Exception:
            pass

    def test_register_and_get(self):
        self.registry.register('key1', 'cylinder', {'radius': 300}, {'x': 1000, 'y': 2000, 'z': 500})
        record = self.registry.get('key1')
        self.assertIsNotNone(record)
        self.assertEqual(record['component_type'], 'cylinder')
        self.assertEqual(record['params']['radius'], 300)
        self.assertEqual(record['placement']['x'], 1000)

    def test_persistence(self):
        self.registry.register('key1', 'box', {'length': 200}, {'x': 1, 'y': 2, 'z': 3})
        # 重新实例化，模拟跨会话
        ComponentRegistry._instance = None
        reg2 = ComponentRegistry(self.registry_file)
        record = reg2.get('key1')
        self.assertIsNotNone(record)
        self.assertEqual(record['component_type'], 'box')

    def test_clear(self):
        self.registry.register('key1', 'cylinder', {}, {'x': 0, 'y': 0, 'z': 0})
        count = self.registry.clear()
        self.assertEqual(count, 1)
        self.assertIsNone(self.registry.get('key1'))
        # 确认 JSON 也被清空
        with open(self.registry_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data, {})

    def test_get_by_entity_id(self):
        self.registry.register('key1', 'cube', {'size': 100}, {'x': 0, 'y': 0, 'z': 0}, entity_id='eid123')
        record = self.registry.get_by_entity_id('eid123')
        self.assertIsNotNone(record)
        self.assertEqual(record['component_type'], 'cube')


class CommandParserTestCase(unittest.TestCase):
    def test_selected_position_create(self):
        parsed = ModelingCommandParser.parse('在选中的圆柱位置生成边长200的正方体')
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'cube')
        self.assertEqual(parsed['position']['mode'], 'selected')
        self.assertEqual(parsed['params']['size'], 200)

    def test_relative_position_create(self):
        parsed = ModelingCommandParser.parse('在选中实体上方500mm生成圆柱，半径100高200')
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'cylinder')
        self.assertEqual(parsed['position']['mode'], 'relative')
        self.assertEqual(parsed['position']['axis'], 'z')
        self.assertEqual(parsed['position']['distance'], 500)
        self.assertEqual(parsed['params']['radius'], 100)
        self.assertEqual(parsed['params']['height'], 200)

    def test_copy_command(self):
        parsed = ModelingCommandParser.parse('复制选中的圆柱到(1000,2000,0)')
        self.assertEqual(parsed['action'], 'copy')
        self.assertEqual(parsed['target']['mode'], 'selected')
        self.assertEqual(parsed['position']['mode'], 'absolute')
        self.assertEqual(parsed['position']['x'], 1000)
        self.assertEqual(parsed['position']['y'], 2000)
        self.assertEqual(parsed['position']['z'], 0)

    def test_preserve_position_modify(self):
        parsed = ModelingCommandParser.parse('把选中圆柱半径改成400，位置不变')
        self.assertEqual(parsed['action'], 'modify')
        self.assertTrue(parsed['preserve_position'])
        self.assertEqual(parsed['params']['radius'], 400)

    def test_complex_component_type(self):
        parsed = ModelingCommandParser.parse('生成一个引桥桥墩，盖梁总长2000')
        self.assertEqual(parsed['action'], 'create')
        self.assertEqual(parsed['component_type'], 'pier')
        self.assertEqual(parsed['params']['盖梁总长'], 2000)

        parsed2 = ModelingCommandParser.parse('生成索塔锚块，底柱半径180')
        self.assertEqual(parsed2['component_type'], 'anchor')
        self.assertEqual(parsed2['params']['底柱半径'], 180)

    def test_absolute_position_priority_over_selected(self):
        """复制到指定坐标时，应优先识别绝对坐标而非 selected 模式"""
        parsed = ModelingCommandParser.parse('复制选中的圆柱到(1000,2000,500)')
        self.assertEqual(parsed['position']['mode'], 'absolute')


if __name__ == '__main__':
    unittest.main()
