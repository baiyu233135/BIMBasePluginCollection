# -*- coding: utf-8 -*-
"""生成组件成品图标（铁路封闭网：护栏网样式；绿色=优化版，橙色=原版对比用）"""

from PIL import Image, ImageDraw
import os

SIZE = 64


def create_fence_icon(path, color):
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # 网片外框
    draw.rectangle([10, 14, 54, 50], outline=color, width=4)
    # 网格线
    for x in (21, 32, 43):
        draw.line([(x, 16), (x, 48)], fill=color, width=2)
    for y in (25, 36):
        draw.line([(12, y), (52, y)], fill=color, width=2)
    # 左右立柱
    draw.line([(8, 8), (8, 58)], fill=color, width=5)
    draw.line([(56, 8), (56, 58)], fill=color, width=5)
    img.save(path, sizes=[(16, 16), (32, 32), (64, 64)])


def create_grooved_plate_icon(path, color):
    """被插板:带凹槽的板"""
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([6, 18, 58, 46], outline=color, width=4)   # 板
    for x in (18, 30, 42):                                     # 凹槽
        draw.line([(x, 22), (x, 42)], fill=color, width=3)
    img.save(path, sizes=[(16, 16), (32, 32), (64, 64)])


def create_toothed_plate_icon(path, color):
    """凸插板:带凸起的板"""
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([6, 12, 58, 28], outline=color, width=4)   # 板
    for x in (14, 29, 44):                                     # 凸起(齿)
        draw.rectangle([x, 28, x + 7, 50], outline=color, width=3)
    img.save(path, sizes=[(16, 16), (32, 32), (64, 64)])


def create_tunnel_icon(path):
    """隧道:深黑底 + 三条白色纵向线(对应组件路面三条设备带)"""
    img = Image.new("RGBA", (SIZE, SIZE), (20, 20, 20, 255))  # 深黑底
    draw = ImageDraw.Draw(img)
    for y in (20, 32, 44):                                     # 三条白线
        draw.line([(8, y), (56, y)], fill=(255, 255, 255, 255), width=4)
    img.save(path, sizes=[(16, 16), (32, 32), (64, 64)])


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    create_fence_icon(os.path.join(base, "铁路封闭网.ico"), (0, 150, 60, 255))
    create_fence_icon(os.path.join(base, "铁路封闭网_原版.ico"), (200, 120, 0, 255))
    create_grooved_plate_icon(os.path.join(base, "被插板.ico"), (60, 110, 180, 255))
    create_toothed_plate_icon(os.path.join(base, "凸插板.ico"), (170, 90, 50, 255))
    create_tunnel_icon(os.path.join(base, "隧道.ico"))
    print("图标已生成：铁路封闭网.ico（绿）、铁路封闭网_原版.ico（橙）、被插板.ico（蓝）、凸插板.ico（棕）、隧道.ico（深黑底白线）")
