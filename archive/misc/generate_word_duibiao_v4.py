# -*- coding: utf-8 -*-
"""
生成《智检桥安-命题解决方案（对标版）v4.docx》—— 对标沈阳建筑大学模板格式。

项目：智检桥安——基于人工智能与计算机视觉的桥梁表观损伤智能检测系统
命题：基于人工智能与计算机视觉的桥梁表观损伤智能检测系统开发（命题企业：广联达）
输出：docs/国创赛ppt/智检桥安-命题解决方案（对标版）v4.docx

v4 在 v3 基础上新增整页背景装饰：
  向页眉注入 wp:anchor（behindDoc="1"）浮动图片 XML，将 页面背景_A4.png 以页面 (0,0) 对齐、
  A4 整页 extent 衬于文字下方；利用"首页不同"使封面无背景；背景图仅嵌入一次；
  原灰色页眉文字移除（背景图自带顶部赛名与蓝线），页脚页码保留不动。

v3 在 v2 基础上做"真实性审查 + 适度口语化"修订：
  事实修订：5.4 节按 dimension_utils.py 真实实现重写（参照物框选标定＋检测框换算，
    删除不存在的掩膜细化/骨架提取/法向扫描表述，改列为规划提升方向）；图 5-2 换用
    思维导图_尺寸计算流程_v2.png；全文统一"参照物框选标定（量化）/面投影（定位）"术语
    （3.2、4.5、表 7-1 同步修正）；5.1 增加 nc=7（含"已修复"标签）口径说明；
    第一章增加"病害/损伤同义"注释。
  口语化：项目摘要、第二/四/五章引言段、第二章场景、9.4 成长段、9.6 价值引领，
    改写更直白，不超过原字数 1.2 倍；技术章节主体、表格、附录保持严谨不动。

格式（对标模板）：
  A4；正文仿宋四号（14pt）、西文 Times New Roman、1.5 倍行距、首行缩进 2 字符；
  章标题黑体三号（16pt）加粗、节标题黑体四号（14pt）、小节黑体小四（12pt）加粗；
  目录宋体小四；图题在图下方、表题在表上方，小五（9pt）宋体居中；
  图表编号"图 X-Y / 表 X-Y"全文连续无重复；页脚居中页码，封面无页眉页脚。

诚实性约束：mAP50≈0.336、mAP50-95≈0.085 如实；量化/定位/耗时均为"预期"口径并注明
  测试完成后以实测回填；团队成员、指导教师、企业证明一律"待填写/待补充"；
  不编造企业合作事实与市场规模金额。

素材：
  现稿 docs/国创赛ppt/智检桥安-命题解决方案（参考）.docx（运行时提取 5 张真实截图复用）
  配图 docs/国创赛ppt/*.png（10 张预生成图）
  平台截图 桥梁病害识别/数字孪生/Picture/平台总览.png
  代码节选 桥梁病害识别/face_projection.py、dimension_utils.py、cv_anomaly_detector.py
"""
import os
import zipfile

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Emu, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PPT_DIR = os.path.join(ROOT, "docs", "国创赛ppt")
OUT_PATH = os.path.join(PPT_DIR, "智检桥安-命题解决方案（对标版）v4.docx")
REF_DOCX = os.path.join(PPT_DIR, "智检桥安-命题解决方案（参考）.docx")
REF_MEDIA_DIR = os.path.join(ROOT, "archive", "misc", "_ref_media")
TWIN_IMG = os.path.join(ROOT, "桥梁病害识别", "数字孪生", "Picture", "平台总览.png")
BG_IMG = os.path.join(PPT_DIR, "页面背景_A4.png")
COVER_BG_IMG = os.path.join(PPT_DIR, "页面背景_封面.png")

BODY_EAST = "仿宋"
BODY_ASCII = "Times New Roman"
HEAD_EAST = "黑体"
HEADER_FILL = "D9E2F3"
CLUE_GRAY = (0x80, 0x80, 0x80)
CODE_FILL = "F2F2F2"

# 现稿中复用的真实截图
REF_IMAGES = {
    "bridge_photo": "image1.jpeg",   # 常泰长江大桥实景航拍
    "plugin_ui": "image4.png",       # 病害识别插件主界面
    "bim_model": "image5.png",       # 常泰桥 BIM 模型正立面
    "twin_view": "image8.png",       # 数字孪生平台三维视角
    "projection": "image14.png",     # BIMBase 内病害面投影运行效果
}


def ppt_img(name):
    return os.path.join(PPT_DIR, name)


def ref_img(key):
    return os.path.join(REF_MEDIA_DIR, REF_IMAGES[key])


def extract_ref_media():
    """从现稿 docx 中提取需复用的真实截图。"""
    os.makedirs(REF_MEDIA_DIR, exist_ok=True)
    z = zipfile.ZipFile(REF_DOCX)
    for name in REF_IMAGES.values():
        data = z.read("word/media/" + name)
        with open(os.path.join(REF_MEDIA_DIR, name), "wb") as f:
            f.write(data)


# ---------------------------------------------------------------------------
# 基础工具函数
# ---------------------------------------------------------------------------

def set_font(run, east=BODY_EAST, ascii_f=BODY_ASCII, size=14, bold=False, color=None):
    run.font.name = ascii_f
    run.font.size = Pt(size)
    run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), east)
    if color is not None:
        run.font.color.rgb = RGBColor(*color)


def set_first_line_indent_chars(paragraph, chars=2, char_size_pt=14):
    pPr = paragraph._p.get_or_add_pPr()
    ind = pPr.find(qn("w:ind"))
    if ind is None:
        ind = OxmlElement("w:ind")
        pPr.append(ind)
    ind.set(qn("w:firstLineChars"), str(chars * 100))
    ind.set(qn("w:firstLine"), str(int(chars * char_size_pt * 20)))


def set_outline_level(paragraph, level):
    pPr = paragraph._p.get_or_add_pPr()
    ol = OxmlElement("w:outlineLvl")
    ol.set(qn("w:val"), str(level))
    pPr.append(ol)


def add_body(doc, text, indent=True, size=14, bold=False, east=BODY_EAST,
             align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=4, line_spacing=1.5,
             color=None):
    """正文段落：仿宋四号、1.5 倍行距、默认首行缩进两字符。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.line_spacing = line_spacing
    pf.space_after = Pt(space_after)
    pf.alignment = align
    run = p.add_run(text)
    set_font(run, east=east, size=size, bold=bold, color=color)
    if indent:
        set_first_line_indent_chars(p, 2, size)
    return p


def add_h1(doc, text, page_break=True):
    """章标题：黑体三号（16pt）加粗，另起一页。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(6)
    pf.space_after = Pt(14)
    pf.line_spacing = 1.5
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_outline_level(p, 0)
    if page_break:
        p.add_run().add_break(WD_BREAK.PAGE)
    run = p.add_run(text)
    set_font(run, east=HEAD_EAST, ascii_f=HEAD_EAST, size=16, bold=True)
    return p


def add_h2(doc, text):
    """节标题：黑体四号（14pt）。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(10)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.5
    set_outline_level(p, 1)
    run = p.add_run(text)
    set_font(run, east=HEAD_EAST, ascii_f=HEAD_EAST, size=14, bold=True)
    return p


def add_h3(doc, text):
    """小节标题：黑体小四（12pt）加粗。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(6)
    pf.space_after = Pt(4)
    pf.line_spacing = 1.5
    set_outline_level(p, 2)
    run = p.add_run(text)
    set_font(run, east=HEAD_EAST, ascii_f=HEAD_EAST, size=12, bold=True)
    return p


def add_fig(doc, img_path, caption, width_cm=14.0):
    """插图：图片居中，图题在图下方，小五宋体居中。"""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.space_before = Pt(6)
    pf.space_after = Pt(2)
    p.add_run().add_picture(img_path, width=Cm(width_cm))
    cap = doc.add_paragraph()
    cpf = cap.paragraph_format
    cpf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cpf.space_after = Pt(10)
    cpf.line_spacing = 1.0
    run = cap.add_run(caption)
    set_font(run, east="宋体", size=9)
    return p


def set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def set_cell_text(cell, text, bold=False, size=10.5, center=True):
    cell.text = ""
    p = cell.paragraphs[0]
    pf = p.paragraph_format
    pf.line_spacing = 1.0
    pf.space_after = Pt(2)
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    set_font(run, east="宋体", size=size, bold=bold)


def add_tbl(doc, caption, headers, rows):
    """表格：表题在表上方，小五宋体居中；表头加粗带底色。"""
    cap = doc.add_paragraph()
    cpf = cap.paragraph_format
    cpf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cpf.space_before = Pt(6)
    cpf.space_after = Pt(2)
    cpf.line_spacing = 1.0
    run = cap.add_run(caption)
    set_font(run, east="宋体", size=9)
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    for i, h in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], h, bold=True)
        set_cell_shading(table.rows[0].cells[i], HEADER_FILL)
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            set_cell_text(cells[i], val, center=(len(str(val)) <= 16))
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(6)
    return table


def add_clue(doc, text):
    """截图线索占位：灰字小四居中。"""
    return add_body(doc, text, indent=False, size=12,
                    align=WD_ALIGN_PARAGRAPH.CENTER, color=CLUE_GRAY, space_after=8)


def add_note(doc, text):
    """注释：宋体小五，首行缩进两字符。"""
    return add_body(doc, text, size=10.5, east="宋体", space_after=4)


def add_code_block(doc, title, code):
    """代码块：标题小五黑体；正文 Consolas 9pt、灰底、单倍行距。"""
    tp = doc.add_paragraph()
    tp.paragraph_format.space_before = Pt(6)
    tp.paragraph_format.space_after = Pt(2)
    run = tp.add_run(title)
    set_font(run, east=HEAD_EAST, ascii_f=HEAD_EAST, size=10.5, bold=True)
    for line in code.rstrip("\n").split("\n"):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing = 1.0
        pf.space_after = Pt(0)
        pPr = p._p.get_or_add_pPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), CODE_FILL)
        pPr.append(shd)
        r = p.add_run(line if line.strip() else " ")
        set_font(r, east="Consolas", ascii_f="Consolas", size=9)
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(6)


def add_centered(doc, text, size=14, bold=False, east=BODY_EAST, space_after=6, space_before=0):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf.line_spacing = 1.5
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    run = p.add_run(text)
    set_font(run, east=east, ascii_f=BODY_ASCII if east == BODY_EAST else east,
             size=size, bold=bold)
    return p


def setup_page(doc):
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.6)
    section.different_first_page_header_footer = True

    style = doc.styles["Normal"]
    style.font.name = BODY_ASCII
    style.font.size = Pt(14)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), BODY_EAST)

    # v4：页眉不再放灰色文字行——整页背景图自带顶部赛名与蓝线装饰，
    # 背景图由 add_page_background() 注入默认页眉（首页页眉留空，封面无背景）。

    footer_p = section.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_p.add_run()
    set_font(run, size=9)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def _inject_bg_into_header(header, img_path, width_emu, height_emu, docpr_id):
    """向指定页眉注入整页背景图（wp:anchor, behindDoc="1"）。

    python-docx 不直接支持"衬于文字下方"的浮动图片，做法：先在页眉段落中
    add_picture 生成 wp:inline（图片 part 与 r:embed 关系随之建立，仅嵌入一次），
    再将 inline 的 graphic 子元素迁入手工构造的 wp:anchor（页面 (0,0) 对齐、
    A4 整页 extent、wrapNone、behindDoc）。
    """
    header.is_linked_to_previous = False
    p = header.paragraphs[0]
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.0
    run = p.add_run()
    run.add_picture(img_path, width=Emu(width_emu), height=Emu(height_emu))

    drawing = run._r.find(qn("w:drawing"))
    inline = drawing.find(qn("wp:inline"))
    graphic = inline.find(qn("a:graphic"))

    anchor_xml = (
        '<wp:anchor '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'behindDoc="1" layoutInCell="1" locked="0" allowOverlap="1" relativeHeight="0" '
        'simplePos="0" distT="0" distB="0" distL="0" distR="0">'
        '<wp:simplePos x="0" y="0"/>'
        '<wp:positionH relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionH>'
        '<wp:positionV relativeFrom="page"><wp:posOffset>0</wp:posOffset></wp:positionV>'
        '<wp:extent cx="%d" cy="%d"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        '<wp:wrapNone/>'
        '<wp:docPr id="%d" name="PageBackground" descr="page background"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/>'
        '</wp:cNvGraphicFramePr>'
        '</wp:anchor>' % (width_emu, height_emu, docpr_id)
    )
    anchor = parse_xml(anchor_xml)
    anchor.append(graphic)
    drawing.replace(inline, anchor)


