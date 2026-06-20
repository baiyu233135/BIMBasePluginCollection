# -*- coding: utf-8 -*-
"""
BIMBase 进程 PID 注入/校验工具。

pyp3d 运行时在初始化 _Core/Port 时会使用 sys.argv[1] 作为目标 BIMBase
进程 PID。如果 sys.argv[1] 缺失，Port 会回退到查找前台窗口所属的
BIMBase.exe/BIMBASE.exe 进程；当 CADBoard 自己的窗口成为前台窗口时，会
导致连接到错误进程，最终出现 'NoneType' object has no attribute 'send'。

此模块在插件加载早期确保 sys.argv[1] 为当前实际运行的 BIMBase PID，
并在 _Core 损坏恢复时重新校验。
"""

import sys


def _list_bimbase_pids():
    """返回当前系统中 BIMBase/BIMBASE.exe 进程的 PID 列表。"""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        TH32CS_SNAPPROCESS = 0x00000002

        class PROCESSENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", ctypes.c_ulong),
                ("cntUsage", ctypes.c_ulong),
                ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_ulonglong),
                ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong),
                ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("szExeFile", ctypes.c_char * 260),
            ]

        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        entry = PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
        pids = []
        if kernel32.Process32First(snap, ctypes.byref(entry)):
            while True:
                exe = entry.szExeFile.lower()
                if exe in (b"bimbase.exe", b"bimbase.exe"):
                    pids.append(entry.th32ProcessID)
                if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                    break
        kernel32.CloseHandle(snap)
        return pids
    except Exception:
        return []


def ensure_bimbase_pid_argv():
    """确保 sys.argv[1] 为当前实际运行的 BIMBase 进程 PID。"""
    pids = _list_bimbase_pids()
    if not pids:
        # 没有 BIMBase 进程时保留现状，避免破坏其他用途的参数
        return

    current_pid = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        current_pid = int(sys.argv[1])

    if current_pid in pids:
        return

    # 需要更新为可用的 BIMBase PID
    if len(sys.argv) > 1:
        sys.argv[1] = str(pids[0])
    else:
        sys.argv.append(str(pids[0]))
