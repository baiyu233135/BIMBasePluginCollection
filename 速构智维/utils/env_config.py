# -*- coding: utf-8 -*-
"""
环境配置模块 - 一键配置VSCode开发环境 + ODA File Converter

功能:
1. 自动检测BIMBase安装路径
2. 配置VSCode settings.json (Python解释器 + pyp3d补全路径)
3. 安装项目所需依赖包 (PyQt5, ezdxf)
4. 自动安装 ODA File Converter（实现一键导出DWG）
5. 所有步骤一键完成，带详细日志输出

参考: 自动配置环境.py 的BIMBase路径扫描逻辑
"""

import os
import sys
import json
import subprocess
import shutil
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Tuple


# ============================================================
# 依赖包清单 - 安装这个项目所需要的全部依赖
# ============================================================
REQUIRED_PACKAGES = [
    "PyQt5",           # 画板GUI必需
    "ezdxf",           # 导出DXF/DWG测试模式
    "PyMuPDF",         # PDF矢量导入
    "python-docx",     # Word报告生成
    # 注意: torch/torchvision/ultralytics 需要特殊安装指令，详见桥梁病害识别使用说明
]


# ============================================================
# BIMBase 路径检测
# ============================================================

def find_bimbase_installations() -> List[str]:
    r"""
    扫描系统查找BIMBase安装目录

    扫描位置:
    - C:\ProgramData\BIMBase (BIMBase建模软件)
    - C:\ProgramData\PKPM\BIMBase (PKPM版BIMBase)

    Returns:
        找到的BIMBase安装目录名称列表
    """
    search_paths = [
        r"C:\ProgramData\BIMBase",
        r"C:\ProgramData\PKPM\BIMBase",
    ]

    matching_folders = []

    for base_path in search_paths:
        if not os.path.exists(base_path):
            continue

        for folder in os.listdir(base_path):
            folder_path = os.path.join(base_path, folder)
            if not os.path.isdir(folder_path):
                continue

            # 匹配BIMBase相关文件夹
            if any(keyword in folder for keyword in
                   ["BIMBase建模软件", "BIMBase KIT", "BIMBase"]):
                matching_folders.append({
                    'name': folder,
                    'base_path': base_path,
                    'full_path': folder_path
                })

    return matching_folders


def get_latest_bimbase(installations: List[Dict]) -> Optional[Dict]:
    """
    从多个BIMBase安装中选择最新版本

    通过文件夹名称末尾的版本号比较，如 BIMBase建模软件2025V1.6.2.0
    """
    if not installations:
        return None

    # 优先选择版本号最大的
    latest = installations[0]
    for inst in installations[1:]:
        # 简单字符串比较，通常版本号格式一致
        if inst['name'] > latest['name']:
            latest = inst

    return latest


def read_instdir_xml(bimbase_info: Dict) -> Optional[str]:
    """
    读取BIMBase的InstDir.xml获取真实安装路径

    Args:
        bimbase_info: BIMBase安装信息字典

    Returns:
        BIMBase真实安装目录路径，或None
    """
    instdir_xml = os.path.join(bimbase_info['full_path'], 'InstDir.xml')

    if not os.path.exists(instdir_xml):
        # 有些版本可能没有InstDir.xml，直接用full_path
        return bimbase_info['full_path']

    try:
        tree = ET.parse(instdir_xml)
        root = tree.getroot()
        install_dir = root.text.strip() if root.text else None
        if install_dir and os.path.exists(install_dir):
            return install_dir
    except Exception:
        pass

    # 回退到扫描到的路径
    return bimbase_info['full_path']


# ============================================================
# Python 解释器与 pyp3d 路径检测
# ============================================================

