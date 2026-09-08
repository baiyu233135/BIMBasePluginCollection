# -*- coding: utf-8 -*-
"""
T 梁病害识别全流程验证脚本

在不依赖 BIMBase 的情况下，验证以下流程是否可跑通：
1. 读取 T 梁病害照片
2. 使用 cv_anomaly_detector 检测异常区域
3. 使用 FaceProjectionEngine 计算 T 梁投影面
4. 生成模拟病害阴影并转换为世界坐标

运行方式（在普通 Python 环境下即可）：
    python 桥梁病害识别/test_t_beam_workflow.py
"""

import os
import sys
from pathlib import Path

# 添加桥梁病害识别根目录到路径
_module_dir = Path(__file__).resolve().parent
if str(_module_dir) not in sys.path:
    sys.path.insert(0, str(_module_dir))


def test_photo_detection():
    """测试 1：用 CV 检测 T 梁照片中的异常区域"""
    print("\n" + "=" * 60)
    print("测试 1: T 梁照片异常区域检测")
    print("=" * 60)

    from cv_anomaly_detector import detect_anomalies_cv

    photo_path = _module_dir.parent / "数据参考源" / "桥隧数据源" / "T梁照片" / "00.png"
    if not photo_path.exists():
        print(f"[失败] 测试照片不存在: {photo_path}")
        return None

    print(f"[输入] {photo_path}")
    results = detect_anomalies_cv(str(photo_path))

    if not results:
        print("[警告] 未检测到异常区域")
        return []

    print(f"[成功] 检测到 {len(results)} 个异常区域:")
    for i, r in enumerate(results[:5], 1):
        x1, y1, x2, y2 = r.bbox
        print(f"  {i}. 位置=({x1}, {y1}) -> ({x2}, {y2}), 尺寸=({x2-x1}x{y2-y1})")

    return results


def test_face_projection():
    """测试 2：T 梁投影面计算"""
    print("\n" + "=" * 60)
    print("测试 2: T 梁投影面计算")
    print("=" * 60)

    from face_projection import FaceProjectionEngine

    params = {
        '梁长': 3000,
        '底板宽': 80,
        '底板高': 25,
        '腹板宽': 20,
        '翼缘宽': 200,
        '翼缘高': 20,
        '总高': 160,
    }
    base_pos = (0, 0, 0)

    engine = FaceProjectionEngine("投影测试T梁", params, base_pos)

    faces = ["bottom", "web_side", "flange_bottom"]
    for face_name in faces:
        face = engine.get_face_info(face_name)
        if face is None:
            print(f"[失败] 无法获取 {face_name} 面信息")
            continue

        print(f"[成功] {face_name}:")
        print(f"  中心 = ({face.center[0]:.1f}, {face.center[1]:.1f}, {face.center[2]:.1f})")
        print(f"  法向 = ({face.normal[0]:.1f}, {face.normal[1]:.1f}, {face.normal[2]:.1f})")
        print(f"  尺寸 = {face.width:.1f} x {face.height:.1f}")

    return engine


def test_simulated_projection(engine):
    """测试 3：在 T 梁底面生成模拟病害阴影"""
    print("\n" + "=" * 60)
    print("测试 3: 模拟病害投影到梁底面")
    print("=" * 60)

    shadows = engine.generate_simulated_shadows("bottom", count=3, seed=42)
    if not shadows:
        print("[失败] 未生成模拟阴影")
        return

    face = engine.get_face_info("bottom")
    print(f"[成功] 生成 {len(shadows)} 个模拟病害区域:")
    for i, s in enumerate(shadows, 1):
        wx, wy, wz, ww, wh, wt, axis = engine.shadow_to_world(face, s)
        print(f"  {i}. 病害={s.disease_type}, 世界坐标=({wx:.1f}, {wy:.1f}, {wz:.1f}), 尺寸={ww:.1f}x{wh:.1f}")


def test_report_structure():
    """测试 4：报告生成器基本功能"""
    print("\n" + "=" * 60)
    print("测试 4: 报告生成器基本功能")
    print("=" * 60)

    from report_generator import ReportGenerator
    from disease_marker import MarkerRecord

    gen = ReportGenerator()
    sample_records = [
        MarkerRecord(
            record_id='test001',
            photo_path='',
            component_type='投影测试T梁',
            component_key='',
            disease_class='剥落',
            confidence=0.55,
            bbox=(0, 0, 100, 50),
            marked_image_path='',
            ai_diagnosis='',
            ai_diagnosed=False,
            severity='中等',
        )
    ]

    output_path = _module_dir / "test_report_output.docx"
    try:
        ok = gen.generate(sample_records, str(output_path))
        if ok and output_path.exists():
            print(f"[成功] 报告已生成: {output_path}")
            output_path.unlink()  # 清理测试文件
            return True
        else:
            print("[失败] 报告文件未生成")
            return False
    except Exception as e:
        print(f"[失败] 报告生成异常: {e}")
        return False


def main():
    print("=" * 60)
    print("T 梁病害识别全流程验证")
    print("=" * 60)

    results = test_photo_detection()
    engine = test_face_projection()

    if engine:
        test_simulated_projection(engine)

    report_ok = test_report_structure()

    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)
    print(f"照片异常检测: {'通过' if results is not None else '未通过'}")
    print(f"投影面计算: {'通过' if engine else '未通过'}")
    print(f"报告生成: {'通过' if report_ok else '未通过'}")
    print("\n[提示] 以上测试在普通 Python 环境下完成。BIMBase 中的实际投影需通过")
    print("       速构智维 面板 → 桥梁病害识别 → 导入照片 → 识别 → 投影到BIMBase 验证。")


if __name__ == "__main__":
    main()
