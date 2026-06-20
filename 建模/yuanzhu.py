# -*- coding: utf-8 -*-
"""
yuanzhu.py V4 - 圆柱批量生成插件（最终完善版）
功能：根据路线数据和圆柱参数表，自动在三维曲线上生成圆柱

核心特性：
1. 自动关联场景中的三维曲线（无需手动框选）
2. 标高相对于三维曲线对应位置的高程计算
3. 正确处理横向偏移（水平面内垂直于路线）和纵向偏移（沿路线方向）

作者：BIMBase Python插件开发专家
版本：4.0
日期：2025
"""
from pyp3d import *
import os
import subprocess
import math
import openpyxl
import json

# ================= 配置常量 =================
# 数据文件路径 - 与quxian.py共享
DATA_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_data.json")

# 路线组件属性键名
ROUTE_PLAN_DATA_KEY = 'plan_data_json'
ROUTE_VERT_DATA_KEY = 'vert_data_json'
ROUTE_CURVE_POINTS_KEY = '曲线点数据'

# 圆柱Excel表头映射（支持多种可能的列名）
COLUMN_MAPPING = {
    'station': ['桩号', '桩号(m)', 'Station', 'station', '里程'],
    'offset_trans': ['横向偏移', '横向偏移(m)', '横偏', 'TransOffset', 'offset_trans'],
    'offset_long': ['纵向偏移', '纵向偏移(m)', '纵偏', 'LongOffset', 'offset_long'],
    'radius': ['半径', '半径(mm)', '半径(m)', 'Radius', 'radius', 'R'],
    'z_top': ['桩顶标高', '桩顶标高(m)', '顶标高', 'TopElevation', 'z_top'],
    'z_bottom': ['桩底标高', '桩底标高(m)', '底标高', 'BottomElevation', 'z_bottom'],
}


