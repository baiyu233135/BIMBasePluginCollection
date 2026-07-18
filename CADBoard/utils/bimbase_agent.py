# -*- coding: utf-8 -*-
"""
轻量级 BIMBase Agent - Phase 2

工具注册表模式，支持双路径操作:
- 路径 A: 修改 board 元素 → sync to BIMBase
- 路径 B: 直接 re-place in BIMBase (BIMBase-origin 元素)

不依赖外部 LLM，由 AICommandExecutor 调用执行。
"""

import os

try:
    from bimbase_sync import _log
except Exception:
    def _log(msg):
        try:
            log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bimbase_sync_debug.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                from datetime import datetime
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [BIMBaseAgent] {msg}\n")
                f.flush()
        except Exception:
            pass


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

    def _scan_bimbase_for_type(self, comp_type, max_scan=20):
        """轻量扫描 BIMBase，检查是否存在指定类型的参数化组件。
        返回 True/False。对异常 key 直接跳过，避免扫描过程破坏 SDK 状态。"""
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
                try:
                    p = sync._get_params_from_datakey(ik)
                    if p and p.get('_type') == comp_type:
                        return True
                except Exception:
                    # 某些实例 key 可能无法读取，跳过即可
                    pass
            return False
        except Exception:
            return False

    def _tool_modify_component(self, params):
        """
        修改组件参数，自动选择路径 A 或路径 B；支持指定新放置坐标。
        params:
          - target: {'component_type': '圆柱'} 或 {'index': 0}
          - changes: {'半径': 80}
          - path: 'auto'|'board'|'bimbase'  (默认 auto)
          - position: {'x': 100, 'y': 200, 'z': 0} 或 [100, 200, 0]（可选）
        """
        target = params.get('target', {})
        changes = params.get('changes', {})
        path_hint = params.get('path', 'auto')
        position = params.get('position')

        if not changes and not position:
            return False, "modify_component 缺少 changes 或 position 参数"
        _log(f"modify_component called target={target} changes={changes} position={position} path={path_hint}")

        # 解析目标元素
        elems = self._resolve_target(target)
        if not elems:
            return False, f"未找到目标组件: {target}"

        # 收集有效元素，并先应用坐标变更
        elems_info = []
        for elem in elems:
            comp_type = getattr(elem, 'component_type', '')
            if not comp_type:
                continue
            if position:
                _log(f"[_tool_modify_component] applying position {position} to elem {elem.id[:8]} ({comp_type})")
                self._apply_position_to_element(elem, position)
                _log(f"[_tool_modify_component] position applied, pdf_anchor=({getattr(elem,'pdf_anchor_x',None)},{getattr(elem,'pdf_anchor_y',None)},{getattr(elem,'pdf_anchor_z',None)})")
            elems_info.append((elem, comp_type))

        if not elems_info:
            return False, f"未找到有效的参数化组件: {target}"

        # 规范化 changes：把通用别名映射为组件专用参数名，并处理相对值
        def _normalize_changes(comp_type, params, changes):
            mapping = {
                '引桥桥墩': {
                    'height': '墩高', 'h': '墩高',
                    'width': '盖梁总长', 'length': '盖梁总长', 'l': '盖梁总长',
                    'depth': '盖梁宽', 'w': '盖梁宽',
                    '墩高': '墩高', '盖梁总长': '盖梁总长', '盖梁总高': '盖梁总高',
                    '盖梁宽': '盖梁宽', '墩柱直径': '墩柱直径', '墩柱间距': '墩柱间距',
                    '系梁根数': '系梁根数', '系梁数量': '系梁根数',
                },
                '索缆锚锭': {
                    'length': '锚块总长', 'l': '锚块总长',
                    'width': '锚块宽度', 'w': '锚块宽度',
                    'height': '锚块总高', 'h': '锚块总高',
                    '锚块总长': '锚块总长', '锚块总高': '锚块总高', '锚块宽度': '锚块宽度',
                    '承台长度': '承台长度', '承台宽度': '承台宽度', '承台高度': '承台高度',
                    '底柱半径': '底柱半径', '底柱高度': '底柱高度',
                    '底柱数量': '底柱数量', '底柱排数': '底柱排数',
                    '系梁数量': '系梁数量',
                },
            }.get(comp_type, {})
            normalized = {}
            for key, val in changes.items():
                mk = mapping.get(key, key)
                # 相对值表达式
                if isinstance(val, str):
                    val = val.strip()
                    if val.startswith(('+', '-', '*', '/')):
                        old = float(params.get(mk, 0))
                        op = val[0]
                        num = float(val[1:])
                        if op == '+':
                            val = old + num
                        elif op == '-':
                            val = old - num
                        elif op == '*':
                            val = old * num
                        elif op == '/':
                            val = old / num if num != 0 else old
                    else:
                        val = float(val)
                # 计数类参数保持 int
                if mk in ('系梁根数', '系梁数量', '底柱数量', '底柱排数'):
                    val = int(round(float(val)))
                else:
                    val = float(val)
                normalized[mk] = val
            return normalized

        results = []

        if path_hint == 'auto':
            # 歧义检测：每种类型的组件只扫描一次 BIMBase。
            # 若用户已明确给出放置坐标，说明操作对象是画板元素，跳过扫描避免误拦/异常。
            if position is None:
                scanned_types = set()
                for _, comp_type in elems_info:
                    if comp_type in scanned_types:
                        continue
                    scanned_types.add(comp_type)
                    try:
                        bimbase_has_same_type = self._scan_bimbase_for_type(comp_type)
                    except Exception:
                        bimbase_has_same_type = False
                    if bimbase_has_same_type:
                        return False, (
                            f"检测到 '{comp_type}' 同时存在于画板和 BIMBase 中，"
                            f"请明确指定来源后再操作。例如：\n"
                            f"  • '修改画板中的{comp_type}高度为100'\n"
                            f"  • '修改 BIMBase 中的{comp_type}高度为100'"
                        )

            # 为每个元素确定具体路径：auto 模式统一走 board 路径，
            # 由 _sync_element 根据元素来源决定是原地更新还是重新 place。
            for elem, comp_type in elems_info:
                path = 'board'
                norm_changes = _normalize_changes(comp_type, elem.component_params or {}, changes)
                _log(f"[_tool_modify_component] will use board path for elem {elem.id[:8]} ({comp_type}), changes={norm_changes}")
                ok, msg = self._modify_board_then_sync(elem, norm_changes, position=position)
                _log(f"[_tool_modify_component] board path result for elem {elem.id[:8]}: ok={ok}, msg={msg}")
                results.append(f"{comp_type}({path}): {msg}")
        else:
            path = path_hint
            for elem, comp_type in elems_info:
                norm_changes = _normalize_changes(comp_type, elem.component_params or {}, changes)
                if path == 'board':
                    ok, msg = self._modify_board_then_sync(elem, norm_changes, position=position)
                elif path == 'bimbase':
                    ok, msg = self._replace_in_bimbase(elem, norm_changes)
                else:
                    ok, msg = False, f"未知路径 {path}"
                results.append(f"{comp_type}({path}): {msg}")

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

    @staticmethod
    def _apply_position_to_element(elem, position):
        """将 position（dict/list）应用到元素的几何属性上，保持高度不变。
        对 PolylineElement 等无 x/y 属性的元素会调用 translate 移动点集，并更新 pdf_anchor。"""
        if position is None:
            return
        if isinstance(position, dict):
            px = float(position.get('x', position.get('cx', 0)))
            py = float(position.get('y', position.get('cy', 0)))
            pz = float(position.get('z', position.get('z_bottom', 0)))
        elif isinstance(position, (list, tuple)) and len(position) >= 2:
            px = float(position[0])
            py = float(position[1])
            pz = float(position[2]) if len(position) >= 3 else 0.0
        else:
            return

        # 以 pdf_anchor 为优先参考点，没有则取 x/cx/x1
        old_x = float(getattr(elem, 'pdf_anchor_x',
                              getattr(elem, 'x',
                                      getattr(elem, 'cx',
                                              getattr(elem, 'x1', 0.0)))))
        old_y = float(getattr(elem, 'pdf_anchor_y',
                              getattr(elem, 'y',
                                      getattr(elem, 'cy',
                                              getattr(elem, 'y1', 0.0)))))
        old_z = float(getattr(elem, 'pdf_anchor_z', getattr(elem, 'z_start', 0.0)))
        dx = px - old_x
        dy = py - old_y
        dz = pz - old_z
        _log(f"[_apply_position_to_element] elem={elem.id[:8]} old=({old_x},{old_y},{old_z}) new=({px},{py},{pz}) delta=({dx},{dy},{dz})")

        # 优先使用 translate 移动 2D 几何（支持 PolylineElement / RectangleElement / CircleElement 等）
        if hasattr(elem, 'translate') and callable(elem.translate):
            try:
                elem.translate(dx, dy)
            except Exception:
                pass
        else:
            # 兜底：直接设置 x/cx/y/cy
            if hasattr(elem, 'x'):
                elem.x = px
            elif hasattr(elem, 'cx'):
                elem.cx = px
            if hasattr(elem, 'y'):
                elem.y = py
            elif hasattr(elem, 'cy'):
                elem.cy = py

        # 保持高度差，更新 z
        z_start = getattr(elem, 'z_start', old_z)
        z_end = getattr(elem, 'z_end', z_start)
        if hasattr(elem, 'z_start'):
            elem.z_start = pz
        if hasattr(elem, 'z_end'):
            elem.z_end = z_end + dz

        # 同步 PDF 锚点属性，供 BIMBase 同步使用
        for attr, val in (('pdf_anchor_x', px), ('pdf_anchor_y', py), ('pdf_anchor_z', pz)):
            if hasattr(elem, attr):
                setattr(elem, attr, val)

        # 同步到 component_params，确保 _make_component / 生成脚本能读取到新坐标
        if hasattr(elem, 'component_params') and elem.component_params is not None:
            try:
                elem.component_params['x'] = px
                elem.component_params['y'] = py
                elem.component_params['z_bottom'] = pz
            except Exception:
                pass

    def _resolve_target(self, target):
        """解析目标，返回元素列表"""
        if not target:
            return [e for e in getattr(self.board, 'elements', [])
                    if getattr(e, 'selected', False)]

        elems = getattr(self.board, 'elements', [])
        result = list(elems)

        # 通用"组件"关键词：优先处理当前面编辑的源组件，再取选中/最近操作的组件
        if target.get('component'):
            # 1) 面编辑模式下的源组件
            face_cid = getattr(self.board, '_face_component_id', None)
            if face_cid:
                source = next((e for e in elems
                               if e.id == face_cid and not getattr(e, 'face_info', {})), None)
                if source:
                    return [source]
            # 2) 当前选中的参数化组件（排除面元素）
            selected = [e for e in elems
                        if getattr(e, 'selected', False)
                        and getattr(e, 'component_type', '')
                        and not getattr(e, 'face_info', {})]
            if selected:
                return selected
            # 3) 任意参数化组件
            comps = [e for e in elems
                     if getattr(e, 'component_type', '') and not getattr(e, 'face_info', {})]
            if comps:
                return [comps[0]]
            return []

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

    def _modify_board_then_sync(self, elem, changes, position=None):
        """路径 A: 修改 board 元素参数，然后 sync 到 BIMBase。
        指定了 position 时，会强制重新放置（而不是原地更新已有实例），确保坐标生效。"""
        _log(f"[_modify_board_then_sync] start elem={elem.id[:8]} comp_type={elem.component_type} changes={changes} position={position}")
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

        # 复杂构件：重新生成源元素主视图，确保 2D 轮廓与参数一致
        if comp_type in ('引桥桥墩', '索缆锚锭') and hasattr(self.board, '_regenerate_source_front_view'):
            try:
                _log(f"[_modify_board_then_sync] regenerating front view for {comp_type}")
                self.board._regenerate_source_front_view(elem, comp_type, params)
                _log(f"[_modify_board_then_sync] front view regenerated")
            except Exception:
                pass

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
            _log(f"[_modify_board_then_sync] starting BIMBase sync for elem {elem.id[:8]}")
            sync = BIMBaseSync(self.board)
            # 若指定了新坐标，清除已有 instance 引用，避免 _sync_element 走原地 replace 而不移动
            if position is not None:
                info = sync.registry.get(elem.id)
                if info:
                    info['instance'] = None
                    _log(f"[_modify_board_then_sync] cleared existing instance registry for elem {elem.id[:8]}")
            _log(f"[_modify_board_then_sync] calling _sync_element for elem {elem.id[:8]}")
            sync_result = sync._sync_element(elem)
            _log(f"[_modify_board_then_sync] _sync_element returned {sync_result}")
            if sync_result:
                return True, "参数已更新并同步到 BIMBase"
            else:
                return True, "参数已更新，但同步到 BIMBase 失败（可能是首次同步）"
        except Exception as e:
            import traceback
            _log(f"[_modify_board_then_sync] sync exception: {e}\n{traceback.format_exc()}")
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

        # 重新 place 到 BIMBase（使用自动放置，按元素当前坐标）
        try:
            from bimbase_sync import BIMBaseSync, place_component_at
            sync = BIMBaseSync(self.board)
            comp, new_params, new_type = sync._make_component(elem)
            if comp is None:
                return False, "无法构建组件"
            x = float(getattr(elem, 'pdf_anchor_x',
                              getattr(elem, 'x', getattr(elem, 'cx', 0))))
            y = float(getattr(elem, 'pdf_anchor_y',
                              getattr(elem, 'y', getattr(elem, 'cy', 0))))
            z = float(getattr(elem, 'pdf_anchor_z', getattr(elem, 'z_start', 0)))
            _log(f"replace_in_bimbase placing {comp_type} at ({x},{y},{z}) pdf_anchor=({getattr(elem,'pdf_anchor_x',None)},{getattr(elem,'pdf_anchor_y',None)},{getattr(elem,'pdf_anchor_z',None)})")
            ok, pmsg = place_component_at(comp, x, y, z)
            if not ok:
                return False, f"自动放置失败: {pmsg}"
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
