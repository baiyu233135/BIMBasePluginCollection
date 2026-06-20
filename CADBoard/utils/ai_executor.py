# -*- coding: utf-8 -*-
"""
AI指令执行引擎 - Phase 4

解析并执行AI返回的结构化指令，支持:
- modify: 修改元素参数
- delete: 删除元素
- create: 创建新元素
- transform: 平移/旋转/缩放
- sync: 同步到BIMBase
- face_edit: 面编辑操作
"""

import json
import re
import traceback

from utils.bimbase_agent import BIMBaseAgent
import bimbase_sync


class AICommandExecutor:
    """AI指令执行器"""

    def __init__(self, board):
        self.board = board
        self.last_result = None
        self.agent = BIMBaseAgent(board)
        self._last_touched = []  # 记录最近操作过的元素，用于命令链回退

    def execute(self, command_json):
        """
        执行单个AI指令
        command_json: dict，包含 action 和参数
        返回: (success: bool, message: str)
        """
        action = command_json.get('action', '')
        if not action:
            return False, "指令缺少action字段"

        handlers = {
            'modify': self._do_modify,
            'delete': self._do_delete,
            'create': self._do_create,
            'transform': self._do_transform,
            'sync': self._do_sync,
            'face_edit': self._do_face_edit,
            'set_property': self._do_set_property,
            'agent': self._do_agent,
        }

        handler = handlers.get(action)
        if not handler:
            return False, f"不支持的AI指令: {action}"

        try:
            return handler(command_json)
        except Exception as e:
            tb = traceback.format_exc()
            return False, f"执行{action}失败: {e}\n{tb}"

    def execute_batch(self, commands):
        """批量执行指令，返回结果列表"""
        results = []
        for cmd in commands:
            success, msg = self.execute(cmd)
            results.append((success, msg))
        return results

    def _do_modify(self, cmd):
        """修改元素参数，支持面元素自动反推"""
        target = cmd.get('target', {})
        changes = cmd.get('changes', {})
        if not changes:
            return False, "modify指令缺少changes参数"

        elems = self._resolve_target(target)
        if not elems:
            return False, f"未找到目标元素: {target}"

        # === 自动 Agent 路径：如果选中的是参数化组件（或面元素），且修改的是几何属性 ===
        # 先收集所有涉及的源组件元素（面元素→追溯到源组件）
        source_elems_for_agent = []
        for elem in elems:
            comp_type = getattr(elem, 'component_type', '')
            if not comp_type:
                continue
            if getattr(elem, 'face_info', {}):
                # 面元素：追溯到源组件
                cid = elem.face_info.get('component_id')
                source = next((e for e in self.board.elements
                               if e.id == cid and not getattr(e, 'face_info', {})), None)
                if source and source not in source_elems_for_agent:
                    source_elems_for_agent.append(source)
            else:
                # 源元素直接处理
                if elem not in source_elems_for_agent:
                    source_elems_for_agent.append(elem)

        # 调试日志
        import os
        try:
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ai_debug.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[AGENT_CHECK] elems={len(elems)} source_for_agent={len(source_elems_for_agent)}\n")
                for e in elems:
                    f.write(f"  elem={e.__class__.__name__} id={e.id[:8]} comp={getattr(e,'component_type','')} face={bool(getattr(e,'face_info',{}))}\n")
                for s in source_elems_for_agent:
                    f.write(f"  source={s.__class__.__name__} id={s.id[:8]} comp={s.component_type}\n")
        except Exception:
            pass

        if source_elems_for_agent:
            # 尝试将通用属性名映射为组件参数名
            mapped_changes = {}
            for elem in source_elems_for_agent:
                comp_type = elem.component_type
                for key, val in changes.items():
                    mk = self._map_param_key(comp_type, key)
                    if mk:
                        mapped_changes[mk] = float(val) if isinstance(val, (int, float, str)) else val
            try:
                log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ai_debug.log')
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(f"[AGENT_CHECK] mapped_changes={mapped_changes}\n")
            except Exception:
                pass
            if mapped_changes:
                # 走 Agent 的 modify_component 路径（自动 sync + 双路径决策）
                agent_target = {}
                if 'component_type' in target:
                    agent_target['component_type'] = target['component_type']
                elif 'index' in target:
                    agent_target['index'] = target['index']
                elif 'element_type' in target:
                    agent_target['index'] = 'selected'
                else:
                    agent_target['index'] = 'selected'
                return self.agent.execute_tool('modify_component', {
                    'target': agent_target,
                    'changes': mapped_changes,
                    'path': 'auto'
                })

        self.board._save_undo_state()
        self._last_touched = list(elems)  # 记录到命令链回退列表
        modified = 0
        face_elems_modified = []  # 记录被修改的面元素

        # 样式属性需要修改 elem.style 而不是 elem 本身
        style_props = {'color', 'line_width', 'line_type'}
        # AI可能用不同的属性名表示颜色
        color_aliases = {'颜色', 'color', '线条颜色', 'line_color', 'stroke', 'fill', '描边'}

        for elem in elems:
            elem_type_name = elem.__class__.__name__
            is_face = bool(getattr(elem, 'face_info', {}))
            comp_type = getattr(elem, 'component_type', '')
            for key, val in changes.items():
                try:
                    # 颜色属性名别名统一映射到 'color'
                    mapped_key = key
                    if key in color_aliases:
                        mapped_key = 'color'
                    # 样式属性特殊处理
                    if mapped_key in style_props:
                        if hasattr(elem, 'style') and hasattr(elem.style, mapped_key):
                            old_val = getattr(elem.style, mapped_key)
                            if mapped_key == 'color':
                                val = self._parse_color(val)
                            elif isinstance(old_val, (int, float)) and isinstance(val, str):
                                val = self._parse_relative(old_val, val)
                            setattr(elem.style, mapped_key, val)
                            modified += 1
                            continue

                    if hasattr(elem, key):
                        old_val = getattr(elem, key)
                        if isinstance(old_val, (int, float)):
                            # 支持相对修改: "+50", "-30", "*2"
                            if isinstance(val, str):
                                val = self._parse_relative(old_val, val)
                            setattr(elem, key, float(val))
                        else:
                            setattr(elem, key, val)
                        modified += 1

                        # 如果修改了面元素的几何属性，标记为已修改
                        if is_face and key in ('width', 'height', 'radius'):
                            face_elems_modified.append(elem)
                            elem._face_modified = True
                            from geometry.faces import FaceManager
                            elem._face_old_state = FaceManager.capture_element_state(elem)
                    else:
                        # 记录调试信息：属性不存在
                        import os
                        try:
                            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ai_debug.log')
                            with open(log_path, 'a', encoding='utf-8') as f:
                                f.write(f"[MODIFY_SKIP] elem={elem_type_name} id={elem.id[:8]} key={key} comp_type={comp_type} face={is_face}\n")
                        except Exception:
                            pass
                except Exception as e:
                    import os
                    try:
                        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ai_debug.log')
                        with open(log_path, 'a', encoding='utf-8') as f:
                            f.write(f"[MODIFY_ERR] elem={elem_type_name} id={elem.id[:8]} key={key} err={e}\n")
                    except Exception:
                        pass

        # 自动触发面参数反推（如果修改了面元素的几何属性）
        if face_elems_modified:
            # 获取 component_id（所有被修改的面应该属于同一个组件）
            component_id = face_elems_modified[0].face_info.get('component_id')
            if component_id:
                self.board._face_component_id = component_id
                try:
                    self.board._apply_face_changes()
                    return True, f"已修改 {len(elems)} 个元素（含 {len(face_elems_modified)} 个面），组件参数已自动反推更新"
                except Exception as e:
                    return True, f"已修改 {len(elems)} 个元素，面反推时出错: {e}"

        # 组件级参数修改（如"把三棱柱的h改成300"）
        if 'component_type' in target or 'component' in target:
            comp_type_filter = target.get('component_type', '')
            source_elems = []
            for e in self.board.elements:
                et = getattr(e, 'component_type', '')
                is_face = bool(getattr(e, 'face_info', {}))
                if et and not is_face:
                    if comp_type_filter and et == comp_type_filter:
                        source_elems.append(e)
                    elif not comp_type_filter and 'component' in target:
                        source_elems.append(e)
            
            if source_elems:
                elem = source_elems[0]
                comp_type_actual = elem.component_type
                params = dict(elem.component_params)
                
                # 参数名转换（通用属性名 → 组件专用参数名）
                param_changes = {}
                for key, val in changes.items():
                    mapped_key = key
                    if comp_type_actual == '直角三棱柱':
                        if key == 'height':
                            mapped_key = '高度'
                        elif key == 'width':
                            mapped_key = '直角边1'
                        elif key == 'depth':
                            mapped_key = '直角边2'
                    elif comp_type_actual == '圆柱':
                        if key == 'radius':
                            mapped_key = '半径'
                        elif key == 'height':
                            mapped_key = '高度'
                    elif comp_type_actual == '正方体':
                        if key in ('width', 'height', 'depth', 'size'):
                            mapped_key = '边长'
                    elif comp_type_actual == '长方体':
                        if key == 'width':
                            mapped_key = '长度'
                        elif key == 'depth':
                            mapped_key = '宽度'
                        elif key == 'height':
                            mapped_key = '高度'
                    elif comp_type_actual == 'SweepBoxComponent':
                        if key == 'width':
                            mapped_key = 'length'
                        elif key == 'height':
                            mapped_key = 'width'
                    param_changes[mapped_key] = float(val) if isinstance(val, (int, float, str)) else val
                
                for k, v in param_changes.items():
                    params[k] = v
                elem.component_params = params
                
                # 重新生成面元素
                if self.board._face_group:
                    try:
                        self.board._face_group.apply_params_and_regenerate(elem.id, params)
                        self.board.viewport.update()
                        return True, f"已更新 {comp_type_actual} 组件参数并重新生成面元素"
                    except Exception as e:
                        return True, f"已更新组件参数，重新生成面时出错: {e}"
                return True, f"已更新 {comp_type_actual} 组件参数"

        # 如果普通修改未生效，但存在参数化组件，回退到 Agent 路径处理歧义/映射
        if modified == 0 and source_elems_for_agent:
            agent_target = {'index': 'selected'}
            mapped_changes = {}
            for elem in source_elems_for_agent:
                comp_type = elem.component_type
                for key, val in changes.items():
                    mk = self._map_param_key(comp_type, key)
                    if mk:
                        mapped_changes[mk] = float(val) if isinstance(val, (int, float, str)) else val
            if mapped_changes:
                return self.agent.execute_tool('modify_component', {
                    'target': agent_target,
                    'changes': mapped_changes,
                    'path': 'auto'
                })

        self.board.viewport.update()
        if self.board.preview_3d_window:
            self.board.preview_3d_window.refresh_from_canvas(self.board.elements)
        changed_keys = list(changes.keys())
        return True, f"已修改 {len(elems)} 个元素，共 {modified} 个属性，键: {changed_keys}"

    def _parse_color(self, val):
        """将颜色名称或列表转换为RGB元组"""
        color_map = {
            '红色': (255, 0, 0), 'red': (255, 0, 0),
            '绿色': (0, 255, 0), 'green': (0, 255, 0),
            '蓝色': (0, 0, 255), 'blue': (0, 0, 255),
            '黄色': (255, 255, 0), 'yellow': (255, 255, 0),
            '黑色': (0, 0, 0), 'black': (0, 0, 0),
            '白色': (255, 255, 255), 'white': (255, 255, 255),
            '青色': (0, 255, 255), 'cyan': (0, 255, 255),
            '品红': (255, 0, 255), 'magenta': (255, 0, 255),
            '橙色': (255, 165, 0), 'orange': (255, 165, 0),
            '灰色': (128, 128, 128), 'gray': (128, 128, 128), 'grey': (128, 128, 128),
        }
        if isinstance(val, str):
            return color_map.get(val.strip(), (255, 0, 0))  # 未知颜色默认红
        if isinstance(val, (list, tuple)) and len(val) >= 3:
            return (int(val[0]), int(val[1]), int(val[2]))
        return (255, 0, 0)

    def _map_param_key(self, comp_type, key):
        """将通用属性名映射为组件专用参数名。可映射时返回映射后的名，否则返回 None"""
        key = key.lower()
        mapping = {
            '直角三棱柱': {
                'height': '高度', 'h': '高度',
                'width': '直角边1', 'a': '直角边1',
                'depth': '直角边2', 'b': '直角边2',
            },
            '圆柱': {
                'radius': '半径', 'r': '半径',
                'height': '高度', 'h': '高度',
            },
            '正方体': {
                'width': '边长', 'height': '边长', 'depth': '边长', 'size': '边长', 'a': '边长',
            },
            '长方体': {
                'width': '长度', 'length': '长度', 'l': '长度',
                'depth': '宽度', 'w': '宽度',
                'height': '高度', 'h': '高度',
            },
        }
        return mapping.get(comp_type, {}).get(key)

    def _do_delete(self, cmd):
        """删除元素"""
        target = cmd.get('target', {})
        elems = self._resolve_target(target)
        if not elems:
            return False, f"未找到要删除的元素: {target}"

        self.board._save_undo_state()
        for elem in elems:
            if elem in self.board.elements:
                self.board.elements.remove(elem)
        self._last_touched = []  # 删除后清空

        self.board.viewport.update()
        return True, f"已删除 {len(elems)} 个元素"

    def _request_manual_coordinate(self, defaults=(0, 0, 0)):
        """未指定坐标时弹出 X/Y/Z 输入对话框（优先使用自定义三字段对话框，QInputDialog 兜底）"""
        try:
            from PyQt5.QtWidgets import (
                QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QInputDialog
            )
            from PyQt5.QtCore import Qt
        except ImportError:
            from PyQt6.QtWidgets import (
                QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QInputDialog
            )
            from PyQt6.QtCore import Qt

        dx, dy, dz = [float(v) for v in defaults]

        # 方案A：自定义三字段对话框（BIMBase 内嵌环境中更稳定）
        try:
            dlg = QDialog(self.board)
            dlg.setWindowTitle("输入三维坐标")
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
            # PyQt5/6 兼容
            exec_method = getattr(dlg, 'exec_', getattr(dlg, 'exec', None))
            if exec_method and exec_method() == QDialog.Accepted:
                return (
                    float(x_edit.text()),
                    float(y_edit.text()),
                    float(z_edit.text()),
                )
        except Exception as e:
            try:
                import os
                log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ai_debug.log')
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(f"[COORD_DIALOG] custom dialog failed: {e}\n")
            except Exception:
                pass

        # 方案B：顺序 QInputDialog 兜底
        parent = self.board
        x, ok = QInputDialog.getDouble(parent, "输入坐标", "X:", dx, -1e9, 1e9, 2)
        if not ok:
            return None
        y, ok = QInputDialog.getDouble(parent, "输入坐标", "Y:", dy, -1e9, 1e9, 2)
        if not ok:
            return None
        z, ok = QInputDialog.getDouble(parent, "输入坐标", "Z:", dz, -1e9, 1e9, 2)
        if not ok:
            return None
        return (x, y, z)

    def _create_solid_board_element(self, elem_type, x, y, z, params):
        """根据实体类型创建画板占位元素（含组件参数），x,y 为几何中心"""
        from geometry.elements import CircleElement, RectangleElement, PolylineElement
        elem = None
        comp_params = {}
        if elem_type == '圆柱':
            r = float(params.get('radius', 50))
            h = float(params.get('height', 100))
            elem = CircleElement(x, y, r)
            comp_params = {'半径': r, '高度': h}
            elem.z_start = z
            elem.z_end = z + h
        elif elem_type == '正方体':
            a = float(params.get('size', params.get('width', 100)))
            elem = RectangleElement(x - a / 2, y - a / 2, a, a)
            comp_params = {'边长': a}
            elem.z_start = z
            elem.z_end = z + a
        elif elem_type == '长方体':
            L = float(params.get('length', 200))
            W = float(params.get('width', 100))
            H = float(params.get('height', 150))
            elem = RectangleElement(x - L / 2, y - W / 2, L, W)
            comp_params = {'长度': L, '宽度': W, '高度': H}
            elem.z_start = z
            elem.z_end = z + H
        elif elem_type == '球体':
            r = float(params.get('radius', 50))
            elem = CircleElement(x, y, r)
            comp_params = {'半径': r}
            elem.z_start = z
            elem.z_end = z + 2 * r
        elif elem_type == '直角三棱柱':
            a = float(params.get('width', params.get('a', 100)))
            b = float(params.get('depth', params.get('b', 80)))
            h = float(params.get('height', params.get('h', 150)))
            pts = [(x - a / 2, y - b / 2), (x + a / 2, y - b / 2), (x - a / 2, y + b / 2)]
            elem = PolylineElement(pts, closed=True)
            comp_params = {'直角边1': a, '直角边2': b, '高度': h}
            elem.z_start = z
            elem.z_end = z + h
        if elem is None:
            return None
        elem.x = x
        elem.y = y
        elem.component_type = elem_type
        elem.component_params = comp_params
        elem.is_3d = True
        return elem

    def _do_create_axis(self, cmd):
        """沿轴批量创建实体并同步到 BIMBase"""
        bimbase_sync._log(f"[_do_create_axis] called with cmd={cmd}")
        elem_type = cmd.get('element', '')
        axis = str(cmd.get('axis', cmd.get('direction', 'x'))).lower()
        if axis not in ('x', 'y', 'z'):
            axis = 'x'

        # 统一起点字段，兼容列表和字典格式
        raw_start = cmd.get('start') or cmd.get('center') or cmd.get('position') or cmd.get('from')
        start = [0.0, 0.0, 0.0]
        if raw_start is not None:
            try:
                if isinstance(raw_start, dict):
                    start = [
                        float(raw_start.get('x', 0.0)),
                        float(raw_start.get('y', 0.0)),
                        float(raw_start.get('z', 0.0)),
                    ]
                else:
                    start = [float(v) for v in raw_start]
            except Exception:
                start = [0.0, 0.0, 0.0]
        while len(start) < 3:
            start.append(0.0)

        spacing = float(cmd.get('spacing', cmd.get('distance', 20)))
        count = int(cmd.get('count', 1))
        params = dict(cmd.get('params', {}))

        dir_map = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}
        dx, dy, dz = dir_map.get(axis, (1, 0, 0))

        # 记录解析结果到调试日志
        try:
            import os
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ai_debug.log')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"[AXIS_CREATE] type={elem_type} axis={axis} start={start} "
                        f"spacing={spacing} count={count} params={params}\n")
        except Exception:
            pass

        self.board._save_undo_state()
        created = []
        placed = 0
        place_errors = []
        bimbase_sync._log(f"[_do_create_axis] loop count={count} start={start} spacing={spacing} axis={axis}")
        for i in range(count):
            px = start[0] + dx * i * spacing
            py = start[1] + dy * i * spacing
            pz = start[2] + dz * i * spacing
            bimbase_sync._log(f"[_do_create_axis] creating #{i} at ({px},{py},{pz})")
            elem = self._create_solid_board_element(elem_type, px, py, pz, params)
            if elem is None:
                continue
            self.board.apply_current_layer_style(elem)
            color_val = params.get('color')
            if color_val is not None:
                elem.style.color = self._parse_color(color_val)
            self.board.add_element(elem)
            if bimbase_sync.is_bimbase_available():
                ok, pmsg = bimbase_sync.place_element_to_bimbase(elem)
                if ok:
                    placed += 1
                else:
                    place_errors.append(f"#{i}@({px},{py},{pz}): {pmsg}")
            else:
                place_errors.append(f"#{i}@({px},{py},{pz}): pyp3d 未加载")
            created.append(elem)

        if created:
            for e in self.board.elements:
                e.selected = False
            created[-1].selected = True
            self._last_touched = created
            self.board.viewport.update()
            msg = f"已沿 {axis.upper()} 轴创建 {len(created)} 个 {elem_type}"
            if bimbase_sync.is_bimbase_available():
                msg += f"，成功放置 {placed} 个到 BIMBase"
                if place_errors:
                    unique_errors = []
                    for e in place_errors:
                        if e not in unique_errors:
                            unique_errors.append(e)
                    msg += f"；失败 {len(place_errors)} 个: {'; '.join(unique_errors[:3])}"
            return True, msg
        return False, "未能创建任何元素"

    def _do_create(self, cmd):
        """创建新元素 - 支持中英文类型名、参数别名、3D实体直接同步"""
        elem_type = cmd.get('element', '')
        params = dict(cmd.get('params', {}))

        # 调试日志：确认 _do_create 收到的命令内容
        try:
            bimbase_sync._log(f"[_do_create] elem_type={elem_type}, cmd={cmd}")
        except Exception:
            pass

        from geometry.elements import (
            LineElement, RectangleElement, CircleElement,
            ArcElement, PolylineElement,
            EllipseElement, PointElement
        )

        SOLID_TYPES = {'圆柱', '正方体', '长方体', '球体', '直角三棱柱'}

        # 沿轴批量布置（兼容 AI 返回的 direction 字段）
        # 某些 AI 会把 axis/count/spacing/position 放在 params 里
        axis = cmd.get('axis') or cmd.get('direction') or params.get('axis') or params.get('direction')
        has_axis = axis is not None
        try:
            bimbase_sync._log(f"[_do_create] has_axis={has_axis}, axis={axis}, cmd_axis={cmd.get('axis')}, params_axis={params.get('axis')}")
        except Exception:
            pass
        if has_axis:
            cmd['axis'] = axis
            if 'count' not in cmd and 'count' in params:
                cmd['count'] = params['count']
            if 'spacing' not in cmd and 'spacing' in params:
                cmd['spacing'] = params['spacing']
            if 'start' not in cmd and 'position' in params:
                cmd['position'] = params['position']
            if 'start' not in cmd and 'start_point' in params:
                cmd['start'] = params['start_point']
            if 'start' not in cmd and 'from' in params:
                cmd['from'] = params['from']
            bimbase_sync._log(f"[_do_create] routing to _do_create_axis, normalized cmd={cmd}")
            return self._do_create_axis(cmd)

        # 解析位置（兼容 AI 返回的多种字段：start_point/from/origin/point/center/x,y,z）
        def _extract_pos(params):
            for key in ('start_point', 'from', 'origin', 'point', 'position'):
                val = params.get(key)
                if val and isinstance(val, (list, tuple)) and len(val) >= 2:
                    return (
                        float(val[0]),
                        float(val[1]),
                        float(val[2]) if len(val) >= 3 else 0.0,
                    )
            center = params.get('center')
            if center and isinstance(center, (list, tuple)) and len(center) >= 2:
                return (
                    float(center[0]),
                    float(center[1]),
                    float(center[2]) if len(center) >= 3 else float(params.get('z', 0)),
                )
            if any(k in params for k in ('x', 'y', 'z', 'cx', 'cy')):
                return (
                    float(params.get('x', params.get('cx', 0))),
                    float(params.get('y', params.get('cy', 0))),
                    float(params.get('z', 0)),
                )
            return None

        pos = _extract_pos(params)
        if pos is not None:
            x, y, z = pos
        else:
            x = y = 0.0
            z = None

        # 3D 实体：只有完全没有指定位置时才弹出三轴坐标输入对话框
        if elem_type in SOLID_TYPES:
            if pos is None:
                coord = self._request_manual_coordinate(defaults=(x, y, 0))
                if coord is None:
                    return False, "用户取消了坐标输入"
                x, y, z = coord
                params['x'], params['y'], params['z'] = x, y, z

        elem = None
        try:
            if elem_type in ('circle', 'CircleElement', '圆'):
                elem = CircleElement(x, y, float(params.get('radius', 50)))
            elif elem_type in ('rectangle', 'RectangleElement', '矩形'):
                elem = RectangleElement(
                    x, y,
                    float(params.get('width', 100)), float(params.get('height', 80))
                )
            elif elem_type in ('line', 'LineElement', '直线'):
                elem = LineElement(
                    float(params.get('x1', x)), float(params.get('y1', y)),
                    float(params.get('x2', x + 100)), float(params.get('y2', y))
                )
            elif elem_type in ('arc', 'ArcElement', '圆弧'):
                elem = ArcElement(
                    x, y,
                    float(params.get('radius', 50)),
                    float(params.get('start_angle', 0)), float(params.get('end_angle', 90))
                )
            elif elem_type in ('point', 'PointElement', '点'):
                elem = PointElement(x, y)
            elif elem_type in ('polygon', 'PolygonElement', '多边形'):
                pts = params.get('points', [[x, y], [x + 100, y], [x + 100, y + 100]])
                elem = PolylineElement(pts, closed=True)
            elif elem_type in ('polyline', 'PolylineElement', '多段线'):
                pts = params.get('points', [[x, y], [x + 100, y], [x + 100, y + 100]])
                elem = PolylineElement(pts, closed=False)
            elif elem_type in ('ellipse', 'EllipseElement', '椭圆'):
                elem = EllipseElement(
                    x, y,
                    float(params.get('rx', 50)), float(params.get('ry', 30))
                )
            elif elem_type in SOLID_TYPES:
                elem = self._create_solid_board_element(elem_type, x, y, z, params)
        except Exception as e:
            return False, f"创建元素失败: {e}"

        if not elem:
            return False, f"不支持的元素类型: {elem_type}"

        self.board._save_undo_state()
        # 应用3D属性
        if elem_type not in SOLID_TYPES:
            elem.z_start = params.get('z_start', 0)
            elem.z_end = params.get('z_end', 0)
            elem.thickness = params.get('thickness', 0)
            elem.is_3d = params.get('is_3d', False)
            elem.height = params.get('height', 0)

        self.board.apply_current_layer_style(elem)
        # 处理颜色参数（覆盖图层默认颜色）
        color_val = params.get('color', None)
        if color_val is not None:
            rgb = self._parse_color(color_val)
            elem.style.color = rgb

        # 3D 实体直接同步到 BIMBase
        sync_tag = ''
        if elem_type in SOLID_TYPES and bimbase_sync.is_bimbase_available():
            ok, pmsg = bimbase_sync.place_element_to_bimbase(elem)
            if ok:
                sync_tag = '（已同步到BIMBase）'
            else:
                sync_tag = f'（BIMBase 放置失败: {pmsg}）'
        elif elem_type in SOLID_TYPES:
            sync_tag = '（pyp3d 未加载，未同步到BIMBase）'

        self.board.add_element(elem)
        for e in self.board.elements:
            e.selected = False
        elem.selected = True
        self._last_touched = [elem]
        self.board.viewport.update()
        return True, f"已创建 {elem_type} 并自动选中{sync_tag}"

    def _do_transform(self, cmd):
        """变换元素: 平移/旋转/缩放"""
        target = cmd.get('target', {})
        transform_type = cmd.get('transform_type', '')
        params = cmd.get('params', {})

        elems = self._resolve_target(target)
        if not elems:
            return False, f"未找到目标元素: {target}"
        self._last_touched = list(elems)  # 记录到命令链回退列表

        self.board._save_undo_state()
        for elem in elems:
            try:
                if transform_type == 'translate':
                    elem.translate(params.get('dx', 0), params.get('dy', 0))
                elif transform_type == 'rotate':
                    cx = params.get('cx', 0)
                    cy = params.get('cy', 0)
                    angle = params.get('angle', 0)
                    elem.rotate(cx, cy, angle)
                elif transform_type == 'scale':
                    cx = params.get('cx', 0)
                    cy = params.get('cy', 0)
                    factor = params.get('factor', 1.0)
                    elem.scale(cx, cy, factor)
                elif transform_type == 'mirror':
                    x1, y1 = params.get('x1', 0), params.get('y1', 0)
                    x2, y2 = params.get('x2', 100), params.get('y2', 0)
                    elem.mirror(x1, y1, x2, y2)
            except Exception as e:
                pass

        self.board.viewport.update()
        return True, f"已{transform_type} {len(elems)} 个元素"

    def _do_sync(self, cmd):
        """同步到BIMBase"""
        self.board._sync_to_bimbase()
        return True, "已触发同步到BIMBase"

    def _do_face_edit(self, cmd):
        """面编辑操作"""
        sub_action = cmd.get('sub_action', '')
        if sub_action == 'generate':
            self.board._generate_faces_for_selected()
            return True, "已触发面元素生成"
        elif sub_action == 'apply':
            self.board._apply_face_changes()
            return True, "已触发面修改应用"
        return False, f"不支持的面编辑操作: {sub_action}"

    def _do_set_property(self, cmd):
        """设置通用属性（z_start/z_end/is_3d等），支持颜色转换"""
        target = cmd.get('target', {})
        props = cmd.get('properties', {})
        elems = self._resolve_target(target)
        if not elems:
            return False, f"未找到目标元素: {target}"
        self._last_touched = list(elems)

        self.board._save_undo_state()
        changed_keys = []
        for elem in elems:
            for key, val in props.items():
                try:
                    # 颜色属性特殊处理
                    if key in ('color', '颜色', '线条颜色', 'line_color', 'stroke', 'fill', '描边'):
                        if hasattr(elem, 'style'):
                            elem.style.color = self._parse_color(val)
                            changed_keys.append('color')
                            continue
                    if hasattr(elem, key):
                        setattr(elem, key, val)
                        changed_keys.append(key)
                except Exception:
                    pass
        self.board.viewport.update()
        return True, f"已设置 {len(elems)} 个元素的属性: {changed_keys}"

    def _do_agent(self, cmd):
        """执行 Agent 工具调用"""
        tool = cmd.get('tool', '')
        params = cmd.get('params', {})
        if not tool:
            return False, "agent 指令缺少 tool 字段"
        return self.agent.execute_tool(tool, params)

    def _resolve_target(self, target):
        """解析目标，返回元素列表。兼容字符串简写形式。"""
        if not target:
            return []
        # AI可能返回字符串简写：target: "selected"/"all" → 转为字典
        if isinstance(target, str):
            target = {'index': target}

        # 通过index定位
        if 'index' in target:
            idx = target['index']
            if isinstance(idx, int) and 0 <= idx < len(self.board.elements):
                return [self.board.elements[idx]]
            elif idx == 'all':
                return list(self.board.elements)
            elif idx == 'selected':
                selected = [e for e in self.board.elements if getattr(e, 'selected', False)]
                if selected:
                    return selected
                # 命令链回退1: 最近操作的元素
                if self._last_touched:
                    return list(self._last_touched)
                # 命令链回退2: 画板中最后一个元素（最新创建的）
                if self.board.elements:
                    return [self.board.elements[-1]]
                return []

        # 通过id定位
        if 'id' in target:
            eid = target['id']
            for e in self.board.elements:
                if getattr(e, 'id', '') == eid:
                    return [e]
            return []

        # 通过类型过滤
        if 'element_type' in target:
            et = target['element_type']
            # 支持中文和英文类型名
            type_map = {
                'line': 'LineElement', '直线': 'LineElement',
                'rectangle': 'RectangleElement', '矩形': 'RectangleElement',
                'circle': 'CircleElement', '圆': 'CircleElement',
                'arc': 'ArcElement', '圆弧': 'ArcElement',
                'polygon': 'PolygonElement', '多边形': 'PolygonElement',
                'polyline': 'PolylineElement', '多段线': 'PolylineElement',
                'ellipse': 'EllipseElement', '椭圆': 'EllipseElement',
                'point': 'PointElement', '点': 'PointElement',
            }
            target_type = type_map.get(et, et)
            matched = [e for e in self.board.elements
                       if e.__class__.__name__ == target_type]
            # 如果有index限定，取第N个
            if 'index' in target:
                sub_idx = target['index']
                if isinstance(sub_idx, int) and 0 <= sub_idx < len(matched):
                    return [matched[sub_idx]]
                return []
            return matched

        # 通过面名称过滤（三视图修改）
        if 'face_name' in target:
            face_name = target['face_name']
            if face_name == 'all':
                return [e for e in self.board.elements
                        if getattr(e, 'face_info', {})]
            return [e for e in self.board.elements
                    if getattr(e, 'face_info', {}).get('face_name') == face_name]

        return []

    def _parse_relative(self, old_val, expr):
        """解析相对值表达式: '+50', '-30', '*2', '/2'"""
        expr = str(expr).strip()
        if expr.startswith('+'):
            return old_val + float(expr[1:])
        elif expr.startswith('-'):
            return old_val - float(expr[1:])
        elif expr.startswith('*'):
            return old_val * float(expr[1:])
        elif expr.startswith('/'):
            return old_val / float(expr[1:])
        return float(expr)


