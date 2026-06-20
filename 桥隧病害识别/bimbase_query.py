# -*- coding: utf-8 -*-
"""
BIMBase桥梁构件查询模块

扫描BIMBase中所有已放置的桥梁组件实例，按类型分组，
支持按编号规则自动分配照片到对应构件实例。
"""

import os
import sys
import traceback
from collections import defaultdict
from typing import Dict, List, Optional, Any

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# bimbase_sync 位于 CADBoard 目录，需要加入路径
_cadboard_dir = os.path.join(_current_dir, '..', 'CADBoard')
_cadboard_dir = os.path.normpath(_cadboard_dir)
if _cadboard_dir not in sys.path:
    sys.path.insert(0, _cadboard_dir)

# 尝试导入BIMBase实体查询API
# 注意：bimbase_sync在pyp3d不可用时可能抛出TypeError，需捕获所有异常
try:
    from bimbase_sync import (
        get_all_instancekey,
        get_noumKV_from_instancekey,
        get_noumenon_from_instancekey,
        entityid_isvaid,
    )
    _BIMBASE_API_OK = True
except Exception:
    # 直接从pyp3d导入（如果可用）
    try:
        from pyp3d import (
            get_all_instancekey,
            get_noumKV_from_instancekey,
            get_noumenon_from_instancekey,
            entityid_isvaid,
        )
        _BIMBASE_API_OK = True
    except Exception:
        get_all_instancekey = None
        get_noumKV_from_instancekey = None
        get_noumenon_from_instancekey = None
        entityid_isvaid = None
        _BIMBASE_API_OK = False


# ============================================================
# 19种桥梁组件类型及其参数特征（用于从BIMBase参数推断类型）
# ============================================================

COMPONENT_SIGNATURES = {
    # 基本几何体（组件测试）
    '直角三棱柱': {
        'required_keys': {'直角边1', '直角边2', '高度'},
        'optional_keys': set(),
    },
    '圆柱': {
        'required_keys': {'半径', '高度'},
        'optional_keys': set(),
    },
    '正方体': {
        'required_keys': {'边长'},
        'optional_keys': set(),
    },
    '长方体': {
        'required_keys': {'长度', '宽度', '高度'},
        'optional_keys': set(),
    },
    # 上部结构
    'T梁': {
        'required_keys': {'底板宽', '腹板宽', '总高'},
        'optional_keys': {'长', '底板高', '右翼缘宽', '左翼缘宽'},
    },
    '箱梁': {
        'required_keys': {'底板宽度', '箱梁高度', '腹板厚度'},
        'optional_keys': {'顶板厚度', '左翼缘长度', '右翼缘长度', '箱梁长'},
    },
    '主塔': {
        'required_keys': {'塔高', '塔底宽度'},
        'optional_keys': {'塔顶宽度', '壁厚'},
    },
    '工字钢混凝土组合梁': {
        'required_keys': {'主纵梁长度', '顶板宽', '梁高'},
        'optional_keys': {'横梁长', '小纵梁顶板宽', '混凝土板厚度'},
    },
    '斜拉索': {
        'required_keys': {'斜拉索数量', '半径', '竖向距离'},
        'optional_keys': {'横向距离', '竖向间距', '横向间距'},
    },
    '湿接缝': {
        'required_keys': {'接缝宽度', '接缝长度'},
        'optional_keys': {'厚度'},
    },
    '防撞护栏': {
        'required_keys': {'默认长度', '底宽', '顶宽'},
        'optional_keys': {'上端高', '下端高'},
    },
    '波形护栏': {
        'required_keys': {'长', '半径', '立柱高度'},
        'optional_keys': {'间距'},
    },
    # 下部结构
    '主塔群桩承台': {
        'required_keys': {'承台长', '承台宽', '承台高'},
        'optional_keys': {'桩数', '桩径'},
    },
    '异形盖梁': {
        'required_keys': {'盖梁长', '盖梁宽', '盖梁高'},
        'optional_keys': {'悬臂长'},
    },
    '扩大基础': {
        'required_keys': {'基础长', '基础宽', '基础高'},
        'optional_keys': {'埋深'},
    },
    '柱式桥台': {
        'required_keys': {'台身高', '台身宽'},
        'optional_keys': {'台帽宽', '台帽厚'},
    },
    '柱式桥墩': {
        'required_keys': {'墩柱高', '盖梁宽度', '桩基径'},
        'optional_keys': {'盖梁厚度', '盖梁高', '档墙长', '间距'},
    },
    '桩基承台': {
        'required_keys': {'承台宽', '承台长', '承台高'},
        'optional_keys': {'桩半径', '桩高', '单边桩基数量'},
    },
    '薄壁墩': {
        'required_keys': {'柱高度', '柱宽度', '柱厚度'},
        'optional_keys': {'承台高度', '承台长度', '桩基半径'},
    },
    '重力式桥台': {
        'required_keys': {'台身长', '台身高', '台身宽'},
        'optional_keys': {'基础厚', '基础宽'},
    },
    # 附属设施
    '人行道及护栏': {
        'required_keys': {'人行道宽', '栏杆高'},
        'optional_keys': {'人行道厚'},
    },
    '路面及交通标线': {
        'required_keys': {'路面宽', '路面长'},
        'optional_keys': {'标线宽'},
    },
}


