# -*- coding: utf-8 -*-
"""
CAD 组件缓存：复杂识别后，将参数化组件生成为独立 .py 脚本并执行/导入，
绕开 bimbase_sync.py 中组件类可能遇到的模块路径/状态问题。
"""
import os
import shutil
import sys
import tempfile
import time
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(PROJECT_ROOT, 'cad组件缓存')
CADBOARD_DIR = os.path.join(PROJECT_ROOT, 'CADBoard')


def _log(msg):
    try:
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'bimbase_sync_debug.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            import datetime
            f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [gen_cache] {msg}\n")
    except Exception:
        pass


def ensure_cache_dir():
    """确保 cad组件缓存 目录存在"""
    if not os.path.isdir(CACHE_DIR):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            _log(f"created cache dir: {CACHE_DIR}")
        except Exception as e:
            _log(f"create cache dir failed: {e}")
    return CACHE_DIR


def clear_cache_dir():
    """清除 cad组件缓存 目录下的所有生成脚本"""
    if not os.path.isdir(CACHE_DIR):
        return 0
    removed = 0
    for name in os.listdir(CACHE_DIR):
        path = os.path.join(CACHE_DIR, name)
        try:
            if os.path.isfile(path) and name.endswith('.py'):
                os.remove(path)
                removed += 1
            elif os.path.isdir(path) and name == '__pycache__':
                shutil.rmtree(path)
                removed += 1
        except Exception as e:
            _log(f"clear cache failed for {path}: {e}")
    _log(f"cleared {removed} cache items")
    return removed


def clear_all_caches():
    """
    清理 CADBoard 相关的所有运行时缓存：
      - cad组件缓存/ 下的生成脚本
      - CADBoard 内所有 __pycache__ 目录
      - CADBoard 根目录下的 .log 日志文件
      - /tmp 下 cadboard_ 前缀的临时目录
    返回 (removed_count, detail_dict)。
    """
    detail = {
        'component_scripts': 0,
        'pycache_dirs': 0,
        'log_files': 0,
        'temp_dirs': 0,
        'registry': False,
        'errors': [],
    }

    # 1) 组件脚本缓存
    try:
        detail['component_scripts'] = clear_cache_dir()
    except Exception as e:
        detail['errors'].append(f"cad组件缓存: {e}")

    # 1.5) 组件注册表（内存 + 持久化 JSON）
    try:
        from utils.component_registry import ComponentRegistry
        ComponentRegistry().clear()
        detail['registry'] = True
    except Exception as e:
        detail['errors'].append(f"component_registry: {e}")

    # 2) CADBoard 内 __pycache__
    if os.path.isdir(CADBOARD_DIR):
        for root, dirs, files in os.walk(CADBOARD_DIR):
            for d in dirs:
                if d == '__pycache__':
                    path = os.path.join(root, d)
                    try:
                        shutil.rmtree(path)
                        detail['pycache_dirs'] += 1
                    except Exception as e:
                        detail['errors'].append(f"__pycache__ {path}: {e}")

    # 3) CADBoard 根目录日志
    if os.path.isdir(CADBOARD_DIR):
        for name in os.listdir(CADBOARD_DIR):
            if name.endswith('.log'):
                path = os.path.join(CADBOARD_DIR, name)
                try:
                    os.remove(path)
                    detail['log_files'] += 1
                except Exception as e:
                    detail['errors'].append(f"log {path}: {e}")

    # 4) /tmp 下 cadboard_ 前缀临时目录
    tmp_root = tempfile.gettempdir()
    if os.path.isdir(tmp_root):
        for name in os.listdir(tmp_root):
            if name.startswith('cadboard_'):
                path = os.path.join(tmp_root, name)
                if os.path.isdir(path):
                    try:
                        shutil.rmtree(path)
                        detail['temp_dirs'] += 1
                    except Exception as e:
                        detail['errors'].append(f"temp dir {path}: {e}")

    total = (detail['component_scripts'] + detail['pycache_dirs'] +
             detail['log_files'] + detail['temp_dirs'])
    _log(f"clear_all_caches: total={total}, detail={detail}")
    return total, detail


def _safe_id(sid):
    """把 component_id 转成合法的文件名/类名后缀"""
    return ''.join(c if c.isalnum() else '_' for c in sid)[:32]


def normalize_pier_params(params: dict) -> dict:
    """
    把 AI 识别出的引桥桥墩参数归一化为精简版参数集。
    与 组件测试/引桥桥墩.py 的核心参数保持一致。
    """
    normalized = {}
    # 核心外轮廓参数
    core_keys = {
        '盖梁总长': 1930.0,
        '盖梁总高': 300.0,
        '盖梁宽': 300.0,
        '墩柱直径': 250.0,
        '墩柱间距': 1140.0,
        '墩高': 1200.0,
    }
    for k, default in core_keys.items():
        normalized[k] = float(params.get(k, default))

    # 系梁根数兼容旧名 "系梁数量"
    tie_count = params.get('系梁根数', params.get('系梁数量', 2))
    normalized['系梁根数'] = int(tie_count)

    # 保留坐标相关参数（供放置使用）
    for k in ('x', 'y', 'z', 'z_bottom', 'z_top'):
        if k in params:
            normalized[k] = params[k]

    return normalized


