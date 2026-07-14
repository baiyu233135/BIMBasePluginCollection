"""
根据 引桥桥墩.py 组件参数生成 CAD 图纸（DXF 格式）。
包含：正视图（沿 -y 看，x-z 投影）、侧视图（沿 -x 看，y-z 投影）、俯视图（沿 -z 看，x-y 投影）。
单位：cm，比例 1:1。
"""

import ezdxf

# ========== 组件参数（与 引桥桥墩.py 保持一致，单位 cm） ==========
cap_l = 1930.0        # 盖梁总长
cap_h = 300.0         # 盖梁总高
cap_w = 300.0         # 盖梁宽
col_d = 250.0         # 墩柱直径
col_s = 1140.0        # 墩柱间距
col_h = 1200.0        # 墩高
tie_n = 2             # 系梁根数

# 细部固定尺寸
boss_w = 30.0         # 顶部凸起水平宽度
boss_h = 50.0         # 顶部凸起高度
cap_bottom_w = 1390.0 # 盖梁底部宽度
chamfer_h = 120.0     # 斜边高度
tie_h = 200.0         # 系梁截面高度/直径
tie_start = 200.0     # 最上系梁顶面距墩柱顶距离
tie_step = 500.0      # 系梁竖向间距
tie_l = max(col_s - col_d, 100.0)  # 系梁长度

# 派生尺寸
half_l = cap_l / 2
half_bottom = cap_bottom_w / 2
mid_h = cap_h - boss_h
col_r = col_d / 2
tie_r = tie_h / 2

# 盖梁截面外轮廓（x-z 平面局部坐标，z 从墩顶 col_h 算起）
cap_outer_local = [
    (-half_bottom, 0),
    (half_bottom, 0),
    (half_l, chamfer_h),
    (half_l, cap_h),
    (-half_l, cap_h),
    (-half_l, chamfer_h),
]

# 盖梁截面内凹槽（顶部凸起之间的缺口）
cap_inner_local = [
    (-half_l + boss_w, mid_h),
    (half_l - boss_w, mid_h),
    (half_l - boss_w, cap_h),
    (-half_l + boss_w, cap_h),
]

# 系梁中心 z 坐标（从墩顶向下排列）
tie_z_centers = []
for i in range(tie_n):
    z_top = col_h - tie_start - i * tie_step
    z = z_top - tie_h / 2
    if z < 0:
        z = 0
    tie_z_centers.append(z + tie_h / 2)

# ========== 创建 DXF 文档 ==========
doc = ezdxf.new("R2010")
doc.units = ezdxf.units.CM
msp = doc.modelspace()

# 设置图层
layers = {
    "轮廓": {"color": 0},
    "中心线": {"color": 1, "linetype": "CENTER"},
    "标注": {"color": 3},
    "文字": {"color": 4},
}
for name, opts in layers.items():
    if name not in doc.layers:
        doc.layers.add(name, color=opts.get("color", 0), linetype=opts.get("linetype", "CONTINUOUS"))


def add_polyline(points, closed=True, layer="轮廓"):
    if len(points) < 2:
        return
    msp.add_lwpolyline(points, close=closed, dxfattribs={"layer": layer})


def add_circle(center, radius, layer="轮廓"):
    msp.add_circle(center, radius, dxfattribs={"layer": layer})


def add_line(p1, p2, layer="轮廓"):
    msp.add_line(p1, p2, dxfattribs={"layer": layer})


def add_dim(p1, p2, base, angle=0, text=None, layer="标注"):
    dim = msp.add_linear_dim(
        base=base,
        p1=p1,
        p2=p2,
        angle=angle,
        dxfattribs={"layer": layer},
    )
    if text is not None:
        dim.set_text(text)
    dim.render()


def add_text(text, insert, height=60, layer="文字"):
    msp.add_text(text, dxfattribs={"height": height, "layer": layer, "insert": insert})


# ========== 视图布局 ==========
front_origin = (0, 0)
side_origin = (4000, 0)
top_origin = (0, 2500)

