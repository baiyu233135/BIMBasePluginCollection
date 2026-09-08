# -*- coding: utf-8 -*-
"""
BIMBase构件扫描调试脚本

直接打印所有实例的key和参数，帮助排查为什么识别不到构件。
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
            f.write(f"[{ts}] [SCAN_DBG] {msg}\n")
    except Exception:
        pass

_log("=" * 60)
_log("scan_debug.py STARTED")

# 尝试导入API
try:
    from bimbase_sync import get_all_instancekey, get_noumKV_from_instancekey
    _log("bimbase_sync imported OK")
except Exception as e:
    _log(f"bimbase_sync import FAILED: {e}")
    try:
        from pyp3d import get_all_instancekey, get_noumKV_from_instancekey
        _log("pyp3d imported OK")
    except Exception as e2:
        _log(f"pyp3d import FAILED: {e2}")
        _log("ABORT: no API available")
        raise SystemExit(1)

# 获取所有实例key
_log("calling get_all_instancekey()...")
try:
    keys = get_all_instancekey()
    _log(f"get_all_instancekey() returned {len(keys) if keys else 0} keys")
    if not keys:
        _log("WARNING: keys is empty or None")
except Exception as e:
    _log(f"get_all_instancekey() FAILED: {e}\n{traceback.format_exc()}")
    raise SystemExit(1)

if not keys:
    _log("No instances found in BIMBase")
    _log("COMPLETED")
    raise SystemExit(0)

# 打印每个实例的参数（前20个）
_log(f"Scanning first 20 instances...")
for i, k in enumerate(keys[:20]):
    try:
        params = get_noumKV_from_instancekey(k)
        param_keys = list(params.keys()) if params else []
        _log(f"Instance {i}: key={k}, param_keys={param_keys}")
    except Exception as e:
        _log(f"Instance {i}: key={k}, FAILED to get params: {e}")

# 统计所有参数键名
all_keys = set()
for k in keys[:50]:
    try:
        params = get_noumKV_from_instancekey(k)
        if params:
            all_keys.update(str(kk) for kk in params.keys() if isinstance(kk, str))
    except Exception:
        pass

_log(f"All unique param keys found: {sorted(all_keys)}")
_log("COMPLETED")

# 弹窗提示结果
try:
    from PyQt5.QtWidgets import QMessageBox, QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    msg = QMessageBox()
    msg.setWindowTitle("扫描调试")
    msg.setText(f"扫描完成！\n\n共找到 {len(keys)} 个实例\n已记录到 bridge_disease_debug.log\n\n请把日志最后50行发给开发者。")
    msg.exec_()
except Exception:
    pass
