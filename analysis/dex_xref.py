# -*- coding: utf-8 -*-
"""Find methods in XM dexes that use resource 0x7f140ad0 (qq_music_playlist_song_over_size),
and dump their context (strings, invokes, numeric literals)."""
import sys, zipfile
sys.stdout.reconfigure(encoding='utf-8')
from androguard.core.dex import DEX

APK_PATH = r"D:\Zcode\音乐\小米音乐.apk"
RID = 0x7f140ad0

zf = zipfile.ZipFile(APK_PATH)
dex_files = sorted(n for n in zf.namelist() if n.endswith('.dex'))

hits = []
for df in dex_files:
    data = zf.read(df)
    d = DEX(data)
    for c in d.get_classes():
        for m in c.get_methods():
            code = m.get_code()
        if not code:
            continue
        found = False
        strs, invs, lits = [], [], []
        for ins in code.get_bc().get_instructions():
            op = ins.get_name()
            if not found and op.startswith('const') and 'string' not in op:
                try:
                    lit = ins.get_literal()
                except Exception:
                    lit = None
                if lit is not None and lit == RID:
                    found = True
            if op == 'const-string' or op == 'const-string-jumbo':
                try:
                    strs.append(ins.get_string())
                except Exception:
                    pass
            elif op.startswith('invoke'):
                try:
                    invs.append(ins.get_operands()[2][2] if len(ins.get_operands()) > 2 else str(ins.get_operands()))
                except Exception:
                    pass
            elif op.startswith('const') and 'string' not in op:
                try:
                    lits.append(ins.get_literal())
                except Exception:
                    pass
        if found:
            hits.append((df, m.get_class_name(), m.get_name(), m.get_descriptor(), strs, invs, lits))
            print(f"\n===== HIT in {df} =====")
            print(f"  class: {m.get_class_name()}")
            print(f"  method: {m.get_name()} {m.get_descriptor()}")
            print(f"  strings referenced ({len(strs)}):")
            for s in strs[:40]:
                print(f"    {s!r}")
            print(f"  invokes ({len(invs)}):")
            for s in invs[:40]:
                print(f"    {s}")
            interesting_lits = [x for x in lits if x in (1000, 999, 10000, 0x7f140ad0, 1)]
            print(f"  const literals (interesting): {interesting_lits} / total {len(lits)}")

if not hits:
    print("No method found referencing the resource id via const. Trying R field path...")