def find_bimbase_python(bimbase_dir: str) -> Optional[str]:
    """
    查找BIMBase自带的Python解释器

    BIMBase通常自带Python，位于安装目录下的Python子目录

    Args:
        bimbase_dir: BIMBase安装目录

    Returns:
        python.exe 的完整路径，或None
    """
    # 可能的Python路径（按常见位置排序）
    possible_paths = [
        # BIMBase 2025 新版路径
        os.path.join(bimbase_dir, r"PythonScript\python-3.7.9-embed-amd64\python.exe"),
        os.path.join(bimbase_dir, r"PythonScript\python-3.9-embed-amd64\python.exe"),
        os.path.join(bimbase_dir, r"PythonScript\python-3.10-embed-amd64\python.exe"),
        os.path.join(bimbase_dir, r"PythonScript\python-3.11-embed-amd64\python.exe"),
        os.path.join(bimbase_dir, r"PythonScript\python.exe"),
        # 传统路径
        os.path.join(bimbase_dir, r"Python\python.exe"),
        os.path.join(bimbase_dir, r"python\python.exe"),
        os.path.join(bimbase_dir, r"bin\python.exe"),
        os.path.join(bimbase_dir, r"Python37\python.exe"),
        os.path.join(bimbase_dir, r"Python38\python.exe"),
        os.path.join(bimbase_dir, r"Python39\python.exe"),
        os.path.join(bimbase_dir, r"Python310\python.exe"),
        os.path.join(bimbase_dir, r"Python311\python.exe"),
    ]

    # 先检查精确路径
    for path in possible_paths:
        if os.path.exists(path):
            return path

    # 再通配搜索 PythonScript 子目录
    script_dir = os.path.join(bimbase_dir, "PythonScript")
    if os.path.exists(script_dir):
        for folder in os.listdir(script_dir):
            py_exe = os.path.join(script_dir, folder, "python.exe")
            if os.path.exists(py_exe):
                return py_exe

    return None


def find_pyp3d_path(bimbase_dir: str) -> Optional[str]:
    """
    查找 pyp3d 模块所在路径

    pyp3d 是BIMBase Python SDK的核心模块，需要添加到VSCode的补全路径中

    Args:
        bimbase_dir: BIMBase安装目录

    Returns:
        包含pyp3d模块的目录路径，或None
    """
    # 可能的pyp3d路径
    possible_paths = [
        os.path.join(bimbase_dir, r"Python\Lib\site-packages"),
        os.path.join(bimbase_dir, r"python\Lib\site-packages"),
        os.path.join(bimbase_dir, r"bin"),
        os.path.join(bimbase_dir, r"Python\Lib"),
        os.path.join(bimbase_dir, r"SDK"),
        os.path.join(bimbase_dir, r"SDK\python"),
        os.path.join(bimbase_dir, r"plugins\python"),
    ]

    for path in possible_paths:
        if not os.path.exists(path):
            continue
        if os.path.exists(os.path.join(path, "pyp3d.py")) or \
           os.path.exists(os.path.join(path, "pyp3d", "__init__.py")) or \
           any(f.startswith("pyp3d") for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))):
            return path

    # 递归搜索
    for root, dirs, files in os.walk(bimbase_dir):
        if "pyp3d.py" in files or "pyp3d" in dirs:
            return root
        # 限制搜索深度，避免太慢
        depth = root[len(bimbase_dir):].count(os.sep)
        if depth > 4:
            del dirs[:]

    return None


# ============================================================
# VSCode 配置
# ============================================================

def find_vscode_settings_dir() -> Optional[str]:
    """
    查找VSCode的settings.json所在目录

    优先查找工作区设置(.vscode目录)，其次是用户设置
    """
    # 1. 查找当前工作区的 .vscode 目录
    current_dir = os.getcwd()
    vscode_dir = os.path.join(current_dir, '.vscode')
    if os.path.exists(vscode_dir):
        return vscode_dir

    # 2. 向上查找包含 .vscode 的父目录（多层级工作区）
    parent = current_dir
    for _ in range(5):  # 最多向上5层
        parent = os.path.dirname(parent)
        if not parent or parent == current_dir:
            break
        vscode_dir = os.path.join(parent, '.vscode')
        if os.path.exists(vscode_dir):
            return vscode_dir

    # 3. 使用VSCode用户全局设置
    user_settings = os.path.expandvars(
        r"%APPDATA%\Code\User"
    )
    if os.path.exists(user_settings):
        return user_settings

    return None


