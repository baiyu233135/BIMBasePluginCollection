# -*- coding: utf-8 -*-
"""
AI_Modeling 对话删除组件链路回归测试
无需启动 BIMBase：解析器离线测试 + delete_selected_components 打桩测试
+ ai_window._execute_local_delete 路由逻辑测试（fake self，不建真实窗口）。
"""
import os
import sys
import unittest
from unittest import mock

# 确保 AI_Modeling 在路径中
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

from ai_modeling.command_parser import ModelingCommandParser
import ai_modeling.bimbase_modifier as modifier


class DeleteParseTestCase(unittest.TestCase):
    """解析器对删除指令的解析"""

    def test_delete_selected_pier(self):
        parsed = ModelingCommandParser.parse("删除选中的桥墩")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['action'], 'delete')
        self.assertEqual(parsed['target']['mode'], 'selected')
        self.assertEqual(parsed['component_type'], 'pier')

    def test_delete_selected_cylinder_remove_wording(self):
        parsed = ModelingCommandParser.parse("移除选中的圆柱")
        self.assertEqual(parsed['action'], 'delete')
        self.assertEqual(parsed['target']['mode'], 'selected')

    def test_delete_diaowuo_wording(self):
        parsed = ModelingCommandParser.parse("把选中的正方体删掉")
        self.assertEqual(parsed['action'], 'delete')
        self.assertEqual(parsed['target']['mode'], 'selected')

    def test_delete_last_one(self):
        parsed = ModelingCommandParser.parse("删除最后一个桥墩")
        self.assertEqual(parsed['action'], 'delete')
        self.assertEqual(parsed['target']['mode'], 'last')

    def test_delete_by_index(self):
        parsed = ModelingCommandParser.parse("删除第2个圆柱")
        self.assertEqual(parsed['action'], 'delete')
        self.assertEqual(parsed['target']['mode'], 'index')
        self.assertEqual(parsed['target']['index'], 1)

    def test_delete_chinese_numeral_index(self):
        parsed = ModelingCommandParser.parse("删除第三个圆柱")
        self.assertEqual(parsed['action'], 'delete')
        self.assertEqual(parsed['target']['mode'], 'index')
        self.assertEqual(parsed['target']['index'], 2)

    def test_create_command_not_hijacked(self):
        # 创建指令不含删除关键词时不受影响
        parsed = ModelingCommandParser.parse("在(0,0,0)生成一个桥墩")
        self.assertEqual(parsed['action'], 'create')


class DeleteSelectedComponentsTestCase(unittest.TestCase):
    """delete_selected_components 打桩测试（不连真实 BIMBase）"""

    def test_pyp3d_not_loaded(self):
        with mock.patch.object(modifier, '_pyp3d_ok', False):
            ok, msg, deleted = modifier.delete_selected_components()
        self.assertFalse(ok)
        self.assertEqual(deleted, 0)
        self.assertIn('pyp3d', msg)

    def test_no_selection(self):
        with mock.patch.object(modifier, '_pyp3d_ok', True), \
             mock.patch.object(modifier, 'get_selected_entity_ids', return_value=[]), \
             mock.patch.object(modifier, 'get_selected_instance_keys', return_value=[]):
            ok, msg, deleted = modifier.delete_selected_components()
        self.assertFalse(ok)
        self.assertIn('未在 BIMBase 中选中', msg)

    def _run_with_selection(self, entity_ids, instance_keys, before_after=(-1, -1),
                            entity_delete_fails=False):
        """公共打桩：返回 (result, mocks_dict)"""
        delete_entity_mock = mock.Mock()
        if entity_delete_fails:
            delete_entity_mock.side_effect = RuntimeError('entity delete failed')
        delete_data_mock = mock.Mock()
        registry_mock = mock.Mock()
        registry_mock._key_str = lambda k: f"str({k})" if k is not None else None
        registry_mock.all_records.return_value = {}

        counts = iter(before_after)
        with mock.patch.object(modifier, '_pyp3d_ok', True), \
             mock.patch.object(modifier, 'get_selected_entity_ids', return_value=entity_ids), \
             mock.patch.object(modifier, 'get_selected_instance_keys', return_value=instance_keys), \
             mock.patch.object(modifier, 'delete_one_entity', delete_entity_mock), \
             mock.patch.object(modifier, 'delete_data_bydatakey', delete_data_mock), \
             mock.patch.object(modifier, '_count_entities', side_effect=lambda: next(counts)), \
             mock.patch.object(modifier, '_is_entity_valid', return_value=True), \
             mock.patch('ai_modeling.component_registry.get_registry', return_value=registry_mock):
            result = modifier.delete_selected_components()
        return result, {
            'delete_entity': delete_entity_mock,
            'delete_data': delete_data_mock,
            'registry': registry_mock,
        }

    def test_delete_by_entity_success(self):
        (ok, msg, deleted), mocks = self._run_with_selection(['eid1'], ['ik1'])
        self.assertTrue(ok)
        self.assertEqual(deleted, 1)
        self.assertIn('已删除 1 个', msg)
        mocks['delete_entity'].assert_called_once_with('eid1')
        mocks['delete_data'].assert_not_called()
        # 注册表按 instance_key 注销
        mocks['registry'].unregister.assert_called_with('ik1')

    def test_delete_fallback_to_instance(self):
        # 实体删除抛异常 → 兜底按实例删除
        (ok, msg, deleted), mocks = self._run_with_selection(
            ['eid1'], ['ik1'], entity_delete_fails=True)
        self.assertTrue(ok)
        self.assertEqual(deleted, 1)
        mocks['delete_entity'].assert_called_once_with('eid1')
        mocks['delete_data'].assert_called_once_with('ik1')

    def test_delete_no_api_available(self):
        with mock.patch.object(modifier, '_pyp3d_ok', True), \
             mock.patch.object(modifier, 'get_selected_entity_ids', return_value=['eid1']), \
             mock.patch.object(modifier, 'get_selected_instance_keys', return_value=['ik1']), \
             mock.patch.object(modifier, 'delete_one_entity', None), \
             mock.patch.object(modifier, 'delete_data_bydatakey', None):
            ok, msg, deleted = modifier.delete_selected_components()
        self.assertFalse(ok)
        self.assertIn('没有可用的删除 API', msg)

    def test_delete_not_verified(self):
        # 删除前后实体数相同且实体仍有效 → 判定未生效，不注销注册表
        (ok, msg, deleted), mocks = self._run_with_selection(
            ['eid1'], ['ik1'], before_after=(10, 10))
        self.assertFalse(ok)
        self.assertIn('未减少', msg)
        mocks['registry'].unregister.assert_not_called()

    def test_delete_verified_by_count(self):
        (ok, msg, deleted), mocks = self._run_with_selection(
            ['eid1', 'eid2'], ['ik1', 'ik2'], before_after=(10, 8))
        self.assertTrue(ok)
        self.assertEqual(deleted, 2)
        self.assertEqual(mocks['delete_entity'].call_count, 2)


