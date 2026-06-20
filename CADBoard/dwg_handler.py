# -*- coding: utf-8 -*-
"""
DWG/DXF导入导出处理器

修复: ODA File Converter路径查找深度增加至4层，支持版本号子目录
"""

import os
import subprocess as sp
import shutil
import tempfile
from typing import List, Tuple, Optional


def import_dwg(file_path: str, log_callback=None) -> Tuple[List, List[str]]:
    """导入DWG/DXF文件"""
    errors = []
    elements = []

    if not os.path.exists(file_path):
        return elements, [f"文件不存在: {file_path}"]

    ext = os.path.splitext(file_path)[1].lower()
    dxf_path = file_path

    if ext == '.dwg':
        dxf_path, err = _convert_dwg_to_dxf(file_path, log_callback)
        if err:
            errors.append(err)
        if not dxf_path or not os.path.exists(dxf_path):
            return elements, errors + ["DWG转DXF失败，无法导入"]

    try:
        elements, parse_errors = _parse_dxf(dxf_path, log_callback)
        errors.extend(parse_errors)
    except Exception as e:
        errors.append(f"解析DXF失败: {e}")

    return elements, errors


def _convert_dwg_to_dxf(dwg_path: str, log_callback=None) -> Tuple[Optional[str], Optional[str]]:
    """使用ODA File Converter将DWG转为DXF"""
    oda_exe = _find_oda_converter()
    if not oda_exe:
        return None, "未找到ODA File Converter。请先安装ODA File Converter。"

    try:
        temp_in = tempfile.mkdtemp(prefix="oda_import_in_")
        temp_out = tempfile.mkdtemp(prefix="oda_import_out_")
        basename = os.path.splitext(os.path.basename(dwg_path))[0]
        temp_dwg = os.path.join(temp_in, basename + ".dwg")
        shutil.copy2(dwg_path, temp_dwg)

        proc = sp.Popen(
            [oda_exe, temp_in, temp_out, "ACAD2018", "DXF", "0", "1"],
            stdout=sp.PIPE, stderr=sp.PIPE, text=True
        )
        stdout, stderr = proc.communicate(timeout=120)

        # ODAFileConverter输出在子目录中
        for root, dirs, files in os.walk(temp_out):
            for f in files:
                if f.lower().endswith('.dxf'):
                    found = os.path.join(root, f)
                    final_dxf = os.path.join(tempfile.gettempdir(), basename + "_import.dxf")
                    shutil.copy2(found, final_dxf)
                    _safe_rmtree(temp_in)
                    _safe_rmtree(temp_out)
                    return final_dxf, None

        _safe_rmtree(temp_in)
        _safe_rmtree(temp_out)
        return None, f"ODA转换未生成DXF文件 (exit={proc.returncode})"

    except Exception as e:
        return None, f"DWG转DXF异常: {e}"


def _find_oda_converter() -> Optional[str]:
    """查找ODAFileConverter可执行文件 - 支持版本号子目录"""
    # 1. PATH环境变量查找
    for name in ["ODAFileConverter", "ODAFileConverter.exe"]:
        p = shutil.which(name)
        if p and os.path.exists(p):
            return p

    # 2. 常见安装路径递归查找（深度放宽到5层，支持版本号目录）
    search_roots = [
        r"C:\Program Files\ODA",
        r"C:\Program Files (x86)\ODA",
        r"C:\Program Files\Open Design Alliance",
        r"C:\Program Files (x86)\Open Design Alliance",
    ]
    for base in search_roots:
        if not os.path.exists(base):
            continue
        for root, dirs, files in os.walk(base):
            if "ODAFileConverter.exe" in files:
                exe_path = os.path.join(root, "ODAFileConverter.exe")
                if os.path.exists(exe_path):
                    return exe_path
            # 限制搜索深度5层，避免遍历太深
            depth = root[len(base):].count(os.sep)
            if depth > 5:
                del dirs[:]

    # 3. 直接搜索Program Files下所有包含ODA的目录
    for pf in [r"C:\Program Files", r"C:\Program Files (x86)"]:
        if not os.path.exists(pf):
            continue
        try:
            for entry in os.listdir(pf):
                if "ODA" in entry.upper():
                    full_path = os.path.join(pf, entry)
                    if os.path.isdir(full_path):
                        for root, dirs, files in os.walk(full_path):
                            if "ODAFileConverter.exe" in files:
                                return os.path.join(root, "ODAFileConverter.exe")
                            depth = root[len(full_path):].count(os.sep)
                            if depth > 3:
                                del dirs[:]
        except (PermissionError, OSError):
            pass

    return None


def _safe_rmtree(path: str):
    try:
        shutil.rmtree(path)
    except Exception:
        pass


