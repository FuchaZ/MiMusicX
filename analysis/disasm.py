# -*- coding: utf-8 -*-
"""轻量 dex 反汇编：按类名/方法名定位并打印 smali 风格指令。

用法:
    python disasm.py <dex> <class-substr> [method-substr]
    python disasm.py <dex> --list <class-substr>        # 只列方法
"""
import sys, struct, os
sys.stdout.reconfigure(encoding='utf-8')

from dexscan import Dex

# 每条 opcode 的指令宽度（unit 数）
WIDTH = [1] * 256
for op in (0x02, 0x05, 0x08, 0x13, 0x15, 0x16, 0x19, 0x1a, 0x1c, 0x1f, 0x20,
           0x22, 0x23, 0x29, 0x2d, 0x2e, 0x2f, 0x30, 0x31,
           0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
           0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d,
           0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f, 0x50, 0x51,
           0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0x5b, 0x5c, 0x5d, 0x5e, 0x5f,
           0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6a, 0x6b, 0x6c, 0x6d,
           0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0x9b, 0x9c, 0x9d,
           0x9e, 0x9f, 0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa9, 0xaa,
           0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7,
           0xd8, 0xd9, 0xda, 0xdb, 0xdc, 0xdd, 0xde, 0xdf, 0xe0, 0xe1, 0xe2,
           0xfe, 0xff):
    WIDTH[op] = 2
for op in (0x03, 0x06, 0x09, 0x14, 0x17, 0x1b, 0x24, 0x25, 0x26, 0x2a, 0x2b, 0x2c,
           0x6e, 0x6f, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78,
           0xfc, 0xfd):
    WIDTH[op] = 3
for op in (0x18,):
    WIDTH[op] = 5
WIDTH[0xfa] = 4
WIDTH[0xfb] = 4

