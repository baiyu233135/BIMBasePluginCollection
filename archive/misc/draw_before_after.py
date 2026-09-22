# -*- coding: utf-8 -*-
"""生成「检测业务流程前后对比」图 PNG（白底，供 Word 插入）。
上链=传统人工检测（灰红），下链=智检桥安数字化方案（蓝绿），中间橙色转型箭头。"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "对比图_检测流程前后对比.png"))

W, H = 2200, 1300
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


NAVY = "#1F4E79"
ORANGE, ORANGE_D = "#ED7D31", "#C55A11"
BLUE_ARROW = "#2E75B6"
GRAY_NODE, GRAY_ARROW = "#8F8F8F", "#9AA5B1"
RED, GREEN = "#C0504D", "#548235"
BAR_FILL, BAR_EDGE = "#FDF1E5", "#ED7D31"
WHITE = "#FFFFFF"

TITLE = "检测业务流程前后对比"
TOP_LABEL = "传统人工检测"
TOP_STEPS = ["现场登高采集", "人工判读", "现场量测", "文字记录位置", "多人誊录编制报告"]
TOP_NOTE = "痛点：分人分步 · 反复誊录 · 易出错 · 数据断链"
BOT_LABEL = "智检桥安数字化方案"
BOT_STEPS = ["无人机航线采集", "AI 智能识别分类", "自动尺寸量化", "面投影定位 BIM 构件", "一键生成检测报告"]
BOT_NOTE = "优势：一人一键 · 数据贯通 · 全程闭环 · 可追溯"
BOT_COLORS = ["#4472C4", "#548235", "#7030A0", "#BF8F00", "#31859C"]
BAR_TEXT = "同一检测任务：环节由割裂到贯通，数据由纸面到模型，报告由数日到即时"

# ---------- 布局 ----------
NODE_W, NODE_H, GAP = 340, 100, 80
CHAIN_X0 = 90
TOP_NODE_Y = (250, 360)
BOT_NODE_Y = (800, 910)
TOP_CHIP = (90, 160)
BOT_CHIP = (90, 710)
TOP_NOTE_CY = 430
BOT_NOTE_CY = 980
BAR_BOX = (30, 1080, 2170, 1200)


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


def h_arrow(draw, x0, x1, y, color, width=6):
    draw.line([(x0 * S, y * S), ((x1 - 20) * S, y * S)], fill=color,
              width=int(width * S))
    hw, hh = 12 * S, 22 * S
    tip = (x1 * S, y * S)
    draw.polygon([tip, (tip[0] - hh, tip[1] - hw), (tip[0] - hh, tip[1] + hw)],
                 fill=color)


def node_xs(i):
    x0 = CHAIN_X0 + i * (NODE_W + GAP)
    return (x0, x0 + NODE_W)


def draw_chain(draw, steps, colors, y_range, arrow_color, chip_xy, chip_text, chip_fill,
               note, note_color):
    f_node = font(28, bold=True)
    cy = (y_range[0] + y_range[1]) / 2
    for i, step in enumerate(steps):
        x0, x1 = node_xs(i)
        if i < len(steps) - 1:
            h_arrow(draw, x1 + 10, x1 + GAP - 10, cy, arrow_color)
        rr(draw, (x0, y_range[0], x1, y_range[1]), 18, colors[i])
        draw.text(((x0 + x1) / 2 * S, cy * S), step, font=f_node, fill=WHITE,
                  anchor="mm")
    # 链标签
    f_chip = font(26, bold=True)
    tw = draw.textlength(chip_text, font=f_chip) / S + 60
    rr(draw, (chip_xy[0], chip_xy[1], chip_xy[0] + tw, chip_xy[1] + 60), 16, chip_fill)
    draw.text(((chip_xy[0] + tw / 2) * S, (chip_xy[1] + 30) * S), chip_text,
              font=f_chip, fill=WHITE, anchor="mm")
    # 下方标注
    draw.text((W / 2 * S, note_color[1] * S), note, font=font(26, bold=True),
              fill=note_color[0], anchor="mm")


def main():
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    d.text((W / 2 * S, 75 * S), TITLE, font=font(46, bold=True), fill=NAVY,
           anchor="mm")

    # 上链：传统人工检测（灰红）
    draw_chain(d, TOP_STEPS, [GRAY_NODE] * 5, TOP_NODE_Y, GRAY_ARROW,
               TOP_CHIP, TOP_LABEL, "#A65D57", TOP_NOTE, (RED, TOP_NOTE_CY))

    # 中间橙色转型大箭头
    ax = W / 2 - 60
    d.line([(ax * S, 490 * S), (ax * S, 620 * S)], fill=ORANGE, width=int(14 * S))
    hw, hh = 30 * S, 40 * S
    tip = (ax * S, 660 * S)
    d.polygon([tip, (tip[0] - hw, tip[1] - hh), (tip[0] + hw, tip[1] - hh)],
              fill=ORANGE)
    d.text(((ax + 50) * S, 575 * S), "数字化转型", font=font(34, bold=True),
           fill=ORANGE_D, anchor="lm")

    # 下链：智检桥安数字化方案（蓝绿五色）
    draw_chain(d, BOT_STEPS, BOT_COLORS, BOT_NODE_Y, BLUE_ARROW,
               BOT_CHIP, BOT_LABEL, BLUE_ARROW, BOT_NOTE, (GREEN, BOT_NOTE_CY))

    # 底部结论条
    rr(d, BAR_BOX, 20, BAR_FILL, BAR_EDGE, 3)
    fb = font(32, bold=True)
    while d.textlength(BAR_TEXT, font=fb) > (BAR_BOX[2] - BAR_BOX[0] - 60) * S:
        fb = ImageFont.truetype(FONT_BLD, fb.size - S)
    d.text(((BAR_BOX[0] + BAR_BOX[2]) / 2 * S, (BAR_BOX[1] + BAR_BOX[3]) / 2 * S),
           BAR_TEXT, font=fb, fill=ORANGE_D, anchor="mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
