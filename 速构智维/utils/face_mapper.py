# -*- coding: utf-8 -*-
"""
面映射引擎 - Phase 3

负责:
1. 追踪面元素编辑前后的状态变化
2. 根据变化反推组件参数
3. 批量重新生成同一组件的所有面元素
4. 与BIMBase同步联动
"""

from geometry.faces import FaceManager


class FaceEditSession:
    """
    面编辑会话 - 追踪一组面元素的编辑过程
    
    使用方式:
    1. session = FaceEditSession(board)
    2. session.start_edit(component_id)  # 记录所有面元素的初始状态
    3. 用户在画板上修改面元素
    4. session.commit_edit()  # 检测变化 → 更新组件参数 → 重新生成面元素
    """

    def __init__(self, board):
        self.board = board
        self.component_id = None
        self.original_states = {}  # element_id -> state_dict
        self.component_type = None
        self.component_params = None
        self.face_elements = []  # 当前组件的所有面元素

    def start_edit(self, component_id):
        """开始编辑一个组件的面"""
        self.component_id = component_id
        self.original_states.clear()
        self.face_elements.clear()

        # 找出所有属于该组件的面元素
        for elem in self.board.elements:
            if getattr(elem, 'face_info', {}).get('component_id') == component_id:
                self.face_elements.append(elem)
                self.original_states[elem.id] = FaceManager.capture_element_state(elem)
                self.component_type = elem.component_type
                self.component_params = dict(elem.component_params)

        return len(self.face_elements)

    def commit_edit(self):
        """
        提交编辑：检测变化 → 更新组件参数 → 重新生成面元素
        返回: (updated_params, new_face_elements)
        """
        if not self.component_id or not self.component_type:
            return None, []

        # 1. 检测哪些面元素发生了变化
        changed_faces = []
        for elem in self.face_elements:
            old_state = self.original_states.get(elem.id)
            if not old_state:
                continue
            new_state = FaceManager.capture_element_state(elem)
            if self._state_changed(old_state, new_state):
                changed_faces.append((elem, old_state, new_state))

        if not changed_faces:
            return None, []

        # 2. 逐个应用变化到组件参数
        new_params = dict(self.component_params)
        for elem, old_state, _ in changed_faces:
            face_name = elem.face_info.get('face_name', '')
            new_params = FaceManager.update_params_from_face(
                self.component_type, face_name, elem, old_state, new_params
            )

        # 3. 重新生成所有面元素
        new_faces = FaceManager.generate_all_faces(
            self.component_type, new_params, self.component_id
        )

        return new_params, new_faces

    def _state_changed(self, old_state, new_state):
        """对比两个状态是否不同"""
        if set(old_state.keys()) != set(new_state.keys()):
            return True
        for key in old_state:
            old_val = old_state[key]
            new_val = new_state[key]
            if isinstance(old_val, (list, tuple)):
                if len(old_val) != len(new_val):
                    return True
                for a, b in zip(old_val, new_val):
                    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
                        if any(abs(x - y) > 0.001 for x, y in zip(a, b)):
                            return True
                    elif abs(a - b) > 0.001:
                        return True
            elif isinstance(old_val, float):
                if abs(old_val - new_val) > 0.001:
                    return True
            else:
                if old_val != new_val:
                    return True
        return False


class ComponentFaceGroup:
    """
    组件面组 - 管理一个组件的所有面元素
    
    提供便捷方法:
    - 根据选中元素自动识别所属组件
    - 过滤显示特定面
    - 批量更新面元素
    """

    def __init__(self, board):
        self.board = board

    def get_component_ids(self):
        """获取画板中所有有面关联的组件ID"""
        ids = set()
        for elem in self.board.elements:
            cid = getattr(elem, 'face_info', {}).get('component_id')
            if cid:
                ids.add(cid)
        return sorted(ids)

    def get_elements_by_component(self, component_id):
        """获取指定组件的所有面元素"""
        return [e for e in self.board.elements
                if getattr(e, 'face_info', {}).get('component_id') == component_id]

    def get_elements_by_face(self, component_id, face_name):
        """获取指定组件的指定面元素"""
        return [e for e in self.board.elements
                if getattr(e, 'face_info', {}).get('component_id') == component_id
                and getattr(e, 'face_info', {}).get('face_name') == face_name]

    def get_component_info(self, component_id):
        """获取组件的基本信息"""
        elems = self.get_elements_by_component(component_id)
        if not elems:
            return None
        first = elems[0]
        return {
            'component_id': component_id,
            'component_type': first.component_type,
            'component_params': first.component_params,
            'face_count': len(elems),
            'faces': list(set(getattr(e, 'face_info', {}).get('face_name', '') for e in elems)),
        }

    def replace_faces(self, component_id, new_faces):
        """
        用新生成的面元素替换旧的面元素
        new_faces: {face_name: element}
        """
        # 删除旧的面元素
        old_ids = {e.id for e in self.board.elements
                   if getattr(e, 'face_info', {}).get('component_id') == component_id}
        self.board.elements = [e for e in self.board.elements if e.id not in old_ids]

        # 不恢复原始源元素的可见性——调用方（生成面/重新生成面）
        # 通常希望在替换面后保持源元素隐藏，避免与面元素重叠。
        # 如需显示源元素，调用方应自行设置 e.visible = True。

        # 添加新的面元素
        for face_name, elem in new_faces.items():
            elem.face_info['component_id'] = component_id
            self.board.add_element(elem)

    def generate_faces_for_element(self, source_elem, mode=None):
        """
        为单个源元素生成其组件的所有面元素。
        源元素必须已经有 component_type 和 component_params。
        mode: '三视图'|'完整'|'智能'，None 时从 component_params 的 _face_mode 读取，默认 '三视图'
        返回: {face_name: element} 或 None
        """
        if not source_elem.component_type:
            return None
        params = dict(source_elem.component_params)
        if not params:
            return None
        if mode is None:
            mode = params.get('_face_mode', '三视图')
        component_id = source_elem.id
        faces = FaceManager.generate_all_faces(
            source_elem.component_type, params, component_id, mode=mode
        )
        return faces

    def apply_params_and_regenerate(self, component_id, new_params, mode=None):
        """
        应用新参数并重新生成所有面元素
        mode: '三视图' 或 '完整'，None 时从 new_params 的 _face_mode 读取
        """
        elems = self.get_elements_by_component(component_id)
        if not elems:
            return False
        component_type = elems[0].component_type
        if mode is None:
            mode = new_params.get('_face_mode', '三视图')

        # 更新所有面元素的 component_params
        for e in elems:
            e.component_params = dict(new_params)

        # 重新生成面元素
        new_faces = FaceManager.generate_all_faces(
            component_type, new_params, component_id, mode=mode
        )
        self.replace_faces(component_id, new_faces)

        # 确保源元素保持隐藏，避免与新生成的面元素重叠
        for e in self.board.elements:
            if e.id == component_id:
                e.visible = False
                break
        return True