def _parse_dxf(dxf_path: str, log_callback=None) -> Tuple[List, List[str]]:
    try:
        import ezdxf
    except ImportError:
        return [], ["未安装ezdxf。请运行环境配置安装依赖。"]

    elements = []
    errors = []
    layers_found = set()

    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        for entity in msp:
            try:
                layer_name = entity.dxf.layer if hasattr(entity.dxf, 'layer') else '0'
                layers_found.add(layer_name)

                elem = _convert_entity(entity)
                if elem:
                    elem.style.layer_name = layer_name
                    if hasattr(entity.dxf, 'color'):
                        c = entity.dxf.color
                        if c and c > 0:
                            rgb = _aci_to_rgb(c)
                            if rgb:
                                elem.style.color = rgb
                    elements.append(elem)
            except Exception as e:
                errors.append(f"解析实体 {entity.dxftype()} 失败: {e}")

    except Exception as e:
        errors.append(f"读取DXF文件失败: {e}")

    if log_callback:
        log_callback(f"DXF导入完成: {len(elements)} 个实体, 图层: {', '.join(layers_found)}")

    return elements, errors


def _convert_entity(entity):
    dxftype = entity.dxftype()

    if dxftype == 'LINE':
        from geometry.elements import LineElement
        s = entity.dxf.start
        e = entity.dxf.end
        return LineElement(s.x, s.y, e.x, e.y)

    elif dxftype == 'CIRCLE':
        from geometry.elements import CircleElement
        c = entity.dxf.center
        return CircleElement(c.x, c.y, entity.dxf.radius)

    elif dxftype == 'ARC':
        from geometry.elements import ArcElement
        c = entity.dxf.center
        return ArcElement(c.x, c.y, entity.dxf.radius,
                         entity.dxf.start_angle, entity.dxf.end_angle)

    elif dxftype in ('LWPOLYLINE', 'POLYLINE'):
        from geometry.elements import PolylineElement
        points = []
        closed = False
        if dxftype == 'LWPOLYLINE':
            for p in entity.get_points():
                points.append((p[0], p[1]))
            closed = entity.closed
        else:
            for v in entity.vertices:
                points.append((v.dxf.location.x, v.dxf.location.y))
            closed = entity.is_closed
        return PolylineElement(points, closed)

    elif dxftype == 'ELLIPSE':
        from geometry.elements import EllipseElement
        import math
        c = entity.dxf.center
        mx = entity.dxf.major_axis
        ratio = entity.dxf.ratio
        rx = (mx.x**2 + mx.y**2)**0.5
        rot = 0
        if abs(mx.x) > 1e-9:
            rot = math.degrees(math.atan2(mx.y, mx.x))
        ry = rx * ratio
        return EllipseElement(c.x, c.y, rx, ry, rot)

    elif dxftype == 'POINT':
        from geometry.elements import PointElement
        p = entity.dxf.location
        return PointElement(p.x, p.y)

    elif dxftype == 'SPLINE':
        from geometry.elements import PolylineElement
        points = []
        if hasattr(entity, 'control_points'):
            for cp in entity.control_points:
                points.append((cp.x, cp.y))
        elif hasattr(entity, 'fit_points'):
            for fp in entity.fit_points:
                points.append((fp.x, fp.y))
        if len(points) >= 2:
            return PolylineElement(points, closed=False)

    return None


def _aci_to_rgb(aci: int) -> Optional[Tuple[int, int, int]]:
    common_colors = {
        1: (255, 0, 0), 2: (255, 255, 0), 3: (0, 255, 0),
        4: (0, 255, 255), 5: (0, 0, 255), 6: (255, 0, 255),
        7: (255, 255, 255), 8: (128, 128, 128), 9: (192, 192, 192),
    }
    return common_colors.get(aci)


def convert_dxf_to_dwg(dxf_path: str, dwg_path: str) -> Tuple[bool, str]:
    """使用ODA将DXF转为DWG - 供board.py导出调用"""
    oda_exe = _find_oda_converter()
    if not oda_exe:
        return False, "未找到ODA File Converter"

    temp_in_dir = None
    temp_out_dir = None
    try:
        dxf_basename = os.path.splitext(os.path.basename(dxf_path))[0]
        temp_in_dir = tempfile.mkdtemp(prefix="oda_in_")
        temp_dxf = os.path.join(temp_in_dir, dxf_basename + ".dxf")
        shutil.copy2(dxf_path, temp_dxf)
        temp_out_dir = tempfile.mkdtemp(prefix="oda_out_")
        proc = sp.Popen(
            [oda_exe, temp_in_dir, temp_out_dir, "ACAD2018", "DWG", "0", "1"],
            stdout=sp.PIPE, stderr=sp.PIPE, text=True
        )
        stdout, stderr = proc.communicate(timeout=120)

        # ODA输出可能在子目录
        for root, dirs, files in os.walk(temp_out_dir):
            for f in files:
                if f.lower().endswith('.dwg'):
                    temp_dwg = os.path.join(root, f)
                    shutil.copy2(temp_dwg, dwg_path)
                    return True, ""

        return False, f"ODA未生成DWG文件，stdout={stdout[:200]}"
    except Exception as e:
        return False, f"转换异常: {e}"
    finally:
        for td in [temp_in_dir, temp_out_dir]:
            if td and os.path.exists(td):
                try:
                    shutil.rmtree(td)
                except Exception:
                    pass
