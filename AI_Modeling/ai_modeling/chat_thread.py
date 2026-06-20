# -*- coding: utf-8 -*-
"""DeepSeek API 聊天线程（支持流式输出）"""
import json
import urllib.request
import urllib.error

try:
    from PyQt5.QtCore import QThread, pyqtSignal
except ImportError:
    from PyQt6.QtCore import QThread, pyqtSignal


class AIChatThread(QThread):
    """AI对话后台线程 - 流式输出"""
    chunk_ready = pyqtSignal(str)      # 每个流式片段
    response_ready = pyqtSignal(str)   # 完整响应
    error_occurred = pyqtSignal(str)   # 错误

    def __init__(self, api_key, messages, api_base=None, model=None, temperature=0.3, max_tokens=2000):
        super().__init__()
        self.api_key = api_key
        self.messages = messages
        self.api_base = api_base or "https://api.deepseek.com/chat/completions"
        self.model = model or "deepseek-chat"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._full_content = ""

    def run(self):
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "text/event-stream",
            }
            data = {
                "model": self.model,
                "messages": self.messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
                "response_format": {"type": "json_object"},
            }

            req = urllib.request.Request(
                self.api_base,
                data=json.dumps(data).encode('utf-8'),
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                for line in resp:
                    line = line.decode('utf-8').strip()
                    if not line or line == "data: [DONE]":
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    try:
                        chunk = json.loads(line)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            self._full_content += content
                            self.chunk_ready.emit(content)
                    except json.JSONDecodeError:
                        pass

            self.response_ready.emit(self._full_content)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='ignore') if hasattr(e, 'read') else ''
            self.error_occurred.emit(f"API错误 {e.code}: {body[:200]}")
        except Exception as e:
            self.error_occurred.emit(str(e))


class AIChatNonStreamThread(QThread):
    """非流式AI对话线程（备用）"""
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, messages, api_base=None, model=None, temperature=0.3, max_tokens=2000):
        super().__init__()
        self.api_key = api_key
        self.messages = messages
        self.api_base = api_base or "https://api.deepseek.com/chat/completions"
        self.model = model or "deepseek-chat"
        self.temperature = temperature
        self.max_tokens = max_tokens

    def run(self):
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            data = {
                "model": self.model,
                "messages": self.messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "response_format": {"type": "json_object"},
            }

            req = urllib.request.Request(
                self.api_base,
                data=json.dumps(data).encode('utf-8'),
                headers=headers,
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                content = result['choices'][0]['message']['content']
                self.response_ready.emit(content)
        except Exception as e:
            self.error_occurred.emit(str(e))
