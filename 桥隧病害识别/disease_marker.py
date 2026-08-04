# -*- coding: utf-8 -*-
"""
桥梁病害标记模块 — 在BIMBase构件表面生成红色标记

通过创建独立的红色标记组件并放置到BIMBase中对应构件位置，
实现病害的可视化展示。标记信息持久化到JSON文件。
"""

import os
import sys
import json
import traceback
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# 尝试导入pyp3d
_pyp3d_ok = False
Component = Attr = Cube = translate = scale = place = None
try:
    from pyp3d import Component, Attr, Cube, translate, scale, place
    _pyp3d_ok = True
except ImportError:
    pass

# 尝试导入颜色设置函数（模块级别缓存，组件内部会重新导入）
_diffuse_fn = None
_Color_fn = None
try:
    from pyp3d import diffuse as _diffuse_fn
except ImportError:
    pass
if _diffuse_fn is None:
    try:
        from pyp3d import Color as _Color_fn
    except ImportError:
        pass

# 日志文件路径（本模块目录）
_LOG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "bridge_disease_debug.log"
)

def _log(msg: str):
    try:
        ts = datetime.now().strftime("%H:%M:%S")
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [MARKER] {msg}\n")
    except Exception:
        pass

# ★ 关键修复：模块级别定义组件类，BIMBase才能正确序列化
if _pyp3d_ok and Component is not None:
    class _DiseaseMarker(Component):
        def __init__(self, x=0, y=0, z=0, size=500):
            super().__init__()
            self['x'] = Attr(float(x), show=True, obvious=True)
            self['y'] = Attr(float(y), show=True, obvious=True)
            self['z'] = Attr(float(z), show=True, obvious=True)
            self['size'] = Attr(float(size), show=True, obvious=True)
            self['标记'] = Attr(None, show=True, obvious=True)
            self.replace()
        
        def replace(self):
            s = self['size']
            # 红色立方体标记（scale使Cube从原点中心放大，translate移动到指定位置）
            self['标记'] = translate(self['x'], self['y'], self['z']) * scale(s, s, s) * Cube()
    
    class _FaceMarker(Component):
        """红色面标记组件（薄片，可投影到构件表面）"""
        def __init__(self, x=0, y=0, z=0, width=200, height=200, thickness=2):
            super().__init__()
            self['x'] = Attr(float(x), show=True, obvious=True)
            self['y'] = Attr(float(y), show=True, obvious=True)
            self['z'] = Attr(float(z), show=True, obvious=True)
            self['width'] = Attr(float(width), show=True, obvious=True)
            self['height'] = Attr(float(height), show=True, obvious=True)
            self['thickness'] = Attr(float(thickness), show=True, obvious=True)
            self['面标记'] = Attr(None, show=True, obvious=True)
            self.replace()
        
        def replace(self):
            w = self['width']
            h = self['height']
            t = self['thickness']
            # 薄片：很薄的立方体，translate定位到中心
            self['面标记'] = translate(self['x'], self['y'], self['z']) * scale(w, h, t) * Cube()

    # ★ 病害阴影标记组件（带颜色的半透明薄片，贴在构件表面）
    class _DiseaseShadowMarker(Component):
        """
        病害阴影标记组件 — 带颜色的薄片，贴在构件表面模拟投影效果

        参数:
            x, y, z       : 薄片中心世界坐标
            width, height : 薄片面内尺寸
            thickness     : 薄片厚度（建议 1~2mm）
            color_r/g/b   : 颜色分量 0-255
            axis          : 薄片轴向 'xz'/'xy'/'yz'，决定 thickness 沿哪个世界轴
        """
        def __init__(self, x=0, y=0, z=0, width=50, height=50, thickness=2,
                     color_r=255, color_g=0, color_b=0, axis='xz'):
            super().__init__()
            self['x'] = Attr(float(x), show=True, obvious=True)
            self['y'] = Attr(float(y), show=True, obvious=True)
            self['z'] = Attr(float(z), show=True, obvious=True)
            self['width'] = Attr(float(width), show=True, obvious=True)
            self['height'] = Attr(float(height), show=True, obvious=True)
            self['thickness'] = Attr(float(thickness), show=True, obvious=True)
            self['color_r'] = Attr(int(color_r), show=True, obvious=True)
            self['color_g'] = Attr(int(color_g), show=True, obvious=True)
            self['color_b'] = Attr(int(color_b), show=True, obvious=True)
            self['axis'] = Attr(str(axis), show=True, obvious=True)
            self['阴影'] = Attr(None, show=True, obvious=True)
            self.replace()

        def replace(self):
            w = self['width']
            h = self['height']
            t = self['thickness']
            cr = max(0, min(255, self['color_r'])) / 255.0
            cg = max(0, min(255, self['color_g'])) / 255.0
            cb = max(0, min(255, self['color_b'])) / 255.0
            # pyp3d Component 没有 .get() 方法，直接通过字典方式访问
            try:
                axis = str(self['axis'])
            except Exception:
                axis = 'xz'

            # 根据面方向调整 scale，使薄片平贴在对应平面上
            if axis == 'xy':
                sx, sy, sz = w, h, t
            elif axis == 'yz':
                sx, sy, sz = t, w, h
            else:  # default 'xz'
                sx, sy, sz = w, t, h

            # 使用 pyp3d 内置的 .color() 方法设置 RGBA 颜色
            # alpha=0.35 表示 35% 不透明（65% 透明），形成阴影效果
            try:
                geom = (translate(self['x'], self['y'], self['z'])
                        * scale(sx, sy, sz)
                        * Cube().color(cr, cg, cb, 0.35))
            except Exception:
                # 如果 .color() 失败（旧版本 pyp3d），回退到无色
                geom = translate(self['x'], self['y'], self['z']) * scale(sx, sy, sz) * Cube()

            self['阴影'] = geom

    # ★ 病害纹理标记组件（带贴图的薄片）
    class _DiseaseTextureMarker(Component):
        """
        病害纹理标记组件 — 使用PNG纹理贴图贴在构件表面

        参数:
            x, y, z       : 薄片中心世界坐标
            width, height : 薄片面内尺寸
            thickness     : 薄片厚度（mm，建议 1~2）
            texture_path  : PNG纹理图片路径
            axis          : 薄片轴向 'xz'/'xy'/'yz'
        """
        def __init__(self, x=0, y=0, z=0, width=50, height=50, thickness=2,
                     texture_path='', axis='xz'):
            super().__init__()
            self['x'] = Attr(float(x), show=True, obvious=True)
            self['y'] = Attr(float(y), show=True, obvious=True)
            self['z'] = Attr(float(z), show=True, obvious=True)
            self['width'] = Attr(float(width), show=True, obvious=True)
            self['height'] = Attr(float(height), show=True, obvious=True)
            self['thickness'] = Attr(float(thickness), show=True, obvious=True)
            self['texture_path'] = Attr(str(texture_path), show=True, obvious=True)
            self['axis'] = Attr(str(axis), show=True, obvious=True)
            self['纹理'] = Attr(None, show=True, obvious=True)
            self.replace()

        def replace(self):
            w = self['width']
            h = self['height']
            t = self['thickness']
            tex = str(self['texture_path'])
            try:
                axis = str(self['axis'])
            except Exception:
                axis = 'xz'

            if axis == 'xy':
                sx, sy, sz = w, h, t
            elif axis == 'yz':
                sx, sy, sz = t, w, h
            else:
                sx, sy, sz = w, t, h

            geom = translate(self['x'], self['y'], self['z']) * scale(sx, sy, sz) * Cube()

            # 应用纹理材质
            if tex and os.path.exists(tex):
                try:
                    # 材质已在创建组件时预先创建，这里直接引用
                    geom = geom.material('DiseaseTex')
                except Exception:
                    pass

            self['纹理'] = geom

    # ★ 病害点云标记组件（大量彩色小点合并）
    class _DiseasePointCloudMarker(Component):
        """
        病害点云标记组件 — 大量彩色小立方体密集排列模拟点云投影

        参数:
            x, y, z    : 点云基准位置（面中心）
            points     : 点列表，每个点为 (local_u, local_v, 0, (r, g, b))
            point_size : 每个小点的尺寸(mm)
            face_plane : 面类型 'xz'/'xy'/'yz'
        """
        def __init__(self, x=0, y=0, z=0, points=None, point_size=3.0, face_plane='xz'):
            super().__init__()
            self['x'] = Attr(float(x), show=True, obvious=True)
            self['y'] = Attr(float(y), show=True, obvious=True)
            self['z'] = Attr(float(z), show=True, obvious=True)
            self['point_size'] = Attr(float(point_size), show=True, obvious=True)
            self['face_plane'] = Attr(str(face_plane), show=True, obvious=True)
            self['point_count'] = Attr(len(points) if points else 0, show=True, obvious=True)
            # 由于点数量可能很多，不将每个点存为Attr，而是序列化为字符串存一个Attr
            self['points_data'] = Attr(self._encode_points(points or []), show=True, obvious=True)
            self['点云'] = Attr(None, show=True, obvious=True)
            self.replace()

        @staticmethod
        def _encode_points(points):
            """将点列表编码为字符串: 'u,v,z,r,g,b;u,v,z,r,g,b;...'"""
            parts = []
            for p in points:
                if len(p) == 4:
                    u, v, z, (r, g, b) = p
                    parts.append(f"{u:.2f},{v:.2f},{z:.2f},{r},{g},{b}")
            return ';'.join(parts)

        @staticmethod
        def _decode_points(data):
            """将字符串解码为点列表"""
            points = []
            if not data:
                return points
            for part in data.split(';'):
                vals = part.split(',')
                if len(vals) == 6:
                    try:
                        points.append((float(vals[0]), float(vals[1]), float(vals[2]),
                                       (int(vals[3]), int(vals[4]), int(vals[5]))))
                    except ValueError:
                        pass
            return points

        def replace(self):
            ps = self['point_size']
            plane = str(self['face_plane'])
            points = self._decode_points(self['points_data'])

            if not points:
                self['点云'] = Cube()
                return

            try:
                from pyp3d import Combine, Cube, scale, translate
                half = ps / 2.0
                parts = []
                for u, v, z, (r, g, b) in points:
                    cr = max(0, min(255, r)) / 255.0
                    cg = max(0, min(255, g)) / 255.0
                    cb = max(0, min(255, b)) / 255.0
                    if plane == 'xy':
                        px, py, pz = u, v, z
                        sx, sy, sz = ps, ps, ps
                    elif plane == 'yz':
                        px, py, pz = z, u, v
                        sx, sy, sz = ps, ps, ps
                    else:  # xz
                        px, py, pz = u, z, v
                        sx, sy, sz = ps, ps, ps
                    small = translate(px, py, pz) * scale(sx, sy, sz) * Cube().color(cr, cg, cb, 0.7)
                    parts.append(small)

                if len(parts) == 1:
                    cloud = parts[0]
                else:
                    cloud = Combine(*parts)

                # 整体移动到基准位置
                cloud = translate(self['x'], self['y'], self['z']) * cloud
                self['点云'] = cloud
            except Exception as e:
                _log(f"点云生成失败: {e}")
                self['点云'] = Cube()

