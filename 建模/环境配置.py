# -*- coding: utf-8 -*-
"""
环境配置入口 - BIMBase建模插件"自动配置环境"按钮执行脚本

功能：
1. 检测 Python 版本
2. 检测 pyp3d SDK 状态
3. 检测/安装 pandas 和 openpyxl
4. 显示配置结果对话框

注意: 此脚本在模块末尾直接执行，不依赖 __main__ 入口。
"""

import sys
import os
import traceback
import subprocess
import ctypes

# ============================================================
# 工具函数
# ============================================================

def _show_dialog(title, message, icon_type=0x40):
    """使用 Windows API 显示消息框"""
    try:
        MB_OK = 0x0
        ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | icon_type)
    except Exception:
        print(message)


def _get_python_version():
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _check_pyp3d():
    """检查 pyp3d 是否可用"""
    try:
        from pyp3d import Vec3
        test = Vec3(0, 0, 0)
        return True, "✓ 已安装且可用"
    except Exception as e:
        return False, f"✗ 异常: {e}"


def _check_package(pkg_name):
    """检查 Python 包是否已安装"""
    try:
        __import__(pkg_name)
        return True, f"✓ 已安装"
    except ImportError:
        return False, f"✗ 未安装"


def _install_package(pkg_name, log_func):
    """使用 pip 安装指定包"""
    try:
        log_func(f"正在安装 {pkg_name} ...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg_name, "-i", "https://pypi.tuna.tsinghua.edu.cn/simple/"],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            log_func(f"  {pkg_name} 安装成功")
            return True
        else:
            log_func(f"  {pkg_name} 安装失败: {result.stderr}")
            return False
    except Exception as e:
        log_func(f"  {pkg_name} 安装异常: {e}")
        return False


# ============================================================
# 主配置流程
# ============================================================

def run_env_setup():
    """运行完整的环境配置流程"""
    logs = []
    
    def log(msg):
        logs.append(msg)
        print(msg)
    
    log("=" * 50)
    log("建模插件 - 自动配置环境")
    log("=" * 50)
    
    # 1. Python 版本
    py_ver = _get_python_version()
    log(f"Python 版本: {py_ver}")
    
    # 2. pyp3d 状态
    pyp3d_ok, pyp3d_msg = _check_pyp3d()
    log(f"pyp3d SDK: {pyp3d_msg}")
    
    # 3. 检查 pandas
    pandas_ok, pandas_msg = _check_package("pandas")
    log(f"pandas: {pandas_msg}")
    
    # 4. 检查 openpyxl
    openpyxl_ok, openpyxl_msg = _check_package("openpyxl")
    log(f"openpyxl: {openpyxl_msg}")
    
    # 5. 自动安装缺失的包
    install_results = []
    if not pandas_ok:
        ok = _install_package("pandas", log)
        install_results.append(("pandas", ok))
    if not openpyxl_ok:
        ok = _install_package("openpyxl", log)
        install_results.append(("openpyxl", ok))
    
    # 6. 重新检查
    if install_results:
        log("")
        log("重新检查安装结果...")
        for pkg, _ in install_results:
            ok, msg = _check_package(pkg)
            log(f"  {pkg}: {msg}")
            if pkg == "pandas":
                pandas_ok = ok
            elif pkg == "openpyxl":
                openpyxl_ok = ok
    
    # 7. 汇总
    all_ok = pyp3d_ok and pandas_ok and openpyxl_ok
    
    log("")
    log("=" * 50)
    log("配置结果汇总")
    log("=" * 50)
    log(f"Python 版本: {py_ver}")
    log(f"pyp3d SDK: {'✓ 正常' if pyp3d_ok else '✗ 异常'}")
    log(f"pandas: {'✓ 正常' if pandas_ok else '✗ 缺失'}")
    log(f"openpyxl: {'✓ 正常' if openpyxl_ok else '✗ 缺失'}")
    log("")
    
    if all_ok:
        log("✓ 环境配置完成！")
        summary = "\n".join(logs)
        _show_dialog(
            "环境配置完成",
            summary + "\n\n现在可以正常使用建模插件了。",
            0x40  # MB_ICONINFORMATION
        )
    else:
        log("△ 环境配置部分完成，部分依赖缺失")
        summary = "\n".join(logs)
        _show_dialog(
            "环境配置未完成",
            summary + "\n\n请手动安装缺失的依赖后再试。\n"
            "命令: python -m pip install pandas openpyxl",
            0x30  # MB_ICONWARNING
        )


# ============================================================
# BIMBase 执行入口 - 模块级别直接执行
# ============================================================

try:
    run_env_setup()
except Exception as e:
    error_msg = f"环境配置异常: {e}\n{traceback.format_exc()}"
    print(error_msg)
    _show_dialog("环境配置异常", error_msg, 0x10)  # MB_ICONERROR
