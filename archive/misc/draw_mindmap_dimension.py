# -*- coding: utf-8 -*-
"""生成「尺寸计算流程」四步流水线流程图 PNG（白底，供 Word 插入）。
风格与 draw_mindmap_painpoints.py / draw_mindmap_workflow.py 同系列。"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "思维导图_尺寸计算流程.png"))

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
WHITE = "#FFFFFF"

# 系列五色中的蓝/绿/紫/金（主色, 浅底, 深文字）
THEMES = [
    ("#4472C4", "#EAF0FA", "#2F5496"),
    ("#548235", "#EFF5E9", "#3E6226"),
    ("#7030A0", "#F2EAF7", "#522174"),
    ("#BF8F00", "#FAF3DC", "#8F6C00"),
]

STEPS = [
    ("检测框定位", ["识别环节输出矩形检测框", "确定量化感兴趣区域 ROI"]),
    ("掩膜细化", ["框内分割细化", "贴合损伤真实轮廓", "剔除背景干扰"]),
    ("骨架提取", ["线状损伤提取中轴骨架", "作为长度计算基准线"]),
    ("量化输出", ["长度 = 骨架长 × 像素物理尺寸", "最大宽度 = 沿骨架法向", "逐点扫描取最大", "面积 = 掩膜像素数 × 物理尺寸²"]),
]

IN_TEXT_STR = "输入：巡检照片 + 损伤检测框（识别环节输出）+ 参照物标定比例（mm/px，dimension_utils.calc_scale）"
OUT_TEXT_STR = "输出：损伤长度 · 最大宽度 · 面积 三项几何量 → 写入检测报告（box_dimensions）"

# ---------- 布局 ----------
COL_CX = [297.5, 832.5, 1367.5, 1902.5]
IN_BOX = (30, 60, 2170, 150)
NODE_W, NODE_H = 400, 110
NODE_Y = (230, 340)
NOTE_W, NOTE_H = 480, 210
NOTE_Y = (400, 610)
BUS_Y = 690                      # 汇聚母线高度
OUT_BOX = (30, 1130, 2170, 1240)


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


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

        # 节点 → 要点框连接线
        d.line([(cx * S, NODE_Y[1] * S), (cx * S, NOTE_Y[0] * S)],
               fill=GRAY, width=int(3 * S))

        # 步骤间粗箭头
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
        center_text(d, pb, lines, f_note, dark_c, spacing=16)

        # 要点框 → 汇聚母线
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

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
