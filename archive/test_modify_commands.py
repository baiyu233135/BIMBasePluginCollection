# -*- coding: utf-8 -*-
"""FakeBoard 离线测试 - 验证8个修改命令的实际行为"""
import sys, os, math

PLUGIN = r"c:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\速构智维"
sys.path.insert(0, PLUGIN)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from geometry.elements import (LineElement, ArcElement, PolylineElement,
                               RectangleElement, CircleElement, PointElement)


class FakeStatusBar:
    def __init__(self): self.messages = []
    def showMessage(self, msg, *a):
        self.messages.append(str(msg))
        print("  [status]", msg)

class FakeViewport:
    def update(self): pass

class FakeLayerManager:
    def is_visible(self, name): return True
    def apply_layer_style(self, elem): pass

class FakeCoordSystem:
    def get_scale(self): return 1.0
    def world_to_screen(self, x, y): return (x, -y)

class FakeBoard:
    def __init__(self):
        self.elements = []
        self.status_bar = FakeStatusBar()
        self.viewport = FakeViewport()
        self.layer_manager = FakeLayerManager()
        self.coord_system = FakeCoordSystem()
        self._face_edit_mode = False
        self._face_component_id = None
        self._face_filter = 'all'
        self.current_command = None
        self._undo_stack = []
    def set_default_command(self):
        self.current_command = None
    def _save_undo_state(self):
        self._undo_stack.append(list(self.elements))
    def add_element(self, elem):
        self.elements.append(elem)
    def apply_current_layer_style(self, elem): pass

def press(cmd, x, y, button=1, mod=0):
    return cmd.on_mouse_press(x, y, button, mod)

def release(cmd, x, y, button=1, mod=0):
    return cmd.on_mouse_release(x, y, button, mod)

results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (" | " + detail if detail else ""))

# ============ 1. 延伸 Extend (新单步流程) ============
print("\n=== ExtendCommand ===")
from commands.modify_edit import ExtendCommand
b = FakeBoard()
boundary = LineElement(100, -50, 100, 50)   # 垂直边界线 x=100
target = LineElement(0, 0, 60, 0)           # 水平线，右端点(60,0)应延伸到(100,0)
b.elements = [boundary, target]
cmd = ExtendCommand(b); cmd.activate()
press(cmd, 55, 0)           # 直接点击要延伸的线(靠近右端)
ok = abs(target.x2 - 100) < 1e-6 and abs(target.y2) < 1e-6
check("Extend", ok, f"target end=({target.x2},{target.y2}) expect (100,0)")
# 再延伸左端: 加一条左边界 x=-30, 点击靠近左端
b2 = FakeBoard()
bl = LineElement(-30, -50, -30, 50)
t2 = LineElement(0, 0, 60, 0)
b2.elements = [bl, t2, boundary]
cmd2 = ExtendCommand(b2); cmd2.activate()
press(cmd2, 5, 0)
ok2 = abs(t2.x1 - (-30)) < 1e-6
check("Extend(左端)", ok2, f"t2 start=({t2.x1},{t2.y1}) expect (-30,0)")

# ============ 2. 拉伸 Stretch ============
print("\n=== StretchCommand ===")
from commands.modify_advanced import StretchCommand
b = FakeBoard()
line = LineElement(0, 0, 100, 0)
b.elements = [line]
cmd = StretchCommand(b); cmd.activate()
# 交叉框选（从右向左）包含右端点(100,0)
press(cmd, 120, 20); release(cmd, 80, -20)
sel = [e for e in b.elements if e.selected]
print("  selected after crossing box:", len(sel))
press(cmd, 100, 0)   # 基点
press(cmd, 150, 0)   # 目标点
ok = abs(line.x2 - 150) < 1e-6 and abs(line.x1) < 1e-6
check("Stretch", ok, f"line=({line.x1},{line.y1})-({line.x2},{line.y2}) expect x2=150")

