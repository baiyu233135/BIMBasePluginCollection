# -*- coding: utf-8 -*-
"""
几何体导出器：生成标准格式文件并导入 BIMBase
支持 OBJ（三角网格）和 IFC（BIM 实体）
"""
import math
import os
import uuid
import tempfile

# ============================================================
# OBJ 导出器（ASCII 三角网格）
# ============================================================

def _write_obj(path, vertices, faces, normals=None):
    """写入标准 OBJ 文件"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# BIMBase AI Generated OBJ\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        if normals:
            for n in normals:
                f.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
            for face in faces:
                f.write(f"f {' '.join(f'{idx}//{idx}' for idx in face)}\n")
        else:
            for face in faces:
                f.write(f"f {' '.join(str(idx) for idx in face)}\n")


def export_cylinder_obj(path, radius, height, cx, cy, cz, segments=32):
    """圆柱体 OBJ：底圆+顶圆+侧面"""
    vertices = []
    faces = []
    normals = []

    # 底部圆中心 (索引1)
    vertices.append((cx, cy, cz))
    normals.append((0, 0, -1))
    # 顶部圆中心 (索引2)
    vertices.append((cx, cy, cz + height))
    normals.append((0, 0, 1))

    # 底部圆周顶点 (索引 3 .. 2+segments)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        vertices.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle), cz))
        normals.append((0, 0, -1))

    # 顶部圆周顶点 (索引 3+segments .. 2+2*segments)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        vertices.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle), cz + height))
        normals.append((0, 0, 1))

    # 底面（法线向下，顺时针从上方看）
    for i in range(segments):
        nxt = (i + 1) % segments
        faces.append((1, 3 + nxt, 3 + i))

    # 顶面（法线向上，逆时针从上方看）
    top_off = 2 + segments
    for i in range(segments):
        nxt = (i + 1) % segments
        faces.append((2, top_off + i, top_off + nxt))

    # 侧面（每个四边形分成两个三角形，法线朝外）
    for i in range(segments):
        nxt = (i + 1) % segments
        b0 = 3 + i
        b1 = 3 + nxt
        t0 = top_off + i
        t1 = top_off + nxt
        # 外法线
        angle = 2 * math.pi * i / segments
        nx = math.cos(angle)
        ny = math.sin(angle)
        normals[b0 - 1] = (nx, ny, 0)
        normals[b1 - 1] = (nx, ny, 0)
        normals[t0 - 1] = (nx, ny, 0)
        normals[t1 - 1] = (nx, ny, 0)
        faces.append((b0, t0, t1))
        faces.append((b0, t1, b1))

    _write_obj(path, vertices, faces, normals)


def export_box_obj(path, length, width, height, cx, cy, cz):
    """长方体 OBJ"""
    x0, y0, z0 = cx, cy, cz
    x1, y1, z1 = cx + length, cy + width, cz + height

    vertices = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    normals = [
        (0, 0, -1), (0, 0, 1),
        (0, -1, 0), (0, 1, 0),
        (-1, 0, 0), (1, 0, 0),
    ]
    # 面：底(z-), 顶(z+), 前(y-), 后(y+), 左(x-), 右(x+)
    faces = [
        (1, 3, 2), (1, 4, 3),           # 底面  (法线1)
        (5, 6, 7), (5, 7, 8),           # 顶面  (法线2)
        (1, 2, 6), (1, 6, 5),           # 前面  (法线3)
        (3, 4, 8), (3, 8, 7),           # 后面  (法线4)
        (1, 5, 8), (1, 8, 4),           # 左面  (法线5)
        (2, 3, 7), (2, 7, 6),           # 右面  (法线6)
    ]
    # 为每个顶点分配对应的法线索引（简化：每个面用统一法线）
    # OBJ f 语句支持 vn 索引，但这里我们直接为每个面的顶点指定 vn
    # 重新构造：每个面有独立的 vn 索引
    face_vn = [
        (1, 1, 1), (1, 1, 1),           # 底面
        (2, 2, 2), (2, 2, 2),           # 顶面
        (3, 3, 3), (3, 3, 3),           # 前面
        (4, 4, 4), (4, 4, 4),           # 后面
        (5, 5, 5), (5, 5, 5),           # 左面
        (6, 6, 6), (6, 6, 6),           # 右面
    ]
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# BIMBase AI Generated OBJ\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for n in normals:
            f.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
        for fi, face in enumerate(faces):
            vn = face_vn[fi]
            f.write(f"f {' '.join(f'{v}//{vn[i]}' for i, v in enumerate(face))}\n")


def export_sphere_obj(path, radius, cx, cy, cz, stacks=16, slices=16):
    """球体 OBJ"""
    vertices = []
    normals = []
    faces = []

    for i in range(stacks + 1):
        phi = math.pi * i / stacks
        for j in range(slices):
            theta = 2 * math.pi * j / slices
            x = cx + radius * math.sin(phi) * math.cos(theta)
            y = cy + radius * math.sin(phi) * math.sin(theta)
            z = cz + radius * math.cos(phi)
            vertices.append((x, y, z))
            nx = math.sin(phi) * math.cos(theta)
            ny = math.sin(phi) * math.sin(theta)
            nz = math.cos(phi)
            normals.append((nx, ny, nz))

    for i in range(stacks):
        for j in range(slices):
            i0 = i * slices + j
            i1 = i0 + 1 if j < slices - 1 else i * slices
            i2 = (i + 1) * slices + j
            i3 = i2 + 1 if j < slices - 1 else (i + 1) * slices
            if i > 0:
                faces.append((i0 + 1, i2 + 1, i1 + 1))
            if i < stacks - 1:
                faces.append((i1 + 1, i2 + 1, i3 + 1))

    with open(path, 'w', encoding='utf-8') as f:
        f.write("# BIMBase AI Generated OBJ\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for n in normals:
            f.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
        for face in faces:
            f.write(f"f {' '.join(f'{idx}//{idx}' for idx in face)}\n")


def export_cone_obj(path, radius, height, cx, cy, cz, segments=32):
    """圆锥体 OBJ"""
    vertices = []
    normals = []
    faces = []

    # 底面中心
    vertices.append((cx, cy, cz))
    normals.append((0, 0, -1))
    # 顶点
    vertices.append((cx, cy, cz + height))
    normals.append((0, 0, 1))

    # 底面圆周
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        vertices.append((x, y, cz))
        normals.append((0, 0, -1))

    # 底面
    for i in range(segments):
        nxt = (i + 1) % segments
        faces.append((1, 3 + nxt, 3 + i))

    # 侧面
    apex = 2
    for i in range(segments):
        nxt = (i + 1) % segments
        base = 3 + i
        base_nxt = 3 + nxt
        faces.append((apex, base, base_nxt))
        # 侧面法线（近似）
        angle = 2 * math.pi * i / segments
        slant = math.sqrt(radius**2 + height**2)
        nx = height * math.cos(angle) / slant
        ny = height * math.sin(angle) / slant
        nz = radius / slant
        normals[base - 1] = (nx, ny, nz)
        normals[base_nxt - 1] = (nx, ny, nz)

    with open(path, 'w', encoding='utf-8') as f:
        f.write("# BIMBase AI Generated OBJ\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for n in normals:
            f.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
        for face in faces:
            f.write(f"f {' '.join(f'{idx}//{idx}' for idx in face)}\n")


# ============================================================
# IFC 导出器（IFC2X3 SPF 纯文本，无需 ifcopenshell）
# ============================================================

def _ifc_guid():
    """生成 IFC 兼容的 GUID（22字符 base64）"""
    # 简化：使用 uuid4 的前16字节，编码为 base64 变体
    import base64
    raw = uuid.uuid4().bytes[:16]
    # IFC 使用特定的 base64 字母表
    table = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
    result = []
    for i in range(0, 16, 3):
        chunk = raw[i:i+3]
        n = int.from_bytes(chunk.ljust(3, b'\x00'), 'big')
        result.append(table[(n >> 18) & 0x3F])
        result.append(table[(n >> 12) & 0x3F])
        result.append(table[(n >> 6) & 0x3F])
        result.append(table[n & 0x3F])
    return ''.join(result[:22])


def _ifc_header(filename, schema='IFC2X3'):
    from datetime import datetime
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    return f"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'), '2;1');
FILE_NAME('{filename}', '{now}', ('AI'), ('AI'), 'BIMBase AI Modeling', 'BIMBase AI', '');
FILE_SCHEMA(('{schema}'));
ENDSEC;
DATA;
"""


