# -*- coding: utf-8 -*-
"""封面专用 A4 整页背景图（2480×3508，300dpi）。
与 draw_page_background.py（正文版）差异：无顶部赛名与蓝线（封面自有标题）、
保留右上"智检桥安"丝带角标、底部斜拉桥线稿略放大且线条略加深（仍淡雅）。"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "页面背景_封面.png"))

W, H = 2480, 3508
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)

BLUE = "#2E75B6"
ART = "#A8C0D8"        # 线稿色（封面版略加深，不早于该色更深）
WAVE = "#C4D6E8"
TOP_RGB = (255, 255, 255)
BOT_RGB = (244, 248, 252)

RIBBON_TEXT = "智检桥安"


def sc_pts(pts):
    return [(x * S, y * S) for x, y in pts]


def sc(box):
    return [int(v * S) for v in box]


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


def main():
    img = Image.new("RGB", (W * S, H * S), TOP_RGB)
    d = ImageDraw.Draw(img)

    # 1. 白 → 极浅蓝白纵向渐变
    for y in range(H * S):
        t = y / (H * S - 1)
        c = tuple(int(TOP_RGB[i] + (BOT_RGB[i] - TOP_RGB[i]) * t) for i in range(3))
        d.line([(0, y), (W * S, y)], fill=c)

    # 2. 底部：水波纹（更淡，先画压在桥下）
    for wy in (3355, 3405):
        pts = []
        for x in range(280, 2201, 10):
            pts.append((x * S, (wy + 8 * math.sin((x - 280) / 420 * 2 * math.pi)) * S))
        d.line(pts, fill=WAVE, width=int(3 * S), joint="curve")

    # 3. 底部：双塔斜拉桥线稿（较正文版放大 ~10%，线宽略加）
    deck_y = 3260
    towers = [(750, 2680), (1730, 2680)]     # (塔中心x, 塔尖y)

    d.line(sc_pts([(150, deck_y), (2330, deck_y)]), fill=ART, width=int(5 * S))
    d.line(sc_pts([(150, deck_y + 18), (2330, deck_y + 18)]), fill=WAVE,
           width=int(3 * S))

    for tx, apex_y in towers:
        body = [(tx, apex_y), (tx + 100, 3020), (tx + 60, deck_y + 65),
                (tx, 3360), (tx - 60, deck_y + 65), (tx - 100, 3020)]
        d.line(sc_pts(body + [body[0]]), fill=ART, width=int(5 * S), joint="curve")
        if tx == towers[0][0]:
            anchors = [250, 390, 530, 670, 890, 1040, 1190]
        else:
            anchors = [1290, 1440, 1590, 1810, 1950, 2090, 2230]
        for ax in anchors:
            d.line(sc_pts([(tx, apex_y), (ax, deck_y)]), fill=ART,
                   width=int(3.5 * S))

    # 4. 右上角工程蓝丝带角标（保留，同正文版）
    d.polygon(sc_pts([(2000, 0), (2480, 0), (2480, 180), (2130, 180)]), fill=BLUE)
    f_rib = font(48, bold=True)
    d.text((2290 * S, 92 * S), RIBBON_TEXT, font=f_rib, fill="#FFFFFF", anchor="mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
