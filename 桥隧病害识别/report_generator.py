# -*- coding: utf-8 -*-
"""
桥梁病害诊断报告生成模块

基于python-docx生成Word格式的诊断报告，包含：
- 项目概况
- 构件病害统计
- 每处病害的详细信息（照片、位置、类型、处理建议）
"""

import os
import sys
import locale
from typing import List, Dict, Optional
from datetime import datetime
from collections import Counter

# 强制UTF-8编码（BIMBase的pythonw.exe locale可能不是中文）
try:
    locale.setlocale(locale.LC_ALL, '')
except Exception:
    pass

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    import docx.oxml
    _DOCX_OK = True
except ImportError:
    _DOCX_OK = False

# 日志文件路径（与bridge_disease_debug.log共用，便于排查）
_LOG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "bridge_disease_debug.log"
)


def _log(msg: str):
    """写日志到文件（pythonw.exe中print不可见）"""
    try:
        ts = datetime.now().strftime("%H:%M:%S")
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [REPORTGEN] {msg}\n")
    except Exception:
        pass


# 病害处理建议字典
DISEASE_TREATMENT_ADVICE = {
    "裂缝": {
        "轻微": "建议采用表面封闭法处理，使用环氧树脂或聚氨酯密封材料涂刷。",
        "中等": "建议采用压力灌浆法处理，注入环氧树脂浆液或水泥浆液。",
        "严重": "裂缝较严重，建议进行结构评估，必要时采用粘贴钢板或碳纤维布加固。",
    },
    "剥落": {
        "轻微": "建议清除松动混凝土，采用聚合物修补砂浆进行表面修补。",
        "中等": "建议凿除损坏区域至坚实基层，重新浇筑修补混凝土。",
        "严重": "剥落严重，可能存在钢筋锈蚀，建议全面检测并考虑结构加固。",
    },
    "露筋": {
        "轻微": "建议清除钢筋表面锈迹，涂刷防锈漆后用聚合物砂浆修补保护层。",
        "中等": "建议除锈后采用环氧树脂砂浆或喷射混凝土修复保护层。",
        "严重": "钢筋锈蚀严重，建议评估承载力，必要时更换钢筋或加大截面。",
    },
    "蜂窝麻面": {
        "轻微": "建议表面打磨后用聚合物水泥砂浆修补。",
        "中等": "建议凿除蜂窝区域，用细石混凝土或灌浆料填补。",
        "严重": "蜂窝严重，建议进行质量检测，必要时采取加固措施。",
    },
    "渗水": {
        "轻微": "建议查找渗水点，采用防水涂料或注浆止水。",
        "中等": "建议设置排水系统，对渗水部位进行化学注浆堵漏。",
        "严重": "渗水严重，建议全面排查水源，必要时重做防水层。",
    },
    "锈蚀": {
        "轻微": "建议钢丝刷除锈后涂刷防腐涂料。",
        "中等": "建议喷砂除锈后涂装防腐涂层，定期检查维护。",
        "严重": "锈蚀严重，建议更换受损构件或采用外包型钢加固。",
    },
    "异常区域": {
        "轻微": "图像中存在轻微异常区域，建议现场复核确认是否为裂缝、渗水或表面缺陷。",
        "中等": "图像中存在明显异常区域，建议进一步检测（敲击、裂缝测宽、渗水试验）以确定病害类型和程度。",
        "严重": "图像中存在显著异常区域，建议尽快安排专业检测并制定修复方案。",
    },
}


def _get_severity(confidence: float) -> str:
    """根据置信度判断严重程度（简化规则）"""
    if confidence >= 0.7:
        return "严重"
    elif confidence >= 0.5:
        return "中等"
    else:
        return "轻微"