def configure_vscode_settings(
    python_path: Optional[str],
    pyp3d_path: Optional[str],
    log_callback=None
) -> bool:
    """
    配置VSCode的settings.json

    配置项:
    - python.defaultInterpreterPath: Python解释器路径
    - python.analysis.extraPaths: pyp3d模块路径（用于智能提示）
    - python.autoComplete.extraPaths: pyp3d模块路径（用于自动补全）

    Args:
        python_path: Python解释器路径
        pyp3d_path: pyp3d模块所在目录
        log_callback: 日志回调函数

    Returns:
        是否成功
    """
    settings_dir = find_vscode_settings_dir()

    if not settings_dir:
        _log(log_callback, "⚠️ 未找到VSCode设置目录，跳过VSCode配置")
        return False

    settings_file = os.path.join(settings_dir, 'settings.json')

    # 读取现有配置
    settings = {}
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            _log(log_callback, f"📂 已加载现有settings.json")
        except Exception as e:
            _log(log_callback, f"⚠️ 读取settings.json失败: {e}")
            settings = {}

    # 需要添加/更新的配置项
    updates = {}

    if python_path and os.path.exists(python_path):
        key = "python.defaultInterpreterPath"
        old = settings.get(key)
        if old != python_path:
            updates[key] = python_path
            settings[key] = python_path

    if pyp3d_path and os.path.exists(pyp3d_path):
        # python.analysis.extraPaths
        extra_paths = settings.get("python.analysis.extraPaths", [])
        if not isinstance(extra_paths, list):
            extra_paths = [extra_paths]
        if pyp3d_path not in extra_paths:
            extra_paths.append(pyp3d_path)
            settings["python.analysis.extraPaths"] = extra_paths
            updates["python.analysis.extraPaths"] = extra_paths

        # python.autoComplete.extraPaths
        auto_paths = settings.get("python.autoComplete.extraPaths", [])
        if not isinstance(auto_paths, list):
            auto_paths = [auto_paths]
        if pyp3d_path not in auto_paths:
            auto_paths.append(pyp3d_path)
            settings["python.autoComplete.extraPaths"] = auto_paths
            updates["python.autoComplete.extraPaths"] = auto_paths

    if not updates:
        _log(log_callback, "✅ VSCode配置已是最新，无需修改")
        return True

    # 写入配置
    try:
        os.makedirs(settings_dir, exist_ok=True)
        with open(settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)

        _log(log_callback, f"✅ 已更新VSCode settings.json:")
        for key, val in updates.items():
            _log(log_callback, f"   {key} = {val}")
        return True
    except Exception as e:
        _log(log_callback, f"❌ 写入settings.json失败: {e}")
        return False


# ============================================================
# 依赖包安装
# ============================================================

