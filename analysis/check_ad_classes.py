# -*- coding: utf-8 -*-
"""Check XM for the specific classes QMHelper hooks need (ad SDK focus)."""
import os, struct

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
    for fn in sorted(os.listdir(dexdir)):
        if fn.endswith('.dex'):
            s |= dex_strings(os.path.join(dexdir, fn))
    return s

xm = collect(os.path.join(HERE, 'xm_dex'))
qm = collect(os.path.join(HERE, 'qm_dex'))

checks = {
  "SplashShowType(core.constant)": "Lcom/tencentmusic/ad/core/constant/SplashShowType;",
  "OperExpertSplashAdapter": "Lcom/tencentmusic/ad/adapter/madams/splash/OperExpertSplashAdapter;",
  "madams.splash pkg": "Lcom/tencentmusic/ad/adapter/madams/splash/",
  "madams pkg": "Lcom/tencentmusic/ad/adapter/madams/",
  "adapter pkg": "Lcom/tencentmusic/ad/adapter/",
  "tmead core pkg": "Lcom/tencentmusic/ad/core/",
  "tmead integration pkg": "Lcom/tencentmusic/ad/integration/",
  "tmead tmead pkg": "Lcom/tencentmusic/ad/tmead/",
}
print(f"{'target':<36} {'QQ':<3} {'XM':<3}")
for name, desc in checks.items():
    print(f"{name:<36} {'Y' if desc in qm else '-':<3} {'Y' if desc in xm else '-':<3}")

# strings containing madams / OperExpertSplash in both
for label, s in [("QQ", qm), ("XM", xm)]:
    m = sorted(x for x in s if 'madams' in x.lower() or 'OperExpert' in x or 'SplashShowType' in x)
    print(f"\n{label} strings w/ madams|OperExpert|SplashShowType ({len(m)}):")
    for x in m[:20]:
        print("   " + x)

# XM: what contains 'AdResponseData(retCode=' -> find class names around
# Also list XM splash-related strings
for label, s in [("QQ", qm), ("XM", xm)]:
    m = sorted(x for x in s if 'splash' in x.lower() and ('.' in x or '/' in x))[:25]
    print(f"\n{label} splash-ish strings sample:")
    for x in m:
        print("   " + x)

# XM: miui player own classes count
miui = [x for x in xm if x.startswith('Lcom/miui/player/') or x.startswith('Lcom/xiaomi/')]
print(f"\nXM com.miui.player/** / com.xiaomi/** classes: {len(miui)}")
from collections import Counter
c = Counter('/'.join(x.split('/')[:3]) for x in miui)
for k, v in c.most_common(10):
    print(f"   {k}: {v}")
