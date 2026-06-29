# -*- coding: utf-8 -*-
"""
轻量级 BIMBase Agent - Phase 2

工具注册表模式，支持双路径操作:
- 路径 A: 修改 board 元素 → sync to BIMBase
- 路径 B: 直接 re-place in BIMBase (BIMBase-origin 元素)

不依赖外部 LLM，由 AICommandExecutor 调用执行。
"""

import os


class BIMBaseAgent:
    """轻量级 BIMBase Agent - 工具注册表"""

    def __init__(self, board):
        self.board = board
        self.tools = {
            'query_state': self._tool_query_state,
            'modify_component': self._tool_modify_component,
            'sync_to_bimbase': self._tool_sync_to_bimbase,
            'replace_in_bimbase': self._tool_replace_in_bimbase,
            'regenerate_faces': self._tool_regenerate_faces,
            'apply_face_changes': self._tool_apply_face_changes,
            'exit_face_edit': self._tool_exit_face_edit,
        }

    def execute_tool(self, tool_name, params):
        """执行指定工具，返回 (success, message)"""
        tool = self.tools.get(tool_name)
        if not tool:
            return False, f"未知工具: {tool_name}"
        try:
            return tool(params or {})
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            return False, f"工具 {tool_name} 执行失败: {e}\n{tb}"

    # ========== 工具实现 ==========

    @staticmethod
    def _clean_value(v):
        """清理参数值，避免 bytearray 等不可序列化对象产生乱码"""
        if isinstance(v, (int, float, str, bool, type(None))):
            return v
        if isinstance(v, (list, tuple)):
            return [BIMBaseAgent._clean_value(x) for x in v]
        if isinstance(v, dict):
            return {k: BIMBaseAgent._clean_value(vv) for k, vv in v.items()}
        if isinstance(v, bytearray):
            return f"<bytearray len={len(v)}>"
        # 其他对象（如 BIMBase SDK 内部对象）转为简短字符串
        try:
            s = str(v)
            if len(s) > 60:
                s = s[:57] + '...'
            return f"<{type(v).__name__}:{s}>"
        except Exception:
            return f"<{type(v).__name__}:?>"

    @staticmethod
    def _clean_params(params):
        """清理参数字典，过滤内部字段和不可序列化值"""
        if not params:
            return {}
        result = {}
        for k, v in params.items():
            if isinstance(k, str) and k.startswith('_'):
                continue
            result[k] = BIMBaseAgent._clean_value(v)
        return result

    def _tool_query_state(self, params):
        """查询画板和 BIMBase 的当前状态"""
        lines = []

        # 1. 画板中的组件
        components = []
        for e in getattr(self.board, 'elements', []):
            if getattr(e, 'component_type', '') and not getattr(e, 'face_info', {}):
                # P3DInstanceKey 的 __bool__/__len__ 可能触发 _data AttributeError，
                # 因此绝不对 datakey 对象调用 bool()，只检查是否为 None
                dk = getattr(e, '_bimbase_datakey', None)
                is_bimbase_origin = dk is not None
                raw_params = dict(e.component_params) if e.component_params else {}
                components.append({
                    'id': e.id,
                    'type': e.component_type,
                    'params': self._clean_params(raw_params),
                    'bimbase_origin': is_bimbase_origin,
                    'selected': getattr(e, 'selected', False),
                })
        lines.append(f"画板组件: {len(components)} 个")
        for c in components:
            origin_flag = " [BIMBase来源]" if c['bimbase_origin'] else ""
            sel_flag = " (已选中)" if c['selected'] else ""
            lines.append(f"  - {c['type']}: {c['params']}{origin_flag}{sel_flag}")

        # 2. 面元素
        faces = []
        for e in getattr(self.board, 'elements', []):
            if getattr(e, 'face_info', {}):
                faces.append({
                    'name': e.face_info.get('face_name', ''),
                    'component_id': e.face_info.get('component_id', '')[:8],
                })
        if faces:
            lines.append(f"面元素: {len(faces)} 个")
            for f in faces:
                from geometry.faces import FACE_NAME_LABELS
                display_name = FACE_NAME_LABELS.get(f['name'], f['name'])
                lines.append(f"  - {display_name} (组件 {f['component_id']})")

        # 3. BIMBase 中是否有选中实体
        bimbase_selected = 0
        try:
            from bimbase_sync import get_entityid_from_boxselection
            if get_entityid_from_boxselection is not None:
                ids = get_entityid_from_boxselection() or []
                bimbase_selected = len(ids)
        except Exception:
            pass
        lines.append(f"BIMBase 选中实体: {bimbase_selected} 个")

        return True, "\n".join(lines)

    def _scan_bimbase_for_type(self, comp_type, max_scan=100):
        """轻量扫描 BIMBase，检查是否存在指定类型的参数化组件。
        返回 True/False。"""
        try:
            from bimbase_sync import BIMBaseSync, get_all_instancekey
            if get_all_instancekey is None:
                return False
            keys = get_all_instancekey() or []
            if not keys:
                return False
            sync = BIMBaseSync(self.board)
            count = 0
            for ik in keys:
                if count >= max_scan:
                    break
                count += 1
                p = sync._get_params_from_datakey(ik)
                if p and p.get('_type') == comp_type:
                    return True
            return False
        except Exception:
            return False

    def _tool_modify_component(self, params):
        """
        修改组件参数，自动选择路径 A 或路径 B。
        params:
          - target: {'component_type': '圆柱'} 或 {'index': 0}
          - changes: {'半径': 80}
          - path: 'auto'|'board'|'bimbase'  (默认 auto)
        """
        target = params.get('target', {})
        changes = params.get('changes', {})
        path_hint = params.get('path', 'auto')

        if not changes:
            return False, "modify_component 缺少 changes 参数"

        # 解析目标元素
        elems = self._resolve_target(target)
        if not elems:
            return False, f"未找到目标组件: {target}"

        results = []
        for elem in elems:
            comp_type = getattr(elem, 'component_type', '')
            if not comp_type:
                continue

            # 确定操作路径（注意：绝不对 _bimbase_datakey 调用 bool()，
            # 因为 P3DInstanceKey.__bool__ 会触发 '_data' AttributeError）
            dk = getattr(elem, '_bimbase_datakey', None)
            is_bimbase_origin = dk is not None
            if path_hint == 'auto':
                # 歧义检测：如果画板中有该类型组件，且 BIMBase 中也存在同类型实体，
                # 提示用户明确来源（因为 _resolve_target 只能看到画板元素，
                # 真正的"同时存在"是画板元素 + BIMBase 独立实体）。
                bimbase_has_same_type = self._scan_bimbase_for_type(comp_type)
                if bimbase_has_same_type:
                    return False, (
                        f"检测到 '{comp_type}' 同时存在于画板和 BIMBase 中，"
                        f"请明确指定来源后再操作。例如：\n"
                        f"  • '修改画板中的{comp_type}高度为100'\n"
                        f"  • '修改 BIMBase 中的{comp_type}高度为100'"
                    )
                if is_bimbase_origin:
                    path = 'bimbase'
                else:
                    path = 'board'
            else:
                path = path_hint

            if path == 'board':
                # 路径 A: 修改 board → sync
                ok, msg = self._modify_board_then_sync(elem, changes)
                results.append(f"{comp_type}(board): {msg}")
            elif path == 'bimbase':
                # 路径 B: 直接 re-place in BIMBase
                ok, msg = self._replace_in_bimbase(elem, changes)
                results.append(f"{comp_type}(bimbase): {msg}")
            else:
                results.append(f"{comp_type}: 未知路径 {path}")

        return True, "\n".join(results)

    def _tool_sync_to_bimbase(self, params):
        """将选中的或指定元素同步到 BIMBase"""
        target = params.get('target', None)
        if target:
            elems = self._resolve_target(target)
            if elems:
                # 只同步指定元素
                count = 0
                errors = []
                for elem in elems:
                    try:
                        from bimbase_sync import BIMBaseSync
                        sync = BIMBaseSync(self.board)
                        if sync._sync_element(elem):
                            count += 1
                    except Exception as e:
                        errors.append(str(e))
                msg = f"同步 {count}/{len(elems)} 个元素到 BIMBase"
                if errors:
                    msg += f"\n错误: {errors[:3]}"
                return count > 0, msg

        # 同步全部
        self.board._sync_to_bimbase()
        return True, "已触发全部同步到 BIMBase"

    def _tool_replace_in_bimbase(self, params):
        """强制在 BIMBase 中重新放置组件（路径 B）"""
        target = params.get('target', {})
        changes = params.get('changes', {})
        elems = self._resolve_target(target)
        if not elems:
            return False, f"未找到目标: {target}"

        results = []
        for elem in elems:
            ok, msg = self._replace_in_bimbase(elem, changes)
            results.append(msg)
        return True, "\n".join(results)

    def _tool_regenerate_faces(self, params):
        """重新生成面元素"""
        target = params.get('target', {})
        mode = params.get('mode', None)  # '三视图' 或 '完整'
        elems = self._resolve_target(target)
        if not elems:
            # 如果没有指定目标，尝试当前面编辑模式的源组件
            face_cid = getattr(self.board, '_face_component_id', None)
            if face_cid:
                elems = [e for e in getattr(self.board, 'elements', [])
                         if e.id == face_cid and not getattr(e, 'face_info', {})]

        if not elems:
            return False, "未找到要生成面的组件，请先选中一个参数化组件"

        from geometry.faces import FaceManager
        fg = getattr(self.board, '_face_group', None)
        if not fg:
            return False, "面编辑系统未初始化"

        count = 0
        for elem in elems:
            if not getattr(elem, 'component_type', ''):
                continue
            if mode and hasattr(elem, 'component_params') and elem.component_params is not None:
                elem.component_params['_face_mode'] = mode
            faces = fg.generate_faces_for_element(elem)
            if faces:
                fg.replace_faces(elem.id, faces)
                elem.visible = False
                count += 1

        self.board.viewport.update()
        return count > 0, f"已为 {count} 个组件重新生成面元素"

    def _tool_apply_face_changes(self, params):
        """应用面修改并同步"""
        try:
            self.board._apply_face_changes()
            return True, "已应用面修改"
        except Exception as e:
            return False, f"应用面修改失败: {e}"

    def _tool_exit_face_edit(self, params):
        """退出面编辑模式"""
        try:
            if hasattr(self.board, '_exit_face_edit_mode'):
                self.board._exit_face_edit_mode()
                return True, "已退出面编辑模式"
            return False, "画板不支持面编辑模式"
        except Exception as e:
            return False, f"退出面编辑模式失败: {e}"

    # ========== 内部辅助方法 ==========

    def _resolve_target(self, target):
        """解析目标，返回元素列表"""
        if not target:
            return [e for e in getattr(self.board, 'elements', [])
                    if getattr(e, 'selected', False)]

        elems = getattr(self.board, 'elements', [])
        result = list(elems)

        # 先按 component_type 过滤
        if 'component_type' in target:
            ct = target['component_type']
            result = [e for e in result
                      if getattr(e, 'component_type', '') == ct
                      and not getattr(e, 'face_info', {})]

        # 再按 index 过滤
        if 'index' in target:
            idx = target['index']
            if idx == 'selected':
                result = [e for e in result if getattr(e, 'selected', False)]
            elif idx == 'all':
                pass  # 保留当前 result
            elif isinstance(idx, int) and 0 <= idx < len(result):
                result = [result[idx]]
            elif isinstance(idx, int):
                result = []  # 索引越界

        return result

    def _modify_board_then_sync(self, elem, changes):
        """路径 A: 修改 board 元素参数，然后 sync 到 BIMBase"""
        self.board._save_undo_state()
        comp_type = elem.component_type
        params = dict(elem.component_params) if elem.component_params else {}

        # 应用参数变更
        for k, v in changes.items():
            params[k] = v
        elem.component_params = params

        # 同时更新元素的几何属性（确保画板显示正确）
        from utils.component_registry import apply_component_params_to_element
        apply_component_params_to_element(elem, params, comp_type)

        # 如果处于面编辑模式，重新生成面
        face_cid = getattr(self.board, '_face_component_id', None)
        if face_cid == elem.id:
            fg = getattr(self.board, '_face_group', None)
            if fg:
                faces = fg.generate_faces_for_element(elem)
                if faces:
                    fg.replace_faces(elem.id, faces)
                    elem.visible = False

        self.board.viewport.update()

        # 同步到 BIMBase
        try:
            from bimbase_sync import BIMBaseSync
            sync = BIMBaseSync(self.board)
            if sync._sync_element(elem):
                return True, "参数已更新并同步到 BIMBase"
            else:
                return True, "参数已更新，但同步到 BIMBase 失败（可能是首次同步）"
        except Exception as e:
            return True, f"参数已更新，同步时出错: {e}"

    def _replace_in_bimbase(self, elem, changes):
        """路径 B: 直接在 BIMBase 中重新放置组件"""
        self.board._save_undo_state()
        comp_type = elem.component_type
        params = dict(elem.component_params) if elem.component_params else {}

        # 应用参数变更
        for k, v in changes.items():
            params[k] = v
        elem.component_params = params

        # 更新元素几何属性
        from utils.component_registry import apply_component_params_to_element
        apply_component_params_to_element(elem, params, comp_type)

        self.board.viewport.update()

        # 重新 place 到 BIMBase
        try:
            from bimbase_sync import BIMBaseSync
            sync = BIMBaseSync(self.board)
            comp, new_params, new_type = sync._make_component(elem)
            if comp is None:
                return False, "无法构建组件"
            sync._place_component(comp)
            sync.registry.register(elem.id, comp, new_params, new_type)
            elem.bimbase_component_id = id(comp)
            # 更新高度信息
            if new_type == '直角三棱柱':
                if '高度' in new_params:
                    elem.z_end = elem.z_start + float(new_params['高度'])
            elif new_type == '圆柱':
                if '高度' in new_params:
                    elem.z_end = elem.z_start + float(new_params['高度'])
            elif new_type == '正方体':
                if '边长' in new_params:
                    elem.z_end = elem.z_start + float(new_params['边长'])
            elif new_type == '长方体':
                if '高度' in new_params:
                    elem.z_end = elem.z_start + float(new_params['高度'])
            elif new_type == '引桥桥墩':
                pier_h = float(new_params.get('墩高', 1200)) + float(new_params.get('盖梁总高', 300))
                elem.z_end = elem.z_start + pier_h
            else:
                z_bottom = new_params.get('z_bottom') or new_params.get('z1') or new_params.get('z', 0)
                z_top = new_params.get('z_top') or new_params.get('z2') or new_params.get('z', 0)
                if z_bottom is not None:
                    elem.z_start = float(z_bottom)
                if z_top is not None:
                    elem.z_end = float(z_top)
            elem.is_3d = True
            return True, "已在 BIMBase 中重新放置组件（旧实例保留）"
        except Exception as e:
            return False, f"重新放置失败: {e}"
