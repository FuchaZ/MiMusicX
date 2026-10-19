# -*- coding: utf-8 -*-
"""按关键字搜索类索引。用法: python search_index.py <kw1> [kw2 ...]  (全部 kw 都要出现, 忽略大小写)"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

INDEX = r"classes_index.txt"

keys = [k.lower() for k in sys.argv[1:]]
if not keys:
    sys.exit("usage: python search_index.py <kw...>")

rows = []
skipped = 0
with open(INDEX, encoding='utf-8') as f:
    for line in f:
        line = line.rstrip('\n')
        if '\t' not in line:
            skipped += 1
            continue
        dex, desc = line.split('\t', 1)
        low = desc.lower()
        if all(k in low for k in keys):
            rows.append((dex, desc))

for dex, desc in rows:
    print(f"{dex:<16} {desc}")
print(f"-- {len(rows)} class(es) matched {keys}")