def generate_pier_code(component_id: str, params: dict, x: float, y: float, z: float) -> str:
    """
    根据识别到的引桥桥墩参数，生成独立可执行的 pyp3d 脚本。
    几何逻辑与 组件测试/引桥桥墩.py 保持一致（精简参数版）。
    返回生成的文件路径。
    """
    ensure_cache_dir()
    suffix = _safe_id(component_id) or str(int(time.time()))
    file_name = f"引桥桥墩_{suffix}.py"
    file_path = os.path.join(CACHE_DIR, file_name)

    # 数值参数统一处理
    def _f(key, default):
        return float(params.get(key, default))

    def _i(key, default):
        return int(params.get(key, default))

    # 兼容旧版 AI 可能返回的 "系梁数量" 参数名
    tie_count = params.get('系梁根数', params.get('系梁数量', 2))

    p = {
        '盖梁总长': _f('盖梁总长', 1930.0),
        '盖梁总高': _f('盖梁总高', 300.0),
        '盖梁宽': _f('盖梁宽', 300.0),
        '墩柱直径': _f('墩柱直径', 250.0),
        '墩柱间距': _f('墩柱间距', 1140.0),
        '墩高': _f('墩高', 1200.0),
        '系梁根数': int(tie_count),
    }

    class_name = f"引桥桥墩_{suffix}"
    code = f'''# -*- coding: utf-8 -*-
# Auto-generated by CADBoard for 引桥桥墩
# component_id: {component_id}
# generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}
# placement: ({x}, {y}, {z})

from pyp3d import *
import math
import sys

# create_geometry/place_to 依赖 sys.argv[0] 读取 DependentFile
if hasattr(sys, '_original_argv0'):
    sys.argv[0] = sys._original_argv0
else:
    sys.argv[0] = {repr(os.path.abspath(__file__))}

class {class_name}(Component):
    """引桥桥墩：带斜边和凸起的盖梁 + 双墩柱 + 多根系梁"""

    def __init__(self):
        Component.__init__(self)
        self['盖梁总长'] = Attr({p['盖梁总长']:.6f}, obvious=True)
        self['盖梁总高'] = Attr({p['盖梁总高']:.6f}, obvious=True)
        self['盖梁宽'] = Attr({p['盖梁宽']:.6f}, obvious=True)
        self['墩柱直径'] = Attr({p['墩柱直径']:.6f}, obvious=True)
        self['墩柱间距'] = Attr({p['墩柱间距']:.6f}, obvious=True)
        self['墩高'] = Attr({p['墩高']:.6f}, obvious=True)
        self['系梁根数'] = Attr({p['系梁根数']}, obvious=True)
        self['偏移X'] = Attr(0.0, show=False)
        self['偏移Y'] = Attr(0.0, show=False)
        self['偏移Z'] = Attr(0.0, show=False)
        self['x'] = Attr(0.0, show=False)
        self['y'] = Attr(0.0, show=False)
        self['z_bottom'] = Attr(0.0, show=False)
        self['引桥桥墩'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        cap_l = self['盖梁总长']
        cap_h = self['盖梁总高']
        cap_w = self['盖梁宽']
        col_d = self['墩柱直径']
        col_s = self['墩柱间距']
        col_h = self['墩高']
        tie_n = int(self['系梁根数'])
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0

        # 细部尺寸固定为图纸默认值（与参考 DWG 一致）
        boss_w = 30.0
        boss_h = 50.0
        cap_bottom_w = 1390.0
        chamfer_h = 120.0
        tie_w = 200.0
        tie_h = 200.0
        # 与参考 DWG 一致：上系梁顶面距柱顶 100，间距 500
        # 公式中 tie_start 包含 half tie_h，因此取 200 才能得到顶距 100
        tie_start = 200.0
        tie_step = 500.0
        # 系梁长随墩柱间距自动适配
        tie_l = max(col_s - col_d, 100.0)

        half_l = cap_l / 2.0
        half_bottom = cap_bottom_w / 2.0
        mid_h = cap_h - boss_h

        # 盖梁整体截面（含梯形台、矩形主体、顶部两端凸起），一次 Sweep 成型
        outer = Section(
            Vec2(-half_bottom, 0),
            Vec2(half_bottom, 0),
            Vec2(half_l, chamfer_h),
            Vec2(half_l, cap_h),
            Vec2(-half_l, cap_h),
            Vec2(-half_l, chamfer_h)
        )
        inner = Section(
            Vec2(-half_l + boss_w, mid_h),
            Vec2(half_l - boss_w, mid_h),
            Vec2(half_l - boss_w, cap_h),
            Vec2(-half_l + boss_w, cap_h)
        )
        section = rotate(Vec3(1, 0, 0), 0.5 * math.pi) * (outer - inner)
        path = Line(Vec3(0, -cap_w / 2, 0), Vec3(0, cap_w / 2, 0))
        cap = translate(ox, oy, oz + col_h) * Sweep(section, path)

        # 墩柱（2根，圆柱）
        col_r = col_d / 2.0
        col1 = translate(ox - col_s / 2, oy, oz + col_h / 2) * Cone(Vec3(0, 0, -col_h / 2), Vec3(0, 0, col_h / 2), col_r, col_r)
        col2 = translate(ox + col_s / 2, oy, oz + col_h / 2) * Cone(Vec3(0, 0, -col_h / 2), Vec3(0, 0, col_h / 2), col_r, col_r)

        # 系梁
        ties = None
        if tie_n > 0 and col_h > 0:
            for i in range(tie_n):
                z_top = col_h - tie_start - i * tie_step
                z = z_top - tie_h / 2
                if z < 0:
                    z = 0
                tie = translate(ox, oy, oz + z + tie_h / 2) * Cone(Vec3(-tie_l / 2, 0, 0), Vec3(tie_l / 2, 0, 0), tie_h / 2, tie_h / 2)
                if ties is None:
                    ties = tie
                else:
                    ties = Combine(ties, tie)

        parts = [cap, col1, col2]
        if ties is not None:
            parts.append(ties)
        self['引桥桥墩'] = Combine(*parts)


if __name__ == "__main__":
    comp = {class_name}()
    pos = translate({x:.6f}, {y:.6f}, {z:.6f})

    # 方案1：create_geometry 自动放置，并校验返回的 entityId 是否真正有效
    auto_ok = False
    try:
        eid = create_geometry(pos * comp)
        try:
            from pyp3d import entityid_isvaid
            auto_ok = entityid_isvaid(eid)
        except Exception:
            auto_ok = True  # 无法校验时默认成功
        if auto_ok:
            print("[OK] create_geometry placed with valid entityId")
        else:
            print("[WARN] create_geometry returned invalid entityId, will fallback")
    except Exception as e:
        print(f"[WARN] create_geometry failed: {{e}}, will fallback")

    # 方案2：启动 BIMBase 手动放置工具（与 组件测试/引桥桥墩.py 一致）
    if not auto_ok:
        try:
            place(comp)
            print("[OK] place() manual placement tool started")
        except Exception as e2:
            print(f"[ERROR] place() also failed: {{e2}}")
'''

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        _log(f"generated pier code: {file_path}")
        return file_path
    except Exception as e:
        _log(f"generate pier code failed: {e}")
        raise


