# -*- coding: utf-8 -*-
"""
quxian.py V4 - 路线生成插件（最终完善版）

功能说明：
    本插件用于从Excel文件读取平面要素表和竖直要素表，
    生成三维空间曲线模型，并保存路线数据供圆柱插件使用。

数据流向：
    1. 读取Excel文件（平面要素表、竖直要素表）
    2. 解析路线数据（平面线形 + 竖曲线）
    3. 生成三维空间曲线模型
    4. 保存数据到：
       - 组件属性（plan_data_json, vert_data_json, 曲线点数据）
       - 外部JSON文件（route_data.json）

与圆柱插件的交互：
    - 圆柱插件可以自动从场景中获取路线数据
    - 数据通过组件属性或JSON文件共享
    - 圆柱标高相对于路线高程计算

作者：BIMBase Python插件开发团队
版本：4.0
日期：2025
"""

from pyp3d import *
import os
import subprocess
import math
import openpyxl
import json
from datetime import datetime

# ============================================================================
# 全局配置
# ============================================================================

# 调试模式开关
DEBUG_MODE = True

# 数据文件路径 - 用于与圆柱插件共享数据
# 支持从环境变量覆盖，默认为插件目录下的route_data.json
DATA_FILE_PATH = os.environ.get(
    'ROUTE_DATA_FILE',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_data.json")
)

# 默认采样步长（米）
DEFAULT_SAMPLE_STEP = 0.5

# 最小采样步长限制
MIN_SAMPLE_STEP = 0.1

# 最大采样步长限制
MAX_SAMPLE_STEP = 10.0


def log_message(msg, level="INFO"):
    """
    统一的日志输出函数
    
    参数:
        msg: 日志消息
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
    """
    if level == "DEBUG" and not DEBUG_MODE:
        return
    prefix = f"[曲线插件][{level}]"
    print(f"{prefix} {msg}")


# ============================================================================
# 数据持久化模块
# ============================================================================