def add_page_background(doc, img_path, cover_img_path=None):
    """给全部页面加整页背景：默认页眉用 img_path（正文页），
    首页页眉用 cover_img_path（封面，"首页不同"已开启）。每张图各嵌入一次。"""
    for section in doc.sections:
        width_emu = int(section.page_width)
        height_emu = int(section.page_height)
        _inject_bg_into_header(section.header, img_path, width_emu, height_emu, 9901)
        if cover_img_path is not None:
            _inject_bg_into_header(section.first_page_header, cover_img_path,
                                   width_emu, height_emu, 9902)


# ---------------------------------------------------------------------------
# 封面、摘要、目录
# ---------------------------------------------------------------------------

def build_cover(doc):
    for _ in range(2):
        add_centered(doc, "", size=14)
    add_centered(doc, "中国国际大学生创新大赛（2026）", size=16, bold=True, east=HEAD_EAST)
    add_centered(doc, "产业赛道 · 企业命题组", size=14, bold=True, east=HEAD_EAST)
    add_centered(doc, "", size=12)
    add_centered(doc, "智检桥安", size=36, bold=True, east=HEAD_EAST, space_after=10)
    add_centered(doc, "——基于人工智能与计算机视觉的桥梁表观损伤智能检测系统",
                 size=15, bold=True, east=HEAD_EAST)
    add_centered(doc, "", size=12)
    add_centered(doc, "作品方案说明书 · 命题对策", size=22, bold=True, east=HEAD_EAST, space_before=6)
    add_centered(doc, "", size=12)
    add_centered(doc, "应答命题：基于人工智能与计算机视觉的桥梁表观损伤智能检测系统开发", size=13)
    add_centered(doc, "（命题企业：广联达）", size=12)
    add_centered(doc, "", size=12)

    info = doc.add_table(rows=4, cols=2)
    info.style = "Table Grid"
    info.alignment = WD_TABLE_ALIGNMENT.CENTER
    rows_data = [("参赛学校", "待填写"), ("团队名称", "待填写"),
                 ("指导教师", "待填写"), ("完成日期", "2026年9月")]
    for i, (k, v) in enumerate(rows_data):
        set_cell_text(info.rows[i].cells[0], k, bold=True, size=12)
        set_cell_text(info.rows[i].cells[1], v, size=12)
    for row in info.rows:
        row.cells[0].width = Cm(5.0)
        row.cells[1].width = Cm(8.0)

    add_centered(doc, "", size=14)
    add_centered(doc, "2026 年 9 月", size=14, space_before=6)


def build_abstract(doc):
    add_h1(doc, "项目摘要")
    add_body(doc, "截至2025年底，全国公路桥梁已超过100万座，并且大批桥梁陆续进入运维期——桥会“生病”，"
                  "而查病的工作正变得越来越繁重。传统的检测靠人：爬上去拍、凭经验看、拿尺子量、拿笔记录位置、"
                  "回办公室编报告，五个环节分给不同的人做，数据来回誊录，既慢又容易出错，查完的数据也很难直接"
                  "服务养护决策。")
    add_body(doc, "针对命题企业“基于人工智能与计算机视觉的桥梁表观损伤智能检测系统开发”的真实业务需求，"
                  "我们做了“智检桥安”这套系统：以国产BIMBase三维图形引擎为底座，把“图像采集→损伤智能识别与"
                  "分类→损伤几何尺寸量化→三维空间定位→检测报告自动生成”五个环节串成一条数字化流水线。识别上"
                  "采用YOLOv8n专用模型加免模型五路CV融合的双模式，基线模型在普通CPU电脑上完成训练，mAP50约"
                  "0.336、mAP50-95约0.085——指标还不算高，我们如实写出，并给出明确的提升路线；诊断上集成"
                  "Qwen-VL多模态大模型分析病害成因；定位上用解析式2D→3D面投影把病害精确挂到BIM构件表面；"
                  "最后用python-docx一键生成规范的Word检测报告。")
    add_body(doc, "目前系统已经形成两件拿得出手的成果：一件是BIMBase桌面检测插件，在常泰长江大桥真实工程"
                  "BIM模型（244.9MB，16类参数化构件）上全流程跑通；另一件是数字孪生网页平台——一个662KB的"
                  "单文件离线网页，用three.js按真实尺度重建了整座大桥，能显隐构件、导入病害JSON、在三维模型上"
                  "贴片查看病害，用浏览器打开就能用，也可以部署到公网。")
    add_body(doc, "这套系统走的是低成本、轻量化、可复核的路线：普通无人机加一台笔记本电脑就能干活，基层"
                  "检测和管养单位用得起、用得上。我们希望它能帮桥梁检测行业把内业工作从纸面搬到模型上，也期待"
                  "把这套方法推广到隧道、房屋等更多基础设施的检测中去。")
    add_fig(doc, TWIN_IMG, "图 0-1  数字孪生平台全桥总览", width_cm=15.0)


TOC_ENTRIES = [
    "项目摘要",
    "命题响应对照与提交物清单",
    "一、项目概述与设计目标",
    "二、应用场景",
    "三、系统结构设计",
    "四、操作说明",
    "五、核心技术及原理",
    "六、项目实现与案例验证",
    "七、运行环境",
    "八、市场与竞争性分析",
    "九、产教协同与团队协作",
    "十、风险分析",
    "附录一  知识产权与成果证明",
    "附录二  常泰长江大桥参数化构件清单",
    "附录三  核心代码节选",
    "附录四  成果应用边界与数据合规声明",
    "附录五  需求调研一手资料包",
]


def build_toc(doc):
    doc.add_page_break()
    add_centered(doc, "目  录", size=16, bold=True, east=HEAD_EAST, space_after=18)
    for entry in TOC_ENTRIES:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.line_spacing = 1.5
        pf.space_after = Pt(8)
        pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
        set_first_line_indent_chars(p, 2, 12)
        run = p.add_run(entry)
        set_font(run, east="宋体", size=12)


# ---------------------------------------------------------------------------
# 命题响应对照与提交物清单（A：目录后、不编号小节）
# ---------------------------------------------------------------------------

def build_response_map(doc):
    add_h1(doc, "命题响应对照与提交物清单")
    add_body(doc, "本对策书严格对照命题“基于人工智能与计算机视觉的桥梁表观损伤智能检测系统开发”的答题要求"
                  "（共 12 条）与成果提交要求（共 9 项）组织内容。答题要求响应对照如表 0-1 所示，成果提交物"
                  "清单如表 0-2 所示。")
    add_tbl(doc, "表 0-1  命题答题要求响应对照表",
            ["序号", "命题答题要求", "本对策书响应对照", "响应情况"],
            [["1", "明确企业需求与应用场景", "第一章 1.2、第二章", "已响应"],
             ["2", "选取典型桥型与损伤类型", "第五章 5.1、第六章 6.3（常泰长江大桥·6 类损伤）", "已响应"],
             ["3", "建立清晰的数字化业务流程", "第三章 3.2、图 3-2", "已响应"],
             ["4", "损伤智能识别与分类", "第五章 5.1、5.2", "已响应"],
             ["5", "损伤几何尺寸量化", "第五章 5.4、表 5-2", "已响应"],
             ["6", "损伤空间定位", "第五章 5.5、表 5-3、表 5-4", "已响应"],
             ["7", "数字化成果", "第三章 3.3、第四章、第五章 5.6", "已响应"],
             ["8", "案例验证和效果评价", "第六章 6.3、6.4", "已响应"],
             ["9", "产教协同创新", "第九章", "已响应"],
             ["10", "创新性与推广价值", "第一章 1.6、第八章 8.4", "已响应"],
             ["11", "成果提交要求", "本节表 0-2", "已响应"],
             ["12", "成果应用边界", "附录四", "已响应"]])
    add_tbl(doc, "表 0-2  成果提交物清单表",
            ["序号", "提交物要求", "本项目对应成果", "所在章节", "状态"],
            [["1", "命题对策书/项目技术报告", "本文档", "全文", "已具备"],
             ["2", "企业需求分析和总体解决方案", "需求理解、设计目标与系统结构设计", "第一、三章", "已具备"],
             ["3", "业务流程图或技术路线图", "五环业务流程、四层技术架构", "图 3-1、图 3-2", "已具备"],
             ["4", "可演示的数字化成果或交互原型",
              "BIMBase 桌面检测插件、数字孪生平台 HTML 网页（常泰长江大桥数字孪生.html）",
              "第三、四、五章", "已具备"],
             ["5", "所选桥型与损伤类型的案例说明", "常泰长江大桥（斜拉桥）、6 类表观损伤",
              "第六章 6.3", "已具备"],
             ["6", "损伤识别、量化与定位的分析结果", "识别指标、量化与定位方法及预期指标",
              "第五章", "已具备（实测数据待回填）"],
             ["7", "案例验证与应用效果说明", "常泰长江大桥案例验证与效果评价",
              "第六章 6.4", "已具备（实测数据待回填）"],
             ["8", "团队成员分工及校企协同过程说明", "团队分工、实质性贡献说明与协同机制",
              "第九章", "部分待补充（成员姓名待填写）"],
             ["9", "数据来源、知识产权及授权情况说明", "数据来源说明与合规声明", "附录四", "已具备"]])


# ---------------------------------------------------------------------------
# 一、项目概述与设计目标
# ---------------------------------------------------------------------------

