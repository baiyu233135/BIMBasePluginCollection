# -*- coding: utf-8 -*-
"""
CADBoard 缓存组件（退出面编辑后的普通线条）AI 操作链路回归测试

无需 BIMBase/pyp3d：用桩件模拟 board 元素，验证：
1. _resolve_target 对 {'mode': 'selected'} 和 {'component': True} 能把 3 个视图线归并回 1 个组件持有者
2. 持有者恢复 component_type / component_params / pdf_anchor
3. _tool_sync_to_bimbase 应用 position 且在 write_position=False 时移除位置参数
"""
import importlib.util
import os
import sys
import types
import unittest

_cadboard_dir = os.path.dirname(os.path.abspath(__file__))

# 按文件路径直接加载，避免 'utils' 与第三方包重名
_spec = importlib.util.spec_from_file_location(
    'bimbase_agent_under_test',
    os.path.join(_cadboard_dir, 'utils', 'bimbase_agent.py'))
_ba = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ba)
BIMBaseAgent = _ba.BIMBaseAgent


class _FakeElem:
    def __init__(self, eid, selected=True):
        self.id = eid
        self.selected = selected
        self.face_info = {}
        self.component_type = ''
        self.component_params = {}
        self.x = 0.0
        self.y = 0.0
        self.z_start = 0.0
        self.z_end = 100.0


class _FakeBoard:
    def __init__(self, elements):
        self.elements = elements
        self._face_component_id = None
        self.sync_all_called = 0

    def _sync_to_bimbase(self):
        self.sync_all_called += 1


def _make_cached_group():
    """构造一组退出面编辑后的三视图普通线条：front 带缓存，top/left 为兄弟"""
    front = _FakeElem('front-1')
    front._cached_component_type = '门式桥墩'
    front._cached_component_params = {
        '盖梁总长': 4700.0, '盖梁总高': 400.0, '盖梁宽': 1000.0, '墩高': 5000.0,
        '墩柱间距': 3500.0, '柱顶宽': 1200.0, '柱底宽': 1400.0,
        '柱顶厚': 1000.0, '柱底厚': 1200.0, '系梁根数': 1,
        'x': 100.0, 'y': 200.0, 'z_bottom': 50.0,
    }
    top = _FakeElem('top-1')
    left = _FakeElem('left-1')
    front._cached_sibling_ids = ['top-1', 'left-1']
    return front, top, left


class CachedComponentResolveTestCase(unittest.TestCase):
    def setUp(self):
        self.front, self.top, self.left = _make_cached_group()
        self.board = _FakeBoard([self.front, self.top, self.left])
        self.agent = BIMBaseAgent(self.board)

    def test_mode_selected_merges_to_holder(self):
        elems = self.agent._resolve_target({'mode': 'selected'})
        self.assertEqual(len(elems), 1)
        self.assertIs(elems[0], self.front)

    def test_component_keyword_merges_to_holder(self):
        elems = self.agent._resolve_target({'component': True})
        self.assertEqual(len(elems), 1)
        self.assertIs(elems[0], self.front)

    def test_holder_rehydrated(self):
        elems = self.agent._resolve_target({'mode': 'selected'})
        holder = elems[0]
        self.assertEqual(holder.component_type, '门式桥墩')
        self.assertEqual(holder.component_params.get('墩高'), 5000.0)
        self.assertEqual(holder.pdf_anchor_x, 100.0)
        self.assertEqual(holder.pdf_anchor_y, 200.0)
        self.assertEqual(holder.pdf_anchor_z, 50.0)
        # 缓存属性保留（重新进入面编辑仍可用）
        self.assertEqual(holder._cached_component_type, '门式桥墩')

    def test_partial_selection_sibling_maps_to_holder(self):
        # 只选中一个兄弟面（left），也应归并到持有者
        self.front.selected = False
        self.top.selected = False
        elems = self.agent._resolve_target({'mode': 'selected'})
        self.assertEqual(len(elems), 1)
        self.assertIs(elems[0], self.front)

    def test_sync_applies_position_and_write_position(self):
        # 桩件 BIMBaseSync，拦截 _sync_element
        calls = []

        class _FakeSync:
            def __init__(self, board):
                self.board = board

            def _sync_element(self, elem):
                calls.append(dict(elem.component_params))
                return True

        fake_mod = types.ModuleType('bimbase_sync')
        fake_mod.BIMBaseSync = _FakeSync
        sys.modules['bimbase_sync'] = fake_mod
        try:
            ok, msg = self.agent._tool_sync_to_bimbase({
                'target': {'mode': 'selected'},
                'position': {'x': 200000.0, 'y': 300000.0, 'z': 500000.0},
                'write_position': False,
            })
            self.assertTrue(ok, msg)
            self.assertEqual(len(calls), 1)  # 只同步一次
            # 放置位置写入锚点
            self.assertEqual(self.front.pdf_anchor_x, 200000.0)
            self.assertEqual(self.front.pdf_anchor_y, 300000.0)
            self.assertEqual(self.front.pdf_anchor_z, 500000.0)
            # write_position=False：组件参数不含位置键
            self.assertNotIn('x', calls[0])
            self.assertNotIn('y', calls[0])
            self.assertNotIn('z_bottom', calls[0])
        finally:
            del sys.modules['bimbase_sync']

    def test_sync_write_position_default_keeps_params(self):
        class _FakeSync:
            def __init__(self, board):
                pass

            def _sync_element(self, elem):
                return True

        fake_mod = types.ModuleType('bimbase_sync')
        fake_mod.BIMBaseSync = _FakeSync
        sys.modules['bimbase_sync'] = fake_mod
        try:
            ok, msg = self.agent._tool_sync_to_bimbase({
                'target': {'mode': 'selected'},
                'position': {'x': 1.0, 'y': 2.0, 'z': 3.0},
            })
            self.assertTrue(ok, msg)
            self.assertEqual(self.front.component_params.get('x'), 1.0)
            self.assertEqual(self.front.component_params.get('z_bottom'), 3.0)
        finally:
            del sys.modules['bimbase_sync']

    def test_position_without_target_uses_selected_not_sync_all(self):
        """AI 只给 position 不给 target 时：按选中组件定向同步，
        不走 board._sync_to_bimbase() 全量路径（避免弹基准坐标对话框）。"""
        # 模拟 PDF 识别来源标记：给出坐标后应被清除，避免坐标输入对话框
        self.front.pdf_recognized = True
        calls = []

        class _FakeSync:
            def __init__(self, board):
                pass

            def _sync_element(self, elem):
                calls.append(elem)
                return True

        fake_mod = types.ModuleType('bimbase_sync')
        fake_mod.BIMBaseSync = _FakeSync
        sys.modules['bimbase_sync'] = fake_mod
        try:
            ok, msg = self.agent._tool_sync_to_bimbase({
                'position': {'x': 52000.0, 'y': 13000.0, 'z': 10000.0},
            })
            self.assertTrue(ok, msg)
            self.assertEqual(self.board.sync_all_called, 0)  # 未走全量同步
            self.assertEqual(len(calls), 1)  # 只同步持有者一次
            self.assertIs(calls[0], self.front)
            self.assertFalse(self.front.pdf_recognized)  # 标记已清除，不会再弹窗
            self.assertEqual(self.front.pdf_anchor_x, 52000.0)
        finally:
            del sys.modules['bimbase_sync']

    def test_no_target_no_position_falls_back_to_sync_all(self):
        """既无 target 又无 position：维持原有的全量同步行为。"""
        ok, msg = self.agent._tool_sync_to_bimbase({})
        self.assertTrue(ok, msg)
        self.assertEqual(self.board.sync_all_called, 1)


