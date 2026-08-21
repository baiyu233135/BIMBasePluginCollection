# -*- coding: utf-8 -*-
"""
铁路封闭网参数化组件（Cone 优化版 + 放置坐标直写）

优化说明：线杆/长杆由“32边形截面 Section + Loft”改为原生 Cone（真圆弧截面），
几何位置、可调参数、外观与布置方式（TwoPointPlace.linearize 按 网长 拉伸）均不变，
仅减少每根杆的截面数据封送与图形节点组装开销，缓解长网布置时的卡顿。
（原版备份：archive/misc/铁路封闭网_原版备份.py）

坐标直写：replace() 从 self.transformation 提取放置平移写入 X/Y/Z坐标 参数。
放置瞬间平移为零（跳过）；后续重生成（面板改参/点修改/重开工程）时自动写入。
交互全程原生 TwoPointPlace，无 Python 鼠标回调，流畅度与原生一致。
（实测：replace 由内核 service 进程执行，工具取点 API 在其中恒返回 (0,0,0)，不可用）
诊断日志：组件成品/坐标写入_debug.log

可调参数：
- 长杆半径 / 长杆高 / 侧长 : 立柱与顶部 45° 斜杆
- 线半径 : 网格线杆半径
- 单块网长度 / 单块网高度 : 网片单元尺寸
- 网长 : 总长度（两点布置时拉伸）
- X坐标 / Y坐标 / Z坐标 : 放置基准点坐标（放置时自动写入，仅显示）
"""

from pyp3d import *
import os
import time


