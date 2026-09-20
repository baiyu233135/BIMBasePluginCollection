# -*- coding: utf-8 -*-
"""生成「智检桥安系统总体架构」四层架构图 PNG（白底，供 Word 插入）。"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "架构图_系统总体架构.png"))

W, H = 2200, 1400
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
WHITE = "#FFFFFF"

TITLE = "智检桥安系统总体架构"
BRACKET_TEXT = "五环业务流程贯通：采集→识别→量化→定位→报告"

# (层名, 主色, 浅底, [小方块文字]) —— 自上而下（顶层=应用层）
LAYERS = [
    ("应用层", "#548235", "#EFF5E9",
     ["桌面检测插件", "检测报告自动生成", "数字孪生在线平台", "三维可视化"]),
    ("引擎层", NAVY, "#E4EAF2",
     ["国产 BIMBase 三维图形引擎 + pyp3d"]),
    ("算法层", "#4472C4", "#EAF0FA",
     ["YOLOv8n 检测模型", "免模型五路CV融合", "Qwen-VL 多模态诊断", "尺寸量化与面投影"]),
    ("数据层", "#6E7F96", "#EEF1F5",
     ["公开数据集\nGYU-DET / CODEBRIM", "本地标注数据集", "无人机巡检照片", "常泰长江大桥\nBIM 模型"]),
]

BAND_X0, BAND_X1 = 260, 2140
BAND_H, BAND_GAP = 250, 40
BAND_Y0 = 150
CHIP = (290, 450)          # 层名标签 x 范围
BOX_AREA = (500, 2100)     # 小方块区域


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


def up_arrow(draw, x, y0, y1, color, width=6):
    """从 y0(下) 指向 y1(上) 的箭头。"""
    draw.line([(x * S, y0 * S), (x * S, (y1 + 16) * S)], fill=color, width=int(width * S))
    hw, hh = 13 * S, 18 * S
    tip = (x * S, y1 * S)
    draw.polygon([tip, (tip[0] - hw, tip[1] + hh), (tip[0] + hw, tip[1] + hh)], fill=color)


def main():
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    f_title = font(46, bold=True)
    f_chip = font(30, bold=True)
    f_box = font(26, bold=True)
    f_engine = font(30, bold=True)
    f_badge = font(24, bold=True)
    f_bracket = font(28, bold=True)

    d.text((W / 2 * S, 70 * S), TITLE, font=f_title, fill=NAVY, anchor="mm")

    band_bottoms = []
    for li, (name, mc, tint, boxes) in enumerate(LAYERS):
        y0 = BAND_Y0 + li * (BAND_H + BAND_GAP)
        y1 = y0 + BAND_H
        band_bottoms.append((y0, y1))

        emphasis = (name == "引擎层")
        rr(d, (BAND_X0, y0, BAND_X1, y1), 24, tint,
           NAVY if emphasis else None, 4)

        # 层名标签
        cy = (y0 + y1) / 2
        rr(d, (CHIP[0], cy - 45, CHIP[1], cy + 45), 16, mc)
        d.text(((CHIP[0] + CHIP[1]) / 2 * S, cy * S), name, font=f_chip,
               fill=WHITE, anchor="mm")

        if len(boxes) == 1:
            # 引擎层：整条白框 + 自主可控角标
            bx = (BOX_AREA[0], y0 + 65, BOX_AREA[1], y1 - 65)
            rr(d, bx, 18, WHITE, mc, 3)
            d.text(((bx[0] + bx[2]) / 2 * S, cy * S), boxes[0], font=f_engine,
                   fill=NAVY, anchor="mm")
            bw, bh = 190, 60
            rr(d, (bx[2] - 25 - bw, bx[1] - bh / 2, bx[2] - 25, bx[1] + bh / 2),
               28, ORANGE)
            d.text(((bx[2] - 25 - bw / 2) * S, bx[1] * S), "自主可控",
                   font=f_badge, fill=WHITE, anchor="mm")
        else:
            n = len(boxes)
            gap = 40
            bw = (BOX_AREA[1] - BOX_AREA[0] - (n - 1) * gap) / n
            for i, t in enumerate(boxes):
                x0 = BOX_AREA[0] + i * (bw + gap)
                bx = (x0, y0 + 60, x0 + bw, y1 - 60)
                rr(d, bx, 18, WHITE, mc, 3)
                d.text(((bx[0] + bx[2]) / 2 * S, cy * S), t, font=f_box,
                       fill=mc, anchor="mm", align="center", spacing=int(8 * S))

    # 层间上行箭头（数据自底向上流动，仅画在层间空隙）
    for li in range(1, len(LAYERS)):
        y_top = band_bottoms[li - 1][1]      # 上一层底边
        y_bot = band_bottoms[li][0]          # 本层顶边
        for x in (800, 1200, 1600):
            up_arrow(d, x, y_bot, y_top, GRAY)

    # 左侧竖向括号标注
    d.line([(215 * S, BAND_Y0 * S), (215 * S, (BAND_Y0 + 4 * BAND_H + 3 * BAND_GAP) * S)],
           fill=NAVY, width=int(3 * S))
    for yy in (BAND_Y0, BAND_Y0 + 4 * BAND_H + 3 * BAND_GAP):
        d.line([(195 * S, yy * S), (215 * S, yy * S)], fill=NAVY, width=int(3 * S))
    tmp = Image.new("RGBA", (int(1300 * S), int(60 * S)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((650 * S, 30 * S), BRACKET_TEXT, font=f_bracket,
                             fill=NAVY, anchor="mm")
    tmp = tmp.rotate(90, expand=True)   # 逆时针，自下而上读（与数据流向一致）
    img.paste(tmp, (int(120 * S - tmp.width / 2),
                    int((BAND_Y0 + 1270) / 2 * S - tmp.height / 2)), tmp)

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