def build_ch1(doc):
    add_h1(doc, "一、项目概述与设计目标")

    add_h2(doc, "1.1  项目背景")
    add_body(doc, "桥梁是公路交通网络的关键节点，其技术状况直接关系到人民群众出行安全与国民经济运行效率。"
                  "截至2025年底，全国公路桥梁已超过100万座，大量桥梁陆续进入运维期，定期检测、经常性检查与"
                  "养护维修任务日益繁重，桥梁检测养护市场持续增长。本项目的验证对象常泰长江大桥实景如图 1-1 "
                  "所示，该桥为双层公铁两用斜拉桥，是长江干线通道上的标志性重大工程。")
    add_fig(doc, ref_img("bridge_photo"), "图 1-1  常泰长江大桥实景", width_cm=14.0)
    add_body(doc, "从行业作业方式看，表观损伤检测长期以人工抵近观测为主：（1）登高与桥检车抵近作业风险高、"
                  "效率低；（2）损伤判读依赖个人经验，主观性强、标准不一；（3）检测结果以纸质或零散电子文档"
                  "沉淀，难以形成可追溯、可对比的数字化资产。交通强国建设纲要明确提出推进基础设施数字化、"
                  "养护管理智能化，行业对“采得回、看得懂、算得准、定位得到”的智能检测手段需求日益迫切。")
    add_note(doc, "注：本说明书中“病害”与“损伤”同义，均指桥梁结构的表观病害（如裂缝、剥落、露筋等），"
                  "全文混用、不再区分。")
    add_body(doc, "从自主可控看，三维图形引擎与BIM核心软件长期由国外产品主导，工程数据安全与供应链安全存在"
                  "隐忧。本项目全程基于国产BIMBase三维图形引擎与国产开源生态构建，以青年学子的工程实践回应"
                  "“关键核心技术自主可控”的时代命题；同时以“企业出题、高校指导、学生攻关”的产教融合模式组织"
                  "实施，让团队成员在服务国家基础设施运维的真实场景中锤炼本领、增长才干。")

    add_h2(doc, "1.2  企业需求理解与命题解析")
    add_body(doc, "命题企业（广联达）发布的命题为“基于人工智能与计算机视觉的桥梁表观损伤智能检测系统开发”。"
                  "本团队深入梳理了桥梁检测业务全流程，图像采集、人工判读、尺寸测量、空间定位与报告编制五个"
                  "环节相互割裂，痛点与对策的对应关系如图 1-2 所示，具体痛点如下：")
    add_body(doc, "（1）图像采集环节：无人机、桥检车抵近采集的照片数量大、角度杂，照片与构件的对应关系依赖"
                  "人工记录，整理归档工作量大；")
    add_body(doc, "（2）人工判读环节：损伤类型与损伤程度的判读依赖检测人员个人经验，主观性强、标准不一，"
                  "登高与桥检车抵近作业风险高、效率低；")
    add_body(doc, "（3）尺寸测量环节：裂缝长度、宽度等几何尺寸需现场人工量测，高空作业危险，测量效率低，"
                  "数据离散度大；")
    add_body(doc, "（4）空间定位环节：病害位置多以“第几跨、第几号墩”等文字方式描述，难以在三维空间中准确"
                  "归档与直观展示，复查时难以快速回溯；")
    add_body(doc, "（5）报告编制环节：采集、判读、测量、定位、报告由不同人员分步完成，数据在多个环节间反复"
                  "誊录，易出错、周期长；检测数据与养护决策、加固设计之间缺乏有效衔接，形成数据断链。")
    add_body(doc, "综上，企业的核心诉求是打通“图像采集→损伤识别→量化分析→空间定位→报告输出”的数字化闭环，"
                  "以数字化手段实现检测全流程的提质增效，如图 1-2 所示。")
    add_fig(doc, ppt_img("思维导图_检测业务流程痛点.png"), "图 1-2  检测业务流程痛点与本方案对策",
            width_cm=15.0)

    add_h2(doc, "1.3  系统设计目标")
    add_body(doc, "针对命题五环节，本系统设定可考核的设计目标，如表 1-1 所示。各项目标的实现路径与验证方式"
                  "在第三章至第六章展开。")
    add_tbl(doc, "表 1-1  命题五环节与系统设计目标对照表",
            ["命题业务环节", "系统设计目标", "对应章节"],
            [["图像采集", "兼容无人机、手机、相机影像，照片批量导入与构件关联", "第三、四章"],
             ["损伤识别与分类", "YOLOv8n专用模型＋免模型五路CV融合双模式，覆盖6类表观损伤", "第五章"],
             ["尺寸量化", "像素—物理尺度自动换算，输出长度、宽度、面积（预期误差见表 5-2）", "第五章"],
             ["空间定位", "解析式2D→3D面投影，病害归属到具体BIM构件并三维标记", "第五章"],
             ["报告输出", "Qwen-VL诊断＋python-docx一键生成规范Word报告", "第五、六章"]])

    add_h2(doc, "1.4  作品介绍")
    add_body(doc, "本作品为“桌面检测插件＋数字孪生网页平台”双形态交付的整体解决方案：")
    add_body(doc, "（1）BIMBase桌面检测插件：承载“导入照片→智能检测→AI诊断→尺寸量化→面投影定位→报告生成”"
                  "全流程，普通笔记本电脑即可运行，YOLOv8n轻量化模型支持CPU端推理；")
    add_body(doc, "（2）数字孪生网页平台：基于three.js的单文件离线网页，实现常泰长江大桥真实尺度程序化三维"
                  "重建，支持构件显隐、病害JSON导入与三维贴片可视化，浏览器免安装直接访问，可部署至公网网址，"
                  "平台三维视角如图 1-3 所示。")
    add_fig(doc, ref_img("twin_view"), "图 1-3  数字孪生平台三维视角", width_cm=15.0)
    add_body(doc, "两种形态通过病害数据JSON文件衔接：插件完成内业处理并导出数据，平台承载成果展示与病害档案"
                  "服务，形成“检测工具＋数据平台”的完整交付。")

    add_h2(doc, "1.5  可行性分析")
    add_body(doc, "（1）项目可行性：团队已完成从算法训练、插件开发到数字孪生平台的全流程实现，并在常泰长江"
                  "大桥真实工程BIM模型上完成贯通验证，基线指标如实可查，项目处于小试阶段，后续路线清晰；")
    add_body(doc, "（2）社会环境可行性：全国公路桥梁超100万座进入运维期，检测养护需求持续增长；交通强国、"
                  "数字中国战略为基础设施数字化提供政策支撑；国产BIMBase引擎的推广为本作品提供了良好的产业"
                  "生态；")
    add_body(doc, "（3）技术可行性：YOLOv8、OpenCV、PyTorch、Qwen-VL、three.js等关键技术均为成熟开源生态；"
                  "解析式面投影直接利用BIM精确几何信息，无需额外硬件，计算量小、确定性强；双模式检测路线保证"
                  "了无标注场景下的可用性。")

    add_h2(doc, "1.6  项目创新点")
    add_body(doc, "（1）免模型五路CV融合冷启动：黑帽变换、多尺度自适应阈值、K-Means颜色聚类、局部纹理标准差、"
                  "Canny边缘密度五路掩码融合，配合HSV天空抑制与NMS去重，在无标注数据场景下实现零样本冷启动"
                  "检测，并可反哺模型预标注；")
    add_body(doc, "（2）Qwen-VL双图多模态诊断：以“原图＋带框图”双图输入Qwen-VL-Max大模型，严格输出病害类型、"
                  "程度、成因、处置建议、紧迫度五字段结构化JSON，将通用多模态大模型规范化为可归档的工程诊断"
                  "能力；")
    add_body(doc, "（3）解析式面投影轻量定位：利用BIM模型精确几何信息，以解析公式完成2D→3D等比投影，替代"
                  "成本高昂的SFM三维重建与点云路线，无需额外硬件，定位颗粒度与构件管理单元一致；")
    add_body(doc, "（4）识别—量化—定位—报告全链路闭环与双形态交付：五环流程在桌面插件内一键贯通；同时已"
                  "建成基于three.js的数字孪生网页平台，以单文件离线网页形式承载常泰长江大桥真实尺度三维模型与"
                  "病害贴片档案，实现“桌面检测插件＋已建成数字孪生网页平台”的双形态交付。")


# ---------------------------------------------------------------------------
# 二、应用场景
# ---------------------------------------------------------------------------

def build_ch2(doc):
    add_h1(doc, "二、应用场景")
    add_body(doc, "这套系统到底能在哪些场合派上用场？我们梳理了桥梁检测业务中最常见的四类场景，逐一说明"
                  "用法；正式提交前，各场景还会配上实际操作的演示截图。")
    add_body(doc, "先看一张对比图（图 2-1）：过去干一次检测，采集、判读、测量、定位、写报告五个环节分给"
                  "不同人分步做，数据在纸面与表格间反复誊录，环节割裂、数据断链；现在用本方案，同一次检测任务"
                  "由一个人点一次按钮就能从头走到尾，数据自动衔接、全程可追溯。正是这个转变，让下面四类场景"
                  "真正落地。")
    add_fig(doc, ppt_img("对比图_检测流程前后对比.png"), "图 2-1  检测业务流程前后对比", width_cm=15.0)

    add_h2(doc, "2.1  定期检测辅助")
    add_body(doc, "定期检测是法规规定的“规定动作”，报告要求高。本系统为定期检测当好“内业助手”：外业拍完"
                  "照片回来，病害识别、尺寸量化、三维定位由系统批量完成，检测人员把精力集中在复核与签认上，"
                  "内业整理的工作量明显减轻。")
    add_clue(doc, "【截图线索】定期检测场景：插件批量导入某跨巡检照片并输出病害清单的界面截图")

    add_h2(doc, "2.2  经常性检查")
    add_body(doc, "经常性检查贵在勤快、便宜。巡查人员拿手机随手拍的照片，回去导进系统就能自动分析——哪座桥"
                  "新冒了裂缝、哪处剥落又扩大了，一目了然，支撑“早发现、早处置”的预防性养护。")
    add_clue(doc, "【截图线索】经常性检查场景：手机拍摄照片导入插件并完成识别的界面截图")

    add_h2(doc, "2.3  灾后应急排查")
    add_body(doc, "台风、洪水、地震过后，最缺的就是时间。系统能在短时间内把成百上千张应急排查照片过一遍，"
                  "自动挑出疑似病害并统计分布，帮助应急人员快速锁定需要优先复查的部位，为抢通保通决策提供"
                  "参考。")
    add_clue(doc, "【截图线索】灾后应急场景：批量影像初筛结果统计与病害分布的界面截图")

    add_h2(doc, "2.4  无人机航线化巡检")
    add_body(doc, "无人机按规划航线自动采集，照片角度齐、覆盖全，正好与本系统的批量分析和面投影定位能力"
                  "匹配：飞机回来，照片批量导入，病害自动分析、自动归档到三维模型，形成“航线采集—自动分析—"
                  "三维归档”的标准化作业流。")
    add_clue(doc, "【截图线索】无人机巡检场景：无人机航拍照片与病害三维落位对照的截图")

    add_h2(doc, "2.5  服务对象与系统定位边界")
    add_body(doc, "这套系统服务三类用户：（1）桥梁检测单位——少爬高、少熬夜编报告；（2）桥梁管养单位——"
                  "病害档案在三维模型里看得见、可追溯，养护决策有依据；（3）设计施工单位——拿到带准确定位的"
                  "病害数据，加固维修有的放矢。")
    add_body(doc, "系统定位为桥梁表观损伤智能检测的数字化辅助决策工具，不替代依法开展的定期检测、特殊检测、"
                  "荷载试验和结构安全评估。系统输出的识别、量化与定位结果，均需经具有相应资质的专业人员复核"
                  "确认后，方可作为正式检测成果使用。应用边界的完整声明见附录四。")


# ---------------------------------------------------------------------------
# 三、系统结构设计
# ---------------------------------------------------------------------------

def build_ch3(doc):
    add_h1(doc, "三、系统结构设计")

    add_h2(doc, "3.1  总体架构")
    add_body(doc, "系统采用“数据层—算法层—引擎层—应用层”四层架构，自下而上逐层支撑，如表 3-1 所示，总体"
                  "架构如图 3-1 所示。")
    add_tbl(doc, "表 3-1  系统总体架构",
            ["层次", "主要组成", "功能定位"],
            [["应用层", "BIMBase桌面检测插件、Word报告自动生成、网页端数字孪生平台",
              "面向用户的数字化成果形态"],
             ["引擎层", "BIMBase国产三维图形引擎、pyp3d参数化建模库、three.js网页三维引擎",
              "三维显示、面投影计算、模型承载"],
             ["算法层", "YOLOv8目标检测（PyTorch）、免模型五路CV掩码融合、Qwen-VL多模态诊断",
              "损伤识别、量化与诊断核心算法"],
             ["数据层", "GYU-DET（11,123张）、CODEBRIM（1,022张）、本地标注整合集（1,014张）",
              "训练验证数据与病害档案数据"]])
    add_fig(doc, ppt_img("架构图_系统总体架构.png"), "图 3-1  系统总体架构", width_cm=15.0)
    add_body(doc, "四层架构中，数据层为算法层提供训练与验证基础；算法层输出识别、量化与诊断结果；引擎层承载"
                  "三维模型与空间计算；应用层面向最终用户提供可交互的数字化成果。各层之间通过标准数据接口"
                  "解耦，便于独立升级与跨平台迁移。")

    add_h2(doc, "3.2  数字化业务流程")
    add_body(doc, "系统将检测业务重构为五环闭环流程，如图 3-2 所示：（1）图像采集：以无人机巡检照片为主要"
                  "数据来源，兼容手机、相机影像；（2）损伤智能识别与分类：YOLOv8n与五路CV融合双模式；（3）损伤"
                  "几何尺寸量化：基于参照物框选标定的像素—物理尺度换算；（4）三维空间定位：解析式2D→3D面投影，"
                  "病害归属到具体构件；（5）检测报告自动生成：Qwen-VL诊断＋python-docx一键生成Word报告。")
    add_fig(doc, ppt_img("思维导图_数字化业务流程.png"), "图 3-2  数字化业务流程五环闭环", width_cm=15.0)
    add_body(doc, "五环流程在插件内一键贯通，各环节输出均作为下一环节的标准输入，数据不落地、不誊录，从机制"
                  "上消除了传统模式“多人分步、数据断链”的痛点，如图 3-2 所示。")

    add_h2(doc, "3.3  双形态部署")
    add_body(doc, "系统采用“桌面插件＋在线平台”双形态交付，如图 3-3 所示：")
    add_body(doc, "（1）桌面检测插件：基于BIMBase平台开发的Python插件，普通笔记本电脑即可运行；YOLOv8n轻量化"
                  "模型支持CPU端推理，无需专业GPU设备，契合基层检测单位硬件条件；")
    add_body(doc, "（2）数字孪生在线平台：团队已建成的网页端桥梁数字孪生平台（基于three.js引擎的单文件离线"
                  "网页，662KB），已实现常泰长江大桥真实尺度程序化三维重建与病害三维贴片可视化，浏览器免安装"
                  "直接访问，并支持部署至公网网址对外提供服务。")
    add_fig(doc, ppt_img("示意图_双形态交付.png"), "图 3-3  双形态交付示意图", width_cm=15.0)
    add_body(doc, "两种形态通过病害数据JSON文件衔接：插件完成检测、诊断、定位与报告生成后导出JSON，平台导入"
                  "JSON即在三维场景中还原病害分布，如图 3-3 所示。")

    add_h2(doc, "3.4  参数化构件库")
    add_body(doc, "病害三维定位与数字孪生展示依赖结构化的构件模型。团队围绕常泰长江大桥建立了参数化构件库，"
                  "全部构件均为原创参数化构件，每个构件有效可调参数不少于4个，参数摘自组件库源码。常泰长江"
                  "大桥模型共包含16类参数化构件，如图 3-4 所示：上部结构7项（主塔、侧面钢桁架、工字钢梁、"
                  "斜拉索、支座、自密实混凝土层及隔离层、轨道底座）、下部结构3项（门式桥墩、承台及桩基、"
                  "扩大基础）、附属设施6项（新泽西护栏、防撞护栏、轨道、接触网、路面及交通标线、铁路封闭网）。")
    add_fig(doc, ppt_img("构件清单表.png"), "图 3-4  常泰长江大桥参数化构件清单", width_cm=15.0)
    add_body(doc, "构件清单同时给出了病害定位路由规则：病害数据按构件关键词（塔/墩/承台/索/桥面板/附属）"
                  "自动路由至对应构件组，与数字孪生平台的贴片归属规则一一对应，如图 3-4 所示。完整清单说明"
                  "见附录二。")