# ================= 1. 交互与文件读取模块 =================
def run_cylinder_ui():
    """
    弹出圆柱生成交互窗口
    
    Returns:
        str: 用户选择 - 'Generate'(自动生成), 'FromFile'(从文件读取), 'Cancel'(取消)
    """
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$form = New-Object System.Windows.Forms.Form; "
        "$form.Text = '圆柱批量生成终端 V4'; "
        "$form.Size = New-Object System.Drawing.Size(450, 320); "
        "$form.StartPosition = 'CenterScreen'; "
        "$form.TopMost = $true; "
        "$lblTitle = New-Object System.Windows.Forms.Label; "
        "$lblTitle.Text = '圆柱批量生成插件'; "
        "$lblTitle.Location = New-Object System.Drawing.Point(20, 15); "
        "$lblTitle.AutoSize = $true; "
        "$lblTitle.Font = New-Object System.Drawing.Font('微软雅黑', 14, [System.Drawing.FontStyle]::Bold); "
        "$lblTitle.ForeColor = [System.Drawing.Color]::DarkBlue; "
        "$form.Controls.Add($lblTitle); "
        "$lbl1 = New-Object System.Windows.Forms.Label; "
        "$lbl1.Text = '插件将自动关联场景中的三维曲线'; "
        "$lbl1.Location = New-Object System.Drawing.Point(20, 50); "
        "$lbl1.AutoSize = $true; "
        "$lbl1.Font = New-Object System.Drawing.Font('微软雅黑', 10, [System.Drawing.FontStyle]::Bold); "
        "$form.Controls.Add($lbl1); "
        "$lbl2 = New-Object System.Windows.Forms.Label; "
        "$lbl2.Text = '(标高将相对于曲线对应位置的高程计算)'; "
        "$lbl2.Location = New-Object System.Drawing.Point(20, 75); "
        "$lbl2.AutoSize = $true; "
        "$lbl2.Font = New-Object System.Drawing.Font('微软雅黑', 9); "
        "$lbl2.ForeColor = [System.Drawing.Color]::Gray; "
        "$form.Controls.Add($lbl2); "
        "$btnC = New-Object System.Windows.Forms.Button; "
        "$btnC.Text = '导入圆柱表并自动生成'; "
        "$btnC.Location = New-Object System.Drawing.Point(20, 110); "
        "$btnC.Size = New-Object System.Drawing.Size(400, 70); "
        "$btnC.BackColor = [System.Drawing.Color]::LightSkyBlue; "
        "$btnC.Font = New-Object System.Drawing.Font('微软雅黑', 12, [System.Drawing.FontStyle]::Bold); "
        "$btnC.Add_Click({$global:res='Generate'; $form.Close()}); "
        "$form.Controls.Add($btnC); "
        "$btnFile = New-Object System.Windows.Forms.Button; "
        "$btnFile.Text = '从文件读取路线数据'; "
        "$btnFile.Location = New-Object System.Drawing.Point(20, 190); "
        "$btnFile.Size = New-Object System.Drawing.Size(400, 40); "
        "$btnFile.BackColor = [System.Drawing.Color]::LightYellow; "
        "$btnFile.Font = New-Object System.Drawing.Font('微软雅黑', 10); "
        "$btnFile.Add_Click({$global:res='FromFile'; $form.Close()}); "
        "$form.Controls.Add($btnFile); "
        "$btnCancel = New-Object System.Windows.Forms.Button; "
        "$btnCancel.Text = '取消'; "
        "$btnCancel.Location = New-Object System.Drawing.Point(20, 240); "
        "$btnCancel.Size = New-Object System.Drawing.Size(400, 40); "
        "$btnCancel.BackColor = [System.Drawing.Color]::LightCoral; "
        "$btnCancel.Font = New-Object System.Drawing.Font('微软雅黑', 10); "
        "$btnCancel.Add_Click({$global:res='Cancel'; $form.Close()}); "
        "$form.Controls.Add($btnCancel); "
        "$form.ShowDialog() | Out-Null; "
        "Write-Host $global:res"
    )
    proc = subprocess.Popen(['powershell', '-Command', ps_cmd], 
                           stdout=subprocess.PIPE, shell=True, universal_newlines=True)
    stdout, _ = proc.communicate()
    return stdout.strip()


def select_excel_file():
    """
    弹出文件选择对话框，选择圆柱参数表
    
    Returns:
        str: 选择的Excel文件路径，取消则返回空字符串
    """
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$f = New-Object System.Windows.Forms.OpenFileDialog; "
        "$f.Filter = 'Excel文件 (*.xlsx)|*.xlsx'; "
        "$f.Title = '请选择圆柱设计参数表 (.xlsx)'; "
        "if($f.ShowDialog() -eq 'OK'){ Write-Host $f.FileName }"
    )
    proc = subprocess.Popen(['powershell', '-Command', ps_cmd], 
                           stdout=subprocess.PIPE, shell=True, universal_newlines=True)
    stdout, _ = proc.communicate()
    return stdout.strip()


def parse_station(station_str):
    """
    解析桩号字符串为数值（单位：米）
    
    支持的格式：
    - K0+30, K1+234.5, K10+000
    - 1000, 1234.5
    
    Args:
        station_str: 桩号字符串
        
    Returns:
        float: 桩号数值（米）
    """
    if station_str is None:
        return 0.0
    
    s = str(station_str).strip().upper().replace('K', '')
    
    if '+' in s:
        parts = s.split('+')
        try:
            return float(parts[0]) * 1000 + float(parts[1])
        except (ValueError, IndexError):
            return 0.0
    
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def find_column_index(headers, column_type):
    """
    根据列类型查找对应的列索引
    
    Args:
        headers: Excel表头列表
        column_type: 列类型（如 'station', 'radius' 等）
        
    Returns:
        int: 列索引，未找到返回-1
    """
    possible_names = COLUMN_MAPPING.get(column_type, [column_type])
    for name in possible_names:
        for i, header in enumerate(headers):
            if header and str(header).strip().lower() == name.lower():
                return i
    return -1


