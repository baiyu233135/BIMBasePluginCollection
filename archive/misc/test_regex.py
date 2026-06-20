# -*- coding: utf-8 -*-
import re

texts = [
    '把高度改为100',
    '把第一个矩形的高度改为100',
    '把圆柱半径改成80',
    '把所有元素的颜色改成红色',
]

# 先尝试匹配带 "的" 的模式
pat_with_de = r'(?:把|将|让)\s*(.+?)\s*的\s*(\S+?)\s*(?:改成|变成|设为|改为)\s*([+-]?\d+\.?\d*)'
# 再尝试匹配不带 "的" 的模式
pat_without_de = r'(?:把|将|让)\s*(.*?)\s*(?:改成|变成|设为|改为)\s*([+-]?\d+\.?\d*)'

for text in texts:
    print('\nText:', text)
    m = re.search(pat_with_de, text)
    if m:
        print('WITH DE -> target:', repr(m.group(1)), 'prop:', repr(m.group(2)), 'val:', repr(m.group(3)))
    else:
        m = re.search(pat_without_de, text)
        if m:
            print('WITHOUT DE -> target:', repr(m.group(1)), 'val:', repr(m.group(2)))