def _set_cell_border(cell, **kwargs):
    """设置单元格边框"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        edge_data = kwargs.get(edge)
        if edge_data:
            tag = f'w:{edge}'
            element = tcPr.find(qn(tag))
            if element is None:
                element = docx.oxml.OxmlElement(tag)
                tcPr.append(element)
            element.set(qn('w:val'), 'single')
            element.set(qn('w:sz'), str(edge_data.get('sz', 4)))
            element.set(qn('w:space'), '0')
            element.set(qn('w:color'), edge_data.get('color', '000000'))


class ReportGenerator:
    """诊断报告生成器"""

    def __init__(self):
        self.project_name = "桥梁病害检测项目"
        self.bridge_name = "待填写"
        self.inspector = "AI自动检测系统"
        self.inspection_date = datetime.now().strftime("%Y年%m月%d日")
    
    def set_project_info(self, project_name: str = "", bridge_name: str = "", 
                         inspector: str = ""):
        """设置项目信息"""
        if project_name:
            self.project_name = project_name
        if bridge_name:
            self.bridge_name = bridge_name
        if inspector:
            self.inspector = inspector
    
    def generate(self, records: list, output_path: str) -> bool:
        """
        生成Word诊断报告。
        
        Args:
            records: MarkerRecord列表（或含to_dict方法的对象）
            output_path: 输出Word文件路径
        
        Returns:
            是否成功
        """
        if not _DOCX_OK:
            _log("python-docx未安装，无法生成报告")
            return False
        
        try:
            _log("开始生成报告...")
            doc = Document()
            _log("Document() created")
            
            # 设置中文字体
            self._set_chinese_font(doc)
            _log("中文字体设置完成")
            
            # ===== 封面 =====
            self._add_cover(doc)
            _log("封面完成")
            
            # ===== 一、项目概况 =====
            self._add_section_title(doc, "一、项目概况")
            self._add_project_overview(doc, records)
            _log("项目概况完成")
            
            # ===== 二、构件病害统计 =====
            self._add_section_title(doc, "二、构件病害统计")
            self._add_statistics(doc, records)
            _log("统计完成")
            
            # ===== 三、病害详图 =====
            self._add_section_title(doc, "三、病害详图")
            self._add_disease_details(doc, records)
            _log("病害详图完成")
            
            # ===== 四、处理建议汇总 =====
            self._add_section_title(doc, "四、处理建议汇总")
            self._add_treatment_summary(doc, records)
            _log("处理建议完成")
            
            # 保存
            _log(f"准备保存到: {output_path}")
            doc.save(output_path)
            _log(f"报告已生成: {output_path}")
            return True
        
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            _log(f"生成报告失败: {e}\n{err}")
            return False
    
    def _set_chinese_font(self, doc):
        """设置文档默认中文字体"""
        try:
            style = doc.styles['Normal']
            font = style.font
            font.name = '宋体'
            font.size = Pt(12)
            # python-docx 1.2.0: rPr 可能为 None，需手动创建
            rPr = style.element.get_or_add_rPr()
            rFonts = rPr.get_or_add_rFonts()
            rFonts.set(qn('w:eastAsia'), '宋体')
        except Exception as e:
            _log(f"设置中文字体失败: {e}")
    
    def _add_cover(self, doc):
        """添加封面"""
        # 标题
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run("桥梁结构病害诊断报告")
        run.font.size = Pt(26)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x15, 0x65, 0xC0)
        
        doc.add_paragraph()
        
        # 项目信息表格
        info_table = doc.add_table(rows=4, cols=2)
        info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        info_data = [
            ("项目名称", self.project_name),
            ("桥梁名称", self.bridge_name),
            ("检测日期", self.inspection_date),
            ("检测单位", self.inspector),
        ]
        for i, (label, value) in enumerate(info_data):
            row = info_table.rows[i]
            row.cells[0].text = label
            row.cells[1].text = value
            for cell in row.cells:
                cell.paragraphs[0].runs[0].font.size = Pt(14)
                if i == 0:
                    cell.paragraphs[0].runs[0].font.bold = True
        
        doc.add_page_break()
    
    def _add_section_title(self, doc, title: str):
        """添加章节标题"""
        p = doc.add_paragraph()
        run = p.add_run(title)
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0x15, 0x65, 0xC0)
        p.space_after = Pt(12)
    
    def _add_project_overview(self, doc, records):
        """添加项目概况"""
        if not records:
            doc.add_paragraph("本次检测未发现病害。")
            return
        
        # 统计信息
        total_diseases = len(records)
        component_types = set(r.component_type for r in records)
        disease_types = Counter(r.disease_class for r in records)
        
        doc.add_paragraph(f"本次检测共发现 {total_diseases} 处病害，涉及 {len(component_types)} 种构件类型。")
        doc.add_paragraph()
        
        # 病害类型分布
        doc.add_paragraph("病害类型分布：")
        for dtype, count in disease_types.most_common():
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(f"{dtype}: {count} 处")
    
    def _add_statistics(self, doc, records):
        """添加统计表格"""
        if not records:
            doc.add_paragraph("暂无数据。")
            return
        
        # 按构件类型分组统计
        from collections import defaultdict
        comp_stats = defaultdict(lambda: Counter())
        for r in records:
            comp_stats[r.component_type][r.disease_class] += 1
        
        # 创建表格
        headers = ["构件类型", "病害类型", "数量", "严重程度"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = 'Table Grid'
        
        # 表头
        for i, header in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = header
            cell.paragraphs[0].runs[0].font.bold = True
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # 数据行
        for comp_type, diseases in sorted(comp_stats.items()):
            for dtype, count in diseases.most_common():
                row_cells = table.add_row().cells
                row_cells[0].text = comp_type
                row_cells[1].text = dtype
                row_cells[2].text = str(count)
                row_cells[3].text = "-"
                for cell in row_cells:
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    def _add_disease_details(self, doc, records):
        """添加每处病害的详细信息"""
        if not records:
            doc.add_paragraph("暂无数据。")
            return
        
        for idx, r in enumerate(records, 1):
            # 病害编号标题
            p = doc.add_paragraph()
            run = p.add_run(f"病害 #{idx}")
            run.font.size = Pt(14)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0xC6, 0x28, 0x28)
            
            # 信息表格
            severity = getattr(r, "severity", "") or _get_severity(r.confidence)
            info = [
                ("病害类型", r.disease_class),
                ("所属构件", r.component_type),
                ("严重程度", severity),
                ("检测置信度", f"{r.confidence:.1%}"),
                ("检测时间", r.created_at),
            ]
            if getattr(r, "ai_diagnosed", False):
                info.append(("AI 智能诊断", getattr(r, "ai_diagnosis", "") or "已诊断"))

            # 每条记录附带对应的处理建议（按病害类型+严重程度）
            advice_map = DISEASE_TREATMENT_ADVICE.get(r.disease_class, {})
            advice = advice_map.get(severity) or advice_map.get("中等") or ""
            if advice:
                info.append(("处理建议", advice))

            for label, value in info:
                p = doc.add_paragraph(style='List Bullet')
                p.add_run(f"{label}: ").bold = True
                p.add_run(str(value))

            # 插入照片：优先使用带框/标注图，否则使用原图
            image_to_insert = getattr(r, "marked_image_path", "") or r.photo_path
            if image_to_insert and os.path.exists(image_to_insert):
                try:
                    doc.add_picture(image_to_insert, width=Inches(4.0))
                    last_paragraph = doc.paragraphs[-1]
                    last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                except Exception as e:
                    _log(f"插入图片失败 {image_to_insert}: {e}")
            elif r.photo_path and os.path.exists(r.photo_path):
                try:
                    doc.add_picture(r.photo_path, width=Inches(4.0))
                    last_paragraph = doc.paragraphs[-1]
                    last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                except Exception:
                    pass
            
            doc.add_paragraph()  # 间距
    
    def _add_treatment_summary(self, doc, records):
        """添加处理建议汇总"""
        if not records:
            doc.add_paragraph("暂无数据。")
            return
        
        # 按病害类型汇总建议
        from collections import defaultdict
        advice_groups = defaultdict(list)
        for r in records:
            severity = getattr(r, "severity", "") or _get_severity(r.confidence)
            advice = DISEASE_TREATMENT_ADVICE.get(r.disease_class, {}).get(severity, "建议进一步检测评估。")
            advice_groups[r.disease_class].append({
                'component': r.component_type,
                'severity': severity,
                'advice': advice,
            })
        
        for dtype, items in sorted(advice_groups.items()):
            p = doc.add_paragraph()
            run = p.add_run(f"【{dtype}】")
            run.font.bold = True
            run.font.size = Pt(13)
            
            for item in items:
                p = doc.add_paragraph(style='List Bullet')
                p.add_run(f"{item['component']} ({item['severity']}): ").bold = True
                p.add_run(item['advice'])


def generate_report(records: list, output_path: str, 
                    project_name: str = "", bridge_name: str = "") -> bool:
    """便捷函数：一键生成报告"""
    gen = ReportGenerator()
    gen.set_project_info(project_name, bridge_name)
    return gen.generate(records, output_path)
