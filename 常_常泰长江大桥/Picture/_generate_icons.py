# -*- coding: utf-8 -*-
"""生成常泰长江大桥组件库图标(22 个组件,PIL 线框示意图,64x64,按面板分组配色)"""

from PIL import Image, ImageDraw
import os

SIZE = 64

# 分组配色:墩柱与基础=钢蓝,梁板与支座=橙,缆索与锚固=紫,桥面系与附属=绿
C_PIER = (60, 110, 180, 255)
C_BEAM = (200, 120, 0, 255)
C_CABLE = (130, 60, 170, 255)
C_DECK = (0, 150, 60, 255)


def canvas():
    return Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))


def save(img, base, name):
    img.save(os.path.join(base, name + ".ico"), sizes=[(16, 16), (32, 32), (64, 64)])


# ---------- 墩柱与基础 ----------

def icon_桥柱(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.polygon([(20, 56), (26, 12), (38, 12), (44, 56)], outline=c, width=3)  # 变截面塔身
    d.line([(14, 12), (50, 12)], fill=c, width=4)             # 顶端垫梁
    d.arc([16, 40, 48, 64], 180, 360, fill=c, width=3)        # 底部拱洞
    return img


def icon_椭圆墩柱(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 34, 54, 52], radius=10, outline=c, width=4)  # 底部椭圆墩
    d.rounded_rectangle([16, 12, 48, 30], radius=8, outline=c, width=3)   # 上部墩身
    return img