def _ifc_footer():
    return """ENDSEC;
END-ISO-10303-21;
"""


def _ifc_box_body(entities, cx, cy, cz, length, width, height):
    """向实体列表追加长方体的 IFC 几何定义，返回 root entity id"""
    # 简化的 IFC 实体图
    entities.append(f"#1=IFCPERSON($,$,'AI',$,$,$,$,$);")
    entities.append(f"#2=IFCORGANIZATION($,'AI',$,$,$);")
    entities.append(f"#3=IFCPERSONANDORGANIZATION(#1,#2,$);")
    entities.append(f"#4=IFCAPPLICATION(#2,'1.0','AI','AI');")
    entities.append(f"#5=IFCOWNERHISTORY(#3,#4,$,.ADDED.,$,#3,#4,0);")
    entities.append(f"#6=IFCDIRECTION((1.,0.,0.));")
    entities.append(f"#7=IFCDIRECTION((0.,0.,1.));")
    entities.append(f"#8=IFCCARTESIANPOINT((0.,0.,0.));")
    entities.append(f"#9=IFCAXIS2PLACEMENT3D(#8,#7,#6);")
    entities.append(f"#10=IFCDIRECTION((0.,1.,0.));")
    entities.append(f"#11=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-5,#9,#10);")
    entities.append(f"#12=IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,#11,$,.MODEL_VIEW.,$);")
    entities.append(f"#13=IFCCARTESIANPOINT((0.,0.));")
    entities.append(f"#14=IFCDIRECTION((1.,0.));")
    entities.append(f"#15=IFCDIRECTION((0.,1.));")
    entities.append(f"#16=IFCAXIS2PLACEMENT2D(#13,#14,#15);")
    entities.append(f"#17=IFCRECTANGLEPROFILEDEF(.AREA.,$,#16,{length:.6f},{width:.6f});")
    entities.append(f"#18=IFCCARTESIANPOINT(({cx:.6f},{cy:.6f},{cz:.6f}));")
    entities.append(f"#19=IFCDIRECTION((0.,0.,1.));")
    entities.append(f"#20=IFCDIRECTION((1.,0.,0.));")
    entities.append(f"#21=IFCAXIS2PLACEMENT3D(#18,#19,#20);")
    entities.append(f"#22=IFCDIRECTION((0.,0.,1.));")
    entities.append(f"#23=IFCEXTRUDEDAREASOLID(#17,#21,#22,{height:.6f});")
    entities.append(f"#24=IFCSHAPEREPRESENTATION(#12,'Body','SweptSolid',(#23));")
    entities.append(f"#25=IFCPRODUCTDEFINITIONSHAPE($,$,(#24));")
    entities.append(f"#26=IFCCARTESIANPOINT(({cx:.6f},{cy:.6f},{cz:.6f}));")
    entities.append(f"#27=IFCAXIS2PLACEMENT3D(#26,$,$);")
    entities.append(f"#28=IFCLOCALPLACEMENT($,#27);")
    guid = _ifc_guid()
    entities.append(f"#29=IFCBUILDINGELEMENTPROXY('{guid}',#5,'Box','Box',$,#28,#25,$,.NOTDEFINED.);")
    entities.append(f"#30=IFCPROJECT('{_ifc_guid()}',#5,'AI Project',$,$,$,$,(#11),#11);")
    entities.append(f"#31=IFCSITE('{_ifc_guid()}',#5,$,$,$,$,$,$,.ELEMENT.,$,$,$,$,$);")
    entities.append(f"#32=IFCBUILDING('{_ifc_guid()}',#5,$,$,$,$,$,$,.ELEMENT.,$,$,$,$,$,$);")
    entities.append(f"#33=IFCBUILDINGSTOREY('{_ifc_guid()}',#5,$,$,$,$,$,$,.ELEMENT.,$);")
    entities.append(f"#34=IFCRELAGGREGATES('{_ifc_guid()}',#5,$,$,#30,(#31));")
    entities.append(f"#35=IFCRELAGGREGATES('{_ifc_guid()}',#5,$,$,#31,(#32));")
    entities.append(f"#36=IFCRELAGGREGATES('{_ifc_guid()}',#5,$,$,#32,(#33));")
    entities.append(f"#37=IFCRELCONTAINEDINSPATIALSTRUCTURE('{_ifc_guid()}',#5,$,$,(#29),#33);")
    return 29  # 返回几何根实体 id


