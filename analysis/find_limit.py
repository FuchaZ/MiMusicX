# -*- coding: utf-8 -*-
"""Find the playlist 1000-song limit string in XM/QM dexes and resources."""
import os, struct, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))

def dex_strings(path):
    strings = set()
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'dex\n':
        return strings
    string_ids_size, string_ids_off = struct.unpack_from('<II', data, 56)
    for i in range(string_ids_size):
        off = struct.unpack_from('<I', data, string_ids_off + i * 4)[0]
        b0 = data[off]
        off += 1 if b0 < 0x80 else 2
        end = data.index(b'\x00', off)
        try:
            strings.add(data[off:end].decode('utf-8', errors='replace'))
        except Exception:
            pass
    return strings

def collect(dexdir):
    s = set()
    per_file = {}
    for fn in sorted(os.listdir(dexdir)):
        if fn.endswith('.dex'):
            t = dex_strings(os.path.join(dexdir, fn))
            per_file[fn] = t
            s |= t
    return s, per_file

needles = ["该歌单已超过1000首歌啦", "已超过1000", "1000首歌", "歌单已超过", "超过1000",
           "歌单最多", "最多添加", "该歌单", "首歌啦"]

for label, dexdir in [("XM", 'xm_dex'), ("QM", 'qm_dex')]:
    s, per_file = collect(os.path.join(HERE, dexdir))
    print(f"\n========== {label} ==========")
    for n in needles:
        hits = sorted(x for x in s if n in x)
        if hits:
            print(f"  [{n}] ({len(hits)}):")
            for h in hits[:15]:
                print(f"     {h!r}")
            # which dex files
            files = [fn for fn, t in per_file.items() if any(n in x for x in t)]
            print(f"     in dexes: {files}")

# also search resources.arsc (strings may live there)
for label, apk in [("XM", r"D:\Zcode\音乐\小米音乐.apk"), ("QM", r"D:\Zcode\音乐\QQ音乐.apk")]:
    with zipfile.ZipFile(apk) as z:
        names = [n for n in z.namelist() if 'resources.arsc' in n or n.startswith('res/values')][:5]
        arsc = z.read('resources.arsc') if 'resources.arsc' in z.namelist() else b''
    print(f"\n{label} resources.arsc size: {len(arsc)}")
    for n in ["该歌单已超过1000首歌啦", "已超过1000", "1000首歌", "歌单已超过", "首歌啦"]:
        cnt = arsc.count(n.encode('utf-8'))
        # also UTF-16LE
        cnt16 = arsc.count(n.encode('utf-16-le'))
        if cnt or cnt16:
            print(f"  arsc [{n}]: utf8={cnt} utf16={cnt16}")
