# -*- coding: utf-8 -*-
"""
语音输入模块 - v1.6
使用 PyQt5 QAudioInput 录制音频，支持百度语音识别 API
"""

import io
import json
import math
import struct
import urllib.request
import urllib.parse
import wave
from urllib.error import URLError

from PyQt5.QtCore import QObject, pyqtSignal, QBuffer, QIODevice
from PyQt5.QtMultimedia import QAudioInput, QAudioFormat, QAudioDeviceInfo, QAudio


class VoiceRecorder(QObject):
    """PyQt5 音频录制器"""
    finished = pyqtSignal(object, int)  # (wav_data, sample_rate)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._audio_input = None
        self._buffer = None
        self._recording = False
        self._sample_rate = 16000

    def _pick_device(self):
        """选择录音设备：优先选真实麦克风，避开虚拟设备"""
        devices = QAudioDeviceInfo.availableDevices(QAudio.AudioInput)
        names = [d.deviceName() for d in devices]
        print(f"[VoiceInput] 可用设备: {names}")

        # 优先匹配真实麦克风
        for d in devices:
            name_lower = d.deviceName().lower()
            if '阵列' in name_lower or 'realtek' in name_lower or 'microphone' in name_lower:
                if 'todesk' not in name_lower and 'virtual' not in name_lower:
                    return d
        # 次选任何不含 virtual/todesk 的设备
        for d in devices:
            name_lower = d.deviceName().lower()
            if 'todesk' not in name_lower and 'virtual' not in name_lower:
                return d
        # 最后用默认
        return QAudioDeviceInfo.defaultInputDevice()

    def start(self):
        """开始录音"""
        if self._recording:
            return

        info = self._pick_device()
        if info.isNull():
            self.error.emit("未检测到麦克风设备")
            return
        print(f"[VoiceInput] 使用设备: {info.deviceName()}")

        fmt = QAudioFormat()
        fmt.setSampleRate(16000)
        fmt.setChannelCount(1)
        fmt.setSampleSize(16)
        fmt.setCodec("audio/pcm")
        fmt.setByteOrder(QAudioFormat.LittleEndian)
        fmt.setSampleType(QAudioFormat.SignedInt)

        if not info.isFormatSupported(fmt):
            fmt = info.nearestFormat(fmt)
        self._sample_rate = fmt.sampleRate()
        print(f"[VoiceInput] 实际格式: {fmt.sampleRate()}Hz {fmt.sampleSize()}bit {fmt.channelCount()}ch")

        # 每次新建 buffer（避免状态污染）
        self._buffer = QBuffer()
        self._buffer.open(QIODevice.WriteOnly)

        self._audio_input = QAudioInput(info, fmt)
        self._audio_input.start(self._buffer)
        self._recording = True

    def stop(self):
        """停止录音并发出 WAV 数据"""
        if not self._recording or self._audio_input is None:
            return

        self._audio_input.stop()
        self._recording = False

        if self._buffer is None:
            return
        pcm_data = bytes(self._buffer.data())
        self._buffer.close()
        self._buffer = None

        print(f"[VoiceInput] 原始 PCM: {len(pcm_data)} bytes")

        if len(pcm_data) < 2048:
            self.error.emit(f"录音时间太短 ({len(pcm_data)} bytes)")
            return

        rms = self._calc_rms(pcm_data)
        print(f"[VoiceInput] RMS: {rms:.1f}")
        if rms < 50:
            self.error.emit(f"录音音量过低 (RMS={rms:.0f})，请对着麦克风说话")
            return

        wav_data = self._pcm_to_wav(pcm_data, self._sample_rate, 1, 16)
        print(f"[VoiceInput] WAV: {len(wav_data)} bytes")
        self.finished.emit(wav_data, self._sample_rate)

    def is_recording(self):
        return self._recording

    @staticmethod
    def _calc_rms(pcm_data: bytes) -> float:
        if len(pcm_data) < 2:
            return 0.0
        count = len(pcm_data) // 2
        samples = struct.unpack(f'<{count}h', pcm_data[:count * 2])
        if not samples:
            return 0.0
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / len(samples))

    @staticmethod
    def _pcm_to_wav(pcm_data, sample_rate, channels, sample_bits):
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(channels)
            w.setsampwidth(sample_bits // 8)
            w.setframerate(sample_rate)
            w.writeframes(pcm_data)
        return buf.getvalue()


class BaiduSpeechRecognizer(QObject):
    """百度语音识别（短语音识别标准版）"""
    result = pyqtSignal(str)   # 识别成功，发出文字
    error = pyqtSignal(str)    # 识别失败

    def __init__(self, api_key='', secret_key='', parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.secret_key = secret_key
        self._token = None

    def _get_token(self):
        """获取百度 access_token"""
        if not self.api_key or not self.secret_key:
            raise ValueError("未配置百度语音 API Key / Secret Key")

        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        })
        req = urllib.request.Request(url, data=params.encode('utf-8'))
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            token = data.get('access_token')
            if not token:
                err = data.get('error_description', str(data))
                raise ValueError(f"获取百度 token 失败: {err}")
            self._token = token
            return self._token

    def recognize(self, wav_data: bytes, sample_rate: int = 16000):
        """识别 WAV 音频，返回文字"""
        try:
            token = self._get_token()
            url = (
                f"https://vop.baidu.com/server_api"
                f"?dev_pid=1537&cuid=CADBoard&token={token}&rate={sample_rate}"
            )

            req = urllib.request.Request(url, data=wav_data, method='POST')
            req.add_header('Content-Type', f'audio/wav; rate={sample_rate}')

            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            if result.get('err_no') != 0:
                err_no = result.get('err_no')
                err_msg = result.get('err_msg', '未知错误')
                # 常见错误码给出明确指引
                if err_no == 6:
                    hint = (
                        "百度识别失败: 权限不足。请检查:\n"
                        "1. API Key 和 Secret Key 是否填写正确\n"
                        "2. 百度应用是否开通了'短语音识别标准版'服务\n"
                        "3. 应用是否已审核通过 (未审核应用有额度限制)\n"
                        "控制台: https://console.bce.baidu.com/ai"
                    )
                elif err_no == 3300:
                    hint = "百度识别失败: 输入参数错误，音频格式可能不对"
                elif err_no == 3301:
                    hint = "百度识别失败: 音频质量过差，请靠近麦克风重试"
                elif err_no == 3302:
                    hint = "百度识别失败: token 验证失败，请检查 Secret Key"
                else:
                    hint = f"百度识别失败 ({err_no}): {err_msg}"
                self.error.emit(hint)
                return

            results = result.get('result', [])
            if results and results[0] and results[0].strip():
                text = results[0].strip()
                self.result.emit(text)
            else:
                snr = result.get('snr', '未知')
                self.error.emit(f"未能识别到语音内容 (百度返回空结果，信噪比: {snr})")

        except URLError as e:
            self.error.emit(f"网络错误: {e}")
        except Exception as e:
            self.error.emit(f"识别异常: {e}")