def _normalize_key(key):
    """标准化参数键名，用于匹配"""
    if not isinstance(key, str):
        return ''
    return key.strip().replace(' ', '').replace('\u3000', '')


def infer_bridge_component_type(params: dict) -> str:
    """
    根据BIMBase组件参数字典，推断中文构件类型名称。
    
    策略：对每个已知构件类型，计算参数键名的匹配度：
    - required_keys 命中越多分数越高（权重10）
    - optional_keys 命中越多分数越高（权重1）
    - 放宽条件：不要求required全部命中，按总分排序取最高
    
    Args:
        params: BIMBase get_noumKV_from_instancekey 返回的字典
    
    Returns:
        构件类型名称（如"箱梁"），无法识别时返回空字符串
    """
    if not params or not isinstance(params, dict):
        return ''
    
    param_keys = set(_normalize_key(k) for k in params.keys() if isinstance(k, str))
    if not param_keys:
        return ''
    
    candidates = []
    for comp_name, sig in COMPONENT_SIGNATURES.items():
        req = set(_normalize_key(k) for k in sig['required_keys'])
        opt = set(_normalize_key(k) for k in sig['optional_keys'])
        
        # 计算匹配分数（放宽：部分匹配即可）
        req_match = len(req & param_keys)
        opt_match = len(opt & param_keys)
        total_score = req_match * 10 + opt_match
        
        if total_score > 0:
            candidates.append((comp_name, total_score, req_match, opt_match))
    
    if not candidates:
        return ''
    
    # 按总分降序，取最高分
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


class BridgeComponentQuery:
    """BIMBase桥梁构件查询器"""

    def __init__(self):
        self._groups: Dict[str, List[dict]] = {}
        self._last_scan_count = 0
        self._api_available = _BIMBASE_API_OK

    def is_api_available(self) -> bool:
        """BIMBase实体查询API是否可用"""
        return self._api_available

    def scan_components(self) -> Dict[str, List[dict]]:
        """
        扫描BIMBase中所有桥梁组件实例，按类型分组。
        
        Returns:
            {构件类型: [实例信息列表]}，每个实例信息包含 'key', 'params', 'index'
        """
        self._groups = defaultdict(list)
        
        if not self._api_available or get_all_instancekey is None:
            return dict(self._groups)
        
        try:
            keys = get_all_instancekey()
            if not keys:
                return dict(self._groups)
            
            # 限制扫描数量，避免太慢
            MAX_SCAN = 500
            scanned = 0
            
            for k in keys:
                if scanned >= MAX_SCAN:
                    break
                scanned += 1
                
                try:
                    params = get_noumKV_from_instancekey(k)
                    comp_type = infer_bridge_component_type(params)
                    if comp_type:
                        self._groups[comp_type].append({
                            'key': k,
                            'params': params,
                            'index': len(self._groups[comp_type]) + 1,
                        })
                except Exception:
                    pass
            
            # 每组按key字符串排序，保证编号稳定
            for comp_type in self._groups:
                self._groups[comp_type].sort(key=lambda x: str(x['key']))
                # 重新编号
                for i, item in enumerate(self._groups[comp_type], 1):
                    item['index'] = i
            
            self._last_scan_count = scanned
            
        except Exception as e:
            # 静默处理，避免pythonw.exe编码问题
            pass
        
        return dict(self._groups)
    
    def get_component_types(self) -> List[str]:
        """返回当前扫描到的所有构件类型列表"""
        return sorted(self._groups.keys())
    
    def get_instances_by_type(self, comp_type: str) -> List[dict]:
        """获取指定类型的所有实例"""
        return self._groups.get(comp_type, [])
    
    def auto_assign(self, comp_type: str, used_indices: set = None) -> Optional[dict]:
        """
        按编号顺序自动分配一个未使用的实例。
        
        Args:
            comp_type: 构件类型名称
            used_indices: 已使用的实例索引集合（避免重复分配）
        
        Returns:
            分配到的实例信息字典，或None（该类型无实例或全部已分配）
        """
        if used_indices is None:
            used_indices = set()
        
        instances = self._groups.get(comp_type, [])
        for inst in instances:
            idx = inst.get('index', 0)
            if idx not in used_indices:
                return inst
        return None
    
    def get_assignment_preview(self) -> str:
        """获取扫描结果的预览文本（用于UI显示）"""
        lines = []
        lines.append(f"扫描到 {self._last_scan_count} 个BIMBase实例")
        lines.append(f"识别出 {len(self._groups)} 种桥梁构件类型:")
        for comp_type in sorted(self._groups.keys()):
            count = len(self._groups[comp_type])
            lines.append(f"  • {comp_type}: {count} 个实例")
        return "\n".join(lines)


# 全局单例
_query_instance: Optional[BridgeComponentQuery] = None

def get_component_query() -> BridgeComponentQuery:
    """获取全局唯一的BridgeComponentQuery实例"""
    global _query_instance
    if _query_instance is None:
        _query_instance = BridgeComponentQuery()
    return _query_instance
