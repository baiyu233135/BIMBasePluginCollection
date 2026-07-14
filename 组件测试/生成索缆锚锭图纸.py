"""
根据 索缆锚锭.py 组件参数生成 CAD 图纸（DXF 格式）。
包含：正视图（沿 -y 看，x-z 投影）、侧视图（沿 -x 看，y-z 投影）、俯视图（沿 -z 看，x-y 投影）。
单位：cm，比例 1:1。
"""

import ezdxf
from math import pi, cos, sin

# ========== 组件参数（与 索缆锚锭.py 保持一致，单位 cm） ==========
L = 5450          # 锚块总长
H = 2039          # 锚块总高
W = 1200          # 锚块宽度
CL = 5680         # 承台长度
CW = 1600         # 承台宽度
CH = 400          # 承台高度
R = 170           # 底柱半径
DH = 1000         # 底柱高度
N = 64            # 底柱圆周分段数

# 底柱中心 x 坐标（7 对，共 14 根）
col_x = [290 - R / 2 + i * 850 for i in range(7)]
col_y = [250 + R / 2, -(250 + R / 2)]  # ±335

# 锚块截面关键点（正视图 x-z 平面，z 从承台顶面算起，即 DH+CH 处开始）
# 代码中截面局部 z 为 0~2039，实际全局 z = DH+CH + 局部 z
anchor_sec_local = [
    (50, 0),
    (50 + L, 0),
    (50 + L, 1250),
    (4863, 2039),
    (3863, 2039),
    (50, 1300),
]

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
    """按点序列添加 LWPOLYLINE。"""
    if len(points) < 2:
        return
    msp.add_lwpolyline(points, close=closed, dxfattribs={"layer": layer})


def add_circle(center, radius, layer="轮廓"):
    msp.add_circle(center, radius, dxfattribs={"layer": layer})


def add_line(p1, p2, layer="轮廓"):
    msp.add_line(p1, p2, dxfattribs={"layer": layer})


def add_dim(p1, p2, base, angle=0, text=None, layer="标注"):
    """添加线性尺寸标注。"""
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


def add_text(text, insert, height=80, layer="文字"):
    msp.add_text(text, dxfattribs={"height": height, "layer": layer, "insert": insert})


# ========== 视图布局 ==========
# 正视图：左下角 (0, 0)
# 侧视图：右下角 (8000, 0)
# 俯视图：上方居中 (0, 5000)
front_origin = (0, 0)
side_origin = (8000, 0)
top_origin = (0, 5000)

# ---------------- 正视图（x-z 平面） ----------------
# 锚块轮廓（全局 z = DH+CH + 局部 z）
anchor_front = [(x, DH + CH + z) for x, z in anchor_sec_local]
add_polyline(anchor_front, closed=True, layer="轮廓")

# 承台（x: 0 ~ CL, z: DH ~ DH+CH；Cube 默认 [0,1]^3，经 translate(0,-CW/2,DH) 平移）
pile_z0 = DH
pile_z1 = DH + CH
ct_front = [
    (0, pile_z0),
    (CL, pile_z0),
    (CL, pile_z1),
    (0, pile_z1),
]
add_polyline(ct_front, closed=True, layer="轮廓")