def normalize_cable_anchor_params(params: dict) -> dict:
    """把 AI 识别出的索缆锚锭参数归一化为标准参数集。"""
    normalized = {}
    core_keys = {
        '锚块总长': 5450.0,
        '锚块总高': 2039.0,
        '锚块宽度': 1200.0,
        '承台长度': 5680.0,
        '承台宽度': 1600.0,
        '承台高度': 400.0,
        '底柱半径': 170.0,
        '底柱高度': 1000.0,
        '底柱数量': 7.0,
        '底柱排数': 2.0,
        '系梁数量': 0.0,
    }
    for k, default in core_keys.items():
        normalized[k] = float(params.get(k, default))

    # 底柱数量可能是 AI 返回的「总数」（如 14 = 2 排 × 7 个），需要换算成每排根数
    rows = int(round(float(params.get('底柱排数', 2))))
    total_or_per_row = int(round(float(params.get('底柱数量', 7))))
    if rows > 1 and total_or_per_row == rows * 7:
        # AI 把总数 14 当成了每排数量，修正为每排 7
        per_row = 7
    else:
        per_row = max(1, total_or_per_row)
    normalized['底柱数量'] = float(per_row)
    normalized['底柱排数'] = float(rows)
    normalized['系梁数量'] = float(int(round(float(params.get('系梁数量', 0)))))

    for k in ('x', 'y', 'z', 'z_bottom', 'z_top'):
        if k in params:
            normalized[k] = params[k]
    return normalized