class WindowDeleteRoutingTestCase(unittest.TestCase):
    """ai_window._execute_local_delete 路由逻辑（fake self，不建真实窗口）"""

    @classmethod
    def setUpClass(cls):
        try:
            import ai_modeling.ai_window as aw
            cls.aw = aw
        except Exception as e:
            raise unittest.SkipTest(f"ai_window 离线导入失败: {e}")

    def _make_fake_self(self):
        msgs = []

        class FakeStatus:
            def setText(self, t):
                pass

        class FakeSelf:
            _append_system = lambda self, t, c="#666": msgs.append(t)
            status_label = FakeStatus()

        return FakeSelf(), msgs

    def _call_delete(self, fake, parsed, text, n_entity=1, n_keys=1,
                     delete_result=(True, '已删除 1 个组件', 1), confirm_yes=True):
        delete_mock = mock.Mock(return_value=delete_result)
        with mock.patch.object(self.aw, 'delete_selected_components', delete_mock), \
             mock.patch.object(self.aw, 'get_selected_instance_keys',
                               return_value=['k'] * n_keys), \
             mock.patch('ai_modeling.bimbase_modifier.get_selected_entity_ids',
                        return_value=['e'] * n_entity), \
             mock.patch('PyQt5.QtWidgets.QMessageBox.question',
                        return_value=self._qmb_yes() if confirm_yes else self._qmb_no()):
            self.aw.AIModelingWindow._execute_local_delete(fake, parsed, text)
        return delete_mock

    @staticmethod
    def _qmb_yes():
        from PyQt5.QtWidgets import QMessageBox
        return QMessageBox.Yes

    @staticmethod
    def _qmb_no():
        from PyQt5.QtWidgets import QMessageBox
        return QMessageBox.No

    def test_single_selected_deletes_directly(self):
        fake, msgs = self._make_fake_self()
        delete_mock = self._call_delete(fake, {'target': {'mode': 'selected'}}, '删除选中的组件')
        delete_mock.assert_called_once()
        self.assertTrue(any('已删除' in m for m in msgs))

    def test_batch_all_blocked(self):
        fake, msgs = self._make_fake_self()
        delete_mock = self._call_delete(fake, {'target': {'mode': 'selected'}}, '删除所有圆柱')
        delete_mock.assert_not_called()
        self.assertTrue(any('暂不支持批量删除' in m for m in msgs))

    def test_index_target_blocked(self):
        fake, msgs = self._make_fake_self()
        delete_mock = self._call_delete(fake, {'target': {'mode': 'index', 'index': 1}}, '删除第2个圆柱')
        delete_mock.assert_not_called()
        self.assertTrue(any('仅支持删除选中组件' in m for m in msgs))

    def test_multi_selection_confirm_yes(self):
        fake, msgs = self._make_fake_self()
        delete_mock = self._call_delete(fake, {'target': {'mode': 'selected'}},
                                        '删除选中的组件', n_entity=2, n_keys=2,
                                        delete_result=(True, '已删除 2 个组件', 2),
                                        confirm_yes=True)
        delete_mock.assert_called_once()

    def test_multi_selection_confirm_no(self):
        fake, msgs = self._make_fake_self()
        delete_mock = self._call_delete(fake, {'target': {'mode': 'selected'}},
                                        '删除选中的组件', n_entity=2, n_keys=2,
                                        confirm_yes=False)
        delete_mock.assert_not_called()
        self.assertTrue(any('已取消删除' in m for m in msgs))

    def test_delete_failure_message(self):
        fake, msgs = self._make_fake_self()
        delete_mock = self._call_delete(fake, {'target': {'mode': 'selected'}}, '删除选中的组件',
                                        delete_result=(False, '未在 BIMBase 中选中任何组件，请先选中要删除的组件', 0))
        delete_mock.assert_called_once()
        self.assertTrue(any('未在 BIMBase 中选中' in m for m in msgs))


if __name__ == '__main__':
    unittest.main(verbosity=2)
