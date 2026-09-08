# -*- coding: utf-8 -*-
"""音频设备诊断脚本 - 检查麦克风和录音功能"""

import sys
import struct
import math
import io

# 修复 Windows 控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("=" * 50)
print("音频设备诊断")
print("=" * 50)

try:
    from PyQt5.QtCore import QCoreApplication, QBuffer, QIODevice
    from PyQt5.QtMultimedia import QAudioInput, QAudioFormat, QAudioDeviceInfo, QAudio
    app = QCoreApplication(sys.argv)
except Exception as e:
    print(f"ERROR: 无法加载 PyQt5: {e}")
    sys.exit(1)

# 1. 列出所有音频输入设备
print("\n【1. 音频输入设备列表】")
devices = QAudioDeviceInfo.availableDevices(QAudio.AudioInput)
if not devices:
    print("  未检测到任何音频输入设备！")
    print("  → 如果你用的是台式机，必须插上带麦克风的耳机/USB麦克风")
else:
    for i, d in enumerate(devices):
        marker = " <-- 默认设备" if d.deviceName() == QAudioDeviceInfo.defaultInputDevice().deviceName() else ""
        print(f"  [{i}] {d.deviceName()}{marker}")

# 2. 默认设备详情
print("\n【2. 默认输入设备详情】")
default = QAudioDeviceInfo.defaultInputDevice()
if default.isNull():
    print("  默认设备为空！")
else:
    print(f"  设备名: {default.deviceName()}")
    
    # 测试格式支持
    fmt = QAudioFormat()
    fmt.setSampleRate(16000)
    fmt.setChannelCount(1)
    fmt.setSampleSize(16)
    fmt.setCodec("audio/pcm")
    fmt.setByteOrder(QAudioFormat.LittleEndian)
    fmt.setSampleType(QAudioFormat.SignedInt)
    
    supported = default.isFormatSupported(fmt)
    print(f"  支持 16kHz/16bit/单声道: {supported}")
    
    if not supported:
        nearest = default.nearestFormat(fmt)
        print(f"  最接近的格式: {nearest.sampleRate()}Hz, {nearest.sampleSize()}bit, {nearest.channelCount()}ch")

# 3. 尝试录音测试
print("\n【3. 录音测试】")
print("  正在录音 3 秒，请对着麦克风说话...")

fmt = QAudioFormat()
fmt.setSampleRate(16000)
fmt.setChannelCount(1)
fmt.setSampleSize(16)
fmt.setCodec("audio/pcm")
fmt.setByteOrder(QAudioFormat.LittleEndian)
fmt.setSampleType(QAudioFormat.SignedInt)

info = QAudioDeviceInfo.defaultInputDevice()
if not info.isFormatSupported(fmt):
    fmt = info.nearestFormat(fmt)

buffer = QBuffer()
buffer.open(QIODevice.WriteOnly)

audio_input = QAudioInput(info, fmt)
audio_input.start(buffer)

# 用 QEventLoop 等待 3 秒
from PyQt5.QtCore import QEventLoop, QTimer
loop = QEventLoop()
QTimer.singleShot(3000, loop.quit)
loop.exec_()

audio_input.stop()
buffer.close()

pcm_data = bytes(buffer.data())
print(f"  录音数据大小: {len(pcm_data)} bytes")

if len(pcm_data) >= 2:
    count = len(pcm_data) // 2
    samples = struct.unpack(f'<{count}h', pcm_data[:count * 2])
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    peak = max(abs(s) for s in samples)
    print(f"  RMS 音量: {rms:.1f} (16bit 满幅=32767)")
    print(f"  峰值: {peak}")
    
    if rms < 50:
        print("  → 音量过低！麦克风可能没有声音")
        print("  → 如果你用的是台式机，请插上带麦克风的耳机或USB麦克风")
    elif rms < 500:
        print("  → 音量偏低，请靠近麦克风或提高音量")
    else:
        print("  → 音量正常，麦克风工作正常")
else:
    print("  → 没有录到数据！")

print("\n" + "=" * 50)
print("诊断完成")
print("=" * 50)
