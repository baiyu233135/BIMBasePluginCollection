# -*- coding: utf-8 -*-
"""
AI 智能诊断模块 — 基于阿里云 Qwen-VL 多模态大模型

输入：原图 + 算法圈好框的图片
输出：每个异常区域的结构化诊断结果

使用方式：
    from ai_diagnosis import diagnose_image
    results = diagnose_image(
        image_path="00.png",
        marked_image_path="00_anomaly.jpg",
        bboxes=[(x1,y1,x2,y2), ...],
        component_type="T梁"
    )
"""

import os
import json
import base64
import traceback
from typing import List, Tuple, Dict, Optional

# 尝试使用 requests，若不可用则使用 urllib
requests = None
try:
    import requests
except ImportError:
    pass


# 默认配置
DEFAULT_CONFIG = {
    "dashscope_api_key": "",
    "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "model": "qwen-vl-max",
    "temperature": 0.3,
    "max_tokens": 2000,
    "max_boxes": 10,
}


# 模块级配置缓存
_config_cache = None


def get_config_path() -> str:
    """获取配置文件路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "disease_config.json")


def load_config() -> dict:
    """加载配置文件，不存在则返回默认配置"""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    config_path = get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            # 自动迁移旧的 DashScope 原生 URL 到 OpenAI 兼容模式
            old_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
            if cfg.get("api_base") == old_url:
                cfg["api_base"] = DEFAULT_CONFIG["api_base"]
                _log(f"已自动更新 api_base 为 OpenAI 兼容模式")
            _config_cache = cfg
            return cfg
        except Exception as e:
            print(f"[AI诊断] 读取配置失败: {e}")

    _config_cache = dict(DEFAULT_CONFIG)
    return _config_cache


def save_config(cfg: dict) -> bool:
    """保存配置到配置文件，并刷新缓存"""
    global _config_cache
    config_path = get_config_path()
    try:
        merged = dict(DEFAULT_CONFIG)
        merged.update(cfg)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        _config_cache = merged
        _log(f"配置已保存: {config_path}")
        return True
    except Exception as e:
        _log(f"保存配置失败: {e}")
        return False


def set_api_key(api_key: str) -> bool:
    """便捷函数：仅更新 API Key"""
    cfg = load_config()
    cfg["dashscope_api_key"] = api_key.strip()
    return save_config(cfg)


def _log(msg: str):
    """写调试日志"""
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_disease_debug.log")
        from datetime import datetime
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] [AI_DIAG] {msg}\n")
    except Exception:
        pass


def image_to_base64(image_path: str) -> str:
    """将图片文件转为 base64 data URL"""
    try:
        with open(image_path, "rb") as f:
            data = f.read()
        ext = os.path.splitext(image_path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        _log(f"图片转base64失败: {image_path}, {e}")
        return ""


def _build_prompt(bboxes: List[Tuple[int, int, int, int]], component_type: str) -> str:
    """构造给 Qwen-VL 的 Prompt"""
    n = len(bboxes)
    bbox_text = "\n".join(
        f"  区域 {i+1}: 左上角({x1},{y1}), 右下角({x2},{y2}), 像素尺寸 {x2-x1}×{y2-y1}"
        for i, (x1, y1, x2, y2) in enumerate(bboxes)
    )

    prompt = f"""你是一位资深的桥梁病害检测专家。我将提供两张图片：

第一张是原始照片，第二张是用红色矩形框标出了异常区域的同一张照片。
这些照片拍摄的是桥梁的 {component_type} 构件表面。

算法共检测到 {n} 个异常区域，各区域像素坐标如下：
{bbox_text}

请按区域编号顺序，依次分析每个红色框内的异常。
对每个区域给出以下信息：
1. 病害类型：从 [裂缝、剥落、露筋、蜂窝麻面、渗水、锈蚀、异常区域] 中选择，若无法判断则填"异常区域"。
2. 严重程度：轻微 / 中等 / 严重 / 极严重。
3. 位置：用一句话描述该异常在照片中的相对位置（如"T梁腹板中部偏下"）。
4. 尺寸：用像素或估算实际尺寸描述。
5. 诊断建议：给出专业的处理或复查建议。

请严格按以下 JSON 格式输出，不要输出任何额外文字：
{{
  "diagnoses": [
    {{
      "box_index": 1,
      "disease_type": "剥落",
      "severity": "严重",
      "position": "T梁腹板中部偏下",
      "size": "约 150×100 像素",
      "diagnosis": "混凝土保护层大面积剥落，露骨料，建议尽快修补。"
    }},
    ...
  ]
}}