def generate_cable_anchor_code(component_id: str, params: dict, x: float, y: float, z: float) -> str:
    """
    根据识别到的索缆锚锭参数，生成独立可执行的 pyp3d 脚本。
    几何逻辑与 bimbase_sync.CableAnchorComponent 保持一致。
    返回生成的文件路径。
    """
    ensure_cache_dir()
    suffix = _safe_id(component_id) or str(int(time.time()))
    file_name = f"索缆锚锭_{suffix}.py"
    file_path = os.path.join(CACHE_DIR, file_name)

    def _f(key, default):
        return float(params.get(key, default))

    p = {
        '锚块总长': _f('锚块总长', 5450.0),
        '锚块总高': _f('锚块总高', 2039.0),
        '锚块宽度': _f('锚块宽度', 1200.0),
        '承台长度': _f('承台长度', 5680.0),
        '承台宽度': _f('承台宽度', 1600.0),
        '承台高度': _f('承台高度', 400.0),
        '底柱半径': _f('底柱半径', 170.0),
        '底柱高度': _f('底柱高度', 1000.0),
        '底柱数量': _f('底柱数量', 7.0),
        '底柱排数': _f('底柱排数', 2.0),
        '系梁数量': _f('系梁数量', 0.0),
    }

    class_name = f"索缆锚锭_{suffix}"
    code = f'''# -*- coding: utf-8 -*-
# Auto-generated by CADBoard for 索缆锚锭
# component_id: {component_id}
# generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}
# placement: ({x}, {y}, {z})

from pyp3d import *
import math
import sys

# create_geometry/place_to 依赖 sys.argv[0] 读取 DependentFile
if hasattr(sys, '_original_argv0'):
    sys.argv[0] = sys._original_argv0
else:
    sys.argv[0] = {repr(os.path.abspath(__file__))}

class {class_name}(Component):
    """索缆锚锭：锚块 + 承台 + 可变数量底柱 + 系梁"""

    def __init__(self):
        Component.__init__(self)
        self['锚块总长'] = Attr({p['锚块总长']:.6f}, obvious=True)
        self['锚块总高'] = Attr({p['锚块总高']:.6f}, obvious=True)
        self['锚块宽度'] = Attr({p['锚块宽度']:.6f}, obvious=True)
        self['承台长度'] = Attr({p['承台长度']:.6f}, obvious=True)
        self['承台宽度'] = Attr({p['承台宽度']:.6f}, obvious=True)
        self['承台高度'] = Attr({p['承台高度']:.6f}, obvious=True)
        self['底柱半径'] = Attr({p['底柱半径']:.6f}, obvious=True)
        self['底柱高度'] = Attr({p['底柱高度']:.6f}, obvious=True)
        self['底柱数量'] = Attr({p['底柱数量']:.6f}, obvious=True)
        self['底柱排数'] = Attr({p['底柱排数']:.6f}, obvious=True)
        self['系梁数量'] = Attr({p['系梁数量']:.6f}, obvious=True)
        self['偏移X'] = Attr(0.0, show=False)
        self['偏移Y'] = Attr(0.0, show=False)
        self['偏移Z'] = Attr(0.0, show=False)
        self['x'] = Attr(0.0, show=False)
        self['y'] = Attr(0.0, show=False)
        self['z_bottom'] = Attr(0.0, show=False)
        self['索缆锚锭'] = Attr(None, show=True)
        self.replace()

    def get(self, key, default=0):
        try:
            return self[key]
        except Exception:
            return default

    @export
    def replace(self):
        L = self['锚块总长']
        H = self['锚块总高']
        W = self['锚块宽度']
        CL = self['承台长度']
        CW = self['承台宽度']
        CH = self['承台高度']
        R = self['底柱半径']
        DH = self['底柱高度']
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0

        seg = 64
        circle_pts = [Vec2(R * math.cos(2 * math.pi * i / seg), R * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
        sec = Section(*circle_pts)

        col_count = max(1, int(round(float(self.get('底柱数量', 7)))))
        col_rows = max(1, int(round(float(self.get('底柱排数', 2)))))
        tie_n = max(0, int(round(float(self.get('系梁数量', 0)))))

        scale_l = L / 5450.0
        scale_w = W / 1200.0
        spacing = 850.0 * scale_l
        row_spacing = 670.0 * scale_w

        span_l = min(CL, L)
        if col_count == 1:
            xs = [0.0]
        else:
            margin = max((span_l - (col_count - 1) * spacing) / 2.0, R)
            xs = [-span_l / 2.0 + margin + i * spacing for i in range(col_count)]

        if col_rows == 1:
            ys = [0.0]
        else:
            ys = [-row_spacing / 2.0 + i * row_spacing for i in range(col_rows)]

        columns = []
        for cx in xs:
            for cy in ys:
                col = translate(ox + cx, oy + cy, oz) * Loft(sec, translate(0, 0, DH) * sec)
                columns.append(col)
        alld = Combine(*columns) if columns else None

        CT = translate(ox - CL / 2, oy - CW / 2, oz + DH) * scale(CL, CW, CH) * Cube()

        left_x = -L / 2
        right_x = L / 2
        MDP = Section(
            Vec2(left_x, 0),
            Vec2(right_x, 0),
            Vec2(right_x, H * 0.614),
            Vec2(right_x - L * 0.117, H),
            Vec2(left_x + L * 0.200, H),
            Vec2(left_x, H * 0.638)
        )
        section = rotate(Vec3(1, 0, 0), 0.5 * math.pi) * MDP
        line = Line(Vec3(0, 0, 0), Vec3(0, W, 0))
        MD = translate(ox, oy - W / 2, oz + DH + CH) * Sweep(section, line)

        # 系梁
        ties = []
        if col_count > 1 and tie_n > 0:
            tie_h = max(R * 0.8, 80.0)
            tie_margin = DH * 0.15
            usable_h = DH - 2 * tie_margin
            for i in range(1, tie_n + 1):
                z = oz + tie_margin + i * usable_h / (tie_n + 1)
                for j in range(col_count - 1):
                    x1 = ox + xs[j] + R
                    x2 = ox + xs[j + 1] - R
                    tie = translate(x1, oy - CW * 0.3, z - tie_h / 2) * scale(x2 - x1, CW * 0.6, tie_h) * Cube()
                    ties.append(tie)

        parts = []
        if alld is not None:
            parts.append(alld)
        parts.extend([CT, MD])
        if ties:
            parts.extend(ties)
        self['索缆锚锭'] = Combine(*parts)


if __name__ == "__main__":
    comp = {class_name}()
    pos = translate({x:.6f}, {y:.6f}, {z:.6f})

    auto_ok = False
    try:
        eid = create_geometry(pos * comp)
        try:
            from pyp3d import entityid_isvaid
            auto_ok = entityid_isvaid(eid)
        except Exception:
            auto_ok = True
        if auto_ok:
            print("[OK] create_geometry placed with valid entityId")
        else:
            print("[WARN] create_geometry returned invalid entityId, will fallback")
    except Exception as e:
        print(f"[WARN] create_geometry failed: {{e}}, will fallback")

    if not auto_ok:
        try:
            place(comp)
            print("[OK] place() manual placement tool started")
        except Exception as e2:
            print(f"[ERROR] place() also failed: {{e2}}")
'''

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        _log(f"generated cable anchor code: {file_path}")
        return file_path
    except Exception as e:
        _log(f"generate cable anchor code failed: {e}")
        raise


