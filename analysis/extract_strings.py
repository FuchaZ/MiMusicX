# -*- coding: utf-8 -*-
"""提取 dex 中包含关键字的完整字符串（string_data_item = uleb128 utf16_len + MUTF-8 + NUL）。"""
import sys, zipfile, os
sys.stdout.reconfigure(encoding='utf-8')

# 宿主 APK 路径：可用环境变量 XMPU_APK 覆盖
APK_PATH = os.environ.get("XMPU_APK", r"E:\QQ下载\base.apk")
NEEDLES = ['免费听', '听书']


def read_uleb(data, off):
    result = 0
    shift = 0
    while True:
        b = data[off]
        off += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            return result, off
        shift += 7


def mutf8_utf16_len(raw):
    """返回 MUTF-8 字节串的 utf16 长度；遇非法序列返回 None。"""
    n = 0
    i = 0
    L = len(raw)
    while i < L:
        b = raw[i]
        if b < 0x80:
            n += 1
            i += 1
        elif (b & 0xE0) == 0xC0:
            n += 1
            i += 2
        elif (b & 0xF0) == 0xE0:
            n += 1
            i += 3
        elif (b & 0xF8) == 0xF0:
            n += 2          # 4 字节 = surrogate pair = 2 个 utf16 单元
            i += 4
        else:
            return None
    if i != L:
        return None
    return n


def strings_containing(data, needle):
    """返回 [(完整字符串, 文件内偏移)]。"""
    out = []
    nb = needle.encode('utf-8')
    start = 0
    while True:
        i = data.find(nb, start)
        if i < 0:
            break
        start = i + 1
        for back in range(1, 4):
            pos = i - back
            if pos < 0:
                continue
            try:
                length, pay = read_uleb(data, pos)
            except Exception:
                continue
            if pay != i:
                continue
            end = data.find(b'\x00', pay)
            if end < 0:
                continue
            raw = data[pay:end]
            if mutf8_utf16_len(raw) != length:
                continue
            try:
                s = raw.decode('utf-8')
            except Exception:
                s = raw.decode('utf-8', errors='replace')
            out.append((s, pos))
            break
    return out


z = zipfile.ZipFile(APK_PATH)
for n in sorted(x for x in z.namelist() if x.endswith('.dex')):
    data = z.read(n)
    found = []
    for nd in NEEDLES:
        for s, off in strings_containing(data, nd):
            found.append((nd, s, off))
    if not found:
        continue
    print(f"\n========== {n} ==========")
    seen = set()
    for nd, s, off in found:
        if s in seen:
            continue
        seen.add(s)
        print(f"  [{nd}] off={off}  {s!r}")
