# -*- coding: utf-8 -*-
"""一键环境自检 / 自动配置（面向插件分发）。

别人拿到 .pyplugin 包后，BIMBase 内置 Python 往往缺依赖，点一下按钮即可补齐：
  1. 定位当前解释器（BIMBase 内置 Python，3.7 embed）
  2. 检查关键依赖导入情况（torch / ultralytics / cv2 / PIL / numpy）
  3. 缺 pip 则补 pip（ensurepip → 联网 get-pip.py）
  4. 必要时修正 pythonXX._pth（取消 #import site 注释，使 site-packages 生效）
  5. 按 Python 3.7 兼容版本安装依赖（torch CPU + ultralytics==8.0.145 + cv2 + PIL + numpy，
     清华镜像 + pytorch cpu 源）
  6. 子进程验证导入，输出配置报告

本模块不依赖 Qt，进度通过 log_cb 回调透出。
"""
import os
import sys
import json
import subprocess
import urllib.request

# Python 3.7 兼容的版本钉死（BIMBase 内置 Python 为 3.7.9 embed）
PIP_PACKAGES = [
    "numpy==1.21.6",
    "Pillow==9.5.0",
    "opencv-python==4.8.1.78",
    "PyYAML==6.0.1",
    "requests==2.31.0",
    "tqdm==4.66.1",
    "matplotlib==3.5.3",
    "pandas==1.3.5",
    "seaborn==0.12.2",
    "ultralytics==8.0.145",
    "python-docx==0.8.11",
]
TORCH_PACKAGES = ["torch==1.13.1+cpu", "torchvision==0.14.1+cpu"]
TORCH_FIND_LINKS = "https://download.pytorch.org/whl/cpu"
PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

# PyQt5 由 BIMBase 自带（装在它内置 Python 的 site-packages），正常不会缺失；
# 仍列入检查——万一被损坏/删除，对话框打不开，这里一并补齐。
REQUIRED_IMPORTS = ["torch", "ultralytics", "cv2", "PIL", "numpy", "yaml",
                    "docx", "PyQt5"]

_CHECK_SCRIPT = "\n".join(
    ["import json", "r = {}"]
    + [
        "try:\n    import {m}\n    r[{m!r}] = getattr({m}, '__version__', 'ok')\n"
        "except Exception as _e:\n"
        "    r[{m!r}] = 'MISSING: %s: %s' % (type(_e).__name__, _e)".format(m=m)
        for m in REQUIRED_IMPORTS
    ]
    + ["print('@@ENV@@' + json.dumps(r, ensure_ascii=False))"]
)


def _is_missing(v):
    return str(v).startswith("MISSING")


