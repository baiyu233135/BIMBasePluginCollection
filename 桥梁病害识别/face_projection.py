# -*- coding: utf-8 -*-
"""
面投影引擎 — 将病害识别结果投影到构件表面

根据构件类型和参数，计算指定面的3D坐标，
并在面上生成带颜色的半透明阴影标记。
"""

import math
import os
import random
import tempfile
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

try:
    from PIL import Image, ImageDraw
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# ============================================================
# 病害颜色映射（与 disease_detector.py 保持一致）
# ============================================================

DISEASE_COLOR_MAP = {
    "裂缝": (255, 0, 0),       # 红
    "剥落": (255, 128, 0),     # 橙
    "露筋": (255, 255, 0),     # 黄
    "蜂窝麻面": (128, 0, 255),  # 紫
    "渗水": (0, 128, 255),     # 蓝
    "锈蚀": (128, 128, 128),   # 灰
    "已修复": (102, 187, 106),  # 绿 #66bb6a
}

DISEASE_CLASSES = list(DISEASE_COLOR_MAP.keys())

# 未知病害类型的兜底颜色：绿
_FALLBACK_COLOR = (0, 200, 0)

# 各构件类型可用的投影面清单（供 UI 下拉选择）
FACE_REGISTRY = {
    '长方体': ['front', 'top', 'left'],
    '正方体': ['front', 'top'],
    '圆柱': ['front', 'side'],
    '直角三棱柱': ['side_a', 'side_b', 'hypotenuse'],
    '投影测试T梁': ['bottom', 'web_side', 'flange_bottom'],
    '投影测试横隔板': ['front', 'side'],
    '投影测试湿接缝': ['top', 'side'],
    '投影测试墩柱': ['front', 'side'],
    '柱式桥墩': ['左墩柱正面', '右墩柱正面', '系梁正面', '盖梁正面'],
    '引桥桥墩': ['左墩柱正面', '右墩柱正面', '系梁正面', '盖梁正面'],
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
    plane: str           # 'xy', 'xz', 'yz', 'side', 'unroll'
    center: Tuple[float, float, float]   # 面中心世界坐标
    normal: Tuple[float, float, float]   # 面向外法向（单位向量）
    width: float         # 面主方向尺寸
    height: float        # 面次方向尺寸
    u_axis: Tuple[float, float, float]   # U方向在世界坐标中的单位向量
    v_axis: Tuple[float, float, float]   # V方向在世界坐标中的单位向量


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
        '投影测试T梁': 'bottom',
        '投影测试横隔板': 'front',
        '投影测试湿接缝': 'top',
        '投影测试墩柱': 'front',
        '柱式桥墩': '左墩柱正面',
        '引桥桥墩': '左墩柱正面',
    }

    def __init__(self, component_type: str, params: dict,
                 base_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)):
        """
        初始化投影引擎

        Args:
            component_type: 构件类型名称
            params: 构件参数字典
            base_position: 构件在世界坐标中的基准位置（place 时的放置点）
        """
        self.component_type = component_type
        self.params = dict(params) if params else {}
        self.base_x, self.base_y, self.base_z = base_position

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

        return method()

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

    # ---------- 投影测试T梁 ----------

    def _get_投影测试T梁_bottom_face(self) -> FaceInfo:
        """梁底面（仰视拍摄时的主要投影面），底面位于组件基准点 Z=base_z"""
        L = float(self.params.get('梁长', 3000))
        dw = float(self.params.get('底板宽', 80))
        return FaceInfo(
            face_name='bottom',
            plane='xy',
            center=(self.base_x, self.base_y, self.base_z),
            normal=(0, 0, -1),
            width=dw,
            height=L,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
        )

    def _get_投影测试T梁_web_side_face(self) -> FaceInfo:
        """腹板侧面（沿 X 方向看，位于腹板一侧）"""
        L = float(self.params.get('梁长', 3000))
        tw = float(self.params.get('腹板宽', 20))
        dh = float(self.params.get('底板高', 25))
        fh = float(self.params.get('翼缘高', 20))
        H = float(self.params.get('总高', 160))
        web_h = H - dh - fh
        return FaceInfo(
            face_name='web_side',
            plane='yz',
            center=(self.base_x - tw / 2, self.base_y, self.base_z + dh + web_h / 2),
            normal=(-1, 0, 0),
            width=L,
            height=web_h,
            u_axis=(0, 1, 0),
            v_axis=(0, 0, 1),
        )

    def _get_投影测试T梁_flange_bottom_face(self) -> FaceInfo:
        """翼缘底面（掉角、剥落常见位置）"""
        L = float(self.params.get('梁长', 3000))
        fw = float(self.params.get('翼缘宽', 200))
        dh = float(self.params.get('底板高', 25))
        fh = float(self.params.get('翼缘高', 20))
        H = float(self.params.get('总高', 160))
        web_h = H - dh - fh
        return FaceInfo(
            face_name='flange_bottom',
            plane='xy',
            center=(self.base_x, self.base_y, self.base_z + dh + web_h),
            normal=(0, 0, -1),
            width=fw,
            height=L,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
        )

    # ---------- 投影测试横隔板 ----------

    def _get_投影测试横隔板_front_face(self) -> FaceInfo:
        """横隔板大桩号面/小桩号面（Y 方向正面）"""
        W = float(self.params.get('宽度', 200))
        H = float(self.params.get('高度', 160))
        T = float(self.params.get('厚度', 20))
        return FaceInfo(
            face_name='front',
            plane='xz',
            center=(self.base_x, self.base_y - T / 2, self.base_z + H / 2),
            normal=(0, -1, 0),
            width=W,
            height=H,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_投影测试横隔板_side_face(self) -> FaceInfo:
        """横隔板侧面（X 方向）"""
        W = float(self.params.get('宽度', 200))
        H = float(self.params.get('高度', 160))
        T = float(self.params.get('厚度', 20))
        return FaceInfo(
            face_name='side',
            plane='yz',
            center=(self.base_x - W / 2, self.base_y, self.base_z + H / 2),
            normal=(-1, 0, 0),
            width=T,
            height=H,
            u_axis=(0, 1, 0),
            v_axis=(0, 0, 1),
        )

    # ---------- 投影测试湿接缝 ----------

    def _get_投影测试湿接缝_top_face(self) -> FaceInfo:
        """湿接缝顶面"""
        L = float(self.params.get('长度', 3000))
        top_w = float(self.params.get('顶宽', 50))
        H = float(self.params.get('高度', 80))
        return FaceInfo(
            face_name='top',
            plane='xy',
            center=(self.base_x, self.base_y, self.base_z + H),
            normal=(0, 0, 1),
            width=top_w,
            height=L,
            u_axis=(1, 0, 0),
            v_axis=(0, 1, 0),
        )

    def _get_投影测试湿接缝_side_face(self) -> FaceInfo:
        """湿接缝侧面（X 方向）"""
        L = float(self.params.get('长度', 3000))
        top_w = float(self.params.get('顶宽', 50))
        bottom_w = float(self.params.get('底宽', 30))
        H = float(self.params.get('高度', 80))
        # 侧面取梯形中位宽
        mid_w = (top_w + bottom_w) / 2
        return FaceInfo(
            face_name='side',
            plane='xz',
            center=(self.base_x - mid_w / 2, self.base_y, self.base_z + H / 2),
            normal=(-1, 0, 0),
            width=L,
            height=H,
            u_axis=(0, 1, 0),
            v_axis=(0, 0, 1),
        )

    # ---------- 投影测试墩柱 ----------

    def _get_投影测试墩柱_front_face(self) -> FaceInfo:
        """墩柱正面（圆柱近似为矩形面）"""
        D = float(self.params.get('柱径', 120))
        H = float(self.params.get('柱高', 800))
        return FaceInfo(
            face_name='front',
            plane='xz',
            center=(self.base_x, self.base_y - D / 2, self.base_z + H / 2),
            normal=(0, -1, 0),
            width=D,
            height=H,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_投影测试墩柱_side_face(self) -> FaceInfo:
        """墩柱侧面展开（圆柱近似）"""
        D = float(self.params.get('柱径', 120))
        H = float(self.params.get('柱高', 800))
        return FaceInfo(
            face_name='side',
            plane='xz',
            center=(self.base_x - D / 2, self.base_y, self.base_z + H / 2),
            normal=(-1, 0, 0),
            width=math.pi * D,
            height=H,
            u_axis=(0, 1, 0),
            v_axis=(0, 0, 1),
        )
    # ---------- 柱式桥墩（真实组件，桥梁组件/2-下部结构/柱式桥墩.py） ----------
    # 组件原点：盖梁前左下角（z=0 为盖梁截面顶起点）。
    # 左墩柱圆心 x=235，右墩柱 x=L-235，墩柱从 z=-85 向下延伸 DZH，半径 R=桩基径。

    def _pier_params(self):
        DZH = float(self.params.get('墩柱高', 1700))
        R = float(self.params.get('桩基径', 110))
        L = float(self.params.get('盖梁宽度', 1220))
        W = float(self.params.get('盖梁厚度', 230))
        TH = float(self.params.get('盖梁高', 95))
        DH = float(self.params.get('档墙高', 60))
        TH1 = float(self.params.get('系梁高', 200))
        return DZH, R, L, W, TH, DH, TH1

    def _get_柱式桥墩_左墩柱正面_face(self) -> FaceInfo:
        """左墩柱正面（圆柱按矩形近似，朝 -Y 方向）"""
        DZH, R, L, W, TH, DH, TH1 = self._pier_params()
        return FaceInfo(
            face_name='左墩柱正面',
            plane='xz',
            center=(self.base_x + 235, self.base_y + W / 2 - R, self.base_z - 85 - DZH / 2),
            normal=(0, -1, 0),
            width=2 * R,
            height=DZH,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_柱式桥墩_右墩柱正面_face(self) -> FaceInfo:
        """右墩柱正面（圆柱按矩形近似，朝 -Y 方向）"""
        DZH, R, L, W, TH, DH, TH1 = self._pier_params()
        return FaceInfo(
            face_name='右墩柱正面',
            plane='xz',
            center=(self.base_x + L - 235, self.base_y + W / 2 - R, self.base_z - 85 - DZH / 2),
            normal=(0, -1, 0),
            width=2 * R,
            height=DZH,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_柱式桥墩_系梁正面_face(self) -> Optional[FaceInfo]:
        """首段系梁正面（朝 -Y 方向）。墩柱高 <=1500 时无系梁，返回 None"""
        DZH, R, L, W, TH, DH, TH1 = self._pier_params()
        if DZH <= 1500:
            return None
        seg = int(DZH / 1500)
        pos = DZH / (seg + 1)   # 首段系梁顶面 z = -pos
        return FaceInfo(
            face_name='系梁正面',
            plane='xz',
            center=(self.base_x + L / 2, self.base_y + W / 2 - R + 30, self.base_z - pos - TH1 / 2),
            normal=(0, -1, 0),
            width=L - 580,
            height=TH1,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_柱式桥墩_盖梁正面_face(self) -> FaceInfo:
        """盖梁正面（y=0 平面，截面按外接矩形近似）"""
        DZH, R, L, W, TH, DH, TH1 = self._pier_params()
        return FaceInfo(
            face_name='盖梁正面',
            plane='xz',
            center=(self.base_x + L / 2, self.base_y, self.base_z + (DH + TH - 85) / 2),
            normal=(0, -1, 0),
            width=L,
            height=DH + TH + 85,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )
    # ---------- 引桥桥墩（组件测试/引桥桥墩.py，AI_Modeling 同款） ----------
    # 组件原点：两墩柱中心连线的中点、墩柱底部（z=0）。
    # 墩柱 z 从 0 到墩高，盖梁在 z=墩高 到 墩高+盖梁总高。

    def _ap_pier_params(self):
        cap_l = float(self.params.get('盖梁总长', 1930))
        cap_h = float(self.params.get('盖梁总高', 300))
        cap_w = float(self.params.get('盖梁宽', 300))
        col_d = float(self.params.get('墩柱直径', 250))
        col_s = float(self.params.get('墩柱间距', 1140))
        col_h = float(self.params.get('墩高', 1200))
        tie_n = int(self.params.get('系梁根数', 2))
        return cap_l, cap_h, cap_w, col_d, col_s, col_h, tie_n

    def _get_引桥桥墩_左墩柱正面_face(self) -> FaceInfo:
        """左墩柱正面（圆柱按矩形近似，朝 -Y 方向）"""
        cap_l, cap_h, cap_w, col_d, col_s, col_h, tie_n = self._ap_pier_params()
        return FaceInfo(
            face_name='左墩柱正面',
            plane='xz',
            center=(self.base_x - col_s / 2, self.base_y - col_d / 2, self.base_z + col_h / 2),
            normal=(0, -1, 0),
            width=col_d,
            height=col_h,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_引桥桥墩_右墩柱正面_face(self) -> FaceInfo:
        """右墩柱正面（圆柱按矩形近似，朝 -Y 方向）"""
        cap_l, cap_h, cap_w, col_d, col_s, col_h, tie_n = self._ap_pier_params()
        return FaceInfo(
            face_name='右墩柱正面',
            plane='xz',
            center=(self.base_x + col_s / 2, self.base_y - col_d / 2, self.base_z + col_h / 2),
            normal=(0, -1, 0),
            width=col_d,
            height=col_h,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_引桥桥墩_系梁正面_face(self) -> Optional[FaceInfo]:
        """首根系梁正面（朝 -Y 方向）。系梁根数<1 时返回 None"""
        cap_l, cap_h, cap_w, col_d, col_s, col_h, tie_n = self._ap_pier_params()
        if tie_n < 1 or col_h <= 0:
            return None
        tie_l = max(col_s - col_d, 100.0)
        # 与组件代码一致：首根系梁顶面 z = 墩高-200，梁高 200，半径 100（y=-100 处为正面）
        return FaceInfo(
            face_name='系梁正面',
            plane='xz',
            center=(self.base_x, self.base_y - 100, self.base_z + col_h - 300),
            normal=(0, -1, 0),
            width=tie_l,
            height=200.0,
            u_axis=(1, 0, 0),
            v_axis=(0, 0, 1),
        )

    def _get_引桥桥墩_盖梁正面_face(self) -> FaceInfo:
        """盖梁正面（朝 -Y 方向，梯形截面按外接矩形近似）"""
        cap_l, cap_h, cap_w, col_d, col_s, col_h, tie_n = self._ap_pier_params()
        return FaceInfo(
            face_name='盖梁正面',
            plane='xz',
            center=(self.base_x, self.base_y - cap_w / 2, self.base_z + col_h + cap_h / 2),
            normal=(0, -1, 0),
            width=cap_l,
            height=cap_h,
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
    """

    def __init__(self, density: float = 5.0, point_size: float = 3.0):
        """
        Args:
            density: 点间距(mm)，默认5mm
            point_size: 每个小点的尺寸(mm)，默认3mm
        """
        self.density = max(2.0, density)
        self.point_size = max(1.0, point_size)

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
        for shadow in shadows:
            r, g, b = shadow.color_rgb
            nx = max(1, int(shadow.width / self.density))
            ny = max(1, int(shadow.height / self.density))

            for i in range(nx):
                for j in range(ny):
                    pu = shadow.local_u - shadow.width / 2 + (i + 0.5) * shadow.width / nx
                    pv = shadow.local_v - shadow.height / 2 + (j + 0.5) * shadow.height / ny
                    points.append((pu, pv, normal_offset, (r, g, b)))

        return points

    def estimate_point_count(self, shadows: List[ShadowRegion]) -> int:
        """估算生成的点数"""
        total = 0
        for shadow in shadows:
            nx = max(1, int(shadow.width / self.density))
            ny = max(1, int(shadow.height / self.density))
            total += nx * ny
        return total
