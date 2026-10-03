# -*- coding: utf-8 -*-
"""Debug: verify scan works; search R field name in dexes; find sget refs."""
import sys, zipfile, struct
sys.stdout.reconfigure(encoding='utf-8')
from androguard.core.dex import DEX

APK_PATH = r"D:\Zcode\音乐\小米音乐.apk"
NAME = "qq_music_playlist_song_over_size"
RID = 0x7f140ad0

zf = zipfile.ZipFile(APK_PATH)
dex_files = sorted(n for n in zf.namelist() if n.endswith('.dex'))

for df in dex_files:
    data = zf.read(df)
    # raw search for the field name string
    if NAME.encode() in data:
        print(f"{df}: raw contains field name '{NAME}'")
    d = DEX(data)
    n_methods = 0
    n_with_code = 0
    r_fields = []
    sget_hits = []
    const_hits = []
    for c in d.get_classes():
        for m in c.get_methods():
            n_methods += 1
            code = m.get_code()
            if not code:
                continue
            n_with_code += 1
            for ins in code.get_bc().get_instructions():
                op = ins.get_name()
                if op.startswith('sget'):
                    try:
                        ops = ins.get_operands()
                        # (kind, reg), (KIND, idx, name)
                        for o in ops[1:]:
                            if len(o) >= 3 and isinstance(o[2], str) and NAME in o[2]:
                                sget_hits.append((m.get_class_name(), m.get_name(), o[2]))
                    except Exception:
                        pass
                elif op.startswith('const') and 'string' not in op and 'wide' not in op:
                    try:
                        if ins.get_literal() == RID:
                            const_hits.append((m.get_class_name(), m.get_name()))
                    except Exception:
                        pass
    print(f"{df}: classes={len(list(d.get_classes()))} methods={n_methods} with_code={n_with_code} const_hits={len(const_hits)} sget_hits={len(sget_hits)}")
    for cn, mn, fn in sget_hits[:10]:
        print(f"   sget: {cn}->{mn} field={fn}")
    for cn, mn in const_hits[:10]:
        print(f"   const: {cn}->{mn}")
    del d
