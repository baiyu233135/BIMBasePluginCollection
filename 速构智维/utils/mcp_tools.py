# -*- coding: utf-8 -*-
"""
MCP (Model Context Protocol) 工具注册表 —— P2 Enhancement

为未来支持MCP协议的AI模型提供本地工具暴露能力。
当前作为预留架构，注册CADBoard的核心操作函数，
供将来本地LLM或MCP客户端调用。
"""

import json
from typing import Dict, Callable, Any, List


class MCPTool:
    """单个MCP工具定义"""

    def __init__(self, name: str, description: str, parameters: dict, handler: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema 格式
        self.handler = handler

    def to_dict(self):
        """转为MCP工具描述字典"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def call(self, **kwargs):
        """调用工具"""
        return self.handler(**kwargs)


class MCPToolRegistry:
    """MCP工具注册表 —— 管理所有可用的本地工具"""

    def __init__(self, board=None):
        self.board = board
        self._tools: Dict[str, MCPTool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """注册CADBoard默认工具集"""
        self.register(
            name="draw_element",
            description="在画板上绘制几何元素（圆、矩形、直线等）",
            parameters={
                "type": "object",
                "properties": {
                    "element_type": {"type": "string", "enum": ["circle", "rectangle", "line", "arc", "point"]},
                    "x": {"type": "number", "description": "X坐标"},
                    "y": {"type": "number", "description": "Y坐标"},
                    "radius": {"type": "number", "description": "圆半径"},
                    "width": {"type": "number", "description": "宽度"},
                    "height": {"type": "number", "description": "高度"},
                },
                "required": ["element_type", "x", "y"],
            },
            handler=self._handle_draw,
        )
        self.register(
            name="modify_element",
            description="修改选中元素的属性",
            parameters={
                "type": "object",
                "properties": {
                    "property": {"type": "string", "description": "属性名如width/height/radius"},
                    "value": {"type": "number", "description": "新值"},
                },
                "required": ["property", "value"],
            },
            handler=self._handle_modify,
        )
        self.register(
            name="delete_selected",
            description="删除所有选中的元素",
            parameters={"type": "object", "properties": {}},
            handler=self._handle_delete,
        )
        self.register(
            name="sync_to_bimbase",
            description="将当前画板内容同步到BIMBase",
            parameters={"type": "object", "properties": {}},
            handler=self._handle_sync,
        )
        self.register(
            name="generate_faces",
            description="为选中的参数化组件生成面元素",
            parameters={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["三视图", "完整", "智能"], "description": "面生成模式"},
                },
            },
            handler=self._handle_generate_faces,
        )
        self.register(
            name="query_state",
            description="查询当前画板状态（元素列表、选中项等）",
            parameters={"type": "object", "properties": {}},
            handler=self._handle_query_state,
        )
        self.register(
            name="exit_face_edit",
            description="退出面编辑模式",
            parameters={"type": "object", "properties": {}},
            handler=self._handle_exit_face_edit,
        )

    def register(self, name: str, description: str, parameters: dict, handler: Callable):
        """注册新工具"""
        self._tools[name] = MCPTool(name, description, parameters, handler)

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """获取指定工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[dict]:
        """列出所有可用工具"""
        return [t.to_dict() for t in self._tools.values()]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """调用指定工具，返回标准MCP结果格式"""
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"未知工具: {name}"}
        try:
            result = tool.call(**arguments)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    # ========== 默认工具处理器 ==========

    def _handle_draw(self, element_type, x, y, radius=50, width=100, height=80, **kwargs):
        if not self.board:
            return "画板未初始化"
        from geometry.elements import CircleElement, RectangleElement, LineElement, ArcElement, PointElement
        elem = None
        if element_type == 'circle':
            elem = CircleElement(float(x), float(y), float(radius))
        elif element_type == 'rectangle':
            elem = RectangleElement(float(x), float(y), float(width), float(height))
        elif element_type == 'line':
            elem = LineElement(float(x), float(y), float(x) + float(width), float(y))
        elif element_type == 'arc':
            elem = ArcElement(float(x), float(y), float(radius), 0, 90)
        elif element_type == 'point':
            elem = PointElement(float(x), float(y))
        if elem:
            self.board.apply_current_layer_style(elem)
            self.board.add_element(elem)
            self.board.viewport.update()
            return f"已绘制 {element_type}"
        return "未知元素类型"

    def _handle_modify(self, property, value, **kwargs):
        if not self.board:
            return "画板未初始化"
        selected = [e for e in self.board.elements if getattr(e, 'selected', False)]
        if not selected:
            return "没有选中元素"
        for elem in selected:
            if hasattr(elem, property):
                try:
                    setattr(elem, property, float(value))
                except Exception:
                    pass
        self.board.viewport.update()
        return f"已修改 {len(selected)} 个元素的 {property}"

    def _handle_delete(self, **kwargs):
        if not self.board:
            return "画板未初始化"
        selected = [e for e in self.board.elements if getattr(e, 'selected', False)]
        for e in selected:
            if e in self.board.elements:
                self.board.elements.remove(e)
        self.board.viewport.update()
        return f"已删除 {len(selected)} 个元素"

    def _handle_sync(self, **kwargs):
        if not self.board:
            return "画板未初始化"
        if hasattr(self.board, '_sync_to_bimbase'):
            self.board._sync_to_bimbase()
            return "已触发同步"
        return "画板不支持同步"

    def _handle_generate_faces(self, mode="三视图", **kwargs):
        if not self.board:
            return "画板未初始化"
        if hasattr(self.board, '_generate_faces_for_selected'):
            self.board._generate_faces_for_selected()
            return f"已生成面元素（模式: {mode}）"
        return "画板不支持面生成"

    def _handle_query_state(self, **kwargs):
        if not self.board:
            return {"error": "画板未初始化"}
        total = len(self.board.elements)
        selected = [e for e in self.board.elements if getattr(e, 'selected', False)]
        comp_types = {}
        for e in self.board.elements:
            ct = getattr(e, 'component_type', '')
            if ct:
                comp_types[ct] = comp_types.get(ct, 0) + 1
        return {
            "total_elements": total,
            "selected_count": len(selected),
            "component_types": comp_types,
            "face_edit_mode": getattr(self.board, '_face_edit_mode', False),
        }

    def _handle_exit_face_edit(self, **kwargs):
        if not self.board:
            return "画板未初始化"
        if hasattr(self.board, '_exit_face_edit_mode'):
            self.board._exit_face_edit_mode()
            return "已退出面编辑模式"
        return "画板不支持面编辑"


def get_mcp_registry(board=None):
    """获取全局MCP工具注册表实例"""
    return MCPToolRegistry(board)
