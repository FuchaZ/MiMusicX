# -*- coding: utf-8 -*-
"""轻量 dex 分析器：无需 androguard，可精确到「方法级」定位字段/方法/字符串引用。

用法:
    python dexscan.py index  <dex> <out.pkl>           # 建立索引缓存
    python dexscan.py find-ref <dex> <keyword> [--all] # 谁引用含 keyword 的字段/方法/字符串
    python dexscan.py dump <dex> <class-substr>        # 打印匹配类的字段/方法摘要
    python dexscan.py who-uses-field <dex> <fieldname>
    python dexscan.py who-uses-string <dex> <string>
"""
import sys, struct, pickle, os, re
sys.stdout.reconfigure(encoding='utf-8')


# ---------------- 基础读取 ----------------
def u16(b, o):
    return struct.unpack_from('<H', b, o)[0]


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def uleb(b, o):
    result = 0
    shift = 0
    while True:
        x = b[o]
        o += 1
        result |= (x & 0x7f) << shift
        if not (x & 0x80):
            return result, o
        shift += 7


class Dex:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.b = f.read()
        b = self.b
        assert b[:4] == b'dex\n', "not a dex"
        self.string_ids_size = u32(b, 0x38)
        self.string_ids_off = u32(b, 0x3c)
        self.type_ids_size = u32(b, 0x40)
        self.type_ids_off = u32(b, 0x44)
        self.proto_ids_size = u32(b, 0x48)
        self.proto_ids_off = u32(b, 0x4c)
        self.field_ids_size = u32(b, 0x50)
        self.field_ids_off = u32(b, 0x54)
        self.method_ids_size = u32(b, 0x58)
        self.method_ids_off = u32(b, 0x5c)
        self.class_defs_size = u32(b, 0x60)
        self.class_defs_off = u32(b, 0x64)
        self._strings = None
        self._types = None

    # 字符串池
    @property
    def strings(self):
        if self._strings is None:
            b = self.b
            out = []
            for i in range(self.string_ids_size):
                off = u32(b, self.string_ids_off + i * 4)
                _, pay = uleb(b, off)
                end = b.find(b'\x00', pay)
                out.append(b[pay:end].decode('utf-8', errors='replace'))
            self._strings = out
        return self._strings

    @property
    def types(self):
        if self._types is None:
            self._types = [self.strings[u32(self.b, self.type_ids_off + i * 4)]
                           for i in range(self.type_ids_size)]
        return self._types

    def field(self, idx):
        o = self.field_ids_off + idx * 8
        cls_idx, type_idx, name_idx = struct.unpack_from('<HHI', self.b, o)
        return self.types[cls_idx], self.types[type_idx], self.strings[name_idx]

    def method(self, idx):
        o = self.method_ids_off + idx * 8
        cls_idx, proto_idx, name_idx = struct.unpack_from('<HHI', self.b, o)
        po = self.proto_ids_off + proto_idx * 12
        ret_idx, params_off = struct.unpack_from('<II', self.b, po + 4)
        params = self.params(params_off)
        return self.types[cls_idx], self.strings[name_idx], self.types[ret_idx], params

    def params(self, off):
        if off == 0:
            return []
        n = u32(self.b, off)
        return [self.types[u16(self.b, off + 4 + i * 2)] for i in range(n)]

    def method_keyword_search(self, kw):
        return [(i,) + self.method(i) for i in range(self.method_ids_size)
                if kw in self.method(i)[1] or kw in self.method(i)[0]]

    # 类定义遍历
    def classes(self):
        """yield (descriptor, class_data 解析结果)"""
        b = self.b
        for ci in range(self.class_defs_size):
            o = self.class_defs_off + ci * 32
            class_idx = u32(b, o)
            class_data_off = u32(b, o + 24)
            desc = self.types[class_idx]
            yield desc, self.class_data(class_data_off)

    def class_data(self, off):
        if off == 0:
            return {'static_fields': [], 'instance_fields': [], 'direct_methods': [], 'virtual_methods': []}
        b = self.b
        sf, off = uleb(b, off)
        inf, off = uleb(b, off)
        dm, off = uleb(b, off)
        vm, off = uleb(b, off)
        out = {'static_fields': [], 'instance_fields': [], 'direct_methods': [], 'virtual_methods': []}

        def fields(n, off):
            arr = []
            idx = 0
            for _ in range(n):
                diff, off = uleb(b, off)
                acc, off = uleb(b, off)
                idx += diff
                arr.append((idx, acc))
            return arr, off

        def methods(n, off):
            arr = []
            idx = 0
            for _ in range(n):
                diff, off = uleb(b, off)
                acc, off = uleb(b, off)
                code_off, off = uleb(b, off)
                idx += diff
                arr.append((idx, acc, code_off))
            return arr, off

        out['static_fields'], off = fields(sf, off)
        out['instance_fields'], off = fields(inf, off)
        out['direct_methods'], off = methods(dm, off)
        out['virtual_methods'], off = methods(vm, off)
        return out

    def insns(self, code_off):
        """返回 (insns_u16_tuple, insns_bytes_offset)"""
        b = self.b
        insns_size = u32(b, code_off + 12)
        start = code_off + 16
        return insns_size, start

    # ---- 方法体内引用扫描 ----
    def scan_code(self, code_off):
        """返回 dict: fields=set(fieldname), methods=set('cls->name'), strings=set(), consts=set()"""
        b = self.b
        n, start = self.insns(code_off)
        end = start + n * 2
        fields, methods, strings, consts = set(), set(), set(), set()
        i = start
        while i + 2 <= end:
            op = b[i]
            # --- 字段访问: iget/iput/sget/sput 都带 field idx ---
            if 0x52 <= op <= 0x6d:
                if i + 4 > end:
                    break
                fidx = u16(b, i + 2)
                if fidx < self.field_ids_size:
                    _, _, fname = self.field(fidx)
                    fields.add(fname)
                i += 4 if not (0x53 <= op <= 0x58 or 0x60 <= op <= 0x6d) else 4
                continue
            # --- invoke 族 ---
            if op in (0x6e, 0x6f, 0x70, 0x71, 0x72):
                midx = u16(b, i + 2)
                if midx < self.method_ids_size:
                    cls, name, _, _ = self.method(midx)
                    methods.add(f'{cls}->{name}')
                i += 6
                continue
            if op in (0x74, 0x75, 0x76, 0x77, 0x78):
                midx = u16(b, i + 2)
                if midx < self.method_ids_size:
                    cls, name, _, _ = self.method(midx)
                    methods.add(f'{cls}->{name}')
                i += 6
                continue
            # --- const-string ---
            if op == 0x1a:
                sidx = u16(b, i + 2)
                if sidx < self.string_ids_size:
                    strings.add(self.strings[sidx])
                i += 4
                continue
            if op == 0x1b:
                sidx = u32(b, i + 2)
                if sidx < self.string_ids_size:
                    strings.add(self.strings[sidx])
                i += 6
                continue
            # --- const / const-wide (11n / 21s / 21h / 31i / 51l) ---
            if op == 0x12:
                consts.add(b[i + 1] << 24 >> 24)
                i += 2
                continue
            if op in (0x13, 0x14, 0x15):
                consts.add(u16(b, i + 2))
                i += 4
                continue
            if op == 0x16:
                consts.add(struct.unpack_from('<i', b, i + 2)[0])
                i += 6
                continue
            if op == 0x17:
                consts.add(struct.unpack_from('<q', b, i + 2)[0])
                i += 10
                continue
            i += 2
        return {'fields': fields, 'methods': methods, 'strings': strings, 'consts': consts}

    def all_methods(self):
        """yield (class_desc, method_name, params, ret, code_off)"""
        for desc, data in self.classes():
            for kind in ('direct_methods', 'virtual_methods'):
                for m_idx, acc, code_off in data[kind]:
                    cls, name, ret, params = self.method(m_idx)
                    yield desc, name, params, ret, code_off