# ================= 2. 路线数学解析引擎 =================
class RouteMathEngine:
    """
    路线数学计算引擎
    
    根据平面数据和竖曲线数据，计算任意桩号的三维坐标和方向向量
    """
    
    def __init__(self, plan_data, vert_data):
        """
        初始化路线计算引擎
        
        Args:
            plan_data: 平面线形数据列表
            vert_data: 竖曲线数据列表
        """
        # 解析平面线形
        self.plan_segments = []
        curr_s = 0.0
        curr_ang = 0.0
        curr_x, curr_y = 0.0, 0.0
        
        for row in plan_data:
            seg_type = str(row.get('类型', '')).strip().upper()
            if not seg_type:
                continue
            
            length = float(row.get('长度', 0)) if row.get('长度') else 0.0
            radius = float(row.get('半径', 0)) if row.get('半径') else 0.0
            
            seg = {
                'start_s': curr_s,
                'end_s': curr_s + length,
                'type': seg_type,
                'L': length,
                'R': radius,
                'x0': curr_x,
                'y0': curr_y,
                'ang0': curr_ang
            }
            self.plan_segments.append(seg)
            
            # 计算线段终点坐标和方向
            if seg_type == 'Z':  # 直线
                curr_x += length * math.cos(curr_ang)
                curr_y += length * math.sin(curr_ang)
            elif seg_type == 'Y' and radius != 0:  # 圆曲线
                curr_ang += length / radius
                xc = curr_x - radius * math.sin(seg['ang0'])
                yc = curr_y + radius * math.cos(seg['ang0'])
                curr_x = xc + radius * math.sin(curr_ang)
                curr_y = yc - radius * math.cos(curr_ang)
            
            curr_s += length
        
        # 解析竖曲线数据
        self.pvi_list = []
        for row in vert_data:
            if '桩号' not in row:
                continue
            try:
                pvi = {
                    's': parse_station(row.get('桩号', '')),
                    'e': float(str(row.get('变坡点标高', '')).strip()),
                    'r': float(str(row.get('竖曲线半径', '')).strip()) if row.get('竖曲线半径') else 0.0
                }
                self.pvi_list.append(pvi)
            except (ValueError, TypeError):
                continue
        
        # 按桩号排序
        self.pvi_list.sort(key=lambda item: item['s'])
        
        # 计算各变坡点的坡度
        for i in range(len(self.pvi_list) - 1):
            p1, p2 = self.pvi_list[i], self.pvi_list[i + 1]
            slope = (p2['e'] - p1['e']) / (p2['s'] - p1['s']) if p2['s'] != p1['s'] else 0
            p1['slope_out'] = slope
            p2['slope_in'] = slope
        
        # 计算竖曲线起点和终点
        for i in range(1, len(self.pvi_list) - 1):
            p = self.pvi_list[i]
            r = p['r']
            if r > 0:
                g1, g2 = p['slope_in'], p['slope_out']
                L = r * abs(g2 - g1)
                T = L / 2
                p['bvc_s'] = p['s'] - T
                p['evc_s'] = p['s'] + T
                p['bvc_e'] = p['e'] - T * g1
            else:
                p['bvc_s'], p['evc_s'] = p['s'], p['s']
    
    def get_xyz(self, s):
        """
        根据桩号计算三维坐标
        
        Args:
            s: 桩号（米）
            
        Returns:
            tuple: (x, y, z) 三维坐标
        """
        # 计算平面坐标
        x, y = 0.0, 0.0
        for seg in self.plan_segments:
            if seg['start_s'] <= s <= seg['end_s'] + 1e-5:
                ds = s - seg['start_s']
                if seg['type'] == 'Z':  # 直线
                    x = seg['x0'] + ds * math.cos(seg['ang0'])
                    y = seg['y0'] + ds * math.sin(seg['ang0'])
                elif seg['type'] == 'Y' and seg['R'] != 0:  # 圆曲线
                    xc = seg['x0'] - seg['R'] * math.sin(seg['ang0'])
                    yc = seg['y0'] + seg['R'] * math.cos(seg['ang0'])
                    ang_s = seg['ang0'] + ds / seg['R']
                    x = xc + seg['R'] * math.sin(ang_s)
                    y = yc - seg['R'] * math.cos(ang_s)
                break
        
        # 计算高程
        z = 0.0
        if self.pvi_list:
            if s <= self.pvi_list[0]['s']:
                z = self.pvi_list[0]['e']
            elif s >= self.pvi_list[-1]['s']:
                z = self.pvi_list[-1]['e']
            else:
                for i in range(len(self.pvi_list) - 1):
                    p1, p2 = self.pvi_list[i], self.pvi_list[i + 1]
                    if p1['s'] <= s <= p2['s']:
                        # 检查是否在竖曲线范围内
                        if 'bvc_s' in p2 and p2['bvc_s'] < s < p2['evc_s']:
                            g1, g2 = p2['slope_in'], p2['slope_out']
                            L = p2['evc_s'] - p2['bvc_s']
                            dx = s - p2['bvc_s']
                            z = p2['bvc_e'] + g1 * dx + ((g2 - g1) / (2 * L)) * (dx ** 2)
                        elif 'bvc_s' in p1 and p1['bvc_s'] < s < p1['evc_s']:
                            g1, g2 = p1['slope_in'], p1['slope_out']
                            L = p1['evc_s'] - p1['bvc_s']
                            dx = s - p1['bvc_s']
                            z = p1['bvc_e'] + g1 * dx + ((g2 - g1) / (2 * L)) * (dx ** 2)
                        else:
                            z = p1['e'] + p1['slope_out'] * (s - p1['s'])
                        break
        
        return x, y, z
    
    def get_3d_frame(self, s):
        """
        获取当前桩号的3D点、切向向量、横向向量
        
        坐标系定义：
        - 切向向量T：沿路线前进方向（三维）
        - 横向向量N：水平面内垂直于路线投影的方向（nz=0）
        
        Args:
            s: 桩号（米）
            
        Returns:
            tuple: ((x, y, z), (tx, ty, tz), (nx, ny, nz))
                - (x, y, z): 桩号对应的三维点
                - (tx, ty, tz): 切向向量（单位向量）
                - (nx, ny, nz): 横向向量（单位向量，水平面内）
        """
        # 获取当前点和前方一点，计算切向向量
        x0, y0, z0 = self.get_xyz(s)
        x1, y1, z1 = self.get_xyz(s + 0.01)
        
        # 计算切向向量并归一化
        tx, ty, tz = x1 - x0, y1 - y0, z1 - z0
        length = math.sqrt(tx ** 2 + ty ** 2 + tz ** 2)
        if length > 1e-10:
            tx, ty, tz = tx / length, ty / length, tz / length
        else:
            tx, ty, tz = 1.0, 0.0, 0.0
        
        # 计算横向向量（水平面内垂直于路线投影）
        # 横向向量 = (-ty, tx, 0) 并归一化
        nx, ny, nz = -ty, tx, 0.0
        n_len = math.sqrt(nx ** 2 + ny ** 2)
        if n_len > 1e-10:
            nx, ny = nx / n_len, ny / n_len
        else:
            nx, ny = 0.0, 1.0
        
        return (x0, y0, z0), (tx, ty, tz), (nx, ny, nz)


