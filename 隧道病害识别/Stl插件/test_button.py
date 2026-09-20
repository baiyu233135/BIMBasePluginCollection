from pyp3d.tool import messages
import os
import subprocess
import sys

def find_suitable_python():
    """扫描系统中可用的Python 3.9+，返回 (python_cmd, version_str, has_pymeshlab)"""
    # 常见安装路径（按推荐程度排序）
    candidates = []
    
    # 用户目录下的Python
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        for ver in ["Python313", "Python312", "Python311", "Python310", "Python39"]:
            candidates.append(os.path.join(localappdata, "Programs", "Python", ver, "python.exe"))
    
    # 全局安装路径
    for ver in ["Python313", "Python312", "Python311", "Python310", "Python39"]:
        candidates.append(fr"C:\{ver}\python.exe")
        candidates.append(fr"C:\Program Files\{ver}\python.exe")
    
    # 本机已知路径（向后兼容）
    candidates.append(r"D:\zengpython3.13.2\python.exe")
    
    # PATH中的python
    candidates.append("python")
    
    # py launcher（按版本从高到低）
    for ver in ["-3.13", "-3.12", "-3.11", "-3.10", "-3.9"]:
        candidates.append(f"py {ver}")
    candidates.append("py")
    
    for c in candidates:
        try:
            # 获取版本
            if c.startswith("py "):
                cmd = c.split() + ["--version"]
            else:
                cmd = [c, "--version"]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=False)
            if result.returncode != 0:
                continue
            
            output = result.stdout.strip() or result.stderr.strip()
            parts = output.split()
            if len(parts) < 2 or not parts[1][0].isdigit():
                continue
            
            version_str = parts[1]
            ver_parts = version_str.split(".")
            major = int(ver_parts[0])
            minor_str = ver_parts[1] if len(ver_parts) > 1 else "0"
            
            # 排除 free-threaded（如 3.13t）
            if "t" in minor_str:
                continue
            
            minor = int(minor_str.replace("t", ""))
            
            # 需要 Python 3.9+
            if major < 3 or (major == 3 and minor < 9):
                continue
            
            # 检查 pymeshlab
            if c.startswith("py "):
                check_cmd = c.split() + ["-c", "import pymeshlab; print('OK')"]
            else:
                check_cmd = [c, "-c", "import pymeshlab; print('OK')"]
            
            result2 = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10, shell=False)
            has_pymeshlab = result2.returncode == 0 and "OK" in result2.stdout
            
            return c, version_str, has_pymeshlab
            
        except Exception:
            continue
    
    return None, None, False

def install_pymeshlab(python_cmd):
    """自动安装 pymeshlab"""
    try:
        if python_cmd.startswith("py "):
            cmd = python_cmd.split() + ["-m", "pip", "install", "pymeshlab", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
        else:
            cmd = [python_cmd, "-m", "pip", "install", "pymeshlab", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
        subprocess.check_call(cmd, timeout=180)
        return True
    except Exception:
        return False

if __name__ == "__main__":
    python_cmd, version, has_pymeshlab = find_suitable_python()
    
    if python_cmd is None:
        messages(
            "【环境检测失败】\n\n"
            "找不到可用的 Python 3.9+ 解释器。\n\n"
            "请先安装 Python 3.9 或更高版本：\n"
            "https://www.python.org/downloads/\n\n"
            "安装时请务必勾选【Add Python to PATH】，\n"
            "推荐安装 Python 3.13。"
        )
        exit()
    
    if not has_pymeshlab:
        messages(f"检测到 Python {version}，正在自动安装 pymeshlab，请稍候...")
        if install_pymeshlab(python_cmd):
            messages("pymeshlab 安装成功，请重新点击【FBX转STL工具】按钮。")
        else:
            messages(
                f"【自动安装失败】\n\n"
                f"Python 版本: {version}\n"
                f"路径: {python_cmd}\n\n"
                f"请手动打开命令行运行：\n"
                f"{python_cmd} -m pip install pymeshlab\n\n"
                f"或使用国内镜像：\n"
                f"{python_cmd} -m pip install pymeshlab -i https://pypi.tuna.tsinghua.edu.cn/simple"
            )
        exit()
    
    # 一切就绪，启动转换工具
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(current_dir, "FBX转STL工具.py")
    
    if not os.path.exists(script):
        messages(f"找不到转换脚本:\n{script}")
        exit()
    
    try:
        subprocess.Popen([python_cmd, script], shell=False, creationflags=0x08000000)
        messages(f"FBX转STL工具已启动（Python {version}）。\n请在弹出的窗口中操作。")
    except Exception as e:
        messages(f"启动失败: {str(e)}")
