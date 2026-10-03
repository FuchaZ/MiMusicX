# -*- coding: utf-8 -*-
"""Find FolderInfo class definition dex + dump method signatures."""
import sys, zipfile
sys.stdout.reconfigure(encoding='utf-8')
from androguard.core.dex import DEX

APK_PATH = r"D:\Zcode\音乐\小米音乐.apk"
TARGET = 'Lcom/tencent/qqmusic/core/folder/FolderInfo;'

zf = zipfile.ZipFile(APK_PATH)
for df in sorted(n for n in zf.namelist() if n.endswith('.dex')):
    data = zf.read(df)
    if TARGET.encode() not in data:
        continue
    d = DEX(data)
    for c in d.get_classes():
        if c.get_name() == TARGET:
            print(f"FOUND in {df}")
            print(f"access={hex(c.get_access_flags())} super={c.get_superclassname()}")
            for m in c.get_methods():
                print(f"  {hex(m.get_access_flags())} {m.get_name()} {m.get_descriptor()}")
            for f in c.get_fields()[:10]:
                print(f"  field {f.get_name()} {f.get_descriptor()}")
            sys.exit(0)
print("not found as class def")