else:
    _DiseaseMarker = None
    _FaceMarker = None
    _DiseaseShadowMarker = None
    _DiseaseTextureMarker = None
    _DiseasePointCloudMarker = None

# 持久化文件路径（本模块目录）
RECORDS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "disease_records.json"
)


@dataclass
class MarkerRecord:
    """病害标记记录"""
    record_id: str           # 唯一编号
    photo_path: str          # 原始照片路径
    component_type: str      # 构件类型
    component_key: str       # BIMBase实例key（字符串化）
    disease_class: str       # 病害类型
    confidence: float        # 检测置信度
    bbox: Tuple[int, int, int, int]  # 照片上的bbox
    marker_x: float = 0.0    # 标记3D位置X
    marker_y: float = 0.0    # 标记3D位置Y
    marker_z: float = 0.0    # 标记3D位置Z
    created_at: str = ""     # 创建时间
    marked_image_path: str = ""   # 带框/标注的照片路径
    ai_diagnosis: str = ""        # AI 智能诊断结论
    ai_diagnosed: bool = False    # 是否已完成 AI 诊断
    severity: str = ""            # 严重程度（轻微/中等/严重/极严重）
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['bbox'] = list(d['bbox'])
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> "MarkerRecord":
        d = dict(d)
        d['bbox'] = tuple(d['bbox'])
        return cls(**d)


