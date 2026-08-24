# -*- coding: utf-8 -*-
"""
承台及桩基参数化组件（精简参数版）

参考：数据参考源/承台及桩基/承台及桩基.dwg

保留用户可交互调整的核心外轮廓参数，其余细部尺寸固定为图纸默认值。

结构：矩形承台 + 列×排桩阵列
坐标系（BIMBase）：X 长向，Y 宽向，Z 高度；原点在承台底面中心，桩向下延伸
"""

from pyp3d import *


class 承台及桩基(Component):
    """承台及桩基：矩形承台 + 列×排圆柱桩阵列"""

    def __init__(self):
        Component.__init__(self)
        # 核心外轮廓参数（单位 cm，在属性面板可交互修改）
        self['承台长'] = Attr(5500.0, obvious=True)
        self['承台宽'] = Attr(2350.0, obvious=True)
        self['承台高'] = Attr(500.0, obvious=True)
        self['桩径'] = Attr(250.0, obvious=True)
        self['桩长'] = Attr(5000.0, obvious=True)
        self['桩间距'] = Attr(630.0, obvious=True)      # 桩中心间距
        self['桩列数'] = Attr(9, obvious=True)          # X 向桩数
        self['桩排数'] = Attr(4, obvious=True)          # Y 向桩数
        self['承台及桩基'] = Attr(None, show=True)
        self['颜色'] = Attr(None, show=False)  # 整体颜色 (r,g,b,a)，None 表示不上色
        self.replace()

    @export
    def replace(self):
        cap_l = self['承台长']
        cap_w = self['承台宽']
        cap_h = self['承台高']
        pile_d = self['桩径']
        pile_l = self['桩长']
        spacing = self['桩间距']
        n_col = max(int(self['桩列数']), 1)
        n_row = max(int(self['桩排数']), 1)

        # 承台：z 从 0 到 承台高，中心在原点
        cap = translate(-cap_l / 2, -cap_w / 2, 0) * scale(cap_l, cap_w, cap_h) * Cube()

        # 桩阵列：桩顶伸入承台底（z=0），桩底 z=-桩长
        r = pile_d / 2
        x0 = -(n_col - 1) * spacing / 2
        y0 = -(n_row - 1) * spacing / 2
        piles = []
        for i in range(n_col):
            for j in range(n_row):
                x = x0 + i * spacing
                y = y0 + j * spacing
                piles.append(Cone(Vec3(x, y, -pile_l), Vec3(x, y, 0), r, r))

        geom = Combine(cap, *piles)
        try:
            c = self['颜色'] if '颜色' in self else None
            if c:
                vals = [float(x) for x in str(c).split(',') if x.strip()]
                if len(vals) >= 3:
                    geom = geom.color(*vals)
        except Exception:
            pass
        self['承台及桩基'] = geom


if __name__ == "__main__":
    FinalGeometry = 承台及桩基()
    place(FinalGeometry)
