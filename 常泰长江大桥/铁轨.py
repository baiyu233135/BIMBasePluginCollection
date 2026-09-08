# -*- coding: utf-8 -*-
"""
铁轨 — 性能优化版

优化说明：
- 轨枕组（每 400mm 一组、每组 3 个摆放对象）由循环逐个 Combine 复制改为
  Array 实例化排布，长度 L 拉伸到公里级时图元数量不再线性爆炸。
- 底板分段复制同样改 Array。
- 钢轨 14 点截面一次 Loft 拉通，保持不变。
- 可调参数、几何位置与外观均不变。
"""
from pyp3d import * 


def _arr(geo, offsets):
    """Array 实例化排布：geo 为基准几何，offsets 为平移向量（Vec3）列表"""
    a = Array(geo)
    for v in offsets:
        a.append(translate(v))
    return a


class 铁轨(Component):

    def __init__(self):
        Component.__init__(self) 
        self['长度'] = Attr(10000,obvious = True)
        self['宽度'] = Attr(2500,obvious = True)
        self['高度'] = Attr(200,obvious = True)
        self['轨枕高度'] = Attr(10,obvious = True)
        self['轨枕长度'] = Attr(100,obvious = True)
        self['轨枕间隔'] = Attr(300,obvious = True)
        
        self['铁轨'] = Attr(None,show = True)
        self.replace()

    @export

    def replace(self):
        L = self['长度']
        W = self['宽度']
        H = self['高度']
        l = self['轨枕长度']
        h = self['轨枕高度']
        long = self['轨枕间隔']
        dl = 5575
        seg = dl + long if (dl + long) != 0 else 1   # 防除零
        y = int(L // seg)

        # ---- 轨枕单元（一组：左股轨枕+垫块、右股轨枕） ----
        R = 130
        cone = Cone(Vec3(0,0,0),Vec3(l,0,0),R,R)
        sec_dian = Section(Vec2(0,0),Vec2(l,0),Vec2(l,l+R),Vec2(0,l+R),Vec2(0,0))
        dian = Loft(sec_dian,trans(0,0,h)*sec_dian)
        zhen = Combine(trans(0,100+R*2,0)*cone,cone,trans(0,R/2,0)*dian)

        gz_unit = Combine(
            trans(0, W/4-R-150/2, H) * zhen,
            trans(0, W/4-R-150/2, H/50*51) * dian,
            trans(0, W/4*3-R-150/2, H) * zhen)
        gz_spacing = (l + long) if (l + long) > 0 else 1   # 防除零
        n_gz = int((L+(y+1)*25) // gz_spacing + 1)
        all_gz = _arr(gz_unit, [Vec3(i * gz_spacing, 0, 0) for i in range(n_gz)])

        # ---- 钢轨（截面一次 Loft 拉通） ----
        sec_gui = rotate(Vec3(0,0,1),pi/2)*rotate(Vec3(1,0,0),pi/2)*Section(Vec2(0,0),Vec2(46.83,0),Vec2(46.83,12),Vec2(5.36,16.67),Vec2(5.36,66.67),
                          Vec2(20.4,70.67),Vec2(20.4,93.66),Vec2(-20.4,93.66),Vec2(-20.4,70.67),
                          Vec2(-5.36,66.67),Vec2(-5.36,16.67),Vec2(-46.83,12),Vec2(-46.83,0),Vec2(0,0))
        gui = Loft(sec_gui,trans(L+(y+1)*25,0,0)*sec_gui)

        # ---- 底板（整段 Array + 末段） ----
        sec_d = Section(Vec2(0,0),Vec2(dl,0),Vec2(dl,W),Vec2(0,W),Vec2(0,0))
        di = Loft(sec_d,trans(0,0,H)*sec_d)
        sec_la = Section(Vec2(0,0),Vec2(L-dl*y,0),Vec2(L-dl*y,W),Vec2(0,W),Vec2(0,0))
        la = Loft(sec_la,trans(0,0,H)*sec_la)
        
        gui_all = Combine(trans(0,W/2/2-25,H/50*51)*gui,trans(0,W/4*3-25,H/50*51)*gui)
        di_arr = _arr(di, [Vec3(i * (dl + 25), 0, 0) for i in range(int(y))]) if y > 0 else None
        allla = trans(y*(dl+25),0,0)*la
        
        di_parts = [p for p in (di_arr, allla) if p is not None]
        allin = Combine(*di_parts)

        self['铁轨'] = Combine(allin,gui_all,all_gz)

if __name__ == "__main__":
    FinalGeometry = 铁轨()
    TwoPointPlace.linearize(FinalGeometry, '长度')
    place(FinalGeometry)
