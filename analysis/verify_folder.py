# -*- coding: utf-8 -*-
"""Verify FolderInfo methods/flags + other refs of the two limit strings + their arsc values."""
import sys, zipfile, struct
sys.stdout.reconfigure(encoding='utf-8')
from androguard.core.dex import DEX

APK_PATH = r"D:\Zcode\音乐\小米音乐.apk"

# 1) arsc values for the sibling strings
import subprocess
from androguard.core.axml import ARSCParser
a = None
with zipfile.ZipFile(APK_PATH) as z:
    arsc_data = z.read('resources.arsc')
arsc = ARSCParser(arsc_data)
for name in ["qq_music_playlist_song_over_size", "qq_music_create_playlist_song_over_size", "network_tips_not_available", "qq_music_not_bind_account"]:
    # find resId via string values
    pass

# simpler: reuse arsc scan approach — find entries by name via androguard
try:
    from androguard.core.axml import ARSCResTableConfig
    # androguard: get_string_resources gives default locale strings map name->value? API: arsc.get_string_resources(package)
    pkgs = arsc.get_packages_names()
    for p in pkgs:
        res = arsc.get_string_resources(p)
        for k, v in res.items():
            if 'over_size' in str(k) or 'song_over' in str(k):
                print(f"arsc[{p}] {k} = {v!r}")
except Exception as e:
    print("arsc via androguard failed:", e)

# 2) FolderInfo class info + who else calls getCount with const 1000 nearby
zf = zipfile.ZipFile(APK_PATH)
data8 = zf.read('classes8.dex')
d = DEX(data8)
print("\n=== FolderInfo class in classes8 ===")
for c in d.get_classes():
    if c.get_name() == 'Lcom/tencent/qqmusic/core/folder/FolderInfo;':
        print("class access:", hex(c.get_access_flags()), "super:", c.get_superclassname())
        for m in c.get_methods():
            print(f"  method: {hex(m.get_access_flags())} {m.get_name()} {m.get_descriptor()}")

# 3) find all methods that reference the other string R field
for dex_name, target_field in [
    ('classes8.dex', 'qq_music_create_playlist_song_over_size'),
    ('classes8.dex', 'qq_music_playlist_song_over_size'),
]:
    data = zf.read(dex_name)
    dd = DEX(data)
    print(f"\n=== refs to {target_field} in {dex_name} ===")
    for c in dd.get_classes():
        for m in c.get_methods():
            code = m.get_code()
            if not code:
                continue
            for ins in code.get_bc().get_instructions():
                op = ins.get_name()
                if op.startswith('sget'):
                    try:
                        for o in ins.get_operands()[1:]:
                            if len(o) >= 3 and isinstance(o[2], str) and target_field in o[2]:
                                print(f"  {m.get_class_name()}->{m.get_name()}")
                    except Exception:
                        pass
