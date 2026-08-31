# -*- coding: utf-8 -*-
"""生成 CADBoard 面板三个按钮的图标：CAD画板 / 自动配置环境 / 桥梁病害识别

4 倍超采样绘制后降采样，保证边缘平滑；输出多尺寸 .ico + .png 预览。
旧图标已被 git 跟踪，如需还原：git checkout -- CADBoard/Picture/
"""
from PIL import Image, ImageDraw
import os
import math

S = 4          # 超采样倍数
SIZE = 64 * S  # 绘制画布 256x256


def _u(v):
    """64 单位坐标 -> 画布坐标"""
    return int(round(v * S))


def _new_canvas():
    return Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))


def _save(img, path_wo_ext):
    ico = img.resize((64, 64), Image.LANCZOS)
    ico.save(path_wo_ext + ".ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64)])
    img.resize((64, 64), Image.LANCZOS).save(path_wo_ext + ".png")


def create_cad_board_icon(path_wo_ext):
    """CAD画板：绘图板 + 网格 + 铅笔"""
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    blue = (0, 120, 215, 255)
    light = (190, 220, 245, 255)

    # 板面（圆角矩形）
    d.rounded_rectangle([_u(6), _u(8), _u(58), _u(48)], radius=_u(4),
                        fill=(255, 255, 255, 255), outline=blue, width=_u(3))
    # 网格
    for gx in (16, 26, 36, 46):
        d.line([(_u(gx), _u(12)), (_u(gx), _u(44))], fill=light, width=_u(1))
    for gy in (20, 28, 36):
        d.line([(_u(10), _u(gy)), (_u(54), _u(gy))], fill=light, width=_u(1))
    # 板上的对角线（代表图形）
    d.line([(_u(13), _u(41)), (_u(30), _u(16))], fill=blue, width=_u(2.5))
    d.ellipse([_u(38), _u(14), _u(50), _u(26)], outline=blue, width=_u(2.5))

    # 铅笔（斜跨右下）
    d.line([(_u(26), _u(56)), (_u(50), _u(32))], fill=(255, 140, 0, 255), width=_u(5))
    d.polygon([(_u(50), _u(32)), (_u(54), _u(26)), (_u(46), _u(28))],
              fill=(60, 60, 60, 255))  # 笔尖
    _save(img, path_wo_ext)


def create_setup_env_icon(path_wo_ext):
    """自动配置环境：齿轮 + 对勾"""
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    green = (16, 124, 16, 255)
    cx, cy, r_out, r_in = _u(30), _u(30), _u(20), _u(13)

    # 齿轮：8 齿 + 圆环
    for i in range(8):
        a = math.radians(i * 45)
        tx, ty = cx + r_out * math.cos(a), cy + r_out * math.sin(a)
        d.ellipse([tx - _u(4.5), ty - _u(4.5), tx + _u(4.5), ty + _u(4.5)], fill=green)
    d.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out], fill=green)
    d.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=(255, 255, 255, 0))
    d.ellipse([cx - _u(6), cy - _u(6), cx + _u(6), cy + _u(6)], fill=green)

    # 对勾徽章（右下角）
    bx, by, br = _u(48), _u(48), _u(13)
    d.ellipse([bx - br, by - br, bx + br, by + br], fill=(255, 140, 0, 255),
              outline=(255, 255, 255, 255), width=_u(2))
    d.line([(_u(42.5), _u(48)), (_u(46.5), _u(52.5))], fill=(255, 255, 255, 255), width=_u(3))
    d.line([(_u(46.5), _u(52.5)), (_u(54), _u(42.5))], fill=(255, 255, 255, 255), width=_u(3))
    _save(img, path_wo_ext)


def create_disease_icon(path_wo_ext):
    """桥梁病害识别：桥 + 放大镜"""
    img = _new_canvas()
    d = ImageDraw.Draw(img)
    steel = (80, 100, 120, 255)

    # 桥面
    d.line([(_u(4), _u(26)), (_u(60), _u(26))], fill=steel, width=_u(4))
    # 拱
    d.arc([_u(8), _u(10), _u(56), _u(58)], start=180, end=360, fill=steel, width=_u(3))
    # 吊杆
    for hx in (16, 26, 38, 48):
        d.line([(_u(hx), _u(27)), (_u(hx), _u(38))], fill=steel, width=_u(2))
    # 双墩
    d.rectangle([_u(10), _u(28), _u(14), _u(50)], fill=steel)
    d.rectangle([_u(50), _u(28), _u(54), _u(50)], fill=steel)

    # 放大镜（中央偏右下）
    mx, my, mr = _u(36), _u(40), _u(13)
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr],
              outline=(0, 120, 215, 255), width=_u(4))
    d.line([(_u(45), _u(50)), (_u(55), _u(60))], fill=(0, 120, 215, 255), width=_u(5))
    # 镜片里的"裂缝"
    d.line([(_u(30), _u(35)), (_u(35), _u(40)), (_u(32), _u(45))],
           fill=(220, 40, 40, 255), width=_u(2.5))
    _save(img, path_wo_ext)


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    create_cad_board_icon(os.path.join(base, "CAD画板"))
    create_setup_env_icon(os.path.join(base, "配置环境"))
    create_disease_icon(os.path.join(base, "桥隧识别"))
    print("图标已生成：CAD画板.ico、配置环境.ico、桥隧识别.ico（含 .png 预览）")
