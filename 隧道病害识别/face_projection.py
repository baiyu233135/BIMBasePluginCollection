# -*- coding: utf-8 -*-
"""
面投影引擎（隧道版）— 将病害识别结果投影到隧道构件表面

根据构件类型和参数，计算指定面的3D坐标，
并在面上生成带颜色的半透明阴影标记。

隧道面几何依据：组件成品/隧道.py 的横断面体系（XZ 断面沿 Y 拉伸，洞口朝 ±Y）：
- 内轮廓拱圈：起拱线 (±W/2, 0) 经拱顶 (0, H) 的三点圆弧（XZ 截面）
- 仰拱：起拱线 (±W/2, 0) 经拱底 (0, -h) 的三点圆弧（XZ 截面）
- 路面：顶面 z=40，宽 W-2*x1（x1=1000 为组件内硬编码路缘带宽度）
- 检修道：端头顶面 z=h1=H/5000*200，内侧面 x=±(W/2-x1)
参数键名：隧道净宽 W、拱仰厚度 H、二次衬砌厚度 w、底部高度 h、隧道长度 L
"""

import math
import os
import random
import tempfile
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass

try:
    from PIL import Image, ImageDraw
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# ============================================================
# 病害颜色映射（隧道版统一配色，照片框/烘焙图/投影点云/报告共用）：
# 裂缝→红、渗水→蓝、剥落→橙、其他→灰，未知类型绿色兜底
# ============================================================

DISEASE_COLOR_MAP = {
    "裂缝": (255, 0, 0),       # 红
    "渗水": (0, 0, 255),       # 蓝
    "剥落": (255, 165, 0),     # 橙
    "其他": (128, 128, 128),   # 灰
}

DISEASE_CLASSES = list(DISEASE_COLOR_MAP.keys())

# 未知病害类型的兜底颜色：绿
_FALLBACK_COLOR = (0, 255, 0)

# 各隧道构件类型可用的投影面清单（供 UI 下拉选择）
FACE_REGISTRY = {
    # 通用基本几何体（保留，便于兜底测试）
    '长方体': ['front', 'top', 'left'],
    '正方体': ['front', 'top'],
    '圆柱': ['front', 'side'],
    '直角三棱柱': ['side_a', 'side_b', 'hypotenuse'],
    # 隧道构件（与 bimbase_query.COMPONENT_SIGNATURES 的构件名一致）
    '衬砌': ['拱圈内壁', '仰拱内壁'],
    '路面': ['顶面'],
    '检修道': ['左检修道顶面', '右检修道顶面', '左检修道内侧面', '右检修道内侧面'],
    '排水': ['沟底面'],
    '洞门': ['正面'],
}


def get_available_faces(component_type: str) -> List[str]:
    """获取指定构件类型可投影的面名称列表"""
    return list(FACE_REGISTRY.get(component_type, []))


def photo_bbox_to_shadow(face: "FaceInfo", bbox: Tuple[float, float, float, float],
                         photo_w: int, photo_h: int, disease_type: str) -> "ShadowRegion":
    """
    将照片上的病害 bbox 按“等比铺满整面”映射为面上的阴影区域。

    假设照片取景范围≈目标面：照片 X → 面 U 方向，照片 Y（向下）→ 面 V 方向（向上取反）。

    Args:
        face: 目标面几何信息
        bbox: 照片上的病害框 (x1, y1, x2, y2)，像素
        photo_w, photo_h: 照片像素尺寸
        disease_type: 病害类型（决定颜色，未知类型用绿色兜底）

    Returns:
        ShadowRegion（面局部坐标，原点在面中心）
    """
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)

    u = (cx / photo_w - 0.5) * face.width
    v = (0.5 - cy / photo_h) * face.height
    w = bw / photo_w * face.width
    h = bh / photo_h * face.height

    color = DISEASE_COLOR_MAP.get(disease_type, _FALLBACK_COLOR)
    return ShadowRegion(
        local_u=u,
        local_v=v,
        width=w,
        height=h,
        disease_type=disease_type,
        color_rgb=color,
    )


@dataclass
class ShadowRegion:
    """面上的一个阴影区域"""
    local_u: float       # 面局部坐标U（沿面主方向）
    local_v: float       # 面局部坐标V（沿面次方向）
    width: float         # 区域宽度（U方向）
    height: float        # 区域高度（V方向）
    disease_type: str    # 病害类型
    color_rgb: Tuple[int, int, int]   # 颜色 (R, G, B)