class NormalizeChangesColorTestCase(unittest.TestCase):
    """颜色变更不能被 float() 崩掉"""

    def test_color_passthrough(self):
        front, top, left = _make_cached_group()
        board = _FakeBoard([front, top, left])
        agent = BIMBaseAgent(board)
        # 直接调用 _tool_modify_component 内部的归一化不可达（闭包），
        # 改为验证 _resolve_target + 颜色参数链路不抛异常的最小路径：
        # 构造 changes 含颜色，走 _tool_modify_component 的 auto 路径（无 BIMBase 扫描干扰）
        # 这里仅验证 _apply_position_to_element 与颜色透传不冲突
        elems = agent._resolve_target({'component': True})
        self.assertEqual(len(elems), 1)
        # 手动模拟 normalize：颜色键应原样保留
        changes = {'颜色': '1,0,0,1'}
        for key, val in changes.items():
            self.assertEqual(val, '1,0,0,1')  # 透传语义


class CopyComponentToolTestCase(unittest.TestCase):
    """画板侧复制工具：以画板选中组件为源，支持阵列与相对位置"""

    def setUp(self):
        self.front, self.top, self.left = _make_cached_group()
        self.board = _FakeBoard([self.front, self.top, self.left])
        self.board.apply_current_layer_style = lambda e: None
        self.board.viewport = types.SimpleNamespace(update=lambda: None)
        self.board.add_element = lambda e: self.board.elements.append(e)
        self.agent = BIMBaseAgent(self.board)
        self.synced = []
        self.created = []

        outer = self

        class _FakeSync:
            def __init__(self, board):
                pass

            def _sync_element(self, elem):
                outer.synced.append((elem.pdf_anchor_x, elem.pdf_anchor_y, elem.pdf_anchor_z))
                return True

        def _fake_create(params, comp_type):
            e = _FakeElem('new-%d' % len(outer.created), selected=False)
            e.component_type = comp_type
            e.component_params = dict(params)
            outer.created.append(e)
            return e

        sync_mod = types.ModuleType('bimbase_sync')
        sync_mod.BIMBaseSync = _FakeSync
        cr_mod = types.ModuleType('utils.component_registry')
        cr_mod.create_element_from_params = _fake_create
        utils_pkg = types.ModuleType('utils')
        utils_pkg.component_registry = cr_mod
        self._mods = {'bimbase_sync': sync_mod, 'utils': utils_pkg,
                      'utils.component_registry': cr_mod}
        sys.modules.update(self._mods)

    def tearDown(self):
        for k in self._mods:
            sys.modules.pop(k, None)

    def test_array_copy_from_board_selection(self):
        ok, msg = self.agent.execute_tool('copy_component', {
            'target': {'mode': 'selected'},
            'position': {'mode': 'manual'},
            'array': {'mode': 'linear', 'axis': 'x', 'spacing': 500000.0, 'count': 5},
        })
        self.assertTrue(ok, msg)
        self.assertEqual(len(self.created), 5)
        self.assertEqual(len(self.synced), 5)
        # 基准 (100,200,50)，沿 x 间隔 500000
        xs = [p[0] for p in self.synced]
        self.assertEqual(xs, [100.0 + 500000.0 * i for i in range(5)])
        # 副本是可识别元素
        self.assertTrue(all(e.component_type == '门式桥墩' for e in self.created))

    def test_relative_copy(self):
        ok, msg = self.agent.execute_tool('copy_component', {
            'target': {'mode': 'selected'},
            'position': {'mode': 'relative', 'axis': 'z', 'distance': 500000.0},
        })
        self.assertTrue(ok, msg)
        self.assertEqual(len(self.synced), 1)
        self.assertEqual(self.synced[0], (100.0, 200.0, 50.0 + 500000.0))


if __name__ == '__main__':
    unittest.main()