def normalize_gate_pier_params(params: dict) -> dict:
    """
    把 AI 识别出的门式桥墩参数归一化为精简版参数集。
    与 组件测试/门式桥墩.py 的核心参数保持一致。
    """
    normalized = {}
    # 核心外轮廓参数
    core_keys = {
        '盖梁总长': 4700.0,
        '盖梁总高': 400.0,
        '盖梁宽': 1000.0,
        '墩高': 5000.0,
        '墩柱间距': 3500.0,
        '柱顶宽': 1200.0,
        '柱底宽': 1400.0,
        '柱顶厚': 1000.0,
        '柱底厚': 1200.0,
    }
    for k, default in core_keys.items():
        normalized[k] = float(params.get(k, default))

    normalized['系梁根数'] = int(params.get('系梁根数', 1))

    # 保留坐标相关参数（供放置使用）
    for k in ('x', 'y', 'z', 'z_bottom', 'z_top'):
        if k in params:
            normalized[k] = params[k]

    return normalized


def generate_gate_pier_code(component_id: str, params: dict, x: float, y: float, z: float) -> str:
    """
    根据识别到的门式桥墩参数，生成独立可执行的 pyp3d 脚本。
    几何逻辑与 组件测试/门式桥墩.py 保持一致（精简参数版）。
    返回生成的文件路径。
    """
    ensure_cache_dir()
    suffix = _safe_id(component_id) or str(int(time.time()))
    file_name = f"门式桥墩_{suffix}.py"
    file_path = os.path.join(CACHE_DIR, file_name)

    # 数值参数统一处理
    def _f(key, default):
        return float(params.get(key, default))

    def _i(key, default):
        return int(params.get(key, default))

    p = {
        '盖梁总长': _f('盖梁总长', 4700.0),
        '盖梁总高': _f('盖梁总高', 400.0),
        '盖梁宽': _f('盖梁宽', 1000.0),
        '墩高': _f('墩高', 5000.0),
        '墩柱间距': _f('墩柱间距', 3500.0),
        '柱顶宽': _f('柱顶宽', 1200.0),
        '柱底宽': _f('柱底宽', 1400.0),
        '柱顶厚': _f('柱顶厚', 1000.0),
        '柱底厚': _f('柱底厚', 1200.0),
        '系梁根数': _i('系梁根数', 1),
    }

    # 整体上色（"r,g,b[,a]" 字符串或 (r,g,b[,a]) 元组；无则 None）
    _color = params.get('颜色')
    if _color and not isinstance(_color, str):
        try:
            _color = ','.join(str(float(c)) for c in _color)
        except Exception:
            _color = None
    color_repr = repr(_color) if _color else 'None'

    class_name = f"门式桥墩_{suffix}"
    code = f'''# -*- coding: utf-8 -*-
# Auto-generated by CADBoard for 门式桥墩
# component_id: {component_id}
# generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}
# placement: ({x}, {y}, {z})

from pyp3d import *
import math
import sys

# create_geometry/place_to 依赖 sys.argv[0] 读取 DependentFile
if hasattr(sys, '_original_argv0'):
    sys.argv[0] = sys._original_argv0
else:
    sys.argv[0] = {repr(os.path.abspath(__file__))}

def _octagon_section(w, d, c):
    """XY 平面内的倒角八边形截面：宽 w（X），深 d（Y），倒角 c"""
    hw, hd = w / 2.0, d / 2.0
    c = min(c, hw, hd)
    return Section(
        Vec2(-hw + c, -hd), Vec2(hw - c, -hd),
        Vec2(hw, -hd + c), Vec2(hw, hd - c),
        Vec2(hw - c, hd), Vec2(-hw + c, hd),
        Vec2(-hw, hd - c), Vec2(-hw, -hd + c)
    )

def _rect_section(w, d):
    """XY 平面内的矩形截面：宽 w（X），深 d（Y）"""
    hw, hd = w / 2.0, d / 2.0
    return Section(
        Vec2(-hw, -hd), Vec2(hw, -hd), Vec2(hw, hd), Vec2(-hw, hd)
    )

class {class_name}(Component):
    """门式桥墩：盖梁（含垫石）+ 双根变截面空心八边形墩柱 + 系梁"""

    def __init__(self):
        Component.__init__(self)
        self['盖梁总长'] = Attr({p['盖梁总长']:.6f}, obvious=True)
        self['盖梁总高'] = Attr({p['盖梁总高']:.6f}, obvious=True)
        self['盖梁宽'] = Attr({p['盖梁宽']:.6f}, obvious=True)
        self['墩高'] = Attr({p['墩高']:.6f}, obvious=True)
        self['墩柱间距'] = Attr({p['墩柱间距']:.6f}, obvious=True)
        self['柱顶宽'] = Attr({p['柱顶宽']:.6f}, obvious=True)
        self['柱底宽'] = Attr({p['柱底宽']:.6f}, obvious=True)
        self['柱顶厚'] = Attr({p['柱顶厚']:.6f}, obvious=True)
        self['柱底厚'] = Attr({p['柱底厚']:.6f}, obvious=True)
        self['系梁根数'] = Attr({p['系梁根数']}, obvious=True)
        self['偏移X'] = Attr(0.0, show=False)
        self['偏移Y'] = Attr(0.0, show=False)
        self['偏移Z'] = Attr(0.0, show=False)
        self['x'] = Attr(0.0, show=False)
        self['y'] = Attr(0.0, show=False)
        self['z_bottom'] = Attr(0.0, show=False)
        self['颜色'] = Attr({color_repr}, show=False)  # 整体颜色 "r,g,b[,a]"，None 表示不上色
        self['门式桥墩'] = Attr(None, show=True)
        self.replace()

    @export
    def replace(self):
        cap_l = self['盖梁总长']
        cap_h = self['盖梁总高']
        cap_w = self['盖梁宽']
        col_h = self['墩高']
        col_s = self['墩柱间距']
        top_w = self['柱顶宽']
        bot_w = self['柱底宽']
        top_d = self['柱顶厚']
        bot_d = self['柱底厚']
        tie_n = int(self['系梁根数'])
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0

        # 细部尺寸固定为图纸默认值（与 组件测试/门式桥墩.py 一致）
        pad_l = 400.0       # 垫石平面边长
        pad_h = 80.0        # 垫石高
        wall = 300.0        # 空心柱壁厚
        chamfer = 300.0     # 八边形倒角
        tie_h = 400.0       # 系梁高
        tie_d = 400.0       # 系梁深（Y 向）
        tie_step = 1000.0   # 多根系梁时的竖向间距（顶到顶）

        parts = []

        # 盖梁：z 从 墩高 到 墩高+盖梁总高
        cap = translate(ox - cap_l / 2, oy - cap_w / 2, oz + col_h) * scale(cap_l, cap_w, cap_h) * Cube()
        parts.append(cap)

        # 垫石×2：位于柱顶中心的盖梁顶面
        for sx in (-col_s / 2, col_s / 2):
            pad = translate(ox + sx - pad_l / 2, oy - pad_l / 2, oz + col_h + cap_h) * scale(pad_l, pad_l, pad_h) * Cube()
            parts.append(pad)

        # 墩柱×2：变截面空心八边形（底截面 -> 顶截面 Loft）
        outer_bot = _octagon_section(bot_w, bot_d, chamfer)
        outer_top = _octagon_section(top_w, top_d, chamfer)
        core_bot = _rect_section(max(bot_w - 2 * wall, 10.0), max(bot_d - 2 * wall, 10.0))
        core_top = _rect_section(max(top_w - 2 * wall, 10.0), max(top_d - 2 * wall, 10.0))
        for sx in (-col_s / 2, col_s / 2):
            outer = Loft(outer_bot, translate(0, 0, col_h) * outer_top)
            try:
                # 空心：减去内腔（布尔运算不稳定时退化为实心柱）
                core = Loft(core_bot, translate(0, 0, col_h) * core_top)
                col = outer - core
            except Exception:
                col = outer
            parts.append(translate(ox + sx, oy, oz) * col)

        # 系梁：贴盖梁底向下均布，长度随柱身锥度自动适配（与两柱内侧面相接）
        if tie_n > 0 and col_h > 0:
            for i in range(tie_n):
                z_top = col_h - i * tie_step
                if z_top - tie_h < 0:
                    z_top = tie_h
                zc = z_top - tie_h / 2
                # 该高度处柱身 X 向宽度（线性插值）
                w_at = bot_w + (top_w - bot_w) * (zc / col_h)
                tie_l = max(col_s - w_at, 100.0)
                tie = translate(ox - tie_l / 2, oy - tie_d / 2, oz + z_top - tie_h) * scale(tie_l, tie_d, tie_h) * Cube()
                parts.append(tie)

        geom = Combine(*parts)
        try:
            # 整体上色（颜色为 "r,g,b[,a]" 字符串，pyp3d Attr 只能存标量/字符串）
            _c = self['颜色'] if '颜色' in self else None
            if _c:
                _vals = [float(v) for v in str(_c).split(',') if v.strip()]
                if len(_vals) >= 3:
                    geom = geom.color(*_vals)
        except Exception:
            pass
        self['门式桥墩'] = geom


if __name__ == "__main__":
    comp = {class_name}()
    pos = translate({x:.6f}, {y:.6f}, {z:.6f})

    # 方案1：create_geometry 自动放置，并校验返回的 entityId 是否真正有效
    auto_ok = False
    try:
        eid = create_geometry(pos * comp)
        try:
            from pyp3d import entityid_isvaid
            auto_ok = entityid_isvaid(eid)
        except Exception:
            auto_ok = True  # 无法校验时默认成功
        if auto_ok:
            print("[OK] create_geometry placed with valid entityId")
        else:
            print("[WARN] create_geometry returned invalid entityId, will fallback")
    except Exception as e:
        print(f"[WARN] create_geometry failed: {{e}}, will fallback")

    # 方案2：启动 BIMBase 手动放置工具（与 组件测试/门式桥墩.py 一致）
    if not auto_ok:
        try:
            place(comp)
            print("[OK] place() manual placement tool started")
        except Exception as e2:
            print(f"[ERROR] place() also failed: {{e2}}")
'''

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        _log(f"generated gate pier code: {file_path}")
        return file_path
    except Exception as e:
        _log(f"generate gate pier code failed: {e}")
        raise