# 底柱（圆柱正视图为矩形，x 中心 ± R，z 0 ~ DH）
for cx in col_x:
    rect = [
        (cx - R, 0),
        (cx + R, 0),
        (cx + R, DH),
        (cx - R, DH),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 正视图尺寸标注
# 承台总长度
add_dim((0, 0), (CL, 0), base=(0, -500), angle=0, text="承台长度 5680")
# 锚块底部长度
add_dim((50, DH + CH), (50 + L, DH + CH), base=(50, DH + CH - 400), angle=0, text="锚块总长 5450")
# 锚块总高（从承台顶到锚块最高点，取 x=3863 处）
add_dim((3863, DH + CH), (3863, DH + CH + H), base=(3863 + 600, DH + CH), angle=90, text="锚块总高 2039")
# 底柱高度
add_dim((col_x[0] - R, 0), (col_x[0] - R, DH), base=(col_x[0] - R - 400, 0), angle=90, text="底柱高 1000")
# 承台高度
add_dim((CL, DH), (CL, DH + CH), base=(CL + 400, DH), angle=90, text="承台高 400")
# 底柱直径
add_dim((col_x[0] - R, DH / 2), (col_x[0] + R, DH / 2), base=(col_x[0] - R, DH / 2 + 250), angle=0, text="底柱直径 340")
# 第一、二根底柱中心距
add_dim((col_x[0], -250), (col_x[1], -250), base=(col_x[0], -350), angle=0, text="底柱间距 850")

add_text("正视图", (CL / 2 - 400, -700), layer="文字")

# ---------------- 侧视图（y-z 平面） ----------------
# 侧视图 x 方向被压缩，显示 y-z 投影
sx, sz = side_origin

# 锚块侧视轮廓：y 范围 -W/2 ~ W/2，z 范围 DH+CH ~ DH+CH+H
anchor_side = [
    (sx + (-W / 2), sz + (DH + CH)),
    (sx + (W / 2), sz + (DH + CH)),
    (sx + (W / 2), sz + (DH + CH + H)),
    (sx + (-W / 2), sz + (DH + CH + H)),
]
add_polyline(anchor_side, closed=True, layer="轮廓")

# 承台侧视轮廓：y 范围 -CW/2 ~ CW/2，z 范围 DH ~ DH+CH
ct_side = [
    (sx + (-CW / 2), sz + DH),
    (sx + (CW / 2), sz + DH),
    (sx + (CW / 2), sz + (DH + CH)),
    (sx + (-CW / 2), sz + (DH + CH)),
]
add_polyline(ct_side, closed=True, layer="轮廓")

# 底柱侧视：每对底柱在 y=±335 处，投影为两个矩形
for cy in col_y:
    rect = [
        (sx + (cy - R), sz + 0),
        (sx + (cy + R), sz + 0),
        (sx + (cy + R), sz + DH),
        (sx + (cy - R), sz + DH),
    ]
    add_polyline(rect, closed=True, layer="轮廓")

# 侧视图尺寸标注
# 承台宽度
add_dim((sx + (-CW / 2), sz + 0), (sx + (CW / 2), sz + 0), base=(sx + (-CW / 2), sz - 500), angle=0, text="承台宽度 1600")
# 锚块宽度
add_dim((sx + (-W / 2), sz + (DH + CH + H) + 100), (sx + (W / 2), sz + (DH + CH + H) + 100), base=(sx + (-W / 2), sz + (DH + CH + H) + 200), angle=0, text="锚块宽度 1200")
# 锚块总高
add_dim((sx + (W / 2), sz + (DH + CH)), (sx + (W / 2), sz + (DH + CH + H)), base=(sx + (W / 2) + 400, sz + (DH + CH)), angle=90, text="锚块总高 2039")
# 底柱高
add_dim((sx + (col_y[0] - R), sz + 0), (sx + (col_y[0] - R), sz + DH), base=(sx + (col_y[0] - R) - 400, sz + 0), angle=90, text="底柱高 1000")
# 承台高
add_dim((sx + (CW / 2), sz + DH), (sx + (CW / 2), sz + (DH + CH)), base=(sx + (CW / 2) + 400, sz + DH), angle=90, text="承台高 400")
# 两排底柱中心距
add_dim((sx + col_y[1], sz - 250), (sx + col_y[0], sz - 250), base=(sx + col_y[1], sz - 350), angle=0, text="底柱排距 670")

add_text("侧视图", (sx + (-W / 2), sz - 700), layer="文字")

# ---------------- 俯视图（x-y 平面） ----------------
# 俯视图 z 方向被压缩，显示 x-y 投影
tx, ty = top_origin

# 承台俯视图：x 0~CL, y -CW/2~CW/2
ct_top = [
    (tx + 0, ty + (-CW / 2)),
    (tx + CL, ty + (-CW / 2)),
    (tx + CL, ty + (CW / 2)),
    (tx + 0, ty + (CW / 2)),
]
add_polyline(ct_top, closed=True, layer="轮廓")

# 锚块俯视图：x 50~50+L, y -W/2~W/2
anchor_top = [
    (tx + 50, ty + (-W / 2)),
    (tx + (50 + L), ty + (-W / 2)),
    (tx + (50 + L), ty + (W / 2)),
    (tx + 50, ty + (W / 2)),
]
add_polyline(anchor_top, closed=True, layer="轮廓")

# 底柱俯视图：14 个圆
circles = []
for cx in col_x:
    for cy in col_y:
        add_circle((tx + cx, ty + cy), R, layer="轮廓")
        circles.append((tx + cx, ty + cy))

# 俯视图尺寸标注
# 承台长度
add_dim((tx + 0, ty + (-CW / 2) - 300), (tx + CL, ty + (-CW / 2) - 300), base=(tx + 0, ty + (-CW / 2) - 500), angle=0, text="承台长度 5680")
# 承台宽度
add_dim((tx + CL + 300, ty + (-CW / 2)), (tx + CL + 300, ty + (CW / 2)), base=(tx + CL + 500, ty + (-CW / 2)), angle=90, text="承台宽度 1600")
# 锚块长度
add_dim((tx + 50, ty + (W / 2) + 300), (tx + (50 + L), ty + (W / 2) + 300), base=(tx + 50, ty + (W / 2) + 500), angle=0, text="锚块总长 5450")
# 锚块宽度
add_dim((tx + (50 + L) + 300, ty + (-W / 2)), (tx + (50 + L) + 300, ty + (W / 2)), base=(tx + (50 + L) + 500, ty + (-W / 2)), angle=90, text="锚块宽度 1200")
# 底柱间距
add_dim((tx + col_x[0], ty + col_y[0] + R + 200), (tx + col_x[1], ty + col_y[0] + R + 200), base=(tx + col_x[0], ty + col_y[0] + R + 400), angle=0, text="底柱间距 850")
# 底柱排距
add_dim((tx + col_x[0] - R - 200, ty + col_y[1]), (tx + col_x[0] - R - 200, ty + col_y[0]), base=(tx + col_x[0] - R - 400, ty + col_y[1]), angle=90, text="底柱排距 670")
# 底柱直径（示意一个）
add_dim((tx + col_x[0] - R, ty + col_y[0]), (tx + col_x[0] + R, ty + col_y[0]), base=(tx + col_x[0] - R, ty + col_y[0] + 200), angle=0, text="底柱直径 340")

add_text("俯视图", (tx + CL / 2 - 400, ty - CW / 2 - 700), layer="文字")

# ========== 标题与说明 ==========
add_text("索缆锚锭 三视图（单位：cm，比例 1:1）", (tx + 500, ty + CW / 2 + 600), height=120, layer="文字")

# 添加图例说明
legend_x, legend_y = tx + CL / 2 + 800, ty + CW / 2 - 200
add_text("图例：", (legend_x, legend_y), height=80, layer="文字")
add_text("1. 锚块：异形拉伸体，长 5450，高 2039，宽 1200", (legend_x, legend_y - 150), height=60, layer="文字")
add_text("2. 承台：长 5680，宽 1600，高 400", (legend_x, legend_y - 250), height=60, layer="文字")
add_text("3. 底柱：14 根圆柱，半径 170，高 1000", (legend_x, legend_y - 350), height=60, layer="文字")
add_text("4. 底柱排布：7 对，x 向间距 850，y 向排距 670", (legend_x, legend_y - 450), height=60, layer="文字")

# ========== 保存文件 ==========
output_path = r"c:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\组件测试\索缆锚锭.dxf"
doc.saveas(output_path)
print(f"图纸已保存：{output_path}")
