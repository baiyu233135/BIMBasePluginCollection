# -*- coding: utf-8 -*-
"""
从隧道定期检测 Word 报告中结构化提取病害照片并生成两级分类数据集。

数据源：隧道数据源/官新2024隧道定检报告/益阳分公司第六册/XX隧道（附件N）.docx

表格结构（第 3 章各构件小节，标题为 Heading 3，如 "3.1.3 衬砌"）：
  表头：序号 | 位置(桩号) | 病害种类 | 病害描述（可能跨多列） | 照片 | 状况值
  数据行：照片列为引用编号（如 3.1.3.4），"/" 表示无照片；
  表格末尾「典型病害图」行之后，图片单元格的文字即引用编号，通过编号关联取图。
  个别表格表头为空或合并单元格，按「约 6 列、含图片、上方标题为构件名」兜底识别。

输出：
  datasets/tunnel_disease/by_component/{衬砌,路面,洞门,检修道,排水,未分类构件}/*.jpg
  datasets/tunnel_disease/by_disease/{裂缝,渗水,剥落,其他,未分类病害}/*.jpg（硬链接）
  datasets/tunnel_disease/labels.json / labels.csv

不依赖 Microsoft Word COM；跳过 ~$ 锁文件与 .doc（OLE2）旧格式；
附件章「展示图」检测车全景照片不在病害表格内，不解包输出。
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image

# ============================================================
# 配置
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent          # 隧道病害识别/
PROJECT_ROOT = BASE_DIR.parent                              # 仓库根
DEFAULT_SOURCE = PROJECT_ROOT / "隧道数据源" / "官新2024隧道定检报告" / "益阳分公司第六册"
DEFAULT_OUT = BASE_DIR / "datasets" / "tunnel_disease"

# 构件分类：Heading 3 标题（如 "3.1.3 衬砌"）中的构件名 → 归一类
COMPONENT_MAP = {
    "洞口": "洞门",
    "洞门": "洞门",
    "衬砌": "衬砌",
    "路面": "路面",
    "检修道": "检修道",
    "排水": "排水",
}
COMPONENT_CLASS_FALLBACK = "未分类构件"   # 吊顶及预埋件/内装饰/标志标线轮廓标/电缆沟/其他

# 病害归一化（按优先级顺序匹配）
DISEASE_RULES = [
    ("裂缝", ["裂缝"]),
    ("渗水", ["渗水", "湿渍", "干渍"]),
    ("剥落", ["剥落", "掉块"]),
]
DISEASE_CLASS_FALLBACK = "其他"
DISEASE_CLASS_UNPARSED = "未分类病害"

# 构件标题关键词（兜底识别表格用）
COMPONENT_KEYWORDS = list(COMPONENT_MAP.keys()) + ["吊顶", "内装饰", "标志", "电缆沟"]

STAKE_RE = re.compile(r"[A-Za-z]{0,2}K\s*\d+\s*\+\s*\d+(?:\.\d+)?")
REF_RE = re.compile(r"^\s*(\d+\.\d+\.\d+\.\d+)\s*$")
SEQ_RE = re.compile(r"^\s*\d+\s*$")

ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\s]+')


def safe_filename(name: str, max_len: int = 60) -> str:
    """文件名非法字符用下划线替代。"""
    name = ILLEGAL_FILENAME_CHARS.sub("_", str(name)).strip("_")
    return name[:max_len] or "未知"


def norm_disease(raw: str) -> str:
    """病害种类归一化；为空或编号时返回「未分类病害」。"""
    text = (raw or "").strip()
    if not text or REF_RE.match(text) or SEQ_RE.match(text):
        return DISEASE_CLASS_UNPARSED
    for cls, keywords in DISEASE_RULES:
        if any(kw in text for kw in keywords):
            return cls
    return DISEASE_CLASS_FALLBACK


def norm_component(heading_text: str) -> str:
    """从 Heading 3 标题（如 "3.1.3 衬砌"）取得构件归一类。"""
    text = (heading_text or "").strip()
    # 去掉编号前缀，如 "3.1.3"、"6.1.3"
    name = re.sub(r"^\d+(\.\d+)*\s*", "", text)
    for kw, cls in COMPONENT_MAP.items():
        if kw in name:
            return cls
    return COMPONENT_CLASS_FALLBACK


def tunnel_names(doc_filename: str):
    """从 '碧玉岩隧道（附件一）.docx' 解析出 (短名, 全名)。"""
    stem = Path(doc_filename).stem
    m = re.match(r"^(.+?)(隧道)?(?:（附件.+?）|\(附件.+?\))?$", stem)
    short = m.group(1) if m else stem
    return short, (short + "隧道") if not short.endswith("隧道") else short


def cell_text(tc) -> str:
    return "".join(n.text or "" for n in tc.iter(qn("w:t"))).strip()


def cell_images(tc):
    """返回单元格内所有 a:blip 的 r:embed 列表。"""
    return [b.get(qn("r:embed")) for b in tc.findall(".//" + qn("a:blip")) if b.get(qn("r:embed"))]


def grid_positions(tr):
    """计算一行中每个 tc 的起始/结束网格列（考虑 gridSpan）。"""
    spans = []
    col = 0
    for tc in tr.findall(qn("w:tc")):
        span = 1
        gs = tc.find(qn("w:tcPr") + "/" + qn("w:gridSpan"))
        if gs is not None:
            span = int(gs.get(qn("w:val"), "1"))
        spans.append((tc, col, col + span))
        col += span
    return spans


def locate_columns(header_tr):
    """从表头行定位各字段的网格列范围。表头可能为空 → 返回 None 走兜底。"""
    spans = grid_positions(header_tr)
    cols = {}
    for tc, c0, c1 in spans:
        text = cell_text(tc)
        if not text:
            continue
        if "序号" in text and "seq" not in cols:
            cols["seq"] = (c0, c1)
        elif "位置" in text and "stake" not in cols:
            cols["stake"] = (c0, c1)
        elif "病害种类" in text and "disease" not in cols:
            cols["disease"] = (c0, c1)
        elif "照片" in text and "photo" not in cols:
            cols["photo"] = (c0, c1)
        elif "状况值" in text and "condition" not in cols:
            cols["condition"] = (c0, c1)
    if "seq" in cols and "photo" in cols:
        # 病害描述 = 病害种类与照片之间的列
        if "disease" in cols:
            cols["desc"] = (cols["disease"][1], cols["photo"][0])
        return cols
    return None


def get_cell_by_range(row_tr, c0, c1):
    """取一行中落在 [c0, c1) 网格列内的 tc 列表。"""
    out = []
    for tc, t0, t1 in grid_positions(row_tr):
        if t0 >= c0 and t1 <= c1:
            out.append(tc)
    return out


def text_in_range(row_tr, c0, c1) -> str:
    parts = [cell_text(tc) for tc in get_cell_by_range(row_tr, c0, c1)]
    return " ".join(p for p in parts if p).strip()


def is_disease_table(tbl_el, ncols, header_text, heading_text):
    """识别病害汇总表：表头含 照片/状况值，或 约6列+含图+上方为构件标题。"""
    if not tbl_el.findall(".//" + qn("a:blip")):
        return False
    if "照片" in header_text and "状况值" in header_text:
        return True
    if 5 <= ncols <= 12 and any(k in heading_text for k in COMPONENT_KEYWORDS):
        return True
    return False


def extract_refs(text: str):
    """从图片单元格文字提取引用编号列表。处理整体编号、两个编号直接相连
    （如 "3.1.8.23.2.8.2" = 3.1.8.2 + 3.2.8.2）、编号混在其他文字里等情况。"""
    text = (text or "").strip()
    if not text:
        return []
    m = REF_RE.match(text)
    if m:
        return [m.group(1)]
    m = re.match(r"^(\d+\.\d+\.\d+\.\d+)(\d+\.\d+\.\d+\.\d+)$", text)
    if m:
        return [m.group(1), m.group(2)]
    return re.findall(r"\d+\.\d+\.\d+\.\d+", text)


def section_of(ref: str) -> str:
    """引用编号的小节前缀，如 "3.2.8.1" → "3.2.8"。"""
    return ref.rsplit(".", 1)[0]


def extract_from_doc(doc_path: Path, out_component_dir: Path):
    """从单个报告提取病害照片记录。返回 (records, stats)。"""
    short_name, full_name = tunnel_names(doc_path.name)
    stats = {
        "disease_tables": 0,
        "rows_total": 0,
        "extracted": 0,
        "rows_no_image": 0,       # 数据行照片列为 "/" 或编号无对应图片
        "images_unmatched": 0,    # 图片单元格编号无对应数据行
        "images_unsupported": 0,  # EMF/WMF 等 PIL 无法转换的格式
    }
    records = []

    doc = Document(str(doc_path))
    part = doc.part
    body = doc.element.body

    last_heading3 = ""
    last_heading_any = ""

    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, doc)
            st = p.style.name if p.style is not None else ""
            if st.startswith("Heading"):
                txt = p.text.strip()
                last_heading_any = txt
                if st == "Heading 3":
                    last_heading3 = txt
            continue

        if child.tag != qn("w:tbl"):
            continue

        tbl = Table(child, doc)
        ncols = len(tbl.columns)
        rows = child.findall(qn("w:tr"))
        if not rows:
            continue
        header_tr = rows[0]
        header_text = "".join(cell_text(tc) for tc in header_tr.findall(qn("w:tc")))
        heading = last_heading3 or last_heading_any

        if not is_disease_table(child, ncols, header_text, heading):
            continue
        stats["disease_tables"] += 1
        component = norm_component(heading)

        # 1) 收集图片：全表扫描含 blip 的单元格，以单元格文字（引用编号）为键
        ref_to_rids = defaultdict(list)
        orphan_rids = []
        for tc in child.iter(qn("w:tc")):
            rids = cell_images(tc)
            if not rids:
                continue
            refs = extract_refs(cell_text(tc))
            if refs:
                for ref in refs:
                    ref_to_rids[ref].extend(rids)
            else:
                orphan_rids.extend(rids)

        # 2) 解析数据行并关联图片
        cols = locate_columns(header_tr)
        used_refs = set()
        consumed_rids = set()
        table_rows = []   # 本表数据行（含未匹配到图的）
        for tr in rows[1:]:
            if cols:
                seq = text_in_range(tr, *cols["seq"])
                stake_raw = text_in_range(tr, *cols["stake"]) if "stake" in cols else ""
                disease_raw = text_in_range(tr, *cols["disease"]) if "disease" in cols else ""
                photo_ref = text_in_range(tr, *cols["photo"]) if "photo" in cols else ""
                condition = text_in_range(tr, *cols["condition"]) if "condition" in cols else ""
                desc = text_in_range(tr, *cols["desc"]) if "desc" in cols else ""
            else:
                # 表头为空/合并单元格兜底：按单元格文本特征识别
                cells = [cell_text(tc) for tc in tr.findall(qn("w:tc"))]
                cells = [c for c in cells if c]
                if not cells or not SEQ_RE.match(cells[0]):
                    continue
                seq = cells[0]
                stake_raw = next((c for c in cells if STAKE_RE.search(c)), "")
                mref = next((c for c in cells if REF_RE.match(c)), "")
                photo_ref = mref
                nums = [c for c in cells if SEQ_RE.match(c)]
                condition = nums[-1] if len(nums) >= 2 else ""
                disease_raw = next(
                    (c for c in cells if any(k in c for _, kws in DISEASE_RULES for k in kws)),
                    "",
                )
                desc = next(
                    (c for c in cells if len(c) >= 8 and c not in (seq, stake_raw, disease_raw, photo_ref, condition)),
                    "",
                )

            if not SEQ_RE.match(seq or ""):
                continue  # 非数据行（典型病害图行、二级表头等）
            stats["rows_total"] += 1

            m = REF_RE.match(photo_ref.strip())
            ref = m.group(1) if m else None
            rids = ref_to_rids.get(ref, []) if ref else []

            if not rids and orphan_rids:
                # 兜底：图片无编号时按顺序分配给无图数据行
                rids = [orphan_rids.pop(0)]

            if not rids:
                stats["rows_no_image"] += 1
                mstake0 = STAKE_RE.search(stake_raw)
                stake0 = mstake0.group(0).replace(" ", "") if mstake0 else ""
                table_rows.append({
                    "隧道名": full_name, "桩号": stake0, "构件类型": component,
                    "病害原始名": disease_raw, "病害归一类": norm_disease(disease_raw),
                    "病害描述": desc, "状况值": condition,
                    "来源docx文件名": doc_path.name, "_short": short_name,
                    "_rids": [], "_ref": ref, "_seq_raw": seq,
                })
                continue
            used_refs.add(ref)
            consumed_rids.update(rids)

            mstake = STAKE_RE.search(stake_raw)
            stake = mstake.group(0).replace(" ", "") if mstake else safe_filename(stake_raw or "无桩号", 20)
            disease_cls = norm_disease(disease_raw)

            table_rows.append({
                "隧道名": full_name,
                "桩号": stake,
                "构件类型": component,
                "病害原始名": disease_raw or disease_cls,
                "病害归一类": disease_cls,
                "病害描述": desc,
                "状况值": condition,
                "来源docx文件名": doc_path.name,
                "_short": short_name,
                "_rids": rids,
                "_ref": ref,
                "_seq_raw": seq,
            })

        # 3) 恢复配对：源文档编号错乱时（如数据行填 3.1.8.x、图片格填 3.2.8.x），
        #    将同小节前缀的未匹配图片与未匹配数据行按顺序配对
        heading_sec_m = re.match(r"^\s*(\d+\.\d+\.\d+)", heading)
        heading_sec = heading_sec_m.group(1) if heading_sec_m else ""
        leftover_imgs = [
            (ref, rids) for ref, rids in sorted(ref_to_rids.items())
            if ref not in used_refs and heading_sec and section_of(ref) == heading_sec
            and any(rid not in consumed_rids for rid in rids)
        ]
        if leftover_imgs:
            noimg_rows = [r for r in table_rows if not r["_rids"] and r["_ref"]]
            for row, (ref, rids) in zip(noimg_rows, leftover_imgs):
                avail = [rid for rid in rids if rid not in consumed_rids]
                if not avail:
                    continue
                row["_rids"] = avail[:1]
                consumed_rids.update(avail[:1])
                used_refs.add(ref)
                stats["recovered"] = stats.get("recovered", 0) + 1
                stats["rows_no_image"] -= 1
                if not row["桩号"]:
                    row["桩号"] = "无桩号"

        # 4) 无编号孤儿图按顺序补给既无编号又无图的数据行
        need_rows = [r for r in table_rows if not r["_rids"] and not r["_ref"]]
        for row in need_rows:
            while orphan_rids and orphan_rids[0] in consumed_rids:
                orphan_rids.pop(0)
            if not orphan_rids:
                break
            rid = orphan_rids.pop(0)
            row["_rids"] = [rid]
            consumed_rids.add(rid)
            stats["rows_no_image"] -= 1
            stats["recovered"] = stats.get("recovered", 0) + 1
            if not row["桩号"]:
                row["桩号"] = "无桩号"

        for row in table_rows:
            if row["_rids"]:
                row.pop("_ref", None)
                row.pop("_seq_raw", None)
                records.append(row)

        stats["images_unmatched"] += sum(
            1 for ref, rids in ref_to_rids.items()
            if ref not in used_refs and any(rid not in consumed_rids for rid in rids)
        )

    return records, stats


def save_image(blob: bytes, dest: Path, unsupported_counter: list) -> bool:
    """将图片字节写入 dest（统一 .jpg）。EMF/WMF 等不支持格式跳过。"""
    try:
        from io import BytesIO
        with Image.open(BytesIO(blob)) as im:
            im.verify()
        with Image.open(BytesIO(blob)) as im:
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(str(dest), "JPEG", quality=95)
        return True
    except Exception:
        unsupported_counter[0] += 1
        if dest.exists():
            dest.unlink()
        return False


def main():
    ap = argparse.ArgumentParser(description="隧道病害照片结构化提取与两级分类")
    ap.add_argument("--source", default=str(DEFAULT_SOURCE), help="报告目录（默认：官新2024隧道定检报告/益阳分公司第六册）")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="数据集输出目录")
    args = ap.parse_args()

    source_dir = Path(args.source)
    out_dir = Path(args.out)
    by_component_dir = out_dir / "by_component"
    by_disease_dir = out_dir / "by_disease"
    for d in (by_component_dir, by_disease_dir):
        d.mkdir(parents=True, exist_ok=True)

    docx_files = sorted(
        p for p in source_dir.iterdir()
        if p.suffix.lower() == ".docx" and not p.name.startswith("~$")
    )
    skipped_docs = [
        p.name for p in source_dir.iterdir()
        if (p.suffix.lower() == ".doc" or p.name.startswith("~$")) and p.is_file()
    ]
    print(f"[扫描] {source_dir}")
    print(f"[扫描] 待处理 docx: {len(docx_files)} 份；跳过锁文件/.doc: {len(skipped_docs)} 个")
    for n in skipped_docs:
        print(f"        [跳过] {n}")

    all_records = []
    tunnel_stats = {}
    global_idx = 0

    for doc_path in docx_files:
        try:
            records, stats = extract_from_doc(doc_path, by_component_dir)
        except Exception as e:
            print(f"[错误] {doc_path.name}: {e}")
            tunnel_stats[doc_path.name] = {"extracted": 0, "error": str(e)}
            continue

        # 写图片 + 构件分类
        unsupported = [0]
        doc = Document(str(doc_path))
        part = doc.part
        kept = []
        for r in records:
            dest_name = "{}_{}_{}_{:03d}.jpg".format(
                safe_filename(r["_short"], 20),
                safe_filename(r["桩号"], 25),
                safe_filename(r["病害原始名"], 20),
                global_idx + len(kept) + 1,
            )
            comp_dir = by_component_dir / r["构件类型"]
            comp_dir.mkdir(parents=True, exist_ok=True)
            dest = comp_dir / dest_name
            ok_any = False
            for rid in r["_rids"]:
                blob = None
                rel = part.rels.get(rid)
                if rel is not None and not rel.is_external:
                    try:
                        blob = rel.target_part.blob
                    except Exception:
                        blob = None
                if blob and save_image(blob, dest, unsupported):
                    ok_any = True
                    break
            if ok_any:
                r["图片相对路径"] = str(dest.relative_to(out_dir).as_posix())
                kept.append(r)
        stats["extracted"] = len(kept)
        stats["images_unsupported"] = unsupported[0]
        all_records.extend(kept)
        tunnel_stats[doc_path.name] = stats
        print(f"[提取] {doc_path.name}: 表格 {stats['disease_tables']} 张, "
              f"数据行 {stats['rows_total']} 条, 出图 {stats['extracted']} 张 "
              f"(无图行 {stats['rows_no_image']}, 未匹配图 {stats['images_unmatched']}, "
              f"不支持格式 {stats['images_unsupported']})")

    # 按病害分类（硬链接，失败则复制）
    n_linked = 0
    for r in all_records:
        src = out_dir / r["图片相对路径"]
        disease_dir = by_disease_dir / r["病害归一类"]
        disease_dir.mkdir(parents=True, exist_ok=True)
        dst = disease_dir / src.name
        try:
            if not dst.exists():
                os.link(str(src), str(dst))
            n_linked += 1
        except OSError:
            import shutil
            if not dst.exists():
                shutil.copy2(str(src), str(dst))
            n_linked += 1

    # 标签文件
    fields = ["隧道名", "桩号", "构件类型", "病害原始名", "病害归一类",
              "病害描述", "状况值", "图片相对路径", "来源docx文件名"]
    labels_json = {
        "total": len(all_records),
        "component_classes": ["衬砌", "路面", "洞门", "检修道", "排水", COMPONENT_CLASS_FALLBACK],
        "disease_classes": ["裂缝", "渗水", "剥落", DISEASE_CLASS_FALLBACK, DISEASE_CLASS_UNPARSED],
        "records": [{k: r.get(k, "") for k in fields} for r in all_records],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "labels.json", "w", encoding="utf-8") as f:
        json.dump(labels_json, f, ensure_ascii=False, indent=2)
    with open(out_dir / "labels.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for r in all_records:
            w.writerow([r.get(k, "") for k in fields])

    # 统计
    comp_count = defaultdict(int)
    disease_count = defaultdict(int)
    for r in all_records:
        comp_count[r["构件类型"]] += 1
        disease_count[r["病害归一类"]] += 1

    print("\n========== 汇总 ==========")
    print(f"总计提取病害照片: {len(all_records)} 张（按病害分类链接 {n_linked} 张）")
    print("\n[按隧道分布]")
    for name, st in tunnel_stats.items():
        if "error" in st:
            print(f"  {name}: 错误 {st['error']}")
        else:
            print(f"  {name}: {st['extracted']} 张 (表格 {st['disease_tables']}, 数据行 {st['rows_total']}, "
                  f"无图行 {st['rows_no_image']}, 未匹配图 {st['images_unmatched']})")
    print("\n[按构件分布]")
    for k, v in sorted(comp_count.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("\n[按病害分布]")
    for k, v in sorted(disease_count.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print(f"\n[输出] {out_dir / 'labels.json'}")
    print(f"[输出] {out_dir / 'labels.csv'}")
    print("[完成]")


if __name__ == "__main__":
    main()
