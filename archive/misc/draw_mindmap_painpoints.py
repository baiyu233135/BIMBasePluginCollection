# -*- coding: utf-8 -*-
"""生成「桥梁检测业务流程痛点 × 智检桥安对策」思维导图 PNG（白底，供 Word 插入）。"""

import os
from PIL import Image, ImageDraw, ImageFont

# ---------- 输出 ----------
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "国创赛ppt")
OUT_PATH = os.path.abspath(os.path.join(OUT_DIR, "思维导图_检测业务流程痛点.png"))

# ---------- 画布 ----------
W, H = 2200, 1400
S = 2  # 2 倍渲染后降采样，保证清晰度

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BLD = "C:/Windows/Fonts/msyhbd.ttc"
for p in (FONT_REG, FONT_BLD):
    if not os.path.exists(p):
        raise FileNotFoundError(p)


def font(size, bold=False):
    return ImageFont.truetype(FONT_BLD if bold else FONT_REG, int(size * S))


# ---------- 颜色 ----------
CENTER_FILL = "#1F4E79"
PAIN_FILL, PAIN_EDGE, PAIN_TEXT = "#FBECEC", "#C0504D", "#943634"
PLAN_FILL, PLAN_EDGE, PLAN_TEXT = "#EBF2FA", "#2E75B6", "#1F5C99"
BAR_FILL, BAR_EDGE, BAR_TEXT_COLOR = "#FDF1E5", "#ED7D31", "#C55A11"
GRAY = "#9AA5B1"
WHITE = "#FFFFFF"

BRANCH_COLORS = ["#4472C4", "#548235", "#7030A0", "#BF8F00", "#31859C"]

# ---------- 内容 ----------
BRANCHES = [
    ("图像采集",
     ["照片量大角度杂", "构件对应靠人工记录", "归档工作量大"],
     ["无人机航线化采集", "照片与桩号构件自动关联"]),
    ("人工判读",
     ["依赖个人经验", "主观性强标准不一", "登高作业危险"],
     ["YOLOv8 六类损伤自动识别", "+ 五路CV免模型冷启动", "+ Qwen-VL 大模型诊断"]),
    ("尺寸测量",
     ["现场人工量测", "高空危险效率低", "数据离散度大"],
     ["像素—物理尺度自动换算", "输出长度宽度面积"]),
    ("空间定位",
     ["文字描述位置", "无法三维归档", "复查难以回溯"],
     ["解析式 2D→3D 面投影", "病害精准定位到 BIM 构件"]),
    ("报告编制",
     ["多人分步誊录易错", "周期长", "与养护决策脱节"],
     ["一键生成规范化 Word 报告", "数据直达养护决策"]),
]
BAR_TEXT = "核心诉求：打通「图像采集 → 损伤识别 → 量化分析 → 空间定位 → 报告输出」数字化闭环，实现检测全流程提质增效"

# ---------- 布局（逻辑坐标）----------
CENTER_BOX = (30, 515, 430, 775)          # 中心节点
COL_STAGE = (520, 760)                     # 环节列 x0,x1
COL_PAIN = (850, 1440)                     # 痛点列
COL_PLAN = (1530, 2170)                    # 对策列
ROW_TOP, ROW_BOT = 50, 1240
BAR_BOX = (30, 1275, 2170, 1365)

PITCH = (ROW_BOT - ROW_TOP) / 5
ROW_CY = [ROW_TOP + PITCH * (i + 0.5) for i in range(5)]
CENTER_CY = (CENTER_BOX[1] + CENTER_BOX[3]) / 2

STAGE_H, NODE_H = 100, 180


def sc(box):
    return [int(v * S) for v in box]


def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(sc(box), radius=int(radius * S), fill=fill,
                           outline=outline, width=int(width * S))


def bezier_points(p0, p3, n=60):
    x0, y0 = p0
    x3, y3 = p3
    dx = max(60, (x3 - x0) * 0.5)
    p1 = (x0 + dx, y0)
    p2 = (x3 - dx, y3)
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3 * x0 + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * x3
        y = mt**3 * y0 + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * y3
        pts.append((x * S, y * S))
    return pts


def connect(draw, src_right, dst_left, color, arrow=True):
    x0, y0 = src_right
    x1, y1 = dst_left
    end_x = x1 - (16 if arrow else 2)
    pts = bezier_points((x0, y0), (end_x, y1))
    draw.line(pts, fill=color, width=int(4.5 * S), joint="curve")
    if arrow:
        a = 9 * S
        tip = (x1 * S, y1 * S)
        draw.polygon([tip, (tip[0] - 18 * S, tip[1] - a),
                      (tip[0] - 18 * S, tip[1] + a)], fill=color)


def center_text(draw, box, lines, fnt, fill, spacing=12):
    cx = (box[0] + box[2]) / 2 * S
    cy = (box[1] + box[3]) / 2 * S
    draw.multiline_text((cx, cy), "\n".join(lines), font=fnt, fill=fill,
                        anchor="mm", align="center", spacing=int(spacing * S))


def main():
    img = Image.new("RGB", (W * S, H * S), WHITE)
    d = ImageDraw.Draw(img)

    f_center = font(32, bold=True)
    f_stage = font(34, bold=True)
    f_node = font(28)
    f_bar = font(34, bold=True)

    # 底部结论条（先画，避免压线）
    rr(d, BAR_BOX, 20, BAR_FILL, BAR_EDGE, 3)
    # 结论条文字宽度自检，过宽则缩字号
    fb = f_bar
    while d.textlength(BAR_TEXT, font=fb) > (BAR_BOX[2] - BAR_BOX[0] - 60) * S:
        fb = ImageFont.truetype(FONT_BLD, fb.size - S)
    center_text(d, BAR_BOX, [BAR_TEXT], fb, BAR_TEXT_COLOR)

    # 中心节点
    rr(d, CENTER_BOX, 26, CENTER_FILL)
    center_text(d, CENTER_BOX,
                ["桥梁检测业务流程痛点", "×", "智检桥安对策"],
                f_center, WHITE, spacing=14)

    cx_r = CENTER_BOX[2]

    for i, (stage, pains, plans) in enumerate(BRANCHES):
        color = BRANCH_COLORS[i]
        cy = ROW_CY[i]
        stage_box = (COL_STAGE[0], cy - STAGE_H / 2, COL_STAGE[1], cy + STAGE_H / 2)
        pain_box = (COL_PAIN[0], cy - NODE_H / 2, COL_PAIN[1], cy + NODE_H / 2)
        plan_box = (COL_PLAN[0], cy - NODE_H / 2, COL_PLAN[1], cy + NODE_H / 2)

        # 连接线
        connect(d, (cx_r, CENTER_CY), (stage_box[0], cy), color)
        connect(d, (stage_box[2], cy), (pain_box[0], cy), GRAY)
        connect(d, (pain_box[2], cy), (plan_box[0], cy), GRAY)

        # 环节节点
        rr(d, stage_box, 18, color)
        center_text(d, stage_box, [stage], f_stage, WHITE)

        # 痛点节点
        rr(d, pain_box, 18, PAIN_FILL, PAIN_EDGE, 3)
        center_text(d, pain_box, pains, f_node, PAIN_TEXT, spacing=13)

        # 对策节点
        rr(d, plan_box, 18, PLAN_FILL, PLAN_EDGE, 3)
        center_text(d, plan_box, plans, f_node, PLAN_TEXT, spacing=13)

    os.makedirs(OUT_DIR, exist_ok=True)
    img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT_PATH, "PNG")
    print("saved:", OUT_PATH, img.size)


if __name__ == "__main__":
    main()
