# -*- coding: utf-8 -*-
"""Manually parse resources.arsc: find resource ID(s) whose value == target string."""
import struct, sys, zipfile
sys.stdout.reconfigure(encoding='utf-8')

APK_PATH = r"D:\Zcode\音乐\小米音乐.apk"
TARGET = "该歌单已超过1000首歌啦"

def parse_string_pool(data, base):
    """Parse a ResStringPool chunk at base. Returns list of strings."""
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
            n = data[so]; so += 2 if n & 0x80 else 1
            n2 = data[so]; so += 2 if n2 & 0x80 else 1
            end = data.index(b'\x00', so)
            out.append(data[so:end].decode('utf-8', errors='replace'))
        else:
            n = struct.unpack_from('<H', data, so)[0]; so += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from('<H', data, so)[0]; so += 2
            out.append(data[so:so + n * 2].decode('utf-16-le', errors='replace'))
    return out

def uleb(data, off):
    result = 0; shift = 0
    while True:
        b = data[off]; off += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            return result, off
        shift += 7

with zipfile.ZipFile(APK_PATH) as z:
    data = z.read('resources.arsc')

print(f"arsc size: {len(data)}")
# ResTable header
_, _, table_size, package_count = struct.unpack_from('<HHII', data, 0)
pos = 12
value_pool = None
results = []

# First chunk should be global string pool
ctype = struct.unpack_from('<H', data, pos)[0]
if ctype == 0x0001:
    value_pool = parse_string_pool(data, pos)
    pos += struct.unpack_from('<I', data, pos + 4)[0]
    print(f"global value string pool: {len(value_pool)} strings")

# find target string index
tidx = None
for i, s in enumerate(value_pool):
    if s == TARGET:
        tidx = i
        break
print(f"target string index in value pool: {tidx}")

if tidx is None:
    sys.exit("target string not found in value pool")

def walk_package(pbase):
    ptype, phsize, psize = struct.unpack_from('<HHI', data, pbase)
    assert ptype == 0x0200, hex(ptype)
    pkg_id, = struct.unpack_from('<I', data, pbase + 8)
    name = data[pbase + 12:pbase + 12 + 256].decode('utf-16-le', errors='replace').rstrip('\x00')
    typestrings, lastpubtype, keystrings, lastkey = struct.unpack_from('<IIII', data, pbase + 268)
    type_pool = parse_string_pool(data, pbase + typestrings)
    key_pool = parse_string_pool(data, pbase + keystrings)
    print(f"\npackage id=0x{pkg_id:02x} name={name} types={len(type_pool)} keys={len(key_pool)}")
    # walk inner chunks after key string pool
    # inner chunks start after header; skip type & key pools
    inner = pbase + phsize
    end = pbase + psize
    # find first inner chunk: it's right after header usually typeStrings pool
    # we iterate chunks from pbase+phsize, but pools are chunks too
    q = pbase + phsize
    while q + 8 <= end:
        ct, chs, csz = struct.unpack_from('<HHI', data, q)
        if ct == 0x0201:  # RES_TABLE_TYPE_TYPE
            type_id = data[q + 8]
            entry_count = struct.unpack_from('<I', data, q + 12)[0]
            entries_start = struct.unpack_from('<I', data, q + 16)[0]
            # config size:
            cfg_size = struct.unpack_from('<I', data, q + 20)[0]
            hdr_size = struct.unpack_from('<H', data, q + 2)[0]
            offsets_off = hdr_size
            for ei in range(entry_count):
                off = struct.unpack_from('<I', data, q + offsets_off + ei * 4)[0]
                if off == 0xFFFFFFFF:
                    continue
                ebase = q + entries_start + off
                esize, eflags, ekey = struct.unpack_from('<HHI', data, ebase)
                if eflags & 0x0001:  # complex
                    continue
                vsize, res0, dtype, dval = struct.unpack_from('<HBBI', data, ebase + 8)
                if dtype == 0x03 and dval == tidx:
                    rid = (pkg_id << 24) | (type_id << 16) | ei
                    tname = type_pool[type_id - 1] if 0 < type_id <= len(type_pool) else f"type{type_id}"
                    kname = key_pool[ekey] if ekey < len(key_pool) else f"key{ekey}"
                    print(f"  >>> MATCH: resId=0x{rid:08x} type={tname} name={kname}")
                    results.append((rid, tname, kname))
        # advance: for 0x0201/0x0202 use chunk size; skip unknown safely
        if csz == 0:
            break
        q += csz

p = pos
seen_pkgs = 0
while p + 8 <= len(data) and seen_pkgs < package_count + 2:
    ct, chs, csz = struct.unpack_from('<HHI', data, p)
    if ct == 0x0200:
        walk_package(p)
        seen_pkgs += 1
        p += csz
    elif ct == 0x0001:
        p += csz
    else:
        p += csz if csz else len(data)

print("\n=== summary ===")
for rid, tname, kname in results:
    print(f"0x{rid:08x}  {tname}/{kname}")
