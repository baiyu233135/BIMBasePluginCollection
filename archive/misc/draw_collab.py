# -*- coding: utf-8 -*-
"""生成「产教协同三方协同」三角布局示意图 PNG（白底，供 Word 插入）。"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "示意图_产教协同.png"))

W, H = 2000, 1300
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


NAVY = "#1F4E79"
BLUE, BLUE_TINT, BLUE_TEXT = "#2E75B6", "#EBF2FA", "#1F5C99"
GREEN, GREEN_TINT, GREEN_TEXT = "#548235", "#EFF5E9", "#3E6226"
ORANGE, ORANGE_TINT, ORANGE_TEXT = "#ED7D31", "#FDF1E5", "#C55A11"
EDGE = "#8A97A8"
WHITE = "#FFFFFF"

# (标题, 主色, 浅底, 文字色, 要点, 框) —— 三角：上=企业，左下=高校，右下=学生团队
NODES = [
    ("命题企业（广联达）", BLUE, BLUE_TINT, BLUE_TEXT,
     ["命题需求", "业务流程", "数据格式", "行业专家指导"],
     (690, 160, 1310, 460)),
    ("高校", GREEN, GREEN_TINT, GREEN_TEXT,
     ["土木工程 / 计算机视觉专业指导", "科研训练", "场地与算力支持"],
     (140, 800, 760, 1100)),
    ("学生团队", ORANGE, ORANGE_TINT, ORANGE_TEXT,
     ["需求分析", "模型训练", "系统开发", "案例验证", "成果展示"],
     (1240, 800, 1860, 1100)),
]
CENTER = (1000, 720, 140)     # 圆心 + 半径
CENTER_TEXT = ["产教融合", "协同攻关"]

# 双向边：((起点), (终点), 标签)
EDGES = [
    ((820, 460), (560, 800), "实践 / 学习"),    # 企业 — 高校（左边）
    ((1180, 460), (1440, 800), "出题 / 反馈"),  # 企业 — 学生团队（右边）
    ((760, 950), (1240, 950), "指导 / 成果"),   # 高校 — 学生团队（底边）
]


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


def double_arrow(draw, p0, p1, color, width=4.5):
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    hh, hw = 22, 12
    q0 = (x0 + hh * ux, y0 + hh * uy)
    q1 = (x1 - hh * ux, y1 - hh * uy)
    draw.line([(q0[0] * S, q0[1] * S), (q1[0] * S, q1[1] * S)],
              fill=color, width=int(width * S))
    for tip, sgn in (((x1, y1), 1), ((x0, y0), -1)):
        bx, by = tip[0] - sgn * hh * ux, tip[1] - sgn * hh * uy
        draw.polygon([(tip[0] * S, tip[1] * S),
                      ((bx - hw * uy) * S, (by + hw * ux) * S),
                      ((bx + hw * uy) * S, (by - hw * ux) * S)], fill=color)


def main():
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    # 三边双向箭头（先画，压在节点下）
    for p0, p1, _ in EDGES:
        double_arrow(d, p0, p1, EDGE)

    # 中心圆
    ccx, ccy, cr = CENTER
    d.ellipse(sc((ccx - cr, ccy - cr, ccx + cr, ccy + cr)), fill=NAVY)
    d.text((ccx * S, (ccy - 30) * S), CENTER_TEXT[0], font=font(30, bold=True),
           fill=WHITE, anchor="mm")
    d.text((ccx * S, (ccy + 30) * S), CENTER_TEXT[1], font=font(30, bold=True),
           fill=WHITE, anchor="mm")

    # 三个节点
    for title, mc, tint, tc, lines, box in NODES:
        rr(d, box, 24, tint, mc, 3.5)
        cx = (box[0] + box[2]) / 2
        d.text((cx * S, (box[1] + 52) * S), title, font=font(30, bold=True),
               fill=mc, anchor="mm")
        d.line([((box[0] + 50) * S, (box[1] + 92) * S),
                ((box[2] - 50) * S, (box[1] + 92) * S)], fill=mc, width=int(2 * S))
        f = font(24)
        y = box[1] + 122
        for ln in lines:
            d.text(((box[0] + 60) * S, y * S), "· " + ln, font=f, fill=tc, anchor="lm")
            y += 38

    # 边标签（白底小胶囊）
    f_lab = font(23, bold=True)
    for p0, p1, lab in EDGES:
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        tw = d.textlength(lab, font=f_lab) / S + 44
        rr(d, (mx - tw / 2, my - 24, mx + tw / 2, my + 24), 12, WHITE, EDGE, 2)
        d.text((mx * S, my * S), lab, font=f_lab, fill=NAVY, anchor="mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
