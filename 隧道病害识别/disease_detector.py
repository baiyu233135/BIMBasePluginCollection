# -*- coding: utf-8 -*-
"""
隧道病害检测模块 — YOLOv8n封装

提供隧道巡检照片的自动病害识别功能。
支持4类病害：裂缝、渗水、剥落、其他

使用CPU推理，适用于无GPU环境。
"""

import os
import sys
import traceback
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# ============================================================
# 配置
# ============================================================

# 模型文件目录（相对于本模块目录）
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

# 统一病害模型权重（桥隧合并训练，YOLOv8n，nc=7），优先使用
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, "disease_yolov8n.pt")

# 通用预训练权重兜底（不存在专用模型时使用，走 CV 检测路径）
GENERIC_FALLBACK_PATH = os.path.join(MODEL_DIR, "yolov8n.pt")

# 病害类别名称（隧道版显示层 4 类，顺序固定，界面/投影/报告共用）
DISEASE_CLASSES = [
    "裂缝",
    "渗水",
    "剥落",
    "其他",
]

# 统一模型类别（nc=7，桥梁类别顺序，与 disease_yolov8n.pt 训练配置一致）
UNIFIED_MODEL_CLASSES = [
    "裂缝",
    "剥落",
    "露筋",
    "蜂窝麻面",
    "渗水",
    "锈蚀",
    "已修复",
]

# 统一模型 7 类 → 隧道显示层 4 类 归并映射：
# 裂缝→裂缝、渗水→渗水、剥落→剥落、露筋/蜂窝麻面/锈蚀/已修复→其他
UNIFIED_TO_TUNNEL = {
    "裂缝": "裂缝",
    "渗水": "渗水",
    "剥落": "剥落",
    "露筋": "其他",
    "蜂窝麻面": "其他",
    "锈蚀": "其他",
    "已修复": "其他",
}


def merge_to_tunnel_class(class_name: str) -> str:
    """把统一模型 7 类名称归并为隧道显示层 4 类；非统一模型的类别原样返回（限 4 类内）。"""
    if class_name in UNIFIED_TO_TUNNEL:
        return UNIFIED_TO_TUNNEL[class_name]
    if class_name in DISEASE_CLASSES:
        return class_name
    return "其他"


# 各类隧道构件的常规病害映射（用于过滤/提示，均为归并后的 4 类）
COMPONENT_DISEASE_MAP = {
    # 衬砌：裂缝、渗水、剥落为最常见病害，露筋/蜂窝麻面等归并为其他
    '衬砌': ['裂缝', '渗水', '剥落', '其他'],
    # 路面：以裂缝、剥落（坑槽、断板）为主，其余归并类兜底
    '路面': ['裂缝', '渗水', '剥落', '其他'],
    # 洞门：开裂、砌体剥落、渗漏水
    '洞门': ['裂缝', '剥落', '渗水', '其他'],
    # 检修道：混凝土开裂、边角剥落、渗水
    '检修道': ['裂缝', '剥落', '渗水', '其他'],
    # 排水设施：渗漏水、淤塞及其他异常
    '排水': ['渗水', '其他'],
}


@dataclass
class DiseaseResult:
    """单个病害检测结果"""
    class_name: str          # 病害类型名称
    confidence: float        # 置信度 0-1
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2) 像素坐标
    image_width: int = 0
    image_height: int = 0
    
    def to_dict(self) -> dict:
        return {
            'class_name': self.class_name,
            'confidence': round(self.confidence, 4),
            'bbox': self.bbox,
            'image_width': self.image_width,
            'image_height': self.image_height,
        }


