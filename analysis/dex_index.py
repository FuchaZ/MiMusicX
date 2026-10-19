# -*- coding: utf-8 -*-
"""建立全量类索引：解析每个 dex 的 class_defs，输出 descriptor -> dex 文件映射。

用法:
    python dex_index.py                 # 生成索引到 classes_index.txt
    python dex_index.py <关键字…>        # 按关键字过滤打印（大小写不敏感）
"""
import sys, zipfile, struct, os
sys.stdout.reconfigure(encoding='utf-8')

# 宿主 APK 路径：可用环境变量 XMPU_APK 覆盖
APK_PATH = os.environ.get("XMPU_APK", r"E:\QQ下载\base.apk")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "classes_index.txt")


def uleb(data, off):
    result = 0
    shift = 0
    while True:
        b = data[off]
        off += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            return result, off
        shift += 7


def mutf8_len_ok(raw, want):
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
            n += 2
            i += 4
        else:
            return False
    return i == L and n == want


def read_strings(data):
    """返回 dex 字符串池列表；用 string_ids_off 反推 string_data 区算偏移解码失败时退回长度校验。"""
    string_ids_size, string_ids_off = struct.unpack_from('<II', data, 56)
    out = []
    for i in range(string_ids_size):
        off = struct.unpack_from('<I', data, string_ids_off + i * 4)[0]
        length, pay = uleb(data, off)
        end = data.find(b'\x00', pay)
        raw = data[pay:end]
        try:
            s = raw.decode('utf-8')
        except Exception:
            s = raw.decode('utf-8', errors='replace')
        out.append(s)
    return out


def class_descriptors(data, strings):
    # class_def_item.class_idx 是 type_ids 的索引；type_ids 里存的是 string_ids 索引
    type_ids_size, type_ids_off = struct.unpack_from('<II', data, 0x40)
    type_desc_idx = [
        struct.unpack_from('<I', data, type_ids_off + i * 4)[0] for i in range(type_ids_size)
    ]
    class_defs_size, class_defs_off = struct.unpack_from('<II', data, 0x60)
    out = []
    for i in range(class_defs_size):
        base = class_defs_off + i * 32
        class_idx = struct.unpack_from('<I', data, base)[0]
        out.append(strings[type_desc_idx[class_idx]])
    return out


def build():
    z = zipfile.ZipFile(APK_PATH)
    rows = []
    for n in sorted(x for x in z.namelist() if x.endswith('.dex')):
        data = z.read(n)
        strings = read_strings(data)
        for desc in class_descriptors(data, strings):
            rows.append((desc, n))
    rows.sort()
    with open(OUT, 'w', encoding='utf-8') as f:
        for desc, n in rows:
            f.write(f"{n}\t{desc}\n")
    print(f"total classes: {len(rows)} -> {OUT}")
    import collections
    c = collections.Counter(n for _, n in rows)
    for k in sorted(c):
        print(f"  {k:<16} {c[k]}")


def search(keys):
    keys = [k.lower() for k in keys]
    n_hit = 0
    with open(OUT, encoding='utf-8') as f:
        for line in f:
            dex, desc = line.rstrip('\n').split('\t')
            low = desc.lower()
            if all(k in low for k in keys):
                print(f"{dex:<16} {desc}")
                n_hit += 1
    print(f"-- {n_hit} class(es) matched {keys}")


if __name__ == '__main__':
    args = sys.argv[1:]
    if args:
        search(args)
    else:
        build()
