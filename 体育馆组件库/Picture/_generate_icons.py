# -*- coding: utf-8 -*-
"""生成体育馆组件库图标(19 个组件,PIL 线框示意图,64x64,按面板分组配色)"""

from PIL import Image, ImageDraw
import os

SIZE = 64

# 分组配色:屋盖与桁架=钢蓝,看台与座位=绿,外墙=灰,场地与附属=橙
C_ROOF = (60, 110, 180, 255)
C_STAND = (0, 150, 60, 255)
C_WALL = (110, 110, 110, 255)
C_MISC = (200, 120, 0, 255)


def canvas():
    return Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))


def save(img, base, name):
    img.save(os.path.join(base, name + ".ico"), sizes=[(16, 16), (32, 32), (64, 64)])


# ---------- 屋盖与桁架 ----------

def icon_上盖张弦梁(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.arc([8, 6, 56, 42], 180, 360, fill=c, width=4)          # 上弦(拱)
    d.arc([8, 22, 56, 58], 0, 180, fill=c, width=3)           # 下弦(拉索,下挠)
    for x in (20, 32, 44):                                     # 撑杆
        d.line([(x, 24), (x, 40)], fill=c, width=3)
    d.line([(8, 14), (8, 40)], fill=c, width=4)               # 端柱
    d.line([(56, 14), (56, 40)], fill=c, width=4)
    return img


def icon_边屋盖(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(6, 42), (26, 20), (58, 20)], fill=c, width=4)    # 斜屋面
    d.line([(6, 50), (26, 28), (58, 28)], fill=c, width=3)    # 板厚
    d.line([(6, 42), (6, 50)], fill=c, width=3)
    d.line([(58, 20), (58, 28)], fill=c, width=3)
    return img


def icon_中屋盖(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([8, 22, 56, 42], outline=c, width=4)          # 平屋面
    d.line([(8, 32), (56, 32)], fill=c, width=2)              # 分格
    d.line([(24, 22), (24, 42)], fill=c, width=2)
    d.line([(40, 22), (40, 42)], fill=c, width=2)
    return img


def icon_中部桁架(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(8, 18), (56, 18)], fill=c, width=4)              # 上弦
    d.line([(8, 46), (56, 46)], fill=c, width=4)              # 下弦
    pts = [(8, 46), (16, 18), (24, 46), (32, 18), (40, 46), (48, 18), (56, 46)]
    d.line(pts, fill=c, width=3)                              # 腹杆锯齿
    return img


def icon_边部桁架(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(8, 46), (56, 46)], fill=c, width=4)              # 下弦
    d.line([(8, 30), (56, 18)], fill=c, width=4)              # 斜上弦
    d.line([(8, 30), (8, 46)], fill=c, width=3)
    pts = [(8, 46), (20, 26), (24, 46), (36, 22), (40, 46), (52, 19), (56, 46)]
    d.line(pts, fill=c, width=3)
    return img


def icon_行人架(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(8, 30), (56, 30)], fill=c, width=5)              # 走道板
    d.line([(8, 20), (56, 20)], fill=c, width=2)              # 扶手
    for x in (14, 32, 50):                                     # 支腿
        d.line([(x, 30), (x, 52)], fill=c, width=4)
    return img


# ---------- 看台与座位 ----------

def _steps(d, c, n, x0=10, y0=52, x1=56, y1=14):
    """直段阶梯:n 级,从 (x0,y0) 走到 (x1,y1)"""
    w = (x1 - x0) / n; h = (y0 - y1) / n
    pts = [(x0, y0)]
    for i in range(n):
        x = x0 + w * i
        pts += [(x, y0 - h * i - h), (x + w, y0 - h * i - h)]
    d.line(pts, fill=c, width=4)
    d.line([(x0, y0), (x1, y0)], fill=c, width=3)             # 地面线


def icon_直段下看台(c):
    img = canvas(); d = ImageDraw.Draw(img)
    _steps(d, c, 3, y1=26)
    return img


def icon_直段上看台(c):
    img = canvas(); d = ImageDraw.Draw(img)
    _steps(d, c, 6, y1=10)
    return img


def _arc_steps(d, c, n, r0, r1):
    """曲段阶梯:n 级同心弧"""
    for i in range(n):
        r = r0 + (r1 - r0) * i / max(1, n - 1)
        b = [32 - r, 32 - r, 32 + r, 32 + r]
        d.arc(b, 200, 340, fill=c, width=4)


