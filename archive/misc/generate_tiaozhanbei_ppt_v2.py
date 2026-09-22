# -*- coding: utf-8 -*-
"""生成 25 页挑战杯产业赛道 PPT v2：桥元智构（ciaftlink 蓝白科技风）

输出：
  docs/挑战杯项目官方文件及参考/挑战杯产业赛道_桥元智构_v2.pptx
  docs/挑战杯项目官方文件及参考/配图线索清单_桥元智构v2.md
"""
import math
import os

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.dml import MSO_LINE
from pptx.oxml.ns import qn

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_DIR = os.path.join(ROOT, "docs", "挑战杯项目官方文件及参考")
OUT = os.path.join(OUT_DIR, "挑战杯产业赛道_桥元智构_v2.pptx")
MD_OUT = os.path.join(OUT_DIR, "配图线索清单_桥元智构v2.md")

# ---- 色板（ciaftlink 蓝白科技风） ----
DEEP   = RGBColor(0x0F, 0x6C, 0xC6)   # 深蓝：标题/重点
BLUE   = RGBColor(0x14, 0x87, 0xF0)   # 亮蓝：渐变起
CYAN   = RGBColor(0x0A, 0xCB, 0xF8)   # 青：渐变止/点缀
ORANGE = RGBColor(0xFB, 0x90, 0x17)   # 橙：强调点缀（少量）
TEXT   = RGBColor(0x33, 0x33, 0x33)   # 正文深灰
SUB    = RGBColor(0x7F, 0x9F, 0xBF)   # 副题灰蓝
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
BG_TOP = RGBColor(0xF5, 0xFA, 0xFF)   # 页面背景渐变起
BG_BOT = RGBColor(0xDC, 0xEE, 0xFF)   # 页面背景渐变止
BORDER = RGBColor(0xB9, 0xD6, 0xF2)   # 卡片边框
CHIPBG = RGBColor(0xEA, 0xF4, 0xFF)   # 小芯片底色
NUMBL  = RGBColor(0x9F, 0xCE, 0xF5)   # 大号浅蓝序号
PH_BG  = RGBColor(0xF2, 0xF2, 0xF2)   # 占位框底
PH_LN  = RGBColor(0xA6, 0xA6, 0xA6)   # 占位框虚线
PH_TX  = RGBColor(0x8C, 0x8C, 0x8C)   # 占位框文字
WAVE1  = RGBColor(0xA8, 0xE6, 0xFB)   # 波浪最浅层
FONT = "微软雅黑"

PAGE_W, PAGE_H = 12192000, 6858000    # 16:9
IW, IH = 13.3333, 7.5                 # 英寸
MX = 0.45                             # 左右边距
CW = 12.4333                          # 内容宽（0.45..12.8833）

prs = Presentation()
prs.slide_width = Emu(PAGE_W)
prs.slide_height = Emu(PAGE_H)
BLANK = prs.slide_layouts[6]

IMG_SPOTS = []   # (page, pos, need, how) 配图占位
PHOTOS = []      # (page, pos, desc) 照片占位


# ===================== 基础工具 =====================
def _font(run, size, color, bold):
    f = run.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        e = rPr.find(qn(tag))
        if e is None:
            e = rPr.makeelement(qn(tag), {})
            rPr.append(e)
        e.set("typeface", FONT)


