# -*- coding: utf-8 -*-
"""把 template.html + 本地 three.js 打包成单文件 常泰长江大桥数字孪生.html（离线可用）。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


template = read(os.path.join(HERE, 'template.html'))
three = read(os.path.join(HERE, 'lib', 'three.min.js'))
orbit = read(os.path.join(HERE, 'lib', 'OrbitControls.js'))

assert '</script' not in three.lower(), 'three.min.js 含 </script>，内联会破坏 HTML'
assert '</script' not in orbit.lower(), 'OrbitControls.js 含 </script>，内联会破坏 HTML'

html = (template
        .replace('/*__THREE_JS__*/', three)
        .replace('/*__ORBIT_JS__*/', orbit))
assert '/*__THREE_JS__*/' not in html and '/*__ORBIT_JS__*/' not in html

out = os.path.join(HERE, '常泰长江大桥数字孪生.html')
with io.open(out, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'OK: {out}  ({os.path.getsize(out)/1024:.0f} KB)')