# ============ 3. 偏移 Offset ============
print("\n=== OffsetCommand ===")
from commands.modify_advanced import OffsetCommand
b = FakeBoard()
line = LineElement(0, 0, 100, 0)
b.elements = [line]
cmd = OffsetCommand(b); cmd.activate()
cmd.on_cmd_confirm("10")     # 命令行设距离
press(cmd, 50, 0)            # 选线
press(cmd, 50, 30)           # 点上方 -> 往上方偏
news = [e for e in b.elements if e is not line]
ok = len(news) == 1 and abs(news[0].y1 - 10) < 1e-6 and abs(news[0].y2 - 10) < 1e-6
check("Offset", ok, f"new={[(e.y1,e.y2) for e in news] if news and hasattr(news[0],'y1') else news}")

# ============ 4. 合并 Join ============
print("\n=== JoinCommand ===")
from commands.modify_edit import JoinCommand
b = FakeBoard()
l1 = LineElement(0, 0, 50, 0)
l2 = LineElement(50, 0, 50, 50)
b.elements = [l1, l2]
cmd = JoinCommand(b); cmd.activate()
press(cmd, -10, -10); release(cmd, 100, 100)   # 框选
polys = [e for e in b.elements if e.element_type.value == '多段线']
ok = len(polys) == 1 and l1 not in b.elements and l2 not in b.elements and len(polys[0].points) == 3
check("Join", ok, f"polys={len(polys)} pts={len(polys[0].points) if polys else 0} remaining={len(b.elements)}")

# ============ 5. 倒斜角 Chamfer (新流程: 点选两线) ============
print("\n=== ChamferCommand ===")
from commands.modify_edit import ChamferCommand
b = FakeBoard()
l1 = LineElement(0, 0, 100, 0)    # 水平
l2 = LineElement(100, 0, 100, 100)  # 垂直, 交于(100,0)
b.elements = [l1, l2]
cmd = ChamferCommand(b); cmd.activate()
cmd.on_cmd_confirm("10")   # 命令行设距离
press(cmd, 50, 0)          # 点第1条线
press(cmd, 100, 50)        # 点第2条线 -> 立即执行
chamfers = [e for e in b.elements if e not in (l1, l2)]
ok = (len(chamfers) == 1 and
      abs(l1.x2 - 90) < 1e-6 and       # l1 修剪到距交点10mm
      abs(l2.y1 - 10) < 1e-6 and       # l2 修剪到距交点10mm
      abs(chamfers[0].x1 - 90) < 1e-6 and abs(chamfers[0].y2 - 10) < 1e-6)
check("Chamfer", ok, f"l1.x2={l1.x2} l2.y1={l2.y1} chamfer={chamfers and (chamfers[0].x1,chamfers[0].y1,chamfers[0].x2,chamfers[0].y2)}")

# ============ 6. 圆角 Fillet (新流程: 点选两线) ============
print("\n=== FilletCommand ===")
from commands.modify_edit import FilletCommand
b = FakeBoard()
l1 = LineElement(0, 0, 100, 0)
l2 = LineElement(100, 0, 100, 100)
b.elements = [l1, l2]
cmd = FilletCommand(b); cmd.activate()
cmd.on_cmd_confirm("10")
press(cmd, 50, 0)
press(cmd, 100, 50)
arcs = [e for e in b.elements if e.element_type.value == '圆弧']
ok = (len(arcs) == 1 and
      abs(l1.x2 - 90) < 1e-6 and abs(l1.x1) < 1e-6 and   # l1 保留远端(0,0), 近端裁到(90,0)
      abs(l2.y1 - 10) < 1e-6 and abs(l2.y2 - 100) < 1e-6 and
      abs(arcs[0].radius - 10) < 1e-6)
# 校验圆弧连接性: 弧端点应等于两线切点
if arcs:
    a = arcs[0]
    pts = a.sample_points(36)
    p_start, p_end = pts[0], pts[-1]
    conn = (min(math.hypot(p_start[0]-90, p_start[1]-0), math.hypot(p_end[0]-90, p_end[1]-0)) < 1e-6 and
            min(math.hypot(p_start[0]-100, p_start[1]-10), math.hypot(p_end[0]-100, p_end[1]-10)) < 1e-6)
else:
    conn = False
