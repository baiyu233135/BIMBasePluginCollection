# -*- coding: utf-8 -*-
"""测试问题1修复: _on_cmd_return 命令名/快捷键激活"""
import sys, os, types

PLUGIN = r"c:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\速构智维"
sys.path.insert(0, PLUGIN)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 打桩掉依赖 pyp3d / 网络的模块
for name in ["bimbase_sync"]:
    m = types.ModuleType(name)
    m.__dict__["__all__"] = []
    sys.modules[name] = m

from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

try:
    import board
except Exception as e:
    import traceback; traceback.print_exc()
    print("BOARD IMPORT FAILED:", e)
    sys.exit(2)

win = board.CADBoardWindow()
print("window created OK, registered commands:", len(win._command_registry))

results = []
def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (" | " + detail if detail else ""))

# 1. 快捷键激活: TR -> 修剪
win.cmd_input.setText("TR")
win._on_cmd_return()
check("输入TR激活修剪", win.current_command is not None and win.current_command.name == "修剪",
      f"current={win.current_command and win.current_command.name}, input='{win.cmd_input.text()}'")

# 2. 中文名激活: 延伸
win.set_default_command()
win.cmd_input.setText("延伸")
win._on_cmd_return()
check("输入'延伸'激活延伸", win.current_command is not None and win.current_command.name == "延伸",
      f"current={win.current_command and win.current_command.name}")

# 3. 快捷键 DIV -> 定数等分
win.set_default_command()
win.cmd_input.setText("div")   # 小写也应匹配
win._on_cmd_return()
check("输入div(小写)激活定数等分", win.current_command is not None and win.current_command.name == "定数等分",
      f"current={win.current_command and win.current_command.name}")

# 4. 非命令文本仍走原逻辑: 定数等分激活时输入 4 -> 段数设为4(不被命令名抢占)
win.cmd_input.setText("4")
win._on_cmd_return()
cmd = win.current_command
check("命令参数仍可确认(段数=4)", cmd is not None and cmd.name == "定数等分" and cmd._num_segments == 4,
      f"num={getattr(cmd, '_num_segments', None)}")

# 5. 无命令时输入坐标 -> 不崩溃、不激活命令
win.set_default_command()
before = win.current_command
win.cmd_input.setText("100,200")
win._on_cmd_return()
check("坐标输入不误触发命令", win.current_command is before.__class__ or win.current_command.name == "选择",
      f"current={win.current_command and win.current_command.name}")

# 6. 未知文本不崩溃
win.cmd_input.setText("不存在的命令xyz")
win._on_cmd_return()
check("未知命令名安全忽略", True)

print("\n===== SUMMARY =====")
for name, ok in results:
    print(("PASS " if ok else "FAIL ") + name)
print(f"{sum(1 for _,ok in results if ok)}/{len(results)} passed")
win.close()