class DiseaseMarkerComponent:
    """红色病害标记组件（pyp3d Component）"""
    
    @staticmethod
    def create_component(x: float, y: float, z: float, size: float = 50.0):
        """创建红色立方体标记组件实例"""
        if not _pyp3d_ok or _DiseaseMarker is None:
            _log("pyp3d不可用或_DiseaseMarker未定义")
            return None
        
        try:
            comp = _DiseaseMarker(x, y, z, size)
            _log(f"立方体标记创建成功: pos=({x},{y},{z}), size={size}")
            return comp
        except Exception as e:
            _log(f"创建立方体标记失败: {e}\n{traceback.format_exc()}")
            return None
    
    @staticmethod
    def create_face_marker(x: float, y: float, z: float, width: float = 200, height: float = 200, thickness: float = 2):
        """创建红色面标记组件实例（薄片，可投影到构件表面）"""
        if not _pyp3d_ok or _FaceMarker is None:
            _log("pyp3d不可用或_FaceMarker未定义")
            return None
        
        try:
            comp = _FaceMarker(x, y, z, width, height, thickness)
            _log(f"面标记创建成功: pos=({x},{y},{z}), size={width}x{height}x{thickness}")
            return comp
        except Exception as e:
            _log(f"创建面标记失败: {e}\n{traceback.format_exc()}")
            return None

    @staticmethod
    def create_shadow_marker(x: float, y: float, z: float,
                             width: float = 50, height: float = 50, thickness: float = 2,
                             color_r: int = 255, color_g: int = 0, color_b: int = 0,
                             axis: str = 'xz'):
        """
        创建彩色病害阴影标记组件实例（带颜色薄片，贴在构件表面）。

        Args:
            x, y, z: 薄片中心世界坐标
            width, height: 薄片面内尺寸
            thickness: 薄片厚度（mm，建议 1~2）
            color_r, color_g, color_b: RGB 颜色分量 0-255
            axis: 薄片轴向 'xz'/'xy'/'yz'
        """
        if not _pyp3d_ok or _DiseaseShadowMarker is None:
            _log("pyp3d不可用或_DiseaseShadowMarker未定义")
            return None

        try:
            comp = _DiseaseShadowMarker(
                x, y, z, width, height, thickness,
                color_r, color_g, color_b, axis
            )
            _log(f"阴影标记创建成功: pos=({x:.1f},{y:.1f},{z:.1f}), "
                 f"size={width:.1f}x{height:.1f}x{thickness:.1f}, "
                 f"color=({color_r},{color_g},{color_b}), axis={axis}")
            return comp
        except Exception as e:
            _log(f"创建阴影标记失败: {e}\n{traceback.format_exc()}")
            return None

    @staticmethod
    def create_texture_marker(x: float, y: float, z: float,
                              width: float = 50, height: float = 50, thickness: float = 2,
                              texture_path: str = '', axis: str = 'xz'):
        """
        创建纹理贴图标记组件实例（PNG贴图薄片，贴在构件表面）。

        Args:
            x, y, z: 薄片中心世界坐标
            width, height: 薄片面内尺寸
            thickness: 薄片厚度（mm，建议 1~2）
            texture_path: PNG纹理图片路径
            axis: 薄片轴向 'xz'/'xy'/'yz'
        """
        if not _pyp3d_ok or _DiseaseTextureMarker is None:
            _log("pyp3d不可用或_DiseaseTextureMarker未定义")
            return None

        try:
            # 预创建材质（使用唯一名称避免冲突）
            mat_name = 'DiseaseTex'
            try:
                from pyp3d import create_material
                if os.path.exists(texture_path):
                    mat = create_material(
                        mat_name,
                        path=texture_path,
                        mapMode=0,
                        mapUnit=0,
                        uvScale=[1, 1],
                        wRotation=0
                    )
                    _log(f"材质创建成功: {mat_name}, mapFile={texture_path}")
                else:
                    _log(f"纹理文件不存在: {texture_path}")
            except Exception as e:
                _log(f"预创建材质失败: {e}")

            comp = _DiseaseTextureMarker(
                x, y, z, width, height, thickness,
                texture_path, axis
            )
            _log(f"纹理标记创建成功: pos=({x:.1f},{y:.1f},{z:.1f}), "
                 f"size={width:.1f}x{height:.1f}x{thickness:.1f}, "
                 f"tex={texture_path}, axis={axis}")
            return comp
        except Exception as e:
            _log(f"创建纹理标记失败: {e}\n{traceback.format_exc()}")
            return None

    @staticmethod
    def create_point_cloud_marker(x: float, y: float, z: float,
                                  points: list, point_size: float = 3.0,
                                  face_plane: str = 'xz'):
        """
        创建点云标记组件实例（大量彩色小立方体密集排列）。

        Args:
            x, y, z: 点云基准位置（面中心世界坐标）
            points: 点列表，每个点为 (local_u, local_v, 0, (r, g, b))
            point_size: 每个小点的尺寸(mm)
            face_plane: 面类型 'xz'/'xy'/'yz'
        """
        if not _pyp3d_ok or _DiseasePointCloudMarker is None:
            _log("pyp3d不可用或_DiseasePointCloudMarker未定义")
            return None

        try:
            comp = _DiseasePointCloudMarker(
                x, y, z, points, point_size, face_plane
            )
            _log(f"点云标记创建成功: pos=({x:.1f},{y:.1f},{z:.1f}), "
                 f"points={len(points) if points else 0}, size={point_size}")
            return comp
        except Exception as e:
            _log(f"创建点云标记失败: {e}\n{traceback.format_exc()}")
            return None


