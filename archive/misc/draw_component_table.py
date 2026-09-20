# -*- coding: utf-8 -*-
"""生成「常泰长江大桥参数化构件清单」表格 PNG（白底，供 Word 插入）。
参数摘自常_常泰长江大桥/常泰长江大桥/ 下 16 个组件源码的 self['xxx'] = Attr(...) 定义。"""

import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "构件清单表.png"))

W = 2200
S = 2

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


NAVY = "#1F4E79"
BLUE = "#2E75B6"
ZEBRA = "#F7F9FC"
GRID = "#C9D2DE"
TEXT = "#333333"
FOOT = "#808080"

TITLE = "常泰长江大桥参数化构件清单"
FOOT_LINES = [
    "注：全部构件均为原创参数化构件，每个构件有效可调参数 ≥4 个；参数摘自组件库源码；病害定位路由对应数字孪生平台贴片归属规则。",
    "铁路封闭网组件位于组件库「铁路封闭网/」目录，一并归入附属设施。",
]

# (分类名, [(构件名, 参数列表, 路由), ...]) —— 参数逐一摘自对应 .py 源码
DATA = [
    ("上部结构", [
        ("主塔", ["底座长", "底座宽", "底座高", "中截面长", "中上高度", "上部柱子高度"], "塔"),
        ("侧面钢桁架", ["竖长", "斜长", "数量", "截面长", "截面宽", "厚度"], "桥面"),
        ("工字钢梁", ["总宽度", "总高度", "厚度", "长度"], "桥面"),
        ("斜拉索", ["斜拉索数量", "斜拉索半径", "竖向间距", "横向间距", "上间距", "下间距"], "索"),
        ("支座", ["上部平台长", "上部平台宽", "中部高", "下部平台长", "下部平台宽", "螺丝半径"], "桥面"),
        ("自密实混凝土层及隔离层", ["长度", "宽度", "高度", "凸起宽度", "凸起间隔"], "桥面"),
        ("轨道底座", ["长度", "宽度", "高度", "凹槽宽度", "凹槽深度", "凹槽间隔"], "桥面"),
    ]),
    ("下部结构", [
        ("门式桥墩", ["底面长", "底面宽", "柱高", "垫石长", "系梁长", "系梁宽"], "墩"),
        ("承台及桩基", ["承台长", "承台宽", "承台高", "横向圆柱数量", "圆柱半径", "圆柱高度"], "承台"),
        ("扩大基础", ["底长(m)", "底宽(m)", "底高", "上长", "上宽", "上高"], "承台"),
    ]),
    ("附属设施", [
        ("新泽西护栏", ["下宽", "下高", "上宽", "上高", "长度"], "附属"),
        ("防撞护栏", ["默认长度", "底宽", "顶宽", "总高"], "附属"),
        ("轨道", ["长度", "宽度", "高度", "轨枕高度", "轨枕长度", "轨枕间隔"], "附属"),
        ("接触网", ["电线杆半径", "电线杆高", "电线杆间隔", "绝缘子长", "电线长", "电线半径"], "附属"),
        ("路面及交通标线", ["中央分隔带宽度", "路缘带宽度", "单车道宽度", "应急车道宽度", "单侧车道数初始值"], "附属"),
        ("铁路封闭网", ["立柱边长", "长杆高", "线半径", "柱子间隔", "单块网高度", "立柱间隔块数"], "附属"),
    ]),
]

# ---------- 布局 ----------
MARGIN_X = 130
COL_W = [130, 320, 1230, 260]          # 序号/构件名称/主要可调参数/病害定位路由
COL_ALIGN = ["center", "center", "left", "center"]
HEADERS = ["序号", "构件名称", "主要可调参数", "病害定位路由"]
TABLE_X0 = MARGIN_X
TABLE_X1 = W - MARGIN_X
TITLE_CY = 75
TABLE_Y0 = 150
ROW_H = 66           # 单行数据行高
LINE_H = 36          # 参数列换行行距
ROW_PAD = 15         # 行内上下留白
HEAD_H = 62
CAT_H = 56


def wrap_params(draw, text, fnt, max_w):
    """按顿号边界换行，返回行列表。"""
    parts = text.split("、")
    lines, cur = [], ""
    for p in parts:
        cand = p if not cur else cur + "、" + p
        if draw.textlength(cand, font=fnt) <= max_w * S:
            cur = cand
        else:
            lines.append(cur)
            cur = p
    if cur:
        lines.append(cur)
    return lines


