# -*- coding: utf-8 -*-
"""
T 梁病害照片投影测试（专用）

针对“T 梁腹板侧面病害照片”，将 CV 检测到的病害区域
按照片位置等比例映射到 T 梁腹板侧面，并在 BIMBase 中自动放置
红色点云标记（很多小圆珠效果）。

使用方法（在 BIMBase Python 控制台或 exec 环境中运行）：
    exec(open('桥隧病害识别/test_t_beam_projection.py', encoding='utf-8').read())

说明：
- 使用 CADBoard/bimbase_sync.py 的 _PlaceToDirect 实现自动放置，不进入手动布置模式。
- 点云效果通过在病害区域生成多个红色小立方体/球体实现。
"""

import os
import sys
import traceback
import random
from pathlib import Path

# ============================================================
# 配置
# ============================================================
PHOTO_PATH = Path("数据参考源/桥隧数据源/T梁照片/00.png")

# T 梁参数（与 组件测试/投影测试T梁.py 一致）
T_BEAM_PARAMS = {
    '梁长': 3000.0,
    '底板宽': 80.0,
    '底板高': 25.0,
    '腹板宽': 20.0,
    '翼缘宽': 200.0,
    '翼缘高': 20.0,
    '总高': 160.0,
}

# 点云参数
POINT_CLOUD_SIZE = 10.0   # 每个小标记的尺寸
POINT_CLOUD_SPACING = 25.0  # 小标记间距


def _log(msg: str):
    """打印并写入日志"""
    print(f"[T梁投影] {msg}")
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "t_beam_projection_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{msg}\n")
    except Exception:
        pass


def detect_diseases(photo_path: str):
    """用 CV 检测照片中的异常区域"""
    _module_dir = os.path.dirname(os.path.abspath(__file__))
    if _module_dir not in sys.path:
        sys.path.insert(0, _module_dir)

    from cv_anomaly_detector import detect_anomalies_cv
    results = detect_anomalies_cv(photo_path)
    _log(f"CV 检测到 {len(results)} 个异常区域")
    return results


def map_photo_to_web_side(photo_w: int, photo_h: int, bbox: tuple,
                          beam_params: dict, base_pos: tuple = (0, 0, 0)):
    """
    将照片上的 bbox 映射到 T 梁腹板侧面，返回中心点和区域尺寸。

    映射规则（等比例）：
    - 照片 X 方向 → T 梁 Y 方向（梁长方向）
    - 照片 Y 方向 → T 梁 Z 方向（高度方向，从腹板底部到顶部）

    Returns:
        (center_x, center_y, center_z, width, height)
        width: Y 方向尺寸，height: Z 方向尺寸
    """
    L = beam_params['梁长']
    dh = beam_params['底板高']
    fh = beam_params['翼缘高']
    H = beam_params['总高']
    web_h = H - dh - fh

    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    bw = x2 - x1
    bh = y2 - y1

    nx = cx / photo_w
    ny = cy / photo_h

    # 中心点
    world_y = base_pos[1] + (nx - 0.5) * L
    world_z = base_pos[2] + dh + ny * web_h

    # 区域尺寸（按相同比例缩放）
    world_w = bw / photo_w * L
    world_h = bh / photo_h * web_h

    # X: 腹板一侧
    tw = beam_params['腹板宽']
    world_x = base_pos[0] - tw / 2

    return world_x, world_y, world_z, world_w, world_h


def generate_point_cloud_positions(center, width, height, spacing=POINT_CLOUD_SPACING):
    """
    在病害区域内生成点云位置。

    Args:
        center: (x, y, z) 中心
        width: Y 方向尺寸
        height: Z 方向尺寸
        spacing: 点间距

    Returns:
        [(x, y, z), ...]
    """
    cx, cy, cz = center
    points = []

    ny = max(1, int(width / spacing))
    nz = max(1, int(height / spacing))

    for i in range(ny):
        for j in range(nz):
            py = cy - width / 2 + (i + 0.5) * width / ny
            pz = cz - height / 2 + (j + 0.5) * height / nz
            points.append((cx, py, pz))

    return points