def _ensure_pip_installed(py_exe: str, log_callback=None) -> bool:
    """确保目标Python解释器已安装pip。嵌入式Python默认没有pip，需要先安装。"""
    # 检查pip是否已可用
    try:
        result = subprocess.run(
            [py_exe, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            _log(log_callback, f"   ✅ pip已安装: {result.stdout.strip()}")
            return True
    except Exception:
        pass

    _log(log_callback, "   pip未检测到，尝试安装...")

    # 策略1: 使用 ensurepip（Python标准库自带）
    try:
        result = subprocess.run(
            [py_exe, "-m", "ensurepip", "--upgrade"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            _log(log_callback, "   ✅ ensurepip 安装pip成功")
            return True
        else:
            _log(log_callback, f"   ⚠️ ensurepip失败: {result.stderr.strip()[:200]}")
    except Exception as e:
        _log(log_callback, f"   ⚠️ ensurepip异常: {e}")

    # 策略2: 下载 get-pip.py 安装
    try:
        import urllib.request
        # 把 get-pip.py 下载到 CADBoard 根目录，方便用户手动执行
        cdboard_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        get_pip_path = os.path.join(cdboard_dir, "get-pip.py")
        if not os.path.exists(get_pip_path):
            _log(log_callback, "   正在下载 get-pip.py...")
            urllib.request.urlretrieve("https://bootstrap.pypa.io/pip/3.7/get-pip.py", get_pip_path)
        result = subprocess.run(
            [py_exe, get_pip_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            _log(log_callback, "   ✅ get-pip.py 安装pip成功")
            return True
        else:
            _log(log_callback, f"   ⚠️ get-pip.py失败: {result.stderr.strip()[:200]}")
    except Exception as e:
        _log(log_callback, f"   ⚠️ get-pip.py异常: {e}")

    return False


def install_packages(
    python_path: Optional[str] = None,
    packages: Optional[List[str]] = None,
    log_callback=None
) -> Dict[str, bool]:
    """
    安装项目所需的Python依赖包

    Args:
        python_path: 使用的Python解释器路径，None则使用当前环境
        packages: 要安装的包列表，None则使用默认清单
        log_callback: 日志回调函数

    Returns:
        {包名: 是否成功} 的字典
    """
    if packages is None:
        packages = REQUIRED_PACKAGES

    results = {}

    # 确定使用的Python解释器
    if python_path and os.path.exists(python_path):
        py_exe = python_path
    else:
        py_exe = sys.executable

    # 嵌入式Python使用 pythonw.exe 会导致子进程问题，改用 python.exe
    if py_exe.endswith("pythonw.exe"):
        py_exe_alt = py_exe.replace("pythonw.exe", "python.exe")
        if os.path.exists(py_exe_alt):
            py_exe = py_exe_alt

    _log(log_callback, f"🐍 使用Python: {py_exe}")

    # Step 0: 确保pip已安装（嵌入式Python需要）
    _log(log_callback, "📦 检查pip...")
    pip_ok = _ensure_pip_installed(py_exe, log_callback)
    if not pip_ok:
        _log(log_callback, "   ❌ pip安装失败，跳过依赖包安装")
        _log(log_callback, "   💡 提示: 如果无法自动安装pip，可以手动下载 get-pip.py 后运行")
        for pkg in packages:
            results[pkg] = False
        return results

    pip_cmd = [py_exe, "-m", "pip"]

    # Step 1: 先升级pip和基础工具
    _log(log_callback, "📦 正在升级pip/setuptools/wheel...")
    try:
        result = subprocess.run(
            pip_cmd + ["install", "--upgrade", "pip", "setuptools", "wheel"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            _log(log_callback, "   ✅ 升级完成")
        else:
            _log(log_callback, f"   ⚠️ 升级输出: {result.stderr.strip()[:200]}")
    except Exception as e:
        _log(log_callback, f"   ⚠️ 升级异常: {e}")

    # 逐个安装包
    for pkg in packages:
        _log(log_callback, f"📦 正在安装 {pkg} ...")

        # 尝试策略1: 强制只使用预编译wheel（避免嵌入式Python缺少编译器的问题）
        try:
            result = subprocess.run(
                pip_cmd + ["install", "--only-binary", ":all:", "--upgrade", pkg],
                capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0:
                _log(log_callback, f"   ✅ {pkg} 安装成功")
                results[pkg] = True
                continue
            else:
                err = _safe_stderr_tail(result)
                _log(log_callback, f"   ⚠️ {pkg} 强制wheel安装失败: {err}")
        except Exception as e:
            _log(log_callback, f"   ⚠️ {pkg} 安装异常: {e}")

        # 尝试策略2: 不限制，允许源码构建（某些包可能没有wheel）
        _log(log_callback, f"   📦 {pkg} 尝试常规安装...")
        try:
            result = subprocess.run(
                pip_cmd + ["install", "--upgrade", pkg],
                capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0:
                _log(log_callback, f"   ✅ {pkg} 安装成功")
                results[pkg] = True
            else:
                err = _safe_stderr_tail(result)
                _log(log_callback, f"   ❌ {pkg} 安装失败: {err}")
                results[pkg] = False
        except subprocess.TimeoutExpired:
            _log(log_callback, f"   ⏱️ {pkg} 安装超时")
            results[pkg] = False
        except Exception as e:
            _log(log_callback, f"   ❌ {pkg} 安装异常: {e}")
            results[pkg] = False

    return results


# ============================================================
# ODA File Converter 安装
# ============================================================

ODA_MSI_URL_64 = "https://download.opendesign.com/guestfiles/ODAFileConverter/ODAFileConverter_QT5_vc14_amd64dll.msi"
ODA_MSI_URL_32 = "https://download.opendesign.com/guestfiles/ODAFileConverter/ODAFileConverter_QT5_vc10dll.msi"
ODA_DEFAULT_PATH = r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"


def _find_odafc_executable() -> Optional[str]:
    """查找 ODAFileConverter 可执行文件路径"""
    # 1. 检查 PATH
    exe = shutil.which("ODAFileConverter")
    if exe:
        return exe
    exe = shutil.which("ODAFileConverter.exe")
    if exe:
        return exe

    # 2. 检查默认安装路径
    if os.path.exists(ODA_DEFAULT_PATH):
        return ODA_DEFAULT_PATH

    # 3. 搜索 Program Files 中可能的安装目录
    for pf in [r"C:\Program Files", r"C:\Program Files (x86)"]:
        if not os.path.exists(pf):
            continue
        for root, dirs, files in os.walk(pf):
            if "ODAFileConverter.exe" in files:
                return os.path.join(root, "ODAFileConverter.exe")
            # 限制搜索深度
            depth = root[len(pf):].count(os.sep)
            if depth > 3:
                del dirs[:]

    return None


def _safe_stderr_tail(result, max_chars: int = 300) -> str:
    """安全地从 subprocess result 中提取 stderr 尾部，避免空值导致异常"""
    try:
        if not result or not hasattr(result, 'stderr'):
            return "无输出"
        stderr = result.stderr
        if stderr is None:
            return "stderr=None"
        text = str(stderr).strip()
        if not text:
            return "无错误输出"
        return text[-max_chars:] if len(text) > max_chars else text
    except Exception:
        return "提取stderr失败"


def _run_msi_install(msi_path: str, log_callback=None, ui_mode: str = "/passive") -> bool:
    """
    使用 subprocess 同步执行 MSI 安装。
    嵌入式Python的subprocess对text=True支持不稳定，改用二进制模式+手动解码。

    Args:
        msi_path: MSI 文件路径
        log_callback: 日志回调
        ui_mode: "/passive"=显示进度条自动完成, "/qn"=完全静默

    Returns:
        安装是否成功
    """
    import subprocess as sp

    try:
        _log(log_callback, f"   🔧 msiexec {ui_mode} ALLUSERS=1 /norestart ...")
        # 不用 text=True，用二进制模式避免嵌入式Python兼容问题
        proc = sp.Popen(
            ["msiexec", "/i", msi_path, "ALLUSERS=1", ui_mode, "/norestart"],
            stdout=sp.PIPE, stderr=sp.PIPE
        )
        stdout_bytes, stderr_bytes = proc.communicate(timeout=120)
        retcode = proc.returncode

        # 手动解码输出
        stdout = stdout_bytes.decode('utf-8', errors='ignore') if stdout_bytes else ""
        stderr = stderr_bytes.decode('utf-8', errors='ignore') if stderr_bytes else ""

        if retcode == 0 or retcode == 3010:  # 3010 = 成功，需要重启
            _log(log_callback, f"   ✅ MSI 安装成功 (exit={retcode})")
            return True
        else:
            # 安全地提取错误信息（避免任何切片操作）
            err_text = stderr.strip()
            if err_text:
                err = err_text if len(err_text) <= 300 else err_text[-300:]
            else:
                err = f"exit code {retcode}"
            _log(log_callback, f"   ⚠️ MSI 安装失败: {err}")
            return False

    except sp.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        _log(log_callback, "   ⚠️ MSI 安装超时（120秒）")
        return False
    except FileNotFoundError:
        _log(log_callback, "   ⚠️ msiexec 未找到")
        return False
    except Exception as e:
        _log(log_callback, f"   ⚠️ MSI 安装异常: {type(e).__name__}: {e}")
        return False


def _find_odafc_all_locations() -> Optional[str]:
    """在更广的范围内搜索 ODAFileConverter.exe"""
    # 1. PATH
    for name in ["ODAFileConverter", "ODAFileConverter.exe"]:
        p = shutil.which(name)
        if p:
            return p

    # 2. 默认安装路径（含各种版本号）
    for p in [
        r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
        r"C:\Program Files (x86)\ODA\ODAFileConverter\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.12\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.11\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.10\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.9\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.8\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.7\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.6\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.5\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.4\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.3\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.2\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 25.1\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 24.12\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 24.11\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 24.10\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 24.9\ODAFileConverter.exe",
        r"C:\Program Files\ODA\ODAFileConverter 24.8\ODAFileConverter.exe",
    ]:
        if os.path.exists(p):
            return p

    # 3. 搜索 Program Files 下的 ODA 目录
    for pf in [r"C:\Program Files", r"C:\Program Files (x86)"]:
        if not os.path.exists(pf):
            continue
        oda_dir = os.path.join(pf, "ODA")
        if os.path.exists(oda_dir):
            for sub in os.listdir(oda_dir):
                exe = os.path.join(oda_dir, sub, "ODAFileConverter.exe")
                if os.path.exists(exe):
                    return exe

    return None


def install_odafc(log_callback=None) -> Tuple[bool, Optional[str]]:
    """
    检测并引导安装 ODA File Converter（用于 DWG 转换）

    注意: ODA 官网已取消免登录下载，无法自动下载安装包。
    此函数只负责:
    1. 检测是否已安装
    2. 如果没安装，自动打开浏览器到下载页面
    3. 提示用户下载安装后重新配置

    Returns:
        (是否已安装, 可执行文件路径)
    """
    # Step 1: 检测是否已安装
    existing = _find_odafc_all_locations()
    if existing:
        _log(log_callback, f"   ✅ ODA File Converter 已安装: {existing}")
        return True, existing

    _log(log_callback, "   ⚠️ 未检测到 ODA File Converter")
    _log(log_callback, "")
    _log(log_callback, "   🌐 正在打开浏览器到 ODA 下载页面...")

    # Step 2: 自动打开浏览器到下载页面
    try:
        import webbrowser
        # ODA File Converter 官方下载页面
        download_url = "https://www.opendesign.com/guestfiles/oda_file_converter"
        webbrowser.open(download_url)
        _log(log_callback, f"   ✅ 已打开浏览器: {download_url}")
    except Exception as e:
        _log(log_callback, f"   ⚠️ 打开浏览器失败: {e}")
        _log(log_callback, "   请手动访问: https://www.opendesign.com/guestfiles/oda_file_converter")

    # Step 3: 提示用户
    _log(log_callback, "")
    _log(log_callback, "   📋 请按以下步骤完成安装:")
    _log(log_callback, "   1. 在浏览器中下载 ODA File Converter (Windows x64)")
    _log(log_callback, "   2. 运行下载的 MSI 安装包，按提示完成安装")
    _log(log_callback, "   3. 安装完成后，重新点击'自动配置环境'按钮")
    _log(log_callback, "")
    _log(log_callback, "   💡 提示: 安装 ODA File Converter 前，导出将使用 DXF 格式")
    _log(log_callback, "   DXF 文件可被 AutoCAD 直接打开，无需额外转换")

    return False, None

# ============================================================
# 主控流程
# ============================================================

def run_environment_configuration(log_callback=None) -> Dict:
    """
    一键配置环境的主入口

    执行完整的环境配置流程:
    1. 检测BIMBase安装
    2. 查找Python解释器和pyp3d路径
    3. 配置VSCode settings.json
    4. 安装依赖包
    5. 安装 ODA File Converter（导出DWG必需）

    Args:
        log_callback: 日志回调函数，接收(str)参数

    Returns:
        配置结果报告字典
    """
    result = {
        'success': True,
        'bimbase_found': False,
        'bimbase_dir': None,
        'python_path': None,
        'pyp3d_path': None,
        'vscode_configured': False,
        'packages': {},
        'odafc_installed': False,
        'odafc_path': None,
        'messages': []
    }

    def _local_log(msg: str):
        result['messages'].append(msg)
        _log(log_callback, msg)

    _local_log("=" * 50)
    _local_log("🔧 CAD画板 - 环境配置开始")
    _local_log("=" * 50)

    # Step 1: 查找BIMBase
    _local_log("")
    _local_log("📍 Step 1: 查找BIMBase安装...")

    installations = find_bimbase_installations()
    if installations:
        _local_log(f"   找到 {len(installations)} 个BIMBase安装:")
        for inst in installations:
            _local_log(f"   - {inst['name']}")

        latest = get_latest_bimbase(installations)
        bimbase_dir = read_instdir_xml(latest)

        result['bimbase_found'] = True
        result['bimbase_dir'] = bimbase_dir
        _local_log(f"   ✅ 使用最新版本: {latest['name']}")
        _local_log(f"   📂 安装路径: {bimbase_dir}")
    else:
        _local_log("   ⚠️ 未找到BIMBase安装，将使用系统Python")
        bimbase_dir = None

    # Step 2: 查找Python和pyp3d
    _local_log("")
    _local_log("📍 Step 2: 查找Python解释器和SDK路径...")

    python_path = None
    pyp3d_path = None

    if bimbase_dir:
        python_path = find_bimbase_python(bimbase_dir)
        if python_path:
            _local_log(f"   ✅ Python: {python_path}")
        else:
            _local_log("   ⚠️ 未找到BIMBase自带Python")

        pyp3d_path = find_pyp3d_path(bimbase_dir)
        if pyp3d_path:
            _local_log(f"   ✅ pyp3d SDK: {pyp3d_path}")
        else:
            _local_log("   ⚠️ 未找到pyp3d模块路径")

    result['python_path'] = python_path
    result['pyp3d_path'] = pyp3d_path

    # Step 3: 配置VSCode
    _local_log("")
    _local_log("📍 Step 3: 配置VSCode settings.json...")

    vscode_ok = configure_vscode_settings(python_path, pyp3d_path, _local_log)
    result['vscode_configured'] = vscode_ok

    # Step 4: 安装依赖包
    _local_log("")
    _local_log("📍 Step 4: 安装依赖包...")
    _local_log(f"   需要安装: {', '.join(REQUIRED_PACKAGES)}")

    pkg_results = install_packages(python_path, None, _local_log)
    result['packages'] = pkg_results

    # Step 5: 安装 ODA File Converter（DWG 导出必需）
    _local_log("")
    _local_log("📍 Step 5: 安装 ODA File Converter（DWG 导出转换器）...")

    odafc_ok, odafc_path = install_odafc(_local_log)
    result['odafc_installed'] = odafc_ok
    result['odafc_path'] = odafc_path

    # 总结
    _local_log("")
    _local_log("=" * 50)
    _local_log("📋 配置结果汇总")
    _local_log("=" * 50)

    if result['bimbase_found']:
        _local_log(f"BIMBase: ✅ {result['bimbase_dir']}")
    else:
        _local_log("BIMBase: ⚠️ 未检测到")

    if result['python_path']:
        _local_log(f"Python: ✅ {result['python_path']}")
    else:
        _local_log(f"Python: ⚠️ 使用系统Python")

    if result['pyp3d_path']:
        _local_log(f"pyp3d SDK: ✅ {result['pyp3d_path']}")
    else:
        _local_log("pyp3d SDK: ⚠️ 未找到")

    _local_log(f"VSCode配置: {'✅' if result['vscode_configured'] else '⚠️'}")

    all_pkg_ok = all(result['packages'].values()) if result['packages'] else False
    if all_pkg_ok:
        _local_log(f"依赖包: ✅ 全部安装成功")
    else:
        for pkg, ok in result['packages'].items():
            status = "✅" if ok else "❌"
            _local_log(f"依赖包 {pkg}: {status}")

    if result['odafc_installed']:
        _local_log(f"ODA转换器: ✅ {result['odafc_path']}")
    else:
        _local_log("ODA转换器: ❌ 未安装（DWG导出将回退到DXF格式）")

    result['success'] = (
        result['bimbase_found'] and
        bool(result['python_path']) and
        bool(result['pyp3d_path']) and
        result['vscode_configured'] and
        all_pkg_ok and
        result['odafc_installed']
    )

    _local_log("")
    if result['success']:
        _local_log("🎉 环境配置全部完成！可以导出 DWG 文件了！")
    else:
        _local_log("⚠️ 环境配置部分完成，请检查上述日志")

    return result


# ============================================================
# 工具函数
# ============================================================

def _log(callback, message: str):
    """输出日志"""
    if callback:
        callback(message)


def get_environment_info() -> Dict:
    """
    获取当前环境信息（用于诊断）

    Returns:
        环境信息字典
    """
    return {
        'sys.executable': sys.executable,
        'sys.version': sys.version,
        'sys.path': sys.path[:5],  # 只显示前5个
        'cwd': os.getcwd(),
        'platform': sys.platform,
    }


# 独立运行入口
if __name__ == "__main__":
    # 命令行模式直接运行配置
    def print_log(msg: str):
        print(msg)

    result = run_environment_configuration(print_log)
    sys.exit(0 if result['success'] else 1)
