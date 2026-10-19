# -*- coding: utf-8 -*-
"""按资源名查询 resources.arsc 中的值（string/其它简单值）。"""
import struct, sys, zipfile, os
sys.stdout.reconfigure(encoding='utf-8')

# 宿主 APK 路径：可用环境变量 XMPU_APK 覆盖
APK_PATH = os.environ.get("XMPU_APK", r"E:\QQ下载\base.apk")
NAMES = sys.argv[1:] or [
    "free_mode_menu_title", "welfare_center_menu_title", "nav_quick_play_title",
    "mine_task_bar_title_highlight", "quick_play", "nav_recommend", "nav_listen_book",
]


def parse_string_pool(data, base):
    ctype, hsize, csize = struct.unpack_from('<HHI', data, base)
    assert ctype == 0x0001, hex(ctype)
    strcount, stylecount, flags = struct.unpack_from('<III', data, base + 8)
    strstart, stylestart = struct.unpack_from('<II', data, base + 20)
    utf8 = flags & (1 << 8)
    out = []
    for i in range(strcount):
        o = struct.unpack_from('<I', data, base + 28 + i * 4)[0]
        so = base + strstart + o
        if utf8:
            n = data[so]
            so += 2 if n & 0x80 else 1
            n2 = data[so]
            so += 2 if n2 & 0x80 else 1
            end = data.index(b'\x00', so)
            out.append(data[so:end].decode('utf-8', errors='replace'))
        else:
            n = struct.unpack_from('<H', data, so)[0]
            so += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from('<H', data, so)[0]
                so += 2
            out.append(data[so:so + n * 2].decode('utf-16-le', errors='replace'))
    return out


with zipfile.ZipFile(APK_PATH) as z:
    data = z.read('resources.arsc')

pos = 12
ctype = struct.unpack_from('<H', data, pos)[0]
assert ctype == 0x0001
value_pool = parse_string_pool(data, pos)
pos += struct.unpack_from('<I', data, pos + 4)[0]

wanted = set(NAMES)
found = {}


def walk_package(pbase):
    ptype, phsize, psize = struct.unpack_from('<HHI', data, pbase)
    pkg_id, = struct.unpack_from('<I', data, pbase + 8)
    typestrings, lastpubtype, keystrings, lastkey = struct.unpack_from('<IIII', data, pbase + 268)
    type_pool = parse_string_pool(data, pbase + typestrings)
    key_pool = parse_string_pool(data, pbase + keystrings)

    q = pbase + phsize
    end = pbase + psize
    while q + 8 <= end:
        ct, chs, csz = struct.unpack_from('<HHI', data, q)
        if ct == 0x0201:
            type_id = data[q + 8]
            entry_count = struct.unpack_from('<I', data, q + 12)[0]
            entries_start = struct.unpack_from('<I', data, q + 16)[0]
            hdr_size = struct.unpack_from('<H', data, q + 2)[0]
            # 只看默认配置（locale 为 0）
            for ei in range(entry_count):
                off = struct.unpack_from('<I', data, q + hdr_size + ei * 4)[0]
                if off == 0xFFFFFFFF:
                    continue
                ebase = q + entries_start + off
                esize, eflags, ekey = struct.unpack_from('<HHI', data, ebase)
                if eflags & 0x0001:
                    continue
                kname = key_pool[ekey] if ekey < len(key_pool) else None
                if kname not in wanted:
                    continue
                tname = type_pool[type_id - 1] if 0 < type_id <= len(type_pool) else f"type{type_id}"
                vsize, res0, dtype, dval = struct.unpack_from('<HBBI', data, ebase + 8)
                val = value_pool[dval] if dtype == 0x03 and dval < len(value_pool) else f"<type=0x{dtype:02x} data=0x{dval:08x}>"
                rid = (pkg_id << 24) | (type_id << 16) | ei
                found.setdefault(kname, []).append((rid, tname, val))
        if csz == 0:
            break
        q += csz


p = pos
while p + 8 <= len(data):
    ct, chs, csz = struct.unpack_from('<HHI', data, p)
    if csz == 0:
        break
    if ct == 0x0200:
        walk_package(p)
    p += csz

for name in NAMES:
    entries = found.get(name, [])
    if not entries:
        print(f"{name:<34} <not found>")
        continue
    for rid, tname, val in entries:
        print(f"{name:<34} 0x{rid:08x}  {tname:<10} {val!r}")
