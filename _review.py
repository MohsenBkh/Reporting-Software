# -*- coding: utf-8 -*-
"""بازبینی کیفی متن گزارش تولیدشده."""
import glob
import re
import sys
import zipfile

f = glob.glob(r'D:\My apps\Report Generator\new\_demo_out\*.docx')[0]
with zipfile.ZipFile(f) as z:
    xml = z.read('word/document.xml').decode('utf-8')
texts = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', xml)
full = '\n'.join(t for t in texts if t.strip())
sys.stdout.buffer.write(full[:3500].encode('utf-8'))
print()
print('==== length:', len(full))
