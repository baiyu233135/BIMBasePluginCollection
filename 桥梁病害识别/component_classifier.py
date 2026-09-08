# -*- coding: utf-8 -*-
"""
桥梁构件图像分类模块 — EfficientNet-B0封装

自动识别无人机照片中的桥梁构件类型（19类）。

分类类别（与桥梁组件库19种构件对应）：
上部结构: T梁、主塔、工字钢混凝土组合梁、斜拉索、湿接缝、箱梁、防撞护栏、波形护栏
下部结构: 主塔群桩承台、异形盖梁、扩大基础、柱式桥台、柱式桥墩、桩基承台、薄壁墩、重力式桥台
附属设施: 人行道及护栏、波形护栏、路面及交通标线、防撞护栏
"""

import os
import sys
import traceback
from typing import Optional, Tuple

# 模型文件路径（本模块目录）
DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "models", "component_classifier.pt"
)

# 19种构件类型（与桥梁组件库一一对应）
COMPONENT_CLASSES = [
    # 上部结构
    "T梁",
    "主塔",
    "工字钢混凝土组合梁",
    "斜拉索",
    "湿接缝",
    "箱梁",
    "防撞护栏",
    "波形护栏",
    # 下部结构
    "主塔群桩承台",
    "异形盖梁",
    "扩大基础",
    "柱式桥台",
    "柱式桥墩",
    "桩基承台",
    "薄壁墩",
    "重力式桥台",
    # 附属设施
    "人行道及护栏",
    "路面及交通标线",
]

# 构件类型与病害的关联（用于后续病害检测过滤）
COMPONENT_TO_STRUCTURE = {
    # 上部结构
    "T梁": "superstructure",
    "主塔": "superstructure",
    "工字钢混凝土组合梁": "superstructure",
    "斜拉索": "superstructure",
    "湿接缝": "superstructure",
    "箱梁": "superstructure",
    "防撞护栏": "superstructure",
    "波形护栏": "superstructure",
    # 下部结构
    "主塔群桩承台": "substructure",
    "异形盖梁": "substructure",
    "扩大基础": "substructure",
    "柱式桥台": "substructure",
    "柱式桥墩": "substructure",
    "桩基承台": "substructure",
    "薄壁墩": "substructure",
    "重力式桥台": "substructure",
    # 附属设施
    "人行道及护栏": "ancillary",
    "路面及交通标线": "ancillary",
}


class ComponentClassifier:
    """构件图像分类器"""

    def __init__(self, model_path: Optional[str] = None, device: str = 'cpu'):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.device = device
        self.model = None
        self._model_loaded = False
        self._load_error = ""
        self.input_size = 224  # EfficientNet-B0标准输入尺寸
    
    def _try_load_model(self) -> bool:
        """尝试加载分类模型"""
        if self._model_loaded:
            return True
        
        # 检查模型文件是否存在
        if not os.path.exists(self.model_path):
            self._load_error = (
                f"构件分类模型不存在: {self.model_path}\n"
                "请先运行训练脚本训练模型，或在UI中手动选择构件类型。"
            )
            return False
        
        try:
            import torch
            import torchvision.transforms as transforms
            from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights
            
            # 加载模型结构
            self.model = efficientnet_b0(weights=None)
            num_features = self.model.classifier[1].in_features
            self.model.classifier[1] = torch.nn.Linear(num_features, len(COMPONENT_CLASSES))
            
            # 加载训练好的权重
            state_dict = torch.load(self.model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            self.model.to(self.device)
            
            # 定义预处理
            self.transform = transforms.Compose([
                transforms.Resize((self.input_size, self.input_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                                     std=[0.229, 0.224, 0.225]),
            ])
            
            self._model_loaded = True
            self._load_error = ""
            return True
        
        except ImportError as e:
            self._load_error = f"缺少依赖: {e}\n请运行: pip install torch torchvision"
            return False
        except Exception as e:
            self._load_error = f"加载模型失败: {e}"
            traceback.print_exc()
            return False
    
    def is_ready(self) -> bool:
        """分类器是否已就绪"""
        if not self._model_loaded:
            self._try_load_model()
        return self._model_loaded
    
    def get_load_error(self) -> str:
        """获取加载错误信息"""
        return self._load_error
    
    def classify(self, image_path: str) -> Tuple[str, float]:
        """
        对单张图片进行构件类型分类。
        
        Args:
            image_path: 图片文件路径
        
        Returns:
            (构件类型名称, 置信度)，分类失败返回 ("", 0.0)
        """
        if not self.is_ready():
            return "", 0.0
        
        try:
            import torch
            from PIL import Image
            
            img = Image.open(image_path).convert('RGB')
            input_tensor = self.transform(img).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(input_tensor)
                probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
                conf, predicted_idx = torch.max(probabilities, 0)
            
            predicted_idx = predicted_idx.item()
            conf = conf.item()
            
            if 0 <= predicted_idx < len(COMPONENT_CLASSES):
                return COMPONENT_CLASSES[predicted_idx], conf
            return "", 0.0
        
        except Exception as e:
            print(f"[ComponentClassifier] 分类失败: {e}")
            traceback.print_exc()
            return "", 0.0
    
    def classify_topk(self, image_path: str, k: int = 3) -> list:
        """
        返回Top-K分类结果（用于UI展示候选）。
        
        Returns:
            [(构件类型, 置信度), ...]
        """
        if not self.is_ready():
            return []
        
        try:
            import torch
            from PIL import Image
            
            img = Image.open(image_path).convert('RGB')
            input_tensor = self.transform(img).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(input_tensor)
                probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
            
            topk = torch.topk(probabilities, min(k, len(COMPONENT_CLASSES)))
            result = []
            for i in range(len(topk.indices)):
                idx = topk.indices[i].item()
                conf = topk.values[i].item()
                if 0 <= idx < len(COMPONENT_CLASSES):
                    result.append((COMPONENT_CLASSES[idx], conf))
            return result
        
        except Exception as e:
            print(f"[ComponentClassifier] TopK分类失败: {e}")
            traceback.print_exc()
            return []


def classify_component(image_path: str) -> Tuple[str, float]:
    """便捷函数：一键分类"""
    clf = ComponentClassifier()
    return clf.classify(image_path)
