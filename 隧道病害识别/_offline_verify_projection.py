# -*- coding: utf-8 -*-
"""离线验证：隧道版 face_projection 衬砌面 + 点云生成不爆炸（不依赖 BIMBase/pyp3d）。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from face_projection import (
    FaceProjectionEngine, PointCloudGenerator, photo_bbox_to_shadow,
    ShadowRegion,
)

MAX_TOTAL = PointCloudGenerator.DEFAULT_MAX_TOTAL_POINTS
MAX_PER = PointCloudGenerator.DEFAULT_MAX_POINTS_PER_SHADOW


def check_points_in_bounds(points, shadow):
    half_w, half_h = shadow.width / 2.0, shadow.height / 2.0
    bad = [p for p in points
           if not (shadow.local_u - half_w - 1e-6 <= p[0] <= shadow.local_u + half_w + 1e-6
                   and shadow.local_v - half_h - 1e-6 <= p[1] <= shadow.local_v + half_h + 1e-6)]
    return len(bad)


def run_case(name, face, bbox, photo_size):
    photo_w, photo_h = photo_size
    shadow = photo_bbox_to_shadow(face, bbox, photo_w, photo_h, "裂缝")

    t0 = time.time()
    pc = PointCloudGenerator(density=15.0, point_size=8.0)
    est = pc.estimate_point_count([shadow])
    points = pc.generate(face, [shadow])
    dt = time.time() - t0

    n = len(points)
    assert n == est, f"{name}: estimate({est}) != generate({n})"
    assert n <= MAX_PER, f"{name}: 单区域点数 {n} > 上限 {MAX_PER}"
    assert n <= MAX_TOTAL, f"{name}: 总点数 {n} > 上限 {MAX_TOTAL}"
    assert dt < 5.0, f"{name}: 耗时 {dt:.2f}s >= 5s"
    bad = check_points_in_bounds(points, shadow)
    assert bad == 0, f"{name}: {bad} 个点越界"

    raw_nx = max(1, int(shadow.width / 15.0))
    raw_ny = max(1, int(shadow.height / 15.0))
    print(f"[PASS] {name}: 点数={n} (修复前按固定15mm间距将生成 {raw_nx}x{raw_ny}="
          f"{raw_nx*raw_ny}) 耗时={dt*1000:.1f}ms 面={face.width:.0f}x{face.height:.0f}")
    return n


# ---- 用例1：真实故障场景 衬砌拱圈内壁 15708x50000（精确半圆弧长 pi*5000），典型 bbox ----
engine = FaceProjectionEngine('衬砌', {}, (0.0, 0.0, 0.0))
face = engine.get_face_info('拱圈内壁')
assert face is not None
assert abs(face.width - 15708) < 1 and abs(face.height - 50000) < 1, \
    f"面尺寸不符预期: {face.width}x{face.height}"
print(f"衬砌拱圈内壁 face: center={face.center}, size={face.width:.1f}x{face.height:.1f}")

run_case("衬砌-小框(640x480图上200x200)", face, (100, 100, 300, 300), (640, 480))
run_case("衬砌-半图大框(640x480图上320x240)", face, (160, 120, 480, 360), (640, 480))
run_case("衬砌-整图框", face, (0, 0, 640, 480), (640, 480))

# ---- 用例2：多区域合计不超过总上限 ----
shadows = [photo_bbox_to_shadow(face, b, 640, 480, "裂缝")
           for b in [(0, 0, 640, 480), (0, 0, 640, 480), (0, 0, 640, 480), (0, 0, 640, 480)]]
pc = PointCloudGenerator(density=15.0, point_size=8.0)
pts = pc.generate(face, shadows)
assert len(pts) <= MAX_TOTAL, f"多区域总点数 {len(pts)} > {MAX_TOTAL}"
print(f"[PASS] 4个整图区域合计: 点数={len(pts)} <= 总上限 {MAX_TOTAL}")

# ---- 用例3：超大 face 100000x100000 ----
big_face = type(face)(
    face_name='超大面', plane='xz', center=(0, 0, 0), normal=(0, -1, 0),
    width=100000.0, height=100000.0, u_axis=(1, 0, 0), v_axis=(0, 0, 1))
run_case("超大面100000x100000-整图框", big_face, (0, 0, 640, 480), (640, 480))

# ---- 用例4：小面精度不受影响（间距不变）----
small_face = type(face)(
    face_name='小面', plane='xz', center=(0, 0, 0), normal=(0, -1, 0),
    width=600.0, height=450.0, u_axis=(1, 0, 0), v_axis=(0, 0, 1))
shadow = photo_bbox_to_shadow(small_face, (160, 120, 480, 360), 640, 480, "剥落")
pc = PointCloudGenerator(density=15.0, point_size=8.0)
pts = pc.generate(small_face, [shadow])
expect = max(1, int(300 / 15)) * max(1, int(225 / 15))
assert len(pts) == expect, f"小面点数 {len(pts)} != 预期 {expect}（不应被压缩）"
print(f"[PASS] 小面600x450局部框: 点数={len(pts)}（未被上限压缩，密度保持15mm）")

print("\nALL ASSERTIONS PASSED")