def cmd_find_ref(dexpath, kw, mode='all'):
    d = Dex(dexpath)
    print(f"# dex={os.path.basename(dexpath)} keyword={kw!r}")
    n = 0
    for desc, name, params, ret, code_off in d.all_methods():
        if not code_off:
            continue
        try:
            info = d.scan_code(code_off)
        except Exception:
            continue
        hit = []
        if mode in ('all', 'field'):
            hit += [f"field:{x}" for x in info['fields'] if kw.lower() in x.lower()]
        if mode in ('all', 'method'):
            hit += [f"method:{x}" for x in info['methods'] if kw.lower() in x.lower()]
        if mode in ('all', 'string'):
            hit += [f"string:{x!r}" for x in info['strings'] if kw.lower() in x.lower()]
        if hit:
            n += 1
            print(f"\n{desc}  ->  {name}")
            for h in sorted(set(hit)):
                print(f"    {h}")
    print(f"\n-- {n} method(s) referenced {kw!r}")


def cmd_dump(dexpath, substr):
    d = Dex(dexpath)
    s = substr.lower()
    for desc, data in d.classes():
        if s not in desc.lower():
            continue
        print(f"\n========== {desc} ==========")
        for kind in ('static_fields', 'instance_fields'):
            for f_idx, acc in data[kind]:
                _, ftype, fname = d.field(f_idx)
                print(f"  [{kind[0:6]}] {fname} : {ftype}")
        for kind in ('direct_methods', 'virtual_methods'):
            print(f"  ---- {kind} ----")
            for m_idx, acc, code_off in data[kind]:
                cls, name, ret, params = d.method(m_idx)
                print(f"    {'0x%04x' % acc} {name}({', '.join(params)}){ret}  code=0x{code_off:x}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == 'find-ref':
        cmd_find_ref(sys.argv[2], sys.argv[3],
                     sys.argv[4] if len(sys.argv) > 4 else 'all')
    elif cmd == 'dump':
        cmd_dump(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