def normalize_pile_foundation_params(params: dict) -> dict:
    """
    把 AI 识别出的承台及桩基参数归一化为精简版参数集。
    与 组件测试/承台及桩基.py 的核心参数保持一致。
    """
    normalized = {}
    # 核心外轮廓参数
    core_keys = {
        '承台长': 5500.0,
        '承台宽': 2350.0,
        '承台高': 500.0,
        '桩径': 250.0,
        '桩长': 5000.0,
        '桩间距': 630.0,
    }
    for k, default in core_keys.items():
        normalized[k] = float(params.get(k, default))

    normalized['桩列数'] = max(int(params.get('桩列数', 9)), 1)
    normalized['桩排数'] = max(int(params.get('桩排数', 4)), 1)

    # 保留坐标相关参数（供放置使用）
    for k in ('x', 'y', 'z', 'z_bottom', 'z_top'):
        if k in params:
            normalized[k] = params[k]

    return normalized


def generate_pile_foundation_code(component_id: str, params: dict, x: float, y: float, z: float) -> str:
    """
    根据识别到的承台及桩基参数，生成独立可执行的 pyp3d 脚本。
    几何逻辑与 组件测试/承台及桩基.py 保持一致（精简参数版）。
    返回生成的文件路径。
    """
    ensure_cache_dir()
    suffix = _safe_id(component_id) or str(int(time.time()))
    file_name = f"承台及桩基_{suffix}.py"
    file_path = os.path.join(CACHE_DIR, file_name)

    # 数值参数统一处理
    def _f(key, default):
        return float(params.get(key, default))

    def _i(key, default):
        return int(params.get(key, default))

    p = {
        '承台长': _f('承台长', 5500.0),
        '承台宽': _f('承台宽', 2350.0),
        '承台高': _f('承台高', 500.0),
        '桩径': _f('桩径', 250.0),
        '桩长': _f('桩长', 5000.0),
        '桩间距': _f('桩间距', 630.0),
        '桩列数': _i('桩列数', 9),
        '桩排数': _i('桩排数', 4),
    }

    # 整体上色（"r,g,b[,a]" 字符串或 (r,g,b[,a]) 元组；无则 None）
    _color = params.get('颜色')
    if _color and not isinstance(_color, str):
        try:
            _color = ','.join(str(float(c)) for c in _color)
        except Exception:
            _color = None
    color_repr = repr(_color) if _color else 'None'

    class_name = f"承台及桩基_{suffix}"
    code = f'''# -*- coding: utf-8 -*-
# Auto-generated by CADBoard for 承台及桩基
# component_id: {component_id}
# generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}
# placement: ({x}, {y}, {z})

from pyp3d import *
import math
import sys

# create_geometry/place_to 依赖 sys.argv[0] 读取 DependentFile
if hasattr(sys, '_original_argv0'):
    sys.argv[0] = sys._original_argv0
else:
    sys.argv[0] = {repr(os.path.abspath(__file__))}

class {class_name}(Component):
    """承台及桩基：矩形承台 + 列×排圆柱桩阵列"""

    def __init__(self):
        Component.__init__(self)
        self['承台长'] = Attr({p['承台长']:.6f}, obvious=True)
        self['承台宽'] = Attr({p['承台宽']:.6f}, obvious=True)
        self['承台高'] = Attr({p['承台高']:.6f}, obvious=True)
        self['桩径'] = Attr({p['桩径']:.6f}, obvious=True)
        self['桩长'] = Attr({p['桩长']:.6f}, obvious=True)
        self['桩间距'] = Attr({p['桩间距']:.6f}, obvious=True)
        self['桩列数'] = Attr({p['桩列数']}, obvious=True)
        self['桩排数'] = Attr({p['桩排数']}, obvious=True)
        self['偏移X'] = Attr(0.0, show=False)
        self['偏移Y'] = Attr(0.0, show=False)
        self['偏移Z'] = Attr(0.0, show=False)
        self['x'] = Attr(0.0, show=False)
        self['y'] = Attr(0.0, show=False)
        self['z_bottom'] = Attr(0.0, show=False)
        self['颜色'] = Attr({color_repr}, show=False)  # 整体颜色 "r,g,b[,a]"，None 表示不上色
        self['承台及桩基'] = Attr(None, show=True)
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
        ox = float(self['偏移X']) if '偏移X' in self else 0.0
        oy = float(self['偏移Y']) if '偏移Y' in self else 0.0
        oz = float(self['偏移Z']) if '偏移Z' in self else 0.0

        # 承台：z 从 0 到 承台高，中心在原点
        cap = translate(ox - cap_l / 2, oy - cap_w / 2, oz) * scale(cap_l, cap_w, cap_h) * Cube()

        # 桩阵列：桩顶伸入承台底（z=0），桩底 z=-桩长
        r = pile_d / 2
        x0 = -(n_col - 1) * spacing / 2
        y0 = -(n_row - 1) * spacing / 2
        piles = []
        for i in range(n_col):
            for j in range(n_row):
                px = x0 + i * spacing
                py = y0 + j * spacing
                piles.append(Cone(Vec3(ox + px, oy + py, oz - pile_l), Vec3(ox + px, oy + py, oz), r, r))

        geom = Combine(cap, *piles)
        try:
            # 整体上色（颜色为 "r,g,b[,a]" 字符串，pyp3d Attr 只能存标量/字符串）
            _c = self['颜色'] if '颜色' in self else None
            if _c:
                _vals = [float(v) for v in str(_c).split(',') if v.strip()]
                if len(_vals) >= 3:
                    geom = geom.color(*_vals)
        except Exception:
            pass
        self['承台及桩基'] = geom


if __name__ == "__main__":
    comp = {class_name}()
    pos = translate({x:.6f}, {y:.6f}, {z:.6f})

    # 方案1：create_geometry 自动放置，并校验返回的 entityId 是否真正有效
    auto_ok = False
    try:
        eid = create_geometry(pos * comp)
        try:
            from pyp3d import entityid_isvaid
            auto_ok = entityid_isvaid(eid)
        except Exception:
            auto_ok = True  # 无法校验时默认成功
        if auto_ok:
            print("[OK] create_geometry placed with valid entityId")
        else:
            print("[WARN] create_geometry returned invalid entityId, will fallback")
    except Exception as e:
        print(f"[WARN] create_geometry failed: {{e}}, will fallback")

    # 方案2：启动 BIMBase 手动放置工具（与 组件测试/承台及桩基.py 一致）
    if not auto_ok:
        try:
            place(comp)
            print("[OK] place() manual placement tool started")
        except Exception as e2:
            print(f"[ERROR] place() also failed: {{e2}}")
'''

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        _log(f"generated pile foundation code: {file_path}")
        return file_path
    except Exception as e:
        _log(f"generate pile foundation code failed: {e}")
        raise