# ================= 3. 圆柱组件定义 =================
class CylindersAssembly(Component):
    """
    圆柱群组件
    
    将多个圆柱组合成一个组件，便于管理和显示
    """
    
    def __init__(self, cylinders):
        """
        初始化圆柱群组件
        
        Args:
            cylinders: 圆柱几何体列表
        """
        Component.__init__(self)
        self.cylinders = cylinders
        self['圆柱群'] = Attr(None, show=True)
        self.replace()
    
    @export
    def replace(self):
        """生成圆柱几何体"""
        if self.cylinders:
            # 设置圆柱颜色为绿色，透明度为1（不透明）
            colored_cylinders = [c.color(0, 1, 0, 1) for c in self.cylinders]
            self['圆柱群'] = combine(*colored_cylinders)
        else:
            self['圆柱群'] = None


# ================= 4. 自动获取路线数据模块 =================
def find_route_component_in_scene():
    """
    自动在场景中寻找包含路线数据的组件
    
    Returns:
        tuple: (plan_data, vert_data) 或 None（未找到）
    """
    print("[圆柱插件] 正在自动查找场景中的路线组件...")
    
    try:
        # 获取场景中的所有实体
        # 使用框选工具，但不需要用户交互，直接获取所有实体
        entity_ids = get_all_entities()
        
        if not entity_ids:
            print("[圆柱插件] 场景中未找到任何实体")
            return None
        
        print(f"[圆柱插件] 场景中找到 {len(entity_ids)} 个实体")
        
        for i, entity_id in enumerate(entity_ids):
            try:
                # 验证实体ID有效性
                if not entityid_isvalid(entity_id):
                    continue
                
                # 获取实体属性
                attributes = get_entity_attributes(entity_id)
                
                if not attributes:
                    continue
                
                # 检查是否包含路线数据
                has_plan = ROUTE_PLAN_DATA_KEY in attributes
                has_vert = ROUTE_VERT_DATA_KEY in attributes
                
                if has_plan and has_vert:
                    print(f"[圆柱插件] ✓ 找到包含路线数据的组件（实体 {i+1}）")
                    
                    try:
                        plan_data = json.loads(attributes[ROUTE_PLAN_DATA_KEY])
                        vert_data = json.loads(attributes[ROUTE_VERT_DATA_KEY])
                        print(f"[圆柱插件] 成功解析路线数据")
                        print(f"  - 平面数据: {len(plan_data)} 条记录")
                        print(f"  - 竖曲线数据: {len(vert_data)} 条记录")
                        return plan_data, vert_data
                    except Exception as e:
                        print(f"[圆柱插件] 解析JSON数据失败: {e}")
                        continue
                        
            except Exception as e:
                continue
        
        print("[圆柱插件] 未找到包含路线数据的组件")
        return None
        
    except Exception as e:
        print(f"[圆柱插件] 查找路线组件时出错: {e}")
        return None


