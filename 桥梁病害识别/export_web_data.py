# -*- coding: utf-8 -*-
"""
网站数据导出工具 — 把桥隧病害记录整理成数字孪生网站可直接消费的 JSON 数据包

独立命令行脚本，不依赖 pyp3d / PyQt，仅使用标准库。

用法:
    python export_web_data.py                          # 用默认路径导出
    python export_web_data.py --out 网站数据/data.json # 指定输出文件
    python export_web_data.py --bridge-records xxx.json --tunnel-records yyy.json

输出:
    <out>                    机器可读 JSON 数据包（CIMPro / three.js 直接消费）
    同目录 web_disease_summary.md  人类可读汇总报告
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime

# 项目根目录（本脚本位于 <项目根>/桥梁病害识别/ 下）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, os.pardir))

DEFAULT_BRIDGE_RECORDS = os.path.join(SCRIPT_DIR, "disease_records.json")
DEFAULT_TUNNEL_RECORDS = os.path.join(
    PROJECT_ROOT, "隧道病害识别", "tunnel_disease_records.json")
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "网站数据", "web_disease_data.json")

MISSING_LIST_LIMIT = 20  # 汇总报告中缺失清单最多列出的条数


def _warn(msg):
    print(f"[警告] {msg}", file=sys.stderr)


def _rel_to_root(path):
    """把绝对路径转为相对项目根的路径（正斜杠分隔，便于 Web 使用）。
    无法转换（不在项目根内、相对路径等）时原样返回。"""
    if not path:
        return ""
    norm = os.path.normpath(path)
    try:
        rel = os.path.relpath(norm, PROJECT_ROOT)
        if rel.startswith(os.pardir + os.sep) or rel == os.pardir:
            return path.replace("\\", "/")
        return rel.replace("\\", "/")
    except ValueError:
        return path.replace("\\", "/")


def _to_abs(path):
    """把记录里的路径转为绝对路径（记录里是绝对路径；若是相对路径，
    优先按项目根解析）。"""
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(PROJECT_ROOT, path))


def load_records(path, source_name):
    """加载一个来源的记录文件。文件不存在记 0 条并警告，不报错。"""
    if not os.path.exists(path):
        _warn(f"{source_name}记录文件不存在: {path}（该来源按 0 条处理）")
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        _warn(f"{source_name}记录文件读取失败: {path} ({e})，该来源按 0 条处理")
        return []
    if not isinstance(data, list):
        _warn(f"{source_name}记录文件格式异常（顶层应为数组）: {path}")
        return []
    return data


def convert_record(rec, source):
    """把一条 MarkerRecord dict 转成网站数据包格式。"""
    if not isinstance(rec, dict):
        return None

    # 3D 坐标：marker_x/y/z 缺失或非数值时 position 记为 null
    pos = None
    try:
        mx = rec.get("marker_x")
        my = rec.get("marker_y")
        mz = rec.get("marker_z")
        if mx is not None and my is not None and mz is not None:
            pos = {"x": float(mx), "y": float(my), "z": float(mz)}
    except (TypeError, ValueError):
        pos = None

    # 照片：转相对项目根路径并校验存在性
    photo_rel = _rel_to_root(rec.get("photo_path", ""))
    photo_abs = _to_abs(rec.get("photo_path", ""))
    photo_exists = bool(photo_abs) and os.path.isfile(photo_abs)

    out = {
        "source": source,
        "id": rec.get("record_id", ""),
        "tunnel_or_bridge_name": rec.get("tunnel_or_bridge_name",
                               rec.get("bridge_name",
                               rec.get("tunnel_name", ""))),
        "component": rec.get("component_type", ""),
        "disease": rec.get("disease_class", ""),
        "severity": rec.get("severity", ""),
        "position": pos,
        "bbox": rec.get("bbox", []),
        "photo": photo_rel,
        "photo_exists": photo_exists,
        "created_at": rec.get("created_at", ""),
    }
    # AI 诊断摘要（有则带上）
    if rec.get("ai_diagnosed") and rec.get("ai_diagnosis"):
        out["diagnosis"] = rec.get("ai_diagnosis")

    # 尺寸量化字段（并行开发中的新功能，存在才带上）
    dims = {}
    for key in ("length_mm", "width_mm", "area_mm2"):
        val = rec.get(key)
        if val is not None:
            dims[key] = val
    if dims:
        out["dimensions"] = dims

    return out


def build_stats(diseases):
    """按病害类型 / 严重程度 / 构件统计。"""
    by_disease = {}
    by_severity = {}
    by_component = {}
    for d in diseases:
        for bucket, key in ((by_disease, d["disease"]),
                            (by_severity, d["severity"]),
                            (by_component, d["component"])):
            label = key if key else "未填写"
            entry = bucket.setdefault(label, {"total": 0, "bridge": 0, "tunnel": 0})
            entry["total"] += 1
            entry[d["source"]] += 1
    return {
        "by_disease": by_disease,
        "by_severity": by_severity,
        "by_component": by_component,
    }


def _md_table(bucket, name_col):
    lines = [f"| {name_col} | 总数 | 桥梁 | 隧道 |", "| --- | ---: | ---: | ---: |"]
    for name, e in sorted(bucket.items(), key=lambda kv: -kv[1]["total"]):
        lines.append(f"| {name} | {e['total']} | {e['bridge']} | {e['tunnel']} |")
    return "\n".join(lines)


def write_summary(md_path, meta, diseases, missing_pos, missing_photo):
    lines = []
    lines.append("# 桥隧病害网站数据导出汇总")
    lines.append("")
    lines.append(f"- 导出时间：{meta['exported_at']}")
    lines.append(f"- 记录总数：**{meta['total']}**（桥梁 {meta['bridge_count']} 条，"
                 f"隧道 {meta['tunnel_count']} 条）")
    lines.append(f"- 缺失 3D 坐标记录：{meta['missing_position_count']} 条；"
                 f"照片文件缺失：{meta['missing_photo_count']} 条")
    lines.append(f"- 数据文件：`{os.path.basename(meta['output_json'])}`"
                 f"（与本文件同目录）")
    lines.append("")

    stats = meta["stats_preview"]
    lines.append("## 按病害类型统计")
    lines.append("")
    lines.append(_md_table(stats["by_disease"], "病害类型"))
    lines.append("")
    lines.append("## 按严重程度统计")
    lines.append("")
    lines.append(_md_table(stats["by_severity"], "严重程度"))
    lines.append("")
    lines.append("## 按构件统计")
    lines.append("")
    lines.append(_md_table(stats["by_component"], "构件类型"))
    lines.append("")

    lines.append("## 缺失 3D 坐标的记录"
                 f"（前 {MISSING_LIST_LIMIT} 条，共 {len(missing_pos)} 条）")
    lines.append("")
    if missing_pos:
        lines.append("| id | 来源 | 构件 | 病害 |")
        lines.append("| --- | --- | --- | --- |")
        for d in missing_pos[:MISSING_LIST_LIMIT]:
            lines.append(f"| {d['id']} | {d['source']} | {d['component']} | {d['disease']} |")
    else:
        lines.append("无")
    lines.append("")

    lines.append("## 照片文件缺失的记录"
                 f"（前 {MISSING_LIST_LIMIT} 条，共 {len(missing_photo)} 条）")
    lines.append("")
    if missing_photo:
        lines.append("| id | 来源 | 照片路径 |")
        lines.append("| --- | --- | --- |")
        for d in missing_photo[:MISSING_LIST_LIMIT]:
            lines.append(f"| {d['id']} | {d['source']} | `{d['photo']}` |")
    else:
        lines.append("无")
    lines.append("")

    lines.append("## 数据对接说明（CIMPro 孪大师 / three.js）")
    lines.append("")
    lines.append("### JSON 结构")
    lines.append("")
    lines.append("```json")
    lines.append('{')
    lines.append('  "meta": { ... },        // 导出元信息（见下）')
    lines.append('  "diseases": [ { ... } ],// 病害记录数组，一病一条')
    lines.append('  "stats": { ... }        // 分类统计')
    lines.append('}')
    lines.append("```")
    lines.append("")
    lines.append("- `meta.exported_at`：导出时间；`meta.total` / `bridge_count` / "
                 "`tunnel_count`：记录数")
    lines.append("- `meta.suggested_model`：留给用户填写的项目/模型信息"
                 "（`project` 建议填如 `\"常泰长江大桥\"`）")
    lines.append("- `meta.coordinate_system` / `meta.unit`：坐标说明。"
                 "坐标为 **BIMBase 世界坐标，单位 mm，Y 轴向上**，"
                 "具体坐标系以模型为准。three.js 中 Y 向上、默认单位为米，"
                 "放置标记时需自行缩放（如 `position/1000`）并确认轴向。")
    lines.append("- `diseases[i]` 关键字段：`source`(bridge/tunnel)、`id`、"
                 "`tunnel_or_bridge_name`、`component`(构件类型)、`disease`(病害类型)、"
                 "`severity`、`position:{x,y,z}`（无 3D 坐标时为 `null`）、"
                 "`bbox`（照片像素框）、`photo`（相对项目根的照片路径，"
                 "`photo_exists=false` 表示文件缺失）、`dimensions`"
                 "（可选，`length_mm`/`width_mm`/`area_mm2`）、"
                 "`diagnosis`（可选，AI 诊断摘要）")
    lines.append("")
    lines.append("### 加载示例（three.js）")
    lines.append("")
    lines.append("```js")
    lines.append("fetch('web_disease_data.json')")
    lines.append("  .then(r => r.json())")
    lines.append("  .then(data => {")
    lines.append("    const MM_PER_M = 1000;  // 数据单位为 mm，three.js 按米")
    lines.append("    for (const d of data.diseases) {")
    lines.append("      if (!d.position) continue;          // 无坐标的跳过")
    lines.append("      const p = new THREE.Vector3(")
    lines.append("        d.position.x / MM_PER_M,")
    lines.append("        d.position.y / MM_PER_M,")
    lines.append("        d.position.z / MM_PER_M);")
    lines.append("      const color = d.source === 'bridge' ? 0xff4444 : 0xffa500;")
    lines.append("      const marker = new THREE.Mesh(")
    lines.append("        new THREE.SphereGeometry(0.3, 16, 16),")
    lines.append("        new THREE.MeshBasicMaterial({ color }));")
    lines.append("      marker.position.copy(p);")
    lines.append("      marker.userData = d;   // 整条记录挂到 userData，点击可弹详情")
    lines.append("      scene.add(marker);")
    lines.append("    }")
    lines.append("  });")
    lines.append("```")
    lines.append("")
    lines.append("### CIMPro 孪大师对接")
    lines.append("")
    lines.append("1. 把 `web_disease_data.json` 及照片目录（如 `桥梁病害识别/datasets/`）"
                 "一并放到可访问的 Web 目录或文件服务；")
    lines.append("2. CIMPro 的 Web/API 组件按上述字段取 `position` 放置标记，"
                 "`disease`/`severity`/`dimensions` 做弹窗与筛选；")
    lines.append("3. 若平台坐标系与 BIMBase 不一致（如 Z 向上），"
                 "在加载层做一次轴变换即可。")
    lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(
        description="把桥隧病害记录导出为数字孪生网站可用的 JSON 数据包")
    ap.add_argument("--bridge-records", default=DEFAULT_BRIDGE_RECORDS,
                    help=f"桥梁记录 JSON（默认: {DEFAULT_BRIDGE_RECORDS}）")
    ap.add_argument("--tunnel-records", default=DEFAULT_TUNNEL_RECORDS,
                    help=f"隧道记录 JSON（默认: {DEFAULT_TUNNEL_RECORDS}）")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help=f"输出 JSON 路径（默认: {DEFAULT_OUT}）")
    args = ap.parse_args()

    bridge_raw = load_records(args.bridge_records, "桥梁")
    tunnel_raw = load_records(args.tunnel_records, "隧道")

    diseases = []
    for rec in bridge_raw:
        item = convert_record(rec, "bridge")
        if item:
            diseases.append(item)
    for rec in tunnel_raw:
        item = convert_record(rec, "tunnel")
        if item:
            diseases.append(item)

    missing_pos = [d for d in diseases if d["position"] is None]
    missing_photo = [d for d in diseases if not d["photo_exists"]]

    stats = build_stats(diseases)

    out_abs = os.path.abspath(args.out)
    meta = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generator": "export_web_data.py",
        "project_root": PROJECT_ROOT.replace("\\", "/"),
        "total": len(diseases),
        "bridge_count": len(bridge_raw),
        "tunnel_count": len(tunnel_raw),
        "missing_position_count": len(missing_pos),
        "missing_photo_count": len(missing_photo),
        "unit": "mm",
        "coordinate_system": "BIMBase 世界坐标，Y 轴向上，具体坐标系以模型为准",
        "suggested_model": {
            "project": "",
            "bridge_model": "",
            "tunnel_model": "",
            "note": "留给用户填写，如 project: 常泰长江大桥",
        },
        "output_json": out_abs.replace("\\", "/"),
        "stats_preview": stats,
    }

    package = {"meta": meta, "diseases": diseases, "stats": stats}

    out_dir = os.path.dirname(out_abs)
    os.makedirs(out_dir, exist_ok=True)
    with open(out_abs, "w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)

    md_path = os.path.join(out_dir, "web_disease_summary.md")
    write_summary(md_path, meta, diseases, missing_pos, missing_photo)

    print(f"导出完成: {out_abs}")
    print(f"  桥梁记录: {len(bridge_raw)} 条")
    print(f"  隧道记录: {len(tunnel_raw)} 条")
    print(f"  总计: {len(diseases)} 条（缺失坐标 {len(missing_pos)}，照片缺失 {len(missing_photo)}）")
    print(f"  汇总报告: {md_path}")


if __name__ == "__main__":
    main()
