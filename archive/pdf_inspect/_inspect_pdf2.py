# -*- coding: utf-8 -*-
import fitz, os
path = r'C:\ProgramData\PKPM\BIMBase\Plugins\Pro\V1.6\pythonplugin\测试1.0.pdf'
doc = fitz.open(path)
page = doc[0]
print('Page size pt:', page.rect.width, page.rect.height)
drawings = page.get_drawings()
PT_TO_MM = 25.4/72.0
def to_mm(x,y):
    return x*PT_TO_MM, (page.rect.height-y)*PT_TO_MM
for idx, d in enumerate(drawings):
    print('\nDrawing', idx, 'color', d.get('color'), 'fill', d.get('fill'))
    for item in d.get('items', []):
        it = item[0]
        if it == 'l':
            p1, p2 = item[1], item[2]
            print('  line', to_mm(p1.x,p1.y), to_mm(p2.x,p2.y))
        elif it == 're':
            r = item[1]
            print('  rect', to_mm(r.x0,r.y0), to_mm(r.x1,r.y1))
        elif it == 'qu':
            q = item[1]
            pts = [q.ul, q.ur, q.lr, q.ll]
            print('  quad', [to_mm(p.x,p.y) for p in pts])
        elif it == 'c':
            print('  bezier')
        else:
            print('  ', it)
doc.close()
