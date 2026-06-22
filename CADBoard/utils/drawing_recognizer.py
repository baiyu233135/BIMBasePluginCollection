# -*- coding: utf-8 -*-
"""
多模态图纸识别器 — Phase 2

基于 DashScope Qwen-VL 从 PDF/图片图纸中提取参数化组件信息。
"""

import os
import json
import base64
import re
import traceback
import tempfile
from typing import Dict, List, Tuple, Optional

# 优先使用 requests，否则回退 urllib
_requests = None
try:
    import requests as _requests
except ImportError:
    pass

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from utils.component_matcher import match_recognized_result


DEFAULT_CONFIG = {
    "dashscope_api_key": "",
    "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "model": "qwen-vl-max",
    "temperature": 0.2,
    "max_tokens": 2000,
}

_config_cache = None


def get_config_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "drawing_ai_config.json")


def load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            _config_cache = cfg
            return cfg
        except Exception as e:
            _log(f"读取配置失败: {e}")
    _config_cache = dict(DEFAULT_CONFIG)
    return _config_cache


def save_config(cfg: dict) -> bool:
    global _config_cache
    path = get_config_path()
    try:
        merged = dict(DEFAULT_CONFIG)
        merged.update(cfg)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        _config_cache = merged
        return True
    except Exception as e:
        _log(f"保存配置失败: {e}")
        return False


def set_api_key(api_key: str) -> bool:
    cfg = load_config()
    cfg["dashscope_api_key"] = api_key.strip()
    return save_config(cfg)


def has_api_key() -> bool:
    return bool(load_config().get("dashscope_api_key", "").strip())


def _log(msg: str):
    try:
        log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "drawing_recognizer.log")
        from datetime import datetime
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def image_to_base64(image_path: str) -> str:
    try:
        with open(image_path, "rb") as f:
            data = f.read()
        ext = os.path.splitext(image_path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        _log(f"图片转 base64 失败: {image_path}, {e}")
        return ""


def pdf_to_images(pdf_path: str, output_dir: Optional[str] = None, dpi: int = 150) -> List[str]:
    """将 PDF 每页渲染为 PNG，返回图片路径列表。"""
    if fitz is None:
        raise RuntimeError("未安装 PyMuPDF (fitz)，无法转换 PDF")

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="cadboard_drawing_")
    os.makedirs(output_dir, exist_ok=True)

    paths = []
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i in range(len(doc)):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=mat)
        out_path = os.path.join(output_dir, f"page_{i + 1}.png")
        pix.save(out_path)
        paths.append(out_path)
    doc.close()
    return paths


def _build_prompt(component_hint: Optional[str]) -> str:
    hint_text = f"本次优先识别构件类型：{component_hint}。" if component_hint else ""
    return f"""你是一位资深的桥梁工程图纸识别专家。我将提供一张 PDF/DWG 图纸截图，其中包含桥梁构件的三视图或二维表达。

{hint_text}
请忽略图框、尺寸标注线、文字说明、标题栏等非构件本体内容，只提取构件本体的关键几何尺寸。

请按以下 JSON 格式输出，不要输出任何额外文字：
{{
  "component_type": "引桥桥墩",
  "confidence": 0.92,
  "views": {{
    "front": {{"description": "主视图描述"}},
    "top": {{"description": "俯视图描述"}},
    "left": {{"description": "左视图描述"}}
  }},
  "parameters": {{
    "盖梁总长": {{"value": 1930, "unit": "mm"}},
    "盖梁总高": {{"value": 300, "unit": "mm"}},
    "凸起宽": {{"value": 30, "unit": "mm"}},
    "凸起高": {{"value": 50, "unit": "mm"}},
    "盖梁主体底宽": {{"value": 1390, "unit": "mm"}},
    "斜边水平投影": {{"value": 270, "unit": "mm"}},
    "斜边垂直投影": {{"value": 120, "unit": "mm"}},
    "盖梁宽": {{"value": 300, "unit": "mm"}},
    "墩柱直径": {{"value": 270, "unit": "mm"}},
    "墩柱间距": {{"value": 1140, "unit": "mm"}},
    "墩高": {{"value": 1200, "unit": "mm"}},
    "系梁长": {{"value": 890, "unit": "mm"}},
    "系梁宽": {{"value": 200, "unit": "mm"}},
    "系梁高": {{"value": 200, "unit": "mm"}},
    "系梁数量": {{"value": 2, "unit": "个"}},
    "系梁起始距顶": {{"value": 200, "unit": "mm"}},
    "系梁间距": {{"value": 500, "unit": "mm"}}
  }},
  "notes": "任何补充说明"
}}

说明：
1. component_type 请从 [引桥桥墩] 中选择；无法判断时填最接近的。
2. 单位支持 mm/cm/m，输出时统一标注实际单位，系统会自动换算为 mm。
3. 若图纸中某些尺寸缺失，可省略该字段，系统会使用默认值。
4. confidence 为 0~1 的识别置信度。
"""


