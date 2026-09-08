# -*- coding: utf-8 -*-
"""
铁路封闭网（1）— Array 实例化优化版

优化说明（2026-09-07）：
- 所有重复几何（网片横竖杆、整排网片、顶部网格杆）改用 Array + linspace 实例化排布，
  替代原来的 Combine(*[trans(...) * cone for ...]) 逐杆合并。
- 参考：BIMBase 内置围栏（安全围栏样式一两点布置.py）就是用 Array 做线性排布的。
- 几何位置、可调参数、外观与布置方式（TwoPointPlace.linearize 按 网长 拉伸）均不变，
  仅减少图元数量（从 O(面板数×杆数) 降到 O(1) 基准几何 + 阵列定义），大幅缓解长网布置卡顿。

注意：类名改为 铁路封闭网_1，避免与 铁路封闭网.py 的类名冲突（BIMBase 序列化按类名解析）。
"""
from pyp3d import *


def _arr(geo, offsets):
    """Array 实例化排布：geo 为基准几何，offsets 为平移向量（Vec3）列表"""
    a = Array(geo)
    for v in offsets:
        a.append(translate(v))
    return a


class 铁路封闭网_1(Component):
    def __init__(self):
        Component.__init__(self)
        self['立柱边长'] = Attr(100, obvious=True)
        self['长杆高'] = Attr(1000, obvious=True)
        self['线半径'] = Attr(5, obvious=True)
        self['柱子间隔'] = Attr(3000, obvious=True)
        self['单块网高度'] = Attr(900, obvious=True)
        self['网长'] = Attr(100, obvious=True)
        self['立柱间隔块数'] = Attr('3', obvious=True)   # 字符串型(避免面板显示 mm 后缀),每隔几块网一根中间立柱
        self['铁路封闭网_1'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        P = self['立柱边长']
        R = self['线半径']
        long = self['长杆高']
        wind = self['单块网高度']
        x = self['柱子间隔']
        y = self['网长']
        k = 50
        frame_long = y - 4 * k
        z = int(frame_long // x)

        # ---- 立柱（长方体） + 侧向耳板 ----
        pillar_unit = trans(-P/2, -P/2, 0) * scale(P, P, long) * Cube()
        box = trans(0, -k/4, 0) * scale(2*k, k/2, k/2) * Cube()
        pillar_first_box = Combine(trans(0, 0, long-300) * box,
                                   trans(0, 0, long-300-long/5) * box,
                                   trans(0, 0, long-300-long/5*2) * box)
        pillar_first_box_color = pillar_first_box.color(0, 0.6, 0, 1)
        pillar_first = Combine(pillar_first_box_color, pillar_unit)
        pillar_last = trans(y, 0, 0) * rotate(Vec3(0, 0, 1), pi) * pillar_first

        # 中间立柱：每隔 nb 块网一根，双面耳板（两侧都接网），Array 实例化
        # nb <= 0 表示不加中间柱（只有首尾两根）
        # 注意：网片从 2k 处开始排布，交界处 = 2k + nb*j*x，柱子必须落在交界处，
        # 否则网格杆会穿过柱身；交界柱与端柱之间至少留一块网（y-x），避免末尾两根柱挤在一起
        try:
            nb = int(float(str(self['立柱间隔块数']).strip()))
        except (TypeError, ValueError):
            nb = 3
        mid_offsets = []
        if nb > 0:
            j = 1
            while 2 * k + nb * j * x <= y - x:
                mid_offsets.append(Vec3(2 * k + nb * j * x, 0, 0))
                j += 1
        if mid_offsets:
            mid_ears = Combine(pillar_first_box_color, trans(-2*k, 0, 0) * pillar_first_box_color)
            mid_pillar_unit = Combine(pillar_unit, mid_ears)
            pillar_mid = _arr(mid_pillar_unit, mid_offsets)
        else:
            pillar_mid = None

        # ---- 顶部网格（Array 实例化） ----
        pl_el = int(y - 2 * k)
        pl_ew = int(P - 2 * k)
        pl_ell = int(pl_el // k) + 1
        pl_eww = int(pl_ew // k) + 1

        # 竖杆：一根基准杆 + Array 沿 X 排 pl_ell 根
        # 注意：Array 的 parts 是变换矩阵，Combine 后染色染不到基准几何，
        # 必须在创建基准几何时就上色（参考 BIMBase 内置围栏的写法）
        v_bar = Cone(Vec3(0, 0, 0), Vec3(0, 0, P), R, R).color(0, 0.6, 0, 1)
        v_top = _arr(v_bar, linspace(
            Vec3(pl_el % k + k, 0, 0),
            Vec3(pl_el % k + pl_ell * k, 0, 0),
            pl_ell))

        # 横杆：一根基准杆 + Array 沿 Z 排 pl_eww 根
        h_bar = Cone(Vec3(0, 0, 0), Vec3(y, 0, 0), R, R).color(0, 0.6, 0, 1)
        h_top = _arr(h_bar, linspace(
            Vec3(0, 0, pl_ew % k + k),
            Vec3(0, 0, pl_ew % k + pl_eww * k),
            pl_eww))

        pillar_line = trans(0, 0, wind) * Combine(v_top, h_top)
        pillar_parts = [pillar_first, pillar_last, pillar_line]
        if pillar_mid is not None:
            pillar_parts.append(pillar_mid)
        pillar = Combine(*pillar_parts)

        # ---- 网片（Array 实例化：杆内排 + 面板排） ----
        el = int(x - 2 * k)
        ew = int(wind - 2 * k)
        ell = int(el // k)
        eww = int(ew // k)

        # 竖杆：一根基准杆 + Array 沿 X 排 ell 根（基准杆创建时上色）
        v_line = Cone(Vec3(0, 0, 0), Vec3(0, 0, wind), R, R).color(0, 0.6, 0, 1)
        v_panel = _arr(v_line, linspace(
            Vec3(el % k + k, k/2, 0),
            Vec3(el % k + ell * k, k/2, 0),
            ell))

        # 横杆：一根基准杆 + Array 沿 Z 排 eww 根
        h_line = Cone(Vec3(0, 0, 0), Vec3(x, 0, 0), R, R).color(0, 0.6, 0, 1)
        h_panel = _arr(h_line, linspace(
            Vec3(0, k/2, ew % k + k),
            Vec3(0, k/2, ew % k + eww * k),
            eww))

        # 边框（创建时上色）
        frame_unit = (scale(x, k, wind) * Cube()
                      - trans(k/2, 0, k/2) * scale(x-k, k, wind-k) * Cube()).color(0, 0.6, 0, 1)

        # 单块网片 = 边框 + 竖杆阵列 + 横杆阵列
        panel = Combine(frame_unit, v_panel, h_panel)

        # 整排网片 = Array(panel) 排 n_full 块
        if z > 0 and int(frame_long % x) <= 200:
            n_full, end_extra = z - 1, x
        elif z > 0:
            n_full, end_extra = z, 0
        else:
            n_full, end_extra = 0, 0
        end_w = frame_long - x * z + end_extra

        frame_parts = []
        if n_full > 0:
            panel_arr = _arr(panel, linspace(
                Vec3(0, 0, 0),
                Vec3(x * (n_full - 1), 0, 0),
                n_full))
            frame_parts.append(trans(k*2, -k/2, 0) * panel_arr)

        # 末块网（宽度 end_w，单独建；基准几何创建时上色）
        if end_w > 0:
            h_end_bar = Cone(Vec3(0, 0, 0), Vec3(end_w, 0, 0), R, R).color(0, 0.6, 0, 1)
            frame_unit_end = (scale(end_w, k, wind) * Cube()
                              - trans(k, 0, k) * scale(end_w - k*2, k, wind - k*2) * Cube()).color(0, 0.6, 0, 1)
            end_ell = int((end_w - 2 * k) // k)
            v_end = _arr(v_line, linspace(
                Vec3(el % k + k, k/2, 0),
                Vec3(el % k + end_ell * k, k/2, 0),
                end_ell))
            h_end = _arr(h_end_bar, linspace(
                Vec3(0, k/2, ew % k + k),
                Vec3(0, k/2, ew % k + eww * k),
                eww))
            panel_end = Combine(frame_unit_end, v_end, h_end)
            frame_parts.append(trans(k*2 + x * n_full, -k/2, 0) * panel_end)

        frame_all = Combine(*frame_parts)
        self['铁路封闭网_1'] = Combine(frame_all, pillar)


if __name__ == '__main__':
    FinalGeometry = 铁路封闭网_1()
    TwoPointPlace.linearize(FinalGeometry, '网长')
    place(FinalGeometry)
