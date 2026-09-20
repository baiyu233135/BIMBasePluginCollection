# -*- coding: utf-8 -*-
"""生成「双形态交付」示意图 PNG（白底，供 Word 插入）。"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "示意图_双形态交付.png"))

W, H = 2200, 1100
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
BLUE, BLUE_TINT, BLUE_TEXT = "#2E75B6", "#EBF2FA", "#1F5C99"
GREEN, GREEN_TINT, GREEN_TEXT = "#548235", "#EFF5E9", "#3E6226"
WHITE = "#FFFFFF"

CARD_Y = (310, 790)
LEFT_CARD = (100, CARD_Y[0], 720, CARD_Y[1])
RIGHT_CARD = (1480, CARD_Y[0], 2100, CARD_Y[1])
CENTER_BOX = (880, 440, 1320, 660)
ARROW_Y = 550

LEFT = ("桌面端 · BIMBase 检测插件", BLUE, BLUE_TINT, BLUE_TEXT,
        ["面向内业处理", "检测 · 诊断 · 量化 · 定位一体化", "检测报告一键生成"])
RIGHT = ("网页端 · 数字孪生在线平台", GREEN, GREEN_TINT, GREEN_TEXT,
         ["浏览器免安装访问", "三维浏览与病害档案展示", "可部署至公网网址"])


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


def card(draw, box, title, mc, tint, tc, lines):
    rr(draw, box, 24, tint, mc, 3)
    # 标题牌（压在卡片顶边）
    tw = draw.textlength(title, font=font(30, bold=True)) / S + 80
    cx = (box[0] + box[2]) / 2
    rr(draw, (cx - tw / 2, box[1] - 34, cx + tw / 2, box[1] + 34), 17, mc)
    draw.text((cx * S, box[1] * S), title, font=font(30, bold=True),
              fill=WHITE, anchor="mm")
    # 要点
    f = font(26)
    y = box[1] + 150
    for ln in lines:
        draw.text(((box[0] + 70) * S, y * S), "· " + ln, font=f, fill=tc, anchor="lm")
        y += 100


def double_arrow(draw, x0, x1, y, color):
    draw.line([(x0 * S, y * S), (x1 * S, y * S)], fill=color, width=int(5 * S))
    hw, hh = 12 * S, 20 * S
    draw.polygon([(x1 * S, y * S), (x1 * S - hh, y * S - hw), (x1 * S - hh, y * S + hw)],
                 fill=color)
    draw.polygon([(x0 * S, y * S), (x0 * S + hh, y * S - hw), (x0 * S + hh, y * S + hw)],
                 fill=color)


def main():
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    card(d, LEFT_CARD, *LEFT)
    card(d, RIGHT_CARD, *RIGHT)

    # 中心数据底座
    rr(d, CENTER_BOX, 26, NAVY)
    cx = (CENTER_BOX[0] + CENTER_BOX[2]) / 2
    cy = (CENTER_BOX[1] + CENTER_BOX[3]) / 2
    d.text((cx * S, (cy - 42) * S), "同一数据底座", font=font(34, bold=True),
           fill=WHITE, anchor="mm")
    d.text((cx * S, (cy + 30) * S), "病害档案 JSON / BIM 模型", font=font(26),
           fill="#D6E2F0", anchor="mm")

    # 双向箭头 + 标注
    f_lab = font(20)
    for x0, x1, gx in ((LEFT_CARD[2] + 8, CENTER_BOX[0] - 8, 800),
                       (CENTER_BOX[2] + 8, RIGHT_CARD[0] - 8, 1400)):
        double_arrow(d, x0, x1, ARROW_Y, ORANGE)
        d.text((gx * S, (ARROW_Y - 42) * S), "数据同源", font=f_lab,
               fill=ORANGE, anchor="mm")
        d.text((gx * S, (ARROW_Y + 42) * S), "一键导出/导入", font=f_lab,
               fill=ORANGE, anchor="mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