def _default_log(msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        # 控制台为 GBK 等窄编码时降级输出（GUI 回调写文件/控件不受影响）
        print(msg.encode(getattr(sys.stdout, "encoding", "utf-8") or "utf-8",
                         errors="replace").decode(
                             getattr(sys.stdout, "encoding", "utf-8") or "utf-8",
                             errors="replace"))


def run_cmd(args, log_cb=_default_log, timeout=None):
    """运行子进程并流式输出（合并 stderr）。返回 (returncode, output)。"""
    log_cb("  $ " + " ".join(str(a) for a in args))
    proc = subprocess.Popen(
        [str(a) for a in args],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, encoding="utf-8", errors="replace",
    )
    out_lines = []
    try:
        for line in proc.stdout:
            line = line.rstrip()
            out_lines.append(line)
            log_cb("  | " + line)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return -9, "\n".join(out_lines)
    return proc.returncode, "\n".join(out_lines)


def check_imports(py=None, log_cb=_default_log):
    """返回 {模块: 版本或 'MISSING'}。"""
    import tempfile
    py = py or sys.executable
    script = os.path.join(tempfile.gettempdir(), "_tunnel_env_check.py")
    try:
        with open(script, "w", encoding="utf-8") as f:
            f.write(_CHECK_SCRIPT)
        rc, out = run_cmd([py, script], log_cb=lambda m: None)
    finally:
        try:
            os.remove(script)
        except OSError:
            pass
    for line in out.splitlines():
        if line.startswith("@@ENV@@"):
            try:
                return json.loads(line[len("@@ENV@@"):])
            except Exception:
                break
    return {m: "MISSING: 检查脚本自身执行失败" for m in REQUIRED_IMPORTS}


def ensure_pip(py, log_cb=_default_log):
    """确保 pip 可用。返回 True/False。"""
    rc, _ = run_cmd([py, "-m", "pip", "--version"], log_cb=log_cb)
    if rc == 0:
        return True
    log_cb("pip 缺失，尝试 ensurepip ...")
    rc, _ = run_cmd([py, "-m", "ensurepip", "--upgrade"], log_cb=log_cb)
    if rc == 0:
        return True
    log_cb("ensurepip 不可用，联网下载 get-pip.py ...")

    import py_compile
    import time

    gp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "_get_pip.py")

    def _valid_get_pip(path):
        if not os.path.isfile(path):
            return False
        # 正常 get-pip.py 远大于 100KB，过小说明下载中断/为空
        if os.path.getsize(path) < 100 * 1024:
            return False
        try:
            py_compile.compile(path, doraise=True)
            return True
        except Exception:
            return False

    def _download_get_pip(path, timeout=60):
        url = "https://bootstrap.pypa.io/pip/3.7/get-pip.py"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        with open(path, "wb") as f:
            f.write(data)

    # 若本地已有残损文件，先删除，避免一直复用
    if os.path.isfile(gp) and not _valid_get_pip(gp):
        log_cb("检测到已下载的 _get_pip.py 损坏/不完整，删除后重新下载 ...")
        try:
            os.remove(gp)
        except Exception as e:
            log_cb(f"删除残损 _get_pip.py 失败: {e}")

    # 最多尝试下载并执行两次
    for attempt in range(2):
        if not os.path.isfile(gp):
            try:
                _download_get_pip(gp)
            except Exception as e:
                log_cb(f"get-pip.py 下载失败: {e}")
                if attempt == 0:
                    log_cb("5秒后重试 ...")
                    time.sleep(5)
                continue

        if not _valid_get_pip(gp):
            log_cb("下载的 _get_pip.py 校验失败，删除后重试 ...")
            try:
                os.remove(gp)
            except Exception:
                pass
            if attempt == 0:
                time.sleep(1)
            continue

        rc, _ = run_cmd([py, gp], log_cb=log_cb)
        if rc == 0:
            return True

        log_cb("get-pip.py 执行失败，清理后重试 ...")
        try:
            os.remove(gp)
        except Exception:
            pass

    log_cb("✗ pip 初始化失败：请检查网络后重试（或在有网环境手动安装 pip）")
    return False


def fix_embed_pth(py, log_cb=_default_log):
    """嵌入式 Python 需要 _pth 启用 site（取消 '#import site' 注释），
    否则 pip 装到 site-packages 的包 import 不到。"""
    py_dir = os.path.dirname(os.path.abspath(py))
    ver = "python{}{}".format(sys.version_info.major, sys.version_info.minor)
    pth = os.path.join(py_dir, ver + "._pth")
    if not os.path.isfile(pth):
        return  # 非嵌入式布局，无需处理
    try:
        with open(pth, encoding="utf-8", errors="replace") as f:
            content = f.read()
        if "import site" in content and "#import site" not in content:
            log_cb(f"{os.path.basename(pth)} 已启用 site，跳过")
            return
        new = content.replace("#import site", "import site")
        if new == content:
            log_cb(f"{os.path.basename(pth)} 中未找到 #import site 行（请手工检查）")
            return
        try:
            with open(pth, "w", encoding="utf-8") as f:
                f.write(new)
            log_cb(f"已修正 {os.path.basename(pth)}：启用 import site")
        except PermissionError:
            log_cb(f"⚠ 无权限写 {pth}，请用管理员身份运行 BIMBase 后重试")
    except Exception as e:
        log_cb(f"检查 _pth 失败（忽略，继续）: {e}")