class AIResponseParser:
    """解析AI返回的响应，提取结构化指令"""

    @classmethod
    def parse(cls, text):
        """
        解析AI返回文本，提取JSON指令。
        返回: (commands_list, plain_text)
        """
        commands = []
        plain_parts = []

        # 查找JSON代码块
        json_pattern = r'```(?:json)?\s*([\s\S]*?)```'
        matches = list(re.finditer(json_pattern, text))

        last_end = 0
        for m in matches:
            # 代码块之前的文本作为plain text
            plain_parts.append(text[last_end:m.start()].strip())
            json_str = m.group(1).strip()
            try:
                data = json.loads(json_str)
                if isinstance(data, list):
                    commands.extend(data)
                elif isinstance(data, dict):
                    commands.append(data)
            except json.JSONDecodeError:
                plain_parts.append(f"[JSON解析失败]\n{json_str}")
            last_end = m.end()

        plain_parts.append(text[last_end:].strip())
        plain_text = '\n\n'.join(p for p in plain_parts if p)

        # 如果没有代码块，尝试直接解析整个文本为JSON
        if not commands and text.strip().startswith('{'):
            try:
                data = json.loads(text.strip())
                if isinstance(data, list):
                    commands = data
                elif isinstance(data, dict):
                    commands = [data]
            except json.JSONDecodeError:
                pass

        return commands, plain_text