# ---------------------------------------------------------------------------
# 四、操作说明
# ---------------------------------------------------------------------------

def build_ch4(doc):
    add_h1(doc, "四、操作说明")
    add_body(doc, "这一章手把手演示系统怎么用。主界面如图 4-1 所示：左边是操作面板，按“导入照片—构件信息—"
                  "尺寸标定—病害记录—生成报告”分区排布；右边是照片浏览和已录入的病害列表。下面分九步走一遍"
                  "完整流程，走完就能从照片得到报告、再把病害挂到三维模型上。")
    add_fig(doc, ref_img("plugin_ui"), "图 4-1  桥梁病害识别插件主界面", width_cm=13.0)

    steps = [
        ("4.1  第一步：导入照片",
         "点击“导入无人机照片”按钮，选择巡检照片导入插件。支持无人机、手机、相机拍摄的常见格式影像，"
         "兼容中文路径。导入后照片显示于右侧视图区，可缩放查看细节。",
         "【截图线索】步骤1：点击“导入无人机照片”后照片载入视图区的界面截图"),
        ("4.2  第二步：参照物标定",
         "点击“框选参照物标定”，在照片上框选已知实际尺寸的参照物（如标尺、已知宽度构件），输入参照物实际"
         "长度，系统自动计算该照片的像素—物理比例（mm/px），作为尺寸量化的标定基础；可随时“清除标定”"
         "重新标定。",
         "【截图线索】步骤2：框选参照物并输入实际长度完成标定的界面截图"),
        ("4.3  第三步：智能检测",
         "点击“自动识别异常区域”，系统按双模式策略执行检测：已加载YOLOv8n模型时输出六类损伤的类别与检测框；"
         "无模型环境下自动切换免模型五路CV掩码融合，输出损伤候选区域。检测结果以标注框形式叠加显示在照片上。",
         "【截图线索】步骤3：自动识别后照片叠加损伤检测框的界面截图"),
        ("4.4  第四步：AI 智能诊断",
         "点击“AI 智能诊断”，系统将原图与带框图双图输入Qwen-VL-Max多模态大模型，返回病害类型、程度、成因、"
         "处置建议、紧迫度五字段结构化结果，供人工复核。AI诊断需配置DashScope API Key（点击“配置 AI Key”）；"
         "离线环境下可跳过本步，直接进入人工录入。",
         "【截图线索】步骤4：AI 诊断返回五字段结果的界面截图"),
        ("4.5  第五步：尺寸量化",
         "系统基于第二步的标定比例，对检测框内的损伤自动完成尺寸换算：长度取检测框长边乘以比例，宽度取短边"
         "乘以比例，面积按检测框外接矩形乘以比例平方估算（真实病害面积偏小），三项几何量随病害记录一并保存。",
         "【截图线索】步骤5：病害记录中显示长度/宽度/面积量化结果的界面截图"),
        ("4.6  第六步：面投影定位",
         "在“构件信息”区选择构件类型与桥梁名称、构件编号，或点击“获取当前选中组件”读取BIMBase中选中构件；"
         "选择投影面后点击“病害投影”，系统按解析式2D→3D面投影将病害标记落位到构件表面，沿法向偏移2mm防止"
         "闪面，投影标记以点云形式合成显示于三维模型。",
         "【截图线索】步骤6：病害投影后BIM模型上出现病害标记的三维视图截图"),
        ("4.7  第七步：报告生成",
         "在“添加病害记录”区复核病害类型、严重程度、位置、尺寸与备注，点击“添加到列表”；全部记录完成后"
         "点击“生成诊断报告”，系统基于python-docx一键生成规范Word检测报告，包含封面信息、病害清单、损伤"
         "位置分布、成因分析与处置建议。",
         "【截图线索】步骤7：生成的Word检测报告首页与病害清单页截图"),
        ("4.8  第八步：导出网页数据",
         "点击导出功能，将病害记录序列化为标准JSON文件，作为数字孪生平台的数据输入。JSON包含病害类型、"
         "所属构件、位置、尺寸、程度与紧迫度等字段，与平台贴片归属规则一一对应。",
         "【截图线索】步骤8：导出病害数据JSON文件的界面截图"),
        ("4.9  第九步：数字孪生查看",
         "用浏览器打开数字孪生平台网页（单文件离线网页，或公网部署地址），点击“导入JSON”选择第八步导出的"
         "数据文件，病害即以三维贴片形式落位于全桥模型对应构件；可通过构件复选框分组显隐，点击贴片查看病害"
         "详情，或使用“载入示例数据”查看内置示例。",
         "【截图线索】步骤9：数字孪生平台导入JSON后病害贴片分布的界面截图"),
    ]
    for title, body, clue in steps:
        add_h3(doc, title)
        add_body(doc, body)
        add_clue(doc, clue)
    add_body(doc, "至此，从照片到报告、再到三维档案的完整业务闭环操作完成，全过程无需人工誊录数据，如图 4-1 "
                  "所示的主界面即可完成全部操作。")


# ---------------------------------------------------------------------------
# 五、核心技术及原理
# ---------------------------------------------------------------------------

def build_ch5(doc):
    add_h1(doc, "五、核心技术及原理")
    add_body(doc, "前面几章说了系统能做什么，这一章讲讲它是怎么做到的。四项关键技术——损伤智能识别"
                  "（双模式）、损伤几何尺寸量化、解析式面投影三维定位、数字孪生平台，全部由团队自主实现；"
                  "核心代码节选见附录三，欢迎评审专家对照查验。")

    add_h2(doc, "5.1  基于 YOLOv8 的损伤智能识别")
    add_body(doc, "（1）模型选型：选用YOLOv8n轻量化目标检测模型，基于PyTorch框架构建。n级骨干参数量小、推理"
                  "速度快，支持在CPU端完成训练与部署，便于在基层检测单位普通办公电脑上运行，契合命题对轻量化"
                  "部署的要求；")
    add_body(doc, "（2）类别体系：覆盖裂缝、剥落、露筋、蜂窝麻面、渗水、锈蚀6类桥梁典型表观损伤，与GYU-DET、"
                  "CODEBRIM公开数据集的类别体系兼容，便于训练与对标。需要说明的是，本地合并训练集实际为7个类别"
                  "（nc=7），即在对外六类损伤之外另设“已修复”标签，用于病害复检闭环管理；系统对外识别与展示的"
                  "损伤类别口径仍为六类；")
    add_body(doc, "（3）数据集建设：训练数据由公开数据集与本地自建标注数据集联合构成，如表 5-1 所示。公开"
                  "数据集提供类别多样性与规模基础；本地标注数据来自真实巡检报告影像的提取与人工标注，使模型"
                  "更贴近实际业务场景的成像条件与病害形态。")
    add_tbl(doc, "表 5-1  数据集建设情况",
            ["数据来源", "规模", "标注方式", "用途"],
            [["GYU-DET（公开数据集）", "11,123张", "已有标注（格式转换）", "训练/验证"],
             ["CODEBRIM（公开数据集）", "1,022张", "已有标注（格式转换）", "训练/验证"],
             ["本地巡检报告提取与人工标注", "1,014张（整合集）", "YOLO格式人工标注",
              "贴近真实业务场景的训练/验证"]])
    add_body(doc, "（4）基线性能：基线模型在CPU环境下完成50个epochs训练，实测mAP50约0.336、mAP50-95约0.085，"
                  "识别准确率与召回率由PR曲线与归一化混淆矩阵佐证，训练曲线完整保存、可复核。上述指标为基线"
                  "模型的真实水平，本说明书如实呈现、不作夸大，如图 5-1 所示；")
    add_fig(doc, ppt_img("模型性能基线与提升预期.png"), "图 5-1  模型性能基线与提升预期", width_cm=14.0)
    add_body(doc, "（5）提升路线：针对当前基线，拟从数据增强（旋转、翻转、光照扰动、马赛克拼接）、更大骨干"
                  "网络（YOLOv8s/m迁移学习）、半监督学习（未标注影像伪标签迭代）、补充标注与类别均衡采样、"
                  "小目标特征层优化五条路径持续提升，预期区间如图 5-1 所示；模型改进训练完成后将以实测值如实"
                  "更新，原始记录可备查。")

    add_h2(doc, "5.2  免模型五路 CV 掩码融合")
    add_body(doc, "针对冷启动场景（无标注数据、无训练条件），团队设计了免训练的五路CV掩码融合检测方法，"
                  "五路独立通道从不同图像特征视角刻画损伤：")
    add_body(doc, "（1）黑帽变换通道：利用暗色病害与亮背景的形态学差异，检测细长裂缝类损伤；")
    add_body(doc, "（2）多尺度自适应阈值通道：以三种邻域尺度的自适应阈值并联，检测不同大小的暗色区域；")
    add_body(doc, "（3）K-Means颜色聚类通道：在Lab颜色空间聚类并提取最暗/最亮类，检测颜色明显异常区域；")
    add_body(doc, "（4）局部纹理标准差通道：计算局部纹理标准差并与邻域均值比较，检测剥落、露骨料等粗糙区域；")
    add_body(doc, "（5）Canny边缘密度通道：统计局部边缘密度，检测具有明显边界的病害区域。")
    add_body(doc, "五路掩码经HSV天空抑制剔除无关背景、NMS去重合并重叠候选后融合输出损伤区域。该方案无需任何"
                  "标注数据与训练过程，在新桥型、新场景下零门槛冷启动；其输出还可作为YOLO模型的预标注辅助，"
                  "降低数据集建设成本。五路方法的真实代码见附录三。")

    add_h2(doc, "5.3  Qwen-VL 双图多模态诊断")
    add_body(doc, "病害成因诊断采用“原图＋带框图”双图输入范式：将巡检原图与叠加检测框的标注图一并输入"
                  "Qwen-VL-Max多模态大模型，通过严格提示词约束，输出包含病害类型、程度、成因、处置建议、紧迫度"
                  "五个字段的结构化JSON。双图输入使模型既能观察原始纹理细节，又能聚焦待诊断区域；结构化输出"
                  "保证结果可解析、可归档，直接对接检测报告生成环节。调用经DashScope API完成，密钥由用户自行"
                  "配置，离线环境下可跳过诊断、以人工录入代替。")

    add_h2(doc, "5.4  损伤几何尺寸量化")
    add_body(doc, "（1）尺度标定：损伤几何尺寸量化的关键是确定每个像素对应的实际物理尺寸。系统采用参照物"
                  "框选标定：检测人员在照片上框选已知实际长度的参照物（如标尺、已知尺寸的构件边缘），系统按"
                  "“参照物实际长度÷参照物框像素长边”计算像素比例（mm/px），作为该照片全部量化计算的尺度基准；"
                  "每张照片独立标定，标定可随时清除重做；")
    add_body(doc, "（2）计算流程：尺寸量化按“检测框定位→参照物框选标定→像素尺寸换算→量化输出”四步处理，"
                  "如图 5-2 所示。检测框定位：由识别环节输出损伤检测框，确定量化区域；参照物框选标定：获得该"
                  "照片的像素比例；像素尺寸换算：损伤长度取检测框长边乘以比例，宽度取短边乘以比例，面积按检测框"
                  "外接矩形乘以比例平方估算；量化输出：长度、宽度、面积三项几何量随病害记录一并保存，并写入检测"
                  "报告；")
    add_fig(doc, ppt_img("思维导图_尺寸计算流程_v2.png"), "图 5-2  损伤尺寸计算流程", width_cm=15.0)
    add_body(doc, "（3）量化口径与精度提升方向：需要如实说明的是，当前版本按检测框外接矩形估算面积，对"
                  "不规则病害的面积估计存在偏差，代码注释中已明确标注该口径；损伤掩膜细化以贴合真实轮廓、骨架"
                  "提取以精确测量裂缝长度，是规划中的精度提升方向，将在后续版本中实现并按实测口径重新评估；")
    add_body(doc, "（4）精度目标：量化精度采用与人工测量对比的方式验证，选取覆盖各损伤类型的典型样本，由检测"
                  "人员按现行规程现场测量作为基准值，计算系统量化值的相对误差。预期目标如表 5-2 所示。")
    add_tbl(doc, "表 5-2  损伤尺寸量化精度预期目标（预期口径，测试完成后以实测回填）",
            ["验证项", "预期误差目标", "验证方式", "实测结果"],
            [["裂缝长度", "相对误差≤3.5%", "与人工测量对比", "待补充实测数据"],
             ["损伤最大宽度", "相对误差≤6%", "与人工测量对比", "待补充实测数据"],
             ["损伤面积", "相对误差≤7%", "与人工测量对比", "待补充实测数据"]])
    add_note(doc, "注：表 5-2 为预期目标口径，系统测试完成后以实测数据如实回填，测试脚本与原始测量记录"
                  "同步归档、可备查。")

    add_h2(doc, "5.5  解析式面投影三维定位")
    add_body(doc, "（1）方法原理：对BIM模型中的构件面，以面中心为原点、面法向与外轮廓U/V轴建立局部坐标系，"
                  "通过解析公式将图像中的损伤像素坐标等比投影到构件表面，实现损伤从二维图像到三维模型的空间"
                  "映射。投影标记沿构件面法向偏移2mm，避免与构件表面渲染重叠产生闪面；全部投影标记以点云形式"
                  "经Combine合成，在三维模型中持久化展示。投影运行效果如图 5-3 所示；")
    add_fig(doc, ref_img("projection"), "图 5-3  病害面投影定位效果（BIMBase 内运行）", width_cm=15.0)
    add_body(doc, "（2）构件联动：系统内置构件类型识别能力，覆盖19种构件参数签名；病害投影后自动归属到具体"
                  "构件，与16类参数化构件清单联动，形成“构件—病害”对应的数字化档案，支持按构件检索病害、"
                  "按病害跳转定位；")
    add_body(doc, "（3）方法对比：与常见定位路线相比，解析式面投影直接利用BIM模型已有的精确几何信息，计算量"
                  "小、结果确定性强，且投影过程参数化、可解释、可复核，对比如表 5-3 所示。")
    add_tbl(doc, "表 5-3  三维空间定位方法对比",
            ["定位方法", "硬件成本", "精度水平", "部署门槛", "适用场景"],
            [["本方案（解析式面投影）", "无额外硬件", "以构件为单元", "低，普通笔记本即可",
              "基层管养单位常态化检测"],
             ["SFM三维重建", "需大量影像与较高算力", "较高", "高，重建耗时较长",
              "科研与重点工程精细分析"],
             ["GPS定位", "依赖差分设备与信号条件", "普通GPS为米级", "中", "开阔场景粗略定位"],
             ["人工参考点测量", "全站仪等测量设备", "高", "中，需专业测量人员", "局部精细测量"]])
    add_body(doc, "（4）精度目标：定位精度通过在BIM模型中预设已知坐标标记点、对比投影坐标与真实坐标偏差的"
                  "方式测试，预期目标如表 5-4 所示。")
    add_tbl(doc, "表 5-4  三维定位精度预期目标（预期口径，测试完成后以实测回填）",
            ["验证项", "预期目标", "验证方式", "实测结果"],
            [["构件归属正确率", "≥95%", "投影落位构件与人工指定构件比对", "待补充实测数据"],
             ["面内平均定位误差", "≤8cm", "预设标记点投影坐标与真实坐标比对", "待补充实测数据"],
             ["面内最大定位误差", "≤20cm", "同上", "待补充实测数据"]])
    add_note(doc, "注：表 5-4 为预期目标口径，测试完成后以实测数据如实回填，原始记录可备查。")

    add_h2(doc, "5.6  数字孪生平台技术")
    add_body(doc, "（1）平台形态：团队已建成常泰长江大桥数字孪生平台，平台为662KB的单文件离线网页，基于"
                  "three.js三维引擎开发，无需安装任何软件，浏览器打开即可使用，同时支持部署至公网网址，"
                  "实现免安装直接访问；")
    add_body(doc, "（2）真实尺度重建：按设计资料对常泰长江大桥进行程序化三维重建——主航道桥为双塔双索面"
                  "钢桁梁斜拉桥，桥梁全长2440m，跨径布置142+490+1176+490+142m，空间钻石型主塔总高352m，双层"
                  "钢桁梁宽39m、高16m，上层为双向6车道高速公路，下层为双线城际铁路加4车道公路；墩位里程按"
                  "-1220/-1078/-588/+588/+1078/+1220m真实布置，如图 5-4 所示；")
    add_body(doc, "（3）病害可视化：平台支持病害数据JSON导入，按构件关键词（塔/墩/承台/索/桥面）自动路由"
                  "落位，在三维模型上以贴片形式展示病害位置，点击贴片可查看病害类型、程度、成因与处置建议等"
                  "详情；内置8条示例病害数据便于演示；提供照片覆盖尺度换算滑块与工程概况卡；15组构件复选框与"
                  "参数化构件库一一对应，支持分组显隐。")
    add_fig(doc, TWIN_IMG, "图 5-4  数字孪生平台界面（常泰长江大桥全桥总览）", width_cm=15.0)
    add_body(doc, "平台与桌面插件通过病害数据JSON衔接，构成“内业处理＋成果展示”的完整链路，如图 5-4 所示。")


