# -*- coding: utf-8 -*-
"""
根据 门式桥墩.py 组件参数生成 CAD 图纸（DXF 格式）。
包含：正视图（沿 -y 看，x-z 投影）、侧视图（沿 -x 看，y-z 投影）、俯视图（沿 -z 看，x-y 投影）。
单位：cm，比例 1:1。
"""

import ezdxf

# ========== 组件参数（与 门式桥墩.py 保持一致，单位 cm） ==========
cap_l = 4700.0        # 盖梁总长
cap_h = 400.0         # 盖梁总高
cap_w = 1000.0        # 盖梁宽
col_h = 5000.0        # 墩高
col_s = 3500.0        # 墩柱间距（两柱中心间距）
top_w = 1200.0        # 柱顶宽（X 向）
bot_w = 1400.0        # 柱底宽（X 向）
top_d = 1000.0        # 柱顶厚（Y 向）
bot_d = 1200.0        # 柱底厚（Y 向）
tie_n = 1             # 系梁根数

# 细部固定尺寸
pad_l = 400.0         # 垫石平面边长
pad_h = 80.0          # 垫石高
chamfer = 300.0       # 八边形倒角
tie_h = 400.0         # 系梁高
tie_d = 400.0         # 系梁深（Y 向）

# 派生尺寸
half_l = cap_l / 2
half_w = cap_w / 2
tie_top = col_h                        # 系梁顶面贴盖梁底
tie_zc = tie_top - tie_h / 2           # 系梁中心 z
w_at = bot_w + (top_w - bot_w) * (tie_zc / col_h)  # 系梁高度处柱身 X 向宽度
tie_l = max(col_s - w_at, 100.0)       # 系梁长度（与两柱内侧面相接）

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
    # dimscale 放大默认标注样式（文字 2.5cm→约 62cm），保证 1:1 大图幅下标注可读
    dim = msp.add_linear_dim(
        base=base,
        p1=p1,
        p2=p2,
        angle=angle,
        override={"dimscale": 25.0},
        dxfattribs={"layer": layer},
    )
    if text is not None:
        dim.set_text(text)
    dim.render()


def add_text(text, insert, height=60, layer="文字"):
    msp.add_text(text, dxfattribs={"height": height, "layer": layer, "insert": insert})


def octagon_points(cx, cy, w, d, c):
    """XY 平面内的倒角八边形：中心 (cx,cy)，宽 w（X），深 d（Y），倒角 c"""
    hw, hd = w / 2, d / 2
    c = min(c, hw, hd)
    return [
        (cx - hw + c, cy - hd), (cx + hw - c, cy - hd),
        (cx + hw, cy - hd + c), (cx + hw, cy + hd - c),
        (cx + hw - c, cy + hd), (cx - hw + c, cy + hd),
        (cx - hw, cy + hd - c), (cx - hw, cy - hd + c),
    ]


# ========== 视图布局 ==========
front_origin = (0, 0)
side_origin = (4000, 0)
top_origin = (0, 6800)

# ---------------- 正视图（x-z 平面） ----------------
# 盖梁正视图：矩形 x=-half_l~half_l, z=col_h~col_h+col_h?  -> z=col_h~col_h+cap_h
cap_front = [
    (-half_l, col_h),
    (half_l, col_h),
    (half_l, col_h + cap_h),
    (-half_l, col_h + cap_h),
]
add_polyline(cap_front, closed=True, layer="轮廓")

