# -*- coding: utf-8 -*-
"""
铁路封闭网（1）— Array 实例化优化版 v2（2026-09-16 交互布置提速）

优化说明：
1. 【修复崩溃】旧版 _arr_row 中 `start + (count-1)*step` 是 Vec3 + 标量，pyp3d 的
   GeVec3d.__add__ 只接受 Vec3/Vec2，会直接抛 TypeError —— 旧版 replace() 必然异常
   中断，两点布置时每次拖动都在跨进程重跑一个必然崩溃的重建，这是卡顿的最大根源。
   现改为显式 Vec3 偏移列表，位置 = start + i*step，与原设计完全一致。
2. 【去布尔运算】网片边框 frame_unit / frame_unit_end 原为 Cube-Cube 布尔差（Fusion），
   每次重建都要内核布尔求值；改为 4 根长条 Cube 无缝拼接，占据区域与布尔差完全相同
   （左右两根通高 + 上下两根嵌中间），颜色不变，组件内布尔运算清零。
   Combine 经 pyp3d 源码核实只是逻辑分组（不做布尔、不展开 Array），予以保留。
3. 【减深拷贝与树层级】pyp3d 的 `矩阵 * 几何` 是整体 deepcopy（Graphics.__rmul__）。
   原 trans(0,0,wind) * Combine(顶部网格) 每次重建都深拷贝整棵顶部网格阵列树
   （百米网约 500+ 矩阵对象）；现把 z=wind 直接写进阵列偏移，省掉这次深拷贝与一层
   Combine。整排网片 Array 的 trans(2k, -k/2, 0) 同理烘焙进偏移。平移矩阵相乘等于
   平移量相加，世界位置不变。
4. 顶部竖杆等距阵列 _arr_row 的 step 参数改为 Vec3（支持任意方向），分组平铺策略不变。

2026-09-16 v3（2409m 超长网提速）：
5. 【整排网片两级嵌套】panel_arr 由单层 Array（n_full 个矩阵）改为 _arr_row 分组
   平铺（16 块一组），2409m 时该阵列矩阵数 802 → 68，序列化/传输量随之下降；
   位置 = (2k + i*x, -k/2, 0) 不变。
   注：Array.isinstance = True（pyp3d 源码中默认 False 的同构实例阵列标志）实测
   效果不行，未采用，保持默认 False。

实测（2409m，BIMBase 嵌入式 Python + pyp3d v18446497937724801024 Subprocess 模式）：
- replace() Python 侧约 45~107 ms/次（展开后叶子实例 112,687 个：107,598 根杆 + 5,089 块板）；
- Python 侧不是瓶颈，瓶颈在内核对 11 万实例的提取/剖分/渲染。

几何外观、位置、可调参数（Attr）、布置方式（TwoPointPlace.linearize 按 网长 拉伸）均不变。
类名 铁路封闭网_1 不变（BIMBase 序列化按类名解析）。
"""
from pyp3d import *


def _arr(geo, offsets):
    """Array 实例化排布：geo 为基准几何，offsets 为平移向量（Vec3）列表"""
    a = Array(geo)
    for v in offsets:
        a.append(translate(v))
    return a


def _arr_row(geo, start, step, count, group=250):
    """等距阵列的低开销版：start/step 均为 Vec3，第 i 根位置 = start + i*step，
    与逐根排布完全一致；先排一组 group 根，再整组平移，最后补零头。"""
    if count <= 0:
        return _arr(geo, [])
    if count <= group:
        return _arr(geo, [start + i * step for i in range(count)])
    n_full, rem = divmod(count, group)
    unit = _arr(geo, [start + i * step for i in range(group)])
    tiled = _arr(unit, [step * (i * group) for i in range(n_full)])
    if rem == 0:
        return tiled
    rest_start = start + step * (n_full * group)
    rest = _arr(geo, [rest_start + i * step for i in range(rem)])
    return Combine(tiled, rest)


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

        # ---- 顶部网格（Array 实例化，z=wind 直接写进偏移，省掉整树深拷贝） ----
        pl_el = int(y - 2 * k)
        pl_ew = int(P - 2 * k)
        pl_ell = int(pl_el // k) + 1
        pl_eww = int(pl_ew // k) + 1

        # 竖杆：一根基准杆 + Array 沿 X 排 pl_ell 根
        # 注意：Array 的 parts 是变换矩阵，Combine 后染色染不到基准几何，
        # 必须在创建基准几何时就上色（参考 BIMBase 内置围栏的写法）
        v_bar = Cone(Vec3(0, 0, 0), Vec3(0, 0, P), R, R).color(0, 0.6, 0, 1)
        v_top = _arr_row(v_bar,
                         Vec3(pl_el % k + k, 0, wind),
                         Vec3(k, 0, 0), pl_ell)

        # 横杆：一根基准杆 + Array 沿 Z 排 pl_eww 根
        h_bar = Cone(Vec3(0, 0, 0), Vec3(y, 0, 0), R, R).color(0, 0.6, 0, 1)
        h_top = _arr(h_bar, linspace(
            Vec3(0, 0, wind + pl_ew % k + k),
            Vec3(0, 0, wind + pl_ew % k + pl_eww * k),
            pl_eww))

        pillar_parts = [pillar_first, pillar_last, v_top, h_top]
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

        # 边框：4 根长条 Cube 无缝拼接（区域 = 外框 Cube 减内框 Cube，与原布尔差完全一致；
        # 消除布尔运算，创建时上色）
        frame_unit = Combine(
            scale(k/2, k, wind) * Cube(),
            trans(x - k/2, 0, 0) * scale(k/2, k, wind) * Cube(),
            trans(k/2, 0, 0) * scale(x - k, k, k/2) * Cube(),
            trans(k/2, 0, wind - k/2) * scale(x - k, k, k/2) * Cube(),
        ).color(0, 0.6, 0, 1)

        # 单块网片 = 边框 + 竖杆阵列 + 横杆阵列
        panel = Combine(frame_unit, v_panel, h_panel)

        # 整排网片 = Array(panel) 排 n_full 块（面板偏移 2k/-k/2 直接写进阵列偏移）
        if z > 0 and int(frame_long % x) <= 200:
            n_full, end_extra = z - 1, x
        elif z > 0:
            n_full, end_extra = z, 0
        else:
            n_full, end_extra = 0, 0
        end_w = frame_long - x * z + end_extra

        frame_parts = []
        if n_full > 0:
            # 两级嵌套阵列（16 块一组再整组平铺），位置 = (2k + i*x, -k/2, 0)，
            # 与原 linspace 逐块排布一致；超长网时矩阵/序列化量从 O(n_full) 降到 O(组+组数)
            panel_arr = _arr_row(panel,
                                 Vec3(k*2, -k/2, 0),
                                 Vec3(x, 0, 0), n_full, group=16)
            frame_parts.append(panel_arr)

        # 末块网（宽度 end_w，单独建；基准几何创建时上色）
        if end_w > 0:
            h_end_bar = Cone(Vec3(0, 0, 0), Vec3(end_w, 0, 0), R, R).color(0, 0.6, 0, 1)
            frame_unit_end = Combine(
                scale(k, k, wind) * Cube(),
                trans(end_w - k, 0, 0) * scale(k, k, wind) * Cube(),
                trans(k, 0, 0) * scale(end_w - k*2, k, k) * Cube(),
                trans(k, 0, wind - k) * scale(end_w - k*2, k, k) * Cube(),
            ).color(0, 0.6, 0, 1)
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