def save_route_data_to_file(plan_data, vert_data, metadata=None):
    """
    将路线数据保存到JSON文件
    
    参数:
        plan_data: 平面要素数据列表
        vert_data: 竖直要素数据列表
        metadata: 可选的元数据字典
        
    返回:
        bool: 保存是否成功
    """
    try:
        # 构建数据字典
        data = {
            'version': '4.0',
            'created_at': datetime.now().isoformat(),
            'plan_data': plan_data,
            'vert_data': vert_data,
            'metadata': metadata or {}
        }
        
        # 确保目录存在
        dir_path = os.path.dirname(DATA_FILE_PATH)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            log_message(f"创建目录: {dir_path}")
        
        # 写入JSON文件
        with open(DATA_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        log_message(f"路线数据已保存到: {DATA_FILE_PATH}")
        log_message(f"  - 平面数据: {len(plan_data)} 条记录")
        log_message(f"  - 竖曲线数据: {len(vert_data)} 条记录")
        return True
        
    except PermissionError as e:
        log_message(f"保存数据失败 - 权限错误: {e}", "ERROR")
        return False
    except Exception as e:
        log_message(f"保存数据到文件失败: {e}", "ERROR")
        return False


def load_route_data_from_file():
    """
    从JSON文件加载路线数据
    
    返回:
        tuple: (plan_data, vert_data, metadata) 或 (None, None, None)
    """
    try:
        if not os.path.exists(DATA_FILE_PATH):
            log_message(f"数据文件不存在: {DATA_FILE_PATH}", "WARNING")
            return None, None, None
        
        with open(DATA_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        plan_data = data.get('plan_data')
        vert_data = data.get('vert_data')
        metadata = data.get('metadata', {})
        
        log_message(f"从文件加载数据成功")
        log_message(f"  - 平面数据: {len(plan_data) if plan_data else 0} 条记录")
        log_message(f"  - 竖曲线数据: {len(vert_data) if vert_data else 0} 条记录")
        
        return plan_data, vert_data, metadata
        
    except json.JSONDecodeError as e:
        log_message(f"JSON解析错误: {e}", "ERROR")
        return None, None, None
    except Exception as e:
        log_message(f"从文件加载数据失败: {e}", "ERROR")
        return None, None, None


def validate_route_data(plan_data, vert_data):
    """
    验证路线数据的完整性和有效性
    
    参数:
        plan_data: 平面要素数据
        vert_data: 竖直要素数据
        
    返回:
        tuple: (是否有效, 错误信息列表)
    """
    errors = []
    
    # 验证平面数据
    if not plan_data:
        errors.append("平面数据为空")
    else:
        for i, row in enumerate(plan_data):
            row_num = i + 1
            if '类型' not in row:
                errors.append(f"平面数据第{row_num}行缺少'类型'字段")
            elif str(row.get('类型', '')).strip().upper() not in ['Z', 'Y']:
                errors.append(f"平面数据第{row_num}行类型必须是'Z'或'Y'")
            
            if '长度' not in row or row.get('长度') is None:
                errors.append(f"平面数据第{row_num}行缺少'长度'字段")
            else:
                try:
                    length = float(row.get('长度', 0))
                    if length <= 0:
                        errors.append(f"平面数据第{row_num}行长度必须大于0")
                except (ValueError, TypeError):
                    errors.append(f"平面数据第{row_num}行长度格式无效")
    
    # 验证竖直数据
    if not vert_data:
        errors.append("竖直数据为空")
    else:
        for i, row in enumerate(vert_data):
            row_num = i + 1
            if '桩号' not in row:
                errors.append(f"竖直数据第{row_num}行缺少'桩号'字段")
            if '变坡点标高' not in row:
                errors.append(f"竖直数据第{row_num}行缺少'变坡点标高'字段")
    
    return len(errors) == 0, errors


# ============================================================================
# 组件属性操作模块
# ============================================================================

def get_component_attributes(entity_id):
    """
    获取Component的属性（增强版）
    
    支持多种获取方式，提高兼容性
    
    参数:
        entity_id: 实体ID或Component对象
        
    返回:
        dict: 属性字典
    """
    attributes = {}
    
    try:
        # 方式1：如果entity_id本身就是Component对象
        if hasattr(entity_id, 'keys') and callable(getattr(entity_id, 'keys', None)):
            log_message("使用Component对象直接获取属性", "DEBUG")
            for key in entity_id.keys():
                try:
                    val = entity_id[key]
                    # 如果值是Attr对象，获取其实际值
                    if hasattr(val, 'value'):
                        attributes[key] = val.value
                    else:
                        attributes[key] = val
                except Exception as e:
                    log_message(f"获取属性'{key}'时出错: {e}", "DEBUG")
            return attributes
        
        # 方式2：通过datakey获取
        try:
            datakey = get_datakey_from_entity(entity_id)
            if datakey is None:
                log_message("无法获取datakey", "DEBUG")
                return attributes
            
            noumenon = get_noumKV_from_instancekey(datakey)
            if noumenon is not None:
                if isinstance(noumenon, dict):
                    attributes = dict(noumenon)
                elif hasattr(noumenon, 'keys'):
                    for key in noumenon.keys():
                        try:
                            val = noumenon[key]
                            if hasattr(val, 'value'):
                                attributes[key] = val.value
                            else:
                                attributes[key] = val
                        except Exception as e:
                            log_message(f"获取本体属性'{key}'时出错: {e}", "DEBUG")
        except Exception as e:
            log_message(f"通过datakey获取属性失败: {e}", "DEBUG")
            
    except Exception as e:
        log_message(f"获取属性时出错: {e}", "ERROR")
    
    return attributes


def get_route_data_from_selection():
    """
    从选中的组件获取路线数据（供圆柱插件调用）
    
    使用流程：
        1. 调用此函数启动框选工具
        2. 在视口中框选路线模型
        3. 函数自动查找包含路线数据的组件
        4. 返回解析后的路线数据
    
    返回:
        tuple: (plan_data, vert_data) 或 (None, None)
    """
    log_message("=" * 60)
    log_message("启动框选工具，请在视口中框选路线模型...")
    log_message("=" * 60)
    
    try:
        entity_ids = get_element_from_boxselect()
    except Exception as e:
        log_message(f"框选工具调用失败: {e}", "ERROR")
        entity_ids = None
    
    if not entity_ids:
        log_message("未选中任何实体", "WARNING")
        return None, None
    
    if not isinstance(entity_ids, (list, tuple)):
        entity_ids = [entity_ids]
    
    log_message(f"选中 {len(entity_ids)} 个实体")
    
    for i, entity_id in enumerate(entity_ids):
        log_message(f"检查第 {i+1} 个实体...")
        
        try:
            # 验证实体ID有效性
            if not entityid_isvalid(entity_id):
                log_message(f"实体ID无效，跳过", "DEBUG")
                continue
        except Exception as e:
            log_message(f"验证实体ID时出错: {e}", "DEBUG")
            continue
        
        log_message(f"实体ID有效，尝试获取属性...", "DEBUG")
        
        # 获取组件属性
        attributes = get_component_attributes(entity_id)
        
        if not attributes:
            log_message(f"无法获取实体属性", "DEBUG")
            continue
        
        log_message(f"获取到 {len(attributes)} 个属性", "DEBUG")
        log_message(f"属性键: {list(attributes.keys())}", "DEBUG")
        
        # 检查是否包含路线数据
        has_plan = 'plan_data_json' in attributes
        has_vert = 'vert_data_json' in attributes
        
        log_message(f"包含plan_data_json: {has_plan}", "DEBUG")
        log_message(f"包含vert_data_json: {has_vert}", "DEBUG")
        
        if has_plan and has_vert:
            log_message(f"✓ 找到包含路线数据的组件!")
            
            try:
                plan_data = json.loads(attributes['plan_data_json'])
                vert_data = json.loads(attributes['vert_data_json'])
                log_message(f"成功解析路线数据")
                log_message(f"  - 平面数据: {len(plan_data)} 条记录")
                log_message(f"  - 竖曲线数据: {len(vert_data)} 条记录")
                return plan_data, vert_data
            except json.JSONDecodeError as e:
                log_message(f"解析JSON数据失败: {e}", "ERROR")
                continue
            except Exception as e:
                log_message(f"处理路线数据时出错: {e}", "ERROR")
                continue
        else:
            log_message(f"该实体不包含路线数据，跳过", "DEBUG")
    
    log_message("未找到包含路线数据的组件", "WARNING")
    return None, None


# ============================================================================
# UI交互模块
# ============================================================================

def select_main_action(plan_added, vert_added):
    """
    显示主操作选择对话框
    
    参数:
        plan_added: 是否已添加平面要素表
        vert_added: 是否已添加竖直要素表
        
    返回:
        str: 用户选择 ('Planar', 'Vertical', 'Confirm', 或其他)
    """
    plan_status = "已添加" if plan_added else "未添加"
    vert_status = "已添加" if vert_added else "未添加"
    
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$form = New-Object System.Windows.Forms.Form; "
        "$form.Text = '要素表批量导入终端 V4'; "
        "$form.Size = New-Object System.Drawing.Size(400,280); "
        "$form.StartPosition = 'CenterScreen'; "
        "$form.TopMost = $true; "
        "$lbl1 = New-Object System.Windows.Forms.Label; "
        "$lbl1.Text = '平面要素表： " + plan_status + "'; "
        "$lbl1.Location = New-Object System.Drawing.Point(20,15); "
        "$lbl1.AutoSize = $true; "
        "$lbl1.Font = New-Object System.Drawing.Font('Microsoft Sans Serif', 10, [System.Drawing.FontStyle]::Bold); "
        "$form.Controls.Add($lbl1); "
        "$lbl2 = New-Object System.Windows.Forms.Label; "
        "$lbl2.Text = '竖直要素表： " + vert_status + "'; "
        "$lbl2.Location = New-Object System.Drawing.Point(200,15); "
        "$lbl2.AutoSize = $true; "
        "$lbl2.Font = New-Object System.Drawing.Font('Microsoft Sans Serif', 10, [System.Drawing.FontStyle]::Bold); "
        "$form.Controls.Add($lbl2); "
        "$btnP = New-Object System.Windows.Forms.Button; "
        "$btnP.Text = '添加平面要素表'; "
        "$btnP.Location = New-Object System.Drawing.Point(20,50); "
        "$btnP.Size = New-Object System.Drawing.Size(160,45); "
        "$btnP.Add_Click({$global:res='Planar'; $form.Close()}); "
        "$form.Controls.Add($btnP); "
        "$btnV = New-Object System.Windows.Forms.Button; "
        "$btnV.Text = '添加竖直要素表'; "
        "$btnV.Location = New-Object System.Drawing.Point(200,50); "
        "$btnV.Size = New-Object System.Drawing.Size(160,45); "
        "$btnV.Add_Click({$global:res='Vertical'; $form.Close()}); "
        "$form.Controls.Add($btnV); "
        "$btnC = New-Object System.Windows.Forms.Button; "
        "$btnC.Text = '确定并生成 3D 组合模型'; "
        "$btnC.Location = New-Object System.Drawing.Point(20,110); "
        "$btnC.Size = New-Object System.Drawing.Size(340,60); "
        "$btnC.BackColor = [System.Drawing.Color]::LightGreen; "
        "$btnC.Font = New-Object System.Drawing.Font('Microsoft Sans Serif', 12, [System.Drawing.FontStyle]::Bold); "
        "$btnC.Add_Click({$global:res='Confirm'; $form.Close()}); "
        "$form.Controls.Add($btnC); "
        "$btnCancel = New-Object System.Windows.Forms.Button; "
        "$btnCancel.Text = '取消'; "
        "$btnCancel.Location = New-Object System.Drawing.Point(20,180); "
        "$btnCancel.Size = New-Object System.Drawing.Size(340,35); "
        "$btnCancel.Add_Click({$global:res='Cancel'; $form.Close()}); "
        "$form.Controls.Add($btnCancel); "
        "$form.ShowDialog() | Out-Null; "
        "Write-Host $global:res"
    )
    
    try:
        proc = subprocess.Popen(
            ['powershell', '-Command', ps_cmd],
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True
        )
        stdout, _ = proc.communicate()
        return stdout.strip()
    except Exception as e:
        log_message(f"显示对话框失败: {e}", "ERROR")
        return ""


def select_excel_file(title):
    """
    显示Excel文件选择对话框
    
    参数:
        title: 对话框标题
        
    返回:
        str: 选中的文件路径，或空字符串
    """
    # 默认路径：插件目录下的Sample文件夹
    default_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Sample"
    )
    
    # 如果默认路径不存在，使用桌面
    if not os.path.exists(default_path):
        default_path = os.path.expanduser("~\\Desktop")
    
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$f = New-Object System.Windows.Forms.OpenFileDialog; "
        "$f.Filter = 'Excel文件 (*.xlsx)|*.xlsx'; "
        "$f.InitialDirectory = '" + default_path.replace("\\", "\\\\") + "'; "
        "$f.Title = '" + title + "'; "
        "if($f.ShowDialog() -eq 'OK'){ Write-Host $f.FileName }"
    )
    
    try:
        proc = subprocess.Popen(
            ['powershell', '-Command', ps_cmd],
            stdout=subprocess.PIPE,
            shell=True,
            universal_newlines=True
        )
        stdout, _ = proc.communicate()
        return stdout.strip()
    except Exception as e:
        log_message(f"显示文件对话框失败: {e}", "ERROR")
        return ""


