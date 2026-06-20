# -*- coding: utf-8 -*-
import sys, types

# Stub pyp3d
pyp3d = types.ModuleType('pyp3d')
class _DummyMeta(type):
    def __getitem__(cls, key): return None
    def __setitem__(cls, key, val): pass
class _Vec:
    def __init__(self,*a): pass
class _Comp(metaclass=_DummyMeta):
    def __init__(self): pass
    def __getitem__(self,k): return 0
    def __setitem__(self,k,v): pass
class _Attr:
    def __init__(self,v,**kw): self.value=v
class _Line:
    def __init__(self,a,b): pass
class _Section:
    def __init__(self,*a): pass
class _Sweep:
    def __init__(self,a,b): pass
class _Cube: pass
class _Sphere: pass
class _Cone: pass
class _Arc: pass
def _place(*a): pass
def _place_to(*a): pass
def _scale(*a): return None
def _translate(*a): return None
def _rotation(*a): return None
def _isinside(): pass
def _setglob(): pass
def _export(f): return f

for name, obj in {
    'Component': _Comp, 'Attr': _Attr, 'Line': _Line, 'Section': _Section,
    'Sweep': _Sweep, 'Cube': _Cube, 'Sphere': _Sphere, 'Cone': _Cone, 'Arc': _Arc,
    'Vec2': _Vec, 'Vec3': _Vec, 'Point': _Vec,
    'place': _place, 'place_to': _place_to, 'scale': _scale, 'translate': _translate, 'rotation': _rotation,
    'isinside_global_variable': _isinside, 'set_global_variable': _setglob,
    'export': _export,
    'create_component': lambda x: None,
    'UnifiedFunction': lambda *a: lambda x: None,
    'PARACMPT_PARAMETRIC_COMPONENT': 1,
    'PARACMPT_KEYWORD_TRANSFORMATION': 2,
    'PARACMPT_KEYWORD_DEPENDENT_FILE': 3,
}.items():
    setattr(pyp3d, name, obj)

for name in ['get_element_from_boxselect','entityid_isvaid','get_datakey_from_entity',
             'get_noumKV_from_instancekey','get_noumenon_from_instancekey','get_all_instancekey',
             'get_entity_property','get_entityid_from_boxselection','get_current_entityId']:
    setattr(pyp3d, name, None)

sys.modules['pyp3d'] = pyp3d

# Stub PyQt5
qt = types.ModuleType('PyQt5')
qtcore = types.ModuleType('PyQt5.QtCore')
qtgui = types.ModuleType('PyQt5.QtGui')
qtwidgets = types.ModuleType('PyQt5.QtWidgets')
qtmultimedia = types.ModuleType('PyQt5.QtMultimedia')

def _sig(*a,**k): return None
class _QObj:
    finished = _sig
    error = _sig
    stream_chunk = _sig
    response_ready = _sig

for mod in [qt, qtcore, qtgui, qtwidgets, qtmultimedia]:
    mod.__dict__.setdefault('QObject', _QObj)
    mod.__dict__.setdefault('pyqtSignal', _sig)

qtcore.QBuffer = object
qtcore.QIODevice = object

for name in ['QWidget','QVBoxLayout','QHBoxLayout','QTextEdit','QLineEdit','QPushButton','QLabel',
             'QDialog','QFormLayout','QMessageBox','QSplitter','QListWidget','QListWidgetItem',
             'QSizePolicy','QCheckBox','QComboBox','QGroupBox','QInputDialog','QFileDialog',
             'QStatusBar','QToolBar','QMainWindow','QAction','QFrame','QApplication','QProgressBar',
             'QDialogButtonBox','QMenu','QColorDialog','QDoubleSpinBox','QSpinBox']:
    setattr(qtwidgets, name, object)

qtcore.Qt = types.SimpleNamespace(
    StrongFocus=0, NoBrush=0, Antialiasing=0, DashLine=0, DotLine=0, SolidLine=0,
    Horizontal=0, Vertical=0,
)
qtcore.QThread = _QObj
qtcore.QTimer = object
qtcore.QPoint = object
qtcore.QSize = object
qtcore.QRect = object
qtgui.QColor = object
qtgui.QFont = object
qtgui.QIcon = object
qtgui.QCursor = object
qtgui.QKeyEvent = object
qtgui.QMouseEvent = object
qtgui.QWheelEvent = object
qtgui.QPaintEvent = object
qtgui.QResizeEvent = object
qtgui.QPainter = object
qtgui.QPen = object
qtgui.QBrush = object

qtmultimedia.QAudioInput = object
qtmultimedia.QAudioFormat = object
qtmultimedia.QAudioDeviceInfo = object
qtmultimedia.QAudio = object
qtmultimedia.QBuffer = object
qtmultimedia.QIODevice = object

sys.modules['PyQt5'] = qt
sys.modules['PyQt5.QtCore'] = qtcore
sys.modules['PyQt5.QtGui'] = qtgui
sys.modules['PyQt5.QtWidgets'] = qtwidgets
sys.modules['PyQt5.QtMultimedia'] = qtmultimedia

sys.path.insert(0, r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\CADBoard')

from utils.ai_panel import LocalCommandParser

tests = [
    '沿X轴长度100间距20生成圆柱',
    '沿Y轴布置5个正方体',
    '沿Z轴从(10,20,30)间距30生成3个球体',
    '在(100,200,300)画一个边长80的正方体',
    '画一个半径50的球体',
]
for t in tests:
    r = LocalCommandParser.parse(t)
    print(repr(t))
    print(r)
    print()
