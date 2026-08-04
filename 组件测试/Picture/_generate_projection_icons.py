# -*- coding: utf-8 -*-
"""生成桥隧投影测试组件图标"""

from PIL import Image, ImageDraw
import os

SIZE = 64


def save_icon(img, path):
    img.save(path, sizes=[(16, 16), (32, 32), (64, 64)])


def create_t_beam_icon(path):
    """T 梁：橙色 T 形截面"""
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(12, 42), (52, 54)], fill=(255, 140, 0, 255))      # 底板
    draw.rectangle([(24, 14), (40, 42)], fill=(255, 140, 0, 255))      # 腹板
    draw.rectangle([(8, 8), (56, 18)], fill=(255, 140, 0, 255))        # 翼缘
    save_icon(img, path)


def create_diaphragm_icon(path):
    """横隔板：青色竖直板"""
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(20, 8), (44, 56)], fill=(0, 180, 180, 255))
    draw.rectangle([(28, 22), (36, 42)], fill=(255, 255, 255, 0))      # 预留孔
    save_icon(img, path)


def create_wet_joint_icon(path):
    """湿接缝：紫色梯形"""
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.polygon([(20, 12), (44, 12), (52, 52), (12, 52)], fill=(128, 0, 255, 255))
    save_icon(img, path)


def create_pier_icon(path):
    """墩柱：灰色圆柱/方柱"""
    img = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(18, 8), (46, 56)], radius=12, fill=(128, 128, 128, 255))
    save_icon(img, path)


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    create_t_beam_icon(os.path.join(base, "投影测试T梁.ico"))
    create_diaphragm_icon(os.path.join(base, "投影测试横隔板.ico"))
    create_wet_joint_icon(os.path.join(base, "投影测试湿接缝.ico"))
    create_pier_icon(os.path.join(base, "投影测试墩柱.ico"))
    print("图标已生成：投影测试T梁.ico、投影测试横隔板.ico、投影测试湿接缝.ico、投影测试墩柱.ico")