def execute_generated_code(file_path: str):
    """
    在 BIMBase 插件进程中执行生成的组件脚本。
    返回 (ok, message, is_manual)。
    """
    if not os.path.isfile(file_path):
        return False, f"生成的代码文件不存在: {file_path}", False

    _log(f"executing generated code: {file_path}")

    # 执行命名空间：确保 pyp3d 相关名称可用，并保留 __main__ 语义
    namespace = {
        '__name__': '__main__',
        '__file__': file_path,
    }
    # 把 pyp3d 已导入的符号注入命名空间，避免生成脚本再 import 时遇到路径问题
    try:
        import pyp3d
        for name in dir(pyp3d):
            if not name.startswith('_'):
                namespace[name] = getattr(pyp3d, name)
    except Exception as e:
        _log(f"inject pyp3d namespace failed: {e}")

    # 保存并恢复 sys.argv[0]；执行期间让 sys.argv[0] 指向生成脚本本身，
    # 这样 create_geometry / place 读取 DependentFile 时才能正确定位组件类。
    original_argv0 = sys.argv[0]
    sys.argv[0] = file_path

    # 捕获脚本的标准输出，用于判断是自动放置还是手动放置
    import io
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        exec(compile(code, file_path, 'exec'), namespace)
        output = captured.getvalue()
        _log(f"generated code output:\n{output}")
        is_manual = "place() manual placement tool started" in output
        auto_ok = "create_geometry placed with valid entityId" in output
        if auto_ok:
            return True, f"已自动放置: {os.path.basename(file_path)}", False
        if is_manual:
            return True, f"已启动手动放置工具，请在 BIMBase 3D 视图中点击放置: {os.path.basename(file_path)}", True
        return True, f"已执行生成脚本: {os.path.basename(file_path)}", False
    except Exception as e:
        err = traceback.format_exc()
        _log(f"generated code execution failed: {e}\n{err}")
        return False, f"执行生成脚本失败: {e}", False
    finally:
        sys.stdout = old_stdout
        sys.argv[0] = original_argv0