# 垫石×2：位于柱顶中心的盖梁顶面
for cx in [-col_s / 2, col_s / 2]:
    rect = [
        (cx - pad_l / 2, col_h + cap_h),
        (cx + pad_l / 2, col_h + cap_h),
        (cx + pad_l / 2, col_h + cap_h + pad_h),
        (cx - pad_l / 2, col_h + cap_h + pad_h),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 墩柱×2：变截面（梯形）正视图，底宽 bot_w → 顶宽 top_w
for cx in [-col_s / 2, col_s / 2]:
    trapezoid = [
        (cx - bot_w / 2, 0),
        (cx + bot_w / 2, 0),
        (cx + top_w / 2, col_h),
        (cx - top_w / 2, col_h),
    ]
    add_polyline(trapezoid, closed=True, layer="轮廓")

# 系梁：贴盖梁底，z=tie_top-tie_h~tie_top
tie_front = [
    (-tie_l / 2, tie_top - tie_h),
    (tie_l / 2, tie_top - tie_h),
    (tie_l / 2, tie_top),
    (-tie_l / 2, tie_top),
]
add_polyline(tie_front, closed=True, layer="轮廓")

# 正视图尺寸标注
# 盖梁总长
add_dim((-half_l, col_h + cap_h + pad_h), (half_l, col_h + cap_h + pad_h), base=(-half_l, col_h + cap_h + pad_h + 150), angle=0, text="盖梁总长 4700")
# 盖梁总高
add_dim((-half_l, col_h), (-half_l, col_h + cap_h), base=(-half_l - 250, col_h), angle=90, text="盖梁总高 400")
# 墩高
add_dim((col_s / 2 + bot_w / 2, 0), (col_s / 2 + bot_w / 2, col_h), base=(col_s / 2 + bot_w / 2 + 250, 0), angle=90, text="墩高 5000")
# 柱底宽
add_dim((col_s / 2 - bot_w / 2, 0), (col_s / 2 + bot_w / 2, 0), base=(col_s / 2 - bot_w / 2, -200), angle=0, text="柱底宽 1400")
# 墩柱间距
add_dim((-col_s / 2, -450), (col_s / 2, -450), base=(-col_s / 2, -600), angle=0, text="墩柱间距 3500")

add_text("正视图", (-100, -850), layer="文字")

# ---------------- 侧视图（y-z 平面） ----------------
sx, sz = side_origin

# 盖梁侧视：y=-half_w~half_w, z=col_h~col_h+cap_h
cap_side = [
    (sx + (-half_w), sz + col_h),
    (sx + half_w, sz + col_h),
    (sx + half_w, sz + (col_h + cap_h)),
    (sx + (-half_w), sz + (col_h + cap_h)),
]
add_polyline(cap_side, closed=True, layer="轮廓")

# 垫石侧视：两垫石重叠为一个矩形
pad_side = [
    (sx + (-pad_l / 2), sz + col_h + cap_h),
    (sx + pad_l / 2, sz + col_h + cap_h),
    (sx + pad_l / 2, sz + (col_h + cap_h + pad_h)),
    (sx + (-pad_l / 2), sz + (col_h + cap_h + pad_h)),
]
add_polyline(pad_side, closed=True, layer="轮廓")

# 墩柱侧视：两柱重叠为一个梯形，底厚 bot_d → 顶厚 top_d
col_side = [
    (sx + (-bot_d / 2), sz + 0),
    (sx + bot_d / 2, sz + 0),
    (sx + top_d / 2, sz + col_h),
    (sx + (-top_d / 2), sz + col_h),
]
add_polyline(col_side, closed=True, layer="轮廓")

# 系梁侧视：y=-tie_d/2~tie_d/2, z=tie_top-tie_h~tie_top
tie_side = [
    (sx + (-tie_d / 2), sz + (tie_top - tie_h)),
    (sx + tie_d / 2, sz + (tie_top - tie_h)),
    (sx + tie_d / 2, sz + tie_top),
    (sx + (-tie_d / 2), sz + tie_top),
]
add_polyline(tie_side, closed=True, layer="轮廓")

# 侧视图尺寸标注
# 盖梁宽
add_dim((sx + (-half_w), sz + col_h + cap_h + pad_h), (sx + half_w, sz + col_h + cap_h + pad_h), base=(sx + (-half_w), sz + col_h + cap_h + pad_h + 150), angle=0, text="盖梁宽 1000")
# 柱底厚
add_dim((sx + (-bot_d / 2), sz - 200), (sx + bot_d / 2, sz - 200), base=(sx + (-bot_d / 2), sz - 350), angle=0, text="柱底厚 1200")
# 系梁高
add_dim((sx + tie_d / 2, sz + (tie_top - tie_h)), (sx + tie_d / 2, sz + tie_top), base=(sx + tie_d / 2 + 150, sz + (tie_top - tie_h)), angle=90, text="系梁高 400")

add_text("侧视图", (sx - 100, sz - 850), layer="文字")

# ---------------- 俯视图（x-y 平面） ----------------
tx, ty = top_origin

# 盖梁俯视：x=-half_l~half_l, y=-half_w~half_w
cap_top = [
    (tx + (-half_l), ty + (-half_w)),
    (tx + half_l, ty + (-half_w)),
    (tx + half_l, ty + half_w),
    (tx + (-half_l), ty + half_w),
]
add_polyline(cap_top, closed=True, layer="轮廓")

# 墩柱俯视：2 个柱顶八边形（1200×1000，倒角 300）
for cx in [-col_s / 2, col_s / 2]:
    add_polyline(octagon_points(tx + cx, ty, top_w, top_d, chamfer), closed=True, layer="轮廓")

# 垫石俯视：2 个矩形（400×400）
for cx in [-col_s / 2, col_s / 2]:
    rect = [
        (tx + cx - pad_l / 2, ty + (-pad_l / 2)),
        (tx + cx + pad_l / 2, ty + (-pad_l / 2)),
        (tx + cx + pad_l / 2, ty + pad_l / 2),
        (tx + cx - pad_l / 2, ty + pad_l / 2),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 俯视图尺寸标注
# 柱顶宽（右柱八边形 X 向宽度）
add_dim((tx + col_s / 2 - top_w / 2, ty + half_w), (tx + col_s / 2 + top_w / 2, ty + half_w), base=(tx + col_s / 2 - top_w / 2, ty + half_w + 150), angle=0, text="柱顶宽 1200")
# 墩柱间距
add_dim((tx + (-col_s / 2), ty - half_w - 150), (tx + col_s / 2, ty - half_w - 150), base=(tx + (-col_s / 2), ty - half_w - 300), angle=0, text="墩柱间距 3500")
# 盖梁总长
add_dim((tx + (-half_l), ty - half_w - 600), (tx + half_l, ty - half_w - 600), base=(tx + (-half_l), ty - half_w - 750), angle=0, text="盖梁总长 4700")
# 盖梁宽
add_dim((tx + half_l + 150, ty + (-half_w)), (tx + half_l + 150, ty + half_w), base=(tx + half_l + 300, ty + (-half_w)), angle=90, text="盖梁宽 1000")

add_text("俯视图", (tx - 100, ty - half_w - 1050), layer="文字")

# ========== 标题与说明 ==========
add_text("门式桥墩 三视图（单位：cm，比例 1:1）", (tx + 500, ty + half_w + 500), height=100, layer="文字")

legend_x, legend_y = tx + half_l + 700, ty + half_w - 100
add_text("图例：", (legend_x, legend_y), height=70, layer="文字")
add_text("1. 盖梁：总长 4700，总高 400，宽 1000", (legend_x, legend_y - 130), height=50, layer="文字")
add_text("2. 垫石：2 块，平面 400×400，高 80", (legend_x, legend_y - 210), height=50, layer="文字")
add_text("3. 墩柱：2 根，变截面八边形（底 1400×1200 → 顶 1200×1000），高 5000，间距 3500", (legend_x, legend_y - 290), height=50, layer="文字")
add_text("4. 系梁：1 根，截面 400×400，长 2292", (legend_x, legend_y - 370), height=50, layer="文字")

# ========== 保存文件 ==========
output_path = r"c:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\组件测试\门式桥墩.dxf"
doc.saveas(output_path)
print(f"图纸已保存：{output_path}")