# ---------------- 正视图（x-z 平面） ----------------
# 盖梁正视图完整轮廓（外轮廓 + 凹槽合并为一条闭合多段线，避免顶边重复）
cap_front_profile = [
    (-half_bottom, col_h + 0),
    (half_bottom, col_h + 0),
    (half_l, col_h + chamfer_h),
    (half_l, col_h + cap_h),
    (half_l - boss_w, col_h + cap_h),
    (half_l - boss_w, col_h + mid_h),
    (-half_l + boss_w, col_h + mid_h),
    (-half_l + boss_w, col_h + cap_h),
    (-half_l, col_h + cap_h),
    (-half_l, col_h + chamfer_h),
]
add_polyline(cap_front_profile, closed=True, layer="轮廓")

# 墩柱（圆柱正视图为矩形）
for cx in [-col_s / 2, col_s / 2]:
    rect = [
        (cx - col_r, 0),
        (cx + col_r, 0),
        (cx + col_r, col_h),
        (cx - col_r, col_h),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 系梁（圆柱正视图为矩形）
for cz in tie_z_centers:
    rect = [
        (-tie_l / 2, cz - tie_r),
        (tie_l / 2, cz - tie_r),
        (tie_l / 2, cz + tie_r),
        (-tie_l / 2, cz + tie_r),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 正视图尺寸标注
# 盖梁总长
add_dim((-half_l, col_h + cap_h), (half_l, col_h + cap_h), base=(-half_l, col_h + cap_h + 150), angle=0, text="盖梁总长 1930")
# 盖梁总高
add_dim((half_l, col_h), (half_l, col_h + cap_h), base=(half_l + 200, col_h), angle=90, text="盖梁总高 300")
# 盖梁底部宽度
add_dim((-half_bottom, col_h), (half_bottom, col_h), base=(-half_bottom, col_h - 150), angle=0, text="盖梁底宽 1390")
# 墩柱直径
add_dim((-col_s / 2 - col_r, 0), (-col_s / 2 + col_r, 0), base=(-col_s / 2 - col_r, -150), angle=0, text="墩柱直径 250")
# 墩柱间距
add_dim((-col_s / 2, -300), (col_s / 2, -300), base=(-col_s / 2, -400), angle=0, text="墩柱间距 1140")
# 墩高
add_dim((col_s / 2 + col_r, 0), (col_s / 2 + col_r, col_h), base=(col_s / 2 + col_r + 200, 0), angle=90, text="墩高 1200")
# 系梁长度
if tie_z_centers:
    add_dim((-tie_l / 2, tie_z_centers[0]), (tie_l / 2, tie_z_centers[0]), base=(-tie_l / 2, tie_z_centers[0] + 150), angle=0, text="系梁长 890")
# 系梁截面高
add_dim((tie_l / 2, tie_z_centers[0] - tie_r), (tie_l / 2, tie_z_centers[0] + tie_r), base=(tie_l / 2 + 150, tie_z_centers[0] - tie_r), angle=90, text="系梁高 200")

add_text("正视图", (-100, -600), layer="文字")

# ---------------- 侧视图（y-z 平面） ----------------
sx, sz = side_origin

# 盖梁侧视：沿 y 方向均匀拉伸，显示为矩形 y=-cap_w/2~cap_w/2, z=col_h~col_h+cap_h
cap_side = [
    (sx + (-cap_w / 2), sz + col_h),
    (sx + (cap_w / 2), sz + col_h),
    (sx + (cap_w / 2), sz + (col_h + cap_h)),
    (sx + (-cap_w / 2), sz + (col_h + cap_h)),
]
add_polyline(cap_side, closed=True, layer="轮廓")

# 墩柱侧视：两圆柱重叠为一个矩形，y=-col_r~col_r, z=0~col_h
col_side = [
    (sx + (-col_r), sz + 0),
    (sx + col_r, sz + 0),
    (sx + col_r, sz + col_h),
    (sx + (-col_r), sz + col_h),
]
add_polyline(col_side, closed=True, layer="轮廓")

# 系梁侧视：y=-tie_r~tie_r, z=cz±tie_r
for cz in tie_z_centers:
    rect = [
        (sx + (-tie_r), sz + (cz - tie_r)),
        (sx + tie_r, sz + (cz - tie_r)),
        (sx + tie_r, sz + (cz + tie_r)),
        (sx + (-tie_r), sz + (cz + tie_r)),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 侧视图尺寸标注
# 盖梁宽
add_dim((sx + (-cap_w / 2), sz + col_h + cap_h + 100), (sx + (cap_w / 2), sz + col_h + cap_h + 100), base=(sx + (-cap_w / 2), sz + col_h + cap_h + 200), angle=0, text="盖梁宽 300")
# 墩柱直径
add_dim((sx + (-col_r), sz - 150), (sx + col_r, sz - 150), base=(sx + (-col_r), sz - 250), angle=0, text="墩柱直径 250")
# 墩高
add_dim((sx + col_r, sz + 0), (sx + col_r, sz + col_h), base=(sx + col_r + 150, sz + 0), angle=90, text="墩高 1200")
# 系梁截面高
if tie_z_centers:
    add_dim((sx + tie_r, sz + (tie_z_centers[0] - tie_r)), (sx + tie_r, sz + (tie_z_centers[0] + tie_r)), base=(sx + tie_r + 150, sz + (tie_z_centers[0] - tie_r)), angle=90, text="系梁高 200")

add_text("侧视图", (sx - 100, sz - 600), layer="文字")

# ---------------- 俯视图（x-y 平面） ----------------
tx, ty = top_origin

# 盖梁俯视：x=-half_l~half_l, y=-cap_w/2~cap_w/2
cap_top = [
    (tx + (-half_l), ty + (-cap_w / 2)),
    (tx + half_l, ty + (-cap_w / 2)),
    (tx + half_l, ty + (cap_w / 2)),
    (tx + (-half_l), ty + (cap_w / 2)),
]
add_polyline(cap_top, closed=True, layer="轮廓")

# 墩柱俯视：2 个圆
for cx in [-col_s / 2, col_s / 2]:
    add_circle((tx + cx, ty + 0), col_r, layer="轮廓")

# 系梁俯视：多根系梁在 x-y 平面投影完全重合，只画一个矩形示意
if tie_z_centers:
    rect = [
        (tx + (-tie_l / 2), ty + (-tie_r)),
        (tx + (tie_l / 2), ty + (-tie_r)),
        (tx + (tie_l / 2), ty + tie_r),
        (tx + (-tie_l / 2), ty + tie_r),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 俯视图尺寸标注
# 盖梁总长
add_dim((tx + (-half_l), ty + (-cap_w / 2) - 150), (tx + half_l, ty + (-cap_w / 2) - 150), base=(tx + (-half_l), ty + (-cap_w / 2) - 300), angle=0, text="盖梁总长 1930")
# 盖梁宽
add_dim((tx + half_l + 150, ty + (-cap_w / 2)), (tx + half_l + 150, ty + (cap_w / 2)), base=(tx + half_l + 300, ty + (-cap_w / 2)), angle=90, text="盖梁宽 300")
# 墩柱间距
add_dim((tx + (-col_s / 2), ty - col_r - 150), (tx + (col_s / 2), ty - col_r - 150), base=(tx + (-col_s / 2), ty - col_r - 300), angle=0, text="墩柱间距 1140")
# 系梁长度
add_dim((tx + (-tie_l / 2), ty + tie_r + 150), (tx + (tie_l / 2), ty + tie_r + 150), base=(tx + (-tie_l / 2), ty + tie_r + 300), angle=0, text="系梁长 890")

add_text("俯视图", (tx - 100, ty - cap_w / 2 - 500), layer="文字")

# ========== 标题与说明 ==========
add_text("引桥桥墩 三视图（单位：cm，比例 1:1）", (tx + 500, ty + cap_w / 2 + 400), height=100, layer="文字")

legend_x, legend_y = tx + half_l + 600, ty + cap_w / 2 - 100
add_text("图例：", (legend_x, legend_y), height=70, layer="文字")
add_text("1. 盖梁：总长 1930，总高 300，宽 300", (legend_x, legend_y - 130), height=50, layer="文字")
add_text("2. 墩柱：2 根，直径 250，高 1200，间距 1140", (legend_x, legend_y - 210), height=50, layer="文字")
add_text("3. 系梁：2 根，截面 200×200，长 890", (legend_x, legend_y - 290), height=50, layer="文字")

# ========== 保存文件 ==========
output_path = r"c:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\组件测试\引桥桥墩.dxf"
doc.saveas(output_path)
print(f"图纸已保存：{output_path}")