# ============================================================================
# 数据解析工具函数
# ============================================================================

def parse_station(station_str):
    """
    解析桩号字符串为数值
    
    支持的格式：
        - "K0+100" -> 100.0
        - "K1+500" -> 1500.0
        - "100" -> 100.0
        - "100.5" -> 100.5
    
    参数:
        station_str: 桩号字符串
        
    返回:
        float: 桩号数值（米）
    """
    if station_str is None:
        return 0.0
    
    try:
        s = str(station_str).strip().upper().replace('K', '').replace(' ', '')
        
        if '+' in s:
            parts = s.split('+')
            if len(parts) == 2:
                try:
                    km = float(parts[0]) if parts[0] else 0
                    m = float(parts[1]) if parts[1] else 0
                    return km * 1000 + m
                except ValueError:
                    return 0.0
        
        return float(s) if s else 0.0
        
    except (ValueError, TypeError):
        log_message(f"无法解析桩号: {station_str}", "WARNING")
        return 0.0


def format_station(station_value):
    """
    将桩号数值格式化为字符串
    
    参数:
        station_value: 桩号数值（米）
        
    返回:
        str: 格式化后的桩号字符串，如 "K0+100"
    """
    km = int(station_value // 1000)
    m = station_value % 1000
    return f"K{km}+{m:03.0f}"


def read_excel_data(file_path):
    """
    读取Excel文件数据
    
    参数:
        file_path: Excel文件路径
        
    返回:
        list: 数据字典列表，每个字典代表一行数据
        
    异常:
        读取失败时抛出异常
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    
    # 读取表头
    headers = []
    for cell in ws[1]:
        if cell.value is not None:
            headers.append(str(cell.value).strip())
        else:
            headers.append("")
    
    log_message(f"读取到 {len(headers)} 列: {headers}", "DEBUG")
    
    # 读取数据行
    data = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        # 跳过空行
        if not any(row):
            continue
        
        # 构建字典
        row_dict = {}
        for i, (header, value) in enumerate(zip(headers, row)):
            if header:  # 只保存有表头的列
                row_dict[header] = value
        
        data.append(row_dict)
    
    log_message(f"读取到 {len(data)} 行数据")
    return data


# ============================================================================
# 核心建模类
# ============================================================================

class CombinedRouteModel(Component):
    """
    组合路线模型组件
    
    功能：
        1. 解析平面要素数据，构建平面线形
        2. 解析竖直要素数据，构建竖曲线
        3. 生成三维空间曲线
        4. 保存数据供圆柱插件使用（包括曲线点数据）
    
    属性：
        plan_data: 平面要素数据列表
        vert_data: 竖直要素数据列表
        sample_step: 采样步长（米）
        curve_points: 曲线点列表（供外部查询）
    """
    
    def __init__(self, plan_data, vert_data, sample_step=DEFAULT_SAMPLE_STEP):
        """
        初始化路线模型
        
        参数:
            plan_data: 平面要素数据列表
            vert_data: 竖直要素数据列表
            sample_step: 采样步长（米），默认0.5
        """
        Component.__init__(self)
        
        # 保存原始数据
        self.plan_data = plan_data
        self.vert_data = vert_data
        self.sample_step = max(MIN_SAMPLE_STEP, min(MAX_SAMPLE_STEP, sample_step))
        
        # 初始化属性
        self['模型'] = Attr(None, show=True)
        self['曲线点数据'] = Attr(None, show=False)  # 存储采样点供圆柱插件使用
        self['路线长度'] = Attr(0.0, show=True)
        self['采样步长'] = Attr(self.sample_step, show=True)
        
        # 将数据持久化到组件属性
        self['plan_data_json'] = Attr(json.dumps(plan_data), show=False)
        self['vert_data_json'] = Attr(json.dumps(vert_data), show=False)
        
        # 存储解析后的几何数据（供外部查询）
        self.plan_segments = []
        self.pvi_list = []
        self.curve_points = []
        self.max_plan_s = 0.0
        
        # 保存到外部文件
        metadata = {
            'sample_step': self.sample_step,
            'created_by': 'quxian.py V4'
        }
        save_route_data_to_file(plan_data, vert_data, metadata)
        
        # 生成模型
        self.replace()
    
    @export
    def replace(self):
        """
        重新生成三维空间曲线模型
        
        流程：
            1. 解析平面数据
            2. 解析竖直数据
            3. 采样生成三维点
            4. 构建线段模型
        """
        log_message("开始生成三维空间曲线...")
        
        # A. 解析平面数据
        self._parse_plan_data()
        
        # B. 解析竖直数据
        self._parse_vert_data()
        
        # C. 采样生成三维曲线
        self._generate_3d_curve()
        
        log_message("三维空间曲线生成完成")
    
    def _parse_plan_data(self):
        """
        解析平面要素数据
        
        构建平面线形段列表，包括：
            - Z（直线段）
            - Y（圆曲线段）
        """
        self.plan_segments = []
        curr_s = 0.0      # 当前桩号
        curr_ang = 0.0    # 当前方位角（弧度）
        curr_x, curr_y = 0.0, 0.0  # 当前坐标
        
        for row in self.plan_data:
            seg_type = str(row.get('类型', '')).strip().upper()
            if not seg_type:
                continue
            
            # 获取长度和半径
            try:
                length = float(row.get('长度', 0)) if row.get('长度') is not None else 0.0
            except (ValueError, TypeError):
                log_message(f"无效的长度值: {row.get('长度')}", "WARNING")
                length = 0.0
            
            try:
                radius = float(row.get('半径', 0)) if row.get('半径') is not None else 0.0
            except (ValueError, TypeError):
                radius = 0.0
            
            # 创建线段数据
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
            
            # 计算线段终点
            if seg_type == 'Z':  # 直线
                curr_x += length * math.cos(curr_ang)
                curr_y += length * math.sin(curr_ang)
                # 方位角不变
                
            elif seg_type == 'Y' and radius != 0:  # 圆曲线
                d_theta = length / radius  # 转角（弧度）
                curr_ang += d_theta
                
                # 圆心坐标
                xc = curr_x - radius * math.sin(seg['ang0'])
                yc = curr_y + radius * math.cos(seg['ang0'])
                
                # 终点坐标
                curr_x = xc + radius * math.sin(curr_ang)
                curr_y = yc - radius * math.cos(curr_ang)
            
            curr_s += length
        
        self.max_plan_s = curr_s
        log_message(f"平面线形解析完成: {len(self.plan_segments)} 段, 总长 {curr_s:.2f}m")
    
    def _parse_vert_data(self):
        """
        解析竖直要素数据
        
        构建竖曲线变坡点列表，计算：
            - 坡度
            - 竖曲线起终点
            - 抛物线控制点
        """
        self.pvi_list = []
        
        # 读取变坡点数据
        for row in self.vert_data:
            if '桩号' not in row:
                continue
            
            try:
                s = parse_station(row.get('桩号', ''))
                e = float(str(row.get('变坡点标高', '')).strip())
                
                # 竖曲线半径（可选）
                r_str = row.get('竖曲线半径', '')
                r = float(str(r_str).strip()) if r_str else 0.0
                
                self.pvi_list.append({
                    's': s,      # 桩号
                    'e': e,      # 标高
                    'r': r       # 半径
                })
            except (ValueError, TypeError) as e:
                log_message(f"解析竖曲线数据时出错: {e}", "WARNING")
                continue
        
        # 按桩号排序
        self.pvi_list.sort(key=lambda item: item['s'])
        
        if len(self.pvi_list) < 2:
            log_message("竖曲线数据不足（至少需要2个变坡点）", "WARNING")
            return
        
        # 计算各段坡度
        for i in range(len(self.pvi_list) - 1):
            p1, p2 = self.pvi_list[i], self.pvi_list[i+1]
            ds = p2['s'] - p1['s']
            de = p2['e'] - p1['e']
            slope = de / ds if ds != 0 else 0
            p1['slope_out'] = slope  # 出坡
            p2['slope_in'] = slope   # 入坡
        
        # 计算竖曲线参数
        for i in range(1, len(self.pvi_list) - 1):
            p = self.pvi_list[i]
            r = p['r']
            
            if r > 0:
                g1 = p['slope_in']   # 入坡坡度
                g2 = p['slope_out']  # 出坡坡度
                
                # 竖曲线长度
                L = r * abs(g2 - g1)
                T = L / 2  # 切线长
                
                p['bvc_s'] = p['s'] - T  # 竖曲线起点桩号
                p['evc_s'] = p['s'] + T  # 竖曲线终点桩号
                p['bvc_e'] = p['e'] - T * g1  # 竖曲线起点标高
            else:
                # 无竖曲线
                p['bvc_s'] = p['s']
                p['evc_s'] = p['s']
        
        log_message(f"竖曲线解析完成: {len(self.pvi_list)} 个变坡点")
    
    def _get_xy(self, s):
        """
        根据桩号获取平面坐标
        
        参数:
            s: 桩号（米）
            
        返回:
            tuple: (x, y) 坐标
        """
        for seg in self.plan_segments:
            if seg['start_s'] <= s <= seg['end_s'] + 1e-5:
                ds = s - seg['start_s']
                
                if seg['type'] == 'Z':  # 直线
                    x = seg['x0'] + ds * math.cos(seg['ang0'])
                    y = seg['y0'] + ds * math.sin(seg['ang0'])
                    return x, y
                    
                elif seg['type'] == 'Y' and seg['R'] != 0:  # 圆曲线
                    # 圆心坐标
                    xc = seg['x0'] - seg['R'] * math.sin(seg['ang0'])
                    yc = seg['y0'] + seg['R'] * math.cos(seg['ang0'])
                    
                    # 当前角度
                    ang_s = seg['ang0'] + ds / seg['R']
                    
                    # 坐标
                    x = xc + seg['R'] * math.sin(ang_s)
                    y = yc - seg['R'] * math.cos(ang_s)
                    return x, y
        
        # 如果超出范围，返回最后一个点
        if self.plan_segments:
            last_seg = self.plan_segments[-1]
            return last_seg['x0'], last_seg['y0']
        return 0.0, 0.0
    
    def _get_z(self, s):
        """
        根据桩号获取高程
        
        参数:
            s: 桩号（米）
            
        返回:
            float: 高程（米）
        """
        if not self.pvi_list:
            return 0.0
        
        # 超出范围处理
        if s <= self.pvi_list[0]['s']:
            return self.pvi_list[0]['e']
        if s >= self.pvi_list[-1]['s']:
            return self.pvi_list[-1]['e']
        
        # 查找所在区间
        for i in range(len(self.pvi_list) - 1):
            p1, p2 = self.pvi_list[i], self.pvi_list[i+1]
            
            if p1['s'] <= s <= p2['s']:
                # 检查是否在下一个变坡点的竖曲线范围内
                if 'bvc_s' in p2 and p2['bvc_s'] < s < p2['evc_s']:
                    g1 = p2['slope_in']
                    g2 = p2['slope_out']
                    L = p2['evc_s'] - p2['bvc_s']
                    x = s - p2['bvc_s']
                    
                    # 抛物线公式
                    return p2['bvc_e'] + g1 * x + ((g2 - g1) / (2 * L)) * (x ** 2)
                
                # 检查是否在当前变坡点的竖曲线范围内
                elif 'bvc_s' in p1 and p1['bvc_s'] < s < p1['evc_s']:
                    g1 = p1['slope_in']
                    g2 = p1['slope_out']
                    L = p1['evc_s'] - p1['bvc_s']
                    x = s - p1['bvc_s']
                    
                    # 抛物线公式
                    return p1['bvc_e'] + g1 * x + ((g2 - g1) / (2 * L)) * (x ** 2)
                
                # 直线坡段
                else:
                    return p1['e'] + p1['slope_out'] * (s - p1['s'])
        
        return 0.0
    
    def _generate_3d_curve(self):
        """
        生成三维空间曲线
        
        使用采样点生成线段模型，并保存点数据供圆柱插件使用
        """
        # 确定采样范围
        max_s = self.max_plan_s
        if self.pvi_list:
            max_s = min(max_s, self.pvi_list[-1]['s'])
        
        if max_s <= 0:
            log_message("路线长度无效，无法生成曲线", "ERROR")
            return
        
        # 生成采样点
        self.curve_points = []
        segments_3d = []
        
        # 起点
        prev_x, prev_y = self._get_xy(0.0)
        prev_z = self._get_z(0.0)
        self.curve_points.append({'s': 0.0, 'x': prev_x, 'y': prev_y, 'z': prev_z})
        
        # 采样生成
        s = self.sample_step
        point_count = 1
        
        while s <= max_s + self.sample_step:
            curr_s = min(s, max_s)
            
            x, y = self._get_xy(curr_s)
            z = self._get_z(curr_s)
            
            # 创建线段
            segments_3d.append(
                Line(Vec3(prev_x, prev_y, prev_z), Vec3(x, y, z))
            )
            
            # 保存点数据
            self.curve_points.append({'s': curr_s, 'x': x, 'y': y, 'z': z})
            point_count += 1
            
            # 更新前一个点
            prev_x, prev_y, prev_z = x, y, z
            
            # 检查是否到达终点
            if curr_s >= max_s:
                break
            
            s += self.sample_step
        
        # 更新属性
        self['路线长度'] = max_s
        self['曲线点数据'] = json.dumps(self.curve_points)
        
        # 创建模型
        if segments_3d:
            self['模型'] = combine(*segments_3d).color(1, 0, 0)  # 红色
            log_message(f"生成曲线: {point_count} 个点, {len(segments_3d)} 条线段")
        else:
            log_message("未能生成任何线段", "WARNING")
    
    @export
    def get_point_at_station(self, s):
        """
        获取指定桩号处的三维坐标（供圆柱插件调用）
        
        参数:
            s: 桩号（米）
            
        返回:
            dict: {'x': x, 'y': y, 'z': z} 或 None
        """
        try:
            x, y = self._get_xy(s)
            z = self._get_z(s)
            return {'x': x, 'y': y, 'z': z}
        except Exception as e:
            log_message(f"获取桩号 {s} 处的坐标失败: {e}", "ERROR")
            return None
    
    @export
    def get_all_points(self):
        """
        获取所有采样点数据（供圆柱插件调用）
        
        返回:
            list: 点数据列表，每个点为 {'s': 桩号, 'x': x, 'y': y, 'z': z}
        """
        return self.curve_points
    
    @export
    def get_curve_length(self):
        """
        获取路线总长度
        
        返回:
            float: 路线长度（米）
        """
        return self.max_plan_s


# ============================================================================
# 插件主逻辑
# ============================================================================

def run_plugin():
    """
    运行路线生成插件
    
    流程：
        1. 显示主操作对话框
        2. 选择并读取平面/竖直要素表
        3. 验证数据完整性
        4. 生成三维曲线模型
    """
    log_message("=" * 60)
    log_message("路线生成插件 V4 启动")
    log_message("=" * 60)
    
    plan_data = []
    vert_data = []
    
    while True:
        # 显示主对话框
        choice = select_main_action(len(plan_data) > 0, len(vert_data) > 0)
        log_message(f"用户选择: {choice}")
        
        if choice == 'Confirm':
            # 确认生成
            if not plan_data or not vert_data:
                log_message("平面数据或竖直数据为空，无法生成模型", "WARNING")
                continue
            break
            
        elif choice == 'Planar':
            # 添加平面要素表
            file_path = select_excel_file("请选择平面要素表 (.xlsx)")
            if file_path and os.path.exists(file_path):
                try:
                    plan_data = read_excel_data(file_path)
                    log_message(f"成功读取平面要素表: {len(plan_data)} 行")
                except Exception as e:
                    log_message(f"读取平面要素表失败: {e}", "ERROR")
            else:
                log_message("未选择文件或文件不存在", "WARNING")
                
        elif choice == 'Vertical':
            # 添加竖直要素表
            file_path = select_excel_file("请选择竖直要素表 (.xlsx)")
            if file_path and os.path.exists(file_path):
                try:
                    vert_data = read_excel_data(file_path)
                    log_message(f"成功读取竖直要素表: {len(vert_data)} 行")
                except Exception as e:
                    log_message(f"读取竖直要素表失败: {e}", "ERROR")
            else:
                log_message("未选择文件或文件不存在", "WARNING")
                
        elif choice == 'Cancel' or not choice:
            # 取消操作
            log_message("用户取消操作")
            return
        
        else:
            log_message(f"未知选项: {choice}", "WARNING")
    
    # 验证数据
    log_message("验证数据完整性...")
    is_valid, errors = validate_route_data(plan_data, vert_data)
    
    if not is_valid:
        log_message("数据验证失败:", "ERROR")
        for error in errors:
            log_message(f"  - {error}", "ERROR")
        return
    
    log_message("数据验证通过")
    
    # 生成模型
    log_message("开始生成三维曲线模型...")
    try:
        model = CombinedRouteModel(plan_data, vert_data)
        place(model)
        log_message("模型生成成功并已放置到场景中")
    except Exception as e:
        log_message(f"生成模型失败: {e}", "ERROR")
        import traceback
        log_message(traceback.format_exc(), "DEBUG")


# ============================================================================
# 程序入口
# ============================================================================

if __name__ == "__main__":
    run_plugin()
