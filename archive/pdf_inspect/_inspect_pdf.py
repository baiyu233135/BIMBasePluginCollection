# -*- coding: utf-8 -*-
import fitz, os, json
path = r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\测试1.0.pdf'
doc = fitz.open(path)
for i, page in enumerate(doc):
    print('Page', i+1, 'size', page.rect.width, 'x', page.rect.height)
    drawings = page.get_drawings()
    print('Drawings:', len(drawings))
    items_summary = {}
    for d in drawings:
        for item in d.get('items', []):
            it = item[0]
            items_summary[it] = items_summary.get(it, 0) + 1
    print('Item types:', items_summary)
    # list some line bounds
    bounds = []
    for d in drawings:
        for item in d.get('items', []):
            if item[0] == 'l':
                p1, p2 = item[1], item[2]
                xs = [p1.x, p2.x]
                ys = [p1.y, p2.y]
                bounds.append((min(xs), min(ys), max(xs), max(ys)))
            elif item[0] == 're':
                r = item[1]
                bounds.append((r.x0, r.y0, r.x1, r.y1))
    print('Bounds count:', len(bounds))
    if bounds:
        print('First 10 bounds:')
        for b in bounds[:10]:
            print(' ', b)
        all_x = [x for b in bounds for x in (b[0], b[2])]
        all_y = [y for b in bounds for y in (b[1], b[3])]
        print('Overall bbox:', min(all_x), min(all_y), max(all_x), max(all_y))
    texts = page.get_text('blocks')
    print('Text blocks:', len(texts))
    for t in texts[:5]:
        print(' ', t)
doc.close()