class DiseaseMarkerManager:
    """病害标记管理器"""

    def __init__(self):
        self.records: List[MarkerRecord] = []
        self._load_records()
    
    def _load_records(self):
        """从JSON加载历史记录"""
        if os.path.exists(RECORDS_PATH):
            try:
                with open(RECORDS_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.records = [MarkerRecord.from_dict(r) for r in data]
            except Exception as e:
                _log(f"加载记录失败: {e}")
                self.records = []
    
    def _save_records(self):
        """保存记录到JSON"""
        try:
            with open(RECORDS_PATH, 'w', encoding='utf-8') as f:
                json.dump([r.to_dict() for r in self.records], f, 
                         ensure_ascii=False, indent=2)
        except Exception as e:
            _log(f"保存记录失败: {e}")
    
    def place_marker(self, photo_path: str, component_type: str, 
                     component_key, disease_result, 
                     position_3d: Tuple[float, float, float]) -> Optional[MarkerRecord]:
        """
        在BIMBase中放置病害标记。
        
        Args:
            photo_path: 原始照片路径
            component_type: 构件类型名称
            component_key: BIMBase实例key
            disease_result: DiseaseResult对象
            position_3d: (x, y, z) 标记放置的3D坐标
        
        Returns:
            MarkerRecord对象，失败返回None
        """
        import uuid

        # component_key 可能是 P3DInstanceKey 对象，直接 str() 会触发
        # '_data' 属性访问异常。这里做安全转换。
        component_key_str = ""
        if component_key is not None:
            try:
                component_key_str = str(component_key)
            except Exception:
                try:
                    component_key_str = repr(component_key)
                except Exception:
                    component_key_str = "<unknown_key>"

        record = MarkerRecord(
            record_id=str(uuid.uuid4())[:8],
            photo_path=photo_path,
            component_type=component_type,
            component_key=component_key_str,
            disease_class=disease_result.class_name,
            confidence=disease_result.confidence,
            bbox=disease_result.bbox,
            marker_x=position_3d[0],
            marker_y=position_3d[1],
            marker_z=position_3d[2],
        )
        
        # 尝试在BIMBase中放置标记组件
        if _pyp3d_ok and place is not None:
            try:
                comp = DiseaseMarkerComponent.create_component(
                    position_3d[0], position_3d[1], position_3d[2], size=50.0
                )
                if comp is not None:
                    # 使用place()放置到BIMBase
                    _cadboard_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'CADBoard')
                    _cadboard_dir = os.path.normpath(_cadboard_dir)
                    if _cadboard_dir not in sys.path:
                        sys.path.insert(0, _cadboard_dir)
                    import bimbase_sync as _ref
                    original_argv0 = sys.argv[0]
                    sys.argv[0] = os.path.join(_cadboard_dir, 'bimbase_sync.py')
                    try:
                        place(comp)
                    finally:
                        sys.argv[0] = original_argv0
            except Exception as e:
                _log(f"BIMBase放置标记失败: {e}\n{traceback.format_exc()}")
        
        self.records.append(record)
        self._save_records()
        return record
    
    def place_marker_simple(self, photo_path: str, component_type: str,
                            component_key, disease_class: str, confidence: float,
                            position_3d: Tuple[float, float, float]) -> Optional[MarkerRecord]:
        """
        简化版：在BIMBase中放置病害标记（不依赖DiseaseResult对象）。
        
        Args:
            photo_path: 原始照片路径
            component_type: 构件类型名称
            component_key: BIMBase实例key
            disease_class: 病害类型（如"裂缝"）
            confidence: 置信度/严重程度数值
            position_3d: (x, y, z) 标记放置的3D坐标
        
        Returns:
            MarkerRecord对象，失败返回None
        """
        import uuid

        # component_key 可能是 P3DInstanceKey 对象，直接 str() 会触发
        # '_data' 属性访问异常。这里做安全转换。
        component_key_str = ""
        if component_key is not None:
            try:
                component_key_str = str(component_key)
            except Exception:
                try:
                    component_key_str = repr(component_key)
                except Exception:
                    component_key_str = "<unknown_key>"

        record = MarkerRecord(
            record_id=str(uuid.uuid4())[:8],
            photo_path=photo_path,
            component_type=component_type,
            component_key=component_key_str,
            disease_class=disease_class,
            confidence=confidence,
            bbox=(0, 0, 0, 0),
            marker_x=position_3d[0],
            marker_y=position_3d[1],
            marker_z=position_3d[2],
        )
        
        # 尝试在BIMBase中放置标记组件
        if _pyp3d_ok and place is not None:
            try:
                comp = DiseaseMarkerComponent.create_component(
                    position_3d[0], position_3d[1], position_3d[2], size=50.0
                )
                if comp is not None:
                    _cadboard_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'CADBoard')
                    _cadboard_dir = os.path.normpath(_cadboard_dir)
                    if _cadboard_dir not in sys.path:
                        sys.path.insert(0, _cadboard_dir)
                    import bimbase_sync as _ref
                    original_argv0 = sys.argv[0]
                    sys.argv[0] = os.path.join(_cadboard_dir, 'bimbase_sync.py')
                    try:
                        place(comp)
                    finally:
                        sys.argv[0] = original_argv0
            except Exception as e:
                _log(f"BIMBase放置标记失败: {e}\n{traceback.format_exc()}")
        
        self.records.append(record)
        self._save_records()
        return record
    
    def get_records_by_component(self, component_type: str) -> List[MarkerRecord]:
        """获取指定构件类型的所有病害记录"""
        return [r for r in self.records if r.component_type == component_type]
    
    def get_all_records(self) -> List[MarkerRecord]:
        """获取所有病害记录"""
        return list(self.records)
    
    def clear_records(self):
        """清空所有记录"""
        self.records.clear()
        self._save_records()
    
    def estimate_marker_position(self, component_params: dict) -> Tuple[float, float, float]:
        """
        根据构件参数估算标记放置位置（构件顶部中心）。
        
        Args:
            component_params: BIMBase构件参数字典
        
        Returns:
            (x, y, z) 3D坐标
        """
        if not component_params:
            return 0.0, 0.0, 0.0
        
        # 尝试提取位置参数
        x = 0.0
        y = 0.0
        z = 0.0
        
        # X/Y 位置
        for key in ['x', 'cx', 'x1']:
            if key in component_params:
                try:
                    x = float(component_params[key])
                    break
                except (ValueError, TypeError):
                    pass
        
        for key in ['y', 'cy', 'y1']:
            if key in component_params:
                try:
                    y = float(component_params[key])
                    break
                except (ValueError, TypeError):
                    pass
        
        # Z 高度（取顶部）
        for key in ['z_top', 'z2', 'z']:
            if key in component_params:
                try:
                    z = float(component_params[key])
                    break
                except (ValueError, TypeError):
                    pass
        
        # 如果没有z_top，尝试从高度推算
        if z == 0.0:
            for key in ['高度', '箱梁高度', '总高', '墩柱高', '盖梁高']:
                if key in component_params:
                    try:
                        z = float(component_params[key])
                        break
                    except (ValueError, TypeError):
                        pass
        
        return x, y, z + 100  # 在构件顶部上方100mm放置标记


def get_marker_manager() -> DiseaseMarkerManager:
    """获取全局唯一的DiseaseMarkerManager实例"""
    return DiseaseMarkerManager()