NAMES = {
    0x00: 'nop', 0x01: 'move', 0x02: 'move/from16', 0x03: 'move/16',
    0x04: 'move-wide', 0x05: 'move-wide/from16', 0x06: 'move-wide/16',
    0x07: 'move-object', 0x08: 'move-object/from16', 0x09: 'move-object/16',
    0x0a: 'move-result', 0x0b: 'move-result-wide', 0x0c: 'move-result-object',
    0x0d: 'move-exception', 0x0e: 'return-void', 0x0f: 'return', 0x10: 'return-wide',
    0x11: 'return-object',
    0x12: 'const/4', 0x13: 'const/16', 0x14: 'const', 0x15: 'const/high16',
    0x16: 'const-wide/16', 0x17: 'const-wide/32', 0x18: 'const-wide',
    0x19: 'const-wide/high16', 0x1a: 'const-string', 0x1b: 'const-string/jumbo',
    0x1c: 'const-class', 0x1d: 'monitor-enter', 0x1e: 'monitor-exit',
    0x1f: 'check-cast', 0x20: 'instance-of', 0x21: 'array-length',
    0x22: 'new-instance', 0x23: 'new-array', 0x24: 'filled-new-array',
    0x25: 'filled-new-array/range', 0x26: 'fill-array-data', 0x27: 'throw',
    0x28: 'goto', 0x29: 'goto/16', 0x2a: 'goto/32',
    0x2b: 'packed-switch', 0x2c: 'sparse-switch',
    0x2d: 'cmpl-float', 0x2e: 'cmpg-float', 0x2f: 'cmpl-double',
    0x30: 'cmpg-double', 0x31: 'cmp-long',
    0x32: 'if-eq', 0x33: 'if-ne', 0x34: 'if-lt', 0x35: 'if-ge',
    0x36: 'if-gt', 0x37: 'if-le',
    0x38: 'if-eqz', 0x39: 'if-nez', 0x3a: 'if-ltz', 0x3b: 'if-gez',
    0x3c: 'if-gtz', 0x3d: 'if-lez',
    0x44: 'aget', 0x45: 'aget-wide', 0x46: 'aget-object', 0x47: 'aget-boolean',
    0x48: 'aget-byte', 0x49: 'aget-char', 0x4a: 'aget-short',
    0x4b: 'aput', 0x4c: 'aput-wide', 0x4d: 'aput-object', 0x4e: 'aput-boolean',
    0x4f: 'aput-byte', 0x50: 'aput-char', 0x51: 'aput-short',
    0x52: 'iget', 0x53: 'iget-wide', 0x54: 'iget-object', 0x55: 'iget-boolean',
    0x56: 'iget-byte', 0x57: 'iget-char', 0x58: 'iget-short',
    0x59: 'iput', 0x5a: 'iput-wide', 0x5b: 'iput-object', 0x5c: 'iput-boolean',
    0x5d: 'iput-byte', 0x5e: 'iput-char', 0x5f: 'iput-short',
    0x60: 'sget', 0x61: 'sget-wide', 0x62: 'sget-object', 0x63: 'sget-boolean',
    0x64: 'sget-byte', 0x65: 'sget-char', 0x66: 'sget-short',
    0x67: 'sput', 0x68: 'sput-wide', 0x69: 'sput-object', 0x6a: 'sput-boolean',
    0x6b: 'sput-byte', 0x6c: 'sput-char', 0x6d: 'sput-short',
    0x6e: 'invoke-virtual', 0x6f: 'invoke-super', 0x70: 'invoke-direct',
    0x71: 'invoke-static', 0x72: 'invoke-interface',
    0x74: 'invoke-virtual/range', 0x75: 'invoke-super/range',
    0x76: 'invoke-direct/range', 0x77: 'invoke-static/range',
    0x78: 'invoke-interface/range',
    0x7b: 'neg-int', 0x7c: 'not-int', 0x7d: 'neg-long', 0x7e: 'not-long',
    0x7f: 'neg-float', 0x80: 'neg-double', 0x81: 'int-to-long',
    0x82: 'int-to-float', 0x83: 'int-to-double', 0x84: 'long-to-int',
    0x85: 'long-to-float', 0x86: 'long-to-double', 0x87: 'float-to-int',
    0x88: 'float-to-long', 0x89: 'float-to-double', 0x8a: 'double-to-int',
    0x8b: 'double-to-long', 0x8c: 'double-to-float', 0x8d: 'int-to-byte',
    0x8e: 'int-to-char', 0x8f: 'int-to-short',
    0xfa: 'invoke-polymorphic', 0xfb: 'invoke-polymorphic/range',
    0xfc: 'invoke-custom', 0xfd: 'invoke-custom/range',
    0xfe: 'const-method-handle', 0xff: 'const-method-type',
}
BIN = {0x90: 'add-int', 0x91: 'sub-int', 0x92: 'mul-int', 0x93: 'div-int',
       0x94: 'rem-int', 0x95: 'and-int', 0x96: 'or-int', 0x97: 'xor-int',
       0x98: 'shl-int', 0x99: 'shr-int', 0x9a: 'ushr-int', 0x9b: 'add-long',
       0x9c: 'sub-long', 0x9d: 'mul-long', 0x9e: 'div-long', 0x9f: 'rem-long',
       0xa0: 'and-long', 0xa1: 'or-long', 0xa2: 'xor-long', 0xa3: 'shl-long',
       0xa4: 'shr-long', 0xa5: 'ushr-long', 0xa6: 'add-float', 0xa7: 'sub-float',
       0xa8: 'mul-float', 0xa9: 'div-float', 0xaa: 'rem-float',
       0xab: 'add-double', 0xac: 'sub-double', 0xad: 'mul-double',
       0xae: 'div-double', 0xaf: 'rem-double'}
BIN2ADDR = {0xb0: 'add-int/2addr', 0xb1: 'sub-int/2addr', 0xb2: 'mul-int/2addr',
            0xb3: 'div-int/2addr', 0xb4: 'rem-int/2addr', 0xb5: 'and-int/2addr',
            0xb6: 'or-int/2addr', 0xb7: 'xor-int/2addr', 0xb8: 'shl-int/2addr',
            0xb9: 'shr-int/2addr', 0xba: 'ushr-int/2addr', 0xbb: 'add-long/2addr',
            0xbc: 'sub-long/2addr', 0xbd: 'mul-long/2addr', 0xbe: 'div-long/2addr',
            0xbf: 'rem-long/2addr', 0xc0: 'and-long/2addr', 0xc1: 'or-long/2addr',
            0xc2: 'xor-long/2addr', 0xc3: 'shl-long/2addr', 0xc4: 'shr-long/2addr',
            0xc5: 'ushr-long/2addr', 0xc6: 'add-float/2addr', 0xc7: 'sub-float/2addr',
            0xc8: 'mul-float/2addr', 0xc9: 'div-float/2addr', 0xca: 'rem-float/2addr',
            0xcb: 'add-double/2addr', 0xcc: 'sub-double/2addr', 0xcd: 'mul-double/2addr',
            0xce: 'div-double/2addr', 0xcf: 'rem-double/2addr'}
