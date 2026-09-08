# -*- coding: utf-8 -*-
"""
窗户 — 性能优化版

优化说明：
- 外框、窗扇的"方体减方体"布尔减改为 4 根杆件拼框，外观一致且规避布尔不稳定。
- 修正玻璃截面退化 bug：原截面 5 个点全部共线（零面积），玻璃实际显示不出来；
  改为正常矩形截面。
- 开合角度字符串解析加容错（合法数字输入行为不变）。
- 可调参数、几何位置与外观均不变。
"""
from pyp3d import * 
import math


def _frame_box(long, wide, high, open_long, open_high):
    """矩形框：4 根杆件拼成（替代布尔减，外观一致）。
    long/wide/high 为外轮廓，open_long/open_high 为居中的开孔尺寸。"""
    mx = max((long - open_long) / 2.0, 0)   # 单侧横边宽
    mz = max((high - open_high) / 2.0, 0)   # 单侧竖边宽
    parts = []
    if mx > 0:
        parts.append(scale(mx, wide, high) * Cube())                       # 左边
        parts.append(trans(long - mx, 0, 0) * scale(mx, wide, high) * Cube())  # 右边
    if mz > 0 and open_long > 0:
        parts.append(trans(mx, 0, 0) * scale(open_long, wide, mz) * Cube())          # 底边
        parts.append(trans(mx, 0, high - mz) * scale(open_long, wide, mz) * Cube())  # 顶边
    if not parts:                       # 开孔覆盖整个面时退化为薄片，防空 Combine
        parts.append(scale(long, wide, max(high, 1)) * Cube())
    return Combine(*parts)


class 窗户(Component):

    def __init__(self):
        Component.__init__(self) 
        self['外框长'] = Attr(1150,obvious = True)
        self['外框宽'] = Attr(50,obvious = True)
        self['外框高'] = Attr(1340,obvious = True)
        self['单侧窗户长'] = Attr(500,obvious = True)
        self['单侧窗户宽'] = Attr(50,obvious = True)
        self['单侧窗户高'] = Attr(1200,obvious = True)
        self['玻璃长'] = Attr(400,obvious = True)
        self['玻璃宽'] = Attr(10,obvious = True)
        self['玻璃高'] = Attr(1000,obvious = True)
        
        self['开合角度'] = Attr('90',obvious = True)
        
        self['窗户'] = Attr(None,show = True)
        self.replace()

    @export
    def replace(self):
        out_window_long = self['外框长']
        out_window_wide = self['外框宽']
        out_window_high = self['外框高']
        in_window_long = self['单侧窗户长']
        in_window_wide = self['单侧窗户宽']
        in_window_high = self['单侧窗户高']
        window_long = self['玻璃长']
        window_wide = self['玻璃宽']
        window_high = self['玻璃高']
        # 开合角度为字符串型，容错解析（非法输入回退 90）
        try:
            x1 = int(float(str(self['开合角度']).strip()))
        except (TypeError, ValueError):
            x1 = 90
        angle = pi/180*x1

        # 外框：原逻辑为外方体减去居中内方体（开孔贯穿整个宽度方向）
        out_window = _frame_box(out_window_long, out_window_wide, out_window_high,
                                in_window_long * 2, in_window_high)

        # 窗扇：原逻辑为窗扇方体减去居中玻璃孔（开孔贯穿整个宽度方向）
        # 窗扇：原逻辑为窗扇方体减去居中玻璃孔（开孔贯穿整个宽度方向）
        # 原窗扇局部坐标 y∈[-in_wide/2, in_wide/2]，拼框后平移对齐
        in_window = trans(0, -in_window_wide/2, 0) * _frame_box(
            in_window_long, in_window_wide, in_window_high,
            window_long, window_high)

        # 玻璃：修正原零面积退化截面，改为正常矩形板，在窗扇厚度方向居中
        glass_sec = Section(Vec2(0,-window_wide/2),Vec2(window_long,-window_wide/2),
                            Vec2(window_long,window_wide/2),Vec2(0,window_wide/2),
                            Vec2(0,-window_wide/2))
        window_unit = Loft(glass_sec, trans(0,0,window_high)*glass_sec)
        # 玻璃板设透明0.1，窗扇保持默认色
        window_unit_color = window_unit.color(0.5,0,0,0.1)

        sash = Combine(in_window,
                       trans((in_window_long-window_long)/2,0,(in_window_high-window_high)/2)*window_unit_color)
        window_left = trans(out_window_long/2-in_window_long,in_window_wide/2,out_window_high/2-in_window_high/2)*rotate(Vec3(0,0,1),angle)*sash
        window_right = trans(out_window_long/2+in_window_long,in_window_wide/2,out_window_high/2-in_window_high/2)*rotate(Vec3(0,0,1),pi-angle)*sash
        
        self['窗户'] = Combine(out_window, window_left, window_right)

if __name__ == "__main__":
    FinalGeometry = 窗户()
    place(FinalGeometry)
