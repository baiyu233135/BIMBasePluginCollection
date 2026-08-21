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


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    create_fence_icon(os.path.join(base, "铁路封闭网.ico"), (0, 150, 60, 255))
    create_fence_icon(os.path.join(base, "铁路封闭网_原版.ico"), (200, 120, 0, 255))
    print("图标已生成：铁路封闭网.ico（绿）、铁路封闭网_原版.ico（橙）")