def install_packages(py, log_cb=_default_log, extra=()):
    """安装依赖（extra 为按需追加的包，如缺失的 PyQt5）。返回 True/False。"""
    mirror = ["-i", PIP_MIRROR]
    ok = True
    log_cb("安装 torch CPU 版（约 170MB，最慢的一步）...")
    rc, _ = run_cmd([py, "-m", "pip", "install", "--upgrade"] + TORCH_PACKAGES
                    + ["-f", TORCH_FIND_LINKS] + mirror, log_cb=log_cb)
    if rc != 0:
        # +cpu 版本只在 download.pytorch.org 提供；该源被墙/不可达时，
        # 退回镜像站的 torch==1.13.1（Windows 官方 wheel 本身就是 CPU 版）
        log_cb("pytorch 专用源不可用，改用镜像站安装 torch==1.13.1 "
               "（Windows 版即为 CPU 版）...")
        rc, _ = run_cmd([py, "-m", "pip", "install", "--upgrade",
                         "torch==1.13.1", "torchvision==0.14.1"] + mirror,
                        log_cb=log_cb)
    ok = ok and rc == 0
    log_cb("安装其余依赖（ultralytics/cv2/PIL/numpy ...）...")
    rc, _ = run_cmd([py, "-m", "pip", "install", "--upgrade"] + PIP_PACKAGES
                    + mirror, log_cb=log_cb)
    ok = ok and rc == 0
    if extra:
        log_cb("安装额外缺失依赖（%s）..." % ", ".join(extra))
        # --only-binary :all: 禁止从源码编译（目标机通常没有 MSVC 编译器，
        # 例如 PyQt5-sip 12.13+ 已放弃 Python 3.7 只剩源码包）
        rc, _ = run_cmd([py, "-m", "pip", "install", "--upgrade",
                         "--only-binary", ":all:"] + list(extra)
                        + mirror, log_cb=log_cb)
        ok = ok and rc == 0
    return ok


def auto_setup(log_cb=_default_log):
    """一键配置入口。返回 (成功: bool, 报告: str)。"""
    lines = []
    def log(msg):
        lines.append(msg)
        log_cb(msg)

    py = sys.executable
    log(f"目标解释器: {py}")
    log(f"Python 版本: {sys.version.split()[0]}")

    log("① 检查当前依赖 ...")
    before = check_imports(py)
    missing = [m for m, v in before.items() if _is_missing(v)]
    log("   " + "，".join(f"{m}={v}" for m, v in before.items()))
    if not missing:
        log("✓ 依赖齐全，无需配置")
        return True, "\n".join(lines)

    log(f"② 缺失: {', '.join(missing)}，开始配置")
    if not ensure_pip(py, log):
        log("✗ pip 初始化失败：请检查网络后重试（或在有网环境手动安装 pip）")
        return False, "\n".join(lines)
    fix_embed_pth(py, log)

    log("③ 安装依赖（可能需要 10~30 分钟，视网络而定）...")
    # PyQt5 正常由 BIMBase 自带；仅在缺失时补装。
    # 5.15.9 是支持 Python 3.7 的末版；PyQt5-sip 必须钉 12.12.2
    # （12.13+ 放弃 Python 3.7，无预编译 wheel，会触发现场编译而失败）
    extra = (["PyQt5-sip==12.12.2", "PyQt5-Qt5==5.15.2", "PyQt5==5.15.9"]
             if "PyQt5" in missing else [])
    if not install_packages(py, log, extra=extra):
        log("✗ 部分依赖安装失败（见上方日志），可点击按钮重试")
        return False, "\n".join(lines)

    log("④ 验证导入 ...")
    after = check_imports(py)
    still = [m for m, v in after.items() if _is_missing(v)]
    log("   " + "，".join(f"{m}={v}" for m, v in after.items()))
    if still:
        log(f"✗ 仍无法导入: {', '.join(still)}（可重试；或重启 BIMBase 后再试）")
        return False, "\n".join(lines)
    log("✓ 环境配置完成，识别功能已可用（如仍异常请重启 BIMBase）")
    return True, "\n".join(lines)