# ---------------------------------------------------------------------------
# 六、项目实现与案例验证
# ---------------------------------------------------------------------------

def build_ch6(doc):
    add_h1(doc, "六、项目实现与案例验证")

    add_h2(doc, "6.1  实施计划与进度安排")
    add_body(doc, "项目自 2026 年 6 月启动，按六个阶段推进，进度安排如表 6-1 所示。其中需求调研与命题对接、"
                  "基线系统开发、数据集建设与模型训练三个阶段已完成，案例验证与指标测试正在开展（实测数据"
                  "按计划回填），材料申报与决赛转化为后续节点并已在表中标注。")
    add_tbl(doc, "表 6-1  实施计划与进度安排表",
            ["阶段", "时间", "主要任务与目标", "关键难点", "资源配置", "责任人"],
            [["需求调研与命题对接", "2026.6—2026.7",
              "梳理检测业务流程痛点，完成命题解析与总体方案设计",
              "业务理解深度", "企业命题文件、公开资料、指导教师", "待填写"],
             ["基线系统开发", "2026.7—2026.8",
              "完成 BIMBase 桌面插件五环流程开发与联调",
              "插件与引擎接口适配", "BIMBase 平台、pyp3d、PyQt5", "待填写"],
             ["数据集建设与模型训练", "2026.8—2026.9",
              "公开数据集转换、本地标注整合，完成 YOLOv8n 基线训练（50 epochs，CPU）",
              "标注质量与类别均衡", "GYU-DET、CODEBRIM、本地巡检影像", "待填写"],
             ["案例验证与指标测试", "2026.9",
              "常泰长江大桥全流程验证；量化、定位、耗时实测并如实回填",
              "实测组织与人工对标", "常泰桥 BIM 模型、巡检照片、人工测量工具", "待填写"],
             ["材料申报与网评", "2026.9—2026.10",
              "对策书、演示材料与证明文书制作、审核与提交",
              "材料真实性与完整性", "本文档及配套材料、企业证明文书模板", "待填写"],
             ["决赛演示与成果转化（规划）", "2026.11—2026.12",
              "决赛路演演示；对接试用企业，推进成果转化落地",
              "现场演示稳定性", "数字孪生平台、插件演示环境", "待填写"]])
    add_note(doc, "注：责任人待团队报名确认后填写；“规划”节点为尚未开展的后续安排，其余节点为已完成或"
                  "进行中的真实进度。")

    add_h2(doc, "6.2  实现过程与迭代")
    add_body(doc, "项目按“数据集建设→基线模型→插件开发→面投影定位→报告生成→数字孪生平台”的路径迭代"
                  "推进，里程碑如图 6-1 所示：（1）完成GYU-DET、CODEBRIM公开数据集格式转换与本地巡检影像人工"
                  "标注，形成整合训练集；（2）完成YOLOv8n基线模型训练（50 epochs，CPU），指标如实记录；（3）完成"
                  "BIMBase桌面插件五环流程开发并联调；（4）建成数字孪生网页平台，实现真实尺度重建与病害贴片"
                  "可视化。后续节点（模型优化训练、量化与定位实测回填、公网部署与试用）为规划节点，已在图 6-1 "
                  "中明确标注“规划”。")
    add_fig(doc, ppt_img("示意图_里程碑.png"), "图 6-1  项目实施里程碑", width_cm=15.0)

    add_h2(doc, "6.3  常泰长江大桥案例验证")
    add_body(doc, "（1）验证对象：常泰长江大桥为双层公铁两用斜拉桥，团队已建立其BIM参数化模型，P3D工程文件"
                  "244.9MB，包含16类参数化构件（清单见图 3-4 及附录二）。模型按真实工程数据构建：桥梁全长"
                  "2440m（主航道桥），跨径布置142+490+1176+490+142m，空间钻石型主塔总高352m，双层钢桁梁宽39m、"
                  "高16m，墩位里程-1220/-1078/-588/+588/+1078/+1220m，模型正立面如图 6-2 所示；")
    add_fig(doc, ref_img("bim_model"), "图 6-2  常泰长江大桥 BIM 模型正立面", width_cm=15.0)
    add_body(doc, "（2）验证过程：以巡检影像为输入，在BIMBase中运行桌面插件，完成“导入照片→智能检测→AI诊断"
                  "→尺寸量化→面投影定位→报告生成”全流程贯通验证，病害标记成功落位至对应构件表面并与构件清单"
                  "联动；随后将病害数据JSON导入数字孪生平台，三维贴片正确分布于对应构件，验证了双形态链路的"
                  "完整性（投影效果见图 5-3，平台效果见图 5-4）。")

    add_h2(doc, "6.4  效果评价指标")
    add_body(doc, "案例验证的效果评价指标如表 6-2 所示。已完成的指标如实填写；预期口径的指标统一在表中标注"
                  "“预期”，测试完成后以实测数据如实回填。全部评价数据真实、清晰、可复核，测试脚本与原始记录"
                  "可备查。")
    add_tbl(doc, "表 6-2  案例验证效果评价指标",
            ["评价指标", "结果"],
            [["损伤识别准确率与召回率",
              "实测：mAP50约0.336、mAP50-95约0.085（基线模型，PR曲线与混淆矩阵佐证，见5.1节）"],
             ["单张图像平均检测时间",
              "预期：YOLOv8n约0.2～0.5秒/张（CPU），五路CV融合约1～3秒/张；待补充实测数据回填"],
             ["尺寸量化与人工测量差异",
              "预期：长度≤3.5%、宽度≤6%、面积≤7%（相对误差）；待补充实测数据回填"],
             ["空间定位精度",
              "预期：构件归属正确率≥95%、面内平均误差≤8cm；待补充实测数据回填"],
             ["人工判读环节减少情况",
              "判读、测量、定位、报告编制四个环节由多人分步完成转变为一人一键流转（定性）"],
             ["检测报告生成效率改善", "一键自动生成规范Word报告，替代手工编制（定性）"]])


# ---------------------------------------------------------------------------
# 七、运行环境
# ---------------------------------------------------------------------------

