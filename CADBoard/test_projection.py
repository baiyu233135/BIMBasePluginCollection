# -*- coding: utf-8 -*-
"""
BIMBase投影功能独立测试脚本

不依赖GUI，直接测试：
1. pyp3d是否可用
2. 能否创建红色标记组件
3. 能否放置到BIMBase中

用法：在BIMBase中通过按钮执行此脚本，或命令行测试
"""

import sys
import os
import traceback

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

_log_file = os.path.join(_current_dir, "bridge_disease_debug.log")

def _log(msg):
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    try:
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [TEST] {msg}\n")
    except Exception:
        pass

_log("=" * 60)
_log("test_projection.py STARTED")

# 测试1: pyp3d导入
_log("--- Test 1: import pyp3d ---")
try:
    from pyp3d import Component, Attr, Cube, translate, scale, place
    _log("pyp3d imported OK")
    _pyp3d_ok = True
except Exception as e:
    _log(f"pyp3d import FAILED: {e}")
    _pyp3d_ok = False

if not _pyp3d_ok:
    _log("ABORT: pyp3d not available")
    _log("COMPLETED")
    raise SystemExit(1)

# 测试2: 创建红色标记组件
_log("--- Test 2: create red marker component ---")
try:
    class _TestMarker(Component):
        def __init__(self, x=0, y=0, z=0, size=50):
            super().__init__()
            self['x'] = Attr(float(x), show=True, obvious=True)
            self['y'] = Attr(float(y), show=True, obvious=True)
            self['z'] = Attr(float(z), show=True, obvious=True)
            self['size'] = Attr(float(size), show=True, obvious=True)
            self['标记'] = Attr(None, show=True, obvious=True)
            self.replace()
        
        def replace(self):
            s = self['size']
            self['标记'] = translate(self['x'], self['y'], self['z']) * scale(s, s, s) * Cube()
    
    comp = _TestMarker(100, 200, 300, 50)
    _log(f"Component created OK: {type(comp)}")
except Exception as e:
    _log(f"Component creation FAILED: {e}\n{traceback.format_exc()}")
    _log("COMPLETED")
    raise SystemExit(1)

# 测试3: 放置到BIMBase
_log("--- Test 3: place component into BIMBase ---")
try:
    # 模拟bimbase_sync的sys.argv处理
    original_argv0 = sys.argv[0]
    sys.argv[0] = os.path.join(_current_dir, 'bimbase_sync.py')
    try:
        place(comp)
        _log("place() called OK")
    finally:
        sys.argv[0] = original_argv0
except Exception as e:
    _log(f"place() FAILED: {e}\n{traceback.format_exc()}")
    _log("COMPLETED")
    raise SystemExit(1)

_log("ALL TESTS PASSED")
_log("COMPLETED")

# 弹窗提示
try:
    from PyQt5.QtWidgets import QMessageBox, QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    msg = QMessageBox()
    msg.setWindowTitle("投影测试")
    msg.setText("✅ 投影测试全部通过！\n\n红色标记已放置到BIMBase。\n请查看BIMBase视图确认。")
    msg.exec_()
except Exception:
    pass