check("Fillet", ok and conn, f"l1=({l1.x1},{l1.y1})-({l1.x2},{l1.y2}) l2.y1={l2.y1} arc_r={arcs and arcs[0].radius} conn={conn}")

# ============ 7. 分解 Explode ============
print("\n=== ExplodeCommand ===")
from commands.modify_edit import ExplodeCommand
b = FakeBoard()
rect = RectangleElement(0, 0, 100, 50)
b.elements = [rect]
cmd = ExplodeCommand(b); cmd.activate()
press(cmd, 50, 0)   # 点击矩形底边
lines = [e for e in b.elements if e.element_type.value == '直线']
ok = rect not in b.elements and len(lines) == 4
check("Explode", ok, f"lines={len(lines)} rect_gone={rect not in b.elements}")

# ============ 8a. 定数等分 Divide ============
print("\n=== DivideCommand ===")
from commands.divide_command import DivideCommand, MeasureCommand
b = FakeBoard()
line = LineElement(0, 0, 100, 0)
b.elements = [line]
cmd = DivideCommand(b); cmd.activate()
cmd.on_cmd_confirm("4")
press(cmd, 50, 0)
pts = [e for e in b.elements if e.element_type.value == '点']
ok = len(pts) == 3 and abs(pts[0].x - 25) < 1e-6
check("Divide", ok, f"points={[(round(p.x,1),round(p.y,1)) for p in pts]}")

# ============ 8b. 定距等分 Measure ============
print("\n=== MeasureCommand ===")
b = FakeBoard()
line = LineElement(0, 0, 100, 0)
b.elements = [line]
cmd = MeasureCommand(b); cmd.activate()
cmd.on_cmd_confirm("30")
press(cmd, 50, 0)
pts = [e for e in b.elements if e.element_type.value == '点']
ok = len(pts) == 3 and abs(pts[0].x - 30) < 1e-6
check("Measure", ok, f"points={[(round(p.x,1),round(p.y,1)) for p in pts]}")

# ============ 补充: 圆角-交叉线(X形, 点击右上象限) ============
print("\n=== FilletCommand 交叉线 ===")
b = FakeBoard()
l1 = LineElement(0, 0, 100, 0)     # 水平线穿过交点(50,0)... 改用真正X交叉
l2 = LineElement(50, -50, 50, 50)  # 垂直线, 与l1交于(50,0)
b.elements = [l1, l2]
cmd = FilletCommand(b); cmd.activate()
cmd.on_cmd_confirm("5")
press(cmd, 80, 0)    # l1 右侧
press(cmd, 50, 30)   # l2 上侧
arcs = [e for e in b.elements if e.element_type.value == '圆弧']
ok = (len(arcs) == 1 and
      abs(l1.x1 - 55) < 1e-6 and abs(l1.x2 - 100) < 1e-6 and  # l1 保留点击的右侧 (55,0)-(100,0)
      abs(l2.y1 - 5) < 1e-6 and abs(l2.y2 - 50) < 1e-6)       # l2 保留点击的上侧
check("Fillet(交叉)", ok, f"l1=({l1.x1},{l1.y1})-({l1.x2},{l1.y2}) l2=({l2.x1},{l2.y1})-({l2.x2},{l2.y2})")

# ============ 补充: 拉伸-点选模式(回归 _sel_box=None 修复) ============
print("\n=== StretchCommand 点选 ===")
b = FakeBoard()
line = LineElement(0, 0, 100, 0)
b.elements = [line]
cmd = StretchCommand(b); cmd.activate()
press(cmd, 50, 0); release(cmd, 50, 0)   # 点选直线
press(cmd, 0, 0)        # 基点
press(cmd, 10, 20)      # 目标点
ok = abs(line.x1 - 10) < 1e-6 and abs(line.y1 - 20) < 1e-6 and abs(line.x2 - 110) < 1e-6
check("Stretch(点选整体移动)", ok, f"line=({line.x1},{line.y1})-({line.x2},{line.y2})")

print("\n===== SUMMARY =====")
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name)
print(f"{sum(1 for _,ok,_ in results if ok)}/{len(results)} passed")
