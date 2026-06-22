# -*- coding: utf-8 -*-
"""生成组件测试用图标（直线、曲线）"""

from PIL import Image, ImageDraw
import os

SIZE = 64

def create_line_icon(path):
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # 蓝色直线
    draw.line([(12, 52), (52, 12)], fill=(0, 120, 215, 255), width=6)
    img.save(path, sizes=[(16, 16), (32, 32), (64, 64)])

def create_curve_icon(path):
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    # 橙色弧线
    draw.arc([(10, 10), (54, 54)], start=180, end=270, fill=(255, 140, 0, 255), width=6)
    img.save(path, sizes=[(16, 16), (32, 32), (64, 64)])

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    create_line_icon(os.path.join(base, "直线.ico"))
    create_curve_icon(os.path.join(base, "曲线.ico"))
    print("图标已生成：直线.ico、曲线.ico")