def export_box_ifc(path, length, width, height, cx, cy, cz):
    """导出长方体为 IFC2X3 文件"""
    entities = []
    _ifc_box_body(entities, cx, cy, cz, length, width, height)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(_ifc_header(os.path.basename(path)))
        for e in entities:
            f.write(e + '\n')
        f.write(_ifc_footer())


def export_cylinder_ifc(path, radius, height, cx, cy, cz):
    """导出圆柱体为 IFC2X3 文件（用 IfcCircleProfileDef + IfcExtrudedAreaSolid）"""
    entities = []
    entities.append("#1=IFCPERSON($,$,'AI',$,$,$,$,$);")
    entities.append("#2=IFCORGANIZATION($,'AI',$,$,$);")
    entities.append("#3=IFCPERSONANDORGANIZATION(#1,#2,$);")
    entities.append("#4=IFCAPPLICATION(#2,'1.0','AI','AI');")
    entities.append("#5=IFCOWNERHISTORY(#3,#4,$,.ADDED.,$,#3,#4,0);")
    entities.append("#6=IFCDIRECTION((1.,0.,0.));")
    entities.append("#7=IFCDIRECTION((0.,0.,1.));")
    entities.append("#8=IFCCARTESIANPOINT((0.,0.,0.));")
    entities.append("#9=IFCAXIS2PLACEMENT3D(#8,#7,#6);")
    entities.append("#10=IFCDIRECTION((0.,1.,0.));")
    entities.append("#11=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-5,#9,#10);")
    entities.append("#12=IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,#11,$,.MODEL_VIEW.,$);")
    entities.append(f"#13=IFCCARTESIANPOINT(({cx:.6f},{cy:.6f}));")
    entities.append("#14=IFCDIRECTION((1.,0.));")
    entities.append("#15=IFCDIRECTION((0.,1.));")
    entities.append("#16=IFCAXIS2PLACEMENT2D(#13,#14,#15);")
    entities.append(f"#17=IFCCIRCLEPROFILEDEF(.AREA.,$,#16,{radius:.6f});")
    entities.append(f"#18=IFCCARTESIANPOINT(({cx:.6f},{cy:.6f},{cz:.6f}));")
    entities.append("#19=IFCDIRECTION((0.,0.,1.));")
    entities.append("#20=IFCDIRECTION((1.,0.,0.));")
    entities.append("#21=IFCAXIS2PLACEMENT3D(#18,#19,#20);")
    entities.append("#22=IFCDIRECTION((0.,0.,1.));")
    entities.append(f"#23=IFCEXTRUDEDAREASOLID(#17,#21,#22,{height:.6f});")
    entities.append("#24=IFCSHAPEREPRESENTATION(#12,'Body','SweptSolid',(#23));")
    entities.append("#25=IFCPRODUCTDEFINITIONSHAPE($,$,(#24));")
    entities.append(f"#26=IFCCARTESIANPOINT(({cx:.6f},{cy:.6f},{cz:.6f}));")
    entities.append("#27=IFCAXIS2PLACEMENT3D(#26,$,$);")
    entities.append("#28=IFCLOCALPLACEMENT($,#27);")
    guid = _ifc_guid()
    entities.append(f"#29=IFCBUILDINGELEMENTPROXY('{guid}',#5,'Cylinder','Cylinder',$,#28,#25,$,.NOTDEFINED.);")
    entities.append(f"#30=IFCPROJECT('{_ifc_guid()}',#5,'AI Project',$,$,$,$,(#11),#11);")
    entities.append(f"#31=IFCSITE('{_ifc_guid()}',#5,$,$,$,$,$,$,.ELEMENT.,$,$,$,$,$);")
    entities.append(f"#32=IFCBUILDING('{_ifc_guid()}',#5,$,$,$,$,$,$,.ELEMENT.,$,$,$,$,$,$);")
    entities.append(f"#33=IFCBUILDINGSTOREY('{_ifc_guid()}',#5,$,$,$,$,$,$,.ELEMENT.,$);")
    entities.append(f"#34=IFCRELAGGREGATES('{_ifc_guid()}',#5,$,$,#30,(#31));")
    entities.append(f"#35=IFCRELAGGREGATES('{_ifc_guid()}',#5,$,$,#31,(#32));")
    entities.append(f"#36=IFCRELAGGREGATES('{_ifc_guid()}',#5,$,$,#32,(#33));")
    entities.append(f"#37=IFCRELCONTAINEDINSPATIALSTRUCTURE('{_ifc_guid()}',#5,$,$,(#29),#33);")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(_ifc_header(os.path.basename(path)))
        for e in entities:
            f.write(e + '\n')
        f.write(_ifc_footer())


# ============================================================
# 统一导出接口
# ============================================================

EXPORTERS = {
    'obj': {
        'cylinder': export_cylinder_obj,
        'box': export_box_obj,
        'cube': export_box_obj,
        'sphere': export_sphere_obj,
        'cone': export_cone_obj,
    },
    'ifc': {
        'cylinder': export_cylinder_ifc,
        'box': export_box_ifc,
        'cube': export_box_ifc,
        'sphere': export_box_ifc,   # 先用长方体占位，后续实现真正的球体 IFC
        'cone': export_box_ifc,     # 先用长方体占位，后续实现真正的圆锥 IFC
    }
}


def export_geometry(fmt, component_type, path, **params):
    """
    统一导出接口
    fmt: 'obj' 或 'ifc'
    component_type: 'cylinder'|'box'|'cube'|'sphere'|'cone'
    path: 输出文件路径
    params: 几何参数（半径、高度、尺寸、坐标等）
    """
    exporter = EXPORTERS.get(fmt, {}).get(component_type)
    if not exporter:
        raise ValueError(f"不支持的格式/类型: {fmt}/{component_type}")
    exporter(path, **params)
    return path