def txt(slide, x, y, w, h, lines, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
        space_after=6, line_spacing=1.08, size=12, color=TEXT, bold=False):
    """lines: str | (text,size,color,bold) | [(text,size,color,bold), ...] 的列表"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    first = True
    for ln in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.space_after = Pt(space_after)
        p.line_spacing = line_spacing
        if isinstance(ln, str):
            runs = [(ln, size, color, bold)]
        elif isinstance(ln, tuple):
            runs = [ln]
        else:
            runs = ln
        for rtext, rsize, rcolor, rbold in runs:
            r = p.add_run()
            r.text = rtext
            _font(r, rsize, rcolor, rbold)
    return tb


def shape_text(sp, lines, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
               space_after=2, line_spacing=1.0, size=12, color=WHITE, bold=True):
    tf = sp.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = 0
    first = True
    for ln in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        p.space_after = Pt(space_after)
        p.line_spacing = line_spacing
        if isinstance(ln, str):
            runs = [(ln, size, color, bold)]
        elif isinstance(ln, tuple):
            runs = [ln]
        else:
            runs = ln
        for rtext, rsize, rcolor, rbold in runs:
            r = p.add_run()
            r.text = rtext
            _font(r, rsize, rcolor, rbold)
    return sp


def box(slide, x, y, w, h, shape=MSO_SHAPE.RECTANGLE, fill=WHITE, line=None,
        line_w=1.0, adj=None, dash=False):
    sp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if adj is not None:
        try:
            sp.adjustments[0] = adj
        except Exception:
            pass
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(line_w)
        if dash:
            sp.line.dash_style = MSO_LINE.DASH
    sp.shadow.inherit = False
    return sp


def grad(sp, c1, c2, angle=None):
    sp.fill.gradient()
    sp.fill.gradient_stops[0].color.rgb = c1
    sp.fill.gradient_stops[1].color.rgb = c2
    try:
        if angle is not None:
            sp.fill.gradient_angle = angle
    except Exception:
        pass
    return sp


def est_w(text, size):
    """估算文本宽度（英寸）：CJK 全宽、大写/数字 0.68、小写 0.54、空格 0.35"""
    w = 0.0
    for ch in text:
        o = ord(ch)
        if o >= 0x2E80:
            w += size / 72.0
        elif ch == " ":
            w += size / 72.0 * 0.35
        elif ch.isascii() and (ch.isupper() or ch.isdigit()):
            w += size / 72.0 * 0.68
        else:
            w += size / 72.0 * 0.54
    return w


def bg(slide):
    sp = box(slide, 0, 0, IW, IH, fill=WHITE)
    grad(sp, BG_TOP, BG_BOT, angle=90)
    return sp


def wave(slide, y_base, amp, lam, phase, color):
    """正弦波色带：顶边 y = y_base - amp*cos(2πx/λ + phase)，向下封底"""
    steps = 72
    pts = []
    for i in range(steps + 1):
        x = IW * i / steps
        yy = y_base - amp * math.cos(2 * math.pi * x / lam + phase)
        pts.append((int(Inches(x)), int(Inches(yy))))
    fb = slide.shapes.build_freeform(pts[0][0], pts[0][1], scale=1.0)
    fb.add_line_segments(pts[1:] + [(PAGE_W, PAGE_H), (0, PAGE_H)], close=True)
    sp = fb.convert_to_shape(Emu(0), Emu(0))
    sp.fill.solid()
    sp.fill.fore_color.rgb = color
    sp.line.fill.background()
    sp.shadow.inherit = False
    return sp


def waves(slide, page=None):
    """底部三层波浪 + 封底矩形 + 页脚文字"""
    wave(slide, 6.97, 0.075, 7.6, 1.2, WAVE1)
    wave(slide, 7.09, 0.080, 5.3, 2.6, CYAN)
    wave(slide, 7.235, 0.075, 6.6, 0.0, BLUE)
    box(slide, 0, 7.30, IW, 0.20, fill=BLUE)   # 封底，保证文字始终落在蓝色上
    if page is not None:
        txt(slide, 0.45, 7.295, 8.6, 0.19,
            [("桥元智构 · 基于国产 BIMBase 与人工智能的桥梁建养一体化平台", 9, WHITE, False)],
            anchor=MSO_ANCHOR.MIDDLE, space_after=0)
        txt(slide, 11.28, 7.295, 1.6, 0.19,
            [(f"{page:02d} / 25", 9, WHITE, True)],
            align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE, space_after=0)


def header(slide, abbr, title, subtitle):
    """内页页眉：渐变图标 + 26pt 深蓝标题 + 9.5pt 副题 + 渐变细条"""
    icon = box(slide, MX, 0.28, 0.50, 0.50, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.25)
    grad(icon, BLUE, CYAN, angle=45)
    shape_text(icon, [(abbr, 13, WHITE, True)])
    txt(slide, 1.12, 0.16, 11.7, 0.56, [(title, 26, DEEP, True)],
        anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    txt(slide, 1.14, 0.76, 11.6, 0.24, [(subtitle, 9.5, SUB, False)],
        anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    bar = box(slide, MX, 1.06, CW, 0.035)
    grad(bar, BLUE, CYAN, angle=0)


def card(slide, x, y, w, h):
    return box(slide, x, y, w, h, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
               fill=WHITE, line=BORDER, line_w=1.0, adj=0.06)


def pill(slide, x, y, w, h, text, size=13, c1=BLUE, c2=CYAN):
    sp = box(slide, x, y, w, h, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.5)
    grad(sp, c1, c2, angle=0)
    shape_text(sp, [(text, size, WHITE, True)])
    return sp


def pill_auto(slide, x, y, h, text, size=13, c1=BLUE, c2=CYAN, pad=0.50):
    w = max(1.0, est_w(text, size) + pad)
    return pill(slide, x, y, w, h, text, size, c1, c2), w


def bar(slide, x, y, w, h, text, size=14, style="blue"):
    sp = box(slide, x, y, w, h, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.5)
    if style == "orange":
        grad(sp, ORANGE, RGBColor(0xFB, 0xAF, 0x4F), angle=0)
    elif style == "deep":
        grad(sp, DEEP, BLUE, angle=0)
    else:
        grad(sp, BLUE, CYAN, angle=0)
    shape_text(sp, [(text, size, WHITE, True)])
    return sp


def img_ph(slide, x, y, w, h, page, pos, need, how):
    sp = box(slide, x, y, w, h, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
             fill=PH_BG, line=PH_LN, line_w=1.0, adj=0.045, dash=True)
    shape_text(sp, [("【配图线索】", 10.5, PH_TX, True),
                    (need, 10.5, PH_TX, False),
                    (f"（获取方式：{how}）", 9, PH_LN, False)],
               space_after=4)
    IMG_SPOTS.append((page, pos, need, how))
    return sp


def chev(slide, x, y, w, h, text, size=11, c1=BLUE, c2=CYAN):
    sp = box(slide, x, y, w, h, shape=MSO_SHAPE.CHEVRON)
    grad(sp, c1, c2, angle=0)
    shape_text(sp, [(text, size, WHITE, True)])
    return sp


def num_badge(slide, x, y, d, num, c1=BLUE, c2=CYAN):
    sp = box(slide, x, y, d, d, shape=MSO_SHAPE.OVAL)
    grad(sp, c1, c2, angle=45)
    shape_text(sp, [(num, 12, WHITE, True)])
    tf = sp.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return sp


# ===================== P1 封面 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
# 顶部药丸横幅
banner = box(s, (IW - 9.3) / 2, 0.32, 9.3, 0.50, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.5)
grad(banner, BLUE, CYAN, angle=0)
shape_text(banner, [("第十九届“挑战杯”全国大学生课外学术科技作品竞赛 · 中国青年科技创新“揭榜挂帅”擂台赛",
                     12.5, WHITE, True)])
# 左侧标题区
txt(s, 0.72, 1.28, 6.7, 1.05, [("桥元智构", 54, DEEP, True)], space_after=0)
txt(s, 0.74, 2.46, 6.75, 0.62,
    [("基于国产 BIMBase 三维引擎与人工智能的", 18, BLUE, True),
     ("桥梁建养一体化平台", 18, BLUE, True)], space_after=0, line_spacing=1.05)
txt(s, 0.74, 3.30, 6.6, 0.30,
    [("BridgeElement Intelligence · BIMBase × AI", 11, SUB, False)], space_after=0)
# 三个药丸标签
tags = [
    ("参赛赛道", "产业赛道（揭榜挂帅）", 11),
    ("参赛赛题", "XH-202601 人工智能与国产三维图形引擎关键核心技术的融合创新应用研究", 10.5),
    ("发榜单位", "中国建筑科学研究院有限公司", 11),
]
for i, (lab, val, vs) in enumerate(tags):
    ty = 3.78 + i * 0.60
    pill(s, 0.74, ty, 1.22, 0.44, lab, 11)
    tb_box = box(s, 2.08, ty, 5.55, 0.44, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
                 fill=WHITE, line=BORDER, line_w=1.0, adj=0.5)
    tf = tb_box.text_frame
    tf.margin_left = Inches(0.16)
    shape_text(tb_box, [(val, vs, DEEP, True)], align=PP_ALIGN.LEFT)
txt(s, 0.74, 5.70, 6.9, 0.32,
    [("参赛学校：______（待填写）  团队名称：______（待填写）  指导教师：______（待填写）",
      10.5, TEXT, False)], space_after=0)
txt(s, 0.74, 6.22, 6.9, 0.42,
    [("建 · 验 · 诊 · 养 全链路闭环 ｜ 常泰长江大桥真实工程验证", 14, DEEP, True)], space_after=0)
# 右侧大图占位
img_ph(s, 7.70, 1.35, 5.15, 4.90, "P1", "封面右侧大图",
       "常泰长江大桥 P3D 全景截图",
       "BIMBase 中打开 P3D文件/常泰长江大桥.p3d，三维视图截图")
waves(s)

# ===================== P2 目录 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "目录", "目录", "CONTENTS · 桥元智构汇报框架")
toc = [
    ("01", "行业背景与痛点", "国产引擎 · 人工巡检 · 数据割裂"),
    ("02", "研究意义与现状", "国内外研究进展"),
    ("03", "项目总览与目标", "建-验-诊-养闭环 · 技术底座"),
    ("04", "智能建造 · 建", "AI 建模 · CAD 画板 · 图纸识别 · 组件库"),
    ("05", "工程验证 · 验", "常泰长江大桥 P3D 工程"),
    ("06", "智能诊断 · 诊", "病害检测 · AI 诊断 · 面投影"),
    ("07", "智慧养护 · 养", "报告闭环 · 数字孪生"),
    ("08", "特色创新与产业价值", "项目特色 · 六项创新 · 推广路径"),
]
for i, (num, t, d) in enumerate(toc):
    r, c = divmod(i, 2)
    x = MX + c * 6.38
    y = 1.32 + r * 1.32
    card(s, x, y, 6.05, 1.18)
    txt(s, x + 0.30, y, 0.95, 1.18, [(num, 26, NUMBL, True)],
        anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    txt(s, x + 1.35, y + 0.16, 4.55, 0.86,
        [(t, 15, DEEP, True), (d, 10, SUB, False)], space_after=5)
waves(s, 2)

# ===================== P3 行业背景 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "背景", "行业背景 · 政策与战略驱动", "“十五五”开局，智能建造与自主可控的双重号角")
bg_cards = [
    ("交通强国战略深入推进",
     "我国桥梁保有量居世界前列，运维养管需求持续增长，桥梁数字化建养成为行业共识。【行业数据待补权威来源】"),
    ("国产三维引擎自主可控",
     "BIM 基础三维图形引擎的自主可控，已成为关乎国家重大工程建设安全与建设领域数字主权的关键战役。（引自赛题文件）"),
    ("AI×BIM 融合新赛道",
     "发榜单位中国建研院自主研发的 BIMBase 平台已实现设计工具层面自主化，亟需探索 AI 在智能建模、智慧运维等场景的融合应用。"),
]
for i, (t, d) in enumerate(bg_cards):
    x = MX + i * 4.23
    card(s, x, 1.45, 3.97, 3.60)
    pill(s, x + 0.25, 1.69, 3.47, 0.44, t, 13)
    txt(s, x + 0.30, 2.37, 3.37, 2.50, [(d, 12, TEXT, False)],
        space_after=6, line_spacing=1.22)
img_ph(s, MX, 5.30, CW, 1.42, "P3", "底部横幅",
       "政策文件或桥梁全景横幅图 1 张",
       "政府官网/新闻下载，或用常泰长江大桥 P3D 全景裁切")
waves(s, 3)

# ===================== P4 研究痛点 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "痛点", "研究痛点", "桥梁建养行业的四大结构性难题")
pains = [
    ("引擎受制于人", "桥梁三维设计建模长期依赖国外商业 BIM 软件，国产三维图形引擎存在“卡脖子”风险"),
    ("巡检依赖人工", "病害检测以人工目测为主，效率低、主观性强，高空水上作业危险"),
    ("病害与模型脱节", "检测结果停留在纸质报告与二维照片，无法落位到 BIM 具体构件，病害演变难以追踪"),
    ("建养数据割裂", "建造模型与运维数据互不贯通，模型价值随竣工而终结"),
]
for i, (t, d) in enumerate(pains):
    r, c = divmod(i, 2)
    x = MX + c * 6.38
    y = 1.36 + r * 2.30
    card(s, x, y, 6.05, 2.12)
    pill(s, x + 0.28, y + 0.22, 2.30, 0.42, f"0{i+1} · {t}", 12.5)
    txt(s, x + 0.32, y + 0.82, 5.45, 1.15, [(d, 11.5, TEXT, False)],
        space_after=4, line_spacing=1.15)
bar(s, MX, 6.06, CW, 0.56, "亟需“国产引擎 + 人工智能”的桥梁建养一体化平台", 15, "orange")
waves(s, 4)

# ===================== P5 研究意义 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "意义", "研究意义", "为什么做 —— 三重价值")
means = [
    ("01", "推动桥梁建养数字化转型",
     "提供“国产引擎 + AI”全流程方案，助力桥梁运维从“经验驱动”向“数据驱动”跨越"),
    ("02", "填补国产平台应用空白",
     "首个基于国产 BIMBase 引擎的“病害识别 — BIM 投影”闭环，为 BIMBase 生态贡献桥梁专业插件体系"),
    ("03", "服务国家自主可控战略",
     "从三维引擎到 AI 应用全栈摆脱对国外平台依赖，保障桥梁工程数据安全"),
]
for i, (num, t, d) in enumerate(means):
    x = MX + i * 4.23
    card(s, x, 1.75, 3.97, 4.10)
    txt(s, x + 2.75, 2.00, 1.05, 0.75, [(num, 30, NUMBL, True)],
        align=PP_ALIGN.RIGHT, space_after=0)
    pill(s, x + 0.25, 2.92, 3.47, 0.46, t, 12.5)
    txt(s, x + 0.30, 3.62, 3.37, 2.00, [(d, 12, TEXT, False)],
        space_after=6, line_spacing=1.25)
waves(s, 5)

# ===================== P6 国内外研究现状 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "现状", "国内外研究现状", "站在何处 —— 现状与缺口")
card(s, MX, 1.38, 6.05, 3.95)
pill(s, MX + 0.28, 1.62, 1.80, 0.44, "国外现状", 13)
txt(s, MX + 0.32, 2.20, 5.45, 2.95, [
    [("▪ ", 12.5, BLUE, True), ("BIM 生态由 Revit / IFC 等国外平台主导", 12.5, TEXT, False)],
    [("▪ ", 12.5, BLUE, True), ("病害三维定位多依赖摄影测量与点云配准，设备昂贵、流程重，基层管养难落地", 12.5, TEXT, False)],
], space_after=12, line_spacing=1.25, anchor=MSO_ANCHOR.MIDDLE)
x2 = MX + 6.38
card(s, x2, 1.38, 6.05, 3.95)
pill(s, x2 + 0.28, 1.62, 1.80, 0.44, "国内现状", 13)
txt(s, x2 + 0.32, 2.20, 5.45, 2.95, [
    [("▪ ", 12.5, BLUE, True), ("BIMBase 国产三维引擎实现自主化突破，并开放 Python 接口", 12.5, TEXT, False)],
    [("▪ ", 12.5, BLUE, True), ("基于 YOLO 系列的病害识别研究日益成熟", 12.5, TEXT, False)],
    [("▪ ", 12.5, ORANGE, True), ("但“AI 识别 → BIM 构件落位 → 养护闭环”的完整链路仍缺失", 12.5, ORANGE, True)],
], space_after=12, line_spacing=1.25, anchor=MSO_ANCHOR.MIDDLE)
bar(s, MX, 5.62, CW, 0.58, "现有成果多基于国外平台，国产引擎上的桥梁建养一体化应用尚属空白 —— 本项目切入点", 13, "deep")
waves(s, 6)

# ===================== P7 项目总览 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "总览", "项目总览", "建 · 验 · 诊 · 养 全链路闭环架构")
quad = [
    ("建 · 智能建造", ["AI 智能建模", "CAD 画板", "图纸识别", "参数化组件库"]),
    ("验 · 工程验证", ["常泰长江大桥真实工程", "15 个原创 bfa 参数化构件", "233.6 MB P3D 工程"]),
    ("诊 · 智能诊断", ["YOLOv8 + 免模型 CV 双模检测", "Qwen-VL 大模型诊断", "2D→3D 面投影定位"]),
    ("养 · 智慧养护", ["尺寸量化", "Word 巡检报告", "数字孪生", "数据归档"]),
]
cw4, gap4 = 2.80, 0.411
for i, (t, items) in enumerate(quad):
    x = MX + i * (cw4 + gap4)
    card(s, x, 1.55, cw4, 3.30)
    pill(s, x + 0.22, 1.78, cw4 - 0.44, 0.44, t, 12.5)
    txt(s, x + 0.24, 2.42, cw4 - 0.44, 2.30,
        [[("· ", 10.5, BLUE, True), (it, 10.5, TEXT, False)] for it in items],
        space_after=7, line_spacing=1.12)
    if i < 3:
        ar = box(s, x + cw4 + 0.02, 3.05, 0.37, 0.30, shape=MSO_SHAPE.RIGHT_ARROW, fill=BLUE)
loop = box(s, 2.20, 5.10, 8.93, 0.36, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.5,
           fill=RGBColor(0xCF, 0xE6, 0xFA))
shape_text(loop, [("◀ 数据回流 · 闭环迭代 · 模型价值贯穿全生命周期", 10.5, DEEP, True)])
bar(s, MX, 5.78, CW, 0.58, "技术底座：BIMBase 国产三维图形引擎 · pyp3d 参数化接口 · Python 插件体系", 14, "deep")
waves(s, 7)

# ===================== P8 技术底座 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "底座", "技术底座", "国产引擎 × 人工智能 × 工程应用三层技术栈")
layers = [
    ("国产引擎层", ["BIMBase（中国建筑科学研究院 / 构力科技）", "pyp3d 参数化建模接口（拉伸 / 放样 / 布尔 / 阵列）"]),
    ("AI 层", ["YOLOv8 病害检测", "OpenCV 五路图像分析", "Qwen-VL 多模态诊断", "DeepSeek 大模型", "百度语音识别"]),
    ("应用层", ["PyQt5 插件界面", "python-docx 报告生成", "ezdxf / PyMuPDF 图纸解析", "ODA DWG 转换", "three.js 数字孪生"]),
]
for i, (t, items) in enumerate(layers):
    y = 1.42 + i * 1.68
    lab = box(s, MX, y, 2.10, 1.50, shape=MSO_SHAPE.ROUNDED_RECTANGLE, adj=0.10)
    grad(lab, DEEP, BLUE, angle=45)
    shape_text(lab, [(t, 15, WHITE, True)])
    card(s, 2.72, y, 10.16, 1.50)
    cx, cy = 2.98, y + 0.22
    for it in items:
        twi = est_w(it, 11) + 0.50
        if cx + twi > 12.68:
            cx = 2.98
            cy += 0.60
        chip = box(s, cx, cy, twi, 0.46, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
                   fill=CHIPBG, line=BORDER, line_w=0.75, adj=0.5)
        shape_text(chip, [(it, 11, DEEP, False)])
        cx += twi + 0.16
waves(s, 8)

# ===================== P9 研究目标与思路 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "目标", "研究目标与思路", "四大目标 · 一条主线")
goals = [
    ("01", "构建桥梁参数化构件库与 AI 建模能力", "15+ 原创 bfa 构件，自然语言一键生成"),
    ("02", "完成真实工程全桥搭建验证", "常泰长江大桥：主跨 1176m 公铁双层斜拉桥，完整 P3D 工程"),
    ("03", "实现病害智能检测与诊断", "双模检测 + 大模型结构化诊断 + 尺寸量化"),
    ("04", "打通“诊 → 养”闭环", "2D→3D 面投影落位 + Word 报告 + 数字孪生"),
]
for i, (num, t, d) in enumerate(goals):
    r, c = divmod(i, 2)
    x = MX + c * 6.38
    y = 1.34 + r * 1.92
    card(s, x, y, 6.05, 1.76)
    num_badge(s, x + 0.26, y + 0.24, 0.46, num)
    txt(s, x + 0.92, y + 0.18, 4.95, 1.45,
        [(t, 13.5, DEEP, True), (d, 10.5, TEXT, False)], space_after=5, line_spacing=1.12)
txt(s, MX, 5.30, 3.0, 0.32, [("技术路线", 12.5, DEEP, True)], space_after=0)
steps9 = ["需求分析", "构件库建设", "AI 建模研发", "工程验证", "病害识别", "投影落位", "报告闭环"]
for i, t in enumerate(steps9):
    chev(s, MX + i * 1.762, 5.70, 1.86, 0.62, t, 10.5)
waves(s, 9)

# ===================== P10 建·AI 智能建模 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "建模", "智能建造 · 建 —— AI 智能建模", "自然语言一句话 → BIMBase 参数化构件")
txt(s, MX, 1.36, 7.55, 4.60, [
    [("▪ 双路驱动：", 12, DEEP, True),
     ("本地中文解析器优先（897 行：汉字数字连读、全半角归一、单位换算、方向词映射），DeepSeek 大模型兜底（JSON 结构化输出）", 12, TEXT, False)],
    [("▪ 七级兜底自动放置链：", 12, DEEP, True),
     ("破解 pyp3d“实体创建必须在交互回调链中”的限制", 12, TEXT, False)],
    [("　　create_geometry → _PlaceToDirect → place_to → 坐标烘焙 → IFC/OBJ 文件导入 → SendInput 模拟交互 → 手动放置", 10.5, SUB, False)],
    [("▪ 阵列与沿路线布置：", 12, DEEP, True),
     ("线性 / 矩形 / 极坐标阵列；沿直线 / 折线 / 圆弧按弧长插值采样，构件自动沿切向“拐弯”", 12, TEXT, False)],
    [("▪ 语音输入：", 12, DEEP, True), ("百度语音识别", 12, TEXT, False)],
], space_after=14, line_spacing=1.25)
img_ph(s, 8.20, 1.36, 4.68, 4.58, "P10", "右侧",
       "AI 建模面板运行截图",
       "BIMBase 内运行 AI 建模插件，自然语言生成构件后截图")
bar(s, MX, 6.12, CW, 0.54, "示例：“沿路线每隔 50 米放一个门式桥墩” → 自动阵列布置", 13, "blue")
waves(s, 10)

# ===================== P11 建·CAD 画板 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "画板", "智能建造 · 建 —— CAD 画板", "内嵌 BIMBase 的 PyQt 参数化二维画板")
txt(s, MX, 1.36, 7.55, 5.40, [
    [("▪ A3 虚拟画布（420×297mm）：", 12, DEEP, True),
     ("35 个绘图 / 编辑 / 3D 命令，50 步撤销重做，端点 / 交点 / 中心点 / 垂足 / 网格 5 种吸附", 12, TEXT, False)],
    [("▪ 画板 ↔ BIMBase 双向同步：", 12, DEEP, True),
     ("18 个 pyp3d Component 子类 + 多级放置策略链；“从 BIMBase 更新”框选回写（避免 1900+ 实例全场景扫描卡死）", 12, TEXT, False)],
    [("▪ 面编辑创新：", 12, DEEP, True),
     ("面属性 ↔ 参数映射，编辑 diff 反推参数，批量重生成并同步 BIMBase 实体", 12, TEXT, False)],
    [("▪ 图纸互通：", 12, DEEP, True),
     ("DWG / PDF 导入导出（ODA + ezdxf + PyMuPDF）", 12, TEXT, False)],
    [("▪ 一键环境配置：", 12, DEEP, True),
     ("自动检测 BIMBase 路径、配置 VSCode、安装依赖、静默安装 ODA", 12, TEXT, False)],
], space_after=16, line_spacing=1.25)
img_ph(s, 8.20, 1.36, 4.68, 5.30, "P11", "右侧",
       "CAD 画板运行截图",
       "速构智维插件内打开画板，绘制三视图后截图")
waves(s, 11)

# ===================== P12 建·图纸识别 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "识图", "智能建造 · 建 —— 图纸识别", "三视图 PDF / DXF 图纸 → 结构化参数 → 参数化构件自动生成")
txt(s, MX, 1.34, CW, 2.30, [
    [("▪ 双路混合识别：", 12, DEEP, True),
     ("本地规则解析（第一角投影三视图聚类，支持长方体 / 正方体 / 圆柱 / 球体 / 直角三棱柱）+ Qwen-VL 多模态识别（复杂构件参数提取）", 12, TEXT, False)],
    [("▪ 模板匹配生成：", 12, DEEP, True),
     ("component_matcher 匹配构件模板 → 自动生成参数化 .py → 执行建模", 12, TEXT, False)],
    [("▪ 已打通四大构件：", 12, DEEP, True),
     ("门式桥墩 / 引桥桥墩 / 索缆锚锭 / 承台及桩基", 12, ORANGE, True)],
], space_after=9, line_spacing=1.15)
img_ph(s, MX, 3.50, 5.95, 3.16, "P12", "左下",
       "三视图图纸识别输入截图（PDF / DXF）",
       "组件测试目录下 门式桥墩.dxf 等图纸打开截图")
img_ph(s, 6.93, 3.50, 5.95, 3.16, "P12", "右下",
       "图纸 → 模型对照截图（识别生成的构件三维效果）",
       "识别流程运行后，BIMBase 三维视图截图")
ar = box(s, 6.48, 4.92, 0.40, 0.34, shape=MSO_SHAPE.RIGHT_ARROW, fill=BLUE)
waves(s, 12)

# ===================== P13 组件库·常泰 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "构件", "参数化组件库 · 常泰长江大桥", "15 个原创 bfa 参数化构件 · 3 大分类 · 总可调参数约 141 个")
cols13 = [
    ("上部结构（7）", ["主塔（21 参）", "支座（14）", "轨道底座（9）", "斜拉索（8）",
                  "自密实混凝土层及隔离层（7）", "侧面钢桁架（6）", "工字钢梁（4）"]),
    ("下部结构（3）", ["门式桥墩（11）", "承台及桩基（9）", "扩大基础（6）"]),
    ("附属设施（5+1）", ["接触网（16）", "轨道（6）", "路面及交通标线（6）",
                    "新泽西护栏（5）", "防撞护栏（4）", "铁路封闭网（7）"]),
]
for i, (t, items) in enumerate(cols13):
    x = MX + i * 4.23
    card(s, x, 1.34, 3.97, 3.92)
    pill(s, x + 0.25, 1.56, 3.47, 0.44, t, 13)
    txt(s, x + 0.32, 2.18, 3.40, 2.95,
        [[("· ", 11, BLUE, True), (it, 11, TEXT, False)] for it in items],
        space_after=6, line_spacing=1.1)
card(s, MX, 5.46, 7.55, 1.26)
txt(s, 0.75, 5.60, 7.00, 1.00,
    [("技术亮点", 12, DEEP, True),
     ("主塔多段变截面 Loft + 布尔减挖空；斜拉索截面分段自适应（数据量降约 62%）；桁架与接触网 Array 实例化排布", 10.5, TEXT, False)],
    space_after=5, line_spacing=1.12)
img_ph(s, 8.20, 5.46, 4.68, 1.26, "P13", "右下",
       "构件库面板截图或构件拼图",
       "桥梁组件插件面板截图，或 15 个构件缩略图拼图")
waves(s, 13)

# ===================== P14 组件库·组件测试 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "测试", "参数化组件库 · 组件测试", "按真实工程图纸逐构件参数化建模与健壮性检验")
txt(s, MX, 1.36, 7.45, 5.40, [
    [("▪ 4 个基础几何体：", 12, DEEP, True),
     ("正方体 / 长方体 / 圆柱 / 直角三棱柱 —— 验证组件创建与放置流程", 12, TEXT, False)],
    [("▪ 5 个工程构件（按真实图纸）：", 12, DEEP, True)],
    [("　　· 工字钢混凝土组合梁（加劲肋阵列）", 11, TEXT, False)],
    [("　　· 索缆锚锭（异形 Sweep + 7 对 14 根底柱）", 11, TEXT, False)],
    [("　　· 引桥桥墩（斜边盖梁 Sweep，按 6.22-A1.dwg 精确重建）", 11, TEXT, False)],
    [("　　· 门式桥墩（双变截面空心八边形，Loft + 布尔减兜底）", 11, TEXT, False)],
    [("　　· 承台及桩基（锥形桩阵列）", 11, TEXT, False)],
    [("▪ DXF 图纸自动生成：", 12, DEEP, True),
     ("ezdxf 三视图布局，4 图层 + 自动线性标注，构件图纸一键出图", 12, TEXT, False)],
], space_after=11, line_spacing=1.18)
img_ph(s, 8.10, 1.36, 4.78, 2.55, "P14", "右上",
       "构件三维效果截图",
       "BIMBase 中运行组件测试构件（如门式桥墩）后三维视图截图")
img_ph(s, 8.10, 4.10, 4.78, 2.55, "P14", "右下",
       "自动生成的 DXF 三视图图纸截图",
       "运行 组件测试/生成承台及桩基图纸.py 等输出后用 CAD 软件打开截图")
waves(s, 14)

# ===================== P15 验·常泰工程实践 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "验证", "工程验证 · 验 —— 常泰长江大桥", "以 15 个参数化构件在国产 BIMBase 平台搭建完整桥梁")
prac = [
    ("工程背景", "常泰长江大桥 —— 主跨 1176m 双塔斜拉桥，塔高 352m，公铁双层（钢桁梁宽 39m）"),
    ("交付成果", "233.6 MB 完整 P3D 工程文件，场景自洽、可流畅加载、可直接交付"),
    ("工程化能力", "一键 pack_to_bfa 批量打包；组件库性能优化，独立为 v1.3.0 插件（上部 / 下部 / 附属 3 大分类面板）"),
]
for i, (t, d) in enumerate(prac):
    y = 1.40 + i * 1.80
    card(s, MX, y, 6.35, 1.62)
    pill(s, 0.73, y + 0.20, 1.70, 0.40, t, 12)
    txt(s, 0.75, y + 0.72, 5.80, 0.80, [(d, 11.5, TEXT, False)],
        space_after=4, line_spacing=1.15)
img_ph(s, 7.10, 1.40, 5.78, 5.26, "P15", "右侧大图",
       "常泰长江大桥 P3D 全景截图（建议标注：主塔 / 斜拉索 / 双层桥面 / 门式桥墩）",
       "BIMBase 中打开 P3D文件/常泰长江大桥.p3d 截图")
waves(s, 15)

# ===================== P16 诊·病害智能检测 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "检测", "智能诊断 · 诊 —— 病害智能检测", "无人机巡检照片 → 智能检测（6 类病害）")
txt(s, MX, 1.34, CW, 2.90, [
    [("▪ 6+1 类病害：", 12, DEEP, True),
     ("裂缝 / 剥落 / 露筋 / 蜂窝麻面 / 渗水 / 锈蚀（+ 已修复）", 12, TEXT, False)],
    [("▪ 模式一 · YOLOv8n 专用权重：", 12, DEEP, True),
     ("GPU / CPU 均可训练部署，实测 mAP50 ≈ 0.35（如实呈现，持续迭代优化）", 12, TEXT, False)],
    [("▪ 模式二 · 免模型五路 CV 融合（创新）：", 12, ORANGE, True),
     ("黑帽变换 + 多尺度自适应阈值 + K-Means 颜色聚类 + 局部纹理标准差 + Canny 边缘密度，叠加 HSV 天空抑制与 NMS 去重 —— 无训练数据场景零门槛可用", 12, TEXT, False)],
], space_after=9, line_spacing=1.15)
img_ph(s, MX, 3.62, 5.95, 3.04, "P16", "左下",
       "YOLOv8 训练曲线 results.png",
       "桥梁病害识别/training 或 models 目录下训练输出 results.png")
img_ph(s, 6.93, 3.62, 5.95, 3.04, "P16", "右下",
       "验证集检测效果图 val_batch0_pred.jpg",
       "桥梁病害识别/runs/detect/val 目录下验证集预测图")
waves(s, 16)

# ===================== P17 诊·数据集与大模型诊断 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "诊断", "智能诊断 · 诊 —— 数据集与大模型诊断", "公开数据集 + 本地标注 + Qwen-VL 双图结构化诊断")
txt(s, MX, 1.34, CW, 2.70, [
    [("▪ 数据集：", 12, DEEP, True),
     ("GYU-DET 公开集 11,123 张 + CODEBRIM 1,022 张 + 本地巡检报告提取与人工标注（合并训练集约 700 张）", 12, TEXT, False)],
    [("▪ 训练实测：", 12, DEEP, True),
     ("YOLOv8n · CPU 训练 · 两轮迭代（50 → 200 epochs 早停 121），mAP50 由 0.25 提升至 0.35", 12, TEXT, False)],
    [("▪ Qwen-VL 双图诊断：", 12, DEEP, True),
     ("原图 + 带框标注图双输入 → 严格 JSON 输出（病害类型 / 严重程度 / 位置 / 尺寸 / 诊断建议），三级容错解析", 12, TEXT, False)],
], space_after=9, line_spacing=1.15)
ph17 = [
    ("PR 曲线 BoxPR_curve.png", "训练输出目录（runs/detect/val 或 training/runs）下"),
    ("混淆矩阵 confusion_matrix.png", "训练输出目录下归一化混淆矩阵图"),
    ("AI 诊断返回截图", "插件配置 DashScope API Key 后联网运行截图"),
]
for i, (need, how) in enumerate(ph17):
    img_ph(s, MX + i * 4.23, 3.35, 3.97, 3.32, "P17", f"下排{i+1}", need, how)
waves(s, 17)

# ===================== P18 诊·2D→3D 面投影 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "投影", "智能诊断 · 诊 —— 核心创新：2D→3D 解析式面投影", "让病害精准“贴”到 BIM 真实构件")
txt(s, MX, 1.36, 7.55, 5.40, [
    [("▪ 传统路线：", 12, DEEP, True),
     ("摄影测量 / 点云配准 —— 设备昂贵、流程重、基层难落地", 12, TEXT, False)],
    [("▪ 本项目轻量路线（创新）：", 12, ORANGE, True),
     ("检测框 → 构件面中心 + 法向 + U/V 轴解析式等比投影；2mm 法向偏移防闪面；彩色点云 Combine 合成病害标记（按病害类型着色）", 12, TEXT, False)],
    [("▪ 构件智能识别：", 12, DEEP, True),
     ("参数签名匹配覆盖 23 种构件类型；当前已注册柱式桥墩 / 引桥桥墩各 4 个可投影面，注册表机制可扩展", 12, TEXT, False)],
    [("▪ 价值：", 12, DEEP, True),
     ("形成“看得见的病害档案”，为养护决策提供三维可视化依据", 12, TEXT, False)],
], space_after=16, line_spacing=1.25)
img_ph(s, 8.20, 1.36, 4.68, 5.30, "P18", "右侧",
       "病害投影前后对比截图（BIMBase 三维视图）",
       "投影功能运行前后三维视图截图，左右拼版")
waves(s, 18)

# ===================== P19 养·闭环与数字孪生 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "养护", "智慧养护 · 养 —— 全链路闭环与数字孪生", "从无人机巡检到 Word 报告归档，一键贯通")
steps19 = ["无人机巡检", "CV / YOLO 检测", "Qwen-VL 诊断", "尺寸量化", "面投影定位", "Word 报告", "数字孪生"]
for i, t in enumerate(steps19):
    chev(s, MX + i * 1.762, 1.36, 1.86, 0.60, t, 10.5)
keep = [
    ("尺寸量化", "参照物框选标定，病害长 / 宽 / 面积自动换算（误差来源已在报告中说明）"),
    ("Word 报告（python-docx）", "项目概况、构件病害统计表、病害详图（含带框照片）、分档处理建议，可直接归档"),
    ("数字孪生", "一键导出 JSON 数据包 + 离线单文件 HTML（three.js），病害三维分布浏览器直达"),
]
for i, (t, d) in enumerate(keep):
    x = MX + i * 4.23
    card(s, x, 2.26, 3.97, 2.72)
    pill(s, x + 0.25, 2.48, 3.47, 0.44, t, 12.5)
    txt(s, x + 0.30, 3.12, 3.37, 1.75, [(d, 11, TEXT, False)],
        space_after=5, line_spacing=1.15)
img_ph(s, MX, 5.24, 5.95, 1.44, "P19", "左下",
       "Word 巡检报告截图（含统计表与病害详图页）",
       "生成的 docx 报告打开后截图（两页拼版）")
img_ph(s, 6.93, 5.24, 5.95, 1.44, "P19", "右下",
       "数字孪生界面截图（病害三维分布视图）",
       "浏览器打开导出的单文件 HTML 后截图")
waves(s, 19)

# ===================== P20 数据参考源 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "数据", "数据参考源", "数据按需使用，全程服务于建模训练与验证")
rows20 = [
    ("数据类型", "主要内容", "用途"),
    ("真实工程图纸", "承台及桩基 / 门式桥墩 / 索缆锚锭 / 引桥桥墩 DWG", "构件参数化建模依据"),
    ("设计文件与论文", "桥梁设计分册 docx · 参考论文 PDF", "构件尺寸与构造参考"),
    ("曲线数据", "圆柱 / 平面 / 竖直曲线 Excel", "数据驱动建模"),
    ("病害数据集", "GYU-DET · CODEBRIM · 本地标注", "模型训练与验证"),
]
gf = s.shapes.add_table(5, 3, Inches(0.70), Inches(1.55), Inches(11.93), Inches(2.98))
tbl = gf.table
tbl.first_row = False
tbl.horz_banding = False
tbl.columns[0].width = Inches(2.60)
tbl.columns[1].width = Inches(5.63)
tbl.columns[2].width = Inches(3.70)
tbl.rows[0].height = Inches(0.50)
for ri in range(1, 5):
    tbl.rows[ri].height = Inches(0.62)
for ri, row in enumerate(rows20):
    for ci, val in enumerate(row):
        cell = tbl.cell(ri, ci)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = Inches(0.15)
        cell.margin_right = Inches(0.08)
        cell.margin_top = cell.margin_bottom = Inches(0.02)
        cell.fill.solid()
        if ri == 0:
            cell.fill.fore_color.rgb = DEEP
        else:
            cell.fill.fore_color.rgb = WHITE if ri % 2 else CHIPBG
        p = cell.text_frame.paragraphs[0]
        r = p.add_run()
        r.text = val
        if ri == 0:
            _font(r, 13, WHITE, True)
            p.alignment = PP_ALIGN.CENTER
        elif ci == 0:
            _font(r, 12.5, DEEP, True)
        else:
            _font(r, 12, TEXT, False)
bar(s, MX, 5.20, CW, 0.56, "原则：数据按需使用，服务于建模、训练与验证，不作他用", 14, "deep")
waves(s, 20)

# ===================== P21 项目特色 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "特色", "项目特色", "五大特色")
feats = [
    ("国产引擎全栈自主", "BIMBase + Python 插件体系，摆脱国外平台依赖"),
    ("双模检测互为补充", "YOLO 专用权重 + 免模型 CV 融合，有 / 无训练数据皆可用"),
    ("大模型与确定性规则协同", "本地解析器优先、大模型兜底；关键计算不交模型自由发挥"),
    ("轻量级 2D→3D 投影", "解析式面投影替代摄影测量，普通无人机 + 笔记本即可落地"),
    ("建-验-诊-养全生命周期", "建造模型即养护数据载体，模型价值贯穿桥梁全生命周期"),
]
for i, (t, d) in enumerate(feats):
    if i < 3:
        x = MX + i * 4.23
        y = 1.42
    else:
        x = 2.555 + (i - 3) * 4.23
        y = 4.06
    card(s, x, y, 3.97, 2.42)
    txt(s, x + 2.85, y + 0.14, 0.95, 0.62, [(f"0{i+1}", 26, NUMBL, True)],
        align=PP_ALIGN.RIGHT, space_after=0)
    pill(s, x + 0.25, y + 0.22, min(3.47, est_w(t, 12) + 0.5), 0.42, t, 12)
    txt(s, x + 0.30, y + 0.88, 3.37, 1.42, [(d, 11, TEXT, False)],
        space_after=5, line_spacing=1.18)
waves(s, 21)

# ===================== P22 创新点总结 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "创新", "创新点总结", "六项核心创新")
innov = [
    ("平台空档", "首个基于国产 BIMBase 的桥梁病害识别 — BIM 投影闭环（现有成果多基于 Revit / IFC）"),
    ("免模型检测", "五路 CV 掩码融合，零训练数据门槛"),
    ("多模态诊断", "Qwen-VL 双图输入，六字段结构化输出"),
    ("轻量投影", "解析式面投影 + 点云标记，2mm 防闪面"),
    ("自然语言建模", "897 行本地中文解析器 + 七级兜底放置链"),
    ("工程实证", "15 个原创 bfa 构件 + 主跨 1176m 常泰长江大桥整桥 P3D 验证"),
]
for i, (t, d) in enumerate(innov):
    r, c = divmod(i, 3)
    x = MX + c * 4.23
    y = 1.38 + r * 2.62
    card(s, x, y, 3.97, 2.45)
    num_badge(s, x + 0.25, y + 0.20, 0.50, f"0{i+1}")
    txt(s, x + 0.90, y + 0.24, 2.90, 0.42, [(t, 13, DEEP, True)],
        anchor=MSO_ANCHOR.MIDDLE, space_after=0)
    txt(s, x + 0.30, y + 0.86, 3.40, 1.45, [(d, 11, TEXT, False)],
        space_after=5, line_spacing=1.15)
waves(s, 22)

# ===================== P23 产业价值与推广 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "价值", "产业价值与推广", "战略契合 · 生态协同 · 落地路径清晰")
vals23 = [
    ("战略契合", "交通强国、基础设施智慧运维、国产软件自主可控"),
    ("生态协同", "与 PKPM / BIMBase 系列软件深度结合，共建国产 BIM 插件生态"),
    ("落地门槛低", "普通无人机 + 笔记本即可部署，适合基层管养单位"),
    ("可持续演进", "病害样本持续积累 → 模型迭代 → 构件库扩展，形成数据飞轮"),
]
for i, (t, d) in enumerate(vals23):
    r, c = divmod(i, 2)
    x = MX + c * 6.38
    y = 1.34 + r * 1.66
    card(s, x, y, 6.05, 1.50)
    pill(s, x + 0.26, y + 0.19, 1.90, 0.40, t, 12)
    txt(s, x + 0.30, y + 0.72, 5.50, 0.65, [(d, 11.5, TEXT, False)],
        space_after=4, line_spacing=1.12)
txt(s, MX, 4.80, 3.0, 0.32, [("推广路径", 12.5, DEEP, True)], space_after=0)
path23 = ["设计院（AI 智能建模）", "施工单位（图纸识别）", "管养单位（巡检闭环）"]
for i, t in enumerate(path23):
    chev(s, MX + i * 4.00, 5.20, 4.15, 0.72, t, 12.5)
waves(s, 23)

# ===================== P24 团队介绍 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
header(s, "团队", "团队介绍", "分工明确 · 产教协同")
members = [
    ("成员 A（队长）", ["统筹规划", "项目管理", "文档撰写"], "【姓名 / 专业待填写】"),
    ("成员 B", ["BIMBase 插件开发", "参数化构件库建设"], "【姓名 / 专业待填写】"),
    ("成员 C", ["病害识别算法", "数据集建设", "模型训练"], "【姓名 / 专业待填写】"),
    ("成员 D", ["工程验证", "测试", "答辩素材"], "【姓名 / 专业待填写】"),
]
for i, (t, roles, todo) in enumerate(members):
    x = MX + i * 3.15
    card(s, x, 1.38, 2.98, 3.30)
    pill(s, x + 0.20, 1.58, min(2.58, est_w(t, 12) + 0.5), 0.40, t, 12)
    pho = box(s, x + 0.20, 2.18, 0.85, 2.28, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
              fill=PH_BG, line=PH_LN, line_w=0.75, adj=0.08, dash=True)
    shape_text(pho, [("照片", 9, PH_TX, False)])
    PHOTOS.append(("P24", f"成员{chr(65+i)}卡片左侧", f"{t} 证件照/生活照 1 张"))
    txt(s, x + 1.16, 2.24, 1.72, 1.70,
        [(r_, 10.5, TEXT, False) for r_ in roles], space_after=5, line_spacing=1.1)
    txt(s, x + 1.16, 4.02, 1.74, 0.60, [(todo, 8.5, SUB, False)],
        space_after=0, line_spacing=1.05)
# 指导教师
card(s, MX, 4.98, CW, 1.38)
pho = box(s, 0.75, 5.17, 0.95, 1.00, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
          fill=PH_BG, line=PH_LN, line_w=0.75, adj=0.08, dash=True)
shape_text(pho, [("照片", 9, PH_TX, False)])
PHOTOS.append(("P24", "指导教师卡片左侧", "指导教师证件照 1 张"))
pill(s, 1.95, 5.22, 1.60, 0.42, "指导教师", 12.5)
txt(s, 3.75, 5.22, 8.9, 1.00,
    [("【姓名 / 职称 / 研究方向待填写】", 12.5, TEXT, True),
     ("产教协同 · 联合指导 · 全程把关", 10, SUB, False)],
    anchor=MSO_ANCHOR.MIDDLE, space_after=6)
waves(s, 24)

# ===================== P25 封底 =====================
s = prs.slides.add_slide(BLANK)
bg(s)
txt(s, 1.0, 2.00, 11.33, 0.85,
    [("让每一座桥梁，建得更快、养得更智", 36, DEEP, True)],
    align=PP_ALIGN.CENTER, space_after=0)
txt(s, 1.0, 3.10, 11.33, 0.50,
    [("以国产引擎筑基，以人工智能赋能 —— 桥元智构，服务桥梁全生命周期", 16, BLUE, False)],
    align=PP_ALIGN.CENTER, space_after=0)
txt(s, 1.0, 4.20, 11.33, 0.45,
    [("感谢发榜单位中国建筑科学研究院有限公司与各位评审专家", 14, TEXT, False)],
    align=PP_ALIGN.CENTER, space_after=0)
txt(s, 1.0, 5.05, 11.33, 0.40,
    [("团队联系方式：____________（待填写）", 12, SUB, False)],
    align=PP_ALIGN.CENTER, space_after=0)
waves(s, 25)

# ===================== 保存 + 配图线索清单 =====================
prs.save(OUT)
print("OK ->", OUT)
print("slides:", len(prs.slides._sldIdLst))

md = []
md.append("# 《挑战杯产业赛道_桥元智构_v2》配图线索清单")
md.append("")
md.append("配套 PPT：`docs/挑战杯项目官方文件及参考/挑战杯产业赛道_桥元智构_v2.pptx`（25 页，16:9）")
md.append("生成脚本：`archive/misc/generate_tiaozhanbei_ppt_v2.py`")
md.append("说明：PPT 中所有灰色虚线圆角矩形为配图占位框，框内文字已注明所需图片与获取方式；替换时删除占位框、按框尺寸等比插入图片即可。P1/P24/P25 中的“待填写”信息见文末清单。")
md.append("")
md.append(f"## 一、配图占位清单（{len(IMG_SPOTS)} 处）")
md.append("")
md.append("| 序号 | 页码 | 占位框位置 | 需要的图 | 获取方式 |")
md.append("|---|---|---|---|---|")
for i, (pg, pos, need, how) in enumerate(IMG_SPOTS, 1):
    md.append(f"| {i} | {pg} | {pos} | {need} | {how} |")
md.append("")
md.append(f"## 二、照片占位清单（{len(PHOTOS)} 处）")
md.append("")
md.append("| 序号 | 页码 | 位置 | 需要的内容 |")
md.append("|---|---|---|---|")
for i, (pg, pos, desc) in enumerate(PHOTOS, 1):
    md.append(f"| {i} | {pg} | {pos} | {desc} |")
md.append("")
md.append("## 三、人员与联系信息待填写清单")
md.append("")
md.append("| 序号 | 位置 | 占位内容 | 获取方式 |")
md.append("|---|---|---|---|")
md.append("| 1 | P1 封面底部 | 参赛学校、团队名称、指导教师 | 报名确认后填写 |")
md.append("| 2 | P24 成员 A~D 卡片 | 成员姓名 / 专业（4 人） | 团队确认分工后填写 |")
md.append("| 3 | P24 指导教师卡片 | 教师姓名 / 职称 / 研究方向 | 确认后填写 |")
md.append("| 4 | P25 封底 | 团队联系方式 | 确认后填写 |")
md.append("| 5 | P3 卡片① | 桥梁保有量等行业数据的权威来源标注 | 引用交通部统计公报等权威来源后补注 |")
md.append("")
with open(MD_OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(md))
print("MD ->", MD_OUT)