def get_all_entities():
    """
    获取场景中的所有实体
    
    Returns:
        list: 实体ID列表
    """
    try:
        # 尝试使用get_element_from_boxselect获取所有实体
        # 或者使用其他BIMBase API获取所有实体
        entity_ids = get_element_from_boxselect()
        if not entity_ids:
            return []
        if not isinstance(entity_ids, (list, tuple)):
            entity_ids = [entity_ids]
        return entity_ids
    except:
        return []


def get_entity_attributes(entity_id):
    """
    获取实体的所有属性
    
    Args:
        entity_id: 实体ID
        
    Returns:
        dict: 属性字典
    """
    attributes = {}
    
    try:
        datakey = get_datakey_from_entity(entity_id)
        if datakey is None:
            return attributes
        
        try:
            noumenon = get_noumKV_from_instancekey(datakey)
        except:
            return attributes
        
        if noumenon is None:
            return attributes
        
        # 提取属性
        if isinstance(noumenon, dict):
            attributes = dict(noumenon)
        elif hasattr(noumenon, 'keys'):
            for key in noumenon.keys():
                try:
                    attributes[key] = noumenon[key]
                except:
                    pass
        elif hasattr(noumenon, '__iter__') and hasattr(noumenon, '__getitem__'):
            try:
                for key in noumenon:
                    try:
                        attributes[key] = noumenon[key]
                    except:
                        pass
            except:
                pass
        else:
            for attr_name in dir(noumenon):
                if not attr_name.startswith('_'):
                    try:
                        val = getattr(noumenon, attr_name)
                        if not callable(val):
                            attributes[attr_name] = val
                    except:
                        pass
    except:
        pass
    
    return attributes


