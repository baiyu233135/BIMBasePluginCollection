# -*- coding: utf-8 -*-
"""生成「模型性能基线与提升预期」分组柱状图 PNG（白底，供 Word 插入）。
风格与 draw_mindmap_painpoints.py / draw_mindmap_workflow.py 同系列。"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "模型性能基线与提升预期.png"))

W, H = 2000, 1200
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


NAVY, NAVY_D = "#1F4E79", "#122E49"
ORANGE, ORANGE_D = "#ED7D31", "#B8641F"
GRAY_BAR, GRAY_D = "#BFBFBF", "#7F7F7F"
GRID, AXIS, TEXT = "#D9D9D9", "#888888", "#333333"
BAND = "#F4F4F4"
BAR_FILL, BAR_EDGE, BAR_TEXT_COLOR = "#FDF1E5", "#ED7D31", "#C55A11"

TITLE = "模型性能基线与提升预期"
NOTE = "注：基线数值为真实实测结果；v2 为同数据集 200 epochs 训练的预期区间，训练完成后将以实测值如实更新"

# (标签, 值, 显示文本, 误差下限, 误差上限, 柱色, 深色) — 误差 None 表示无误差线
GROUPS = [
    ("mAP50", [
        ("基线模型实测", 0.336, "0.336", None, None, NAVY, NAVY_D),
        ("v2 训练预期", 0.52, "0.52", 0.45, 0.60, ORANGE, ORANGE_D),
        ("行业参考水平", 0.65, "0.65", 0.55, 0.80, GRAY_BAR, GRAY_D),
    ]),
    ("mAP50-95", [
        ("基线模型实测", 0.085, "0.085", None, None, NAVY, NAVY_D),
        ("v2 训练预期", 0.18, "0.18", 0.12, 0.25, ORANGE, ORANGE_D),
        ("行业参考水平", 0.40, "0.40", 0.30, 0.50, GRAY_BAR, GRAY_D),
    ]),
]
REF_BANDS = [(0.55, 0.80), (0.30, 0.50)]   # 每组行业参考区间背景带

LEGEND = [
    (NAVY, "基线实测"),
    (ORANGE, "v2 预期（训练完成后以实测更新）"),
    (GRAY_BAR, "行业参考区间"),
]

# 绘图区
PX0, PY0, PX1, PY1 = 170, 150, 1960, 950   # 左、上、右、下（PY1 为 x 轴）
Y_MAX = 0.9
BAR_W, BAR_GAP = 130, 40
GROUP_CX = [620, 1430]
NOTE_BOX = (60, 1055, 1940, 1135)


def y_of(v):
    return PY1 - v / Y_MAX * (PY1 - PY0)


def sc(box):
    return [int(v * S) for v in box]


def dashed_hline(draw, y, x0, x1, color, dash=12, gap=8, width=2):
    x = x0
    while x < x1:
        draw.line([(x * S, y * S), (min(x + dash, x1) * S, y * S)],
                  fill=color, width=int(width * S))
        x += dash + gap


def main():
    img = Image.new("RGB", (W * S, H * S), "#FFFFFF")
    d = ImageDraw.Draw(img)

    f_title = font(46, bold=True)
    f_tick = font(24)
    f_axis = font(28, bold=True)
    f_group = font(32, bold=True)
    f_val = font(28, bold=True)
    f_legend = font(26)
    f_note = font(26)
    f_band = font(20)

    # 标题
    d.text((W / 2 * S, 75 * S), TITLE, font=f_title, fill=NAVY, anchor="mm")

    # 参考区间背景带（网格线之前）
    for (gcx, (lo, hi)) in zip(GROUP_CX, REF_BANDS):
        half = (3 * BAR_W + 2 * BAR_GAP) / 2 + 30
        d.rectangle(sc((gcx - half, y_of(hi), gcx + half, y_of(lo))), fill=BAND)
        d.text(((gcx - half + 12) * S, (y_of(hi) + 8) * S), "行业参考区间",
               font=f_band, fill="#A6A6A6", anchor="la")

    # 网格线 + Y 轴刻度
    for i in range(1, 10):
        v = i / 10
        dashed_hline(d, y_of(v), PX0, PX1, GRID)
    for i in range(10):
        v = i / 10
        d.text(((PX0 - 16) * S, y_of(v) * S), f"{v:.1f}", font=f_tick,
               fill=TEXT, anchor="rm")

    # 坐标轴
    d.line([(PX0 * S, PY0 * S), (PX0 * S, PY1 * S)], fill=AXIS, width=int(2.5 * S))
    d.line([(PX0 * S, PY1 * S), (PX1 * S, PY1 * S)], fill=AXIS, width=int(2.5 * S))

    # Y 轴标签（竖排）
    f_ylab = font(28, bold=True)
    tmp = Image.new("RGBA", (int(140 * S), int(60 * S)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((70 * S, 30 * S), "指标值", font=f_ylab,
                             fill=TEXT, anchor="mm")
    tmp = tmp.rotate(90, expand=True)
    img.paste(tmp, (int(55 * S - tmp.width / 2),
                    int((PY0 + PY1) / 2 * S - tmp.height / 2)), tmp)

    # 柱 + 误差线 + 数值
    for gi, (gname, bars) in enumerate(GROUPS):
        gcx = GROUP_CX[gi]
        x = gcx - (3 * BAR_W + 2 * BAR_GAP) / 2
        for (label, val, txt, lo, hi, bc, dc) in bars:
            y_top = y_of(val)
            d.rectangle(sc((x, y_top, x + BAR_W, PY1)), fill=bc)
            if lo is not None:
                cx = x + BAR_W / 2
                y_lo, y_hi = y_of(lo), y_of(hi)
                d.line([(cx * S, y_lo * S), (cx * S, y_hi * S)],
                       fill=dc, width=int(4 * S))
                for yy in (y_lo, y_hi):
                    d.line([((cx - 22) * S, yy * S), ((cx + 22) * S, yy * S)],
                           fill=dc, width=int(4 * S))
                label_y = y_hi - 14
            else:
                label_y = y_top - 14
            d.text(((x + BAR_W / 2) * S, label_y * S), txt, font=f_val,
                   fill=dc, anchor="ms")
            x += BAR_W + BAR_GAP
        d.text((gcx * S, (PY1 + 28) * S), gname, font=f_group,
               fill=TEXT, anchor="mm")

    # 图例（右上角）
    lx, ly = 1430, 185
    for color, text in LEGEND:
        d.rounded_rectangle(sc((lx, ly, lx + 42, ly + 26)), radius=int(6 * S), fill=color)
        d.text(((lx + 56) * S, (ly + 13) * S), text, font=f_legend,
               fill=TEXT, anchor="lm")
        ly += 46

    # 底部注释条
    d.rounded_rectangle(sc(NOTE_BOX), radius=int(16 * S), fill=BAR_FILL,
                        outline=BAR_EDGE, width=int(2.5 * S))
    fb = f_note
    while d.textlength(NOTE, font=fb) > (NOTE_BOX[2] - NOTE_BOX[0] - 50) * S:
        fb = ImageFont.truetype(FONT_REG, fb.size - S)
    d.text(((NOTE_BOX[0] + NOTE_BOX[2]) / 2 * S, (NOTE_BOX[1] + NOTE_BOX[3]) / 2 * S),
           NOTE, font=fb, fill=BAR_TEXT_COLOR, anchor="mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
