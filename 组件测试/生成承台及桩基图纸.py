# -*- coding: utf-8 -*-
"""
根据 承台及桩基.py 组件参数生成 CAD 图纸（DXF 格式）。
包含：正视图（沿 -y 看，x-z 投影）、侧视图（沿 -x 看，y-z 投影）、俯视图（沿 -z 看，x-y 投影）。
单位：cm，比例 1:1。
"""

import ezdxf

# ========== 组件参数（与 承台及桩基.py 保持一致，单位 cm） ==========
cap_l = 5500.0        # 承台长（X 向）
cap_w = 2350.0        # 承台宽（Y 向）
cap_h = 500.0         # 承台高
pile_d = 250.0        # 桩径
pile_l = 5000.0       # 桩长
spacing = 630.0       # 桩间距（桩中心间距）
n_col = 9             # 桩列数（X 向桩数）
n_row = 4             # 桩排数（Y 向桩数）

# 派生尺寸
half_l = cap_l / 2
half_w = cap_w / 2
pile_r = pile_d / 2
x0 = -(n_col - 1) * spacing / 2   # 首列桩中心 x
y0 = -(n_row - 1) * spacing / 2   # 首排桩中心 y
pile_xs = [x0 + i * spacing for i in range(n_col)]
pile_ys = [y0 + j * spacing for j in range(n_row)]

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


# ========== 视图布局 ==========
front_origin = (0, 0)
side_origin = (4500, 0)
top_origin = (0, 2000)

# ---------------- 正视图（x-z 平面） ----------------
# 承台正视图：矩形 x=-half_l~half_l, z=0~cap_h
cap_front = [
    (-half_l, 0),
    (half_l, 0),
    (half_l, cap_h),
    (-half_l, cap_h),
]
add_polyline(cap_front, closed=True, layer="轮廓")

# 桩正视图：9 根桩（圆柱正视图为矩形），x 向均布，z=-pile_l~0
for x in pile_xs:
    rect = [
        (x - pile_r, -pile_l),
        (x + pile_r, -pile_l),
        (x + pile_r, 0),
        (x - pile_r, 0),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 正视图尺寸标注
# 承台长
add_dim((-half_l, cap_h), (half_l, cap_h), base=(-half_l, cap_h + 150), angle=0, text="承台长 5500")
# 承台高
add_dim((half_l, 0), (half_l, cap_h), base=(half_l + 250, 0), angle=90, text="承台高 500")
# 桩长（最右一根桩）
add_dim((pile_xs[-1] + pile_r, -pile_l), (pile_xs[-1] + pile_r, 0), base=(pile_xs[-1] + pile_r + 200, -pile_l), angle=90, text="桩长 5000")
# 桩径（最左一根桩底）
add_dim((pile_xs[0] - pile_r, -pile_l), (pile_xs[0] + pile_r, -pile_l), base=(pile_xs[0] - pile_r, -pile_l - 200), angle=0, text="桩径 250")
# 桩间距（最左两根桩中心）
add_dim((pile_xs[0], -pile_l - 450), (pile_xs[1], -pile_l - 450), base=(pile_xs[0], -pile_l - 600), angle=0, text="桩间距 630")

add_text("正视图", (-100, -pile_l - 900), layer="文字")

# ---------------- 侧视图（y-z 平面） ----------------
sx, sz = side_origin

# 承台侧视：y=-half_w~half_w, z=0~cap_h
cap_side = [
    (sx + (-half_w), sz + 0),
    (sx + half_w, sz + 0),
    (sx + half_w, sz + cap_h),
    (sx + (-half_w), sz + cap_h),
]
add_polyline(cap_side, closed=True, layer="轮廓")

# 桩侧视：4 根桩（同排桩投影重叠，按 y 向 4 个位置绘制）
for y in pile_ys:
    rect = [
        (sx + y - pile_r, sz + (-pile_l)),
        (sx + y + pile_r, sz + (-pile_l)),
        (sx + y + pile_r, sz + 0),
        (sx + y - pile_r, sz + 0),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 侧视图尺寸标注
# 承台宽
add_dim((sx + (-half_w), sz + cap_h), (sx + half_w, sz + cap_h), base=(sx + (-half_w), sz + cap_h + 150), angle=0, text="承台宽 2350")
# 桩长（最右一根桩）
add_dim((sx + pile_ys[-1] + pile_r, sz + (-pile_l)), (sx + pile_ys[-1] + pile_r, sz + 0), base=(sx + pile_ys[-1] + pile_r + 200, sz + (-pile_l)), angle=90, text="桩长 5000")
# 桩间距（最左两根桩中心）
add_dim((sx + pile_ys[0], sz + (-pile_l - 200)), (sx + pile_ys[1], sz + (-pile_l - 200)), base=(sx + pile_ys[0], sz + (-pile_l - 350)), angle=0, text="桩间距 630")

add_text("侧视图", (sx - 100, sz - pile_l - 900), layer="文字")

# ---------------- 俯视图（x-y 平面） ----------------
tx, ty = top_origin

# 承台俯视：x=-half_l~half_l, y=-half_w~half_w
cap_top = [
    (tx + (-half_l), ty + (-half_w)),
    (tx + half_l, ty + (-half_w)),
    (tx + half_l, ty + half_w),
    (tx + (-half_l), ty + half_w),
]
add_polyline(cap_top, closed=True, layer="轮廓")

# 桩俯视：9 列×4 排共 36 个桩圆
for x in pile_xs:
    for y in pile_ys:
        add_circle((tx + x, ty + y), pile_r, layer="轮廓")

# 俯视图尺寸标注
# 承台长
add_dim((tx + (-half_l), ty - half_w - 150), (tx + half_l, ty - half_w - 150), base=(tx + (-half_l), ty - half_w - 300), angle=0, text="承台长 5500")
# 承台宽
add_dim((tx + half_l + 150, ty + (-half_w)), (tx + half_l + 150, ty + half_w), base=(tx + half_l + 300, ty + (-half_w)), angle=90, text="承台宽 2350")
# 桩间距（右上角相邻两桩中心）
add_dim((tx + pile_xs[-2], ty + pile_ys[-1] + pile_r + 150), (tx + pile_xs[-1], ty + pile_ys[-1] + pile_r + 150), base=(tx + pile_xs[-2], ty + pile_ys[-1] + pile_r + 300), angle=0, text="桩间距 630")
# 桩径（右下角桩圆）
add_dim((tx + pile_xs[-1] - pile_r, ty + pile_ys[0]), (tx + pile_xs[-1] + pile_r, ty + pile_ys[0]), base=(tx + pile_xs[-1] - pile_r, ty + pile_ys[0] - pile_r - 150), angle=0, text="桩径 250")

add_text("俯视图", (tx - 100, ty - half_w - 600), layer="文字")

# ========== 标题与说明 ==========
add_text("承台及桩基 三视图（单位：cm，比例 1:1）", (tx + 500, ty + half_w + 400), height=100, layer="文字")

legend_x, legend_y = tx + half_l + 600, ty + half_w - 100
add_text("图例：", (legend_x, legend_y), height=70, layer="文字")
add_text("1. 承台：长 5500，宽 2350，高 500", (legend_x, legend_y - 130), height=50, layer="文字")
add_text("2. 桩：9 列×4 排共 36 根，直径 250，长 5000，间距 630", (legend_x, legend_y - 210), height=50, layer="文字")

# ========== 保存文件 ==========
output_path = r"c:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\组件测试\承台及桩基.dxf"
doc.saveas(output_path)
print(f"图纸已保存：{output_path}")