LIT16 = {(0xd0 + i): n + '/lit16' for i, n in enumerate(
    ['add-int', 'rsub-int', 'mul-int', 'div-int', 'rem-int', 'and-int', 'or-int', 'xor-int'])}
LIT8 = {(0xd8 + i): n + '/lit8' for i, n in enumerate(
    ['add-int', 'rsub-int', 'mul-int', 'div-int', 'rem-int', 'and-int', 'or-int',
     'xor-int', 'shl-int', 'shr-int', 'ushr-int'])}


def opname(op):
    if op in NAMES:
        return NAMES[op]
    if op in BIN:
        return BIN[op]
    if op in BIN2ADDR:
        return BIN2ADDR[op]
    if op in LIT16:
        return LIT16[op]
    if op in LIT8:
        return LIT8[op]
    return f'op_0x{op:02x}'


def disasm_method(d, code_off, base_label=''):
    b = d.b
    n_units = struct.unpack_from('<I', b, code_off + 12)[0]
    start = code_off + 16
    regs = struct.unpack_from('<H', b, code_off)[0]
    ins = struct.unpack_from('<H', b, code_off + 2)[0]
    outs = struct.unpack_from('<H', b, code_off + 4)[0]
    print(f"    # regs={regs} ins={ins} outs={outs} units={n_units}")
    i = start
    end = start + n_units * 2
    while i < end:
        pc = (i - start) // 2
        op = b[i]
        # payload 检测
        if op == 0x00 and i + 1 < end:
            ident = struct.unpack_from('<H', b, i + 2)[0] if i + 4 <= end else 0
            if ident == 0x0100:  # packed-switch-payload
                size = struct.unpack_from('<H', b, i + 2)[0]
                cnt = struct.unpack_from('<H', b, i + 8)[0]
                print(f"  {pc:04x}: packed-switch-payload ({cnt} targets)")
                i += 8 + cnt * 4
                continue
            if ident == 0x0200:  # sparse-switch-payload
                cnt = struct.unpack_from('<H', b, i + 2)[0]
                print(f"  {pc:04x}: sparse-switch-payload ({cnt} targets)")
                i += 4 + cnt * 8
                continue
            if ident == 0x0300:  # fill-array-data-payload
                elem_w = struct.unpack_from('<H', b, i + 2)[0]
                size = struct.unpack_from('<I', b, i + 4)[0]
                print(f"  {pc:04x}: array-data-payload (size={size})")
                i += 8 + ((size * elem_w + 1) // 2) * 2
                continue

        w = WIDTH[op]
        args = ''
        if op == 0x1a:
            sidx = struct.unpack_from('<H', b, i + 2)[0]
            s = d.strings[sidx] if sidx < d.string_ids_size else f'<str{sidx}>'
            args = f'v{b[i+1]&0xf}, {s!r}'
        elif op == 0x1b:
            sidx = struct.unpack_from('<I', b, i + 2)[0]
            s = d.strings[sidx] if sidx < d.string_ids_size else f'<str{sidx}>'
            args = f'v{b[i+1]}, {s!r}'
        elif op in (0x6e, 0x6f, 0x70, 0x71, 0x72):
            midx = struct.unpack_from('<H', b, i + 2)[0]
            cls, name, ret, params = d.method(midx)
            nargs = (op - 0x6e) if op < 0x74 else 0
            args = f'{{{nargs} args}}, {cls}->{name}({" ".join(params)}){ret}'
        elif op in (0x74, 0x75, 0x76, 0x77, 0x78):
            midx = struct.unpack_from('<H', b, i + 2)[0]
            cnt = b[i + 1]
            cls, name, ret, params = d.method(midx)
            args = f'{{v{b[i+2]} .. {cnt}}}, {cls}->{name}({" ".join(params)}){ret}'
        elif 0x52 <= op <= 0x6d:
            fidx = struct.unpack_from('<H', b, i + 2)[0]
            fcls, ftype, fname = d.field(fidx)
            args = f'v{b[i+1]&0xf}, {fcls}->{fname}:{ftype}'
        elif op == 0x1c or op == 0x22 or op == 0x1f or op == 0x20 or op == 0x23:
            tidx = struct.unpack_from('<H', b, i + 2)[0]
            t = d.types[tidx] if tidx < d.type_ids_size else f'<type{tidx}>'
            args = f'v{b[i+1]&0xf}, {t}'
        elif op == 0x12:
            v = b[i + 1]
            val = ((v >> 4) & 0xf) << 28 >> 28
            args = f'v{v & 0xf}, {val}'
        elif op in (0x13, 0x15):
            val = struct.unpack_from('<h', b, i + 2)[0]
            args = f'v{b[i+1]}, {val}' + (' << 16' if op == 0x15 else '')
        elif op == 0x14:
            val = struct.unpack_from('<i', b, i + 2)[0]
            args = f'v{b[i+1]}, {val}'
        elif op in (0x32, 0x33, 0x34, 0x35, 0x36, 0x37):
            off = struct.unpack_from('<h', b, i + 2)[0]
            args = f'v{b[i+1]&0xf}, v{b[i+1]>>4}, +{off:x}'
        elif op in (0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d):
            off = struct.unpack_from('<h', b, i + 2)[0]
            args = f'v{b[i+1]}, +{off:x}'
        elif op == 0x28:
            off = struct.unpack_from('<b', b, i + 1)[0]
            args = f'+{off:x}'
        elif op == 0x29:
            off = struct.unpack_from('<h', b, i + 2)[0]
            args = f'+{off:x}'
        elif op == 0x2a:
            off = struct.unpack_from('<i', b, i + 2)[0]
            args = f'+{off:x}'
        elif op == 0x2b or op == 0x2c:
            off = struct.unpack_from('<i', b, i + 2)[0]
            args = f'v{b[i+1]}, +{off:x}'
        elif op in (0x0e, 0x0f, 0x10, 0x11, 0x0a, 0x0b, 0x0c, 0x0d, 0x1d, 0x1e, 0x27,
                    0x21):
            if op in (0x0f, 0x10, 0x11, 0x0a, 0x0b, 0x0c, 0x0d, 0x21):
                args = f'v{b[i+1]}'
        elif op in (0x01, 0x04, 0x07):
            args = f'v{b[i+1]&0xf}, v{b[i+1]>>4}'
        elif op in (0x02, 0x05, 0x08, 0x7b, 0x7c, 0x7d, 0x7e, 0x7f, 0x80,
                    0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
                    0x8a, 0x8b, 0x8c, 0x8d, 0x8e, 0x8f):
            if op < 0x7b:
                args = f'v{b[i+1]}, v{struct.unpack_from("<H", b, i + 2)[0]}'
            else:
                args = f'v{b[i+1]&0xf}, v{b[i+1]>>4}'
        elif op in BIN:
            args = f'v{b[i+1]&0xf}, v{b[i+1]>>4}, v{b[i+2]&0xf}'
        elif op in BIN2ADDR:
            args = f'v{b[i+1]&0xf}, v{b[i+1]>>4}'
        elif op in LIT16:
            val = struct.unpack_from('<h', b, i + 2)[0]
            args = f'v{b[i+1]&0xf}, v{b[i+1]>>4}, {val}'
        elif op in LIT8:
            val = struct.unpack_from('<b', b, i + 3)[0]
            args = f'v{b[i+1]}, v{b[i+2]}, {val}'

        print(f"  {pc:04x}: {opname(op):<26} {args}")
        i += WIDTH[op] * 2


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    dexpath = sys.argv[1]
    cls_sub = sys.argv[2]
    meth_sub = sys.argv[3] if len(sys.argv) > 3 else None
    d = Dex(dexpath)
    s = cls_sub.lower()
    shown = 0
    for desc, data in d.classes():
        if s not in desc.lower():
            continue
        for kind in ('direct_methods', 'virtual_methods'):
            for m_idx, acc, code_off in data[kind]:
                _, name, ret, params = d.method(m_idx)
                if meth_sub and meth_sub.lower() not in name.lower():
                    continue
                if meth_sub is None and code_off == 0:
                    continue
                print(f"\n===== {desc}->{name}({' '.join(params)}){ret}  [{kind}] =====")
                if code_off == 0:
                    print("    <abstract/native>")
                    continue
                try:
                    disasm_method(d, code_off)
                except Exception as e:
                    print(f"    <disasm error: {e}>")
                shown += 1
    print(f"\n-- {shown} method(s) shown")


if __name__ == '__main__':
    main()
