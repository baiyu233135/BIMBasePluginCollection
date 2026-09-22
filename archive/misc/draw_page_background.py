# -*- coding: utf-8 -*-
"""生成 A4 整页背景图（2480×3508，300dpi）：顶部赛名+蓝线、右上丝带角标、
底部极淡双塔斜拉桥线稿，中间留白供 Word 正文。"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "页面背景_A4.png"))

W, H = 2480, 3508
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)

NAVY = "#1F4E79"
BLUE = "#2E75B6"
ART = "#B8CCE0"        # 线稿色
WAVE = "#D3E1EF"       # 更淡的水波纹
TOP_RGB = (255, 255, 255)
BOT_RGB = (244, 248, 252)

TITLE = "中国国际大学生创新大赛（2026）产业赛道"
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
    for wy in (3345, 3390):
        pts = []
        for x in range(300, 2181, 10):
            pts.append((x * S, (wy + 7 * math.sin((x - 300) / 400 * 2 * math.pi)) * S))
        d.line(pts, fill=WAVE, width=int(3 * S), joint="curve")

    # 3. 底部：双塔斜拉桥线稿
    deck_y = 3280
    towers = [(800, 2760), (1680, 2760)]     # (塔中心x, 塔尖y)
    lw = int(4 * S)

    # 桥面（主线 + 下方一根稍淡的辅线表现桥体厚度）
    d.line(sc_pts([(200, deck_y), (2280, deck_y)]), fill=ART, width=lw)
    d.line(sc_pts([(200, deck_y + 16), (2280, deck_y + 16)]), fill=WAVE,
           width=int(3 * S))

    for tx, apex_y in towers:
        # 钻石型主塔：塔尖 → 中宽 → 穿过桥面 → 塔底
        body = [(tx, apex_y), (tx + 90, 3050), (tx + 55, deck_y + 60),
                (tx, 3350), (tx - 55, deck_y + 60), (tx - 90, 3050)]
        d.line(sc_pts(body + [body[0]]), fill=ART, width=lw, joint="curve")
        # 扇形斜拉索：塔尖 → 桥面锚点
        if tx == towers[0][0]:
            anchors = [280, 410, 540, 670, 930, 1060, 1190]
        else:
            anchors = [1290, 1420, 1550, 1810, 1940, 2070, 2200]
        for ax in anchors:
            d.line(sc_pts([(tx, apex_y), (ax, deck_y)]), fill=ART,
                   width=int(3 * S))

    # 4. 顶部：深蓝圆点 + 赛名
    f_title = font(44, bold=True)
    d.ellipse([(108 * S, 93 * S), (132 * S, 117 * S)], fill=NAVY)
    d.text((160 * S, 105 * S), TITLE, font=f_title, fill=NAVY, anchor="lm")

    # 5. 赛名下方深蓝横线（宽约页面 45%）
    d.rectangle(sc((160, 155, 160 + int(W * 0.45), 161)), fill=NAVY)

    # 6. 右上角工程蓝丝带角标（直角梯形）
    d.polygon(sc_pts([(2000, 0), (2480, 0), (2480, 180), (2130, 180)]), fill=BLUE)
    f_rib = font(48, bold=True)
    d.text((2290 * S, 92 * S), RIBBON_TEXT, font=f_rib, fill="#FFFFFF", anchor="mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
