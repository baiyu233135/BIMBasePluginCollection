# -*- coding: utf-8 -*-
"""隧道病害识别效果展示脚本。

用统一模型 disease_yolov8n.pt 对 by_disease 下全部原图跑推理，
输出带检测框的标注图（PIL 绘制，支持中文），并生成 HTML 画廊页。
"""
import html
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO

BASE = Path(__file__).resolve().parent.parent  # 隧道病害识别/
MODEL_PATH = BASE / "models" / "disease_yolov8n.pt"
DATA_DIR = BASE / "datasets" / "tunnel_disease" / "by_disease"
OUT_DIR = BASE / "展示效果"
RESULT_DIR = OUT_DIR / "识别结果"
HTML_PATH = OUT_DIR / "index.html"

CONF = 0.25

# 展示用 4 类归并：模型 7 类 -> 裂缝/渗水/剥落/其他
MERGE_MAP = {
    "裂缝": "裂缝",
    "渗水": "渗水",
    "剥落": "剥落",
    "露筋": "其他",
    "蜂窝麻面": "其他",
    "锈蚀": "其他",
    "已修复": "其他",
}

# RGB 颜色（与原插件 BGR 对应转换后）
COLORS = {
    "裂缝": (255, 0, 0),
    "渗水": (0, 0, 255),
    "剥落": (255, 165, 0),
    "其他": (128, 128, 128),
}

FONT_CANDIDATES = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]


def load_font(size):
    for p in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def detect_font():
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def draw_detections(img, boxes, font):
    """在原图副本上画框：矩形 + 顶部文字条「类名 置信度」，中文标注。"""
    img = img.copy()
    draw = ImageDraw.Draw(img)
    for cls_disp, conf, xyxy in boxes:
        color = COLORS[cls_disp]
        x1, y1, x2, y2 = [int(v) for v in xyxy]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=4)
        label = f"{cls_disp} {conf:.2f}"
        # 文字条尺寸
        try:
            lb = draw.textbbox((0, 0), label, font=font)
            tw, th = lb[2] - lb[0], lb[3] - lb[1]
        except AttributeError:
            tw, th = draw.textsize(label, font=font)
        pad = 4
        bar_h = th + 2 * pad
        ty = y1 - bar_h
        if ty < 0:
            ty = y1  # 顶部空间不足时画在框内上沿
        draw.rectangle([x1, ty, x1 + tw + 2 * pad, ty + bar_h], fill=color)
        draw.text((x1 + pad, ty + pad - (lb[1] if hasattr(draw, "textbbox") else 0)),
                  label, fill=(255, 255, 255), font=font)
    return img


