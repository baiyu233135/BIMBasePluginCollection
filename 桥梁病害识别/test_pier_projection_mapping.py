# -*- coding: utf-8 -*-
"""
柱式桥墩病害投影映射 — 离线测试

纯数学验证，不依赖 pyp3d/BIMBase：
- 柱式桥墩 4 个投影面的几何参数正确性
- 系梁在墩柱高<=1500 时不可用
- 照片 bbox → 面局部坐标（等比铺满）映射正确性
- 病害颜色映射与未知类型兜底
- shadow_to_world 世界坐标换算

运行（开发机）：
    D:\\zengpython3.13.2\\python.exe 桥梁病害识别/test_pier_projection_mapping.py
"""

import os
import sys

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

from face_projection import (
    FaceProjectionEngine, get_available_faces, photo_bbox_to_shadow,
    DISEASE_COLOR_MAP,
)

# 柱式桥墩默认参数（与 桥梁组件/2-下部结构/柱式桥墩.py 一致）
PIER_PARAMS = {
    '墩柱高': 1700, '桩基径': 110,
    '盖梁宽度': 1220, '盖梁厚度': 230, '盖梁高': 95,
    '档墙高': 60, '系梁高': 200,
}

_passed = 0
_failed = 0


def check(name, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS {name}")
    else:
        _failed += 1
        print(f"  FAIL {name}  {detail}")


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_available_faces():
    print("[1] 可用面清单")
    faces = get_available_faces('柱式桥墩')
    check("柱式桥墩4个面", faces == ['左墩柱正面', '右墩柱正面', '系梁正面', '盖梁正面'], str(faces))
    check("未知类型为空", get_available_faces('不存在构件') == [])
    check("测试T梁保持原样", get_available_faces('投影测试T梁') == ['bottom', 'web_side', 'flange_bottom'])


def test_pier_faces():
    print("[2] 柱式桥墩面几何（默认参数，base=(0,0,0)）")
    engine = FaceProjectionEngine('柱式桥墩', PIER_PARAMS, (0, 0, 0))

    f = engine.get_face_info('左墩柱正面')
    check("左墩柱正面 center",
          approx(f.center[0], 235) and approx(f.center[1], 5) and approx(f.center[2], -935),
          str(f.center))
    check("左墩柱正面尺寸", approx(f.width, 220) and approx(f.height, 1700), f"{f.width}x{f.height}")
    check("左墩柱正面法向", f.normal == (0, -1, 0) and f.plane == 'xz')

    f = engine.get_face_info('右墩柱正面')
    check("右墩柱正面 center.x", approx(f.center[0], 985), str(f.center))

    f = engine.get_face_info('系梁正面')
    check("系梁正面 center",
          approx(f.center[0], 610) and approx(f.center[1], 35) and approx(f.center[2], -950),
          str(f.center))
    check("系梁正面尺寸", approx(f.width, 640) and approx(f.height, 200), f"{f.width}x{f.height}")

    f = engine.get_face_info('盖梁正面')
    check("盖梁正面 center",
          approx(f.center[0], 610) and approx(f.center[1], 0) and approx(f.center[2], 35),
          str(f.center))
    check("盖梁正面尺寸", approx(f.width, 1220) and approx(f.height, 240), f"{f.width}x{f.height}")

    # 默认面
    check("默认测试面=左墩柱正面", engine.get_face_info().face_name == '左墩柱正面')


def test_pier_faces_with_base():
    print("[3] 带基准位置的面几何")
    engine = FaceProjectionEngine('柱式桥墩', PIER_PARAMS, (1000, 2000, 3000))
    f = engine.get_face_info('左墩柱正面')
    check("base偏移生效",
          approx(f.center[0], 1235) and approx(f.center[1], 2005) and approx(f.center[2], 2065),
          str(f.center))


def test_no_xiliang_when_short():
    print("[4] 墩柱高<=1500 时无系梁")
    params = dict(PIER_PARAMS, 墩柱高=1200)
    engine = FaceProjectionEngine('柱式桥墩', params, (0, 0, 0))
    check("系梁正面返回None", engine.get_face_info('系梁正面') is None)


def test_bbox_mapping():
    print("[5] 照片bbox→面局部坐标（等比铺满）")
    engine = FaceProjectionEngine('柱式桥墩', PIER_PARAMS, (0, 0, 0))
    face = engine.get_face_info('左墩柱正面')  # 220 x 1700

    # 照片 1000x2000，中心 bbox
    s = photo_bbox_to_shadow(face, (400, 900, 600, 1100), 1000, 2000, '裂缝')
    check("中心bbox→面中心", approx(s.local_u, 0) and approx(s.local_v, 0),
          f"u={s.local_u}, v={s.local_v}")
    check("中心bbox尺寸", approx(s.width, 44) and approx(s.height, 170),
          f"{s.width}x{s.height}")
    check("裂缝为红色", s.color_rgb == DISEASE_COLOR_MAP['裂缝'])

    # 左上角 bbox → u 负、v 正
    s = photo_bbox_to_shadow(face, (0, 0, 100, 100), 1000, 2000, '剥落')
    check("左上bbox→左下", approx(s.local_u, -99) and approx(s.local_v, 807.5),
          f"u={s.local_u}, v={s.local_v}")

    # 未知病害类型 → 绿色兜底
    s = photo_bbox_to_shadow(face, (0, 0, 100, 100), 1000, 2000, '已修复')
    check("未知类型绿色兜底", s.color_rgb == (0, 200, 0), str(s.color_rgb))


def test_shadow_to_world():
    print("[6] shadow_to_world 世界坐标换算")
    engine = FaceProjectionEngine('柱式桥墩', PIER_PARAMS, (0, 0, 0))
    face = engine.get_face_info('左墩柱正面')
    s = photo_bbox_to_shadow(face, (400, 900, 600, 1100), 1000, 2000, '裂缝')
    wx, wy, wz, ww, wh, wt, axis = engine.shadow_to_world(face, s, thickness=2.0)
    # 面中心 (235, 5, -935)，法向 (0,-1,0) 偏移 2mm → y=3
    check("世界坐标≈面中心+法向偏移",
          approx(wx, 235) and approx(wy, 3) and approx(wz, -935),
          f"({wx},{wy},{wz})")
    check("axis=xz", axis == 'xz')
    check("世界尺寸", approx(ww, 44) and approx(wh, 170), f"{ww}x{wh}")


# 引桥桥墩默认参数（与 组件测试/引桥桥墩.py 一致）
AP_PIER_PARAMS = {
    '盖梁总长': 1930, '盖梁总高': 300, '盖梁宽': 300,
    '墩柱直径': 250, '墩柱间距': 1140, '墩高': 1200, '系梁根数': 2,
}


def test_ap_pier_type_inference():
    print("[7] 引桥桥墩类型识别（不被误判为异形盖梁）")
    from bimbase_query import infer_bridge_component_type
    params = dict(AP_PIER_PARAMS)
    params['引桥桥墩'] = None  # BIMBase 返回的几何属性键
    t = infer_bridge_component_type(params)
    check("识别为引桥桥墩", t == '引桥桥墩', f"got: {t}")


def test_ap_pier_faces():
    print("[8] 引桥桥墩面几何（默认参数，base=(0,0,0)）")
    faces = get_available_faces('引桥桥墩')
    check("引桥桥墩4个面", faces == ['左墩柱正面', '右墩柱正面', '系梁正面', '盖梁正面'], str(faces))

    engine = FaceProjectionEngine('引桥桥墩', AP_PIER_PARAMS, (0, 0, 0))

    f = engine.get_face_info('左墩柱正面')
    check("左墩柱正面 center",
          approx(f.center[0], -570) and approx(f.center[1], -125) and approx(f.center[2], 600),
          str(f.center))
    check("左墩柱正面尺寸", approx(f.width, 250) and approx(f.height, 1200), f"{f.width}x{f.height}")

    f = engine.get_face_info('右墩柱正面')
    check("右墩柱正面 center.x", approx(f.center[0], 570), str(f.center))

    f = engine.get_face_info('系梁正面')
    check("系梁正面 center",
          approx(f.center[0], 0) and approx(f.center[1], -100) and approx(f.center[2], 900),
          str(f.center))
    check("系梁正面尺寸", approx(f.width, 890) and approx(f.height, 200), f"{f.width}x{f.height}")

    f = engine.get_face_info('盖梁正面')
    check("盖梁正面 center",
          approx(f.center[0], 0) and approx(f.center[1], -150) and approx(f.center[2], 1350),
          str(f.center))
    check("盖梁正面尺寸", approx(f.width, 1930) and approx(f.height, 300), f"{f.width}x{f.height}")

    check("默认测试面=左墩柱正面", engine.get_face_info().face_name == '左墩柱正面')

    # 系梁根数=0 时无系梁
    engine0 = FaceProjectionEngine('引桥桥墩', dict(AP_PIER_PARAMS, 系梁根数=0), (0, 0, 0))
    check("系梁根数0→系梁正面None", engine0.get_face_info('系梁正面') is None)


def main():
    print("=" * 50)
    print("柱式桥墩病害投影映射 — 离线测试")
    print("=" * 50)
    test_available_faces()
    test_pier_faces()
    test_pier_faces_with_base()
    test_no_xiliang_when_short()
    test_bbox_mapping()
    test_shadow_to_world()
    test_ap_pier_type_inference()
    test_ap_pier_faces()
    print("=" * 50)
    print(f"结果: {_passed} 通过, {_failed} 失败")
    print("=" * 50)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