def icon_曲段下看台(c):
    img = canvas(); d = ImageDraw.Draw(img)
    _arc_steps(d, c, 3, 10, 26)
    return img


def icon_曲段上看台(c):
    img = canvas(); d = ImageDraw.Draw(img)
    _arc_steps(d, c, 6, 8, 30)
    return img


def icon_座位(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(16, 40), (46, 40)], fill=c, width=5)             # 坐面
    d.line([(42, 16), (42, 40)], fill=c, width=5)             # 靠背
    d.line([(20, 40), (20, 54)], fill=c, width=4)             # 前腿
    d.line([(42, 40), (42, 54)], fill=c, width=4)             # 后腿
    return img


# ---------- 外墙 ----------

def icon_外墙_有门(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([10, 8, 54, 56], outline=c, width=4)          # 墙
    d.rectangle([27, 34, 39, 56], outline=c, width=3)         # 门洞
    return img


def icon_外墙_无门(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([10, 8, 54, 56], outline=c, width=4)
    d.line([(24, 8), (24, 56)], fill=c, width=2)              # 分缝
    d.line([(40, 8), (40, 56)], fill=c, width=2)
    return img


def icon_外墙_斜(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.polygon([(18, 56), (30, 8), (52, 8), (40, 56)], outline=c, width=4)  # 斜墙
    return img


# ---------- 场地与附属 ----------

def icon_足球场(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([6, 14, 58, 50], outline=c, width=4)          # 场地
    d.line([(32, 14), (32, 50)], fill=c, width=2)             # 中线
    d.ellipse([25, 25, 39, 39], outline=c, width=3)           # 中圈
    return img


def icon_大屏及支架(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([12, 8, 52, 30], outline=c, width=4)          # 大屏
    d.line([(24, 30), (24, 54)], fill=c, width=4)             # 左支腿
    d.line([(40, 30), (40, 54)], fill=c, width=4)             # 右支腿
    d.line([(18, 54), (46, 54)], fill=c, width=3)             # 底梁
    return img


def icon_外楼梯(c):
    img = canvas(); d = ImageDraw.Draw(img)
    pts = [(8, 54), (8, 46), (16, 46), (16, 38), (24, 38), (24, 30),
           (32, 30), (32, 22), (40, 22), (40, 14), (48, 14), (48, 6), (56, 6)]
    d.line(pts, fill=c, width=4)                              # 踏步
    d.line([(8, 58), (56, 58)], fill=c, width=3)              # 地面
    return img


def icon_外栏杆(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(6, 18), (58, 18)], fill=c, width=4)              # 扶手
    for x in (12, 24, 36, 48):                                 # 立杆
        d.line([(x, 18), (x, 50)], fill=c, width=3)
    d.line([(6, 50), (58, 50)], fill=c, width=3)              # 地线
    return img


def icon_无障碍坡道(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(8, 46), (40, 24)], fill=c, width=5)              # 坡道
    d.line([(40, 24), (56, 24)], fill=c, width=5)             # 平台
    d.line([(8, 54), (56, 54)], fill=c, width=3)              # 地面
    d.line([(40, 24), (40, 54)], fill=c, width=2)             # 平台支撑
    return img


ICONS = [
    ("上盖张弦梁", icon_上盖张弦梁, C_ROOF),
    ("边屋盖", icon_边屋盖, C_ROOF),
    ("中屋盖", icon_中屋盖, C_ROOF),
    ("中部桁架", icon_中部桁架, C_ROOF),
    ("边部桁架", icon_边部桁架, C_ROOF),
    ("行人架", icon_行人架, C_ROOF),
    ("直段下看台", icon_直段下看台, C_STAND),
    ("直段上看台", icon_直段上看台, C_STAND),
    ("曲段下看台", icon_曲段下看台, C_STAND),
    ("曲段上看台", icon_曲段上看台, C_STAND),
    ("座位", icon_座位, C_STAND),
    ("体育馆外墙(有门)", icon_外墙_有门, C_WALL),
    ("体育馆外墙(无门)", icon_外墙_无门, C_WALL),
    ("体育馆外墙(斜)", icon_外墙_斜, C_WALL),
    ("足球场", icon_足球场, C_MISC),
    ("大屏及支架", icon_大屏及支架, C_MISC),
    ("外楼梯", icon_外楼梯, C_MISC),
    ("外栏杆", icon_外栏杆, C_MISC),
    ("无障碍坡道", icon_无障碍坡道, C_MISC),
]


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    for name, fn, color in ICONS:
        save(fn(color), base, name)
    print("已生成 %d 个图标" % len(ICONS))