def build_ch7(doc):
    add_h1(doc, "七、运行环境")

    add_h2(doc, "7.1  软件环境")
    add_body(doc, "系统软件环境如表 7-1 所示。桌面插件运行于国产BIMBase三维图形平台，算法基于成熟开源生态，"
                  "数字孪生平台基于three.js且无需安装。")
    add_tbl(doc, "表 7-1  软件环境",
            ["类别", "名称与版本", "用途"],
            [["三维平台", "BIMBase（国产三维图形引擎，支持pyp3d）", "插件运行底座、模型承载"],
             ["运行环境", "Python 3.x（BIMBase插件环境）", "插件与算法运行"],
             ["深度学习", "PyTorch、ultralytics（YOLOv8）", "损伤识别模型训练与推理"],
             ["计算机视觉", "OpenCV", "五路CV掩码融合、检测框尺寸换算"],
             ["界面框架", "PyQt5", "插件交互界面"],
             ["报告生成", "python-docx", "Word检测报告自动生成"],
             ["多模态诊断", "Qwen-VL-Max（DashScope API）", "病害成因与处置建议诊断"],
             ["网页三维", "three.js（单文件离线网页内置）", "数字孪生平台三维渲染"]])

    add_h2(doc, "7.2  硬件环境")
    add_body(doc, "系统面向基层检测单位硬件条件设计，无需专业GPU与测量设备，如表 7-2 所示。")
    add_tbl(doc, "表 7-2  硬件环境",
            ["类别", "配置", "说明"],
            [["影像采集", "消费级无人机/手机/数码相机", "对接既有巡检作业模式"],
             ["运行终端", "普通办公笔记本/台式机（CPU即可）", "YOLOv8n支持CPU推理"],
             ["三维展示", "支持WebGL的浏览器终端", "数字孪生平台免安装访问"],
             ["网络", "可选", "仅AI诊断环节需要联网"]])

    add_h2(doc, "7.3  数据接入与通信")
    add_body(doc, "（1）AI诊断通信：Qwen-VL诊断通过阿里云DashScope API完成，需用户自行配置API Key并联网调用；"
                  "影像数据经API传输时由用户按所在单位数据管理要求执行授权与脱敏；")
    add_body(doc, "（2）本地离线模式：YOLOv8n检测、五路CV融合、尺寸量化、面投影定位与报告生成全部支持本地"
                  "离线运行；离线环境下可跳过AI诊断环节，以人工录入病害信息代替，核心闭环不中断；")
    add_body(doc, "（3）双形态数据衔接：插件与数字孪生平台之间通过病害数据JSON文件衔接，字段规范、可校验，"
                  "便于留痕与归档。")


# ---------------------------------------------------------------------------
# 八、市场与竞争性分析
# ---------------------------------------------------------------------------

def build_ch8(doc):
    add_h1(doc, "八、市场与竞争性分析")

    add_h2(doc, "8.1  行业与市场需求")
    add_body(doc, "（1）存量规模：截至2025年底，全国公路桥梁已超过100万座，大量桥梁进入运维期，定期检测与"
                  "经常性检查任务繁重（本说明书仅引用公开总量口径，不估算具体市场金额）；")
    add_body(doc, "（2）需求驱动：检测资质管理趋严、养护决策精细化要求提升，推动检测业务从“人工经验驱动”"
                  "向“数据驱动”转型；无人机低空采集装备的普及使影像数据获取成本显著降低，为影像智能分析创造"
                  "了条件；")
    add_body(doc, "（3）基层缺口：基层管养单位普遍存在“设备买得起、软件用不起、人才留不住”的现实约束，"
                  "低成本、轻量化、免GPU的智能检测工具存在明确需求缺口。")

    add_h2(doc, "8.2  PEST 宏观环境分析")
    add_body(doc, "从政治、经济、社会、技术四个维度分析项目宏观环境，如图 8-1 所示：")
    add_body(doc, "（1）政治（P）：交通强国、数字中国战略持续推进，基础设施数字化与养护智能化获政策支持；"
                  "关键软件自主可控导向为国产BIM引擎生态带来发展机遇；")
    add_body(doc, "（2）经济（E）：基础设施存量运维期到来，检测养护投入持续增长；降本增效诉求推动检测单位"
                  "采用数字化工具；")
    add_body(doc, "（3）社会（S）：公众出行安全意识提升，桥梁安全事件社会关注度高；检测人员高空作业风险与"
                  "老龄化和用工短缺问题凸显，机器换人需求迫切；")
    add_body(doc, "（4）技术（T）：深度学习目标检测、多模态大模型、WebGL三维渲染等技术成熟并开源化，为轻量"
                  "级工程落地提供了技术底座。")
    add_fig(doc, ppt_img("分析图_PEST.png"), "图 8-1  PEST 宏观环境分析", width_cm=15.0)

    add_h2(doc, "8.3  竞争格局与差异化对比")
    add_body(doc, "本方案与三类现有路线的差异化对比如表 8-1 所示。")
    add_tbl(doc, "表 8-1  竞争格局差异化对比",
            ["对比维度", "国外商业BIM软件", "传统人工检测", "点云摄影测量方案", "本方案"],
            [["软件成本", "授权费用高", "无软件成本", "重建软件与算力成本高", "插件轻量、平台免安装"],
             ["硬件门槛", "需高配工作站", "桥检车等装备", "需扫描设备与算力", "普通笔记本＋消费级无人机"],
             ["智能识别", "多需二次开发", "依赖人工经验", "侧重几何重建", "YOLOv8＋五路CV双模式内置"],
             ["三维定位", "依赖完整BIM流程", "文字描述位置", "点云配准复杂", "解析式面投影，病害直达构件"],
             ["自主可控", "国外引擎", "—", "部分依赖国外软件", "国产BIMBase引擎＋开源生态"],
             ["报告输出", "需定制开发", "手工编制", "需二次加工", "一键生成规范Word报告"]])
    add_body(doc, "差异化定位：本方案不与大型商业软件正面竞争，而是面向基层检测单位与管养单位提供“够用、"
                  "好用、用得起”的轻量化数字化工具，以双形态交付覆盖内业处理与成果展示两类需求，如表 8-1 所示。")

    add_h2(doc, "8.4  商业模式与成果转化路径")
    add_body(doc, "（1）商业模式：插件授权（License年费，面向检测单位与管养单位）；检测服务（按项目收费，"
                  "提供数据处理＋AI分析＋报告生成服务）；平台订阅（数字孪生平台账号订阅、病害档案托管与多期"
                  "对比分析）；")
    add_body(doc, "（2）阶段定位：项目当前处于小试阶段，核心功能已在真实工程BIM模型上完成全流程贯通验证，"
                  "基线指标如实可查；")
    add_body(doc, "（3）转化路径：第一步，检测单位工具化落地，以插件授权与按项目服务切入；第二步，平台订阅"
                  "推广，依托数字孪生平台提供病害档案与劣化趋势服务；第三步，桥隧全域推广，将方法迁移至隧道、"
                  "房屋等基础设施检测场景。本方案落地门槛低，普通无人机加笔记本电脑即可完成部署，契合基层管养"
                  "单位预算。")

    add_h2(doc, "8.5  社会效益")
    add_body(doc, "（1）安全效益：降低检测人员高空抵近作业风险，提升病害早期发现能力，服务公众出行安全；")
    add_body(doc, "（2）行业效益：推动检测数据资产化、标准化，为养护科学决策提供数据支撑；")
    add_body(doc, "（3）育人效益：项目在真实工程场景中锤炼了团队成员的全栈开发与工程实践能力，是产教融合、"
                  "科教融汇的具体实践。")


# ---------------------------------------------------------------------------
# 九、产教协同与团队协作
# ---------------------------------------------------------------------------

def build_ch9(doc):
    add_h1(doc, "九、产教协同与团队协作")

    add_h2(doc, "9.1  三方协同机制")
    add_body(doc, "项目按照“企业出题、高校指导、学生攻关、成果服务产业”的模式组织实施，如图 9-1 所示："
                  "命题企业发布真实业务命题，并在检测业务流程、数据格式与业务规范方面提供指导；高校教师从土木"
                  "工程、智能建造、计算机视觉等专业方向把关技术路线；学生团队承担需求分析、方案设计、模型训练、"
                  "系统开发与案例验证的具体攻关任务。三方通过常态化交流机制将产业真实需求转化为可落地的技术"
                  "成果。")
    add_fig(doc, ppt_img("示意图_产教协同.png"), "图 9-1  产教协同三方机制", width_cm=15.0)

    add_h2(doc, "9.2  团队分工")
    add_body(doc, "团队按跨专业原则组建，涵盖土木工程、计算机、人工智能、电子信息等专业方向，分工如表 9-1 "
                  "所示。")
    add_tbl(doc, "表 9-1  团队分工表",
            ["角色", "姓名", "专业方向", "主要分工"],
            [["项目负责人", "待填写", "待填写", "总体统筹、进度管理、命题对接与答辩组织"],
             ["模型训练与数据集建设", "待填写", "待填写", "数据集整理标注、YOLOv8n训练优化、五路CV算法实现"],
             ["系统开发与集成部署", "待填写", "待填写", "BIMBase插件开发、面投影定位实现、报告生成"],
             ["需求分析与方案设计", "待填写", "待填写", "检测业务流程梳理、损伤类型体系确定、方案撰写"],
             ["数字孪生平台开发", "待填写", "待填写", "three.js平台开发、病害贴片可视化、JSON数据衔接"],
             ["案例验证与数据分析", "待填写", "待填写", "常泰桥案例组织、实测方案执行、指标回填"],
             ["成果展示与商业策划", "待填写", "待填写", "材料制作、市场分析、路演展示"]])
    add_note(doc, "注：团队成员姓名与专业方向待报名确认后填写，最终分工以实际报名材料为准。")
    add_body(doc, "在分工基础上，各角色的实质性贡献如表 9-2 所示，贡献内容均可对照源码仓库提交记录、训练"
                  "日志与项目文档核实。")
    add_tbl(doc, "表 9-2  成员实质性贡献说明表",
            ["角色", "姓名", "实质性贡献"],
            [["项目负责人", "待填写",
              "提出总体技术路线与系统架构，统筹全栈开发与进度管理，组织命题对接与阶段评审"],
             ["模型训练与数据集建设", "待填写",
              "完成三个来源数据集的整理、格式转换与人工标注，完成 YOLOv8n 基线训练与调参，如实记录训练指标"],
             ["系统开发与集成部署", "待填写",
              "实现 BIMBase 插件五环业务流程，开发面投影定位与报告生成模块并完成系统联调"],
             ["需求分析与方案设计", "待填写",
              "梳理检测业务五环痛点，完成命题契合度分析与总体方案设计，形成需求分析文档"],
             ["数字孪生平台开发", "待填写",
              "基于 three.js 独立完成常泰长江大桥真实尺度程序化三维重建与病害贴片可视化平台"],
             ["案例验证与数据分析", "待填写",
              "组织常泰桥案例验证，制定指标测试方案，负责实测执行与数据分析（实测进行中，结果如实回填）"],
             ["成果展示与商业策划", "待填写",
              "完成对策书、演示 PPT 与展示材料的制作，负责市场分析与路演呈现"]])
    add_note(doc, "注：成员实质性贡献承诺以报名系统提交为准。")

    add_h2(doc, "9.3  指导教师与外部资源")
    add_body(doc, "指导教师：待填写（拟由土木工程与计算机相关专业教师共同指导，负责技术路线把关与进度督导）。")
    add_body(doc, "外部资源：企业试用证明【待补充】——团队拟对接命题企业提供的试用渠道开展工具试用并获取"
                  "书面反馈；公开数据集（GYU-DET、CODEBRIM）按其许可协议使用；开源生态（PyTorch、ultralytics、"
                  "OpenCV、three.js等）按各自授权方式合规使用。")

    add_h2(doc, "9.4  调研过程与个人成长")
    add_body(doc, "【待补充】企业调研与试用记录：团队与命题企业及检测单位的调研纪要、试用反馈记录待整理后"
                  "补充，本说明书不作虚构陈述。调研工具（问卷、访谈提纲、纪要模板）见附录五，实际回收的问卷"
                  "与纪要扫描件将按附录五说明归档补入。")
    add_body(doc, "这个项目做下来，团队成员的收获是实打实的：（1）全栈开发能力：从Python插件、桌面界面到"
                  "three.js网页三维平台，一套跨端系统从头到尾自己实现；（2）AI工程能力：数据集建设、模型训练"
                  "调优、多模态大模型接入完整走过一遍，更重要的是学会了用如实的口径呈现指标——不夸大、不遮掩；"
                  "（3）工程实践能力：在真实重大工程BIM模型上做集成验证，理解了检测业务流程与工程合规的分量；"
                  "（4）职业认知：通过企业命题对接与需求分析，体会到“技术服务产业”的含义，找到了个人专业发展与"
                  "国家基础设施数字化需求的结合点。")

    add_h2(doc, "9.5  专业课程与知识应用映射")
    add_body(doc, "项目将多门专业课程知识直接应用于工程实现，课程知识与项目应用的映射关系如表 9-3 所示，"
                  "体现了“学以致用、用以促学”的人才培养路径。")
    add_tbl(doc, "表 9-3  专业课程与知识应用映射表",
            ["专业课程", "核心知识点", "在本项目中的应用"],
            [["桥梁工程", "桥梁结构体系与构件组成", "检测对象划分、16 类参数化构件库与病害定位路由设计"],
             ["土木工程材料", "混凝土病害机理与表观特征", "裂缝、剥落、露筋等六类损伤的特征定义与判据"],
             ["计算机视觉/数字图像处理", "图像滤波、边缘检测、形态学运算",
              "免模型五路 CV 掩码融合算法设计与实现"],
             ["机器学习与深度学习", "目标检测原理与模型评估", "YOLOv8n 训练、调参与 mAP 指标评估"],
             ["Python 程序设计", "桌面应用与算法开发", "BIMBase 插件、算法模块与报告工具的全系统实现"],
             ["数据库与软件工程", "数据管理与软件架构设计", "病害档案 JSON 数据规范与插件分层架构设计"]])

    add_h2(doc, "9.6  价值引领与社会责任")
    add_body(doc, "桥梁安全不是小事，它连着千万人的出行。我们愿意把学到的本事用在桥梁运维这件实实在在的事上，"
                  "以青年学子的方式参与交通强国建设。这份心意，落在三个具体的地方：")
    add_body(doc, "（1）家国情怀：主动选用国产 BIMBase 三维图形引擎做自主可控的探索——把个人的技术成长，"
                  "融进国家关键软件自主化与交通强国战略的需要里；")
    add_body(doc, "（2）工匠精神：指标如实写、不夸大——基线模型 mAP50 约 0.336 就写 0.336，预期指标逐处标明"
                  "口径，测试数据与原始记录全程留痕、经得起查验；")
    add_body(doc, "（3）社会责任：坚持轻量化、低成本的路线，让基层管养单位用得起、用得上——好的检测工具，"
                  "不该只属于预算充足的大单位，我们以普惠的数字化工具服务公共出行安全。")