class DiseaseDetector:
    """病害检测器封装"""

    def __init__(self, model_path: Optional[str] = None, device: str = 'cpu'):
        """
        初始化病害检测器
        
        Args:
            model_path: YOLO模型权重文件路径，None则使用默认路径
            device: 推理设备，'cpu' 或 'cuda'
        """
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.device = device
        self.model = None
        self._model_loaded = False
        self._load_error = ""
    
    def _try_load_model(self) -> bool:
        """尝试加载YOLO模型"""
        if self._model_loaded:
            return True
        
        try:
            from ultralytics import YOLO
        except ImportError:
            self._load_error = "ultralytics未安装，正在尝试自动安装..."
            self._auto_install_ultralytics()
            try:
                from ultralytics import YOLO
            except ImportError:
                self._load_error = "ultralytics安装失败，请手动运行: pip install ultralytics"
                return False
        
        # 如果模型文件不存在，使用预训练权重或提示下载
        if not os.path.exists(self.model_path):
            self._load_error = f"模型文件不存在: {self.model_path}\n请先运行训练脚本下载数据集并训练模型。"
            # 尝试使用预训练权重作为fallback（检测通用物体）
            try:
                self.model = YOLO(GENERIC_FALLBACK_PATH)
                self._model_loaded = True
                self._load_error = "警告：使用通用预训练权重(yolov8n.pt)，病害检测可能不准确。请训练专用模型。"
                return True
            except Exception as e:
                self._load_error += f"\n加载默认权重也失败: {e}"
                return False
        
        try:
            self.model = YOLO(self.model_path)
            self._model_loaded = True
            self._load_error = ""
            return True
        except Exception as e:
            self._load_error = f"加载模型失败: {e}"
            traceback.print_exc()
            return False
    
    def _auto_install_ultralytics(self):
        """自动安装ultralytics及其依赖"""
        import subprocess
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "ultralytics", "torch", "torchvision",
                "--index-url", "https://download.pytorch.org/whl/cpu"
            ])
        except Exception:
            pass
    
    def is_ready(self) -> bool:
        """检测器是否已就绪"""
        if not self._model_loaded:
            self._try_load_model()
        return self._model_loaded
    
    def get_load_error(self) -> str:
        """获取模型加载错误信息"""
        return self._load_error
    
    def detect_anomalies(self, image_path: str) -> List[DiseaseResult]:
        """
        使用传统 CV 方法检测图片中的异常区域，不区分具体病害类型。

        不依赖 YOLO 模型，适合在没有专用病害模型时快速识别衬砌、洞门等
        隧道混凝土构件表面的裂缝、渗水、污渍等异常。

        Args:
            image_path: 图片文件路径

        Returns:
            DiseaseResult 列表，class_name 均为 "异常区域"
        """
        try:
            from cv_anomaly_detector import detect_anomalies_cv
            return detect_anomalies_cv(image_path)
        except Exception as e:
            print(f"[DiseaseDetector] 异常区域检测失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _resolve_class_name(self, cls_id: int) -> str:
        """
        把 YOLO 输出的类别 id 解析为隧道显示层类别名（4 类）。

        优先读模型自带类别表 names（统一模型 disease_yolov8n.pt 为 7 类，
        按桥梁类别顺序）；读不到时按统一模型 7 类顺序兜底索引。
        结果统一经 merge_to_tunnel_class 归并为隧道 4 类。
        """
        raw_name = None
        names = getattr(self.model, "names", None)
        if isinstance(names, dict):
            raw_name = names.get(cls_id)
        elif isinstance(names, (list, tuple)) and 0 <= cls_id < len(names):
            raw_name = names[cls_id]

        if raw_name is None:
            if 0 <= cls_id < len(UNIFIED_MODEL_CLASSES):
                raw_name = UNIFIED_MODEL_CLASSES[cls_id]
            elif 0 <= cls_id < len(DISEASE_CLASSES):
                raw_name = DISEASE_CLASSES[cls_id]
            else:
                return f"未知类别-{cls_id}"

        return merge_to_tunnel_class(raw_name)

    def detect(self, image_path: str, conf_threshold: float = 0.25) -> List[DiseaseResult]:
        """
        对单张图片进行病害检测。
        
        策略：
        - 如果加载的是专用病害模型，使用YOLO推理
        - 如果加载的是通用fallback模型（yolov8n.pt），使用OpenCV传统方法检测裂缝
        
        Args:
            image_path: 图片文件路径
            conf_threshold: 置信度阈值，低于此值的检测结果会被过滤
        
        Returns:
            DiseaseResult列表
        """
        # 判断是否使用通用fallback模型（仅当权重路径是通用 yolov8n.pt，
        # 或因缺少专用模型已回退到通用权重时；注意 disease_yolov8n.pt 也含
        # "yolov8n.pt" 子串，不能靠子串判断）
        is_fallback = os.path.basename(str(getattr(self, 'model_path', ''))) == "yolov8n.pt" or \
                      (self._load_error and "通用预训练权重" in self._load_error)
        
        if is_fallback:
            # 使用传统CV方法检测异常区域（隧道版统一走 cv_anomaly_detector，
            # 桥梁版的 cv_crack_detector 未复制到本插件）
            try:
                from cv_anomaly_detector import detect_anomalies_cv
                return detect_anomalies_cv(image_path)
            except Exception as e:
                print(f"[DiseaseDetector] CV检测失败: {e}")
                traceback.print_exc()
                return []
        
        if not self.is_ready():
            return []
        
        results = []
        try:
            from PIL import Image
            img = Image.open(image_path)
            img_w, img_h = img.size
            
            # YOLO推理（用 PIL 图像对象作为输入，不能用字符串路径：
            # BIMBase 内置环境的 opencv 读不了中文路径，会静默返回空结果）
            yolo_results = self.model.predict(
                source=img,
                device=self.device,
                conf=conf_threshold,
                verbose=False,
            )
            
            for r in yolo_results:
                boxes = r.boxes
                if boxes is None:
                    continue
                for box in boxes:
                    cls_id = int(box.cls.item()) if hasattr(box.cls, 'item') else int(box.cls[0])
                    conf = float(box.conf.item()) if hasattr(box.conf, 'item') else float(box.conf[0])
                    xyxy = box.xyxy.cpu().numpy().flatten().tolist()
                    x1, y1, x2, y2 = map(int, xyxy)
                    
                    # 映射到中文类别名：优先读模型自带类别表（统一模型为7类），
                    # 返回前统一归并为隧道显示层4类
                    class_name = self._resolve_class_name(cls_id)
                    
                    results.append(DiseaseResult(
                        class_name=class_name,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                        image_width=img_w,
                        image_height=img_h,
                    ))
        
        except Exception as e:
            print(f"[DiseaseDetector] 检测失败: {e}")
            traceback.print_exc()
        
        return results
    
    def detect_for_component(self, image_path: str, component_type: str, 
                             conf_threshold: float = 0.25) -> List[DiseaseResult]:
        """
        针对特定构件类型进行病害检测，返回结果可附加该构件的常规病害提示。
        
        Args:
            image_path: 图片文件路径
            component_type: 构件类型名称（如"箱梁"）
            conf_threshold: 置信度阈值
        
        Returns:
            DiseaseResult列表（已过滤掉该构件不可能出现的病害类型）
        """
        all_results = self.detect(image_path, conf_threshold)
        
        # 获取该构件的常规病害列表
        common_diseases = COMPONENT_DISEASE_MAP.get(component_type, DISEASE_CLASSES)
        
        # 过滤：只保留该构件常规的病害类型
        filtered = [r for r in all_results if r.class_name in common_diseases]
        
        return filtered
    
    def draw_results(self, image_path: str, results: List[DiseaseResult], 
                     output_path: Optional[str] = None) -> Optional[str]:
        """
        在图片上绘制检测结果的bbox和标签，保存并返回输出路径。
        
        Args:
            image_path: 原图路径
            results: 检测结果列表
            output_path: 输出路径，None则使用临时文件
        
        Returns:
            标注后的图片路径
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            img = Image.open(image_path).convert('RGB')
            draw = ImageDraw.Draw(img)
            
            # 尝试加载字体
            try:
                font = ImageFont.truetype("simhei.ttf", 20)
            except Exception:
                try:
                    font = ImageFont.truetype("msyh.ttf", 20)
                except Exception:
                    font = ImageFont.load_default()
            
            # 颜色映射：与 face_projection.DISEASE_COLOR_MAP 同源
            # （裂缝→红、渗水→蓝、剥落→橙、其他→灰，未知类型绿色兜底）
            try:
                from face_projection import DISEASE_COLOR_MAP as color_map
            except Exception:
                color_map = {
                    "裂缝": (255, 0, 0),        # 红
                    "渗水": (0, 0, 255),        # 蓝
                    "剥落": (255, 165, 0),      # 橙
                    "其他": (128, 128, 128),    # 灰
                }
            
            for r in results:
                color = color_map.get(r.class_name, (0, 255, 0))
                x1, y1, x2, y2 = r.bbox
                
                # 画框
                draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
                
                # 画标签背景
                label = f"{r.class_name} {r.confidence:.2f}"
                bbox_text = draw.textbbox((0, 0), label, font=font)
                tw, th = bbox_text[2] - bbox_text[0], bbox_text[3] - bbox_text[1]
                draw.rectangle([x1, y1 - th - 4, x1 + tw + 4, y1], fill=color)
                draw.text((x1 + 2, y1 - th - 2), label, fill=(255, 255, 255), font=font)
            
            if output_path is None:
                import tempfile
                output_path = os.path.join(tempfile.gettempdir(), "disease_detected.jpg")
            
            img.save(output_path, quality=95)
            return output_path
        
        except Exception as e:
            print(f"[DiseaseDetector] 绘制结果失败: {e}")
            traceback.print_exc()
            return None


# 便捷函数
def detect_diseases(image_path: str, component_type: str = "", 
                    conf_threshold: float = 0.25) -> List[DiseaseResult]:
    """便捷函数：一键检测"""
    detector = DiseaseDetector()
    if component_type:
        return detector.detect_for_component(image_path, component_type, conf_threshold)
    return detector.detect(image_path, conf_threshold)
