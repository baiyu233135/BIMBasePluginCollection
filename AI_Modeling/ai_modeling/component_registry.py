# -*- coding: utf-8 -*-
"""
AI_Modeling 组件注册表
记录 AI 生成并放置到 BIMBase 中的组件元数据，支持跨会话持久化。
"""
import os
import sys
import json
import time
from datetime import datetime

_plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

_registry_file = os.path.join(_plugin_dir, 'component_registry.json')


def _log(msg):
    try:
        log_path = os.path.join(_plugin_dir, 'ai_modeling_debug.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            ts = datetime.now().strftime('%H:%M:%S')
            f.write(f"[{ts}] [registry] {msg}\n")
    except Exception:
        pass


class ComponentRegistry:
    """单例组件注册表"""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, registry_file=None):
        if self._initialized:
            return
        self._initialized = True
        self._registry_file = registry_file or _registry_file
        self._registry = {}
        # 延迟加载：首次调用 get/set 时再加载，避免模块导入时 BIMBase 上下文未就绪
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self.load()
            self._loaded = True

    def _key_str(self, key):
        """把 instance_key / entity_id 统一转成可哈希的字符串。
        对 BIMBase 实体 ID，同时保留 ModelId 和 ElementId，避免只用 ModelId 导致冲突。"""
        if key is None:
            return None
        if isinstance(key, (str, int, float)):
            return str(key)

        mid = None
        eid = None
        for attr in ('_ModelId', '_PClassId', 'ModelId', 'model_id'):
            try:
                mid = getattr(key, attr, None)
                if mid is not None:
                    break
            except Exception:
                continue
        # instance key 使用 _P3DInstanceId，entity id 使用 _ElementId
        for attr in ('_ElementId', 'ElementId', 'element_id', '_P3DInstanceId', 'P3DInstanceId', 'p3d_instance_id'):
            try:
                eid = getattr(key, attr, None)
                if eid is not None:
                    break
            except Exception:
                continue

        if mid is not None and eid is not None:
            return f"ModelId={mid};ElementId={eid}"
        if eid is not None:
            return f"ElementId={eid}"
        if mid is not None:
            return f"ModelId={mid}"
        return str(key)

    def _safe_json_value(self, value):
        """确保值可 JSON 序列化"""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool, list, tuple)):
            try:
                json.dumps(value)
                return value
            except (TypeError, ValueError):
                pass
        return str(value)

    def _record_to_serializable(self, record):
        """把记录转为可 JSON 序列化的字典"""
        return {
            'component_type': record.get('component_type', ''),
            'params': {k: self._safe_json_value(v) for k, v in record.get('params', {}).items()},
            'placement': {
                'x': float(record.get('placement', {}).get('x', 0)),
                'y': float(record.get('placement', {}).get('y', 0)),
                'z': float(record.get('placement', {}).get('z', 0)),
            },
            'entity_id': self._key_str(record.get('entity_id')),
            'created_at': record.get('created_at', ''),
        }

    def load(self):
        """从 JSON 文件加载注册表"""
        self._registry = {}
        if not os.path.exists(self._registry_file):
            _log(f"registry file not found: {self._registry_file}")
            return
        try:
            with open(self._registry_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                _log("registry file is not a dict, reset")
                return
            for key, record in data.items():
                if isinstance(record, dict):
                    self._registry[key] = {
                        'component_type': record.get('component_type', ''),
                        'params': dict(record.get('params', {})),
                        'placement': {
                            'x': float(record.get('placement', {}).get('x', 0)),
                            'y': float(record.get('placement', {}).get('y', 0)),
                            'z': float(record.get('placement', {}).get('z', 0)),
                        },
                        'entity_id': record.get('entity_id'),
                        'created_at': record.get('created_at', ''),
                    }
            _log(f"loaded {len(self._registry)} records")
        except Exception as e:
            _log(f"load registry failed: {e}")
            self._registry = {}

    def save(self):
        """保存注册表到 JSON 文件"""
        try:
            serializable = {}
            for key, record in self._registry.items():
                try:
                    serializable[self._key_str(key)] = self._record_to_serializable(record)
                except Exception as e:
                    _log(f"skip record {key}: {e}")
            with open(self._registry_file, 'w', encoding='utf-8') as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
            _log(f"saved {len(serializable)} records")
        except Exception as e:
            _log(f"save registry failed: {e}")

    def register(self, instance_key, component_type, params, placement, entity_id=None):
        """
        注册一个已放置的组件
        :param instance_key: BIMBase 实例 key（通常是 datakey）
        :param component_type: 组件类型，如 'cylinder'/'pier'
        :param params: 组件参数字典
        :param placement: {'x', 'y', 'z'} 世界坐标
        :param entity_id: 可选的 BIMBase entity id
        """
        self._ensure_loaded()
        key = self._key_str(instance_key)
        if key is None:
            _log("register skipped: instance_key is None")
            return
        record = {
            'component_type': str(component_type),
            'params': dict(params) if params else {},
            'placement': {
                'x': float(placement.get('x', 0)),
                'y': float(placement.get('y', 0)),
                'z': float(placement.get('z', 0)),
            },
            'entity_id': self._key_str(entity_id),
            'created_at': datetime.now().isoformat(),
        }
        self._registry[key] = record
        self.save()
        _log(f"registered {component_type} at {record['placement']}")

    def unregister(self, instance_key):
        """注销指定组件"""
        self._ensure_loaded()
        key = self._key_str(instance_key)
        if key and key in self._registry:
            del self._registry[key]
            self.save()
            _log(f"unregistered {key}")

    def get(self, instance_key):
        """根据 instance_key 获取记录"""
        self._ensure_loaded()
        key = self._key_str(instance_key)
        return self._registry.get(key)

    def get_by_entity_id(self, entity_id):
        """根据 entity_id 查找记录"""
        self._ensure_loaded()
        target = self._key_str(entity_id)
        if not target:
            return None
        for record in self._registry.values():
            if record.get('entity_id') == target:
                return record
        return None

    def get_by_component_type(self, component_type):
        """根据组件类型返回所有匹配记录"""
        self._ensure_loaded()
        result = []
        for key, record in self._registry.items():
            if record.get('component_type') == component_type:
                result.append((key, record))
        return result

    def all_records(self):
        """返回所有记录的副本"""
        self._ensure_loaded()
        return dict(self._registry)

    def clear(self):
        """清空注册表"""
        self._ensure_loaded()
        count = len(self._registry)
        self._registry = {}
        self.save()
        _log(f"cleared {count} records")
        return count

    def validate_and_update(self, get_all_keys_func=None, is_valid_func=None, bounds_func=None):
        """
        校验注册表与当前 BIMBase 场景的一致性
        - 删除已不存在的记录
        - 对仍存在的记录，尝试用 bounds_func 更新 placement
        """
        self._ensure_loaded()
        if not self._registry:
            return 0

        valid_keys = set()
        if get_all_keys_func is not None:
            try:
                all_keys = get_all_keys_func() or []
                valid_keys = {self._key_str(k) for k in all_keys}
            except Exception as e:
                _log(f"validate get_all_keys failed: {e}")

        removed = 0
        updated = 0
        new_registry = {}
        for key, record in self._registry.items():
            # 如果提供了 get_all_keys_func，但 key 不在场景中，则删除
            if valid_keys and key not in valid_keys:
                removed += 1
                continue

            # 尝试更新位置
            if bounds_func is not None and record.get('entity_id'):
                try:
                    bounds = bounds_func(record['entity_id'])
                    if bounds and len(bounds) == 6:
                        x_min, y_min, z_min, x_max, y_max, z_max = bounds
                        record['placement'] = {
                            'x': (x_min + x_max) / 2.0,
                            'y': (y_min + y_max) / 2.0,
                            'z': (z_min + z_max) / 2.0,
                        }
                        updated += 1
                except Exception as e:
                    _log(f"update bounds failed for {key}: {e}")

            new_registry[key] = record

        self._registry = new_registry
        if removed or updated:
            self.save()
        _log(f"validate done: removed={removed}, updated={updated}, remaining={len(self._registry)}")
        return removed + updated


# 全局访问入口
def get_registry():
    return ComponentRegistry()