# ---------------------------------------------------------------------------
# 十、风险分析
# ---------------------------------------------------------------------------

def build_ch10(doc):
    add_h1(doc, "十、风险分析")

    add_h2(doc, "10.1  技术风险")
    add_body(doc, "风险分析：当前基线模型mAP50约0.336、mAP50-95约0.085，距工程实用水平尚有差距；微裂缝等"
                  "小目标损伤识别难度大；复杂光照、遮挡与表面污渍可能引起误检漏检；尺寸量化与定位精度尚待实测"
                  "验证。")
    add_body(doc, "应对措施：（1）按既定五条路线提升模型——数据增强、更大骨干网络迁移学习、半监督学习、"
                  "补充标注与类别均衡采样、小目标特征层优化；（2）保留免模型五路CV融合作为无模型环境的兜底"
                  "方案；（3）量化与定位环节采用预期口径管理，测试完成后以实测数据如实回填；（4）系统定位"
                  "为辅助决策工具，全部输出由专业人员复核，从机制上控制技术风险外溢。")

    add_h2(doc, "10.2  市场与推广风险")
    add_body(doc, "风险分析：检测行业存在既有软件生态与用户习惯壁垒，新工具导入需要培训与流程适配成本；"
                  "基层单位预算有限，付费意愿需要培育；同类AI检测创业团队与大厂行业方案可能形成竞争。")
    add_body(doc, "应对措施：（1）依托国产BIMBase引擎生态对接行业用户，同时保持算法层与平台层解耦，预留多"
                  "平台适配能力；（2）坚持轻量化部署路线，普通笔记本与消费级无人机即可运行，降低试用门槛；"
                  "（3）以“插件授权＋检测服务＋平台订阅”组合模式适配不同付费能力的用户；（4）以真实工程案例"
                  "与如实指标建立可信度，差异化定位基层市场，避免与大型商业软件正面竞争。")

    add_h2(doc, "10.3  合规与数据风险")
    add_body(doc, "风险分析：检测数据涉及实际工程信息，存在授权与保密要求；AI输出若被误用为正式检测结论，"
                  "存在合规风险；公开数据集与开源组件的使用需遵守各自许可协议。")
    add_body(doc, "应对措施：（1）涉及实际工程图像、检测报告、企业数据及人员信息时，依法取得授权或进行脱敏"
                  "处理后方可使用；（2）在全系统与全部文档中明确“辅助决策工具”定位，不替代依法开展的定期检测、"
                  "特殊检测、荷载试验和结构安全评估，正式成果由具备资质的专业人员复核签认；（3）建立知识产权"
                  "合规清单，公开数据集与开源组件按许可规范使用并标注来源（完整声明见附录四）。")


# ---------------------------------------------------------------------------
# 附录
# ---------------------------------------------------------------------------

CODE_PHOTO_BBOX = '''def photo_bbox_to_shadow(face: "FaceInfo", bbox: Tuple[float, float, float, float],
                         photo_w: int, photo_h: int, disease_type: str) -> "ShadowRegion":
    """将照片上的病害 bbox 按"等比铺满整面"映射为面上的阴影区域。

    假设照片取景范围≈目标面：照片 X → 面 U 方向，照片 Y（向下）→ 面 V 方向（向上取反）。
    """
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)

    u = (cx / photo_w - 0.5) * face.width
    v = (0.5 - cy / photo_h) * face.height
    w = bw / photo_w * face.width
    h = bh / photo_h * face.height

    color = DISEASE_COLOR_MAP.get(disease_type, _FALLBACK_COLOR)
    return ShadowRegion(
        local_u=u,
        local_v=v,
        width=w,
        height=h,
        disease_type=disease_type,
        color_rgb=color,
    )'''

CODE_SHADOW_WORLD = '''def shadow_to_world(self, face: FaceInfo, shadow: ShadowRegion,
                    thickness: float = 2.0) -> Tuple[float, float, float, float, float, float, str]:
    """将面上的阴影区域转换为世界坐标中的放置参数。"""
    # 薄片中心 = 面中心 + u * u_axis + v * v_axis + 法向偏移（贴紧表面外侧）
    offset = 2.0   # 沿法向偏移 2mm，避免与构件表面重叠（z-fighting）
    cx = (face.center[0] + shadow.local_u * face.u_axis[0]
          + shadow.local_v * face.v_axis[0] + face.normal[0] * offset)
    cy = (face.center[1] + shadow.local_u * face.u_axis[1]
          + shadow.local_v * face.v_axis[1] + face.normal[1] * offset)
    cz = (face.center[2] + shadow.local_u * face.u_axis[2]
          + shadow.local_v * face.v_axis[2] + face.normal[2] * offset)

    # 尺寸映射：根据面的 plane 类型决定 width/height/thickness 在世界坐标中的轴向
    if face.plane == 'xz':
        return cx, cy, cz, shadow.width, shadow.height, thickness, 'xz'
    elif face.plane == 'yz':
        return cx, cy, cz, shadow.width, shadow.height, thickness, 'yz'
    else:   # 'xy' or others
        return cx, cy, cz, shadow.width, shadow.height, thickness, 'xy' '''.rstrip()

CODE_DIMENSION = '''def calc_scale(ref_length_mm: float, bbox: Tuple[float, float, float, float]) -> Optional[float]:
    """根据参照物框计算照片像素比例（mm/px），取框长边计算。"""
    try:
        ref = float(ref_length_mm)
        x1, y1, x2, y2 = (float(v) for v in bbox)
    except (TypeError, ValueError):
        return None
    if ref <= 0:
        return None
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    long_edge = max(w, h)
    if long_edge <= 0:
        return None
    return ref / long_edge


def box_dimensions(bbox, scale: Optional[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """计算病害框的几何尺寸，返回 (length_mm, width_mm, area_mm2)；未标定时均为 None。"""
    if scale is None:
        return None, None, None
    s = float(scale)
    x1, y1, x2, y2 = (float(v) for v in bbox)
    if s <= 0:
        return None, None, None
    w = abs(x2 - x1)
    h = abs(y2 - y1)
    if w <= 0 or h <= 0:
        return None, None, None
    length_mm = max(w, h) * s
    width_mm = min(w, h) * s
    area_mm2 = w * h * s * s   # 外接矩形面积，真实病害面积偏小
    return length_mm, width_mm, area_mm2'''

CODE_CV_FIVE = '''def _method_crack(gray: np.ndarray) -> np.ndarray:
    """黑帽变换：检测细长裂缝"""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    _, mask = cv2.threshold(blackhat, 8, 255, cv2.THRESH_BINARY)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    return mask


def _method_adaptive(gray: np.ndarray) -> np.ndarray:
    """多尺度自适应阈值：检测不同大小的暗区"""
    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)
    combined = np.zeros((h, w), dtype=np.uint8)
    for bs, c in [(31, 5), (51, 10), (71, 15)]:
        mask = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, bs, c)
        combined = cv2.bitwise_or(combined, mask)
    return combined


def _method_kmeans(img: np.ndarray) -> np.ndarray:
    """K-Means 颜色聚类：检测颜色明显异常的区域（最暗/最亮类）"""
    small = cv2.resize(img, None, fx=0.5, fy=0.5)
    pixels = small.reshape((-1, 3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    lab_centers = cv2.cvtColor(
        centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1, 3)
    lum = lab_centers[:, 0]
    mask_dark = (labels.reshape(small.shape[:2]) == int(np.argmin(lum))).astype(np.uint8) * 255
    mask_bright = (labels.reshape(small.shape[:2]) == int(np.argmax(lum))).astype(np.uint8) * 255
    mask = cv2.resize(cv2.bitwise_or(mask_dark, mask_bright),
                      (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
    return mask


def _method_texture(gray: np.ndarray) -> np.ndarray:
    """局部纹理差异：检测剥落露骨料等粗糙区域"""
    mean = cv2.blur(gray.astype(np.float32), (15, 15))
    mean_sq = cv2.blur(gray.astype(np.float32) ** 2, (15, 15))
    std = np.sqrt(np.maximum(mean_sq - mean ** 2, 0))
    diff = std - cv2.blur(std, (41, 41))
    mask = np.zeros(gray.shape, dtype=np.uint8)
    mask[diff > np.percentile(diff, 78)] = 255
    return mask


def _method_edge(gray: np.ndarray) -> np.ndarray:
    """边缘密度：检测有明显边界的病害区域"""
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 120)
    edge_density = cv2.boxFilter(edges.astype(np.float32), -1, (25, 25), normalize=True)
    mask = np.zeros(gray.shape, dtype=np.uint8)
    mask[edge_density > np.percentile(edge_density, 88)] = 255
    return mask'''


