# -*- coding: utf-8 -*-
"""离线验证（不依赖 BIMBase/pyp3d）：
1. 组件成品/隧道.py 几何沿 Y 拉伸（Y∈[0,L]，XZ 断面，洞口朝 ±Y）
2. 衬砌拱圈内壁投影点云逐点落在真实弧面上（距内弧 = 2mm 法向偏移 + 半点尺寸），
   颜色与病害类型一致，点数在上限内
3. disease_marker 点云 'xyz' 模式编码/解码与几何重建
"""
import math
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================
# pyp3d 最小 stub（记录几何包围盒；Cube 为 [0,1]^3 角点基）
# ============================================================

class _Geom:
    def __init__(self, lo, hi):
        self.lo = list(lo)
        self.hi = list(hi)

    def color(self, *a):
        return self

    def material(self, *a):
        return self

    def __add__(self, o):
        return _combine(self, o)

    def __sub__(self, o):
        # 布尔减结果的包围盒 ⊆ 被减体，直接返回被减体（保守且对本断言足够）
        return _Geom(self.lo, self.hi)


def _combine(*gs):
    lo = [min(g.lo[i] for g in gs) for i in range(3)]
    hi = [max(g.hi[i] for g in gs) for i in range(3)]
    return _Geom(lo, hi)


def _bez2(p1, p2, p3, n=32):
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p1[0] + 2 * t * (1 - t) * p2[0] + t ** 2 * p3[0]
        y = (1 - t) ** 2 * p1[1] + 2 * t * (1 - t) * p2[1] + t ** 2 * p3[1]
        pts.append((x, y))
    return pts


class _TF:
    """仿射变换（3x3 矩阵 + 平移），支持组合（左乘）与作用于几何/断面"""
    def __init__(self, M, t):
        self.M = M  # 3x3 行主序
        self.t = t

    def _apply(self, p):
        x, y, z = p
        M, t = self.M, self.t
        return (M[0][0] * x + M[0][1] * y + M[0][2] * z + t[0],
                M[1][0] * x + M[1][1] * y + M[1][2] * z + t[1],
                M[2][0] * x + M[2][1] * y + M[2][2] * z + t[2])

    def __mul__(self, g):
        if isinstance(g, _TF):
            # 组合：self ∘ g
            M = [[sum(self.M[i][k] * g.M[k][j] for k in range(3))
                  for j in range(3)] for i in range(3)]
            t = self._apply(g.t)
            return _TF(M, t)
        if isinstance(g, _Section):
            g = g.to_geom()
        corners = [(x, y, z)
                   for x in (g.lo[0], g.hi[0])
                   for y in (g.lo[1], g.hi[1])
                   for z in (g.lo[2], g.hi[2])]
        pts = [self._apply(c) for c in corners]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        return _Geom(lo, hi)


class _Section:
    """XY 平面内的 2D 断面（含 Arc 采样点）"""
    def __init__(self, pts):
        self.pts = pts

    def to_geom(self):
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        return _Geom((min(xs), min(ys), 0.0), (max(xs), max(ys), 0.0))

    def __rmul__(self, tf):
        return tf * self.to_geom()


def _make_pyp3d_stub():
    m = types.ModuleType('pyp3d')

    m.Vec2 = lambda x, y: (float(x), float(y))
    m.Vec3 = lambda x, y, z: (float(x), float(y), float(z))
    m.pi = math.pi

    def Arc(p1, p2, p3):
        return _bez2(p1, p2, p3)

    def Section(*items):
        pts = []
        for it in items:
            if isinstance(it, list):      # Arc 展开
                pts.extend(it)
            else:
                pts.append(it)
        return _Section(pts)

    def Loft(a, b):
        if isinstance(a, _Section):
            a = a.to_geom()
        if isinstance(b, _Section):
            b = b.to_geom()
        return _combine(a, b)

    def Cone(v1, v2, r1, r2):
        r = max(r1, r2)
        lo = [min(v1[i], v2[i]) - r for i in range(3)]
        hi = [max(v1[i], v2[i]) + r for i in range(3)]
        return _Geom(lo, hi)

    def Cube():
        return _Geom((0, 0, 0), (1, 1, 1))

    def trans(x, y, z):
        return _TF([[1, 0, 0], [0, 1, 0], [0, 0, 1]], (x, y, z))

    def scale(x, y, z):
        return _TF([[x, 0, 0], [0, y, 0], [0, 0, z]], (0, 0, 0))

    def rotate(axis, angle):
        assert axis == (1.0, 0.0, 0.0) and abs(angle - math.pi / 2) < 1e-9
        # 绕 X 轴 +90°: (x,y,z) → (x,-z,y)
        return _TF([[1, 0, 0], [0, 0, -1], [0, 1, 0]], (0, 0, 0))

    def Combine(*gs):
        return _combine(*gs)

    class AttrFn:
        def __call__(self, v, **kw):
            return v
    Attr = AttrFn()

    class Component(dict):
        def __init__(self):
            super().__init__()

    m.Arc = Arc
    m.Section = Section
    m.Loft = Loft
    m.Cone = Cone
    m.Cube = Cube
    m.trans = trans
    m.translate = trans
    m.scale = scale
    m.rotate = rotate
    m.Combine = Combine
    m.Attr = Attr
    m.Component = Component
    m.export = lambda fn: fn
    m.place = lambda comp: None
    return m


