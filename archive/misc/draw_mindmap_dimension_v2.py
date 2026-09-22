# -*- coding: utf-8 -*-
"""生成「损伤尺寸计算流程」四步流水线流程图 v2 PNG（白底，供 Word 插入）。
v2：按 桥梁病害识别/dimension_utils.py 真实流程（参照物框选标定 + 检测框几何量估算）重画，
掩膜细化/骨架提取降为底部"规划中"优化方向（虚线灰条，与主流程区分）。"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "思维导图_尺寸计算流程_v2.png"))

W, H = 2200, 1300
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


GRAY = "#9AA5B1"
NAVY = "#1F4E79"
IN_FILL, IN_EDGE, IN_TEXT = "#EBF2FA", "#2E75B6", "#1F5C99"
OUT_FILL, OUT_EDGE, OUT_TEXT = "#FDF1E5", "#ED7D31", "#C55A11"
OPT_FILL, OPT_EDGE, OPT_TEXT = "#F7F7F7", "#A6A6A6", "#808080"
WHITE = "#FFFFFF"

THEMES = [
    ("#4472C4", "#EAF0FA", "#2F5496"),
    ("#548235", "#EFF5E9", "#3E6226"),
    ("#7030A0", "#F2EAF7", "#522174"),
    ("#BF8F00", "#FAF3DC", "#8F6C00"),
]

STEPS = [
    ("检测框定位", ["识别环节输出矩形检测框", "确定量化感兴趣区域"]),
    ("参照物框选标定", ["照片上框选已知长度参照物", "换算该照片的像素物理比例"]),
    ("像素尺寸换算", ["长度 = 框长边 × 比例", "宽度 = 框短边 × 比例",
                     "面积 = 外接矩形 × 比例²", "（外接矩形估算）"]),
    ("量化输出", ["长度 · 最大宽度 · 面积三项几何量", "写入检测报告", "（box_dimensions）"]),
]

TITLE = "损伤尺寸计算流程"
IN_TEXT_STR = "输入：巡检照片 + 损伤检测框（识别环节输出）+ 参照物框选标定（calc_scale：参照物实际长度 ÷ 参照物像素长边 = 物理比例 mm/px）"
OUT_TEXT_STR = "输出：损伤长度 · 最大宽度 · 面积 → 写入检测报告"
OPT_TEXT_STR = "规划中：掩膜细化贴合真实轮廓 · 骨架提取精确测长 —— 进一步提升量化精度"

# ---------- 布局 ----------
COL_CX = [297.5, 832.5, 1367.5, 1902.5]
IN_BOX = (30, 115, 2170, 200)
NODE_W, NODE_H = 400, 110
NODE_Y = (260, 370)
NOTE_W, NOTE_H = 480, 210
NOTE_Y = (420, 630)
BUS_Y = 700
OUT_BOX = (30, 1020, 2170, 1120)
OPT_BOX = (30, 1150, 2170, 1230)


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


def dashed_rr(draw, box, radius, outline, width=3, dash=18, gap=12):
    """虚线描边圆角矩形（直边段虚线，圆角处留空）。"""
    x0, y0, x1, y1 = box
    for xa, xb, ya, yb, horiz in (
            (x0 + radius, x1 - radius, y0, y0, True),
            (x0 + radius, x1 - radius, y1, y1, True),
            (y0 + radius, y1 - radius, x0, x0, False),
            (y0 + radius, y1 - radius, x1, x1, False)):
        p = xa
        while p < xb:
            q = min(p + dash, xb)
            if horiz:
                draw.line([(p * S, ya * S), (q * S, yb * S)], fill=outline,
                          width=int(width * S))
            else:
                draw.line([(ya * S, p * S), (yb * S, q * S)], fill=outline,
                          width=int(width * S))
            p += dash + gap
    # 四角小圆弧
    for cx, cy, a0 in ((x0 + radius, y0 + radius, 180),
                       (x1 - radius, y0 + radius, 270),
                       (x1 - radius, y1 - radius, 0),
                       (x0 + radius, y1 - radius, 90)):
        draw.arc(sc((cx - radius, cy - radius, cx + radius, cy + radius)),
                 a0, a0 + 90, fill=outline, width=int(width * S))


def center_text(draw, box, lines, fnt, fill, spacing=12):
    cx = (box[0] + box[2]) / 2 * S
    cy = (box[1] + box[3]) / 2 * S
    draw.multiline_text((cx, cy), "\n".join(lines), font=fnt, fill=fill,
                        anchor="mm", align="center", spacing=int(spacing * S))


def vline_arrow(draw, x, y0, y1, color, width=4, arrow=True):
    draw.line([(x * S, y0 * S), (x * S, (y1 - 14) * S)], fill=color, width=int(width * S))
    if arrow:
        hw, hh = 11 * S, 16 * S
        tip = (x * S, y1 * S)
        draw.polygon([tip, (tip[0] - hw, tip[1] - hh), (tip[0] + hw, tip[1] - hh)],
                     fill=color)


def hline_arrow(draw, x0, x1, y, color, width=8):
    draw.line([(x0 * S, y * S), ((x1 - 26) * S, y * S)], fill=color, width=int(width * S))
    hw, hh = 14 * S, 26 * S
    tip = (x1 * S, y * S)
    draw.polygon([tip, (tip[0] - hh, tip[1] - hw), (tip[0] - hh, tip[1] + hw)], fill=color)


def main():
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    f_in = font(28)
    f_step = font(30, bold=True)
    f_badge = font(26, bold=True)
    f_note = font(24)
    f_out = font(30, bold=True)
    f_opt = font(25)

    # 标题
    d.text((W / 2 * S, 62 * S), TITLE, font=font(44, bold=True), fill=NAVY, anchor="mm")

    # 顶部输入条
    rr(d, IN_BOX, 20, IN_FILL, IN_EDGE, 3)
    fi = f_in
    while d.textlength(IN_TEXT_STR, font=fi) > (IN_BOX[2] - IN_BOX[0] - 60) * S:
        fi = ImageFont.truetype(FONT_REG, fi.size - S)
    center_text(d, IN_BOX, [IN_TEXT_STR], fi, IN_TEXT)

    # 输入条 → 各步骤节点的分流竖箭头
    for cx in COL_CX:
        vline_arrow(d, cx, IN_BOX[3], NODE_Y[0], GRAY)

    # 步骤节点 / 徽章 / 要点框 / 步骤间粗箭头
    for i, ((name, lines), (main_c, light_c, dark_c)) in enumerate(zip(STEPS, THEMES)):
        cx = COL_CX[i]
        nb = (cx - NODE_W / 2, NODE_Y[0], cx + NODE_W / 2, NODE_Y[1])
        pb = (cx - NOTE_W / 2, NOTE_Y[0], cx + NOTE_W / 2, NOTE_Y[1])

        d.line([(cx * S, NODE_Y[1] * S), (cx * S, NOTE_Y[0] * S)],
               fill=GRAY, width=int(3 * S))

        if i < 3:
            hline_arrow(d, nb[2] + 12, COL_CX[i + 1] - NODE_W / 2 - 12,
                        (NODE_Y[0] + NODE_Y[1]) / 2, GRAY)

        rr(d, nb, 20, main_c)
        center_text(d, nb, [name], f_step, WHITE)

        bx, by, br = nb[0] + 10, nb[1] - 10, 30
        d.ellipse(sc((bx - br, by - br, bx + br, by + br)),
                  fill=WHITE, outline=main_c, width=int(3.5 * S))
        d.text((bx * S, by * S), str(i + 1), font=f_badge, fill=main_c, anchor="mm")

        rr(d, pb, 18, light_c, main_c, 3)
        center_text(d, pb, lines, f_note, dark_c, spacing=14)

        d.line([(cx * S, NOTE_Y[1] * S), (cx * S, BUS_Y * S)], fill=GRAY,
               width=int(4 * S))

    # 汇聚母线 + 下行粗箭头
    d.line([(COL_CX[0] * S, BUS_Y * S), (COL_CX[-1] * S, BUS_Y * S)],
           fill=GRAY, width=int(4 * S))
    mid_x = (COL_CX[0] + COL_CX[-1]) / 2
    d.line([(mid_x * S, BUS_Y * S), (mid_x * S, (OUT_BOX[1] - 44) * S)],
           fill=OUT_EDGE, width=int(10 * S))
    tip = (mid_x * S, (OUT_BOX[1] - 6) * S)
    draw_hw, draw_hh = 22 * S, 38 * S
    d.polygon([tip, (tip[0] - draw_hw, tip[1] - draw_hh),
               (tip[0] + draw_hw, tip[1] - draw_hh)], fill=OUT_EDGE)

    # 底部输出条
    rr(d, OUT_BOX, 20, OUT_FILL, OUT_EDGE, 3)
    fo = f_out
    while d.textlength(OUT_TEXT_STR, font=fo) > (OUT_BOX[2] - OUT_BOX[0] - 60) * S:
        fo = ImageFont.truetype(FONT_BLD, fo.size - S)
    center_text(d, OUT_BOX, [OUT_TEXT_STR], fo, OUT_TEXT)

    # 优化方向条（虚线灰框，与主流程区分）
    rr(d, OPT_BOX, 20, OPT_FILL)
    dashed_rr(d, OPT_BOX, 20, OPT_EDGE)
    center_text(d, OPT_BOX, [OPT_TEXT_STR], f_opt, OPT_TEXT)

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
