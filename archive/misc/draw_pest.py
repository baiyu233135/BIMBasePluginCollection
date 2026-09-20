# -*- coding: utf-8 -*-
"""生成「PEST 宏观环境分析」四象限图 PNG（白底，供 Word 插入）。"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "分析图_PEST.png"))

W, H = 2000, 1400
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


NAVY = "#1F4E79"
WHITE = "#FFFFFF"

# (字母+名称, 主色, 浅底, 文字色, 三条短句, 象限框)
QUADS = [
    ("P  政治", "#4472C4", "#EAF0FA", "#2F5496",
     ["交通强国战略", "基础设施智慧运维政策", "国产软件自主可控导向"],
     (110, 130, 990, 640)),
    ("E  经济", "#548235", "#EFF5E9", "#3E6226",
     ["百万座桥梁进入运维期", "检测养护市场持续增长", "人工成本上升倒逼智能化"],
     (1010, 130, 1890, 640)),
    ("S  社会", "#7030A0", "#F2EAF7", "#522174",
     ["桥梁安全关乎公共安全", "检测人员高空作业风险", "基层管养数字化人才缺口"],
     (110, 710, 990, 1220)),
    ("T  技术", "#ED7D31", "#FDF1E5", "#C55A11",
     ["深度学习检测成熟", "多模态大模型普及", "国产三维引擎 BIMBase 生态完善"],
     (1010, 710, 1890, 1220)),
]
CENTER = (1000, 675, 105)


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


def main():
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    f_head = font(32, bold=True)
    f_line = font(26)

    for title, mc, tint, tc, lines, box in QUADS:
        rr(d, box, 28, tint, mc, 3)
        # 标题牌
        rr(d, (box[0] + 40, box[1] + 34, box[0] + 240, box[1] + 102), 16, mc)
        d.text(((box[0] + 140) * S, (box[1] + 68) * S), title, font=f_head,
               fill=WHITE, anchor="mm")
        # 三条短句
        y = box[1] + 180
        for ln in lines:
            d.text(((box[0] + 60) * S, y * S), "· " + ln, font=f_line,
                   fill=tc, anchor="lm")
            y += 62

    # 中心圆
    ccx, ccy, cr = CENTER
    d.ellipse(sc((ccx - cr, ccy - cr, ccx + cr, ccy + cr)), fill=WHITE,
              outline=NAVY, width=int(4 * S))
    d.text((ccx * S, (ccy - 26) * S), "PEST", font=font(40, bold=True),
           fill=NAVY, anchor="mm")
    d.text((ccx * S, (ccy + 30) * S), "分析", font=font(28, bold=True),
           fill=NAVY, anchor="mm")

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
