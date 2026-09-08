from pyp3d import *
import math

class 拱桥立柱及盖梁(Component):
    def __init__(self):
        Component.__init__(self)
        # ===== 可修改核心参数（图纸默认值，单位cm）=====
        self['盖梁总长度L'] = Attr(660, obvious = True)
        self['立柱总高度H'] = Attr(1000, obvious = True)
        self['盖梁高度'] = Attr(80, obvious = True)
        self['立柱宽度'] = Attr(60, obvious = True)
        self['拱柱高度'] = Attr(40, obvious = True)
        self['拱柱间距'] = Attr(60, obvious = True)
        self['挡墙高度'] = Attr(40, obvious = True)
        self['系梁高度'] = Attr(400, obvious = True)
        self['拱上垫梁高度'] = Attr(70,obvious = True)
        self['模型主体'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self): 
        # 读取参数（单位cm）
        L = self['盖梁总长度L']
        H = self['立柱总高度H']
        girder_h = self['盖梁高度']
        col_width = self['立柱宽度']
        arch_col_h = self['拱柱高度']
        arch_col_space = self['拱柱间距']
        wall_h = self['挡墙高度']
        tie_h = self['系梁高度']
        gsdl_h = self['拱上垫梁高度']
                        # ===== 图纸固定尺寸（单位cm）=====
        base_len = 600.0            # 底部长度（X方向）
        base_width = 150.0          # 底部宽度（Y方向）
        base_h = 20.0               # 长方体高度
        tri_h = 70.0                # 三棱柱高度
        col_side_width = 120.0
        girder_side_width = 160.0
        end_dist = 80.0
        pad_h = base_h              # 垫梁顶面z坐标（长方体顶面）
        gsdl_w = 150.0
                # ============================================================
        # 1. 底部（长方体 + 三棱柱）
        #    长方体：600×150×20
        #    三棱柱：侧面直角三角形(150×70)，沿X轴拉伸600
        # ============================================================
        box_base = translate(-base_len/2, -base_width/2, 0.0) * \
                    scale(base_len, base_width, base_h) * Cube()
        
       
        sanjiao = Section(Vec2(0,0),Vec2(150,0),Vec2(0,70),Vec2(0,0))
        sanjiao_2 = trans(0,0,600) * sanjiao
        sl = Loft(sanjiao,sanjiao_2)
        sl_2 = rotate(Vec3(1,0,0), 1.5*pi) * trans(0,0,0) * sl
        sanleng = rotate(Vec3(0,0,1),0.5*pi) *trans(-base_len/8,-300,0) * sl_2
        pad = Combine(box_base, sanleng)

        # ============================================================
        # 2. 三根立柱
        # ============================================================
        col_x_positions = [
            -L/2 + end_dist,
            0.0,
            L/2 - end_dist
        ]
        columns = []
        for x in col_x_positions:
            col = translate(x - col_width/2, -col_side_width/2, pad_h) * \
                  scale(col_width, col_side_width, H) * Cube()
            columns.append(col)

        col_all = Combine(*columns)

        # ============================================================
        # 3. 盖梁
        # ============================================================
        girder = translate(-L/2, -girder_side_width/2, pad_h + H) * \
                 scale(L, girder_side_width, girder_h) * Cube()

        # ============================================================
        # 4. 挡板（左右两端，与盖梁同宽）
        #    最左/最右拱柱中心距挡板 25cm
        # ============================================================
        wall_thick = 25.0  # 挡板厚度（X方向）
        # 挡板z从盖梁顶面到盖梁顶面+wall_h
        left_wall = translate(-L/2, -girder_side_width/2, pad_h + H + girder_h) * \
                    scale(wall_thick, girder_side_width, wall_h) * Cube()
        right_wall = translate(L/2 - wall_thick, -girder_side_width/2, pad_h + H + girder_h) * \
                     scale(wall_thick, girder_side_width, wall_h) * Cube()

        # ============================================================
        # 5. 顶部拱柱
        #    模式：101101101101101101（1=有拱柱，0=空白）
        #    Y方向两排，布局相同
        #    每个拱柱：底部38×38×10，顶部18×18×10
        #    间距规则：1和1中间有0则中心距60，没有0则中心距40
        #    第一列中心距左挡板25cm，最后一列中心距右挡板25cm
        # ============================================================
        pattern = [1,0,1,1,0,1,1,0,1,1,0,1,1,0,1,1,0,1]

        # 按间距规则计算每个1的位置
        positions_x = []
        x0 = -L/2 + wall_thick + 25.0  # 第一个拱柱中心距左挡板25
        idx = 0
        while idx < len(pattern):
            if pattern[idx] == 1:
                positions_x.append(x0)
                # 找下一个1
                next_idx = idx + 1
                while next_idx < len(pattern) and pattern[next_idx] == 0:
                    next_idx += 1
                if next_idx < len(pattern):
                    if next_idx == idx + 1:
                        x0 += 40  # 相邻：间距40
                    else:
                        x0 += 60  # 中间有0：间距60
                idx = next_idx
            else:
                idx += 1

        # Y方向两排，对称居中于盖梁宽度方向
        y_gap = 50.0
        y_positions = [-y_gap/2, y_gap/2]

        arch_base_h = 10.0   # 拱柱底部高度
        arch_top_h = 10.0    # 拱柱顶部高度
        base_size = 38.0
        top_size = 18.0

        arch_z_base = pad_h + H + girder_h  # 拱柱底面在盖梁顶面（与挡板同高度起算）

        # 拱柱阵列：底/顶各一个基准方块，Array 实例化排布（替代双重循环逐个 + 合并）
        xy = [(x, y) for x in positions_x for y in y_positions]
        if xy:
            base_unit = scale(base_size, base_size, arch_base_h) * Cube()
            top_unit = scale(top_size, top_size, arch_top_h) * Cube()
            base_arr = Array(base_unit)
            top_arr = Array(top_unit)
            for (x, y) in xy:
                base_arr.append(translate(Vec3(x - base_size/2, y - base_size/2, arch_z_base)))
                top_arr.append(translate(Vec3(x - top_size/2, y - top_size/2, arch_z_base + arch_base_h)))
            arch_all = Combine(base_arr, top_arr)
        else:
            arch_all = None

        # ============================================================
        # 6. 系梁（连接左-中、中-右立柱）
        #    系梁底部距离垫梁顶面高度 = 系梁高度参数
        #    系梁截面：长宽均为60（正方形）
        #    在Y方向居中
        # ============================================================
        tie_size = 60.0       # 系梁截面边长
        tie_z_bottom = pad_h + tie_h

        x_left = -L/2 + end_dist       # 左立柱中心x
        x_right = L/2 - end_dist       # 右立柱中心x

        # 左-中系梁：从左立柱右边缘到中立柱中心
        tie_left_len = -x_left - col_width/2
        tie_left = translate(x_left + col_width/2, -tie_size/2, tie_z_bottom) * \
                   scale(tie_left_len, tie_size, tie_size) * Cube()

        # 中-右系梁：从中立柱中心到右立柱左边缘
        tie_right_len = x_right - col_width/2
        tie_right = translate(0, -tie_size/2, tie_z_bottom) * \
                    scale(tie_right_len, tie_size, tie_size) * Cube()

        tie_all = Combine(tie_left, tie_right)

        # ============================================================
        # 7. 总组合
        # ============================================================
        parts = [pad, col_all, girder, left_wall, right_wall, tie_all]
        if arch_all is not None:
            parts.append(arch_all)
        self['模型主体'] = Combine(*parts)

if __name__ == "__main__":
    Final_Geometry = 拱桥立柱及盖梁()
    place(Final_Geometry)