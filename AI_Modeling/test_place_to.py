# -*- coding: utf-8 -*-
"""
测试 place_to 和 replace_noumenon 功能
在 BIMBase 底部命令行中输入：
    exec(open(r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\CADBoard\test_place_to.py').read())
"""
import sys
import os
import math
import traceback

# 确保当前目录在路径中
plugin_dir = r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\CADBoard'
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# 临时修改 sys.argv[0] 以便 place/place_to 能读取 DependentFile
original_argv0 = sys.argv[0]
sys.argv[0] = os.path.join(plugin_dir, 'aim_bimbase_sync.py')

log_path = os.path.join(plugin_dir, 'test_place_to_output.txt')

def log(*args):
    line = ' '.join(str(a) for a in args)
    try:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass
    print(line)

# 清空旧日志
with open(log_path, 'w', encoding='utf-8') as f:
    f.write('')

log("=" * 60)
log("TEST PLACE_TO & REPLACE_NOUMENON")
log("=" * 60)

# ---------- 导入测试 ----------
try:
    from pyp3d import (
        Component, Attr, Line, Section, Sweep, Cube, Sphere, Cone,
        Vec2, Vec3, Point, place, place_to, scale, translate, rotation,
        get_all_instancekey, get_noumKV_from_instancekey, get_noumenon_from_instancekey,
        get_datakey_from_entity, get_entityid_from_boxselection, get_current_entityId,
        entityid_isvaid, replace_noumenon,
    )
    log("✅ pyp3d imports OK")
except Exception as e:
    log("❌ pyp3d import failed:", e)
    traceback.print_exc()
    sys.argv[0] = original_argv0
    raise

# ---------- Test 1: place_to 基础测试 ----------
log("\n--- Test 1: place_to with translate(x,y,z) ---")
try:
    class TestCylinder(Component):
        def __init__(self, radius=100, height=200):
            super().__init__()
            self['半径'] = Attr(float(radius), show=True)
            self['高度'] = Attr(float(height), show=True)
            self.replace()
        def replace(self):
            r = self['半径']
            h = self['高度']
            segments = 32
            points = []
            for i in range(segments):
                angle = 2 * math.pi * i / segments
                points.append(Vec2(r * math.cos(angle), r * math.sin(angle)))
            section = Section(*points)
            path = Line(Vec3(0, 0, 0), Vec3(0, 0, h))
            self['圆柱'] = Sweep(section, path)

    test_comp = TestCylinder(radius=150, height=300)
    # 关键测试：place_to 直接放置到 (500, 600, 700)
    place_to(test_comp, translate(500, 600, 700))
    log("✅ place_to(translate(500, 600, 700)) SUCCESS")
except Exception as e:
    log("❌ place_to test FAILED:", e)
    traceback.print_exc()

# ---------- Test 2: 球体直接放置 ----------
log("\n--- Test 2: place Sphere ---")
try:
    # Sphere 是 pyp3d 内置的
    sphere_comp = scale(100, 100, 100) * Sphere()
    place_to(sphere_comp, translate(1000, 1000, 500))
    log("✅ Sphere place_to SUCCESS")
except Exception as e:
    log("❌ Sphere place_to FAILED:", e)
    traceback.print_exc()

# ---------- Test 3: 圆锥直接放置 ----------
log("\n--- Test 3: place Cone ---")
try:
    # Cone 需要参数，通过 scale 控制尺寸
    cone_comp = scale(100, 100, 200) * Cone()
    place_to(cone_comp, translate(1500, 1500, 0))
    log("✅ Cone place_to SUCCESS")
except Exception as e:
    log("❌ Cone place_to FAILED:", e)
    traceback.print_exc()

# ---------- Test 4: replace_noumenon 测试 ----------
log("\n--- Test 4: replace_noumenon ---")
try:
    keys = get_all_instancekey()
    log(f"  Total instances: {len(keys)}")
    if keys:
        first_key = keys[0]
        # 读取原参数
        old_params = get_noumKV_from_instancekey(first_key)
        log(f"  First instance params keys: {list(old_params.keys())[:8] if old_params else 'None'}")

        # 尝试用新组件替换
        new_comp = TestCylinder(radius=200, height=400)
        replace_noumenon(new_comp, first_key)
        log("✅ replace_noumenon SUCCESS (first instance replaced)")
    else:
        log("⚠️ No instances found, skip replace_noumenon test")
except Exception as e:
    log("❌ replace_noumenon FAILED:", e)
    traceback.print_exc()

# ---------- Test 5: 获取选中实体 ----------
log("\n--- Test 5: get_current_entityId ---")
try:
    cur_id = get_current_entityId()
    if cur_id and entityid_isvaid(cur_id):
        log(f"✅ get_current_entityId returned valid entity: {cur_id}")
        dk = get_datakey_from_entity(cur_id)
        if dk:
            params = get_noumKV_from_instancekey(dk)
            log(f"  Params: {params}")
    else:
        log("⚠️ No entity currently selected")
except Exception as e:
    log("❌ get_current_entityId FAILED:", e)
    traceback.print_exc()

log("\n" + "=" * 60)
log("TEST COMPLETE. See output at:", log_path)
log("=" * 60)

# 恢复 sys.argv[0]
sys.argv[0] = original_argv0
