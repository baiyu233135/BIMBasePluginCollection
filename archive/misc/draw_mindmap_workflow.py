# -*- coding: utf-8 -*-
"""生成「数字化业务流程 · 五环闭环」环形思维导图 PNG（白底，供 Word 插入）。
风格与 draw_mindmap_painpoints.py 一致：PIL、2 倍渲染降采样、微软雅黑。"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "思维导图_数字化业务流程.png"))

W, H = 2200, 1600
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


CENTER_FILL = "#1F4E79"
GRAY = "#9AA5B1"
BAR_FILL, BAR_EDGE, BAR_TEXT_COLOR = "#FDF1E5", "#ED7D31", "#C55A11"
WHITE = "#FFFFFF"

# 与上一张一致的五色：蓝/绿/紫/金/青（主色, 浅底, 深文字）
THEMES = [
    ("#4472C4", "#EAF0FA", "#2F5496"),
    ("#548235", "#EFF5E9", "#3E6226"),
    ("#7030A0", "#F2EAF7", "#522174"),
    ("#BF8F00", "#FAF3DC", "#8F6C00"),
    ("#31859C", "#E7F2F5", "#256577"),
]

STAGES = [
    ("图像采集",
     ["无人机巡检为主，兼容手机相机", "公开数据集 + 本地标注训练", "对接航线化巡检", "不改变外业习惯"]),
    ("损伤智能识别与分类",
     ["双模式检测策略", "YOLOv8n 专用模型", "免模型五路CV掩码融合", "零标注冷启动"]),
    ("损伤几何尺寸量化",
     ["面投影标定物理尺度", "像素→物理尺寸换算", "输出长度·最大宽度·面积"]),
    ("三维空间定位",
     ["解析式 2D→3D 面投影", "映射至 BIM 构件表面", "空间关联与三维可视化标记"]),
    ("检测报告自动生成",
     ["Qwen-VL 多模态成因诊断", "python-docx 自动生成", "病害清单·位置·程度", "成因·处置建议"]),
]
BAR_TEXT = "五环相扣、数据贯通——巡检一次完成，识别、量化、定位、报告一站输出"

# ---------- 环形布局 ----------
CX, CY, R = 1100, 780, 430          # 圆心与环节节点轨道半径
ANGLES = [-90 + 72 * i for i in range(5)]   # 正上方起顺时针
NODE_W, NODE_H = 340, 88
ARC_PHI = 26                         # 弧线两端让开节点的角度
BAR_BOX = (30, 1495, 2170, 1565)


def pt(angle_deg, radius):
    a = math.radians(angle_deg)
    return (CX + radius * math.cos(a), CY + radius * math.sin(a))


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


def quad_points(p0, pc, p1, n=80):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt * mt * p0[0] + 2 * mt * t * pc[0] + t * t * p1[0]
        y = mt * mt * p0[1] + 2 * mt * t * pc[1] + t * t * p1[1]
        pts.append((x * S, y * S))
    return pts


def arc_arrow(draw, a0, a1, color, ctrl_r=540):
    """沿圆周外侧画 a0→a1 的顺时针弧形箭头（角度制，y 向下即顺时针递增）。"""
    p0 = pt(a0 + ARC_PHI, R)
    p1 = pt(a1 - ARC_PHI, R)
    pc = pt((a0 + a1) / 2, ctrl_r)
    pts = quad_points(p0, pc, p1)
    # 箭头尖端前移到 p1，线段在尖端前收住
    draw.line(pts, fill=color, width=int(4.5 * S), joint="curve")
    tx, ty = p1[0] - pc[0], p1[1] - pc[1]
    L = math.hypot(tx, ty)
    ux, uy = tx / L, ty / L
    tip = (p1[0] * S, p1[1] * S)
    bl, hw = 22 * S, 11 * S
    bx, by = tip[0] - bl * ux, tip[1] - bl * uy
    draw.polygon([tip, (bx - hw * uy, by + hw * ux),
                  (bx + hw * uy, by - hw * ux)], fill=color)


def center_text(draw, box, lines, fnt, fill, spacing=10):
    cx = (box[0] + box[2]) / 2 * S
    cy = (box[1] + box[3]) / 2 * S
    draw.multiline_text((cx, cy), "\n".join(lines), font=fnt, fill=fill,
                        anchor="mm", align="center", spacing=int(spacing * S))


def main():
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    f_center = font(32, bold=True)
    f_stage = font(28, bold=True)
    f_badge = font(26, bold=True)
    f_note = font(24)
    f_bar = font(34, bold=True)

    node_boxes = []
    for ang in ANGLES:
        nx, ny = pt(ang, R)
        node_boxes.append((nx - NODE_W / 2, ny - NODE_H / 2,
                           nx + NODE_W / 2, ny + NODE_H / 2))

    # 要点框位置：①正上、②正右、③④正下、⑤正左
    note_boxes = [
        (790, 85, 1410, 275),     # ① 4 行
        (1704, 532, 2164, 722),   # ② 4 行
        (1103, 1285, 1603, 1435), # ③ 3 行
        (597, 1285, 1097, 1435),  # ④ 3 行
        (36, 532, 496, 722),      # ⑤ 4 行
    ]
    # 节点 → 要点框的短连接线（起止点）
    links = [
        ((1100, 275), (1100, 306)),
        ((1679, 627), (1704, 627)),
        ((1353, 1172), (1353, 1285)),
        ((847, 1172), (847, 1285)),
        ((521, 627), (496, 627)),
    ]

    # 1. 闭环弧形箭头（先画，压在节点下）
    for i in range(5):
        a0 = ANGLES[i]
        a1 = ANGLES[(i + 1) % 5] + (360 if i == 4 else 0)
        arc_arrow(d, a0, a1, GRAY, ctrl_r=510 if i == 2 else 540)

    # 2. 节点与要点框的连接线
    for (x0, y0), (x1, y1) in links:
        d.line([(x0 * S, y0 * S), (x1 * S, y1 * S)], fill=GRAY, width=int(3 * S))

    # 3. 中心圆节点
    d.ellipse(sc((CX - 160, CY - 160, CX + 160, CY + 160)), fill=CENTER_FILL)
    center_text(d, (CX - 160, CY - 160, CX + 160, CY + 160),
                ["数字化业务流程", "·", "五环闭环"], f_center, WHITE, spacing=8)

    # 4. 环节节点 + 编号徽章 + 要点框
    for i, ((name, lines), (main_c, light_c, dark_c)) in enumerate(zip(STAGES, THEMES)):
        nb = node_boxes[i]
        rr(d, nb, 20, main_c)
        center_text(d, nb, [name], f_stage, WHITE)

        # 编号徽章：白底彩环圆形，压在节点左上角
        bx, by, br = nb[0] + 10, nb[1] - 10, 30
        d.ellipse(sc((bx - br, by - br, bx + br, by + br)),
                  fill=WHITE, outline=main_c, width=int(3.5 * S))
        d.text((bx * S, by * S), str(i + 1), font=f_badge, fill=main_c, anchor="mm")

        # 要点框
        pb = note_boxes[i]
        rr(d, pb, 18, light_c, main_c, 3)
        center_text(d, pb, lines, f_note, dark_c, spacing=12)

    # 5. 底部结论条
    rr(d, BAR_BOX, 20, BAR_FILL, BAR_EDGE, 3)
    fb = f_bar
    while d.textlength(BAR_TEXT, font=fb) > (BAR_BOX[2] - BAR_BOX[0] - 60) * S:
        fb = ImageFont.truetype(FONT_BLD, fb.size - S)
    center_text(d, BAR_BOX, [BAR_TEXT], fb, BAR_TEXT_COLOR)

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