def build_appendices(doc):
    add_h1(doc, "附录一  知识产权与成果证明")
    add_body(doc, "（1）软件著作权：《智检桥安桥梁表观损伤智能检测系统 V1.0》【占位：受理通知书待申请取得后"
                  "替换】；")
    add_body(doc, "（2）软件著作权：《桥梁数字孪生在线展示平台 V1.0》【占位：受理通知书待申请取得后替换】；")
    add_body(doc, "（3）源码仓库：GitHub 开源仓库 https://github.com/baiyu233135/BIMBasePluginCollection ，"
                  "包含插件、算法与数字孪生平台全部源码，可公开查验；")
    add_body(doc, "（4）企业合作证明：【待补充】企业试用证明与合作说明材料待对接后补充，本说明书不作虚构"
                  "陈述；")
    add_body(doc, "（5）数据集与第三方组件：GYU-DET、CODEBRIM 公开数据集按其各自许可协议使用；BIMBase、"
                  "pyp3d、PyTorch、ultralytics（YOLOv8）、OpenCV、PyQt5、python-docx、Qwen-VL、three.js 等"
                  "第三方平台与开源组件均按其授权方式合规使用。")

    add_h1(doc, "附录二  常泰长江大桥参数化构件清单")
    add_body(doc, "常泰长江大桥BIM参数化模型共包含16类参数化构件：上部结构7项（主塔、侧面钢桁架、工字钢梁、"
                  "斜拉索、支座、自密实混凝土层及隔离层、轨道底座）、下部结构3项（门式桥墩、承台及桩基、扩大"
                  "基础）、附属设施6项（新泽西护栏、防撞护栏、轨道、接触网、路面及交通标线、铁路封闭网）。"
                  "全部构件均为原创参数化构件，每个构件有效可调参数不少于4个，参数摘自组件库源码。完整清单"
                  "（含主要可调参数与病害定位路由）见图 3-4。")

    add_h1(doc, "附录三  核心代码节选")
    add_body(doc, "本附录节选系统核心算法的真实源码（省略导入与常量变定义），完整代码见 GitHub 仓库。")
    add_code_block(doc, "代码 附3-1  解析式面投影：照片检测框→面局部阴影区域"
                        "（桥梁病害识别/face_projection.py 第 60～95 行）",
                   CODE_PHOTO_BBOX)
    add_code_block(doc, "代码 附3-2  解析式面投影：面局部阴影→世界坐标（含 2mm 法向偏移防闪面）"
                        "（桥梁病害识别/face_projection.py 第 227～255 行）",
                   CODE_SHADOW_WORLD)
    add_code_block(doc, "代码 附3-3  像素—物理尺度换算与病害尺寸计算"
                        "（桥梁病害识别/dimension_utils.py 第 20～74 行）",
                   CODE_DIMENSION)
    add_code_block(doc, "代码 附3-4  免模型五路 CV 掩码融合：五路检测方法"
                        "（桥梁病害识别/cv_anomaly_detector.py 第 58～132 行）",
                   CODE_CV_FIVE)

    add_h1(doc, "附录四  成果应用边界与数据合规声明")
    add_body(doc, "（1）功能定位：本系统为桥梁表观损伤智能检测的数字化辅助决策工具，其输出结果为检测工作提供"
                  "辅助参考，不替代依法开展的定期检测、特殊检测、荷载试验和结构安全评估，不构成对桥梁结构安全"
                  "的最终判定；正式检测成果必须由具有相应资质的专业人员复核确认并签认；")
    add_body(doc, "（2）可解释可复核：系统输出的损伤识别结果、尺寸数据和定位信息均保留中间过程数据，具备"
                  "依据可查、过程可解释和人工可复核的特征；模型训练曲线、PR曲线、混淆矩阵及各项测试脚本与"
                  "原始记录全部归档，可备查验；")
    add_body(doc, "（3）数据合规与脱敏：项目在数据采集与使用过程中严格遵守相关法律法规；涉及实际工程图像、"
                  "检测报告、企业数据及人员信息时，依法取得授权或进行脱敏处理后方可使用；对外展示与参赛材料"
                  "中不出现未授权的工程敏感信息；")
    add_body(doc, "（4）真实性承诺：本说明书全部技术指标如实呈现——基线模型mAP50约0.336、mAP50-95约0.085为"
                  "真实实测结果；尺寸量化精度、定位精度与检测耗时为预期口径，已逐处标注，测试完成后以实测数据"
                  "如实回填；团队成员、指导教师与企业证明材料待补充处均已明确标注，无任何虚构陈述。本团队承诺"
                  "成果真实合法，不侵犯他人知识产权，接受评审专家与命题企业查验。")

    add_h1(doc, "附录五  需求调研一手资料包")
    add_body(doc, "本附录收录团队开展需求调研使用的一手资料工具：调研问卷（附 5-1）、企业访谈提纲（附 5-2）"
                  "与调研纪要记录表模板（附 5-3）。实际调研回收的问卷、访谈记录与纪要原件，扫描后作为佐证材料"
                  "归入本附录补入，与第九章 9.4 调研记录联动。团队承诺调研过程真实，未开展的调研不虚构、不杜撰。")

    add_h2(doc, "附 5-1  桥梁检测数字化需求调研问卷（检测单位版）")
    add_body(doc, "填写说明：请在“□”内打“√”；标注“可多选”的题目可选择多项；填写约需 5 分钟。", size=12)
    add_body(doc, "1. 贵单位性质：□国有检测企业　□民营检测企业　□科研院所　□管养单位　□其他＿＿＿＿")
    add_body(doc, "2. 贵单位年均检测桥梁数量：□50 座以下　□50～200 座　□200～500 座　□500 座以上")
    add_body(doc, "3. 目前表观损伤检测主要方式（可多选）：□人工抵近目视　□桥检车　□无人机影像＋人工判读　"
                  "□无人机影像＋智能识别　□其他＿＿＿＿")
    add_body(doc, "4. 巡检照片的管理与归档方式：□人工文件夹分类　□按项目表格登记　□专业检测管理系统　"
                  "□无固定方式")
    add_body(doc, "5. 损伤尺寸测量方式：□现场人工量测（卷尺/裂缝卡）　□照片估读　□图像软件辅助　□三维扫描")
    add_body(doc, "6. 病害位置记录方式：□文字描述（跨号/墩号）　□平面示意草图　□BIM/GIS 系统标注　"
                  "□其他＿＿＿＿")
    add_body(doc, "7. 一份常规检测报告的内业编制耗时约为：□1 天以内　□1～3 天　□3～7 天　□7 天以上")
    add_body(doc, "8. 对 AI 辅助识别病害的接受度：□愿意试用　□观望，需看准确率　□暂不需要　□有顾虑"
                  "（请说明）＿＿＿＿")
    add_body(doc, "9. 对“病害三维定位到构件”功能的需求程度：□非常需要　□有一定需要　□一般　□不需要")
    add_body(doc, "10. 期望智能检测工具优先具备的功能（可多选）：□病害自动识别　□尺寸自动量化　□三维定位"
                    "归档　□报告自动生成　□多期对比分析　□离线可用")

    add_h2(doc, "附 5-2  企业访谈提纲")
    add_body(doc, "（1）贵单位桥梁检测业务流程中，最耗时、最易出错的环节是什么？")
    add_body(doc, "（2）目前使用了哪些数字化工具？存在哪些不足？")
    add_body(doc, "（3）检测病害数据如何衔接养护决策与加固设计？是否存在数据断链？")
    add_body(doc, "（4）对 AI 识别准确率的最低可接受要求是什么？哪些类型的误判最不能接受？")
    add_body(doc, "（5）对“辅助决策工具、人工复核签认”的合规边界怎么看？")
    add_body(doc, "（6）尺寸量化与三维定位功能对实际业务的帮助有多大？")
    add_body(doc, "（7）贵单位是否愿意试用本系统并提供反馈？倾向于哪种合作形式（试用/检测服务/联合验证）？")
    add_body(doc, "（8）对系统功能与落地形态还有哪些建议？")

    add_h2(doc, "附 5-3  调研纪要记录表（模板）")
    tbl = doc.add_table(rows=4, cols=5)
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(["日期", "调研对象", "调研方式", "调研要点", "佐证材料"]):
        set_cell_text(tbl.rows[0].cells[i], h, bold=True)
        set_cell_shading(tbl.rows[0].cells[i], HEADER_FILL)
    for r in range(1, 4):
        for c in range(5):
            set_cell_text(tbl.rows[r].cells[c], "")
    add_note(doc, "注：每次调研填写一表；佐证材料包括现场照片、录音、回收问卷编号等，扫描归档后与本表"
                  "一一对应。")


# ---------------------------------------------------------------------------
# 主流程与自检
# ---------------------------------------------------------------------------

def main():
    for p in [REF_DOCX, TWIN_IMG]:
        if not os.path.exists(p):
            raise FileNotFoundError("缺少素材: %s" % p)
    extract_ref_media()

    doc = Document()
    setup_page(doc)
    doc.core_properties.title = "智检桥安-命题解决方案（对标版）v4"
    doc.core_properties.author = "智检桥安团队"
    doc.core_properties.subject = "中国国际大学生创新大赛（2026）产业赛道企业命题组"

    build_cover(doc)
    build_abstract(doc)
    build_toc(doc)
    build_response_map(doc)
    build_ch1(doc)
    build_ch2(doc)
    build_ch3(doc)
    build_ch4(doc)
    build_ch5(doc)
    build_ch6(doc)
    build_ch7(doc)
    build_ch8(doc)
    build_ch9(doc)
    build_ch10(doc)
    build_appendices(doc)

    if not os.path.exists(BG_IMG):
        raise FileNotFoundError("缺少背景图: %s" % BG_IMG)
    if not os.path.exists(COVER_BG_IMG):
        raise FileNotFoundError("缺少封面背景图: %s" % COVER_BG_IMG)
    add_page_background(doc, BG_IMG, COVER_BG_IMG)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    doc.save(OUT_PATH)

    # ---------------------------- 自检 ----------------------------
    import re
    check = Document(OUT_PATH)
    para_count = len(check.paragraphs)
    table_count = len(check.tables)
    img_count = len(check.inline_shapes)
    full_text = "\n".join(p.text for p in check.paragraphs)
    for t in check.tables:
        for row in t.rows:
            for c in row.cells:
                full_text += "\n" + c.text

    chapters = ["项目摘要", "命题响应对照与提交物清单", "一、项目概述与设计目标", "二、应用场景",
                "三、系统结构设计", "四、操作说明", "五、核心技术及原理", "六、项目实现与案例验证",
                "七、运行环境", "八、市场与竞争性分析", "九、产教协同与团队协作", "十、风险分析",
                "附录一", "附录二", "附录三", "附录四", "附录五"]
    missing = [c for c in chapters if c not in full_text]

    figs = re.findall(r"图\s*([0-9]+-[0-9]+)", full_text)
    tbls = re.findall(r"表\s*([0-9]+-[0-9]+)", full_text)
    fig_ids = sorted(set(figs))
    tbl_ids = sorted(set(tbls))

    char_total = sum(len(p.text) for p in check.paragraphs)
    for t in check.tables:
        for row in t.rows:
            for c in row.cells:
                char_total += len(c.text)

    print("输出文件:", OUT_PATH)
    print("文件大小: %.1f KB" % (os.path.getsize(OUT_PATH) / 1024.0))
    print("段落数:", para_count, " 表格数:", table_count, " 嵌入图片数:", img_count)
    print("正文字符数(含表格):", char_total, " 估算页数: 约%d页" % (3 + char_total // 550 + img_count // 3))
    print("章节齐全:", "是" if not missing else "否，缺失: %s" % ",".join(missing))
    print("图编号(%d个): %s" % (len(fig_ids), ", ".join(fig_ids)))
    print("表编号(%d个): %s" % (len(tbl_ids), ", ".join(tbl_ids)))
    print("占位统计: 待填写 x%d, 待补充实测数据 x%d, 截图线索 x%d, 【占位】x%d, 【待补充】x%d"
          % (full_text.count("待填写"), full_text.count("待补充实测数据"),
             full_text.count("【截图线索】"), full_text.count("【占位】"), full_text.count("【待补充】")))
    print("诚实性核查: 0.336 ->", "0.336" in full_text, "; 0.085 ->", "0.085" in full_text,
          "; 建设中 ->", full_text.count("建设中"))
    print("v3 事实修订核查: 面投影标定(应0)=%d, 掩膜细化(应1,仅提升方向)=%d, 骨架提取(应1,仅提升方向)=%d"
          % (full_text.count("面投影标定"), full_text.count("掩膜细化"), full_text.count("骨架提取")))
    print("v3 新增口径: nc=7 ->", "nc=7" in full_text, "; 病害损伤同义注 ->",
          "同义" in full_text, "; 外接矩形估算 ->", "外接矩形" in full_text)

    # 图 5-2 图片内容核验：媒体包内应含 思维导图_尺寸计算流程_v2.png 的同内容图片
    import hashlib
    import zipfile as _zf
    target_md5 = hashlib.md5(open(ppt_img("思维导图_尺寸计算流程_v2.png"), "rb").read()).hexdigest()
    zf = _zf.ZipFile(OUT_PATH)
    media_md5 = {m: hashlib.md5(zf.read(m)).hexdigest()
                 for m in zf.namelist() if m.startswith("word/media/") and not m.endswith("/")}
    print("图5-2新图嵌入:", "是" if target_md5 in media_md5.values() else "否")

    # v4 背景图核验：默认页眉与首页页眉各含一个 behindDoc 锚点、两张背景图各嵌入一次
    import zipfile as _zf2
    from docx.oxml.ns import qn as _qn2
    zf2 = _zf2.ZipFile(OUT_PATH)
    bg_md5 = hashlib.md5(open(BG_IMG, "rb").read()).hexdigest()
    cover_md5 = hashlib.md5(open(COVER_BG_IMG, "rb").read()).hexdigest()
    media_all = [m for m in zf2.namelist() if m.startswith("word/media/") and not m.endswith("/")]
    media_md5_all = {m: hashlib.md5(zf2.read(m)).hexdigest() for m in media_all}
    print("媒体 part 总数:", len(media_all))
    print("正文背景图 part 嵌入:", "是" if bg_md5 in media_md5_all.values() else "否")
    print("封面背景图 part 嵌入:", "是" if cover_md5 in media_md5_all.values() else "否")
    sec = check.sections[0]
    hdr_xml = sec.header.part.element.xml if sec.header is not None else ""
    first_hdr_xml = sec.first_page_header.part.element.xml if sec.first_page_header is not None else ""
    print("默认页眉 behindDoc 锚点:", hdr_xml.count('behindDoc="1"'), "个")
    print("首页页眉（封面）behindDoc 锚点:", first_hdr_xml.count('behindDoc="1"'), "个")
    print("首页不同开关:", "开" if sec.different_first_page_header_footer else "关")
    print("页脚页码字段:", "保留" if "PAGE" in sec.footer.part.element.xml else "缺失")


if __name__ == "__main__":
    main()
