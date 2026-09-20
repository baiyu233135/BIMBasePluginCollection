# -*- coding: utf-8 -*-
"""生成「项目里程碑时间线」图 PNG（白底，供 Word 插入）。"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "示意图_里程碑.png"))

W, H = 2200, 900
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


NAVY = "#1F4E79"
ORANGE = "#ED7D31"
GRAY = "#9AA5B1"
TEXT = "#333333"
WHITE = "#FFFFFF"

AXIS_Y = 450
AXIS_X = (150, 2050)
NODE_XS = [250, 590, 930, 1270, 1610, 1950]

# (时间, 描述行, 已完成?) —— 已完成=实心蓝点，规划中=空心橙点+「规划」标注
MILESTONES = [
    ("2026.6", ["命题对接", "与需求调研"], True),
    ("2026.7-8", ["基线系统开发", "与数据集建设"], True),
    ("2026.9", ["案例验证与指标测试", "（常泰长江大桥）"], True),
    ("2026.9", ["报名与材料提交"], True),
    ("2026.10", ["网络评审", "与优化迭代"], True),
    ("2026.11", ["总决赛现场演示"], False),
]

BOX_W = 300


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


def main():
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    f_date = font(26, bold=True)
    f_desc = font(22)
    f_tag = font(20, bold=True)
    f_legend = font(24)

    # 图例（右上）
    lx, ly = 1620, 90
    d.ellipse(sc((lx, ly, lx + 24, ly + 24)), fill=NAVY)
    d.text(((lx + 40) * S, (ly + 12) * S), "已完成", font=f_legend, fill=TEXT, anchor="lm")
    lx2 = lx + 220
    d.ellipse(sc((lx2, ly, lx2 + 24, ly + 24)), fill=WHITE, outline=ORANGE,
              width=int(4 * S))
    d.text(((lx2 + 40) * S, (ly + 12) * S), "规划", font=f_legend, fill=TEXT, anchor="lm")

    # 时间轴主线 + 末端箭头
    d.line([(AXIS_X[0] * S, AXIS_Y * S), (AXIS_X[1] * S, AXIS_Y * S)],
           fill=GRAY, width=int(4 * S))
    tip = (AXIS_X[1] * S, AXIS_Y * S)
    d.polygon([tip, (tip[0] - 24 * S, tip[1] - 13 * S),
               (tip[0] - 24 * S, tip[1] + 13 * S)], fill=GRAY)

    box_h = 150
    for i, ((date, lines, done), nx) in enumerate(zip(MILESTONES, NODE_XS)):
        above = (i % 2 == 0)
        color = NAVY if done else ORANGE

        # 节点圆点
        r = 15
        if done:
            d.ellipse(sc((nx - r, AXIS_Y - r, nx + r, AXIS_Y + r)), fill=NAVY)
        else:
            d.ellipse(sc((nx - r, AXIS_Y - r, nx + r, AXIS_Y + r)), fill=WHITE,
                      outline=ORANGE, width=int(4.5 * S))

        # 文本框位置（上下交错）
        if above:
            bb = (nx - BOX_W / 2, AXIS_Y - 70 - box_h, nx + BOX_W / 2, AXIS_Y - 70)
            d.line([(nx * S, bb[3] * S), (nx * S, (AXIS_Y - r) * S)],
                   fill=color, width=int(2.5 * S))
        else:
            bb = (nx - BOX_W / 2, AXIS_Y + 70, nx + BOX_W / 2, AXIS_Y + 70 + box_h)
            d.line([(nx * S, (AXIS_Y + r) * S), (nx * S, bb[1] * S)],
                   fill=color, width=int(2.5 * S))

        rr(d, bb, 16, WHITE, color, 2.5)
        cy = (bb[1] + bb[3]) / 2
        d.text((nx * S, (bb[1] + 38) * S), date, font=f_date, fill=color, anchor="mm")
        fy = bb[1] + 78
        for ln in lines:
            d.text((nx * S, fy * S), ln, font=f_desc, fill=TEXT, anchor="mm")
            fy += 32
        if not done:
            d.text((nx * S, fy * S), "（规划）", font=f_tag, fill=ORANGE, anchor="mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
