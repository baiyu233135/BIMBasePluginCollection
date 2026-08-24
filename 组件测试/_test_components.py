# -*- coding: utf-8 -*-
"""
组件测试脚本：验证索缆锚锭、引桥桥墩能否正常实例化与放置

使用方法：
1. 在 BIMBase 的 Python 控制台中执行：
   exec(open(r"C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\组件测试\_test_components.py", encoding="utf-8").read())
2. 或在 BIMBase 中通过插件命令运行本文件。
"""

from pyp3d import *

print("=== 开始测试组件 ===")

# 测试基础 API
print("\n[1] 测试基础几何 API")
try:
    cube = scale(100, 100, 100) * Cube()
    print("  [OK] Cube + scale")
except Exception as e:
    print(f"  [ERR] Cube + scale: {type(e).__name__}: {e}")

try:
    cone = Cone(Vec3(0, 0, 0), Vec3(0, 0, 100), 50, 50)
    print("  [OK] Cone 圆柱")
except Exception as e:
    print(f"  [ERR] Cone: {type(e).__name__}: {e}")

try:
    section = Section(Vec2(-100, 0), Vec2(100, 0), Vec2(50, 200), Vec2(-50, 200))
    path = Line(Vec3(0, -50, 0), Vec3(0, 50, 0))
    sweep = Sweep(section, path)
    print("  [OK] Section + Sweep")
except Exception as e:
    print(f"  [ERR] Section + Sweep: {type(e).__name__}: {e}")

try:
    a = scale(100, 100, 100) * Cube()
    b = Cone(Vec3(0, 0, 0), Vec3(0, 0, 100), 50, 50)
    c = Combine(a, b)
    print("  [OK] Combine")
except Exception as e:
    print(f"  [ERR] Combine: {type(e).__name__}: {e}")

# 测试索缆锚锭
print("\n[2] 测试索缆锚锭")
try:
    from 索缆锚锭 import 索缆锚锭
    a = 索缆锚锭()
    print("  [OK] 索缆锚锭实例化成功")
    try:
        place(a)
        print("  [OK] 索缆锚锭 place 成功")
    except Exception as e:
        print(f"  [ERR] 索缆锚锭 place: {type(e).__name__}: {e}")
except Exception as e:
    print(f"  [ERR] 索缆锚锭实例化: {type(e).__name__}: {e}")

# 测试引桥桥墩
print("\n[3] 测试引桥桥墩")
try:
    from 引桥桥墩 import 引桥桥墩
    b = 引桥桥墩()
    print("  [OK] 引桥桥墩实例化成功")
    try:
        place(b)
        print("  [OK] 引桥桥墩 place 成功")
    except Exception as e:
        print(f"  [ERR] 引桥桥墩 place: {type(e).__name__}: {e}")
except Exception as e:
    print(f"  [ERR] 引桥桥墩实例化: {type(e).__name__}: {e}")

# 测试直线
print("\n[4] 测试直线")
try:
    from 直线 import 直线
    c = 直线()
    print("  [OK] 直线实例化成功")
    try:
        place(c)
        print("  [OK] 直线 place 成功")
    except Exception as e:
        print(f"  [ERR] 直线 place: {type(e).__name__}: {e}")
except Exception as e:
    print(f"  [ERR] 直线实例化: {type(e).__name__}: {e}")

# 测试曲线
print("\n[5] 测试曲线")
try:
    from 曲线 import 曲线
    d = 曲线()
    print("  [OK] 曲线实例化成功")
    try:
        place(d)
        print("  [OK] 曲线 place 成功")
    except Exception as e:
        print(f"  [ERR] 曲线 place: {type(e).__name__}: {e}")
except Exception as e:
    print(f"  [ERR] 曲线实例化: {type(e).__name__}: {e}")

# 测试门式桥墩
print("\n[6] 测试门式桥墩")
try:
    from 门式桥墩 import 门式桥墩
    e1 = 门式桥墩()
    print("  [OK] 门式桥墩实例化成功")
    try:
        place(e1)
        print("  [OK] 门式桥墩 place 成功")
    except Exception as e:
        print(f"  [ERR] 门式桥墩 place: {type(e).__name__}: {e}")
except Exception as e:
    print(f"  [ERR] 门式桥墩实例化: {type(e).__name__}: {e}")

# 测试承台及桩基
print("\n[7] 测试承台及桩基")
try:
    from 承台及桩基 import 承台及桩基
    f1 = 承台及桩基()
    print("  [OK] 承台及桩基实例化成功")
    try:
        place(f1)
        print("  [OK] 承台及桩基 place 成功")
    except Exception as e:
        print(f"  [ERR] 承台及桩基 place: {type(e).__name__}: {e}")
except Exception as e:
    print(f"  [ERR] 承台及桩基实例化: {type(e).__name__}: {e}")

print("\n=== 测试结束 ===")