def _parse_json_response(content: str) -> Optional[Dict]:
    if not content:
        return None

    # 直接解析
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 从 markdown 代码块提取
    matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    for m in matches:
        try:
            data = json.loads(m)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    # 查找第一个 JSON 对象
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(content[start:end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    return None


def recognize_with_qwen_vl(image_path: str, component_hint: Optional[str] = None) -> Dict:
    """调用 Qwen-VL 识别单张图纸图片，返回原始 JSON 结果。"""
    cfg = load_config()
    api_key = cfg.get("dashscope_api_key", "").strip()
    if not api_key:
        raise ValueError("未配置 dashscope_api_key，请在 图纸识别 API 配置 中填写")

    b64 = image_to_base64(image_path)
    if not b64:
        raise ValueError("图片转 base64 失败")

    prompt = _build_prompt(component_hint)
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": b64}},
        ]
    }]

    payload = {
        "model": cfg.get("model", "qwen-vl-max"),
        "messages": messages,
        "temperature": float(cfg.get("temperature", 0.2)),
        "max_tokens": int(cfg.get("max_tokens", 2000)),
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    api_base = cfg.get("api_base", DEFAULT_CONFIG["api_base"])

    try:
        _log(f"开始识别: image={image_path}, model={payload['model']}, hint={component_hint}")
        if _requests is not None:
            resp = _requests.post(api_base, headers=headers, json=payload, timeout=120)
            if not resp.ok:
                detail = resp.text[:500]
                _log(f"API 请求失败: {resp.status_code}, {detail}")
                raise RuntimeError(f"API 请求失败 ({resp.status_code}): {detail}")
            result = resp.json()
        else:
            import urllib.request
            req = urllib.request.Request(
                api_base,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        _log(f"AI 原始返回: {content[:800]}")

        parsed = _parse_json_response(content)
        if parsed is None:
            raise ValueError(f"无法解析 AI 返回为 JSON: {content[:500]}")
        return parsed

    except Exception as e:
        err = traceback.format_exc()
        _log(f"识别异常: {e}\n{err}")
        raise


def recognize_drawing_file(file_path: str, component_hint: Optional[str] = None) -> List[Dict]:
    """
    识别一个图纸文件（PDF 或图片）。
    返回每页的识别结果列表，每个元素包含原始结果与匹配后的本地参数。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}

    image_paths = []
    if ext == ".pdf":
        image_paths = pdf_to_images(file_path)
    elif ext in image_exts:
        image_paths = [file_path]
    else:
        raise ValueError(f"暂不支持的文件格式: {ext}，请使用 PDF 或图片")

    results = []
    for img_path in image_paths:
        raw = recognize_with_qwen_vl(img_path, component_hint=component_hint)
        comp_type, params, confidence, notes = match_recognized_result(raw, component_hint=component_hint)
        results.append({
            'image_path': img_path,
            'raw': raw,
            'component_type': comp_type,
            'params': params,
            'confidence': confidence,
            'notes': notes,
        })
    return results