# ============================================================
# 用例1：隧道组件沿 Y 拉伸
# ============================================================
sys.modules['pyp3d'] = _make_pyp3d_stub()
src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   '..', '组件成品', '隧道.py')
ns = {'__name__': 'tunnel_mod'}
with open(src, encoding='utf-8') as f:
    exec(compile(f.read(), src, 'exec'), ns)
comp = ns['隧道']()
geom = comp['隧道']

W, H, w, h, L = 10000, 5000, 350, 800, 50000
eps = 1.0
print(f"隧道组件包围盒: X[{geom.lo[0]:.0f},{geom.hi[0]:.0f}] "
      f"Y[{geom.lo[1]:.0f},{geom.hi[1]:.0f}] Z[{geom.lo[2]:.0f},{geom.hi[2]:.0f}]")
assert abs(geom.lo[1] - 0) < eps and abs(geom.hi[1] - L) < eps, \
    f"隧道未沿 Y 拉伸: Y∈[{geom.lo[1]}, {geom.hi[1]}], 期望 [0, {L}]"
assert geom.lo[0] >= -(W / 2 + w) - eps and geom.hi[0] <= (W / 2 + w) + eps, \
    f"断面横向(X)超出预期: [{geom.lo[0]}, {geom.hi[0]}]"
assert geom.lo[2] >= -(h + w) - eps and geom.hi[2] <= (H + w) + eps, \
    f"断面竖向(Z)超出预期: [{geom.lo[2]}, {geom.hi[2]}]"
print(f"[PASS] 隧道轴线沿 Y：Y∈[0,{L}]，XZ 断面 X∈[{geom.lo[0]:.0f},{geom.hi[0]:.0f}] "
      f"Z∈[{geom.lo[2]:.0f},{geom.hi[2]:.0f}]，洞口朝 ±Y")

# ============================================================
# 用例2：衬砌拱圈内壁点云逐点落在真实弧面上
# ============================================================
from face_projection import (
    FaceProjectionEngine, PointCloudGenerator, photo_bbox_to_shadow,
    DISEASE_COLOR_MAP,
)

base = (1000.0, 2000.0, 3000.0)
engine = FaceProjectionEngine('衬砌', {}, base)
face = engine.get_face_info('拱圈内壁')
assert face is not None and face.surface_fn is not None, "拱圈内壁缺少 surface_fn"
print(f"拱圈内壁 face: center={face.center}, size={face.width:.1f}x{face.height:.1f}, "
      f"plane={face.plane}")
# 轴向语义：面中心在隧道中段 y=base_y+L/2，拱顶高 base_z+H
assert abs(face.center[1] - (base[1] + L / 2)) < eps
assert abs(face.center[2] - (base[2] + H)) < eps

# 真实内弧（与 surface_fn 同一精确圆；距离 = |dist(点,圆心) - R|）
P1, P2, P3 = (-W / 2, 0.0), (0.0, float(H)), (W / 2, 0.0)


def dist_to_bez(x, z, p1, p2, p3, coarse=4096, refine=200):
    """点到三点圆弧（pyp3d Arc 语义，精确圆）的距离。
    face_projection 已改用精确圆解析计算，这里以 |dist(点,圆心) - R| 为基准。"""
    from face_projection import FaceProjectionEngine
    c, rho, _s, _psi0 = FaceProjectionEngine._circle_through(p1, p2, p3)
    return abs(math.hypot(x, z - c) - rho)