def icon_方圆钢柱(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([10, 46, 54, 54], outline=c, width=4)         # 底方板
    d.rectangle([10, 8, 54, 16], outline=c, width=4)          # 顶方板
    d.line([(32, 16), (32, 46)], fill=c, width=6)             # 圆柱
    return img


def icon_链接多边柱脚(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.polygon([(14, 22), (20, 16), (28, 16), (34, 22),
               (34, 52), (14, 52)], outline=c, width=3)       # 左多边柱
    d.polygon([(40, 22), (46, 16), (54, 16), (60, 22),
               (60, 52), (40, 52)], outline=c, width=3)       # 右多边柱
    d.line([(34, 34), (40, 34)], fill=c, width=4)             # 系梁
    return img


def icon_多腿站台(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([4, 8, 60, 18], outline=c, width=4)           # 承台
    for x in (12, 26, 40, 54):                                 # 圆柱腿
        d.line([(x, 18), (x, 56)], fill=c, width=3)
    return img


def icon_拱桥立柱及盖梁(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(6, 14), (58, 14)], fill=c, width=4)              # 盖梁
    for x in (12, 32, 52):                                     # 三根立柱
        d.line([(x, 14), (x, 50)], fill=c, width=4)
    d.line([(12, 50), (52, 50)], fill=c, width=3)             # 系梁
    d.rectangle([10, 50, 54, 56], outline=c, width=3)         # 底座
    return img


# ---------- 梁板与支座 ----------

def icon_工字钢(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(12, 14), (52, 14)], fill=c, width=5)             # 上翼缘
    d.line([(32, 14), (32, 50)], fill=c, width=4)             # 腹板
    d.line([(12, 50), (52, 50)], fill=c, width=5)             # 下翼缘
    return img


def icon_组装工字梁(c):
    img = canvas(); d = ImageDraw.Draw(img)
    for x in (12, 32, 52):                                     # 三根立柱
        d.line([(x, 10), (x, 54)], fill=c, width=3)
    d.line([(12, 54), (32, 10)], fill=c, width=3)             # 斜撑
    d.line([(32, 54), (52, 10)], fill=c, width=3)
    return img


def icon_凸插板(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([6, 26, 58, 40], outline=c, width=3)          # 底板
    for x in (16, 30, 44):                                     # 底部凸起
        d.rectangle([x, 40, x + 6, 52], outline=c, width=3)
    return img


def icon_被插板(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([6, 18, 58, 44], outline=c, width=3)          # 板
    for x in (16, 32, 44):                                     # 顶面凹槽
        d.line([(x, 18), (x, 28), (x + 6, 28), (x + 6, 18)], fill=c, width=3)
    return img


def icon_支座(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(14, 12), (50, 12)], fill=c, width=4)             # 上板
    d.line([(20, 20), (44, 20)], fill=c, width=4)             # 中板
    d.line([(24, 20), (24, 44)], fill=c, width=6)             # 支座体
    d.line([(40, 20), (40, 44)], fill=c, width=6)
    d.line([(10, 52), (54, 52)], fill=c, width=4)             # 下板
    d.line([(10, 44), (54, 44)], fill=c, width=3)
    return img


# ---------- 缆索与锚固 ----------

def icon_斜拉索(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(12, 6), (12, 58)], fill=c, width=5)              # 索塔
    for y in (12, 22, 32):                                     # 扇形拉索
        d.line([(12, y), (54, 50)], fill=c, width=2)
    d.line([(4, 50), (60, 50)], fill=c, width=4)              # 桥面
    return img


def icon_索塔锚块(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.polygon([(10, 20), (54, 20), (40, 38), (24, 38)], outline=c, width=3)  # 锚块
    d.line([(20, 38), (20, 54)], fill=c, width=4)             # 底柱
    d.line([(44, 38), (44, 54)], fill=c, width=4)
    d.line([(32, 6), (32, 20)], fill=c, width=3)              # 进索
    return img


# ---------- 桥面系与附属 ----------

def icon_路面及交通标线(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([4, 16, 60, 48], outline=c, width=3)          # 路面
    for x in (10, 26, 42):                                     # 虚线
        d.line([(x, 32), (x + 8, 32)], fill=c, width=3)
    d.line([(4, 24), (60, 24)], fill=c, width=2)              # 实线
    return img


def icon_新泽西护栏(c):
    img = canvas(); d = ImageDraw.Draw(img)
    pts = [(20, 56), (20, 34), (26, 20), (38, 20), (44, 34), (44, 56)]
    d.line(pts, fill=c, width=4)                              # 护栏断面
    d.line([(8, 56), (56, 56)], fill=c, width=3)              # 地面
    return img


def icon_铁路封闭网(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([8, 14, 56, 52], outline=c, width=3)          # 网片边框
    for x in (20, 32, 44):                                     # 竖网格
        d.line([(x, 14), (x, 52)], fill=c, width=2)
    for y in (26, 40):                                         # 横网格
        d.line([(8, y), (56, y)], fill=c, width=2)
    d.line([(8, 14), (56, 6)], fill=c, width=3)               # 顶部斜撑
    return img


def icon_铁轨(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(8, 18), (56, 18)], fill=c, width=4)              # 左股钢轨
    d.line([(8, 46), (56, 46)], fill=c, width=4)              # 右股钢轨
    for x in (14, 26, 38, 50):                                 # 轨枕
        d.line([(x, 14), (x, 50)], fill=c, width=3)
    return img


def icon_电线杆(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.line([(32, 12), (32, 56)], fill=c, width=4)             # 主杆
    d.line([(16, 18), (48, 18)], fill=c, width=3)             # 横担
    d.line([(8, 12), (56, 12)], fill=c, width=2)              # 电线
    d.line([(8, 24), (56, 24)], fill=c, width=2)
    d.line([(22, 56), (42, 56)], fill=c, width=3)             # 基础
    return img


def icon_窗户(c):
    img = canvas(); d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 56, 56], outline=c, width=4)           # 外框
    d.line([(32, 8), (32, 56)], fill=c, width=2)              # 中梃
    d.line([(36, 12), (52, 18), (52, 50), (36, 52)], fill=c, width=2)  # 开启扇
    return img


ICONS = [
    ("桥柱", icon_桥柱, C_PIER),
    ("椭圆墩柱", icon_椭圆墩柱, C_PIER),
    ("方圆钢柱", icon_方圆钢柱, C_PIER),
    ("链接多边柱脚", icon_链接多边柱脚, C_PIER),
    ("多腿站台", icon_多腿站台, C_PIER),
    ("拱桥立柱及盖梁", icon_拱桥立柱及盖梁, C_PIER),
    ("工字钢", icon_工字钢, C_BEAM),
    ("组装工字梁", icon_组装工字梁, C_BEAM),
    ("凸插板", icon_凸插板, C_BEAM),
    ("被插板", icon_被插板, C_BEAM),
    ("支座", icon_支座, C_BEAM),
    ("斜拉索", icon_斜拉索, C_CABLE),
    ("索塔锚块", icon_索塔锚块, C_CABLE),
    ("路面及交通标线", icon_路面及交通标线, C_DECK),
    ("新泽西护栏", icon_新泽西护栏, C_DECK),
    ("铁路封闭网", icon_铁路封闭网, C_DECK),
    ("铁轨", icon_铁轨, C_DECK),
    ("电线杆", icon_电线杆, C_DECK),
    ("窗户", icon_窗户, C_DECK),
]


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    for name, fn, color in ICONS:
        save(fn(color), base, name)
    print("已生成 %d 个图标" % len(ICONS))
