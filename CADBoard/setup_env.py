# -*- coding: utf-8 -*-
"""
环境配置入口 - BIMBase插件"自动配置环境"按钮执行脚本

点击"自动配置环境"按钮时，BIMBase通过exec方式执行此脚本。
自动完成：
1. 检测BIMBase安装路径
2. 配置VSCode的Python解释器和pyp3d代码补全
3. 安装项目所需依赖包 (PyQt5, ezdxf)
4. 检测/引导安装 ODA File Converter（DWG导出转换器）

注意: 此脚本在模块末尾直接执行，不依赖__main__入口。
"""

import sys
import os
import traceback

# ============================================================
# 路径设置
# ============================================================

_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

# ============================================================
# 日志系统
# ============================================================

_LOG_FILE = os.path.join(_current_dir, "CADBoard_env_setup.log")


def _write_log(message):
    """将日志追加写入文件，同时尝试print到控制台"""
    try:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        print(message)
    except Exception:
        pass


def _show_result_dialog(title, message, is_success=True):
    """使用Windows API显示消息框，完全不依赖PyQt5"""
    try:
        import ctypes
        MB_OK = 0x0
        MB_ICONINFORMATION = 0x40
        MB_ICONWARNING = 0x30
        icon = MB_ICONINFORMATION if is_success else MB_ICONWARNING
        ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | icon)
    except Exception as e:
        _write_log(f"无法显示对话框: {e}")
        _write_log(f"结果: {title} - {message}")


# ============================================================
# 主配置流程
# ============================================================

def run_env_setup():
    """运行完整的环境配置流程"""
    _write_log("")
    _write_log("=" * 50)
    _write_log("CADBoard 自动配置环境 开始")
    _write_log("=" * 50)

    try:
        _write_log("导入环境配置模块...")
        from utils.env_config import run_environment_configuration
        _write_log("模块导入成功")

        result = run_environment_configuration(_write_log)

        _write_log("")
        _write_log("=" * 50)
        _write_log("配置结果汇总")
        _write_log("=" * 50)

        summary_lines = []
        if result.get('bimbase_found'):
            summary_lines.append(f"BIMBase: 已检测到 ({result['bimbase_dir']})")
        else:
            summary_lines.append("BIMBase: 未检测到")

        if result.get('python_path'):
            summary_lines.append(f"Python: {result['python_path']}")
        else:
            summary_lines.append("Python: 使用系统Python")

        if result.get('pyp3d_path'):
            summary_lines.append(f"pyp3d SDK: {result['pyp3d_path']}")
        else:
            summary_lines.append("pyp3d SDK: 未找到")

        summary_lines.append(f"VSCode配置: {'成功' if result.get('vscode_configured') else '跳过/失败'}")

        pkg_results = result.get('packages', {})
        if pkg_results:
            for pkg, ok in pkg_results.items():
                status = "安装成功" if ok else "安装失败"
                summary_lines.append(f"依赖包 {pkg}: {status}")

        odafc_ok = result.get('odafc_installed', False)
        if odafc_ok:
            summary_lines.append(f"ODA转换器: 已安装 ({result.get('odafc_path', '')})")
        else:
            summary_lines.append("ODA转换器: 未安装（DWG导出将回退到DXF格式）")

        summary_text = "\n".join(summary_lines)
        _write_log(summary_text)

        if result.get('success'):
            _write_log("环境配置全部完成！")
            _show_result_dialog(
                "环境配置完成",
                "环境配置全部完成！\n\n" + summary_text + "\n\n现在可以正常使用CAD画板了。",
                is_success=True
            )
        else:
            _write_log("环境配置部分完成，建议检查日志")
            _show_result_dialog(
                "环境配置部分完成",
                "部分配置未完成，建议检查日志文件排查问题。\n\n" + summary_text + "\n\n日志文件:\n" + _LOG_FILE,
                is_success=False
            )

    except ImportError as e:
        error_msg = f"导入环境配置模块失败: {e}\n{traceback.format_exc()}"
        _write_log(error_msg)
        _show_result_dialog(
            "配置失败",
            f"无法导入环境配置模块，可能缺少依赖。\n\n错误: {e}\n\n"
            f"请手动安装依赖后再试:\n"
            f"python -m pip install PyQt5 ezdxf",
            is_success=False
        )

    except Exception as e:
        error_msg = f"环境配置异常: {e}\n{traceback.format_exc()}"
        _write_log(error_msg)
        _show_result_dialog(
            "配置异常",
            f"配置过程中发生异常:\n{e}\n\n请查看日志:\n{_LOG_FILE}",
            is_success=False
        )


# ============================================================
# BIMBase执行入口 - 模块级别直接执行
# ============================================================

_write_log("")
_write_log("setup_env.py loaded, starting setup...")

try:
    run_env_setup()
    _write_log("环境配置脚本执行完毕")
except Exception as e:
    _write_log(f"环境配置脚本异常终止: {e}")
    _write_log(traceback.format_exc())