for disease, bbox in [("裂缝", (160, 120, 480, 360)),
                      ("渗水", (100, 100, 300, 300)),
                      ("剥落", (0, 0, 640, 480)),
                      ("其他", (200, 150, 400, 350))]:
    shadow = photo_bbox_to_shadow(face, bbox, 640, 480, disease)
    pc = PointCloudGenerator(density=15.0, point_size=8.0)
    pts = pc.generate_surface(face, [shadow])
    n = len(pts)
    assert 0 < n <= pc.max_points_per_shadow, f"{disease}: 点数 {n} 超限"
    expect_off = 2.0 + pc.point_size / 2.0   # 2mm 法向偏移 + 半点尺寸
    expect_rgb = DISEASE_COLOR_MAP[disease]
    max_err = 0.0
    for px, py, pz, rgb in pts:
        assert rgb == expect_rgb, f"{disease}: 颜色 {rgb} != {expect_rgb}"
        wx, wy, wz = (face.center[0] + px, face.center[1] + py, face.center[2] + pz)
        # 截面坐标（相对拱心水平面）落在内弧法向偏移 expect_off 处
        d = dist_to_bez(wx - base[0], wz - base[2], P1, P2, P3)
        err = abs(d - expect_off)
        max_err = max(max_err, err)
        # 纵向坐标在隧道范围内
        assert base[1] - eps <= wy <= base[1] + L + eps, f"点 y={wy} 超出隧道长度范围"
    assert max_err < 5.0, f"{disease}: 点距内弧偏差 {max_err:.2f}mm >= 5mm"
    print(f"[PASS] 拱圈内壁-{disease}: 点数={n} 颜色={rgb} "
          f"距内弧={expect_off:.1f}mm±{max_err:.2f}mm (<5mm)")

# 仰拱内壁同样逐点贴弧
face_inv = engine.get_face_info('仰拱内壁')
assert face_inv is not None and face_inv.surface_fn is not None
shadow = photo_bbox_to_shadow(face_inv, (160, 120, 480, 360), 640, 480, "渗水")
pts = pc.generate_surface(face_inv, [shadow])
max_err = max(abs(dist_to_bez(face_inv.center[0] + px - base[0],
                              face_inv.center[2] + pz - base[2],
                              (-W / 2, 0.0), (0.0, -float(h)), (W / 2, 0.0))
                  - expect_off)
              for px, py, pz, rgb in pts)
assert max_err < 5.0, f"仰拱内壁: 点距内弧偏差 {max_err:.2f}mm >= 5mm"
print(f"[PASS] 仰拱内壁-渗水: 点数={len(pts)} 距内弧={expect_off:.1f}mm±{max_err:.2f}mm (<5mm)")

# ============================================================
# 用例3：disease_marker 点云 'xyz' 模式（编码/解码 + 几何位置）
# ============================================================
import disease_marker as dm

assert dm._DiseasePointCloudMarker is not None, "stub 下 _DiseasePointCloudMarker 未定义"
sample = [(12.5, -34.25, 56.75, (255, 0, 0)), (-100.0, 200.0, -50.5, (0, 0, 255))]
marker = dm._DiseasePointCloudMarker(x=base[0], y=base[1], z=base[2],
                                     points=sample, point_size=8.0,
                                     face_plane='xyz', disease_type='裂缝')
dec = dm._DiseasePointCloudMarker._decode_points(marker['points_data'])
assert len(dec) == 2
for (a, b) in zip(dec, sample):
    assert abs(a[0] - b[0]) < 0.01 and abs(a[1] - b[1]) < 0.01 and abs(a[2] - b[2]) < 0.01
    assert a[3] == b[3]
cloud = marker['点云']
# 几何包围盒 = base + 点坐标 + [0,point_size]（Cube 角点基）
assert abs(cloud.lo[0] - (base[0] - 100.0)) < 0.5 and abs(cloud.hi[0] - (base[0] + 12.5 + 8)) < 0.5
assert abs(cloud.lo[1] - (base[1] - 34.25)) < 0.5 and abs(cloud.hi[1] - (base[1] + 200.0 + 8)) < 0.5
assert abs(cloud.lo[2] - (base[2] - 50.5)) < 0.5 and abs(cloud.hi[2] - (base[2] + 56.75 + 8)) < 0.5
print(f"[PASS] disease_marker 'xyz' 模式: 编码/解码一致，点云包围盒 = 基准+真3D坐标 "
      f"X[{cloud.lo[0]:.1f},{cloud.hi[0]:.1f}]")

print("\nALL ASSERTIONS PASSED")
