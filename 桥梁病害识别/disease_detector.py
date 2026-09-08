# -*- coding: utf-8 -*-
"""
桥梁病害检测模块 — YOLOv8n封装

提供无人机照片的自动病害识别功能。
支持6类病害：裂缝、剥落、露筋、蜂窝麻面、渗水、锈蚀

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

# 模型文件路径（相对于本模块目录）
DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "models", "disease_yolov8n.pt"
)

# 病害类别名称（与训练时的顺序一致）
DISEASE_CLASSES = [
    "裂缝",
    "剥落",
    "露筋",
    "蜂窝麻面",
    "渗水",
    "锈蚀",
    "异常区域",  # 传统 CV 不分类别时的兜底标签
]

# 各类构件的常规病害映射（用于过滤/提示）
COMPONENT_DISEASE_MAP = {
    # 混凝土构件
    'T梁': ['裂缝', '剥落', '露筋', '蜂窝麻面', '渗水'],
    '箱梁': ['裂缝', '剥落', '露筋', '蜂窝麻面', '渗水'],
    '工字钢混凝土组合梁': ['裂缝', '剥落', '露筋', '蜂窝麻面', '渗水'],
    '主塔': ['裂缝', '剥落', '露筋', '蜂窝麻面', '渗水'],
    '湿接缝': ['裂缝', '渗水'],
    '防撞护栏': ['裂缝', '剥落', '锈蚀'],
    '主塔群桩承台': ['裂缝', '剥落', '露筋', '渗水'],
    '异形盖梁': ['裂缝', '剥落', '露筋', '渗水'],
    '扩大基础': ['裂缝', '剥落', '渗水'],
    '柱式桥台': ['裂缝', '剥落', '露筋', '渗水'],
    '柱式桥墩': ['裂缝', '剥落', '露筋', '渗水'],
    '桩基承台': ['裂缝', '剥落', '露筋', '渗水'],
    '薄壁墩': ['裂缝', '剥落', '露筋', '渗水'],
    '重力式桥台': ['裂缝', '剥落', '渗水'],
    '人行道及护栏': ['裂缝', '剥落', '锈蚀'],
    # 钢结构构件
    '斜拉索': ['锈蚀', '断丝'],
    '波形护栏': ['锈蚀', '涂层脱落', '变形'],
    # 路面
    '路面及交通标线': ['裂缝', '坑槽', '标线磨损'],
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
            fallback_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "models", "yolov8n.pt"
            )
            try:
                self.model = YOLO(fallback_path)
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

        不依赖 YOLO 模型，适合在没有专用病害模型时快速识别 T 梁等
        混凝土构件表面的裂缝、渗水、污渍等异常。

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
        # 判断是否使用通用fallback模型
        is_fallback = "yolov8n.pt" in str(getattr(self, 'model_path', '')) or \
                      (self._load_error and "通用预训练权重" in self._load_error)
        
        if is_fallback:
            # 使用传统CV方法检测裂缝
            try:
                from cv_crack_detector import detect_cracks_cv
                return detect_cracks_cv(image_path)
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
            
            # YOLO推理
            yolo_results = self.model.predict(
                source=image_path,
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
                    
                    # 映射到中文类别名
                    if 0 <= cls_id < len(DISEASE_CLASSES):
                        class_name = DISEASE_CLASSES[cls_id]
                    else:
                        class_name = f"未知类别-{cls_id}"
                    
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
            
            # 颜色映射
            color_map = {
                "裂缝": (255, 0, 0),      # 红
                "剥落": (255, 128, 0),    # 橙
                "露筋": (255, 255, 0),    # 黄
                "蜂窝麻面": (128, 0, 255), # 紫
                "渗水": (0, 128, 255),    # 蓝
                "锈蚀": (128, 128, 128),  # 灰
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
