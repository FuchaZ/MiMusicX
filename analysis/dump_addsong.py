# -*- coding: utf-8 -*-
"""Disassemble SongListAddViewModel and its addSong coroutine."""
import sys, zipfile
sys.stdout.reconfigure(encoding='utf-8')
from androguard.core.dex import DEX

APK_PATH = r"D:\Zcode\音乐\小米音乐.apk"
TARGETS = [
    "Lcom/tencent/qqmusiclite/fragment/SongListAddViewModel$addSong$1;",
    "Lcom/tencent/qqmusiclite/fragment/SongListAddViewModel$addSong$2;",
    "Lcom/tencent/qqmusiclite/fragment/SongListAddViewModel$addSong$3;",
    "Lcom/tencent/qqmusiclite/fragment/SongListAddViewModel$addSong$4;",
    "Lcom/tencent/qqmusiclite/fragment/SongListAddViewModel;",
]

zf = zipfile.ZipFile(APK_PATH)
data = zf.read('classes8.dex')
d = DEX(data)

def dump_method(m, indent="  "):
    print(f"{indent}--- method {m.get_name()} {m.get_descriptor()} ---")
    for ins in m.get_code().get_bc().get_instructions():
        op = ins.get_name()
        try:
            operands = ins.get_operands()
            parts = []
            for o in operands:
                kind = o[0]
                if len(o) >= 3:
                    parts.append(f"{o[1]}({o[2]})")
                else:
                    parts.append(str(o[1]))
            print(f"{indent}  {op} {' '.join(parts)}")
        except Exception as e:
            print(f"{indent}  {op} <err {e}>")

for c in d.get_classes():
    cn = c.get_name()
    if cn in TARGETS:
        print(f"\n========== {cn} ==========")
        sf = c.get_fields()
        for f in sf:
            print(f"  field: {f.get_name()} : {f.get_descriptor()}")
        for m in c.get_methods():
            dump_method(m)

# also look for related classes in same dex
print("\n\n========== related classes containing 'SongListAdd' in classes8 ==========")
for c in d.get_classes():
    cn = c.get_name()
    if 'SongListAdd' in cn and cn not in TARGETS:
        print(f"  {cn}")
        for m in c.get_methods():
            print(f"      {m.get_name()} {m.get_descriptor()}")