def main():
    model = YOLO(str(MODEL_PATH))
    font_path = detect_font()
    print(f"中文字体: {font_path or '未找到，退回默认字体'}")
    font = load_font(22)

    # 收集全部图片（按标注类别分目录）
    records = []
    for label_dir in sorted(DATA_DIR.iterdir()):
        if not label_dir.is_dir():
            continue
        true_cls = label_dir.name
        for img_path in sorted(label_dir.glob("*.jpg")) + sorted(label_dir.glob("*.jpeg")):
            records.append((true_cls, img_path))

    total = len(records)
    print(f"共 {total} 张图片，开始推理 (conf={CONF}) ...")

    stats = {
        "total": total,
        "detected": 0,
        "nodetect": 0,
        "pred_dist": Counter(),   # 按识别（归并后）类别
        "true_dist": Counter(),   # 按原图标注类别
        "match": 0,               # 归并后识别类别 == 原图标注类别（对裂缝/渗水/剥落而言“其他”不参与匹配）
    }
    per_class_records = {}  # true_cls -> list of record dict

    for i, (true_cls, img_path) in enumerate(records, 1):
        # 统一尺寸推理，坐标再映射回原图
        im = Image.open(img_path).convert("RGB")
        orig_w, orig_h = im.size
        results = model.predict(str(img_path), conf=CONF, verbose=False)
        r = results[0]

        boxes = []
        for b in r.boxes:
            raw_name = model.names[int(b.cls)]
            disp = MERGE_MAP.get(raw_name, "其他")
            conf = float(b.conf)
            xyxy = b.xyxy[0].tolist()
            boxes.append((disp, conf, xyxy))

        annotated = draw_detections(im, boxes, font)

        # 图上方条带：报告标注 vs 识别结果
        pred_cls = boxes[0][0] if boxes else None
        if boxes:
            stats["detected"] += 1
            stats["pred_dist"][pred_cls] += 1
        else:
            stats["nodetect"] += 1
        stats["true_dist"][true_cls] += 1
        correct = pred_cls == true_cls
        if correct:
            stats["match"] += 1

        status = ("识别：" + pred_cls + ("✓" if correct else "（实际标注 %s）" % true_cls)) if boxes else "未检出"
        header = f"报告标注：{true_cls} ｜ {status}"

        hf = load_font(26)
        band_h = 44
        canvas = Image.new("RGB", (orig_w, orig_h + band_h), (32, 34, 38))
        canvas.paste(annotated, (0, band_h))
        d = ImageDraw.Draw(canvas)
        try:
            hb = d.textbbox((0, 0), header, font=hf)
            d.text((14, (band_h - (hb[3] - hb[1])) // 2 - hb[1]), header,
                   fill=(120, 220, 130) if (boxes and correct) else (245, 200, 90) if boxes else (240, 110, 110),
                   font=hf)
        except AttributeError:
            d.text((14, 10), header, fill=(120, 220, 130) if (boxes and correct) else (245, 200, 90), font=hf)

        # 输出：按识别类别（无检出归为“未检出”目录）
        out_cls = pred_cls if boxes else "未检出"
        out_dir = RESULT_DIR / out_cls
        out_dir.mkdir(parents=True, exist_ok=True)
        out_name = f"{i:03d}_{true_cls}_{img_path.stem}.jpg"
        canvas.save(out_dir / out_name, quality=92)

        per_class_records.setdefault(true_cls, []).append({
            "img": f"识别结果/{out_cls}/{out_name}",
            "true": true_cls,
            "pred": pred_cls or "未检出",
            "conf": max(b[1] for b in boxes) if boxes else None,
            "count": len(boxes),
            "correct": bool(boxes and correct),
            "detected": bool(boxes),
            "src": img_path.name,
        })

        if i % 20 == 0 or i == total:
            print(f"  进度 {i}/{total}")

    # ---------- 统计打印 ----------
    det = stats["detected"]
    print("\n========== 识别统计 ==========")
    print(f"总图数:            {total}")
    print(f"检出图数:          {det}  ({det/total*100:.1f}%)")
    print(f"无检出图数:        {stats['nodetect']}  ({stats['nodetect']/total*100:.1f}%)")
    print(f"识别与原标注一致:  {stats['match']}  ({stats['match']/total*100:.1f}%)")
    print("按识别类别分布:")
    for c in ["裂缝", "渗水", "剥落", "其他", "未检出"]:
        n = stats["pred_dist"].get(c, 0)
        print(f"  {c}: {n}")
    print("按原图标注分布:")
    for c, n in stats["true_dist"].items():
        print(f"  {c}: {n}")

    # ---------- HTML 画廊 ----------
    gen_html(per_class_records, stats)
    print(f"\n画廊页: {HTML_PATH}")
    (OUT_DIR / "stats.json").write_text(json.dumps({
        "total": total, "detected": det, "nodetect": stats["nodetect"],
        "match": stats["match"],
        "pred_dist": dict(stats["pred_dist"]),
        "true_dist": dict(stats["true_dist"]),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def gen_html(per_class, stats):
    det = stats["detected"]
    rate = det / stats["total"] * 100
    match_rate = stats["match"] / stats["total"] * 100
    chips = "".join(
        f'<span class="chip chip-{c}">{c} <b>{stats["pred_dist"].get(c, 0)}</b></span>'
        for c in ["裂缝", "渗水", "剥落", "其他"]
    )
    sections = []
    for true_cls in ["裂缝", "剥落", "渗水"]:
        recs = per_class.get(true_cls, [])
        cards = []
        for r in recs:
            conf_txt = f"{r['conf']:.2f}" if r["conf"] is not None else "—"
            badge = ('<span class="badge ok">识别:' + r["pred"] + " ✓</span>") if r["correct"] else \
                    ('<span class="badge miss">未检出</span>' if not r["detected"] else
                     '<span class="badge warn">识别:' + r["pred"] + "</span>")
            cards.append(f"""
      <figure class="card">
        <a href="{html.escape(r['img'])}" target="_blank">
          <img loading="lazy" src="{html.escape(r['img'])}" alt="{html.escape(r['src'])}">
        </a>
        <figcaption>
          <div class="fname" title="{html.escape(r['src'])}">{html.escape(r['src'])}</div>
          <div class="meta">{badge}<span class="conf">置信度 {conf_txt}</span></div>
        </figcaption>
      </figure>""")
        sections.append(f"""
    <section>
      <h2>报告标注：{true_cls} <span class="sec-count">{len(recs)} 张</span></h2>
      <div class="grid">{''.join(cards)}
      </div>
    </section>""")

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>隧道病害智能识别 · 效果展示</title>
<style>
  :root {{ --bg:#0f1420; --panel:#1a2130; --line:#2a3350; --txt:#e8ecf4; --sub:#9aa5bd; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--txt); font-family: "Microsoft YaHei","微软雅黑",sans-serif; }}
  header {{ padding: 34px 24px 18px; text-align: center; }}
  header h1 {{ font-size: 26px; letter-spacing: 1px; }}
  header p {{ color: var(--sub); margin-top: 6px; font-size: 13px; }}
  .banner {{ display: flex; flex-wrap: wrap; gap: 14px; justify-content: center; margin: 18px auto 8px; max-width: 1200px; padding: 0 16px; }}
  .stat {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 26px; text-align: center; min-width: 130px; }}
  .stat .num {{ font-size: 28px; font-weight: 700; }}
  .stat .lab {{ color: var(--sub); font-size: 12px; margin-top: 4px; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin: 12px 0 4px; }}
  .chip {{ border-radius: 999px; padding: 4px 14px; font-size: 13px; color:#fff; }}
  .chip b {{ margin-left: 4px; }}
  .chip-裂缝 {{ background:#d33; }} .chip-渗水 {{ background:#3355dd; }}
  .chip-剥落 {{ background:#e0912b; }} .chip-其他 {{ background:#7a7f8a; }}
  section {{ max-width: 1400px; margin: 26px auto; padding: 0 18px; }}
  section h2 {{ font-size: 19px; border-left: 4px solid #4c8dff; padding-left: 10px; margin-bottom: 14px; }}
  .sec-count {{ color: var(--sub); font-size: 13px; font-weight: 400; margin-left: 8px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }}
  .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; transition: transform .15s, box-shadow .15s; }}
  .card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 22px rgba(0,0,0,.45); }}
  .card img {{ width: 100%; height: 180px; object-fit: cover; display: block; cursor: zoom-in; }}
  .card figcaption {{ padding: 8px 10px 10px; }}
  .fname {{ font-size: 12px; color: var(--sub); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .meta {{ display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 12px; }}
  .badge {{ border-radius: 6px; padding: 2px 8px; }}
  .badge.ok {{ background: rgba(60,180,90,.18); color:#6fdc8c; }}
  .badge.warn {{ background: rgba(230,180,60,.16); color:#f0c060; }}
  .badge.miss {{ background: rgba(220,70,70,.18); color:#f08080; }}
  .conf {{ color: var(--sub); }}
  footer {{ text-align:center; color: var(--sub); font-size: 12px; padding: 24px 0 34px; }}
</style>
</head>
<body>
<header>
  <h1>隧道病害智能识别 · 效果展示</h1>
  <p>统一模型 YOLOv8n（裂缝 / 渗水 / 剥落 / 其他 四类归并）· 共 {stats['total']} 张隧道定检原图 · 置信度阈值 0.25</p>
</header>
<div class="banner">
  <div class="stat"><div class="num">{stats['total']}</div><div class="lab">总图数</div></div>
  <div class="stat"><div class="num" style="color:#6fdc8c">{det}</div><div class="lab">检出图数 ({rate:.1f}%)</div></div>
  <div class="stat"><div class="num">{stats['match']}</div><div class="lab">识别与标注一致 ({match_rate:.1f}%)</div></div>
  <div class="stat"><div class="num" style="color:#f08080">{stats['nodetect']}</div><div class="lab">未检出</div></div>
</div>
<div class="chips">{chips}</div>
{''.join(sections)}
<footer>生成于本机 · 图片均为检测框标注输出，点击缩略图查看大图</footer>
</body>
</html>"""
    HTML_PATH.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
