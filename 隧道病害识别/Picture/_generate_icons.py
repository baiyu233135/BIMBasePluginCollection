# -*- coding: utf-8 -*-
"""
隧道病害识别 / 隧道组件 图标生成脚本（可重复运行）

用法:  python _generate_icons.py
输出:  隧道病害识别.ico (替换现有) / 隧道组件.ico
       多分辨率: 16 / 32 / 48 / 256

设计: 1024x1024 超采样绘制(4x)，LANCZOS 缩小到各尺寸保证边缘平滑。
  - 深蓝竖向渐变圆角方形底
  - 白色隧道拱形轮廓（外拱填充白，内拱填深色，形成衬砌环）
  - 隧道病害识别: 拱顶红色裂缝折线 + 底部蓝色渗水水滴
  - 隧道组件:     拱内深色路面 + 黄色车道虚线 + 两侧壁灯点
"""

import math
import os

from PIL import Image, ImageDraw

W = 256          # 逻辑画布尺寸
S = 4            # 超采样倍数（实际绘制 1024x1024）
OUT_SIZES = [16, 32, 48, 256]

BG_TOP = (30, 64, 124)      # 深蓝（顶）
BG_BOTTOM = (11, 30, 66)    # 深蓝（底）
WHITE = (245, 248, 252, 255)
INTERIOR = (13, 30, 58, 255)    # 隧道洞内深色
RED = (229, 57, 53, 255)        # 裂缝红
DROP = (66, 165, 245, 255)      # 渗水蓝
DROP_HI = (144, 202, 249, 255)
ROAD = (52, 58, 70, 255)        # 路面
LANE = (250, 200, 80, 255)      # 车道线
LAMP = (255, 213, 128, 255)     # 壁灯


def base_canvas():
    """深蓝渐变 + 圆角方形蒙版"""
    img = Image.new("RGBA", (W * S, W * S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (W * S, W * S))
    gd = ImageDraw.Draw(grad)
    for y in range(W * S):
        t = y / (W * S - 1)
        c = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)) + (255,)
        gd.line([(0, y), (W * S, y)], fill=c)
    mask = Image.new("L", (W * S, W * S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W * S - 1, W * S - 1], radius=54 * S, fill=255)
    img.paste(grad, (0, 0), mask)
    return img, ImageDraw.Draw(img)


def draw_tunnel_body(d):
    """白色隧道拱形轮廓，返回洞内区域参数（供细节绘制）"""
    cx, cy = 128, 104          # 拱圆心（逻辑坐标）
    ro, ri = 70, 53            # 外/内拱半径
    yo = 200                   # 拱脚底部
    arc = lambda r: [(cx + r * math.cos(math.pi + i * math.pi / 60),
                      cy + r * math.sin(math.pi + i * math.pi / 60)) for i in range(61)]
    # 外轮廓（左侧壁 -> 半圆拱 -> 右侧壁，底部闭合在 yo）
    d.polygon([(x * S, y * S) for x, y in
               [(cx - ro, yo), (cx - ro, cy)] + arc(ro) + [(cx + ro, yo)]], fill=WHITE)
    # 内轮廓（深色洞内）
    d.polygon([(x * S, y * S) for x, y in
               [(cx - ri, yo), (cx - ri, cy)] + arc(ri) + [(cx + ri, yo)]], fill=INTERIOR)
    return cx, cy, ri, yo


def draw_crack(d, cx, cy):
    """拱顶红色裂缝折线（带一小分叉）"""
    pts = [(cx - 2, cy - 40), (cx - 14, cy - 22), (cx + 2, cy - 6),
           (cx - 12, cy + 12), (cx + 4, cy + 28), (cx - 6, cy + 44)]
    d.line([(x * S, y * S) for x, y in pts], fill=RED, width=6 * S, joint="curve")
    d.line([(x * S, y * S) for x, y in [(cx + 2, cy - 6), (cx + 18, cy + 4), (cx + 12, cy + 16)]],
           fill=RED, width=4 * S, joint="curve")


def draw_drop(d, cx, yo):
    """底部渗水水滴（略压拱脚）"""
    top = yo - 6
    d.polygon([(cx * S, top * S), ((cx - 15) * S, (top + 22) * S), ((cx + 15) * S, (top + 22) * S)],
              fill=DROP)
    d.ellipse([(cx - 15) * S, (top + 12) * S, (cx + 15) * S, (top + 42) * S], fill=DROP)
    d.ellipse([(cx - 8) * S, (top + 18) * S, (cx + 1) * S, (top + 30) * S], fill=DROP_HI)


def draw_road(d, cx, ri, yo):
    """洞内路面 + 车道虚线 + 两侧壁灯"""
    d.rectangle([(cx - ri + 4) * S, (yo - 40) * S, (cx + ri - 4) * S, yo * S], fill=ROAD)
    for yy in range(yo - 36, yo - 4, 12):                       # 中央车道虚线
        d.rectangle([(cx - 3) * S, yy * S, (cx + 3) * S, (yy + 6) * S], fill=LANE)
    for sx in (cx - ri + 13, cx + ri - 13):                     # 两侧壁灯
        d.ellipse([(sx - 4) * S, (yo - 78) * S, (sx + 4) * S, (yo - 70) * S], fill=LAMP)


def build_icon(disease):
    img, d = base_canvas()
    cx, cy, ri, yo = draw_tunnel_body(d)
    if disease:
        draw_crack(d, cx, cy)
        draw_drop(d, cx, yo)
    else:
        draw_road(d, cx, ri, yo)
    return img


def save_icon(img, path):
    big = img.resize((256, 256), Image.LANCZOS)
    big.save(path, format="ICO", sizes=[(s, s) for s in OUT_SIZES])
    print("written:", path, OUT_SIZES)


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    save_icon(build_icon(disease=True), os.path.join(out_dir, "隧道病害识别.ico"))
    save_icon(build_icon(disease=False), os.path.join(out_dir, "隧道组件.ico"))