def main():
    f_title = font(44, bold=True)
    f_head = font(26, bold=True)
    f_cat = font(25, bold=True)
    f_cell = font(25)
    f_name = font(24, bold=True)
    f_param = font(24)
    f_foot = font(20)

    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))

    # 第一遍：计算行高
    param_w = COL_W[2] - 48
    rows = []          # ("head" | "cat" | "data", payload, height)
    rows.append(("head", HEADERS, HEAD_H))
    for cat, items in DATA:
        rows.append(("cat", f"{cat}（{len(items)} 项）", CAT_H))
        for no_name in items:
            name, params, route = no_name
            ptext = "、".join(params)
            lines = wrap_params(probe, ptext, f_param, param_w)
            h = max(ROW_H, len(lines) * LINE_H + 2 * ROW_PAD)
            rows.append(("data", (name, lines, route), h))

    table_h = sum(r[2] for r in rows)
    foot_y = TABLE_Y0 + table_h + 26
    H = int(foot_y + len(FOOT_LINES) * 30 + 40)

    img = Image.new("RGB", (W * S, H * S), "#FFFFFF")
    d = ImageDraw.Draw(img)

    # 标题
    d.text((W / 2 * S, TITLE_CY * S), TITLE, font=f_title, fill=NAVY, anchor="mm")

    # 列 x 边界
    xs = [TABLE_X0]
    for w in COL_W:
        xs.append(xs[-1] + w)

    y = TABLE_Y0
    zebra = 0
    for kind, payload, h in rows:
        yb = y + h
        if kind == "head":
            d.rectangle([TABLE_X0 * S, y * S, TABLE_X1 * S, yb * S], fill=NAVY)
            for i, t in enumerate(payload):
                d.text(((xs[i] + xs[i + 1]) / 2 * S, (y + yb) / 2 * S), t,
                       font=f_head, fill="#FFFFFF", anchor="mm")
        elif kind == "cat":
            d.rectangle([TABLE_X0 * S, y * S, TABLE_X1 * S, yb * S], fill=BLUE)
            d.text(((TABLE_X0 + 30) * S, (y + yb) / 2 * S), payload,
                   font=f_cat, fill="#FFFFFF", anchor="lm")
        else:
            name, plines, route = payload
            if zebra % 2 == 1:
                d.rectangle([TABLE_X0 * S, y * S, TABLE_X1 * S, yb * S], fill=ZEBRA)
            zebra += 1
            cy = (y + yb) / 2
            # 序号（全局连续）
            d.text(((xs[0] + xs[1]) / 2 * S, cy * S), str(zebra), font=f_cell,
                   fill=TEXT, anchor="mm")
            d.text(((xs[1] + xs[2]) / 2 * S, cy * S), name, font=f_name,
                   fill=NAVY, anchor="mm")
            # 参数列：左对齐，多行垂直居中
            block_h = len(plines) * LINE_H
            ty = cy - block_h / 2 + LINE_H / 2
            for ln in plines:
                d.text(((xs[2] + 24) * S, ty * S), ln, font=f_param,
                       fill=TEXT, anchor="lm")
                ty += LINE_H
            d.text(((xs[3] + xs[4]) / 2 * S, cy * S), route, font=f_cell,
                   fill=TEXT, anchor="mm")
        # 行内竖线（分类通栏行不画）
        if kind in ("head", "data"):
            for x in xs:
                d.line([(x * S, y * S), (x * S, yb * S)], fill=GRID,
                       width=int(1.5 * S))
        # 行底线
        d.line([(TABLE_X0 * S, yb * S), (TABLE_X1 * S, yb * S)],
               fill=GRID, width=int(1.5 * S))
        y = yb

    # 表顶线 + 外框竖线
    d.line([(TABLE_X0 * S, TABLE_Y0 * S), (TABLE_X1 * S, TABLE_Y0 * S)],
           fill=GRID, width=int(1.5 * S))
    for x in (xs[0], xs[-1]):
        d.line([(x * S, TABLE_Y0 * S), (x * S, y * S)], fill=GRID,
               width=int(1.5 * S))

    # 脚注
    fy = foot_y
    for ln in FOOT_LINES:
        d.text((TABLE_X0 * S, fy * S), ln, font=f_foot, fill=FOOT, anchor="ls")
        fy += 30

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)
    total = sum(len(items) for _, items in DATA)
    print("components:", total)
    for cat, items in DATA:
        for name, params, route in items:
            print(f"  [{cat}] {name}: {len(params)} 参数 -> {route}")


if __name__ == "__main__":
    main()