def create_red_sphere_component(x, y, z, size):
    """创建红色小球组件（出生在原点，由 place_to 负责定位）"""
    from pyp3d import Component, Attr, Sphere, translate, scale

    class _RedSphere(Component):
        def __init__(self):
            super().__init__()
            self['x'] = Attr(float(x), show=True, obvious=True)
            self['y'] = Attr(float(y), show=True, obvious=True)
            self['z'] = Attr(float(z), show=True, obvious=True)
            self['size'] = Attr(float(size), show=True, obvious=True)
            self['标记'] = Attr(None, show=True, obvious=True)
            self.replace()

        def replace(self):
            s = self['size']
            try:
                # 使用 color 设置红色（RGBA）
                self['标记'] = (translate(self['x'], self['y'], self['z'])
                                * scale(s, s, s)
                                * Sphere().color(1.0, 0.0, 0.0, 1.0))
            except Exception:
                # 旧版本没有 color 方法，回退到无色
                self['标记'] = translate(self['x'], self['y'], self['z']) * scale(s, s, s) * Sphere()

    return _RedSphere()


def place_component_direct(comp, x, y, z):
    """
    使用 CADBoard/bimbase_sync.py 的 _PlaceToDirect 自动放置组件。
    不进入手动布置模式。
    """
    try:
        _module_dir = os.path.dirname(os.path.abspath(__file__))
        _cadboard_dir = os.path.normpath(os.path.join(_module_dir, '..', 'CADBoard'))
        if _cadboard_dir not in sys.path:
            sys.path.insert(0, _cadboard_dir)

        import bimbase_sync as _bimbase_sync
        from pyp3d import translate as _translate

        if not _bimbase_sync._ensure_place_to_direct():
            _log("_PlaceToDirect 初始化失败")
            return False

        # 设置 sys.argv[0] 以便 place_to 读取 DependentFile
        original_argv0 = sys.argv[0]
        sys.argv[0] = os.path.join(_cadboard_dir, 'bimbase_sync.py')
        try:
            _bimbase_sync._PlaceToDirect(comp, _translate(x, y, z))
        finally:
            sys.argv[0] = original_argv0

        _log(f"自动放置成功: ({x:.1f}, {y:.1f}, {z:.1f})")
        return True
    except Exception as e:
        _log(f"自动放置失败: {e}\n{traceback.format_exc()}")
        return False


def place_point_cloud(center, width, height, size=POINT_CLOUD_SIZE):
    """在指定区域放置点云（很多红色小圆珠）"""
    positions = generate_point_cloud_positions(center, width, height)
    placed = 0

    for x, y, z in positions:
        comp = create_red_sphere_component(x, y, z, size)
        if comp is None:
            continue
        # 组件出生在原点，place_to 负责定位到 (x, y, z)
        if place_component_direct(comp, x, y, z):
            placed += 1

    _log(f"点云放置完成: {placed}/{len(positions)} 个")
    return placed


def main():
    _log("=" * 60)
    _log("T 梁病害照片投影测试（点云版）")
    _log("=" * 60)

    # 1. 检查照片
    abs_photo = (Path(__file__).resolve().parent.parent / PHOTO_PATH).resolve()
    if not abs_photo.exists():
        _log(f"照片不存在: {abs_photo}")
        return

    _log(f"照片: {abs_photo}")

    # 2. 读取照片尺寸
    import cv2
    import numpy as np
    data = np.fromfile(str(abs_photo), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        _log("无法读取照片")
        return
    photo_h, photo_w = img.shape[:2]
    _log(f"照片尺寸: {photo_w} x {photo_h}")

    # 3. CV 检测病害
    results = detect_diseases(str(abs_photo))
    if not results:
        _log("未检测到病害，退出")
        return

    # 4. 逐个映射并放置点云
    base_pos = (0, 0, 0)  # 假设 T 梁放置在世界原点
    total_placed = 0

    for i, res in enumerate(results, 1):
        x, y, z, w, h = map_photo_to_web_side(
            photo_w, photo_h, res.bbox, T_BEAM_PARAMS, base_pos
        )
        _log(f"病害 {i}: bbox={res.bbox}, 映射到中心 ({x:.1f}, {y:.1f}, {z:.1f}), 尺寸 {w:.1f}x{h:.1f}")

        # 在该区域生成点云
        placed = place_point_cloud((x, y, z), w, h)
        total_placed += placed

    _log(f"共放置 {total_placed} 个点云标记")
    _log("完成")


if __name__ == "__main__":
    main()
else:
    # 在 exec 环境中直接执行
    main()