class 铁路封闭网(Component):
    def __init__(self):
        Component.__init__(self)
        self['长杆半径'] = Attr(40, obvious=True)
        self['长杆高'] = Attr(3000, obvious=True)
        self['侧长'] = Attr(500, obvious=True)
        self['线半径'] = Attr(10, obvious=True)
        self['单块网长度'] = Attr(9000, obvious=True)
        self['单块网高度'] = Attr(2800, obvious=True)
        self['网长'] = Attr(100, obvious=True)
        # 放置基准点坐标（仅显示用；放置后运行"回写放置坐标"按钮写入实际值）
        self['X坐标'] = Attr(0.0, obvious=True)
        self['Y坐标'] = Attr(0.0, obvious=True)
        self['Z坐标'] = Attr(0.0, obvious=True)
        self['铁路封闭网'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        R1 = self['长杆半径']
        R2 = self['线半径']
        long = self['长杆高']
        up = self['侧长']
        wind = self['单块网高度']
        x = self['单块网长度']
        y = self['网长']
        k = 100
        frame_long = y - 2 * R1 - 2 * k
        z = int(frame_long // x)

        # ---- 立柱（首尾两根，含侧向耳板与顶部 45° 斜撑） ----
        pillar_unit = Cone(Vec3(0, 0, 0), Vec3(0, 0, long), R1, R1)
        box = trans(0, -R1, 0) * scale(k + R1, k, k) * Cube()
        pillar_first_down = (pillar_unit
                             + trans(0, 0, long - 300) * box
                             + trans(0, 0, long - 300 - long / 5) * box
                             + trans(0, 0, long - 300 - long / 5 * 2) * box
                             + trans(0, 0, long - 300 - long / 5 * 3) * box)
        pillar_last_down = trans(y, 0, 0) * rotate(Vec3(0, 0, 1), pi) * pillar_first_down
        pillar_up_unit = Cone(Vec3(0, 0, 0), Vec3(0, 0, up), R1, R1)
        pillar_up = trans(0, R1 / 2, long - R1) * rotate(Vec3(1, 0, 0), pi / 4) * pillar_up_unit
        pillar_first = pillar_first_down + pillar_up
        pillar_last = pillar_last_down + trans(y, 0, 0) * pillar_up

        # 顶部 45° 斜面网格
        pillar_line_wide_unit = Cone(Vec3(0, 0, 0), Vec3(0, 0, up), R2, R2)
        pillar_line_long_unit = Cone(Vec3(0, 0, 0), Vec3(y, 0, 0), R2, R2)
        pl_el = int(y - 2 * k)
        pl_ew = int(up - 2 * k)
        pl_ell = int(pl_el // k)
        pl_eww = int(pl_ew // k)
        pillar_line_wide = Combine(*[
            trans(pl_el % k + i * k + k, k / 2, 0) * pillar_line_wide_unit
            for i in range(pl_ell)
        ])
        pillar_line_long = Combine(*[
            trans(0, k / 2, pl_ew % k + i * k + k) * pillar_line_long_unit
            for i in range(pl_eww)
        ])
        pillar_line = (trans(0, R1 / 2, long - R1) * rotate(Vec3(1, 0, 0), pi / 4)
                       * (pillar_line_long + pillar_line_wide))
        pillar = Combine(pillar_first, pillar_last, pillar_line)

        # ---- 网片（边框 + 横竖网格线） ----
        line_unit_wide = Cone(Vec3(0, 0, 0), Vec3(0, 0, wind), R2, R2)
        line_unit_long = Cone(Vec3(0, 0, 0), Vec3(x, 0, 0), R2, R2)

        el = int(x - 2 * k)
        ew = int(wind - 2 * k)
        ell = int(el // k)
        eww = int(ew // k)

        # 整网数量与末块网宽度：余量 <=200 时末块并入最后一块整网
        if z > 0 and int(frame_long % x) <= 200:
            n_full, end_extra = z - 1, x
        elif z > 0:
            n_full, end_extra = z, 0
        else:
            n_full, end_extra = 0, 0
        end_w = frame_long - x * z + end_extra

        frame_all_parts = []
        if n_full > 0:
            frame_unit = scale(x, k, wind) * Cube() - trans(k, 0, k) * scale(x - k * 2, k, wind - k * 2) * Cube()
            line_long = Combine(*[
                trans(0, k / 2, ew % k + i * k + k) * line_unit_long
                for i in range(eww)
            ])
            line_wide = Combine(*[
                trans(el % k + i * k + k, k / 2, 0) * line_unit_wide
                for i in range(ell)
            ])
            frame = Combine(line_long, line_wide, frame_unit)
            frame_unit_all = Combine(*[trans(i * x, 0, 0) * frame for i in range(n_full)])
            frame_all_parts.append(trans(k + R1, -R1, long - wind) * frame_unit_all)

        # 末块网（宽度 end_w）
        line_end_unit = Cone(Vec3(0, 0, 0), Vec3(end_w, 0, 0), R2, R2)
        frame_unit_end = (scale(end_w, k, wind) * Cube()
                          - trans(k, 0, k) * scale(end_w - k * 2, k, wind - k * 2) * Cube())
        line_end_long = Combine(*[
            trans(0, k / 2, ew % k + i * k + k) * line_end_unit
            for i in range(eww)
        ])
        end_vn = int((end_w - 2 * k) // k)
        line_end_wide = Combine(*[
            trans(el % k + i * k + k, k / 2, 0) * line_unit_wide
            for i in range(end_vn)
        ])
        frame_unit_end = Combine(line_end_long, line_end_wide, frame_unit_end)
        frame_all_parts.append(trans(k + R1 + x * n_full, -R1, long - wind) * frame_unit_end)
        frame_all = Combine(*frame_all_parts)

        self['铁路封闭网'] = Combine(frame_all, pillar)
        self._write_place_coords()

    def _write_place_coords(self):
        """从 self.transformation 提取放置平移并写入 X/Y/Z坐标 参数。
        时机说明（2026-08-21 实测定论）：
        - replace() 由内核 service 进程执行，无交互工具上下文，
          get_current_point()/get_dynamic_point() 永远返回 (0,0,0)，不可用于取点；
        - 放置瞬间：变换只含旋转（平移由 place_to 之后施加），平移为零 → 跳过；
        - 后续重生成（面板改参/点“修改”/重开工程）：内核用已存储实例数据重跑
          replace，self.transformation 含完整放置平移 → 自动写入坐标。"""
        try:
            t = self.transformation
            mat = getattr(t, '_mat', None)
            if not (isinstance(mat, (list, tuple)) and len(mat) == 3):
                return
            x, y, z = float(mat[0][3]), float(mat[1][3]), float(mat[2][3])
            try:
                import sys as _sys
                line = (f"[{time.strftime('%H:%M:%S')}] translation=({x:.2f}, {y:.2f}, {z:.2f}) "
                        f"argv0={_sys.argv[0]}\n")
                log_dirs = []
                for base in (os.path.dirname(os.path.abspath(__file__)),
                             os.path.dirname(os.path.abspath(_sys.argv[0])),
                             r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\组件成品'):
                    if base and base not in log_dirs:
                        log_dirs.append(base)
                for d in log_dirs:
                    try:
                        with open(os.path.join(d, '坐标写入_debug.log'), 'a', encoding='utf-8') as f:
                            f.write(line)
                    except Exception:
                        pass
            except Exception:
                pass
            if abs(x) < 1e-9 and abs(y) < 1e-9 and abs(z) < 1e-9:
                return  # 放置瞬间（旋转尚未带平移）或原点放置，不写
            self['X坐标'] = x
            self['Y坐标'] = y
            self['Z坐标'] = z
        except Exception:
            pass


if __name__ == "__main__":
    FinalGeometry = 铁路封闭网()
    TwoPointPlace.linearize(FinalGeometry, '网长')
    place(FinalGeometry)