如果某个区域看起来是正常纹理或文字标记而非真实病害，也请在 diagnosis 中说明"疑似正常纹理/标记"。
"""
    return prompt


def _parse_response(content: str, expected_count: int) -> List[Dict]:
    """解析 AI 返回的 JSON"""
    if not content:
        return []

    # 尝试直接解析
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "diagnoses" in data:
            return data["diagnoses"]
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    import re
    matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    for m in matches:
        try:
            data = json.loads(m)
            if isinstance(data, dict) and "diagnoses" in data:
                return data["diagnoses"]
        except json.JSONDecodeError:
            continue

    # 尝试查找第一个 JSON 对象
    try:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(content[start:end+1])
            if isinstance(data, dict) and "diagnoses" in data:
                return data["diagnoses"]
    except json.JSONDecodeError:
        pass

    _log(f"无法解析AI返回: {content[:500]}")
    return []


def diagnose_image(
    image_path: str,
    marked_image_path: str,
    bboxes: List[Tuple[int, int, int, int]],
    component_type: str = "T梁"
) -> List[Dict]:
    """
    调用 Qwen-VL 对整张图进行智能诊断。

    Args:
        image_path: 原图路径
        marked_image_path: 带框图路径
        bboxes: 检测框列表 [(x1,y1,x2,y2), ...]
        component_type: 构件类型

    Returns:
        诊断结果列表，每个元素为 dict，包含 box_index、disease_type、severity、position、size、diagnosis
    """
    cfg = load_config()
    api_key = cfg.get("dashscope_api_key", "").strip()
    if not api_key:
        raise ValueError("未配置 dashscope_api_key，请先填写 桥梁病害识别/disease_config.json")

    base64_original = image_to_base64(image_path)
    base64_marked = image_to_base64(marked_image_path)
    if not base64_original or not base64_marked:
        raise ValueError("图片转 base64 失败")

    prompt = _build_prompt(bboxes, component_type)

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": base64_original}},
            {"type": "image_url", "image_url": {"url": base64_marked}},
        ]
    }]

    payload = {
        "model": cfg.get("model", "qwen-vl-max"),
        "messages": messages,
        "temperature": cfg.get("temperature", 0.3),
        "max_tokens": cfg.get("max_tokens", 2000),
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    api_base = cfg.get("api_base", DEFAULT_CONFIG["api_base"])

    try:
        _log(f"开始调用 Qwen-VL: model={payload['model']}, boxes={len(bboxes)}")

        if requests is not None:
            # 禁用系统代理，避免本地代理环境导致 SSL/Proxy 握手失败
            proxies = {"http": None, "https": None}
            resp = requests.post(api_base, headers=headers, json=payload, timeout=120, proxies=proxies)
            if not resp.ok:
                detail = resp.text[:500]
                _log(f"API请求失败: status={resp.status_code}, body={detail}")
                raise RuntimeError(f"API请求失败 ({resp.status_code}): {detail}")
            result = resp.json()
        else:
            import urllib.request
            req = urllib.request.Request(
                api_base,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            try:
                # 禁用 urllib 自动代理，与 requests 行为保持一致
                proxy_handler = urllib.request.ProxyHandler({})
                opener = urllib.request.build_opener(proxy_handler)
                with opener.open(req, timeout=120) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="ignore")[:500]
                _log(f"API请求失败: status={e.code}, body={body}")
                raise RuntimeError(f"API请求失败 ({e.code}): {body}")

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        _log(f"AI原始返回: {content[:500]}")

        diagnoses = _parse_response(content, len(bboxes))

        # 补齐缺失的 box_index
        for i, diag in enumerate(diagnoses):
            diag.setdefault("box_index", i + 1)
            diag.setdefault("disease_type", "异常区域")
            diag.setdefault("severity", "轻微")
            diag.setdefault("position", "未描述")
            diag.setdefault("size", "未估算")
            diag.setdefault("diagnosis", "暂无诊断建议")

        return diagnoses

    except Exception as e:
        err = traceback.format_exc()
        _log(f"AI诊断调用异常: {e}\n{err}")
        raise


def diagnose_image_safe(
    image_path: str,
    marked_image_path: str,
    bboxes: List[Tuple[int, int, int, int]],
    component_type: str = "T梁"
) -> Tuple[bool, List[Dict], str]:
    """
    diagnose_image 的安全包装，返回 (success, results, error_msg)
    """
    try:
        results = diagnose_image(image_path, marked_image_path, bboxes, component_type)
        return True, results, ""
    except Exception as e:
        return False, [], str(e)