def get_route_data_from_file():
    """
    从JSON文件获取路线数据
    
    Returns:
        tuple: (plan_data, vert_data) 或 None（未找到或失败）
    """
    print("=" * 60)
    print("[圆柱插件] 尝试从文件读取路线数据...")
    print(f"[圆柱插件] 文件路径: {DATA_FILE_PATH}")
    print("=" * 60)
    
    try:
        if not os.path.exists(DATA_FILE_PATH):
            print(f"[圆柱插件] 数据文件不存在: {DATA_FILE_PATH}")
            return None
        
        with open(DATA_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        plan_data = data.get('plan_data')
        vert_data = data.get('vert_data')
        
        if plan_data and vert_data:
            print(f"[圆柱插件] 成功从文件读取路线数据")
            print(f"  - 平面数据: {len(plan_data)} 条记录")
            print(f"  - 竖曲线数据: {len(vert_data)} 条记录")
            return plan_data, vert_data
        else:
            print(f"[圆柱插件] 文件数据不完整")
            return None
    
    except Exception as e:
        print(f"[圆柱插件] 从文件读取数据失败: {e}")
        return None


# ================= 5. Excel数据读取模块 =================
def read_cylinder_excel(file_path):
    """
    读取圆柱参数Excel文件
    
    Args:
        file_path: Excel文件路径
        
    Returns:
        list: 圆柱参数字典列表
    """
    cylinders_params = []
    
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active
        
        # 读取表头
        headers = [str(cell.value).strip() if cell.value is not None else "" for cell in ws[1]]
        print(f"[圆柱插件] Excel表头: {headers}")
        
        # 查找各列索引
        col_indices = {
            'station': find_column_index(headers, 'station'),
            'offset_trans': find_column_index(headers, 'offset_trans'),
            'offset_long': find_column_index(headers, 'offset_long'),
            'radius': find_column_index(headers, 'radius'),
            'z_top': find_column_index(headers, 'z_top'),
            'z_bottom': find_column_index(headers, 'z_bottom'),
        }
        
        print(f"[圆柱插件] 列索引映射: {col_indices}")
        
        # 检查必需列
        required_cols = ['station', 'radius', 'z_top', 'z_bottom']
        missing_cols = [col for col in required_cols if col_indices[col] == -1]
        if missing_cols:
            print(f"[圆柱插件] 警告：缺少必需列: {missing_cols}")
            print(f"[圆柱插件] 将尝试使用默认列顺序")
            # 使用默认列顺序
            col_indices = {
                'station': 1,  # 第2列（B列）
                'offset_trans': 2,  # 第3列（C列）
                'offset_long': 3,  # 第4列（D列）
                'radius': 4,  # 第5列（E列）
                'z_top': 5,  # 第6列（F列）
                'z_bottom': 6,  # 第7列（G列）
            }
        
        # 读取数据行
        row_count = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            
            row_count += 1
            
            try:
                # 提取参数
                station = parse_station(row[col_indices['station']]) if col_indices['station'] >= 0 else 0.0
                offset_trans = float(row[col_indices['offset_trans']]) if col_indices['offset_trans'] >= 0 and row[col_indices['offset_trans']] is not None else 0.0
                offset_long = float(row[col_indices['offset_long']]) if col_indices['offset_long'] >= 0 and row[col_indices['offset_long']] is not None else 0.0
                radius = float(row[col_indices['radius']]) if col_indices['radius'] >= 0 and row[col_indices['radius']] is not None else 1.0
                z_top = float(row[col_indices['z_top']]) if col_indices['z_top'] >= 0 and row[col_indices['z_top']] is not None else 0.0
                z_bottom = float(row[col_indices['z_bottom']]) if col_indices['z_bottom'] >= 0 and row[col_indices['z_bottom']] is not None else 0.0
                
                # 半径单位转换（如果Excel中是毫米，转换为米）
                if radius > 10:  # 假设大于10的是毫米单位
                    radius = radius / 1000.0
                
                cylinders_params.append({
                    'station': station,
                    'offset_trans': offset_trans,
                    'offset_long': offset_long,
                    'radius': radius,
                    'z_top': z_top,
                    'z_bottom': z_bottom,
                })
            
            except Exception as e:
                print(f"[圆柱插件] 读取第 {row_count} 行时出错: {e}")
                continue
        
        print(f"[圆柱插件] 成功读取 {len(cylinders_params)} 个圆柱参数")
        return cylinders_params
    
    except Exception as e:
        print(f"[圆柱插件] 读取Excel文件失败: {e}")
        return []


# ================= 6. 圆柱生成模块（核心修正） =================
def create_cylinder_at_station(engine, params):
    """
    在指定桩号位置创建圆柱（标高相对于路线高程）
    
    偏移逻辑：
    1. 根据桩号找到三维曲线上的基准点P
    2. 计算该点的切向向量T（沿路线方向）
    3. 计算横向向量N（水平面内垂直于路线投影）
    4. 最终XY位置 = P.xy + T.xy * 纵向偏移 + N * 横向偏移
    5. 最终Z位置 = P.z + 标高偏移（相对于路线高程）
    
    Args:
        engine: RouteMathEngine实例
        params: 圆柱参数字典
        
    Returns:
        Cone: 圆柱几何体，失败返回None
    """
    try:
        s = params['station']
        offset_trans = params['offset_trans']
        offset_long = params['offset_long']
        radius = params['radius']
        z_top_offset = params['z_top']  # 相对于路线高程的顶部偏移
        z_bottom_offset = params['z_bottom']  # 相对于路线高程的底部偏移
        
        # 获取桩号对应的三维坐标和方向向量
        (px, py, pz), (tx, ty, tz), (nx, ny, nz) = engine.get_3d_frame(s)
        
        # 计算偏移后的XY位置
        # 横向偏移：沿水平法向N
        # 纵向偏移：沿切向T的XY投影方向
        final_x = px + nx * offset_trans + tx * offset_long
        final_y = py + ny * offset_trans + ty * offset_long
        
        # 计算相对于路线高程的Z坐标
        # 路线在桩号处的高程为 pz
        # 圆柱顶部标高 = 路线高程 + 桩顶标高偏移
        # 圆柱底部标高 = 路线高程 + 桩底标高偏移
        final_z_top = pz + z_top_offset
        final_z_bottom = pz + z_bottom_offset
        
        print(f"  路线高程: {pz:.3f}m, 顶部偏移: {z_top_offset:.3f}m, 底部偏移: {z_bottom_offset:.3f}m")
        print(f"  实际顶部标高: {final_z_top:.3f}m, 实际底部标高: {final_z_bottom:.3f}m")
        
        # 创建圆柱（使用Cone创建圆柱体，顶部和底部半径相同）
        cylinder = Cone(
            Vec3(final_x, final_y, final_z_bottom),
            Vec3(final_x, final_y, final_z_top),
            radius,
            radius
        )
        
        return cylinder
    
    except Exception as e:
        print(f"[圆柱插件] 创建圆柱时出错: {e}")
        import traceback
        traceback.print_exc()
        return None


# ================= 7. 主执行逻辑 =================
def generate_cylinders():
    """
    主函数：生成圆柱
    
    执行流程：
    1. 显示交互UI，获取用户选择
    2. 自动获取路线数据（从场景中的组件或文件）
    3. 初始化路线计算引擎
    4. 读取圆柱参数Excel文件
    5. 根据参数生成圆柱（标高相对于路线高程）
    6. 布置圆柱到场景
    """
    print("\n" + "=" * 60)
    print("[圆柱插件] 启动圆柱批量生成程序 V4")
    print("[圆柱插件] 标高将相对于三维曲线对应位置的高程计算")
    print("=" * 60)
    
    # 启动交互UI
    choice = run_cylinder_ui()
    print(f"[圆柱插件] UI返回: {choice}")
    
    if choice == 'Cancel':
        print("[圆柱插件] 用户取消操作")
        return
    
    # 获取路线数据
    route_data = None
    
    if choice == 'FromFile':
        # 从文件读取
        route_data = get_route_data_from_file()
    elif choice == 'Generate':
        # 自动从场景获取
        route_data = find_route_component_in_scene()
        
        # 如果自动获取失败，尝试从文件读取
        if route_data is None:
            print("\n[圆柱插件] 自动查找失败，尝试从文件读取...")
            route_data = get_route_data_from_file()
    
    if route_data is None:
        print("\n" + "=" * 60)
        print("[圆柱插件] 错误：无法获取路线数据！")
        print("=" * 60)
        print("请确保：")
        print("  1. 已使用 quxian.py 生成路线模型")
        print("  2. 路线模型存在于当前场景中")
        print("  3. 路线数据文件存在: route_data.json")
        return
    
    plan_data, vert_data = route_data
    
    # 创建路线计算引擎
    print("\n" + "=" * 60)
    print("[圆柱插件] 初始化路线计算引擎...")
    print("=" * 60)
    try:
        engine = RouteMathEngine(plan_data, vert_data)
        print("[圆柱插件] 路线计算引擎初始化成功")
    except Exception as e:
        print(f"[圆柱插件] 路线计算引擎初始化失败: {e}")
        return
    
    # 导入圆柱Excel
    print("\n[圆柱插件] 请选择圆柱参数表...")
    file_path = select_excel_file()
    print(f"[圆柱插件] 选择的文件: {file_path}")
    
    if not file_path or not os.path.exists(file_path):
        print("[圆柱插件] 未选择文件或文件不存在")
        return
    
    print(f"[圆柱插件] 已选择文件: {file_path}")
    
    # 读取圆柱参数
    cylinder_params_list = read_cylinder_excel(file_path)
    
    if not cylinder_params_list:
        print("[圆柱插件] 未读取到任何圆柱参数")
        return
    
    # 生成圆柱
    cylinders = []
    success_count = 0
    fail_count = 0
    
    print("\n" + "=" * 60)
    print("[圆柱插件] 开始生成圆柱（标高相对于路线高程）...")
    print("=" * 60)
    
    for i, params in enumerate(cylinder_params_list):
        print(f"\n[圆柱插件] 处理第 {i + 1}/{len(cylinder_params_list)} 个圆柱:")
        print(f"  桩号: K{params['station'] / 1000:.3f}+{params['station'] % 1000:.3f}")
        print(f"  横向偏移: {params['offset_trans']:.2f}m, 纵向偏移: {params['offset_long']:.2f}m")
        print(f"  半径: {params['radius']:.3f}m")
        print(f"  桩顶标高偏移: {params['z_top']:.2f}m, 桩底标高偏移: {params['z_bottom']:.2f}m")
        
        cylinder = create_cylinder_at_station(engine, params)
        
        if cylinder:
            cylinders.append(cylinder.color(0, 1, 0, 1))
            success_count += 1
            print(f"  ✓ 圆柱生成成功")
        else:
            fail_count += 1
            print(f"  ✗ 圆柱生成失败")
    
    # 布置圆柱到场景
    if cylinders:
        print(f"\n" + "=" * 60)
        print(f"[圆柱插件] 成功生成 {success_count} 个圆柱，正在布置到场景...")
        if fail_count > 0:
            print(f"[圆柱插件] 失败: {fail_count} 个")
        print("=" * 60)
        
        try:
            place(CylindersAssembly(cylinders))
            print(f"[圆柱插件] 圆柱布置完成！")
        except Exception as e:
            print(f"[圆柱插件] 布置圆柱时出错: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("\n[圆柱插件] 警告：未生成任何圆柱")


# ================= 8. 入口点 =================
if __name__ == "__main__":
    generate_cylinders()