@dataclass
class FaceInfo:
    """构件面的几何信息"""
    face_name: str
    plane: str           # 'xy', 'xz', 'yz', 'side', 'unroll', 'xyz'(弧面真3D)
    center: Tuple[float, float, float]   # 面中心世界坐标
    normal: Tuple[float, float, float]   # 面向外法向（单位向量）
    width: float         # 面主方向尺寸
    height: float        # 面次方向尺寸
    u_axis: Tuple[float, float, float]   # U方向在世界坐标中的单位向量
    v_axis: Tuple[float, float, float]   # V方向在世界坐标中的单位向量
    # 弧面映射（仅曲面：衬砌拱圈内壁/仰拱内壁）：(u, v) → ((dx,dy,dz), (nx,ny,nz))
    # 返回相对面中心的 3D 偏移与该点内法线（单位向量）；平面面为 None
    surface_fn: Optional[Callable[[float, float], Tuple[Tuple[float, float, float],
                                                         Tuple[float, float, float]]]] = None


class FaceProjectionEngine:
    """
    面投影引擎

    根据构件类型和参数，计算构件各面的3D几何信息，
    并支持在指定面上生成模拟的病害阴影区域。
    """

    # 各构件类型的默认测试面（用于一键测试）
    DEFAULT_TEST_FACE = {
        '长方体': 'front',
        '正方体': 'front',
        '圆柱': 'front',
        '直角三棱柱': 'side_a',
        '衬砌': '拱圈内壁',
        '路面': '顶面',
        '检修道': '左检修道顶面',
        '排水': '沟底面',
        '洞门': '正面',
    }

    def __init__(self, component_type: str, params: dict,
                 base_position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                 rotation_z: float = 0.0):
        """
        初始化投影引擎

        Args:
            component_type: 构件类型名称
            params: 构件参数字典
            base_position: 构件在世界坐标中的基准位置（place 时的放置点）
            rotation_z: 构件绕 Z 轴的旋转弧度（绕 base_position 点旋转，0 表示无旋转）
        """
        self.component_type = component_type
        self.params = dict(params) if params else {}
        self.base_x, self.base_y, self.base_z = base_position
        self.rot_z = float(rotation_z or 0.0)
        self._rc = math.cos(self.rot_z)
        self._rs = math.sin(self.rot_z)

    def _rot2(self, x: float, y: float) -> Tuple[float, float]:
        """绕 Z 轴旋转平面分量"""
        return (x * self._rc - y * self._rs, x * self._rs + y * self._rc)

    def _rotate_face(self, face: FaceInfo) -> FaceInfo:
        """将轴对齐的面信息按 rot_z 旋转（绕 base 点）。

        中心点：center' = base + R·(center − base)；轴向/法向直接旋转；
        surface_fn 的偏移与内法线同样旋转，保证
        世界坐标 = base + R·(面局部几何) 这条链不变。
        """
        if abs(self.rot_z) < 1e-12:
            return face

        def rv(v):
            rx, ry = self._rot2(v[0], v[1])
            return (rx, ry, v[2])

        cx, cy = self._rot2(face.center[0] - self.base_x,
                            face.center[1] - self.base_y)
        center = (self.base_x + cx, self.base_y + cy, face.center[2])

        surface_fn = face.surface_fn
        if surface_fn is not None:
            def _surf(u, v, _f=surface_fn):
                (px, py, pz), (nx, ny, nz) = _f(u, v)
                rpx, rpy = self._rot2(px, py)
                rnx, rny = self._rot2(nx, ny)
                return (rpx, rpy, pz), (rnx, rny, nz)
            surface_fn = _surf

        return FaceInfo(
            face_name=face.face_name,
            plane=face.plane,
            center=center,
            normal=rv(face.normal),
            width=face.width,
            height=face.height,
            u_axis=rv(face.u_axis),
            v_axis=rv(face.v_axis),
            surface_fn=surface_fn,
        )

    def get_face_info(self, face_name: Optional[str] = None) -> Optional[FaceInfo]:
        """
        获取指定面的几何信息。如果未指定，使用默认测试面。
        """
        if face_name is None:
            face_name = self.DEFAULT_TEST_FACE.get(self.component_type)

        if face_name is None:
            return None

        method_name = f'_get_{self.component_type}_{face_name}_face'
        method = getattr(self, method_name, None)
        if method is None:
            return None

        return self._rotate_face(method())

    def generate_simulated_shadows(self, face_name: Optional[str] = None,
                                   count: int = 3,
                                   seed: Optional[int] = None) -> List[ShadowRegion]:
        """
        在指定面上生成模拟的病害阴影区域。

        Args:
            face_name: 面名称，None 则使用默认测试面
            count: 生成区域数量
            seed: 随机种子（用于可重复测试）

        Returns:
            ShadowRegion 列表
        """
        if seed is not None:
            random.seed(seed)

        face = self.get_face_info(face_name)
        if face is None:
            return []

        regions = []
        margin = 0.15   # 边距比例（距离面边缘 15%）

        for _ in range(count):
            disease_type = random.choice(DISEASE_CLASSES)
            color = DISEASE_COLOR_MAP[disease_type]

            # 区域尺寸：面的 15% ~ 35%
            rw = face.width * random.uniform(0.15, 0.35)
            rh = face.height * random.uniform(0.15, 0.35)

            # 区域位置：在面内随机，留边距
            max_u = face.width * (0.5 - margin) - rw / 2
            max_v = face.height * (0.5 - margin) - rh / 2
            min_u = -max_u
            min_v = -max_v

            u = random.uniform(min_u, max_u) if max_u > min_u else 0.0
            v = random.uniform(min_v, max_v) if max_v > min_v else 0.0

            regions.append(ShadowRegion(
                local_u=u,
                local_v=v,
                width=rw,
                height=rh,
                disease_type=disease_type,
                color_rgb=color,
            ))

        return regions

    def shadow_to_world(self, face: FaceInfo, shadow: ShadowRegion,
                        thickness: float = 2.0) -> Tuple[float, float, float, float, float, float, str]:
        """
        将面上的阴影区域转换为世界坐标中的放置参数。

        Returns:
            (world_x, world_y, world_z, world_width, world_height, world_thickness, axis)
            其中 (world_x, world_y, world_z) 是薄片中心的世界坐标，
            axis 为 'xz'/'xy'/'yz'，用于指导阴影组件的轴向。
        """
        # 薄片中心 = 面中心 + u * u_axis + v * v_axis + 法向偏移（贴紧表面外侧）
        offset = 2.0   # 沿法向偏移 2mm，避免与构件表面重叠（z-fighting）
        cx = (face.center[0] + shadow.local_u * face.u_axis[0]
              + shadow.local_v * face.v_axis[0] + face.normal[0] * offset)
        cy = (face.center[1] + shadow.local_u * face.u_axis[1]
              + shadow.local_v * face.v_axis[1] + face.normal[1] * offset)
        cz = (face.center[2] + shadow.local_u * face.u_axis[2]
              + shadow.local_v * face.v_axis[2] + face.normal[2] * offset)

        # 尺寸映射：根据面的 plane 类型决定 width/height/thickness 在世界坐标中的轴向
        if face.plane == 'xz':
            # 面在 XZ 平面，厚度沿 Y 轴
            return cx, cy, cz, shadow.width, shadow.height, thickness, 'xz'
        elif face.plane == 'yz':
            # 面在 YZ 平面，厚度沿 X 轴
            return cx, cy, cz, shadow.width, shadow.height, thickness, 'yz'
        else:   # 'xy' or others
            # 面在 XY 平面，厚度沿 Z 轴
            return cx, cy, cz, shadow.width, shadow.height, thickness, 'xy'

    # ============================================================
    # 各构件类型的面计算（内部方法）
    # ============================================================

    # ---------- 长方体 ----------

    def _get_长方体_front_face(self) -> FaceInfo:
        L = float(self.params.get('长度', 200))
        W = float(self.params.get('宽度', 100))
        H = float(self.params.get('高度', 150))
        # 长方体中心在 base_position，front 面在 Y = base_y - W/2
        return FaceInfo(
            face_name='front',
            plane='xz',
            center=(self.base_x, self.base_y - W / 2, self.base_z),
            normal=(0, -1, 0),
            width=L,
            height=H,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_长方体_top_face(self) -> FaceInfo:
        L = float(self.params.get('长度', 200))
        W = float(self.params.get('宽度', 100))
        H = float(self.params.get('高度', 150))
        return FaceInfo(
            face_name='top',
            plane='xy',
            center=(self.base_x, self.base_y, self.base_z + H / 2),
            normal=(0, 0, 1),
            width=L,
            height=W,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
        )

    def _get_长方体_left_face(self) -> FaceInfo:
        L = float(self.params.get('长度', 200))
        W = float(self.params.get('宽度', 100))
        H = float(self.params.get('高度', 150))
        return FaceInfo(
            face_name='left',
            plane='yz',
            center=(self.base_x - L / 2, self.base_y, self.base_z),
            normal=(-1, 0, 0),
            width=W,
            height=H,
            u_axis=(0, 1, 0),
            v_axis=(0, 0, 1),
        )

    # ---------- 正方体 ----------

    def _get_正方体_front_face(self) -> FaceInfo:
        a = float(self.params.get('边长', 100))
        return FaceInfo(
            face_name='front',
            plane='xz',
            center=(self.base_x, self.base_y - a / 2, self.base_z),
            normal=(0, -1, 0),
            width=a,
            height=a,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_正方体_top_face(self) -> FaceInfo:
        a = float(self.params.get('边长', 100))
        return FaceInfo(
            face_name='top',
            plane='xy',
            center=(self.base_x, self.base_y, self.base_z + a / 2),
            normal=(0, 0, 1),
            width=a,
            height=a,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
        )

    # ---------- 圆柱 ----------

    def _get_圆柱_front_face(self) -> FaceInfo:
        r = float(self.params.get('半径', 50))
        h = float(self.params.get('高度', 100))
        # 圆柱底面圆心在 base_position，front 方向在 Y = base_y - r
        return FaceInfo(
            face_name='front',
            plane='xz',
            center=(self.base_x, self.base_y - r, self.base_z + h / 2),
            normal=(0, -1, 0),
            width=2 * r,
            height=h,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_圆柱_side_face(self) -> FaceInfo:
        r = float(self.params.get('半径', 50))
        h = float(self.params.get('高度', 100))
        # 侧面展开：近似为矩形，贴在 front 方向
        return FaceInfo(
            face_name='side',
            plane='xz',
            center=(self.base_x, self.base_y - r, self.base_z + h / 2),
            normal=(0, -1, 0),
            width=2 * math.pi * r,
            height=h,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    # ---------- 直角三棱柱 ----------

    def _get_直角三棱柱_side_a_face(self) -> FaceInfo:
        a = float(self.params.get('直角边1', 100))
        b = float(self.params.get('直角边2', 100))
        h = float(self.params.get('高度', 200))
        # side_a 面：沿 Y 轴看过去的面，位于 Y = base_y，尺寸 a × h
        return FaceInfo(
            face_name='side_a',
            plane='xz',
            center=(self.base_x + a / 2, self.base_y, self.base_z + h / 2),
            normal=(0, -1, 0),
            width=a,
            height=h,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_直角三棱柱_side_b_face(self) -> FaceInfo:
        a = float(self.params.get('直角边1', 100))
        b = float(self.params.get('直角边2', 100))
        h = float(self.params.get('高度', 200))
        # side_b 面：沿 X 轴看过去的面，位于 X = base_x，尺寸 b × h
        return FaceInfo(
            face_name='side_b',
            plane='yz',
            center=(self.base_x, self.base_y + b / 2, self.base_z + h / 2),
            normal=(-1, 0, 0),
            width=b,
            height=h,
            u_axis=(0, 1, 0),
            v_axis=(0, 0, 1),
        )

    def _get_直角三棱柱_hypotenuse_face(self) -> FaceInfo:
        a = float(self.params.get('直角边1', 100))
        b = float(self.params.get('直角边2', 100))
        h = float(self.params.get('高度', 200))
        hyp = math.hypot(a, b)
        # 斜面中心：三角形斜边中点在 XY 平面的投影，加上 base_position
        mid_x = self.base_x + a / 2
        mid_y = self.base_y + b / 2
        # 斜面向外法向（垂直于斜边，指向外侧）
        nx = -b / hyp
        ny = -a / hyp
        return FaceInfo(
            face_name='hypotenuse',
            plane='side',
            center=(mid_x, mid_y, self.base_z + h / 2),
            normal=(nx, ny, 0),
            width=hyp,
            height=h,
            u_axis=(a / hyp, -b / hyp, 0),   # 沿斜边方向
            v_axis=(0, 0, 1),
        )

    # ============================================================
    # 隧道构件面（组件成品/隧道.py 断面体系：XZ 断面沿 Y 拉伸，洞口朝 ±Y）
    # 断面参数：W=隧道净宽, H=拱仰厚度, w=二次衬砌厚度, h=底部高度, L=隧道长度
    # 隧道轴向为 Y（0 → L），竖向为 Z（起拱线 z=0，拱顶 z=H，仰拱底 z=-h）；
    # 拱圈/仰拱内弧为 XZ 截面上的三点圆弧（pyp3d Arc 语义，精确圆解析计算）。
    # ============================================================

    # 组件内硬编码的派生尺寸（与 组件成品/隧道.py replace() 中的公式一致）
    _TUNNEL_X1 = 1000.0   # 路缘带宽度（检修道内侧至起拱线的水平偏移）

    def _tunnel_params(self):
        """读取隧道断面参数（键名与 组件成品/隧道.py 的 Attr 定义一致）"""
        W = float(self.params.get('隧道净宽', 10000))
        H = float(self.params.get('拱仰厚度', 5000))
        w = float(self.params.get('二次衬砌厚度', 350))
        h = float(self.params.get('底部高度', 800))
        L = float(self.params.get('隧道长度', 50000))
        x1 = self._TUNNEL_X1
        h1 = H / 5000 * 200          # 检修道顶面高度（组件公式）
        b1 = W / 2 / 5000 * 1029.7   # 检修道顶面宽度（组件公式）
        return W, H, w, h, L, x1, h1, b1

    @staticmethod
    def _circle_through(p1, p2, p3):
        """过三点（p2 为弧上中点，pyp3d Arc 语义）的精确圆参数。
        隧道拱圈/仰拱三点均为 (-a,0)、(0,m)、(a,0)，圆心必在纵轴上。
        返回 (c, rho, s, psi0)：圆心 (0, c)，半径 rho=|R|（R=m-c 带符号），
        s=sign(R)（拱圈 +1、仰拱 -1），半圆心角 psi0 = atan2(a, -s*c)。
        弧长参数 psi = u / rho，点 = (rho*sin(psi), c + s*rho*cos(psi))。"""
        a = abs(float(p3[0] - p1[0])) / 2.0
        m = float(p2[1])
        if a <= 0.0:
            return 0.0, abs(m), (1.0 if m >= 0 else -1.0), 0.0
        if abs(m) < 1e-9:
            return 0.0, a, 1.0, math.pi / 2.0
        c = (m * m - a * a) / (2.0 * m)   # 圆心纵坐标
        R = m - c                          # 带符号半径：p2 = 圆心 + R*(0,1)
        rho = abs(R)
        s = 1.0 if R > 0 else -1.0
        psi0 = math.atan2(a, -s * c)       # (0, pi)
        return c, rho, s, psi0

    @staticmethod
    def _arc_length(p1, p2, p3, segments=32):
        """三点圆弧（pyp3d Arc 语义）的精确展开长度 = 2*rho*psi0。
        segments 参数仅为兼容旧签名，不再使用（精确圆代替贝塞尔近似）。"""
        _c, rho, _s, psi0 = FaceProjectionEngine._circle_through(p1, p2, p3)
        return 2.0 * rho * psi0

    @staticmethod
    def _arc_sampler(p1, p2, p3, segments=32):
        """兼容旧接口：返回 (samples, total)。
        精确圆实现下不再需要在折线采样表上定位，samples 返回空表，
        实际取点由 _arc_point_at 直接按解析圆计算。"""
        total = FaceProjectionEngine._arc_length(p1, p2, p3)
        return [], total

    @staticmethod
    def _arc_point_at(samples, total, u, p1, p2, p3, segments=32, inward=+1):
        """按距弧中点（拱顶/仰拱底）的弧长 u（左负右正）取弧面点与内法线（XZ 截面内）。
        精确圆：psi = u / rho，点 = (rho*sin(psi), c + s*rho*cos(psi))，
        单位切向 (cos(psi), -s*sin(psi))，保证 u>0 恒对应 +x 侧。
        inward=+1：内法线取 (tz,-tx)（拱圈，朝隧道内侧下方）；
        inward=-1：内法线取 (-tz,tx)（仰拱，朝隧道内侧上方）。
        返回 ((x, z), (nx, nz))。"""
        c, rho, s, psi0 = FaceProjectionEngine._circle_through(p1, p2, p3)
        half = rho * psi0
        psi = min(max(u, -half), half) / rho
        x = rho * math.sin(psi)
        z = c + s * rho * math.cos(psi)
        tx, tz = math.cos(psi), -s * math.sin(psi)
        if inward > 0:
            return (x, z), (tz, -tx)
        return (x, z), (-tz, tx)

    # ---------- 衬砌（组件成品/隧道.py：内轮廓为起拱线±W/2、拱顶(0,H)、仰拱底(0,-h) 的三点圆弧，XZ 截面沿 Y 拉伸） ----------

    def _get_衬砌_拱圈内壁_face(self) -> FaceInfo:
        """衬砌内轮廓拱圈面：真实弧面（非切平面近似）。
        surface_fn 逐点落在拱圈内弧上：u 为距拱顶的弧长（左负右正），v 沿隧道纵向 Y；
        内法线朝隧道内侧（拱顶处约 -Z）。照片假设为隧道内仰拍拱圈，
        照片 X → 沿拱圈弧长展开，照片 Y → 沿隧道纵向。"""
        W, H, w, h, L, x1, h1, b1 = self._tunnel_params()
        arc = self._arc_length((-W / 2, 0), (0, H), (W / 2, 0))
        samples, total = self._arc_sampler((-W / 2, 0), (0, H), (W / 2, 0))

        def _surf(u, v, _s=samples, _tot=total, _zref=H,
                  _p1=(-W / 2, 0), _p2=(0, H), _p3=(W / 2, 0)):
            (x, z), (nx, nz) = FaceProjectionEngine._arc_point_at(
                _s, _tot, u, _p1, _p2, _p3, inward=+1)
            return (x, v, z - _zref), (nx, 0.0, nz)

        return FaceInfo(
            face_name='拱圈内壁',
            plane='xyz',
            center=(self.base_x, self.base_y + L / 2, self.base_z + H),
            normal=(0, 0, -1),
            width=arc,
            height=L,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
            surface_fn=_surf,
        )

    def _get_衬砌_仰拱内壁_face(self) -> FaceInfo:
        """仰拱（底板）内弧面（真实弧面）。
        surface_fn 逐点落在仰拱内弧上，内法线朝隧道内侧上方（仰拱底处约 +Z），照片假设为俯拍。"""
        W, H, w, h, L, x1, h1, b1 = self._tunnel_params()
        arc = self._arc_length((-W / 2, 0), (0, -h), (W / 2, 0))
        samples, total = self._arc_sampler((-W / 2, 0), (0, -h), (W / 2, 0))

        def _surf(u, v, _s=samples, _tot=total, _zref=-h,
                  _p1=(-W / 2, 0), _p2=(0, -h), _p3=(W / 2, 0)):
            (x, z), (nx, nz) = FaceProjectionEngine._arc_point_at(
                _s, _tot, u, _p1, _p2, _p3, inward=-1)
            return (x, v, z - _zref), (nx, 0.0, nz)

        return FaceInfo(
            face_name='仰拱内壁',
            plane='xyz',
            center=(self.base_x, self.base_y + L / 2, self.base_z - h),
            normal=(0, 0, 1),
            width=arc,
            height=L,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
            surface_fn=_surf,
        )

    # ---------- 路面（组件成品/隧道.py：路面顶面 z=40，宽 W-2*x1，沿 Y 伸展） ----------

    def _get_路面_顶面_face(self) -> FaceInfo:
        """隧道路面顶面（水平面 z=base_z+40）。
        独立路面组件可用 路面宽/路面长/路面厚 覆盖；缺省时按隧道组件参数派生
        （顶面高 40 与 组件成品/隧道.py 中 sec_lu 断面的顶面高度 40 一致）。"""
        W, H, w, h, L, x1, h1, b1 = self._tunnel_params()
        road_w = float(self.params.get('路面宽', W - 2 * x1))
        road_l = float(self.params.get('路面长', L))
        top_z = float(self.params.get('路面厚', 40))
        return FaceInfo(
            face_name='顶面',
            plane='xy',
            center=(self.base_x, self.base_y + road_l / 2, self.base_z + top_z),
            normal=(0, 0, 1),
            width=road_w,
            height=road_l,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
        )

    # ---------- 检修道（组件成品/隧道.py：dun 段，顶面高 h1=H/5000*200，顶面宽约 b1） ----------

    def _get_检修道_左检修道顶面_face(self) -> FaceInfo:
        """左侧检修道顶面（水平面，照片通常为俯拍/侧俯拍）"""
        W, H, w, h, L, x1, h1, b1 = self._tunnel_params()
        width = float(self.params.get('检修道宽', b1))
        height = float(self.params.get('检修道高', h1))
        cx = self.base_x - W / 2 + x1 - width / 2
        return FaceInfo(
            face_name='左检修道顶面',
            plane='xy',
            center=(cx, self.base_y + L / 2, self.base_z + height),
            normal=(0, 0, 1),
            width=width,
            height=L,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
        )

    def _get_检修道_右检修道顶面_face(self) -> FaceInfo:
        """右侧检修道顶面"""
        W, H, w, h, L, x1, h1, b1 = self._tunnel_params()
        width = float(self.params.get('检修道宽', b1))
        height = float(self.params.get('检修道高', h1))
        cx = self.base_x + W / 2 - x1 + width / 2
        return FaceInfo(
            face_name='右检修道顶面',
            plane='xy',
            center=(cx, self.base_y + L / 2, self.base_z + height),
            normal=(0, 0, 1),
            width=width,
            height=L,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
        )

    def _get_检修道_左检修道内侧面_face(self) -> FaceInfo:
        """左侧检修道靠路面一侧的内侧面（竖直面 x=-(W/2-x1)，法向朝路面 +X）"""
        W, H, w, h, L, x1, h1, b1 = self._tunnel_params()
        height = float(self.params.get('检修道高', h1))
        return FaceInfo(
            face_name='左检修道内侧面',
            plane='yz',
            center=(self.base_x - W / 2 + x1, self.base_y + L / 2, self.base_z + height / 2),
            normal=(1, 0, 0),
            width=L,
            height=height,
            u_axis=(0, 1, 0),
            v_axis=(0, 0, 1),
        )

    def _get_检修道_右检修道内侧面_face(self) -> FaceInfo:
        """右侧检修道靠路面一侧的内侧面（竖直面 x=+(W/2-x1)，法向朝路面 -X）"""
        W, H, w, h, L, x1, h1, b1 = self._tunnel_params()
        height = float(self.params.get('检修道高', h1))
        return FaceInfo(
            face_name='右检修道内侧面',
            plane='yz',
            center=(self.base_x + W / 2 - x1, self.base_y + L / 2, self.base_z + height / 2),
            normal=(-1, 0, 0),
            width=L,
            height=height,
            u_axis=(0, 1, 0),
            v_axis=(0, 0, 1),
        )

    # ---------- 排水 ----------

    def _get_排水_沟底面_face(self) -> FaceInfo:
        """排水沟沟底面（水平面）。
        说明：组件成品/隧道.py 中 all_sb 细条（宽≈200、厚 5、位于路面顶 z=40）语义不明确
        （疑似电缆沟或防撞基座条带），无法据此确定排水沟几何；此处按通用矩形边沟近似，
        靠左侧路面边缘布置，可用 排水沟宽/排水沟深/排水沟长 参数覆盖。"""
        W, H, w, h, L, x1, h1, b1 = self._tunnel_params()
        g_w = float(self.params.get('排水沟宽', 400))
        g_l = float(self.params.get('排水沟长', L))
        g_d = float(self.params.get('排水沟深', 300))
        road_top = float(self.params.get('路面厚', 40))
        cx = self.base_x - (W / 2 - x1) + g_w / 2   # 从左侧路面边缘起算
        return FaceInfo(
            face_name='沟底面',
            plane='xy',
            center=(cx, self.base_y + g_l / 2, self.base_z + road_top - g_d),
            normal=(0, 0, 1),
            width=g_w,
            height=g_l,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
        )

    # ---------- 洞门 ----------

    def _get_洞门_正面_face(self) -> FaceInfo:
        """洞门端墙正面（小桩号端 y=base_y，法向朝洞外 -Y）。
        暂无独立洞门组件参数，按隧道断面外轮廓外接矩形近似
        （宽 W+2w、高 H+h+w，即拱顶外缘至仰拱外缘）。"""
        W, H, w, h, L, x1, h1, b1 = self._tunnel_params()
        door_w = float(self.params.get('洞门宽', W + 2 * w))
        door_h = float(self.params.get('洞门高', H + h + w))
        return FaceInfo(
            face_name='正面',
            plane='xz',
            center=(self.base_x, self.base_y, self.base_z + (H - h) / 2),
            normal=(0, -1, 0),
            width=door_w,
            height=door_h,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )


# ============================================================
# 纹理贴图生成
# ============================================================

def generate_disease_texture(face_width: float, face_height: float,
                             shadows: List[ShadowRegion],
                             output_size: Tuple[int, int] = (512, 512),
                             alpha: int = 128) -> Optional[str]:
    """
    根据病害区域生成透明背景的PNG纹理图片。

    Args:
        face_width: 面的实际宽度(mm)
        face_height: 面的实际高度(mm)
        shadows: ShadowRegion列表
        output_size: 输出图片尺寸(像素)，默认512x512
        alpha: 颜色不透明度 0-255，默认128(50%不透明)

    Returns:
        PNG临时文件路径，失败返回None
    """
    if not _PIL_OK:
        return None

    try:
        img_w, img_h = output_size
        img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        for shadow in shadows:
            # 将病害区域从世界局部坐标映射到图片像素坐标
            # 局部坐标原点在面中心，范围: u∈[-width/2, width/2], v∈[-height/2, height/2]
            # 映射到图片: x∈[0, img_w], y∈[0, img_h]（Y轴翻转，图片原点在左上角）
            half_w = face_width / 2.0
            half_h = face_height / 2.0

            left   = (shadow.local_u - shadow.width / 2 + half_w) / face_width * img_w
            right  = (shadow.local_u + shadow.width / 2 + half_w) / face_width * img_w
            top    = (half_h - (shadow.local_v + shadow.height / 2)) / face_height * img_h
            bottom = (half_h - (shadow.local_v - shadow.height / 2)) / face_height * img_h

            left   = max(0, min(img_w, int(left)))
            right  = max(0, min(img_w, int(right)))
            top    = max(0, min(img_h, int(top)))
            bottom = max(0, min(img_h, int(bottom)))

            if right > left and bottom > top:
                r, g, b = shadow.color_rgb
                draw.rectangle([left, top, right, bottom],
                               fill=(r, g, b, alpha))

        temp_path = os.path.join(tempfile.gettempdir(), "disease_texture.png")
        img.save(temp_path)
        return temp_path
    except Exception:
        return None


# ============================================================
# 点云生成器
# ============================================================

class PointCloudGenerator:
    """
    点云阴影生成器 — 在病害区域内生成密集的彩色小几何体

    防护（防止大面积构件如衬砌拱圈内壁 11477×50000mm 导致点云爆炸卡死）：
    - 目标总点数上限 max_total_points（默认 2000）：所有阴影区域合计不超过该值；
    - 单区域点数上限 max_points_per_shadow（默认 1000）；
    - 间距自适应：区域尺寸越大，实际间距在 density 基础上等比放大，
      保证任何尺寸的面/区域生成的立方体数量都有限可控。
    """

    # 目标总点数上限：一次投影所有区域合计不超过该值
    DEFAULT_MAX_TOTAL_POINTS = 2000
    # 单个病害区域的点数上限
    DEFAULT_MAX_POINTS_PER_SHADOW = 1000

    def __init__(self, density: float = 5.0, point_size: float = 3.0,
                 max_total_points: Optional[int] = None,
                 max_points_per_shadow: Optional[int] = None):
        """
        Args:
            density: 点间距(mm)，默认5mm
            point_size: 每个小点的尺寸(mm)，默认3mm
            max_total_points: 目标总点数上限，None 用默认值
            max_points_per_shadow: 单区域点数上限，None 用默认值
        """
        self.density = max(2.0, density)
        self.point_size = max(1.0, point_size)
        self.max_total_points = max(1, int(max_total_points
                                           or self.DEFAULT_MAX_TOTAL_POINTS))
        self.max_points_per_shadow = max(1, int(max_points_per_shadow
                                                or self.DEFAULT_MAX_POINTS_PER_SHADOW))

    def _grid_for(self, width: float, height: float, budget: int) -> Tuple[int, int]:
        """按给定点数预算计算 (nx, ny)。预算不足时等比放大间距，保证 nx*ny <= budget。"""
        nx = max(1, int(width / self.density))
        ny = max(1, int(height / self.density))
        if nx * ny > budget:
            # 等比放大间距，使 nx*ny 约等于 budget
            factor = math.sqrt((nx * ny) / float(budget))
            nx = max(1, int(nx / factor))
            ny = max(1, int(ny / factor))
            # 取整后可能仍略微超预算，逐格回退
            while nx * ny > budget and (nx > 1 or ny > 1):
                if nx >= ny and nx > 1:
                    nx -= 1
                else:
                    ny -= 1
        return nx, ny

    def generate(self, face: FaceInfo, shadows: List[ShadowRegion]) -> List[Tuple[float, float, float, Tuple[int, int, int]]]:
        """
        生成点云数据列表。

        Returns:
            [(local_u, local_v, normal_offset, (r, g, b)), ...]
            其中 local_u/local_v 是面局部坐标，normal_offset 是沿法向的偏移量（使小点紧贴表面外侧）
        """
        points = []
        # 沿法向向外偏移半个点尺寸，使小点中心在构件表面外侧
        normal_offset = self.point_size / 2.0
        remaining = self.max_total_points
        for shadow in shadows:
            if remaining <= 0:
                break
            r, g, b = shadow.color_rgb
            budget = min(self.max_points_per_shadow, remaining)
            nx, ny = self._grid_for(shadow.width, shadow.height, budget)

            for i in range(nx):
                for j in range(ny):
                    pu = shadow.local_u - shadow.width / 2 + (i + 0.5) * shadow.width / nx
                    pv = shadow.local_v - shadow.height / 2 + (j + 0.5) * shadow.height / ny
                    points.append((pu, pv, normal_offset, (r, g, b)))
            remaining -= nx * ny

        return points

    def generate_surface(self, face: FaceInfo, shadows: List[ShadowRegion],
                         normal_offset: float = 2.0
                         ) -> List[Tuple[float, float, float, Tuple[int, int, int]]]:
        """
        在弧面病害区域内生成贴面点云（真 3D 坐标，相对面中心 face.center）。

        逐点调用 face.surface_fn(u, v) 落在真实弧面上，再沿该点内法线偏移
        normal_offset + point_size/2（2mm 防 z-fighting + 半个点尺寸使小点露出表面）。
        点数上限/自适应间距与 generate() 同一套逻辑。

        Returns:
            [(px, py, pz, (r, g, b)), ...]，face.surface_fn 为 None 时返回空列表
        """
        if face.surface_fn is None:
            return []
        points = []
        off = normal_offset + self.point_size / 2.0
        remaining = self.max_total_points
        for shadow in shadows:
            if remaining <= 0:
                break
            r, g, b = shadow.color_rgb
            budget = min(self.max_points_per_shadow, remaining)
            nx, ny = self._grid_for(shadow.width, shadow.height, budget)

            for i in range(nx):
                for j in range(ny):
                    pu = shadow.local_u - shadow.width / 2 + (i + 0.5) * shadow.width / nx
                    pv = shadow.local_v - shadow.height / 2 + (j + 0.5) * shadow.height / ny
                    (px, py, pz), (nx_, ny_, nz_) = face.surface_fn(pu, pv)
                    points.append((px + nx_ * off, py + ny_ * off, pz + nz_ * off, (r, g, b)))
            remaining -= nx * ny

        return points

    def estimate_point_count(self, shadows: List[ShadowRegion]) -> int:
        """估算生成的点数（与 generate 同一套上限/自适应间距逻辑，结果一致）"""
        total = 0
        remaining = self.max_total_points
        for shadow in shadows:
            if remaining <= 0:
                break
            budget = min(self.max_points_per_shadow, remaining)
            nx, ny = self._grid_for(shadow.width, shadow.height, budget)
            total += nx * ny
            remaining -= nx * ny
        return total
